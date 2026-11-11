import json
import os

import flask
import flask_praetorian

import untitledapp.account as uaa
import untitledapp.misc as uam
from untitledapp import guard, db, User, REQUESTS_SESSION

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
    query = db.session.query(User).all()
    for user in query:
        user.kd_id = None
        user.kd_created = False
        user.kd_death_date = None
    db.session.commit()
    uaa._update_accounts()
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
