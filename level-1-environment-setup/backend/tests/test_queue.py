import pytest
from backend.store import DashboardStore
from backend.models import EventEnvelope


def test_store_robot_queue_snapshot_and_reset():
    store = DashboardStore()
    assert store.robot_queue == []

    # Ingest simulation.state with robot_queue
    env = EventEnvelope(
        event_id="test-env-1",
        event_type="simulation.state",
        schema_version=1,
        simulation_id="sim-1",
        server_epoch="epoch-1",
        run_id="run-1",
        run_generation=1,
        event_sequence=1,
        state_revision=1,
        occurred_at="2026-01-01T00:00:00Z",
        sim_time_minutes=0,
        payload={
            "lifecycle_status": "running",
            "running": True,
            "operational_error": None,
            "resource_deliveries": [],
            "resources": {"resin": 0, "silicon": 0, "metals": 0, "copper": 0, "energy": 0},
            "parts": {"chassis": 0, "electronics": 0, "actuator": 0, "battery": 0},
            "stations": [],
            "completed_robots": {"count": 0, "last_robot_id": None},
            "robot_queue": ["gatherer", "gatherer", "engineer"],
            "last_applied_command_id": None,
        },
    )

    store.ingest(env)
    assert store.robot_queue == ["gatherer", "gatherer", "engineer"]
    snap = store.snapshot()
    assert snap["robot_queue"] == ["gatherer", "gatherer", "engineer"]

    # Reset clears queue
    store.reset()
    assert store.robot_queue == []
