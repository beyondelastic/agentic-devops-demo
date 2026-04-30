#!/usr/bin/env bash
# Demo 6 — PREP step (run before the recording, NOT during).
#
# Caps the API to maxReplicas=2 so the leak isn't diluted across the
# autoscale fleet, then waits until the new revision is Active and the
# replica count has actually settled to <=2. Without this, demo6.sh's load
# would briefly run against the old config (maxReplicas=10) and the OOM
# signal hides in the average.
#
# Run from the repo root, ~2 minutes before kicking off the recording:
#   ./demo6-prep.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# shellcheck source=demo6-env.sh
source "$SCRIPT_DIR/demo6-env.sh"

echo "==> Capping max-replicas to 2 on $API_NAME ..."
az containerapp update -g "$RG" -n "$API_NAME" --max-replicas 2 -o none

echo "==> Tightening replicas to the smallest ACA Consumption combo (0.25 cpu / 0.5Gi)..."
echo "    Default is 0.5 cpu / 1Gi; demo6-fix.sh restores it."
az containerapp update -g "$RG" -n "$API_NAME" --cpu 0.25 --memory 0.5Gi -o none

echo "==> Waiting for the new revision to become Active..."
for i in {1..30}; do
  STATE="$(az containerapp revision list -g "$RG" -n "$API_NAME" \
    --query "[?properties.active].properties.runningState | [0]" -o tsv 2>/dev/null || echo "")"
  if [[ "$STATE" == "Running" ]]; then
    echo "    revision Running."
    break
  fi
  printf '    [%02d/30] revision state=%s, sleeping 5s...\n' "$i" "${STATE:-unknown}"
  sleep 5
done

echo "==> Waiting for replica count to settle (<=2)..."
for i in {1..30}; do
  REVISION="$(az containerapp revision list -g "$RG" -n "$API_NAME" \
    --query "[?properties.active].name | [0]" -o tsv)"
  COUNT="$(az containerapp replica list -g "$RG" -n "$API_NAME" \
    --revision "$REVISION" --query "length(@)" -o tsv 2>/dev/null || echo "?")"
  if [[ "$COUNT" =~ ^[0-9]+$ && "$COUNT" -le 2 ]]; then
    echo "    replicas=$COUNT — ready."
    break
  fi
  printf '    [%02d/30] replicas=%s, sleeping 5s...\n' "$i" "$COUNT"
  sleep 5
done

echo
echo "==> Prep complete. You can now:"
echo "    1. Open the metrics chart (Memory %, Replica Count, Restart Count)."
echo "    2. Start ./demo6-watch.sh and ./demo6-logs.sh in side terminals."
echo "    3. Run ./demo6.sh to enable the leak + start k6."
