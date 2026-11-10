"""
In-memory store for the basic connect-simulation dashboard.

Tracks only what the design comp needs:
  - sim_time_minutes    from any event envelope
  - Simulation lifecycle    from simulation.state
  - completed counts     from *.completed event payloads
  - in-progress flags    from *.started / *.completed pairing
  - blocked state        from *.blocked event payloads
  - workstation layout       from gathering/manufacturing/assembly .state events (tier per workstation)
  - workstation inputs       from manufacturing.state / assembly.state (recipes), then *.started payloads
  - job durations        from workstation_efficiency topic (elapsed_sim_minutes per workstation type)
  - Queen's orders       from queens_orders topic (one row per order, Level 4)
  - stream health
"""

import logging
import time
from typing import Dict, List, Optional, Any

from backend.log_setup import MAJOR
from backend.models import EventEnvelope

logger = logging.getLogger("hive.store")


# ── Resource label / icon mapping ────────────────────────────────────────────
# These lists must stay in sync with schemas/simulation_rules_private.json in hive-simulation.
# They are used only to pre-zero completed/active counters before simulation.initialized arrives.
# Assembly stations are not pre-zeroed here — the set is derived dynamically from
# the *.state events.
RESOURCE_STATIONS = ["copper", "energy", "metals", "resin", "silicon"]

MANUFACTURING_STATIONS = [
    "actuator",
    "battery",
    "chassis",
    "electronics",
]

# The parts a robot is built from (the columns of parts_priority_queue).
PART_IDS = ("actuator", "battery", "chassis", "electronics")

# Recent raw events kept per dashboard section (newest first), keyed by event_type prefix.
# "queen" covers queen.worker.ordered and queen.worker.assigned.
EVENT_LOG_CATEGORIES = ("simulation", "gathering", "manufacturing", "assembly", "queen")
EVENT_LOG_LIMIT = 250


class DashboardStore:
    def __init__(self) -> None:
        self.attendee_id: Optional[str] = None
        self.active_simulation_id: Optional[str] = None
        self.server_epoch: Optional[str] = None
        # run_id of the most recent event; matches the run_id column in workstation_efficiency
        self.run_id: Optional[str] = None

        # simulation_config from simulation.initialized — carries workstation tiers,
        # workstation_initial_tiers.
        # None until the first simulation.initialized event is ingested.
        self.simulation_config: Optional[Dict[str, Any]] = None

        # Live workstation layout, built from the gathering/manufacturing/assembly .state events
        # (one message per workstation, the latest wins).
        # workstations: workstation_type → list of {workstation_id, tier}, sorted by workstation_id.
        self.workstations: Dict[str, List[Dict[str, int]]] = {}

        # sim time — updated from every envelope
        self.latest_sim_time_minutes: int = 0
        self.run_generation: int = 0

        # lifecycle — from simulation.state
        self.lifecycle_status: str = "paused"
        self.running: bool = False

        # stream health tracking
        self._last_event_mono: float = 0.0

        # Completed counts: workstation_type / workstation_type / robot_id → int
        self.gathering_completed: Dict[str, int] = {r: 0 for r in RESOURCE_STATIONS}
        self.manufacturing_completed: Dict[str, int] = {s: 0 for s in MANUFACTURING_STATIONS}
        self.assembly_completed: Dict[str, int] = {}  # output_type → count

        # Active jobs: tracks currently in-progress jobs per "slot"
        # gathering: workstation_type → bool
        # manufacturing / assembly: workstation_type → bool
        self.gathering_active: Dict[str, bool] = {r: False for r in RESOURCE_STATIONS}
        self.manufacturing_active: Dict[str, bool] = {s: False for s in MANUFACTURING_STATIONS}
        self.assembly_active: Dict[str, bool] = {}

        # Blocked state: workstation_type → missing_inputs dict (non-empty means blocked)
        self.manufacturing_blocked: Dict[str, Dict[str, int]] = {}
        self.assembly_blocked: Dict[str, Dict[str, int]] = {}

        # Workstation inputs: set from the manufacturing.state / assembly.state recipe at the start of a
        # run (and refreshed from *.started payloads); workstation_type → inputs dict.
        # Preserved across jobs — shows the full recipe the workstation uses.
        self.manufacturing_inputs: Dict[str, Dict[str, int]] = {}
        self.assembly_inputs: Dict[str, Dict[str, int]] = {}

        # Job durations from workstation_efficiency (Flink output):
        # workstation_type → latest elapsed_sim_minutes
        self.job_durations: Dict[str, int] = {}

        # Inventory balances from resource_inventory & parts_inventory (Flink output), kept per run
        # because the topics retain rows from earlier runs:
        # run_id → item_type → item_id → quantity.  item_type: 'resource' | 'part'
        # Independent of reset(): rows can arrive before the new run's first event does.
        self.inventory_by_run: Dict[str, Dict[str, Dict[str, int]]] = {}

        # The Queen's orders from queens_orders (Flink output), kept per run:
        # run_id → order_id → {order_id, robot_type, workstation_type, workstation_id, action, placed_seq, status}
        # status: 'OPEN' | 'IN_ASSEMBLY' | 'ASSIGNED'
        # Independent of reset(): rows can arrive before the new run's first event does.
        self.orders_by_run: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # The parts each order's robot needs, from parts_priority_queue (Flink output), kept per run:
        # run_id → order_id → {actuator, battery, chassis, electronics}
        # Same pattern as orders_by_run. The two topics come from separate Flink jobs, so an
        # order can be in orders_by_run before its parts arrive; it then has no parts yet.
        self.parts_by_run: Dict[str, Dict[str, Dict[str, int]]] = {}

        # Recent events per section, newest first (raw envelopes for the event panels)
        self.events: Dict[str, list] = {c: [] for c in EVENT_LOG_CATEGORIES}
        # Event types already warned about for having no event panel (warn once per type).
        self._unlogged_event_types: set = set()

        # Level 1 gate: every event topic listed by the Simulation server (GET /v1/schemas) exists in Confluent.
        # `event_topics_missing` lists the absent topic names (empty until the first check completes).
        # Unlike the Flink gates this is re-evaluated continuously, so deleting topics re-locks Level 1.
        self.event_topics_ready: bool = False
        self.event_topics_missing: List[str] = []

        # Level 2 gate: the workstation_efficiency topic exists (created by the attendee's Flink SQL).
        # Re-evaluated continuously like Level 1's, so deleting the topic re-locks Level 2.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.workstation_efficiency_ready: bool = False

        # Level 3 gate: resource_inventory & parts_inventory topics exist. Re-evaluated continuously.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.resource_inventory_ready: bool = False

        # Level 4 gate: the queens_orders topic exists. Re-evaluated continuously.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.queens_orders_ready: bool = False

        # The parts_priority_queue topic exists. Only adds the "Parts required" row to the order
        # cards; it does not lock or unlock a level. Independent of the Simulation run.
        self.parts_priority_queue_ready: bool = False

        # Connection to the Simulation server / Confluent, set by auto_connect:
        #   'connecting' | 'connected' | 'failed'
        # `connection_issues` holds plain-language problems (backend.connection_issues.Issue
        # as dicts) to show the attendee; empty unless status is 'failed'.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.connection_status: str = "connecting"
        self.connection_issues: List[Dict[str, Any]] = []

        # Warnings that the schemas in the attendee's Schema Registry do not match what the
        # Simulation server publishes (backend.connection_issues.Issue as dicts). Re-evaluated
        # continuously; the dashboard only warns, the attendee fixes Confluent themselves.
        # Independent of the Simulation run, so reset() leaves it alone.
        self.schema_warnings: List[Dict[str, Any]] = []

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
        self.simulation_config = None
        self.workstations = {}
        self._seen_ids.clear()

    def ingest(self, env: EventEnvelope) -> bool:
        """Returns True if something changed."""
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
            self.simulation_config = None
            self.workstations = {}
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
        elif et not in self._unlogged_event_types:
            self._unlogged_event_types.add(et)
            logger.warning(
                f"Store: event type '{et}' has no event panel, so it is not logged. "
                f"Add '{category}' to EVENT_LOG_CATEGORIES (store.py) and a panel in the level screens."
            )

        if et == "simulation.state":
            prev_status = self.lifecycle_status
            self.lifecycle_status = p.get("lifecycle_status", self.lifecycle_status)
            self.running = p.get("running", self.running)
            if prev_status != self.lifecycle_status:
                logger.info(f"Store: lifecycle_status changed '{prev_status}' -> '{self.lifecycle_status}'")
            return True

        if et == "gathering.started":
            rid = p.get("workstation_type")
            if rid:
                self.gathering_active[rid] = True
            return True

        if et == "gathering.completed":
            rid = p.get("workstation_type")
            if rid:
                self.gathering_active[rid] = False
                self.gathering_completed[rid] = self.gathering_completed.get(rid, 0) + 1
            return True

        if et == "manufacturing.resources.acquired":
            # Resources have been pulled from stock into the station's cart;
            # the job is about to start. No state change needed beyond activity.
            return True

        if et == "manufacturing.started":
            sid = p.get("workstation_type")
            if sid:
                self.manufacturing_active[sid] = True
                self.manufacturing_blocked.pop(sid, None)
                inputs = p.get("inputs")
                if isinstance(inputs, dict):
                    self.manufacturing_inputs[sid] = inputs
            return True

        if et == "manufacturing.completed":
            sid = p.get("workstation_type")
            if sid:
                self.manufacturing_active[sid] = False
                self.manufacturing_blocked.pop(sid, None)
                self.manufacturing_completed[sid] = self.manufacturing_completed.get(sid, 0) + 1
            return True

        if et == "manufacturing.blocked":
            sid = p.get("workstation_type")
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
            sid = p.get("workstation_type")
            if sid:
                self.assembly_active[sid] = True
                self.assembly_blocked.pop(sid, None)
                inputs = p.get("inputs")
                if isinstance(inputs, dict):
                    self.assembly_inputs[sid] = inputs
            return True

        if et == "assembly.completed":
            sid = p.get("workstation_type")
            output_type = p.get("output_type", sid)
            if sid:
                self.assembly_active[sid] = False
                self.assembly_blocked.pop(sid, None)
            if output_type:
                self.assembly_completed[output_type] = self.assembly_completed.get(output_type, 0) + 1
            return True

        if et == "assembly.blocked":
            sid = p.get("workstation_type")
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

        if et in ("gathering.state", "manufacturing.state", "assembly.state"):
            wtype = p.get("workstation_type")
            wid = p.get("workstation_id")
            tier = p.get("tier")
            if wtype and wid and tier:
                self.ingest_workstation_state(wtype, int(wid), int(tier))
                # The recipe is known from the start of a run, before any job has started.
                recipe = p.get("resources_required") if et == "manufacturing.state" else p.get("parts_required")
                if isinstance(recipe, dict):
                    inputs = self.manufacturing_inputs if et == "manufacturing.state" else self.assembly_inputs
                    inputs[wtype] = recipe
            return True

        # simulation.state etc. — still counted as activity
        return True

    def ingest_workstation_state(self, workstation_type: str, workstation_id: int, tier: int) -> None:
        """Set the tier of one workstation. The message carries the whole state, so replays are safe."""
        layout = self.workstations.setdefault(workstation_type, [])
        for entry in layout:
            if entry["workstation_id"] == workstation_id:
                entry["tier"] = tier
                return
        layout.append({"workstation_id": workstation_id, "tier": tier})
        layout.sort(key=lambda e: e["workstation_id"])

    def ingest_calculated_value(self, workstation_type: str, elapsed_sim_minutes: int) -> bool:
        """Update the latest job duration for a workstation_type."""
        self.job_durations[workstation_type] = elapsed_sim_minutes
        return True

    def ingest_inventory_balance(self, run_id: str, item_type: str, item_id: str, quantity: int) -> bool:
        """Update the live inventory balance for one item of one run.

        Returns True only if the value belongs to the current run and changed what is shown.
        """
        if item_type not in ("resource", "part"):
            return False
        run = self.inventory_by_run.setdefault(
            run_id, {"resource": {}, "part": {}}
        )
        run[item_type][item_id] = quantity
        return run_id == self.run_id

    @property
    def inventory(self) -> Dict[str, Dict[str, int]]:
        """Balances for the current run."""
        empty: Dict[str, Dict[str, int]] = {"resource": {}, "part": {}}
        return self.inventory_by_run.get(self.run_id, empty) if self.run_id else empty

    def ingest_queens_order(self, run_id: str, order: Dict[str, Any]) -> bool:
        """Update one order of one run from a queens_orders row.

        Returns True only if the order belongs to the current run and the row changed.
        """
        order_id = order.get("order_id")
        if not order_id:
            return False
        run = self.orders_by_run.setdefault(run_id, {})
        previous = run.get(order_id)
        merged = {**previous, **{k: v for k, v in order.items() if v is not None}} if previous else dict(order)
        run[order_id] = merged
        return run_id == self.run_id and merged != previous

    def ingest_order_parts(self, run_id: str, order_id: str, parts: Dict[str, Any]) -> bool:
        """Set the parts one order's robot needs, from a parts_priority_queue row.

        Parts that are null in the row (the recipe does not use them) are dropped.
        Returns True only if the order belongs to the current run and its parts changed.
        """
        if not order_id:
            return False
        known = {k: int(v) for k, v in parts.items() if k in PART_IDS and v is not None}
        run = self.parts_by_run.setdefault(run_id, {})
        previous = run.get(order_id)
        run[order_id] = known
        return run_id == self.run_id and known != previous

    @property
    def queens_orders(self) -> List[Dict[str, Any]]:
        """All of the current run's orders, in the order the Queen placed them."""
        if not self.run_id:
            return []
        rows = self.orders_by_run.get(self.run_id, {}).values()
        parts = self.parts_by_run.get(self.run_id, {})
        # Attach the parts only when they have arrived, so the card shows no zeros in the gap.
        rows = [{**o, "parts": dict(parts[o["order_id"]])} if parts.get(o["order_id"]) else o for o in rows]
        return sorted(rows, key=lambda o: (o.get("placed_seq") is None, o.get("placed_seq") or 0))

    @property
    def robot_queue(self) -> List[Dict[str, Any]]:
        """The Queen's open queue: OPEN orders, first in first out."""
        return [dict(o) for o in self.queens_orders if o.get("status") == "OPEN"]

    @property
    def orders_in_assembly(self) -> List[Dict[str, Any]]:
        """Orders whose robot is being built (they have left the queue)."""
        return [dict(o) for o in self.queens_orders if o.get("status") == "IN_ASSEMBLY"]

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
            "robot_queue": self.robot_queue,
            "orders_in_assembly": self.orders_in_assembly,
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
            "workstation_efficiency_ready": self.workstation_efficiency_ready,
            "resource_inventory_ready": self.resource_inventory_ready,
            "queens_orders_ready": self.queens_orders_ready,
            "parts_priority_queue_ready": self.parts_priority_queue_ready,
            "simulation_config": self.simulation_config,
            "workstations": {t: [dict(w) for w in ws] for t, ws in self.workstations.items()},
            "connection_status": self.connection_status,
            "connection_issues": [dict(i) for i in self.connection_issues],
            "schema_warnings": [dict(i) for i in self.schema_warnings],
        }
