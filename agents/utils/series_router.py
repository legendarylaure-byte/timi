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
            "render_type": "branded_card",
            # Keep the real subject, drop the routing label. Was ["intro", series_title].
            "asset_keywords": [series_title],
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
            "render_type": "branded_card",
            # Same reasoning as the intro card: if this card render fails, a
            # stock search for "subscribe"/"outro" returns a clip of the word.
            # The visible text comes from `description` below.
            "description": "Subscribe to Vyom Ai Cloud",
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
        "render_type": "branded_card",
        # Was ["intro", "channel_brand"] -- pipeline routing labels, not
        # content. The branded card never rendered them, but if the card render
        # failed this fell through to a stock search for "intro" and produced a
        # clip of the word. The card's own text comes from `description`; the
        # keyword list is now left to asset_router's honest default.
        "description": "Vyom Ai Cloud",
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
        "render_type": "branded_card",
        # Same reasoning as the intro card: if this card render fails, a stock
        # search for "subscribe"/"outro" returns a clip of the word. The visible
        # text comes from `description` below.
        "description": "Subscribe to Vyom Ai Cloud",
        "text": [],
        "transition": "fade",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "uplifting",
        "narration_text": "",
    }
    return [intro_scene] + scenes + [outro_scene]
