import pytest
from utils.scene_schema import validate_scenes, ValidationError, load_characters


def test_validate_scenes_empty():
    with pytest.raises(ValidationError, match="At least one scene"):
        validate_scenes([])


def test_validate_scenes_valid():
    scenes = [{
        "background": "gradient_sky",
        "duration": 6.0,
        "characters": [{"name": "pixel", "pose": "idle", "expression": "neutral",
                        "animation": "float", "x": 0.5, "y": 0.55}],
        "text": [{"text": "Hello!", "style": "narration", "position": "center"}],
        "effects": ["fade_in"],
        "transition": "cut",
        "camera": {"zoom": 1.0, "pan_x": 0, "pan_y": 0},
        "music_mood": "happy",
    }]
    result = validate_scenes(scenes)
    assert len(result) == 1


def test_validate_scenes_invalid_missing_fields():
    scenes = [{"background": "gradient_sky"}]  # missing required fields
    with pytest.raises(ValidationError, match="missing 'duration'"):
        validate_scenes(scenes)


def test_load_characters_returns_dict():
    chars = load_characters()
    assert isinstance(chars, dict)


def test_validation_error_exception():
    try:
        raise ValidationError("test error")
    except ValidationError as e:
        assert str(e) == "test error"
