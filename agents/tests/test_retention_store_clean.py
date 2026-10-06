"""The retention store must only ever hold real measurements.

`agents/data/retention/retention_data.json` is the file the Wave 5 learning loop
reads for per-category baselines. It shipped looking populated -- 13 KB, 64 rows
-- and every single row was pollution:

    'unit'         63 rows, video_id in {t_drop, t_hook, t_perfect}
    'AI Explained'  1 row,  video_id = "test_vid"

None of those four IDs exists in the `videos` collection. 63 were the selfcheck's
own fixtures, and the last was a probe against the live YouTube API made under a
*guessed* category name -- the dangerous kind, because a wrong label feeds a
wrong per-category average and is invisible in the file.

So this pins the mechanism, not the data: the pollution came from calling the
analyzer with persistence left on, and the data file is gitignored, so nothing
else would ever notice. Note the default is `persist=True`, so a caller must opt
OUT deliberately -- that is the direction to assert, because the failure mode is
a fixture silently becoming a baseline.
"""
import ast
import re
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]

ANALYZERS = ("analyze_retention", "pull_retention_from_youtube")
_MISSING = object()


def _called_names(path):
    """Names of analyzer/puller calls in a file.

    `node.func` may be a bare Name or an Attribute, and only the latter has
    `.attr` -- reading it unconditionally raises AttributeError on a Name.
    """
    tree = ast.parse((AGENTS / path).read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in ANALYZERS:
            found.append(node)
    return found


def _default_of(fn, arg_name):
    """The default value node for `arg_name`, or _MISSING.

    `defaults` align to the LAST len(defaults) positional args, so there is no
    `arg.default` to read -- that was the bug in the first attempt.
    """
    pos = [a.arg for a in fn.args.args]
    if arg_name not in pos:
        return _MISSING
    first_defaulted = len(pos) - len(fn.args.defaults)
    return fn.args.defaults[pos.index(arg_name) - first_defaulted]


def test_selfcheck_never_persists_its_fixtures():
    """The 63 `unit` rows came from here. Every call must opt out."""
    calls = _called_names("utils/retention_selfcheck.py")
    assert calls, "the selfcheck stopped calling the analyzer -- re-check this test"

    for call in calls:
        kws = {kw.arg: kw.value for kw in call.keywords}
        assert "persist" in kws, (
            f"line {call.lineno}: the analyzer defaults to persist=True, so this "
            f"fixture would be written into the store the learning loop reads"
        )
        value = kws["persist"]
        assert isinstance(value, ast.Constant) and value.value is False, (
            f"line {call.lineno}: persist={ast.dump(value)} -- only False is a read-only probe"
        )


def test_selfcheck_fixture_ids_are_not_shaped_like_real_ones():
    """No string literal in the selfcheck may contain an 8-digit group.

    That is precisely the rule `check_daily_volume` uses to pull a run date out
    of a video id: split on '-', take the first 8-digit chunk. So an 8-digit
    group anywhere is what makes a fixture look like a real measurement and
    could let it stand in for a run.

    An earlier version anchored the digits to the end of the string, which real
    ids never are (`short-20261005-n1` has a suffix) -- so the test passed
    against a mutation it was written to catch. Match the digit group, not the
    whole id.
    """
    source = (AGENTS / "utils" / "retention_selfcheck.py").read_text()
    tree = ast.parse(source)
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    offending = [s for s in literals if re.search(r"\d{8}", s)]
    assert not offending, (
        f"string literals containing an 8-digit group, which reads as a run date: "
        f"{offending}"
    )


def test_analyzer_defaults_are_persist_true():
    """Both entry points default to persisting, so a probe has to opt out.

    Asserting the current default makes a flip a reviewed change instead of
    something a future probe discovers by running.
    """
    tree = ast.parse((AGENTS / "utils" / "retention_analyzer.py").read_text())
    seen = set()
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name in ANALYZERS:
            seen.add(fn.name)
            default = _default_of(fn, "persist")
            assert default is not _MISSING, f"{fn.name} lost its persist parameter"
            assert isinstance(default, ast.Constant), (
                f"{fn.name}: persist default is {ast.dump(default)}, not a constant"
            )
            assert default.value is True, (
                f"{fn.name} defaults persist={default.value!r}; the safe shape is "
                f"persist=True with probes opting out"
            )
    assert seen == set(ANALYZERS), (
        f"only found {sorted(seen)} -- a rename would silently skip this guard"
    )


def test_scheduled_collector_is_the_only_persisting_caller():
    """main.py's collector is the one caller that SHOULD persist.

    If a probe is added to main.py it inherits persist=True by omission, which is
    how the guessed-category row got in. This names the intended single writer so
    a second one is a deliberate act.
    """
    calls = _called_names("main.py")
    persisting = [
        c
        for c in calls
        if not (c.keywords and any(kw.arg == "persist" for kw in c.keywords))
    ]
    assert len(persisting) == 1, (
        f"expected exactly one persist-by-default caller in main.py (the scheduled "
        f"collector), found {len(persisting)} at lines "
        f"{[c.lineno for c in persisting]}"
    )
