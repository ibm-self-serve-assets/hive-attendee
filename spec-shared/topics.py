"""
Single source of truth for Kafka topic names.

Topic names are derived directly from the ``topics`` keys in
``schemas/event_payloads_base.json`` (Levels 1-3) and
``schemas/event_payloads_orders.json`` (Level 4) by replacing ``.`` with ``-``.

Consumers of this module use:

    from topics import TOPICS, BASE_TOPICS, ORDER_TOPICS, ACTIVITY_TOPIC_SUFFIXES

    BASE_TOPICS     – dict mapping suffix → topic name for the Level 1 topics
                      e.g. ".gathering-started" → "gathering-started"

    ORDER_TOPICS    – same, for the Level 4 order topics. These are optional:
                      attendees only create them when they reach Level 4.

    TOPICS          – BASE_TOPICS and ORDER_TOPICS combined (used for publishing).

    ACTIVITY_TOPIC_SUFFIXES – list of suffixes for every *base* topic except
                      ".simulation-state" (used for probe writes).
"""

import json
import pathlib
from typing import Dict, List

_SCHEMA_DIR = pathlib.Path(__file__).parent / "schemas"


def _load(filename: str) -> Dict[str, str]:
    with (_SCHEMA_DIR / filename).open() as fh:
        schema = json.load(fh)
    return {
        "." + key.replace(".", "-"): key.replace(".", "-")
        for key in schema["topics"]
    }


BASE_TOPICS: Dict[str, str] = _load("event_payloads_base.json")
ORDER_TOPICS: Dict[str, str] = _load("event_payloads_orders.json")

TOPICS: Dict[str, str] = {**BASE_TOPICS, **ORDER_TOPICS}

ACTIVITY_TOPIC_SUFFIXES: List[str] = [
    suffix for suffix in BASE_TOPICS if suffix != ".simulation-state"
]
