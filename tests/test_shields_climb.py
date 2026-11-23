"""Raised shields climb to their level over BASE_SHIELDS_CLIMB_EPOCHS; cut ones drop at once (tenet 1)."""
import datetime

import pytest

import untitledapp.shared as uas
from tests import kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _set_up_kingdom

START = kingdoms.START
EPOCH = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]


def _at(epochs):
    return START + datetime.timedelta(seconds=EPOCH * epochs * uas.GAME_CONFIG["BASE_SHIELDS_CLIMB_EPOCHS"])


def _climbing(start=0.05, to=0.10):
    return {"shields": {"military": start, "spy": 0.0, "spy_radar": 0.0, "missiles": 0.0},
            "shields_climb": {"military": {"from": start, "to": to, "since": START.isoformat()}}}


def test_a_raise_climbs_in_a_straight_line_and_then_holds():
    kd = _climbing()
    assert uas.shields_now(kd, _at(0))["military"] == pytest.approx(0.05)
    assert uas.shields_now(kd, _at(0.2))["military"] == pytest.approx(0.06)
    assert uas.shields_now(kd, _at(1))["military"] == pytest.approx(0.10)
    assert uas.shields_now(kd, _at(5))["military"] == pytest.approx(0.10)


def test_a_kingdom_made_before_climbs_reads_its_shields_as_they_are():
    kd = {"shields": {"military": 0.1, "spy": 0.2, "spy_radar": 0.0, "missiles": 0.5}}
    assert uas.shields_now(kd) == kd["shields"]
    assert uas.shields_average(kd, START, _at(3)) == kd["shields"]


def test_raising_climbs_from_where_the_shield_is_and_cutting_is_at_once():
    kd = _climbing()
    shields, climbs = uas.change_shields(kd, {"military": 0.08, "spy": 0.2}, _at(0.4))  # military is at 7% now
    assert climbs["military"] == {"from": pytest.approx(0.07), "to": 0.08, "since": _at(0.4).isoformat()}
    assert climbs["spy"]["from"] == 0.0 and climbs["spy"]["to"] == 0.2

    shields, climbs = uas.change_shields(kd, {"military": 0.02}, _at(0.4))
    assert shields["military"] == 0.02 and "military" not in climbs


def test_asking_again_for_the_level_a_shield_is_climbing_to_does_not_restart_it():
    kd = _climbing()
    _, climbs = uas.change_shields(kd, {"military": 0.10, "spy": 0.0}, _at(0.5))
    assert climbs["military"]["since"] == START.isoformat()


def test_the_refresh_charges_fuel_on_the_average_level_and_settles_a_finished_climb(app):
    # The maintainer's example: 5% costs 1000 and 10% costs 2000, so 6% costs 1200. Fuel is linear in the level.
    stars = 300
    per_pct = uas.shield_fuel_per_pct("military")
    kd = kingdoms.kingdom(stars=stars, fuel=10 ** 5, structures={"fuel_plants": 200}, **_climbing())

    early = kingdoms.income(app, kd, epochs=0.2)  # from 5% to 6%: 5.5% on average
    assert early["income"]["fuel"]["shields"]["military"] == pytest.approx(5.5 * stars * per_pct)
    assert early["shields"]["military"] == pytest.approx(0.06)
    assert "military" in early["shields_climb"]

    late = kingdoms.income(app, kd, epochs=2)  # a late refresh: half the time climbing (7.5%), half at 10%
    assert late["income"]["fuel"]["shields"]["military"] == pytest.approx(8.75 * stars * per_pct)
    assert late["shields"]["military"] == pytest.approx(0.10)
    assert late["shields_climb"] == {}


def test_running_out_of_fuel_drops_every_shield_and_climb(app):
    kd = kingdoms.kingdom(stars=300, fuel=-10 ** 9, **_climbing())
    after = kingdoms.income(app, kd, epochs=0.5)
    assert after["shields"]["military"] == 0 and after["shields_climb"] == {}


def test_the_shields_route_starts_a_climb_and_cuts_at_once(app, client, jwt1):
    _set_up_kingdom(money=0)
    _create_item(f"kingdom_{KD_ID}", {"fuel": 1000, "shields": {"military": 0.0, "spy": 0.2, "spy_radar": 0.0, "missiles": 0.0}})
    response = client.post("/api/shields", json={"military": 10, "spy": 5}, headers={"Authorization": f"Bearer {jwt1}"})
    assert response.status_code == 200, response.get_json()

    kd = _get(f"/kingdom/{KD_ID}")
    assert kd["shields"]["military"] == pytest.approx(0.0, abs=1e-3)  # just started
    assert kd["shields_climb"]["military"]["to"] == pytest.approx(0.10)
    assert kd["shields"]["spy"] == pytest.approx(0.05) and "spy" not in kd["shields_climb"]
    later = uas.utc(kd["shields_climb"]["military"]["since"]) + datetime.timedelta(seconds=EPOCH * 10)
    assert uas.shields_now(kd, later)["military"] == pytest.approx(0.10)


def test_an_attack_meets_the_shields_as_far_as_they_have_climbed():
    """Strength never changes much in an instant: a raise just made adds next to nothing yet."""
    kd = _climbing(start=0.0, to=0.10)
    assert uas.shields_now(kd, _at(0.01))["military"] == pytest.approx(0.001)


def test_spying_on_shields_shows_the_climb():
    assert "shields_climb" in uas.REVEAL_FIELDS["shields"]
