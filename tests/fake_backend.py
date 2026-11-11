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
  are called directly instead of over HTTP by ``FakeSession``, which stands in for the ``requests`` session.

So the routes and the version checks are the real ones. What is not tested here is Cosmos itself (the emulator still
is, see ``USE_EMULATOR`` in conftest.py) and the HTTP layer.

``latency`` (seconds, upper bound) sleeps a random short time inside every container call. Without it the calls are so
quick that threads almost never overlap and a race test would pass on code that has the race. A couple of milliseconds
gives the same interleavings as the real network.
"""
import copy
import importlib
import json
import os
import pathlib
import random
import re
import sys
import threading
import time
import types
import urllib.parse

from azure.core import MatchConditions
from azure.cosmos.exceptions import (
    CosmosAccessConditionFailedError,
    CosmosHttpResponseError,
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)

FUNCAPP_DIR = pathlib.Path(__file__).resolve().parent.parent / "funcapp"


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

    # --- the part of the container API the function app uses -------------------------------------------------------

    def read_item(self, item, partition_key=None, **kwargs):
        self._pause()
        with self.lock:
            if item not in self.docs:
                raise _not_found(f"{item} does not exist")
            return copy.deepcopy(self.docs[item])

    def create_item(self, body, **kwargs):
        self._pause()
        with self.lock:
            if body["id"] in self.docs:
                raise CosmosResourceExistsError(status_code=409, message=f"{body['id']} already exists")
            self.docs[body["id"]] = self._stamp(copy.deepcopy(body))
            return copy.deepcopy(self.docs[body["id"]])

    def replace_item(self, item, body, **kwargs):
        self._pause()
        with self.lock:
            if item not in self.docs:
                raise _not_found(f"{item} does not exist")
            etag = kwargs.get("etag")
            if etag and kwargs.get("match_condition") == MatchConditions.IfNotModified and etag != self.docs[item]["_etag"]:
                raise CosmosAccessConditionFailedError(status_code=412, message="The document changed")
            new = {key: value for key, value in copy.deepcopy(body).items() if key not in ("_etag", "_ts", "_rid", "_self", "_attachments")}
            new["id"] = item
            self.docs[item] = self._stamp(new)
            return copy.deepcopy(self.docs[item])

    def delete_item(self, item, partition_key=None, **kwargs):
        self._pause()
        with self.lock:
            if item not in self.docs:
                raise _not_found(f"{item} does not exist")
            del self.docs[item]

    def read_all_items(self, **kwargs):
        with self.lock:
            return [copy.deepcopy(doc) for doc in self.docs.values()]

    # --- for tests -------------------------------------------------------------------------------------------------

    def blank(self):
        """What the function app's /deleteall does: every document stays, with nothing in it but its id."""
        with self.lock:
            for doc_id in list(self.docs):
                self.docs[doc_id] = self._stamp({"id": doc_id})

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
    import azure.cosmos

    os.environ.setdefault("COSMOS_ENDPOINT", "https://fake.invalid")
    os.environ.setdefault("COSMOS_KEY", "fake")
    _FakeCosmosClient.container = container
    real_client = azure.cosmos.CosmosClient
    azure.cosmos.CosmosClient = _FakeCosmosClient
    sys.path.insert(0, str(FUNCAPP_DIR))
    try:
        for name in ("function_app", "concurrency"):
            sys.modules.pop(name, None)
        return importlib.import_module("function_app")
    finally:
        azure.cosmos.CosmosClient = real_client
        sys.path.remove(str(FUNCAPP_DIR))


class _Route:
    def __init__(self, pattern, methods, handler):
        self.methods = {method.upper() for method in methods}
        self.handler = handler
        self.names = re.findall(r"\{(\w+)(?::\w+)?\}", pattern)
        regex = re.sub(r"\{(\w+)(?::\w+)?\}", r"(?P<\1>[^/]+)", re.escape(pattern).replace(r"\{", "{").replace(r"\}", "}"))
        self.regex = re.compile("^" + regex + "$")


class FakeSession:
    """Quacks like the ``requests.Session`` the Flask code uses, but calls the function app's handlers directly."""

    def __init__(self, function_app):
        self.routes = []
        for function in function_app.APP.get_functions():
            route = next(b for b in function.get_bindings() if getattr(b, "route", None) is not None)
            methods = [str(m.value) if hasattr(m, "value") else str(m) for m in route.methods]
            self.routes.append(_Route(route.route, methods, function.get_user_function()))
        # a literal route must win over a parameterised one with the same shape
        self.routes.sort(key=lambda r: len(r.names))

    def request(self, method, url, params=None, data=None, json=None, headers=None, **kwargs):  # noqa: A002
        import azure.functions as func

        parsed = urllib.parse.urlparse(url)
        path = parsed.path.split("/api/", 1)[-1].strip("/")
        query = {key: values[-1] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        for route in self.routes:
            match = route.regex.match(path)
            if match and method.upper() in route.methods:
                break
        else:
            return _Response(404, f"No route {method} {path}")

        body = b""
        if json is not None:
            import json as json_module
            body = json_module.dumps(json).encode()
        elif data is not None:
            body = data.encode() if isinstance(data, str) else data
        request_headers = {"content-type": "application/json", **{k: str(v) for k, v in (headers or {}).items()}}
        request = func.HttpRequest(
            method=method.upper(), url=url, headers=request_headers, params={**query, **(params or {})},
            route_params=match.groupdict(), body=body,
        )
        response = route.handler(request)
        return _Response(response.status_code, response.get_body().decode(), dict(response.headers))

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


class _Response:
    def __init__(self, status_code, text, headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.content = text.encode()

    def json(self):
        return json.loads(self.text)
