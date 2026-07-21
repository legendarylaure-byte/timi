"""ponytail: thumbnail A/B tester — reuses title_tester's sequential rotation pattern."""
import json
import os
import time
from datetime import datetime, timedelta

THUMBNAIL_TESTS_DIR = "data/thumbnail_tests"

os.makedirs(THUMBNAIL_TESTS_DIR, exist_ok=True)


def init_thumbnail_test(video_id: str, thumbnail_paths: list[str]):
    path = os.path.join(THUMBNAIL_TESTS_DIR, f"{video_id}.json")
    data = {
        "video_id": video_id,
        "variants": [{"path": p, "index": i} for i, p in enumerate(thumbnail_paths)],
        "current_index": 0,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "stage_end": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        "results": {},
        "winner": None,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return data


def advance_thumbnail_test(video_id: str):
    path = os.path.join(THUMBNAIL_TESTS_DIR, f"{video_id}.json")
    if not os.path.exists(path):
        return None

    with open(path) as f:
        data = json.load(f)

    if data["status"] != "running":
        return data

    next_idx = data["current_index"] + 1
    if next_idx >= len(data["variants"]):
        data["status"] = "completed"
        data["stage_end"] = datetime.utcnow().isoformat()
        # ponytail: pick winner by latest CTR from YouTube analytics
        data["winner"] = _pick_winner(data)
    else:
        data["current_index"] = next_idx
        data["stage_end"] = (datetime.utcnow() + timedelta(hours=24)).isoformat()

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return data


def _pick_winner(data: dict) -> dict | None:
    if not data["results"]:
        return None
    best_idx = max(data["results"], key=lambda k: data["results"][k].get("ctr", 0))
    return {
        "variant_index": int(best_idx),
        "path": data["variants"][int(best_idx)]["path"],
        "ctr": data["results"][best_idx].get("ctr", 0),
        "method": "highest_ctr",
    }


def record_thumbnail_result(video_id: str, variant_index: int, ctr: float, views: int):
    path = os.path.join(THUMBNAIL_TESTS_DIR, f"{video_id}.json")
    if not os.path.exists(path):
        return

    with open(path) as f:
        data = json.load(f)

    data["results"][str(variant_index)] = {"ctr": ctr, "views": views, "recorded_at": datetime.utcnow().isoformat()}

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_thumbnail_tests() -> list[dict]:
    tests = []
    if not os.path.exists(THUMBNAIL_TESTS_DIR):
        return tests
    for fname in os.listdir(THUMBNAIL_TESTS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(THUMBNAIL_TESTS_DIR, fname)) as f:
                tests.append(json.load(f))
        except Exception:
            pass
    return tests
