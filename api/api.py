import datetime
import math
import os
import random
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
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'defense': {
        'offense': 0,
        'defense': 5,
        'cost': 350,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'flex': {
        'offense': 6,
        'defense': 6,
        'cost': 900,
        'fuel': 2,
        'hangar_capacity': 2,
    },
    'big_flex': {
        'offense': 9,
        'defense': 9,
        'cost': 1350,
        'fuel': 2,
        'hangar_capacity': 2,
    },
    'recruits': {
        'offense': 0,
        'defense': 1,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'engineers': {
        'offense': 0,
        'defense': 0,
        'fuel': 1,
        'hangar_capacity': 0,
    }
}

STRUCTURES = [
    "homes",
    "mines",
    "fuel_plants",
    "hangars",
    "drone_factories",
    "missile_silos",
    "workshops",
]

MISSILES = {
    "planet_busters": {
        "stars_damage": 1,
        "fuel_damage": 0,
        "pop_damage": 0,
        "fuel_cost": 1000,
        "cost": 2000,
    },
    "star_busters": {
        "stars_damage": 2,
        "fuel_damage": 500,
        "pop_damage": 0,
        "fuel_cost": 2000,
        "cost": 6000,
    },
    "galaxy_busters": {
        "stars_damage": 4,
        "fuel_damage": 1000,
        "pop_damage": 100,
        "fuel_cost": 4000,
        "cost": 15000,
    },
}

PROJECTS = {
    "pop_bonus": {
        "max_points": lambda stars: math.floor((stars ** 1.5) / 10),
        "max_bonus": 0.25
    },
    "fuel_bonus": {
        "max_points": lambda stars: math.floor((stars ** 1.5) / 10),
        "max_bonus": 0.25
    },
    "military_bonus": {
        "max_points": lambda stars: math.floor((stars ** 1.5) / 10),
        "max_bonus": 0.25
    },
    "money_bonus": {
        "max_points": lambda stars: math.floor((stars ** 1.5) / 10),
        "max_bonus": 0.25
    },
    "general_bonus": {
        "max_points": lambda stars: math.floor((stars ** 1.5) / 10),
        "max_bonus": 0.25
    },
    "spy_bonus": {
        "max_points": lambda stars: math.floor((stars ** 1.5) / 10),
        "max_bonus": 0.25
    },
    "big_flexers": {
        "max_points": lambda stars: 100000
    },
    "star_busters": {
        "max_points": lambda stars: 100000
    },
    "galaxy_busters": {
        "max_points": lambda stars: 250000
    },
    "drone_gadgets": {
        "max_points": lambda stars: 50000
    },
}

BASE_EPOCH_SECONDS = 60 * 60

BASE_SETTLE_COST = lambda stars: math.floor((stars ** 0.5) * 50)
BASE_MAX_SETTLE = lambda stars: math.floor(stars * 0.15)
BASE_SETTLE_TIME_MULTIPLIER = 12

BASE_STRUCTURE_COST = lambda stars: math.floor((stars ** 0.5) * 60)
BASE_STRUCTURE_TIME_MULTIPLIER = 8

BASE_MAX_RECRUITS = lambda pop: math.floor(pop * 0.12)
BASE_RECRUIT_COST = 100
BASE_RECRUIT_TIME_MULTIPLIER = 12

BASE_SPECIALIST_TIME_MULTIPLIER = 12

BASE_ENGINEER_COST = 1000
BASE_ENGINEER_TIME_MULTIPLIER = 12
BASE_MAX_ENGINEERS = lambda pop: math.floor(pop * 0.05)

BASE_HOMES_CAPACITY = 50
BASE_HANGAR_CAPACITY = 75
BASE_MISSILE_SILO_CAPACITY = 1
BASE_WORKSHOP_CAPACITY = 50

BASE_MISSILE_TIME_MULTIPLER = 24

BASE_REVEAL_DURATION_MULTIPLIER = 8

BASE_GENERALS_BONUS = lambda generals: (generals - 1) * 0.03
BASE_GENERALS_RETURN_TIME_MULTIPLIER = 8
BASE_DEFENDER_UNIT_LOSS_RATE = 0.05
BASE_ATTACKER_UNIT_LOSS_RATE = 0.05
BASE_KINGDOM_LOSS_RATE = 0.10

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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(news.text, file=sys.stderr)
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)

def _get_kingdoms():
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdoms',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    return kd_info_parse["kingdoms"]

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
    kingdoms = _get_kingdoms()
    return (flask.jsonify(kingdoms), 200)

def _get_galaxy_info():
    galaxy_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxies',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
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
    return galaxies_inverted, galaxy_info

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
    galaxies_inverted, _ = _get_galaxies_inverted()
    return (flask.jsonify(galaxies_inverted), 200)

def _get_empire_info():
    empire_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    empire_info_parse = json.loads(empire_info.text)
    print(empire_info_parse, file=sys.stderr)
    return empire_info_parse["empires"]


def _get_empires_inverted():
    empire_infos = _get_empire_info()
    galaxy_info = _get_galaxy_info()

    galaxy_empires = {}
    empires_inverted = {}
    for empire_id, empire_info in empire_infos.items():
        for galaxy in empire_info["galaxies"]:
            galaxy_empires[galaxy] = empire_id
            galaxy_kds = galaxy_info[galaxy]
            for galaxy_kd in galaxy_kds:
                empires_inverted[galaxy_kd] = empire_id
    return empires_inverted, empire_infos, galaxy_empires, galaxy_info

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
    empires_inverted, _, galaxy_empires, _ = _get_empires_inverted()
    payload = {
        "empires_inverted": empires_inverted,
        "galaxy_empires": galaxy_empires
    }
    return (flask.jsonify(payload), 200)



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
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy = galaxies_inverted[kd_id]
    print(galaxy)
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
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
    empires_inverted, _, _, _ = _get_empires_inverted()
    print(empires_inverted)
    kd_empire = empires_inverted[kd_id]
    print(kd_empire)
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(news.text, file=sys.stderr)
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)



@app.route('/api/attackhistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def attack_history():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(history.text, file=sys.stderr)
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["attack_history"]), 200)


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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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

    current_total = {
        key: 0
        for key in UNITS.keys()
    }
    for dict_units in units.values():
        for key_unit in UNITS.keys():
            current_total[key_unit] += dict_units.get(key_unit, 0)

    units["current_total"] = current_total

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

def _calc_max_offense(
    unit_dict,
    military_bonus=0.25,
    other_bonuses=0.0,
    generals=4,
):

    raw_attack = sum([
        stat_map["offense"] * unit_dict.get(key, 0)
        for key, stat_map in UNITS.items() 
    ])
    attack_w_bonuses = raw_attack * (1 + BASE_GENERALS_BONUS(generals) + military_bonus + other_bonuses)
    return math.floor(attack_w_bonuses)

def _calc_max_defense(
    unit_dict,
    military_bonus=0.25,
    other_bonuses=0.0,
    shields=0.10,
):

    raw_defense = sum([
        stat_map["defense"] * unit_dict.get(key, 0)
        for key, stat_map in UNITS.items() 
    ])
    defense_w_bonuses = raw_defense * (1 + shields + military_bonus + other_bonuses)
    return math.floor(defense_w_bonuses)

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
        type_max: _calc_max_defense(type_units)
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
        type_max: _calc_max_offense(type_units)
        for type_max, type_units in units.items() 
    }
    return maxes

def _calc_hangar_capacity(kd_info, units):
    max_hangar_capacity = kd_info["structures"]["hangars"] * BASE_HANGAR_CAPACITY
    current_hangar_capacity = sum([
        stat_map["hangar_capacity"] * (units["current_total"].get(key, 0) + units["hour_24"].get(key, 0))
        for key, stat_map in UNITS.items()
    ])
    return max_hangar_capacity, current_hangar_capacity

def _calc_max_recruits(kd_info, units):
    recruits_training = units["hour_24"]["recruits"]
    max_total_recruits = BASE_MAX_RECRUITS(int(kd_info["population"]))
    max_available_recruits = max(max_total_recruits - recruits_training, 0)
    max_recruits_cost = BASE_RECRUIT_COST * max_available_recruits
    try:
        current_available_recruits = min(
            math.floor((kd_info["money"] / max_recruits_cost) * max_available_recruits),
            max_available_recruits,
        )
    except ZeroDivisionError:
        current_available_recruits = 0
    return max_available_recruits, current_available_recruits

def _get_mobis_info(kd_id):
    mobis_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(mobis_info.text, file=sys.stderr)
    mobis_info_parse = json.loads(mobis_info.text)
    return mobis_info_parse["mobis"]

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

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    mobis_info_parse = _get_mobis_info(kd_id)
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse

    start_time = datetime.datetime.now()
    units = _calc_units(start_time, current_units, generals_units, mobis_units)
    maxes = _calc_maxes(units)

    max_hangar_capacity, current_hangar_capacity = _calc_hangar_capacity(kd_info_parse, units)
    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units)
    payload = {
        'units': units,
        'maxes': maxes,
        'recruit_price': BASE_RECRUIT_COST,
        'max_hangar_capacity': max_hangar_capacity,
        'current_hangar_capacity': current_hangar_capacity,
        'max_available_recruits': max_available_recruits,
        'current_available_recruits': current_available_recruits,
        'units_desc': UNITS,
        }
    return (flask.jsonify(payload), 200)

def _validate_recruits(recruits_input, current_available_recruits):
    if recruits_input > current_available_recruits:
        return False
    if recruits_input <= 0:
        return False

    return True

@app.route('/api/recruits', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def recruits():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    print(req, file=sys.stderr)
    recruits_input = int(req["recruitsInput"])
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    mobis_info_parse = _get_mobis_info(kd_id)
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse

    start_time = datetime.datetime.now()
    units = _calc_units(start_time, current_units, generals_units, mobis_units)

    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units)
    valid_recruits = _validate_recruits(recruits_input, current_available_recruits)
    if not valid_recruits:
        return (flask.jsonify('Please enter valid recruits value'), 400)

    new_money = kd_info_parse["money"] - BASE_RECRUIT_COST * recruits_input
    kd_payload = {'money': new_money}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    recruits_payload = {
        "mobis": [
            {
                "time": (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_RECRUIT_TIME_MULTIPLIER)).isoformat(),
                "recruits": recruits_input,
            }
        ]
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(recruits_payload),
    )
    return (flask.jsonify(kd_patch_response.text), 200)

def _get_mobis_cost(mobis_request):
    mobis_cost = sum([
        UNITS[k]['cost'] * units_value
        for k, units_value in mobis_request.items()
    ])
    return mobis_cost

def _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost):
    if sum(mobis_request.values()) > current_units["recruits"]:
        return False
    if any((value < 0 for value in mobis_request.values())):
        return False
    if mobis_cost > kd_info_parse["money"]:
        return False
    
    return True
    

@app.route('/api/mobis', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def train_mobis():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    current_units = kd_info_parse["units"]

    mobis_request = {
        k: int(v or 0)
        for k, v in req.items()
    }
    mobis_cost = _get_mobis_cost(mobis_request)
    valid_mobis = _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost)
    if not valid_mobis:
        return (flask.jsonify('Please enter valid training values'), 400)

    new_money = kd_info_parse["money"] - mobis_cost
    new_recruits = kd_info_parse["units"]["recruits"] - sum(mobis_request.values())
    kd_payload = {
        'money': new_money,
        'units': {
            **kd_info_parse["units"],
            'recruits': new_recruits,
        }
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    mobis_payload = {
        "mobis": [
            {
                "time": (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SPECIALIST_TIME_MULTIPLIER)).isoformat(),
                **mobis_request,
            }
        ]
    }
    mobis_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(mobis_payload),
    )
    return (flask.jsonify(mobis_patch_response.text), 200)

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

def _get_structure_price(kd_info):
    return BASE_SETTLE_COST(int(kd_info["stars"]))

def _calc_available_structures(structure_price, kd_info, structures_info):
    total_structures = sum(structures_info["current"].values()) + sum(structures_info["hour_24"].values())
    max_available_structures = max(int(kd_info["stars"]) - total_structures, 0)
    max_structures_cost = structure_price * max_available_structures
    try:
        current_available_structures = min(
            math.floor((kd_info["money"] / max_structures_cost) * max_available_structures),
            max_available_structures,
        )
    except ZeroDivisionError:
        current_available_structures
    return max_available_structures, current_available_structures


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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(structures_info.text, file=sys.stderr)
    structures_info_parse = json.loads(structures_info.text)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    current_price = _get_structure_price(kd_info_parse)
    current_structures = kd_info_parse["structures"]
    building_structures = structures_info_parse["structures"]

    start_time = datetime.datetime.now()
    structures = _calc_structures(start_time, current_structures, building_structures)

    max_available_structures, current_available_structures = _calc_available_structures(current_price, kd_info_parse, structures)

    payload = {
        **structures,
        "price": current_price,
        "max_available_structures": max_available_structures,
        "current_available_structures": current_available_structures,
    }

    return (flask.jsonify(payload), 200)

def _validate_structures(structures_input, current_available_structures):
    """Confirm that spending request is valid"""

    values = structures_input.values()
    if any((value < 0 for value in values)):
        return False
    if sum(values) > current_available_structures:
        return False
    if sum(values) == 0:
        return False
    
    return True

@app.route('/api/structures', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def build_structures():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(structures_info.text, file=sys.stderr)
    structures_info_parse = json.loads(structures_info.text)

    current_price = _get_structure_price(kd_info_parse)
    current_structures = kd_info_parse["structures"]
    building_structures = structures_info_parse["structures"]

    start_time = datetime.datetime.now()
    structures = _calc_structures(start_time, current_structures, building_structures)

    max_available_structures, current_available_structures = _calc_available_structures(current_price, kd_info_parse, structures)

    structures_request = {
        k: int(v or 0)
        for k, v in req.items()
    }
    valid_structures = _validate_structures(structures_request, current_available_structures)
    if not valid_structures:
        return (flask.jsonify('Please enter valid structures values'), 400)

    new_money = kd_info_parse["money"] - sum(structures_request.values()) * current_price
    kd_payload = {'money': new_money}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    structures_payload = {
        "structures": [
            {
                "time": (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_STRUCTURE_TIME_MULTIPLIER)).isoformat(),
                **structures_request,
            }
        ]
    }
    structures_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(structures_payload),
    )
    return (flask.jsonify(structures_patch_response.text), 200)

def _get_max_kd_info(kd_id, revealed_info, max=False):
    always_allowed_keys = {"name", "race"}
    allowed_keys = {
        "stats": ["stars", "score"],
        "kingdom": ["stars", "fuel", "population", "score", "money", "spy_attempts", "auto_spending", "missiles"],
        "military": ["units", "generals_available", "generals_out"],
        "structures": ["structures"],
        "shields": ["shields"],
        "projects": ["projects_points", "projects_max_points", "projects_assigned", "completed_projects"],
    }
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    if max:
        return kd_info_parse
    
    revealed_categories = revealed_info.get(kd_id, {}).keys()
    kingdom_info_keys = always_allowed_keys
    for revealed_category in revealed_categories:
        kingdom_info_keys = kingdom_info_keys.union(allowed_keys[revealed_category])

    kd_info_parse_allowed = {
        k: v
        for k, v in kd_info_parse.items()
        if k in kingdom_info_keys
    }
    if "projects_points" in kd_info_parse_allowed:
        kd_info_parse_allowed["max_bonuses"] = {
            project: project_dict.get("max_bonus", 0)
            for project, project_dict in PROJECTS.items()
            if "max_bonus" in project_dict
        }
        kd_info_parse_allowed["current_bonuses"] = {
            project: project_dict.get("max_bonus", 0) * kd_info_parse_allowed["projects_points"][project] / kd_info_parse_allowed["projects_max_points"][project]
            for project, project_dict in PROJECTS.items()
            if "max_bonus" in project_dict
        }
    return kd_info_parse_allowed


@app.route('/api/kingdom/<other_kd_id>', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def max_kingdom(other_kd_id):
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)

    revealed_info = _get_revealed(kd_id)["revealed"]
    max_kd_info = _get_max_kd_info(other_kd_id, revealed_info)

    return (flask.jsonify(max_kd_info), 200)


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
    revealed_info = _get_revealed(kd_id)["revealed"]
    galaxy_kd_info = {}
    for galaxy_kd_id in current_galaxy:
        kd_info = _get_max_kd_info(galaxy_kd_id, revealed_info)
        galaxy_kd_info[galaxy_kd_id] = kd_info
    
    print(galaxy_kd_info)

    return (flask.jsonify(galaxy_kd_info), 200)

def _get_settle_info(kd_id):
    settle_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(settle_info.text, file=sys.stderr)
    settle_info_parse = json.loads(settle_info.text)
    return settle_info_parse["settles"]

def _get_settle_price(kd_info):
    return BASE_SETTLE_COST(int(kd_info["stars"]))

def _get_available_settle(kd_info, settle_info):
    max_settle = BASE_MAX_SETTLE(int(kd_info["stars"]))
    current_settle = sum([
        int(settle_item["amount"])
        for settle_item in settle_info
    ])
    max_available_settle = max(max_settle - current_settle, 0)
    current_settle_cost = _get_settle_price(kd_info)
    max_settle_cost = current_settle_cost * max_available_settle
    try:
        current_available_settle = min(
            math.floor((kd_info["money"] / max_settle_cost) * max_available_settle),
            max_available_settle,
        )
    except ZeroDivisionError:
        current_available_settle = 0
    return max_available_settle, current_available_settle

@app.route('/api/settle', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def get_settle():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    settle_info = _get_settle_info(kd_id)

    settle_price = _get_settle_price(kd_info_parse)
    max_settle, available_settle = _get_available_settle(kd_info_parse, settle_info)

    payload = {
        "settle_price": settle_price,
        "max_available_settle": max_settle,
        "current_available_settle": available_settle,
    }

    return (flask.jsonify(payload), 200)

def _validate_settles(settle_input, kd_info, settle_info):
    max_settle, available_settle = _get_available_settle(kd_info, settle_info)
    if settle_input > available_settle:
        return False

    return True


@app.route('/api/settle', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def settle():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    print(req, file=sys.stderr)
    settle_input = int(req["settleInput"])
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    settle_info = _get_settle_info(kd_id)
    valid_settle = _validate_settles(settle_input, kd_info_parse, settle_info)
    if not valid_settle:
        return (flask.jsonify('Please enter valid settle value'), 400)

    settle_price = _get_settle_price(kd_info_parse)
    new_money = kd_info_parse["money"] - settle_price * settle_input
    kd_payload = {'money': new_money}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    settle_payload = {
        "settles": [
            {
                "time": (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SETTLE_TIME_MULTIPLIER)).isoformat(),
                "amount": settle_input,
            }
        ]
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(settle_payload),
    )
    return (flask.jsonify(kd_patch_response.text), 200)

def _get_missiles_info(kd_id):
    missiles_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(missiles_info.text, file=sys.stderr)
    missiles_info_parse = json.loads(missiles_info.text)
    return missiles_info_parse["missiles"]

def _get_missiles_building(missiles_info):
    missiles_building = {
        k: 0
        for k in MISSILES
    }
    for missile_queue in missiles_info:
        missile_queue.pop("time")
        for key_missile, amt_missile in missile_queue.items():
            missiles_building[key_missile] += amt_missile
    return missiles_building


@app.route('/api/missiles', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def missiles():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    missiles_info = _get_missiles_info(kd_id)
    missiles_building = _get_missiles_building(missiles_info)

    current_missiles = kd_info_parse["missiles"]

    payload = {
        "current": current_missiles,
        "building": missiles_building,
        "build_time": BASE_MISSILE_TIME_MULTIPLER * BASE_EPOCH_SECONDS,
        "capacity": kd_info_parse["structures"]["missile_silos"] * BASE_MISSILE_SILO_CAPACITY,
        "desc": MISSILES,
    }

    return (flask.jsonify(payload), 200)

def _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles):
    current_missiles = kd_info_parse["missiles"]
    missiles = {k: current_missiles.get(k, 0) + missiles_building.get(k, 0) for k in MISSILES}

    missiles_available = {k: max_available_missiles - missiles.get(k, 0) for k in missiles}
    costs = sum([MISSILES[key_missile]["cost"] * value_missile for key_missile, value_missile in missiles_request.items()])
    fuel_costs = sum([MISSILES[key_missile]["fuel_cost"] * value_missile for key_missile, value_missile in missiles_request.items()])

    if any((value < 0 for value in missiles_request.values())):
        return False
    if any((value_missile > missiles_available.get(key_missile, 0) for key_missile, value_missile in missiles_request.items())):
        return False
    if sum(missiles_request.values()) == 0:
        return False
    if costs > kd_info_parse["money"]:
        return False
    if fuel_costs > kd_info_parse["fuel"]:
        return False
    
    return True


@app.route('/api/missiles', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def build_missiles():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    
    missiles_info = _get_missiles_info(kd_id)
    missiles_building = _get_missiles_building(missiles_info)

    max_available_missiles = kd_info_parse["structures"]["missile_silos"] * BASE_MISSILE_SILO_CAPACITY

    missiles_request = {
        k: int(v or 0)
        for k, v in req.items()
    }
    valid_missiles = _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles)
    if not valid_missiles:
        return (flask.jsonify('Please enter valid missiles values'), 400)

    costs = sum([MISSILES[key_missile]["cost"] * value_missile for key_missile, value_missile in missiles_request.items()])
    fuel_costs = sum([MISSILES[key_missile]["fuel_cost"] * value_missile for key_missile, value_missile in missiles_request.items()])
    new_money = kd_info_parse["money"] - costs
    new_fuel = kd_info_parse["fuel"] - fuel_costs
    kd_payload = {
        'money': new_money,
        'fuel': new_fuel,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    missiles_payload = {
        "missiles": [
            {
                "time": (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_MISSILE_TIME_MULTIPLER)).isoformat(),
                **missiles_request,
            }
        ]
    }
    missiles_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(missiles_payload),
    )
    return (flask.jsonify(missiles_patch_response.text), 200)

def _calc_workshop_capacity(kd_info, engineers_building):
    max_workshop_capacity = kd_info["structures"]["workshops"] * BASE_WORKSHOP_CAPACITY
    current_engineers = kd_info["units"]["engineers"]
    current_workshop_capacity = current_engineers + engineers_building
    return max_workshop_capacity, current_workshop_capacity

def _calc_max_engineers(kd_info, engineers_building, max_workshop_capacity):
    engineers_total = kd_info["units"]["engineers"] + engineers_building
    available_workshop_capacity = max(max_workshop_capacity - engineers_total, 0)
    max_trainable_engineers = BASE_MAX_ENGINEERS(int(kd_info["population"]))
    max_available_engineers = min(available_workshop_capacity, max_trainable_engineers)
    try:
        current_available_engineers = min(
            math.floor(kd_info["money"] / BASE_ENGINEER_COST),
            max_available_engineers,
        )
    except ZeroDivisionError:
        current_available_engineers = 0
    return max_available_engineers, current_available_engineers

def _get_engineers_info(kd_id):
    engineers_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(engineers_info.text, file=sys.stderr)
    engineers_info_parse = json.loads(engineers_info.text)
    return engineers_info_parse["engineers"]

@app.route('/api/engineers', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def engineers():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    engineers_info = _get_engineers_info(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = _calc_workshop_capacity(kd_info_parse, engineers_building)
    max_available_engineers, current_available_engineers = _calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity)

    payload = {
        'engineers_price': BASE_ENGINEER_COST,
        'max_workshop_capacity': max_workshop_capacity,
        'current_workshop_capacity': current_workshop_capacity,
        'max_available_engineers': max_available_engineers,
        'current_available_engineers': current_available_engineers,
        'current_engineers': kd_info_parse["units"]["engineers"],
        'engineers_building': engineers_building,
        }
    return (flask.jsonify(payload), 200)

def _validate_engineers(engineers_input, current_available_engineers):
    if engineers_input > current_available_engineers:
        return False
    if engineers_input <= 0:
        return False

    return True

@app.route('/api/engineers', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def train_engineers():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    print(req, file=sys.stderr)
    engineers_input = int(req["engineersInput"])
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    engineers_info = _get_engineers_info(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = _calc_workshop_capacity(kd_info_parse, engineers_building)
    max_available_engineers, current_available_engineers = _calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity)

    valid_engineers = _validate_engineers(engineers_input, current_available_engineers)
    if not valid_engineers:
        return (flask.jsonify('Please enter valid recruits value'), 400)

    new_money = kd_info_parse["money"] - BASE_ENGINEER_COST * engineers_input
    kd_payload = {'money': new_money}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    engineers_payload = {
        "engineers": [
            {
                "time": (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_ENGINEER_TIME_MULTIPLIER)).isoformat(),
                "amount": engineers_input,
            }
        ]
    }
    engineers_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(engineers_payload),
    )
    return (flask.jsonify(engineers_patch_response.text), 200)

@app.route('/api/projects', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def projects():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    max_bonuses = {
        project: project_dict.get("max_bonus", 0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project]
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }
    available_engineers = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())

    payload = {
        "current_bonuses": current_bonuses,
        "max_bonuses": max_bonuses,
        "available_engineers": available_engineers,
    }
    return (flask.jsonify(payload), 200)

def _validate_assign_projects(req, kd_info_parse):
    engineers_assigned = sum(req["assign"].values())
    if engineers_assigned > kd_info_parse["units"]["engineers"]:
        return False
    if any(value < 0 for value in req["assign"].values()):
        return False
    return True

def _validate_add_projects(req, available_engineers):
    engineers_added = sum(req["add"].values())
    if engineers_added > available_engineers:
        return False
    if any(value < 0 for value in req["add"].values()):
        return False
    return True

@app.route('/api/projects', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def manage_projects():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    new_projects_assigned = kd_info_parse["projects_assigned"].copy()
    if "clear" in req.keys():
        projects_to_clear = req["clear"]
        for project_to_clear in projects_to_clear:
            new_projects_assigned[project_to_clear] = 0

    elif "assign" in req.keys():
        req["assign"] = {k: int(v) for k, v in req["assign"].items()}
        valid_assign = _validate_assign_projects(req, kd_info_parse)
        if not valid_assign:
            return (flask.jsonify('Please enter valid assign engineers value'), 400)
        
        new_projects_assigned = {
            key: req["assign"].get(key, 0)
            for key in kd_info_parse["projects_assigned"]
        }
        
    elif "add" in req.keys():
        req["add"] = {k: int(v) for k, v in req["add"].items()}
        available_engineers = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())
        valid_add = _validate_add_projects(req, available_engineers)
        if not valid_add:
            return (flask.jsonify('Please enter valid add engineers value'), 400)
        
        new_projects_assigned = {
            key: value + req["add"].get(key, 0)
            for key, value in kd_info_parse["projects_assigned"].items()
        }

    kd_payload = {"projects_assigned": new_projects_assigned}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    return (flask.jsonify(kd_patch_response.text), 200)

def _get_revealed(kd_id):
    revealed_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(revealed_info.text, file=sys.stderr)
    revealed_info_parse = json.loads(revealed_info.text)
    return revealed_info_parse

@app.route('/api/revealed', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def revealed():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    revealed_info = _get_revealed(kd_id)
    return (flask.jsonify(revealed_info), 200)

def _get_shared(kd_id):
    shared_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(shared_info.text, file=sys.stderr)
    shared_info_parse = json.loads(shared_info.text)
    return shared_info_parse

@app.route('/api/shared', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def shared():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    shared_info = _get_shared(kd_id)
    return (flask.jsonify(shared_info), 200)

@app.route('/api/shared', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def accept_shared():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    accepted_kd = str(req["shared"])
    print(accepted_kd)

    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    shared_info = _get_shared(kd_id)

    new_shared = shared_info["shared_requests"].pop(accepted_kd)
    shared_info["shared"][accepted_kd] = new_shared

    shared_info_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(shared_info),
    )

    return (flask.jsonify(shared_info_response.text), 200)

def _get_pinned(kd_id):
    pinned_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(pinned_info.text, file=sys.stderr)
    pinned_info_parse = json.loads(pinned_info.text)
    return pinned_info_parse

@app.route('/api/pinned', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def pinned():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    pinned_info = _get_pinned(kd_id)
    return (flask.jsonify(pinned_info["pinned"]), 200)

@app.route('/api/pinned', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def update_pinned():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    print(req)
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    
    pinned_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(req),
    )
    return (flask.jsonify(pinned_patch_response.text), 200)


@app.route('/api/kingdomsinfo', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def max_kingdoms():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    kingdoms = req["kingdoms"]

    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    revealed_info = _get_revealed(kd_id)["revealed"]

    payload = {
        kd_id: _get_max_kd_info(kd_id, revealed_info)
        for kd_id in kingdoms
    }
    return (flask.jsonify(payload), 200)

@app.route('/api/revealrandomgalaxy', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def reveal_random_galaxy():
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
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    if kd_info_parse["spy_attempts"] <= 0:
        return (flask.jsonify('You do not have any spy attempts remaining'), 400)

    revealed_info = _get_revealed(kd_id)

    empires_inverted, empires, _, _ = _get_empires_inverted()
    galaxies_inverted, galaxy_info = _get_galaxies_inverted()

    kd_empire = empires_inverted.get(kd_id, None)
    kd_galaxy = galaxies_inverted[kd_id]

    print(empires)
    print(kd_empire)
    excluded_galaxies = list(revealed_info["galaxies"].keys())
    print(excluded_galaxies)
    if kd_empire:
        print(empires[kd_empire])
        excluded_galaxies.extend(empires[kd_empire]["galaxies"])
    else:
        excluded_galaxies.extend(kd_galaxy)

    potential_galaxies = set(galaxy_info.keys()) - set(excluded_galaxies)

    if not len(potential_galaxies):
        return (flask.jsonify('There are no more galaxies to reveal'), 400)

    galaxy_to_reveal = random.choice(list(potential_galaxies))

    time = (datetime.datetime.now() + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_REVEAL_DURATION_MULTIPLIER)).isoformat()
    payload = {
        "galaxies": {
            galaxy_to_reveal: time
        }
    }

    payload["revealed"] = {
        kd_id: {
            "stats": time,
        }
        for kd_id in galaxy_info[galaxy_to_reveal]
    }

    reveal_galaxy_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )

    kd_payload = {"spy_attempts": kd_info_parse["spy_attempts"] - 1}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )


    return (flask.jsonify(reveal_galaxy_response.text), 200)

def _validate_attack_request(
    attacker_raw_values,
    kd_info
):
    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in UNITS and value != "")
    }
    if any((
        attack_units > kd_info["units"].get(key_unit, 0)
        for key_unit, attack_units in attacker_units.items()
    )):
        return False, "You do not have that many units"
    if any((
        attack_units < 0
        for attack_units in attacker_units.values()
    )):
        return False, "You can not send negative units"
    if sum(attacker_units.values()) == 0:
        return False, "You must send at least 1 unit"
    if int(attacker_raw_values["generals"] or 0) > kd_info["generals_available"]:
        return False, "You do not have that many generals"
    if int(attacker_raw_values["generals"] or 0) == 0:
        return False, "You must send at least 1 general"
    
    return True, ""

def _calc_losses(
    unit_dict,
    loss_rate,
):
    losses = {
        key_unit: math.floor(value_unit * loss_rate)
        for key_unit, value_unit in unit_dict.items()
    }
    return losses

def _calc_generals_return_time(
    generals,
    return_multiplier,
    base_time,
):
    return_times = [
        base_time + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * return_multiplier / i)
        for i in range(generals, 0, -1)
    ]
    return return_times

@app.route('/api/calculate/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def calculate_attack(target_kd):
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]
    defender_raw_values = req["defenderValues"]

    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project]
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }

    revealed = _get_revealed(kd_id)["revealed"]
    shared = _get_shared(kd_id)["shared"]
    max_target_kd_info = _get_max_kd_info(target_kd, revealed)

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return (flask.jsonify({"message": attack_request_message}), 400)

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in UNITS and value != "")
    }
    if "units" in max_target_kd_info:
        defender_units = max_target_kd_info["units"]
    else:
        defender_units = {
            key: int(value)
            for key, value in defender_raw_values.items()
            if (key in UNITS and value != "")
        }
    
    if "current_bonuses" in max_target_kd_info:
        defender_military_bonus = max_target_kd_info["current_bonuses"]["military_bonus"]
    else:
        defender_military_bonus = float(defender_raw_values['military_bonus'] or 0) / 100

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["military"]
    else:
        defender_shields = float(defender_raw_values['shields'] or 0) / 100
    attack = _calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
    )
    defense = _calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
    )
    attack_ratio = min(attack / defense, 1.0)
    attacker_losses = _calc_losses(
        attacker_units,
        BASE_ATTACKER_UNIT_LOSS_RATE,
    )
    defender_losses = _calc_losses(
        defender_units,
        BASE_DEFENDER_UNIT_LOSS_RATE * attack_ratio,
    )
    time_now = datetime.datetime.now()
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
    )
    generals_strftime = ', '.join([
        str(general_return_time - time_now)
        for general_return_time in generals_return_times
    ])
    if attack > defense:
        message = f"The attack will be a success!\n"
        message += f"Your general(s) will return in: {generals_strftime}. \n"
        if target_kd in shared:
            cut = shared[target_kd]["cut"]
            sharer = shared[target_kd]["shared_by"]
        else:
            cut = 0
            sharer = None
        spoils_values = {
            key_spoil: math.floor(value_spoil * BASE_KINGDOM_LOSS_RATE * (1 - cut))
            for key_spoil, value_spoil in max_target_kd_info.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        if spoils_values:
            message += 'You will gain '
            message += ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
            message += '. \n'
            if sharer:
                sharer_spoils_values = {
                    key_spoil: math.floor(value_spoil * BASE_KINGDOM_LOSS_RATE * cut)
                    for key_spoil, value_spoil in max_target_kd_info.items()
                    if key_spoil in {"stars", "population", "money", "fuel"}
                }
                kingdoms = _get_kingdoms()
                sharer_name = kingdoms[sharer]
                message += f'Your galaxymate {sharer_name} will gain '
                message += ', '.join([f"{value} {key}" for key, value in sharer_spoils_values.items()])
                message += ' for sharing intel. \n'

                
    else:
        message = f"The attack will fail.\n"
        message += f"Your general(s) will return in: {generals_strftime}\n"

    payload = {
        "defender_defense": defense,
        "attacker_offense": attack,
        "defender_losses": defender_losses,
        "attacker_losses": attacker_losses,
        "defender_unit_losses_rate": BASE_DEFENDER_UNIT_LOSS_RATE,
        "attacker_unit_losses_rate": BASE_ATTACKER_UNIT_LOSS_RATE,
        "defender_stars_loss_rate": BASE_KINGDOM_LOSS_RATE,
        "generals_return_times": generals_return_times,
        "message": message
    }

    return (flask.jsonify(payload), 200)

@app.route('/api/attack/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def attack(target_kd):
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    if target_kd == kd_id:
        return (flask.jsonify("You cannot attack yourself!"), 400)

    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project]
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }

    revealed = _get_revealed(kd_id)["revealed"]
    shared = _get_shared(kd_id)["shared"]
    target_kd_info = _get_max_kd_info(target_kd, revealed, max=True)
    target_current_bonuses = {
        project: project_dict.get("max_bonus", 0) * target_kd_info["projects_points"][project] / target_kd_info["projects_max_points"][project]
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return (flask.jsonify({"message": attack_request_message}), 400)

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in UNITS and value != "")
    }
    defender_units = {
        key: value
        for key, value in target_kd_info["units"].items()
        if UNITS[key].get("defense", 0) > 0
    }
    defender_military_bonus = target_current_bonuses['military_bonus']
    defender_shields = target_kd_info["shields"]["military"]

    attack = _calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
    )
    defense = _calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
    )
    attack_ratio = min(attack / defense, 1.0)
    attacker_losses = _calc_losses(
        attacker_units,
        BASE_ATTACKER_UNIT_LOSS_RATE,
    )
    defender_losses = _calc_losses(
        defender_units,
        BASE_DEFENDER_UNIT_LOSS_RATE * attack_ratio,
    )
    time_now = datetime.datetime.now()
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
    )
    new_home_attacker_units = {
        key_unit: value_unit - attacker_units.get(key_unit, 0)
        for key_unit, value_unit in kd_info_parse["units"].items()
    }
    remaining_attacker_units = {
        key_unit: value_unit - attacker_losses.get(key_unit, 0)
        for key_unit, value_unit in attacker_units.items()
    }
    generals = [
        {
            "return_time": general_time.isoformat(),
            **{
                key_unit: math.floor(remaining_unit / len(generals_return_times))
                for key_unit, remaining_unit in remaining_attacker_units.items()
            }
        }
        for general_time in generals_return_times
    ]
    new_defender_units = {
        key_unit: value_unit - defender_losses.get(key_unit, 0)
        for key_unit, value_unit in target_kd_info["units"].items()
    }
    if target_kd in shared:
        cut = shared[target_kd]["cut"]
        sharer = shared[target_kd]["shared_by"]
    else:
        cut = 0
        sharer = None
    if attack > defense:
        total_spoils = {
            key_spoil: math.floor(value_spoil * BASE_KINGDOM_LOSS_RATE)
            for key_spoil, value_spoil in target_kd_info.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        spoils_values = {
            key_spoil: math.floor(value_spoil * BASE_KINGDOM_LOSS_RATE * (1 - cut))
            for key_spoil, value_spoil in target_kd_info.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        if sharer:
            sharer_spoils_values = {
                key_spoil: math.floor(value_spoil * BASE_KINGDOM_LOSS_RATE * cut)
                for key_spoil, value_spoil in target_kd_info.items()
                if key_spoil in {"stars", "population", "money", "fuel"}
            }
            sharer_message = (
                "You have gained "
                + ', '.join([f"{value} {key}" for key, value in sharer_spoils_values.items()])
                + f" for sharing intel leading to a successful attack by your galaxymate {kd_info_parse['name']}"
            )
            sharer_news = {
                "time": time_now.isoformat(),
                "from": kd_id,
                "news": sharer_message,
            }
            sharer_news_patch_response = REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{sharer}/news',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps(sharer_news),
            )

        units_destroyed = sum(defender_losses.values())
        attack_status = "success"
        attacker_message = (
            "Success! You have gained "
            + ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
            + f" and destroyed {units_destroyed} units."
            + " You have lost "
            + ', '.join([f"{value} {key}" for key, value in attacker_losses.items()])
        )
        defender_message = (
            f"Your kingdom was defeated in battle by {kd_info_parse['name']}. You have lost "
            + ', '.join([f"{value} {key}" for key, value in total_spoils.items()])
            + ' and '
            + ', '.join([f"{value} {key}" for key, value in defender_losses.items()])
        )
    else:
        attack_status = "failure"
        attacker_message = "Failure! You have lost " + ', '.join([f"{value} {key}" for key, value in attacker_losses.items()])
        defender_message = (
            f"Your kingdom was successfully defended an attack by {kd_info_parse['name']}. You have lost "
            + ', '.join([f"{value} {key}" for key, value in defender_losses.items()])
        )
        spoils_values = {}
        sharer_spoils_values = {}

    kd_info_parse["units"] = new_home_attacker_units
    kd_info_parse["generals_out"] = kd_info_parse["generals_out"] + generals
    kd_info_parse["generals_available"] = kd_info_parse["generals_available"] - int(attacker_raw_values["generals"])

    target_kd_info["units"] = new_defender_units
    for key_spoil, value_spoil in spoils_values.items():
        kd_info_parse[key_spoil] += value_spoil
        target_kd_info[key_spoil] -= value_spoil

    for key_project, project_dict in PROJECTS.items():
        project_max_func = project_dict["max_points"]
        kd_info_parse["projects_max_points"][key_project] = project_max_func(kd_info_parse["stars"])
        target_kd_info["projects_max_points"][key_project] = project_max_func(target_kd_info["stars"])

    if sharer:
        sharer_kd_info = _get_max_kd_info(sharer, revealed, max=True)
        for key_spoil, value_spoil in sharer_spoils_values.items():
            sharer_kd_info[key_spoil] += value_spoil
            target_kd_info[key_spoil] -= value_spoil
        sharer_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{sharer}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(sharer_kd_info),
        )
    target_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_kd_info),
    )
    target_news = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "news": defender_message,
    }
    target_news_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_news),
    )
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_info_parse, default=str),
    )
    kd_attack_history = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "news": attacker_message,
    }
    kd_attack_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_attack_history, default=str),
    )

    attack_results = {
        "status": attack_status,
        "message": attacker_message,
    }
    return (flask.jsonify(attack_results), 200)
        

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