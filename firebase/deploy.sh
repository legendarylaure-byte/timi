#!/usr/bin/env bash
set -euo pipefail

echo "=== Firestore Rules & Indexes Deploy ==="
echo ""
echo "Prerequisites:"
echo "  1. npm install -g firebase-tools"
echo "  2. firebase login"
echo ""

# Run from the repo root: firebase.json (the ONE config both this script and CI
# read) lives there. This used to cd into firebase/, which silently picked up a
# second, relative-path copy of the config -- two sources of truth for the same
# deploy, which is how CI once shipped indexes with no rules.
cd "$(dirname "$0")/.."

echo "Deploying Firestore rules..."
npx firebase-tools deploy --only firestore:rules --project timi-childern-stories

echo ""
echo "Deploying Firestore indexes..."
npx firebase-tools deploy --only firestore:indexes --project timi-childern-stories

echo ""
echo "Done! Verify at Firebase Console."
