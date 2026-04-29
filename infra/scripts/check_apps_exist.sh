#!/usr/bin/env sh
# Detect whether each container app already exists in the target resource group
# and write SERVICE_<svc>_EXISTS env vars into the azd environment so Bicep can
# decide between placeholder image (first deploy) and existing image (re-deploy).
set -eu

: "${AZURE_RESOURCE_GROUP:=}"
if [ -z "${AZURE_RESOURCE_GROUP}" ]; then
  # azd may not have set RG yet on the very first run — derive name from env name + token unknown.
  # Best-effort: leave defaults (false) so Bicep uses placeholder.
  echo "[preprovision] AZURE_RESOURCE_GROUP not set yet; assuming first deploy."
  azd env set SERVICE_TOOLS_EXISTS false
  azd env set SERVICE_API_EXISTS    false
  azd env set SERVICE_FRONTEND_EXISTS false
  exit 0
fi

check() {
  svc="$1"
  prefix="$2"
  # Look up by azd-service-name tag in the target RG.
  name="$(az containerapp list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "[?tags.\"azd-service-name\"=='${svc}'].name | [0]" \
    -o tsv 2>/dev/null || true)"
  if [ -n "${name:-}" ] && [ "${name}" != "null" ]; then
    echo "[preprovision] ${svc}: exists (${name})"
    azd env set "SERVICE_${prefix}_EXISTS" true
  else
    echo "[preprovision] ${svc}: not found — first deploy."
    azd env set "SERVICE_${prefix}_EXISTS" false
  fi
}

check tools    TOOLS
check api      API
check frontend FRONTEND
