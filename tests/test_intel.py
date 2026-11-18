"""
The galaxy's intel market (api/untitledapp/intel.py): listing, buying, free shares, bounties, exclusions, and the rules
that decide who earns which cut.

Galaxy "1" is kingdoms 1, 2 and 3 (``jwt1`` plays 1, ``jwt2`` plays 2); the target, 5, is in galaxy "2".
"""
import datetime

import pytest

import untitledapp.intel as uai
import untitledapp.shared as uas

from tests.test_concurrency import _create_item, _get, _run_together, _set_up_kingdom  # noqa: F401

NOW = datetime.datetime(2026, 11, 18, 12, 0, tzinfo=datetime.timezone.utc)
TARGET = "5"


def _at(hours, now=None):
    return ((now or NOW) + datetime.timedelta(hours=hours)).isoformat()


def _later(hours):
    return _at(hours, datetime.datetime.now(datetime.timezone.utc))


def _record(sharer, cut, hours=8, source="market"):
    return {"sharer": sharer, "cut": cut, "time": _at(hours), "source": source, "accepted_at": NOW.isoformat()}


def _market(**fields):
    return uai.normalize(fields)


# --- the rules, on plain documents ---------------------------------------------------------------------------------

def test_a_kingdom_takes_intel_it_does_not_have():
    assert uai.accept_problem(_market(), "2", TARGET, "military", 0.1, NOW, until=_at(8)) is None


def test_the_same_category_at_a_lower_cut_is_refused():
    market = _market(accepted={"2": {TARGET: {"military": _record("1", 0.10)}}})
    problem = uai.accept_problem(market, "2", TARGET, "military", 0.05, NOW, until=_at(12))
    assert "lower" in problem
    # Even free intel, and even when it would last longer.
    assert "lower" in uai.accept_problem(market, "2", TARGET, "military", 0, NOW, until=_at(20))


def test_the_same_category_at_the_same_or_a_higher_cut_is_taken_only_if_it_lasts_longer():
    market = _market(accepted={"2": {TARGET: {"military": _record("1", 0.10, hours=8)}}})
    assert uai.accept_problem(market, "2", TARGET, "military", 0.10, NOW, until=_at(12)) is None
    assert uai.accept_problem(market, "2", TARGET, "military", 0.12, NOW, until=_at(12)) is None
    assert "at least as long" in uai.accept_problem(market, "2", TARGET, "military", 0.12, NOW, until=_at(8))


def test_expired_intel_does_not_count():
    market = _market(accepted={"2": {TARGET: {"military": _record("1", 0.15, hours=-1)}}})
    assert uai.accept_problem(market, "2", TARGET, "military", 0.01, NOW, until=_at(4)) is None
    assert uai.spoils_cuts(market, "2", TARGET, NOW) == {}


def test_cuts_on_one_target_may_not_add_up_to_more_than_the_maximum():
    maximum = uas.GAME_CONFIG["BASE_MAX_TOTAL_SHARE_CUT"]
    market = _market(accepted={"2": {TARGET: {"military": _record("1", 0.15), "kingdom": _record("3", maximum - 0.15)}}})
    problem = uai.accept_problem(market, "2", TARGET, "shields", 0.01, NOW, until=_at(4))
    assert "the most is" in problem
    assert uai.accept_problem(market, "2", TARGET, "shields", 0, NOW, until=_at(4)) is None  # free is always room
    # Replacing a category counts its new cut instead of the old one.
    assert uai.accept_problem(market, "2", TARGET, "military", 0.15, NOW, until=_at(12)) is None
    # A bounty (no ``until``) is checked for the cuts only.
    assert "the most is" in uai.accept_problem(market, "2", TARGET, "shields", 0.01, NOW)


def test_spoils_cuts_add_up_per_sharer_and_skip_free_intel():
    market = _market(accepted={"2": {TARGET: {
        "military": _record("1", 0.10), "shields": _record("1", 0.05), "kingdom": _record("3", 0.15),
        "drones": _record("4", 0, source="free"),
    }}})
    assert uai.spoils_cuts(market, "2", TARGET, NOW) == pytest.approx({"1": 0.15, "3": 0.15})
    assert uai.spoils_cuts(market, "2", "6", NOW) == {}
    assert uai.spoils_cuts(market, "3", TARGET, NOW) == {}


def test_split_spoils_gives_each_sharer_its_cut_and_the_attacker_the_rest():
    total = {"stars": 101, "money": 1000, "funding": {"settle": 50, "military": 0}}
    attacker, sharers = uai.split_spoils(total, {"1": 0.10, "3": 0.15})
    assert sharers["1"] == {"stars": 10, "money": 100, "funding": {"settle": 5, "military": 0}}
    assert sharers["3"] == {"stars": 15, "money": 150, "funding": {"settle": 7, "military": 0}}
    assert attacker == {"stars": 75, "money": 750, "funding": {"settle": 37, "military": 0}}
    assert uai.split_spoils(total, {}) == (total, {})


def test_prune_drops_what_has_ended():
    market = _market(
        listings={"a": {"time": _at(-1)}, "b": {"time": _at(1)}},
        bounties={"c": {"time": _at(-1)}},
        accepted={"2": {TARGET: {"military": _record("1", 0.1, hours=-1)}}, "3": {TARGET: {"kingdom": _record("1", 0)}}},
        exclusions={"1": [], "2": ["3"]},
        history=[{"n": i} for i in range(uai.HISTORY_LENGTH + 5)],
    )
    uai.prune(market, NOW)
    assert list(market["listings"]) == ["b"]
    assert market["bounties"] == {}
    assert list(market["accepted"]) == ["3"]
    assert market["exclusions"] == {"2": ["3"]}
    assert len(market["history"]) == uai.HISTORY_LENGTH and market["history"][0] == {"n": 0}


def test_free_intel_never_replaces_paid_intel_but_replaces_older_free_intel():
    market = _market(accepted={
        "2": {TARGET: {"military": _record("3", 0.10, hours=4)}},
        "3": {TARGET: {"military": _record("4", 0, hours=2, source="free")}},
    }, bounties={
        "2.5.military": {"id": "2.5.military", "requester": "2", "target": TARGET, "category": "military", "cut": 0.1,
                         "time": _at(5)},
        "4.5.military": {"id": "4.5.military", "requester": "4", "target": TARGET, "category": "military", "cut": 0.1,
                         "time": _at(5)},
    })
    receivers, met = uai.share_free(market, "1", TARGET, "military", _at(8), ["2", "3"], NOW)
    assert receivers == ["2", "3"]
    assert market["accepted"]["2"][TARGET]["military"]["sharer"] == "3"  # paid intel stays
    assert market["accepted"]["3"][TARGET]["military"]["sharer"] == "1"  # older free intel is replaced
    assert [bounty["id"] for bounty in met] == ["2.5.military"]  # 4 did not receive it
    assert list(market["bounties"]) == ["4.5.military"]
    assert market["history"][0]["kind"] == "free" and market["history"][0]["to"] is None


def test_the_view_hides_excluded_listings_and_says_why_each_item_can_not_be_taken():
    market = {
        "listings": {
            "1.5.military": {"id": "1.5.military", "seller": "1", "target": TARGET, "category": "military", "cut": 0.1,
                             "time": _at(8)},
            "3.5.kingdom": {"id": "3.5.kingdom", "seller": "3", "target": TARGET, "category": "kingdom", "cut": 0.1,
                            "time": _at(8)},
        },
        "bounties": {
            "3.5.shields": {"id": "3.5.shields", "requester": "3", "target": TARGET, "category": "shields", "cut": 0.1,
                            "time": _at(8)},
            "3.5.drones": {"id": "3.5.drones", "requester": "3", "target": TARGET, "category": "drones", "cut": 0.1,
                           "time": _at(8)},
        },
        "accepted": {"2": {TARGET: {"drones": _record("1", 0)}}, "3": {"6": {"military": _record("1", 0.1)}}},
        "exclusions": {"3": ["2"]},
    }
    revealed = {"revealed": {TARGET: {"shields": _at(4), "drones": _at(4), "military": _at(-1)}, "1": {"kingdom": _at(4)}}}
    seen = uai.view(market, "2", revealed, NOW, members=["1", "2", "3"])
    assert [listing["id"] for listing in seen["listings"]] == ["1.5.military"]  # 3 excludes 2
    assert seen["listings"][0]["problem"] is None
    problems = {bounty["id"]: bounty["problem"] for bounty in seen["bounties"]}
    assert problems == {"3.5.shields": None, "3.5.drones": "You can not pass on intel that was shared with you"}
    assert seen["accepted"] == [{"target": TARGET, "category": "drones", **_record("1", 0)}]
    assert [(item["target"], item["category"], item["received"]) for item in seen["my_intel"]] == [
        (TARGET, "drones", True), (TARGET, "shields", False),  # expired military and galaxymate 1 left out
    ]
    assert seen["exclusions"] == []
    assert "accepted" not in str(seen["exclusions"]) and "3" not in seen["cuts"]
    # The seller's own view of its listing, and a bounty for intel it does not have.
    mine = uai.view(market, "1", {"revealed": {}}, NOW, members=["1", "2", "3"])
    assert {listing["id"]: listing["problem"] for listing in mine["listings"]}["1.5.military"] == "This is your listing"
    assert all("do not have" in bounty["problem"] for bounty in mine["bounties"])


# --- through the routes --------------------------------------------------------------------------------------------

def _set_up(revealed_1=None, revealed_2=None):
    for kd in ("1", "2", "3", TARGET):
        _set_up_kingdom(money=0, kd_id=kd)
    _create_item("galaxies", {"galaxies": {"1": ["1", "2", "3"], "2": [TARGET]}})
    _create_item("kingdoms", {"kingdoms": {"1": "One", "2": "Two", "3": "Three", TARGET: "Target"}})
    for kd, revealed in (("1", revealed_1), ("2", revealed_2)):
        if revealed is not None:
            _create_item(f"revealed_{kd}", {**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": revealed})


def _post(client, jwt, route, body):
    return client.post(f"/api/intel/{route}", json=body, headers={"Authorization": f"Bearer {jwt}"})


def _intel(client, jwt):
    response = client.get("/api/intel", headers={"Authorization": f"Bearer {jwt}"})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _stored():
    return _get("/galaxy/1/intel")


def test_list_and_buy(app, client, jwt1, jwt2):
    until = _later(8)
    _set_up(revealed_1={TARGET: {"military": until}})

    listed = _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    assert listed.status_code == 200, listed.get_json()
    (listing,) = _intel(client, jwt2)["listings"]
    assert (listing["seller"], listing["cut"], listing["time"], listing["problem"]) == ("1", 0.1, until, None)

    bought = _post(client, jwt2, "buy", {"listing": listing["id"]})
    assert bought.status_code == 200, bought.get_json()
    stored = _stored()
    assert stored["accepted"]["2"][TARGET]["military"]["sharer"] == "1"
    assert stored["accepted"]["2"][TARGET]["military"]["cut"] == 0.1
    assert listing["id"] in stored["listings"]  # still listed for anyone else
    assert stored["history"][0]["kind"] == "purchase" and stored["history"][0]["to"] == "2"
    # The buyer has the reveal, and its refresh expires it on time (issue #60).
    assert _get("/kingdom/2/revealed")["revealed"][TARGET]["military"] == until
    assert _get("/kingdom/2")["next_resolve"]["revealed"] == until
    # The seller hears of it.
    assert _get("/kingdom/1/news")["news"][0]["kind"] == "intel"
    assert _get("/kingdom/1/notifs")["shared"] == 1
    # Buying it again does nothing more.
    again = _post(client, jwt2, "buy", {"listing": listing["id"]})
    assert again.status_code == 400 and "at least as long" in again.get_json()["message"]


def test_several_galaxymates_can_buy_one_listing(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}})
    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    listing = uai.listing_id("1", TARGET, "military")
    assert _post(client, jwt2, "buy", {"listing": listing}).status_code == 200
    with app.app_context():
        assert uai._buy("3", listing)[1] == 200
    assert set(_stored()["accepted"]) == {"2", "3"}


def test_buying_at_the_same_moment_takes_it_once(app, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}})
    with app.app_context():
        uai._share("1", TARGET, "military", 10)
    listing = uai.listing_id("1", TARGET, "military")
    responses = _run_together(app, 6, lambda client, _: _post(client, jwt2, "buy", {"listing": listing}))
    assert sorted(response.status_code for response in responses) == [200] + [400] * 5
    assert [entry["kind"] for entry in _stored()["history"]] == ["purchase"]


def test_what_can_not_be_listed(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}, "2": {"kingdom": _later(8)}})
    cases = [
        ({"target": TARGET, "category": "shields", "cut": 5}, "do not have"),
        ({"target": TARGET, "category": "military", "cut": 50}, "at most"),
        ({"target": TARGET, "category": "military", "cut": -1}, "positive"),
        ({"target": TARGET, "category": "secrets", "cut": 5}, "Choose a kind of intel"),
        ({"target": "2", "category": "kingdom", "cut": 5}, "galaxymate"),
    ]
    for body, message in cases:
        response = _post(client, jwt1, "share", body)
        assert response.status_code == 400 and message in response.get_json()["message"], (body, response.get_json())
    assert _stored().get("listings") in (None, {})


def test_intel_you_received_can_not_be_passed_on(app, client, jwt1, jwt2):
    until = _later(8)
    _set_up(revealed_1={TARGET: {"military": until}})
    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    _post(client, jwt2, "buy", {"listing": uai.listing_id("1", TARGET, "military")})
    resold = _post(client, jwt2, "share", {"target": TARGET, "category": "military", "cut": 5})
    assert resold.status_code == 400 and "pass on" in resold.get_json()["message"]
    assert next(item for item in _intel(client, jwt2)["my_intel"] if item["category"] == "military")["received"] is True


def test_a_galaxymate_can_not_undercut_intel_already_taken(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}})
    _create_item("revealed_3", {**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {TARGET: {"military": _later(10)}}})
    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    assert _post(client, jwt2, "buy", {"listing": uai.listing_id("1", TARGET, "military")}).status_code == 200
    with app.app_context():
        assert uai._share("3", TARGET, "military", 5)[1] == 200  # listing it is fine
        cheaper = uai._buy("2", uai.listing_id("3", TARGET, "military"))
        assert cheaper[1] == 400 and "lower" in cheaper[0]["message"]
        assert uai._share("3", TARGET, "military", 0)[1] == 200  # nor can free intel push 1 out
    assert _stored()["accepted"]["2"][TARGET]["military"]["sharer"] == "1"
    listing = next(item for item in _intel(client, jwt2)["listings"] if item["seller"] == "3")
    assert "lower" in listing["problem"]


def test_exclusions(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8), "kingdom": _later(8)}})
    assert _post(client, jwt1, "exclusions", {"excluded": ["2"]}).status_code == 200
    assert _intel(client, jwt1)["exclusions"] == ["2"]
    assert _intel(client, jwt2)["exclusions"] == []  # 2 is not told

    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    assert _intel(client, jwt2)["listings"] == []
    refused = _post(client, jwt2, "buy", {"listing": uai.listing_id("1", TARGET, "military")})
    assert refused.status_code == 400 and "no longer on offer" in refused.get_json()["message"]

    shared = _post(client, jwt1, "share", {"target": TARGET, "category": "kingdom", "cut": 0})
    assert shared.status_code == 200, shared.get_json()
    accepted = _stored()["accepted"]
    assert "3" in accepted and "2" not in accepted
    assert TARGET not in _get("/kingdom/2/revealed")["revealed"]

    for body in ({"excluded": [TARGET]}, {"excluded": ["1"]}, {"excluded": "2"}):
        assert _post(client, jwt1, "exclusions", body).status_code == 400
    assert _post(client, jwt1, "exclusions", {"excluded": []}).status_code == 200
    assert _intel(client, jwt2)["listings"] != []


def test_free_intel_reaches_every_galaxymate_at_once(app, client, jwt1, jwt2):
    until = _later(8)
    _set_up(revealed_1={TARGET: {"military": until}})
    assert _post(client, jwt2, "bounty", {"target": TARGET, "category": "military", "cut": 10, "epochs": 4}).status_code == 200

    shared = _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 0})
    assert shared.status_code == 200 and "meeting 1 bounty" in shared.get_json()["message"], shared.get_json()
    stored = _stored()
    for kd in ("2", "3"):
        assert stored["accepted"][kd][TARGET]["military"] == {**stored["accepted"][kd][TARGET]["military"],
                                                              "sharer": "1", "cut": 0, "source": "free"}
        assert _get(f"/kingdom/{kd}/revealed")["revealed"][TARGET]["military"] == until
        assert _get(f"/kingdom/{kd}")["next_resolve"]["revealed"] == until
        assert _get(f"/kingdom/{kd}/notifs")["shared"] == 1
    assert stored["listings"] == {} and stored["bounties"] == {}
    assert stored["history"][0]["kind"] == "free"


def test_a_free_share_never_shortens_a_reveal(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(2)}}, revealed_2={TARGET: {"military": _later(9)}})
    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 0})
    assert _get("/kingdom/2/revealed")["revealed"][TARGET]["military"] > _later(8)


def test_bounty_posted_fulfilled_and_kept_in_history(app, client, jwt1, jwt2):
    until = _later(8)
    _set_up(revealed_1={TARGET: {"military": until}})
    posted = _post(client, jwt2, "bounty", {"target": TARGET, "category": "military", "cut": 10, "epochs": 4})
    assert posted.status_code == 200, posted.get_json()
    (bounty,) = _intel(client, jwt1)["bounties"]
    assert (bounty["requester"], bounty["cut"], bounty["problem"]) == ("2", 0.1, None)
    assert _intel(client, jwt2)["bounties"][0]["problem"] == "This is your bounty"

    fulfilled = _post(client, jwt1, "fulfil", {"bounty": bounty["id"]})
    assert fulfilled.status_code == 200, fulfilled.get_json()
    stored = _stored()
    assert stored["bounties"] == {}
    assert stored["accepted"]["2"][TARGET]["military"] == {**stored["accepted"]["2"][TARGET]["military"],
                                                           "sharer": "1", "cut": 0.1, "time": until, "source": "bounty"}
    assert stored["history"][0] == {**stored["history"][0], "kind": "bounty", "from": "1", "to": "2"}
    assert _get("/kingdom/2/revealed")["revealed"][TARGET]["military"] == until
    assert _get("/kingdom/2")["next_resolve"]["revealed"] == until
    assert _get("/kingdom/2/news")["news"][0]["kind"] == "intel"


def test_a_bounty_is_fulfilled_once(app, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}})
    _create_item("revealed_3", {**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {TARGET: {"military": _later(8)}}})
    with app.app_context():
        uai._post_bounty("2", TARGET, "military", 10, 4)
    bounty = uai.bounty_id("2", TARGET, "military")

    def fulfil(client, i):
        if i % 2:
            return _post(client, jwt1, "fulfil", {"bounty": bounty}).status_code
        with app.app_context():
            return uai._fulfil("3", bounty)[1]

    codes = _run_together(app, 6, fulfil)
    assert sorted(codes) == [200] + [400] * 5
    assert [entry["kind"] for entry in _stored()["history"]] == ["bounty"]


def test_what_can_not_be_asked_for_or_fulfilled(app, client, jwt1, jwt2):
    maximum = uas.GAME_CONFIG["BASE_INTEL_BOUNTY_MAX_EPOCHS"]
    _set_up(revealed_2={TARGET: {"shields": _later(8)}})
    cases = [
        ({"target": TARGET, "category": "military", "cut": 10, "epochs": maximum + 1}, "epochs"),
        ({"target": TARGET, "category": "military", "cut": 10, "epochs": 0}, "epochs"),
        ({"target": "3", "category": "military", "cut": 10, "epochs": 4}, "galaxymate"),
        ({"target": "99", "category": "military", "cut": 10, "epochs": 4}, "no such kingdom"),
        ({"target": TARGET, "category": "military", "cut": 20, "epochs": 4}, "at most"),
    ]
    for body, message in cases:
        response = _post(client, jwt1, "bounty", body)
        assert response.status_code == 400 and message in response.get_json()["message"], (body, response.get_json())

    _post(client, jwt1, "bounty", {"target": TARGET, "category": "military", "cut": 10, "epochs": 4})
    bounty = uai.bounty_id("1", TARGET, "military")
    no_intel = _post(client, jwt2, "fulfil", {"bounty": bounty})
    assert no_intel.status_code == 400 and "do not have" in no_intel.get_json()["message"]
    own = _post(client, jwt1, "fulfil", {"bounty": bounty})
    assert own.status_code == 400 and "your bounty" in own.get_json()["message"]


def test_a_bounty_can_not_ask_for_less_than_intel_already_taken(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}})
    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    _post(client, jwt2, "buy", {"listing": uai.listing_id("1", TARGET, "military")})
    cheaper = _post(client, jwt2, "bounty", {"target": TARGET, "category": "military", "cut": 5, "epochs": 4})
    assert cheaper.status_code == 400 and "lower" in cheaper.get_json()["message"]


def test_withdrawing_bounties_and_listings(app, client, jwt1, jwt2):
    _set_up(revealed_1={TARGET: {"military": _later(8)}})
    _post(client, jwt1, "share", {"target": TARGET, "category": "military", "cut": 10})
    _post(client, jwt2, "bounty", {"target": TARGET, "category": "kingdom", "cut": 10, "epochs": 4})
    listing, bounty = uai.listing_id("1", TARGET, "military"), uai.bounty_id("2", TARGET, "kingdom")

    assert _post(client, jwt2, "delist", {"listing": listing}).status_code == 400  # not theirs
    assert _post(client, jwt1, "cancelbounty", {"bounty": bounty}).status_code == 400
    assert _post(client, jwt1, "delist", {"listing": listing}).status_code == 200
    assert _post(client, jwt2, "cancelbounty", {"bounty": bounty}).status_code == 200
    stored = _stored()
    assert stored["listings"] == {} and stored["bounties"] == {}


def test_spying_with_share_lists_or_shares_what_it_reveals(app):
    until = _later(8)
    _set_up(revealed_1={TARGET: {"military": until, "kingdom": until}})
    with app.app_context():
        assert uai._share("1", TARGET, "military", 10)[1] == 200
        assert uai._share("1", TARGET, "kingdom", 0)[1] == 200
    stored = _stored()
    assert list(stored["listings"]) == [uai.listing_id("1", TARGET, "military")]
    assert stored["accepted"]["2"][TARGET]["kingdom"]["source"] == "free"


def test_listings_made_at_the_same_moment_are_all_kept(app):
    _set_up(revealed_1={TARGET: {"military": _later(8)}}, revealed_2={TARGET: {"military": _later(8)}})
    _create_item("revealed_3", {**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": {TARGET: {"military": _later(8)}}})
    sellers = ["1", "2", "3"]

    def share(client, i):
        with app.app_context():
            return uai._share(sellers[i], TARGET, "military", 5)[1]

    assert _run_together(app, 3, share) == [200, 200, 200]
    assert set(_stored()["listings"]) == {uai.listing_id(kd, TARGET, "military") for kd in sellers}
