-- =============================================================================
-- STEP 2 of 3: start the inventory jobs  (run ONCE, stays Running)
-- =============================================================================
--
-- WHAT THIS DOES
--   Submits three continuous Flink aggregation jobs bundled into a single
--   statement set:
--
--     Job 1 — Resources  : gathering-completed deliveries minus
--                          inputs consumed by manufacturing-started
--     Job 2 — Parts      : manufacturing-completed output minus
--                          inputs consumed by assembly-started
--     Job 3 — Robots     : assembly-completed accumulation (never consumed)
--
--   Each job maintains a running SUM keyed by (simulation_id, run_id, item_id)
--   and writes upsert rows to `hive_inventory_balances`.  The row for each
--   item is continuously updated as new events arrive.
--
-- BEFORE YOU RUN
--   * Step 1 (01_create_sink.sql) has completed successfully.
--   * The Simulation simulation is running and events are flowing.
--   * Same CLI context as Step 1 (environment, cluster, compute pool).
--
-- HOW INPUTS ARE EXTRACTED
--   The `inputs` field in manufacturing.started and assembly.started is a
--   JSON object, e.g. {"energy": 1, "resin": 3, "metals": 1}.
--   Because Confluent Flink SQL cannot dynamically expand a JSON map from
--   raw bytes, each known input key is extracted individually with JSON_VALUE
--   and UNIONed.  Unknown keys (future recipe changes) produce no row.
--
-- IMPORTANT
--   * Do NOT stop this statement — it runs continuously.
--   * The statement status must be RUNNING before the dashboard Level 3
--     view will show live inventory numbers.
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

-- ============================================================================
-- JOB 1: Resource inventory
--   Inflows  : gathering-completed  (payload.station_id, payload.quantity)
--   Outflows : manufacturing-started (payload.inputs.{energy,resin,metals,copper,silicon})
-- ============================================================================
INSERT INTO `hive_inventory_balances`
SELECT
  simulation_id,
  run_id,
  'resource'  AS item_type,
  item_id,
  SUM(delta)  AS quantity
FROM (

  -- +quantity: each gathering completion delivers resources
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station_id')                     AS item_id,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.quantity') AS BIGINT)        AS delta
  FROM `gathering-completed`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station_id') IS NOT NULL

  UNION ALL

  -- -quantity: each manufacturing job start consumes inputs (energy)
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'energy'                                                                        AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.energy'),   '0') AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.energy') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'resin'                                                                         AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.resin'),    '0') AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.resin') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'metals'                                                                        AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.metals'),   '0') AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.metals') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'copper'                                                                        AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.copper'),   '0') AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.copper') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'silicon'                                                                       AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.silicon'),  '0') AS BIGINT) AS delta
  FROM `manufacturing-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.silicon') IS NOT NULL

)
GROUP BY simulation_id, run_id, item_id;

-- ============================================================================
-- JOB 2: Parts inventory
--   Inflows  : manufacturing-completed (payload.part_id, payload.quantity)
--   Outflows : assembly-started        (payload.inputs.{chassis,electronics,actuator,battery})
-- ============================================================================
INSERT INTO `hive_inventory_balances`
SELECT
  simulation_id,
  run_id,
  'part'      AS item_type,
  item_id,
  SUM(delta)  AS quantity
FROM (

  -- +quantity: each manufacturing completion produces a part
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.part_id')                         AS item_id,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.quantity') AS BIGINT)        AS delta
  FROM `manufacturing-completed`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.part_id') IS NOT NULL

  UNION ALL

  -- -quantity: each assembly job start consumes parts (chassis)
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'chassis'                                                                       AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.chassis'),  '0') AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.chassis') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'electronics'                                                                   AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.electronics'), '0') AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.electronics') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'actuator'                                                                      AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.actuator'), '0') AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.actuator') IS NOT NULL

  UNION ALL

  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
    'battery'                                                                       AS item_id,
    -CAST(COALESCE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.battery'),  '0') AS BIGINT) AS delta
  FROM `assembly-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.inputs.battery') IS NOT NULL

)
GROUP BY simulation_id, run_id, item_id;

-- ============================================================================
-- JOB 3: Robot inventory
--   Inflows only: assembly-completed (payload.output_type, payload.quantity)
--   Robots are never consumed.
-- ============================================================================
INSERT INTO `hive_inventory_balances`
SELECT
  JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                              AS simulation_id,
  JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                  AS run_id,
  'robot'                                                                         AS item_type,
  JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.output_type')                       AS item_id,
  SUM(CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.quantity') AS BIGINT))   AS quantity
FROM `assembly-completed`
WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.output_type') IS NOT NULL
GROUP BY
  JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id'),
  JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id'),
  JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.output_type');

END;
