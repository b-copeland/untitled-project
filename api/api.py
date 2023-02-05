import datetime
import os
import requests
import sys
import json
import flask
import flask_sqlalchemy
import flask_praetorian
import flask_cors
from flask_mail import Mail

db = flask_sqlalchemy.SQLAlchemy()
guard = flask_praetorian.Praetorian()
cors = flask_cors.CORS()
mail = Mail()

REQUESTS_SESSION = requests.Session()

# A generic user model that might be used by an app powered by flask-praetorian
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, unique=True)
    password = db.Column(db.Text)
    roles = db.Column(db.Text)
    kd_id = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True, server_default='true')
    is_verified = db.Column(db.Boolean, default=True, server_default='false')

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


# Initialize flask app for the example
app = flask.Flask(__name__, static_folder='../build', static_url_path=None)
app.debug = True
app.config['SECRET_KEY'] = 'top secret'
app.config['JWT_ACCESS_LIFESPAN'] = {'hours': 24}
app.config['JWT_REFRESH_LIFESPAN'] = {'days': 30}
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'
app.config['MAIL_PASSWORD'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
app.config['AZURE_FUNCTION_ENDPOINT'] = os.environ.get('COSMOS_ENDPOINT')
app.config['AZURE_FUNCTION_KEY'] = os.environ.get('COSMOS_KEY')


# Initialize the flask-praetorian instance for the app
guard.init_app(app, User)

# Initialize a local database for the example
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.getcwd(), 'database.db')}"
db.init_app(app)

# Initializes CORS so that the api_tool can talk to the example app
cors.init_app(app)

mail.init_app(app)

# Add users for the example
with app.app_context():
    db.create_all()
    if db.session.query(User).filter_by(username='admin').count() < 1:
        db.session.add(User(
          username='admin',
          password=guard.hash_password('pass'),
          roles='operator,admin'
		))
    if db.session.query(User).filter_by(username='user').count() < 1:
        db.session.add(User(
          username='user',
          password=guard.hash_password('pass'),
          roles='verified',
          kd_id=0
		))
    db.session.commit()


# Set up some routes for the example
@app.route('/api/')
def home():
  	return {"Hello": "World"}, 200

@app.route('/api/login', methods=['POST'])
def login():
    """
    Logs a user in by parsing a POST request containing user credentials and
    issuing a JWT token.
    .. example::
       $ curl http://localhost:5000/api/login -X POST \
         -d '{"username":"Yasoob","password":"strongpassword"}'
    """
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)
    user = guard.authenticate(username, password)
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@app.route('/api/refresh', methods=['POST'])
def refresh():
    """
    Refreshes an existing JWT by creating a new one that is a copy of the old
    except that it has a refrehsed access expiration.
    .. example::
       $ curl http://localhost:5000/refresh -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    print("refresh request")
    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200


@app.route('/api/kingdom')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdom():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    return (flask.jsonify(kd_info_parse), 200)


@app.route('/api/protected')
@flask_praetorian.auth_required
@flask_praetorian.roles_required('verified')
def protected():
    """
    A protected endpoint. The auth_required decorator will require a header
    containing a valid JWT
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    return {"message": f'protected endpoint (allowed user {flask_praetorian.current_user().username})'}


@app.route('/api/disable_user', methods=['POST'])
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
    return flask.jsonify(message='disabled user {}'.format(usr.username))



@app.route('/api/register', methods=['POST'])
def register():
    """
    Registers a new user by parsing a POST request containing new user info and
    dispatching an email with a registration token
    .. example::
       $ curl http://localhost:5000/register -X POST \
         -d '{
           "username":"Brandt", \
           "password":"herlifewasinyourhands" \
           "email":"brandt@biglebowski.com"
         }'
    """
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


@app.route('/api/finalize')
def finalize():
    """
    Finalizes a user registration with the token that they were issued in their
    registration email
    .. example::
       $ curl http://localhost:5000/finalize -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    registration_token = guard.read_token_from_header()
    user = guard.get_user_from_registration_token(registration_token)
    user.roles = 'operator,verified'
    db.session.commit()
    ret = {'access_token': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@app.route('/api/blacklist_token', methods=['POST'])
@flask_praetorian.auth_required
@flask_praetorian.roles_required('admin')
def blacklist_token():
    """
    Blacklists an existing JWT by registering its jti claim in the blacklist.
    .. example::
       $ curl http://localhost:5000/blacklist_token -X POST \
         -d '{"token":"<your_token>"}'
    """
    req = flask.request.get_json(force=True)
    data = guard.extract_jwt_token(req['token'])
    blacklist.add(data['jti'])
    return flask.jsonify(message='token blacklisted ({})'.format(req['token']))

@app.route('/api/time')
@flask_praetorian.auth_required
def time():
    return (flask.jsonify(datetime.datetime.now().isoformat()), 200)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    print("Hello from catch all")
    if path != "" and os.path.exists(os.path.join('..','build',path)):
        return app.send_static_file(path)
    else:
        return app.send_static_file('index.html')

# Run the example
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)