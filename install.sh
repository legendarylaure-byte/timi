#!/bin/bash
# One-time Mac setup for LTX-2.3 MLX + self-hosted GitHub runner
# Run: bash install.sh
# Requires: macOS 14+, Apple Silicon, 60GB+ free, Admin password for some steps

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
err()   { echo -e "${RED}✗${NC} $1"; }

REPO="legendarylaure-byte/timi"
WORK_DIR="$HOME/timi-runner"
LTX_MODEL_DIR="$HOME/ltx-models"
PYTHON_MIN="3.11"

echo "==========================================="
echo "  Timi Mac Setup — LTX-2.3 MLX + Runner"
echo "==========================================="
echo ""

# --- Step 1: Check prerequisites ---
echo "--- Step 1/8: Checking prerequisites ---"

OS=$(uname)
if [[ "$OS" != "Darwin" ]]; then
    err "This script is for macOS only (detected: $OS)"
    exit 1
fi

ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    err "Apple Silicon required (detected: $ARCH)"
    exit 1
fi
log "Apple Silicon Mac ($ARCH)"

if ! command -v brew &>/dev/null; then
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
log "Homebrew installed"

if ! command -v python3 &>/dev/null; then
    warn "Python 3 not found. Installing via Homebrew..."
    brew install python@3.11
fi
PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
log "Python $PY_VER"

if ! command -v ffmpeg &>/dev/null; then
    warn "FFmpeg not found. Installing..."
    brew install ffmpeg
fi
log "FFmpeg installed"

if ! command -v git &>/dev/null; then
    warn "Git not found. Installing..."
    brew install git
fi
log "Git installed"

if ! command -v gh &>/dev/null; then
    warn "GitHub CLI not found. Installing..."
    brew install gh
fi
log "GitHub CLI installed"

# --- Step 2: Authenticate with GitHub ---
echo ""
echo "--- Step 2/8: GitHub authentication ---"
if ! gh auth status 2>/dev/null; then
    echo "Please authenticate with GitHub:"
    gh auth login --with-token || gh auth login
fi
log "GitHub authenticated"

# --- Step 3: Clone/update repo ---
echo ""
echo "--- Step 3/8: Setting up workspace ---"
mkdir -p "$WORK_DIR"
if [[ -d "$WORK_DIR/.git" ]]; then
    warn "Workspace exists, updating..."
    cd "$WORK_DIR" && git pull
else
    git clone "https://github.com/$REPO.git" "$WORK_DIR"
fi
log "Repo at $WORK_DIR"

# --- Step 4: Set up Python venv ---
echo ""
echo "--- Step 4/8: Python virtual environment ---"
cd "$WORK_DIR/agents"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip uv
uv pip install -r requirements.txt
log "Dependencies installed"

# --- Step 5: Install MLX + LTX ---
echo ""
echo "--- Step 5/8: Installing MLX and LTX ---"
uv pip install mlx mlx-lm huggingface_hub numpy
uv pip install git+https://github.com/appautomaton/ltx-video-mlx.git 2>/dev/null || {
    warn "ltx-video-mlx not found, trying dgrauet/ltx-2-mlx..."
    uv pip install git+https://github.com/dgrauet/ltx-2-mlx.git#subdirectory=ltx-core-mlx
    uv pip install git+https://github.com/dgrauet/ltx-2-mlx.git#subdirectory=ltx-pipelines-mlx
}
log "MLX/LTX installed"

# --- Step 6: Download model weights ---
echo ""
echo "--- Step 6/8: Downloading LTX-2.3 model weights ---"
mkdir -p "$LTX_MODEL_DIR"

download_model() {
    local repo=$1
    local dir=$2
    if [[ -d "$dir" ]] && [[ -n "$(ls -A "$dir" 2>/dev/null)" ]]; then
        log "Model already downloaded: $repo → $dir ($(du -sh "$dir" | cut -f1))"
        return 0
    fi
    echo "  Downloading $repo (this may take a while)..."
    huggingface-cli download "$repo" --local-dir "$dir" 2>&1 | tail -3
}

# Try int4 quantized first (fits 16GB)
download_model "dgrauet/ltx-2.3-mlx-q4" "$LTX_MODEL_DIR" || {
    warn "int4 download failed, trying appautomaton variant..."
    download_model "appautomaton/ltx-video-mlx-q4" "$LTX_MODEL_DIR"
}

# Download Gemma 3 12B text encoder
GEMMA_DIR="$HOME/ltx-models/gemma-3-12b"
download_model "google/gemma-3-12b-pt" "$GEMMA_DIR" || {
    warn "Gemma download skipped (will download on first run)"
}

log "Model weights ready"

# --- Step 7: Verify LTX generation ---
echo ""
echo "--- Step 7/8: Testing LTX generation ---"
cd "$WORK_DIR/agents"
TEST_OUTPUT="$WORK_DIR/test_ltx_clip.mp4"
python3 -c "
from utils.ltx_engine import generate_clip
result = generate_clip(prompt='neural network with glowing nodes', duration=5, output_path='$TEST_OUTPUT')
if result:
    import os
    size = os.path.getsize(result)
    print(f'SUCCESS: Generated {size//1024//1024}MB clip at {result}')
else:
    print('FAILED: LTX generation returned None')
    exit(1)
" && log "LTX test passed" || warn "LTX test failed — check logs above"

# --- Step 8: Install GitHub Actions runner ---
echo ""
echo "--- Step 8/8: Installing GitHub self-hosted runner ---"
RUNNER_DIR="$HOME/actions-runner"
if [[ -d "$RUNNER_DIR" ]]; then
    log "Runner already installed at $RUNNER_DIR"
else
    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"
    RUNNER_VERSION="2.322.0"
    curl -o actions-runner.tar.gz -L \
        "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-osx-arm64-${RUNNER_VERSION}.tar.gz"
    tar xzf actions-runner.tar.gz
    rm actions-runner.tar.gz

    echo ""
    echo "=== Runner Configuration ==="
    echo "Go to: https://github.com/$REPO/settings/actions/runners/new"
    echo "Select: New self-hosted runner → macOS → ARM64"
    echo "Copy the registration token and run:"
    echo ""
    echo "  cd $RUNNER_DIR"
    echo "  ./config.sh --url https://github.com/$REPO --token YOUR_TOKEN --labels mac,m5"
    echo "  ./svc.sh install"
    echo "  ./svc.sh start"
    echo ""
    echo "After registration, the runner will auto-start on login."
fi

echo ""
echo "=========================================="
echo "  Setup Complete"
echo "=========================================="
echo ""
echo "Model directory:  $LTX_MODEL_DIR"
echo "Workspace:       $WORK_DIR"
echo "Runner:          $RUNNER_DIR"
echo ""
echo "To verify runner is connected:"
echo "  gh run list --workflow daily-content.yml"
echo ""
echo "To manually trigger a test video:"
echo "  gh workflow run daily-content.yml --field format=shorts --field topic='AI explained: transformers'"
echo ""
log "Your Mac is ready. Videos will generate automatically when CI triggers."
