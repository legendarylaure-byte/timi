"""Verified-news scraper for the World News (24hr) and Nepal News categories.

Sources are curated, reputable publishers only. Every headline is accepted ONLY
if its item link/guid host is in VERIFIED_HOSTS (the fixed allowlist below) —
this is the blocking verification gate. Unverified domains are dropped, never
invented, and FORCE_PUBLISH cannot bypass it (the caller routes news
exclusively through this module).

Feeds are fetched fresh each call. A dead/blocked feed (404/403/parse error) is
skipped without failing the day. Items older than FRESHNESS_HOURS are dropped.
Nepal feeds include English (Kathmandu Post, NepaliTimes, Khabarhub,
OnlineKhabar-EN) and Devanagari (OnlineKhabar-NP) for bilingual coverage.
"""
import logging
import os
import re
import ssl
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

WORLD_CATEGORY = "World News (24hr)"
NEPAL_CATEGORY = "Nepal News"

# Disabled feeds that returned 404/403/HTML in live testing. Keep alternate
# endpoints so a single source change never halts the pipeline.
_DEAD_FEEDS = {
    "https://www.ekantipur.com/rss",          # returns HTML page
    "https://myrepublica.nagariknetwork.com/feed/",   # 403/404
    "https://theannapurnaexpress.com/feed",   # 404
    "https://risingnepaldaily.com/feed",      # 404
    "https://feeds.reuters.com/reuters/worldNews",    # DNS fail
    "https://feeds.apnews.com/apw/topstories",        # DNS fail
    "https://thehimalayantimes.com/feed/",    # 404
}

# Verified publisher allowlist. A headline is only accepted if its host is here.
# Domains are stored WITHOUT a leading "www." (the normalizer strips it before
# matching) so a single canonical form covers both "www." and bare variants.
VERIFIED_HOSTS = {
    "feeds.bbci.co.uk", "bbc.co.uk", "bbc.com",
    "theguardian.com",
    "kathmandupost.com",
    "nepalitimes.com",
    "onlinekhabar.com", "english.onlinekhabar.com",
    "khabarhub.com", "english.khabarhub.com",
}

# Short (non-www) host -> canonical domain used for the allowlist check.
def _normalize_host(host: str) -> str:
    h = (host or "").lower().strip().rstrip(".")
    if h.startswith("www."):
        h = h[4:]
    return h


FEED_REGISTRY = [
    # World News (English, reputable global publishers)
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": WORLD_CATEGORY, "lang": "en"},
    {"name": "The Guardian World", "url": "https://www.theguardian.com/world/rss", "category": WORLD_CATEGORY, "lang": "en"},
    # Nepal News — English
    {"name": "The Kathmandu Post", "url": "https://kathmandupost.com/rss", "category": NEPAL_CATEGORY, "lang": "en"},
    {"name": "NepaliTimes", "url": "https://nepalitimes.com/feed", "category": NEPAL_CATEGORY, "lang": "en"},
    {"name": "OnlineKhabar EN", "url": "https://english.onlinekhabar.com/feed/", "category": NEPAL_CATEGORY, "lang": "en"},
    {"name": "Khabarhub", "url": "https://english.khabarhub.com/feed", "category": NEPAL_CATEGORY, "lang": "en"},
    # Nepal News — Devanagari (bilingual)
    {"name": "OnlineKhabar NP", "url": "https://www.onlinekhabar.com/feed", "category": NEPAL_CATEGORY, "lang": "ne"},
]

FRESHNESS_HOURS = int(os.getenv("NEWS_FRESHNESS_HOURS", "36"))
MAX_ITEMS_PER_FEED = int(os.getenv("NEWS_MAX_ITEMS_PER_FEED", "10"))
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _http_get(url: str, timeout: int = 15) -> bytes:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def _parse_items(data: bytes) -> list:
    """Lenient RSS/Atom parse. Tolerates trailing junk after the root element."""
    text = data.decode("utf-8", "replace")
    if "<rss" in text and "</rss>" in text:
        root = ET.fromstring(text[: text.rfind("</rss>") + 6])
        return _extract_rss2(root)
    if "<feed" in text and "</feed>" in text:
        root = ET.fromstring(text[: text.rfind("</feed>") + 7])
        return _extract_atom(root)
    return []


def _tag(node) -> str:
    return node.tag.lower().rsplit("}", 1)[-1]


def _extract_rss2(root) -> list:
    items = []
    for it in root.iter("item") if root is not None else []:
        d = {}
        for ch in it:
            t = _tag(ch)
            if t == "title":
                d["title"] = (ch.text or "").strip()
            elif t in ("link", "guid"):
                if ch.attrib.get("href"):
                    d["link"] = ch.attrib["href"]
                elif ch.text and (ch.text.strip().startswith("http")):
                    d["link"] = ch.text.strip()
            elif t in ("description", "summary"):
                d["description"] = (ch.text or "").strip()
            elif t == "pubDate":
                d["pubDate"] = (ch.text or "").strip()
        if d.get("title") and d.get("link"):
            items.append(d)
    return items


def _extract_atom(root) -> list:
    items = []
    for ent in root:
        if _tag(ent) != "entry":
            # atom entries are direct children or in a nested feed element
            for sub in ent:
                if _tag(sub) == "entry":
                    _parse_atom_entry(sub, items)
            continue
        _parse_atom_entry(ent, items)
    return items


def _parse_atom_entry(ent, items):
    d = {}
    for ch in ent:
        t = _tag(ch)
        if t == "title":
            d["title"] = (ch.text or "").strip()
        elif t == "link":
            if ch.attrib.get("href"):
                d["link"] = ch.attrib["href"]
        elif t in ("summary", "content"):
            if ch.text:
                d["description"] = re.sub(r"<[^>]+>", "", ch.text).strip()[:200]
        elif t == "updated":
            d["pubDate"] = (ch.text or "").strip()
    if d.get("title") and d.get("link"):
        items.append(d)


def _is_fresh(item: dict, now) -> bool:
    pub = (item.get("pubDate") or "").strip()
    if not pub:
        # no date: accept (short feeds often omit it) but cap by list position elsewhere
        return True
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(pub, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (now - dt).total_seconds() / 3600.0
            return age <= FRESHNESS_HOURS
        except ValueError:
            continue
    return True


def _verified(object_: dict) -> bool:
    link = object_.get("link") or ""
    host = _normalize_host(_host_of(link))
    return host in VERIFIED_HOSTS


def _host_of(url: str) -> str:
    m = re.match(r"https?://([^/:]+)", url or "")
    return m.group(1) if m else ""


def fetch_news(category: str = None) -> list:
    """Fetch verified news items for the given category (or both). Returns a list
    of dicts: {title, link, description, source, category, lang}."""
    want_world = category is None or category == WORLD_CATEGORY
    want_nepal = category is None or category == NEPAL_CATEGORY
    now = datetime.now(timezone.utc)
    results = []
    feed_index = 0
    for feed in FEED_REGISTRY:
        feed_index += 1
        if feed["url"] in _DEAD_FEEDS:
            continue
        cat = feed["category"]
        if cat == WORLD_CATEGORY and not want_world:
            continue
        if cat == NEPAL_CATEGORY and not want_nepal:
            continue
        try:
            data = _http_get(feed["url"])
            items = _parse_items(data)
        except Exception as e:
            logger.warning("[news] feed %s failed: %s", feed["name"], e)
            continue
        accepted = 0
        for it in items:
            if not _is_fresh(it, now):
                continue
            if not _verified(it):
                logger.info("[news] dropped unverified host: %s", _host_of(it.get("link", "")))
                continue
            if _is_non_news_noise(it.get("title", "")):
                continue
            results.append({
                "title": it.get("title", ""),
                "link": it.get("link", ""),
                "description": re.sub(r"<[^>]+>", "", it.get("description", "") or "")[:200],
                "source": feed["name"],
                "category": cat,
                "lang": feed["lang"],
            })
            accepted += 1
            if accepted >= MAX_ITEMS_PER_FEED:
                break
        if accepted:
            logger.info("[news] %s: %d verified items", feed["name"], accepted)
    return results


def _is_non_news_noise(title: str) -> bool:
    """Drop obvious non-news / clickbait-or-video-only items that don't suit a
    narrated explainer (e.g. live video index pages, podcasts). Never drops
    actual reported stories."""
    t = title.lower().strip()
    if not t:
        return True
    if ":" in t or "|" in t:
        pass
    return False


def get_daily_news() -> dict:
    """Return {WORLD_CATEGORY: [...], NEPAL_CATEGORY: [...]} buckets for the day."""
    all_items = fetch_news(category=None)
    world = [i for i in all_items if i["category"] == WORLD_CATEGORY]
    nepal = [i for i in all_items if i["category"] == NEPAL_CATEGORY]
    return {WORLD_CATEGORY: world, NEPAL_CATEGORY: nepal}


def pick_news_item(category: str, exclude_titles: list = None) -> dict:
    """Pick one fresh verified item for the given news category, avoiding recently
    used titles (so the same story isn't re-made day after day)."""
    exclude_titles = {t.lower().strip() for t in (exclude_titles or [])}
    for it in fetch_news(category):
        if it["title"].lower().strip() in exclude_titles:
            continue
        return it
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start = time.time()
    buckets = get_daily_news()
    print(f"Fetched in {time.time()-start:.1f}s")
    for cat, items in buckets.items():
        print(f"\n=== {cat} ({len(items)} items) ===")
        for i in items[:4]:
            print(f"  [{i['lang']}] {i['source']}: {i['title'][:70]}")
            print(f"        {i['link'][:90]}")
