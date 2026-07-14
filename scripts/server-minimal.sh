#!/usr/bin/env bash
# Minimal server: remote view-only Nextcloud + Immich, lowest resources, stays up when locked.
set -euo pipefail

PROJECT="$HOME/personal-cloud"
# shellcheck source=server-common.sh
source "$PROJECT/scripts/server-common.sh"

echo "=== Starting personal-cloud server (minimal mode) ==="
echo "  Remote file/photo access only — uploads disabled, ML off"
echo "  Do NOT run with sudo."
echo ""

require_cloud_mount
require_docker

set_server_mode "minimal"
echo "minimal" > "$POWER_MODE_FILE"
install_crons_minimal

docker_up_minimal
enable_immich_readonly
apply_minimal_limits
start_minimal_keepawake

echo ""
print_status
echo ""
echo "Minimal mode active:"
echo "  - Nextcloud: browse & download files remotely"
echo "  - Immich: browse photos remotely (no new uploads)"
echo "  - ML, photo-agent, and background jobs: off"
echo "  - Keeps running when you lock the screen (caffeinate -i)"
echo ""
echo "For full features + uploads: ~/personal-cloud/scripts/server-start.sh"
