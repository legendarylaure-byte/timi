#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$REPO_DIR/agents"
PLIST_SRC="$INSTALL_DIR/com.timi.pipeline.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.timi.pipeline.plist"
LOG_FILE="/tmp/timi_pipeline.log"
ERR_FILE="/tmp/timi_pipeline_err.log"

detect_platform() {
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "macos"
    elif [[ -f /etc/os-release ]] && grep -qi ubuntu /etc/os-release 2>/dev/null; then
        echo "linux"
    else
        echo "unknown"
    fi
}

install_macos() {
    echo ">>> Installing pipeline service for macOS..."

    mkdir -p "$HOME/Library/LaunchAgents"

    python3 -c "
import re
with open('$PLIST_SRC') as f:
    content = f.read()
content = content.replace('/path/to/timi/agents', '$INSTALL_DIR')
with open('$PLIST_DST', 'w') as f:
    f.write(content)
"

    launchctl unload "$PLIST_DST" 2>/dev/null || true
    launchctl load "$PLIST_DST"

    echo ""
    echo "✅ Service installed at $PLIST_DST"
    echo "   Start:    launchctl start com.timi.pipeline"
    echo "   Stop:     launchctl stop com.timi.pipeline"
    echo "   Status:   launchctl list com.timi.pipeline"
    echo "   Logs:     tail -f $LOG_FILE"
}

install_linux() {
    echo ">>> Installing pipeline service for Linux (systemd)..."
    SERVICE_DST="/etc/systemd/system/timi-pipeline.service"

    sudo tee "$SERVICE_DST" > /dev/null << EOF
[Unit]
Description=Timi AI Video Pipeline
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/run_pipeline.sh
Restart=always
RestartSec=10
StandardOutput=append:$LOG_FILE
StandardError=append:$ERR_FILE

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable timi-pipeline
    sudo systemctl start timi-pipeline

    echo ""
    echo "✅ Service installed at $SERVICE_DST"
    echo "   Status: sudo systemctl status timi-pipeline"
    echo "   Logs:   journalctl -u timi-pipeline -f"
}

# ── main ──
PLATFORM=$(detect_platform)
echo "=== Timi Pipeline Service Setup ==="
echo "Platform: $PLATFORM"
echo "Repo:     $REPO_DIR"
echo ""

case "$PLATFORM" in
    macos) install_macos ;;
    linux) install_linux ;;
    *)
        echo "Unsupported platform: $PLATFORM"
        echo "Create a systemd/launchd service manually using:"
        echo "  $PLIST_SRC"
        exit 1
        ;;
esac

# Verify
echo ""
echo ">>> Verifying..."
sleep 2
if launchctl list com.timi.pipeline &>/dev/null 2>&1 || systemctl is-active timi-pipeline &>/dev/null 2>&1; then
    echo "✅ Pipeline service is running!"
else
    echo "⚠️  Service may not be running. Check logs: tail -f $LOG_FILE"
fi
