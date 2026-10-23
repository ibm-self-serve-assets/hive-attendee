# Next steps: dashboard UI and attendee levels

Working notes for Anthony and Bob. Not for attendees or instructors.

Scope: everything in this repo (`hive`). That is the unified dashboard in `level-1-environment-setup/` (FastAPI backend, React/TypeScript/Vite frontend), the level folders, `spec-shared/`, and `Hive_Workshop_Overview.md`.

The simulation server lives in the `hive-simulation` repo. Its work is in [`next_steps_simulation.md`](next_steps_simulation.md). Decisions that affect both sides are listed in that file under "Shared decisions" and are not repeated here, only referenced.

## Blocked on the simulation side

These need an answer from [`next_steps_simulation.md`](next_steps_simulation.md) first:

- The **order model** and the **event names** (`order.placed` / `order.fulfilled`). The Level 4 Orders panel and Treasury both depend on them.
- How `spec-shared/` is **shared between the repos**. This repo and `hive-simulation` each hold a copy; the two are identical today. Any edit to `event_payloads.json` or `topics.py` has to land in both until this is decided.

## State of the repo

- Working tree is clean on `main`. The old notes marked the Level 4 screen as "uncommitted"; it is committed (`levels/level4/` exists).
- Levels 1 to 3 are done. Level 4 is partly built (see below). `level-4-gamify/` and `level-5-tableflow/` are empty folders.
- `backup_ui/` no longer exists on disk. The old notes still list it, so references to it can go.

## 1. Level 4 screen: Orders and Treasury

On `levels/level4/Level4Screen.tsx`, replace the **Robot inventory** panel above **Robot assembly** with **Orders** and **Treasury**.

- [ ] Move the Orders and Treasury sections out of the left sidebar (`components/Sidebar.tsx`, the "Level 4 Orders & Treasury" block) into that slot, then delete them from the sidebar.
- [ ] Delete the Robot-inventory code from Level 4: the panel, the `ROBOTS` inventory rendering, and the `useLevel4` coin lookup in the sidebar.
- [ ] Drive Orders and Treasury from the new order events, not from `state.inventory.robot`. Coins earned are the sum of `coins` in the order-fulfilled events. Spending stays in `Level4Context.tsx` (`coins = earned - spent`). Remove `earnedCoins`, which multiplies robot counts by `ROBOT_PRICES`.
- [ ] Add the new event types to the dashboard backend (`store.py`) and to `types.ts` as **optional** fields, so Levels 1 to 3 are unaffected.
- [ ] Do not touch Level 3's Robot inventory (`levels/level3/Level3Screen.tsx`). A shipped level stays frozen, and it reads `hive_inventory_balances`.
- [ ] Decide whether purchases should stay client-only. They are tracked in `Level4Context.tsx`, so a page refresh loses them and the server does not know about them. Keep this deliberate, or persist them (for example in `localStorage`).
- [ ] Keep gating Level 4 on `hive_inventory_balances` like Level 3, or add a gate for the order topic once it exists.

## 2. Topics and events in the attendee repo

- [ ] Confirm the `*.acquired` events (`manufacturing.resources.acquired`, `assembly.parts.acquired`) are provisioned and deleted. `provision_topics.py` builds its topic list from `spec-shared/schemas/event_payloads.json`, so they should be covered with no script change. Verify with `python3 provision_topics.py --dry-run` and a look at `delete_topics.py`. `store.py` already accepts them with no state change.
- [ ] Order topics: the same check applies once the events are added to `event_payloads.json`.
- [ ] Document the new events in the Level 1 docs (`README.md`, topic list).
- [ ] Confirm `debug_mode_instructor_only` is `null` in any workshop run. `store.py` reads it to bypass Flink inventory; keep that path out of attendee docs, since the field is instructor-only.

## 3. Level numbering (needs a decision)

The docs and the dashboard disagree:

- `Hive_Workshop_Overview.md` plans **Level 4 = Tableflow**, Level 5 = headless agent and IBM Bob, Level 6 = Bob runs the simulation.
- The dashboard's **Level 4** is the gamified orders / treasury screen. The folders are `level-4-gamify/` and `level-5-tableflow/`.

- [ ] Pick one numbering and update together: the overview, the folder names, the label in `levels/registry.ts`, and the Tableflow roadmap item.
- [ ] Fill in or remove the two empty folders once the numbering is set.

## 4. Level documentation

- [ ] Write the Level 4 (gamify) README for attendees. It must not reveal the simulation's hidden counters or internals.
- [ ] Update `level-1-environment-setup/README.md` for the new topics and any change to how the dashboard finds the simulation server.
- [ ] Fix the leftover rename artifact "simulation simulation" in `Hive_Workshop_Overview.md` (it appears in several sentences, for example "manages the simulation simulation itself"; likely a global rename of "factory" to "simulation").
- [ ] Remove stale references to `simulation-instructor-only/` and `backup_ui/` from docs once the repo move is settled. The only place the old path still appears in this repo is `next_steps.md`.

## 5. Tableflow runbook (Level 4 or 5, see numbering)

- [ ] Write the Iceberg sync and data-lakehouse instructions for both `hive_job_durations` (append) and `hive_inventory_balances` (upsert). Keep the two topics separate; they have different changelog modes, consumers and dashboard levels.

## 6. Later levels (from the overview)

- [ ] Headless agentic harness with IBM Bob (planned Level 5).
- [ ] Bob managing the simulation (planned Level 6). This needs the simulation's REST controls documented for an agent, which is a simulation-repo task.

## 7. Connecting to the deployed simulation

- [ ] Once the server is on Cloud Run, check how the dashboard backend is pointed at it (URL and auth) and update the Level 1 setup steps.
- [ ] Check the dashboard backend's long-lived connections against the Cloud Run request timeout. A run lasts 2.8 to 5.6 real hours.
- [ ] Rehearse with 3 to 5 real attendee clusters before the class. The load test in the simulation repo uses a mock Kafka and does not cover real Confluent behaviour.

## 8. Cleanup

- [ ] Delete `SegmentRingLegacy` in `level-1-environment-setup/frontend/src/components/StationStats.tsx` once the new `DotSpinner` is confirmed.

## Architecture rules (keep)

Each level has its own screen, and a shipped level is frozen. Adding Level N must never break Levels 1 to N-1.

- `levels/types.ts`: `LevelScreenProps` and `LevelDefinition` (`id`, `label`, `Screen`, optional `isUnlocked`, `isReady`, `Requirements`).
- `levels/registry.ts`: the `LEVELS` list. The dropdown and `DEFAULT_LEVEL_ID` come from it.
- Only identical, presentation-only pieces are shared (`FlowDots.tsx`, `EventPanel.tsx`, `Sidebar.tsx`). If a shared piece needs a level-specific change, copy it into that level's folder instead of adding flags.

To add a level:

1. Copy the previous level folder (for example `levels/level3/` to `levels/level4/`) and rename the screen.
2. Change only the new copy.
3. Append one entry to `LEVELS` in `levels/registry.ts`.
4. If the level needs data the dashboard does not provide yet, add it to the backend store and `types.ts` as optional fields.
5. Update the matching level docs.

## Working agreements for this repo

- **Keep the levels current.** When the simulation, the attendee backend/frontend, or the Flink SQL changes, update the matching level `.md` files in the same change.
- **Audience.** Levels 1 to 4 are written for attendees and do not reveal hidden simulation state.
- **Hidden state stays out.** Do not add fields such as `staged_inputs` to the schema, the models, or the dashboard, and do not recompute carts in the dashboard backend.
- **One source of truth.** Point to `simulation_rules.json` and `event_payloads.json` instead of copying values into docs.
- **Attendee SQL** runs in the Confluent Flink workspace, one statement per run. Prefer a small number of files that each run once.
- **Two Flink output topics:** `hive_job_durations` (append) and `hive_inventory_balances` (upsert). Do not merge them.

## Done (for reference)

- Unified dashboard with a Levels dropdown, URL hash routing (`#level-1` to `#level-4`), and a screen per level.
- Level 2: job durations, blocked state, input chips; `isUnlocked` gate on `hive_job_durations`; `isReady` gate ("New simulation run required" / "Waiting for Flink…"); FlowDots; Flink SQL verified in Confluent Cloud.
- Level 3: ledger and balances; gate on `hive_inventory_balances`; Flink SQL (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`) and CLI-first README.
- Event panels start collapsed in Levels 1 and 2.
- Schema Registry 5-byte magic prefix stripped in both Flink topic consumers.
- Level 4 screen started: per-station add/upgrade controls and treasury sidebar (to be reworked in section 1).
