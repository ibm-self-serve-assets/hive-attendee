-- =============================================================================
-- STEP 3 of 3: validate inventory balances
-- =============================================================================
--
-- Run this inside a `confluent flink shell` session (see README, Step 5).
-- The Simulation simulation must be running and hive-inventory-jobs must have
-- status RUNNING before rows appear.
--
-- Expected: one row per item per run (5 resources + 4 parts + 2 robots = 11
-- rows).  Quantities change as the Simulation runs.
--
-- There is no ORDER BY on purpose.  This table is a live stream that keeps
-- changing, and Flink cannot sort a stream by a regular column.
-- =============================================================================

-- Current stock of all items (includes run_id to distinguish multiple simulation runs).
SELECT run_id, item_type, item_id, quantity
FROM `hive_inventory_balances`;
