#!/usr/bin/env python3
"""Fail if dependency advisories grow beyond what's explicitly accepted.

npm is gated strict-zero: the dashboard is at 0 and we want no baseline to
hide behind. Python is gated against .github/dependency-audit-baseline.json,
which holds advisories we deliberately accepted (all blocked by a declined
major/beta bump or NO-FIX upstream). New ids fail; baselined ones don't.

    audit_gate.py npm <npm-audit.json> [baseline]
    audit_gate.py pip <pip-audit.json> [baseline]
    audit_gate.py --self-check
"""
import json
import os
import sys

BASELINE = ".github/dependency-audit-baseline.json"


def summary(text):
    """Print a line, and mirror it into the Actions job summary when in CI.

    Keeps the two Python units apart on purpose. `pip_ids` dedupes, so the gate
    compares DISTINCT advisory ids on both sides. pip-audit's own headline
    number is raw finding instances, which is a different (larger) figure --
    D44 quoted 197->142 alongside a 96-id baseline without labelling which was
    which, which is exactly the confusion this summary exists to remove.
    """
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a") as fh:
        fh.write(text.rstrip() + "\n")


def new_python_ids(found, baseline):
    """Advisory ids present now but not in the accepted baseline."""
    return sorted(set(found) - set(baseline))


def npm_is_clean(doc):
    """npm gate is strict: any advisory at all fails."""
    return not doc.get("vulnerabilities")


def npm_ids(doc):
    ids = set()
    for entry in doc.get("vulnerabilities", {}).values():
        for via in entry.get("via", []):
            if isinstance(via, dict):
                ids.add(via.get("source") or via.get("url") or "?")
    return sorted(ids)


def pip_ids(doc):
    deps = doc.get("dependencies", doc if isinstance(doc, list) else [])
    return sorted({v["id"] for dep in deps for v in dep.get("vulns", [])})


def pip_raw_count(doc):
    """Finding INSTANCES (no dedupe). Distinct-id count is len(pip_ids(doc))."""
    deps = doc.get("dependencies", doc if isinstance(doc, list) else [])
    return sum(len(dep.get("vulns", [])) for dep in deps)


def load_baseline(path):
    with open(path) as fh:
        return json.load(fh).get("python", {})


def self_check():
    # A baselined advisory must NOT fail -- otherwise the gate is useless.
    assert new_python_ids(["PYSEC-1"], {"PYSEC-1": "litellm"}) == []
    # A genuinely new advisory MUST fail.
    assert new_python_ids(["PYSEC-1", "PYSEC-2"], {"PYSEC-1": "litellm"}) == ["PYSEC-2"]
    # npm strict-zero: clean passes, one advisory fails.
    assert npm_is_clean({"vulnerabilities": {}}) is True
    assert npm_is_clean({"vulnerabilities": {"tar": {}}}) is False
    assert npm_ids({"vulnerabilities": {"tar": {"via": [{"source": 1}]}}}) == [1]
    # Raw findings != distinct ids: one id can hit several packages. D44's
    # 197->142 vs 96-id-baseline confusion is exactly this, so pin both.
    dup = {"dependencies": [
        {"name": "a", "vulns": [{"id": "PYSEC-1"}, {"id": "PYSEC-1"}]},
        {"name": "b", "vulns": [{"id": "PYSEC-1"}, {"id": "PYSEC-2"}]},
    ]}
    assert pip_ids(dup) == ["PYSEC-1", "PYSEC-2"]
    assert pip_raw_count(dup) == 4
    # summary() must append to GITHUB_STEP_SUMMARY when CI sets it, and stay
    # a plain print otherwise -- otherwise the summary silently no-ops.
    import os
    import tempfile
    old = os.environ.get("GITHUB_STEP_SUMMARY")
    with tempfile.NamedTemporaryFile("w+", delete=False) as fh:
        tmp = fh.name
    os.environ["GITHUB_STEP_SUMMARY"] = tmp
    summary("hello")
    del os.environ["GITHUB_STEP_SUMMARY"]
    assert open(tmp).read().strip() == "hello"
    if old is not None:
        os.environ["GITHUB_STEP_SUMMARY"] = old
    os.unlink(tmp)

    # The FAILING npm path must also write a summary. It used to return 1 before
    # any summary() call, so a red npm job rendered a bare exit code and no
    # counts -- the one case where the summary is actually needed. Assert both
    # paths, not just the passing one.
    import json
    import tempfile
    for clean_doc, want_rc, want_fail in (
            ({"vulnerabilities": {}}, 0, False),
            ({"vulnerabilities": {"tar": {"via": [{"source": 1}]},
                                  "tar2": {"via": [{"source": 2}]}}}, 1, True),
    ):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(clean_doc, fh)
            rep = fh.name
        with tempfile.NamedTemporaryFile("w+", delete=False) as fh:
            summ = fh.name
        os.environ["GITHUB_STEP_SUMMARY"] = summ
        rc = main(["audit_gate.py", "npm", rep])
        del os.environ["GITHUB_STEP_SUMMARY"]
        body = open(summ).read()
        os.unlink(rep)
        os.unlink(summ)
        assert rc == want_rc, f"npm rc={rc} want {want_rc}"
        assert "distinct advisory IDs" in body, "summary table missing"
        assert ("| npm (FAIL) |" in body) is want_fail, \
            f"FAIL row mismatch for rc={rc}: {body!r}"
    if old is not None:
        os.environ["GITHUB_STEP_SUMMARY"] = old
    print("  audit_gate self-check OK")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return 0
    kind, report = argv[1], argv[2]
    baseline = argv[3] if len(argv) > 3 else BASELINE
    doc = json.load(open(report))
    if kind == "npm":
        clean = npm_is_clean(doc)
        ids = npm_ids(doc)
        summary("### Dependency advisories")
        summary("")
        summary("| ecosystem | distinct advisory IDs | raw findings | accepted | new |")
        summary("| --- | --- | --- | --- | --- |")
        if clean:
            summary("| npm | 0 | 0 | 0 (strict-zero, no baseline) | 0 |")
            return 0
        # npm has no baseline, so every advisory id is by definition "new" and
        # must be fixed, never baselined. Emitting this BEFORE returning 1 is
        # the whole point: a red job that writes no summary leaves the engineer
        # with a bare exit code and nothing to act on.
        summary(f"| npm (FAIL) | {len(ids)} | {len(ids)} "
                f"| 0 (strict-zero, no baseline) | {len(ids)} |")
        summary("")
        summary("New advisory IDs (npm has no baseline -- fix, do not baseline):")
        summary("")
        for i in ids:
            summary(f"- `{i}`")
        print(f"FAIL: {len(ids)} npm advisories; npm must be zero", file=sys.stderr)
        for i in ids[:20]:
            print(f"  {i}", file=sys.stderr)
        return 1
    if kind == "pip":
        accepted = load_baseline(baseline)
        new = new_python_ids(pip_ids(doc), accepted)
        total = len(pip_ids(doc))
        raw = pip_raw_count(doc)
        summary("### Dependency advisories")
        summary("")
        summary("| ecosystem | distinct advisory IDs | raw findings | accepted | new |")
        summary("| --- | --- | --- | --- | --- |")
        row = (f"| python | {total} | {raw} | {len(accepted)} | {len(new)} |")
        if new:
            summary(row.replace("| python |", "| python (FAIL) |"))
            summary("")
            summary("New advisory IDs (add to the baseline only after review):")
            summary("")
            for i in new:
                summary(f"- `{i}`")
        else:
            summary(row)
            summary("")
            summary("Gate **passing**: every advisory ID is in the accepted baseline.")
        if new:
            print(f"FAIL: {len(new)} new python advisories "
                  f"({total} distinct ids, {raw} raw findings, {len(accepted)} baselined)",
                  file=sys.stderr)
            for i in new:
                print(f"  {i}", file=sys.stderr)
            print(f"  Fix them, or after review add to {BASELINE}", file=sys.stderr)
            return 1
        print(f"  python: {total} distinct advisory ids "
              f"({raw} raw findings), all baselined ({len(accepted)} accepted)")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))