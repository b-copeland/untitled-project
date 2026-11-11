"""Sign-up, login, token refresh and disabling users."""


def _login(client, username, password):
    return client.post("/api/login", json={"username": username, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_a_new_account_can_log_in_and_the_password_is_not_stored_as_given(app, client):
    response = client.post("/api/signup", json={"username": "acct_a", "password": "secret"})

    assert response.status_code == 201 and response.get_json()["status"] == "success"
    assert _login(client, "acct_a", "secret").status_code == 200
    with app.app_context():
        import untitledapp

        stored = app.extensions["sqlalchemy"].session.query(untitledapp.User).filter_by(username="acct_a").one()
        assert stored.password != "secret" and stored.roles == "verified" and stored.is_active


def test_signing_up_twice_with_the_same_name_is_refused(client):
    assert client.post("/api/signup", json={"username": "acct_b", "password": "x"}).status_code == 201
    again = client.post("/api/signup", json={"username": "acct_b", "password": "y"})

    assert again.status_code == 400 and again.get_json()["message"] == "Account already exists"
    assert _login(client, "acct_b", "x").status_code == 200  # the original password still works


def test_empty_usernames_and_passwords_are_refused(client):
    assert client.post("/api/signup", json={"username": "", "password": "x"}).status_code == 400
    assert client.post("/api/signup", json={"username": "acct_c", "password": ""}).status_code == 400


def test_a_wrong_password_or_unknown_user_is_unauthorised(client):
    assert _login(client, "user1", "wrong").status_code == 401
    assert _login(client, "no_such_user", "x").status_code == 401


def test_a_token_that_has_not_expired_yet_can_not_be_refreshed(client):
    tokens = _login(client, "user1", "user1").get_json()
    assert client.post("/api/refresh", headers=_auth(tokens["accessToken"])).status_code == 425  # too early


def test_protected_routes_need_a_token(client):
    assert client.get("/api/account").status_code == 401
    assert client.get("/api/account", headers=_auth("garbage")).status_code in (401, 403)


def test_only_an_admin_can_disable_a_user_and_a_disabled_user_can_not_log_in(client):
    client.post("/api/signup", json={"username": "acct_d", "password": "x"})
    user_token = _login(client, "user1", "user1").get_json()["accessToken"]
    admin_token = _login(client, "admin", "admin").get_json()["accessToken"]

    refused = client.post("/api/disable_user", json={"username": "acct_d"}, headers=_auth(user_token))
    assert refused.status_code in (401, 403)
    assert _login(client, "acct_d", "x").status_code == 200

    done = client.post("/api/disable_user", json={"username": "acct_d"}, headers=_auth(admin_token))
    assert done.status_code == 200
    assert _login(client, "acct_d", "x").status_code == 403  # a disabled account is refused, not "wrong password"
