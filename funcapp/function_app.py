import azure.functions as func
import logging
import os
import json
import uuid
import datetime
import re
from collections import defaultdict

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import (
    CosmosAccessConditionFailedError,
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)

from concurrency import ConditionalContainer, Refused, TooBusy, change_document, retry_on_conflict
from queues import coalesce

ENDPOINT = os.environ["COSMOS_ENDPOINT"]
KEY = os.environ["COSMOS_KEY"]

DATABASE_NAME = os.environ.get("COSMOS_DATABASE_NAME", "dev")
CONTAINER_NAME = os.environ.get("COSMOS_CONTAINER_NAME", "test")

CLIENT = CosmosClient(url=ENDPOINT, credential=KEY)
DATABASE = CLIENT.create_database_if_not_exists(id=DATABASE_NAME)
CONTAINER = ConditionalContainer(DATABASE.get_container_client(CONTAINER_NAME))

APP = func.FunctionApp()

ARCHIVE_PREFIX = "archive_"  # finished rounds (api/untitledapp/roundend.py) outlive a reset
RESET_KEEP_IDS = [
    "accounts",
    "state",
    "kingdoms",
    "galaxies",
    "empires",
    "universe_news",
    "universe_votes",
    "scores",
]

@APP.function_name(name="DeleteAll")
@APP.route(route="deleteall", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def delete_all(req: func.HttpRequest) -> func.HttpResponse:
    items = CONTAINER.read_all_items()
    for item in items:
        if is_user_document(item["id"]):
            # Blanked, a username claim would still block its name and a user would lose its id_number.
            CONTAINER.delete_item(item=item["id"], partition_key=item["id"])
        else:
            CONTAINER.replace_item(item["id"], {"id": item["id"]})
    try:
        return func.HttpResponse(
            "Deleted",
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Encountered an error",
            status_code=500,
        )

@APP.function_name(name="CreateState")
@APP.route(route="init", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def init_state(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create initial game state.')

    try:
        CONTAINER.create_item(
            {
                "id": "state",
                "state": {},
                "round": str(uuid.uuid4()),
            }
        )
        CONTAINER.create_item(
            {
                "id": "kingdoms",
                "kingdoms": {},
            }
        )
        CONTAINER.create_item(
            {
                "id": "galaxies",
                "galaxies": {},
            }
        )
        CONTAINER.create_item(
            {
                "id": "empires",
                "empires": {},
                "last_update": "",
            }
        )
        CONTAINER.create_item(
            {
                "id": "universe_news",
                "news": [],
            }
        )
        CONTAINER.create_item(
            {
                "id": "universe_votes",
                "votes": {},
            }
        )
        CONTAINER.create_item(
            {
                "id": "accounts",
                "accounts": [],
            }
        )
        CONTAINER.create_item(
            {
                "id": "scores",
                "points": {},
                "stars": {},
                "networth": {},
                "galaxy_networth": {},
                "last_update": "",
            }
        )
        return func.HttpResponse(
            "Initial state created.",
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Initial state creation encountered an error",
            status_code=500,
        )


@APP.function_name(name="GetState")
@APP.route(route="state", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_state(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get state request.')    
    item_id = f"state"
    try:
        state = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(state),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve state info",
            status_code=500,
        )
    
@APP.function_name(name="Update")
@APP.route(route="updatestate", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_state(req: func.HttpRequest) -> func.HttpResponse:
    req_body = req.get_json()
    try:
        state = CONTAINER.read_item(
            item="state",
            partition_key="state",
        )
        state["state"] = {
            **state["state"],
            **req_body,
        }
        CONTAINER.replace_item(
            "state",
            state,
        )
        return func.HttpResponse(
            "Updated state",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "Failed to update state",
            status_code=500,
        )

@APP.function_name(name="ResetState")
@APP.route(route="resetstate", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def reset_state(req: func.HttpRequest) -> func.HttpResponse:
    try:
        items = CONTAINER.read_all_items()
        for item in items:
            if (item["id"] not in RESET_KEEP_IDS and not is_user_document(item["id"])
                    and not item["id"].startswith(ARCHIVE_PREFIX)):
                CONTAINER.delete_item(
                    item=item["id"],
                    partition_key=item["id"],
                )

        # A new round id: login tokens issued before the reset stop working (decision 0005).
        round_state = CONTAINER.read_item(item="state", partition_key="state")
        round_state["round"] = str(uuid.uuid4())
        CONTAINER.replace_item("state", round_state)

        accounts = CONTAINER.read_item(
            item="accounts",
            partition_key="accounts"
        )
        new_accounts = []
        for account in accounts["accounts"]:
            reset_account = account
            reset_account["kd_id"] = None
            reset_account["kd_death_date"] = None
            reset_account["kd_created"] = False
            new_accounts.append(reset_account)
        accounts["accounts"] = new_accounts
        CONTAINER.replace_item(
            "accounts",
            accounts,
        )
        kingdoms = CONTAINER.read_item(
            item="kingdoms",
            partition_key="kingdoms"
        )
        kingdoms["next_id"] = max(
            [kingdoms.get("next_id", 0), len(kingdoms["kingdoms"])] + [int(k) + 1 for k in kingdoms["kingdoms"]]
        )
        kingdoms["kingdoms"] = {}
        CONTAINER.replace_item(
            "kingdoms",
            kingdoms,
        )

        galaxies = CONTAINER.read_item(
            item="galaxies",
            partition_key="galaxies"
        )
        galaxies["galaxies"] = {}
        CONTAINER.replace_item(
            "galaxies",
            galaxies,
        )

        empires = CONTAINER.read_item(
            item="empires",
            partition_key="empires"
        )
        empires["empires"] = {}
        empires["last_update"] = ""
        CONTAINER.replace_item(
            "empires",
            empires,
        )

        universe_news = CONTAINER.read_item(
            item="universe_news",
            partition_key="universe_news"
        )
        universe_news["news"] = []
        CONTAINER.replace_item(
            "universe_news",
            universe_news,
        )

        universe_votes = CONTAINER.read_item(
            item="universe_votes",
            partition_key="universe_votes"
        )
        universe_votes["votes"] = {
            "policy_1": {
                "option_1": {},
                "option_2": {},
            },
            "policy_2": {
                "option_1": {},
                "option_2": {},
            }
        }
        CONTAINER.replace_item(
            "universe_votes",
            universe_votes,
        )

        scores = CONTAINER.read_item(
            item="scores",
            partition_key="scores"
        )
        scores["last_update"] = ""
        scores["points"] = {}
        scores["stars"] = {}
        scores["networth"] = {}
        scores["galaxy_networth"] = {}

        CONTAINER.replace_item(
            "scores",
            scores,
        )
        return func.HttpResponse(
            "Reset state",
            status_code=200,
        )
    except Exception as e:
        logging.warn(str(e))
        return func.HttpResponse(
            "Failed to reset state",
            status_code=500,
        )
    
@APP.function_name(name="GetAccounts")
@APP.route(route="accounts", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_accounts(req: func.HttpRequest) -> func.HttpResponse:
    try:
        accounts = CONTAINER.read_item(
            item="accounts",
            partition_key="accounts",
        )
        return func.HttpResponse(
            json.dumps(accounts),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "Failed to get accounts",
            status_code=500,
        )
    
@APP.function_name(name="UpdateAccounts")
@APP.route(route="accounts", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_accounts(req: func.HttpRequest) -> func.HttpResponse:
    req_body = req.get_json()
    try:
        accounts = CONTAINER.read_item(
            item="accounts",
            partition_key="accounts",
        )
        accounts["accounts"] = req_body["accounts"]
        CONTAINER.replace_item(
            "accounts",
            accounts,
        )
        return func.HttpResponse(
            "Updated accounts",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "Failed to update accounts",
            status_code=500,
        )
    
@APP.function_name(name="GetScores")
@APP.route(route="scores", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_scores(req: func.HttpRequest) -> func.HttpResponse:
    try:
        scores = CONTAINER.read_item(
            item="scores",
            partition_key="scores",
        )
        return func.HttpResponse(
            json.dumps(scores),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "Failed to get scores",
            status_code=500,
        )
    
@APP.function_name(name="UpdateScores")
@APP.route(route="scores", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_scores(req: func.HttpRequest) -> func.HttpResponse:
    req_body = req.get_json()
    try:
        scores = CONTAINER.read_item(
            item="scores",
            partition_key="scores",
        )
        new_scores = {
            **scores,
            **req_body,
        }
        CONTAINER.replace_item(
            "scores",
            new_scores,
        )
        return func.HttpResponse(
            "Updated scores",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "Failed to update scores",
            status_code=500,
        )

    
@APP.function_name(name="CreateGalaxy")
@APP.route(route="galaxy/{galaxyId}", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_galaxy(req: func.HttpRequest) -> func.HttpResponse:
    try:
        galaxies_id = "galaxies"
        galaxies = CONTAINER.read_item(
            item=galaxies_id,
            partition_key=galaxies_id,
        )

        galaxy_id = str(req.route_params.get('galaxyId'))
        if galaxy_id not in galaxies["galaxies"].keys():
            galaxies["galaxies"][galaxy_id] = []
            CONTAINER.replace_item(
                galaxies_id,
                galaxies,
            )
            CONTAINER.create_item(
                {
                    "id": f"galaxy_news_{galaxy_id}",
                    "news": [],
                }
            )
            CONTAINER.create_item(
                {
                    "id": f"galaxy_votes_{galaxy_id}",
                    "votes": {
                        "policy_1": {},
                        "policy_2": {},
                        "leader": {},
                    },
                    "active_policies": [],
                    "leader": "",
                    "policy_1_winner": "",
                    "policy_2_winner": "",
                    "empire_invitations": [],
                    "empire_join_requests": [],
                }
            )
        return func.HttpResponse(
            "Created galaxy",
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not create galaxy",
            status_code=500,
        )

@APP.function_name(name="CreateKingdom")
@APP.route(route="kingdom", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_kingdom(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create kingdom request.')    
    req_body = req.get_json()
    kd_name = req_body.get('kingdom_name')
    galaxy = req_body.get('galaxy')

    # The id is taken with a conditional write on `kingdoms`, and the kingdom added to its galaxy with one on
    # `galaxies`, so two kingdoms created at the same moment get different ids and both stay in their galaxies.
    def take_id(existing_kds):
        kingdoms = existing_kds["kingdoms"]
        if kd_name in kingdoms.values():
            raise Refused("This kingdom already exists")
        # `next_id` survives a round reset, so an id is never reused: a login token from an earlier round
        # (docs/decisions/0005-kingdom-in-the-token.md) names a kingdom that does not exist, not someone else's.
        kd_id = str(max(len(kingdoms), existing_kds.get("next_id", 0)))
        while kd_id in kingdoms:
            kd_id = str(int(kd_id) + 1)
        kingdoms[kd_id] = kd_name
        existing_kds["next_id"] = int(kd_id) + 1
        return kd_id

    def join_galaxy(galaxies):
        if kd_id not in galaxies["galaxies"][galaxy]:
            galaxies["galaxies"][galaxy].append(kd_id)

    try:
        kd_id = change_document(CONTAINER, "kingdoms", take_id)
    except Refused as refused:
        return func.HttpResponse(refused.message, status_code=refused.status_code)
    except TooBusy:
        return func.HttpResponse("Too many kingdoms are being created at once. Try again.", status_code=503)
    try:
        change_document(CONTAINER, "galaxies", join_galaxy)

        for resource_name in [
            "kingdom",
            "siphons_in",
            "siphons_out",
            "news",
            "settles",
            "mobis",
            "structures",
            "missiles",
            "engineers",
            "revealed",
            "shared",
            "pinned",
            "spy_history",
            "attack_history",
            "missile_history",
            "messages",
            "notifs",
            "history",
        ]:
            CONTAINER.create_item(
                {
                    "id": f"{resource_name}_{kd_id}",
                    "kdId": kd_id,
                    "type": resource_name,
                }
            )
        return func.HttpResponse(
            kd_id,
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "The kingdom was not created",
            status_code=500,
        )

@APP.function_name(name="GetItem")
@APP.route(route="item", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_item(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create item request.')    
    req_body = req.get_json()
    item = req_body.get('item')

    item_contents = CONTAINER.read_item(
        item=item,
        partition_key=item,
    )
    try:
        return func.HttpResponse(
            json.dumps(item_contents),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            f"{item} state was not created",
            status_code=500,
        )

@APP.function_name(name="CreateItem")
@APP.route(route="createitem", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_item(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create item request.')    
    req_body = req.get_json()
    item = req_body.get('item')
    state = req_body.get('state')

    try:
        item_contents = CONTAINER.read_item(
            item=item,
            partition_key=item,
        )
    except:
        CONTAINER.create_item(
            {
                "id": item,
                **state,
            }
        )
        return func.HttpResponse(
            f"Successfully created {item} state",
            status_code=201,
        )
    try:
        CONTAINER.replace_item(
            item,
            {
                **item_contents,
                **state,
            },
        )
        return func.HttpResponse(
            f"Successfully created {item} state",
            status_code=201,
        )
    except:
        return func.HttpResponse(
            f"{item} state was not created",
            status_code=500,
        )

@APP.function_name(name="GetKingdoms")
@APP.route(route="kingdoms", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_kingdoms(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get kingdoms request.')    
    item_id = f"kingdoms"
    try:
        kd = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(kd),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve kingdoms info",
            status_code=500,
        )


@APP.function_name(name="UpdateKingdoms")
@APP.route(route="kingdoms", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_kingdoms(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update kingdoms request.')    
    req_body = req.get_json()
    item_id = f"kingdoms"
    kingdoms = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        update_kd = {**kingdoms, **req_body}
        CONTAINER.replace_item(
            item_id,
            update_kd,
        )
        return func.HttpResponse(
            "Kingdoms updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdoms were not updated",
            status_code=500,
        )


@APP.function_name(name="GetGalaxies")
@APP.route(route="galaxies", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_galaxies(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get galaxies request.')    
    item_id = f"galaxies"
    try:
        galaxies = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(galaxies),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve galaxies info",
            status_code=500,
        )


@APP.function_name(name="GetGalaxyPolitics")
@APP.route(route="galaxy/{galaxy_id}/politics", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_galaxy_politics(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get galaxy politics request.')    
    galaxy_id = str(req.route_params.get('galaxy_id'))
    item_id = f"galaxy_votes_{galaxy_id}"
    try:
        galaxy_votes = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(galaxy_votes),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve galaxy politics info",
            status_code=500,
        )


@APP.function_name(name="UpdateGalaxyPolitics")
@APP.route(route="galaxy/{galaxy_id}/politics", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_galaxy_politics(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a galaxy politics update request.')    
    req_body = req.get_json()
    galaxy_id = str(req.route_params.get('galaxy_id'))
    item_id = f"galaxy_votes_{galaxy_id}"
    galaxy_votes = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        update_galaxy_votes = {**galaxy_votes, **req_body}
        CONTAINER.replace_item(
            item_id,
            update_galaxy_votes,
        )
        return func.HttpResponse(
            "Galaxy politics updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The galaxy politics were not updated",
            status_code=500,
        )


@APP.function_name(name="GetEmpirePolitics")
@APP.route(route="empire/{empire_id}/politics", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_empire_politics(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get empire politics request.')    
    empire_id = str(req.route_params.get('empire_id'))
    item_id = f"empire_politics_{empire_id}"
    try:
        empire_politics = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(empire_politics),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve empire politics info",
            status_code=500,
        )


@APP.function_name(name="UpdateEmpirePolitics")
@APP.route(route="empire/{empire_id}/politics", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_empire_politics(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a empire politics update request.')    
    req_body = req.get_json()
    empire_id = str(req.route_params.get('empire_id'))
    item_id = f"empire_politics_{empire_id}"
    empire_politics = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        update_empire_politics = {**empire_politics, **req_body}
        CONTAINER.replace_item(
            item_id,
            update_empire_politics,
        )
        return func.HttpResponse(
            "Empire politics updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The empire politics were not updated",
            status_code=500,
        )


@APP.function_name(name="GetUniverseVotes")
@APP.route(route="universevotes", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_universe_votes(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get universe votes request.')    
    item_id = f"universe_votes"
    try:
        universe_votes = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(universe_votes),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve universe politics info",
            status_code=500,
        )


@APP.function_name(name="UpdateUniversePolitics")
@APP.route(route="universepolitics", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_universe_politics(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a universe politics update request.')    
    req_body = req.get_json()
    item_id = f"universe_votes"
    universe_votes = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        update_universe_votes = {**universe_votes, **req_body}
        CONTAINER.replace_item(
            item_id,
            update_universe_votes,
        )
        return func.HttpResponse(
            "Universe politics updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The universe politics were not updated",
            status_code=500,
        )

@APP.function_name(name="GetEmpires")
@APP.route(route="empires", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_empires(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get empires request.')    
    item_id = f"empires"
    try:
        empires = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(empires),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve empires info",
            status_code=500,
        )

@APP.function_name(name="CreateEmpire")
@APP.route(route="empire", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_empire(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create empire request.')    
    req_body = req.get_json()
    empire_name = req_body.get('empire_name')
    galaxy_id = req_body.get("galaxy_id")
    leader = req_body.get("leader")

    # Decided with a conditional write on `empires`: two empires created at once get different ids, and a galaxy that
    # is already in an empire (a double click, or a join that landed first) can not found another.
    def take_id(empires):
        if any(galaxy_id in empire.get("galaxies", []) for empire in empires["empires"].values()):
            raise Refused("This galaxy is already in an Empire", status_code=409)
        empire_id = str(len(empires["empires"]))
        while empire_id in empires["empires"]:
            empire_id = str(int(empire_id) + 1)
        empires["empires"][empire_id] = {
            "name": empire_name,
            "galaxies": [galaxy_id],
            "aggression": {},
            "num_kingdoms": 0,
            "aggression_max": 999,
            "war": [],
            "peace": {},
            "denounced": "",
            "denounced_expires": "",
            "surprise_war_penalty": False,
            "surprise_war_penalty_expires": "",
        }
        return empire_id

    try:
        empire_id = change_document(CONTAINER, "empires", take_id)
    except Refused as refused:
        return func.HttpResponse(refused.message, status_code=refused.status_code)
    except TooBusy:
        return func.HttpResponse("Too many empires are being created at once. Try again.", status_code=503)
    try:
        CONTAINER.create_item(
            {
                "id": f"empire_politics_{empire_id}",
                "empire_invitations": [],
                "empire_join_requests": [],
                "surrender_offers_sent": [],
                "surrender_offers_received": [],
                "surrender_requests_sent": [],
                "surrender_requests_received": [],
                "leader": leader,
            }
        )
        CONTAINER.create_item(
            {
                "id": f"empire_news_{empire_id}",
                "news": [],
            }
        )
        return func.HttpResponse(
            empire_id,
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "The empire was not created",
            status_code=500,
        )


@APP.function_name(name="UpdateEmpires")
@APP.route(route="empires", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_empires(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update empires request.')    
    req_body = req.get_json()
    item_id = f"empires"
    empires = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        update_kd = {**empires, **req_body}
        CONTAINER.replace_item(
            item_id,
            update_kd,
        )
        return func.HttpResponse(
            "Empires updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The empires were not updated",
            status_code=500,
        )

@APP.function_name(name="GetKingdom")
@APP.route(route="kingdom/{kdId:int}", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_kingdom(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get kingdom request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"kingdom_{kd_id}"
    try:
        kd = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(kd),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve kingdom info",
            status_code=500,
        )


@APP.function_name(name="UpdateKingdom")
@APP.route(route="kingdom/{kdId:int}", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_kingdom(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update kingdom request.')    
    req_body = req.get_json()
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"kingdom_{kd_id}"
    kd = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        update_kd = {**kd, **req_body}
        CONTAINER.replace_item(
            item_id,
            update_kd,
        )
        return func.HttpResponse(
            "Kingdom updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom was not updated",
            status_code=500,
        )

@APP.function_name(name="GetSiphonsIn")
@APP.route(route="kingdom/{kdId:int}/siphonsin", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_siphons_in(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get siphons in request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"siphons_in_{kd_id}"
    try:
        siphons_in = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(siphons_in),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve siphons in info",
            status_code=500,
        )

@APP.function_name(name="GetSiphonsOut")
@APP.route(route="kingdom/{kdId:int}/siphonsout", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_siphons_out(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get siphons out request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"siphons_out_{kd_id}"
    try:
        siphons_out = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(siphons_out),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve siphons out info",
            status_code=500,
        )
        
@APP.function_name(name="UpdateSiphonsOut")
@APP.route(route="kingdom/{kdId:int}/siphonsout", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_siphonsout(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update siphons out request.')    
    req_body = req.get_json()
    new_siphons = req_body.get("new_siphons", None)
    siphons = req_body.get("siphons", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"siphons_out_{kd_id}"
    siphons_out_info = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_siphons:
            siphons_out_info["siphons_out"] = siphons_out_info["siphons_out"] + [new_siphons]
        if siphons != None:
            siphons_out_info["siphons_out"] = siphons
        CONTAINER.replace_item(
            item_id,
            siphons_out_info,
        )
        return func.HttpResponse(
            "Kingdom siphons out updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom siphons out were not updated",
            status_code=500,
        )
        
@APP.function_name(name="UpdateSiphonsIn")
@APP.route(route="kingdom/{kdId:int}/siphonsin", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_siphonsin(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update siphons in request.')    
    req_body = req.get_json()
    new_siphons = req_body.get("new_siphons", None)
    siphons = req_body.get("siphons", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"siphons_in_{kd_id}"
    siphons_in_info = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_siphons:
            siphons_in_info["siphons_in"] = siphons_in_info["siphons_in"] + [new_siphons]
        if siphons != None:
            siphons_in_info["siphons_in"] = siphons
        CONTAINER.replace_item(
            item_id,
            siphons_in_info,
        )
        return func.HttpResponse(
            "Kingdom siphons in updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom siphons in were not updated",
            status_code=500,
        )

@APP.function_name(name="GetNews")
@APP.route(route="kingdom/{kdId:int}/news", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get news request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"news_{kd_id}"
    try:
        news = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(news),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve kingdom news",
            status_code=500,
        )

@APP.function_name(name="GetGalaxyNews")
@APP.route(route="galaxy/{galaxyId}/news", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_galaxy_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get galaxy news request.')    
    galaxy_id = str(req.route_params.get('galaxyId'))
    item_id = f"galaxy_news_{galaxy_id}"
    try:
        news = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(news),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve galaxy news",
            status_code=500,
        )

@APP.function_name(name="UpdateGalaxyNews")
@APP.route(route="galaxy/{galaxyId}/news", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_galaxy_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update news request.')    
    req_body = req.get_json()
    new_news = req_body
    galaxy_id = str(req.route_params.get('galaxyId'))
    item_id = f"galaxy_news_{galaxy_id}"
    news = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if isinstance(new_news, dict):
            news["news"] = [new_news] + news["news"]
        else:
            news["news"] = new_news + news["news"]
        CONTAINER.replace_item(
            item_id,
            news,
        )
        return func.HttpResponse(
            "Kingdom news updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom news was not updated",
            status_code=500,
        )

@APP.function_name(name="GetEmpireNews")
@APP.route(route="empire/{empireId:int}/news", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_empire_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get empire news request.')    
    empire_id = str(req.route_params.get('empireId'))
    item_id = f"empire_news_{empire_id}"
    try:
        news = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(news),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve empire news",
            status_code=500,
        )

@APP.function_name(name="GetUniverseNews")
@APP.route(route="universenews", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_universe_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get universe news request.')    
    item_id = f"universe_news"
    try:
        news = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(news),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve universe news",
            status_code=500,
        )

@APP.function_name(name="UpdateNews")
@APP.route(route="kingdom/{kdId:int}/news", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update news request.')    
    req_body = req.get_json()
    new_news = req_body
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"news_{kd_id}"
    news = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if isinstance(new_news, dict):
            news["news"] = [new_news] + news["news"]
        else:
            news["news"] = new_news + news["news"]
        CONTAINER.replace_item(
            item_id,
            news,
        )
        return func.HttpResponse(
            "Kingdom news updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom news was not updated",
            status_code=500,
        )

@APP.function_name(name="UpdateEmpireNews")
@APP.route(route="empire/{empireId:int}/news", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_empire_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update empire news request.')  
    try:  
        req_body = req.get_json()
        new_news = req_body["news"]
        empire_id = str(req.route_params.get('empireId'))
        item_id = f"empire_{empire_id}"
        news = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        if isinstance(new_news, dict):
            news["news"] = [new_news] + news["news"]
        else:
            news["news"] = new_news + news["news"]
        CONTAINER.replace_item(
            item_id,
            news,
        )
        return func.HttpResponse(
            "Empire news updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The Empire news was not updated",
            status_code=500,
        )

@APP.function_name(name="UpdateUniverseNews")
@APP.route(route="universenews", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_universe_news(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update universe news request.')  
    try:  
        req_body = req.get_json()
        new_news = req_body["news"]
        item_id = f"universe_news"
        news = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        if isinstance(new_news, dict):
            news["news"] = [new_news] + news["news"]
        else:
            news["news"] = new_news + news["news"]
        CONTAINER.replace_item(
            item_id,
            news,
        )
        return func.HttpResponse(
            "Universe news updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The Universe news was not updated",
            status_code=500,
        )

@APP.function_name(name="GetMessages")
@APP.route(route="kingdom/{kdId:int}/messages", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_messages(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get messages request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"messages_{kd_id}"
    try:
        messages = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(messages),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve kingdom messages",
            status_code=500,
        )

@APP.function_name(name="UpdateMessages")
@APP.route(route="kingdom/{kdId:int}/messages", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_messages(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update messages request.')    
    req_body = req.get_json()
    new_messages = req_body
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"messages_{kd_id}"
    messages = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if isinstance(new_messages, dict):
            messages["messages"] = [new_messages] + messages["messages"][0:99]
        else:
            messages["messages"] = new_messages + messages["messages"][0:99]
        CONTAINER.replace_item(
            item_id,
            messages,
        )
        return func.HttpResponse(
            "Kingdom messages updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom messages was not updated",
            status_code=500,
        )

@APP.function_name(name="GetNotifs")
@APP.route(route="kingdom/{kdId:int}/notifs", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_notifs(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get notifs request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"notifs_{kd_id}"
    try:
        notifs = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(notifs),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve kingdom notifs",
            status_code=500,
        )

@APP.function_name(name="UpdateNotifs")
@APP.route(route="kingdom/{kdId:int}/notifs", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_notifs(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update notifs request.')    
    req_body = req.get_json()
    add_categories = req_body.get("add_categories", [])
    clear_categories = req_body.get("clear_categories", [])

    kd_id = str(req.route_params.get('kdId'))
    item_id = f"notifs_{kd_id}"
    notifs = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        for add_cat in add_categories:
            notifs[add_cat] += 1
        for clear_cat in clear_categories:
            notifs[clear_cat] = 0
        CONTAINER.replace_item(
            item_id,
            notifs,
        )
        return func.HttpResponse(
            "Kingdom notifs updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom notifs was not updated",
            status_code=500,
        )

@APP.function_name(name="GetSettles")
@APP.route(route="kingdom/{kdId:int}/settles", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_settles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get settles request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"settles_{kd_id}"
    settles = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(settles),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom settles could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdateSettles")
@APP.route(route="kingdom/{kdId:int}/settles", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_settles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update settles request.')    
    req_body = req.get_json()
    new_settles = req_body.get("new_settles", None)
    replace_settles = req_body.get("settles", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"settles_{kd_id}"
    settles = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_settles:
            settles["settles"] = coalesce(settles["settles"] + new_settles)
        if replace_settles != None:
            settles["settles"] = replace_settles
        CONTAINER.replace_item(
            item_id,
            settles,
        )
        return func.HttpResponse(
            "Kingdom settles updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom settles were not updated",
            status_code=500,
        )

@APP.function_name(name="GetMobis")
@APP.route(route="kingdom/{kdId:int}/mobis", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_mobis(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get mobis request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"mobis_{kd_id}"
    mobis = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(mobis),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom mobis could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdateMobis")
@APP.route(route="kingdom/{kdId:int}/mobis", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_mobis(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update mobis request.')    
    req_body = req.get_json()
    new_mobis = req_body.get("new_mobis", None)
    replace_mobis = req_body.get("mobis", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"mobis_{kd_id}"
    mobis = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_mobis:
            mobis["mobis"] = coalesce(mobis["mobis"] + new_mobis)
        if replace_mobis != None:
            mobis["mobis"] = replace_mobis
        CONTAINER.replace_item(
            item_id,
            mobis,
        )
        return func.HttpResponse(
            "Kingdom mobis updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom mobis were not updated",
            status_code=500,
        )

@APP.function_name(name="GetStructures")
@APP.route(route="kingdom/{kdId:int}/structures", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_structures(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get structures request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"structures_{kd_id}"
    structures = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(structures),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom structures could not be retrieved",
            status_code=500,
        )
        
@APP.function_name(name="UpdateStructures")
@APP.route(route="kingdom/{kdId:int}/structures", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_structures(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update structures request.')    
    req_body = req.get_json()
    new_structures = req_body.get("new_structures", None)
    replace_structures = req_body.get("structures", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"structures_{kd_id}"
    structures = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_structures:
            structures["structures"] = coalesce(structures["structures"] + new_structures)
        if replace_structures != None:
            structures["structures"] = replace_structures
        CONTAINER.replace_item(
            item_id,
            structures,
        )
        return func.HttpResponse(
            "Kingdom structures updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom structures were not updated",
            status_code=500,
        )

@APP.function_name(name="GetMissiles")
@APP.route(route="kingdom/{kdId:int}/missiles", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_missiles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get missiles request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"missiles_{kd_id}"
    missiles = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(missiles),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom missiles could not be retrieved",
            status_code=500,
        )
        
@APP.function_name(name="UpdateMissiles")
@APP.route(route="kingdom/{kdId:int}/missiles", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_missiles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update missiles request.')    
    req_body = req.get_json()
    new_missiles = req_body.get("new_missiles", None)
    replace_missiles = req_body.get("missiles", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"missiles_{kd_id}"
    missiles = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_missiles:
            missiles["missiles"] = coalesce(missiles["missiles"] + new_missiles)
        if replace_missiles != None:
            missiles["missiles"] = replace_missiles
        CONTAINER.replace_item(
            item_id,
            missiles,
        )
        return func.HttpResponse(
            "Kingdom missiles updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom missiles were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetEngineers")
@APP.route(route="kingdom/{kdId:int}/engineers", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_engineers(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get engineers request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"engineers_{kd_id}"
    engineers = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(engineers),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom engineers could not be retrieved",
            status_code=500,
        )
        
@APP.function_name(name="UpdateEngineers")
@APP.route(route="kingdom/{kdId:int}/engineers", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_engineers(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update engineers request.')    
    req_body = req.get_json()
    new_engineers = req_body.get("new_engineers", None)
    replace_engineers = req_body.get("engineers", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"engineers_{kd_id}"
    engineers = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_engineers:
            engineers["engineers"] = coalesce(engineers["engineers"] + new_engineers)
        if replace_engineers != None:
            engineers["engineers"] = replace_engineers
        CONTAINER.replace_item(
            item_id,
            engineers,
        )
        return func.HttpResponse(
            "Kingdom engineers updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom engineers were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetRevealed")
@APP.route(route="kingdom/{kdId:int}/revealed", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_revealed(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get revealed request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"revealed_{kd_id}"
    revealed = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(revealed),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom revealed could not be retrieved",
            status_code=500,
        )
        
@APP.function_name(name="UpdateRevealed")
@APP.route(route="kingdom/{kdId:int}/revealed", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_revealed(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update revealed request.')    
    req_body = req.get_json()
    new_revealed = req_body.get("new_revealed", None)
    new_galaxies = req_body.get("new_galaxies", None)
    new_revealed_galaxymates = req_body.get("new_revealed_galaxymates", None)
    new_revealed_to_galaxymates = req_body.get("new_revealed_to_galaxymates", None)
    revealed = req_body.get("revealed", None)
    galaxies = req_body.get("galaxies", None)
    revealed_galaxymates = req_body.get("revealed_galaxymates", None)
    revealed_to_galaxymates = req_body.get("revealed_to_galaxymates", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"revealed_{kd_id}"
    revealed_info = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        if new_revealed:
            current_revealed = revealed_info["revealed"]
            for kd_id, revealed_dict in new_revealed.items():
                kd_revealed = current_revealed.get(kd_id, {})
                current_revealed[kd_id] = {
                    **kd_revealed,
                    **revealed_dict,
                }
            revealed_info["revealed"] = current_revealed
        if new_galaxies:
            revealed_info["galaxies"] = {
                **revealed_info["galaxies"],
                **new_galaxies,
            }
        if new_revealed_galaxymates:
            revealed_info["revealed_galaxymates"] += new_revealed_galaxymates
        if new_revealed_to_galaxymates:
            revealed_info["revealed_to_galaxymates"] += new_revealed_to_galaxymates
        if revealed != None:
            revealed_info["revealed"] = revealed
        if galaxies != None:
            revealed_info["galaxies"] = galaxies
        if revealed_galaxymates != None:
            revealed_info["revealed_galaxymates"] = revealed_galaxymates
        if revealed_to_galaxymates != None:
            revealed_info["revealed_to_galaxymates"] = revealed_to_galaxymates
        CONTAINER.replace_item(
            item_id,
            revealed_info,
        )
        return func.HttpResponse(
            "Kingdom revealed updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom revealed were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetShared")
@APP.route(route="kingdom/{kdId:int}/shared", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_shared(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get shared request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"shared_{kd_id}"
    shared = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(shared),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom shared could not be retrieved",
            status_code=500,
        )
        
@APP.function_name(name="SetShared")
@APP.route(route="kingdom/{kdId:int}/shared", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
@retry_on_conflict
def set_shared(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a set shared request.')        
    req_body = req.get_json()

    kd_id = str(req.route_params.get('kdId'))
    item_id = f"shared_{kd_id}"
    shared = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    new_shared = {
        **shared,
        **req_body,
    }
    try:
        CONTAINER.replace_item(
            item_id,
            new_shared,
        )
        return func.HttpResponse(
            "Kingdom shared set.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom shared could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdateShared")
@APP.route(route="kingdom/{kdId:int}/shared", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_shared(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update shared request.')    
    req_body = req.get_json()
    new_shared = req_body["shared"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"shared_{kd_id}"
    shared = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        shared["shared"] = shared["shared"] + new_shared
        CONTAINER.replace_item(
            item_id,
            shared,
        )
        return func.HttpResponse(
            "Kingdom shared updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom shared were not updated",
            status_code=500,
        )

@APP.function_name(name="UpdateSharedRequests")
@APP.route(route="kingdom/{kdId:int}/sharedrequests", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_shared_requests(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update shared_requests request.')    
    req_body = req.get_json()
    new_shared_requests = req_body["shared_requests"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"shared_requests_{kd_id}"
    shared_requests = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        shared_requests["shared_requests"] = shared_requests["shared_requests"] + new_shared_requests
        CONTAINER.replace_item(
            item_id,
            shared_requests,
        )
        return func.HttpResponse(
            "Kingdom shared_requests updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom shared_requests were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetPinned")
@APP.route(route="kingdom/{kdId:int}/pinned", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_pinned(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get pinned request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"pinned_{kd_id}"
    pinned = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(pinned),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom pinned could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdatePinned")
@APP.route(route="kingdom/{kdId:int}/pinned", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_pinned(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update pinned request.')    
    req_body = req.get_json()
    new_pinned = req_body.get("pinned", [])
    new_unpinned = req_body.get("unpinned", [])
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"pinned_{kd_id}"
    pinned = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        pinned["pinned"] = pinned["pinned"] + new_pinned
        pinned["pinned"] = [
            kd
            for kd in pinned["pinned"]
            if kd not in new_unpinned
        ]
        CONTAINER.replace_item(
            item_id,
            pinned,
        )
        return func.HttpResponse(
            "Kingdom pinned updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom pinned were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetSpyHistory")
@APP.route(route="kingdom/{kdId:int}/spyhistory", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_spyhistory(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get spyhistory request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"spy_history_{kd_id}"
    spyhistory = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(spyhistory),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom spyhistory could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdateSpyHistory")
@APP.route(route="kingdom/{kdId:int}/spyhistory", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_spy_history(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update spy_history request.')    
    req_body = req.get_json()
    new_spy_history = req_body
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"spy_history_{kd_id}"
    spy_history = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        spy_history["spy_history"] = [new_spy_history] + spy_history["spy_history"]
        CONTAINER.replace_item(
            item_id,
            spy_history,
        )
        return func.HttpResponse(
            "Kingdom spy_history updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom spy_history were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetAttackHistory")
@APP.route(route="kingdom/{kdId:int}/attackhistory", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_attackhistory(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get attackhistory request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"attack_history_{kd_id}"
    attackhistory = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(attackhistory),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom attackhistory could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdateAttackHistory")
@APP.route(route="kingdom/{kdId:int}/attackhistory", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_attack_history(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update attack_history request.')    
    req_body = req.get_json()
    new_attack_history = req_body
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"attack_history_{kd_id}"
    attack_history = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        attack_history["attack_history"] = [new_attack_history] + attack_history["attack_history"]
        CONTAINER.replace_item(
            item_id,
            attack_history,
        )
        return func.HttpResponse(
            "Kingdom attack_history updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom attack_history were not updated",
            status_code=500,
        )
        
@APP.function_name(name="GetMissileHistory")
@APP.route(route="kingdom/{kdId:int}/missilehistory", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_missilehistory(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get missilehistory request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"missile_history_{kd_id}"
    missilehistory = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        return func.HttpResponse(
            json.dumps(missilehistory),
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom missilehistory could not be retrieved",
            status_code=500,
        )

@APP.function_name(name="UpdateMissileHistory")
@APP.route(route="kingdom/{kdId:int}/missilehistory", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_missile_history(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update missile_history request.')    
    req_body = req.get_json()
    new_missile_history = req_body
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"missile_history_{kd_id}"
    missile_history = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        missile_history["missile_history"] = [new_missile_history] + missile_history["missile_history"]
        CONTAINER.replace_item(
            item_id,
            missile_history,
        )
        return func.HttpResponse(
            "Kingdom missile_history updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom missile_history were not updated",
            status_code=500,
        )

@APP.function_name(name="GetHistory")
@APP.route(route="kingdom/{kdId:int}/history", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_history(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a get history request.')    
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"history_{kd_id}"
    try:
        history = CONTAINER.read_item(
            item=item_id,
            partition_key=item_id,
        )
        return func.HttpResponse(
            json.dumps(history),
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "Could not retrieve history info",
            status_code=500,
        )
@APP.function_name(name="UpdateHistory")
@APP.route(route="kingdom/{kdId:int}/history", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_history(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update history request.')    
    req_body = req.get_json()
    new_history = req_body.get("history", {})
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"history_{kd_id}"
    history = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        for key_history, item_history in new_history.items():
            history["history"][key_history].append(item_history)
        CONTAINER.replace_item(
            item_id,
            history,
        )
        return func.HttpResponse(
            "Kingdom history updated.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom history were not updated",
            status_code=500,
        )


# --- Users -------------------------------------------------------------------------------------------------------
#
# One document per user (``user_<id>``), one per username (``username_<hex of the UTF-8 username>``, holding the
# user id: creating it is the uniqueness check) and a counter for the next numeric id (``user_counter``). See
# docs/data-model.md. Unlike the older handlers above, these let unexpected errors surface with their real status.

USER_PREFIX = "user_"
USERNAME_PREFIX = "username_"
USER_COUNTER_ID = "user_counter"


def is_user_document(item_id):
    """Users outlive a round: /resetstate keeps these and /deleteall removes them rather than blanking them."""
    return item_id.startswith(USER_PREFIX) or item_id.startswith(USERNAME_PREFIX)


def _json_response(document, status_code=200):
    return func.HttpResponse(json.dumps(document), status_code=status_code, mimetype="application/json")


def _read_or_none(item_id):
    try:
        return CONTAINER.read_item(item=item_id, partition_key=item_id)
    except CosmosResourceNotFoundError:
        return None


def _create_or_conflict(document, what):
    try:
        created = CONTAINER.create_item(document)
    except CosmosResourceExistsError:
        return func.HttpResponse(f"{what} already exists", status_code=409)
    return _json_response(created, status_code=201)


def _non_negative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _username_key(req):
    """The route's key, if it is lowercase hex of whole bytes (the only form Flask sends), else None."""
    key = req.route_params.get("key", "")
    if not re.fullmatch(r"[0-9a-f]+", key) or len(key) % 2:
        return None
    return key


@APP.function_name(name="GetUser")
@APP.route(route="user/{userId:int}", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_user(req: func.HttpRequest) -> func.HttpResponse:
    user = _read_or_none(f"{USER_PREFIX}{req.route_params.get('userId')}")
    if user is None:
        return func.HttpResponse("No such user", status_code=404)
    return _json_response(user)


@APP.function_name(name="CreateUser")
@APP.route(route="user", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_user(req: func.HttpRequest) -> func.HttpResponse:
    """Body: the user's fields plus ``id_number`` (int). Creates ``user_<id_number>``; 409 if it exists."""
    body = req.get_json()
    if not isinstance(body, dict) or not _non_negative_int(body.get("id_number")):
        return func.HttpResponse("id_number must be a non-negative integer", status_code=400)
    return _create_or_conflict({**body, "id": f"{USER_PREFIX}{body['id_number']}"}, "User")


@APP.function_name(name="UpdateUser")
@APP.route(route="user/{userId:int}", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_user(req: func.HttpRequest) -> func.HttpResponse:
    """Shallow merge into ``user_<id>``. Honours If-Match (412). ``id`` and ``id_number`` are never changed."""
    item_id = f"{USER_PREFIX}{req.route_params.get('userId')}"
    body = req.get_json()
    if not isinstance(body, dict):
        return func.HttpResponse("The body must be an object", status_code=400)
    user = _read_or_none(item_id)
    if user is None:
        return func.HttpResponse("No such user", status_code=404)
    changes = {key: value for key, value in body.items() if key not in ("id", "id_number")}
    try:
        CONTAINER.replace_item(item_id, {**user, **changes})
    except CosmosAccessConditionFailedError:
        # retry_on_conflict has noted the conflict: it runs this again, or answers 412 to an If-Match caller
        return func.HttpResponse("Conflict", status_code=412)
    return func.HttpResponse("User updated", status_code=200)


@APP.function_name(name="GetUserCounter")
@APP.route(route="usercounter", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_user_counter(req: func.HttpRequest) -> func.HttpResponse:
    """The next free user id. Created with ``next_id: 1`` the first time it is read, so it always exists."""
    counter = _read_or_none(USER_COUNTER_ID)
    if counter is None:
        try:
            counter = CONTAINER.create_item({"id": USER_COUNTER_ID, "next_id": 1})
        except CosmosResourceExistsError:  # another request created it first
            counter = CONTAINER.read_item(item=USER_COUNTER_ID, partition_key=USER_COUNTER_ID)
    return _json_response(counter)


@APP.function_name(name="UpdateUserCounter")
@APP.route(route="usercounter", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
@retry_on_conflict
def update_user_counter(req: func.HttpRequest) -> func.HttpResponse:
    """Body ``{"next_id": <int>}``. Callers send If-Match (``occ.update``), so two sign-ups never take the same id."""
    body = req.get_json()
    if not isinstance(body, dict) or not _non_negative_int(body.get("next_id")):
        return func.HttpResponse("next_id must be a non-negative integer", status_code=400)
    counter = _read_or_none(USER_COUNTER_ID)
    if counter is None:
        return func.HttpResponse("No user counter", status_code=404)
    try:
        CONTAINER.replace_item(USER_COUNTER_ID, {**counter, "next_id": body["next_id"]})
    except CosmosAccessConditionFailedError:
        return func.HttpResponse("Conflict", status_code=412)
    return func.HttpResponse("User counter updated", status_code=200)


@APP.function_name(name="GetUsername")
@APP.route(route="username/{key}", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_username(req: func.HttpRequest) -> func.HttpResponse:
    key = _username_key(req)
    if key is None:
        return func.HttpResponse("The key must be lowercase hex", status_code=400)
    claim = _read_or_none(f"{USERNAME_PREFIX}{key}")
    if claim is None:
        return func.HttpResponse("No such username", status_code=404)
    return _json_response(claim)


@APP.function_name(name="CreateUsername")
@APP.route(route="username/{key}", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_username(req: func.HttpRequest) -> func.HttpResponse:
    """Body ``{"user_id": <int>}``. Claims the username; 409 if it is taken. Creating the document is the check."""
    key = _username_key(req)
    if key is None:
        return func.HttpResponse("The key must be lowercase hex", status_code=400)
    body = req.get_json()
    if not isinstance(body, dict) or not _non_negative_int(body.get("user_id")):
        return func.HttpResponse("user_id must be a non-negative integer", status_code=400)
    return _create_or_conflict({"id": f"{USERNAME_PREFIX}{key}", "user_id": body["user_id"]}, "Username")


# query parameter -> the clause it adds. Every value is compared as a string (kd_id is a string, like kingdom ids).
USER_QUERY_FILTERS = {
    "email": "c.email = @email",
    "kd_id": "c.kd_id = @kd_id",
    "prefix": "STARTSWITH(c.username, @prefix)",
}


@APP.function_name(name="GetUsers")
@APP.route(route="users", auth_level=func.AuthLevel.ADMIN, methods=["GET"])
def get_users(req: func.HttpRequest) -> func.HttpResponse:
    """
    Every user, or those matching all the filters given (``email``, ``kd_id``, ``prefix`` of the username), in id
    order, as ``{"users": [...]}``.

    One cross-partition query: for admin and rare lookups (email recovery, bot names), never a hot path.
    """
    clauses = ["IS_DEFINED(c.id_number)"]
    parameters = []
    for name, clause in USER_QUERY_FILTERS.items():
        value = req.params.get(name)
        if value is not None:
            clauses.append(clause)
            parameters.append({"name": f"@{name}", "value": str(value)})
    users = list(CONTAINER.query_items(
        query="SELECT * FROM c WHERE " + " AND ".join(clauses),
        parameters=parameters,
        enable_cross_partition_query=True,
    ))
    users.sort(key=lambda user: user["id_number"])
    return _json_response({"users": users})
