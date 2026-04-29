#!/usr/bin/env bash
# Shared env loader for the Demo 6 helper scripts.
#
# Pulls AZURE_RESOURCE_GROUP and the API container app name out of `azd env
# get-values` (no hard-coded names). Source this from the other demo6-*.sh
# scripts:
#
#   source "$(dirname "$0")/demo6-env.sh"

set -euo pipefail

if ! command -v azd >/dev/null 2>&1; then
  echo "azd CLI not found on PATH" >&2
  exit 1
fi

if ! command -v az >/dev/null 2>&1; then
  echo "az CLI not found on PATH" >&2
  exit 1
fi

_AZD_VALUES="$(azd env get-values 2>/dev/null)"

extract() {
  awk -F'=' -v key="$1" '$1==key {gsub(/"/,"",$2); print $2}' <<<"$_AZD_VALUES"
}

RG="$(extract AZURE_RESOURCE_GROUP)"
API_FQDN="$(extract API_INTERNAL_FQDN)"
FRONTEND_URL="$(extract FRONTEND_URL)"

# API container app name = first DNS label of the internal FQDN
# (e.g. "adgd-api-3wnyg3nk2w76m.internal.<env>.eastus2.azurecontainerapps.io").
API_NAME="${API_FQDN%%.*}"

if [[ -z "$RG" || -z "$API_NAME" || -z "$FRONTEND_URL" ]]; then
  echo "Could not resolve azd env values. Run 'azd env get-values' to debug." >&2
  echo "  RG='$RG'  API_NAME='$API_NAME'  FRONTEND_URL='$FRONTEND_URL'" >&2
  exit 1
fi

export RG API_NAME FRONTEND_URL
