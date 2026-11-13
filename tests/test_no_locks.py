"""
The steps that the legacy locks used to cover, now that there are none: each is decided against the document as it is
(occ.update), so two refreshes or requests that overlap can not both do it, and none overwrites what landed meanwhile.
"""
import datetime
import json
import threading


import untitledapp.refresh as refresh
import untitledapp.misc as uam
import untitledapp.shared as uas
from untitledapp import REQUESTS_SESSION
from tests.test_concurrency import FUNCTION_URL, KD_ID, _create_item, _get, _set_up_kingdom

NOW = datetime.datetime.now(datetime.timezone.utc)
PAST = (NOW - datetime.timedelta(minutes=5)).isoformat()
FUTURE = (NOW + datetime.timedelta(hours=5)).isoformat()


def _together(count, target):
    gate = threading.Barrier(count)
    results = [None] * count

    def run(i):
        gate.wait()
        results[i] = target(i)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# --- scheduled actions -------------------------------------------------------------------------------------------

def _schedule_kingdom():
    _set_up_kingdom(money=100, schedule=[
        {"time": PAST, "type": "attack", "options": {"target": "2"}},
        {"time": FUTURE, "type": "attack", "options": {"target": "3"}},
    ])


def test_overlapping_ticks_run_a_due_schedule_once(app, monkeypatch):
    _schedule_kingdom()
    ran = []
    monkeypatch.setattr(refresh, "_resolve_schedule_attack", lambda kd, schedule: (ran.append, (schedule["options"]["target"],)))

    def tick(_):
        with app.app_context():
            return refresh._resolve_schedules(KD_ID, NOW)

    results = _together(4, tick)

    assert ran == ["2"]
    assert sorted(results) == [False, False, False, True]
    assert [s["options"]["target"] for s in _get(f"/kingdom/{KD_ID}")["schedule"]] == ["3"]


def test_running_schedules_does_not_overwrite_what_changed_meanwhile(app, monkeypatch):
    """The old step wrote the whole kingdom back from its own copy, undoing anything that landed in between."""
    _schedule_kingdom()

    def an_action_lands_meanwhile(kd, schedule):
        REQUESTS_SESSION.patch(f"{FUNCTION_URL}/kingdom/{KD_ID}", data=json.dumps({"money": 999}))
        return (lambda: None), ()

    monkeypatch.setattr(refresh, "_resolve_schedule_attack", an_action_lands_meanwhile)
    with app.app_context():
        assert refresh._resolve_schedules(KD_ID, NOW) is True
    assert _get(f"/kingdom/{KD_ID}")["money"] == 999


def test_a_schedule_that_can_not_be_prepared_is_dropped_not_retried_forever(app, monkeypatch):
    _schedule_kingdom()

    def broken(kd, schedule):
        raise KeyError("missing option")

    monkeypatch.setattr(refresh, "_resolve_schedule_attack", broken)
    with app.app_context():
        assert refresh._resolve_schedules(KD_ID, NOW) is True
    assert len(_get(f"/kingdom/{KD_ID}")["schedule"]) == 1


# --- elections and history ---------------------------------------------------------------------------------------

def _universe_votes(**option_1_votes):
    return {"votes": {
        "policy_1": {"option_1": dict(option_1_votes), "option_2": {}},
        "policy_2": {"option_1": {}, "option_2": {}},
    }}


def _election_state(**fields):
    state = {"game_start": PAST, "election_start": PAST, "election_end": "", "active_policies": ["old"],
             "next_history": PAST, **fields}
    _create_item("state", {"state": state})
    return {"state": dict(state)}


def test_an_election_is_opened_once_and_a_vote_cast_meanwhile_survives(app):
    stale_state = _election_state()
    _create_item("universe_votes", _universe_votes(**{"5": 3}))
    with app.app_context():
        refresh._begin_election(json.loads(json.dumps(stale_state)))
        assert _get("/universevotes")["votes"]["policy_1"]["option_1"] == {}
        _create_item("universe_votes", _universe_votes(**{"7": 2}))  # a vote in the new election
        # A tick that overlapped the first one, still holding the state from before it opened the election.
        refresh._begin_election(json.loads(json.dumps(stale_state)))

    assert _get("/universevotes")["votes"]["policy_1"]["option_1"] == {"7": 2}
    assert _get("/state")["state"]["election_end"] != ""


def test_overlapping_ticks_open_an_election_once(app):
    stale_state = _election_state()
    _create_item("universe_votes", _universe_votes())  # opening an election clears the votes, so they must exist

    def tick(_):
        with app.app_context():
            refresh._begin_election(json.loads(json.dumps(stale_state)))
            return _get("/state")["state"]["election_end"]

    ends = _together(4, tick)
    assert len(set(ends)) == 1 and ends[0] != ""


def test_an_election_is_closed_once(app):
    end = (NOW - datetime.timedelta(minutes=1)).isoformat()
    stale_state = _election_state(election_end=end)
    _create_item("universe_votes", _universe_votes(**{"5": 3}))

    def tick(_):
        with app.app_context():
            return refresh._resolve_election(json.loads(json.dumps(stale_state)))["state"]["election_start"]

    _together(4, tick)
    stored = _get("/state")["state"]
    assert stored["election_end"] == ""
    # Closed once: the next election starts one results period after this one ended, not several.
    config = uas.GAME_CONFIG
    results = datetime.timedelta(seconds=config["BASE_EPOCH_SECONDS"] * config["BASE_ELECTION_RESULTS_DURATION_MULTIPLIER"])
    assert stored["election_start"] == (datetime.datetime.fromisoformat(end) + results).isoformat()
    assert len(stored["active_policies"]) == 2


def test_overlapping_ticks_take_the_history_mark_once(app):
    _election_state()

    def tick(_):
        with app.app_context():
            return refresh._take_history_mark(NOW)

    assert sorted(_together(5, tick)) == [False] * 4 + [True]


# --- the settings routes -----------------------------------------------------------------------------------------

def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_auto_attack_settings_and_switch(app, client, jwt1):
    _set_up_kingdom(money=100, auto_attack_settings={"pure": 0, "flex": 0})
    refused = client.post("/api/attackprimitives/auto", json={"enabled": True}, headers=_auth(jwt1))
    assert refused.status_code == 400 and "percent" in refused.get_json()["message"]

    assert client.post("/api/attackprimitives/auto", json={"pure": 20}, headers=_auth(jwt1)).status_code == 200
    assert client.post("/api/attackprimitives/auto", json={"enabled": True}, headers=_auth(jwt1)).status_code == 200
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["auto_attack_enabled"] is True and kingdom["auto_attack_settings"]["pure"] == 0.2

    bad = client.post("/api/attackprimitives/auto", json={"pure": "lots"}, headers=_auth(jwt1))
    assert bad.status_code == 400


def test_auto_rob_settings_and_switch(app, client, jwt1):
    _set_up_kingdom(money=100, auto_rob_settings={"drones": 0, "keep": 0, "shielded": False})
    assert client.post("/api/robprimitives/auto", json={"enabled": True}, headers=_auth(jwt1)).status_code == 400
    assert client.post("/api/robprimitives/auto", json={"drones": 50, "keep": 2}, headers=_auth(jwt1)).status_code == 200
    assert client.post("/api/robprimitives/auto", json={"enabled": True}, headers=_auth(jwt1)).status_code == 200
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["auto_rob_enabled"] is True and kingdom["auto_rob_settings"] == {"drones": 0.5, "keep": 2, "shielded": False}


# --- no lock functions are left to call --------------------------------------------------------------------------

def test_the_legacy_lock_functions_are_gone():
    import untitledapp

    for name in ("acquire_lock", "acquire_locks", "release_lock", "release_locks_by_id", "release_locks_by_name"):
        assert not hasattr(uam, name), name
    assert not hasattr(untitledapp, "Locks")
