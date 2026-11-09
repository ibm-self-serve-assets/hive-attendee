#!/usr/bin/env python3
"""
delete_topics_and_schemas.py
────────────────────────────
Deletes everything Level 1 created in YOUR Confluent Cloud, so you can start again:

  1. every topic in your Kafka cluster (nothing is hard-coded; all topics found are removed), and
  2. the Schema Registry subjects that belong to those topics and to the Hive event topics
     (<topic>-value and <topic>-key), first soft, then permanently, so that
     register_schemas.py starts again from version 1.

Both halves are deleted together on purpose. Records already in a topic point at schema ids,
and a schema left behind meets a new registration with stale versions.

It lists what it found and asks for confirmation before deleting anything.

NEEDS in spec-shared/.env: ATTENDEE_ID, CONFLUENT_REST_ENDPOINT, CONFLUENT_CLUSTER_ID,
KAFKA_CLUSTER_API_KEY, KAFKA_CLUSTER_API_SECRET, SCHEMA_REGISTRY_URL, SCHEMA_REGISTRY_API_KEY,
SCHEMA_REGISTRY_API_SECRET. SIMULATION_SERVER_URL, WORKSHOP_ACCESS_TOKEN are used to find the
subjects of Hive topics that are already deleted; without the server only the subjects of
topics that still exist are found.

    python3 delete_topics_and_schemas.py            # discover, confirm, delete
    python3 delete_topics_and_schemas.py --dry-run  # discover and list only, nothing is deleted
    python3 delete_topics_and_schemas.py --yes      # skip confirmation prompt

Afterwards run provision_topics.sh, then register_schemas.sh, to recreate them.

IDEMPOTENT: topics and subjects that disappear between discovery and deletion are skipped.
"""

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import certifi
from dotenv import load_dotenv

from sim_server import fetch_schemas

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# Load from spec-shared/.env first; fall back to a local .env if not found.
_SPEC_DIR = Path(__file__).resolve().parent
_SHARED_ENV = _SPEC_DIR.parent.parent / "spec-shared" / ".env"
ENV_PATH = _SHARED_ENV if _SHARED_ENV.exists() else _SPEC_DIR / ".env"


def _auth_header(api_key: str, api_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()


def list_topics(rest_endpoint: str, cluster_id: str, auth: str) -> list[str]:
    """
    Fetch all topics from the cluster.
    Uses the Confluent Admin REST API v3 topic list endpoint.
    Follows next_cursor pagination if present.
    """
    found = []
    url = f"{rest_endpoint}/kafka/v3/clusters/{cluster_id}/topics"

    while url:
        req = urllib.request.Request(url, headers={"Authorization": auth})
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            print(f"ERROR listing topics (HTTP {e.code}): {raw.decode(errors='replace')}")
            sys.exit(1)
        except Exception as ex:
            print(f"ERROR listing topics: {ex}")
            sys.exit(1)

        for item in body.get("data", []):
            found.append(item.get("topic_name", ""))

        # Follow pagination cursor if present
        next_cursor = body.get("metadata", {}).get("next", None)
        url = next_cursor if next_cursor else None

    return sorted(found)


def delete_topic(
    rest_endpoint: str,
    cluster_id: str,
    auth: str,
    topic_name: str,
    dry_run: bool,
) -> bool:
    if dry_run:
        print(f"  [dry-run] {topic_name}")
        return True

    url = f"{rest_endpoint}/kafka/v3/clusters/{cluster_id}/topics/{topic_name}"
    req = urllib.request.Request(url, headers={"Authorization": auth}, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            if resp.getcode() in (200, 204):
                print(f"  ✓ Deleted  {topic_name}")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  ~ Missing  {topic_name}  (already gone)")
            return True
        raw = e.read()
        print(f"  ✗ Failed   {topic_name}  (HTTP {e.code}: {raw.decode(errors='replace')})")
        return False
    except Exception as ex:
        print(f"  ✗ Failed   {topic_name}  ({ex})")
        return False
    return False


def _sr_request(method: str, url: str, auth: str):
    """One Schema Registry request. Returns (status, parsed body); network failures return (0, message)."""
    req = urllib.request.Request(
        url, headers={"Authorization": auth, "Accept": "application/vnd.schemaregistry.v1+json"}, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
            return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as ex:
        return 0, str(ex)


def _event_topic_names(server_url: str, token: str, attendee_id: str) -> list[str]:
    """
    The 17 event topics from the Simulation server, so their subjects are also found when the
    topics are already gone. If the server cannot be reached, only the subjects of topics that
    still exist are found, and a note says so.
    """
    if not (server_url and token and attendee_id):
        print("  Note: SIMULATION_SERVER_URL, WORKSHOP_ACCESS_TOKEN or ATTENDEE_ID is not set, so subjects")
        print("  of topics that are already deleted will not be found.")
        return []
    try:
        return [s["topic"] for s in fetch_schemas(server_url, token, attendee_id)]
    except RuntimeError as e:
        print(f"  Note: {e}")
        print("  Subjects of topics that are already deleted will not be found.")
        return []


def subjects_for_topics(topics: list[str], sr_url: str, auth: str, event_topics: list[str]) -> list[str]:
    """Registered subjects named <topic>-value or <topic>-key for the given topics and the event topics."""
    status, body = _sr_request("GET", f"{sr_url}/subjects", auth)
    if status != 200 or not isinstance(body, list):
        print(f"ERROR listing subjects (HTTP {status}): {body}")
        sys.exit(1)
    names = set(topics) | set(event_topics)
    wanted = {f"{t}-value" for t in names} | {f"{t}-key" for t in names}
    return sorted(s for s in body if s in wanted)


def delete_subject(sr_url: str, auth: str, subject: str, dry_run: bool) -> bool:
    """Soft delete, then permanent delete (a permanent delete is only accepted after a soft one)."""
    if dry_run:
        print(f"  [dry-run] {subject}")
        return True
    quoted = urllib.parse.quote(subject, safe="")
    status, body = _sr_request("DELETE", f"{sr_url}/subjects/{quoted}", auth)
    if status == 404:
        print(f"  ~ Missing  {subject}  (already gone)")
        return True
    if status != 200:
        print(f"  ✗ Failed   {subject}  (soft delete HTTP {status}: {body})")
        return False
    status, body = _sr_request("DELETE", f"{sr_url}/subjects/{quoted}?permanent=true", auth)
    if status not in (200, 404):
        print(f"  ✗ Failed   {subject}  (permanent delete HTTP {status}: {body})")
        return False
    print(f"  ✓ Deleted  {subject}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Delete your Confluent Cloud topics and their Schema Registry subjects for the Hive workshop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="Discover and list topics and subjects without deleting.")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    load_dotenv(ENV_PATH, override=False)

    def get(key: str) -> str:
        val = os.environ.get(key, "").strip().strip("'\"")
        return "" if val == "CHANGE_ME" else val

    attendee_id   = get("ATTENDEE_ID")
    server_url    = get("SIMULATION_SERVER_URL").rstrip("/")
    token         = get("WORKSHOP_ACCESS_TOKEN")
    rest_endpoint = get("CONFLUENT_REST_ENDPOINT").rstrip("/")
    cluster_id    = get("CONFLUENT_CLUSTER_ID")
    api_key       = get("KAFKA_CLUSTER_API_KEY")
    api_secret    = get("KAFKA_CLUSTER_API_SECRET")
    sr_url        = get("SCHEMA_REGISTRY_URL").rstrip("/")
    sr_key        = get("SCHEMA_REGISTRY_API_KEY")
    sr_secret     = get("SCHEMA_REGISTRY_API_SECRET")

    required = [
        ("ATTENDEE_ID",            attendee_id),
        ("CONFLUENT_REST_ENDPOINT", rest_endpoint),
        ("CONFLUENT_CLUSTER_ID",    cluster_id),
        ("KAFKA_CLUSTER_API_KEY",       api_key),
        ("KAFKA_CLUSTER_API_SECRET",    api_secret),
        ("SCHEMA_REGISTRY_URL",         sr_url),
        ("SCHEMA_REGISTRY_API_KEY",     sr_key),
        ("SCHEMA_REGISTRY_API_SECRET",  sr_secret),
    ]

    missing = [name for name, val in required if not val]
    if missing:
        print("ERROR: the following values are missing or still set to CHANGE_ME in .env:")
        for name in missing:
            print(f"  {name}=...")
        print(f"\nEdit {ENV_PATH} and fill in the values, then retry.")
        sys.exit(1)

    auth   = _auth_header(api_key, api_secret)

    print(f"Attendee : {attendee_id}")
    print(f"Cluster  : {cluster_id}")
    print(f"Endpoint : {rest_endpoint}")
    if args.dry_run:
        print("Mode     : dry-run — no deletions will be made")
    print()
    print("Discovering topics…")

    topics = list_topics(rest_endpoint, cluster_id, auth)

    print("Discovering Schema Registry subjects…")
    sr_auth = _auth_header(sr_key, sr_secret)
    event_topics = _event_topic_names(server_url, token, attendee_id)
    subjects = subjects_for_topics(topics, sr_url, sr_auth, event_topics)

    if not topics and not subjects:
        print("No topics or Schema Registry subjects found.\nNothing to delete.")
        return

    print(f"\n  Found {len(topics)} Kafka topic(s):\n")
    for t in topics:
        print(f"  {t}")
    print(f"\n  Found {len(subjects)} schema subject(s) in Schema Registry")
    print("  (each <topic>-value subject holds the schema for that topic's events):\n")
    for s in subjects:
        print(f"  {s}")
    print()

    if not args.dry_run and not args.yes:
        answer = input("Delete these topics AND subjects? This cannot be undone. [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    failures = 0
    print("== Deleting Kafka topics ==")
    for topic in topics:
        ok = delete_topic(rest_endpoint, cluster_id, auth, topic, args.dry_run)
        if not ok:
            failures += 1
    print()
    print("== Deleting schemas (Schema Registry subjects, named <topic>-value) ==")
    for subject in subjects:
        if not delete_subject(sr_url, sr_auth, subject, args.dry_run):
            failures += 1

    print()
    if failures:
        print(f"Finished with {failures} failure(s). Review the errors above.")
        sys.exit(1)
    elif args.dry_run:
        print("Dry-run complete. Remove --dry-run to delete the topics and subjects for real.")
    else:
        print("All topics and Schema Registry subjects deleted. Run provision_topics.sh, then register_schemas.sh, to recreate them.")


if __name__ == "__main__":
    main()
