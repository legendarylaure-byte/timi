"""Daily-volume guard: the target and the format matching.

Regression-locks three real defects:
  1. target was SCHEDULE_SHORTS_PER_DAY + SCHEDULE_LONG_PER_DAY (1+2=3) but real
     daily volume is 5, because news adds 2 shorts + 1 long and the news long
     eats a GPU slot.
  2. format was compared to "short"; Firestore stores "shorts", so every
     per-format count was 0.
  3. the whole block was behind `except Exception: pass`.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.alert_manager import check_daily_volume  # noqa: E402
from utils.scheduler_planner import daily_slate  # noqa: E402


def _expected_slate(pillar_shorts, pillar_longs, gpu, news):
    pillar_long_slots = max(min(pillar_longs, gpu - (1 if news else 0)), 0)
    shorts = pillar_shorts + (2 if news else 0)
    longs = pillar_long_slots + (1 if news else 0)
    return {
        "pillar_shorts": pillar_shorts,
        "pillar_longs": pillar_longs,
        "pillar_long_slots": pillar_long_slots,
        "news_shorts": 2 if news else 0,
        "news_longs": 1 if news else 0,
        "gpu_budget": gpu,
        "news_enabled": news,
        "shorts": shorts,
        "longs": longs,
        "total": shorts + longs,
    }


# ---------------------------------------------------------------- slate maths
def test_daily_slate_current_config_is_five():
    """The production config must resolve to 3 short + 2 long = 5, not 1+2=3."""
    os.environ.update({
        "SCHEDULE_SHORTS_PER_DAY": "1",
        "SCHEDULE_LONG_PER_DAY": "2",
        "GPU_VIDEO_BUDGET_PER_DAY": "2",
        "ENABLE_NEWS": "true",
    })
    s = daily_slate()
    assert (s["shorts"], s["longs"], s["total"]) == (3, 2, 5), s


def test_daily_slate_news_off():
    os.environ.update({
        "SCHEDULE_SHORTS_PER_DAY": "1",
        "SCHEDULE_LONG_PER_DAY": "2",
        "GPU_VIDEO_BUDGET_PER_DAY": "2",
        "ENABLE_NEWS": "false",
    })
    s = daily_slate()
    assert (s["shorts"], s["longs"], s["total"]) == (1, 2, 3), s


def test_daily_slate_news_long_consumes_a_gpu_slot():
    """budget 1 + news on => the news long is the only long; no pillar long fits."""
    os.environ.update({
        "SCHEDULE_SHORTS_PER_DAY": "1",
        "SCHEDULE_LONG_PER_DAY": "2",
        "GPU_VIDEO_BUDGET_PER_DAY": "1",
        "ENABLE_NEWS": "true",
    })
    s = daily_slate()
    assert (s["shorts"], s["longs"], s["total"]) == (3, 1, 4), s
    assert s["pillar_long_slots"] == 0


def test_daily_slate_budget_one_no_news():
    os.environ.update({
        "SCHEDULE_SHORTS_PER_DAY": "1",
        "SCHEDULE_LONG_PER_DAY": "2",
        "GPU_VIDEO_BUDGET_PER_DAY": "1",
        "ENABLE_NEWS": "false",
    })
    s = daily_slate()
    assert (s["shorts"], s["longs"], s["total"]) == (1, 1, 2), s


def test_daily_slate_tolerates_junk_config():
    """A mistyped var must not raise at import/boot."""
    os.environ.update({
        "SCHEDULE_SHORTS_PER_DAY": "not-a-number",
        "SCHEDULE_LONG_PER_DAY": "",
        "GPU_VIDEO_BUDGET_PER_DAY": "x",
        "ENABLE_NEWS": "TRUE",
    })
    s = daily_slate()
    assert s["total"] >= 0 and isinstance(s["shorts"], int)


# ------------------------------------------------------------ format matching
def test_format_plural_short_is_counted():
    """The regression: 'shorts' used to match nothing."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260926-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260926-{i}", "format": "long", "status": "published"}
        for i in range(1, 3)
    ]
    assert check_daily_volume(videos, slate) is None


def test_format_singular_short_also_accepted():
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"short-20260926-{i}", "format": "short", "status": "uploaded"}
        for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260926-{i}", "format": "long", "status": "scheduled"}
        for i in range(1, 3)
    ]
    assert check_daily_volume(videos, slate) is None


def test_format_inferred_from_id_when_field_missing():
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260926-{i}", "status": "published"} for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260926-{i}", "status": "published"} for i in range(1, 3)
    ]
    assert check_daily_volume(videos, slate) is None


# ------------------------------------------------------------ shortfall fires
def test_short_run_is_flagged():
    """The 2026-09-25 case: 3 of 5 shipped and the old guard stayed silent."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260925-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 3)
    ] + [
        {"video_id": "long-20260925-1", "format": "long", "status": "published"},
    ]
    alert = check_daily_volume(videos, slate)
    assert alert is not None, "3/5 must raise an alert"
    assert alert["detail"]["run_date"] == "2026-09-25"
    assert alert["detail"]["published"] == 3
    assert alert["detail"]["target"] == 5
    assert "1 short" in alert["message"]
    assert "1 long" in alert["message"]


def test_single_video_run_is_flagged():
    """The 2026-09-15 case: 1 of 5."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [{"video_id": "shorts-20260915-1", "format": "shorts", "status": "published"}]
    alert = check_daily_volume(videos, slate)
    assert alert is not None
    assert alert["detail"]["published"] == 1


def test_wrong_split_flagged_even_at_full_count():
    """5 published but 4 shorts / 1 long is still a broken slate."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260926-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 5)
    ] + [{"video_id": "long-20260926-1", "format": "long", "status": "published"}]
    alert = check_daily_volume(videos, slate)
    assert alert is not None, "format mix must be checked, not just the total"
    assert alert["detail"]["published"] == 5
    assert "1 long" in alert["message"]


def test_no_published_videos_is_an_error_not_silence():
    slate = _expected_slate(1, 2, 2, True)
    alert = check_daily_volume([], slate)
    assert alert is not None
    assert alert["severity"] == "error"


def test_failed_and_generating_are_not_counted():
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260926-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260926-{i}", "format": "long", "status": "published"}
        for i in range(1, 3)
    ] + [
        {"video_id": "long-20260926-9", "format": "long", "status": "failed"},
        {"video_id": "long-20260926-8", "format": "long", "status": "generating"},
    ]
    assert check_daily_volume(videos, slate) is None


# ------------------------------------------------------------ run-date logic
def test_only_newest_run_date_is_judged():
    """Yesterday's complete run must not mask today's empty one."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260925-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260925-{i}", "format": "long", "status": "published"}
        for i in range(1, 3)
    ] + [
        {"video_id": "shorts-20260926-1", "format": "shorts", "status": "failed"},
    ]
    alert = check_daily_volume(videos, slate)
    assert alert is not None
    assert alert["detail"]["run_date"] == "2026-09-26"


def test_run_date_prefers_id_over_created_at():
    v = {
        "video_id": "long-20260927-1",
        "format": "long",
        "status": "published",
        "created_at": "2026-09-26T23:00:00",
    }
    from utils.alert_manager import _run_date
    assert _run_date(v) == "2026-09-27"


# ------------------------------------------------- historical replay (real data)
def test_replay_nine_healthy_days_raise_nothing():
    """Replays the run dates between the two incidents. All were 5/5."""
    slate = _expected_slate(1, 2, 2, True)
    for day in ("20260916", "20260917", "20260918", "20260919",
                "20260920", "20260921", "20260922", "20260923", "20260924"):
        videos = [
            {"video_id": f"shorts-{day}-{i}", "format": "shorts", "status": "published"}
            for i in range(1, 4)
        ] + [
            {"video_id": f"long-{day}-{i}", "format": "long", "status": "published"}
            for i in range(1, 3)
        ]
        assert check_daily_volume(videos, slate) is None, f"{day} should be clean"


def test_replay_catches_both_known_bad_days():
    slate = _expected_slate(1, 2, 2, True)

    # 2026-09-15: one long published, the other four pipelines died (D30 race).
    v15 = [{"video_id": "long-20260915-1", "format": "long", "status": "published"}]
    a15 = check_daily_volume(v15, slate)
    assert a15 is not None and a15["detail"]["run_date"] == "2026-09-15"

    # 2026-09-25: two shorts + one long.
    v25 = [
        {"video_id": f"shorts-20260925-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 3)
    ] + [{"video_id": "long-20260925-1", "format": "long", "status": "published"}]
    a25 = check_daily_volume(v25, slate)
    assert a25 is not None and a25["detail"]["run_date"] == "2026-09-25"


def test_old_target_arithmetic_exactly_where_the_blind_spot_was():
    """Pins the precise blind spot of the old target, without overclaiming.

    The old guard compared `published < 1 + 2` (i.e. < 3). So:
      - 2026-09-15 shipped 1  -> 1 < 3  -> it DID alert. Not a miss.
      - 2026-09-25 shipped 3  -> 3 >= 3 -> it stayed silent. This is the miss.

    The dangerous part is that the target being too low did not just weaken the
    guard, it made a partially-failed day look identical to a healthy one. The
    per-format counts could not rescue it either: they compared to "short" while
    Firestore stores "shorts", so shorts/longs were always 0 and the per-format
    half of the message was pure fiction.
    """
    slate = _expected_slate(1, 2, 2, True)
    old_target = 1 + 2  # SCHEDULE_SHORTS_PER_DAY + SCHEDULE_LONG_PER_DAY

    # 09-15: caught, even by the broken guard.
    v15 = [{"video_id": "long-20260915-1", "format": "long", "status": "published"}]
    assert len(v15) < old_target, "old guard did alert on 1/5"

    # 09-25: 3 published, which is exactly the old target. Blind spot.
    v25 = [
        {"video_id": f"shorts-20260925-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 3)
    ] + [{"video_id": "long-20260925-1", "format": "long", "status": "published"}]
    assert len(v25) == old_target, "3 >= 3, so the old guard passed this day"

    # Both are now caught, and the real target is 5.
    for videos, day in ((v15, "2026-09-15"), (v25, "2026-09-25")):
        alert = check_daily_volume(videos, slate)
        assert alert is not None, f"{day} must raise an alert now"
        assert alert["detail"]["run_date"] == day
        assert alert["detail"]["target"] == 5


def test_per_format_counts_are_never_zero_when_formats_are_known():
    """The 'short' vs 'shorts' bug made the per-format half of the message read 0."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260925-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 3)
    ]
    alert = check_daily_volume(videos, slate)
    assert alert is not None
    assert alert["detail"]["shorts"] == 2, "shorts must be counted, not 0"
    assert alert["detail"]["longs"] == 0
    assert "shorts 2/3" in alert["message"]


def test_all_failed_run_does_not_fall_back_to_yesterday():
    """The bug this fix was written for: zero published today, complete yesterday."""
    slate = _expected_slate(1, 2, 2, True)
    videos = [
        {"video_id": f"shorts-20260925-{i}", "format": "shorts", "status": "published"}
        for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260925-{i}", "format": "long", "status": "published"}
        for i in range(1, 3)
    ] + [
        {"video_id": f"shorts-20260926-{i}", "format": "shorts", "status": "failed"}
        for i in range(1, 4)
    ] + [
        {"video_id": f"long-20260926-{i}", "format": "long", "status": "failed"}
        for i in range(1, 3)
    ]
    alert = check_daily_volume(videos, slate)
    assert alert is not None, "a fully-failed run must not be masked by yesterday"
    assert alert["detail"]["run_date"] == "2026-09-26"
    assert alert["detail"]["published"] == 0
    assert alert["severity"] == "error"
    assert alert["detail"]["docs_seen"] == 5
