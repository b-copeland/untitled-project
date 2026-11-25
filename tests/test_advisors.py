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


# What is on order: a fix that takes time to build or train is said, or stands the warning down once it is enough.
# Twelve hours is 24 epochs at the default epoch length.

def test_hangars_on_order_that_make_the_room_stand_the_warning_down():
    assert _ids(_ctx(max_hangar=1000, used_hangar=1100, max_hangar_built=1100, hangars_ready_epochs=24)) == []


def test_hangars_on_order_that_are_not_enough_are_said_with_when():
    [advice] = uaadv.advise(_ctx(max_hangar=6150, used_hangar=7041, max_hangar_built=6500, hangars_ready_epochs=24))
    assert advice.id == "hangars_full"
    assert "hold 6,150 now and 6,500 in about 12 hours, once the hangars on order are built" in advice.text
    assert "The 891 without a hangar" in advice.text and "Build more hangars." in advice.text
    assert "epoch" not in advice.text


def test_fuel_plants_on_order_in_time_stand_the_warning_down():
    assert "fuel_running_out" not in _ids(_ctx(fuel=1000, income={"fuel": {"net": -100}}, fuel_net_built=50,
                                               fuel_plants_ready_epochs=8))


def test_fuel_plants_on_order_too_late_or_too_few_are_said():
    [late] = uaadv.advise(_ctx(fuel=1000, income={"fuel": {"net": -100}}, fuel_net_built=50,
                               fuel_plants_ready_epochs=16))
    assert "those on order are ready only in about 8 hours" in late.text and "Lower your shields" in late.text
    [few] = uaadv.advise(_ctx(fuel=1000, income={"fuel": {"net": -100}}, fuel_net_built=-20,
                              fuel_plants_ready_epochs=4))
    assert "even with those on order" in few.text and "Build more fuel plants" in few.text


def test_out_of_fuel_with_enough_fuel_plants_on_order_says_when():
    [advice] = uaadv.advise(_ctx(fuel=0, fuel_net_built=50, fuel_plants_ready_epochs=4))
    assert "The fuel plants on order make more than you use in about 2 hours" in advice.text


def test_defense_with_units_in_training_says_what_it_will_be():
    line = 1000 * strategy.break_even_per_star(96 + 24)
    [enough] = uaadv.advise(_ctx(home_defense=0, defense_trained=line + 10, training_ready_epochs=24))
    assert enough.id == "defense_under_break_even"
    assert f"The units in training bring it to {int(line + 10):,} in about 12 hours" in enough.text
    assert ("Shields", "/shields") in enough.links
    [short] = uaadv.advise(_ctx(home_defense=0, defense_trained=line / 2, training_ready_epochs=24))
    assert f"0 right now and {int(line / 2):,} in about 12 hours" in short.text
    assert f"At least {int(line):,}" in short.text and "Train more defense" in short.text


def test_context_projects_what_is_on_order():
    kd = {"kdId": "1", "race": "Xo", "stars": 300, "fuel": 100, "units": {"defense": 0},
          "structures": {"hangars": 10, "fuel_plants": 2}, "income": {"fuel": {"net": -100, "bonus": 0.5}}}
    state = {"state": {"game_start": (NOW - datetime.timedelta(days=1)).isoformat(),
                       "game_end": (NOW + datetime.timedelta(days=6)).isoformat(), "election_end": ""}}
    epoch = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
    soon, later = (NOW + datetime.timedelta(seconds=epoch * n) for n in (2, 6))
    structures = [{"time": soon.isoformat(), "hangars": 5}, {"time": later.isoformat(), "hangars": 5, "fuel_plants": 1}]
    mobis = [{"time": soon.isoformat(), "defense": 100}]
    ctx = uaadv.context_for(kd, state, mobis, {}, {}, NOW, structures_queue=structures)
    capacity = uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    assert ctx.max_hangar == 10 * capacity and ctx.max_hangar_built == 20 * capacity
    assert ctx.hangars_ready_epochs == 6 and ctx.fuel_plants_ready_epochs == 6
    assert ctx.fuel_net_built == -100 + uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"] * 1.5
    assert ctx.defense_trained > ctx.home_defense and ctx.training_ready_epochs == 2
    nothing = uaadv.context_for(kd, state, [], {}, {}, NOW)
    assert nothing.max_hangar_built is None and nothing.fuel_net_built is None and nothing.defense_trained is None


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


# ------------------------------------------------------------------------------------------------------------ peer

def _kingdom(drones, income=1000, stars=100, race="Xo", status="Active"):
    return {"kdId": "x", "race": race, "status": status, "stars": stars, "drones": drones, "fuel": 100,
            "income": {"money": {"net": income}}, "units": {"defense": 10}, "shields": {}}


def test_peer_ranges_need_enough_kingdoms_and_leave_out_the_dead_and_unset():
    nine = [_kingdom(drones=d) for d in range(9)]
    assert uaadv.peer_ranges(nine) == {}
    assert uaadv.peer_ranges(nine + [_kingdom(1, status="Dead"), _kingdom(1, race=""), None]) == {}
    ranges = uaadv.peer_ranges(nine + [_kingdom(drones=9)])
    assert ranges["drones_per_star"] == {"low": pytest.approx(0.009), "median": pytest.approx(0.045), "n": 10}
    assert set(ranges) == set(uaadv.PEER_ADVICE)


def test_peer_advice_only_for_the_extreme_and_never_with_a_figure():
    spread = {"drones_per_star": {"low": 2.0, "median": 4.0, "n": 50}}
    advice = uaadv.advise(_ctx(peer={"drones_per_star": 1.0}, peer_ranges=spread))
    assert [a.id for a in advice] == ["peer_drones_low"]
    assert advice[0].kind == "peer" and advice[0].text.startswith("Almost every kingdom")
    assert not any(ch.isdigit() for ch in advice[0].text)
    assert _ids(_ctx(peer={"drones_per_star": 2.0}, peer_ranges=spread)) == []           # at the low percentile
    tight = {"drones_per_star": {"low": 3.9, "median": 4.0, "n": 50}}
    assert _ids(_ctx(peer={"drones_per_star": 3.5}, peer_ranges=tight)) == []            # only a little below
    assert _ids(_ctx(peer={"drones_per_star": 1.0}, peer_ranges={})) == []               # no ranges yet


def test_peer_advice_can_be_hidden(app, client, jwt1):
    response = client.post("/api/advisors/hide", headers=_auth(jwt1),
                           data=json.dumps({"id": "peer_drones_low", "hidden": True}))
    assert response.status_code == 200


def test_the_universe_stats_keep_peer_ranges_and_the_advice_has_no_figure(app, client, jwt1):
    import untitledapp.refresh as refresh
    from tests.test_concurrency import _get
    _set_up(drones=0)
    now = datetime.datetime.now(datetime.timezone.utc)
    others = [_kingdom(drones=d * 100 + 200) for d in range(12)]
    with app.app_context():
        context = refresh._RefreshContext(state=None)
        context.kingdoms = {str(i): kd for i, kd in enumerate(others)}
        refresh._resolve_universe_stats(context, now)
    stored = _get("/universestats")
    assert stored["peer_ranges"]["drones_per_star"]["n"] == 12 and stored["last_update"] == now.isoformat()
    # The kingdom with no drones is told, in words.
    advice = client.get("/api/advisors", headers=_auth(jwt1)).get_json()["advice"]
    peers = {item["id"]: item for item in advice if item["kind"] == "peer"}
    assert "peer_drones_low" in peers and peers["peer_drones_low"]["hideable"] is True
    assert not any(ch.isdigit() for item in peers.values() for ch in item["text"])


def test_without_universe_stats_there_is_no_peer_advice(app, client, jwt1):
    _set_up(drones=0)
    advice = client.get("/api/advisors", headers=_auth(jwt1)).get_json()["advice"]
    assert not [item for item in advice if item["kind"] == "peer"]


def _run_refresh(app, monkeypatch, next_history):
    import untitledapp.refresh as refresh
    seen = {}
    monkeypatch.setattr(uaadv, "peer_ranges", lambda kingdoms: seen.setdefault("kingdoms", list(kingdoms)) and {})
    monkeypatch.setattr(refresh.uag, "_update_universe_stats", lambda fields: seen.update(written=fields))
    monkeypatch.setattr(refresh, "_resolve_scores", lambda scores, now, context=None: None)
    monkeypatch.setattr(refresh, "_refresh_kd", lambda kd_id, state, now, history, context=None:
                        context.kingdoms.update({kd_id: {"kdId": kd_id}}) or (1, 1))
    monkeypatch.setattr(refresh, "_resolve_empires", lambda scores, now: None)
    monkeypatch.setattr(refresh, "_resolve_clusters", lambda empires, now, context: None)
    monkeypatch.setattr(refresh, "_take_history_mark", lambda now: True)
    monkeypatch.setattr(refresh.uag, "_get_state", lambda: {"state": {
        "game_start": "2000-01-01T00:00:00+00:00", "election_start": "", "election_end": "",
        "next_history": next_history, "migrations_done": uaadv_migration_ids()}})
    monkeypatch.setattr(refresh.uag, "_get_kingdoms", lambda: ["1", "2"])
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    response = app.test_client().get("/api/refreshdata", headers={"Refresh-Secret": "secret"})
    assert response.status_code == 200, response.get_data(as_text=True)
    return seen


def uaadv_migration_ids():
    import untitledapp.migrations as migrations
    return migrations.all_ids()


def test_the_refresh_compares_the_kingdoms_it_holds_once_per_history_mark(app, monkeypatch):
    seen = _run_refresh(app, monkeypatch, "2000-01-01T00:00:00+00:00")  # the mark is due
    assert [kd["kdId"] for kd in seen["kingdoms"]] == ["1", "2"]
    assert seen["written"]["peer_ranges"] == {}
    assert "written" not in _run_refresh(app, monkeypatch, "2999-01-01T00:00:00+00:00")  # not due: nothing written


def test_the_migration_makes_the_document_once_and_leaves_one_alone(app):
    import untitledapp.migrations as migrations
    from tests.test_concurrency import _get
    with app.app_context():
        migrations.universe_stats({})
        stored = _get("/universestats")
        assert stored["peer_ranges"] == {} and stored["last_update"] == ""
        _create_item("universe_stats", {"peer_ranges": {"drones_per_star": {"low": 1}}, "last_update": "x"})
        migrations.universe_stats({})  # again: changes nothing
    assert _get("/universestats")["peer_ranges"] == {"drones_per_star": {"low": 1}}
    assert "185_universe_stats" in migrations.all_ids()


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
    assert advice["kind"] == "danger" and advice["hideable"] is True and advice["hidden"] is False
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


def test_unknown_advice_and_a_body_without_hidden_are_refused(app, client, jwt1):
    hide = lambda body: client.post("/api/advisors/hide", headers=_auth(jwt1), data=json.dumps(body))
    assert hide({"id": "no_such_advice", "hidden": True}).status_code == 400
    assert hide({"id": "hangars_full"}).status_code == 400
    assert client.get("/api/preferences", headers=_auth(jwt1)).get_json()["hidden_advice"] == []


def test_danger_can_be_hidden_for_good_too(app, client, jwt1):
    _set_up()  # a new kingdom: under the break-even
    response = client.post("/api/advisors/hide", headers=_auth(jwt1),
                           data=json.dumps({"id": "defense_under_break_even", "hidden": True}))
    assert response.status_code == 200, response.get_json()
    advice = client.get("/api/advisors", headers=_auth(jwt1)).get_json()["advice"]
    [item] = [item for item in advice if item["id"] == "defense_under_break_even"]
    assert item["hideable"] is True and item["hidden"] is True


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


# ----------------------------------------------------------------------------------------------- the stats (#239)

def _stats_by_key(sections):
    return {row["key"]: row["value"] for section in sections for row in section["rows"]}


def test_the_stats_split_strength_by_role_and_per_star():
    hour = 3600 / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
    kd = {"kdId": "1", "race": "Xo", "stars": 100, "fuel": 1000, "money": 500, "drones": 300,
          "units": {"attack": 10, "defense": 20, "flex": 5, "recruits": 0, "engineers": 0},
          "generals_out": [{"attack": 10, "return_time": "x"}],
          "structures": {"homes": 40, "mines": 30, "fuel_plants": 10, "drone_factories": 5},
          "income": {"money": {"net": 1000, "population": 400, "mines": 300, "bonus": 0.0, "siphons_in": 999},
                     "fuel": {"net": -10, "population": 40, "bonus": 0.0}},
          "projects_points": {}, "projects_max_points": {}, "funding": {"settle": 0},
          "siphons_running": {
              "7|a": {"from": "7", "until": (NOW + datetime.timedelta(hours=3)).isoformat(), "rate": 10},
              "8|b": {"from": "8", "until": (NOW + datetime.timedelta(hours=1)).isoformat(), "rate": 20},
              "9|c": {"from": "9", "until": (NOW - datetime.timedelta(minutes=1)).isoformat(), "rate": 500},  # ended
          }}
    stats = _stats_by_key(uaadv.kingdom_stats(kd, epochs=48, now=NOW, max_hangar=100, used_hangar=25))
    attack, flex = uas.UNITS["attack"]["offense"], uas.UNITS["flex"]["offense"]
    assert stats["pure_offense"] == 20 * attack  # home and out
    assert stats["flex_offense"] == 5 * flex
    assert stats["total_offense"] == 20 * attack + 5 * flex
    # Upgraded units count with their line: heavy attackers with attackers, big flexers with flexers.
    upgraded = _stats_by_key(uaadv.kingdom_stats({**kd, "units": {**kd["units"], "heavy_attack": 4, "big_flex": 2}},
                                                 epochs=48, now=NOW))
    assert upgraded["pure_offense"] == 20 * attack + 4 * uas.UNITS["heavy_attack"]["offense"]
    assert upgraded["flex_offense"] == 5 * flex + 2 * uas.UNITS["big_flex"]["offense"]
    assert stats["total_offense_per_star"] == stats["total_offense"] / 100
    assert stats["pure_defense"] == uaadv.home_defense({**kd, "units": {"defense": 20}})
    assert stats["total_defense"] == uaadv.home_defense(kd)
    assert stats["income_per_star"] == 1000 * hour / 100
    assert stats["income_structures_share"] == 0.75  # homes, mines and drone factories
    assert stats["pop_income_per_home"] == 400 * hour / 40
    fuel_plant = uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"]
    assert stats["pop_income_per_home_fuelled"] == pytest.approx(400 * hour / 40 / (1 + 40 / (40 * fuel_plant)))
    assert stats["mine_income_per_mine"] == 300 * hour / 30
    # From the rates of the siphons still running, not the payments credited at the last tick (siphons_in).
    assert stats["siphon_income"] == pytest.approx(30 * hour)
    assert stats["siphon_income_per_drone_factory"] == pytest.approx(30 * hour / 5)
    assert stats["fuel_hours_left"] == pytest.approx(1000 / (10 * hour))
    assert stats["hangar_used"] == 0.25
    assert stats["idle_money_hours"] == pytest.approx(500 / (1000 * hour))
    assert stats["break_even_defense_per_star"] == strategy.break_even_per_star(48)
    assert "primitives_defense_per_star" not in stats


def test_a_figure_with_nothing_to_divide_by_is_left_empty():
    kd = {"kdId": "1", "race": "Xo", "stars": 0, "fuel": 10, "money": 0, "units": {}, "structures": {},
          "income": {"money": {"net": 0}, "fuel": {"net": 5}}, "projects_points": {}, "projects_max_points": {}}
    stats = _stats_by_key(uaadv.kingdom_stats(kd, epochs=0, now=NOW))
    for key in ("total_offense_per_star", "pop_income_per_home", "pop_income_per_home_fuelled",
                "mine_income_per_mine", "siphon_income_per_drone_factory", "fuel_hours_left", "hangar_used", "idle_money_hours"):
        assert stats[key] is None, key


def test_the_stats_route_answers_for_the_callers_own_kingdom(app, client, jwt1):
    _set_up()
    answer = client.get("/api/kingdomstats", headers=_auth(jwt1)).get_json()
    titles = [section["title"] for section in answer["sections"]]
    assert titles == ["Military", "Economy", "What your advisors watch"]
    rows = [row for section in answer["sections"] for row in section["rows"]]
    assert all(set(row) == {"key", "label", "value", "format", "tip"} for row in rows)
    assert _stats_by_key(answer["sections"])["break_even_defense_per_star"] > 0
