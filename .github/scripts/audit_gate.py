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
import tempfile

# Resolved from THIS FILE, not from os.getcwd(). CI invokes the gate with
# working-directory: dashboard, so a bare ".github/..." default resolved to
# dashboard/.github/... and only failed once npm started reading a baseline.
# ponytail: one normpath beats making every caller remember to pass a path.
BASELINE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "dependency-audit-baseline.json"))


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


def npm_ids(doc):
    """Distinct npm advisory IDs. Normalised to str.

    Mixed int/str would make sorted() raise TypeError, which crashed the gate
    into a red job with no summary -- the exact failure this summary fixes.
    npm reports some advisories with an integer `source` and others with a
    GHSA string or a URL, so one report can genuinely contain both.
    """
    ids = set()
    for entry in doc.get("vulnerabilities", {}).values():
        for via in entry.get("via", []):
            if isinstance(via, dict):
                ids.add(str(via.get("source") or via.get("url") or "?"))
    return sorted(ids)


def pip_ids(doc):
    deps = doc.get("dependencies", doc if isinstance(doc, list) else [])
    return sorted({v["id"] for dep in deps for v in dep.get("vulns", [])})


def pip_raw_count(doc):
    """Finding INSTANCES (no dedupe). Distinct-id count is len(pip_ids(doc))."""
    deps = doc.get("dependencies", doc if isinstance(doc, list) else [])
    return sum(len(dep.get("vulns", [])) for dep in deps)


def load_baseline(path, ecosystem="python"):
    with open(path) as fh:
        return json.load(fh).get(ecosystem, {})


def self_check():
    # A baselined advisory must NOT fail -- otherwise the gate is useless.
    assert new_python_ids(["PYSEC-1"], {"PYSEC-1": "litellm"}) == []
    # A genuinely new advisory MUST fail.
    assert new_python_ids(["PYSEC-1", "PYSEC-2"], {"PYSEC-1": "litellm"}) == ["PYSEC-2"]
    # npm strict-zero: clean passes, one advisory fails.
    # str-normalised: a real report can carry int `source` and GHSA strings
    # together, and sorted() over mixed types raises TypeError.
    assert npm_ids({"vulnerabilities": {"tar": {"via": [{"source": 1}]}}}) == ["1"]
    assert npm_ids({"vulnerabilities": {"a": {"via": [{"source": "GHSA-x"}]},
                                        "b": {"via": [{"source": 2}]}}}) \
        == ["2", "GHSA-x"]
    # The default baseline must resolve regardless of cwd -- CI runs from
    # dashboard/, which is exactly how the first npm read of a baseline crashed.
    assert os.path.exists(BASELINE), f"baseline not found from cwd: {BASELINE}"
    assert load_baseline(BASELINE, "npm"), "npm baseline section missing/empty"
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
    real = sorted(load_baseline(BASELINE, "npm"))[0]
    cases = (
        ({"vulnerabilities": {}}, 0, False),
        # A baselined dev-only NO-FIX id must PASS -- the behaviour the owner
        # just approved. Without this the accept path could rot silently.
        ({"vulnerabilities": {"braces": {"via": [{"source": real}]}}}, 0, False),
        # Anything not baselined must still fail.
        ({"vulnerabilities": {"tar": {"via": [{"source": 1}]},
                              "tar2": {"via": [{"source": 2}]}}}, 1, True),
        # Baselined AND new together: the new one must still fail the job.
        ({"vulnerabilities": {"braces": {"via": [{"source": real}]},
                              "tar": {"via": [{"source": 9999}]}}}, 1, True),
    )
    for clean_doc, want_rc, want_fail in cases:
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

    # npm-prod must reject an advisory that IS in the baseline. This is the exact
    # regression of 10-05: two baselined ids were a PRODUCTION busboy advisory
    # filed under a "dev-only NO-FIX" rationale, and membership alone passed it.
    # So craft a production report carrying a baselined id and require a failure.
    baselined_id = sorted(load_baseline(BASELINE, "npm"))[0]
    prod_doc = {"vulnerabilities": {"@fastify/busboy": {
        "severity": "high", "isDirect": False,
        "via": [{"source": baselined_id}]}}}
    summ2, rep2 = tempfile.mkstemp(suffix=".json"), tempfile.mkstemp(suffix=".md")
    os.close(summ2[0]); os.close(rep2[0])
    with open(rep2[1], "w") as f:
        json.dump(prod_doc, f)
    old2 = os.environ.get("GITHUB_STEP_SUMMARY")
    os.environ["GITHUB_STEP_SUMMARY"] = summ2[1]
    rc = main(["audit_gate.py", "npm-prod", rep2[1]])
    body2 = open(summ2[1]).read()
    os.unlink(rep2[1]); os.unlink(summ2[1])
    if old2 is not None:
        os.environ["GITHUB_STEP_SUMMARY"] = old2
    assert rc == 1, f"npm-prod accepted a BASELINED id ({baselined_id}); " \
                    "production has no baseline and must not be able to use one"
    assert "| npm prod (FAIL) |" in body2, f"FAIL row missing: {body2!r}"
    # And a clean production report must pass, or the gate is unusable.
    summ3, rep3 = tempfile.mkstemp(suffix=".json"), tempfile.mkstemp(suffix=".md")
    os.close(summ3[0]); os.close(rep3[0])
    with open(rep3[1], "w") as f:
        json.dump({"vulnerabilities": {}}, f)
    old3 = os.environ.get("GITHUB_STEP_SUMMARY")
    os.environ["GITHUB_STEP_SUMMARY"] = summ3[1]
    rc3 = main(["audit_gate.py", "npm-prod", rep3[1]])
    os.unlink(rep3[1]); os.unlink(summ3[1])
    if old3 is not None:
        os.environ["GITHUB_STEP_SUMMARY"] = old3
    assert rc3 == 0, "npm-prod rejected a clean production report"
    print("  audit_gate self-check OK")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return 0
    kind, report = argv[1], argv[2]
    baseline = argv[3] if len(argv) > 3 else BASELINE
    doc = json.load(open(report))
    if kind == "npm":
        # npm was strict-zero by policy (D44). On 10-02 a new `braces` DoS
        # advisory (<=3.0.3, no upstream fix) landed and reached 8 dev-only
        # packages. Both escapes were majors the owner had already declined
        # (tailwindcss 3->4 / eslint-config-next downgrade), so the owner chose
        # to baseline the NO-FIX chain instead.
        #
        # Production npm deps stay strict-zero BY CONSTRUCTION, not by extra
        # code: only dev-chain IDs are baselined, so any advisory touching
        # something we ship is simply not in the baseline and fails as new.
        accepted = load_baseline(baseline, "npm")
        ids = npm_ids(doc)
        new = [i for i in ids if i not in accepted]
        summary("### Dependency advisories")
        summary("")
        summary("| ecosystem | distinct advisory IDs | raw findings | accepted | new |")
        summary("| --- | --- | --- | --- | --- |")
        if new:
            summary(f"| npm (FAIL) | {len(ids)} | {len(ids)} "
                    f"| {len(accepted)} | {len(new)} |")
            summary("")
            summary("New advisory IDs (npm accepts only NO-FIX/dev-only entries "
                    "-- fix these, do not baseline them):")
            summary("")
            for i in new:
                summary(f"- `{i}`")
            print(f"FAIL: {len(new)} new npm advisories "
                  f"({len(ids)} distinct, {len(accepted)} baselined)", file=sys.stderr)
            for i in new:
                print(f"  {i}", file=sys.stderr)
            print(f"  Fix them, or after review add to {BASELINE}", file=sys.stderr)
            return 1
        summary(f"| npm | {len(ids)} | {len(ids)} | {len(accepted)} | 0 |")
        if ids:
            summary("")
            summary("Baselined npm advisories are **dev-only NO-FIX** "
                    "(braces 3.0.3 is the latest published and is itself "
                    "vulnerable). No production dependency is affected.")
        print(f"  npm: {len(ids)} distinct advisory ids, all baselined "
              f"({len(accepted)} accepted)")
        return 0
    if kind == "npm-prod":
        # Strict-zero for shipped code, and NOT baselined. This exists because the
        # "only dev-chain IDs are baselined" promise was unenforced prose, and on
        # 10-05 two baselined IDs turned out to be @fastify/busboy -- a PRODUCTION
        # advisory arriving via firebase-admin -- filed under a rationale that
        # claimed they were a braces NO-FIX dev chain. Membership alone could not
        # catch that, because the ID was in the baseline. Only ever auditing the
        # full tree cannot either: a production finding and a dev finding are
        # indistinguishable there. So the production tree is audited separately
        # and nothing is accepted.
        ids = npm_ids(doc)
        summary("### Dependency advisories (production, strict-zero)")
        summary("")
        summary("| ecosystem | distinct advisory IDs | raw findings |")
        summary("| --- | --- | --- |")
        if ids:
            summary(f"| npm prod (FAIL) | {len(ids)} | {len(ids)} |")
            summary("")
            summary("Production npm dependencies must have ZERO advisories, and "
                    "there is no production baseline. Fix these:")
            summary("")
            for i in ids:
                summary(f"- `{i}`")
            print(f"FAIL: {len(ids)} advisories in production npm deps "
                  f"(no baseline by policy)", file=sys.stderr)
            for i in ids:
                print(f"  {i}", file=sys.stderr)
            return 1
        summary("| npm prod | 0 | 0 |")
        print("  npm production: 0 advisories (strict-zero, no baseline)")
        return 0
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