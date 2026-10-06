#!/usr/bin/env python3
"""Delete all anonymous Firebase Auth users.

Anonymous users have no email and no provider_data. They accumulate from
previous auth models and are inert (Firestore rules deny them), but they
clutter the Firebase console and are a review flag.

Run: python scripts/cleanup-anonymous-users.py
Requires: firebase/serviceAccountKey.json in the repo root.
"""
import firebase_admin
from firebase_admin import auth, credentials

cred = credentials.Certificate("firebase/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

page = auth.list_users()
deleted = 0
while page:
    for user in page.users:
        if not user.email and not user.provider_data:
            auth.delete_user(user.uid)
            deleted += 1
            print(f"Deleted {user.uid}")
    page = page.get_next_page()
print(f"Done. Deleted {deleted} anonymous users.")
