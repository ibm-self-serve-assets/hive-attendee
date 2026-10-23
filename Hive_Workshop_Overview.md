# HIVE: From Simulation Events to Real-Time Insight

## 1. High-level architecture

![HIVE architecture](assets/images/Hive_Architecture.png)

The instructor-hosted simulation operates a robotic bee simulation: gathering resources, manufacturing parts, and assembling robots. It publishes lifecycle events and simulation-state snapshots to Apache Kafka in Confluent Cloud.

Two consumers put those events to work. The attendee's local FastAPI backend builds an in-memory view and sends updates to the React dashboard using Server-Sent Events (SSE). Apache Flink independently processes the same topics and writes two derived streams: `hive_job_durations` (an append-only record of how long each job took) and `hive_inventory_balances` (an upsert stream holding the current stock of every resource, part, and robot). The dashboard backend reads both derived topics, and attendees validate them in Confluent Cloud: the SQL workspace for durations and the Confluent CLI Flink shell for inventory.

Simulation controls follow a separate path: the browser sends HTTP requests to the local backend, which forwards REST commands to the simulation. The dashboard observes Kafka events; it does not query an internal simulation database.

Dashed paths show the planned extensions: Tableflow synchronization of the derived topics to Apache Iceberg tables (Level 4), and a headless agentic harness running IBM Bob (Levels 5 and 6). Through Level 4, IBM Bob supports development alongside this architecture. In Level 6, Bob moves into the operating loop and manages the simulation simulation itself.

## 2. Introduction for attendees

Welcome to the Hive. Your mission is to turn a busy robotic bee simulation's stream of activity into useful, real-time insight, and then hand the simulation over to an AI agent to run.

Resources arrive, parts move through manufacturing, and robots roll off assembly lines. Every step produces events—but an event that says a job started, and another that says it finished, don't tell the whole story on their own. How long did the job take? How many units of copper are in stock right now? How can you build a live operational view from events flowing across independent services?

In this hands-on workshop, you'll connect a live simulation simulation to Apache Kafka on Confluent Cloud and watch its activity appear in your dashboard. Then you'll use Apache Flink streaming SQL to match related events and calculate production durations, and to keep a continuously updated inventory balance for every resource, part, and robot. You'll validate the results while the simulation keeps running, seeing how continuous processing differs from querying a static dataset.

You'll work with a supplied React and FastAPI dashboard, shared event contracts, and guided SQL exercises. You start in the Confluent Cloud web UI for Level 2 and move to the Confluent CLI for Level 3. IBM Bob is available as an AI development assistant to help you understand the specifications and work through the code. Later, you'll publish your streams to Apache Iceberg with Tableflow, install Bob in a headless agentic harness, and put everything together with Bob managing the simulation simulation.

By the end of the core labs (Levels 0–3), you'll be able to:

- Explain how Kafka separates event producers from independent consumers.
- Connect a live event stream to an operational dashboard.
- Use Flink interval joins to correlate started and completed jobs across gathering, manufacturing, and assembly.
- Distinguish simulated production time from elapsed wall-clock time.
- Use Flink stateful aggregations to maintain live inventory balances, and explain the difference between append and upsert changelog modes.
- Validate continuously running SQL pipelines and their derived output.

The extension levels (4–6) then take those streams into the lakehouse and under agent control. Each builds on the Kafka and Flink foundations you've established first.

## 3. Workshop summary

HIVE is a hands-on workshop for developers and engineers exploring enterprise event-driven architecture. A simulated robotic bee simulation provides a visible, practical setting for learning how Apache Kafka moves operational events, how Apache Flink transforms those events into continuous insight, and how an AI agent can operate a system built on them.

Attendees create a Confluent Cloud environment, configure a local dashboard, provision Kafka topics, connect to a simulation server, and observe live production activity. They then deploy Flink SQL interval joins that correlate job-start and job-completion events, producing an append-only stream of duration records. Next they switch to the Confluent CLI and deploy stateful aggregations that keep a live inventory balance, written as an upsert stream. The exercises connect event contracts, decoupled services, stateful stream processing, and live validation in one working example.

The workshop then extends in three planned levels. Level 4 materializes the derived topics as Apache Iceberg tables with Confluent Tableflow. Level 5 installs a headless agentic harness and IBM Bob. Level 6 brings everything together, with IBM Bob managing the simulation simulation.

| Level | Attendee activity | Learning outcome | Repository status |
|---|---|---|---|
| Level 1 — Set up and connect | Create the `hive_dev` Confluent Cloud environment, configure `spec-shared/.env`, provision the simulation topics, launch the unified dashboard, start the simulation and observe events | Understand the components and connection points; see producer/consumer decoupling in action | Setup guide, scripts and application supplied |
| Level 2 — Intro to Flink | Create a Flink compute pool and deploy interval joins in the Confluent Cloud SQL workspace | Turn separate lifecycle events into job-duration facts (`hive_job_durations`, append) | Sink, processing, and validation SQL supplied; dashboard view supplied |
| Level 3 — Hive Inventory | Install the Confluent CLI and deploy stateful aggregations | Maintain live stock levels for resources, parts, and robots (`hive_inventory_balances`, upsert) | Sink, processing, and validation SQL supplied; dashboard view supplied |
| Level 4 — Tableflow | Materialize `hive_job_durations` and `hive_inventory_balances` as Apache Iceberg tables | Extend streams into lakehouse analytics without a separate pipeline | Planned; folder created, runbook not yet written |
| Level 5 — Headless agent and IBM Bob | Install a headless agentic harness and IBM Bob | Give an AI agent a runnable, non-interactive environment | Planned |
| Level 6 — Bob runs the simulation | Connect the pieces so IBM Bob manages the simulation simulation | See an agent operate an event-driven system end to end | Planned |

### What each completed level provides

- **Level 1** — The attendee creates a `hive_dev` environment with a Kafka cluster, an API key and Stream Governance Essentials (which enables Schema Registry for Levels 2 and 3). They fill in `spec-shared/.env` and start the FastAPI backend (port 8001) and the React frontend (port 5174). The backend builds its view only from Kafka events; there is no simulation database to query. A script provisions the topics defined in `spec-shared/schemas/event_payloads.json`, and it is safe to run more than once. The dashboard's Level 1 view stays locked until every one of those topics exists. Running the simulation advances the simulation clock (1 real second = 1 simulated minute) and shows live counters and flow animations.
- **Level 2** — Three continuous interval joins pair `*.started` and `*.completed` events by `job_id` and write elapsed simulated minutes and wall-clock seconds to `hive_job_durations`. The dashboard's Level 2 view stays locked until that topic exists, then shows a segmented progress ring on each station sized to its job duration.
- **Level 3** — Three parallel aggregation jobs compute resources (gathered minus consumed at manufacturing start), parts (manufactured minus consumed at assembly start), and robots (accumulate only). Output is an upsert changelog with one current row per item. The dashboard's Level 3 view unlocks once `hive_inventory_balances` exists, adds resource, parts, and robot inventory strips, and reuses the Level 2 progress rings.

### Notes carried into the extension levels

- `hive_inventory_balances` uses an upsert changelog from the start, because the changelog mode cannot be changed after a Tableflow materialization. This is deliberate preparation for Level 4.
- `hive_job_durations` and `hive_inventory_balances` are intentionally separate (append versus upsert, different consumers, different dashboard levels) and should not be merged.

## Review notes and source references

Reviewed against the working tree on top of repository commit `9bc9e7787fdff29ea811f9b55382b5d6b08f9ed3` on October 20, 2026 (Pacific time). Level 3 and the renamed Level 2 folder were still uncommitted at the time of review, so links below are repo-relative rather than pinned to a commit. This review examined the Level 1–3 READMEs, the dashboard level registry and the working notes; it did not run a live cloud deployment.

The unified frontend registers Levels 1, 2 and 3, with Level 1 gated on the event topics and Levels 2 and 3 each gated on their Flink output topic existing. Working notes still list automated level-validation gates as open work. `level-4-tableflow/` exists but is empty, and no folders or documents exist yet for Levels 5 and 6, so the descriptions of those levels above reflect the planned direction and not implemented code. Some older guides and the Level 2 README's topic and resource examples (pollen, nectar, wax, frames, honeycombs) do not match the current simulation, which uses copper, energy, metals, resin and silicon, with chassis, electronics, actuator and battery parts. The copy above follows current source behavior where these disagree. The architecture diagram image has not yet been updated to show Levels 4–6.

Primary sources:

- [Level 1 setup](level-1-environment-setup/README.md)
- [Run your simulation (Level 1, Step 8)](level-1-environment-setup/README.md#step-8-run-your-simulation)
- [Level 2 Flink exercises](level-2-intro-to-flink/README.md)
- [Level 2 processing SQL](level-2-intro-to-flink/flink/02_run_jobs.sql)
- [Level 3 inventory exercises](level-3-hive-inventory/README.md)
- [Level 3 processing SQL](level-3-hive-inventory/flink/02_run_jobs.sql)
- [Dashboard backend](level-1-environment-setup/backend/app.py)
- [Current level registry](level-1-environment-setup/frontend/src/levels/registry.ts)
- [Working notes and roadmap](next_steps.md)
