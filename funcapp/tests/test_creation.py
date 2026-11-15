"""
Kingdom and empire creation (create_kingdom, create_empire in funcapp/function_app.py) when several happen at once.

The id of a new kingdom or empire is chosen with a conditional write on `kingdoms` / `empires`
(concurrency.change_document), so overlapping creations get different ids and none is lost from its galaxy.
"""
import json
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
    container = fake_backend.FakeContainer(latency=0.003)
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    assert session.request("POST", ENDPOINT + "/init").status_code == 201
    container.docs["galaxies"]["galaxies"] = {"1:1": [], "1:2": []}
    return container, session


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


def _create_kingdom(session, name, galaxy="1:1"):
    return session.request("POST", ENDPOINT + "/kingdom", data=json.dumps({"kingdom_name": name, "galaxy": galaxy}))


def _create_empire(session, galaxy):
    return session.request("POST", ENDPOINT + "/empire", data=json.dumps(
        {"empire_name": f"Empire of {galaxy}", "galaxy_id": galaxy, "leader": galaxy}))


def test_kingdoms_created_at_once_get_different_ids_and_all_join_their_galaxy(backend):
    container, session = backend
    responses = _in_threads(8, lambda i: _create_kingdom(session, f"kd{i}", galaxy=("1:1", "1:2")[i % 2]))

    assert [r.status_code for r in responses] == [201] * 8
    ids = [r.text for r in responses]
    assert len(set(ids)) == 8
    assert sorted(container.docs["kingdoms"]["kingdoms"].values()) == sorted(f"kd{i}" for i in range(8))
    galaxies = container.docs["galaxies"]["galaxies"]
    assert sorted(galaxies["1:1"] + galaxies["1:2"]) == sorted(ids)
    assert all(f"kingdom_{kd_id}" in container.docs for kd_id in ids)


def test_the_same_kingdom_name_twice_at_once_makes_one(backend):
    container, session = backend
    responses = _in_threads(4, lambda i: _create_kingdom(session, "Twin"))

    assert sorted(r.status_code for r in responses) == [201, 400, 400, 400]
    assert list(container.docs["kingdoms"]["kingdoms"].values()) == ["Twin"]
    assert len(container.docs["galaxies"]["galaxies"]["1:1"]) == 1


def test_a_kingdom_id_is_never_reused(backend):
    container, session = backend
    container.docs["kingdoms"]["kingdoms"] = {"0": "a", "2": "c"}  # "1" was removed somehow
    response = _create_kingdom(session, "new")
    assert response.status_code == 201 and response.text not in ("0", "2")


def test_empires_created_at_once_by_different_galaxies_get_different_ids(backend):
    container, session = backend
    responses = _in_threads(6, lambda i: _create_empire(session, f"1:{i + 1}"))

    assert [r.status_code for r in responses] == [201] * 6
    ids = {r.text for r in responses}
    assert len(ids) == 6
    assert set(container.docs["empires"]["empires"]) == ids
    assert all(f"empire_politics_{empire_id}" in container.docs for empire_id in ids)


def test_a_galaxy_founding_two_empires_at_once_founds_one(backend):
    container, session = backend
    responses = _in_threads(5, lambda i: _create_empire(session, "1:1"))

    assert sorted(r.status_code for r in responses) == [201] + [409] * 4
    assert len(container.docs["empires"]["empires"]) == 1


def test_a_galaxy_already_in_an_empire_can_not_found_another(backend):
    container, session = backend
    assert _create_empire(session, "1:1").status_code == 201
    container.docs["empires"]["empires"]["0"]["galaxies"].append("1:2")  # 1:2 joined it
    assert _create_empire(session, "1:2").status_code == 409


def test_kingdom_ids_are_not_reused_after_a_round_reset_and_the_round_changes(backend):
    """A login token from the earlier round must not name a new player's kingdom (decision 0005)."""
    container, session = backend
    first = [_create_kingdom(session, f"old{i}").text for i in range(3)]
    round_before = container.docs["state"]["round"]
    for name in ("accounts",):
        container.docs.setdefault(name, {"id": name, "accounts": []})
    for name, body in {
        "universe_news": {"news": []}, "universe_votes": {"votes": {}},
        "scores": {"points": {}, "stars": {}, "networth": {}, "galaxy_networth": {}},
    }.items():
        container.docs.setdefault(name, {"id": name, **body})

    assert session.request("POST", ENDPOINT + "/resetstate").status_code == 200
    container.docs["galaxies"]["galaxies"] = {"1:1": [], "1:2": []}
    second = [_create_kingdom(session, f"new{i}").text for i in range(3)]

    assert set(first).isdisjoint(second)
    assert container.docs["state"]["round"] != round_before
