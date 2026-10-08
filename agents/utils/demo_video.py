"""Deterministic <30s demo short for TikTok composer tests. No LLM.

Builds 3 branded portrait cards from a topic, narrates a fixed template with
Edge TTS, and muxes them into one mp4 rough-capped below 30s. Used by the
`demo_video_requests` job so the dashboard always has a test video to queue
even after the nightly run posts and cleans up its renders.
"""
import asyncio
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.brand_palette import LICORICE, PURPLE, ORANGE, hex_to_rgb

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1080, 1920
FPS = 24
MAX_DURATION = 30.0

_NARRATION_FACT_LEAD = "quick look"
_TEMPLATE = (
    "Have you subscribed to Vyom AI Cloud? Here's a {LEAD} at {TOPIC}. "
    "AI tools are changing faster than ever. Learning one new skill a day "
    "builds a career no machine can replace. Follow for daily AI updates."
)

_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/System/Library/Fonts",
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in _FONT_DIRS:
        path = Path(d) / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.Draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _card(topic: str, headline: str, body_lines: list[str], out_path: Path,
          accent: str = PURPLE) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), LICORICE)
    draw = ImageDraw.Draw(img)
    accent_rgb = hex_to_rgb(accent)
    white = (255, 255, 255)

    # Top accent band (brand look).
    draw.rectangle([0, 0, WIDTH, 12], fill=accent_rgb)

    title_font = _font(92)
    for i, ln in enumerate(_wrap(draw, topic, title_font, WIDTH - 140)[:2]):
        draw.text((70, 150 + i * 110), ln, fill=white, font=title_font)

    draw.rectangle([70, 150 + (len(_wrap(draw, topic, title_font, WIDTH - 140)[:2])) * 110 + 20,
                    70 + 160, 150 + (len(_wrap(draw, topic, title_font, WIDTH - 140)[:2])) * 110 + 24],
                   fill=accent_rgb)

    head_font = _font(60, bold=True)
    body_font = _font(48, bold=False)
    y = 720
    draw.text((70, y), headline, fill=hex_to_rgb(ORANGE), font=head_font)
    y += 90
    for ln in body_lines:
        for part in _wrap(draw, ln, body_font, WIDTH - 140)[:2]:
            draw.text((70, y), part, fill=(220, 220, 220), font=body_font)
            y += 80

    # CTA footer strip.
    foot_font = _font(42, bold=True)
    cta = "Vyom AI Cloud"
    bbox = draw.textbbox((0, 0), cta, font=foot_font)
    cw = bbox[2] - bbox[0]
    draw.text(((WIDTH - cw) // 2, HEIGHT - 160), cta, fill=white, font=foot_font)
    draw.rectangle([(WIDTH - 220) // 2, HEIGHT - 100, (WIDTH + 220) // 2, HEIGHT - 92], fill=accent_rgb)

    img.save(out_path)


def build_narration(topic: str) -> str:
    t = topic.strip() or "AI"
    if len(t) > 60:
        t = t[:57] + "..."
    return _TEMPLATE.format(TOPIC=t, LEAD=_NARRATION_FACT_LEAD)


def render_demo_short(topic: str, out_path: str, video_id: str = "") -> dict:
    """Render a <30s 1080x1920 demo short. Returns {path, duration_seconds}."""
    out_path = str(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp = Path(out_path + ".cards")
    tmp.mkdir(parents=True, exist_ok=True)

    facts = [
        "AI skills compound daily",
        "One new skill per day",
        "Free, practical, beginner-friendly",
    ]

    cards = [
        (topic.strip() or "AI in under 30 seconds", "WHAT YOU'LL LEARN", facts),
        (topic.strip() or "AI", "WHY IT MATTERS", ["Faster than most think", "Built for beginners", "No jargon, no hype"]),
        ("Follow for daily AI", "NEXT STEPS", ["Subscribe", "Turn on notifications", "New videos daily"]),
    ]
    card_paths = []
    for i, (headline, body_head, body) in enumerate(cards):
        p = tmp / f"card_{i}.png"
        _card(headline, body_head, body, p, accent=(PURPLE, ORANGE, PURPLE)[i])
        card_paths.append(p)

    narration = build_narration(topic)
    wav = str(tmp / "vo.wav")
    from utils.voice_provider import get_tts_provider
    provider = get_tts_provider("edge")
    ok = asyncio.run(provider.generate(narration, wav))
    if not ok or not os.path.exists(wav) or os.path.getsize(wav) < 100:
        raise RuntimeError("Edge TTS failed for demo narration")

    from utils.subprocess_helper import safe_run, safe_run_bool
    probe = safe_run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", wav], timeout=15)
    try:
        audio_dur = min(float(probe.stdout.strip()), MAX_DURATION)
    except Exception:
        audio_dur = 18.0
    if audio_dur < 4:
        audio_dur = 4.0

    # Allocate each card a fair slice of the narration.
    per = audio_dur / len(cards)
    segs = []
    concat_file = tmp / "concat.txt"
    with open(concat_file, "w") as f:
        for i, cp in enumerate(card_paths):
            seg = tmp / f"seg_{i}.mp4"
            part = per if i < len(cards) - 1 else audio_dur - per * (len(cards) - 1)
            cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(cp),
                   "-t", f"{part:.3f}", "-r", str(FPS),
                   "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                   "-pix_fmt", "yuv420p", str(seg)]
            if not safe_run_bool(cmd, timeout=120):
                raise RuntimeError(f"Card segment {i} render failed")
            f.write(f"file '{seg.resolve()}'\n")
            segs.append(seg)

    silent = str(tmp / "silent.mp4")
    silent_cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
                  "-t", f"{audio_dur:.3f}", "-c:a", "aac", "-b:a", "96k", str(silent)]
    if not safe_run_bool(silent_cmd, timeout=60):
        raise RuntimeError("silent track render failed")

    raw = str(tmp / "raw.mp4")
    concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                  "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                  "-pix_fmt", "yuv420p", str(raw)]
    if not safe_run_bool(concat_cmd, timeout=120):
        raise RuntimeError("concat render failed")

    mux_cmd = ["ffmpeg", "-y", "-i", str(raw), "-i", str(wav),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
               "-shortest", "-pix_fmt", "yuv420p", out_path]
    if not safe_run_bool(mux_cmd, timeout=120):
        raise RuntimeError("mux failed")

    for p in list(tmp.iterdir()):
        try:
            p.unlink()
        except OSError:
            pass
    tmp.rmdir()

    return {"path": out_path, "duration_seconds": round(audio_dur, 2)}


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI in under 30 seconds"
    r = render_demo_short(topic, str(OUTPUT_DIR / "demo_test.mp4"))
    print(r)