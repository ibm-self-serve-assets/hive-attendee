-- =============================================================================
-- STEP 1 of 3: create the inventory sink table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `hive_inventory_balances` table.  Flink will maintain one row
--   per (simulation_id, run_id, item_id, item_type) holding the current live
--   quantity.  Each row is continuously updated as events arrive.
--
-- SCHEMA DESIGN
--   item_type  : 'resource' | 'part' | 'robot'
--   item_id    : station_id, part_id, or robot output_type
--   quantity   : running net balance (deliveries/completions minus consumption)
--
-- WHY UPSERT (not append like hive_job_durations)
--   Inventory is a running balance — the same row is updated every time a
--   delivery arrives or a station consumes inputs.  `changelog.mode = 'upsert'`
--   means Flink emits an updated row for each key change.  The backing Kafka
--   topic carries a full changelog (inserts + updates).  Tableflow materialises
--   this as a live Iceberg snapshot of current inventory.
--
--   Unlike hive_job_durations (append), once a topic has been touched by
--   Tableflow its changelog mode is locked, so this is set correctly up front.
--
-- PRIMARY KEY
--   Required for upsert mode.  The composite key uniquely identifies one
--   inventory line.  There is no DISTRIBUTED BY clause on purpose: in upsert
--   mode Confluent requires the distribution key to equal the primary key,
--   which is what it uses by default.
--
-- BEFORE YOU RUN
--   * Complete Level 2 first (hive_job_durations must exist and be running).
--   * In your SQL Workspace header: catalog = hive_dev, database = your cluster,
--     compute pool = hive_compute_pool (or a new pool for Level 3).
--   * Paste this file into a new workspace cell and click Run.
--   * Do NOT create the `hive_inventory_balances` topic yourself — Flink does it.
-- =============================================================================

CREATE TABLE `hive_inventory_balances` (
  `simulation_id`  STRING,          -- simulation this balance belongs to
  `run_id`      STRING,          -- simulation run; resets when the simulation restarts
  `item_type`   STRING,          -- 'resource' | 'part' | 'robot'
  `item_id`     STRING,          -- e.g. 'copper', 'chassis', 'engineer'
  `quantity`    BIGINT,          -- current net stock (always >= 0 in a healthy sim)
  PRIMARY KEY (`simulation_id`, `run_id`, `item_type`, `item_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
