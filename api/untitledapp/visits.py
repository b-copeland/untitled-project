"""
When a player was last here, for the "since you were last here" summary (#206).

Kept on the kingdom's ``notifs_<id>`` document, which ``/api/notifs`` already reads every time the page polls it (only
while the tab is shown), so recording a visit adds no read:

* ``last_active``: the last time the player had the game open, written at most every ``ACTIVE_WRITE_SECONDS``.
* ``visit_started``: when the current visit began, the first poll after a gap of ``VISIT_GAP_SECONDS`` or more.
* ``visit_since``: the ``last_active`` before that gap, the end of the previous visit.

Decided against the document with ``occ.update``, so two tabs polling at once record one visit. Documents from before
these fields lack them: the first poll starts them, and until a gap there is no previous visit.
"""
import datetime

import flask

import untitledapp.occ as occ
import untitledapp.shared as uas

ACTIVE_WRITE_SECONDS = 5 * 60
VISIT_GAP_SECONDS = 60 * 60
# How long into a visit the summary still counts from the previous one; after that it shows the last hour.
SUMMARY_FROM_VISIT_SECONDS = 60 * 60


def _notifs_path(kd_id):
    return f"/kingdom/{kd_id}/notifs"


def touch(notifs, now):
    """The ``set`` payload that records activity at ``now`` on ``notifs``, or None if nothing needs writing."""
    last = notifs.get("last_active")
    if last and (now - uas.utc(last)).total_seconds() < ACTIVE_WRITE_SECONDS:
        return None
    fields = {"last_active": now.isoformat()}
    if not last or (now - uas.utc(last)).total_seconds() >= VISIT_GAP_SECONDS:
        fields["visit_started"] = now.isoformat()
        if last:
            fields["visit_since"] = last
    return fields


def record(kd_id, notifs, now=None):
    """
    Record that the player is here, deciding against ``notifs`` as just read (it carries its ``_etag``). Returns the
    notifs as they are after it. Never fails the caller: a busy document is left for the next poll.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    after = {"notifs": notifs}

    def decide(document):
        fields = touch(document, now)
        # What the caller gets: the newest copy decided against, with what this writes. A second tab that finds the
        # visit already recorded gets the first tab's fields.
        after["notifs"] = {**document, **(fields or {})}
        return ({"set": fields}, None) if fields else (None, None)

    try:
        occ.update(_notifs_path(kd_id), decide, document=notifs)
    except (occ.Busy, RuntimeError) as error:
        flask.current_app.logger.warning("Could not record a visit for %s: %s", kd_id, error)
        return notifs
    return after["notifs"]


def read_and_record(kd_id, now=None):
    """Read the kingdom's notifs and ``record`` the visit. ``{}`` if they can not be read."""
    try:
        notifs = occ.read(_notifs_path(kd_id))
    except (ValueError, TypeError):
        return {}
    if not isinstance(notifs, dict) or "_etag" not in notifs:
        return {}
    return record(kd_id, notifs, now)


def summary_window(notifs, now):
    """
    ``(since, since_visit)``: the end of the previous visit while the current one began less than
    ``SUMMARY_FROM_VISIT_SECONDS`` ago, otherwise an hour ago.
    """
    started, since = notifs.get("visit_started"), notifs.get("visit_since")
    if started and since and (now - uas.utc(started)).total_seconds() < SUMMARY_FROM_VISIT_SECONDS:
        return uas.utc(since), True
    return now - datetime.timedelta(hours=1), False
