# Shared Simulation API — contract 1.0

This contract describes the shared contract around API and schema between both specifications 1 & 2. It defines the boundary between the hosted Simulation Server and the attendee's local application. Implement /v1 routes and publish matching OpenAPI before integrating the two packages. The server owns this contract; change both copies together.

## Identity and onboarding

An organizer prepares an attendee record and an opaque, high-entropy workshop access token. Load its hash from organizer-provided deployment configuration into memory. The record contains attendee_id, permitted cluster connection profile, precreated topic prefix, consumer-group prefix, expiry and a one-simulation quota. The token is delivered privately and stored only by the attendee's local backend. This is the initial workshop authentication scheme; organizational OIDC can replace it later.

Authenticate all attendee endpoints with Authorization: Bearer <workshop_access_token>. Resolve owner from that token, never from an attendee_id in a request body. An unrecognized token is 401; a Simulation belonging to someone else is 404. Listing returns only the caller's simulation. An API key is Kafka authentication, not proof of workshop identity or ownership.

The organizer precreates ten topics (nine activity topics and one compacted state topic) and scopes permissions for each attendee. Endpoint/profile and prefix come from the attendee's in-memory enrollment record; attendees cannot supply arbitrary network destinations or redirect another Simulation to their topics. For a workshop using attendee-owned clusters, an organizer first approves/adds that cluster profile and exact namespace. This is a preparation dependency, not automatic arbitrary-cluster onboarding.

## Provision a simulation

POST /v1/simulations, with Idempotency-Key header (UUID):

```json
{
  "producer_credentials": {
    "api_key": "<Kafka API key>",
    "api_secret": "<Kafka API secret>"
  }
}
```

The bootstrap endpoint, namespace and TLS profile are resolved from the authorized connection profile. If a single key pair is used for both producer and consumer during the pilot, the attendee also saves it in the local backend. Prefer separate producer-write and consumer-read credentials where preparation permits. Never send consumer-only credentials to the Simulation server.

Creation reserves the caller's quota, simulation_id and initial empty run/generation under an in-process registration lock, keeps credentials only in memory and creates a provisioning operation. Return 202 containing simulation_id, operation_id and status_url. Do not start Simulation time yet. A background task verifies broker connectivity, existing topics and actual publish permission by sending an empty paused simulation.state probe with this newly assigned Simulation identity; it must not create resources or robots. Verify write permission on the nine activity topics using an isolated connection.test event defined in the event contract. All probes require broker acknowledgment. Failure produces provisioning_failed with a sanitized diagnostic. Do not leave a clock running behind a failed registration.

GET /v1/operations/{operation_id} returns only the owner's operation status: pending, succeeded or failed, plus error_code/message (no secrets). On success the Simulation is paused at zero and GET Simulation returns simulation_id, run_id, run_generation, topic names, consumer_group_prefix, status, expires_at. It never returns the API secret. The local application starts its consumer and waits for a real snapshot before showing observed Simulation state.

A replay of creation with the same idempotency key and identical request returns the same simulation/operation. Keep a keyed request digest in memory, not a plaintext credential body, for conflict detection. Same key/different request returns 409. A second creation key when the owner already has a Simulation returns 409 with the existing simulation_id. Provisioning retries use the existing Simulation via connection update, not another quota slot.

## Lifecycle semantics

| Current state | Start | Pause | Stop | Restart at zero |
| --- | --- | --- | --- | --- |
| paused (including newly created) | running, same run | no-op | stopped, same run | new run, time zero |
| running | no-op | paused, same run | stopped, same run | new run, time zero |
| stopped | 409: use restart | 409 | no-op | new run, time zero |
| provisioning / provisioning_failed | 409 | 409 | 409 | 409 |
| expired | 410 | 410 | 410 | 410 |

Pause is resumable. Stop freezes current state and disables further progress for that run; it preserves its history and unfinished job records for inspection but Start cannot resume it. Restart at zero abandons prior unfinished work, increments generation, creates a new run_id, clears current inventory and clock, and resets robot counts. No topic deletion occurs.

Restart body is {"start": true} by default; it queues an empty time-zero snapshot before allowing the first delivery cycle to start. Set start=false for a new paused run. Include this choice in the UI confirmation. This proposal distinguishes Stop from Pause and gives Restart its ordinary meaning of starting again; the controls spec implements it consistently.

## Endpoints

| Endpoint | Behavior |
| --- | --- |
| GET /v1/simulations | Caller-owned Simulation metadata only |
| GET /v1/simulations/{id} | Lifecycle, run/generation, topic names, event-stream health, expiry; no inventory or job-progress view |
| POST /v1/simulations/{id}/start | Resume/create progress in existing paused run |
| POST /v1/simulations/{id}/pause | Freeze logical time |
| POST /v1/simulations/{id}/stop | End progress for current run |
| POST /v1/simulations/{id}/restart | New empty generation; body start boolean, default true |
| POST /v1/simulations/{id}/speed | Body speed: 1 or 5 |
| PUT /v1/simulations/{id}/connection | Rotate producer key/secret for the same allowed profile; validate before activating replacement |
| GET /v1/operations/{id} | Owner-scoped asynchronous operation outcome |

All mutating requests require Idempotency-Key. For lifecycle commands also send expected_generation (integer) in the JSON body; reject a stale expected generation with 409, except an exact idempotent replay returns its earlier result. Speed body includes both speed and expected_generation. This protects against a delayed Stop applying to a newly restarted run.

After applying a command under the Simulation lock return 200 with command_id, accepted=true, resulting lifecycle_status, run_id, run_generation and applied_at. These are command receipts, not observed Simulation inventory. The UI labels them as server status until Kafka observation catches up. A command ID is included in subsequent snapshots. A retried command cannot reset twice.

Status codes: 400 malformed request; 401 invalid token; 404 not owned/not found; 409 state/idempotency/generation conflict; 410 expired simulation; 422 invalid speed/fields; 429 configured rate/capacity limit; 503 server temporarily unavailable. A Kafka outage alone does not reject lifecycle controls on an already provisioned simulation.

Connection rotation returns 202 with operation_id. Continue the prior credential until the replacement validates; do not discard the pending memory queue on failure. Credentials cannot change topic namespace or ownership through this endpoint.

## Memory-only lifetime

Use a single server process. Keep simulations, owner-to-simulation mappings, jobs, credentials, command-id caches, operation results and pending events in memory. Protect registration with a process lock and each Simulation with its own lock. Never hold those locks across Kafka/network calls.

Idempotency, one-simulation-per-owner and retry guarantees last only for this process lifetime. Pause/Stop and Restart at zero are application commands; they do not restart the server. A process crash, deployment or platform replacement loses all simulations, submitted credentials, pending events and idempotency history. Nothing is rebuilt from Kafka.

On each server boot generate a new server_epoch UUID. Include it in all simulation/operation responses and every event. GET /v1/server returns the current epoch and contract version to authenticated attendees. Requests for simulations from a previous boot return 404. Every mutating request includes X-Server-Epoch; a mismatch returns 409 server_restarted without performing the action. This prevents automatic replay of a stale registration/command against a new process.

The local app detects epoch change or a missing owned simulation, clears its active-simulation association, retains any displayed old values only as stale historical observations, and asks the attendee to register again. A new registration gets a new simulation_id and empty paused run. An old Restart request must not recreate a lost Simulation automatically. Organizer enrollment/token configuration survives because it is deployment configuration, not Simulation state.

Simulation queries, clients and event queues remain owner-scoped in memory. Never log credential bodies or Authorization headers. Kafka credentials remain plaintext only in process memory while needed; no credential database or encryption-key service is required in this prototype.

Defaults remain one Simulation per enrolled owner, six-hour TTL and organizer-set limits. Expiry freezes the Simulation and releases scheduler/producer resources. Keep a lightweight expired marker until process exit to return 410 and prevent reuse of the quota; discard credentials and pending data after a bounded best-effort final publish. An organizer/attendee still revokes Confluent keys externally.

A Kafka outage alone does not pause a running simulation: queue unsent events in a bounded per-simulation in-memory buffer and retry. Set both byte and record limits. If the next transition would exceed a limit, do not apply it; flag buffer_full and halt that Simulation until it drains and the attendee explicitly resumes. Stop/Pause remain available; reserve capacity for control/status records. Do not claim delivery of records lost on a server crash. Confluent still retains records already acknowledged according to topic retention.


