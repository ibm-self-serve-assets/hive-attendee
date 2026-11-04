import asyncio

import pytest

from backend import topic_watch
from backend.store import DashboardStore
from backend.topic_watch import QueensOrdersWatcher


async def _noop():
    pass


def _watcher(store, answers, unlocked):
    """A watcher whose topic check returns `answers` in turn, then cancels the poll loop."""
    async def on_unlocked(label):
        unlocked.append(label)

    watcher = QueensOrdersWatcher(
        store=store,
        bootstrap_servers="b",
        api_key="k",
        api_secret="s",
        on_change=_noop,
        on_unlocked=on_unlocked,
    )
    remaining = list(answers)

    def topic_exists():
        if not remaining:
            raise asyncio.CancelledError
        return remaining.pop(0)

    watcher._topic_exists = topic_exists
    return watcher


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch):
    monkeypatch.setattr(topic_watch, "POLL_SECONDS", 0)


async def test_gate_met_at_startup_does_not_restart():
    store, unlocked = DashboardStore(), []
    await _watcher(store, [True, True], unlocked)._run()
    assert store.queens_orders_ready is True
    assert unlocked == []


async def test_gate_going_from_unmet_to_met_restarts_once():
    store, unlocked = DashboardStore(), []
    await _watcher(store, [False, False, True, True], unlocked)._run()
    assert store.queens_orders_ready is True
    assert unlocked == ["Level 4"]


async def test_gate_met_then_lost_then_met_restarts_again():
    store, unlocked = DashboardStore(), []
    await _watcher(store, [True, False, True, True], unlocked)._run()
    assert store.queens_orders_ready is True
    assert unlocked == ["Level 4"]


async def test_failed_check_does_not_count_as_gate_lost():
    store, unlocked = DashboardStore(), []
    watcher = _watcher(store, [True], unlocked)
    calls = iter([True, RuntimeError("kafka unreachable"), True])

    def flaky():
        nxt = next(calls, None)
        if nxt is None:
            raise asyncio.CancelledError
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    watcher._topic_exists = flaky
    await watcher._run()
    assert unlocked == []


def test_event_topics_are_asked_of_the_server_until_it_answers(monkeypatch):
    from backend.topic_watch import EventTopicsWatcher

    calls = []

    def source():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("server not reachable yet")
        return ["gathering-started"]

    watcher = EventTopicsWatcher(
        store=DashboardStore(), bootstrap_servers="b", api_key="k", api_secret="s",
        on_change=_noop, topic_source=source,
    )

    class Meta:
        topics = {"gathering-started": type("T", (), {"error": None})()}

    class Admin:
        def __init__(self, *a, **k): ...
        def list_topics(self, timeout):
            return Meta()

    monkeypatch.setattr(topic_watch, "AdminClient", Admin)
    with pytest.raises(RuntimeError):
        watcher._missing_topics()
    assert watcher._missing_topics() == []
    assert watcher._missing_topics() == []
    assert len(calls) == 2  # asked again after the failure, then kept
