-- =============================================================================
-- STEP 1 of 3: create the Queen's orders sink table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `queens_orders` table.  Flink maintains ONE row per order,
--   keyed by (simulation_id, run_id, order_id).  The row is updated as the
--   order moves through its life:
--
--     OPEN         queen-robot-ordered     the Queen placed the order
--     IN_ASSEMBLY  assembly-started        a robot is being built for it
--                                          (the order has left the queue)
--     ASSIGNED     queen-robot-assigned    the finished robot was assigned
--
-- SCHEMA DESIGN
--   robot_type : 'gatherer' | 'engineer' | 'builder'
--   station    : the workstation the robot will be applied to
--   action     : 'upgrade' (gatherer, engineer) | 'add' (builder)
--   placed_seq : event_sequence of the ordered event.  Sort OPEN rows by this
--                to get the Queen's first-in, first-out queue.
--   status     : 'OPEN' | 'IN_ASSEMBLY' | 'ASSIGNED'
--
-- WHY UPSERT (and not a per-item SUM like Level 3)
--   The queue is an ordered list of individual orders, not a running total.
--   One row per order keeps the order of the queue.  `changelog.mode = 'upsert'`
--   makes Flink emit an updated row each time an order changes status.
--
-- PRIMARY KEY
--   Required for upsert mode.  There is no DISTRIBUTED BY clause on purpose: in
--   upsert mode Confluent requires the distribution key to equal the primary
--   key, which is what it uses by default.
--
-- BEFORE YOU RUN
--   * Complete Level 3 first.
--   * In your SQL Workspace header: catalog = hive_dev, database = your cluster,
--     compute pool = hive_compute_pool.
--   * Paste this file into a new workspace cell and click Run.
--   * Do NOT create the `queens_orders` topic yourself — Flink does it.
-- =============================================================================

CREATE TABLE `queens_orders` (
  `simulation_id` STRING,          -- Simulation this order belongs to
  `run_id`        STRING,          -- Simulation run; resets when the Simulation restarts
  `order_id`      STRING,          -- UUID created by the Queen when she orders the robot
  `robot_type`    STRING,          -- 'gatherer' | 'engineer' | 'builder'
  `station`       STRING,          -- workstation the robot will be applied to, e.g. 'resin'
  `action`        STRING,          -- 'upgrade' | 'add'
  `placed_seq`    BIGINT,          -- event_sequence of queen-robot-ordered (queue position)
  `status`        STRING,          -- 'OPEN' | 'IN_ASSEMBLY' | 'ASSIGNED'
  PRIMARY KEY (`simulation_id`, `run_id`, `order_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
