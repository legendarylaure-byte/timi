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
    scenes = [{"dummy": True}]
    result = inject_intro_outro(scenes, "NonExistentCategory")
    assert len(result) == 1
    assert result[0]["dummy"] is True
