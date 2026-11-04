-- =============================================================================
-- STEP 1 of 4: create the `resource_inventory` table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `resource_inventory` table and its backing Kafka topic.
--   Flink keeps one row per resource holding its current quantity, updating
--   the row as events arrive.
--
--     resource_id : 'copper' | 'energy' | 'metals' | 'resin' | 'silicon'
--     quantity    : gathering deliveries minus manufacturing consumption
--
-- WHY UPSERT
--   Inventory is a running balance, so each key is updated in place rather
--   than appended.  `changelog.mode = 'upsert'` requires a PRIMARY KEY.
--
-- BEFORE YOU RUN
--   * Complete Level 2 first.
--   * Use the same catalog, database and compute pool as Level 2.
--   * Do NOT create the topic yourself; Flink does it.
--   * Flink accepts one statement at a time, so `parts_inventory` is created
--     separately by 02_create_parts_sink.sql.
-- =============================================================================

CREATE TABLE `resource_inventory` (
  `simulation_id`  STRING,          -- Simulation this balance belongs to
  `run_id`         STRING,          -- Simulation run; resets when the Simulation restarts
  `resource_id`    STRING,          -- e.g. 'copper', 'energy', 'metals', 'resin', 'silicon'
  `quantity`       BIGINT,          -- current net stock (always >= 0 in a healthy sim)
  PRIMARY KEY (`simulation_id`, `run_id`, `resource_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
