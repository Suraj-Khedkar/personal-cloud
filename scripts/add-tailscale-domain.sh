#!/usr/bin/env bash
set -euo pipefail

# Run after: tailscale up
# Adds your Tailscale IP as a trusted Nextcloud domain

CONTAINER="personal-cloud-nextcloud-1"
TS_IP=$(tailscale ip -4 2>/dev/null || true)

if [ -z "$TS_IP" ]; then
  echo "Tailscale not running. Install and run: tailscale up"
  exit 1
fi

echo "Adding Tailscale IP: $TS_IP"

docker exec -u www-data "$CONTAINER" php occ config:system:set trusted_domains 2 --value="${TS_IP}"
docker exec -u www-data "$CONTAINER" php occ config:system:set overwrite.cli.url --value="https://${TS_IP}"

echo ""
echo "Remote access URL for iPhone Nextcloud app:"
echo "  https://${TS_IP}"
echo ""
echo "Re-trust the certificate on iPhone when prompted."
