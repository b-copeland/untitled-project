"""
Users, stored in Cosmos through the function app (docs/decisions/0004-users-in-cosmos.md).

Three kinds of document (docs/data-model.md):

* ``user_<id>``: the user's fields, plus ``id_number``, the numeric id that JWTs and email tokens carry.
* ``username_<key>``: ``{"user_id": <id>}``. ``key`` is the lowercase hex of the UTF-8 username, so any name is a
  valid Cosmos id and lookups stay case-sensitive. Creating it is the uniqueness check: the function app answers
  ``409`` if the name is taken.
* ``user_counter``: ``{"next_id": <int>}``, taken with ``occ.update`` so two sign-ups never get the same id.

``User`` is what flask-praetorian works with. It calls only ``lookup``, ``identify``, ``identity``, ``rolenames``,
``password`` and ``is_valid``. ``identify`` is what ``flask_praetorian.current_user()`` calls, every time it is
called, so it reads ``user_<id>`` at most once per request (through ``request_cache``); a write through the shared
session drops that copy, so a request that changes its user reads the new version next.

Changes go through ``save(**fields)`` or ``update(decide)``, both ``occ.update`` on ``user_<id>``. Never set an
attribute and expect it to be stored.
"""
import json

import flask
from flask_praetorian.utilities import app_context_has_jwt_data, get_jwt_data_from_app_context

from untitledapp import REQUESTS_SESSION
import untitledapp.occ as occ
import untitledapp.request_cache as request_cache

# Every stored field, and what a document without it means. Documents written before a field existed lack it.
FIELDS = {
    "username": None,
    "password": None,
    "roles": "",
    "kd_id": None,
    "kd_created": False,
    "kd_death_date": None,
    "is_active": True,
    "is_verified": True,
    "email": None,
    "email_verified": False,
    "banned_at": None,  # set with is_active False by an admin's ban (adminaccounts.py)
    "ban_reason": None,
    "seen": None,  # login signals: [{"kind": "ip" | "device", "hash", "first", "last"}] (adminaccounts.py)
}


class UserExists(Exception):
    """The username is taken."""


def username_key(username):
    """The id-safe form of a username: lowercase hex of its UTF-8 bytes. Case-sensitive, like the names."""
    return username.encode("utf-8").hex()


def _url(path):
    return flask.current_app.config["AZURE_FUNCTION_ENDPOINT"] + path


def _headers():
    return {"x-functions-key": flask.current_app.config["AZURE_FUNCTION_KEY"]}


def _get(path, params=None):
    """The parsed document at ``path``, or None if it does not exist."""
    response = REQUESTS_SESSION.get(_url(path), headers=_headers(), params=params)
    if response.status_code == 404:
        return None
    if response.status_code >= 300:
        raise RuntimeError(f"Reading {path} failed with {response.status_code}: {response.text}")
    return json.loads(response.text)


class User:
    def __init__(self, document):
        self.id = int(document["id_number"])
        for field, default in FIELDS.items():
            setattr(self, field, document.get(field, default))

    def __repr__(self):
        return f"User({self.id}, {self.username!r})"

    @property
    def _path(self):
        return f"/user/{self.id}"

    # --- what flask-praetorian uses --------------------------------------------------------------------------------

    @property
    def identity(self):
        return self.id

    @property
    def rolenames(self):
        return [role for role in (self.roles or "").split(",") if role]

    def is_valid(self):
        return bool(self.is_active)

    @classmethod
    def identify(cls, id):
        """
        The user with this id. A token that carries the kingdom (docs/decisions/0005-kingdom-in-the-token.md) is
        answered from the token, with no read: the full user is only read if something other than the id, roles,
        ``kd_id`` and ``kd_created`` is asked for. Otherwise the document is read at most once per request. None if
        there is none.
        """
        claims = _token_claims()
        if claims is not None and "kd" in claims and not flask.g.get("strict_identify") and str(claims.get("id")) == str(id):
            return TokenUser(claims)
        return cls.read(id)

    @classmethod
    def read(cls, id):
        """The user with this id from the document, read at most once per request. None if there is none."""
        try:
            path = f"/user/{int(id)}"
        except (TypeError, ValueError):
            return None

        def fetch():
            response = REQUESTS_SESSION.get(_url(path), headers=_headers())
            if response.status_code == 404:
                return "null"
            if response.status_code >= 300:
                raise RuntimeError(f"Reading {path} failed with {response.status_code}: {response.text}")
            return response.text

        document = request_cache.read(path, fetch)
        return cls(document) if document else None

    @classmethod
    def lookup(cls, username):
        """The user with exactly this username (case-sensitive), or None."""
        if not isinstance(username, str) or not username:
            return None
        claim = _get(f"/username/{username_key(username)}")
        if claim is None:
            return None
        user = cls.get(claim["user_id"])
        # A claim can outlive its user, or point at an id that was reused (a sign-up before the migration ran).
        if user is None or user.username != username:
            return None
        return user

    # --- reading ---------------------------------------------------------------------------------------------------

    @classmethod
    def get(cls, id):
        """The user with this id as it is now, not memoised. None if there is none."""
        try:
            document = _get(f"/user/{int(id)}")
        except (TypeError, ValueError):
            return None
        return cls(document) if document else None

    @classmethod
    def _query(cls, **filters):
        """Users matching every filter. One cross-partition query: admin and rare paths only."""
        params = {name: str(value) for name, value in filters.items() if value is not None}
        return [cls(document) for document in _get("/users", params=params)["users"]]

    @classmethod
    def all(cls):
        return cls._query()

    @classmethod
    def by_email(cls, email):
        return cls._query(email=email)

    @classmethod
    def by_kd_id(cls, kd_id):
        return cls._query(kd_id=kd_id)

    @classmethod
    def with_prefix(cls, prefix):
        return cls._query(prefix=prefix)

    # --- writing ---------------------------------------------------------------------------------------------------

    def update(self, decide):
        """
        ``occ.update`` on this user. ``decide(user)`` gets the user as stored now and returns ``(fields, result)``,
        like any ``occ.update`` decision, and may raise ``occ.Rejected``. This object is updated to match.
        """
        written = {}

        def decide_document(document):
            fields, result = decide(User(document))
            written.clear()
            written.update(fields or {})
            return fields, result

        result = occ.update(self._path, decide_document)
        for field, value in written.items():
            if field in FIELDS:
                setattr(self, field, value)
        return result

    def save(self, **fields):
        """Store these fields, whatever the user holds now."""
        return self.update(lambda user: (fields, None))

    @classmethod
    def create(cls, username, password, **fields):
        """
        A new user with a hashed ``password``. Raises ``UserExists`` if the name is taken, even by a sign-up that
        started at the same moment.

        Three documents, in an order that never leaves a reachable half-made user: take an id from the counter, claim
        the name for it, then write the user. A crash after the claim leaves the name taken by nobody (see
        decision 0004); a wasted id is harmless.
        """
        unknown = set(fields) - set(FIELDS)
        if unknown:
            raise ValueError(f"Unknown user fields: {sorted(unknown)}")
        id_number = occ.update("/usercounter", lambda counter: ({"next_id": counter["next_id"] + 1}, counter["next_id"]))

        claimed = REQUESTS_SESSION.post(
            _url(f"/username/{username_key(username)}"), headers=_headers(), data=json.dumps({"user_id": id_number}),
        )
        if claimed.status_code == 409:
            raise UserExists(username)
        if claimed.status_code >= 300:
            raise RuntimeError(f"Claiming the username failed with {claimed.status_code}: {claimed.text}")

        document = {**FIELDS, **fields, "username": username, "password": password, "id_number": id_number}
        created = REQUESTS_SESSION.post(_url("/user"), headers=_headers(), data=json.dumps(document))
        if created.status_code >= 300:
            raise RuntimeError(f"Creating user {id_number} failed with {created.status_code}: {created.text}")
        return cls(document)


def _token_claims():
    """The verified claims of this request's token, or None outside an authenticated request."""
    try:
        if flask.has_request_context() and app_context_has_jwt_data():
            return get_jwt_data_from_app_context()
    except Exception:
        pass
    return None


class TokenUser:
    """
    The caller as the login token describes them: id, username, roles, kingdom id and whether the kingdom was created. It is
    what ``current_user()`` returns for most requests, so a poll does not read the user document. Any other field
    (death date, email, ...) and ``save`` use the document, read once per request.

    A token is valid for a day, so a player disabled since it was issued still passes ``is_valid`` here (decision
    0005). ``refresh`` and login read the document.
    """

    def __init__(self, claims):
        self.id = int(claims["id"])
        self.kd_id = claims.get("kd") or None
        self.kd_created = bool(claims.get("kc"))
        self.roles = claims.get("rls", "")
        self.round = claims.get("rnd", "")
        if "un" in claims:  # a token issued before the username was a claim reads it from the document
            self.username = claims["un"]

    @property
    def identity(self):
        return self.id

    @property
    def rolenames(self):
        return [role for role in (self.roles or "").split(",") if role]

    def is_valid(self):
        return True

    def _user(self):
        user = User.read(self.id)
        if user is None:
            raise RuntimeError(f"User {self.id} no longer exists")
        return user

    def __getattr__(self, name):
        # Only called for attributes not set above: the rest of the user's fields and methods.
        if name.startswith("__") or name in ("claims",):
            raise AttributeError(name)
        return getattr(self._user(), name)

    def save(self, **fields):
        user = User.get(self.id)
        result = user.save(**fields)
        self.kd_id = user.kd_id or None
        self.kd_created = bool(user.kd_created)
        return result


def issue_tokens(user, round_id=None):
    """
    A new ``{"accessToken", "refreshToken"}`` pair for ``user`` (a ``User`` read now), with the kingdom and the round
    in the claims. Call it after every change to ``kd_id`` or ``kd_created`` and hand the result to the player.
    """
    guard = flask.current_app.extensions["praetorian"]
    if round_id is None:
        round_id = current_round()
    claims = {"kd": user.kd_id or "", "kc": bool(user.kd_created), "rnd": round_id, "un": user.username}
    return {
        "accessToken": guard.encode_jwt_token(user, **claims),
        "refreshToken": guard.encode_jwt_token(user, **claims),
    }


def current_round():
    """The id of the round now running ('' on a game that has never been reset)."""
    import untitledapp.getters as getters
    try:
        return getters._get_state().get("round", "") or ""
    except ValueError:  # no state document yet (a game that was never initialised)
        return ""


def token_is_stale():
    """True if this request's token was issued in an earlier round. A token without a round (old) is not stale."""
    claims = _token_claims()
    return claims is not None and "rnd" in claims and claims["rnd"] != current_round()


STALE_MESSAGE = "The round has ended. Please log in again."
