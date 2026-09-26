"""End-to-end check for the dub publish orchestration in main._publish_dubbed_languages.

SAFETY: this stubs `multi_platform_publish`, so it can never upload anything to
the real channel. It proves the orchestration contract:

  * a fallback translation is refused (never dubbed, never published)
  * real Hindi narration that cannot be reconciled to the visuals is refused
  * narration that CAN be reconciled produces a real video + correctly offset SRT
  * the publisher receives the real language, not a hardcoded "en"

Run:  python3 -m utils.dub_orchestration_selfcheck
"""
import os
import subprocess
import sys
import tempfile

FAILED = []
CAPTURED = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(label)


def _install_stubs():
    """Replace the publisher with a recorder so nothing can be uploaded."""
    import utils.multi_platform_publisher as mpp

    def fake_publish(*args, **kwargs):
        CAPTURED.append(kwargs)
        return {"success_count": 1, "platforms": {"youtube": {"success": True,
                                                             "video_url": "https://stub"}}}
    mpp.multi_platform_publish = fake_publish


def _video(path, seconds=10):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=640x360:rate=24", "-f", "lavfi", "-i",
                    f"sine=frequency=300:sample_rate=44100", "-t", str(seconds),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", path],
                   capture_output=True)
    return path


def main():
    print("=" * 68)
    print("DUB ORCHESTRATION SELFCHECK (publisher stubbed - nothing is uploaded)")
    print("=" * 68)
    import main
    from utils.dub_pipeline import duration_of
    _install_stubs()

    HINDI = ("नमस्ते दोस्तों। आज हम आर्टिफिशियल इंटेलिजेंस के बारे में बात करेंगे। "
             "यह विषय बहुत रोचक है।")

    with tempfile.TemporaryDirectory() as tmp:
        vid = _video(os.path.join(tmp, "clean.mp4"), 10)
        vdur = duration_of(vid)
        check("synthetic clean master built", abs(vdur - 10) < 0.5, f"{vdur:.2f}s")

        print("\n[1] fallback translation is refused (no English-through-hindi-voice)")
        r = main._publish_dubbed_languages(
            video_id="t1", clean_video_path=vid, script_text="hello", topic="T",
            translations={"hi": {"translated_script": "[Hindi] hello world",
                                 "is_fallback": True, "language_name": "हिन्दी",
                                 "edge_tts_voice": "hi-IN-SwaraNeural"}},
            thumbnail_path="", fmt="shorts")
        check("nothing published", r["published"] == [], str(r["published"]))
        check("recorded as skipped", "hi" in r["skipped"], str(r["skipped"]))
        check("publisher never called", CAPTURED == [], f"{len(CAPTURED)} call(s)")

        print("\n[2] missing clean master skips everything")
        r = main._publish_dubbed_languages(
            video_id="t2", clean_video_path=os.path.join(tmp, "nope.mp4"),
            script_text="x", topic="T", translations={"hi": {"translated_script": HINDI}},
            thumbnail_path="", fmt="shorts")
        check("no publish, reported setup failure",
              r["published"] == [] and "_setup" in r["failed"], str(r["failed"]))

        print("\n[3] real Hindi narration that genuinely cannot be reconciled")
        from utils.translate import generate_dubbed_audio
        SHORT = "नमस्ते।"
        probe_short = main._run_async(generate_dubbed_audio(
            SHORT, "hi", "hi-IN-SwaraNeural", "probe2", "+0%", "-2Hz"), timeout=900)
        spoken_short = probe_short["duration"]
        # A TTS/provider failure yields no probe audio; report it instead of
        # dividing by zero and crashing the whole selfcheck.
        check("probe narration produced audio", spoken_short > 0, f"{spoken_short:.2f}s")
        if spoken_short <= 0:
            return 1
        # Video deliberately 3x the narration so the drift is unrecoverable.
        long_vid = _video(os.path.join(tmp, "long.mp4"), round(spoken_short * 3, 2))
        print(f"       narration {spoken_short:.2f}s vs video "
              f"{duration_of(long_vid):.2f}s -> ~{abs(duration_of(long_vid)/spoken_short-1)*100:.0f}% drift")
        r = main._publish_dubbed_languages(
            video_id="t3", clean_video_path=long_vid, script_text="x", topic="T",
            translations={"hi": {"translated_script": SHORT, "is_fallback": False,
                                 "language_name": "हिन्दी",
                                 "edge_tts_voice": "hi-IN-SwaraNeural"}},
            thumbnail_path="", fmt="shorts")
        check("refused rather than published", r["published"] == [], str(r["published"]))
        check("publisher never called", CAPTURED == [], f"{len(CAPTURED)} call(s)")
        if "hi" in r["failed"]:
            print(f"       reason: {r['failed']['hi']}")

        print("\n[4] real Hindi narration matched to the video -> publishes")
        # Measure the real TTS length, then give the pipeline that exact target so
        # the reconcile ladder has something achievable to prove end to end.
        HINDI_LONG = HINDI
        probe = main._run_async(generate_dubbed_audio(
            HINDI_LONG, "hi", "hi-IN-SwaraNeural", "probe", "+0%", "-2Hz"), timeout=900)
        if not probe.get("success"):
            check("real hi TTS reachable", False, str(probe))
            return 1
        spoken = probe["duration"]
        print(f"       real Hindi TTS = {spoken:.2f}s; matching video length to it")
        matched = _video(os.path.join(tmp, "matched.mp4"), round(spoken, 2))

        r = main._publish_dubbed_languages(
            video_id="t4", clean_video_path=matched, script_text="x", topic="T",
            translations={"hi": {"translated_script": HINDI, "is_fallback": False,
                                 "language_name": "हिन्दी",
                                 "edge_tts_voice": "hi-IN-SwaraNeural",
                                 "title": "आर्टिफिशियल इंटेलिजेंस"}},
            thumbnail_path="", fmt="shorts")
        check("published the dub", r["published"] == ["hi"], str(r))
        if not r["published"]:
            print(f"       failed: {r['failed']}")
            return 1

        kw = CAPTURED[-1]
        check("publisher got the Hindi language, not 'en'",
              kw.get("default_language") == "hi", str(kw.get("default_language")))
        check("YouTube-only", kw.get("platforms") == ["youtube"], str(kw.get("platforms")))
        check("localized title used", "आर्टिफिशियल" in kw.get("title", ""), kw.get("title", ""))
        check("did not auto-clean the master mid-loop", kw.get("cleanup") is False)

        tags = kw.get("tags") or []
        check("localized tags were sent", len(tags) > 0, str(tags))
        check("  tags carry the language name", "हिन्दी" in tags, str(tags))
        check("  tags come from the translated title, not the English topic",
              any("आर्टिफिशियल" in t for t in tags), str(tags))

        dub_vid = kw["video_path"]
        check("dub video exists", os.path.exists(dub_vid), dub_vid)
        from utils.dub_pipeline import intro_seconds
        card_s = intro_seconds("hi")
        got = duration_of(dub_vid)
        check("dub duration = video + desync card",
              abs(got - (duration_of(matched) + card_s)) < 0.7,
              f"{got:.2f}s vs {duration_of(matched) + card_s:.2f}s")

        srt = kw.get("subtitle_path")
        check("an SRT was produced", bool(srt) and os.path.exists(srt), str(srt))
        if srt and os.path.exists(srt):
            with open(srt, encoding="utf-8") as f:
                body = f.read()
            first_start = body.split("-->")[0]
            cues = [l for l in body.splitlines() if "-->" in l]
            n_dev = sum(1 for c in body if "ऀ" <= c <= "ॿ")
            check("SRT carries real Devanagari (not the English source)", n_dev > 0,
                  f"{n_dev} Devanagari chars")
            check("SRT starts after the desync card",
                  f"00:00:0{int(card_s)}" in cues[0] or f"00:00:0{int(card_s)}," in cues[0],
                  f"first cue: {cues[0].strip() if cues else 'none'}")
            last_end = cues[-1].split("-->")[1].strip().split(" ")[0].replace(",", ".")
            check("last cue ends near the narration, not the card start",
                  last_end >= f"00:00:0{int(card_s)}", f"last cue ends {last_end}")
            print(f"       {len(cues)} cues, first starts {cues[0].split('-->')[0].strip()}")

    print("\n" + "=" * 68)
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {FAILED}")
        return 1
    print("RESULT: ALL PASS (nothing was uploaded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
