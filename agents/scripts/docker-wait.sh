#!/bin/bash
# Wait for Docker Desktop to be ready, then start docker-compose services.
# This handles the boot-order issue: launchd runs before Login Items,
# so Docker Desktop isn't running when this fires at login.
#
# launchd has minimal PATH (/usr/bin:/bin), so we set it explicitly.

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

DOCKER="/usr/local/bin/docker"
COMPOSE="/usr/local/bin/docker compose"
MAX_RETRIES=30
RETRY_INTERVAL=5
PROJECT_DIR="/Users/Ai Mark/timi"

echo "[docker-wait] Waiting for Docker daemon..."

for i in $(seq 1 $MAX_RETRIES); do
  if $DOCKER info >/dev/null 2>&1; then
    echo "[docker-wait] Docker ready after ~$((i * RETRY_INTERVAL))s"
    break
  fi
  if [ "$i" -eq "$MAX_RETRIES" ]; then
    echo "[docker-wait] Timed out after $((MAX_RETRIES * RETRY_INTERVAL))s — Docker not available"
    exit 1
  fi
  sleep $RETRY_INTERVAL
done

cd "$PROJECT_DIR" || { echo "[docker-wait] Failed to cd to $PROJECT_DIR"; exit 1; }

echo "[docker-wait] Starting docker compose services..."
$DOCKER compose up -d

echo "[docker-wait] All services started"
