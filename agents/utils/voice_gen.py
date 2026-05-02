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

async def generate_segment_timing(text: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH) -> list[dict]:
    sentence_times = []
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        async for chunk in communicate.stream():
            if chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                sentence_times.append({
                    "text": chunk.get("text", ""),
                    "offset_ms": chunk.get("offset", 0) / 10000,
                    "duration_ms": chunk.get("duration", 0) / 10000,
                    "type": chunk["type"],
                })
    except Exception as e:
        print(f"[voice_gen] Timing error: {e}")
    return sentence_times

def generate_phrase_timings_from_sentences(text: str, sentence_times: list[dict]) -> list[dict]:
    sentences_in_text = re.split(r'(?<=[.!?])\s+', text.strip())
    phrase_timings = []
    max_words_per_phrase = 8

    for sent_time in sentence_times:
        offset = sent_time["offset_ms"]
        duration = sent_time["duration_ms"]
        sent_text = sent_time.get("text", "")

        matching_sentences = [s for s in sentences_in_text if sent_text and (s.strip() in sent_text or sent_text.strip() in s)]
        if not matching_sentences:
            continue

        for sent in matching_sentences:
            words = sent.split()
            if not words:
                continue

            if len(words) <= max_words_per_phrase:
                phrase_timings.append({
                    "text": " ".join(words),
                    "start_ms": offset,
                    "end_ms": offset + duration,
                })
            else:
                num_phrases = (len(words) + max_words_per_phrase - 1) // max_words_per_phrase
                phrase_duration = duration / num_phrases
                for i in range(num_phrases):
                    start_idx = i * max_words_per_phrase
                    end_idx = min(start_idx + max_words_per_phrase, len(words))
                    phrase_words = words[start_idx:end_idx]
                    phrase_timings.append({
                        "text": " ".join(phrase_words),
                        "start_ms": offset + (i * phrase_duration),
                        "end_ms": offset + ((i + 1) * phrase_duration),
                    })

    return phrase_timings

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
    all_phrase_timings = []
    cumulative_offset = 0.0

    for i, seg_text in enumerate(segments):
        seg_path = str(VOICE_DIR / f"seg_{i+1:03d}.wav")
        timing_path = str(VOICE_DIR / f"seg_{i+1:03d}_timing.json")
        success = await generate_segment_audio(seg_text, seg_path, voice=voice)
        if success:
            segment_files.append(seg_path)

            sentence_times = await generate_segment_timing(seg_text, voice=voice)
            if sentence_times:
                phrase_timings = generate_phrase_timings_from_sentences(seg_text, sentence_times)
                for pt in phrase_timings:
                    pt["start_ms"] += cumulative_offset
                    pt["end_ms"] += cumulative_offset
                all_phrase_timings.extend(phrase_timings)

                with open(timing_path, "w") as f:
                    json.dump({"sentences": sentence_times, "phrases": phrase_timings}, f)

            try:
                seg_audio = AudioSegment.from_file(seg_path)
                cumulative_offset += len(seg_audio) + 200
            except Exception:
                cumulative_offset += 5000

    output_path = str(VOICE_DIR / output_filename)
    concat_success = concatenate_audio(segment_files, output_path)

    timing_file = str(VOICE_DIR / "phrase_timing.json")
    if all_phrase_timings:
        with open(timing_file, "w") as f:
            json.dump(all_phrase_timings, f)
        print(f"[voice_gen] Generated {len(all_phrase_timings)} phrase timings")

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
        "timing_file": timing_file if all_phrase_timings else None,
        "phrase_timings": all_phrase_timings,
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
