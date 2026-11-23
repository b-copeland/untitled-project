"""The notification sockets (sockets.py): several per kingdom, registered only with a valid token, removed when gone."""
import json

from flask_sock import ConnectionClosed

from untitledapp.sockets import Registry, serve


class FakeSocket:
    """A socket that hands out ``incoming`` one by one (None: nothing within the timeout), then reports it closed."""

    def __init__(self, incoming=(), fail_send=False):
        self.incoming = list(incoming)
        self.sent = []
        self.closed = None
        self.fail_send = fail_send

    def receive(self, timeout=None):
        if not self.incoming:
            raise ConnectionClosed(1000, "gone")
        return self.incoming.pop(0)

    def send(self, text):
        if self.fail_send:
            raise ConnectionError("broken pipe")
        self.sent.append(text)

    def close(self, reason=None, message=None):
        self.closed = (reason, message)


TOKENS = {"good-7": "7", "good-8": "8"}


def kingdom_for_token(token):
    return TOKENS[token]  # KeyError for a bad token, as a forged or expired one raises


def hello(token):
    return json.dumps({"jwt": token})


def test_every_tab_of_a_kingdom_gets_a_push():
    registry = Registry()
    tabs = [FakeSocket(), FakeSocket()]
    for tab in tabs:
        registry.register("7", tab)

    assert registry.send("7", "hello") == 2
    assert all(tab.sent == ["hello"] for tab in tabs)


def test_a_socket_that_fails_is_dropped():
    registry = Registry()
    broken, fine = FakeSocket(fail_send=True), FakeSocket()
    registry.register("7", broken)
    registry.register("7", fine)

    assert registry.send("7", "hello") == 1
    assert registry.kingdom_sockets("7") == [fine]


def test_too_many_tabs_close_the_oldest():
    ticks = iter(range(100))
    registry = Registry(per_kingdom=2, clock=lambda: next(ticks))
    first, second, third = FakeSocket(), FakeSocket(), FakeSocket()
    for tab in (first, second, third):
        registry.register("7", tab)

    assert registry.kingdom_sockets("7") == [second, third]
    assert first.closed is not None


def test_the_process_cap_refuses_new_sockets():
    registry = Registry(total=1)
    assert registry.register("7", FakeSocket())
    assert not registry.register("8", FakeSocket())


def test_a_socket_without_a_valid_token_is_closed_and_never_registered():
    registry = Registry()
    for incoming in ([None], [hello("forged")], ["not json"]):
        ws = FakeSocket(incoming)
        serve(ws, registry, kingdom_for_token)
        assert ws.closed[0] == 1008
    assert len(registry) == 0


def test_a_registered_socket_is_removed_when_it_closes():
    registry = Registry()
    ws = FakeSocket([hello("good-7"), hello("good-7")])  # then the browser closes it

    serve(ws, registry, kingdom_for_token)

    assert len(registry) == 0


def test_a_quiet_socket_is_closed():
    registry = Registry()
    ws = FakeSocket([hello("good-7"), None, hello("good-7")])  # None: no message within the idle time

    serve(ws, registry, kingdom_for_token)

    assert ws.incoming == [hello("good-7")]  # it stopped at the silence
    assert len(registry) == 0 and ws.closed is not None


def test_a_new_kingdom_moves_the_socket():
    registry = Registry()
    seen = []

    class Watching(FakeSocket):
        def receive(self, timeout=None):
            seen.append(sorted(kd for kd in ("7", "8") if self in registry.kingdom_sockets(kd)))
            return super().receive(timeout)

    ws = Watching([hello("good-7"), hello("good-8")])
    serve(ws, registry, kingdom_for_token)

    assert seen[1:] == [["7"], ["8"]]  # after the first token it is kingdom 7's, after the second kingdom 8's


def test_invalid_tokens_keep_a_socket_only_until_the_idle_time(monkeypatch):
    import untitledapp.sockets as sockets
    now = [0.0]
    monkeypatch.setattr(sockets.time, "monotonic", lambda: now[0])
    registry = Registry()

    class Ageing(FakeSocket):
        def receive(self, timeout=None):
            now[0] += 100
            return super().receive(timeout)

    ws = Ageing([hello("good-7"), hello("expired"), hello("expired"), hello("expired"), hello("good-7")])
    serve(ws, registry, kingdom_for_token, idle_seconds=250)

    assert ws.incoming == [hello("good-7")]  # gave up after 300 s of invalid tokens
    assert len(registry) == 0
