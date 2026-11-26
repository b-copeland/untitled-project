"""
The rate limits count against the caller, not against the token string they send (issue #219).

A limit keyed on the raw ``Authorization`` header gave every made-up token a fresh allowance. Each test makes its own app
with the limits on (``RateLimitTestingConfig``), so the counts start at zero and the session's app is not touched.
"""
import pytest

import untitledapp
from untitledapp import create_app


@pytest.fixture
def limited(backend):
    app = create_app(config_class="config.RateLimitTestingConfig")
    with app.app_context():
        untitledapp.seed_testing_users()
    return app


def _get(client, path, token=None, address="203.0.113.7"):
    headers = {"X-Forwarded-For": address}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.get(path, headers=headers)


def _login(client, username, address="203.0.113.7"):
    return client.post("/api/login", json={"username": username, "password": username},
                       headers={"X-Forwarded-For": address})


def test_made_up_tokens_share_the_callers_allowance(limited):
    client = limited.test_client()
    statuses = [_get(client, "/api/kingdoms", token=f"made-up-{i}").status_code for i in range(101)]

    assert statuses[:100] == [401] * 100
    assert statuses[100] == 429


def test_two_tokens_of_one_user_share_one_allowance(limited):
    client = limited.test_client()
    tokens = [_login(client, "user1").json["accessToken"] for _ in range(2)]
    statuses = [_get(client, "/api/preferences", token=tokens[i % 2], address=f"198.51.100.{i}").status_code
                for i in range(101)]

    assert 429 not in statuses[:100]
    assert statuses[100] == 429


def test_logins_are_limited_per_address_whatever_the_username(limited):
    client = limited.test_client()
    statuses = [_login(client, f"nobody{i}").status_code for i in range(11)]

    assert 429 not in statuses[:10]
    assert statuses[10] == 429
    # Another address still logs in.
    assert _login(client, "user1", address="203.0.113.8").status_code == 200


def test_every_route_together_is_limited_per_address(limited, monkeypatch):
    client = limited.test_client()
    # 600 a minute in all, spread over routes that each allow 100.
    paths = ["/api/kingdoms", "/api/galaxies", "/api/empires", "/api/kingdom", "/api/preferences", "/api/news", "/api/messages"]
    statuses = [_get(client, paths[i % len(paths)], token=f"made-up-{i}").status_code for i in range(601)]

    assert 429 not in statuses[:600]
    assert statuses[600] == 429


def test_the_tick_is_not_limited(limited, monkeypatch):
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    client = limited.test_client()
    statuses = [
        client.get("/api/refreshdata", headers={"Refresh-Secret": "wrong", "X-Forwarded-For": "203.0.113.7"}).status_code
        for _ in range(120)
    ]

    assert 429 not in statuses
