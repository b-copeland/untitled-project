"""The galaxy policies' rules (galaxypolicies.py): the round's draw, the timed tally, and what the options are worth."""
import datetime
import random
import re

import pytest

import untitledapp.galaxypolicies as gp
import untitledapp.shared as uas

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
HOUR = datetime.timedelta(hours=1)
POLICIES = ["growth_doctrine", "industry"]


def period():
    return datetime.timedelta(seconds=gp.tally_seconds())


def at(hours):
    return START + hours * HOUR


def stored(galaxy):
    return gp.written(galaxy)


def vote(document, when, kd_id, option, policy="growth_doctrine"):
    """The document after ``kd_id`` votes ``option`` at ``when``, as the vote route writes it."""
    galaxy = gp.advance(document, POLICIES, START, when)
    gp.cast(galaxy, kd_id, policy, option)
    return stored(galaxy)


def active(document, when):
    return gp.advance(document, POLICIES, START, when)["active"]


# --- the policies themselves -----------------------------------------------------------------------------------------

def test_every_policy_has_two_options_and_every_option_is_one_policys():
    assert all(len(entry["options"]) == 2 for entry in uas.GALAXY_POLICIES.values())
    assert len(uas.GALAXY_POLICY_OF_OPTION) == 2 * len(uas.GALAXY_POLICIES)


def test_every_option_does_something_the_game_knows_and_says_what_in_real_words():
    for policy, entry in uas.GALAXY_POLICIES.items():
        for option, option_entry in entry["options"].items():
            assert option_entry["effects"], option
            assert set(option_entry["effects"]) <= set(uas.EFFECTS), option
            assert option_entry["desc"] and "epoch" not in option_entry["desc"].lower(), option


def test_both_options_of_a_policy_only_help_the_galaxy():
    # Each effect is signed the way that helps: no galaxy option makes the galaxy's own kingdoms worse off.
    for entry in uas.GALAXY_POLICIES.values():
        for option, option_entry in entry["options"].items():
            for effect, value in option_entry["effects"].items():
                helps = value < 0 if uas.EFFECTS[effect]["better"] == "lower" else value > 0
                assert helps, (option, effect)


def test_the_sentences_name_the_size_of_the_effect():
    assert uas.effect_text("settle_cost", -0.15) == "Settling costs 15% less"
    assert uas.effect_text("pop_growth", 0.5) == "Population grows 50% faster"
    assert uas.effects_text({"rob_primitives": 0.2, "siphon_shield_fuel": -0.25}) == (
        "Robbing primitives yields 20% more money. Shielding Siphon Funds operations costs 25% less fuel")
    assert uas.GALAXY_POLICIES["refit_doctrine"]["options"]["renovators"]["desc"] == (
        "Razing structures refunds 50% of the build cost instead of 25%")


def test_modifiers_add_up_across_sources_and_read_zero_when_absent():
    assert uas.add_modifiers({"settle_cost": -0.15}, {"settle_cost": -0.05, "unit_cost": -0.02}, None) == pytest.approx(
        {"settle_cost": -0.20, "unit_cost": -0.02})
    assert uas.modifier(None, "settle_cost") == 0.0
    assert uas.modifier({"unit_cost": -0.1}, "settle_cost") == 0.0


# --- the draw ----------------------------------------------------------------------------------------------------------

def test_a_round_draws_its_share_of_different_policies_in_the_listed_order():
    drawn = gp.draw(random.Random(3))
    assert len(drawn) == uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"] == len(set(drawn))
    order = list(uas.GALAXY_POLICIES)
    assert drawn == sorted(drawn, key=order.index)
    assert gp.draw(random.Random(3)) == drawn  # the same seed, the same round
    assert {tuple(gp.draw(random.Random(seed))) for seed in range(30)} != {tuple(drawn)}  # and it does vary


def test_a_draw_never_asks_for_more_than_there_are():
    assert sorted(gp.draw(random.Random(1), count=100)) == sorted(uas.GALAXY_POLICIES)
    assert gp.draw(random.Random(1), count=0) == []


def test_the_rounds_policies_come_from_the_state_and_older_rounds_play_the_first_ones():
    assert gp.round_policies({"galaxy_policies": ["arsenal", "economy"]}) == ["arsenal", "economy"]
    assert gp.round_policies({"galaxy_policies": ["arsenal", "gone"]}) == ["arsenal"]
    first = list(uas.GALAXY_POLICIES)[:uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"]]
    assert gp.round_policies({}) == first and gp.round_policies(None) == first
    assert gp.round_policies({"galaxy_policies": []}) == first


# --- the tally times ---------------------------------------------------------------------------------------------------

def test_tallies_fall_at_the_start_and_every_period_after_it():
    assert gp.tally_after(START, START - HOUR) == START
    assert gp.tally_after(START, START) == START + period()  # strictly after
    assert gp.tally_after(START, START + period() / 2) == START + period()
    assert gp.tally_after(START, START + period()) == START + 2 * period()


# --- the tally ---------------------------------------------------------------------------------------------------------

def test_no_votes_no_policy():
    assert active({}, at(100)) == {}
    assert gp.advance({}, POLICIES, START, at(100))["votes"] == {"growth_doctrine": {}, "industry": {}}


def test_a_vote_does_not_switch_the_policy_until_a_tally():
    document = vote({}, at(1), "1", "expansionist")
    assert active(document, at(1)) == {}
    tally = gp.tally_after(START, at(1))
    assert active(document, tally - datetime.timedelta(seconds=1)) == {}
    assert active(document, tally) == {"growth_doctrine": "expansionist"}


def test_votes_cast_before_the_round_count_at_its_start():
    document = vote({}, START - 3 * HOUR, "1", "raiders")
    assert active(document, START - HOUR) == {}
    assert active(document, START) == {"growth_doctrine": "raiders"}


def test_the_tally_counts_the_votes_as_they_are_at_the_tally():
    # Two kingdoms vote Expansionist all through the window; three switch to Raiders an hour before the tally.
    tally = START + period()
    document = vote({}, START, "1", "expansionist")
    document = vote(document, START, "2", "expansionist")
    assert active(document, tally) == {"growth_doctrine": "expansionist"}
    for kd in ("3", "4", "5"):
        document = vote(document, tally + period() - HOUR, kd, "raiders")
    assert active(document, tally + period() - datetime.timedelta(seconds=1)) == {"growth_doctrine": "expansionist"}
    assert active(document, tally + period()) == {"growth_doctrine": "raiders"}  # three votes to two at the tally


def test_a_vote_cast_just_before_a_tally_counts_in_full():
    tally = START + period()
    document = vote({}, START, "1", "expansionist")
    document = vote(document, START, "2", "raiders")
    assert active(document, tally) == {}  # even: nothing changes
    document = vote(document, tally + period() - datetime.timedelta(minutes=10), "3", "raiders")
    assert active(document, tally + period()) == {"growth_doctrine": "raiders"}


def test_a_tie_keeps_the_active_option():
    tally = START + period()
    document = vote({}, START, "1", "expansionist")
    assert active(document, tally) == {"growth_doctrine": "expansionist"}
    document = vote(document, tally, "2", "raiders")  # one each for the whole next window
    assert active(document, tally + period()) == {"growth_doctrine": "expansionist"}
    # Everyone withdrawing keeps it too.
    document = vote(document, tally + period(), "1", None)
    document = vote(document, tally + period(), "2", None)
    assert active(document, tally + 5 * period()) == {"growth_doctrine": "expansionist"}


def test_votes_carry_from_one_tally_to_the_next():
    tally = START + period()
    document = vote({}, START, "1", "expansionist")
    galaxy = gp.advance(document, POLICIES, START, tally + 3 * period())
    assert galaxy["votes"]["growth_doctrine"] == {"1": "expansionist"} and galaxy["active"] == {"growth_doctrine": "expansionist"}


def test_the_tally_is_the_same_however_often_it_is_read():
    document = vote({}, at(1), "1", "expansionist")
    document = vote(document, at(2), "2", "raiders")
    document = vote(document, at(3), "3", "raiders")
    once = gp.advance(document, POLICIES, START, at(40))
    stepwise = document
    for hours in (5, 6, 13, 20.5, 33, 40):
        stepwise = stored(gp.advance(stepwise, POLICIES, START, at(hours)))
    again = gp.advance(stepwise, POLICIES, START, at(40))
    assert again["active"] == once["active"] and again["votes"] == once["votes"]


def test_reading_at_an_earlier_moment_changes_nothing():
    document = vote({}, at(10), "1", "expansionist")
    assert gp.advance(document, POLICIES, START, at(5))["updated"] == at(10).isoformat()


def test_policies_are_independent():
    tally = START + period()
    document = vote({}, START, "1", "expansionist")
    document = vote(document, START, "1", "engineering_corps", policy="industry")
    assert active(document, tally) == {"growth_doctrine": "expansionist", "industry": "engineering_corps"}


def test_a_galaxy_from_before_the_tally_keeps_its_active_policies_by_name():
    legacy = {"active_policies": ["Expansionist", "Warlike"], "votes": {"policy_1": {"1": "1"}}}
    assert active(legacy, at(1)) == {"growth_doctrine": "expansionist"}  # Warlike's policy is not in this round
    document = vote(legacy, at(1), "1", "raiders")
    assert gp.normalize(document, POLICIES)["active"] == {"growth_doctrine": "expansionist"}  # until a tally says not


def test_votes_for_options_this_round_does_not_play_are_dropped():
    document = {"policy_votes": {"growth_doctrine": {"1": "warlike"}, "economy": {"1": "refineries"}},
                "policy_active": {"economy": "refineries"}}
    galaxy = gp.normalize(document, POLICIES)
    assert galaxy["votes"] == {"growth_doctrine": {}, "industry": {}} and galaxy["active"] == {}


# --- votes ---------------------------------------------------------------------------------------------------------------

def test_a_vote_for_what_it_already_is_changes_nothing():
    galaxy = gp.advance({}, POLICIES, START, at(1))
    assert gp.cast(galaxy, "1", "growth_doctrine", "raiders") is True
    assert gp.cast(galaxy, "1", "growth_doctrine", "raiders") is False
    assert gp.cast(galaxy, "1", "growth_doctrine", None) is True
    assert gp.cast(galaxy, "1", "growth_doctrine", None) is False


def test_what_a_vote_can_be_for():
    assert gp.vote_problem(POLICIES, "growth_doctrine", "raiders") is None
    assert gp.vote_problem(POLICIES, "growth_doctrine", None) is None
    assert gp.vote_problem(POLICIES, "economy", "refineries") == "Economy is not one of this round's policies"
    assert gp.vote_problem(POLICIES, "nope", "x") == "Choose one of this round's policies"
    assert gp.vote_problem(POLICIES, "growth_doctrine", "warlike") == "Choose one of the options of Growth Doctrine"


# --- what the options are worth ------------------------------------------------------------------------------------------

def test_modifiers_are_the_active_options_effects():
    tally = START + period()
    document = vote({}, START, "1", "expansionist")
    document = vote(document, START, "1", "industrialists", policy="industry")
    assert gp.modifiers(gp.advance(document, POLICIES, START, tally)) == pytest.approx(
        {"settle_cost": -0.15, "structure_cost": -0.15})
    assert gp.modifiers(gp.advance(document, POLICIES, START, at(1))) == {}


# --- what the page shows --------------------------------------------------------------------------------------------------

def test_the_view_shows_each_policy_and_its_votes():
    document = vote({}, START, "1", "expansionist")
    document = vote(document, START + 3 * HOUR, "2", "raiders")
    document = vote(document, START + 3 * HOUR, "3", "raiders")
    galaxy = gp.advance(document, POLICIES, START, START + 4 * HOUR)
    view = gp.view(galaxy, POLICIES, START, START + 4 * HOUR, "2")
    assert [policy["key"] for policy in view["policies"]] == POLICIES
    growth = view["policies"][0]
    assert growth["my_vote"] == "raiders" and growth["active"] is None
    options = {option["key"]: option for option in growth["options"]}
    assert options["expansionist"]["votes"] == 1 and options["raiders"]["votes"] == 2
    assert options["expansionist"]["desc"] == "Settling costs 15% less"
    assert view["next_tally"] == (START + period()).isoformat()
    assert view["tally_hours"] == pytest.approx(period() / HOUR)
    assert all(option["votes"] == 0 for option in view["policies"][1]["options"])


def test_every_effect_is_read_somewhere_in_the_game():
    """An effect that nothing reads would be an option that does nothing."""
    import pathlib

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (pathlib.Path(__file__).resolve().parent.parent / "api" / "untitledapp").glob("*.py")
        if path.name != "shared.py"
    ) + pathlib.Path(uas.__file__).read_text(encoding="utf-8").split("EFFECTS = {", 1)[0]
    for effect in uas.EFFECTS:
        assert re.search(rf'["\']{effect}["\']', source), f"nothing reads {effect}"


# --- the news of a tally -----------------------------------------------------------------------------------------------

def test_the_last_tally_and_what_it_adopted():
    assert gp.last_tally(START, START - HOUR) is None
    assert gp.last_tally(START, START) == START
    assert gp.last_tally(START, START + period() + HOUR) == START + period()
    document = vote({}, START + HOUR, "1", "expansionist")
    assert gp.adopted_at(document, POLICIES, START, START + period()) == {"growth_doctrine": "expansionist"}
    assert gp.adopted_at(document, POLICIES, START, START + 2 * period()) == {}  # already active: nothing new


def test_the_refresh_posts_what_a_tally_adopted_once(app):
    import untitledapp.refresh as refresh
    from tests.test_concurrency import _create_item, _get, _set_up_kingdom

    _set_up_kingdom(money=0)
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - 2 * period() - HOUR
    state = _get("/state")["state"]
    _create_item("state", {"state": {**state, "game_start": start.isoformat(), "galaxy_policies": POLICIES}})
    _create_item("galaxies", {"galaxies": {"1:1": ["1"]}})
    _create_item("galaxy_news_1:1", {"news": []})
    _create_item("galaxy_votes_1:1", {"votes": {"leader": {}}, "policy_votes": {"industry": {"1": "industrialists"}},
                                      "policy_active": {}, "policy_updated": (start + period() + HOUR).isoformat()})
    with app.app_context():
        for _ in range(2):  # a second tick finds the tally's news posted
            refresh._galaxy_tally_news(_get("/state"), refresh._RefreshContext(_get("/state")), now)
    news = [item["news"] for item in _get("/galaxy/1:1/news")["news"]]
    assert news.count("The galaxy voted for the Industrialists policy") == 1
