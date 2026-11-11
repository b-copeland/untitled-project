"""
Attack behaviour, through the real route: who loses what, who gains what, and what gets recorded.

These pin the outcome of one attack so that changes to how attacks are committed (see docs/concurrency.md) can be
checked against the game rules as they were.
"""
import json

import pytest

import untitledapp.shared as uas

from tests.test_concurrency import (  # noqa: F401
    KD_ID, no_shared_lock, _create_item, _get, _post, _run_together, _set_up_kingdom,
)

TARGET_ID = "2"


def _set_up_two_kingdoms(attacker_attack=1000, target_defense=10, target_overrides=None):
    _set_up_kingdom(
        money=1_000_000,
        units={"attack": attacker_attack, "defense": 0, "flex": 0, "recruits": 0, "engineers": 0, "big_flex": 0},
    )
    target = {"units": {"attack": 0, "defense": target_defense, "flex": 0, "recruits": 0, "engineers": 0,
                        "big_flex": 0}}
    target.update(target_overrides or {})
    _set_up_kingdom(money=1_000_000, kd_id=TARGET_ID, **target)
    _create_item("galaxies", {"galaxies": {"1": [KD_ID], "2": [TARGET_ID]}})
    for galaxy in ("1", "2"):
        _create_item(f"galaxy_votes_{galaxy}", {"active_policies": [], "votes": {}})
        _create_item(f"galaxy_news_{galaxy}", {"news": []})
    _create_item("empires", {"empires": {}})


def _attack(client, jwt, units=1000):
    return client.post(
        f"/api/attack/{TARGET_ID}",
        json={"attackerValues": {"attack": units, "generals": 1}},
        headers={"Authorization": f"Bearer {jwt}"},
    )


def test_a_successful_attack_moves_spoils_and_records_both_sides(app, client, jwt1):
    _set_up_two_kingdoms()
    attacker0, target0 = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")

    response = _attack(client, jwt1)

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["status"] == "success"
    attacker, target = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")
    stars_taken = target0["stars"] - target["stars"]
    assert stars_taken > 0
    assert attacker["stars"] == attacker0["stars"] + stars_taken  # no intel was shared, so the attacker keeps it all
    assert target["money"] < target0["money"] and attacker["money"] > attacker0["money"]
    assert attacker["units"]["attack"] == 0  # all sent out
    assert len(attacker["generals_out"]) == 1 and attacker["generals_available"] == attacker0["generals_available"] - 1
    assert target["units"]["defense"] <= target0["units"]["defense"]
    assert len(_get(f"/kingdom/{TARGET_ID}/news")["news"]) == 1
    assert len(_get(f"/kingdom/{KD_ID}/attackhistory")["attack_history"]) == 1
    assert len(_get("/galaxy/1/news")["news"]) == 1 and len(_get("/galaxy/2/news")["news"]) == 1


def test_a_failed_attack_takes_nothing(app, client, jwt1):
    _set_up_two_kingdoms(attacker_attack=1, target_defense=10_000)
    attacker0, target0 = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")

    response = _attack(client, jwt1, units=1)

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["status"] == "failure"
    assert _get(f"/kingdom/{TARGET_ID}")["stars"] == target0["stars"]
    assert _get(f"/kingdom/{KD_ID}")["stars"] == attacker0["stars"]


def test_attacking_a_dead_kingdom_is_refused_and_keeps_the_units_home(app, client, jwt1):
    _set_up_two_kingdoms(target_overrides={"status": "Dead"})

    response = _attack(client, jwt1)

    assert response.status_code == 400
    assert _get(f"/kingdom/{KD_ID}")["units"]["attack"] == 1000


def test_sending_more_units_than_you_have_is_refused(app, client, jwt1):
    _set_up_two_kingdoms(attacker_attack=10)
    assert _attack(client, jwt1, units=1000).status_code == 400
    assert _get(f"/kingdom/{KD_ID}")["units"]["attack"] == 10


@pytest.mark.parametrize("repeat", range(3))  # the overlap is down to timing, so a few tries find it more reliably
def test_racing_duplicate_attacks_send_the_units_once(app, client, jwt1, repeat):
    _set_up_two_kingdoms()
    attacker0, target0 = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")

    responses = _run_together(app, 8, lambda c, i: _attack(c, jwt1))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    attacker, target = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")
    assert len(attacker["generals_out"]) == 1
    assert attacker["generals_available"] == attacker0["generals_available"] - 1
    stars_taken = target0["stars"] - target["stars"]
    assert attacker["stars"] == attacker0["stars"] + stars_taken
    assert len(_get(f"/kingdom/{TARGET_ID}/news")["news"]) == 1
    assert len(_get(f"/kingdom/{KD_ID}/attackhistory")["attack_history"]) == 1


def test_attacks_and_the_targets_own_actions_at_the_same_time_lose_nothing(app, client, jwt1, jwt2):
    """The target spends money while being attacked: both must be reflected."""
    _set_up_two_kingdoms(target_overrides={"units": {"attack": 0, "defense": 10, "flex": 0, "recruits": 400,
                                                      "engineers": 0, "big_flex": 0}})
    target0 = _get(f"/kingdom/{TARGET_ID}")

    def request(c, i):
        if i == 0:
            return _attack(c, jwt1)
        return c.post("/api/mobis", json={"attack": 5}, headers={"Authorization": f"Bearer {jwt2}"})

    responses = _run_together(app, 6, request)

    assert responses[0].status_code == 200, responses[0].get_json()
    trained = sum(1 for r in responses[1:] if r.status_code == 200)
    attacker, target = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")
    plundered = attacker["money"] - 1_000_000
    assert plundered > 0 and target["stars"] < target0["stars"]
    # what the target started with, less what it spent training, less what the attacker took: nothing else
    assert target["money"] == pytest.approx(1_000_000 - trained * 5 * uas.UNITS["attack"]["cost"] - plundered)


def _attack_primitives(client, jwt, units=100000):
    return client.post(
        "/api/attackprimitives",
        json={"attackerValues": {"attack": units, "generals": 1}},
        headers={"Authorization": f"Bearer {jwt}"},
    )


@pytest.mark.parametrize("repeat", range(3))
def test_racing_duplicate_attacks_on_primitives_send_the_units_once(app, client, jwt1, repeat):
    _set_up_two_kingdoms(attacker_attack=100000)
    stars0 = _get(f"/kingdom/{KD_ID}")["stars"]

    responses = _run_together(app, 8, lambda c, i: _attack_primitives(c, jwt1))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    attacker = _get(f"/kingdom/{KD_ID}")
    assert len(attacker["generals_out"]) == 1
    assert attacker["units"]["attack"] == 0
    assert attacker["stars"] > stars0
    assert len(_get(f"/kingdom/{KD_ID}/attackhistory")["attack_history"]) == 1


def test_an_attack_on_primitives_gains_stars_and_records_history(app, client, jwt1):
    _set_up_two_kingdoms(attacker_attack=100000)
    stars0 = _get(f"/kingdom/{KD_ID}")["stars"]

    response = _attack_primitives(client, jwt1)

    assert response.status_code == 200, response.get_json()
    assert _get(f"/kingdom/{KD_ID}")["stars"] > stars0


def _launch(client, jwt, count=5):
    return client.post(
        f"/api/launchmissiles/{TARGET_ID}",
        json={"attackerValues": {"planet_busters": count}},
        headers={"Authorization": f"Bearer {jwt}"},
    )


def _with_missiles(count):
    _set_up_two_kingdoms()
    kingdom = _get(f"/kingdom/{KD_ID}")
    _create_item(f"kingdom_{KD_ID}", {**kingdom, "missiles": {**kingdom["missiles"], "planet_busters": count}})


def test_missiles_damage_the_target_and_are_used_up(app, client, jwt1):
    _with_missiles(5)
    target0 = _get(f"/kingdom/{TARGET_ID}")

    response = _launch(client, jwt1)

    assert response.status_code == 200, response.get_json()
    assert _get(f"/kingdom/{KD_ID}")["missiles"]["planet_busters"] == 0
    assert _get(f"/kingdom/{TARGET_ID}")["stars"] < target0["stars"]
    assert len(_get(f"/kingdom/{KD_ID}/missilehistory")["missile_history"]) == 1


@pytest.mark.parametrize("repeat", range(3))
def test_racing_duplicate_missile_launches_use_the_missiles_once(app, client, jwt1, repeat):
    _with_missiles(5)
    target0 = _get(f"/kingdom/{TARGET_ID}")

    responses = _run_together(app, 8, lambda c, i: _launch(c, jwt1))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    assert _get(f"/kingdom/{KD_ID}")["missiles"]["planet_busters"] == 0
    stars_lost = target0["stars"] - _get(f"/kingdom/{TARGET_ID}")["stars"]
    assert stars_lost == 5 * 1  # planet_busters do 1 star of damage each against no shields
    assert len(_get(f"/kingdom/{KD_ID}/missilehistory")["missile_history"]) == 1


def _in_threads(app, count, work):
    import threading

    gate = threading.Barrier(count)

    def run(i):
        with app.app_context():
            gate.wait()
            work(i)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_aggression_added_at_the_same_time_is_all_counted(app, client):
    import untitledapp.conquer as conquer

    _create_item("empires", {"empires": {"e1": {"aggression": {}}, "e2": {"aggression": {}}}})

    _in_threads(app, 16, lambda i: conquer._add_aggression("e1", "e2", 2))

    assert _get("/empires")["empires"]["e1"]["aggression"]["e2"] == 32


def test_overlapping_reveal_timers_end_up_at_the_earliest(app, client):
    import untitledapp.conquer as conquer

    _set_up_kingdom(money=0)
    times = [f"2030-01-{day:02d}T00:00:00+00:00" for day in range(1, 17)]

    _in_threads(app, 16, lambda i: conquer._lower_reveal_timer(KD_ID, times[i]))

    assert _get(f"/kingdom/{KD_ID}")["next_resolve"]["revealed"] == times[0]
    other = f"2031-01-01T00:00:00+00:00"
    _in_threads(app, 1, lambda i: conquer._lower_reveal_timer(KD_ID, other))
    assert _get(f"/kingdom/{KD_ID}")["next_resolve"]["revealed"] == times[0]  # a later time never moves it back


def test_a_refused_auto_attack_or_auto_rob_does_not_break_the_tick(app, client):
    """The attack and rob helpers answer a refusal with no kingdom document; the refresh must not trip over that."""
    import untitledapp.refresh as refresh

    _set_up_two_kingdoms(attacker_attack=0)
    kingdom = _get(f"/kingdom/{KD_ID}")
    kingdom = {**kingdom, "auto_attack_settings": {"pure": 0.5, "flex": 0.5},
               "auto_rob_settings": {"drones": 0.5, "shielded": False, "keep": 100},
               "spy_attempts": 500, "generals_available": 4}
    with app.app_context():
        assert refresh._resolve_auto_attack(kingdom) is True  # no units to send: refused, and still fine
        assert refresh._resolve_auto_rob({**kingdom, "drones": 0}) is True
