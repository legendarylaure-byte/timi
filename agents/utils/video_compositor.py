from dotenv import load_dotenv
from pydub import AudioSegment
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

_FFMPEG_BIN = "/opt/homebrew/opt/ffmpeg-full/bin"
if _FFMPEG_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_BIN + ":" + os.environ.get("PATH", "")


load_dotenv()

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "")


def _get_env():
    env = os.environ.copy()
    env_path = os.getenv("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    if "/opt/homebrew/opt/ffmpeg-full/bin" not in env_path:
        env_path = "/opt/homebrew/opt/ffmpeg-full/bin:" + env_path
    env["PATH"] = env_path
    return env


def _ffmpeg_cmd():
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        return FFMPEG_PATH
    full_path = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    if os.path.exists(full_path):
        return full_path
    return "ffmpeg"


def _ffprobe_cmd():
    if FFPROBE_PATH and os.path.exists(FFPROBE_PATH):
        return FFPROBE_PATH
    full_path = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
    if os.path.exists(full_path):
        return full_path
    return "ffprobe"


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


def apply_ken_burns(input_path: str, output_path: str, target_w: int, target_h: int, duration: float, preset_idx: int = 0) -> bool:  # noqa: E501
    kb = KEN_BURNS_PRESETS[preset_idx % len(KEN_BURNS_PRESETS)]
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path,
        "-v", f"scale={target_w}*2:{target_h}*2,zoompan='{kb}':d={int(duration*30)}:s={target_w}x{target_h}:fps=30",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-cr", "23",
        "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_get_env())
        return result.returncode == 0
    except Exception as e:
        print(f"[compositor] Ken Burns error: {e}")
        return False


def trim_clip(input_path: str, output_path: str, start: float = 0, duration: float = 5) -> bool:
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path, "-ss", str(start), "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-cr", "23", "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=_get_env()).returncode == 0
    except Exception as e:
        print(f"[compositor] Trim error: {e}")
        return False


def resize_to_target(input_path: str, output_path: str, target_w: int, target_h: int) -> bool:
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path,
        "-v", f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
        "-c:v", "libx264", "-preset", "fast", "-cr", "23", "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=_get_env()).returncode == 0
    except Exception as e:
        print(f"[compositor] Resize error: {e}")
        return False


def mix_audio(voice_path: str, music_path: Optional[str], output_path: str, voice_volume_db: float = 0, music_volume_db: float = -18) -> bool:  # noqa: E501
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


def add_text_overlay(video_path: str, text: str, output_path: str, fontsize: int = 48, color: str = "white", position: str = "center", start_time: float = 0, duration: float = 3) -> bool:  # noqa: E501
    positions = {"center": "(w-text_w)/2:(h-text_h)/2",
                 "bottom": "(w-text_w)/2:(h-text_h)-50", "top": "(w-text_w)/2:50"}
    pos = positions.get(position, positions["center"])
    escaped_text = text.replace("'", "\\'").replace(":", "\\:").replace("-", "\\-")
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path,
        "-v", f"drawtext=text='{escaped_text}':fontsize={fontsize}:fontcolor={color}:x={pos}:enable='between(t,{start_time},{start_time+duration})'",  # noqa: E501
        "-c:v", "libx264", "-preset", "fast", "-cr", "23", "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=_get_env()).returncode == 0
    except Exception as e:
        print(f"[compositor] Text overlay error: {e}")
        return False


KIDS_FONT = "Marker Felt"
KIDS_SUB_COLORS = [
    {"primary": "&H00FFFF&", "outline": "&H0000FF&"},
    {"primary": "&HFF00FF&", "outline": "&H000080&"},
    {"primary": "&H00FF00&", "outline": "&H800000&"},
    {"primary": "&HFFFF00&", "outline": "&HFF0000&"},
    {"primary": "&HFF8000&", "outline": "&H000000&"},
]


def burn_subtitles(video_path: str, subtitle_path: str, output_path: str, fontsize: int = 24, is_kids: bool = True) -> bool:  # noqa: E501
    abs_subtitle = os.path.abspath(subtitle_path)
    if is_kids:
        temp_ass = str(TEMP_DIR / "kids_subtitles.ass")
        _convert_srt_to_kids_ass(abs_subtitle, temp_ass, fontsize)
        vf = f"subtitles=filename='{os.path.abspath(temp_ass)}'"
    else:
        vf = f"subtitles=filename='{abs_subtitle}':force_style='FontSize={fontsize},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Shadow=1'"  # noqa: E501
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-cr", "23",
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_get_env())
        if result.returncode == 0:
            print("[compositor] Subtitles burned successfully")
            return True
        else:
            print(f"[compositor] Subtitle burn error: {result.stderr[-300:]}")
            cmd_fallback = [
                _ffmpeg_cmd(), "-y", "-i", video_path,
                "-v", f"subtitles=filename='{abs_subtitle}':force_style='FontSize={fontsize},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Shadow=1'",  # noqa: E501
                "-c:v", "libx264", "-preset", "fast", "-cr", "23",
                "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
            ]
            result2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=300, env=_get_env())
            if result2.returncode == 0:
                print("[compositor] Subtitles burned with fallback style")
                return True
            return False
    except Exception as e:
        print(f"[compositor] Subtitle burn error: {e}")
        return False


def _convert_srt_to_kids_ass(srt_path: str, ass_path: str, base_fontsize: int = 36) -> bool:
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()
        blocks = re.split(r'\n\s*\n', srt_content.strip())
        ass_header = (
            "[Script Info]\n"
            "Title: Kids Subtitles\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,"
            "&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,10,10,40,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        font = KIDS_FONT
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header.format(font=font, size=base_fontsize))
            idx = 0
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 3:
                    continue
                try:
                    int(lines[0])
                except ValueError:
                    continue
                time_line = lines[1]
                text_lines = lines[2:]
                if '-->' not in time_line:
                    continue
                start, end = time_line.split('-->')
                start = start.strip().replace(',', '.')
                end = end.strip().replace(',', '.')
                text = ' '.join(t.strip() for t in text_lines)
                color = KIDS_SUB_COLORS[idx % len(KIDS_SUB_COLORS)]
                styled_text = r"{\c%s\3c%s\3%s\blur1}%s" % (
                    color["primary"], color["outline"], "b1", text
                )
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{styled_text}\n")
                idx += 1
        return True
    except Exception as e:
        print(f"[compositor] ASS conversion error: {e}")
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
        _ffmpeg_cmd(), "-y", "-i", video_path, "-i", metadata_path,
        "-map_metadata", "1",
        "-c:v", "copy", "-c:a", "copy", output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=_get_env())
        if result.returncode == 0:
            print(f"[compositor] Chapter markers added: {len(chapters)} chapters")
            return True
        return False
    except Exception as e:
        print(f"[compositor] Chapter markers error: {e}")
        return False


def composite_video(clips: list[dict], voice_path: str, music_path: Optional[str] = None, format_type: str = "shorts", video_id: str = "output", subtitle_path: Optional[str] = None, chapters: Optional[list] = None, category: str = "") -> Optional[str]:  # noqa: E501
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
    cmd = [_ffmpeg_cmd(), "-y", "-", "concat", "-safe", "0", "-i", concat_list_path,
           "-c:v", "libx264", "-preset", "fast", "-cr", "23", "-pix_fmt", "yuv420p", combined_video]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_get_env())
        if result.returncode != 0:
            print(f"[compositor] Concat error: {result.stderr[-300:]}")
    except Exception as e:
        print(f"[compositor] Concat error: {e}")
        return None

    if not os.path.exists(combined_video):
        return None

    if subtitle_path and os.path.exists(subtitle_path):
        print("[compositor] Burning subtitles into video")
        with_subs_path = str(TEMP_DIR / "video_with_subs.mp4")
        is_kids_content = any(kw in category.lower() for kw in [
                              "kids", "children", "bedtime", "fable", "rhyme", "story", "nursery", "baby", "toddler"])
        sub_fontsize = 52 if format_type == "shorts" else 36
        if burn_subtitles(combined_video, subtitle_path, with_subs_path, fontsize=sub_fontsize, is_kids=is_kids_content):  # noqa: E501
            combined_video = with_subs_path

    if chapters and format_type == "long":
        print("[compositor] Adding chapter markers")
        with_chapters_path = str(TEMP_DIR / "video_with_chapters.mp4")
        if add_chapter_markers(combined_video, chapters, with_chapters_path):
            combined_video = with_chapters_path

    mixed_audio_path = str(TEMP_DIR / "mixed_audio.wav")
    mix_audio(voice_path, music_path, mixed_audio_path)

    final_path = str(OUTPUT_DIR / f"{video_id}_{format_type}.mp4")
    cmd = [_ffmpeg_cmd(), "-y", "-i", combined_video, "-i", mixed_audio_path,
           "-c:v", "libx264", "-preset", "fast", "-cr", "23",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-pix_fmt", "yuv420p", final_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_get_env())
        if result.returncode == 0 and os.path.exists(final_path):
            print(f"[compositor] Final video: {final_path}")
            return final_path
    except Exception as e:
        print(f"[compositor] Final mux error: {e}")
    return None
