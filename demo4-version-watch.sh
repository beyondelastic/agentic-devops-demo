#!/usr/bin/env bash
# Demo 4 — watch /version every 5s and print git_sha.
#
# Usage:
#   ./demo4-version-watch.sh           # tail forever (Ctrl+C to stop)
#   INTERVAL=10 ./demo4-version-watch.sh
#
# Hits the API container app's external FQDN. Run ./demo4-ingress-external.sh
# once before recording to flip ingress from internal -> external.

set -euo pipefail

INTERVAL="${INTERVAL:-5}"

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

API_FQDN="$(az containerapp show \
  -g "$AZURE_RESOURCE_GROUP" -n "$API_APP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)"

EXTERNAL="$(az containerapp show \
  -g "$AZURE_RESOURCE_GROUP" -n "$API_APP" \
  --query "properties.configuration.ingress.external" -o tsv)"

if [[ "$EXTERNAL" != "true" ]]; then
  echo "WARNING: API ingress is internal — /version will not be reachable from your laptop." >&2
  echo "Run ./demo4-ingress-external.sh first to flip it (and ./demo4-ingress-internal.sh to revert)." >&2
fi

echo "RG:       $AZURE_RESOURCE_GROUP"
echo "API:      $API_APP"
echo "URL:      https://${API_FQDN}/version"
echo "Interval: ${INTERVAL}s  (Ctrl+C to stop)"
echo

while true; do
  echo "$(date +%H:%M:%S)  $(curl -sf --max-time 4 "https://${API_FQDN}/version" 2>/dev/null | grep -oE '"git_sha":"[^"]+"' || echo '(no response)')"
  sleep "$INTERVAL"
done
