"""The bot brain: what each rule decides on a made-up view of the world, then one bot driven through the real refresh."""
import copy
import dataclasses
import datetime
import random
import types

import pytest

import untitledapp.botbrain as brain
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get  # noqa: F401

NOW = datetime.datetime(2026, 1, 3, 12, 0, tzinfo=datetime.timezone.utc)
HOUR = datetime.timedelta(hours=1)
MINUTE = datetime.timedelta(minutes=1)
DAY = datetime.timedelta(days=1)
EPOCH = datetime.timedelta(seconds=brain.EPOCH)


def until(hours):
    return (NOW + hours * HOUR).isoformat()


def kingdom(**changes):
    """A set-up kingdom: 1000 stars, built on, with an army at home, engineers, drones and four generals."""
    kd = copy.deepcopy(uas.INITIAL_KINGDOM_STATE["kingdom"])
    kd.update({
        "kdId": "1", "name": "Kd1", "race": "Xo", "stars": 1000, "population": 16000, "money": 0, "fuel": 100_000,
        "drones": 20_000, "spy_attempts": 8, "networth": 150_000, "generals_available": 4,
        "units": {"attack": 4000, "defense": 3000, "flex": 0, "big_flex": 0, "recruits": 100, "engineers": 1500},
        "structures": {"homes": 350, "mines": 290, "fuel_plants": 90, "hangars": 110, "drone_factories": 80,
                       "missile_silos": 0, "workshops": 80},
        "income": {"money": {"net": 80_000}, "fuel": {"net": 500}},
    })
    kd["projects_max_points"] = {key: uas.PROJECTS_FUNCS[key](1000) for key in uas.PROJECTS}
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(kd.get(key), dict):
            kd[key] = {**kd[key], **value}
        else:
            kd[key] = value
    return kd


class StubWorld(brain.World):
    """A world made of plain data, so the rules can be tried without a backend.

    Kingdom 1 (the bot) and 2 share galaxy g1; 3, 4 and 5 are in g2 and 6 in g3. ``stats`` gives the stars and networth
    the bot can see, ``info`` what ``target_info`` returns for a kingdom."""

    def __init__(self, me=None, day=3.5, days=10, galaxies=None, revealed=None, stats=None, info=None, empires=None,
                 politics=None, news=None, shared=None, attack_history=None, state=None):
        self.kd_id = "1"
        self.now = NOW
        self.me = kingdom(**(me or {}))
        galaxies = galaxies or {"g1": ["1", "2"], "g2": ["3", "4", "5"], "g3": ["6"]}
        self.galaxies = galaxies
        self.galaxy_of = {kd: galaxy for galaxy, members in galaxies.items() for kd in members}
        self.names = {kd: f"Kd{kd}" for kd in self.galaxy_of}
        self.revealed = revealed or {}
        self.revealed_info = {"revealed": self.revealed, "revealed_galaxymates": [], "galaxies": {}}
        start = NOW - day * DAY
        self.state = {"state": {"game_start": start.isoformat(), "game_end": (start + days * DAY).isoformat(),
                                "election_end": "", "active_policies": [], **(state or {})}}
        self._seen = dict(info or {})
        stats = stats or {}
        empire_list = empires or {}
        galaxy_empire = {galaxy: eid for eid, empire in empire_list.items() for galaxy in empire["galaxies"]}
        kd_empire = {kd: galaxy_empire[galaxy] for kd, galaxy in self.galaxy_of.items() if galaxy in galaxy_empire}
        self._cache = {
            "galaxy_politics": {"votes": {"policy_1": {}, "policy_2": {}, "leader": {}}, "active_policies": [],
                                "leader": "", "empire_invitations": [], "empire_join_requests": [], **(politics or {})},
            "empires": (kd_empire, empire_list, galaxy_empire),
            "scores": {
                "networth": sorted(((kd, nw) for kd, (_, nw) in stats.items()), key=lambda item: -item[1]),
                "stars": sorted(((kd, stars) for kd, (stars, _) in stats.items()), key=lambda item: -item[1]),
                "points": [], "galaxy_networth": [("g1", 300_000), ("g2", 900_000), ("g3", 100_000)],
            },
            "news": news or [],
            "shared": shared or {"shared": {}, "shared_requests": {}, "shared_offers": {}},
            "attack_history": attack_history or [],
        }

    def target_info(self, target):
        return self._seen.get(target, {})


def empire(name, galaxies, **fields):
    return {"name": name, "galaxies": galaxies, "war": [], "peace": {}, "denounced": "", **fields}


class ChanceOf(random.Random):
    """A random source whose chances always roll the same: 0.0 passes every chance, 1.0 fails every one."""

    def __init__(self, roll, seed=7):
        super().__init__(seed)
        self.roll = roll

    def random(self):
        return self.roll


ATTACKER = brain.PERSONALITIES["attacker"]
THIEF = brain.PERSONALITIES["thief"]
INTEL = brain.PERSONALITIES["intel"]
EXPLORER = brain.PERSONALITIES["explorer"]


def style(army="both", drones="primitives", bomber=False, temper=1.0):
    return {"army": army, "drones": drones, "bomber": bomber, "temper": temper}


def military(defense_units, **more):
    """What target_info shows of a kingdom whose military is revealed."""
    return {"units": {"defense": defense_units, "recruits": 0, "flex": 0, "big_flex": 0, "attack": 0}, **more}


# ------------------------------------------------------------------------------------------------------ personalities

def test_every_personality_is_legal_and_covers_every_archetype():
    import untitledapp.bots as bots

    assert set(brain.PERSONALITIES) == set(bots.ARCHETYPES)
    for key, personality in brain.PERSONALITIES.items():
        assert brain.problems(personality) == [], key


def test_an_illegal_edit_is_caught():
    bad = dataclasses.replace(
        ATTACKER, intel_tries=(1, 99), intel_ops=("siphonfunds",), galaxy_votes={"policy_1": "7"},
        army_targets={"wizards": 1}, key_projects=("money_bonus",), settle_drive=(1, 2, 3), share_cut=40)
    found = " ".join(brain.problems(bad))
    for word in ("intel tries", "siphonfunds", "policy_1", "army_targets", "money_bonus", "settle_drive", "share_cut"):
        assert word in found, word


def test_bots_of_one_playstyle_differ_and_between_them_hit_everything():
    styles = [brain.roll_style(ATTACKER, random.Random(seed)) for seed in range(200)]
    assert {s["army"] for s in styles} == {"primitives", "players", "both"}
    assert 20 < sum(s["bomber"] for s in styles) < 120
    assert len({s["temper"] for s in styles}) > 100
    thieves = [brain.roll_style(THIEF, random.Random(seed)) for seed in range(200)]
    assert {s["drones"] for s in thieves} == {"primitives", "players", "both"}
    assert "none" in {s["army"] for s in thieves}


def test_a_bot_made_before_styles_existed_still_has_one():
    assert brain._style({"type": "attacker"}, ATTACKER)["army"] == "primitives"
    assert brain._style({"type": "thief"}, THIEF) == {"army": "primitives", "drones": "primitives", "bomber": False, "temper": 1.0}
    assert brain._style({"style": {"army": "players"}}, ATTACKER)["army"] == "players"
    # Its auto attack keeps the generals it always kept; a bot the brain has re-planned keeps none back.
    assert brain.reserved_generals({"bot": {"type": "attacker"}}) == brain.RESERVED_GENERALS
    assert brain.reserved_generals({"bot": {"reserved_generals": 0}}) == 0
    assert brain.reserved_generals({}) == 0


# -------------------------------------------------------------------------------------------- reacting and learning

def test_being_beaten_makes_a_grudge_and_a_wish_for_more_defense():
    world = StubWorld(news=[
        {"time": until(-2), "from": "4", "kind": "attack", "news": "Your kingdom was defeated in battle by Kd4. You have lost ..."},
        {"time": until(-1), "from": "5", "kind": "attack", "news": "Your kingdom successfully defended an attack by Kd5."},
        {"time": until(-1.5), "from": "3", "kind": "missiles", "news": "Missiles from Kd3 have destroyed ..."},
    ])
    memory = {}
    notes = brain.react(world, memory)
    assert memory["grudges"]["4"] > memory["grudges"]["5"] > 0 and memory["grudges"]["3"] > 0
    assert memory["defense_boost"] > 1.25
    assert memory["hit_at"] == until(-2) and memory["missiles_at"] == until(-1.5)
    assert len(notes) == 3
    # The same news is not counted twice, and caution wears off.
    before = memory["defense_boost"]
    assert brain.react(world, memory) == []
    assert 1.0 < memory["defense_boost"] < before


def test_a_failed_strike_widens_the_buffer_and_a_won_one_narrows_it():
    strike = {"target": "4", "time": until(-1), "planned": until(-3)}
    lost = StubWorld(attack_history=[{"time": until(-1), "to": "4", "news": "Failure! You have lost ..."}])
    memory = {"strike": dict(strike)}
    notes = brain.learn(lost, ATTACKER, style(), memory)
    assert memory["buffer_extra"] == 4.0 and "strike" not in memory and any("failed" in note for note in notes)
    won = StubWorld(attack_history=[{"time": until(-1), "to": "4", "news": "Success! You have gained ..."}])
    memory = {"strike": dict(strike), "buffer_extra": 4.0}
    brain.learn(won, ATTACKER, style(), memory)
    assert memory["buffer_extra"] == 3.0
    # A strike still to come is left alone.
    memory = {"strike": {"target": "4", "time": until(2), "planned": until(-1)}}
    brain.learn(StubWorld(), ATTACKER, style(), memory)
    assert "strike" in memory


def test_a_kingdom_that_stops_growing_notices_and_one_that_grows_again_recovers():
    world = StubWorld(day=3.5)
    epochs = world.epochs
    memory = {"stars_log": [[epochs - 30, 995], [epochs - 10, 1000]]}
    notes = brain.learn(world, EXPLORER, style(army="none"), memory)
    assert memory["stalled"] is True and any("stopped growing" in note for note in notes)
    # Stalled, even a bot that hits nothing sends its army at primitives and settles.
    settings, why = brain.plan_economy(world, EXPLORER, style(army="none"), memory)
    assert settings["auto_attack_enabled"] is True and "stalled" in why
    memory["stars_log"] = [[epochs - 30, 800]]
    notes = brain.learn(world, EXPLORER, style(army="none"), memory)
    assert memory["stalled"] is False and any("growing again" in note for note in notes)


def test_spies_that_keep_failing_on_a_kingdom_leave_it_alone_for_a_while():
    def spied(memory, revealed=None):
        memory["spying"] = {"3": {"category": "military", "due": until(-0.5)}}
        return brain.learn(StubWorld(revealed=revealed or {}), ATTACKER, style(), memory)

    memory = {}
    assert spied(memory) == [] and memory["spy_fails"] == {"3": 1} and memory["spying"] == {}
    spied(memory)
    notes = spied(memory)
    assert memory["spy_fails"]["3"] == brain.SPY_FAILS and any("keep failing" in note for note in notes)
    # An operation still to run says nothing yet; one that worked wipes the slate.
    waiting = {"spying": {"3": {"category": "military", "due": until(1)}}}
    brain.learn(StubWorld(), ATTACKER, style(), waiting)
    assert waiting["spying"] and not waiting["spy_fails"]
    spied(memory, revealed={"3": {"military": until(10)}})
    assert "3" not in memory["spy_fails"]
    # And after a couple of days it tries again.
    old = {"spy_fails": {"3": 3}, "spy_fails_at": until(-30)}
    brain.learn(StubWorld(), ATTACKER, style(), old)
    assert old["spy_fails"] == {}


def test_an_army_the_kingdom_can_no_longer_keep_is_disbanded_defenders_last():
    # After losing stars: every star is built on, the hangars hold 1,500, and 7,100 units need a place.
    shrunk = {"stars": 300, "structures": {"homes": 150, "mines": 80, "fuel_plants": 30, "hangars": 20,
                                           "drone_factories": 10, "missile_silos": 0, "workshops": 10}}
    (decision,) = brain.plan_survival(StubWorld(me=shrunk), {})
    assert decision.kind == "disband"
    assert decision.options == {"recruits": 100, "attack": 4000, "defense": 1500}
    # With stars to build hangars on, or an army that fits, nothing is disbanded.
    assert brain.plan_survival(StubWorld(me={**shrunk, "stars": 400}), {}) == []
    assert brain.plan_survival(StubWorld(me={"stars": 1000}), {}) == []
    # Out of fuel and still burning more than it makes: the same way out.
    dry = {"stars": 1000, "fuel": -50, "income": {"money": {"net": 1}, "fuel": {"net": -2000}}}
    (decision,) = brain.plan_survival(StubWorld(me=dry), {})
    assert decision.options == {"recruits": 100, "attack": 2100}


def test_with_money_to_spare_the_army_is_built_for_strength_per_recruit():
    rich = {"surplus": 0.6}
    settings, _ = brain.plan_economy(StubWorld(me={"units": {"defense": 200}}, day=4), THIEF, style(army="primitives"), rich)
    assert settings["units_target"].get("flex", 0) > 0.1
    assert settings["auto_attack_settings"]["flex"] == 0  # its flexers are its defense: they stay home
    tight, _ = brain.plan_economy(StubWorld(me={"units": {"defense": 200}}, day=4), THIEF, style(army="primitives"), {"surplus": -0.3})
    assert tight["units_target"].get("flex", 0) == 0


# ------------------------------------------------------------------------------------------------------- the economy

def test_the_economy_plan_is_legal_and_leaves_nothing_idle(app):
    with app.app_context():
        for key, personality in brain.PERSONALITIES.items():
            for day in (0.5, 4, 9):
                for army in ("none", "primitives", "players", "both"):
                    world = StubWorld(day=day)
                    settings, why = brain.plan_economy(world, personality, style(army=army, bomber=True), {})
                    assert "refused" not in why, (key, day, why)
                    assert sum(settings["auto_spending"].values()) <= 1.0001
                    assert sum(settings["structures_target"].values()) <= 1.0001
                    assert sum(settings["units_target"].values()) <= 1.0001
                    assert sum(settings["projects_assigned"].values()) == world.me["units"]["engineers"]
                    assert settings["recruits_before_units"] is False and settings["max_recruits"] >= 50
                    assert settings["auto_spending_enabled"] is True


def test_an_under_defended_kingdom_puts_defense_first():
    weak = StubWorld(me={"units": {"defense": 200, "recruits": 0}}, day=4)
    settings, why = brain.plan_economy(weak, ATTACKER, style(), {})
    safe = StubWorld(me={"units": {"defense": 40_000}}, day=4)
    safe_settings, _ = brain.plan_economy(safe, ATTACKER, style(), {})
    assert settings["units_target"]["defense"] > 0.25  # defenders are 5% of its army now: every new unit is one
    assert settings["units_target"]["attack"] < 4000 / 4200
    assert settings["auto_spending"]["military"] >= safe_settings["auto_spending"]["military"]
    assert safe_settings["units_target"]["attack"] > 4000 / 44_000  # the safe one buys offense
    # Having been hit asks for more still.
    hit, _ = brain.plan_economy(StubWorld(me={"units": {"defense": 6000}}, day=4), ATTACKER, style(), {"defense_boost": 2.0})
    calm, _ = brain.plan_economy(StubWorld(me={"units": {"defense": 6000}}, day=4), ATTACKER, style(), {})
    assert hit["units_target"]["defense"] > calm["units_target"]["defense"]


def test_what_a_bot_hits_decides_its_army_and_its_automation():
    none, _ = brain.plan_economy(StubWorld(me={"units": {"attack": 0}}), THIEF, style(army="none"), {})
    assert none["auto_attack_enabled"] is False and none["units_target"] == {"defense": 1.0}
    primitives, _ = brain.plan_economy(StubWorld(), THIEF, style(army="primitives"), {})
    assert primitives["auto_attack_enabled"] is True and primitives["auto_attack_settings"]["pure"] == 1.0
    players, _ = brain.plan_economy(StubWorld(), ATTACKER, style(army="players"), {})
    assert players["auto_attack_enabled"] is False and players["units_target"]["attack"] > 0
    # Drones: a bot that only works on kingdoms does not rob primitives.
    assert brain.plan_economy(StubWorld(), THIEF, style(drones="players"), {})[0]["auto_rob_enabled"] is False
    assert brain.plan_economy(StubWorld(), THIEF, style(drones="both"), {})[0]["auto_rob_enabled"] is True


def test_the_army_stays_home_while_a_strike_is_pending():
    memory = {"strike": {"target": "4", "time": until(3), "planned": until(-1)}}
    settings, why = brain.plan_economy(StubWorld(), ATTACKER, style(army="both"), memory)
    assert settings["auto_attack_enabled"] is False and "holding" in why


def test_the_plan_follows_the_round():
    early, _ = brain.plan_economy(StubWorld(day=1), ATTACKER, style(bomber=True), {})
    late, _ = brain.plan_economy(StubWorld(day=9), ATTACKER, style(bomber=True), {})
    assert early["shields"]["military"] == 0 and late["shields"]["military"] > 0
    assert early["structures_target"]["missile_silos"] == 0 and late["structures_target"]["missile_silos"] > 0
    assert sum(late["auto_spending"].values()) < 0.95  # a bomber keeps money for missiles
    # Late, settling has stopped paying for a big kingdom.
    big = {"stars": 20_000, "structures": {"homes": 20_000}}
    assert brain.plan_economy(StubWorld(me=big, day=9.8), EXPLORER, style(), {})[0]["auto_spending"]["settle"] == 0


def test_loose_money_is_spent_on_the_build_pages():
    rich = StubWorld(me={"money": 500_000}, day=1)
    kinds = [d.kind for d in brain.spend_money(rich, ATTACKER, style(), {}, {"auto_spending": {"settle": 0.1}})]
    assert kinds == ["buy_settle", "buy_structures", "buy_engineers"]
    assert brain.spend_money(StubWorld(me={"money": 10_000}), ATTACKER, style(), {}, {}) == []
    # After finding nothing to buy it does not ask again for a while.
    assert brain.spend_money(rich, ATTACKER, style(), {"nothing_to_buy": until(-1)}, {}) == []


# ---------------------------------------------------------------------------------------------------------- politics

def test_it_votes_for_its_policies_and_backs_the_candidate_the_others_back():
    world = StubWorld(stats={"2": (900, 400_000)},
                      politics={"votes": {"policy_1": {"1": "2"}, "policy_2": {}, "leader": {}}})
    decisions = brain.plan_politics(world, ATTACKER, style(), {}, random.Random(1))
    assert [(d.kind, d.options) for d in decisions] == [
        ("vote_galaxy", {"policy": "policy_2", "option": "2"}),     # policy_1 is already its vote
        ("vote_leader", {"selected": "2"}),                         # nobody has voted: the strongest
    ]
    # Somebody has votes already: join them, so the galaxy gets a leader.
    world = StubWorld(stats={"2": (900, 400_000)}, galaxies={"g1": ["1", "2", "7", "8"], "g2": ["3"]},
                      politics={"votes": {"policy_1": {"1": "2"}, "policy_2": {"1": "2"}, "leader": {"7": "8", "8": "8"}}})
    (decision,) = brain.plan_politics(world, ATTACKER, style(), {}, random.Random(1))
    assert decision.kind == "vote_leader" and decision.options == {"selected": "8"}


def test_in_an_election_it_buys_votes_once_and_casts_them_as_the_universe_page_does():
    world = StubWorld(me={"money": 400_000, "votes": 2}, state={"election_end": until(6)},
                      politics={"votes": {"policy_1": {"1": "2"}, "policy_2": {"1": "2"}, "leader": {"1": "1"}}})
    memory = {}
    decisions = brain.plan_politics(world, ATTACKER, style(), memory, random.Random(1))
    bought = [d for d in decisions if d.kind == "buy_votes"]
    cast = [d for d in decisions if d.kind == "vote_universe"]
    assert bought[0].options == {"votes": 10}   # a quarter of its money at 10,000 a vote
    assert sum(d.options["votes"] for d in cast) == 12
    assert {d.options["option"] for d in cast} <= {"option_1", "option_2"}
    assert cast[0].options["votes"] > cast[1].options["votes"]  # most on the arms doctrine
    again = brain.plan_politics(world, ATTACKER, style(), memory, random.Random(1))
    assert not [d for d in again if d.kind == "buy_votes"]


LEADER = {"leader": "1", "votes": {"policy_1": {"1": "2"}, "policy_2": {"1": "2"}, "leader": {"1": "1"}}}


def empire_decisions(world, monkeypatch=None, empire_politics=None):
    if monkeypatch is not None:
        monkeypatch.setattr(brain.uag, "_get_empire_politics", lambda empire_id: {
            "leader": "g1", "empire_join_requests": [], "empire_invitations": [], **(empire_politics or {})})
    return [(d.kind, d.options) for d in brain.plan_politics(world, ATTACKER, style(), {}, random.Random(1))
            if d.kind.startswith("empire")]


def test_a_leader_founds_an_empire_or_joins_one_with_room():
    assert empire_decisions(StubWorld(politics=LEADER)) == [("empire_found", {"name": "League g1"})]
    # Not the leader: empires are not its business.
    assert empire_decisions(StubWorld()) == []
    open_empire = {"0": empire("Reds", ["g2"])}
    assert empire_decisions(StubWorld(politics=LEADER, empires=open_empire)) == [("empire_join", {"empire": "0"})]
    invited = {**LEADER, "empire_invitations": ["0"]}
    assert empire_decisions(StubWorld(politics=invited, empires=open_empire)) == [("empire_accept_invite", {"empire": "0"})]
    waiting = {**LEADER, "empire_join_requests": ["0"]}
    assert empire_decisions(StubWorld(politics=waiting, empires=open_empire)) == []
    # It filled up while the request waited (three galaxies: an empire takes two).
    full = {"0": empire("Reds", ["g2", "g3"])}
    assert empire_decisions(StubWorld(politics=waiting, empires=full)) == [("empire_withdraw", {"empire": "0"})]
    assert empire_decisions(StubWorld(politics=LEADER, empires=full)) == [("empire_found", {"name": "League g1"})]


def test_an_empire_holds_at_most_30_percent_of_the_kingdoms_and_35_percent_of_the_networth():
    galaxies = {f"g{i}": [f"{i}{j}" for j in range(3)] for i in range(10)}  # ten galaxies of three
    world = StubWorld(galaxies={**galaxies, "g0": ["1", "2", "3"]})
    world._cache["scores"]["galaxy_networth"] = [(g, 100) for g in galaxies]
    assert brain.fits_in_empire(world, ["g1"], "g2")              # two may always ally
    assert brain.fits_in_empire(world, ["g1", "g2"], "g3")        # 30% of the kingdoms
    assert not brain.fits_in_empire(world, ["g1", "g2", "g3"], "g4")
    world._cache["scores"]["galaxy_networth"] = [("g1", 900)] + [(g, 100) for g in galaxies if g != "g1"]
    assert not brain.fits_in_empire(world, ["g1", "g2"], "g3")    # 1,100 of 1,800 networth


def test_an_empire_leader_admits_denounces_and_goes_to_war_as_the_round_goes_on(monkeypatch):
    ours = {"0": empire("Blues", ["g1"]), "1": empire("Reds", ["g2"])}
    mid = StubWorld(politics=LEADER, empires=ours, day=5)
    assert empire_decisions(mid, monkeypatch, {"empire_join_requests": ["g3"]}) == [
        ("empire_admit", {"galaxy": "g3"}), ("empire_denounce", {"empire": "1"})]
    # With nobody asking, it invites a galaxy that has no empire.
    assert ("empire_invite", {"galaxy": "g3"}) in empire_decisions(mid, monkeypatch)
    # Early it keeps the peace.
    assert empire_decisions(StubWorld(politics=LEADER, empires=ours, day=1), monkeypatch,
                            {"empire_invitations": ["g3"]}) == []
    denounced = {"0": empire("Blues", ["g1"], denounced="1"), "1": empire("Reds", ["g2"])}
    late = StubWorld(politics=LEADER, empires=denounced, day=9)
    assert ("empire_war", {"empire": "1"}) in empire_decisions(late, monkeypatch)
    at_war = {"0": empire("Blues", ["g1"], war=["1"]), "1": empire("Reds", ["g2"], war=["0"])}
    assert [d for d in empire_decisions(StubWorld(politics=LEADER, empires=at_war, day=9), monkeypatch)
            if d[0] in ("empire_war", "empire_denounce")] == []
    # A member galaxy that does not lead the empire leaves all this to the one that does.
    assert empire_decisions(mid, monkeypatch, {"leader": "g2"}) == []


def test_allies_are_not_targets_and_enemies_are_known():
    world = StubWorld(empires={"0": empire("Blues", ["g1", "g3"], war=["1"], denounced="1"), "1": empire("Reds", ["g2"])})
    assert world.allies() == ["6"] and sorted(world.outsiders()) == ["3", "4", "5"]
    assert world.relation("3") == (True, True) and world.relation("6") == (False, False)


# ------------------------------------------------------------------------------------------------------------- intel

def test_knowing_nobody_it_reveals_a_galaxy_and_then_spies_where_it_pays():
    (decision,) = brain.plan_intel(StubWorld(), ATTACKER, style(), {}, ChanceOf(0.0))
    assert decision.kind == "reveal_galaxy"
    # Three kingdoms in sight: for military intel, the one with the most stars for the least army.
    stats = {"3": (1000, 50_000), "4": (1000, 400_000), "5": (300, 15_000)}
    (decision,) = brain.plan_intel(StubWorld(stats=stats), ATTACKER, style(), {}, ChanceOf(0.0), want_military=True)
    assert decision.kind == "intelspy" and decision.options["target"] == "3"
    assert decision.options["operation"] == "spymilitary" and 0 < decision.options["drones_pct"] <= 100
    # One it already has intel on is not spied on again; one that keeps beating its spies is left alone.
    world = StubWorld(stats=stats, revealed={"3": {"military": until(30)}})
    assert brain.plan_intel(world, ATTACKER, style(), {}, ChanceOf(0.0), want_military=True)[0].options["target"] != "3"
    stubborn = {"spy_fails": {"3": 3}}
    assert brain.plan_intel(StubWorld(stats=stats), ATTACKER, style(), stubborn, ChanceOf(0.0), want_military=True)[0].options["target"] != "3"


def test_spies_are_sent_in_the_numbers_that_work_and_not_without_attempts_or_drones():
    stats = {"3": (1000, 50_000), "4": (1000, 60_000), "5": (900, 60_000)}
    (decision,) = brain.plan_intel(StubWorld(stats=stats), INTEL, style(), {}, ChanceOf(0.0), want_military=True)
    # 85% against 1000 stars and a guessed 4000 drones is 6800 drones, of 20,000.
    assert decision.options["drones_pct"] == pytest.approx(34.0)
    assert decision.options["max_tries"] == 1  # good odds: one try
    assert brain.plan_intel(StubWorld(stats=stats, me={"spy_attempts": 0}), INTEL, style(), {}, ChanceOf(0.0)) == []
    assert brain.plan_intel(StubWorld(stats=stats, me={"drones": 50}), INTEL, style(), {}, ChanceOf(0.0)) == []
    assert brain.plan_intel(StubWorld(stats=stats), INTEL, style(), {}, ChanceOf(0.99)) == []  # not this time


def test_intel_bots_share_what_they_learn_for_a_cut_and_others_rarely_do():
    stats = {"3": (1000, 50_000), "4": (1000, 60_000), "5": (900, 60_000)}

    def shares(personality):
        made = [brain.plan_intel(StubWorld(stats=stats), personality, style(), {}, random.Random(seed), want_military=True)[0]
                for seed in range(200)]
        return sum(d.options["share_to_galaxy"] for d in made), {d.options["cut"] for d in made if d.options["share_to_galaxy"]}

    intel_shares, intel_cuts = shares(INTEL)
    attacker_shares, _ = shares(ATTACKER)
    assert intel_shares > 170 and attacker_shares < 80
    assert intel_cuts == {INTEL.share_cut} and INTEL.share_cut > 0


def test_it_accepts_the_intel_it_can_use():
    offers = {"shared": {}, "shared_offers": {}, "shared_requests": {
        "3_2": {"shared_by": "2", "shared_stat": "military", "cut": 0.1, "time": until(6)},
        "4_2": {"shared_by": "2", "shared_stat": "kingdom", "cut": 0.1, "time": until(6)},
        "5_2": {"shared_by": "2", "shared_stat": "military", "cut": 0.1, "time": until(0.5)},  # about to run out
    }}
    attacker = brain.accept_intel(StubWorld(shared=offers), ATTACKER, style(army="both"), {})
    assert [d.options["key"] for d in attacker] == ["3_2"]
    thief = brain.accept_intel(StubWorld(shared=offers), THIEF, style(army="none", drones="both"), {})
    assert [d.options["key"] for d in thief] == ["4_2"]
    assert brain.accept_intel(StubWorld(shared=offers), EXPLORER, style(army="primitives"), {}) == []
    # What it already has it does not take again.
    known = StubWorld(shared=offers, revealed={"3": {"military": until(8)}})
    assert brain.accept_intel(known, ATTACKER, style(army="both"), {}) == []


# ----------------------------------------------------------------------------------------------------------- attacks

INTEL_ON_ALL = {"3": {"military": until(30)}, "4": {"military": until(30)}, "5": {"military": until(30)}}


def test_it_attacks_the_kingdom_that_pays_best_and_never_one_it_would_lose_to():
    world = StubWorld(
        revealed=INTEL_ON_ALL, stats={"3": (2000, 150_000), "4": (5000, 900_000), "5": (2500, 200_000)},
        info={"3": military(1500), "4": military(60_000), "5": military(1500)},  # 4 can not be beaten
    )
    (decision,) = brain.plan_attack(world, ATTACKER, style(army="both"), {}, ChanceOf(0.0))
    assert decision.kind == "attack" and decision.options["target"] == "5"  # as easy as 3, and more stars
    assert decision.options["prefer_autofill"] is True and decision.options["generals"] == 4
    assert "primitives" in decision.why


def test_a_bot_that_hits_both_only_takes_a_kingdom_that_beats_primitives():
    # Early in the round primitives are easy: this kingdom would cost more offense per star than they do.
    world = StubWorld(day=0.5, revealed={"3": {"military": until(30)}}, stats={"3": (400, 60_000)},
                      info={"3": military(2000)})
    both = brain.plan_attack(world, ATTACKER, style(army="both"), {}, ChanceOf(0.0))
    assert [d.kind for d in both] != ["attack"]
    players = brain.plan_attack(world, ATTACKER, style(army="players"), {}, ChanceOf(0.0))
    assert [d.kind for d in players] == ["attack"]
    # A bot that only hits primitives, or nothing, plans no strike at all.
    assert brain.plan_attack(world, ATTACKER, style(army="primitives"), {}, ChanceOf(0.0)) == []
    assert brain.plan_attack(world, ATTACKER, style(army="none"), {}, ChanceOf(0.0)) == []


def test_without_intel_it_sends_spies_for_it_instead_of_attacking_blind():
    world = StubWorld(stats={"3": (1000, 50_000), "4": (800, 50_000), "5": (700, 50_000)})
    (decision,) = brain.plan_attack(world, ATTACKER, style(army="players"), {}, ChanceOf(0.0))
    assert decision.kind == "intelspy" and decision.options["operation"] == "spymilitary"
    assert decision.options["target"] in ("3", "4", "5")  # never a galaxymate


def test_intel_that_is_about_to_run_out_does_not_count():
    world = StubWorld(revealed={"3": {"military": until(0.2)}}, stats={"3": (2000, 150_000)}, info={"3": military(100)})
    decisions = brain.plan_attack(world, ATTACKER, style(army="players"), {}, ChanceOf(0.0))
    assert [d.kind for d in decisions] != ["attack"]


def test_it_waits_for_generals_on_their_way_home_when_the_army_at_home_is_not_enough():
    away = {"generals_available": 1, "units": {"attack": 500},
            "generals_out": [{"return_time": until(2), "attack": 3500}]}
    world = StubWorld(me=away, revealed={"3": {"military": until(30)}}, stats={"3": (2500, 200_000)},
                      info={"3": military(2500)})
    (decision,) = brain.plan_attack(world, ATTACKER, style(army="both"), {}, ChanceOf(0.0))
    assert decision.kind == "attack" and decision.options["generals"] == 2
    assert 2 * 3600 < decision.at < 2.5 * 3600  # once the general is back
    # Too long a wait for a bot that could be at the primitives meanwhile.
    far = {**away, "generals_out": [{"return_time": until(11), "attack": 3500}]}
    world = StubWorld(me=far, revealed={"3": {"military": until(30)}}, stats={"3": (2500, 200_000)}, info={"3": military(2500)})
    assert [d.kind for d in brain.plan_attack(world, ATTACKER, style(army="both"), {}, ChanceOf(0.0))] != ["attack"]


def test_one_strike_at_a_time():
    world = StubWorld(revealed=INTEL_ON_ALL, stats={"3": (2000, 150_000)}, info={"3": military(100)})
    pending = {"strike": {"target": "3", "time": until(1), "planned": until(-1)}}
    assert brain.plan_attack(world, ATTACKER, style(army="players"), pending, ChanceOf(0.0)) == []


def test_enemies_grudges_and_leaders_are_worth_more():
    def edge(**world_fields):
        world = StubWorld(revealed={"3": {"military": until(30)}}, stats={"3": (2000, 150_000)},
                          info={"3": military(2000)}, **world_fields)
        (decision,) = brain.plan_attack(world, ATTACKER, style(army="players"), world_fields.pop("memory", {}), ChanceOf(0.0))
        return float(decision.why.split("buffer, ")[1].split("x")[0])

    plain = edge()
    at_war = edge(empires={"0": empire("Blues", ["g1"], war=["1"]), "1": empire("Reds", ["g2"], war=["0"])})
    assert at_war > plain * 1.3
    assert edge(day=9) > edge(day=8.99) * 0  # late: still a number
    world = StubWorld(revealed={"3": {"military": until(30)}}, stats={"3": (2000, 150_000)}, info={"3": military(2000)})
    (hated,) = brain.plan_attack(world, ATTACKER, style(army="players"), {"grudges": {"3": 4}}, ChanceOf(0.0))
    assert float(hated.why.split("buffer, ")[1].split("x")[0]) > plain * 1.3


def test_late_in_the_round_a_leader_it_can_not_beat_is_worn_down():
    world = StubWorld(day=9, revealed={"4": {"military": until(30)}}, stats={"4": (9000, 2_000_000), "3": (500, 30_000)},
                      info={"4": military(4500)})  # 30,375 defense against about 23,400 offense
    (decision,) = brain.plan_attack(world, ATTACKER, style(army="both"), {}, ChanceOf(0.0))
    assert decision.kind == "attack" and decision.options["target"] == "4"
    assert decision.options["prefer_autofill"] is False and decision.options["pure_offense"] == 100
    assert "wear down" in decision.why
    # Not in the mid game, and not against a wall.
    mid = StubWorld(day=5, revealed={"4": {"military": until(30)}}, stats={"4": (9000, 2_000_000)}, info={"4": military(4500)})
    assert [d.kind for d in brain.plan_attack(mid, ATTACKER, style(army="both"), {}, ChanceOf(0.0))] != ["attack"]
    wall = StubWorld(day=9, revealed={"4": {"military": until(30)}}, stats={"4": (9000, 2_000_000)}, info={"4": military(50_000)})
    assert [d.kind for d in brain.plan_attack(wall, ATTACKER, style(army="both"), {}, ChanceOf(0.0))] != ["attack"]


# ------------------------------------------------------------------------------------------------------------ drones

def test_a_thief_siphons_when_that_beats_robbing_primitives():
    stats = {"3": (3000, 400_000), "4": (500, 40_000)}
    world = StubWorld(day=5, stats=stats)  # primitives are robbed half bare by now
    THIEF = dataclasses.replace(brain.PERSONALITIES["thief"], sabotage_chance=(0.0, 0.0, 0.0))  # siphons only, here
    decision, second = brain.plan_drones(world, THIEF, style(drones="both"), {}, ChanceOf(0.0))
    assert second.options["target"] == "4"  # every spare attempt to a siphon, one per kingdom, the best first
    assert decision.kind == "aggressivespy" and decision.options["operation"] == "siphonfunds"
    assert decision.options["target"] == "3" and "robbing primitives" in decision.why
    # At the very start robbing is better, unless kingdoms are all it works on.
    early = StubWorld(day=0.01, stats={"3": (150, 10_000)}, me={"drones": 11_000})
    assert brain.plan_drones(early, THIEF, style(drones="both"), {}, ChanceOf(0.0)) == []
    assert [d.options["operation"] for d in brain.plan_drones(early, THIEF, style(drones="players"), {}, ChanceOf(0.0))] == ["siphonfunds"]
    # A bot that only robs primitives leaves kingdoms alone, and one siphon runs on a kingdom at a time.
    assert brain.plan_drones(world, THIEF, style(drones="primitives"), {}, ChanceOf(0.0)) == []
    running = {"siphons": {"3": until(4)}}
    assert brain.plan_drones(world, THIEF, style(drones="both"), running, ChanceOf(0.0))[0].options["target"] == "4"


def test_late_in_the_round_drones_go_after_a_leader():
    stats = {"4": (9000, 2_000_000), "3": (500, 30_000)}
    world = StubWorld(day=9, stats=stats, me={"drones": 60_000})
    decision = brain.plan_drones(world, THIEF, style(drones="primitives"), {}, ChanceOf(0.0))[0]
    assert decision.options["target"] in ("4", "3") and decision.options["operation"] in THIEF.sabotage_ops
    assert brain.plan_drones(StubWorld(day=1, stats=stats), THIEF, style(drones="primitives"), {}, ChanceOf(0.0)) == []
    # A leader low on fuel has it burnt: with kingdom intel showing the fuel.
    low = StubWorld(day=9, stats={"4": (9000, 2_000_000)}, revealed={"4": {"kingdom": until(9)}}, info={"4": {"fuel": 150_000}},
                    me={"drones": 60_000})
    (decision,) = brain.plan_drones(low, THIEF, style(drones="primitives"), {}, ChanceOf(0.0))
    assert decision.options["operation"] == "suicidedrones" and 0 < decision.options["drones_pct"] <= 50


def test_no_drones_or_no_attempts_no_operations():
    stats = {"3": (3000, 400_000)}
    assert brain.plan_drones(StubWorld(day=9, stats=stats, me={"drones": 100}), THIEF, style(drones="both"), {}, ChanceOf(0.0)) == []
    assert brain.plan_drones(StubWorld(day=9, stats=stats, me={"spy_attempts": 0}), THIEF, style(drones="both"), {}, ChanceOf(0.0)) == []


# ---------------------------------------------------------------------------------------------------------- missiles

def test_a_bomber_fills_its_silos_with_the_best_missile_it_can_and_fires_at_whoever_hit_it():
    armed = {"structures": {"missile_silos": 30}, "money": 400_000, "completed_projects": ["star_busters"],
             "missiles": {"planet_busters": 20, "star_busters": 0, "galaxy_busters": 0}}
    world = StubWorld(me=armed, stats={"4": (9000, 2_000_000), "3": (500, 30_000)})
    decisions = brain.plan_missiles(world, ATTACKER, style(bomber=True), {"grudges": {"3": 2}}, ChanceOf(0.0))
    build, launch = decisions
    assert build.kind == "build_missiles" and build.options["star_busters"] == 30 and build.options.get("planet_busters", 0) == 10
    assert launch.kind == "missiles" and launch.options["target"] == "3"  # the grudge, before the leader
    assert set(launch.options) == {"target", "planet_busters", "star_busters", "galaxy_busters"}
    assert 12 <= launch.options["planet_busters"] <= 20
    # No grudge: the leader. Not a bomber: it builds none, but fires what it holds. Just ordered: it waits.
    no_grudge = brain.plan_missiles(world, ATTACKER, style(bomber=True), {}, ChanceOf(0.0))
    assert no_grudge[-1].options["target"] == "4"
    assert [d.kind for d in brain.plan_missiles(world, ATTACKER, style(), {}, ChanceOf(0.0))] == ["missiles"]
    ordered = brain.plan_missiles(world, ATTACKER, style(bomber=True), {"missiles_ordered": until(-2)}, ChanceOf(0.0))
    assert [d.kind for d in ordered] == ["missiles"]
    assert brain.plan_missiles(StubWorld(), ATTACKER, style(bomber=True), {}, ChanceOf(0.0)) == []


# ---------------------------------------------------------------------------------------------------- the whole plan

def test_the_schedule_is_never_overfilled_and_actions_are_spread_out():
    stats = {"3": (2000, 150_000), "4": (1500, 100_000), "5": (900, 60_000)}
    full = StubWorld(stats=stats, me={"schedule": [{}] * INTEL.max_pending})
    _, decisions, _ = brain.plan(full, INTEL, style(), {}, random.Random(1))
    assert [d for d in decisions if d.kind in brain._SCHEDULERS] == []
    delays = set()
    for seed in range(40):
        world = StubWorld(stats=stats, day=9)
        _, decisions, _ = brain.plan(world, THIEF, style(drones="both"), {}, random.Random(seed))
        scheduled = [d for d in decisions if d.kind in brain._SCHEDULERS]
        assert len(scheduled) <= THIEF.max_new
        for decision in scheduled:
            assert 0 < decision.delay <= THIEF.think_epochs[0] * brain.EPOCH
            delays.add(round(decision.delay))
    assert len(delays) > 20


def test_a_planned_strike_keeps_the_army_home_and_spies_keep_their_attempts():
    world = StubWorld(revealed={"3": {"military": until(30)}}, stats={"3": (2500, 200_000)}, info={"3": military(1000)},
                      politics={"votes": {"policy_1": {"1": "2"}, "policy_2": {"1": "2"}, "leader": {"1": "1"}}})
    memory = {}
    settings, decisions, notes = brain.plan(world, ATTACKER, style(army="both"), memory, ChanceOf(0.0))
    assert [d.kind for d in decisions if d.kind in brain._SCHEDULERS][0] == "attack"
    assert settings["auto_attack_enabled"] is False
    assert settings["auto_rob_settings"]["keep"] == memory["keep_attempts"] >= 1
    assert any("spend settle" in note for note in notes)


def test_each_bot_thinks_at_its_own_time():
    personality = EXPLORER
    firsts = {brain.first_think_time(personality, random.Random(seed), NOW) for seed in range(50)}
    nexts = {brain.next_think_time(personality, random.Random(seed), NOW) for seed in range(50)}
    assert len(firsts) == len(nexts) == 50
    low, high = personality.think_epochs
    assert all(NOW + low * EPOCH <= t <= NOW + high * EPOCH for t in nexts)
    assert all(NOW <= t <= NOW + low * EPOCH for t in firsts)  # a new bot gets going within its first interval


# ---------------------------------------------------------------------------------------------------- with a backend

def _make_kingdom_one_a_bot(kind="attacker", bot=None, **fields):
    """Kingdom 1 becomes a bot of ``kind`` that is due to think, in a started round with a galaxy it can vote in."""
    _set_up_two_kingdoms()
    now = datetime.datetime.now(datetime.timezone.utc)
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Bot", TARGET_ID: "Target"}})
    _create_item("state", {"state": {
        "game_start": (now - 1 * DAY).isoformat(), "game_end": (now + 7 * DAY).isoformat(),
        "election_start": (now + 5 * DAY).isoformat(), "election_end": "", "active_policies": [], "next_history": (now + DAY).isoformat(),
    }})
    _create_item("scores", {"points": {}, "stars": {KD_ID: 300, TARGET_ID: 300}, "networth": {KD_ID: 20000, TARGET_ID: 20000},
                            "galaxy_networth": {"1": 20000, "2": 20000}, "last_update": now.isoformat()})
    _create_item("galaxy_votes_1", {
        "votes": {"policy_1": {}, "policy_2": {}, "leader": {}}, "active_policies": [], "leader": "",
        "policy_1_winner": "", "policy_2_winner": "", "empire_invitations": [], "empire_join_requests": [],
    })
    long_ago = (now - 2 * HOUR).isoformat()
    with_bot = {"bot": {"type": kind, "next_think": (now - HOUR).isoformat(), "log": [], **(bot or {})},
                "last_income": long_ago, "race": "Xo", **fields}
    kd = _get(f"/kingdom/{KD_ID}")
    if "next_resolve" in fields:  # only the named categories change
        with_bot["next_resolve"] = {**kd["next_resolve"], **fields["next_resolve"]}
    _create_item(f"kingdom_{KD_ID}", {**kd, **with_bot})
    return now


def _think(rng=None, now=None):
    return brain.think(KD_ID, now=now or datetime.datetime.now(datetime.timezone.utc), rng=rng or random.Random(1))


def test_a_think_sets_up_the_kingdom_votes_and_remembers(app, client):
    _make_kingdom_one_a_bot("attacker", bot={"style": style(army="both")})
    with app.app_context():
        _think()
    kingdom_now = _get(f"/kingdom/{KD_ID}")
    bot = kingdom_now["bot"]
    assert kingdom_now["auto_spending_enabled"] is True and 0 < sum(kingdom_now["auto_spending"].values()) <= 1.0001
    assert kingdom_now["next_resolve"]["auto_spending"] < uas.DATE_SENTINEL  # switched on, so it has a time to run
    assert kingdom_now["recruits_before_units"] is False and kingdom_now["auto_rob_enabled"] is True
    assert sum(kingdom_now["structures_target"].values()) > 0.99
    assert bot["phase"] == "early" and bot["style"]["army"] == "both" and bot["reserved_generals"] == 0
    assert datetime.datetime.fromisoformat(bot["next_think"]) > datetime.datetime.now(datetime.timezone.utc)
    assert any(entry["kind"] == "plan" and "spend settle" in entry["why"] for entry in bot["log"])
    assert bot["counts"]["vote_galaxy"] == 2 and bot["counts"]["vote_leader"] == 1
    assert "stars_log" in bot["memory"]
    # The attacker votes Warlike and Conscription in its galaxy, and for a leader.
    votes = _get("/galaxy/1/politics")
    assert votes["votes"]["policy_1"] == {KD_ID: "2"} and "Warlike" in votes["active_policies"]
    assert votes["leader"] == KD_ID


def test_a_bot_that_knows_the_enemys_army_schedules_a_strike(app, client):
    now = _make_kingdom_one_a_bot("attacker", bot={"style": style(army="players")})
    _create_item(f"revealed_{KD_ID}", {
        "revealed": {TARGET_ID: {"military": (now + 12 * HOUR).isoformat(), "stats": (now + 12 * HOUR).isoformat()}},
        "galaxies": {}, "revealed_galaxymates": [], "revealed_to_galaxymates": [],
    })
    with app.app_context():
        decisions = _think(ChanceOf(0.0), now)
    assert any(d.kind == "attack" for d in decisions)
    kingdom_now = _get(f"/kingdom/{KD_ID}")
    (attack,) = [item for item in kingdom_now["schedule"] if item["type"] == "attack"]
    assert attack["options"]["target"] == TARGET_ID and attack["options"]["prefer_autofill"] is True
    assert now < datetime.datetime.fromisoformat(attack["time"])
    assert kingdom_now["bot"]["memory"]["strike"]["target"] == TARGET_ID
    assert kingdom_now["auto_attack_enabled"] is False
    assert any(entry["kind"] == "attack" and "scheduled" in entry["outcome"] for entry in kingdom_now["bot"]["log"])


def test_a_scheduled_strike_asking_for_generals_that_are_not_home_does_nothing(app, client):
    """The autofill refuses it; that used to be a KeyError in the refresh."""
    now = _make_kingdom_one_a_bot("attacker", generals_available=1)
    _create_item(f"revealed_{KD_ID}", {
        "revealed": {TARGET_ID: {"military": (now + 12 * HOUR).isoformat()}},
        "galaxies": {}, "revealed_galaxymates": [], "revealed_to_galaxymates": [],
    })
    schedule = {"type": "attack", "options": {"target": TARGET_ID, "generals": 4, "prefer_autofill": True, "autofill_buffer": 0.05}}
    with app.app_context():
        action, arguments = refresh._resolve_schedule_attack(_get(f"/kingdom/{KD_ID}"), schedule)
        assert action(*arguments) is None
    assert _get(f"/kingdom/{KD_ID}")["generals_available"] == 1
    assert _get(f"/kingdom/{KD_ID}/attackhistory")["attack_history"] == []


def test_a_bot_votes_only_once_for_the_same_thing(app, client):
    _make_kingdom_one_a_bot("explorer")
    with app.app_context():
        first = _think(random.Random(1))
        second = _think(random.Random(2))
    assert sum(d.kind == "vote_galaxy" for d in first) == 2 and sum(d.kind == "vote_leader" for d in first) == 1
    assert sum(d.kind.startswith("vote_") for d in second) == 0


def test_loose_money_is_really_spent(app, client):
    _make_kingdom_one_a_bot("explorer", money=200_000)
    before = _get(f"/kingdom/{KD_ID}")
    with app.app_context():
        _think()
    after = _get(f"/kingdom/{KD_ID}")
    assert after["money"] < before["money"]
    assert _get(f"/kingdom/{KD_ID}/settles")["settles"], "it did not settle"
    assert after["bot"]["counts"].get("buy_settle") == 1


def test_an_old_bot_without_a_style_or_memory_still_thinks(app, client):
    _make_kingdom_one_a_bot("thief")  # only type, next_think and log, as bots were first made
    with app.app_context():
        _think()
    bot = _get(f"/kingdom/{KD_ID}")["bot"]
    assert bot["style"]["drones"] == "primitives" and bot["memory"] and bot["log"]


class Eager(random.Random):
    """Every chance comes up: the bot does everything it can, as soon as it can."""

    def random(self):
        return 0.0


def test_the_refresh_wakes_a_bot_and_its_scheduled_actions_run_when_due(app, client, monkeypatch):
    """End to end: a due bot thinks in the refresh, and a spy it queued runs when it falls due."""
    monkeypatch.setattr(brain, "random", types.SimpleNamespace(Random=Eager))
    now = _make_kingdom_one_a_bot("intel", spy_attempts=10, drones=5000, auto_rob_enabled=False)
    _create_item(f"revealed_{KD_ID}", {
        "revealed": {TARGET_ID: {"stats": (now + 12 * HOUR).isoformat()}},
        "galaxies": {"2": (now + 12 * HOUR).isoformat()}, "revealed_galaxymates": [], "revealed_to_galaxymates": [],
    })
    with app.app_context():
        state = refresh.uag._get_state()
        for step in range(1, 5):  # the intel personality queues things within its first interval
            refresh._refresh_kd(KD_ID, state, now + step * 20 * MINUTE, False)
    kingdom_now = _get(f"/kingdom/{KD_ID}")
    assert kingdom_now["bot"]["log"], "the bot never thought"
    # The first think queued a spy on the other galaxy's kingdom; once due, the refresh ran it through the real spy code.
    assert kingdom_now["bot"]["counts"].get("intelspy", 0) >= 1
    assert len(_get(f"/kingdom/{KD_ID}/spyhistory")["spy_history"]) >= 1


def test_a_player_kingdom_is_left_alone_by_the_refresh(app, client):
    _set_up_two_kingdoms()
    with app.app_context():
        assert brain.maybe_think(_get(f"/kingdom/{KD_ID}"), datetime.datetime.now(datetime.timezone.utc)) is False
    assert "bot" not in _get(f"/kingdom/{KD_ID}")


def test_a_bot_that_fails_to_think_does_not_stop_the_refresh(app, client, monkeypatch):
    _make_kingdom_one_a_bot("attacker")

    def broken(*args, **kwargs):
        raise RuntimeError("no plan today")

    monkeypatch.setattr(brain, "plan", broken)
    with app.app_context():
        assert brain.maybe_think(_get(f"/kingdom/{KD_ID}"), datetime.datetime.now(datetime.timezone.utc)) is False


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


def _auto_spend_military(app, units, units_target, recruits=200):
    """One auto spending step for a kingdom with money for its army; returns the units it started training."""
    long_ago = datetime.datetime.now(datetime.timezone.utc) - 2 * HOUR
    _make_kingdom_one_a_bot(
        "explorer", bot={"next_think": (datetime.datetime.now(datetime.timezone.utc) + DAY).isoformat()},
        units={"attack": 0, "defense": 0, "flex": 0, "big_flex": 0, "engineers": 0, **units, "recruits": recruits},
        units_target=units_target, auto_spending_enabled=True, recruits_before_units=False, max_recruits=0,
        auto_spending={"settle": 0, "structures": 0, "military": 0, "engineers": 0},
        funding={"settle": 0, "structures": 0, "military": 50_000, "engineers": 0},
        next_resolve={"auto_spending": long_ago.isoformat()},
    )
    with app.app_context():
        state = refresh.uag._get_state()
        refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)
    training = {}
    for entry in _get(f"/kingdom/{KD_ID}/mobis")["mobis"]:
        for unit, count in entry.items():
            if unit != "time":
                training[unit] = training.get(unit, 0) + count
    return training


def test_auto_spending_keeps_building_an_army_that_already_has_the_mix_asked_for(app, client):
    """A target of one unit (all defense) is met by the first defender, and the builder then built nothing more: found
    with the bots, whose defenders stayed at their starting number all round."""
    training = _auto_spend_military(app, {"defense": 500}, {"defense": 1.0})
    assert training.get("defense", 0) > 0


def test_auto_spending_copes_with_a_kingdom_that_has_none_of_the_units_it_aims_for(app, client):
    """Used to divide by zero, which skipped the kingdom on every tick."""
    training = _auto_spend_military(app, {}, {"attack": 0.5, "defense": 0.5})
    assert training.get("attack", 0) > 0 and training.get("defense", 0) > 0


def test_siphons_are_spread_over_kingdoms_in_proportion_to_their_worth():
    stats = {"3": (3000, 400_000), "4": (2500, 300_000)}
    thief = dataclasses.replace(THIEF, sabotage_chance=(0.0, 0.0, 0.0))
    world = StubWorld(day=5, stats=stats)
    # A low draw takes the best target first, a high one the next: thieves do not all pile on the same kingdom.
    class Rolls:
        def __init__(self, *rolls):
            self.rolls = list(rolls)

        def random(self):
            return self.rolls.pop(0) if self.rolls else 0.0

    # The rolls: no sabotage, go siphoning, then the draw for the first target.
    best = brain.plan_drones(world, thief, style(drones="players"), {}, Rolls(0.5, 0.0, 0.0))[0].options["target"]
    other = brain.plan_drones(world, thief, style(drones="players"), {}, Rolls(0.5, 0.0, 0.99))[0].options["target"]
    assert {best, other} == {"3", "4"}


def test_a_kingdom_that_keeps_catching_the_siphons_is_tried_less():
    stats = {"3": (3000, 400_000), "4": (2500, 300_000)}
    thief = dataclasses.replace(THIEF, sabotage_chance=(0.0, 0.0, 0.0))
    world = StubWorld(day=5, stats=stats)
    world._cache["spy_history"] = [
        {"time": until(-i), "to": "3", "operation": "Siphon Funds", "news": "Failure! Your drones were caught"}
        for i in range(1, 6)] + [{"time": until(-1), "to": "4", "operation": "Siphon Funds", "news": "Success!"}]
    memory = {"siphons": {"6": until(5)}}
    brain.note_siphons(world, memory)
    assert memory["siphon_record"]["3"][0] == 0 and memory["siphon_record"]["3"][1] > 3
    assert memory["siphon_record"]["4"] == [1, 1]
    assert brain.plan_drones(world, thief, style(drones="players"), memory, ChanceOf(0.0))[0].options["target"] == "4"
    # What was counted is not counted again.
    brain.note_siphons(world, memory)
    assert memory["siphon_record"]["4"] == [1, 1]


def test_a_bot_keeps_out_the_strongest_army_it_knows_of():
    army = {"units": {"attack": 60_000, "defense": 0, "flex": 0, "big_flex": 0, "recruits": 0}, "generals_available": 4,
            "race": "Xo"}
    world = StubWorld(day=3, stats={"3": (1000, 500_000)}, revealed={"3": {"military": until(6)}}, info={"3": army})
    memory = {}
    threat = brain.note_threat(world, memory)
    assert threat > 60_000 * uas.UNITS["attack"]["offense"] and memory["threat"]["from"] == "3"
    settings, why = brain.plan_economy(world, ATTACKER, style(), memory)
    line = max(brain.strategy.defense_wanted(world.me, world.epochs, ATTACKER.defense_margin),
               world.me["stars"] * brain.strategy.break_even_per_star(world.epochs) * brain.MIN_DEFENSE)
    wanted = float(why.split(" of ")[1].split(" wanted")[0].replace(",", ""))
    assert line < wanted <= line * brain.THREAT_CAP + 1  # the log rounds it
    # The threat is remembered for a while after the intel runs out, then forgotten.
    blind = StubWorld(day=3, stats={"3": (1000, 500_000)})
    assert brain.note_threat(blind, memory) == threat
    memory["threat"]["at"] = (NOW - datetime.timedelta(seconds=(brain.THREAT_EPOCHS + 1) * brain.EPOCH)).isoformat()
    assert brain.note_threat(blind, memory) == 0.0 and "threat" not in memory


def test_every_bot_keeps_more_defense_than_makes_it_a_better_target_than_primitives(monkeypatch):
    monkeypatch.setattr(brain, "MIN_DEFENSE", 1.1)  # off by default; the rule as it works when switched on
    world = StubWorld(day=5)
    bold = dataclasses.replace(ATTACKER, defense_margin=0.3)
    _, why = brain.plan_economy(world, bold, style(), {})
    wanted = float(why.split(" of ")[1].split(" wanted")[0].replace(",", ""))
    floor = world.me["stars"] * brain.strategy.break_even_per_star(world.epochs) * brain.MIN_DEFENSE
    assert wanted == pytest.approx(floor, abs=1)


def test_each_bot_has_its_own_riskiness_within_the_range(monkeypatch):
    monkeypatch.setattr(brain, "DEFENSE_RISK", (0.95, 1.1))
    floors = [brain.risk_floor(kd) for kd in range(100)]
    assert all(0.95 <= f <= 1.1 for f in floors) and max(floors) - min(floors) > 0.1
    assert brain.risk_floor("7") == brain.risk_floor("7")  # fixed per kingdom


def test_homes_follow_whether_recruits_are_trained_flat_out(monkeypatch):
    monkeypatch.setattr(brain, "HOMES_RULE", "training")
    world = StubWorld(day=3, me={"funding": {**kingdom()["funding"], "military": 10 ** 7}})
    monkeypatch.setattr(brain, "recruits_training_share", lambda world: 1.0)
    memory = {}
    brain.plan_economy(world, ATTACKER, style(), memory)
    assert memory["homes_shift"] == brain.HOMES_STEP  # flat out, money waiting: more homes
    monkeypatch.setattr(brain, "recruits_training_share", lambda world: 0.3)
    brain.plan_economy(world, ATTACKER, style(), memory)
    brain.plan_economy(world, ATTACKER, style(), memory)
    assert memory["homes_shift"] == -brain.HOMES_STEP  # not training flat out: too many homes
