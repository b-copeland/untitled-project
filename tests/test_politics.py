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


def _clock(monkeypatch, hours_from_now=0.0):
    """Moves the vote routes' clock forward, so a cooldown can pass without waiting."""
    start = datetime.datetime.now(datetime.timezone.utc)
    monkeypatch.setattr(uap, "_now", lambda: start + datetime.timedelta(hours=hours_from_now))


def _cooldown_hours():
    return uas.GAME_CONFIG["BASE_GALAXY_VOTE_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600


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


ROUND = ["growth_doctrine", "industry", "arsenal", "home_front"]


def _play_policies(policies=ROUND):
    """The round's galaxy policies, written into the state the setups made."""
    state = _get("/state")
    _create_item("state", {"state": {**state["state"], "galaxy_policies": policies}})


def test_galaxy_policy_votes_from_two_players_at_once_are_both_kept_and_switch_nothing_yet(app, client, jwt1, jwt2):
    _two_player_galaxy()
    _play_policies()

    responses = _run_together(app, 2, lambda c, i: c.post(
        "/api/galaxypolitics/policies", json={"policy": "growth_doctrine", "option": "expansionist"},
        headers=_auth([jwt1, jwt2][i])))

    assert [r.status_code for r in responses] == [200, 200]
    stored = _get("/galaxy/1:1/politics")
    assert stored["policy_votes"]["growth_doctrine"] == {KD_ID: "expansionist", "2": "expansionist"}
    # A vote does not switch the policy: the next tally does.
    assert stored["policy_active"] == {}
    page = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    growth = next(policy for policy in page["policies"] if policy["key"] == "growth_doctrine")
    assert growth["active"] is None and growth["my_vote"] == "expansionist"
    assert {option["key"]: option["votes"] for option in growth["options"]} == {"expansionist": 2, "raiders": 0}


def _policy_vote(client, token, option, policy="growth_doctrine"):
    return client.post("/api/galaxypolitics/policies", json={"policy": policy, "option": option}, headers=_auth(token))


def _leader_vote(client, token, selected):
    return client.post("/api/galaxypolitics/leader", json={"selected": selected}, headers=_auth(token))


def test_a_policy_vote_can_change_at_once_and_be_withdrawn(app, client, jwt1, monkeypatch):
    _two_player_galaxy()
    _play_policies()
    assert _policy_vote(client, jwt1, "expansionist").status_code == 200
    changed = _policy_vote(client, jwt1, "raiders")
    assert changed.status_code == 200, changed.get_json()  # no cooldown: the tally weighs votes by time instead
    assert "next tally" in changed.get_json()["message"]
    assert _get("/galaxy/1:1/politics")["policy_votes"]["growth_doctrine"] == {KD_ID: "raiders"}
    withdrawn = _policy_vote(client, jwt1, "")
    assert withdrawn.status_code == 200 and "withdrawn" in withdrawn.get_json()["message"]
    assert _get("/galaxy/1:1/politics")["policy_votes"]["growth_doctrine"] == {}


def test_voting_what_it_already_is_writes_nothing(app, client, jwt1, monkeypatch):
    _two_player_galaxy()
    _play_policies()
    assert _policy_vote(client, jwt1, "expansionist").status_code == 200
    before = _get("/galaxy/1:1/politics")
    _clock(monkeypatch, 1)
    assert _policy_vote(client, jwt1, "expansionist").status_code == 200
    after = _get("/galaxy/1:1/politics")
    assert after["policy_updated"] == before["policy_updated"]


@pytest.mark.parametrize("body, message", [
    ({"policy": "economy", "option": "mining_guilds"}, "Economy is not one of this round's policies"),
    ({"policy": "nonsense", "option": "x"}, "Choose one of this round's policies"),
    ({"policy": "growth_doctrine", "option": "warlike"}, "Choose one of the options of Growth Doctrine"),
    ({"option": "expansionist"}, "Choose a policy and one of its options"),
    ({"policy": "growth_doctrine", "option": 3}, "Choose a policy and one of its options"),
])
def test_a_vote_for_something_this_round_does_not_play_is_refused(app, client, jwt1, body, message):
    _two_player_galaxy()
    _play_policies()
    refused = client.post("/api/galaxypolitics/policies", json=body, headers=_auth(jwt1))
    assert refused.status_code == 400 and refused.get_json()["message"] == message
    assert not _get("/galaxy/1:1/politics").get("policy_votes")


def test_a_round_made_before_the_draw_plays_the_first_policies(app, client, jwt1):
    _two_player_galaxy()  # its state has no galaxy_policies
    page = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    assert [policy["key"] for policy in page["policies"]] == list(uas.GALAXY_POLICIES)[:uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"]]
    assert _policy_vote(client, jwt1, "expansionist").status_code == 200


def test_the_page_shows_the_rounds_policies_the_next_tally_and_only_the_leader_vote_has_a_wait(app, client, jwt1):
    _two_player_galaxy()
    _play_policies()
    page = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    assert [policy["key"] for policy in page["policies"]] == ROUND
    arsenal = next(policy for policy in page["policies"] if policy["key"] == "arsenal")
    assert [option["name"] for option in arsenal["options"]] == ["Silo Programme", "Aegis"]
    assert arsenal["options"][1]["desc"] == "Missile shields cost 50% less fuel"
    assert page["tally_hours"] == uas.GAME_CONFIG["GALAXY_POLICY_TALLY_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600
    next_tally = datetime.datetime.fromisoformat(page["next_tally"])
    now = datetime.datetime.now(datetime.timezone.utc)
    assert now < next_tally <= now + datetime.timedelta(hours=page["tally_hours"])
    assert page["vote_unlocks_at"] == {"leader": None}
    assert page["vote_cooldown_hours"] == _cooldown_hours()
    _leader_vote(client, jwt1, KD_ID)
    _leader_vote(client, jwt1, "2")
    later = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    assert later["vote_unlocks_at"]["leader"] is not None  # the vote holds for the cooldown, so the change was refused
    assert later["votes"]["leader"] == {KD_ID: KD_ID} and later["leader"] == KD_ID


def test_a_vote_held_through_a_tally_makes_the_policy_active_and_prices_follow(app, client, jwt1, monkeypatch):
    _two_player_galaxy()
    _play_policies()
    _clock(monkeypatch, -7)  # it voted seven hours ago, so a tally has passed since
    assert _policy_vote(client, jwt1, "industrialists", policy="industry").status_code == 200
    page = client.get("/api/galaxypolitics", headers=_auth(jwt1)).get_json()
    assert next(policy for policy in page["policies"] if policy["key"] == "industry")["active"] == "industrialists"
    structures = client.get("/api/structures", headers=_auth(jwt1)).get_json()
    base = uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"]))
    assert structures["price"] == pytest.approx(base * 0.85)
    modifiers = client.get("/api/modifiers", headers=_auth(jwt1)).get_json()
    assert modifiers["modifiers"] == {"structure_cost": pytest.approx(-0.15)}
    assert modifiers["texts"] == {"structure_cost": "Structures cost 15% less"}


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
