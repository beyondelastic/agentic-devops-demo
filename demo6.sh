#!/usr/bin/env bash
# Demo 6 — kick off the memory-leak scenario.
#
# Prerequisite: run ./demo6-prep.sh first (caps max-replicas to 2 and waits
# for the new revision to be Active). Without that, the leak gets diluted
# across an autoscaling fleet and the OOM cycles aren't visible in metrics.
#
# This script:
# 1. Toggles ENABLE_MEMORY_LEAK=true on the API container app.
# 2. Starts the k6 soak (constant arrival rate, 10 min) against the public
#    frontend, which proxies /api/chat to the API.
#
# Run from the repo root:
#   ./demo6.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# shellcheck source=demo6-env.sh
source "$SCRIPT_DIR/demo6-env.sh"

echo "==> Resource group: $RG"
echo "==> API container app: $API_NAME"
echo "==> Frontend URL: $FRONTEND_URL"
echo

# Sanity check: maxReplicas must already be 2 (set by demo6-prep.sh).
MAX_REPLICAS="$(az containerapp show -g "$RG" -n "$API_NAME" \
  --query "properties.template.scale.maxReplicas" -o tsv)"
if [[ "$MAX_REPLICAS" != "2" ]]; then
  echo "WARNING: maxReplicas=$MAX_REPLICAS (expected 2). Run ./demo6-prep.sh first." >&2
  echo "Press Ctrl+C now to abort, or wait 5s to continue anyway..." >&2
  sleep 5
fi

echo "==> [1/2] Enabling ENABLE_MEMORY_LEAK=true..."
az containerapp update -g "$RG" -n "$API_NAME" \
  --set-env-vars ENABLE_MEMORY_LEAK=true -o none

echo "==> [2/2] Starting k6 soak (load/k6-leak.js, 10 min)..."
echo "    OOM cycles should appear in the pre-staged terminals within 1-2 min."
echo
exec k6 run -e API_BASE="$FRONTEND_URL" "$SCRIPT_DIR/load/k6-leak.js"
