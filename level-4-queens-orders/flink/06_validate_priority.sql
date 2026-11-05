-- =============================================================================
-- STEP 6 of 6: validate the parts priority queue
-- =============================================================================
--
-- Run this in a `confluent flink shell` session or a new cell of the Flink SQL
-- Workspace (see README).  The Simulation must be running and the
-- parts-priority job must have status RUNNING before rows appear.
--
-- Expected: up to 4 rows per run, one per part (chassis, electronics, battery,
-- actuator).  quantity_needed goes up when the Queen places an order and down
-- when assembly starts for an OPEN order.  A part with no OPEN demand has no
-- row.
--
-- There is no ORDER BY on purpose.  This table is a live stream that keeps
-- changing, and Flink cannot sort a stream by a regular column.  Read the
-- rows from the highest quantity_needed down to get the priority.
-- =============================================================================

SELECT run_id, part_id, quantity_needed, open_orders
FROM `parts_priority_queue`;
