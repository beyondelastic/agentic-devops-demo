#!/usr/bin/env bash
# Demo 6 — pre-stage terminal: live replica churn view.
#
# Replica names rotate and the `created` timestamps reset every time ACA
# replaces an OOM-killed replica, even though the count stays at N/N. This is
# the cleanest CLI signal that things are dying.
#
# Run from the repo root in its own terminal pane:
#   ./demo6-watch.sh

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# shellcheck source=demo6-env.sh
source "$SCRIPT_DIR/demo6-env.sh"

REVISION="$(az containerapp revision list -g "$RG" -n "$API_NAME" \
  --query "[?properties.active].name | [0]" -o tsv)"

if [[ -z "$REVISION" ]]; then
  echo "No active revision found for $API_NAME in $RG" >&2
  exit 1
fi

echo "==> Watching replicas of $API_NAME (revision $REVISION)"
echo "    Watch the 'name' and 'created' columns rotate when replicas OOM."
echo

QUERY='[].{name:name, created:properties.createdTime, state:properties.runningState}'
CMD="az containerapp replica list -g '$RG' -n '$API_NAME' --revision '$REVISION' --query \"$QUERY\" -o table"
exec watch -n 1 "$CMD"
