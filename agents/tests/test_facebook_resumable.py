"""Tests for Meta's Facebook resumable upload protocol.

The bug these guard: the resumable path sent the whole file in ONE transfer under
the field name `source` with a hardcoded `start_offset=0`, and never called
`upload_phase=finish`. Meta therefore opened a session and abandoned it, returning
1363030 "Video Upload Timeout" -- which reads exactly like slow bandwidth but is
nothing of the sort.

These tests fake the HTTP layer, so they assert the *protocol* (phase order, field
name, offset handling) without needing a real 50MB upload or a real page.
"""
import json
import os
import sys
import types

import pytest

# The container has crewai/langchain; the host does not (15 known host-only
# import failures). Follow the existing convention: skip rather than add noise.
pytest.importorskip("utils.multi_platform_publisher", reason="needs container deps")

from utils import multi_platform_publisher as mpp  # noqa: E402
from utils.multi_platform_publisher import (  # noqa: E402
    _FB_CHUNK_BYTES,
    _FB_RESUMABLE_THRESHOLD,
    _fb_json,
    _fb_resumable_transfer,
)


# --- fakes -------------------------------------------------------------------

class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload=None, status_code=200, text=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}
        if text is not None:
            self.text = text
        elif payload is None:
            self.text = ""
        else:
            self.text = json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class FakeGraph:
    """Records every POST and answers per upload_phase.

    `window` controls what Meta hands back as the next offset: 'honour' advances
    by the chunk actually sent, 'freeze' always returns the same offset (the stall
    case). `fail_first_transfer` emits a 1363037 once, which carries a recovery
    window in the same error body.
    """

    VIDEO_ID = "fbvid-123"

    def __init__(self, window="honour", fail_first_transfer=False, hard_error=None):
        self.window = window
        self.fail_first_transfer = fail_first_transfer
        self.hard_error = hard_error
        self.calls = []          # (phase, start_offset, bytes_sent, field_name)
        self.transfers_done = 0
        self.accepted = []       # offsets the server actually took

    def post(self, url, params=None, files=None, data=None, timeout=None, **kw):
        phase = (params or {}).get("upload_phase")
        offset = int((params or {}).get("start_offset", 0) or 0)

        # The single-shot upload: no upload_phase, body under 'source'.
        if phase is None:
            field = next(iter((files or {}).keys()), None)
            payload = (files or {}).get(field)
            nbytes = len(payload.read()) if hasattr(payload, "read") else len(payload or b"")
            self.calls.append(("direct", None, nbytes, field))
            if self.hard_error:
                return FakeResponse({"error": self.hard_error})
            return FakeResponse({"id": self.VIDEO_ID, "success": True})

        if phase == "start":
            self.calls.append(("start", None, None, None))
            return FakeResponse({
                "video_id": self.VIDEO_ID,
                "upload_session_id": "sess-abc",
                "start_offset": 0,
                "end_offset": 0,
            })

        if phase == "transfer":
            field = next(iter((files or {}).keys()), None)
            payload = (files or {}).get(field)
            nbytes = len(payload) if payload is not None else 0
            self.calls.append(("transfer", offset, nbytes, field))
            self.transfers_done += 1

            if self.hard_error:
                return FakeResponse({"error": self.hard_error})

            if self.fail_first_transfer and self.transfers_done == 1:
                # 1363037: stale offset, Meta hands back the valid window. The
                # bytes went on the wire but were NOT accepted.
                return FakeResponse({
                    "error": {
                        "message": "Invalid offset",
                        "type": "OAuthException",
                        "code": 1363037,
                        "error_user_title": "Video Upload Timeout",
                    },
                    "start_offset": 0,
                    "end_offset": 0,
                })

            self.accepted.append((offset, nbytes))
            nxt = offset + nbytes if self.window == "honour" else offset
            return FakeResponse({"start_offset": nxt, "end_offset": nxt})

        if phase == "finish":
            self.calls.append(("finish", None, None, None))
            return FakeResponse({"success": True})

        raise AssertionError(f"unexpected phase {phase!r}")


@pytest.fixture
def video_file(tmp_path):
    """A small real file, so getsize/read/seek behave exactly as in production."""
    p = tmp_path / "clip.mp4"
    size = _FB_CHUNK_BYTES * 2 + 1234        # forces 3 transfers
    p.write_bytes(os.urandom(size))
    return str(p), size


def _install(monkeypatch, graph):
    fake_requests = types.ModuleType("requests")
    fake_requests.post = graph.post
    monkeypatch.setitem(sys.modules, "requests", fake_requests)


def _strict_raise(body, phase):
    """Mirrors the real _raise_fb_api_error: raise on any API error."""
    err = body.get("error")
    if err:
        raise RuntimeError(f"{phase}: {err.get('message')} (code {err.get('code')})")


def _run(path, size, graph, raiser=None):
    session = {"upload_session_id": "sess-abc", "video_id": FakeGraph.VIDEO_ID}
    _fb_resumable_transfer(
        path, "page-1", "tok", size, session, "idem",
        _fb_json, raiser or _no_raise, _noop_rate_check,
    )
    return session


def _no_raise(body, phase):
    pass


def _noop_rate_check(resp, platform):
    pass


# --- _fb_json ----------------------------------------------------------------

def test_fb_json_reports_status_and_body_on_non_json():
    """The old code raised 'Expecting value' with no status, no phase, no body."""
    resp = FakeResponse(payload=None, status_code=502, text="<html>Bad Gateway</html>")
    with pytest.raises(RuntimeError) as e:
        _fb_json(resp, "resumable start")
    msg = str(e.value)
    assert "resumable start" in msg
    assert "502" in msg
    assert "Bad Gateway" in msg


def test_fb_json_passes_through_valid_body():
    assert _fb_json(FakeResponse({"ok": 1}), "x")["ok"] == 1


def test_fb_json_rejects_non_object_json():
    with pytest.raises(RuntimeError, match="list"):
        _fb_json(FakeResponse([1, 2, 3]), "x")


# --- protocol ----------------------------------------------------------------

def test_transfer_uses_video_file_chunk_not_source(monkeypatch, video_file):
    """THE core assertion. 'source' is the direct-upload field and is wrong here."""
    path, size = video_file
    graph = FakeGraph()
    _install(monkeypatch, graph)

    _run(path, size, graph)

    transfers = [c for c in graph.calls if c[0] == "transfer"]
    assert transfers, "no transfer phase was issued"
    for _, _, _, field in transfers:
        assert field == "video_file_chunk", f"transfer used {field!r}, not 'video_file_chunk'"


def test_finish_is_called_last(monkeypatch, video_file):
    """Without 'finish' the session is opened and abandoned -> 1363030."""
    path, size = video_file
    graph = FakeGraph()
    _install(monkeypatch, graph)

    _run(path, size, graph)

    phases = [c[0] for c in graph.calls]
    assert phases.count("finish") == 1, "finish must be called exactly once"
    assert phases[-1] == "finish", f"finish must be last, got {phases}"


def test_transfer_advances_offset_and_covers_whole_file(monkeypatch, video_file):
    path, size = video_file
    graph = FakeGraph()
    _install(monkeypatch, graph)

    _run(path, size, graph)

    transfers = [c for c in graph.calls if c[0] == "transfer"]
    offsets = [c[1] for c in transfers]
    assert offsets[0] == 0
    assert offsets == sorted(offsets), f"offsets must increase, got {offsets}"
    assert offsets == sorted(set(offsets)), f"offsets must not repeat, got {offsets}"
    total = sum(c[2] for c in transfers)
    assert total == size, f"sent {total} of {size} bytes"
    assert offsets[-1] + transfers[-1][2] == size


def test_1363037_recovers_using_the_offset_in_the_error_body(monkeypatch, video_file):
    """A stale offset must resume, not throw away a nearly-complete upload."""
    path, size = video_file
    graph = FakeGraph(fail_first_transfer=True)
    _install(monkeypatch, graph)

    _run(path, size, graph, raiser=_strict_raise)

    assert graph.calls[-1][0] == "finish", "should recover and still finish"
    # Count only what the server ACCEPTED: the rejected chunk went on the wire but
    # was discarded, so it is not part of the transferred total.
    accepted = sum(n for _, n in graph.accepted)
    assert accepted == size, f"accepted {accepted} of {size} bytes"
    last_offset, last_len = graph.accepted[-1]
    assert last_offset + last_len == size, "final accepted chunk must land on EOF"


def test_frozen_offset_stalls_out_instead_of_looping_forever(monkeypatch, video_file):
    """A server that never advances the offset must not hang the overnight run."""
    path, size = video_file
    graph = FakeGraph(window="freeze")
    _install(monkeypatch, graph)

    with pytest.raises(RuntimeError, match="stalled"):
        _run(path, size, graph)


def test_resumes_from_the_offset_meta_reported_on_start(monkeypatch, video_file):
    """A session that already holds bytes must not re-send them from 0.

    Re-uploading from 0 is the original 1363030 bug in a new disguise: Meta
    rejects the offset, and a whole file goes out over the wire for nothing.
    """
    path, size = video_file
    graph = FakeGraph()
    _install(monkeypatch, graph)
    resume_at = _FB_CHUNK_BYTES          # Meta already holds the first chunk

    _fb_resumable_transfer(
        path, "page-1", "tok", size,
        {"upload_session_id": "sess-abc", "video_id": FakeGraph.VIDEO_ID}, "idem",
        _fb_json, _no_raise, _noop_rate_check,
        start_offset=resume_at,
    )

    transfers = [c for c in graph.calls if c[0] == "transfer"]
    assert transfers[0][1] == resume_at, \
        f"first transfer must start at Meta's offset {resume_at}, got {transfers[0][1]}"
    assert sum(c[2] for c in transfers) == size - resume_at, \
        "only the remaining bytes should be sent"


def test_fresh_session_end_offset_zero_still_sends_full_chunks(monkeypatch, video_file):
    """Meta's start response reports end_offset=0 on a fresh session.

    That means "nothing received yet", NOT "you may send 1 byte". An earlier
    version of this code capped chunks by end_offset and turned a 3-chunk upload
    into 5,242,881 one-byte requests. The start offset is honoured; the
    end_offset is not used as a cap.
    """
    path, size = video_file
    graph = FakeGraph()
    _install(monkeypatch, graph)

    # Take the resume offset from a real 'start' call rather than hardcoding it,
    # so this stays true if FakeGraph's start response ever changes.
    init = graph.post("u", params={"upload_phase": "start"}).json()
    assert init["end_offset"] == 0, "fake must model a fresh session"

    _fb_resumable_transfer(
        path, "page-1", "tok", size,
        {"upload_session_id": "sess-abc", "video_id": FakeGraph.VIDEO_ID}, "idem",
        _fb_json, _no_raise, _noop_rate_check,
        start_offset=init["start_offset"],
    )

    transfers = [c for c in graph.calls if c[0] == "transfer"]
    assert len(transfers) == 3, f"expected 3 full chunks, got {len(transfers)}"
    assert transfers[0][2] == _FB_CHUNK_BYTES, "fresh session must send a full chunk"
    assert sum(c[2] for c in transfers) == size


def test_real_api_error_still_raises(monkeypatch, video_file):
    """Recovery must not swallow genuine failures."""
    path, size = video_file
    graph = FakeGraph(hard_error={"message": "Invalid OAuth token", "code": 190})
    _install(monkeypatch, graph)

    with pytest.raises(RuntimeError, match="Invalid OAuth token"):
        _run(path, size, graph, raiser=_strict_raise)


# --- the whole _upload_facebook call -----------------------------------------

def test_upload_facebook_runs_the_full_three_phase_protocol(monkeypatch, tmp_path):
    """Drive the real entry point, not just the helper.

    The helper tests prove the transfer loop, but nothing proved the wiring:
    that a file over the threshold actually takes the resumable branch, calls
    start, and returns a video_id built from the start response. Those are
    exactly the seams where the original 1363030 bug lived.
    """
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page-1")
    monkeypatch.setattr(mpp, "_FB_RESUMABLE_THRESHOLD", 0)   # force resumable
    monkeypatch.setattr(mpp, "_compress_for_facebook", lambda p: p)
    monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)
    monkeypatch.setattr(mpp, "get_ai_disclosure", lambda platform: {})
    monkeypatch.setattr(mpp, "retry_with_backoff",
                        lambda fn, **k: (True, fn()))
    monkeypatch.setattr(mpp, "_check_meta_rate_limit", _noop_rate_check)

    path = tmp_path / "clip.mp4"
    path.write_bytes(os.urandom(_FB_CHUNK_BYTES + 777))

    graph = FakeGraph()
    _install(monkeypatch, graph)

    result = mpp._upload_facebook("t", "d", str(path))

    phases = [c[0] for c in graph.calls]
    assert phases[0] == "start", f"resumable must open with start, got {phases}"
    assert phases[-1] == "finish", f"resumable must close with finish, got {phases}"
    assert "transfer" in phases, "resumable must transfer the body"
    assert phases.count("finish") == 1
    assert phases.index("start") < phases.index("transfer") < phases.index("finish")

    assert result["success"] is True, result
    assert result["video_id"] == FakeGraph.VIDEO_ID
    assert result["url"] == f"https://www.facebook.com/watch/?v={FakeGraph.VIDEO_ID}"
    # the whole file went out, in transfer phases only
    assert sum(c[2] for c in graph.calls if c[0] == "transfer") == os.path.getsize(path)


def test_upload_facebook_takes_the_direct_path_below_the_threshold(monkeypatch, tmp_path):
    """A small file must NOT pay for the 3-phase dance."""
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page-1")
    monkeypatch.setattr(mpp, "_FB_RESUMABLE_THRESHOLD", 50 * 1024 * 1024)
    monkeypatch.setattr(mpp, "_compress_for_facebook", lambda p: p)
    monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)
    monkeypatch.setattr(mpp, "get_ai_disclosure", lambda platform: {})
    monkeypatch.setattr(mpp, "retry_with_backoff",
                        lambda fn, **k: (True, fn()))
    monkeypatch.setattr(mpp, "_check_meta_rate_limit", _noop_rate_check)

    path = tmp_path / "small.mp4"
    path.write_bytes(b"x" * 4096)

    graph = FakeGraph()
    _install(monkeypatch, graph)

    result = mpp._upload_facebook("t", "d", str(path))

    phases = [c[0] for c in graph.calls]
    assert phases == ["direct"], f"expected one direct post, got {phases}"
    assert result["success"] is True, result


# --- testability of the threshold -------------------------------------------

def test_threshold_is_a_named_module_constant():
    """If this reverts to an inline literal, the protocol becomes untestable."""
    assert isinstance(_FB_RESUMABLE_THRESHOLD, int)
    assert _FB_RESUMABLE_THRESHOLD == 50 * 1024 * 1024
    src = open(mpp.__file__).read()
    assert "_FB_RESUMABLE_THRESHOLD" in src
    assert "file_size > _FB_RESUMABLE_THRESHOLD" in src, \
        "the upload_method decision must reference the constant"
