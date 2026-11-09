"""
Optimistic concurrency for the function app's read-modify-write handlers.

Every ``update_*`` handler does the same thing: read a document, change it, write it back. With nothing checking that
the document is still the one that was read, two requests that overlap lose one of the updates (for example, two
appends to the same news list, or two spends from the same kingdom), no matter how many locks the caller holds.

Cosmos DB gives every document an ``_etag`` that changes on each write, and a replace can be made conditional on it.
This module uses that in two ways, and neither needs any shared state, so it keeps working with any number of function
app and web app instances:

1. **Server side, automatic.** A handler wrapped in ``retry_on_conflict`` has its ``replace_item`` made conditional on
   the version it read. If another request got there first, the write is rejected and the whole handler runs again
   against the newer document. Two appends both land; two patches to different fields both land.

2. **Client side, opt-in.** A caller that read a document, decided something based on it, and now wants to write the
   result sends ``If-Match: <the _etag it read>``. If the document changed in between, the answer is ``412`` and the
   caller must read again and re-decide. This is what makes "spend money" safe: the second of two overlapping spends
   fails, re-reads the lower balance, and is rejected by the caller's own validation.

Both only apply inside ``retry_on_conflict``. Anything else that uses the container behaves exactly as before.

Handlers must be safe to run again from the top, which holds when they perform a single ``replace_item`` (all the
``update_*`` handlers do). Handlers that write several documents are not wrapped.
"""
import functools
import random
import threading
import time

import azure.functions as func
from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosAccessConditionFailedError

# Managed by Cosmos. A client that sends back a document it read would otherwise overwrite the fresh values.
SYSTEM_FIELDS = ("_rid", "_self", "_etag", "_attachments", "_ts")

MAX_ATTEMPTS = 12

_local = threading.local()


class _RequestState:
    def __init__(self, if_match):
        self.if_match = if_match
        self.conflict = False
        self.precondition_failed = False
        self.new_etag = None


def _current_state():
    return getattr(_local, "state", None)


class ConditionalContainer:
    """A Cosmos container whose ``replace_item`` is conditional while inside ``retry_on_conflict``."""

    def __init__(self, container):
        self._container = container

    def __getattr__(self, name):
        return getattr(self._container, name)

    def replace_item(self, item, body, **kwargs):
        state = _current_state()
        if state is None:
            return self._container.replace_item(item, body, **kwargs)

        etag = state.if_match or (body.get("_etag") if isinstance(body, dict) else None)
        if etag and "etag" not in kwargs:
            kwargs["etag"] = etag
            kwargs["match_condition"] = MatchConditions.IfNotModified
        try:
            result = self._container.replace_item(item, body, **kwargs)
        except CosmosAccessConditionFailedError:
            state.conflict = True
            state.precondition_failed = bool(state.if_match)
            raise
        state.new_etag = result.get("_etag") if isinstance(result, dict) else None
        return result


class _RequestView:
    """The request, with the fields Cosmos manages removed from JSON bodies."""

    def __init__(self, request):
        self._request = request

    def __getattr__(self, name):
        return getattr(self._request, name)

    def get_json(self):
        body = self._request.get_json()
        if isinstance(body, dict):
            return {key: value for key, value in body.items() if key not in SYSTEM_FIELDS}
        return body


def retry_on_conflict(handler):
    """
    Run a single-write read-modify-write handler so that it can not lose updates.

    - A conflicting write is retried (the handler runs again on the newer document), up to ``MAX_ATTEMPTS`` times with
      a short random backoff, then answers ``409``.
    - If the request has an ``If-Match`` header, the write only happens if the document still has that ``_etag``,
      otherwise the answer is ``412`` and nothing is retried.
    - A successful write returns the document's new ``_etag`` in the ``ETag`` response header.
    """

    @functools.wraps(handler)
    def wrapper(req: func.HttpRequest) -> func.HttpResponse:
        if_match = req.headers.get("If-Match") or None
        view = _RequestView(req)
        for attempt in range(MAX_ATTEMPTS):
            state = _RequestState(if_match)
            _local.state = state
            try:
                response = handler(view)
            finally:
                _local.state = None

            if state.precondition_failed:
                return func.HttpResponse("The document changed since it was read.", status_code=412)
            if not state.conflict:
                if state.new_etag:
                    response.headers["ETag"] = state.new_etag
                return response
            time.sleep(random.uniform(0, min(0.02 * 2**attempt, 0.25)))
        return func.HttpResponse("Too many concurrent updates to this document. Try again.", status_code=409)

    return wrapper
