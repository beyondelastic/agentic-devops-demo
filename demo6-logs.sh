#!/usr/bin/env bash
# Demo 6 — pre-stage terminal: stream system logs (OOMKilled / provisioned).
#
# Run from the repo root in its own terminal pane:
#   ./demo6-logs.sh

# NOTE: deliberately NOT using `set -e` / `pipefail` — Azure's log-stream
# endpoint regularly drops (ConnectionResetError) and grep returns 1 when no
# lines match, both of which would otherwise kill the script.
set -uo pipefail || true
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# shellcheck source=demo6-env.sh
source "$SCRIPT_DIR/demo6-env.sh"

echo "==> Streaming system logs for $API_NAME..."
echo "    Filtering to demo-relevant events (OOMKilled, replica restarts, failures)."
echo "    Look for: 'Replica was terminated: OOMKilled' and"
echo "              'Replica has been provisioned'."
echo "    (auto-reconnects if the Azure stream drops; Ctrl+C to stop)"
echo

KEEP_RE='"Reason":"(ContainerTerminated|ContainerRestarted|ContainerCrashed|OOMKilled|ReplicaProvisioned|ReplicaScheduled|ReplicaFailedScheduling|FailedScheduling|BackOff|Unhealthy|Failed)"|OOMKilled|terminated|provisioned'
DROP_RE='"Reason":"(StartingGettingEvents|ConnectedToEventsServer)"'

while true; do
  az containerapp logs show \
    -g "$RG" -n "$API_NAME" \
    --type system --follow --tail 50 2>/dev/null \
    | grep --line-buffered -E "$KEEP_RE" \
    | grep --line-buffered -vE "$DROP_RE" \
    || true
  echo "[$(date +%H:%M:%S)] log stream dropped, reconnecting in 3s..." >&2
  sleep 3
done
