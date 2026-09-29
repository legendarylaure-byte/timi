"""P4: audit what the stock-footage path actually returns, and tile it.

Why this exists: after D39 removed the manim/blender/diagram render paths and the
branded intro card, stock footage is the pipeline's primary visual source. There
was no measurement of whether it is actually delivering, and one specific thing
looked wrong on inspection without being proven:

  asset_router.py:176  search_query = ", ".join(kw_list)
  scene_parser._infer_keywords()  asset_keywords = [title, tech[:3], visual[:3]]
  and those `visual` entries are IMAGE-GENERATION phrases, e.g.
  "neural network architecture with flowing attention connections".

So the primary search hands Pexels a comma-joined blob mixing a real title with
phrases written for a diffusion model. Pexels ANDs terms, so the join is expected
to return nothing, and the scene silently falls through to the per-keyword
fallback -- where the same image-gen phrases are tried literally.

This script measures it instead of asserting it. It calls the real functions
(clean_scene_keywords, search_and_download) rather than reimplementing the query
path, because an audit that reimplements the thing it audits cannot see its bugs.

Writes to /app/output/footage_audit/:
  contact_sheet.png   one tile per scene, captioned with the winning query
  report.json         per-scene machine-readable outcome

Run in-container (needs the API keys, ffmpeg and PIL):
  docker exec timi-pipeline python3 /app/scripts/footage_audit.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from PIL import Image, ImageDraw, ImageFont

from utils.scene_parser import clean_scene_keywords, _apply_category_style
from utils.stock_video import search_and_download, _keyword_expand

OUT_DIR = Path("/app/output/footage_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# One scene per category, shaped like what the pipeline actually produces:
# a real-ish narration block plus the category, which is what injects
# CATEGORY_VISUAL_KEYWORDS. Titles are the kinds of topics the slate is made of.
SCENES = [
    {
        "category": "AI News",
        "title": "OpenAI Ships a Cheaper Reasoning Model",
        "narration": (
            "The new model cuts inference cost by eighty percent. "
            "Developers can now run long chains of reasoning in production, "
            "because the transformer no longer burns a GPU budget on every token."
        ),
    },
    {
        "category": "Science & Technology",
        "title": "Quantum Error Correction Reaches a Milestone",
        "narration": (
            "A logical qubit held long enough to run a full algorithm. "
            "The result matters because quantum computers are limited by noise, "
            "not by the number of physical qubits we can fabricate."
        ),
    },
    {
        "category": "Programming & Software",
        "title": "Why Your Python Code Is Slow",
        "narration": (
            "Profiling beats guessing. The bottleneck was a list comprehension "
            "inside a nested loop, and the data layer was copying tensors twice "
            "before the model ever started training."
        ),
    },
    {
        "category": "World News (24hr)",
        "title": "Global Climate Accord Reaches Final Vote",
        "narration": (
            "Delegates approved the framework after overnight talks. "
            "The text commits signatories to emissions targets and a shared "
            "reporting standard for the first time."
        ),
    },
    {
        "category": "Nepal News",
        "title": "Kathmandu Opens Its First Quantum Lab",
        "narration": (
            "Researchers in Kathmandu will study superconducting qubits. "
            "The national project aims to train its own graduate students, "
            "rather than sending every one of them abroad."
        ),
    },
]


def _font(px: int, serif: bool = False):
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if serif
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    try:
        return ImageFont.truetype(path, px)
    except Exception:
        return ImageFont.load_default()


def _frame(path: str, at: float = 1.0) -> Image.Image | None:
    """Grab a single frame with ffmpeg. ffmpeg is the ground truth here --
    PIL cannot reliably open an arbitrary mp4 without imageio."""
    out = OUT_DIR / "_frame.jpg"
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", path,
           "-frames:v", "1", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 or not out.exists():
        return None
    try:
        return Image.open(out).convert("RGB")
    finally:
        out.unlink(missing_ok=True)


def audit_scene(idx: int, spec: dict) -> dict:
    scene = {
        "keyword": spec["title"],
        "description": spec["narration"],
        "asset_keywords": [spec["title"]],
        "render_type": "stock",
        "asset_type": "STOCK_FOOTAGE",
    }
    # Same call the pipeline makes, so the injected category vocabulary is real.
    scene = _apply_category_style([scene], spec["category"])[0]
    scene["asset_keywords"] = clean_scene_keywords(scene["asset_keywords"]) or ["technology"]

    kw_list = scene["asset_keywords"]
    joined = ", ".join(kw_list)

    # The exact primary query asset_router tries first.
    primary = search_and_download(joined, orientation="landscape", scene_idx=idx,
                                 video_id=f"audit{idx}", narration_text=spec["narration"])
    # And the per-keyword fallback, only if the join produced nothing -- otherwise
    # a second download would cost API calls and tell us nothing new.
    winner = primary
    if not winner:
        for k in kw_list:
            winner = search_and_download(k, orientation="landscape", scene_idx=idx,
                                         video_id=f"audit{idx}", narration_text=spec["narration"])
            if winner:
                break

    row = {
        "idx": idx,
        "category": spec["category"],
        "title": spec["title"],
        "keywords": kw_list,
        "joined_query": joined,
        "joined_query_chars": len(joined),
        "expanded_queries": _keyword_expand(joined)[:6],
        "primary_join_returned": bool(primary),
        "won_via": "joined_query" if primary else ("per_keyword" if winner else "nothing"),
        "winning_keyword": (winner or {}).get("keyword"),
        "source": (winner or {}).get("source"),
        "width": (winner or {}).get("width"),
        "height": (winner or {}).get("height"),
        "duration": round((winner or {}).get("duration", 0), 2),
        "path": (winner or {}).get("path"),
    }
    img = _frame(row["path"]) if row["path"] else None
    row["frame_ok"] = img is not None
    if img is not None:
        img.save(OUT_DIR / f"scene_{idx:02d}.jpg", quality=90)
        row["frame_path"] = f"scene_{idx:02d}.jpg"
    print(f"  [{idx}] {spec['category']:<26} via={row['won_via']:<13} "
          f"src={row['source']} {row['width']}x{row['height']} {row['duration']}s")
    return row


def contact_sheet(rows: list[dict]) -> Path:
    TW, TH = 480, 270           # tile image
    CAP = 92                    # caption block under each tile
    COLS = 3
    pad = 14
    n = max(len(rows), 1)
    rws = (n + COLS - 1) // COLS
    W = COLS * TW + pad * (COLS + 1)
    H = rws * (TH + CAP) + pad * (rws + 1) + 58

    sheet = Image.new("RGB", (W, H), (14, 12, 20))
    d = ImageDraw.Draw(sheet)
    f_h = _font(26, serif=True)
    f_l = _font(15)
    f_s = _font(13)
    d.text((pad, 16), "P4 footage audit - what the stock path actually returned",
           font=f_h, fill=(235, 230, 245))
    d.text((pad, 44), f"one scene per category, real search path, "
                      f"{sum(1 for r in rows if r['won_via']=='nothing')} of {n} returned nothing",
           font=f_s, fill=(150, 140, 170))

    for i, r in enumerate(rows):
        cx = pad + (i % COLS) * (TW + pad)
        cy = 58 + pad + (i // COLS) * (TH + CAP + pad)
        fp = OUT_DIR / r.get("frame_path", "")
        if fp.exists():
            tile = Image.open(fp).convert("RGB")
            tile.thumbnail((TW, TH), Image.LANCZOS)
            sheet.paste(tile, (cx + (TW - tile.width) // 2, cy + (TH - tile.height) // 2))
        else:
            d.rectangle([cx, cy, cx + TW, cy + TH], fill=(40, 20, 24))
            d.text((cx + 18, cy + TH // 2 - 8), "NO FOOTAGE RETURNED", font=f_s, fill=(240, 130, 130))

        d.text((cx, cy + TH + 6), r["category"], font=f_l, fill=(232, 226, 244))
        d.text((cx, cy + TH + 26), f"via {r['won_via']}", font=f_s, fill=(190, 170, 220))
        if r["winning_keyword"]:
            q = r["winning_keyword"]
            q = q if len(q) <= 44 else q[:41] + "..."
            d.text((cx, cy + TH + 44), f"“{q}”", font=f_s, fill=(160, 190, 255))
        d.text((cx, cy + TH + 64),
               f"{r['source'] or '-'} {r['width'] or '?'}x{r['height'] or '?'} "
               f"{r['duration'] or 0:.1f}s", font=f_s, fill=(150, 140, 165))

    out = OUT_DIR / "contact_sheet.png"
    sheet.save(out)
    return out


def main() -> int:
    print(f"[audit] output -> {OUT_DIR}")
    rows = []
    for i, spec in enumerate(SCENES):
        try:
            rows.append(audit_scene(i, spec))
        except Exception as e:                      # one bad scene must not
            print(f"  [{i}] ERROR {type(e).__name__}: {e}")   # hide the other 4
            rows.append({**spec, "idx": i, "won_via": "error", "error": str(e),
                         "source": None, "width": None, "height": None,
                         "duration": 0, "frame_ok": False})
    (OUT_DIR / "report.json").write_text(json.dumps(rows, indent=2))
    sheet = contact_sheet(rows)

    got = [r for r in rows if r["won_via"] != "nothing"]
    print(f"\n[audit] contact sheet -> {sheet}")
    print(f"[audit] footage returned for {len(got)}/{len(rows)} scenes")
    print(f"[audit] joined query returned for "
          f"{sum(1 for r in rows if r.get('primary_join_returned'))}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
