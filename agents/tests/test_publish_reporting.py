"""Publish reporting: a 3/4 publish must never read as 4/4.

On 2026-09-27 the nightly run produced five videos and 19/20 platform uploads.
One short, `short-20260927-1`, reported `published_platforms` with all four
platforms in it while only three had a URL -- TikTok was attempted, returned no
URL, and disappeared. Nothing consumed the counters, so the gap was invisible.

The cause was one line: `published_platforms` was built from every *attempted*
key rather than the successful ones. This pins that, plus the raw per-platform
outcome that makes a future failure diagnosable at all -- the original was not,
because the success counters are lossy (a `success` with no URL and a hard
failure look identical once logged) and the log had already rotated.
"""
import pytest

from utils import multi_platform_publisher as mpp


def _stub_side_effects(monkeypatch, captured):
    """Neutralise every outbound call so only the reporting logic runs."""
    monkeypatch.setenv("PLATFORM_UPLOAD_DELAY", "0")
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "_send_telegram_notification", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "_register_in_playlist", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "optimize_title_for_platform", lambda t, p: t)
    monkeypatch.setattr(mpp, "optimize_for_platform", lambda t, d, p: d)

    # R2 cleanup fires on any success and would otherwise delete from the real
    # bucket with real credentials.
    import utils.r2_storage as r2
    monkeypatch.setattr(r2, "delete_video", lambda *a, **k: None)
    monkeypatch.setattr(r2, "delete_thumbnail", lambda *a, **k: None)

    def _update_video_record(video_id, data):
        captured.update(data)

    monkeypatch.setattr(mpp, "update_video_record", _update_video_record)


def _run(monkeypatch, per_platform, tmp_path):
    """Drive multi_platform_publish with a scripted outcome per platform."""
    captured = {}
    _stub_side_effects(monkeypatch, captured)

    def _upload(platform, *a, **k):
        return per_platform[platform]

    monkeypatch.setattr(mpp, "upload_to_platform", _upload)

    # Real files, and TikTok gets its own watermark-free one. TikTok is skipped
    # outright when the pipeline watermarks and no clean master is available --
    # which is correct, but it meant these reporting tests saw 3/4 and asserted
    # against the skip instead of the counters. An earlier version instead
    # stubbed os.path.exists to False everywhere, which silenced the guard as a
    # side effect; a stub that broad stops being a stub and becomes a lie.
    marked = tmp_path / "watermarked.mp4"
    clean = tmp_path / "clean.mp4"
    marked.write_bytes(b"x")
    clean.write_bytes(b"x")

    results = mpp.multi_platform_publish(
        video_id="v-test", title="T", description="D",
        video_path=str(marked), tiktok_path=str(clean), thumbnail_path="",
        format_type="shorts", platforms=list(per_platform), cleanup=False,
    )
    return results, captured


THREE_OF_FOUR = {
    "youtube": {"success": True, "platform": "youtube", "video_id": "yt1",
                "url": "https://youtu.be/yt1"},
    # Attempted, no URL -> this is the exact 09-27 TikTok shape.
    "tiktok": {"success": False, "platform": "tiktok",
               "error": "status fetch returned no publish id"},
    "facebook": {"success": True, "platform": "facebook", "video_id": "fb1",
                 "url": "https://fb.com/fb1"},
    "instagram": {"success": True, "platform": "instagram", "video_id": "ig1",
                  "url": "https://ig.com/ig1"},
}


def test_published_platforms_excludes_failed_attempts(monkeypatch, tmp_path):
    """A failed platform must not appear in the published list."""
    results, captured = _run(monkeypatch, THREE_OF_FOUR, tmp_path)

    assert results["success_count"] == 3
    assert results["all_success"] is False

    published = captured["published_platforms"]
    assert "tiktok" not in published, (
        "tiktok was attempted and failed; listing it as published is the 09-27 bug"
    )
    assert set(published) == {"youtube", "facebook", "instagram"}
    # Deterministic order, so the field is diffable between runs.
    assert published == sorted(published)


def test_publish_urls_only_carries_successful_platforms(monkeypatch, tmp_path):
    results, captured = _run(monkeypatch, THREE_OF_FOUR, tmp_path)
    assert set(captured["publish_urls"]) == {"youtube", "facebook", "instagram"}
    assert captured["publish_urls"]["youtube"] == "https://youtu.be/yt1"


def test_raw_per_platform_results_are_persisted(monkeypatch, tmp_path):
    """Without this, a later failure is unrecoverable once logs rotate."""
    _, captured = _run(monkeypatch, THREE_OF_FOUR, tmp_path)

    raw = captured["platform_publish_results"]
    assert set(raw) == {"youtube", "tiktok", "facebook", "instagram"}
    # The failure reason survives, which is the whole point.
    assert raw["tiktok"]["success"] is False
    assert "no publish id" in raw["tiktok"]["error"]


def test_all_four_published_is_still_reported_as_four(monkeypatch, tmp_path):
    """The fix must not shrink a genuine 4/4."""
    clean = {
        "youtube": {"success": True, "platform": "youtube", "video_id": "yt1", "url": "u1"},
        "tiktok": {"success": True, "platform": "tiktok", "video_id": "tt1", "url": "u2"},
        "facebook": {"success": True, "platform": "facebook", "video_id": "fb1", "url": "u3"},
        "instagram": {"success": True, "platform": "instagram", "video_id": "ig1", "url": "u4"},
    }
    results, captured = _run(monkeypatch, clean, tmp_path)
    assert results["success_count"] == 4
    assert results["all_success"] is True
    assert len(captured["published_platforms"]) == 4


def test_total_failure_still_records_the_attempt(monkeypatch, tmp_path):
    """A 0/4 must be visible, not silently empty."""
    allbad = {p: {"success": False, "platform": p, "error": "boom"} for p in THREE_OF_FOUR}
    results, captured = _run(monkeypatch, allbad, tmp_path)
    assert results["success_count"] == 0
    assert captured["published_platforms"] == []
    assert captured["publish_urls"] == {}
    # Still diagnosable.
    assert len(captured["platform_publish_results"]) == 4
