import logging
import re

logger = logging.getLogger(__name__)

MANIM_SKELETON = '''from manim import *
import numpy as np
import json
config.disable_caching = True
config.verbosity = "WARNING"

DURATION = {duration}

class GeneratedScene(Scene):
    def construct(self):
        # {title}
        # {description}

        title_text = Text("{title}", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)

        # === CUSTOM SCENE CONTENT ===

        # Available: Text, Circle, Square, Rectangle, RoundedRectangle, VGroup,
        #   Line, Arrow, Dot, Polygon, RegularPolygon, Arc, NumberPlane, Axes,
        #   MathTex, Tex, SurroundingRectangle
        # Animations: Write, Create, FadeIn, FadeOut, Transform,
        #   ReplacementTransform, Rotate, ScaleInPlace, Indicate
        # Colors: WHITE, BLACK, RED, GREEN, BLUE, YELLOW, PURPLE, ORANGE, PINK,
        #   GRAY, BLUE_D, BLUE_C, GREEN_D, GREEN_C, YELLOW_C, YELLOW_D

        # --- YOUR CODE HERE ---

        # --- END OF YOUR CODE ---

        remaining = max(0, DURATION - self.time)
        if remaining > 0:
            self.wait(remaining)
'''

SYSTEM_PROMPT = """You are a Manim animation expert. Generate valid Python code for ManimCE (v0.20.x).

RULES:
1. Output ONLY valid Python code — no markdown fences, no explanations, no extra text
2. The class MUST inherit from Scene or ThreeDScene
3. Include the construct(self) method with all animation logic
4. Add DURATION = <N> at module level (after imports)
5. End construct() with the duration enforcement block:
   remaining = max(0, DURATION - self.time)
   if remaining > 0:
       self.wait(remaining)
6. All self.play() calls should include run_time=N to control duration
7. Available imports: Manim, numpy, json — use from manim import *
8. Do NOT use os.system, subprocess, eval, exec, __import__ — these are blocked
9. Use color constants (WHITE, BLUE, YELLOW, etc.) or hex strings like "#FF6B6B"
10. Make scenes visually engaging with multiple colors, shapes, and smooth animations"""


def _build_generation_prompt(
    description: str,
    title: str,
    duration: float,
    scene_type: str,
    similar_examples: list[dict],
    errors: list[str] | None = None,
) -> str:
    examples_text = ""
    for i, ex in enumerate(similar_examples[:2]):
        code_snippet = (ex.get("code") or "")[:1200]
        ex_type = ex.get("metadata", {}).get("scene_type", "unknown")
        if code_snippet:
            examples_text += f"\n--- Similar scene {i+1} (type: {ex_type}) ---\n{code_snippet}\n"

    safe_title = re.sub(r'[^a-zA-Z0-9 .,!?\-]', '', title)
    prompt = f"""Generate a Manim Scene for this educational concept:

TITLE: {title}
DESCRIPTION: {description}
TARGET DURATION: {duration:.1f} seconds
SCENE TYPE: {scene_type}

Use the skeleton structure shown below. Keep the imports, config, DURATION constant, and the duration enforcement block at the end intact. Fill in the animation code between the markers.

Skeleton:
{MANIM_SKELETON.format(duration=duration, title=safe_title, description=description[:200])}"""

    if examples_text:
        prompt += f"\n\nStudy these examples of successful Manim code for similar scenes:\n{examples_text}\n\nGenerate a new scene that follows the same patterns but visualizes the new concept above."

    if errors:
        prompt += f"\n\n=== FIX THESE ERRORS ===\n" + "\n".join(errors[:5]) + "\n\nRewrite the ENTIRE code with these errors fixed."

    return prompt


def _extract_code(raw: str) -> str | None:
    code = raw.strip()
    match = re.search(r"```python\s*\n(.*?)```", code, re.DOTALL)
    if match:
        code = match.group(1).strip()
    match = re.search(r"```\s*\n(.*?)```", code, re.DOTALL)
    if match:
        code = match.group(1).strip()
    return code if (len(code) > 50 and ("class " in code) and ("def construct" in code)) else None


def _ensure_duration_block(code: str, duration: float) -> str:
    if "DURATION =" not in code:
        code = code.rstrip() + f'\n\nDURATION = {duration}\n'
    if "remaining = max(0, DURATION - self.time)" not in code:
        code = code.rstrip() + """
        remaining = max(0, DURATION - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return code


def generate_manim_code(
    description: str,
    title: str,
    duration: float,
    scene_type: str,
    similar_examples: list[dict],
    errors: list[str] | None = None,
) -> str | None:
    from utils.llm_client import generate_completion

    prompt = _build_generation_prompt(description, title, duration, scene_type, similar_examples, errors)

    try:
        raw = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3 if not errors else 0.2,
            max_tokens=4000,
            caller_id="manim_code_gen",
        )
    except Exception as e:
        logger.warning(f"[ManimGen] LLM call failed: {e}")
        return None

    code = _extract_code(raw) or raw.strip()
    if not code or len(code) < 100:
        logger.warning("[ManimGen] Generated code too short or empty")
        return None

    code = _ensure_duration_block(code, duration)

    if not errors:
        logger.info(f"[ManimGen] Generated {len(code)} chars of Manim code")
    else:
        logger.info(f"[ManimGen] Regenerated {len(code)} chars after {len(errors)} error(s)")

    return code
