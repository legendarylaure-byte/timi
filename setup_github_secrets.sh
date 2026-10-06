#!/bin/bash
# Setup GitHub Repository Secrets
# Run: bash setup_github_secrets.sh
# Requires: GitHub CLI (gh) authenticated

echo "=== Setting up GitHub Repository Secrets ==="
echo

# Check if gh is authenticated
if ! gh auth status 2>/dev/null; then
  echo "Please authenticate with GitHub CLI first:"
  echo "  gh auth login"
  exit 1
fi

# Get the repository
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Repository: $REPO"
echo

# Set each secret
set_secret() {
  local name=$1
  local value=$2
  echo "Setting secret: $name"
  gh secret set "$name" --body "$value" --repo "$REPO"
}

echo "Reading secrets from agents/.env and local files..."
echo

# Read from .env if exists
if [ -f "agents/.env" ]; then
  source agents/.env
  
  set_secret "PEXELS_API_KEY" "$PEXELS_API_KEY"
  set_secret "PIXABAY_API_KEY" "$PIXABAY_API_KEY"
  set_secret "YOUTUBE_CLIENT_ID" "$YOUTUBE_CLIENT_ID"
  set_secret "YOUTUBE_CLIENT_SECRET" "$YOUTUBE_CLIENT_SECRET"
  set_secret "FIREBASE_PROJECT_ID" "$FIREBASE_PROJECT_ID"
fi

# Firebase service account. Written RAW, not base64.
#
# Two readers disagreed about this one value: daily-content.yml writes it with
# `printf '%s'` (raw), while cleanup_videos.cjs/.mjs base64-decoded the SAME
# secret via its _KEY alias, so they could never both be right. Raw is what the
# live secret is today, and firebase-deploy.yml accepts either -- raw is the
# common denominator.
#
# The key is the repo-root copy because that is what docker-compose.yml mounts.
# The old agents/firebase/ path held a *different* private key for the same
# service account, so re-running this published a credential the running
# container never uses. And a missing key used to skip silently, so the script
# could report success having set nothing -- the "green job that published
# nothing" shape. Fail loudly instead.
SA_KEY="firebase/serviceAccountKey.json"
if [ ! -f "$SA_KEY" ]; then
  echo "ERROR: $SA_KEY not found, so FIREBASE_SERVICE_ACCOUNT would be left unset."
  echo "       Run this from the repo root, or correct SA_KEY above."
  exit 1
fi
echo "Setting secret: FIREBASE_SERVICE_ACCOUNT (raw JSON)"
gh secret set "FIREBASE_SERVICE_ACCOUNT" --body "$(cat "$SA_KEY")" --repo "$REPO"

SA_PROJECT=$(python3 -c "import json;print(json.load(open('$SA_KEY'))['project_id'])")
SA_EMAIL=$(python3 -c "import json;print(json.load(open('$SA_KEY'))['client_email'])")

# YouTube OAuth token
if [ -f "agents/youtube_token.json" ]; then
  echo "Setting secret: YOUTUBE_OAUTH_TOKEN (base64)"
  base64 -i "agents/youtube_token.json" | gh secret set "YOUTUBE_OAUTH_TOKEN" --repo "$REPO"
fi

echo
echo "=== Service account IAM (not in git) ==="
# firebase-deploy.yml authenticates as this service account, so its roles must
# exist in the PROJECT -- nothing in the repo records them. A project rebuild
# otherwise fails with `403 Permission denied to get service
# [firestore.googleapis.com]`, which reads like a credentials fault rather than
# a missing role.
#
# roles/firebaserules.admin alone is NOT enough: firebase-tools preflights
# serviceusage.services.get before it deploys anything. serviceUsageViewer is
# read-only -- it grants services.get/list and cannot enable or disable an API.
if ! command -v gcloud >/dev/null 2>&1; then
  echo "  SKIPPED: gcloud not on PATH. The deploy job will 403 until these roles"
  echo "           are bound by hand -- see AGENTS.md D50."
else
  for ROLE in roles/firebaserules.admin roles/serviceusage.serviceUsageViewer; do
    echo "  binding $ROLE"
    gcloud projects add-iam-policy-binding "$SA_PROJECT" \
      --member="serviceAccount:$SA_EMAIL" --role="$ROLE" --condition=None --quiet >/dev/null
  done
  echo "  roles now bound to $SA_EMAIL:"
  gcloud projects get-iam-policy "$SA_PROJECT" \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:$SA_EMAIL" \
    --format="value(bindings.role)" | sed 's/^/    /'
fi

echo
echo "=== All secrets set successfully ==="
echo
echo "Next steps:"
echo "1. Go to https://github.com/$REPO/settings/secrets/actions to verify"
echo "2. Test the workflow: gh workflow run daily-content.yml --ref main"
echo "3. View logs: gh run list --workflow daily-content.yml"
