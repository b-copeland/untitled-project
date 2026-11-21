"""
The galaxy's intel market: selling intel, asking for it, and who earns a cut of which attack.

A kingdom that has revealed something about another kingdom (a category: kingdom, military, shields, ...) can

* **list** it on its galaxy's market for a cut of the spoils. Any galaxymate can buy a listing, and it stays listed,
  so several can buy the same one. It is listed until the seller's reveal ends.
* **share it free** with the whole galaxy. Free intel needs no accepting: every galaxymate gets it at once.

A kingdom that wants intel posts a **bounty** for it, offering a cut. The first galaxymate to fulfil it with their own
intel earns the cut, and the bounty leaves the board. Recent purchases, fulfilled bounties and free shares stay in the
history.

The cut is paid out of every successful attack on the target while the intel lasts. Different categories add up, each
paid to its own sharer, up to ``BASE_MAX_TOTAL_SHARE_CUT`` for one target. Once a kingdom has accepted a category on a
target, it can not take the same category on that target at a lower cut (so a galaxymate can not cut the first
sharer out by offering it cheaper), and a free share never replaces paid intel.

A kingdom can exclude galaxymates from its intel: they do not see its listings or its bounties, can not buy or answer
them, and get nothing from its free shares. Intel received from a galaxymate can not be passed on.

Everything lives in one document per galaxy, ``galaxy_intel_<galaxy>``, which is the single decision point of every
action here (``occ.update``). Its fields (each read with a default, since the function app creates it as ``{"id"}``):

* ``listings``: listing id to ``{id, seller, target, category, cut, time, listed_at}``. One per seller, target and
  category; listing again replaces it. ``time`` is when the seller's reveal, and so the listing, ends.
* ``bounties``: bounty id to ``{id, requester, target, category, cut, time, posted_at}``. One per requester, target and
  category. ``time`` is when it expires.
* ``accepted``: buyer to target to category to ``{sharer, cut, time, source, accepted_at}``: the intel the buyer has
  received, and so owes a cut for. ``source`` is ``market``, ``bounty`` or ``free``.
* ``received``: receiver to target to category to the time until which the receiver has intel from galaxymates (the
  latest of everything it bought, was given for a bounty, or got free). This, not ``accepted``, is what says it may not
  pass the intel on: a free share that outlasts paid intel leaves the paid record (and its cut) in ``accepted``, but
  the intel is still received until the free share ends.
* ``exclusions``: kingdom to the galaxymates it keeps its intel from.
* ``history``: the newest ``HISTORY_LENGTH`` of ``{kind, time, from, to, target, category, cut}``, ``kind`` being
  ``purchase``, ``bounty`` or ``free`` (``to`` is ``None`` for a free share, which went to the whole galaxy).

Nothing here is on a timer: expired entries are ignored when read and dropped whenever the document is next written.
Cuts are fractions in the document and percents in requests, as on the pages.
"""
import copy
import datetime
import json

import flask
import flask_praetorian
from flask_sock import ConnectionClosed

import untitledapp.getters as uag
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import REQUESTS_SESSION, SOCK_HANDLERS, alive_required

bp = flask.Blueprint("intel", __name__)

# The kinds of intel: what the operations reveal (Full Infiltration reveals all of them, and is not a kind of its own).
CATEGORIES = list(dict.fromkeys(stat for operation in uas.REVEAL_OPERATIONS for stat in uas.REVEAL_OPERATION_STATS[operation]))
HISTORY_LENGTH = 50
FIELDS = ("listings", "bounties", "accepted", "received", "exclusions", "history")
_EPSILON = 1e-9


# --- pure rules: plain dicts in, plain values out -----------------------------------------------------------------

_utc = uas.utc  # compare times as datetimes, never as strings


def listing_id(seller, target, category):
    return f"{seller}.{target}.{category}"


def bounty_id(requester, target, category):
    return f"{requester}.{target}.{category}"


def normalize(document):
    """The market's fields from a stored document, each with its default, as a private copy."""
    document = document or {}
    return {
        "listings": copy.deepcopy(document.get("listings") or {}),
        "bounties": copy.deepcopy(document.get("bounties") or {}),
        "accepted": copy.deepcopy(document.get("accepted") or {}),
        "received": copy.deepcopy(document.get("received") or {}),
        "exclusions": copy.deepcopy(document.get("exclusions") or {}),
        "history": copy.deepcopy(document.get("history") or []),
    }


def prune(market, now):
    """Drop what has expired: listings, bounties, accepted and received intel whose time has passed, and old history."""
    market["listings"] = {key: item for key, item in market["listings"].items() if _utc(item["time"]) > now}
    market["bounties"] = {key: item for key, item in market["bounties"].items() if _utc(item["time"]) > now}
    accepted = {}
    for buyer, targets in market["accepted"].items():
        kept_targets = {}
        for target, categories in targets.items():
            kept = {category: record for category, record in categories.items() if _utc(record["time"]) > now}
            if kept:
                kept_targets[target] = kept
        if kept_targets:
            accepted[buyer] = kept_targets
    market["accepted"] = accepted
    received = {}
    for kd_id, targets in market["received"].items():
        kept_targets = {}
        for target, categories in targets.items():
            kept = {category: until for category, until in categories.items() if _utc(until) > now}
            if kept:
                kept_targets[target] = kept
        if kept_targets:
            received[kd_id] = kept_targets
    market["received"] = received
    market["exclusions"] = {kd: list(excluded) for kd, excluded in market["exclusions"].items() if excluded}
    market["history"] = market["history"][:HISTORY_LENGTH]
    return market


def accepted_on(market, buyer, target, now):
    """The intel ``buyer`` has received on ``target`` and still has: category to record."""
    categories = market["accepted"].get(buyer, {}).get(target, {})
    return {category: record for category, record in categories.items() if _utc(record["time"]) > now}


def has_received(market, kd_id, target, category, now):
    """Whether ``kd_id`` has this intel from a galaxymate (and so may not pass it on): bought, a bounty, or free."""
    until = market["received"].get(kd_id, {}).get(target, {}).get(category)
    return (until is not None and _utc(until) > now) or category in accepted_on(market, kd_id, target, now)


def accept_problem(market, buyer, target, category, cut, now, until=None):
    """
    Why ``buyer`` may not take ``category`` intel on ``target`` at ``cut`` (lasting ``until``), or None if it may.

    The same category at a lower cut than one already taken is refused, so the first sharer can not be cut out; so is
    intel that would not last longer than what the buyer already has; and the cuts on one target may not add up to more
    than ``BASE_MAX_TOTAL_SHARE_CUT``. ``until=None`` (posting a bounty) checks only the cuts.
    """
    current = accepted_on(market, buyer, target, now)
    existing = current.get(category)
    if existing is not None:
        if cut + _EPSILON < existing["cut"]:
            return (f"You already have {category} intel on this kingdom at a {existing['cut']:.1%} cut, and can not "
                    "take it at a lower one")
        if until is not None and _utc(until) <= _utc(existing["time"]):
            return f"You already have {category} intel on this kingdom for at least as long"
    total = sum(record["cut"] for other, record in current.items() if other != category) + cut
    maximum = uas.GAME_CONFIG["BASE_MAX_TOTAL_SHARE_CUT"]
    if total > maximum + _EPSILON:
        return f"That would make your cuts on this kingdom {total:.1%}; the most is {maximum:.1%}"
    return None


def spoils_cuts(market, attacker, target, now):
    """Each sharer's cut of ``attacker``'s spoils from ``target``: the cuts of every category they shared, added."""
    cuts = {}
    for record in accepted_on(market, attacker, target, now).values():
        if record["cut"] > 0:
            cuts[record["sharer"]] = cuts.get(record["sharer"], 0) + record["cut"]
    return cuts


def split_spoils(total_spoils, cuts):
    """
    ``(attacker_spoils, {sharer: spoils})`` from the whole of what an attack takes (``{"stars": n, ..., "funding":
    {category: n}}``). Each sharer gets their cut of each amount, rounded down; the attacker gets what is left after
    all the cuts, also rounded down.
    """
    total_cut = sum(cuts.values())

    def part(share):
        spoils = {}
        for key, value in total_spoils.items():
            if isinstance(value, dict):
                spoils[key] = {inner: max(int(amount * share), 0) for inner, amount in value.items()}
            else:
                spoils[key] = max(int(value * share), 0)
        return spoils

    return part(max(1 - total_cut, 0)), {sharer: part(cut) for sharer, cut in cuts.items()}


def _record(sharer, cut, until, source, now):
    return {"sharer": sharer, "cut": cut, "time": _iso(until), "source": source, "accepted_at": now.isoformat()}


def _iso(value):
    return value.isoformat() if isinstance(value, datetime.datetime) else value


def _give(market, buyer, target, category, record):
    market["accepted"].setdefault(buyer, {}).setdefault(target, {})[category] = record
    _mark_received(market, buyer, target, category, record["time"])


def _mark_received(market, kd_id, target, category, until):
    """Note that ``kd_id`` has received this intel until ``until`` (the later of that and what was noted)."""
    categories = market["received"].setdefault(kd_id, {}).setdefault(target, {})
    stored = categories.get(category)
    if stored is None or _utc(until) > _utc(stored):
        categories[category] = _iso(until)


def _history(market, kind, now, sharer, to, target, category, cut):
    market["history"] = ([{"kind": kind, "time": now.isoformat(), "from": sharer, "to": to, "target": target,
                           "category": category, "cut": cut}] + market["history"])[:HISTORY_LENGTH]


def share_free(market, sharer, target, category, until, recipients, now):
    """
    Give free intel to each recipient. Returns ``(receivers, bounties_met)``: who got it (all of them: the reveal
    reaches them even where their record stays) and the bounties it answered, which leave the board.

    A recipient's record is replaced only if it was free and ends sooner, so free intel never takes the place of intel
    someone paid a cut for. Each recipient's open bounty for this intel is met by it, for no cut.
    """
    for recipient in recipients:
        existing = accepted_on(market, recipient, target, now).get(category)
        if existing is None or (existing["cut"] <= 0 and _utc(existing["time"]) < _utc(until)):
            _give(market, recipient, target, category, _record(sharer, 0, until, "free", now))
        else:
            _mark_received(market, recipient, target, category, until)  # the paid record stays; the intel is received
    met = [bounty for bounty in market["bounties"].values()
           if bounty["target"] == target and bounty["category"] == category and bounty["requester"] in recipients]
    for bounty in met:
        del market["bounties"][bounty["id"]]
    _history(market, "free", now, sharer, None, target, category, 0)
    return list(recipients), met


def revealed_until(revealed, target, category, now):
    """When ``category`` on ``target`` stops being revealed in a ``revealed_<id>`` document, or None if it is not."""
    until = ((revealed or {}).get("revealed") or {}).get(target, {}).get(category)
    if until is None or _utc(until) <= now:
        return None
    return until


def view(market, kd_id, revealed, now, members=()):
    """
    What ``kd_id`` sees of its galaxy's market. Listings and bounties from kingdoms that exclude it are left out, and only its own
    accepted intel and exclusions are included, and its own intel (``my_intel``) leaves out galaxymates, whose
    intel can not be shared. Each listing and bounty says why the viewer could not take it
    (``problem``, None if it can), so the page can say so before anything is sent. Each bounty also says whether the
    viewer has that intel at all (``have``): without it, the page offers to spy for it instead.
    """
    market = prune(normalize(market), now)
    listings = []
    for listing in market["listings"].values():
        if kd_id in market["exclusions"].get(listing["seller"], []):
            continue
        if listing["seller"] == kd_id:
            problem = "This is your listing"
        else:
            problem = accept_problem(market, kd_id, listing["target"], listing["category"], listing["cut"], now,
                                     until=listing["time"])
        listings.append({**listing, "problem": problem})
    bounties = []
    for bounty in market["bounties"].values():
        if kd_id in market["exclusions"].get(bounty["requester"], []):
            continue
        bounties.append({**bounty, "problem": fulfil_problem(market, kd_id, bounty, revealed, now),
                         "have": revealed_until(revealed, bounty["target"], bounty["category"], now) is not None})
    accepted = [
        {"target": target, "category": category, **record}
        for target, categories in market["accepted"].get(kd_id, {}).items()
        for category, record in categories.items()
    ]
    cuts = {target: sum(record["cut"] for record in categories.values())
            for target, categories in market["accepted"].get(kd_id, {}).items()}
    my_intel = []
    for target, categories in ((revealed or {}).get("revealed") or {}).items():
        for category, until in categories.items():
            if _utc(until) <= now or target in members:
                continue
            listing = market["listings"].get(listing_id(kd_id, target, category))
            my_intel.append({
                "target": target, "category": category, "time": until,
                "received": has_received(market, kd_id, target, category, now),
                "listing": listing["id"] if listing else None,
                "cut": listing["cut"] if listing else None,
            })
    by_time = lambda item: _utc(item["time"])  # noqa: E731
    return {
        "listings": sorted(listings, key=by_time),
        "bounties": sorted(bounties, key=by_time),
        "accepted": sorted(accepted, key=by_time),
        "cuts": cuts,
        "my_intel": sorted(my_intel, key=lambda item: (item["target"], item["category"])),
        "exclusions": market["exclusions"].get(kd_id, []),
        "history": market["history"],
    }


def fulfil_problem(market, kd_id, bounty, revealed, now):
    """Why ``kd_id`` could not fulfil ``bounty`` with the reveals in ``revealed``, or None if it can."""
    if bounty["requester"] == kd_id:
        return "This is your bounty"
    until = revealed_until(revealed, bounty["target"], bounty["category"], now)
    if until is None:
        return f"You do not have {bounty['category']} intel on this kingdom"
    if has_received(market, kd_id, bounty["target"], bounty["category"], now):
        return "You can not pass on intel that was shared with you"
    problem = accept_problem(market, bounty["requester"], bounty["target"], bounty["category"], bounty["cut"], now,
                             until=until)
    if problem is not None:
        return "They can not take this intel any more: " + problem[0].lower() + problem[1:]
    return None


# --- reading and writing the market --------------------------------------------------------------------------------

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _path(galaxy):
    return f"/galaxy/{galaxy}/intel"


def _galaxy(kd_id):
    """``(galaxy id, its kingdoms)`` of ``kd_id``."""
    galaxies_inverted, galaxies = uag._get_galaxies_inverted()
    galaxy = galaxies_inverted.get(kd_id)
    return galaxy, list(galaxies.get(galaxy, []))


def _market(galaxy):
    return occ.read(_path(galaxy))


def _written(market):
    return {field: market[field] for field in FIELDS}


def _cut_from_percent(value):
    """A cut sent as a percent, as a fraction; raises ValueError for anything that is not a number from 0 to the max."""
    cut = float(value or 0) / 100
    if cut != cut or cut < 0:  # NaN or negative
        raise ValueError("The cut must be a positive number")
    if cut > uas.GAME_CONFIG["BASE_MAX_SHARE_CUT"] + _EPSILON:
        raise ValueError(f"The cut can be at most {uas.GAME_CONFIG['BASE_MAX_SHARE_CUT']:.1%}")
    return cut


def _name(kingdoms, kd_id):
    return kingdoms.get(kd_id, f"kingdom {kd_id}")


def _tell(kd_id, message, update=("intel",)):
    try:
        SOCK_HANDLERS[kd_id].send(json.dumps({
            "message": message, "status": "info", "category": "Intel", "delay": 15000, "update": list(update),
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass


def _news(kd_id, message, from_kd):
    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"time": _now().isoformat(), "from": from_kd, "news": message, "kind": "intel"}),
    )


def _reveal_to(kd_id, target, category, until):
    """Give ``kd_id`` the reveal, and make sure its refresh expires it on time (issue #60)."""
    import untitledapp.conquer as uac  # conquer imports this module

    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"new_revealed": {target: {category: _iso(until)}}}),
    )
    uac._lower_timer(kd_id, "revealed", _iso(until))


def _decide(galaxy, decide):
    """``occ.update`` on the galaxy's market, turning its refusals into ``(payload, status)``."""
    try:
        return occ.update(_path(galaxy), decide), None
    except occ.Rejected as rejection:
        return None, ({"message": rejection.message}, rejection.status)
    except occ.Busy:
        return None, ({"message": "Server is busy"}, 400)


def _check_category(category):
    if category not in CATEGORIES:
        raise ValueError("Choose a kind of intel: " + ", ".join(CATEGORIES))


def spoils_cuts_for(attacker, target):
    """The cuts each sharer earns from ``attacker``'s spoils on ``target``, from the attacker's galaxy's market."""
    galaxy, _ = _galaxy(attacker)
    if galaxy is None:
        return {}
    return spoils_cuts(normalize(_market(galaxy)), attacker, str(target), _now())


def _view(kd_id):
    galaxy, members = _galaxy(kd_id)
    return view(_market(galaxy), kd_id, uag._get_revealed(kd_id), _now(), members)


# --- actions (the routes and the bots both come through these) -----------------------------------------------------

def _share(kd_id, target, category, cut_percent):
    """List intel on the market for a cut, or share it free with the galaxy at a cut of 0. Returns (payload, status)."""
    target = str(target)
    try:
        _check_category(category)
        cut = _cut_from_percent(cut_percent)
    except (TypeError, ValueError) as error:
        return {"message": str(error)}, 400
    now = _now()
    until = revealed_until(uag._get_revealed(kd_id), target, category, now)
    if until is None:
        return {"message": f"You do not have {category} intel on that kingdom to share"}, 400
    galaxy, members = _galaxy(kd_id)
    if target in members:
        return {"message": "You can not share intel on a galaxymate"}, 400

    def decide(document):
        market = prune(normalize(document), now)
        if has_received(market, kd_id, target, category, now):
            raise occ.Rejected("You can not pass on intel that was shared with you")
        if cut > 0:
            key = listing_id(kd_id, target, category)
            market["listings"][key] = {"id": key, "seller": kd_id, "target": target, "category": category, "cut": cut,
                                       "time": until, "listed_at": now.isoformat()}
            return _written(market), ([], [])
        excluded = market["exclusions"].get(kd_id, [])
        recipients = [member for member in members if member != kd_id and member not in excluded]
        shared = share_free(market, kd_id, target, category, until, recipients, now)
        return _written(market), shared

    result, refused = _decide(galaxy, decide)
    if refused:
        return refused
    receivers, met = result
    kingdoms = uag._get_kingdoms()
    if cut > 0:
        for member in members:
            if member != kd_id:
                _tell(member, f"{_name(kingdoms, kd_id)} listed {category} intel on {_name(kingdoms, target)} for a "
                              f"{cut:.1%} cut")
        return {"message": f"Listed your {category} intel for a {cut:.1%} cut", "status": "success"}, 200
    for receiver in receivers:
        _reveal_to(receiver, target, category, until)
        uam._add_notifs(receiver, ["shared"])
        _tell(receiver, f"{_name(kingdoms, kd_id)} shared {category} intel on {_name(kingdoms, target)} with you",
              update=("intel", "revealed"))
    return {"message": f"Shared your {category} intel with {len(receivers)} galaxymate(s)"
                       + (f", meeting {len(met)} bounty(s)" if met else ""), "status": "success"}, 200


def _delist(kd_id, listing):
    galaxy, _ = _galaxy(kd_id)
    now = _now()

    def decide(document):
        market = prune(normalize(document), now)
        if market["listings"].get(listing, {}).get("seller") != kd_id:
            raise occ.Rejected("That listing is not yours or has ended")
        del market["listings"][listing]
        return _written(market), None

    _, refused = _decide(galaxy, decide)
    return refused or ({"message": "Listing removed", "status": "success"}, 200)


def _buy(kd_id, listing):
    """Take a listing from the market: the reveal now, the cut from each successful attack while it lasts."""
    galaxy, _ = _galaxy(kd_id)
    now = _now()

    def decide(document):
        market = prune(normalize(document), now)
        offer = market["listings"].get(listing)
        if offer is None or kd_id in market["exclusions"].get(offer["seller"], []):
            raise occ.Rejected("That intel is no longer on offer")
        if offer["seller"] == kd_id:
            raise occ.Rejected("You can not buy your own intel")
        problem = accept_problem(market, kd_id, offer["target"], offer["category"], offer["cut"], now,
                                 until=offer["time"])
        if problem:
            raise occ.Rejected(problem)
        _give(market, kd_id, offer["target"], offer["category"],
              _record(offer["seller"], offer["cut"], offer["time"], "market", now))
        _history(market, "purchase", now, offer["seller"], kd_id, offer["target"], offer["category"], offer["cut"])
        return _written(market), offer

    offer, refused = _decide(galaxy, decide)
    if refused:
        return refused
    _reveal_to(kd_id, offer["target"], offer["category"], offer["time"])
    kingdoms = uag._get_kingdoms()
    message = (f"{_name(kingdoms, kd_id)} took your {offer['category']} intel on {_name(kingdoms, offer['target'])} "
               f"for a {offer['cut']:.1%} cut")
    _news(offer["seller"], message, kd_id)
    uam._add_notifs(offer["seller"], ["shared", "news_kingdom"])
    _tell(offer["seller"], message)
    return {"message": f"You now have {offer['category']} intel on {_name(kingdoms, offer['target'])}",
            "status": "success"}, 200


def bounty_max_hours():
    """The longest a bounty stays up, in hours: what players see (epochs are not shown to them)."""
    return uas.GAME_CONFIG["BASE_INTEL_BOUNTY_MAX_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600


def _post_bounty(kd_id, target, category, cut_percent, hours):
    target = str(target)
    try:
        _check_category(category)
        cut = _cut_from_percent(cut_percent)
        # Left blank, a bounty stays up as long as one may.
        longest = bounty_max_hours()
        hours = longest if hours is None or str(hours).strip() == "" else float(hours)
        if not 0 < hours <= longest:
            raise ValueError(f"A bounty lasts from more than 0 to {longest:g} hours")
    except (TypeError, ValueError) as error:
        return {"message": str(error)}, 400
    kingdoms = uag._get_kingdoms()
    galaxy, members = _galaxy(kd_id)
    if target not in kingdoms:
        return {"message": "There is no such kingdom"}, 400
    if target in members:
        return {"message": "You can not ask for intel on a galaxymate"}, 400
    now = _now()
    expires = now + datetime.timedelta(hours=hours)

    def decide(document):
        market = prune(normalize(document), now)
        problem = accept_problem(market, kd_id, target, category, cut, now)
        if problem:
            raise occ.Rejected(problem)
        key = bounty_id(kd_id, target, category)
        market["bounties"][key] = {"id": key, "requester": kd_id, "target": target, "category": category, "cut": cut,
                                   "time": expires.isoformat(), "posted_at": now.isoformat()}
        return _written(market), None

    _, refused = _decide(galaxy, decide)
    if refused:
        return refused
    for member in members:
        if member != kd_id:
            _tell(member, f"{_name(kingdoms, kd_id)} wants {category} intel on {_name(kingdoms, target)} for a "
                          f"{cut:.1%} cut")
    return {"message": f"Posted a bounty for {category} intel on {_name(kingdoms, target)}", "status": "success"}, 200


def _cancel_bounty(kd_id, bounty):
    galaxy, _ = _galaxy(kd_id)
    now = _now()

    def decide(document):
        market = prune(normalize(document), now)
        if market["bounties"].get(bounty, {}).get("requester") != kd_id:
            raise occ.Rejected("That bounty is not yours or has ended")
        del market["bounties"][bounty]
        return _written(market), None

    _, refused = _decide(galaxy, decide)
    return refused or ({"message": "Bounty withdrawn", "status": "success"}, 200)


def _fulfil(kd_id, bounty):
    """Answer a galaxymate's bounty with your own intel: they get the reveal, you the cut, and it leaves the board."""
    galaxy, _ = _galaxy(kd_id)
    now = _now()
    revealed = uag._get_revealed(kd_id)

    def decide(document):
        market = prune(normalize(document), now)
        wanted = market["bounties"].get(bounty)
        if wanted is None or kd_id in market["exclusions"].get(wanted["requester"], []):
            raise occ.Rejected("That bounty is no longer open")
        problem = fulfil_problem(market, kd_id, wanted, revealed, now)
        if problem:
            raise occ.Rejected(problem)
        until = revealed_until(revealed, wanted["target"], wanted["category"], now)
        _give(market, wanted["requester"], wanted["target"], wanted["category"],
              _record(kd_id, wanted["cut"], until, "bounty", now))
        del market["bounties"][bounty]
        _history(market, "bounty", now, kd_id, wanted["requester"], wanted["target"], wanted["category"],
                 wanted["cut"])
        return _written(market), (wanted, until)

    result, refused = _decide(galaxy, decide)
    if refused:
        return refused
    wanted, until = result
    _reveal_to(wanted["requester"], wanted["target"], wanted["category"], until)
    kingdoms = uag._get_kingdoms()
    message = (f"{_name(kingdoms, kd_id)} answered your bounty for {wanted['category']} intel on "
               f"{_name(kingdoms, wanted['target'])}")
    _news(wanted["requester"], message, kd_id)
    uam._add_notifs(wanted["requester"], ["shared", "news_kingdom"])
    _tell(wanted["requester"], message, update=("intel", "revealed"))
    return {"message": "Bounty fulfilled", "status": "success"}, 200


def _set_exclusions(kd_id, excluded):
    if not isinstance(excluded, list):
        return {"message": "Send the kingdoms to exclude as a list"}, 400
    excluded = sorted({str(kd) for kd in excluded})
    galaxy, members = _galaxy(kd_id)
    if any(kd not in members or kd == kd_id for kd in excluded):
        return {"message": "You can only exclude your galaxymates"}, 400
    now = _now()

    def decide(document):
        market = prune(normalize(document), now)
        market["exclusions"][kd_id] = excluded
        return _written(prune(market, now)), None

    _, refused = _decide(galaxy, decide)
    return refused or ({"message": "Exclusions saved", "status": "success"}, 200)


# --- routes --------------------------------------------------------------------------------------------------------

def _body():
    body = flask.request.get_json(force=True, silent=True)
    return body if isinstance(body, dict) else {}


def _answer(result):
    payload, status = result
    return flask.jsonify(payload), status


def _me():
    return str(flask_praetorian.current_user().kd_id)


@bp.route('/api/intel', methods=['GET'])
@flask_praetorian.auth_required
def intel():
    return flask.jsonify(_view(_me())), 200


@bp.route('/api/intel/share', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def share():
    body = _body()
    return _answer(_share(_me(), body.get("target", ""), body.get("category"), body.get("cut", 0)))


@bp.route('/api/intel/delist', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def delist():
    return _answer(_delist(_me(), str(_body().get("listing", ""))))


@bp.route('/api/intel/buy', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def buy():
    return _answer(_buy(_me(), str(_body().get("listing", ""))))


@bp.route('/api/intel/bounty', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def post_bounty():
    body = _body()
    return _answer(_post_bounty(_me(), body.get("target", ""), body.get("category"), body.get("cut", 0),
                                body.get("hours")))


@bp.route('/api/intel/cancelbounty', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def cancel_bounty():
    return _answer(_cancel_bounty(_me(), str(_body().get("bounty", ""))))


@bp.route('/api/intel/fulfil', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def fulfil():
    return _answer(_fulfil(_me(), str(_body().get("bounty", ""))))


@bp.route('/api/intel/exclusions', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def exclusions():
    return _answer(_set_exclusions(_me(), _body().get("excluded")))
