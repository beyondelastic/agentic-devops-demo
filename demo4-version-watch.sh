#!/usr/bin/env bash
# Demo 4 — watch /version every 5s and print git_sha.
#
# Usage:
#   ./demo4-version-watch.sh           # tail forever (Ctrl+C to stop)
#   INTERVAL=10 ./demo4-version-watch.sh
#
# The API has internal-only ingress, so we can't curl it from the laptop.
# `az containerapp exec` runs curl from inside the running container.

set -euo pipefail

INTERVAL="${INTERVAL:-5}"

# Resolve RG + API container app name from the current azd env.
eval "$(azd env get-values | grep -E '^AZURE_RESOURCE_GROUP=')"
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP not set — run from an azd-initialized repo}"

API_APP="$(az containerapp list \
  -g "$AZURE_RESOURCE_GROUP" \
  --query "[?tags.\"azd-service-name\"=='api'].name | [0]" \
  -o tsv)"

if [[ -z "$API_APP" ]]; then
  echo "ERROR: could not find an api container app in $AZURE_RESOURCE_GROUP" >&2
  exit 1
fi

echo "RG:       $AZURE_RESOURCE_GROUP"
echo "API app:  $API_APP"
echo "Interval: ${INTERVAL}s  (Ctrl+C to stop)"
echo

version() {
  az containerapp exec \
    -g "$AZURE_RESOURCE_GROUP" \
    -n "$API_APP" \
    --command "curl -s http://localhost:8000/version"
}

while true; do
  echo "$(date +%H:%M:%S)  $(version 2>/dev/null | grep -oE '"git_sha":"[^"]+"' || echo '(no response)')"
  sleep "$INTERVAL"
done
