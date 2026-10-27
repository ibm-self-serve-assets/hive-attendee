#!/usr/bin/env python3
"""
provision_topics.py
───────────────────
Creates your Kafka topics before you register your simulation.  Uses the topics located in [spec-shared/schemas/event_payloads.json](../../spec-shared/schemas/event_payloads.json).

The Simulation server publishes events to these topics as your Simulation runs.
Topics must exist before you call /v1/simulations — the server verifies them
at registration time and will reject your request if any are missing.

State topic (compact policy, infinite retention):
simulation-state             — full Simulation snapshot (lifecycle, inventory, stations)

WHY COMPACT FOR FACTORY-STATE?
  Log compaction keeps only the most recent message per key. This means your
  local consumer can always replay from offset 0 and land on current state
  in a single pass — no matter how long the Simulation has been running.

IDEMPOTENT: running this script twice is safe. Existing topics are left
unchanged and reported as "~ Exists" rather than causing an error.

USAGE:
  # 1. Fill in your .env (same directory as this script):
  #
  #    CONFLUENT_REST_ENDPOINT=https://pkc-xxxxx.us-west-2.aws.confluent.cloud
  #      → Confluent Cloud → Cluster → Cluster Settings → Endpoints → REST endpoint
  #
  #    CONFLUENT_CLUSTER_ID=lkc-xxxxxx
  #      → Confluent Cloud → Cluster → Cluster Settings → General → Cluster ID
  #
  #    CONFLUENT_API_KEY=...   CONFLUENT_API_SECRET=...
  #      → Confluent Cloud → Cluster → API Keys → Add key → My account

  # 2. Preview what will be created (no API calls):
  python3 provision_topics.py --dry-run

  # 3. Create your topics:
  python3 provision_topics.py
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
from typing import List, Tuple

import certifi
from dotenv import load_dotenv

# Use certifi's CA bundle so urllib works on macOS without the
# "Install Certificates.command" step or any system keychain config.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# ── Paths ─────────────────────────────────────────────────────────────────────
# .env is now shared across specs — look in spec-shared/ first, then fall back
# to this script's own directory for local overrides.
_SPEC_DIR = Path(__file__).resolve().parent
_SHARED_ENV = _SPEC_DIR.parent.parent / "spec-shared" / ".env"
ENV_PATH = _SHARED_ENV if _SHARED_ENV.exists() else _SPEC_DIR / ".env"

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "spec-shared" / "schemas" / "event_payloads.json"

# ── Topic configuration ───────────────────────────────────────────────────────
# Activity events: keep for 24 hours then discard.
# This is enough time for a workshop session and keeps storage costs low.
ACTIVITY_CONFIG = {
    "cleanup.policy": "delete",
    "retention.ms": str(24 * 60 * 60 * 1000),
}

# Simulation state: compact — broker retains only the latest message per key.
# Your local consumer replays from offset 0 on every restart to rebuild
# current state without needing any external database.
STATE_CONFIG = {
    "cleanup.policy": "compact",
    "retention.ms": "-1",   # -1 = no time-based deletion; compaction handles cleanup
}

def _load_topics() -> List[Tuple[str, dict]]:
    """
    Derive topic names from spec-shared/schemas/event_payloads.json.
    Keys in ``topics`` use dot-notation (e.g. ``gathering.started``);
    topic names use hyphens (``gathering-started``).
    ``simulation.state`` gets the compact/infinite-retention policy;
    all others get the delete/24 h policy.
    """
    with _SCHEMA_PATH.open() as fh:
        schema = json.load(fh)
    return [
        (
            key.replace(".", "-"),
            STATE_CONFIG if key == "simulation.state" else ACTIVITY_CONFIG,
        )
        for key in schema["topics"]
    ]


# Each tuple is (topic name, config), derived from the shared schema.
TOPICS = _load_topics()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth_header(api_key: str, api_secret: str) -> str:
    """Build the HTTP Basic Authorization header from an API key + secret pair."""
    return "Basic " + base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()


def create_topic(
    rest_endpoint: str,
    cluster_id: str,
    auth: str,
    topic_name: str,
    config: dict,
    dry_run: bool,
) -> bool:
    """
    Create one topic via the Confluent Admin REST API v3.

    Single partition — each attendee has their own isolated topics, so there
    is no need for parallelism within a topic. Replication factor 3 is the
    Confluent Cloud default for durability.

    Returns True on success or if the topic already exists (idempotent).
    """
    if dry_run:
        print(f"  [dry-run] {topic_name}")
        return True

    url = f"{rest_endpoint}/kafka/v3/clusters/{cluster_id}/topics"
    body = json.dumps({
        "topic_name": topic_name,
        "partitions_count": 1,
        "replication_factor": 3,
        "configs": [{"name": k, "value": v} for k, v in config.items()],
    }).encode()

    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": auth, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            if resp.getcode() in (200, 201):
                print(f"  ✓ Created  {topic_name}")
                return True
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            err = json.loads(raw)
        except Exception:
            err = {}
        # Confluent returns HTTP 400 / error_code 40002 when the topic already exists.
        if e.code == 400 and (
            err.get("error_code") == 40002
            or "already exists" in err.get("message", "").lower()
        ):
            print(f"  ~ Exists   {topic_name}")
            return True
        print(f"  ✗ Failed   {topic_name}  (HTTP {e.code}: {raw.decode(errors='replace')})")
        return False
    except Exception as ex:
        print(f"  ✗ Failed   {topic_name}  ({ex})")
        return False
    return False


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create your Confluent Cloud topics for the Hive workshop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making any API calls.",
    )
    args = parser.parse_args()

    # Load .env into os.environ (does not overwrite already-set shell vars).
    # Attendees only need to fill in .env — no `export` commands required.
    load_dotenv(ENV_PATH, override=False)

    def get(key: str) -> str:
        """Return the value, treating CHANGE_ME as empty."""
        val = os.environ.get(key, "").strip().strip("'\"")
        return "" if val == "CHANGE_ME" else val

    rest_endpoint = get("CONFLUENT_REST_ENDPOINT").rstrip("/")
    cluster_id    = get("CONFLUENT_CLUSTER_ID")
    api_key       = get("CONFLUENT_API_KEY")
    api_secret    = get("CONFLUENT_API_SECRET")

    # Validate all required values before doing any work.
    # In dry-run mode credentials are not needed.
    required = []
    if not args.dry_run:
        required += [
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
        if not args.dry_run:
            print("Use --dry-run to preview topic names without credentials.")
        sys.exit(1)

    # Print a summary header before doing any work.
    print(f"Topics   : {len(TOPICS)}")
    if args.dry_run:
        print("Mode     : dry-run — no API calls will be made")
    else:
        print(f"Cluster  : {cluster_id}")
        print(f"Endpoint : {rest_endpoint}")
    print()

    auth = _auth_header(api_key, api_secret) if not args.dry_run else ""
    failures = 0

    for topic, cfg in TOPICS:
        ok = create_topic(rest_endpoint, cluster_id, auth, topic, cfg, args.dry_run)
        if not ok:
            failures += 1

    print()

    # Final status — exit non-zero so shell scripts can detect failures.
    if failures:
        print(f"Finished with {failures} failure(s). Review the errors above.")
        sys.exit(1)

    if args.dry_run:
        print("Dry-run complete. Remove --dry-run to create the topics for real.")
    else:
        print("All topics provisioned. You can now register your simulation.")


if __name__ == "__main__":
    main()
