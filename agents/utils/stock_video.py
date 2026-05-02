import os
import re
import json
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

def _keyword_expand(base_keyword: str) -> list[str]:
    base = base_keyword.lower().strip()
    for key, aliases in PEXELS_KEYWORD_MAP.items():
        if key in base or base in key:
            return aliases
    return [base, base + " cartoon", base + " animation", base + " kids"]

def search_pexels(query: str, orientation: str = "landscape", per_page: int = 10) -> list[dict]:
    if not PEXELS_API_KEY:
        return []
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    try:
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=15)
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
    except Exception as e:
        print(f"[stock_video] Pexels search error: {e}")
        return []

def search_pixabay(query: str, per_page: int = 10) -> list[dict]:
    if not PIXABAY_API_KEY:
        return []
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "video_type": "all",
        "per_page": per_page,
        "safesearch": "true",
    }
    try:
        resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=15)
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
    except Exception as e:
        print(f"[stock_video] Pixabay search error: {e}")
        return []

def download_clip(video_url: str, output_path: Path, timeout: int = 60) -> bool:
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
    except Exception as e:
        print(f"[stock_video] Download error: {e}")
        return False

def get_video_duration(file_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def search_and_download(
    scene_keyword: str,
    target_duration: float = 5.0,
    orientation: str = "landscape",
    scene_idx: int = 0,
) -> Optional[dict]:
    expanded = _keyword_expand(scene_keyword)
    all_candidates = []
    for kw in expanded:
        pexels_results = search_pexels(kw, orientation=orientation, per_page=8)
        all_candidates.extend(pexels_results)
        pixabay_results = search_pixabay(kw, per_page=8)
        all_candidates.extend(pixabay_results)
        if all_candidates:
            break

    if not all_candidates:
        fallback_kw = [scene_keyword, "nature", "colorful background"]
        for kw in fallback_kw:
            all_candidates.extend(search_pexels(kw, orientation=orientation, per_page=5))
            all_candidates.extend(search_pixabay(kw, per_page=5))
            if all_candidates:
                break

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
    for i, scene in enumerate(scenes):
        keyword = scene.get("keyword", scene.get("description", ""))
        target_dur = scene.get("target_duration", 5.0)
        print(f"[stock_video] Scene {i+1}/{len(scenes)}: '{keyword}'")
        clip = search_and_download(keyword, target_duration=target_dur, orientation=orientation, scene_idx=i)
        if clip:
            clips.append(clip)
            print(f"[stock_video] -> Found: {clip['path']} ({clip['duration']:.1f}s)")
        else:
            print(f"[stock_video] -> FAILED for '{keyword}'")
        time.sleep(0.5)
    return clips
