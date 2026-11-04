import asyncio
import logging
from typing import Awaitable, Callable, List, Optional, Tuple

import httpx

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


def fetch_event_topic_names(server_url: str, token: Optional[str], attendee_id: Optional[str]) -> List[str]:
    """
    Topic names the Level 1 provisioning script creates: the ``topic`` of every entry the
    Simulation server publishes at GET /v1/schemas. Raises on any failure.
    """
    headers = {"Authorization": f"Bearer {token}"}
    if attendee_id:
        headers["X-Attendee-Id"] = attendee_id
    r = httpx.get(f"{server_url}/v1/schemas", headers=headers, timeout=8.0)
    r.raise_for_status()
    return [s["topic"] for s in r.json()["subjects"]]


# Called with a level label when that level's gate goes from not met to met.
# Not called for a gate that is already met the first time it is checked.
OnUnlocked = Callable[[str], Awaitable[None]]


class EventTopicsWatcher:
    """
    Polls Confluent Cloud for the Simulation event topics listed by the Simulation server
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
        topic_source: Optional[Callable[[], List[str]]] = None,
    ):
        self.store = store
        self.on_change = on_change
        self.on_unlocked = on_unlocked
        # Returns the event topic names. Asked again on every poll until it succeeds once.
        self._topic_source = topic_source
        self._topics: Optional[List[str]] = None
        self._conf = {
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "enable.metrics.push": False,
        }
        self._enabled = bool(KAFKA_AVAILABLE and bootstrap_servers and api_key and api_secret and topic_source)
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
        # The list comes from the Simulation server; ask once and keep it. If the server is
        # not reachable yet this raises, the gate stays locked and the next poll tries again.
        if self._topics is None:
            self._topics = self._topic_source()
        topics = self._topics
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
    Polls Confluent Cloud for the `resource_inventory` and `parts_inventory` topics
    (Flink creates them when the attendee runs 01_create_resource_sink.sql and 02_create_parts_sink.sql for Level 3)
    and keeps `store.resource_inventory_ready` current, so deleting either topic locks Level 3 again.
    Only checks that the topics exist; it never reads records.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str],
        api_key: Optional[str],
        api_secret: Optional[str],
        on_change: Callable[[], Awaitable[None]],
        topics: Tuple[str, ...] = ("resource_inventory", "parts_inventory"),
        on_unlocked: Optional[OnUnlocked] = None,
    ):
        self.store = store
        self.topics = topics
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
        return all(
            meta.topics.get(t) is not None and meta.topics.get(t).error is None
            for t in self.topics
        )

    async def _run(self) -> None:
        was_ready: Optional[bool] = None  # None until the first successful check
        while True:
            try:
                ready = await asyncio.to_thread(self._topic_exists)
                if ready != self.store.resource_inventory_ready:
                    self.store.resource_inventory_ready = ready
                    topics_str = ", ".join(self.topics)
                    logger.info(
                        f"Level 3 unlocked: Topics {topics_str} exist" if ready
                        else f"Level 3 locked: Topics {topics_str} missing",
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



