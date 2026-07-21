#!/bin/bash
# timi-cron.sh — Health monitor for timi pipeline services
# Called by cron every 5 minutes to ensure services are running.

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
cd /Users/Ai\ Mark/timi || exit 1

# 1. Docker container health
if ! docker ps --filter name=timi-pipeline --format "{{.Status}}" | grep -q "Up" 2>/dev/null; then
  echo "[cron] $(date): timi-pipeline container not running — restarting via docker compose"
  docker compose up -d >> /Users/Ai\ Mark/timi/logs/cron-restart.log 2>&1
fi

# 2. GitHub Actions runner health
RUNNER_SERVICE="actions.runner.legendarylaure-byte-timi.Saykars-MacBook-Pro"
if ! launchctl list | grep -q "$RUNNER_SERVICE.*0$"; then
  echo "[cron] $(date): GitHub Actions runner not running — restarting"
  cd /Users/saykar/actions-runner && ./run.sh &
fi

# 3. Dashboard health
if ! pgrep -f "node.*dashboard" > /dev/null 2>&1 && ! pgrep -f "next.*dev" > /dev/null 2>&1; then
  echo "[cron] $(date): Dashboard not running — restarting"
  cd /Users/Ai\ Mark/timi/dashboard && nohup npx next start -p 5001 > /tmp/dashboard.log 2>&1 &
fi

# 4. Disk cleanup (once daily at 4am)
HOUR=$(date +%H)
if [ "$HOUR" = "04" ]; then
  docker system prune -f >> /Users/Ai\ Mark/timi/logs/cron-cleanup.log 2>&1
  # Remove temp files older than 1 day
  find /Users/Ai\ Mark/timi/agents/tmp -name "*.mp4" -mtime +1 -delete 2>/dev/null
fi
