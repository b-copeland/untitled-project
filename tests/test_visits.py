"""When a player was last here (visits.py): recorded on the notifs document, at most every few minutes, once per gap."""
import datetime
import json
import threading

import untitledapp.visits as visits
from untitledapp import REQUESTS_SESSION
from tests.test_concurrency import FUNCTION_URL, KD_ID, _create_item, _set_up_kingdom

NOW = datetime.datetime(2026, 11, 23, 12, tzinfo=datetime.timezone.utc)


def ago(minutes):
    return (NOW - datetime.timedelta(minutes=minutes)).isoformat()


def test_a_first_poll_starts_a_visit_with_no_previous_one():
    assert visits.touch({}, NOW) == {"last_active": NOW.isoformat(), "visit_started": NOW.isoformat()}


def test_polls_within_a_few_minutes_write_nothing():
    assert visits.touch({"last_active": ago(4)}, NOW) is None


def test_a_poll_later_in_the_same_visit_only_moves_last_active():
    assert visits.touch({"last_active": ago(10)}, NOW) == {"last_active": NOW.isoformat()}


def test_a_poll_after_an_hour_away_starts_a_new_visit_from_the_old_last_active():
    assert visits.touch({"last_active": ago(90)}, NOW) == {
        "last_active": NOW.isoformat(), "visit_started": NOW.isoformat(), "visit_since": ago(90)}


def test_the_summary_counts_from_the_last_visit_for_the_first_hour_of_a_visit():
    notifs = {"visit_started": ago(20), "visit_since": ago(200)}
    assert visits.summary_window(notifs, NOW) == (NOW - datetime.timedelta(minutes=200), True)
    later = {"visit_started": ago(70), "visit_since": ago(200)}
    assert visits.summary_window(later, NOW) == (NOW - datetime.timedelta(hours=1), False)
    assert visits.summary_window({}, NOW) == (NOW - datetime.timedelta(hours=1), False)


def _notifs():
    return json.loads(REQUESTS_SESSION.get(f"{FUNCTION_URL}/kingdom/{KD_ID}/notifs").text)


def test_two_tabs_polling_at_once_record_one_visit(app):
    with app.app_context():
        _set_up_kingdom(1000)
        _create_item(f"notifs_{KD_ID}", {"last_active": ago(120), "news_kingdom": 3})
        gate = threading.Barrier(2)
        results = []

        def poll():
            with app.app_context():
                notifs = _notifs()
                gate.wait()
                results.append(visits.record(KD_ID, notifs, NOW))

        threads = [threading.Thread(target=poll) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stored = _notifs()

    assert stored["visit_since"] == ago(120)  # not overwritten by the second tab with the first tab's NOW
    assert stored["last_active"] == NOW.isoformat()
    assert stored["news_kingdom"] == 3        # the counters are left alone
    assert all(result["visit_since"] == ago(120) for result in results)


def test_the_notifs_route_records_the_visit(app, client, jwt1):
    with app.app_context():
        _set_up_kingdom(1000)
    response = client.get("/api/notifs", headers={"Authorization": f"Bearer {jwt1}"})

    assert response.status_code == 200
    assert "last_active" in response.json and "visit_started" in response.json
    with app.app_context():
        assert _notifs()["last_active"] == response.json["last_active"]
