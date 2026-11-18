"""
Helpers for tests that run the game's sums on a whole kingdom: a complete kingdom document with only the fields a test
cares about changed, and one stretch of income from the refresh's ``_kingdom_with_income``.
"""
import copy
import datetime

import untitledapp.shared as uas
from tests.test_concurrency import _set_up_kingdom

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def kingdom(**overrides):
    """
    A set-up kingdom "1" (Xo, 300 stars, no structures, units or projects worth anything) with ``overrides`` applied.
    Nested dicts in ``overrides`` are merged into the starting ones, so ``structures={"mines": 10}`` keeps the rest.
    """
    kd = copy.deepcopy(uas.INITIAL_KINGDOM_STATE["kingdom"])
    kd.update({
        "kdId": "1",
        "name": "Test Kingdom",
        "race": "Xo",
        "last_income": START.isoformat(),
        "projects_points": {key: 0 for key in uas.PROJECTS},
        "completed_projects": [],
    })
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(kd.get(key), dict):
            kd[key] = {**kd[key], **value}
        else:
            kd[key] = value
    return kd


def with_bonus(project, share=1.0):
    """``projects_points`` overrides that give a continuous project ``share`` of its max bonus (at 300 stars)."""
    return {project: uas.PROJECTS_FUNCS[project](300) * share}


def income(app, kd, epochs=1.0, state=None, mobis=None):
    """
    The kingdom after ``epochs`` of income, as the refresh computes it. Sets up kingdom "1" in the store first, since
    the income step reads its siphons.
    """
    import untitledapp.refresh as refresh

    state = state or {"state": {"active_policies": []}}
    later = START + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * epochs)
    kd = copy.deepcopy(kd)
    with app.app_context():
        _set_up_kingdom(0)
        return refresh._kingdom_with_income(kd, uas.project_bonuses(kd), state, later, None, mobis or [])
