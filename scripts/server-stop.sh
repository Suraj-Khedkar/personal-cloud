#!/usr/bin/env bash
# Stop personal-cloud server: Docker down + remove cron automation.
set -euo pipefail

PROJECT="$HOME/personal-cloud"
# shellcheck source=server-common.sh
source "$PROJECT/scripts/server-common.sh"

echo "=== Stopping personal-cloud server ==="

stop_keepawake
disable_immich_readonly

if "$DOCKER" info >/dev/null 2>&1; then
  reset_resource_limits
  docker_down
else
  log "Docker not running — skipping compose down."
fi

remove_crons
set_server_mode "stopped"
clear_state

echo ""
if crontab -l 2>/dev/null | grep -qF "personal-cloud"; then
  echo "WARNING: some personal-cloud cron lines may remain. Run: crontab -l"
else
  echo "Crontab: clean (no personal-cloud jobs)."
fi
echo "Server stopped. Cron and keep-awake disabled."
