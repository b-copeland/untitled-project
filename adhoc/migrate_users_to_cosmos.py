"""Copy the users from the `accounts` document (or a SQLite file) into user_<id>, username_<key> and user_counter.

One-off, for the move of users out of SQLite (docs/decisions/0004-users-in-cosmos.md). Run it in the function app's
environment (it needs azure-cosmos). Credentials come from the environment (COSMOS_ENDPOINT, COSMOS_KEY,
COSMOS_DATABASE_NAME, COSMOS_CONTAINER_NAME) or, failing that, funcapp/local.settings.json. The key is never printed.

    python adhoc/migrate_users_to_cosmos.py                      # dry run against the emulator: says what it would do
    python adhoc/migrate_users_to_cosmos.py --apply              # write to the emulator
    python adhoc/migrate_users_to_cosmos.py --sqlite path/to.db  # read users from a SQLite file instead
    python adhoc/migrate_users_to_cosmos.py --production --apply # a non-localhost endpoint: the maintainer only

Idempotent: a user or name claim that is already stored as the source says is left alone, so running it twice writes
nothing the second time. A stored document that *differs* from the source is reported and left alone unless
--overwrite is given. Expect one such difference in production: Flask creates an `admin` user at start-up when it finds
none, so after the deploy and before this runs there is a second admin holding the name. --overwrite gives the name
to the source's admin and removes the other. Users the source does not know, with names it does not have, are
sign-ups made after the switch and are kept. The counter is only ever raised, to one past the highest id.

Exits with status 1 if it found problems (two users with one name or one id, or stored documents that differ and
were not overwritten), so a dry run is a check.
"""
import argparse
import json
import os
import pathlib
import sqlite3
import sys
from urllib.parse import urlparse

SETTINGS = pathlib.Path(__file__).resolve().parent.parent / "funcapp" / "local.settings.json"
SYSTEM_FIELDS = ("_rid", "_self", "_etag", "_attachments", "_ts")
LOCAL_HOSTS = ("localhost", "127.0.0.1")

# The fields of a user document (api/untitledapp/users.py FIELDS), and how to read each one from the source.
BOOLEAN_FIELDS = ("kd_created", "is_active", "is_verified", "email_verified")
FIELD_DEFAULTS = {
    "username": None,
    "password": None,
    "roles": "",
    "kd_id": None,
    "kd_created": False,
    "kd_death_date": None,
    "is_active": True,
    "is_verified": True,
    "email": None,
    "email_verified": False,
}


def username_key(username):
    """As users.username_key: lowercase hex of the UTF-8 bytes."""
    return username.encode("utf-8").hex()


def _settings():
    values = {}
    if SETTINGS.exists():
        values = json.loads(SETTINGS.read_text(encoding="utf-8")).get("Values", {})
    names = ("COSMOS_ENDPOINT", "COSMOS_KEY", "COSMOS_DATABASE_NAME", "COSMOS_CONTAINER_NAME")
    found = {name: os.environ.get(name) or values.get(name) for name in names}
    found["COSMOS_DATABASE_NAME"] = found["COSMOS_DATABASE_NAME"] or "dev"
    found["COSMOS_CONTAINER_NAME"] = found["COSMOS_CONTAINER_NAME"] or "test"
    missing = [name for name in ("COSMOS_ENDPOINT", "COSMOS_KEY") if not found[name]]
    if missing:
        sys.exit(f"Missing settings: {', '.join(missing)}")
    return found


def _container(settings):
    from azure.cosmos import CosmosClient

    local = urlparse(settings["COSMOS_ENDPOINT"]).hostname in LOCAL_HOSTS
    # The emulator uses a self-signed certificate and never leaves this machine.
    if local:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    client = CosmosClient(settings["COSMOS_ENDPOINT"], credential=settings["COSMOS_KEY"], connection_verify=not local)
    return client.get_database_client(settings["COSMOS_DATABASE_NAME"]).get_container_client(
        settings["COSMOS_CONTAINER_NAME"]
    )


def _normalise(row):
    """A source row as a user document's fields, with id_number. Missing fields get the defaults users.py uses."""
    user = {field: row.get(field, default) for field, default in FIELD_DEFAULTS.items()}
    for field in BOOLEAN_FIELDS:
        if user[field] is not None:
            user[field] = bool(user[field])  # SQLite stores 0 and 1
    if user["kd_id"] is not None:
        user["kd_id"] = str(user["kd_id"])  # kingdom ids are strings
    user["id_number"] = int(row["id"])
    return user


def read_accounts_document(container):
    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    try:
        accounts = container.read_item("accounts", partition_key="accounts")
    except CosmosResourceNotFoundError:
        sys.exit("There is no accounts document to read users from.")
    return accounts.get("accounts", [])


def read_sqlite(path):
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute("SELECT * FROM user")]
    finally:
        connection.close()


def check_source(users):
    """Problems that make the source ambiguous: two users with one id or one name."""
    problems = []
    by_id, by_name = {}, {}
    for user in users:
        if user["username"] is None or user["username"] == "":
            problems.append(f"user {user['id_number']} has no username")
            continue
        if user["id_number"] in by_id:
            problems.append(f"id {user['id_number']} is used by {by_id[user['id_number']]!r} and {user['username']!r}")
        by_id[user["id_number"]] = user["username"]
        if user["username"] in by_name:
            problems.append(f"username {user['username']!r} is used by ids {by_name[user['username']]} and {user['id_number']}")
        by_name[user["username"]] = user["id_number"]
    lower = {}
    for name in by_name:
        lower.setdefault(name.lower(), []).append(name)
    notes = [f"names that differ only in case (allowed, lookups are case-sensitive): {names}"
             for names in lower.values() if len(names) > 1]
    return problems, notes


def _stored(container, item_id):
    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    try:
        document = container.read_item(item_id, partition_key=item_id)
    except CosmosResourceNotFoundError:
        return None
    return {key: value for key, value in document.items() if key not in SYSTEM_FIELDS}


def plan(container, users):
    """The writes needed, as (item id, document, reason), and the differences that need --overwrite."""
    writes, conflicts = [], []
    for user in users:
        if not user["username"]:
            continue
        wanted = {"id": f"user_{user['id_number']}", **user}
        stored = _stored(container, wanted["id"])
        if stored is None:
            writes.append((wanted["id"], wanted, "new"))
        elif stored != wanted:
            changed = sorted(key for key in set(stored) | set(wanted) if stored.get(key) != wanted.get(key))
            conflicts.append((wanted["id"], wanted, f"stored user differs in {changed}"
                              f" (stored name {stored.get('username')!r}, source {user['username']!r})"))

        claim = {"id": f"username_{username_key(user['username'])}", "user_id": user["id_number"]}
        stored = _stored(container, claim["id"])
        if stored is None:
            writes.append((claim["id"], claim, f"claim {user['username']!r}"))
        elif stored != claim:
            conflicts.append((claim["id"], claim, f"{user['username']!r} is claimed by id {stored.get('user_id')},"
                              f" source says {user['id_number']}"))

    # Users in the target that the source does not have. One with a name the source also has was made before the
    # migration ran (the admin Flask creates at start-up when it finds none): the source's user takes the name, so it
    # can never be reached again. Anything else is a sign-up made after the switch, and stays.
    source_ids = {user["id_number"] for user in users}
    source_names = {user["username"] for user in users}
    target_ids = []
    for document in container.query_items(
        "SELECT c.id, c.id_number, c.username FROM c WHERE IS_DEFINED(c.id_number)", enable_cross_partition_query=True,
    ):
        target_ids.append(document["id_number"])
        if document["id_number"] in source_ids:
            continue
        if document.get("username") in source_names:
            conflicts.append((document["id"], None, f"made before the migration as {document['username']!r};"
                              f" the source's {document['username']!r} replaces it (removed with --overwrite)"))
        else:
            print(f"  keep  {document['id']:<60} {document.get('username')!r} signed up after the switch")

    next_id = max(list(source_ids) + target_ids, default=0) + 1
    stored = _stored(container, "user_counter")
    if stored is None or stored.get("next_id", 0) < next_id:
        reason = f"next_id {stored.get('next_id') if stored else None} -> {next_id}"
        writes.append(("user_counter", {"id": "user_counter", "next_id": next_id}, reason))
    return writes, conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the documents (default: dry run)")
    parser.add_argument("--sqlite", metavar="PATH", help="read users from this SQLite file, not the accounts document")
    parser.add_argument("--production", action="store_true", help="allow an endpoint that is not localhost")
    parser.add_argument("--overwrite", action="store_true", help="replace stored documents that differ from the source")
    args = parser.parse_args()

    settings = _settings()
    host = urlparse(settings["COSMOS_ENDPOINT"]).hostname
    if host not in LOCAL_HOSTS and not args.production:
        sys.exit(f"Refusing to run: {host} is not the emulator. Pass --production if that is really what you mean.")
    print(f"target: {host} {settings['COSMOS_DATABASE_NAME']}/{settings['COSMOS_CONTAINER_NAME']}")

    container = _container(settings)
    rows = read_sqlite(args.sqlite) if args.sqlite else read_accounts_document(container)
    users = sorted((_normalise(row) for row in rows), key=lambda user: user["id_number"])
    print(f"source: {'SQLite ' + args.sqlite if args.sqlite else 'the accounts document'}, {len(users)} users")

    problems, notes = check_source(users)
    for note in notes:
        print(f"  note: {note}")
    for problem in problems:
        print(f"  PROBLEM: {problem}")
    if problems:
        sys.exit("Fix the source first: these users would collide.")

    writes, conflicts = plan(container, users)
    for item_id, _, reason in writes:
        print(f"  write {item_id:<60} {reason}")
    for item_id, _, reason in conflicts:
        print(f"  {'OVERWRITE' if args.overwrite else 'DIFFERS  '} {item_id:<56} {reason}")
    if args.overwrite:
        writes += conflicts
        conflicts = []
    if not writes:
        print("Nothing to write: the users are already migrated.")

    if not args.apply:
        print(f"Dry run: {len(writes)} documents would be written. Re-run with --apply to write them.")
    else:
        for item_id, document, _ in writes:
            if document is None:
                container.delete_item(item_id, partition_key=item_id)
            else:
                container.upsert_item(document)
        print(f"Wrote {len(writes)} documents.")
    if conflicts:
        print(f"{len(conflicts)} stored documents differ from the source and were left alone (--overwrite replaces them).")
        sys.exit(1)


if __name__ == "__main__":
    main()
