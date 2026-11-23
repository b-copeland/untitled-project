import pytest
import json
from untitledapp import REQUESTS_SESSION
import untitledapp.getters as app_getters
import untitledapp.shared as app_shared

def test_max_kingdom(app, client, jwt1):
    
    resp = client.get("/api/kingdom/2")
    assert resp.status_code == 401

    galaxies_data = {
        "item": "galaxies",
        "state": {
            "galaxies": {
                "1:1": ["1"],
                "1:2": ["2"],
            }
        }
    }
    revealed_1_data = {
        "item": "revealed_1",
        "state": {
            "revealed": {
                "2": {
                    "stats": "date string"
                }
            },
            "revealed_galaxymates": [],
        }
    }
    kingdom_2_data = {
        "item": "kingdom_2",
        "state": {
            "name": "kd2",
            "stars": 100,
            "networth": 1000,
            "fuel": 1000,
            "shields": {
                "military": 0,
                "spy": 0,
                "spy_radar": 0,
                "missiles": 0
            },
        }
    }
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(galaxies_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(revealed_1_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(kingdom_2_data),
    )

    resp = client.get(
        "/api/kingdom/2",
        headers={"Authorization": f"Bearer {jwt1}"}
    )

    assert resp.status_code == 200
    resp_json = resp.json
    assert len(resp_json.keys()) == 3
    assert resp_json["stars"] == 100
    assert resp_json["networth"] == 1000
    assert resp_json["name"] == "kd2"

def test_scores(app, client, jwt1):
    
    resp = client.get("/api/scores")
    assert resp.status_code == 401

    scores_data = {
        "item": "scores",
        "state": {
            "points": {
                "1": 101,
                "2": 102,
                "3": 103,
                "4": 104,
            },
            "stars": {
                "1": 201,
                "2": 202,
                "3": 203,
                "4": 204,
            },
            "networth": {
                "1": 301,
                "2": 302,
                "3": 303,
                "4": 304,
            },
            "galaxy_networth": {
                "1:1": 604,
                "1:2": 606,
            }
        }
    }

    galaxies_data = {
        "item": "galaxies",
        "state": {
            "galaxies": {
                "1:1": ["1", "3"],
                "1:2": ["2", "4"],
            }
        }
    }
    revealed_1_data = {
        "item": "revealed_1",
        "state": {
            "revealed": {
                "2": {
                    "stats": "date string"
                }
            },
            "revealed_galaxymates": [],
        }
    }
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(scores_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(galaxies_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(revealed_1_data),
    )

    resp = client.get(
        "/api/scores",
        headers={"Authorization": f"Bearer {jwt1}"}
    )

    assert resp.status_code == 200
    resp_json = resp.json

    for kd_id, networth in resp_json["networth"]:
        assert kd_id not in ["4"]
        if kd_id == "1":
            assert networth == 301
        if kd_id == "2":
            assert networth == 302
        if kd_id == "3":
            assert networth == 303

    for kd_id, stars in resp_json["stars"]:
        assert kd_id not in ["4"]
        if kd_id == "1":
            assert stars == 201
        if kd_id == "2":
            assert stars == 202
        if kd_id == "3":
            assert stars == 203

    for kd_id, points in resp_json["points"]:
        assert kd_id not in ["2", "4"]
        if kd_id == "1":
            assert points == 101
        if kd_id == "2":
            assert points == 102

def test__calc_max_recruits():

    population = 1000
    max_recruits = app_shared.GAME_FUNCS["BASE_MAX_RECRUITS"](population)
    max_recruits_cost = app_shared.GAME_CONFIG["BASE_RECRUIT_COST"] * max_recruits

    kd_max_recruits = {
        "money": max_recruits_cost * 100,
        "population": population
    }
    units_max_recruits = {
        "queued": {
            "recruits": 0,
        }
    }

    assert app_getters._calc_max_recruits(kd_max_recruits, units_max_recruits) == (max_recruits, max_recruits)

    kd_too_poor = {
        "money": 10 * app_shared.GAME_CONFIG["BASE_RECRUIT_COST"],
        "population": population
    }
    units_too_poor = {
        "queued": {
            "recruits": 0,
        }
    }
    assert app_getters._calc_max_recruits(kd_too_poor, units_too_poor) == (max_recruits, 10)

    kd_recruits_training = {
        "money": max_recruits_cost * 100,
        "population": population
    }
    units_recruits_training = {
        "queued": {
            "recruits": 10,
        }
    }
    assert app_getters._calc_max_recruits(kd_recruits_training, units_recruits_training) == (max_recruits - 10, max_recruits - 10)

def test_military_estimate_counts_units_out_with_generals_and_only_when_units_are_revealed():
    import untitledapp.getters as getters

    assert getters._military_estimate({"name": "x"}) is None
    home = getters._military_estimate({"units": {"attack": 100, "defense": 50}})
    with_generals_out = getters._military_estimate({
        "units": {"attack": 100, "defense": 50}, "generals_out": [{"attack": 100, "return_time": "2099-01-01"}]})
    assert home["offense"] > 0 and home["defense"] > 0
    assert with_generals_out["offense"] > home["offense"] and with_generals_out["defense"] == home["defense"]
    # Lumina's offense is reduced, and Gaian's defense is not the same as anybody else's.
    assert getters._military_estimate({"units": {"attack": 100}, "race": "Lumina"})["offense"] < getters._military_estimate({"units": {"attack": 100}})["offense"]


def test_the_projects_of_a_dead_kingdom_can_be_looked_at(app, client, jwt1):
    from tests.test_concurrency import _create_item

    _create_item("galaxies", {"galaxies": {"1:1": ["1"], "1:2": ["2"]}})
    _create_item("revealed_1", {"revealed": {"2": {"projects": "2999-01-01T00:00:00+00:00"}}, "revealed_galaxymates": []})
    zero = {project: 0 for project in app_shared.PROJECTS}
    _create_item("kingdom_2", {**app_shared.INITIAL_KINGDOM_STATE["kingdom"],
                               "kdId": "2", "name": "kd2", "stars": 0, "status": "Dead", "networth": 0,
                               "projects_points": zero, "projects_max_points": zero})

    resp = client.get("/api/kingdom/2", headers={"Authorization": f"Bearer {jwt1}"})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert set(resp.json["current_bonuses"].values()) == {0.0}


def test_queue_forecasts_follow_the_epoch_length_and_queued_counts_everything(monkeypatch):
    """The Status page's columns are epochs ahead, so a longer epoch looks further ahead; limits use "queued"."""
    import datetime
    import untitledapp.getters as getters

    now = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
    at = lambda hours, **counts: {"time": (now + datetime.timedelta(hours=hours)).isoformat(), **counts}
    queue = [at(0.5, homes=1), at(3, homes=2), at(30, homes=4)]

    monkeypatch.setitem(app_shared.GAME_CONFIG, "BASE_EPOCH_SECONDS", 1800)
    half_hour = getters._calc_structures(now, {"homes": 10}, queue)
    assert [half_hour[f"future_{n}"]["homes"] for n in app_shared.GAME_CONFIG["QUEUE_FORECAST_EPOCHS"]] == [1, 1, 3, 3, 3]
    assert half_hour["queued"]["homes"] == 7  # the entry 30 hours out is past the last column, but it is still queued

    monkeypatch.setitem(app_shared.GAME_CONFIG, "BASE_EPOCH_SECONDS", 3600)
    hour = getters._calc_structures(now, {"homes": 10}, queue)
    assert [hour[f"future_{n}"]["homes"] for n in app_shared.GAME_CONFIG["QUEUE_FORECAST_EPOCHS"]] == [1, 3, 3, 3, 7]

    units = getters._calc_units(now, {"recruits": 5}, [], [at(40, recruits=9)])
    assert units["queued"]["recruits"] == 9 and units["future_2"]["recruits"] == 0
    assert getters._calc_max_recruits({"money": 10 ** 9, "population": 1000}, units)[0] == (
        app_shared.GAME_FUNCS["BASE_MAX_RECRUITS"](1000) - 9)


def test_the_military_page_gives_strength_now_as_well_as_the_best_case(app, client, jwt1):
    """The Status page's Military card shows the kingdom's own strength as it is: real bonus, shields, fuel and the
    generals at home, not the best case of ``maxes`` (full bonus, 10% shields, four generals)."""
    from tests.test_concurrency import _set_up_kingdom
    units = {**app_shared.INITIAL_KINGDOM_STATE["kingdom"]["units"], "defense": 1000, "attack": 1000}
    _set_up_kingdom(money=0, race="Xo", units=units, generals_available=1,
                    shields={"military": 0.0, "spy": 0.0, "spy_radar": 0.0, "missiles": 0.0})
    mobis = client.get("/api/mobis", headers={"Authorization": f"Bearer {jwt1}"}).get_json()
    now, best = mobis["now"], mobis["maxes"]
    from tests.test_concurrency import _get
    bonus = app_shared.project_bonuses(_get("/kingdom/1"))["military_bonus"]  # what its starting projects give
    with app.app_context():
        expected_defense = app_getters._calc_max_defense({"defense": 1000}, military_bonus=bonus, shields=0)
        expected_offense = app_getters._calc_max_offense({"attack": 1000}, military_bonus=bonus, generals=1)
    assert now == {"defense": expected_defense, "offense": expected_offense}
    assert now["defense"] < best["defense"]["current"] and now["offense"] < best["offense"]["current"]
