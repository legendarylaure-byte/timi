"""Per-language dub pipeline: duration reconcile, subtitles, desync cards.

The old path (a since-deleted `translate.mux_dubbed_video`) used
`-c:v copy -shortest`, which meant:
  * dubbed audio longer than the video -> the last sentence was silently eaten
  * dubbed audio shorter            -> the video froze on the final frame

Hindi and Korean TTS run measurably slower than English, so this was not
hypothetical. Here the audio is reconciled to the video *before* muxing, and a
language is rejected outright rather than published out of sync.

Reconcile ladder (first step that lands inside tolerance wins):
  1. exact                         -> no correction
  2. |drift| <= ATEMPO_TOLERANCE   -> `atempo` (inaudible at this range)
  3. regenerate TTS with a rate    -> natural speech, better than heavy atempo
  4. |drift| <= REJECT_TOLERANCE   -> final small atempo
  5. otherwise                     -> reject the language, log why
"""
import json
import logging
import os
import shutil

from utils.fonts import resolve_font_file
from utils.subprocess_helper import safe_run

logger = logging.getLogger(__name__)

ATEMPO_TOLERANCE = 0.05   # atempo is inaudible below this
# Past this the dub is too far off to ever publish (and atempo sounds robotic).
# One constant: it used to be duplicated as ATEMPO_CEILING, which nothing read.
REJECT_TOLERANCE = 0.25
MAX_TTS_RETRIES = 1

# Desync: a language-specific intro card of differing length. Different opening
# frames + different total duration is what breaks perceptual-hash duplicate
# detection, and the variable length is what the duration target absorbs.
INTRO_CARD_SECONDS = {"es": 2.0, "hi": 2.5, "ko": 3.0}
INTRO_CARD_FALLBACK = 2.0

# Scripts without word spaces (ko) and with combining marks (hi) need different
# subtitle splitting than space-delimited Latin.
CHAR_SPLIT_LANGS = {"hi", "ko", "ja", "ar", "zh"}
MAX_CUE_WORDS = 8
MAX_CUE_CHARS = 34

BG = (30, 30, 30)
TEAL = (0, 204, 204)
ORANGE = (255, 107, 53)
WHITE = (245, 245, 245)


def _probe(path: str) -> dict:
    """Return {duration, width, height} for a media file (0/0 when unknown)."""
    out = {"duration": 0.0, "width": 0, "height": 0}
    try:
        r = safe_run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "json", path,
        ], timeout=60)
        data = json.loads(r.stdout or "{}")
        out["duration"] = float((data.get("format") or {}).get("duration") or 0.0)
        streams = data.get("streams") or [{}]
        out["width"] = int(streams[0].get("width") or 0)
        out["height"] = int(streams[0].get("height") or 0)
    except Exception as e:
        logger.warning("[dub] probe failed for %s: %s", path, e)
    return out


def duration_of(path: str) -> float:
    return _probe(path).get("duration", 0.0)


def intro_seconds(lang_code: str) -> float:
    return INTRO_CARD_SECONDS.get(lang_code, INTRO_CARD_FALLBACK)


# --------------------------------------------------------------------------
# SRT
# --------------------------------------------------------------------------

def _split_cue(text: str, lang_code: str) -> list:
    """Split one spoken segment into readable cues."""
    text = (text or "").strip()
    if not text:
        return []
    if lang_code in CHAR_SPLIT_LANGS:
        return _split_by_chars(text, MAX_CUE_CHARS)
    words = text.split()
    if len(words) <= MAX_CUE_WORDS:
        return [text]
    return [" ".join(words[i:i + MAX_CUE_WORDS])
            for i in range(0, len(words), MAX_CUE_WORDS)]


def _split_by_chars(text: str, max_chars: int) -> list:
    """Char-based split that prefers whitespace, else hard-wraps.

    Devanagari/Korean have no reliable word delimiter, but they do have spaces
    between phrases, so we cut on the last space that fits before wrapping.
    """
    if len(text) <= max_chars:
        return [text]
    chunks, buf = [], ""
    for token in text.split():
        if len(buf) + len(token) + 1 <= max_chars:
            buf = f"{buf} {token}".strip()
            continue
        if buf:
            chunks.append(buf)
        while len(token) > max_chars:
            chunks.append(token[:max_chars])
            token = token[max_chars:]
        buf = token
    if buf:
        chunks.append(buf)
    return chunks


def _srt_timestamp(ms: int) -> str:
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_dub_timings(segments: list, segment_durations: list, lang_code: str,
                      scale: float = 1.0, offset_s: float = 0.0) -> list:
    """Build [{text,start_ms,end_ms}] from spoken segments and their real durations.

    Durations are measured from the dubbed audio, so subtitles match the voice.
    Within a segment, cue lengths are distributed proportionally to size so long
    lines get proportionally more time.

    `scale` re-times everything when atempo has sped the narration up or down, and
    `offset_s` shifts every cue past the desync intro card. Without these the
    captions would run `offset_s` seconds early and drift against the voice.
    """
    phrases, cursor = [], 0.0
    for seg, dur in zip(segments, segment_durations):
        dur = float(dur or 0.0) * scale
        if dur <= 0:
            continue
        cues = _split_cue(seg, lang_code)
        if not cues:
            continue
        weights = [max(1, len(c)) for c in cues]
        total_w = float(sum(weights))
        for cue, w in zip(cues, weights):
            span = dur * (w / total_w)
            phrases.append({
                "text": cue,
                "start_ms": int((offset_s + cursor) * 1000),
                "end_ms": int((offset_s + cursor + span) * 1000),
            })
            cursor += span
    return phrases


def write_srt(phrases: list, output_path: str) -> str:
    lines = []
    for i, p in enumerate(phrases, 1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(p['start_ms'])} --> {_srt_timestamp(p['end_ms'])}")
        lines.append(p["text"])
        lines.append("")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


# --------------------------------------------------------------------------
# Intro card (desync)
# --------------------------------------------------------------------------

def make_intro_card(lang_label: str, out_png: str, width: int = 1080,
                    height: int = 1920, lang_code: str = "") -> str:
    """Render a language intro card. Doubles as the per-language desync frame.

    Pass `lang_code` ("hi", "ko", ...) so the font comes from the real language
    entry. Without it the code is guessed from the first two characters of the
    label, which is wrong for every non-Latin name: "हिन्दी" yields "हि" and
    "한국어" yields "한국", neither of which is a language code, so both cards
    fell back to Latin-only DejaVu and rendered as tofu boxes.
    """
    from PIL import Image, ImageDraw, ImageFont

    width, height = max(2, width), max(2, height)
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    font_path = resolve_font_file(lang_code or _script_of(lang_label))
    try:
        title_font = ImageFont.truetype(font_path, int(height * 0.075))
        sub_font = ImageFont.truetype(font_path, int(height * 0.028))
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    bar_h = max(4, height // 180)
    draw.rectangle([0, height // 2 - bar_h, width, height // 2 + bar_h], fill=TEAL)

    def _centered(text, font, y, fill):
        try:
            l, t, r, b = draw.textbbox((0, 0), text, font=font)
        except Exception:
            l, t, r, b = (0, 0, draw.textlength(text, font=font), height * 0.05)
        draw.text(((width - (r - l)) / 2 - l, y), text, font=font, fill=fill)

    _centered(lang_label, title_font, height * 0.40, WHITE)
    _centered("Vyom Ai Cloud", sub_font, height * 0.56, TEAL)

    for cx, cy, col in ((0.08, 0.10, ORANGE), (0.92, 0.10, TEAL),
                        (0.08, 0.90, TEAL), (0.92, 0.90, ORANGE)):
        r = max(6, int(min(width, height) * 0.018))
        draw.ellipse([cx * width - r, cy * height - r, cx * width + r, cy * height + r], fill=col)

    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    img.save(out_png)
    return out_png


def _script_of(lang_code: str) -> str:
    return (lang_code or "")[:2].lower()


# --------------------------------------------------------------------------
# Duration reconcile
# --------------------------------------------------------------------------

def atempo_filter(ratio: float) -> str:
    """atempo chain for a target ratio (single instance is limited to 0.5-2.0)."""
    if ratio <= 0:
        return ""
    factors, remaining = [], ratio
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={f:.6f}" for f in factors)


def assess_drift(measured: float, target_duration: float) -> tuple:
    """Classify the mismatch. Returns (decision, stats).

    Decisions:
      atempo     -> correct in place, no TTS regeneration needed
      retry_tts  -> regenerate the narration at a compensating rate first
      reject     -> too far off, never publish this language
    """
    stats = {"measured": round(measured, 3), "target": round(target_duration, 3)}
    if measured <= 0 or target_duration <= 0:
        stats["reason"] = "unmeasurable audio or target"
        return "reject", stats
    ratio = measured / target_duration
    drift = abs(ratio - 1.0)
    stats["ratio"] = round(ratio, 4)
    stats["drift_pct"] = round(drift * 100, 2)
    if drift <= ATEMPO_TOLERANCE:
        return "atempo", stats
    if drift <= REJECT_TOLERANCE:
        return "retry_tts", stats
    stats["reason"] = (
        f"drift {stats['drift_pct']}% exceeds {REJECT_TOLERANCE * 100:.0f}% ceiling; "
        "refusing to publish out-of-sync audio"
    )
    return "reject", stats


def correct_audio_tempo(audio_path: str, target_duration: float,
                        out_path: str, allow_retry_decision: bool = True) -> tuple:
    """Force audio to match target_duration. Returns (ok, out_path, stats).

    Only called after `assess_drift` returned `atempo`; a `reject` verdict is
    honoured here so the module can never emit out-of-sync audio.
    """
    measured = duration_of(audio_path)
    decision, stats = assess_drift(measured, target_duration)
    if decision == "reject":
        return False, "", stats
    if decision == "retry_tts" and not allow_retry_decision:
        stats["reason"] = "drift needs TTS regeneration, retries exhausted"
        return False, "", stats
    stats["action"] = f"atempo ({decision})"

    ratio = stats["ratio"]
    filt = atempo_filter(ratio)
    ok = safe_run([
        "ffmpeg", "-y", "-i", audio_path, "-filter:a", filt, "-c:a", "pcm_s16le", out_path,
    ], timeout=900).returncode == 0
    if not ok:
        stats["reason"] = "atempo ffmpeg failed"
        return False, "", stats
    stats["corrected"] = round(duration_of(out_path), 3)
    # atempo=ratio compresses/expands by `ratio`, so cue timings must scale by it.
    stats["scale"] = round(ratio, 6)
    stats["final_drift_pct"] = round(
        abs(stats["corrected"] - target_duration) / target_duration * 100, 2)
    return True, out_path, stats


def dub_language(lang_code: str, target_duration: float, tts_fn, workdir: str,
                 base_rate: str = "+0%", label: str = "") -> dict:
    """Full TTS + duration-reconcile ladder for one language.

    `tts_fn(rate) -> {"audio_path","segments","segment_durations","success"}`

    Order: generate at base rate, measure, and only regenerate (once) when the
    drift is real but recoverable. TTS rate compensation yields natural speech;
    atempo is the last-mile corrector. Anything that cannot be reconciled inside
    REJECT_TOLERANCE is refused rather than published mis-synced.
    """
    os.makedirs(workdir, exist_ok=True)
    label = label or lang_code
    attempts = []
    rate = base_rate

    for attempt in range(MAX_TTS_RETRIES + 1):
        result = tts_fn(rate)
        if not result or not result.get("success"):
            attempts.append({"rate": rate, "outcome": "tts_failed"})
            if attempt >= MAX_TTS_RETRIES:
                return {"success": False, "reason": "tts_failed", "attempts": attempts}
            continue

        audio = result["audio_path"]
        measured = duration_of(audio)
        decision, stats = assess_drift(measured, target_duration)
        attempts.append({"rate": rate, "outcome": decision,
                         "drift_pct": stats.get("drift_pct")})

        if decision == "reject":
            return {"success": False, "reason": stats.get("reason", "out_of_sync"),
                    "attempts": attempts, "stats": stats}

        # The last attempt has no regeneration left, so anything still inside the
        # ceiling is finished with atempo rather than thrown away. Before this,
        # a retry that landed at 10% was reported as a failure.
        last_attempt = attempt >= MAX_TTS_RETRIES
        if decision == "atempo" or last_attempt:
            fixed = os.path.join(workdir, f"{label}_fixed.wav")
            ok, fixed_path, cstats = correct_audio_tempo(
                audio, target_duration, fixed,
                allow_retry_decision=decision == "retry_tts")
            if not ok:
                if last_attempt and decision == "retry_tts":
                    return {"success": False,
                            "reason": f"still {stats.get('drift_pct')}% off after "
                                      f"{MAX_TTS_RETRIES} regeneration(s)",
                            "attempts": attempts, "stats": stats}
                return {"success": False, "reason": cstats.get("reason", "atempo_failed"),
                        "attempts": attempts}
            return {"success": True, "audio_path": fixed_path, "stats": cstats,
                    "attempts": attempts,
                    "segments": result.get("segments", []),
                    "segment_durations": result.get("segment_durations", [])}

        # retry_tts: compensate with the TTS rate and try once more
        rate = suggested_tts_rate(stats["ratio"], rate)

    # ponytail: unreachable. The last attempt returns on every verdict
    # (reject -> fail, atempo/retry_tts -> corrected or failed), so there is no
    # path that falls out of this loop.
    raise AssertionError("dub_language must return from inside the retry loop")


def suggested_tts_rate(drift_ratio: float, base_rate: str = "+0%") -> str:
    """Rate string that would pre-compensate a measured drift.

    drift > 1 means the dub ran long, so ask TTS to speak faster (+N%).
    """
    try:
        base = float(str(base_rate).replace("%", "").strip() or 0)
    except ValueError:
        base = 0.0
    pct = int(round((drift_ratio - 1.0) * 100))
    total = max(-40, min(40, int(base) + pct))
    return f"{total:+d}%"


# --------------------------------------------------------------------------
# Mux (card + main video + reconciled dub audio)
# --------------------------------------------------------------------------

def build_dub_video(main_video: str, dub_audio: str, out_path: str,
                    card_png: str = "", card_seconds: float = 0.0) -> tuple:
    """Compose the language version: optional intro card + main video + dub audio.

    The card is silent and the narration starts after it, so the dubbed audio is
    reconciled against the *main* video duration and then delayed by the card.
    """
    main_dur = duration_of(main_video)
    if main_dur <= 0:
        return False, {"reason": "main video unmeasurable"}
    if duration_of(dub_audio) <= 0:
        return False, {"reason": "dub audio unmeasurable"}

    info = _probe(main_video)
    w, h = info["width"] or 1080, info["height"] or 1920
    card_seconds = float(card_seconds or 0.0)

    cmd = ["ffmpeg", "-y"]
    if card_png and card_seconds > 0:
        cmd += ["-loop", "1", "-t", f"{card_seconds}", "-i", card_png]
    cmd += ["-i", main_video, "-i", dub_audio]

    card_idx, main_idx, audio_idx = (0, 1, 2) if card_png and card_seconds > 0 else (-1, 0, 1)

    if card_idx >= 0:
        fc = (f"[{card_idx}:v]scale={w}:{h},setsar=1,fps=24,format=yuv420p[cv];"
              f"[{main_idx}:v]setsar=1,fps=24,format=yuv420p[mv];"
              f"[cv][mv]concat=n=2:v=1:a=0[v];"
              f"[{audio_idx}:a]aresample=44100,adelay={int(card_seconds * 1000)}|{int(card_seconds * 1000)}[a]")
    else:
        fc = f"[{main_idx}:v]setsar=1,fps=24,format=yuv420p[v];[{audio_idx}:a]aresample=44100[a]"

    cmd += [
        "-filter_complex", fc,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", out_path,
    ]
    res = safe_run(cmd, timeout=3600)
    if res.returncode != 0 or not os.path.exists(out_path):
        return False, {"reason": f"mux ffmpeg rc={res.returncode}"}
    final = duration_of(out_path)
    return True, {"duration": round(final, 3), "main_duration": round(main_dur, 3),
                  "card_seconds": card_seconds, "width": w, "height": h}


def publishable_dub(source_video: str) -> str:
    """Reusable artifact path for a dub's video."""
    base, _ = os.path.splitext(source_video)
    return f"{base}_dub.mp4"


def cleanup_dub_artifacts(*paths: str) -> None:
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


def copy_artifact(src: str, dst: str) -> str:
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    shutil.copy2(src, dst)
    return dst
