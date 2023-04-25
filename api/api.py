import collections
import datetime
import math
import os
import random
import requests
import sys
import json
import copy
import time
import uuid
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

ONE_TIME_PROJECTS = [
    "big_flexers",
    "star_busters",
    "galaxy_busters",
    "drone_gadgets",
]

BASE_EPOCH_SECONDS = 60 * 60

BASE_SETTLE_COST = lambda stars: math.floor((stars ** 0.5) * 50)
BASE_MAX_SETTLE = lambda stars: math.floor(stars * 0.15)
BASE_SETTLE_TIME_MULTIPLIER = 12

BASE_STRUCTURE_COST = lambda stars: math.floor((stars ** 0.5) * 40)
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
BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH = 1

BASE_STRUCTURES_LOSS_RETURN_RATE = 0.2
BASE_STRUCTURES_LOSS_PER_STAR_PER_EPOCH = 0.02

BASE_MISSILE_TIME_MULTIPLER = 24

BASE_GENERALS_BONUS = lambda generals: (generals - 1) * 0.03
BASE_GENERALS_RETURN_TIME_MULTIPLIER = 8
BASE_RETURN_TIME_PENALTY_PER_COORDINATE = 0.01
BASE_DEFENDER_UNIT_LOSS_RATE = 0.05
BASE_ATTACKER_UNIT_LOSS_RATE = 0.05
BASE_KINGDOM_LOSS_RATE = 0.10
BASE_FUELLESS_STRENGTH_REDUCTION = 0.2
BASE_ATTACK_MIN_STARS_GAIN = 25

BASE_PRIMITIVES_DEFENSE_PER_STAR = lambda seconds: 100 * math.sqrt(1 + seconds / 3600 / 24)
BASE_PRIMITIVES_MONEY_PER_STAR = 1000
BASE_PRIMITIVES_FUEL_PER_STAR = 100
BASE_PRIMITIVES_POPULATION_PER_STAR = 10
BASE_PRIMITIVES_ROB_PER_DRONE = lambda seconds: 4 / math.sqrt(1 + seconds / 3600 / 24)

BASE_STARS_DRONE_DEFENSE_MULTIPLIER = 4
BASE_DRONES_DRONE_DEFENSE_MULTIPLIER = 1
BASE_SPY_MIN_SUCCESS_CHANCE = 0.10
BASE_DRONES_SUCCESS_LOSS_RATE = 0.01
BASE_DRONES_FAILURE_LOSS_RATE = 0.02
BASE_DRONES_SHIELDING_LOSS_REDUCTION = 0.5
BASE_REVEAL_DURATION_MULTIPLIER = 8

BASE_DRONES_SIPHON_PER_DRONE = 8
BASE_DRONES_SIPHON_TIME_MULTIPLIER = 8
BASE_DRONES_PER_HOME_DAMAGE = 1500
BASE_DRONES_MAX_HOME_DAMAGE = 0.05
BASE_DRONES_PER_FUEL_PLANT_DAMAGE = 1500
BASE_DRONES_MAX_FUEL_PLANT_DAMAGE = 0.05
BASE_DRONES_PER_KIDNAP = 10
BASE_DRONES_MAX_KIDNAP_DAMAGE = 0.05
BASE_DRONES_SUICIDE_FUEL_DAMAGE = 5
BASE_KIDNAP_RETURN_RATE = 0.4

BASE_MAX_SIPHON = 0.10

BASE_POP_INCOME_PER_EPOCH = 2
BASE_POP_FUEL_CONSUMPTION_PER_EPOCH = 0.5
BASE_PCT_POP_GROWTH_PER_EPOCH = 0.10
BASE_POP_GROWTH_PER_STAR_PER_EPOCH = 0.5
BASE_FUELLESS_POP_GROWTH_REDUCTION = 0.9
BASE_FUELLESS_POP_CAP_REDUCTION = 0.2
BASE_NEGATIVE_FUEL_CAP = lambda stars: stars * -5

BASE_PCT_POP_LOSS_PER_EPOCH = 0.10
BASE_POP_LOSS_PER_STAR_PER_EPOCH = 0.2

BASE_SPY_ATTEMPT_TIME_MULTIPLIER = 1
BASE_SPY_ATTEMPTS_MAX = 10

BASE_MILITARY_SHIELDS_MAX = 0.10
BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT = 0.1
BASE_SPY_SHIELDS_MAX = 0.20
BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT = 0.05
BASE_SPY_RADAR_MAX = 0.20
BASE_SPY_RADAR_COST_PER_LAND_PER_PCT = 0.05
BASE_MISSILES_SHIELDS_MAX = 1.0
BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT = 0.005

BASE_VOTES_COST = 10000
BASE_ELECTION_LENGTH_SECONDS = BASE_EPOCH_SECONDS * 24 * 1
BASE_ELECTION_RESULTS_DURATION = BASE_EPOCH_SECONDS * 24 * 6

BASE_AUTO_SPENDING_TIME_MULTIPLIER = 0.1

REVEAL_OPERATIONS = [
    "spykingdom",
    "spymilitary",
    "spyshields",
    "spyprojects",
    "spystructures",
    "spydrones",
]
AGGRO_OPERATIONS = [
    "siphonfunds",
    "bombhomes",
    "sabotagefuelplants",
    "kidnappopulation",
    "suicidedrones"
]

DATE_SENTINEL = "2099-01-01T00:00:00+00:00"

INITIAL_KINGDOM_STARS = 300
INITIAL_KINGDOM_STATE = {
    "kingdom": {
        "kdId": "",
        "name": "",
        "race": "",
        "status": "Active",
        "coordinate": random.randint(0, 99),
        "last_income": "",
        "next_resolve": {
            "generals": DATE_SENTINEL,
            "spy_attempt": DATE_SENTINEL,
            "settles": DATE_SENTINEL,
            "mobis": DATE_SENTINEL,
            "missiles": DATE_SENTINEL,
            "engineers": DATE_SENTINEL,
            "structures": DATE_SENTINEL,
            "revealed": DATE_SENTINEL,
            "shared": DATE_SENTINEL,
            "auto_spending": DATE_SENTINEL,
        },
        "stars": INITIAL_KINGDOM_STARS,
        "fuel": 10000,
        "population": 2500,
        "score": 0,
        "votes": 0,
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
        "max_recruits": 99999,
        "recruits_before_units": True,
        "units_target": {
            "attack": 0,
            "defense": 0,
            "flex": 0,
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
        "structures_target": {
            "homes": 0,
            "mines": 0,
            "fuel_plants": 0,
            "hangars": 0,
            "drone_factories": 0,
            "missile_silos": 0,
            "workshops": 0,
        },
        "revealed_to": {},
        "auto_spending_enabled": False,
        "auto_spending": {
            "settle": 0,
            "structures": 0,
            "military": 0,
            "engineers": 0,
        },
        "funding": {
            "settle": 0,
            "structures": 0,
            "military": 0,
            "engineers": 0,
        },
        "auto_attack_enabled": False,
        "auto_attack_settings": {
            "flex": 0,
            "pure": 0,
        },
        "auto_rob_enabled": False,
        "auto_rob_settings": {
            "drones": 0,
            "shielded": False,
            "keep": 0,
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
        "auto_assign_projects": False,
        "projects_target": {
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
        "projects_max_points": {
            "pop_bonus": PROJECTS["pop_bonus"]["max_points"](INITIAL_KINGDOM_STARS),
            "fuel_bonus": PROJECTS["fuel_bonus"]["max_points"](INITIAL_KINGDOM_STARS),
            "military_bonus": PROJECTS["military_bonus"]["max_points"](INITIAL_KINGDOM_STARS),
            "money_bonus": PROJECTS["money_bonus"]["max_points"](INITIAL_KINGDOM_STARS),
            "general_bonus": PROJECTS["general_bonus"]["max_points"](INITIAL_KINGDOM_STARS),
            "spy_bonus": PROJECTS["spy_bonus"]["max_points"](INITIAL_KINGDOM_STARS),
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
            "spy_radar": 0.0,
            "missiles": 0.0
        },
        "schedule": [],
    },
    "siphons_in": {"siphons_in": []},
    "siphons_out": {"siphons_out": []},
    "news": {"news": []},
    "settles": {"settles": []},
    "mobis": {"mobis": []},
    "structures": {"structures": []},
    "missiles": {"missiles": []},
    "engineers": {"engineers": []},
    "revealed": {
        "revealed": {},
        "galaxies": {},
        "revealed_galaxymates": [],
        "revealed_to_galaxymates": [],
    },
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

GALAXY_POLICIES = {
    "policy_1": {
        "name": "Growth Doctrine",
        "options": {
            "1": {
                "name": "Expansionist",
                "desc": "You grow your kingdoms through exploring new frontiers. Your galaxy's settling costs 15% less"
            },
            "2": {
                "name": "Warlike",
                "desc": "You grow your kingdoms through military force. Your galaxy's generals return 10% faster"
            }
        }
    },
    "policy_2": {
        "name": "Defense Doctrine",
        "options": {
            "1": {
                "name": "Intelligence",
                "desc": "You protect your kingdoms through proactive intelligence gathering. Your galaxy's spy attempts return 10% faster"
            },
            "2": {
                "name": "Conscription",
                "desc": "You protect your kingdoms through mandatory military enlistment. Your galaxy's recruits are trained 20% faster"
            }
        }
    },
}

UNIVERSE_POLICIES = {
    "policy_1": {
        "name": "Arms Doctrine",
        "options": {
            "1": {
                "name": "Unregulated",
                "desc": "Militarization has no universal regulation. All military units cost 20% less."
            },
            "2": {
                "name": "Treatied",
                "desc": "Universal treaties enforce demilitarization. All military units cost 20% more."
            }
        }
    },
    "policy_2": {
        "name": "Trade Doctrine",
        "options": {
            "1": {
                "name": "Free Trade",
                "desc": "Kingdoms freely engage in mutually beneficial trade. Universal income is increased by 10%"
            },
            "2": {
                "name": "Isolationist",
                "desc": "Kingdoms impose tariffs on imported goods. Universal income is decreased by 10%"
            }
        }
    },
}

BASE_EXPANSIONIST_SETTLE_REDUCTION = 0.15
BASE_WARLIKE_RETURN_REDUCTION = 0.1
BASE_INTELLIGENCE_RETURN_REDUCTION = 0.1
BASE_CONSCRIPTION_TIME_REDUCTION = 0.2
BASE_UNREGULATED_COST_REDUCTION = 0.2
BASE_TREATIED_COST_INCREASE = 0.2
BASE_FREE_TRADE_INCREASE = 0.1
BASE_ISOLATIONIST_DECREASE = 0.1

PRETTY_NAMES = {
    "spykingdom": "Spy on Kingdom",
    "spymilitary": "Spy on Military",
    "spyshields": "Spy on Shields",
    "spyprojects": "Spy on Projects",
    "spystructures": "Spy on Structures",
    "spydrones": "Spy on Drones",
    "siphonfunds": "Siphon Funds",
    "bombhomes": "Bomb Homes",
    "sabotagefuelplants": "Sabotage Fuel Plants",
    "kidnappopulation": "Kidnap Population",
    "suicidedrones": "Suicide Drones",
    "robprimitives": "Rob Primitives",
    "recruits": "Recruits",
    "attack": "Attackers",
    "defense": "Defenders",
    "flex": "Flexers",
    "big_flex": "Big Flexers",
    "engineers": "Engineers",
    "homes": "Homes",
    "mines": "Mines",
    "fuel_plants": "Fuel Plants",
    "hangars": "Hangars",
    "missile_silos": "Missile Silos",
    "drone_factories": "Drone Factories",
    "workshops": "Workshops",
    "planet_busters": "Planet Busters",
    "star_busters": "Star Busters",
    "galaxy_busters": "Galaxy Busters",
}

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


# Initialize flask app for the example
app = flask.Flask(__name__, static_folder='../build', static_url_path=None)
app.debug = True
app.config['SECRET_KEY'] = 'top secret'
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


# Initialize the flask-praetorian instance for the app
guard.init_app(app, User)

# Initialize a local database for the example
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ["SQLALCHEMY_DATABASE_URI"]
db.init_app(app)

# Initializes CORS so that the api_tool can talk to the example app
cors.init_app(app)

mail.init_app(app)

sock = Sock(app)

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
    print(accounts)
    for user in accounts:
        print("user:", user)
        if db.session.query(User).filter_by(username=user["username"]).count() < 1:
            print('Adding user:', user["username"])
            db.session.add(
                User(**user)
            )
    if db.session.query(User).filter_by(username='admin').count() < 1:
        db.session.add(User(
          username='admin',
          password=guard.hash_password('adminpass'),
          roles='operator,admin',
          kd_created=True,
		))
    # for i in range(0, 6):
    #     if db.session.query(User).filter_by(username=f'anewkd{i}').count() < 1:
    #         db.session.add(User(
    #         username=f'anewkd{i}',
    #         password=guard.hash_password(f'anewkd{i}'),
    #         roles='verified',
    #         # kd_id=str(i),
    #         # kd_created=True,
    #         # kd_death_date=None if i != 4 else "populated"
    #         ))
    db.session.commit()

def alive_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        kd_death_date = flask_praetorian.current_user().kd_death_date
        if kd_death_date not in (None, ""):
            return flask.jsonify({"message": "You can not do that because your kingdom is dead!"}), 400
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/api/adminlogin', methods=['POST'])
def admin_login():
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
    if "admin" not in user.roles:
        return flask.jsonify({"message": "Not authorized"})
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@app.route('/api/adminrefresh', methods=['POST'])
@flask_praetorian.roles_required('admin')
def admin_refresh():
    """
    Refreshes an existing JWT by creating a new one that is a copy of the old
    except that it has a refrehsed access expiration.
    .. example::
       $ curl http://localhost:5000/refresh -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    
    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200

@app.route('/api/refresh', methods=['POST'])
def refresh():
    """
    Refreshes an existing JWT by creating a new one that is a copy of the old
    except that it has a refrehsed access expiration.
    .. example::
       $ curl http://localhost:5000/refresh -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    
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
    _update_accounts()
    return flask.jsonify(create_response.text), 200

def _get_state():
    get_response = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/state',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    get_response_json = json.loads(get_response.text)
    return get_response_json

@app.route('/api/state', methods=["GET"])
# @flask_praetorian.roles_required('verified')
def get_state():
    """
    Get state
    """    
    get_response_json = _get_state()
    start_time = datetime.datetime.fromisoformat(get_response_json["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = BASE_PRIMITIVES_DEFENSE_PER_STAR(max(seconds_elapsed, 0))
    primitives_rob_per_drone = BASE_PRIMITIVES_ROB_PER_DRONE(max(seconds_elapsed, 0))
    return flask.jsonify({
        **get_response_json,
        "pretty_names": PRETTY_NAMES,
        "units": UNITS,
        "structures": {
            "pop_per_home": BASE_HOMES_CAPACITY,
            "income_per_mine": BASE_MINES_INCOME_PER_EPOCH,
            "fuel_per_fuel_plant": BASE_FUEL_PLANTS_INCOME_PER_EPOCH,
            "fuel_cap_per_fuel_plant": BASE_FUEL_PLANTS_CAPACITY,
            "hangar_capacity": BASE_HANGAR_CAPACITY,
            "drone_production_per_drone_plant": BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH,
            "missile_capacity_per_missile_silo": BASE_MISSILE_SILO_CAPACITY,
            "engineers_capacity_per_workshop": BASE_WORKSHOP_CAPACITY,
        },
        "income_per_pop": BASE_POP_INCOME_PER_EPOCH,
        "fuel_consumption_per_pop": BASE_POP_FUEL_CONSUMPTION_PER_EPOCH,
        "primitives_defense_per_star": primitives_defense_per_star,
        "primitives_rob_per_drone": primitives_rob_per_drone,
    }), 200

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
        data = ws.receive()
        json_data = json.loads(data)

        jwt = json_data.get('jwt', None)
        if jwt:
            id = guard.extract_jwt_token(jwt)["id"]
            query = db.session.query(User).filter_by(id=id).all()
            user = query[0]
            SOCK_HANDLERS[user.kd_id] = ws

        time.sleep(5)

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
    _update_accounts()
    
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
    _update_accounts()
    
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
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return (flask.jsonify(kd_info_parse), 200)

@app.route('/api/shields')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def shields():
    return {
        "desc": {
            "military": {
                "max": BASE_MILITARY_SHIELDS_MAX,
                "cost": BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT,
            },
            "spy": {
                "max": BASE_SPY_SHIELDS_MAX,
                "cost": BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT,
            },
            "spy_radar": {
                "max": BASE_SPY_RADAR_MAX,
                "cost": BASE_SPY_RADAR_COST_PER_LAND_PER_PCT,
            },
            "missiles": {
                "max": BASE_MISSILES_SHIELDS_MAX,
                "cost": BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT,
            },
        }
    }

def _validate_shields(req_values):

    if req_values.get("military", 0) > BASE_MILITARY_SHIELDS_MAX:
        return False, "Military shields must be at or below max shields value"
    if req_values.get("spy", 0) > BASE_SPY_SHIELDS_MAX:
        return False, "Spy shields must be at or below max shields value"
    if req_values.get("spy_radar", 0) > BASE_SPY_RADAR_MAX:
        return False, "Spy radar must be at or below max value"
    if req_values.get("missiles", 0) > BASE_MISSILES_SHIELDS_MAX:
        return False, "Missiles shields must be at or below max shields value"
    if any((value < 0 for value in req_values.values())):
        return False, "Shields value must be non-negative"

    return True, ""

@app.route('/api/shields', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def set_shields():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    req_values = {
        k: int(v or 0) / 100
        for k, v in req.items()
        if int(v or 0)
    }
    valid_shields, error_message = _validate_shields(req_values)
    if not valid_shields:
        return flask.jsonify({"message": error_message}), 400
    
    
    kd_id = flask_praetorian.current_user().kd_id
    kd_info = _get_kd_info(kd_id)

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
    
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)

def _get_kingdoms():
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdoms',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy = galaxies_inverted[kd_id]
    
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    empires_inverted, _, _, _ = _get_empires_inverted()
    
    kd_empire = empires_inverted[kd_id]
    
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["missile_history"]), 200)


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
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
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
            next_resolve["auto_spending"] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_AUTO_SPENDING_TIME_MULTIPLIER)).isoformat()
            payload["next_resolve"] = next_resolve
        else:
            total_funding = sum(kd_info_parse["funding"].values())
            next_resolve = kd_info_parse["next_resolve"]
            next_resolve["auto_spending"] = DATE_SENTINEL
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
    fuelless=False,
):
    int_fuelless = int(fuelless)
    raw_attack = sum([
        stat_map["offense"] * unit_dict.get(key, 0)
        for key, stat_map in UNITS.items() 
    ])
    attack_w_bonuses = raw_attack * (1 + BASE_GENERALS_BONUS(generals) + military_bonus + other_bonuses - (int_fuelless * BASE_FUELLESS_STRENGTH_REDUCTION))
    return math.floor(attack_w_bonuses)

def _calc_max_defense(
    unit_dict,
    military_bonus=0.25,
    other_bonuses=0.0,
    shields=0.10,
    fuelless=False,
):

    int_fuelless = int(fuelless)
    raw_defense = sum([
        stat_map["defense"] * unit_dict.get(key, 0)
        for key, stat_map in UNITS.items() 
    ])
    defense_w_bonuses = raw_defense * (1 + shields + military_bonus + other_bonuses - (int_fuelless * BASE_FUELLESS_STRENGTH_REDUCTION))
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
    max_hangar_capacity = math.floor(kd_info["structures"]["hangars"]) * BASE_HANGAR_CAPACITY
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

def _get_mobis_queue(kd_id):
    mobis_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    mobis_info_parse = json.loads(mobis_info.text)
    return mobis_info_parse["mobis"]

def _calc_recruit_time(is_conscription):
    return BASE_EPOCH_SECONDS * BASE_RECRUIT_TIME_MULTIPLIER * (1 - int(is_conscription) * BASE_CONSCRIPTION_TIME_REDUCTION)

def _get_units_adjusted_costs(state):
    is_unregulated = "Unregulated" in state["state"]["active_policies"]
    is_treatied = "Treatied" in state["state"]["active_policies"]
    
    cost_modifier = 1.0 - is_unregulated * BASE_UNREGULATED_COST_REDUCTION + is_treatied * BASE_TREATIED_COST_INCREASE
    units_desc = copy.deepcopy(UNITS)
    for unit, unit_dict in units_desc.items():
        if "cost" in unit_dict:
            unit_dict["cost"] = unit_dict["cost"] * cost_modifier

    return units_desc

def _get_mobis(kd_id):
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    mobis_info_parse = _get_mobis_queue(kd_id)
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
    len_queue = len(mobis_info_parse)

    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_conscription = "Conscription" in galaxy_policies["active_policies"]
    recruit_time = _calc_recruit_time(is_conscription)

    state = _get_state()
    units_adjusted_costs = _get_units_adjusted_costs(state)

    max_hangar_capacity, current_hangar_capacity = _calc_hangar_capacity(kd_info_parse, units)
    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units)
    payload = {
        'units': units,
        'maxes': maxes,
        'recruit_price': BASE_RECRUIT_COST,
        'recruit_time': recruit_time,
        'max_hangar_capacity': max_hangar_capacity,
        'current_hangar_capacity': current_hangar_capacity,
        'max_available_recruits': max_available_recruits,
        'current_available_recruits': current_available_recruits,
        'units_desc': units_adjusted_costs,
        'top_queue': top_queue,
        'len_queue': len_queue,
        }
    return payload

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
    payload = _get_mobis(kd_id)
    return (flask.jsonify(payload), 200)

def _validate_recruits(recruits_input, current_available_recruits):
    if recruits_input > current_available_recruits:
        return False
    if recruits_input <= 0:
        return False

    return True

@app.route('/api/recruits', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def recruits():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    recruits_input = int(req["recruitsInput"])
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    mobis_info_parse = _get_mobis_queue(kd_id)
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse

    start_time = datetime.datetime.now(datetime.timezone.utc)
    units = _calc_units(start_time, current_units, generals_units, mobis_units)

    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units)
    valid_recruits = _validate_recruits(recruits_input, current_available_recruits)
    if not valid_recruits:
        return (flask.jsonify({"message": 'Please enter valid recruits value'}), 400)

    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_conscription = "Conscription" in galaxy_policies["active_policies"]
    recruit_time = _calc_recruit_time(is_conscription)

    mobis_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=recruit_time)).isoformat()
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
    return (flask.jsonify({"message": "Successfully began recruiting", "status": "success"}), 200)

def _get_mobis_cost(mobis_request):
    state = _get_state()
    units_adjusted_costs = _get_units_adjusted_costs(state)
    mobis_cost = sum([
        units_adjusted_costs[k]['cost'] * units_value
        for k, units_value in mobis_request.items()
    ])
    return mobis_cost

def _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost):
    if sum(mobis_request.values()) > current_units["recruits"]:
        return False
    if sum(mobis_request.values()) == 0:
        return False
    if any((value < 0 for value in mobis_request.values())):
        return False
    if mobis_cost > kd_info_parse["money"]:
        return False
    if mobis_request.get("big_flex", 0) > 0 and "big_flexers" not in kd_info_parse["completed_projects"]:
        return False
    
    return True
    

@app.route('/api/mobis', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def train_mobis():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    current_units = kd_info_parse["units"]

    mobis_request = {
        k: int(v or 0)
        for k, v in req.items()
        if int(v or 0) != 0
    }
    mobis_cost = _get_mobis_cost(mobis_request)
    valid_mobis = _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost)
    if not valid_mobis:
        return (flask.jsonify({"message": 'Please enter valid training values'}), 400)

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
    return (flask.jsonify({"message": "Successfully began training specialists", "status": "success"}), 200)

def _validate_mobis_target(req_targets, kd_info_parse):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    if req_targets.get("big_flex", 0) > 0 and "big_flexers" not in kd_info_parse["completed_projects"]:
        return False, "You have not unlocked big_flexers"
    
    return True, ""

@app.route('/api/mobis/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_mobis():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("recruits_before_units", None) is not None:
        recruits_before_units = req["recruits_before_units"]
        payload = {'recruits_before_units': recruits_before_units}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if recruits_before_units:
            message = "Recruits will be trained before units during auto spending"
        else:
            message = "Recruits will be trained after units during auto spending"
        return (flask.jsonify({"message": message, "status": "success"}), 200)

    
    req_targets = {
        key: float(value or 0) / 100
        for key, value in req.get("targets", {}).items()
        if (value or 0) != 0
    }

    current_targets = kd_info_parse['units_target']
    new_targets = {
        **current_targets,
        **req_targets,
    }
    valid_targets, message = _validate_mobis_target(new_targets, kd_info_parse)
    if not valid_targets:
        return (flask.jsonify({"message": message}), 400)

    payload = {'units_target': new_targets}
    if req.get("max_recruits", "") != "":
        payload["max_recruits"] = int(req["max_recruits"])
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _calc_structures(
    start_time,
    current_structures,
    building_structures,
    epochs=[1, 2, 4, 8, 24]
):
    structures = {
        "current": {k: current_structures.get(k, 0) for k in STRUCTURES}
    }

    for hours in epochs:
        epoch_seconds = hours * BASE_EPOCH_SECONDS
        hour_structures = {
            key: 0
            for key in STRUCTURES
        }
        max_time = start_time + datetime.timedelta(seconds=epoch_seconds)
        for building_structure in building_structures:
            if datetime.datetime.fromisoformat(building_structure["time"]).astimezone(datetime.timezone.utc) < max_time:
                for key_structure in hour_structures.keys():
                    hour_structures[key_structure] += building_structure.get(key_structure, 0)

        structures[f"hour_{hours}"] = hour_structures
    return structures

def _get_structure_price(kd_info):
    return BASE_STRUCTURE_COST(int(kd_info["stars"]))

def _calc_available_structures(structure_price, kd_info, structures_info):
    total_structures = math.ceil(sum(structures_info["current"].values()) + sum(structures_info["hour_24"].values()))
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

def _get_structures_info(kd_id):
    
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    structures_info_parse = json.loads(structures_info.text)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    top_queue = sorted(
        structures_info_parse["structures"],
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(structures_info_parse["structures"])

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
        "len_queue": len_queue,
    }
    return payload


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
    payload = _get_structures_info(kd_id)

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
@alive_required
# @flask_praetorian.roles_required('verified')
def build_structures():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
        if int(v or 0) != 0
    }
    valid_structures = _validate_structures(structures_request, current_available_structures)
    if not valid_structures:
        return (flask.jsonify({"message": 'Please enter valid structures values'}), 400)

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
    return (flask.jsonify({"message": "Successfully began building structures", "status": "success"}), 200)

def _validate_structures_target(req_targets):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    
    return True, ""

@app.route('/api/structures/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_structures():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    
    req_targets = {
        key: float(value or 0) / 100
        for key, value in req.items()
        if (value or 0) != 0
    }

    current_targets = kd_info_parse['structures_target']
    new_targets = {
        **current_targets,
        **req_targets,
    }
    valid_targets, message = _validate_structures_target(new_targets)
    if not valid_targets:
        return (flask.jsonify({"message": message}), 400)

    payload = {'structures_target': new_targets}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _get_kd_info(kd_id):
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return kd_info_parse


def _get_max_kd_info(other_kd_id, kd_id, revealed_info, max=False, galaxies_inverted=None):
    if galaxies_inverted == None:
        galaxies_inverted, _ = _get_galaxies_inverted()
    always_allowed_keys = {"name", "race", "status", "coordinate"}
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{other_kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    if max:
        return kd_info_parse

    if other_kd_id in revealed_info["revealed_galaxymates"]:
        return kd_info_parse
    
    revealed_categories = revealed_info["revealed"].get(other_kd_id, {}).keys()
    kingdom_info_keys = always_allowed_keys
    for revealed_category in revealed_categories:
        kingdom_info_keys = kingdom_info_keys.union(allowed_keys[revealed_category])

    if galaxies_inverted[other_kd_id] == galaxies_inverted[kd_id]:
        kingdom_info_keys = kingdom_info_keys.union(allowed_keys["stats"])

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
    

    revealed_info = _get_revealed(kd_id)
    max_kd_info = _get_max_kd_info(other_kd_id, kd_id, revealed_info)

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
    
    galaxies_inverted, galaxy_info = _get_galaxies_inverted()
    current_galaxy_kingdoms = galaxy_info[galaxy]
    galaxy_kd_info = _get_max_kingdoms(kd_id, current_galaxy_kingdoms)  
    

    return (flask.jsonify(galaxy_kd_info), 200)

def _get_settle_queue(kd_id):
    settle_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    settle_info_parse = json.loads(settle_info.text)
    return settle_info_parse["settles"]

def _get_settle_price(kd_info, is_expansionist):
    return BASE_SETTLE_COST(int(kd_info["stars"])) * (1 - int(is_expansionist) * BASE_EXPANSIONIST_SETTLE_REDUCTION)

def _get_available_settle(kd_info, settle_info, is_expansionist):
    max_settle = BASE_MAX_SETTLE(int(kd_info["stars"]))
    current_settle = sum([
        int(settle_item["amount"])
        for settle_item in settle_info
    ])
    max_available_settle = max(max_settle - current_settle, 0)
    current_settle_cost = _get_settle_price(kd_info, is_expansionist)
    max_settle_cost = current_settle_cost * max_available_settle
    try:
        current_available_settle = min(
            math.floor((kd_info["money"] / max_settle_cost) * max_available_settle),
            max_available_settle,
        )
    except ZeroDivisionError:
        current_available_settle = 0
    return max_available_settle, current_available_settle

def _get_settle(kd_id):
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    settle_info = _get_settle_queue(kd_id)

    top_queue = sorted(
        settle_info,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(settle_info)

    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_expansionist = "Expansionist" in galaxy_policies["active_policies"]
    settle_price = _get_settle_price(kd_info_parse, is_expansionist)
    max_settle, available_settle = _get_available_settle(kd_info_parse, settle_info, is_expansionist)

    payload = {
        "settle_price": settle_price,
        "max_available_settle": max_settle,
        "current_available_settle": available_settle,
        "top_queue": top_queue,
        "len_queue": len_queue,
    }
    return payload


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
    payload = _get_settle(kd_id)
    return (flask.jsonify(payload), 200)

def _validate_settles(settle_input, kd_info, settle_info, is_expansionist):
    max_settle, available_settle = _get_available_settle(kd_info, settle_info, is_expansionist)
    if settle_input <= 0:
        return False
    if settle_input > available_settle:
        return False

    return True


@app.route('/api/settle', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def settle():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    settle_input = int(req["settleInput"])
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    settle_info = _get_settle_queue(kd_id)
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_expansionist = "Expansionist" in galaxy_policies["active_policies"]
    valid_settle = _validate_settles(settle_input, kd_info_parse, settle_info, is_expansionist)
    if not valid_settle:
        return (flask.jsonify({"message": 'Please enter valid settle value'}), 400)


    settle_price = _get_settle_price(kd_info_parse, is_expansionist)
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
    return (flask.jsonify({"message": "Successfully began settling", "status": "success"}), 200)

def _get_missiles_info(kd_id):
    missiles_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    missiles_info = _get_missiles_info(kd_id)
    top_queue = sorted(
        missiles_info,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(missiles_info)
    missiles_building = _get_missiles_building(missiles_info)

    current_missiles = kd_info_parse["missiles"]

    

    payload = {
        "current": current_missiles,
        "building": missiles_building,
        "build_time": BASE_MISSILE_TIME_MULTIPLER * BASE_EPOCH_SECONDS,
        "capacity": math.floor(kd_info_parse["structures"]["missile_silos"]) * BASE_MISSILE_SILO_CAPACITY,
        "desc": MISSILES,
        "top_queue": top_queue,
        "len_queue": len_queue,
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
    if missiles_request["star_busters"] > 0 and "star_busters" not in kd_info_parse["completed_projects"]:
        return False
    if missiles_request["galaxy_busters"] > 0 and "galaxy_busters" not in kd_info_parse["completed_projects"]:
        return False
    
    return True


@app.route('/api/missiles', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def build_missiles():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    
    missiles_info = _get_missiles_info(kd_id)
    missiles_building = _get_missiles_building(missiles_info)

    max_available_missiles = math.floor(kd_info_parse["structures"]["missile_silos"]) * BASE_MISSILE_SILO_CAPACITY

    missiles_request = {
        k: int(v or 0)
        for k, v in req.items()
    }
    valid_missiles = _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles)
    if not valid_missiles:
        return (flask.jsonify({"message": 'Please enter valid missiles values'}), 400)

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
    return (flask.jsonify({"message": "Successfully began building missiles", "status": "success"}), 200)

def _calc_workshop_capacity(kd_info, engineers_building):
    max_workshop_capacity = math.floor(kd_info["structures"]["workshops"]) * BASE_WORKSHOP_CAPACITY
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

def _get_engineers_queue(kd_id):
    engineers_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    engineers_info_parse = json.loads(engineers_info.text)
    return engineers_info_parse["engineers"]

def _get_engineers(kd_id):
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    engineers_info = _get_engineers_queue(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = _calc_workshop_capacity(kd_info_parse, engineers_building)
    max_available_engineers, current_available_engineers = _calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity)
    top_queue = sorted(
        engineers_info,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(engineers_info)

    payload = {
        'engineers_price': BASE_ENGINEER_COST,
        'max_workshop_capacity': max_workshop_capacity,
        'current_workshop_capacity': current_workshop_capacity,
        'max_available_engineers': max_available_engineers,
        'current_available_engineers': current_available_engineers,
        'current_engineers': kd_info_parse["units"]["engineers"],
        'engineers_building': engineers_building,
        "top_queue": top_queue,
        "len_queue": len_queue,
        }
    return payload

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
    payload = _get_engineers(kd_id)
    return (flask.jsonify(payload), 200)

def _validate_engineers(engineers_input, current_available_engineers):
    if engineers_input > current_available_engineers:
        return False
    if engineers_input <= 0:
        return False

    return True

@app.route('/api/engineers', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def train_engineers():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    engineers_input = int(req["engineersInput"])
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    engineers_info = _get_engineers_queue(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = _calc_workshop_capacity(kd_info_parse, engineers_building)
    max_available_engineers, current_available_engineers = _calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity)

    valid_engineers = _validate_engineers(engineers_input, current_available_engineers)
    if not valid_engineers:
        return (flask.jsonify({"message": 'Please enter valid recruits value'}), 400)

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
    return (flask.jsonify({"message": "Successfully began training engineers", "status": "success"}), 200)

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
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    max_bonuses = {
        project: project_dict.get("max_bonus", 0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
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

def _validate_projects_target(req_targets, kd_info_parse):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    if req_targets.get("spy_bonus", 0) > 0 and "drone_gadgets" not in kd_info_parse["completed_projects"]:
        return False
    
    return True, ""

@app.route('/api/projects/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_projects():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) is not None:
        payload = {'auto_assign_projects': req["enabled"]}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if req["enabled"]:
            message = "Auto assigning engineers enabled"
        else:
            message = "Auto assigning engineers disabled"
        return (flask.jsonify({"message": message, "status": "success"}), 200)

    
    req_targets = {
        key: float(value or 0) / 100
        for key, value in req.get("targets", {}).items()
        if (value or 0) != 0
    }

    current_targets = kd_info_parse['projects_target']
    new_targets = {
        **current_targets,
        **req_targets,
    }
    valid_targets, message = _validate_projects_target(new_targets, kd_info_parse)
    if not valid_targets:
        return (flask.jsonify({"message": message}), 400)

    payload = {'projects_target': new_targets}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _validate_assign_projects(req, kd_info_parse):
    engineers_assigned = sum(req["assign"].values())
    if engineers_assigned > kd_info_parse["units"]["engineers"]:
        return False
    if any(value < 0 for value in req["assign"].values()):
        return False
    if req.get("spy_bonus", 0) > 0 and "drone_gadgets" not in kd_info_parse["completed_projects"]:
        return False
    return True

def _validate_add_projects(req, available_engineers, kd_info_parse):
    engineers_added = sum(req["add"].values())
    if engineers_added > available_engineers:
        return False
    if any(value < 0 for value in req["add"].values()):
        return False
    if req.get("spy_bonus", 0) > 0 and "drone_gadgets" not in kd_info_parse["completed_projects"]:
        return False
    return True

@app.route('/api/projects', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
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
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
            return (flask.jsonify({"message": 'Please enter valid assign engineers value'}), 400)
        
        new_projects_assigned = {
            key: req["assign"].get(key, 0)
            for key in kd_info_parse["projects_assigned"]
        }
        
    elif "add" in req.keys():
        req["add"] = {k: int(v) for k, v in req["add"].items()}
        available_engineers = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())
        valid_add = _validate_add_projects(req, available_engineers, kd_info_parse)
        if not valid_add:
            return (flask.jsonify({"message": 'Please enter valid add engineers value'}), 400)
        
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
    return (flask.jsonify({"message": "Successfully updated project assignment", "status": "success"}), 200)

def _get_revealed(kd_id):
    revealed_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    revealed_info = _get_revealed(kd_id)
    return (flask.jsonify(revealed_info), 200)

def _get_shared(kd_id):
    shared_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    shared_info = _get_shared(kd_id)
    return (flask.jsonify(shared_info), 200)

@app.route('/api/shared', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
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
    

    kd_id = flask_praetorian.current_user().kd_id
    kingdoms = _get_kingdoms()
    
    shared_info = _get_shared(kd_id)

    new_shared = shared_info["shared_requests"].pop(accepted_kd)
    shared_info["shared"][accepted_kd] = new_shared

    shared_info_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(shared_info),
    )

    revealed_payload = {
        "new_revealed" : {
            accepted_kd: {
                new_shared["shared_stat"]: new_shared["time"],
            }
        }
    }
    revealed_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(revealed_payload),
    )
    
    try:
        ws = SOCK_HANDLERS[shared_info["shared"][accepted_kd]["shared_by"]]
        ws.send(json.dumps({
            "message": f"{kingdoms[kd_id]} accepted intel {shared_info['shared'][accepted_kd]['shared_stat']} for target {kingdoms[accepted_kd]}",
            "status": "info",
            "category": "Galaxy",
            "delay": 15000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return (flask.jsonify(shared_info_response.text), 200)

@app.route('/api/offershared', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
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
    kingdoms = _get_kingdoms()

    if (
        shared_kd == "" or shared_kd == None
        or shared_stat == "" or shared_stat == None
        or shared_to_kd == "" or shared_to_kd == None
    ):
        return flask.jsonify({"message": "The request selections are not complete"}), 400

    kd_id = flask_praetorian.current_user().kd_id
    

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

    
    try:
        ws = SOCK_HANDLERS[shared_to_kd]
        ws.send(json.dumps({
            "message": f"{kingdoms[shared_to_kd]} offered intel {shared_stat} for target {kingdoms[shared_kd]} with a cut of {cut:.1%}",
            "status": "info",
            "category": "Galaxy",
            "delay": 15000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return (flask.jsonify({"message": "Succesfully shared intel", "status": "success"}), 200)

def _get_pinned(kd_id):
    pinned_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    pinned_info = _get_pinned(kd_id)
    return (flask.jsonify(pinned_info["pinned"]), 200)

@app.route('/api/pinned', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def update_pinned():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    
    pinned_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(req),
    )
    return (flask.jsonify(pinned_patch_response.text), 200)


@app.route('/api/share/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def share_kd(share_to):
    kd_id = flask_praetorian.current_user().kd_id

    galaxies_inverted, _ = _get_galaxies_inverted()
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

    kd_revealed = _get_revealed(kd_id)
    share_to_revealed = _get_revealed(share_to)

    galaxies_inverted, _ = _get_galaxies_inverted()
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

def _get_max_kingdoms(kd_id, kingdoms):
    revealed_info = _get_revealed(kd_id)
    galaxies_inverted, _ = _get_galaxies_inverted()

    payload = {
        other_kd_id: _get_max_kd_info(other_kd_id, kd_id, revealed_info, galaxies_inverted=galaxies_inverted)
        for other_kd_id in kingdoms
    }
    return payload

@app.route('/api/kingdomsinfo', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
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
    payload = _get_max_kingdoms(kd_id, kingdoms)
    return (flask.jsonify(payload), 200)

@app.route('/api/revealrandomgalaxy', methods=['GET'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def reveal_random_galaxy():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if kd_info_parse["spy_attempts"] <= 0:
        return (flask.jsonify('You do not have any spy attempts remaining'), 400)

    revealed_info = _get_revealed(kd_id)

    empires_inverted, empires, _, _ = _get_empires_inverted()
    galaxies_inverted, galaxy_info = _get_galaxies_inverted()

    kd_empire = empires_inverted.get(kd_id, None)
    kd_galaxy = galaxies_inverted[kd_id]

    
    
    excluded_galaxies = list(revealed_info["galaxies"].keys())
    
    if kd_empire:
        
        excluded_galaxies.extend(empires[kd_empire]["galaxies"])
    else:
        excluded_galaxies.append(kd_galaxy)

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

    
    reveal_galaxy_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    

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

def _calc_coordinate_distance(
    coord_a,
    coord_b,
):
    direct_distance = abs(coord_a - coord_b)
    indirect_distance_1 = (coord_a) + (99 - coord_b)
    indirect_distance_2 = (coord_b) + (99 - coord_a)
    return min(direct_distance, indirect_distance_1, indirect_distance_2)

def _calc_generals_return_time(
    generals,
    return_multiplier,
    base_time,
    general_bonus=0,
    is_warlike=False,
    coordinate_distance=25,
):
    coordinate_distance_norm = coordinate_distance - 25
    coordinate_effect = coordinate_distance_norm * BASE_RETURN_TIME_PENALTY_PER_COORDINATE
    return_time_with_bonus = datetime.timedelta(seconds=BASE_EPOCH_SECONDS * return_multiplier) * (1 - general_bonus - int(is_warlike) * BASE_WARLIKE_RETURN_REDUCTION + coordinate_effect)
    
    return_times = [
        base_time + (return_time_with_bonus / i)
        for i in range(generals, 0, -1)
    ]
    return return_times

@app.route('/api/calculate/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
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
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }

    revealed = _get_revealed(kd_id)
    shared = _get_shared(kd_id)["shared"]
    max_target_kd_info = _get_max_kd_info(target_kd, kd_id, revealed)

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

    if "fuel" in max_target_kd_info:
        target_fuelless = max_target_kd_info["fuel"] <= 0
    else:
        target_fuelless = False

    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = _calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless
    )
    defense = _calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless
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
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=_calc_coordinate_distance(kd_info_parse["coordinate"], max_target_kd_info["coordinate"]),
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
        try:
            spoils_values["stars"] = max(spoils_values["stars"], BASE_ATTACK_MIN_STARS_GAIN * (1 - cut))
        except KeyError:
            pass
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
                try:
                    sharer_spoils_values["stars"] = max(sharer_spoils_values["stars"], BASE_ATTACK_MIN_STARS_GAIN * (cut))
                except KeyError:
                    pass
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

def _attack(req, kd_id, target_kd):
    
    attacker_raw_values = req["attackerValues"]

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }

    shared = _get_shared(kd_id)["shared"]
    galaxies_inverted, _ = _get_galaxies_inverted()
    target_kd_info = _get_kd_info(target_kd)
    if target_kd_info["status"].lower() == "dead":
        return (flask.jsonify({"message": "You can't attack this kingdom because they are dead!"}), 400)
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
        return kd_info_parse, {"message": attack_request_message}, 400

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

    attacker_fuelless = kd_info_parse["fuel"] <= 0
    target_fuelless = target_kd_info["fuel"] <= 0
    attack = _calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless,
    )
    defense = _calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless,
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
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=_calc_coordinate_distance(kd_info_parse["coordinate"], target_kd_info["coordinate"]),
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
        total_spoils["stars"] = max(total_spoils["stars"], BASE_ATTACK_MIN_STARS_GAIN)
        spoils_values = {
            key_spoil: math.floor(value_spoil * (1 - cut))
            for key_spoil, value_spoil in total_spoils.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        if sharer:
            sharer_spoils_values = {
                key_spoil: math.floor(value_spoil * cut)
                for key_spoil, value_spoil in total_spoils.items()
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
        else:
            sharer_spoils_values = {}

        units_destroyed = sum(defender_losses.values())
        attack_status = "success"
        attacker_message = (
            "Success! You have gained "
            + ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
            + f" and destroyed {units_destroyed} units."
            + " You have lost "
            + ', '.join([f"{value} {PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
        )
        defender_message = (
            f"Your kingdom was defeated in battle by {kd_info_parse['name']}. You have lost "
            + ', '.join([f"{value} {key}" for key, value in total_spoils.items()])
            + ' and '
            + ', '.join([f"{value} {PRETTY_NAMES.get(key, key)}" for key, value in defender_losses.items()])
        )
    else:
        attack_status = "failure"
        attacker_message = "Failure! You have lost " + ', '.join([f"{value} {PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
        defender_message = (
            f"Your kingdom successfully defended an attack by {kd_info_parse['name']}. You have lost "
            + ', '.join([f"{value} {PRETTY_NAMES.get(key, key)}" for key, value in defender_losses.items()])
        )
        spoils_values = {}
        sharer_spoils_values = {}
    

    kd_info_parse["units"] = new_home_attacker_units
    kd_info_parse["generals_out"] = kd_info_parse["generals_out"] + generals
    kd_info_parse["generals_available"] = kd_info_parse["generals_available"] - int(attacker_raw_values["generals"])
    kd_info_parse["next_resolve"]["generals"] = min(kd_info_parse["next_resolve"]["generals"], next_return_time)

    target_kd_info["units"] = new_defender_units
    for key_spoil, value_spoil in spoils_values.items():
        if key_spoil != "money":
            kd_info_parse[key_spoil] += value_spoil
        else:
            if kd_info_parse["auto_spending_enabled"]:
                pct_allocated = sum(kd_info_parse["auto_spending"].values())
                for key_spending, pct_spending in kd_info_parse["auto_spending"].items():
                    kd_info_parse["funding"][key_spending] += pct_spending * value_spoil
                kd_info_parse["money"] += value_spoil * (1 - pct_allocated)
            else:
                kd_info_parse["money"] += value_spoil
        target_kd_info[key_spoil] -= value_spoil

    target_kd_info["stars"] = max(target_kd_info["stars"], 0)
    for key_project, project_dict in PROJECTS.items():
        project_max_func = project_dict["max_points"]
        kd_info_parse["projects_max_points"][key_project] = project_max_func(kd_info_parse["stars"])
        target_kd_info["projects_max_points"][key_project] = project_max_func(target_kd_info["stars"])

    if sharer and sharer_spoils_values:
        sharer_kd_info = _get_kd_info(sharer)
        for key_spoil, value_spoil in sharer_spoils_values.items():
            if key_spoil != "money":
                sharer_kd_info[key_spoil] += value_spoil
            else:
                if sharer_kd_info["auto_spending_enabled"]:
                    pct_allocated = sum(sharer_kd_info["auto_spending"].values())
                    for key_spending, pct_spending in sharer_kd_info["auto_spending"].items():
                        sharer_kd_info["funding"][key_spending] += pct_spending * value_spoil
                    sharer_kd_info["money"] += value_spoil * (1 - pct_allocated)
                else:
                    sharer_kd_info["money"] += value_spoil
            sharer_kd_info[key_spoil] += value_spoil
            target_kd_info[key_spoil] -= value_spoil
        sharer_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{sharer}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(sharer_kd_info),
        )
        try:
            ws = SOCK_HANDLERS[sharer]
            ws.send(json.dumps({
                "message": f"You have gained {sharer_spoils_values['stars']} from an attack by your galaxymate {kd_info_parse['name']}",
                "status": "info",
                "category": "Galaxy",
                "delay": 15000,
                "update": [],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    
    if target_kd_info["stars"] <= 0:
        target_kd_info["status"] = "Dead"
        _mark_kingdom_death(target_kd)
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
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": defender_message,
            "status": "warning",
            "category": "Attack",
            "delay": 60000,
            "update": ["news", "galaxynews"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
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

    
    galaxies_inverted, galaxy_info = _get_galaxies_inverted()
    attacker_galaxy = galaxies_inverted[kd_id]
    kds_to_reveal = galaxy_info[attacker_galaxy]

    revealed_until = (time_now + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_REVEAL_DURATION_MULTIPLIER)).isoformat()
    payload = {
        "new_galaxies": {
            attacker_galaxy: revealed_until
        }
    }

    payload["new_revealed"] = {
        kd_id: {
            "stats": revealed_until,
        }
        for kd_id in kds_to_reveal
    }

    defender_galaxy = galaxies_inverted[target_kd]
    if attacker_galaxy != defender_galaxy:
        kds_revealed_to = galaxy_info[defender_galaxy]
        for kd_revealed_to in kds_revealed_to:
            reveal_galaxy_response = REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_revealed_to}/revealed',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps(payload),
            )
            kd_revealed_to_info = _get_kd_info(kd_revealed_to)
            if revealed_until < kd_revealed_to_info["next_resolve"]["revealed"]:
                kd_revealed_to_next_resolve = kd_revealed_to_info["next_resolve"]
                kd_revealed_to_next_resolve["revealed"] = revealed_until
                kd_revealed_to_patch_payload = {
                    "next_resolve": kd_revealed_to_next_resolve
                }
                REQUESTS_SESSION.patch(
                    os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_revealed_to}',
                    headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                    data=json.dumps(kd_revealed_to_patch_payload),
                )
            if kd_revealed_to != target_kd:
                try:
                    ws = SOCK_HANDLERS[kd_revealed_to]
                    ws.send(json.dumps({
                        "message": f"Your galaxymate {target_kd_info['name']} was attacked by {kd_info_parse['name']}. Galaxy {attacker_galaxy} will be revealed for {BASE_EPOCH_SECONDS * BASE_REVEAL_DURATION_MULTIPLIER / 3600} hours",
                        "status": "info",
                        "category": "Galaxy",
                        "delay": 15000,
                        "update": ["galaxynews"],
                    }))
                except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
                    pass

    attacker_galaxy_payload = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "to": target_kd,
    }
    defender_galaxy_payload = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "to": target_kd,
    }
    if attack > defense:
        attacker_galaxy_payload["news"] = f"Your kingdom {kd_info_parse['name']} successfully attacked {target_kd_info['name']} and gained {spoils_values['stars']} stars."
        if sharer_spoils_values:
            attacker_galaxy_payload["news"] += f" Your kingdom {sharer_kd_info['name']} provided intel and gained {sharer_spoils_values['stars']} stars."

        defender_galaxy_payload["news"] = f"Your kingdom {target_kd_info['name']} was defeated by {kd_info_parse['name']} and lost {total_spoils['stars']} stars."
    else:
        attacker_galaxy_payload["news"] = f"Your kingdom {kd_info_parse['name']} failed an attack on {target_kd_info['name']}."

        defender_galaxy_payload["news"] = f"Your kingdom {target_kd_info['name']} successfully defended an attack by {kd_info_parse['name']}."

    REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{attacker_galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(attacker_galaxy_payload),
    )
    REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{defender_galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(defender_galaxy_payload),
    )
    attack_results = {
        "status": attack_status,
        "message": attacker_message,
    }
    return kd_info_parse, attack_results, 200

@app.route('/api/attack/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def attack(target_kd):
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    _, payload, status_code = _attack(req, kd_id, target_kd)
    return (flask.jsonify(payload), status_code)

@app.route('/api/calculateprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_attack_primitives():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )

    state = _get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = BASE_PRIMITIVES_DEFENSE_PER_STAR(max(seconds_elapsed, 0))
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
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
    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = _calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless
    )
    stars = math.floor(attack / primitives_defense_per_star)
    money = stars * BASE_PRIMITIVES_MONEY_PER_STAR
    fuel = stars * BASE_PRIMITIVES_FUEL_PER_STAR
    pop = stars * BASE_PRIMITIVES_POPULATION_PER_STAR
    attacker_losses = _calc_losses(
        attacker_units,
        BASE_ATTACKER_UNIT_LOSS_RATE,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=25,
    )
    generals_strftime = ', '.join([
        str(general_return_time - time_now)
        for general_return_time in generals_return_times
    ])
    
    message = f"Your general(s) will return in: {generals_strftime}. \n"
    spoils_values = {
        "stars": stars,
        "money": money,
        "fuel": fuel,
        "population": pop,
    }
    if spoils_values:
        message += 'You will gain '
        message += ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
        message += '. \n'

    payload = {
        "attacker_offense": attack,
        "attacker_losses": attacker_losses,
        "attacker_unit_losses_rate": BASE_ATTACKER_UNIT_LOSS_RATE,
        "generals_return_times": generals_return_times,
        "message": message
    }

    return (flask.jsonify(payload), 200)

def _attack_primitives(req, kd_id):
    attacker_raw_values = req["attackerValues"]
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in PROJECTS.items()
        if "max_bonus" in project_dict
    }
    state = _get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = BASE_PRIMITIVES_DEFENSE_PER_STAR(max(seconds_elapsed, 0))

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return kd_info_parse, {"message": attack_request_message}, 400

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in UNITS and value != "")
    }

    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = _calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless,
    )
    attacker_losses = _calc_losses(
        attacker_units,
        BASE_ATTACKER_UNIT_LOSS_RATE,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        BASE_GENERALS_RETURN_TIME_MULTIPLIER,
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=25,
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

    stars = math.floor(attack / primitives_defense_per_star)
    money = stars * BASE_PRIMITIVES_MONEY_PER_STAR
    fuel = stars * BASE_PRIMITIVES_FUEL_PER_STAR
    pop = stars * BASE_PRIMITIVES_POPULATION_PER_STAR
    spoils_values = {
        "stars": stars,
        "money": money,
        "fuel": fuel,
        "population": pop,
    }

    attack_status = "success"
    attacker_message = (
        "You have attacked primitives and gained "
        + ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
        + ". You have lost "
        + ', '.join([f"{value} {PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
    )

    kd_info_parse["units"] = new_home_attacker_units
    kd_info_parse["generals_out"] = kd_info_parse["generals_out"] + generals
    kd_info_parse["generals_available"] = kd_info_parse["generals_available"] - int(attacker_raw_values["generals"])
    kd_info_parse["next_resolve"]["generals"] = min(kd_info_parse["next_resolve"]["generals"], next_return_time)

    for key_spoil, value_spoil in spoils_values.items():
        if key_spoil != "money":
            kd_info_parse[key_spoil] += value_spoil
        else:
            if kd_info_parse["auto_spending_enabled"]:
                pct_allocated = sum(kd_info_parse["auto_spending"].values())
                for key_spending, pct_spending in kd_info_parse["auto_spending"].items():
                    kd_info_parse["funding"][key_spending] += pct_spending * value_spoil
                kd_info_parse["money"] += value_spoil * (1 - pct_allocated)
            else:
                kd_info_parse["money"] += value_spoil

    for key_project, project_dict in PROJECTS.items():
        project_max_func = project_dict["max_points"]
        kd_info_parse["projects_max_points"][key_project] = project_max_func(kd_info_parse["stars"])

    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_info_parse, default=str),
    )
    kd_attack_history = {
        "time": time_now.isoformat(),
        "to": "",
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
    return kd_info_parse, attack_results, 200

@app.route('/api/attackprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def attack_primitives():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    _, attack_results, status_code = _attack_primitives(req, kd_id)
    return (flask.jsonify(attack_results), status_code)

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

def _validate_auto_attack_settings(req_settings):
    """Confirm that spending request is valid"""

    values = req_settings.values()
    if any((value < 0 for value in values)):
        return False, "Unit percents must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Unit percents must be less than 100%"
    
    return True, ""


@app.route('/api/attackprimitives/auto', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def auto_attack_primitives():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) != None:
        if kd_info_parse["auto_attack_settings"].get("pure", 0) == 0 and kd_info_parse["auto_attack_settings"].get("flex", 0) == 0:
            return (flask.jsonify({"message": "Could not enable auto attack. You must first specify the percent of units to send"}), 400)
        enabled = req["enabled"]
        payload = {'auto_attack_enabled': enabled}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if enabled:
            message = "Enabled auto attacking primitives"
        else:
            message = "Disabled auto attacking primitives"
        return (flask.jsonify({"message": message, "status": "success"}), 200)
    
    req_settings = {
        "pure": float(
            req.get("pure", kd_info_parse["auto_attack_settings"].get("pure", 0)) or 0
        ) / 100,
        "flex": float(
            req.get("flex", kd_info_parse["auto_attack_settings"].get("flex", 0)) or 0
        ) / 100,
    }

    current_settings = kd_info_parse['auto_attack_settings']
    new_settings = {
        **current_settings,
        **req_settings,
    }
    valid_settings, message = _validate_auto_attack_settings(new_settings)
    if not valid_settings:
        return (flask.jsonify({"message": message}), 400)

    payload = {'auto_attack_settings': new_settings}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated auto attack settings", "status": "success"}), 200)


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
@alive_required
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
    
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = _get_revealed(kd_id)
    max_target_kd_info = _get_max_kd_info(target_kd, kd_id, revealed)
    
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
    if operation == "siphonfunds":
        siphon_damage = math.floor(drones * BASE_DRONES_SIPHON_PER_DRONE)
        siphon_seconds = BASE_DRONES_SIPHON_TIME_MULTIPLIER * BASE_EPOCH_SECONDS
        siphon_hours = siphon_seconds / 3600
        message = f"If successful, you will siphon up to {siphon_damage} money over the next {siphon_hours} hours."
    if operation == "bombhomes":
        if "structures" in max_target_kd_info.keys():
            homes_damage = min(math.floor(max_target_kd_info["structures"]["homes"] * BASE_DRONES_MAX_HOME_DAMAGE), math.floor(drones / BASE_DRONES_PER_HOME_DAMAGE))
            message = f"If successful, you will destroy {homes_damage} homes."
        else:
            homes_damage = math.floor(drones / BASE_DRONES_PER_HOME_DAMAGE)
            message = f"If successful, you will destroy up to {homes_damage} homes."
    if operation == "sabotagefuelplants":
        if "structures" in max_target_kd_info.keys():
            fuel_plant_damage = min(math.floor(max_target_kd_info["structures"]["fuel_plants"] * BASE_DRONES_MAX_FUEL_PLANT_DAMAGE), math.floor(drones / BASE_DRONES_PER_FUEL_PLANT_DAMAGE))
            message = f"If successful, you will destroy {fuel_plant_damage} fuel plants."
        else:
            fuel_plant_damage = math.floor(drones / BASE_DRONES_PER_FUEL_PLANT_DAMAGE)
            message = f"If successful, you will destroy up to {fuel_plant_damage} fuel plants."
    if operation == "kidnappopulation":
        if "population" in max_target_kd_info.keys():
            kidnap_damage = min(math.floor(max_target_kd_info["population"] * BASE_DRONES_MAX_KIDNAP_DAMAGE), math.floor(drones / BASE_DRONES_PER_KIDNAP))
            kidnap_return = math.floor(kidnap_damage * BASE_KIDNAP_RETURN_RATE)
            message = f"If successful, you will kidnap {kidnap_damage} civilians. {kidnap_return} civilians will join your population."
        else:
            kidnap_damage = math.floor(drones / BASE_DRONES_PER_KIDNAP)
            kidnap_return = math.floor(kidnap_damage * BASE_KIDNAP_RETURN_RATE)
            message = f"If successful, you will kidnap up to {kidnap_damage} civilians. Up to {kidnap_return} civilians will join your population."
    if operation == "suicidedrones":
        fuel_damage = drones * 5
        if "fuel" in max_target_kd_info.keys():
            fuel_damage = min(fuel_damage, max_target_kd_info["fuel"])
            message = f"You will destroy {fuel_damage} fuel."
        else:
            message = f"You will destroy up to {fuel_damage} fuel."

    payload = {
        "message": message,
        "stars_defense": stars_defense,
        "drones_defense": drones_defense,
        "total_defense": stars_defense + drones_defense,
    }
    return (flask.jsonify(payload), 200)
    
def _spy(req, kd_id, target_kd):
    
    drones = int(req["drones"])
    shielded = req["shielded"]
    operation = req["operation"]

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return kd_info_parse, {"message": message}, 400, False
    
    revealed = _get_revealed(kd_id)["revealed"]
    max_target_kd_info = _get_kd_info(target_kd)
    if max_target_kd_info["status"].lower() == "dead":
        return (flask.jsonify({"message": "You can't attack this kingdom because they are dead!"}), 400)
    
    defender_drones = max_target_kd_info["drones"]
    defender_stars = max_target_kd_info["stars"]
    defender_shields = max_target_kd_info["shields"]["spy"]
    
    spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
        drones,
        defender_drones,
        defender_stars,
        defender_shields
    )
    
    success_losses, failure_losses = _calculate_spy_losses(drones, shielded)

    roll = random.uniform(0, 1)
    spy_radar_roll = random.uniform(0, 1)
    success = roll < spy_probability
    spy_radar_success = spy_radar_roll < max_target_kd_info["shields"]["spy_radar"]

    time_now = datetime.datetime.now(datetime.timezone.utc)
    revealed_until = None
    siphon_damage = None
    siphon_until = None
    homes_damage = None
    fuel_plant_damage = None
    kidnap_damage = None
    kidnap_return = None
    fuel_damage = None
    revealed = False

    if operation == "suicidedrones":
        burnable_fuel = max_target_kd_info["fuel"] - BASE_NEGATIVE_FUEL_CAP(max_target_kd_info["stars"])
        fuel_damage = min(burnable_fuel, drones * BASE_DRONES_SUICIDE_FUEL_DAMAGE)
        losses = drones
        status = "success"
        message = f"You have destroyed {fuel_damage} fuel. You have lost {losses} drones"
        target_message = f"Enemy drones have destroyed {fuel_damage} fuel"
    else:
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
                target_message = "You were infiltrated by drones on a spy operation."
            
            if operation == "siphonfunds":
                siphon_damage = drones * BASE_DRONES_SIPHON_PER_DRONE
                siphon_seconds = BASE_DRONES_SIPHON_TIME_MULTIPLIER * BASE_EPOCH_SECONDS
                siphon_hours = siphon_seconds / 3600
                siphon_until = time_now + datetime.timedelta(seconds=siphon_seconds)
                message = f"Success! Your drones will siphon up to {siphon_damage} money over the next {siphon_hours} hours. You have lost {success_losses} drones."
                target_message = f"Enemy drones have begun siphoning up to {siphon_damage} money over the next {siphon_hours} hours."
            if operation == "bombhomes":
                homes_damage = min(math.floor(max_target_kd_info["structures"]["homes"] * BASE_DRONES_MAX_HOME_DAMAGE), math.floor(drones / BASE_DRONES_PER_HOME_DAMAGE))
                message = f"Success! You have destroyed {homes_damage} homes. You have lost {success_losses} drones."
                target_message = f"Enemy drones have destroyed {homes_damage} homes."
            if operation == "sabotagefuelplants":
                fuel_plant_damage = min(math.floor(max_target_kd_info["structures"]["fuel_plants"] * BASE_DRONES_MAX_FUEL_PLANT_DAMAGE), math.floor(drones / BASE_DRONES_PER_FUEL_PLANT_DAMAGE))
                message = f"Success! You have destroyed {fuel_plant_damage} fuel plants. You have lost {success_losses} drones."
                target_message = f"Enemy drones have destroyed {fuel_plant_damage} fuel plants."
            if operation == "kidnappopulation":
                kidnap_damage = min(math.floor(max_target_kd_info["population"] * BASE_DRONES_MAX_KIDNAP_DAMAGE), math.floor(drones / BASE_DRONES_PER_KIDNAP))
                kidnap_return = math.floor(kidnap_damage * BASE_KIDNAP_RETURN_RATE)
                message = f"Success! You have kidnapped {kidnap_damage} civilians. {kidnap_return} civilians have joined your population. You have lost {success_losses} drones."
                target_message = f"Enemy drones have kidnapped {kidnap_damage} civilians."

            losses = success_losses
        else:
            status = "failure"
            message = f"Failure! You have lost {failure_losses} drones."
            if operation in REVEAL_OPERATIONS:
                target_message = f"{kd_info_parse['name']} failed a spy operation on you."
            else:
                target_message = f"{kd_info_parse['name']} failed an aggressive spy operation on you."
            losses = failure_losses
            if operation in AGGRO_OPERATIONS:
                revealed = True

    if spy_radar_success and not revealed:
        revealed = True
        target_message += f" Your spy radar has revealed the operation came from {kd_info_parse['name']}."

    kd_patch_payload = {
        "drones": kd_info_parse["drones"] - losses,
        "spy_attempts": kd_info_parse["spy_attempts"] - 1
    }
    if kidnap_return:
        kd_patch_payload["population"] = kd_info_parse["population"] + kidnap_return
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

    target_patch_payload = {}
    if siphon_damage:
        siphons_out_payload = {
            "new_siphons": {
                "from": kd_id,
                "time": siphon_until,
                "siphon": siphon_damage
            }
        }
        siphons_out_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/siphonsout',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(siphons_out_payload, default=str),
        )
    if homes_damage:
        target_patch_payload["structures"] = {
            **max_target_kd_info["structures"],
            "homes": max_target_kd_info["structures"]["homes"] - homes_damage
        }
    if fuel_plant_damage:
        target_patch_payload["structures"] = {
            **max_target_kd_info["structures"],
            "fuel_plants": max_target_kd_info["structures"]["fuel_plants"] - fuel_plant_damage
        }
    if kidnap_damage:
        target_patch_payload["population"] = max_target_kd_info["population"] - kidnap_damage
    if fuel_damage:
        target_patch_payload["fuel"] = max_target_kd_info["fuel"] - fuel_damage


    if revealed:
        revealed_until = (time_now + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_REVEAL_DURATION_MULTIPLIER)).isoformat()
        if revealed_until < max_target_kd_info["next_resolve"]["revealed"]:
            next_resolve = max_target_kd_info["next_resolve"]
            next_resolve["revealed"] = min(next_resolve["revealed"], revealed_until)
            target_patch_payload["next_resolve"] = next_resolve

        revealed_payload = {
            "new_revealed": {
                kd_id: {
                    "stats": revealed_until,
                    "drones": revealed_until,
                }
            }
        }
        reveal_galaxy_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/revealed',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(revealed_payload),
        )
        target_message += f" Their kingdom 'stats' and 'drones' will be revealed for {BASE_EPOCH_SECONDS * BASE_REVEAL_DURATION_MULTIPLIER / 3600} hours"

    if target_patch_payload:
        target_kd_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(target_patch_payload, default=str),
        )
    history_payload = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "operation": PRETTY_NAMES.get(operation, operation),
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
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": target_message,
            "status": "warning",
            "category": "Spy",
            "delay": 15000,
            "update": ["news"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass

    new_kd_info = {
        **kd_info_parse,
        **kd_patch_payload,
    }
    payload = {
        "status": status,
        "message": message,
    }
    return new_kd_info, payload, 200, success
        
@app.route('/api/spy/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def spy(target_kd):
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)
    if not req["operation"]:
        return (flask.jsonify({"message": "You must select an operation"}), 400)
    
    _, payload, status_code, success = _spy(req, kd_id, target_kd)

    return (flask.jsonify(payload), status_code)

def _rob_primitives(req, kd_id):
    drones = int(req["drones"])
    shielded = req["shielded"]
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    state = _get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_rob_per_drone = BASE_PRIMITIVES_ROB_PER_DRONE(max(seconds_elapsed, 0))

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return kd_info_parse, {"message": message}, 400

    success_losses, _ = _calculate_spy_losses(drones, shielded)

    status = "success"
    rob = math.floor(drones * primitives_rob_per_drone)
    message = f"You have robbed {rob} money from primitives. You have lost {success_losses} drones."
    

    losses = success_losses

    if kd_info_parse["auto_spending_enabled"]:
        pct_allocated = sum(kd_info_parse["auto_spending"].values())
        new_funding = kd_info_parse["funding"]
        for key_spending, pct_spending in kd_info_parse["auto_spending"].items():
            new_funding[key_spending] += pct_spending * rob
        new_money = rob * (1 - pct_allocated)
    else:
        new_funding = kd_info_parse["funding"]
        new_money = rob
    kd_patch_payload = {
        "drones": kd_info_parse["drones"] - losses,
        "spy_attempts": kd_info_parse["spy_attempts"] - 1,
        "money": kd_info_parse["money"] + new_money,
        "funding": new_funding,
    }
    if shielded:
        kd_patch_payload["fuel"] = kd_info_parse["fuel"] - drones
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload, default=str),
    )

    time_now = datetime.datetime.now(datetime.timezone.utc)
    history_payload = {
        "time": time_now.isoformat(),
        "to": "",
        "operation": PRETTY_NAMES.get("robprimitives", "robprimitives"),
        "news": message,
    }
    kd_spy_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(history_payload, default=str),
    )

    new_kd_info = {
        **kd_info_parse,
        **kd_patch_payload,
    }
    payload = {
        "status": status,
        "message": message,
    }
    return new_kd_info, payload, 200

@app.route('/api/robprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def rob_primitives():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    _, payload, status_code = _rob_primitives(req, kd_id)
    return (flask.jsonify(payload), status_code)

def _validate_auto_rob_settings(req_settings):
    """Confirm that spending request is valid"""

    if req_settings["drones"] < 0:
        return False, "Drones percent must be greater than 0"
    if req_settings["drones"] > 1:
        return False, "Drones percent must be less than 100%"
    if req_settings["keep"] < 0:
        return False, "Keep spy attempts must be greater than 0"
    if req_settings["keep"] >= 10:
        return False, "Keep spy attempts must be less than 10"
    
    return True, ""


@app.route('/api/robprimitives/auto', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def auto_rob_primitives():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) != None:
        if kd_info_parse["auto_rob_settings"].get("drones", 0) == 0:
            return (flask.jsonify({"message": "Could not enable auto robs. You must first specify the percent of drones to send"}), 400)
        enabled = req["enabled"]
        payload = {'auto_rob_enabled': enabled}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if enabled:
            message = "Enabled auto robbing primitives"
        else:
            message = "Disabled auto robbing primitives"
        return (flask.jsonify({"message": message, "status": "success"}), 200)
    
    req_settings = {
        "drones": float(
            req.get("drones", kd_info_parse["auto_rob_settings"].get("drones", 0)) or 0
        ) / 100,
        "keep": int(
            req.get("keep", kd_info_parse["auto_rob_settings"].get("keep", 0)) or 0
        ),
        "shielded": bool(
            req.get("shielded", kd_info_parse["auto_rob_settings"].get("shielded", False)) or False
        ),
    }

    current_settings = kd_info_parse['auto_rob_settings']
    new_settings = {
        **current_settings,
        **req_settings,
    }
    valid_settings, message = _validate_auto_rob_settings(new_settings)
    if not valid_settings:
        return (flask.jsonify({"message": message}), 400)

    payload = {'auto_rob_settings': new_settings}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated auto attack settings", "status": "success"}), 200)

def _validate_schedule_attack(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if options["generals"] < 1 or options["generals"] > 4:
        return False, "Generals must be between 1 and 4"
    if options["pure_offense"] < 0 or options["pure_offense"] > 1:
        return False, "Pure offense must be between 0% and 100%"
    if options["flex_offense"] < 0 or options["flex_offense"] > 1:
        return False, "Pure offense must be between 0% and 100%"
    if options["target"] == kd_id:
        return False, "You can not schedule an attack against yourself"
    
    return True, ""

def _schedule_attack(
    id,
    time,
    options,
    kd_info,
):
    options["generals"] = int(options["generals"] or 0)
    options["pure_offense"] = float(options["pure_offense"] or 0) / 100
    options["flex_offense"] = float(options["flex_offense"] or 0) / 100
    valid_schedule, message = _validate_schedule_attack(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message

    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "attack",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_attackprimitives(
    options,
):
    if options["generals"] < 1 or options["generals"] > 4:
        return False, "Generals must be between 1 and 4"
    if options["pure_offense"] < 0 or options["pure_offense"] > 1:
        return False, "Pure offense must be between 0% and 100%"
    if options["flex_offense"] < 0 or options["flex_offense"] > 1:
        return False, "Flex offense must be between 0% and 100%"
    
    return True, ""

def _schedule_attackprimitives(
    id,
    time,
    options,
    kd_info,
):
    options["generals"] = int(options["generals"] or 0)
    options["pure_offense"] = float(options["pure_offense"] or 0) / 100
    options["flex_offense"] = float(options["flex_offense"] or 0) / 100
    valid_schedule, message = _validate_schedule_attackprimitives(options)
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "attackprimitives",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_intelspy(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if options["operation"] is None:
        return False, "Operation must be selected"
    if options["max_tries"] < 1 or options["max_tries"] > 10:
        return False, "Max tries must be between 1 and 10"
    if options["drones_pct"] < 0 or options["drones_pct"] > 1:
        return False, "Drones percent must be between 0% and 100%"
    if options["target"] == kd_id:
        return False, "You can not schedule a spy attempt against yourself"
    if options["operation"] not in REVEAL_OPERATIONS:
        return False, "Intel schedules must be intel operations"
    
    return True, ""

def _schedule_intelspy(
    id,
    time,
    options,
    kd_info,
):
    options["max_tries"] = int(options["max_tries"] or 0)
    options["drones_pct"] = float(options["drones_pct"] or 0) / 100
    valid_schedule, message = _validate_schedule_intelspy(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "intelspy",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_aggressivespy(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if options["operation"] is None:
        return False, "Operation must be selected"
    if options["attempts"] < 1 or options["attempts"] > 10:
        return False, "Attempts must be between 1 and 10"
    if options["drones_pct"] <= 0 or options["drones_pct"] > 1:
        return False, "Drones percent must be between 0% and 100%"
    if options["target"] == kd_id:
        return False, "You can not schedule a spy attempt against yourself"
    if options["operation"] not in AGGRO_OPERATIONS:
        return False, "Aggressive schedules must be aggressive operations"
    
    return True, ""

def _schedule_aggressivespy(
    id,
    time,
    options,
    kd_info,
):
    options["attempts"] = int(options["attempts"] or 0)
    options["drones_pct"] = float(options["drones_pct"] or 0) / 100
    valid_schedule, message = _validate_schedule_aggressivespy(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "aggressivespy",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_missiles(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if (options["planet_busters"] + options["star_busters"] + options["galaxy_busters"]) <= 0:
        return False, "Missiles amount must be greater than 0"
    if options["planet_busters"] < 0:
        return False, "Missiles amount must be greater than 0"
    if options["star_busters"] < 0:
        return False, "Missiles amount must be greater than 0"
    if options["galaxy_busters"] < 0:
        return False, "Missiles amount must be greater than 0"
    if options["target"] == kd_id:
        return False, "You can not schedule missiles against yourself"
    
    return True, ""

def _schedule_missiles(
    id,
    time,
    options,
    kd_info,
):
    options["planet_busters"] = int(options["planet_busters"] or 0)
    options["star_busters"] = int(options["star_busters"] or 0)
    options["galaxy_busters"] = int(options["galaxy_busters"] or 0)
    valid_schedule, message = _validate_schedule_missiles(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "missiles",
        "options": options,
    }
    return True, new_schedule, ""
    

@app.route('/api/schedule', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def add_schedule():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    kd_info = _get_kd_info(kd_id)

    schedule_type = req.get("type")
    schedule_time = datetime.datetime.fromisoformat(req["time"].replace('Z', '+00:00')).isoformat()
    schedule_options = req.get("options", {})
    schedule_id = uuid.uuid4()
    
    state = _get_state()

    if schedule_time < state["state"]["game_start"] or schedule_time > state["state"]["game_end"]:
        return flask.jsonify({"message": "Scheduled time occurs outside of game duration"}), 400
    
    if len(kd_info["schedule"]) >= 10:
        return flask.jsonify({"message": "You can not schedule more than 10 actions"}), 400

    handler_funcs = {
        "attack": _schedule_attack,
        "attackprimitives": _schedule_attackprimitives,
        "intelspy": _schedule_intelspy,
        "aggressivespy": _schedule_aggressivespy,
        "missiles": _schedule_missiles,
    }
    scheduled, new_schedule, message = handler_funcs[schedule_type](
        id=schedule_id,
        time=schedule_time,
        options=schedule_options,
        kd_info=kd_info,
    )
    if not scheduled:
        return flask.jsonify({"message": message}), 400
    
    schedule_payload = kd_info["schedule"]
    schedule_payload.append(new_schedule)
    schedule_payload_sorted = sorted(schedule_payload, key=lambda item: item["time"])

    kd_payload = {
        "schedule": schedule_payload_sorted,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload, default=str),
    )

    return (flask.jsonify({"message": "Successfully scheduled", "status": "success"}), 200)

@app.route('/api/schedule/cancel', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def cancel_schedule():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    kd_info = _get_kd_info(kd_id)

    schedule_id = req.get("id")

    new_schedule = [
        item
        for item in kd_info["schedule"]
        if item["id"] != schedule_id
    ]
    kd_payload = {
        "schedule": new_schedule,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload, default=str),
    )
    return (flask.jsonify({"message": "Cancelled scheduled action", "status": "success"}), 200)


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
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_missiles(target_kd):
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
    
    revealed = _get_revealed(kd_id)
    max_target_kd_info = _get_max_kd_info(target_kd, kd_id, revealed)

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
    
def _launch_missiles(req, kd_id, target_kd):

    attacker_raw_values = req["attackerValues"]
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
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
        return kd_info_parse, {"message": message}, 400
    
    max_target_kd_info = _get_kd_info(target_kd)
    defender_shields = max_target_kd_info["shields"]["missiles"]
    if max_target_kd_info["status"].lower() == "dead":
        return (flask.jsonify({"message": "You can't attack this kingdom because they are dead!"}), 400)
    
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

    target_stars = max_target_kd_info["stars"] - missile_damage["stars_damage"]
    target_pop = max_target_kd_info["population"] - missile_damage["pop_damage"]
    defender_patch_payload = {
        "stars": target_stars,
        "population": target_pop,
        "fuel": max_target_kd_info["fuel"] - missile_damage["fuel_damage"],
    }
    if target_stars <= 0 or target_pop <= 0:
        defender_patch_payload["status"] = "Dead"
        _mark_kingdom_death(target_kd)
    defender_patch_payload["stars"] = max(defender_patch_payload["stars"], 0)
    defender_patch_payload["projects_max_points"] = {}
    for key_project, project_dict in PROJECTS.items():
        project_max_func = project_dict["max_points"]
        defender_patch_payload["projects_max_points"][key_project] = project_max_func(max_target_kd_info["stars"])
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
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": defender_message,
            "status": "warning",
            "category": "Missiles",
            "delay": 30000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass

    new_kd_info = {
        **kd_info_parse,
        **kd_patch_payload,
    }
    payload = {
        "message": message,
    }
    return new_kd_info, payload, 200

@app.route('/api/launchmissiles/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def launch_missiles(target_kd):
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)
    
    _, payload, status_code = _launch_missiles(req, kd_id, target_kd)
    return (flask.jsonify(payload), status_code)

def _get_galaxy_politics(kd_id, galaxy_id=None):
    if not galaxy_id:
        galaxies_inverted, _ = _get_galaxies_inverted()
        galaxy_id = galaxies_inverted[kd_id]
    galaxy_politics_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    galaxy_politics_info_parse = json.loads(galaxy_politics_info.text)
    return galaxy_politics_info_parse, galaxy_id

@app.route('/api/galaxypolitics', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy_politics():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, _ = _get_galaxy_politics(kd_id)
    payload = {
        **galaxy_votes,
        "desc": GALAXY_POLICIES,
    }
    return (flask.jsonify(payload), 200)

@app.route('/api/galaxypolitics/leader', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_leader():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, galaxy_id = _get_galaxy_politics(kd_id)

    galaxy_votes["votes"]["leader"][kd_id] = req["selected"]
    patch_payload = {
        "votes": galaxy_votes["votes"],
    }
    leader_votes = collections.defaultdict(int)
    for leader in galaxy_votes["votes"]["leader"].values():
        leader_votes[leader] += 1

    current_leader = galaxy_votes["leader"]
    most_votes = max(leader_votes.values())
    kds_with_most_votes = [
        k
        for k, v in leader_votes.items()
        if v == most_votes
    ]
    if len(kds_with_most_votes) == 1 and (kds_with_most_votes[0] != current_leader):
        patch_payload["leader"] = kds_with_most_votes[0]
    
    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(patch_payload)
    )

    return (flask.jsonify(galaxy_votes), 200)

@app.route('/api/galaxypolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_policies():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, galaxy_id = _get_galaxy_politics(kd_id)

    galaxy_votes["votes"][req["policy"]][kd_id] = req["option"].split('_')[-1]
    patch_payload = {
        "votes": galaxy_votes["votes"],
    }
    policy_votes = collections.defaultdict(int)
    for policy in galaxy_votes["votes"][req["policy"]].values():
        policy_votes[policy] += 1

    current_option_winner = galaxy_votes[f"{req['policy']}_winner"]
    most_votes = max(policy_votes.values())
    policies_with_most_votes = [
        k
        for k, v in policy_votes.items()
        if v == most_votes
    ]
    if len(policies_with_most_votes) == 1 and (policies_with_most_votes[0] != current_option_winner):
        patch_payload[f"{req['policy']}_winner"] = policies_with_most_votes[0]
        option_names = [option["name"] for option in GALAXY_POLICIES[req["policy"]]["options"].values()]
        new_option_name = GALAXY_POLICIES[req["policy"]]["options"][policies_with_most_votes[0]]["name"]
        new_active_policies = [policy for policy in galaxy_votes["active_policies"] if policy not in option_names] + [new_option_name]
        patch_payload["active_policies"] = new_active_policies

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(patch_payload)
    )

    return (flask.jsonify(galaxy_votes), 200)

def _validate_buy_votes(
    kd_info,
    votes,
):
    if votes <= 0:
        return False, "Votes must be greater than 0"
    votes_cost = votes * BASE_VOTES_COST
    if votes_cost > kd_info["money"]:
        return False, "Not enough money"
    
    return True, ""

@app.route('/api/votes', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def buy_votes():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = _get_kd_info(kd_id)
    
    votes = int(req["votes"])
    votes_cost = votes * BASE_VOTES_COST

    valid_votes, message = _validate_buy_votes(kd_info, votes)
    if not valid_votes:
        return flask.jsonify({"message": message}), 400
    
    kd_patch_payload = {
        "money": kd_info["money"] - votes_cost,
        "votes": kd_info["votes"] + votes,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload)
    )

    return (flask.jsonify({"message": "Bought votes", "status": "success"}), 200)

def _get_universe_politics():
    universe_politics_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universevotes',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    universe_politics_info_parse = json.loads(universe_politics_info.text)
    return universe_politics_info_parse


@app.route('/api/universepolitics', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def universe_politics():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    
    universe_politics = _get_universe_politics()
    kd_payload = {
        "policy_1": {
            "option_1": "",
            "option_2": "",
        },
        "policy_2": {
            "option_1": "",
            "option_2": "",
        },
    }
    for policy_name, policy_options in universe_politics["votes"].items():
        for option_name, option_votes in policy_options.items():
            for vote_kd_id, votes_cast in option_votes.items():
                if kd_id == vote_kd_id:
                    kd_payload[policy_name][option_name] = votes_cast
    payload = {
        **kd_payload,
        "desc": UNIVERSE_POLICIES,
    }
    return (flask.jsonify(payload), 200)

def _validate_cast_votes(
    kd_info,
    votes,
):
    if votes <= 0:
        return False, "Votes must be greater than 0"
    if votes > kd_info["votes"]:
        return False, "Not enough votes available"
    
    return True, ""

@app.route('/api/universepolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def universe_policies():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = _get_kd_info(kd_id)
    
    votes = int(req["votes"])
    policy = req["policy"]
    option = req["option"]

    valid_votes, message = _validate_cast_votes(kd_info, votes)
    if not valid_votes:
        return flask.jsonify({"message": message}), 400
    
    universe_politics = _get_universe_politics()

    kd_patch_payload = {
        "votes": kd_info["votes"] - votes,
    }

    try:
        universe_politics["votes"][policy][option][kd_id] += votes
    except KeyError:
        universe_politics["votes"][policy][option][kd_id] = votes

    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload)
    )

    universe_politics_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universepolitics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(universe_politics)
    )

    return (flask.jsonify({"message": "Cast votes", "status": "success"}), 200)


def _calc_pop_change_per_epoch(
    kd_info_parse,
    fuelless: bool,
    epoch_elapsed,
):
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_info = _get_mobis_queue(kd_info_parse["kdId"])
    mobis_units = mobis_info
    int_fuelless = int(fuelless)

    start_time = datetime.datetime.now(datetime.timezone.utc)
    units = _calc_units(start_time, current_units, generals_units, mobis_units)
    max_hangar_capacity, current_hangar_capacity = _calc_hangar_capacity(kd_info_parse, units)

    overflow = max(current_hangar_capacity - max_hangar_capacity, 0)
    pop_capacity = math.floor(kd_info_parse["structures"]["homes"] * BASE_HOMES_CAPACITY * (1 - int_fuelless * BASE_FUELLESS_POP_CAP_REDUCTION))
    
    pop_capacity_less_overflow = max(pop_capacity - overflow, 0)

    pop_difference = pop_capacity_less_overflow - kd_info_parse["population"]
    if pop_difference < 0:
        pct_pop_loss = BASE_PCT_POP_LOSS_PER_EPOCH * kd_info_parse["population"] * epoch_elapsed
        stars_pop_loss = BASE_POP_LOSS_PER_STAR_PER_EPOCH * kd_info_parse["stars"] * epoch_elapsed
        greater_pop_loss = max(pct_pop_loss, stars_pop_loss)
        pop_change = -1 *min(greater_pop_loss, abs(pop_difference))
    elif pop_difference > 0:
        pct_pop_gain = BASE_PCT_POP_GROWTH_PER_EPOCH * kd_info_parse["population"] * epoch_elapsed
        stars_pop_gain = BASE_POP_GROWTH_PER_STAR_PER_EPOCH * kd_info_parse["stars"] * epoch_elapsed
        greater_pop_gain = max(pct_pop_gain, stars_pop_gain) * (1 - int_fuelless * BASE_FUELLESS_POP_GROWTH_REDUCTION)
        pop_change = min(greater_pop_gain, pop_difference)
    else:
        pop_change = 0
    
    return pop_change, pop_capacity_less_overflow

def _calc_structures_losses(
    kd_info_parse,
    epoch_elapsed
):
    # kd_id = kd_info_parse['kdId']
    # structures_info = REQUESTS_SESSION.get(
    #     os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
    #     headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    # )
    # 
    # structures_info_parse = json.loads(structures_info.text)

    current_structures = kd_info_parse["structures"]
    # building_structures = structures_info_parse["structures"]

    # start_time = datetime.datetime.now(datetime.timezone.utc)
    # structures = _calc_structures(start_time, current_structures, building_structures, epochs=[999])
    count_current_structures = sum(current_structures.values())
    # all_building_structures = sum(structures["hour_999"].values())
    total_structures = {
        k: (
            kd_info_parse["structures"].get(k, 0)
            # + all_building_structures.get(k, 0) 
        )
        for k in STRUCTURES
    }
    count_total_structures = (
        count_current_structures
        # + all_building_structures
    )
    if count_total_structures <= kd_info_parse["stars"]:
        return None
    try:
        pct_total_structures = {
            k: v / count_total_structures
            for k, v in total_structures.items()
        }
    except ZeroDivisionError:
        pct_total_structures = {
            k: 0
            for k in total_structures
        }
    
    structures_to_reduce = count_total_structures - kd_info_parse["stars"]
    reduction_per_epoch = structures_to_reduce * BASE_STRUCTURES_LOSS_RETURN_RATE * epoch_elapsed
    reduction_per_stars = min(kd_info_parse["stars"] * BASE_STRUCTURES_LOSS_PER_STAR_PER_EPOCH * epoch_elapsed, structures_to_reduce, count_current_structures)
    greater_reduction = max(reduction_per_epoch, reduction_per_stars)

    structures_to_reduce = {
        k: v * greater_reduction
        for k, v in pct_total_structures.items()
    }
    return structures_to_reduce
    
def _get_siphons_in(kd_id):
    siphons_in_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsin',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    siphons_in_info_parse = json.loads(siphons_in_info.text)
    return siphons_in_info_parse["siphons_in"]
    
def _get_siphons_out(kd_id):
    siphons_out_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsout',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    siphons_out_info_parse = json.loads(siphons_out_info.text)
    return siphons_out_info_parse["siphons_out"]
    

def _calc_siphons(
    gross_income,
    kd_id,
    time_update,
    epoch_elapsed,
):
    siphons_out = _get_siphons_out(kd_id)
    siphons_in = _get_siphons_in(kd_id)

    total_siphons = sum([siphon["siphon"] for siphon in siphons_out])
    siphon_pool = min(gross_income * BASE_MAX_SIPHON, total_siphons)
    keep_siphons = []
    for siphon_out in siphons_out:
        from_kd = siphon_out["from"]
        time_expiry = datetime.datetime.fromisoformat(siphon_out["time"]).astimezone(datetime.timezone.utc)
        pct_siphon = siphon_out["siphon"] / total_siphons
        siphon_money = pct_siphon * siphon_pool * epoch_elapsed
        payload_siphons_in = {
            "new_siphons": {
                "from": kd_id,
                "siphon": siphon_money,
            }
        }
        siphons_in_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{from_kd}/siphonsin',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload_siphons_in),
        )
        if time_expiry > time_update:
            keep_siphons.append(
                {
                    "from": siphon_out["from"],
                    "time": siphon_out["time"],
                    "siphon": siphon_out["siphon"] - siphon_money
                }
            )
    
    siphon_out_payload = {
        "siphons": keep_siphons,
    }
    siphon_out_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsout',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(siphon_out_payload),
    )

    siphon_in_income = sum(siphon["siphon"] for siphon in siphons_in) / epoch_elapsed
    resolve_siphons_in_payload = {
        "siphons": []
    }
    resolve_siphons_in = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsin',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(resolve_siphons_in_payload),
    )
    return siphon_pool, siphon_in_income

def _kingdom_with_income(
    kd_info_parse,
    current_bonuses,
    state,
):
    time_now = datetime.datetime.now(datetime.timezone.utc)
    time_last_income = datetime.datetime.fromisoformat(kd_info_parse["last_income"]).astimezone(datetime.timezone.utc)
    seconds_elapsed = (time_now - time_last_income).total_seconds()
    epoch_elapsed = seconds_elapsed / BASE_EPOCH_SECONDS

    is_isolationist = "Isolationist" in state["state"]["active_policies"]
    is_free_trade = "Free Trade" in state["state"]["active_policies"]

    income = {
        "money": {},
        "fuel": {},
    }
    income["money"]["mines"] = math.floor(kd_info_parse["structures"]["mines"]) * BASE_MINES_INCOME_PER_EPOCH
    income["money"]["population"] = math.floor(kd_info_parse["population"]) * BASE_POP_INCOME_PER_EPOCH
    income["money"]["bonus"] = current_bonuses["money_bonus"] - is_isolationist * BASE_ISOLATIONIST_DECREASE + is_free_trade * BASE_FREE_TRADE_INCREASE
    income["money"]["gross"] = (
        income["money"]["mines"]
        + income["money"]["population"]
    ) * (1 + income["money"]["bonus"])
    income["money"]["siphons_out"], income["money"]["siphons_in"] = _calc_siphons(
        income["money"]["gross"],
        kd_info_parse["kdId"],
        time_now,
        epoch_elapsed,
    )
    income["money"]["net"] = (income["money"]["gross"] + income["money"]["siphons_in"] - income["money"]["siphons_out"])
    new_income = income["money"]["net"] * epoch_elapsed

    total_units = {
        k: v
        for k, v in kd_info_parse["units"].items()
    }
    for general in kd_info_parse["generals_out"]:
        for key_unit, value_unit in general.items():
            if key_unit == "return_time":
                continue
            total_units[key_unit] += value_unit

    income["fuel"]["fuel_plants"] = math.floor(kd_info_parse["structures"]["fuel_plants"]) * BASE_FUEL_PLANTS_INCOME_PER_EPOCH
    income["fuel"]["bonus"] = current_bonuses["fuel_bonus"]
    income["fuel"]["units"] = {}
    for key_unit, value_units in total_units.items():
        income["fuel"]["units"][key_unit] = value_units * UNITS[key_unit]["fuel"]
    income["fuel"]["population"] = kd_info_parse["population"] * BASE_POP_FUEL_CONSUMPTION_PER_EPOCH
    income["fuel"]["shields"] = {}
    income["fuel"]["shields"]["military"] = kd_info_parse["shields"]["military"] * 100 * kd_info_parse["stars"] * BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT
    income["fuel"]["shields"]["spy"] = kd_info_parse["shields"]["spy"] * 100 * kd_info_parse["stars"] * BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT
    income["fuel"]["shields"]["spy_radar"] = kd_info_parse["shields"]["spy_radar"] * 100 * kd_info_parse["stars"] * BASE_SPY_RADAR_COST_PER_LAND_PER_PCT
    income["fuel"]["shields"]["missiles"] = kd_info_parse["shields"]["missiles"] * 100 * kd_info_parse["stars"] * BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT

    new_fuel = income["fuel"]["fuel_plants"] * (1 + income["fuel"]["bonus"])
    raw_fuel_consumption = (
        sum(income["fuel"]["units"].values())
        + sum(income["fuel"]["shields"].values())
        + income["fuel"]["population"]
    )
    income["fuel"]["net"] = new_fuel - raw_fuel_consumption
    net_fuel = income["fuel"]["net"] * epoch_elapsed
    max_fuel = math.floor(kd_info_parse["structures"]["fuel_plants"]) * BASE_FUEL_PLANTS_CAPACITY
    min_fuel = BASE_NEGATIVE_FUEL_CAP(kd_info_parse["stars"])

    income["drones"] = math.floor(kd_info_parse["structures"]["drone_factories"]) * BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH
    new_drones = income["drones"] * epoch_elapsed

    fuelless = kd_info_parse["fuel"] <= 0
    pop_change, _ = _calc_pop_change_per_epoch(kd_info_parse, fuelless, epoch_elapsed)
    income["population"] = pop_change / epoch_elapsed

    structures_to_reduce = _calc_structures_losses(kd_info_parse, epoch_elapsed)

    new_project_points = {
        key_project: assigned_engineers * BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH * epoch_elapsed
        for key_project, assigned_engineers in kd_info_parse["projects_assigned"].items()
    }
    new_kd_info = kd_info_parse.copy()
    for key_project, new_points in new_project_points.items():
        new_kd_info["projects_points"][key_project] += new_points
    for key_project in ONE_TIME_PROJECTS:
        if key_project not in kd_info_parse["completed_projects"]:
            if new_kd_info["projects_points"][key_project] >= new_kd_info["projects_max_points"][key_project]:
                new_kd_info["completed_projects"].append(key_project)
                new_kd_info["projects_assigned"][key_project] = 0
                try:
                    ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
                    ws.send(json.dumps({
                        "message": f"Completed project {key_project}!",
                        "status": "info",
                        "category": "Projects",
                        "delay": 15000,
                        "update": [],
                    }))
                except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
                    pass

    if new_kd_info["auto_spending_enabled"]:
        pct_allocated = sum(new_kd_info["auto_spending"].values())
        for key_spending, pct_spending in new_kd_info["auto_spending"].items():
            new_kd_info["funding"][key_spending] += pct_spending * new_income
        new_kd_info["money"] += new_income * (1 - pct_allocated)
    else:
        new_kd_info["money"] += new_income
    new_kd_info["fuel"] = max(min(max_fuel, new_kd_info["fuel"] + net_fuel), min_fuel)
    new_kd_info["drones"] += new_drones
    new_kd_info["population"] = new_kd_info["population"] + pop_change
    new_kd_info["last_income"] = time_now.isoformat()
    new_kd_info["income"] = income

    if new_kd_info["population"] <= 0:
        new_kd_info["status"] = "Dead"
        _mark_kingdom_death(kd_info_parse["kdId"])
    if structures_to_reduce:
        new_kd_info["structures"] = {
            k: v - structures_to_reduce.get(k, 0)
            for k, v in new_kd_info["structures"].items()
        }
    if new_kd_info["fuel"] <= 0:
        new_kd_info["shields"] = {
            k: 0
            for k in new_kd_info["shields"]
        }

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
    try:
        ws = SOCK_HANDLERS[kd_id]
        ws.send(json.dumps({
            "message": f"Finished settling {ready_settles} stars",
            "status": "info",
            "category": "Settles",
            "delay": 5000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    
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
    
    
    
    mobis_payload = {
        "mobis": keep_mobis
    }
    mobis_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(mobis_payload),
    )
    try:
        ws = SOCK_HANDLERS[kd_id]
        count_mobis = sum(ready_mobis.values())
        ws.send(json.dumps({
            "message": f"Finished mobilizing {count_mobis} units",
            "status": "info",
            "category": "Mobis",
            "delay": 5000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    
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
    
    
    
    structures_payload = {
        "structures": keep_structures
    }
    structures_patch = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(structures_payload),
    )
    try:
        ws = SOCK_HANDLERS[kd_id]
        count_structures = sum(ready_structures.values())
        ws.send(json.dumps({
            "message": f"Finished building {count_structures} structures",
            "status": "info",
            "category": "Structures",
            "delay": 5000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    
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
    try:
        ws = SOCK_HANDLERS[kd_id]
        count_missiles = sum(ready_missiles.values())
        ws.send(json.dumps({
            "message": f"Finished building {count_missiles} missiles",
            "status": "info",
            "category": "Missiles",
            "delay": 5000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    
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
    try:
        ws = SOCK_HANDLERS[kd_id]
        ws.send(json.dumps({
            "message": f"Finished training {ready_engineers} engineers",
            "status": "info",
            "category": "Engineers",
            "delay": 5000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    
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
    
    try:
        ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
        count_returning_units = sum(returning_units.values())
        ws.send(json.dumps({
            "message": f"{returning_generals} generals returned with {count_returning_units} units",
            "status": "info",
            "category": "Generals",
            "delay": 15000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return kd_info_parse, next_resolve


def _resolve_spy(kd_info_parse, time_update, current_bonuses):
    resolve_time = datetime.datetime.fromisoformat(kd_info_parse["next_resolve"]["spy_attempt"]).astimezone(datetime.timezone.utc)
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_info_parse["kdId"], galaxies_inverted[kd_info_parse["kdId"]])
    is_intelligence = "Intelligence" in galaxy_policies["active_policies"]
    next_resolve_time = max(
        resolve_time + datetime.timedelta(
            seconds=BASE_EPOCH_SECONDS * BASE_SPY_ATTEMPT_TIME_MULTIPLIER * (1 - current_bonuses["spy_bonus"] - int(is_intelligence) * BASE_INTELLIGENCE_RETURN_REDUCTION)
        ),
        time_update,
    )
    if kd_info_parse["spy_attempts"] < BASE_SPY_ATTEMPTS_MAX:
        kd_info_parse["spy_attempts"] += 1
        try:
            ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
            ws.send(json.dumps({
                "message": f"A new spy attempt is available",
                "status": "info",
                "category": "Spy",
                "delay": 15000,
                "update": [],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    return kd_info_parse, next_resolve_time

def _resolve_auto_spending(
    kd_info_parse,
    time_update,
    current_bonuses,
    settle_info=None,
    structures_info=None,
    mobis_info=None,
    engineers_info=None,
):
    resolve_time = datetime.datetime.fromisoformat(kd_info_parse["next_resolve"]["auto_spending"]).astimezone(datetime.timezone.utc)
    kd_id = kd_info_parse["kdId"]
    next_resolves = {}

    if settle_info is None:
        settle_info = _get_settle(kd_id)
    if structures_info is None:
        structures_info = _get_structures_info(kd_id)
    if mobis_info is None:
        mobis_info = _get_mobis(kd_id)
    if engineers_info is None:
        engineers_info = _get_engineers(kd_id)

    settle_price = settle_info["settle_price"]
    max_available_settle = settle_info["max_available_settle"]
    settle_funding = kd_info_parse["funding"]["settle"]

    new_settles = min(math.floor(settle_funding / settle_price), max_available_settle)
    if new_settles:
        kd_info_parse["funding"]["settle"] = settle_funding - new_settles * settle_price
        
        settle_time = (time_update + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SETTLE_TIME_MULTIPLIER)).isoformat()
        next_resolves["settles"] = min(settle_time, kd_info_parse["next_resolve"]["settles"])
        settle_payload = {
            "new_settles": [
                {
                    "time": settle_time,
                    "amount": new_settles,
                }
            ]
        }
        settles_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(settle_payload),
        )
    

    def _weighted_random_by_dct(dct):
        rand_val = random.random()
        total = 0
        for k, v in dct.items():
            total += v
            if rand_val <= total:
                return k

    structures_price = structures_info["price"]
    max_available_structures = structures_info["max_available_structures"]
    structures_funding = kd_info_parse["funding"]["structures"]
    structures_to_build = min(math.floor(structures_funding / structures_price), max_available_structures)
    if structures_to_build and sum(kd_info_parse["structures_target"].values()) > 0:
        print("Structures to build", structures_to_build)
        structures_current = structures_info["current"]
        structures_building = structures_info["hour_24"]
        total_structures = {
            k: structures_current.get(k, 0) + structures_building.get(k, 0)
            for k in STRUCTURES
        }
        print("Total structures", total_structures)
        pct_total_structures = {
            k: v / kd_info_parse["stars"]
            for k, v in total_structures.items()
        }
        print("Pct total structures", pct_total_structures)
        target_gap = {
            k: kd_info_parse["structures_target"].get(k, 0) - v
            for k, v in pct_total_structures.items()
            if (kd_info_parse["structures_target"].get(k, 0) - v) > 0
        }
        print("Target gap", target_gap)
        total_target_gap = sum(target_gap.values())
        target_gap_pct = {
            k: v / total_target_gap
            for k, v in target_gap.items()
        }
        print("Target gap pct", target_gap_pct)
        target_structures_to_build = {
            k: math.floor(v * structures_to_build)
            for k, v in target_gap_pct.items()
        }
        print("Target structures to build", target_structures_to_build)
        leftover_structures = structures_to_build - sum(target_structures_to_build.values())
        print("Leftover structures", leftover_structures)
        for _ in range(leftover_structures):
            rand_structure = _weighted_random_by_dct(target_gap_pct)
            target_structures_to_build[rand_structure] += 1
        print("Leftover structures", leftover_structures)
        
        kd_info_parse["funding"]["structures"] = structures_funding - structures_to_build * structures_price
        
        structures_time = (time_update + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_STRUCTURE_TIME_MULTIPLIER)).isoformat()
        next_resolves["structures"] = min(structures_time, kd_info_parse["next_resolve"]["structures"])
        target_structures_to_build_nonzero = {
            k: v
            for k, v in target_structures_to_build.items()
            if v > 0
        }
        structures_payload = {
            "new_structures": [
                {
                    "time": structures_time,
                    **target_structures_to_build_nonzero,
                }
            ]
        }
        structures_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(structures_payload),
        )

    recruit_price = mobis_info["recruit_price"]
    recruit_time = mobis_info["recruit_time"]
    max_available_recruits = mobis_info["max_available_recruits"]
    current_units = mobis_info["units"]["current"]
    building_units = mobis_info["units"]["hour_24"]
    units_desc = mobis_info["units_desc"]
    military_funding = kd_info_parse["funding"]["military"]

    if military_funding > 0 and sum(kd_info_parse["units_target"].values()) > 0:
        recruits_to_train = min(math.floor(military_funding / recruit_price), max_available_recruits)
        remaining_funding = military_funding - recruits_to_train * recruit_price
        
        total_units = {
            k: current_units.get(k, 0) + building_units.get(k, 0)
            for k in kd_info_parse["units_target"].keys()
        }
        for general in kd_info_parse["generals_out"]:
            for key_unit, value_unit in general.items():
                if key_unit == "return_time":
                    continue
                total_units[key_unit] += value_unit
        print("Total units", total_units)
        count_total_units = sum(total_units.values())
        pct_total_units = {
            k: v / count_total_units
            for k, v in total_units.items()
        }
        print("Pct total units", pct_total_units)
        target_units_gap = {
            k: kd_info_parse["units_target"].get(k, 0) - v
            for k, v in pct_total_units.items()
            if (kd_info_parse["units_target"].get(k, 0) - v) > 0
        }
        print("Target units gap", target_units_gap)
        total_target_units_gap = sum(target_units_gap.values())
        target_units_gap_pct = {
            k: v / total_target_units_gap
            for k, v in target_units_gap.items()
        }
        print("Target units gap pct", target_units_gap_pct)
        target_gap_weighted_funding = {
            k: v * remaining_funding
            for k, v in target_units_gap_pct.items()
        }
        print("Target units gap pct weighted funding", target_gap_weighted_funding)
        target_gap_weighted_recruits = {
            k: math.floor(v * kd_info_parse["units"]["recruits"])
            for k, v in target_units_gap_pct.items()
        }
        print("Target units gap pct weighted recruits", target_gap_weighted_recruits)
        target_units_to_build = {}
        for key_unit, funding_unit in target_gap_weighted_funding.items():
            units_to_build = min(math.floor(funding_unit / units_desc[key_unit]["cost"]), target_gap_weighted_recruits[key_unit])
            remaining_funding = remaining_funding - units_to_build * units_desc[key_unit]["cost"]
            kd_info_parse["units"]["recruits"] = kd_info_parse["units"]["recruits"] - units_to_build
            target_units_to_build[key_unit] = units_to_build
        print("Target units to build", target_units_to_build)
        print("Remaining funding", remaining_funding)
        
        kd_info_parse["funding"]["military"] = remaining_funding
        
        recruits_time = (time_update + datetime.timedelta(seconds=recruit_time)).isoformat()
        mobis_time = (time_update + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_SPECIALIST_TIME_MULTIPLIER)).isoformat()
        target_units_to_build_nonzero = {
            k: v
            for k, v in target_units_to_build.items()
            if v > 0
        }
        mobis_payload = {
            "new_mobis": []
        }
        if recruits_to_train:
            mobis_payload["new_mobis"].append({
                "time": recruits_time,
                "recruits": recruits_to_train
            })
            next_resolves["mobis"] = min(recruits_time, kd_info_parse["next_resolve"]["mobis"])
        if sum(target_units_to_build_nonzero.values()) > 0:
            mobis_payload["new_mobis"].append({
                "time": mobis_time,
                **target_units_to_build_nonzero,
            })
            kd_info_parse["next_resolve"]["mobis"] = min(mobis_time, kd_info_parse["next_resolve"]["mobis"], next_resolves.get("mobis", DATE_SENTINEL))
        mobis_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(mobis_payload),
        )

    engineers_price = engineers_info["engineers_price"]
    max_available_engineers = engineers_info["max_available_engineers"]
    engineers_funding = kd_info_parse["funding"]["engineers"]
    new_engineers = min(math.floor(engineers_funding / engineers_price), max_available_engineers)
    if new_engineers:
        kd_info_parse["funding"]["engineers"] = engineers_funding - new_engineers * engineers_price
        
        engineers_time = (time_update + datetime.timedelta(seconds=BASE_EPOCH_SECONDS * BASE_ENGINEER_TIME_MULTIPLIER)).isoformat()
        next_resolves["engineers"] = min(engineers_time, kd_info_parse["next_resolve"]["engineers"])
        engineers_payload = {
            "new_engineers": [
                {
                    "time": engineers_time,
                    "amount": new_engineers,
                }
            ]
        }
        engineers_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(engineers_payload),
        )

    next_resolve_time = max(
        resolve_time + datetime.timedelta(
            seconds=BASE_EPOCH_SECONDS * BASE_AUTO_SPENDING_TIME_MULTIPLIER
        ),
        time_update,
    )
    next_resolves["auto_spending"] = next_resolve_time.isoformat()
    return kd_info_parse, next_resolves

def _resolve_auto_attack(kd_info_parse):
    pure_pct = kd_info_parse["auto_attack_settings"].get("pure", 0)
    flex_pct = kd_info_parse["auto_attack_settings"].get("flex", 0)

    req = {
        "attackerValues": {
            "generals": kd_info_parse["generals_available"]
        }
    }
    total_units = kd_info_parse["units"].copy()
    total_general_units = {
        k: 0
        for k in UNITS
    }
    for general_units in kd_info_parse["generals_out"]:
        for key_unit, value_unit in general_units.items():
            if key_unit == "return_time":
                continue
            total_units[key_unit] += value_unit
            total_general_units[key_unit] += value_unit

    pct_units_out = {
        k: v / max(total_units.get(k), 1)
        for k, v in total_general_units.items()
    }
    pct_units_available_pure = {
        k: max(pure_pct - v, 0)
        for k, v in pct_units_out.items()
    }
    pct_units_available_flex = {
        k: max(flex_pct - v, 0)
        for k, v in pct_units_out.items()
    }
    
    for key_unit, value_unit in kd_info_parse["units"].items():
        if UNITS[key_unit].get("offense", 0) == 0:
            continue
        else:
            if UNITS[key_unit].get("defense", 0) == 0:
                req["attackerValues"][key_unit] = math.floor(pct_units_available_pure[key_unit] * value_unit)
            else:
                req["attackerValues"][key_unit] = math.floor(pct_units_available_flex[key_unit] * value_unit)
    _attack_primitives(req, kd_info_parse["kdId"])
    try:
        ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
        units = {
            k: v
            for k, v in req["attackerValues"].items()
            if k != "generals"
        }
        count_units = sum(units.values())
        ws.send(json.dumps({
            "message": f"Automatically attacked primitives with {req['attackerValues']['generals']} generals and {count_units} units",
            "status": "info",
            "category": "Auto Primitives",
            "delay": 15000,
            "update": ["mobis", "attackhistory"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass

def _resolve_auto_rob(kd_info_parse):
    drones_pct = kd_info_parse["auto_rob_settings"].get("drones", 0)
    keep_spy_attempts = kd_info_parse["auto_rob_settings"].get("keep", 10)
    shielded = kd_info_parse["auto_rob_settings"].get("shielded", False)

    if kd_info_parse["spy_attempts"] > keep_spy_attempts:
        req = {
            "drones": math.floor(drones_pct * kd_info_parse["drones"]),
            "shielded": shielded,
        }
        _rob_primitives(req, kd_info_parse["kdId"])
        try:
            ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
            ws.send(json.dumps({
                "message": f"Automatically robbed primitives with {req['drones']} drones",
                "status": "info",
                "category": "Auto Primitives",
                "delay": 15000,
                "update": ["spyhistory"],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass

def _resolve_auto_projects(kd_info_parse):
    engineers_to_assign = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())
    total_engineers = kd_info_parse["units"]["engineers"]

    pct_assigned = {
        k: v / total_engineers
        for k, v in kd_info_parse["projects_assigned"].items()
    }
    target_gap = {
        k: kd_info_parse["projects_target"].get(k, 0) - v
        for k, v in pct_assigned.items()
        if (kd_info_parse["projects_target"].get(k, 0) - v) > 0
    }
    total_target_gap = sum(target_gap.values())
    target_gap_pct = {
        k: v / total_target_gap
        for k, v in target_gap.items()
    }
    target_engineers_to_assign = {
        k: math.floor(v * engineers_to_assign)
        for k, v in target_gap_pct.items()
    }
    leftover_engineers = engineers_to_assign - sum(target_engineers_to_assign.values())
    highest_gap_pct = max(target_gap_pct, key=target_gap_pct.get)
    target_engineers_to_assign[highest_gap_pct] += leftover_engineers
    
    new_projects_assigned = kd_info_parse["projects_assigned"]
    for key_project, value_engineers in target_engineers_to_assign.items():
        kd_info_parse["projects_assigned"][key_project] += value_engineers
    return kd_info_parse

def _resolve_schedule_attack(new_kd_info, schedule):
    pure_pct = schedule["options"].get("pure_offense", 0)
    flex_pct = schedule["options"].get("flex_offense", 0)

    req = {
        "attackerValues": {
            "generals": schedule["options"].get("generals", 0)
        }
    }
    total_units = new_kd_info["units"].copy()
    total_general_units = {
        k: 0
        for k in UNITS
    }
    for general_units in new_kd_info["generals_out"]:
        for key_unit, value_unit in general_units.items():
            if key_unit == "return_time":
                continue
            total_units[key_unit] += value_unit
            total_general_units[key_unit] += value_unit

    pct_units_out = {
        k: v / max(total_units.get(k), 1)
        for k, v in total_general_units.items()
    }
    pct_units_available_pure = {
        k: max(pure_pct - v, 0)
        for k, v in pct_units_out.items()
    }
    pct_units_available_flex = {
        k: max(flex_pct - v, 0)
        for k, v in pct_units_out.items()
    }
    
    for key_unit, value_unit in new_kd_info["units"].items():
        if UNITS[key_unit].get("offense", 0) == 0:
            continue
        else:
            if UNITS[key_unit].get("defense", 0) == 0:
                req["attackerValues"][key_unit] = math.floor(pct_units_available_pure[key_unit] * value_unit)
            else:
                req["attackerValues"][key_unit] = math.floor(pct_units_available_flex[key_unit] * value_unit)
    new_kd_info, payload, status_code = _attack(req, new_kd_info["kdId"], schedule["options"]["target"])
    return new_kd_info

def _resolve_schedule_attackprimitives(new_kd_info, schedule):
    pure_pct = schedule["options"].get("pure_offense", 0)
    flex_pct = schedule["options"].get("flex_offense", 0)

    req = {
        "attackerValues": {
            "generals": schedule["options"].get("generals", 0)
        }
    }
    total_units = new_kd_info["units"].copy()
    total_general_units = {
        k: 0
        for k in UNITS
    }
    for general_units in new_kd_info["generals_out"]:
        for key_unit, value_unit in general_units.items():
            if key_unit == "return_time":
                continue
            total_units[key_unit] += value_unit
            total_general_units[key_unit] += value_unit

    pct_units_out = {
        k: v / max(total_units.get(k), 1)
        for k, v in total_general_units.items()
    }
    pct_units_available_pure = {
        k: max(pure_pct - v, 0)
        for k, v in pct_units_out.items()
    }
    pct_units_available_flex = {
        k: max(flex_pct - v, 0)
        for k, v in pct_units_out.items()
    }
    
    for key_unit, value_unit in new_kd_info["units"].items():
        if UNITS[key_unit].get("offense", 0) == 0:
            continue
        else:
            if UNITS[key_unit].get("defense", 0) == 0:
                req["attackerValues"][key_unit] = math.floor(pct_units_available_pure[key_unit] * value_unit)
            else:
                req["attackerValues"][key_unit] = math.floor(pct_units_available_flex[key_unit] * value_unit)
    new_kd_info, payload, status_code = _attack_primitives(req, new_kd_info["kdId"])
    return new_kd_info

def _resolve_schedule_intelspy(new_kd_info, schedule):
    drones_pct = schedule["options"].get("drones_pct", 0)
    max_tries = schedule["options"].get("max_tries", 0)
    shielded = schedule["options"].get("shielded", False)
    operation = schedule["options"].get("operation", "")
    target_kd = schedule["options"].get("target", "")
    share_to_galaxy = schedule["options"].get("share_to_galaxy", False)

    for _ in range(max_tries):
        req = {
            "drones": math.floor(drones_pct * new_kd_info["drones"]),
            "shielded": shielded,
            "operation": operation
        }
        new_kd_info, payload, status_code, success = _spy(req, new_kd_info["kdId"], target_kd)
        if success:
            if share_to_galaxy:
                pass
            break
    return new_kd_info

def _resolve_schedule_aggressivespy(new_kd_info, schedule):
    drones_pct = schedule["options"].get("drones_pct", 0)
    attempts = schedule["options"].get("attempts", 0)
    shielded = schedule["options"].get("shielded", False)
    operation = schedule["options"].get("operation", "")
    target_kd = schedule["options"].get("target", "")

    for _ in range(attempts):
        req = {
            "drones": math.floor(drones_pct * new_kd_info["drones"]),
            "shielded": shielded,
            "operation": operation
        }
        new_kd_info, payload, status_code, success = _spy(req, new_kd_info["kdId"], target_kd)
    return new_kd_info

def _resolve_schedule_missiles(new_kd_info, schedule):
    planet_busters = schedule["options"].get("planet_busters", 0)
    star_busters = schedule["options"].get("star_busters", 0)
    galaxy_busters = schedule["options"].get("galaxy_busters", 0)
    target_kd = schedule["options"].get("target", "")

    req = {
        "attackerValues": {
            "planet_busters": planet_busters,
            "star_busters": star_busters,
            "galaxy_busters": galaxy_busters,
        }
    }
    new_kd_info, payload, status_code = _launch_missiles(req, new_kd_info["kdId"], target_kd)
    return new_kd_info

def _resolve_schedules(new_kd_info, time_update):
    keep_schedules = []
    ready_schedules = []
    for schedule in new_kd_info["schedule"]:
        if datetime.datetime.fromisoformat(schedule["time"]).astimezone(datetime.timezone.utc) < time_update:
            ready_schedules.append(schedule)
        else:
            keep_schedules.append(schedule)
    
    handler_funcs = {
        "attack": _resolve_schedule_attack,
        "attackprimitives": _resolve_schedule_attackprimitives,
        "intelspy": _resolve_schedule_intelspy,
        "aggressivespy": _resolve_schedule_aggressivespy,
        "missiles": _resolve_schedule_missiles,
    }
    for ready_sched in ready_schedules:
        new_kd_info = handler_funcs[ready_sched["type"]](new_kd_info, ready_sched)

    new_kd_info["schedule"] = keep_schedules
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{new_kd_info["kdId"]}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(new_kd_info, default=str),
    )
    return new_kd_info

def _mark_kingdom_death(kd_id):
    query = db.session.query(User).filter_by(kd_id=kd_id).all()
    user = query[0]
    user.kd_death_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.session.commit()
    _update_accounts()
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

def _begin_election(state):
    election_start = datetime.datetime.fromisoformat(state["state"]["election_start"]).astimezone(datetime.timezone.utc)
    election_end = election_start + datetime.timedelta(seconds=BASE_ELECTION_LENGTH_SECONDS)

    state_payload = {
        "election_end": election_end.isoformat(),
        "active_policies": [],
    }

    universe_politics_payload = {
        "votes": {
            "policy_1": {
                "option_1": {},
                "option_2": {},
            },
            "policy_2": {
                "option_1": {},
                "option_2": {},
            },
        }
    }

    universe_politics_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universepolitics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(universe_politics_payload)
    )
    update_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(state_payload)
    )
    return state

def _resolve_election(state):
    election_end = datetime.datetime.fromisoformat(state["state"]["election_end"]).astimezone(datetime.timezone.utc)
    next_election_start = election_end + datetime.timedelta(seconds=BASE_ELECTION_RESULTS_DURATION)


    universe_politics = _get_universe_politics()
    policy_1_option_1_votes = sum(universe_politics["votes"]["policy_1"]["option_1"].values())
    policy_1_option_2_votes = sum(universe_politics["votes"]["policy_1"]["option_2"].values())
    policy_2_option_1_votes = sum(universe_politics["votes"]["policy_2"]["option_1"].values())
    policy_2_option_2_votes = sum(universe_politics["votes"]["policy_2"]["option_2"].values())

    active_policies = []
    if policy_1_option_1_votes >= policy_1_option_2_votes:
        active_policies.append(UNIVERSE_POLICIES["policy_1"]["options"]["1"]["name"])
    else:
        active_policies.append(UNIVERSE_POLICIES["policy_1"]["options"]["2"]["name"])

        
    if policy_2_option_1_votes >= policy_2_option_2_votes:
        active_policies.append(UNIVERSE_POLICIES["policy_2"]["options"]["1"]["name"])
    else:
        active_policies.append(UNIVERSE_POLICIES["policy_2"]["options"]["2"]["name"])

    state_payload = {
        "election_start": next_election_start.isoformat(),
        "election_end": "",
        "active_policies": active_policies,
    }
    state["state"]["active_policies"] = active_policies

    update_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(state_payload)
    )
    return state


@app.route('/api/refreshdata')
def refresh_data():
    """Performance periodic refresh tasks"""
    headers = flask.request.headers
    if headers.get("Refresh-Secret", "") != "domnusrefresh":
        return ("Not Authorized", 401)
    
    state = _get_state()
    time_now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if time_now > state["state"]["election_end"] and state["state"]["election_end"] != "":
        state = _resolve_election(state)
    elif time_now > state["state"]["election_start"] and state["state"]["election_end"] == "":
        state = _begin_election(state)

    kingdoms = _get_kingdoms()
    for kd_id in kingdoms:
        try:
            query = db.session.query(User).filter_by(kd_id=kd_id).all()
            user = query[0]
            if not user.kd_created:
                continue
        except:
            print(f"Could not query kd_id {kd_id}")
            pass
        next_resolves = {}
        time_update = datetime.datetime.now(datetime.timezone.utc)
        kd_info = REQUESTS_SESSION.get(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
        )
        kd_info_parse = json.loads(kd_info.text)
        if kd_info_parse["status"].lower() == "dead":
            continue
        current_bonuses = {
            project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
            for project, project_dict in PROJECTS.items()
            if "max_bonus" in project_dict
        }

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
                time_update,
                current_bonuses,
            )
        if "auto_spending" in categories_to_resolve:
            kd_info_parse, next_resolves_auto_spending = _resolve_auto_spending(
                kd_info_parse,
                time_update,
                current_bonuses,
            )
            next_resolves = {
                k: min(
                    datetime.datetime.fromisoformat(v).astimezone(datetime.timezone.utc),
                    next_resolves.get(k, datetime.datetime.fromisoformat(DATE_SENTINEL).astimezone(datetime.timezone.utc))
                )
                for k, v in next_resolves_auto_spending.items()
            }
        if kd_info_parse["auto_assign_projects"] and (kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values()) > 0):
            kd_info_parse = _resolve_auto_projects(kd_info_parse)

        for category, next_resolve_datetime in next_resolves.items():
            kd_info_parse["next_resolve"][category] = next_resolve_datetime.isoformat()
        new_kd_info = _kingdom_with_income(kd_info_parse, current_bonuses, state)
        kd_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(new_kd_info, default=str),
        )
        new_kd_info = _resolve_schedules(new_kd_info, time_update)
        if new_kd_info["auto_attack_enabled"] and new_kd_info["generals_available"] > 0:
            _resolve_auto_attack(new_kd_info)
        if new_kd_info["auto_rob_enabled"]:
            _resolve_auto_rob(new_kd_info)
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
    _update_accounts()
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
    _update_accounts()
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
def get_time():
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