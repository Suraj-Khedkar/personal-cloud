#!/usr/bin/env bash
# Minimal-mode watchdog: keep ML stopped + keep-awake while locked.
set -euo pipefail

PROJECT="$HOME/personal-cloud"
# shellcheck source=server-common.sh
source "$PROJECT/scripts/server-common.sh"

[ "$(get_server_mode)" = "minimal" ] || exit 0

"$DOCKER" info >/dev/null 2>&1 || exit 0

stop_ml 2>/dev/null || true
start_minimal_keepawake
