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

UNITS = {
    'attack': {
        'offense': 5,
        'defense': 0,
        'cost': 300,
    },
    'defense': {
        'offense': 0,
        'defense': 5,
        'cost': 350,
    },
    'flex': {
        'offense': 6,
        'defense': 6,
        'cost': 900,
    },
}

STRUCTURES = [
    "homes",
    "mines",
    "fuel_plants",
    "hangars",
    "drone_factories",
]

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


@app.route('/api/news')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def news():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(news.text, file=sys.stderr)
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@app.route('/api/kingdoms')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdoms():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdoms',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    return (flask.jsonify(kd_info_parse["kingdoms"]), 200)

def _get_galaxy_info():
    galaxy_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxies',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    galaxy_info_parse = json.loads(galaxy_info.text)
    print(galaxy_info_parse, file=sys.stderr)
    return galaxy_info_parse["galaxies"]

@app.route('/api/galaxies')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxies():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    galaxy_info = _get_galaxy_info()
    return (flask.jsonify(galaxy_info), 200)

def _get_galaxies_inverted():
    galaxy_info = _get_galaxy_info()

    galaxies_inverted = {}
    for galaxy_name, kd_list in galaxy_info.items():
        for kd in kd_list:
            galaxies_inverted[kd] = galaxy_name
    return galaxies_inverted

@app.route('/api/galaxies_inverted')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxies_inverted():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    galaxies_inverted = _get_galaxies_inverted()
    return (flask.jsonify(galaxies_inverted), 200)

def _get_empire_info():
    empire_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    empire_info_parse = json.loads(empire_info.text)
    print(empire_info_parse, file=sys.stderr)
    return empire_info_parse["empires"]


def _get_empires_inverted():
    empire_info = _get_empire_info()
    galaxy_info = _get_galaxy_info()

    empires_inverted = {}
    for empire_id, empire_info in empire_info.items():
        for galaxy in empire_info["galaxies"]:
            galaxy_kds = galaxy_info[galaxy]
            for galaxy_kd in galaxy_kds:
                empires_inverted[galaxy_kd] = empire_id
    return empires_inverted

@app.route('/api/empires')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empires():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    empires = _get_empire_info()
    return (flask.jsonify(empires), 200)

@app.route('/api/empires_inverted')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empires_inverted():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    empires_inverted = _get_empires_inverted()
    return (flask.jsonify(empires_inverted), 200)



@app.route('/api/galaxynews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy_news():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    galaxies_inverted = _get_galaxies_inverted()
    galaxy = galaxies_inverted[kd_id]
    print(galaxy)
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy}/news',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(news.text, file=sys.stderr)
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@app.route('/api/empirenews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empire_news():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    empires_inverted = _get_empires_inverted()
    print(empires_inverted)
    kd_empire = empires_inverted[kd_id]
    print(kd_empire)
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/news',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(news.text, file=sys.stderr)
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@app.route('/api/universenews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def universe_news():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(news.text, file=sys.stderr)
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


def _validate_spending(spending_input):
    """Confirm that spending request is valid"""

    values = spending_input.values()
    if any((value < 0 for value in values)):
        return False
    if any((value > 100 for value in values)):
        return False
    if sum(values) > 100:
        return False
    
    return True


@app.route('/api/spending', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def spending():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    print(req, file=sys.stderr)
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    current_spending = kd_info_parse['auto_spending']
    new_spending = {
        'settle': float(req.get('settleInput', current_spending['settle'])),
        'structures': float(req.get('structuresInput', current_spending['structures'])),
        'military': float(req.get('militaryInput', current_spending['military'])),
        'engineers': float(req.get('engineersInput', current_spending['engineers'])),
    }
    valid_spending = _validate_spending(new_spending)
    if not valid_spending:
        return (flask.jsonify('Please enter valid spending percents'), 400)

    payload = {'auto_spending': new_spending}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-Azure-Functions-Host-Key': ''},
        data=json.dumps(payload),
    )
    return (flask.jsonify(patch_response.text), 200)

def _calc_units(
    start_time,
    current_units,
    generals_units,
    mobis_units,
):
    units = {
        "current": {k: v for k, v in current_units.items() if k in UNITS.keys()}
    }
    for i_general, general in enumerate(generals_units):
        units[f"general_{i_general}"] = general

    for hours in [1, 2, 4, 8, 24]:
        hour_units = {
            key: 0
            for key in UNITS.keys()
        }
        max_time = start_time + datetime.timedelta(hours=hours)
        for mobi in mobis_units:
            print(mobi)
            print(type(mobi))
            print(mobi.keys())
            if datetime.datetime.fromisoformat(mobi["time"]) < max_time:
                for key_unit in hour_units.keys():
                    hour_units[key_unit] += mobi.get(key_unit, 0)

        units[f"hour_{hours}"] = hour_units
    return units

def _calc_maxes(
    units,
):
    maxes = {}
    # maxes["defense"] = {
    #     type_max: {
    #         key: stat_map["defense"] * type_units.get(key, 0)
    #         for key, stat_map in UNITS.items() 
    #     }
    #     for type_max, type_units in units.items() 
    # }
    maxes["defense"] = {
        type_max: sum([
            stat_map["defense"] * type_units.get(key, 0)
            for key, stat_map in UNITS.items() 
        ])
        for type_max, type_units in units.items() 
    }
    # maxes["offense"] = {
    #     type_max: {
    #         key: stat_map["offense"] * type_units.get(key, 0)
    #         for key, stat_map in UNITS.items() 
    #     }
    #     for type_max, type_units in units.items() 
    # }
    maxes["offense"] = {
        type_max: sum([
            stat_map["offense"] * type_units.get(key, 0)
            for key, stat_map in UNITS.items() 
        ])
        for type_max, type_units in units.items() 
    }
    return maxes

@app.route('/api/mobis', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def mobis():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    mobis_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(mobis_info.text, file=sys.stderr)
    mobis_info_parse = json.loads(mobis_info.text)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse["mobis"]

    start_time = datetime.datetime.now()
    units = _calc_units(start_time, current_units, generals_units, mobis_units)
    maxes = _calc_maxes(units)

    payload = {'units': units, 'maxes': maxes}
    return (flask.jsonify(payload), 200)

def _calc_structures(
    start_time,
    current_structures,
    building_structures,
):
    structures = {
        "current": {k: current_structures.get(k, 0) for k in STRUCTURES}
    }

    for hours in [1, 2, 4, 8, 24]:
        hour_structures = {
            key: 0
            for key in STRUCTURES
        }
        max_time = start_time + datetime.timedelta(hours=hours)
        for building_structure in building_structures:
            if datetime.datetime.fromisoformat(building_structure["time"]) < max_time:
                for key_structure in hour_structures.keys():
                    hour_structures[key_structure] += building_structure.get(key_structure, 0)

        structures[f"hour_{hours}"] = hour_structures
    return structures

@app.route('/api/structures', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def structures():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(structures_info.text, file=sys.stderr)
    structures_info_parse = json.loads(structures_info.text)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-Azure-Functions-Host-Key': ''}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    current_structures = kd_info_parse["structures"]
    building_structures = structures_info_parse["structures"]

    start_time = datetime.datetime.now()
    structures = _calc_structures(start_time, current_structures, building_structures)

    return (flask.jsonify(structures), 200)

@app.route('/api/galaxy/<galaxy>', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy(galaxy):
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    galaxy_info = _get_galaxy_info()
    current_galaxy = galaxy_info[galaxy]
    galaxy_kd_info = {}
    for kd_id in current_galaxy:
        kd_info = REQUESTS_SESSION.get(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-Azure-Functions-Host-Key': ''}
        )
        print(kd_info.text, file=sys.stderr)
        galaxy_kd_info[kd_id] = json.loads(kd_info.text)

    return (flask.jsonify(galaxy_kd_info), 200)


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