"""Times are compared as datetimes (``shared.utc``), never as ISO strings, whose order is not time order (#42)."""
import datetime

import untitledapp.shared as uas

UTC = datetime.timezone.utc


def test_utc_reads_every_iso_form_of_the_same_instant():
    instant = datetime.datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    for text in ("2026-11-20T12:00:00+00:00", "2026-11-20T12:00:00Z", "2026-11-20T12:00:00.000000+00:00",
                 "2026-11-20T13:00:00+01:00", "2026-11-20T12:00:00"):
        assert uas.utc(text) == instant, text
    assert uas.utc(instant) == instant
    assert uas.utc(datetime.datetime(2026, 11, 20, 13, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))) == instant


def test_string_order_is_not_time_order_but_utc_order_is():
    half_past, on_the_second = "2026-11-20T12:00:00.500000+00:00", "2026-11-20T12:00:00Z"
    assert half_past < on_the_second  # what comparing the text would conclude
    assert uas.utc(half_past) > uas.utc(on_the_second)
    in_paris, in_london = "2026-11-20T13:30:00+02:00", "2026-11-20T12:00:00+00:00"
    assert in_paris > in_london
    assert uas.utc(in_paris) < uas.utc(in_london)


def test_is_after_treats_an_empty_cursor_as_the_start_of_time():
    assert uas.is_after("2026-11-20T12:00:00+00:00", "")
    assert uas.is_after("2026-11-20T12:00:00+00:00", None)
    assert not uas.is_after("", "2026-11-20T12:00:00+00:00")
    assert not uas.is_after("2026-11-20T12:00:00Z", "2026-11-20T12:00:00+00:00")
    assert uas.is_after("2026-11-20T12:00:01Z", "2026-11-20T12:00:00+00:00")
    assert not uas.is_after("2026-11-20T13:30:00+02:00", "2026-11-20T12:00:00+00:00")


def test_queues_sort_by_time_not_by_text(app, client, jwt1):
    """The Build page's queue is soonest first even when the stored strings are written differently."""
    from tests.test_concurrency import KD_ID, _create_item, _set_up_kingdom
    _set_up_kingdom(money=0)
    _create_item(f"structures_{KD_ID}", {"structures": [
        {"time": "2030-01-01T13:30:00+02:00", "homes": 1},  # 11:30 UTC, first; but last as text
        {"time": "2030-01-01T12:00:00+00:00", "homes": 2},
    ]})
    queue = client.get("/api/structures", headers={"Authorization": f"Bearer {jwt1}"}).get_json()["top_queue"]
    assert [entry["homes"] for entry in queue] == [1, 2]
