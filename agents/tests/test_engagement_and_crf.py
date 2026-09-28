"""Tests for the engagement-logging and CRF changes.

Two defects prompted these:

1. `post_pinned_comment()`'s return value was discarded, so every run logged
   "Pinned comment + auto-reply set up" while doing nothing -- the log claimed
   success unconditionally. The callers in main.py now branch on the return
   value, so its contract (False on failure, never raises) is load-bearing and
   is pinned here.

2. A private or comments-disabled video returns HTTP 403 `commentsDisabled`.
   That is the expected state, not a fault, and `logger.error` on it raised a
   Sentry alert on every single run.

Imports are function-local on purpose: module-level `importorskip` + `from ...
import` did not survive pytest's import rewriting reliably here, and a helper
that silently fails to bind is a test that proves nothing.
"""
import os
import types

import pytest


def _em():
    return pytest.importorskip(
        "utils.engagement_manager", reason="needs container deps")


# --- _comments_unavailable ---------------------------------------------------

class _CommentsDisabled(Exception):
    def __str__(self):
        return ("HttpError 403: commentThreads.list - commentsDisabled")


def test_comments_disabled_is_recognised():
    _comments_unavailable = _em()._comments_unavailable
    assert _comments_unavailable(_CommentsDisabled()) is True


def test_missing_scope_is_still_a_real_fault():
    """A bare 403 'forbidden' is what a missing OAuth scope looks like too.

    Treating it as a skip would hide a genuine misconfiguration behind a debug
    line, so the matcher must NOT match it.

    The message deliberately contains the word "forbidden" -- an earlier version
    of this test used "insufficient permissions", which the matcher never looked
    for, so it passed even with "forbidden" added to the list.
    """
    _comments_unavailable = _em()._comments_unavailable

    class Forbidden(Exception):
        def __str__(self):
            return "HttpError 403: forbidden - insufficient permissions"

    assert _comments_unavailable(Forbidden()) is False


# --- post_pinned_comment contract -------------------------------------------

class _FakeExecute:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    def execute(self):
        if self._exc:
            raise self._exc
        return self._result


class _FakeYouTube:
    """Fails both the insert and the moderation call with `exc`."""

    def __init__(self, exc):
        self._exc = exc
        self.threads_inserted = 0

    def commentThreads(self):
        outer = self

        class _T:
            def insert(self, part=None, body=None):
                outer.threads_inserted += 1
                return _FakeExecute(exc=outer._exc)

            def list(self, part=None, videoId=None, maxResults=None, order=None):
                return _FakeExecute(exc=outer._exc)

        return _T()

    def comments(self):
        exc = self._exc

        class _C:
            def setModerationStatus(self, id=None, moderationStatus=None):
                return _FakeExecute(exc=exc)

            def insert(self, part=None, body=None):
                return _FakeExecute(exc=exc)

        return _C()


def test_post_pinned_comment_returns_false_on_comments_disabled():
    """The main.py callers branch on this bool, so False -- not an exception."""
    post = _em().post_pinned_comment
    assert post("vid1", "hello", _FakeYouTube(_CommentsDisabled())) is False


def test_post_pinned_comment_returns_false_on_real_error():
    post = _em().post_pinned_comment

    class Boom(Exception):
        def __str__(self):
            return "HttpError 500: backend error"

    assert post("vid1", "hello", _FakeYouTube(Boom())) is False


def test_post_pinned_comment_returns_true_on_success():
    post = _em().post_pinned_comment
    svc = _FakeYouTube(Exception("unused"))
    svc.commentThreads = lambda: types.SimpleNamespace(
        insert=lambda part=None, body=None: _FakeExecute(result={"id": "c1"}))
    svc.comments = lambda: types.SimpleNamespace(
        setModerationStatus=lambda id=None, moderationStatus=None: _FakeExecute(result={}))
    assert post("vid1", "hello", svc) is True


def test_post_pinned_comment_returns_false_without_service():
    post = _em().post_pinned_comment
    assert post("vid1", "hello", None) is False


def test_comments_disabled_never_logs_at_error_level(caplog):
    """The actual regression: logger.error here is what alerted Sentry every run.

    `post_pinned_comment` returning the right bool is not enough -- the caller
    logging an expected state at ERROR was the noisy half of the same bug, and
    a bool-only test cannot see it.

    Both entry points are covered. They are separate `except` blocks with their
    own `_comments_unavailable` branches, and testing only one of them let a
    regression in the other through.
    """
    import logging

    em = _em()
    with caplog.at_level(logging.DEBUG, logger=em.logger.name):
        em.post_pinned_comment("vid1", "hi", _FakeYouTube(_CommentsDisabled()))
        em.auto_reply_to_comments("vid1", _FakeYouTube(_CommentsDisabled()))
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert not errors, f"commentsDisabled must not log ERROR, got: {errors}"


def test_a_real_fault_still_logs_at_error_level(caplog):
    """Control for the test above, so it cannot pass by silencing everything."""
    import logging

    em = _em()

    class Boom(Exception):
        def __str__(self):
            return "HttpError 500: backend error"

    with caplog.at_level(logging.DEBUG, logger=em.logger.name):
        em.post_pinned_comment("vid1", "hi", _FakeYouTube(Boom()))
        em.auto_reply_to_comments("vid1", _FakeYouTube(Boom()))
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "a genuine fault must still be reported at ERROR"


# --- the main.py call sites gate on publish_at -------------------------------

def test_both_call_sites_defer_engagement_when_publish_at_is_set():
    """A scheduled video is private, so there is no comment thread to post to.

    Source-level check, and honestly labelled: this asserts the guard is present
    at both sites. It cannot prove the surrounding branch logic is correct. It
    exists to catch someone deleting the gate and silently reintroducing a 403
    plus a false "set up" line on every run.
    """
    main_py = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    src = open(main_py).read()
    assert src.count("if youtube_id and publish_at:") == 2, \
        "expected the publish_at engagement gate at BOTH the short and long call sites"
    # The level matters, not just the wording: a pin that did not happen is a
    # warning, and log_event is what reaches Firestore/activity_logs.
    assert src.count(
        'f"Pinned comment NOT posted for {youtube_id}", "warn")') == 2, \
        "both failure branches must log at warn, not as a success line"
    assert src.count('f"Pinned comment + auto-reply set up for {youtube_id}"') == 2


# --- CRF selection -----------------------------------------------------------

def test_long_form_renders_at_crf_long_and_shorts_do_not():
    """Longs shrink the master; shorts keep the sharper dial.

    A single literal would have changed both, because composite_video renders
    both formats.
    """
    vc = pytest.importorskip("utils.video_compositor", reason="needs container deps")
    assert vc._final_crf("long") == vc.CRF_LONG == "20"
    assert vc._final_crf("shorts") == vc.CRF == "17"
    # Unknown/deep-lesson formats must not silently inherit the long setting.
    assert vc._final_crf("deep_lesson") == vc.CRF


def test_only_the_final_encode_uses_the_format_aware_value():
    """The per-scene encodes must stay on CRF.

    They are re-encoded into the final pass, so their quality is transient; if
    they drifted to CRF_LONG the savings would come out of the wrong encode and
    the final would be re-compressing already-degraded input.
    """
    vc = pytest.importorskip("utils.video_compositor", reason="needs container deps")
    src = open(vc.__file__).read()
    assert src.count('"-crf", final_crf') == 2, \
        "exactly the two final encodes should use final_crf"
    assert 'final_crf = _final_crf(format_type)' in src
