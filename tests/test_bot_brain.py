"""The bot brain: what each rule decides on a made-up view of the world, then one bot driven through the real refresh."""
import datetime
import random
import types

import pytest

import untitledapp.botbrain as brain
import untitledapp.refresh as refresh
import untitledapp.occ as occ
import untitledapp.shared as uas
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, no_shared_lock, _create_item, _get  # noqa: F401

NOW = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
HOUR = datetime.timedelta(hours=1)
MINUTE = datetime.timedelta(minutes=1)


class StubWorld(brain.World):
    """A world made of plain data, so the rules can be tried without a backend."""

    def __init__(self, me=None, galaxies=None, revealed=None, info=None, outcomes=None):
        self.kd_id = "1"
        self.now = NOW
        self.me = {"generals_available": 3, "units": {"attack": 1000, "flex": 500}, "spy_attempts": 8, "drones": 5000,
                   "schedule": [], "missiles": {}, "votes": 0, **(me or {})}
        galaxies = galaxies or {"g1": ["1", "2"], "g2": ["3", "4", "5"]}
        self.galaxies = galaxies
        self.galaxy_of = {kd: galaxy for galaxy, members in galaxies.items() for kd in members}
        self.names = {kd: f"Kd{kd}" for kd in self.galaxy_of}
        self.revealed = revealed or {}
        self.revealed_info = {"revealed": self.revealed, "revealed_galaxymates": []}
        self.state = {"state": {"game_end": (NOW + 30 * 24 * HOUR).isoformat(), "election_end": ""}}
        self._info = info or {}
        self._outcomes = outcomes or {}

    def target_info(self, target):
        return self._info.get(target, {})

    def evaluate_attack(self, target, generals, buffer_percent):
        return self._outcomes.get(target)


def until(hours):
    return (NOW + hours * HOUR).isoformat()


def test_every_personality_is_legal_and_covers_every_archetype():
    import untitledapp.bots as bots

    assert set(brain.PERSONALITIES) == set(bots.ARCHETYPES)
    for key, personality in brain.PERSONALITIES.items():
        assert brain.problems(personality) == [], key


def test_an_illegal_edit_is_caught():
    import dataclasses

    bad = dataclasses.replace(brain.PERSONALITIES["attacker"], attack_generals=(1, 9), intel_ops=("siphonfunds",),
                              galaxy_votes={"policy_1": "7"})
    found = " ".join(brain.problems(bad))
    assert "generals" in found and "siphonfunds" in found and "policy_1" in found


def test_it_attacks_the_biggest_target_it_can_beat_and_leaves_the_rest():
    world = StubWorld(
        revealed={"3": {"military": until(30)}, "4": {"military": until(30)}, "5": {"military": until(30)}},
        info={"3": {"stars": 300}, "4": {"stars": 900}, "5": {"stars": 500}},
        outcomes={"3": (2000, 1000), "4": (500, 1000), "5": (2000, 1900)},  # 4 can not be beaten
    )
    personality = brain.PERSONALITIES["attacker"]
    decisions = brain.plan_attack(world, personality, ChanceOf(0.0))
    assert [d.kind for d in decisions] == ["attack"]
    assert decisions[0].options["target"] in ("3", "5")  # never 4, which it would lose to
    assert decisions[0].options["prefer_autofill"] is True
    assert 1 <= decisions[0].options["generals"] <= 3


def test_without_intel_it_sends_spies_for_it_instead_of_attacking_blind():
    world = StubWorld()
    decisions = brain.plan_attack(world, brain.PERSONALITIES["attacker"], ChanceOf(0.0))
    assert [d.kind for d in decisions] == ["intelspy"]
    assert decisions[0].options["operation"] == "spymilitary"
    assert decisions[0].options["target"] in ("3", "4", "5")  # never a galaxymate


def test_no_generals_or_no_offense_means_no_attack():
    personality = brain.PERSONALITIES["attacker"]
    assert brain.plan_attack(StubWorld(me={"generals_available": 0}), personality, ChanceOf(0.0)) == []
    assert brain.plan_attack(StubWorld(me={"units": {"defense": 900}}), personality, ChanceOf(0.0)) == []


def test_expiring_intel_does_not_count_as_intel():
    # Gone before the attack would run, so it is not enough to attack on: it asks for fresh intel instead.
    world = StubWorld(revealed={"3": {"military": until(0.2)}}, info={"3": {"stars": 300}}, outcomes={"3": (2000, 1000)})
    decisions = brain.plan_attack(world, brain.PERSONALITIES["attacker"], ChanceOf(0.0))
    assert [d.kind for d in decisions] == ["intelspy"]


def test_spies_never_spend_the_attempts_it_keeps_back():
    thief = brain.PERSONALITIES["thief"]  # keeps 5
    assert brain.plan_intel(StubWorld(me={"spy_attempts": 5}), thief, ChanceOf(0.0), force=True) == []
    decisions = brain.plan_intel(StubWorld(me={"spy_attempts": 7}), thief, ChanceOf(0.0), force=True)
    assert decisions and decisions[0].options["max_tries"] <= 2


def test_intel_bots_share_what_they_learn_and_others_rarely_do():
    shares = lambda key: sum(
        brain.plan_intel(StubWorld(), brain.PERSONALITIES[key], random.Random(seed), force=True)[0].options["share_to_galaxy"]
        for seed in range(200))
    assert shares("intel") > 150 and shares("attacker") < 80


def test_thieves_siphon_the_richest_target_they_know_the_money_of():
    world = StubWorld(
        revealed={"3": {"kingdom": until(30)}, "4": {"kingdom": until(30)}},
        info={"3": {"money": 100}, "4": {"money": 9000}},
    )
    decisions = brain.plan_aggressive(world, brain.PERSONALITIES["thief"], ChanceOf(0.0))
    assert decisions[0].kind == "aggressivespy" and decisions[0].options["target"] == "4"
    assert decisions[0].options["operation"] == "siphonfunds"


def test_thieves_find_out_who_is_rich_before_siphoning():
    decisions = brain.plan_aggressive(StubWorld(), brain.PERSONALITIES["thief"], ChanceOf(0.0))
    assert decisions[0].kind == "intelspy" and decisions[0].options["operation"] == "spykingdom"


def test_missiles_name_all_three_kinds_and_keep_some_back():
    world = StubWorld(me={"missiles": {"planet_busters": 10, "star_busters": 0, "galaxy_busters": 0}},
                      revealed={"4": {"kingdom": until(30)}}, info={"4": {"stars": 700}})
    (decision,) = brain.plan_missiles(world, brain.PERSONALITIES["attacker"], ChanceOf(0.0))
    assert set(decision.options) == {"target", "planet_busters", "star_busters", "galaxy_busters"}
    assert 1 <= decision.options["planet_busters"] < 10


def test_actions_are_spread_over_the_interval_not_all_at_once():
    world = StubWorld(revealed={"3": {"military": until(30)}}, info={"3": {"stars": 3}}, outcomes={"3": (2, 1)},
                      me={"votes": 100})
    personality = brain.PERSONALITIES["attacker"]
    delays = set()
    for seed in range(30):
        for decision in brain.plan(world_without_politics(world), personality, random.Random(seed)):
            assert 0 < decision.delay <= personality.think_epochs[1] * brain.EPOCH
            delays.add(round(decision.delay))
    assert len(delays) > 20


def test_each_bot_thinks_at_its_own_time():
    personality = brain.PERSONALITIES["explorer"]
    firsts = {brain.first_think_time(personality, random.Random(seed), NOW) for seed in range(50)}
    nexts = {brain.next_think_time(personality, random.Random(seed), NOW) for seed in range(50)}
    assert len(firsts) == len(nexts) == 50
    low, high = personality.think_epochs
    assert all(NOW + datetime.timedelta(seconds=low * brain.EPOCH) <= t <= NOW + datetime.timedelta(seconds=high * brain.EPOCH) for t in nexts)


def test_a_full_schedule_stops_it_adding_more():
    personality = brain.PERSONALITIES["intel"]
    busy = StubWorld(me={"schedule": [{}] * personality.max_pending})
    assert [d for d in brain.plan(world_without_politics(busy), personality, random.Random(1)) if d.kind in brain._SCHEDULERS] == []


class ChanceOf:
    """A random source that always rolls the same: 0.0 passes every chance, and ``choice``/``sample`` take the first."""

    def __init__(self, roll):
        self.roll = roll
        self._real = random.Random(7)

    def random(self):
        return self.roll

    def uniform(self, low, high):
        return self._real.uniform(low, high)

    def randint(self, low, high):
        return self._real.randint(low, high)

    def choice(self, items):
        return items[0]

    def sample(self, items, count):
        return list(items)[:count]


def world_without_politics(world):
    """The rules that need no backend: politics reads the galaxy's votes from it."""
    world.plan_politics_skipped = True
    return world


@pytest.fixture(autouse=True)
def no_politics_reads(monkeypatch):
    """``plan`` also asks the backend how the galaxy has voted; the stub world has no backend, so say nobody has."""
    real = brain.plan_politics

    def politics(world, personality, rng):
        if getattr(world, "plan_politics_skipped", False):
            return []
        return real(world, personality, rng)

    monkeypatch.setattr(brain, "plan_politics", politics)


# ---------------------------------------------------------------------------------------------------- with a backend

def _make_kingdom_one_a_bot(kind="attacker", **fields):
    """Kingdom 1 becomes a bot of ``kind`` that is due to think, with a galaxy politics document it can vote in."""
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Bot", TARGET_ID: "Target"}})
    _create_item("galaxy_votes_1", {
        "votes": {"policy_1": {}, "policy_2": {}, "leader": {}}, "active_policies": [], "leader": "",
        "policy_1_winner": "", "policy_2_winner": "", "empire_invitations": [], "empire_join_requests": [],
    })
    long_ago = (datetime.datetime.now(datetime.timezone.utc) - 2 * HOUR).isoformat()
    with_bot = {"bot": {"type": kind, "next_think": (NOW - HOUR).isoformat(), "log": []}, "last_income": long_ago, **fields}
    kd = _get(f"/kingdom/{KD_ID}")
    if "next_resolve" in fields:  # only the named categories change
        with_bot["next_resolve"] = {**kd["next_resolve"], **fields["next_resolve"]}
    _create_item(f"kingdom_{KD_ID}", {**kd, **with_bot})


def _think(rng_seed=1, now=None):
    return brain.think(KD_ID, now=now or datetime.datetime.now(datetime.timezone.utc), rng=random.Random(rng_seed))


def test_a_bot_that_knows_the_enemys_army_schedules_an_attack_and_votes(app, client):
    _make_kingdom_one_a_bot("attacker")
    now = datetime.datetime.now(datetime.timezone.utc)
    _create_item(f"revealed_{KD_ID}", {
        "revealed": {TARGET_ID: {"military": (now + 12 * HOUR).isoformat()}},
        "galaxies": {}, "revealed_galaxymates": [], "revealed_to_galaxymates": [],
    })
    with app.app_context():
        for seed in range(40):  # the attack is a chance, so give it a few goes
            decisions = _think(seed, now)
            if any(d.kind == "attack" for d in decisions):
                break
        else:
            pytest.fail("never decided to attack a kingdom it could beat")

    kingdom = _get(f"/kingdom/{KD_ID}")
    attacks = [item for item in kingdom["schedule"] if item["type"] == "attack"]
    assert attacks and attacks[0]["options"]["target"] == TARGET_ID and attacks[0]["options"]["prefer_autofill"] is True
    assert all(now < datetime.datetime.fromisoformat(item["time"]) for item in kingdom["schedule"])
    assert datetime.datetime.fromisoformat(kingdom["bot"]["next_think"]) > now
    assert any(entry["kind"] == "attack" and "scheduled" in entry["outcome"] for entry in kingdom["bot"]["log"])
    # The attacker votes Warlike and Conscription in its galaxy.
    votes = _get("/galaxy/1/politics")
    assert votes["votes"]["policy_1"] == {KD_ID: "2"} and "Warlike" in votes["active_policies"]


def test_a_bot_votes_only_once_for_the_same_thing(app, client):
    _make_kingdom_one_a_bot("explorer")
    with app.app_context():
        first = _think(1)
        second = _think(2)
    assert sum(d.kind == "vote_galaxy" for d in first) == 2
    assert sum(d.kind == "vote_galaxy" for d in second) == 0


class Eager(random.Random):
    """Every chance comes up, and every range gives its low end: the bot does everything it can, as soon as it can."""

    def random(self):
        return 0.0


def test_the_refresh_wakes_a_bot_and_its_scheduled_actions_run_when_due(app, client, monkeypatch):
    """End to end: a due bot thinks in the refresh, and a spy it queued runs when it falls due."""
    monkeypatch.setattr(brain, "random", types.SimpleNamespace(Random=Eager))
    _make_kingdom_one_a_bot("intel", spy_attempts=10)
    with app.app_context():
        now = datetime.datetime.now(datetime.timezone.utc)
        state = refresh.uag._get_state()
        for step in range(1, 4):  # the intel personality queues things within 75 minutes
            refresh._refresh_kd(KD_ID, state, now + step * 40 * MINUTE, False)
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["bot"]["log"], "the bot never thought"
    # The first think queued a spy on the other galaxy's kingdom; once due, the refresh ran it through the real spy
    # code (this is the path that used to call a function that does not exist).
    assert any(entry["kind"] == "intelspy" for entry in kingdom["bot"]["log"])
    assert kingdom["spy_attempts"] < 10
    assert len(_get(f"/kingdom/{KD_ID}/spyhistory")["spy_history"]) >= 1


def test_a_player_kingdom_is_left_alone_by_the_refresh(app, client):
    _set_up_two_kingdoms()
    with app.app_context():
        assert brain.maybe_think(_get(f"/kingdom/{KD_ID}"), datetime.datetime.now(datetime.timezone.utc)) is False
    assert "bot" not in _get(f"/kingdom/{KD_ID}")


def test_auto_spending_copes_with_a_general_carrying_a_unit_the_plan_does_not_list(app, client):
    """Regression: attackers send big_flex units that their unit targets do not name, and the refresh used to raise KeyError
    for them every tick (found by running the bots on a real stack)."""
    _make_kingdom_one_a_bot(
        "attacker",
        units_target={"attack": 0.5, "defense": 0.5},
        funding={"settle": 0, "structures": 0, "military": 5000, "engineers": 0},
        generals_out=[{"return_time": (NOW + 5 * HOUR).isoformat(), "attack": 10, "flex": 5, "big_flex": 3}],
        next_resolve={"auto_spending": (NOW - HOUR).isoformat()},
    )
    with app.app_context():
        state = refresh.uag._get_state()
        refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)
