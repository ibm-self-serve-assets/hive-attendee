from backend.store import DashboardStore


def _order(order_id, placed_seq, status="OPEN", robot_type="gatherer", workstation_type="resin", workstation_id=1, action="upgrade"):
    return {
        "order_id": order_id,
        "robot_type": robot_type,
        "workstation_type": workstation_type,
        "workstation_id": workstation_id,
        "action": action,
        "placed_seq": placed_seq,
        "status": status,
    }


def _store(run_id="run-1") -> DashboardStore:
    store = DashboardStore()
    store.run_id = run_id
    return store


def test_queue_is_empty_before_any_orders():
    store = _store()
    assert store.robot_queue == []
    assert store.orders_in_assembly == []
    assert store.snapshot()["robot_queue"] == []
    assert store.snapshot()["queens_orders_ready"] is False


def test_queue_holds_only_open_orders_sorted_by_placed_seq():
    store = _store()
    store.ingest_queens_order("run-1", _order("c", 30))
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_queens_order("run-1", _order("b", 20, status="IN_ASSEMBLY"))
    store.ingest_queens_order("run-1", _order("d", 40, status="ASSIGNED"))

    assert [o["order_id"] for o in store.robot_queue] == ["a", "c"]
    assert [o["order_id"] for o in store.snapshot()["robot_queue"]] == ["a", "c"]


def test_in_assembly_order_leaves_the_queue_and_is_listed_separately():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_queens_order("run-1", _order("b", 20))

    assert store.ingest_queens_order("run-1", _order("a", 10, status="IN_ASSEMBLY")) is True

    assert [o["order_id"] for o in store.robot_queue] == ["b"]
    assert [o["order_id"] for o in store.orders_in_assembly] == ["a"]


def test_later_row_for_same_order_replaces_status_and_keeps_other_fields():
    store = _store()
    store.ingest_queens_order("run-1", _order("a", 10, robot_type="builder", action="add"))
    # An upsert row that omits fields must not erase what is already known.
    store.ingest_queens_order("run-1", {"order_id": "a", "status": "ASSIGNED"})

    (order,) = store.queens_orders
    assert order["status"] == "ASSIGNED"
    assert order["robot_type"] == "builder"
    assert order["placed_seq"] == 10


def test_ingest_reports_change_only_for_current_run_and_new_data():
    store = _store("run-2")
    assert store.ingest_queens_order("run-1", _order("old", 1)) is False
    assert store.ingest_queens_order("run-2", _order("new", 1)) is True
    assert store.ingest_queens_order("run-2", _order("new", 1)) is False
    assert store.ingest_queens_order("run-2", {"robot_type": "gatherer"}) is False


def test_orders_are_scoped_to_the_current_run():
    store = _store("run-1")
    store.ingest_queens_order("run-1", _order("a", 10))
    store.ingest_queens_order("run-2", _order("z", 10))

    assert [o["order_id"] for o in store.robot_queue] == ["a"]

    store.run_id = "run-2"
    assert [o["order_id"] for o in store.robot_queue] == ["z"]

    store.run_id = None
    assert store.robot_queue == []
