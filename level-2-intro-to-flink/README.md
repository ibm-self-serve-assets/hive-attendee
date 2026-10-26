# Stream Processing with Apache Flink in Confluent Cloud

## Overview & Goal

In the Hive workshop, your simulation emits discrete lifecycle events across different Kafka topics as resources are collected, parts are manufactured and robots are assembled. 

However, raw events tell you only what happened at an instant in time:
- A `*.started` event announces that a job began.
- A `*.completed` event announces that the job finished.

**The Problem:** There is no single event that tells you how long a job actually took, whether it ran on schedule, or how station performance is trending across stages.

**Your Objective:** As a stream processing engineer, you will use **Apache Flink on Confluent Cloud** to correlate unbounded event streams in real time. You will build an interval-join pipeline that pairs started and completed events by `job_id`, calculates job durations and outputs continuous, typed performance metrics to a unified `hive_job_durations` stream.

**Key Terminology:** Interval Joins, Stream-to-Stream Joins, Watermarks, Stream Windows


```
┌─────────────────────────┐
│   *.started topic       ├──┐
└─────────────────────────┘  │   Flink Stateful Join
                             ├──► (matches on job_id)  ───►  hive_job_durations table & topic
┌─────────────────────────┐  │   [within 1-min window]      (Schema Registry + Tableflow ready)
│   *.completed topic     ├──┘
└─────────────────────────┘
```

---

## What You Are Building

### 1. Input Streams
Your simulation publishes raw JSON events across three production stages (defined in [`spec-shared/schemas/event_payloads.json`](../spec-shared/schemas/event_payloads.json)):

| Production Stage | Started Topic | Completed Topic | What It Represents |
|---|---|---|---|
| **Gathering** | `gathering-started` | `gathering-completed` | Resource extraction (pollen, nectar, wax) |
| **Manufacturing** | `manufacturing-started` | `manufacturing-completed` | Component production at stations (frames, honeycombs) |
| **Assembly** | `assembly-started` | `assembly-completed` | Final robot assembly lines |

Each event is wrapped in a standard envelope containing metadata (`occurred_at`, `sim_time_minutes`, `simulation_id`, `run_id`) and a `payload` containing `job_id` and the details of the job (resource, station or output).

### 2. Output Stream (`hive_job_durations`)
Flink will create a Kafka topic named `hive_job_durations` and publish a unified, append-only stream with these fields:

| Derived Metric / Field | Source / Calculation | Why It Matters |
|---|---|---|
| `job_id` | Shared `payload.job_id` | Correlates both events together |
| `stage` | `gathering`, `manufacturing`, or `assembly` | Allows cross-stage filtering and grouping |
| `output_type` | `station_id` | Identifies which station or item type was worked on |
| `elapsed_sim_minutes` | `completed.sim_time_minutes - started.sim_time_minutes` | **Exact simulated duration.** Independent of clock drift or simulation speed. |
| `elapsed_wall_s` | Difference between `occurred_at` timestamps | **Real-world duration in seconds.** Measures real wall-clock latency. |

---

## Interval Joins: Why Stream-to-Stream Joins Need Watermarks and Windows

In traditional databases, you can join two tables at any time because all rows are stored on disk. In stream processing, events arrive continuously over time over unbounded streams. 

If Flink joined streams without time constraints, it would have to keep every `started` event in memory forever waiting for a possible `completed` event, eventually exhausting memory.

To solve this, our Flink queries use an **Interval Join**:
```sql
ON  s.job_id = c.job_id
AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;
```
This tells Flink:
1. Match records where `job_id` is identical.
2. Only retain state for the max expected time between tracked events.  Having implemented the simulations ourselves, we know the max time to gather resouces, manufacture parts or assemble robots is hard-coded to 30 seconds.  So the SQL code above will retain state for a max 1 minute of Kafka record time. This means once a `started` event is older than 1 minute without a match, it is evicted from state, keeping memory usage minimal and bounded.  The likelihood of this happenng due to network or compute processing latency is negligible for the simulation.

---

## Step-by-Step Instructions

You will first configure your environment and run the pipeline using the **Confluent Cloud Web UI**. In Level 3, you will learn to perform similar commands using the **Confluent CLI**.

---

### Step 1: Initial Setup via Confluent Cloud UI

> **Note on Schema Registry:** Schema Registry is already active because you selected the **Essentials** Stream Governance package when creating the `hive_dev` environment in **Level 1**.

1. **Create Your Flink Compute Pool**:
   - From the home page of your Confluent Cloud instance, select **Environment** from the left navigation
   - Click into your `hive_dev` environment then click into **Compute Pools**.

    <img src="screenshots/screenshot-0.png" alt="Add Compute Pool"/>

   - In the left navigation, click **Flink** and go to the **Compute pools** tab.
   - Click **Add compute pool**.

   <img src="screenshots/screenshot-1.png" alt="Add Compute Pool"/>

   - Select **Google Cloud** as the provider and **Oregon (us-west)** as the region (or a region closer to you). Click **Continue**.
   <img src="screenshots/select_google_cloud.png" alt="Select Region"/>

   - Rename your **Pool name** to `hive_compute_pool` and click **Create**.

   <img src="screenshots/screenshot-3.png" alt="Review and Create"/>

2. **Flink SQL Workspace**:
   - From your Compute Pool screen, click **SQL Workspace** at the top.

   <img src="screenshots/screenshot-9.png"/>
   
   - At the top-right of the **SQL Workspace**, there are two settings drop-down options:
     - **Use catalog**: Select your Confluent Cloud environment, e.g. `hive_dev` (Flink refers to a **Confluent Environment** as a **Catalog**)
     - **Use database**: Select your Kafka cluster, e.g. `hive_cluster_1`. (Flink refers to a **Confluent Cluster** as a **Database**)

   <img src="screenshots/screenshot-10.png"/>

   - Click the Gear icon at top-right to edit your **Workspace Settings**:
     - **Rename Your Workspace:** to **`hive_job_durations`**.
     - **Compute pool**: Select your newly created pool (e.g. `hive_compute_pool`).
     - **Save Changes**: DO NOT click the X to close this window.  You must click **Save Changes** (located at bottom-right of Workspace Settings)!

    <img src="screenshots/workspace_settings.png"/>
   
---

### Step 2: Execute Flink SQL Statements in the Workspace

#### A. Ensure Simulation Data is Flowing
Before proceeding, ensure your Simulation Dashboard is:
- Connected to the Hive simulation server and running.
- The simulation timer is incrementing up.
- This ensures Kafka events are being actively published to `gathering-*`, `manufacturing-*`, and `assembly-*` topics.

<img src="screenshots/screenshot-12.png" width="35%" />

#### B. Prepare SQL execution windows
1. Click twice (2 x) on the **+** button at top-right of the SQL execution cell, so you have a total of 3 SQL execution cells.
2. If there is text in the first cell, delete as it's not needed.

<img src="screenshots/screenshot-13.png" />

#### C. Create the Sink Table
1. Open [`flink/01_create_sink.sql`](flink/01_create_sink.sql).
2. Copy the entire SQL statement and paste it into the **first workspace cell**.
3. Before clicking **Run**, check the **Mode** selector at the bottom-right of the cell. Set it to **Snapshot** (not Streaming).
   - **Snapshot** — runs once and returns a final result set. Correct for DDL statements like `CREATE TABLE`.
   - **Streaming** — keeps the statement alive as a continuous job. This is for DML queries in the next step.
4. Click **Run**.
  - **What this does:** Registers the `hive_job_durations` table in Flink, generates the registered schema in Schema Registry, and creates the underlying Kafka topic with `append` changelog mode.
  - **Expected status:** **Completed**. This DDL statement executes once and finishes immediately.
  - **If you see `Schema Registry subject 'hive_job_durations-value' doesn't match the existing one`:** A previous run left stale Schema Registry subjects that must be deleted manually. `DROP TABLE` alone is not sufficient. Follow these steps in order:
    1. In your `hive_dev` environment, click **Schema Registry** → **Subjects** tab.
    2. Find and delete **`hive_job_durations-value`** and **`hive_job_durations-key`** (if present). Click into each subject → **Delete subject** → confirm.
    3. Navigate to your Kafka cluster → **Topics**. If `hive_job_durations` still exists, delete it.
    4. Re-run `01_create_sink.sql` in this cell (Snapshot mode).

<img src="screenshots/screenshot-14.png" width="75%" />

#### D. Deploy the Stream Processing Jobs
1. Open [`flink/02_run_jobs.sql`](flink/02_run_jobs.sql).
2. Copy the entire `EXECUTE STATEMENT SET ... BEGIN ... END;` block, paste it into the **second workspace cell** and click **Run**.
  - **What this does:** Submits three continuous streaming jobs (gathering, manufacturing, assembly) bundled into a single Flink statement. Flink continuously joins incoming `started` and `completed` events and writes the correlated duration records into `hive_job_durations`.
  - **Expected status:** **Running**. Unlike the earlier DDL commands creating the Sink table, stream processing queries are continuous, long-running background jobs that stay active on your compute pool, listening for incoming Kafka events and calculating durations in real time.
  - Ignore the warning.  This is because the simulation event producer is not using the Confluent's Schema Registry to keep this workshop simple to start.
3. So do **not** click **Stop**.  Clicking the red **Stop** button cancels and terminates your background Flink streaming pipeline.
  - After the next step, we will close this SQL Workspace while leaving this stream processing queries running in the background.

<img src="screenshots/screenshot-15.png" width="75%" />

#### E. Validate the Streaming Output
1. Open [`flink/03_validate.sql`](flink/03_validate.sql).
2. Copy the entire SQL block, paste it into the **third workspace cell** and click **Run**.
3. Wait up to a minute to confirm derived duration records are being generated by Flink. The first rows are slow to appear because Flink commits its output about once a minute.
4. Once you have verified records are being generated, click **Stop** as this 3rd command does not need to run anymore.

<img src="screenshots/screenshot-16.png" width="75%" />

#### F. Close this SQL workspace
Click the **x** next to the SQL Workspace name to close it as we are done.

<img src="screenshots/screenshot-17.png" width="25%" />

#### G. View Your Running Flink Statement in the Console
To inspect and verify your active streaming statement running on your compute pool:
1. Navigate back to your **`hive_dev`** environment.
2. In the left navigation, click **Flink** and go to the **Statements** tab.
3. You will see the statements that you just executed listed.  Ensure only the Statement of type **Execute Statement Set** has status **Running**:

<img src="screenshots/screenshot-18.png" width="75%" />

> **Dashboard unlock:** In the dashboard, choosing **Level 2** from the Levels dropdown hides the simulation controls and shows what is required, until the `hive_job_durations` topic exists. Running `01_create_sink.sql` creates it, so the controls appear shortly after that step. The topic holds no records until the simulation runs, so start it afterwards.

> **⚠️ Gate Check — Do Not Proceed If Not Running:**
> Your statement status must be **Running**. If it is stopped or missing, verify that your simulation simulation is running, ensure your compute pool is active, and re-run [`flink/02_run_jobs.sql`](flink/02_run_jobs.sql).

4. Click on the statement name to open its **Statement Details** page:

<img src="screenshots/screenshot-7.png" alt="Statement Details Overview" width="75%" />

- **Catalog & Cluster:** Confirms binding to `hive_dev` and `hive_cluster_1`.
- **Throughput by Table:** Shows live messages in and out across `gathering-*`, `manufacturing-*`, and `assembly-*` topics.
- **SQL Definition:** Displays the running statement set and joins.

5. Scroll down to inspect the **Activity Trends** charts:

<img src="screenshots/screenshot-8.png" alt="Activity Trends & Performance Metrics" width="75%" />

- **Statement CFU:** Shows Confluent Flink Units allocated to this pipeline.
- **Messages behind (Lag):** Confirms Flink is processing in real time with near-zero lag.
- **Messages in/out per minute:** Visualizes incoming simulation events and derived duration records being produced.

---

## Next Step

Return to your Hive Dashboard and select Level 2.  Now that the `hive_job_durations` topic exists, you can see the updated UI with Flink's calculations visible.  After exploring the new UI, proceed to **[Level 3 — Real-time Inventory](../level-3-hive-inventory/README.md)**. Level 3 introduces the Confluent CLI and builds live inventory balances using stateful Flink aggregations.

