import json
import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SERIES_PATH = os.path.join(ASSETS_DIR, "series.json")


def load_series() -> dict:
    if os.path.exists(SERIES_PATH):
        with open(SERIES_PATH) as f:
            return json.load(f)
    return {}


def pick_series_for_category(category: str) -> dict | None:
    series_map = load_series()
    for s in series_map.values():
        if category in s.get("categories", []):
            return s
    return None


def build_intro_scene(series: dict, format_type: str) -> dict:
    placement = series.get("character_placement", {})
    return {
        "background": series.get("background", "gradient_sky"),
        "duration": series.get("intro_duration", 3.0),
        "characters": [{
            "name": series["host"],
            "pose": series.get("host_pose", "wave"),
            "expression": series.get("host_expression", "happy"),
            "animation": "bounce" if series.get("music_mood") == "playful" else "float",
            "x": placement.get("x", 0.5),
            "y": placement.get("y", 0.55),
        }],
        "text": [{
            "text": series.get("intro_text", "Welcome!"),
            "style": "title",
            "position": "top",
        }],
        "effects": ["sparkle"],
        "transition": "cut",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": series.get("music_mood", "happy"),
    }


def build_outro_scene(series: dict, format_type: str) -> dict:
    placement = series.get("character_placement", {})
    return {
        "background": series.get("background", "gradient_sky"),
        "duration": series.get("outro_duration", 3.0),
        "characters": [{
            "name": series["host"],
            "pose": "idle",
            "expression": series.get("host_expression", "happy"),
            "animation": "float",
            "x": placement.get("x", 0.5),
            "y": placement.get("y", 0.55),
        }],
        "text": [{
            "text": series.get("outro_text", "Goodbye!"),
            "style": "title",
            "position": "center",
        }],
        "effects": ["fade_out"],
        "transition": "fade",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": series.get("music_mood", "happy"),
    }


def inject_intro_outro(scenes: list[dict], category: str, format_type: str = "shorts") -> list[dict]:
    series = pick_series_for_category(category)
    if not series:
        return scenes

    intro = build_intro_scene(series, format_type)
    outro = build_outro_scene(series, format_type)
    return [intro] + scenes + [outro]
