from .series_builder import load_series, pick_series_for_category, register_video_in_series, add_video_to_playlist, create_youtube_playlist


def inject_intro_outro(scenes: list[dict], category: str, format_type: str = "shorts") -> list[dict]:
    series = pick_series_for_category(category)
    if not series:
        return scenes
    intro_text = f"📚 {series.get('title', 'Series')} — Part {series.get('current_part', 0) + 1}"
    outro_text = series.get("outro_text", "Subscribe for the next part!")
    intro_scene = {
        "background": "stock_footage",
        "duration": 3.0,
        "asset_type": "STOCK_FOOTAGE",
        "asset_keywords": ["technology", series.get("title", "series")],
        "text": [{"text": intro_text, "style": "title", "position": "center"}],
        "transition": "cut",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "focused",
    }
    outro_scene = {
        "background": "stock_footage",
        "duration": 4.0,
        "asset_type": "STOCK_FOOTAGE",
        "asset_keywords": ["subscribe", "next video"],
        "text": [{"text": outro_text, "style": "title", "position": "center"}],
        "transition": "fade",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "focused",
    }
    return [intro_scene] + scenes + [outro_scene]
