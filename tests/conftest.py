import os

import pytest

from untitledapp import create_app, User, REQUESTS_SESSION

@pytest.fixture(scope="session")
def app():
    app = create_app(config_class='config.TestingConfig')
    return app

@pytest.fixture(scope="session")
def client(app):
    with app.test_client() as client:
        with app.app_context():
            db = app.extensions['sqlalchemy']
            guard = app.extensions['praetorian']
            db.drop_all()
            db.create_all()
            db.session.add(User(
                username='admin',
                password=guard.hash_password("admin"),
                roles='operator,admin',
                kd_created=False,
            ))
            db.session.add(User(
                username='user1',
                password=guard.hash_password("user1"),
                roles='operator',
                kd_created=True,
                kd_id=1,
                is_active=True,
            ))
            db.session.add(User(
                username='user2',
                password=guard.hash_password("user2"),
                roles='operator',
                kd_created=True,
                kd_id=2,
                is_active=True,
            ))
            db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()
    return client

@pytest.fixture(scope="session")
def jwt1(client):
    response = client.post("/api/login", json={"username": "user1", "password": "user1"})
    print(response)
    token = response.json["accessToken"]
    return token

@pytest.fixture(scope="session")
def jwt2(client):
    response = client.post("/api/login", json={"username": "user2", "password": "user2"})
    print(response)
    token = response.json["accessToken"]
    return token


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


@pytest.fixture(autouse=True)
def setup(app, backend):
    if USE_EMULATOR:
        REQUESTS_SESSION.post(
            app.config["AZURE_FUNCTION_ENDPOINT"] + f'/deleteall',
            headers={'x-functions-key': app.config["AZURE_FUNCTION_ENDPOINT"] },
        )
    else:
        backend.blank()  # what /deleteall does