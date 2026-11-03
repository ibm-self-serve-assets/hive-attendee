# The Queen's Orders with Apache Flink (Confluent CLI)

## Overview & Goal

At the end of Level 3, you may have noticed a UI element in the top-right of your Hive Dashboard: the list of orders for robots in the **Robot assembly queue**.  As below, there are 3 orders in the queue: 2 x **G**atherer robots followed by an **E**ngineer robot.  The left-most icon indicates the next robot in queue to be assembled once parts are available.

<img src="screenshots/robot_assembly_queue.png"/>

Until now, that queue has been a black box.  In Level 4, the **Queen** takes control of it.  She decides which robots the Hive builds and in what order, and she tells the Hive by publishing **events** rather than by calling the assembly line directly.

**The Problem:** The Queen's orders are separate events (`queen-robot-ordered`, `queen-robot-cancelled`, and so on).  No single event says "here is the queue right now".  To know what is waiting to be built, a consumer would have to replay every order and subtract everything that was cancelled or has already started assembly.

**Your Objective:** Use Apache Flink to fold those events into a `queens_orders` table with one row per order.  The dashboard reads that table to draw the queue, so the queue on screen is nothing more than a view of your Flink output.

### What robots do

The Queen orders three kinds of robot.  Each order names the workstation the robot is for:

| Robot | What it does | Allowed stations | `action` |
|---|---|---|---|
| **Gatherer** | Speeds up a gathering station | Gathering stations only (`copper`, `energy`, `metals`, `resin`, `silicon`) | `upgrade` |
| **Engineer** | Speeds up a station | Manufacturing or assembly stations only | `upgrade` |
| **Builder** | Adds a new station | Any station group | `add` |

The Simulation rejects an order that breaks these pairing rules, so the queue only ever holds valid orders.

> **Not wired up yet:** a finished robot is assigned to its order (`queen-robot-assigned`), but the assignment does not change the station yet.  The dashboard therefore shows the queue and its status changes, and the stations keep their starting tiers.

### New Kafka Topics and Table

The Simulation adds three Queen topics to the ones you created in Level 1, and extends two existing ones with an `order_id`:

| Topic | Written when |
|---|---|
| `queen-robot-ordered` | The Queen places an order. Carries `order_id`, `robot_type`, `station`, `action`. |
| `queen-robot-cancelled` | The Queen cancels an order that is still in the queue. |
| `queen-robot-assigned` | A robot finished assembly and was assigned. `causation_id` is the id of the `assembly-completed` event. |
| `assembly-started` / `assembly-completed` | Now carry the `order_id` they were built for. |

```
queen-robot-ordered ────┐
assembly-started ───────┤
                        ├──► Flink GROUP BY order_id ───►  queens_orders
queen-robot-assigned ───┤        (highest rank wins)       (upsert changelog)
queen-robot-cancelled ──┘
```

If your Level 1 topics were created before this level was added, rerun `provision_topics.py` from Level 1.  It is safe to run twice.

---

## Why is this important in Event Streaming? (Event Sourcing)

* **Commands become facts.** The Queen does not edit a queue.  She appends `ordered` and `cancelled` events, and each is a permanent record of what she decided and when.
* **State is derived.** The queue is a *projection* of those events.  Flink holds the running state and emits the latest row per order, exactly like the inventory balance in Level 3, but keyed by `order_id` instead of by item.
* **Anyone can build their own view.** The dashboard reads `queens_orders`, but a different team could read the same `queen-robot-*` topics and build an audit trail or a fairness report, without any change to the Simulation.

---

## Prerequisites

- Level 3 is complete: `resource_inventory` exists and its statement is **Running**.
- The Simulation is running and events are flowing.
- The Confluent CLI is installed and you are logged in (see [Level 3, Steps 1 and 2](../level-3-hive-inventory/README.md)).  Use the same `ENV_ID`, `CLUSTER_ID` and `POOL_ID` variables.

```bash
echo $ENV_ID/$CLUSTER_ID/$POOL_ID
```

If that prints empty values, export them again as described in Level 3.

---

## Step 1 — Create the Orders Sink Table

**NOTE:** Ensure your Terminal window is in the **Level 4 directory** when running the following commands.

Create the `queens_orders` table in Flink and the backing Kafka topic with upsert changelog mode.

```bash
confluent flink statement create hive-queens-orders-sink \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/01_create_sink.sql)" > /dev/null
```

Confirm it succeeded:
```bash
confluent flink statement describe hive-queens-orders-sink -o json | grep -E '"(status|status_detail)"'
```

**Expected result:** status `COMPLETED`.  This is a DDL statement, so it runs once and finishes.  It starts as `PENDING`, so wait a few seconds and check again.

If the status is `FAILED`, the `status_detail` line explains why.

The table has one row per order:

| Column | Meaning |
|---|---|
| `simulation_id`, `run_id`, `order_id` | The primary key. `run_id` changes when the Simulation restarts. |
| `robot_type` | `gatherer`, `engineer` or `builder` |
| `station` | The workstation the robot is for, e.g. `resin` |
| `action` | `upgrade` or `add` |
| `placed_seq` | The `event_sequence` of the order. Lower means earlier in the queue. |
| `status` | `OPEN`, `IN_ASSEMBLY`, `ASSIGNED` or `CANCELLED` |

---

## Step 2 — Start the Orders Job

Run `02_run_jobs.sql` to start the continuous streaming statement.

```bash
confluent flink statement create hive-queens-orders-jobs \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/02_run_jobs.sql)" > /dev/null
```

Confirm it is running:

```bash
confluent flink statement describe hive-queens-orders-jobs -o json | grep -E '"(status|status_detail)"'
```

**Expected result:** It starts as `PENDING` and can take a minute or two to reach `RUNNING`.  Execute the command as needed until `RUNNING` is displayed.

### How the Queue Is Computed

The job reads four streams and gives every event a **rank**.  It groups the events by `order_id`, and the highest rank seen for an order becomes its status:

| Event | Rank | Status |
|---|---|---|
| `queen-robot-ordered` | 1 | `OPEN` |
| `assembly-started` (with an `order_id`) | 2 | `IN_ASSEMBLY` |
| `queen-robot-assigned` | 3 | `ASSIGNED` |
| `queen-robot-cancelled` | 4 | `CANCELLED` |

Two details are worth noticing:

* **Rank makes the result order-independent.** Events from different topics can reach Flink in any order.  Taking the highest rank means an order never moves backwards, even if `assembly-started` arrives before `queen-robot-ordered`.
* **`MAX()` fills the gaps.** Only some events carry `robot_type`, `station` and `action`.  `MAX()` ignores `NULL`, so whichever event brings a value fills it in.  `placed_seq` comes only from the ordered event.

Cancelling is only possible while an order is `OPEN`.  Once `assembly-started` takes the order off the queue, the Simulation answers a cancel request with `422`, so `CANCELLED` never follows `IN_ASSEMBLY`.

The **queue** on the dashboard is the rows with `status = 'OPEN'`, sorted by `placed_seq`: first in, first out.

---

## Step 3 — Validate using Flink Shell

**1. Open the Flink shell.**
```bash
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```
A `>` prompt appears when the shell is ready.

**2. Copy the query** from `flink/03_validate.sql`, paste it at the `>` prompt, and press **Enter**.

**3. Read the result.** After a delay of 5-10 seconds a table of results opens and auto-updates while the Simulation runs.

You should see:
- On a fresh run, 8 rows, all `OPEN`: the Queen's initial orders.
- Rows move to `IN_ASSEMBLY` as the assembly line starts building them, then to `ASSIGNED` once the robot is built.
- A cancelled order shows `CANCELLED`.
- If you restarted the Simulation, earlier runs are listed too.  Each run has its own `run_id`.

**4. Congratulations! Level 4 Achieved!!!**

Open your Hive Dashboard and select **Level 4.**  The queue on screen is the same data as in the Flink Shell.  The dashboard updates within a second of a new value being written, while the Flink Shell can lag by up to a minute.  Both read the same `queens_orders` topic, but the dashboard backend uses `read_uncommitted` and the shell uses `read_committed`, which only shows records after Flink's checkpoint transaction commits.

**5. Close the results and the shell.** Press `Q` to close the results. Then type `EXIT;` or press `Ctrl+D` to close the shell.

> **Gate Check:** The dashboard Level 4 view unlocks once the `queens_orders` topic exists.  Running `01_create_sink.sql` (Step 1) creates it.

---

## Explore the Level 4 Dashboard

### The Queen's Buttons

Every workstation now has buttons that act as the Queen:

* **Gathering stations:** the **Forager** button orders a **Gatherer** to upgrade the station.
* **Manufacturing and assembly stations:** the **Engineer** button orders an **Engineer** to upgrade the station.
* **Every station group:** the **Builder** button, next to the dashed hexagon, orders a **Builder** to add a station.

Pressing a button sends one order to the Simulation as a `queen-robot-ordered` event.  The dashboard does **not** put the order in the queue itself.  It appears in the **Robot assembly queue** only after the event has travelled through Flink into `queens_orders`, which is why there can be a moment between the click and the new icon.

### Cancelling an Order

Hover over a robot in the queue and click the **x** that appears to cancel the order.  This is allowed only while the order is `OPEN`.  When assembly starts, the robot leaves the queue and can no longer be cancelled.

### Watching the Status Change

Place an order, then watch its icon in the queue.  While earlier orders are built, it waits.  When its turn comes, assembly starts, the icon leaves the queue and the same row in `queens_orders` changes from `OPEN` to `IN_ASSEMBLY`.  You can see the row change in the Flink Shell by rerunning the Step 3 query.

---

## What's Next: Prioritizing Parts Manufacturing

The queue answers *what* the Hive should build next.  It raises a new question: how do we prioritize **parts manufacturing** based on the robot at the front of the queue?

The **Robot Assembly** stations "know" the parts they need, but they are independent of **Parts Manufacturing**.  The non-event-driven solution would be a hard-coded REST call to place orders for parts based on the next robot in the queue.  Instead, you can use Flink to join `queens_orders` with the recipe inputs from `assembly-started` and produce a new topic that drives a **Parts Manufacturing Queue**.  That, and handing the Queen's decisions to your AI coding assistant, are the later levels.

## Useful CLI Commands

```bash
# Short status of one statement (the plain `describe` and `list` print the whole SQL)
confluent flink statement describe hive-queens-orders-jobs -o json | grep -E '"(name|status|status_detail)"'

# Stop a statement (use only if you need to restart).
# Deleting is not instant: wait a few seconds, until the name is free, before creating it again.
confluent flink statement delete hive-queens-orders-jobs
```

## Next Step

After exploring the Level 4 Dashboard, proceed to Level 5 - Tableflow.
