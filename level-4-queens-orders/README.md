# The Queen's Orders

## Overview & Goal

At the end of Level 3, you may have noticed a UI element in the top-right of your Hive Dashboard: the list of orders for robots in the **Queen's Orders**.  As below, there are orders for new Workers in the queue.  The left-most icon indicates the next robot in queue to be assembled once parts are available.

<img src="screenshots/queens_orders.png"/>

In the queue above for the Queen's orders, we can see:

- **Next to be assembled:** Gatherer to upgrade a Resin workstation
- **After that:** Gatherer to upgrade the Metals workstation
- **And after that:** Engineer to upgrade an Actuator workstation

The **Queen** decides which new Worker robots are required to improve the Hive and in what order. And she does this by publishing **events**.

**The Problem:** The Queen's orders are separate events (`queen-robot-ordered`, `queen-robot-assigned`, and so on).  No single event says "here is the queue right now".  To know what is waiting to be built, every event consumer would have to cache every order and subtract the ones already in assembly or assigned, which means also tracking the assembly status of Worker robots in the Assembly process.

**Your Objective:** Use Apache Flink to fold these events into a `queens_orders` table with one row per order.  Your Hive Dashboard can then read that table to draw the queue, so the queue on screen is nothing more than a view of your Flink output.

### How do the different Worker types behave?

The Queen can order three kinds of Worker robots.  Each order names the workstation the Worker is for:

| Worker Type | What it does | Allowed stations | `action` |
|---|---|---|---|
| **Gatherer** | Speeds up a gathering station | Gathering stations only (`copper`, `energy`, `metals`, `resin`, `silicon`) | `upgrade` |
| **Engineer** | Speeds up a station | Manufacturing or assembly stations only | `upgrade` |
| **Builder** | Adds a new station | Any station group | `add` |

> **Not wired up yet:** a finished robot is assigned to its order (`queen-robot-assigned`), but the assignment does not change the station yet.  The dashboard therefore shows the queue and its status changes, and the stations keep their starting tiers.

### New Kafka Topics and Table

Your Hive Simulation includes two Queen topics:

| Topic | Written when |
|---|---|
| `queen-robot-ordered` | The Queen places an order. Carries `order_id`, `robot_type`, `station`, `action`. |
| `queen-robot-assigned` | A robot finished assembly and was assigned. `causation_id` is the id of the `assembly-completed` event. |


Note that we must also track when the Queen's orders have been processed.  The `assembly-started` topic triggers the removal of an order from the open order queue.  So your Flink SQL must process these 3 topics to track status of the Queen's order queue:

```
queen-robot-ordered ────┐
assembly-started ───────┼──► Flink GROUP BY order_id ───►  queens_orders
queen-robot-assigned ───┘   (highest lifecycle_stage wins)  (upsert changelog)
```

Flink gives every event a `lifecycle_stage`, groups the events by `order_id`, and the highest `lifecycle_stage` seen for an order becomes its status:

| Event | `lifecycle_stage` | Status |
|---|---|---|
| `queen-robot-ordered` | 1 | `OPEN` |
| `assembly-started` (with an `order_id`) | 2 | `IN_ASSEMBLY` |
| `queen-robot-assigned` | 3 | `ASSIGNED` |

---

## Why is this important in Event Streaming? (Event Sourcing)

* **Commands become facts.** The Queen does not edit a queue.  She appends `ordered` events, and each is a permanent record of what she decided and when.
* **State is derived.** The queue is a *projection* of those events.  Flink holds the running state and emits the latest row per order, exactly like the inventory balance in Level 3, but keyed by `order_id` instead of by item.
* **Anyone can build their own view.** The dashboard reads `queens_orders`, but a different team could read the same `queen-robot-*` topics and build an audit trail or a fairness report, without any change to the Simulation.

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

* **`lifecycle_stage` makes the result order-independent.** Events from different topics can reach Flink in any order.  Taking the highest `lifecycle_stage` means an order never moves backwards, even if `assembly-started` arrives before `queen-robot-ordered`.
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

### The Queen's Buttons

Every workstation now has buttons that act as the Queen:

* **Gathering stations:** the **Gatherer** button orders a **Gatherer** to upgrade the station.
* **Manufacturing and assembly stations:** the **Engineer** button orders an **Engineer** to upgrade the station.
* **Every station group:** the **Builder** button, next to the dashed hexagon, orders a **Builder** to add a station.

Pressing a button sends one order to the Simulation as a `queen-robot-ordered` event.  The dashboard does **not** put the order in the queue itself.  It appears in the **Queen's Orders** only after the event has travelled through Flink into `queens_orders`, which is why there can be a moment between the click and the new icon.

### Watching the Status Change

Place an order, then watch its icon in the queue.  While earlier orders are built, it waits.  When its turn comes, assembly starts, the icon leaves the queue and the same row in `queens_orders` changes from `OPEN` to `IN_ASSEMBLY`.  You can see the row change by rerunning the Step 3 query.

---

## What's Next: Part Prioritization (Level 5)

The queue answers *what* the Hive should build next.  It raises a new question: how do we prioritize **parts manufacturing** based on the robot at the front of the queue?

The **Robot Assembly** stations "know" the parts they need, but they are independent of **Parts Manufacturing**.  The non-event-driven solution would be a hard-coded REST call to place orders for parts based on the next robot in the queue.  Instead, you can use Flink to join `queens_orders` with the recipe inputs from `assembly-started` and produce a new topic that drives a **Parts Manufacturing Queue**.  That is Level 5.  Handing the Queen's decisions to your AI coding assistant comes in the later levels.

## Useful CLI Commands

```bash
# Short status of one statement (the plain `describe` and `list` print the whole SQL)
confluent flink statement describe hive-queens-orders-jobs -o json | grep -E '"(name|status|status_detail)"'

# Stop a statement (use only if you need to restart).
# Deleting is not instant: wait a few seconds, until the name is free, before creating it again.
confluent flink statement delete hive-queens-orders-jobs
```

## Next Step

After exploring the Level 4 Dashboard, proceed to Level 5 - Part Prioritization (coming soon).
