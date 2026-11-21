"""
The auto-spending targets (structures, units, projects), spending shares and shields: a box left empty keeps its target, and one set to 0 takes the
target down to 0. Zero used to be skipped, so a target could never be lowered to nothing.
"""
import json

import untitledapp.shared as uas
from tests.test_concurrency import _get, _set_up_kingdom


def _post(client, jwt, path, body):
    return client.post(path, headers={"Authorization": f"Bearer {jwt}"}, data=json.dumps(body))


def test_a_structures_target_can_be_lowered_to_zero_and_an_empty_box_keeps_its_target(app, client, jwt1):
    _set_up_kingdom(0, structures_target={**uas.INITIAL_KINGDOM_STATE["kingdom"]["structures_target"], "homes": 0.4, "mines": 0.3})
    response = _post(client, jwt1, "/api/structures/target", {"homes": 0, "mines": ""})
    assert response.status_code == 200, response.get_json()
    targets = _get("/kingdom/1")["structures_target"]
    assert targets["homes"] == 0
    assert targets["mines"] == 0.3


def test_a_units_target_can_be_lowered_to_zero_and_an_empty_box_keeps_its_target(app, client, jwt1):
    _set_up_kingdom(0, units_target={**{key: 0 for key in uas.TRAINABLE_UNITS}, "attack": 0.5, "defense": 0.25})
    response = _post(client, jwt1, "/api/mobis/target", {"targets": {"attack": 0, "defense": ""}})
    assert response.status_code == 200, response.get_json()
    targets = _get("/kingdom/1")["units_target"]
    assert targets["attack"] == 0
    assert targets["defense"] == 0.25


def test_a_spending_share_can_be_lowered_to_zero_and_unknown_keys_are_ignored(app, client, jwt1):
    _set_up_kingdom(0, auto_spending={"settle": 0.25, "structures": 0.25, "military": 0.25, "engineers": 0.25})
    response = _post(client, jwt1, "/api/spending", {"settle": 0, "structures": "", "military": 50, "engineers": 25, "money": 99})
    assert response.status_code == 200, response.get_json()
    spending = _get("/kingdom/1")["auto_spending"]
    assert spending == {"settle": 0, "structures": 0.25, "military": 0.5, "engineers": 0.25}


def test_shields_can_be_lowered_to_zero(app, client, jwt1):
    _set_up_kingdom(0, shields={"military": 0.1, "spy": 0.1, "spy_radar": 0, "missiles": 0}, fuel=1000)
    response = _post(client, jwt1, "/api/shields", {"military": 0, "spy": 5, "spy_radar": 0, "missiles": 0})
    assert response.status_code == 200, response.get_json()
    shields = _get("/kingdom/1")["shields"]
    assert shields["military"] == 0
    assert shields["spy"] == 0.05


def test_automatic_attack_and_rob_shares_can_be_lowered_to_zero(app, client, jwt1):
    _set_up_kingdom(0, auto_attack_settings={"pure": 0.5, "flex": 0.25}, auto_rob_settings={"drones": 0.5, "keep": 2, "shielded": False})
    assert _post(client, jwt1, "/api/attackprimitives/auto", {"pure": 0, "flex": ""}).status_code == 200
    assert _get("/kingdom/1")["auto_attack_settings"] == {"pure": 0, "flex": 0.25}
    assert _post(client, jwt1, "/api/robprimitives/auto", {"drones": 10, "keep": 0}).status_code == 200
    rob = _get("/kingdom/1")["auto_rob_settings"]
    assert rob["drones"] == 0.1 and rob["keep"] == 0
