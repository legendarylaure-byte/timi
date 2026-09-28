"""ManimCE code generator — LLM writes scenes, this module manages the prompt."""
import re
import logging
from utils.llm_helper import get_llm

logger = logging.getLogger(__name__)

_SYSTEM = """You are a ManimCE v0.21 code generator for educational tech videos.

RULES — every one is mandatory:
- Use `from manim import *` as the ONLY import. If you need Code, add `from manim import Code` on the NEXT line.
- NEVER use MathTex, Tex, TexMath, or any LaTeX class — use ONLY Text() for all text.
- Class name MUST be exactly: `class DiagScene(Scene)`
- Set `self.camera.background_color = "#1B1212"` as first line in construct().
- Brand palette: purple #9B4DFF, violet #6641FC, pink #F856A5, orange #FF8133, light orange #FFB05F, white #FFFFFF, dark #1B1212. NEVER use teal or any other pre-rebrand colour.
- Sum of all run_time values MUST equal the requested duration (±1s).
- NEVER animate raw attributes (obj.height.animate(…)). Use Create, FadeIn, GrowFromEdge, Transform, or .animate.set_*() that returns a mobject.
- BarChart uses x_length/y_length (NOT height/width). MObject subclasses generally do NOT accept height=/width= — use scale_to_fit_width()/scale_to_fit_height() to resize.
- font_size is set via Text(font_size=..., color=...) or Code(paragraph_config={"font_size": ...}); most objects resize via scale_to_fit_width().
- For code snippets: use Code(code_string=..., language="python", background="rectangle", formatter_style="monokai", add_line_numbers=False).
- Labels MUST be the exact literal strings provided — no abbreviations or rewording.
- Output ONLY a ```python ... ``` markdown block — no text outside it.
- Keep scenes visually clean: one concept per scene, clear spatial layout, readable font_size (≥28)."""



def generate_manim_code(task: dict) -> str | None:
    """Generate Manim scene code. Returns code string or None."""
    llm = get_llm(temperature=0.2, max_tokens=8000, agent_id="manim_codegen")

    diagram = task.get("diagram")
    diagram_hint = ""
    if isinstance(diagram, dict):
        diagram_hint = (
            f"\nDiagram: type={diagram.get('type', '')}, "
            f"items={diagram.get('items', [])}, "
            f"blocks={diagram.get('blocks', [])}, "
            f"layer_sizes={diagram.get('layer_sizes', [])}"
        )

    user = (
        f"Create a Manim scene for this educational video segment.\n\n"
        f"Title: {task.get('title', 'AI Concept')}\n"
        f"Duration: {task.get('duration', 8)}s  (sum run_time values to this)\n"
        f"Resolution: {task.get('width', 1920)}x{task.get('height', 1080)}\n"
        f"Narration (what viewer hears): {task.get('narration', '')[:400]}\n"
        f"Description: {task.get('description', '')}{diagram_hint}\n\n"
        f"Output a complete DiagScene class that visually illustrates the narration."
    )
    msgs = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
    try:
        out = llm.call(msgs)
    except Exception as e:
        logger.warning(f"[ManimAgent] LLM call failed: {e}")
        return None

    code = _extract_code(out)
    if code:
        code = re.sub(r"class\s+\w+\s*\(", "class DiagScene(", code, count=1)
    return code


def fix_manim_code(code: str, tb: str) -> str | None:
    """Fix broken Manim code using traceback. Returns fixed code or None."""
    llm = get_llm(temperature=0.15, max_tokens=8000, agent_id="manim_codegen")
    user = (
        f"The following Manim code fails to render. Fix the bug.\n\n"
        f"ERROR:\n{tb[:2500]}\n\n"
        f"BROKEN CODE:\n```python\n{code}\n```\n\n"
        f"Return ONLY the corrected ```python ... ``` block. "
        f"Keep class name DiagScene. Keep all Text() constraints."
    )
    msgs = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
    try:
        out = llm.call(msgs)
    except Exception as e:
        logger.warning(f"[ManimAgent] fix LLM call failed: {e}")
        return None
    fixed = _extract_code(out)
    if fixed:
        fixed = re.sub(r"class\s+\w+\s*\(", "class DiagScene(", fixed, count=1)
    return fixed


def _extract_code(response: str) -> str | None:
    """Pull ```python ... ``` from LLM response."""
    m = re.search(r"```python\s*\n(.*?)```", response, re.S)
    if m:
        code = m.group(1).strip()
        if "DiagScene" in code and "manim" in code:
            return code
    m = re.search(r"```\s*\n(.*?)```", response, re.S)
    if m:
        code = m.group(1).strip()
        if "DiagScene" in code and "manim" in code:
            return code
    return None
