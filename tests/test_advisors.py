"""
The advisors (``advisors.py``, docs/advisors.md): each check with plain inputs, then the route, hiding advice and the
switch in the preferences.
"""
import datetime
import json

import pytest

import untitledapp.advisors as uaadv
import untitledapp.botstrategy as strategy
import untitledapp.shared as uas
from tests.test_concurrency import _create_item, _set_up_kingdom

NOW = datetime.datetime(2026, 11, 22, tzinfo=datetime.timezone.utc)


def _ctx(**kd_fields):
    """A healthy kingdom: fuel to spare, room in its hangars, defended well over the break-even."""
    ctx_fields = {key: kd_fields.pop(key) for key in ("epochs", "max_hangar", "used_hangar", "home_defense", "at_war")
                  if key in kd_fields}
    kd = {"kdId": "1", "stars": 1000, "fuel": 50000, "income": {"fuel": {"net": 100}}, **kd_fields}
    fields = {"epochs": 96, "max_hangar": 1000, "used_hangar": 500, "home_defense": 10 ** 6, "at_war": False,
              **ctx_fields}
    return uaadv.Context(kd=kd, now=NOW, **fields)


def _ids(ctx):
    return [advice.id for advice in uaadv.advise(ctx)]


def test_a_healthy_kingdom_gets_no_advice():
    assert _ids(_ctx()) == []


def test_out_of_fuel_says_what_it_costs_and_where_to_fix_it():
    [advice] = uaadv.advise(_ctx(fuel=0))
    assert advice.id == "out_of_fuel" and advice.kind == "danger"
    assert "20% weaker" in advice.text  # BASE_FUELLESS_STRENGTH_REDUCTION, from shared.py
    assert ("Build fuel plants", "/structures") in advice.links


@pytest.mark.parametrize("fuel, net, fires", [
    (1000, -100, True),     # 10 epochs: 5 hours
    (2400, -100, True),     # 24 epochs: 12 hours, the edge
    (2500, -100, False),    # over 12 hours: not yet
    (1000, 100, False),     # rising
    (0, -100, False),       # already out: out_of_fuel says it instead
])
def test_fuel_running_out_warns_within_twelve_hours(fuel, net, fires):
    ids = _ids(_ctx(fuel=fuel, income={"fuel": {"net": net}}))
    assert ("fuel_running_out" in ids) is fires


def test_fuel_running_out_gives_the_time_in_hours_not_epochs():
    [advice] = uaadv.advise(_ctx(fuel=1000, income={"fuel": {"net": -100}}))
    assert "in about 5 hours" in advice.text
    assert "epoch" not in advice.text


def test_a_kingdom_without_an_income_yet_is_not_warned_about_fuel():
    assert _ids(_ctx(income={})) == []


def test_hangars_full_counts_units_in_training():
    assert _ids(_ctx(max_hangar=1000, used_hangar=1000)) == []
    [advice] = uaadv.advise(_ctx(max_hangar=1000, used_hangar=1200))
    assert advice.id == "hangars_full"
    assert "1,200" in advice.text and "1,000" in advice.text


def test_defense_under_the_break_even_with_primitives():
    line = 1000 * strategy.break_even_per_star(96)
    assert _ids(_ctx(home_defense=line)) == []
    [advice] = uaadv.advise(_ctx(home_defense=line - 1))
    assert advice.id == "defense_under_break_even"
    assert f"{int(line):,}" in advice.text
    assert ("Train units", "/military") in advice.links


def test_at_war_the_line_is_higher_and_the_advice_says_why():
    peace_line = 1000 * strategy.break_even_per_star(96)
    assert _ids(_ctx(home_defense=peace_line, at_war=False)) == []
    [advice] = uaadv.advise(_ctx(home_defense=peace_line, at_war=True))
    assert "at war" in advice.text


def test_every_check_has_an_id_and_kind_listed():
    ctx = _ctx(fuel=0, max_hangar=0, used_hangar=1, home_defense=0)
    for check in uaadv.CHECKS:
        advice = check(ctx)
        if advice is not None:
            assert uaadv.IDS[advice.id] == advice.kind
            assert advice.links, f"{advice.id} has no link to where it is fixed"


def test_advice_is_most_serious_kind_first():
    first = uaadv.Advice("w", "waste", "", [])
    second = uaadv.Advice("d", "danger", "", [])
    found = uaadv.advise(_ctx(), checks=[lambda ctx: first, lambda ctx: second])
    assert [advice.id for advice in found] == ["d", "w"]


# ----------------------------------------------------------------------------------------------------------- route

def _auth(jwt):
    return {"Authorization": f"Bearer {jwt}"}


def _set_up(**overrides):
    fields = {"race": "Xo", "last_income": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    fields.update(overrides)
    _set_up_kingdom(money=1000, **fields)
    _create_item("empires", {"empires": {}})


def test_the_route_gives_a_new_kingdom_its_advice(app, client, jwt1):
    # The starting kingdom has no defense at all: under the break-even from the first hour.
    _set_up()
    answer = client.get("/api/advisors", headers=_auth(jwt1)).get_json()
    assert answer["enabled"] is True
    ids = [advice["id"] for advice in answer["advice"]]
    assert "defense_under_break_even" in ids
    advice = answer["advice"][ids.index("defense_under_break_even")]
    assert advice["kind"] == "danger" and advice["hideable"] is False and advice["hidden"] is False
    assert advice["links"][0] == {"label": "Train units", "to": "/military"}


def test_the_route_reads_fuel_and_hangars_from_the_kingdom(app, client, jwt1):
    units = {**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "defense": 100000}
    _set_up(fuel=0, units=units)
    ids = [advice["id"] for advice in client.get("/api/advisors", headers=_auth(jwt1)).get_json()["advice"]]
    assert ids == ["out_of_fuel", "hangars_full"]  # no hangars for 100,000 defenders, which out-defend the line


def test_no_advice_before_the_round_starts(app, client, jwt1):
    _set_up()
    later = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
    _create_item("state", {"state": {"game_start": later, "game_end": later, "active_policies": []}})
    assert client.get("/api/advisors", headers=_auth(jwt1)).get_json() == {"enabled": True, "advice": []}


def test_advisors_switched_off_give_nothing(app, client, jwt1, jwt2):
    _set_up()
    response = client.post("/api/preferences", headers=_auth(jwt1), data=json.dumps({"advisors": "off"}))
    assert response.status_code == 200, response.get_json()
    assert client.get("/api/advisors", headers=_auth(jwt1)).get_json() == {"enabled": False, "advice": []}
    assert client.get("/api/preferences", headers=_auth(jwt2)).get_json()["advisors"] == "on"


def test_danger_can_not_be_hidden_and_unknown_advice_is_refused(app, client, jwt1):
    hide = lambda body: client.post("/api/advisors/hide", headers=_auth(jwt1), data=json.dumps(body))
    assert hide({"id": "defense_under_break_even", "hidden": True}).status_code == 400
    assert hide({"id": "no_such_advice", "hidden": True}).status_code == 400
    assert hide({"id": "defense_under_break_even"}).status_code == 400
    assert client.get("/api/preferences", headers=_auth(jwt1)).get_json()["hidden_advice"] == []


def test_hidden_advice_is_kept_per_player_and_can_be_shown_again(app, client, jwt1, jwt2, monkeypatch):
    monkeypatch.setitem(uaadv.IDS, "a_waste", "waste")
    monkeypatch.setitem(uaadv.IDS, "b_waste", "waste")
    hide = lambda advice_id, hidden: client.post(
        "/api/advisors/hide", headers=_auth(jwt1), data=json.dumps({"id": advice_id, "hidden": hidden}))
    assert hide("a_waste", True).status_code == 200
    assert hide("b_waste", True).status_code == 200
    assert client.get("/api/preferences", headers=_auth(jwt1)).get_json()["hidden_advice"] == ["a_waste", "b_waste"]
    assert client.get("/api/preferences", headers=_auth(jwt2)).get_json()["hidden_advice"] == []
    assert hide("a_waste", False).status_code == 200
    assert client.get("/api/preferences", headers=_auth(jwt1)).get_json()["hidden_advice"] == ["b_waste"]


def test_hidden_advice_comes_back_flagged_hidden(app, client, jwt1, monkeypatch):
    _set_up()
    waste = uaadv.Advice("a_waste", "waste", "Something is idle.", [("Fix it", "/build")])
    monkeypatch.setitem(uaadv.IDS, "a_waste", "waste")
    monkeypatch.setattr(uaadv, "CHECKS", [lambda ctx: waste])
    client.post("/api/advisors/hide", headers=_auth(jwt1), data=json.dumps({"id": "a_waste", "hidden": True}))
    answer = client.get("/api/advisors", headers=_auth(jwt1)).get_json()
    assert answer["advice"] == [{"id": "a_waste", "kind": "waste", "text": "Something is idle.",
                                 "links": [{"label": "Fix it", "to": "/build"}], "hideable": True, "hidden": True}]


def test_advisors_need_a_login(app, client):
    assert client.get("/api/advisors").status_code == 401
