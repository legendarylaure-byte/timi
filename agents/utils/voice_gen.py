from dotenv import load_dotenv
from pydub import AudioSegment
import os
import re
import json
import asyncio
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
DEFAULT_RATE = "-8%"
DEFAULT_PITCH = "-2Hz"

NARRATOR_VOICE = {"voice": "en-US-JennyNeural", "rate": "-8%", "pitch": "-2Hz"}

SSML_EMPHASIS_WORDS = [
    "key", "important", "crucial", "critical", "essential", "fundamental",
    "never", "always", "must", "cannot", "extremely", "remarkably",
    "significantly", "dramatically", " revolutionary", " breakthrough",
]


def _wrap_ssml(text: str, voice_name: str = None, rate: str = "0%") -> str:
    """Wrap narration text with SSML for improved prosody.
    
    Adds emphasis on key terms, micro-pauses at punctuation, and prosody control.
    """
    emphasized = text
    for word in SSML_EMPHASIS_WORDS:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        emphasized = pattern.sub(lambda m: f"<emphasis level=\"strong\">{m.group()}</emphasis>", emphasized)
    emphasized = re.sub(r'([.?!])\s+', r'\1<break time="300ms"/> ', emphasized)
    emphasized = re.sub(r'([,;:])\s', r'\1<break time="100ms"/> ', emphasized)
    voice_attr = f" name=\"{voice_name}\"" if voice_name else ""
    ssml = (
        f"<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" xml:lang=\"en-US\">"
        f"<prosody rate=\"{rate}\">{emphasized}</prosody>"
        f"</speak>"
    )
    return ssml


def _expand_symbols_for_tts(text: str) -> str:
    text = re.sub(r'https?://\S+', ' link ', text)
    text = re.sub(r'www\.\S+', ' link ', text)
    expansions = [
        (r'\bC\+\+', 'C plus plus'),
        (r'\bC#', 'C sharp'),
        (r'\bF#', 'F sharp'),
        (r'\b\.NET\b', 'dot net'),
        (r'\bA\+\+', 'A plus'),
        (r'(\w+)/(\w+)', r'\1 or \2'),
        (r' \+ ', ' plus '),
        (r' = ', ' equals '),
        (r' != ', ' not equal to '),
        (r' == ', ' equals '),
        (r' <= ', ' less than or equal to '),
        (r' >= ', ' greater than or equal to '),
        (r' < ', ' less than '),
        (r' > ', ' greater than '),
        (r' && ', ' and '),
        (r' \|\| ', ' or '),
        (r' \| ', ' pipe '),
        (r' #(\w)', r' hash \1'),
        (r' \* ', ' times '),
        (r' & ', ' and '),
        (r' % ', ' percent '),
        (r' ~ ', ' approximately '),
        (r' @ ', ' at '),
        (r' \{', ' open brace '),
        (r' \}', ' close brace '),
        (r' \[', ' open bracket '),
        (r' \]', ' close bracket '),
        (r' \\ ', ' backslash '),
        (r'`(\w+)`', r'\1'),
    ]
    result = text
    for pattern, replacement in expansions:
        result = re.sub(pattern, replacement, result)
    return result


def _extract_narration_via_markers(script: str) -> str | None:
    """Primary method: extract text between NARRATION: markers (new format)."""
    lines = script.split('\n')
    in_narration = False
    parts = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith('NARRATION:'):
            in_narration = True
            text = stripped.split(':', 1)[1].strip()
            if text:
                parts.append(text)
            continue
        if stripped.upper().startswith('VISUAL:'):
            in_narration = False
            continue
        if re.match(r'^--SCENE\s+\d+--', stripped, re.IGNORECASE):
            in_narration = False
            continue
        if in_narration and stripped:
            maybe_dialogue = re.split(r'^[A-Z][A-Z\s]+:\s*', stripped, maxsplit=1)
            if len(maybe_dialogue) > 1 and maybe_dialogue[-1].strip():
                parts.append(maybe_dialogue[-1].strip())
            elif stripped and not any(
                kw in stripped.lower()
                for kw in ['camera', 'angle', 'color palette', 'background',
                           'transition', 'mood', 'emotional', 'educational']
            ):
                parts.append(stripped)
    if parts:
        return ' '.join(parts)
    return None


def _extract_narration_via_dialogue_tags(script: str) -> str | None:
    """Secondary method: extract text after character dialogue tags."""
    lines = script.split('\n')
    parts = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        char_match = re.match(
            r'^(NARRATOR|NARR\.?|HOST|VOICE|SPEAKER)\s*:\s*(.+)',
            stripped, re.IGNORECASE)
        if char_match:
            text = char_match.group(2).strip()
            text = re.sub(r'^["\'\u2018\u2019]+|["\'\u2018\u2019]+$', '', text).strip()
            if text and len(text) > 2:
                parts.append(text)
            continue
        if re.match(r'^["\u2018\u2019](.+?)["\u2018\u2019]', stripped):
            text = re.sub(r'^["\'\u2018\u2019]+|["\'\u2018\u2019]+$', '', stripped).strip()
            if text and len(text) > 5:
                parts.append(text)
    if parts:
        return ' '.join(parts)
    return None


def extract_narration_text(script: str, is_long_form: bool = False) -> str:
    skip_patterns = [
        r'^--SCENE\s+\d+--',
        r'^#{1,6}\s',
        r'^\*{1,2}Scene\s*:',
        r'^Scene\s*:',
        r'^\*{1,2}Scene\s+\d+',
        r'^Scene\s+\d+',
        r'^VISUAL\s*:',
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
        r'^Educational\s+[Vv]alue',
        r'^Call.to.action',
        r'^Age\s+[Gg]roup',
        r'^Language\s+must\s+be',
    ]

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

    result = _extract_narration_via_markers(script)
    if result and len(result) > 50:
        return result

    result = _extract_narration_via_dialogue_tags(script)
    if result and len(result) > 50:
        return result

    lines = script.split('\n')
    narration_parts = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(re.match(pattern, stripped, re.IGNORECASE) for pattern in skip_patterns):
            continue
        colon_match = re.match(r'^[A-Z][A-Z\s]+:\s*(.+)', stripped)
        if colon_match and not re.match(r'^(HTTP|HTTPS|WWW)\b', stripped, re.IGNORECASE):
            text = colon_match.group(1).strip()
            text = re.sub(r'[\*\'\"]', '', text).strip()
            if text and len(text) > 5:
                narration_parts.append(text)
            continue
        cleaned = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', stripped)
        cleaned = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', cleaned)
        if not cleaned.startswith('*') and not cleaned.startswith('**') and not cleaned.startswith('-') and not cleaned.startswith('#'):
            metadata_keywords = ['camera angle', 'character position', 'color palette',
                                 'background element', 'transition to', 'mood and emotional',
                                 'educational value', 'educational value statement', 'call to action']
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

    if not result or len(result) < 100:
        print("[voice_gen] WARNING: Narration extraction produced empty/short text, using fallback")
        fallback_lines = []
        for line in lines:
            s = line.strip()
            quote_match = re.findall(r'["\'"]([^"\']+?)["\'"]', s)
            for q in quote_match:
                if len(q) > 5 and not any(w in q.lower() for w in ['scene', 'visual', 'camera', 'color', 'background', 'transition', 'mood']):
                    fallback_lines.append(q)
        if fallback_lines:
            result = ' '.join(fallback_lines)
        else:
            result = re.sub(r'\*[^*]+\*', '', script)
            result = re.sub(r'#{1,6}\s', '', result)
            result = re.sub(r'\n\s*\n', '\n', result)
            result = re.sub(r'\s+', ' ', result).strip()
    return result


def parse_dialogue_segments(script: str) -> list[dict]:
    """Parse script into ordered list of {character, text} segments.

    Handles multiple formats:
    1. NARRATION:/VISUAL: markers (new pipeline format)
    2. CHARACTER_NAME: dialogue text (e.g. NARRATOR: Hello!)
    3. Plain text with no markers -> NARRATOR
    """
    lines = script.split('\n')
    segments = []
    current_character = None
    current_text = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.upper().startswith('VISUAL:') or re.match(r'^--SCENE\s+\d+--', stripped, re.IGNORECASE):
            if current_text:
                segments.append({"character": current_character, "text": ' '.join(current_text)})
                current_text = []
                current_character = None
            continue

        if stripped.upper().startswith('NARRATION:'):
            if current_text:
                segments.append({"character": current_character, "text": ' '.join(current_text)})
                current_text = []
            current_character = "NARRATOR"
            text = stripped.split(':', 1)[1].strip()
            if text:
                current_text.append(text)
            continue

        narrator_match = re.match(r'^(NARRATOR)\s*:\s*(.+)', stripped, re.IGNORECASE)
        if narrator_match:
            if current_text:
                segments.append({"character": current_character, "text": ' '.join(current_text)})
                current_text = []
            current_character = "NARRATOR"
            text = narrator_match.group(2).strip()
            if text:
                current_text.append(text)
            continue

        is_technical = any(kw in stripped.lower() for kw in
                           ['camera', 'angle', 'color palette', 'background',
                            'transition', 'mood', 'visual', 'educational value',
                            'call to action', 'character position'])
        if is_technical:
            continue

        if current_character:
            current_text.append(stripped)
        else:
            current_character = "NARRATOR"
            current_text.append(stripped)

    if current_text:
        segments.append({"character": current_character, "text": ' '.join(current_text)})

    merged = []
    for seg in segments:
        if merged and merged[-1]["character"] == seg["character"]:
            merged[-1]["text"] += " " + seg["text"]
        else:
            merged.append(seg)

    return merged


def _compute_dynamic_rates(segments: list[str], content_type: str, base_rate: str) -> list[str]:
    base_pct = int(base_rate.replace("%", "").replace("+", "") or "0")
    rates = []
    total = len(segments)
    for i, text in enumerate(segments):
        rate_adj = 0
        if i == 0 and total > 1:
            rate_adj = 5
        elif content_type == "educational":
            word_count = len(text.split())
            if word_count > 35:
                rate_adj = -5
            elif "this means" in text.lower() or "in other words" in text.lower():
                rate_adj = -5
            elif "for example" in text.lower() or "think of" in text.lower():
                rate_adj = -3
        rate_val = max(-50, min(50, base_pct + rate_adj))
        sign = "+" if rate_val >= 0 else ""
        rates.append(f"{sign}{rate_val}%")
    return rates


def get_voice_settings(content_type: str = "general") -> dict:
    settings = {
        "storytelling": {
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
            "rate": "-8%",
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
    from utils.voice_provider import get_tts_provider
    provider = get_tts_provider()
    return await provider.generate(text, output_path, voice, rate, pitch)


async def generate_segment_timing(text: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH) -> list[dict]:  # noqa: E501
    from utils.voice_provider import get_tts_provider
    provider = get_tts_provider()
    return await provider.generate_timing(text, voice, rate, pitch)


def generate_phrase_timings_from_sentences(text: str, sentence_times: list[dict]) -> list[dict]:
    max_words_per_phrase = 8
    phrase_timings = []

    sentence_events = [st for st in sentence_times if st.get("type") == "SentenceBoundary"]
    word_events = [wt for wt in sentence_times if wt.get("type") == "WordBoundary"]

    sentences_in_text = re.split(r'(?<=[.!?])\s+', text.strip())
    used_indices = set()

    for sent_time in sentence_events:
        offset = sent_time["offset_ms"]
        duration = sent_time["duration_ms"]
        sent_text = sent_time.get("text", "").strip()
        if not sent_text:
            continue

        for i, s in enumerate(sentences_in_text):
            if i in used_indices:
                continue
            s_norm = s.strip()
            if s_norm in sent_text or sent_text in s_norm:
                used_indices.add(i)
                words = s_norm.split()
                if not words:
                    break
                if len(words) <= max_words_per_phrase:
                    phrase_timings.append({
                        "text": " ".join(words),
                        "start_ms": offset,
                        "end_ms": offset + duration,
                    })
                else:
                    num_phrases = (len(words) + max_words_per_phrase - 1) // max_words_per_phrase
                    phrase_duration = duration / num_phrases
                    for j in range(num_phrases):
                        idx = j * max_words_per_phrase
                        phrase_words = words[idx:idx + max_words_per_phrase]
                        phrase_timings.append({
                            "text": " ".join(phrase_words),
                            "start_ms": offset + (j * phrase_duration),
                            "end_ms": offset + ((j + 1) * phrase_duration),
                        })
                break

    if not phrase_timings and word_events:
        current_words = []
        current_start = None
        for wt in word_events:
            offset = wt.get("offset_ms", 0)
            duration = wt.get("duration_ms", 100)
            word = wt.get("text", "")
            if not word:
                continue
            if current_start is None:
                current_start = offset
            current_words.append(word)
            if len(current_words) >= max_words_per_phrase:
                phrase_timings.append({
                    "text": " ".join(current_words),
                    "start_ms": current_start,
                    "end_ms": offset + duration,
                })
                current_words = []
                current_start = None
        if current_words and current_start is not None:
            last = word_events[-1]
            phrase_timings.append({
                "text": " ".join(current_words),
                "start_ms": current_start,
                "end_ms": last.get("offset_ms", 0) + last.get("duration_ms", 100),
            })

    return phrase_timings


SECTION_TRANSITION_WORDS = [
    "now", "next", "finally", "first", "second", "third",
    "another", "however", "meanwhile", "in addition",
    "let's talk", "let me", "moving on", "beyond that",
    "the real", "what makes", "at its", "in practice",
    "specifically", "for instance", "for example",
    "the key", "crucially", "importantly",
]


def _detect_section_transition(segments: list[str]) -> list[int]:
    gaps = []
    base_gap = 300
    for i, seg in enumerate(segments):
        lower = seg.lower().strip()
        is_transition = any(lower.startswith(w) for w in SECTION_TRANSITION_WORDS)
        if is_transition and i > 0:
            gaps.append(1200)
        else:
            gaps.append(base_gap)
    return gaps


def concatenate_audio(segment_files: list[str], output_path: str, gap_ms: list[int] = None) -> bool:
    try:
        combined = AudioSegment.empty()
        fade_ms = 50
        for i, f in enumerate(segment_files):
            if os.path.exists(f):
                audio = AudioSegment.from_file(f)
                if len(audio) > fade_ms * 2:
                    audio = audio.fade_in(fade_ms).fade_out(fade_ms)
                gap = (gap_ms[i] if gap_ms and i < len(gap_ms) else 300)
                if i > 0 and gap < 100 and len(combined) > 50:
                    overlap = min(gap, fade_ms)
                    seg_start = audio[:overlap].fade_in(overlap) * 0.5
                    combined_end = combined[-overlap:].fade_out(overlap) * 0.5
                    combined = combined[:-overlap] + combined_end.overlay(seg_start)
                    audio = audio[overlap:]
                    gap = 0
                silence = AudioSegment.silent(duration=gap)
                combined += audio + silence
        if len(combined) > 200:
            combined = combined.fade_in(150).fade_out(200)
        combined.export(output_path, format="wav")
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"[voice_gen] Concatenation error: {e}")
        return False


async def generate_voiceover(script: str, voice: str = DEFAULT_VOICE, output_filename: str = "voiceover.wav", content_type: str = "general", is_long_form: bool = False) -> dict:  # noqa: E501
    VOICE_DIR.mkdir(parents=True, exist_ok=True)

    dialogue_segments = parse_dialogue_segments(script)
    has_multi_character = len({s["character"] for s in dialogue_segments}) > 1 or any(
        s["character"] != "NARRATOR" for s in dialogue_segments)

    if has_multi_character:
        print(f"[voice_gen] Multi-voice: {len(dialogue_segments)} segments, characters: {set(s['character'] for s in dialogue_segments)}")
        return await _generate_multi_voice(dialogue_segments, output_filename)

    narration_text = extract_narration_text(script, is_long_form=is_long_form)
    print(f"[voice_gen] Single voice: {len(script)} chars -> {len(narration_text)} chars")
    if not narration_text.strip():
        print("[voice_gen] WARNING: Narration extraction failed, using raw script")
        narration_text = script
    narration_text = _expand_symbols_for_tts(narration_text)
    voice_settings = get_voice_settings(content_type)
    if voice == DEFAULT_VOICE:
        voice = voice_settings["voice"]
    base_rate = voice_settings["rate"]
    pitch = voice_settings["pitch"]

    segments = split_script_into_segments(narration_text)
    seg_rates = _compute_dynamic_rates(segments, content_type, base_rate)

    print(f"[voice_gen] Voice: {voice}, Pitch: {pitch}, Rates: {seg_rates[:5]}{'...' if len(seg_rates) > 5 else ''}")

    _tts_sem = asyncio.Semaphore(5)

    async def _gen_seg(i: int, seg_text: str, seg_rate: str) -> tuple[int, str, bool]:
        seg_path = str(VOICE_DIR / f"seg_{i+1:03d}.wav")
        async with _tts_sem:
            success = await generate_segment_audio(seg_text, seg_path, voice=voice, rate=seg_rate, pitch=pitch)
        return i, seg_path, success

    results = await asyncio.gather(*[_gen_seg(i, s, seg_rates[i]) for i, s in enumerate(segments)])

    segment_files = [r[1] for r in sorted(results) if r[2]]
    all_phrase_timings = []
    cumulative_offset = 0.0
    gap_ms = _detect_section_transition(segments)

    for i, seg_text in enumerate(segments):
        seg_path = str(VOICE_DIR / f"seg_{i+1:03d}.wav")
        if seg_path not in segment_files:
            continue
        timing_path = str(VOICE_DIR / f"seg_{i+1:03d}_timing.json")

        sentence_times = await generate_segment_timing(seg_text, voice=voice, rate=seg_rates[i], pitch=pitch)
        if sentence_times:
            phrase_timings = generate_phrase_timings_from_sentences(seg_text, sentence_times)
            for pt in phrase_timings:
                pt["start_ms"] += cumulative_offset
                pt["end_ms"] += cumulative_offset
            all_phrase_timings.extend(phrase_timings)

            with open(timing_path, "w") as f:
                json.dump({"sentences": sentence_times, "phrases": phrase_timings}, f)

        this_gap = gap_ms[i] if i < len(gap_ms) else 300
        try:
            seg_audio = AudioSegment.from_file(seg_path)
            cumulative_offset += len(seg_audio) + this_gap
        except Exception as e:
            print(f"[voice_gen] Failed to load seg_{i+1:03d} audio, guessing 5s offset: {e}")
            cumulative_offset += 5000

    output_path = str(VOICE_DIR / output_filename)
    concat_success = concatenate_audio(segment_files, output_path, gap_ms=gap_ms)

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


async def _generate_multi_voice(dialogue_segments: list[dict], output_filename: str) -> dict:
    """Generate voiceover with multiple character-specific voices."""
    segment_files = []
    all_phrase_timings = []
    cumulative_offset = 0.0
    seg_idx = 0

    for seg in dialogue_segments:
        character = seg["character"]
        text = seg["text"]
        if not text.strip():
            continue

        char_cfg = NARRATOR_VOICE
        voice = char_cfg["voice"]
        rate = char_cfg["rate"]
        pitch = char_cfg["pitch"]

        sub_segments = split_script_into_segments(text)
        for sub_text in sub_segments:
            seg_idx += 1
            seg_path = str(VOICE_DIR / f"seg_{seg_idx:03d}.wav")
            timing_path = str(VOICE_DIR / f"seg_{seg_idx:03d}_timing.json")

            success = await generate_segment_audio(sub_text, seg_path, voice=voice, rate=rate, pitch=pitch)
            if not success:
                continue

            segment_files.append(seg_path)

            sentence_times = await generate_segment_timing(sub_text, voice=voice, rate=rate, pitch=pitch)
            if sentence_times:
                phrase_timings = generate_phrase_timings_from_sentences(sub_text, sentence_times)
                for pt in phrase_timings:
                    pt["start_ms"] += cumulative_offset
                    pt["end_ms"] += cumulative_offset
                all_phrase_timings.extend(phrase_timings)

                with open(timing_path, "w") as f:
                    json.dump({"sentences": sentence_times, "phrases": phrase_timings}, f)

            try:
                seg_audio = AudioSegment.from_file(seg_path)
                cumulative_offset += len(seg_audio) + 100
            except Exception as e:
                print(f"[voice_gen] Failed to load seg_{seg_idx:03d} audio, guessing 5s offset: {e}")
                cumulative_offset += 5000

    output_path = str(VOICE_DIR / output_filename)
    concat_success = concatenate_audio(segment_files, output_path)

    timing_file = str(VOICE_DIR / "phrase_timing.json")
    if all_phrase_timings:
        with open(timing_file, "w") as f:
            json.dump(all_phrase_timings, f)
        print(f"[voice_gen] Multi-voice: {seg_idx} segments, {len(set(s['character'] for s in dialogue_segments))} characters")

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
