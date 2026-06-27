#!/bin/bash
set -e

cd "$(dirname "$0")"

MAX_RETRIES=5
RETRY_DELAY=10
HEALTH_URL="http://localhost:8080/health"
PID_FILE="/tmp/timi_pipeline.pid"

cleanup() {
    echo "[WRAPPER] Shutting down..."
    if [ -f "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    exit 0
}
trap cleanup SIGTERM SIGINT

echo "[WRAPPER] Starting timi pipeline..."
echo "$$" > "$PID_FILE"

retries=0
while [ $retries -lt $MAX_RETRIES ]; do
    echo "[WRAPPER] Launching main.py (attempt $((retries + 1))/$MAX_RETRIES)..."
    python3 main.py &
    PIPELINE_PID=$!
    echo "$PIPELINE_PID" > "$PID_FILE"

    wait $PIPELINE_PID
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "[WRAPPER] Pipeline exited cleanly (code 0). No restart needed."
        cleanup
    fi

    echo "[WRAPPER] Pipeline crashed with code $EXIT_CODE. Restarting in ${RETRY_DELAY}s..."
    retries=$((retries + 1))
    sleep $RETRY_DELAY
done

echo "[WRAPPER] Max retries ($MAX_RETRIES) reached. Giving up."
exit 1
