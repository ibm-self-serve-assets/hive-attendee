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


def test_event_topics_are_asked_of_the_server_on_every_check(monkeypatch):
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
    assert len(calls) == 3  # asked on every check, so a changed list is noticed


def test_event_topics_use_the_last_list_when_the_server_is_unreachable(monkeypatch):
    from backend.topic_watch import EventTopicsWatcher

    answers = iter([["gathering-started"], RuntimeError("down")])

    def source():
        nxt = next(answers)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    watcher = EventTopicsWatcher(
        store=DashboardStore(), bootstrap_servers="b", api_key="k", api_secret="s",
        on_change=_noop, topic_source=source,
    )

    class Admin:
        def __init__(self, *a, **k): ...
        def list_topics(self, timeout):
            return type("Meta", (), {"topics": {}})()

    monkeypatch.setattr(topic_watch, "AdminClient", Admin)
    assert watcher._missing_topics() == ["gathering-started"]
    assert watcher._missing_topics() == ["gathering-started"]  # server down: last list still used


# ── schema watcher ────────────────────────────────────────────────────────────

GOOD = '{"type": "object", "properties": {"a": {"type": "string"}}}'
OLD = '{"type": "object", "properties": {"b": {"type": "string"}}}'


def _schema_watcher(store, published, registered):
    from backend.topic_watch import SchemaWatcher

    return SchemaWatcher(
        store=store,
        on_change=_noop,
        published_source=lambda: published(),
        registered_source=lambda subject: registered().get(subject),
    )


def _entries(*subjects):
    return [{"subject": s, "topic": s[:-6], "schema_type": "JSON", "schema": GOOD} for s in subjects]


def test_schema_watcher_warns_about_missing_and_different_subjects():
    store = DashboardStore()
    watcher = _schema_watcher(
        store,
        lambda: _entries("a-value", "b-value", "c-value"),
        lambda: {"a-value": GOOD, "b-value": OLD},  # a matches, b differs, c is missing
    )
    codes = {w.code: w.message for w in watcher._check()}
    assert set(codes) == {"schema_subjects_missing", "schema_subjects_differ"}
    assert "c-value" in codes["schema_subjects_missing"] and "register_schemas.sh" in codes["schema_subjects_missing"]
    assert "b-value" in codes["schema_subjects_differ"]
    assert "a-value" not in "".join(codes.values())


def test_schema_watcher_ignores_whitespace_and_key_order():
    store = DashboardStore()
    reordered = '{"properties": {"a": {"type": "string"}}, "type": "object"}'
    watcher = _schema_watcher(store, lambda: _entries("a-value"), lambda: {"a-value": reordered})
    assert watcher._check() == []


def test_schema_watcher_follows_the_server_every_poll_and_never_writes(monkeypatch):
    # The server's schema changes between polls; the watcher notices because it caches nothing.
    store = DashboardStore()
    server = {"schema": GOOD}
    registry = {"a-value": GOOD}
    writes = []

    class ReadOnlyRegistry(dict):
        def __setitem__(self, *a): writes.append(a)
        def __delitem__(self, *a): writes.append(a)

    watcher = _schema_watcher(
        store,
        lambda: [{"subject": "a-value", "schema": server["schema"]}],
        lambda: ReadOnlyRegistry(registry),
    )
    assert watcher._check() == []
    server["schema"] = OLD
    assert [w.code for w in watcher._check()] == ["schema_subjects_differ"]
    assert writes == []


async def test_schema_watcher_warning_clears_by_itself_when_the_attendee_fixes_it(monkeypatch):
    monkeypatch.setattr(topic_watch, "SCHEMA_POLL_SECONDS", 0)
    store, seen = DashboardStore(), []
    registry = {}  # empty: everything missing
    polls = {"n": 0}
    holder = {}

    def published():
        polls["n"] += 1
        seen.append((bool(store.schema_warnings), holder["w"].clean))
        if polls["n"] == 3:
            registry["a-value"] = GOOD  # the attendee runs register_schemas.sh
        if polls["n"] > 5:
            raise asyncio.CancelledError
        return _entries("a-value")

    holder["w"] = _schema_watcher(store, published, lambda: registry)
    await holder["w"]._run()
    assert store.schema_warnings == []
    assert holder["w"].clean is True
    assert seen[1] == (True, False)  # warned and not clean while it was wrong
    assert seen[-1] == (False, True)  # cleared on the next poll after the fix


async def test_schema_watcher_keeps_last_result_when_a_source_is_unreachable(monkeypatch):
    monkeypatch.setattr(topic_watch, "SCHEMA_POLL_SECONDS", 0)
    store = DashboardStore()
    polls = {"n": 0}

    def published():
        polls["n"] += 1
        if polls["n"] == 1:
            return _entries("a-value")
        if polls["n"] == 2:
            raise RuntimeError("server unreachable")
        raise asyncio.CancelledError

    watcher = _schema_watcher(store, published, lambda: {})
    await watcher._run()
    assert [w["code"] for w in store.schema_warnings] == ["schema_subjects_missing"]
