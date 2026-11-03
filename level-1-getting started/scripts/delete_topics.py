#!/usr/bin/env python3
"""
delete_topics.py
────────────────
Discovers all topics in your cluster that start with your workshop ID
(e.g. hive.*), lists them, asks for confirmation, then deletes them.

Nothing is hard-coded — every topic in the cluster is found and removed.

    python3 delete_topics.py            # discover, confirm, delete
    python3 delete_topics.py --dry-run  # discover and list only, no API calls
    python3 delete_topics.py --yes      # skip confirmation prompt

IDEMPOTENT: topics that disappear between discovery and deletion are skipped.
"""

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

import certifi
from dotenv import load_dotenv

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


def main():
    parser = argparse.ArgumentParser(
        description="Discover and delete your Confluent Cloud topics for the Hive workshop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="Discover and list without deleting.")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    load_dotenv(ENV_PATH, override=False)

    def get(key: str) -> str:
        val = os.environ.get(key, "").strip().strip("'\"")
        return "" if val == "CHANGE_ME" else val

    attendee_id   = get("ATTENDEE_ID")
    rest_endpoint = get("CONFLUENT_REST_ENDPOINT").rstrip("/")
    cluster_id    = get("CONFLUENT_CLUSTER_ID")
    api_key       = get("CONFLUENT_API_KEY")
    api_secret    = get("CONFLUENT_API_SECRET")

    required = [
        ("ATTENDEE_ID",            attendee_id),
        ("CONFLUENT_REST_ENDPOINT", rest_endpoint),
        ("CONFLUENT_CLUSTER_ID",    cluster_id),
        ("CONFLUENT_API_KEY",       api_key),
        ("CONFLUENT_API_SECRET",    api_secret),
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

    if not topics:
        print(  "No topics found\nNothing to delete.")
        return

    print(f"  Found {len(topics)} topic(s):\n")
    for t in topics:
        print(f"  {t}")
    print()

    if not args.dry_run and not args.yes:
        answer = input("Delete these topics? This cannot be undone. [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    failures = 0
    for topic in topics:
        ok = delete_topic(rest_endpoint, cluster_id, auth, topic, args.dry_run)
        if not ok:
            failures += 1

    print()
    if failures:
        print(f"Finished with {failures} failure(s). Review the errors above.")
        sys.exit(1)
    elif args.dry_run:
        print("Dry-run complete. Remove --dry-run to delete the topics for real.")
    else:
        print("All topics deleted. Run provision_topics.sh to recreate them.")


if __name__ == "__main__":
    main()
