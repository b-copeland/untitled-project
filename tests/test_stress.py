"""
Mixed-action stress test with exact conservation checks.

A pile of different requests hit one kingdom at the same moment (lock off, like several web app instances). Whatever
order they land in, the books must balance exactly: every success changes the kingdom by a known amount, so the end
state is fully determined by how many of each succeeded. A lost update or a duplicated action shows up as a mismatch.

Needs the function app and Azurite running, like the rest of this directory. Slower than the others, so it is the
last thing to add rounds to when looking for rare races: raise ROUNDS or set STRESS_ROUNDS.
"""
import os
import random
import collections

import pytest

import untitledapp.getters as uag
import untitledapp.shared as uas

from tests.test_concurrency import (  # noqa: F401  (the autouse lock-off fixture must be active here too)
    KD_ID, no_shared_lock, _get, _post, _run_together, _set_up_kingdom,
)

ROUNDS = int(os.environ.get("STRESS_ROUNDS", "3"))
REQUESTS_PER_ROUND = 40
TRAIN, DISBAND, RAZE, BUILD, SPEND = "train", "disband", "raze", "build", "spend"


@pytest.mark.parametrize("seed", range(ROUNDS))
def test_every_success_is_accounted_for_exactly_once(app, client, jwt1, seed):
    rng = random.Random(seed)
    attack_cost = uas.UNITS["attack"]["cost"]
    start = {"attack": 30, "recruits": 400, "homes": 20}
    money0 = 5_000_000
    _set_up_kingdom(
        money=money0,
        units={"attack": start["attack"], "defense": 0, "flex": 0, "recruits": start["recruits"],
               "engineers": 0, "big_flex": 0},
        structures={"homes": start["homes"], "mines": 0, "fuel_plants": 0, "hangars": 0, "drone_factories": 0,
                    "missile_silos": 0, "workshops": 0},
    )
    plan = [rng.choice([TRAIN, TRAIN, DISBAND, RAZE, SPEND]) for _ in range(REQUESTS_PER_ROUND)]

    def request(c, i):
        headers = {"Authorization": f"Bearer {jwt1}"}
        kind = plan[i]
        if kind == TRAIN:
            return c.post("/api/mobis", json={"attack": 5}, headers=headers)
        if kind == DISBAND:
            return c.post("/api/mobis/disband", json={"input": {"attack": "3"}}, headers=headers)
        if kind == RAZE:
            return c.post("/api/structures/raze", json={"input": {"homes": "2"}}, headers=headers)
        return c.post("/api/spending", json={"settle": rng.choice([1, 2, 3])}, headers=headers)

    responses = _run_together(app, REQUESTS_PER_ROUND, request)
    ok = collections.Counter(plan[i] for i, r in enumerate(responses) if r.status_code == 200)
    assert all(r.status_code in (200, 400) for r in responses), [r.status_code for r in responses]

    kingdom = _get(f"/kingdom/{KD_ID}")
    queue = _get(f"/kingdom/{KD_ID}/mobis")
    queued_attack = sum(batch.get("attack", 0) for batch in next(v for v in queue.values() if isinstance(v, list)))

    assert kingdom["units"]["recruits"] == start["recruits"] - 5 * ok[TRAIN]
    assert queued_attack == 5 * ok[TRAIN]
    assert kingdom["units"]["attack"] == start["attack"] - 3 * ok[DISBAND]
    assert kingdom["structures"]["homes"] == start["homes"] - 2 * ok[RAZE]
    assert kingdom["units"]["attack"] >= 0 and kingdom["structures"]["homes"] >= 0
    # money: spent on training, returned on disband and raze
    with app.app_context():
        kingdom_at_start = {**kingdom, "structures": {**kingdom["structures"], "homes": start["homes"]}}
        raze_price = uag._get_structure_price(kingdom_at_start)
    expected_money = (
        money0
        - ok[TRAIN] * 5 * attack_cost
        + ok[DISBAND] * 3 * attack_cost * uas.GAME_CONFIG["BASE_DISBAND_COST_RETURN"]
        + ok[RAZE] * 2 * raze_price * uas.GAME_CONFIG["BASE_STRUCTURES_RAZE_RETURN"]
    )
    assert kingdom["money"] == pytest.approx(expected_money)


def test_refresh_ticks_racing_player_actions_lose_and_duplicate_nothing(app, client, jwt1):
    """
    Finished training is credited by the periodic refresh while the player trains more and the refresh runs again and
    again. At the end every unit is accounted for: credited exactly once, queued exactly once, nothing negative.
    """
    import datetime
    import threading
    import untitledapp.refresh as refresh
    import untitledapp.getters as getters
    from tests.test_concurrency import _create_item

    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
    _set_up_kingdom(
        money=5_000_000,
        units={"attack": 30, "defense": 0, "flex": 0, "recruits": 400, "engineers": 0, "big_flex": 0},
    )
    kingdom = _get(f"/kingdom/{KD_ID}")
    _create_item(f"kingdom_{KD_ID}", {**kingdom, "last_income": past, "next_resolve": {**kingdom["next_resolve"], "mobis": past}})
    _create_item(f"mobis_{KD_ID}", {"mobis": [
        {"time": past, "attack": 10, "defense": 0, "flex": 0, "big_flex": 0, "recruits": 0} for _ in range(5)
    ]})

    outcomes = []
    tick_errors = []
    gate = threading.Barrier(14)

    def train():
        client_ = app.test_client()
        gate.wait()
        outcomes.append(client_.post("/api/mobis", json={"attack": 5},
                                     headers={"Authorization": f"Bearer {jwt1}"}).status_code)

    def tick():
        with app.app_context():
            state = getters._get_state()
            gate.wait()
            for _ in range(3):
                try:
                    refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)
                except Exception as error:  # a tick that gives up is fine, the next one runs a minute later
                    import traceback; tick_errors.append(traceback.format_exc())

    threads = [threading.Thread(target=train) for _ in range(10)] + [threading.Thread(target=tick) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    trained = outcomes.count(200)
    kingdom = _get(f"/kingdom/{KD_ID}")
    queue = _get(f"/kingdom/{KD_ID}/mobis")["mobis"]
    queued_attack = sum(batch.get("attack", 0) for batch in queue)
    assert trained == 10  # money and recruits for all of them
    assert kingdom["units"]["recruits"] == 400 - 5 * trained
    # Some of the newly queued batches may themselves have finished by a later tick (an epoch is short in the test
    # config), so count them wherever they ended up: in the kingdom or still queued. Each unit exists exactly once.
    assert kingdom["units"]["attack"] + queued_attack == 30 + 5 * 10 + 5 * trained
    assert kingdom["units"]["attack"] >= 30 + 5 * 10  # the five finished batches were credited, once
