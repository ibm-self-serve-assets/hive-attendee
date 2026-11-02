import pytest
from backend.store import DashboardStore
from backend.models import EventEnvelope


def test_store_robot_queue_snapshot_and_reset():
    store = DashboardStore()
    assert store.robot_queue == []

    # Ingest assembly.state with robot_queue
    env = EventEnvelope(
        event_id="test-env-1",
        event_type="assembly.state",
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
            "robot_queue": ["gatherer", "gatherer", "engineer"],
        },
    )

    store.ingest(env)
    assert store.robot_queue == ["gatherer", "gatherer", "engineer"]
    snap = store.snapshot()
    assert snap["robot_queue"] == ["gatherer", "gatherer", "engineer"]

    # Reset clears queue
    store.reset()
    assert store.robot_queue == []
