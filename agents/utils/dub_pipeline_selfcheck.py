"""End-to-end selfcheck for the per-language dub pipeline.

Proves the thing that actually broke before: dubbed audio that runs longer than
the video (the Hindi/Korean case) now gets reconciled to the video instead of
being silently truncated by `-shortest`, and audio that cannot be reconciled is
refused rather than published out of sync.

Run:  python3 -m utils.dub_pipeline_selfcheck
"""
import os
import subprocess
import sys
import tempfile

from utils import dub_pipeline as dp

FAILED = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(label)


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def _tone(path, seconds, freq=440):
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=44100",
          "-t", f"{seconds:.3f}", "-ac", "1", path])
    return path


def _parse_rate(rate):
    try:
        return int(str(rate).replace("%", "").strip())
    except ValueError:
        return 0


# U+E000 is unassigned private-use: no font can have a real glyph for it, so it
# always renders as .notdef. Anything matching it is tofu.
_NOTDEF = 0xE000
# One representative codepoint per script we claim to support.
_PROBE = {"hi": 0x0935, "ko": 0xAC00, "es": 0x00E1, "ne": 0x0928}


def _is_tofu(lang_code, codepoint):
    """True when the resolved font renders `codepoint` identically to .notdef."""
    from PIL import ImageFont
    f = ImageFont.truetype(dp.resolve_font_file(lang_code), 48)

    def bmp(cp):
        m = f.getmask(chr(cp))
        return (m.size, bytes(m))

    return bmp(codepoint) == bmp(_NOTDEF)


def fake_tts(tmp, natural_seconds, obeys_rate=True, tag="tts"):
    """Stand-in for edge-tts. Speaking faster yields proportionally shorter audio."""
    counter = {"n": 0}

    def _fn(rate):
        counter["n"] += 1
        pct = _parse_rate(rate) if obeys_rate else 0
        secs = natural_seconds / (1 + pct / 100.0) if obeys_rate else natural_seconds
        path = _tone(os.path.join(tmp, f"{tag}_{counter['n']}_{pct}.wav"), secs, 300 + counter["n"] * 40)
        return {"success": True, "audio_path": path,
                "segments": ["first segment", "second segment"],
                "segment_durations": [secs / 2, secs / 2]}

    return _fn


def check_logic():
    print("\n[1] drift decisions")
    d, s = dp.assess_drift(10.3, 10.0)
    check("3% drift -> atempo (inaudible)", d == "atempo", f"{s['drift_pct']}%")
    d, s = dp.assess_drift(11.5, 10.0)
    check("15% drift -> retry_tts (regenerate narration)", d == "retry_tts", f"{s['drift_pct']}%")
    d, s = dp.assess_drift(14.0, 10.0)
    check("40% drift -> reject (never publish)", d == "reject", f"{s['drift_pct']}%")
    d, s = dp.assess_drift(0, 10.0)
    check("unmeasurable -> reject", d == "reject", s.get("reason", ""))

    print("\n[2] atempo + rate helpers")
    # The ladder's two boundaries. ATEMPO_CEILING used to duplicate
    # REJECT_TOLERANCE under a second name and nothing read it; assert the
    # invariant instead so the "past this atempo sounds robotic" intent is
    # expressed exactly once.
    check("tolerance ladder ordered", dp.ATEMPO_TOLERANCE < dp.REJECT_TOLERANCE,
          f"{dp.ATEMPO_TOLERANCE} < {dp.REJECT_TOLERANCE}")
    check("atempo 1.0 single instance", dp.atempo_filter(1.0) == "atempo=1.000000")
    check("atempo slow-down chains", dp.atempo_filter(0.4).count("atempo") == 2)
    check("atempo speed-up chains", dp.atempo_filter(3.0).count("atempo") == 2)
    check("srt timestamp", dp._srt_timestamp(3661234) == "01:01:01,234")
    check("rate suggest +12%", dp.suggested_tts_rate(1.12) == "+12%")
    check("rate suggest -8%", dp.suggested_tts_rate(0.92) == "-8%")
    # edge-tts rejects any rate without a leading sign ("0%" and "" both raise
    # "Invalid rate"), so every rate this module hands to TTS must be signed.
    for r in (dp.suggested_tts_rate(1.12), dp.suggested_tts_rate(0.92), dp.suggested_tts_rate(1.0)):
        check(f"rate {r!r} is signed (edge-tts safe)", r and r[0] in "+-")

    print("\n[3] subtitle splitting")
    es = dp._split_cue("word " * 20, "es")
    check("latin splits on words", all(len(c.split()) <= 8 for c in es), f"{len(es)} cues")
    hi = "नमस्ते दुनिया यह एक परीक्षण वाक्य है जिसे हम विभाजित करना चाहते हैं"
    hi_cues = dp._split_cue(hi, "hi")
    check("hindi splits by chars", all(len(c) <= 34 for c in hi_cues), f"{len(hi_cues)} cues")
    check("hindi loses no text", "".join(hi_cues).replace(" ", "") == hi.replace(" ", ""))
    ko = "안녕하세요 여러분 이것은 자막을 테스트하기 위한 문장입니다 아주 긴 문장"
    ko_cues = dp._split_cue(ko, "ko")
    check("korean splits by chars", all(len(c) <= 34 for c in ko_cues), f"{len(ko_cues)} cues")

    ph = dp.build_dub_timings(["one two three", "four five"], [2.0, 2.0], "es")
    check("timings contiguous, sum to audio",
          len(ph) == 2 and ph[0]["start_ms"] == 0 and abs(ph[-1]["end_ms"] - 4000) <= 2,
          f"end={ph[-1]['end_ms']}ms")

    srt_path = dp.write_srt(ph, os.path.join(tempfile.gettempdir(), "_dub_srt_check.srt"))
    with open(srt_path, encoding="utf-8") as f:
        body = f.read()
    check("srt renders numbered cues", body.count("-->") == 2 and body.startswith("1\n"))
    os.remove(srt_path)


def check_ladder(tmp):
    print("\n[4] THE BUG: 15% slow dub (Hindi/Korean case) vs 10s video")
    r = dp.dub_language("hi", 10.0, fake_tts(tmp, 11.5, obeys_rate=True, tag="hi"),
                        os.path.join(tmp, "w_hi"))
    check("slow dub succeeds via TTS-rate regeneration", r["success"], r.get("reason", ""))
    if r["success"]:
        got = dp.duration_of(r["audio_path"])
        check("  narration ends with the video", abs(got - 10.0) < 0.35, f"{got:.2f}s vs 10.00s")
        check("  regeneration actually used",
              any(a["outcome"] == "retry_tts" for a in r["attempts"]),
              f"{[a.get('drift_pct') for a in r['attempts']]}")
    return r


def check_small_drift(tmp):
    print("\n[5] small drift -> no regeneration, straight atempo")
    r = dp.dub_language("es", 10.0, fake_tts(tmp, 10.2, obeys_rate=True, tag="es"),
                        os.path.join(tmp, "w_es"))
    check("small drift succeeds", r["success"], r.get("reason", ""))
    check("  no TTS regeneration needed", len(r["attempts"]) == 1, f"{len(r['attempts'])} attempt(s)")
    if r["success"]:
        check("  audio matches video", abs(dp.duration_of(r["audio_path"]) - 10.0) < 0.2,
              f"{dp.duration_of(r['audio_path']):.2f}s")


def fake_tts_partial(tmp, natural_seconds, target, residual_ratio, tag="tts"):
    """edge-tts stand-in whose rate compensation only partly bites.

    Real voices do not scale duration perfectly with the requested rate, so a
    retry can leave drift still inside the ceiling. `residual_ratio` is the
    fraction of the first attempt's excess that the regeneration removes:
    0.0 removes none, 1.0 removes all.
    """
    counter = {"n": 0}

    def _fn(rate):
        counter["n"] += 1
        excess = natural_seconds - target
        secs = natural_seconds if counter["n"] == 1 else target + excess * residual_ratio
        path = _tone(os.path.join(tmp, f"{tag}_{counter['n']}.wav"), secs, 320)
        return {"success": True, "audio_path": path,
                "segments": ["first segment", "second segment"],
                "segment_durations": [secs / 2, secs / 2]}

    return _fn


def check_residual_correction(tmp):
    print("\n[7] retry that only partly bites -> residual atempo, not a failure")
    # 11.5s narration for a 10s video; the regeneration removes half the excess
    # and lands at ~10.75s, which is still retry_tts territory (5-25%).
    r = dp.dub_language("hi", 10.0, fake_tts_partial(tmp, 11.5, 10.0, 0.5, tag="res"),
                        os.path.join(tmp, "w_res"))
    check("partly-corrected dub still succeeds", r["success"], r.get("reason", ""))
    if not r["success"]:
        return r
    check("  used exactly one regeneration", len(r["attempts"]) == 2,
          f"{[a.get('drift_pct') for a in r['attempts']]}")
    check("  the retry landed back in retry_tts range",
          r["attempts"][-1]["outcome"] == "retry_tts",
          f"{r['attempts'][-1].get('drift_pct')}%")
    got = dp.duration_of(r["audio_path"])
    check("  residual atempo landed on target", abs(got - 10.0) < 0.35, f"{got:.2f}s vs 10.00s")
    check("  stats record the residual atempo",
          "atempo" in str(r["stats"].get("action", "")), r["stats"].get("action", ""))
    check("  segment cues were rescaled", abs(float(r["stats"].get("scale", 1.0)) - 1.0) > 0.001,
          f"scale={r['stats'].get('scale')}")

    print("\n[7b] a regeneration that fixes nothing is finished by atempo, not published raw")
    r2 = dp.dub_language("es", 10.0, fake_tts_partial(tmp, 11.5, 10.0, 0.0, tag="res2"),
                         os.path.join(tmp, "w_res2"))
    check("no-benefit regeneration still ends in sync", r2["success"], r2.get("reason", ""))
    if r2["success"]:
        got2 = dp.duration_of(r2["audio_path"])
        check("  and lands on target", abs(got2 - 10.0) < 0.35, f"{got2:.2f}s vs 10.00s")
    return r


def check_reject(tmp):
    print("\n[6] hopeless dub is refused, not published")
    r = dp.dub_language("ko", 10.0, fake_tts(tmp, 26.0, obeys_rate=True, tag="ko"),
                        os.path.join(tmp, "w_ko"))
    check("26s narration vs 10s video rejected", not r["success"], r.get("reason", "")[:60])
    check("  gave up after the retry budget", len(r["attempts"]) <= 2, f"{len(r['attempts'])} attempt(s)")

    r2 = dp.dub_language("es", 10.0, lambda rate: {"success": False}, os.path.join(tmp, "w_bad"))
    check("TTS failure is contained", not r2["success"], r2.get("reason", ""))


def check_mux(tmp, ladder):
    print("\n[7] intro card (desync) + final mux")
    video = os.path.join(tmp, "main.mp4")
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24",
          "-t", "10", "-c:v", "libx264", "-pix_fmt", "yuv420p", video])
    vdur = dp.duration_of(video)
    check("main video is 10s", abs(vdur - 10) < 0.4, f"{vdur:.2f}s")

    for label, font_lang in (("हिन्दी", "hi"), ("한국어", "ko"), ("Español", "es")):
        card = dp.make_intro_card(label, os.path.join(tmp, f"card_{font_lang}.png"),
                                  640, 360, lang_code=font_lang)
        size = os.path.getsize(card) if os.path.exists(card) else 0
        check(f"card renders: {label}", size > 500, f"{size}B")
        # Size proves nothing: a card full of .notdef boxes is just as large.
        # Compare the glyph against a private-use codepoint that no font has,
        # so a tofu box and a real glyph cannot both pass.
        check(f"  card font actually covers {label}",
              not _is_tofu(font_lang, _PROBE.get(font_lang)),
              f"font={dp.resolve_font_file(font_lang).split('/')[-1]}")

    if not ladder.get("success"):
        check("mux needs a successful dub", False, "skipped")
        return

    card_s = dp.intro_seconds("hi")
    check("per-language card length differs (desync)",
          len({dp.intro_seconds(c) for c in ("es", "hi", "ko")}) == 3,
          ", ".join(f"{c}={dp.intro_seconds(c)}s" for c in ("es", "hi", "ko")))

    out = os.path.join(tmp, "hi_dub.mp4")
    ok, stats = dp.build_dub_video(video, ladder["audio_path"], out,
                                   os.path.join(tmp, "card_hi.png"), card_s)
    check("dub video builds with card", ok, stats.get("reason", ""))
    if ok:
        got = dp.duration_of(out)
        check("final = video + card", abs(got - (vdur + card_s)) < 0.6,
              f"{got:.2f}s vs {vdur + card_s:.2f}s")
        check("not frozen/truncated", got > vdur, f"{got:.2f}s")

    out2 = os.path.join(tmp, "plain_dub.mp4")
    ok2, _ = dp.build_dub_video(video, ladder["audio_path"], out2)
    check("dub video builds without card", ok2)
    if ok2:
        check("no-card duration = video", abs(dp.duration_of(out2) - vdur) < 0.4,
              f"{dp.duration_of(out2):.2f}s")


def main():
    print("=" * 64)
    print("DUB PIPELINE SELFCHECK")
    print("=" * 64)
    check_logic()
    with tempfile.TemporaryDirectory() as tmp:
        ladder = check_ladder(tmp)
        check_small_drift(tmp)
        check_reject(tmp)
        check_residual_correction(tmp)
        check_mux(tmp, ladder)
    print("\n" + "=" * 64)
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {FAILED}")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
