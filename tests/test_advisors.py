"""
The advisors (``advisors.py``, docs/advisors.md): each check with plain inputs, then the route, hiding advice and the
switch in the preferences.
"""
import dataclasses
import datetime
import json

import pytest

import untitledapp.advisors as uaadv
import untitledapp.botstrategy as strategy
import untitledapp.shared as uas
from tests.test_concurrency import _create_item, _set_up_kingdom

NOW = datetime.datetime(2026, 11, 22, tzinfo=datetime.timezone.utc)


def _ctx(**kd_fields):
    """A healthy kingdom: fuel to spare, room in its hangars, defended well over the break-even, built on, settling,
    money spent, and its galaxy votes in. Keyword arguments that are ``Context`` fields set those; the rest go into the
    kingdom."""
    ctx_fields = {key: kd_fields.pop(key) for key in [field.name for field in dataclasses.fields(uaadv.Context)]
                  if key in kd_fields}
    kd = {"kdId": "1", "race": "Xo", "stars": 1000, "fuel": 50000, "money": 1000,
          "income": {"fuel": {"net": 100}, "money": {"net": 5000}},
          "structures": {"homes": 500, "mines": 500}, "units": {"attack": 0, "engineers": 0}, "spy_attempts": 2,
          **kd_fields}
    fields = {"epochs": 96, "max_hangar": 1000, "used_hangar": 500, "home_defense": 10 ** 6, "at_war": False,
              "epochs_left": 240, "progress": 0.3,
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
    assert "fuel_running_out" not in _ids(_ctx(income={}))


def test_hangars_full_past_two_percent_over():
    assert _ids(_ctx(max_hangar=1000, used_hangar=1020)) == []
    [advice] = uaadv.advise(_ctx(max_hangar=1000, used_hangar=1030))
    assert advice.id == "hangars_full"
    assert "1,030" in advice.text and "1,000" in advice.text and "The 30 without a hangar" in advice.text


def test_defense_well_under_the_break_even_with_primitives():
    line = 1000 * strategy.break_even_per_star(96)
    assert _ids(_ctx(home_defense=line * uaadv.DEFENSE_WARNING_SHARE)) == []
    [advice] = uaadv.advise(_ctx(home_defense=line * uaadv.DEFENSE_WARNING_SHARE - 1))
    assert advice.id == "defense_under_break_even"
    assert f"{int(line):,}" in advice.text  # the full line, not the warning point
    assert ("Train units", "/military") in advice.links


def test_at_war_the_line_is_higher_and_the_advice_says_why():
    defense = 1000 * strategy.break_even_per_star(96) * uaadv.DEFENSE_WARNING_SHARE
    assert _ids(_ctx(home_defense=defense, at_war=False)) == []
    [advice] = uaadv.advise(_ctx(home_defense=defense, at_war=True))
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


# ----------------------------------------------------------------------------------------------------------- waste

def _only(ctx, advice_id):
    [advice] = [advice for advice in uaadv.advise(ctx) if advice.id == advice_id]
    return advice


def test_empty_stars_count_what_is_on_order():
    assert "empty_stars" not in _ids(_ctx(structures={"homes": 900}, structures_queued=60))  # 40 empty: under 5%
    assert _only(_ctx(structures={"homes": 900}, structures_queued=40), "empty_stars").text.startswith("60 of your stars")


def test_empty_stars_say_nothing_while_the_auto_builder_will_build_on_them():
    # Right after a big attack the new stars arrive empty; auto spending with structure targets builds on them.
    builder = {"auto_spending_enabled": True, "auto_spending": {"structures": 0.3}, "structures_target": {"homes": 1}}
    assert "empty_stars" not in _ids(_ctx(structures={"homes": 500}, **builder))
    assert "empty_stars" in _ids(_ctx(structures={"homes": 500}, **{**builder, "auto_spending": {"structures": 0}}))


def test_idle_money_past_six_epochs_of_income_said_in_hours():
    # 5,000 an epoch: six epochs is 30,000.
    assert "idle_money" not in _ids(_ctx(money=20000, funding={"military": 10000}))
    advice = _only(_ctx(money=30000, funding={"military": 10000}), "idle_money")
    assert "40,000" in advice.text and "4 hours" in advice.text and "epoch" not in advice.text


def test_auto_spending_without_targets_names_what_is_missing():
    base = {"auto_spending_enabled": True, "auto_spending": {"structures": 0.3, "military": 0.3},
            "structures_target": {"homes": 0.5}, "units_target": {"attack": 0}}
    assert "for units" in _only(_ctx(**base), "auto_spending_without_targets").text
    assert "auto_spending_without_targets" not in _ids(_ctx(**{**base, "auto_spending_enabled": False}))
    assert "auto_spending_without_targets" not in _ids(_ctx(**{**base, "units_target": {"attack": 1}}))


def test_engineers_idle_any_without_auto_assign():
    kd = {"units": {"engineers": 100}, "projects_assigned": {"pop_bonus": 99}}
    assert "engineers_idle" not in _ids(_ctx(**kd))                  # auto assign is on by default
    assert _only(_ctx(auto_assign_projects=False, **kd), "engineers_idle").text.startswith("1 of your engineers is not")
    assert "engineers_idle" not in _ids(_ctx(auto_assign_projects=False, units={"engineers": 100},
                                             projects_assigned={"pop_bonus": 100}))


def test_generals_idle_needs_an_army_and_nothing_to_send_it():
    army = {"units": {"attack": 100}}
    assert "generals_idle" in _ids(_ctx(**army))
    assert "generals_idle" not in _ids(_ctx(**army, auto_attack_enabled=True))
    assert "generals_idle" not in _ids(_ctx(**army, generals_out=[{"attack": 50}]))
    assert "generals_idle" not in _ids(_ctx(**army, schedule=[{"type": "attackprimitives"}]))
    assert "generals_idle" not in _ids(_ctx())                       # no offense to send


def test_generals_idle_skips_an_army_of_flex_units_or_defenders():
    assert "generals_idle" not in _ids(_ctx(units={"flex": 1000}))                     # all flex
    assert "generals_idle" not in _ids(_ctx(units={"defense": 1000, "attack": 40}))    # 4% pure attackers
    assert "generals_idle" in _ids(_ctx(units={"defense": 1000, "attack": 60}))        # 6%


def test_spy_attempts_full():
    full = uas.GAME_CONFIG["BASE_SPY_ATTEMPTS_MAX"]
    assert "spy_attempts_full" in _ids(_ctx(spy_attempts=full))
    assert "spy_attempts_full" not in _ids(_ctx(spy_attempts=full, auto_rob_enabled=True))


# ------------------------------------------------------------------------------------------------------------ team

def test_galaxy_votes_missing_says_which():
    [advice] = uaadv.advise(_ctx(galaxy_votes_missing=["policies"]))
    assert advice.id == "galaxy_votes_missing"
    assert advice.text.startswith("You have not voted for all of your galaxy's policies.")
    assert "leader and policies" in _only(_ctx(galaxy_votes_missing=["leader", "policies"]), "galaxy_votes_missing").text


def test_a_galaxy_without_policies():
    advice = _only(_ctx(galaxy_policies_active=0), "galaxy_without_policies")
    assert "galaxy_without_policies" not in _ids(_ctx(galaxy_policies_active=1))
    assert "galaxy_without_policies" not in _ids(_ctx(galaxy_policies_active=None))  # no galaxy
    assert ("Galaxy politics", "/galaxypolitics") in advice.links


def test_leader_only_advice_goes_only_to_the_leader():
    assert "cluster_vote_missing" not in _ids(_ctx(is_leader=False, cluster_voted=False))
    assert "cluster_vote_missing" in _ids(_ctx(is_leader=True, cluster_voted=False))
    assert "galaxy_without_empire" not in _ids(_ctx(is_leader=False, in_empire=False))
    assert "galaxy_without_empire" in _ids(_ctx(is_leader=True, in_empire=False, progress=0.5))
    assert "galaxy_without_empire" not in _ids(_ctx(is_leader=True, in_empire=False, progress=0.1))  # early


def test_an_open_election_without_your_votes():
    ends = NOW + datetime.timedelta(hours=5, minutes=30)
    [advice] = uaadv.advise(_ctx(election_ends=ends, cast_universe_votes=False))
    assert advice.id == "universe_election_open" and "about 5 hours" in advice.text
    assert _ids(_ctx(election_ends=ends, cast_universe_votes=True)) == []


def test_war_targets():
    [advice] = uaadv.advise(_ctx(at_war=True, war_targets=2))
    assert advice.id == "empire_war_targets" and "2 targets" in advice.text
    assert _ids(_ctx(at_war=False, war_targets=2)) == []


def test_context_reads_leadership_votes_and_targets():
    kd = {"kdId": "1", "race": "Xo", "stars": 300, "fuel": 100, "units": {}, "structures": {"hangars": 0}}
    state = {"state": {"game_start": (NOW - datetime.timedelta(days=1)).isoformat(),
                       "game_end": (NOW + datetime.timedelta(days=6)).isoformat(),
                       "election_end": (NOW + datetime.timedelta(hours=2)).isoformat()}}
    votes = {"votes": {"policy_1": {"option_1": {"2": 5}}, "policy_2": {"option_1": {}}}}
    ctx = uaadv.context_for(kd, state, [], {"1": "e"}, {"e": {"war": ["f"]}}, NOW, galaxy_id="1:1",
                            galaxy_votes={"leader": "1"}, cluster={"votes": {"1:2": "x"}}, universe_votes=votes,
                            targets={"targets": {"9": {}}})
    assert ctx.is_leader and not ctx.cluster_voted and ctx.in_empire and ctx.at_war and ctx.war_targets == 1
    assert ctx.election_ends is not None and not ctx.cast_universe_votes
    assert abs(ctx.progress - 1 / 7) < 0.01
    assert ctx.galaxy_votes_missing == ["leader", "policies"] and ctx.galaxy_policies_active == 0


def test_context_reads_the_galaxy_policies_the_round_plays():
    import untitledapp.galaxypolicies as uagp
    kd = {"kdId": "1", "race": "Xo", "stars": 300, "fuel": 100, "units": {}, "structures": {"hangars": 0}}
    policy = uagp.round_policies({})[0]
    option = next(iter(uas.GALAXY_POLICIES[policy]["options"]))
    state = {"state": {"game_start": (NOW - datetime.timedelta(days=1)).isoformat(),
                       "game_end": (NOW + datetime.timedelta(days=6)).isoformat(), "election_end": ""}}
    document = {"votes": {"leader": {"1": "2"}}, "policy_votes": {policy: {"1": option}},
                "policy_active": {policy: option}, "policy_updated": NOW.isoformat()}
    ctx = uaadv.context_for(kd, state, [], {}, {}, NOW, galaxy_id="1:1", galaxy_votes=document)
    assert ctx.galaxy_votes_missing == [] and ctx.galaxy_policies_active == 1
    assert uaadv.context_for(kd, state, [], {}, {}, NOW).galaxy_policies_active is None


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
    advice = client.get("/api/advisors", headers=_auth(jwt1)).get_json()["advice"]
    danger = [item["id"] for item in advice if item["kind"] == "danger"]
    assert danger == ["out_of_fuel", "hangars_full"]  # no hangars for 100,000 defenders, which out-defend the line


def test_the_route_tells_a_galaxy_leader_about_the_cluster_vote(app, client, jwt1):
    _set_up()
    _create_item("galaxies", {"galaxies": {"1:1": ["1"]}})
    _create_item("galaxy_votes_1:1", {"leader": "1", "votes": {"leader": {"1": "1"}},
                                      "policy_votes": {}, "policy_active": {}})
    ids = [advice["id"] for advice in client.get("/api/advisors", headers=_auth(jwt1)).get_json()["advice"]]
    assert "cluster_vote_missing" in ids
    assert "galaxy_votes_missing" in ids  # policies, not the leader
    assert "galaxy_without_policies" in ids


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
