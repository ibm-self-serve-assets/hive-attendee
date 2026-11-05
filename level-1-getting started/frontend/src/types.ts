/** Workstation tier configuration from simulation.initialized → simulation_config. */
export interface WorkstationTierConfig {
  tier: number;
  interval_sim_minutes: number;
}

/** Configuration block published in simulation.initialized so the frontend never needs
 *  hardcoded copies of initial station tiers. */
export interface SimulationConfig {
  workstation_tiers: WorkstationTierConfig[];
  /** station_id → initial tier number */
  station_initial_tiers: Record<string, number>;
}

/** A raw event envelope as received from Kafka (kept for the event panels). */
export interface HiveEvent {
  event_id: string;
  event_type: string;
  simulation_id?: string | null;
  server_epoch?: string | null;
  run_id?: string | null;
  run_generation: number;
  event_sequence: number;
  state_revision?: number | null;
  schema_version?: number | null;
  sim_time_minutes: number;
  occurred_at?: string | null;
  causation_id?: string | null;
  payload: Record<string, unknown>;
}

export type EventSection = 'gathering' | 'manufacturing' | 'assembly';

/** A plain-language connection problem reported by the backend (backend/connection_issues.py). */
export interface ConnectionIssue {
  code: string;
  /** Where the problem is: the local .env ('config'), the Simulation server, or Confluent. */
  source: 'config' | 'simulation_server' | 'confluent';
  title: string;
  /** What went wrong. */
  message: string;
  /** Technical detail from the underlying error, if any. */
  detail?: string | null;
}

/** One of the Queen's robot orders (a row of the queens_orders Flink topic). */
export interface QueenOrder {
  order_id: string;
  robot_type: 'gatherer' | 'engineer' | 'builder';
  /** Workstation the robot will be applied to, e.g. 'resin'. */
  station: string;
  /** 'add' for a builder, 'upgrade' otherwise. */
  action: 'add' | 'upgrade';
  /** Queue position: event_sequence of the order. Lower is first. */
  placed_seq: number;
  status: 'OPEN' | 'IN_ASSEMBLY' | 'ASSIGNED';
}

/** Shape of the state object sent from the backend SSE stream. */
export interface DashboardState {
  stream_health: 'live' | 'stale' | 'awaiting_events';
  attendee_id?: string | null;
  active_simulation_id: string | null;
  /** run_id of the most recent event (matches the run_id column in workstation_efficiency). */
  run_id: string | null;
  run_generation: number;
  sim_time_minutes: number;
  lifecycle_status: 'paused' | 'running' | 'stopped' | 'expired';
  running: boolean;
  /** The Queen's open queue: OPEN orders in the order they were placed (from queens_orders, Level 4). */
  robot_queue?: QueenOrder[];
  /** Orders whose robot is being built; they have left the queue. */
  orders_in_assembly?: QueenOrder[];

  // Completed counts keyed by station_id / station_id / output_type
  gathering_completed: Record<string, number>;
  manufacturing_completed: Record<string, number>;
  assembly_completed: Record<string, number>;

  // Active (in-progress) flags
  gathering_active: Record<string, boolean>;
  manufacturing_active: Record<string, boolean>;
  assembly_active: Record<string, boolean>;

  // Blocked state: keyed by station_id / station_id; value is missing_inputs (or reason for gathering)
  manufacturing_blocked: Record<string, Record<string, number>>;
  assembly_blocked: Record<string, Record<string, number>>;

  // Recipe inputs captured from *.started events: station_id → { input_id → quantity }
  manufacturing_inputs: Record<string, Record<string, number>>;
  assembly_inputs: Record<string, Record<string, number>>;

  // Latest job durations from the workstation_efficiency Flink topic:
  // station_id → elapsed_sim_minutes
  job_durations: Record<string, number>;

  // Live inventory balances from the resource_inventory and parts_inventory Flink topics (Level 3).
  // inventory.resource / inventory.part → item_id → quantity
  inventory: {
    resource: Record<string, number>;
    part: Record<string, number>;
  };

  // Recent raw events per section, newest first
  events: Record<EventSection, HiveEvent[]>;

  // True when every event topic listed by the Simulation server exists in Confluent (unlocks Level 1)
  event_topics_ready: boolean;
  // Names of the event topics not yet present in Confluent
  event_topics_missing: string[];

  // True once the workstation_efficiency topic exists (created by the attendee's Flink SQL) (unlocks Level 2)
  workstation_efficiency_ready: boolean;

  // True once the resource_inventory and parts_inventory topics exist (created by the attendee's Flink SQL) (unlocks Level 3)
  resource_inventory_ready: boolean;

  // True once the queens_orders topic exists (created by the attendee's Flink SQL) (unlocks Level 4)
  queens_orders_ready: boolean;

  // simulation_config from simulation.initialized — null until the event is received
  simulation_config: SimulationConfig | null;

  /** Live station tiers: station_id → current tier. Seeded from station_initial_tiers,
   *  then updated whenever a *.upgraded event arrives. */
  station_tiers?: Record<string, number>;

  /** Live station slots: station_id → list of { id, tier } objects.
   *  One entry per parallel slot; a Builder order appends a new entry. */
  station_slots?: Record<string, Array<{ id: number; tier: number }>>;

  // Whether the backend has connected your dashboard to the Simulation server and Confluent.
  connection_status: 'connecting' | 'connected' | 'failed';
  // Why the connection failed; empty unless connection_status is 'failed'.
  connection_issues: ConnectionIssue[];
  // Schemas in your Schema Registry that do not match the Simulation server. Warning only;
  // run register_schemas.sh to fix. Empty when they match (or have not been checked yet).
  schema_warnings: ConnectionIssue[];
}

export const EMPTY_STATE: DashboardState = {
  stream_health: 'awaiting_events',
  attendee_id: null,
  active_simulation_id: null,
  run_id: null,
  run_generation: 0,
  sim_time_minutes: 0,
  lifecycle_status: 'paused',
  running: false,
  gathering_completed: {},
  manufacturing_completed: {},
  assembly_completed: {},
  gathering_active: {},
  manufacturing_active: {},
  assembly_active: {},
  manufacturing_blocked: {},
  assembly_blocked: {},
  manufacturing_inputs: {},
  assembly_inputs: {},
  job_durations: {},
  inventory: { resource: {}, part: {} },
  events: { gathering: [], manufacturing: [], assembly: [] },
  event_topics_ready: false,
  event_topics_missing: [],
  workstation_efficiency_ready: false,
  resource_inventory_ready: false,
  queens_orders_ready: false,
  simulation_config: null,
  connection_status: 'connecting',
  connection_issues: [],
  schema_warnings: [],
};

/**
 * Format sim_time_minutes as "Xd XXh XXm".
 * 1 real second = 1 sim minute, so sim_time_minutes counts real seconds elapsed.
 */
export function fmtSimTime(totalMin: number): string {
  const mins = Math.max(0, totalMin);
  const d = Math.floor(mins / (24 * 60));
  const h = Math.floor((mins % (24 * 60)) / 60);
  const m = mins % 60;
  return `${d}d ${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m`;
}
