import collections
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
BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH = 1
BASE_MAX_ENGINEERS = lambda pop: math.floor(pop * 0.05)

BASE_HOMES_CAPACITY = 50
BASE_HANGAR_CAPACITY = 75
BASE_MISSILE_SILO_CAPACITY = 1
BASE_WORKSHOP_CAPACITY = 50
BASE_MINES_INCOME_PER_EPOCH = 150
BASE_FUEL_PLANTS_INCOME_PER_EPOCH = 200
BASE_FUEL_PLANTS_CAPACITY = 1000
BASE_DRONE_PLANTS_PRODUCTION_PER_EPOCH = 1

BASE_MISSILE_TIME_MULTIPLER = 24

BASE_GENERALS_BONUS = lambda generals: (generals - 1) * 0.03
BASE_GENERALS_RETURN_TIME_MULTIPLIER = 8
BASE_DEFENDER_UNIT_LOSS_RATE = 0.05
BASE_ATTACKER_UNIT_LOSS_RATE = 0.05
BASE_KINGDOM_LOSS_RATE = 0.10

BASE_STARS_DRONE_DEFENSE_MULTIPLIER = 4
BASE_DRONES_DRONE_DEFENSE_MULTIPLIER = 1
BASE_SPY_MIN_SUCCESS_CHANCE = 0.10
BASE_DRONES_SUCCESS_LOSS_RATE = 0.01
BASE_DRONES_FAILURE_LOSS_RATE = 0.02
BASE_DRONES_SHIELDING_LOSS_REDUCTION = 0.5
BASE_REVEAL_DURATION_MULTIPLIER = 8

BASE_POP_INCOME_PER_EPOCH = 2
BASE_POP_FUEL_CONSUMPTION_PER_EPOCH = 0.5

BASE_SPY_ATTEMPT_TIME_MULTIPLIER = 1
BASE_SPY_ATTEMPTS_MAX = 10

REVEAL_OPERATIONS = [
    "spykingdom",
    "spymilitary",
    "spyshields",
    "spyprojects",
    "spystructures",
    "spydrones",
]

INITIAL_KINGDOM_STARS = 300
INITIAL_KINGDOM_STATE = {
    "kingdom": {
        "kdId": "",
        "name": "",
        "race": "",
        "last_income": "",
        "next_resolve": {
            "generals": "2099-01-01T00:00:00+00:00",
            "spy_attempt": "2099-01-01T00:00:00+00:00",
            "settles": "2099-01-01T00:00:00+00:00",
            "mobis": "2099-01-01T00:00:00+00:00",
            "missiles": "2099-01-01T00:00:00+00:00",
            "engineers": "2099-01-01T00:00:00+00:00",
            "structures": "2099-01-01T00:00:00+00:00",
            "revealed": "2099-01-01T00:00:00+00:00",
            "shared": "2099-01-01T00:00:00+00:00",
        },
        "stars": INITIAL_KINGDOM_STARS,
        "fuel": 10000,
        "population": 2500,
        "score": 0,
        "money": 100000,
        "drones": 1000,
        "spy_attempts": 10,
        "generals_available": 4,
        "generals_out": [],
        "units": {
            "attack": 0,
            "defense": 0,
            "flex": 0,
            "recruits": 0,
            "engineers": 0,
            "big_flex": 0,
        },
        "structures": {
            "homes": 0,
            "mines": 0,
            "fuel_plants": 0,
            "hangars": 0,
            "drone_factories": 0,
            "missile_silos": 0,
            "workshops": 0,
        },
        "revealed_to": {},
        "auto_spending": {
            "settle": 0,
            "structures": 0,
            "military": 0,
            "engineers": 0
        },
        "projects_points": {
            "pop_bonus": 1000,
            "fuel_bonus": 1000,
            "military_bonus": 1000,
            "money_bonus": 1000,
            "general_bonus": 1000,
            "spy_bonus": 0,
            "big_flexers": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
            "drone_gadgets": 0
        },
        "projects_max_points": {
            "pop_bonus": PROJECTS["big_flexers"]["max_points"](INITIAL_KINGDOM_STARS),
            "fuel_bonus": PROJECTS["big_flexers"]["max_points"](INITIAL_KINGDOM_STARS),
            "military_bonus": PROJECTS["big_flexers"]["max_points"](INITIAL_KINGDOM_STARS),
            "money_bonus": PROJECTS["big_flexers"]["max_points"](INITIAL_KINGDOM_STARS),
            "general_bonus": PROJECTS["big_flexers"]["max_points"](INITIAL_KINGDOM_STARS),
            "spy_bonus": PROJECTS["big_flexers"]["max_points"](INITIAL_KINGDOM_STARS),
            "big_flexers": PROJECTS["big_flexers"]["max_points"](0),
            "star_busters": PROJECTS["star_busters"]["max_points"](0),
            "galaxy_busters": PROJECTS["galaxy_busters"]["max_points"](0),
            "drone_gadgets": PROJECTS["drone_gadgets"]["max_points"](0),
        },
        "projects_assigned": {
            "pop_bonus": 0,
            "fuel_bonus": 0,
            "military_bonus": 0,
            "money_bonus": 0,
            "general_bonus": 0,
            "spy_bonus": 0,
            "big_flexers": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
            "drone_gadgets": 0
        },
        "completed_projects": [],
        "missiles": {
            "planet_busters": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
        },
        "shields": {
            "military": 0.0,
            "spy": 0.0,
            "missiles": 0.0
        },
    },
    "news": {"news": []},
    "settles": {"settles": []},
    "mobis": {"mobis": []},
    "structures": {"structures": []},
    "missiles": {"missiles": []},
    "engineers": {"engineers": []},
    "revealed": {"revealed": {}, "galaxies": {}},
    "shared": {
        "shared": {},
        "shared_requests": {},
        "shared_offers": {},
    },
    "pinned": {"pinned": []},
    "spy_history": {"spy_history": []},
    "attack_history": {"attack_history": []},
    "missile_history": {"missile_history": []},
}

KINGDOM_CREATOR_STARTING_POINTS = 20000
KINGDOM_CREATOR_POINTS = {
    "drones": 1,
    "recruits": 1,
    "attack": 5,
    "defense": 5,
    "flex": 10,
    "engineers": 10,
}

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
          roles='operator,admin',
          kd_created=True,
		))
    if db.session.query(User).filter_by(username='user').count() < 1:
        db.session.add(User(
          username='user',
          password=guard.hash_password('pass'),
          roles='verified',
          kd_id="0",
          kd_created=True,
		))
    if db.session.query(User).filter_by(username='newkd').count() < 1:
        db.session.add(User(
          username='newkd',
          password=guard.hash_password('newkd'),
          roles='verified',
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

@app.route('/api/kingdomid')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdomid():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    kd_created = flask_praetorian.current_user().kd_created
    if kd_id == None:
        return flask.jsonify({"kd_id": "", "created": kd_created}), 200
    
    return flask.jsonify({"kd_id": kd_id, "created": kd_created}), 200

def _validate_kingdom_name(
    name,    
):
    kingdoms = _get_kingdoms()
    if any((name.lower() == existing_name.lower() for existing_name in kingdoms.values())):
        return False, "Kingdom name already exists"
    
    if len(name) > 24:
        return False, "Kingdom name must be less than 25 characters"
    
    if len(name) == 0:
        return False, "Kingdom name must have at least one character"
    
    return True, ""

@app.route('/api/createkingdom', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_initial_kingdom():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    user = flask_praetorian.current_user()

    if user.kd_id != "" and user.kd_id != None:
        return (flask.jsonify("You already have a kingdom ID"), 400)

    valid_name, message = _validate_kingdom_name(req["kdName"])
    if not valid_name:
        return (flask.jsonify(message), 400)
    
    galaxies = _get_galaxy_info()
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
        return (flask.jsonify("Error creating kingdom"), 400)
    
    kd_id = create_kd_response.text

    for table, initial_state in INITIAL_KINGDOM_STATE.items():
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
    
    return kd_id, 200

@app.route('/api/createkingdomdata')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom_data():
    """
    Return information to inform kingdom creator page
    """

    payload = {
        "total_points": KINGDOM_CREATOR_STARTING_POINTS,
        "selection_points": KINGDOM_CREATOR_POINTS,
        "total_stars": INITIAL_KINGDOM_STATE["kingdom"]["stars"],
    }
    return (flask.jsonify(payload), 200)

def _validate_kingdom_choices(
    unit_choices,
    structures_choices,    
):
    sum_units_points = sum([
        value_unit * KINGDOM_CREATOR_POINTS[key_unit]
        for key_unit, value_unit in unit_choices.items()
    ])
    sum_structures = sum(structures_choices.values())
    if any((value_unit < 0 for value_unit in unit_choices.values())):
        return False, "Unit values must be non-negative"
    if any((value_structure < 0 for value_structure in structures_choices.values())):
        return False, "Structures values must be non-negative"
    
    if KINGDOM_CREATOR_STARTING_POINTS - sum_units_points < 0:
        return False, "You do not have that many unit points available"

    if sum_units_points != KINGDOM_CREATOR_STARTING_POINTS:
        return False, "You must use all units points"
    
    if INITIAL_KINGDOM_STATE["kingdom"]["stars"] - sum_structures < 0:
        return False, "You do not have that many stars available for structures"

    if sum_structures != INITIAL_KINGDOM_STATE["kingdom"]["stars"]:
        return False, "You must use all stars for structures"
    
    return True, ""

@app.route('/api/createkingdomchoices', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom_choices():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    user = flask_praetorian.current_user()

    if user.kd_created:
        return (flask.jsonify("This kingdom has already been created"), 400)

    unit_choices = {
        k: int(v or 0)
        for k, v in req["unitsChoices"].items()
    }
    structures_choices = {
        k: int(v or 0)
        for k, v in req["structuresChoices"].items()
    }

    valid_kd, message = _validate_kingdom_choices(unit_choices, structures_choices)
    if not valid_kd:
        return (flask.jsonify(message), 400)
    
    kd_id = user.kd_id
    kd_info = _get_kd_info(kd_id)
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
    payload["last_income"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload["next_resolve"] = kd_info["next_resolve"]
    payload["next_resolve"]["spy_attempt"] = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SPY_ATTEMPT_TIME_MULTIPLIER)
    ).isoformat()

    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )        

    user.kd_created = True
    db.session.commit()
    
    return (flask.jsonify("Success"), 200)


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


@app.route('/api/spyhistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def spy_history():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(history.text, file=sys.stderr)
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["spy_history"]), 200)


@app.route('/api/missilehistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def missile_history():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(history.text, file=sys.stderr)
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["missile_history"]), 200)


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
            if datetime.datetime.fromisoformat(mobi["time"]).astimezone(datetime.timezone.utc) < max_time:
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

    start_time = datetime.datetime.now(datetime.timezone.utc)
    units = _calc_units(start_time, current_units, generals_units, mobis_units)
    maxes = _calc_maxes(units)

    top_queue = sorted(
        mobis_info_parse,
        key=lambda queue: queue["time"],
    )[:10]

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
        'top_queue': top_queue,
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

    start_time = datetime.datetime.now(datetime.timezone.utc)
    units = _calc_units(start_time, current_units, generals_units, mobis_units)

    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units)
    valid_recruits = _validate_recruits(recruits_input, current_available_recruits)
    if not valid_recruits:
        return (flask.jsonify('Please enter valid recruits value'), 400)

    mobis_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_RECRUIT_TIME_MULTIPLIER)).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["mobis"] = min(next_resolve["mobis"], mobis_time)
    new_money = kd_info_parse["money"] - BASE_RECRUIT_COST * recruits_input
    kd_payload = {'money': new_money, 'next_resolve': next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    recruits_payload = {
        "new_mobis": [
            {
                "time": mobis_time,
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
    mobis_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SPECIALIST_TIME_MULTIPLIER)).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["mobis"] = min(next_resolve["mobis"], mobis_time)
    kd_payload = {
        'money': new_money,
        'units': {
            **kd_info_parse["units"],
            'recruits': new_recruits,
        },
        'next_resolve': next_resolve,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    mobis_payload = {
        "new_mobis": [
            {
                "time": mobis_time,
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
            if datetime.datetime.fromisoformat(building_structure["time"]).astimezone(datetime.timezone.utc) < max_time:
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
        current_available_structures = 0
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

    top_queue = sorted(
        structures_info_parse["structures"],
        key=lambda queue: queue["time"],
    )[:10]

    current_price = _get_structure_price(kd_info_parse)
    current_structures = kd_info_parse["structures"]
    building_structures = structures_info_parse["structures"]

    start_time = datetime.datetime.now(datetime.timezone.utc)
    structures = _calc_structures(start_time, current_structures, building_structures)

    max_available_structures, current_available_structures = _calc_available_structures(current_price, kd_info_parse, structures)

    payload = {
        **structures,
        "price": current_price,
        "max_available_structures": max_available_structures,
        "current_available_structures": current_available_structures,
        "top_queue": top_queue,
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

    start_time = datetime.datetime.now(datetime.timezone.utc)
    structures = _calc_structures(start_time, current_structures, building_structures)

    max_available_structures, current_available_structures = _calc_available_structures(current_price, kd_info_parse, structures)

    structures_request = {
        k: int(v or 0)
        for k, v in req.items()
    }
    valid_structures = _validate_structures(structures_request, current_available_structures)
    if not valid_structures:
        return (flask.jsonify('Please enter valid structures values'), 400)

    structures_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_STRUCTURE_TIME_MULTIPLIER)).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["structures"] = min(next_resolve["structures"], structures_time)
    new_money = kd_info_parse["money"] - sum(structures_request.values()) * current_price
    kd_payload = {'money': new_money, 'next_resolve': next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    structures_payload = {
        "new_structures": [
            {
                "time": structures_time,
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

def _get_kd_info(kd_id):
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info.text, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    return kd_info_parse


def _get_max_kd_info(kd_id, revealed_info, max=False):
    always_allowed_keys = {"name", "race"}
    allowed_keys = {
        "stats": ["stars", "score"],
        "kingdom": ["stars", "fuel", "population", "score", "money", "spy_attempts", "auto_spending", "missiles"],
        "military": ["units", "generals_available", "generals_out"],
        "structures": ["structures"],
        "shields": ["shields"],
        "projects": ["projects_points", "projects_max_points", "projects_assigned", "completed_projects"],
        "drones": ["drones"],
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
            project: project_dict.get("max_bonus", 0) * min(kd_info_parse_allowed["projects_points"][project] / kd_info_parse_allowed["projects_max_points"][project], 1.0)
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

    top_queue = sorted(
        settle_info,
        key=lambda queue: queue["time"],
    )[:10]

    settle_price = _get_settle_price(kd_info_parse)
    max_settle, available_settle = _get_available_settle(kd_info_parse, settle_info)

    payload = {
        "settle_price": settle_price,
        "max_available_settle": max_settle,
        "current_available_settle": available_settle,
        "top_queue": top_queue
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
    settle_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SETTLE_TIME_MULTIPLIER)).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["settles"] = min(next_resolve["settles"], settle_time)
    kd_payload = {'money': new_money, "next_resolve": next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    settle_payload = {
        "new_settles": [
            {
                "time": settle_time,
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

def _get_missiles_building(missiles_info): # TODO: Make this not mutate
    missiles_building = {
        k: 0
        for k in MISSILES
    }
    for missile_queue in missiles_info:
        for key_missile, amt_missile in missile_queue.items():
            if key_missile != "time":
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
    top_queue = sorted(
        missiles_info,
        key=lambda queue: queue["time"],
    )[:10]
    missiles_building = _get_missiles_building(missiles_info)

    current_missiles = kd_info_parse["missiles"]

    print(missiles_info)

    payload = {
        "current": current_missiles,
        "building": missiles_building,
        "build_time": BASE_MISSILE_TIME_MULTIPLER * BASE_EPOCH_SECONDS,
        "capacity": kd_info_parse["structures"]["missile_silos"] * BASE_MISSILE_SILO_CAPACITY,
        "desc": MISSILES,
        "top_queue": top_queue
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
    missiles_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_MISSILE_TIME_MULTIPLER)).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["missiles"] = min(next_resolve["missiles"], missiles_time)
    kd_payload = {
        'money': new_money,
        'fuel': new_fuel,
        'next_resolve': next_resolve,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    missiles_payload = {
        "new_missiles": [
            {
                "time": missiles_time,
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
    untrained_engineers = max(max_trainable_engineers - engineers_building, 0)
    max_available_engineers = min(available_workshop_capacity, untrained_engineers)
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

    engineers_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_ENGINEER_TIME_MULTIPLIER)).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["engineers"] = min(next_resolve["engineers"], engineers_time)
    new_money = kd_info_parse["money"] - BASE_ENGINEER_COST * engineers_input
    kd_payload = {'money': new_money, 'next_resolve': next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    engineers_payload = {
        "new_engineers": [
            {
                "time": engineers_time,
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

@app.route('/api/offershared', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def offer_shared():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    shared_kd = str(req["shared"])
    shared_stat = req["shared_stat"]
    shared_to_kd = str(req["shared_to"])
    cut = float(req.get("cut", 0)) / 100

    if (
        shared_kd == "" or shared_kd == None
        or shared_stat == "" or shared_stat == None
        or shared_to_kd == "" or shared_to_kd == None
    ):
        return flask.jsonify({"message": "The request selections are not complete"}), 400

    kd_id = flask_praetorian.current_user().kd_id
    print(kd_id, file=sys.stderr)

    galaxies_inverted, _ = _get_galaxies_inverted()
    revealed_info = _get_revealed(kd_id)
    
    your_shared_info = _get_shared(kd_id)
    shared_to_shared_info = _get_shared(shared_to_kd)

    if shared_stat not in revealed_info["revealed"][shared_kd].keys():
        return flask.jsonify({"message": "You do not have that revealed stat to share"}), 400
    
    if shared_stat == your_shared_info["shared"].get(shared_kd, {}).get("shared_stat"):
        return flask.jsonify({"message": "You can not share intel that was shared with you"}), 400

    your_galaxy = galaxies_inverted[kd_id]
    shared_to_galaxy = galaxies_inverted.get(shared_to_kd, None)

    if your_galaxy != shared_to_galaxy and shared_to_kd != "galaxy":
        return flask.jsonify({"message": "You can not share to kingdoms outside of your galaxy"}), 400

    shared_resolve_time = revealed_info["revealed"][shared_kd][shared_stat]
    your_payload = { # TODO: this needs to support offers to multiple KDs
        "shared_offers": {
            **your_shared_info["shared_offers"],
            shared_kd: {
                "shared_to": shared_to_kd,
                "shared_stat": shared_stat,
                "cut": cut,
                "time": shared_resolve_time,
            }
        }
    }
    shared_to_payload = { # TODO: this needs to support offers from multiple KDs
        "shared_requests": {
            **shared_to_shared_info["shared_requests"],
            shared_kd: {
                "shared_by": kd_id,
                "shared_stat": shared_stat,
                "cut": cut,
                "time": shared_resolve_time,
            }
        }
    }

    your_shared_info_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(your_payload),
    )
    shared_to_shared_info_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{shared_to_kd}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(shared_to_payload),
    )

    your_info = _get_kd_info(kd_id)
    if shared_resolve_time < your_info["next_resolve"]["shared"]:
        your_next_resolve = your_info["next_resolve"]
        your_next_resolve["shared"] = shared_resolve_time
        REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({"next_resolve": your_next_resolve}),
        )
    shared_to_kd_info = _get_kd_info(shared_to_kd)
    if shared_resolve_time < shared_to_kd_info["next_resolve"]["shared"]:
        shared_to_next_resolve = shared_to_kd_info["next_resolve"]
        shared_to_next_resolve["shared"] = shared_resolve_time
        REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{shared_to_kd}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({"next_resolve": shared_to_next_resolve}),
        )
    return (flask.jsonify({"message": "Succesfully shared intel", "status": "success"}), 200)

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

    time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_REVEAL_DURATION_MULTIPLIER)).isoformat()
    payload = {
        "new_galaxies": {
            galaxy_to_reveal: time
        }
    }

    payload["new_revealed"] = {
        kd_id: {
            "stats": time,
        }
        for kd_id in galaxy_info[galaxy_to_reveal]
    }

    print(payload)
    reveal_galaxy_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    print(reveal_galaxy_response.text)

    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["revealed"] = min(next_resolve["revealed"], time)
    kd_payload = {"spy_attempts": kd_info_parse["spy_attempts"] - 1, "next_resolve": next_resolve}
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
    general_bonus=0
):
    return_time_with_bonus = datetime.timedelta(seconds=BASE_EPOCH_SECONDS * return_multiplier) * (1 - general_bonus)
    print(return_time_with_bonus)
    return_times = [
        base_time + (return_time_with_bonus / i)
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
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
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
    try:
        attack_ratio = min(attack / defense, 1.0)
    except ZeroDivisionError:
        attack_ratio = 1.0
    attacker_losses = _calc_losses(
        attacker_units,
        BASE_ATTACKER_UNIT_LOSS_RATE,
    )
    defender_losses = _calc_losses(
        defender_units,
        BASE_DEFENDER_UNIT_LOSS_RATE * attack_ratio,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
        current_bonuses["general_bonus"],
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
    if str(target_kd) == str(kd_id):
        return (flask.jsonify("You cannot attack yourself!"), 400)

    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }

    revealed = _get_revealed(kd_id)["revealed"]
    shared = _get_shared(kd_id)["shared"]
    target_kd_info = _get_max_kd_info(target_kd, revealed, max=True)
    target_current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(target_kd_info["projects_points"][project] / target_kd_info["projects_max_points"][project], 1.0)
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
    time_now = datetime.datetime.now(datetime.timezone.utc)
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
        current_bonuses["general_bonus"],
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
    next_return_time = min([general["return_time"] for general in generals])
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
    kd_info_parse["next_resolve"]["generals"] = min(kd_info_parse["next_resolve"]["generals"], next_return_time)

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

def _validate_spy_request(
    drones,
    kd_info,
    shielded,
):
    if drones > kd_info["drones"]:
        return False, "You do not have that many drones"
    if drones < 0:
        return False, "You can not send negative drones"
    if shielded:
        if kd_info["fuel"] < drones:
            return False, "You do not have enough fuel"
    if kd_info["spy_attempts"] == 0:
        return False, "You do not have any more spy attempts"
    
    return True, ""

def _calculate_spy_probability(
    drones_to_send,
    target_drones,
    target_stars,
    target_shields,
):
    drones_defense = target_drones * BASE_DRONES_DRONE_DEFENSE_MULTIPLIER
    stars_defense = target_stars * BASE_STARS_DRONE_DEFENSE_MULTIPLIER
    total_defense = max(drones_defense + stars_defense, 1)

    base_probability = min(max(drones_to_send / total_defense, BASE_SPY_MIN_SUCCESS_CHANCE), 1.0)
    shielded_probability = base_probability * (1 - target_shields)

    return shielded_probability, drones_defense, stars_defense

def _calculate_spy_losses(
    drones_to_send,
    shielded,
):
    shielded_reduction = 1 - (int(shielded) * BASE_DRONES_SHIELDING_LOSS_REDUCTION)
    success_loss = math.floor(drones_to_send * BASE_DRONES_SUCCESS_LOSS_RATE * shielded_reduction)
    failure_loss = math.floor(drones_to_send * BASE_DRONES_FAILURE_LOSS_RATE * shielded_reduction)
    return success_loss, failure_loss
    
        
@app.route('/api/calculatespy/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def calculate_spy(target_kd):
    req = flask.request.get_json(force=True)
    drones = int(req["drones"])
    shielded = req["shielded"]
    defender_raw_values = req["defenderValues"]
    operation = req["operation"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    if not operation:
        return (flask.jsonify({"message": "You must select an operation"}), 400)
    
    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = _get_revealed(kd_id)["revealed"]
    max_target_kd_info = _get_max_kd_info(target_kd, revealed)
    
    if "drones" in max_target_kd_info:
        defender_drones = max_target_kd_info["drones"]
    else:
        defender_drones = int(defender_raw_values["drones"] or 0)
    
    if "stars" in max_target_kd_info:
        defender_stars = max_target_kd_info["stars"]
    else:
        defender_stars = int(defender_raw_values["stars"] or 0)

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["spy"]
    else:
        defender_shields = float(defender_raw_values['shields'] or 0) / 100
    
    spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
        drones,
        defender_drones,
        defender_stars,
        defender_shields
    )
    success_losses, failure_losses = _calculate_spy_losses(drones, shielded)

    message = f"The operation has a {spy_probability:.2%} chance of success. \n\nIf successful, {success_losses} drones will be lost. \nIf unsuccessful, {failure_losses} drones will be lost.\n"

    if operation in REVEAL_OPERATIONS:
        revealed_stat = operation.replace('spy', '')
        reveal_duration_seconds = BASE_REVEAL_DURATION_MULTIPLIER * BASE_EPOCH_SECONDS
        reveal_duration_hours = reveal_duration_seconds / 3600
        message += f"If successful, the target's {revealed_stat} will be revealed for {reveal_duration_hours} hours.\n"

    payload = {
        "message": message,
        "stars_defense": stars_defense,
        "drones_defense": drones_defense,
        "total_defense": stars_defense + drones_defense,
    }
    return (flask.jsonify(payload), 200)
    
        
@app.route('/api/spy/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def spy(target_kd):
    req = flask.request.get_json(force=True)
    drones = int(req["drones"])
    shielded = req["shielded"]
    operation = req["operation"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)
    
    if not operation:
        return (flask.jsonify({"message": "You must select an operation"}), 400)

    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = _get_revealed(kd_id)["revealed"]
    max_target_kd_info = _get_max_kd_info(target_kd, revealed, max=True)
    
    defender_drones = max_target_kd_info["drones"]
    defender_stars = max_target_kd_info["stars"]
    defender_shields = max_target_kd_info["shields"]["spy"]
    
    spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
        drones,
        defender_drones,
        defender_stars,
        defender_shields
    )
    print(spy_probability)
    success_losses, failure_losses = _calculate_spy_losses(drones, shielded)

    roll = random.uniform(0, 1)
    print(roll)
    success = roll < spy_probability

    time_now = datetime.datetime.now(datetime.timezone.utc)
    revealed_until = None
    if success:
        status = "success"
        if operation in REVEAL_OPERATIONS:
            revealed_stat = operation.replace('spy', '')
            reveal_duration_seconds = BASE_REVEAL_DURATION_MULTIPLIER * BASE_EPOCH_SECONDS
            revealed_until = time_now + datetime.timedelta(seconds=reveal_duration_seconds)
            reveal_duration_hours = reveal_duration_seconds / 3600

            revealed_payload = {
                "new_revealed": {
                    target_kd: {
                        revealed_stat: revealed_until.isoformat()
                    }
                }
            }
            reveal_response = REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps(revealed_payload),
            )
            message = f"Success! The target will be revealed for {reveal_duration_hours} hours. You have lost {success_losses} drones."
        target_message = "You were infiltrated by drones on a spy operation"
        losses = success_losses
    else:
        status = "failure"
        message = f"Failure! You have lost {failure_losses} drones."
        target_message = f"{kd_info_parse['name']} failed a spy operation on you"
        losses = failure_losses

    kd_patch_payload = {
        "drones": kd_info_parse["drones"] - losses,
        "spy_attempts": kd_info_parse["spy_attempts"] - 1
    }
    if shielded:
        kd_patch_payload["fuel"] = kd_info_parse["fuel"] - drones
    if revealed_until:
        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["revealed"] = min(next_resolve["revealed"], revealed_until.isoformat())
        kd_patch_payload["next_resolve"] = next_resolve
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload, default=str),
    )

    history_payload = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "operation": operation,
        "news": message,
    }
    kd_spy_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(history_payload, default=str),
    )

    target_news_payload = {
        "time": time_now.isoformat(),
        "from": "" if success else kd_id,
        "news": target_message,
    }
    target_news_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_news_payload),
    )

    payload = {
        "status": status,
        "message": message,
    }
    return (flask.jsonify(payload), 200)



def _validate_missiles_request(
    attacker_missiles,
    kd_info,
):
    if any((
        value_missile > kd_info["missiles"][key_missile]
        for key_missile, value_missile in attacker_missiles.items()
    )):
        return False, "You do not have that many missiles"
    if any((
        value_missile < 0
        for value_missile in attacker_missiles.values()
    )):
        return False, "You can not send negative missiles"
    
    return True, ""

def _calculate_missiles_damage(
    attacker_missiles,
    defender_shields,
):
    damage_categories = {"stars_damage", "fuel_damage", "pop_damage"}
    damage = {}
    for damage_category in damage_categories:
        damage[damage_category] = sum([
            math.floor(value_missiles * MISSILES[key_missile].get(damage_category) * (1 - defender_shields))
            for key_missile, value_missiles in attacker_missiles.items()
        ])
    return damage
    

@app.route('/api/calculatemissiles/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def calculate_missiles(target_kd):
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    attacker_missiles = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if value != ""
    }

    valid_request, message = _validate_missiles_request(
        attacker_missiles,
        kd_info_parse,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = _get_revealed(kd_id)["revealed"]
    max_target_kd_info = _get_max_kd_info(target_kd, revealed)

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["missiles"]
    else:
        defender_shields = float(req['defenderShields'] or 0) / 100
    
    missile_damage = _calculate_missiles_damage(
        attacker_missiles,
        defender_shields
    )

    message = f"The missiles will destroy " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

    payload = {
        "message": message,
    }
    return (flask.jsonify(payload), 200)         
    

@app.route('/api/launchmissiles/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def launch_missiles(target_kd):
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    print(kd_id, file=sys.stderr)
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    print(kd_info, file=sys.stderr)
    kd_info_parse = json.loads(kd_info.text)

    attacker_missiles = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if value != ""
    }

    valid_request, message = _validate_missiles_request(
        attacker_missiles,
        kd_info_parse,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = _get_revealed(kd_id)["revealed"]
    max_target_kd_info = _get_max_kd_info(target_kd, revealed, max=True)
    defender_shields = max_target_kd_info["shields"]["missiles"]
    
    missile_damage = _calculate_missiles_damage(
        attacker_missiles,
        defender_shields
    )

    message = f"Your missiles destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])
    defender_message = f"Missiles from {kd_info_parse['name']} have destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

    kd_patch_payload = {
        "missiles": {
            k: v - attacker_missiles.get(k, 0)
            for k, v in kd_info_parse["missiles"].items()
        }
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload, default=str),
    )

    defender_patch_payload = {
        "stars": kd_info_parse["stars"] - missile_damage["stars_damage"],
        "population": kd_info_parse["population"] - missile_damage["pop_damage"],
        "fuel": kd_info_parse["fuel"] - missile_damage["fuel_damage"],
    }
    defender_kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(defender_patch_payload, default=str),
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    target_news_payload = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "news": defender_message,
    }
    target_news_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_news_payload),
    )
    history_payload = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "news": message,
    }
    kd_missile_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(history_payload, default=str),
    )

    payload = {
        "message": message,
    }
    return (flask.jsonify(payload), 200)


def _kingdom_with_income(
    kd_info_parse,
): # TODO: Pop handling
    time_now = datetime.datetime.now(datetime.timezone.utc)
    time_last_income = datetime.datetime.fromisoformat(kd_info_parse["last_income"]).astimezone(datetime.timezone.utc)
    seconds_elapsed = (time_now - time_last_income).seconds
    epoch_elapsed = seconds_elapsed / BASE_EPOCH_SECONDS

    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }
    raw_new_income = (
        (kd_info_parse["structures"]["mines"] * BASE_MINES_INCOME_PER_EPOCH)
        + (kd_info_parse["population"] * BASE_POP_INCOME_PER_EPOCH)
    ) * (1 + current_bonuses["money_bonus"])
    new_income = raw_new_income * epoch_elapsed
    new_fuel = kd_info_parse["structures"]["fuel_plants"] * BASE_FUEL_PLANTS_INCOME_PER_EPOCH * epoch_elapsed * (1 + current_bonuses["fuel_bonus"])
    raw_fuel_consumption = (
        sum([
            value_units * UNITS[key_unit]["fuel"]
            for key_unit, value_units in kd_info_parse["units"].items()
        ])
        + (kd_info_parse["population"] * BASE_POP_FUEL_CONSUMPTION_PER_EPOCH)
    )
    fuel_spent = raw_fuel_consumption * epoch_elapsed
    net_fuel = new_fuel - fuel_spent
    max_fuel = kd_info_parse["structures"]["fuel_plants"] * BASE_FUEL_PLANTS_CAPACITY
    new_drones = kd_info_parse["structures"]["drone_factories"] * BASE_DRONE_PLANTS_PRODUCTION_PER_EPOCH * epoch_elapsed

    new_project_points = {
        key_project: assigned_engineers * BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH * epoch_elapsed
        for key_project, assigned_engineers in kd_info_parse["projects_assigned"].items()
    }
    new_kd_info = kd_info_parse.copy()
    for key_project, new_points in new_project_points.items():
        kd_info_parse["projects_points"][key_project] += new_points
    new_kd_info["money"] += new_income
    new_kd_info["fuel"] = min(max_fuel, new_kd_info["fuel"] + net_fuel)
    new_kd_info["drones"] += new_drones
    new_kd_info["last_income"] = time_now.isoformat()

    return new_kd_info
    
def _resolve_settles(kd_id, time_update):
    settle_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    settle_info_parse = json.loads(settle_info.text)

    ready_settles = 0
    keep_settles = []
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)
    for settle in settle_info_parse["settles"]:
        time = datetime.datetime.fromisoformat(settle["time"]).astimezone(datetime.timezone.utc)
        if time < time_update:
            ready_settles += settle['amount']
        else:
            if time < next_resolve:
                next_resolve = time
            keep_settles.append(settle)
    
    settles_payload = {
        "settles": keep_settles
    }
    settles_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(settles_payload),
    )
    print(settles_patch.text)
    return ready_settles, next_resolve
    
def _resolve_mobis(kd_id, time_update):
    mobis_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    mobis_info_parse = json.loads(mobis_info.text)

    ready_mobis = collections.defaultdict(int)
    keep_mobis = []
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)
    for mobi in mobis_info_parse["mobis"]:
        time = datetime.datetime.fromisoformat(mobi["time"]).astimezone(datetime.timezone.utc)
        if time < time_update:
            mobi.pop("time")
            for key_unit, amt_unit in mobi.items():
                ready_mobis[key_unit] += amt_unit
        else:
            next_resolve = min(time, next_resolve)
            keep_mobis.append(mobi)
    
    print(ready_mobis)
    print(keep_mobis)
    mobis_payload = {
        "mobis": keep_mobis
    }
    mobis_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(mobis_payload),
    )
    print(mobis_patch.text)
    return ready_mobis, next_resolve
    
def _resolve_structures(kd_id, time_update):
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    structures_info_parse = json.loads(structures_info.text)

    ready_structures = collections.defaultdict(int)
    keep_structures = []
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)
    for structure in structures_info_parse["structures"]:
        time = datetime.datetime.fromisoformat(structure["time"]).astimezone(datetime.timezone.utc)
        if time < time_update:
            structure.pop("time")
            for key_structure, amt_structure in structure.items():
                ready_structures[key_structure] += amt_structure
        else:
            next_resolve = min(time, next_resolve)
            keep_structures.append(structure)
    
    print(ready_structures)
    print(keep_structures)
    structures_payload = {
        "structures": keep_structures
    }
    structures_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(structures_payload),
    )
    print(structures_patch.text)
    return ready_structures, next_resolve
    
def _resolve_missiles(kd_id, time_update):
    missiles_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    missiles_info_parse = json.loads(missiles_info.text)

    ready_missiles = collections.defaultdict(int)
    keep_missiles = []
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)
    for missile in missiles_info_parse["missiles"]:
        time = datetime.datetime.fromisoformat(missile["time"]).astimezone(datetime.timezone.utc)
        if time < time_update:
            missile.pop("time")
            for key_missile, amt_missile in missile.items():
                ready_missiles[key_missile] += amt_missile
        else:
            next_resolve = min(time, next_resolve)
            keep_missiles.append(missile)
    
    missiles_payload = {
        "missiles": keep_missiles
    }
    missiles_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(missiles_payload),
    )
    print(missiles_patch.text)
    return ready_missiles, next_resolve
    
def _resolve_engineers(kd_id, time_update):
    engineer_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    engineer_info_parse = json.loads(engineer_info.text)

    ready_engineers = 0
    keep_engineers = []
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)
    for engineer in engineer_info_parse["engineers"]:
        time = datetime.datetime.fromisoformat(engineer["time"]).astimezone(datetime.timezone.utc)
        if time < time_update:
            ready_engineers += engineer['amount']
        else:
            if time < next_resolve:
                next_resolve = time
            keep_engineers.append(engineer)
    
    engineers_payload = {
        "engineers": keep_engineers
    }
    engineers_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(engineers_payload),
    )
    print(engineers_patch.text)
    return ready_engineers, next_resolve
    
def _resolve_revealed(kd_id, time_update):
    revealed_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    revealed_info_parse = json.loads(revealed_info.text)

    keep_revealed = collections.defaultdict(dict)
    keep_galaxies = {}
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)

    for revealed_kd_id, revealed_dict in revealed_info_parse["revealed"].items():
        for revealed_stat, time_str in revealed_dict.items():
            time = datetime.datetime.fromisoformat(time_str).astimezone(datetime.timezone.utc)
            if time > time_update:
                next_resolve = min(time, next_resolve)
                keep_revealed[revealed_kd_id][revealed_stat] = time_str

    for galaxy_id, time_str in revealed_info_parse["galaxies"].items():
        time = datetime.datetime.fromisoformat(time_str).astimezone(datetime.timezone.utc)
        if time > time_update:
            keep_galaxies[galaxy_id] = time_str
            next_resolve = min(time, next_resolve)

    revealed_payload = {
        "revealed": keep_revealed,
        "galaxies": keep_galaxies,
    }
    revealed_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(revealed_payload),
    )
    print(revealed_patch.text)
    return next_resolve
    
def _resolve_shared(kd_id, time_update):
    shared_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    shared_info_parse = json.loads(shared_info.text)

    keep_shared = collections.defaultdict(dict)
    keep_shared_requests = collections.defaultdict(dict)
    keep_shared_offers = collections.defaultdict(dict)
    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)

    for shared_kd_id, shared_dict in shared_info_parse["shared"].items():
        time = datetime.datetime.fromisoformat(shared_dict["time"]).astimezone(datetime.timezone.utc)
        if time > time_update:
            next_resolve = min(time, next_resolve)
            keep_shared[shared_kd_id] = shared_dict

    for shared_kd_id, shared_dict in shared_info_parse["shared_requests"].items():
        time = datetime.datetime.fromisoformat(shared_dict["time"]).astimezone(datetime.timezone.utc)
        if time > time_update:
            next_resolve = min(time, next_resolve)
            keep_shared_requests[shared_kd_id] = shared_dict

    for shared_kd_id, shared_dict in shared_info_parse["shared_offers"].items():
        time = datetime.datetime.fromisoformat(shared_dict["time"]).astimezone(datetime.timezone.utc)
        if time > time_update:
            next_resolve = min(time, next_resolve)
            keep_shared_offers[shared_kd_id] = shared_dict

    shared_payload = {
        "shared": keep_shared,
        "shared_requests": keep_shared_requests,
        "shared_offers": keep_shared_offers,
    }
    shared_post = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(shared_payload),
    )
    print(shared_post.text)
    return next_resolve

def _resolve_generals(kd_info_parse, time_update):
    generals_keep = []
    returning_units = collections.defaultdict(int)
    returning_generals = 0

    next_resolve = datetime.datetime(year=2099, month=1, day=1).astimezone(datetime.timezone.utc)
    for general in kd_info_parse["generals_out"]:
        time = datetime.datetime.fromisoformat(general["return_time"]).astimezone(datetime.timezone.utc)
        if time < time_update:
            general.pop("return_time")
            for key_unit, value_units in general.items():
                returning_units[key_unit] += value_units
            returning_generals += 1
        else:
            next_resolve = min(time, next_resolve)
            generals_keep.append(general)

    kd_info_parse["generals_available"] += returning_generals
    for key_unit, value_unit in returning_units.items():
        kd_info_parse["units"][key_unit] += value_unit

    kd_info_parse["generals_out"] = generals_keep
    return kd_info_parse, next_resolve


def _resolve_spy(kd_info_parse, time_update):
    resolve_time = datetime.datetime.fromisoformat(kd_info_parse["next_resolve"]["spy_attempt"]).astimezone(datetime.timezone.utc)
    next_resolve_time = max(
        resolve_time + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SPY_ATTEMPT_TIME_MULTIPLIER),
        time_update,
    )
    if kd_info_parse["spy_attempts"] < BASE_SPY_ATTEMPTS_MAX:
        kd_info_parse["spy_attempts"] += 1
    return kd_info_parse, next_resolve_time

@app.route('/api/refreshdata')
def refresh_data():
    """Performance periodic refresh tasks"""
    headers = flask.request.headers
    if headers.get("Refresh-Secret", "") != "domnusrefresh":
        return ("Not Authorized", 401)

    kingdoms = _get_kingdoms()
    for kd_id in kingdoms:
        if str(kd_id) != "12":
            continue
        next_resolves = {}
        time_update = datetime.datetime.now(datetime.timezone.utc)
        kd_info = REQUESTS_SESSION.get(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
        )
        kd_info_parse = json.loads(kd_info.text)

        categories_to_resolve = [cat for cat, time in kd_info_parse["next_resolve"].items() if datetime.datetime.fromisoformat(time).astimezone(datetime.timezone.utc) < time_update]
        if "settles" in categories_to_resolve:
            new_stars, next_resolves["settles"] = _resolve_settles(
                kd_id,
                time_update,
            )
            kd_info_parse["stars"] += new_stars
            for key_project, project_dict in PROJECTS.items():
                project_max_func = project_dict["max_points"]
                kd_info_parse["projects_max_points"][key_project] = project_max_func(kd_info_parse["stars"])
        
        if "mobis" in categories_to_resolve:
            new_units, next_resolves["mobis"] = _resolve_mobis(kd_id, time_update)
            for key_unit, amt_unit in new_units.items():
                kd_info_parse["units"][key_unit] += amt_unit
        
        if "structures" in categories_to_resolve:
            new_structures, next_resolves["structures"] = _resolve_structures(kd_id, time_update)
            for key_structure, amt_structure in new_structures.items():
                kd_info_parse["structures"][key_structure] += amt_structure
        
        if "missiles" in categories_to_resolve:
            new_missiles, next_resolves["missiles"] = _resolve_missiles(kd_id, time_update)
            for key_missiles, amt_missiles in new_missiles.items():
                kd_info_parse["missiles"][key_missiles] += amt_missiles

        if "engineers" in categories_to_resolve:
            new_engineers, next_resolves["engineers"] = _resolve_engineers(
                kd_id,
                time_update,
            )
            kd_info_parse["units"]["engineers"] += new_engineers
        
        if "revealed" in categories_to_resolve:
            next_resolves["revealed"] = _resolve_revealed(
                kd_id,
                time_update,
            )
        
        if "shared" in categories_to_resolve:
            next_resolves["shared"] = _resolve_shared(
                kd_id,
                time_update,
            )

        if "generals" in categories_to_resolve:
            kd_info_parse, next_resolves["generals"] = _resolve_generals(
                kd_info_parse,
                time_update,
            )
        
        if "spy_attempt" in categories_to_resolve:
            kd_info_parse, next_resolves["spy_attempt"] = _resolve_spy(
                kd_info_parse,
                time_update
            )

        for category, next_resolve_datetime in next_resolves.items():
            kd_info_parse["next_resolve"][category] = next_resolve_datetime.isoformat()
        new_kd_info = _kingdom_with_income(kd_info_parse)
        kd_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(new_kd_info, default=str),
        )
    return "Refreshed", 200



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
    return (flask.jsonify(datetime.datetime.now(datetime.timezone.utc).isoformat()), 200)

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