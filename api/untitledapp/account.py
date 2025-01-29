import json
import os

import flask
import flask_praetorian

from untitledapp import guard, db, User, REQUESTS_SESSION

bp = flask.Blueprint("account", __name__)

@bp.route('/api/login', methods=['POST'])
def login():
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)
    user = guard.authenticate(username, password)
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@bp.route('/api/refresh', methods=['POST'])
def refresh():
    
    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200

def _update_accounts():
    query = db.session.query(User).all()
    users = [{k: v for k, v in user.__dict__.items() if k != "_sa_instance_state"} for user in query]
    update_accounts = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/accounts',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({"accounts": users}),
    )
    return update_accounts.text



@bp.route('/api/disable_user', methods=['POST'])
@flask_praetorian.auth_required
@flask_praetorian.roles_required('admin')
def disable_user():
    """
    Disables a user in the data store
    .. example::
        $ curl http://localhost:5000/disable_user -X POST \
          -H "Authorization: Bearer <your_token>" \
          -d '{"username":"Walter"}'
    """
    req = flask.request.get_json(force=True)
    usr = User.query.filter_by(username=req.get('username', None)).one()
    usr.is_active = False
    db.session.commit()
    _update_accounts()
    return flask.jsonify(message='disabled user {}'.format(usr.username))

def _validate_signup(
    username,
    password,
):
    if db.session.query(User).filter_by(username=username).count() >= 1:
        return False, "Account already exists"
    if len(username) == 0:
        return False, "Username must be at least 1 character"
    if len(password) == 0:
        return False, "Password must be at least 1 character"
    
    return True, ""

@bp.route('/api/signup', methods=['POST'])
def signup():
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)

    valid_signup, message = _validate_signup(username, password)
    if not valid_signup:
        ret = {'message': message}
        return (flask.jsonify(ret), 400)
    new_user = User(
        username=username,
        password=guard.hash_password(password),
        roles='verified',
        is_active=True,
    )
    db.session.add(new_user)
    db.session.commit()
    _update_accounts()
    ret = {'message': 'Successfully created!', "status": "success"}
    return (flask.jsonify(ret), 201)

@bp.route('/api/register', methods=['POST'])
def register():
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    email = req.get('email', None)
    password = req.get('password', None)
    new_user = User(
        username=username,
        password=guard.hash_password(password),
        roles='operator',
        is_active=False,
    )
    db.session.add(new_user)
    db.session.commit()
    _update_accounts()
    guard.send_registration_email(
        email,
        user=new_user,
        confirmation_sender="domnusgame@gmail.com",
        confirmation_uri="http://localhost:3000/finalize",
        subject="Confirm your registration"
    )
    ret = {'message': 'successfully sent registration email to user {}'.format(
        new_user.username
    )}
    return (flask.jsonify(ret), 201)


@bp.route('/api/finalize')
def finalize():
    registration_token = guard.read_token_from_header()
    user = guard.get_user_from_registration_token(registration_token)
    user.roles = 'operator,verified'
    db.session.commit()
    _update_accounts()
    ret = {'access_token': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)