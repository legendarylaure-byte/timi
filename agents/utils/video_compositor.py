import os
import re
import json
import subprocess
from pathlib import Path
from typing import Optional
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = Path(__file__).parent.parent / "tmp" / "compositor"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

ASPECT_RATIOS = {
    "shorts": {"w": 1080, "h": 1920, "ar": "9:16"},
    "long": {"w": 1920, "h": 1080, "ar": "16:9"},
}

KEN_BURNS_PRESETS = [
    "z=1.0+0.3*t:x=0:y=0",
    "z=1.0+0.3*t:x=(iw-iw/zoom)/2:y=0",
    "z=1.3-0.3*t:x=0:y=0",
    "z=1.0+0.2*t:x=0:y=(ih-ih/zoom)/2",
    "z=1.2-0.2*t:x=(iw-iw/zoom)/2:y=(ih-ih/zoom)/2",
    "z=1.0+0.25*t:x=(iw-iw/zoom)/4:y=0",
    "z=1.0+0.2*t:x=0:y=(ih-ih/zoom)/4",
    "z=1.25-0.25*t:x=(iw-iw/zoom)/3:y=(ih-ih/zoom)/3",
]

def apply_ken_burns(input_path: str, output_path: str, target_w: int, target_h: int, duration: float, preset_idx: int = 0) -> bool:
    kb = KEN_BURNS_PRESETS[preset_idx % len(KEN_BURNS_PRESETS)]
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={target_w}*2:{target_h}*2,zoompan='{kb}':d={int(duration*30)}:s={target_w}x{target_h}:fps=30",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except Exception as e:
        print(f"[compositor] Ken Burns error: {e}")
        return False

def trim_clip(input_path: str, output_path: str, start: float = 0, duration: float = 5) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", input_path, "-ss", str(start), "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).returncode == 0
    except Exception as e:
        print(f"[compositor] Trim error: {e}")
        return False

def resize_to_target(input_path: str, output_path: str, target_w: int, target_h: int) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).returncode == 0
    except Exception as e:
        print(f"[compositor] Resize error: {e}")
        return False

def mix_audio(voice_path: str, music_path: Optional[str], output_path: str, voice_volume_db: float = 0, music_volume_db: float = -18) -> bool:
    try:
        voice = AudioSegment.from_file(voice_path) + voice_volume_db
        if music_path and os.path.exists(music_path):
            music = (AudioSegment.from_file(music_path) + music_volume_db)
            music = (music * (len(voice) // len(music) + 1))[:len(voice)]
            mixed = voice.overlay(music)
        else:
            mixed = voice
        mixed.export(output_path, format="wav")
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"[compositor] Audio mix error: {e}")
        return False

def add_text_overlay(video_path: str, text: str, output_path: str, fontsize: int = 48, color: str = "white", position: str = "center", start_time: float = 0, duration: float = 3) -> bool:
    positions = {"center": "(w-text_w)/2:(h-text_h)/2", "bottom": "(w-text_w)/2:(h-text_h)-50", "top": "(w-text_w)/2:50"}
    pos = positions.get(position, positions["center"])
    escaped_text = text.replace("'", "\\'").replace(":", "\\:").replace("-", "\\-")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"drawtext=text='{escaped_text}':fontsize={fontsize}:fontcolor={color}:x={pos}:enable='between(t,{start_time},{start_time+duration})'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).returncode == 0
    except Exception as e:
        print(f"[compositor] Text overlay error: {e}")
        return False

def burn_subtitles(video_path: str, subtitle_path: str, output_path: str, fontsize: int = 24) -> bool:
    escaped_subtitle = subtitle_path.replace(":", "\\:").replace("'", "\\'")
    vf = f"subtitles='{escaped_subtitle}':force_style='FontSize={fontsize},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Shadow=1'"
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"[compositor] Subtitles burned successfully")
            return True
        else:
            print(f"[compositor] Subtitle burn error: {result.stderr[-300:]}")
            return False
    except Exception as e:
        print(f"[compositor] Subtitle burn error: {e}")
        return False

def add_chapter_markers(video_path: str, chapters: list[dict], output_path: str) -> bool:
    metadata_path = str(TEMP_DIR / "chapters_metadata.txt")
    with open(metadata_path, "w") as f:
        f.write(";FFMETADATA1\n")
        for chapter in chapters:
            start_ms = int(chapter.get("start_time", 0) * 1000)
            end_ms = int(chapter.get("end_time", 0) * 1000)
            title = chapter.get("title", "Chapter")
            f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={start_ms}\nEND={end_ms}\ntitle={title}\n")

    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", metadata_path,
        "-map_metadata", "1",
        "-c:v", "copy", "-c:a", "copy", output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"[compositor] Chapter markers added: {len(chapters)} chapters")
            return True
        return False
    except Exception as e:
        print(f"[compositor] Chapter markers error: {e}")
        return False

def composite_video(clips: list[dict], voice_path: str, music_path: Optional[str] = None, format_type: str = "shorts", video_id: str = "output", subtitle_path: Optional[str] = None, chapters: Optional[list] = None) -> Optional[str]:
    target = ASPECT_RATIOS.get(format_type, ASPECT_RATIOS["long"])
    tw, th = target["w"], target["h"]

    processed_clips = []
    for i, clip in enumerate(clips):
        clip_path = clip["path"]
        clip_duration = clip.get("duration", 5.0)
        processed_path = str(TEMP_DIR / f"kb_{i:03d}.mp4")
        print(f"[compositor] Ken Burns on clip {i+1}/{len(clips)}")
        success = apply_ken_burns(clip_path, processed_path, tw, th, clip_duration, i)
        if not success:
            fallback_path = str(TEMP_DIR / f"resize_{i:03d}.mp4")
            success = resize_to_target(clip_path, fallback_path, tw, th)
            if success:
                processed_clips.append(fallback_path)
        else:
            processed_clips.append(processed_path)

    if not processed_clips:
        print("[compositor] No clips to composite")
        return None

    concat_list_path = str(TEMP_DIR / "concat_list.txt")
    with open(concat_list_path, "w") as f:
        for p in processed_clips:
            f.write(f"file '{p}'\n")

    combined_video = str(TEMP_DIR / "combined_video.mp4")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
           "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", combined_video]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"[compositor] Concat error: {result.stderr[-300:]}")
    except Exception as e:
        print(f"[compositor] Concat error: {e}")
        return None

    if not os.path.exists(combined_video):
        return None

    if subtitle_path and os.path.exists(subtitle_path):
        print(f"[compositor] Burning subtitles into video")
        with_subs_path = str(TEMP_DIR / "video_with_subs.mp4")
        if burn_subtitles(combined_video, subtitle_path, with_subs_path):
            combined_video = with_subs_path

    if chapters and format_type == "long":
        print(f"[compositor] Adding chapter markers")
        with_chapters_path = str(TEMP_DIR / "video_with_chapters.mp4")
        if add_chapter_markers(combined_video, chapters, with_chapters_path):
            combined_video = with_chapters_path

    mixed_audio_path = str(TEMP_DIR / "mixed_audio.wav")
    mix_audio(voice_path, music_path, mixed_audio_path)

    final_path = str(OUTPUT_DIR / f"{video_id}_{format_type}.mp4")
    cmd = ["ffmpeg", "-y", "-i", combined_video, "-i", mixed_audio_path,
           "-c:v", "libx264", "-preset", "fast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-pix_fmt", "yuv420p", final_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and os.path.exists(final_path):
            print(f"[compositor] Final video: {final_path}")
            return final_path
    except Exception as e:
        print(f"[compositor] Final mux error: {e}")
    return None
