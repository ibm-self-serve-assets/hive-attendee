-- =============================================================================
-- STEP 1 of 2: create the output table  (run this ONCE, as a single statement)
-- =============================================================================
--
-- WHAT THIS DOES
--   Creates the `hive_job_durations` table. Flink will fill it in Step 2 with one row
--   per finished job: how long it took between its "started" and "completed"
--   events.
--
-- BEFORE YOU RUN
--   * In your SQL Workspace header, set "Use catalog" to hive_dev, "Use database"
--     to your Kafka cluster, and select your active Flink compute pool.
--   * Paste this file into a workspace cell and click Run.
--
-- NOTES
--   * Flink creates the backing Kafka topic `hive_job_durations` for you. Do not
--     create that topic yourself (for example with provision_topics.py).
--   * 'json-registry' stores the table's schema in Schema Registry. Schema
--     Registry must be enabled for the environment, and Tableflow needs the
--     registered schema.
--   * 'changelog.mode' = 'append' means every row is a new, final fact (never
--     updated or deleted). Tableflow remembers this mode after its first
--     materialization and it cannot be changed later, so pick it up front.
-- =============================================================================

CREATE TABLE `hive_job_durations` (
  `job_id`              STRING,           -- shared by the started and completed event
  `simulation_id`          STRING,
  `run_id`              STRING,
  `stage`               STRING,           -- gathering | manufacturing | assembly
  `started_topic`       STRING,           -- Kafka topic the started event came from
  `completed_topic`     STRING,           -- Kafka topic the completed event came from
  `subject`             STRING,           -- station_id (gathering) or station_id
  `output_type`           STRING,           -- what the job produced
  `started_at`          TIMESTAMP(3),     -- wall-clock time of the started event (UTC)
  `completed_at`        TIMESTAMP(3),     -- wall-clock time of the completed event (UTC)
  `elapsed_sim_minutes` BIGINT,           -- simulated time between the two events in minutes (exact; 1 real second = 1 sim minute)
  `elapsed_wall_s`      BIGINT            -- real seconds between the two events
) DISTRIBUTED BY (`job_id`) INTO 1 BUCKETS
WITH (
  'changelog.mode'                 = 'append',
  'key.format'                     = 'json-registry',
  'value.format'                   = 'json-registry',
  'kafka.consumer.isolation-level' = 'read-committed'
);
