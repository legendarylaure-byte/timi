import os
import re
import json
import asyncio
import edge_tts
from pathlib import Path
from typing import Optional
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

VOICE_DIR = Path(__file__).parent.parent / "tmp" / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

KIDS_VOICES = {
    "narrator_female": "en-US-AnaNeural",
    "narrator_male": "en-US-ChristopherNeural",
    "narrator_warm": "en-US-AriaNeural",
    "narrator_cheerful": "en-US-JennyNeural",
}

DEFAULT_VOICE = KIDS_VOICES["narrator_warm"]
DEFAULT_RATE = "+10%"
DEFAULT_PITCH = "+2Hz"

def split_script_into_segments(script: str, max_chars: int = 300) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    segments = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars and current:
            segments.append(current.strip())
            current = sentence
        else:
            current = current + " " + sentence if current else sentence
    if current.strip():
        segments.append(current.strip())
    return segments

async def generate_segment_audio(text: str, output_path: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH) -> bool:
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 100
    except Exception as e:
        print(f"[voice_gen] Edge TTS error: {e}")
        return False

async def generate_word_timing(text: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH) -> list[dict]:
    word_times = []
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        async for chunk in communicate.stream():
            if chunk["type"] == "WordBoundary":
                word_times.append({
                    "word": chunk["text"],
                    "offset_ms": chunk["offset"] / 10000,
                    "duration_ms": chunk["duration"] / 10000,
                })
    except Exception as e:
        print(f"[voice_gen] Word timing error: {e}")
    return word_times

def concatenate_audio(segment_files: list[str], output_path: str) -> bool:
    try:
        combined = AudioSegment.empty()
        for f in segment_files:
            if os.path.exists(f):
                audio = AudioSegment.from_file(f)
                silence = AudioSegment.silent(duration=200)
                combined += audio + silence
        combined.export(output_path, format="wav")
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"[voice_gen] Concatenation error: {e}")
        return False

async def generate_voiceover(script: str, voice: str = DEFAULT_VOICE, output_filename: str = "voiceover.wav") -> dict:
    segments = split_script_into_segments(script)
    segment_files = []
    all_word_times = []

    for i, seg_text in enumerate(segments):
        seg_path = str(VOICE_DIR / f"seg_{i+1:03d}.wav")
        timing_path = str(VOICE_DIR / f"seg_{i+1:03d}_timing.json")
        success = await generate_segment_audio(seg_text, seg_path, voice=voice)
        if success:
            segment_files.append(seg_path)
            word_times = await generate_word_timing(seg_text, voice=voice)
            if word_times:
                with open(timing_path, "w") as f:
                    json.dump(word_times, f)
                all_word_times.extend(word_times)

    output_path = str(VOICE_DIR / output_filename)
    concat_success = concatenate_audio(segment_files, output_path)

    timing_file = str(VOICE_DIR / "word_timing.json")
    if all_word_times:
        with open(timing_file, "w") as f:
            json.dump(all_word_times, f)

    duration = 0.0
    if concat_success:
        try:
            audio = AudioSegment.from_file(output_path)
            duration = len(audio) / 1000.0
        except Exception:
            pass

    return {
        "path": output_path,
        "duration": duration,
        "segments": len(segment_files),
        "timing_file": timing_file if all_word_times else None,
        "success": concat_success,
    }

async def generate_voiceover_multi(translations: dict, voice_dir_suffix: str = "") -> dict:
    results = {}
    for lang_code, translation in translations.items():
        voice = translation.get("edge_tts_voice", DEFAULT_VOICE)
        script = translation.get("translated_script", "")
        filename = f"voiceover_{lang_code}{voice_dir_suffix}.wav"
        print(f"[voice_gen] Generating voiceover for {lang_code} with voice {voice}")
        result = await generate_voiceover(script, voice=voice, output_filename=filename)
        results[lang_code] = {
            **result,
            "language": lang_code,
            "translated_title": translation.get("title", ""),
        }
    return results
