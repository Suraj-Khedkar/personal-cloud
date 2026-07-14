#!/usr/bin/env bash
# Run the photo cleanup agent locally on Mac (without Docker)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

if [ ! -d "$VENV" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -r "$DIR/requirements.txt"
fi

# Mac paths — override Docker /data/cloud paths
export CLOUD_ROOT="/Volumes/Cloud"
CONFIG_TMP=$(mktemp)
sed "s|/data/cloud|${CLOUD_ROOT}|g" "$DIR/config.yaml" > "$CONFIG_TMP"

mkdir -p "${CLOUD_ROOT}/_review/quarantine" "${CLOUD_ROOT}/_review/logs"

"$VENV/bin/python" "$DIR/agent.py" --config "$CONFIG_TMP" "$@"
rm -f "$CONFIG_TMP"
