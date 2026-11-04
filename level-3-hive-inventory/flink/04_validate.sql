-- =============================================================================
-- STEP 4 of 4: validate inventory balances
-- =============================================================================
--
-- Run in a `confluent flink shell` session (see README, Step 5), with the
-- Simulation running and the Step 3 statement RUNNING.
--
-- Expected: 5 rows in `resource_inventory` and 4 rows in `parts_inventory`.
-- Quantities change continuously. There is no ORDER BY because Flink cannot
-- sort a live stream.
-- =============================================================================

-- Current stock of resources (5 rows for current run)
SELECT run_id, resource_id, quantity
FROM `resource_inventory`;

-- Current stock of parts (4 rows for current run)
SELECT run_id, part_id, quantity
FROM `parts_inventory`;
