#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_NAME="legendarylaure-byte/timi"
VERCEL_TOKEN="${VERCEL_TOKEN:-}"
VERCEL_PROJECT_ID="${VERCEL_PROJECT_ID:-prj_ALkaTWucBOWJkIpRsydJjtbyrUXC}"
VERCEL_TEAM_ID="${VERCEL_TEAM_ID:-team_METb2rXDBa5NqFCU1bb3mmNv}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $1"; }
header(){ echo -e "\n${BOLD}═══ $1 ═══${NC}\n"; }

prompt_yn() {
    read -r -p "$1 [y/N] " resp
    [[ "$resp" =~ ^[yY] ]]
}

vercel_api() {
    curl -sf -H "Authorization: Bearer $VERCEL_TOKEN" "https://api.vercel.com$1" ${2:+-X "$2"} ${3:+-d "$3"} -H "Content-Type: application/json"
}

github_api() {
    local token="$1"; shift
    curl -sf -H "Authorization: Bearer $token" -H "Accept: application/vnd.github.v3+json" "https://api.github.com$1" ${2:+-X "$2"} ${3:+-d "$3"}
}

add_vercel_env() {
    local key="$1" value="$2"
    vercel_api "/v10/projects/$VERCEL_PROJECT_ID/env" POST \
        "$(printf '{"key":"%s","value":"%s","target":["production"],"type":"encrypted"}' "$key" "$value")" > /dev/null 2>&1 && \
        ok "Vercel env $key set" || warn "Failed to set Vercel env $key"
}

GITHUB_TOKEN=""

# ──────────────────────────────────────
echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║       Timi — Full Setup Wizard          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

echo "Repo: $REPO_NAME ($REPO_DIR)"
echo ""

# Check required tokens
if [ -z "$VERCEL_TOKEN" ]; then
    warn "VERCEL_TOKEN not set. Some steps will be skipped."
    echo "  Export it:   export VERCEL_TOKEN='your_token'"
    echo "  Or get one:  npx vercel token --token <existing>"
    echo ""
    echo "  Steps that need it: Sentry DSN (Vercel env)"
    echo ""
fi

# ──────────────────────────────────────
header "Step 1 — Pipeline Auto-Restart Service"

if prompt_yn "Install pipeline as a background service (auto-restart on crash + boot)?"; then
    bash "$REPO_DIR/scripts/setup-pipeline-service.sh"
else
    info "Skipped. Run later: ./scripts/setup-pipeline-service.sh"
fi

# ──────────────────────────────────────
header "Step 2 — Sentry Error Tracking"

if prompt_yn "Set up Sentry error tracking?"; then
    echo ""
    echo "You need a Sentry DSN. Get one:"
    echo "  1. Go to https://sentry.io → Create Project → Next.js"
    echo "  2. Copy the DSN (https://xxx@xxx.ingest.sentry.io/xxx)"
    echo "  3. Paste it below"
    echo ""

    read -r -p "Sentry DSN (leave blank to skip): " SENTRY_DSN

    if [ -n "$SENTRY_DSN" ]; then
        add_vercel_env "SENTRY_DSN" "$SENTRY_DSN"
        add_vercel_env "NEXT_PUBLIC_SENTRY_DSN" "$SENTRY_DSN"

        if [ -n "$GITHUB_TOKEN" ]; then
            github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/SENTRY_DSN" PUT \
                "$(printf '{"encrypted_value":"%s","key_id":"%s"}' "$SENTRY_DSN" "$(github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/public-key" | python3 -c "import sys,json;print(json.load(sys.stdin)['key_id'])")")" > /dev/null 2>&1
            ok "SENTRY_DSN added to GitHub secrets"
        fi

        ok "Sentry DSN configured"
    else
        info "Skipped."
    fi
else
    info "Skipped."
fi

# ──────────────────────────────────────
header "Step 3 — Discord / Slack Notifications"

if prompt_yn "Set up CI failure notifications (Discord or Slack)?"; then
    echo ""
    echo "Create a webhook in your Discord server:"
    echo "  Server Settings → Integrations → Webhooks → New Webhook"
    echo "  Copy the URL and paste below."
    echo ""
    read -r -p "Discord Webhook URL (leave blank to skip): " DISCORD_URL

    if [ -n "$DISCORD_URL" ]; then
        if [ -n "$GITHUB_TOKEN" ]; then
            github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/DISCORD_WEBHOOK" PUT \
                "$(printf '{"encrypted_value":"%s","key_id":"%s"}' "$DISCORD_URL" "$(github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/public-key" | python3 -c "import sys,json;print(json.load(sys.stdin)['key_id'])")")" > /dev/null 2>&1
            ok "DISCORD_WEBHOOK added to GitHub secrets"
        else
            warn "GitHub token not set. Add DISCORD_WEBHOOK manually:"
            echo "  https://github.com/$REPO_NAME/settings/secrets/actions"
        fi
    else
        info "Skipped."
    fi

    echo ""
    read -r -p "Slack Webhook URL (leave blank to skip): " SLACK_URL
    if [ -n "$SLACK_URL" ]; then
        if [ -n "$GITHUB_TOKEN" ]; then
            github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/SLACK_WEBHOOK" PUT \
                "$(printf '{"encrypted_value":"%s","key_id":"%s"}' "$SLACK_URL" "$(github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/public-key" | python3 -c "import sys,json;print(json.load(sys.stdin)['key_id'])")")" > /dev/null 2>&1
            ok "SLACK_WEBHOOK added to GitHub secrets"
        else
            warn "GitHub token not set. Add SLACK_WEBHOOK manually:"
            echo "  https://github.com/$REPO_NAME/settings/secrets/actions"
        fi
    fi
else
    info "Skipped."
fi

# ──────────────────────────────────────
header "Step 4 — Firebase Token (for Auto-Index Deploy)"

if prompt_yn "Generate Firebase CI token for auto-deploying indexes?"; then
    echo ""
    info "This will open your browser to authenticate with Firebase."
    echo "After login, a token will be displayed. Copy and paste it below."
    echo ""
    read -r -p "Press Enter to open Firebase login (in browser)..."

    if command -v npx &>/dev/null; then
        npx firebase-tools login:ci --project timi-childern-stories 2>&1 | tee /tmp/firebase_login_output.txt
        FIREBASE_TOKEN_RAW=$(grep -oP '1//[0-9a-zA-Z_-]+' /tmp/firebase_login_output.txt | head -1 || true)
        rm -f /tmp/firebase_login_output.txt

        if [ -n "$FIREBASE_TOKEN_RAW" ]; then
            ok "Firebase CI token obtained"

            if [ -n "$GITHUB_TOKEN" ]; then
                github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/FIREBASE_TOKEN" PUT \
                    "$(printf '{"encrypted_value":"%s","key_id":"%s"}' "$FIREBASE_TOKEN_RAW" "$(github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets/public-key" | python3 -c "import sys,json;print(json.load(sys.stdin)['key_id'])")")" > /dev/null 2>&1
                ok "FIREBASE_TOKEN added to GitHub secrets"
            else
                warn "GitHub token not set. Add FIREBASE_TOKEN manually:"
                echo "  https://github.com/$REPO_NAME/settings/secrets/actions"
            fi
        else
            warn "Could not extract token. Add it manually:"
            echo "  https://github.com/$REPO_NAME/settings/secrets/actions"
            echo "  Secret name: FIREBASE_TOKEN"
            echo "  Value from:  firebase login:ci"
        fi
    else
        warn "npx not found. Install Node.js first."
    fi
else
    info "Skipped."
fi

# ──────────────────────────────────────
header "Step 5 — Final Checks"

echo ""
echo "=== Vercel Env Vars ==="
for key in SENTRY_DSN NEXT_PUBLIC_SENTRY_DSN; do
    result=$(vercel_api "/v9/projects/$VERCEL_PROJECT_ID/env?decrypt=true" | \
        python3 -c "import sys,json;d=json.load(sys.stdin);found=[e for e in d.get('envs',[]) if e['key']=='$key' and 'production' in e.get('target',[])];print('YES' if found else 'NO')" 2>/dev/null || echo "?")
    echo "  $key → $result"
done

echo ""
echo "=== GitHub Secrets ==="
if [ -n "$GITHUB_TOKEN" ]; then
    secrets=$(github_api "$GITHUB_TOKEN" "/repos/$REPO_NAME/actions/secrets")
    for name in SENTRY_DSN DISCORD_WEBHOOK SLACK_WEBHOOK FIREBASE_TOKEN; do
        present=$(echo "$secrets" | python3 -c "import sys,json;d=json.load(sys.stdin);print('YES' if any(s['name']=='$name' for s in d.get('secrets',[])) else 'NO')" 2>/dev/null || echo "?")
        echo "  $name → $present"
    done
else
    echo "  (set GITHUB_TOKEN to check)"
fi

echo ""
echo "=== Pipeline Service ==="
if launchctl list com.timi.pipeline &>/dev/null 2>&1; then
    echo "  ✅ Running"
elif systemctl is-active timi-pipeline &>/dev/null 2>&1; then
    echo "  ✅ Running"
else
    echo "  ⚠️  Not detected (may start on next boot)"
fi

echo ""
echo -e "${GREEN}${BOLD}Setup complete!${NC}"
echo "Run verifications:"
echo "  curl https://timi.vyomai.cloud/api/health"
echo "  tail -f /tmp/timi_pipeline.log"
