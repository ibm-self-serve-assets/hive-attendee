-- =============================================================================
-- VALIDATE FLINK OPERATION
-- =============================================================================
-- The Simulation must be running (click Run in the dashboard) so events exist.
-- -----------------------------------------------------------------------------
-- Are results arriving in hive_job_durations?
-- Rows can take up to a minute to appear after the Simulation starts: Flink writes
-- its output in transactions that commit about once a minute.
-- -----------------------------------------------------------------------------
SELECT * FROM `hive_job_durations` LIMIT 20;