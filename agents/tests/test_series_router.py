from utils.series_router import (
    load_series, pick_series_for_category, inject_intro_outro,
)


def test_load_series_returns_dict():
    series = load_series()
    assert isinstance(series, dict)


def test_pick_series_for_category_known():
    series = pick_series_for_category("AI Explained")
    if series:
        assert "categories" in series


def test_pick_series_for_category_unknown():
    series = pick_series_for_category("UnknownCategoryXYZ")
    assert series is None


def test_inject_intro_outro_no_series():
    """Scenes + outro card. D39 removed the branded intro card."""
    scenes = [{"dummy": True}]
    result = inject_intro_outro(scenes, "NonExistentCategory")
    assert len(result) == 2
    assert result[0]["dummy"] is True
    assert result[1]["asset_type"] == "STATIC_IMAGE"
    assert result[1]["render_type"] == "branded_card"


def test_inject_intro_outro_never_returns_an_intro_card():
    """The regression that matters: a title card in front of the hook.

    Negative-tested against the old behaviour: reinstating the `intro_scene`
    prepend makes `result[0] is scenes[0]` false.
    """
    scenes = [{"dummy": True}, {"dummy": 2}]
    for category in ("AI News", "Programming & Software", "NonExistentCategory"):
        result = inject_intro_outro(scenes, category)
        assert result[0] is scenes[0], "a branded intro card was prepended"
        assert result[-1]["render_type"] == "branded_card"
