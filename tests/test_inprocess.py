"""
The in-process storage session (``api/untitledapp/inprocess.py``): the function app's handlers called without HTTP.

Every other test already runs through it (``tests/fake_backend.py``'s ``FakeSession`` is this session), so these cover
what the rest do not: how it finds a route, what it answers when a handler fails, and that importing it is free.
"""
import pathlib
import subprocess
import sys

import pytest

from tests import fake_backend

inprocess = fake_backend.inprocess
API_DIR = pathlib.Path(__file__).resolve().parent.parent / "api"


@pytest.fixture
def container():
    return fake_backend.FakeContainer()


@pytest.fixture
def function_app(container):
    return fake_backend.load_function_app(container)


@pytest.fixture
def session(function_app):
    """As production would build it: constraints checked, a failing handler answered with 500."""
    return inprocess.InProcessSession(function_app)


def test_importing_needs_no_azure_package():
    """The web app imports it without ``azure-functions`` or ``azure-cosmos``: they load only with the handlers."""
    code = (
        "import sys; import untitledapp.inprocess; "
        "loaded = [m for m in sys.modules if m.startswith('azure')]; "
        "assert not loaded, loaded"
    )
    subprocess.run([sys.executable, "-c", code], cwd=API_DIR, check=True)


def test_every_function_has_a_route(session):
    """One route per ``@APP.route`` in the function app (``APP.get_functions()`` can be called once per load)."""
    source = (inprocess.FUNCAPP_DIR / "function_app.py").read_text(encoding="utf-8")
    assert len(session.routes) == source.count("@APP.route(")


def test_a_literal_route_wins_over_a_parameter(session):
    """Each route with no parameters is found by its own path, whatever parameterised route also matches it."""
    for route in session.routes:
        if route.names:
            continue
        for method in route.methods:
            found, _ = session.find(method, route.pattern)
            assert found is route, f"{method} {route.pattern} found {found.pattern}"


def test_an_int_parameter_must_be_a_number(session):
    found, params = session.find("GET", "kingdom/12")
    assert found.pattern == "kingdom/{kdId:int}" and params == {"kdId": "12"}
    assert session.find("GET", "kingdom/abc") == (None, None)
    assert session.find("GET", "kingdom/1?x") == (None, None)
    assert session.get("https://x.invalid/api/kingdom/abc").status_code == 404


def test_reads_and_conditional_writes_round_trip(container, session):
    container.create_item({"id": "kingdom_7", "name": "Seven", "money": 10})
    base = "https://x.invalid/api"
    read = session.get(f"{base}/kingdom/7")
    assert read.ok and read.json()["money"] == 10
    etag = read.json()["_etag"]

    written = session.patch(f"{base}/kingdom/7", json={"money": 5}, headers={"If-Match": etag})
    assert written.status_code == 200 and written.headers["ETag"] != etag
    # The same version again: the document changed since, so nothing is written.
    stale = session.patch(f"{base}/kingdom/7", json={"money": 0}, headers={"If-Match": etag})
    assert stale.status_code == 412
    assert session.get(f"{base}/kingdom/7").json()["money"] == 5


def test_a_failing_handler_answers_500_like_the_host(container, session):
    route, _ = session.find("GET", "kingdom/1")

    def broken(request):
        raise RuntimeError("boom")

    route.handler = broken
    assert session.get("https://x.invalid/api/kingdom/1").status_code == 500

    raising = inprocess.InProcessSession(fake_backend.load_function_app(container), raise_errors=True)
    raising_route, _ = raising.find("GET", "kingdom/1")
    raising_route.handler = broken
    with pytest.raises(RuntimeError):
        raising.get("https://x.invalid/api/kingdom/1")
