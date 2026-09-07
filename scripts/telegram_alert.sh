#!/bin/bash
# Send a Telegram message via FRIDAY's bot. Reads token + chat_id from FRIDAY config.
set -uo pipefail

TEXT="${1:-no message}"
CONFIG="/Users/andrew/code/friday-remote/config.yml"

if [ ! -f "$CONFIG" ]; then
  echo "telegram_alert: config not found at $CONFIG" >&2
  exit 1
fi

TOKEN=$(awk -F'"' '/bot_token:/ {print $2; exit}' "$CONFIG")
CHAT_ID=$(grep -E '^\s*allowed_chat_ids:' "$CONFIG" | grep -oE '[0-9]{6,}' | head -1)

if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "telegram_alert: missing token ($TOKEN) or chat_id ($CHAT_ID)" >&2
  exit 1
fi

curl -s --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT_ID}" \
  --data-urlencode "text=${TEXT}" > /dev/null
