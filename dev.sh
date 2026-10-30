#!/usr/bin/env bash
# Starts the EquiCrew website and the contact API together for development.
# Ctrl-C stops both.
#
#   ./dev.sh                         website http://localhost:8080, API http://127.0.0.1:8000
#   WEB_PORT=3000 API_PORT=9000 ./dev.sh
#
# SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM and CONTACT_TO are taken
# from the calling environment; without them the API starts and the form answers 503.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
WEB_PORT="${WEB_PORT:-8080}"
API_PORT="${API_PORT:-8000}"

api_pid=""
web_pid=""

cleanup() {
  trap - INT TERM EXIT
  for pid in "$api_pid" "$web_pid"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(
  cd "$ROOT/backend"
  CORS_ORIGIN="http://localhost:${WEB_PORT}" exec "$PYTHON" -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$API_PORT" --no-access-log
) &
api_pid=$!

PORT="$WEB_PORT" API_BASE_URL="http://127.0.0.1:${API_PORT}" \
  node "$ROOT/frontend/dev_server.mjs" &
web_pid=$!

echo "Website: http://localhost:${WEB_PORT}/   API: http://127.0.0.1:${API_PORT}/api/health"
echo "Ctrl-C stops both."

# Stop everything as soon as one of the two exits (or Ctrl-C arrives).
wait -n "$api_pid" "$web_pid" || true
