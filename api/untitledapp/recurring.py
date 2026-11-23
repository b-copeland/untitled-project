"""
Recurring spy operations (issue #137): standing orders that use spy attempts as they come back, so a player who logs in
twice a day still uses them (tenet 1).

Two kinds, each on one target:

* **siphon**: Siphon Funds, again each time the last siphon it sent has run its course
  (``BASE_DRONES_SIPHON_TIME_MULTIPLIER``), and at the next free attempt after one fails.
* **intel**: an intel operation, again once the intel it reveals has run out (the game refuses to spy for intel that is
  still revealed), optionally shared with the galaxy for a cut.

They live on the kingdom as ``recurring`` (a list, missing on kingdoms made before it). Each entry carries ``next``,
the earliest time it may run, so the refresh finds the ones due in the document it has already read and costs nothing
for a kingdom with none due. Due entries run in the order they were added, one spy attempt each, **before the auto
rob**: the auto rob only gets the attempts left over (above its "keep").

An entry stops by itself, with a line in the player's news, when its target is dead, when it has failed
``stop_after_fails`` times in a row (0: never), when it has been refused ``REFUSALS_TO_STOP`` times in a row (the
operation is locked, say), or once its ``until`` has passed.
"""
import datetime
import json
import math
import uuid

import flask
import flask_praetorian

import untitledapp.getters as uag
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import REQUESTS_SESSION, alive_required
from untitledapp.push import push

bp = flask.Blueprint("recurring", __name__)

TYPES = ("siphon", "intel")
REFUSALS_TO_STOP = 3
NAMES = {"siphon": "siphon", "intel": "intel operation"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _epoch():
    return datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])


def entries(kd):
    return kd.get("recurring") or []


# ------------------------------------------------------------------------------------------------------ the route


def make_entry(req, kd_id, now=None):
    """
    ``(entry, None)`` for a valid request, or ``(None, message)``. Percent fields are 0-100 as the form sends them.
    """
    kind = req.get("type")
    if kind not in TYPES:
        return None, "Choose a siphon or an intel operation"
    target = str(req.get("target") or "")
    if not target:
        return None, "Choose a target"
    if target == str(kd_id):
        return None, "You can not spy on yourself"
    operation = "siphonfunds" if kind == "siphon" else req.get("operation")
    if kind == "intel" and operation not in uas.REVEAL_OPERATIONS:
        return None, "Choose an intel operation"
    try:
        drones_pct = float(req.get("drones_pct") or 0) / 100
        stop_after_fails = int(req.get("stop_after_fails") if req.get("stop_after_fails") not in (None, "") else 3)
        cut = float(req.get("cut") or 0)
    except (TypeError, ValueError):
        return None, "Numbers only, please"
    if not 0 < drones_pct <= 1:
        return None, "Send between 1% and 100% of your drones"
    if not 0 <= stop_after_fails <= 10:
        return None, "Stop after 0 to 10 failures in a row (0 never stops)"
    share = bool(req.get("share_to_galaxy")) and kind == "intel"
    if share and not 0 <= cut <= uas.GAME_CONFIG["BASE_MAX_SHARE_CUT"] * 100:
        return None, f"The cut is 0% to {uas.GAME_CONFIG['BASE_MAX_SHARE_CUT'] * 100:g}%"
    until = req.get("until") or None
    now = now or _now()
    if until:
        try:
            until = uas.utc(until).isoformat()
        except (TypeError, ValueError):
            return None, "That is not a time"
        if uas.utc(until) <= now:
            return None, "The end time has passed"
    return {
        "id": str(uuid.uuid4()),
        "type": kind,
        "target": target,
        "operation": operation,
        "drones_pct": drones_pct,
        "shielded": bool(req.get("shielded")),
        "share_to_galaxy": share,
        "cut": cut if share else 0,
        "stop_after_fails": stop_after_fails,
        "until": until,
        "next": now.isoformat(),
        "fails": 0,
        "refused": 0,
        "runs": 0,
        "last": None,
    }, None


@bp.route('/api/recurring', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def add_recurring():
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True) or {}
    entry, message = make_entry(req, kd_id)
    if entry is None:
        return flask.jsonify({"message": message}), 400
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    entry["target_name"] = uag._get_kingdoms().get(entry["target"], entry["target"])
    if entry["target"] not in galaxies_inverted:
        return flask.jsonify({"message": "There is no such kingdom"}), 400
    if galaxies_inverted[entry["target"]] == galaxies_inverted.get(str(kd_id)):
        return flask.jsonify({"message": "You can not spy on a galaxymate"}), 400

    def decide(kd_info):
        current = entries(kd_info)
        limit = uas.GAME_CONFIG["BASE_MAX_RECURRING_ENTRIES"]
        if len(current) >= limit:
            raise occ.Rejected(f"You can not have more than {limit} repeating operations")
        if any(e["target"] == entry["target"] and e["operation"] == entry["operation"] for e in current):
            raise occ.Rejected("That operation already repeats on that kingdom")
        return {"recurring": current + [entry]}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return flask.jsonify({"message": "It will repeat whenever a spy attempt is free", "status": "success"}), 200


@bp.route('/api/recurring/cancel', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def cancel_recurring():
    kd_id = flask_praetorian.current_user().kd_id
    entry_id = (flask.request.get_json(force=True) or {}).get("id")

    def decide(kd_info):
        current = entries(kd_info)
        kept = [e for e in current if e["id"] != entry_id]
        if len(kept) == len(current):
            raise occ.Rejected("That repeating operation is not there")
        return {"recurring": kept}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return flask.jsonify({"message": "Stopped repeating", "status": "success"}), 200


# ---------------------------------------------------------------------------------------------- in the refresh


def is_due(entry, now):
    return uas.utc(entry.get("next") or uas.DATE_SENTINEL) <= now


def _revealed_until(revealed_info, entry, now):
    """When the intel ``entry`` would reveal next becomes worth spying for: None if it can be spied for now."""
    if entry["target"] in revealed_info.get("revealed_galaxymates", []):
        return None
    held = revealed_info.get("revealed", {}).get(entry["target"], {})
    times = [uas.utc(held[stat]) for stat in uas.REVEAL_OPERATION_STATS[entry["operation"]] if stat in held]
    if len(times) < len(uas.REVEAL_OPERATION_STATS[entry["operation"]]) or min(times) <= now:
        return None
    return min(times)


def outcome(entry, result, now):
    """
    What one run did to ``entry``: ``(entry, stop_reason)``. ``result`` is ``("waited", until)``, ``("success",
    message)``, ``("failure", message)``, ``("refused", message)`` or ``("dead", message)``.
    """
    entry = dict(entry)
    kind, detail = result
    if kind == "waited":
        entry["next"] = detail.isoformat()
        return entry, None
    entry["runs"] = entry.get("runs", 0) + 1
    entry["last"] = {"time": now.isoformat(), "status": kind, "message": str(detail)}
    if kind == "dead":
        return entry, "its target is dead"
    if kind == "refused":
        entry["refused"] = entry.get("refused", 0) + 1
        entry["next"] = (now + _epoch()).isoformat()
        if entry["refused"] >= REFUSALS_TO_STOP:
            return entry, f"it was refused {REFUSALS_TO_STOP} times in a row ({str(detail).rstrip('.')})"
        return entry, None
    entry["refused"] = 0
    if kind == "success":
        entry["fails"] = 0
        if entry["type"] == "siphon":
            # Again when this siphon has run its course.
            entry["next"] = (now + datetime.timedelta(
                seconds=uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])).isoformat()
        else:
            # The next run finds when the intel runs out, and waits for it.
            entry["next"] = now.isoformat()
        return entry, None
    entry["fails"] = entry.get("fails", 0) + 1
    entry["next"] = now.isoformat()  # at the next free attempt
    limit = entry.get("stop_after_fails", 0)
    if limit and entry["fails"] >= limit:
        return entry, f"it failed {entry['fails']} times in a row"
    return entry, None


def _tell(kd_id, entry, message, status="info"):
    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"time": _now().isoformat(), "from": "", "news": message, "kind": "schedule"}),
    )
    uam._add_notifs(kd_id, ["news_kingdom"])
    push(kd_id, "schedules", message, status=status, update=["kingdom", "news"])


def _run(kd_id, entry, now, revealed):
    """Run one entry once. ``revealed`` reads the kingdom's revealed intel, at most once a tick."""
    import untitledapp.conquer as uac  # conquer imports the blueprints' helpers

    if entry["type"] == "intel":
        until = _revealed_until(revealed(), entry, now)
        if until is not None:
            return ("waited", until), False
    kingdom = uag._get_kd_info(kd_id)
    if int(kingdom.get("spy_attempts") or 0) < 1:
        return ("waited", now + _epoch() / 4), False
    req = {
        "drones": math.floor(entry["drones_pct"] * (kingdom.get("drones") or 0)),
        "shielded": entry.get("shielded", False),
        "operation": entry["operation"],
    }
    if entry["type"] == "intel":
        req["share_to_galaxy"] = entry.get("share_to_galaxy", False)
        req["cut"] = entry.get("cut", 0)
    _, payload, status, success = uac._spy(req, kd_id, entry["target"])
    message = (payload or {}).get("message", "")
    if status != 200:
        return ("dead" if "dead" in message else "refused", message), False
    return ("success" if success else "failure", message), True


def resolve_recurring(kd_id, time_update, kd_info):
    """
    Run the due recurring operations, one spy attempt each. Returns True if any spy operation ran (the kingdom
    changed). Nothing is read or written unless an entry is due and an attempt is free.
    """
    current = entries(kd_info)
    runnable = int(kd_info.get("spy_attempts") or 0) >= 1 and any(is_due(entry, time_update) for entry in current)
    ending = any(entry.get("until") and uas.utc(entry["until"]) <= time_update for entry in current)
    if not runnable and not ending:
        return False

    # Claim the due entries with a version-checked write (``next`` an epoch on), so two overlapping ticks do not both
    # run one, and drop those past their end. What each run did is written after.
    def claim(kingdom):
        claimed, ended, kept = [], [], []
        attempts = int(kingdom.get("spy_attempts") or 0)
        for entry in entries(kingdom):
            if entry.get("until") and uas.utc(entry["until"]) <= time_update:
                ended.append(entry)
                continue
            if is_due(entry, time_update) and len(claimed) < attempts:
                claimed.append(entry)
                entry = {**entry, "next": (time_update + _epoch()).isoformat()}
            kept.append(entry)
        if not claimed and not ended:
            return None, ([], [])
        return {"recurring": kept}, (claimed, ended)

    claimed, ended = occ.update(f'/kingdom/{kd_id}', claim)
    for entry in ended:
        _tell(kd_id, entry, f"Your repeating {NAMES[entry['type']]} on {entry.get('target_name', entry['target'])} has reached its end time and stopped.")
    if not claimed:
        return False

    revealed_info = {}

    def revealed():
        if "value" not in revealed_info:
            revealed_info["value"] = uag._get_revealed(kd_id)
        return revealed_info["value"]

    results, spied = {}, False
    for entry in claimed:
        try:
            result, ran = _run(kd_id, entry, time_update, revealed)
        except Exception:
            flask.current_app.logger.exception("Recurring %s failed for kingdom %s", entry.get("type"), kd_id)
            result, ran = ("refused", "Something went wrong"), False
        spied = spied or ran
        results[entry["id"]] = outcome(entry, result, time_update)

    def record(kingdom):
        kept, stopped = [], []
        for entry in entries(kingdom):
            if entry["id"] not in results:
                kept.append(entry)  # not run this tick, or added meanwhile
                continue
            new_entry, stop = results[entry["id"]]
            if stop:
                stopped.append((new_entry, stop))
            else:
                kept.append(new_entry)
        return {"recurring": kept}, stopped

    stopped = occ.update(f'/kingdom/{kd_id}', record)
    for entry, reason in stopped:
        _tell(kd_id, entry, f"Your repeating {NAMES[entry['type']]} on {entry.get('target_name', entry['target'])} stopped: {reason}.", "warning")
    return spied
