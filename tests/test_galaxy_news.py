"""What reaches galaxy and universe news: primitives, galaxymates' attacks, deaths, joins, galaxy politics, elections."""
import json

import pytest

import untitledapp.misc as uam
import untitledapp.refresh as refresh
from tests.test_attack import TARGET_ID, _attack, _attack_primitives, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _set_up_kingdom
from tests.test_no_locks import _election_state, _together, _universe_votes
from tests.test_politics import _auth, _galaxy_politics


def _galaxy_news(galaxy):
    return _get(f"/galaxy/{galaxy}/news")["news"]


def _two_galaxymates_and_a_target():
    """Kingdoms 1 and 3 share galaxy 1; kingdom 2 (the target) is in galaxy 2."""
    _set_up_two_kingdoms(attacker_attack=100000)
    _set_up_kingdom(money=0, kd_id="3")
    _create_item("galaxies", {"galaxies": {"1": [KD_ID, "3"], "2": [TARGET_ID]}})
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Alpha", TARGET_ID: "Bravo", "3": "Charlie"}})


def test_an_attack_on_primitives_tells_the_galaxy_when_the_generals_are_home(app, client, jwt1):
    _two_galaxymates_and_a_target()

    assert _attack_primitives(client, jwt1).status_code == 200

    (line,) = _galaxy_news("1")
    assert line["kind"] == "primitives" and line["from"] == KD_ID
    assert "attacked primitives and gained" in line["news"] and "1 general out, back in " in line["news"]
    assert "epoch" not in line["news"]
    assert _galaxy_news("2") == []


def test_the_galaxy_news_line_for_primitives_gives_the_spread_of_return_times():
    import datetime
    import untitledapp.conquer as conquer

    now = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
    generals = [{"return_time": (now + datetime.timedelta(hours=hours)).isoformat()} for hours in (2, 3)]
    assert conquer._primitives_galaxy_news("Alpha", 40, generals, now) == (
        "Alpha attacked primitives and gained 40 stars. 2 generals out, back in 2 hours to 3 hours.")


def test_an_attack_is_unread_galaxy_news_for_the_attackers_galaxymates_too(app, client, jwt1):
    _two_galaxymates_and_a_target()

    assert _attack(client, jwt1).status_code == 200

    assert [line["kind"] for line in _galaxy_news("1")] == ["attack"]
    assert _get("/kingdom/3/notifs")["news_galaxy"] == 1
    assert _get(f"/kingdom/{KD_ID}/notifs")["news_galaxy"] == 0  # not for the attacker
    assert _get(f"/kingdom/{TARGET_ID}/notifs")["news_galaxy"] == 1


def test_a_death_is_galaxy_news_naming_the_killer(app):
    _two_galaxymates_and_a_target()

    with app.test_request_context():
        uam._mark_kingdom_death(TARGET_ID, killer=KD_ID)
        uam._mark_kingdom_death("3")

    assert [line["news"] for line in _galaxy_news("2")] == ["Bravo has died, killed by Alpha"]
    assert [line["news"] for line in _galaxy_news("1")] == ["Charlie has died"]
    assert _get(f"/kingdom/{KD_ID}/notifs")["news_galaxy"] == 1


def test_a_new_leader_and_a_new_policy_are_galaxy_news(app, client, jwt1, jwt2):
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID, "2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics())
    _create_item("galaxy_news_1:1", {"news": []})
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Alpha", "2": "Bravo"}})

    assert client.post("/api/galaxypolitics/leader", json={"selected": "2"}, headers=_auth(jwt1)).status_code == 200
    # A second vote for the same leader changes nothing, so it is not news.
    assert client.post("/api/galaxypolitics/leader", json={"selected": "2"}, headers=_auth(jwt2)).status_code == 200
    response = client.post("/api/galaxypolitics/policies", json={"policy": "policy_1", "option": "option_1"},
                           headers=_auth(jwt1))
    assert response.status_code == 200, response.get_json()

    news = [line["news"] for line in _galaxy_news("1:1")]
    assert len(news) == 2 and news[1] == "Bravo is now the galaxy leader"
    assert news[0].startswith("The galaxy voted for the ") and news[0].endswith(" policy")
    assert _get("/kingdom/2/notifs")["news_galaxy"] == 2


@pytest.fixture
def new_galaxy(app, client):
    from tests.test_bots import _kingdoms_starting_past_any_used_id

    _set_up_kingdom(money=0)
    _kingdoms_starting_past_any_used_id()
    _create_item("galaxies", {"galaxies": {"1:1": []}})
    _create_item("galaxy_news_1:1", {"news": []})


def test_a_player_setting_up_a_kingdom_is_galaxy_news(app, client, new_galaxy):
    from tests.test_users import _add_user

    _add_user(app, "joiner")
    token = client.post("/api/login", json={"username": "joiner", "password": "pw"}).get_json()["accessToken"]
    response = client.post("/api/createkingdom", json={"kdName": "Newcomer", "preset": "attacker"},
                           headers=_auth(token))

    assert response.status_code == 200, response.get_json()
    assert [line["news"] for line in _galaxy_news("1:1")] == ["Newcomer joined the galaxy"]


def test_a_bot_joining_is_galaxy_news_too(app, new_galaxy):
    import untitledapp.bots as bots

    with app.test_request_context():
        bots.create_bot("Botty", next(iter(bots.ARCHETYPES)))

    assert [line["news"] for line in _galaxy_news("1:1")] == ["Botty joined the galaxy"]


def test_an_election_opening_and_closing_is_universe_news_once(app):
    stale_state = _election_state()
    _create_item("universe_votes", _universe_votes())
    _create_item("universe_news", {"news": []})

    def open_election(_):
        with app.app_context():
            refresh._begin_election(json.loads(json.dumps(stale_state)))

    _together(4, open_election)
    opened = _get("/state")
    with app.app_context():
        refresh._resolve_election(json.loads(json.dumps(opened)))

    news = [line["news"] for line in _get("/universenews")["news"]]
    assert len(news) == 2
    assert news[1].startswith("A universe election has begun. Voting closes in ")
    assert news[0].startswith("The universe election is over. The universe has chosen ")
