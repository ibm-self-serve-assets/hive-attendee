-- =============================================================================
-- STEP 2 of 4: create the `parts_inventory` table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `parts_inventory` table and its backing Kafka topic.
--   Flink keeps one row per part holding its current quantity, updating
--   the row as events arrive.
--
--     part_id  : 'actuator' | 'battery' | 'chassis' | 'electronics'
--     quantity : manufacturing completions minus assembly consumption
--
-- It uses the same upsert settings as 01_create_resource_sink.sql.
--
-- BEFORE YOU RUN
--   * Step 1 (01_create_resource_sink.sql) has completed successfully.
--   * Use the same catalog, database and compute pool as Step 1.
--   * Do NOT create the topic yourself; Flink does it.
-- =============================================================================

CREATE TABLE `parts_inventory` (
  `simulation_id`  STRING,          -- Simulation this balance belongs to
  `run_id`         STRING,          -- Simulation run; resets when the Simulation restarts
  `part_id`        STRING,          -- e.g. 'actuator', 'battery', 'chassis', 'electronics'
  `quantity`       BIGINT,          -- current net stock (always >= 0 in a healthy sim)
  PRIMARY KEY (`simulation_id`, `run_id`, `part_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
