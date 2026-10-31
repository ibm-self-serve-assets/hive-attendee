#!/usr/bin/env bash
# provision_order_topics.sh
# ──────────────────────────
# Creates the two Kafka topics for Level 4 Order Fulfillment.
#
# Configuration is read from spec-shared/.env (the same file you filled in for Level 1).
# No extra setup is needed.
#
# Usage:
#   ./provision_order_topics.sh            # create topics
#   ./provision_order_topics.sh --dry-run  # preview without making API calls
#
# This script:
#   1. Reuses the .venv from level-1-environment-setup/scripts/ (shares requirements)
#   2. Runs provision_order_topics.py inside that venv
#
# Run from the level-4-order-fulfillment/scripts/ directory:
#   cd level-4-order-fulfillment/scripts
#   chmod +x provision_order_topics.sh
#   ./provision_order_topics.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Re-use the venv installed by Level 1 (same requirements: certifi, python-dotenv)
LEVEL1_SCRIPTS="$SCRIPT_DIR/../../level-1-environment-setup/scripts"
VENV_DIR="$LEVEL1_SCRIPTS/.venv"
REQUIREMENTS="$LEVEL1_SCRIPTS/requirements.txt"
SCRIPT="$SCRIPT_DIR/provision_order_topics.py"

# ── 1. Create / reuse venv ────────────────────────────────────────────────────
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
  echo "Creating virtual environment at $VENV_DIR ..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# ── 2. Install / sync requirements ───────────────────────────────────────────
echo "Installing requirements ..."
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
