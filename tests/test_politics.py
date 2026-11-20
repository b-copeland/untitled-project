"""Galaxy and empire politics, including players acting at the same moment."""
import datetime
import re

import pytest

import untitledapp.politics as uap
import untitledapp.shared as uas
from tests.test_attack import _in_threads
from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom  # noqa: F401


def _galaxy_politics(**fields):
    return {
        "votes": {"policy_1": {}, "policy_2": {}, "leader": {}},
        "active_policies": [], "leader": "", "policy_1_winner": "", "policy_2_winner": "",
        "empire_invitations": [], "empire_join_requests": [], **fields,
    }


def _empire_politics(leader, **fields):
    return {"empire_invitations": [], "empire_join_requests": [], "leader": leader, **fields}


def _two_player_galaxy():
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID, "2"]}})  # after the setups, which reset it
    _create_item("galaxy_votes_1:1", _galaxy_politics())
    _create_item("empires", {"empires": {}})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_galaxymates_voting_for_a_leader_at_the_same_moment_are_both_counted(app, client, jwt1, jwt2):
    _two_player_galaxy()

    def vote(c, i):
        token, choice = [(jwt1, KD_ID), (jwt2, KD_ID)][i % 2]
        return c.post("/api/galaxypolitics/leader", json={"selected": choice}, headers=_auth(token))

    responses = _run_together(app, 8, vote)

    assert [r.status_code for r in responses] == [200] * 8
    votes = _get("/galaxy/1:1/politics")
    assert votes["votes"]["leader"] == {KD_ID: KD_ID, "2": KD_ID}  # both kingdoms' votes survived
    assert votes["leader"] == KD_ID


def test_galaxy_policy_votes_from_two_players_are_both_kept_and_the_winner_is_set_once_decided(app, client, jwt1, jwt2):
    _two_player_galaxy()

    responses = _run_together(app, 2, lambda c, i: c.post(
        "/api/galaxypolitics/policies", json={"policy": "policy_1", "option": "option_1"},
        headers=_auth([jwt1, jwt2][i])))

    assert [r.status_code for r in responses] == [200, 200]
    votes = _get("/galaxy/1:1/politics")
    assert votes["votes"]["policy_1"] == {KD_ID: "1", "2": "1"}
    assert votes["policy_1_winner"] == "1" and "Expansionist" in votes["active_policies"]


def _clock(monkeypatch, hours_from_now=0.0):
    """Moves the vote routes' clock forward, so a cooldown can pass without waiting."""
    start = datetime.datetime.now(datetime.timezone.utc)
    monkeypatch.setattr(uap, "_now", lambda: start + datetime.timedelta(hours=hours_from_now))


def _cooldown_hours():
    return uas.GAME_CONFIG["BASE_GALAXY_VOTE_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600


def _policy_vote(client, token, option, policy="policy_1"):
    return client.post("/api/galaxypolitics/policies", json={"policy": policy, "option": option}, headers=_auth(token))


def _leader_vote(client, token, selected):
    return client.post("/api/galaxypolitics/leader", json={"selected": selected}, headers=_auth(token))


def test_a_changed_policy_vote_is_locked_for_the_cooldown(app, client, jwt1, monkeypatch):
    _two_player_galaxy()
    assert _policy_vote(client, jwt1, "option_1").status_code == 200  # the first vote is free
    _clock(monkeypatch, 1)
    refused = _policy_vote(client, jwt1, "option_2")
    assert refused.status_code == 400, refused.get_json()
    assert re.search(r"can change it again in (2 hours|1 hour 59 minutes)\.", refused.get_json()["message"])
    assert "epoch" not in refused.get_json()["message"].lower()
    assert _get("/galaxy/1:1/politics")["votes"]["policy_1"] == {KD_ID: "1"}

    _clock(monkeypatch, _cooldown_hours() + 0.01)
    assert _policy_vote(client, jwt1, "option_2").status_code == 200
    assert _get("/galaxy/1:1/politics")["votes"]["policy_1"] == {KD_ID: "2"}
    _clock(monkeypatch, _cooldown_hours() + 0.02)  # that change started the wait again
    assert _policy_vote(client, jwt1, "option_1").status_code == 400


def test_each_vote_and_each_kingdom_has_its_own_cooldown(app, client, jwt1, jwt2):
    _two_player_galaxy()
    assert _policy_vote(client, jwt1, "option_1").status_code == 200
    assert _policy_vote(client, jwt1, "option_2").status_code == 400
    assert _policy_vote(client, jwt1, "option_1", policy="policy_2").status_code == 200  # another vote of the same kingdom
    assert _policy_vote(client, jwt2, "option_2").status_code == 200  # another kingdom
    assert _leader_vote(client, jwt1, KD_ID).status_code == 200
    assert _leader_vote(client, jwt1, "2").status_code == 400
    assert _get("/galaxy/1:1/politics")["votes"]["leader"] == {KD_ID: KD_ID}


def test_voting_what_it_already_is_changes_nothing_and_starts_no_wait(app, client, jwt1, monkeypatch):
    _two_player_galaxy()
    assert _leader_vote(client, jwt1, KD_ID).status_code == 200
    stamp = _get("/galaxy/1:1/politics")["vote_changed"]["leader"][KD_ID]
    _clock(monkeypatch, 1)
    assert _leader_vote(client, jwt1, KD_ID).status_code == 200
    assert _get("/galaxy/1:1/politics")["vote_changed"]["leader"][KD_ID] == stamp


def test_a_changed_leader_vote_is_locked_too(app, client, jwt1, monkeypatch):
    _two_player_galaxy()
    assert _leader_vote(client, jwt1, KD_ID).status_code == 200
    refused = _leader_vote(client, jwt1, "2")
    assert refused.status_code == 400 and "changed this vote recently" in refused.get_json()["message"]
    _clock(monkeypatch, _cooldown_hours() + 0.01)
    assert _leader_vote(client, jwt1, "2").status_code == 200


def test_the_page_is_told_when_each_vote_can_change(app, client, jwt1):
    _two_player_galaxy()
    first = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    assert first["vote_unlocks_at"] == {"leader": None, "policy_1": None, "policy_2": None}
    assert first["vote_cooldown_hours"] == _cooldown_hours()
    _policy_vote(client, jwt1, "option_1")
    later = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    assert later["vote_unlocks_at"]["policy_1"] is not None
    assert later["vote_unlocks_at"]["policy_2"] is None and later["vote_unlocks_at"]["leader"] is None


def test_join_requests_from_two_galaxies_to_one_empire_are_both_recorded(app, client, jwt1, jwt2):
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"], "1:3": ["3"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("galaxy_votes_1:2", _galaxy_politics(leader="2"))
    _create_item("galaxy_votes_1:3", _galaxy_politics())
    _create_item("empires", {"empires": {"e1": {"galaxies": ["1:3"], "aggression": {}}}})
    _create_item("empire_politics_e1", _empire_politics("1:3"))

    responses = _run_together(app, 2, lambda c, i: c.post(
        "/api/empire/e1/join", headers=_auth([jwt1, jwt2][i])))

    assert [r.status_code for r in responses] == [200, 200], [r.get_json() for r in responses]
    assert sorted(_get("/empire/e1/politics")["empire_join_requests"]) == ["1:1", "1:2"]
    assert _get("/galaxy/1:1/politics")["empire_join_requests"] == ["e1"]


def test_repeating_a_join_request_does_not_duplicate_it(app, client, jwt1):
    _set_up_kingdom(money=0)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:3": ["3"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("empires", {"empires": {"e1": {"galaxies": ["1:3"], "aggression": {}}}})
    _create_item("empire_politics_e1", _empire_politics("1:3"))

    responses = _run_together(app, 4, lambda c, i: c.post("/api/empire/e1/join", headers=_auth(jwt1)))

    assert [r.status_code for r in responses] == [200] * 4
    assert _get("/empire/e1/politics")["empire_join_requests"] == ["1:1"]


def test_a_galaxy_accepting_two_invitations_at_once_joins_only_one_empire(app, client, jwt1):
    _set_up_kingdom(money=0)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"], "1:3": ["3"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID, empire_invitations=["e1", "e2"]))
    _create_item("empires", {"empires": {"e1": {"galaxies": ["1:2"], "aggression": {}},
                                          "e2": {"galaxies": ["1:3"], "aggression": {}}}})
    _create_item("empire_politics_e1", _empire_politics("1:2", empire_invitations=["1:1"]))
    _create_item("empire_politics_e2", _empire_politics("1:3", empire_invitations=["1:1"]))

    responses = _run_together(app, 2, lambda c, i: c.post(
        f"/api/empire/e{i + 1}/acceptinvite", headers=_auth(jwt1)))

    assert sorted(r.status_code for r in responses) == [200, 400], [r.get_json() for r in responses]
    empires = _get("/empires")["empires"]
    assert sum("1:1" in empire["galaxies"] for empire in empires.values()) == 1


def test_leaving_an_empire_removes_the_galaxy_and_hands_over_the_leadership(app, client, jwt1):
    _set_up_kingdom(money=0)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("empires", {"empires": {"e1": {"galaxies": ["1:1", "1:2"], "aggression": {}}}})
    _create_item("empire_politics_e1", _empire_politics("1:1"))

    response = client.post("/api/leaveempire", headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    assert _get("/empires")["empires"]["e1"]["galaxies"] == ["1:2"]
    assert _get("/empire/e1/politics")["leader"] == "1:2"


def test_a_galaxy_can_not_leave_its_empire_during_a_war(app, client, jwt1):
    _at_war()
    response = client.post("/api/leaveempire", headers=_auth(jwt1))
    assert response.status_code == 400 and "at war" in response.get_json()["message"]
    assert _get("/empires")["empires"]["e1"]["galaxies"] == ["1:1"]


def test_a_war_declared_as_the_galaxy_leaves_still_holds_it(app):
    _at_war()
    with app.test_request_context():
        with pytest.raises(uap.occ.Rejected):
            uap._change_empire_galaxies("e1", remove="1:1", leave_check=uap._refuse_leaving)
    assert _get("/empires")["empires"]["e1"]["galaxies"] == ["1:1"]


def _two_empires():
    _set_up_kingdom(money=0)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    empire = {"galaxies": [], "war": [], "peace": {}, "denounced": "", "aggression": {}, "aggression_max": 100}
    _create_item("empires", {"empires": {"e1": {**empire, "name": "One", "galaxies": ["1:1"]},
                                          "e2": {**empire, "name": "Two", "galaxies": ["1:2"]}}})
    _create_item("empire_politics_e1", _empire_politics("1:1"))
    _create_item("empire_politics_e2", _empire_politics("1:2"))
    _create_item("universe_news", {"news": []})


@pytest.mark.parametrize("repeat", range(3))  # the overlap is down to timing
def test_racing_denouncements_denounce_once(app, client, jwt1, repeat):
    _two_empires()

    responses = _run_together(app, 6, lambda c, i: c.post("/api/empire/e2/denounce", headers=_auth(jwt1)))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 5, [r.get_json() for r in responses]
    e1 = _get("/empires")["empires"]["e1"]
    assert e1["denounced"] == "e2" and e1["aggression"]["e2"] > 0
    assert len(_get("/universenews")["news"]) == 1


@pytest.mark.parametrize("repeat", range(3))
def test_racing_war_declarations_declare_war_once(app, client, jwt1, repeat):
    _two_empires()

    responses = _run_together(app, 6, lambda c, i: c.post("/api/empire/e2/declare", headers=_auth(jwt1)))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 5, [r.get_json() for r in responses]
    empires = _get("/empires")["empires"]
    assert empires["e1"]["war"] == ["e2"] and empires["e2"]["war"] == ["e1"]
    assert empires["e1"]["surprise_war_penalty"] is True
    assert len(_get("/universenews")["news"]) == 1


def _at_war(**e1_politics):
    """Empire e1 (galaxy 1:1, led by kingdom 1) at war with e2 (galaxy 1:2, led by kingdom 2)."""
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("galaxy_votes_1:2", _galaxy_politics(leader="2"))
    empire = {"war": [], "peace": {}, "denounced": "", "aggression": {}, "aggression_max": 100}
    _create_item("empires", {"empires": {"e1": {**empire, "name": "One", "galaxies": ["1:1"], "war": ["e2"],
                                                 "aggression": {"e2": 50}},
                                          "e2": {**empire, "name": "Two", "galaxies": ["1:2"], "war": ["e1"]}}})
    surrender_lists = {"surrender_offers_sent": [], "surrender_offers_received": [],
                       "surrender_requests_sent": [], "surrender_requests_received": []}
    _create_item("empire_politics_e1", _empire_politics("1:1", **{**surrender_lists, **e1_politics}))
    _create_item("empire_politics_e2", _empire_politics("1:2", **surrender_lists))


def test_a_surrender_request_is_recorded_on_both_sides_and_can_be_cancelled(app, client, jwt1):
    _at_war()
    body = {"type": "stars", "value": 0.05}

    assert client.post("/api/empire/e2/surrenderrequest", json=body, headers=_auth(jwt1)).status_code == 200
    assert _get("/empire/e2/politics")["surrender_requests_received"] == [{**body, "empire": "e1"}]
    assert _get("/empire/e1/politics")["surrender_requests_sent"] == [{**body, "empire": "e2"}]

    assert client.post("/api/empire/e2/cancelsurrenderrequest", json=body, headers=_auth(jwt1)).status_code == 200
    assert _get("/empire/e2/politics")["surrender_requests_received"] == []
    assert _get("/empire/e1/politics")["surrender_requests_sent"] == []


def test_cancelling_one_request_leaves_a_different_one_between_the_same_empires(app, client, jwt1):
    _at_war()
    first, second = {"type": "stars", "value": 0.05}, {"type": "stars", "value": 0.1}
    # a request replaces the earlier one between the same two empires, so make the second from the other side
    client.post("/api/empire/e2/surrenderrequest", json=first, headers=_auth(jwt1))

    client.post("/api/empire/e2/cancelsurrenderrequest", json=second, headers=_auth(jwt1))

    assert _get("/empire/e2/politics")["surrender_requests_received"] == [{**first, "empire": "e1"}]


@pytest.mark.parametrize("repeat", range(3))
def test_racing_acceptances_of_one_surrender_offer_transfer_the_stars_once(app, client, jwt1, jwt2, repeat):
    _at_war(surrender_offers_received=[{"empire": "e2", "type": "stars", "value": 0.1}])
    stars0 = {kd: _get(f"/kingdom/{kd}")["stars"] for kd in (KD_ID, "2")}
    body = {"type": "stars", "value": 0.1}

    responses = _run_together(app, 6, lambda c, i: c.post(
        "/api/empire/e2/acceptsurrenderoffer", json=body, headers=_auth(jwt1)))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 5, [r.get_json() for r in responses]
    lost = int(stars0["2"] * 0.1)
    assert _get("/kingdom/2")["stars"] == stars0["2"] - lost
    assert _get(f"/kingdom/{KD_ID}")["stars"] == stars0[KD_ID] + lost
    empires = _get("/empires")["empires"]
    assert empires["e1"]["war"] == [] and empires["e2"]["war"] == []
    assert "e2" in empires["e1"]["peace"] and "e1" in empires["e2"]["peace"]
    assert empires["e1"]["aggression"]["e2"] == 0
    assert _get("/empire/e1/politics")["surrender_offers_received"] == []


def test_a_double_click_on_create_empire_makes_one_empire(app, client, jwt1, backend):
    """No lock: the function app takes the id with a conditional write and refuses a galaxy already in an empire."""
    _two_player_galaxy()
    # An empire founded by an earlier test leaves empire_politics_0 behind (the reset between tests blanks documents,
    # it does not delete them), and creating the new empire's documents would then fail. Between rounds /resetstate
    # deletes them.
    if backend is not None:
        for doc_id in [d for d in backend.docs if d.startswith(("empire_politics_", "empire_news_"))]:
            del backend.docs[doc_id]
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))

    responses = _run_together(app, 5, lambda c, i: c.post(
        "/api/empire", json={"empireName": "Once"}, headers=_auth(jwt1)))

    assert sorted(r.status_code for r in responses) == [201] + [400] * 4, [r.get_json() for r in responses]
    assert {r.get_json()["message"] for r in responses if r.status_code == 400} == {"You are already part of an Empire"}
    empires = _get("/empires")["empires"]
    assert len(empires) == 1 and next(iter(empires.values()))["galaxies"] == ["1:1"]


# --- how large an empire may grow


def _ten_galaxies(empire_galaxies, networth=None, **leader_politics):
    """Ten galaxies of one kingdom each; ``KD_ID`` leads 1:1, and empire e1 holds ``empire_galaxies``."""
    _set_up_kingdom(money=0)
    galaxies = {f"1:{i}": [KD_ID if i == 1 else str(i)] for i in range(1, 11)}
    _create_item("galaxies", {"galaxies": galaxies})
    for galaxy in galaxies:
        _create_item(f"galaxy_votes_{galaxy}", _galaxy_politics(leader=galaxies[galaxy][0]))
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID, **leader_politics))
    _create_item("scores", {"stars": {}, "networth": {}, "points": {},
                            "galaxy_networth": networth or {galaxy: 100 for galaxy in galaxies}})
    _create_item("empires", {"empires": {"e1": {"galaxies": empire_galaxies, "aggression": {}}}})


def test_an_empire_may_not_grow_past_30_percent_of_the_kingdoms():
    import untitledapp.politics as uap

    members = {f"g{i}": ["k"] for i in range(10)}
    networth = {g: 100 for g in members}
    assert uap.empire_size_problem(["g1"], "g2", members, networth) is None             # two may always ally
    assert uap.empire_size_problem(["g1", "g2"], "g3", members, networth) is None       # 30% of the kingdoms
    assert "kingdoms" in uap.empire_size_problem(["g1", "g2", "g3"], "g4", members, networth)
    assert "networth" in uap.empire_size_problem(["g1", "g2"], "g3", members, {**networth, "g1": 1000})


def test_accepting_an_invitation_that_would_make_the_empire_too_large_is_refused(app, client, jwt1):
    _ten_galaxies(["1:2", "1:3", "1:4"], empire_invitations=["e1"])
    _create_item("empire_politics_e1", _empire_politics("1:2", empire_invitations=["1:1"]))

    response = client.post("/api/empire/e1/acceptinvite", headers=_auth(jwt1))

    assert response.status_code == 400 and "30%" in response.get_json()["message"]
    assert _get("/empires")["empires"]["e1"]["galaxies"] == ["1:2", "1:3", "1:4"]


def test_asking_to_join_an_empire_with_too_much_networth_is_refused(app, client, jwt1):
    _ten_galaxies(["1:2", "1:3"], networth={**{f"1:{i}": 100 for i in range(1, 11)}, "1:2": 1000})
    _create_item("empire_politics_e1", _empire_politics("1:2"))

    response = client.post("/api/empire/e1/join", headers=_auth(jwt1))

    assert response.status_code == 400 and "networth" in response.get_json()["message"]
    assert _get("/empire/e1/politics")["empire_join_requests"] == []


def test_an_empire_with_room_admits_a_galaxy(app, client, jwt1):
    _ten_galaxies(["1:1", "1:3"])
    _create_item("galaxy_votes_1:4", _galaxy_politics(leader="4", empire_join_requests=["e1"]))
    _create_item("empire_politics_e1", _empire_politics("1:1", empire_join_requests=["1:4"]))

    response = client.post("/api/galaxy/1:4/accept", headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    assert _get("/empires")["empires"]["e1"]["galaxies"] == ["1:1", "1:3", "1:4"]
