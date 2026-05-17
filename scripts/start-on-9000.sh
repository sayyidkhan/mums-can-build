#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-9000}"
APP_DIR="${APP_DIR:-.}"
START_CMD="${START_CMD:-npm start}"
LOG_FILE="${LOG_FILE:-/tmp/mcb-app-${PORT}.log}"

echo "Checking for existing process on port ${PORT}..."
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti tcp:${PORT} || true)"
  if [[ -n "${PIDS}" ]]; then
    echo "Stopping existing process(es): ${PIDS}"
    kill ${PIDS} || true
    sleep 1
    REMAINING="$(lsof -ti tcp:${PORT} || true)"
    if [[ -n "${REMAINING}" ]]; then
      echo "Force stopping process(es): ${REMAINING}"
      kill -9 ${REMAINING} || true
    fi
  fi
else
  echo "lsof not found. Skipping pre-stop check."
fi

echo "Starting app in ${APP_DIR} on port ${PORT}..."
(
  cd "${APP_DIR}"
  nohup env PORT="${PORT}" bash -lc "${START_CMD}" >"${LOG_FILE}" 2>&1 &
  echo $! >"/tmp/mcb-app-${PORT}.pid"
)

sleep 1
echo "Started. PID: $(cat /tmp/mcb-app-${PORT}.pid)"
echo "Log file: ${LOG_FILE}"
echo "Check URL: http://127.0.0.1:${PORT}"
