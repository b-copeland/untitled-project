"""
The admin's tools for one kingdom during a round (issue #219), on the Watch tab of the admin page (docs/admin.md):

* rename it (an offensive name, or one made to look like another kingdom's);
* delete one of its messages, from both kingdoms' copies;
* delete one of its posts from its galaxy's board;
* clear fields from its kingdom document that kingdoms do not have (``KINGDOM_FIELDS``), which a write made before
  those were checked could have left there. The kingdom write only merges, so this goes through the function app's
  ``/kingdom/<id>/removefields``.

``admin_kingdom`` (admin.py) shows what these act on: the messages, the board posts and the stray fields.
Admin only. Every change is decided on the document as it is (``occ.update``) or is a removal that is safe to repeat.
"""
import json

import flask
import flask_praetorian

import untitledapp.board as uabo
import untitledapp.getters as uag
import untitledapp.inputs as uin
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import REQUESTS_SESSION

bp = flask.Blueprint("adminkingdoms", __name__)

# What the store adds to a kingdom document, which is not a game field but must stay (see check_function_url).
STORE_FIELDS = {"id", "type", "_etag", "_ts", "_rid", "_self", "_attachments"}


def stray_fields(kingdom):
    """The fields of a kingdom document that kingdoms do not have."""
    return sorted(set(kingdom) - uas.KINGDOM_FIELDS - STORE_FIELDS)


def _url(path):
    return flask.current_app.config["AZURE_FUNCTION_ENDPOINT"] + path


def _headers():
    return {"x-functions-key": flask.current_app.config["AZURE_FUNCTION_KEY"]}


def _kingdom_or_404(kd_id):
    if str(kd_id) not in uag._get_kingdoms():
        flask.abort(flask.make_response(flask.jsonify({"message": "No such kingdom"}), 404))
    return str(kd_id)


def _answer(message, status=200, **extra):
    body = {"message": message, **({"status": "success"} if status == 200 else {}), **extra}
    return flask.jsonify(body), status


@bp.route('/api/admin/kingdom/<kd_id>/rename', methods=["POST"])
@flask_praetorian.roles_required('admin')
def rename(kd_id):
    """Body ``{"name"}``. The same rules as a player's choice (``_validate_kingdom_name``). Old news keeps the old name."""
    kd_id = _kingdom_or_404(kd_id)
    name = uin.text(uin.body(flask.request).get("name"), "Name").strip()
    valid, message = uam._validate_kingdom_name(name)
    if not valid:
        return _answer(message, 400)

    def in_list(document):
        kingdoms = dict(document["kingdoms"])
        if any(other != kd_id and existing.lower() == name.lower() for other, existing in kingdoms.items()):
            raise occ.Rejected("Kingdom name already exists")
        kingdoms[kd_id] = name
        return {"kingdoms": kingdoms}, None

    try:
        occ.update("/kingdoms", in_list)
        occ.update(f"/kingdom/{kd_id}", lambda kingdom: ({"name": name}, None))
    except occ.Rejected as rejection:
        return _answer(rejection.message, rejection.status)
    except occ.Busy:
        return _answer("Server is busy", 400)
    return _answer(f"Renamed to {name}")


@bp.route('/api/admin/kingdom/<kd_id>/messages/delete', methods=["POST"])
@flask_praetorian.roles_required('admin')
def delete_message(kd_id):
    """Body ``{"message": <an entry of the kingdom's messages, as the admin page shows it>}``. Taken out of this
    kingdom's messages and of the other kingdom's copy."""
    kd_id = _kingdom_or_404(kd_id)
    message = uin.body(flask.request).get("message")
    if not isinstance(message, dict):
        raise uin.BadInput("Choose a message to delete")
    mine = occ.read(f"/kingdom/{kd_id}/messages").get("messages", [])
    if message not in mine:
        return _answer("That message is not in this kingdom's messages", 400)
    removals = {kd_id: [message]}
    other = str(message.get("with"))
    if other in uag._get_kingdoms():
        theirs = occ.read(f"/kingdom/{other}/messages").get("messages", [])
        # The other side's copy: the same text at the same time, with this kingdom, from the other direction.
        copies = [entry for entry in theirs
                  if str(entry.get("with")) == kd_id and entry.get("from") != message.get("from")
                  and entry.get("time") == message.get("time") and entry.get("message") == message.get("message")]
        if copies:
            removals[other] = copies
    for owner, entries in removals.items():
        response = REQUESTS_SESSION.patch(_url(f"/kingdom/{owner}/messages"), headers=_headers(),
                                          data=json.dumps({"remove": entries}))
        if response.status_code >= 300:
            return _answer("The message could not be deleted. Try again.", 503)
    return _answer("Message deleted")


@bp.route('/api/admin/kingdom/<kd_id>/board/<post_id>/delete', methods=["POST"])
@flask_praetorian.roles_required('admin')
def delete_board_post(kd_id, post_id):
    """Delete a post from the board of the kingdom's galaxy, as its leader could (it is unpinned if pinned)."""
    kd_id = _kingdom_or_404(kd_id)
    galaxy = uag._get_galaxies_inverted()[0].get(kd_id)
    if galaxy is None:
        return _answer("That kingdom is in no galaxy", 400)

    def decide(document):
        return uabo.without_post(uabo.normalize(document), post_id, kd_id, is_leader=True), None

    try:
        occ.update(f"/galaxy/{galaxy}/board", decide)
    except occ.Rejected as rejection:
        return _answer(rejection.message, rejection.status)
    except occ.Busy:
        return _answer("Server is busy", 400)
    return _answer("Post deleted")


@bp.route('/api/admin/kingdom/<kd_id>/clearfields', methods=["POST"])
@flask_praetorian.roles_required('admin')
def clear_fields(kd_id):
    """Take out of the kingdom document every field kingdoms do not have (``stray_fields``). Safe to repeat."""
    kd_id = _kingdom_or_404(kd_id)
    stray = stray_fields(occ.read(f"/kingdom/{kd_id}"))
    if not stray:
        return _answer("The kingdom has no stray fields", removed=[])
    response = REQUESTS_SESSION.post(_url(f"/kingdom/{kd_id}/removefields"), headers=_headers(),
                                     data=json.dumps({"fields": stray}))
    if response.status_code >= 300:
        return _answer("The fields could not be cleared. Try again.", 503)
    removed = json.loads(response.text).get("removed", [])
    return _answer(f"Cleared {', '.join(removed) or 'nothing'}", removed=removed)
