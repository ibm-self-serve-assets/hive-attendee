#!/usr/bin/env bash
# delete_topics_and_schemas.sh
# ────────────────────────────
# Deletes everything Level 1 created in your Confluent Cloud, so you can start again:
#   - every topic in your Kafka cluster, and
#   - the Schema Registry subjects for those topics and for the Hive event topics.
# They go together: records in a topic point at schema ids, and a schema left behind
# meets a new registration with stale versions.
#
# Configuration is read from spec-shared/.env (the shared env file at the repo root).
# Fill in these values there before running:
#
#   ATTENDEE_ID=...
#   CONFLUENT_REST_ENDPOINT=https://pkc-xxxxx.us-west-2.aws.confluent.cloud
#   CONFLUENT_CLUSTER_ID=lkc-xxxxxx
#   KAFKA_CLUSTER_API_KEY=...
#   KAFKA_CLUSTER_API_SECRET=...
#   SCHEMA_REGISTRY_URL=https://psrc-xxxxx.us-west-2.aws.confluent.cloud
#   SCHEMA_REGISTRY_API_KEY=...
#   SCHEMA_REGISTRY_API_SECRET=...
#   SIMULATION_SERVER_URL, WORKSHOP_ACCESS_TOKEN   (used to find subjects of topics already deleted)
#
# Usage:
#   ./delete_topics_and_schemas.sh            # discover, confirm, then delete
#   ./delete_topics_and_schemas.sh --dry-run  # list topics and subjects without deleting
#   ./delete_topics_and_schemas.sh --yes      # skip confirmation prompt
#
# Afterwards run ./provision_topics.sh, then ./register_schemas.sh, to recreate them.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

SHARED_ENV="$SCRIPT_DIR/../../spec-shared/.env"
if [ -f "$SHARED_ENV" ]; then
  echo "Using env : $SHARED_ENV"
else
  echo "Warning   : spec-shared/.env not found — falling back to local .env (if any)"
fi
echo ""

.venv/bin/python delete_topics_and_schemas.py "$@" || true

echo ""
read -rp "Press Enter to close..." || true
