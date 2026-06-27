#!/bin/bash
# Setup script for pipeline auto-restart service
# Usage:
#   macOS (launchd):  ./scripts/setup-pipeline-service.sh launchd
#   Linux (systemd):  ./scripts/setup-pipeline-service.sh systemd

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$SCRIPT_DIR/agents"

install_launchd() {
    PLIST_SRC="$INSTALL_DIR/com.timi.pipeline.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.timi.pipeline.plist"

    if [ ! -f "$PLIST_SRC" ]; then
        echo "ERROR: $PLIST_SRC not found"
        exit 1
    fi

    # Fix the path in the plist to point to actual install location
    sed "s|/path/to/timi/agents|$INSTALL_DIR|g" "$PLIST_SRC" > "$PLIST_DST"

    # Unload if already loaded
    launchctl unload "$PLIST_DST" 2>/dev/null || true

    # Load the service (auto-starts on boot)
    launchctl load "$PLIST_DST"

    echo "✅ launchd service installed at $PLIST_DST"
    echo "   Start manually: launchctl start com.timi.pipeline"
    echo "   Check status:   launchctl list com.timi.pipeline"
    echo "   Stop:           launchctl stop com.timi.pipeline"
    echo "   Logs:           tail -f /tmp/timi_pipeline.log"
}

install_systemd() {
    SERVICE_SRC="$INSTALL_DIR/timi-pipeline.service"
    SERVICE_DST="/etc/systemd/system/timi-pipeline.service"

    # Create systemd service file
    cat > "$SERVICE_SRC" << EOF
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
StandardOutput=append:/tmp/timi_pipeline.log
StandardError=append:/tmp/timi_pipeline_err.log

[Install]
WantedBy=multi-user.target
EOF

    sudo cp "$SERVICE_SRC" "$SERVICE_DST"
    sudo systemctl daemon-reload
    sudo systemctl enable timi-pipeline
    sudo systemctl start timi-pipeline

    echo "✅ systemd service installed at $SERVICE_DST"
    echo "   Status: sudo systemctl status timi-pipeline"
    echo "   Logs:   journalctl -u timi-pipeline -f"
}

case "${1:-launchd}" in
    launchd) install_launchd ;;
    systemd) install_systemd ;;
    *)
        echo "Usage: $0 [launchd|systemd]"
        exit 1
        ;;
esac
