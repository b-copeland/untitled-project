"""STORAGE_BACKEND chooses where storage calls go: the function app over HTTP, or its handlers in this process."""
import flask
import pytest

import untitledapp
from untitledapp import REQUESTS_SESSION, inprocess
from tests import fake_backend


def _app(**config):
    app = flask.Flask("storage-test")
    app.config.update(config)
    return app


@pytest.fixture
def no_backend(monkeypatch):
    """The session as production starts it, with no backend; the tests' own is put back afterwards."""
    monkeypatch.setattr(REQUESTS_SESSION, "backend", None)


def test_the_function_app_is_the_default(no_backend):
    untitledapp.configure_storage(_app())
    untitledapp.configure_storage(_app(STORAGE_BACKEND="functionapp"))
    assert REQUESTS_SESSION.backend is None


def test_an_unknown_backend_stops_the_app_starting(no_backend):
    with pytest.raises(ValueError):
        untitledapp.configure_storage(_app(STORAGE_BACKEND="cosmos"))


def test_in_process_needs_the_cosmos_settings(no_backend, monkeypatch):
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    monkeypatch.setenv("COSMOS_KEY", "k")
    with pytest.raises(RuntimeError, match="COSMOS_ENDPOINT"):
        untitledapp.configure_storage(_app(STORAGE_BACKEND="inprocess"))
    assert REQUESTS_SESSION.backend is None


def test_in_process_runs_the_handlers_here(no_backend, monkeypatch):
    container = fake_backend.FakeContainer()
    container.create_item({"id": "kingdom_3", "name": "Three"})
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.invalid")
    monkeypatch.setenv("COSMOS_KEY", "fake")
    monkeypatch.setattr(inprocess, "load_function_app", lambda: fake_backend.load_function_app(container))
    app = _app(STORAGE_BACKEND="inprocess", AZURE_FUNCTION_ENDPOINT=None)

    untitledapp.configure_storage(app)

    assert isinstance(REQUESTS_SESSION.backend, inprocess.InProcessSession)
    assert app.config["AZURE_FUNCTION_ENDPOINT"] == untitledapp.INPROCESS_ENDPOINT
    # A call through the shared session, with its URL checks, reaches the handler with no HTTP.
    with app.app_context():
        assert REQUESTS_SESSION.get(f"{untitledapp.INPROCESS_ENDPOINT}/kingdom/3").json()["name"] == "Three"


def test_a_backend_the_tests_set_is_kept(monkeypatch):
    mine = REQUESTS_SESSION.backend
    assert mine is not None  # conftest's in-memory one
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.invalid")
    monkeypatch.setenv("COSMOS_KEY", "fake")
    untitledapp.configure_storage(_app(STORAGE_BACKEND="inprocess"))
    assert REQUESTS_SESSION.backend is mine
