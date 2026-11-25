import datetime
import os
import re
import urllib.parse
import requests
import json
import time
import logging

from functools import wraps

import flask
import flask_praetorian
import flask_cors
from flask_mail import Mail
from flask_limiter import Limiter
from flask_sock import Sock

guard = flask_praetorian.Praetorian()
cors = flask_cors.CORS()
mail = Mail()

class UnsafePath(ValueError):
    """A function app URL with something in it other than plain path segments (see ``_FunctionAppSession``)."""


# Every function app route is plain segments: names, numbers, galaxy ids ("1:2") and the hex of a username (users.py).
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_:-]+$")
# What Cosmos adds to every document, and the `type` the function app gives each document of a kingdom when it makes
# it (`create_kingdom`): a write of a whole document read back carries them along.
_COSMOS_FIELDS = {"id", "type", "_etag", "_ts", "_rid", "_self", "_attachments"}


def check_function_url(url, method="GET", data=None):
    """
    Refuse a function app URL that is not plain path segments, and return the body to send: for a write to a kingdom
    document, without any field kingdoms do not have.

    Ids from a request go into these URLs, and Flask decodes the URL before the route sees it, so an id of
    ``29%3Fx`` arrives as ``29?x``. Pasted into ``/kingdom/29?x/messages`` it would cut the path short, and the
    write meant for kingdom 29's messages would land on kingdom 29's own document (issue #219). Routes check their
    ids too; this is the backstop for every call, whatever the route forgot. Query strings go in ``params=``.

    An unknown kingdom field is dropped and logged rather than refused, so a kingdom that already carries one (written
    before this check) can still be written whole. With ``STRICT_KINGDOM_FIELDS`` (the tests) it raises, so a new
    field missing from ``KINGDOM_FIELDS`` fails a test instead of being dropped.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.query or parts.fragment or "?" in url or "#" in url:
        raise UnsafePath(f"Function app URL with a query or fragment: {url!r}")
    segments = parts.path.strip("/").split("/")
    if not all(_SAFE_SEGMENT.match(segment) for segment in segments):
        raise UnsafePath(f"Function app URL with an unsafe segment: {url!r}")
    if method != "PATCH" or len(segments) < 2 or segments[-2] != "kingdom" or not data:
        return data
    from untitledapp.shared import KINGDOM_FIELDS
    try:
        fields = json.loads(data)
    except (TypeError, ValueError):
        return data
    if not isinstance(fields, dict):
        return data
    unknown = sorted(set(fields) - KINGDOM_FIELDS - _COSMOS_FIELDS)
    if not unknown:
        return data
    if flask.has_app_context() and flask.current_app.config.get("STRICT_KINGDOM_FIELDS"):
        raise UnsafePath(f"Kingdom write with fields kingdoms do not have: {unknown}")
    logging.warning("Dropped fields kingdoms do not have from a write to %s: %s", parts.path, unknown)
    return json.dumps({key: value for key, value in fields.items() if key not in unknown})


def _refuse_unsafe_path_ids():
    """For ``before_request``: a 404 for a route whose id from the path is not a plain id. Flask has decoded the path
    by now, so ``%3F`` is a ``?`` here; see ``check_function_url``. Only API routes: the static files' paths have
    dots and slashes."""
    if not flask.request.path.startswith("/api/"):
        return None
    for value in (flask.request.view_args or {}).values():
        if isinstance(value, str) and not _SAFE_SEGMENT.match(value):
            return flask.jsonify({"message": "There is nothing here by that name"}), 404
    return None


def _unsafe_path_response(error):
    logging.warning("Refused an unsafe function app call: %s", error)
    return flask.jsonify({"message": "That request is not valid"}), 400


class _FunctionAppSession(requests.Session):
    """The session every module uses to call the function app. Every URL is checked first (``check_function_url``).
    A write drops what this request has cached of the document it changes (see request_cache.py), before it is sent
    and again after, so no read in between or after sees the old version."""

    def get(self, url, **kwargs):
        check_function_url(url)
        kwargs.setdefault("allow_redirects", True)
        return self.request("GET", url, **kwargs)

    def _write(self, method, url, **kwargs):
        from untitledapp import request_cache
        if "data" in kwargs:
            kwargs["data"] = check_function_url(url, method, kwargs["data"])
        else:
            check_function_url(url, method)
        request_cache.invalidate(url)
        try:
            return self.request(method, url, **kwargs)
        finally:
            request_cache.invalidate(url)

    def post(self, url, data=None, json=None, **kwargs):
        return self._write("POST", url, data=data, json=json, **kwargs)

    def put(self, url, data=None, **kwargs):
        return self._write("PUT", url, data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        return self._write("PATCH", url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self._write("DELETE", url, **kwargs)


REQUESTS_SESSION = _FunctionAppSession()

from untitledapp.sockets import Registry  # noqa: E402

SOCKETS = Registry()  # this process's open notification sockets, by kingdom (sockets.py)

# Users live in Cosmos, behind the function app (users.py, docs/decisions/0004-users-in-cosmos.md).
from untitledapp.users import User, UserExists  # noqa: E402


def _stale_round_response():
    """A 401 if this request's token is from an earlier round (decision 0005), else None. One cached read of the state per request."""
    from untitledapp import users
    if users.token_is_stale():
        return flask.jsonify({"message": users.STALE_MESSAGE}), 401
    return None

def alive_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        stale = _stale_round_response()
        if stale:
            return stale
        kd_death_date = flask_praetorian.current_user().kd_death_date
        if kd_death_date not in (None, ""):
            return flask.jsonify({"message": "You can not do that because your kingdom is dead!"}), 400
        return f(*args, **kwargs)
    return decorated_function

def start_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        stale = _stale_round_response()
        if stale:
            return stale
        state = uag._get_state()
        time_now = datetime.datetime.now(datetime.timezone.utc)
        if time_now < uas.utc(state["state"]["game_start"]):
            return flask.jsonify({"message": "The game has not yet started!"}), 400
        return f(*args, **kwargs)
    return decorated_function

def before_start_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        stale = _stale_round_response()
        if stale:
            return stale
        state = uag._get_state()
        time_now = datetime.datetime.now(datetime.timezone.utc)
        if time_now > uas.utc(state["state"]["game_start"]):
            return flask.jsonify({"message": "The game has already started!"}), 400
        return f(*args, **kwargs)
    return decorated_function

import untitledapp.getters as uag
import untitledapp.shared as uas
import untitledapp.sockets as untitledapp_sockets

# Every route together, per address: a page load is a few dozen requests and a household may share an address.
ADDRESS_LIMIT = "600 per minute"
# Routes with a tighter limit of their own. Logging in hashes the password (slow on purpose, so a flood of logins is a
# flood of CPU), and signing up or the email routes create accounts or send mail.
ROUTE_LIMITS = (
    ("account.login", "10 per minute"),
    ("account.refresh", "10 per minute"),
    ("account.signup", "5 per hour"),
    ("admin.admin_login", "5 per minute"),
    ("account.forgot_password", "5 per minute"),
    ("account.forgot_username", "5 per minute"),
    ("account.reset_password", "10 per minute"),
    ("account.verify_email", "10 per minute"),
    ("account.set_email", "5 per minute"),
    ("account.resend_verification", "5 per minute"),
    ("board.post_to_board", "10 per minute"),
    # One read per kingdom asked for: the Conquer page asks twice when it opens.
    ("getters.max_kingdoms", "20 per minute"),
)


def _address_key():
    """The caller's address (the last ``X-Forwarded-For`` entry, the one App Service adds; see ``client_address``)."""
    from untitledapp.adminaccounts import client_address
    request = flask.request
    return "address:" + (client_address(request.headers.get("X-Forwarded-For"), request.remote_addr) or "unknown")


def _limit_key():
    """
    Who a request counts against: the user of a valid, unexpired login token, else the caller's address.

    Not the token itself: anyone can make up a token string, and a logged-in player can mint new ones with
    ``/api/refresh``, so a key per token gave every request a fresh allowance (issue #219). Checking the signature is
    a hash, no read. The result is kept for the request, as each limit asks for it.
    """
    if "limit_key" in flask.g:
        return flask.g.limit_key
    key = None
    try:
        token = guard.read_token_from_header()
        key = f"user:{guard.extract_jwt_token(token)['id']}"
    except Exception:  # no token, or a forged, expired or malformed one
        key = _address_key()
    flask.g.limit_key = key
    return key

def _ensure_user(username, password, **fields):
    """Create the user unless the name is taken. Safe when several processes start at once: one claim wins."""
    if User.lookup(username) is not None:
        return
    try:
        User.create(username, guard.hash_password(password), **fields)
    except UserExists:
        pass


# The test users, created afresh for every test (tests/conftest.py). Their hashes are computed once per process:
# hashing is slow on purpose, and the passwords are the well-known test ones.
TESTING_USERS = (
    ("admin", {"roles": "operator,admin", "kd_created": False}),
    ("user1", {"roles": "operator", "kd_created": True, "kd_id": "1", "is_active": True}),
    ("user2", {"roles": "operator", "kd_created": True, "kd_id": "2", "is_active": True}),
)
_testing_hashes = {}


def seed_testing_users():
    """Create the test users in an empty container, in order, so they get ids 1, 2 and 3. Needs an app context."""
    for username, fields in TESTING_USERS:
        if username not in _testing_hashes:
            _testing_hashes[username] = guard.hash_password(username)
        try:
            User.create(username, _testing_hashes[username], **fields)
        except UserExists:
            pass


def create_app(config_class='config.Config'):
    # Initialize flask app for the example
    app = flask.Flask(__name__, static_folder='../../build', static_url_path=None)
    app.config.from_object(config_class)
    app.debug = True

    app.logger.addHandler(logging.StreamHandler())

    # Initialize the flask-praetorian instance for the app
    guard.init_app(app, User)
    app.extensions["praetorian"] = guard

    # Initializes CORS so that the api_tool can talk to the example app
    cors.init_app(app)

    mail.init_app(app)

    sock = Sock(app)
    if config_class.lower() == "config.config":
        with app.app_context():
            _ensure_user("admin", os.environ["ADMIN_PASSWORD"], roles="operator,admin", kd_created=True)
    elif config_class.lower() == "config.testingconfig":
        with app.app_context():
            seed_testing_users()

    # Shared documents are read at most once per request (request_cache.py).
    from untitledapp import request_cache
    app.before_request(request_cache.start)
    app.teardown_request(request_cache.end)

    import untitledapp.account as uaa
    import untitledapp.advisors as uaadv
    import untitledapp.admin as uaad
    import untitledapp.adminaccounts as uaadac
    import untitledapp.board as uabo
    import untitledapp.build as uab
    import untitledapp.clusters as uacl
    import untitledapp.conquer as uac
    import untitledapp.intel as uai
    import untitledapp.misc as uam
    import untitledapp.politics as uap
    import untitledapp.preferences as uapr
    import untitledapp.recurring as uarec
    import untitledapp.refresh as uar
    import untitledapp.rules as uarules
    import untitledapp.roundend as uare
    import untitledapp.targets as uat
    app.register_blueprint(uaa.bp)
    app.register_blueprint(uaad.bp)
    app.register_blueprint(uaadac.bp)
    app.register_blueprint(uab.bp)
    app.register_blueprint(uacl.bp)
    app.register_blueprint(uac.bp)
    app.register_blueprint(uai.bp)
    app.register_blueprint(uag.bp)
    app.register_blueprint(uam.bp)
    app.register_blueprint(uap.bp)
    app.register_blueprint(uapr.bp)
    app.register_blueprint(uar.bp)
    app.register_blueprint(uarec.bp)
    app.register_blueprint(uarules.bp)
    app.register_blueprint(uare.bp)
    app.register_blueprint(uat.bp)
    app.register_blueprint(uabo.bp)
    app.register_blueprint(uaadv.bp)
    app.before_request(uare.frozen_response)  # once the round is over, the game is read only
    app.before_request(_refuse_unsafe_path_ids)
    app.register_error_handler(UnsafePath, _unsafe_path_response)

    # Limits (docs/architecture.md#rate-limits): each route allows 100 a minute per user (per address without a
    # login), and every route together allows ADDRESS_LIMIT per address, however many accounts or tokens it uses. The
    # tick (`refreshdata`) is called by the scheduler with its own secret and is not limited.
    limiter = Limiter(
        _limit_key,
        app=app,
        default_limits=["100 per minute",],
        storage_uri="memory://",
    )

    app.extensions["limiter_ref"] = limiter  # the per-route limits below hold only a weak reference to it
    for endpoint, limit in ROUTE_LIMITS:
        app.view_functions[endpoint] = limiter.limit(limit)(app.view_functions[endpoint])
    address_limit = limiter.shared_limit(ADDRESS_LIMIT, scope="address", key_func=_address_key, override_defaults=False)
    for endpoint, view in list(app.view_functions.items()):
        if endpoint == "refresh.refresh_data":
            app.view_functions[endpoint] = limiter.exempt(view)
        elif endpoint != "static":
            app.view_functions[endpoint] = address_limit(view)

    def kingdom_for_token(token):
        """The kingdom of a valid, unexpired login token's user (one read: the socket outlives any request cache)."""
        user = User.get(guard.extract_jwt_token(token)["id"])
        if user is None or not user.is_valid() or user.kd_id is None:
            raise ValueError("No kingdom for this token")
        return user.kd_id

    @sock.route('/ws/listen')
    def listen(ws):
        """Notification pushes (push.py). The browser sends ``{"jwt": ...}`` on opening and every minute after."""
        from untitledapp.adminaccounts import client_address
        address = client_address(flask.request.headers.get("X-Forwarded-For"), flask.request.remote_addr)
        untitledapp_sockets.serve(ws, SOCKETS, kingdom_for_token, logger=sock.app.logger, address=address)


    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        if path != "" and os.path.exists(os.path.join('..','build',path)):
            return app.send_static_file(path)
        else:
            return app.send_static_file('index.html')

    return app