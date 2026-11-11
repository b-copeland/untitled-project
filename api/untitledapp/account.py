import hashlib
import json
import os
import re

import flask
import flask_praetorian

from untitledapp import User, REQUESTS_SESSION
import untitledapp.mailer as mailer

bp = flask.Blueprint("account", __name__)

@bp.route('/api/login', methods=['POST'])
def login():
    guard = flask.current_app.extensions['praetorian']
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)
    user = guard.authenticate(username, password)
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@bp.route('/api/refresh', methods=['POST'])
def refresh():
    guard = flask.current_app.extensions['praetorian']
    
    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200

def _update_accounts():
    app = flask.current_app
    db = flask.current_app.extensions["sqlalchemy"]
    query = db.session.query(User).all()
    users = [{k: v for k, v in user.__dict__.items() if k != "_sa_instance_state"} for user in query]
    update_accounts = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/accounts',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
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
    db = flask.current_app.extensions["sqlalchemy"]
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
    db = flask.current_app.extensions["sqlalchemy"]
    if db.session.query(User).filter_by(username=username).count() >= 1:
        return False, "Account already exists"
    if len(username) == 0:
        return False, "Username must be at least 1 character"
    if len(password) == 0:
        return False, "Password must be at least 1 character"
    
    return True, ""

@bp.route('/api/signup', methods=['POST'])
def signup():
    db = flask.current_app.extensions["sqlalchemy"]
    guard = flask.current_app.extensions['praetorian']
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)

    email = (req.get('email') or '').strip()

    valid_signup, message = _validate_signup(username, password)
    if valid_signup and email and not _valid_email(email):
        valid_signup, message = False, "That does not look like an email address"
    if not valid_signup:
        ret = {'message': message}
        return (flask.jsonify(ret), 400)
    new_user = User(
        username=username,
        password=guard.hash_password(password),
        roles='verified',
        is_active=True,
        email=email or None,
        email_verified=False,
    )
    db.session.add(new_user)
    db.session.commit()
    _update_accounts()
    if email:
        _send_verification(new_user)
    ret = {'message': 'Successfully created!', "status": "success"}
    return (flask.jsonify(ret), 201)

@bp.route('/api/register', methods=['POST'])
def register():
    db = flask.current_app.extensions["sqlalchemy"]
    guard = flask.current_app.extensions['praetorian']
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
    db = flask.current_app.extensions["sqlalchemy"]
    guard = flask.current_app.extensions['praetorian']
    registration_token = guard.read_token_from_header()
    user = guard.get_user_from_registration_token(registration_token)
    user.roles = 'operator,verified'
    db.session.commit()
    _update_accounts()
    ret = {'access_token': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)


# --- Email: attach an address, verify it, and use it to recover an account -----------------------------------------
#
# Only a *verified* address can be used to recover an account, so typing someone else's address in at sign-up does not
# let anybody reset a password with it. The recovery endpoints always give the same answer whether or not the address
# is known, so they can not be used to find out who has an account.

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RECOVERY_REPLY = {"message": "If that address belongs to an account, we have sent an email to it.", "status": "success"}


def _valid_email(email):
    return len(email) <= 254 and bool(_EMAIL_PATTERN.match(email))


def _password_fingerprint(user):
    """Changes whenever the password does, which makes a reset link work exactly once."""
    return hashlib.sha256((user.password or "").encode()).hexdigest()[:16]


def _send_verification(user):
    token = mailer.make_token(mailer.VERIFY_EMAIL, {"id": user.id, "email": user.email})
    link = f"{mailer.frontend_url()}/verifyemail?token={token}"
    mailer.send_email(
        user.email,
        "Confirm your email address",
        f"Hello {user.username},\n\nConfirm this address for your account by opening:\n{link}\n\n"
        "The link works for 48 hours. If you did not ask for this, ignore this email.",
    )


@bp.route('/api/account', methods=['GET'])
@flask_praetorian.auth_required
def get_account():
    user = flask_praetorian.current_user()
    return flask.jsonify({"username": user.username, "email": user.email, "email_verified": bool(user.email_verified)})


@bp.route('/api/account/email', methods=['POST'])
@flask_praetorian.auth_required
def set_email():
    """Set or change the address on your account. It has to be verified again before it can be used for recovery."""
    db = flask.current_app.extensions["sqlalchemy"]
    email = (flask.request.get_json(force=True).get('email') or '').strip()
    if not _valid_email(email):
        return flask.jsonify({"message": "That does not look like an email address"}), 400
    user = flask_praetorian.current_user()
    user.email = email
    user.email_verified = False
    db.session.commit()
    _update_accounts()
    _send_verification(user)
    return flask.jsonify({"message": "We have sent you an email to confirm the address.", "status": "success"}), 200


@bp.route('/api/account/email/resend', methods=['POST'])
@flask_praetorian.auth_required
def resend_verification():
    user = flask_praetorian.current_user()
    if not user.email:
        return flask.jsonify({"message": "Your account has no email address"}), 400
    if user.email_verified:
        return flask.jsonify({"message": "Your email address is already confirmed", "status": "success"}), 200
    _send_verification(user)
    return flask.jsonify({"message": "We have sent you an email to confirm the address.", "status": "success"}), 200


@bp.route('/api/account/email/verify', methods=['POST'])
def verify_email():
    db = flask.current_app.extensions["sqlalchemy"]
    payload = mailer.read_token(mailer.VERIFY_EMAIL, flask.request.get_json(force=True).get('token') or '')
    user = db.session.get(User, payload["id"]) if payload else None
    # The token is for the address it was sent to; if the address was changed since, it no longer counts.
    if user is None or user.email != payload["email"]:
        return flask.jsonify({"message": "This link is invalid or has expired"}), 400
    user.email_verified = True
    db.session.commit()
    _update_accounts()
    return flask.jsonify({"message": "Your email address is confirmed", "status": "success"}), 200


def _accounts_for(email):
    db = flask.current_app.extensions["sqlalchemy"]
    email = (email or '').strip()
    if not _valid_email(email):
        return []
    return [
        user for user in db.session.query(User).filter(User.email == email, User.email_verified.is_(True)).all()
        if user.is_active
    ]


@bp.route('/api/account/forgot-password', methods=['POST'])
def forgot_password():
    for user in _accounts_for(flask.request.get_json(force=True).get('email')):
        token = mailer.make_token(mailer.RESET_PASSWORD, {"id": user.id, "fp": _password_fingerprint(user)})
        link = f"{mailer.frontend_url()}/resetpassword?token={token}"
        mailer.send_email(
            user.email,
            "Reset your password",
            f"Hello {user.username},\n\nChoose a new password by opening:\n{link}\n\n"
            "The link works once, for one hour. If you did not ask for this, ignore this email and your password "
            "stays as it is.",
        )
    return flask.jsonify(RECOVERY_REPLY), 200


@bp.route('/api/account/reset-password', methods=['POST'])
def reset_password():
    db = flask.current_app.extensions["sqlalchemy"]
    guard = flask.current_app.extensions['praetorian']
    req = flask.request.get_json(force=True)
    payload = mailer.read_token(mailer.RESET_PASSWORD, req.get('token') or '')
    user = db.session.get(User, payload["id"]) if payload else None
    if user is None or not user.is_active or payload["fp"] != _password_fingerprint(user):
        return flask.jsonify({"message": "This link is invalid or has expired"}), 400
    password = req.get('password') or ''
    if len(password) == 0:
        return flask.jsonify({"message": "Password must be at least 1 character"}), 400
    user.password = guard.hash_password(password)
    db.session.commit()
    _update_accounts()
    return flask.jsonify({"message": "Your password has been changed", "status": "success"}), 200


@bp.route('/api/account/forgot-username', methods=['POST'])
def forgot_username():
    users = _accounts_for(flask.request.get_json(force=True).get('email'))
    if users:
        names = "\n".join(f"  {user.username}" for user in users)
        mailer.send_email(
            users[0].email,
            "Your username",
            f"The accounts using this address are:\n{names}\n\nIf you did not ask for this, ignore this email.",
        )
    return flask.jsonify(RECOVERY_REPLY), 200
