"""Viral News Social Media Agent.

Monitors verified news sources for viral articles and posts image+caption
content to Facebook and Instagram independently of the video pipeline.

Isolation guarantees (does NOT affect the running pipeline):
  - Uses its own temp dir: tmp/viral_news/ (separate from compositor TEMP_DIR)
  - Uses its own Firestore collection: viral_news_posts
  - Does NOT call generate_short_video/generate_long_video or any video render
  - Does NOT touch the GPU/LTX or video rendering path
  - Runs on its own scheduler entries in main.py
"""
import json
import logging
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_TEMP_DIR = _BASE_DIR / "tmp" / "viral_news"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Brand colors ───────────────────────────────────────────────────────────
# The palette itself lives in utils/brand_palette.py -- one source of truth,
# because these four were hardcoded here AND in ~20 other places. The old local
# copies (_BRAND_BG/_BRAND_TEAL/_BRAND_ORANGE/_WHITE) are gone; import from there.
_FONT_PATH = os.getenv("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
# Concept B headline voice. FreeSerif ships in the image (fonts-freefont-ttf, which
# the Hindi/Korean font work already depends on), so this needs no new package.
# Falls back to the sans face rather than tofu if the container ever loses it.
_SERIF_FONT_PATH = os.getenv(
    "VIRAL_SERIF_FONT_PATH", "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
)

# ── Virality thresholds ────────────────────────────────────────────────────
VIRAL_THRESHOLD = float(os.getenv("VIRAL_THRESHOLD", "55"))
VIRAL_HOLD_THRESHOLD = float(os.getenv("VIRAL_HOLD_THRESHOLD", "40"))
VIRAL_COOLDOWN_HOURS = int(os.getenv("VIRAL_COOLDOWN_HOURS", "3"))
VIRAL_MAX_PER_DAY = int(os.getenv("VIRAL_MAX_PER_DAY", "5"))
HOLD_REVIEW_MINUTES = int(os.getenv("VIRAL_HOLD_REVIEW_MINUTES", "15"))

_config_cache = {"ts": 0.0, "data": None}


def _live_config() -> dict:
    """Live operational config (Firestore overrides env, TTL-cached 60s).

    The dashboard threshold editor writes viral_news_config/settings; the
    module-level env constants above are only the process-boot fallback.
    """
    import time as _t
    now = _t.time()
    if _config_cache["data"] is None or now - _config_cache["ts"] > 60:
        try:
            from utils.viral_config import get_viral_config
            _config_cache["data"] = get_viral_config()
        except Exception:
            _config_cache["data"] = {}
        _config_cache["ts"] = now
    c = _config_cache["data"]
    return {
        "viral_threshold": float(c.get("viral_threshold", VIRAL_THRESHOLD)),
        "viral_hold_threshold": float(c.get("viral_hold_threshold", VIRAL_HOLD_THRESHOLD)),
        "viral_max_per_day": int(c.get("viral_max_per_day", VIRAL_MAX_PER_DAY)),
        "viral_cooldown_hours": float(c.get("viral_cooldown_hours", VIRAL_COOLDOWN_HOURS)),
    }

# ── Scheduling ──────────────────────────────────────────────────────────────
VIRAL_SCHEDULE_TIMES = os.getenv("VIRAL_SCHEDULE_TIMES", "06:00,18:00").split(",")
# Real-time viral news monitor — runs every VIRAL_CHECK_INTERVAL minutes.
# Ponytail: polling interval — adjust via env var (default 5 minutes).
VIRAL_CHECK_INTERVAL = int(os.getenv("VIRAL_CHECK_INTERVAL", "5"))

# ── Image generation ────────────────────────────────────────────────────────
_IMAGE_WIDTH = int(os.getenv("VIRAL_IMAGE_WIDTH", "1080"))
_IMAGE_HEIGHT = int(os.getenv("VIRAL_IMAGE_HEIGHT", "1080"))

# Two different budgets, on purpose. The caption is a text surface with room for
# 2-4 sentences; the card has a fixed panel and a structural clamp on how many
# summary lines fit, so it cannot be pushed off the bottom edge any more (it
# could while the panel floated under the divider). They are now sized
# independently rather than by the same accident.
_CARD_SUMMARY_CHARS = 200
_CAPTION_SUMMARY_CHARS = 400

# Card type scale, as a fraction of card height. One dict rather than six inline
# literals so the sizes are assertable and so scripts/viral_card_review.py can
# render competing scales without duplicating the drawing code.
#
# The previous scale (title 0.058, body 0.026, url 0.020) was tuned for a
# top-weighted layout and left 21-39% of the card empty (measured across real
# article shapes -- see the bottom-anchoring note in _card_layout). A phone
# renders this card at roughly 500px wide, so 0.026 -> ~13pt of body text.
_CARD_SCALE = {
    "eyebrow": 0.030,
    # Headline-led (owner choice, 09-29, from the A/B sheet): the headline is
    # what makes someone tap, so it gets the space and the body pays for it.
    # Measured over real article shapes, this is the option with the tighter
    # sparsest case (15.5% vs 21.5% on a 2-line headline) at the cost of 3px of
    # body and 30 characters of summary. See scripts/viral_card_review.py.
    "title": 0.085,
    # Line spacing is derived from the title scale rather than set independently,
    # so a bigger headline cannot silently overlap the summary below it.
    "line": 0.085 * 1.20,
    "body": 0.037,
    "body_line": 0.036,
    "src": 0.036,
    "cta": 0.030,
    "url": 0.026,
}
# Hard ceiling on headline lines, and on summary lines. The headline cap is a
# locked rule: a >5-line title loses its tail to the wrap and the card still
# lays out correctly. The summary cap is soft -- _card_layout lowers it further
# when the headline left no room.
_CARD_MAX_HEADLINE_LINES = 5
_CARD_MAX_SUMMARY_LINES = 5
# Floor for the auto-fit below. Below this the type stops being readable, and
# unreadably small type is a worse failure than a long headline losing its tail.
_CARD_TITLE_MIN_SCALE = 0.055

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from utils.viral_config import (
    get_viral_config, set_viral_active, log_viral_activity,
    get_viral_posts,
)

# ── Timezone helpers ────────────────────────────────────────────────
# Nepal Time (NPT) = UTC+5:45
_NPT_OFFSET_HOURS = 5.75


def utc_to_npt(utc_str: str) -> str:
    """Convert UTC ISO timestamp to Nepal Time string."""
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        npt_dt = utc_dt + timedelta(hours=_NPT_OFFSET_HOURS)
        return npt_dt.strftime("%Y-%m-%d %I:%M %p NPT")
    except Exception:
        return utc_str


def now_npt() -> str:
    """Current time in Nepal Time."""
    return (datetime.now(timezone.utc) + timedelta(hours=_NPT_OFFSET_HOURS)).strftime(
        "%Y-%m-%d %I:%M %p NPT"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Firestore helpers
# ═══════════════════════════════════════════════════════════════════════════
def _get_firestore():
    from utils.firebase_status import get_firestore_client
    return get_firestore_client()


def _save_post_firestore(doc: dict):
    """Save a viral post record to Firestore for audit trail."""
    try:
        db = _get_firestore()
        db.collection("viral_news_posts").add(doc)
    except Exception as e:
        logger.warning("[viral] Firestore save failed: %s", e)


def _save_score_insights(scored_stories: list):
    """Persist the top-8 scored stories each scan (live feed for dashboard).

    Replaces the whole insights subset — keeps the panel a live snapshot of
    the latest scan, not a growing collection.
    """
    try:
        db = _get_firestore()
        top = sorted(scored_stories, key=lambda s: s["virality_score"], reverse=True)[:8]
        if not top:
            return
        docs = [d.id for d in db.collection("viral_news_insights").limit(8).stream()]
        batch = db.batch()
        coll = db.collection("viral_news_insights")
        for i, story in enumerate(top):
            doc = coll.document(docs[i]) if i < len(docs) else coll.document()
            story["scanned_at"] = datetime.now(timezone.utc).isoformat()
            batch.set(doc, story)
        batch.commit()
    except Exception as e:
        logger.warning("[viral] Insights save failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════
# News monitoring (reuses VERIFIED_HOSTS pattern from news_scraper.py)
# ═══════════════════════════════════════════════════════════════════════════
# Import verified hosts from existing scraper to maintain source authenticity.
try:
    from utils.news_scraper import VERIFIED_HOSTS, _normalize_host, _host_of, _http_get
    HAS_NEWS_SCRAPER = True
except ImportError:
    HAS_NEWS_SCRAPER = False
    VERIFIED_HOSTS = set()


# Additional sources specifically good for viral social content.
# These are sources whose articles frequently trend on social media.
VIRAL_BOOST_SOURCES = {
    "BBC World", "The Guardian World",
    "The Kathmandu Post", "NepaliTimes", "OnlineKhabar EN", "Khabarhub",
}

# Keywords that boost virality score (signals broad public interest).
VIRAL_KEYWORDS = [
    "breakthrough", "revolutionary", "shocking", "game-changer", "massive",
    "record", "first-ever", "historic", "explosion", "crash", "scandal",
    "AI", "artificial intelligence", "tech giant", "stock surge", "election",
    "crisis", "emergency", "outbreak", "discovery", "innovation", "transforms",
    "rewrites", "billion", "million", "shares", "viral", "trending",
]


def fetch_candidate_articles(category: str = None) -> list:
    """Fetch verified news articles suitable for social media posting.

    Reuses the verified-hosts gate from news_scraper.py so no unverified
    source ever reaches scoring. Returns candidate articles with full text.
    """
    if not HAS_NEWS_SCRAPER:
        logger.warning("[viral] news_scraper not available, no candidates")
        return []

    from utils.news_scraper import fetch_news

    try:
        items = fetch_news(category=category)
    except Exception as e:
        logger.warning("[viral] fetch_news failed: %s", e)
        return []

    candidates = []
    for item in items:
        # Enrich with extra fields for scoring
        article = dict(item)
        article.setdefault("body", item.get("description", ""))
        article.setdefault("published_at", datetime.now(timezone.utc).isoformat())
        article.setdefault("source", item.get("source", "Unknown"))
        article.setdefault("category", item.get("category", "Unknown"))
        article.setdefault("lang", item.get("lang", "en"))
        candidates.append(article)
    return candidates


# ═══════════════════════════════════════════════════════════════════════════
# Virality scoring
# ═══════════════════════════════════════════════════════════════════════════
def score_virality(article: dict) -> dict:
    """Score an article for virality potential (0-100).

    Pure signal-based — no LLM call (keeps it fast and deterministic).
    Factors:
      - Source authority (0-25): verified + viral-boost sources get more
      - Keyword density (0-25): how many viral signals in title+body
      - Recency (0-20): fresher = more viral
      - Length/completeness (0-15): has body text = better context
      - Social signal hints (0-15): words like 'shares', 'million', 'trending'

    ponytail: this is a heuristic scorer, not ML — fast, stateless, no LLM
    dependency. Upgrade path: swap in a fine-tuned classifier later.
    """
    title = (article.get("title") or "").lower()
    body = (article.get("body") or "").lower()
    source = article.get("source", "")
    text = f"{title} {body}"
    now = datetime.now(timezone.utc)

    # 1. Source authority (0-25)
    source_score = 10  # baseline for any verified source
    if source in VIRAL_BOOST_SOURCES:
        source_score = 22
    elif any(kw in source.lower() for kw in ["bbc", "guardian", "reuters", "ap", "nyt"]):
        source_score = 20

    # 2. Keyword density (0-25)
    keyword_hits = sum(1 for kw in VIRAL_KEYWORDS if kw in text)
    keyword_score = min(25, keyword_hits * 4)  # 1 hit = 4 pts, cap 25

    # 3. Recency (0-20)
    pub_str = article.get("published_at", "")
    hours_old = 999
    try:
        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
        hours_old = (now - pub_dt).total_seconds() / 3600.0
    except Exception:
        pass
    if hours_old <= 2:
        recency_score = 20
    elif hours_old <= 6:
        recency_score = 16
    elif hours_old <= 12:
        recency_score = 12
    elif hours_old <= 24:
        recency_score = 8
    elif hours_old <= 48:
        recency_score = 4
    else:
        recency_score = 1

    # 4. Completeness (0-15)
    body_len = len(body)
    if body_len > 500:
        completeness_score = 15
    elif body_len > 200:
        completeness_score = 12
    elif body_len > 50:
        completeness_score = 8
    elif body_len > 0:
        completeness_score = 4
    else:
        completeness_score = 0

    # 5. Social signal hints (0-15)
    social_hits = sum(1 for s in ["shares", "million", "thousand", "trending",
                                   "breaking", "exclusive", "alert", "urgent"]
                      if s in text)
    social_score = min(15, social_hits * 4)

    total = source_score + keyword_score + recency_score + completeness_score + social_score

    breakdown = {
        "source": source_score,
        "keywords": keyword_score,
        "recency": recency_score,
        "completeness": completeness_score,
        "social_signals": social_score,
    }

    live = _live_config()
    viral_threshold = live["viral_threshold"]
    hold_threshold = live["viral_hold_threshold"]

    return {
        "virality_score": total,
        "breakdown": breakdown,
        "is_viral": total >= viral_threshold,
        "is_hold": hold_threshold <= total < viral_threshold,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Post generation (caption + image)
# ═══════════════════════════════════════════════════════════════════════════
_VIRAL_CTA = "What's your take? Comment below"
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "of", "to", "in", "on", "at",
    "is", "are", "was", "were", "be", "as", "by", "with", "from", "that", "this",
    "it", "its", "has", "have", "will", "would", "can", "could", "after", "over",
    "new", "says", "say", "said", "amid", "into",
}


def _hashtags(article: dict, limit: int = 5) -> str:
    """Hashtags derived from the headline, not from the LLM.

    Letting the model place hashtags inside the caption body meant the fixed
    order (title, hook, body, CTA, hashtags, link) could not be enforced -- the
    hashtags arrived wherever it felt like putting them. Built here instead, so
    the structure holds and there is exactly one place to tune the count.
    """
    tags: list[str] = []
    for word in (article.get("title") or "").split():
        w = re.sub(r"[^0-9A-Za-z]+", "", word)
        if len(w) > 3 and w.lower() not in _STOPWORDS and w.lower() not in {t.lower() for t in tags}:
            tags.append(w)
    for cat_word in (article.get("category") or "").replace("&", " ").split():
        w = re.sub(r"[^0-9A-Za-z]+", "", cat_word)
        if len(w) > 2 and w.lower() not in {t.lower() for t in tags}:
            tags.append(w)
    if not tags:
        tags = ["News"]
    return " ".join(f"#{t}" for t in tags[:limit])


def _article_text(article: dict) -> str:
    raw = (article.get("body") or article.get("description") or "").strip()
    return re.sub(r"\s+", " ", raw)


def _trim_to(raw: str, limit: int) -> str:
    """Trim to `limit` on a word boundary. Anything else leaves a half word."""
    if not raw or len(raw) <= limit:
        return raw
    cut = raw[:limit].rsplit(" ", 1)[0]
    return (cut or raw[:limit]).rstrip(",;:- ") + "…"


def _caption_body_summary(article: dict, limit: int = _CAPTION_SUMMARY_CHARS) -> str:
    """The article's own text, trimmed to what the surface can hold."""
    return _trim_to(_article_text(article), limit)


def generate_caption(article: dict) -> str:
    """V0 caption: title first, then hook, then the facts, then CTA, tags, link.

    The order is the point. The old caption led with a generated hook, so the
    post opened with a paraphrase of a headline the reader could already see on
    the card, and the article's own claim never appeared at all. Leading with the
    verbatim headline makes the caption self-contained in the feed text, where a
    photo post is often read without the image.

    Tries Ollama/Gemini for the hook + summary. Falls back to a deterministic
    template on any failure -- the structure is never abandoned for content.
    """
    title = (article.get("title") or "Untitled").strip()
    source = article.get("source") or "Verified Source"
    link = (article.get("link") or "").strip()
    category = article.get("category") or ""
    body = _caption_body_summary(article)

    # The card image draws a "Read the full story at <source>" panel, but an
    # IMAGE CANNOT BE A HYPERLINK. The caption is the only clickable surface on
    # a Facebook/Instagram/TikTok photo post, so the link must be here -- the
    # card is the visual cue, this is the destination.
    link_line = f"\n\nRead the full story at {source}: {link}" if link else \
                "\n\nRead the full story in the comments."

    hook = summary = ""

    # No article text: there is nothing to summarise, and inventing a summary
    # would be the "unsupported detail" this function exists to avoid. Title and
    # link only -- no hook, no CTA pretending there is something to discuss.
    if not body:
        return f"{title}{link_line}"

    try:
        from utils.llm_helper import get_llm
        llm = get_llm(temperature=0.4, max_tokens=400, agent_id="viral_caption")
        prompt = f"""Write two parts for a social media post about this news article.

HOOK: one line, under 12 words, that makes someone want to read on. No clickbait
that the article does not support.
BODY: 2-4 sentences stating what the article actually says. Under 400 characters.

Rules:
- Use ONLY facts present in the summary below. Do not add names, numbers, dates,
  causes or consequences that are not written there.
- No links, URLs or hashtags. Those are added separately.
- Plain text, no markdown.

Article headline: {title}
Source: {source}
Category: {category}
Article summary: {body}

Return exactly two lines:
HOOK: <your hook>
BODY: <your summary>"""
        resp = llm.call([{"role": "user", "content": prompt}])
        if resp and len(str(resp).strip()) > 20:
            raw = str(resp).strip()
            m = re.search(r"HOOK\s*:\s*(.+?)\s*(?:\n\s*BODY\s*:|\Z)", raw, re.S | re.I)
            b = re.search(r"BODY\s*:\s*(.+)\Z", raw, re.S | re.I)
            if m and b:
                hook = " ".join(m.group(1).split())[:140]
                summary = " ".join(b.group(1).split())[:_CAPTION_SUMMARY_CHARS + 60]
            else:
                logger.warning("[viral] caption LLM reply missing HOOK/BODY markers")
    except Exception as e:
        logger.warning("[viral] LLM caption failed, using template: %s", e)

    # A hook that only restates the headline makes the caption open with the same
    # sentence twice. The title already did that job -- drop it. Compared on
    # word sets, not equality: "Quantum lab opens in Nepal" is not the same string
    # as the headline but is just as redundant next to it.
    if hook:
        def _keyset(s):
            return {w.lower() for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 3}
        ht, hk = _keyset(title), _keyset(hook)
        if hk and (hk <= ht or hk & ht) and len(hk & ht) >= max(1, len(hk) - 1):
            hook = ""

    # Without a usable summary, the article's own text is the summary.
    if not summary:
        summary = body
    parts = [title]
    if hook:
        parts.append(hook)
    parts.append(summary)
    parts.append(_VIRAL_CTA)
    parts.append(_hashtags(article))
    return "\n\n".join(parts) + link_line


def _spotlight_background(W: int, H: int) -> Image.Image:
    """Concept B: a dark base with a soft spotlight bloom behind the headline.

    Built as a vertical ramp instead of a blur, because a blur over a 1080px
    canvas is the single slowest thing in image generation and buys nothing
    that a 3-stop ramp does not.
    """
    from utils.brand_palette import LICORICE, SPOTLIGHT_RAMP, hex_to_rgb, lerp

    base = hex_to_rgb(LICORICE)
    # Where the glow peaks, as a fraction of height (upper third = headline zone).
    peak = 0.34
    span = 0.62

    img = Image.new("RGB", (1, H))
    px = img.load()
    for row in range(H):
        d = abs((row / H) - peak) / span
        # ease-out so the glow falls off fast and the bottom stays near-black
        w = max(0.0, 1.0 - d) ** 2
        if w <= 0.001:
            px[0, row] = base
            continue
        # Two ramp stops, weighted by w, keeps it cheap and predictable.
        pos = w * (len(SPOTLIGHT_RAMP) - 1)
        i = min(int(pos), len(SPOTLIGHT_RAMP) - 2)
        blend = lerp(SPOTLIGHT_RAMP[i], SPOTLIGHT_RAMP[i + 1], pos - i)
        px[0, row] = tuple(
            round(base[c] + (blend[c] - base[c]) * w) for c in range(3)
        )
    return img.resize((W, H), Image.BILINEAR)


def generate_image(article: dict, index: int = 0) -> str:
    """Generate a branded news card (Concept B — Gradient Spotlight).

    Layout:
      - Licorice base with a spotlight bloom behind the headline
      - Full-width gradient accent strip at the top
      - SOURCE eyebrow (D39: was category + date -- this card exists to send
        people to a specific publisher, so the publisher goes first)
      - The article's own headline, verbatim
      - The article's own summary, wrapped, between the headline and the divider.
        A headline alone makes the reader tap through to learn what happened;
        the summary is what earns the second of attention. Article words only.
      - Orange divider
      - A "Read the full story" panel naming the SOURCE, which is the visual
        half of the click-through; the other half is the link the post caption
        must carry (see generate_caption). An image cannot be a hyperlink, so
        the card points at it and the caption delivers it.
      - Original article URL printed small, for people reading the image itself

    Returns path to the generated PNG.
    """
    if not HAS_PIL:
        logger.warning("[viral] PIL not available, skipping image generation")
        return ""

    _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    from utils.brand_palette import (LICORICE, LIGHT_ORANGE, ORANGE, PINK, PURPLE,
                                     VIOLET, WHITE)

    # Verbatim, no slice. The wrap (max 5 lines) is what bounds the headline; a
    # character cut here would silently edit a publisher's words, which is the one
    # thing this card must never do. A >5-line title loses its tail to the wrap
    # and the card still lays out correctly -- proven by
    # test_long_headline_still_renders_and_keeps_its_panel.
    title = (article.get("title") or "Breaking News").strip()
    source = article.get("source", "Verified Source")
    link = (article.get("link") or "").strip()
    # D39: the card eyebrow is the source, so `category` and the date stamp left
    # generate_image entirely. The category is still carried on the caption and
    # in Firestore, where it filters and sorts.

    W, H = _IMAGE_WIDTH, _IMAGE_HEIGHT
    img = _spotlight_background(W, H)
    draw = ImageDraw.Draw(img, "RGBA")

    # Gradient accent strip across the top, in the brand ramp order.
    bar_h = int(H * 0.035)
    ramp = (PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE)
    for col in range(W):
        pos = col / max(W - 1, 1) * (len(ramp) - 1)
        i = min(int(pos), len(ramp) - 2)
        draw.line([(col, 0), (col, bar_h)],
                  fill=(*_mix(ramp[i], ramp[i + 1], pos - i), 255))

    # Fonts: display serif for the headline, sans for everything else. Sizes come
    # from _CARD_SCALE so the review renderer can compare competing scales. The
    # headline scale is fitted first, because a headline that will not fit is made
    # smaller rather than cut -- see _title_scale_for.
    s = _CARD_SCALE
    margin = int(W * 0.075)
    max_line_w = W - margin * 2
    title_scale = _title_scale_for(draw, title, H, W, margin)
    try:
        font_eyebrow = ImageFont.truetype(_FONT_PATH, int(H * s["eyebrow"]))
        font_title = ImageFont.truetype(_SERIF_FONT_PATH, int(H * title_scale))
        font_body = ImageFont.truetype(_FONT_PATH, int(H * s["body"]))
        font_src = ImageFont.truetype(_FONT_PATH, int(H * s["src"]))
        font_cta = ImageFont.truetype(_FONT_PATH, int(H * s["cta"]))
        font_url = ImageFont.truetype(_FONT_PATH, int(H * s["url"]))
    except Exception:
        font_eyebrow = font_title = font_body = font_src = font_cta = font_url = ImageFont.load_default()
        title_scale = s["title"]

    # Headline: the article's own title, verbatim. Never reworded -- a headline the
    # publisher did not write is a misattribution, and never sliced either: the
    # scale is fitted instead. Only the line count is capped.
    headline_lines = _wrap_text(draw, title, font_title, max_line_w)
    # The article's own summary, between the headline and the divider. This is
    # what makes the card worth a second of looking: a headline alone makes the
    # reader tap through to learn what happened. Only ever the article's own
    # words -- no generated detail (see generate_caption).
    summary_text = _caption_body_summary(article, limit=_CARD_SUMMARY_CHARS)
    summary_lines = _wrap_text(draw, summary_text, font_body, max_line_w) if summary_text else []
    # Every y on the card comes from here, including the eyebrow. The eyebrow
    # used to be drawn at its own inline `bar_h + 0.05H` while the headline took
    # the centred value, so centring moved the headline down and left the
    # eyebrow stranded above it -- caught by the review script's top-gap
    # measurement reporting a constant 5.6% on every card.
    lay = _card_layout(len(headline_lines), len(summary_lines), H,
                       line_spacing=int(H * title_scale * 1.20))

    # Eyebrow: the SOURCE, not the category. This card exists to send people to a
    # specific publisher, so the first thing on it is who is reporting it. The
    # category was a topic label the reader already knows from the feed.
    draw.text((margin, lay["eyebrow_y"]), source.upper(),
              fill=LIGHT_ORANGE, font=font_eyebrow)

    for i, line in enumerate(headline_lines[:lay["n_headline"]]):
        draw.text((margin, lay["headline_y"] + i * lay["line_spacing"]),
                  line, fill=WHITE, font=font_title)

    for i, line in enumerate(summary_lines[:lay["n_summary"]]):
        draw.text((margin, lay["summary_y"] + i * lay["body_line_h"]),
                  line, fill=(255, 255, 255, 205), font=font_body)

    # Divider
    div_y = lay["div_y"]
    draw.line([(margin, div_y), (W - margin, div_y)], fill=ORANGE, width=4)

    # "Read the full story" panel — the click-through cue. Bottom-anchored, so it
    # lands in the same place on every card regardless of headline length.
    panel_y, panel_h = lay["panel_y"], lay["panel_h"]
    draw.rounded_rectangle(
        [margin, panel_y, W - margin, panel_y + panel_h],
        radius=int(H * 0.014), fill=(255, 255, 255, 22),
        outline=(*_mix(PURPLE, VIOLET, 0.5), 200), width=3,
    )
    pad = int(H * 0.018)
    draw.text((margin + pad, panel_y + pad),
              "Read the full story", fill=WHITE, font=font_src)
    draw.text((margin + pad, panel_y + pad + int(H * 0.042)),
              f"at {source}", fill=LIGHT_ORANGE, font=font_cta)
    # Arrow, so it reads as an affordance rather than a caption.
    ax = W - margin - pad
    ay = panel_y + panel_h // 2
    for dx, dy in ((-int(H * 0.022), -int(H * 0.022)),
                   (0, 0),
                   (-int(H * 0.022), int(H * 0.022))):
        draw.line([(ax, ay), (ax + dx, ay + dy)], fill=PURPLE, width=5)

    # The URL itself, small, for anyone reading the image.
    if link:
        host = link.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
        draw.text((margin, lay["url_y"]), host, fill=(255, 255, 255, 150), font=font_url)

    out_path = str(_TEMP_DIR / f"viral_post_{int(time.time())}_{index}.png")
    img.save(out_path, "PNG", optimize=True)
    logger.info("[viral] Generated image: %s (source=%s)", out_path, source)
    return out_path


def _title_scale_for(draw, title: str, H: int, W: int, margin: int) -> float:
    """Largest title scale whose wrap still fits `_CARD_MAX_HEADLINE_LINES`.

    This exists because raising the title scale made a locked invariant fail for
    real: at 0.075 a 149-character headline wraps to 6 lines, so the 5-line cap
    dropped its tail -- the card was showing a headline the publisher did not
    write in that form. The 0.058 scale this replaced happened to fit that title
    in 5 lines, which is exactly why the defect was invisible until the type got
    bigger.

    A headline is a publisher's own words, so a title that will not fit is made
    smaller rather than cut. Below `_CARD_TITLE_MIN_SCALE` we stop shrinking and
    accept the cap, because a 5-line card is a worse outcome than a 6-line one
    with the last line dropped.
    """
    max_w = W - margin * 2
    scale = _CARD_SCALE["title"]
    while True:
        try:
            f = ImageFont.truetype(_SERIF_FONT_PATH, max(1, int(H * scale)))
        except Exception:
            return scale
        if len(_wrap_text(draw, title, f, max_w)) <= _CARD_MAX_HEADLINE_LINES:
            return scale
        if scale <= _CARD_TITLE_MIN_SCALE:
            return _CARD_TITLE_MIN_SCALE
        scale = round(scale - 0.005, 4)


def _card_layout(n_headline: int, n_summary: int, H: int,
                 line_spacing: int | None = None) -> dict:
    """Y positions for the card's blocks, given how many lines each wrapped to.

    Extracted from the drawing code because the ordering (headline, then summary,
    then divider, then panel) was previously only implicit in a running `y`.
    That made the invariant untestable: a pixel diff between "card with a body"
    and "card without" moves the DIVIDER as well as the summary, so the diff top
    reports the divider, not the summary -- a fixed-y summary and a correct one
    produced identical diffs (measured, not assumed).

    The panel and the URL are BOTTOM-ANCHORED. They used to float at
    `div_y + pad`, which meant the card's dead space was whatever the headline
    happened to leave: 39% of a 1080px card on a 2-line headline, 21% on a
    4-line one (measured across real article shapes). Anchoring them to fixed
    offsets from the bottom edge means a 2-line and a 5-line headline both fill
    the frame, and the click-through cue sits in the same place on every card.

    Overlap is impossible by construction, not by clamp: the summary is allowed
    only as many lines as physically fit between the headline and the divider,
    and the headline likewise. A longer input draws fewer lines; it never draws
    on top of the panel. That replaced `panel_fits`, which became vacuous once
    the panel stopped moving (a test that cannot fail is worse than no test --
    the same lesson as the dead duplicate-query test in test_stock_query_order).

    Returns a dict of y positions plus the line counts that are actually safe to
    draw. Pure arithmetic on ints, so it is testable without PIL or fonts.
    """
    bar_h = int(H * 0.035)
    if line_spacing is None:
        line_spacing = int(H * _CARD_SCALE["line"])
    body_line_h = int(H * _CARD_SCALE["body_line"])

    # Bottom-anchored blocks, fixed for every card.
    panel_h = int(H * 0.105)
    panel_y = H - int(H * 0.075) - panel_h
    url_y = H - int(H * 0.038)

    eyebrow_y = bar_h + int(H * 0.050)
    headline_y = eyebrow_y + int(H * 0.062)

    gap = int(H * 0.030)
    # The divider is the ceiling for the summary, and the panel is the ceiling
    # for the divider.
    div_max = panel_y - int(H * 0.045)

    n_headline = max(0, min(n_headline, _CARD_MAX_HEADLINE_LINES))
    n_summary = max(0, min(n_summary, _CARD_MAX_SUMMARY_LINES))
    # The headline is a locked rule, so it is never cut -- if it genuinely cannot
    # fit, the summary is what gives way, and below that the summary goes away
    # entirely rather than overlapping.
    n_headline = min(n_headline, max(0, (div_max - headline_y) // line_spacing))
    summary_y = headline_y + n_headline * line_spacing + gap
    room = div_max - summary_y - int(H * 0.028)
    n_summary = min(n_summary, max(0, room // body_line_h))

    summary_h = n_summary * body_line_h
    div_y = summary_y + summary_h + (int(H * 0.028) if n_summary else 0)

    # Centre the text block in the slack above the panel. Bottom-anchoring alone
    # fixed the panel but left a hole on a short card: a 2-line headline with a
    # 1-line summary still measured 36% dead. Splitting the slack above and below
    # the block turns that hole into balanced padding. The panel stays put -- it
    # is the constant, the text is the variable.
    shift = max(0, div_max - div_y) // 2
    eyebrow_y += shift
    headline_y += shift
    summary_y += shift
    div_y += shift

    return {
        "eyebrow_y": eyebrow_y,
        "headline_y": headline_y,
        "line_spacing": line_spacing,
        "n_headline": n_headline,
        "summary_y": summary_y,
        "body_line_h": body_line_h,
        "n_summary": n_summary,
        "div_y": div_y,
        "panel_y": panel_y,
        "panel_h": panel_h,
        "url_y": url_y,
    }


def _mix(a: str, b: str, t: float) -> tuple:
    """Local alias so the card body stays readable; see brand_palette.lerp."""
    from utils.brand_palette import lerp
    return lerp(a, b, t)



def _wrap_text(draw, text: str, font, max_width: int) -> list:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ═══════════════════════════════════════════════════════════════════════════
# Telegram notification
# ═══════════════════════════════════════════════════════════════════════════

def _send_telegram_notification(title: str, platforms_results: dict,
                                 score: int = 0, category: str = "") -> bool:
    """Send Telegram notification about a published viral post.

    Uses direct Telegram API call (same as multi_platform_publisher).
    Respects notification preferences from config.
    """
    try:
        config = get_viral_config()
        bot_token = config.get("telegram_bot_token", "")
        chat_id = config.get("telegram_chat_id", "")
        if not bot_token or not chat_id:
            logger.info("[viral] Telegram not configured, skipping notification")
            return False

        # Check notification preferences
        event_type = "viral" if score >= VIRAL_THRESHOLD else "scheduled"
        pref_key = f"telegram_notify_on_{event_type}"
        if not config.get(pref_key, True):
            return False

        import requests as _req
        platform_lines = []
        for plat, r in platforms_results.items():
            if r.get("success"):
                icon = "✅"
                platform_lines.append(f"{icon} {plat.title()}: {r.get('url', 'posted')}")
            else:
                icon = "❌"
                platform_lines.append(f"{icon} {plat.title()}: {r.get('error', 'unknown')}")

        score_line = f"Virality score: {score}/100" if score else ""
        category_line = f"Category: {category}" if category else ""

        message = (
            f"📡 *Viral Post Published!*\n"
            f"{category_line}\n"
            f"{score_line}\n"
            f"🕐 {now_npt()}\n"
            f"📝 {title[:80]}"
        )
        if platform_lines:
            message += "\n\n" + "\n".join(platform_lines)

        _req.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=30,
        )
        logger.info("[viral] Telegram notification sent")
        return True
    except Exception as e:
        logger.warning("[viral] Telegram notification failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Social media posting (Facebook/Instagram photo posts)
# ═══════════════════════════════════════════════════════════════════════════
_PAGE_TOKEN_CACHE: dict = {}


def _page_access_token() -> str:
    """Resolve a Page-scoped token from the user token via /me/accounts.

    Photo posts to a Page require a Page token; the stored user token only
    carries publish_video. Resolved token is cached in-process AND persisted
    to Firestore platform_settings/facebook.access_token so it survives
    restarts without a live /me/accounts round-trip.

    A Graph error/empty body is logged loudly (was silently returning "" and
    failing every FB post) and retried once before giving up.
    """
    user_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    page_id = str(os.getenv("FACEBOOK_PAGE_ID", ""))
    if not user_token or not page_id:
        return ""
    cached = _PAGE_TOKEN_CACHE.get((user_token, page_id))
    if cached:
        return cached

    # Warm-from-Firestore: reuse last resolved page token before querying Graph.
    try:
        settings = _get_firestore().collection("platform_settings").document("facebook").get()
        stored = (settings.get("access_token") or "") if settings.exists else ""
        if stored:
            _PAGE_TOKEN_CACHE[(user_token, page_id)] = stored
            return stored
    except Exception as e:
        logger.warning("[viral] FB token Firestore read failed (continuing): %s", e)

    for attempt in (1, 2):
        try:
            resp = requests.get(
                "https://graph.facebook.com/v25.0/me/accounts",
                params={"access_token": user_token},
                timeout=15,
            )
            body = resp.json()
            if resp.status_code != 200 or "data" not in body:
                logger.warning(
                    "[viral] FB /me/accounts failed (attempt %d): status=%s body=%s",
                    attempt, resp.status_code, str(body)[:300],
                )
                continue
            for page in body.get("data", []):
                if str(page.get("id")) == page_id:
                    token = page.get("access_token", "")
                    if token:
                        _PAGE_TOKEN_CACHE[(user_token, page_id)] = token
                        try:
                            _get_firestore().collection("platform_settings").document(
                                "facebook"
                            ).set({"access_token": token}, merge=True)
                        except Exception as e:
                            logger.warning("[viral] FB token Firestore save failed: %s", e)
                        return token
            logger.warning(
                "[viral] FB /me/accounts returned no match for page_id=%s (attempt %d)",
                page_id, attempt,
            )
        except Exception as e:
            logger.warning("[viral] Failed to resolve FB page token (attempt %d): %s", attempt, e)
    return ""


def _fb_post_photo(image_path: str, caption: str) -> dict:
    """Post a photo to Facebook Page via Graph API (requires Page token)."""
    page_id = os.getenv("FACEBOOK_PAGE_ID")
    if not page_id:
        return {"success": False, "platform": "facebook", "error": "FB credentials not configured"}
    access_token = _page_access_token()
    if not access_token:
        return {"success": False, "platform": "facebook", "error": "No FB page access token"}

    if not os.path.exists(image_path):
        return {"success": False, "platform": "facebook", "error": f"Image not found: {image_path}"}

    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/v25.0/{page_id}/photos",
                params={"access_token": access_token},
                files={"source": f},
                data={"message": caption},
                timeout=120,
            )
        result = resp.json()
        if "id" in result:
            logger.info("[viral] Facebook photo posted: %s", result["id"])
            return {"success": True, "platform": "facebook", "post_id": result["id"],
                    "url": f"https://facebook.com/{page_id}/posts/{result['id']}"}
        return {"success": False, "platform": "facebook", "error": result.get("error", {}).get("message", "Unknown")}
    except Exception as e:
        logger.error("[viral] Facebook post failed: %s", e)
        return {"success": False, "platform": "facebook", "error": str(e)}


def _ig_post_photo(image_path: str, caption: str) -> dict:
    """Post a photo to Instagram via Graph API media-container flow.

    IG requires a public image_url (R2 presigned) — not a file upload.
    Steps: create media container -> poll status -> publish.
    Mirrors the working _upload_instagram() video flow in
    multi_platform_publisher.py (ponytail: reuse, don't reinvent).
    """
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    if not access_token or not ig_account_id:
        return {"success": False, "platform": "instagram", "error": "IG credentials not configured"}

    if not os.path.exists(image_path):
        return {"success": False, "platform": "instagram", "error": f"Image not found: {image_path}"}

    try:
        import uuid as _uuid
        from utils.r2_storage import get_r2_client, generate_presigned_url

        # 1. Upload image to R2 and get a presigned public URL (expires in 1h).
        client = get_r2_client()
        key = f"viral/{_uuid.uuid4().hex}.jpg"
        with open(image_path, "rb") as inf:
            client.upload_fileobj(
                inf, os.getenv("CLOUDFLARE_R2_BUCKET", "vyom-ai-videos"), key,
                ExtraArgs={"ContentType": "image/jpeg"},
            )
        image_url = generate_presigned_url(key, expires_in=3600)

        base = f"https://graph.facebook.com/v25.0/{ig_account_id}"

        # 2. Create media container (image_url, no media_type = photo).
        create_resp = requests.post(
            f"{base}/media",
            params={"access_token": access_token, "image_url": image_url, "caption": caption},
            timeout=60,
        )
        result = create_resp.json()
        creation_id = result.get("id")
        if not creation_id:
            return {"success": False, "platform": "instagram",
                    "error": result.get("error", {}).get("message", str(result))[:400]}

        # 3. Poll container status until FINISHED.
        poll_finished = False
        for _ in range(60):
            status_resp = requests.get(
                f"https://graph.facebook.com/v25.0/{creation_id}",
                params={"access_token": access_token, "fields": "status_code"},
                timeout=30,
            )
            if status_resp.status_code == 200:
                status_code = status_resp.json().get("status_code")
                if status_code == "FINISHED":
                    poll_finished = True
                    break
                if status_code == "ERROR":
                    return {"success": False, "platform": "instagram",
                            "error": f"IG media processing failed: {status_resp.json()}"}
            time.sleep(5)
        if not poll_finished:
            return {"success": False, "platform": "instagram", "error": "IG media processing timed out"}

        # 4. Publish the container.
        publish_resp = requests.post(
            f"{base}/media_publish",
            params={"access_token": access_token, "creation_id": creation_id},
            timeout=60,
        )
        media_id = publish_resp.json().get("id", creation_id) if publish_resp.status_code == 200 else ""
        if not media_id:
            return {"success": False, "platform": "instagram",
                    "error": publish_resp.json().get("error", {}).get("message", "publish failed")[:400]}
        logger.info("[viral] Instagram photo posted: %s", media_id)
        return {"success": True, "platform": "instagram", "post_id": media_id,
                "url": f"https://www.instagram.com/p/{media_id}/"}
    except Exception as e:
        logger.error("[viral] Instagram post failed: %s", e)
        return {"success": False, "platform": "instagram", "error": str(e)}


def _tt_post_photo(image_path: str, caption: str) -> dict:
    """Exception-safe wrapper: TikTok must never abort a viral post.

    IG/FB helpers swallow their own exceptions; this one does too so a
    transient R2/network error can't skip the Firestore save + image cleanup
    after FB/IG already landed (and can't break dedup for the next scan).
    """
    try:
        return _tt_post_photo_impl(image_path, caption)
    except Exception as e:
        logger.error("[viral] TikTok photo post failed: %s", e)
        return {"success": False, "platform": "tiktok", "error": str(e)}


def _tt_post_photo_impl(image_path: str, caption: str) -> dict:
    """Post a photo to TikTok via the Content Posting API (PHOTO / DIRECT_POST).

    TikTok pulls the image from a public URL (PULL_FROM_URL). Per TikTok docs
    that URL must sit on a domain/URL-prefix that is VERIFIED in the app's
    developer portal — R2 hosts (pub-*.r2.dev / *.r2.cloudflarestorage.com)
    are not verified, so if init fails with a domain error you must: (1) serve
    the R2 bucket on a custom domain you control, (2) verify that domain in
    the TikTok portal, (3) set VIRAL_IMAGE_URL_BASE=https://<your-domain> and
    the key suffix is appended. Falls back to an R2 presigned URL otherwise.
    Privacy comes from TIKTOK_PRIVACY_LEVEL (SELF_ONLY until the Direct Post
    audit grants public posting). Non-fatal: caller still posts FB/IG.
    """
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        return {"success": False, "platform": "tiktok", "error": "TikTok token not configured"}

    if not os.path.exists(image_path):
        return {"success": False, "platform": "tiktok", "error": f"Image not found: {image_path}"}

    _tt_refresh_attempted = [False]

    def _do_init(_token: str) -> requests.Response:
        import uuid as _uuid
        from utils.r2_storage import get_r2_client, generate_presigned_url

        client = get_r2_client()
        key = f"viral/{_uuid.uuid4().hex}.jpg"
        with open(image_path, "rb") as inf:
            client.upload_fileobj(
                inf, os.getenv("CLOUDFLARE_R2_BUCKET", "vyom-ai-videos"), key,
                ExtraArgs={"ContentType": "image/jpeg"},
            )
        base = os.getenv("VIRAL_IMAGE_URL_BASE", "").rstrip("/")
        image_url = f"{base}/{key}" if base else generate_presigned_url(key, expires_in=3600)

        privacy_level = os.getenv("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY")
        return requests.post(
            "https://open.tiktokapis.com/v2/post/publish/content/init/",
            headers={
                "Authorization": f"Bearer {_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={
                "source_info": {"source": "PULL_FROM_URL",
                                "photo_images": [{"url": image_url, "index": 1}]},
                "post_mode": "DIRECT_POST",
                "media_type": "PHOTO",
                "post_info": {
                    "title": caption.strip()[:90],
                    "description": caption[:4000],
                    "privacy_level": privacy_level,
                    "is_aigc": os.getenv("TIKTOK_IS_AIGC", "false").lower() == "true",
                    "disable_comment": False,
                    "disable_duet": True,
                    "disable_stitch": True,
                },
            },
            timeout=30,
        )

    init_resp = _do_init(access_token)
    if init_resp.status_code == 401 and not _tt_refresh_attempted[0]:
        _tt_refresh_attempted[0] = True
        try:
            from utils.multi_platform_publisher import _refresh_tiktok_token
            refreshed = _refresh_tiktok_token()
        except Exception as refresh_err:
            logger.warning("[viral] TikTok token refresh failed: %s", refresh_err)
            refreshed = None
        if refreshed:
            access_token = refreshed
            init_resp = _do_init(access_token)

    if init_resp.status_code != 200:
        return {"success": False, "platform": "tiktok",
                "error": f"TikTok photo init failed: {init_resp.status_code} {init_resp.text[:400]}"}

    publish_id = init_resp.json().get("data", {}).get("publish_id")
    if not publish_id:
        return {"success": False, "platform": "tiktok",
                "error": f"TikTok init returned no publish_id: {init_resp.text[:400]}"}

    # Poll publish status (DIRECT_POST completes asynchronously).
    for _ in range(120):
        time.sleep(5)
        status_resp = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {access_token}",
                     "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
            timeout=30,
        )
        data = status_resp.json().get("data", {}) if status_resp.status_code == 200 else {}
        status = data.get("status")
        if status == "PUBLISH_COMPLETE":
            logger.info("[viral] TikTok photo posted: publish_id=%s", publish_id)
            return {"success": True, "platform": "tiktok", "publish_id": publish_id,
                    "url": f"https://www.tiktok.com/@{os.getenv('TIKTOK_USERNAME', '')}"}
        if status == "PUBLISH_FAILED":
            return {"success": False, "platform": "tiktok",
                    "error": f"TikTok publish failed: {data.get('fail_reason', '') or status_resp.text[:300]}"}

    return {"success": False, "platform": "tiktok", "error": "TikTok publish status timed out"}


# ═══════════════════════════════════════════════════════════════════════════
# Over-triggering guards
# ═══════════════════════════════════════════════════════════════════════════
def _can_post_now() -> tuple:
    """Check if we can post a viral item right now.

    Returns (can_post: bool, reason: str).
    """
    try:
        db = _get_firestore()
        live = _live_config()
        max_per_day = live["viral_max_per_day"]
        cooldown_hours = live["viral_cooldown_hours"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        docs = db.collection("viral_news_posts").where(
            "date", "==", today
        ).stream()
        today_posts = [d for d in docs if d.to_dict().get("date", "").startswith(today)]

        if len(today_posts) >= max_per_day:
            return False, f"Daily viral limit reached ({len(today_posts)}/{max_per_day})"

        if today_posts:
            last = max(today_posts, key=lambda d: d.to_dict().get("posted_at", ""))
            last_time = datetime.fromisoformat(last.to_dict()["posted_at"].replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
            if elapsed < cooldown_hours:
                return False, f"Cooldown active ({elapsed:.1f}h < {cooldown_hours}h)"

        return True, "OK"
    except Exception as e:
        logger.warning("[viral] Cooldown check failed, BLOCKING post: %s", e)
        return False, f"Firestore check failed, blocking ({e})"


def _already_posted(url: str) -> bool:
    """True if this article URL was already posted recently (dedup).

    Prevents rescanning the same top story (which currently gets re-picked
    on every 5-min scan and re-posted/retried). Skips on any Firestore error
    so transient failures never cascade into a false "already posted".
    """
    if not url:
        return False
    try:
        db = _get_firestore()
        for d in db.collection("viral_news_posts").where("url", "==", url).limit(5).stream():
            if d.to_dict().get("url") == url:
                return True
        return False
    except Exception as e:
        logger.warning("[viral] Dedup check failed, NOT blocking: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Core agent functions
# ═══════════════════════════════════════════════════════════════════════════
def run_viral_check(forced: bool = False) -> dict:
    """Check for viral news and post immediately if score >= VIRAL_THRESHOLD.

    This is the main entry point called by the scheduler every 5 minutes.
    Returns a summary dict.

    Ponytail: polling interval is 5 min — adjust via VIRAL_CHECK_INTERVAL
    env var if needed.
    """
    result = {"checked": 0, "viral_posted": 0, "held": 0, "errors": []}

    # Check if agent is active (unless forced via test)
    if not forced and not is_agent_active():
        logger.info("[viral] Agent paused (active=false in config)")
        result["skipped"] = "Agent paused"
        return result

    try:
        can_post, reason = _can_post_now()
        if not can_post and not forced:
            logger.info("[viral] Skipping viral check: %s", reason)
            result["skipped"] = reason
            log_viral_activity("scan_complete", {
                "skipped": reason, "checked": 0, "viral_posted": 0,
                "held": 0, "highest_score": 0,
            })
            return result
    except Exception as e:
        logger.warning("[viral] Can-post check failed: %s", e)

    log_viral_activity("scan_start", {})

    articles = fetch_candidate_articles()
    if not articles:
        logger.info("[viral] No candidate articles found")
        log_viral_activity("scan_complete", {
            "checked": 0, "viral_posted": 0, "held": 0, "highest_score": 0,
        })
        return result

    highest_score = 0
    scored_stories = []

    for article in articles:
        result["checked"] += 1
        try:
            score = score_virality(article)
            article_score = score["virality_score"]
            scored_stories.append({
                "title": article.get("title", "?")[:160],
                "source": article.get("source", ""),
                "category": article.get("category", ""),
                "link": article.get("link", ""),
                "published_at": article.get("published_at", ""),
                "virality_score": article_score,
                "score_breakdown": score["breakdown"],
                "is_viral": score["is_viral"],
                "is_hold": score["is_hold"],
            })
            if article_score > highest_score:
                highest_score = article_score
            logger.info("[viral] %s → score=%d (%s)", article.get("title", "?")[:60],
                        article_score, score["breakdown"])

            if score["is_viral"]:
                if _already_posted(article.get("link", "")):
                    logger.info("[viral] Skipping already-posted story: %s",
                                article.get("title", "?")[:50])
                    continue
                can_post, reason = _can_post_now()
                if not can_post:
                    logger.info("[viral] Stopping scan mid-batch: %s", reason)
                    break
                posted = _publish_viral_post(article, score)
                if posted:
                    result["viral_posted"] += 1
                else:
                    result["errors"].append(f"Publish failed: {article.get('title', '?')[:50]}")
            elif score["is_hold"]:
                result["held"] += 1
                logger.info("[viral] Held for review: %s (score=%d)",
                            article.get("title", "?")[:50], article_score)
        except Exception as e:
            logger.error("[viral] Error processing article: %s", e)
            result["errors"].append(str(e)[:200])

    # Persist top-8 scored stories each scan -> live feed for the dashboard.
    _save_score_insights(scored_stories)

    log_viral_activity("scan_complete", {
        "checked": result["checked"], "viral_posted": result["viral_posted"],
        "held": result["held"], "highest_score": highest_score,
        "errors": len(result["errors"]),
    })

    return result


def is_agent_active() -> bool:
    """Check if the viral agent is enabled in Firestore config.

    Returns True if active (default). Returns False only if explicitly
    disabled via the dashboard toggle.
    """
    try:
        config = get_viral_config()
        return config.get("active", True)
    except Exception:
        return True


def test_now():
    """Force-run a viral check immediately (for manual testing).

    Bypasses:
      - Agent active check
      - Cooldown timer
      - Schedule timing

    Use from dashboard 'Run Now' button or CLI:
      python -m utils.viral_news_agent --test
    """
    logger.info("[viral] TEST MODE — running forced viral check")
    log_viral_activity("test_started", {})
    result = run_viral_check(forced=True)
    log_viral_activity("test_completed", result)
    return result


def _publish_viral_post(article: dict, score: dict) -> bool:
    """Generate content and publish a viral post to Facebook + Instagram."""
    if _already_posted(article.get("link", "")):
        logger.info("[viral] Dedup: article already posted, skipping: %s",
                    article.get("title", "?")[:50])
        return False
    can_post, reason = _can_post_now()
    if not can_post:
        logger.info("[viral] Blocked by guard, not posting: %s", reason)
        return False
    logger.info("[viral] Publishing VIRAL post: %s", article.get("title", "?")[:60])

    # Generate caption
    caption = generate_caption(article)

    # Generate image
    image_path = generate_image(article)
    if not image_path:
        logger.warning("[viral] No image generated, posting text-only to Facebook")
        image_path = ""

    # Post to platforms
    platform_results = {}

    if image_path:
        ig_result = _ig_post_photo(image_path, caption)
        fb_result = _fb_post_photo(image_path, caption)
        platform_results["instagram"] = ig_result
        platform_results["facebook"] = fb_result

        tt_result = _tt_post_photo(image_path, caption)
        platform_results["tiktok"] = tt_result

        # Clean up temp image
        try:
            os.remove(image_path)
        except OSError:
            pass
    else:
        fb_result = _fb_post_photo("", caption)
        platform_results["facebook"] = fb_result

    # YouTube Community post (text) — gated by ENABLE_COMMUNITY_POSTS.
    # Run in a worker thread with a short timeout: expired Studio cookies
    # trigger a 120s interactive login wait inside playwright which must never
    # stall the viral scan (09-22: FB post landed ~3min late behind it).
    yt_caption = f"{caption}\n\n{article.get('link', '')}"
    yt_ok = False
    try:
        import threading

        _yt_holder = {}

        def _post_yt():
            from utils.community_manager import post_community_text
            _yt_holder["ok"] = post_community_text(yt_caption)

        _t = threading.Thread(target=_post_yt, daemon=True)
        _t.start()
        _t.join(timeout=10)
        if _t.is_alive():
            logger.warning("[viral] YouTube community post timed out (>10s), skipping")
            yt_ok = False
        else:
            yt_ok = bool(_yt_holder.get("ok", False))
    except Exception as cm_err:
        logger.warning("[viral] YouTube community post failed: %s", cm_err)
        yt_ok = False
    platform_results["youtube_community"] = {
        "success": yt_ok, "platform": "youtube_community",
        "url": "https://studio.youtube.com" if yt_ok else "",
    }

    # Save to Firestore for audit
    _save_post_firestore({
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "category": article.get("category", ""),
        "virality_score": score["virality_score"],
        "score_breakdown": score["breakdown"],
        "caption": caption,
        "image_path": image_path if os.path.exists(image_path) else "",
        "platform_results": platform_results,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "posted_at_npt": utc_to_npt(datetime.now(timezone.utc).isoformat()),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "url": article.get("link", ""),
        "type": "viral_realtime",
    })

    # Log activity for dashboard
    any_success = any(r.get("success") for r in platform_results.values())
    if any_success:
        log_viral_activity("viral_posted", {
            "title": article.get("title", "")[:100],
            "category": article.get("category", ""),
            "score": score["virality_score"],
            "platforms": list(platform_results.keys()),
        })

    # Send Telegram notification on success
    if any_success:
        config = get_viral_config()
        if config.get("telegram_notify_on_viral", True):
            _send_telegram_notification(
                title=article.get("title", "")[:100],
                platforms_results=platform_results,
                score=score["virality_score"],
                category=article.get("category", ""),
            )

    # Log summary
    for plat, r in platform_results.items():
        status = "✅" if r.get("success") else "❌"
        logger.info("[viral] %s: %s %s", plat, status, r.get("url", r.get("error", "")))

    return any_success


def run_scheduled_post(scheduled_time: str = None) -> dict:
    """Generate and post a scheduled news post at 10:30 AM or 8:30 PM.

    This picks the best non-viral article from today's feed and posts it
    as a planned post. Reuses the same caption/image pipeline as viral
    posts so the output is consistent.
    """
    result = {"scheduled": False, "time": scheduled_time, "error": ""}

    if not is_agent_active():
        result["error"] = "Agent paused"
        return result

    try:
        can_post, reason = _can_post_now()
        if not can_post:
            result["error"] = f"Blocked by cooldown: {reason}"
            logger.info("[viral] Scheduled post blocked: %s", reason)
            log_viral_activity("scheduled_post", {
                "status": "blocked", "reason": reason,
            })
            return result
    except Exception as e:
        logger.warning("[viral] Cooldown check failed: %s", e)

    log_viral_activity("scheduled_post", {"status": "started"})

    articles = fetch_candidate_articles()
    if not articles:
        result["error"] = "No articles available"
        log_viral_activity("scheduled_post", {
            "status": "failed", "reason": "no articles",
        })
        return result

    # Pick the highest-scoring article that is NOT already posted today
    try:
        db = _get_firestore()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = [d.to_dict() for d in db.collection("viral_news_posts")
                     .where("date", "==", today).stream()]
        existing_titles = {e.get("title", "").lower() for e in existing}
    except Exception:
        existing_titles = set()

    scored = []
    for a in articles:
        if a.get("title", "").lower().strip() in existing_titles:
            continue
        s = score_virality(a)
        scored.append((s, a))

    if not scored:
        result["error"] = "All articles already posted today"
        log_viral_activity("scheduled_post", {
            "status": "failed", "reason": "all posted",
        })
        return result

    # For scheduled posts, pick highest scored article (not necessarily viral)
    scored.sort(key=lambda x: x[0]["virality_score"], reverse=True)
    best_score, best_article = scored[0]

    logger.info("[viral] Scheduled post: %s (score=%d)", best_article.get("title", "?")[:60],
                best_score["virality_score"])

    ok = _publish_viral_post(best_article, best_score)
    result["scheduled"] = ok
    result["title"] = best_article.get("title", "")
    result["virality_score"] = best_score["virality_score"]

    log_viral_activity("scheduled_post", {
        "status": "posted" if ok else "failed",
        "title": best_article.get("title", "")[:100],
        "score": best_score["virality_score"],
    })

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Entry points
# ═══════════════════════════════════════════════════════════════════════════
def main():
    """CLI entry point for testing:
      python -m utils.viral_news_agent --monitor     (continuous)
      python -m utils.viral_news_agent --once        (single forced check)
      python -m utils.viral_news_agent --scheduled   (scheduled post)
      python -m utils.viral_news_agent --test        (test mode, bypasses all guards)
    """
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "monitor"

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if mode == "once" or mode == "--once":
        r = run_viral_check(forced=True)
        print(json.dumps(r, indent=2))
    elif mode == "scheduled" or mode == "--scheduled":
        r = run_scheduled_post()
        print(json.dumps(r, indent=2))
    elif mode == "test" or mode == "--test":
        r = test_now()
        print(json.dumps(r, indent=2))
    elif mode == "monitor" or mode == "--monitor":
        interval = int(os.getenv("VIRAL_CHECK_INTERVAL", "5")) * 60
        logger.info("[viral] Monitoring mode (interval=%ds)", interval)
        while True:
            run_viral_check()
            time.sleep(interval)
    else:
        print("Usage: python -m utils.viral_news_agent [monitor|once|scheduled|test]")


if __name__ == "__main__":
    main()
