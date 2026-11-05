# The Queen's Orders

## Overview & Goal

You are getting closer to implementing your AI Queen.  First, you need to add logic to integrate your queen with the other systems in your hive.  The **Queen** decides which new Worker robots are required to improve the Hive and in what order. And she does this by publishing an `queen-worker-ordered` event.  You may have noticed this event earlier when you intially provisioned all the events provided by the Hive Simulation server.

**The Problem:** The Queen's order for a new Worker (`queen-worker-ordered`) is separate from the `assembly-started` and `worker-assigned` events.  So there is no single event says "here is the **Queen's Worker Order** queue right now.  To know what is waiting to be built, every event consumer would have to cache every order and subtract the ones already in assembly or assigned, which means also tracking the assembly status of Worker robots in the Assembly process.

**Your Objective:** Use Apache Flink to fold these events into a `queens_orders` table with one row per order.  Your Hive Dashboard can then read that table to render a **Worker Order Queue**.

### Types of Worker Orders?

The Queen can order three kinds of **Workers**.  Each order names the workstation the Worker is for:

| Worker Type | What it does | Allowed Units | `action` |
|---|---|---|---|
| **Gatherer** | Adds gatherer to a region | `copper`, `energy`, `metals`, `resin`, `silicon` | `upgrade` |
| **Engineer** | Upgrade up a workstation | Manufacturing or assembly stations only | `upgrade` |
| **Builder** | Adds a new workstation | Manufacturing or Assembly | `add` |

> **Not wired up yet:** a finished robot is assigned to its order (`worker-assigned`), but the assignment does not change the station yet.  The dashboard therefore shows the queue and its status changes, and the stations keep their starting tiers.

### New Kafka Topics and Table

Your Hive Simulation includes these two topics:

| Topic | Written when |
|---|---|
| `queen-worker-ordered` | The Queen places an order. Carries `order_id`, `robot_type`, `station`, `action`. |
| `worker-assigned` | A robot finished assembly and was assigned. `causation_id` is the id of the `assembly-completed` event. |

Note that we must also track when the Queen's orders have been processed.  The `assembly-started` topic triggers the removal of an order from the open order queue.  So your Flink SQL must process these 3 topics to track status of the Queen's order queue:

```
queen-worker-ordered ────┐
assembly-started ───────┼──► Flink GROUP BY order_id ───►  queens_orders
worker-assigned ───┘   (highest lifecycle_stage wins)  (upsert changelog)
```

Flink gives every event a `lifecycle_stage`, groups the events by `order_id`, and the highest `lifecycle_stage` seen for an order becomes its status:

| Event | `lifecycle_stage` | Status |
|---|---|---|
| `queen-worker-ordered` | 1 | `OPEN` |
| `assembly-started` (with an `order_id`) | 2 | `IN_ASSEMBLY` |
| `worker-assigned` | 3 | `ASSIGNED` |

---

## Why is this important in Event Streaming? (Event Sourcing)

* **Commands become facts.** The Queen does not edit a queue.  She publishes `queen-worker-ordered` events, and each is a permanent record of what she decided and when.
* **State is derived.** The queue is a *projection* of those events.  Flink holds the running state and emits the latest row per order, exactly like the inventory balance in Level 3, but keyed by `order_id` instead of by item.
* **Anyone can build their own view.** The dashboard reads `queens_orders`, but a different team could read the same `queen-worker-ordered` and `worker-assigned` topics and build an audit trail or a fairness report, without any change to the Simulation.

---

## Prerequisites

- Level 3 is complete: `resource_inventory` and `parts_inventory` exist and their statements are **Running**.
- The Simulation is running and events are flowing.
- You know how to execute a Flink SQL script in Confluent Cloud, using either the **Confluent Cloud UI** (Level 2) or the **Confluent CLI** (Level 3).

---

## Run the Level 4 Scripts

Execute the three scripts in the [`flink/`](flink/) directory, in order, using whichever method you prefer: the **Confluent Cloud UI** (as in Level 2) or the **Confluent CLI** (as in Level 3).  The steps are the same as in those levels, only the SQL files are new.

| Step | Script | Type | Expected status |
|---|---|---|---|
| 1 | [`01_create_sink.sql`](flink/01_create_sink.sql) | DDL: runs once | `COMPLETED` |
| 2 | [`02_run_jobs.sql`](flink/02_run_jobs.sql) | DML: runs continuously | `RUNNING` |
| 3 | [`03_validate.sql`](flink/03_validate.sql) | Query: for checking only | Results appear |

If you use the CLI, run the commands from the **Level 4 directory** with the same `$ENV_ID`, `$CLUSTER_ID` and `$POOL_ID` variables as Level 3.  Suggested statement names are `hive-queens-orders-sink` and `hive-queens-orders-jobs`.

---

## Step 1 — Create the Orders Sink Table

Execute `01_create_sink.sql`.  It creates the `queens_orders` table in Flink and the backing Kafka topic with upsert changelog mode.  This is a DDL statement, so it runs once and finishes with status `COMPLETED`.

The table has one row per order:

| Column | Meaning |
|---|---|
| `simulation_id`, `run_id`, `order_id` | The primary key. `run_id` changes when the Simulation restarts. |
| `robot_type` | `gatherer`, `engineer` or `builder` |
| `station` | The workstation the robot is for, e.g. `resin` |
| `action` | `upgrade` or `add` |
| `placed_seq` | The `event_sequence` of the order. Lower means earlier in the queue. |
| `status` | `OPEN`, `IN_ASSEMBLY` or `ASSIGNED` |

---

## Step 2 — Start the Orders Job

Execute `02_run_jobs.sql` to start the continuous streaming statement.  It starts as `PENDING` and can take a minute or two to reach `RUNNING`.  Do not continue until it is `RUNNING`, and leave it running: the dashboard's Level 4 view depends on it.

### How the Queue Is Computed

The job applies the `lifecycle_stage` table from the overview above.  Two details are worth noticing:

* **`lifecycle_stage` makes the result order-independent.** Events from different topics can reach Flink in any order.  Taking the highest `lifecycle_stage` means an order never moves backwards, even if `assembly-started` arrives before `queen-worker-ordered`.
* **`MAX()` fills the gaps.** Only some events carry `robot_type`, `station` and `action`.  `MAX()` ignores `NULL`, so whichever event brings a value fills it in.  `placed_seq` comes only from the ordered event.

Orders cannot be cancelled: once the Queen places an order it stays until its robot is built and assigned.

The **queue** on the dashboard is the rows with `status = 'OPEN'`, sorted by `placed_seq`: first in, first out.

---

## Step 3 — Validate the Results

Execute the query in `03_validate.sql`, either in a new cell of the Flink SQL Workspace or at the prompt of the Flink shell (`confluent flink shell --compute-pool $POOL_ID --environment $ENV_ID --database $CLUSTER_ID`).  The Simulation should be running so you can watch the rows change.  After a delay of 5-10 seconds a table of results appears and auto-updates.

You should see:
- On a fresh run, 8 rows, all `OPEN`: the Queen's initial orders.
- Rows move to `IN_ASSEMBLY` as the assembly line starts building them, then to `ASSIGNED` once the robot is built.
- If you restarted the Simulation, earlier runs are listed too.  Each run has its own `run_id`.

When you have verified the results, stop this query (**Stop** in the UI, or press `Q` in the shell, then `EXIT;` or `Ctrl+D` to close it).  Only the `02_run_jobs.sql` statement needs to keep running.

**Congratulations! Level 4 Achieved!!!**

Open your Hive Dashboard and select **Level 4.**  The queue on screen is the same data as in the validation query.  The dashboard updates within a second of a new value being written, while the Flink Shell can lag by up to a minute.  Both read the same `queens_orders` topic, but the dashboard backend uses `read_uncommitted` and the shell uses `read_committed`, which only shows records after Flink's checkpoint transaction commits.

> **Gate Check:** The dashboard Level 4 view unlocks once the `queens_orders` topic exists.  Running `01_create_sink.sql` (Step 1) creates it.

---

## Explore the Level 4 Dashboard

Level 4 will now be active so you can view the **Queen's orders** in the top-right of your Hive Dashboard.  The left-most icon indicates the next robot in queue to be assembled once parts are available.

<img src="screenshots/queens_orders.png"/>

In the queue above for the Queen's orders, we can see:

- **Next to be assembled:** Add Gatherer to a Resin workstation
- **After that:** Engineer to upgrade the Actuator workstation
- **And after that:** Builder to add a new Actuator workstation

---

## Part Prioritization

The queue answers *what* the Hive should build next.  It raises a new question: how do we prioritize **parts manufacturing** based on the next Worker in the queue?

The **Robot Assembly** stations "know" the parts they need, but they are independent of **Parts Manufacturing**.  The non-event-driven solution would be a hard-coded REST call to place orders for parts based on the next robot in the queue.  Instead, you'll use Flink to join `queens_orders` with the recipe inputs from `assembly-started` and produce a new topic that drives a **Parts Manufacturing Queue**.

## Useful CLI Commands

```bash
# Short status of one statement (the plain `describe` and `list` print the whole SQL)
confluent flink statement describe hive-queens-orders-jobs -o json | grep -E '"(name|status|status_detail)"'
```

## Parts Manufacturing Prioritization

The problem with isolated systems within any Organization is that they struggle to coordinate their activities.  Especially when it's a Queen isolated in the Hive's safest interior.  Execution of the Queen's orders requires tight coordination between the Part Manufacturing and Worker Assembly teams.  To achieve this, we need to extract real-time data from `assembly-started` about the parts required to manufacture each **Worker Bee**. 

From `assembly-started` for a **Gatherer Worker**:
``` json
"station_id": "gatherer",
"output_type": "gatherer",   
   "inputs": {
    "chassis": 2,
    "electronics": 1,
    "battery": 5,
    "actuator": 6
}
```

Pairing this with each `queens_orders` event generates a `parts_priority_queue` to guide the **Parts Manufacturing Team** in generating the most in-demand parts.  

```
assembly-started ──► recipe per robot type ───┐
                     (payload.inputs)         ├──► Flink JOIN + SUM per part ──► parts_priority_queue
queens_orders ──► OPEN orders only ───────────┘                                  (upsert changelog)
```

### How the Priority Is Computed

1. **Identify required parts.** Each `assembly-started` event lists the parts its robot consumed.  Flink keeps one recipe per robot type (`gatherer`, `engineer`, `builder`) and reads each part by name, as in Level 3.
2. **Determine demand.** Only `queens_orders` rows with `status = 'OPEN'` count.  An order that is `IN_ASSEMBLY` has already taken its parts.
3. **Join and sum.** Each OPEN order is joined to the recipe of its `robot_type`, and the parts are summed per part.  The part with the highest `quantity_needed` is the most in-demand.

For example, if the Queen's open orders are one Gatherer, one Engineer and one Builder, the recipes combine like this:

| Part | Gatherer | Engineer | Builder | `quantity_needed` | Priority |
|---|---|---|---|---|---|
| `actuator` | 6 | 8 | 10 | **24** | 1 |
| `battery` | 5 | 2 | 4 | **11** | 2 |
| `chassis` | 2 | 1 | 3 | **6** | 3 |
| `electronics` | 1 | 3 | 2 | **6** | 3 |

When assembly starts for the Gatherer, its order is no longer OPEN, so Flink updates each row: `actuator` falls to 18, and so on.  When no OPEN order needs a part, its row is deleted.

> **Recipe appears after the first build:** a robot type only gets a recipe once its first `assembly-started` event has been seen, so until then its OPEN orders add no demand.  The table fills in as each robot type is first built.


### Run Scripts

Run the three new scripts in the [`flink/`](flink/) directory, in order, using whichever method you prefer: the **Confluent Cloud UI** (as in Level 2) or the **Confluent CLI** (as in Level 3).  You can use a different method for each step; the result is the same.

| Step | Script | Type | Expected status |
|---|---|---|---|
| 4 | [`04_create_priority_sink.sql`](flink/04_create_priority_sink.sql) | DDL: runs once | `COMPLETED` |
| 5 | [`05_run_priority_job.sql`](flink/05_run_priority_job.sql) | DML: runs continuously | `RUNNING` |
| 6 | [`06_validate_priority.sql`](flink/06_validate_priority.sql) | Query: for checking only | Results appear |

**Before you start:**
- The `hive-queens-orders-jobs` statement from Step 2 is still **Running**.  The new job reads from `queens_orders`, so it cannot produce anything without it.
- The Simulation is running and its timer is incrementing.
- **UI users:** open your Flink **SQL Workspace** in the `hive_dev` environment, with the same catalog (environment) and database (cluster) selected as in Level 2, and have 3 empty cells ready (click **+** as needed).
- **CLI users:** open a terminal in the **Level 4 directory** (`hive-attendee/level-4-queens-orders`) with the `$ENV_ID`, `$CLUSTER_ID` and `$POOL_ID` variables from Level 3 still set.  Check with `echo $ENV_ID/$CLUSTER_ID/$POOL_ID`.

### Step 4 — Create the Priority Sink Table

`04_create_priority_sink.sql` creates the `parts_priority_queue` table in Flink and its backing Kafka topic, with upsert changelog mode.  It is a DDL statement, so it runs once and finishes with status `COMPLETED`.

The table has one row per part:

| Column | Meaning |
|---|---|
| `simulation_id`, `run_id`, `part_id` | The primary key. `part_id` is `chassis`, `electronics`, `battery` or `actuator`. |
| `quantity_needed` | Units of the part needed by all OPEN orders. Higher means more urgent. |
| `open_orders` | How many OPEN orders need the part. |

**Using the UI**
1. Open [`flink/04_create_priority_sink.sql`](flink/04_create_priority_sink.sql), copy the entire contents and paste them into the **first workspace cell**.
2. Set the cell's **Mode** (bottom-right) to **Snapshot**, then click **Run**.
3. Wait for the status **Completed**.

**Using the CLI**
```bash
confluent flink statement create hive-parts-priority-sink \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/04_create_priority_sink.sql)" > /dev/null

confluent flink statement describe hive-parts-priority-sink -o json | grep -E '"(status|status_detail)"'
```
The `> /dev/null` hides the CLI's echo of the whole SQL file; errors are still shown.  The status starts as `PENDING`, so repeat the `describe` command after a few seconds until it shows `COMPLETED`.  If it shows `FAILED`, the `status_detail` line explains why.

---

### Step 5 — Start the Priority Job

`05_run_priority_job.sql` starts the continuous statement that joins the OPEN orders in `queens_orders` with the robot recipes from `assembly-started`, and keeps `parts_priority_queue` up to date.  It starts as `PENDING` and can take a minute or two to reach `RUNNING`.  Do not continue until it is `RUNNING`, and leave it running.

**Using the UI**
1. Open [`flink/05_run_priority_job.sql`](flink/05_run_priority_job.sql), copy the entire contents and paste them into the **second workspace cell**.
2. Click **Run**.  The status is **Running** once it has started.
3. Do **not** click **Stop**: that terminates the job.  You can close the SQL Workspace after Step 6 and the job keeps running in the background.
4. To check it later, go to **Flink** → **Statements** in the `hive_dev` environment.  The statement of type **Execute Statement Set** must have status **Running**.

**Using the CLI**
```bash
confluent flink statement create hive-parts-priority-jobs \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/05_run_priority_job.sql)" > /dev/null

confluent flink statement describe hive-parts-priority-jobs -o json | grep -E '"(status|status_detail)"'
```
This command may take a few seconds to return.  Repeat the `describe` command until it shows `RUNNING`.

> **Gate Check:** Both `hive-queens-orders-jobs` (Step 2) and `hive-parts-priority-jobs` (Step 5) must be `RUNNING` before you continue.

---

### Step 6 — Validate the Results

`06_validate_priority.sql` is a query for checking only.  The Simulation should be running so you can watch the rows change.

**Using the UI**
1. Open [`flink/06_validate_priority.sql`](flink/06_validate_priority.sql), copy the entire contents and paste them into the **third workspace cell**.
2. Click **Run**.  Rows can take **up to a minute** to appear, because the query reads committed output and Flink commits about once a minute.
3. When you have verified the results, click **Stop** on this cell only.  Do not stop the Step 5 cell.
4. Close the SQL Workspace tab (**x**, top-left).  The Step 5 statement stays running.

**Using the CLI**

Open the Flink shell:
```bash
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```
At the `>` prompt, paste the query from `flink/06_validate_priority.sql` and press **Enter**.  The shell may show a typeahead hint; ignore it.  You will see `statement phase pending`, then a table opens after 5-10 seconds and auto-updates.  When you have verified the results, press `Q` to close the table, then type `EXIT;` or press `Ctrl+D` to leave the shell.

**What you should see**
- Up to 4 rows per run: `chassis`, `electronics`, `battery` and `actuator`.  Flink cannot sort a live stream, so read down from the highest `quantity_needed` to get the priority.
- `actuator` and `battery` near the top while the Queen has Engineer or Builder orders open, because those recipes need the most units.
- `quantity_needed` rising when the Queen places an order, and falling when assembly starts for an OPEN order.
- Earlier runs listed too if you restarted the Simulation.  Each run has its own `run_id`.
- If no rows appear after a couple of minutes, check that the Simulation timer is incrementing and that both jobs are `RUNNING`.  Remember that a robot type has no recipe until its first `assembly-started` event.

**Congratulations! Your Parts Manufacturing Team now has a `parts_priority_queue`!**  The next level builds on this topic.

---

### Useful CLI Commands

```bash
# Short status of the priority statements
confluent flink statement describe hive-parts-priority-jobs -o json | grep -E '"(name|status|status_detail)"'

# Stop a statement (use only if you need to restart).
# Deleting is not instant: wait a few seconds, until the name is free, before creating it again.
confluent flink statement delete hive-parts-priority-jobs
```
