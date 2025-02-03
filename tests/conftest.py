import os

import pytest

from api.untitledapp import create_app, User, REQUESTS_SESSION

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


@pytest.fixture(autouse=True)
def setup(app):
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/deleteall',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_ENDPOINT"] },
    )