"""
Strength forecasts: a kingdom's offense and defense over time, for its own Status page and for another kingdom's page.

Three timelines, each a list of points (a time and the strength then):

- ``generals``: the army at home now, then as each general that is out comes home with its units;
- ``production``: the army at home now, then as training lands by each forecast horizon (``QUEUE_FORECAST_EPOCHS``);
- ``combined``: both, at every time either has.

Offense counts the generals at home at that time; defense counts the military shields. The military shields and the
military efficiency (the Military Bonus project) are what the kingdom has, as far as the caller knows them, or what the
caller asks about instead (a what-if), and otherwise the largest there can be. Another kingdom needs military intel
(its units and generals); production intel adds the training. Bonuses that depend on who attacks (war, denouncing,
peace) are left out, as on the Status page.
"""
import datetime

import flask
import flask_praetorian

import untitledapp.getters as uag
import untitledapp.inputs as uin
import untitledapp.shared as uas

bp = flask.Blueprint("strength", __name__)


def _units(values):
    return {key: values.get(key, 0) or 0 for key in uas.UNITS}


def _add(total, more):
    for key in uas.UNITS:
        total[key] += more.get(key, 0) or 0


def timelines(kd, mobis_queue, start_time, shields, military_bonus, fuelless):
    """
    The three timelines of ``kd`` (its ``units``, ``generals_available``, ``generals_out`` and ``race``) from
    ``start_time``. ``mobis_queue`` is its training queue, or None when that is not known: then there is no
    ``production`` or ``combined`` timeline.
    """
    home = _units(kd.get("units", {}))
    generals_home = int(kd.get("generals_available", 0) or 0)
    generals = sorted(
        ((uas.utc(general["return_time"]), general) for general in kd.get("generals_out", []) or []),
        key=lambda item: item[0],
    )
    training = sorted(((uas.utc(entry["time"]), entry) for entry in mobis_queue or []), key=lambda item: item[0])
    horizons = uas.GAME_CONFIG["QUEUE_FORECAST_EPOCHS"]
    epoch = datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])

    def point(when, with_generals, with_training, **label):
        units = dict(home)
        count = generals_home
        if with_generals:
            for back, general in generals:
                if back <= when:
                    _add(units, general)
                    count += 1
        if with_training:
            for lands, entry in training:
                if lands < when:  # as the queue forecasts count it: what lands before the horizon
                    _add(units, entry)
        return {
            "time": when.isoformat(),
            **label,
            "generals_home": count,
            "offense": uag._calc_max_offense(units, military_bonus=military_bonus, other_bonuses=0, generals=count,
                                             fuelless=fuelless, lumina=kd.get("race") == "Lumina"),
            "defense": uag._calc_max_defense(units, military_bonus=military_bonus, other_bonuses=0, shields=shields,
                                             fuelless=fuelless, gaian=kd.get("race") == "Gaian"),
        }

    general_times = [(back, {"kind": "general", "general": index}) for index, (back, _) in enumerate(generals)
                     if back > start_time]
    horizon_times = [(start_time + epochs * epoch, {"kind": "horizon", "epochs": epochs}) for epochs in horizons]
    now = (start_time, {"kind": "now"})

    result = {"generals": [point(when, True, False, **label) for when, label in [now] + general_times]}
    if mobis_queue is not None:
        result["production"] = [point(when, False, True, **label) for when, label in [now] + horizon_times]
        both = sorted(general_times + horizon_times, key=lambda item: item[0])
        result["combined"] = [point(when, True, True, **label) for when, label in [now] + both]
    return result


def _setting(req, field, known, maximum):
    """A what-if value (a percentage in the request) as a fraction, else ``known``, else ``maximum``."""
    asked = uin.number(req.get(field), field, minimum=0, maximum=round(maximum * 100, 6), blank=-1)
    if asked >= 0:
        return asked / 100
    return known if known is not None else maximum


def forecast(kd_id, req):
    """What ``/api/strengthforecast`` answers for ``kd_id`` asking with ``req``."""
    target = req.get("target")
    if target is not None and not isinstance(target, str):
        raise uin.BadInput("target must be a kingdom id")
    state = uag._get_state()
    if target in (None, "", str(kd_id)):
        kd = uag._get_kd_info(kd_id)
        mobis_queue = uag._get_mobis_queue(kd_id)
        known_shields = uas.shields_now(kd).get("military", 0)
        known_bonus = uas.project_bonuses(kd)["military_bonus"] or 0
        fuel = kd.get("fuel")
    else:
        revealed = uag._get_revealed(kd_id)
        galaxies_inverted, _ = uag._get_galaxies_inverted()
        if target not in galaxies_inverted:
            raise uin.BadInput("There is no kingdom with that id")
        kd = uag._get_max_kd_info(target, kd_id, revealed, galaxies_inverted=galaxies_inverted)
        if "generals_out" not in kd:
            raise uin.BadInput("Reveal this kingdom's military to forecast its strength")
        categories = uag._revealed_categories(target, kd_id, revealed, galaxies_inverted)
        production_known = categories is None or "production" in categories
        mobis_queue = uag._read_queue(target, "mobis") if production_known else None
        known_shields = uas.shields_now(kd).get("military", 0) if "shields" in kd else None
        known_bonus = (kd["current_bonuses"]["military_bonus"] or 0) if "current_bonuses" in kd else None
        fuel = kd.get("fuel")

    max_shields = uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"]
    max_bonus = uas.PROJECTS["military_bonus"]["max_bonus"]
    shields = _setting(req, "shields", known_shields, max_shields)
    military_bonus = _setting(req, "military_bonus", known_bonus, max_bonus)
    fuelless = fuel is not None and fuel <= 0
    return {
        "timelines": timelines(kd, mobis_queue, uag._forecast_start(state), shields, military_bonus, fuelless),
        "shields": {"value": shields, "known": known_shields, "max": max_shields},
        "military_bonus": {"value": military_bonus, "known": known_bonus, "max": max_bonus},
        "fuelless": fuelless,
        "fuel_known": fuel is not None,
        "production_known": mobis_queue is not None,
    }


@bp.route("/api/strengthforecast", methods=["POST"])
@flask_praetorian.auth_required
def strength_forecast():
    """
    Offense and defense over time. Body: ``target`` (another kingdom's id; leave it out for your own), and optionally
    ``shields`` and ``military_bonus`` as percentages to see what they would change.
    """
    kd_id = flask_praetorian.current_user().kd_id
    return flask.jsonify(forecast(kd_id, uin.body(flask.request))), 200
