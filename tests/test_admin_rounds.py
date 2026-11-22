"""
Starting a round from the admin page (issue #172): ``POST /api/admin/newround``, changing its dates
(``POST /api/admin/round``) and adding bots. See docs/admin.md.

These are the operations that used to be finicky, so the tests walk whole rounds through the real routes: from an
empty container, from one ``/deleteall`` blanked (every test's starting point), from a running round, from a finished
one, after a failure part way, and with the refresh ticking in between.
"""
import datetime
import json

import pytest

import untitledapp
import untitledapp.admin as admin
import untitledapp.roundend as roundend
import untitledapp.shared as uas
from tests.test_concurrency import _create_item, _get
from untitledapp import REQUESTS_SESSION, User

SECRET = "round-tests"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(delta=datetime.timedelta(0), **kwargs):
    return (_now() + delta + datetime.timedelta(**kwargs)).isoformat()


def new_round_body(**overrides):
    """A good new round: started a minute ago, a week long, first election in two days, four galaxies."""
    body = {
        "game_start": _iso(minutes=-1),
        "game_end": _iso(days=7),
        "election_start": _iso(days=2),
        "num_galaxies": 4,
    }
    body.update(overrides)
    return body


_ADMIN_TOKEN = {}


def _admin(client):
    """The admin's headers. One login for the module (checking a password is slow on purpose): the admin user comes
    back with the same id in every test, and admin routes do not check the round."""
    if "token" not in _ADMIN_TOKEN:
        _ADMIN_TOKEN["token"] = client.post("/api/login", json={"username": "admin", "password": "admin"}).get_json()["accessToken"]
    return {"Authorization": f"Bearer {_ADMIN_TOKEN['token']}"}


def _player(client, name="user1", password="user1"):
    token = client.post("/api/login", json={"username": name, "password": password}).get_json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def docs(backend):
    """The documents as stored (the in-memory container; these tests read it directly)."""
    if backend is None:
        pytest.skip("reads the in-memory container")
    return backend.docs


@pytest.fixture
def ticks(monkeypatch, client):
    """``ticks()`` runs one refresh and returns its text; it fails the test on an error, as a real tick would log one."""
    monkeypatch.setenv("REFRESH_SECRET", SECRET)

    def tick():
        response = client.get("/api/refreshdata", headers={"Refresh-Secret": SECRET})
        text = response.get_data(as_text=True)
        assert response.status_code == 200, text
        assert "failed" not in text, text
        return text

    return tick


def _start(client, **overrides):
    response = client.post("/api/admin/newround", json=new_round_body(**overrides), headers=_admin(client))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _make_kingdom(client, headers, name, preset="explorer"):
    response = client.post("/api/createkingdom", json={"kdName": name, "preset": preset}, headers=headers)
    assert response.status_code == 200, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['accessToken']}"}


def _state():
    return _get("/state")["state"]


def _users(app):
    with app.app_context():
        return {user.username: user for user in User.all()}


# --- the rules, as plain functions ------------------------------------------------------------------------------------

def test_a_good_new_round_has_no_errors_and_its_times_come_back_in_utc():
    now = _now()
    settings, errors = admin.check_new_round({
        "game_start": "2030-01-01T10:00:00Z",  # what the page sends (toISOString)
        "game_end": "2030-01-08T12:00:00+02:00",
        "election_start": "",
        "num_galaxies": "1,2",
    }, now)

    assert errors == {}
    assert settings["game_start"].isoformat() == "2030-01-01T10:00:00+00:00"
    assert settings["game_end"].isoformat() == "2030-01-08T10:00:00+00:00"
    assert settings["election_start"] is None and settings["num_galaxies"] == 12
    assert settings["cluster_size"] == uas.GAME_CONFIG["CLUSTER_SIZE"] and settings["archive"] is True


@pytest.mark.parametrize("change, field", [
    ({"game_start": ""}, "game_start"),
    ({"game_start": "next tuesday"}, "game_start"),
    ({"game_end": ""}, "game_end"),
    ({"game_end": "2020-01-01T00:00:00+00:00"}, "game_end"),  # in the past
    ({"game_start": "2031-01-01T00:00:00+00:00", "game_end": "2030-06-01T00:00:00+00:00"}, "game_end"),
    ({"election_start": "soon"}, "election_start"),
    ({"election_start": "2032-01-01T00:00:00+00:00"}, "election_start"),  # after the end
    ({"num_galaxies": 0}, "num_galaxies"),
    ({"num_galaxies": admin.MAX_GALAXIES + 1}, "num_galaxies"),
    ({"num_galaxies": "many"}, "num_galaxies"),
    ({"cluster_size": 0}, "cluster_size"),
])
def test_a_bad_new_round_names_the_field(change, field):
    body = {"game_start": "2030-01-01T00:00:00+00:00", "game_end": "2030-02-01T00:00:00+00:00",
            "election_start": "2030-01-03T00:00:00+00:00", "num_galaxies": 4, **change}
    _, errors = admin.check_new_round(body, _now())
    assert field in errors, errors


def test_the_round_state_is_complete_and_starts_clean():
    settings, _ = admin.check_new_round(new_round_body(cluster_size=3), _now())
    state = admin.round_state(settings, rounds_archived=4)

    # every key the refresh and the decorators read
    assert {"game_start", "game_end", "election_start", "election_end", "next_history", "active_policies",
            "game_over", "rounds_archived"} <= set(state)
    assert state["election_end"] == "" and state["game_over"] == "" and state["active_policies"] == []
    assert state["next_history"] == state["game_start"] and state["rounds_archived"] == 4
    assert state["cluster_size"] == 3


def _stored(**overrides):
    return {"game_start": _iso(hours=2), "game_end": _iso(days=7), "election_start": "", "election_end": "",
            "game_over": "", **overrides}


def test_before_the_start_the_start_can_move_and_takes_the_history_mark_with_it():
    new_start = _iso(hours=5)
    changes, errors = admin.check_round_change(_stored(), {"game_start": new_start}, _now())
    assert errors == {}
    assert changes["game_start"] == changes["next_history"] == uas.utc(new_start).isoformat()


@pytest.mark.parametrize("stored, change, field", [
    ({"game_start": _iso(hours=-1)}, {"game_start": _iso(hours=3)}, "game_start"),  # already started
    ({}, {"game_end": _iso(hours=-1)}, "game_end"),  # in the past: End the round now is for that
    ({}, {"game_end": _iso(hours=1)}, "game_end"),  # before the start
    ({"election_end": _iso(hours=10)}, {"election_start": _iso(days=3)}, "election_start"),  # one is open
    ({}, {"election_start": _iso(days=30)}, "election_start"),  # after the end
    ({"game_over": _iso()}, {"game_end": _iso(days=9)}, "round"),
    ({"game_start": "", "game_end": ""}, {"game_end": _iso(days=9)}, "round"),
])
def test_a_bad_change_to_the_round_names_the_field(stored, change, field):
    _, errors = admin.check_round_change(_stored(**stored), change, _now())
    assert field in errors, errors


def test_an_empty_election_start_means_no_more_elections():
    changes, errors = admin.check_round_change(_stored(election_start=_iso(days=2)), {"election_start": ""}, _now())
    assert errors == {} and changes == {"election_start": ""}


# --- who may ----------------------------------------------------------------------------------------------------------

def test_players_can_not_run_the_round(app, client):
    headers = _player(client)
    assert client.get("/api/admin/round", headers=headers).status_code in (401, 403)
    assert client.post("/api/admin/newround", json=new_round_body(), headers=headers).status_code in (401, 403)
    assert client.post("/api/admin/round", json={"game_end": _iso(days=9)}, headers=headers).status_code in (401, 403)
    assert client.post("/api/admin/bots", json={"total": 1}, headers=headers).status_code in (401, 403)


def test_the_old_round_routes_are_gone(app, client):
    headers = _admin(client)
    for path in ("/api/resetstate", "/api/createstate", "/api/updatestate"):
        assert client.post(path, json={}, headers=headers).status_code in (404, 405)  # 405: the page catch-all


# --- starting a round, from every starting point --------------------------------------------------------------------

def test_a_blanked_container_shows_no_round_and_a_new_round_makes_a_playable_game(app, client, docs, ticks):
    """Every test starts here: what ``/deleteall`` leaves. This is a fresh deployment as the admin first sees it."""
    summary = client.get("/api/admin/round", headers=_admin(client)).get_json()
    assert summary["phase"] == "not set up" and summary["galaxies"] == 0

    body = _start(client, cluster_size=3)

    assert body["round"]["phase"] == "running"
    assert sorted(_get("/galaxies")["galaxies"]) == ["1:1", "1:2", "1:3", "2:1"]
    assert all(f"galaxy_votes_{g}" in docs and f"galaxy_news_{g}" in docs for g in ["1:1", "2:1"])
    assert client.get("/api/state").status_code == 200
    assert ticks() == "Refreshed"

    kingdom = _make_kingdom(client, _player(client), "First Light")
    assert ticks() == "Refreshed"
    assert client.get("/api/kingdom", headers=kingdom).status_code == 200
    assert _get("/scores")["stars"]


def test_an_empty_container_needs_nothing_but_a_new_round(app, client, docs, backend, ticks):
    backend.reset()  # not even the users
    with app.app_context():
        untitledapp.seed_testing_users()

    _start(client)

    for core in ("state", "kingdoms", "galaxies", "empires", "scores", "universe_votes", "universe_news"):
        assert core in backend.docs
    assert _get("/state")["round"]
    assert ticks() == "Refreshed"


def test_a_round_that_has_not_started_waits_and_kingdoms_made_early_earn_from_the_start(app, client, docs, ticks):
    start = _now() + datetime.timedelta(hours=3)
    _start(client, game_start=start.isoformat(), election_start=_iso(days=2))
    assert client.get("/api/admin/round", headers=_admin(client)).get_json()["phase"] == "not started"

    _make_kingdom(client, _player(client), "Early Bird")
    kingdom = next(doc for doc_id, doc in docs.items() if doc_id.startswith("kingdom_") and doc.get("name") == "Early Bird")

    assert uas.utc(kingdom["last_income"]) == start
    assert ticks() == "Not started"


def test_times_typed_with_a_z_work_everywhere(app, client, ticks):
    _start(client, game_start=(_now() - datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           game_end=(_now() + datetime.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
           election_start="")

    assert "Z" not in _state()["game_start"] and "Z" not in _state()["game_end"]
    assert client.get("/api/state").status_code == 200
    assert ticks() == "Refreshed"


def test_a_bad_new_round_changes_nothing(app, client, ticks):
    _start(client)
    _make_kingdom(client, _player(client), "Still Here")
    before = _state()

    response = client.post("/api/admin/newround", json=new_round_body(game_end=_iso(days=-1)), headers=_admin(client))

    assert response.status_code == 400 and "game_end" in response.get_json()["errors"]
    assert _state() == before
    assert "Still Here" in _get("/kingdoms")["kingdoms"].values()


# --- the next round ------------------------------------------------------------------------------------------------

def test_a_whole_round_then_the_next_one_starts_clean(app, client, docs, ticks):
    """Round one is played, ends and is archived; round two starts from nothing but users and the archive."""
    _start(client)
    old_player = _make_kingdom(client, _player(client), "Round One")
    assert client.post("/api/admin/bots", json={"total": 2}, headers=_admin(client)).status_code == 201
    ticks()
    old_round = _get("/state")["round"]
    old_next_id = _get("/kingdoms")["next_id"]
    assert client.post("/api/admin/endround", headers=_admin(client)).status_code == 200
    assert ticks() == "Round over"

    _start(client, num_galaxies=2, cluster_size=1)

    state = _state()
    assert state["game_over"] == "" and state["rounds_archived"] == 1 and state["election_end"] == ""
    assert _get("/state")["round"] != old_round
    assert _get("/kingdoms")["kingdoms"] == {} and _get("/kingdoms")["next_id"] >= old_next_id
    assert _get("/galaxies")["galaxies"] == {"1:1": [], "2:1": []}
    assert _get("/scores")["stars"] == {} and _get("/scores")["points"] == {}
    assert _get("/empires")["empires"] == {}
    assert not any(doc_id.startswith(("kingdom_", "galaxy_votes_1:2", "galaxy_intel_", "cluster_"))
                   for doc_id in docs)
    assert "archive_1" in docs
    assert all(not user.kd_id and not user.kd_created for user in _users(app).values())
    # the old login token is from another round: the app signs the player out when it next loads (decision 0005)
    assert client.get("/api/kingdomid", headers=old_player).status_code == 401

    assert ticks() == "Refreshed"
    again = _make_kingdom(client, _player(client), "Round One")  # the name is free again
    assert client.post("/api/admin/bots", json={"total": 2}, headers=_admin(client)).status_code == 201
    assert ticks() == "Refreshed"
    assert client.get("/api/kingdom", headers=again).status_code == 200
    assert len(_get("/kingdoms")["kingdoms"]) == 3


def test_a_running_round_is_archived_first_unless_the_admin_says_not(app, client, docs, ticks):
    _start(client)
    _make_kingdom(client, _player(client), "Kept")
    ticks()

    _start(client)
    assert _state()["rounds_archived"] == 1
    assert docs["archive_1"]["reason"] == "Ended by the admin to start a new round"

    _make_kingdom(client, _player(client), "Thrown Away")
    _start(client, archive=False)
    assert _state()["rounds_archived"] == 1 and "number" not in docs.get("archive_2", {})


def test_a_round_that_never_started_is_not_archived(app, client, docs):
    _start(client, game_start=_iso(hours=3))
    _make_kingdom(client, _player(client), "Too Early")

    _start(client)

    # earlier tests leave blanked archive_ documents behind: only one with content counts
    assert _state()["rounds_archived"] == 0 and not any(d.startswith("archive_") and "number" in docs[d] for d in docs)


def test_nothing_from_the_last_round_state_carries_over(app, client, ticks):
    _start(client)
    _create_item("state", {"state": {**_state(), "election_end": _iso(hours=5), "active_policies": ["Arms Race"],
                                     "something_old": 1}})

    _start(client)

    state = _state()
    assert state["election_end"] == "" and state["active_policies"] == [] and "something_old" not in state
    assert ticks() == "Refreshed"


def test_starting_the_same_round_twice_is_the_same_as_once(app, client, ticks):
    _start(client, archive=False)
    _start(client, archive=False)
    assert len(_get("/galaxies")["galaxies"]) == 4 and _state()["rounds_archived"] == 0
    assert ticks() == "Refreshed"


def test_a_new_round_that_fails_part_way_leaves_the_game_paused_and_running_it_again_fixes_it(app, client, ticks, monkeypatch):
    _start(client)
    _make_kingdom(client, _player(client), "Interrupted")
    real = admin._function_app

    def galaxies_fail(method, path, payload=None):
        if path.startswith("/galaxy/"):
            return type("Failed", (), {"status_code": 500, "text": "no"})()
        return real(method, path, payload)

    monkeypatch.setattr(admin, "_function_app", galaxies_fail)
    response = client.post("/api/admin/newround", json=new_round_body(archive=False), headers=_admin(client))
    assert response.status_code == 500 and "paused" in response.get_json()["message"]

    # paused: the refresh does nothing, players can not act
    assert ticks() == "Round over"
    assert client.post("/api/createkingdom", json={"kdName": "Sneaky", "preset": "explorer"},
                       headers=_player(client)).status_code == 400

    monkeypatch.setattr(admin, "_function_app", real)
    _start(client, archive=False)
    assert ticks() == "Refreshed"
    assert _state()["game_over"] == "" and len(_get("/galaxies")["galaxies"]) == 4


def test_a_refresh_that_runs_while_the_round_is_being_reset_does_nothing(app, client, ticks, monkeypatch):
    """The refresh is called every minute whatever the admin is doing: one landing mid-reset must not run the game."""
    _start(client)
    _make_kingdom(client, _player(client), "Busy")
    real = admin._function_app
    seen = []

    def tick_during_reset(method, path, payload=None):
        if path == "/resetstate":
            seen.append(_state()["game_over"])  # what a tick starting now would see
        return real(method, path, payload)

    monkeypatch.setattr(admin, "_function_app", tick_during_reset)
    _start(client, archive=False)

    assert seen and seen[0]  # paused before anything was deleted
    assert roundend.is_over({"state": {"game_over": seen[0]}})


# --- changing the round --------------------------------------------------------------------------------------------

def test_the_admin_can_extend_a_round_and_move_its_election(app, client, ticks):
    _start(client)
    new_end, new_election = _iso(days=10), _iso(days=4)

    response = client.post("/api/admin/round", json={"game_end": new_end, "election_start": new_election},
                           headers=_admin(client))

    assert response.status_code == 200, response.get_json()
    assert uas.utc(_state()["game_end"]) == uas.utc(new_end)
    assert uas.utc(_state()["election_start"]) == uas.utc(new_election)
    assert ticks() == "Refreshed"


def test_moving_the_start_before_it_moves_the_clocks_and_after_it_is_refused(app, client):
    _start(client, game_start=_iso(hours=2), election_start="")
    later = _iso(hours=6)

    assert client.post("/api/admin/round", json={"game_start": later}, headers=_admin(client)).status_code == 200
    assert uas.utc(_state()["game_start"]) == uas.utc(later) == uas.utc(_state()["next_history"])
    assert uas.utc(_get("/scores")["last_update"]) == uas.utc(later)
    assert uas.utc(_get("/empires")["last_update"]) == uas.utc(later)

    _start(client, archive=False)  # started a minute ago
    refused = client.post("/api/admin/round", json={"game_start": _iso(hours=1)}, headers=_admin(client))
    assert refused.status_code == 400 and "game_start" in refused.get_json()["errors"]


def test_a_finished_or_missing_round_can_not_be_changed(app, client):
    response = client.post("/api/admin/round", json={"game_end": _iso(days=3)}, headers=_admin(client))
    assert response.status_code == 400  # nothing set up yet

    _start(client)
    client.post("/api/admin/endround", headers=_admin(client))
    response = client.post("/api/admin/round", json={"game_end": _iso(days=3)}, headers=_admin(client))
    assert response.status_code == 400 and "over" in response.get_json()["message"]


# --- bots ------------------------------------------------------------------------------------------------------------

def test_bots_by_total_get_the_default_mix(app, client):
    import untitledapp.bots as bots
    _start(client)

    response = client.post("/api/admin/bots", json={"total": 5}, headers=_admin(client))

    assert response.status_code == 201, response.get_json()
    names = response.get_json()["bots"]
    made = {kind: sum(1 for name in names if name.startswith(f"bot_{kind}_")) for kind in bots.ARCHETYPES}
    assert made == {**{kind: 0 for kind in bots.ARCHETYPES}, **bots.mix_for(5)}


@pytest.mark.parametrize("body", [{"total": 0}, {"total": admin.MAX_BOTS_PER_CALL + 1}, {"total": "lots"},
                                  {"explorer": -1}, {"pirate": 2}])
def test_bad_bot_requests_are_refused(app, client, body):
    _start(client)
    assert client.post("/api/admin/bots", json=body, headers=_admin(client)).status_code == 400


def test_bots_need_galaxies(app, client):
    response = client.post("/api/admin/bots", json={"total": 2}, headers=_admin(client))
    assert response.status_code == 400 and "galaxies" in response.get_json()["message"]


def test_the_round_summary_counts_players_and_bots(app, client):
    _start(client, num_galaxies=7, cluster_size=5)
    _make_kingdom(client, _player(client), "Counted")
    client.post("/api/admin/bots", json={"total": 2}, headers=_admin(client))

    summary = client.get("/api/admin/round", headers=_admin(client)).get_json()

    assert (summary["galaxies"], summary["clusters"], summary["players"], summary["bots"]) == (7, 2, 1, 2)
    assert summary["cluster_size"] == 5 and summary["phase"] == "running"
