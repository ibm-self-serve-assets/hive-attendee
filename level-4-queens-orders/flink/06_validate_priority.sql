-- =============================================================================
-- STEP 6 of 6: validate the parts priority queue
-- =============================================================================
--
-- Run this in a `confluent flink shell` session or a new cell of the Flink SQL
-- Workspace (see README).  The Simulation must be running and the
-- parts-priority job must have status RUNNING before rows appear.
--
-- Expected: one row per order, the same orders as `queens_orders`, each with
-- the parts its robot needs.  Orders of the same robot type show the same
-- numbers.  Rows move from OPEN to IN_ASSEMBLY to ASSIGNED as the order
-- progresses; the parts stay the same.
--
-- There is no ORDER BY on purpose.  This table is a live stream that keeps
-- changing, and Flink cannot sort a stream by a regular column.  The dashboard
-- sorts the OPEN rows by placed_seq: the lowest is the next robot to build.
-- =============================================================================

SELECT run_id, placed_seq, robot_type, workstation_type, workstation_id, action, status,
       actuator, battery, chassis, electronics
FROM `parts_priority_queue`;
