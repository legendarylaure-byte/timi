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
    "AI Explained": {
        "accent_color": "#00CCCC",
        "bg_color": "#1e1e1e",
        "text_color": "#FFFFFF",
        "music_mood": "upbeat",
        "camera_style": "smooth_tracking",
        "transition": "dissolve",
        "ltx_keywords": ["clean infographic style", "teal accent lighting", "modern tech aesthetic", "sharp lines"],
        "subtitle_accent": "&H00CCCC00&",  # ASS teal
        "description": "Clean, educational, modern tech feel with teal accents",
    },
    "Tech Deep Dives": {
        "accent_color": "#FF6B35",
        "bg_color": "#0d1117",
        "text_color": "#FFFFFF",
        "music_mood": "ambient",
        "camera_style": "slow_zoom",
        "transition": "smoothleft",
        "ltx_keywords": ["technical diagram style", "orange accent highlights", "dark background", "circuit board aesthetic"],
        "subtitle_accent": "&H00356BFF&",  # ASS orange
        "description": "Dark, technical, orange highlights, circuit-board feel",
    },
    "AI News & Breakthroughs": {
        "accent_color": "#00FF88",
        "bg_color": "#1a1a2e",
        "text_color": "#FFFFFF",
        "music_mood": "energetic",
        "camera_style": "lateral_sweep",
        "transition": "wipeleft",
        "ltx_keywords": ["news broadcast style", "green accent lighting", "futuristic", "clean modern"],
        "subtitle_accent": "&H0088FF00&",  # ASS green
        "description": "Energetic, news-like, green accents, futuristic",
    },
    "Hands-on AI Tools": {
        "accent_color": "#BB86FC",
        "bg_color": "#1e1e1e",
        "text_color": "#FFFFFF",
        "music_mood": "playful",
        "camera_style": "handheld_glide",
        "transition": "slideleft",
        "ltx_keywords": ["hands-on tutorial style", "purple accent lighting", "workspace aesthetic", "tool interface"],
        "subtitle_accent": "&H0086BBFF&",  # ASS purple
        "description": "Playful, hands-on, purple accents, workspace feel",
    },
    "Future of AI": {
        "accent_color": "#FF4444",
        "bg_color": "#2d1b69",
        "text_color": "#FFFFFF",
        "music_mood": "dramatic",
        "camera_style": "epic_pullback",
        "transition": "radial",
        "ltx_keywords": ["cinematic futuristic", "red accent dramatic lighting", "sci-fi aesthetic", "epic scale"],
        "subtitle_accent": "&H004444FF&",  # ASS red
        "description": "Dramatic, cinematic, red accents, sci-fi feel",
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
        "subtitle_accent": "&H00CCCCCC&",  # ASS silver
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
