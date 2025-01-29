import json
import os

import flask
import flask_praetorian

import untitledapp.account as uaa
import untitledapp.misc as uam
from untitledapp import app, guard, db, User, REQUESTS_SESSION

@app.route('/api/adminlogin', methods=['POST'])
def admin_login():
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)
    user = guard.authenticate(username, password)
    if "admin" not in user.roles:
        return flask.jsonify({"message": "Not authorized"})
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@app.route('/api/adminrefresh', methods=['POST'])
@flask_praetorian.roles_required('admin')
def admin_refresh():
    
    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200

@app.route('/api/updatestate', methods=["POST"])
@flask_praetorian.roles_required('admin')
def update_state():
    """
    Update initial state
    """
    req = flask.request.get_json(force=True)

    if "game_start" in req:
        create_response = REQUESTS_SESSION.post(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({
                "item": "scores",
                "state": {
                    "last_update": req["game_start"]
                },
            }),
        )        
        create_response = REQUESTS_SESSION.post(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({
                "item": "empires",
                "state": {
                    "last_update": req["game_start"]
                },
            }),
        )        
    
    update_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(req)
    )
    return flask.jsonify(update_response.text), 200


@app.route('/api/createstate', methods=["POST"])
@flask_praetorian.roles_required('admin')
def create_state():
    """
    Create galaxies
    """
    req = flask.request.get_json(force=True)

    num_galaxies = int(req["num_galaxies"])
    max_galaxy_size = int(req["max_galaxy_size"])
    avg_size_new_galaxy = int(req["avg_size_new_galaxy"])

    for i in range(0, num_galaxies):
        galaxy_id = f"1:{i + 1}"
        uam._create_galaxy(galaxy_id)
    
    update_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({
            "max_galaxy_size": max_galaxy_size,
            "avg_size_new_galaxy": avg_size_new_galaxy,
            "active_policies": [],
        })
    )
    return flask.jsonify(update_response.text), 200

@app.route('/api/resetstate', methods=["POST"])
@flask_praetorian.roles_required('admin')
def reset_state():
    """
    Return game to initial state
    """
    
    create_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/resetstate',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    query = db.session.query(User).all()
    for user in query:
        user.kd_id = None
        user.kd_created = False
        user.kd_death_date = None
    db.session.commit()
    uaa._update_accounts()
    return flask.jsonify(create_response.text), 200