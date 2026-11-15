"""
The user store (api/untitledapp/users.py): users in Cosmos documents through the function app.

Also the helpers other tests use to make and read users: ``_add_user`` and ``_stored_user``.
"""
import datetime

import pendulum
import pytest

import untitledapp.refresh as refresh
import untitledapp.request_cache as request_cache
from untitledapp import REQUESTS_SESSION, User
from untitledapp.users import username_key
from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom

_hashes = {}


def _add_user(app, username, password="pw", **fields):
    """A user straight into the store, with the defaults a sign-up gives. Returns its id."""
    with app.app_context():
        if password not in _hashes:
            _hashes[password] = app.extensions["praetorian"].hash_password(password)
        fields = {"roles": "operator", "kd_created": False, "is_active": True, **fields}
        return User.create(username, _hashes[password], **fields).id


def _stored_user(app, username):
    """The user as stored now, or None."""
    with app.app_context():
        return User.lookup(username)


def _login(client, username, password):
    return client.post("/api/login", json={"username": username, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- the documents -----------------------------------------------------------------------------------------------

def test_a_sign_up_writes_the_user_the_name_claim_and_the_counter(app, client):
    assert client.post("/api/signup", json={"username": "Docs", "password": "pw"}).status_code == 201

    user_id = _stored_user(app, "Docs").id
    assert user_id == 4  # after admin, user1 and user2
    assert _get(f"/username/{username_key('Docs')}")["user_id"] == user_id
    stored = _get(f"/user/{user_id}")
    assert stored["username"] == "Docs" and stored["id_number"] == user_id and stored["password"] != "pw"
    assert stored["roles"] == "verified" and stored["is_active"] is True and stored["kd_id"] is None
    assert _get("/usercounter")["next_id"] == user_id + 1


def test_the_test_users_keep_their_ids_from_test_to_test(app):
    assert [(user.username, user.id, user.kd_id) for user in _all(app)] == [
        ("admin", 1, None), ("user1", 2, "1"), ("user2", 3, "2"),
    ]


def _all(app):
    with app.app_context():
        return User.all()


def test_lookup_by_username_is_case_sensitive(app, client):
    _add_user(app, "CaseName", password="one")
    _add_user(app, "casename", password="two")

    assert _login(client, "CaseName", "one").status_code == 200
    assert _login(client, "casename", "two").status_code == 200
    assert _login(client, "CaseName", "two").status_code == 401
    assert _login(client, "CASENAME", "one").status_code == 401
    assert _stored_user(app, "CASENAME") is None


def test_names_that_are_not_valid_cosmos_ids_work(app, client):
    name = "a/b?c#d\\ é"
    assert client.post("/api/signup", json={"username": name, "password": "pw"}).status_code == 201
    assert _login(client, name, "pw").status_code == 200


def test_a_name_claim_whose_user_is_someone_else_finds_nobody(app):
    """A claim left pointing at an id that now holds another user (a sign-up before the migration) is ignored."""
    other = _add_user(app, "real_owner")
    _create_item(f"username_{username_key('stale')}", {"user_id": other})
    assert _stored_user(app, "stale") is None


def test_signup_races_make_exactly_one_account(app):
    body = {"username": "racer", "password": "pw"}
    responses = _run_together(app, 6, lambda client, i: client.post("/api/signup", json=body))

    assert sorted(r.status_code for r in responses) == [201] + [400] * 5, [r.get_json() for r in responses]
    assert {r.get_json()["message"] for r in responses if r.status_code == 400} == {"Account already exists"}
    assert [user.username for user in _all(app)].count("racer") == 1
    ids = [user.id for user in _all(app)]
    assert len(ids) == len(set(ids))


def test_different_names_signing_up_at_once_all_get_their_own_id(app):
    responses = _run_together(app, 6, lambda client, i: client.post("/api/signup", json={"username": f"n{i}", "password": "pw"}))

    assert [r.status_code for r in responses] == [201] * 6
    users = {user.username: user.id for user in _all(app)}
    assert {f"n{i}" for i in range(6)} <= set(users)
    assert len(set(users.values())) == len(users)


# --- identify is read once per request ---------------------------------------------------------------------------

def _counting_user_reads(monkeypatch):
    reads = []
    original = REQUESTS_SESSION.request

    def counting(method, url, *args, **kwargs):
        if method.upper() == "GET" and "/user/" in url:
            reads.append(url)
        return original(method, url, *args, **kwargs)

    monkeypatch.setattr(REQUESTS_SESSION, "request", counting)
    return reads


def test_identify_reads_the_user_once_per_request_and_sees_its_own_writes(app, monkeypatch):
    reads = _counting_user_reads(monkeypatch)
    with app.test_request_context(), request_cache.scope():
        for _ in range(5):
            assert User.identify(2).kd_id == KD_ID
        assert len(reads) == 1

        User.identify(2).save(email="new@example.com")
        assert User.identify(2).email == "new@example.com"  # the write dropped the old copy
        assert len(reads) == 3  # plus the read occ.update decides on, and one fresh copy after the write

    with app.test_request_context(), request_cache.scope():
        User.identify(2)
        assert len(reads) == 4  # a new request reads afresh


def test_identify_outside_a_request_always_reads(app, monkeypatch):
    reads = _counting_user_reads(monkeypatch)
    with app.app_context():
        User.identify(2)
        User.identify(2)
    assert len(reads) == 2


def test_an_unknown_or_malformed_id_identifies_nobody(app):
    with app.app_context():
        assert User.identify(999) is None
        assert User.identify("not a number") is None
        assert User.lookup("") is None and User.lookup(None) is None


@pytest.mark.parametrize("path", ["/api/notifs", "/api/kingdom", "/api/kingdomid"])
def test_a_polled_route_reads_the_user_once(app, client, jwt1, monkeypatch, path):
    _set_up_kingdom(money=100)
    reads = _counting_user_reads(monkeypatch)
    assert client.get(path, headers=_auth(jwt1)).status_code == 200
    assert len(reads) == 1


def test_an_action_behind_alive_required_reads_the_user_once(app, client, jwt1, monkeypatch):
    _set_up_kingdom(money=100)
    reads = _counting_user_reads(monkeypatch)
    response = client.post("/api/shields", json={"military": 0}, headers=_auth(jwt1))
    assert response.status_code in (200, 400), response.get_json()
    assert len(reads) == 1


def test_a_dead_kingdom_is_refused_by_alive_required(app, client, jwt1):
    _set_up_kingdom(money=100)
    with app.app_context():
        User.lookup("user1").save(kd_death_date=datetime.datetime.now(datetime.timezone.utc).isoformat())
    response = client.post("/api/shields", json={"military": 0}, headers=_auth(jwt1))
    assert response.status_code == 400 and "dead" in response.get_json()["message"]


# --- disabled users ----------------------------------------------------------------------------------------------

def test_a_disabled_user_can_not_log_in_or_refresh(app, client, monkeypatch):
    _add_user(app, "to_disable", password="pw")
    _add_user(app, "still_active", password="pw")
    # A token can only be refreshed once its access part has expired, so hand out tokens that are born expired.
    monkeypatch.setattr(app.extensions["praetorian"], "access_lifespan", pendulum.duration(seconds=-5))
    disabled_token = _login(client, "to_disable", "pw").get_json()["refreshToken"]
    active_token = _login(client, "still_active", "pw").get_json()["refreshToken"]
    monkeypatch.undo()

    admin = _login(client, "admin", "admin").get_json()["accessToken"]
    assert client.post("/api/disable_user", json={"username": "to_disable"}, headers=_auth(admin)).status_code == 200

    assert _login(client, "to_disable", "pw").status_code == 403
    assert client.post("/api/refresh", headers=_auth(disabled_token)).status_code == 403
    assert client.post("/api/refresh", headers=_auth(active_token)).status_code == 200


def test_disabling_someone_unknown_says_so(client):
    admin = _login(client, "admin", "admin").get_json()["accessToken"]
    response = client.post("/api/disable_user", json={"username": "nobody_here"}, headers=_auth(admin))
    assert response.status_code == 400


# --- email recovery gives nothing away ---------------------------------------------------------------------------

def test_email_recovery_answers_the_same_whether_or_not_the_address_exists(app, client):
    _add_user(app, "has_email", email="known@example.com", email_verified=True)
    known = client.post("/api/account/forgot-password", json={"email": "known@example.com"})
    unknown = client.post("/api/account/forgot-password", json={"email": "unknown@example.com"})
    assert (known.status_code, known.get_json()) == (unknown.status_code, unknown.get_json())
    known = client.post("/api/account/forgot-username", json={"email": "known@example.com"})
    unknown = client.post("/api/account/forgot-username", json={"email": "unknown@example.com"})
    assert (known.status_code, known.get_json()) == (unknown.status_code, unknown.get_json())


# --- the refresh -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("race, refreshed", [("", False), ("Xo", True)])
def test_the_refresh_skips_kingdoms_that_were_never_set_up(app, race, refreshed):
    """A kingdom is set up when its race is chosen (_finish_kingdom); until then the refresh leaves it alone."""
    hour_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    _set_up_kingdom(money=100, race=race, last_income=hour_ago)  # _finish_kingdom sets both
    before = _get(f"/kingdom/{KD_ID}")
    state = _get("/state")
    with app.app_context():
        refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)
    after = _get(f"/kingdom/{KD_ID}")
    assert (after["_etag"] != before["_etag"]) is refreshed
    assert (after["last_income"] != before["last_income"]) is refreshed


def test_the_refresh_does_not_read_users(app, monkeypatch):
    hour_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    _set_up_kingdom(money=100, race="Xo", last_income=hour_ago)
    state = _get("/state")
    reads = _counting_user_reads(monkeypatch)
    with app.app_context():
        refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)
    assert reads == []


# --- a round reset keeps users ------------------------------------------------------------------------------------

def test_a_round_reset_keeps_accounts_and_frees_their_kingdoms(app, client):
    # the global documents /resetstate expects, as /init makes them
    for doc_id, state in {
        "accounts": {"accounts": []}, "kingdoms": {"kingdoms": {}}, "galaxies": {"galaxies": {}},
        "empires": {"empires": {}}, "universe_news": {"news": []}, "universe_votes": {"votes": {}},
        "scores": {"points": {}, "stars": {}, "networth": {}, "galaxy_networth": {}},
    }.items():
        _create_item(doc_id, state)
    _create_item("kingdom_1", {"name": "Gone"})
    admin = _login(client, "admin", "admin").get_json()["accessToken"]
    assert client.post("/api/resetstate", headers=_auth(admin)).status_code == 200

    users = {user.username: user for user in _all(app)}
    assert {"admin", "user1", "user2"} <= set(users)
    assert all(user.kd_id is None and not user.kd_created for user in users.values())
    assert _login(client, "user1", "user1").status_code == 200
