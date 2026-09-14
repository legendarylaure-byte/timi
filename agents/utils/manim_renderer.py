"""ManimCE renderer — code-gen → preview → retry → final render."""
import os
import re
import hashlib
import logging
import threading
from pathlib import Path

from utils.subprocess_helper import safe_run, register_temp_dir

logger = logging.getLogger(__name__)

MANIM_RENDER_DIR = Path(__file__).resolve().parent.parent / "tmp" / "manim_gen"
MANIM_RENDER_DIR.mkdir(parents=True, exist_ok=True)
register_temp_dir(str(MANIM_RENDER_DIR))


_BARCHART_KWARGS = {
    "bar_names", "y_range", "x_length", "y_length", "bar_colors",
    "bar_width", "bar_fill_opacity", "bar_stroke_width",
}


def _split_top_args(inner: str) -> list[str]:
    """Split on commas outside brackets/parens (BarChart spans lines, values are lists)."""
    parts, depth, cur = [], 0, ""
    for ch in inner + ",":
        if ch in "[({":
            depth += 1
        elif ch in "])}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [p for p in parts if p]


def _sanitize_bar_chart(inner: str) -> str:
    """Keep only valid manim 0.21 BarChart kwargs + leading positional values.
    The codegen LLM reliably guesses legacy kwargs (show_values, value_color,
    font_size, height/width) that raise TypeError — drop them deterministically.
    """
    parts = _split_top_args(inner)
    kept = []
    for p in parts:
        if "=" not in p:
            if not any("=" in k for k in kept):
                kept.append(p)  # positional (values) only before first kwarg
            continue
        name = p.split("=", 1)[0].strip()
        val = p.split("=", 1)[1].strip()
        if name in ("height", "width"):
            name = "y_length" if name == "height" else "x_length"
        if name in _BARCHART_KWARGS:
            kept.append(f"{name}={val}")
    return ", ".join(kept)


def _apply_manim_compat(code: str) -> str:
    """Post-process common manim 0.21 API mismatches in LLM output."""

    def fix_bar_chart(m):
        return f"BarChart({_sanitize_bar_chart(m.group(1))})"

    return re.sub(r"BarChart\(([^)]*)\)", fix_bar_chart, code)

# One manim render at a time on the 16GB box (CPU-heavy, shares with LTX/Blender).
_preview_lock = threading.Lock()

_PALETTE = ["#00CCCC", "#FF6B35", "#8a50e8", "#5aa9e6", "#e6c229", "#9ae66e"]


def _item_label(item) -> str:
    if isinstance(item, dict):
        return str(item.get("label") or item.get("name") or item.get("value") or "step")[:22]
    return str(item)[:22]


def _item_value(item) -> float:
    if isinstance(item, dict):
        try:
            return max(float(item.get("value") or 0), 0.15)
        except (TypeError, ValueError):
            return 1.0
    return 1.0


def _data_viz_scene(task: dict) -> str | None:
    """Deterministically generate a manim scene for known diagram types.
    The LLM codegen reliably trips manim internal edge cases (zero-height BarChart
    bars, legacy kwargs) — data-viz scenes don't need it. Returns source or None.
    """
    d = task.get("diagram")
    if not isinstance(d, dict):
        return None
    dtype = (d.get("type") or "").strip().lower()
    items = d.get("items") or d.get("blocks") or d.get("layers") or []
    if not items:
        return None
    DUR = max(2.0, float(task.get("duration", 8.0)))
    TITLE = (d.get("title") or task.get("title") or "AI Concept")[:60]
    L = [
        "from manim import *",
        "",
        "class DiagScene(Scene):",
        "    def construct(self):",
        '        self.camera.background_color = "#1e1e1e"',
        f"        title = Text({TITLE!r}, font_size=40, color=\"#00CCCC\").to_edge(UP, buff=0.4)",
        "        self.add(title)",
    ]

    if dtype in ("bar_chart", "comparison"):
        n = min(len(items), 6)
        vals = [_item_value(it) for it in items[:n]]
        vmax = max(vals) or 1.0
        heights = [max(0.3, v / vmax * 3.2) for v in vals]
        per = DUR / n * 0.75
        gap = DUR - per * n
        L.append("        bars = VGroup()")
        L.append("        bar_labels = VGroup()")
        for i in range(n):
            col = _PALETTE[i % len(_PALETTE)]
            L.append(f'        b{i} = Rectangle(width=1.3, height={heights[i]:.2f}, stroke_color="{col}", fill_color="{col}", fill_opacity=0.9)')
            L.append(f'        lb{i} = Text({_item_label(items[i])!r}, font_size=26, color="#FFFFFF")')
            L.append(f"        bars.add(b{i})")
            L.append(f"        bar_labels.add(lb{i})")
        L.append("        bars.arrange(RIGHT, buff=0.45).shift(DOWN * 0.5)")
        L.append("        bar_labels.arrange(RIGHT, buff=0.45).next_to(bars, DOWN, buff=0.3)")
        L.append("        self.add(bar_labels)")
        for i in range(n):
            L.append(f"        self.play(GrowFromEdge(b{i}, DOWN), run_time={per:.2f})")
        L.append(f"        self.wait({max(0.4, gap):.1f})")
        return "\n".join(L)

    if dtype in ("architecture", "layers", "stack", "layer_explosion"):
        n = min(len(items), 6)
        bh = min(0.9, 4.6 / n)
        per = DUR / n * 0.8
        gap = DUR - per * n
        L.append("        boxes = VGroup()")
        L.append("        box_labels = VGroup()")
        for i in range(n):
            col = _PALETTE[i % len(_PALETTE)]
            L.append(f'        x{i} = Rectangle(width=5.0, height={bh:.2f}, stroke_color="{col}", fill_color="{col}", fill_opacity=0.85)')
            L.append(f'        xt{i} = Text({_item_label(items[i])!r}, font_size=24, color="#1e1e1e")')
            L.append(f"        boxes.add(x{i})")
            L.append(f"        box_labels.add(xt{i})")
        L.append("        boxes.arrange(DOWN, buff=0.15).shift(DOWN * 0.2)")
        L.append("        box_labels.arrange(DOWN, buff=0.15)")
        L.append("        self.add(box_labels)")
        for i in range(n):
            L.append(f"        self.play(GrowFromEdge(x{i}, UP), run_time={per:.2f})")
        L.append(f"        self.wait({max(0.4, gap):.1f})")
        return "\n".join(L)

    if dtype in ("flow", "pipeline", "process", "timeline"):
        n = min(len(items), 5)
        x0, w = -7.2, min(3.0, 14.4 / (n + 1))
        y = 0.6
        per = (DUR - (n - 1) * 0.4) / n if n else DUR
        L.append(f"        line = Line([{x0 + w / 2 - 4}, {y}, 0], [{x0 + w / 2 + 12}, {y}, 0], color='#8a50e8', stroke_width=4)")
        L.append("        self.play(Create(line), run_time=0.5)")
        for i in range(n):
            col = _PALETTE[i % len(_PALETTE)]
            cx = x0 + i * w + w / 2
            L.append(f'        p{i} = Circle(radius=0.45, color="{col}", fill_color="{col}", fill_opacity=1.0).move_to([{cx:.2f}, {y}, 0])')
            L.append(f'        pt{i} = Text({_item_label(items[i])!r}, font_size=22, color="#FFFFFF").next_to(p{i}, {"UP" if i % 2 == 0 else "DOWN"}, buff=0.4)')
            L.append(f"        self.play(GrowFromCenter(p{i}), run_time=0.4)")
            L.append(f"        self.play(FadeIn(pt{i}), run_time={per - 0.4:.2f})")
            if i > 0:
                prev_x = x0 + (i - 1) * w + w / 2
                L.append(f"        a{i} = Line([{prev_x + 0.45:.2f}, {y}, 0], [{cx - 0.45:.2f}, {y}, 0], color='#00CCCC', stroke_width=5)")
                L.append(f"        self.play(Create(a{i}), run_time=0.2)")
        L.append("        self.wait(0.5)")
        return "\n".join(L)

    # Unknown type → let the LLM attempt it
    return None


def _render_source(code: str, out_base: Path, w: int, h: int, quality: str = "ql",
                   timeout: int = 300) -> tuple[int, str]:
    """Write code to a temp file, render, return (returncode, stderr)."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="manim_run_") as td:
        py_path = os.path.join(td, "scene.py")
        with open(py_path, "w") as f:
            f.write(code)
        cmd = ["manim", f"-{quality}", "-r", f"{w},{h}", "-o", str(out_base), py_path, "DiagScene"]
        r = safe_run(cmd, timeout=timeout, capture_output=True)
        return r.returncode, r.stderr or ""


def render_manim_scene(
    scene: dict,
    video_id: str,
    scene_idx: int,
    format_type: str = "long",
    narration: str = "",
    topic: str = "",
) -> str | None:
    """Render a Manim scene and return the mp4 path (or None on failure).

    Flow:
    1. Generate Python via manim_agent.
    2. Preview render (-ql) to validate syntax + animation.
    3. Feed traceback back to LLM up to 2 times on failure.
    4. Final render at MANIM_RENDER_QUALITY.
    5. Cache keyed on narration+diagram hash.
    """
    if os.getenv("ENABLE_MANIM", "true").lower() != "true":
        return None

    try:
        from crew.manim_agent import generate_manim_code, fix_manim_code
    except ImportError as e:
        logger.warning(f"[Manim] manim_agent import failed: {e}")
        return None

    quality = os.getenv("MANIM_RENDER_QUALITY", "qh")
    w, h = (1080, 1920) if format_type == "shorts" else (1920, 1080)
    dur = scene.get("target_duration", scene.get("duration", 8.0))
    dur = max(2.0, float(dur))

    task = {
        "title": topic or "AI Concept",
        "narration": narration or scene.get("narration_text", ""),
        "diagram": scene.get("diagram"),
        "description": scene.get("description", ""),
        "duration": dur,
        "width": w,
        "height": h,
        "format_type": format_type,
    }

    # Deterministic path preferred: known diagram types need no LLM and avoid
    # manim internal edge cases (zero-height BarChart bars, legacy kwargs).
    code = _data_viz_scene(task)
    src_desc = "deterministic"
    if not code:
        if scene.get("render_type") != "manim" or not scene.get("diagram"):
            # Only LLM-generate for free-form manim intentions, not bare fallbacks.
            logger.info(f"[Manim] scene {scene_idx}: no diagram spec, skipping")
            return None
        code = generate_manim_code(task)
        src_desc = "llm"
        if not code:
            return None
        code = _apply_manim_compat(code)

    # Cache check
    raw = f"{src_desc}{task['narration']}{task['diagram']}"
    cache_key = hashlib.sha256(raw.encode()).hexdigest()[:16]
    cached = MANIM_RENDER_DIR / f"manim_{video_id}_{scene_idx}_{cache_key}.mp4"
    if cached.exists() and cached.stat().st_size > 1000:
        logger.info(f"[Manim] scene {scene_idx}: cache hit")
        return str(cached)

    final_base: Path = cached.with_suffix("")

    if src_desc == "deterministic":
        # Deterministic code: render straight at final quality, no retry loop.
        with _preview_lock:
            rc, err = _render_source(code, final_base, w, h, quality=quality, timeout=600)
        final_mp4 = final_base.with_suffix(".mp4")
        if rc == 0 and final_mp4.exists() and final_mp4.stat().st_size > 1000:
            dtype = (task.get("diagram") or {}).get("type", "unknown")
            logger.info(f"[Manim] scene {scene_idx}: deterministic '{dtype}' OK")
            return str(final_mp4)
        logger.warning(f"[Manim] scene {scene_idx}: deterministic render failed rc={rc} ({err[-400:]})")
        return None

    # LLM path: preview → fix → final.
    tmp_dir = MANIM_RENDER_DIR / f"tmp_{video_id}_{scene_idx}_{cache_key}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    preview_base = tmp_dir / "preview"

    with _preview_lock:
        for attempt in range(3):
            rc, err = _render_source(code, preview_base, w, h, quality="ql", timeout=300)
            preview_mp4 = preview_base.with_suffix(".mp4")
            if rc == 0 and preview_mp4.exists() and preview_mp4.stat().st_size > 1000:
                break
            tb = err[-2500:]
            logger.info(f"[Manim] scene {scene_idx} preview attempt {attempt+1} failed, retrying with LLM fix")
            code = _apply_manim_compat(fix_manim_code(code, tb))
            if not code:
                logger.warning(f"[Manim] scene {scene_idx} fix returned empty")
                _cleanup(tmp_dir)
                return None
        else:
            logger.warning(f"[Manim] scene {scene_idx} failed after 3 preview attempts")
            _cleanup(tmp_dir)
            return None

    rc, _ = _render_source(code, final_base, w, h, quality=quality, timeout=600)
    final_mp4 = final_base.with_suffix(".mp4")
    if rc == 0 and final_mp4.exists() and final_mp4.stat().st_size > 1000:
        _cleanup(tmp_dir)
        logger.info(f"[Manim] scene {scene_idx}: rendered OK ({final_mp4})")
        return str(final_mp4)

    logger.warning(f"[Manim] scene {scene_idx}: final render failed")
    _cleanup(tmp_dir)
    return None


def _cleanup(tmp_dir: Path):
    try:
        for f in tmp_dir.iterdir():
            f.unlink()
        tmp_dir.rmdir()
    except Exception:
        pass


def render_manim_code_snippet(
    code_lines: list[str] | str,
    video_id: str,
    scene_idx: int,
    format_type: str = "long",
    title: str = "",
) -> str | None:
    """Render a static code panel via Manim Code object (no LLM needed).
    Deterministic, fast. Returns mp4 path or None.
    """
    if os.getenv("ENABLE_MANIM", "true").lower() != "true":
        return None

    if isinstance(code_lines, list):
        code_str = "\n".join(code_lines)
    else:
        code_str = code_lines or "# code example"
    code_str = code_str[:4000]  # Cap for manim Code rendering

    w, h = (1080, 1920) if format_type == "shorts" else (1920, 1080)

    # Build a minimal Manim scene directly (no LLM).
    scene_py = f'''from manim import *
from manim import Code

class DiagScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        title_text = {(title or "Code")[:60]!r}
        if title_text:
            title = Text(title_text, color="#00CCCC", font_size=36)
            title.to_edge(UP, buff=0.5)
            self.add(title)
        code = Code(
            code_string={code_str!r},
            language="python",
            background="rectangle",
            formatter_style="monokai",
            add_line_numbers=False,
        )
        code.scale_to_fit_width({w - 200})
        code.move_to(ORIGIN if not title_text else DOWN * 0.3)
        self.wait(0.5)
'''

    cache_key = hashlib.sha256(code_str.encode()).hexdigest()[:12]
    out_base = MANIM_RENDER_DIR / f"code_{video_id}_{scene_idx}_{cache_key}"

    tmp_dir = MANIM_RENDER_DIR / f"code_tmp_{video_id}_{scene_idx}_{cache_key}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    py_path = tmp_dir / "scene.py"
    py_path.write_text(scene_py)

    quality = os.getenv("MANIM_RENDER_QUALITY", "qh")
    with _preview_lock:
        cmd = [
            "manim", f"-{quality}",
            "-r", f"{w},{h}",
            "-o", str(out_base),
            str(py_path),
            "DiagScene",
        ]
        result = safe_run(cmd, timeout=180, capture_output=True)

    out_mp4 = out_base.with_suffix(".mp4")
    _cleanup(tmp_dir)
    if result.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 1000:
        return str(out_mp4)
    return None
