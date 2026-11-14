"""Run a whole round of bots on the local stack and report what they did.

Needs the local stack running (Cosmos emulator, function app, Flask API), with Flask and the function app started
with the same ``EPOCH_SECONDS`` as this script's ``--epoch`` (a short epoch makes a round run fast), e.g. 30.

It WIPES the local game (``/api/resetstate``), so it refuses to run unless ``COSMOS_ENDPOINT`` in
``funcapp/local.settings.json`` is the local emulator. Secrets are read from ``api/.flaskenv`` and never printed.

    python scripts/simulate_bots.py --epoch 30 --minutes 10 --bots 12
"""
import argparse
import collections
import datetime
import json
import pathlib
import sys
import time
from urllib.parse import urlparse

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "funcapp" / "local.settings.json"
FLASKENV = ROOT / "api" / ".flaskenv"


def flaskenv():
    env = {}
    for line in FLASKENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def require_local():
    endpoint = json.loads(SETTINGS.read_text(encoding="utf-8"))["Values"]["COSMOS_ENDPOINT"]
    if urlparse(endpoint).hostname not in ("localhost", "127.0.0.1"):
        sys.exit("Refusing to run: COSMOS_ENDPOINT is not the local emulator.")


class Sim:
    def __init__(self, api, func, env):
        self.api, self.func, self.env = api, func, env
        self.session = requests.Session()
        self.headers = {}

    def login(self):
        r = self.session.post(f"{self.api}/api/adminlogin", json={"username": "admin", "password": self.env["ADMIN_PASSWORD"]})
        r.raise_for_status()
        self.headers = {"Authorization": "Bearer " + r.json()["accessToken"]}

    def post(self, path, body=None):
        r = self.session.post(f"{self.api}{path}", json=body or {}, headers=self.headers, timeout=600)
        return r

    def tick(self):
        r = self.session.get(f"{self.api}/api/refreshdata", headers={"Refresh-Secret": self.env["REFRESH_SECRET"]}, timeout=600)
        return r.text

    def fget(self, path):
        r = self.session.get(f"{self.func}{path}", headers={"x-functions-key": self.env.get("AZURE_FUNCTIONS_HOST_KEY", "")}, timeout=120)
        r.raise_for_status()
        return r.json()


def summarise(sim, started):
    kingdoms = sim.fget("/kingdoms")
    kingdoms = kingdoms.get("kingdoms", kingdoms)
    scores = sim.fget("/scores")
    stars = scores.get("stars", {})
    kinds = collections.Counter()
    outcomes = collections.Counter()
    for kd_id in kingdoms:
        try:
            kd = sim.fget(f"/kingdom/{kd_id}")
        except Exception:
            continue
        for entry in (kd.get("bot") or {}).get("log", []):
            kinds[entry.get("kind")] += 1
            outcomes[(entry.get("kind"), str(entry.get("outcome"))[:30])] += 1
    top = sorted(stars.items(), key=lambda kv: -kv[1])[:5]
    elapsed = int(time.time() - started)
    print(f"[{elapsed:4d}s] kingdoms={len(kingdoms)} top stars={top} decisions={dict(kinds)}")
    return outcomes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--func", default="http://localhost:7071/api")
    parser.add_argument("--epoch", type=float, default=30, help="EPOCH_SECONDS the servers were started with")
    parser.add_argument("--minutes", type=float, default=10)
    parser.add_argument("--bots", type=int, default=12, help="total, split evenly over the four archetypes")
    parser.add_argument("--galaxies", type=int, default=3)
    parser.add_argument("--no-reset", action="store_true", help="keep the current game and just tick")
    parser.add_argument("--tick-every", type=float, default=5)
    args = parser.parse_args()

    require_local()
    sim = Sim(args.api, args.func, flaskenv())
    sim.login()

    if not args.no_reset:
        print("reset:", sim.post("/api/resetstate").status_code)
        r = sim.post("/api/createstate", {"num_galaxies": args.galaxies, "max_galaxy_size": 12, "avg_size_new_galaxy": 6})
        print("createstate:", r.status_code)
        start = datetime.datetime.now(datetime.timezone.utc)
        r = sim.post("/api/updatestate", {
            "game_start": start.isoformat(),
            "game_end": (start + datetime.timedelta(minutes=args.minutes + 30)).isoformat(),
            "election_start": (start + datetime.timedelta(seconds=args.epoch * 20)).isoformat(),
            "next_history": (start + datetime.timedelta(seconds=args.epoch)).isoformat(),
        })
        print("updatestate:", r.status_code)
        each = max(1, args.bots // 4)
        r = sim.post("/api/admin/bots", {"explorer": each, "attacker": each, "intel": each, "thief": each})
        print("bots:", r.status_code, r.text[:200])

    started = time.time()
    last_report = 0
    while time.time() - started < args.minutes * 60:
        try:
            result = sim.tick()
            if "failed" in result:
                print("tick:", result[:300])
        except Exception as error:
            print("tick error:", repr(error))
        if time.time() - last_report > 30:
            last_report = time.time()
            try:
                outcomes = summarise(sim, started)
            except Exception as error:
                print("report error:", repr(error))
        time.sleep(args.tick_every)

    print("\nOutcomes (decision kind, outcome):")
    for key, count in sorted(outcomes.items(), key=lambda kv: -kv[1])[:30]:
        print(f"  {count:4d}  {key}")


if __name__ == "__main__":
    main()
