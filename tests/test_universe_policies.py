"""Universe policies (universepolicies.py): the ballots, the count, the effects, the routes and the elections."""
import datetime
import json
import random

import pytest

import untitledapp.admin as admin
import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.refresh as refresh
import untitledapp.shared as uas
import untitledapp.universepolicies as up
from tests import kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom

FIRSTS = [key for key, entry in uas.UNIVERSE_POLICIES.items() if entry.get("first_election_only")]
PER_BALLOT = uas.GAME_CONFIG["UNIVERSE_POLICIES_PER_ELECTION"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- the policies --------------------------------------------------------------------------------------------------------

def test_every_option_punishes_and_says_how_in_real_words():
    for policy, entry in uas.UNIVERSE_POLICIES.items():
        assert len(entry["options"]) == 2, policy
        for option, option_entry in entry["options"].items():
            for effect, value in option_entry["effects"].items():
                hurts = value > 0 if uas.EFFECTS[effect]["better"] == "lower" else value < 0
                assert hurts, (option, effect)
            assert option_entry["desc"] and "epoch" not in option_entry["desc"].lower() and "100%" not in option_entry["desc"]
    assert FIRSTS == ["primitives"]
    assert len(uas.UNIVERSE_POLICY_OF_OPTION) == 2 * len(uas.UNIVERSE_POLICIES)


def test_the_old_options_that_only_helped_are_gone():
    names = {entry["name"] for policy in uas.UNIVERSE_POLICIES.values() for entry in policy["options"].values()}
    assert not names & {"Unregulated", "Free Trade", "Isolationist"}
    assert not {"BASE_UNREGULATED_COST_REDUCTION", "BASE_FREE_TRADE_INCREASE", "BASE_ISOLATIONIST_DECREASE"} & set(uas.GAME_CONFIG)


# --- ballots -------------------------------------------------------------------------------------------------------------

def test_the_first_ballot_has_primitives_and_one_more():
    for seed in range(20):
        ballot = up.draw_ballot(random.Random(seed), first=True)
        assert len(ballot) == PER_BALLOT and "primitives" in ballot


def test_later_ballots_never_have_primitives_nor_the_last_ballots_policies():
    for seed in range(40):
        previous = up.draw_ballot(random.Random(seed), first=True)
        ballot = up.draw_ballot(random.Random(seed + 1000), previous=previous)
        assert len(ballot) == PER_BALLOT == len(set(ballot))
        assert "primitives" not in ballot and not set(ballot) & set(previous)


def test_ballots_are_in_the_listed_order_and_follow_the_seed():
    ballot = up.draw_ballot(random.Random(9))
    order = list(uas.UNIVERSE_POLICIES)
    assert ballot == sorted(ballot, key=order.index)
    assert up.draw_ballot(random.Random(9)) == ballot


def test_the_ballot_and_what_is_in_force_come_from_the_state():
    assert up.ballot_of({"ballot": ["wealth", "labor", "gone"]}) == ["labor", "wealth"]
    assert up.ballot_of({}) == [] and up.ballot_of(None) == []
    assert up.active_options({"active_policies": ["land_tax", "transparency"]}) == ["land_tax", "transparency"]
    # A round from before the ballot keeps Treatied, the one old option still here, and loses the rest.
    assert up.active_options({"active_policies": ["Treatied", "Free Trade", "Unregulated"]}) == ["treatied"]


# --- the count -----------------------------------------------------------------------------------------------------------

def _votes(**by_option):
    """A tally: option to {kingdom: votes}, under the option's policy."""
    tally = {}
    for option, cast in by_option.items():
        tally.setdefault(uas.UNIVERSE_POLICY_OF_OPTION[option], {})[option] = cast
    return tally


def test_the_option_with_the_most_votes_wins_each_policy():
    tally = _votes(land_tax={"1": 3, "2": 4}, ceasefire_accords={"3": 6}, classified={"1": 1})
    assert up.tally(tally, ["rules_of_war", "secrecy"], "seed") == ["land_tax", "classified"]


def test_a_tie_is_decided_at_random_and_the_same_every_time_for_one_election():
    tally = _votes(land_tax={"1": 5}, ceasefire_accords={"2": 5})
    winners = {up.tally(tally, ["rules_of_war"], f"election {n}")[0] for n in range(40)}
    assert winners == {"land_tax", "ceasefire_accords"}  # either can win a tie
    assert up.tally(tally, ["rules_of_war"], "x") == up.tally(tally, ["rules_of_war"], "x")
    # No votes at all is a tie too.
    assert up.tally({}, ["labor"], "x")[0] in uas.UNIVERSE_POLICIES["labor"]["options"]


# --- who an option hits --------------------------------------------------------------------------------------------------

SCORES = {
    "networth": {str(kd): 1000 - kd for kd in range(15)},
    "galaxy_networth": {"1:1": 500, "1:2": 900, "2:1": 700, "2:2": 100},
}


def test_the_wealth_options_hit_only_the_leaders():
    top_kingdoms, top_galaxies = up.leaders(SCORES)
    assert top_kingdoms == {str(kd) for kd in range(10)} and top_galaxies == {"1:2", "2:1"}
    assert up.modifiers(["progressive_tax"], "3", "2:2", SCORES) == {"money_income": pytest.approx(-0.10)}
    assert up.modifiers(["progressive_tax"], "12", "1:2", SCORES) == {}
    assert up.modifiers(["antitrust"], "12", "1:2", SCORES) == {"money_income": pytest.approx(-0.10)}
    assert up.modifiers(["antitrust"], "3", "2:2", SCORES) == {}
    assert up.needs_scores(["antitrust"]) and not up.needs_scores(["land_tax"])


def test_the_other_options_hit_everyone():
    assert up.modifiers(["land_tax", "treatied"], "99", "9:9", {}) == pytest.approx({"settle_cost": 0.15, "unit_cost": 0.2})
    assert up.modifiers(["land_tax"]) == pytest.approx({"settle_cost": 0.15})


def test_votes_can_only_be_cast_on_the_ballot_while_an_election_is_open():
    assert up.vote_problem(["labor"], "labor", "draft_limits", True) is None
    assert up.vote_problem(["labor"], "labor", "draft_limits", False) == "Votes can only be cast while an election is open"
    assert up.vote_problem(["labor"], "wealth", "antitrust", True) == "Wealth is not on this election's ballot"
    assert up.vote_problem(["labor"], "nope", "x", True) == "Choose one of the policies on the ballot"
    assert up.vote_problem(["labor"], "labor", "antitrust", True) == "Choose one of the options of Labor"


# --- the effects only universe policies have ------------------------------------------------------------------------------

def test_attack_stars():
    assert uac._attack_stars(100, {"attack_stars": -0.15}) == 85
    assert uac._attack_stars(100) == 100


def test_primitives_defense():
    assert uac._primitives_defense(100.0, {"primitives_defense": 0.3}) == pytest.approx(130.0)


def test_failed_aggressive_operations_lose_more_and_others_do_not():
    assert uac._failure_losses(10, "bombhomes", 1000, {"aggressive_failure_losses": 1.0}) == 20
    assert uac._failure_losses(10, "spykingdom", 1000, {"aggressive_failure_losses": 1.0}) == 10
    assert uac._failure_losses(10, "bombhomes", 15, {"aggressive_failure_losses": 1.0}) == 15  # never more than sent


def test_spy_defense():
    plain, _, _ = uac._calculate_spy_probability(1000, 1000, 1000, 0.0)
    easier, drones_defense, stars_defense = uac._calculate_spy_probability(1000, 1000, 1000, 0.0, defense_modifier=-0.25)
    assert easier == pytest.approx(min(plain / 0.75, 1.0))
    assert drones_defense == pytest.approx(1000 * uas.GAME_CONFIG["BASE_DRONES_DRONE_DEFENSE_MULTIPLIER"] * 0.75)


def test_money_income(app):
    kd = kingdoms.kingdom(structures={"mines": 100}, population=10_000)
    plain = kingdoms.income(app, kd)["income"]["money"]
    taxed = kingdoms.income(app, kd, modifiers={"money_income": -0.1})["income"]["money"]
    assert taxed["bonus"] == pytest.approx(plain["bonus"] - 0.1)
    assert taxed["gross"] < plain["gross"]


def test_aggression_follows_the_universe(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(uag, "_get_state", lambda: {"state": {"active_policies": ["aggression_monitors"]}})
        assert uac._aggression_multiplier() == pytest.approx(1.5)
        monkeypatch.setattr(uag, "_get_state", lambda: {"state": {"active_policies": ["land_tax"]}})
        assert uac._aggression_multiplier() == 1.0


# --- through the routes ------------------------------------------------------------------------------------------------

def _universe(active=(), ballot=("labor", "secrecy"), open_=True, **state_fields):
    state = _get("/state")["state"]
    _create_item("state", {"state": {**state, "active_policies": list(active), "ballot": list(ballot),
                                     "election_end": "2099-01-01T00:00:00+00:00" if open_ else "", **state_fields}})
    _create_item("universe_votes", {"votes": up.empty_votes(list(ballot))})


def test_the_universe_in_force_prices_every_kingdom(app, client, jwt1):
    _set_up_kingdom(money=0)
    _universe(active=["land_tax", "treatied"], open_=False)
    settle = client.get("/api/settle", headers=_auth(jwt1)).get_json()
    kd = _get(f"/kingdom/{KD_ID}")
    assert settle["settle_price"] == pytest.approx(uag._get_settle_price(kd, {"settle_cost": 0.15}))
    mobis = client.get("/api/mobis", headers=_auth(jwt1)).get_json()
    assert mobis["units_desc"]["attack"]["cost"] == pytest.approx(uas.UNITS["attack"]["cost"] * 1.2)


def test_the_page_shows_the_ballot_my_votes_and_what_is_in_force(app, client, jwt1):
    _set_up_kingdom(money=0, votes=10)
    _universe(active=["progressive_tax", "land_tax"])
    # Kingdom 1 is not among the ten richest here.
    _create_item("scores", {"networth": {str(kd): 10_000 + kd for kd in range(2, 14)}, "galaxy_networth": {}, "points": {},
                            "stars": {}, "galaxy_kingdoms_alive": {}, "last_update": ""})
    assert client.post("/api/universepolitics/policies", json={"policy": "labor", "option": "draft_limits", "votes": 4},
                       headers=_auth(jwt1)).status_code == 200
    page = client.get("/api/universepolitics", headers=_auth(jwt1)).get_json()
    assert page["election"]["open"] is True
    assert [policy["key"] for policy in page["ballot"]] == ["labor", "secrecy"]
    labor = page["ballot"][0]["options"]
    assert [(option["key"], option["my_votes"]) for option in labor] == [("draft_limits", 4), ("research_moratorium", 0)]
    assert [(option["key"], option["hits_me"]) for option in page["active"]] == [("progressive_tax", False), ("land_tax", True)]
    # It never shows how anyone else voted.
    assert "votes" not in json.dumps(page["ballot"]).replace("my_votes", "")


@pytest.mark.parametrize("body, message", [
    ({"policy": "wealth", "option": "antitrust", "votes": 1}, "Wealth is not on this election's ballot"),
    ({"policy": "labor", "option": "antitrust", "votes": 1}, "Choose one of the options of Labor"),
    ({"policy": "labor", "option": "draft_limits", "votes": "x"}, "Choose how many votes to cast"),
])
def test_a_vote_off_the_ballot_is_refused_and_costs_nothing(app, client, jwt1, body, message):
    _set_up_kingdom(money=0, votes=10)
    _universe()
    refused = client.post("/api/universepolitics/policies", json=body, headers=_auth(jwt1))
    assert refused.status_code == 400 and refused.get_json()["message"] == message
    assert _get(f"/kingdom/{KD_ID}")["votes"] == 10


def test_no_votes_between_elections(app, client, jwt1):
    _set_up_kingdom(money=0, votes=10)
    _universe(open_=False)
    refused = client.post("/api/universepolitics/policies", json={"policy": "labor", "option": "draft_limits", "votes": 1},
                          headers=_auth(jwt1))
    assert refused.status_code == 400 and "while an election is open" in refused.get_json()["message"]
    assert _get(f"/kingdom/{KD_ID}")["votes"] == 10


# --- the elections -------------------------------------------------------------------------------------------------------

def test_an_election_runs_from_ballot_to_result_to_the_next_ballot(app):
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()
    _create_item("state", {"state": {"game_start": past, "election_start": past, "election_end": "",
                                     "active_policies": ["native_reserves"], "ballot": ["labor", "secrecy"],
                                     "next_history": past}})
    _create_item("universe_votes", {"votes": {}})
    with app.app_context():
        state = refresh._begin_election(_get("/state"))
    opened = _get("/state")["state"]
    assert opened["election_end"] and opened["active_policies"] == ["native_reserves"]  # holds while voting
    assert _get("/universevotes")["votes"] == up.empty_votes(["labor", "secrecy"])
    _create_item("universe_votes", {"votes": {"labor": {"draft_limits": {"1": 2}, "research_moratorium": {"2": 5}},
                                              "secrecy": {"classified": {"1": 3}, "transparency": {}}}})
    with app.app_context():
        refresh._resolve_election(state)
    closed = _get("/state")["state"]
    assert closed["election_end"] == "" and closed["active_policies"] == ["research_moratorium", "classified"]
    assert len(closed["ballot"]) == PER_BALLOT and not set(closed["ballot"]) & {"labor", "secrecy", "primitives"}


def test_a_round_from_before_the_ballot_draws_one_when_its_election_opens(app):
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()
    _create_item("state", {"state": {"game_start": past, "election_start": past, "election_end": "",
                                     "active_policies": [], "next_history": past}})
    _create_item("universe_votes", {"votes": {}})
    with app.app_context():
        refresh._begin_election(_get("/state"))
    ballot = _get("/state")["state"]["ballot"]
    assert len(ballot) == PER_BALLOT and "primitives" in ballot  # nothing in force yet: it is the first


def _new_round(**fields):
    body = {"game_start": "2030-01-01T00:00:00+00:00", "game_end": "2030-02-01T00:00:00+00:00", "num_galaxies": 4, **fields}
    settings, errors = admin.check_new_round(body, datetime.datetime(2029, 12, 1, tzinfo=datetime.timezone.utc))
    return settings, errors


def test_a_new_round_opens_its_first_election_a_set_time_after_the_start():
    settings, errors = _new_round()
    assert errors == {}
    epochs = uas.GAME_CONFIG["BASE_FIRST_ELECTION_START_MULTIPLIER"]
    assert settings["election_start"] == datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(
        seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * epochs)
    state = admin.round_state(settings, rounds_archived=0, rng=random.Random(1))
    assert "primitives" in state["ballot"] and len(state["ballot"]) == PER_BALLOT
    # The admin can still choose another time, or none.
    chosen, _ = _new_round(election_start="2030-01-05T00:00:00+00:00")
    assert chosen["election_start"] == datetime.datetime(2030, 1, 5, tzinfo=datetime.timezone.utc)
    none, _ = _new_round(election_start="")
    assert none["election_start"] is None
    # A round too short for the first election has none.
    short, errors = _new_round(game_end="2030-01-01T12:00:00+00:00")
    assert errors == {} and short["election_start"] is None


def test_two_kingdoms_voting_at_once_both_count(app, jwt1, jwt2):
    _set_up_kingdom(money=0, votes=5)
    _set_up_kingdom(money=0, kd_id="2", votes=5)
    _universe()

    def vote(c, i):
        return c.post("/api/universepolitics/policies", json={"policy": "labor", "option": "draft_limits", "votes": 5},
                      headers=_auth([jwt1, jwt2][i]))

    assert [r.status_code for r in _run_together(app, 2, vote)] == [200, 200]
    assert _get("/universevotes")["votes"]["labor"]["draft_limits"] == {KD_ID: 5, "2": 5}
