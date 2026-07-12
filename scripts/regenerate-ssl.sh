#!/usr/bin/env bash
# Regenerate SSL cert — run after LAN IP changes or before Pi migration.
# Usage: ./regenerate-ssl.sh 192.168.1.4 [100.x.x.x]

set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAN_IP="${1:-192.168.1.4}"
TS_IP="${2:-}"

ALT_NAMES="DNS.1 = personal-cloud.local
DNS.2 = localhost
IP.1 = 127.0.0.1
IP.2 = ${LAN_IP}"

if [ -n "$TS_IP" ]; then
  ALT_NAMES="${ALT_NAMES}
IP.3 = ${TS_IP}"
fi

cat > "${DIR}/nginx/ssl/openssl.cnf" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
CN = personal-cloud.local
O = Personal Cloud
C = IN

[req_ext]
subjectAltName = @alt_names

[alt_names]
${ALT_NAMES}
EOF

openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "${DIR}/nginx/ssl/cloud.key" \
  -out "${DIR}/nginx/ssl/cloud.crt" \
  -config "${DIR}/nginx/ssl/openssl.cnf" \
  -extensions req_ext

chmod 600 "${DIR}/nginx/ssl/cloud.key"
echo "SSL cert regenerated for LAN IP ${LAN_IP}${TS_IP:+ and Tailscale IP ${TS_IP}}"
echo "Restart nginx: cd ${DIR} && docker compose restart nginx"
