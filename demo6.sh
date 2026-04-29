#!/usr/bin/env bash
# Demo 6 — kick off the memory-leak scenario.
#
# 1. Cap maxReplicas to 2 so the leak isn't diluted across the autoscale fleet.
# 2. Toggle ENABLE_MEMORY_LEAK=true on the API container app.
# 3. Start the k6 soak (constant arrival rate, 10 min) against the public
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

echo "==> [1/3] Capping max-replicas to 2..."
az containerapp update -g "$RG" -n "$API_NAME" --max-replicas 2 -o none

echo "==> [2/3] Enabling ENABLE_MEMORY_LEAK=true..."
az containerapp update -g "$RG" -n "$API_NAME" \
  --set-env-vars ENABLE_MEMORY_LEAK=true -o none

echo "==> [3/3] Starting k6 soak (load/k6-leak.js, 10 min)..."
echo "    OOM cycles should appear in the pre-staged terminals within 1-2 min."
echo
exec k6 run -e API_BASE="$FRONTEND_URL" "$SCRIPT_DIR/load/k6-leak.js"
