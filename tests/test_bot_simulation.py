"""A short round of bots played end to end (scripts/simulate_round.py), in its own process because it moves the clock."""
import json
import pathlib
import statistics
import subprocess
import sys

import untitledapp.shared as uas

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_a_day_of_bots_runs_clean_and_every_playstyle_grows(tmp_path):
    out = tmp_path / "round.json"
    done = subprocess.run(
        # Three of each playstyle, not the default mix: with one intel bot among five attackers, "the median intel bot"
        # is one kingdom, and whether it is farmed on the first day is chance.
        [sys.executable, str(ROOT / "scripts" / "simulate_round.py"), "--days", "1",
         "--mix", "explorer=3,attacker=3,intel=3,thief=3", "--galaxies", "3", "--seed", "5", "--json", str(out),
         "--replay", str(tmp_path / "replay.html")],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    results = json.loads(out.read_text(encoding="utf-8"))
    # The replay page carries the round: frames, every kingdom, and the bots' decisions.
    page = (tmp_path / "replay.html").read_text(encoding="utf-8")
    data = json.loads(page.split("const REPLAY = ", 1)[1].split(";\nconst TYPES", 1)[0].replace("<\\/", "</"))
    assert len(data["kingdoms"]) == 12 and len(data["frames"]) > 20 and sum(map(len, data["decisions"].values())) > 100

    # Nothing the game logs as an error: no bot failed to think, no kingdom was skipped by the refresh.
    assert results["errors"] == {} and results["failed_ticks"] == []
    rows = results["rows"]
    assert len(rows) == 12 and all(str(row["status"]).lower() != "dead" for row in rows)

    by_type = {}
    for row in rows:
        by_type.setdefault(row["type"], []).append(row)
    assert set(by_type) == {"explorer", "attacker", "intel", "thief"}
    for kind, kingdoms in by_type.items():
        # Each started at 300 stars. A day of settling, primitives and building is worth at least a third more.
        assert statistics.median(row["stars"] for row in kingdoms) > 400, kind
        # And nothing piles up unspent: the bots this replaced sat on millions.
        assert all(row["funding"] < 40 * row["stars"] * 12 for row in kingdoms), kind

    did = {}
    for counter in results["actions"].values():
        for name, count in counter.items():
            did[name] = did.get(name, 0) + count
    for action in ("attack primitives", "Rob Primitives", "did:intelspy", "did:vote_galaxy", "did:vote_leader",
                   "did:buy_settle", "did:reveal_galaxy"):
        assert did.get(action, 0) > 0, action
    # Every galaxy elected a leader and voted its policies in: once a tally has passed, each of the round's policies
    # has an active option.
    assert all(len(policies) == uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"] for policies in results["galaxy_policies"].values())
