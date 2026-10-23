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

/** Shape of the state object sent from the backend SSE stream. */
export interface DashboardState {
  stream_health: 'live' | 'stale' | 'awaiting_events';
  active_simulation_id: string | null;
  /** run_id of the most recent event (matches the run_id column in hive_job_durations). */
  run_id: string | null;
  run_generation: number;
  sim_time_minutes: number;
  lifecycle_status: 'paused' | 'running' | 'stopped' | 'expired';
  running: boolean;

  // Completed counts keyed by resource_id / station_id / output_type
  gathering_completed: Record<string, number>;
  manufacturing_completed: Record<string, number>;
  assembly_completed: Record<string, number>;

  // Active (in-progress) flags
  gathering_active: Record<string, boolean>;
  manufacturing_active: Record<string, boolean>;
  assembly_active: Record<string, boolean>;

  // Blocked state: keyed by resource_id / station_id; value is missing_inputs (or reason for gathering)
  gathering_blocked: Record<string, Record<string, unknown>>;
  manufacturing_blocked: Record<string, Record<string, number>>;
  assembly_blocked: Record<string, Record<string, number>>;

  // Recipe inputs captured from *.started events: station_id → { input_id → quantity }
  manufacturing_inputs: Record<string, Record<string, number>>;
  assembly_inputs: Record<string, Record<string, number>>;

  // Latest job durations from the hive_job_durations Flink topic:
  // subject (resource_id or station_id) → elapsed_sim_minutes
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
}

export const EMPTY_STATE: DashboardState = {
  stream_health: 'awaiting_events',
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
  gathering_blocked: {},
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
