"""
The function app's handlers, run inside the Flask process instead of over HTTP.

Flask calls storage through ``REQUESTS_SESSION`` with URLs such as ``<endpoint>/kingdom/1``. Today those go over HTTP to
the function app (``funcapp/function_app.py``), whose handlers read and write Cosmos DB. ``InProcessSession`` answers
the same calls by running those same handlers in this process: it finds the handler by route and method, builds the
``azure.functions.HttpRequest`` the host would have built, and returns what the handler answers. Nothing in
``funcapp/`` is copied or changed, so the merges, appends, version checks (``funcapp/concurrency.py``) and queue
folding are the ones the function app runs, and a change there applies to both.

This is the backend the tests already use, on an in-memory container (``tests/fake_backend.py``). With a real Cosmos
client it would remove the function app's executions and network hop from production. It is **not wired in**: nothing
in the app uses it yet, and switching production to it is the maintainer's decision (docs/architecture.md, "Why there is
a function app"; the plan is in docs/status.md, "Cost and efficiency").

The Azure packages are imported only when ``load_function_app`` runs, so importing this module costs nothing and needs
neither ``azure-functions`` nor ``azure-cosmos`` installed.
"""
import importlib
import json
import logging
import pathlib
import re
import sys
import threading
import urllib.parse

FUNCAPP_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "funcapp"

# The function app's own modules, imported by name from FUNCAPP_DIR. Loading again drops them so a new client is used.
_FUNCAPP_MODULES = ("function_app", "concurrency", "queues", "notifs")

_load_lock = threading.Lock()
_logger = logging.getLogger(__name__)


def load_function_app(cosmos_client_class=None):
    """
    Import ``funcapp/function_app.py`` and return the module.

    It connects to Cosmos when imported, from the same settings the function app reads (``COSMOS_ENDPOINT``,
    ``COSMOS_KEY``, ``COSMOS_DATABASE_NAME``, ``COSMOS_CONTAINER_NAME``). ``cosmos_client_class`` replaces
    ``azure.cosmos.CosmosClient`` for that import, which is how the tests hand it an in-memory container.
    """
    import azure.cosmos

    with _load_lock:
        real_client = azure.cosmos.CosmosClient
        if cosmos_client_class is not None:
            azure.cosmos.CosmosClient = cosmos_client_class
        sys.path.insert(0, str(FUNCAPP_DIR))
        try:
            for name in _FUNCAPP_MODULES:
                sys.modules.pop(name, None)
            return importlib.import_module("function_app")
        finally:
            azure.cosmos.CosmosClient = real_client
            sys.path.remove(str(FUNCAPP_DIR))


# Route constraints the Functions host checks before a handler runs: ``kingdom/{kdId:int}`` does not match
# ``kingdom/abc``. Only ``int`` is used in funcapp/; another one raises here rather than matching anything.
_CONSTRAINTS = {None: r"[^/]+", "int": r"-?\d+"}


def _parameter(match):
    name, constraint = match[1], match[2]
    if constraint not in _CONSTRAINTS:
        raise NotImplementedError(f"InProcessSession does not know the route constraint {constraint!r}")
    return f"(?P<{name}>{_CONSTRAINTS[constraint]})"


class _Route:
    def __init__(self, pattern, methods, handler):
        self.pattern = pattern
        self.methods = {method.upper() for method in methods}
        self.handler = handler
        self.names = re.findall(r"\{(\w+)(?::\w+)?\}", pattern)
        escaped = re.escape(pattern).replace(r"\{", "{").replace(r"\}", "}")
        self.regex = re.compile("^" + re.sub(r"\{(\w+)(?::(\w+))?\}", _parameter, escaped) + "$")


class Response:
    """The part of ``requests.Response`` the Flask code reads."""

    def __init__(self, status_code, text, headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.content = text.encode()

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return json.loads(self.text)


class InProcessSession:
    """Quacks like the ``requests.Session`` the Flask code uses, but calls the function app's handlers directly."""

    def __init__(self, function_app, raise_errors=False):
        # The Functions host answers 500 when a handler raises, and so does this session, unless ``raise_errors``
        # (the tests set it, so a handler's exception shows where it happened).
        self.raise_errors = raise_errors
        self.routes = []
        for function in function_app.APP.get_functions():
            route = next(b for b in function.get_bindings() if getattr(b, "route", None) is not None)
            methods = [str(m.value) if hasattr(m, "value") else str(m) for m in route.methods]
            self.routes.append(_Route(route.route, methods, function.get_user_function()))
        # A literal route must win over a parameterised one of the same shape (``kingdom/new`` before ``kingdom/{id}``).
        self.routes.sort(key=lambda r: len(r.names))

    def find(self, method, path):
        """The route and its parameters for ``method`` and a path relative to ``/api/``, or ``(None, None)``."""
        for route in self.routes:
            match = route.regex.match(path)
            if match and method.upper() in route.methods:
                return route, match.groupdict()
        return None, None

    def request(self, method, url, params=None, data=None, json=None, headers=None, **kwargs):  # noqa: A002
        import azure.functions as func

        parsed = urllib.parse.urlparse(url)
        path = parsed.path.split("/api/", 1)[-1].strip("/")
        query = {key: values[-1] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        route, route_params = self.find(method, path)
        if route is None:
            return Response(404, f"No route {method} {path}")

        body = b""
        if json is not None:
            import json as json_module
            body = json_module.dumps(json).encode()
        elif data is not None:
            body = data.encode() if isinstance(data, str) else data
        request_headers = {"content-type": "application/json", **{k: str(v) for k, v in (headers or {}).items()}}
        request = func.HttpRequest(
            method=method.upper(), url=url, headers=request_headers, params={**query, **(params or {})},
            route_params=route_params, body=body,
        )
        try:
            response = route.handler(request)
        except Exception:
            if self.raise_errors:
                raise
            _logger.exception("Storage handler %s %s failed", method.upper(), route.pattern)
            return Response(500, "The storage handler failed")
        return Response(response.status_code, response.get_body().decode(), dict(response.headers))

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
