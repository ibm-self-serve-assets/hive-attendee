-- =============================================================================
-- STEP 2 of 3: start the Queen's orders job  (run ONCE, stays Running)
-- =============================================================================
--
-- WHAT THIS DOES
--   Submits one continuous Flink job that turns four event streams into the
--   `queens_orders` table, one row per order:
--
--     queen-robot-ordered     -> OPEN         (carries robot_type, station, action)
--     assembly-started        -> IN_ASSEMBLY  (only rows that carry an order_id)
--     queen-robot-assigned    -> ASSIGNED
--     queen-robot-cancelled   -> CANCELLED
--
--   The job groups the events by order_id.  Each event has a status_rank, and the
--   highest status_rank seen for an order is its status:
--
--     OPEN (1) < IN_ASSEMBLY (2) < ASSIGNED (3) < CANCELLED (4)
--
--   CANCELLED is only reachable from OPEN: once assembly-started has taken an
--   order off the queue, the Simulation refuses to cancel it.
--
--   assembly-started is what removes an order from the open queue.  The
--   dashboard queue shows the rows where status = 'OPEN'.
--
-- HOW THE COLUMNS ARE FILLED
--   Only queen-robot-ordered, -assigned and -cancelled carry robot_type and
--   station; only -ordered and -assigned carry action.  MAX() ignores NULLs, so
--   whichever event brings the value fills it in.  placed_seq comes from the
--   ordered event only.
--
-- BEFORE YOU RUN
--   * Step 1 (01_create_sink.sql) has completed successfully.
--   * The Simulation is running and events are flowing.
--   * Same CLI context as Step 1 (environment, cluster, compute pool).
--
-- IMPORTANT
--   * Do NOT stop this statement — it runs continuously.
--   * The statement status must be RUNNING before the dashboard Level 4
--     view will show the Queen's queue.
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

INSERT INTO `queens_orders`
SELECT
  simulation_id,
  run_id,
  order_id,
  MAX(robot_type)  AS robot_type,
  MAX(station)     AS station,
  MAX(action)      AS action,
  MAX(placed_seq)  AS placed_seq,
  CASE MAX(status_rank)
    WHEN 1 THEN 'OPEN'
    WHEN 2 THEN 'IN_ASSEMBLY'
    WHEN 3 THEN 'ASSIGNED'
    ELSE        'CANCELLED'
  END              AS status
FROM (

  -- The Queen places an order: it joins the queue (OPEN)
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                       AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                              AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id')                    AS order_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.robot_type')                  AS robot_type,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station')                     AS station,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.action')                      AS action,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.event_sequence') AS BIGINT)      AS placed_seq,
    1                                                                           AS status_rank
  FROM `queen-robot-ordered`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id') IS NOT NULL

  UNION ALL

  -- Assembly starts: the order leaves the queue (IN_ASSEMBLY)
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                       AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                              AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id')                    AS order_id,
    CAST(NULL AS STRING)                                                        AS robot_type,
    CAST(NULL AS STRING)                                                        AS station,
    CAST(NULL AS STRING)                                                        AS action,
    CAST(NULL AS BIGINT)                                                        AS placed_seq,
    2                                                                           AS status_rank
  FROM `assembly-started`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id') IS NOT NULL

  UNION ALL

  -- The Queen assigns the finished robot (ASSIGNED)
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                       AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                              AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id')                    AS order_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.robot_type')                  AS robot_type,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station')                     AS station,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.action')                      AS action,
    CAST(NULL AS BIGINT)                                                        AS placed_seq,
    3                                                                           AS status_rank
  FROM `queen-robot-assigned`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id') IS NOT NULL

  UNION ALL

  -- The Queen cancels an order that was still in the queue (CANCELLED)
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                       AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                              AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id')                    AS order_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.robot_type')                  AS robot_type,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station')                     AS station,
    CAST(NULL AS STRING)                                                        AS action,
    CAST(NULL AS BIGINT)                                                        AS placed_seq,
    4                                                                           AS status_rank
  FROM `queen-robot-cancelled`
  WHERE JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.order_id') IS NOT NULL

)
GROUP BY simulation_id, run_id, order_id;

END;
