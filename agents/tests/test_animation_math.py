from utils.animation_math import ANIMATION_FUNCTIONS, none_anim


def test_none_anim():
    result = none_anim(10)
    assert result == {"x": 0, "y": 0, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def test_bounce():
    fn = ANIMATION_FUNCTIONS.get("bounce")
    assert fn is not None
    result = fn(15, amplitude=10, frequency=2.0)
    assert "y" in result
    assert abs(result["y"]) <= 10


def test_float():
    fn = ANIMATION_FUNCTIONS.get("float")
    assert fn is not None
    result = fn(10, amplitude=8, period=3.0)
    assert "y" in result


def test_wave():
    fn = ANIMATION_FUNCTIONS.get("wave")
    assert fn is not None
    result = fn(10, max_angle=25, frequency=2.5)
    assert "rotation" in result


def test_grow():
    fn = ANIMATION_FUNCTIONS.get("grow")
    assert fn is not None
    result = fn(15, scale_min=0.8, scale_max=1.15, frequency=1.5)
    assert "scale_x" in result and "scale_y" in result
    assert 0.8 <= result["scale_x"] <= 1.15
    assert 0.8 <= result["scale_y"] <= 1.15


def test_wiggle():
    fn = ANIMATION_FUNCTIONS.get("wiggle")
    assert fn is not None
    result = fn(10, amplitude=5, frequency=4.0)
    assert "x" in result


def test_slide_in():
    fn = ANIMATION_FUNCTIONS.get("slide_in")
    assert fn is not None
    result = fn(10, total_frames=30, direction="left", duration_ratio=0.5)
    assert "x" in result


def test_twinkle():
    fn = ANIMATION_FUNCTIONS.get("twinkle")
    assert fn is not None
    result = fn(20)
    assert "scale_x" in result and "scale_y" in result


def test_all_animations_have_required_keys():
    for name, fn in ANIMATION_FUNCTIONS.items():
        kwargs = {}
        if name == "slide_in":
            kwargs["total_frames"] = 30
        result = fn(15, **kwargs)
        for key in ("x", "y", "rotation", "scale_x", "scale_y"):
            assert key in result, f"{name} missing key {key}"
