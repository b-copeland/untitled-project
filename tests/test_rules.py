"""Reactive rules (issue #35): when something happens to the kingdom, switch its settings or react against the sender."""
import datetime

import pytest

import untitledapp.conquer as uac
import untitledapp.rules as rules
import untitledapp.shared as uas
from tests import kingdoms
from tests.test_attack import TARGET_ID, _attack, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get

NOW = datetime.datetime(2026, 6, 1, 12, tzinfo=datetime.timezone.utc)
HANDLERS = {"intelspy": uac._schedule_intelspy, "missiles": uac._schedule_missiles}


def _rule(when, then, cooldown=6, created=NOW):
    rule, problem = rules.make_rule({"when": when, "then": then, "cooldown_hours": cooldown}, created)
    assert problem is None, problem
    return rule


def _war_footing(hours=12):
    return {"kind": "settings", "hours": hours, "settings": {
        "shields": {"military": 10}, "auto_spending": {"settle": 0, "structures": 10, "military": 80, "engineers": 10},
        "auto_attack_enabled": False}}


def _attacked(at, by="2", lost=True):
    return {"attacked": {"at": at.isoformat(), "by": by, "lost": lost, "count": 1}}


def _kingdom(**overrides):
    base = {"fuel": 1000, "auto_attack_enabled": True,
            "auto_spending": {"settle": 0.5, "structures": 0.25, "military": 0.25, "engineers": 0}}
    return kingdoms.kingdom(**{**base, **overrides})


# --- making a rule ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("when, then, problem", [
    ({"kind": "rain"}, {"kind": "settings"}, "Choose what the rule reacts to"),
    ({"kind": "attacked"}, {"kind": "dance"}, "Choose what the rule does"),
    ({"kind": "fuel_low", "hours": 4}, {"kind": "spy_sender", "operation": "spymilitary", "drones_pct": 50},
     "Low fuel has nobody to react against: switch settings instead"),
    ({"kind": "attacked"}, {"kind": "settings", "hours": 4, "settings": {}}, "Choose at least one setting to switch"),
    ({"kind": "attacked"}, {"kind": "settings", "hours": 4, "settings": {"shields": {"military": 50}}},
     "Military shields must be at or below max shields value"),
    ({"kind": "attacked"}, {"kind": "settings", "hours": 4, "settings": {"money": 5}}, "A rule can not change money"),
    ({"kind": "attacked"}, {"kind": "spy_sender", "operation": "bombhomes", "drones_pct": 50}, "Choose an intel operation"),
    ({"kind": "attacked"}, {"kind": "missiles_sender"}, "Choose how many missiles to fire"),
])
def test_a_bad_rule_is_refused_with_a_reason(when, then, problem):
    assert rules.make_rule({"when": when, "then": then}, NOW) == (None, problem)


def test_settings_are_stored_as_fractions():
    rule = _rule({"kind": "attacked", "lost_only": True}, _war_footing())
    assert rule["then"]["settings"]["shields"] == {"military": 0.1}
    assert rule["then"]["settings"]["auto_spending"]["military"] == 0.8
    assert rule["when"] == {"kind": "attacked", "lost_only": True}


# --- in the refresh --------------------------------------------------------------------------------------------------


def test_no_rules_change_nothing():
    assert rules.step(_kingdom(), NOW, HANDLERS) == ({}, [])


def test_an_attack_switches_settings_for_a_while_and_they_go_back():
    rule = _rule({"kind": "attacked"}, _war_footing(hours=12))
    kd = _kingdom(rules=[rule], events=_attacked(NOW + datetime.timedelta(minutes=5)))
    later = NOW + datetime.timedelta(minutes=10)
    changes, notes = rules.step(kd, later, HANDLERS)
    assert changes["auto_spending"]["military"] == 0.8 and changes["auto_attack_enabled"] is False
    assert changes["shields_climb"]["military"]["to"] == 0.1  # shields climb, as on the Shields page
    assert "settings switched for 12 hours" in notes[0]
    kd.update(changes)

    # The same event does not fire it again.
    again, _ = rules.step(kd, later + datetime.timedelta(minutes=1), HANDLERS)
    assert "auto_spending" not in again

    done = later + datetime.timedelta(hours=12, minutes=1)
    back, notes = rules.step(kd, done, HANDLERS)
    assert back["auto_spending"]["settle"] == 0.5 and back["auto_attack_enabled"] is True
    assert uas.shields_now({**kd, **back}, done)["military"] == 0  # a cut is at once
    assert "back as they were" in notes[0]


def test_a_setting_the_player_changed_meanwhile_is_left_as_they_set_it():
    rule = _rule({"kind": "attacked"}, _war_footing(hours=1))
    kd = _kingdom(rules=[rule], events=_attacked(NOW + datetime.timedelta(minutes=1)))
    changes, _ = rules.step(kd, NOW + datetime.timedelta(minutes=2), HANDLERS)
    kd.update(changes)
    kd["auto_attack_enabled"] = True  # the player turned it back on
    back, _ = rules.step(kd, NOW + datetime.timedelta(hours=2), HANDLERS)
    assert "auto_attack_enabled" not in back and back["auto_spending"]["settle"] == 0.5


def test_lost_only_ignores_attacks_the_kingdom_held_off():
    rule = _rule({"kind": "attacked", "lost_only": True}, _war_footing())
    kd = _kingdom(rules=[rule], events=_attacked(NOW + datetime.timedelta(minutes=1), lost=False))
    changes, notes = rules.step(kd, NOW + datetime.timedelta(minutes=2), HANDLERS)
    assert "auto_spending" not in changes and notes == []
    assert changes["rules"][0]["state"]["seen"] == (NOW + datetime.timedelta(minutes=1)).isoformat()


def test_the_cooldown_keeps_it_from_firing_again_too_soon():
    rule = _rule({"kind": "spied"}, {"kind": "spy_sender", "operation": "spymilitary", "drones_pct": 50}, cooldown=6)
    first = NOW + datetime.timedelta(minutes=1)
    kd = _kingdom(rules=[rule], events={"spied": {"at": first.isoformat(), "by": "2", "lost": True, "count": 1}})
    changes, _ = rules.step(kd, first, HANDLERS)
    kd.update(changes)
    second = NOW + datetime.timedelta(hours=1)
    kd["events"] = {"spied": {"at": second.isoformat(), "by": "2", "lost": True, "count": 2}}
    changes, notes = rules.step(kd, second, HANDLERS)
    assert "schedule" not in changes and notes == []


def test_a_spy_reaction_schedules_intel_on_the_sender_due_at_once():
    rule = _rule({"kind": "attacked"}, {"kind": "spy_sender", "operation": "spymilitary", "drones_pct": 40})
    when = NOW + datetime.timedelta(minutes=1)
    changes, notes = rules.step(_kingdom(rules=[rule], events=_attacked(when)), when, HANDLERS)
    [entry] = changes["schedule"]
    assert entry["type"] == "intelspy" and entry["options"]["target"] == "2" and entry["options"]["drones_pct"] == 0.4
    assert uas.utc(entry["time"]) < when  # the schedule step right after the write runs it
    assert "spying on whoever did it" in notes[0]


def test_without_knowing_who_did_it_a_reaction_against_them_does_nothing():
    rule = _rule({"kind": "spied"}, {"kind": "missiles_sender", "planet_busters": 5})
    when = NOW + datetime.timedelta(minutes=1)
    kd = _kingdom(rules=[rule], events={"spied": {"at": when.isoformat(), "by": None, "lost": True, "count": 1}})
    changes, notes = rules.step(kd, when, HANDLERS)
    assert "schedule" not in changes and "you do not know who it was" in notes[0]


def test_low_fuel_fires_once_until_the_fuel_recovers():
    rule = _rule({"kind": "fuel_low", "hours": 6}, {"kind": "settings", "hours": 2, "settings": {"auto_rob_enabled": False}})
    epoch_hours = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600
    low = _kingdom(rules=[rule], fuel=100, income={"fuel": {"net": -100 * epoch_hours}})  # an hour of fuel left
    changes, _ = rules.step(low, NOW, HANDLERS)
    assert changes["auto_rob_enabled"] is False
    low.update(changes)
    changes, notes = rules.step(low, NOW + datetime.timedelta(minutes=5), HANDLERS)
    assert "auto_rob_enabled" not in changes and notes == []
    assert rules.fuel_hours_left({"fuel": 100, "income": {"fuel": {"net": 5}}}) is None


# --- the events, written where they happen ---------------------------------------------------------------------------


def test_an_attack_stamps_the_defender_with_who_attacked_and_whether_it_lost(app, client, jwt1):
    _set_up_two_kingdoms()
    assert _attack(client, jwt1).status_code == 200
    event = _get(f"/kingdom/{TARGET_ID}")["events"]["attacked"]
    assert event["by"] == KD_ID and event["lost"] is True and event["count"] == 1


def test_a_spy_operation_stamps_the_target_naming_the_spy_only_when_it_failed(app, client, jwt1, monkeypatch):
    _set_up_two_kingdoms()
    _create_item(f"kingdom_{KD_ID}", {"drones": 10_000, "spy_attempts": 5})
    _create_item(f"kingdom_{TARGET_ID}", {"drones": 0})
    monkeypatch.setattr(uac.random, "uniform", lambda a, b: 0.0)  # the operation works, the radar does not
    _create_item(f"kingdom_{TARGET_ID}", {"shields": {"military": 0, "spy": 0, "spy_radar": 0, "missiles": 0}})
    response = client.post(f"/api/spy/{TARGET_ID}", json={"drones": 1000, "shielded": False, "operation": "spykingdom"},
                           headers={"Authorization": f"Bearer {jwt1}"})
    assert response.status_code == 200, response.get_json()
    event = _get(f"/kingdom/{TARGET_ID}")["events"]["spied"]
    assert event["by"] is None and event["lost"] is True


# --- the routes ------------------------------------------------------------------------------------------------------


def test_adding_and_removing_a_rule(app, client, jwt1):
    _set_up_two_kingdoms()
    headers = {"Authorization": f"Bearer {jwt1}"}
    body = {"when": {"kind": "attacked"}, "then": _war_footing(), "cooldown_hours": 3}
    assert client.post("/api/rules", json=body, headers=headers).status_code == 200
    [rule] = _get(f"/kingdom/{KD_ID}")["rules"]
    assert rule["cooldown_hours"] == 3
    assert client.post("/api/rules/cancel", json={"id": rule["id"]}, headers=headers).status_code == 200
    assert _get(f"/kingdom/{KD_ID}")["rules"] == []


def test_the_number_of_rules_is_capped(app, client, jwt1, monkeypatch):
    monkeypatch.setitem(uas.GAME_CONFIG, "BASE_MAX_RULES", 1)
    _set_up_two_kingdoms()
    headers = {"Authorization": f"Bearer {jwt1}"}
    body = {"when": {"kind": "attacked"}, "then": _war_footing()}
    assert client.post("/api/rules", json=body, headers=headers).status_code == 200
    response = client.post("/api/rules", json=body, headers=headers)
    assert response.status_code == 400 and "more than 1" in response.get_json()["message"]


# --- build targets ---------------------------------------------------------------------------------------------------


def _defensive_build(hours=6):
    return {"kind": "settings", "hours": hours, "settings": {
        "units_target": {"defense": 70, "flex": 30},
        "structures_target": {"homes": 30, "hangars": 30, "fuel_plants": 40}}}


def test_targets_are_stored_as_whole_splits():
    rule = _rule({"kind": "attacked"}, _defensive_build())
    units = rule["then"]["settings"]["units_target"]
    assert units["defense"] == 0.7 and units["flex"] == 0.3 and units["attack"] == 0  # the rest is 0, not kept
    assert set(rule["then"]["settings"]["structures_target"]) == set(uas.INITIAL_KINGDOM_STATE["kingdom"]["structures_target"])


@pytest.mark.parametrize("settings, problem", [
    ({"units_target": {"tanks": 10}}, "There is no tanks to target"),
    ({"structures_target": {"homes": 60, "mines": 60}}, "The structure targets must be 0% to 100% and add up to at most 100%"),
])
def test_a_bad_target_is_refused(settings, problem):
    assert rules.make_rule({"when": {"kind": "attacked"}, "then": {"kind": "settings", "hours": 2, "settings": settings}}, NOW) == (None, problem)


def test_an_attack_switches_the_build_targets_and_they_go_back():
    rule = _rule({"kind": "attacked"}, _defensive_build(hours=6))
    before_units = {key: 0 for key in uas.INITIAL_KINGDOM_STATE["kingdom"]["units_target"]}
    before_units["attack"] = 1.0
    kd = _kingdom(rules=[rule], units_target=before_units, events=_attacked(NOW + datetime.timedelta(minutes=1)))
    changes, _ = rules.step(kd, NOW + datetime.timedelta(minutes=2), HANDLERS)
    assert changes["units_target"]["defense"] == 0.7 and changes["units_target"]["attack"] == 0
    assert changes["structures_target"]["fuel_plants"] == 0.4
    kd.update(changes)
    back, _ = rules.step(kd, NOW + datetime.timedelta(hours=7), HANDLERS)
    assert back["units_target"]["attack"] == 1.0 and back["units_target"]["defense"] == 0


def test_a_target_on_something_locked_when_it_fires_is_left_and_the_news_says_why():
    locked = next(unit for unit, info in uas.UNITS.items() if info.get("project"))
    rule = _rule({"kind": "attacked"}, {"kind": "settings", "hours": 2, "settings": {
        "units_target": {locked: 50}, "auto_rob_enabled": False}})
    kd = _kingdom(rules=[rule], auto_rob_enabled=True, events=_attacked(NOW + datetime.timedelta(minutes=1)))
    changes, notes = rules.step(kd, NOW + datetime.timedelta(minutes=2), HANDLERS)
    assert "units_target" not in changes and changes["auto_rob_enabled"] is False
    assert "unit targets not changed (Complete the" in notes[0]
    kd.update(changes)
    back, _ = rules.step(kd, NOW + datetime.timedelta(hours=3), HANDLERS)
    assert back["auto_rob_enabled"] is True and "units_target" not in back


def test_the_route_refuses_a_target_on_a_locked_unit(app, client, jwt1):
    _set_up_two_kingdoms()
    locked = next(unit for unit, info in uas.UNITS.items() if info.get("project"))
    body = {"when": {"kind": "attacked"}, "then": {"kind": "settings", "hours": 2, "settings": {"units_target": {locked: 50}}}}
    response = client.post("/api/rules", json=body, headers={"Authorization": f"Bearer {jwt1}"})
    assert response.status_code == 400 and response.get_json()["message"].startswith("Complete the")
