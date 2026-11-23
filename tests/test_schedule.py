"""Scheduled attacks: how each way of counting the share picks units, the cap on the suggested army, and the news a
player gets when a scheduled action does nothing (issue #24)."""
import datetime

import pytest

import untitledapp.conquer as uac
import untitledapp.refresh as refresh
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get


def _kingdom(attack, flex, out_attack=0, out_flex=0, defense=0):
    out = [{"attack": out_attack, "flex": out_flex, "return_time": "2999-01-01T00:00:00+00:00"}] if out_attack or out_flex else []
    return {"units": {"attack": attack, "flex": flex, "defense": defense, "engineers": 0}, "generals_out": out}


# --- the share -------------------------------------------------------------------------------------------------------

def test_send_takes_the_share_of_the_whole_army():
    # 300 attackers at home and 100 out: 25% of the 400 is 100. Flexers: 50% of 200 is 100.
    units = refresh._schedule_units(_kingdom(300, 200, out_attack=100), 0.25, 0.5, uac.SCHEDULE_SEND)
    assert units == {"attack": 100, "flex": 100}  # units with no offense (defense, engineers) are never sent


def test_send_never_takes_more_than_is_at_home():
    units = refresh._schedule_units(_kingdom(50, 0, out_attack=350), 0.5, 0, uac.SCHEDULE_SEND)
    assert units == {"attack": 50, "flex": 0}


def test_up_to_counts_the_units_already_out():
    # 50% of 400 attackers is 200, and 100 are out already: send 100 more. Flexers: 30% of 100 is 30, 40 out: none.
    units = refresh._schedule_units(_kingdom(300, 60, out_attack=100, out_flex=40), 0.5, 0.3, uac.SCHEDULE_SEND_UP_TO)
    assert units == {"attack": 100, "flex": 0}


def test_an_entry_saved_before_the_choice_counts_up_to():
    kingdom = _kingdom(300, 0, out_attack=100)
    assert refresh._schedule_options_units(kingdom, {"pure_offense": 0.5}) == {"attack": 100, "flex": 0}


# --- the route -------------------------------------------------------------------------------------------------------

def _in_an_hour():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()


def _schedule(client, jwt, kind, **options):
    return client.post("/api/schedule", json={"type": kind, "time": _in_an_hour(), "options": options},
                       headers={"Authorization": f"Bearer {jwt}"})


def test_each_attack_type_has_its_own_default_way_of_counting(app, client, jwt1):
    _set_up_two_kingdoms()
    assert _schedule(client, jwt1, "attack", target=TARGET_ID, generals=1, pure_offense=25, flex_offense=0,
                     autofill_buffer=1, prefer_autofill=False).status_code == 200
    assert _schedule(client, jwt1, "attackprimitives", generals=1, pure_offense=25, flex_offense=0).status_code == 200
    attack, primitives = _get(f"/kingdom/{KD_ID}")["schedule"]
    assert (attack["options"]["units_mode"], attack["options"]["send_without_intel"]) == ("send", True)
    assert primitives["options"]["units_mode"] == "up_to"


@pytest.mark.parametrize("options, message", [
    ({"pure_offense": 25, "flex_offense": 0, "units_mode": "half"}, "how to count"),
    ({"pure_offense": 0, "flex_offense": 0}, "Send some attackers or flexers"),
])
def test_a_schedule_that_could_never_send_anything_is_refused(app, client, jwt1, options, message):
    _set_up_two_kingdoms()
    response = _schedule(client, jwt1, "attackprimitives", generals=1, **options)
    assert response.status_code == 400 and message in response.get_json()["message"]
    assert _get(f"/kingdom/{KD_ID}")["schedule"] == []


# --- running them ----------------------------------------------------------------------------------------------------

PAST = "2000-01-01T00:00:00+00:00"


def _due(kind, **options):
    return {"id": f"{kind}-{len(options)}-{sorted(options.items())}", "time": PAST, "type": kind, "options": options}


def _run(app, *schedules):
    _create_item(f"kingdom_{KD_ID}", {**_get(f"/kingdom/{KD_ID}"), "schedule": list(schedules)})
    with app.app_context():
        assert refresh._resolve_schedules(KD_ID, datetime.datetime.now(datetime.timezone.utc))


def _schedule_news():
    return [item["news"] for item in _get(f"/kingdom/{KD_ID}/news")["news"] if item.get("kind") == "schedule"]


def test_four_attacks_that_each_send_a_quarter_all_go(app):
    _set_up_two_kingdoms()
    quarter = {"generals": 1, "pure_offense": 0.25, "flex_offense": 0, "units_mode": "send"}
    _run(app, *[_due("attackprimitives", wave=i, **quarter) for i in range(4)])

    # Each wave counts the survivors still out, so the four are about a quarter each and all of them go.
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert len(kingdom["generals_out"]) == 4 and kingdom["units"]["attack"] < 50
    assert _schedule_news() == []


def test_a_second_up_to_attack_only_tops_up_to_the_share_and_says_why_when_that_is_too_little(app):
    _set_up_two_kingdoms()
    quarter = {"generals": 1, "pure_offense": 0.25, "flex_offense": 0, "units_mode": "up_to"}
    _run(app, _due("attackprimitives", wave=1, **quarter), _due("attackprimitives", wave=2, **quarter))

    # The first sent 250 and lost a few; the second could only make up those few, which the primitives refuse.
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert len(kingdom["generals_out"]) == 1 and kingdom["units"]["attack"] == 750
    (news,) = _schedule_news()
    assert news.startswith("Your scheduled attack on the primitives did not run. ")


def _reveal_military():
    _create_item(f"revealed_{KD_ID}", {"revealed": {TARGET_ID: {"military": "2999-01-01T00:00:00+00:00"}},
                                       "galaxies": {}, "revealed_galaxymates": [], "revealed_to_galaxymates": []})


def _suggested_attack(share, **extra):
    return _due("attack", target=TARGET_ID, generals=1, prefer_autofill=True, autofill_buffer=0.05,
                pure_offense=share, flex_offense=0, units_mode="send", **extra)


def test_the_suggested_army_stays_within_the_share(app):
    _set_up_two_kingdoms(attacker_attack=1000, target_defense=100)
    _reveal_military()
    _run(app, _suggested_attack(0.5))

    kingdom = _get(f"/kingdom/{KD_ID}")
    assert len(kingdom["generals_out"]) == 1
    assert 500 <= kingdom["units"]["attack"] < 1000  # the suggestion, within the share
    assert _schedule_news() == []


def test_a_suggestion_that_needs_more_than_the_share_sends_nothing_and_says_why(app):
    _set_up_two_kingdoms(attacker_attack=1000, target_defense=500)
    _reveal_military()
    _run(app, _suggested_attack(0.1))

    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["units"]["attack"] == 1000 and kingdom["generals_out"] == []
    (news,) = _schedule_news()
    assert news.startswith("Your scheduled attack did not run. Your military intel shows it would fail")


def test_without_intel_it_sends_the_share_unless_told_not_to(app):
    _set_up_two_kingdoms(attacker_attack=1000, target_defense=10)
    _run(app, _suggested_attack(0.3, send_without_intel=False))
    assert _get(f"/kingdom/{KD_ID}")["generals_out"] == []
    (news,) = _schedule_news()
    assert "no military intel" in news

    _run(app, _suggested_attack(0.3))  # an entry saved before the switch existed: send the share
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert len(kingdom["generals_out"]) == 1 and kingdom["units"]["attack"] == 700


def test_a_refused_action_is_reported(app):
    _set_up_two_kingdoms()
    _run(app, _due("attackprimitives", generals=5, pure_offense=0.5, flex_offense=0, units_mode="send"))
    (news,) = _schedule_news()
    assert news.startswith("Your scheduled attack on the primitives did not run. ")


def test_scheduled_missiles_launch_once(app, monkeypatch):
    _set_up_two_kingdoms()
    launches = []
    monkeypatch.setattr(refresh.uac, "_launch_missiles", lambda *args: launches.append(args) or (None, {}, 200))
    _run(app, _due("missiles", target=TARGET_ID, planet_busters=1, star_busters=0, galaxy_busters=0))
    assert len(launches) == 1
