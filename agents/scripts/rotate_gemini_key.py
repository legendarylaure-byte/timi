"""One-shot: rotate GEMINI_API_KEY + GEMINI_MODEL into Firestore env_vars.

Firestore wins over .env at boot (sync_env_from_firestore overwrites os.environ
unconditionally), so this is the location that actually takes effect.

Usage: python -m agents.scripts.rotate_gemini_key
Reads the new key from the GEMINI_API_KEY env var — never hardcode a secret here.
"""
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from utils.firebase_status import get_firestore_client  # noqa: E402


def main() -> int:
    new_key = os.getenv("NEW_GEMINI_API_KEY", "").strip()
    if not new_key:
        print("set NEW_GEMINI_API_KEY in the environment first")
        return 1

    db = get_firestore_client()
    if db is None:
        print("no Firestore client — check service account")
        return 1

    ts = datetime.now(timezone.utc).isoformat()
    for name, value in (
        ("GEMINI_API_KEY", new_key),
        ("GEMINI_MODEL", os.getenv("NEW_GEMINI_MODEL", "gemini-3.8-flash")),
    ):
        db.collection("env_vars").document(name).set(
            {"value": value, "updated_at": ts}, merge=True
        )
        shown = f"{value[:6]}...len{len(value)}" if "KEY" in name else value
        print(f"env_vars/{name} = {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
