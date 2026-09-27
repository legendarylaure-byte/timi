"""Verifies the clean-master mechanism that dubbing depends on.

`burn_subtitles()` had no callers before this change, so the "composite clean,
then burn the English SRT in a second pass" path is unproven. This builds a real
two-scene video both ways and checks the results are equivalent in length while
actually differing in the caption band.

Run:  python3 -m utils.clean_master_selfcheck
"""
import os
import subprocess
import sys
import tempfile

FAILED = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(label)


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def _clip(path, seconds, color):
    # Flat dark colour keeps the caption band easy to measure; the noise layer
    # is only there to push the file past the 10KB clip gate so _process_clip
    # takes the same Ken Burns branch real stock/LTX clips take.
    r = _run(["ffmpeg", "-y", "-f", "lavfi", "-i",
              f"color=c={color}:size=1280x720:rate=24",
              "-vf", "noise=alls=24:allf=t+u", "-t", str(seconds),
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", path])
    if r.returncode != 0 or not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"clip build failed: {r.stderr[-300:]}")
    return path


def _voice(path, seconds):
    r = _run(["ffmpeg", "-y", "-f", "lavfi", "-i",
              "sine=frequency=260:sample_rate=44100", "-t", str(seconds),
              "-ac", "1", "-c:a", "pcm_s16le", path])
    if r.returncode != 0 or not os.path.exists(path):
        raise RuntimeError(f"voice build failed: {r.stderr[-300:]}")
    return path


def _srt(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,500 --> 00:00:04,000\nCAPTION TEST LINE\n\n"
                "2\n00:00:04,200 --> 00:00:07,500\nSECOND CAPTION LINE\n")
    return path


def _caption_pixels(video, at="2.0"):
    """Bright-pixel count over the WHOLE frame.

    The caption band is not where you would guess: with BorderStyle=3 and
    MarginV=40, libass draws the box around rows ~840-910 of 1080, well above
    the bottom eighth. Measuring a guessed band reports "no captions" on a
    perfectly good burn, so scan everything.
    """
    out_png = os.path.join(tempfile.gettempdir(), "cm_caption_probe.png")
    _run(["ffmpeg", "-y", "-v", "error", "-ss", at, "-i", video, "-frames:v", "1",
          "-f", "image2", out_png])
    if not os.path.exists(out_png):
        return -1
    from PIL import Image
    import numpy as np
    arr = np.array(Image.open(out_png).convert("L"), dtype=float)
    return int((arr > 100).sum())


def _dur(path):
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path])
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def main():
    print("=" * 68)
    print("CLEAN MASTER SELFCHECK (two real composites, no publish)")
    print("=" * 68)
    import utils.video_compositor as vc
    from utils.video_compositor import composite_video, burn_subtitles
    from utils.subtitle_gen import should_burn_subtitles, should_upload_cc

    # This selfcheck proves one thing: whether the clean master carries burned
    # captions. It detects that by counting pixels above luma 100 and asserting
    # the count is exactly 0.
    #
    # That proxy stopped being valid once colour grading shipped. The grade
    # legitimately lifts dark footage toward the Y=92 reference, and the two
    # test clips here are 0x1e2a38 / 0x2a1e38 (luma ~40), so grading pushed 185
    # of their pixels over the threshold and the check reported captions in a
    # master that has none -- while a real burn scores ~53,000. 185 vs 53,000 is
    # a 290x gap, so the pixels were source content, not text.
    #
    # Grading is orthogonal to caption routing, so switch it off here rather than
    # invent a brightness threshold. The grade is verified on its own terms by
    # scripts/measure_grade.py and tests/test_brand_colors.py; if it silently
    # stopped working, this selfcheck would never have noticed either way.
    vc.GRADE_STRENGTH = 0.0

    with tempfile.TemporaryDirectory() as tmp:
        # composite_video writes to the module-level OUTPUT_DIR, which is the
        # host-mounted agents/output/. Redirect it so a selfcheck never drops
        # ~240MB of test video next to real deliverables.
        vc.OUTPUT_DIR = __import__("pathlib").Path(tmp)
        clips = [{"path": _clip(os.path.join(tmp, "a.mp4"), 4, "0x1e2a38"), "duration": 4.0},
                 {"path": _clip(os.path.join(tmp, "b.mp4"), 4, "0x2a1e38"), "duration": 4.0}]
        voice = _voice(os.path.join(tmp, "v.wav"), 8.0)
        srt = _srt(os.path.join(tmp, "s.srt"))

        # shorts is the format that burns inside composite_video, so it is the
        # one that can prove the re-burn matches the single-pass result.
        print("\n[1] dubs OFF path: subtitles burn inside composite (unchanged)")
        direct = composite_video(clips=[dict(c) for c in clips], voice_path=voice,
                                 format_type="shorts", video_id="direct",
                                 subtitle_path=srt)
        check("composite returned a file", bool(direct), str(direct))
        if not direct:
            return 1
        d_dur = _dur(direct)

        print("\n[2] dubs ON path: composite clean, then burn English in pass 2")
        clean = composite_video(clips=[dict(c) for c in clips], voice_path=voice,
                                format_type="shorts", video_id="clean",
                                subtitle_path=None)
        check("clean master returned a file", bool(clean), str(clean))
        if not clean:
            return 1
        c_dur = _dur(clean)

        burned_path = os.path.join(tmp, "burned.mp4")
        ok = burn_subtitles(clean, srt, burned_path, fontsize=32, tier="")
        check("burn_subtitles reported success", ok is True, str(ok))
        check("burned file exists", os.path.exists(burned_path))
        if not os.path.exists(burned_path):
            return 1
        b_dur = _dur(burned_path)

        print("\n[3] equivalence")
        check("clean and direct have the same length",
              abs(c_dur - d_dur) < 0.6, f"clean={c_dur:.2f}s direct={d_dur:.2f}s")
        check("burning did not change the length",
              abs(b_dur - c_dur) < 0.6, f"burned={b_dur:.2f}s clean={c_dur:.2f}s")

        print("\n[4] the clean master really is caption-free, and burning adds them")
        pc, pd, pb = _caption_pixels(clean), _caption_pixels(direct), _caption_pixels(burned_path)
        check("could sample every frame", -1 not in (pc, pd, pb), f"{pc} {pd} {pb}")
        check("clean master has NO burned captions", pc == 0, f"bright_px={pc}")
        check("single-pass burn drew captions", pd > 500, f"bright_px={pd}")
        check("re-burn drew captions", pb > 500, f"bright_px={pb}")
        check("re-burn put text in the same place as the single-pass burn",
              abs(pb - pd) / max(pd, 1) < 0.35, f"direct={pd} burned={pb}")

        print("\n[5] caption routing gives every format exactly ONE caption layer")
        check("longs burn (guaranteed mobile visibility)",
              should_burn_subtitles("long"))
        check("longs do NOT also upload a soft CC track",
              not should_upload_cc("long"), "would double up on burned captions")
        check("shorts burn", should_burn_subtitles("shorts"))
        check("shorts do NOT also upload a soft CC track",
              not should_upload_cc("shorts"))
        print(f"       upload_cc(long)={should_upload_cc('long')} "
              f"(dubs bypass via default_language -- see youtube_upload._caption_body)")

    print("\n" + "=" * 68)
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {FAILED}")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
