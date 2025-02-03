import pytest
import json
from api.untitledapp import REQUESTS_SESSION

def test_set_shields(app, client, jwt1):
    
    resp = client.post("/api/shields")
    assert resp.status_code == 401

    kingdom_1_data = {
        "item": "kingdom_1",
        "state": {
            "fuel": 1000,
            "shields": {
                "military": 0,
                "spy": 0,
                "spy_radar": 0,
                "missiles": 0
            },
        }
    }
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(kingdom_1_data),
    )

    req = {
        "military": "10",
    }
    resp = client.post(
        "/api/shields",
        headers={"Authorization": f"Bearer {jwt1}"},
        data=json.dumps(req)
    )
    
    result = REQUESTS_SESSION.get(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/item',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps({"item": "kingdom_1"}),
    )
    assert resp.status_code == 200
    assert result.json()["shields"]["military"] == 0.1