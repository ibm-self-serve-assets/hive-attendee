-- =============================================================================
-- STEP 3 of 4: start the inventory jobs  (run ONCE, stays Running)
-- =============================================================================
--
-- Starts two continuous Flink jobs in one statement set. Each keeps a running
-- SUM per (simulation_id, run_id, item) and upserts it into a sink table:
--
--     Job 1: gathering-completed minus manufacturing-started inputs
--            -> `resource_inventory`
--     Job 2: manufacturing-completed minus assembly-started inputs
--            -> `parts_inventory`
--
-- Before you run: Steps 1-2 are done, the Simulation is running, and you are
-- in the same CLI context as Step 1.
--
-- Each input in `payload.inputs` is read by name and UNIONed; an input that is
-- not in the recipe is NULL and produces no row.
--
-- Do NOT stop this statement. It must stay RUNNING for the Level 3 dashboard
-- to show live inventory.
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

-- ============================================================================
-- JOB 1: Resource inventory
--   Inflows  : gathering-completed  (payload.workstation_type, payload.quantity)
--   Outflows : manufacturing-started (payload.inputs.{energy,resin,metals,copper,silicon})
-- ============================================================================
INSERT INTO `resource_inventory`
SELECT
  simulation_id,
  run_id,
  resource_id,
  SUM(delta)  AS quantity
FROM (

  -- +quantity: each gathering completion delivers resources
  SELECT
    simulation_id,
    run_id,
    payload.workstation_type AS resource_id,
    CAST(payload.quantity AS BIGINT) AS delta
  FROM `gathering-completed`
  WHERE payload.workstation_type IS NOT NULL

  UNION ALL

  -- -quantity: each manufacturing job start consumes inputs (energy)
  SELECT
    simulation_id,
    run_id,
    'energy' AS resource_id,
    -CAST(payload.inputs.energy AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE payload.inputs.energy IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'resin' AS resource_id,
    -CAST(payload.inputs.resin AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE payload.inputs.resin IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'metals' AS resource_id,
    -CAST(payload.inputs.metals AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE payload.inputs.metals IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'copper' AS resource_id,
    -CAST(payload.inputs.copper AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE payload.inputs.copper IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'silicon' AS resource_id,
    -CAST(payload.inputs.silicon AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE payload.inputs.silicon IS NOT NULL

)
GROUP BY simulation_id, run_id, resource_id;

-- ============================================================================
-- JOB 2: Parts inventory
--   Inflows  : manufacturing-completed (payload.part_id, payload.quantity)
--   Outflows : assembly-started        (payload.inputs.{chassis,electronics,actuator,battery})
-- ============================================================================
INSERT INTO `parts_inventory`
SELECT
  simulation_id,
  run_id,
  part_id,
  SUM(delta)  AS quantity
FROM (

  -- +quantity: each manufacturing completion produces a part
  SELECT
    simulation_id,
    run_id,
    payload.part_id AS part_id,
    CAST(payload.quantity AS BIGINT) AS delta
  FROM `manufacturing-completed`
  WHERE payload.part_id IS NOT NULL

  UNION ALL

  -- -quantity: each assembly job start consumes parts (chassis)
  SELECT
    simulation_id,
    run_id,
    'chassis' AS part_id,
    -CAST(payload.inputs.chassis AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE payload.inputs.chassis IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'electronics' AS part_id,
    -CAST(payload.inputs.electronics AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE payload.inputs.electronics IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'actuator' AS part_id,
    -CAST(payload.inputs.actuator AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE payload.inputs.actuator IS NOT NULL

  UNION ALL

  SELECT
    simulation_id,
    run_id,
    'battery' AS part_id,
    -CAST(payload.inputs.battery AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE payload.inputs.battery IS NOT NULL

)
GROUP BY simulation_id, run_id, part_id;

END;
