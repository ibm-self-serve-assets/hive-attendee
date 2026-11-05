-- =============================================================================
-- STEP 4 of 6: create the parts priority sink table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `parts_priority_queue` table and its backing Kafka topic.
--   Flink keeps ONE row per part, holding how many units of that part are
--   needed by the Queen's orders that are still waiting to be built (OPEN).
--
--     part_id         : 'chassis' | 'electronics' | 'battery' | 'actuator'
--     quantity_needed : units of the part required by all OPEN orders
--     open_orders     : number of OPEN orders that need the part
--
--   The Parts Manufacturing Team should make the part with the highest
--   quantity_needed first.
--
-- WHY UPSERT
--   Demand changes as the Queen places orders and as assembly starts, so each
--   row is updated in place.  `changelog.mode = 'upsert'` requires a PRIMARY KEY.
--   When no OPEN order needs a part any more, its row is deleted.
--
-- BEFORE YOU RUN
--   * Steps 1-3 are done and the `queens_orders` job is RUNNING.
--   * Use the same catalog, database and compute pool as Step 1.
--   * Do NOT create the topic yourself; Flink does it.
-- =============================================================================

CREATE TABLE `parts_priority_queue` (
  `simulation_id`   STRING,          -- Simulation this demand belongs to
  `run_id`          STRING,          -- Simulation run; resets when the Simulation restarts
  `part_id`         STRING,          -- 'chassis' | 'electronics' | 'battery' | 'actuator'
  `quantity_needed` BIGINT,          -- units needed by all OPEN orders
  `open_orders`     BIGINT,          -- number of OPEN orders that need this part
  PRIMARY KEY (`simulation_id`, `run_id`, `part_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
