-- =============================================================================
-- STEP 2 of 2: start the jobs  (run this ONCE, as a single statement)
-- =============================================================================
--
-- WHAT THIS DOES
--   Starts one continuous Flink statement that runs three jobs, one each for
--   gathering, manufacturing and assembly. Each job pairs a "started" event with
--   its "completed" event and writes the time between them to `hive_job_durations`.
--
-- BEFORE YOU RUN
--   * Step 1 (01_create_sink.sql) has been run.
--   * Same SQL workspace context as Step 1 (catalog, database, compute pool).
--   * Click "+" to create a new SQL cell below, paste this entire file, and click Run.
--   * The EXECUTE STATEMENT SET ... BEGIN ... END block bundles all three stage
--     jobs into a single continuous statement.
--   * Once it reaches "Running", you can delete (trash icon) the cell card to keep
--     your workspace clean; the job continues running 24/7 in the background.
--
-- HOW EACH JOB WORKS
--   1. The server publishes plain JSON, so Flink sees `key` and `val` as raw
--      bytes. MAKE_VALID_UTF8(`val`) turns the bytes into a string that
--      JSON_VALUE can read, replacing any invalid UTF-8 bytes.
--   2. A started event and a completed event belong together when their
--      payload.job_id is equal. Probe events (connection.test) have no job_id,
--      so they never match and are ignored.
--   3. The join only looks for a completed event from 5 seconds before to
--      1 minute after the started event (Kafka record time). Jobs normally
--      take 5-15 s, so this keeps Flink's memory small. A started event with no
--      completed event in that window produces no row.
--      If you slow the simulation down so jobs take over a minute, widen the
--      "+ INTERVAL '1' MINUTE" bound.
--
-- WHAT THE OUTPUT NUMBERS MEAN
--   elapsed_sim_minutes  completed.sim_time_minutes - started.sim_time_minutes.
--                        Exact sim-time difference in minutes. 1 real second = 1
--                        sim minute, so this equals elapsed wall seconds.
--   elapsed_wall_s       real seconds between the two occurred_at timestamps.
--
-- Only values from the events themselves are used (no NOW(), UUID(), RAND()),
-- so replaying the same events gives the same rows.
--
-- Event fields used (see spec-shared/schemas/event_payloads.json):
--   envelope : simulation_id, run_id, occurred_at, sim_time_minutes
--   payload  : job_id, station_id / station_id / output_type
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

-- ---- gathering: gathering-started -> gathering-completed --------------------
INSERT INTO `hive_job_durations`
SELECT
  s.job_id, s.simulation_id, s.run_id,
  'gathering'                                         AS stage,
  'gathering-started'                                 AS started_topic,
  'gathering-completed'                               AS completed_topic,
  s.subject, s.output_type,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  c.sim_time_minutes - s.sim_time_minutes             AS elapsed_sim_minutes,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.job_id')                              AS job_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                                  AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                      AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station_id')                         AS subject,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station_id')                         AS output_type,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.sim_time_minutes') AS BIGINT)           AS sim_time_minutes,
    CAST(REPLACE(REPLACE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                         AS row_time
  FROM `gathering-started`
) AS s
JOIN (
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.job_id')                              AS job_id,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.sim_time_minutes') AS BIGINT)           AS sim_time_minutes,
    CAST(REPLACE(REPLACE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                         AS row_time
  FROM `gathering-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

-- ---- manufacturing: manufacturing-started -> manufacturing-completed --------
INSERT INTO `hive_job_durations`
SELECT
  s.job_id, s.simulation_id, s.run_id,
  'manufacturing'                                     AS stage,
  'manufacturing-started'                             AS started_topic,
  'manufacturing-completed'                           AS completed_topic,
  s.subject, s.output_type,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  c.sim_time_minutes - s.sim_time_minutes             AS elapsed_sim_minutes,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.job_id')                              AS job_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                                  AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                      AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station_id')                          AS subject,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.output_type')                           AS output_type,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.sim_time_minutes') AS BIGINT)           AS sim_time_minutes,
    CAST(REPLACE(REPLACE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                         AS row_time
  FROM `manufacturing-started`
) AS s
JOIN (
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.job_id')                              AS job_id,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.sim_time_minutes') AS BIGINT)           AS sim_time_minutes,
    CAST(REPLACE(REPLACE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                         AS row_time
  FROM `manufacturing-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

-- ---- assembly: assembly-started -> assembly-completed -----------------------
INSERT INTO `hive_job_durations`
SELECT
  s.job_id, s.simulation_id, s.run_id,
  'assembly'                                          AS stage,
  'assembly-started'                                  AS started_topic,
  'assembly-completed'                                AS completed_topic,
  s.subject, s.output_type,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  c.sim_time_minutes - s.sim_time_minutes             AS elapsed_sim_minutes,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.job_id')                              AS job_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.simulation_id')                                  AS simulation_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.run_id')                                      AS run_id,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.station_id')                          AS subject,
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.output_type')                           AS output_type,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.sim_time_minutes') AS BIGINT)           AS sim_time_minutes,
    CAST(REPLACE(REPLACE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                         AS row_time
  FROM `assembly-started`
) AS s
JOIN (
  SELECT
    JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.payload.job_id')                              AS job_id,
    CAST(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.sim_time_minutes') AS BIGINT)           AS sim_time_minutes,
    CAST(REPLACE(REPLACE(JSON_VALUE(MAKE_VALID_UTF8(`val`), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                         AS row_time
  FROM `assembly-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

END;
