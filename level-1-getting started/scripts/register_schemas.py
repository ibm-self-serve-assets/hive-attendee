#!/usr/bin/env python3
"""
register_schemas.py
───────────────────
Registers the event schemas in YOUR Schema Registry. Run it after provision_topics.py
and before you connect the dashboard.

The Simulation server owns the schemas. This script downloads them from the server
(GET /v1/schemas) and, for every topic, registers one subject named <topic>-value.
The server never registers schemas itself: at connection time it only checks that each
subject exists and matches the schema it publishes, so a skipped or outdated registration
shows up as a clear message in the dashboard.

For each subject the script:
  1. sets the compatibility level to BACKWARD_TRANSITIVE (before the first version, so the
     rule applies from version 1 on),
  2. if a version is already registered and identical, leaves it alone ("~ Unchanged"),
  3. otherwise checks the schema is compatible with the registered versions and registers it.

WHY BACKWARD_TRANSITIVE?
  Your dashboard and your Flink jobs replay topics from offset 0, and simulation-state is
  compacted forever. Every old record must stay readable with the newest schema.

IDEMPOTENT: running this script twice is safe. Run it again after the Simulation server is
redeployed; if the schemas changed it registers a new version.

USAGE:
  # 1. Fill in spec-shared/.env:
  #
  #    SIMULATION_SERVER_URL, WORKSHOP_ACCESS_TOKEN, ATTENDEE_ID   (from your instructor)
  #
  #    SCHEMA_REGISTRY_URL=https://psrc-xxxxx.us-west-2.aws.confluent.cloud
  #      → Confluent Cloud → Environment → Stream Governance → Schema Registry → Endpoint
  #
  #    SCHEMA_REGISTRY_API_KEY=...   SCHEMA_REGISTRY_API_SECRET=...
  #      → Confluent Cloud → Environment → Stream Governance → Schema Registry → API keys
  #      (a different key from the Kafka cluster key)

  # 2. Preview the subjects (only contacts the Simulation server):
  python3 register_schemas.py --dry-run

  # 3. Register them:
  python3 register_schemas.py
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
from typing import Any, Dict, Optional, Tuple

import certifi
from dotenv import load_dotenv

from sim_server import clean_env, fetch_schemas

# Use certifi's CA bundle so urllib works on macOS without the
# "Install Certificates.command" step or any system keychain config.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# ── Paths ─────────────────────────────────────────────────────────────────────
_SPEC_DIR = Path(__file__).resolve().parent
_SHARED_ENV = _SPEC_DIR.parent.parent / "spec-shared" / ".env"
ENV_PATH = _SHARED_ENV if _SHARED_ENV.exists() else _SPEC_DIR / ".env"

COMPATIBILITY = "BACKWARD_TRANSITIVE"
SR_CONTENT_TYPE = "application/vnd.schemaregistry.v1+json"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _basic(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def _http(method: str, url: str, headers: Dict[str, str], body: Optional[dict] = None) -> Tuple[int, Any]:
    """One JSON request. Returns (status, parsed body). Network failures return (0, message)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            raw = resp.read()
            return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode(errors="replace")
    except Exception as ex:
        return 0, str(ex)


def _sr_headers(auth: str) -> Dict[str, str]:
    return {"Authorization": auth, "Content-Type": SR_CONTENT_TYPE, "Accept": SR_CONTENT_TYPE}


def _error_text(status: int, body: Any) -> str:
    if status == 0:
        return str(body)
    if isinstance(body, dict) and body.get("message"):
        return f"HTTP {status}: {body['message']}"
    return f"HTTP {status}: {body}"


# ── Schema Registry ───────────────────────────────────────────────────────────

def _same_schema(a: Optional[str], b: str) -> bool:
    """Compare two JSON Schema documents ignoring whitespace and key order."""
    try:
        return json.loads(a or "") == json.loads(b)
    except ValueError:
        return False


def register_subject(sr_url: str, auth: str, entry: Dict[str, str]) -> bool:
    """Register one subject. Returns True on success or when it is already registered."""
    subject = entry["subject"]
    schema = entry["schema"]
    quoted = urllib.parse.quote(subject, safe="")
    headers = _sr_headers(auth)

    # 1. Compatibility first, so it applies from version 1.
    status, body = _http("PUT", f"{sr_url}/config/{quoted}", headers, {"compatibility": COMPATIBILITY})
    if status != 200:
        print(f"  ✗ Failed   {subject}  (set compatibility: {_error_text(status, body)})")
        return False

    # 2. Already registered and identical?
    status, body = _http("GET", f"{sr_url}/subjects/{quoted}/versions/latest", headers)
    if status == 200:
        if _same_schema(body.get("schema"), schema):
            print(f"  ~ Unchanged {subject}  (version {body.get('version')})")
            return True
        # 3. A different schema is registered: it must be compatible before it becomes a new version.
        status, body = _http(
            "POST", f"{sr_url}/compatibility/subjects/{quoted}/versions/latest", headers,
            {"schema": schema, "schemaType": entry.get("schema_type", "JSON")},
        )
        if status != 200:
            print(f"  ✗ Failed   {subject}  (compatibility check: {_error_text(status, body)})")
            return False
        if not body.get("is_compatible"):
            print(
                f"  ✗ Rejected {subject}  (not {COMPATIBILITY} with the registered versions; "
                "ask your instructor before changing this subject)"
            )
            return False
    elif status != 404:
        print(f"  ✗ Failed   {subject}  (read latest version: {_error_text(status, body)})")
        return False

    status, body = _http(
        "POST", f"{sr_url}/subjects/{quoted}/versions", headers,
        {"schema": schema, "schemaType": entry.get("schema_type", "JSON")},
    )
    if status not in (200, 201):
        print(f"  ✗ Failed   {subject}  (register: {_error_text(status, body)})")
        return False
    print(f"  ✓ Registered {subject}  (schema id {body.get('id')})")
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Register the Hive event schemas in your Confluent Cloud Schema Registry.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the subjects that would be registered; Schema Registry is not contacted.",
    )
    args = parser.parse_args()

    load_dotenv(ENV_PATH, override=False)

    get = clean_env

    server_url  = get("SIMULATION_SERVER_URL").rstrip("/")
    token       = get("WORKSHOP_ACCESS_TOKEN")
    attendee_id = get("ATTENDEE_ID")
    sr_url      = get("SCHEMA_REGISTRY_URL").rstrip("/")
    sr_key      = get("SCHEMA_REGISTRY_API_KEY")
    sr_secret   = get("SCHEMA_REGISTRY_API_SECRET")

    required = [
        ("SIMULATION_SERVER_URL", server_url),
        ("WORKSHOP_ACCESS_TOKEN", token),
        ("ATTENDEE_ID",           attendee_id),
    ]
    if not args.dry_run:
        required += [
            ("SCHEMA_REGISTRY_URL",        sr_url),
            ("SCHEMA_REGISTRY_API_KEY",    sr_key),
            ("SCHEMA_REGISTRY_API_SECRET", sr_secret),
        ]
    missing = [name for name, val in required if not val]
    if missing:
        print("ERROR: the following values are missing or still set to a template value in .env:")
        for name in missing:
            print(f"  {name}=...")
        print(f"\nEdit {ENV_PATH} and fill in the values, then retry.")
        sys.exit(1)

    print(f"Simulation server : {server_url}")
    if args.dry_run:
        print("Mode              : dry-run — Schema Registry will not be contacted")
    else:
        print(f"Schema Registry   : {sr_url}")
    print()

    try:
        subjects = fetch_schemas(server_url, token, attendee_id)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Subjects : {len(subjects)}")
    failures = 0
    auth = "" if args.dry_run else _basic(sr_key, sr_secret)
    for entry in subjects:
        if args.dry_run:
            print(f"  [dry-run] {entry['subject']}")
        elif not register_subject(sr_url, auth, entry):
            failures += 1

    print()
    if failures:
        print(f"Finished with {failures} failure(s). Review the errors above.")
        sys.exit(1)
    if args.dry_run:
        print("Dry-run complete. Remove --dry-run to register the schemas for real.")
    else:
        print("All schemas registered. You can now connect the dashboard.")


if __name__ == "__main__":
    main()
