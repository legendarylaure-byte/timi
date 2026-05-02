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
  
  set_secret "GROQ_API_KEY" "$GROQ_API_KEY"
  set_secret "GROQ_MODEL" "${GROQ_MODEL:-llama-3.3-70b-versatile}"
  set_secret "PEXELS_API_KEY" "$PEXELS_API_KEY"
  set_secret "PIXABAY_API_KEY" "$PIXABAY_API_KEY"
  set_secret "YOUTUBE_CLIENT_ID" "$YOUTUBE_CLIENT_ID"
  set_secret "YOUTUBE_CLIENT_SECRET" "$YOUTUBE_CLIENT_SECRET"
  set_secret "FIREBASE_PROJECT_ID" "$FIREBASE_PROJECT_ID"
fi

# Firebase service account (base64 encoded to preserve formatting)
if [ -f "agents/firebase/serviceAccountKey.json" ]; then
  echo "Setting secret: FIREBASE_SERVICE_ACCOUNT (base64)"
  base64 -i "agents/firebase/serviceAccountKey.json" | gh secret set "FIREBASE_SERVICE_ACCOUNT" --repo "$REPO"
fi

# YouTube OAuth token
if [ -f "agents/youtube_token.json" ]; then
  echo "Setting secret: YOUTUBE_OAUTH_TOKEN (base64)"
  base64 -i "agents/youtube_token.json" | gh secret set "YOUTUBE_OAUTH_TOKEN" --repo "$REPO"
fi

echo
echo "=== All secrets set successfully ==="
echo
echo "Next steps:"
echo "1. Go to https://github.com/$REPO/settings/secrets/actions to verify"
echo "2. Test the workflow: gh workflow run daily-content.yml --ref main"
echo "3. View logs: gh run list --workflow daily-content.yml"
