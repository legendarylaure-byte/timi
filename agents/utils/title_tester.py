import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
    # Start at the variant we actually published, not blindly at index 0.
    current_index = next((i for i, v in enumerate(variants)
                          if (v.get("title") if isinstance(v, dict) else v) == initial_title), 0)
    test = {
        "video_id": video_id,
        "variants": variants,
        "current_index": current_index,
        "started_at": _utcnow_iso(),
        "stage_end": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "status": "testing",
        "results": {},
        # views_at_stage_start[title] = view count when that variant went live.
        # CTR/impressions are NOT available on this channel (no Brand Account), so
        # views-per-hour is the only real signal an A/B test can use here.
        "views_at_stage_start": {initial_title: None},
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
    now = datetime.now(timezone.utc)
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
                test.setdefault("views_at_stage_start", {})[next_title] = None
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
    """Pick the variant that gained the most views per hour of exposure.

    Returns method="insufficient_data" when nothing was measured — never a fake
    winner, which is what the old CTR version did on an all-None results dict.
    """
    results = test.get("results", {}) or {}
    starts = test.get("views_at_stage_start", {}) or {}
    hours = float(os.getenv("TITLE_TEST_STAGE_HOURS", "24"))

    measured = {}
    for title, views in results.items():
        if views is None:
            continue
        start = starts.get(title)
        if start is None:
            continue
        measured[title] = (views - start) / hours
    if measured:
        best = max(measured, key=measured.get)
        return {"title": best, "views_per_hour": round(measured[best], 3),
                "method": "highest_views_per_hour", "measured": measured}
    return {"title": None, "method": "insufficient_data",
            "message": "No view data measured for any variant; leaving the title unchanged."}


def get_test_status(video_id: str) -> dict:
    path = _test_path(video_id)
    if not os.path.exists(path):
        return {"status": "no_test"}
    with open(path) as f:
        return json.load(f)


def sync_title_ctr_from_youtube() -> int:
    """Record the view count for whatever variant is currently live.

    Kept under the old name so existing callers still work, but it no longer tries to
    read CTR: this channel has no Brand Account, so YouTube returns no impressions and
    fetch_video_stats() exposes no impression, title or ctr keys at all. The old version
    guarded on the impression and title keys and therefore skipped every single video,
    forever.

    Returns the number of tests updated.
    """
    try:
        from utils.youtube_upload import fetch_video_stats
    except Exception:
        return 0

    updated = 0
    if not os.path.isdir(TEST_DATA_DIR):
        return 0
    for fname in os.listdir(TEST_DATA_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(TEST_DATA_DIR, fname)
        try:
            with open(path) as f:
                test = json.load(f)
        except Exception:
            continue
        if test.get("status") != "testing":
            continue

        variants = test.get("variants") or []
        idx = test.get("current_index", 0)
        if not (0 <= idx < len(variants)):
            continue
        current = variants[idx]
        current_title = current.get("title") if isinstance(current, dict) else current
        if not current_title:
            continue

        # Record the stage baseline the first time we see this variant.
        starts = test.setdefault("views_at_stage_start", {})
        if starts.get(current_title) is None:
            stats = fetch_video_stats(test["video_id"])
            if not stats or stats.get("error"):
                continue
            starts[current_title] = stats.get("views", 0)
            with open(path, "w") as f:
                json.dump(test, f, indent=2)
            updated += 1

    return updated
