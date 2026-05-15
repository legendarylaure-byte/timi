from utils.series_router import (
    load_series, pick_series_for_category, inject_intro_outro,
    build_intro_scene, build_outro_scene,
)


def test_load_series_returns_dict():
    series = load_series()
    assert isinstance(series, dict)


def test_pick_series_for_category_known():
    series = pick_series_for_category("Self-Learning")
    if series:
        assert "host" in series
        assert "categories" in series


def test_pick_series_for_category_unknown():
    series = pick_series_for_category("UnknownCategoryXYZ")
    assert series is None


def test_build_intro_scene():
    series_data = {
        "host": "pixel",
        "host_pose": "wave",
        "host_expression": "happy",
        "background": "gradient_space",
        "intro_duration": 3.0,
        "intro_text": "Welcome!",
        "character_placement": {"x": 0.5, "y": 0.55},
        "music_mood": "happy",
    }
    scene = build_intro_scene(series_data, "shorts")
    assert scene["duration"] == 3.0
    assert scene["characters"][0]["name"] == "pixel"
    assert scene["characters"][0]["pose"] == "wave"


def test_build_outro_scene():
    series_data = {
        "host": "nova",
        "host_expression": "happy",
        "background": "gradient_night",
        "outro_duration": 3.0,
        "outro_text": "Goodbye!",
        "character_placement": {"x": 0.5, "y": 0.55},
        "music_mood": "calm",
    }
    scene = build_outro_scene(series_data, "shorts")
    assert scene["duration"] == 3.0
    assert scene["characters"][0]["name"] == "nova"
    assert "fade_out" in scene["effects"]


def test_inject_intro_outro_with_series():
    scenes = [{"background": "gradient_sky", "duration": 6.0, "characters": [],
               "text": [], "effects": [], "transition": "cut",
               "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0}, "music_mood": "happy"}]
    result = inject_intro_outro(scenes, "Self-Learning")
    assert len(result) == 3  # intro + scene + outro
    assert result[0]["effects"] == ["sparkle"]


def test_inject_intro_outro_no_series():
    scenes = [{"dummy": True}]
    result = inject_intro_outro(scenes, "NonExistentCategory")
    assert len(result) == 1
    assert result[0]["dummy"] is True
