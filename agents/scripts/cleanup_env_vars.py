"""
Firestore env_vars Collection Cleanup
Lists all docs in the env_vars collection and allows deleting stale entries
(especially FACEBOOK_ACCESS_TOKEN that may override .env with outdated values).

Run: python -m agents.scripts.cleanup_env_vars   (from timi/ directory)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.firebase_status import get_firestore_client


def main():
    db = get_firestore_client()
    if db is None:
        print("ERROR: Could not connect to Firestore. Check service account credentials.")
        sys.exit(1)

    print("\n=== Firestore env_vars Collection ===")
    snapshot = list(db.collection('env_vars').stream())

    if not snapshot:
        print("No documents found in env_vars collection. Nothing to clean up.")
        return

    print(f"\nFound {len(snapshot)} document(s):\n")

    sensitive_keys = {
        "FACEBOOK_ACCESS_TOKEN", "FACEBOOK_PAGE_ID", "INSTAGRAM_ACCOUNT_ID",
        "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET",
        "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN",
        "TIKTOK_OPEN_ID", "TIKTOK_REFRESH_TOKEN",
        "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "FIREBASE_SERVICE_ACCOUNT_KEY",
    }

    docs = {}
    for doc in snapshot:
        data = doc.to_dict()
        value = data.get('value', '')
        key = doc.id
        docs[key] = (doc.reference, value)

        display = value[:20] + "..." if len(value) > 20 else value
        if key in sensitive_keys:
            display = display[:8] + "..." if len(display) > 8 else display
        print(f"  [{key}] = {display}")

    print("\nCommands:")
    print("  delete <key>   — Remove a document from env_vars")
    print("  show <key>     — Show full value (truncated for security)")
    print("  list           — Refresh list")
    print("  done           — Exit")

    while True:
        try:
            cmd = input("\n> ").strip().split(maxsplit=1)
            if not cmd:
                continue
            action = cmd[0].lower()
            arg = cmd[1] if len(cmd) > 1 else ""

            if action == "done":
                break
            elif action == "list":
                for key, (ref, val) in docs.items():
                    display = val[:20] + "..." if len(val) > 20 else val
                    if key in sensitive_keys:
                        display = display[:8] + "..." if len(display) > 8 else display
                    print(f"  [{key}] = {display}")
            elif action == "show":
                if arg not in docs:
                    print(f"  Unknown key: {arg}")
                    continue
                val = docs[arg][1]
                display = val[:60] + "..." if len(val) > 60 else val
                print(f"  [{arg}] = {display}")
            elif action == "delete":
                if arg not in docs:
                    print(f"  Unknown key: {arg}")
                    continue
                confirm = input(f"  Delete '{arg}'? (yes/no): ").strip().lower()
                if confirm == "yes":
                    docs[arg][0].delete()
                    del docs[arg]
                    print(f"  Deleted '{arg}' from Firestore env_vars.")
                else:
                    print("  Skipped.")
            else:
                print(f"  Unknown command: {action}")
        except (EOFError, KeyboardInterrupt):
            break

    print("\nDone.")


if __name__ == "__main__":
    main()
