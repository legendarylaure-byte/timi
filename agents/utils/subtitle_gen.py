import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUBTITLE_DIR = Path(__file__).parent.parent / "tmp" / "subtitles"
SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)


def _load_segment_timing_dir(timing_file: str) -> list[dict]:
    base = os.path.dirname(timing_file)
    if not base or not os.path.isdir(base):
        return []
    word_events = []
    pattern = re.compile(r"seg_(\d+)_timing\.json$")
    files = []
    for fname in os.listdir(base):
        m = pattern.match(fname)
        if m:
            files.append((int(m.group(1)), os.path.join(base, fname)))
    files.sort(key=lambda x: x[0])
    for _, fpath in files:
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            for sent in data.get("sentences", []):
                if sent.get("type") == "WordBoundary":
                    word_events.append(sent)
        except Exception:
            continue
    return word_events


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
    return _load_segment_timing_dir(timing_file)


def _fallback_to_word_timing(timing_file: str) -> list[dict]:
    word_events = load_word_timing(timing_file)
    if word_events:
        logger.warning("[subtitle_gen] Phrase timing empty, falling back to word-level timing (%d words)", len(word_events))
        return _convert_word_times_to_phrases(word_events)
    logger.warning("[subtitle_gen] Phrase timing empty and no word-level timing available")
    return []


def generate_srt(timing_file: str, full_text: str, output_path: Optional[str] = None, language: str = "en") -> str:
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    phrases = load_phrase_timing(timing_file)

    if not phrases:
        phrases = _fallback_to_word_timing(timing_file)

    if not phrases and full_text:
        logger.warning("[subtitle_gen] Phrase + word timings both empty, generating fallback SRT from full_text (%d chars)", len(full_text))
        sentences = re.split(r'(?<=[.!?])\s+', full_text.strip())
        words_per_sec = 2.5
        total_words = len(full_text.split())
        estimated_duration_ms = (total_words / words_per_sec) * 1000
        chunk_duration = estimated_duration_ms / max(len(sentences), 1)
        for i, sent in enumerate(sentences):
            sent = sent.strip()
            if not sent:
                continue
            words = sent.split()
            if len(words) <= 8:
                phrases.append({
                    "text": sent,
                    "start_ms": int(i * chunk_duration),
                    "end_ms": int((i + 1) * chunk_duration),
                })
            else:
                num_chunks = (len(words) + 8 - 1) // 8
                for j in range(num_chunks):
                    chunk_words = words[j * 8:(j + 1) * 8]
                    chunk_text = " ".join(chunk_words)
                    chunk_start = int((i + j / num_chunks) * chunk_duration)
                    chunk_end = int((i + (j + 1) / num_chunks) * chunk_duration)
                    phrases.append({
                        "text": chunk_text,
                        "start_ms": chunk_start,
                        "end_ms": chunk_end,
                    })

    if not phrases:
        logger.error("[subtitle_gen] No subtitles could be generated")
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

    logger.info("[subtitle_gen] SRT saved: %s (%d phrases, %d chars)", output_path, len(phrases), len(srt_content))
    return output_path


def generate_vtt(timing_file: str, full_text: str, output_path: Optional[str] = None, language: str = "en") -> str:
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    phrases = load_phrase_timing(timing_file)

    if not phrases:
        phrases = _fallback_to_word_timing(timing_file)
        if not phrases:
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

    logger.info("[subtitle_gen] VTT saved: %s (%d phrases)", output_path, len(phrases))
    return output_path


def _convert_word_times_to_phrases(word_times: list[dict], max_words: int = 8) -> list[dict]:
    phrases = []
    current_words = []
    current_start = None
    current_end = None

    for wt in word_times:
        offset = wt.get("offset_ms", 0)
        duration = wt.get("duration_ms", 100)
        word = wt.get("text", "")

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
