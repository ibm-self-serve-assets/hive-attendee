"""The store builds the workstation layout and recipes from the *.state events."""
from backend.models import EventEnvelope
from backend.store import DashboardStore


def _state(event_type, payload, seq, run_generation=1, event_id=None):
    return EventEnvelope(
        event_id=event_id or f"e-{seq}",
        event_type=event_type,
        simulation_id="sim-1",
        run_id=f"run-{run_generation}",
        run_generation=run_generation,
        event_sequence=seq,
        payload=payload,
    )


def _gathering(workstation_type, workstation_id, tier, seq, **kw):
    return _state("gathering.state", {
        "workstation_type": workstation_type, "workstation_id": workstation_id, "tier": tier,
    }, seq, **kw)


def test_state_events_build_the_layout_per_workstation():
    store = DashboardStore()
    store.ingest(_gathering("resin", 1, 2, 1))
    store.ingest(_gathering("resin", 2, 1, 2))
    assert store.snapshot()["workstations"]["resin"] == [
        {"workstation_id": 1, "tier": 2},
        {"workstation_id": 2, "tier": 1},
    ]


def test_a_later_state_message_replaces_the_tier_of_that_workstation_only():
    store = DashboardStore()
    store.ingest(_gathering("resin", 1, 2, 1))
    store.ingest(_gathering("resin", 2, 1, 2))
    store.ingest(_gathering("resin", 2, 2, 3))
    assert store.workstations["resin"] == [
        {"workstation_id": 1, "tier": 2},
        {"workstation_id": 2, "tier": 2},
    ]


def test_replaying_a_state_message_changes_nothing():
    store = DashboardStore()
    for seq in (1, 2):  # same message twice (a different event_id, as after a replay)
        store.ingest(_gathering("metals", 1, 1, seq))
    assert store.workstations["metals"] == [{"workstation_id": 1, "tier": 1}]


def test_workstations_stay_sorted_when_messages_arrive_out_of_order():
    store = DashboardStore()
    store.ingest(_gathering("copper", 3, 1, 1))
    store.ingest(_gathering("copper", 1, 2, 2))
    store.ingest(_gathering("copper", 2, 1, 3))
    assert [w["workstation_id"] for w in store.workstations["copper"]] == [1, 2, 3]


def test_manufacturing_and_assembly_state_fill_the_recipes_before_any_job_starts():
    store = DashboardStore()
    store.ingest(_state("manufacturing.state", {
        "workstation_type": "battery", "workstation_id": 1, "output_type": "battery",
        "resources_required": {"energy": 5, "copper": 2, "metals": 1}, "tier": 1,
    }, 1))
    store.ingest(_state("assembly.state", {
        "workstation_type": "builder", "workstation_id": 1, "output_type": "builder",
        "parts_required": {"chassis": 3, "electronics": 2, "actuator": 10, "battery": 4}, "tier": 1,
    }, 2))
    assert store.manufacturing_inputs["battery"] == {"energy": 5, "copper": 2, "metals": 1}
    assert store.assembly_inputs["builder"]["actuator"] == 10
    snap = store.snapshot()
    assert snap["manufacturing_inputs"]["battery"]["energy"] == 5
    assert snap["workstations"]["battery"] == [{"workstation_id": 1, "tier": 1}]


def test_a_new_run_clears_the_layout_and_is_seeded_from_its_own_state_messages():
    store = DashboardStore()
    store.ingest(_gathering("resin", 1, 2, 1))
    store.ingest(_gathering("resin", 2, 1, 2))
    assert len(store.workstations["resin"]) == 2

    # Restart: run_generation 2 starts with workstation 1 only.
    store.ingest(_gathering("resin", 1, 2, 3, run_generation=2))
    assert store.workstations["resin"] == [{"workstation_id": 1, "tier": 2}]


def test_the_old_change_events_are_gone():
    store = DashboardStore()
    assert not hasattr(store, "station_tiers") and not hasattr(store, "station_slots")
    assert "station_slots" not in store.snapshot() and "station_tiers" not in store.snapshot()
