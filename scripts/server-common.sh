#!/usr/bin/env bash
# Shared helpers for personal-cloud server lifecycle scripts.
set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Always use the real login user — never root (sudo installs crontab for wrong user).
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  REAL_USER="$SUDO_USER"
else
  REAL_USER="$USER"
fi

REAL_HOME=$(eval echo "~$REAL_USER")
PROJECT="$REAL_HOME/personal-cloud"
STATE_DIR="$REAL_HOME/.personal-cloud"
DOCKER="/usr/local/bin/docker"
PMSET="/usr/bin/pmset"
SERVER_MODE_FILE="$STATE_DIR/server-mode"
POWER_MODE_FILE="$STATE_DIR/power-mode"
CAFFEINATE_PIDFILE="$STATE_DIR/caffeinate.pid"
CRONTAB_FILE="$STATE_DIR/crontab.new"

PERSONAL_CLOUD_CRON_TAG="# personal-cloud-managed"

mkdir -p "$STATE_DIR"

ensure_state_dir_writable() {
  if [ -w "$STATE_DIR" ] && { [ ! -f "$SERVER_MODE_FILE" ] || [ -w "$SERVER_MODE_FILE" ]; }; then
    return 0
  fi
  echo "ERROR: $STATE_DIR has root-owned files (from running with sudo)."
  echo "Fix once, then re-run WITHOUT sudo:"
  echo "  sudo chown -R $REAL_USER \"$STATE_DIR\""
  echo "  sudo crontab -r"
  echo "  ~/personal-cloud/scripts/server-minimal.sh"
  exit 1
}

if [ "$(id -u)" -eq 0 ]; then
  echo "ERROR: Do not run server scripts with sudo."
  echo "Cron installs for root — your user will not see them with crontab -l."
  if [ -n "${SUDO_USER:-}" ]; then
    echo "Run as $SUDO_USER instead:"
    echo "  ~/personal-cloud/scripts/server-minimal.sh"
  fi
  echo ""
  echo "To remove mistaken root crontab: sudo crontab -r"
  exit 1
fi

crontab_list() {
  crontab -l 2>/dev/null || true
}

crontab_install() {
  crontab "$1"
}

crontab_remove_all() {
  crontab -r 2>/dev/null || true
}

crontab_install_filtered() {
  crontab -
}

CRON_PHOTO="0 3 * * 0 /bin/bash $PROJECT/photo-agent/run-local.sh >> /Volumes/Cloud/_review/logs/cron.log 2>&1"
CRON_POWER="*/10 * * * * /bin/bash $PROJECT/scripts/docker-power-mode.sh >> $PROJECT/docker-power.log 2>&1"
CRON_MINIMAL="*/30 * * * * /bin/bash $PROJECT/scripts/server-minimal-watchdog.sh >> $PROJECT/docker-power.log 2>&1"

MINIMAL_SERVICES=(nextcloud-db nextcloud nginx immich-db immich-redis immich-server)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

require_cloud_mount() {
  if [ ! -d "/Volumes/Cloud" ]; then
    echo "ERROR: /Volumes/Cloud is not mounted. Plug in the external drive first."
    exit 1
  fi
}

require_docker() {
  if ! "$DOCKER" info >/dev/null 2>&1; then
    echo "ERROR: Docker is not running. Open Docker Desktop first."
    exit 1
  fi
}

set_server_mode() {
  ensure_state_dir_writable
  echo "$1" > "$SERVER_MODE_FILE"
}

get_server_mode() {
  if [ -f "$SERVER_MODE_FILE" ]; then
    cat "$SERVER_MODE_FILE"
  else
    echo "stopped"
  fi
}

_is_personal_cloud_cron_line() {
  local line="$1"
  [[ "$line" == *"$PERSONAL_CLOUD_CRON_TAG"* ]] \
    || [[ "$line" == *"personal-cloud/photo-agent"* ]] \
    || [[ "$line" == *"personal-cloud/scripts/docker-power-mode"* ]] \
    || [[ "$line" == *"personal-cloud/scripts/server-minimal-watchdog"* ]] \
    || [[ "$line" == *"personal-cloud/scripts/server-"* ]]
}

_filter_out_personal_cloud_crons() {
  local line
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "${line//[[:space:]]/}" ] && continue
    if _is_personal_cloud_cron_line "$line"; then
      continue
    fi
    printf '%s\n' "$line"
  done
}

_has_personal_cloud_crons() {
  local existing line
  existing=$(crontab_list)
  [ -z "$existing" ] && return 1
  while IFS= read -r line; do
    _is_personal_cloud_cron_line "$line" && return 0
  done <<< "$existing"
  return 1
}

install_personal_cloud_crons() {
  local existing filtered
  existing=$(crontab_list)

  {
    if [ -n "$existing" ]; then
      printf '%s\n' "$existing" | _filter_out_personal_cloud_crons
    fi
    while [ "$#" -gt 0 ]; do
      echo "$1 $PERSONAL_CLOUD_CRON_TAG"
      shift
    done
  } > "$CRONTAB_FILE"

  if ! crontab_install "$CRONTAB_FILE"; then
    echo "ERROR: crontab install failed for user $REAL_USER."
    echo "Grant Full Disk Access to Terminal (or Cursor), then retry."
    echo "Do NOT use sudo."
    rm -f "$CRONTAB_FILE"
    exit 1
  fi
  rm -f "$CRONTAB_FILE"

  if ! crontab_list | grep -qF "$PERSONAL_CLOUD_CRON_TAG"; then
    echo "ERROR: crontab install verification failed for user $REAL_USER."
    echo "Run: crontab -l   (without sudo)"
    exit 1
  fi

  log "Cron jobs installed for user $REAL_USER."
  echo ""
  crontab_list | grep -F "$PERSONAL_CLOUD_CRON_TAG" || true
}

install_crons_full() {
  install_personal_cloud_crons "$CRON_PHOTO" "$CRON_POWER"
}

install_crons_minimal() {
  install_personal_cloud_crons "$CRON_MINIMAL"
}

remove_crons() {
  local existing filtered
  existing=$(crontab_list)

  if [ -z "$existing" ]; then
    log "No crontab present for user $REAL_USER."
    return 0
  fi

  filtered=$(printf '%s\n' "$existing" | _filter_out_personal_cloud_crons || true)

  if [ -z "${filtered//[[:space:]]/}" ]; then
    crontab_remove_all
  else
    printf '%s\n' "$filtered" | crontab_install_filtered
  fi

  if _has_personal_cloud_crons; then
    echo "ERROR: failed to remove all personal-cloud cron jobs for $REAL_USER."
    echo "Remaining crontab:"
    crontab_list
    exit 1
  fi

  log "Cron jobs removed for user $REAL_USER."
}

docker_up() {
  cd "$PROJECT"
  log "Starting full Docker stack..."
  "$DOCKER" compose up -d
}

docker_up_minimal() {
  cd "$PROJECT"
  log "Starting minimal Docker stack (remote view only)..."
  "$DOCKER" compose up -d "${MINIMAL_SERVICES[@]}"
  stop_ml 2>/dev/null || true
}

docker_down() {
  cd "$PROJECT"
  log "Stopping Docker stack..."
  "$DOCKER" compose down
}

stop_ml() {
  cd "$PROJECT"
  "$DOCKER" compose stop immich-machine-learning 2>/dev/null || true
}

start_ml() {
  cd "$PROJECT"
  "$DOCKER" compose start immich-machine-learning 2>/dev/null || \
    "$DOCKER" compose up -d immich-machine-learning
}

reload_nginx() {
  "$DOCKER" exec personal-cloud-nginx-1 nginx -s reload 2>/dev/null || true
}

enable_immich_readonly() {
  cp "$PROJECT/nginx/templates/immich-minimal.conf" "$PROJECT/nginx/conf.d/immich.conf"
  reload_nginx
  log "Immich: view/download only (uploads blocked)."
}

disable_immich_readonly() {
  cp "$PROJECT/nginx/templates/immich-full.conf" "$PROJECT/nginx/conf.d/immich.conf"
  reload_nginx
}

apply_minimal_limits() {
  log "Applying memory/CPU limits for minimal mode..."
  local spec name mem cpu
  for spec in \
    "personal-cloud-immich-server-1:1024m:1.0" \
    "personal-cloud-nextcloud-1:384m:0.5" \
    "personal-cloud-nextcloud-db-1:256m:0.5" \
    "personal-cloud-immich-db-1:256m:0.5" \
    "personal-cloud-immich-redis-1:64m:0.25" \
    "personal-cloud-nginx-1:64m:0.25"; do
    IFS=: read -r name mem cpu <<< "$spec"
    "$DOCKER" update --memory="$mem" --memory-swap="$mem" --cpus="$cpu" "$name" 2>/dev/null || true
  done
}

reset_resource_limits() {
  log "Removing Docker resource limits..."
  local name
  for name in personal-cloud-immich-server-1 personal-cloud-nextcloud-1 \
    personal-cloud-nextcloud-db-1 personal-cloud-immich-db-1 \
    personal-cloud-immich-redis-1 personal-cloud-nginx-1 \
    personal-cloud-immich-machine-learning-1; do
    "$DOCKER" update --memory=0 --memory-swap=0 --cpus=0 "$name" 2>/dev/null || true
  done
}

start_minimal_keepawake() {
  if [ -f "$CAFFEINATE_PIDFILE" ]; then
    local pid
    pid=$(cat "$CAFFEINATE_PIDFILE")
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    rm -f "$CAFFEINATE_PIDFILE"
  fi
  caffeinate -i &
  echo $! > "$CAFFEINATE_PIDFILE"
  log "Keep-awake enabled for lock screen (caffeinate -i, PID $(cat "$CAFFEINATE_PIDFILE"))."
}

stop_keepawake() {
  if [ -f "$CAFFEINATE_PIDFILE" ]; then
    kill "$(cat "$CAFFEINATE_PIDFILE")" 2>/dev/null || true
    rm -f "$CAFFEINATE_PIDFILE"
  fi
  log "Keep-awake stopped."
}

apply_power_mode() {
  /bin/bash "$PROJECT/scripts/docker-power-mode.sh" --force
}

print_status() {
  cd "$PROJECT"
  echo ""
  "$DOCKER" compose ps
  echo ""
  echo "Mode: $(get_server_mode)"
  echo "Nextcloud: https://192.168.1.4  (Tailscale: https://100.94.81.46)"
  echo "Immich:    https://192.168.1.4:8443  (Tailscale: https://100.94.81.46:8443)"
}

clear_state() {
  rm -f "$SERVER_MODE_FILE" "$POWER_MODE_FILE" "$CRONTAB_FILE"
}
