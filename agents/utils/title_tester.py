import os
import json
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "title_tests")
os.makedirs(TEST_DATA_DIR, exist_ok=True)


class TitleTester:
    def __init__(self, youtube_api_update_func=None):
        self.youtube_api_update_func = youtube_api_update_func

    def start_test(self, video_id: str, initial_title: str, variants: list) -> dict:
        return start_title_test(video_id, variants, initial_title)

    def advance_test(self, video_id: str) -> dict:
        return advance_title_test(video_id, self.youtube_api_update_func)

    def record_ctr(self, video_id: str, title: str, ctr: float):
        record_title_ctr(video_id, title, ctr)

    def get_status(self, video_id: str) -> dict:
        return get_test_status(video_id)


def _test_path(video_id: str) -> str:
    return os.path.join(TEST_DATA_DIR, f"{video_id}.json")


def start_title_test(video_id: str, variants: list, initial_title: str) -> dict:
    test = {
        "video_id": video_id,
        "variants": variants,
        "current_index": 0,
        "started_at": datetime.utcnow().isoformat(),
        "stage_end": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        "status": "testing",
        "results": {},
    }
    test["results"][initial_title] = None
    with open(_test_path(video_id), "w") as f:
        json.dump(test, f, indent=2)
    logger.info(f"Title test started for {video_id}: initial title '{initial_title}'")
    return test


def advance_title_test(video_id: str, youtube_api_update_func=None) -> dict:
    path = _test_path(video_id)
    if not os.path.exists(path):
        return {"status": "no_test", "message": "No title test found"}
    with open(path) as f:
        test = json.load(f)
    if test["status"] != "testing":
        return test
    now = datetime.utcnow()
    stage_end = datetime.fromisoformat(test["stage_end"])
    if now < stage_end:
        remaining = (stage_end - now).total_seconds() / 3600
        return {"status": "waiting", "hours_remaining": round(remaining, 1)}
    if youtube_api_update_func:
        current_idx = test["current_index"]
        variants = test["variants"]
        if current_idx < len(variants) - 1:
            next_idx = current_idx + 1
            next_title = variants[next_idx]["title"]
            try:
                youtube_api_update_func(video_id, next_title)
                test["current_index"] = next_idx
                test["stage_end"] = (now + timedelta(hours=24)).isoformat()
                test["results"][next_title] = None
                logger.info(f"Title test advanced to variant {next_idx + 1}: '{next_title}'")
            except Exception as e:
                logger.error(f"Failed to update title: {e}")
                test["status"] = "failed"
                test["error"] = str(e)
        else:
            test["status"] = "completed"
            test["completed_at"] = now.isoformat()
            winner = _pick_winner(test)
            test["winner"] = winner
            logger.info(f"Title test completed for {video_id}. Winner: {winner}")
    with open(path, "w") as f:
        json.dump(test, f, indent=2)
    return test


def record_title_ctr(video_id: str, title: str, ctr: float):
    path = _test_path(video_id)
    if not os.path.exists(path):
        return
    with open(path) as f:
        test = json.load(f)
    test["results"][title] = ctr
    with open(path, "w") as f:
        json.dump(test, f, indent=2)


def _pick_winner(test: dict) -> dict:
    results = test.get("results", {})
    best_title = None
    best_ctr = -1
    for title, ctr in results.items():
        if ctr is not None and ctr > best_ctr:
            best_ctr = ctr
            best_title = title
    if best_title:
        return {"title": best_title, "ctr": best_ctr, "method": "highest_ctr"}
    return {"title": list(results.keys())[0] if results else "unknown", "ctr": 0, "method": "first_available"}


def get_test_status(video_id: str) -> dict:
    path = _test_path(video_id)
    if not os.path.exists(path):
        return {"status": "no_test"}
    with open(path) as f:
        return json.load(f)
