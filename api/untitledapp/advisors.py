"""
The advisors: short, plain-English advice on the Status page about what in a kingdom may need fixing, each with links
to where it is fixed (docs/advisors.md, issue #185).

Each advice is a **check**, a plain function of a ``Context`` (the caller's own kingdom and the few shared facts the
route reads once) that returns an ``Advice`` or ``None``. No Flask and no storage in the checks, so they are tested with
plain inputs and the bot simulator can run them on every bot. Thresholds come from the game's formulas in
``shared.py`` and the sums the bots use (``botstrategy.py``), never from numbers copied here.

Kinds, in the order the card shows them:

* ``danger``: something is hurting the kingdom now. Can not be hidden.
* ``waste``: money, land or people doing nothing.
* ``team``: something the galaxy, cluster, empire or universe is waiting on.

A player can hide any advice that is not ``danger``, for good (it is stored in their preferences, so it stays hidden
in later rounds), and turn the advisors off in Settings.
"""
import dataclasses
import datetime
import math

import flask
import flask_praetorian

import untitledapp.botstrategy as strategy
import untitledapp.getters as uag
import untitledapp.preferences as uapr
import untitledapp.shared as uas
from untitledapp import alive_required

bp = flask.Blueprint("advisors", __name__)

KINDS = ("danger", "waste", "team")
HIDEABLE_KINDS = ("waste", "team")

# Fuel that runs out within this many hours is worth a warning: a player who logs in twice a day (tenet 1) would
# otherwise find it gone before they are back.
FUEL_WARNING_HOURS = 12


@dataclasses.dataclass
class Advice:
    id: str
    kind: str
    text: str
    links: list  # [(label, path)], where the fix is made

    def view(self, hidden=False):
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "links": [{"label": label, "to": to} for label, to in self.links],
            "hideable": self.kind in HIDEABLE_KINDS,
            "hidden": hidden,
        }


@dataclasses.dataclass
class Context:
    """What the checks may look at: the caller's own kingdom, and facts about the round. Nothing about another
    kingdom that the caller could not see."""
    kd: dict
    now: datetime.datetime
    epochs: float               # epochs since the round started
    max_hangar: float           # hangar space the kingdom has
    used_hangar: float          # hangar space its units take, those in training included
    home_defense: float         # the defense an attacker would face now, by the rules an attack uses
    at_war: bool = False        # the kingdom's empire is at war


def _hours(epochs):
    return epochs * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600


def _number(value):
    return f"{math.floor(value):,}"


def _percent(share):
    return f"{round(share * 100)}%"


# ------------------------------------------------------------------------------------------------------------ danger

def out_of_fuel(ctx):
    if ctx.kd.get("fuel", 0) > 0:
        return None
    config = uas.GAME_CONFIG
    return Advice(
        "out_of_fuel", "danger",
        f"Your kingdom is out of fuel. Until it has fuel again your army is {_percent(config['BASE_FUELLESS_STRENGTH_REDUCTION'])} "
        f"weaker, your shields are off, your homes hold {_percent(config['BASE_FUELLESS_POP_CAP_REDUCTION'])} fewer people "
        "and your population barely grows. Build fuel plants, or use less fuel.",
        [("Build fuel plants", "/structures"), ("Shields", "/shields")],
    )


def fuel_running_out(ctx):
    fuel = ctx.kd.get("fuel", 0)
    net = ((ctx.kd.get("income") or {}).get("fuel") or {}).get("net") or 0
    if fuel <= 0 or net >= 0:
        return None
    hours_left = _hours(fuel / -net)
    if hours_left > FUEL_WARNING_HOURS:
        return None
    when = "within the hour" if hours_left < 1 else f"in about {math.floor(hours_left)} hours"
    return Advice(
        "fuel_running_out", "danger",
        f"Your fuel runs out {when}: you use more than your fuel plants make. Without fuel your army is weaker and your "
        "shields switch off. Build fuel plants, or lower your shields.",
        [("Build fuel plants", "/structures"), ("Shields", "/shields")],
    )


def hangars_full(ctx):
    if ctx.used_hangar <= ctx.max_hangar:
        return None
    return Advice(
        "hangars_full", "danger",
        f"Your units, with those in training, need {_number(ctx.used_hangar)} hangar space and your hangars hold "
        f"{_number(ctx.max_hangar)}. Units without a hangar take room in your homes, so your population shrinks. "
        "Build hangars.",
        [("Build hangars", "/structures"), ("Military", "/military")],
    )


def defense_under_break_even(ctx):
    """Below this line, hitting the kingdom pays an attacker more than sending the same army at primitives (bots.md,
    "what the simulations say", 2: bots that dropped to it were hunted at once)."""
    stars = ctx.kd.get("stars", 0)
    if stars <= 0:
        return None
    line = stars * strategy.break_even_per_star(ctx.epochs, war=ctx.at_war)
    if ctx.home_defense >= line:
        return None
    war = " Your empire is at war, which makes you worth more to its enemies." if ctx.at_war else ""
    return Advice(
        "defense_under_break_even", "danger",
        f"Your defense at home is {_number(ctx.home_defense)} right now, with the bonuses and shields you have, low "
        "enough that attacking you pays better than attacking "
        f"primitives.{war} At least {_number(line)} would make you the worse target. Train defense, or keep more "
        "units at home.",
        [("Train units", "/military"), ("Spending", "/automation?tab=spending")],
    )


CHECKS = [
    out_of_fuel,
    fuel_running_out,
    hangars_full,
    defense_under_break_even,
]

# Every advice id there is, and whether it can be hidden, so the hide route can refuse anything else.
IDS = {
    "out_of_fuel": "danger",
    "fuel_running_out": "danger",
    "hangars_full": "danger",
    "defense_under_break_even": "danger",
}


def advise(ctx, checks=None):
    """Every advice that applies, most serious kind first, then in the order of ``checks`` (``CHECKS`` by default)."""
    found = [advice for advice in (check(ctx) for check in (CHECKS if checks is None else checks)) if advice is not None]
    return sorted(found, key=lambda advice: KINDS.index(advice.kind))


def context_for(kd, state, mobis_queue, empires_inverted, empires, now=None):
    """The context for ``kd``, from documents the route has read."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    epochs = strategy.epochs_since(now, uas.utc(state["state"]["game_start"]))
    units = uag._calc_units(now, kd["units"], kd.get("generals_out", []), mobis_queue)
    max_hangar, used_hangar = uag._calc_hangar_capacity(kd, units)
    home_defense = uag._calc_max_defense(
        {key: value for key, value in kd["units"].items() if key in uas.UNITS},
        military_bonus=uas.project_bonuses(kd)["military_bonus"],
        other_bonuses=0,
        shields=kd.get("shields", {}).get("military", 0),
        fuelless=kd.get("fuel", 0) <= 0,
        gaian=kd.get("race") == "Gaian",
    )
    empire = empires_inverted.get(str(kd.get("kdId")))
    at_war = bool(empire and empires.get(empire, {}).get("war"))
    return Context(kd=kd, now=now, epochs=epochs, max_hangar=max_hangar, used_hangar=used_hangar,
                   home_defense=home_defense, at_war=at_war)


@bp.route("/api/advisors")
@flask_praetorian.auth_required
@alive_required
def get_advisors():
    """``{"enabled", "advice"}``: the caller's advice, most serious first, the hidden ones flagged ``hidden``. Nothing
    while the advisors are switched off, before the round starts, or without a kingdom."""
    user = flask_praetorian.current_user()
    preferences = uapr.read(user.id)
    if preferences["advisors"] == "off":
        return flask.jsonify({"enabled": False, "advice": []}), 200
    kd_id = user.kd_id
    state = uag._get_state()
    now = datetime.datetime.now(datetime.timezone.utc)
    if kd_id is None or now < uas.utc(state["state"]["game_start"]):
        return flask.jsonify({"enabled": True, "advice": []}), 200
    kd = uag._get_kd_info(kd_id)
    if not kd.get("race"):  # never set up
        return flask.jsonify({"enabled": True, "advice": []}), 200
    empires_inverted, empire_infos, _, _ = uag._get_empires_inverted()
    ctx = context_for(kd, state, uag._get_mobis_queue(kd_id), empires_inverted, empire_infos["empires"], now)
    hidden = set(preferences["hidden_advice"])
    advice = [item.view(hidden=item.id in hidden and item.kind in HIDEABLE_KINDS) for item in advise(ctx)]
    return flask.jsonify({"enabled": True, "advice": advice}), 200


@bp.route("/api/advisors/hide", methods=["POST"])
@flask_praetorian.auth_required
def hide_advice():
    """Body: ``{"id": <advice id>, "hidden": true|false}``. Hides an advice for good, or shows it again."""
    req = flask.request.get_json(force=True, silent=True)
    if not isinstance(req, dict) or not isinstance(req.get("hidden"), bool):
        return flask.jsonify({"message": "Say whether to hide the advice"}), 400
    advice_id = req.get("id")
    if advice_id not in IDS:
        return flask.jsonify({"message": "There is no such advice"}), 400
    if IDS[advice_id] not in HIDEABLE_KINDS:
        return flask.jsonify({"message": "Warnings about danger to your kingdom can not be hidden"}), 400
    if not uapr.set_advice_hidden(flask_praetorian.current_user().id, advice_id, req["hidden"]):
        return flask.jsonify({"message": "Your advisors could not be updated. Try again."}), 503
    message = "Advice hidden" if req["hidden"] else "Advice shown again"
    return flask.jsonify({"message": message, "status": "success"}), 200
