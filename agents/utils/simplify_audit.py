"""Enforce plain-language narration so scripts are genuinely understandable by a
non-technical (16+) audience.

Two functions:
- audit_simplify():  heuristic scan for jargon/acronyms/unnecessarily complex terms.
- simplify_rewrite(): one LLM pass that rewrites NARRATION lines into simpler wording,
  preserving scene structure. Returns the original script when nothing needs changing
  or the rewrite fails (never blocks the pipeline more than one pass).
"""

import os
import re

from utils.llm_client import generate_completion

# Terms a 16+ general audience can reasonably parse — keep them out of the "flag" list.
_ALLOWLIST = {
    "cpu", "gpu", "ram", "usb", "wifi", "wlan", "bluetooth", "pdf", "url", "link",
    "app", "apps", "microsoft", "apple", "google", "amazon", "iphone", "android",
    "tiktok", "youtube", "instagram", "facebook", "twitter", "ai", "video", "photo",
    "music", "email", "chat", "phone", "screen", "keyboard", "mouse", "battery",
    "electric", "wifi", "cloud", "smartphone", "laptop", "computer", "internet",
}

# Flag these as jargon if used bare (without an in-line plain-language explanation).
_JARGON = [
    "transformer", "neural network", "tokenization", "embedding", "latent", "diffusion",
    "backpropagation", "gradient descent", "convolution", "regression", "overfitting",
    "api", "sdk", "cli", "repository", "dependency", "containerization", "kubernetes",
    "docker", "microservice", "quantum", "entanglement", "superposition", "blockchain",
    "cryptocurrency", "hash", "protocol", "bandwidth", "serverless", "latency",
    "throughput", "schema", "endpoint", "middleware", "cache", "algorithm", "vector",
    "tensor", "parameter", "inference", "fine-tuning", "prompt engineering", "hallucination",
]

_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9+]{1,}\b")


def _narration_blocks(script: str) -> list[str]:
    blocks = []
    for m in re.finditer(r"(?m)^NARRATION:\s*(.*)$", script):
        txt = m.group(1)
        if txt.strip():
            blocks.append(txt)
    return blocks


def audit_simplify(script: str, max_flags: int = 3) -> dict:
    """Return {'passed': bool, 'issues': [str], 'terms': [str]}."""
    issues: list[str] = []
    terms: list[str] = []
    for block in _narration_blocks(script):
        lower = block.lower()
        for term in _JARGON:
            if term in lower and term not in terms:
                terms.append(term)
                issues.append(f"'{term}' used without a plain-language definition")
        for acr in _ACRONYM_RE.findall(block):
            key = acr.lower()
            if key in _ALLOWLIST or key in terms:
                continue
            if len(acr) >= 3 and not re.match(r"^\d+$", acr):
                terms.append(acr)
                issues.append(f"undefiend acronym '{acr}'")
        for word in block.split():
            letters = re.sub(r"[^A-Za-z]", "", word)
            if len(letters) > 22 and word.lower() not in _ALLOWLIST:
                terms.append(word)
                issues.append(f"overly complex word '{word}'")
    # Dedupe keeping order, cap the reported list
    seen: set[str] = set()
    unique_issues = []
    for it in issues:
        if it not in seen:
            seen.add(it)
            unique_issues.append(it)
    passed = len(unique_issues) < max_flags
    return {"passed": passed, "issues": unique_issues, "terms": terms[:12]}


def simplify_rewrite(script: str, format_type: str = "long", category: str = "") -> dict:
    """Rewrite NARRATION lines to plain language. One pass only; never blocks forever."""
    audit = audit_simplify(script)
    if audit["passed"]:
        return {"rewritten": script, "changed": False, **audit}

    term_desc = ", ".join(audit["terms"]) or "technical jargon"
    prompt = f"""Rewrite the NARRATION lines of this {format_type} video script ({category}) so a
curious 16-year-old with zero tech background understands every sentence.

- Keep the exact --SCENE-- / NARRATION: / VISUAL: structure and VISUAL lines unchanged.
- Replace jargon ({term_desc}) with everyday words or add a one-line plain explanation the
  first time each term appears.
- Preserve the hook, the topic, the length, and the educational tone.
- Return ONLY the full rewritten script with the same scene structure. No commentary."""

    try:
        rewritten = generate_completion(
            prompt=prompt + "\n\nSCRIPT:\n" + script,
            system_prompt="You simplify video narration for a general audience. Return ONLY the rewritten script.",
            temperature=0.5,
            max_tokens=16000,
            caller_id="simplify_rewrite",
        )
        if not rewritten or "--SCENE" not in rewritten:
            return {"rewritten": script, "changed": False, **audit, "error": "bad rewrite output"}
        return {"rewritten": rewritten, "changed": True, **audit}
    except Exception as e:  # pragma: no cover - defensive
        return {"rewritten": script, "changed": False, **audit, "error": str(e)}
