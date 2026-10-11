"""Prompt-content guards for the scriptwriter (WS5 Phase 3).

The "script point" the channel was failing on: scripts narrated generic topic
overviews with visuals that did not match the words. The fix lives in prompt
rules, so the guard works on the prompt strings themselves -- AST-extracted
string literals, NOT a text grep, so a rule that survives only inside a comment
does not count as present (the legacy-teal lesson: read the source, and read
the *right* part of it).

This file imports nothing from crewai/langchain on purpose: it parses
crew/scriptwriter.py as text. That keeps it green on the host, where the
crewai chain is absent.
"""
import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "crew" / "scriptwriter.py"

# Distinctive phrases, one per rule, so a deletion names exactly what left.
FOOTAGE_FIRST_RULES = {
    "shorts/coupling (rule 13)": "VISUAL-NARRATION COUPLING",
    "shorts/show-dont-tell (rule 14)": "SHOW, DON'T TELL",
    "shorts/narration-arc (rule 16)": "NARRATION ARC",
    "shorts/narration-tone (rule 17)": "NARRATION TONE",
    "shorts/let-visual-lead (rule 18)": "Let the visual lead",
    "shorts/specific-angle (rule 19)": "SPECIFIC ANGLE",
    "deep/footage-is-explanation (rule 11)": "footage IS the explanation",
    "deep/narration-times-visual (rule 12)": "NARRATION TIMES VISUAL",
    "deep/progressive-visual-build (rule 13)": "PROGRESSIVE VISUAL BUILDING",
    "deep/open-with-a-real-hook (rule 7)": "OPEN WITH A REAL HOOK",
}


def _prompt_text() -> str:
    tree = ast.parse(SRC.read_text())
    parts = [n.value for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return "\n".join(parts)


def test_every_footage_first_rule_is_present():
    text = _prompt_text()
    missing = [name for name, phrase in FOOTAGE_FIRST_RULES.items() if phrase not in text]
    assert not missing, f"missing footage-first rules: {missing}"


def test_deep_lesson_no_longer_forbids_hooks():
    # Phase 3 turned long-form hooks ON: the old blanket ban is gone, the new
    # rule keeps the anti-gimmick line but AFTER the hook.
    text = _prompt_text()
    assert "NO VIRAL TRICKS" not in text, "deep rule 7 still bans hooks outright"
    assert "OPEN WITH A REAL HOOK" in text


def test_angle_rule_marks_a_supplied_angle_mandatory():
    text = _prompt_text()
    assert "SPECIFIC ANGLE" in text
    assert "MANDATORY" in text, "a supplied angle must be obligatory, not a suggestion"


def test_generic_topic_overview_is_named_as_forbidden():
    text = _prompt_text()
    assert 'never a generic "What is X?" topic overview' in text


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
