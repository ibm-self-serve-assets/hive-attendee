# Next steps: dashboard UI and attendee levels

Working notes for Anthony and Bob. Not for attendees or instructors.

Scope: everything in this repo (`hive-attendee`, remote `ibm-self-serve-assets/hive-attendee`). That is the unified dashboard in `level-1-environment-setup/` (FastAPI backend, React/TypeScript/Vite frontend), the level folders, `spec-shared/`, and `Hive_Workshop_Overview.md`.

Layout: both repos sit side by side in one working directory, `hive-workshop/`:

```
hive-workshop/
  hive-attendee/     this repo: dashboard, level docs, Flink SQL   -> next_steps.md
  hive-simulation/   the simulation server                         -> hive-simulation/next_steps.md
```

The simulation server's plan is in [`../hive-simulation/next_steps.md`](../hive-simulation/next_steps.md). Decisions that affect both repos are listed there under "v2: shared decisions" and are not repeated here, only referenced.

## Release plan

| Release | What it is | Rule |
|---|---|---|
| **v1** | The current code in both repos, deployed as it stands. | **Frozen.** No feature work lands before v1 is deployed and tagged. Only fixes needed to ship (section "Before v1 ships"). |
| **v2** | Everything else in this file: the Orders/Treasury rework, order events, Tableflow, later levels. | Starts after v1 is deployed. Work on a separate branch, so v1 can still take a hotfix. |

Suggested tagging (you run git): tag `v1.0.0` in both repos at the commit that is deployed, then branch `v2` from it. Record which simulation server image the v1 dashboard was tested against, since the two are deployed separately.

## v1: state

- Working tree is clean on `main` (one commit, "Initial commit").
- Levels 1 to 3 are done. `levels/registry.ts` registers four levels, so **Level 4 ships in v1 in its current form**: per-station add/upgrade controls and the treasury sidebar. It is driven from `state.inventory.robot` (coins earned = robot counts times `ROBOT_PRICES`), and purchases are held client-side in `Level4Context.tsx`. The server has no orders in v1, so nothing replaces that yet. The rework is v2 section 1.
- `level-4-gamify/` and `level-5-tableflow/` are empty folders. They do not affect v1.
- `backup_ui/` no longer exists on disk, so references to it can go.

## Before v1 ships

Verification and configuration only. No new features.

- [ ] **Decide whether Level 4 ships.** It is registered and unlocked by `hive_inventory_balances_ready`, but it is partly built and has no README (`level-4-gamify/` is empty). Either ship it as is and tell attendees it is a preview, or hide it for v1 by removing its entry from `LEVELS` in `levels/registry.ts`. That is a one-line change and a v1 call. Default if undecided: ship it unchanged.
- [ ] **Point the dashboard backend at the deployed simulation server** (URL and auth) and update the Level 1 setup steps in `level-1-environment-setup/README.md`.
- [ ] **Check the dashboard backend's long-lived connections** against the Cloud Run request timeout. A run lasts 2.8 to 5.6 real hours.
- [ ] **Rehearse with 3 to 5 real attendee clusters** before the class. The v2 load test uses a mock Kafka and does not cover real Confluent behaviour.
- [ ] Confirm `debug_mode_instructor_only` is `null` in any workshop run. `store.py` reads it to bypass Flink inventory; keep that path out of attendee docs, since the field is instructor-only.
- [ ] Confirm the `*.acquired` events (`manufacturing.resources.acquired`, `assembly.parts.acquired`) are provisioned and deleted. `provision_topics.py` builds its topic list from `spec-shared/schemas/event_payloads.json`, so they should be covered with no script change. Verify with `python3 provision_topics.py --dry-run` and a look at `delete_topics.py`. `store.py` already accepts them with no state change.
- [ ] Document the `*.acquired` events in the Level 1 docs (`README.md`, topic list) if they are missing.
- [ ] Fix the leftover rename artifact "simulation simulation" in `Hive_Workshop_Overview.md` (it appears in several sentences, for example "manages the simulation simulation itself"; likely a global rename of "factory" to "simulation"). This is a text fix, safe for v1.
- [ ] Repo hygiene: untrack `.DS_Store` if tracked. `.gitignore` already lists it.
- [ ] Commit, push, tag `v1.0.0`, branch `v2`.

## v2: blocked on the simulation side

These need an answer from [`../hive-simulation/next_steps.md`](../hive-simulation/next_steps.md) first:

- The **order model**, the **event names** (`order.placed` / `order.fulfilled`) and the **contract version**. The Level 4 Orders panel and Treasury both depend on them.
- How `spec-shared/` is **shared between the repos**. This repo and `hive-simulation` each hold a copy; the two are identical today apart from a stray `.DS_Store` in the simulation copy. Any edit to `event_payloads.json` or `topics.py` has to land in both until this is decided.

## v2 work

### 1. Level 4 screen: Orders and Treasury

On `levels/level4/Level4Screen.tsx`, replace the **Robot inventory** panel above **Robot assembly** with **Orders** and **Treasury**.

- [ ] Move the Orders and Treasury sections out of the left sidebar (`components/Sidebar.tsx`, the "Level 4 Orders & Treasury" block) into that slot, then delete them from the sidebar.
- [ ] Delete the Robot-inventory code from Level 4: the panel, the `ROBOTS` inventory rendering, and the `useLevel4` coin lookup in the sidebar.
- [ ] Drive Orders and Treasury from the new order events, not from `state.inventory.robot`. Coins earned are the sum of `coins` in the order-fulfilled events. Spending stays in `Level4Context.tsx` (`coins = earned - spent`). Remove `earnedCoins`, which multiplies robot counts by `ROBOT_PRICES`.
- [ ] Add the new event types to the dashboard backend (`store.py`) and to `types.ts` as **optional** fields, so Levels 1 to 3 are unaffected.
- [ ] Do not touch Level 3's Robot inventory (`levels/level3/Level3Screen.tsx`). A shipped level stays frozen, and it reads `hive_inventory_balances`.
- [ ] Decide whether purchases should stay client-only. They are tracked in `Level4Context.tsx`, so a page refresh loses them and the server does not know about them. Keep this deliberate, or persist them (for example in `localStorage`).
- [ ] Keep gating Level 4 on `hive_inventory_balances` like Level 3, or add a gate for the order topic once it exists.

### 2. Topics and events

- [ ] Order topics: provisioning and deletion pick them up from `event_payloads.json` once the events are added. Re-run `provision_topics.py --dry-run` and check `delete_topics.py`.
- [ ] Document the order events in the Level 1 docs (`README.md`, topic list).

### 3. Level numbering (needs a decision)

The docs and the dashboard disagree:

- `Hive_Workshop_Overview.md` plans **Level 4 = Tableflow**, Level 5 = headless agent and IBM Bob, Level 6 = Bob runs the simulation.
- The dashboard's **Level 4** is the gamified orders / treasury screen. The folders are `level-4-gamify/` and `level-5-tableflow/`.

- [ ] Pick one numbering and update together: the overview, the folder names, the label in `levels/registry.ts`, and the Tableflow roadmap item.
- [ ] Fill in or remove the two empty folders once the numbering is set.

### 4. Level documentation

- [ ] Write the Level 4 (gamify) README for attendees. It must not reveal the simulation's hidden counters or internals.
- [ ] Update `level-1-environment-setup/README.md` for the order topics and any change to how the dashboard finds the simulation server.
- [ ] Remove stale references to `simulation-instructor-only/` and `backup_ui/` from docs once the layout is settled.

### 5. Tableflow runbook (Level 4 or 5, see numbering)

- [ ] Write the Iceberg sync and data-lakehouse instructions for both `hive_job_durations` (append) and `hive_inventory_balances` (upsert). Keep the two topics separate; they have different changelog modes, consumers and dashboard levels.

### 6. Later levels (from the overview)

- [ ] Headless agentic harness with IBM Bob (planned Level 5).
- [ ] Bob managing the simulation (planned Level 6). This needs the simulation's REST controls documented for an agent, which is a simulation-repo task.

### 7. Cleanup

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

- v1 is frozen once tagged. Fixes to a deployed v1 go on a hotfix branch, not on `v2`.
- **Keep the levels current.** When the simulation, the attendee backend/frontend, or the Flink SQL changes, update the matching level `.md` files in the same change.
- **Audience.** Levels 1 to 4 are written for attendees and do not reveal hidden simulation state.
- **Hidden state stays out.** Do not add fields such as `staged_inputs` to the schema, the models, or the dashboard, and do not recompute carts in the dashboard backend.
- **One source of truth.** Point to `simulation_rules.json` and `event_payloads.json` instead of copying values into docs.
- **Attendee SQL** runs in the Confluent Flink workspace, one statement per run. Prefer a small number of files that each run once.
- **Two Flink output topics:** `hive_job_durations` (append) and `hive_inventory_balances` (upsert). Do not merge them.
- Until `spec-shared/` is resolved, change it in both repos in the same step and diff the two copies.

## Done (for reference)

- Unified dashboard with a Levels dropdown, URL hash routing (`#level-1` to `#level-4`), and a screen per level.
- Level 2: job durations, blocked state, input chips; `isUnlocked` gate on `hive_job_durations`; `isReady` gate ("New simulation run required" / "Waiting for Flink…"); FlowDots; Flink SQL verified in Confluent Cloud.
- Level 3: ledger and balances; gate on `hive_inventory_balances`; Flink SQL (`01_create_sink.sql`, `02_run_jobs.sql`, `03_validate.sql`) and CLI-first README.
- Event panels start collapsed in Levels 1 and 2.
- Schema Registry 5-byte magic prefix stripped in both Flink topic consumers.
- Level 4 screen started: per-station add/upgrade controls and treasury sidebar (ships in v1 as is; reworked in v2 section 1).
