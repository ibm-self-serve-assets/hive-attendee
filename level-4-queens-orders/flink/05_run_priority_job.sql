-- =============================================================================
-- STEP 5 of 6: start the parts priority job  (run ONCE, stays Running)
-- =============================================================================
--
-- Starts one continuous Flink job that builds the `parts_priority_queue`
-- table by pairing two streams:
--
--     assembly-started  -> the recipe: which parts each robot type needs
--     queens_orders     -> the OPEN orders: which robots are waiting to be built
--
-- For every OPEN order, the recipe of its robot type is expanded into parts,
-- then summed per part.  The bigger the total, the more in demand the part.
--
-- THE RECIPE
--   The recipe of a robot type is read from `payload.inputs` of its
--   `assembly-started` events (MAX() keeps one value per part, as every event of
--   a robot type carries the same recipe).  It is keyed by simulation_id and
--   robot type only, not run_id, because a recipe does not change when the
--   Simulation restarts.  Each part is read by name and UNIONed, as in Level 3.
--   A robot type only gets a recipe once its first assembly has started, so
--   until then its OPEN orders add no demand.
--
-- Before you run: Step 4 is done, the `queens_orders` job is RUNNING, the
-- Simulation is running, and you are in the same CLI context as Step 1.
--
-- Do NOT stop this statement. It must stay RUNNING for the parts priority
-- queue to stay up to date.
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

INSERT INTO `parts_priority_queue`
SELECT
  o.simulation_id,
  o.run_id,
  r.part_id,
  SUM(r.quantity)  AS quantity_needed,
  COUNT(*)         AS open_orders
FROM `queens_orders` AS o
JOIN (

  SELECT
    simulation_id,
    payload.output_type AS robot_type,
    'chassis' AS part_id,
    MAX(CAST(payload.inputs.chassis AS BIGINT)) AS quantity
  FROM `assembly-started`
  WHERE payload.inputs.chassis IS NOT NULL
  GROUP BY simulation_id, payload.output_type

  UNION ALL

  SELECT
    simulation_id,
    payload.output_type AS robot_type,
    'electronics' AS part_id,
    MAX(CAST(payload.inputs.electronics AS BIGINT)) AS quantity
  FROM `assembly-started`
  WHERE payload.inputs.electronics IS NOT NULL
  GROUP BY simulation_id, payload.output_type

  UNION ALL

  SELECT
    simulation_id,
    payload.output_type AS robot_type,
    'battery' AS part_id,
    MAX(CAST(payload.inputs.battery AS BIGINT)) AS quantity
  FROM `assembly-started`
  WHERE payload.inputs.battery IS NOT NULL
  GROUP BY simulation_id, payload.output_type

  UNION ALL

  SELECT
    simulation_id,
    payload.output_type AS robot_type,
    'actuator' AS part_id,
    MAX(CAST(payload.inputs.actuator AS BIGINT)) AS quantity
  FROM `assembly-started`
  WHERE payload.inputs.actuator IS NOT NULL
  GROUP BY simulation_id, payload.output_type

) AS r
  ON  o.simulation_id = r.simulation_id
  AND o.robot_type    = r.robot_type
WHERE o.status = 'OPEN'
GROUP BY o.simulation_id, o.run_id, r.part_id;

END;
