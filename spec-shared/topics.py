"""
Single source of truth for Kafka topic names.

Topic names are derived directly from the ``topics`` keys in
``schemas/event_payloads_base.json`` by replacing ``.`` with ``-``.

Consumers of this module use:

    from topics import TOPICS, BASE_TOPICS, ACTIVITY_TOPIC_SUFFIXES

    BASE_TOPICS     – dict mapping suffix → topic name
                      e.g. ".gathering-started" → "gathering-started"

    TOPICS          – alias for BASE_TOPICS (used for publishing).

    STATE_TOPIC_SUFFIXES    – set of suffixes for state snapshot topics
                      (".simulation-state")

    ACTIVITY_TOPIC_SUFFIXES – list of suffixes for every activity topic
                      (used for probe writes).
"""

import json
import pathlib
from typing import Dict, List, Set

_SCHEMA_DIR = pathlib.Path(__file__).parent / "schemas"


def _load(filename: str) -> Dict[str, str]:
    with (_SCHEMA_DIR / filename).open() as fh:
        schema = json.load(fh)
    return {
        "." + key.replace(".", "-"): key.replace(".", "-")
        for key in schema["topics"]
    }


BASE_TOPICS: Dict[str, str] = _load("event_payloads_base.json")

TOPICS: Dict[str, str] = BASE_TOPICS

STATE_TOPIC_SUFFIXES: Set[str] = {".simulation-state"}

ACTIVITY_TOPIC_SUFFIXES: List[str] = [
    suffix for suffix in BASE_TOPICS if suffix not in STATE_TOPIC_SUFFIXES
]
