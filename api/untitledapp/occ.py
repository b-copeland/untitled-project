"""
Optimistic concurrency for game actions: decide against the state as it is, and commit only if it still is.

The old way to stop two requests from both spending the same money was a lock row in this server's SQLite file. That
only works while exactly one web app instance exists, because every instance has its own file, and it can not protect
writers that never take the lock (for example a refresh adding to another kingdom's siphons).

This does it where the data lives. Cosmos DB gives each document an ``_etag`` that changes on every write, and the
function app (funcapp/concurrency.py) rejects a write that sends ``If-Match: <etag>`` if the document has changed
since. So an action is:

    def decide(kingdom):                     # sees the document as it is right now
        if kingdom["money"] < cost:
            raise occ.Rejected("Not enough money")
        return {"money": kingdom["money"] - cost}, None

    occ.update(f"/kingdom/{kd_id}", decide)

If anything else wrote the kingdom between the read and the write, the write is refused and ``decide`` runs again on
the newer document, where the second of two identical requests now finds the money gone and is rejected. That holds
for any number of web app instances, with no lock state anywhere.

``decide`` can run more than once, so it must not have side effects. Do those after ``update`` returns.
"""
import json
import random
import time

import flask

from untitledapp import REQUESTS_SESSION

MAX_ATTEMPTS = 12


class Rejected(Exception):
    """The action is not allowed given the state it was decided against. Routes turn this into an error response."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


class Busy(Exception):
    """The document kept changing underneath us and we gave up. The caller can simply try again."""


def _url(path):
    return flask.current_app.config["AZURE_FUNCTION_ENDPOINT"] + path


def _headers(**extra):
    return {"x-functions-key": flask.current_app.config["AZURE_FUNCTION_KEY"], **extra}


def read(path):
    """The document at ``path``, including its ``_etag``."""
    return json.loads(REQUESTS_SESSION.get(_url(path), headers=_headers()).text)


def update(path, decide):
    """
    Apply a change to the document at ``path`` that is valid for the document as it is when the change lands.

    ``decide(document)`` returns ``(payload, result)``: the fields to change (``None`` to change nothing) and any
    value to hand back to the caller. It may raise ``Rejected``. Returns ``result``.

    Raises ``Busy`` if the document changed on every one of ``MAX_ATTEMPTS`` attempts.
    """
    for attempt in range(MAX_ATTEMPTS):
        document = read(path)
        payload, result = decide(document)
        if payload is None:
            return result

        response = REQUESTS_SESSION.patch(
            _url(path),
            headers=_headers(**{"If-Match": document["_etag"]}),
            data=json.dumps(payload),
        )
        if response.status_code == 412 or response.status_code == 409:
            # Changed since we read it (412), or the function app gave up merging into a busy document (409).
            time.sleep(random.uniform(0, min(0.01 * 2**attempt, 0.2)))
            continue
        if response.status_code >= 300:
            raise RuntimeError(f"Updating {path} failed with {response.status_code}: {response.text}")
        return result
    raise Busy(path)
