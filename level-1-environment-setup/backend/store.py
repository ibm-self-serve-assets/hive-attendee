"""
In-memory store for the basic connect-simulation dashboard.

Tracks only what the design comp needs:
  - sim_time_minutes    from any event envelope
  - Simulation lifecycle    from simulation.state
  - completed counts     from *.completed event payloads
  - in-progress flags    from *.started / *.completed pairing
  - blocked state        from *.blocked event payloads
  - workstation inputs       from *.started event payloads (full recipe inputs)
  - job durations        from hive_job_durations topic (elapsed_sim_minutes per station)
  - stream health
"""

import logging
import time
from typing import Dict, List, Optional, Any

from backend.log_setup import MAJOR
from backend.models import EventEnvelope

logger = logging.getLogger("hive.store")


# ── Resource label / icon mapping ────────────────────────────────────────────
RESOURCE_STATIONS = ["copper", "energy", "metals", "resin", "silicon"]

# Parts manufacturing stations
MANUFACTURING_STATIONS = [
    "actuator_fabrication",
    "battery_assembly",
    "structural_molding",
    "electronics_assembly",
]

# Assembly stations and their robot output
ASSEMBLY_STATIONS = {
    "worker_assembly": "engineer",
    "gatherer_assembly": "gatherer",
}

# Recent raw events kept per dashboard section (newest first), keyed by event_type prefix.
EVENT_LOG_CATEGORIES = ("gathering", "manufacturing", "assembly")
EVENT_LOG_LIMIT = 100


class DashboardStore:
    def __init__(self) -> None:
        self.attendee_id: Optional[str] = None
        self.active_simulation_id: Optional[str] = None
        self.server_epoch: Optional[str] = None
        # run_id of the most recent event; matches the run_id column in hive_job_durations
        self.run_id: Optional[str] = None

        # simulation_config from simulation.initialized — carries workstation tiers,
        # robot prices, max_station_slots, and station_initial_tiers.
        # None until the first simulation.initialized event is ingested.
        self.simulation_config: Optional[Dict[str, Any]] = None

        # sim time — updated from every envelope
        self.latest_sim_time_minutes: int = 0
        self.run_generation: int = 0

        # lifecycle — from simulation.state
        self.lifecycle_status: str = "paused"
        self.running: bool = False

        # stream health tracking
        self._last_event_mono: float = 0.0

        # Completed counts: station_id / station_id / robot_id → int
        self.gathering_completed: Dict[str, int] = {r: 0 for r in RESOURCE_STATIONS}
        self.manufacturing_completed: Dict[str, int] = {s: 0 for s in MANUFACTURING_STATIONS}
        self.assembly_completed: Dict[str, int] = {}  # output_type → count

        # Active jobs: tracks currently in-progress jobs per "slot"
        # gathering: station_id → bool
        # manufacturing / assembly: station_id → bool
        self.gathering_active: Dict[str, bool] = {r: False for r in RESOURCE_STATIONS}
        self.manufacturing_active: Dict[str, bool] = {s: False for s in MANUFACTURING_STATIONS}
        self.assembly_active: Dict[str, bool] = {}

        # Blocked state: station/resource → missing_inputs dict (non-empty means blocked)
        self.manufacturing_blocked: Dict[str, Dict[str, int]] = {}
        self.assembly_blocked: Dict[str, Dict[str, int]] = {}

        # Station inputs: captured from *.started payloads; station_id → inputs dict
        # Preserved across jobs — shows the full recipe the workstation uses.
        self.manufacturing_inputs: Dict[str, Dict[str, int]] = {}
        self.assembly_inputs: Dict[str, Dict[str, int]] = {}

        # Job durations from hive_job_durations (Flink output):
        # subject (station_id / station_id) → latest elapsed_sim_minutes
        self.job_durations: Dict[str, int] = {}

        # Inventory balances from hive_inventory_balances (Flink output), kept per run
        # because the topic retains rows from earlier runs:
        # run_id → item_type → item_id → quantity.  item_type: 'resource' | 'part' | 'robot'
        # Independent of reset(): rows can arrive before the new run's first event does.
        self.inventory_by_run: Dict[str, Dict[str, Dict[str, int]]] = {}

        # Recent events per section, newest first (raw envelopes for the event panels)
        self.events: Dict[str, list] = {c: [] for c in EVENT_LOG_CATEGORIES}

        # Level 1 gate: every topic in spec-shared/schemas/event_payloads.json exists in Confluent.
        # `event_topics_missing` lists the absent topic names (empty until the first check completes).
        # Unlike the Flink gates this is re-evaluated continuously, so deleting topics re-locks Level 1.
        self.event_topics_ready: bool = False
        self.event_topics_missing: List[str] = []

        # Level 2 gate: the hive_job_durations topic exists (created by the attendee's Flink SQL).
        # Independent of the Simulation run, so reset() leaves it alone.
        self.hive_job_durations_ready: bool = False

        # Level 3 gate: the hive_inventory_balances topic exists.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.hive_inventory_balances_ready: bool = False

        # Level 4 order fulfillment state — reset on new run_generation
        self.orders_placed: int = 0
        self.open_order: Optional[Dict[str, Any]] = None
        self.orders_fulfilled_engineer: int = 0
        self.orders_fulfilled_gatherer: int = 0
        self.treasury_coins: int = 0

        # Level 4 gate: both order topics exist in Confluent (created by provision_order_topics.sh)
        self.order_topics_ready: bool = False

        # Connection to the Simulation server / Confluent, set by auto_connect:
        #   'connecting' | 'connected' | 'failed'
        # `connection_issues` holds plain-language problems (backend.connection_issues.Issue
        # as dicts) to show the attendee; empty unless status is 'failed'.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.connection_status: str = "connecting"
        self.connection_issues: List[Dict[str, Any]] = []

        # Dedup
        self._seen_ids: Dict[str, None] = {}
        self._seen_max = 5000

    def reset(self) -> None:
        self.latest_sim_time_minutes = 0
        self.run_generation = 0
        self.run_id = None
        self.lifecycle_status = "paused"
        self.running = False
        self.gathering_completed = {r: 0 for r in RESOURCE_STATIONS}
        self.manufacturing_completed = {s: 0 for s in MANUFACTURING_STATIONS}
        self.assembly_completed = {}
        self.gathering_active = {r: False for r in RESOURCE_STATIONS}
        self.manufacturing_active = {s: False for s in MANUFACTURING_STATIONS}
        self.assembly_active = {}
        self.manufacturing_blocked = {}
        self.assembly_blocked = {}
        self.manufacturing_inputs = {}
        self.assembly_inputs = {}
        self.job_durations = {}
        self.events = {c: [] for c in EVENT_LOG_CATEGORIES}
        self.orders_placed = 0
        self.open_order = None
        self.orders_fulfilled_engineer = 0
        self.orders_fulfilled_gatherer = 0
        self.treasury_coins = 0
        self.simulation_config = None
        self._seen_ids.clear()

    def ingest(self, env: EventEnvelope) -> bool:
        """Returns True if something changed."""
        # Skip probes
        if env.event_type == "connection.test":
            return False

        # Simulation identity guard
        if self.active_simulation_id and env.simulation_id != self.active_simulation_id:
            return False
        if not self.active_simulation_id and self.server_epoch and env.server_epoch != self.server_epoch:
            return False

        # Dedup
        if env.event_id in self._seen_ids:
            return False
        self._seen_ids[env.event_id] = None
        if len(self._seen_ids) > self._seen_max:
            # evict oldest
            oldest = next(iter(self._seen_ids))
            del self._seen_ids[oldest]

        # An "expired" snapshot freezes the run: it must never wipe the final counts
        # or sim time the dashboard is showing (e.g. when the server's TTL expires a
        # freshly restarted run that is still at 0d 00h 00m).
        is_expired_snapshot = (
            env.event_type == "simulation.state"
            and env.payload.get("lifecycle_status") == "expired"
        )

        # Drop events that belong to a previous run generation entirely. This prevents
        # Kafka replay of old events (after a backend restart + sim restart) from
        # polluting the store before the new run's first snapshot arrives.
        if self.run_generation > 0 and not is_expired_snapshot and env.run_generation < self.run_generation:
            return False

        # Always advance sim time and record activity
        if is_expired_snapshot:
            self.run_generation = max(self.run_generation, env.run_generation)
            self.latest_sim_time_minutes = max(self.latest_sim_time_minutes, env.sim_time_minutes)
            logger.info(f"Store: simulation run {self.run_id[:8] if self.run_id else ''} expired at {self.latest_sim_time_minutes}m")
        elif env.run_generation > self.run_generation:
            logger.info(f"Store: advanced to run_generation {env.run_generation}")
            self.run_generation = env.run_generation
            self.latest_sim_time_minutes = env.sim_time_minutes
            self.gathering_completed = {r: 0 for r in RESOURCE_STATIONS}
            self.manufacturing_completed = {s: 0 for s in MANUFACTURING_STATIONS}
            self.assembly_completed = {}
            self.manufacturing_blocked = {}
            self.assembly_blocked = {}
            self.manufacturing_inputs = {}
            self.assembly_inputs = {}
            self.job_durations = {}
            self.events = {c: [] for c in EVENT_LOG_CATEGORIES}
            self.orders_placed = 0
            self.open_order = None
            self.orders_fulfilled_engineer = 0
            self.orders_fulfilled_gatherer = 0
            self.treasury_coins = 0
            self.simulation_config = None
        elif env.sim_time_minutes > self.latest_sim_time_minutes:
            self.latest_sim_time_minutes = env.sim_time_minutes
        self._last_event_mono = time.monotonic()
        if env.run_id:
            self.run_id = env.run_id

        et = env.event_type
        p = env.payload

        category = et.split(".", 1)[0]
        if category in self.events:
            log = self.events[category]
            log.insert(0, env.model_dump())
            del log[EVENT_LOG_LIMIT:]

        if et == "simulation.state":
            prev_status = self.lifecycle_status
            self.lifecycle_status = p.get("lifecycle_status", self.lifecycle_status)
            self.running = p.get("running", self.running)
            if prev_status != self.lifecycle_status:
                logger.info(f"Store: lifecycle_status changed '{prev_status}' -> '{self.lifecycle_status}'")
            # When the server is in debug mode it embeds ground-truth inventory
            # directly in the simulation.state payload so the attendee screen can
            # show it without waiting for a Flink hive_inventory_balances topic.
            debug_inv = p.get("debug_mode_instructor_only")
            if debug_inv and isinstance(debug_inv, dict) and self.run_id:
                run = self.inventory_by_run.setdefault(
                    self.run_id, {"resource": {}, "part": {}, "robot": {}}
                )
                for itype in ("resource", "part", "robot"):
                    vals = debug_inv.get(itype)
                    if isinstance(vals, dict):
                        run[itype] = dict(vals)
            return True

        if et == "gathering.started":
            rid = p.get("station_id")
            if rid:
                self.gathering_active[rid] = True
            return True

        if et == "gathering.completed":
            rid = p.get("station_id")
            if rid:
                self.gathering_active[rid] = False
                self.gathering_completed[rid] = self.gathering_completed.get(rid, 0) + 1
            return True

        if et == "manufacturing.resources.acquired":
            # Resources have been pulled from stock into the station's cart;
            # the job is about to start. No state change needed beyond activity.
            return True

        if et == "manufacturing.started":
            sid = p.get("station_id")
            if sid:
                self.manufacturing_active[sid] = True
                self.manufacturing_blocked.pop(sid, None)
                inputs = p.get("inputs")
                if isinstance(inputs, dict):
                    self.manufacturing_inputs[sid] = inputs
            return True

        if et == "manufacturing.completed":
            sid = p.get("station_id")
            if sid:
                self.manufacturing_active[sid] = False
                self.manufacturing_blocked.pop(sid, None)
                self.manufacturing_completed[sid] = self.manufacturing_completed.get(sid, 0) + 1
            return True

        if et == "manufacturing.blocked":
            sid = p.get("station_id")
            if sid:
                self.manufacturing_active[sid] = False
                missing = p.get("missing_inputs", {})
                self.manufacturing_blocked[sid] = missing
            return True

        if et == "assembly.parts.acquired":
            # Parts have been pulled from stock into the station's cart;
            # the assembly job is about to start. No state change needed beyond activity.
            return True

        if et == "assembly.started":
            sid = p.get("station_id")
            if sid:
                self.assembly_active[sid] = True
                self.assembly_blocked.pop(sid, None)
                inputs = p.get("inputs")
                if isinstance(inputs, dict):
                    self.assembly_inputs[sid] = inputs
            return True

        if et == "assembly.completed":
            sid = p.get("station_id")
            output_type = p.get("output_type", sid)
            if sid:
                self.assembly_active[sid] = False
                self.assembly_blocked.pop(sid, None)
            if output_type:
                self.assembly_completed[output_type] = self.assembly_completed.get(output_type, 0) + 1
            return True

        if et == "assembly.blocked":
            sid = p.get("station_id")
            if sid:
                self.assembly_active[sid] = False
                missing = p.get("missing_inputs", {})
                self.assembly_blocked[sid] = missing
            return True

        if et == "simulation.initialized":
            cfg = p.get("simulation_config")
            if isinstance(cfg, dict):
                self.simulation_config = cfg
            return True

        if et == "order.placed":
            self.orders_placed += 1
            self.open_order = {
                "order_id": p.get("order_id"),
                "quantity_engineer": p.get("quantity_engineer", 0),
                "quantity_gatherer": p.get("quantity_gatherer", 0),
            }
            return True

        if et == "order.fulfilled":
            if self.open_order and self.open_order.get("order_id") == p.get("order_id"):
                self.open_order = None
            q_eng = p.get("quantity_engineer", 0)
            q_for = p.get("quantity_gatherer", 0)
            self.orders_fulfilled_engineer += q_eng
            self.orders_fulfilled_gatherer += q_for
            self.treasury_coins += p.get("coins_received", 0)
            return True

        # simulation.state (non-order), etc. — still counted as activity
        return True

    def ingest_calculated_value(self, subject: str, elapsed_sim_minutes: int) -> bool:
        """Update the latest job duration for a subject (station_id or station_id)."""
        self.job_durations[subject] = elapsed_sim_minutes
        return True

    def ingest_inventory_balance(self, run_id: str, item_type: str, item_id: str, quantity: int) -> bool:
        """Update the live inventory balance for one item of one run.

        Returns True only if the value belongs to the current run and changed what is shown.
        """
        if item_type not in ("resource", "part", "robot"):
            return False
        run = self.inventory_by_run.setdefault(
            run_id, {"resource": {}, "part": {}, "robot": {}}
        )
        run[item_type][item_id] = quantity
        return run_id == self.run_id

    @property
    def inventory(self) -> Dict[str, Dict[str, int]]:
        """Balances for the current run."""
        empty: Dict[str, Dict[str, int]] = {"resource": {}, "part": {}, "robot": {}}
        return self.inventory_by_run.get(self.run_id, empty) if self.run_id else empty

    def get_stream_health(self) -> str:
        if self._last_event_mono == 0.0:
            return "awaiting_events"
        age = time.monotonic() - self._last_event_mono
        return "live" if age <= 8.0 else "stale"

    def snapshot(self) -> Dict[str, Any]:
        return {
            "stream_health": self.get_stream_health(),
            "attendee_id": self.attendee_id,
            "active_simulation_id": self.active_simulation_id,
            "run_id": self.run_id,
            "run_generation": self.run_generation,
            "sim_time_minutes": self.latest_sim_time_minutes,
            "lifecycle_status": self.lifecycle_status,
            "running": self.running,
            "gathering_completed": dict(self.gathering_completed),
            "manufacturing_completed": dict(self.manufacturing_completed),
            "assembly_completed": dict(self.assembly_completed),
            "gathering_active": dict(self.gathering_active),
            "manufacturing_active": dict(self.manufacturing_active),
            "assembly_active": dict(self.assembly_active),
            "manufacturing_blocked": {k: dict(v) for k, v in self.manufacturing_blocked.items()},
            "assembly_blocked": {k: dict(v) for k, v in self.assembly_blocked.items()},
            "manufacturing_inputs": {k: dict(v) for k, v in self.manufacturing_inputs.items()},
            "assembly_inputs": {k: dict(v) for k, v in self.assembly_inputs.items()},
            "job_durations": dict(self.job_durations),
            "inventory": {k: dict(v) for k, v in self.inventory.items()},
            "events": {c: list(evs) for c, evs in self.events.items()},
            "event_topics_ready": self.event_topics_ready,
            "event_topics_missing": list(self.event_topics_missing),
            "hive_job_durations_ready": self.hive_job_durations_ready,
            "hive_inventory_balances_ready": self.hive_inventory_balances_ready,
            "simulation_config": self.simulation_config,
            "orders_placed": self.orders_placed,
            "open_order": dict(self.open_order) if self.open_order else None,
            "orders_fulfilled_engineer": self.orders_fulfilled_engineer,
            "orders_fulfilled_gatherer": self.orders_fulfilled_gatherer,
            "treasury_coins": self.treasury_coins,
            "order_topics_ready": self.order_topics_ready,
            "connection_status": self.connection_status,
            "connection_issues": [dict(i) for i in self.connection_issues],
        }
