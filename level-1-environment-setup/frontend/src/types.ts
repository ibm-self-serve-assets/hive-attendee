/** Workstation tier configuration from simulation.initialized → simulation_config. */
export interface WorkstationTierConfig {
  tier: number;
  cost_purchase: number;
  cost_upgrade: number;
  interval_sim_minutes: number;
}

/** Configuration block published in simulation.initialized so the frontend never needs
 *  hardcoded copies of tier costs, robot prices, or initial station tiers. */
export interface SimulationConfig {
  workstation_tiers: WorkstationTierConfig[];
  /** robot_type → price_in_coins */
  robot_prices: Record<string, number>;
  max_station_slots: number;
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

/** Shape of the state object sent from the backend SSE stream. */
export interface DashboardState {
  stream_health: 'live' | 'stale' | 'awaiting_events';
  attendee_id?: string | null;
  active_simulation_id: string | null;
  /** run_id of the most recent event (matches the run_id column in hive_job_durations). */
  run_id: string | null;
  run_generation: number;
  sim_time_minutes: number;
  lifecycle_status: 'paused' | 'running' | 'stopped' | 'expired';
  running: boolean;

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

  // Latest job durations from the hive_job_durations Flink topic:
  // subject (station_id or station_id) → elapsed_sim_minutes
  job_durations: Record<string, number>;

  // Live inventory balances from the hive_inventory_balances Flink topic (Level 3).
  // inventory.resource / inventory.part / inventory.robot → item_id → quantity
  inventory: {
    resource: Record<string, number>;
    part: Record<string, number>;
    robot: Record<string, number>;
  };

  // Recent raw events per section, newest first
  events: Record<EventSection, HiveEvent[]>;

  // True when every topic in spec-shared/schemas/event_payloads.json exists in Confluent (unlocks Level 1)
  event_topics_ready: boolean;
  // Names of the event topics not yet present in Confluent
  event_topics_missing: string[];

  // True once the hive_job_durations topic exists (created by the attendee's Flink SQL) (unlocks Level 2)
  hive_job_durations_ready: boolean;

  // True once the hive_inventory_balances topic exists (created by the attendee's Flink SQL) (unlocks Level 3)
  hive_inventory_balances_ready: boolean;

  // simulation_config from simulation.initialized — null until the event is received
  simulation_config: SimulationConfig | null;

  // Level 4 order fulfillment counts (reset on new run_generation)
  orders_placed: number;
  /** The one currently open order (standing-order model); null until order.placed arrives. */
  open_order: { order_id: string; quantity_engineer: number; quantity_gatherer: number } | null;
  orders_fulfilled_engineer: number;
  orders_fulfilled_gatherer: number;
  /** Treasury coins — authoritative sum from order.fulfilled events (backend-driven). */
  treasury_coins: number;

  // True once both order-placed and order-fulfilled topics exist in Confluent (unlocks Level 4)
  order_topics_ready: boolean;

  // Whether the backend has connected your dashboard to the Simulation server and Confluent.
  connection_status: 'connecting' | 'connected' | 'failed';
  // Why the connection failed; empty unless connection_status is 'failed'.
  connection_issues: ConnectionIssue[];
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
  inventory: { resource: {}, part: {}, robot: {} },
  events: { gathering: [], manufacturing: [], assembly: [] },
  event_topics_ready: false,
  event_topics_missing: [],
  hive_job_durations_ready: false,
  hive_inventory_balances_ready: false,
  simulation_config: null,
  orders_placed: 0,
  open_order: null,
  orders_fulfilled_engineer: 0,
  orders_fulfilled_gatherer: 0,
  treasury_coins: 0,
  order_topics_ready: false,
  connection_status: 'connecting',
  connection_issues: [],
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
