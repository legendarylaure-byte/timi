"""Render animated visual annotations (callouts, arrows, highlights, counters)
on top of video frames using ffmpeg drawtext/drawbox/drawgraph filters.

Each annotation type produces one or more ffmpeg vf filter strings
that can be appended to the compositor's filter chain.
"""



BRAND_TEAL = "#00CCCC"
BRAND_ORANGE = "#FF6B35"
BRAND_PURPLE = "#8a50e8"
BRAND_DARK = "#1e1e1e"
BRAND_WHITE = "#FFFFFF"

FONT = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"

POSITIONS = {
    "top-left":      ("(w*0.05)",            "h*0.08"),
    "top-right":     ("(w-text_w-w*0.05)",   "h*0.08"),
    "center":        ("(w-text_w)/2",        "(h-text_h)/2"),
    "bottom-left":   ("(w*0.05)",            "(h-text_h-h*0.05)"),
    "bottom-right":  ("(w-text_w-w*0.05)",   "(h-text_h-h*0.05)"),
    "top-center":    ("(w-text_w)/2",        "h*0.08"),
    "middle-left":   ("(w*0.03)",            "(h-text_h)/2"),
    "middle-right":  ("(w-text_w-w*0.03)",   "(h-text_h)/2"),
}

POS_FALLBACK = ("(w*0.05)", "(h-text_h-h*0.05)")


def _esc(t: str) -> str:
    return t.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-").replace(",", "\\,")


def _slide_in_x(x_pos_expr: str, appear: float, slide_dur: float = 0.3, from_side: str = "left") -> str:
    if from_side == "left":
        return (
            f"if(lt(t\\,{appear}+{slide_dur})\\,"
            f"(-text_w-20)+(w+text_w+20)*(t-{appear})/{slide_dur}\\,"
            f"{x_pos_expr})"
        )
    elif from_side == "right":
        return (
            f"if(lt(t\\,{appear}+{slide_dur})\\,"
            f"(w+20)-(w+text_w+20)*(t-{appear})/{slide_dur}\\,"
            f"{x_pos_expr})"
        )
    return x_pos_expr


def _fade_alpha(appear: float, fade_dur: float, disappear: float) -> str:
    return (
        f"if(lt(t\\,{appear})\\,0\\,"
        f"if(lt(t\\,{appear}+{fade_dur})\\,(t-{appear})/{fade_dur}\\,"
        f"if(lt(t\\,{disappear})\\,1\\,"
        f"if(lt(t\\,{disappear}+{fade_dur})\\,1-(t-{disappear})/{fade_dur}\\,0))))"
    )


def animate_callout_box(text: str, appear: float, duration: float,
                        position: str = "bottom-left",
                        color: str = BRAND_TEAL,
                        fontsize: int = 18,
                        box_bg: str = "black@0.6",
                        slide_from: str = "left") -> list[str]:
    """Animated callout box: slides in from side, holds, slides out."""
    escaped = _esc(text)
    x_key, y_key = POSITIONS.get(position, POS_FALLBACK)
    x_expr = _slide_in_x(x_key, appear, 0.3, slide_from)
    disappear = appear + duration
    fade_out_start = disappear
    full_end = fade_out_start + 0.3
    enable = f"between(t\\,{appear}\\,{full_end})"

    filters = []
    filters.append(
        f"drawtext=text='{escaped}':fontsize={fontsize}:fontcolor={color}:"
        f"box=1:boxcolor={box_bg}:boxborderw=8:"
        f"x={x_expr}:y={y_key}:"
        f"enable='{enable}':"
        f"fontfile={FONT}"
    )
    return filters


def animate_step_counter(step_num: int, text: str, appear: float,
                         duration: float, total_steps: int = 0,
                         color: str = BRAND_ORANGE,
                         fontsize: int = 20) -> list[str]:
    """Numbered step indicator: [1/3] Text appears with circle + number."""
    escaped = _esc(text)
    label = f"[{step_num}/{total_steps}]" if total_steps else f"[{step_num}]"
    disappear = appear + duration
    full_end = disappear + 0.3
    enable = f"between(t\\,{appear}\\,{full_end})"

    label_offset = len(label) * (fontsize * 0.6)
    filters = []
    filters.append(
        f"drawtext=text='{label}':fontsize={fontsize}:fontcolor={BRAND_WHITE}:"
        f"box=1:boxcolor={color}@0.9:boxborderw=6:"
        f"x=w*0.03:y=h*0.12:"
        f"enable='{enable}':fontfile={FONT}"
    )
    filters.append(
        f"drawtext=text='{escaped}':fontsize={fontsize - 2}:fontcolor={BRAND_WHITE}:"
        f"x=w*0.03+{label_offset}:y=h*0.12:"
        f"enable='{enable}':fontfile={FONT}"
    )
    return filters


def animate_definition(term: str, definition: str, appear: float,
                       duration: float, position: str = "top-center") -> list[str]:
    """Definition popup: term in bold on one line, definition below."""
    escaped_term = _esc(term)
    escaped_def = _esc(definition)
    disappear = appear + duration
    full_end = disappear + 0.3
    enable = f"between(t\\,{appear}\\,{full_end})"

    filters = []
    filters.append(
        f"drawtext=text='{escaped_term}':fontsize=22:fontcolor={BRAND_TEAL}:"
        f"box=1:boxcolor=black@0.7:boxborderw=6:"
        f"x=(w-text_w)/2:y=h*0.05:"
        f"enable='{enable}':fontfile={FONT_BOLD}"
    )
    filters.append(
        f"drawtext=text='{escaped_def}':fontsize=16:fontcolor={BRAND_WHITE}:"
        f"x=(w-text_w)/2:y=h*0.05+28:"
        f"enable='{enable}':fontfile={FONT}"
    )
    return filters


def animate_arrow(direction: str = "down", appear: float = 0,
                  duration: float = 2.0, position: str = "center",
                    color: str = BRAND_ORANGE) -> list[str]:
    """Arrow pointer using unicode arrow character."""
    arrow_char = {"up": "\u2191", "down": "\u2193", "left": "\u2190",
                  "right": "\u2192", "ne": "\u2197", "nw": "\u2196",
                  "se": "\u2198", "sw": "\u2199"}.get(direction, "\u2193")
    disappear = appear + duration
    enable = f"between(t\\,{appear}\\,{disappear})"
    x_key, y_key = POSITIONS.get(position, POS_FALLBACK)

    return [
        f"drawtext=text='{arrow_char}':fontsize=48:fontcolor={color}:"
        f"x={x_key}:y={y_key}:"
        f"enable='{enable}':fontfile={FONT}"
    ]


def animate_highlight_box(appear: float, duration: float,
                           position: str = "center",
                           color: str = BRAND_TEAL,
                           width_pct: float = 0.3,
                           height_pct: float = 0.2) -> list[str]:
    """Pulsing highlight box around a region of the frame."""
    disappear = appear + duration
    enable = f"between(t\\,{appear}\\,{disappear})"
    bx = f"(w-w*{width_pct})/2"
    by = f"(h-h*{height_pct})/2"
    bw = f"w*{width_pct}"
    bh = f"h*{height_pct}"

    return [
        f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color={color}@0.15:t=fill:"
        f"enable='{enable}'"
    ]


def animate_counter(label: str, start_val: float = 0, end_val: float = 100,
                    appear: float = 0, duration: float = 3.0,
                    position: str = "center",
                    color: str = BRAND_ORANGE) -> list[str]:
    """Animated counting number that ticks up from start_val to end_val."""
    escaped_label = _esc(label)
    disappear = appear + duration
    enable = f"between(t\\,{appear}\\,{disappear})"

    speed = (end_val - start_val) / duration if duration > 0 else 0
    x_key, y_key = POSITIONS.get(position, POS_FALLBACK)

    filters = []
    if label:
        filters.append(
            f"drawtext=text='{escaped_label}':fontsize=20:fontcolor={BRAND_WHITE}:"
            f"x={x_key}:y={y_key.replace('text_h', '0')}-30:"
            f"enable='{enable}':fontfile={FONT}"
        )
    value_expr = (
        f"if(lt(t\\,{appear})\\,{start_val}\\,"
        f"if(lt(t\\,{disappear})\\,"
        f"{start_val}+(t-{appear})*{speed}\\,{end_val}))"
    )
    filters.append(
        f"drawtext=text='%{{expr_int_format:{value_expr}}}':fontsize=48:fontcolor={color}:"
        f"x={x_key}:y={y_key}:"
        f"enable='{enable}':fontfile={FONT_BOLD}"
    )
    return filters


def render_scene_annotations(scene: dict, timeline_start: float) -> list[str]:
    """Render all annotations for a single scene, returning ffmpeg vf strings."""
    filters = []
    annotations = scene.get("annotations", [])

    for ann in annotations:
        ann_type = ann.get("type", "callout")
        appear = timeline_start + ann.get("timing_offset", 0)
        dur = ann.get("duration", 3.0)
        pos = ann.get("position", "bottom-left")
        color = ann.get("color", BRAND_TEAL)
        fs = ann.get("fontsize", 18)
        text = ann.get("text", "")

        if ann_type == "callout":
            filters.extend(animate_callout_box(text, appear, dur, pos, color, fs))
        elif ann_type == "step":
            total = ann.get("total", 0)
            step = ann.get("step", 1)
            filters.extend(animate_step_counter(step, text, appear, dur, total, color))
        elif ann_type == "definition":
            def_text = ann.get("definition", "")
            if def_text:
                filters.extend(animate_definition(text, def_text, appear, dur, pos))
        elif ann_type == "arrow":
            filters.extend(animate_arrow(ann.get("direction", "down"), appear, dur, pos, color))
        elif ann_type == "highlight":
            filters.extend(animate_highlight_box(appear, dur, pos, color,
                                                  ann.get("width_pct", 0.3),
                                                  ann.get("height_pct", 0.2)))
        elif ann_type == "counter":
            filters.extend(animate_counter(text, ann.get("start", 0), ann.get("end", 100),
                                           appear, dur, pos, color))
    return filters


def build_annotation_filters(scenes: list[dict], clips: list[dict]) -> list[str]:
    """Build all annotation vf strings for a complete video."""
    filters = []
    for i, scene in enumerate(scenes):
        ts = sum(c.get("duration", 8.0) for c in clips[:i]) if i < len(clips) else 0
        filters.extend(render_scene_annotations(scene, ts))
    return filters
