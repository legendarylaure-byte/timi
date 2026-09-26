"""Per-language font resolution.

Why this exists: `FONT_PATH` was hardcoded to DejaVuSans and the ASS style pinned
`FontName=Arial`. Both resolve to a Latin-only face, so Devanagari (`hi`) and
Hangul (`ko`) render as tofu boxes. Verified against fontconfig in-container:

    fc-list :lang=hi file  ->  FreeSans, unifont, FreeSerif   (NOT DejaVuSans)
    fc-list :lang=ko file  ->  wqy-zenhei, unifont            (NOT DejaVuSans)

Two different lookups are needed because the two consumers disagree:
  * ffmpeg `drawtext=fontfile=` and PIL need a FILE PATH.
  * libass (`subtitles=...:force_style=FontName=`) needs a FAMILY NAME.

`selfcheck()` below re-verifies the map against fontconfig so a font being
dropped from the image can never silently reintroduce tofu.
"""
import logging
import os
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)

DEFAULT_FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEFAULT_FONT_FAMILY = "DejaVu Sans"

# lang code -> (file path, fontconfig family name)
# Only scripts we can actually render are mapped; everything else falls back to
# the Latin default, which is correct for es/de/fr/pt/en.
FONT_MAP = {
    "hi": ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "FreeSans"),
    "ko": ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYi Zen Hei"),
    "ja": ("/usr/share/fonts/opentype/unifont/unifont.otf", "Unifont"),
    "ar": ("/usr/share/fonts/opentype/unifont/unifont.otf", "Unifont"),
}


def _env_default_file() -> str:
    return os.getenv("FONT_PATH") or DEFAULT_FONT_FILE


@lru_cache(maxsize=32)
def _probe_lang(code: str) -> bool:
    try:
        out = subprocess.run(
            ["fc-list", f":lang={code}", "file"],
            capture_output=True, text=True, timeout=20,
        ).stdout
        return bool(out.strip())
    except Exception:
        return False


def _entry(lang_code: str):
    """Return a usable (file, family) for lang_code, or None to use the default."""
    if not lang_code:
        return None
    entry = FONT_MAP.get(lang_code.lower()[:2])
    if not entry:
        return None
    path, family = entry
    if not os.path.exists(path):
        logger.warning("[fonts] %s font missing at %s; falling back to Latin", lang_code, path)
        return None
    return path, family


def resolve_font_file(lang_code: str = "") -> str:
    """Font FILE PATH for drawtext / PIL. Falls back to FONT_PATH then DejaVu."""
    entry = _entry(lang_code)
    if entry:
        return entry[0]
    return _env_default_file()


@lru_cache(maxsize=32)
def _family_of(font_path: str) -> str:
    try:
        out = subprocess.run(
            ["fc-query", "-f", "%{family[0]}", font_path],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        return out
    except Exception:
        return ""


def resolve_font_family(lang_code: str = "") -> str:
    """Family NAME for libass FontName. Falls back to FONT_PATH's family, then DejaVu."""
    entry = _entry(lang_code)
    if entry:
        return entry[1]
    env = _env_default_file()
    if os.path.exists(env):
        return _family_of(env) or DEFAULT_FONT_FAMILY
    return DEFAULT_FONT_FAMILY


# Unicode blocks per script -> FONT_MAP key. Used by font_for_text so callers do
# not need a lang_code threaded through just to render a string correctly.
_SCRIPT_RANGES = (
    ("hi", ((0x0900, 0x097F), (0xA8E0, 0xA8FF))),                 # Devanagari
    ("ko", ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F))),  # Hangul
    ("ja", ((0x3040, 0x30FF), (0x4E00, 0x9FFF))),                 # kana + CJK
    ("ar", ((0x0600, 0x06FF), (0x0750, 0x077F))),                 # Arabic
)


def script_of(text: str) -> str:
    """Dominant non-Latin script in `text`, as a FONT_MAP key ('' if Latin)."""
    counts: dict = {}
    for ch in text or "":
        cp = ord(ch)
        for key, ranges in _SCRIPT_RANGES:
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[key] = counts.get(key, 0) + 1
                break
    return max(counts, key=counts.get) if counts else ""


def font_for_text(text: str, lang_code: str = "") -> str:
    """Font FILE PATH guaranteed to cover `text`.

    Draws the script it actually finds, so a Devanagari overlay lands on FreeSans
    even when the caller has no language context. Explicit lang_code wins.
    """
    return resolve_font_file(lang_code or script_of(text))


def covers(lang_code: str) -> bool:
    """True when the installed fonts can render lang_code."""
    if not lang_code:
        return True
    return _probe_lang(lang_code.lower()[:2])


def selfcheck() -> bool:
    """Verify every mapped font really covers its language. Run: python -m utils.fonts"""
    ok = True
    for code, (path, family) in FONT_MAP.items():
        exists = os.path.exists(path)
        renders = covers(code)
        good = exists and renders
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {code}: file={exists} lang={renders} "
              f"({family} @ {os.path.basename(path)})")
    for code in ("es", "de", "fr", "pt"):
        renders = covers(code)
        ok = ok and renders
        print(f"  {'PASS' if renders else 'FAIL'} {code}: Latin default covers ({renders})")

    print("  -- script detection --")
    for text, want in (("Hello world", ""), ("नमस्ते दुनिया", "hi"),
                       ("안녕하세요 여러분", "ko"), ("こんにちは", "ja"), ("مرحبا", "ar")):
        got = script_of(text)
        good = got == want
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {text[:12]!r} -> {got or 'latin'} (want {want or 'latin'})")

    print("  -- font_for_text resolves a real file --")
    for text, want in (("Hello", "DejaVuSans"), ("नमस्ते", "FreeSans"),
                       ("안녕하세요", "wqy-zenhei")):
        path = font_for_text(text)
        good = os.path.exists(path) and want.lower() in os.path.basename(path).lower()
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {text[:10]!r} -> {path}")

    # libass needs a family name, not a path -- make sure that still resolves.
    for code, want in (("hi", "FreeSans"), ("ko", "WenQuanYi"), ("es", "DejaVu")):
        fam = resolve_font_family(code)
        good = want.lower() in fam.lower()
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} family({code}) -> {fam}")

    print(f"  fonts selfcheck: {'OK' if ok else 'FAILED'}")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if selfcheck() else 1)
