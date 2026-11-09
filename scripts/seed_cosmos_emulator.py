"""Copy the Azure Cosmos dev container into the local Cosmos emulator.

Reads from Azure only; every write goes to the emulator. Credentials come from
funcapp/local.settings.json:
    AZURE_COSMOS_ENDPOINT / AZURE_COSMOS_KEY  source (Azure, read-only)
    COSMOS_ENDPOINT / COSMOS_KEY              destination (must be localhost)

Usage:
    python scripts/seed_cosmos_emulator.py            # report only, writes nothing
    python scripts/seed_cosmos_emulator.py --apply    # copy into the emulator
    python scripts/seed_cosmos_emulator.py --apply --replace
                                                      # overwrite a non-empty emulator
"""
import argparse
import json
import pathlib
import sys
from urllib.parse import urlparse

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError

SETTINGS = pathlib.Path(__file__).resolve().parent.parent / "funcapp" / "local.settings.json"
SYSTEM_FIELDS = ("_rid", "_self", "_etag", "_attachments", "_ts")
LOCAL_HOSTS = ("localhost", "127.0.0.1")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write to the emulator")
    parser.add_argument("--replace", action="store_true", help="allow overwriting existing emulator data")
    args = parser.parse_args()

    values = json.loads(SETTINGS.read_text(encoding="utf-8"))["Values"]
    db_name = values.get("COSMOS_DATABASE_NAME", "dev")
    container_name = values.get("COSMOS_CONTAINER_NAME", "test")
    dest_url = values["COSMOS_ENDPOINT"]

    if urlparse(dest_url).hostname not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: destination {urlparse(dest_url).hostname} is not localhost.")

    source = CosmosClient(url=values["AZURE_COSMOS_ENDPOINT"], credential=values["AZURE_COSMOS_KEY"])
    source_container = source.get_database_client(db_name).get_container_client(container_name)
    partition_path = source_container.read()["partitionKey"]["paths"][0]
    documents = list(source_container.read_all_items())

    print(f"source: {db_name}/{container_name}, partition key {partition_path}, {len(documents)} documents")
    for doc in sorted(documents, key=lambda d: d["id"]):
        print(f"  {doc['id']:<40} {len(json.dumps(doc)):>10,} bytes")

    if not args.apply:
        print("Report only. Re-run with --apply to copy into the emulator.")
        return

    # The emulator uses a self-signed certificate and never leaves this machine.
    dest = CosmosClient(url=dest_url, credential=values["COSMOS_KEY"], connection_verify=False)
    dest_db = dest.create_database_if_not_exists(id=db_name)
    dest_container = dest_db.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path=partition_path),
        offer_throughput=4000,  # the emulator default of 400 RU/s throttles concurrent tests and probes
    )

    try:
        existing = list(dest_container.read_all_items())
    except CosmosResourceNotFoundError:
        existing = []
    if existing and not args.replace:
        sys.exit(f"Emulator already holds {len(existing)} documents. Pass --replace to overwrite them.")

    for doc in documents:
        dest_container.upsert_item({k: v for k, v in doc.items() if k not in SYSTEM_FIELDS})

    copied = sum(1 for _ in dest_container.read_all_items())
    print(f"emulator now holds {copied} documents")
    if copied != len(documents):
        sys.exit("Document count does not match the source.")


if __name__ == "__main__":
    main()
