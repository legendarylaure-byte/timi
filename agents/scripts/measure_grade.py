"""Measure a rendered video's luma/chroma and report what the grade would do.

Run:
    python3 -m scripts.measure_grade /app/output/long-20260926-1_long.mp4
    python3 -m scripts.measure_grade a.mp4 b.mp4 --json
    python3 -m scripts.measure_grade a.mp4 --histogram

`--histogram` answers the question a mean cannot: a cinematic dark frame and a
flat muddy one have the same average, and only the distribution tells them
apart. You want mass in the shadows *and* a real highlight tail, not everything
piled into one bucket.

Why this exists: `GRADE_REFERENCE_YUV` used to be a freehand guess. The old teal
reference (y=140,u=160,v=80) turned into a silent 4% desaturation of every frame
and sat 32/255 off neutral chroma, so ordinary footage measured as "off brand"
and got re-encoded for no reason. The replacement is derived from measured
output, which means the thing that justifies it has to be measurable -- hence
this script, so the decision can be re-checked against new footage instead of
inherited on faith.

Note `signalstats` is an ffmpeg *video filter*, not an ffprobe metadata section.
`ffprobe -show_entries frame=...:signalstats=...` always fails and silently
disables grading. `metadata=print` is the supported reader.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.brand_palette import GRADE_REFERENCE_YUV  # noqa: E402
from utils.video_compositor import _histogram_shift  # noqa: E402

_ROW = re.compile(r"lavfi\.signalstats\.(YAVG|UAVG|VAVG)=([0-9.]+)")


def measure(path: str, fps: float = 2.0) -> dict | None:
    """Mean YAVG/UAVG/VAVG over the clip, or None if signalstats yields nothing."""
    dump = os.path.join(tempfile.gettempdir(), f"grade_{os.getpid()}.txt")
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path,
         "-vf", f"fps={fps},signalstats,metadata=print:file={dump}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    try:
        if proc.returncode != 0 or not os.path.exists(dump):
            print(f"  signalstats failed rc={proc.returncode} {proc.stderr[:200]}", file=sys.stderr)
            return None
        text = open(dump, errors="ignore").read()
    finally:
        try:
            os.unlink(dump)
        except OSError:
            pass

    acc = {"YAVG": 0.0, "UAVG": 0.0, "VAVG": 0.0}
    n = dict.fromkeys(acc, 0)
    for line in text.splitlines():
        m = _ROW.search(line)
        if m:
            acc[m.group(1)] += float(m.group(2))
            n[m.group(1)] += 1
    if not n["YAVG"]:
        return None
    return {
        "y_mean": acc["YAVG"] / n["YAVG"],
        "u_mean": acc["UAVG"] / n["UAVG"],
        "v_mean": acc["VAVG"] / n["VAVG"],
        "frames": n["YAVG"],
    }


def derived_eq(ref: dict) -> dict:
    """The eq filter `_apply_color_correction` builds from a reference."""
    y, v = ref["y_mean"] / 255.0, ref["v_mean"] / 255.0
    return {
        "brightness": (y - 0.5) * 0.3,
        "contrast": 0.95 + y * 0.1,
        "saturation": 0.9 + v * 0.2,
    }


def report(path: str, threshold: float = 0.15) -> dict:
    m = measure(path)
    if m is None:
        return {"path": path, "error": "signalstats produced no YAVG rows"}
    ref = GRADE_REFERENCE_YUV
    shift = _histogram_shift(ref, m)
    return {
        "path": os.path.basename(path),
        "measured": m,
        "reference": ref,
        "shift": round(shift, 4),
        "threshold": threshold,
        "would_grade": shift > threshold,
        "derived_eq": {k: round(v, 4) for k, v in derived_eq(ref).items()},
    }


def luma_histogram(path: str, fps: float = 1.0) -> dict | None:
    """Per-second YAVG distribution. A mean hides whether a dark frame is
    cinematic (mass in shadows + a highlight tail) or just muddy (one pile)."""
    m = measure(path, fps=fps)
    if m is None:
        return None
    dump = os.path.join(tempfile.gettempdir(), f"hist_{os.getpid()}.txt")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path,
         "-vf", f"fps={fps},signalstats,metadata=print:file={dump}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    try:
        text = open(dump, errors="ignore").read()
    finally:
        try:
            os.unlink(dump)
        except OSError:
            pass
    vals = sorted(float(x) for x in re.findall(r"YAVG=([0-9.]+)", text))
    if not vals:
        return None
    n = len(vals)
    bands = [(0, 32, "crushed shadows"), (32, 64, "dark"), (64, 96, "mid-low"),
             (96, 128, "mid"), (128, 160, "bright"), (160, 256, "highlights")]
    out = {"frames": n, "min": vals[0], "max": vals[-1],
           "p10": vals[n // 10], "p50": vals[n // 2], "p90": vals[9 * n // 10],
           "bands": []}
    for lo, hi, label in bands:
        c = sum(1 for v in vals if lo <= v < hi)
        out["bands"].append({"label": label, "pct": round(c / n * 100, 1), "count": c})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--threshold", type=float, default=0.15)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--histogram", action="store_true")
    a = ap.parse_args()

    if a.histogram:
        for v in a.videos:
            h = luma_histogram(v)
            if h is None:
                print(f"{os.path.basename(v)}: no histogram")
                continue
            print(f"{os.path.basename(v)}  ({h['frames']}s sampled)")
            print(f"  YAVG  min={h['min']:6.1f}  p10={h['p10']:6.1f}  "
                  f"p50={h['p50']:6.1f}  p90={h['p90']:6.1f}  max={h['max']:6.1f}")
            for b in h["bands"]:
                bar = "#" * int(b["pct"] / 100 * 60)
                print(f"    {b['label']:16s} {b['pct']:5.1f}%  {bar}")
            print()
        return 0

    rows = [report(v, a.threshold) for v in a.videos]
    if a.json:
        print(json.dumps(rows, indent=2))
        return 0

    for r in rows:
        if "error" in r:
            print(f"{r['path']}: ERROR {r['error']}")
            continue
        m, eq = r["measured"], r["derived_eq"]
        print(f"{r['path']}  ({m['frames']} frames @2fps)")
        print(f"  measured  Y={m['y_mean']:7.2f}  U={m['u_mean']:7.2f}  V={m['v_mean']:7.2f}")
        print(f"  reference Y={r['reference']['y_mean']:7.2f}  U={r['reference']['u_mean']:7.2f}  "
              f"V={r['reference']['v_mean']:7.2f}")
        verdict = "WOULD GRADE" if r["would_grade"] else "left alone"
        print(f"  shift     {r['shift']:.4f}  vs {r['threshold']}  -> {verdict}")
        print(f"  eq        brightness={eq['brightness']:+.3f} contrast={eq['contrast']:.3f} "
              f"saturation={eq['saturation']:.3f}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
