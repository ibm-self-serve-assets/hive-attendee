#!/usr/bin/env python3
"""
provision_order_topics.py
──────────────────────────
Creates the two Kafka topics for Level 4 Order Fulfillment.  Topic names are
derived from spec-shared/schemas/event_payloads_orders.json.

  order-placed       — emitted by the Simulation server every time a new order opens
  order-fulfilled    — emitted by the Simulation server every time a robot order ships

Both topics use the delete / 24-hour retention policy (same as all activity topics).

IDEMPOTENT: running this script twice is safe. Existing topics are left unchanged
and reported as "~ Exists" rather than causing an error.

USAGE:
  # 1. Fill in spec-shared/.env with your Confluent Cloud credentials (same file used
  #    by Level 1's provision_topics.py — no extra setup needed if you completed Level 1).
  #
  # 2. Preview what will be created (no API calls):
  python3 provision_order_topics.py --dry-run
  #
  # 3. Create your topics:
  python3 provision_order_topics.py
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

# ── Paths ──────────────────────────────────────────────────────────────────────
_SPEC_DIR   = Path(__file__).resolve().parent
_SHARED_ENV = _SPEC_DIR.parent.parent / "spec-shared" / ".env"
ENV_PATH    = _SHARED_ENV if _SHARED_ENV.exists() else _SPEC_DIR / ".env"

_ORDERS_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "spec-shared" / "schemas" / "event_payloads_orders.json"
)

# ── Topic configuration ────────────────────────────────────────────────────────
ACTIVITY_CONFIG = {
    "cleanup.policy": "delete",
    "retention.ms": str(24 * 60 * 60 * 1000),
}


def _load_topics():
    """Derive topic names from event_payloads_orders.json."""
    with _ORDERS_SCHEMA_PATH.open() as fh:
        schema = json.load(fh)
    return [
        (key.replace(".", "-"), ACTIVITY_CONFIG)
        for key in schema["topics"]
    ]


TOPICS = _load_topics()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _auth_header(api_key: str, api_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()


def create_topic(
    rest_endpoint: str,
    cluster_id: str,
    auth: str,
    topic_name: str,
    config: dict,
    dry_run: bool,
) -> bool:
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


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create Confluent Cloud topics for Level 4 Order Fulfillment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making any API calls.",
    )
    args = parser.parse_args()

    load_dotenv(ENV_PATH, override=False)

    def get(key: str) -> str:
        val = os.environ.get(key, "").strip().strip("'\"")
        return "" if val == "CHANGE_ME" else val

    rest_endpoint = get("CONFLUENT_REST_ENDPOINT").rstrip("/")
    cluster_id    = get("CONFLUENT_CLUSTER_ID")
    api_key       = get("CONFLUENT_API_KEY")
    api_secret    = get("CONFLUENT_API_SECRET")

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
        sys.exit(1)

    print(f"Topics   : {len(TOPICS)}")
    if args.dry_run:
        print("Mode     : dry-run — no API calls will be made")
    else:
        print(f"Cluster  : {cluster_id}")
        print(f"Endpoint : {rest_endpoint}")
    print()

    auth     = _auth_header(api_key, api_secret) if not args.dry_run else ""
    failures = 0

    for topic, cfg in TOPICS:
        ok = create_topic(rest_endpoint, cluster_id, auth, topic, cfg, args.dry_run)
        if not ok:
            failures += 1

    print()

    if failures:
        print(f"Finished with {failures} failure(s). Review the errors above.")
        sys.exit(1)

    if args.dry_run:
        print("Dry-run complete. Remove --dry-run to create the topics for real.")
    else:
        print("Order topics provisioned. Your Level 4 dashboard will unlock automatically.")


if __name__ == "__main__":
    main()
