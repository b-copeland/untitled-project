"""One simulated round on several processes: ``simulate_round.py --workers N``.

A round's state is one store of documents. Here it lives in a process of its own (``serve_store``), and every other
process talks to it through ``RemoteContainer``, which has the part of the Cosmos container API the function app uses.
The store only reads and writes documents (and checks a write's version, as Cosmos does); everything expensive (the
function app's handlers and their JSON, the refresh, the bots' thinking) runs in the processes that call it.

Each tick, the main process runs the start of the refresh (elections, the history mark), hands the kingdoms out in
slices to the workers, which refresh them at the same time, and runs the end (scores, empires, clusters). The game's
writes are all version-checked (``occ.update``), so workers touching the same document at once is what the real game
does with several web app instances.

What is lost: the order of the writes within a tick now depends on timing, so a seed no longer plays exactly the same
round twice. Compare variants over more seeds.
"""
import collections
import copy
import multiprocessing
import multiprocessing.connection
import os
import pathlib
import pickle
import random
import sys
import threading
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

_ERRORS = {"412": "CosmosAccessConditionFailedError", "409": "CosmosResourceExistsError",
           "404": "CosmosResourceNotFoundError"}


# --- the store's process ---------------------------------------------------------------------------------------------

def serve_store(address, authkey, ready, shard=0):
    """
    Hold the round's documents and answer every process's calls, one connection per thread. A document is kept as the
    pickled bytes its writer sent, with its version (``_etag``) beside it, so the store never copies, parses or
    pickles a document itself: that work is done in the callers, at the same time. Only a write's version check and
    the new version happen here, under one lock.
    """
    docs = {}  # id -> (pickled body, etag)
    version = [0]
    lock = threading.Lock()

    def answer(message):
        op = message[0]
        if op == "read":
            entry = docs.get(message[1])
            return ("ok", entry) if entry else ("404", f"{message[1]} does not exist")
        if op == "create":
            _, item, blob = message
            with lock:
                if item in docs:
                    return "409", f"{item} already exists"
                version[0] += 1
                etag = f'"{shard}-{version[0]}"'
                docs[item] = (blob, etag)
            return "ok", etag
        if op == "replace":
            _, item, blob, if_match = message
            with lock:
                if item not in docs:
                    return "404", f"{item} does not exist"
                if if_match and if_match != docs[item][1]:
                    return "412", "The document changed"
                version[0] += 1
                etag = f'"{shard}-{version[0]}"'
                docs[item] = (blob, etag)
            return "ok", etag
        if op == "delete":
            with lock:
                if docs.pop(message[1], None) is None:
                    return "404", f"{message[1]} does not exist"
            return "ok", None
        if op == "all":
            with lock:
                return "ok", list(docs.values())
        return "error", f"unknown operation {op}"

    def handle(connection):
        try:
            while True:
                connection.send(answer(connection.recv()))
        except (EOFError, ConnectionError, OSError):
            pass

    listener = multiprocessing.connection.Listener(address, authkey=authkey)
    ready.set()
    while True:
        connection = listener.accept()
        threading.Thread(target=handle, args=(connection,), daemon=True).start()


_SYSTEM = ("_etag", "_ts", "_rid", "_self", "_attachments")


class RemoteContainer:
    """
    The container API the function app uses (as ``tests/fake_backend.FakeContainer`` has it), answered by the store's
    process. Documents are pickled and unpickled here, in the caller. One connection per process.
    """

    def __init__(self, addresses, authkey):
        # One connection to each shard of the store; a document always lives on the same one.
        self._connections = [multiprocessing.connection.Client(address, authkey=authkey) for address in addresses]
        self._locks = [threading.Lock() for _ in addresses]

    def _shard(self, item):
        return zlib.crc32(str(item).encode()) % len(self._connections)

    def _call(self, *message, shard=None):
        from azure.cosmos import exceptions

        index = self._shard(message[1]) if shard is None else shard
        with self._locks[index]:
            self._connections[index].send(message)
            code, value = self._connections[index].recv()
        if code == "ok":
            return value
        if code in _ERRORS:
            raise getattr(exceptions, _ERRORS[code])(status_code=int(code), message=value)
        raise RuntimeError(f"store: {value}")

    @staticmethod
    def _open(entry):
        blob, etag = entry
        doc = pickle.loads(blob)
        doc["_etag"] = etag
        return doc

    @staticmethod
    def _pack(body, item):
        doc = {key: value for key, value in body.items() if key not in _SYSTEM}
        doc["id"] = item
        return doc, pickle.dumps(doc, protocol=pickle.HIGHEST_PROTOCOL)

    def read_item(self, item, partition_key=None, **kwargs):
        return self._open(self._call("read", item))

    def create_item(self, body, **kwargs):
        doc, blob = self._pack(body, body["id"])
        etag = self._call("create", body["id"], blob)
        return self._open((blob, etag))

    def replace_item(self, item, body, **kwargs):
        from azure.core import MatchConditions

        if_match = kwargs.get("etag") if kwargs.get("match_condition") == MatchConditions.IfNotModified else None
        doc, blob = self._pack(body, item)
        etag = self._call("replace", item, blob, if_match)
        return self._open((blob, etag))

    def delete_item(self, item, partition_key=None, **kwargs):
        self._call("delete", item)

    def read_all_items(self, **kwargs):
        return [self._open(entry) for shard in range(len(self._connections)) for entry in self._call("all", shard=shard)]

    def query_items(self, query, parameters=None, **kwargs):
        # Rare (the function app sends one kind of query): every document, matched here as the fake container does.
        sys.path.insert(0, str(ROOT))
        from tests import fake_backend

        local = fake_backend.FakeContainer()
        local.docs = {doc["id"]: doc for doc in self.read_all_items()}
        return local.query_items(query, parameters=parameters)

    def doc(self, item):
        """A document as stored, or {} if there is none: for the simulation's own reports."""
        try:
            return self.read_item(item)
        except Exception:  # noqa: BLE001: not found
            return {}


def start_store(shards=1):
    """Start the store, in ``shards`` processes. Returns ``(processes, addresses, authkey)``."""
    authkey = os.urandom(16)
    processes, addresses = [], []
    for shard in range(shards):
        with multiprocessing.connection.Listener(("127.0.0.1", 0)) as probe:
            address = probe.address  # a free port, released for the store to take
        ready = multiprocessing.Event()
        process = multiprocessing.Process(target=serve_store, args=(address, authkey, ready, shard), daemon=True)
        process.start()
        ready.wait(60)
        processes.append(process)
        addresses.append(address)
    return processes, addresses, authkey


# --- a worker --------------------------------------------------------------------------------------------------------

def worker_main(connection, address, authkey, options):
    """Set up the game against the shared store, then refresh the chunks of kingdoms the main process sends."""
    import simulate_round

    sim = simulate_round.Simulation.worker(RemoteContainer(address, authkey), options)
    import untitledapp.refresh as refresh

    import untitledapp.request_cache as request_cache

    # A tick is one request, as the refresh route is: the shared documents (state, galaxies, empires, the kingdom
    # list) are read once a tick per worker and cached, and the refresh's own per-tick context too.
    request, context, context_tick = None, None, None
    while True:
        message = connection.recv()
        if message is None:
            return
        now, tick, kd_ids, seed = message
        sim.clock.now = now
        random.seed(seed)
        sim.errors.clear()
        sim.calls.clear()
        if context_tick != now:
            if request is not None:
                request_cache.end()
                request.pop()
            request = sim.app.test_request_context()
            request.push()
            request_cache.start()
            context, context_tick = refresh._RefreshContext(tick["state"]), now
        scores, failed = refresh._refresh_kingdoms(kd_ids, tick, context)
        refresh._record_ended_intel(context)
        connection.send((scores, failed, dict(sim.errors), dict(sim.calls)))


class Workers:
    """``count`` worker processes, each with a pipe to this one."""

    CHUNK = 3  # kingdoms per message: small, so a worker whose bots think a lot does not hold up the tick

    def __init__(self, count, address, authkey, options):
        self.pipes = []
        self.processes = []
        for _ in range(count):
            here, there = multiprocessing.Pipe()
            process = multiprocessing.Process(target=worker_main, args=(there, address, authkey, options), daemon=True)
            process.start()
            self.pipes.append(here)
            self.processes.append(process)

    def refresh(self, now, tick, kd_ids, seed):
        """
        Refresh ``kd_ids`` on the workers: a chunk to each, then the next chunk to whichever is free first. Returns
        ``(scores, failed, errors, calls)``, summed.
        """
        chunks = [kd_ids[index:index + self.CHUNK] for index in range(0, len(kd_ids), self.CHUNK)]
        scores, failed = {}, []
        errors, calls = collections.Counter(), collections.Counter()
        busy = set()
        sent = 0

        def send(pipe):
            nonlocal sent
            pipe.send((now, tick, chunks[sent], f"{seed}:{sent}"))
            sent += 1
            busy.add(pipe)

        for pipe in self.pipes:
            if sent < len(chunks):
                send(pipe)
        while busy:
            for pipe in multiprocessing.connection.wait(list(busy)):
                busy.discard(pipe)
                part_scores, part_failed, part_errors, part_calls = pipe.recv()
                scores.update(part_scores)
                failed.extend(part_failed)
                errors.update(part_errors)
                calls.update(part_calls)
                if sent < len(chunks):
                    send(pipe)
        return scores, failed, errors, calls

    def close(self):
        for pipe in self.pipes:
            try:
                pipe.send(None)
            except OSError:
                pass
        for process in self.processes:
            process.join(5)
