import json
import os
from pathlib import Path
from typing import Optional

SUBTITLE_DIR = Path(__file__).parent.parent / "tmp" / "subtitles"
SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)


def load_phrase_timing(timing_file: str) -> list[dict]:
    if os.path.exists(timing_file):
        with open(timing_file, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("phrases", [])
    return []


def load_word_timing(timing_file: str) -> list[dict]:
    if os.path.exists(timing_file):
        with open(timing_file, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def generate_srt(timing_file: str, full_text: str, output_path: Optional[str] = None, language: str = "en") -> str:
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    phrases = load_phrase_timing(timing_file)

    if not phrases:
        words = load_word_timing(timing_file)
        if words:
            phrases = _convert_word_times_to_phrases(words)
        else:
            return ""

    srt_content = ""
    for i, phrase in enumerate(phrases, 1):
        start_time = _ms_to_srt_time(phrase.get("start_ms", 0))
        end_time = _ms_to_srt_time(phrase.get("end_ms", 0))
        text = phrase.get("text", "")
        if text:
            srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"

    if output_path is None:
        output_path = str(SUBTITLE_DIR / f"subtitles_{language}.srt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"[subtitle_gen] SRT saved: {output_path} ({len(phrases)} phrases)")
    return output_path


def generate_vtt(timing_file: str, full_text: str, output_path: Optional[str] = None, language: str = "en") -> str:
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    phrases = load_phrase_timing(timing_file)

    if not phrases:
        words = load_word_timing(timing_file)
        if words:
            phrases = _convert_word_times_to_phrases(words)
        else:
            return ""

    vtt_content = "WEBVTT\n\n"
    for i, phrase in enumerate(phrases, 1):
        start_time = _ms_to_vtt_time(phrase.get("start_ms", 0))
        end_time = _ms_to_vtt_time(phrase.get("end_ms", 0))
        text = phrase.get("text", "")
        if text:
            vtt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"

    if output_path is None:
        output_path = str(SUBTITLE_DIR / f"subtitles_{language}.vtt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)

    print(f"[subtitle_gen] VTT saved: {output_path} ({len(phrases)} phrases)")
    return output_path


def _convert_word_times_to_phrases(word_times: list[dict], max_words: int = 8) -> list[dict]:
    phrases = []
    current_words = []
    current_start = None
    current_end = None

    for wt in word_times:
        offset = wt.get("offset_ms", 0)
        duration = wt.get("duration_ms", 100)
        word = wt.get("word", "")

        if current_start is None:
            current_start = offset

        current_words.append(word)
        current_end = offset + duration

        if len(current_words) >= max_words or word.endswith((".", "!", "?")):
            phrases.append({
                "text": " ".join(current_words),
                "start_ms": current_start,
                "end_ms": current_end + 200,
            })
            current_words = []
            current_start = None
            current_end = None

    if current_words:
        phrases.append({
            "text": " ".join(current_words),
            "start_ms": current_start,
            "end_ms": current_end + 200,
        })

    return phrases


def _ms_to_srt_time(ms: float) -> str:
    total_seconds = int(ms / 1000)
    milliseconds = int(ms % 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _ms_to_vtt_time(ms: float) -> str:
    total_seconds = int(ms / 1000)
    milliseconds = int(ms % 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def generate_subtitles_for_video(
    timing_file: str,
    full_text: str,
    language: str = "en",
    formats: list = None,
) -> dict:
    if formats is None:
        formats = ["srt", "vtt"]

    results = {"language": language, "srt": None, "vtt": None}

    if "srt" in formats:
        results["srt"] = generate_srt(timing_file, full_text, language=language)

    if "vtt" in formats:
        results["vtt"] = generate_vtt(timing_file, full_text, language=language)

    return results
