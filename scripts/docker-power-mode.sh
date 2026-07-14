#!/usr/bin/env bash
# Cron helper: adjusts ML container based on server mode and power source.
set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
DOCKER="/usr/local/bin/docker"
PMSET="/usr/bin/pmset"

PROJECT="$HOME/personal-cloud"
STATE_DIR="$HOME/.personal-cloud"
LOG="$PROJECT/docker-power.log"
SERVER_MODE_FILE="$STATE_DIR/server-mode"
POWER_MODE_FILE="$STATE_DIR/power-mode"
FORCE=0

if [ "${1:-}" = "--force" ]; then
  FORCE=1
fi

# shellcheck source=server-common.sh
source "$PROJECT/scripts/server-common.sh"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

power_source() {
  if "$PMSET" -g batt | grep -q "AC Power"; then
    echo "ac"
  else
    echo "battery"
  fi
}

if ! "$DOCKER" info >/dev/null 2>&1; then
  log "Docker not running — skipping."
  exit 0
fi

server_mode=$(get_server_mode)

if [ "$server_mode" = "stopped" ]; then
  exit 0
fi

if [ "$server_mode" = "minimal" ]; then
  stop_ml || log "ML already stopped."
  echo "minimal" > "$POWER_MODE_FILE"
  exit 0
fi

cd "$PROJECT"
mode=$(power_source)
prev=""
[ -f "$POWER_MODE_FILE" ] && prev=$(cat "$POWER_MODE_FILE")

if [ "$mode" = "$prev" ] && [ "$FORCE" -eq 0 ]; then
  exit 0
fi

echo "$mode" > "$POWER_MODE_FILE"

if [ "$mode" = "battery" ]; then
  log "Auto mode on battery — stopping Immich ML."
  stop_ml
else
  log "Auto mode on AC — starting Immich ML."
  start_ml
fi
