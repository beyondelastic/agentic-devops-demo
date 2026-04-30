#!/usr/bin/env bash
# Demo 2 fast path: reconcile .foundry/* into a new Foundry agent version
# locally (~5s), without waiting for the CI pipeline.
#
# Same script the azd postdeploy hook runs in CI; we just invoke it directly
# with `azd env get-values` exported into the shell.
set -euo pipefail

cd "$(dirname "$0")"

VENV="${TMPDIR:-/tmp}/foundry-venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "==> creating venv at $VENV (one-time, ~20s)"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet \
    azure-ai-projects==2.1.0 \
    azure-identity==1.19.0 \
    pyyaml==6.0.2
fi

echo "==> loading azd env"
# Each line of `azd env get-values` is KEY="value" — set -a + source handles quoting.
set -a
# shellcheck disable=SC1090
source <(azd env get-values)
set +a

echo "==> reconciling agent"
"$VENV/bin/python" infra/scripts/sync_agent.py
