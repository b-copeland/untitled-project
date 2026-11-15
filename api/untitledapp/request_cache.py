"""
Read a shared document from the function app at most once per Flask request.

Many helpers need the same few documents that every kingdom shares (the game state, the galaxy and empire lists, the
kingdom list, a galaxy's politics), and each used to fetch its own copy: one page load could read ``/galaxies`` three
times, and one refresh tick read it several times per kingdom. ``read(path)`` keeps what it fetched on ``flask.g``,
which belongs to the current request and is gone when it ends. So nothing is shared between requests, processes or
machines (architecture rule 1), and a request still sees other requests' writes as soon as it next starts.

Within a request, any write the request itself sends drops the cached copy of what it wrote (see ``invalidate``,
called by the session for every write), so a request never reads back an older version of something it changed.
Decisions are not affected: ``occ.update`` always reads the document it decides on directly.

Only the paths in ``CACHEABLE`` are cached. Per-kingdom documents are not, because they are what actions change.

The cache exists only between ``start`` and ``end``, which the app runs before and after every request
(``create_app``). Code run outside a request (tests that call helpers directly, scripts) reads afresh every time,
unless it opens a ``scope()`` itself.
"""
import contextlib
import json
import re

import flask

# The documents worth caching: read by many helpers, written rarely.
CACHEABLE = re.compile(r"^/(state|galaxies|empires|kingdoms|galaxy/[^/]+/politics)$")

# Writes that change a cached document, and which one. A write to a per-kingdom document, or to a document that is
# never cached, changes nothing cached. Any other write (creating kingdoms or galaxies, resets, ``/createitem``)
# empties the cache, which is always safe.
_WRITE_DROPS = (
    (re.compile(r"^/updatestate$"), lambda m: "/state"),
    (re.compile(r"^/empires$"), lambda m: "/empires"),
    (re.compile(r"^/kingdoms$"), lambda m: "/kingdoms"),
    (re.compile(r"^/galaxy/([^/]+)/politics$"), lambda m: f"/galaxy/{m.group(1)}/politics"),
)
_WRITES_THAT_CHANGE_NOTHING_CACHED = re.compile(
    r"^/(kingdom/\d+/.+|kingdom/\d+|galaxy/[^/]+/news|empire/[^/]+/(news|politics)|universenews|universepolitics|scores|accounts)$"
)


def start():
    """Open an empty cache for the request that is starting."""
    flask.g._shared_documents = {}


def end(exception=None):
    """Drop the cache when the request ends."""
    flask.g.pop("_shared_documents", None)


@contextlib.contextmanager
def scope():
    """Cache shared documents for the duration of the block, as a request does. Needs an app context."""
    start()
    try:
        yield
    finally:
        end()


def _store():
    if not flask.has_app_context():
        return None
    return flask.g.get("_shared_documents")


def _path(url):
    """``/galaxies`` from ``http://host/api/galaxies?x=1``."""
    path = url.split("?", 1)[0]
    endpoint = flask.current_app.config["AZURE_FUNCTION_ENDPOINT"] or ""
    if endpoint and path.startswith(endpoint):
        path = path[len(endpoint):]
    return "/" + path.strip("/")


def read(path, fetch):
    """
    The document at ``path`` as parsed JSON. ``fetch()`` returns the response text and is only called when this
    request has not read ``path`` yet. Each call returns a fresh copy, so a caller may change what it gets.
    """
    store = _store()
    if store is None or not CACHEABLE.match(path):  # outside a request, or not a shared document
        return json.loads(fetch())
    if path not in store:
        store[path] = fetch()
    return json.loads(store[path])


def invalidate(url):
    """Forget what a write to ``url`` may have changed. Called by the session before and after every write."""
    store = _store()
    if not store:
        return
    path = _path(url)
    for pattern, cached_path in _WRITE_DROPS:
        match = pattern.match(path)
        if match:
            store.pop(cached_path(match), None)
            return
    if _WRITES_THAT_CHANGE_NOTHING_CACHED.match(path):
        return
    store.clear()
