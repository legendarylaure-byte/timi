from utils.groq_client import generate_completion
from utils.json_utils import extract_json

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

SYSTEM_PROMPT = """You are a professional translator specializing in children's content localization.
Translate the given English script into the target language while:
1. Keeping language simple and age-appropriate (ages 1-9)
2. Preserving the educational value and tone
3. Adapting cultural references to be locally relevant
4. Maintaining the same number of sentences/segments for audio sync
5. Keeping names of characters if they are story-specific

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

    prompt = f"""Translate this children's content to {lang['name']} ({target_lang}):

Original title: {title if title else "N/A"}

Original script:
{script}

Translate all content to {lang['name']} while keeping it age-appropriate and culturally relevant."""

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
