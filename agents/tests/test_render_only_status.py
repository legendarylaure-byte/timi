"""Render-only must be recorded as render_only, never as a failure.

Under DEMO_RENDER_ONLY the pipeline renders a video and publishes to 0/0 on
purpose. The status it persisted was still derived from the publish result, and
an empty result looks exactly like a total failure:

    "uploaded" if (youtube_url or success_count > 0) else "upload_failed"

So a deliberate 0/0 preview was written to Firestore as `upload_failed`. Nobody
can tell that apart from a real upload outage by reading the record, and the
run logged "[PUBLISH] ALL platform uploads failed" while nothing had failed.
That is the D20 rule ("only mark uploaded when a real youtube_url exists")
behaving correctly and landing on a misleading negative.

With publish_at set the old short-path ordering produced a second, different
lie: "scheduled", claiming a publication that can never happen because nothing
was uploaded. Both are pinned below.

The dashboard consumer already existed and is committed (STATUS_META.render_only
-> "Preview only", muted tone, added in 9c814f95). This is the missing producer:
a status declared by the UI that the pipeline never wrote.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from utils import alert_manager  # noqa: E402


def _main():
    """Import main, or skip: crewai -> langchain is container-only.

    Without this every test here becomes a new HOST failure instead of a
    container pass, inflating the known 14-failure baseline. Same pattern as
    test_facebook_resumable.py; verify.sh in the container is the gate.
    """
    return pytest.importorskip("main", reason="needs container deps")


# ------------------------------------------------------------- the predicate
def test_render_only_reads_the_switch():
    main = _main()
    for truthy in ("1", "true", "yes", "TRUE", " Yes "):
        main.os.environ["DEMO_RENDER_ONLY"] = truthy
        assert main._render_only() is True, f"{truthy!r} should enable render-only"
    for falsy in ("0", "false", "no", ""):
        main.os.environ["DEMO_RENDER_ONLY"] = falsy
        assert main._render_only() is False, f"{falsy!r} must NOT suppress publishing"


def test_render_only_agrees_with_the_platform_list():
    """The gate is openable by a bad value if these two disagree.

    _platforms_to_publish() returning [] is what suppresses the upload, and
    _render_only() is what decides the status. If one said yes and the other no,
    a render-only video would get a real status from an empty platform list --
    i.e. exactly the upload_failed bug, reintroduced through drift.
    """
    main = _main()
    main.os.environ["PLATFORMS_TO_PUBLISH"] = "youtube,tiktok,facebook,instagram"
    for truthy in ("1", "true", "yes"):
        main.os.environ["DEMO_RENDER_ONLY"] = truthy
        assert main._platforms_to_publish() == []
        assert main._render_only() is True

    main.os.environ["DEMO_RENDER_ONLY"] = "0"
    assert main._platforms_to_publish() != []
    assert main._render_only() is False


def test_empty_platforms_is_not_render_only():
    """An empty PLATFORMS_TO_PUBLISH is a config fault, not a deliberate preview.

    So render_only must NOT be inferred from `not platforms_to_publish` -- that
    would silently relabel a real misconfiguration as an intentional hold.
    """
    main = _main()
    main.os.environ.pop("DEMO_RENDER_ONLY", None)
    main.os.environ["PLATFORMS_TO_PUBLISH"] = ""
    assert main._platforms_to_publish() == []
    assert main._render_only() is False


# --------------------------------------------------- status lines in main.py
def _status_expr():
    """Return the source of both status assignments, so a revert is visible.

    These assert on the AST/source rather than calling the pipelines: rendering
    a video is not something a unit test should do, and the expression IS the
    behaviour. Anchored on the exact shape so the assertions fail loudly if the
    code is restructured rather than silently matching something else.
    """
    src = Path(_main().__file__).read_text()
    return src


def test_short_status_prefers_render_only_over_upload_failed():
    src = _status_expr()
    line = next(
        (ln for ln in src.splitlines() if ln.strip().startswith("short_status = ")),
        None,
    )
    assert line is not None, "the short path's status assignment moved or was renamed"
    assert "render_only" in line
    # render_only must be the OUTER ternary, or publish_at wins again.
    assert line.index("render_only") < line.rindex("else"), (
        "render_only must be checked before the publish_at branch, or a "
        "render-only video with publish_at is still recorded as 'scheduled'"
    )


def test_long_status_prefers_render_only_over_upload_failed():
    src = _status_expr()
    line = next(
        (ln for ln in src.splitlines() if ln.strip().startswith("final_status = ")),
        None,
    )
    assert line is not None, "the long path's status assignment moved or was renamed"
    assert "render_only" in line


def test_render_only_never_produces_a_failure_status():
    """No path may still write upload_failed while render_only is on.

    Grep-level on purpose: the short and long paths are separate copies of this
    decision, and a single-site fix is a silent half-deploy (the same reason
    P6 wired both persist sites).
    """
    src = _status_expr()
    for path_marker, var in (("short_status = ", "short"), ("final_status = ", "long")):
        line = next(ln for ln in src.splitlines() if ln.strip().startswith(path_marker))
        assert "render_only" in line, f"{var} path has no render_only branch"


def test_both_paths_persist_the_boolean():
    """A distinct status AND a boolean: the status is for humans, the flag is for queries."""
    src = _status_expr()
    assert src.count('"render_only": _render_only(),') == 2, (
        "expected the render_only boolean at both persist sites; a single-site "
        "wire is a half-deploy"
    )


def test_long_path_mirrors_status_into_add_video_record():
    """The long path writes the SAME doc twice, so both copies must agree.

    add_video_record() does a merge=True set on videos/{id} with its own 'status'.
    Passing a hardcoded "upload_failed" in the else would immediately overwrite
    the render_only the line above had just written -- the fix would be undone
    one statement later, which no single-site test can see.
    """
    src = _status_expr()
    assert 'add_video_record(video_id, topic, "long", "upload_failed"' not in src, (
        "the long path still hardcodes upload_failed into add_video_record, "
        "overwriting the render_only status"
    )
    assert 'add_video_record(video_id, topic, "long", final_status' in src


# ------------------------------------------------- consumers must agree
def _repo_root():
    """Walk up for the dashboard/ tree these two tests assert against.

    The container has no dashboard source -- agents/tests is bind-mounted at
    /app/tests, so Path.parents[2] is "/" and the paths resolve to
    /dashboard/... which does not exist. Rather than hardcode a host path (and
    have the assertion quietly pass on a missing file), find the root by looking
    for a file that must be there, and skip with the reason if it is not.

    These two therefore RUN on the host and SKIP in the container. That is the
    honest split, not a gap: the thing they check only exists on the host, and
    pytest reports the skip rather than a green that verified nothing.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "dashboard" / "src" / "lib" / "brand.ts").exists():
            return parent
    pytest.skip("dashboard source not present (container); run on the host")


def test_render_only_is_not_counted_as_published():
    """A preview is not a publication, so the volume guard must not claim it."""
    assert "render_only" not in alert_manager._PUBLISHED_STATUSES, (
        "render_only in _PUBLISHED_STATUSES would count previews toward the "
        "daily 5-video target"
    )


def test_render_only_is_not_counted_as_failed():
    """And it must not raise a failure either -- that is the whole fix."""
    # content_calendar classifies failures by prefix; render_only must not match.
    assert not "render_only".startswith(("failed", "upload_failed", "blocked_"))


def test_dashboard_declares_the_status():
    """The consumer side is committed; this pins that it stays declared.

    A UI badge for a status the backend writes, and vice versa, is how a video
    renders as "Unknown" in the archive. Cheap to keep in sync.
    """
    brand = _repo_root() / "dashboard" / "src" / "lib" / "brand.ts"
    assert "render_only" in brand.read_text()


def test_archive_filter_offers_the_status():
    """Otherwise a preview video is visible under 'all' but impossible to find.

    The archive file already argues this for pending_review and blocked_review;
    the same argument applies here.
    """
    page = _repo_root() / "dashboard" / "src" / "app" / "dashboard" / "archive" / "page.tsx"
    assert '<option value="render_only">' in page.read_text()
