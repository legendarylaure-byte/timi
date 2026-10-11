"""WS1 guard: the fake `snippet.py` code cards must never render again.

The 2026-10-10 output showed code cards on ~83% of programming-video scenes: a
dark IDE panel whose body was the *narration* clipped to 80 chars
(`asset_router._render_scene_inner` did `description.split("\\n")`), watermarked
and captioned. They read as unprofessional and leaked onto non-code topics.
Removed channel-wide 2026-10.

Three things must hold, and each is checked where it can actually fail:
  1. the rule parser never tags a scene as code;
  2. the schema coerces a stale code scene (stored doc / LLM tag) to stock;
  3. the render path has no code branch, so even a scene that still says
     render_type="code" comes back as stock footage.
"""
import os
import sys
import tempfile
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

SCRIPT_WITH_CODE_TAG = (
    "NARRATION: Python lists are ordered collections that hold items in sequence.\n"
    "VISUAL: [CODE] a code snippet showing how to create a list and append items.\n\n"
    "NARRATION: You can index a list to read or replace a single element by position.\n"
    "VISUAL: [LTX] close-up of a developer workspace, monitor glowing, warm key light.\n"
)


def test_rule_parse_never_emits_a_code_scene():
    from utils.scene_parser import parse_script_to_scenes

    scenes = parse_script_to_scenes(
        SCRIPT_WITH_CODE_TAG, title="Python Lists Explained",
        category="Programming & Software", format_type="long",
    )
    assert scenes, "parser returned no scenes, so this proves nothing"
    bad = [(s.get("render_type"), s.get("asset_type")) for s in scenes
           if s.get("render_type") != "stock"
           or s.get("asset_type") not in ("STOCK_FOOTAGE", "STATIC_IMAGE")]
    assert not bad, f"a code scene slipped through the rule parser: {bad}"


def test_infer_render_type_is_always_stock():
    """Pins the parser itself, not the end result.

    The rule-parse test above is masked: `parse_script_to_scenes` runs scenes
    through `validate_scene`, which coerces any "code" back to "stock". So a
    regression that makes `_infer_render_type` emit "code" again would still
    pass that test (verified by mutation). This asserts the parser directly.
    """
    from utils.scene_parser import _infer_render_type

    assert _infer_render_type("VISUAL: [CODE] code snippet showing a list") == "stock"
    assert _infer_render_type("VISUAL: [LTX] cinematic close-up of a server") == "stock"


def test_schema_coerces_a_stale_code_scene_to_stock():
    from utils.scene_schema import validate_scene

    out = validate_scene(
        {"render_type": "code", "asset_type": "CODE_SNIPPET", "duration": 5.0},
        index=0,
    )
    assert out["render_type"] == "stock"
    assert out["asset_type"] == "STOCK_FOOTAGE"


def test_render_path_has_no_code_branch(monkeypatch):
    import utils.asset_router as ar

    assert not hasattr(ar, "render_code_snippet"), (
        "asset_router still imports the code-card renderer; the branch is back"
    )

    fake = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    fake.write(b"x" * 2000)
    fake.close()
    try:
        class _NoModel:
            def is_available(self):
                return False

        monkeypatch.setattr(ar, "get_video_model", lambda: _NoModel())
        monkeypatch.setattr(ar, "_get_stock_clip", lambda *a, **k: fake.name)

        scene = {"render_type": "code", "asset_type": "CODE_SNIPPET",
                 "asset_keywords": ["python list"], "description": "a code snippet"}
        result = ar._render_scene_inner(scene, "short-x", 0, "long", 5.0)

        assert result, "render returned nothing; the stock stub did not fire"
        assert result["source"] == "stock", result
        assert "snippet" not in os.path.basename(result["path"]).lower()
    finally:
        os.unlink(fake.name)
