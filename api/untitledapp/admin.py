import json
import os

import flask
import flask_praetorian

import untitledapp.misc as uam
from untitledapp import guard, User, REQUESTS_SESSION

bp = flask.Blueprint("admin", __name__)

@bp.route('/api/adminlogin', methods=['POST'])
def admin_login():
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)
    user = guard.authenticate(username, password)
    if "admin" not in user.roles:
        return flask.jsonify({"message": "Not authorized"})
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@bp.route('/api/adminrefresh', methods=['POST'])
@flask_praetorian.roles_required('admin')
def admin_refresh():
    
    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200

@bp.route('/api/updatestate', methods=["POST"])
@flask_praetorian.roles_required('admin')
def update_state():
    """
    Update initial state
    """
    app = flask.current_app
    req = flask.request.get_json(force=True)

    if "game_start" in req:
        create_response = REQUESTS_SESSION.post(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({
                "item": "scores",
                "state": {
                    "last_update": req["game_start"]
                },
            }),
        )        
        create_response = REQUESTS_SESSION.post(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({
                "item": "empires",
                "state": {
                    "last_update": req["game_start"]
                },
            }),
        )        
    
    update_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(req)
    )
    return flask.jsonify(update_response.text), 200


@bp.route('/api/createstate', methods=["POST"])
@flask_praetorian.roles_required('admin')
def create_state():
    """
    Create galaxies
    """
    app = flask.current_app
    req = flask.request.get_json(force=True)

    num_galaxies = int(req["num_galaxies"])
    max_galaxy_size = int(req["max_galaxy_size"])
    avg_size_new_galaxy = int(req["avg_size_new_galaxy"])

    for i in range(0, num_galaxies):
        galaxy_id = f"1:{i + 1}"
        uam._create_galaxy(galaxy_id)
    
    update_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({
            "max_galaxy_size": max_galaxy_size,
            "avg_size_new_galaxy": avg_size_new_galaxy,
            "active_policies": [],
        })
    )
    return flask.jsonify(update_response.text), 200

@bp.route('/api/resetstate', methods=["POST"])
@flask_praetorian.roles_required('admin')
def reset_state():
    """
    Return game to initial state
    """
    
    app = flask.current_app
    create_response = REQUESTS_SESSION.post(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/resetstate',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    )
    # A new round is open for play again; the finished one stays in its archive.
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + '/updatestate',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"game_over": ""}),
    )
    # Users outlive the round (the function app's reset keeps their documents); only their kingdoms go.
    for user in User.all():
        if user.kd_id not in (None, "") or user.kd_created or user.kd_death_date not in (None, ""):
            user.save(kd_id=None, kd_created=False, kd_death_date=None)
    return flask.jsonify(create_response.text), 200

@bp.route('/api/admin/bots', methods=["POST"])
@flask_praetorian.roles_required('admin')
def create_bots():
    """
    Add bots, e.g. ``{"explorer": 25, "attacker": 25, "intel": 25, "thief": 25}``. See docs/bots.md.
    """
    import untitledapp.bots as bots

    counts = flask.request.get_json(force=True)
    unknown = set(counts) - set(bots.ARCHETYPES)
    if unknown:
        return flask.jsonify({"message": f"Unknown bot types {sorted(unknown)}; choose from {sorted(bots.ARCHETYPES)}"}), 400
    if sum(int(n) for n in counts.values()) > 200:
        return flask.jsonify({"message": "Create at most 200 bots at a time"}), 400
    try:
        created = bots.create_bots(counts)
    except ValueError as error:
        return flask.jsonify({"message": str(error)}), 400
    return flask.jsonify({"message": f"Created {len(created)} bots", "status": "success", "bots": created}), 201


# --- watching a round -------------------------------------------------------------------------------------------------
# Admin only, and everything is shown: these routes are for the maintainer watching a round (bots included), not for
# players. The universe view reads four shared documents whatever the number of kingdoms; a kingdom's details are two
# reads, made when the admin opens it.


@bp.route('/api/admin/universe', methods=["GET"])
@flask_praetorian.roles_required('admin')
def admin_universe():
    """Every kingdom at a glance: name, galaxy, empire, stars, networth and points, and the round's times."""
    import untitledapp.getters as uag

    names = uag._get_kingdoms()
    kd_empire, empires_info, _, galaxy_members = uag._get_empires_inverted()
    galaxy_of = {kd: galaxy for galaxy, members in galaxy_members.items() for kd in members}
    scores = uag._get_scores()
    state = uag._get_state().get("state", {})
    empires = empires_info.get("empires", {})
    kingdoms = []
    for kd_id, name in names.items():
        empire = kd_empire.get(kd_id)
        kingdoms.append({
            "kd_id": kd_id,
            "name": name,
            # Bots are named bot_<playstyle>_<n> (bots.py).
            "playstyle": name.split("_")[1] if name.startswith("bot_") and name.count("_") >= 2 else "player",
            "galaxy": galaxy_of.get(kd_id),
            "empire": empires.get(empire, {}).get("name") if empire else None,
            "stars": scores.get("stars", {}).get(kd_id, 0),
            "networth": scores.get("networth", {}).get(kd_id, 0),
            "points": round(scores.get("points", {}).get(kd_id, 0), 1),
        })
    return flask.jsonify({
        "kingdoms": sorted(kingdoms, key=lambda kd: -kd["networth"]),
        "game_start": state.get("game_start"),
        "game_end": state.get("game_end"),
        "empires": {eid: {"name": e.get("name"), "galaxies": e.get("galaxies", []), "war": e.get("war", [])}
                    for eid, e in empires.items()},
    }), 200


@bp.route('/api/admin/kingdom/<kd_id>', methods=["GET"])
@flask_praetorian.roles_required('admin')
def admin_kingdom(kd_id):
    """One kingdom in full, with its bot's style, phase, memory and decisions if it is a bot, and its latest news."""
    import untitledapp.getters as uag
    import untitledapp.occ as occ

    kingdom = uag._get_kd_info(kd_id)
    if not kingdom or "kdId" not in kingdom:
        return flask.jsonify({"message": "No such kingdom"}), 400
    kingdom = {key: value for key, value in kingdom.items() if not key.startswith("_")}
    news = occ.read(f'/kingdom/{kd_id}/news').get("news", [])
    return flask.jsonify({"kingdom": kingdom, "news": news[-20:]}), 200
