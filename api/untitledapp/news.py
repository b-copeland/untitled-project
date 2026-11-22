"""
News lines that are not about one kingdom: a galaxy's news (``galaxy_news_<id>``), an empire's news
(``empire_news_<id>``, read by its members on the News page) and the universe news (read by everyone). Both are appends the function app applies to the newest version of the
document, so callers post after their decision has landed and never need a condition.

Each call here is one function app call per document. Pass every line for a document in one call where there are
several (the refresh's wars by aggression, for example).
"""
import datetime
import functools
import json
import logging

import flask

from untitledapp import REQUESTS_SESSION


def best_effort(post):
    """For a function that only posts news after an action has landed: a failure is logged, never raised, so the
    player's action still answers as done (it was)."""
    @functools.wraps(post)
    def wrapped(*args, **kwargs):
        try:
            return post(*args, **kwargs)
        except Exception:  # noqa: BLE001 (news is a side effect; the action it reports has already happened)
            logging.getLogger(__name__).exception("News not posted by %s", post.__name__)
            return None
    return wrapped


def item(message, time_now=None):
    """One news line as stored: ``{"time", "news"}``."""
    time_now = time_now or datetime.datetime.now(datetime.timezone.utc)
    return {"time": time_now.isoformat(), "news": message}


def _patch(path, items):
    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + path,
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"news": items}),
    )


def empire(empires, message, time_now=None):
    """Add ``message`` to the news of each empire in ``empires`` (ids; ``None`` and repeats are skipped)."""
    line = item(message, time_now)
    for empire_id in dict.fromkeys(str(empire_id) for empire_id in empires if empire_id is not None):
        _patch(f'/empire/{empire_id}/news', [line])


def empire_lines(lines_by_empire):
    """Several lines per empire, ``{empire_id: [line, ...]}`` (newest first), in one call per empire."""
    for empire_id, lines in lines_by_empire.items():
        if lines:
            _patch(f'/empire/{empire_id}/news', lines)


def galaxy(galaxy_id, message, time_now=None, kind="", from_kd="", to_kd=""):
    """Add a line to a galaxy's news. ``kind`` labels it on the News page; ``from_kd`` and ``to_kd`` are kingdoms the
    page links to (empty for none)."""
    app = flask.current_app
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({**item(message, time_now), "kind": kind, "from": from_kd, "to": to_kd}),
    )


def universe(message, time_now=None):
    """Add ``message`` to the universe news."""
    universe_lines([item(message, time_now)])


def universe_lines(lines):
    """Several lines (newest first) for the universe news, in one call."""
    if lines:
        _patch('/universenews', lines)
