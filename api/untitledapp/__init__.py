import datetime
import os
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
    request_id = db.Column(db.Text)
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

import untitledapp.account as uaa
import untitledapp.admin as uaad
import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.misc as uam
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