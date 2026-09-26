"""One-shot: drop fabricated YouTube metrics written by the pre-P1 analytics pull.

Those runs wrote ctr=0.0 / impressions=0 for every video because the channel has no
Brand Account, so Analytics returns no impression data. update_video_analytics() uses
merge=True, so once written the fields stayed forever and the feedback loop ranked
categories on a fabricated 0% CTR. The current code omits unavailable metrics; this
removes the ones already persisted.
"""
from utils.firebase_status import get_firestore_client

# Keys to drop. A CTR of exactly 0.0 with impressions of 0 is the fabricated sentinel
# the old pull wrote on every video; real CTR/impressions are unavailable on this
# channel (no Brand Account), so any value at all here is suspect.
DROP = ("ctr", "impressions", "average_view_duration_seconds")


def main() -> int:
    db = get_firestore_client()
    cleaned = 0
    for doc in db.collection("videos").limit(500).stream():
        data = doc.to_dict() or {}
        if not any(k in data for k in DROP):
            continue
        # No DELETE sentinel exists in this client version, so rewrite the doc without
        # the keys. Fine for a one-shot: the fields being removed are fabricated anyway.
        cleaned_data = {k: v for k, v in data.items() if k not in DROP}
        doc.reference.set(cleaned_data)
        cleaned += 1
        print(f"  cleaned {doc.id}")
    print(f"docs cleaned: {cleaned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
