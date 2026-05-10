import os
import time
import requests
import subprocess
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

CLIPS_DIR = Path(__file__).parent.parent / "tmp" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

_API_CACHE = {}
_PIXABAY_BLOCKED = False
_API_LAST_CALL = 0.0


def _rate_limit_delay():
    global _API_LAST_CALL
    now = time.time()
    elapsed = now - _API_LAST_CALL
    if elapsed < 0.35:
        time.sleep(0.35 - elapsed)
    _API_LAST_CALL = time.time()


PEXELS_KEYWORD_MAP = {
    "bunny": ["rabbit", "bunny", "cute animal"],
    "bear": ["teddy bear", "bear cub", "cartoon bear"],
    "forest": ["forest", "woodland", "trees nature"],
    "ocean": ["ocean", "sea waves", "underwater"],
    "space": ["stars", "galaxy", "space", "planet"],
    "play": ["kids playing", "children playground", "happy kids"],
    "sleep": ["sleeping child", "night sky stars", "moon"],
    "friend": ["friends playing", "kids together", "hugging"],
    "magic": ["sparkles", "fairy dust", "glowing particles"],
    "garden": ["garden flowers", "butterfly", "nature spring"],
    "adventure": ["exploring", "hiking nature", "mountain view"],
    "animal": ["cute animals", "wildlife", "farm animals"],
    "rainbow": ["rainbow", "colorful sky"],
    "snow": ["snowfall", "winter wonderland", "snowy"],
    "sunset": ["sunset", "golden hour", "dawn sky"],
    "birthday": ["birthday cake", "party balloons"],
    "school": ["classroom kids", "learning", "reading book"],
    "food": ["kids eating", "fruit vegetables", "cooking food"],
    "car": ["toy car", "cars driving"],
    "dog": ["dog playing", "cute puppy", "dog running"],
    "cat": ["cat playing", "cute kitten"],
    "bird": ["bird flying", "colorful bird"],
    "fish": ["fish swimming", "aquarium", "tropical fish"],
    "dragon": ["dragon", "fantasy creature"],
    "princess": ["princess", "castle", "fairy tale"],
    "superhero": ["superhero", "flying", "action hero"],
    "music": ["music instruments", "dancing"],
    "dance": ["kids dancing", "ballet"],
    "cloud": ["clouds sky", "fluffy clouds"],
    "flower": ["flower blooming", "flower garden"],
}

UNIVERSAL_KEYWORDS = [
    "colorful background", "nature scenery", "kids learning",
    "happy children", "animated shapes", "bright colors",
    "cute animals playing", "nature landscape", "abstract animation",
    "sunny day outdoor", "waterfall nature", "rainbow sky",
]


def _keyword_expand(base_keyword: str) -> list[str]:
    base = base_keyword.lower().strip()
    for key, aliases in PEXELS_KEYWORD_MAP.items():
        if key in base or base in key:
            return aliases
    return [base, base + " cartoon", base + " animation", base + " kids"]


def _handle_rate_limit(resp: requests.Response, source: str, max_retries: int = 1) -> requests.Response:
    """Handle 429 rate limit. Sets circuit breaker for Pixabay, logs for Pexels."""
    global _PIXABAY_BLOCKED
    if resp.status_code != 429:
        return resp
    if source == "Pixabay":
        print("[stock_video] Pixabay rate limited (429) — disabling Pixabay for this run")
        _PIXABAY_BLOCKED = True
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
    _rate_limit_delay()
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": orientation}
    try:
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=15)
        resp = _handle_rate_limit(resp, "Pexels")
        if resp.status_code == 403:
            print("[stock_video] Pexels API key invalid (403)")
            return []
        resp.raise_for_status()
        data = resp.json()
        results = []
        for v in data.get("videos", []):
            vf = v.get("video_files", [])
            if not vf:
                continue
            best = max(vf, key=lambda f: f.get("width", 0) * f.get("height", 0))
            results.append({
                "id": v["id"],
                "url": best.get("link", ""),
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
        return []
    except Exception as e:
        print(f"[stock_video] Pexels search error: {e}")
        return []


def _search_pixabay_uncached(query: str) -> list[dict]:
    if not PIXABAY_API_KEY:
        print("[stock_video] PIXABAY_API_KEY is empty — set it in GitHub secrets")
        return []
    if _PIXABAY_BLOCKED:
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
            return []
        resp.raise_for_status()
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
        return []
    except Exception as e:
        print(f"[stock_video] Pixabay search error: {e}")
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
        result = subprocess.run(
            [_ffprobe_cmd(), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10
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


def search_videos_for_scenes(scenes: list[dict], orientation: str = "landscape") -> list[dict]:
    clips = []
    max_retries_per_scene = 2

    for i, scene in enumerate(scenes):
        keyword = scene.get("keyword", scene.get("description", ""))
        target_dur = scene.get("target_duration", 5.0)
        print(f"[stock_video] Scene {i+1}/{len(scenes)}: '{keyword}'")

        for attempt in range(max_retries_per_scene):
            if attempt > 0:
                print(f"[stock_video] Retrying scene {i+1} (attempt {attempt+1})")
                time.sleep(2)

            clip = search_and_download(keyword, target_duration=target_dur, orientation=orientation, scene_idx=i)
            if clip:
                clips.append(clip)
                print(f"[stock_video] -> Found: {clip['path']} ({clip['duration']:.1f}s)")
                break

        if not clip and attempt == max_retries_per_scene - 1:
            print(f"[stock_video] -> FAILED for '{keyword}' after {max_retries_per_scene} attempts")
            if clips:
                prev_clip = clips[-1]
                clips.append({
                    "path": prev_clip["path"],
                    "duration": prev_clip["duration"] * 0.5,
                    "width": prev_clip["width"],
                    "height": prev_clip["height"],
                    "source": "fallback",
                    "keyword": keyword,
                })
                print("[stock_video] -> Using fallback clip from previous scene")

        time.sleep(0.5)

    if not clips:
        print("[stock_video] CRITICAL: No clips found for any scene. Using universal fallback.")
        for kw in UNIVERSAL_KEYWORDS:
            clip = search_and_download(kw, target_duration=5.0, orientation=orientation, scene_idx=len(clips))
            if clip:
                clips.append(clip)
                print(f"[stock_video] -> Universal fallback: {clip['path']} ({clip['duration']:.1f}s)")
            if len(clips) >= min(len(scenes), 5):
                break
            time.sleep(0.5)

    return clips
