"""
sim_server.py
─────────────
What the Level 1 scripts ask the Simulation server for: the list of event topics and their
schemas (GET /v1/schemas). The server owns this list, so the scripts keep no copy of it.

Used by provision_topics.py, delete_topics_and_schemas.py and register_schemas.py.
"""

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Dict, List, Tuple

import certifi

# Use certifi's CA bundle so urllib works on macOS without the
# "Install Certificates.command" step or any system keychain config.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# Topics that keep only the latest message per key and never expire. Every other
# event topic keeps its events for 24 hours.
STATE_TOPICS = {"simulation-state", "simulation-initialized"}


def clean_env(key: str) -> str:
    """Return the value from the environment, treating CHANGE_ME and <...> template text as empty."""
    val = os.environ.get(key, "").strip().strip("'\"")
    if val == "CHANGE_ME" or (val.startswith("<") and val.endswith(">")):
        return ""
    return val


def fetch_schemas(server_url: str, token: str, attendee_id: str) -> List[Dict[str, str]]:
    """Download the subject list from the Simulation server. Raises RuntimeError with a plain message."""
    url = f"{server_url}/v1/schemas"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "X-Attendee-Id": attendee_id},
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = f"HTTP {e.code}: {e.read().decode(errors='replace')}"
        if e.code == 404:
            detail += " (this Simulation server does not publish schemas yet; ask your instructor)"
        raise RuntimeError(f"Could not download the schemas from {url}: {detail}")
    except Exception as ex:
        raise RuntimeError(f"Could not download the schemas from {url}: {ex}")
    if not isinstance(body, dict) or "subjects" not in body:
        raise RuntimeError(f"Could not download the schemas from {url}: unexpected response")
    return body["subjects"]


def fetch_topics(server_url: str, token: str, attendee_id: str) -> List[Tuple[str, str]]:
    """The event topics as (name, kind) pairs; kind is "state" (compacted) or "activity"."""
    return [
        (s["topic"], "state" if s["topic"] in STATE_TOPICS else "activity")
        for s in fetch_schemas(server_url, token, attendee_id)
    ]
