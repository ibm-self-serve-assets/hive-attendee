"""EventConsumerManager reads Schema Registry framed records (0x00 + 4-byte schema id + JSON)."""
import json
from types import SimpleNamespace

import pytest

from confluent_kafka.schema_registry.json_schema import JSONSerializer
from confluent_kafka.schema_registry._sync.mock_schema_registry_client import MockSchemaRegistryClient
from confluent_kafka.serialization import MessageField, SerializationContext

from backend.consumer import EventConsumerManager, make_event_deserializer
from backend.store import DashboardStore

TOPIC = "simulation-initialized"
SCHEMA = json.dumps({
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "event_id": {"type": "string"},
        "event_type": {"type": "string"},
        "simulation_id": {"type": "string"},
        "payload": {"type": "object"},
    },
    "required": ["event_id", "event_type", "simulation_id", "payload"],
})


def _event(**overrides):
    base = {
        "event_id": "e-1",
        "event_type": "simulation.initialized",
        "simulation_id": "sim-1",
        "payload": {"config": {"x": 1}},
    }
    base.update(overrides)
    return base


@pytest.fixture
def sr():
    return MockSchemaRegistryClient({"url": "mock://"})


def _record(sr, value, topic=TOPIC):
    """Value bytes as the Simulation server writes them."""
    ser = JSONSerializer(SCHEMA, sr, conf={"auto.register.schemas": True})
    return SimpleNamespace(
        topic=lambda: topic,
        value=lambda: ser(value, SerializationContext(topic, MessageField.VALUE)),
    )


def _manager(sr):
    return EventConsumerManager(store=DashboardStore(), deserializer=make_event_deserializer(schema_registry_client=sr))


def test_record_has_the_5_byte_schema_registry_prefix(sr):
    raw = _record(sr, _event()).value()
    assert raw[0] == 0x00
    assert json.loads(raw[5:]) == _event()


def test_decode_returns_the_envelope(sr):
    env = _manager(sr).decode(_record(sr, _event()))
    assert env.event_type == "simulation.initialized"
    assert env.simulation_id == "sim-1"
    assert env.payload == {"config": {"x": 1}}


def test_decode_falls_back_to_topic_name_when_event_type_is_empty(sr):
    env = _manager(sr).decode(_record(sr, _event(event_type="")))
    assert env.event_type == "simulation.initialized"


def test_plain_json_record_without_prefix_is_rejected(sr):
    plain = SimpleNamespace(topic=lambda: TOPIC, value=lambda: json.dumps(_event()).encode())
    with pytest.raises(Exception):
        _manager(sr).decode(plain)


def test_no_deserializer_without_schema_registry_settings():
    assert make_event_deserializer() is None
    assert make_event_deserializer("https://sr.example.com", "key", None) is None
