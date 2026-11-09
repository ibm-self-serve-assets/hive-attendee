import asyncio

import pytest

from backend import topic_watch
from backend.consumer import PartsPriorityQueueConsumer, QueensOrdersConsumer
from backend.store import DashboardStore
from backend.topic_watch import PartsPriorityQueueWatcher, QueensOrdersWatcher

GATHERER = {"actuator": 6, "battery": 5, "chassis": 2, "electronics": 1}
ENGINEER = {"actuator": 8, "battery": 2, "chassis": 1, "electronics": 3}


def _order(order_id, placed_seq, robot_type="gatherer", status="OPEN"):
    return {
        "order_id": order_id,
        "robot_type": robot_type,
        "workstation_type": "resin",
        "workstation_id": 1,
        "action": "upgrade",
        "placed_seq": placed_seq,
        "status": status,
    }


def _store(run_id="run-1") -> DashboardStore:
    store = DashboardStore()
    store.run_id = run_id
    return store


def test_parts_are_attached_to_the_right_order():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_queens_order("run-1", _order("b", 20, robot_type="engineer"))
    store.ingest_order_parts("run-1", "a", GATHERER)
    store.ingest_order_parts("run-1", "b", ENGINEER)

    by_id = {o["order_id"]: o for o in store.robot_queue}
    assert by_id["a"]["parts"] == GATHERER
    assert by_id["b"]["parts"] == ENGINEER


def test_an_order_whose_parts_have_not_arrived_has_no_parts_and_a_later_row_fills_them():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10))

    (before,) = store.robot_queue
    assert "parts" not in before  # no zeros in the gap between the two Flink jobs

    assert store.ingest_order_parts("run-1", "a", GATHERER) is True
    (after,) = store.robot_queue
    assert after["parts"] == GATHERER


def test_parts_that_arrive_before_the_order_are_kept():
    store = _store()
    store.ingest_order_parts("run-1", "a", GATHERER)
    store.ingest_queens_order("run-1", _order("a", 10))

    (order,) = store.robot_queue
    assert order["parts"] == GATHERER


def test_null_parts_are_dropped():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_order_parts("run-1", "a", {"actuator": 4, "battery": None, "chassis": 2, "electronics": None})

    (order,) = store.robot_queue
    assert order["parts"] == {"actuator": 4, "chassis": 2}


def test_parts_stay_on_the_order_as_its_status_changes():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_order_parts("run-1", "a", GATHERER)
    store.ingest_queens_order("run-1", _order("a", 10, status="IN_ASSEMBLY"))

    (order,) = store.orders_in_assembly
    assert order["parts"] == GATHERER


def test_parts_are_kept_per_run():
    store = _store("run-1")
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_order_parts("run-1", "a", GATHERER)
    store.ingest_queens_order("run-2", _order("a", 10))
    store.ingest_order_parts("run-2", "a", ENGINEER)

    assert store.robot_queue[0]["parts"] == GATHERER
    store.run_id = "run-2"
    assert store.robot_queue[0]["parts"] == ENGINEER


def test_ingest_parts_reports_change_only_for_current_run_and_new_data():
    store = _store("run-2")
    assert store.ingest_order_parts("run-1", "old", GATHERER) is False  # another run
    assert store.ingest_order_parts("run-2", "new", GATHERER) is True
    assert store.ingest_order_parts("run-2", "new", GATHERER) is False  # same row again
    assert store.ingest_order_parts("run-2", "", GATHERER) is False  # no order id


def test_snapshot_carries_the_parts_and_the_ready_flag():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_order_parts("run-1", "a", GATHERER)

    snap = store.snapshot()
    assert snap["robot_queue"][0]["parts"] == GATHERER
    assert snap["parts_priority_queue_ready"] is False
    store.parts_priority_queue_ready = True
    assert store.snapshot()["parts_priority_queue_ready"] is True


# ── consumer: a parts row goes to the parts, not to the order ────────────────

def test_parts_consumer_stores_only_the_parts():
    store = _store()
    consumer = PartsPriorityQueueConsumer(store=store)
    row = {**_order("a", 10), **GATHERER}

    assert consumer._ingest("run-1", "a", row) is True
    assert store.parts_by_run["run-1"]["a"] == GATHERER
    assert store.orders_by_run == {}  # the order itself comes from queens_orders


def test_orders_consumer_still_stores_the_order():
    store = _store()
    consumer = QueensOrdersConsumer(store=store)

    assert consumer._ingest("run-1", "a", _order("a", 10)) is True
    assert store.orders_by_run["run-1"]["a"]["robot_type"] == "gatherer"
    assert store.parts_by_run == {}


def test_the_two_consumers_read_their_own_topic_with_their_own_group():
    assert QueensOrdersConsumer(store=_store()).topic == "queens_orders"
    parts = PartsPriorityQueueConsumer(store=_store())
    assert parts.topic == "parts_priority_queue"
    assert parts.group_prefix != QueensOrdersConsumer.group_prefix


# ── watcher: the parts topic never locks Level 4 or restarts the Simulation ──

async def _noop():
    pass


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch):
    monkeypatch.setattr(topic_watch, "POLL_SECONDS", 0)


def _parts_watcher(store, answers):
    watcher = PartsPriorityQueueWatcher(
        store=store, bootstrap_servers="b", api_key="k", api_secret="s", on_change=_noop,
    )
    remaining = list(answers)

    def topic_exists():
        if not remaining:
            raise asyncio.CancelledError
        return remaining.pop(0)

    watcher._topic_exists = topic_exists
    return watcher


async def test_parts_watcher_sets_its_own_flag_and_leaves_level_4_alone():
    store = DashboardStore()
    await _parts_watcher(store, [True, True])._run()
    assert store.parts_priority_queue_ready is True
    assert store.queens_orders_ready is False


async def test_parts_watcher_clears_the_flag_when_the_topic_goes_away():
    store = DashboardStore()
    await _parts_watcher(store, [True, False])._run()
    assert store.parts_priority_queue_ready is False


async def test_parts_watcher_never_restarts_the_simulation():
    store = DashboardStore()
    watcher = _parts_watcher(store, [False, True, True])
    assert watcher.on_unlocked is None
    await watcher._run()
    assert store.parts_priority_queue_ready is True


def test_parts_watcher_watches_the_parts_topic():
    watcher = PartsPriorityQueueWatcher(
        store=DashboardStore(), bootstrap_servers="b", api_key="k", api_secret="s", on_change=_noop,
    )
    assert watcher.topic == "parts_priority_queue"
    assert QueensOrdersWatcher(
        store=DashboardStore(), bootstrap_servers="b", api_key="k", api_secret="s", on_change=_noop,
    ).topic == "queens_orders"
