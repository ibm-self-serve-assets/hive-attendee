# Real-time Inventory with Apache Flink (Confluent CLI)

## Overview & Goal

In Level 2, you used Confluent Cloud's UI to execute SQL commands in Apache Flink that calcuated that `job-duration` for each Station in your manufacturing Simulation.  In Level 3, you will use the **Confluent CLI** to calculate teh **Live Inventory** for your Simulation: how many resources, parts, and robots are in stock or surplus.

**The Problem:** Raw Simulation events record only what was produced or consumed at a single instant.  There is no event that says "there are currently 7 units of copper in inventory."

**Your Objective:** Use Apache Flink stateful aggregations to maintain a continuously updated inventory balance for every item in the Simulation:

- **Resources** arrive via `gathering.completed` and are consumed when manufacturing stations start jobs (`manufacturing.started` inputs).
- **Parts** arrive via `manufacturing.completed` and are consumed when assembly starts (`assembly.started` inputs).
- **Robots** accumulate via `assembly.completed` and are never consumed.

```
gathering-completed  ──┐
                        ├──► Flink stateful SUM  ───►  hive_inventory_balances
manufacturing-started ──┘        (per item_id)          (upsert changelog)

manufacturing-completed ──┐ 
                           ├──► Flink stateful SUM ───►  hive_inventory_balances
assembly-started ──────────┘

assembly-completed ────────────► Flink stateful SUM ───►  hive_inventory_balances
```

**Key difference from Level 2:** `hive_inventory_balances` uses `changelog.mode = 'upsert'` — Flink continuously updates a single row per item as stock changes, rather than appending one row per event. The dashboard always shows the current balance, not a history of changes.

---

## Prerequisites

- Level 2 is complete: `hive_job_durations` exists and the stream processing statement is **Running**.
- The Simulation simulation is running and events are flowing.
- The Confluent CLI is installed (instructions below).

---

## Step 1 — Install the Confluent CLI

### macOS

Via Homebrew (recommended):
```bash
brew install confluentinc/tap/cli
```
Or via curl:
```bash
curl -sL --http1.1 https://cnfl.io/cli | sh -s -- -b /usr/local/bin
```

### Windows

Via winget:
```powershell
winget install Confluent.ConfluentCLI
```
Or via PowerShell:
```powershell
Invoke-WebRequest -Uri https://cnfl.io/cli -OutFile confluent-cli-install.ps1
powershell -ExecutionPolicy Bypass -File confluent-cli-install.ps1 -bin %USERPROFILE%\bin
```

### Verify
```bash
confluent version
```

---

## Step 2 — Authenticate & Set Context

```bash
# Log in (opens browser)
confluent login --save

# List environments and select yours
confluent environment list
# <ENV_ID> looks like env-abc123
confluent environment use <ENV_ID>

# List Kafka clusters and select yours
confluent kafka cluster list
# <CLUSTER_ID> looks like lkc-xyz789
confluent kafka cluster use <CLUSTER_ID>

# List Flink compute pools and note your pool ID
confluent flink compute-pool list

# Select the cloud and region your cluster and compute pool run in
# (replace <REGION> with a value from the table below, e.g. us-west1)
confluent flink region use --cloud gcp --region <REGION>

# Then select the matching Flink endpoint (run this AFTER the region command)
confluent flink endpoint use "https://flink.<REGION>.gcp.confluent.cloud"
```

Without the region, commands such as `confluent flink statement delete`, `list` and `describe` fail with `no cloud provider and region selected`. Without the endpoint, every Flink command prints `No Flink endpoint is specified, defaulting to public endpoint`. That notice is harmless, but setting the endpoint removes it. Changing the region unsets the endpoint, so always run the region command first.

Everyone uses Google Cloud, so the cloud is always `gcp`. Use the region your cluster was created in (`confluent kafka cluster describe` shows it). Common values:

| `--region` value | Location |
|---|---|
| `us-central1` | Iowa, USA |
| `us-east1` | South Carolina, USA |
| `us-east4` | Northern Virginia, USA |
| `us-west1` | Oregon, USA |
| `us-west4` | Las Vegas, USA |

Store these as shell variables to avoid retyping them:
```bash
export ENV_ID=<ENV_ID>
export CLUSTER_ID=<CLUSTER_ID>
export POOL_ID=<COMPUTE_POOL_ID>
```

---

## Step 3 — Create the Inventory Sink Table

Run `01_create_sink.sql` once. This creates the `hive_inventory_balances` table in Flink and the backing Kafka topic with upsert changelog mode.

```bash
confluent flink statement create hive-inventory-sink \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/01_create_sink.sql)" > /dev/null
```

The `> /dev/null` hides the CLI's echo of the whole SQL file. Errors are still shown.

**Expected result:** status `COMPLETED`. This is a DDL statement — it runs once and finishes. It starts as `PENDING`, so wait a few seconds and check again.

Confirm it succeeded:
```bash
confluent flink statement describe hive-inventory-sink -o json | grep -E '"(status|status_detail)"'
```

If the status is `FAILED`, the `status_detail` line explains why.

---

## Step 4 — Start the Inventory Jobs

Run `02_run_jobs.sql` to start the continuous streaming statement. This submits three parallel aggregation jobs (resources, parts, robots) bundled into a single Flink statement.

```bash
confluent flink statement create hive-inventory-jobs \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/02_run_jobs.sql)" > /dev/null
```

**Expected result:** status `RUNNING`. Unlike the DDL above, this statement runs indefinitely — do not delete it. It starts as `PENDING` and can take a minute or two to reach `RUNNING`.

Watch it come up (run again until it says `RUNNING`):
```bash
confluent flink statement describe hive-inventory-jobs -o json | grep -E '"(status|status_detail)"'
```

---

## Step 5 — Validate

The jobs from Step 4 are running, but nothing so far has shown you their output. In this step you read the `hive_inventory_balances` table to confirm that Flink is keeping a current stock count for every resource, part, and robot. The Simulation should be running so that you can see the numbers change.

**1. Open the Flink shell.** This is an interactive window where you type SQL and see the results.
```bash
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```
A `>` prompt appears when the shell is ready.

**2. Copy the query from `flink/03_validate.sql`, paste it at the `>` prompt and press Enter.** It reads the table the jobs write to.

**3. Read the result.** A table of results opens and updates by itself while the Simulation runs. It is not sorted, because Flink cannot sort a live stream. 

<img src="assets/screenshots/inventory_in_confluent_shell.png" width="75%" />

You should see:
- one row for each of the 5 resources, 4 parts and 2 robots for the current run (11 rows);
- quantities that change as the Simulation runs;
- no negative numbers.

If you restarted the simulation, the table also keeps rows from earlier runs. Each run has its own `run_id`.

**4. Close the results and the shell.** Press `Q` to close the results. Then type `EXIT;` or press `Ctrl+D` to close the shell.

If you see rows with changing quantities, Level 3 is working. Open **Level 3** in the dashboard to see the same numbers on the Simulation floor.

> **Gate Check:** The dashboard Level 3 view unlocks once the `hive_inventory_balances` topic exists. Running `01_create_sink.sql` (Step 3) creates it.

---

## How the Inventory Calculation Works

### Resources
```
resources[item_id] =
    SUM(gathering-completed.payload.quantity   WHERE station_id = item_id)
  − SUM(manufacturing-started.payload.inputs[item_id])
```
Resources are delivered by gathering jobs and consumed when manufacturing stations start (inputs are staged at job start, not at job completion).

### Parts
```
parts[item_id] =
    SUM(manufacturing-completed.payload.quantity  WHERE part_id = item_id)
  − SUM(assembly-started.payload.inputs[item_id])
```
Parts are produced by manufacturing completions and consumed when assembly stations start.

### Robots
```
robots[output_type] = SUM(assembly-completed.payload.quantity  WHERE output_type = item_id)
```
Robots only accumulate — nothing consumes them.

---

## Useful CLI Commands

```bash
# Short status of one statement (the plain `describe` and `list` print the whole SQL)
confluent flink statement describe hive-inventory-jobs -o json | grep -E '"(name|status|status_detail)"'

# Stop a statement (use only if you need to restart).
# Deleting is not instant: wait a few seconds, until the name is free, before creating it again.
confluent flink statement delete hive-inventory-jobs

# Open an interactive SQL shell
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```

---

## Technical Notes

- **Upsert vs Append:** `hive_inventory_balances` uses `changelog.mode = 'upsert'`. Unlike `hive_job_durations` (append), each row is updated in place as stock changes. The Kafka topic carries the full changelog. Tableflow materialises it as a live Iceberg snapshot.  
- **Changelog mode is locked after first Tableflow materialisation.** This is why the mode is `upsert` from the start — it cannot be changed later.
- **JSON inputs expansion:** The `inputs` field in `manufacturing.started` and `assembly.started` is a JSON object (e.g. `{"energy": 1, "resin": 3}`). The SQL extracts each known key by name using `JSON_VALUE` — there is no dynamic unnest because Confluent Flink SQL does not support dynamic map expansion from raw JSON in this pattern.
- **Do not pre-create** `hive_inventory_balances` manually. Flink creates and owns the topic and its Schema Registry entry.

---

## Visualizing Topics with Stream Lineage

Now that you have both raw event topics and derived stream processing pipelines active, you can use Confluent Cloud's **Stream Lineage** feature to visually inspect the end-to-end data flow graph across your cluster.

Stream Lineage is built into Stream Governance (Essentials) and automatically tracks event provenance across producers, Kafka topics, Flink stream processing statements, and consumer applications without any manual instrumentation.

### How to Access Stream Lineage

1. Open the [Confluent Cloud Console](https://confluent.cloud).
2. Select your **`hive_dev`** environment.
3. Click into your Kafka cluster (e.g. `hive_cluster_1`).
4. In the left navigation menu under your cluster, click **Stream Lineage**.

### What to Explore in Level 3

- **Upstream Source Topics:** Trace events originating from the Simulation across raw topics such as `gathering-completed`, `manufacturing-started`, `manufacturing-completed`, `assembly-started`, and `assembly-completed`.
- **Flink Processing Statement:** Identify the Flink job node representing your running `hive-inventory-jobs` statement set (as well as Level 2's `hive_job_durations` joins).
- **Derived Sink Topic:** Observe the flow routing into the `hive_inventory_balances` topic (the upsert changelog table).
- **Downstream Consumers:** Locate the consumer application nodes representing your local Hive Dashboard backend service reading the live inventory balances and raw events.
- **Node & Stream Inspection:** Click on any topic or stream edge in the lineage graph to view real-time throughput metrics (records/sec, bytes/sec), active schemas registered in Schema Registry, partition distributions, and consumer lag.

---

## Workshop Teardown & Resource Cleanup

> Only perform these steps when you are ready to clean up all cloud resources.

```bash
# Stop the inventory streaming statement
confluent flink statement delete hive-inventory-jobs

# If Level 2 streaming is also no longer needed
confluent flink statement delete <LEVEL_2_STATEMENT_NAME>

# Delete the compute pool once no statements remain
confluent flink compute-pool delete $POOL_ID
```
