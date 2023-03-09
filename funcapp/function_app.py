import azure.functions as func
import logging
import os
import json
import datetime
from collections import defaultdict

from azure.cosmos import CosmosClient, PartitionKey

ENDPOINT = os.environ["COSMOS_ENDPOINT"]
KEY = os.environ["COSMOS_KEY"]

DATABASE_NAME = "dev"
CONTAINER_NAME = "data"

CLIENT = CosmosClient(url=ENDPOINT, credential=KEY)
DATABASE = CLIENT.create_database_if_not_exists(id=DATABASE_NAME)
CONTAINER = DATABASE.get_container_client(CONTAINER_NAME)

APP = func.FunctionApp()



@APP.function_name(name="CreateState")
@APP.route(route="init", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def init_state(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create initial game state.')

    try:
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
                "policies": {},
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

@APP.function_name(name="CreateKingdom")
@APP.route(route="kingdom", auth_level=func.AuthLevel.ADMIN, methods=["POST"])
def create_kingdom(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a create kingdom request.')    
    req_body = req.get_json()
    kd_name = req_body.get('kingdom_name')

    existing_kds = CONTAINER.read_item(
        item="kingdoms",
        partition_key="kingdoms",
    )
    if kd_name in existing_kds["kingdoms"]:
        return func.HttpResponse(
            "This kingdom already exists",
            status_code=400,
        )
    try:
        kd_id = str(len(existing_kds["kingdoms"]))
        existing_kds["kingdoms"][kd_name] = kd_id
        CONTAINER.replace_item(
            "kingdoms",
            existing_kds,
        )
        for resource_name in [
            "kingdom",
            "news",
            "settles",
            "mobis",
            "structures",
            "missiles",
            "engineers",
            "revealed",
            "shared",
            "shared_requests",
            "pinned",
            "spy_history",
            "attack_history",
            "missile_history",
        ]:
            CONTAINER.create_item(
                {
                    "id": f"{resource_name}_{kd_id}",
                    "kdId": kd_id,
                    "type": resource_name,
                    resource_name: [],
                }
            )
        return func.HttpResponse(
            "Kingdom created.",
            status_code=201,
        )
    except:
        return func.HttpResponse(
            "The kingdom was not created",
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
        if isinstance(new_news, str):
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
def update_settles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update settles request.')    
    req_body = req.get_json()
    new_settles = req_body["settles"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"settles_{kd_id}"
    settles = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        settles["settles"] = settles["settles"] + new_settles
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

@APP.function_name(name="ResolveSettles")
@APP.route(route="kingdom/{kdId:int}/resolvesettles", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_settles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve settles request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        settles_id = f"settles_{kd_id}"
        settles = CONTAINER.read_item(
            item=settles_id,
            partition_key=settles_id,
        )
        ready_settles = []
        keep_settles = []
        for settle in settles:
            if datetime.datetime.fromtimestamp(settle["time"]) < timestamp:
                ready_settles.append(settle['stars'])
            else:
                keep_settles.append(settle)
        new_stars = sum(ready_settles)
        kd_info_id = f"kingdom_{kd_id}"
        kd_info = CONTAINER.read_item(
            item=kd_info_id,
            partition_key=kd_info_id,
        )
        kd_info['stars'] += new_stars

        CONTAINER.replace_item(
            settles_id,
            keep_settles,
        )
        CONTAINER.replace_item(
            kd_info_id,
            kd_info,
        )
        return func.HttpResponse(
            "Kingdom settles resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom settles were not resolved",
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
def update_mobis(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update mobis request.')    
    req_body = req.get_json()
    new_mobis = req_body["mobis"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"mobis_{kd_id}"
    mobis = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        mobis["mobis"] = mobis["mobis"] + new_mobis
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

@APP.function_name(name="ResolveMobis")
@APP.route(route="kingdom/{kdId:int}/resolvemobis", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_mobis(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve mobis request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        mobis_id = f"mobis_{kd_id}"
        mobis = CONTAINER.read_item(
            item=mobis_id,
            partition_key=mobis_id,
        )
        ready_mobis = defaultdict(int)
        keep_mobis = []
        for mobi in mobis:
            if datetime.datetime.fromtimestamp(mobi["time"]) < timestamp:
                mobi.pop('time')
                for unit, amt in mobi.items():
                    ready_mobis[unit] += amt
            else:
                keep_mobis.append(mobi)

        kd_info_id = f"kingdom_{kd_id}"
        kd_info = CONTAINER.read_item(
            item=kd_info_id,
            partition_key=kd_info_id,
        )
        for unit, amt in ready_mobis.items():
            kd_info['units'][unit] += amt

        CONTAINER.replace_item(
            mobis_id,
            keep_mobis,
        )
        CONTAINER.replace_item(
            kd_info_id,
            kd_info,
        )
        return func.HttpResponse(
            "Kingdom mobis resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom mobis were not resolved",
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
def update_structures(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update structures request.')    
    req_body = req.get_json()
    new_structures = req_body["structures"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"structures_{kd_id}"
    structures = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        structures["structures"] = structures["structures"] + new_structures
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

@APP.function_name(name="ResolveStructures")
@APP.route(route="kingdom/{kdId:int}/resolvestructures", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_structures(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve structures request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        structures_id = f"structures_{kd_id}"
        structures = CONTAINER.read_item(
            item=structures_id,
            partition_key=structures_id,
        )
        ready_structures = defaultdict(int)
        keep_structures = []
        for structure in structures:
            if datetime.datetime.fromtimestamp(structure["time"]) < timestamp:
                structure.pop('time')
                for structure, amt in structure.items():
                    ready_structures[structure] += amt
            else:
                keep_structures.append(structure)

        kd_info_id = f"kingdom_{kd_id}"
        kd_info = CONTAINER.read_item(
            item=kd_info_id,
            partition_key=kd_info_id,
        )
        for structure, amt in ready_structures.items():
            kd_info['structures'][structure] += amt

        CONTAINER.replace_item(
            structures_id,
            keep_structures,
        )
        CONTAINER.replace_item(
            kd_info_id,
            kd_info,
        )
        return func.HttpResponse(
            "Kingdom mobis resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom mobis were not resolved",
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
def update_missiles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update missiles request.')    
    req_body = req.get_json()
    new_missiles = req_body["missiles"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"missiles_{kd_id}"
    missiles = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        missiles["missiles"] = missiles["missiles"] + new_missiles
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

@APP.function_name(name="ResolveMissiles")
@APP.route(route="kingdom/{kdId:int}/resolvemissiles", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_missiles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve missiles request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        missiles_id = f"missiles_{kd_id}"
        missiles = CONTAINER.read_item(
            item=missiles_id,
            partition_key=missiles_id,
        )
        ready_missiles = defaultdict(int)
        keep_missiles = []
        for missile in missiles:
            if datetime.datetime.fromtimestamp(missiles["time"]) < timestamp:
                missile.pop('time')
                for key_missile, amt in missile.items():
                    ready_missiles[key_missile] += amt
            else:
                keep_missiles.append(missile)

        kd_info_id = f"kingdom_{kd_id}"
        kd_info = CONTAINER.read_item(
            item=kd_info_id,
            partition_key=kd_info_id,
        )
        for missile, amt in ready_missiles.items():
            kd_info['missiles'][missile] += amt

        CONTAINER.replace_item(
            missiles_id,
            keep_missiles,
        )
        CONTAINER.replace_item(
            kd_info_id,
            kd_info,
        )
        return func.HttpResponse(
            "Kingdom missiles resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom missiles were not resolved",
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
def update_engineers(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update engineers request.')    
    req_body = req.get_json()
    new_engineers = req_body["engineers"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"engineers_{kd_id}"
    engineers = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        engineers["engineers"] = engineers["engineers"] + new_engineers
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

@APP.function_name(name="ResolveEngineers")
@APP.route(route="kingdom/{kdId:int}/resolveengineers", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_engineers(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve engineers request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        engineers_id = f"engineers_{kd_id}"
        engineers = CONTAINER.read_item(
            item=engineers_id,
            partition_key=engineers_id,
        )
        ready_engineers = 0
        keep_engineers = []
        for engineer in engineers:
            if datetime.datetime.fromtimestamp(engineers["time"]) < timestamp:
                ready_engineers += engineer["amount"]
            else:
                keep_engineers.append(engineer)

        kd_info_id = f"kingdom_{kd_id}"
        kd_info = CONTAINER.read_item(
            item=kd_info_id,
            partition_key=kd_info_id,
        )
        kd_info['unit']['engineers'] += ready_engineers

        CONTAINER.replace_item(
            engineers_id,
            keep_engineers,
        )
        CONTAINER.replace_item(
            kd_info_id,
            kd_info,
        )
        return func.HttpResponse(
            "Kingdom engineers resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom engineers were not resolved",
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
def update_revealed(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update revealed request.')    
    req_body = req.get_json()
    new_revealed = req_body["revealed"]
    new_galaxies = req_body.get("galaxies", None)
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"revealed_{kd_id}"
    revealed = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        current_revealed = revealed["revealed"]
        for kd_id, revealed_dict in new_revealed.items():
            kd_revealed = current_revealed.get(kd_id, {})
            current_revealed[kd_id] = {
                **kd_revealed,
                **revealed_dict,
            }
        revealed["revealed"] = current_revealed
        if new_galaxies:
            revealed["galaxies"] = {
                **revealed["galaxies"],
                **new_galaxies,
            }
        CONTAINER.replace_item(
            item_id,
            revealed,
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

@APP.function_name(name="ResolveRevealed")
@APP.route(route="kingdom/{kdId:int}/resolverevealed", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_revealed(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve revealed request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        revealed_id = f"revealed_{kd_id}"
        revealed = CONTAINER.read_item(
            item=revealed_id,
            partition_key=revealed_id,
        )
        keep_revealed = [
            i_revealed for i_revealed in revealed
            if datetime.datetime.fromtimestamp(i_revealed["time"]) < timestamp
        ]

        CONTAINER.replace_item(
            revealed_id,
            keep_revealed,
        )
        return func.HttpResponse(
            "Kingdom revealed resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom revealed were not resolved",
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
def get_shared(req: func.HttpRequest) -> func.HttpResponse:
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

@APP.function_name(name="ResolveShared")
@APP.route(route="kingdom/{kdId:int}/resolveshared", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_shared(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve shared request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        shared_id = f"shared_{kd_id}"
        shared = CONTAINER.read_item(
            item=shared_id,
            partition_key=shared_id,
        )
        keep_shared = [
            i_shared for i_shared in shared
            if datetime.datetime.fromtimestamp(i_shared["time"]) < timestamp
        ]

        CONTAINER.replace_item(
            shared_id,
            keep_shared,
        )
        return func.HttpResponse(
            "Kingdom shared resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom shared were not resolved",
            status_code=500,
        )

@APP.function_name(name="UpdateSharedRequests")
@APP.route(route="kingdom/{kdId:int}/sharedrequests", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
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

@APP.function_name(name="ResolveSharedRequests")
@APP.route(route="kingdom/{kdId:int}/resolvesharedrequests", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def resolve_shared_requests(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a resolve shared_requests request.')    
    try:
        req_body = req.get_json()
        timestamp = datetime.datetime.fromtimestamp(req_body["timestamp"])
        kd_id = str(req.route_params.get('kdId'))
        shared_requests_id = f"shared_requests_{kd_id}"
        shared_requests = CONTAINER.read_item(
            item=shared_requests_id,
            partition_key=shared_requests_id,
        )
        keep_shared_requests = [
            i_shared_requests for i_shared_requests in shared_requests
            if datetime.datetime.fromtimestamp(i_shared_requests["time"]) < timestamp
        ]

        CONTAINER.replace_item(
            shared_requests_id,
            keep_shared_requests,
        )
        return func.HttpResponse(
            "Kingdom shared_requests resolved.",
            status_code=200,
        )
    except:
        return func.HttpResponse(
            "The kingdom shared_requests were not resolved",
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

@APP.function_name(name="UpdateMissileHistory")
@APP.route(route="kingdom/{kdId:int}/missilehistory", auth_level=func.AuthLevel.ADMIN, methods=["PATCH"])
def update_missile_history(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed an update missile_history request.')    
    req_body = req.get_json()
    new_missile_history = req_body["missile_history"]
    kd_id = str(req.route_params.get('kdId'))
    item_id = f"missile_history_{kd_id}"
    missile_history = CONTAINER.read_item(
        item=item_id,
        partition_key=item_id,
    )
    try:
        missile_history["missile_history"] = missile_history["missile_history"] + new_missile_history
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