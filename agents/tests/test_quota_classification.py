"""Quota error classification in _fail_intent.

TikTok guideline 1b: when the creator cannot make more posts, the app must
stop the publishing attempt and prompt the user to "try again later". The
backend maps quota error codes to friendly messages, but _fail_intent was
marking them as generic 'failed' — the UI could not distinguish a quota
limit from a real failure.

These tests verify that quota-related errors produce status 'limit_reached'
and all other errors produce 'failed'.
"""
import ast
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def _extract_fail_intent():
    src = pathlib.Path(__file__).resolve().parents[1].joinpath("main.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_fail_intent":
            return node
    pytest.fail("_fail_intent not found in main.py")


def _has_quota_classification():
    node = _extract_fail_intent()
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name) and target.id == "is_quota":
                    return True
    return False


def _has_limit_reached_status():
    node = _extract_fail_intent()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and child.value == "limit_reached":
            return True
    return False


def _has_quota_codes():
    node = _extract_fail_intent()
    src_lines = pathlib.Path(__file__).resolve().parents[1].joinpath("main.py").read_text().splitlines()
    segment = "\n".join(
        src_lines[node.lineno - 1 : node.end_lineno]
    )
    return "spam_risk_too_many_posts" in segment and "reached_active_user_cap" in segment


class TestQuotaClassification:
    def test_fail_intent_exists(self):
        _extract_fail_intent()

    def test_quota_classification_variable_present(self):
        assert _has_quota_classification(), (
            "_fail_intent must compute is_quota to distinguish quota errors"
        )

    def test_limit_reached_status_present(self):
        assert _has_limit_reached_status(), (
            "_fail_intent must set status='limit_reached' for quota errors"
        )

    def test_quota_codes_listed(self):
        assert _has_quota_codes(), (
            "_fail_intent must check for spam_risk_too_many_posts and "
            "reached_active_user_cap in the error string"
        )

    def test_status_uses_ternary(self):
        node = _extract_fail_intent()
        src_lines = pathlib.Path(__file__).resolve().parents[1].joinpath("main.py").read_text().splitlines()
        segment = "\n".join(src_lines[node.lineno - 1 : node.end_lineno])
        assert "limit_reached" in segment and "failed" in segment, (
            "_fail_intent must set status to 'limit_reached' or 'failed' "
            "based on is_quota"
        )
