-- =============================================================================
-- STEP 4 of 6: create the parts priority sink table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `parts_priority_queue` table and its backing Kafka topic.
--   Flink keeps ONE row per Queen's order: everything in `queens_orders`, plus
--   the parts the robot of that order needs.
--
--     [ { order, worker type, parts required for the worker type },
--       { order, worker type, parts required for the worker type },
--       ... ]
--
--   The leftmost OPEN order (lowest placed_seq) is the next robot to build, so
--   its parts are the ones that matter most.
--
-- COLUMNS
--   The first nine are the columns of `queens_orders`.  The last four are the
--   recipe of the order's robot type, one column per part:
--
--     actuator, battery, chassis, electronics : units of the part one robot needs
--                                               (NULL if the recipe does not use it)
--
-- WHY UPSERT
--   An order changes status as it moves through its life, so each row is updated
--   in place.  `changelog.mode = 'upsert'` requires a PRIMARY KEY.  Rows are
--   never filtered out in Flink: the dashboard shows the rows with
--   status = 'OPEN', exactly as it does for `queens_orders`.
--
-- BEFORE YOU RUN
--   * Steps 1-3 are done and the `queens_orders` job is RUNNING.
--   * Use the same catalog, database and compute pool as Step 1.
--   * Do NOT create the topic yourself; Flink does it.
-- =============================================================================

CREATE TABLE `parts_priority_queue` (
  `simulation_id`    STRING,         -- Simulation this order belongs to
  `run_id`           STRING,         -- Simulation run; resets when the Simulation restarts
  `order_id`         STRING,         -- UUID created by the Queen when she orders the robot
  `robot_type`       STRING,         -- 'gatherer' | 'engineer' | 'builder'
  `workstation_type` STRING,         -- type of workstation the robot will be applied to, e.g. 'resin'
  `workstation_id`   BIGINT,         -- workstation of that type to upgrade (1 to 4); NULL for a Builder order
  `action`           STRING,         -- 'upgrade' | 'add'
  `placed_seq`       BIGINT,         -- event_sequence of queen-worker-ordered (queue position)
  `status`           STRING,         -- 'OPEN' | 'IN_ASSEMBLY' | 'ASSIGNED'
  `actuator`         BIGINT,         -- actuators one robot of this type needs
  `battery`          BIGINT,         -- batteries one robot of this type needs
  `chassis`          BIGINT,         -- chassis one robot of this type needs
  `electronics`      BIGINT,         -- electronics one robot of this type needs
  PRIMARY KEY (`simulation_id`, `run_id`, `order_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
