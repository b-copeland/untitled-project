"""Run several simulated rounds at once, one process each, and compare variants by the mean over seeds.

``scripts/simulate_round.py`` plays one round in one process (about 12 minutes for a week of 100 bots), and a result
needs about three seeds and every variant you want to compare. Rounds do not depend on each other, so this runs them
side by side, one subprocess each (a seed always plays the same round, whatever else is running).

    python scripts/simulate_many.py --seeds 1,2,3 --days 7 --bots 100 --galaxies 10
    python scripts/simulate_many.py --seeds 1,2,3 --variant base= --variant "wide=--set HOMES_FLOOR=0.1"
    python scripts/simulate_many.py --workers 8 --variant "x=--set thief.defense_margin=1.3 --set MIN_DEFENSE=1"

Each ``--variant`` is ``name=<extra arguments for simulate_round.py>`` (empty for the code as it is). The report is, per
variant and playstyle, the mean over the seeds of the kingdoms' mean stars and networth (means, not medians: medians
hide a playstyle that half the time does nothing), and the share that died. Results are kept as JSON in ``--out``
(default: the system temp directory) so a run can be looked at again.

Run it in the Flask environment, from the repository root. A worker is about a core and a gigabyte of memory.
"""
import argparse
import collections
import concurrent.futures
import json
import os
import pathlib
import shlex
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_one(job):
    """One round in its own process. Returns ``(variant, seed, results or None, seconds, error)``."""
    variant, seed, extra, common, out_dir = job
    path = pathlib.Path(out_dir) / f"{variant}_seed{seed}.json"
    command = [sys.executable, str(ROOT / "scripts" / "simulate_round.py"), *common, "--seed", str(seed),
               "--json", str(path), *extra]
    started = time.time()
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if done.returncode != 0 or not path.exists():
        return variant, seed, None, time.time() - started, (done.stderr or done.stdout)[-600:]
    return variant, seed, json.loads(path.read_text(encoding="utf-8")), time.time() - started, None


def means(results):
    """``{playstyle: {n, alive, stars, networth, points}}``: means over the playstyle's kingdoms."""
    by_type = collections.defaultdict(list)
    for row in results["rows"]:
        by_type[row["type"]].append(row)
    return {
        kind: {
            "n": len(rows),
            "alive": sum(str(r["status"]).lower() != "dead" for r in rows) / len(rows),
            "stars": statistics.mean(r["stars"] for r in rows),
            "networth": statistics.mean(r["networth"] for r in rows),
            "points": statistics.mean(r["points"] for r in rows),
        }
        for kind, rows in by_type.items()
    }


def compare(finished, out=sys.stdout):
    """Print the per-variant table: mean over seeds of each playstyle's means."""
    kinds = sorted({kind for runs in finished.values() for results in runs for kind in means(results)})
    for field, title in (("stars", "Stars (mean of kingdoms, then of seeds)"), ("networth", "Networth"),
                         ("alive", "Share alive"), ("points", "Points")):
        print(f"\n{title}", file=out)
        print(f"  {'variant':<22}{'seeds':>6}" + "".join(f"{kind:>11}" for kind in kinds) + f"{'all':>11}", file=out)
        for variant, runs in finished.items():
            cells, weights = [], []
            for kind in kinds:
                values = [means(r)[kind][field] for r in runs if kind in means(r)]
                cells.append(statistics.mean(values) if values else 0.0)
                weights.append(statistics.mean(means(r)[kind]["n"] for r in runs if kind in means(r)) if values else 0)
            overall = sum(c * w for c, w in zip(cells, weights)) / max(sum(weights), 1)
            fmt = (lambda v: f"{v:>11.0%}") if field == "alive" else (lambda v: f"{v:>11,.0f}")
            print(f"  {variant:<22}{len(runs):>6}" + "".join(fmt(c) for c in cells) + fmt(overall), file=out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default="1,2,3", help="comma separated")
    parser.add_argument("--variant", action="append", default=[], metavar="NAME=ARGS",
                        help="a variant: name, then the arguments for simulate_round.py (default: one called base)")
    parser.add_argument("--workers", type=int, default=max((os.cpu_count() or 2) // 2, 1))
    parser.add_argument("--out", default=str(pathlib.Path(tempfile.gettempdir()) / "simulate_many"))
    parser.add_argument("--bots", type=int, default=100)
    parser.add_argument("--galaxies", type=int, default=10)
    parser.add_argument("--days", type=float, default=7.0)
    args, passthrough = parser.parse_known_args()

    variants = {}
    for text in args.variant or ["base="]:
        name, _, extra = text.partition("=")
        variants[name] = shlex.split(extra, posix=False) if extra else []
    seeds = [int(seed) for seed in args.seeds.split(",")]
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    common = ["--bots", str(args.bots), "--galaxies", str(args.galaxies), "--days", str(args.days), *passthrough]
    jobs = [(name, seed, [part.strip('"') for part in extra], common, str(out_dir)) for name, extra in variants.items() for seed in seeds]

    print(f"{len(jobs)} rounds on {args.workers} workers; results in {out_dir}", flush=True)
    finished = collections.defaultdict(list)
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:  # threads only wait on subprocesses
        for variant, seed, results, seconds, error in pool.map(run_one, jobs):
            if results is None:
                print(f"  {variant} seed {seed} FAILED after {seconds:.0f}s: {error}", flush=True)
                continue
            finished[variant].append(results)
            print(f"  {variant} seed {seed} done in {seconds:.0f}s ({time.time() - started:.0f}s in all)", flush=True)
    if finished:
        compare(finished)


if __name__ == "__main__":
    main()
