"""The refresh logs how long each tick took, so production's log stream shows when a tick nears a minute."""
import logging

from tests.test_admin_rounds import _admin, new_round_body


def test_a_tick_logs_its_duration(app, client, monkeypatch, caplog):
    assert client.post("/api/admin/newround", json=new_round_body(), headers=_admin(client)).status_code == 200
    monkeypatch.setenv("REFRESH_SECRET", "s")
    caplog.set_level(logging.INFO, logger=app.logger.name)

    response = client.get("/api/refreshdata", headers={"Refresh-Secret": "s"})

    assert response.get_data(as_text=True) == "Refreshed"
    lines = [record.getMessage() for record in caplog.records if record.getMessage().startswith("Tick: ")]
    assert len(lines) == 1 and lines[0].startswith("Tick: 0 kingdoms in ") and lines[0].endswith(", 0 failed")
