"""
Last-known intel: what a kingdom saw of another when a reveal of it ended.

When a reveal ends (the refresh expires it, or a galaxymate stops sharing), the holder gets a snapshot of the fields
that reveal showed, as they were then, in its ``lastknown_<kd_id>`` document:

    {"known": {target: {category: {"ended": <iso>, "values": {...the category's fields...}}}}}

The pages that show other kingdoms show these values where no reveal is active, with how long ago the reveal ended.
Active intel always comes first: a category that is revealed now is left out (``visible``), and the pages prefer a
value from the live fields over a snapshot. One document per kingdom, not per pair: see decision 0009.

The functions that build and filter snapshots are plain; ``read`` and ``record`` are the only storage calls.
"""
import collections
import json

import flask

from untitledapp import REQUESTS_SESSION
import untitledapp.shared as uas


# Per-project numbers that are mostly zero: the pages show a missing project as 0, so a snapshot drops the zeros
# (projects are most of a snapshot's size). The rest stay exact, since the bonuses are worked out from them.
_MOSTLY_ZERO = ("projects_points", "projects_assigned")


def _compact(values):
    for field in _MOSTLY_ZERO:
        if isinstance(values.get(field), dict):
            values[field] = {key: number for key, number in values[field].items() if number}
    return values


def snapshot(kd_info, categories, ended):
    """What ``categories`` of intel show of ``kd_info``, as entries ending at ``ended`` (an ISO time)."""
    return {
        category: {"ended": ended,
                   "values": _compact(uas.revealed_fields(kd_info, [category], public=False, derived=False))}
        for category in categories
        if uas.REVEAL_FIELDS.get(category)  # production has no kingdom fields to keep
    }


def visible(known_of_target, active_categories):
    """
    The snapshots of one target to show alongside what is revealed now: those of categories not revealed now, with
    what is worked out from them (projects' bonuses) added, as the live fields have it.
    """
    shown = {}
    for category, entry in (known_of_target or {}).items():
        if category in active_categories:
            continue
        values = dict(entry.get("values", {}))
        if category == "projects":
            uas.with_project_bonuses(values)
        shown[category] = {**entry, "values": values}
    return shown


def ended_by_holder(ended_intel):
    """``[(holder, target, category, ended), ...]`` grouped as ``{holder: {target: {category: ended}}}``, each keeping
    its latest end."""
    grouped = collections.defaultdict(lambda: collections.defaultdict(dict))
    for holder, target, category, ended in ended_intel:
        current = grouped[str(holder)][str(target)].get(category)
        grouped[str(holder)][str(target)][category] = max(current, ended) if current else ended
    return grouped


def read(kd_id):
    """``kd_id``'s last-known intel: target to category to entry (empty for a kingdom that has none)."""
    app = flask.current_app
    response = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/lastknown',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    )
    if response.status_code != 200:
        return {}
    return json.loads(response.text).get("known", {})


def record(holder, new_known):
    """Merge ``{target: {category: entry}}`` into ``holder``'s last-known intel (each category keeps the later end)."""
    if not new_known:
        return
    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{holder}/lastknown',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"new_known": new_known}, default=str),
    )


def record_ended(ended_intel, kingdom_of):
    """
    Snapshot every ended reveal in ``ended_intel`` (``(holder, target, category, ended)``), one write per holder.
    ``kingdom_of(kd_id)`` gives a target's document (None if it is gone, and it is skipped).
    """
    for holder, targets in ended_by_holder(ended_intel).items():
        new_known = {}
        for target, categories in targets.items():
            kd_info = kingdom_of(target)
            if not kd_info:
                continue
            entries = {}
            for category, ended in categories.items():
                entries.update(snapshot(kd_info, [category], ended))
            if entries:
                new_known[target] = entries
        record(holder, new_known)
