import asyncio
import json
import logging
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from backend.log_setup import MAJOR
from backend.store import DashboardStore

logger = logging.getLogger("hive.topic_watch")
kafka_logger = logging.getLogger("hive.kafka")

try:
    from confluent_kafka.admin import AdminClient
    KAFKA_AVAILABLE = True
except ImportError:
    AdminClient = None
    KAFKA_AVAILABLE = False

POLL_SECONDS = 3.0

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "spec-shared" / "schemas" / "event_payloads_base.json"


def load_event_topic_names() -> List[str]:
    """
    Topic names the Level 1 provisioning script creates: the keys of ``topics`` in
    spec-shared/schemas/event_payloads.json with dots replaced by hyphens.
    """
    with _SCHEMA_PATH.open() as fh:
        schema = json.load(fh)
    return [key.replace(".", "-") for key in schema["topics"]]


# Called with a level label when that level's gate goes from not met to met.
# Not called for a gate that is already met the first time it is checked.
OnUnlocked = Callable[[str], Awaitable[None]]


class EventTopicsWatcher:
    """
    Polls Confluent Cloud for the Simulation event topics defined in event_payloads.json
    (created by Level 1's provision_topics.sh) and keeps `store.event_topics_ready` /
    `store.event_topics_missing` current. Only checks that topics exist; it never reads records.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str],
        api_key: Optional[str],
        api_secret: Optional[str],
        on_change: Callable[[], Awaitable[None]],
        on_unlocked: Optional[OnUnlocked] = None,
    ):
        self.store = store
        self.on_change = on_change
        self.on_unlocked = on_unlocked
        self._conf = {
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "enable.metrics.push": False,
        }
        self._enabled = bool(KAFKA_AVAILABLE and bootstrap_servers and api_key and api_secret)
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if not self._enabled or self._task:
            return
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _missing_topics(self) -> List[str]:
        # List all topics rather than asking for them by name, so a missing topic
        # is never auto-created by the metadata request.
        # Re-read the schema every poll so edits to event_payloads.json apply without a restart.
        topics = load_event_topic_names()
        meta = AdminClient(self._conf, logger=kafka_logger).list_topics(timeout=5)
        return [
            t for t in topics
            if t not in meta.topics or meta.topics[t].error is not None
        ]

    async def _run(self) -> None:
        was_ready: Optional[bool] = None  # None until the first successful check
        while True:
            try:
                missing = await asyncio.to_thread(self._missing_topics)
                ready = not missing
                if ready != self.store.event_topics_ready or missing != self.store.event_topics_missing:
                    self.store.event_topics_ready = ready
                    self.store.event_topics_missing = missing
                    logger.info(
                        "All topics present." if ready else f"Topics missing: {', '.join(missing)}",
                        extra=MAJOR,
                    )
                    await self.on_change()
                if ready and was_ready is False and self.on_unlocked:
                    await self.on_unlocked("Level 1")
                was_ready = ready
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Event topics check failed: {e}")
            await asyncio.sleep(POLL_SECONDS)


class CalculatedValuesWatcher:
    """
    Polls Confluent Cloud for the `workstation_efficiency` topic (Flink creates it when the
    attendee runs 01_create_sink.sql) and keeps `store.workstation_efficiency_ready` current,
    so deleting the topic locks Level 2 again.
    Only checks that the topic exists; it never reads records.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str],
        api_key: Optional[str],
        api_secret: Optional[str],
        on_change: Callable[[], Awaitable[None]],
        topic: str = "workstation_efficiency",
        on_unlocked: Optional[OnUnlocked] = None,
    ):
        self.store = store
        self.topic = topic
        self.on_change = on_change
        self.on_unlocked = on_unlocked
        self._conf = {
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "enable.metrics.push": False,
        }
        self._enabled = bool(KAFKA_AVAILABLE and bootstrap_servers and api_key and api_secret)
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if not self._enabled or self._task:
            return
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _topic_exists(self) -> bool:
        # List all topics rather than asking for this one by name, so a missing topic
        # is never auto-created by the metadata request.
        meta = AdminClient(self._conf, logger=kafka_logger).list_topics(timeout=5)
        topic_meta = meta.topics.get(self.topic)
        return topic_meta is not None and topic_meta.error is None

    async def _run(self) -> None:
        was_ready: Optional[bool] = None  # None until the first successful check
        while True:
            try:
                ready = await asyncio.to_thread(self._topic_exists)
                if ready != self.store.workstation_efficiency_ready:
                    self.store.workstation_efficiency_ready = ready
                    logger.info(
                        f"Level 2 unlocked: Topic {self.topic} exists" if ready
                        else f"Level 2 locked: Topic {self.topic} is missing",
                        extra=MAJOR,
                    )
                    await self.on_change()
                if ready and was_ready is False and self.on_unlocked:
                    await self.on_unlocked("Level 2")
                was_ready = ready
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Topic check failed: {e}")
            await asyncio.sleep(POLL_SECONDS)


class InventoryBalancesWatcher:
    """
    Polls Confluent Cloud for the `resource_inventory` topic
    (Flink creates it when the attendee runs 01_create_sink.sql for Level 3)
    and keeps `store.resource_inventory_ready` current, so deleting the topic locks Level 3 again.
    Only checks that the topic exists; it never reads records.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str],
        api_key: Optional[str],
        api_secret: Optional[str],
        on_change: Callable[[], Awaitable[None]],
        topic: str = "resource_inventory",
        on_unlocked: Optional[OnUnlocked] = None,
    ):
        self.store = store
        self.topic = topic
        self.on_change = on_change
        self.on_unlocked = on_unlocked
        self._conf = {
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "enable.metrics.push": False,
        }
        self._enabled = bool(KAFKA_AVAILABLE and bootstrap_servers and api_key and api_secret)
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if not self._enabled or self._task:
            return
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _topic_exists(self) -> bool:
        meta = AdminClient(self._conf, logger=kafka_logger).list_topics(timeout=5)
        topic_meta = meta.topics.get(self.topic)
        return topic_meta is not None and topic_meta.error is None

    async def _run(self) -> None:
        was_ready: Optional[bool] = None  # None until the first successful check
        while True:
            try:
                ready = await asyncio.to_thread(self._topic_exists)
                if ready != self.store.resource_inventory_ready:
                    self.store.resource_inventory_ready = ready
                    logger.info(
                        f"Level 3 unlocked: Topic {self.topic} exists" if ready
                        else f"Level 3 locked: Topic {self.topic} is missing",
                        extra=MAJOR,
                    )
                    await self.on_change()
                if ready and was_ready is False and self.on_unlocked:
                    await self.on_unlocked("Level 3")
                was_ready = ready
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Inventory topic check failed: {e}")
            await asyncio.sleep(POLL_SECONDS)


class QueensOrdersWatcher:
    """
    Polls Confluent Cloud for the `queens_orders` topic
    (Flink creates it when the attendee runs 01_create_sink.sql for Level 4)
    and keeps `store.queens_orders_ready` current, so deleting the topic locks Level 4 again.
    Only checks that the topic exists; it never reads records.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str],
        api_key: Optional[str],
        api_secret: Optional[str],
        on_change: Callable[[], Awaitable[None]],
        topic: str = "queens_orders",
        on_unlocked: Optional[OnUnlocked] = None,
    ):
        self.store = store
        self.topic = topic
        self.on_change = on_change
        self.on_unlocked = on_unlocked
        self._conf = {
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "enable.metrics.push": False,
        }
        self._enabled = bool(KAFKA_AVAILABLE and bootstrap_servers and api_key and api_secret)
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if not self._enabled or self._task:
            return
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _topic_exists(self) -> bool:
        meta = AdminClient(self._conf, logger=kafka_logger).list_topics(timeout=5)
        topic_meta = meta.topics.get(self.topic)
        return topic_meta is not None and topic_meta.error is None

    async def _run(self) -> None:
        was_ready: Optional[bool] = None  # None until the first successful check
        while True:
            try:
                ready = await asyncio.to_thread(self._topic_exists)
                if ready != self.store.queens_orders_ready:
                    self.store.queens_orders_ready = ready
                    logger.info(
                        f"Level 4 unlocked: Topic {self.topic} exists" if ready
                        else f"Level 4 locked: Topic {self.topic} is missing",
                        extra=MAJOR,
                    )
                    await self.on_change()
                if ready and was_ready is False and self.on_unlocked:
                    await self.on_unlocked("Level 4")
                was_ready = ready
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Queens orders topic check failed: {e}")
            await asyncio.sleep(POLL_SECONDS)



