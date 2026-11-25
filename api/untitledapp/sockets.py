"""
The open notification sockets of this process (``/ws/listen``), by kingdom.

Still the known gap in docs/status.md: a push only reaches sockets held by the process that sends it, which is fine
while production runs one process. Within that, this keeps the registry correct and bounded:

* a kingdom may have several sockets (two tabs, a phone and a laptop), and a push goes to all of them;
* a socket is registered only once it has sent a valid token, within ``AUTH_SECONDS`` of opening;
* it is removed when it closes, when a send to it fails, or when it has sent no valid token for ``IDLE_SECONDS``
  (the browser sends one every minute);
* there are at most ``PER_KINGDOM`` per kingdom (the oldest is closed for a new one) and ``TOTAL`` in all, because
  each open socket holds one of the web server's threads for as long as it is open;
* a socket holds its thread from the moment it opens, before it has sent a token, so at most ``PENDING`` may be
  waiting for one at a time, and one address may have at most ``PER_ADDRESS`` open, waiting or registered. Without
  these, opening sockets and never sending a token took every thread and stopped the site (issue #219). With them the
  sockets can hold at most ``TOTAL + PENDING`` threads, and the pages keep the rest.

The registry is one dict keyed by socket. Its single operations are atomic in CPython, and the sends iterate over a
copy, so concurrent request threads need no lock. The caps are checked without one, so a burst may pass them by a few.
"""
import json
import time

from flask_sock import ConnectionClosed

AUTH_SECONDS = 5  # the browser sends its token as soon as the socket opens
IDLE_SECONDS = 3 * 60
PER_KINGDOM = 5
TOTAL = 50  # of the web server's 100 threads (the gunicorn command in docs/deployment.md)
PENDING = 10  # sockets open but not yet sent a valid token
PER_ADDRESS = 10  # a household with a few players, each with a tab or two


class Registry:
    def __init__(self, per_kingdom=PER_KINGDOM, total=TOTAL, clock=time.monotonic, pending=PENDING,
                 per_address=PER_ADDRESS):
        self._sockets = {}  # ws -> (kd_id, registered at)
        self._open = {}  # ws -> address, for every socket from opening to closing, registered or not
        self.per_kingdom = per_kingdom
        self.total = total
        self.clock = clock
        self.pending = pending
        self.per_address = per_address

    def admit(self, ws, address):
        """
        Count ``ws`` as open, from ``address``. False if ``pending`` sockets are already waiting for a token, or the
        address already has ``per_address`` open. ``leave`` when it closes.
        """
        open_sockets = list(self._open.items())
        if sum(1 for other, _ in open_sockets if other not in self._sockets) >= self.pending:
            return False
        if address and sum(1 for _, other in open_sockets if other == address) >= self.per_address:
            return False
        self._open[ws] = address
        return True

    def leave(self, ws):
        self._open.pop(ws, None)
        self.unregister(ws)

    def kingdom_sockets(self, kd_id):
        """The kingdom's sockets, oldest first."""
        entries = [(at, ws) for ws, (kd, at) in list(self._sockets.items()) if kd == kd_id]
        return [ws for _, ws in sorted(entries, key=lambda entry: entry[0])]

    def __len__(self):
        return len(self._sockets)

    def register(self, kd_id, ws):
        """
        Map ``ws`` to ``kd_id`` (moving it if it was another kingdom's: the player made a new kingdom). False if the
        process has ``total`` sockets already. Closes the kingdom's oldest socket if this makes one too many.
        """
        if ws in self._sockets:
            self._sockets[ws] = (kd_id, self._sockets[ws][1])
            return True
        if len(self._sockets) >= self.total:
            return False
        self._sockets[ws] = (kd_id, self.clock())
        for old in self.kingdom_sockets(kd_id)[:-self.per_kingdom]:
            self.unregister(old)
            _close(old, 1008, "Too many open tabs")
        return True

    def unregister(self, ws):
        self._sockets.pop(ws, None)

    def send(self, kd_id, text):
        """Send ``text`` to every socket of the kingdom. One that fails is dropped. Returns how many it reached."""
        reached = 0
        for ws in self.kingdom_sockets(kd_id):
            try:
                ws.send(text)
                reached += 1
            except (ConnectionError, ConnectionClosed, OSError, StopIteration):
                self.unregister(ws)
        return reached


def _close(ws, reason, message):
    try:
        ws.close(reason=reason, message=message)
    except Exception:  # already closed, or the connection is gone
        pass


def _kingdom_of(data, kingdom_for_token):
    """The kingdom a ``{"jwt": ...}`` message is for, or None if the message or its token is not valid."""
    try:
        token = json.loads(data).get("jwt")
    except (TypeError, ValueError, AttributeError):
        return None
    if not token:
        return None
    try:
        return kingdom_for_token(token)
    except Exception:  # an expired, forged or malformed token, or a user without a kingdom
        return None


def serve(ws, registry, kingdom_for_token, logger=None, auth_seconds=AUTH_SECONDS, idle_seconds=IDLE_SECONDS,
          address=""):
    """
    Run one socket: wait for a valid token, register it, then keep it while valid tokens keep coming. Returns when the
    socket closes or goes quiet, having removed it. ``address`` is the caller's, for ``PER_ADDRESS``.
    """
    if not registry.admit(ws, address):
        if logger:
            logger.warning("Refused a notification socket before its token: %s open", len(registry._open))
        _close(ws, 1013, "Too many connections, try again later")
        return
    try:
        _serve(ws, registry, kingdom_for_token, logger, auth_seconds, idle_seconds)
    except ConnectionClosed:
        pass  # closed before it sent a token
    finally:
        registry.leave(ws)


def _serve(ws, registry, kingdom_for_token, logger, auth_seconds, idle_seconds):
    kd_id = _kingdom_of(ws.receive(timeout=auth_seconds), kingdom_for_token)
    if kd_id is None:
        _close(ws, 1008, "Send a valid token first")
        return
    if not registry.register(kd_id, ws):
        if logger:
            logger.warning("Refused a notification socket: %s open", len(registry))
        _close(ws, 1013, "Too many connections, try again later")
        return
    last_valid = time.monotonic()
    try:
        while True:
            data = ws.receive(timeout=idle_seconds)
            if data is None:
                break  # nothing for too long: the browser is gone without closing
            kingdom = _kingdom_of(data, kingdom_for_token)
            if kingdom is not None:
                last_valid = time.monotonic()
                if kingdom != kd_id:
                    kd_id = kingdom
                    registry.register(kd_id, ws)
            elif time.monotonic() - last_valid > idle_seconds:
                break  # only invalid tokens for too long: an expired login
    except ConnectionClosed:
        pass
    finally:
        registry.unregister(ws)
        _close(ws, 1000, "Bye")
