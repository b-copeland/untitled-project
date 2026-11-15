"""
Tests for the user routes in funcapp/function_app.py: user_<id>, username_<key> and user_counter.

They run the real handlers (through tests/fake_backend.py, the same in-memory container the Flask tests use), so they
need no emulator or function host. Run them from the repo root:

    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import pathlib
import sys
import threading

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests import fake_backend  # noqa: E402

ENDPOINT = "http://funcapp/api"


@pytest.fixture
def backend():
    container = fake_backend.FakeContainer(latency=0.002)
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    return container, session


def _call(session, method, path, **kwargs):
    return session.request(method, ENDPOINT + path, **kwargs)


def _key(username):
    return username.encode("utf-8").hex()


def _user(id_number, username, **fields):
    return {"id_number": id_number, "username": username, "password": "hash", "roles": "operator", "kd_id": None,
            "kd_created": False, "is_active": True, "email": None, **fields}


def _in_threads(count, target):
    results = [None] * count
    barrier = threading.Barrier(count)

    def run(index):
        barrier.wait()
        results[index] = target(index)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# --- user_<id> ---------------------------------------------------------------------------------------------------

def test_create_then_get_user(backend):
    _, session = backend
    created = _call(session, "POST", "/user", json=_user(7, "alice"))
    assert created.status_code == 201
    response = _call(session, "GET", "/user/7")
    assert response.status_code == 200
    assert response.json()["id"] == "user_7"
    assert response.json()["username"] == "alice"
    assert response.json()["id_number"] == 7


def test_create_user_twice_is_a_conflict(backend):
    container, session = backend
    assert _call(session, "POST", "/user", json=_user(1, "alice")).status_code == 201
    assert _call(session, "POST", "/user", json=_user(1, "bob")).status_code == 409
    assert container.docs["user_1"]["username"] == "alice"


@pytest.mark.parametrize("id_number", [None, "3", -1, True, 1.5])
def test_create_user_needs_an_integer_id(backend, id_number):
    container, session = backend
    assert _call(session, "POST", "/user", json=_user(id_number, "alice")).status_code == 400
    assert not container.docs


def test_missing_user_is_404(backend):
    _, session = backend
    assert _call(session, "GET", "/user/3").status_code == 404
    assert _call(session, "PATCH", "/user/3", json={"email": "a@b.c"}).status_code == 404


def test_patch_user_is_a_shallow_merge_and_keeps_the_id(backend):
    container, session = backend
    _call(session, "POST", "/user", json=_user(2, "alice", email="old@x.y"))
    response = _call(session, "PATCH", "/user/2", json={"email": "new@x.y", "id_number": 99, "id": "user_99"})
    assert response.status_code == 200
    stored = container.docs["user_2"]
    assert stored["email"] == "new@x.y"
    assert stored["username"] == "alice"
    assert stored["id_number"] == 2
    assert "user_99" not in container.docs


def test_patch_user_honours_if_match(backend):
    container, session = backend
    _call(session, "POST", "/user", json=_user(2, "alice"))
    etag = _call(session, "GET", "/user/2").json()["_etag"]
    first = _call(session, "PATCH", "/user/2", json={"kd_id": "4"}, headers={"If-Match": etag})
    assert first.status_code == 200
    assert first.headers["ETag"] == container.docs["user_2"]["_etag"]
    stale = _call(session, "PATCH", "/user/2", json={"kd_id": "5"}, headers={"If-Match": etag})
    assert stale.status_code == 412
    assert container.docs["user_2"]["kd_id"] == "4"


def test_concurrent_patches_to_different_fields_all_land(backend):
    container, session = backend
    _call(session, "POST", "/user", json=_user(1, "alice"))
    statuses = _in_threads(12, lambda i: _call(session, "PATCH", "/user/1", json={f"field_{i}": i}).status_code)
    assert statuses == [200] * 12
    assert all(container.docs["user_1"][f"field_{i}"] == i for i in range(12))


# --- username_<key> ----------------------------------------------------------------------------------------------

def test_claim_username_then_read_it(backend):
    _, session = backend
    assert _call(session, "POST", f"/username/{_key('Alice')}", json={"user_id": 3}).status_code == 201
    response = _call(session, "GET", f"/username/{_key('Alice')}")
    assert response.status_code == 200
    assert response.json()["user_id"] == 3


def test_usernames_are_case_sensitive(backend):
    _, session = backend
    assert _call(session, "POST", f"/username/{_key('Alice')}", json={"user_id": 1}).status_code == 201
    assert _call(session, "POST", f"/username/{_key('alice')}", json={"user_id": 2}).status_code == 201
    assert _call(session, "GET", f"/username/{_key('ALICE')}").status_code == 404


def test_unicode_and_unsafe_characters_make_a_valid_key(backend):
    _, session = backend
    name = "a/b?c#d\\é😀"
    assert _call(session, "POST", f"/username/{_key(name)}", json={"user_id": 1}).status_code == 201
    assert _call(session, "GET", f"/username/{_key(name)}").json()["user_id"] == 1


@pytest.mark.parametrize("key", ["ABCD", "xyz1", "abc", "61/62"])
def test_username_key_must_be_lowercase_hex(backend, key):
    container, session = backend
    assert _call(session, "POST", f"/username/{key}", json={"user_id": 1}).status_code in (400, 404)
    assert not container.docs


def test_only_one_of_many_concurrent_claims_wins(backend):
    container, session = backend
    key = _key("popular")
    statuses = _in_threads(10, lambda i: _call(session, "POST", f"/username/{key}", json={"user_id": i}).status_code)
    assert sorted(statuses) == [201] + [409] * 9
    winner = statuses.index(201)
    assert container.docs[f"username_{key}"]["user_id"] == winner


# --- user_counter ------------------------------------------------------------------------------------------------

def test_counter_is_created_on_first_read(backend):
    container, session = backend
    response = _call(session, "GET", "/usercounter")
    assert response.status_code == 200
    assert response.json()["next_id"] == 1
    assert container.docs["user_counter"]["next_id"] == 1
    assert _call(session, "GET", "/usercounter").json()["_etag"] == response.json()["_etag"]


def test_concurrent_first_reads_create_one_counter(backend):
    container, session = backend
    results = _in_threads(8, lambda i: _call(session, "GET", "/usercounter"))
    assert {r.status_code for r in results} == {200}
    assert {r.json()["next_id"] for r in results} == {1}


def test_conditional_counter_increments_never_hand_out_an_id_twice(backend):
    """What occ.update does: read, then write next_id + 1 with If-Match, again on a 412."""
    container, session = backend

    def take_id(_):
        while True:
            counter = _call(session, "GET", "/usercounter").json()
            response = _call(session, "PATCH", "/usercounter", json={"next_id": counter["next_id"] + 1},
                             headers={"If-Match": counter["_etag"]})
            if response.status_code == 200:
                return counter["next_id"]
            assert response.status_code == 412

    ids = _in_threads(10, take_id)
    assert sorted(ids) == list(range(1, 11))
    assert container.docs["user_counter"]["next_id"] == 11


def test_counter_patch_validates(backend):
    _, session = backend
    assert _call(session, "PATCH", "/usercounter", json={"next_id": 5}).status_code == 404
    _call(session, "GET", "/usercounter")
    assert _call(session, "PATCH", "/usercounter", json={"next_id": "5"}).status_code == 400
    assert _call(session, "PATCH", "/usercounter", json={"next_id": 5}).status_code == 200


# --- /users ------------------------------------------------------------------------------------------------------

def _seed_users(session):
    _call(session, "POST", "/user", json=_user(3, "bot_b", email="x@y.z", kd_id="5"))
    _call(session, "POST", "/user", json=_user(1, "alice", email="x@y.z", kd_id="2"))
    _call(session, "POST", "/user", json=_user(2, "bot_a", email=None, kd_id=None))
    _call(session, "POST", f"/username/{_key('alice')}", json={"user_id": 1})
    _call(session, "GET", "/usercounter")


def _names(response):
    assert response.status_code == 200
    return [user["username"] for user in response.json()["users"]]


def test_users_lists_only_users_in_id_order(backend):
    _, session = backend
    _seed_users(session)
    assert _names(_call(session, "GET", "/users")) == ["alice", "bot_a", "bot_b"]


def test_users_filters(backend):
    _, session = backend
    _seed_users(session)
    assert _names(_call(session, "GET", "/users", params={"email": "x@y.z"})) == ["alice", "bot_b"]
    assert _names(_call(session, "GET", "/users", params={"kd_id": "5"})) == ["bot_b"]
    assert _names(_call(session, "GET", "/users?prefix=bot_")) == ["bot_a", "bot_b"]
    assert _names(_call(session, "GET", "/users", params={"prefix": "bot_", "email": "x@y.z"})) == ["bot_b"]
    assert _names(_call(session, "GET", "/users", params={"email": "nobody@y.z"})) == []


# --- users outlive a round, but not /deleteall -------------------------------------------------------------------

def test_resetstate_keeps_users_and_deleteall_removes_them(backend):
    container, session = backend
    assert _call(session, "POST", "/init").status_code == 201
    _seed_users(session)
    container.docs["kingdom_1"] = {"id": "kingdom_1", "_etag": '"x"'}

    assert _call(session, "POST", "/resetstate").status_code == 200
    assert "kingdom_1" not in container.docs
    assert {"user_1", "user_2", "user_3", "user_counter", f"username_{_key('alice')}"} <= set(container.docs)

    _call(session, "POST", "/deleteall")
    assert not [doc_id for doc_id in container.docs if doc_id.startswith(("user_", "username_"))]
    assert container.docs["state"] == {"id": "state", "_etag": container.docs["state"]["_etag"],
                                       "_ts": container.docs["state"]["_ts"]}
    # and the name is free again
    assert _call(session, "POST", f"/username/{_key('alice')}", json={"user_id": 1}).status_code == 201
