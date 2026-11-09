"""Hammer the local function app with concurrent requests and report any lost updates.

Four checks, each run with many threads at once against one kingdom:

  appends        N threads append to the same list (siphons in)       expect N entries
  disjoint       N threads each set a different field of one document expect N fields
  naive spend    N threads read the balance, then write balance-1     expect balance - N  (a plain write loses some)
  If-Match spend the same, but writing with If-Match and re-reading   expect balance - N  (this is the safe pattern)
                 when the document changed

Everything is written to the Cosmos emulator, so reseed afterwards:
    python scripts/seed_cosmos_emulator.py --apply --replace

Usage:
    python scripts/check_concurrency.py [--threads 24] [--base http://localhost:7071/api] [--kingdom 22]
"""
import argparse
import json
import pathlib
import sys
import threading
import time
from urllib.parse import urlparse

import requests

SETTINGS = pathlib.Path(__file__).resolve().parent.parent / "funcapp" / "local.settings.json"
LOCAL_HOSTS = ("localhost", "127.0.0.1")


def run_threads(count, target):
    errors = []

    def wrapped(i):
        try:
            target(i)
        except Exception as e:  # report, do not hide
            errors.append(repr(e))

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(count)]
    barrier_start = time.time() + 0.5
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors, time.time() - barrier_start


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--threads", type=int, default=24)
    parser.add_argument("--base", default="http://localhost:7071/api")
    parser.add_argument("--kingdom", type=int, default=22)
    args = parser.parse_args()

    if urlparse(args.base).hostname not in LOCAL_HOSTS:
        sys.exit("Refusing to run against a non-local function app.")
    cosmos = json.loads(SETTINGS.read_text(encoding="utf-8"))["Values"]["COSMOS_ENDPOINT"]
    if urlparse(cosmos).hostname not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: the function app is configured for {urlparse(cosmos).hostname}, not the emulator.")

    n, kd = args.threads, args.kingdom
    run_id = str(int(time.time()))  # field names are unique per run, so earlier runs can not be mistaken for this one
    session = requests.Session()
    kingdom_url = f"{args.base}/kingdom/{kd}"
    results = {}

    # 1. appends
    siphons_url = f"{kingdom_url}/siphonsin"
    before = len(session.get(siphons_url).json()["siphons_in"])
    errors, _ = run_threads(
        n,
        lambda i: session.patch(siphons_url, data=json.dumps({"new_siphons": {"from": f"probe-{i}", "siphon": 1}})).raise_for_status(),
    )
    after = len(session.get(siphons_url).json()["siphons_in"])
    results["appends"] = (n, after - before, errors)

    # 2. disjoint fields
    errors, _ = run_threads(
        n, lambda i: session.patch(kingdom_url, data=json.dumps({f"probe_{run_id}_{i}": i})).raise_for_status()
    )
    doc = session.get(kingdom_url).json()
    results["disjoint fields"] = (n, sum(1 for i in range(n) if f"probe_{run_id}_{i}" in doc), errors)

    # 3. naive spend: read, then write an absolute value
    session.patch(kingdom_url, data=json.dumps({"money": 1000000})).raise_for_status()

    def naive(i):
        money = session.get(kingdom_url).json()["money"]
        session.patch(kingdom_url, data=json.dumps({"money": money - 1})).raise_for_status()

    errors, _ = run_threads(n, naive)
    results["naive spend"] = (n, 1000000 - session.get(kingdom_url).json()["money"], errors)

    # 4. spend with If-Match, re-reading when the document changed
    session.patch(kingdom_url, data=json.dumps({"money": 1000000})).raise_for_status()
    retries = []

    def safe(i):
        attempts = 0
        while True:
            attempts += 1
            doc = session.get(kingdom_url).json()
            response = session.patch(
                kingdom_url, data=json.dumps({"money": doc["money"] - 1}), headers={"If-Match": doc["_etag"]}
            )
            if response.status_code == 412:
                continue
            response.raise_for_status()
            retries.append(attempts)
            return

    errors, _ = run_threads(n, safe)
    results["If-Match spend"] = (n, 1000000 - session.get(kingdom_url).json()["money"], errors)

    print(f"{n} concurrent requests per check, kingdom {kd}\n")
    print(f"{'check':<18}{'expected':>10}{'applied':>10}{'told 409':>10}   result")
    ok = True
    informational = {"naive spend"}  # expected to lose updates; shown for contrast
    for name, (expected, applied, errs) in results.items():
        rejected = sum(1 for e in errs if "409" in e)  # the function app said: too much contention, retry
        other = len(errs) - rejected
        silent = expected - applied - rejected
        if name in informational:
            print(f"{name:<18}{expected:>10}{applied:>10}{'':>10}   (contrast) a plain write loses {expected - applied}")
            continue
        good = silent == 0 and other == 0
        ok = ok and good
        if not good:
            note = f"LOST {silent} silently" if silent else f"{other} unexpected errors: {errs[0]}"
        elif rejected:
            note = "ok: every request applied once or was told to retry"
        else:
            note = "ok"
        print(f"{name:<18}{expected:>10}{applied:>10}{rejected:>10}   {note}")
    if retries:
        print(f"\nIf-Match spend: {sum(retries) - len(retries)} retries across {len(retries)} requests (max {max(retries)} attempts)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
