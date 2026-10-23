#!/usr/bin/env bash
# provision_topics.sh
# ───────────────────
# Creates (or verifies) the Confluent Cloud topics for this attendee.
#
# Configuration is read from spec-shared/.env (the shared env file at the repo root).
# Fill in the four values there before running:
#
#   CONFLUENT_REST_ENDPOINT=https://pkc-xxxxx.us-west-2.aws.confluent.cloud
#   CONFLUENT_CLUSTER_ID=lkc-xxxxxx
#   CONFLUENT_API_KEY=...
#   CONFLUENT_API_SECRET=...
#
# Usage:
#   ./provision_topics.sh            # create topics
#   ./provision_topics.sh --dry-run  # preview without making API calls
#
# This script:
#   1. Creates (or reuses) a Python venv at .venv/
#   2. Installs requirements.txt into the venv (idempotent, cached by pip)
#   3. Runs provision_topics.py inside that venv using certifi for SSL
#
# Run from the level-1-environment-setup/scripts/ directory:
#   cd level-1-environment-setup/scripts
#   chmod +x provision_topics.sh
#   ./provision_topics.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
SCRIPT="$SCRIPT_DIR/provision_topics.py"

# ── 1. Create venv (recreate if the interpreter shebang is stale) ────────────
_venv_ok=false
if [ -f "$VENV_DIR/bin/python" ]; then
  _shebang="$(head -1 "$VENV_DIR/bin/pip" 2>/dev/null || true)"
  if [[ "$_shebang" == *"$VENV_DIR"* ]]; then
    _venv_ok=true
  else
    echo "Venv interpreter path is stale (folder was renamed). Recreating .venv/ ..."
    rm -rf "$VENV_DIR"
  fi
fi
if [ "$_venv_ok" = false ]; then
  echo "Creating virtual environment at .venv/ ..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# ── 2. Install / sync requirements ───────────────────────────────────────────
echo "Installing requirements (certifi, confluent-kafka, python-dotenv, ...) ..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$REQUIREMENTS"

# ── 3. Confirm env source ────────────────────────────────────────────────────
SHARED_ENV="$SCRIPT_DIR/../../spec-shared/.env"
if [ -f "$SHARED_ENV" ]; then
  echo "Using env : $SHARED_ENV"
else
  echo "Warning   : spec-shared/.env not found — falling back to local .env (if any)"
fi
echo ""

# ── 4. Run the provisioner ───────────────────────────────────────────────────
"$PYTHON" "$SCRIPT" "$@"
