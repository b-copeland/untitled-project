"""Call /api/refreshdata on the local API every few seconds, so game time moves forward like it does in production.

Locally nothing else calls the refresh (see docs/development.md), so without this income, finished builds, scheduled
actions, reveal expiry, scores and bots (they think from the refresh) only change when you call it by hand.

Start it after the API (step 5 in CLAUDE.md "Running locally"), in its own terminal:

    python scripts/refresh_loop.py [--interval 30] [--url http://localhost:8000]

It reads ``REFRESH_SECRET`` from the environment, or else from api/.flaskenv, and never prints it. Stop it with Ctrl+C.
It keeps going if the API is down or a refresh fails, and says so once per change rather than on every try. Uses only
the standard library, so any Python will do.
"""
import argparse
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

FLASKENV = pathlib.Path(__file__).resolve().parent.parent / "api" / ".flaskenv"


def read_secret(env=os.environ, flaskenv=FLASKENV):
    """REFRESH_SECRET from the environment, or from the ``KEY=value`` lines of api/.flaskenv. None if it is in neither."""
    if env.get("REFRESH_SECRET"):
        return env["REFRESH_SECRET"]
    try:
        lines = pathlib.Path(flaskenv).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if line.startswith("REFRESH_SECRET") and "=" in line:
            return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


def refresh_once(url, secret, timeout=120):
    """One call. Returns ``(ok, text)``: whether it worked and what the API said (or what went wrong)."""
    request = urllib.request.Request(url.rstrip("/") + "/api/refreshdata", headers={"Refresh-Secret": secret})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, response.read().decode("utf-8", "replace").strip()
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code}: {error.read().decode('utf-8', 'replace').strip()[:200]}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return False, f"could not reach the API ({getattr(error, 'reason', error)})"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--interval", type=float, default=30.0, help="seconds between refreshes (default 30)")
    parser.add_argument("--url", default="http://localhost:8000", help="the Flask API (default http://localhost:8000)")
    parser.add_argument("--once", action="store_true", help="refresh once and exit")
    args = parser.parse_args(argv)

    secret = read_secret()
    if not secret:
        print("No REFRESH_SECRET in the environment or api/.flaskenv.", file=sys.stderr)
        return 2

    print(f"Refreshing {args.url} every {args.interval:g}s. Ctrl+C to stop.")
    last = None
    while True:
        started = time.monotonic()
        ok, text = refresh_once(args.url, secret)
        # Say something only when it changes (starts working, stops working, or the message differs).
        if (ok, text) != last:
            print(f"{time.strftime('%H:%M:%S')}  {'ok' if ok else 'FAILED'}: {text}", flush=True)
            last = (ok, text)
        if args.once:
            return 0 if ok else 1
        try:
            # The interval is from one start to the next, so a slow refresh does not push the schedule back.
            time.sleep(max(args.interval - (time.monotonic() - started), 0.5))
        except KeyboardInterrupt:
            print("Stopped.")
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Stopped.")
