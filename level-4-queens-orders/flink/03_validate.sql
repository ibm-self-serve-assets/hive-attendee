-- =============================================================================
-- STEP 3 of 3: validate the Queen's orders
-- =============================================================================
--
-- Run this inside a `confluent flink shell` session (see README).
-- The Simulation must be running and the queens-orders job must have
-- status RUNNING before rows appear.
--
-- Expected on a fresh run: 8 rows, all OPEN, matching the Queen's initial
-- orders.  Rows move to IN_ASSEMBLY as assembly starts, then to ASSIGNED when
-- the robot is built.
--
-- There is no ORDER BY on purpose.  This table is a live stream that keeps
-- changing, and Flink cannot sort a stream by a regular column.  The dashboard
-- sorts the OPEN rows by placed_seq to show the queue.
-- =============================================================================

-- All orders per run (includes run_id to distinguish multiple simulation runs).
SELECT run_id, placed_seq, robot_type, station, action, status, order_id
FROM `queens_orders`;
