"""Shared intel, unsharing, and revealing a random galaxy, including requests landing together."""
import pytest

from tests.test_attack import _in_threads
from tests.test_concurrency import KD_ID, no_shared_lock, _create_item, _get, _run_together, _set_up_kingdom  # noqa: F401

FUTURE = "2030-06-01T00:00:00+00:00"


def _galaxy_of(*kd_ids):
    _create_item("galaxies", {"galaxies": {"1": list(kd_ids)}})
    _create_item("galaxy_votes_1", {"active_policies": [], "votes": {}})
    _create_item("empires", {"empires": {}})
    _create_item("kingdoms", {"kingdoms": {k: f"Kingdom {k}" for k in kd_ids}})


def test_racing_accepts_of_one_offer_accept_it_once(app, client, jwt1):
    _set_up_kingdom(money=0)
    _galaxy_of(KD_ID, "2")
    offer = {"shared_by": "2", "shared_stat": "stats", "cut": 0.1, "time": FUTURE}
    _create_item(f"shared_{KD_ID}", {"shared": {}, "shared_requests": {"9_2": offer}, "shared_offers": {}})

    responses = _run_together(app, 8, lambda c, i: c.post(
        "/api/shared", json={"shared": "9_2"}, headers={"Authorization": f"Bearer {jwt1}"}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    shared = _get(f"/kingdom/{KD_ID}/shared")
    assert shared["shared"] == {"9": offer} and shared["shared_requests"] == {}


def test_offers_from_two_players_to_the_same_recipient_are_both_kept(app, client):
    import untitledapp.conquer as conquer

    for kd in ("1", "2", "3"):
        _set_up_kingdom(money=0, kd_id=kd)
    _galaxy_of("1", "2", "3")
    for kd in ("1", "2"):
        _create_item(f"revealed_{kd}", {"revealed": {"9": {"stats": FUTURE}}, "galaxies": {},
                                        "revealed_galaxymates": [], "revealed_to_galaxymates": []})

    def offer(i):
        conquer._offer_shared({"shared": "9", "shared_stat": "stats", "shared_to": "3", "cut": 10}, ["1", "2"][i])

    _in_threads(app, 2, offer)

    assert set(_get("/kingdom/3/shared")["shared_requests"]) == {"9_1", "9_2"}
    assert "9_3" in _get("/kingdom/1/shared")["shared_offers"] and "9_3" in _get("/kingdom/2/shared")["shared_offers"]
    assert _get("/kingdom/3")["next_resolve"]["shared"] == FUTURE


def test_unsharing_removes_only_that_galaxymate(app, client, jwt1):
    _set_up_kingdom(money=0)
    _galaxy_of(KD_ID, "2", "3")
    _create_item(f"revealed_{KD_ID}", {"revealed": {}, "galaxies": {}, "revealed_galaxymates": [],
                                       "revealed_to_galaxymates": ["2", "3"]})
    _create_item("revealed_2", {"revealed": {}, "galaxies": {}, "revealed_galaxymates": [KD_ID, "3"],
                                "revealed_to_galaxymates": []})

    response = client.post("/api/unshare/2", headers={"Authorization": f"Bearer {jwt1}"})

    assert response.status_code == 200
    assert _get(f"/kingdom/{KD_ID}/revealed")["revealed_to_galaxymates"] == ["3"]
    assert _get("/kingdom/2/revealed")["revealed_galaxymates"] == ["3"]


@pytest.mark.parametrize("repeat", range(2))
def test_racing_random_reveals_spend_the_one_attempt_once(app, client, jwt1, repeat):
    for kd in ("2", "3"):
        _set_up_kingdom(money=0, kd_id=kd)
    _set_up_kingdom(money=0, spy_attempts=1)
    _create_item("galaxies", {"galaxies": {"1": [KD_ID], "2": ["2"], "3": ["3"]}})  # after the setups, which reset it
    _create_item("empires", {"empires": {}})

    responses = _run_together(app, 6, lambda c, i: c.get(
        "/api/revealrandomgalaxy", headers={"Authorization": f"Bearer {jwt1}"}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 5, [r.get_json() for r in responses]
    assert _get(f"/kingdom/{KD_ID}")["spy_attempts"] == 0
    assert len(_get(f"/kingdom/{KD_ID}/revealed")["galaxies"]) == 1
