#!/bin/bash
# Daily Octopoda telemetry cleanup.
# Stops the API briefly so SQLite has exclusive access (avoids swap thrashing
# on the memory-pressured Mac Mini). Total outage budget: ~90 seconds.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/octopoda-cleanup.log"
CONTAINER="octopoda-os-api-1"
API_HEALTH_URL="http://localhost:8443/v1/agents"
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

mkdir -p "$(dirname "$LOG")"
TS=$(date +%Y-%m-%dT%H:%M:%S)
log() { echo "$TS $*" >> "$LOG"; }

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
  log "[ERROR] container $CONTAINER not running before cleanup"
  "$SCRIPT_DIR/telegram_alert.sh" "Octopoda cleanup skipped: container not running" || true
  exit 1
fi

log "[INFO] stopping $CONTAINER for exclusive DB access"
if ! docker stop --time 10 "$CONTAINER" > /dev/null 2>&1; then
  log "[ERROR] docker stop failed"
  "$SCRIPT_DIR/telegram_alert.sh" "Octopoda cleanup FAILED: docker stop" || true
  exit 1
fi

# Run cleanup in a one-shot container using the same Octopoda image
# (has python3+sqlite3 baked in) with entrypoint overridden to python3.
RESULT=$(docker run --rm -i \
  --entrypoint python3 \
  -v octopoda-os_synrix-data:/data \
  octopoda-os-api \
  - < "$SCRIPT_DIR/cleanup_telemetry.py" 2>&1)
RC=$?

log "[INFO] cleanup RC=$RC: $RESULT"

log "[INFO] starting $CONTAINER"
if ! docker start "$CONTAINER" > /dev/null 2>&1; then
  log "[ERROR] docker start failed"
  "$SCRIPT_DIR/telegram_alert.sh" "Octopoda cleanup CRITICAL: container won't restart after cleanup" || true
  exit 2
fi

# Wait up to 120s for API health
DEADLINE=$(( $(date +%s) + 120 ))
while [ $(date +%s) -lt $DEADLINE ]; do
  CODE=$(curl -s --max-time 5 -o /dev/null -w '%{http_code}' "$API_HEALTH_URL" || echo 000)
  if [ "$CODE" = "200" ]; then
    log "[INFO] API back up (HTTP 200)"
    break
  fi
  sleep 3
done

if [ "$CODE" != "200" ]; then
  log "[ERROR] API did not become healthy within 120s after restart"
  "$SCRIPT_DIR/telegram_alert.sh" "Octopoda cleanup CRITICAL: API not healthy after restart (got $CODE)" || true
  exit 2
fi

# Parse cleanup result + alert on warn/crit/error
case "$RESULT" in
  *'"status": "crit"'*)
    "$SCRIPT_DIR/telegram_alert.sh" "Octopoda DB over 600MB crit threshold after cleanup: $RESULT" || true
    ;;
  *'"status": "error"'*)
    "$SCRIPT_DIR/telegram_alert.sh" "Octopoda cleanup FAILED: $RESULT" || true
    ;;
  *'"status": "warn"'*)
    "$SCRIPT_DIR/telegram_alert.sh" "Octopoda DB above 400MB warn threshold: $RESULT" || true
    ;;
esac

exit "$RC"
