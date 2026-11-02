# Welcome to The Hive

<a href="assets/welcome_to_the_hive.png"><img src="assets/welcome_to_the_hive.png"/></a>

**The Hive** is a hands-on workshop where you monitor a robotic bee manufacturing Simulation.  Your bees gather resources, manufacture parts then assemble them into functional bees of different types: Gatherers, Engineers and Builders. Gatherer bees obtain the required Copper, Energy, Metals, Resin and Silicon required to maufacture the parts required to assemble your bees: Actuator, Battery, Chassis and Electronics.  You will ultimately assume the role as Queen of your robotic bee colony, assigning your bees to build new workstations and upgrade existing ones.  

To be efficient though, you must first obtain detailed insights into your production workflows including rates of resource gathering, time to manufacture parts, bottlenecks in available resources and efficiencies in assembling new robots from limited parts.  To gain insights into your robotic manufacturing Simulation, you'll connect real-time events into Apache Kafka on Confluent Cloud to generate real-time insight from your event stream. As your bees gather raw materials, manufactures parts and assembles robots, they are publishing detailed metadata at every step as a a live stream of events. Your job is to turn that stream of raw activity into something useful.

The Hive Workshop is structured as multiple Levels that you progress through while deploying Apache Flink SQL to correlate workstation start and completion events into production durations, maintain live inventory balances with stateful aggregations and validate continuously running pipelines as the Simulation keeps moving. In later levels, you'll store those streams in Apache Iceberg tables in Google BigQuery using Confluent Tableflow then hand the Simulation over to IBM Bob and Google Gemini to manage autonomously.

## Workshop Levels
Head to **[Level 1 — Environment Setup](level-1-environment-setup/README.md)** to configure your Confluent Cloud environment, provision your Kafka topics, and launch the Hive Dashboard.

| Level | Title | Focus |
|---|---|---|
| 1 | Environment Setup | Connect to Confluent Cloud, provision topics, launch the Hive Dashboard |
| 2 | Intro to Apache Flink | Interval joins → job duration stream (`hive_job_durations`) |
| 3 | Hive Inventory | Stateful aggregations → live inventory balances (`hive_inventory_balances`) |
| 4 | Tableflow *(planned)* | Materialize streams as Apache Iceberg tables |
| 5 | Headless Agent *(planned)* | Install IBM Bob in a headless agentic harness |
| 6 | Bob Runs the Hive *(planned)* | IBM Bob manages the Simulation end-to-end |

## Architecture

<a href="assets/hive_architecture.png"><img src="assets/hive_architecture.png"/></a>

The HIVE platform is built around an event-driven architecture connecting a hosted Simulation engine, cloud-native streaming data pipelines, and a local attendee dashboard:

1. **Simulation Server (Hosted Engine)**: Simulates the robotics manufacturing floor (gathering raw materials, fabricating parts, and assembling robots). It receives attendee lifecycle commands (Start, Pause, Stop, Restart) over HTTP REST and writes raw event logs directly to Confluent Cloud.
2. **Confluent Cloud (Event Streaming Backbone)**: Provides managed Apache Kafka topics for each event type (e.g., `gathering-started`, `manufacturing-completed`, `simulation-state`), backed by Schema Registry for event contract governance.
3. **Apache Flink SQL (Stream Processing)**: Continuously joins, enriches, and aggregates raw event streams in real time (calculating job durations and tracking live inventory balances), outputting enriched streams back to Kafka and downstream storage.
4. **Attendee Dashboard (FastAPI Backend + React UI)**: Runs locally on your machine. The Python backend consumes events directly from your Confluent Cloud cluster and streams live state updates to the React frontend over Server-Sent Events (SSE).