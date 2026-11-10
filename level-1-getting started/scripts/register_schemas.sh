#!/usr/bin/env bash
# register_schemas.sh
# ───────────────────
# Registers the event schemas (one subject per topic) in your Confluent Cloud Schema Registry.
# Run it after provision_topics.sh.
#
# Configuration is read from spec-shared/.env (the shared env file at the repo root).
# Fill in these values there before running:
#
#   SIMULATION_SERVER_URL=...      WORKSHOP_ACCESS_TOKEN=...      ATTENDEE_ID=...
#   SCHEMA_REGISTRY_URL=https://psrc-xxxxx.us-west-2.aws.confluent.cloud
#   SCHEMA_REGISTRY_API_KEY=...
#   SCHEMA_REGISTRY_API_SECRET=...
#
# Usage:
#   ./register_schemas.sh            # register the schemas
#   ./register_schemas.sh --dry-run  # list the subjects without contacting Schema Registry
#
# This script:
#   1. Creates (or reuses) a Python venv at .venv/
#   2. Installs requirements.txt into the venv (idempotent, cached by pip)
#   3. Runs register_schemas.py inside that venv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
SCRIPT="$SCRIPT_DIR/register_schemas.py"

# ── 1. Create venv (recreate if the interpreter shebang is stale) ────────────
_venv_ok=false
if [ -f "$VENV_DIR/bin/python" ]; then
  _shebang="$(head -3 "$VENV_DIR/bin/pip" 2>/dev/null || true)"
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
echo "Installing requirements (certifi, python-dotenv) ..."
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

# ── 4. Run the registration ──────────────────────────────────────────────────
"$PYTHON" "$SCRIPT" "$@"
