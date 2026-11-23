"""
Reactive rules (issue #35): "when this happens to me, do that". Things happening to a kingdom, not things it wants
done on a timer: that is the Schedule and its repeating operations (``recurring.py``).

A rule has a **when** and a **then**:

* when: the kingdom was **attacked**, **spied on** or hit by **missiles** (optionally only when it lost), or its fuel
  will **run out** within a number of hours. The first three are read from ``events``, which the attack, the spy
  operation and the missile strike stamp on the defender (``shared.note_event``); the last from the kingdom's own fuel
  and fuel income. Only what the player can see: who did it is known only when the news names them.
* then: **switch settings** (shields, auto spending, auto attack, auto rob) for a number of hours, then back; or,
  against whoever did it, **spy** on them or **fire missiles** at them, as a scheduled action that runs at once.

A rule fires once for each new event (or, for fuel, once each time the condition starts to hold), and not again
within its cooldown. Switched settings go back when their hours are up, except the ones the player has changed
meanwhile, which are left as the player set them.

The refresh runs ``step`` on the kingdom it is about to write, so checking rules costs nothing: no read and no write
of its own. A spy or missile reaction adds one schedule entry to that write; the refresh's schedule step runs it.
"""
import copy
import datetime
import uuid

import flask
import flask_praetorian

import untitledapp.build as uab
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import alive_required

bp = flask.Blueprint("rules", __name__)

WHEN_KINDS = ("attacked", "spied", "missiles", "fuel_low")
THEN_KINDS = ("settings", "spy_sender", "missiles_sender")
# The build targets a rule can switch, each a whole split (shares of 0 to 1 adding up to at most 1), and the check the
# kingdom must pass when the rule fires: a unit or project can be locked, or a one-time project done, by then.
TARGET_CHECKS = {
    "structures_target": lambda target, kd: uab._validate_structures_target(target),
    "units_target": uab._validate_mobis_target,
    "projects_target": uab._validate_projects_target,
}
SETTINGS_FIELDS = ("shields", "auto_spending", "auto_attack_enabled", "auto_rob_enabled") + tuple(TARGET_CHECKS)
TARGET_NAMES = {"structures_target": "structure targets", "units_target": "unit targets",
                "projects_target": "project targets"}
SPENDING_KEYS = ("settle", "structures", "military", "engineers")
MISSILE_KEYS = ("planet_busters", "star_busters", "galaxy_busters")
WHEN_TEXT = {
    "attacked": "you were attacked", "spied": "you were spied on", "missiles": "missiles hit you",
    "fuel_low": "your fuel was running low",
}


def _hours(value, low, high, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: enter a number of hours")
    if not low <= number <= high:
        raise ValueError(f"{label} must be {low:g} to {high:g} hours")
    return number


def _settings(raw):
    """The settings a rule switches to, checked and in the stored units (fractions). Raises ValueError."""
    settings = {}
    for field, value in (raw or {}).items():
        if field not in SETTINGS_FIELDS:
            raise ValueError(f"A rule can not change {field}")
        if field == "shields":
            levels = {kind: float(value.get(kind) or 0) / 100 for kind in uas.SHIELD_KINDS if kind in value}
            ok, message = uam._validate_shields(levels)
            if not ok or not levels:
                raise ValueError(message or "Choose the shields to set")
            settings[field] = levels
        elif field in TARGET_CHECKS:
            keys = uas.INITIAL_KINGDOM_STATE["kingdom"][field]
            unknown = [key for key in (value or {}) if key not in keys]
            if unknown:
                raise ValueError(f"There is no {unknown[0]} to target")
            # The whole split: anything not given is 0, so the rule means the same whatever the targets are then.
            shares = {key: float((value or {}).get(key) or 0) / 100 for key in keys}
            if any(share < 0 or share > 1 for share in shares.values()) or sum(shares.values()) > 1 + 1e-9:
                raise ValueError(f"The {TARGET_NAMES[field]} must be 0% to 100% and add up to at most 100%")
            settings[field] = shares
        elif field == "auto_spending":
            shares = {key: float(value.get(key) or 0) / 100 for key in SPENDING_KEYS}
            ok, message = uam._validate_spending(shares)
            if not ok:
                raise ValueError(message)
            settings[field] = shares
        else:
            settings[field] = bool(value)
    if not settings:
        raise ValueError("Choose at least one setting to switch")
    return settings


def make_rule(req, now=None):
    """``(rule, None)`` for a valid request, or ``(None, message)``. Percent fields are 0-100 as the form sends them."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    when, then = dict(req.get("when") or {}), dict(req.get("then") or {})
    try:
        if when.get("kind") not in WHEN_KINDS:
            raise ValueError("Choose what the rule reacts to")
        clean_when = {"kind": when["kind"], "lost_only": bool(when.get("lost_only")) and when["kind"] != "fuel_low"}
        if when["kind"] == "fuel_low":
            clean_when["hours"] = _hours(when.get("hours"), 1, 72, "Fuel left")
        if then.get("kind") not in THEN_KINDS:
            raise ValueError("Choose what the rule does")
        if then["kind"] != "settings" and when["kind"] == "fuel_low":
            raise ValueError("Low fuel has nobody to react against: switch settings instead")
        clean_then = {"kind": then["kind"]}
        if then["kind"] == "settings":
            clean_then["settings"] = _settings(then.get("settings"))
            clean_then["hours"] = _hours(then.get("hours"), 0.5, 72, "How long")
        elif then["kind"] == "spy_sender":
            if then.get("operation") not in uas.REVEAL_OPERATIONS:
                raise ValueError("Choose an intel operation")
            drones = float(then.get("drones_pct") or 0)
            if not 0 < drones <= 100:
                raise ValueError("Send between 1% and 100% of your drones")
            clean_then.update(operation=then["operation"], drones_pct=drones)
        else:
            counts = {key: int(then.get(key) or 0) for key in MISSILE_KEYS}
            if any(count < 0 for count in counts.values()) or sum(counts.values()) <= 0:
                raise ValueError("Choose how many missiles to fire")
            clean_then.update(counts)
        cooldown = _hours(req.get("cooldown_hours", 6), 0, 72, "Cooldown")
    except ValueError as problem:
        return None, str(problem)
    return {
        "id": str(uuid.uuid4()),
        "when": clean_when,
        "then": clean_then,
        "cooldown_hours": cooldown,
        "created": now.isoformat(),
        "state": {"seen": now.isoformat(), "fired_at": None, "until": None, "armed": True,
                  "applied": None, "previous": None, "fires": 0, "last": None},
    }, None


# ---------------------------------------------------------------------------------------------- in the refresh


def fuel_hours_left(kd):
    """Hours until the fuel runs out at the kingdom's fuel income, or None if it is not falling."""
    net = ((kd.get("income") or {}).get("fuel") or {}).get("net")
    if net is None or net >= 0:
        return None
    return max(kd.get("fuel", 0), 0) / -net * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600


def _shields_heading(kd):
    """Each shield's level, or the level it is climbing to: what the player last asked for."""
    levels = dict(kd.get("shields") or {})
    for kind, climb in (kd.get("shields_climb") or {}).items():
        levels[kind] = climb["to"]
    return levels


def _current(kd, field):
    if field == "shields":
        return _shields_heading(kd)
    return copy.deepcopy(kd.get(field))


def _set(kd, changes, field, value, now):
    """Write ``value`` for ``field`` into ``changes``, the shields through the climb (a raise climbs, a cut is at once)."""
    if field == "shields":
        merged = {**kd, **changes}
        changes["shields"], changes["shields_climb"] = uas.change_shields(merged, value, now)
    else:
        changes[field] = copy.deepcopy(value)


def _same(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return all(abs(float(a.get(key, 0)) - float(b.get(key, 0))) < 1e-9 for key in set(a) | set(b))
    return a == b


def _triggered(rule, kd, now):
    """``(fire, sender, state)``: whether the rule's condition has newly happened, who did it, and its new state."""
    state, when = dict(rule["state"]), rule["when"]
    if when["kind"] == "fuel_low":
        hours = fuel_hours_left(kd)
        low = kd.get("fuel", 0) <= 0 or (hours is not None and hours < when["hours"])
        fire = low and state.get("armed", True)
        state["armed"] = not low
        return fire, None, state
    event = (kd.get("events") or {}).get(when["kind"])
    if not event or not uas.is_after(event["at"], state.get("seen") or rule["created"]):
        return False, None, state
    state["seen"] = event["at"]
    if when.get("lost_only") and not event.get("lost"):
        return False, None, state
    return True, event.get("by"), state


def step(kd, now, schedule_handlers):
    """
    The kingdom's rules at ``now``: ``(changes, notes)``, the fields to write with the tick and the lines for the
    player's news. ``schedule_handlers`` are the Schedule's ``_schedule_<type>`` functions, for reactions against a
    sender. Pure: it reads nothing and writes nothing, so the refresh can run it again on a retry.
    """
    rules = kd.get("rules") or []
    if not rules:
        return {}, []
    changes, notes, new_rules = {}, [], []
    schedule = list(kd.get("schedule") or [])
    for rule in rules:
        rule = {**rule, "state": dict(rule["state"])}
        state, then = rule["state"], rule["then"]
        view = {**kd, **changes}

        # Settings switched for a while go back when the time is up, unless the player has changed them since.
        if state.get("until") and uas.utc(state["until"]) <= now:
            restored = []
            for field, applied in (state.get("applied") or {}).items():
                if _same(_current(view, field), applied):
                    _set(view, changes, field, state["previous"][field], now)
                    view = {**kd, **changes}
                    restored.append(field)
            if restored:
                notes.append(f"Your rule for when {WHEN_TEXT[rule['when']['kind']]} has ended: settings are back as they were.")
            state.update(until=None, applied=None, previous=None)

        fire, sender, new_state = _triggered(rule, view, now)
        state.update(new_state)
        cooling = state.get("fired_at") and now < uas.utc(state["fired_at"]) + datetime.timedelta(hours=rule["cooldown_hours"])
        if fire and not cooling:
            outcome = None
            if then["kind"] == "settings":
                fresh = not state.get("until")  # not already switched: what to go back to is what is set now
                if fresh:
                    state["previous"] = {field: _current(view, field) for field in then["settings"]}
                skipped = []
                for field, value in then["settings"].items():
                    if field in TARGET_CHECKS:
                        ok, message = TARGET_CHECKS[field](value, view)
                        if not ok:
                            skipped.append(f"{TARGET_NAMES[field]} not changed ({message.rstrip('.')})")
                            if fresh:
                                state["previous"].pop(field, None)
                            continue
                    _set(view, changes, field, value, now)
                    view = {**kd, **changes}
                state["applied"] = {field: _current(view, field) for field in then["settings"] if field in state["previous"]}
                state["until"] = (now + datetime.timedelta(hours=then["hours"])).isoformat()
                outcome = f"settings switched for {then['hours']:g} hours" + "".join(f"; {why}" for why in skipped)
            elif not sender:
                outcome = "nothing done: you do not know who it was"
            elif len(schedule) >= uas.GAME_CONFIG["BASE_MAX_SCHEDULE_ENTRIES"]:
                outcome = "nothing done: your schedule is full"
            else:
                if then["kind"] == "spy_sender":
                    kind = "intelspy"
                    options = {"target": sender, "operation": then["operation"], "drones_pct": then["drones_pct"],
                               "max_tries": 1, "shielded": False, "share_to_galaxy": False}
                else:
                    kind = "missiles"
                    options = {"target": sender, **{key: then.get(key, 0) for key in MISSILE_KEYS}}
                # A moment before now, so the schedule step right after this tick's write finds it due.
                ok, entry, message = schedule_handlers[kind](
                    id=str(uuid.uuid4()), time=(now - datetime.timedelta(seconds=1)).isoformat(), options=options,
                    kd_info=view)
                if ok:
                    schedule.append(entry)
                    changes["schedule"] = sorted(schedule, key=lambda item: uas.utc(item["time"]))
                    outcome = "spying on whoever did it" if kind == "intelspy" else "firing missiles at whoever did it"
                else:
                    outcome = f"nothing done: {message}"
            state["fired_at"] = now.isoformat()
            state["fires"] = state.get("fires", 0) + 1
            state["last"] = {"time": now.isoformat(), "outcome": outcome}
            notes.append(f"Your rule for when {WHEN_TEXT[rule['when']['kind']]} fired: {outcome}.")
        new_rules.append(rule)
    if new_rules != rules:
        changes["rules"] = new_rules
    return changes, notes


# ------------------------------------------------------------------------------------------------------ the routes


@bp.route('/api/rules', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def add_rule():
    kd_id = flask_praetorian.current_user().kd_id
    rule, message = make_rule(flask.request.get_json(force=True) or {})
    if rule is None:
        return flask.jsonify({"message": message}), 400

    def decide(kd_info):
        current = kd_info.get("rules") or []
        # Checked now as well as when it fires, so a target on a locked unit or project is refused at once.
        for field, value in rule["then"].get("settings", {}).items():
            if field in TARGET_CHECKS:
                ok, problem = TARGET_CHECKS[field](value, kd_info)
                if not ok:
                    raise occ.Rejected(problem)
        limit = uas.GAME_CONFIG["BASE_MAX_RULES"]
        if len(current) >= limit:
            raise occ.Rejected(f"You can not have more than {limit} rules")
        return {"rules": current + [rule]}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return flask.jsonify({"message": "Rule added", "status": "success"}), 200


@bp.route('/api/rules/cancel', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def cancel_rule():
    """Removes a rule. Settings it switched stay as they are now."""
    kd_id = flask_praetorian.current_user().kd_id
    rule_id = (flask.request.get_json(force=True) or {}).get("id")

    def decide(kd_info):
        current = kd_info.get("rules") or []
        kept = [rule for rule in current if rule["id"] != rule_id]
        if len(kept) == len(current):
            raise occ.Rejected("That rule is not there")
        return {"rules": kept}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return flask.jsonify({"message": "Rule removed", "status": "success"}), 200
