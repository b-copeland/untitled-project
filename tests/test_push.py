"""
Push notifications (``untitledapp/push.py``): every one carries a kind the Settings page can list, and a kingdom with no
open socket is not an error.
"""
import json
import pathlib
import re

import untitledapp
from untitledapp import push as uapu
from untitledapp import refresh as uar

API = pathlib.Path(__file__).resolve().parents[1] / "api" / "untitledapp"


class _Socket:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(json.loads(text))


def test_a_push_carries_its_kind_and_the_label_as_its_category(monkeypatch):
    socket = _Socket()
    monkeypatch.setitem(untitledapp.SOCK_HANDLERS, "7", socket)
    uapu.push("7", "spy_attempts", "A new spy attempt is available", update=("kingdom",))
    assert socket.sent == [{
        "message": "A new spy attempt is available", "status": "info", "kind": "spy_attempts",
        "category": "Spy attempts", "delay": 15000, "update": ["kingdom"],
    }]


def test_a_kingdom_without_a_socket_is_skipped():
    uapu.push("no such kingdom", "settles", "Finished settling 3 stars")


def test_every_push_in_the_code_uses_a_known_kind():
    known = uapu.MUTABLE | set(uapu.ALWAYS)
    used = set()
    for path in API.glob("*.py"):
        used |= set(re.findall(r"\bpush\([^,]+,\s*\"(\w+)\"", path.read_text(encoding="utf-8")))
    queue_kinds = {kind for kind, _ in uar._QUEUE_NOTICES.values()}
    assert used, "found no push calls: the pattern is out of date"
    assert used | queue_kinds <= known, (used | queue_kinds) - known
    # Every kind the page offers is one the server sends.
    assert uapu.MUTABLE <= used | queue_kinds, uapu.MUTABLE - (used | queue_kinds)
