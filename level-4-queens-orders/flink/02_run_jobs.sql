-- =============================================================================
-- STEP 2 of 3: start the Queen's orders job  (run ONCE, stays Running)
-- =============================================================================
--
-- Starts one continuous Flink job that builds the `queens_orders` table,
-- one row per order, from three event streams:
--
--     queen-worker-ordered   -> OPEN
--     assembly-started      -> IN_ASSEMBLY
--     worker-assigned  -> ASSIGNED
--
-- Events are grouped by order_id; the furthest stage reached is the order's
-- status. The dashboard queue shows orders with status = 'OPEN'.
--
-- Before you run: Step 1 is done, the Simulation is running, and you are in
-- the same CLI context as Step 1.
--
-- Do NOT stop this statement. It must stay RUNNING for the Level 4 queue to
-- show orders.
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

INSERT INTO `queens_orders`
SELECT
  simulation_id,
  run_id,
  order_id,
  MAX(robot_type) AS robot_type,
  MAX(station) AS station,
  MAX(action) AS action,
  MAX(placed_seq) AS placed_seq,
  CASE MAX(lifecycle_stage)
    WHEN 1 THEN 'OPEN'
    WHEN 2 THEN 'IN_ASSEMBLY'
    ELSE        'ASSIGNED'
  END              AS status
FROM (

  -- The Queen places an order: it joins the queue (OPEN)
  SELECT
    simulation_id,
    run_id,
    payload.order_id AS order_id,
    payload.robot_type AS robot_type,
    payload.station AS station,
    payload.action AS action,
    CAST(event_sequence AS BIGINT) AS placed_seq,
    1 AS lifecycle_stage
  FROM `queen-worker-ordered`
  WHERE payload.order_id IS NOT NULL

  UNION ALL

  -- Assembly starts: the order leaves the queue (IN_ASSEMBLY)
  SELECT
    simulation_id,
    run_id,
    payload.order_id AS order_id,
    CAST(NULL AS STRING) AS robot_type,
    CAST(NULL AS STRING) AS station,
    CAST(NULL AS STRING) AS action,
    CAST(NULL AS BIGINT) AS placed_seq,
    2 AS lifecycle_stage
  FROM `assembly-started`
  WHERE payload.order_id IS NOT NULL

  UNION ALL

  -- The Queen assigns the finished robot (ASSIGNED)
  SELECT
    simulation_id,
    run_id,
    payload.order_id AS order_id,
    payload.robot_type AS robot_type,
    payload.station AS station,
    payload.action AS action,
    CAST(NULL AS BIGINT) AS placed_seq,
    3 AS lifecycle_stage
  FROM `worker-assigned`
  WHERE payload.order_id IS NOT NULL

)
GROUP BY simulation_id, run_id, order_id;

END;
