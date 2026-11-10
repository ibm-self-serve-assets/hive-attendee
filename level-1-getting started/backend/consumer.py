import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional, Callable, Awaitable, Tuple

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

try:
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.json_schema import JSONDeserializer
    from confluent_kafka.serialization import MessageField, SerializationContext
    SCHEMA_REGISTRY_AVAILABLE = True
except ImportError:
    SchemaRegistryClient = None
    JSONDeserializer = None
    MessageField = None
    SerializationContext = None
    SCHEMA_REGISTRY_AVAILABLE = False


def make_event_deserializer(
    schema_registry_url: Optional[str] = None,
    schema_registry_api_key: Optional[str] = None,
    schema_registry_api_secret: Optional[str] = None,
    schema_registry_client: Any = None,
):
    """
    Deserializer for Simulation event records: a 5-byte Schema Registry prefix (0x00 + schema id)
    followed by JSON. The writer schema is fetched from Schema Registry by id and the record is
    validated against it. Returns None when Schema Registry is not configured.
    """
    if not SCHEMA_REGISTRY_AVAILABLE:
        return None
    if schema_registry_client is None:
        if not (schema_registry_url and schema_registry_api_key and schema_registry_api_secret):
            return None
        schema_registry_client = SchemaRegistryClient({
            "url": schema_registry_url,
            "basic.auth.user.info": f"{schema_registry_api_key}:{schema_registry_api_secret}",
        })
    return JSONDeserializer(schema_str=None, schema_registry_client=schema_registry_client)


def _make_group_id(name: str, store: DashboardStore) -> str:
    """Consumer group id: <name>-<attendee>, e.g. events-hive-003 for ATTENDEE_ID queen-003.

    One stable group per consumer. A leading "queen-" in the attendee id is shown as "hive-".
    """
    attendee_short = (store.attendee_id or "attendee").split("@")[0].replace(".", "-")[:16]
    if attendee_short.startswith("queen-"):
        attendee_short = "hive-" + attendee_short[len("queen-"):]
    return f"{name}-{attendee_short}"


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
        schema_registry_url: Optional[str] = None,
        schema_registry_api_key: Optional[str] = None,
        schema_registry_api_secret: Optional[str] = None,
        deserializer: Any = None,
    ):
        self.store = store
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topics = topics or []
        self.on_event_callback = on_event_callback
        self.deserializer = deserializer or make_event_deserializer(
            schema_registry_url, schema_registry_api_key, schema_registry_api_secret,
        )

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
                # close() sends LeaveGroup. If it does not happen, the broker keeps this
                # member until its session expires and the next consumer in the group waits.
                self._kafka_consumer.close()
            except Exception as e:
                logger.warning(f"Event consumer could not leave its group cleanly: {e}")
            self._kafka_consumer = None
        logger.info("Event consumer stopped.", extra=MAJOR)

    def decode(self, msg) -> EventEnvelope:
        """Turn one Kafka record into an EventEnvelope. Raises if it does not match its schema."""
        data = self.deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
        env = EventEnvelope(**data)
        if not env.event_type and msg.topic():
            env.event_type = msg.topic().replace("-", ".")
        return env

    async def _run(self):
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret):
            logger.info("Event consumer not started: Kafka client or credentials are missing.")
            return
        if not self.topics:
            logger.info("Event consumer waiting: no topics yet. It starts once the Simulation is connected.")
            return
        if self.deserializer is None:
            logger.warning("Kafka consumer not started: Schema Registry is not configured.")
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
            # The group id is stable, so a backend restart (e.g. uvicorn --reload) rejoins the
            # same group. If the old process did not leave cleanly, the broker holds the
            # partitions until its session expires (librdkafka default: 45 s) and nothing is
            # consumed meanwhile. A short session makes that gap a few seconds.
            "session.timeout.ms": 10000,
        }
        self._kafka_consumer = ConfluentConsumer(conf, logger=kafka_logger)
        joined_at = time.monotonic()

        def on_assign(consumer, partitions):
            consumer.assign(partitions)
            logger.info(
                f"Kafka consumer {group_id}: {len(partitions)} partitions assigned "
                f"{time.monotonic() - joined_at:.1f}s after joining the group"
            )

        self._kafka_consumer.subscribe(self.topics, on_assign=on_assign)
        topic_counts: dict = {}
        last_summary = time.monotonic()

        while self._running:
            try:
                now = time.monotonic()
                if now - last_summary >= 30.0:
                    last_summary = now
                    logger.info(f"Consumer summary (last 30s, records per topic): {topic_counts or 'none'}")
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

                    try:
                        env = self.decode(msg)
                    except Exception as parse_err:
                        logger.debug(f"Skipping malformed or unparseable record on {msg.topic()}: {parse_err}")
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
    Consumes records from the `workstation_efficiency` topic (written by the attendee's Flink SQL)
    and updates `store.job_durations` with the latest elapsed_sim_minutes per workstation_type.

    The topic uses json-registry format; the value is a flat JSON object with the columns
    defined in 01_create_sink.sql.  We only need `workstation_type` and `elapsed_sim_minutes`.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topic: str = "workstation_efficiency",
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

        group_id = _make_group_id("efficiency", self.store)
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
            # the commit; the store only keeps the latest value per workstation_type.
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
                    # workstation_efficiency uses json-registry (Confluent Schema Registry
                    # JSON format).  The value is prefixed with a 5-byte magic header:
                    # 0x00 (magic byte) + 4-byte big-endian schema ID.  Strip it before
                    # JSON parsing.
                    payload = raw_val
                    if len(payload) > 5 and payload[0] == 0x00:
                        payload = payload[5:]
                    data = json.loads(payload.decode("utf-8"))
                    workstation_type = data.get("workstation_type")
                    elapsed = data.get("elapsed_sim_minutes")
                    if workstation_type and elapsed is not None:
                        changed = self.store.ingest_calculated_value(str(workstation_type), int(elapsed))
                        if changed and self.on_change:
                            await self.on_change()
                    else:
                        logger.debug(f"workstation_efficiency record missing workstation_type/elapsed: {data}")
                except Exception as parse_err:
                    logger.warning(f"Skipping malformed workstation_efficiency record: {parse_err}")
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CalculatedValues consumer error: {e}")
                await asyncio.sleep(0.5)


class InventoryBalancesConsumer:
    """
    Consumes records from the `resource_inventory` and `parts_inventory` topics
    (written by the attendee's Level 3 Flink SQL) and updates `store.inventory`
    with the latest quantity per (item_type, item_id).

    The topics use json-registry upsert format; each record is the current balance
    for one item. Flink writes the table's primary key (simulation_id, run_id,
    resource_id/part_id) to the Kafka message *key* and only `quantity` to the value,
    so both must be read.
    """

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topics: Tuple[str, ...] = ("resource_inventory", "parts_inventory"),
        on_change: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.store = store
        self.bootstrap_servers = bootstrap_servers
        self.api_key = api_key
        self.api_secret = api_secret
        self.topics = list(topics)
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

        group_id = _make_group_id("inventory", self.store)
        logger.info(f"InventoryBalances consumer group: {group_id}, topics: {self.topics}")

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
        self._kafka_consumer.subscribe(self.topics)

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
                    if not item_type:
                        topic_name = msg.topic() or ""
                        if "part" in topic_name:
                            item_type = "part"
                        else:
                            item_type = "resource"

                    item_id = key.get("item_id")
                    if not item_id:
                        item_id = key.get("part_id") if item_type == "part" else key.get("resource_id")

                    quantity  = value.get("quantity")
                    if run_id and item_type and item_id and quantity is not None:
                        changed = self.store.ingest_inventory_balance(
                            str(run_id), str(item_type), str(item_id), int(quantity)
                        )
                        if changed and self.on_change:
                            await self.on_change()
                    else:
                        logger.debug(f"inventory record missing fields: {key} {value}")
                except Exception as parse_err:
                    logger.warning(f"Skipping malformed inventory record: {parse_err}")
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"InventoryBalances consumer error: {e}")
                await asyncio.sleep(0.5)


class QueensOrdersConsumer:
    """
    Consumes records from the `queens_orders` topic (written by the attendee's
    Level 4 Flink SQL) and updates `store.orders_by_run` with the latest row per order.

    The topic uses json-registry upsert format: Flink writes the table's primary key
    (simulation_id, run_id, order_id) to the Kafka message *key* and the remaining
    columns (robot_type, workstation_type, workstation_id, action, placed_seq, status) to the value, so both
    must be read.
    """

    # Used in the Kafka group id and in log messages; the parts consumer overrides them.
    group_prefix = "orders"
    name = "QueensOrders"

    def __init__(
        self,
        store: DashboardStore,
        bootstrap_servers: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        topic: str = "queens_orders",
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
        logger.info(f"{self.name} consumer started.", extra=MAJOR)

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
        logger.info(f"{self.name} consumer stopped.", extra=MAJOR)

    def _ingest(self, run_id: str, order_id: str, value: dict) -> bool:
        """Store one row of the topic. Returns True if the current run's screen changed."""
        order = {
            "order_id": order_id,
            "robot_type": value.get("robot_type"),
            "workstation_type": value.get("workstation_type"),
            "workstation_id": value.get("workstation_id"),
            "action": value.get("action"),
            "placed_seq": value.get("placed_seq"),
            "status": value.get("status"),
        }
        return self.store.ingest_queens_order(run_id, order)

    async def _run(self) -> None:
        if not (KAFKA_AVAILABLE and self.bootstrap_servers and self.api_key and self.api_secret):
            logger.info(f"{self.name} consumer not started: missing credentials.")
            return

        group_id = _make_group_id(self.group_prefix, self.store)
        logger.info(f"{self.name} consumer group: {group_id}, topic: {self.topic}")

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
            # records so the UI does not wait; the store only keeps the latest row per order.
            "isolation.level": "read_uncommitted",
        }
        self._kafka_consumer = ConfluentConsumer(conf, logger=kafka_logger)
        self._kafka_consumer.subscribe([self.topic])

        def _decode(b: bytes) -> dict:
            # Strip 5-byte Schema Registry magic header if present (0x00 + 4-byte schema ID)
            if len(b) > 5 and b[0] == 0x00:
                b = b[5:]
            return json.loads(b.decode("utf-8"))

        while self._running:
            try:
                msg = await asyncio.to_thread(self._kafka_consumer.poll, 0.5)
                if msg is None:
                    continue
                if msg.error():
                    logger.debug(f"{self.name} Kafka error: {msg.error()}")
                    continue

                try:
                    raw_val = msg.value()
                    raw_key = msg.key()
                    if raw_val is None or raw_key is None:
                        continue
                    key = _decode(raw_key)
                    value = _decode(raw_val)
                    run_id = key.get("run_id")
                    order_id = key.get("order_id")
                    if run_id and order_id:
                        changed = self._ingest(str(run_id), str(order_id), value)
                        if changed and self.on_change:
                            await self.on_change()
                    else:
                        logger.debug(f"{self.topic} record missing fields: {key} {value}")
                except Exception as parse_err:
                    logger.warning(f"Skipping malformed {self.topic} record: {parse_err}")
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"{self.name} consumer error: {e}")
                await asyncio.sleep(0.5)


class PartsPriorityQueueConsumer(QueensOrdersConsumer):
    """
    Consumes the `parts_priority_queue` topic (Level 4 Flink SQL, steps 4 to 6): the Queen's
    orders with the parts each robot needs. Same key and value layout as `queens_orders`; only
    the parts are kept, in `store.parts_by_run`, so the order cards can show "Parts required".
    """

    group_prefix = "parts-priority"
    name = "PartsPriorityQueue"

    def __init__(self, *args, topic: str = "parts_priority_queue", **kwargs):
        super().__init__(*args, topic=topic, **kwargs)

    def _ingest(self, run_id: str, order_id: str, value: dict) -> bool:
        return self.store.ingest_order_parts(run_id, order_id, value)
