"""
The admin's accounts tools (issue #172, api/untitledapp/adminaccounts.py): the list, setting a password, bans, and the
login signals that show accounts which may be one person.
"""
import datetime

import pytest

import untitledapp.adminaccounts as uaac
from untitledapp import User
from tests.test_admin_rounds import _start
from tests.test_users import _add_user, _stored_user

NOW = datetime.datetime(2026, 11, 22, 12, tzinfo=datetime.timezone.utc)


def _login(client, username, password="pw", device=None, address=None):
    body = {"username": username, "password": password, **({"device": device} if device else {})}
    headers = {"X-Forwarded-For": f"9.9.9.9, {address}"} if address else {}
    return client.post("/api/login", json=body, headers=headers)


def _admin(client):
    return {"Authorization": f"Bearer {_login(client, 'admin', 'admin').get_json()['accessToken']}"}


def _accounts(client):
    response = client.get("/api/admin/accounts", headers=_admin(client))
    assert response.status_code == 200
    return {row["username"]: row for row in response.get_json()["accounts"]}


# --- the signals, as plain functions ---------------------------------------------------------------------------------

@pytest.mark.parametrize("forwarded, remote, expected", [
    ("1.2.3.4", None, "1.2.3.4"),
    ("1.2.3.4:5678", None, "1.2.3.4"),
    ("6.6.6.6, 1.2.3.4:5678", None, "1.2.3.4"),  # the last entry is the front end's; the first is the client's claim
    ("[2001:db8:1:2:3:4:5:6]:443", None, "2001:db8:1:2::/64"),
    ("2001:db8:1:2:aaaa::1", None, "2001:db8:1:2::/64"),  # one household's /64 is one address
    ("::ffff:1.2.3.4", None, "1.2.3.4"),
    ("", "127.0.0.1", "127.0.0.1"),
    ("not an address", None, ""),
    (None, None, ""),
])
def test_the_address_is_the_last_forwarded_one_without_its_port(forwarded, remote, expected):
    assert uaac.client_address(forwarded, remote) == expected


def test_a_signal_hash_is_stable_keyed_and_hides_the_value():
    one = uaac.signal_hash("key", "ip", "1.2.3.4")
    assert one == uaac.signal_hash("key", "ip", "1.2.3.4")
    assert one != uaac.signal_hash("other key", "ip", "1.2.3.4")
    assert one != uaac.signal_hash("key", "device", "1.2.3.4")
    assert "1.2.3.4" not in one


def _entry(kind, value, days_ago):
    when = (NOW - datetime.timedelta(days=days_ago)).isoformat()
    return {"kind": kind, "hash": value, "first": when, "last": when}


def test_a_new_signal_is_added_and_a_fresh_one_is_not_written_again():
    seen = uaac.with_signals([], {"ip": "a", "device": "d"}, NOW)
    assert [(e["kind"], e["hash"]) for e in seen] == [("ip", "a"), ("device", "d")]
    assert uaac.with_signals(seen, {"ip": "a", "device": "d"}, NOW + datetime.timedelta(hours=1)) is None


def test_a_signal_seen_again_after_a_day_has_its_last_time_moved():
    seen = [_entry("ip", "a", 2)]
    updated = uaac.with_signals(seen, {"ip": "a"}, NOW)
    assert updated[0]["last"] == NOW.isoformat() and updated[0]["first"] == seen[0]["first"]


def test_old_signals_are_dropped_and_only_the_newest_are_kept():
    old = _entry("ip", "old", uaac.SEEN_DAYS + 1)
    many = [_entry("device", f"d{i}", i) for i in range(uaac.SEEN_PER_KIND + 3)]
    kept = uaac.prune_seen([old, *many], NOW)
    assert "old" not in {e["hash"] for e in kept}
    assert [e["hash"] for e in kept] == [f"d{i}" for i in range(uaac.SEEN_PER_KIND)]
    # Expiry alone is a reason to write, even with nothing new.
    assert uaac.with_signals([old], {}, NOW) == []


class _U:
    def __init__(self, id, username, seen):
        self.id, self.username, self.seen = id, username, seen


def test_accounts_that_share_a_signal_are_listed_with_what_they_share():
    users = [
        _U(1, "ann", [_entry("ip", "home", 1), _entry("device", "laptop", 1)]),
        _U(2, "bob", [_entry("ip", "home", 3)]),
        _U(3, "cat", [_entry("device", "laptop", 2), _entry("ip", "cafe", 1)]),
        _U(4, "dan", [_entry("ip", "cafe", uaac.SEEN_DAYS + 5)]),  # too long ago to count
    ]
    shared = uaac.shared_signals(users, NOW)
    assert shared[1] == [
        {"id": 2, "username": "bob", "ip": True, "device": False},
        {"id": 3, "username": "cat", "ip": False, "device": True},
    ]
    assert shared[2] == [{"id": 1, "username": "ann", "ip": True, "device": False}]
    assert 4 not in shared


# --- the routes ------------------------------------------------------------------------------------------------------

def test_only_an_admin_sees_the_accounts_and_no_password_is_in_the_list(client):
    player = {"Authorization": f"Bearer {_login(client, 'user1', 'user1').get_json()['accessToken']}"}
    assert client.get("/api/admin/accounts", headers=player).status_code in (401, 403)
    accounts = _accounts(client)
    assert {"admin", "user1", "user2"} <= set(accounts)
    assert accounts["admin"]["admin"] and not accounts["user1"]["admin"]
    assert all("password" not in row and "seen" not in row for row in accounts.values())


def test_logins_from_one_device_or_address_show_the_accounts_together(app, client):
    for name in ("same_a", "same_b", "same_c", "bot_same"):
        _add_user(app, name)
    assert _login(client, "same_a", device="dev-1", address="5.5.5.5").status_code == 200
    assert _login(client, "same_b", device="dev-1", address="7.7.7.7:1234").status_code == 200
    assert _login(client, "same_c", device="dev-2", address="7.7.7.7").status_code == 200
    assert _login(client, "bot_same", device="dev-1", address="7.7.7.7").status_code == 200  # bots record nothing

    accounts = _accounts(client)
    assert accounts["same_a"]["shares"] == [{"id": accounts["same_b"]["id"], "username": "same_b", "ip": False, "device": True}]
    assert [(s["username"], s["ip"], s["device"]) for s in accounts["same_b"]["shares"]] == [
        ("same_a", False, True), ("same_c", True, False)]
    assert accounts["bot_same"]["bot"] and accounts["bot_same"]["shares"] == [] and accounts["bot_same"]["last_login"] == ""
    assert accounts["same_a"]["last_login"] and accounts["same_a"]["devices"] == 1

    stored = _stored_user(app, "same_a")
    assert all("5.5.5.5" not in e["hash"] and "dev-1" not in e["hash"] for e in stored.seen)


def test_a_second_login_the_same_day_writes_nothing(app, client, monkeypatch):
    _add_user(app, "twice")
    assert _login(client, "twice", device="dev-9").status_code == 200
    writes = []
    monkeypatch.setattr(User, "update", lambda self, decide: writes.append(self))
    assert _login(client, "twice", device="dev-9").status_code == 200
    assert writes == []


def test_a_login_that_can_not_record_still_logs_in(app, client, monkeypatch):
    _add_user(app, "fragile")

    def broken(self, decide):
        raise RuntimeError("the store is down")

    monkeypatch.setattr(User, "update", broken)
    assert _login(client, "fragile", device="dev-3").status_code == 200


def test_the_admin_sets_a_password_and_the_old_one_stops_working(app, client):
    user_id = _add_user(app, "forgot", password="old")
    assert client.post(f"/api/admin/accounts/{user_id}/password", json={"password": ""}, headers=_admin(client)).status_code == 400
    done = client.post(f"/api/admin/accounts/{user_id}/password", json={"password": "new"}, headers=_admin(client))
    assert done.status_code == 200 and done.get_json()["message"] == "Password changed for forgot"
    assert _login(client, "forgot", "old").status_code == 401
    assert _login(client, "forgot", "new").status_code == 200


def test_a_ban_keeps_its_date_and_reason_and_an_unban_clears_them(app, client):
    user_id = _add_user(app, "naughty")
    first = client.post(f"/api/admin/accounts/{user_id}/ban", json={"reason": "Multi-accounting"}, headers=_admin(client))
    assert first.status_code == 200
    row = first.get_json()["account"]
    assert row["banned"] and row["ban_reason"] == "Multi-accounting" and row["banned_at"]

    again = client.post(f"/api/admin/accounts/{user_id}/ban", json={"reason": "Also rude"}, headers=_admin(client))
    assert again.get_json()["account"]["banned_at"] == row["banned_at"]
    assert _accounts(client)["naughty"]["ban_reason"] == "Also rude"
    assert _login(client, "naughty").status_code == 403

    unbanned = client.post(f"/api/admin/accounts/{user_id}/unban", headers=_admin(client))
    assert unbanned.status_code == 200
    assert not unbanned.get_json()["account"]["banned"] and unbanned.get_json()["account"]["banned_at"] == ""
    assert _login(client, "naughty").status_code == 200


def test_an_admin_can_not_be_banned_and_an_unknown_account_says_so(app, client):
    admin_id = _stored_user(app, "admin").id
    refused = client.post(f"/api/admin/accounts/{admin_id}/ban", json={}, headers=_admin(client))
    assert refused.status_code == 400 and "admin" in refused.get_json()["message"]
    assert client.post("/api/admin/accounts/99999/ban", json={}, headers=_admin(client)).status_code == 404
    assert client.post("/api/admin/accounts/99999/password", json={"password": "x"}, headers=_admin(client)).status_code == 404
    long_reason = client.post(f"/api/admin/accounts/{admin_id}/ban", json={"reason": "x" * 201}, headers=_admin(client))
    assert long_reason.status_code == 400


def test_a_new_round_drops_signals_older_than_the_limit(app, client):
    old = _entry("ip", "old", uaac.SEEN_DAYS + 1)
    fresh = {**_entry("ip", "fresh", 1)}
    fresh["first"] = fresh["last"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    _add_user(app, "lapsed", seen=[old, fresh])
    _start(client)
    assert [e["hash"] for e in _stored_user(app, "lapsed").seen] == ["fresh"]
