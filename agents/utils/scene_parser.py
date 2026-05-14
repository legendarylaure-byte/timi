import json
import re
import os
from datetime import datetime
from utils.groq_client import generate_completion
from utils.firebase_status import log_activity
from utils.scene_schema import (
    validate_scenes, ValidationError, load_characters,
    ANIMATION_TYPES, BACKGROUND_TYPES, VALID_EFFECTS,
)

SYSTEM_PROMPT = """You are a scene director for children's animated videos. Convert the given script into structured scene descriptions.

Return ONLY a valid JSON array of scene objects. Each scene object has this exact structure:

{
  "background": "gradient_sky|gradient_forest|gradient_ocean|gradient_space|gradient_sunset|gradient_night|gradient_garden|gradient_classroom|gradient_bedroom|gradient_underwater|color_solid",
  "duration": 8.0,
  "characters": [
    {
      "name": "pixel|nova|ziggy|boop|sprout",
      "pose": "idle|happy|wave|point|surprised|thinking|sleep|dance|growing|sad",
      "expression": "neutral|happy|excited|curious|calm|dreamy|silly|sad|surprised|peaceful",
      "animation": "bounce|float|wave|grow|wiggle|slide_in|thinking|twinkle|spin|glide|morph|dance|squish|cry|hug|sway|bloom|none",
      "x": 0.5,
      "y": 0.6
    }
  ],
  "text": [
    {
      "text": "Spoken narration text shown on screen",
      "style": "narration|dialogue|title|emphasis",
      "position": "center|top|bottom|left|right"
    }
  ],
  "effects": ["sparkle|fade_in|fade_out|rainbow_burst|star_rain"],
  "transition": "cut|fade|dissolve|slide_left|slide_right",
  "camera": {
    "zoom": 1.0,
    "pan_x": 0,
    "pan_y": 0
  },
  "music_mood": "happy|calm|adventure|dreamy|playful|exciting"
}

RULES:
- Each scene should be 5-12 seconds
- x and y are normalized 0-1 coordinates (0.5 = center)
- Use characters that match the story content
- Pixel = science/learning, Nova = bedtime/magic, Ziggy = colors/songs, Boop = emotions/play, Sprout = nature/growth
- Max 2 characters per scene (to keep compositing fast)
- Text should be short phrases (3-8 words), not full sentences
- Background should match the scene mood
- camera.zoom of 1.0 means no zoom, >1 zooms in
- Include text overlays for key spoken phrases

Generate scenes that follow the narrative arc of the script. Maintain consistent character placement across consecutive scenes."""


def parse_script_to_scenes(script_text: str, title: str = "", category: str = "", format_type: str = "shorts", storyboard_text: str = "") -> list[dict]:
    log_activity("scene_parser", f"Parsing script: {title}", "info")
    print(f"[SCENE_PARSER] Parsing script for '{title}' ({format_type})")

    scenes = _llm_scene_parse(script_text, title, category, format_type, storyboard_text)
    if scenes:
        return scenes

    scenes = _rule_based_parse(script_text, storyboard_text, format_type)
    if scenes:
        print(f"[SCENE_PARSER] Rule-based parse produced {len(scenes)} scenes")
        return scenes

    scenes = _minimal_fallback(title, category, format_type)
    print(f"[SCENE_PARSER] Using minimal fallback ({len(scenes)} scenes)")
    return scenes


def _llm_scene_parse(script_text: str, title: str, category: str, format_type: str, storyboard_text: str) -> list[dict] | None:
    if len(script_text) > 6000:
        script_text = script_text[:6000] + "\n...[truncated]"

    prompt = f"""Convert this children's video script into structured animation scenes.

Title: {title}
Category: {category}
Format: {format_type}

Script:
{script_text}

Storyboard:
{storyboard_text[:3000] if storyboard_text else "N/A"}

Important: Choose characters that fit the category:
- {category} related characters: {_get_suggested_characters(category)}

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


def _rule_based_parse(script_text: str, storyboard_text: str, format_type: str) -> list[dict]:
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
        characters = _infer_characters(block)
        text = _infer_text(block)
        effects = _infer_effects(block, i, len(scene_blocks))
        transition = _infer_transition(i, len(scene_blocks))

        scene = {
            "background": background,
            "duration": duration,
            "characters": characters,
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
    char_name = _pick_character_for_category(category)
    scene_count = 4 if format_type == "shorts" else 8
    scenes = []
    for i in range(scene_count):
        scenes.append({
            "background": "gradient_sky",
            "duration": 6.0 if format_type == "shorts" else 10.0,
            "characters": [{"name": char_name, "pose": "idle", "expression": "neutral", "animation": "float", "x": 0.5, "y": 0.5}],
            "text": [{"text": title[:50], "style": "title", "position": "center"}],
            "effects": ["sparkle"],
            "transition": "fade" if i > 0 else "cut",
            "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
            "music_mood": "happy",
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
    if any(w in text_lower for w in ["space", "star", "moon", "planet", "galaxy", "astronaut"]):
        return "gradient_space"
    if any(w in text_lower for w in ["ocean", "sea", "water", "fish", "underwater", "beach"]):
        return "gradient_ocean"
    if any(w in text_lower for w in ["night", "sleep", "bedtime", "dream", "moonlight", "dark"]):
        return "gradient_night"
    if any(w in text_lower for w in ["forest", "tree", "wood", "nature", "garden", "flower", "plant"]):
        return "gradient_forest"
    if any(w in text_lower for w in ["sunset", "evening", "dusk", "golden"]):
        return "gradient_sunset"
    if any(w in text_lower for w in ["classroom", "school", "learn", "teach", "book", "read"]):
        return "gradient_classroom"
    if any(w in text_lower for w in ["bedroom", "bed", "room", "home", "house"]):
        return "gradient_bedroom"
    if any(w in text_lower for w in ["garden", "park", "outside", "playground", "flower"]):
        return "gradient_garden"
    if any(w in text_lower for w in ["rainbow", "color", "paint", "draw", "art"]):
        return "gradient_sunset"
    return "gradient_sky"


def _infer_characters(text: str) -> list[dict]:
    text_lower = text.lower()
    characters = []

    char_keywords = {
        "pixel": ["robot", "pixel", "machine", "computer", "screen", "tech", "learn", "discover"],
        "nova": ["star", "nova", "dream", "wish", "night", "imagine", "story", "magic"],
        "ziggy": ["rainbow", "ziggy", "color", "shape", "circle", "square", "dance", "song", "paint"],
        "boop": ["friend", "boop", "feel", "happy", "sad", "share", "play", "care", "hug"],
        "sprout": ["sprout", "plant", "grow", "flower", "nature", "tree", "seed", "garden", "earth"],
    }

    char_poses = {
        "pixel": ["idle", "happy", "wave", "point"],
        "nova": ["idle", "happy", "wave", "float"],
        "ziggy": ["idle", "happy", "dance", "wave"],
        "boop": ["idle", "happy", "wave", "surprised"],
        "sprout": ["idle", "growing", "happy", "wave"],
    }

    char_anims = {
        "pixel": "bounce",
        "nova": "float",
        "ziggy": "dance",
        "boop": "bounce",
        "sprout": "sway",
    }

    for char_name, keywords in char_keywords.items():
        if any(kw in text_lower for kw in keywords):
            poses = char_poses.get(char_name, ["idle"])
            characters.append({
                "name": char_name,
                "pose": poses[len(characters) % len(poses)],
                "expression": "happy" if any(w in text_lower for w in ["happy", "fun", "great", "yay", "celebrate"]) else "neutral",
                "animation": char_anims.get(char_name, "float"),
                "x": 0.3 + len(characters) * 0.4,
                "y": 0.55,
            })
            if len(characters) >= 2:
                break

    if not characters:
        default_char = _pick_character_for_category("general")
        characters.append({
            "name": default_char,
            "pose": "idle",
            "expression": "neutral",
            "animation": "float",
            "x": 0.5,
            "y": 0.55,
        })

    return characters


def _infer_text(text: str) -> list[dict]:
    lines = text.strip().split("\n")
    texts = []
    for line in lines:
        cleaned = re.sub(r'^[\s*#\-]+', '', line).strip()
        cleaned = re.sub(r'[\d\s\-–—,]+(?:seconds?|secs?|s)\)', '', cleaned)
        cleaned = re.sub(r'^Narrator\s*:\s*', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'^[A-Z][a-z]+\s*:\s*', '', cleaned).strip()
        cleaned = re.sub(r'[<>]', '', cleaned)

        if cleaned and 15 < len(cleaned) < 100 and not any(kw in cleaned.lower() for kw in ["scene", "camera", "angle", "color palette", "background"]):
            texts.append({
                "text": cleaned[:80],
                "style": "dialogue" if "?" in cleaned or "!" in cleaned else "narration",
                "position": "bottom" if len(texts) % 2 == 1 else "center",
            })
            if len(texts) >= 3:
                break

    return texts


def _infer_effects(text: str, scene_index: int, total_scenes: int) -> list[str]:
    text_lower = text.lower()
    effects = []

    if scene_index == 0:
        effects.append("fade_in")
    if scene_index == total_scenes - 1:
        effects.append("fade_out")
    if any(w in text_lower for w in ["sparkle", "magic", "twinkle", "wish"]):
        effects.append("sparkle")
    if any(w in text_lower for w in ["rainbow", "colorful", "bright"]):
        effects.append("rainbow_burst")
    if any(w in text_lower for w in ["star", "space", "night", "dream"]):
        effects.append("star_rain")

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
    if any(w in text_lower for w in ["sad", "cry", "lonely", "afraid", "scared"]):
        return "calm"
    if any(w in text_lower for w in ["happy", "fun", "play", "dance", "song", "celebrate"]):
        return "playful"
    if any(w in text_lower for w in ["adventure", "explore", "journey", "discover"]):
        return "adventure"
    if any(w in text_lower for w in ["dream", "sleep", "night", "wish", "imagine", "story"]):
        return "dreamy"
    if any(w in text_lower for w in ["exciting", "wow", "amazing", "incredible"]):
        return "exciting"
    return "happy"


def _get_suggested_characters(category: str) -> str:
    mapping = {
        "Self-Learning": "pixel (robot, curious), boop (friendly, playful)",
        "Science for Kids": "pixel (robot, experiments), sprout (nature, growing)",
        "Bedtime Stories": "nova (star, dreams), boop (snuggle, cozy)",
        "Mythology Stories": "nova (magical, storytelling), pixel (discovering legends)",
        "Animated Fables": "nova (storyteller), sprout (nature), pixel (curious)",
        "Rhymes & Songs": "ziggy (rainbow, dancing), boop (bouncing, singing)",
        "Colors & Shapes": "ziggy (shapeshifter, rainbow), pixel (counting, learning)",
        "Tech & AI": "pixel (robot), ziggy (colorful tech)",
        "DIY & Crafts": "ziggy (creative, colorful), boop (hands-on, playful)",
    }
    return mapping.get(category, "pixel (curious robot), nova (dreamy star), ziggy (rainbow friend)")


def _pick_character_for_category(category: str) -> str:
    if category in ("Self-Learning", "Science for Kids", "Tech & AI"):
        return "pixel"
    if category in ("Bedtime Stories", "Mythology Stories", "Animated Fables"):
        return "nova"
    if category in ("Rhymes & Songs", "Colors & Shapes", "DIY & Crafts"):
        return "ziggy"
    return "pixel"


def _default_scene(index: int) -> dict:
    return {
        "background": "gradient_sky",
        "duration": 6.0,
        "characters": [{"name": "pixel", "pose": "idle", "expression": "neutral", "animation": "float", "x": 0.5, "y": 0.55}],
        "text": [],
        "effects": ["fade_in"] if index == 0 else ["none"],
        "transition": "cut" if index == 0 else "dissolve",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "happy",
    }


def _adjust_scenes_for_format(scenes: list[dict], format_type: str) -> list[dict]:
    if format_type == "shorts":
        max_duration = sum(s.get("duration", 6) for s in scenes)
        if max_duration > 60:
            scale = 60 / max_duration
            for s in scenes:
                s["duration"] = round(max(s.get("duration", 6) * scale, 3), 1)
    return scenes
