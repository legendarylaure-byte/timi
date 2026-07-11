import os
import asyncio
import json
import logging
from pathlib import Path
from utils.llm_client import generate_completion
from utils.json_utils import extract_json

logger = logging.getLogger(__name__)

LANGUAGES = {
    "es": {
        "name": "Spanish",
        "edge_tts_voice": "es-ES-ElviraNeural",
        "alt_voice": "es-MX-DaliaNeural",
        "countries": ["Spain", "Mexico", "Latin America"],
        "cpm_tier": "tier1",
    },
    "de": {
        "name": "German",
        "edge_tts_voice": "de-DE-KatjaNeural",
        "alt_voice": "de-DE-ConradNeural",
        "countries": ["Germany", "Austria", "Switzerland"],
        "cpm_tier": "tier1",
    },
    "fr": {
        "name": "French",
        "edge_tts_voice": "fr-FR-DeniseNeural",
        "alt_voice": "fr-CA-SylvieNeural",
        "countries": ["France", "Canada", "Belgium"],
        "cpm_tier": "tier1",
    },
    "pt": {
        "name": "Portuguese",
        "edge_tts_voice": "pt-BR-FranciscaNeural",
        "alt_voice": "pt-PT-RaquelNeural",
        "countries": ["Brazil", "Portugal"],
        "cpm_tier": "tier2",
    },
    "hi": {
        "name": "Hindi",
        "edge_tts_voice": "hi-IN-SwaraNeural",
        "alt_voice": "hi-IN-MadhurNeural",
        "countries": ["India"],
        "cpm_tier": "tier3",
    },
    "ar": {
        "name": "Arabic",
        "edge_tts_voice": "ar-SA-ZariyahNeural",
        "alt_voice": "ar-EG-SalmaNeural",
        "countries": ["Saudi Arabia", "Egypt", "UAE"],
        "cpm_tier": "tier2",
    },
    "ja": {
        "name": "Japanese",
        "edge_tts_voice": "ja-JP-NanamiNeural",
        "alt_voice": "ja-JP-KeitaNeural",
        "countries": ["Japan"],
        "cpm_tier": "tier1",
    },
    "ko": {
        "name": "Korean",
        "edge_tts_voice": "ko-KR-SunHiNeural",
        "alt_voice": "ko-KR-InJoonNeural",
        "countries": ["South Korea"],
        "cpm_tier": "tier1",
    },
}

SYSTEM_PROMPT = """You are a professional translator specializing in tech content localization.
Translate the given English script into the target language while:
1. Using correct technical terminology
2. Preserving the educational value and tone
3. Adapting cultural references to be locally relevant
4. Maintaining the same number of sentences/segments for audio sync
5. Keeping proper nouns and technical terms untranslated where appropriate

Return ONLY a valid JSON object with this structure:
{
  "translated_script": "Full translated text",
  "segments": ["translated segment 1", "translated segment 2", ...],
  "title": "Translated video title",
  "description_snippet": "Short description in target language"
}"""


def translate_script(script: str, target_lang: str, title: str = "") -> dict:
    lang = LANGUAGES.get(target_lang)
    if not lang:
        raise ValueError(f"Unsupported language: {target_lang}")

    prompt = f"""Translate this tech educational content to {lang['name']} ({target_lang}):

Original title: {title if title else "N/A"}

Original script:
{script}

Translate all content to {lang['name']} while preserving technical accuracy and terminology."""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2000,
        )

        result = extract_json(response)
        if result is None:
            return _fallback_translation(script, title, target_lang, lang)
        result["language_code"] = target_lang
        result["language_name"] = lang["name"]
        result["edge_tts_voice"] = lang["edge_tts_voice"]
        return result
    except Exception as e:
        print(f"[translate] Translation error: {e}")
        return _fallback_translation(script, title, target_lang, lang)


def _fallback_translation(script: str, title: str, lang_code: str, lang_info: dict) -> dict:
    segments = script.split(". ")
    return {
        "translated_script": f"[{lang_info['name']}] {script}",
        "segments": [f"[{lang_info['name']}] {s}" for s in segments],
        "title": f"[{lang_info['name']}] {title}",
        "description_snippet": f"Content in {lang_info['name']}",
        "language_code": lang_code,
        "language_name": lang_info["name"],
        "edge_tts_voice": lang_info["edge_tts_voice"],
    }


def translate_script_batch(script: str, title: str = "", languages: list = None) -> dict:
    if languages is None:
        languages = ["es", "de", "fr", "pt", "hi", "ar"]

    results = {}
    for lang_code in languages:
        if lang_code not in LANGUAGES:
            continue
        print(f"[translate] Translating to {LANGUAGES[lang_code]['name']}...")
        results[lang_code] = translate_script(script, lang_code, title)
    return results


def get_voice_for_language(lang_code: str) -> str:
    lang = LANGUAGES.get(lang_code)
    if not lang:
        raise ValueError(f"Unsupported language: {lang_code}")
    return lang["edge_tts_voice"]


def get_tier1_languages() -> list:
    return [code for code, info in LANGUAGES.items() if info["cpm_tier"] == "tier1"]


DUB_DIR = Path(__file__).parent.parent / "tmp" / "dubs"
DUB_DIR.mkdir(parents=True, exist_ok=True)


async def _dub_segment(text: str, voice: str, rate: str, pitch: str, output_path: str) -> bool:
    """Generate TTS audio for a single translated segment."""
    from utils.voice_gen import generate_segment_audio
    return await generate_segment_audio(text, output_path, voice=voice, rate=rate, pitch=pitch)


async def generate_dubbed_audio(
    script: str,
    target_lang: str,
    voice: str,
    video_id: str,
    rate: str = "0%",
    pitch: str = "-2Hz",
) -> dict:
    """Generate dubbed audio for a translated script in the target language.

    Returns dict with paths to generated files:
    {
        "audio_path": str,
        "segment_paths": [str, ...],
        "duration": float,
        "success": bool,
    }
    """
    from utils.voice_gen import split_script_into_segments, concatenate_audio

    lang_dir = DUB_DIR / f"{video_id}_{target_lang}"
    lang_dir.mkdir(parents=True, exist_ok=True)

    segments = split_script_into_segments(script)

    tasks = []
    for i, seg_text in enumerate(segments):
        seg_path = str(lang_dir / f"seg_{i+1:04d}.wav")
        tasks.append(_dub_segment(seg_text, voice, rate, pitch, seg_path))

    results = await asyncio.gather(*tasks)
    segment_files = [str(lang_dir / f"seg_{i+1:04d}.wav") for i, ok in enumerate(results) if ok]

    if not segment_files:
        logger.warning("[dub] No segments generated for %s", target_lang)
        return {"audio_path": "", "segment_paths": [], "duration": 0.0, "success": False}

    audio_path = str(lang_dir / f"dub_{target_lang}.wav")
    concat_success = concatenate_audio(segment_files, audio_path)

    duration = 0.0
    if concat_success:
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
        except Exception:
            pass

    return {
        "audio_path": audio_path,
        "segment_paths": segment_files,
        "duration": duration,
        "success": concat_success,
    }


async def dub_all_languages(
    translations: dict,
    video_id: str,
    rate: str = "0%",
    pitch: str = "-2Hz",
) -> dict:
    """Generate dubbed audio for all translated languages.

    Args:
        translations: dict of lang_code -> {translated_script, edge_tts_voice, ...}
        video_id: unique video ID for directory naming

    Returns:
        dict of lang_code -> {audio_path, duration, success, ...}
    """
    tasks = {}
    for lang_code, trans in translations.items():
        voice = trans.get("edge_tts_voice", "en-US-JennyNeural")
        script = trans.get("translated_script", "")
        if not script:
            continue
        tasks[lang_code] = generate_dubbed_audio(script, lang_code, voice, video_id, rate, pitch)

    results = {}
    for lang_code, task in tasks.items():
        try:
            results[lang_code] = await task
        except Exception as e:
            logger.error("[dub] Failed to dub %s: %s", lang_code, e)
            results[lang_code] = {"audio_path": "", "segment_paths": [], "duration": 0.0, "success": False}

    return results


def register_dub_cleanup(video_id: str):
    """Register dub temp directory for cleanup on exit."""
    from utils.subprocess_helper import register_temp_dir
    lang_dirs = DUB_DIR.glob(f"{video_id}_*")
    for d in lang_dirs:
        if d.is_dir():
            register_temp_dir(str(d))
