#!/usr/bin/env bash
# Flip the API container app's ingress to external (for demo recording).
# Reverse with ./demo4-ingress-internal.sh.

set -euo pipefail

eval "$(azd env get-values | grep -E '^AZURE_RESOURCE_GROUP=')"
: "${AZURE_RESOURCE_GROUP:?}"

API_APP="$(az containerapp list -g "$AZURE_RESOURCE_GROUP" \
  --query "[?tags.\"azd-service-name\"=='api'].name | [0]" -o tsv)"

echo "Flipping ingress on $API_APP to EXTERNAL ..."
az containerapp ingress update \
  -g "$AZURE_RESOURCE_GROUP" -n "$API_APP" \
  --type external >/dev/null

API_FQDN="$(az containerapp show -g "$AZURE_RESOURCE_GROUP" -n "$API_APP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)"

echo "Done. External FQDN: https://${API_FQDN}"
echo "Allow ~30s for the LB to propagate, then:"
echo "  curl https://${API_FQDN}/version"
