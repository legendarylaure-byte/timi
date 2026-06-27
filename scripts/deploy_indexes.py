#!/usr/bin/env python3
"""
Firestore Index Deployment Tool

Deploy composite indexes defined in firestore.indexes.json to Firebase.
Uses the Firebase Admin SDK service account (read-only listing) or FIREBASE_TOKEN.

Usage:
  python3 scripts/deploy_indexes.py          # List + print Console URLs
  python3 scripts/deploy_indexes.py --deploy  # Create indexes (needs FIREBASE_TOKEN or gcloud auth)

Environment:
  FIREBASE_TOKEN    Firebase CI token for deployment
  GOOGLE_APPLICATION_CREDENTIALS  Service account key path
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse

PROJECT = "timi-childern-stories"
API_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/collectionGroups"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, "..", "firestore.indexes.json")
FIREBASE_CONSOLE = "https://console.firebase.google.com/project/timi-childern-stories/firestore/indexes"


def get_token():
    token = os.getenv("FIREBASE_TOKEN")
    if token:
        return token, "firebase_token"
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip(), "gcloud"
    except FileNotFoundError:
        pass
    return None, None


def get_existing_indexes(token):
    import requests
    indexes = {}
    url = f"{API_BASE}/-/indexes"
    while url:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 403:
            print("  ⚠️  No permission to list indexes (403)")
            return indexes, False
        if resp.status_code != 200:
            print(f"  ⚠️  Failed to list: {resp.status_code}")
            return indexes, False
        data = resp.json()
        for idx in data.get("indexes", []):
            col = idx.get("collectionGroup", "?")
            indexes.setdefault(col, []).append(idx)
        url = data.get("nextPageToken")
    return indexes, True


def index_matches(desired, existing):
    if existing.get("queryScope", "COLLECTION") != desired.get("queryScope", "COLLECTION"):
        return False
    ef = [(f["fieldPath"], f.get("order", ""), f.get("arrayConfig", ""))
          for f in existing.get("fields", []) if f.get("fieldPath") != "__name__"]
    df = [(f["fieldPath"], f.get("order", ""), f.get("arrayConfig", ""))
          for f in desired["fields"]]
    return ef == df


def create_index(token, col, idx_def):
    import requests
    body = {
        "queryScope": idx_def.get("queryScope", "COLLECTION"),
        "fields": idx_def["fields"],
    }
    resp = requests.post(
        f"{API_BASE}/{col}/indexes",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.status_code, resp.text[:200]


def console_url_for_index(col, idx_def):
    """Generate Firebase Console URL to create this index."""
    fields = idx_def.get("fields", [])
    params = {"createIndex": json.dumps({
        "collectionGroup": col,
        "fieldPaths": [f["fieldPath"] for f in fields],
        "fieldOrders": [f.get("order", "") for f in fields],
        "fieldArrayConfigs": [f.get("arrayConfig", "") for f in fields],
        "queryScope": idx_def.get("queryScope", "COLLECTION"),
    })}
    return f"{FIREBASE_CONSOLE}?{urllib.parse.urlencode(params)}"


def main():
    do_deploy = "--deploy" in sys.argv

    if not os.path.exists(INDEX_FILE):
        print(f"ERROR: Index file not found: {INDEX_FILE}")
        return 1

    with open(INDEX_FILE) as f:
        spec = json.load(f)
    desired = spec.get("indexes", [])

    print(f"Project: {PROJECT}")
    print(f"Desired indexes: {len(desired)}")
    print(f"Index file: {INDEX_FILE}")
    print()

    # Get token
    token, token_source = get_token()
    if token:
        print(f"Auth source: {token_source}")
    else:
        print("No auth token available — listing only")
    print()

    # List existing indexes
    existing = {}
    had_permission = False
    if token:
        existing, had_permission = get_existing_indexes(token)
        total = sum(len(v) for v in existing.values())
        print(f"Existing indexes in Firestore: {total}")
        if total > 0:
            for col, idxs in sorted(existing.items()):
                print(f"  {col}: {len(idxs)} index(es)")
        print()
    else:
        print("Cannot check existing indexes (no auth)")
        print()

    # Show status for each desired index
    missing = []
    print("Desired indexes:")
    print(f"{'Collection':<25} {'Fields':<50} {'Status'}")
    print("-" * 85)
    for idx in desired:
        col = idx.get("collectionGroup", "?")
        fields_desc = ", ".join(
            f"{f['fieldPath']}({f.get('order','') or f.get('arrayConfig','')})"
            for f in idx.get("fields", [])
        )
        col_existing = existing.get(col, [])
        found = any(index_matches(idx, ex) for ex in col_existing)

        if found:
            print(f"{col:<25} {fields_desc:<50} ✅ Exists")
        elif not had_permission:
            print(f"{col:<25} {fields_desc:<50} ❓ Unknown (no perms)")
            missing.append((col, idx))
        else:
            print(f"{col:<25} {fields_desc:<50} ❌ Missing")
            missing.append((col, idx))

    print()

    # Create missing indexes
    if do_deploy and missing and token:
        print(f"Creating {len(missing)} missing indexes...")
        created = 0
        skipped = 0
        failed = 0
        for col, idx_def in missing:
            status, detail = create_index(token, col, idx_def)
            if status == 200:
                created += 1
                print(f"  ✅ {col}: created")
            elif status == 409:
                skipped += 1
                print(f"  ⏭️  {col}: already exists")
            else:
                failed += 1
                print(f"  ❌ {col}: {detail}")
            time.sleep(0.5)
        print(f"\nCreated: {created}, Skipped: {skipped}, Failed: {failed}")
        if failed > 0:
            print("\nTo create indexes manually, go to Firebase Console:")
            for col, idx_def in missing:
                print(f"  {console_url_for_index(col, idx_def)}")
    elif missing:
        print(f"To create missing indexes:")
        print(f"  1. Open Firebase Console:")
        print(f"     {FIREBASE_CONSOLE}")
        for col, idx_def in missing:
            fields = ", ".join(f["fieldPath"] for f in idx_def.get("fields", []))
            print(f"     → Create index for {col}: {fields}")
        print()
        print("  2. Or run: python3 scripts/deploy_indexes.py --deploy")
        print("     (with FIREBASE_TOKEN set or gcloud authenticated)")
    else:
        print("All indexes are up to date.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
