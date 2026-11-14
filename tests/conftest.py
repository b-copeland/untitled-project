import os

import pytest

import untitledapp
from untitledapp import create_app, REQUESTS_SESSION

USE_EMULATOR = bool(os.environ.get("USE_EMULATOR"))


@pytest.fixture(scope="session")
def backend():
    """
    The function app and Cosmos DB the Flask code talks to.

    By default they run in this process on an in-memory container (tests/fake_backend.py): no emulator, function host
    or Azurite needed, and a test's data is reset in microseconds. ``USE_EMULATOR=1`` uses the real stack instead (the
    function app on port 7071 over the Cosmos emulator), which is what proves the code against real Cosmos.
    """
    if USE_EMULATOR:
        yield None
        return
    from tests import fake_backend

    container = fake_backend.FakeContainer(latency=float(os.environ.get("FAKE_LATENCY", "0.002")))
    function_app = fake_backend.load_function_app(container)
    session = fake_backend.FakeSession(function_app)
    original_request = REQUESTS_SESSION.request
    REQUESTS_SESSION.request = session.request  # every module shares this one session object
    try:
        yield container
    finally:
        REQUESTS_SESSION.request = original_request


def _empty_backend(app, backend):
    """What every test starts from: every document blank, no users."""
    if USE_EMULATOR:
        REQUESTS_SESSION.post(
            app.config["AZURE_FUNCTION_ENDPOINT"] + f'/deleteall',
            headers={'x-functions-key': app.config["AZURE_FUNCTION_ENDPOINT"] },
        )
    else:
        backend.blank()  # what /deleteall does


@pytest.fixture(scope="session")
def app(backend):
    # After the backend: creating the app creates the test users through the function app.
    return create_app(config_class='config.TestingConfig')


@pytest.fixture(scope="session")
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="session")
def jwt1(client):
    response = client.post("/api/login", json={"username": "user1", "password": "user1"})
    token = response.json["accessToken"]
    return token


@pytest.fixture(scope="session")
def jwt2(client):
    response = client.post("/api/login", json={"username": "user2", "password": "user2"})
    token = response.json["accessToken"]
    return token


@pytest.fixture(autouse=True)
def setup(app, backend):
    _empty_backend(app, backend)
    # The users go with everything else, and come back with the same ids (1, 2, 3), so the session's tokens still
    # name them.
    with app.app_context():
        untitledapp.seed_testing_users()
