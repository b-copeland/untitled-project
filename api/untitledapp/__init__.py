import collections
import datetime
import os
import random
import requests
import json
import time
import logging

from functools import wraps

import flask
import flask_sqlalchemy
import flask_praetorian
import flask_cors
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sock import Sock, ConnectionClosed

db = flask_sqlalchemy.SQLAlchemy()
guard = flask_praetorian.Praetorian()
cors = flask_cors.CORS()
mail = Mail()

REQUESTS_SESSION = requests.Session()

SOCK_HANDLERS = {}

# A generic user model that might be used by an app powered by flask-praetorian
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, unique=True)
    password = db.Column(db.Text)
    roles = db.Column(db.Text)
    kd_id = db.Column(db.Text)
    kd_created = db.Column(db.Boolean, default=False, server_default='false')
    is_active = db.Column(db.Boolean, default=True, server_default='true')
    is_verified = db.Column(db.Boolean, default=True, server_default='false')
    kd_death_date = db.Column(db.Text)

    @property
    def rolenames(self):
        try:
            return self.roles.split(',')
        except Exception:
            return []

    @classmethod
    def lookup(cls, username):
        return cls.query.filter_by(username=username).one_or_none()

    @classmethod
    def identify(cls, id):
        return cls.query.get(id)

    @property
    def identity(self):
        return self.id

    def is_valid(self):
        return self.is_active
    
class Locks(db.Model):
    lock_name = db.Column(db.Text, primary_key=True)
    expires_at = db.Column(db.Text)


# Initialize flask app for the example
app = flask.Flask(__name__, static_folder='../../build', static_url_path=None)
app.debug = True
app.config['SECRET_KEY'] = os.environ["SECRET_KEY"]
app.config['JWT_ACCESS_LIFESPAN'] = {'hours': 24}
app.config['JWT_REFRESH_LIFESPAN'] = {'hours': 24}
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'
app.config['MAIL_PASSWORD'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
app.config['AZURE_FUNCTION_ENDPOINT'] = os.environ.get('COSMOS_ENDPOINT')
app.config['AZURE_FUNCTION_KEY'] = os.environ.get('COSMOS_KEY')

app.logger.addHandler(logging.StreamHandler())


# Initialize the flask-praetorian instance for the app
guard.init_app(app, User)

# Initialize a local database for the example
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ["SQLALCHEMY_DATABASE_URI"]
db.init_app(app)

# Initializes CORS so that the api_tool can talk to the example app
cors.init_app(app)

mail.init_app(app)

sock = Sock(app)

def alive_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        kd_death_date = flask_praetorian.current_user().kd_death_date
        if kd_death_date not in (None, ""):
            return flask.jsonify({"message": "You can not do that because your kingdom is dead!"}), 400
        return f(*args, **kwargs)
    return decorated_function

def start_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        state = uag._get_state()
        time_now = datetime.datetime.now(datetime.timezone.utc)
        if time_now.isoformat() < state["state"]["game_start"]:
            return flask.jsonify({"message": "The game has not yet started!"}), 400
        return f(*args, **kwargs)
    return decorated_function

def before_start_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        state = uag._get_state()
        time_now = datetime.datetime.now(datetime.timezone.utc)
        if time_now.isoformat() > state["state"]["game_start"]:
            return flask.jsonify({"message": "The game has already started!"}), 400
        return f(*args, **kwargs)
    return decorated_function

def _mark_kingdom_death(kd_id):
    query = db.session.query(User).filter_by(kd_id=kd_id).all()
    user = query[0]
    user.kd_death_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.session.commit()
    uaa._update_accounts()
    try:
        ws = SOCK_HANDLERS[kd_id]
        ws.send(json.dumps({
            "message": f"You died!",
            "status": "warning",
            "category": "Dead",
            "delay": 999999,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return flask.jsonify(str(user.__dict__))

def _add_notifs(kd_id, categories):
    add_notifs_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({"add_categories": categories}),
    )

def _clear_notifs(kd_id, categories):
    clear_notifs_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({"clear_categories": categories}),
    )

def _get_notifs(kd_id):
    get_notifs_response = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    get_notifs_response_json = json.loads(get_notifs_response.text)
    return get_notifs_response_json


@app.route('/api/notifs', methods=['GET'])
@flask_praetorian.auth_required
def get_notifs():
    kd_id = flask_praetorian.current_user().kd_id
    notifs = _get_notifs(kd_id)
    return flask.jsonify(notifs), 200


@app.route('/api/clearnotifs', methods=['POST'])
@flask_praetorian.auth_required
def clear_notifs():
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)

    categories = req.get("categories", [])
    if categories:
        _clear_notifs(kd_id, categories)
    
    return "Cleared", 200


import untitledapp.account as uaa
import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.politics as uap
import untitledapp.refresh as uar
import untitledapp.shared as uas

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.glogging.Logger')
    gunicorn_error_handlers = logging.getLogger('gunicorn.error').handlers
    gunicorn_access_handlers = logging.getLogger('gunicorn.access').handlers
    app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.handlers.extend(gunicorn_error_handlers)
    app.logger.handlers.extend(gunicorn_access_handlers)
    app.logger.setLevel(gunicorn_logger.level)

def _custom_limit_key_func():
    try:
        token = guard.read_token_from_header()
    except:
        token = get_remote_address()
    return token

limiter = Limiter(
    _custom_limit_key_func,
    app=app,
    default_limits=["100 per minute",],
    storage_uri="memory://",
)

# Add users for the example
with app.app_context():
    db.create_all()
    accounts_response = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/accounts',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    accounts_json = json.loads(accounts_response.text)
    accounts = accounts_json["accounts"]
    for user in accounts:
        if db.session.query(User).filter_by(username=user["username"]).count() < 1:
            db.session.add(
                User(**user)
            )
    if db.session.query(User).filter_by(username='admin').count() < 1:
        db.session.add(User(
          username='admin',
          password=guard.hash_password(os.environ["ADMIN_PASSWORD"]),
          roles='operator,admin',
          kd_created=True,
		))
    db.session.commit()

def acquire_lock(lock_name, timeout=10):
    """
    Try to acquire a lock with a given name.
    
    :param lock_name: Name of the lock
    :param timeout: Expiry time for the lock in seconds
    :return: True if the lock was acquired, False otherwise
    """
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        expiration_time = now + datetime.timedelta(seconds=timeout)

        # Check if the lock is available or expired
        lock = db.session.query(Locks).filter(Locks.lock_name == lock_name).one_or_none()

        if lock is None or lock.expires_at <= now:
            # Acquire or update the lock
            db.session.merge(Locks(lock_name=lock_name, expires_at=expiration_time))
            db.session.commit()
            return True

        # Lock is already held and not expired
        return False
    except Exception as e:
        print(f"Failed to acquire lock: {e}")
        db.session.rollback()
        return False

def release_lock(lock_name):
    """
    Release a lock with a given name.
    
    :param lock_name: Name of the lock
    """
    try:
        # Delete the lock
        db.session.query(Locks).filter(Locks.lock_name == lock_name).delete()
        db.session.commit()
    except Exception as e:
        print(f"Failed to release lock: {e}")
        db.session.rollback()

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


def _create_galaxy(galaxy_id):
    create_galaxy_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    return create_galaxy_response.text

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
        _create_galaxy(galaxy_id)
    
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


@sock.route('/ws/listen')
# @flask_praetorian.auth_required
def listen(ws):
    while True:
        try:
            data = ws.receive()
            json_data = json.loads(data)

            sock.app.logger.info('Got data %s', str(data))
            jwt = json_data.get('jwt', None)
            if jwt:
                id = guard.extract_jwt_token(jwt)["id"]
                query = db.session.query(User).filter_by(id=id).all()
                user = query[0]
                sock.app.logger.info('Added %s to listeners', user.kd_id)
                SOCK_HANDLERS[user.kd_id] = ws

            sock.app.logger.info('Current handlers %s', SOCK_HANDLERS)
        except ConnectionClosed:
            sock.app.logger.info('Breaking handler')
            break
        except Exception as e:
            sock.app.logger.warning('Error handling listener %s', str(e))

        time.sleep(5)


def _validate_kingdom_name(
    name,    
):
    kingdoms = uag._get_kingdoms()
    if any((name.lower() == existing_name.lower() for existing_name in kingdoms.values())):
        return False, "Kingdom name already exists"
    
    if len(name) > 24:
        return False, "Kingdom name must be less than 25 characters"
    
    if len(name) == 0:
        return False, "Kingdom name must have at least one character"
    
    return True, ""

@app.route('/api/test1', methods=["GET"])
def test_long_redis_lock():
    got_lock = acquire_lock("test_lock")
    while not got_lock:
        time.sleep(0.01)
        got_lock = acquire_lock("test_lock")
    
    time.sleep(5)
    release_lock("test_lock")
    return flask.jsonify({"message": "Succeeded"}), 200

@app.route('/api/createkingdom', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_initial_kingdom():
    req = flask.request.get_json(force=True)
    user = flask_praetorian.current_user()

    if user.kd_id != "" and user.kd_id != None:
        return (flask.jsonify({"message": "You already have a kingdom ID"}), 400)

    valid_name, message = _validate_kingdom_name(req["kdName"])
    if not valid_name:
        return (flask.jsonify({"message": message}), 400)
    
    galaxies = uag._get_galaxy_info()
    size_galaxies = collections.defaultdict(list)
    for galaxy_id, kingdoms in galaxies.items():
        size_galaxies[len(kingdoms)].append(galaxy_id)

    smallest_galaxy_size = min(size_galaxies.keys())
    smallest_galaxies = size_galaxies[smallest_galaxy_size]

    chosen_galaxy = random.choice(smallest_galaxies)
    create_kd_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({"kingdom_name": req["kdName"], "galaxy": chosen_galaxy}),
    )
    if create_kd_response.status_code != 201:
        return (flask.jsonify({"message": "Error creating kingdom"}), 400)
    
    kd_id = create_kd_response.text

    for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
        item_id = f"{table}_{kd_id}"
        state = initial_state.copy()
        if table == "kingdom":
            state["kdId"] = kd_id
            state["name"] = req["kdName"]

        create_response = REQUESTS_SESSION.post(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({
                "item": item_id,
                "state": state,
            }),
        )        

    user.kd_id = kd_id
    db.session.commit()
    uaa._update_accounts()
    
    return flask.jsonify({"message": ""}), 200


@app.route('/api/resetkingdom', methods=["POST"])
@flask_praetorian.auth_required
@before_start_required
# @flask_praetorian.roles_required('verified')
def reset_initial_kingdom():    
    user = flask_praetorian.current_user()
    kd_id = user.kd_id
    kd_info = uag._get_kd_info(kd_id)
    for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
        item_id = f"{table}_{kd_id}"
        state = initial_state.copy()
        if table == "kingdom":
            state["kdId"] = kd_id
            state["name"] = kd_info["name"]

        create_response = REQUESTS_SESSION.post(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({
                "item": item_id,
                "state": state,
            }),
        )
        
    user.kd_created = False
    db.session.commit()
    uaa._update_accounts()
    return (flask.jsonify("Reset kingdom"), 200)

@app.route('/api/createkingdomdata')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom_data():
    """
    Return information to inform kingdom creator page
    """

    payload = {
        "total_points": uas.KINGDOM_CREATOR_STARTING_POINTS,
        "selection_points": uas.KINGDOM_CREATOR_POINTS,
        "total_stars": uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"],
    }
    return (flask.jsonify(payload), 200)

def _validate_kingdom_choices(
    unit_choices,
    structures_choices,
    race,
):
    sum_units_points = sum([
        value_unit * uas.KINGDOM_CREATOR_POINTS[key_unit]
        for key_unit, value_unit in unit_choices.items()
    ])
    sum_structures = sum(structures_choices.values())
    if any((value_unit < 0 for value_unit in unit_choices.values())):
        return False, "Unit values must be non-negative"
    if any((value_structure < 0 for value_structure in structures_choices.values())):
        return False, "Structures values must be non-negative"
    
    if uas.KINGDOM_CREATOR_STARTING_POINTS - sum_units_points < 0:
        return False, "You do not have that many unit points available"

    if sum_units_points != uas.KINGDOM_CREATOR_STARTING_POINTS:
        return False, "You must use all units points"
    
    if uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"] - sum_structures < 0:
        return False, "You do not have that many stars available for structures"

    if sum_structures != uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"]:
        return False, "You must use all stars for structures"
    
    if race not in uas.RACES:
        return False, "You must select a valid race"
    
    return True, ""

@app.route('/api/createkingdomchoices', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom_choices():
    req = flask.request.get_json(force=True)
    user = flask_praetorian.current_user()

    if user.kd_created:
        return (flask.jsonify({"message": "This kingdom has already been created"}), 400)

    unit_choices = {
        k: int(v or 0)
        for k, v in req["unitsChoices"].items()
    }
    structures_choices = {
        k: int(v or 0)
        for k, v in req["structuresChoices"].items()
    }
    race = req["race"]

    valid_kd, message = _validate_kingdom_choices(unit_choices, structures_choices, race)
    if not valid_kd:
        return (flask.jsonify({"message": message}), 400)
    
    kd_id = user.kd_id
    kd_info = uag._get_kd_info(kd_id)
    drones = unit_choices.pop("drones")

    payload = {}
    payload["drones"] = drones
    payload["units"] = {
        k: v + unit_choices.get(k, 0)
        for k, v in kd_info["units"].items()
    }
    payload["structures"] = {
        k: v + structures_choices.get(k, 0)
        for k, v in kd_info["structures"].items()
    }
    state = uag._get_state()
    start_time_datetime = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    payload["last_income"] = max(state["state"]["game_start"], datetime.datetime.now(datetime.timezone.utc).isoformat())
    payload["next_resolve"] = kd_info["next_resolve"]
    payload["next_resolve"]["spy_attempt"] = (
        max(datetime.datetime.now(datetime.timezone.utc), start_time_datetime)
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_SPY_ATTEMPT_TIME_MULTIPLIER"])
    ).isoformat()
    payload["coordinate"] = random.randint(0, 99)
    payload["race"] = race

    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )        

    user.kd_created = True
    db.session.commit()
    uaa._update_accounts()
    
    return (flask.jsonify({"message": ""}), 200)

def _validate_shields(req_values):

    if req_values.get("military", 0) > uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"]:
        return False, "Military shields must be at or below max shields value"
    if req_values.get("spy", 0) > uas.GAME_CONFIG["BASE_SPY_SHIELDS_MAX"]:
        return False, "Spy shields must be at or below max shields value"
    if req_values.get("spy_radar", 0) > uas.GAME_CONFIG["BASE_SPY_RADAR_MAX"]:
        return False, "Spy radar must be at or below max value"
    if req_values.get("missiles", 0) > uas.GAME_CONFIG["BASE_MISSILES_SHIELDS_MAX"]:
        return False, "Missiles shields must be at or below max shields value"
    if any((value < 0 for value in req_values.values())):
        return False, "Shields value must be non-negative"

    return True, ""

@app.route('/api/shields', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def set_shields():
    req = flask.request.get_json(force=True)
    req_values = {
        k: float(v or 0) / 100
        for k, v in req.items()
        if v != ""
    }
    valid_shields, error_message = _validate_shields(req_values)
    if not valid_shields:
        return flask.jsonify({"message": error_message}), 400
    
    
    kd_id = flask_praetorian.current_user().kd_id
    kd_info = uag._get_kd_info(kd_id)

    if kd_info["fuel"] <= 0:
        return flask.jsonify({"message": "You can't set shields without fuel"}), 400

    payload = {
        "shields": {
            **kd_info["shields"],
            **req_values,
        }
    }
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return flask.jsonify({"message": "Successfully updated shields", "status": "success"}), 200


@app.route('/api/messages/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def send_message(target_kd):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)

    kingdoms = uag._get_kingdoms()

    if len(req.get("message", "")) > 1024:
        return flask.jsonify({"message": "Messages must be less than 1024 characters"}), 400

    payload_from = {
        "time": req.get("time", ""),
        "with": target_kd,
        "from": True,
        "message": req.get("message", " "),
    }

    payload_to = {
        "time": req.get("time", ""),
        "with": kd_id,
        "from": False,
        "message": req.get("message", " "),
    }
    
    message_response_from = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/messages',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload_from)
    )
    message_response_to = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/messages',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload_to)
    )
    _add_notifs(target_kd, ["messages"])
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": f"New message from {kingdoms[kd_id]}!",
            "status": "info",
            "category": "Message",
            "delay": 30000,
            "update": ["messages"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    
    return (flask.jsonify({"message": "Message sent!", "status": "success"}), 200)



def _validate_spending(spending_input):
    """Confirm that spending request is valid"""

    values = spending_input.values()
    if any((value < 0 for value in values)):
        return False, "Spending values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Spending values must be less than 100%"
    if sum(values) > 1:
        return False, "Spending values must be less than 100%"
    
    return True, ""


@app.route('/api/spending', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def spending():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) != None:
        enabled = req["enabled"]
        payload = {'auto_spending_enabled': enabled}

        if enabled:
            next_resolve = kd_info_parse["next_resolve"]
            next_resolve["auto_spending"] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])).isoformat()
            payload["next_resolve"] = next_resolve
        else:
            total_funding = sum(kd_info_parse["funding"].values())
            next_resolve = kd_info_parse["next_resolve"]
            next_resolve["auto_spending"] = uas.DATE_SENTINEL
            payload["next_resolve"] = next_resolve
            payload["money"] = kd_info_parse["money"] + total_funding
            payload["funding"] = {
                k: 0
                for k in kd_info_parse["funding"]
            }

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if enabled:
            message = "Enabled auto spending and released funding"
        else:
            message = "Disabled auto spending"
        return (flask.jsonify({"message": message, "status": "success"}), 200)
    
    req_spending = {
        key: float(value or 0) / 100
        for key, value in req.items()
        if (value or 0) != 0
    }

    current_spending = kd_info_parse['auto_spending']
    new_spending = {
        **current_spending,
        **req_spending,
    }
    valid_spending, message = _validate_spending(new_spending)
    if not valid_spending:
        return (flask.jsonify({"message": message}), 400)

    payload = {'auto_spending': new_spending}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

@app.route('/api/share/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def share_kd(share_to):
    kd_id = flask_praetorian.current_user().kd_id

    galaxies_inverted, _ = uag._get_galaxies_inverted()
    if galaxies_inverted[kd_id] != galaxies_inverted[share_to]:
        return flask.jsonify("You can only share your kingdom to galaxymates"), 400

    kd_payload = {
        "new_revealed_to_galaxymates": [share_to]
    }
    share_to_payload = {
        "new_revealed_galaxymates": [kd_id]
    }
    kd_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    share_to_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{share_to}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(share_to_payload),
    )
    return (flask.jsonify(kd_response.text)), 200

@app.route('/api/unshare/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def unshare_kd(share_to):
    kd_id = flask_praetorian.current_user().kd_id

    kd_revealed = uag._get_revealed(kd_id)
    share_to_revealed = uag._get_revealed(share_to)

    galaxies_inverted, _ = uag._get_galaxies_inverted()
    if galaxies_inverted[kd_id] != galaxies_inverted[share_to]:
        return flask.jsonify("You can only share your kingdom to galaxymates"), 400

    kd_payload = {
        "revealed_to_galaxymates": [revealed_to_id for revealed_to_id in kd_revealed["revealed_to_galaxymates"] if revealed_to_id != share_to]
    }
    share_to_payload = {
        "revealed_galaxymates": [revealed_id for revealed_id in share_to_revealed["revealed_galaxymates"] if revealed_id != kd_id]
    }
    kd_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    share_to_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{share_to}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(share_to_payload),
    )
    return (flask.jsonify(kd_response.text)), 200


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path != "" and os.path.exists(os.path.join('..','build',path)):
        return app.send_static_file(path)
    else:
        return app.send_static_file('index.html')

# Run the example
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)