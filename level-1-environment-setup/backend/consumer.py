import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Callable, Awaitable

from backend.models import EventEnvelope
from backend.log_setup import MAJOR
from backend.store import DashboardStore

logger = logging.getLogger("hive.consumer")
kafka_logger = logging.getLogger("hive.kafka")

try:
    from confluent_kafka import Consumer as ConfluentConsumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    ConfluentConsumer = None
    KafkaError = None
    KAFKA_AVAILABLE = False


ORDER_TOPIC_NAMES = ["order-placed", "order-fulfilled"]


def _make_group_id(prefix: str, store: DashboardStore) -> str:
    sim_id_short = (store.active_simulation_id or "default")[:8]
    attendee_short = (store.attendee_id or "attendee").split("@")[0].replace(".", "-")[:16]
    return f"hive-{prefix}-{attendee_short}-{sim_id_short}"


class EventConsumerManager:
    """
    Consumes Simulation events from Confluent Cloud and feeds the dashboard store.
    Identical transport to spec-3; only the store differs.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topics: Optional[list] = None,
        on_event_callback: Optional[Callable] = None,
    ):
        self.store = store
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topics = topics or []
        self.on_event_callback = on_event_callback

        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._kafka_consumer = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._run())
        logger.info("Event consumer started.", extra=MAJOR)

    def stop(self):
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
        if self._kafka_consumer:
            try:
                self._kafka_consumer.close()
            except Exception:
                pass
            self._kafka_consumer = None
        logger.info("Event consumer stopped.", extra=MAJOR)

    async def _run(self):
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret and self.topics):
            logger.info("Kafka consumer not started: missing credentials or topics.")
            return

        group_id = _make_group_id("events", self.store)
        logger.info(f"Kafka consumer group: {group_id}, topics: {self.topics}")

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.api_key,
            "sasl.password": self.api_secret,
            "enable.metrics.push": False,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
        self._kafka_consumer = ConfluentConsumer(conf, logger=kafka_logger)
        self._kafka_consumer.subscribe(self.topics, on_assign=self._on_assign)
        subscribed_orders = False
        topic_counts: dict = {}
        last_summary = time.monotonic()

        while self._running:
            try:
                # Level 4 order topics are created by the attendee later and the Simulation
                # server's topic map may not list them; subscribe once they exist.
                if not subscribed_orders and self.store.order_topics_ready:
                    all_topics = list(dict.fromkeys(self.topics + ORDER_TOPIC_NAMES))
                    self._kafka_consumer.subscribe(all_topics, on_assign=self._on_assign)
                    subscribed_orders = True

                # Every 30s, record how many records arrived per topic. A missing order topic
                # here means nothing was published to (or delivered from) it.
                now = time.monotonic()
                if now - last_summary >= 30.0:
                    last_summary = now
                    logger.info(
                        f"Consumer summary (last 30s, records per topic): {topic_counts or 'none'}; "
                        f"order_topics_ready={self.store.order_topics_ready}, "
                        f"orders_placed={self.store.orders_placed}, "
                        f"fulfilled eng/for={self.store.orders_fulfilled_engineer}/{self.store.orders_fulfilled_gatherer}"
                    )
                    topic_counts = {}

                msgs = await asyncio.to_thread(self._kafka_consumer.consume, 200, 0.2)
                if not msgs:
                    continue

                any_updated = False
                for msg in msgs:
                    if msg.error():
                        logger.warning(f"Kafka error: {msg.error()}")
                        continue

                    topic_counts[msg.topic()] = topic_counts.get(msg.topic(), 0) + 1
                    is_order_topic = msg.topic() in ORDER_TOPIC_NAMES

                    try:
                        raw_val = msg.value().decode("utf-8")
                        data = json.loads(raw_val)
                        env = EventEnvelope(**data)
                        if not env.event_type and msg.topic():
                            env.event_type = msg.topic().replace("-", ".")
                    except Exception as parse_err:
                        # Order records are rare and important: surface parse failures.
                        log = logger.warning if is_order_topic else logger.debug
                        log(f"Skipping malformed or unparseable record on {msg.topic()}: {parse_err}")
                        continue

                    if env.event_type == "connection.test":
                        continue

                    changed = self.store.ingest(env)
                    if changed:
                        any_updated = True

                if any_updated and self.on_event_callback:
                    await self.on_event_callback(self.store.snapshot())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Kafka consumer error: {e}")
                await asyncio.sleep(0.5)


class CalculatedValuesConsumer:
    """
    Consumes records from the `hive_job_durations` topic (written by the attendee's Flink SQL)
    and updates `store.job_durations` with the latest elapsed_sim_minutes per subject.

    The topic uses json-registry format; the value is a flat JSON object with the columns
    defined in 01_create_sink.sql.  We only need `subject` and `elapsed_sim_minutes`.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topic: str = "hive_job_durations",
        on_change: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.store = store
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topic = topic
        self.on_change = on_change

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._kafka_consumer = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("CalculatedValues consumer started.", extra=MAJOR)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._kafka_consumer:
            try:
                self._kafka_consumer.close()
            except Exception:
                pass
            self._kafka_consumer = None
        logger.info("CalculatedValues consumer stopped.", extra=MAJOR)

    async def _run(self) -> None:
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret):
            logger.info("CalculatedValues consumer not started: missing credentials.")
            return

        group_id = _make_group_id("cv", self.store)
        logger.info(f"CalculatedValues consumer group: {group_id}, topic: {self.topic}")

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.api_key,
            "sasl.password": self.api_secret,
            "enable.metrics.push": False,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            # Flink writes this topic in Kafka transactions that commit at each checkpoint
            # (about once a minute).  Read uncommitted records so the UI does not wait for
            # the commit; the store only keeps the latest value per subject.
            "isolation.level": "read_uncommitted",
        }
        self._kafka_consumer = ConfluentConsumer(conf, logger=kafka_logger)
        self._kafka_consumer.subscribe([self.topic])

        while self._running:
            try:
                msg = await asyncio.to_thread(self._kafka_consumer.poll, 0.5)
                if msg is None:
                    continue
                if msg.error():
                    logger.debug(f"CalculatedValues Kafka error: {msg.error()}")
                    continue

                try:
                    raw_val = msg.value()
                    if raw_val is None:
                        continue
                    # hive_job_durations uses json-registry (Confluent Schema Registry
                    # JSON format).  The value is prefixed with a 5-byte magic header:
                    # 0x00 (magic byte) + 4-byte big-endian schema ID.  Strip it before
                    # JSON parsing.
                    payload = raw_val
                    if len(payload) > 5 and payload[0] == 0x00:
                        payload = payload[5:]
                    data = json.loads(payload.decode("utf-8"))
                    subject = data.get("subject")
                    elapsed = data.get("elapsed_sim_minutes")
                    if subject and elapsed is not None:
                        changed = self.store.ingest_calculated_value(str(subject), int(elapsed))
                        if changed and self.on_change:
                            await self.on_change()
                    else:
                        logger.debug(f"hive_job_durations record missing subject/elapsed: {data}")
                except Exception as parse_err:
                    logger.warning(f"Skipping malformed hive_job_durations record: {parse_err}")
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CalculatedValues consumer error: {e}")
                await asyncio.sleep(0.5)


class InventoryBalancesConsumer:
    """
    Consumes records from the `hive_inventory_balances` topic (written by the
    attendee's Level 3 Flink SQL) and updates `store.inventory` with the latest
    quantity per (item_type, item_id).

    The topic uses json-registry upsert format; each record is the current balance
    for one item.  Flink writes the table's primary key (simulation_id, run_id,
    item_type, item_id) to the Kafka message *key* and only `quantity` to the value,
    so both must be read.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topic: str = "hive_inventory_balances",
        on_change: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.store = store
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topic = topic
        self.on_change = on_change

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._kafka_consumer = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("InventoryBalances consumer started.", extra=MAJOR)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._kafka_consumer:
            try:
                self._kafka_consumer.close()
            except Exception:
                pass
            self._kafka_consumer = None
        logger.info("InventoryBalances consumer stopped.", extra=MAJOR)

    async def _run(self) -> None:
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret):
            logger.info("InventoryBalances consumer not started: missing credentials.")
            return

        group_id = _make_group_id("inv", self.store)
        logger.info(f"InventoryBalances consumer group: {group_id}, topic: {self.topic}")

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.api_key,
            "sasl.password": self.api_secret,
            "enable.metrics.push": False,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            # Flink commits its output transactions about once a minute.  Read uncommitted
            # records so the UI does not wait; the store only keeps the latest value per item.
            "isolation.level": "read_uncommitted",
        }
        self._kafka_consumer = ConfluentConsumer(conf, logger=kafka_logger)
        self._kafka_consumer.subscribe([self.topic])

        while self._running:
            try:
                msg = await asyncio.to_thread(self._kafka_consumer.poll, 0.5)
                if msg is None:
                    continue
                if msg.error():
                    logger.debug(f"InventoryBalances Kafka error: {msg.error()}")
                    continue

                try:
                    raw_val = msg.value()
                    raw_key = msg.key()
                    if raw_val is None or raw_key is None:
                        continue
                    # Strip 5-byte Schema Registry magic header if present (0x00 + 4-byte schema ID)
                    def _decode(b: bytes) -> dict:
                        if len(b) > 5 and b[0] == 0x00:
                            b = b[5:]
                        return json.loads(b.decode("utf-8"))

                    key = _decode(raw_key)
                    value = _decode(raw_val)
                    run_id    = key.get("run_id")
                    item_type = key.get("item_type")
                    item_id   = key.get("item_id")
                    quantity  = value.get("quantity")
                    if run_id and item_type and item_id and quantity is not None:
                        changed = self.store.ingest_inventory_balance(
                            str(run_id), str(item_type), str(item_id), int(quantity)
                        )
                        if changed and self.on_change:
                            await self.on_change()
                    else:
                        logger.debug(f"hive_inventory_balances record missing fields: {key} {value}")
                except Exception as parse_err:
                    logger.warning(f"Skipping malformed hive_inventory_balances record: {parse_err}")
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"InventoryBalances consumer error: {e}")
                await asyncio.sleep(0.5)
