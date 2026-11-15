"""Count what each Flask route and each refresh tick costs in function app calls and Cosmos operations.

Runs entirely in this process on the in-memory backend the tests use (``tests/fake_backend.py``): no emulator, function
host or Azure. It builds a game of bots, then measures:

* every read route a page loads, and a few common actions, as the player of kingdom 1;
* refresh ticks, with a short epoch so queues, auto spending and the bot brain all run.

For each it reports the function app calls (each one is a function execution and an HTTP round trip in production),
the Cosmos reads and writes behind them, the bytes written (Cosmos charges writes by size), and the time spent.

    python scripts/profile_calls.py                      # 24 bots, 8 ticks
    python scripts/profile_calls.py --bots 60 --ticks 12 --calls   # also list the calls per route
    python scripts/profile_calls.py --cprofile           # also show where the refresh spends Python time

Run it in the Flask environment, from the repository root. Numbers are counts, so they hold on any machine; the times
are only for comparing before and after on the same machine.
"""
import argparse
import collections
import contextlib
import cProfile
import datetime
import io
import json
import logging
import os
import pathlib
import pstats
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _setup_environment(epoch_seconds):
    os.environ["EPOCH_SECONDS"] = str(epoch_seconds)
    os.environ.setdefault("REFRESH_SECRET", "profile")
    sys.path.insert(0, str(ROOT / "api"))
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT / "api")


class Recorder:
    """Wraps the session and the container, and files every call under the scope that is open."""

    def __init__(self, session, container):
        self.scope = None
        self.calls = collections.defaultdict(collections.Counter)  # scope -> "METHOD /path" -> count
        self.ops = collections.defaultdict(collections.Counter)  # scope -> read/write/bytes
        self.seconds = collections.defaultdict(float)
        self.runs = collections.Counter()
        self.sites = None  # scope -> (call, chain of game functions that made it) -> count, with --sites
        self._wrap_session(session)
        self._wrap_container(container)

    def _wrap_session(self, session):
        original = session.request

        def request(method, url, *args, **kwargs):
            if self.scope:
                path = url.split("/api", 1)[-1]
                path = re.sub(r"/\d+(?=/|$)", "/{id}", path.split("?")[0])
                path = re.sub(r"/1:\d+", "/{galaxy}", path)
                self.calls[self.scope][f"{method.upper()} {path}"] += 1
                if self.sites is not None:
                    self.sites[self.scope][(f"{method.upper()} {path}", self._call_site())] += 1
            return original(method, url, *args, **kwargs)

        session.request = request

    @staticmethod
    def _call_site():
        """The game functions on the stack, innermost last, e.g. ``_refresh_kd > _kingdom_with_income > _get_siphons_in``."""
        names = []
        frame = sys._getframe(2)
        while frame:
            # The session and the request cache are plumbing; the game function that called them is what matters.
            plumbing = frame.f_code.co_filename.endswith(("__init__.py", "request_cache.py"))
            if "untitledapp" in frame.f_code.co_filename and not plumbing:
                module = pathlib.Path(frame.f_code.co_filename).stem
                names.append(f"{module}.{frame.f_code.co_name}")
            frame = frame.f_back
        names.reverse()
        return " > ".join(names[-4:])

    def _wrap_container(self, container):
        recorder = self

        def counted(name, kind):
            original = getattr(container, name)

            def wrapper(*args, **kwargs):
                if recorder.scope:
                    recorder.ops[recorder.scope][kind] += 1
                    if kind == "write":
                        body = kwargs.get("body") or (args[1] if len(args) > 1 else args[0])
                        recorder.ops[recorder.scope]["bytes_written"] += len(json.dumps(body, default=str))
                return original(*args, **kwargs)

            setattr(container, name, wrapper)

        counted("read_item", "read")
        counted("replace_item", "write")
        counted("create_item", "write")

    @contextlib.contextmanager
    def measure(self, scope):
        self.scope = scope
        self.runs[scope] += 1
        started = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[scope] += time.perf_counter() - started
            self.scope = None

    def report(self, show_calls):
        width = max(len(scope) for scope in self.runs) + 2
        print(f"{'scope':<{width}}{'runs':>5}{'calls':>8}{'reads':>8}{'writes':>8}{'KB written':>12}{'ms':>9}   (per run)")
        for scope in self.runs:
            runs = self.runs[scope]
            calls = sum(self.calls[scope].values()) / runs
            ops = self.ops[scope]
            print(
                f"{scope:<{width}}{runs:>5}{calls:>8.1f}{ops['read'] / runs:>8.1f}{ops['write'] / runs:>8.1f}"
                f"{ops['bytes_written'] / runs / 1024:>12.1f}{self.seconds[scope] / runs * 1000:>9.1f}"
            )
            if show_calls:
                for call, count in self.calls[scope].most_common():
                    print(f"{'':<{width}}    {count / runs:>6.1f}  {call}")
            if self.sites is not None:
                for (call, site), count in self.sites[scope].most_common():
                    print(f"{'':<{width}}    {count / runs:>6.1f}  {call}  <- {site}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bots", type=int, default=24, help="total, split evenly over the four archetypes")
    parser.add_argument("--galaxies", type=int, default=3)
    parser.add_argument("--ticks", type=int, default=8)
    parser.add_argument("--epoch", type=float, default=4, help="seconds in an epoch, so a few ticks cover several")
    parser.add_argument("--tick-every", type=float, default=2.0, help="seconds between ticks")
    parser.add_argument("--calls", action="store_true", help="list the function app calls of each scope")
    parser.add_argument("--sites", action="store_true", help="list which game functions made each call")
    parser.add_argument("--only", help="measure only the scopes containing this text, e.g. 'refresh'")
    parser.add_argument("--cprofile", action="store_true", help="profile the Python time of the refresh ticks")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    _setup_environment(args.epoch)
    real_stdout, sys.stdout = sys.stdout, open(os.devnull, "w")  # the game code prints its lock bookkeeping
    import random

    random.seed(args.seed)

    from tests import fake_backend
    from untitledapp import create_app, REQUESTS_SESSION

    container = fake_backend.FakeContainer(latency=0)
    function_app = fake_backend.load_function_app(container)
    session = fake_backend.FakeSession(function_app)
    REQUESTS_SESSION.request = session.request
    recorder = Recorder(REQUESTS_SESSION, container)
    if args.sites:
        recorder.sites = collections.defaultdict(collections.Counter)
    if args.only:
        measure = recorder.measure

        @contextlib.contextmanager
        def measure_only(scope):
            if args.only in scope:
                with measure(scope):
                    yield
            else:
                yield

        recorder.measure = measure_only

    app = create_app(config_class="config.TestingConfig")
    app.testing = True  # a failing route answers 500 instead of raising, so one bad request does not end the run
    app.config["PROPAGATE_EXCEPTIONS"] = False
    logging.disable(logging.CRITICAL)
    client = app.test_client()
    endpoint = app.config["AZURE_FUNCTION_ENDPOINT"]

    # --- the world ----------------------------------------------------------------------------------------------------
    REQUESTS_SESSION.post(f"{endpoint}/init")
    admin = {"Authorization": "Bearer " + client.post("/api/adminlogin", json={"username": "admin", "password": "admin"}).json["accessToken"]}
    client.post("/api/createstate", json={"num_galaxies": args.galaxies, "max_galaxy_size": 50, "avg_size_new_galaxy": 10}, headers=admin)
    now = datetime.datetime.now(datetime.timezone.utc)
    client.post("/api/updatestate", headers=admin, json={
        "game_start": (now - datetime.timedelta(seconds=1)).isoformat(),
        "game_end": (now + datetime.timedelta(days=1)).isoformat(),
        "election_start": (now + datetime.timedelta(days=1)).isoformat(),
        "election_end": "",
        "next_history": now.isoformat(),
    })
    each = max(1, args.bots // 4)
    created = client.post("/api/admin/bots", json={"explorer": each, "attacker": each, "intel": each, "thief": each}, headers=admin)
    assert created.status_code == 201, created.json
    player = {"Authorization": "Bearer " + client.post("/api/login", json={"username": "user1", "password": "user1"}).json["accessToken"]}
    refresh_headers = {"Refresh-Secret": os.environ["REFRESH_SECRET"]}

    # Warm the world up: a couple of ticks so queues and intel exist.
    for _ in range(2):
        client.get("/api/refreshdata", headers=refresh_headers)
        time.sleep(args.tick_every)

    # --- page loads ---------------------------------------------------------------------------------------------------
    target = "5"
    reads = [
        "/api/state", "/api/kingdom", "/api/kingdomid", "/api/shields", "/api/news", "/api/messages", "/api/kingdoms",
        "/api/galaxies", "/api/galaxies_inverted", "/api/empires", "/api/empires_inverted", "/api/galaxynews",
        "/api/universenews", "/api/attackhistory", "/api/spyhistory", "/api/missilehistory", "/api/mobis",
        "/api/structures", f"/api/kingdom/{target}", "/api/galaxy/1:1", "/api/settle", "/api/missiles", "/api/engineers",
        "/api/projects", "/api/revealed", "/api/shared", "/api/pinned", "/api/galaxypolitics", "/api/universepolitics",
        "/api/siphonsout", "/api/history", "/api/scores", "/api/notifs", f"/api/attackcontext/{target}",
        "/api/revealrandomgalaxy",
    ]
    for _ in range(3):
        for path in reads:
            with recorder.measure(f"GET {path}"):
                response = client.get(path, headers=player)
            if response.status_code >= 500:
                print(f"! {path} answered {response.status_code}", file=sys.stderr)
    defender = {"military_bonus": 0, "shields": 0, "other_bonuses": 0, "drones": 0, "stars": 0}
    posts = [
        ("/api/kingdomsinfo", {"kingdoms": [str(i) for i in range(args.bots)]}),
        (f"/api/calculate/{target}", {"attackerValues": {"attack": 10, "generals": 1}, "defenderValues": defender}),
        (f"/api/autofill/{target}", {"attackerValues": {"generals": 1}, "defenderValues": defender, "buffer": 5, "generals": 1}),
        (f"/api/calculatespy/{target}", {"drones": 10, "shielded": False, "operation": "spykingdom", "defenderValues": defender}),
        ("/api/calculateprimitives", {"attackerValues": {"attack": 10, "generals": 1}}),
        ("/api/structures", {"homes": 1}),
        ("/api/settle", {"settleInput": 1}),
        ("/api/mobis", {"attack": 1}),
        (f"/api/spy/{target}", {"drones": 10, "shielded": False, "operation": "spykingdom"}),
        (f"/api/attack/{target}", {"attackerValues": {"attack": 1, "generals": 1}, "defenderValues": defender}),
    ]
    for _ in range(3):
        for path, body in posts:
            with recorder.measure(f"POST {path}"):
                response = client.post(path, json=body, headers=player)
            if response.status_code >= 500:
                print(f"! {path} answered {response.status_code}", file=sys.stderr)

    # --- refresh ------------------------------------------------------------------------------------------------------
    profiler = cProfile.Profile() if args.cprofile else None
    for _ in range(args.ticks):
        time.sleep(args.tick_every)
        with recorder.measure("refresh tick"):
            if profiler:
                profiler.enable()
            result = client.get("/api/refreshdata", headers=refresh_headers)
            if profiler:
                profiler.disable()
        if "failed" in result.text:
            print("!", result.text[:300], file=sys.stderr)

    sys.stdout = real_stdout
    print(f"\n{args.bots} bots, {args.galaxies} galaxies, epoch {args.epoch}s, {args.ticks} ticks {args.tick_every}s apart\n")
    recorder.report(args.calls)
    ticks = recorder.runs["refresh tick"]
    if ticks:
        per_kd = sum(recorder.calls["refresh tick"].values()) / ticks / max(args.bots, 1)
        print(f"\nrefresh: {per_kd:.1f} function app calls per kingdom per tick")
    if profiler:
        out = io.StringIO()
        stats = pstats.Stats(profiler, stream=out)
        stats.sort_stats("cumulative").print_stats(25)
        # The game's own functions by the time spent in their own code: where Python time goes, apart from the
        # SQLite locks and the in-memory backend (which production does not have).
        stats.sort_stats("tottime").print_stats("untitledapp", 25)
        print(out.getvalue())


if __name__ == "__main__":
    main()
