
import collections
import datetime
import json
import math
import os
import time
import random
import uuid

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.misc as uam
import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.shared as uas
from untitledapp import db, User, REQUESTS_SESSION, SOCK_HANDLERS

bp = flask.Blueprint("refresh", __name__)

def _calc_pop_change_per_epoch(
    kd_info_parse,
    fuelless: bool,
    epoch_elapsed,
):
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_info = uag._get_mobis_queue(kd_info_parse["kdId"])
    mobis_units = mobis_info
    int_fuelless = int(fuelless)

    start_time = datetime.datetime.now(datetime.timezone.utc)
    units = uag._calc_units(start_time, current_units, generals_units, mobis_units)
    max_hangar_capacity, current_hangar_capacity = uag._calc_hangar_capacity(kd_info_parse, units)

    overflow = max(current_hangar_capacity - max_hangar_capacity, 0)
    pop_capacity = math.floor(
        kd_info_parse["structures"]["homes"]
        * uas.GAME_CONFIG["BASE_HOMES_CAPACITY"]
        * (
            1 
            - (int_fuelless * uas.GAME_CONFIG["BASE_FUELLESS_POP_CAP_REDUCTION"])
            - (int(kd_info_parse["race"] == "Vult") * uas.GAME_CONFIG["VULT_POPULATION_REDUCTION"])
        )
    )
    
    pop_capacity_less_overflow = max(pop_capacity - overflow, 0)

    pop_difference = pop_capacity_less_overflow - kd_info_parse["population"]
    if pop_difference < 0:
        pct_pop_loss = uas.GAME_CONFIG["BASE_PCT_POP_LOSS_PER_EPOCH"] * kd_info_parse["population"] * epoch_elapsed
        stars_pop_loss = uas.GAME_CONFIG["BASE_POP_LOSS_PER_STAR_PER_EPOCH"] * kd_info_parse["stars"] * epoch_elapsed
        greater_pop_loss = max(pct_pop_loss, stars_pop_loss)
        pop_change = -1 *min(greater_pop_loss, abs(pop_difference))
    elif pop_difference > 0:
        pct_pop_gain = uas.GAME_CONFIG["BASE_PCT_POP_GROWTH_PER_EPOCH"] * kd_info_parse["population"] * epoch_elapsed
        stars_pop_gain = uas.GAME_CONFIG["BASE_POP_GROWTH_PER_STAR_PER_EPOCH"] * kd_info_parse["stars"] * epoch_elapsed
        greater_pop_gain = max(pct_pop_gain, stars_pop_gain) * (1 - int_fuelless * uas.GAME_CONFIG["BASE_FUELLESS_POP_GROWTH_REDUCTION"])
        pop_change = min(greater_pop_gain, pop_difference)
    else:
        pop_change = 0
    
    return pop_change, pop_capacity_less_overflow

def _calc_structures_losses(
    kd_info_parse,
    epoch_elapsed
):

    current_structures = kd_info_parse["structures"]
    count_current_structures = sum(current_structures.values())
    total_structures = {
        k: (
            kd_info_parse["structures"].get(k, 0)
        )
        for k in uas.STRUCTURES
    }
    count_total_structures = (
        count_current_structures
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
    reduction_per_epoch = structures_to_reduce * uas.GAME_CONFIG["BASE_STRUCTURES_LOSS_RETURN_RATE"] * epoch_elapsed
    reduction_per_stars = min(kd_info_parse["stars"] * uas.GAME_CONFIG["BASE_STRUCTURES_LOSS_PER_STAR_PER_EPOCH"] * epoch_elapsed, structures_to_reduce, count_current_structures)
    greater_reduction = max(reduction_per_epoch, reduction_per_stars)

    structures_to_reduce = {
        k: v * greater_reduction
        for k, v in pct_total_structures.items()
    }
    return structures_to_reduce
    
def _resolve_siphons(
    gross_income,
    kd_id,
    time_update,
    epoch_elapsed,
):
    app = flask.current_app
    request_id = str(uuid.uuid4())
    while not uam.acquire_locks([f'/kingdom/{kd_id}/siphonsout', f'/kingdom/{kd_id}/siphonsin'], timeout=999, request_id=request_id):
        time.sleep(0.01)
    try:
        siphons_out = uag._get_siphons_out(kd_id)
        siphons_in = uag._get_siphons_in(kd_id)

        total_siphons = sum([siphon["siphon"] for siphon in siphons_out])
        siphon_pool = min(gross_income * uas.GAME_CONFIG["BASE_MAX_SIPHON"], total_siphons)
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
                    "time": time_expiry.isoformat(),
                    "remaining_siphon": siphon_out["siphon"] - siphon_money,
                }
            }
            siphons_in_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{from_kd}/siphonsin',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsout',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(siphon_out_payload),
        )

        siphon_in_income = sum(siphon["siphon"] for siphon in siphons_in) / epoch_elapsed
        resolve_siphons_in_payload = {
            "siphons": []
        }
        resolve_siphons_in = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsin',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(resolve_siphons_in_payload),
        )
    finally:
        uam.release_locks_by_id(request_id)
    return siphon_pool, siphon_in_income, siphons_in

def _calc_networth(
    kd_info_parse,
    total_units=None,
):
    if not total_units:
        total_units = {
            k: v
            for k, v in kd_info_parse["units"].items()
        }
        for general in kd_info_parse["generals_out"]:
            for key_unit, value_unit in general.items():
                if key_unit == "return_time":
                    continue
                total_units[key_unit] += value_unit

    total_structures = sum(kd_info_parse["structures"].values())
    total_money = sum(kd_info_parse["funding"].values()) + kd_info_parse["money"]

    networth = kd_info_parse["stars"] * uas.GAME_CONFIG["NETWORTH_VALUES"]["stars"]
    networth += (total_structures * uas.GAME_CONFIG["NETWORTH_VALUES"]["structures"])
    networth += (total_money * uas.GAME_CONFIG["NETWORTH_VALUES"]["money"])
    for key_unit, value_unit in total_units.items():
        networth += (value_unit * uas.GAME_CONFIG["NETWORTH_VALUES"][key_unit])
    return networth

def _kingdom_with_income(
    kd_info_parse,
    current_bonuses,
    state,
    time_now,
):
    time_last_income = datetime.datetime.fromisoformat(kd_info_parse["last_income"]).astimezone(datetime.timezone.utc)
    seconds_elapsed = (time_now - time_last_income).total_seconds()
    epoch_elapsed = seconds_elapsed / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]

    is_isolationist = "Isolationist" in state["state"]["active_policies"]
    is_free_trade = "Free Trade" in state["state"]["active_policies"]

    income = {
        "money": {},
        "fuel": {},
    }
    income["money"]["mines"] = math.floor(kd_info_parse["structures"]["mines"]) * uas.GAME_CONFIG["BASE_MINES_INCOME_PER_EPOCH"]
    income["money"]["population"] = math.floor(kd_info_parse["population"]) * uas.GAME_CONFIG["BASE_POP_INCOME_PER_EPOCH"]
    income["money"]["bonus"] = current_bonuses["money_bonus"] - is_isolationist * uas.GAME_CONFIG["BASE_ISOLATIONIST_DECREASE"] + is_free_trade * uas.GAME_CONFIG["BASE_FREE_TRADE_INCREASE"]
    income["money"]["gross"] = (
        income["money"]["mines"]
        + income["money"]["population"]
    ) * (1 + income["money"]["bonus"])
    income["money"]["siphons_out"], income["money"]["siphons_in"], siphons_in = _resolve_siphons(
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

    income["fuel"]["fuel_plants"] = math.floor(kd_info_parse["structures"]["fuel_plants"]) * uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"]
    income["fuel"]["bonus"] = current_bonuses["fuel_bonus"] + (int(kd_info_parse["race"] == "Lumina") * uas.GAME_CONFIG["LUMINA_FUEL_PRODUCTION_INCREASE"])
    income["fuel"]["units"] = {}
    for key_unit, value_units in total_units.items():
        income["fuel"]["units"][key_unit] = value_units * uas.UNITS[key_unit]["fuel"]
    income["fuel"]["population"] = kd_info_parse["population"] * uas.GAME_CONFIG["BASE_POP_FUEL_CONSUMPTION_PER_EPOCH"]
    income["fuel"]["shields"] = {}
    income["fuel"]["shields"]["military"] = kd_info_parse["shields"]["military"] * 100 * kd_info_parse["stars"] * uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT"]
    income["fuel"]["shields"]["spy"] = kd_info_parse["shields"]["spy"] * 100 * kd_info_parse["stars"] * uas.GAME_CONFIG["BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT"]
    income["fuel"]["shields"]["spy_radar"] = kd_info_parse["shields"]["spy_radar"] * 100 * kd_info_parse["stars"] * uas.GAME_CONFIG["BASE_SPY_RADAR_COST_PER_LAND_PER_PCT"]
    income["fuel"]["shields"]["missiles"] = kd_info_parse["shields"]["missiles"] * 100 * kd_info_parse["stars"] * uas.GAME_CONFIG["BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT"]

    new_fuel = income["fuel"]["fuel_plants"] * (1 + income["fuel"]["bonus"])
    raw_fuel_consumption = (
        sum(income["fuel"]["units"].values())
        + sum(income["fuel"]["shields"].values())
        + income["fuel"]["population"]
    )
    income["fuel"]["net"] = new_fuel - raw_fuel_consumption
    net_fuel = income["fuel"]["net"] * epoch_elapsed
    max_fuel = math.floor(kd_info_parse["structures"]["fuel_plants"]) * uas.GAME_CONFIG["BASE_FUEL_PLANTS_CAPACITY"]
    min_fuel = uas.GAME_FUNCS["BASE_NEGATIVE_FUEL_CAP"](kd_info_parse["stars"])

    income["drones"] = (
        math.floor(kd_info_parse["structures"]["drone_factories"])
        * uas.GAME_CONFIG["BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH"]
        * (
            1
            + (int(kd_info_parse["race"] == "Vult") * uas.GAME_CONFIG["VULT_DRONE_PRODUCTION_INCREASE"])
        )
    )
    new_drones = income["drones"] * epoch_elapsed

    fuelless = kd_info_parse["fuel"] <= 0
    pop_change, _ = _calc_pop_change_per_epoch(kd_info_parse, fuelless, epoch_elapsed)
    income["population"] = pop_change / epoch_elapsed

    structures_to_reduce = _calc_structures_losses(kd_info_parse, epoch_elapsed)

    new_project_points = {
        key_project: assigned_engineers * uas.GAME_CONFIG["BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH"] * epoch_elapsed
        for key_project, assigned_engineers in kd_info_parse["projects_assigned"].items()
    }
    new_kd_info = kd_info_parse.copy()
    for key_project, new_points in new_project_points.items():
        new_kd_info["projects_points"][key_project] += new_points
    for key_project in uas.ONE_TIME_PROJECTS:
        if key_project not in kd_info_parse["completed_projects"]:
            if new_kd_info["projects_points"][key_project] >= new_kd_info["projects_max_points"][key_project]:
                new_kd_info["completed_projects"].append(key_project)
                new_kd_info["projects_assigned"][key_project] = 0
                new_kd_info["projects_target"][key_project] = 0
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
    new_kd_info["networth"] = math.floor(_calc_networth(
        new_kd_info,
        total_units,
    ))
    new_kd_info["siphons"] = siphons_in

    if new_kd_info["population"] <= 0:
        new_kd_info["status"] = "Dead"
        uam._mark_kingdom_death(kd_info_parse["kdId"])
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
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/settles', timeout=999):
        time.sleep(0.01)
    try:
        settle_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(settles_payload),
        )
        if ready_settles:
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
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/settles')
    
    return ready_settles, next_resolve
    
def _resolve_mobis(kd_id, time_update):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/mobis', timeout=999):
        time.sleep(0.01)
    try:
        mobis_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(mobis_payload),
        )
        try:
            ws = SOCK_HANDLERS[kd_id]
            count_mobis = sum(ready_mobis.values())
            if count_mobis:
                ws.send(json.dumps({
                    "message": f"Finished mobilizing {count_mobis} units",
                    "status": "info",
                    "category": "Mobis",
                    "delay": 5000,
                    "update": [],
                }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/mobis')
    
    return ready_mobis, next_resolve
    
def _resolve_structures(kd_id, time_update):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/structures', timeout=999):
        time.sleep(0.01)
    try:
        structures_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(structures_payload),
        )
        try:
            ws = SOCK_HANDLERS[kd_id]
            count_structures = sum(ready_structures.values())
            if count_structures:
                ws.send(json.dumps({
                    "message": f"Finished building {count_structures} structures",
                    "status": "info",
                    "category": "Structures",
                    "delay": 5000,
                    "update": [],
                }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/structures')
    
    return ready_structures, next_resolve
    
def _resolve_missiles(kd_id, time_update):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/missiles', timeout=999):
        time.sleep(0.01)
    try:
        missiles_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(missiles_payload),
        )
        try:
            ws = SOCK_HANDLERS[kd_id]
            count_missiles = sum(ready_missiles.values())
            if count_missiles:
                ws.send(json.dumps({
                    "message": f"Finished building {count_missiles} missiles",
                    "status": "info",
                    "category": "Missiles",
                    "delay": 5000,
                    "update": [],
                }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/missiles')
    
    return ready_missiles, next_resolve
    
def _resolve_engineers(kd_id, time_update):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/engineers', timeout=999):
        time.sleep(0.01)
    try:
        engineer_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(engineers_payload),
        )
        if ready_engineers:
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
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/engineers')
    
    return ready_engineers, next_resolve
    
def _resolve_revealed(kd_id, time_update):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/revealed', timeout=999):
        time.sleep(0.01)
    try:
        revealed_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(revealed_payload),
        )
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/revealed')
    
    return next_resolve
    
def _resolve_shared(kd_id, time_update):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}/shared', timeout=999):
        time.sleep(0.01)
    try:
        shared_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(shared_payload),
        )
    finally:
        uam.release_lock(f'/kingdom/{kd_id}/shared')
    
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
        if count_returning_units:
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
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_info_parse["kdId"], galaxies_inverted[kd_info_parse["kdId"]])
    is_intelligence = "Intelligence" in galaxy_policies["active_policies"]
    next_resolve_time = max(
        resolve_time + datetime.timedelta(
            seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_SPY_ATTEMPT_TIME_MULTIPLIER"] * (1 - current_bonuses["spy_bonus"] - int(is_intelligence) * uas.GAME_CONFIG["BASE_INTELLIGENCE_RETURN_REDUCTION"])
        ),
        time_update,
    )
    if kd_info_parse["spy_attempts"] < uas.GAME_CONFIG["BASE_SPY_ATTEMPTS_MAX"]:
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


def _weighted_random_by_dct(dct):
    rand_val = random.random()
    total = 0
    for k, v in dct.items():
        total += v
        if rand_val <= total:
            return k

def _resolve_auto_spending(
    kd_info_parse,
    time_update,
    current_bonuses,
    settle_info=None,
    structures_info=None,
    mobis_info=None,
    engineers_info=None,
):
    app = flask.current_app
    resolve_time = datetime.datetime.fromisoformat(kd_info_parse["next_resolve"]["auto_spending"]).astimezone(datetime.timezone.utc)
    kd_id = kd_info_parse["kdId"]
    request_id = str(uuid.uuid4())
    while not uam.acquire_locks(
        [
            f'/kingdom/{kd_id}/settles',
            f'/kingdom/{kd_id}/structures',
            f'/kingdom/{kd_id}/mobis',
            f'/kingdom/{kd_id}/engineers',
        ], 
        timeout=999, 
        request_id=request_id,
    ):
        time.sleep(0.01)
    try:
        next_resolves = {}

        if settle_info is None:
            settle_info = uag._get_settle(kd_id)
        if structures_info is None:
            structures_info = uag._get_structures_info(kd_id)
        if mobis_info is None:
            mobis_info = uag._get_mobis(kd_id)
        if engineers_info is None:
            engineers_info = uag._get_engineers(kd_id)

        settle_price = settle_info["settle_price"]
        max_available_settle = settle_info["max_available_settle"]
        settle_funding = kd_info_parse["funding"]["settle"]

        new_settles = min(math.floor(settle_funding / settle_price), max_available_settle)
        if new_settles:
            kd_info_parse["funding"]["settle"] = settle_funding - new_settles * settle_price
            
            new_settles_payload, min_settle_time = uab._get_new_settles(kd_info_parse, new_settles, time_update)
            next_resolves["settles"] = min(min_settle_time, kd_info_parse["next_resolve"]["settles"])
            settle_payload = {
                "new_settles": new_settles_payload
            }
            settles_patch_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(settle_payload),
            )
        
        structures_price = structures_info["price"]
        max_available_structures = structures_info["max_available_structures"]
        structures_funding = kd_info_parse["funding"]["structures"]
        structures_to_build = min(math.floor(structures_funding / structures_price), max_available_structures)
        if structures_to_build and sum(kd_info_parse["structures_target"].values()) > 0:
            structures_current = structures_info["current"]
            structures_building = structures_info["hour_24"]
            total_structures = {
                k: structures_current.get(k, 0) + structures_building.get(k, 0)
                for k in uas.STRUCTURES
            }
            pct_total_structures = {
                k: v / kd_info_parse["stars"]
                for k, v in total_structures.items()
            }
            target_gap = {
                k: kd_info_parse["structures_target"].get(k, 0) - v
                for k, v in pct_total_structures.items()
                if (kd_info_parse["structures_target"].get(k, 0) - v) > 0
            }
            total_target_gap = sum(target_gap.values())
            if total_target_gap > 0:
                target_gap_pct = {
                    k: v / total_target_gap
                    for k, v in target_gap.items()
                }
                target_structures_to_build = {
                    k: math.floor(v * structures_to_build)
                    for k, v in target_gap_pct.items()
                }
                leftover_structures = structures_to_build - sum(target_structures_to_build.values())
                for _ in range(leftover_structures):
                    rand_structure = _weighted_random_by_dct(target_gap_pct)
                    target_structures_to_build[rand_structure] += 1
                
                kd_info_parse["funding"]["structures"] = structures_funding - structures_to_build * structures_price
                
                target_structures_to_build_nonzero = {
                    k: v
                    for k, v in target_structures_to_build.items()
                    if v > 0
                }
                if sum(target_structures_to_build_nonzero.values()) > 0:
                    new_structures_payload, min_structures_time = uab._get_new_structures(target_structures_to_build_nonzero, time_update)
                    next_resolves["structures"] = min(min_structures_time, kd_info_parse["next_resolve"]["structures"])
                    structures_payload = {
                        "new_structures": new_structures_payload
                    }
                    structures_patch_response = REQUESTS_SESSION.patch(
                        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
                        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                        data=json.dumps(structures_payload),
                    )

        recruit_price = mobis_info["recruit_price"]
        recruit_time = mobis_info["recruit_time"]
        max_available_recruits = mobis_info["max_available_recruits"]
        current_units = mobis_info["units"]["current"]
        building_units = mobis_info["units"]["hour_24"]
        units_desc = mobis_info["units_desc"]
        military_funding = kd_info_parse["funding"]["military"]

        if military_funding > 0 and (sum(kd_info_parse["units_target"].values()) > 0 or max_available_recruits > 0):
            if kd_info_parse["recruits_before_units"]:
                recruits_til_cap = max(kd_info_parse["max_recruits"] - kd_info_parse["units"]["recruits"] - building_units.get("recruits", 0), 0)
                recruits_to_train = min(math.floor(military_funding / recruit_price), max_available_recruits, recruits_til_cap)
                remaining_funding = military_funding - recruits_to_train * recruit_price
            else:
                remaining_funding = military_funding
            
            total_units = {
                k: current_units.get(k, 0) + building_units.get(k, 0)
                for k in kd_info_parse["units_target"].keys()
            }
            for general in kd_info_parse["generals_out"]:
                for key_unit, value_unit in general.items():
                    if key_unit == "return_time":
                        continue
                    total_units[key_unit] += value_unit
            count_total_units = sum(total_units.values())
            pct_total_units = {
                k: v / count_total_units
                for k, v in total_units.items()
            }
            target_units_gap = {
                k: kd_info_parse["units_target"].get(k, 0) - v
                for k, v in pct_total_units.items()
                if (kd_info_parse["units_target"].get(k, 0) - v) > 0
            }
            total_target_units_gap = sum(target_units_gap.values())
            target_units_gap_pct = {
                k: v / total_target_units_gap
                for k, v in target_units_gap.items()
            }
            target_gap_weighted_funding = {
                k: v * remaining_funding
                for k, v in target_units_gap_pct.items()
            }
            target_gap_weighted_recruits = {
                k: math.floor(v * kd_info_parse["units"]["recruits"])
                for k, v in target_units_gap_pct.items()
            }
            target_units_to_build = {}
            for key_unit, funding_unit in target_gap_weighted_funding.items():
                units_to_build = min(math.floor(funding_unit / units_desc[key_unit]["cost"]), target_gap_weighted_recruits[key_unit])
                remaining_funding = remaining_funding - units_to_build * units_desc[key_unit]["cost"]
                kd_info_parse["units"]["recruits"] = kd_info_parse["units"]["recruits"] - units_to_build
                target_units_to_build[key_unit] = units_to_build
            

            if not kd_info_parse["recruits_before_units"]:
                recruits_til_cap = max(kd_info_parse["max_recruits"] - kd_info_parse["units"]["recruits"] - building_units.get("recruits", 0), 0)
                recruits_to_train = min(math.floor(remaining_funding / recruit_price), max_available_recruits, recruits_til_cap)
                remaining_funding = remaining_funding - recruits_to_train * recruit_price

            kd_info_parse["funding"]["military"] = remaining_funding
            
            target_units_to_build_nonzero = {
                k: v
                for k, v in target_units_to_build.items()
                if v > 0
            }
            mobis_payload = {
                "new_mobis": []
            }
            if recruits_to_train:
                new_recruits, min_recruits_time = uab._get_new_recruits(recruits_to_train, mobis_info["is_conscription"], time_update)
                mobis_payload["new_mobis"].extend(new_recruits)
                next_resolves["mobis"] = min(min_recruits_time, kd_info_parse["next_resolve"]["mobis"])
            if sum(target_units_to_build_nonzero.values()) > 0:
                new_mobis, min_mobis_time = uab._get_new_mobis(target_units_to_build_nonzero, time_update)
                mobis_payload["new_mobis"].extend(new_mobis)
                kd_info_parse["next_resolve"]["mobis"] = min(min_mobis_time, kd_info_parse["next_resolve"]["mobis"], next_resolves.get("mobis", uas.DATE_SENTINEL))
            mobis_patch_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(mobis_payload),
            )

        engineers_price = engineers_info["engineers_price"]
        max_available_engineers = engineers_info["max_available_engineers"]
        engineers_funding = kd_info_parse["funding"]["engineers"]
        new_engineers = min(math.floor(engineers_funding / engineers_price), max_available_engineers)
        if new_engineers:
            kd_info_parse["funding"]["engineers"] = engineers_funding - new_engineers * engineers_price
            
            new_engineers_payload, min_engineers_time = uab._get_new_engineers(new_engineers, time_update)
            next_resolves["engineers"] = min(min_engineers_time, kd_info_parse["next_resolve"]["engineers"])
            engineers_payload = {
                "new_engineers": new_engineers_payload
            }
            engineers_patch_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(engineers_payload),
            )

        next_resolve_time = max(
            resolve_time + datetime.timedelta(
                seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"]
            ),
            time_update,
        )
        next_resolves["auto_spending"] = next_resolve_time.isoformat()
    finally:
        uam.release_locks_by_id(request_id)
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
        for k in uas.UNITS
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
        if uas.UNITS[key_unit].get("offense", 0) == 0:
            continue
        else:
            if uas.UNITS[key_unit].get("defense", 0) == 0:
                req["attackerValues"][key_unit] = min(
                    math.floor(pct_units_available_pure[key_unit] * total_units.get(key_unit, 0)),
                    value_unit,
                )
            else:
                req["attackerValues"][key_unit] = min(
                    math.floor(pct_units_available_flex[key_unit] * total_units.get(key_unit, 0)),
                    value_unit,
                )
    kd_info_parse, payload, _ = uac._attack_primitives(req, kd_info_parse["kdId"])
    try:
        ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
        ws.send(json.dumps({
            "message": payload["message"],
            "status": payload.get("status", "info"),
            "category": "Auto Primitives",
            "delay": 15000,
            "update": ["mobis", "attackhistory"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return None

def _resolve_auto_rob(kd_info_parse):
    drones_pct = kd_info_parse["auto_rob_settings"].get("drones", 0)
    keep_spy_attempts = kd_info_parse["auto_rob_settings"].get("keep", 10)
    shielded = kd_info_parse["auto_rob_settings"].get("shielded", False)

    if kd_info_parse["spy_attempts"] > keep_spy_attempts:
        req = {
            "drones": math.floor(drones_pct * kd_info_parse["drones"]),
            "shielded": shielded,
        }
        kd_info_parse, payload, _ = uac._rob_primitives(req, kd_info_parse["kdId"])
        try:
            ws = SOCK_HANDLERS[kd_info_parse["kdId"]]
            ws.send(json.dumps({
                "message": payload["message"],
                "status": payload.get("status", "info"),
                "category": "Auto Primitives",
                "delay": 15000,
                "update": ["spyhistory"],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    return None

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
    if target_gap:
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

    req = {
        "attackerValues": {
            "generals": schedule["options"].get("generals", 0)
        }
    }
    prefer_autofill = schedule["options"].get("prefer_autofill", False)
    target_kd = schedule["options"]["target"]
    use_autofill = False
    if prefer_autofill:
        revealed = uag._get_revealed(new_kd_info["kdId"])
        if "military" in revealed["revealed"].get(target_kd, {}).keys():
            use_autofill = True
            autofill_req = {
                "defenderValues": {
                    **{
                        key_unit: 0
                        for key_unit in uas.UNITS.keys()
                    },
                    "military_bonus": 25,
                    "shields": 10,
                },
                "buffer": schedule["options"].get("autofill_buffer", 0.01) * 100,
                "generals": schedule["options"].get("generals", 0),
            }
            autofill_payload, _ = uac._autofill_attack(autofill_req, new_kd_info["kdId"], target_kd)
            if autofill_payload["attacker_offense"] > autofill_payload["defender_defense"]:
                for key_unit, value_unit in autofill_payload["attacker_units"].items():
                    req["attackerValues"][key_unit] = value_unit
            else:
                return new_kd_info
    
    if not prefer_autofill or not use_autofill:
        pure_pct = schedule["options"].get("pure_offense", 0)
        flex_pct = schedule["options"].get("flex_offense", 0)

        total_units = new_kd_info["units"].copy()
        total_general_units = {
            k: 0
            for k in uas.UNITS
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
            if uas.UNITS[key_unit].get("offense", 0) == 0:
                continue
            else:
                if uas.UNITS[key_unit].get("defense", 0) == 0:
                    req["attackerValues"][key_unit] = min(
                        math.floor(pct_units_available_pure[key_unit] * total_units.get(key_unit, 0)),
                        value_unit,
                    )
                else:
                    req["attackerValues"][key_unit] = min(
                        math.floor(pct_units_available_flex[key_unit] * total_units.get(key_unit, 0)),
                        value_unit,
                    )
    func = uac._attack
    args = (req, new_kd_info["kdId"], target_kd)
    return func, args

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
        for k in uas.UNITS
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
        if uas.UNITS[key_unit].get("offense", 0) == 0:
            continue
        else:
            if uas.UNITS[key_unit].get("defense", 0) == 0:
                req["attackerValues"][key_unit] = min(
                    math.floor(pct_units_available_pure[key_unit] * total_units.get(key_unit, 0)),
                    value_unit,
                )
            else:
                req["attackerValues"][key_unit] = min(
                    math.floor(pct_units_available_flex[key_unit] * total_units.get(key_unit, 0)),
                    value_unit,
                )
    func = uac._attack_primitives
    args = (req, new_kd_info["kdId"])
    return func, args

def _resolve_schedule_intelspy(new_kd_info, schedule):
    drones_pct = schedule["options"].get("drones_pct", 0)
    max_tries = schedule["options"].get("max_tries", 0)
    shielded = schedule["options"].get("shielded", False)
    operation = schedule["options"].get("operation", "")
    target_kd = schedule["options"].get("target", "")
    share_to_galaxy = schedule["options"].get("share_to_galaxy", False)

    def _loop_spies(kd_id, drones_pct, max_tries, shielded, operation, target_kd, share_to_galaxy):
        kd_info = uag._get_kd(kd_id)
        for _ in range(max_tries):
            req = {
                "drones": math.floor(drones_pct * kd_info["drones"]),
                "shielded": shielded,
                "operation": operation,
                "share_to_galaxy": share_to_galaxy,
            }
            new_kd_info, payload, status_code, success = uac._spy(req, kd_id, target_kd)
            if success:
                break
    func = _loop_spies
    args = (new_kd_info["kdId"], drones_pct, max_tries, shielded, operation, target_kd, share_to_galaxy)
    return func, args

def _resolve_schedule_aggressivespy(new_kd_info, schedule):
    drones_pct = schedule["options"].get("drones_pct", 0)
    attempts = schedule["options"].get("attempts", 0)
    shielded = schedule["options"].get("shielded", False)
    operation = schedule["options"].get("operation", "")
    target_kd = schedule["options"].get("target", "")

    def _loop_spies(kd_id, drones_pct, attempts, shielded, operation, target_kd):
        kd_info = uag._get_kd(kd_id)
        for _ in range(attempts):
            req = {
                "drones": math.floor(drones_pct * kd_info["drones"]),
                "shielded": shielded,
                "operation": operation
            }
            new_kd_info, payload, status_code, success = uac._spy(req, kd_id, target_kd)
    func = _loop_spies
    args = (new_kd_info["kdId"], drones_pct, attempts, shielded, operation, target_kd)
    return func, args

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
    new_kd_info, payload, status_code = uac._launch_missiles(req, new_kd_info["kdId"], target_kd)
    func = uac._launch_missiles
    args = (req, new_kd_info["kdId"], target_kd)
    return func, args

def _resolve_schedules(kd_id, time_update):

    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_id}', timeout=999):
        time.sleep(0.01)
    
    try:
        kd_info = uag._get_kd_info(kd_id)
        keep_schedules = []
        ready_schedules = []
        for schedule in kd_info["schedule"]:
            if datetime.datetime.fromisoformat(schedule["time"]).astimezone(datetime.timezone.utc) < time_update:
                ready_schedules.append(schedule)
            else:
                keep_schedules.append(schedule)
        
        schedule_funcs = {
            "attack": _resolve_schedule_attack,
            "attackprimitives": _resolve_schedule_attackprimitives,
            "intelspy": _resolve_schedule_intelspy,
            "aggressivespy": _resolve_schedule_aggressivespy,
            "missiles": _resolve_schedule_missiles,
        }
        intel_first_schedules = sorted(ready_schedules, key=lambda x: -int(x.get("type", "") == "intelspy"))
        actions = [
            schedule_funcs[ready_sched["type"]](kd_info, ready_sched)
            for ready_sched in intel_first_schedules
        ]


        kd_info["schedule"] = keep_schedules
        kd_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_info["kdId"]}',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_info, default=str),
        )
    finally:
        uam.release_lock(f'/kingdom/{kd_id}')
    
    for action in actions:
        action[0](*action[1])
    return None

def _begin_election(state):
    app = flask.current_app
    request_id = str(uuid.uuid4())
    while not uam.acquire_locks([f'/universepolitics', f'/updatestate'], timeout=999, request_id=request_id):
        time.sleep(0.01)
    try:
        election_start = datetime.datetime.fromisoformat(state["state"]["election_start"]).astimezone(datetime.timezone.utc)
        election_end = election_start + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_ELECTION_LENGTH_MULTIPLIER"])

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
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universepolitics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(universe_politics_payload)
        )
        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(state_payload)
        )
    finally:
        uam.release_locks_by_id(request_id)
    return state

def _resolve_election(state):
    app = flask.current_app
    while not uam.acquire_lock(f'/updatestate', timeout=999):
        time.sleep(0.01)
    try:
        election_end = datetime.datetime.fromisoformat(state["state"]["election_end"]).astimezone(datetime.timezone.utc)
        next_election_start = election_end + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_ELECTION_RESULTS_DURATION_MULTIPLIER"])


        universe_politics = uag._get_universe_politics()
        policy_1_option_1_votes = sum(universe_politics["votes"]["policy_1"]["option_1"].values())
        policy_1_option_2_votes = sum(universe_politics["votes"]["policy_1"]["option_2"].values())
        policy_2_option_1_votes = sum(universe_politics["votes"]["policy_2"]["option_1"].values())
        policy_2_option_2_votes = sum(universe_politics["votes"]["policy_2"]["option_2"].values())

        active_policies = []
        if policy_1_option_1_votes >= policy_1_option_2_votes:
            active_policies.append(uas.UNIVERSE_POLICIES["policy_1"]["options"]["1"]["name"])
        else:
            active_policies.append(uas.UNIVERSE_POLICIES["policy_1"]["options"]["2"]["name"])

            
        if policy_2_option_1_votes >= policy_2_option_2_votes:
            active_policies.append(uas.UNIVERSE_POLICIES["policy_2"]["options"]["1"]["name"])
        else:
            active_policies.append(uas.UNIVERSE_POLICIES["policy_2"]["options"]["2"]["name"])

        state_payload = {
            "election_start": next_election_start.isoformat(),
            "election_end": "",
            "active_policies": active_policies,
        }
        state["state"]["active_policies"] = active_policies

        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(state_payload)
        )
    finally:
        uam.release_lock(f'/updatestate')
    return state

def _resolve_scores(kd_scores, time_update):

    app = flask.current_app
    while not uam.acquire_lock(f'/scores', timeout=999):
        time.sleep(0.01)
    try:
        scores = uag._get_scores()

        new_scores = {
            **scores,
            **kd_scores,
        }
        time_last_update = datetime.datetime.fromisoformat(scores["last_update"]).astimezone(datetime.timezone.utc)
        seconds_elapsed = (time_update - time_last_update).total_seconds()
        epoch_elapsed = seconds_elapsed / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        
        new_scores["last_update"] = time_update.isoformat()

        top_kds = sorted(
            new_scores["networth"],
            key=lambda x: -new_scores["networth"][x]
        )[:len(uas.GAME_CONFIG["NETWORTH_POINTS"])]
        for i_points, kd_scoring in enumerate(top_kds):
            points_value = uas.GAME_CONFIG["NETWORTH_POINTS"][i_points]
            epoch_points = epoch_elapsed * points_value
            try:
                new_scores["points"][kd_scoring] += epoch_points
            except KeyError:
                new_scores["points"][kd_scoring] = epoch_points

        galaxies_inverted, _ = uag._get_galaxies_inverted()
        new_scores["galaxy_networth"] = collections.defaultdict(int)
        for kd_id, networth in kd_scores["networth"].items():
            galaxy = galaxies_inverted[kd_id]
            new_scores["galaxy_networth"][galaxy] += networth
        
        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/scores',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(new_scores)
        )
    finally:
        uam.release_lock(f'/scores')

def _update_history(
    kd_info,
    time_update,
):
    app = flask.current_app
    while not uam.acquire_lock(f'/kingdom/{kd_info["kdId"]}/history', timeout=999):
        time.sleep(0.01)
    try:
        history_payload = {}

        basic_kd_info_keys = ["networth", "stars", "drones", "population"]
        for key_info in basic_kd_info_keys:
            history_payload[key_info] = {
                "time": time_update.isoformat(),
                "value": kd_info[key_info],
            }
        history_payload["engineers"] = {
            "time": time_update.isoformat(),
            "value": kd_info["units"]["engineers"],
        }
        
        total_units = kd_info["units"].copy()
        total_general_units = {
            k: 0
            for k in uas.UNITS
        }
        for general_units in kd_info["generals_out"]:
            for key_unit, value_unit in general_units.items():
                if key_unit == "return_time":
                    continue
                total_units[key_unit] += value_unit
                total_general_units[key_unit] += value_unit
        
        offense = uag._calc_max_offense(total_units)
        defense = uag._calc_max_defense(total_units)

        history_payload["max_offense"] = {
            "time": time_update.isoformat(),
            "value": offense,
        }
        history_payload["max_defense"] = {
            "time": time_update.isoformat(),
            "value": defense,
        }
        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_info["kdId"]}/history',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({"history": history_payload})
        )
    finally:
        uam.release_lock(f'/kingdom/{kd_info["kdId"]}/history')
    return None

def _resolve_empires(
    kd_scores,
    time_update,
):
    app = flask.current_app
    while not uam.acquire_lock(f'/empires', timeout=999):
        time.sleep(0.01)
    try:
        empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
        time_last_update = datetime.datetime.fromisoformat(empires_info["last_update"]).astimezone(datetime.timezone.utc)
        seconds_elapsed = (time_update - time_last_update).total_seconds()
        epoch_elapsed = seconds_elapsed / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]

        kd_counts = collections.defaultdict(int)
        for kd_id in kd_scores["networth"].keys():
            kd_empire = empires_inverted.get(kd_id)
            if kd_empire:
                kd_counts[kd_empire] += 1
        
        for empire_id in empires_info["empires"].keys():
            empires_info["empires"][empire_id]["num_kingdoms"] = kd_counts.get(empire_id, 0)
            empires_info["empires"][empire_id]["aggression_max"] = empires_info["empires"][empire_id]["num_kingdoms"] * uas.GAME_CONFIG["AGGRO_METER_PER_KD"]

            decay_per_epoch = empires_info["empires"][empire_id]["num_kingdoms"] * uas.GAME_CONFIG["AGGRO_METER_DECAY_PER_KD_PER_EPOCH"]
            decay = decay_per_epoch * epoch_elapsed

            if empires_info["empires"][empire_id]["denounced"]:
                denounce_expiration = datetime.datetime.fromisoformat(empires_info["empires"][empire_id]["denounced_expires"]).astimezone(datetime.timezone.utc)
                if denounce_expiration < time_update:
                    empires_info["empires"][empire_id]["denounced"] = ""
                    empires_info["empires"][empire_id]["denounced_expires"] = ""

            if empires_info["empires"][empire_id]["surprise_war_penalty"]:
                denounce_expiration = datetime.datetime.fromisoformat(empires_info["empires"][empire_id]["surprise_war_penalty_expires"]).astimezone(datetime.timezone.utc)
                if denounce_expiration < time_update:
                    empires_info["empires"][empire_id]["surprise_war_penalty"] = False
                    empires_info["empires"][empire_id]["surprise_war_penalty_expires"] = ""

            new_peace = {
                empire_id: peace_expiration
                for empire_id, peace_expiration in empires_info["empires"][empire_id]["peace"].items()
                if datetime.datetime.fromisoformat(peace_expiration).astimezone(datetime.timezone.utc) > time_update
            }
            empires_info["empires"][empire_id]["peace"] = new_peace

            for other_empire_id, aggression_meter in empires_info["empires"][empire_id]["aggression"].items():
                if aggression_meter > empires_info["empires"][empire_id]["aggression_max"]:
                    if other_empire_id not in empires_info["empires"][empire_id]["war"]:
                        empires_info["empires"][empire_id]["war"].append(other_empire_id)
                        empires_info["empires"][other_empire_id]["war"].append(empire_id)

                        news_payload = {
                            "news": {
                                "time": time_update.isoformat(),
                                "news": f"{empires_info['empires'][empire_id]['name']} declared war by aggression on {empires_info['empires'][other_empire_id]['name']}",
                            }
                        }
                        universe_news_update_response = REQUESTS_SESSION.patch(
                            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
                            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                            data=json.dumps(news_payload)
                        )
            for other_empire_id in empires_info["empires"][empire_id]["aggression"]:
                empires_info["empires"][empire_id]["aggression"][other_empire_id] = max(
                    empires_info["empires"][empire_id]["aggression"][other_empire_id] - decay,
                    0,
                )
        empires_payload = {
            "empires": empires_info["empires"],
            "last_update": time_update.isoformat(),
        }

        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empires_payload)
        )
    finally:
        uam.release_lock(f'/empires')

def _refresh_kd(kd_id, state, time_update, update_history):
    app = flask.current_app
    try:
        query = db.session.query(User).filter_by(kd_id=kd_id).all()
        user = query[0]
        if not user.kd_created:
            return (0, 0)
    except:
        print(f"Could not query kd_id {kd_id}")
        pass

    while not uam.acquire_lock(f'/kingdom/{kd_id}', timeout=999):
        time.sleep(0.01)

    try:
        next_resolves = {}
        kd_info = REQUESTS_SESSION.get(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
        )
        kd_info_parse = json.loads(kd_info.text)
        if kd_info_parse["status"].lower() == "dead":
            return (0, 0)
        current_bonuses = {
            project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
            for project, project_dict in uas.PROJECTS.items()
            if "max_bonus" in project_dict
        }

        categories_to_resolve = [cat for cat, time in kd_info_parse["next_resolve"].items() if datetime.datetime.fromisoformat(time).astimezone(datetime.timezone.utc) < time_update]
        if "settles" in categories_to_resolve:
            new_stars, next_resolves["settles"] = _resolve_settles(
                kd_id,
                time_update,
            )
            kd_info_parse["stars"] += new_stars
            for key_project, project_dict in uas.PROJECTS.items():
                project_max_func = uas.PROJECTS_FUNCS[key_project]
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
            next_resolves_spending_effective = {
                k: min(
                    datetime.datetime.fromisoformat(v).astimezone(datetime.timezone.utc),
                    next_resolves.get(k, datetime.datetime.fromisoformat(uas.DATE_SENTINEL).astimezone(datetime.timezone.utc))
                )
                for k, v in next_resolves_auto_spending.items()
            }
            next_resolves = {
                **next_resolves,
                **next_resolves_spending_effective,
            }
        if kd_info_parse["auto_assign_projects"] and (kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values()) > 0):
            kd_info_parse = _resolve_auto_projects(kd_info_parse)

        for category, next_resolve_datetime in next_resolves.items():
            kd_info_parse["next_resolve"][category] = next_resolve_datetime.isoformat()
        new_kd_info = _kingdom_with_income(kd_info_parse, current_bonuses, state, time_update)
        kd_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(new_kd_info, default=str),
        )
    finally:
        uam.release_lock(f'/kingdom/{kd_id}')

    _resolve_schedules(kd_id, time_update)
    new_kd_info = uag._get_kd_info(kd_id)
    if new_kd_info["auto_attack_enabled"] and new_kd_info["generals_available"] > 0:
        _resolve_auto_attack(new_kd_info)
    new_kd_info = uag._get_kd_info(kd_id)
    if new_kd_info["auto_rob_enabled"]:
        _resolve_auto_rob(new_kd_info)

    new_kd_info = uag._get_kd_info(kd_id)
    score_stars = new_kd_info["stars"]
    score_networth = new_kd_info["networth"]

    if update_history:
        _update_history(
            new_kd_info,
            time_update,
        )
    return score_stars, score_networth


@bp.route('/api/refreshdata')
def refresh_data():
    """Perform periodic refresh tasks"""
    app = flask.current_app
    headers = flask.request.headers
    if headers.get("Refresh-Secret", "") != os.environ["REFRESH_SECRET"]:
        return ("Not Authorized", 401)
    
    state = uag._get_state()
    time_now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if time_now < state["state"]["game_start"]:
        return ("Not started", 200)
    if time_now > state["state"]["election_end"] and state["state"]["election_end"] != "":
        state = _resolve_election(state)
    elif time_now > state["state"]["election_start"] and state["state"]["election_end"] == "":
        state = _begin_election(state)

    kingdoms = uag._get_kingdoms()
    time_update = datetime.datetime.now(datetime.timezone.utc)

    history_datetime = datetime.datetime.fromisoformat(state["state"]["next_history"]).astimezone(datetime.timezone.utc)
    if history_datetime < time_update:
        update_history = True
        next_history = history_datetime + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])
        state_payload = {
            "next_history": next_history.isoformat(),
        }

        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/updatestate',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(state_payload)
        )
    else:
        update_history = False

    kd_scores = {}
    for kd_id in kingdoms:
        kd_scores[kd_id] = _refresh_kd(
            kd_id,
            state,
            time_update,
            update_history,
        )
    
    kd_scores_split = {
        "stars": {
            kd_id: items[0]
            for kd_id, items in kd_scores.items() 
        },
        "networth": {
            kd_id: items[1]
            for kd_id, items in kd_scores.items() 
        },
    }
    _resolve_scores(kd_scores_split, time_update)
    _resolve_empires(kd_scores_split, time_update)
        
    return "Refreshed", 200