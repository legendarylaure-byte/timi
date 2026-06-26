import json
import re
from utils.groq_client import generate_completion
from utils.firebase_status import log_activity
from utils.scene_schema import ValidationError

SYSTEM_PROMPT = """You are a scene director for tech/AI educational videos. Convert the given script into structured scene descriptions.

Return ONLY a valid JSON array of scene objects. Each scene object has this exact structure:

{
  "background": "solid_black|solid_white|solid_indigo|solid_slate|gradient_dark_tech|gradient_blueprint|gradient_neon|gradient_corporate|gradient_minimal",
  "duration": 8.0,
  "asset_type": "STOCK_FOOTAGE|SCREEN_CAPTURE|DIAGRAM_ANIMATION|CODE_SNIPPET|STATIC_IMAGE",
  "asset_keywords": ["keyword1", "keyword2"],
  "text": [
    {
      "text": "Spoken narration text shown on screen",
      "style": "narration|title|emphasis|caption",
      "position": "center|top|bottom|left|right"
    }
  ],
  "transition": "cut|fade|dissolve|slide_left|slide_right",
  "camera": {
    "zoom": 1.0,
    "pan_x": 0,
    "pan_y": 0
  },
  "music_mood": "focused|energetic|cinematic|ambient|modern|uplifting"
}

RULES:
- Each scene should be 5-12 seconds
- Use asset_type to specify what visual content to show
- asset_keywords should describe what to search for or render
- Text should be short phrases (3-8 words), not full sentences
- Background should match the scene mood
- camera.zoom of 1.0 means no zoom, >1 zooms in
- Include text overlays for key spoken phrases
- Match asset_type to the technical content:
  - STOCK_FOOTAGE for general concepts/demonstrations
  - SCREEN_CAPTURE for tool tutorials and code walkthroughs
  - DIAGRAM_ANIMATION for explaining architectures and processes
  - CODE_SNIPPET for showing code examples
  - STATIC_IMAGE for reference images and diagrams

Generate scenes that follow the narrative arc of the script. Maintain visual continuity across consecutive scenes."""  # noqa: E501


def parse_script_to_scenes(
    script_text: str, title: str = "", category: str = "",
    format_type: str = "shorts", storyboard_text: str = ""
) -> list[dict]:
    log_activity("scene_parser", f"Parsing script: {title}", "info")
    print(f"[SCENE_PARSER] Parsing script for '{title}' ({format_type})")

    scenes = _llm_scene_parse(script_text, title, category, format_type, storyboard_text)
    if scenes:
        return scenes

    scenes = _rule_based_parse(script_text, storyboard_text, format_type, title)
    if scenes:
        print(f"[SCENE_PARSER] Rule-based parse produced {len(scenes)} scenes")
        return scenes

    scenes = _minimal_fallback(title, category, format_type)
    print(f"[SCENE_PARSER] Using minimal fallback ({len(scenes)} scenes)")
    return scenes


def _llm_scene_parse(
    script_text: str, title: str, category: str, format_type: str, storyboard_text: str
) -> list[dict] | None:
    if len(script_text) > 6000:
        script_text = script_text[:6000] + "\n...[truncated]"

    prompt = f"""Convert this tech/AI educational video script into structured scenes with asset types.

Title: {title}
Category: {category}
Format: {format_type}

Script:
{script_text}

Storyboard:
{storyboard_text[:3000] if storyboard_text else "N/A"}

Important: Choose asset types that fit the category:
- {category} related assets: {_get_suggested_assets(category)}

Return ONLY valid JSON array of scene objects."""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=3000,
        )

        scenes = _extract_json_array(response)
        if not scenes:
            print("[SCENE_PARSER] LLM returned no valid JSON")
            return None

        validated = []
        for s in scenes:
            try:
                from utils.scene_schema import validate_scene
                validated.append(validate_scene(s, len(validated)))
            except ValidationError as e:
                print(f"[SCENE_PARSER] Skipping invalid scene: {e}")
                continue

        if validated:
            print(f"[SCENE_PARSER] LLM parsed {len(validated)} scenes successfully")
            return _adjust_scenes_for_format(validated, format_type)

    except Exception as e:
        print(f"[SCENE_PARSER] LLM parse failed: {e}")

    return None


def _rule_based_parse(script_text: str, storyboard_text: str, format_type: str, title: str = "") -> list[dict]:
    scenes = []

    combined = script_text + "\n" + (storyboard_text or "")

    scene_blocks = re.split(r'(?:^|\n)(?:#{1,3}\s*)?Scene\s+\d+[\s:.-]*', combined, flags=re.IGNORECASE | re.MULTILINE)
    scene_blocks = [s.strip() for s in scene_blocks if s.strip()]

    if len(scene_blocks) < 2:
        scene_blocks = re.split(r'\n\s*\n\s*(?=[A-Z][a-z]+)', combined)
        scene_blocks = [s.strip() for s in scene_blocks if len(s.strip()) > 50]

    if len(scene_blocks) < 1:
        scene_blocks = [combined]

    word_count = len(script_text.split())
    target_scene_count = 6 if format_type == "shorts" else 12
    target_scene_count = min(target_scene_count, max(1, word_count // 20))

    while len(scene_blocks) < target_scene_count:
        scene_blocks.append(scene_blocks[-1] if scene_blocks else combined)

    scene_blocks = scene_blocks[:target_scene_count]

    for i, block in enumerate(scene_blocks):
        duration = _estimate_scene_duration(block, format_type, len(scene_blocks))
        background = _infer_background(block)
        asset_type = _infer_asset_type(block)
        asset_keywords = _infer_keywords(block, title)
        text = _infer_text(block)
        effects = _infer_effects(block, i, len(scene_blocks))
        transition = _infer_transition(i, len(scene_blocks))

        scene = {
            "background": background,
            "duration": duration,
            "asset_type": asset_type,
            "asset_keywords": asset_keywords,
            "text": text,
            "effects": effects,
            "transition": transition,
            "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "music_mood": _infer_mood(block),
        }

        try:
            from utils.scene_schema import validate_scene
            scenes.append(validate_scene(scene, i))
        except ValidationError as e:
            print(f"[SCENE_PARSER] Rule-based validation failed for scene {i}: {e}")
            scenes.append(_default_scene(i))

    return scenes if len(scenes) >= 2 else []


def _minimal_fallback(title: str, category: str, format_type: str) -> list[dict]:
    scene_count = 4 if format_type == "shorts" else 8
    scenes = []
    for i in range(scene_count):
        scenes.append({
            "background": "stock_footage",
            "duration": 6.0 if format_type == "shorts" else 10.0,
            "asset_type": "STOCK_FOOTAGE",
            "asset_keywords": ["technology", title[:30]],
            "text": [{"text": title[:50], "style": "title", "position": "center"}],
            "transition": "fade" if i > 0 else "cut",
            "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "music_mood": "focused",
        })
    return scenes


def _extract_json_array(text: str) -> list | None:
    try:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            raw = text[start:end]
            result = json.loads(raw)
            if isinstance(result, list):
                return result
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            raw = text[start:end]
            wrapped = json.loads(raw)
            if isinstance(wrapped, dict) and "scenes" in wrapped:
                return wrapped["scenes"]
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _estimate_scene_duration(block: str, format_type: str, total_scenes: int) -> float:
    word_count = len(block.split())
    if format_type == "shorts":
        total_duration = 60.0
    else:
        total_duration = 480.0
    per_scene = total_duration / max(total_scenes, 1)
    per_scene = max(per_scene, 4.0)
    if word_count < 10:
        per_scene = min(per_scene, 5.0)
    return round(per_scene, 1)


def _infer_background(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["server", "data center", "cloud", "network", "cluster", "gpu"]):
        return "gradient_dark_tech"
    if any(w in text_lower for w in ["code", "algorithm", "program", "function", "script", "syntax"]):
        return "gradient_blueprint"
    if any(w in text_lower for w in ["neural", "deep learning", "layer", "architecture", "transformer"]):
        return "gradient_neon"
    if any(w in text_lower for w in ["tutorial", "guide", "how to", "step", "build", "setup"]):
        return "gradient_corporate"
    if any(w in text_lower for w in ["future", "innovation", "breakthrough", "next gen", "vision"]):
        return "gradient_dark_tech"
    if any(w in text_lower for w in ["simple", "beginner", "basics", "fundamentals", "overview"]):
        return "gradient_minimal"
    if any(w in text_lower for w in ["training", "benchmark", "performance", "accuracy", "loss"]):
        return "solid_slate"
    if any(w in text_lower for w in ["attention", "qkv", "embedding", "positional"]):
        return "gradient_neon"
    return "solid_black"


def _infer_asset_type(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["code", "function", "implementation", "syntax", "import", "class", "def "]):  # noqa: E501
        return "CODE_SNIPPET"
    if any(w in text_lower for w in ["tutorial", "walkthrough", "click", "install", "terminal", "command"]):
        return "SCREEN_CAPTURE"
    if any(w in text_lower for w in ["architecture", "diagram", "network", "layer", "flow", "neural", "transformer", "attention", "algorithm", "process"]):  # noqa: E501
        return "DIAGRAM_ANIMATION"
    if any(w in text_lower for w in ["chart", "graph", "comparison", "benchmark", "stat", "table"]):
        return "STATIC_IMAGE"
    return "STOCK_FOOTAGE"


def _infer_keywords(text: str, title: str = "") -> list[str]:
    text_lower = text.lower()
    tech_terms = ["AI", "machine learning", "deep learning", "neural network", "transformer",
                  "GPT", "LLM", "data", "algorithm", "code", "GPU", "training", "inference",
                  "automation", "cloud", "API", "model", "embedding", "attention",
                  "token", "pipeline", "architecture", "framework", "PyTorch", "TensorFlow"]
    found = [term for term in tech_terms if term.lower() in text_lower]
    if title:
        found.insert(0, title[:40])
    return found[:5] if found else ["technology", title[:30] if title else "tech"]


def _infer_text(text: str) -> list[dict]:
    lines = text.strip().split("\n")
    texts = []
    for line in lines:
        cleaned = re.sub(r'^[\s*#\-]+', '', line).strip()
        cleaned = re.sub(r'^Narrator\s*:\s*', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'^[A-Z][a-z]+\s*:\s*', '', cleaned).strip()
        cleaned = re.sub(r'[<>]', '', cleaned)

        if cleaned and 15 < len(cleaned) < 100 and not any(
            kw in cleaned.lower() for kw in ["scene", "camera", "angle", "color palette", "background", "visual"]
        ):
            texts.append({
                "text": cleaned[:80],
                "style": "dialogue" if "?" in cleaned or "!" in cleaned else "narration",
                "position": "bottom",
            })
            if len(texts) >= 2:
                break

    return texts


def _infer_effects(text: str, scene_index: int, total_scenes: int) -> list[str]:
    effects = []
    if scene_index == 0:
        effects.append("fade_in")
    if scene_index == total_scenes - 1:
        effects.append("fade_out")
    if not effects:
        effects.append("none")
    return effects[:2]


def _infer_transition(scene_index: int, total_scenes: int) -> str:
    if scene_index == 0:
        return "cut"
    if scene_index == total_scenes - 1:
        return "fade"
    transitions = ["dissolve", "slide_right", "fade", "dissolve", "slide_left"]
    return transitions[scene_index % len(transitions)]


def _infer_mood(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["breakthrough", "revolutionary", "amazing", "incredible"]):
        return "energetic"
    if any(w in text_lower for w in ["deep", "complex", "architecture", "theory", "analysis"]):
        return "focused"
    if any(w in text_lower for w in ["tutorial", "guide", "how to", "step", "build"]):
        return "modern"
    if any(w in text_lower for w in ["future", "vision", "imagine", "next gen", "breakthrough"]):
        return "cinematic"
    if any(w in text_lower for w in ["simple", "easy", "beginner", "basics"]):
        return "uplifting"
    return "focused"


def _get_suggested_assets(category: str) -> str:
    mapping = {
        "AI Explained": "STOCK_FOOTAGE (tech concepts, AI visuals), DIAGRAM_ANIMATION (neural networks)",
        "Deep Tech": "DIAGRAM_ANIMATION (architectures), STOCK_FOOTAGE (scientific concepts)",
        "Paper Breakdowns": "DIAGRAM_ANIMATION (paper figures), CODE_SNIPPET (implementations)",
        "Tool Tutorials": "SCREEN_CAPTURE (tool walkthrough), CODE_SNIPPET (commands)",
        "Industry Analysis": "STOCK_FOOTAGE (business/tech), STATIC_IMAGE (charts, graphs)",
        "Code & Build": "CODE_SNIPPET (code), SCREEN_CAPTURE (build process)",
        "AI News": "STOCK_FOOTAGE (news style), STATIC_IMAGE (logos, products)",
        "Career & Learning": "STOCK_FOOTAGE (learning), SCREEN_CAPTURE (resources)",
    }
    return mapping.get(category, "STOCK_FOOTAGE (tech visuals), DIAGRAM_ANIMATION (explainers)")


def _default_scene(index: int) -> dict:
    return {
        "background": "stock_footage",
        "duration": 6.0,
        "asset_type": "STOCK_FOOTAGE",
        "asset_keywords": ["technology", "abstract"],
        "text": [],
        "transition": "cut" if index == 0 else "dissolve",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "focused",
    }


def _adjust_scenes_for_format(scenes: list[dict], format_type: str) -> list[dict]:
    if format_type == "shorts":
        max_duration = sum(s.get("duration", 6) for s in scenes)
        if max_duration > 60:
            scale = 60 / max_duration
            for s in scenes:
                s["duration"] = round(max(s.get("duration", 6) * scale, 3), 1)
    return scenes
