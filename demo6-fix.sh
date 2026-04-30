#!/usr/bin/env bash
# Demo 6 — apply the SRE Agent's recommended fix.
#
# 1. Disable ENABLE_MEMORY_LEAK on the API container app.
# 2. Restore CPU/memory limits (0.5 cpu / 1Gi) tightened by demo6-prep.sh.
# 3. Restore maxReplicas to 5 (the default from infra/modules/containerapp.bicep).
#
# Run from the repo root:
#   ./demo6-fix.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# shellcheck source=demo6-env.sh
source "$SCRIPT_DIR/demo6-env.sh"

echo "==> [1/3] Disabling ENABLE_MEMORY_LEAK..."
az containerapp update -g "$RG" -n "$API_NAME" \
  --set-env-vars ENABLE_MEMORY_LEAK=false -o none

echo "==> [2/3] Restoring CPU/memory limits (0.5 cpu / 1Gi)..."
az containerapp update -g "$RG" -n "$API_NAME" --cpu 0.5 --memory 1Gi -o none

echo "==> [3/3] Restoring max-replicas to 5..."
az containerapp update -g "$RG" -n "$API_NAME" --max-replicas 5 -o none

echo
echo "Done. Healthy replicas should come back up within ~30s."
