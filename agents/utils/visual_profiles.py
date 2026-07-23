"""Visual Profiles — category-specific visual identity for each content tier.

Each category gets a distinct combination of:
- Color palette (accent, background, text)
- Music mood
- Camera movement style
- Transition preference
- LTX prompt keywords
- Subtitle style

Usage:
    from utils.visual_profiles import get_profile, apply_profile_to_prompt
    profile = get_profile("AI Explained")
    prompt = apply_profile_to_prompt("neural network visualization", "AI Explained")
"""
import os
from typing import Optional

# Category → visual profile mapping
VISUAL_PROFILES = {
    "AI News": {
        "accent_color": "#00CCCC",
        "bg_color": "#1e1e1e",
        "text_color": "#FFFFFF",
        "music_mood": "energetic",
        "camera_style": "lateral_sweep",
        "transition": "wipeleft",
        "ltx_keywords": ["news broadcast style", "teal accent lighting", "futuristic", "clean modern", "sharp focus"],
        "subtitle_accent": "&H00CCCC00&",
        "description": "Energetic, news-like, teal accents, breaking news feel",
    },
    "Science & Technology": {
        "accent_color": "#FF6B35",
        "bg_color": "#0d1117",
        "text_color": "#FFFFFF",
        "music_mood": "ambient",
        "camera_style": "slow_zoom",
        "transition": "smoothleft",
        "ltx_keywords": ["technical diagram style", "orange accent highlights", "dark background", "circuit board aesthetic", "sharp focus"],
        "subtitle_accent": "&H00356BFF&",
        "description": "Dark, technical, orange highlights, science documentary feel",
    },
    "Business & Finance": {
        "accent_color": "#00FF88",
        "bg_color": "#1a1a2e",
        "text_color": "#FFFFFF",
        "music_mood": "upbeat",
        "camera_style": "smooth_tracking",
        "transition": "dissolve",
        "ltx_keywords": ["corporate professional style", "green accent data visualization", "clean modern", "financial dashboard aesthetic"],
        "subtitle_accent": "&H0088FF00&",
        "description": "Professional, data-driven, green accents, corporate feel",
    },
    "Health & Medicine": {
        "accent_color": "#BB86FC",
        "bg_color": "#1e1e1e",
        "text_color": "#FFFFFF",
        "music_mood": "focused",
        "camera_style": "smooth_tracking",
        "transition": "dissolve",
        "ltx_keywords": ["medical visualization style", "purple accent lighting", "clean sterile aesthetic", "anatomical precision"],
        "subtitle_accent": "&H0086BBFF&",
        "description": "Clean, medical, purple accents, scientific precision",
    },
    "Programming & Software": {
        "accent_color": "#FF4444",
        "bg_color": "#0d1117",
        "text_color": "#FFFFFF",
        "music_mood": "playful",
        "camera_style": "handheld_glide",
        "transition": "slideleft",
        "ltx_keywords": ["code editor aesthetic", "red accent syntax highlighting", "dark IDE theme", "developer workspace"],
        "subtitle_accent": "&H004444FF&",
        "description": "Code-focused, IDE aesthetic, red accents, developer feel",
    },
    # Documentary defaults
    "documentary": {
        "accent_color": "#CCCCCC",
        "bg_color": "#0a0a0a",
        "text_color": "#FFFFFF",
        "music_mood": "documentary",
        "camera_style": "slow_pan",
        "transition": "dissolve",
        "ltx_keywords": ["documentary style", "natural lighting", "cinematic", "film grain"],
        "subtitle_accent": "&H00CCCCCC&",
        "description": "Cinematic documentary, natural lighting, film grain",
    },
}

# Default profile for unknown categories
DEFAULT_PROFILE = VISUAL_PROFILES["AI Explained"]


def get_profile(category: str) -> dict:
    """Get the visual profile for a category."""
    return VISUAL_PROFILES.get(category, DEFAULT_PROFILE)


def apply_profile_to_prompt(base_prompt: str, category: str) -> str:
    """Append category-specific visual keywords to an LTX prompt."""
    profile = get_profile(category)
    keywords = profile.get("ltx_keywords", [])
    if keywords:
        return f"{base_prompt}, {', '.join(keywords)}"
    return base_prompt


def get_accent_color(category: str) -> str:
    """Get the hex accent color for a category."""
    return get_profile(category).get("accent_color", "#00CCCC")


def get_music_mood(category: str) -> str:
    """Get the music mood for a category."""
    return get_profile(category).get("music_mood", "upbeat")


def get_camera_style(category: str) -> str:
    """Get the camera movement style for a category."""
    return get_profile(category).get("camera_style", "smooth_tracking")


def get_subtitle_color(category: str) -> str:
    """Get the ASS subtitle accent color for a category."""
    return get_profile(category).get("subtitle_accent", "&H00CCCC00&")
