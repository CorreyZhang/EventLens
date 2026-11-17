#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export DSH_HOME="$PROJECT_DIR/data/harness-home"
# This is a non-secret placeholder: EventLens forwards with its own in-memory key.
export DEEPSEEK_API_KEY='sk-eventlens-loopback-placeholder-not-a-real-key'
export DEEPSEEK_BASE_URL='http://127.0.0.1:8765/harness-api/anthropic'
export DSH_TELEMETRY_MODE=DISABLED
mkdir -p "$DSH_HOME"
NAV_LINK="$DSH_HOME/profiles/web/node_modules/@eventlens/harness-navigation"
mkdir -p "$(dirname "$NAV_LINK")"
if [ ! -e "$NAV_LINK" ] && [ ! -L "$NAV_LINK" ]; then
  ln -s "$PROJECT_DIR/harness-navigation" "$NAV_LINK"
elif [ ! -L "$NAV_LINK" ] || [ "$(readlink "$NAV_LINK")" != "$PROJECT_DIR/harness-navigation" ]; then
  echo "EventLens navigation plugin path conflicts with an existing package: $NAV_LINK" >&2
  exit 1
fi
cd "$PROJECT_DIR/harness-workspace"
HARNESS_CLI=${EVENTLENS_DSH_BIN:-}
if [ -z "$HARNESS_CLI" ] && [ -f "$PROJECT_DIR/data/harness-runtime/node_modules/@deepseek-ai/dsh/lib/bin.js" ]; then
  HARNESS_CLI="$PROJECT_DIR/data/harness-runtime/node_modules/@deepseek-ai/dsh/lib/bin.js"
fi
if [ -n "$HARNESS_CLI" ]; then
  exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/run_harness.py" node "$HARNESS_CLI" --profile web --patch "$PROJECT_DIR/harness.overlay.yaml" --no-open
fi
exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/run_harness.py" npm --cache /private/tmp/eventlens-npm-cache exec --yes --package=@deepseek-ai/dsh@0.2.2-rc.1 -- dsh --profile web --patch "$PROJECT_DIR/harness.overlay.yaml" --no-open
