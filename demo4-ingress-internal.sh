#!/usr/bin/env bash
# Restore internal-only ingress on the API container app after demo recording.

set -euo pipefail

eval "$(azd env get-values | grep -E '^AZURE_RESOURCE_GROUP=')"
: "${AZURE_RESOURCE_GROUP:?}"

API_APP="$(az containerapp list -g "$AZURE_RESOURCE_GROUP" \
  --query "[?tags.\"azd-service-name\"=='api'].name | [0]" -o tsv)"

echo "Flipping ingress on $API_APP back to INTERNAL ..."
az containerapp ingress update \
  -g "$AZURE_RESOURCE_GROUP" -n "$API_APP" \
  --type internal >/dev/null

echo "Done."
