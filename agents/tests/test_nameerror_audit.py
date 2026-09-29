"""Regression tests for three `NameError`s that `except Exception` hid.

All three were found by an AST pass over `agents/` (not by a failing test, and
not by watching the logs). Each one is a call to a name that is never bound in
the module, and each one sat inside a bare `except Exception`, so the job it
broke logged a plausible-looking warning and carried on.

  1. `asset_router._render_scene_inner` built a temp path with `Path(...)` but
     only ever imported `os.path`. Every scene in that branch was wrapped in
     `except Exception`, so they silently fell through to stock. The renderer
     was dead code.
  2. `weekly_monetization_job` called `update_platform_metrics` without
     importing it, so the real YouTube stats were fetched and then thrown away.
     The warning said "Could not fetch real YouTube stats" — the fetch worked.
  3. `weekly_documentary_job` called `generate_video_id()`, which does not exist
     anywhere in the repo. It raised on the FIRST video, outside the per-video
     try, so the job aborted with zero videos produced. Worse: the function set
     `os.environ["TIER"] = "documentary"` before the loop and only restored it
     after, so the abort left TIER="documentary" set for the rest of the
     process — the next daily run would have rendered as a documentary tier.

The AST pass is the real guard: it catches the whole bug class, not just these
three names.
"""

import ast
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

AGENTS = Path(__file__).parent.parent

# Directories that make up the pipeline. tests/ is excluded: tests
# intentionally reference undefined names.
SCAN_DIRS = ("utils", "crew", "models", "scripts")
SCAN_FILES = ("main.py",)


def _bound_names(tree):
    """Every name the module binds anywhere (imports, defs, assignments, args)."""
    bound = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            bound.update(a.asname or a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.Import):
            bound.update(a.asname or a.name.split(".")[0] for a in n.names)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, ast.Global):
            bound.update(n.names)
    return bound


def _pipeline_modules():
    for d in SCAN_DIRS:
        yield from sorted((AGENTS / d).glob("*.py"))
    for f in SCAN_FILES:
        yield AGENTS / f


def test_no_module_references_an_unbound_name():
    """The bug class: a name that is read but never bound, i.e. a guaranteed
    NameError on that code path."""
    import builtins

    # Module globals Python injects — not imports, so `_bound_names` won't see them.
    module_globals = {
        "__file__",
        "__name__",
        "__doc__",
        "__package__",
        "__spec__",
        "__loader__",
        "__builtins__",
    }
    offenders = []
    for f in _pipeline_modules():
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError as e:
            offenders.append(f"{f}: SYNTAX ERROR {e}")
            continue
        bound = _bound_names(tree)
        used = {
            n.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        missing = used - bound - set(dir(builtins)) - module_globals
        if missing:
            offenders.append(f"{f.relative_to(AGENTS)}: {sorted(missing)}")
    assert not offenders, "unbound name(s) — each one is a NameError:\n  " + "\n  ".join(
        offenders
    )


def test_asset_router_has_no_bare_Path_reference():
    """Named separately so the failure points at the dead render branch."""
    src = (AGENTS / "utils" / "asset_router.py").read_text()
    tree = ast.parse(src)
    assert "Path" in _bound_names(tree) or "Path(" not in src, (
        "asset_router uses Path(...) but never imports it; the render branch "
        "swallows it as a warning and the renderer never runs"
    )


def test_main_imports_update_platform_metrics():
    """It exists in crew.monetization_tracker; main must import what it calls."""
    from crew.monetization_tracker import update_platform_metrics

    tree = ast.parse((AGENTS / "main.py").read_text())
    assert "update_platform_metrics" in _bound_names(tree)


def test_documentary_job_uses_an_existing_id_helper_or_inline_format():
    """`generate_video_id()` never existed. The job now builds the id inline
    using the same `long-<date>-n<i>` convention as daily_content_job."""
    src = (AGENTS / "main.py").read_text()
    tree = ast.parse(src)
    job = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "weekly_documentary_job"
    )
    called = {
        n.func.id
        for n in ast.walk(job)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "generate_video_id" not in called, (
        "generate_video_id() is not defined anywhere in the repo — the Sunday "
        "documentary job dies on its first video"
    )
    # and it must still produce a non-empty, dated id
    dated = [
        n
        for n in ast.walk(job)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "video_id" for t in n.targets)
        and isinstance(n.value, ast.JoinedStr)
        and "%Y%m%d" in ast.unparse(n.value)
    ]
    assert dated, (
        "documentary job must build a dated video_id inline, e.g. "
        "f\"long-{datetime.utcnow().strftime('%Y%m%d')}-doc{i}\""
    )


def test_documentary_job_restores_TIER_in_a_finally():
    """The leak that made this dangerous: an abort left TIER='documentary' set
    process-wide, silently re-rendering every later job as a documentary."""
    tree = ast.parse((AGENTS / "main.py").read_text())
    job = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "weekly_documentary_job"
    )

    def has_finally(node):
        return any(
            isinstance(child, ast.Try) and child.finalbody for child in ast.walk(node)
        )

    assert has_finally(job), (
        "weekly_documentary_job sets os.environ['TIER'] and must restore it in a "
        "finally, or a mid-loop failure leaks TIER='documentary' into later jobs"
    )


def test_video_id_generation_is_unique_per_documentary_slot():
    """The loop indexes the id, so two documentaries on the same day cannot
    collide on the same temp/cache paths (the D30 class of bug)."""
    tree = ast.parse((AGENTS / "main.py").read_text())
    job = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "weekly_documentary_job"
    )
    loops = [
        n for n in ast.walk(job) if isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
    ]
    assert loops, "documentary job must iterate its planned videos"
    assert any(
        isinstance(n, ast.Call) and getattr(n.func, "id", "") == "enumerate"
        for loop in loops
        for n in ast.walk(loop)
    ), "documentary loop must enumerate so each video_id is distinct"


def test_pilot_flags_untouched_by_these_fixes():
    """The whole point of the D36 decision: this work must not re-light the
    multilingual pilot as a side effect."""
    for var, expected in (
        ("ENABLE_MULTI_LANG", "false"),
        ("ENABLE_MULTI_LANG_DUB", "false"),
        ("MULTI_LANG_CODES", "es"),
    ):
        val = os.getenv(var)
        if val is not None:
            assert val == expected, f"{var}={val}, expected {expected}"
