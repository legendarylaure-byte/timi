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
import sys

BASELINE = ".github/dependency-audit-baseline.json"


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
    print("  audit_gate self-check OK")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return 0
    kind, report = argv[1], argv[2]
    baseline = argv[3] if len(argv) > 3 else BASELINE
    doc = json.load(open(report))
    if kind == "npm":
        if not npm_is_clean(doc):
            ids = npm_ids(doc)
            print(f"FAIL: {len(ids)} npm advisories; npm must be zero", file=sys.stderr)
            for i in ids[:20]:
                print(f"  {i}", file=sys.stderr)
            return 1
        print("  npm: 0 advisories")
        return 0
    if kind == "pip":
        accepted = load_baseline(baseline)
        new = new_python_ids(pip_ids(doc), accepted)
        total = len(pip_ids(doc))
        if new:
            print(f"FAIL: {len(new)} new python advisories "
                  f"({total} total, {len(accepted)} baselined)", file=sys.stderr)
            for i in new:
                print(f"  {i}", file=sys.stderr)
            print(f"  Fix them, or after review add to {BASELINE}", file=sys.stderr)
            return 1
        print(f"  python: {total} advisories, all baselined ({len(accepted)} accepted)")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))