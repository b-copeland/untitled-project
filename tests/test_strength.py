"""Production intel (Spy on Production) and the strength forecasts on the Status and kingdom pages."""
import datetime

import untitledapp.getters as uag
import untitledapp.shared as uas
import untitledapp.strength as uastr

from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get  # noqa: F401

FUTURE = "2999-01-01T00:00:00+00:00"
NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _at(hours):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).isoformat()


def _reveal(categories, galaxymates=None):
    _create_item(f"revealed_{KD_ID}", {**uas.INITIAL_KINGDOM_STATE["revealed"],
                                      "revealed": {TARGET_ID: {category: FUTURE for category in categories}},
                                      "revealed_galaxymates": galaxymates or []})


def _queues_on_target():
    _create_item(f"mobis_{TARGET_ID}", {"mobis": [{"time": _at(0.5), "defense": 40}, {"time": _at(100), "attack": 7}]})
    _create_item(f"structures_{TARGET_ID}", {"structures": [{"time": _at(0.5), "homes": 3}]})
    _create_item(f"engineers_{TARGET_ID}", {"engineers": [{"time": _at(3), "amount": 5}]})
    _create_item(f"settles_{TARGET_ID}", {"settles": [{"time": _at(3), "amount": 9}]})
    _create_item(f"missiles_{TARGET_ID}", {"missiles": [{"time": _at(3), "planet_busters": 2}]})


def _kingdom(client, jwt):
    return client.get(f"/api/kingdom/{TARGET_ID}", headers={"Authorization": f"Bearer {jwt}"}).get_json()


def _forecast(client, jwt, **body):
    return client.post("/api/strengthforecast", json=body, headers={"Authorization": f"Bearer {jwt}"})


def test_spy_on_production_reveals_production_and_full_infiltration_includes_it():
    assert "spyproduction" in uas.REVEAL_OPERATIONS
    assert uas.REVEAL_OPERATION_STATS["spyproduction"] == ["production"]
    assert "production" in uas.REVEAL_OPERATION_STATS["spyall"]
    assert "spyproduction" in uas.OPERATIONS_REPLACED_BY_PROJECT["vult_evolution"]


def test_production_has_no_kingdom_fields_and_no_last_known_snapshot():
    kd = {"name": "x", "units": {"attack": 3}, "fuel": 9}
    assert uas.revealed_fields(kd, ["production"]) == {"name": "x"}
    import untitledapp.lastknown as uala
    assert uala.snapshot(kd, ["production", "kingdom"], FUTURE).keys() == {"kingdom"}


def test_the_kingdom_page_shows_production_only_with_production_intel(app, client, jwt1):
    _set_up_two_kingdoms()
    _queues_on_target()
    _reveal(["military"])
    assert "production" not in _kingdom(client, jwt1)

    _reveal(["production"])
    production = _kingdom(client, jwt1)["production"]

    assert set(production) == set(uas.PRODUCTION_QUEUES)
    assert production["mobis"]["future_2"]["defense"] == 40  # lands within an hour
    assert production["mobis"]["future_2"]["attack"] == 0
    assert production["mobis"]["queued"]["attack"] == 7
    assert production["structures"]["future_2"]["homes"] == 3
    assert production["engineers"]["future_8"]["amount"] == 5
    assert production["settles"]["future_8"]["amount"] == 9
    assert production["missiles"]["queued"]["planet_busters"] == 2


def test_a_galaxymate_sharing_its_kingdom_shows_its_production(app, client, jwt1):
    _set_up_two_kingdoms()
    _queues_on_target()
    _reveal([], galaxymates=[TARGET_ID])
    assert _kingdom(client, jwt1)["production"]["settles"]["queued"]["amount"] == 9


def test_the_timelines_add_generals_as_they_return_and_training_as_it_lands():
    kd = {
        "race": "Xo",
        "units": {"defense": 100, "attack": 10},
        "generals_available": 2,
        "generals_out": [{"return_time": (NOW + datetime.timedelta(hours=1)).isoformat(), "attack": 50},
                         {"return_time": (NOW + datetime.timedelta(hours=5)).isoformat(), "defense": 20}],
    }
    mobis = [{"time": (NOW + datetime.timedelta(minutes=30)).isoformat(), "defense": 30}]

    result = uastr.timelines(kd, mobis, NOW, shields=0.0, military_bonus=0.0, fuelless=False)

    def strength(units, generals):
        return (uag._calc_max_offense(units, military_bonus=0, generals=generals, lumina=False),
                uag._calc_max_defense(units, military_bonus=0, shields=0))

    generals = result["generals"]
    assert [point["kind"] for point in generals] == ["now", "general", "general"]
    assert [point["generals_home"] for point in generals] == [2, 3, 4]
    assert (generals[1]["offense"], generals[1]["defense"]) == strength({"defense": 100, "attack": 60}, 3)
    assert (generals[2]["offense"], generals[2]["defense"]) == strength({"defense": 120, "attack": 60}, 4)

    production = result["production"]
    assert [point.get("epochs") for point in production[1:]] == uas.GAME_CONFIG["QUEUE_FORECAST_EPOCHS"]
    assert production[0]["defense"] == strength({"defense": 100, "attack": 10}, 2)[1]
    assert production[1]["defense"] == strength({"defense": 130, "attack": 10}, 2)[1]  # one hour: the training is in
    assert production[1]["generals_home"] == 2  # production alone leaves the generals out

    combined = result["combined"]
    times = [point["time"] for point in combined]
    assert times == sorted(times)
    assert len(combined) == 1 + 2 + len(uas.GAME_CONFIG["QUEUE_FORECAST_EPOCHS"])
    assert combined[-1]["defense"] == strength({"defense": 150, "attack": 60}, 4)[1]


def test_without_the_training_queue_there_is_only_the_generals_timeline():
    kd = {"race": "Xo", "units": {"defense": 1}, "generals_available": 4, "generals_out": []}
    assert set(uastr.timelines(kd, None, NOW, 0, 0, False)) == {"generals"}


def test_your_own_forecast_uses_your_shields_and_bonus_unless_you_ask_about_others(app, client, jwt1):
    _set_up_two_kingdoms()
    body = _forecast(client, jwt1).get_json()
    assert body["production_known"] is True
    assert body["shields"]["value"] == body["shields"]["known"]
    assert set(body["timelines"]) == {"generals", "production", "combined"}

    asked = _forecast(client, jwt1, shields=10, military_bonus=0).get_json()
    assert asked["shields"]["value"] == 0.10 and asked["military_bonus"]["value"] == 0


def test_another_kingdoms_forecast_needs_military_intel(app, client, jwt1):
    _set_up_two_kingdoms()
    _reveal(["kingdom"])
    refused = _forecast(client, jwt1, target=TARGET_ID)
    assert refused.status_code == 400
    assert "military" in refused.get_json()["message"]


def test_another_kingdoms_forecast_assumes_the_most_it_does_not_know(app, client, jwt1):
    _set_up_two_kingdoms(target_defense=100)
    _queues_on_target()
    _reveal(["military"])

    body = _forecast(client, jwt1, target=TARGET_ID).get_json()

    assert body["production_known"] is False and set(body["timelines"]) == {"generals"}
    assert body["shields"] == {"value": uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"], "known": None,
                               "max": uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"]}
    assert body["military_bonus"]["known"] is None
    assert body["military_bonus"]["value"] == uas.PROJECTS["military_bonus"]["max_bonus"]


def test_another_kingdoms_forecast_with_production_counts_its_training(app, client, jwt1):
    _set_up_two_kingdoms(target_defense=100)
    _queues_on_target()
    _reveal(["military", "production", "shields"])

    body = _forecast(client, jwt1, target=TARGET_ID, shields=0, military_bonus=0).get_json()

    production = body["timelines"]["production"]
    assert production[1]["defense"] > production[0]["defense"]  # the 40 defense landing within the hour
    assert body["shields"]["known"] == 0


def test_a_what_if_above_the_maximum_is_refused(app, client, jwt1):
    _set_up_two_kingdoms()
    assert _forecast(client, jwt1, shields=500).status_code == 400
    assert _forecast(client, jwt1, target=["1"]).status_code == 400
    assert _forecast(client, jwt1, target="nope").status_code == 400
