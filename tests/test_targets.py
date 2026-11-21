"""
The auto-spending targets (structures, units, projects): a box left empty keeps its target, and one set to 0 takes the
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
