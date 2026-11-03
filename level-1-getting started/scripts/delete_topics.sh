#!/usr/bin/env bash
# delete_topics.sh
# ────────────────
# Discovers all Confluent Cloud topics in your cluster and deletes them.
#
# Configuration is read from spec-shared/.env (the shared env file at the repo root).
# Fill in the five values there before running:
#
#   ATTENDEE_ID=...
#   CONFLUENT_REST_ENDPOINT=https://pkc-xxxxx.us-west-2.aws.confluent.cloud
#   CONFLUENT_CLUSTER_ID=lkc-xxxxxx
#   CONFLUENT_API_KEY=...
#   CONFLUENT_API_SECRET=...
#
# Usage:
#   ./delete_topics.sh            # discover, confirm, then delete
#   ./delete_topics.sh --dry-run  # list topics without deleting
#   ./delete_topics.sh --yes      # skip confirmation prompt

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

.venv/bin/python delete_topics.py "$@" || true

echo ""
read -rp "Press Enter to close..." || true
