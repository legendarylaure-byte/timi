#!/usr/bin/env python3
"""
Firestore Index Deployment Tool

Deploys composite indexes using the Firestore Admin API.
Uses the Firebase Admin SDK service account key for auth.

Usage:
  python3 scripts/deploy_indexes.py           # Check status
  python3 scripts/deploy_indexes.py --deploy   # Create missing indexes
"""
import json
import os
import sys
import time

from google.api_core.exceptions import AlreadyExists, PermissionDenied
from google.cloud.firestore_admin_v1 import FirestoreAdminClient
from google.cloud.firestore_admin_v1.types import Index
from google.oauth2 import service_account

PROJECT = "timi-childern-stories"
DATABASE = "(default)"
PARENT_TEMPLATE = f"projects/{PROJECT}/databases/{DATABASE}/collectionGroups"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, "..", "firestore.indexes.json")


def get_client():
    key_paths = [
        os.path.join(SCRIPT_DIR, "..", "firebase",
                      "Live_timi-childern-stories-firebase-adminsdk-fbsvc-44c82d711e.json"),
        os.path.join(SCRIPT_DIR, "..", "firebase", "serviceAccountKey.json"),
    ]
    for path in key_paths:
        path = os.path.normpath(path)
        if os.path.exists(path):
            creds = service_account.Credentials.from_service_account_file(
                path,
                scopes=["https://www.googleapis.com/auth/datastore"],
            )
            return FirestoreAdminClient(credentials=creds)

    # Fall back to default creds
    return FirestoreAdminClient()


def get_existing_indexes(client):
    """Fetch all existing composite indexes from Firestore."""
    indexes = {}
    try:
        # List all collection groups
        for idx in client.list_indexes(parent=f"{PARENT_TEMPLATE}/-"):
            # Extract collection group from the index name
            # name format: projects/.../collectionGroups/{col}/indexes/{idx}
            parts = idx.name.split("/")
            col = parts[parts.index("collectionGroups") + 1] if "collectionGroups" in parts else "?"
            indexes.setdefault(col, []).append(idx)
    except PermissionDenied:
        print("  ⚠️  No permission to list indexes")
        return indexes
    return indexes


def _scope_name(val):
    """Convert QueryScope enum value to string name."""
    for v in Index.QueryScope:
        if v.value == val:
            return v.name
    return "COLLECTION"


def _order_name(val):
    """Convert Order enum value to string name. Return '' for UNSPECIFIED."""
    for v in Index.IndexField.Order:
        if v.value == val:
            return "" if "UNSPECIFIED" in v.name else v.name
    return ""


def _array_config_name(val):
    """Convert ArrayConfig enum value to string name. Return '' for UNSPECIFIED."""
    for v in Index.IndexField.ArrayConfig:
        if v.value == val:
            return "" if "UNSPECIFIED" in v.name else v.name
    return ""


def index_matches(desired, existing):
    """Check if an existing Index proto matches a desired index dict."""
    existing_scope = _scope_name(existing.query_scope)
    desired_scope = desired.get("queryScope", "COLLECTION")
    if existing_scope != desired_scope:
        return False

    existing_fields = []
    for f in existing.fields:
        if f.field_path == "__name__":
            continue
        order = _order_name(f.order)
        array_config = _array_config_name(f.array_config)
        existing_fields.append((f.field_path, order, array_config))

    desired_fields = [
        (f["fieldPath"], f.get("order", ""), f.get("arrayConfig", ""))
        for f in desired["fields"]
    ]
    return existing_fields == desired_fields


def build_index_proto(idx_def):
    """Build an Index proto from a dict definition."""
    fields = []
    Order = Index.IndexField.Order
    ArrayConfig = Index.IndexField.ArrayConfig
    for f in idx_def["fields"]:
        field = Index.IndexField(field_path=f["fieldPath"])
        if "order" in f and f["order"]:
            field.order = Order.ASCENDING if f["order"] == "ASCENDING" else Order.DESCENDING
        if "arrayConfig" in f and f["arrayConfig"]:
            field.array_config = ArrayConfig.CONTAINS if f["arrayConfig"] == "CONTAINS" else ArrayConfig.CONTAINS
        fields.append(field)

    scope_enum = Index.QueryScope.COLLECTION if idx_def.get("queryScope", "COLLECTION") == "COLLECTION" else Index.QueryScope.COLLECTION_GROUP
    return Index(fields=fields, query_scope=scope_enum)


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
    print()

    print("Connecting to Firestore Admin API...")
    client = get_client()
    existing = get_existing_indexes(client)
    total_existing = sum(len(v) for v in existing.values())
    print(f"Existing indexes: {total_existing}")
    print()

    # Show status
    missing = []
    print(f"{'Collection':<25} {'Fields':<55} {'Status'}")
    print("-" * 90)
    for idx in desired:
        col = idx.get("collectionGroup", "?")
        fields_desc = ", ".join(
            f"{f['fieldPath']}({f.get('order','') or f.get('arrayConfig','')})"
            for f in idx.get("fields", [])
        )
        col_existing = existing.get(col, [])
        found = any(index_matches(idx, ex) for ex in col_existing)
        if found:
            print(f"{col:<25} {fields_desc:<55} ✅ Exists")
        else:
            print(f"{col:<25} {fields_desc:<55} ❌ Missing")
            missing.append((col, idx))
    print()

    # Deploy missing
    if do_deploy and missing:
        print(f"Creating {len(missing)} indexes...")
        created = 0
        failed = 0
        for col, idx_def in missing:
            parent = f"{PARENT_TEMPLATE}/{col}"
            proto = build_index_proto(idx_def)
            try:
                operation = client.create_index(parent=parent, index=proto)
                print(f"  ⏳ {col}: creating...", end=" ", flush=True)
                operation.result(timeout=120)
                print("✅ done")
                created += 1
            except AlreadyExists:
                print(f"  ⏭️  {col}: already exists")
                created += 1
            except PermissionDenied:
                print(f"\n  ❌ {col}: permission denied")
                print("     The service account needs 'datastore.indexes.create'.")
                print("     Run without --deploy for console/gcloud instructions.")
                failed += 1
            except Exception as e:
                print(f"\n  ❌ {col}: {e}")
                failed += 1
            time.sleep(0.5)
        print(f"\nResult: {created} created, {failed} failed")
        return 0 if failed == 0 else 1

    elif missing:
        print("To create missing indexes, choose one option:\n")
        print("1) Firebase Console (recommended):")
        print(f"   https://console.firebase.google.com/project/{PROJECT}/firestore/indexes")
        print()
        print("2) gcloud CLI (requires datastore.indexes.create):")
        print(f"   gcloud auth login  # use an account with Owner/Editor on the project")
        print(f"   gcloud config set project {PROJECT}")
        for col, idx_def in missing:
            flags = [f"--collection-group={col}"]
            for f in idx_def.get("fields", []):
                if "order" in f:
                    flags.append(f'--field-config=field-path={f["fieldPath"]},order={f["order"]}')
                elif "arrayConfig" in f:
                    flags.append(f'--field-config=field-path={f["fieldPath"]},array-config={f["arrayConfig"]}')
            print(f"   gcloud firestore indexes composite create \\")
            for flag in flags:
                print(f"      {flag} \\")
            print()

    else:
        print("All indexes are up to date!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
