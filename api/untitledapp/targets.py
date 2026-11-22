"""
Empire targets: kingdoms an empire's leadership marks for its members to take apart, and the spoils fund that rewards
everyone who took part.

The emperor (the leader of the empire's ruling galaxy) and up to ``TARGET_MAX_DELEGATES`` kingdoms the emperor names
(the delegates) manage the targets. A target must be a kingdom of an empire this empire is at war with, and an empire has
at most one target per galaxy in it. Each target is marked for one or more actions (``TARGET_ACTIONS`` in shared.py: intel, kidnaps, bombing homes, sabotaging fuel plants, missiles, failed
and successful attacks), each with a points multiplier leadership sets.

While a kingdom is a target:

* every intel operation an empire member wins on it is copied to every kingdom in the empire;
* intel cuts from the galaxy's intel market do not apply to attacks on it;
* a member who takes a marked action earns participation points on it, in proportion to the damage done
  (``points_for``);
* a share of each successful attack's stars and money (``fund_share``) goes into the target's spoils fund instead of
  to the attacker, and every star missiles destroy goes into it;
* if it dies, its remaining stars and money go into the fund, in the share the empire has earned (``remains_share``:
  its points against ``TARGET_REMAINS_POINTS_PER_STAR`` for each star the target had when it was marked), and the
  target ends.

The fund is paid out only when the target ends: leadership removes it, it dies, or the war ends. Then each participant
gets a part in proportion to their points, but never more stars than ``TARGET_MAX_PAYOUT_STARS_SHARE`` of their own
land (``star_cap``). Paying out only once per target is what makes that cap hold: a fund paid out in many small payouts
would pass it. What a cap holds back, and the unearned part of a dead target's land and money, leave the game. A
kingdom leadership removed can not be marked again for ``TARGET_REMARK_COOLDOWN_EPOCHS``, so removing and re-marking it
is a slow way to pay out more often.

All of that holds only while the two empires are at war: an action on a target whose kingdom is no longer in an empire
at war with this one (its galaxy left, say) counts for nothing, and when the war ends (a surrender) every target in the
other empire ends with its final payout (``end_war``).

Points last for the whole life of the target. With no participants, the fund is lost. Ended targets go into the
empire's history.

Everything lives in one document per empire, ``empire_targets_<empire>``, which is the decision point of every change
here (``occ.update``). Its fields, each read with a default since the function app creates it as ``{"id"}``:

* ``delegates``: the kingdoms the emperor named.
* ``targets``: target kingdom to ``{target, stars_at_start, actions, fund_share, created_at, created_by, points, fund,
  intel}``: ``actions`` maps each marked action to its points multiplier; ``points`` are per participant; ``fund`` is
  ``{stars, money}``; ``intel`` is category to when the empire's intel on the target ends.
* ``removed``: kingdom to when leadership removed it as a target; it can not be marked again until
  ``TARGET_REMARK_COOLDOWN_EPOCHS`` later. Entries past that are dropped when a target is next added.
* ``history``: the newest ``TARGET_HISTORY_LENGTH`` ended targets, newest first, with what each participant was paid.

The ``empires`` document carries a hint, ``targets`` (a list of kingdom ids) on each empire, so an attack, spy operation
or missile strike knows without another read whether its target is one. It is a superset of the targets: a target is
added to it before the targets document and taken out after, so a crash between the two costs at most a wasted read.
``/api/empires`` leaves it out, so nobody outside the empire learns who it targets.
"""
import copy
import datetime
import json
import math

import flask
import flask_praetorian
from flask_sock import ConnectionClosed

import untitledapp.getters as uag
import untitledapp.news as uan
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import REQUESTS_SESSION, SOCK_HANDLERS, alive_required

bp = flask.Blueprint("targets", __name__)

ACTIONS = list(uas.TARGET_ACTIONS)
FIELDS = ("delegates", "targets", "removed", "history")
_EPSILON = 1e-9


# --- pure rules: plain dicts in, plain values out -----------------------------------------------------------------

_utc = uas.utc  # compare times as datetimes, never as strings


def normalize(document):
    """The document's fields, each with its default, as a private copy."""
    document = document or {}
    return {
        "delegates": [str(kd) for kd in (document.get("delegates") or [])],
        "targets": copy.deepcopy(document.get("targets") or {}),
        "removed": {str(kd): when for kd, when in (document.get("removed") or {}).items()}
        if isinstance(document.get("removed"), dict) else {},
        "history": copy.deepcopy(document.get("history") or []),
    }


def written(document):
    return {field: document[field] for field in FIELDS}


def new_target(target, actions, fund_share, by, now, stars=0):
    return {
        "target": str(target),
        # Its land when it was marked: what the points that earn its land and money at its death are measured against.
        "stars_at_start": stars,
        "actions": dict(actions),
        "fund_share": fund_share,
        "created_at": now.isoformat(),
        "created_by": by,
        "points": {},
        "fund": {"stars": 0, "money": 0},
        "paid": {},
        "intel": {},
    }


def parse_actions(value):
    """
    The actions a request marks, as ``{action: multiplier}``. ``value`` maps action keys to multipliers (a number, or
    ``true`` for 1). Raises ValueError for an unknown action, a multiplier out of range, or no action at all.
    """
    if not isinstance(value, dict):
        raise ValueError("Choose the actions to mark the target for")
    maximum = uas.GAME_CONFIG["TARGET_MAX_POINTS_MULTIPLIER"]
    actions = {}
    for key, multiplier in value.items():
        if key not in uas.TARGET_ACTIONS:
            raise ValueError(f"Unknown action: {key}")
        if multiplier is True:
            multiplier = 1.0
        if multiplier is False or multiplier is None:
            continue
        try:
            multiplier = float(multiplier)
        except (TypeError, ValueError):
            raise ValueError(f"The points multiplier for {uas.TARGET_ACTIONS[key]['name']} must be a number")
        if multiplier != multiplier or multiplier < 0 or multiplier > maximum + _EPSILON:
            raise ValueError(f"Points multipliers go from 0 to {maximum:g}")
        actions[key] = multiplier
    if not actions:
        raise ValueError("Mark the target for at least one action")
    return actions


def parse_fund_share(value):
    """A fund share sent as a percent, as a fraction. Missing means the default."""
    if value is None or value == "":
        return uas.GAME_CONFIG["TARGET_DEFAULT_FUND_SHARE"]
    share = float(value) / 100
    maximum = uas.GAME_CONFIG["TARGET_MAX_FUND_SHARE"]
    if share != share or share < 0 or share > maximum + _EPSILON:
        raise ValueError(f"The spoils fund share goes from 0% to {maximum:.0%}")
    return share


def points_for(action, measures, multiplier=1.0):
    """The points ``measures`` of damage (``{measure: amount}``) earn for ``action`` at ``multiplier``."""
    rates = uas.TARGET_ACTIONS[action]["points"]
    return sum(max(measures.get(measure, 0), 0) * rate for measure, rate in rates.items()) * multiplier


def fund_split(spoils, share):
    """
    ``(attacker_spoils, fund)`` from an attacker's spoils (``{"stars": n, ..., "funding": {category: n}}``): the fund
    takes ``share`` of the stars, of the money and of each funding category, rounded down, and holds the money and
    funding together as money. Population and fuel stay with the attacker.
    """
    attacker = copy.deepcopy(spoils)
    fund = {"stars": 0, "money": 0}
    if share <= 0:
        return attacker, fund
    for key in ("stars", "money"):
        if key not in spoils:
            continue
        taken = math.floor(max(spoils[key], 0) * share)
        attacker[key] = spoils.get(key, 0) - taken
        fund[key] += taken
    for category, amount in (spoils.get("funding") or {}).items():
        taken = math.floor(max(amount, 0) * share)
        attacker["funding"][category] = amount - taken
        fund["money"] += taken
    return attacker, fund


def payout_shares(points, fund):
    """Each participant's part of ``fund`` (``{stars, money}``), in proportion to ``points``, rounded down."""
    total = sum(value for value in points.values() if value > 0)
    if total <= 0:
        return {}
    shares = {}
    for kd_id, value in points.items():
        if value <= 0:
            continue
        part = {key: math.floor(fund.get(key, 0) * value / total) for key in ("stars", "money")}
        if part["stars"] or part["money"]:
            shares[kd_id] = part
    return shares


def star_cap(stars):
    """The most stars a kingdom of ``stars`` receives from one payout: ``TARGET_MAX_PAYOUT_STARS_SHARE`` of its land."""
    return math.floor(max(stars, 0) * uas.GAME_CONFIG["TARGET_MAX_PAYOUT_STARS_SHARE"])


def capped(shares, caps):
    """
    ``(shares, stars over the caps)``: no participant gets more stars than ``caps[kd_id]`` (see ``star_cap``). The stars
    over a cap leave the game; they are not shared out among the others.
    """
    kept, over = {}, 0
    for kd_id, part in shares.items():
        stars = min(part["stars"], max(caps.get(kd_id, part["stars"]), 0))
        over += part["stars"] - stars
        if stars or part["money"]:
            kept[kd_id] = {"stars": stars, "money": part["money"]}
    return kept, over


def remains_share(entry, total_points=None):
    """
    The share of a dead target's land and money that goes into its empire's fund: in proportion to the points the
    empire earned on it, against ``TARGET_REMAINS_POINTS_PER_STAR`` points for every star it had when it was marked,
    up to all of it. So an empire that marks a dying kingdom and lands only the last blow gets little.
    """
    if total_points is None:
        total_points = sum(value for value in entry["points"].values() if value > 0)
    needed = uas.GAME_CONFIG["TARGET_REMAINS_POINTS_PER_STAR"] * max(entry.get("stars_at_start") or 0, 1)
    return min(max(total_points, 0) / needed, 1.0)


def _take(fund, shares):
    """The fund once ``shares`` are paid out of it."""
    return {key: fund.get(key, 0) - sum(part[key] for part in shares.values()) for key in ("stars", "money")}


def _add_lost(entry, stars=0, money=0):
    """Count what left the game instead of being paid: stars over a cap, or the part of a dead target's land and money
    the empire had not earned."""
    lost = entry.setdefault("lost", {"stars": 0, "money": 0})
    lost["stars"] = lost.get("stars", 0) + stars
    lost["money"] = lost.get("money", 0) + money


def _add_paid(entry, shares):
    for kd_id, part in shares.items():
        paid = entry["paid"].setdefault(kd_id, {"stars": 0, "money": 0})
        for key in ("stars", "money"):
            paid[key] += part[key]


def end(document, target, reason, by, now, remains=None, caps=None):
    """
    End ``target``: add the empire's earned share (``remains_share``) of ``remains`` (a dead target's land and money,
    ``{stars, money}``), pay out the whole fund to the participants held to their caps, and move the target to the
    history. What is not earned, over a cap, or left by rounding leaves the game. Returns the shares paid. Changes
    ``document``.
    """
    entry = document["targets"].pop(target)
    if remains:
        share = remains_share(entry)
        earned = {key: math.floor(max(remains.get(key, 0), 0) * share) for key in ("stars", "money")}
        _add_lost(entry, stars=remains.get("stars", 0) - earned["stars"], money=remains.get("money", 0) - earned["money"])
        for key, amount in earned.items():
            entry["fund"][key] = entry["fund"].get(key, 0) + amount
    shares = payout_shares(entry["points"], entry["fund"])
    leftover = _take(entry["fund"], shares)
    shares, over = capped(shares, caps or {})
    _add_lost(entry, stars=leftover["stars"] + over, money=leftover["money"])
    lost = entry["lost"]
    _add_paid(entry, shares)
    if reason == "removed":
        document["removed"][target] = now.isoformat()
    record = {
        "target": target,
        "actions": entry["actions"],
        "fund_share": entry["fund_share"],
        "created_at": entry["created_at"],
        "ended_at": now.isoformat(),
        "reason": reason,
        "ended_by": by,
        "points": entry["points"],
        "paid": entry["paid"],
        # What left the game: stars over the caps, the unearned part of a dead target's land and money, what rounding
        # leaves, and with no participants, the whole fund.
        "lost": lost,
    }
    document["history"] = ([record] + document["history"])[:uas.GAME_CONFIG["TARGET_HISTORY_LENGTH"]]
    return shares


def record_damage(entry, action, measures, fund, kd_id):
    """
    Add what one action did to the target: points for ``kd_id`` if the target is marked for ``action`` (None for
    none), and ``fund`` to the spoils fund. Returns the points earned.
    """
    earned = 0.0
    if action is not None and action in entry["actions"]:
        earned = points_for(action, measures, entry["actions"][action])
        if earned > 0:
            entry["points"][kd_id] = entry["points"].get(kd_id, 0) + earned
    for key, amount in (fund or {}).items():
        entry["fund"][key] = entry["fund"].get(key, 0) + amount
    return earned


def record_intel(entry, categories, until, kd_id, now):
    """
    Note that the empire has ``categories`` of intel on the target until ``until``. Points (if the target is marked for
    intel) only for the categories it did not have, so spying for what is already known earns nothing. Returns
    ``(points earned, the categories that were new)``.
    """
    new = [category for category in categories
           if entry["intel"].get(category) is None or _utc(entry["intel"][category]) <= now]
    for category in categories:
        stored = entry["intel"].get(category)
        if stored is None or _utc(until) > _utc(stored):
            entry["intel"][category] = until.isoformat() if isinstance(until, datetime.datetime) else until
    earned = record_damage(entry, "intel", {"categories": len(new)}, None, kd_id)
    return earned, new


def remark_at(document, target):
    """When ``target``, removed as a target, can be marked again; None if it was never removed."""
    removed = document["removed"].get(target)
    if removed is None:
        return None
    seconds = uas.GAME_CONFIG["TARGET_REMARK_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
    return _utc(removed) + datetime.timedelta(seconds=seconds)


def target_problem(document, target, empire_kingdoms, max_targets, alive, known, target_empire=None, at_war=False,
                   now=None):
    """See ``_target_problem``; also refuses a kingdom removed as a target less than the cooldown ago."""
    unlocks = remark_at(document, target)
    if now is not None and unlocks is not None and unlocks > now:
        return f"You removed that kingdom as a target recently. It can be marked again in {uas.wait_text(unlocks - now)}"
    return _target_problem(document, target, empire_kingdoms, max_targets, alive, known, target_empire, at_war)


def _target_problem(document, target, empire_kingdoms, max_targets, alive, known, target_empire=None, at_war=False):
    """
    Why ``target`` can not be added as a new target, or None if it can. ``target_empire`` is the target's empire (None:
    it is in none), ``at_war`` whether this empire is at war with it.
    """
    if not known:
        return "There is no such kingdom"
    if target in empire_kingdoms:
        return "You can not target a kingdom in your own empire"
    if not alive:
        return "That kingdom is dead"
    if target_empire is None:
        return "Only kingdoms of an empire you are at war with can be targets, and that kingdom is in no empire"
    if not at_war:
        return "Only kingdoms of an empire you are at war with can be targets"
    if target in document["targets"]:
        return "That kingdom is already a target"
    if len(document["targets"]) >= max_targets:
        return f"Your empire can have at most {max_targets} target(s): one per galaxy in it"
    return None


def catalog():
    """The actions, as the pages show them: name, description, and the points each measure earns."""
    return [{
        "key": key,
        "name": action["name"],
        "desc": action["desc"],
        "points": [{"measure": measure, "name": uas.TARGET_MEASURE_NAMES.get(measure, measure), "points": rate}
                   for measure, rate in action["points"].items()],
    } for key, action in uas.TARGET_ACTIONS.items()]


def view(document, kd_id, empire, is_emperor, names, galaxy_of, max_targets, now, war_on=None):
    """
    What ``kd_id`` sees of its empire's targets. Every member sees everything: it is the empire's own business.
    ``war_on`` is the set of target kingdoms whose empire is at war with this one: on the others, actions count for
    nothing (None: all of them are).
    """
    document = normalize(document)
    name = lambda kd: names.get(kd, f"Kingdom {kd}")  # noqa: E731
    can_manage = is_emperor or kd_id in document["delegates"]

    def participants(points, paid):
        total = sum(value for value in points.values() if value > 0)
        kingdoms = sorted(set(points) | set(paid), key=lambda kd: -points.get(kd, 0))
        return [{
            "kd_id": kd, "name": name(kd), "points": points.get(kd, 0),
            "share": points.get(kd, 0) / total if total > 0 else 0,
            "paid": paid.get(kd, {"stars": 0, "money": 0}),
        } for kd in kingdoms]

    targets = []
    for target, entry in sorted(document["targets"].items(), key=lambda item: item[1]["created_at"]):
        total = sum(value for value in entry["points"].values() if value > 0)
        targets.append({
            "target": target,
            "name": name(target),
            "galaxy": galaxy_of.get(target),
            "at_war": war_on is None or target in war_on,
            "actions": entry["actions"],
            "fund_share": entry["fund_share"],
            "fund": entry["fund"],
            "created_at": entry["created_at"],
            "created_by": entry.get("created_by"),
            "points_total": total,
            # How much of its land and money would go into the fund if it died now.
            "remains_share": remains_share(entry, total),
            "lost": entry.get("lost", {"stars": 0, "money": 0}),
            "my_points": entry["points"].get(kd_id, 0),
            "my_share": entry["points"].get(kd_id, 0) / total if total > 0 else 0,
            "participants": participants(entry["points"], entry["paid"]),
            "intel": {category: until for category, until in entry["intel"].items() if _utc(until) > now},
        })
    history = [{
        **record,
        "name": name(record["target"]),
        "participants": participants(record.get("points", {}), record.get("paid", {})),
    } for record in document["history"]]
    return {
        "empire": empire,
        "is_emperor": is_emperor,
        "can_manage": can_manage,
        "delegates": [{"kd_id": kd, "name": name(kd)} for kd in document["delegates"]],
        "max_delegates": uas.GAME_CONFIG["TARGET_MAX_DELEGATES"],
        "max_targets": max_targets,
        "actions": catalog(),
        "default_fund_share": uas.GAME_CONFIG["TARGET_DEFAULT_FUND_SHARE"],
        "max_fund_share": uas.GAME_CONFIG["TARGET_MAX_FUND_SHARE"],
        "max_multiplier": uas.GAME_CONFIG["TARGET_MAX_POINTS_MULTIPLIER"],
        "max_payout_stars_share": uas.GAME_CONFIG["TARGET_MAX_PAYOUT_STARS_SHARE"],
        # The kingdoms that can not be marked again yet, with when they can.
        "removed": {kd: remark_at(document, kd).isoformat() for kd in document["removed"] if remark_at(document, kd) > now},
        "remark_cooldown_hours": uas.GAME_CONFIG["TARGET_REMARK_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600,
        "targets": targets,
        "history": history,
    }


# --- reading and writing --------------------------------------------------------------------------------------------

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _path(empire):
    return f"/empire/{empire}/targets"


def _send(kd_id, message, status="info", update=("empiretargets",)):
    try:
        SOCK_HANDLERS[kd_id].send(json.dumps({
            "message": message, "status": status, "category": "Targets", "delay": 15000, "update": list(update),
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass


def _news(kd_id, message, time_now):
    import untitledapp.misc as uam  # misc imports this module

    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"time": time_now.isoformat(), "from": "", "news": message, "kind": "targets"}),
    )
    uam._add_notifs(kd_id, ["news_kingdom"])


def hinted(empires_info, empire, target):
    """Whether the empires document says ``empire`` may be targeting ``target`` (the hint is a superset)."""
    if empire is None:
        return False
    return str(target) in (empires_info.get("empires", {}).get(empire, {}).get("targets") or [])


def at_war(empires_info, empire, other):
    """Whether ``empire`` is at war with ``other`` (an empire id, or None for no empire)."""
    if empire is None or other is None:
        return False
    return other in (empires_info.get("empires", {}).get(empire, {}).get("war") or [])


def counts(empires_info, empire, target, empires_inverted):
    """Whether an action by ``empire`` on ``target`` can count for one of its targets: the hint lists it, and the two
    empires are at war. Needs no read: the caller has the empires document in hand."""
    return hinted(empires_info, empire, target) and at_war(empires_info, empire, empires_inverted.get(str(target)))


def empires_targeting(empires_info, target):
    """The empires whose hint lists ``target``."""
    return [empire for empire, info in empires_info.get("empires", {}).items() if str(target) in (info.get("targets") or [])]


def _change_hint(empire, add=None, remove=None):
    def change(empires_document):
        info = empires_document["empires"].get(empire)
        if info is None:
            return None, None
        current = list(info.get("targets") or [])
        hint = [kd for kd in current if kd != remove]
        if add is not None and add not in hint:
            hint.append(add)
        if hint == current:
            return None, None
        info["targets"] = hint
        return {"empires": empires_document["empires"]}, None

    occ.update('/empires', change)


def active_target(empire, target, empires_info, empires_inverted):
    """The target's entry in ``empire``'s targets while the two empires are at war, or None. One read, and only when the
    hint says it may be one."""
    if not counts(empires_info, empire, target, empires_inverted):
        return None
    return normalize(occ.read(_path(empire)))["targets"].get(str(target))


def _empire_kingdoms(empire, empires_info, galaxy_info):
    return [kd for galaxy in empires_info["empires"].get(empire, {}).get("galaxies", []) for kd in galaxy_info.get(galaxy, [])]


def _credit(kd_id, part, message, time_now):
    """Pay a participant's part of a fund: stars, and money spread over auto spending like any spoils."""
    import untitledapp.conquer as uac  # conquer imports this module

    add = uac._credit_spoils({"stars": part["stars"], "money": part["money"]})

    def decide(kd):
        if str(kd.get("status", "")).lower() == "dead":
            return None, False
        return add(kd)[0], True

    try:
        credited = occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Busy:
        credited = False
    if credited:
        _news(kd_id, message, time_now)
        _send(kd_id, message, update=("kingdom", "empiretargets", "news"))
    return credited


def _caps_for(points):
    """Each participant's star cap (``star_cap``), from their kingdom as it is now: one read per participant, cached so a
    retried decision does not read again. A dead participant gets nothing (their share leaves the game)."""
    cache = {}
    for kd_id, value in points.items():
        if value <= 0 or kd_id in cache:
            continue
        kd = occ.read(f'/kingdom/{kd_id}')
        dead = str(kd.get("status", "")).lower() == "dead"
        cache[kd_id] = 0 if dead else star_cap(kd.get("stars", 0))
    return cache


def _caps_reader():
    """``caps(points)``: the caps of these participants, each kingdom read once however often it is asked for."""
    read = {}

    def caps(points):
        missing = {kd: value for kd, value in points.items() if kd not in read}
        read.update(_caps_for(missing))
        return {kd: read[kd] for kd in points if kd in read}
    return caps


def _pay(shares, target_name, time_now, final=False):
    for kd_id, part in shares.items():
        what = f"{part['stars']} stars and {part['money']} money"
        if final:
            message = f"The target {target_name} has ended. You received {what} from its spoils fund."
        else:
            message = f"You received {what} from the spoils fund of the target {target_name}."
        _credit(kd_id, part, message, time_now)


def record_action(empire, target, kd_id, action, measures, fund=None, entry=None):
    """
    Record what ``kd_id`` did to ``target``: points for ``action`` (None: no points, only ``fund``), and ``fund`` into
    the spoils fund. Returns True if the target was still there to take it, so a caller that took a fund share from an
    attacker can give it back if the target ended meanwhile. ``entry`` is the target as the caller read it: if the
    action earns nothing and there is no fund, nothing is written.
    """
    if entry is not None and not fund and (action is None or action not in entry["actions"]):
        return True
    target = str(target)

    def decide(document):
        document = normalize(document)
        current = document["targets"].get(target)
        if current is None:
            return None, False
        earned = record_damage(current, action, measures, fund, kd_id)
        if earned <= 0 and not any((fund or {}).values()):
            return None, True
        return written(document), True

    try:
        return occ.update(_path(empire), decide)
    except occ.Busy:
        return False


def share_intel(empire, target, kd_id, categories, until, empires_info, galaxy_info):
    """
    An intel operation by ``kd_id`` on a target: note the intel on the target (earning points for what was new), and
    copy the reveal to every other kingdom in the empire. Returns the points earned.
    """
    import untitledapp.conquer as uac  # conquer imports this module

    target = str(target)
    now = _now()

    def decide(document):
        document = normalize(document)
        current = document["targets"].get(target)
        if current is None:
            return None, None
        earned, _ = record_intel(current, categories, until, kd_id, now)
        return written(document), earned

    try:
        earned = occ.update(_path(empire), decide)
    except occ.Busy:
        earned = 0
    if earned is None:
        return 0
    app = flask.current_app
    until_iso = until.isoformat() if isinstance(until, datetime.datetime) else until
    names = uag._get_kingdoms()
    for member in _empire_kingdoms(empire, empires_info, galaxy_info):
        if member == kd_id:
            continue
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{member}/revealed',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({"new_revealed": {target: {category: until_iso for category in categories}}}),
        )
        uac._lower_timer(member, "revealed", until_iso)
        _send(member, f"{names.get(kd_id, kd_id)} took {', '.join(categories)} intel on the empire target "
                      f"{names.get(target, target)}: it is shared with you", update=("revealed",))
    return earned


def on_kingdom_death(kd_id, killer=None):
    """
    A kingdom died. If any empire targets it, its remaining stars and money (funding counted as money) go into the
    spoils fund, and the target ends with a final payout. The remains go to the killer's empire if it targets the
    kingdom, otherwise they are split evenly between the empires that do. Taking the remains zeroes them on the dead
    kingdom first, so they are only ever taken once.
    """
    kd_id = str(kd_id)
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
    empires = [empire for empire in empires_targeting(empires_info, kd_id)
               if at_war(empires_info, empire, empires_inverted.get(kd_id))]
    if not empires:
        return
    if killer is not None:
        killer_empire = empires_inverted.get(str(killer))
        if killer_empire in empires:
            empires = [killer_empire]

    def take(kd):
        if str(kd.get("status", "")).lower() != "dead":
            return None, {"stars": 0, "money": 0}
        stars = max(math.floor(kd.get("stars", 0)), 0)
        money = max(math.floor(kd.get("money", 0)), 0) + sum(max(math.floor(v), 0) for v in (kd.get("funding") or {}).values())
        if not stars and not money:
            return None, {"stars": 0, "money": 0}
        return {
            "stars": 0, "money": 0, "funding": {key: 0 for key in (kd.get("funding") or {})},
        }, {"stars": stars, "money": money}

    try:
        remains = occ.update(f'/kingdom/{kd_id}', take)
    except occ.Busy:
        remains = {"stars": 0, "money": 0}
    parts = {empire: {"stars": remains["stars"] // len(empires), "money": remains["money"] // len(empires)}
             for empire in empires}
    first = empires[0]
    parts[first]["stars"] += remains["stars"] - sum(part["stars"] for part in parts.values())
    parts[first]["money"] += remains["money"] - sum(part["money"] for part in parts.values())
    for empire in empires:
        try:
            _end_target(empire, kd_id, "killed", None, remains=parts[empire])
        except (occ.Rejected, occ.Busy):
            # Removed by leadership at the same moment (it was paid out then), or too busy: the attack or strike that
            # killed the kingdom has already happened and must not fail now. That empire's part of the remains is lost.
            pass


def end_war(empire_a, empire_b):
    """
    The war between two empires ended: each one's targets in the other end, paying out their funds. Called after the
    empires document no longer lists the war. Kingdoms whose galaxy has since left the enemy empire are ended too,
    since their targets can no longer count.
    """
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
    for empire, other in ((empire_a, empire_b), (empire_b, empire_a)):
        if not (empires_info.get("empires", {}).get(empire, {}).get("targets")):
            continue
        document = normalize(occ.read(_path(empire)))
        for target in list(document["targets"]):
            if empires_inverted.get(target) == other or not at_war(empires_info, empire, empires_inverted.get(target)):
                try:
                    _end_target(empire, target, "war_ended", None)
                except (occ.Rejected, occ.Busy):
                    pass  # removed meanwhile, or too busy: leadership can still remove it


def _end_target(empire, target, reason, by, remains=None, check=None):
    """End a target (``check(document)`` may refuse), pay out its fund, and take it out of the hint."""
    time_now = _now()
    caps = _caps_reader()

    def decide(document):
        document = normalize(document)
        if target not in document["targets"]:
            raise occ.Rejected("That kingdom is not a target")
        if check is not None:
            check(document)
        shares = end(document, target, reason, by, time_now, remains=remains,
                     caps=caps(document["targets"][target]["points"]))
        return written(document), shares

    shares = occ.update(_path(empire), decide)
    _change_hint(empire, remove=target)
    names = uag._get_kingdoms()
    uan.empire([empire], ended_news(reason, names.get(target, target), names.get(by, by), shares), time_now)
    _pay(shares, names.get(target, target), time_now, final=True)
    return shares


def ended_news(reason, target_name, by_name, shares):
    """The empire's news line for a target that ended: why, and what its fund paid out."""
    why = {
        "removed": f"{by_name} removed the target {target_name}",
        "killed": f"The target {target_name} is dead",
        "war_ended": f"The target {target_name} ended with the war",
    }.get(reason, f"The target {target_name} ended")
    if not shares:
        return f"{why}. Its spoils fund paid out nothing"
    stars = sum(part["stars"] for part in shares.values())
    money = sum(part["money"] for part in shares.values())
    return f"{why}. Its spoils fund paid {stars:,} stars and {money:,} money to {len(shares)} kingdom(s)"


# --- the routes ------------------------------------------------------------------------------------------------------

def _context(kd_id):
    """``(empire, is emperor, empires document, galaxy of each kingdom, kingdoms of each galaxy)`` for ``kd_id``."""
    empires_inverted, empires_info, _, galaxy_info = uag._get_empires_inverted()
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    empire = empires_inverted.get(kd_id)
    is_emperor = False
    if empire is not None:
        ruling = uag._get_empire_politics(empire).get("leader")
        galaxy = galaxies_inverted.get(kd_id)
        if ruling is not None and ruling == galaxy:
            galaxy_politics, _ = uag._get_galaxy_politics(kd_id, galaxy)
            is_emperor = galaxy_politics.get("leader") == kd_id
    return empire, is_emperor, empires_info, galaxies_inverted, galaxy_info


def _must_manage(is_emperor, kd_id):
    def check(document):
        if not (is_emperor or kd_id in document["delegates"]):
            raise occ.Rejected("Only the emperor and their delegates can manage the empire's targets")
    return check


def _answer(payload, status=200):
    return flask.jsonify(payload), status


def _refusal(rejection):
    return _answer({"message": rejection.message}, rejection.status)


def _body():
    body = flask.request.get_json(force=True, silent=True)
    return body if isinstance(body, dict) else {}


def view_for(kd_id):
    empire, is_emperor, empires_info, galaxies_inverted, _ = _context(kd_id)
    if empire is None:
        return {"empire": None, "targets": [], "history": [], "can_manage": False, "is_emperor": False,
                "actions": catalog()}
    document = occ.read(_path(empire))
    max_targets = len(empires_info["empires"][empire]["galaxies"])
    empires_inverted, _, _, _ = uag._get_empires_inverted()
    war_on = {target for target in normalize(document)["targets"]
              if at_war(empires_info, empire, empires_inverted.get(target))}
    payload = view(document, kd_id, empire, is_emperor, uag._get_kingdoms(), galaxies_inverted, max_targets, _now(),
                   war_on=war_on)
    payload["at_war_with"] = list(empires_info["empires"][empire].get("war") or [])
    return payload


@bp.route('/api/empiretargets', methods=['GET'])
@flask_praetorian.auth_required
def empire_targets():
    return _answer(view_for(flask_praetorian.current_user().kd_id))


def add_target(kd_id, target, actions_value, fund_share_value):
    """Mark ``target`` as one of the empire's targets. Returns ``(payload, status)``. The route and the bots both use it."""
    target = str(target)
    try:
        actions = parse_actions(actions_value)
        fund_share = parse_fund_share(fund_share_value)
    except (TypeError, ValueError) as error:
        return {"message": str(error)}, 400
    empire, is_emperor, empires_info, _, galaxy_info = _context(kd_id)
    if empire is None:
        return {"message": "You are not in an empire"}, 400
    names = uag._get_kingdoms()
    known = target in names
    target_info = uag._get_kd_info(target) if known else {}
    alive = known and str(target_info.get("status", "")).lower() != "dead"
    members = set(_empire_kingdoms(empire, empires_info, galaxy_info))
    max_targets = len(empires_info["empires"][empire]["galaxies"])
    empires_inverted, _, _, _ = uag._get_empires_inverted()
    target_empire = empires_inverted.get(target)
    war = at_war(empires_info, empire, target_empire)
    now = _now()

    def decide(document):
        document = normalize(document)
        _must_manage(is_emperor, kd_id)(document)
        problem = target_problem(document, target, members, max_targets, alive, known, target_empire, war, now=now)
        if problem:
            raise occ.Rejected(problem)
        document["removed"] = {kd: when for kd, when in document["removed"].items() if remark_at(document, kd) > now}
        document["targets"][target] = new_target(target, actions, fund_share, kd_id, now,
                                                 stars=math.floor(target_info.get("stars", 0)))
        return written(document), None

    try:
        # Checked once before the hint is touched, so a refusal usually leaves it alone; then the hint first, so that
        # it always lists at least the real targets, and the decision on the document as it is when it lands.
        document = occ.read(_path(empire))
        decide(document)
        _change_hint(empire, add=target)
        occ.update(_path(empire), decide, document=document)
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    uan.empire([empire], f"{names.get(kd_id, kd_id)} marked {names.get(target, target)} as a target", now)
    for member in members:
        if member != kd_id:
            _send(member, f"{names.get(kd_id, kd_id)} marked {names.get(target, target)} as an empire target")
    return {"message": f"{names.get(target, target)} is now a target", "status": "success"}, 200


@bp.route('/api/empiretargets/add', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def add_target_route():
    body = _body()
    payload, status = add_target(flask_praetorian.current_user().kd_id, body.get("target"), body.get("actions"),
                                 body.get("fund_share"))
    return _answer(payload, status)


@bp.route('/api/empiretargets/<target>/update', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def update_target_route(target):
    kd_id = flask_praetorian.current_user().kd_id
    body = _body()
    try:
        actions = parse_actions(body.get("actions"))
        fund_share = parse_fund_share(body.get("fund_share"))
    except (TypeError, ValueError) as error:
        return _answer({"message": str(error)}, 400)
    empire, is_emperor, _, _, _ = _context(kd_id)
    if empire is None:
        return _answer({"message": "You are not in an empire"}, 400)

    def decide(document):
        document = normalize(document)
        _must_manage(is_emperor, kd_id)(document)
        entry = document["targets"].get(str(target))
        if entry is None:
            raise occ.Rejected("That kingdom is not a target")
        entry["actions"] = actions
        entry["fund_share"] = fund_share
        return written(document), None

    try:
        occ.update(_path(empire), decide)
    except occ.Rejected as rejection:
        return _refusal(rejection)
    except occ.Busy:
        return _answer({"message": "Server is busy"}, 400)
    return _answer({"message": "Target updated", "status": "success"})


@bp.route('/api/empiretargets/<target>/remove', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def remove_target_route(target):
    kd_id = flask_praetorian.current_user().kd_id
    empire, is_emperor, _, _, _ = _context(kd_id)
    if empire is None:
        return _answer({"message": "You are not in an empire"}, 400)
    try:
        shares = _end_target(empire, str(target), "removed", kd_id, check=_must_manage(is_emperor, kd_id))
    except occ.Rejected as rejection:
        return _refusal(rejection)
    except occ.Busy:
        return _answer({"message": "Server is busy"}, 400)
    paid = f", paying out its fund to {len(shares)} participant(s)" if shares else ""
    hours = uas.GAME_CONFIG["TARGET_REMARK_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600
    return _answer({"message": f"Target removed{paid}. It can be marked again in {hours:g} hours", "status": "success"})


@bp.route('/api/empiretargets/delegates', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def delegates_route():
    kd_id = flask_praetorian.current_user().kd_id
    body = _body()
    delegates = body.get("delegates")
    if not isinstance(delegates, list) or not all(isinstance(kd, (str, int)) for kd in delegates):
        return _answer({"message": "Send the delegates as a list of kingdoms"}, 400)
    delegates = list(dict.fromkeys(str(kd) for kd in delegates))
    maximum = uas.GAME_CONFIG["TARGET_MAX_DELEGATES"]
    if len(delegates) > maximum:
        return _answer({"message": f"You can name at most {maximum} delegate(s)"}, 400)
    empire, is_emperor, empires_info, _, galaxy_info = _context(kd_id)
    if empire is None:
        return _answer({"message": "You are not in an empire"}, 400)
    if not is_emperor:
        return _answer({"message": "Only the emperor can name delegates"}, 400)
    members = set(_empire_kingdoms(empire, empires_info, galaxy_info))
    outside = [kd for kd in delegates if kd not in members]
    if outside:
        return _answer({"message": "Delegates must be kingdoms in your empire"}, 400)

    def decide(document):
        document = normalize(document)
        document["delegates"] = delegates
        return written(document), None

    try:
        occ.update(_path(empire), decide)
    except occ.Busy:
        return _answer({"message": "Server is busy"}, 400)
    return _answer({"message": "Delegates saved", "status": "success"})
