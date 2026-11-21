"""
Last-known intel (``lastknown.py``): a reveal that ends leaves the holder a snapshot of what it showed, and the pages
that show other kingdoms get those snapshots for the categories not revealed now.
"""
import datetime
import json

import pytest

import untitledapp.getters as uag
import untitledapp.lastknown as uala
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from untitledapp import REQUESTS_SESSION
from tests.test_concurrency import FUNCTION_URL, _create_item, _get

NOW = datetime.datetime.now(datetime.timezone.utc)
PAST = (NOW - datetime.timedelta(hours=1)).isoformat()
FUTURE = (NOW + datetime.timedelta(hours=5)).isoformat()


def _kingdom(kd_id, **overrides):
    kd = {**uas.INITIAL_KINGDOM_STATE["kingdom"], "kdId": kd_id, "name": f"kd{kd_id}", "race": "Xo",
          "last_income": (NOW - datetime.timedelta(minutes=1)).isoformat(), "projects_points": {key: 0 for key in uas.PROJECTS}, "completed_projects": []}
    kd.update(overrides)
    return kd


def _set_up(galaxies=None, revealed_1=None, kingdom_1=None, kingdom_2=None):
    """Kingdoms 1 and 2 (in galaxies 1:1 and 1:2 unless ``galaxies`` says otherwise), in a game that has started."""
    game_start = (NOW - datetime.timedelta(days=1)).isoformat()
    _create_item("state", {"state": {"game_start": game_start, "game_end": (NOW + datetime.timedelta(days=30)).isoformat(),
                                     "active_policies": []}})
    _create_item("galaxies", {"galaxies": galaxies or {"1:1": ["1"], "1:2": ["2"]}})
    for kd_id, overrides in (("1", kingdom_1 or {}), ("2", kingdom_2 or {})):
        for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
            if table == "kingdom":
                _create_item(f"kingdom_{kd_id}", _kingdom(kd_id, **overrides))
            else:
                _create_item(f"{table}_{kd_id}", initial_state)
    _create_item("revealed_1", revealed_1 or uas.INITIAL_KINGDOM_STATE["revealed"])


def _last_known(kd_id):
    return _get(f"/kingdom/{kd_id}/lastknown")["known"]


def _put_last_known(kd_id, known):
    response = REQUESTS_SESSION.patch(f"{FUNCTION_URL}/kingdom/{kd_id}/lastknown", data=json.dumps({"new_known": known}))
    assert response.status_code == 200, response.text


# --- the plain functions -------------------------------------------------------------------------------------------


def test_a_snapshot_holds_what_the_category_shows_and_nothing_public_or_hidden():
    kd = _kingdom("2", drones=1234, spy_attempts=7, money=999)
    assert uala.snapshot(kd, ["drones"], PAST) == {"drones": {"ended": PAST, "values": {"drones": 1234, "spy_attempts": 7}}}
    military = uala.snapshot(kd, ["military"], PAST)["military"]["values"]
    assert set(military) == {"units", "generals_available", "generals_out"}
    # Projects keep the stored fields only; the bonuses are worked out again when shown.
    projects = uala.snapshot(kd, ["projects"], PAST)
    assert set(projects["projects"]["values"]) == set(uas.REVEAL_FIELDS["projects"]) | {"units"}
    assert projects["projects"]["values"]["units"] == {"engineers": kd["units"]["engineers"]}
    kd = {**kd, "projects_points": {**kd["projects_points"], "pop_bonus": 12.7}}
    projects = uala.snapshot(kd, ["projects"], PAST)
    assert projects["projects"]["values"]["projects_points"] == {"pop_bonus": 12.7}  # no zeros
    shown = uala.visible(projects, set())["projects"]["values"]
    assert shown["current_bonuses"] == uas.project_bonuses(kd) and shown["engineers"] == kd["units"]["engineers"]
    assert "current_bonuses" not in projects["projects"]["values"]  # visible does not change what is stored
    assert uala.snapshot(kd, ["not a category"], PAST) == {}


def test_revealed_fields_is_what_the_filter_has_always_shown():
    kd = _kingdom("2")
    assert set(uas.revealed_fields(kd, [])) == set(uas.PUBLIC_KINGDOM_FIELDS) & set(kd)
    assert set(uas.revealed_fields(kd, ["kingdom"])) == (set(uas.PUBLIC_KINGDOM_FIELDS) & set(kd)) | set(uas.REVEAL_FIELDS["kingdom"])
    # Projects add the engineers to the units without dropping the army military intel shows.
    both = uas.revealed_fields(kd, ["military", "projects"])
    assert both["units"] == kd["units"]


def test_visible_leaves_out_the_categories_revealed_now():
    known = {"drones": {"ended": PAST, "values": {}}, "military": {"ended": PAST, "values": {}}}
    assert uala.visible(known, {"military"}) == {"drones": known["drones"]}
    assert uala.visible(None, set()) == {}


def test_ended_reveals_are_grouped_by_holder_keeping_the_latest_end():
    grouped = uala.ended_by_holder([("1", "2", "drones", PAST), ("1", "2", "drones", FUTURE), ("1", "3", "military", PAST),
                                    ("4", "2", "drones", PAST)])
    assert grouped == {"1": {"2": {"drones": FUTURE}, "3": {"military": PAST}}, "4": {"2": {"drones": PAST}}}


# --- the refresh ---------------------------------------------------------------------------------------------------


def _refresh(app, kd_id="1", when=None):
    with app.app_context():
        refresh._refresh_kd(kd_id, _get("/state"), when or NOW, False)


def test_a_reveal_that_ends_leaves_a_snapshot_of_what_it_showed(app):
    _set_up(
        revealed_1={**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {"2": {"drones": PAST, "military": FUTURE}}},
        kingdom_1={"next_resolve": {**uas.INITIAL_KINGDOM_STATE["kingdom"]["next_resolve"], "revealed": PAST}},
        kingdom_2={"drones": 4321, "spy_attempts": 3},
    )

    _refresh(app)

    assert _get("/kingdom/1/revealed")["revealed"] == {"2": {"military": FUTURE}}
    assert _last_known("1") == {"2": {"drones": {"ended": PAST, "values": {"drones": 4321, "spy_attempts": 3}}}}


def test_a_second_refresh_records_nothing_more(app, monkeypatch):
    _set_up(
        revealed_1={**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {"2": {"drones": PAST}}},
        kingdom_1={"next_resolve": {**uas.INITIAL_KINGDOM_STATE["kingdom"]["next_resolve"], "revealed": PAST}},
    )
    _refresh(app)
    recorded = []
    monkeypatch.setattr(uala, "record", lambda holder, known: recorded.append((holder, known)))
    _refresh(app, when=NOW + datetime.timedelta(minutes=1))
    assert recorded == []


def test_the_tick_snapshots_each_target_as_it_left_it_without_reading_it_again(app, client, monkeypatch):
    """refresh_data snapshots once every kingdom is done, from the kingdom documents it already has."""
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    _set_up(
        revealed_1={**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {"2": {"drones": PAST}}},
        kingdom_1={"next_resolve": {**uas.INITIAL_KINGDOM_STATE["kingdom"]["next_resolve"], "revealed": PAST}},
        kingdom_2={"drones": 50},
    )
    state = _get("/state")
    state["state"].update({"election_start": "2999-01-01T00:00:00+00:00", "election_end": "",
                           "next_history": "2999-01-01T00:00:00+00:00"})
    monkeypatch.setattr(uag, "_get_state", lambda: state)
    monkeypatch.setattr(uag, "_get_kingdoms", lambda: ["1", "2"])
    monkeypatch.setattr(refresh, "_resolve_empires", lambda scores, now: None)
    monkeypatch.setattr(refresh, "_resolve_clusters", lambda empires, now, context: None)
    monkeypatch.setattr(refresh, "_resolve_scores", lambda scores, now, context=None: None)
    calls = []
    original = REQUESTS_SESSION.request

    def request(method, url, *args, **kwargs):
        calls.append((method.upper(), url.split("/api", 1)[1].split("?")[0]))
        return original(method, url, *args, **kwargs)

    monkeypatch.setattr(REQUESTS_SESSION, "request", request)

    response = client.get("/api/refreshdata", headers={"Refresh-Secret": "secret"})
    tick = list(calls)  # the tick's calls, not the checks below

    assert response.status_code == 200, response.get_data(as_text=True)
    written = _get("/kingdom/2")
    assert _last_known("1")["2"]["drones"]["values"]["drones"] == written["drones"]
    assert tick.count(("GET", "/kingdom/2")) == 1  # the tick's own read of kingdom 2, nothing more
    assert tick.count(("PATCH", "/kingdom/1/lastknown")) == 1


# --- what the pages get --------------------------------------------------------------------------------------------


def test_the_kingdom_route_adds_snapshots_only_for_what_is_not_revealed_now(app, client, jwt1):
    _set_up(revealed_1={**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {"2": {"military": FUTURE}}},
            kingdom_2={"drones": 77})
    _put_last_known("1", {"2": {
        "drones": {"ended": PAST, "values": {"drones": 10, "spy_attempts": 1}},
        "military": {"ended": PAST, "values": {"units": {}, "generals_available": 0, "generals_out": []}},
    }})

    info = client.get("/api/kingdom/2", headers={"Authorization": f"Bearer {jwt1}"}).json

    assert info["last_known"] == {"drones": {"ended": PAST, "values": {"drones": 10, "spy_attempts": 1}}}
    assert "drones" not in info  # the live value stays hidden
    assert info["units"] == _get("/kingdom/2")["units"]  # military is revealed now: the live army, not the snapshot


def test_no_snapshots_when_everything_is_revealed_now(app, client, jwt1):
    _set_up(revealed_1={**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {"2": {"drones": FUTURE}}})
    _put_last_known("1", {"2": {"drones": {"ended": PAST, "values": {"drones": 10}}}})
    info = client.get("/api/kingdom/2", headers={"Authorization": f"Bearer {jwt1}"}).json
    assert "last_known" not in info


def test_another_kingdoms_snapshots_are_never_shown(app, client, jwt1):
    _set_up()
    _put_last_known("2", {"2": {"drones": {"ended": PAST, "values": {"drones": 10}}}})
    _put_last_known("3", {"2": {"drones": {"ended": PAST, "values": {"drones": 10}}}})
    info = client.get("/api/kingdom/2", headers={"Authorization": f"Bearer {jwt1}"}).json
    assert "last_known" not in info and "drones" not in info


def test_a_galaxy_shows_snapshots_with_the_army_estimate_as_it_was(app, client, jwt1):
    _set_up()
    army = {**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "attack": 1000}
    _put_last_known("1", {"2": {"military": {"ended": PAST, "values": {
        "units": army, "generals_available": 2, "generals_out": []}}}})

    info = client.get("/api/galaxy/1:2", headers={"Authorization": f"Bearer {jwt1}"}).json["2"]

    assert "military_estimate" not in info
    known = info["last_known"]["military"]["values"]
    assert known["military_estimate"] == uag._military_estimate({"units": army, "generals_out": []})


def test_projects_intel_alone_gives_no_army_estimate(app, client, jwt1):
    _set_up(revealed_1={**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {"2": {"projects": FUTURE}}})
    info = client.post("/api/kingdomsinfo", json={"kingdoms": ["2"]}, headers={"Authorization": f"Bearer {jwt1}"}).json["2"]
    assert "units" in info and "military_estimate" not in info


def test_the_display_routes_read_the_last_known_document_once(app, client, jwt1, monkeypatch):
    _set_up()
    calls = []
    original = REQUESTS_SESSION.request

    def request(method, url, *args, **kwargs):
        calls.append((method.upper(), url.split("/api", 1)[1].split("?")[0]))
        return original(method, url, *args, **kwargs)

    monkeypatch.setattr(REQUESTS_SESSION, "request", request)
    client.post("/api/kingdomsinfo", json={"kingdoms": ["1", "2"]}, headers={"Authorization": f"Bearer {jwt1}"})
    assert calls.count(("GET", "/kingdom/1/lastknown")) == 1


# --- a galaxymate who stops sharing ----------------------------------------------------------------------------------


def test_a_galaxymate_who_stops_sharing_leaves_a_snapshot_of_everything(app, client, jwt1):
    _set_up(galaxies={"1:1": ["1", "2"]}, kingdom_1={"drones": 600})
    share = client.post("/api/share/2", headers={"Authorization": f"Bearer {jwt1}"})
    assert share.status_code == 200, share.get_data(as_text=True)
    assert _last_known("2") == {}

    unshare = client.post("/api/unshare/2", headers={"Authorization": f"Bearer {jwt1}"})

    assert unshare.status_code == 200
    known = _last_known("2")["1"]
    assert set(known) == set(uas.REVEAL_FIELDS)
    assert known["drones"]["values"]["drones"] == 600
    # Unsharing again (nothing shared any more) leaves the snapshot as it was.
    ended = known["drones"]["ended"]
    client.post("/api/unshare/2", headers={"Authorization": f"Bearer {jwt1}"})
    assert _last_known("2")["1"]["drones"]["ended"] == ended
