"""
Single source of truth for Kafka topic names.

Topic names are derived directly from the ``topics`` keys in
``schemas/event_payloads.json`` by replacing ``.`` with ``-``.

Consumers of this module use:

    from server.topics import TOPICS, ACTIVITY_TOPIC_SUFFIXES

    TOPICS          – dict mapping suffix → topic name
                      e.g. ".gathering-started" → "gathering-started"

    ACTIVITY_TOPIC_SUFFIXES – list of suffixes for every topic *except*
                      ".simulation-state" (used for probe writes).
"""

import json
import pathlib
from typing import Dict, List

_SCHEMA_PATH = pathlib.Path(__file__).parent / "schemas" / "event_payloads.json"


def _load() -> Dict[str, str]:
    with _SCHEMA_PATH.open() as fh:
        schema = json.load(fh)
    return {
        "." + key.replace(".", "-"): key.replace(".", "-")
        for key in schema["topics"]
    }


TOPICS: Dict[str, str] = _load()

ACTIVITY_TOPIC_SUFFIXES: List[str] = [
    suffix for suffix in TOPICS if suffix != ".simulation-state"
]
