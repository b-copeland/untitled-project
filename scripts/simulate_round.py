"""Play a whole round of bots in this process, on a simulated clock, and report how each playstyle did.

Nothing needs to be running: the function app's real handlers run on the in-memory backend the tests use
(``tests/fake_backend.py``), and game time is a clock this script moves forward, so a week of game time takes minutes
and the epoch keeps its real length (every duration in the game stays in proportion). It is the tool for tuning the bots
(docs/bots.md): change a rule, run it again, compare the tables.

    python scripts/simulate_round.py                         # 40 bots, 4 galaxies, 7 days
    python scripts/simulate_round.py --days 2 --bots 24 --seed 3
    python scripts/simulate_round.py --mix explorer=10,attacker=10 --json out.json
    python scripts/simulate_round.py --set WAR_MARGIN=1.5 --set thief.defense_margin=1.3 --set "*.rob_share=1.0"
    python scripts/simulate_round.py --days 3 --bots 40 --replay round.html     # a page to watch the round back

``--set`` tries a number without editing the code: a constant of ``botbrain.py`` or ``botstrategy.py`` by name, or a
``Personality`` field as ``<playstyle>.<field>`` (``*`` for every playstyle). Values are Python literals.

Run it in the Flask environment, from the repository root. The numbers are only comparable between runs with the same
arguments. ``scripts/simulate_bots.py`` is the other one: it drives the real local stack in real time.
"""
import argparse
import collections
import datetime
import json
import logging
import math
import re
import os
import pathlib
import random
import subprocess
import uuid
import statistics
import sys
import time
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent


INCOME_LAND = ("homes", "mines", "drone_factories")
STORAGE_LAND = ("hangars", "workshops", "fuel_plants", "missile_silos")
COMBAT = ("attack", "defense", "flex", "big_flex")
NUMBER = re.compile(r"(-?[\d,.]+) (stars|money)")


class Recorder:
    """
    What a replay page needs: a frame every few epochs (each kingdom's stars, networth and whether it is dead, the
    empires), every bot decision as it is made, and afterwards every attack, spy operation, missile and news item.
    ``write(path)`` puts it in one HTML page (``replay_template.html``) that opens from disk.
    """

    def __init__(self, sim, every_epochs=2.0):
        self.sim = sim
        self.every = every_epochs * sim.epoch
        self.next = 0.0
        self.frames = []
        self.decisions = collections.defaultdict(list)
        self.seen = {}
        self.empires = []

    def day(self, text):
        try:
            when = datetime.datetime.fromisoformat(str(text))
        except ValueError:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        return round((when - self.sim.start).total_seconds() / 86400, 4)

    def tick(self):
        elapsed = (self.sim.clock.now - self.sim.start).total_seconds()
        if elapsed < self.next:
            return
        self.next = elapsed + self.every
        kingdoms = self.sim.kingdoms()
        self.frames.append([round(self.sim.day(), 4), {
            kd_id: [kd.get("stars", 0), kd.get("networth", 0), int(str(kd.get("status")).lower() == "dead")]
            for kd_id, kd in kingdoms.items() if kd.get("race")}])
        for kd_id, kd in kingdoms.items():
            for entry in (kd.get("bot") or {}).get("log", []):
                if self.sim.uas.is_after(entry.get("time", ""), self.seen.get(kd_id, "")):
                    self.decisions[kd_id].append([self.day(entry.get("time")), entry.get("kind"), entry.get("why"),
                                                  entry.get("outcome")])
            log = (kd.get("bot") or {}).get("log", [])
            if log:
                times = [entry["time"] for entry in log if entry.get("time")] + ([self.seen[kd_id]] if self.seen.get(kd_id) else [])
                self.seen[kd_id] = max(times, key=self.sim.uas.utc, default="")
        empires = {eid: {"name": e.get("name"), "galaxies": e.get("galaxies", []), "war": e.get("war", [])}
                   for eid, e in self.sim.doc("empires").get("empires", {}).items()}
        if not self.empires or self.empires[-1][1] != empires:
            self.empires.append([round(self.sim.day(), 4), empires])

    def data(self):
        kingdoms = {kd_id: kd for kd_id, kd in self.sim.kingdoms().items() if kd.get("race")}
        galaxy_of = {kd: g for g, members in self.sim.doc("galaxies").get("galaxies", {}).items() for kd in members}
        events = []
        for kd_id in kingdoms:
            for entry in self.sim.doc(f"attack_history_{kd_id}").get("attack_history", []):
                to = entry.get("to") or ""
                ok = str(entry.get("news", "")).startswith("Success") if to else True  # primitives always give way
                events.append([self.day(entry.get("time")), "attack" if to else "primitives", kd_id, to, ok, entry.get("news", "")])
            for entry in self.sim.doc(f"spy_history_{kd_id}").get("spy_history", []):
                if not entry.get("to"):
                    continue  # robbing primitives: too many to show
                ok = not str(entry.get("news", "")).startswith("Failure")
                events.append([self.day(entry.get("time")), "spy", kd_id, entry["to"], ok,
                               f"{entry.get('operation')}: {entry.get('news', '')}"])
            for entry in self.sim.doc(f"missile_history_{kd_id}").get("missile_history", []):
                events.append([self.day(entry.get("time")), "missiles", kd_id, entry.get("to", ""), True, entry.get("news", "")])
        for item in self.sim.doc("universe_news").get("news", []):
            if isinstance(item, dict):
                events.append([self.day(item.get("time")), "universe", "", "", True, item.get("news", "")])
        events = sorted((e for e in events if e[0] is not None), key=lambda e: e[0])
        return {
            "days": self.sim.days,
            "kingdoms": {kd_id: {"name": kd["name"], "type": (kd.get("bot") or {}).get("type", "player"),
                                 "galaxy": galaxy_of.get(kd_id), "race": kd.get("race"),
                                 "style": (kd.get("bot") or {}).get("style") or {}}
                         for kd_id, kd in kingdoms.items()},
            "frames": self.frames,
            "decisions": self.decisions,
            "events": events,
            "empires": self.empires,
        }

    def write(self, path):
        template = (ROOT / "scripts" / "replay_template.html").read_text(encoding="utf-8")
        payload = json.dumps(self.data(), separators=(",", ":")).replace("</", "<\\/")
        pathlib.Path(path).write_text(template.replace("/*REPLAY_DATA*/null", payload), encoding="utf-8")


def kingdom_metrics(kd, epochs, uas, strategy):
    """What one kingdom looks like, for judging how well it plays: plain numbers, comparable between kingdoms."""
    stars = max(kd["stars"], 1)
    structures = kd["structures"]
    built = max(sum(structures.values()), 1)
    units = strategy.all_units(kd)
    home = {unit: kd["units"].get(unit, 0) for unit in uas.UNITS}
    combat = sum(units.get(unit, 0) for unit in COMBAT)
    housed = sum(count * uas.UNITS[unit]["hangar_capacity"] for unit, count in units.items())
    hangars = math.floor(structures.get("hangars", 0)) * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    defense = strategy.raw_defense(home) * strategy.defense_multiplier(kd)
    income = (kd.get("income") or {}).get("money", {})
    return {
        "defense_per_star": defense / stars,
        "primitives_defense_per_star": strategy.primitives_defense_per_star(epochs),
        "deterrence_per_star": strategy.deterrence_per_star(epochs),
        "income_land": sum(structures.get(key, 0) for key in INCOME_LAND) / built,
        "homes_land": structures.get("homes", 0) / built,
        "mines_land": structures.get("mines", 0) / built,
        "storage_land": sum(structures.get(key, 0) for key in STORAGE_LAND) / built,
        "empty_land": max(stars - built, 0) / stars,
        "hangar_fill": housed / max(hangars, 1),
        "offense_per_unit": strategy.raw_offense(units) / max(combat, 1),
        "defense_per_unit": strategy.raw_defense({u: units.get(u, 0) for u in COMBAT}) / max(combat, 1),
        "army_per_star": combat / stars,
        "recruits_share": units.get("recruits", 0) / max(combat + units.get("recruits", 0), 1),
        "engineers_per_star": units.get("engineers", 0) / stars,
        "drones_per_star": kd.get("drones", 0) / stars,
        "population_per_star": kd.get("population", 0) / stars,
        "income_per_star": income.get("net", 0) / stars,
        "idle_money_epochs": (kd.get("money", 0) + sum(kd.get("funding", {}).values())) / max(income.get("net", 1), 1),
        "fuel_ok": 1.0 if kd.get("fuel", 0) > 0 else 0.0,
    }


class Clock:
    """Game time. ``install`` makes every game module's ``datetime.datetime.now`` return it."""

    def __init__(self, start):
        self.now = start

    def advance(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)

    def install(self):
        clock = self

        class SimulatedDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return clock.now.astimezone(tz) if tz else clock.now.replace(tzinfo=None)

        proxy = types.ModuleType("datetime")
        proxy.__dict__.update({k: v for k, v in datetime.__dict__.items() if not k.startswith("__")})
        proxy.datetime = SimulatedDateTime
        for name, module in list(sys.modules.items()):
            path = str(getattr(module, "__file__", "") or "")
            game = name.startswith("untitledapp") or pathlib.Path(path).parent.name == "funcapp"
            if game and getattr(module, "datetime", None) is datetime:
                module.datetime = proxy


def apply_overrides(overrides):
    """Apply ``--set`` values to the bot modules. Returns what was set, for the report."""
    applied = {}
    if not overrides:
        return applied
    import ast
    import dataclasses

    import untitledapp.botbrain as botbrain
    import untitledapp.botstrategy as botstrategy

    for item in overrides or []:
        name, _, text = item.partition("=")
        value = ast.literal_eval(text)
        if "." in name:
            kind, field = name.split(".", 1)
            kinds = list(botbrain.PERSONALITIES) if kind == "*" else [kind]
            for key in kinds:
                botbrain.PERSONALITIES[key] = dataclasses.replace(botbrain.PERSONALITIES[key], **{field: value})
                wrong = botbrain.problems(botbrain.PERSONALITIES[key])
                if wrong:
                    raise SystemExit(f"--set {item}: {wrong}")
        else:
            module = next((m for m in (botbrain, botstrategy) if hasattr(m, name)), None)
            if module is None:
                raise SystemExit(f"--set {item}: neither botbrain nor botstrategy has {name}")
            setattr(module, name, value)
        applied[name] = value
    return applied


class Simulation:
    def __init__(self, mix, galaxies=4, days=7.0, tick_epochs=0.5, seed=1, election_day=2.0, quiet=True, overrides=None):
        os.environ.pop("EPOCH_SECONDS", None)  # the real epoch: time is simulated instead of shortened
        os.environ.setdefault("REFRESH_SECRET", "simulate")
        for path in (str(ROOT / "api"), str(ROOT)):
            if path not in sys.path:
                sys.path.insert(0, path)
        os.chdir(ROOT / "api")
        random.seed(seed)

        from tests import fake_backend
        import untitledapp
        from untitledapp import create_app, REQUESTS_SESSION
        import untitledapp.shared as uas

        self.uas = uas
        self.epoch = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        self.tick_seconds = tick_epochs * self.epoch
        self.days = days
        self.container = fake_backend.FakeContainer(latency=0)
        session = fake_backend.FakeSession(fake_backend.load_function_app(self.container))
        # Every function app call is counted, and those made while a bot thinks are counted apart, for the cost of
        # the bots (docs/cost.md).
        self.calls = collections.Counter()
        self.thinking = False

        def request(method, url, *args, **kwargs):
            self.calls["all"] += 1
            if self.thinking:
                self.calls["thinking"] += 1
            return session.request(method, url, *args, **kwargs)

        REQUESTS_SESSION.request = request
        self.app = create_app(config_class="config.TestingConfig")
        self.app.testing = True
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        # What the game logs as an error (a bot that failed to think, a kingdom the refresh skipped) is collected
        # and reported at the end, instead of scrolling past.
        self.errors = collections.Counter()
        simulation = self

        class Collect(logging.Handler):
            def emit(self, record):
                message = record.getMessage()
                if record.exc_info and record.exc_info[1] is not None:
                    import traceback
                    frames = traceback.extract_tb(record.exc_info[2])
                    where = f"{pathlib.Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else ""
                    message = f"{message.split(' ')[0]}... {record.exc_info[1]!r} at {where}"
                simulation.errors[message[:300]] += 1

        collect = Collect(level=logging.ERROR)
        self.app.logger.addHandler(collect)
        if quiet:
            self.app.logger.propagate = False
            for handler in list(self.app.logger.handlers):
                if handler is not collect:
                    self.app.logger.removeHandler(handler)
            logging.getLogger().setLevel(logging.CRITICAL)
        self.client = self.app.test_client()
        endpoint = self.app.config["AZURE_FUNCTION_ENDPOINT"]

        import untitledapp.botbrain as botbrain
        import untitledapp.bots as bots

        self.overrides = apply_overrides(overrides)

        # The bots draw their own random numbers (each think makes a fresh generator). Here they are all drawn from
        # the seed, so the same arguments play the same round.
        seeded = types.SimpleNamespace(**{name: getattr(random, name) for name in dir(random) if not name.startswith("_")})
        seeded.Random = lambda *args: random.Random(args[0] if args else random.random())
        botbrain.random = seeded
        bots.random = seeded
        # Ids of scheduled actions too: they order some lists.
        botbrain.uuid = types.SimpleNamespace(uuid4=lambda: uuid.UUID(int=random.getrandbits(128), version=4))

        real_think = botbrain.think

        def counted_think(*args, **kwargs):
            self.calls["thinks"] += 1
            self.thinking = True
            try:
                return real_think(*args, **kwargs)
            finally:
                self.thinking = False

        botbrain.think = counted_think

        self.clock = Clock(datetime.datetime.now(datetime.timezone.utc))
        self.clock.install()
        self.start = self.clock.now

        REQUESTS_SESSION.post(f"{endpoint}/init")
        with self.app.app_context():
            untitledapp.seed_testing_users()
        login = self.client.post("/api/adminlogin", json={"username": "admin", "password": "admin"})
        admin = {"Authorization": "Bearer " + login.json["accessToken"]}
        self.client.post("/api/createstate", headers=admin, json={
            "num_galaxies": galaxies, "max_galaxy_size": 50, "avg_size_new_galaxy": 10})
        self.end = self.start + datetime.timedelta(days=days)
        self.client.post("/api/updatestate", headers=admin, json={
            "game_start": (self.start - datetime.timedelta(seconds=1)).isoformat(),
            "game_end": self.end.isoformat(),
            "election_start": (self.start + datetime.timedelta(days=election_day)).isoformat(),
            "election_end": "",
            "next_history": self.start.isoformat(),
        })
        created = self.client.post("/api/admin/bots", json=mix, headers=admin)
        assert created.status_code == 201, created.get_data(as_text=True)
        self.refresh_headers = {"Refresh-Secret": os.environ["REFRESH_SECRET"]}
        self.failed_ticks = []
        # Per kingdom, summed over the round: money by where it came from and where the auto builder sent it.
        self.flows = collections.defaultdict(collections.Counter)
        self.metric_samples = []  # (day, {kd_id: (type, metrics)})
        self.samples = []  # (day, {kd_id: (type, stars, networth)})

    # ------------------------------------------------------------------------------------------------------ running

    def doc(self, item):
        return self.container.docs.get(item, {})

    def kingdoms(self):
        return {kd_id: self.doc(f"kingdom_{kd_id}") for kd_id in self.doc("kingdoms").get("kingdoms", {})}

    def tick(self):
        self.calls["ticks"] += 1
        self.clock.advance(self.tick_seconds)
        result = self.client.get("/api/refreshdata", headers=self.refresh_headers)
        text = result.get_data(as_text=True)
        if result.status_code != 200 or "failed" in text:
            self.failed_ticks.append((self.day(), text[:200]))
        epochs = self.tick_seconds / self.epoch
        for kd_id, kd in self.kingdoms().items():
            money = (kd.get("income") or {}).get("money") or {}
            if not money:
                continue
            flow = self.flows[kd_id]
            flow["income from mines and people"] += money.get("gross", 0) * epochs
            flow["income from siphons"] += money.get("siphons_in", 0) * epochs
            flow["income lost to siphons"] += money.get("siphons_out", 0) * epochs
            net = money.get("net", 0) * epochs
            spending = kd.get("auto_spending") or {}
            for key in ("settle", "structures", "military", "engineers"):
                flow[f"to {key}"] += net * spending.get(key, 0) if kd.get("auto_spending_enabled") else 0
            flow["to money"] += net * (1 - sum(spending.values()) if kd.get("auto_spending_enabled") else 1)

    def day(self):
        return (self.clock.now - self.start).total_seconds() / 86400

    def sample(self):
        import untitledapp.botstrategy as strategy

        epochs = (self.clock.now - self.start).total_seconds() / self.epoch
        self.metric_samples.append((self.day(), {
            kd_id: ((kd.get("bot") or {}).get("type", "player"), kingdom_metrics(kd, epochs, self.uas, strategy))
            for kd_id, kd in self.kingdoms().items() if kd.get("race") and str(kd.get("status")).lower() != "dead"
        }))
        self.samples.append((self.day(), {
            kd_id: ((kd.get("bot") or {}).get("type", "player"), kd.get("stars", 0), kd.get("networth", 0),
                    kd.get("status"))
            for kd_id, kd in self.kingdoms().items() if kd.get("race")
        }))

    def run(self, progress=None, sample_days=0.5, recorder=None):
        next_sample = 0.0
        while self.clock.now < self.end - datetime.timedelta(seconds=self.tick_seconds):
            self.tick()
            if recorder:
                recorder.tick()
            if self.day() >= next_sample:
                self.sample()
                next_sample += sample_days
                if progress:
                    progress(self)
        self.sample()

    # ---------------------------------------------------------------------------------------------------- reporting

    def results(self):
        """Everything the report prints, as plain data."""
        kingdoms = {kd_id: kd for kd_id, kd in self.kingdoms().items() if kd.get("race")}
        scores = self.doc("scores")
        points = scores.get("points", {})
        galaxy_of = {kd: galaxy for galaxy, members in self.doc("galaxies").get("galaxies", {}).items() for kd in members}
        rows = []
        actions = collections.defaultdict(collections.Counter)
        for kd_id, kd in kingdoms.items():
            kind = (kd.get("bot") or {}).get("type", "player")
            units = dict(kd["units"])
            for general in kd.get("generals_out", []):
                for unit, count in general.items():
                    if unit != "return_time":
                        units[unit] = units.get(unit, 0) + count
            rows.append({
                "kd": kd_id, "name": kd["name"], "type": kind, "galaxy": galaxy_of.get(kd_id), "status": kd["status"],
                "stars": kd["stars"], "networth": kd["networth"], "points": round(points.get(kd_id, 0), 1),
                "money": round(kd["money"]), "funding": round(sum(kd["funding"].values())),
                "funding_by": {k[:3]: round(v / 1000) for k, v in kd["funding"].items()},
                "fuel": round(kd["fuel"]), "population": round(kd["population"]), "drones": round(kd["drones"]),
                "units": {k: round(v) for k, v in units.items()},
                "structures": {k: round(v) for k, v in kd["structures"].items()},
                "phase": (kd.get("bot") or {}).get("phase"),
                "style": (kd.get("bot") or {}).get("style") or {},
                "spending": kd.get("auto_spending"),
                "log": (kd.get("bot") or {}).get("log", [])[-12:],
                "completed": kd.get("completed_projects", []),
            })
            counter = actions[kind]
            flow = self.flows[kd_id]

            def amounts(text):
                found = {}
                for number, what in NUMBER.findall(str(text)):
                    found.setdefault(what, float(number.replace(",", "")))
                return found

            for entry in self.doc(f"attack_history_{kd_id}").get("attack_history", []):
                gained = amounts(entry.get("news", ""))
                if entry.get("to") in ("", None):
                    counter["attack primitives"] += 1
                    flow["stars from primitives"] += gained.get("stars", 0)
                    flow["money from primitives"] += gained.get("money", 0)
                elif str(entry.get("news", "")).startswith("Success"):
                    counter["attack won"] += 1
                    flow["stars from kingdoms"] += gained.get("stars", 0)
                    flow["money from kingdoms"] += gained.get("money", 0)
                else:
                    counter["attack lost"] += 1
            for entry in self.doc(f"spy_history_{kd_id}").get("spy_history", []):
                won = "" if entry.get("to") in ("", None) else (
                    " ok" if not str(entry.get("news", "")).startswith("Failure") else " failed")
                counter[f"{entry.get('operation')}{won}"] += 1
                if entry.get("operation") == "Rob Primitives":
                    match = re.search(r"robbed ([\d,.]+) money", str(entry.get("news", "")))
                    flow["money from robbing"] += float(match.group(1).replace(",", "")) if match else 0
            counter["missile launches"] += len(self.doc(f"missile_history_{kd_id}").get("missile_history", []))
            news = self.doc(f"news_{kd_id}").get("news", [])
            # Intel news is also a sale or a fulfilled bounty; only the cut of an attack says "for sharing intel".
            cut_news = [item for item in news if item.get("kind") == "intel" and "for sharing intel" in str(item.get("news", ""))]
            counter["cuts earned for intel"] += len(cut_news)
            for item in cut_news:
                gained = amounts(item.get("news", ""))
                flow["stars from intel shared"] += gained.get("stars", 0)
                flow["money from intel shared"] += gained.get("money", 0)
                # The attacker that used the intel: how much the attackers lean on what galaxymates share.
                attacker = kingdoms.get(str(item.get("from")), {})
                actions[(attacker.get("bot") or {}).get("type", "player")]["attack won with shared intel"] += 1
            counter["times defeated"] += sum(1 for item in news if "was defeated" in str(item.get("news", "")))
            for item in news:
                if "was defeated" in str(item.get("news", "")):
                    flow["stars lost to kingdoms"] += amounts(item["news"]).get("stars", 0)
                elif item.get("kind") == "missiles":
                    match = re.search(r"([\d,.]+) stars", str(item.get("news", "")))
                    flow["stars lost to missiles"] += float(match.group(1).replace(",", "")) if match else 0
            flow["stars settled (the rest)"] = max(
                kd["stars"] - 300 - flow["stars from primitives"] - flow["stars from kingdoms"]
                + flow["stars lost to kingdoms"] + flow["stars lost to missiles"], 0)
            rows[-1]["flows"] = dict(flow)
            galaxy = next((g for g, members in self.doc("galaxies").get("galaxies", {}).items() if kd_id in members), None)
            market = self.doc(f"galaxy_intel_{galaxy}") if galaxy else {}
            counter["intel listings open"] += sum(1 for item in (market.get("listings") or {}).values() if item.get("seller") == kd_id)
            counter["intel accepted (live)"] += sum(len(c) for c in ((market.get("accepted") or {}).get(kd_id) or {}).values())
            for entry in (kd.get("bot") or {}).get("log", []):
                counter[f"log:{entry.get('kind')}"] += 1
            for key, count in ((kd.get("bot") or {}).get("counts") or {}).items():
                counter[f"did:{key}"] += count
        empires = self.doc("empires").get("empires", {})
        universe_news = [item.get("news", item) for item in self.doc("universe_news").get("news", [])]
        return {
            "days": self.days, "rows": rows, "actions": {k: dict(v) for k, v in actions.items()},
            "empires": {eid: {"name": e.get("name"), "galaxies": e.get("galaxies"), "war": e.get("war"),
                              "denounced": e.get("denounced")} for eid, e in empires.items()},
            "universe_news": universe_news,
            "active_policies": self.doc("state").get("state", {}).get("active_policies"),
            "galaxy_policies": {g: self.doc(f"galaxy_votes_{g}").get("active_policies")
                                for g in self.doc("galaxies").get("galaxies", {})},
            "failed_ticks": self.failed_ticks,
            "errors": dict(self.errors),
            "calls": dict(self.calls),
            "overrides": self.overrides,
            "epochs": self.days * 86400 / self.epoch,
            "samples": self.samples,
            "metrics": self.metric_samples,
        }


def summarise(results):
    """Per playstyle: how many, alive, median and best stars and networth, and total points."""
    by_type = collections.defaultdict(list)
    for row in results["rows"]:
        by_type[row["type"]].append(row)
    table = {}
    for kind, rows in sorted(by_type.items()):
        alive = [row for row in rows if str(row["status"]).lower() != "dead"]
        table[kind] = {
            "n": len(rows), "alive": len(alive),
            "stars_median": statistics.median(row["stars"] for row in rows),
            "stars_max": max(row["stars"] for row in rows),
            "networth_median": statistics.median(row["networth"] for row in rows),
            "networth_max": max(row["networth"] for row in rows),
            "points": round(sum(row["points"] for row in rows), 1),
        }
    return table


def report(results, out=sys.stdout, detail=False):
    table = summarise(results)
    print(f"\nAfter {results['days']:g} days", file=out)
    print(f"{'type':<10}{'n':>3}{'alive':>6}{'stars med':>11}{'stars max':>11}{'nw med':>10}{'nw max':>10}{'points':>9}", file=out)
    for kind, row in table.items():
        print(f"{kind:<10}{row['n']:>3}{row['alive']:>6}{row['stars_median']:>11,.0f}{row['stars_max']:>11,.0f}"
              f"{row['networth_median']:>10,.0f}{row['networth_max']:>10,.0f}{row['points']:>9,.0f}", file=out)
    all_stars = [row["stars"] for row in results["rows"]]
    print(f"{'all':<10}{len(all_stars):>3}{'':>6}{statistics.median(all_stars):>11,.0f}{max(all_stars):>11,.0f}", file=out)

    print("\nGrowth (median stars by day):", file=out)
    kinds = sorted(table)
    print("  day   " + "".join(f"{kind:>10}" for kind in kinds), file=out)
    for day, sample in results["samples"]:
        if abs(day - round(day)) > 0.05 and day < results["days"] - 0.3:
            continue
        medians = []
        for kind in kinds:
            values = [stars for (k, stars, _, _) in sample.values() if k == kind]
            medians.append(statistics.median(values) if values else 0)
        print(f"  {day:5.1f} " + "".join(f"{value:>10,.0f}" for value in medians), file=out)

    print("\nMetrics (median by playstyle; dps = defense per star, against primitives and the deterrence line):", file=out)
    metric_names = list(next(iter(results["metrics"][-1][1].values()))[1]) if results.get("metrics") and results["metrics"][-1][1] else []
    shown_days = sorted({round(day) for day, _ in results.get("metrics", [])} | {results["days"]})
    for day_wanted in shown_days:
        day, sample = min(results["metrics"], key=lambda item: abs(item[0] - day_wanted))
        if not sample:
            continue
        print(f"  day {day:4.1f}" + "".join(f"{kind:>11}" for kind in kinds), file=out)
        for name in metric_names:
            if name in ("primitives_defense_per_star", "deterrence_per_star"):
                continue
            cells = []
            for kind in kinds:
                values = [m[name] for k, m in sample.values() if k == kind]
                cells.append(statistics.median(values) if values else 0)
            extra = ""
            if name == "defense_per_star":
                any_metrics = next(iter(sample.values()))[1]
                extra = f"   primitives {any_metrics['primitives_defense_per_star']:.0f}, deterrence {any_metrics['deterrence_per_star']:.0f}"
            print(f"    {name:<26}" + "".join(f"{value:>11,.2f}" for value in cells) + extra, file=out)

    print("\nWhere stars and money came from, and where the money went (median per kingdom, whole round):", file=out)
    flow_names = sorted({name for row in results["rows"] for name in row.get("flows", {})})
    print(f"    {'':<32}" + "".join(f"{kind:>11}" for kind in kinds), file=out)
    for name in flow_names:
        cells = []
        for kind in kinds:
            values = [row.get("flows", {}).get(name, 0) for row in results["rows"] if row["type"] == kind]
            cells.append(statistics.median(values) if values else 0)
        print(f"    {name:<32}" + "".join(f"{value:>11,.0f}" for value in cells), file=out)
    # Money flows are easier to judge against what a kingdom earns itself.
    for name in ("income from siphons", "income lost to siphons", "money from robbing", "money from intel shared"):
        cells = []
        for kind in kinds:
            values = [row.get("flows", {}).get(name, 0) / max(row.get("flows", {}).get("income from mines and people", 0), 1)
                      for row in results["rows"] if row["type"] == kind]
            cells.append(statistics.median(values) if values else 0)
        print(f"    {(name + ', % of own'):<32}" + "".join(f"{value:>11.1%}" for value in cells), file=out)

    print("\nSpy success rates (ok / tried):", file=out)
    for kind, counter in sorted(results["actions"].items()):
        rates = []
        for group, operations in (("intel", ("Spy on",)), ("hostile", ("Siphon", "Bomb", "Sabotage", "Kidnap"))):
            ok = sum(v for k, v in counter.items() if k.startswith(operations) and k.endswith(" ok"))
            failed = sum(v for k, v in counter.items() if k.startswith(operations) and k.endswith(" failed"))
            rates.append(f"{group} {ok / max(ok + failed, 1):.0%} of {ok + failed}")
        print(f"  {kind}: " + ", ".join(rates), file=out)

    print("\nActions by playstyle:", file=out)
    for kind, counter in sorted(results["actions"].items()):
        shown = ", ".join(f"{name} {count}" for name, count in sorted(counter.items()) if count)
        print(f"  {kind}: {shown}", file=out)
    print(f"\nUniverse policies: {results['active_policies']}", file=out)
    print(f"Galaxy policies: {results['galaxy_policies']}", file=out)
    print(f"Empires: {results['empires']}", file=out)
    for news in results["universe_news"][-12:]:
        print(f"  news: {news}", file=out)
    for message, count in sorted(results.get("errors", {}).items(), key=lambda item: -item[1])[:15]:
        print(f"  error x{count}: {message}", file=out)
    calls = results.get("calls") or {}
    if calls.get("thinks"):
        bots = max(len(results["rows"]), 1)
        print(f"\nFunction app calls: {calls['all']:,} in {calls['ticks']:,} ticks. Bots thought {calls['thinks']:,} times "
              f"({calls['thinks'] / bots / results['epochs']:.2f} per bot per epoch), {calls['thinking'] / calls['thinks']:.1f} calls a think: "
              f"{calls['thinking'] / bots / results['epochs']:.1f} calls per bot per epoch.", file=out)
    if results["failed_ticks"]:
        print(f"\n{len(results['failed_ticks'])} ticks reported failures, e.g. {results['failed_ticks'][0]}", file=out)
    if detail:
        print("\nKingdoms:", file=out)
        for row in sorted(results["rows"], key=lambda r: -r["networth"]):
            style = row.get("style") or {}
            tag = f"{style.get('army', '-')}/{style.get('drones', '-')}{'/bomber' if style.get('bomber') else ''}"
            print(f"  {row['name']:<18}{row['galaxy']:<5}{row['status']:<7}{str(row['phase']):<6}{tag:<26} stars {row['stars']:>6,}"
                  f" nw {row['networth']:>8,} pts {row['points']:>6,.0f} money {row['money']:>9,} idle funding(k) {row['funding_by']}"
                  f" fuel {row['fuel']:>8,} pop {row['population']:>7,} drones {row['drones']:>7,} units {row['units']}"
                  f" {row['completed']}", file=out)


def parse_mix(text, bots):
    if text:
        return {key: int(value) for key, value in (part.split("=") for part in text.split(","))}
    sys.path.insert(0, str(ROOT / "api"))
    import untitledapp.bots as bots_module

    return bots_module.mix_for(bots)


def main():
    # Python orders a set of strings differently in every process unless the hash seed is fixed, and the game and the
    # bots loop over sets of kingdom ids: run again with it fixed, so a seed always plays the same round.
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit(subprocess.run([sys.executable, *sys.argv], env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bots", type=int, default=40, help="total, split over the archetypes as bots.DEFAULT_MIX has it")
    parser.add_argument("--mix", help="instead of --bots: e.g. explorer=10,attacker=10")
    parser.add_argument("--galaxies", type=int, default=4)
    parser.add_argument("--days", type=float, default=7.0, help="length of the round in game days")
    parser.add_argument("--tick", type=float, default=0.5, help="epochs of game time between refreshes")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--election-day", type=float, default=2.0)
    parser.add_argument("--detail", action="store_true", help="also list every kingdom")
    parser.add_argument("--json", help="write the results to this file")
    parser.add_argument("--replay", help="write a page to watch the round back (HTML, opens from disk)")
    parser.add_argument("--errors", action="store_true", help="let the game log its errors")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", dest="overrides",
                        help="try a bot number without editing the code (see above); may be repeated")
    args = parser.parse_args()

    mix = parse_mix(args.mix, args.bots)
    started = time.time()
    real_stdout, sys.stdout = sys.stdout, open(os.devnull, "w")  # the game code prints as it goes
    try:
        sim = Simulation(mix, galaxies=args.galaxies, days=args.days, tick_epochs=args.tick, seed=args.seed,
                         election_day=args.election_day, quiet=not args.errors, overrides=args.overrides)

        def progress(sim):
            stars = sorted((s for (_, s, _, _) in sim.samples[-1][1].values()), reverse=True)
            print(f"  day {sim.day():4.1f}  {time.time() - started:5.0f}s  top stars {stars[:3]}", file=real_stdout, flush=True)

        recorder = Recorder(sim) if args.replay else None
        sim.run(progress=progress, recorder=recorder)
        results = sim.results()
        if recorder:
            recorder.write(args.replay)
    finally:
        sys.stdout = real_stdout
    report(results, detail=args.detail)
    print(f"\n{sum(mix.values())} bots {mix}, {args.galaxies} galaxies, seed {args.seed}, {time.time() - started:.0f}s"
          + (f", with {results['overrides']}" if results["overrides"] else ""))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(results, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
