#!/usr/bin/env bash
# Start full personal-cloud server: Docker + cron automation (AC/battery aware).
set -euo pipefail

PROJECT="$HOME/personal-cloud"
# shellcheck source=server-common.sh
source "$PROJECT/scripts/server-common.sh"

echo "=== Starting personal-cloud server (full / auto mode) ==="

require_cloud_mount
require_docker

stop_keepawake
disable_immich_readonly
set_server_mode "auto"
install_crons_full

docker_up
reset_resource_limits
apply_power_mode

echo ""
print_status
echo ""
echo "Full server running. Uploads enabled. ML runs on AC, stops on battery."
