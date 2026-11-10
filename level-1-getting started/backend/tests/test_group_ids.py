"""Kafka consumer group ids: <name>-<attendee>, one stable group per consumer."""
from backend.consumer import PartsPriorityQueueConsumer, QueensOrdersConsumer, _make_group_id
from backend.store import DashboardStore


def _store(attendee="hive-003", simulation="f1f75bb6-1111"):
    store = DashboardStore()
    store.attendee_id = attendee
    store.active_simulation_id = simulation
    return store


def test_the_group_ids_read_as_name_then_hive_number():
    names = ("events", "efficiency", "inventory", "orders", "parts-priority")
    assert [_make_group_id(n, _store()) for n in names] == [
        "events-hive-003", "efficiency-hive-003", "inventory-hive-003",
        "orders-hive-003", "parts-priority-hive-003",
    ]


def test_a_group_id_does_not_change_with_the_simulation():
    assert _make_group_id("events", _store(simulation=None)) == _make_group_id("events", _store(simulation="f1f75bb6-1"))
    assert _make_group_id("events", _store(simulation="aaaaaaaa-1")) == _make_group_id("events", _store(simulation="bbbbbbbb-2"))


def test_an_attendee_id_that_does_not_start_with_queen_is_kept_as_is():
    assert _make_group_id("orders", _store(attendee="ana.lopez@example.com")) == "orders-ana-lopez"


def test_the_order_consumers_use_the_full_names():
    assert QueensOrdersConsumer.group_prefix == "orders"
    assert PartsPriorityQueueConsumer.group_prefix == "parts-priority"
