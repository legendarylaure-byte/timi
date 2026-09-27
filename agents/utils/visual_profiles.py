"""Visual Profiles — category-specific visual identity for each content tier.

Each category gets a distinct combination of:
- Color palette (accent, background, text)
- Music mood
- Camera movement style
- Transition preference
- LTX prompt keywords
- Subtitle style

This file was dead: nothing imported it, and it could not even be imported —
`DEFAULT_PROFILE = VISUAL_PROFILES["AI Explained"]` raised KeyError at module
level, because "AI Explained" was never one of the keys. Category->look
therefore never affected a single rendered frame.

That matters more than it sounds. `ltx_keywords` are fed to the video model
that generates the actual pixels, so this is the highest-leverage place to put
the brand. An accent drawn on top of a frame says "overlay"; an accent the
model was asked to light the scene with says "produced by".

Usage:
    from utils.visual_profiles import get_profile, apply_profile_to_prompt
    profile = get_profile("AI News")
    prompt = apply_profile_to_prompt("neural network visualization", "AI News")
"""
import os
from typing import Optional

from utils.brand_palette import (
    LICORICE,
    PURPLE,
    VIOLET,
    PINK,
    ORANGE,
    LIGHT_ORANGE,
    WHITE,
    AMBER,
    ass,
)

# Category → visual profile mapping.
#
# Accents step through the brand ramp so categories stay distinguishable without
# leaving the palette: purple (default) → orange → pink. Backgrounds are all
# Licorice, because a branded channel reads as one channel; the differentiation
# is carried by the accent and the LTX keywords, not by drifting the base.
VISUAL_PROFILES = {
    "AI News": {
        "accent_color": PURPLE,
        "bg_color": LICORICE,
        "text_color": WHITE,
        "music_mood": "energetic",
        "camera_style": "lateral_sweep",
        "transition": "wipeleft",
        "ltx_keywords": [
            "news broadcast style",
            "violet and purple accent lighting",
            "futuristic",
            "clean modern",
            "sharp focus",
        ],
        "brand_lighting": "violet and purple accent lighting",
        "subtitle_accent": ass(AMBER),
        "description": "Energetic, news-like, violet accents, breaking news feel",
    },
    "Science & Technology": {
        "accent_color": ORANGE,
        "bg_color": LICORICE,
        "text_color": WHITE,
        "music_mood": "ambient",
        "camera_style": "slow_zoom",
        "transition": "smoothleft",
        "ltx_keywords": [
            "technical diagram style",
            "warm amber and orange accent highlights",
            "dark background",
            "circuit board aesthetic",
            "sharp focus",
        ],
        "brand_lighting": "warm amber and orange accent lighting",
        "subtitle_accent": ass(LIGHT_ORANGE),
        "description": "Dark, technical, amber highlights, science documentary feel",
    },
    "Programming & Software": {
        "accent_color": PINK,
        "bg_color": LICORICE,
        "text_color": WHITE,
        "music_mood": "playful",
        "camera_style": "handheld_glide",
        "transition": "slideleft",
        "ltx_keywords": [
            "code editor aesthetic",
            "magenta and pink accent syntax highlighting",
            "dark IDE theme",
            "developer workspace",
        ],
        "brand_lighting": "magenta and pink accent lighting",
        "subtitle_accent": ass(PINK),
        "description": "Code-focused, IDE aesthetic, magenta accents, developer feel",
    },
    # Documentary defaults — deliberately desaturated. A documentary that
    # carries brand colour on every frame stops reading as documentary.
    "documentary": {
        "accent_color": LIGHT_ORANGE,
        "bg_color": "#0a0a0a",
        "text_color": WHITE,
        "music_mood": "documentary",
        "camera_style": "slow_pan",
        "transition": "dissolve",
        "ltx_keywords": [
            "documentary style",
            "natural lighting",
            "cinematic",
            "film grain",
            "muted natural colour",
        ],
        "brand_lighting": "muted natural lighting",
        "subtitle_accent": ass("#CCCCCC"),
        "description": "Cinematic documentary, natural lighting, film grain",
    },
}

# Default profile for unknown categories. Resolved by LOOKUP, not by indexing a
# literal key: the original `VISUAL_PROFILES["AI Explained"]` was a KeyError on
# import because no such key exists.
DEFAULT_PROFILE = VISUAL_PROFILES["AI News"]


def get_profile(category: str) -> dict:
    """Get the visual profile for a category, falling back to the default.

    News categories are the most common input and the planner emits a few
    spelling variants, so fall back by intent rather than by exact string.
    """
    if category in VISUAL_PROFILES:
        return VISUAL_PROFILES[category]
    lowered = (category or "").lower()
    if "documentar" in lowered:
        return VISUAL_PROFILES["documentary"]
    if any(k in lowered for k in ("science", "technology", "tech")):
        return VISUAL_PROFILES["Science & Technology"]
    if any(k in lowered for k in ("program", "software", "code", "dev")):
        return VISUAL_PROFILES["Programming & Software"]
    if "news" in lowered:
        return VISUAL_PROFILES["AI News"]
    return DEFAULT_PROFILE


def apply_profile_to_prompt(base_prompt: str, category: str) -> str:
    """Append category-specific visual keywords to an LTX prompt."""
    profile = get_profile(category)
    keywords = profile.get("ltx_keywords", [])
    if keywords:
        return f"{base_prompt}, {', '.join(keywords)}"
    return base_prompt


def get_accent_color(category: str) -> str:
    """Get the hex accent color for a category."""
    return get_profile(category).get("accent_color", PURPLE)


def brand_lighting_phrase(category: str) -> str:
    """The one phrase the video model needs so the brand is in the *pixels*.

    Deliberately not `apply_profile_to_prompt` (the full keyword list): the
    renderer already appends its own quality suffix, so re-adding "sharp focus"
    and friends just burns prompt tokens. The accent colour is the part that
    cannot be added later — an overlay sits on top of footage, but the model has
    to be asked to light the scene with it.
    """
    return get_profile(category).get("brand_lighting", "violet accent lighting")


def get_music_mood(category: str) -> str:
    """Get the music mood for a category."""
    return get_profile(category).get("music_mood", "upbeat")


def get_camera_style(category: str) -> str:
    """Get the camera movement style for a category."""
    return get_profile(category).get("camera_style", "smooth_tracking")


def get_subtitle_color(category: str) -> str:
    """Get the ASS subtitle accent color for a category."""
    return get_profile(category).get("subtitle_accent", ass(AMBER))
