-- =============================================================================
-- STEP 1 of 3: create the Queen's orders sink table  (run ONCE)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `queens_orders` table.  Flink maintains ONE row per order,
--   keyed by (simulation_id, run_id, order_id).  The row is updated as the
--   order moves through its life:
--
--     OPEN         queen-worker-ordered     the Queen placed the order
--     IN_ASSEMBLY  assembly-started        a robot is being built for it
--                                          (the order has left the queue)
--     ASSIGNED     queen-worker-assigned    the finished robot was assigned
--
-- SCHEMA DESIGN
--   robot_type : 'gatherer' | 'engineer' | 'builder'
--   workstation_type : the type of workstation the robot will be applied to, e.g. 'resin'
--   workstation_id   : the workstation of that type to upgrade (1 to 4); NULL for a Builder order
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
-- =============================================================================

CREATE TABLE `queens_orders` (
  `simulation_id` STRING,          -- Simulation this order belongs to
  `run_id`        STRING,          -- Simulation run; resets when the Simulation restarts
  `order_id`      STRING,          -- UUID created by the Queen when she orders the robot
  `robot_type`    STRING,          -- 'gatherer' | 'engineer' | 'builder'
  `workstation_type` STRING,       -- type of workstation the robot will be applied to, e.g. 'resin'
  `workstation_id`   BIGINT,       -- workstation of that type to upgrade (1 to 4); NULL for a Builder order
  `action`        STRING,          -- 'upgrade' | 'add'
  `placed_seq`    BIGINT,          -- event_sequence of queen-worker-ordered (queue position)
  `status`        STRING,          -- 'OPEN' | 'IN_ASSEMBLY' | 'ASSIGNED'
  PRIMARY KEY (`simulation_id`, `run_id`, `order_id`) NOT ENFORCED
)
WITH (
  'changelog.mode'                 = 'upsert',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
