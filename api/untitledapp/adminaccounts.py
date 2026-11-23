"""
The admin's accounts tools: every account in one list, setting a player's password, banning and unbanning, and the
signals that show which accounts may be one person (docs/admin.md#accounts).

Signals: each player login stores, on the user document, a keyed hash of the address it came from and of the
browser's device id (a random id the login page keeps in local storage). Only the hashes are kept, so the admin sees
that two accounts share an address, never the address itself. Each signal keeps its first and last time; one not seen
for ``SEEN_DAYS`` is dropped at the user's next login or the next new round, and the list ignores it before then.
"""
import datetime
import hashlib
import hmac
import ipaddress

import flask
import flask_praetorian

import untitledapp.getters as uag
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import guard, User

bp = flask.Blueprint("adminaccounts", __name__)

SEEN_DAYS = 90  # how long a login signal is kept after it was last seen
SEEN_PER_KIND = 10  # the most recent addresses (or devices) kept per account
SEEN_RENEW_SECONDS = 24 * 3600  # a signal seen again is rewritten at most this often, so a login rarely writes
MAX_DEVICE_LENGTH = 64
MAX_REASON_LENGTH = 200
BOT_PREFIX = "bot_"  # bots.BOT_PREFIX; not imported, to keep this module light


# --- signals (plain functions, unit tested) -------------------------------------------------------------------------

def client_address(forwarded_for, remote_addr):
    """
    The caller's address. On Azure App Service the front end appends the address it saw to ``X-Forwarded-For``, so the
    last entry is the one to trust (earlier ones are whatever the client sent). It may carry a port. An IPv6 address
    is reduced to its /64 network, which is one household or phone. '' when there is none.
    """
    candidate = (forwarded_for or "").split(",")[-1].strip() or (remote_addr or "").strip()
    if candidate.startswith("[") and "]" in candidate:  # [v6]:port
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1:  # v4:port
        candidate = candidate.split(":")[0]
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return ""
    if address.version == 6:
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def signal_hash(secret, kind, value):
    """A keyed hash of one signal: equal for equal values, and not reversible without the app's secret key."""
    return hmac.new(str(secret).encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()[:24]


def _when(entry):
    return uas.utc(entry["last"])


def prune_seen(seen, now):
    """The signals still kept: seen in the last ``SEEN_DAYS``, and the newest ``SEEN_PER_KIND`` of each kind."""
    cutoff = now - datetime.timedelta(days=SEEN_DAYS)
    kept = []
    for kind in ("ip", "device"):
        recent = sorted((entry for entry in seen or [] if entry.get("kind") == kind and _when(entry) >= cutoff),
                        key=_when, reverse=True)
        kept.extend(recent[:SEEN_PER_KIND])
    return kept


def with_signals(seen, signals, now):
    """
    ``seen`` after a login with ``signals`` (``{kind: hash}``), or None if nothing needs writing: every signal is
    already there and was last written less than ``SEEN_RENEW_SECONDS`` ago, and nothing has expired.
    """
    seen = [dict(entry) for entry in seen or []]
    changed = False
    for kind, value in signals.items():
        if not value:
            continue
        entry = next((e for e in seen if e.get("kind") == kind and e.get("hash") == value), None)
        if entry is None:
            seen.append({"kind": kind, "hash": value, "first": now.isoformat(), "last": now.isoformat()})
            changed = True
        elif (now - _when(entry)).total_seconds() >= SEEN_RENEW_SECONDS:
            entry["last"] = now.isoformat()
            changed = True
    kept = prune_seen(seen, now)
    if len(kept) != len(seen):
        changed = True
    return kept if changed else None


def login_signals(request, body):
    """The hashed signals of this login: the address, and the device id if the page sent a usable one."""
    secret = flask.current_app.config["SECRET_KEY"]
    signals = {}
    address = client_address(request.headers.get("X-Forwarded-For"), request.remote_addr)
    if address:
        signals["ip"] = signal_hash(secret, "ip", address)
    device = body.get("device") if isinstance(body, dict) else None
    if isinstance(device, str) and 0 < len(device.strip()) <= MAX_DEVICE_LENGTH:
        signals["device"] = signal_hash(secret, "device", device.strip())
    return signals


def record_login(user, request, body):
    """
    Store this login's signals on ``user``. At most one write, and none when the signals are already stored and fresh.
    Never fails the login: a failure is logged and the login goes on.
    """
    try:
        signals = login_signals(request, body)
        now = datetime.datetime.now(datetime.timezone.utc)
        if with_signals(user.seen, signals, now) is None:
            return

        def decide(stored):
            updated = with_signals(stored.seen, signals, now)
            return ({"seen": updated} if updated is not None else None), None

        user.update(decide)
    except Exception:  # noqa: BLE001 - recording is never worth a failed login
        flask.current_app.logger.exception("Could not record the login signals of user %s", user.id)


def shared_signals(users, now):
    """
    For each user id, the other accounts that share a signal with it in the last ``SEEN_DAYS``:
    ``{id: [{"id", "username", "ip", "device"}]}``, where ``ip`` and ``device`` say what they share. One pass over the
    list, no reads.
    """
    by_signal = {}
    for user in users:
        for entry in prune_seen(user.seen, now):
            by_signal.setdefault((entry["kind"], entry["hash"]), set()).add(user.id)
    names = {user.id: user.username for user in users}
    shared = {}
    for (kind, _), ids in by_signal.items():
        if len(ids) < 2:
            continue
        for user_id in ids:
            for other in ids - {user_id}:
                row = shared.setdefault(user_id, {}).setdefault(
                    other, {"id": other, "username": names[other], "ip": False, "device": False})
                row[kind] = True
    return {user_id: sorted(rows.values(), key=lambda row: row["username"].lower()) for user_id, rows in shared.items()}


# --- the routes -----------------------------------------------------------------------------------------------------

def _account_row(user, kingdoms, shares, now):
    seen = prune_seen(user.seen, now)
    last_seen = max((entry["last"] for entry in seen), key=uas.utc, default="")
    return {
        "id": user.id,
        "username": user.username,
        "roles": user.rolenames,
        "admin": "admin" in user.rolenames,
        "bot": str(user.username).startswith(BOT_PREFIX),
        "kd_id": user.kd_id or "",
        "kingdom": kingdoms.get(str(user.kd_id), "") if user.kd_id else "",
        "email": user.email or "",
        "email_verified": bool(user.email_verified),
        "banned": not user.is_active,
        "banned_at": user.banned_at or "",
        "ban_reason": user.ban_reason or "",
        "last_login": last_seen,
        "addresses": sum(1 for entry in seen if entry["kind"] == "ip"),
        "devices": sum(1 for entry in seen if entry["kind"] == "device"),
        "shares": shares.get(user.id, []),
    }


@bp.route('/api/admin/accounts', methods=["GET"])
@flask_praetorian.roles_required('admin')
def list_accounts():
    """Every account, with its kingdom, ban and the accounts it shares a login signal with. Two reads in all."""
    now = datetime.datetime.now(datetime.timezone.utc)
    users = User.all()
    try:
        kingdoms = uag._get_kingdoms()
    except ValueError:  # a game never set up has no kingdoms document; accounts still list
        kingdoms = {}
    shares = shared_signals(users, now)
    return flask.jsonify({
        "accounts": [_account_row(user, kingdoms, shares, now) for user in users],
        "seen_days": SEEN_DAYS,
    }), 200


def _account(user_id):
    user = User.get(user_id)
    if user is None:
        flask.abort(flask.make_response(flask.jsonify({"message": "No such account"}), 404))
    return user


def _reply(message, user, status=200):
    now = datetime.datetime.now(datetime.timezone.utc)
    return flask.jsonify({"message": message, "status": "success", "account": _account_row(user, {}, {}, now)}), status


@bp.route('/api/admin/accounts/<int:user_id>/password', methods=["POST"])
@flask_praetorian.roles_required('admin')
def set_password(user_id):
    """Body ``{"password"}``. Sets the account's password. Its email reset links stop working, as after any change."""
    password = (flask.request.get_json(force=True, silent=True) or {}).get("password")
    if not isinstance(password, str) or len(password) == 0:
        return flask.jsonify({"message": "Password must be at least 1 character"}), 400
    user = _account(user_id)
    hashed = guard.hash_password(password)
    try:
        user.save(password=hashed)
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return _reply(f"Password changed for {user.username}", user)


@bp.route('/api/admin/accounts/<int:user_id>/ban', methods=["POST"])
@flask_praetorian.roles_required('admin')
def ban(user_id):
    """
    Body ``{"reason"}`` (optional). The account can not log in or renew its token; a token already issued works until
    it expires, at most a day (decision 0005). Its kingdom stays. An admin account can not be banned here.
    """
    reason = (flask.request.get_json(force=True, silent=True) or {}).get("reason") or ""
    if not isinstance(reason, str) or len(reason) > MAX_REASON_LENGTH:
        return flask.jsonify({"message": f"The reason must be at most {MAX_REASON_LENGTH} characters"}), 400
    user = _account(user_id)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def decide(stored):
        if "admin" in stored.rolenames:
            raise occ.Rejected("An admin account can not be banned")
        # Banning again only changes the reason: the date stays the first one.
        return {"is_active": False, "ban_reason": reason.strip() or None,
                "banned_at": stored.banned_at if not stored.is_active and stored.banned_at else now}, None

    try:
        user.update(decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return _reply(f"{user.username} is banned", user)


@bp.route('/api/admin/accounts/<int:user_id>/unban', methods=["POST"])
@flask_praetorian.roles_required('admin')
def unban(user_id):
    user = _account(user_id)
    try:
        user.save(is_active=True, ban_reason=None, banned_at=None)
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    return _reply(f"{user.username} can log in again", user)
