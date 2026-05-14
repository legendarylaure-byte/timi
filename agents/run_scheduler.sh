#!/bin/bash
# Run the Vyom Ai Cloud scheduler continuously.
# The scheduler runs daily content generation at 06:00 UTC,
# analytics pull at 08:00 UTC, revenue at 08:30, repurpose at 14:00,
# cleanup at 04:00, and publish checks every 15 minutes.

DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/scheduler.log"
PIDFILE="$DIR/scheduler.pid"
PYTHON="$DIR/.venv/bin/python"

case "${1:-start}" in
  start)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Scheduler already running (pid $(cat "$PIDFILE"))"
      exit 1
    fi
    PYTHONUNBUFFERED=1 nohup "$PYTHON" -u "$DIR/main.py" >> "$LOG" 2>&1 &
    PID=$!
    echo $PID > "$PIDFILE"
    echo "Scheduler started (pid $PID) — log: $LOG"
    ;;
  stop)
    if [ ! -f "$PIDFILE" ]; then
      echo "No pid file found"
      exit 1
    fi
    PID=$(cat "$PIDFILE")
    kill "$PID" 2>/dev/null && echo "Stopped scheduler (pid $PID)" || echo "Failed to stop pid $PID"
    rm -f "$PIDFILE"
    ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Scheduler running (pid $(cat "$PIDFILE"))"
    else
      echo "Scheduler not running"
    fi
    ;;
  log)
    tail -f "$LOG"
    ;;
  *)
    echo "Usage: $0 {start|stop|status|log}"
    exit 1
    ;;
esac
