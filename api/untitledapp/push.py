"""
Push notifications: the messages the server sends down a player's open websocket when something happens to their
kingdom (a build finished, a galaxymate was attacked, a message came in). The browser shows them in the Notifications
panel and refreshes the data keys named in ``update``.

Each one has a ``kind`` from ``KINDS``, which the Settings page lists so a player can turn off the kinds they do not want
to see (``muted`` in their preferences, preferences.py). The browser does the hiding: the server sends every
notification, because reading every player's preferences on every tick would cost a read per player per tick, and the
``update`` keys must still reach the page so its data stays current.
"""
import json

from flask_sock import ConnectionClosed

from untitledapp import SOCK_HANDLERS

# (kind, label, group), in the order the Settings page shows them. The label is also the category the panel shows.
KINDS = [
    ("settles", "Settles", "Your kingdom"),
    ("structures", "Structures", "Your kingdom"),
    ("military", "Military", "Your kingdom"),
    ("missiles", "Missiles", "Your kingdom"),
    ("engineers", "Engineers", "Your kingdom"),
    ("projects", "Projects", "Your kingdom"),
    ("generals", "Generals", "Your kingdom"),
    ("spy_attempts", "Spy attempts", "Your kingdom"),
    ("auto_primitives", "Auto primitives", "Your kingdom"),
    ("schedules", "Scheduled actions", "Your kingdom"),
    ("messages", "Messages", "Other players"),
    ("galaxy", "Galaxy", "Other players"),
    ("targets", "Empire targets", "Other players"),
    ("intel", "Intel market", "Other players"),
    ("attacked", "Attacks on you", "Against you"),
    ("spied", "Spy operations on you", "Against you"),
    ("missile_strikes", "Missile strikes on you", "Against you"),
]
MUTABLE = {kind for kind, _, _ in KINDS}
# Shown whatever the player's settings say.
ALWAYS = {"dead": "Dead"}
_LABELS = {**{kind: label for kind, label, _ in KINDS}, **ALWAYS}


def push(kd_id, kind, message, status="info", delay=15000, update=()):
    """Send one notification to the kingdom's open socket, if it has one. A closed or missing socket is not an error."""
    payload = {
        "message": message,
        "status": status,
        "kind": kind,
        "category": _LABELS[kind],
        "delay": delay,
        "update": list(update),
    }
    try:
        SOCK_HANDLERS[kd_id].send(json.dumps(payload))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
