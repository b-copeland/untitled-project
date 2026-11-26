"""Empire news (#176): each empire event lands in the news of the empires involved, and only their members read it."""
import datetime

from tests.test_concurrency import KD_ID, _create_item, _get, _set_up_kingdom
from tests.test_efficiency import calls  # noqa: F401 (a fixture)
from tests.test_politics import _at_war, _auth, _empire_politics, _galaxy_politics, _two_empires


def _news(empire):
    return [line["news"] for line in _get(f"/empire/{empire}/news")["news"]]


def _empty_news(*empires):
    for empire in empires:
        _create_item(f"empire_news_{empire}", {"news": []})


def test_a_member_reads_the_empire_news_and_a_galaxy_outside_any_empire_reads_nothing(app, client, jwt1, jwt2):
    _two_empires()
    _create_item("empire_news_1", {"news": [{"time": "2030-01-01T00:00:00+00:00", "news": "Hello"}]})
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"], "1:3": ["3"]}})
    _create_item("empires", {"empires": {"1": {"name": "One", "galaxies": ["1:1"]}}})

    assert [line["news"] for line in client.get("/api/empirenews", headers=_auth(jwt1)).get_json()] == ["Hello"]
    assert client.get("/api/empirenews", headers=_auth(jwt2)).get_json() == []


def test_denouncing_and_declaring_war_are_news_for_both_empires_and_the_universe(app, client, jwt1):
    _two_empires()
    _empty_news("1", "2")

    assert client.post("/api/empire/2/denounce", headers=_auth(jwt1)).status_code == 200
    assert client.post("/api/empire/2/declare", headers=_auth(jwt1)).status_code == 200

    expected = ["One declared a surprise war on Two", "One has denounced Two"]
    assert _news("1") == expected and _news("2") == expected
    assert [line["news"] for line in _get("/universenews")["news"]] == expected


def test_a_surrender_ends_the_war_in_both_empires_news_and_the_universe(app, client, jwt1):
    _at_war(surrender_offers_received=[{"empire": "2", "type": "stars", "value": 0.1}])
    _empty_news("1", "2")
    _create_item("universe_news", {"news": []})

    response = client.post("/api/empire/2/acceptsurrenderoffer", json={"type": "stars", "value": 0.1}, headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    expected = "Two surrendered to One, giving up 10% of its stars. The war is over"
    assert _news("1") == [expected] and _news("2") == [expected]
    assert [line["news"] for line in _get("/universenews")["news"]] == [expected]


def _galaxy_outside_an_empire():
    """Kingdom 1 leads galaxy 1:1, in no empire; empire 2 is galaxy 1:2, led by kingdom 2."""
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("galaxy_votes_1:2", _galaxy_politics(leader="2"))
    _create_item("empires", {"empires": {"2": {"name": "Two", "galaxies": ["1:2"], "war": [], "peace": {},
                                                 "denounced": "", "aggression": {}, "aggression_max": 100}}})
    _create_item("empire_politics_2", _empire_politics("1:2"))
    _empty_news("2")


def test_joining_by_request_is_news_for_the_empire(app, client, jwt1, jwt2):
    _galaxy_outside_an_empire()

    assert client.post("/api/empire/2/join", headers=_auth(jwt1)).status_code == 200
    assert client.post("/api/galaxy/1:1/accept", headers=_auth(jwt2)).status_code == 200

    assert _news("2") == ["Galaxy 1:1 joined the empire", "Galaxy 1:1 asked to join the empire"]


def test_joining_by_invitation_is_news_for_the_empire(app, client, jwt1, jwt2):
    _galaxy_outside_an_empire()

    assert client.post("/api/galaxy/1:1/invite", headers=_auth(jwt2)).status_code == 200
    assert client.post("/api/empire/2/acceptinvite", headers=_auth(jwt1)).status_code == 200

    assert _news("2") == ["Galaxy 1:1 accepted the invitation and joined the empire",
                           "The empire invited galaxy 1:1 to join"]


def test_leaving_is_news_for_the_galaxies_that_stay_and_names_the_new_ruler(app, client, jwt1):
    _set_up_kingdom(money=0)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("empires", {"empires": {"1": {"galaxies": ["1:1", "1:2"], "aggression": {}}}})
    _create_item("empire_politics_1", _empire_politics("1:1"))
    _empty_news("1")

    assert client.post("/api/leaveempire", headers=_auth(jwt1)).status_code == 200

    assert _news("1") == ["Galaxy 1:1 left the empire. Galaxy 1:2 now rules it"]


def test_founding_an_empire_is_its_first_news(app, client, jwt1, backend):
    _set_up_kingdom(money=0)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=KD_ID))
    _create_item("empires", {"empires": {}})
    if backend is not None:  # see test_a_double_click_on_create_empire_makes_one_empire
        for doc_id in [d for d in backend.docs if d.startswith(("empire_politics_", "empire_news_"))]:
            del backend.docs[doc_id]

    assert client.post("/api/empire", json={"empireName": "Dawn"}, headers=_auth(jwt1)).status_code == 201

    (empire,) = _get("/empires")["empires"]
    assert _news(empire) == ["Galaxy 1:1 founded Dawn"]


def test_wars_by_aggression_in_one_tick_post_once_to_each_document(app, calls):
    import untitledapp.refresh as refresh

    empire = {"galaxies": [], "war": [], "peace": {}, "denounced": "", "denounced_expires": "",
              "surprise_war_penalty": False, "aggression_max": 100}
    _create_item("empires", {"empires": {
        "1": {**empire, "name": "One", "aggression": {"2": 500, "3": 500}},
        "2": {**empire, "name": "Two", "aggression": {}},
        "3": {**empire, "name": "Three", "aggression": {}},
    }, "last_update": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    _empty_news("1", "2", "3")
    _create_item("universe_news", {"news": []})
    _create_item("galaxies", {"galaxies": {}})

    with app.test_request_context():
        calls.clear()
        refresh._resolve_empires({"networth": {}}, datetime.datetime.now(datetime.timezone.utc))

    assert sorted(_news("1")) == ["One declared war by aggression on Three", "One declared war by aggression on Two"]
    assert _news("2") == ["One declared war by aggression on Two"]
    assert _news("3") == ["One declared war by aggression on Three"]
    assert len(_get("/universenews")["news"]) == 2
    patches = [path for method, path in calls if method == "PATCH" and path.endswith("news")]
    assert sorted(patches) == ["/empire/1/news", "/empire/2/news", "/empire/3/news", "/universenews"]


def test_marking_and_removing_a_target_is_empire_news(app, client, jwt1):
    _at_war()
    _empty_news("1", "2")
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Alpha", "2": "Bravo"}})

    marked = client.post("/api/empiretargets/add", json={"target": "2", "actions": {"successful_attacks": 1}},
                         headers=_auth(jwt1))
    assert marked.status_code == 200, marked.get_json()
    assert client.post("/api/empiretargets/2/remove", headers=_auth(jwt1)).status_code == 200

    assert _news("1") == ["Alpha removed the target Bravo. Its spoils fund paid out nothing",
                           "Alpha marked Bravo as a target"]
    assert _news("2") == []  # the enemy is not told


def test_the_news_of_an_ended_target_says_why_and_what_was_paid():
    import untitledapp.targets as targets

    shares = {"1": {"stars": 10, "money": 1500}, "4": {"stars": 2, "money": 0}}
    assert targets.ended_news("killed", "Bravo", None, shares) == (
        "The target Bravo is dead. Its spoils fund paid 12 stars and 1,500 money to 2 kingdom(s)")
    assert targets.ended_news("war_ended", "Bravo", None, {}) == (
        "The target Bravo ended with the war. Its spoils fund paid out nothing")


def test_a_galaxy_can_ask_and_cancel_only_so_many_times_an_hour(app, client, jwt1):
    """Asking to join and cancelling is free and posts empire news: a loop of it must stop (issue #219)."""
    import untitledapp.shared as uas
    _galaxy_outside_an_empire()
    limit = uas.GAME_CONFIG["GALAXY_DIPLOMACY_ACTIONS_PER_HOUR"]

    statuses = []
    for i in range(limit + 2):
        path = "/api/empire/2/join" if i % 2 == 0 else "/api/empire/2/canceljoin"
        statuses.append(client.post(path, headers=_auth(jwt1)))

    assert [response.status_code for response in statuses[:limit]] == [200] * limit
    refused = statuses[limit]
    assert refused.status_code == 400 and "an hour" in refused.get_json()["message"]
    assert len(_news("2")) == limit // 2


def test_the_hourly_allowance_frees_up_as_actions_age(app, client, jwt1):
    import untitledapp.shared as uas
    _galaxy_outside_an_empire()
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=61)).isoformat()
    _create_item("galaxy_votes_1:1", {**_galaxy_politics(leader=KD_ID),
                                     "diplomacy_actions": [old] * uas.GAME_CONFIG["GALAXY_DIPLOMACY_ACTIONS_PER_HOUR"]})

    assert client.post("/api/empire/2/join", headers=_auth(jwt1)).status_code == 200
    assert _get("/galaxy/1:1/politics")["diplomacy_actions"] != [old] * uas.GAME_CONFIG["GALAXY_DIPLOMACY_ACTIONS_PER_HOUR"]
    assert len(_get("/galaxy/1:1/politics")["diplomacy_actions"]) == 1


def test_a_join_request_to_an_empire_that_does_not_exist_is_refused(app, client, jwt1):
    _galaxy_outside_an_empire()
    assert client.post("/api/empire/9/join", headers=_auth(jwt1)).status_code == 404  # politics._known_targets
    assert client.post("/api/empire/2/canceljoin", headers=_auth(jwt1)).status_code == 400
