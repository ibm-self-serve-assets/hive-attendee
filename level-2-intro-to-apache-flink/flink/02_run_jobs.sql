-- =============================================================================
-- STEP 2 of 2: start the jobs  (run this ONCE, as a single statement)
-- =============================================================================
--
-- Starts one continuous Flink statement with three jobs (gathering,
-- manufacturing, assembly). Each job matches a "started" event to its
-- "completed" event by payload.job_id and writes the time between them to
-- `workstation_efficiency`.
--
-- Before you run: Step 1 is done and you are in the same SQL workspace context.
-- Paste this entire file into a new SQL cell and click Run. Once it shows
-- "Running", you can delete the cell; the job keeps running in the background.
--
-- The join only looks for a completed event from 5 seconds before to 1 minute
-- after the started event. Jobs normally take 5-15 s. If you slow the
-- Simulation down so jobs take over a minute, widen the INTERVAL '1' MINUTE.
--
-- Output columns:
--   elapsed_sim_minutes  completed.sim_time_minutes - started.sim_time_minutes
--   elapsed_wall_s       real seconds between the two occurred_at timestamps
-- (1 real second = 1 sim minute, so the two values are equal.)
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

-- ---- gathering: gathering-started -> gathering-completed --------------------
INSERT INTO `workstation_efficiency`
SELECT
  s.job_id, s.simulation_id, s.run_id,
  'gathering'                                         AS stage,
  'gathering-started'                                 AS started_topic,
  'gathering-completed'                               AS completed_topic,
  s.workstation_type, s.output_type,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  c.sim_time_minutes - s.sim_time_minutes             AS elapsed_sim_minutes,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    payload.job_id                      AS job_id,
    simulation_id,
    run_id,
    payload.workstation_type                  AS workstation_type,
    payload.workstation_type                  AS output_type,   -- gathering has no output_type; the station names the resource
    sim_time_minutes,
    TO_TIMESTAMP(REPLACE(SUBSTR(occurred_at, 1, 19), 'T', ' ')) AS occurred_at,
    `$rowtime`                          AS row_time
  FROM `gathering-started`
) AS s
JOIN (
  SELECT
    payload.job_id                      AS job_id,
    sim_time_minutes,
    TO_TIMESTAMP(REPLACE(SUBSTR(occurred_at, 1, 19), 'T', ' ')) AS occurred_at,
    `$rowtime`                          AS row_time
  FROM `gathering-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

-- ---- manufacturing: manufacturing-started -> manufacturing-completed --------
INSERT INTO `workstation_efficiency`
SELECT
  s.job_id, s.simulation_id, s.run_id,
  'manufacturing'                                     AS stage,
  'manufacturing-started'                             AS started_topic,
  'manufacturing-completed'                           AS completed_topic,
  s.workstation_type, s.output_type,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  c.sim_time_minutes - s.sim_time_minutes             AS elapsed_sim_minutes,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    payload.job_id                      AS job_id,
    simulation_id,
    run_id,
    payload.workstation_type                  AS workstation_type,
    payload.output_type                 AS output_type,
    sim_time_minutes,
    TO_TIMESTAMP(REPLACE(SUBSTR(occurred_at, 1, 19), 'T', ' ')) AS occurred_at,
    `$rowtime`                          AS row_time
  FROM `manufacturing-started`
) AS s
JOIN (
  SELECT
    payload.job_id                      AS job_id,
    sim_time_minutes,
    TO_TIMESTAMP(REPLACE(SUBSTR(occurred_at, 1, 19), 'T', ' ')) AS occurred_at,
    `$rowtime`                          AS row_time
  FROM `manufacturing-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

-- ---- assembly: assembly-started -> assembly-completed -----------------------
INSERT INTO `workstation_efficiency`
SELECT
  s.job_id, s.simulation_id, s.run_id,
  'assembly'                                          AS stage,
  'assembly-started'                                  AS started_topic,
  'assembly-completed'                                AS completed_topic,
  s.workstation_type, s.output_type,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  c.sim_time_minutes - s.sim_time_minutes             AS elapsed_sim_minutes,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    payload.job_id                      AS job_id,
    simulation_id,
    run_id,
    payload.workstation_type                  AS workstation_type,
    payload.output_type                 AS output_type,
    sim_time_minutes,
    TO_TIMESTAMP(REPLACE(SUBSTR(occurred_at, 1, 19), 'T', ' ')) AS occurred_at,
    `$rowtime`                          AS row_time
  FROM `assembly-started`
) AS s
JOIN (
  SELECT
    payload.job_id                      AS job_id,
    sim_time_minutes,
    TO_TIMESTAMP(REPLACE(SUBSTR(occurred_at, 1, 19), 'T', ' ')) AS occurred_at,
    `$rowtime`                          AS row_time
  FROM `assembly-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

END;
