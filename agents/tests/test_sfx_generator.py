import os
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sfx_generator import (
    _sine_freq_sweep, _short_burst, _sine_decay, _noise_burst,
    _square_burst, _noise_sweep, _bounce, _chirp, _laugh,
    generate_sfx, generate_all_sfx, get_sfx_path,
    map_effect_to_sfx, load_sfx_scene_assignments,
    SFX_MAP, EFFECT_TO_SFX, GENERATORS,
)


def test_all_generators_return_audiosegment():
    seg = _sine_freq_sweep(200, 500, 1000)
    assert seg is not None
    assert len(seg) > 0

    seg = _short_burst(100, 800)
    assert seg is not None
    assert len(seg) > 0

    seg = _sine_decay(200, 500)
    assert seg is not None
    assert len(seg) > 0

    seg = _noise_burst(100)
    assert seg is not None
    assert len(seg) > 0

    seg = _square_burst(100, 800)
    assert seg is not None
    assert len(seg) > 0

    seg = _noise_sweep(200, 100, 1000)
    assert seg is not None
    assert len(seg) > 0

    seg = _bounce(200, 400, 200)
    assert seg is not None
    assert len(seg) > 0

    seg = _chirp(200, 2000)
    assert seg is not None
    assert len(seg) > 0

    seg = _laugh(300, 600)
    assert seg is not None
    assert len(seg) > 0


def test_all_generators_produce_correct_duration():
    for name, gen_fn in GENERATORS.items():
        config = SFX_MAP.get(name)
        if config is None:
            continue
        params = dict(config["params"])
        seg = gen_fn(duration_ms=config["duration_ms"], **params)
        assert abs(len(seg) - config["duration_ms"]) < 50, f"{name} duration mismatch"


def test_sfx_map_has_all_generators():
    for name, config in SFX_MAP.items():
        assert config["generator"] in GENERATORS, f"SFX {name} has unknown generator {config['generator']}"
        assert config["duration_ms"] > 0


def test_map_effect_to_sfx():
    assert map_effect_to_sfx("sparkle") == "sparkle"
    assert map_effect_to_sfx("star_rain") == "twinkle"
    assert map_effect_to_sfx("rainbow_burst") == "magic"
    assert map_effect_to_sfx("fade_in") == "swoosh"
    assert map_effect_to_sfx("unknown_effect") is None


def test_generate_sfx_unknown_name():
    result = generate_sfx("nonexistent_sfx", output_dir="/tmp")
    assert result is None


def test_generate_sfx_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generate_sfx("pop", output_dir=tmpdir)
        assert path is not None
        assert os.path.exists(path)
        assert path.endswith(".wav")


def test_generate_all_sfx_creates_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        results = generate_all_sfx(output_dir=tmpdir)
        assert len(results) == len(SFX_MAP)
        for name, path in results.items():
            assert os.path.exists(path), f"{name} was not created at {path}"


def test_get_sfx_path_generates_if_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = get_sfx_path("ding")
        assert path is not None
        assert os.path.exists(path)


def test_load_sfx_scene_assignments():
    scenes = [
        {"effects": ["sparkle", "fade_in"]},
        {"effects": ["unknown_effect"]},
        {},
    ]
    result = load_sfx_scene_assignments(scenes)
    assert "sfx" in result[0]
    assert len(result[0]["sfx"]) == 2
    assert result[0]["sfx"][0]["name"] == "sparkle"
    assert "sfx" not in result[1]
    assert "sfx" not in result[2]


def test_load_sfx_scene_assignments_all_effects_mapped():
    for effect in EFFECT_TO_SFX:
        assert effect in EFFECT_TO_SFX
        sfx_name = EFFECT_TO_SFX[effect]
        assert sfx_name in SFX_MAP, f"Effect {effect} maps to unknown SFX {sfx_name}"
