"""The scene parser must receive the human topic, never the video id.

This is the guard for the defect that made every video look the same.
`main.py` called `parse_script_to_scenes(..., title=video_id)`, and `title` is
not decoration: `_infer_keywords` folds it into `asset_keywords[0]`, and the LLM
prompt prints it as "Title:" so the model copies it into the keywords too. Both
branches therefore searched Pexels for a slug like "short-20261005-1". Pexels
fuzzy-matches that and returns generic abstract tech clips, so every scene of
every video rendered the same dark slate-blue footage.

Measured on the production log: 355 of 487 stock searches used the video id as
the query, and the remaining ones were plumbing tokens -- not one used the scene
topic. The bonus: `_minimal_fallback` used the same value for ON-SCREEN text, so
a fallback render printed "short-20261005-1" on the video.

Why this test exists even though `footage_audit.py` also checks topic-derived
queries: the audit SUPPLIES its own title, so it cannot see a regression in the
call site. This test pins the call site itself.

Behavioural, not a source grep: it captures the value the real function receives,
so it fails for any reason the topic stops arriving, including a future
refactor that renames the parameter.
"""
import sys
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[1]
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

TOPIC = "How Quantum Error Correction Works"
VIDEO_ID = "short-20261005-1"


@pytest.fixture(scope="module")
def main_mod():
    """main.py is imported at module scope for speed. It syncs Firestore env on
    import, which is why this is module-scoped rather than per-test."""
    import main  # noqa: F401
    return main


def _capture_title(main_mod, monkeypatch, topic, video_id):
    """Call the real _parse_scenes_for_asset_router and return the `title` that
    reached parse_script_to_scenes."""
    import utils.scene_parser as sp

    seen = {}

    def _fake_parse(script_text, title="", **kwargs):
        seen["title"] = title
        return [{"narration_text": "x", "render_type": "stock",
                 "asset_type": "STOCK_FOOTAGE", "asset_keywords": [title],
                 "duration": 5.0, "target_duration": 5.0}]

    monkeypatch.setattr(sp, "parse_script_to_scenes", _fake_parse)
    monkeypatch.setattr(main_mod, "SCENE_ARCHITECT_MODE", "off", raising=False)
    main_mod._parse_scenes_for_asset_router(
        "NARRATION: something", "", "Science & Technology", "long",
        video_id, 120, topic=topic,
    )
    return seen.get("title")


def test_topic_reaches_the_scene_parser(main_mod, monkeypatch):
    title = _capture_title(main_mod, monkeypatch, TOPIC, VIDEO_ID)
    assert title == TOPIC, (
        f"parse_script_to_scenes received title={title!r}, expected the topic "
        f"{TOPIC!r}. Passing video_id makes every scene search the stock "
        f"libraries for {VIDEO_ID!r} and render generic footage."
    )


def test_the_video_id_is_not_used_as_the_title(main_mod, monkeypatch):
    title = _capture_title(main_mod, monkeypatch, TOPIC, VIDEO_ID)
    assert title != VIDEO_ID, (
        "the video id reached the scene parser as the scene title; this is the "
        "regression that produced identical slate-blue footage across the channel"
    )


def test_both_run_video_pipeline_call_sites_pass_topic(main_mod):
    """Both the short and long pipelines must thread it. Fixing one leaves the
    other silently broken, and a half-fix looks like a pass in any single-video
    test."""
    import ast
    import inspect

    src = inspect.getsource(main_mod)
    tree = ast.parse(src)
    call_sites = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "run_video_pipeline"):
            call_sites.append(node)

    assert len(call_sites) == 2, (
        f"expected 2 run_video_pipeline call sites, found {len(call_sites)}: "
        "a new one appeared without threading topic="
    )
    for node in call_sites:
        kwargs = {k.arg for k in node.keywords}
        assert "topic" in kwargs, (
            f"run_video_pipeline at line {node.lineno} does not pass topic="
        )


def test_run_video_pipeline_accepts_topic(main_mod):
    """The signature must actually accept it -- passing a keyword to a function
    that does not declare it is a TypeError at the first run, not a lint error."""
    import inspect

    params = inspect.signature(main_mod.run_video_pipeline).parameters
    assert "topic" in params, (
        "run_video_pipeline has no `topic` parameter, so the call sites cannot "
        "thread it"
    )


def test_llm_prompt_carries_the_topic_not_the_video_id(monkeypatch):
    """The LLM branch gets the same value through the prompt's `Title:` line, and
    the model copies what it reads into asset_keywords. Fixing only the rule-based
    branch leaves the defect live through the other door.

    Captures the prompt the real parser builds, so this fails for any reason the
    topic stops arriving -- not merely for one particular prompt string.
    """
    import utils.scene_parser as sp

    captured = {}

    def _fake_gen(prompt=None, system_prompt=None, **kwargs):
        captured["prompt"] = prompt or ""
        # One scene with a real topic keyword, so the branch returns rather than
        # falling through to the rule-based path.
        return ('[{"narration_text": "x", "description": "d", '
                '"asset_keywords": ["quantum error correction"], '
                '"ltx_prompt": "p", "render_type": "stock"}]')

    monkeypatch.setattr(sp, "generate_completion", _fake_gen)
    scenes = sp.parse_script_to_scenes(
        "NARRATION: a paragraph of script about quantum error correction in qubits "
        "and error syndromes and logical qubits and surface codes and thresholds.",
        title=TOPIC, category="Science & Technology", format_type="long",
    )
    assert captured.get("prompt"), "the LLM branch never ran, so this proves nothing"
    assert TOPIC in captured["prompt"], (
        "the scene-parse prompt does not contain the topic"
    )
    assert f"Title: {VIDEO_ID}" not in captured["prompt"], (
        "the scene-parse prompt still labels the topic line with a video id"
    )