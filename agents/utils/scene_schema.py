import json
import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def load_characters() -> dict:
    path = os.path.join(ASSETS_DIR, "characters.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_series() -> dict:
    path = os.path.join(ASSETS_DIR, "series.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


VALID_CATEGORIES = [
    "Self-Learning", "Bedtime Stories", "Mythology Stories", "Animated Fables",
    "Science for Kids", "Rhymes & Songs", "Colors & Shapes", "Tech & AI",
    "Gaming", "Cooking & Food", "DIY & Crafts", "Health & Wellness",
    "Travel & Adventure", "Finance & Business", "Comedy & Entertainment", "Music & Dance",
]

VALID_FORMATS = ["shorts", "long"]
VALID_DIRECTIONS = ["left", "right", "top", "bottom"]
VALID_EFFECTS = ["sparkle", "fade_in", "fade_out", "rainbow_burst", "star_rain", "none"]
VALID_TRANSITIONS = ["cut", "fade", "fade_in", "fade_out", "dissolve", "slide_left", "slide_right", "none"]

SHAPE_TYPES = ["circle", "star", "heart", "diamond", "blob"]
ANIMATION_TYPES = [
    "bounce", "float", "wave", "grow", "wiggle", "slide_in",
    "thinking", "twinkle", "spin", "glide", "morph", "dance",
    "squish", "cry", "hug", "sway", "bloom", "none",
]

BACKGROUND_TYPES = [
    "gradient_sky", "gradient_forest", "gradient_ocean", "gradient_space",
    "gradient_sunset", "gradient_night", "gradient_garden", "gradient_classroom",
    "gradient_bedroom", "gradient_underwater", "color_solid",
]


class ValidationError(Exception):
    pass


def validate_scene(scene: dict, index: int = 0) -> dict:
    errors = []
    if not isinstance(scene, dict):
        raise ValidationError(f"Scene {index}: must be a dict, got {type(scene).__name__}")

    if "duration" not in scene:
        errors.append(f"Scene {index}: missing 'duration'")
    elif not isinstance(scene.get("duration"), (int, float)) or scene["duration"] <= 0:
        errors.append(f"Scene {index}: 'duration' must be positive number, got {scene.get('duration')}")

    background = scene.get("background", "gradient_sky")
    if background and background not in BACKGROUND_TYPES:
        errors.append(f"Scene {index}: unknown background '{background}'")

    transition = scene.get("transition", "cut")
    if transition not in VALID_TRANSITIONS:
        errors.append(f"Scene {index}: unknown transition '{transition}'")

    effects = scene.get("effects", [])
    if isinstance(effects, str):
        effects = [effects]
    if not isinstance(effects, list):
        errors.append(f"Scene {index}: 'effects' must be a list")
    else:
        for e in effects:
            if e not in VALID_EFFECTS:
                errors.append(f"Scene {index}: unknown effect '{e}'")

    characters = scene.get("characters", [])
    if not isinstance(characters, list):
        errors.append(f"Scene {index}: 'characters' must be a list")
    else:
        for ci, char in enumerate(characters):
            if not isinstance(char, dict):
                errors.append(f"Scene {index}, character {ci}: must be a dict")
                continue
            if "name" not in char:
                errors.append(f"Scene {index}, character {ci}: missing 'name'")
            if "animation" in char and char["animation"] not in ANIMATION_TYPES:
                errors.append(f"Scene {index}, character {ci}: unknown animation '{char['animation']}'")

    text_overlays = scene.get("text", [])
    if not isinstance(text_overlays, list):
        errors.append(f"Scene {index}: 'text' must be a list")
    else:
        for ti, t in enumerate(text_overlays):
            if not isinstance(t, dict):
                errors.append(f"Scene {index}, text {ti}: must be a dict")

    scenes = scene.get("scenes", None)
    if scenes is not None:
        for si, sub in enumerate(scenes):
            try:
                validate_scene(sub, si)
            except ValidationError as e:
                errors.append(str(e))

    if errors:
        raise ValidationError("; ".join(errors))

    result = dict(scene)
    result.setdefault("background", "gradient_sky")
    result.setdefault("transition", "cut")
    result.setdefault("effects", [])
    if not result.get("characters"):
        result["characters"] = [{"name": "pixel", "pose": "idle", "expression": "neutral", "animation": "float", "x": 0.5, "y": 0.55}]
    result.setdefault("text", [])
    result.setdefault("camera", {})
    result.setdefault("music_mood", "happy")
    return result


def validate_scenes(scenes: list) -> list:
    if not isinstance(scenes, list):
        raise ValidationError("Top-level must be a list of scenes")
    if not scenes:
        raise ValidationError("At least one scene is required")
    return [validate_scene(s, i) for i, s in enumerate(scenes)]


def scene_to_prompt(scene: dict) -> str:
    parts = [f"Background: {scene['background']}"]
    parts.append(f"Duration: {scene['duration']}s")
    parts.append(f"Transition: {scene['transition']}")
    if scene.get("characters"):
        chars = []
        for c in scene["characters"]:
            desc = c["name"]
            if c.get("pose"):
                desc += f" ({c['pose']})"
            if c.get("animation"):
                desc += f" anim:{c['animation']}"
            chars.append(desc)
        parts.append(f"Characters: {', '.join(chars)}")
    if scene.get("text"):
        texts = [t.get("text", "") for t in scene["text"] if t.get("text")]
        if texts:
            parts.append(f"Text: {' | '.join(texts)}")
    if scene.get("effects"):
        parts.append(f"Effects: {', '.join(scene['effects'])}")
    return " | ".join(parts)
