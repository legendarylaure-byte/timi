"""WS4 guard: descriptions + correct hashtags must reach all four platforms.

Before this change the optimized caption (hook + body + CTA + hashtags) only
made it to YouTube and Facebook:
  - `multi_platform_publish` called `optimize_for_platform` WITHOUT `category`,
    so every platform fell back to the generic hashtag pool;
  - `_upload_tiktok` posted `title` as the caption and dropped `description`;
  - `_upload_instagram` posted `caption=title` and dropped `description`;
  - the YouTube caption carried a hardcoded fake "0:00" timeline.

Each check is written where it can actually fail: the pure helpers are driven
directly, dispatch is exercised with a stub, and the two network-only caption
lines are pinned at the source (the only reachable form without Graph API).
"""
import inspect
import os
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))


def test_youtube_caption_has_no_synthetic_timeline():
    from utils.platform_captions import optimize_for_platform

    out = optimize_for_platform("Why GPUs matter", "Body text here.", "youtube")
    assert "Body text here." in out, f"caption is empty/regenerated, proves nothing: {out!r}"
    assert "0:00" not in out, "the fake hardcoded chapter timeline is back"


def test_hashtags_match_the_real_category():
    from utils.platform_captions import optimize_for_platform, _get_platform_hashtags

    nepal = _get_platform_hashtags("Nepal News", "youtube", 10)
    default = _get_platform_hashtags("__unknown__", "youtube", 10)
    assert nepal and nepal != default, "category is not reaching the hashtag pool"

    out = optimize_for_platform("t", "body", "youtube", category="Nepal News")
    assert "#NepalNews" in out, "the real category's hashtags are not in the caption"


def test_dispatch_passes_description_to_tiktok_and_instagram(monkeypatch):
    import utils.multi_platform_publisher as mp

    seen = {}
    monkeypatch.setattr(mp, "_upload_tiktok",
                        lambda *a, **k: seen.update(tiktok=k.get("description")) or {"success": True})
    monkeypatch.setattr(mp, "_upload_instagram",
                        lambda *a, **k: seen.update(instagram=k.get("description")) or {"success": True})

    mp.upload_to_platform("tiktok", "Title", "THE CAPTION", "/tmp/x.mp4", "shorts")
    mp.upload_to_platform("instagram", "Title", "THE CAPTION", "/tmp/x.mp4", "shorts")

    assert seen.get("tiktok") == "THE CAPTION", f"tiktok dropped the caption: {seen}"
    assert seen.get("instagram") == "THE CAPTION", f"instagram dropped the caption: {seen}"


def test_category_reaches_optimize_for_platform_at_the_call_site():
    """Pins the publisher call site, not just the helper (mutation target)."""
    import utils.multi_platform_publisher as mp

    src = inspect.getsource(mp.multi_platform_publish)
    assert "optimize_for_platform(title, description, platform, category=" in src, (
        "the caption call site no longer threads category, so hashtags regress "
        "to the default pool"
    )


def test_tiktok_uses_description_as_caption():
    import utils.multi_platform_publisher as mp

    src = inspect.getsource(mp._upload_tiktok)
    assert "'title': _truncate_utf16(description, 2200) if description else title" in src, (
        "TikTok is back to posting the bare title as the caption"
    )


def test_instagram_uses_description_as_caption():
    import utils.multi_platform_publisher as mp

    src = inspect.getsource(mp._upload_instagram)
    assert "'caption': (description or title)" in src, (
        "Instagram is back to posting the bare title as the caption"
    )


def test_assemble_description_prepends_title_header():
    import main

    out = main._assemble_description(
        {"full_description": "Body."}, "script", "AI News", title="Why GPUs Matter")
    text = out["full_description"]
    assert text.startswith("🔎 Why GPUs Matter"), text[:60]
    assert "Body." in text


def test_assemble_description_adds_news_source_only_for_news():
    import main

    news = {"full_description": "Body."}
    main._assemble_description(news, "script", "Nepal News", title="Flood",
                               news_article={"source": "Kathmandu Post",
                                             "link": "https://example.com/a"})
    assert "📰 Source: Kathmandu Post — https://example.com/a" in news["full_description"]

    tech = {"full_description": "Body."}
    main._assemble_description(tech, "script", "AI News", title="LLMs", news_article=None)
    assert "📰 Source:" not in tech["full_description"]


def test_assemble_description_never_doubles_the_header():
    import main

    once = main._assemble_description(
        {"full_description": "Body."}, "s", "AI News", title="Topic")
    twice = main._assemble_description(once, "s", "AI News", title="Topic")
    assert twice["full_description"].startswith("🔎 Topic")
    assert twice["full_description"].count("🔎 Topic") == 1, "header was doubled on re-assembly"


def test_retry_path_keeps_the_header_and_source(monkeypatch):
    """A winning SEO retry must not drop the header/source (D40 lesson)."""
    import main

    def fake_generate(**kwargs):
        return {"full_description": "rewritten body", "tags": []}

    monkeypatch.setattr(main, "score_description_seo",
                        lambda d: {"score": 40, "missing": ["cta"]})
    monkeypatch.setattr(main, "suggest_seo_improvements", lambda *a, **k: [])
    monkeypatch.setattr(main, "generate_description", fake_generate)
    monkeypatch.setattr(main, "get_optimized_tags", lambda *a: ["t"])

    desc, _ = main._seo_polish_description(
        {"full_description": "orig", "tags": []}, "script", "Nepal News", "shorts",
        "Flood Alert", "topic", news_article={"source": "Kathmandu Post",
                                              "link": "https://example.com/a"})
    text = desc["full_description"]
    assert text.startswith("🔎 Flood Alert"), text[:60]
    assert "📰 Source: Kathmandu Post" in text
