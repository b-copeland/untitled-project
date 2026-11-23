"""
Cluster politics: the galaxies of a cluster vote to build up benefits that every kingdom in the cluster gets.

A **cluster** is the group of galaxies whose ids share a first part: galaxy ``2:7`` is galaxy 7 of cluster 2.
``/api/admin/newround`` deals galaxies into clusters of ``CLUSTER_SIZE``, and a galaxy never changes cluster, so a
kingdom's cluster follows from its galaxy and needs no document of its own.

A round plays ``CLUSTER_BENEFITS_PER_ROUND`` of the benefits in ``shared.CLUSTER_BENEFITS``, drawn when the admin makes
the round and stored in the state (``cluster_benefits``), for the whole round (``draw``, ``round_benefits``). Each
galaxy's leader casts the galaxy's one vote for one of them, or none. Every benefit has
a **level** from 0 to 1 (a fraction of its ``max``). Per epoch:

* each vote raises the level by ``CLUSTER_VOTE_RATE * CLUSTER_REF_SIZE / galaxies in the cluster``, so a unanimous
  cluster gains the same whatever its size, times how effective votes are at that level (the benefit's
  ``thresholds``: past each one, votes add less), times the empire alignment multiplier;
* every level falls by ``CLUSTER_DECAY_RATE``, voted for or not, so a benefit nobody keeps up fades away.

The level is a pure function of the stored document and the clock (``advance``), so nothing is written on a tick.
Votes are constant between writes because every write advances the levels to its own moment first. The **alignment**
(the share of the cluster's galaxies in its largest empire) changes when empires change, so the refresh stores it,
advancing first, whenever it differs from the stored one (``sync``). Its multiplier is 1.0 for now: a hook for a
coordination bonus to come.

One document per cluster, ``cluster_<cluster>``, the decision point of every write. Its fields (each read with a
default, since the function app creates it as ``{"id"}``):

* ``votes``: galaxy id to benefit key.
* ``vote_changed``: galaxy id to when its vote last changed (cast, switched or withdrawn). The vote can not change
  again for ``CLUSTER_VOTE_COOLDOWN_EPOCHS``, so a leader can not flip it to chase whatever is ahead.
* ``levels``: benefit key to level (0 to 1), as of ``last_update``.
* ``alignment``: the alignment as of ``last_update``.
* ``last_update``: when ``levels`` were last advanced.
"""
import datetime
import random

import flask
import flask_praetorian

import untitledapp.getters as uag
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import alive_required

bp = flask.Blueprint("clusters", __name__)

_EPSILON = 1e-12


# --- pure rules: plain values in, plain values out ----------------------------------------------------------------

_utc = uas.utc  # compare times as datetimes, never as strings


def draw(rng=random, count=None):
    """The benefits a new round plays: ``count`` of them at random, in the order ``CLUSTER_BENEFITS`` lists them."""
    count = uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"] if count is None else count
    keys = list(uas.CLUSTER_BENEFITS)
    chosen = rng.sample(keys, min(max(count, 0), len(keys)))
    return [key for key in keys if key in chosen]


def round_benefits(state_inner):
    """
    The benefits this round plays, from the state's inner object. A round made before the draw plays the first
    ``CLUSTER_BENEFITS_PER_ROUND``, which start with the three it had.
    """
    drawn = [key for key in ((state_inner or {}).get("cluster_benefits") or []) if key in uas.CLUSTER_BENEFITS]
    if drawn:
        return drawn
    return list(uas.CLUSTER_BENEFITS)[:uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]]


def cluster_of(galaxy_id):
    """The cluster of a galaxy id (``"2"`` for ``"2:7"``), or None for no galaxy."""
    if not galaxy_id:
        return None
    return str(galaxy_id).split(":", 1)[0]


def members(galaxies, cluster):
    """The galaxy ids of ``cluster``, in order, from the ``galaxies`` document's ``{galaxy: [kingdoms]}``."""
    def order(galaxy):
        rest = galaxy.split(":", 1)[-1]
        return (0, int(rest)) if rest.isdigit() else (1, rest)
    return sorted((galaxy for galaxy in galaxies if cluster_of(galaxy) == cluster), key=order)


def clusters(galaxies):
    """Every cluster id that has a galaxy."""
    return sorted({cluster_of(galaxy) for galaxy in galaxies}, key=lambda c: (0, int(c)) if c.isdigit() else (1, c))


def alignment(member_galaxies, empires):
    """The share of ``member_galaxies`` in the cluster's largest empire (0 when none is in an empire)."""
    if not member_galaxies:
        return 0.0
    in_cluster = set(member_galaxies)
    largest = max(
        (len(in_cluster.intersection(empire.get("galaxies", []))) for empire in (empires or {}).values()),
        default=0,
    )
    return largest / len(member_galaxies)


def alignment_multiplier(value):
    """How much stronger votes are in a cluster with this alignment. A hook for a coordination bonus: 1.0 for now."""
    return 1.0


def vote_gain(n_galaxies, alignment_value):
    """What one vote adds to a level per epoch, before the thresholds."""
    if n_galaxies <= 0:
        return 0.0
    return (uas.GAME_CONFIG["CLUSTER_VOTE_RATE"] * uas.GAME_CONFIG["CLUSTER_REF_SIZE"] / n_galaxies
            * alignment_multiplier(alignment_value))


def _segments(thresholds):
    """``(bounds, efficiencies)``: level bounds ``0 = b0 < b1 < ... < 1`` and how effective votes are from each up."""
    bounds, efficiencies = [0.0], [1.0]
    for level, efficiency in sorted(thresholds or []):
        if 0 < level < 1:
            bounds.append(float(level))
            efficiencies.append(float(efficiency))
    return bounds, efficiencies


def _segment_up(bounds, level):
    """The segment a level moving up is in: the last bound at or below it."""
    return max(i for i, bound in enumerate(bounds) if bound <= level + _EPSILON)


def _segment_down(bounds, level):
    """The segment a level moving down is in: the last bound strictly below it."""
    return max(i for i, bound in enumerate(bounds) if bound < level - _EPSILON)


def _upper(bounds, segment):
    return bounds[segment + 1] if segment + 1 < len(bounds) else 1.0


def advance_level(level, gain, decay, thresholds, epochs):
    """
    The level after ``epochs`` epochs, gaining ``gain`` per epoch (times the efficiency where it is) and losing
    ``decay``. Exact: within each threshold segment the rate is constant, so it moves segment by segment, and splitting
    the time anywhere gives the same answer. Where votes gain more than the decay below a threshold and less above it,
    the level holds at the threshold. It stays within 0 and 1.
    """
    bounds, efficiencies = _segments(thresholds)
    level = min(max(float(level), 0.0), 1.0)
    remaining = max(float(epochs), 0.0)
    while remaining > _EPSILON:
        if level < 1.0 - _EPSILON:
            segment = _segment_up(bounds, level)
            rate = gain * efficiencies[segment] - decay
            if rate > 0:
                upper = _upper(bounds, segment)
                needed = (upper - level) / rate
                if remaining <= needed:
                    level += rate * remaining
                    break
                level, remaining = upper, remaining - needed
                continue
        if level <= _EPSILON:
            level = 0.0
            break
        segment = _segment_down(bounds, level)
        rate = gain * efficiencies[segment] - decay
        if rate >= 0:  # holding: at the top, or at a threshold votes can keep but not pass
            break
        lower = bounds[segment]
        needed = (level - lower) / -rate
        if remaining <= needed:
            level += rate * remaining
            break
        level, remaining = lower, remaining - needed
    return min(max(level, 0.0), 1.0)


def rate_of(level, gain, decay, thresholds):
    """How fast the level is moving now, per epoch (0 while it holds)."""
    bounds, efficiencies = _segments(thresholds)
    if level < 1.0 - _EPSILON:
        rate = gain * efficiencies[_segment_up(bounds, level)] - decay
        if rate > 0:
            return rate
    if level <= _EPSILON:
        return 0.0
    rate = gain * efficiencies[_segment_down(bounds, level)] - decay
    return min(rate, 0.0)


def normalize(document):
    """The cluster's fields from a stored document, each with its default, as a private copy."""
    document = document or {}
    levels = document.get("levels") or {}
    return {
        "votes": {galaxy: key for galaxy, key in (document.get("votes") or {}).items() if key in uas.CLUSTER_BENEFITS},
        "vote_changed": dict(document.get("vote_changed") or {}),
        "levels": {key: float(levels.get(key, 0.0)) for key in uas.CLUSTER_BENEFITS},
        "alignment": float(document.get("alignment") or 0.0),
        "last_update": document.get("last_update"),
    }


def vote_unlocks_at(cluster, galaxy, now):
    """When ``galaxy``'s vote can change again, or None if it can now (it never changed, or the cooldown is over)."""
    changed = cluster["vote_changed"].get(galaxy)
    if not changed:
        return None
    unlocks = _utc(changed) + datetime.timedelta(
        seconds=uas.GAME_CONFIG["CLUSTER_VOTE_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])
    return unlocks if unlocks > now else None


def _wait_text(delta):
    """A wait in real time, rounded up to the minute: "2 hours 5 minutes", "40 minutes"."""
    minutes = max(1, -(-int(delta.total_seconds()) // 60))
    hours, minutes = divmod(minutes, 60)
    parts = ([f"{hours} hour{'s' if hours != 1 else ''}"] if hours else []) + ([f"{minutes} minute{'s' if minutes != 1 else ''}"] if minutes else [])
    return " ".join(parts)


def tally(votes, member_galaxies):
    """Votes per benefit, counting only the cluster's own galaxies."""
    counts = {key: 0 for key in uas.CLUSTER_BENEFITS}
    for galaxy in member_galaxies:
        key = votes.get(galaxy)
        if key in counts:
            counts[key] += 1
    return counts


def advance(document, member_galaxies, now):
    """The cluster as of ``now``: its stored fields with ``levels`` advanced and ``last_update`` set to ``now``."""
    cluster = normalize(document)
    if cluster["last_update"] is not None:
        epochs = (now - _utc(cluster["last_update"])).total_seconds() / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        if epochs > 0:
            gain = vote_gain(len(member_galaxies), cluster["alignment"])
            decay = uas.GAME_CONFIG["CLUSTER_DECAY_RATE"]
            counts = tally(cluster["votes"], member_galaxies)
            for key, benefit in uas.CLUSTER_BENEFITS.items():
                cluster["levels"][key] = advance_level(
                    cluster["levels"][key], gain * counts[key], decay, benefit["thresholds"], epochs)
    cluster["last_update"] = now.isoformat()
    return cluster


def modifiers(cluster, benefits=None):
    """
    What the cluster's benefits are worth to its kingdoms now: effect to signed value, as policies give them
    (``shared.EFFECTS``): a 5% discount on units is ``{"unit_cost": -0.05}``. From ``advance``. Only the round's
    ``benefits`` count (every benefit if None).
    """
    values = {}
    for key, benefit in uas.CLUSTER_BENEFITS.items():
        if benefits is not None and key not in benefits:
            continue
        effect = benefit["effect"]
        sign = -1.0 if uas.EFFECTS[effect]["better"] == "lower" else 1.0
        values[effect] = values.get(effect, 0.0) + sign * cluster["levels"].get(key, 0.0) * benefit["max"]
    return values


def view(cluster, cluster_id, member_galaxies, galaxies, galaxy_empires, my_galaxy, benefits=None):
    """What ``/api/cluster`` shows a kingdom of ``my_galaxy``: everything about its own cluster, which is all public
    to the cluster. ``cluster`` is from ``advance``. Whether the caller may vote is not here: the page knows its
    galaxy's leader from ``/api/galaxypolitics``, and the vote route checks it. Only the round's ``benefits`` are shown (every benefit if None)."""
    gain = vote_gain(len(member_galaxies), cluster["alignment"])
    decay = uas.GAME_CONFIG["CLUSTER_DECAY_RATE"]
    counts = tally(cluster["votes"], member_galaxies)
    playing = list(uas.CLUSTER_BENEFITS) if benefits is None else [key for key in uas.CLUSTER_BENEFITS if key in benefits]
    benefits = {}
    for key in playing:
        benefit = uas.CLUSTER_BENEFITS[key]
        level = cluster["levels"][key]
        benefits[key] = {
            "name": benefit["name"],
            "desc": benefit["desc"],
            "max": benefit["max"],
            "level": level,
            "value": level * benefit["max"],
            "rate_per_epoch": rate_of(level, gain * counts[key], decay, benefit["thresholds"]) * benefit["max"],
            "votes": counts[key],
            "effect_text": uas.effect_text(benefit["effect"], modifiers(
                {"levels": {key: 1.0}}, [key]).get(benefit["effect"], benefit["max"])),
        }
    return {
        "cluster": cluster_id,
        "galaxy": my_galaxy,
        "galaxies": [
            {
                "id": galaxy,
                "kingdoms": len(galaxies.get(galaxy, [])),
                "empire": galaxy_empires.get(galaxy),
                "vote": cluster["votes"].get(galaxy),
            }
            for galaxy in member_galaxies
        ],
        "vote_cooldown_hours": uas.GAME_CONFIG["CLUSTER_VOTE_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600,
        "vote_unlocks_at": (lambda unlocks: unlocks.isoformat() if unlocks else None)(
            vote_unlocks_at(cluster, my_galaxy, _utc(cluster["last_update"]))),
        "benefits": benefits,
        "order": playing,  # the benefits reach the browser with their keys sorted
        "alignment": cluster["alignment"],
        "alignment_multiplier": alignment_multiplier(cluster["alignment"]),
        "vote_gain_per_epoch": gain,
        "decay_per_epoch": decay,
    }


# --- reading and writing ------------------------------------------------------------------------------------------

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _path(cluster_id):
    return f"/cluster/{cluster_id}"


def _written(cluster):
    return {field: cluster[field] for field in ("votes", "vote_changed", "levels", "alignment", "last_update")}


def _galaxy_empires():
    empires = uag._get_empire_info().get("empires", {})
    return {galaxy: empire_id for empire_id, empire in empires.items() for galaxy in empire.get("galaxies", [])}


def _view(kd_id):
    galaxies_inverted, galaxies = uag._get_galaxies_inverted()
    my_galaxy = galaxies_inverted.get(kd_id)
    if my_galaxy is None:
        return {"message": "You are not in a galaxy"}, 400
    cluster_id = cluster_of(my_galaxy)
    member_galaxies = members(galaxies, cluster_id)
    cluster = advance(uag._get_cluster_document(cluster_id), member_galaxies, _now())
    benefits = round_benefits(uag._get_state().get("state"))
    return view(cluster, cluster_id, member_galaxies, galaxies, _galaxy_empires(), my_galaxy, benefits), 200


def vote(kd_id, benefit):
    """
    Cast (or, with ``benefit`` None, withdraw) ``kd_id``'s galaxy's vote. Only the galaxy leader may.
    Returns ``(payload, status)``.
    """
    if benefit in ("", None):
        benefit = None
    elif benefit not in uas.CLUSTER_BENEFITS:
        return {"message": "Choose one of this round's benefits"}, 400
    elif benefit not in round_benefits(uag._get_state().get("state")):
        return {"message": f"{uas.CLUSTER_BENEFITS[benefit]['name']} is not one of this round's benefits"}, 400
    galaxies_inverted, galaxies = uag._get_galaxies_inverted()
    my_galaxy = galaxies_inverted.get(kd_id)
    if my_galaxy is None:
        return {"message": "You are not in a galaxy"}, 400
    # The leader is in another document, so it is checked here, not in decide: a leader replaced at this very moment
    # could still land one last vote, which the next leader can change.
    galaxy_politics, _ = uag._get_galaxy_politics(kd_id, my_galaxy)
    if galaxy_politics.get("leader") != kd_id:
        return {"message": "Only your galaxy leader can vote for your galaxy"}, 400
    cluster_id = cluster_of(my_galaxy)
    member_galaxies = members(galaxies, cluster_id)
    now = _now()

    def decide(document):
        cluster = advance(document, member_galaxies, now)
        if cluster["votes"].get(my_galaxy) == benefit:
            return _written(cluster), None  # nothing changes, so nothing starts the cooldown
        unlocks = vote_unlocks_at(cluster, my_galaxy, now)
        if unlocks:
            raise occ.Rejected(f"Your galaxy changed its vote recently. It can change again in {_wait_text(unlocks - now)}.")
        if benefit is None:
            cluster["votes"].pop(my_galaxy, None)
        else:
            cluster["votes"][my_galaxy] = benefit
        cluster["vote_changed"][my_galaxy] = now.isoformat()
        return _written(cluster), None

    try:
        occ.update(_path(cluster_id), decide)
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    if benefit is None:
        return {"message": "Your galaxy's vote is withdrawn", "status": "success"}, 200
    return {"message": f"Your galaxy now votes for {uas.CLUSTER_BENEFITS[benefit]['name']}", "status": "success"}, 200


def sync(galaxies, empires, time_update, documents=None):
    """
    The refresh's step: store each cluster's alignment where it has changed, advancing its levels to ``time_update``
    first so the old alignment counts until now. Writes nothing for a cluster whose alignment is as stored.
    ``documents`` are cluster documents already read this tick (with their ``_etag``), to decide against first.
    """
    documents = documents or {}
    for cluster_id in clusters(galaxies):
        member_galaxies = members(galaxies, cluster_id)
        current = alignment(member_galaxies, empires)

        def decide(document, member_galaxies=member_galaxies, current=current):
            stored = normalize(document)
            if abs(stored["alignment"] - current) < 1e-9:
                return None, None
            cluster = advance(document, member_galaxies, time_update)
            cluster["alignment"] = current
            return _written(cluster), None

        occ.update(_path(cluster_id), decide, document=documents.get(cluster_id))


# --- routes -------------------------------------------------------------------------------------------------------

def _me():
    return str(flask_praetorian.current_user().kd_id)


@bp.route('/api/cluster', methods=['GET'])
@flask_praetorian.auth_required
def get_cluster():
    payload, status = _view(_me())
    return flask.jsonify(payload), status


@bp.route('/api/cluster/vote', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def post_vote():
    body = flask.request.get_json(force=True, silent=True)
    body = body if isinstance(body, dict) else {}
    payload, status = vote(_me(), body.get("benefit"))
    return flask.jsonify(payload), status
