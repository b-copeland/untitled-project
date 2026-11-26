"""
The function app and Cosmos DB, in this process.

The Flask code talks to the function app over HTTP (``REQUESTS_SESSION``), and the function app talks to Cosmos DB. For
tests that is slow (about two seconds a call against the emulator, and ``deleteall`` before every test rewrites every
document) and it forces the tests to share one container, so they can not run side by side.

This replaces only the bottom layer:

* ``FakeContainer`` is a Cosmos container held in a dict. It keeps the properties the code relies on: every write gets a
  new ``_etag``, a replace with ``etag`` and ``match_condition=IfNotModified`` is checked and applied atomically and
  fails with the same exception Cosmos raises, and creating an id twice or reading a missing one fails like Cosmos.
* The real ``funcapp/function_app.py`` runs on top of it, unchanged, including the real ``concurrency.py``. Its handlers
  are called directly instead of over HTTP by ``FakeSession``, which stands in for the ``requests`` session. It is
  ``untitledapp/inprocess.py``'s session, the one production could use in place of the function app, so every test
  also tests that.

So the routes and the version checks are the real ones. What is not tested here is Cosmos itself (the emulator still
is, see ``USE_EMULATOR`` in conftest.py) and the HTTP layer.

``latency`` (seconds, upper bound) sleeps a random short time inside every container call. Without it the calls are so
quick that threads almost never overlap and a race test would pass on code that has the race. A couple of milliseconds
gives the same interleavings as the real network.
"""
import copy
import importlib.util
import json
import os
import pathlib
import random
import re
import sys
import threading
import time

from azure.core import MatchConditions
from azure.cosmos.exceptions import (
    CosmosAccessConditionFailedError,
    CosmosHttpResponseError,
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)


def _load_inprocess():
    """
    ``api/untitledapp/inprocess.py``, loaded from its file: the function app's tests use this module in their own
    environment, which has no Flask, so the ``untitledapp`` package (whose ``__init__`` imports Flask) can not be
    imported there. The module itself needs only the standard library.
    """
    name = "untitled_inprocess"
    if name not in sys.modules:
        path = pathlib.Path(__file__).resolve().parent.parent / "api" / "untitledapp" / "inprocess.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


inprocess = _load_inprocess()


def _copy(doc):
    """
    A private copy of a document. Documents are JSON, as they are in Cosmos, so a round trip through ``json`` (in C)
    copies them several times faster than ``copy.deepcopy``, which was most of a simulation's time. Anything that is
    not JSON falls back to ``deepcopy``, as the tests may hand the container anything.
    """
    try:
        return json.loads(json.dumps(doc))
    except (TypeError, ValueError):
        return copy.deepcopy(doc)


def _not_found(message):
    return CosmosResourceNotFoundError(status_code=404, message=message)


class FakeContainer:
    def __init__(self, latency=0.0):
        self.docs = {}
        self.version = 0
        self.lock = threading.RLock()
        self.latency = latency

    def _pause(self):
        if self.latency:
            time.sleep(random.uniform(0, self.latency))

    def _stamp(self, doc):
        self.version += 1
        doc["_etag"] = f'"{self.version}"'
        doc["_ts"] = int(time.time())
        return doc

    def _store(self, item, doc):
        """Keep ``doc`` (stamped, and the container's own) as ``item``, and return a copy of it for the caller."""
        self.docs[item] = self._stamp(doc)
        return _copy(doc)

    def _read(self, item):
        # A copy of the document as it is now: tests may change ``docs`` directly.
        return _copy(self.docs[item])

    # --- the part of the container API the function app uses -------------------------------------------------------

    def read_item(self, item, partition_key=None, **kwargs):
        self._pause()
        with self.lock:
            if item not in self.docs:
                raise _not_found(f"{item} does not exist")
            return self._read(item)

    def create_item(self, body, **kwargs):
        self._pause()
        with self.lock:
            if body["id"] in self.docs:
                raise CosmosResourceExistsError(status_code=409, message=f"{body['id']} already exists")
            return self._store(body["id"], _copy(body))

    def replace_item(self, item, body, **kwargs):
        self._pause()
        with self.lock:
            if item not in self.docs:
                raise _not_found(f"{item} does not exist")
            etag = kwargs.get("etag")
            if etag and kwargs.get("match_condition") == MatchConditions.IfNotModified and etag != self.docs[item]["_etag"]:
                raise CosmosAccessConditionFailedError(status_code=412, message="The document changed")
            new = {key: value for key, value in body.items() if key not in ("_etag", "_ts", "_rid", "_self", "_attachments")}
            new["id"] = item
            return self._store(item, _copy(new))

    def delete_item(self, item, partition_key=None, **kwargs):
        self._pause()
        with self.lock:
            if item not in self.docs:
                raise _not_found(f"{item} does not exist")
            del self.docs[item]

    def read_all_items(self, **kwargs):
        with self.lock:
            return [self._read(item) for item in self.docs]

    def query_items(self, query, parameters=None, **kwargs):
        """
        Only the queries the function app sends: ``SELECT * FROM c WHERE`` followed by clauses joined with ``AND``,
        each one of ``IS_DEFINED(c.<field>)``, ``c.<field> = @<param>`` or ``STARTSWITH(c.<field>, @<param>)``.
        Anything else raises, so a new query shape needs adding here rather than silently matching everything.
        """
        self._pause()
        prefix = "SELECT * FROM c WHERE "
        if not query.startswith(prefix):
            raise NotImplementedError(f"FakeContainer can not run {query!r}")
        values = {parameter["name"]: parameter["value"] for parameter in parameters or []}
        tests = []
        for clause in query[len(prefix):].split(" AND "):
            clause = clause.strip()
            if match := re.fullmatch(r"IS_DEFINED\(c\.(\w+)\)", clause):
                tests.append(lambda doc, field=match[1]: field in doc)
            elif match := re.fullmatch(r"c\.(\w+) = (@\w+)", clause):
                tests.append(lambda doc, field=match[1], value=values[match[2]]: doc.get(field) == value)
            elif match := re.fullmatch(r"STARTSWITH\(c\.(\w+), (@\w+)\)", clause):
                tests.append(
                    lambda doc, field=match[1], value=values[match[2]]:
                        isinstance(doc.get(field), str) and doc[field].startswith(value)
                )
            else:
                raise NotImplementedError(f"FakeContainer can not run the clause {clause!r}")
        with self.lock:
            return [self._read(item) for item, doc in self.docs.items() if all(test(doc) for test in tests)]

    # --- for tests -------------------------------------------------------------------------------------------------

    def blank(self):
        """
        What the function app's /deleteall does: every document stays, with nothing in it but its id, except users
        and username claims, which are removed.
        """
        with self.lock:
            for doc_id in list(self.docs):
                if doc_id.startswith(("user_", "username_")):
                    del self.docs[doc_id]
                else:
                    self._store(doc_id, {"id": doc_id})

    def reset(self):
        with self.lock:
            self.docs.clear()


class _FakeDatabase:
    def __init__(self, container):
        self._container = container

    def get_container_client(self, name):
        return self._container


class _FakeCosmosClient:
    container = None

    def __init__(self, *args, **kwargs):
        pass

    def create_database_if_not_exists(self, id=None, **kwargs):
        return _FakeDatabase(_FakeCosmosClient.container)


def load_function_app(container):
    """Import funcapp/function_app.py with its Cosmos client replaced by ``container``. Returns the module."""
    os.environ.setdefault("COSMOS_ENDPOINT", "https://fake.invalid")
    os.environ.setdefault("COSMOS_KEY", "fake")
    _FakeCosmosClient.container = container
    return inprocess.load_function_app(cosmos_client_class=_FakeCosmosClient)


class FakeSession(inprocess.InProcessSession):
    """The session production would use in-process (``untitledapp/inprocess.py``), raising a handler's exception."""

    def __init__(self, function_app):
        super().__init__(function_app, raise_errors=True)
