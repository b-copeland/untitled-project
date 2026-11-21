"""Play a round of bots that ends now, give user1 one of its kingdoms, and copy it into an emulator container.

For looking at the game in a browser with a lived-in state: the bots have built, attacked and spied for a few days, so
there are revealed kingdoms, intel that ended at many different times (last-known intel), news and history. The round
is played in this process by ``simulate_round.py`` on a clock that starts ``--days`` ago, so every time in it is real
and it is still running when it lands.

    python scripts/demo_round.py                             # report what it would write
    python scripts/demo_round.py --apply                     # write it into the emulator container "demo"
    python scripts/demo_round.py --apply --container demo2 --days 4 --bots 40

Afterwards ``user1`` (password ``user1``) plays the kingdom with the most last-known intel, and ``admin`` (``admin``)
is the admin. The bots keep playing if the refresh runs. Bots seldom spy on anything but armies, so for the player
some other kinds of intel are added as if they had ended, spread over the three ages the pages colour
(``--no-extra-intel`` to leave them out).

To play it, point a function host at the container: copy ``funcapp/local.settings.json``, set
``COSMOS_CONTAINER_NAME`` to the container in the copy, and see docs/development.md for the ports. The destination
must be the local emulator; this refuses any other endpoint. Run it in the Flask environment, from the repository root.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import random
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "funcapp" / "local.settings.json"
SYSTEM_FIELDS = ("_rid", "_self", "_etag", "_attachments", "_ts")
LOCAL_HOSTS = ("localhost", "127.0.0.1")
PLAYER = "user1"
EXTRA_CATEGORIES = ("kingdom", "drones", "structures", "shields", "projects")


def play(days, bots, galaxies, seed):
    """The simulation, played until now. Its clock starts ``days`` ago."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import simulate_round

    class EndingNow(simulate_round.Clock):
        def __init__(self, start):
            super().__init__(start - datetime.timedelta(days=days))

    simulate_round.Clock = EndingNow
    real_stdout, sys.stdout = sys.stdout, open(os.devnull, "w")  # the game code prints as it goes
    started = time.time()
    try:
        sim = simulate_round.Simulation(simulate_round.parse_mix(None, bots), galaxies=galaxies, days=days, seed=seed)
        sim.run(progress=lambda s: print(f"  day {s.day():4.1f}  {time.time() - started:4.0f}s", file=real_stdout,
                                         flush=True))
    finally:
        sys.stdout = real_stdout
    return sim


def hand_over(docs, now, extra_intel, rng):
    """Make the bot with the most last-known intel the player's kingdom, and keep the round going. Returns its id."""
    import untitledapp.lastknown as uala

    def known(kd_id):
        return docs.get(f"lastknown_{kd_id}", {}).get("known", {})

    alive = [kd_id for kd_id in docs["kingdoms"]["kingdoms"]
             if str(docs.get(f"kingdom_{kd_id}", {}).get("status", "")).lower() != "dead"]
    player = max(alive, key=lambda kd_id: (sum(len(c) for c in known(kd_id).values()), len(known(kd_id))))
    kingdom = docs[f"kingdom_{player}"]
    kingdom.pop("bot", None)  # the refresh no longer plays it
    for doc in docs.values():
        if doc.get("username") == PLAYER:
            doc.update({"kd_id": player, "kd_created": True})

    if extra_intel:
        # Intel the bots seldom gather, as if it had ended at different times: each age band in turn (in epochs,
        # with the game's thresholds), so every colour shows.
        import untitledapp.shared as uas
        epoch = datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])
        fresh, aging = uas.GAME_CONFIG["LAST_KNOWN_FRESH_EPOCHS"], uas.GAME_CONFIG["LAST_KNOWN_AGING_EPOCHS"]
        bands = [(0.2, fresh - 0.5), (fresh + 0.5, aging - 0.5), (aging + 0.5, aging * 2)]
        revealed = docs[f"revealed_{player}"]["revealed"]
        targets = [t for t in known(player) if str(docs.get(f"kingdom_{t}", {}).get("status", "")).lower() != "dead"]
        store = docs.setdefault(f"lastknown_{player}", {"id": f"lastknown_{player}", "known": {}})
        turn = 0
        for target in rng.sample(targets, min(12, len(targets))):
            for category in EXTRA_CATEGORIES:
                if category in revealed.get(target, {}) or category in known(player).get(target, {}) or rng.random() < 0.3:
                    continue
                low, high = bands[turn % len(bands)]
                turn += 1
                ended = (now - epoch * rng.uniform(low, high)).isoformat()
                store["known"].setdefault(target, {}).update(uala.snapshot(docs[f"kingdom_{target}"], [category], ended))

    state = docs["state"]["state"]
    state["game_end"] = (now + datetime.timedelta(days=7)).isoformat()  # still running when it lands
    return player


def report(docs, player, now, epoch_seconds, fresh, aging):
    kingdom = docs[f"kingdom_{player}"]
    known = docs.get(f"lastknown_{player}", {}).get("known", {})
    revealed = docs[f"revealed_{player}"]["revealed"]
    ages = collections.Counter()
    by_category = collections.Counter()
    for categories in known.values():
        for category, entry in categories.items():
            by_category[category] += 1
            age = (now - datetime.datetime.fromisoformat(entry["ended"])).total_seconds() / epoch_seconds
            ages["yellow" if age < fresh else "orange" if age < aging else "red"] += 1
    galaxy = next(g for g, members in docs["galaxies"]["galaxies"].items() if player in members)
    print(f"\n{len(docs)} documents. {PLAYER} (password {PLAYER}) plays kingdom {player}, "
          f"{docs['kingdoms']['kingdoms'][player]!r}, in galaxy {galaxy}, {kingdom.get('stars')} stars.")
    print(f"Last-known intel on {len(known)} kingdoms: {dict(sorted(by_category.items()))}")
    print(f"  by age: {dict(ages)}")
    print(f"Intel active now on {len(revealed)} kingdoms: "
          f"{dict(collections.Counter(c for cats in revealed.values() for c in cats))}")
    galaxies_with = collections.Counter(
        next(g for g, members in docs["galaxies"]["galaxies"].items() if target in members) for target in known)
    print(f"  galaxies with the most last-known kingdoms: {galaxies_with.most_common(3)}")


def write(docs, container_name, replace):
    from azure.cosmos import CosmosClient, PartitionKey

    values = json.loads(SETTINGS.read_text(encoding="utf-8"))["Values"]
    endpoint = values["COSMOS_ENDPOINT"]
    if urlparse(endpoint).hostname not in LOCAL_HOSTS:
        sys.exit(f"Refusing to write: COSMOS_ENDPOINT is {urlparse(endpoint).hostname}, not the local emulator.")
    if container_name == values.get("COSMOS_CONTAINER_NAME", "test") and not replace:
        sys.exit(f"Refusing to write: {container_name!r} is the container the function app uses. Pick another, or "
                 "pass --replace to overwrite it.")
    # The emulator uses a self-signed certificate and never leaves this machine.
    client = CosmosClient(url=endpoint, credential=values["COSMOS_KEY"], connection_verify=False)
    database = client.create_database_if_not_exists(id=values.get("COSMOS_DATABASE_NAME", "dev"))
    container = database.create_container_if_not_exists(id=container_name, partition_key=PartitionKey(path="/id"))
    existing = [item["id"] for item in container.query_items("SELECT c.id FROM c", enable_cross_partition_query=True)]
    if existing and not replace:
        sys.exit(f"Refusing to write: container {container_name!r} has {len(existing)} documents. Pass --replace.")
    for item_id in existing:
        container.delete_item(item=item_id, partition_key=item_id)
    for doc in docs.values():
        container.upsert_item({k: v for k, v in doc.items() if k not in SYSTEM_FIELDS})
    print(f"Wrote {len(docs)} documents to {container_name!r}.")


def main():
    # The simulation plays the same round for a seed only with a fixed hash seed (see simulate_round.py).
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit(subprocess.run([sys.executable, *sys.argv], env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=float, default=3.0, help="game days the bots play before now")
    parser.add_argument("--bots", type=int, default=30)
    parser.add_argument("--galaxies", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--container", default="demo", help="the emulator container to write")
    parser.add_argument("--apply", action="store_true", help="write to the emulator (otherwise report only)")
    parser.add_argument("--replace", action="store_true", help="empty the container first if it has documents")
    parser.add_argument("--no-extra-intel", action="store_true", help="only the intel the bots gathered")
    args = parser.parse_args()

    sim = play(args.days, args.bots, args.galaxies, args.seed)
    now = sim.clock.now
    docs = json.loads(json.dumps(sim.container.docs))
    player = hand_over(docs, now, not args.no_extra_intel, random.Random(args.seed))
    config = sim.uas.GAME_CONFIG
    report(docs, player, now, config["BASE_EPOCH_SECONDS"], config["LAST_KNOWN_FRESH_EPOCHS"],
           config["LAST_KNOWN_AGING_EPOCHS"])
    if args.apply:
        write(docs, args.container, args.replace)
    else:
        print("Report only. Run again with --apply to write it.")


if __name__ == "__main__":
    main()
