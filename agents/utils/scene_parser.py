import json
import re
from dataclasses import dataclass, field
from typing import Optional
from utils.llm_client import generate_completion
from utils.firebase_status import log_activity
from utils.scene_schema import ValidationError


@dataclass
class SceneState:
    camera_angle: str = ""
    lighting: str = ""
    color_palette: str = "teal and dark gray"
    dominant_colors: list[str] = field(default_factory=lambda: ["#1e1e1e", "#00CCCC"])

SYSTEM_PROMPT = """You are a scene director for tech/AI educational videos. Convert the given script into structured scene descriptions.

Return ONLY a valid JSON array of scene objects. Each scene object has this exact structure:

{
    "background": "solid_black|solid_white|solid_indigo|solid_slate|brand_dark|gradient_dark_tech|gradient_blueprint|gradient_neon|gradient_corporate|gradient_minimal",
  "duration": 8.0,
  "render_type": "stock|manim|code",
  "asset_type": "STOCK_FOOTAGE|SCREEN_CAPTURE|DIAGRAM_ANIMATION|CODE_SNIPPET|STATIC_IMAGE",
  "asset_keywords": ["keyword1", "keyword2"],
  "ltx_prompt": "Describe the scene in 2-3 vivid sentences optimized for AI video generation. Include camera angle, lighting, composition, colors, and motion. Be specific.",
  "text": [
    {
      "text": "Spoken narration text shown on screen",
      "style": "narration|title|emphasis|caption",
      "position": "center|top|bottom|left|right"
    }
  ],
  "transition": "cut|fade|dissolve|slide_left|slide_right|zoom|circle_open|circle_close|pixelize|wipe_left|wipe_right|smooth_left|smooth_right|fade_gradual",
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
- render_type: "stock" for cinematic/b-roll, "manim" for diagrams/math/concept animations, "code" for code snippets
- ltx_prompt is CRITICAL: Write a detailed 2-3 sentence visual description optimized for text-to-video AI. Reference SPECIFIC visual elements mentioned in the script's NARRATION — if the narration talks about GPUs, describe GPU chips and data pathways; if it mentions training data, show data streams and processing pipelines. Never use generic descriptions. Include: camera angle (close-up, wide, tracking, dolly, over-the-shoulder, top-down), lighting (neon glow, soft diffused, dramatic side, volumetric, rim light), composition (subject placement, depth layers), colors, and motion. Example: "Close-up of futuristic circuit board with glowing neon blue pathways, dramatic side lighting casting long shadows, camera slowly pulling back to reveal a glowing central processor chip, sparks of light traveling along the circuits, deep teal and purple color palette, cinematic 24fps quality"
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
    format_type: str = "shorts", storyboard_text: str = "",
    max_duration: int = None
) -> list[dict]:
    log_activity("scene_parser", f"Parsing script: {title}", "info")
    print(f"[SCENE_PARSER] Parsing script for '{title}' ({format_type})")

    scenes = _llm_scene_parse(script_text, title, category, format_type, storyboard_text, max_duration)
    if scenes:
        return scenes

    scenes = _rule_based_parse(script_text, storyboard_text, format_type, title, max_duration)
    if scenes:
        print(f"[SCENE_PARSER] Rule-based parse produced {len(scenes)} scenes")
        return scenes

    scenes = _minimal_fallback(title, category, format_type)
    print(f"[SCENE_PARSER] Using minimal fallback ({len(scenes)} scenes)")
    return scenes


def _llm_scene_parse(
    script_text: str, title: str, category: str, format_type: str, storyboard_text: str,
    max_duration: int = None
) -> list[dict] | None:
    if len(script_text) > 6000:
        script_text = script_text[:6000] + "\n...[truncated]"

    target_hint = ""
    if max_duration:
        if format_type == "long":
            target_hint = f"\nCRITICAL: The TOTAL duration of ALL scenes combined must be approximately {max_duration} seconds (sum of all 'duration' fields). Generate enough scenes to fill this time — typically 10-15 scenes for long-form, each 12-20 seconds."
        else:
            target_hint = f"\nAim for total duration around {max_duration} seconds across all scenes."

    prompt = f"""Convert this tech/AI educational video script into structured scenes with asset types. CRITICAL: Each scene MUST include a vivid "ltx_prompt" field — a 2-3 sentence visual description optimized for AI text-to-video generation. Include camera angle, lighting, composition, colors, and motion. The ltx_prompt MUST reference SPECIFIC visual elements from the NARRATION text — if the narration mentions GPUs, describe GPU chips and data pathways; if it mentions training, show loss curves and gradient flow. Never use generic descriptions. Also include a "render_type" field: "stock" for cinematic/b-roll footage, "manim" for diagrams and concept animations, "code" for code snippets.

Read the VISUAL lines from the script/storyboard — they contain [MANIM], [WAN2.1], or [CODE] tags. Use these to set render_type: [MANIM] → "manim", [CODE] → "code", [WAN2.1] or no tag → "stock".

Title: {title}
Category: {category}
Format: {format_type}{target_hint}

Script:
{script_text}

Storyboard:
{storyboard_text[:3000] if storyboard_text else "N/A"}

Important: Choose asset types that fit the category:
- {category} related assets: {_get_suggested_assets(category)}

CRITICAL for visual continuity: Each scene's ltx_prompt MUST reference the PREVIOUS scene's visual state. Maintain consistent color palette (dark teal/cyan/neon), lighting, and camera flow across adjacent scenes. Avoid sudden jumps in camera angle or lighting between consecutive scenes. If scene 1 ends on a close-up, scene 2 should start with a similar close-up slowly pulling back. This creates smooth visual storytelling.

The ltx_prompt is the most important field — it's what gets sent to the video generation AI. Make it specific, reference real objects and actions from the narration, and directly based on the VISUAL descriptions in the storyboard.

Return ONLY valid JSON array of scene objects."""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=8192,
        )

        scenes = _extract_json_array(response)
        if not scenes:
            print(f"[SCENE_PARSER] LLM returned no valid JSON (response len={len(response)})")
            print(f"[SCENE_PARSER] First 200 chars: {response[:200]}")
            print(f"[SCENE_PARSER] Last 200 chars: {response[-200:]}")
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
            return _adjust_scenes_for_format(validated, format_type, max_duration)

    except Exception as e:
        print(f"[SCENE_PARSER] LLM parse failed: {e}")

    return None


def _rule_based_parse(script_text: str, storyboard_text: str, format_type: str, title: str = "", max_duration: int = None) -> list[dict]:
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

    prev_state: Optional[SceneState] = None
    for i, block in enumerate(scene_blocks):
        duration = _estimate_scene_duration(block, format_type, len(scene_blocks), max_duration)
        background = _infer_background(block)
        asset_type = _infer_asset_type(block)
        asset_keywords = _infer_keywords(block, title)
        text = _infer_text(block)
        effects = _infer_effects(block, i, len(scene_blocks))
        transition = _infer_transition(i, len(scene_blocks), block)

        ltx_prompt, state = _infer_ltx_prompt(block, title, i, None, prev_state)
        prev_state = state

        scene = {
            "background": background,
            "duration": duration,
            "render_type": _infer_render_type(block),
            "asset_type": asset_type,
            "asset_keywords": asset_keywords,
            "ltx_prompt": ltx_prompt,
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
    try:
        from utils.json_utils import extract_json
        result = extract_json(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "scenes" in result:
            return result["scenes"]
    except Exception:
        pass
    return None


def _estimate_scene_duration(block: str, format_type: str, total_scenes: int, max_duration: int = None) -> float:
    word_count = len(block.split())
    if format_type == "shorts":
        total_seconds = float(max_duration) if max_duration else 60.0
    else:
        total_seconds = float(max_duration) if max_duration else 480.0
    per_scene = total_seconds / max(total_scenes, 1)
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


CAMERA_ANGLES = [
    "close-up shot with macro detail",
    "wide establishing shot",
    "smooth cinematic dolly moving forward",
    "over-the-shoulder angle",
    "top-down birds eye view",
    "low angle looking up",
    "tracking shot moving sideways",
    "aerial drone-style view",
    "Dutch angle tilted for drama",
    "reverse shot from behind subject",
]

LIGHTING_STYLES = [
    "dramatic neon side lighting",
    "soft cinematic volumetric lighting with god rays",
    "warm key light with cool fill",
    "rim lighting with dark ambient fill",
    "diffused overhead with soft shadows",
    "colorful LED strip lighting in cyan and magenta",
    "dramatic chiaroscuro high contrast",
    "cold blue ambient with warm accent light",
    "backlit silhouette with glowing edges",
    "natural soft window light style",
]


def _pick_camera_by_content(text_lower: str, keywords: list, scene_index: int) -> str:
    if any(w in text_lower for w in ["chip", "circuit", "processor", "silicon", "microchip", "transistor"]):
        return "extreme macro close-up with shallow depth of field"
    if any(w in text_lower for w in ["server", "data center", "warehouse", "cluster", "rack"]):
        return "wide establishing shot of large-scale infrastructure"
    if any(w in text_lower for w in ["neural", "network", "brain", "synapse", "layers"]):
        return "smooth cinematic dolly through interconnected layers"
    if any(w in text_lower for w in ["code", "terminal", "screen", "monitor", "algorithm"]):
        return "close-up tracking shot along glowing lines of code"
    if any(w in text_lower for w in ["training", "learning", "evolution", "growth"]):
        return "slow push-in revealing evolving patterns"
    if any(w in text_lower for w in ["data", "flow", "pipeline", "stream", "input", "output"]):
        return "tracking shot moving alongside flowing data streams"
    if any(w in text_lower for w in ["diagram", "graph", "chart", "architecture", "system"]):
        return "top-down birds eye view of structural diagram"
    return CAMERA_ANGLES[scene_index % len(CAMERA_ANGLES)]


def _pick_lighting_by_content(text_lower: str, mood: str, scene_index: int) -> str:
    mood_map = {
        "energetic": "bright dynamic LED lighting with rapid color shifts",
        "cinematic": "dramatic chiaroscuro with deep shadows and key light",
        "focused": "clean diffused overhead lighting for maximum clarity",
        "modern": "cool blue ambient with crisp white highlights",
        "uplifting": "warm golden hour style with soft fill light",
        "ambient": "soft volumetric lighting with gentle color gradients",
    }
    if mood in mood_map:
        return mood_map[mood]
    if any(w in text_lower for w in ["neon", "glow", "digital", "cyber", "hologram", "futuristic"]):
        return "colorful neon edge lighting in cyan and magenta"
    if any(w in text_lower for w in ["dark", "night", "shadow", "mystery", "deep"]):
        return "rim lighting with dark ambient fill and backlight"
    return LIGHTING_STYLES[scene_index % len(LIGHTING_STYLES)]


def _infer_render_type(text: str) -> str:
    m = re.search(r'\[(MANIM|CODE|WAN2\.1)\]', text, re.IGNORECASE)
    if m:
        tag = m.group(1).upper()
        if tag == "MANIM":
            return "manim"
        elif tag == "CODE":
            return "code"
    return "stock"


def _infer_ltx_prompt(text: str, title: str = "", scene_index: int = 0, scene: dict = None, prev_state: Optional[SceneState] = None) -> tuple[str, SceneState]:
    text_lower = text.lower()
    keywords = _infer_keywords(text, title)
    mood = scene.get("music_mood", "") if scene else ""

    if scene:
        cam = _pick_camera_by_content(text_lower, keywords, scene_index)
        lighting = _pick_lighting_by_content(text_lower, mood, scene_index)
    else:
        cam = CAMERA_ANGLES[scene_index % len(CAMERA_ANGLES)]
        lighting = LIGHTING_STYLES[(scene_index + len(keywords)) % len(LIGHTING_STYLES)]

    continuity_hint = ""
    if prev_state and prev_state.camera_angle:
        continuity_hint = f"continuing from previous {prev_state.camera_angle}, similar angle with slight drift, consistent lighting ({prev_state.lighting}), "
        if prev_state.dominant_colors:
            continuity_hint += f"maintaining color palette ({', '.join(prev_state.dominant_colors[:3])}), "
        if prev_state.color_palette:
            continuity_hint += f"consistent {prev_state.color_palette} aesthetic, "

    bg_hint = ""
    if scene:
        bg = scene.get("background", "")
        if bg in ("gradient_neon", "gradient_dark_tech"):
            bg_hint = "against a dark gradient with neon accents, "
        elif bg in ("gradient_blueprint",):
            bg_hint = "over a technical blueprint background, "
        elif bg in ("gradient_corporate", "gradient_minimal"):
            bg_hint = "on a clean professional background, "

    asset_hint = ""
    if scene:
        at = scene.get("asset_type", "")
        if at == "DIAGRAM_ANIMATION":
            asset_hint = "animated diagram elements with glowing connections, "
        elif at == "CODE_SNIPPET":
            asset_hint = "syntax-highlighted code on screen, "

    text_hint = ""
    if scene:
        texts = scene.get("text", [])
        if texts and isinstance(texts, list) and len(texts) > 0:
            first = texts[0].get("text", "") if isinstance(texts[0], dict) else ""
            if first:
                text_hint = f'showing "{first[:40]}" as text overlay, '

    transition_hint = ""
    if scene:
        trans = scene.get("transition", "")
        if trans == "slide_left":
            transition_hint = "subject positioned on right side for slide transition, "
        elif trans == "slide_right":
            transition_hint = "subject positioned on left side for slide transition, "
        elif trans == "fade":
            transition_hint = "slow fading edges for smooth transition, "
        elif trans == "zoom":
            transition_hint = "subject centered with subtle zoom for dramatic entrance, "
        elif trans == "circle_open":
            transition_hint = "subject framed centrally for circular reveal, "
        elif trans == "circle_close":
            transition_hint = "subject framed centrally for circular close, "
        elif trans == "pixelize":
            transition_hint = "subject with crisp edges for pixelation dissolution, "
        elif trans in ("wipe_left", "wipe_right", "wipe_up", "wipe_down"):
            transition_hint = "subject positioned with clear directional space for wipe transition, "

    visual_desc_hint = ""
    visual_match = re.search(r'VISUAL\s*:\s*(.+?)(?=\n|$)', text, re.IGNORECASE | re.DOTALL)
    if visual_match:
        visual_text = visual_match.group(1).strip()[:400]
        visual_text = re.sub(r'\[(MANIM|CODE|WAN2\.1)\]\s*', '', visual_text, flags=re.IGNORECASE)
        if visual_text and len(visual_text) > 10:
            visual_desc_hint = f"scene depicts {visual_text}, "

    narration_hint = ""
    narration_match = re.search(r'NARRATION\s*:\s*(.+?)(?=\n|$)', text, re.IGNORECASE | re.DOTALL)
    if narration_match:
        narration_text = narration_match.group(1).strip()[:200]
        if narration_text and len(narration_text) > 20:
            key_nouns = re.findall(r'\b[A-Z][a-z]{2,}\b', narration_text)
            key_terms = [w for w in key_nouns if w.lower() not in {'the', 'this', 'that', 'with', 'from', 'they', 'what', 'when', 'where', 'there', 'these', 'those'}]
            if key_terms:
                narration_hint = f"visualizing {', '.join(key_terms[:4])}, "

    prompt = f"Cinematic shot of {', '.join(keywords[:2])}, {keywords[-1] if len(keywords) > 2 else 'technology'} visualization, {continuity_hint}{visual_desc_hint}{narration_hint}{bg_hint}{asset_hint}{text_hint}{transition_hint}{cam}, {lighting}, rich colors, professional educational style, 24fps, high quality"  # noqa: E501

    color_terms = set()
    for term in text_lower.split():
        if term in ("teal", "cyan", "blue", "purple", "orange", "amber", "red", "green", "neon", "dark", "black", "white", "gray", "gold"):
            color_terms.add(term)
    if not color_terms:
        color_terms = {"teal", "dark"}

    state = SceneState(
        camera_angle=cam,
        lighting=lighting,
        color_palette=" and ".join(sorted(color_terms)[:3]) or "teal and dark",
        dominant_colors=["#1e1e1e", "#00CCCC"],
    )
    return prompt, state


def _infer_asset_type(text: str) -> str:
    m = re.search(r'ASSET_TYPE\s*:\s*(\w+)', text, re.IGNORECASE)
    if m:
        at = m.group(1).upper()
        if at in ("STOCK_FOOTAGE", "SCREEN_CAPTURE", "DIAGRAM_ANIMATION", "CODE_SNIPPET", "STATIC_IMAGE"):
            return at
    return "STOCK_FOOTAGE"


def _infer_keywords(text: str, title: str = "") -> list[str]:
    text_lower = text.lower()
    title_clean = title.lower().replace(" how ", " ").replace(" what ", " ").replace(" explained", "").strip()[:40]
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                 "have", "has", "had", "do", "does", "did", "will", "would", "could",
                 "should", "may", "might", "can", "shall", "to", "of", "in", "for",
                 "on", "with", "at", "by", "from", "as", "into", "through", "during",
                 "before", "after", "above", "below", "between", "out", "off", "over",
                 "under", "again", "further", "then", "once", "here", "there", "when",
                 "where", "why", "how", "all", "each", "every", "both", "few", "more",
                 "most", "other", "some", "such", "no", "nor", "not", "only", "own",
                 "same", "so", "than", "too", "very", "just", "because", "but", "and",
                 "or", "if", "while", "about", "up", "down", "like", "also", "its",
                 "let", "see", "way", "use", "used", "using", "make", "made", "get"}

    words = re.findall(r'\b[a-zA-Z]{4,}\b', text_lower)
    words = [w for w in words if w not in stopwords]

    from collections import Counter
    word_freq = Counter(words)
    top_words = [w for w, _ in word_freq.most_common(15)]

    tech_terms = ["AI", "machine learning", "deep learning", "neural network", "transformer",
                  "GPT", "LLM", "data", "algorithm", "code", "GPU", "training", "inference",
                  "automation", "cloud", "API", "model", "embedding", "attention",
                  "token", "pipeline", "architecture", "framework", "PyTorch", "TensorFlow",
                  "layer", "weight", "bias", "gradient", "vector", "matrix"]
    found_tech = [t for t in tech_terms if t.lower() in text_lower]

    visual_map = {
        "transformer": "neural network architecture with flowing attention connections",
        "attention": "data streams connecting across a neural grid",
        "neural": "glowing neural pathways and synaptic connections",
        "algorithm": "algorithm visualization with flowing data patterns",
        "data": "streaming data visualization with glowing particles",
        "model": "abstract 3D model rotating with data layers",
        "network": "interconnected nodes pulsing with data flow",
        "training": "neural network training visualization with loss curves",
        "token": "word embeddings floating in vector space",
        "learning": "brain with glowing neural connections forming patterns",
        "layer": "transparent stacked layers with data flowing between them",
        "vector": "vectors in multidimensional space with directional arrows",
        "matrix": "matrix multiplication visualization with glowing cells",
        "GPU": "processor chip with parallel data pathways",
        "inference": "data flowing through a pipeline with processing nodes",
        "embedding": "word vectors arranged in semantic space",
    }
    found_visual = []
    for word in top_words[:5] + found_tech:
        key = word.lower().replace(" ", "_")
        if key in visual_map and visual_map[key] not in found_visual:
            found_visual.append(visual_map[key])
        elif key not in found_visual:
            for vk, vv in visual_map.items():
                if vk in word.lower() and vv not in found_visual:
                    found_visual.append(vv)
                    break

    title_terms = [t.strip() for t in title_clean.replace(" and ", " ").replace(" with ", " ").split() if len(t.strip()) > 3]
    combined = []
    if title_terms:
        combined.append(title_clean)
    combined.extend(found_tech[:3])
    combined.extend(found_visual[:3])

    return combined[:6] if combined else ["technology", "abstract", "digital"]


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


def _infer_transition(scene_index: int, total_scenes: int, text: str = "") -> str:
    if scene_index == 0:
        return "cut"
    if scene_index == total_scenes - 1:
        return "fade"
    text_lower = text.lower()
    if any(w in text_lower for w in ["breakthrough", "introducing", "reveal", "new", "revolutionary"]):
        return "circle_open"
    if any(w in text_lower for w in ["conclusion", "summary", "wrap", "finally", "end"]):
        return "circle_close"
    if any(w in text_lower for w in ["transform", "shift", "change", "evolve", "transition"]):
        return "smooth_left"
    if any(w in text_lower for w in ["explode", "burst", "sudden", "surprising", "shock"]):
        return "pixelize"
    if any(w in text_lower for w in ["side", "compare", "versus", "alternative", "option"]):
        return "slide_left"
    if any(w in text_lower for w in ["zoom", "focus", "detail", "close", "inside"]):
        return "zoom"
    transitions = ["dissolve", "slide_right", "fade", "dissolve", "slide_left", "fade_gradual", "smooth_right"]
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


def _adjust_scenes_for_format(scenes: list[dict], format_type: str, max_allowed: int = None) -> list[dict]:
    if format_type == "shorts":
        cap = 60
    else:
        cap = float(max_allowed) if max_allowed else 480.0
    current_total = sum(s.get("duration", 6) for s in scenes)
    if cap and current_total != cap:
        scale = cap / max(current_total, 1)
        for s in scenes:
            s["duration"] = round(max(s.get("duration", 6) * scale, 3), 1)
    return scenes


def add_end_scene(scenes: list[dict]) -> list[dict]:
    end = {
        "background": "solid_black",
        "duration": 5.0,
        "asset_type": "STOCK_FOOTAGE",
        "asset_keywords": ["subscribe", "technology", "animated"],
        "ltx_prompt": "Cinematic shot of glowing subscribe button with neon light burst, camera slowly zooming in, dark background with particle effects, professional call-to-action style, rich colors, high quality",
        "text": [
            {"text": "Subscribe for more AI Tech", "style": "title", "position": "center"},
            {"text": "vyomcloud.com", "style": "caption", "position": "bottom"},
        ],
        "transition": "fade",
        "camera": {"zoom": 1.05, "pan_x": 0, "pan_y": 0},
        "music_mood": "uplifting",
    }
    return scenes + [end]


def build_timestamps(scenes: list[dict]) -> str:
    total = 0.0
    lines = []
    for i, s in enumerate(scenes):
        dur = s.get("duration", 5.0)
        mins = int(total // 60)
        secs = int(total % 60)
        timestamp = f"{mins}:{secs:02d}"
        title = s.get("keyword") or s.get("description") or s.get("asset_keywords", [None])[0] if s.get("asset_keywords") else f"Scene {i + 1}"
        lines.append(f"{timestamp} - {title}")
        total += dur
    return "\n".join(lines)
