from dotenv import load_dotenv
from pydub import AudioSegment
import os
import re
import json
import edge_tts
from pathlib import Path

_FFMPEG_BIN = None
for _candidate in ["/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/bin", "/usr/bin"]:
    if os.path.exists(os.path.join(_candidate, "ffmpeg")):
        _FFMPEG_BIN = _candidate
        break
if _FFMPEG_BIN and _FFMPEG_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_BIN + ":" + os.environ.get("PATH", "")


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
DEFAULT_RATE = "-5%"
DEFAULT_PITCH = "-2Hz"


def extract_narration_text(script: str, is_long_form: bool = False) -> str:
    skip_patterns = [
        r'^#{1,6}\s',
        r'^\*{1,2}Scene\s*:',
        r'^Scene\s*:',
        r'^\*{1,2}Scene\s+\d+',
        r'^Scene\s+\d+',
        r'^\*{1,2}Visual\s+Description',
        r'^\*{1,2}Emotional\s+Beat',
        r'^\*{1,2}Engagement\s+Hook',
        r'^\*{1,2}Educational\s+Value',
        r'^\*{1,2}Dialogue\s*:\s*$',
        r'^-?\s*\*{1,2}(Visual|Camera|Color|Background|Transition|Mood)\*{1,2}',
        r'^\*\*\s*$',
        r'^[\*\-_]{3,}$',
        r'^#\w',
        r'^\d{1,2}:\d{2}',
        r'\(\d+-\d+\s*seconds?\)',
        r'^\[\d+-\d+\s*seconds?\]',
        r'^End\s+of\s+(Script|Storyboard)',
        r'^For\s+each\s+scene\s+include',
        r'^Optimize\s+for',
        r'^This\s+(script|storyboard|detailed\s+storyboard|video)',
        r'^The\s+script\s+is\s+designed',
        r'^This\s+detailed\s+storyboard',
        r'^\d+\.\s+\*\*',
    ]

    if not is_long_form:
        skip_patterns.extend([
            r'^Camera\s+Angle',
            r'^Character\s+Positions',
            r'^Color\s+Palette',
            r'^Background\s+Elements',
            r'^Transition\s+to',
            r'^Mood\s+(and\s+)?Emotional',
            r'^\d+\.\s+Camera\s+',
            r'^\d+\.\s+Character\s+',
            r'^\d+\.\s+Color\s+',
            r'^\d+\.\s+Background\s+',
            r'^\d+\.\s+Transition\s+',
            r'^\d+\.\s+Mood\s+',
        ])
    lines = script.split('\n')
    narration_parts = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(re.match(pattern, stripped, re.IGNORECASE) for pattern in skip_patterns):
            continue
        if re.search(r'\bDialogue\b', stripped, re.IGNORECASE) and ':' in stripped:
            parts = stripped.split(':', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                text = re.sub(r'[\*\'\"]', '', text).strip()
                if text and len(text) > 5:
                    narration_parts.append(text)
                continue
        if re.search(r'\bNarration\b', stripped, re.IGNORECASE) and ':' in stripped:
            parts = stripped.split(':', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                text = re.sub(r'[\*\'\"]', '', text).strip()
                if text and len(text) > 5:
                    narration_parts.append(text)
                continue
        cleaned = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', stripped)
        cleaned = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', cleaned)
        generic_dialogue = re.search(
            r'[\w\s]+\s*\(?(?:voiceover|to \w+)?\)?\s*:\s*["\u2018\u2019](.+?)["\u2018\u2019]', cleaned, re.IGNORECASE)
        if generic_dialogue:
            narration_parts.append(generic_dialogue.group(1).strip())
            continue
        dialogue_match = re.search(
            r'(?:Narrator|Narr\.?|Child\s*\d*|Character|Host|Voice|Speaker)\s*:\s*["\u2018\u2019](.+?)["\u2018\u2019]', cleaned, re.IGNORECASE)  # noqa: E501
        if dialogue_match:
            narration_parts.append(dialogue_match.group(1).strip())
            continue
        char_match = re.search(
            r'(?:Narrator|Narr\.?|Child\s*\d*|Character|Host|Voice|Speaker)\s*:\s*(.+)', cleaned, re.IGNORECASE)
        if char_match:
            text = char_match.group(1).strip()
            text = text.strip("'").strip('"').strip()
            if text and len(text) > 2:
                narration_parts.append(text)
            continue
        if not cleaned.startswith('*') and not cleaned.startswith('**') and not cleaned.startswith('-') and not cleaned.startswith('#'):  # noqa: E501
            metadata_keywords = ['camera angle', 'character position', 'color palette',
                                 'background element', 'transition to', 'mood and emotional', 'educational value']
            if any(kw in cleaned.lower() for kw in metadata_keywords):
                continue
            if re.match(r'^\d+\.\s+', cleaned):
                continue
            if len(cleaned) > 5:
                narration_parts.append(cleaned)
    result = ' '.join(narration_parts)
    result = re.sub(r'\s+', ' ', result).strip()
    result = re.sub(r'[^\w\s.,!?\'\-:;()&%$#@+=]', '', result)
    result = re.sub(r'\s+', ' ', result).strip()
    if not result or len(result) < 20:
        print("[voice_gen] WARNING: Narration extraction produced empty/short text, using fallback")
        fallback_lines = []
        for line in lines:
            s = line.strip()
            quote_match = re.findall(r'["\'"]([^"\']+?)["\'"]', s)
            for q in quote_match:
                if len(q) > 5 and not any(w in q.lower() for w in ['scene', 'visual', 'camera', 'color', 'background', 'transition', 'mood']):  # noqa: E501
                    fallback_lines.append(q)
        if fallback_lines:
            result = ' '.join(fallback_lines)
        else:
            result = re.sub(r'\*[^*]+\*', '', script)
            result = re.sub(r'#{1,6}\s', '', result)
            result = re.sub(r'\n\s*\n', '\n', result)
            result = re.sub(r'\s+', ' ', result).strip()
    return result


def get_voice_settings(content_type: str = "general") -> dict:
    settings = {
        "bedtime": {
            "voice": "en-US-JennyNeural",
            "rate": "-10%",
            "pitch": "-4Hz",
        },
        "story": {
            "voice": "en-GB-SoniaNeural",
            "rate": "-5%",
            "pitch": "-2Hz",
        },
        "educational": {
            "voice": "en-US-JennyNeural",
            "rate": "-5%",
            "pitch": "-2Hz",
        },
        "energetic": {
            "voice": "en-US-JennyNeural",
            "rate": "+5%",
            "pitch": "+2Hz",
        },
        "general": {
            "voice": DEFAULT_VOICE,
            "rate": DEFAULT_RATE,
            "pitch": DEFAULT_PITCH,
        }
    }
    return settings.get(content_type, settings["general"])


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


async def generate_segment_audio(text: str, output_path: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH) -> bool:  # noqa: E501
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 100
    except Exception as e:
        print(f"[voice_gen] Edge TTS error: {e}")
        return False


async def generate_segment_timing(text: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH) -> list[dict]:  # noqa: E501
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

        matching_sentences = [s for s in sentences_in_text if sent_text and (
            s.strip() in sent_text or sent_text.strip() in s)]
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


async def generate_voiceover(script: str, voice: str = DEFAULT_VOICE, output_filename: str = "voiceover.wav", content_type: str = "general", is_long_form: bool = False) -> dict:  # noqa: E501
    narration_text = extract_narration_text(script, is_long_form=is_long_form)
    print(f"[voice_gen] Original script: {len(script)} chars -> Narration: {len(narration_text)} chars")
    if not narration_text.strip():
        print("[voice_gen] WARNING: Narration extraction failed, using raw script")
        narration_text = script
    voice_settings = get_voice_settings(content_type)
    if voice == DEFAULT_VOICE:
        voice = voice_settings["voice"]
    rate = voice_settings["rate"]
    pitch = voice_settings["pitch"]
    print(f"[voice_gen] Voice: {voice}, Rate: {rate}, Pitch: {pitch}")
    segments = split_script_into_segments(narration_text)
    segment_files = []
    all_phrase_timings = []
    cumulative_offset = 0.0

    for i, seg_text in enumerate(segments):
        seg_path = str(VOICE_DIR / f"seg_{i+1:03d}.wav")
        timing_path = str(VOICE_DIR / f"seg_{i+1:03d}_timing.json")
        success = await generate_segment_audio(seg_text, seg_path, voice=voice, rate=rate, pitch=pitch)
        if success:
            segment_files.append(seg_path)

            sentence_times = await generate_segment_timing(seg_text, voice=voice, rate=rate, pitch=pitch)
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
