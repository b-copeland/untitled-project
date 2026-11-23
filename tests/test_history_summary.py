"""
The "since you were last here" summary (#206): the units and structures breakdowns the refresh records with each
history point, and ``/api/history/summary``, which compares the history point nearest before a time with the kingdom now.
"""
import datetime
import json

import untitledapp.getters as uag
import untitledapp.refresh as refresh
from untitledapp import REQUESTS_SESSION
from tests.kingdoms import kingdom
from tests.test_concurrency import KD_ID, _create_item, _set_up_kingdom

T0 = datetime.datetime(2026, 11, 22, 8, tzinfo=datetime.timezone.utc)


def at(hours):
    return (T0 + datetime.timedelta(hours=hours)).isoformat()


def points(*values, start=0):
    """One point per half hour from ``start`` hours."""
    return [{"time": at(start + i / 2), "value": value} for i, value in enumerate(values)]


def _history():
    return json.loads(REQUESTS_SESSION.get(
        uag.flask.current_app.config["AZURE_FUNCTION_ENDPOINT"] + f"/kingdom/{KD_ID}/history",
        headers={"x-functions-key": uag.flask.current_app.config["AZURE_FUNCTION_KEY"]},
    ).text)["history"]


def test_a_history_point_breaks_down_units_owned_and_structures_built():
    kd = kingdom(
        units={"attack": 10, "defense": 0, "engineers": 7},
        generals_out=[{"attack": 5, "flex": 2, "return_time": at(1)}],
        structures={"homes": 3, "mines": 0},
    )

    values = uag._history_values(kd)

    assert values["units"] == {"attack": 15, "flex": 2}  # out with generals counts, engineers and zeros do not
    assert values["structures"] == {"homes": 3}
    assert values["engineers"] == 7


def test_the_summary_compares_the_point_nearest_before_the_time_with_the_kingdom_now():
    history = {
        "stars": points(300, 310, 320, 330),
        "networth": points(1000, 1100, 1200, 1300),
        "population": points(50, 60, 70, 80),
        "drones": points(0, 0, 5, 5),
        "engineers": points(1, 1, 1, 1),
        "units": points({"attack": 10}, {"attack": 10}, {"attack": 20, "flex": 1}, {"attack": 20, "flex": 1}),
        "structures": points({"homes": 1}, {"homes": 2}, {"homes": 2}, {"homes": 2}),
    }
    kd = kingdom(stars=340, networth=1400, population=90, drones=5,
                 units={"attack": 25, "engineers": 1}, structures={"homes": 2, "mines": 4})

    summary = uag._history_summary(history, kd, T0 + datetime.timedelta(minutes=40))  # the 30-minute point

    assert summary["from"] == at(0.5)
    assert summary["changes"]["stars"] == {"from": 310, "to": 340}
    assert summary["changes"]["drones"] == {"from": 0, "to": 5}
    assert summary["units"] == {"attack": {"from": 10, "to": 25}}  # no flex then, and none now: not listed
    assert summary["structures"] == {"mines": {"from": 0, "to": 4}}  # homes did not change
    assert summary["units_from"] == at(0.5)


def test_a_time_before_the_history_starts_uses_its_first_point():
    history = {"stars": points(300, 310, start=5), "units": points({"attack": 1}, start=5)}

    summary = uag._history_summary(history, kingdom(stars=320), T0)

    assert summary["from"] == at(5)
    assert summary["changes"]["stars"] == {"from": 300, "to": 320}


def test_a_history_from_before_the_breakdowns_has_no_unit_or_structure_changes():
    history = {"stars": points(300)}  # an old document: no units or structures series

    summary = uag._history_summary(history, kingdom(units={"attack": 5}), T0)

    assert summary["units"] == {} and summary["units_from"] is None
    assert summary["structures"] == {} and summary["structures_from"] is None


def test_the_refresh_adds_the_breakdowns_to_an_old_history_and_keeps_only_the_newest(app, monkeypatch):
    with app.app_context():
        _set_up_kingdom(1000, units={**kingdom()["units"], "attack": 4}, structures={**kingdom()["structures"], "homes": 2})
        # A history document from before the breakdowns.
        _create_item(f"history_{KD_ID}", {"history": {key: [] for key in (
            "networth", "stars", "population", "drones", "engineers", "max_offense", "max_defense")}})
        monkeypatch.setattr(refresh, "_history_breakdown_points", lambda: 2)
        kd_info = uag._get_kd_info(KD_ID)
        for hours in range(3):
            refresh._update_history(kd_info, T0 + datetime.timedelta(hours=hours))

        history = _history()

    assert [point["time"] for point in history["units"]] == [at(1), at(2)]  # trimmed to the newest two
    assert history["units"][-1]["value"] == {"attack": 4}
    assert history["structures"][-1]["value"] == {"homes": 2}
    assert len(history["stars"]) == 3  # the other series keep the whole round


def test_a_function_app_that_refuses_the_breakdowns_still_records_the_rest(app, monkeypatch):
    with app.app_context():
        _set_up_kingdom(1000)
        kd_info = uag._get_kd_info(KD_ID)
        sent = []
        real_patch = REQUESTS_SESSION.patch

        def old_function_app(url, **kwargs):
            body = json.loads(kwargs["data"])
            sent.append(sorted(body["history"]))
            if "units" in body["history"]:
                return type("Response", (), {"status_code": 500, "text": "not updated"})()
            return real_patch(url, **kwargs)

        monkeypatch.setattr(REQUESTS_SESSION, "patch", old_function_app)
        refresh._update_history(kd_info, T0)
        monkeypatch.setattr(REQUESTS_SESSION, "patch", real_patch)
        history = _history()

    assert len(sent) == 2 and "units" not in sent[1]
    assert len(history["stars"]) == 1


def test_the_route_needs_a_time_and_answers_for_the_callers_kingdom(app, client, jwt1):
    with app.app_context():
        _set_up_kingdom(1000, stars=310)
        _create_item(f"history_{KD_ID}", {"history": {"stars": points(300), "units": [], "structures": []}})
    headers = {"Authorization": f"Bearer {jwt1}"}

    assert client.get("/api/history/summary", headers=headers).status_code == 400
    assert client.get("/api/history/summary?since=yesterday", headers=headers).status_code == 400
    response = client.get(f"/api/history/summary?since={T0.isoformat().replace('+', '%2B')}", headers=headers)

    assert response.status_code == 200
    assert response.json["changes"]["stars"] == {"from": 300, "to": 310}
