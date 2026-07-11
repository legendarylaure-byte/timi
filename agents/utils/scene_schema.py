VALID_CATEGORIES = [
    "AI Explained", "Deep Tech", "Paper Breakdowns",
    "Tool Tutorials", "Industry Analysis", "Code & Build",
    "AI News", "Career & Learning",
]

VALID_FORMATS = ["shorts", "long"]
VALID_DIRECTIONS = ["left", "right", "top", "bottom"]
VALID_EFFECTS = ["fade_in", "fade_out", "none"]
VALID_TRANSITIONS = ["cut", "fade", "dissolve", "slide_left", "slide_right", "zoom", "none"]

ASSET_TYPES = ["STOCK_FOOTAGE", "SCREEN_CAPTURE", "DIAGRAM_ANIMATION", "CODE_SNIPPET", "STATIC_IMAGE"]
RENDER_TYPES = ["stock", "manim", "code"]

SHAPE_TYPES = ["circle", "square", "rounded_square", "arrow", "line"]
ANIMATION_TYPES = [
    "grow", "fade_in", "fade_out", "slide_in", "none",
]

BACKGROUND_TYPES = [
    "solid_black", "solid_white", "solid_indigo", "solid_slate",
    "gradient_dark_tech", "gradient_blueprint", "gradient_neon",
    "gradient_corporate", "gradient_minimal",
]


class ValidationError(Exception):
    pass


def validate_scene(scene: dict, index: int = 0) -> dict:
    errors = []
    if not isinstance(scene, dict):
        raise ValidationError(f"Scene {index}: must be a dict, got {type(scene).__name__}")

    if "duration" not in scene and "target_duration" not in scene:
        errors.append(f"Scene {index}: missing 'duration' or 'target_duration'")
    dur = scene.get("duration", scene.get("target_duration", 8))
    if not isinstance(dur, (int, float)) or dur <= 0:
        errors.append(f"Scene {index}: 'duration' must be positive number, got {dur}")

    asset_type = scene.get("asset_type", "STOCK_FOOTAGE")
    if asset_type not in ASSET_TYPES:
        import warnings
        warnings.warn(f"Scene {index}: unknown asset_type '{asset_type}', falling back to STOCK_FOOTAGE")
        scene["asset_type"] = "STOCK_FOOTAGE"

    render_type = scene.get("render_type", "stock")
    if render_type not in RENDER_TYPES:
        import warnings
        warnings.warn(f"Scene {index}: unknown render_type '{render_type}', falling back to 'stock'")
        scene["render_type"] = "stock"

    background = scene.get("background", "solid_black")
    if background and background not in BACKGROUND_TYPES:
        import warnings
        warnings.warn(f"Scene {index}: unknown background '{background}', falling back to 'solid_black'")
        scene["background"] = "solid_black"

    transition = scene.get("transition", "cut")
    if transition not in VALID_TRANSITIONS:
        import warnings
        warnings.warn(f"Scene {index}: unknown transition '{transition}', falling back to 'cut'")
        scene["transition"] = "cut"

    effects = scene.get("effects", [])
    if isinstance(effects, str):
        effects = [effects]
    if not isinstance(effects, list):
        import warnings
        warnings.warn(f"Scene {index}: 'effects' must be a list, resetting to []")
        scene["effects"] = []
    else:
        clean = []
        for e in effects:
            if e in VALID_EFFECTS:
                clean.append(e)
            else:
                import warnings
                warnings.warn(f"Scene {index}: unknown effect '{e}', skipping")
        scene["effects"] = clean

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
    result.setdefault("asset_type", "STOCK_FOOTAGE")
    result.setdefault("render_type", "stock")
    result.setdefault("background", "solid_black")
    result.setdefault("transition", "cut")
    result.setdefault("effects", [])
    result.setdefault("text", [])
    result.setdefault("music_mood", "ambient")
    return result


def validate_scenes(scenes: list) -> list:
    if not isinstance(scenes, list):
        raise ValidationError("Top-level must be a list of scenes")
    if not scenes:
        raise ValidationError("At least one scene is required")
    return [validate_scene(s, i) for i, s in enumerate(scenes)]


def scene_to_prompt(scene: dict) -> str:
    parts = [f"Asset: {scene.get('asset_type', 'STOCK_FOOTAGE')}"]
    parts.append(f"Background: {scene.get('background', 'solid_black')}")
    parts.append(f"Duration: {scene.get('duration', scene.get('target_duration', 8))}s")
    parts.append(f"Transition: {scene.get('transition', 'cut')}")
    keywords = scene.get("asset_keywords", [scene.get("keyword", "technology")])
    parts.append(f"Keywords: {', '.join(keywords) if isinstance(keywords, list) else keywords}")
    if scene.get("ltx_prompt"):
        parts.append(f"LTX: {scene['ltx_prompt'][:100]}")
    if scene.get("text"):
        texts = [t.get("text", "") for t in scene["text"] if t.get("text")]
        if texts:
            parts.append(f"Text: {' | '.join(texts)}")
    if scene.get("effects"):
        parts.append(f"Effects: {', '.join(scene['effects'])}")
    return " | ".join(parts)
