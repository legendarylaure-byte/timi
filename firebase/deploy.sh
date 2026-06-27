#!/usr/bin/env bash
set -euo pipefail

echo "=== Firestore Rules & Indexes Deploy ==="
echo ""
echo "Prerequisites:"
echo "  1. npm install -g firebase-tools"
echo "  2. firebase login"
echo ""

cd "$(dirname "$0")"

echo "Deploying Firestore rules..."
npx firebase-tools deploy --only firestore:rules --project timi-childern-stories

echo ""
echo "Deploying Firestore indexes..."
npx firebase-tools deploy --only firestore:indexes --project timi-childern-stories

echo ""
echo "Done! Verify at Firebase Console."
