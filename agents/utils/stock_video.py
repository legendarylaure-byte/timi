import os
import time
import threading
import shutil
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from utils.subprocess_helper import safe_run, register_temp_dir
try:
    from utils.health_monitor import pexels_breaker, pixabay_breaker
except ImportError:
    from types import SimpleNamespace
    _noop_breaker = SimpleNamespace(
        is_available=lambda: True, record_success=lambda: None, record_failure=lambda: None
    )
    pexels_breaker = _noop_breaker
    pixabay_breaker = _noop_breaker

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

CLIPS_DIR = Path(__file__).parent.parent / "tmp" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
register_temp_dir(str(CLIPS_DIR))

_API_CACHE = {}
_PIXABAY_BLOCKED_UNTIL = 0.0
_PIXABAY_LOCK = threading.Lock()
_API_LAST_CALL = 0.0


def _rate_limit_delay():
    global _API_LAST_CALL
    now = time.time()
    elapsed = now - _API_LAST_CALL
    if elapsed < 0.35:
        time.sleep(0.35 - elapsed)
    _API_LAST_CALL = time.time()


PEXELS_KEYWORD_MAP = {
    "neural": ["neural network", "deep learning", "AI brain"],
    "data": ["data center", "server room", "big data"],
    "code": ["computer code", "programming", "developer coding"],
    "robot": ["robot", "automation", "robotic arm"],
    "chip": ["microchip", "processor", "circuit board"],
    "space": ["stars", "galaxy", "space", "planet"],
    "network": ["network", "cloud computing", "internet"],
    "abstract": ["abstract tech", "digital art", "technology background"],
    "office": ["modern office", "coworking space", "tech startup"],
    "analytics": ["data analytics", "dashboard", "statistics"],
    "brain": ["human brain", "neuroscience", "thinking"],
    "innovation": ["innovation", "future technology", "modern tech"],
    "science": ["laboratory", "scientist", "research"],
    "ai": ["artificial intelligence", "machine learning", "AI"],
    "education": ["online learning", "e-learning", "study"],
    "business": ["business meeting", "presentation", "corporate"],
    "phone": ["smartphone", "mobile app", "technology device"],
    "screen": ["computer screen", "monitor", "display"],
    "cloud": ["cloud computing", "cloud storage", "server cloud"],
    "engineering": ["engineering", "blueprint", "technical drawing"],
    "cybersecurity": ["cybersecurity", "data protection", "encryption"],
    "research": ["research paper", "scientific study", "analysis"],
    "startup": ["startup team", "entrepreneur", "innovation lab"],
    "digital": ["digital transformation", "digital technology", "tech"],
    "future": ["futuristic", "future tech", "technology"],
    "algorithm": ["algorithm", "data flow", "binary code"],
    "scientist": ["data scientist", "researcher", "lab work"],
    "computer": ["computer lab", "computing", "pc"],
    "math": ["mathematics", "formula", "equations"],
    "presentation": ["presentation", "conference", "tech talk"],
}

UNIVERSAL_KEYWORDS = [
    "technology background", "abstract tech", "digital network",
    "data visualization", "circuit board", "server room",
    "computer code", "artificial intelligence", "futuristic",
    "blue digital background", "abstract animation", "tech innovation",
]


def _keyword_expand(base_keyword: str) -> list[str]:
    base = base_keyword.lower().strip()
    for key, aliases in PEXELS_KEYWORD_MAP.items():
        if key in base or base in key:
            return aliases
    return [base, base + " technology", base + " abstract", base + " 4k"]


def _handle_rate_limit(resp: requests.Response, source: str, max_retries: int = 1) -> requests.Response:
    """Handle 429 rate limit. Sets cooldown for Pixabay, logs for Pexels."""
    global _PIXABAY_BLOCKED_UNTIL
    if resp.status_code != 429:
        return resp
    if source == "Pixabay":
        cooldown = 60
        print(f"[stock_video] Pixabay rate limited (429) — blocking for {cooldown}s")
        with _PIXABAY_LOCK:
            _PIXABAY_BLOCKED_UNTIL = time.time() + cooldown
        return resp
    wait_time = 10
    retry_header = resp.headers.get('Retry-After')
    if retry_header:
        try:
            wait_time = int(retry_header)
        except ValueError:
            pass
    for attempt in range(max_retries):
        print(f"[stock_video] {source} rate limited (429). Waiting {wait_time}s before retry {attempt+1}/{max_retries}")
        time.sleep(wait_time)
        new_resp = requests.get(resp.url, headers=resp.request.headers, timeout=15)
        if new_resp.status_code != 429:
            return new_resp
        wait_time *= 2
    print(f"[stock_video] {source} still rate limited after {max_retries} retries")
    return resp


def _search_cached(key: str, source: str, orientation: str) -> list[dict]:
    cache_key = f"{source}:{key}:{orientation}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    if source == "pexels":
        result = _search_pexels_uncached(key, orientation)
    else:
        result = _search_pixabay_uncached(key)
    _API_CACHE[cache_key] = result
    return result


def _search_pexels_uncached(query: str, orientation: str = "landscape") -> list[dict]:
    if not PEXELS_API_KEY:
        print("[stock_video] PEXELS_API_KEY is empty — set it in GitHub secrets")
        return []
    if not pexels_breaker.is_available():
        print("[stock_video] Pexels circuit breaker open — skipping")
        return []
    _rate_limit_delay()
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": orientation}
    try:
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=15)
        resp = _handle_rate_limit(resp, "Pexels")
        if resp.status_code == 403:
            print("[stock_video] Pexels API key invalid (403)")
            pexels_breaker.record_failure()
            return []
        resp.raise_for_status()
        pexels_breaker.record_success()
        data = resp.json()
        results = []
        for v in data.get("videos", []):
            vf = v.get("video_files", [])
            if not vf:
                continue
            best = max(vf, key=lambda f: f.get("width", 0) * f.get("height", 0))
            results.append({
                "id": v["id"],
                "url": best.get("link") or best.get("url", ""),
                "width": best.get("width", 1920),
                "height": best.get("height", 1080),
                "duration": v.get("duration", 5),
                "fps": best.get("fps", 30),
                "size": best.get("size", 0),
                "source": "pexels",
                "query": query,
            })
        return results
    except requests.exceptions.HTTPError as e:
        print(f"[stock_video] Pexels HTTP error: {e}")
        pexels_breaker.record_failure()
        return []
    except Exception as e:
        print(f"[stock_video] Pexels search error: {e}")
        pexels_breaker.record_failure()
        return []


def _search_pixabay_uncached(query: str) -> list[dict]:
    if not PIXABAY_API_KEY:
        print("[stock_video] PIXABAY_API_KEY is empty — set it in GitHub secrets")
        return []
    if not pixabay_breaker.is_available():
        print("[stock_video] Pixabay circuit breaker open — skipping")
        return []
    with _PIXABAY_LOCK:
        if time.time() < _PIXABAY_BLOCKED_UNTIL:
            remaining = int(_PIXABAY_BLOCKED_UNTIL - time.time())
            print(f"[stock_video] Pixabay blocked for {remaining}s more — skipping")
            return []
    _rate_limit_delay()
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "video_type": "all",
        "per_page": 5,
        "safesearch": "true",
    }
    try:
        resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=15)
        resp = _handle_rate_limit(resp, "Pixabay")
        if resp.status_code == 403:
            print("[stock_video] Pixabay API key invalid (403)")
            pixabay_breaker.record_failure()
            return []
        resp.raise_for_status()
        pixabay_breaker.record_success()
        data = resp.json()
        results = []
        for v in data.get("hits", []):
            videos = v.get("videos", {})
            if not videos:
                continue
            best_key = max(videos.keys(), key=lambda k: videos[k].get("width", 0))
            best = videos[best_key]
            results.append({
                "id": v["id"],
                "url": best.get("url", ""),
                "width": best.get("width", 1920),
                "height": best.get("height", 1080),
                "duration": v.get("duration", 5),
                "fps": best.get("fps", 30),
                "size": best.get("size", 0),
                "source": "pixabay",
                "query": query,
            })
        return results
    except requests.exceptions.HTTPError as e:
        print(f"[stock_video] Pixabay HTTP error: {e}")
        pixabay_breaker.record_failure()
        return []
    except Exception as e:
        print(f"[stock_video] Pixabay search error: {e}")
        pixabay_breaker.record_failure()
        return []


def download_clip(video_url: str, output_path: Path, timeout: int = 30) -> bool:
    if not video_url:
        return False
    try:
        resp = requests.get(video_url, stream=True, timeout=timeout)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        if output_path.stat().st_size < 1000:
            output_path.unlink(missing_ok=True)
            return False
        return True
    except requests.exceptions.Timeout:
        print(f"[stock_video] Download timeout for {video_url[:50]}")
        return False
    except Exception as e:
        print(f"[stock_video] Download error: {e}")
        return False


def _ffprobe_cmd() -> str:
    env_path = os.getenv("FFPROBE_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path
    candidates = [
        "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/usr/bin/ffprobe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "ffprobe"


def get_video_duration(file_path: str) -> float:
    try:
        result = safe_run(
            [_ffprobe_cmd(), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _search_providers(keywords: list[str], orientation: str, per_page: int = 5) -> list[dict]:
    all_results = []
    for kw in keywords:
        results = _search_cached(kw, "pexels", orientation)
        all_results.extend(results)
        if results:
            continue
        results = _search_cached(kw, "pixabay", orientation)
        all_results.extend(results)
    return all_results


def search_and_download(
    scene_keyword: str,
    target_duration: float = 5.0,
    orientation: str = "landscape",
    scene_idx: int = 0,
) -> Optional[dict]:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    expanded = _keyword_expand(scene_keyword)
    all_candidates = _search_providers(expanded, orientation)

    if not all_candidates:
        fallback_kw = [scene_keyword, "nature", "colorful background"]
        all_candidates = _search_providers(fallback_kw, orientation, per_page=3)

    if not all_candidates:
        all_candidates = _search_providers(UNIVERSAL_KEYWORDS, orientation, per_page=3)

    seen_ids = set()
    unique = []
    for c in all_candidates:
        cid = f"{c['source']}_{c['id']}"
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique.append(c)

    for candidate in unique:
        filename = f"clip_{scene_idx:03d}_{candidate['source']}_{candidate['id']}.mp4"
        output_path = CLIPS_DIR / filename
        if output_path.exists():
            duration = get_video_duration(str(output_path))
            if duration > 0:
                return {
                    "path": str(output_path),
                    "duration": duration,
                    "width": candidate["width"],
                    "height": candidate["height"],
                    "source": candidate["source"],
                    "keyword": candidate["query"],
                }

        if download_clip(candidate["url"], output_path):
            duration = get_video_duration(str(output_path))
            if duration > 0:
                return {
                    "path": str(output_path),
                    "duration": duration,
                    "width": candidate["width"],
                    "height": candidate["height"],
                    "source": candidate["source"],
                    "keyword": candidate["query"],
                }

    print(f"[stock_video] No video found for: {scene_keyword}")
    return None


def _search_single_scene(args: tuple) -> dict | None:
    i, scene, orientation, max_retries = args
    keyword = scene.get("keyword", scene.get("description", ""))
    target_dur = scene.get("target_duration", 5.0)
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(2)
        clip = search_and_download(keyword, target_duration=target_dur, orientation=orientation, scene_idx=i)
        if clip:
            print(f"[stock_video] Scene {i+1}: '{keyword}' -> {clip['path']} ({clip['duration']:.1f}s)")
            return clip
    print(f"[stock_video] Scene {i+1}: FAILED for '{keyword}' after {max_retries} attempts")
    return None


def search_videos_for_scenes(scenes: list[dict], orientation: str = "landscape") -> list[dict]:
    max_retries_per_scene = 2
    n = len(scenes)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    args_list = [(i, scene, orientation, max_retries_per_scene) for i, scene in enumerate(scenes)]
    clip_map = {}
    with ThreadPoolExecutor(max_workers=min(n, 8)) as executor:
        futures = {executor.submit(_search_single_scene, args): i for i, args in enumerate(args_list)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                clip = future.result()
                if clip:
                    clip_map[idx] = clip
            except Exception as e:
                print(f"[stock_video] Scene {idx+1} search failed: {e}")

    clips = [clip_map[i] for i in sorted(clip_map) if clip_map[i] is not None]

    if not clips:
        print("[stock_video] CRITICAL: No clips found for any scene. Using universal fallback.")
        for kw in UNIVERSAL_KEYWORDS:
            clip = search_and_download(kw, target_duration=5.0, orientation=orientation, scene_idx=len(clips))
            if clip:
                clips.append(clip)
            if len(clips) >= min(n, 5):
                break

    return clips
