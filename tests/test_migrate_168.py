"""
The data migrations of issue #168 (migrations.py), run by the refresh on the first tick after a deploy. For each: the
game reads the old shape right before it runs, an action in that gap loses nothing, the migration writes the new
shape, and running it again changes nothing.
"""
import datetime
import json

import pytest

import untitledapp.galaxypolicies as gp
import untitledapp.migrations as migrations
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from tests.test_concurrency import FUNCTION_URL, KD_ID, _create_item, _get, _set_up_kingdom
from untitledapp import REQUESTS_SESSION

FIRST = list(uas.GALAXY_POLICIES)[:uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"]]
OLD_GALAXY = {
    "votes": {"policy_1": {"1": "1", "2": "2", "3": "1"}, "policy_2": {"1": "2", "4": "1"}, "leader": {"1": "1"}},
    "active_policies": ["Expansionist", "Conscription"],
    "policy_1_winner": "1", "policy_2_winner": "2", "leader": "1", "empire_invitations": [], "empire_join_requests": [],
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _old_round():
    """A running round from before #168: no draw in the state, galaxy politics in the old shape."""
    _set_up_kingdom(money=0)
    state = _get("/state")["state"]
    _create_item("state", {"state": {**state, "election_start": "", "election_end": "", "next_history": state["game_start"]}})
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID, "2", "3", "4"], "1:2": []}})
    _create_item("galaxy_votes_1:1", OLD_GALAXY)
    _create_item("galaxy_votes_1:2", {"votes": {"policy_1": {}, "policy_2": {}, "leader": {}}, "active_policies": []})
    _create_item("universe_votes", {"votes": {"policy_1": {"option_1": {}, "option_2": {}},
                                              "policy_2": {"option_1": {}, "option_2": {}}}})


def _migrate(app):
    with app.app_context():
        return migrations.run_pending(_get("/state"), refresh._claim_state)


# --- the old shape, read as the new -------------------------------------------------------------------------------

def test_old_votes_and_active_options_are_read_as_the_new_before_any_migration():
    galaxy = gp.normalize(OLD_GALAXY, FIRST)
    assert galaxy["votes"]["growth_doctrine"] == {"1": "expansionist", "3": "expansionist"}
    assert galaxy["votes"]["tempo_doctrine"] == {"2": "warlike"}
    assert galaxy["votes"]["defense_doctrine"] == {"1": "conscription", "4": "intelligence"}
    assert galaxy["active"] == {"growth_doctrine": "expansionist", "defense_doctrine": "conscription"}


def test_once_a_galaxy_is_in_the_new_shape_its_old_fields_are_ignored():
    moved = {**OLD_GALAXY, "policy_votes": {"growth_doctrine": {"9": "raiders"}}, "policy_active": {}}
    galaxy = gp.normalize(moved, FIRST)
    assert galaxy["votes"]["growth_doctrine"] == {"9": "raiders"} and galaxy["active"] == {}


def test_the_page_shows_the_old_votes_before_the_migration(app, client, jwt1):
    _old_round()
    page = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    growth = next(policy for policy in page["policies"] if policy["key"] == "growth_doctrine")
    assert growth["active"] == "expansionist" and growth["my_vote"] == "expansionist"
    assert {option["key"]: option["votes"] for option in growth["options"]} == {"expansionist": 2, "raiders": 0}


def test_a_vote_before_the_migration_keeps_every_old_vote(app, client, jwt1):
    _old_round()
    assert client.post("/api/galaxypolitics/policies", json={"policy": "tempo_doctrine", "option": "drone_foundries"},
                       headers=_auth(jwt1)).status_code == 200
    stored = _get("/galaxy/1:1/politics")
    assert stored["policy_votes"]["growth_doctrine"] == {"1": "expansionist", "3": "expansionist"}
    assert stored["policy_votes"]["tempo_doctrine"] == {"1": "drone_foundries", "2": "warlike"}
    assert stored["policy_active"] == {"growth_doctrine": "expansionist", "defense_doctrine": "conscription"}


# --- the migration --------------------------------------------------------------------------------------------------

def test_the_migration_moves_every_galaxy_and_the_state_and_is_marked_done(app):
    _old_round()
    assert _migrate(app) == [migration_id for migration_id, _ in migrations.MIGRATIONS]
    state = _get("/state")["state"]
    assert state["galaxy_policies"] == FIRST and "168_galaxy_policies" in state["migrations_done"]
    moved = _get("/galaxy/1:1/politics")
    assert moved["policy_votes"]["defense_doctrine"] == {"1": "conscription", "4": "intelligence"}
    assert moved["policy_active"] == {"growth_doctrine": "expansionist", "defense_doctrine": "conscription"}
    assert _get("/galaxy/1:2/politics")["policy_votes"] == {policy: {} for policy in FIRST}


def test_running_again_changes_nothing(app):
    _old_round()
    _migrate(app)
    before = _get("/galaxy/1:1/politics")
    assert _migrate(app) == []  # marked done: nothing pending
    with app.app_context():
        migrations.galaxy_policies(_get("/state"))  # and run by hand anyway, it leaves the moved galaxy alone
    assert _get("/galaxy/1:1/politics")["_etag"] == before["_etag"]


def test_a_galaxy_that_voted_before_the_migration_is_left_as_it_is(app, client, jwt1):
    _old_round()
    client.post("/api/galaxypolitics/policies", json={"policy": "tempo_doctrine", "option": "drone_foundries"},
                headers=_auth(jwt1))
    voted = _get("/galaxy/1:1/politics")
    _migrate(app)
    assert _get("/galaxy/1:1/politics")["_etag"] == voted["_etag"]


def test_the_refresh_runs_the_migrations_on_its_tick(app, client, monkeypatch):
    _old_round()
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    # The rest of the tick is not what this is about.
    monkeypatch.setattr(refresh.uag, "_get_kingdoms", lambda: {})
    monkeypatch.setattr(refresh, "_resolve_scores", lambda scores, now, context=None: None)
    monkeypatch.setattr(refresh, "_resolve_empires", lambda scores, now: None)
    monkeypatch.setattr(refresh, "_resolve_clusters", lambda empires, now, context: None)
    assert client.get("/api/refreshdata", headers={"Refresh-Secret": "secret"}).status_code == 200
    assert "168_galaxy_policies" in _get("/state")["state"]["migrations_done"]
    assert "policy_active" in _get("/galaxy/1:1/politics")


def test_a_failing_migration_is_tried_again_next_tick_and_does_not_stop_the_rest(app, monkeypatch):
    _old_round()
    calls = []

    def broken(state):
        calls.append(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(migrations, "MIGRATIONS", [("broken", broken)] + list(migrations.MIGRATIONS))
    ran = _migrate(app)
    assert "broken" not in ran and "168_galaxy_policies" in ran
    assert "broken" not in _get("/state")["state"]["migrations_done"]
    _migrate(app)
    assert len(calls) == 2


def test_a_new_round_needs_no_migration():
    import random
    import untitledapp.admin as admin
    settings, _ = admin.check_new_round({"game_start": "2030-01-01T00:00:00+00:00", "game_end": "2030-02-01T00:00:00+00:00",
                                         "num_galaxies": 2}, datetime.datetime(2029, 12, 1, tzinfo=datetime.timezone.utc))
    state = admin.round_state(settings, rounds_archived=0, rng=random.Random(1))
    assert migrations.pending(state) == []


# --- cluster benefits ---------------------------------------------------------------------------------------------

def test_a_round_from_before_reads_as_the_first_benefits_and_the_migration_writes_them_down(app):
    import untitledapp.clusters as clusters

    _old_round()
    first = list(uas.CLUSTER_BENEFITS)[:uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]]
    assert clusters.round_benefits(_get("/state")["state"]) == first  # before: read the same
    _migrate(app)
    state = _get("/state")["state"]
    assert state["cluster_benefits"] == first and "168_cluster_benefits" in state["migrations_done"]
    with app.app_context():
        migrations.cluster_benefits(_get("/state"))  # again: nothing changes
    assert _get("/state")["state"]["cluster_benefits"] == first


# --- universe policies ----------------------------------------------------------------------------------------------

OLD_UNIVERSE_VOTES = {"votes": {"policy_1": {"option_1": {KD_ID: 3, "2": 1}, "option_2": {"3": 2}},
                                "policy_2": {"option_1": {KD_ID: 2}, "option_2": {}}}}


def _set_votes(kd_id, votes):
    """Give kingdom ``kd_id`` ``votes`` to spend, leaving the state alone."""
    response = REQUESTS_SESSION.patch(f"{FUNCTION_URL}/kingdom/{kd_id}", data=json.dumps({"votes": votes}))
    assert response.status_code < 300, response.text


def _old_universe(election_open):
    """A round from before ballots: names in force, old-shape votes, an election open or not."""
    for kd_id in ("2", "3"):
        _set_up_kingdom(money=0, kd_id=kd_id)
    _old_round()  # after them: each setup rewrites the state
    for kd_id, votes in ((KD_ID, 1), ("2", 0), ("3", 0)):
        _set_votes(kd_id, votes)
    state = _get("/state")["state"]
    soon = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).isoformat()
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    _create_item("state", {"state": {**state, "active_policies": ["Treatied", "Free Trade"],
                                     "election_start": past if election_open else soon,
                                     "election_end": soon if election_open else ""}})
    _create_item("universe_votes", OLD_UNIVERSE_VOTES)


def test_before_the_migration_the_universe_reads_as_after_it(app, client, jwt1):
    import untitledapp.universepolicies as up

    _old_universe(election_open=True)
    inner = _get("/state")["state"]
    page = client.get("/api/universepolitics", headers=_auth(jwt1)).get_json()
    assert [option["key"] for option in page["active"]] == ["treatied"]
    ballot = [policy["key"] for policy in page["ballot"]]
    assert ballot == up.ballot_of(inner) and len(ballot) == uas.GAME_CONFIG["UNIVERSE_POLICIES_PER_ELECTION"]
    # A vote before the migration goes on that ballot, beside the old votes.
    policy = ballot[0]
    option = list(uas.UNIVERSE_POLICIES[policy]["options"])[0]
    _set_votes(KD_ID, 4)
    assert client.post("/api/universepolitics/policies", json={"policy": policy, "option": option, "votes": 4},
                       headers=_auth(jwt1)).status_code == 200
    stored = _get("/universevotes")["votes"]
    assert stored[policy][option] == {KD_ID: 4} and "policy_1" in stored


def test_an_open_elections_old_votes_are_given_back_and_new_ones_kept(app, client, jwt1):
    import untitledapp.universepolicies as up

    _old_universe(election_open=True)
    ballot = up.ballot_of(_get("/state")["state"])
    policy, option = ballot[0], list(uas.UNIVERSE_POLICIES[ballot[0]]["options"])[0]
    _set_votes(KD_ID, 4)
    client.post("/api/universepolitics/policies", json={"policy": policy, "option": option, "votes": 4}, headers=_auth(jwt1))
    _migrate(app)
    state = _get("/state")["state"]
    assert state["active_policies"] == ["treatied"] and state["ballot"] == ballot
    votes = _get("/universevotes")
    assert "policy_1" not in votes["votes"] and votes["votes"][policy][option] == {KD_ID: 4}
    assert votes["refunds_pending"] == {}
    # Kingdom 1 spent its 4 on the ballot and gets back the 5 it spent on the old doctrines.
    assert _get(f"/kingdom/{KD_ID}")["votes"] == 5 and _get("/kingdom/2")["votes"] == 1 and _get("/kingdom/3")["votes"] == 2
    # Again: nobody is paid twice.
    with app.app_context():
        migrations.universe_policies(_get("/state"))
    assert _get(f"/kingdom/{KD_ID}")["votes"] == 5 and _get("/kingdom/3")["votes"] == 2


def test_between_elections_old_votes_were_counted_already_and_are_not_given_back(app):
    _old_universe(election_open=False)
    _migrate(app)
    assert _get(f"/kingdom/{KD_ID}")["votes"] == 1 and _get("/kingdom/3")["votes"] == 0
    assert "policy_1" not in _get("/universevotes")["votes"]
    assert "primitives" not in _get("/state")["state"]["ballot"]  # Treatied is in force: not the first election


def test_the_refunds_owed_are_the_votes_spent_in_the_open_election():
    assert migrations.universe_refunds(OLD_UNIVERSE_VOTES["votes"], True) == {KD_ID: 5, "2": 1, "3": 2}
    assert migrations.universe_refunds(OLD_UNIVERSE_VOTES["votes"], False) == {}
