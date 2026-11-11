"""Email on accounts: verification, password reset and username recovery. Mail goes to the in-memory outbox."""
import re

import pytest

import untitledapp.mailer as mailer


@pytest.fixture
def outbox(app):
    app.extensions["mail_outbox"] = []
    return app.extensions["mail_outbox"]


def _token_in(message):
    return re.search(r"token=([\w\-\.]+)", message["text"]).group(1)


def _signup(client, username, email=None, password="pw"):
    body = {"username": username, "password": password}
    if email is not None:
        body["email"] = email
    return client.post("/api/signup", json=body)


def _verified_user(client, outbox, username, email):
    assert _signup(client, username, email).status_code == 201
    token = _token_in(outbox[-1])
    assert client.post("/api/account/email/verify", json={"token": token}).status_code == 200


def test_signup_with_an_email_sends_a_verification_link_and_following_it_verifies(client, outbox):
    assert _signup(client, "em_a", "a@example.com").status_code == 201

    assert len(outbox) == 1 and outbox[0]["to"] == "a@example.com"
    assert "http://frontend.test/verifyemail?token=" in outbox[0]["text"]
    login = client.post("/api/login", json={"username": "em_a", "password": "pw"}).get_json()
    headers = {"Authorization": f"Bearer {login['accessToken']}"}
    assert client.get("/api/account", headers=headers).get_json()["email_verified"] is False

    assert client.post("/api/account/email/verify", json={"token": _token_in(outbox[0])}).status_code == 200
    account = client.get("/api/account", headers=headers).get_json()
    assert account == {"username": "em_a", "email": "a@example.com", "email_verified": True}


def test_signup_without_an_email_still_works_and_sends_nothing(client, outbox):
    assert _signup(client, "em_none").status_code == 201
    assert outbox == []


def test_a_malformed_email_is_refused_at_signup(client, outbox):
    assert _signup(client, "em_bad", "not-an-email").status_code == 400
    assert outbox == []


def test_a_forged_or_wrong_purpose_token_does_not_verify(client, outbox):
    _signup(client, "em_b", "b@example.com")
    assert client.post("/api/account/email/verify", json={"token": "nonsense"}).status_code == 400
    # a reset token is not a verification token
    reset_token = mailer.make_token(mailer.RESET_PASSWORD, {"id": 1, "fp": "x"})
    assert client.post("/api/account/email/verify", json={"token": reset_token}).status_code == 400


def test_an_expired_verification_link_is_refused(client, outbox, monkeypatch):
    _signup(client, "em_c", "c@example.com")
    monkeypatch.setitem(mailer.MAX_AGE, mailer.VERIFY_EMAIL, -1)
    assert client.post("/api/account/email/verify", json={"token": _token_in(outbox[0])}).status_code == 400


def test_changing_the_address_voids_the_old_verification_link_and_needs_a_new_one(client, outbox):
    _signup(client, "em_d", "old@example.com")
    old_token = _token_in(outbox[0])
    login = client.post("/api/login", json={"username": "em_d", "password": "pw"}).get_json()
    headers = {"Authorization": f"Bearer {login['accessToken']}"}

    assert client.post("/api/account/email", json={"email": "new@example.com"}, headers=headers).status_code == 200

    assert outbox[-1]["to"] == "new@example.com"
    assert client.post("/api/account/email/verify", json={"token": old_token}).status_code == 400
    assert client.post("/api/account/email/verify", json={"token": _token_in(outbox[-1])}).status_code == 200


def test_forgot_password_gives_the_same_answer_for_unknown_and_unverified_addresses_and_sends_nothing(client, outbox):
    _signup(client, "em_e", "e@example.com")  # never verified
    outbox.clear()

    unknown = client.post("/api/account/forgot-password", json={"email": "nobody@example.com"})
    unverified = client.post("/api/account/forgot-password", json={"email": "e@example.com"})

    assert unknown.status_code == unverified.status_code == 200
    assert unknown.get_json() == unverified.get_json()
    assert outbox == []


def test_password_reset_works_once_and_the_new_password_logs_in(client, outbox):
    _verified_user(client, outbox, "em_f", "f@example.com")
    outbox.clear()

    assert client.post("/api/account/forgot-password", json={"email": "f@example.com"}).status_code == 200
    assert len(outbox) == 1 and "resetpassword?token=" in outbox[0]["text"]
    token = _token_in(outbox[0])

    assert client.post("/api/account/reset-password", json={"token": token, "password": "new-pw"}).status_code == 200
    assert client.post("/api/login", json={"username": "em_f", "password": "new-pw"}).status_code == 200
    assert client.post("/api/login", json={"username": "em_f", "password": "pw"}).status_code == 401
    # the same link can not be used again
    again = client.post("/api/account/reset-password", json={"token": token, "password": "other"})
    assert again.status_code == 400
    assert client.post("/api/login", json={"username": "em_f", "password": "new-pw"}).status_code == 200


def test_a_reset_link_expires(client, outbox, monkeypatch):
    _verified_user(client, outbox, "em_g", "g@example.com")
    outbox.clear()
    client.post("/api/account/forgot-password", json={"email": "g@example.com"})
    token = _token_in(outbox[0])
    monkeypatch.setitem(mailer.MAX_AGE, mailer.RESET_PASSWORD, -1)

    assert client.post("/api/account/reset-password", json={"token": token, "password": "x"}).status_code == 400


def test_forgot_username_lists_the_verified_accounts_on_that_address(client, outbox):
    _verified_user(client, outbox, "em_h1", "h@example.com")
    _verified_user(client, outbox, "em_h2", "h@example.com")
    outbox.clear()

    reply = client.post("/api/account/forgot-username", json={"email": "h@example.com"})

    assert reply.status_code == 200
    assert len(outbox) == 1
    assert "em_h1" in outbox[0]["text"] and "em_h2" in outbox[0]["text"]
    unknown = client.post("/api/account/forgot-username", json={"email": "who@example.com"})
    assert unknown.get_json() == reply.get_json() and len(outbox) == 1


def test_a_mail_failure_does_not_break_the_request(app, client, outbox, monkeypatch):
    _verified_user(client, outbox, "em_i", "i@example.com")
    monkeypatch.setitem(app.config, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(mailer.mail, "send", lambda message: (_ for _ in ()).throw(ConnectionError("smtp down")))

    reply = client.post("/api/account/forgot-password", json={"email": "i@example.com"})

    assert reply.status_code == 200


def test_the_existing_user_table_gets_the_email_columns_without_losing_rows(tmp_path):
    """Production has a SQLite file from before email existed; create_all() would never add the columns."""
    import flask
    import sqlalchemy
    import untitledapp

    old_app = flask.Flask("old_schema")
    old_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'old.db'}"
    untitledapp.db.init_app(old_app)
    with old_app.app_context():
        with untitledapp.db.engine.begin() as connection:
            connection.execute(sqlalchemy.text('CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT, password TEXT)'))
            connection.execute(sqlalchemy.text("INSERT INTO user (username, password) VALUES ('old', 'hash')"))

        untitledapp._add_missing_columns()
        untitledapp._add_missing_columns()  # running it again is harmless

        with untitledapp.db.engine.connect() as connection:
            row = connection.execute(sqlalchemy.text('SELECT username, email, email_verified FROM user')).one()
    assert tuple(row) == ("old", None, 0)
