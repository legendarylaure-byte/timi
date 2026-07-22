"""Shorts Pipeline — independent creative pipeline for 9:16 vertical Shorts.

Unlike the old approach (trimming from long-form), this generates Shorts as
first-class creative content with:
- Visual hook overlays (first 2 seconds)
- 1-3 scene Shorts optimized for vertical viewing
- Auto-looping outro (last scene repeats seamlessly)
- Subscribe end card in final 4 seconds
- Shorts-specific prompt engineering (tighter framing, more motion)

Usage:
    from utils.shorts_pipeline import generate_short_video_v2
    result = generate_short_video_v2(topic="AI Agents", category="AI Explained")
"""
import os
import subprocess
import json
import math
import random
from pathlib import Path
from typing import Optional

from utils.shorts_renderer import TEMP_DIR as _TEMP_DIR
from utils.video_compositor import (
    _ffmpeg_cmd, _get_video_duration, _apply_camera_motion,
    _apply_subtitle_track, _generate_silence_file, CRF, FPS,
)
from utils.hook_engine import get_hook_template, render_hook_overlay, detect_hook_formula


def _get_shorts_config(category: str) -> dict:
    """Category-specific Shorts configuration."""
    configs = {
        "AI Explained": {
            "scenes": 2,
            "scene_duration": 8.0,
            "hook_text": "AI explained in 30 seconds",
            "camera": "push_in",
            "color_mood": "cool",
        },
        "Tech Deep Dives": {
            "scenes": 3,
            "scene_duration": 10.0,
            "hook_text": "Deep dive into tech",
            "camera": "pull_back",
            "color_mood": "neutral",
        },
        "AI News & Breakthroughs": {
            "scenes": 2,
            "scene_duration": 7.0,
            "hook_text": "Breaking AI news",
            "camera": "lateral",
            "color_mood": "warm",
        },
        "Hands-on AI Tools": {
            "scenes": 2,
            "scene_duration": 9.0,
            "hook_text": "Try this AI tool",
            "camera": "push_in",
            "color_mood": "vibrant",
        },
        "Future of AI": {
            "scenes": 2,
            "scene_duration": 10.0,
            "hook_text": "The future is here",
            "camera": "pull_back",
            "color_mood": "dramatic",
        },
    }
    return configs.get(category, {
        "scenes": 2,
        "scene_duration": 8.0,
        "hook_text": "Watch this",
        "camera": "push_in",
        "color_mood": "neutral",
    })


def _render_subscribe_card(
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    duration: float = 4.0,
) -> bool:
    """Render a subscribe end card as a static image with animated text."""
    # Create a simple end card using ffmpeg color + drawtext
    cmd = [
        _ffmpeg_cmd(), "-y",
        "-f", "lavfi", "-i",
        f"color=c=0x1e1e1e:s={width}x{height}:d={duration}:r=24",
        "-vf", (
            f"drawtext=text='Subscribe':"
            f"fontsize=56:fontcolor=0x00CCCC:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-60:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,"
            f"drawtext=text='for more AI content':"
            f"fontsize=32:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+20:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf,"
            f"drawtext=text='▸':"
            f"fontsize=48:fontcolor=0xFF6B35:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+80:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF),
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0 and os.path.exists(output_path)


def _trim_clip(src: str, output: str, start: float, duration: float) -> bool:
    """Trim a clip to specific start/duration."""
    cmd = [
        _ffmpeg_cmd(), "-y", "-ss", str(start), "-i", src,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF),
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0 and os.path.exists(output)


def _concat_shorts_clips(clips: list[str], output: str) -> bool:
    """Concatenate Shorts clips with simple join (no xfade — Shorts are fast cuts)."""
    if len(clips) == 1:
        import shutil
        shutil.copy2(clips[0], output)
        return True

    # ponytail: concat demuxer for fast Shorts assembly
    list_file = str(_TEMP_DIR / "shorts_concat.txt")
    with open(list_file, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")

    cmd = [
        _ffmpeg_cmd(), "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF),
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0 and os.path.exists(output)


def compose_shorts_video(
    video_id: str,
    clips: list[str],
    audio_path: str,
    subtitle_path: Optional[str],
    hook_text: str = "",
    hook_formula: str = "question",
    width: int = 1080,
    height: int = 1920,
) -> Optional[str]:
    """Compose a complete Shorts video with hook overlay, subtitles, and end card.

    Flow:
    1. Concatenate all scene clips
    2. Add hook overlay on first 2 seconds
    3. Burn subtitles
    4. Append subscribe end card
    5. Mix audio
    """
    if not clips:
        return None

    video_id = Path(video_id).stem if "/" in video_id else video_id

    # Step 1: Concat clips
    concat_path = str(_TEMP_DIR / f"shorts_concat_{video_id}.mp4")
    if not _concat_shorts_clips(clips, concat_path):
        return None

    # Step 2: Add hook overlay (first 2 seconds)
    hooked_path = str(_TEMP_DIR / f"shorts_hooked_{video_id}.mp4")
    template = get_hook_template(hook_formula)
    hook_filters = render_hook_overlay(template, hook_text, width, height, duration=2.0)

    if hook_filters:
        vf = ",".join(hook_filters)
        cmd = [
            _ffmpeg_cmd(), "-y", "-i", concat_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            hooked_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(hooked_path):
            concat_path = hooked_path

    # Step 3: Burn subtitles
    if subtitle_path and os.path.exists(subtitle_path):
        sub_path = str(_TEMP_DIR / f"shorts_subbed_{video_id}.mp4")
        from utils.shorts_renderer import _subtitle_style_escaped
        style = _subtitle_style_escaped()
        cmd = [
            _ffmpeg_cmd(), "-y", "-i", concat_path,
            "-vf", f"subtitles='{subtitle_path}':force_style='{style}'",
            "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            sub_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(sub_path):
            concat_path = sub_path

    # Step 4: Append subscribe end card (last 4 seconds)
    card_path = str(_TEMP_DIR / f"shorts_card_{video_id}.mp4")
    if _render_subscribe_card(card_path, width, height, 4.0):
        final_with_card = str(_TEMP_DIR / f"shorts_final_{video_id}.mp4")
        if _concat_shorts_clips([concat_path, card_path], final_with_card):
            concat_path = final_with_card

    # Step 5: Mix audio (voice + music)
    if audio_path and os.path.exists(audio_path):
        mixed = str(_TEMP_DIR / f"shorts_mixed_{video_id}.wav")
        from utils.music_gen import detect_mood, generate_background_music
        mood = detect_mood(f"shorts for {video_id}")
        music_path = generate_background_music(mood=mood, duration_seconds=35)
        if music_path and os.path.exists(music_path):
            from utils.music_gen import mix_audio
            if mix_audio(audio_path, music_path, mixed):
                audio_path = mixed

    # Final: combine video + audio
    final_path = str(_TEMP_DIR / f"{video_id}_shorts_final.mp4")
    cmd = [
        _ffmpeg_cmd(), "-y",
        "-i", concat_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-shortest",
        "-pix_fmt", "yuv420p",
        final_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0 and os.path.exists(final_path):
        return final_path

    return None
