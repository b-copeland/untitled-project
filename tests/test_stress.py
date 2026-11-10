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
