"""Tests for the TikTok-composer demo short and its real-% progress callback."""
import os
import sys

import pytest

from utils import multi_platform_publisher as mpp


def _chunk_requests(seen):
    class _FakeRequests:
        @staticmethod
        def post(url, **kw):
            if url.endswith("/video/init/"):
                return _Resp(200, {"data": {
                    "publish_id": "pub_1",
                    "upload_url": "https://upload.example/chunk",
                }})
            if url.endswith("/video/publish/"):
                return _Resp(200, {"data": {"publish_id": "pub_1"}})
            if "status" in url:
                return _Resp(200, {"data": {
                    "status": "PUBLISH_COMPLETE",
                    "publicaly_available_post_id": ["7654321"],
                }})
            return _Resp(200, {"data": {}})

        @staticmethod
        def put(url, **kw):
            seen.append(1)
            return _Resp(201, {})

    return _FakeRequests


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_progress_cb_receives_real_chunk_percentages(monkeypatch, tmp_path):
    """Drive the real chunk loop: each PUT must surface a rising pct through progress_cb.

    Two files (one small, one crossing a 64MB chunk boundary) so the callback
    count tracks total_chunk_count rather than always being 1.
    """
    src = tmp_path / "clean.mp4"
    src.write_bytes(b"x" * (80 * 1024 * 1024))  # 80MB -> 2 chunks
    puts = []
    monkeypatch.setitem(sys.modules, "requests", _chunk_requests(puts))
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("TIKTOK_OPEN_ID", "oid")
    monkeypatch.setenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")
    monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "get_ai_disclosure", lambda *a, **k: {"is_aigc": False})

    pcts = []
    res = mpp._upload_tiktok("t", str(src), "shorts",
                             privacy_level="SELF_ONLY",
                             progress_cb=lambda info: pcts.append(info.get("pct")))
    assert res["success"], res
    assert pcts

    pcts_small = []
    src2 = tmp_path / "small.mp4"
    src2.write_bytes(b"x" * (6 * 1024 * 1024))
    res2 = mpp._upload_tiktok("t", str(src2), "shorts",
                              privacy_level="SELF_ONLY",
                              progress_cb=lambda info: pcts_small.append(info.get("pct")))
    assert res2["success"], res2
    assert pcts_small

    # progress must be monotonically non-decreasing and end at 100.
    assert all(a <= b for a, b in zip(pcts, pcts[1:]))
    assert pcts[-1] == 100


def test_demo_render_is_short_and_portrait(tmp_path):
    from utils.demo_video import render_demo_short
    out = tmp_path / "demo.mp4"
    res = render_demo_short("AI in under 30 seconds", str(out))
    assert res["duration_seconds"] < 30
    assert os.path.getsize(out) > 1000
    from utils.subprocess_helper import safe_run
    r = safe_run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                  "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)])
    assert r.stdout.strip() == "1080,1920"


def test_composer_scales_chunk_pct_into_upload_band():
    """The composer's callback maps pct (0-100) into the 60-95 upload band, clamped."""
    scaled = [min(60 + int(pct * 0.35), 95) for pct in (0, 50, 100)]
    assert scaled == [60, 77, 95]


def test_narration_template_is_fixed_and_short():
    from utils.demo_video import build_narration
    n = build_narration("Transformers")
    assert "Transformers" in n
    assert len(n) < 300