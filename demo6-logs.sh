#!/usr/bin/env bash
# Demo 6 — pre-stage terminal: stream system logs (OOMKilled / provisioned).
#
# Run from the repo root in its own terminal pane:
#   ./demo6-logs.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# shellcheck source=demo6-env.sh
source "$SCRIPT_DIR/demo6-env.sh"

echo "==> Streaming system logs for $API_NAME..."
echo "    Look for: 'Replica was terminated: OOMKilled' and"
echo "              'Replica has been provisioned'."
echo

exec az containerapp logs show \
  -g "$RG" -n "$API_NAME" \
  --type system --follow --tail 50
