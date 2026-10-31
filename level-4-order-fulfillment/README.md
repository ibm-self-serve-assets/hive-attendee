# Order Fulfillment

## Overview & Goal

In Level 3, you built a live inventory ledger by aggregating resource and parts deltas in real time. You could see how much stock was on hand — but you had no idea *why* it was being consumed. Level 4 adds **orders**: every robot that rolls off the assembly line fulfils a standing order and earns coins for the Hive's Treasury.

**The Problem:** The Simulation is assembling robots as fast as it can, but there is no signal connecting output to demand. You can see inventory change, but you cannot tell which resources are in most need to manufacture parts in limited supply.

**Your Objective:** Use the new `order-placed` event stream to derive — in real time — what resources are required to fulfil the current open order, compare that against your live inventory and identify which gathering station is the bottleneck.

### New Kafka Topics

| Topic | Retention | Contents |
|---|---|---|
| `order-placed` | 24 hours | One event per order opened; carries `order_id`, `quantity_engineer`, `quantity_gatherer`, `created_at_sim_minute` |
| `order-fulfilled` | 24 hours | One event per robot shipped; carries `order_id`, `quantity_engineer`, `quantity_gatherer`, `coins_received`, `fulfilled_at_sim_minute` |

### New Flink Topic: `hive_order_resource_requirements`

```
order-placed  ──► Flink join with BOM  ──►  hive_order_resource_requirements
                    (station_recipes          (resource_id → quantity_needed)
                     from simulation.state)

hive_order_resource_requirements  ─┐
                                    ├──► JOIN hive_inventory_balances
hive_inventory_balances  ───────────┘        → gap = needed − on_hand
                                             → identifies bottleneck station
```

---

## Prerequisites

- Level 3 is complete: `hive_inventory_balances` exists and `hive-inventory-jobs` is **Running**.
- The Simulation is running and events are flowing.
- The Confluent CLI is installed and authenticated (see Level 3, Steps 1).

---

## Step 1 — Provision the Order Topics

The order topics must exist in your Confluent cluster before the Simulation server will publish to them. Open a new terminal window then execute these commands:

```bash
cd level-4-order-fulfillment/scripts
chmod +x provision_order_topics.sh
./provision_order_topics.sh
```

Expected output:
```
Topics   : 2

  ✓ Created  order-placed
  ✓ Created  order-fulfilled

All topics provisioned. Your Level 4 dashboard will unlock automatically.
```

> **Gate Check:** Once both topics exist in Confluent, the dashboard sidebar will unlock the Level 4 view automatically.


### Look Inside [scripts/provision_order_topics.py](scripts/provision_order_topics.py)

The [provision_order_topics.sh](scripts/provision_order_topics.sh) is a wrapper for exeucting Python code in a virtual environment (venv) so the real work happens in [provision_order_topics.py](scripts/provision_order_topics.py).  That .py script read `event_payloads_orders.json` then calls **Confluent Admin REST APIs** for each topic name:

```
POST {CONFLUENT_REST_ENDPOINT}/kafka/v3/clusters/{CONFLUENT_CLUSTER_ID}/topics
Authorization: Basic <base64(api_key:api_secret)>
Content-Type: application/json

{
  "topic_name":        "order-placed",
  "partitions_count":  1,
  "replication_factor": 3,
  "configs": [
    { "name": "cleanup.policy", "value": "delete" },
    { "name": "retention.ms",   "value": "86400000" }
  ]
}
```

While the event is called `"order.placed"` in `event_payloads_orders.json`, dots replace hyphens to match Kafka's Topic nomenclature. `partitions_count` = `1` as each Hive Workshop attendee owns exactly one simulation with one producer and one consumer. A single partition guarantees ordering and keeps things simple — extra partitions would add rebalancing complexity for no benefit. `replication_factor` = `3` which is Confluent Cloud's default. Messages are copied across three brokers so the topic survives a broker going down — important for a topic that only retains 24 hours of data and cannot be replayed beyond that window. 

`cleanup.policy` is `"delete"` as old messages are discarded once they exceed the retention window. Order events are activity events — their history does not need to be replayed forever. `retention.ms` = `86400000` (24 hours in milliseconds). Long enough to cover a full workshop session; short enough to avoid storage costs accumulating across days. 

---

## Step 2 — Observe the Order Event Stream

Watch orders arrive and get fulfilled in real time. This gives you a feel for the data before you start writing Flink SQL.

### See placed orders

Execute these commands in the same Terminal where you ran Flink Shell in Level 3.  If you closed that window, then you need to replace the cluster and environment variables with your own.

`confluent kafka topic consume` reads from the Kafka cluster directly, so the CLI needs a **Kafka API key** for your cluster. Use the same `CONFLUENT_API_KEY` and `CONFLUENT_API_SECRET` from your Level 1 `.env` file. Run this once per cluster:

```bash
confluent api-key store <CONFLUENT_API_KEY> <CONFLUENT_API_SECRET> --resource $CLUSTER_ID
confluent api-key use <CONFLUENT_API_KEY> --resource $CLUSTER_ID
```

If you see `Error: no API key selected for resource "lkc-..."`, this step was skipped.

```bash
confluent kafka topic consume order-placed \
  --from-beginning \
  --print-key \
  --cluster $CLUSTER_ID \
  --environment $ENV_ID
```

You should see JSON payloads like:
```json
{
  "order_id": "ORD-000001",
  "quantity_engineer": 1,
  "quantity_gatherer": 0,
  "created_at_sim_minute": 0
}
```

Each order is for exactly **one robot**. Orders alternate between engineer and gatherer. A new order is placed the moment the previous one is fulfilled — so there is always exactly one open order.

### See fulfilled orders

```bash
confluent kafka topic consume order-fulfilled \
  --from-beginning \
  --print-key \
  --cluster $CLUSTER_ID \
  --environment $ENV_ID
```

Fulfilled order payload:
```json
{
  "order_id": "ORD-000001",
  "quantity_engineer": 1,
  "quantity_gatherer": 0,
  "coins_received": 250,
  "fulfilled_at_sim_minute": 47
}
```

Notice the gap between `created_at_sim_minute` (0) and `fulfilled_at_sim_minute` (47) — that is the fulfilment time in simulation minutes. The narrower this gap, the more throughput your factory has.

---

## Step 3 — Create the Order Resource Requirements Sink

This step creates the Flink table and the backing Kafka topic that will hold, for each open order, how many units of each resource are required to build the robot it asks for.

### 3a. Understand the Bill of Materials (BOM)

The Simulation publishes a `simulation.initialized` event to the `simulation-state` topic whenever a run begins. Its payload includes `station_recipes` — the full BOM for every manufacturing and assembly station:

```json
{
  "station_recipes": {
    "structural_molding":   { "energy": 1, "resin": 3, "metals": 1 },
    "electronics_assembly": { "energy": 1, "silicon": 3, "copper": 2 },
    "actuator_fabrication": { "energy": 1, "metals": 2, "copper": 1 },
    "battery_assembly":     { "energy": 5, "copper": 2, "metals": 1 },
    "worker_assembly":      { "chassis": 1, "electronics": 3, "battery": 2, "actuator": 8 },
    "gatherer_assembly":     { "chassis": 1, "electronics": 3, "battery": 2, "actuator": 8 }
  }
}
```

An engineer robot (assembled at `worker_assembly`) requires:
- 1 chassis (from `structural_molding`)
- 3 electronics (from `electronics_assembly`)
- 2 batteries (from `battery_assembly`)
- 8 actuators (from `actuator_fabrication`)

Working back through the parts BOM to raw resources, an engineer order requires:

| Resource | Qty |
|---|---|
| energy | 1×1 + 1×3 + 5×2 + 1×8 = 21 |
| resin | 3×1 = 3 |
| silicon | 3×3 = 9 |
| metals | 1×1 + 2×8 + 1×2 = 19 |
| copper | 2×3 + 1×8 + 2×2 = 18 |

### 3b. Create the sink table

Create a file `flink/01_create_sink.sql`:

```sql
CREATE TABLE hive_order_resource_requirements (
  order_id        STRING,
  robot_type      STRING,   -- 'engineer' or 'gatherer'
  resource_id     STRING,
  quantity_needed INT,
  PRIMARY KEY (order_id, resource_id) NOT ENFORCED
) WITH (
  'kafka.topic'             = 'hive-order-resource-requirements',
  'value.format'            = 'json',
  'changelog.mode'          = 'upsert',
  'scan.startup.mode'       = 'earliest-offset'
);
```

Run it:
```bash
confluent flink statement create hive-order-resource-sink \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/01_create_sink.sql)" > /dev/null
```

Confirm `COMPLETED`:
```bash
confluent flink statement describe hive-order-resource-sink -o json | grep -E '"(status|status_detail)"'
```

---

## Step 4 — Start the Order Requirements Job

Now write the continuous DML statement that joins each `order-placed` event with the hard-coded BOM resource totals and writes one row per resource per order.

Create `flink/02_run_jobs.sql`:

```sql
-- For each open order, compute the total raw resources required
-- to build the requested robot from scratch (parts + assembly combined).

-- Engineer BOM (total raw resources for one engineer robot):
--   energy=21, resin=3, silicon=9, metals=19, copper=18
-- Gatherer BOM (same as engineer — identical recipe):
--   energy=21, resin=3, silicon=9, metals=19, copper=18

INSERT INTO hive_order_resource_requirements
SELECT
  o.payload['order_id']                        AS order_id,
  CASE
    WHEN CAST(o.payload['quantity_engineer'] AS INT) = 1 THEN 'engineer'
    ELSE 'gatherer'
  END                                          AS robot_type,
  r.resource_id,
  r.quantity_needed
FROM `order-placed` AS o
CROSS JOIN (VALUES
  ('energy',  21),
  ('resin',    3),
  ('silicon',  9),
  ('metals',  19),
  ('copper',  18)
) AS r (resource_id, quantity_needed);
```

> **Note:** Both robot types have the same raw-resource totals (the parts recipes are identical). If the Simulation's BOM changes, update the VALUES table to match.

Run it:
```bash
confluent flink statement create hive-order-resource-jobs \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID \
  --sql "$(cat flink/02_run_jobs.sql)" > /dev/null
```

Confirm `RUNNING`:
```bash
confluent flink statement describe hive-order-resource-jobs -o json | grep -E '"(status|status_detail)"'
```

---

## Step 5 — Find the Bottleneck

Now join the open order's resource requirements against your live inventory to calculate the **gap**: how many units are still needed before the robot can be built.

Create `flink/03_bottleneck.sql`:

```sql
-- For the most recently placed order, show how many units of each
-- resource are still missing (gap > 0 means the order is blocked on that resource).

SELECT
  req.order_id,
  req.robot_type,
  req.resource_id,
  req.quantity_needed,
  COALESCE(inv.quantity, 0)                             AS on_hand,
  GREATEST(0, req.quantity_needed - COALESCE(inv.quantity, 0)) AS gap
FROM hive_order_resource_requirements AS req
LEFT JOIN hive_inventory_balances AS inv
  ON  inv.item_type = 'resource'
  AND inv.item_id   = req.resource_id
ORDER BY gap DESC;
```

Run it interactively in the Flink Shell:

```bash
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```

Paste the query at the `>` prompt and press Enter. You will see a live table like:

```
order_id     robot_type  resource_id  quantity_needed  on_hand  gap
-----------  ----------  -----------  ---------------  -------  ---
ORD-000042   engineer    metals       19               2        17   ← bottleneck
ORD-000042   engineer    energy       21               8        13
ORD-000042   engineer    copper       18               6        12
ORD-000042   engineer    silicon      9                0         9
ORD-000042   engineer    resin        3                3         0
```

The resource with the highest `gap` is the bottleneck. In the example above, **metals** is the limiting resource — upgrading or adding a metals gathering station would reduce fulfilment time the most.

Press `Q` to close the results, then `EXIT;` to leave the shell.

---

## Step 6 — Use the Treasury to Act

Every fulfilled order earns coins for the Treasury, displayed in the sidebar of the Level 4 dashboard. Coins can be spent on:

| Action | Cost |
|---|---|
| **Add a station** (new gathering slot at tier 1) | 1,000 coins |
| **Upgrade to tier 2** (halves the gathering interval) | 250 coins |
| **Upgrade to tier 3** (fastest interval) | 1,000 coins |

Use the bottleneck analysis from Step 5 to decide which station to invest in:
- If `metals` has the largest gap, add a metals gathering station or upgrade the existing one to tier 2.
- Tier 2 (5-minute interval) doubles throughput compared to tier 1 (10-minute interval).
- Tier 3 (3-minute interval) triples it.

Watch the bottleneck query update in real time as upgrades take effect and the resource gaps narrow.

---

## How the Order Model Works

```
sim start → _place_order(ORD-000001)
              ↓ order.placed emitted
         ... robot assembles ...
              ↓ assembly.completed emitted
         → _fulfill_order(robot_type)
              ↓ order.fulfilled emitted  (coins_received = price_in_coins)
         → _place_order(ORD-000002)      immediately
              ↓ order.placed emitted
```

Key properties:
- **Always one open order.** The next order is placed the moment the previous one is fulfilled.
- **Orders alternate.** Odd-numbered orders are for engineers; even-numbered for gatherers.
- **Treasury is authoritative.** `treasury_coins` in the sidebar is the running sum of all `coins_received` values from `order.fulfilled` events — not a client-side estimate.

---

## Useful CLI Commands

```bash
# Check order statement status
confluent flink statement describe hive-order-resource-jobs -o json | grep -E '"(status|status_detail)"'

# Tail the latest fulfilled orders
confluent kafka topic consume order-fulfilled \
  --from-beginning --print-key \
  --cluster $CLUSTER_ID --environment $ENV_ID

# Stop the order requirements job (only if you need to restart)
confluent flink statement delete hive-order-resource-jobs

# Open the Flink shell for ad-hoc queries
confluent flink shell \
  --compute-pool $POOL_ID \
  --environment $ENV_ID \
  --database $CLUSTER_ID
```

---

## Explore the Level 4 Dashboard

The Level 4 view adds three observable changes to the dashboard:

1. **Orders sidebar** — Engineer and Gatherer counts increment each time an `order.fulfilled` event arrives (not when robots are assembled — fulfilment is the trigger).
2. **Treasury sidebar** — Coins accumulate from `coins_received` in each `order.fulfilled` event. The upgrade and add-station buttons are enabled when you have enough coins.
3. **Hex tier badges** — Each station starts at the tier configured in `simulation_rules.json`. Upgrading a station changes its badge colour and, once the Simulation advances, reduces the gathering interval shown below the badge.

> The initial tier colours and upgrade costs come directly from the `simulation_config` block inside `simulation.initialized` — no hardcoded values in the frontend.

## Next Steps

- Add a real-time alert when a resource gap exceeds a threshold (e.g. `gap > 15` for more than 3 sim minutes).
- Use Tableflow to sync `hive_order_resource_requirements` to an Iceberg table for historical bottleneck analysis (Level 5).
