from .series_builder import (
    load_series, pick_series_for_category, register_video_in_series,
    add_video_to_playlist, create_youtube_playlist, sync_playlist,
    get_series_progress,
)


def inject_intro_outro(scenes: list[dict], category: str, format_type: str = "shorts") -> list[dict]:
    series = pick_series_for_category(category)
    if series:
        outro_text = series.get("outro_text", "Subscribe for the next part!")
        outro_scene = {
            "background": "stock_footage",
            "duration": 4.0,
            "asset_type": "STATIC_IMAGE",
            "render_type": "branded_card",
            "description": outro_text,
            "text": [],
            "transition": "fade",
            "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "music_mood": "uplifting",
            "narration_text": "",
        }
        return scenes + [outro_scene]

    # D39: the branded intro card is gone. The hook now speaks over real footage
    # (the deep-lesson manim hook-scene guarantee was removed with the renderers),
    # and a title card in front of it cost the first seconds of every video.
    # The outro stays -- a subscribe card at the end is the useful half.
    outro_scene = {
        "background": "solid_black",
        "duration": 5.0,
        "asset_type": "STATIC_IMAGE",
        "render_type": "branded_card",
        "description": "Subscribe to Vyom Ai Cloud",
        "text": [],
        "transition": "fade",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "uplifting",
        "narration_text": "",
    }
    return scenes + [outro_scene]
