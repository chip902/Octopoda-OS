#!/bin/bash
# Octopoda+Mini health check. Invoked every 30 min by com.octopoda.healthcheck.
# Alerts on transitions to warn/crit, on recovery to ok, and every 6h if stuck.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/octopoda-healthcheck.log"
STATE_DIR="$HOME/Library/Application Support/octopoda-healthcheck"
STATE_FILE="$STATE_DIR/last_state.txt"
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

mkdir -p "$(dirname "$LOG")" "$STATE_DIR"
TS=$(date +%Y-%m-%dT%H:%M:%S)

RESULT=$(python3 "$SCRIPT_DIR/health_check.py" 2>&1)
RC=$?

echo "$TS RC=$RC $RESULT" >> "$LOG"

CURR="ok"
[ "$RC" -eq 1 ] && CURR="warn"
[ "$RC" -ge 2 ] && CURR="crit"
PREV=$(cat "$STATE_FILE" 2>/dev/null || echo "ok")

ALERT_REASON=""
case "$PREV-$CURR" in
  ok-warn|ok-crit|warn-crit)
    ALERT_REASON="transition to $CURR"
    ;;
  warn-ok|crit-ok)
    "$SCRIPT_DIR/telegram_alert.sh" "Octopoda health recovered to ok: $RESULT" || true
    ;;
esac

# Re-alert every 6h while still degraded
if [ "$CURR" != "ok" ]; then
  AGE_FILE="$STATE_DIR/last_alert_${CURR}.epoch"
  NOW=$(date +%s)
  LAST=$(cat "$AGE_FILE" 2>/dev/null || echo "0")
  AGE=$((NOW - LAST))
  if [ -n "$ALERT_REASON" ] || [ $AGE -gt 21600 ]; then
    "$SCRIPT_DIR/telegram_alert.sh" "Octopoda health $CURR (${ALERT_REASON:-still degraded}): $RESULT" || true
    echo "$NOW" > "$AGE_FILE"
  fi
fi

echo "$CURR" > "$STATE_FILE"
exit 0
