"""TikTok App-Review compliance: clean source, explicit toggles, actionable errors.

Four distinct things had to be true before a TikTok post could survive review,
and each was broken in a way that only shows up under review:

1. The upload must be the pre-watermark master. The channel watermark is a
   competitor's brand burned into the frame, which is the single most common
   App Review rejection. `clean_video_path` is only populated when
   ENABLE_MULTI_LANG_DUB is on, so the watermark-free master is now captured
   explicitly as `tiktok_path`.
2. The composer's own resolution path went through the checkpoint, and
   `save_checkpoint` uses `.set()` (a full replace) -- so it only ever saw the
   WATERMARKED path. Persisting the field was the fix; persisting it at ONE of
   the two call sites would have been a silent half-deploy.
3. `disable_comment`/`disable_duet`/`disable_stitch` were sent as the wrong
   field names, and omitting `brand_content_toggle` lets TikTok default it to
   true -- so a non-branded post was being declared branded.
4. A bare `init failed: 400` tells an operator nothing at 03:00, and two of the
   five causes are permanent states no retry will ever fix.

Every test here is written to fail if its fix is reverted.
"""
import ast
import json
import os
import pathlib
import re
import sys

import pytest

from utils import multi_platform_publisher as mpp


# ---------------------------------------------------------------------------
# 1. The post_info body TikTok actually receives
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _publish_capture(monkeypatch, tmp_path):
    """Drive _upload_tiktok through to the PUBLISH post and capture its post_info.

    Seam note: the toggles belong to the *publish* post, not the init post.
    `/video/init/` only carries source_info (+ an optional privacy_level); the
    title/toggles/disclosure ride on `/video/publish/`. An earlier version of
    this test captured init and therefore asserted nothing -- so the capture
    point is pinned to the publish URL rather than "the first post".
    """
    src = tmp_path / "clean.mp4"
    src.write_bytes(b"x" * (6 * 1024 * 1024))
    seen = {}

    class _FakeRequests:
        @staticmethod
        def post(url, **kw):
            if url.endswith("/video/init/"):
                return _Resp(200, {"data": {
                    "publish_id": "pub_1",
                    "upload_url": "https://upload.example/chunk",
                }})
            if url.endswith("/video/publish/"):
                seen["post_info"] = (kw.get("json") or {}).get("post_info", {})
                return _Resp(200, {"data": {"publish_id": "pub_1"}})
            if "status" in url:
                return _Resp(200, {"data": {
                    "status": "PUBLISH_COMPLETE",
                    "publicaly_available_post_id": ["7654321"],
                }})
            return _Resp(200, {"data": {}})

        @staticmethod
        def put(url, **kw):
            return _Resp(201, {})

    monkeypatch.setitem(__import__("sys").modules, "requests", _FakeRequests)
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("TIKTOK_OPEN_ID", "oid")
    monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "get_ai_disclosure", lambda *a, **k: {"is_aigc": False})
    return seen, str(src)


def test_interaction_fields_use_tiktok_names(monkeypatch, tmp_path):
    """The old code sent comment_disabled/duet_disabled/stitch_disabled.

    Those are not TikTok's field names; the API ignores unknown keys, so every
    toggle silently stayed ON and the post was published with comments open.
    """
    seen, path = _publish_capture(monkeypatch, tmp_path)
    mpp._upload_tiktok("t", path, "shorts", "PUBLIC_TO_EVERYONE",
                       comment_disabled=True, duet_disabled=True, stitch_disabled=True)
    info = seen["post_info"]
    assert info["disable_comment"] is True
    assert info["disable_duet"] is True
    assert info["disable_stitch"] is True
    for wrong in ("comment_disabled", "duet_disabled", "stitch_disabled"):
        assert wrong not in info, f"{wrong} is not a TikTok field; it is silently ignored"


def test_brand_toggles_are_always_explicit(monkeypatch, tmp_path):
    """TikTok defaults an omitted brand_content_toggle to TRUE.

    A non-branded post that omits the field is therefore declared branded, which
    requires a disclosure the uploader never made. Both fields must always be
    present, on every call, including the default path.
    """
    seen, path = _publish_capture(monkeypatch, tmp_path)
    mpp._upload_tiktok("t", path, "shorts", "PUBLIC_TO_EVERYONE")
    info = seen["post_info"]
    assert "brand_content_toggle" in info
    assert "brand_organic_toggle" in info
    assert info["brand_content_toggle"] is False
    assert info["brand_organic_toggle"] is False


def test_brand_toggles_reach_the_post_info(monkeypatch, tmp_path):
    seen, path = _publish_capture(monkeypatch, tmp_path)
    mpp._upload_tiktok("t", path, "shorts", "PUBLIC_TO_EVERYONE",
                       brand_content=True, brand_organic=True)
    info = seen["post_info"]
    assert info["brand_content_toggle"] is True
    assert info["brand_organic_toggle"] is True


def test_brand_toggles_are_forwarded_through_both_layers(monkeypatch, tmp_path):
    """Guards the gap where the toggles existed on _upload_tiktok only.

    Brand flags were added to the leaf function while `upload_to_platform` and
    `multi_platform_publish` had no matching parameters -- so the composer could
    never send them and the leaf defaults silently won. Asserted at the
    signature, because that is where the wiring is.
    """
    import inspect
    for fn in (mpp.upload_to_platform, mpp.multi_platform_publish):
        params = inspect.signature(fn).parameters
        assert "tiktok_brand_content" in params, f"{fn.__name__} cannot forward brand_content"
        assert "tiktok_brand_organic" in params, f"{fn.__name__} cannot forward brand_organic"


def test_brand_content_rejects_self_only(monkeypatch, tmp_path):
    """TikTok refuses brand content at SELF_ONLY: the disclosure is invisible
    on a private post, so the two states are mutually exclusive.

    Checked in the leaf because all three callers reach it -- a check living in
    only the composer would leave the overnight shorts/long paths able to send
    the illegal pair.

    Two things this had to get right, both found by mutation testing:

    * Hermetic. The first version let the call reach the real TikTok API with
      live credentials (18s, real 403), which both burns quota and can publish
      real content. requests is now a tripwire that fails the test on contact.
    * Asserted on "brand content", not "SELF_ONLY". The live 403 is
      unaudited_client_can_only_post_to_private_accounts, whose guidance text
      *contains the string SELF_ONLY* -- so the original assertion passed with
      the guard deleted, for entirely the wrong reason.
    """
    class _Tripwire:
        @staticmethod
        def post(*a, **k):
            raise AssertionError("network call attempted: the guard must short-circuit first")

        @staticmethod
        def put(*a, **k):
            raise AssertionError("network call attempted: the guard must short-circuit first")

    monkeypatch.setitem(sys.modules, "requests", _Tripwire)
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("TIKTOK_OPEN_ID", "oid")
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)

    src = tmp_path / "c.mp4"
    src.write_bytes(b"x" * 100)
    res = mpp._upload_tiktok("t", str(src), "shorts", "SELF_ONLY", brand_content=True)
    assert res["success"] is False
    assert "brand content" in res["error"], \
        f"expected the brand/privacy guard, got a different failure: {res['error']}"


# ---------------------------------------------------------------------------
# 2. Init errors an operator can act on
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code,expect", [
    ("spam_risk_too_many_posts", "posting limit"),
    ("reached_active_user_cap", "active-user cap"),
    ("spam_risk_user_banned_from_posting", "ACCOUNT cannot post"),
    ("unaudited_client_can_only_post_to_private_accounts", "SELF_ONLY"),
    ("privacy_level_option_mismatch", "refresh"),
])
def test_init_errors_map_to_guidance(code, expect):
    resp = _Resp(400, {"error": {"code": code, "message": "some developer string"}})
    out = mpp._tiktok_init_error(resp)
    assert code in out
    assert expect.lower() in out.lower(), f"{code} produced no operator guidance: {out}"


def test_init_error_survives_a_non_json_body():
    resp = _Resp(502, None, text="<html>502 Bad Gateway</html>")
    out = mpp._tiktok_init_error(resp)
    assert "502" in out or "Bad Gateway" in out
    assert out  # must not raise or return empty


def test_init_error_keeps_unknown_codes_diagnosable():
    resp = _Resp(400, {"error": {"code": "some_new_code", "message": "unmapped"}})
    out = mpp._tiktok_init_error(resp)
    assert "some_new_code" in out and "unmapped" in out


def test_unaudited_guidance_is_not_wrong_for_a_branded_post():
    """An unaudited app may only post privately; a brand post may not be private.

    The same TikTok error is therefore a one-line fix for a normal post and an
    impossibility for a branded one. Telling a branded post to "use SELF_ONLY"
    sends the operator down a path that cannot succeed -- and then the guard in
    _upload_tiktok rejects the retry with no new information, so the loop closes
    on a dead end with the real cause two steps away.
    """
    code = "unaudited_client_can_only_post_to_private_accounts"
    resp = _Resp(403, {"error": {"code": code, "message": "raw dev text"}})

    normal = mpp._tiktok_init_error(resp)
    branded = mpp._tiktok_init_error(resp, brand_content=True)

    assert "SELF_ONLY" in normal
    # The branded text must still NAME SELF_ONLY -- that is how it explains why
    # the post is unpostable. What must not survive is the imperative, which is
    # the exact string the normal case gives.
    assert "use SELF_ONLY" not in branded, \
        "a branded post was told to go private, which cannot satisfy the brand guard"
    assert "cannot comply" in branded, "the branded case must state the post is unpostable"
    # Assert the FIX, not the word "brand". Asserting on "brand content" passed
    # with the actionable half deleted, because the explanatory clause reuses
    # the same words -- a test that can be satisfied by the sentence describing
    # the problem is not testing the answer to it.
    assert "complete App Review" in branded, "the durable fix (App Review) is missing"
    assert "unset the brand content toggle" in branded, \
        "the fixable action available right now is missing"


def test_a_permanent_init_error_is_attempted_once(monkeypatch, tmp_path):
    """An unaudited/banned/capped app cannot be fixed by asking again.

    These were being retried 3x with 5->60s backoff, so one impossible upload
    spent ~65s of the overnight run, three rate-limiter slots (of 5/hour) and
    three API calls to arrive at a byte-identical error. Asserted on the CALL
    COUNT, not the message: the message was already right in every case, which
    is why the waste went unnoticed.
    """
    src = tmp_path / "c.mp4"
    src.write_bytes(b"x" * 100)
    calls = {"n": 0}

    # Spelled out rather than iterated from the constant: a test that loops over
    # the same set the code reads shrinks when an entry is deleted, so removing
    # the unaudited code passed. The list here is the claim; the set is the thing
    # under test.
    assert mpp._TIKTOK_PERMANENT_INIT_CODES == {
        'spam_risk_user_banned_from_posting',
        'unaudited_client_can_only_post_to_private_accounts',
        'reached_active_user_cap',
        'privacy_level_option_mismatch',
    }, "the permanent/retryable split changed; confirm each code is genuinely unfixable by a retry"
    assert 'spam_risk_too_many_posts' not in mpp._TIKTOK_PERMANENT_INIT_CODES, \
        "a quota error is time-based and must stay retryable"

    for code in sorted(mpp._TIKTOK_PERMANENT_INIT_CODES):
        calls["n"] = 0
        # _upload_tiktok returns "not configured" before it ever POSTs when these
        # are unset, so without them the call count is 0 and this test passes on
        # a CI runner that has no secrets -- for the wrong reason. Set them here
        # rather than skipping: the retry classification is worth asserting
        # everywhere, and a fake token never leaves the mocked requests.post.
        monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "test-token")
        monkeypatch.setenv("TIKTOK_OPEN_ID", "test-open-id")

        class _Resp:
            status_code = 403
            text = ""

            @staticmethod
            def json():
                return {"error": {"code": code, "message": "nope"}}

        def _post(*a, **k):
            calls["n"] += 1
            return _Resp()

        monkeypatch.setitem(sys.modules, "requests", type("R", (), {"post": staticmethod(_post)}))
        monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
        monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)
        monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)

        res = mpp._upload_tiktok("t", str(src), "shorts", "PUBLIC_TO_EVERYONE")
        assert res["success"] is False, code
        assert calls["n"] == 1, f"{code} was attempted {calls['n']}x; it can never succeed"


def test_a_transient_init_error_is_still_retried(monkeypatch, tmp_path):
    """The other side of the same coin: a quota error must still get its retries.

    Classifying too eagerly is the failure mode that turns a transient blip into
    a lost video, so the retryable branch needs its own test -- "no retry" alone
    would also pass a build that never retried anything.
    """
    src = tmp_path / "c.mp4"
    src.write_bytes(b"x" * 100)
    calls = {"n": 0}
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("TIKTOK_OPEN_ID", "test-open-id")

    class _Resp:
        status_code = 400
        text = ""

        @staticmethod
        def json():
            return {"error": {"code": "spam_risk_too_many_posts", "message": "quota"}}

    def _post(*a, **k):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setitem(sys.modules, "requests", type("R", (), {"post": staticmethod(_post)}))
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)
    # no real sleeping in the test
    monkeypatch.setattr("utils.subprocess_helper.time.sleep", lambda *a: None)

    res = mpp._upload_tiktok("t", str(src), "shorts", "PUBLIC_TO_EVERYONE")
    assert res["success"] is False
    assert calls["n"] == 3, f"a retryable error got {calls['n']} attempts, expected 3"


def test_init_call_site_actually_passes_brand_content(monkeypatch, tmp_path):
    """The wiring, not the helper.

    The test above calls _tiktok_init_error directly, so it stayed green when
    the call site stopped forwarding brand_content -- the helper's default of
    False quietly produced the non-branded guidance for a branded post, which is
    the wrong advice this whole change exists to fix. A helper test cannot see
    its own call site.
    """
    src = tmp_path / "c.mp4"
    src.write_bytes(b"x" * 100)
    # Same reason as the two tests above: unset creds short-circuit _upload_tiktok
    # before the init call, so every assertion below would pass vacuously.
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("TIKTOK_OPEN_ID", "test-open-id")

    def _unaudited(monkeypatch):
        class _Resp:
            status_code = 403
            text = ""

            @staticmethod
            def json():
                return {"error": {"code": "unaudited_client_can_only_post_to_private_accounts",
                                  "message": "app not audited"}}
        monkeypatch.setitem(sys.modules, "requests", type(
            "R", (), {"post": staticmethod(lambda *a, **k: _Resp())}))
        monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
        monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)
        # Must return True, not None: the caller does `if not rate_limiter(...)`,
        # so a None-returning stub reads as "limit reached". The real limiter is
        # in-memory per process and shared across this whole module, so it is
        # already partly spent by the time this test runs.
        monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: True)

    # Unbranded, public: passes the brand guard, hits the unaudited 403.
    _unaudited(monkeypatch)
    plain = mpp._upload_tiktok("t", str(src), "shorts", "PUBLIC_TO_EVERYONE")
    assert plain["success"] is False
    assert "use SELF_ONLY" in plain["error"], plain["error"]

    # Branded, public: also passes the guard, same 403, but the advice differs.
    _unaudited(monkeypatch)
    branded = mpp._upload_tiktok("t", str(src), "shorts", "PUBLIC_TO_EVERYONE",
                                 brand_content=True)
    assert branded["success"] is False
    assert "use SELF_ONLY" not in branded["error"], \
        f"the call site dropped brand_content, so a branded post got the wrong advice: {branded['error']}"


# ---------------------------------------------------------------------------
# 3. Per-platform source selection + cleanup
# ---------------------------------------------------------------------------

def _no_r2(monkeypatch):
    """Neutralise the Cloudflare R2 deletes.

    multi_platform_publish calls delete_video/delete_thumbnail on ANY success,
    with real credentials in the environment -- an unstubbed test really does
    delete from the production bucket, and really does take 13s. The import is
    function-local, so the module attribute is what has to be patched.
    """
    import utils.r2_storage as r2
    monkeypatch.setattr(r2, "delete_video", lambda *a, **k: None)
    monkeypatch.setattr(r2, "delete_thumbnail", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "_register_in_playlist", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "_send_telegram_notification", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "update_video_record", lambda *a, **k: None)


def _stub_publish(monkeypatch, used):
    def _fake(platform, title, description, video_path, thumbnail_path, *a, **kw):
        # *a swallows the positional format_type/publish_at/subtitle_path the real
        # call passes; without it this raises TypeError and the loop's except
        # swallows it, which reads as "TikTok was never attempted".
        used[platform] = video_path
        return {"success": True, "platform": platform, "url": "u", "video_id": "v"}

    monkeypatch.setenv("PLATFORM_UPLOAD_DELAY", "0")
    monkeypatch.setattr(mpp, "upload_to_platform", _fake)
    monkeypatch.setattr(mpp, "optimize_title_for_platform", lambda t, p: t)
    monkeypatch.setattr(mpp, "optimize_for_platform", lambda t, d, p: d)
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    _no_r2(monkeypatch)


def test_tiktok_gets_the_clean_master_and_others_get_the_watermarked(monkeypatch, tmp_path):
    """The whole point of tiktok_path: one file for TikTok, another for everyone else."""
    # Real files: the selection is guarded by os.path.exists, so a fake path
    # proves the fallback branch instead of the thing under test.
    clean = tmp_path / "clean.mp4"
    marked = tmp_path / "watermarked.mp4"
    clean.write_bytes(b"x")
    marked.write_bytes(b"x")
    used = {}
    _stub_publish(monkeypatch, used)

    mpp.multi_platform_publish(
        video_id="v1", title="t", description="d",
        video_path=str(marked), tiktok_path=str(clean),
        thumbnail_path="", format_type="shorts",
        platforms=["youtube", "tiktok"], cleanup=False,
    )
    assert used["tiktok"] == str(clean)
    assert used["youtube"] == str(marked)


def test_tiktok_is_skipped_rather_than_posted_watermarked(monkeypatch, tmp_path):
    """The guard has to be able to fail, or a lost clean file becomes a rejection.

    The previous behaviour fell back to the watermarked master, which is exactly
    the artifact App Review rejects -- so the failure surfaced as a hard external
    rejection hours later instead of as a pipeline error. Other platforms must
    still land, so one dead file cannot cost the whole video.
    """
    marked = tmp_path / "watermarked.mp4"
    marked.write_bytes(b"x")
    used, warned = {}, []

    def _log(actor, msg, level="info", *a, **k):
        warned.append((msg, level))

    _stub_publish(monkeypatch, used)
    monkeypatch.setattr(mpp, "log_activity", _log)
    monkeypatch.setenv("ENABLE_WATERMARK", "true")

    res = mpp.multi_platform_publish(
        video_id="v1", title="t", description="d",
        video_path=str(marked), tiktok_path=str(tmp_path / "gone.mp4"),
        thumbnail_path="", format_type="shorts",
        platforms=["youtube", "tiktok"], cleanup=False,
    )
    assert "tiktok" not in used, "the watermarked copy was uploaded to TikTok"
    assert res["platforms"]["tiktok"]["success"] is False
    assert res["platforms"]["tiktok"]["error"], "a skip with no reason is indistinguishable from a crash"
    assert res["all_success"] is False, "a skipped TikTok must not read as a clean publish"
    # the rest of the slate is unaffected
    assert used["youtube"] == str(marked)
    assert res["success_count"] == 1
    assert any("watermark-free master is missing" in m for m, _ in warned), \
        "skipping TikTok was not logged, so a lost clean file is invisible"


def test_tiktok_falls_back_when_the_pipeline_does_not_watermark(monkeypatch, tmp_path):
    """With ENABLE_WATERMARK=false, video_path is already clean -- so allow it.

    Otherwise the fail-closed guard would silently disable TikTok for every
    watermark-disabled deployment, which is a config nobody tests until it is live.
    """
    marked = tmp_path / "video.mp4"
    marked.write_bytes(b"x")
    used = {}
    _stub_publish(monkeypatch, used)
    monkeypatch.setenv("ENABLE_WATERMARK", "false")

    mpp.multi_platform_publish(
        video_id="v1", title="t", description="d",
        video_path=str(marked), tiktok_path=str(tmp_path / "gone.mp4"),
        thumbnail_path="", format_type="shorts",
        platforms=["tiktok"], cleanup=False,
    )
    assert used["tiktok"] == str(marked)


def test_tiktok_is_skipped_when_the_clean_path_is_the_watermarked_file(monkeypatch, tmp_path):
    """Same path for both is ambiguous, so it is not trusted.

    When `tiktok_path == video_path` there are two very different realities: the
    watermark overlay failed and nothing was burned (the file really is clean), or
    a caller handed the watermarked master over as both. The publisher cannot
    tell them apart, so it declines.

    Skipping a good post is the cheaper error. The alternative -- accepting it --
    republishes exactly the artifact App Review rejects, which is the failure
    this whole path exists to prevent, and it does so on the one input where the
    "clean" label cannot be checked.
    """
    same = tmp_path / "video.mp4"
    same.write_bytes(b"x")
    used, warned = {}, []

    _stub_publish(monkeypatch, used)
    monkeypatch.setattr(mpp, "log_activity",
                        lambda a, m, lv="info", *x, **k: warned.append((m, lv)))
    monkeypatch.setenv("ENABLE_WATERMARK", "true")

    res = mpp.multi_platform_publish(
        video_id="v1", title="t", description="d",
        video_path=str(same), tiktok_path=str(same),
        thumbnail_path="", format_type="shorts",
        platforms=["tiktok"], cleanup=False,
    )
    assert "tiktok" not in used, "an unverified path was accepted as the clean master"
    assert res["platforms"]["tiktok"]["success"] is False


def test_tiktok_is_skipped_when_no_clean_path_was_supplied_at_all(monkeypatch, tmp_path):
    """The hole the caller audit found: tiktok_path omitted, not just missing.

    The guard was keyed on `if platform == 'tiktok' and tiktok_path and ...`, so a
    caller that passed NO clean path skipped the entire branch and shipped the
    watermarked master. Every pre-existing caller did exactly that -- the guard
    looked like it covered the case while covering none of it.
    """
    marked = tmp_path / "watermarked.mp4"
    marked.write_bytes(b"x")
    used, warned = {}, []

    _stub_publish(monkeypatch, used)
    monkeypatch.setattr(mpp, "log_activity",
                        lambda a, m, lv="info", *x, **k: warned.append((m, lv)))
    monkeypatch.setenv("ENABLE_WATERMARK", "true")

    res = mpp.multi_platform_publish(
        video_id="v1", title="t", description="d",
        video_path=str(marked), thumbnail_path="", format_type="shorts",
        platforms=["tiktok"], cleanup=False,
    )
    assert "tiktok" not in used, "a watermarked video was posted to TikTok with no clean path given"
    assert res["platforms"]["tiktok"]["success"] is False
    assert any("no clean master was supplied" in m for m, _ in warned), warned


def test_every_caller_that_reaches_tiktok_supplies_a_clean_path():
    """Static half of the same audit, so a new caller cannot reintroduce it.

    Behavioural tests cannot see a call site that does not exist yet. This walks
    every multi_platform_publish call in main.py and fails if one lists tiktok in
    its platforms without also passing tiktok_path -- the exact shape of the bug.
    """
    src = _main_src()
    tree = ast.parse(src)
    checked = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "multi_platform_publish"):
            continue
        kws = {k.arg for k in node.keywords if k.arg}
        plats = next((ast.unparse(k.value) for k in node.keywords if k.arg == "platforms"), "")
        # Only a literal list proves TikTok is NOT a target. A variable cannot be
        # resolved from the AST, and PLATFORMS_TO_PUBLISH is configured with tiktok
        # in it, so an unresolvable platforms arg is treated as reaching TikTok.
        # Excluding it is what made the first version of this audit inspect 1 of
        # 3 call sites and report success.
        literal = isinstance(next((k.value for k in node.keywords
                                   if k.arg == "platforms"), None), ast.List)
        if literal and "tiktok" not in plats:
            continue
        assert "tiktok_path" in kws, (
            f"line {node.lineno}: platforms={plats} can include TikTok but no tiktok_path is "
            f"passed, so TikTok would receive the watermarked master"
        )
        checked += 1
    assert checked >= 3, (
        f"only {checked} TikTok-reaching call sites inspected -- the audit is not seeing the "
        f"calls it is meant to check"
    )


def test_cleanup_removes_both_the_clean_master_and_the_watermarked_copy(monkeypatch, tmp_path):
    """Two files now exist per video, so cleaning up only one strands the other.

    Stranding the clean master is the expensive direction: it is the large file,
    and it is exactly what a re-publish needs. Asserted behaviourally -- an
    earlier version only regex-matched the source, which cannot tell a working
    loop from a loop that deletes one path and a comment claiming otherwise.
    """
    clean = tmp_path / "clean.mp4"
    marked = tmp_path / "watermarked.mp4"
    clean.write_bytes(b"x" * 2048)
    marked.write_bytes(b"x" * 1024)
    used = {}
    _stub_publish(monkeypatch, used)
    monkeypatch.setenv("ENABLE_WATERMARK", "true")

    mpp.multi_platform_publish(
        video_id="v1", title="t", description="d",
        video_path=str(marked), tiktok_path=str(clean),
        thumbnail_path="", format_type="shorts",
        platforms=["tiktok"], cleanup=True,
    )
    assert used["tiktok"] == str(clean)
    assert not marked.exists(), "the watermarked master was left on disk"
    assert not clean.exists(), "the clean master was stranded on disk"


# ---------------------------------------------------------------------------
# 4. Static guards on the wiring that has no easy runtime seam
# ---------------------------------------------------------------------------

_MAIN = pathlib.Path(__file__).resolve().parents[1] / "main.py"


def _main_src():
    return _MAIN.read_text()


def test_tiktok_path_is_captured_before_the_watermark_overlay():
    """Ordering is the entire fix: after the caption burn, before the logo.

    Captured after the overlay, the "clean" path is watermarked and the whole
    change is a no-op that still reads as correct.

    Scoped to the enclosing function and matched on `add_logo_overlay(` WITH the
    paren. A file-wide regex over the bare name matches the import line
    (`..., burn_subtitles, add_logo_overlay`) and any later mention, so it
    reports "before the overlay" for a capture that is after it.
    """
    src = _main_src()
    tree = ast.parse(src)

    captures = [n for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) == "tiktok_path" for t in n.targets)
                and isinstance(n.value, ast.Name) and n.value.id == "final_path"]
    assert len(captures) == 1, f"expected exactly one tiktok_path capture, found {len(captures)}"
    cap = captures[0]

    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and cap.lineno >= n.lineno), None)
    assert fn is not None, "the capture is not inside a function"
    body = src[fn.lineno - 1:]

    overlay = body.find("add_logo_overlay(")
    assert overlay != -1, f"no add_logo_overlay( call found inside {fn.name}"
    cap_off = body.find("tiktok_path = final_path")
    assert cap_off < overlay, (
        f"in {fn.name}, tiktok_path is captured at +{cap_off} but the watermark "
        f"overlay call is at +{overlay} -- the 'clean' path is watermarked"
    )


def test_tiktok_path_is_persisted_at_both_checkpoint_sites():
    """`save_checkpoint` uses .set(), so the composer resolves its file from here.

    One site wired is a silent half-deploy: shorts would publish clean and longs
    would be rejected. Assert the count, not the presence.
    """
    src = _main_src()
    tree = ast.parse(src)
    writes = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "save_checkpoint"
                and len(node.args) == 3
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "video_pipeline"):
            writes.append(ast.get_source_segment(src, node.args[2]) or "")
    assert len(writes) == 2, f"expected 2 video_pipeline checkpoints, found {len(writes)}"
    for w in writes:
        assert "tiktok_path" in w, f"a video_pipeline checkpoint omits tiktok_path: {w}"


def test_duration_is_persisted_at_both_success_sites():
    """The composer's duration check validates against a field nothing wrote.

    `video_result["duration"]` existed and was only ever passed to a
    notification, so the number the UI checks could not exist.
    """
    src = _main_src()
    assert src.count('"duration": _resolved_duration(video_result)') == 2, \
        "duration must be persisted on both the shorts and the long success path"


def test_composer_job_forwards_the_clean_path_and_brand_flags():
    src = _main_src()
    job = src[src.index("def tiktok_composer_job"):]
    assert "tiktok_path=tiktok_path" in job, "composer still uploads the watermarked file"
    assert "tiktok_brand_content=" in job
    assert "tiktok_brand_organic=" in job


def test_composer_reads_the_clean_path_from_the_checkpoint():
    src = _main_src()
    job = src[src.index("def tiktok_composer_job"):]
    assert "_state.get('tiktok_path'" in job or '_state.get("tiktok_path"' in job, \
        "composer never reads tiktok_path from the checkpoint"


# ---------------------------------------------------------------------------
# 5. Duration resolution
# ---------------------------------------------------------------------------

def test_duration_prefers_the_compositor_count():
    from utils.video_qa import resolved_video_duration
    assert resolved_video_duration({"duration": 42.0, "video_path": "/nope"}) == (42.0, "compositor")


def test_duration_falls_back_to_probing_the_file(monkeypatch, tmp_path):
    """A 0 duration is what blocks the composer's publish.

    The rendered file always exists, so it can be measured -- which is the
    difference between "unknown, refuse to publish" and a usable number.
    """
    import utils.video_qa as vq
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(vq.os.path, "exists", lambda p: True)
    monkeypatch.setattr(vq, "safe_run",
                        lambda *a, **k: type("R", (), {"stdout": "77.5\n"})())
    assert vq.resolved_video_duration({"duration": 0, "video_path": str(f)}) == (77.5, "ffprobe")


def test_duration_is_zero_not_an_exception_when_nothing_is_available():
    from utils.video_qa import resolved_video_duration
    assert resolved_video_duration({})[0] == 0.0
    assert resolved_video_duration({"duration": 0, "video_path": "/does/not/exist"})[0] == 0.0
    # A junk value must not raise on the success path of a video.
    assert resolved_video_duration({"duration": "abc"})[0] == 0.0


def test_main_delegates_to_the_shared_resolver():
    """Pins that main.py has no private copy of the probe.

    A second implementation here would drift from the tested one, which is the
    D42 lesson: two copies of a rule means one of them is wrong. Also asserts
    the import is module-level -- a function-local import cannot satisfy the
    module-level _resolved_duration, which is the D41 NameError exactly.
    """
    import utils.video_qa as vq
    assert hasattr(vq, "resolved_video_duration")
    src = _main_src()
    assert re.search(r"^from utils\.video_qa import resolved_video_duration$", src, re.M), \
        "main.py must import the resolver at module level"
    helper = src[src.index("def _resolved_duration"):src.index("def _platforms_to_publish")]
    assert "ffprobe" not in helper, "main.py grew a private duration probe; use the shared resolver"


# ---------------------------------------------------------------------------
# 6. Caption limit is measured in the unit TikTok enforces
# ---------------------------------------------------------------------------

def test_tiktok_caption_limit_is_2200_utf16_units():
    """`len()` counts code points; TikTok counts UTF-16 code units.

    An emoji outside the BMP is 1 code point and 2 UTF-16 units, so a caption
    that is exactly 2200 in Python is 2400+ on TikTok's side and is rejected.
    """
    from utils.platform_captions import PLATFORM_TITLE_RULES, _utf16_len
    assert PLATFORM_TITLE_RULES["tiktok"]["max_chars"] == 2200
    assert _utf16_len("a" * 2200) == 2200
    assert _utf16_len("🤯") == 2, "an astral emoji is 2 UTF-16 units, not 1"
    assert _utf16_len("🤯" * 1100) == 2200


def test_truncation_never_exceeds_the_limit_with_emoji():
    from utils.platform_captions import optimize_title_for_platform, _utf16_len
    caption = "🤯 " * 1500
    out = optimize_title_for_platform(caption, "tiktok")
    assert _utf16_len(out) <= 2200, f"caption is {_utf16_len(out)} UTF-16 units, over 2200"


def test_rate_limit_is_a_warning_not_a_block(monkeypatch, tmp_path):
    """A soft limit: the upload must proceed, not return a rate-limit refusal.

    A 5-video slate needs exactly 5 uploads per platform, so a hard block with
    zero headroom silently dropped the 6th upload in an hour. The bucket is
    in-memory, so a container restart reset it mid-run -- which is how the
    2026-10-01 TikTok 429 happened. The real protection is PLATFORM_UPLOAD_DELAY
    plus retry_with_backoff, which backs off on a genuine 429. A refused upload
    loses a platform for good; a retried one only costs time.
    """
    mpp = pytest.importorskip("utils.multi_platform_publisher")
    src = tmp_path / "c.mp4"
    src.write_bytes(b"x" * 100)
    # No credentials: the upload short-circuits at the token check, which is
    # PAST the rate limiter. So a rate-limit error here means the limiter
    # blocked; any other error means it proceeded.
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_OPEN_ID", raising=False)
    monkeypatch.setattr(mpp, "rate_limiter", lambda *a, **k: False)
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mpp, "security_audit", lambda *a, **k: None)

    res = mpp._upload_tiktok("t", str(src), "shorts", "SELF_ONLY")

    assert "rate limit" not in res.get("error", "").lower(), (
        f"the rate limiter blocked the upload instead of warning: {res}"
    )
