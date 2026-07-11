from .series_builder import (
    load_series, pick_series_for_category, register_video_in_series,
    add_video_to_playlist, create_youtube_playlist, sync_playlist,
    build_continuity_text, generate_part_title, get_series_progress,
)


def inject_intro_outro(scenes: list[dict], category: str, format_type: str = "shorts") -> list[dict]:
    series = pick_series_for_category(category)
    if series:
        part = series.get("current_part", 0) + 1
        series_title = series.get("title", "Series")
        intro_text = f"{series_title} — {generate_part_title(series.get('series_id', ''), part)}"
        outro_text = series.get("outro_text", "Subscribe for the next part!")
        continuity = build_continuity_text(series, part)
        if continuity and format_type == "long":
            intro_text += f" | {continuity[:80]}"
        intro_scene = {
            "background": "stock_footage",
            "duration": 4.0,
            "asset_type": "STATIC_IMAGE",
            "render_type": "manim",
            "asset_keywords": ["intro", series_title],
            "text": [],
            "transition": "fade",
            "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "music_mood": "focused",
            "narration_text": intro_text,
        }
        outro_scene = {
            "background": "stock_footage",
            "duration": 4.0,
            "asset_type": "STATIC_IMAGE",
            "render_type": "manim",
            "asset_keywords": ["subscribe", "outro"],
            "text": [],
            "transition": "fade",
            "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "music_mood": "uplifting",
            "narration_text": "",
        }
        return [intro_scene] + scenes + [outro_scene]

    intro_scene = {
        "background": "solid_black",
        "duration": 4.0,
        "asset_type": "STATIC_IMAGE",
        "render_type": "manim",
        "asset_keywords": ["intro", "channel_brand"],
        "text": [],
        "transition": "fade",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "focused",
        "narration_text": "",
    }
    outro_scene = {
        "background": "solid_black",
        "duration": 5.0,
        "asset_type": "STATIC_IMAGE",
        "render_type": "manim",
        "asset_keywords": ["subscribe", "outro"],
        "text": [],
        "transition": "fade",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "uplifting",
        "narration_text": "",
    }
    return [intro_scene] + scenes + [outro_scene]
