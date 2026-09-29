"""Guard: no `.get(key, <unbound local>)` in main.py.

Why this exists (2026-09-29 incident): P6 commit 979a8dac added

    full_desc = desc_result.get("full_description", full_desc)

to BOTH `generate_short_video` and `generate_long_video`. `full_desc` is only
ever bound inside `_assemble_description`, a *different* function, so the
default argument raised `UnboundLocalError` on every single video. The 15:05 run
produced 0/5 uploads because of it.

It shipped green because 299 tests exercise the description *helpers*
(description_gen / platform_captions) and none of them run `main`'s call sites.
A test on the helper cannot see a bug in the caller -- same family as the
legacy-teal lesson, where a test read stored config while the constant lived in
source. So this asserts the call-site pattern directly, on the AST.

The fix was deleting both lines: `full_desc` was never read afterwards, every
consumer uses `desc_result.get("full_description", "")`. A deletion needs a test
that fails if someone re-adds it.
"""

import ast
import textwrap
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parents[1] / "main.py"


def _module_level_names(tree: ast.Module) -> set:
    """Names bound at module scope.

    Deliberately does NOT descend into function/lambda bodies: a local inside
    `_assemble_description` is not visible in `generate_short_video`. Sweeping
    every Store in the file into this set is what made the first version of this
    detector inert -- it saw `full_desc = ...` at line 860 (inside another
    function) and concluded the name was safely bound everywhere.
    """
    names: set = set()

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if getattr(child, "name", None):
                    names.add(child.name)
                continue  # body executes in its own scope
            if isinstance(child, ast.ClassDef):
                names.add(child.name)
                visit(child)  # class body DOES execute at module scope
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                names.add(child.id)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                for a in child.names:
                    names.add(a.asname or a.name.split(".")[0])
            elif isinstance(child, (ast.Global, ast.Nonlocal)):
                names.update(child.names)
            visit(child)

    visit(tree)
    return names


def _unbound_get_defaults(source: str, filename: str = "<test>"):
    """Return (function, lineno, target, unbound_default) for each offender.

    An offender is `X = <...>.get(<key>, X)` inside a function where `X` is not
    bound at that point. "Bound" means a module-scope name, a parameter, or an
    assignment that appears EARLIER in the same function.

    Order matters and is the whole subtlety: a name bound only *after* the line
    under test is still an UnboundLocalError at that line, and counting the
    candidate's own assignment target is self-exempting. Collecting binds
    strictly before `lineno` is what makes this actually fire.
    """
    tree = ast.parse(source, filename=filename)
    module_bound = _module_level_names(tree)

    hits = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # (lineno, name) for every binding visible inside this function.
        binds: list = []
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                binds.append((node.lineno, node.id))
            elif isinstance(node, ast.arg):
                binds.append((node.lineno, node.arg))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    binds.append((node.lineno, a.asname or a.name.split(".")[0]))
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                binds.extend((node.lineno, n) for n in node.names)

        for node in ast.walk(func):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            call = node.value
            if not isinstance(call, ast.Call):
                continue
            func_attr = call.func
            if not (isinstance(func_attr, ast.Attribute) and func_attr.attr == "get"):
                continue
            bound_before = module_bound | {n for ln, n in binds if ln < node.lineno}
            for arg in call.args[1:]:
                if isinstance(arg, ast.Name) and arg.id not in bound_before:
                    hits.append((func.name, node.lineno, target.id, arg.id))
    return hits


def test_main_py_has_no_self_referential_unbound_get_defaults():
    """The exact 2026-09-29 outage: 0/5 videos uploaded, UnboundLocalError."""
    assert MAIN_PY.exists(), f"{MAIN_PY} not found"
    source = MAIN_PY.read_text(encoding="utf-8")
    hits = _unbound_get_defaults(source, str(MAIN_PY))
    assert hits == [], (
        "Unbound `.get()` default in main.py -- this raises UnboundLocalError at "
        "runtime and killed the entire 2026-09-29 slate (0/5 published):\n  "
        + "\n  ".join(
            f"{fn}() line {ln}: {tgt} = ....get(key, {dflt})" for fn, ln, tgt, dflt in hits
        )
    )


def test_detector_flags_the_real_p6_regression():
    """Negative test: the detector must actually fire on the real bug.

    Without this, a detector that silently matches nothing would pass the test
    above for the wrong reason -- the exact trap that made the legacy-teal check
    green while three files still hardcoded the hex.

    The regression is inlined rather than read back with `git show`: the image has
    no git binary, so a git-dependent test is green on the host and RED in the
    container, which is the authoritative environment. (D39, fourth repeat.)

    Faithful to pre-fix commit 979a8dac in the four properties that matter:
      1. the self-referential `full_desc` default,
      2. a tuple-unpacking call on the line above,
      3. `full_desc` bound in a DIFFERENT function (`_assemble_description`) --
         this is precisely what made the first version of this detector inert,
         since it swept every Store in the file into one flat name set, and
      4. a subscript assign (`desc_result["tags"] = ...`), which is not a Name
         store and must not count as a binding.
    """
    pre_fix = textwrap.dedent(
        '''
        def _assemble_description(desc_result: dict, script_text: str, category: str) -> dict:
            full_desc = desc_result.get("full_description", "") or ""
            desc_result["full_description"] = full_desc
            return desc_result

        def generate_short_video(desc_result, script_text, category, best_title, topic):
            desc_result, seo_score = _seo_polish_description(
                desc_result, script_text, category, "shorts", best_title, topic)
            full_desc = desc_result.get("full_description", full_desc)
            try:
                desc_result["tags"] = get_optimized_tags(category, "shorts", best_title)
            except Exception as e:
                log_event("SEO", f"Tag generation failed: {e}", "warn")
            return desc_result

        def generate_long_video(desc_result, script_text, category, best_title, topic):
            desc_result, seo_score = _seo_polish_description(
                desc_result, script_text, category, "long", best_title, topic)
            full_desc = desc_result.get("full_description", full_desc)
            return desc_result
        '''
    )

    hits = _unbound_get_defaults(pre_fix, "main.py@979a8dac")
    offenders = {(fn, dflt) for fn, _ln, _tgt, dflt in hits}
    assert offenders == {
        ("generate_short_video", "full_desc"),
        ("generate_long_video", "full_desc"),
    }, f"detector missed the real regression, got: {sorted(offenders)}"

    # ...and the same fixture must be clean once both lines are deleted. Matched on
    # content, not indentation, since textwrap.dedent rewrites the leading spaces.
    fixed = "\n".join(
        line
        for line in pre_fix.splitlines()
        if 'get("full_description", full_desc)' not in line
    )
    assert _unbound_get_defaults(fixed, "main.py@fixed") == [], (
        "removing the dead line must clear the detector"
    )


def test_detector_ignores_legitimate_defaults():
    """Must not fire on the patterns that already exist and are correct."""
    ok = textwrap.dedent(
        '''
        import os
        DEFAULT = 5

        def uses_module_default(d):
            out = d.get("k", DEFAULT)
            return d.get("j", os.sep), out

        def uses_earlier_local(d):
            kw = "fallback"
            desc = d.get("description", kw)
            return desc

        def uses_literal(d):
            return d.get("title", ""), d.get("n", 0), d.get("f", False)
        '''
    )
    assert _unbound_get_defaults(ok) == []


def test_detector_flags_genuinely_unbound_case():
    """And it must fire on a fresh offender, so the guard is not inert."""
    bad = textwrap.dedent(
        '''
        def broken(desc_result):
            full_desc = desc_result.get("full_description", full_desc)
            return full_desc
        '''
    )
    hits = _unbound_get_defaults(bad)
    assert [(fn, dflt) for fn, _ln, _tgt, dflt in hits] == [("broken", "full_desc")]
