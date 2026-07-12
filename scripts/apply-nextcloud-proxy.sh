#!/usr/bin/env bash
set -euo pipefail

CONTAINER="personal-cloud-nextcloud-1"
HOST_IP="${1:-192.168.1.4}"

echo "Applying Nextcloud proxy + trusted domain settings..."

# Trusted domains: LAN IP + Tailscale range placeholder
docker exec -u www-data "$CONTAINER" php occ config:system:set trusted_domains 0 --value="${HOST_IP}"
docker exec -u www-data "$CONTAINER" php occ config:system:set trusted_domains 1 --value="localhost"
docker exec -u www-data "$CONTAINER" php occ config:system:set overwriteprotocol --value="https"
docker exec -u www-data "$CONTAINER" php occ config:system:delete overwritehost 2>/dev/null || true
docker exec -u www-data "$CONTAINER" php occ config:system:set overwrite.cli.url --value="https://${HOST_IP}"

# Trusted proxies (Docker + LAN + Tailscale CGNAT range)
docker exec -u www-data "$CONTAINER" php occ config:system:delete trusted_proxies 2>/dev/null || true
docker exec -u www-data "$CONTAINER" php occ config:system:set trusted_proxies 0 --value="172.16.0.0/12"
docker exec -u www-data "$CONTAINER" php occ config:system:set trusted_proxies 1 --value="192.168.0.0/16"
docker exec -u www-data "$CONTAINER" php occ config:system:set trusted_proxies 2 --value="100.64.0.0/10"

# Security hardening
docker exec -u www-data "$CONTAINER" php occ config:system:set allow_local_remote_servers --value="false" --type=boolean
docker exec -u www-data "$CONTAINER" php occ config:system:set loglevel --value="2" --type=integer

echo "Done. Access Nextcloud at: https://${HOST_IP}"
