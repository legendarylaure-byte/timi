"""Hook Engine — visual hook templates for first 2 seconds of Shorts.

Designed for 9:16 vertical format. Each template is a dict of ffmpeg drawtext
filters that create a visually striking opening frame. The hook text is drawn
at the top 15% (below phone notch), with a contrasting background bar.

Usage:
    from utils.hook_engine import get_hook_template, render_hook_overlay
    template = get_hook_template("question")
    overlay = render_hook_overlay(template, "What if AI could read your mind?", width=1080, height=1920)
"""
import os
import json
from typing import Optional

# ponytail: 5 hook formulas, each with visual style
HOOK_TEMPLATES = {
    "question": {
        "bg_color": "0x1a1a2e",
        "text_color": "white",
        "accent_color": "0x00CCCC",
        "icon": "?",
        "font_size": 42,
        "animation": "slide_in",
    },
    "bold_claim": {
        "bg_color": "0x2d1b69",
        "text_color": "white",
        "accent_color": "0xFF6B35",
        "icon": "!",
        "font_size": 40,
        "animation": "pop_in",
    },
    "statistic": {
        "bg_color": "0x0d1117",
        "text_color": "white",
        "accent_color": "0x00FF88",
        "icon": "#",
        "font_size": 44,
        "animation": "count_up",
    },
    "curiosity_gap": {
        "bg_color": "0x1a0a2e",
        "text_color": "white",
        "accent_color": "0xBB86FC",
        "icon": "...",
        "font_size": 38,
        "animation": "fade_in",
    },
    "pain_point": {
        "bg_color": "0x2e0a0a",
        "text_color": "white",
        "accent_color": "0xFF4444",
        "icon": "X",
        "font_size": 40,
        "animation": "shake_in",
    },
}


def get_hook_template(formula: str) -> dict:
    """Get visual hook template for a given hook formula type."""
    return HOOK_TEMPLATES.get(formula, HOOK_TEMPLATES["question"])


def render_hook_overlay(
    template: dict,
    hook_text: str,
    width: int = 1080,
    height: int = 1920,
    duration: float = 2.0,
) -> list[str]:
    """Generate ffmpeg drawtext filters for a visual hook overlay.

    Returns list of filter strings to prepend to the vf chain.
    The hook appears in the top 15% of the frame with a semi-transparent
    background bar and accent-colored icon.
    """
    bg = template["bg_color"]
    text_color = template["text_color"]
    accent = template["accent_color"]
    icon = template["icon"]
    font_size = template["font_size"]
    anim = template["animation"]

    # Position: top 15% (below phone notch), centered
    y_pos = int(height * 0.08)
    bar_height = int(height * 0.10)

    # Escape text for ffmpeg
    safe_text = hook_text.replace("'", "'\\''").replace(":", "\\:").replace("%", "%%")

    filters = []

    # Semi-transparent background bar
    filters.append(
        f"drawbox=x=0:y={y_pos}:w={width}:h={bar_height}:"
        f"color={bg}@0.85:t=fill"
    )

    # Accent icon on left
    filters.append(
        f"drawtext=text='{icon}':"
        f"fontsize={font_size + 8}:fontcolor={accent}:"
        f"x=40:y={y_pos + bar_height // 2 - (font_size + 8) // 2}:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )

    # Hook text with animation
    if anim == "slide_in":
        # Slide from left over 0.3s
        x_expr = (
            f"if(lt(t\\,0.3)\\,-text_w+(text_w+40)*(t/0.3)\\,40)"
        )
    elif anim == "pop_in":
        # Pop in at 0.2s
        x_expr = "40"
        filters.append(
            f"drawtext=text='{safe_text}':"
            f"fontsize={font_size}:fontcolor={text_color}@if(lt(t\\,0.2)\\,0\\,1):"
            f"x={x_expr}:y={y_pos + bar_height // 2 - font_size // 2}:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        return filters
    elif anim == "count_up":
        x_expr = "40"
    elif anim == "fade_in":
        x_expr = "40"
        filters.append(
            f"drawtext=text='{safe_text}':"
            f"fontsize={font_size}:fontcolor={text_color}@if(lt(t\\,0.5)\\,t/0.5\\,1):"
            f"x={x_expr}:y={y_pos + bar_height // 2 - font_size // 2}:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        return filters
    else:
        x_expr = "40"

    # Default static text
    filters.append(
        f"drawtext=text='{safe_text}':"
        f"fontsize={font_size}:fontcolor={text_color}:"
        f"x={x_expr}:y={y_pos + bar_height // 2 - font_size // 2}:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )

    return filters


def detect_hook_formula(script_text: str) -> str:
    """Detect which hook formula the script opening uses."""
    opening = (script_text or "")[:200].lower()
    if any(opening.startswith(p) for p in ["imagine", "what if", "did you know"]):
        return "question"
    elif any(w in opening for w in ["secretly", "nobody", "the truth", "why most", "actually"]):
        return "bold_claim"
    elif any(c.isdigit() for c in opening[:100]):
        return "statistic"
    elif any(p in opening for p in ["here's why", "the reason", "but here's", "what happens"]):
        return "curiosity_gap"
    elif any(p in opening for p in ["stop", "frustrated", "annoyed", "tired of", "hate"]):
        return "pain_point"
    return "question"
