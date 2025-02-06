import pytest
import json
from api.untitledapp import REQUESTS_SESSION

def test_max_kingdom(app, client, jwt1):
    
    resp = client.get("/api/kingdom/2")
    assert resp.status_code == 401

    galaxies_data = {
        "item": "galaxies",
        "state": {
            "galaxies": {
                "1:1": ["1"],
                "1:2": ["2"],
            }
        }
    }
    revealed_1_data = {
        "item": "revealed_1",
        "state": {
            "revealed": {
                "2": {
                    "stats": "date string"
                }
            },
            "revealed_galaxymates": [],
        }
    }
    kingdom_2_data = {
        "item": "kingdom_2",
        "state": {
            "name": "kd2",
            "stars": 100,
            "networth": 1000,
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
        data=json.dumps(galaxies_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(revealed_1_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(kingdom_2_data),
    )

    resp = client.get(
        "/api/kingdom/2",
        headers={"Authorization": f"Bearer {jwt1}"}
    )

    assert resp.status_code == 200
    resp_json = resp.json
    assert len(resp_json.keys()) == 3
    assert resp_json["stars"] == 100
    assert resp_json["networth"] == 1000
    assert resp_json["name"] == "kd2"

def test_scores(app, client, jwt1):
    
    resp = client.get("/api/scores")
    assert resp.status_code == 401

    scores_data = {
        "item": "scores",
        "state": {
            "points": {
                "1": 101,
                "2": 102,
                "3": 103,
                "4": 104,
            },
            "stars": {
                "1": 201,
                "2": 202,
                "3": 203,
                "4": 204,
            },
            "networth": {
                "1": 301,
                "2": 302,
                "3": 303,
                "4": 304,
            },
            "galaxy_networth": {
                "1:1": 604,
                "1:2": 606,
            }
        }
    }

    galaxies_data = {
        "item": "galaxies",
        "state": {
            "galaxies": {
                "1:1": ["1", "3"],
                "1:2": ["2", "4"],
            }
        }
    }
    revealed_1_data = {
        "item": "revealed_1",
        "state": {
            "revealed": {
                "2": {
                    "stats": "date string"
                }
            },
            "revealed_galaxymates": [],
        }
    }
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(scores_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(galaxies_data),
    )
    REQUESTS_SESSION.post(
        app.config["AZURE_FUNCTION_ENDPOINT"] + f'/createitem',
        headers={'x-functions-key': app.config["AZURE_FUNCTION_KEY"] },
        data=json.dumps(revealed_1_data),
    )

    resp = client.get(
        "/api/scores",
        headers={"Authorization": f"Bearer {jwt1}"}
    )

    assert resp.status_code == 200
    resp_json = resp.json

    for kd_id, networth in resp_json["networth"]:
        assert kd_id not in ["4"]
        if kd_id == "1":
            assert networth == 301
        if kd_id == "2":
            assert networth == 302
        if kd_id == "3":
            assert networth == 303

    for kd_id, stars in resp_json["stars"]:
        assert kd_id not in ["4"]
        if kd_id == "1":
            assert stars == 201
        if kd_id == "2":
            assert stars == 202
        if kd_id == "3":
            assert stars == 203

    for kd_id, points in resp_json["points"]:
        assert kd_id not in ["2", "4"]
        if kd_id == "1":
            assert points == 101
        if kd_id == "2":
            assert points == 102
