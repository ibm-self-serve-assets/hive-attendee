-- =============================================================================
-- STEP 5 of 6: start the parts priority job  (run ONCE, stays Running)
-- =============================================================================
--
-- Starts one continuous Flink job that builds the `parts_priority_queue`
-- table by pairing two streams:
--
--     assembly-state  -> the recipe: which parts each robot type needs
--     queens_orders   -> the Queen's orders
--
-- Every order is copied as it is and gets the recipe of its robot type added.
-- Nothing is filtered or summed, so the table has one row per order.
--
-- THE RECIPE
--   `assembly-state` has one message per assembly workstation, published at the
--   start of every run, so every robot type has a recipe before the first order
--   is built.  The message is joined to the order on `output_type`, the robot
--   that workstation builds.
--
--   Flink reads this compacted topic as an append-only stream, so a robot type
--   can appear more than once (at the start, and again after each upgrade).
--   The recipe never changes, so we group by simulation_id and robot type and
--   take MAX() of each part.  The recipe is keyed by simulation_id only, not
--   run_id, because it does not change when the Simulation restarts.
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
  o.order_id,
  o.robot_type,
  o.workstation_type,
  o.workstation_id,
  o.action,
  o.placed_seq,
  o.status,
  r.actuator,
  r.battery,
  r.chassis,
  r.electronics
FROM `queens_orders` AS o
JOIN (

  SELECT
    simulation_id,
    payload.output_type AS robot_type,
    MAX(CAST(payload.parts_required.actuator    AS BIGINT)) AS actuator,
    MAX(CAST(payload.parts_required.battery     AS BIGINT)) AS battery,
    MAX(CAST(payload.parts_required.chassis     AS BIGINT)) AS chassis,
    MAX(CAST(payload.parts_required.electronics AS BIGINT)) AS electronics
  FROM `assembly-state`
  GROUP BY simulation_id, payload.output_type

) AS r
  ON  o.simulation_id = r.simulation_id
  AND o.robot_type    = r.robot_type;

END;
