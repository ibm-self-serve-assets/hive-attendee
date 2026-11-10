"""The store keeps a recent-event log per dashboard panel, keyed by the event_type prefix."""
from backend.models import EventEnvelope
from backend.store import DashboardStore


def _event(event_type, payload, seq):
    return EventEnvelope(
        event_id=f"e-{seq}",
        event_type=event_type,
        simulation_id="sim-1",
        run_id="run-1",
        run_generation=1,
        event_sequence=seq,
        payload=payload,
    )


ORDER = {
    "order_id": "o-1", "robot_type": "gatherer", "workstation_type": "resin",
    "workstation_id": 1, "action": "upgrade",
}


def test_queen_events_are_logged_in_the_queen_panel():
    store = DashboardStore()
    store.ingest(_event("queen.worker.ordered", ORDER, 1))
    store.ingest(_event("queen.worker.assigned", ORDER, 2))
    log = store.snapshot()["events"]["queen"]
    assert [e["event_type"] for e in log] == ["queen.worker.assigned", "queen.worker.ordered"]


def test_simulation_events_are_logged_in_the_simulation_panel():
    store = DashboardStore()
    store.ingest(_event("simulation.state", {"lifecycle_status": "running", "running": True}, 1))
    log = store.snapshot()["events"]["simulation"]
    assert [e["event_type"] for e in log] == ["simulation.state"]


def test_the_other_panels_do_not_receive_queen_or_simulation_events():
    store = DashboardStore()
    store.ingest(_event("queen.worker.ordered", ORDER, 1))
    store.ingest(_event("simulation.state", {"lifecycle_status": "running", "running": True}, 2))
    events = store.snapshot()["events"]
    assert events["gathering"] == events["manufacturing"] == events["assembly"] == []


def test_an_event_type_with_no_panel_logs_one_warning(caplog):
    store = DashboardStore()
    with caplog.at_level("WARNING"):
        store.ingest(_event("colony.founded", {}, 1))
        store.ingest(_event("colony.founded", {}, 2))
        store.ingest(_event("colony.expanded", {}, 3))
    warned = [r.getMessage() for r in caplog.records if "has no event panel" in r.getMessage()]
    assert len(warned) == 2
    assert "'colony.founded'" in warned[0] and "'colony.expanded'" in warned[1]


def test_events_with_a_panel_do_not_warn(caplog):
    store = DashboardStore()
    with caplog.at_level("WARNING"):
        store.ingest(_event("queen.worker.ordered", ORDER, 1))
    assert not [r for r in caplog.records if "has no event panel" in r.getMessage()]


def test_every_panel_keeps_only_the_newest_250_events():
    store = DashboardStore()
    store.ingest(_event("gathering.state", {"workstation_type": "resin", "workstation_id": 1, "tier": 1}, 1))
    for i in range(2, 400):
        store.ingest(_event("gathering.completed", {"workstation_type": "resin", "quantity": 1}, i))
    for i in range(400, 700):
        store.ingest(_event("simulation.state", {"lifecycle_status": "running", "running": True}, i))
    events = store.snapshot()["events"]
    assert len(events["gathering"]) == 250
    assert len(events["simulation"]) == 250
    assert [e["event_sequence"] for e in events["gathering"]][:2] == [399, 398]
    assert "gathering.state" not in [e["event_type"] for e in events["gathering"]]

