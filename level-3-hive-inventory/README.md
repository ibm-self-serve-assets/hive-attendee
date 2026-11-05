# Real-time Inventory with Apache Flink (Confluent CLI)

## Overview & Goal

In Level 2, you used Confluent Cloud's UI to execute SQL commands in Apache Flink that calculated the `job-duration` for each Station in your manufacturing Simulation. In Level 3, you will use the **Confluent CLI** to calculate the **Live Inventory** for your Simulation: how many resources and parts are in stock or surplus.

**The Problem:** Raw Simulation events record only what was produced or consumed at a single instant. There is no event that says "there are currently 7 units of copper in inventory."

**Your Objective:** Use Apache Flink stateful aggregations to maintain continuously updated inventory balances across two dedicated tables:

- **Resources** (`resource_inventory`): Arrive via `gathering-completed` and are consumed when manufacturing stations start jobs (`manufacturing-started` inputs).
- **Parts** (`parts_inventory`): Arrive via `manufacturing-completed` and are consumed when assembly starts (`assembly-started` inputs).

### New Kafka Topics: resource_inventory & parts_inventory

```
gathering-completed  ──┐
                        ├──► Flink Job 1 (stateful SUM) ───►  resource_inventory
manufacturing-started ──┘         (per resource_id)           (upsert changelog)

manufacturing-completed ──┐ 
                           ├──► Flink Job 2 (stateful SUM) ───►  parts_inventory
assembly-started ──────────┘         (per part_id)            (upsert changelog)
```

### Stream-Table Duality

A foundational concept in event-driven architecture is the **stream-table duality**: a stream represents a history of change (what happened), while a table represents the current state of the world (what is). 

* **Append-Only Streams (Level 2):** Traditional Kafka topics are immutable, append-only event logs. Every single action (e.g., `+1 Copper added`, `-2 Copper consumed`) creates a new record. While great for auditing history, asking *"How much copper do we have in stock right now?"* would require a consumer to replay and sum every transaction from the beginning of time.
* **Upsert Changelog / Materialized State (Level 3):** By configuring `resource_inventory` and `parts_inventory` with `changelog.mode = 'upsert'` and primary keys (`resource_id` / `part_id`), Apache Flink turns the stream of delta events into **live materialized tables**.
* **The Result:** Flink handles all the running sums in internal state and emits the latest balance per item. Downstream applications (like your UI dashboard) don't have to scan millions of historical events — they instantly read the current state of each resource and part directly.

---

## Prerequisites

- Level 2 is complete: `workstation_efficiency` exists and the stream processing statement is **Running**.
- The Simulation is running and events are flowing.
- The Confluent CLI is installed (instructions below if not).

---

## Step 1 — Install the Confluent CLI

### macOS

Via Homebrew (recommended):
```bash
brew install confluentinc/tap/cli
```
No Homebrew or no admin rights? Install to your home directory instead (avoids `/usr/local/bin` permission errors):
```bash
curl -sL --http1.1 https://cnfl.io/cli | sh -s -- -b $HOME/.local/bin
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```
> Using bash instead of zsh? Use `~/.bash_profile` in place of `~/.zshrc`. Check your shell with `echo $SHELL`.

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

# Select your Flink compute pool
confluent flink compute-pool use <POOL_ID>

# Select the cloud and region your cluster and compute pool run in
# (replace <REGION> with a value from your cluster settings, e.g. us-west1)
confluent flink region use --cloud gcp --region <REGION>

# Then select the matching Flink endpoint (run this AFTER the region command)
confluent flink endpoint use https://flink.<REGION>.gcp.confluent.cloud
```

Without the region, commands such as `confluent flink statement delete`, `list` and `describe` fail with `no cloud provider and region selected`. Without the endpoint, every Flink command prints `No Flink endpoint is specified, defaulting to public endpoint`. That notice is harmless, but setting the endpoint removes it. Changing the region unsets the endpoint, so always run the region command first.

### Export environment, cluster and compute pool IDs for use by CLI

Use the same values as in the prior steps to store the values as shell variables:

#### macOS / Linux (bash/zsh)
```bash
export ENV_ID=<ENV_ID>
export CLUSTER_ID=<CLUSTER_ID>
export POOL_ID=<COMPUTE_POOL_ID>
```

Validate presence of your variables:
```bash
echo $ENV_ID/$CLUSTER_ID/$POOL_ID
```

#### Windows (PowerShell)
```powershell
$env:ENV_ID="<ENV_ID>"
$env:CLUSTER_ID="<CLUSTER_ID>"
$env:POOL_ID="<COMPUTE_POOL_ID>"
```

Validate presence of your variables (ensure no extra spaces are present):
```powershell
echo $env:ENV_ID/$env:CLUSTER_ID/$env:POOL_ID
```

---

## Step 3 — Create the Inventory Sink Tables

**NOTE:** Ensure your Terminal window is in the **Level 3 directory** (`hive-attendee/level-3-hive-inventory`) when running the following commands.

Create the `resource_inventory` and `parts_inventory` tables in Flink and their backing Kafka topics with upsert changelog mode. Flink accepts only one statement at a time, so each table has its own file and its own statement:

```bash
confluent flink statement create hive-inventory-sink \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/01_create_resource_sink.sql)" > /dev/null

confluent flink statement create hive-inventory-parts-sink \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/02_create_parts_sink.sql)" > /dev/null
```

The `> /dev/null` hides the CLI's echo of the whole SQL file. Errors are still shown.

Confirm both succeeded:
```bash
confluent flink statement describe hive-inventory-sink -o json | grep -E '"(status|status_detail)"'
confluent flink statement describe hive-inventory-parts-sink -o json | grep -E '"(status|status_detail)"'
```

**Expected result:** status `COMPLETED`. This is a DDL statement — it runs once and finishes. It starts as `PENDING`, so wait a few seconds and check again.  

If the status is `FAILED`, the `status_detail` line explains why.

---

## Step 4 — Start the Inventory Jobs

Run `03_run_jobs.sql` to start the continuous streaming statement. This submits two parallel aggregation jobs (resources and parts) bundled into a single Flink statement.

```bash
confluent flink statement create hive-inventory-jobs \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/03_run_jobs.sql)" > /dev/null
```

This command may take a few seconds to complete. Once it does, confirm it succeeded using this command:

```bash
confluent flink statement describe hive-inventory-jobs -o json | grep -E '"(status|status_detail)"'
```

**Expected result:** It starts as `PENDING` and can take a minute or two to reach `RUNNING`. Execute the above command as needed until `RUNNING` is displayed.   

Unlike the DDL in Step 3, this DML statement runs indefinitely. 

> **Understanding DDL vs. DML in Flink:**
> - **DDL (Data Definition Language):** Commands like `CREATE TABLE` that define schemas, tables, and connectors. They run once, establish metadata, and finish immediately with status `COMPLETED`.
> - **DML (Data Manipulation Language):** Commands like `INSERT INTO ... SELECT` that move, transform, and aggregate data. In streaming systems like Apache Flink, DML statements run continuously in the background with status `RUNNING` to process live events as they arrive.

---

## Step 5 — Validate using Flink Shell

> **What is the Flink Shell?**
> The Flink Shell is an interactive SQL prompt that connects directly to your Confluent Cloud compute pool. Unlike the Confluent Cloud UI editor — which is better suited to writing and saving named statements — the shell is ideal for quick, one-off queries: checking what data is in a table, verifying a job's output, or debugging a schema. Think of it the way you'd use `psql` or the MySQL CLI: not where you author your production SQL, but where you poke around to confirm things are working.
>
> This is the first time in the workshop we use it because it's the right tool for reading live output interactively — you can watch inventory values change in real time as the Simulation runs, which the shell handles naturally. Use it any time you want to inspect a Flink-managed topic, run a quick `SELECT`, or test a query before committing it to a permanent statement.

The jobs from Step 4 are running, but nothing so far has shown you their output. In this step you'll use Flink Shell to read the `resource_inventory` and `parts_inventory` tables to confirm that Flink is keeping a current stock count for every resource and part. The Simulation should be running so that you can see the numbers change.

**1. Open the Flink shell.** This is an interactive window where you type SQL and see the results:
```bash
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```
A `>` prompt appears when the shell is ready.

**2. Copy the query** from `flink/04_validate.sql`, paste it at the `>` prompt. The Shell will likely display a typeahead hint, but ignore it and press **Enter**.

**3. Read the result.** You will initially see `statement phase pending` then a table of results will open after a delay of 5-10 seconds. This table will auto-update while the Simulation runs. It is not sorted, because Flink cannot sort a live stream. 

<img src="screenshots/inventory_in_flink_shell.png"/>

You should see:
- 5 rows for resources in `resource_inventory` (copper, energy, metals, resin, silicon) and 4 rows for parts in `parts_inventory` (actuator, battery, chassis, electronics);
- quantities that change as the Simulation runs;
- no negative numbers;
- if you restarted the simulation, the table will show earlier runs too. Each run has its own `run_id`.

**4. Congratulations! Level 3 Achieved!!!**

Open your Hive Dashboard and select **Level 3.** Your Dashboard shows the same results as in the Flink Shell. You have a real-time Inventory of available resources and parts updated from your new `resource_inventory` and `parts_inventory` topics. By observing the parts manufacturing events, you can see that `manufacturing-started` events coincide with the total resources being reduced by the required input amounts. Likewise the parts inventory is seen to reduce when the `assembly-started` event appears, as expected.

<img src="screenshots/inventory_in_ui.png"/>

The Dashboard updates in near real-time — typically within a second of a new value being written — while the Flink Shell lags by up to a minute. Both are reading from the same `resource_inventory` and `parts_inventory` Kafka topic, but with different isolation levels. The dashboard backend uses `read_uncommitted`, so it sees records the moment Flink writes them. The Flink Shell uses `read_committed` (the default), so it only sees records after Flink's checkpoint transaction commits — which happens on the checkpoint interval, roughly once per minute on Confluent Cloud. The "Last Refresh" timer in the shell is just the shell's own display refresh rate, not an indicator of when new data arrived.

We'll review all the updates to the Level 3 Dashboard later.  But first, let's review how the Inventories works.

**5. Close Flink shell.** 

Press `Q` to close the results. Then type `EXIT;` or press `Ctrl+D` to close the shell.

---

## How the Inventory Calculation Works

### Resources (`resource_inventory`)
```
resources[resource_id] =
    SUM(gathering-completed.payload.quantity   WHERE station_id = resource_id)
  − SUM(manufacturing-started.payload.inputs[resource_id])
```
Resources are delivered by gathering jobs and consumed when manufacturing stations start.

### Parts (`parts_inventory`)
```
parts[part_id] =
    SUM(manufacturing-completed.payload.quantity  WHERE part_id = part_id)
  − SUM(assembly-started.payload.inputs[part_id])
```
Parts are produced by manufacturing completions and consumed when assembly stations start.

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

## Visualizing Topics with Stream Lineage

Now that you have both raw event topics and derived stream processing pipelines active, you can use Confluent Cloud's **Stream Lineage** feature to visually inspect the end-to-end data flow graph across your cluster.

Stream Lineage is built into Stream Governance (Essentials) and automatically tracks event provenance across producers, Kafka topics, Flink stream processing statements, and consumer applications without any manual instrumentation.

### How to Access Stream Lineage

1. Open the [Confluent Cloud Console](https://confluent.cloud).
2. Ensure your **`hive_dev`** environment is selected from the navbar's **Environment** dropdown.
3. Click **Clusters** in the navbar then click your `hive_cluster` tile.
4. The navbar will change to show your Cluster options.
5. Click the **Lineage** option in the navbar.

<img src="screenshots/stream_lineage.png"/>

### Exploring the Simulation Topics and Statements

You can drag the Lineage graph around using your mouse. Zoom in/out using the buttons at bottom-right. Click on the various items noted below and spend time exploring the **Lineage** flow. This will help you better understand how Flink is processing your input Topics and producing new output Topics in your event stream.

- **Node & Stream Inspection:** Click on any topic or stream edge in the lineage graph to view real-time throughput metrics (records/sec, bytes/sec), active schemas registered in Schema Registry, partition distributions, and consumer lag.
- **Producer:** Topics flow from the Simulation producer and into the Flink Statements that you created. Click on the Topic icons in the Stream Lineage UI to trace events originating from the Simulation across raw topics such as `gathering-completed`, `manufacturing-started`, `manufacturing-completed`, `assembly-started`, and `assembly-completed`.
- **Flink Statements:** Identify the Flink Statement nodes representing your running `hive-inventory-jobs` statement set (as well as Level 2's `workstation_efficiency` joins).
- **Derived Sink Topics:** Observe the flow routing into `resource_inventory`, `parts_inventory` (the upsert changelog tables), and `workstation_efficiency`.

<img src="screenshots/lineage_flink_statements.png"/>

Click on a **Flink Statement** node to view useful stats like `Messages in per minute`. In the table, `Activity` is useful to observe a breakdown of the messages by Topic plus select `SQL Content` to view the SQL executing in this Flink statement.

- **Consumer Groups:** Locate and click on the Consumer Group nodes representing your local Hive Dashboard backend service reading the live inventory balances and raw events. In the table, you can view the total Bytes passing through your stream. While we are not reviewing how to size your instance, detailed memory usage is valuable when sizing your Confluent Cloud Cluster and Compute Pool.

<img src="screenshots/consumer_group.png"/>

---

## Explore the Level 3 Dashboard

The Level 3 Dashbaord clarifies what you've been learning about your Hive Simulation.

### Resource Gathering

The Gatherer bees in your Hive are organized to search for each resource along two paths, with two waypoints on each path.  The numbered circles show how many bees have been assigned to each waypoint.  Some paths and waypoints are shown as inactive/gray because no Gatherer bees have been assigned.

The rate of gathering resource is determined by the number of Gatherers at each waypoint:

- Single Gatherer generates 1 resource per 10 Simulation mins (10 seconds in real-time)
- Two Gatherers take 5 Simulation mins
- Three Gatherers take 3 Simulation mins

Each waypoint can host a max of three Gatherers for a max of 12 Gatherers per resource.

<img src="screenshots/resource_gathering.png"/>

### Manufacturing and Assembly Workstation

In Level 2, you discovered the workstations were gathering resources and manufacturing parts at different rates: 10 mins, 5 mins and 3 mins. To simplify the visual depiction for this rate of production, each workstation Tier now displays as a hexagon graphic.  At start though, your Hive's workstations are all Tier 1:

- Tier 1 = 1 chevron = 1 unit per 10 mins
- Tier 2 = 2 chevrons = 1 unit per 5 mins
- Tier 3 = 3 chevrons = 1 unit per 3 mins

<img src="screenshots/workstation_tiers.png"/>

### Required Inputs

You will also see that each manufacturing and worker assembly station now shows its required inputs. This value is obtained from the `manufacturing-started` and `assembly-started` events.

<img src="screenshots/required_inputs.png"/>

### Level 4: The Queen's Orders

You may be asking yourself, what is the motivating force behind manufacturing these robots? Where is the Queen that is managing the Hive? The Queen decides which robots the Hive builds: a Gatherer to speed up a gathering station, an Engineer to upgrade a manufacturing or assembly workstation from Tier 1 to 2 or Tier 2 to 3, or a Builder to build a new workstation (which starts at Tier 1).

Level 4 introduces the Queen and her orders for additional workers. The Queen can place orders for new Workers plus assign them to specific tasks. And as you guessed, Kafka events are generated to let us know about the Queen's requests:

- `queen-worker-ordered`
- `worker-assigned`

Your task in Level 4 will be aggregating these into a new `queens_orders` topic to track progress of this activity. Using Flink again, you will turn those events into a live queue that the assembly line works through, first in first out.  

And yes, handing the Queen's decisions over to your preferred AI coding assistant will occur in a later level.

## Next Step

After exploring the updated Simulation Dashboard, proceed to [Level 4 - Queen's Orders](../level-4-queens-orders/README.md).
