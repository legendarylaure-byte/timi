import re
import json
from utils.llm_client import generate_completion

SAFETY_SYSTEM_PROMPT = """You are a content safety auditor for educational tech videos.
Analyze the script for potential platform policy violations.

Focus on:
1. VIOLENCE — references to real-world violence, weapons, harm (not tech metaphors like "kill process")
2. HATE SPEECH — discriminatory language, personal attacks
3. DANGEROUS — instructions for illegal/harmful activities (not educational explanations)
4. MISINFORMATION — demonstrably false health/safety claims
5. INAPPROPRIATE — profanity, explicit content

Return ONLY valid JSON:
{
  "issues": [{"type": "violence|hate_speech|dangerous|misinformation|inappropriate", "detail": "what was found", "severity": "high|medium|low"}],
  "context_cleared": ["word_or_phrase_that_is_safe_in_context"]
}

If no issues, return {"issues": [], "context_cleared": []}"""

FORBIDDEN_WORDS = {
    "violence": {"severity": "high", "allowlist": []},
    "violent": {"severity": "high", "allowlist": []},
    "scary": {"severity": "medium", "allowlist": []},
    "scared": {"severity": "medium", "allowlist": []},
    "death": {"severity": "high", "allowlist": ["death star", "heat death", "death of distance"]},
    "deadly": {"severity": "high", "allowlist": []},
    "kill": {"severity": "medium", "allowlist": ["kill process", "kill switch", "zombie kill", "kill signal", "kill -9", "kill command"]},
    "killed": {"severity": "high", "allowlist": []},
    "killing": {"severity": "high", "allowlist": []},
    "hurt": {"severity": "medium", "allowlist": []},
    "hurting": {"severity": "medium", "allowlist": []},
    "hurtful": {"severity": "high", "allowlist": []},
    "fight": {"severity": "low", "allowlist": ["fight club"]},
    "fighting": {"severity": "medium", "allowlist": ["fighting game"]},
    "war": {"severity": "medium", "allowlist": ["browser war", "console war", "format war", "trade war", "culture war", "proxy war", "price war", "streaming war", "ai war", "star wars"]},
    "warfare": {"severity": "high", "allowlist": []},
}

TRADEMARK_NAMES = [
    "apple", "google", "microsoft", "amazon", "meta", "openai",
    "tesla", "nvidia", "intel", "samsung", "ibm", "oracle",
    "salesforce", "adobe", "netflix", "spotify", "uber", "airbnb",
    "twitter", "x", "tiktok", "instagram", "facebook", "youtube",
]

SAFETY_WARNINGS = {
    "contains_forbidden": "Script contains forbidden words",
    "trademark_clickbait": "Trademark name used in clickbait context",
    "unsafe_for_platform": "Content may violate platform policies",
    "copyright_risk": "Content references potentially copyrighted material",
}


def _llm_content_safety_check(text: str) -> dict:
    try:
        response = generate_completion(
            prompt=f"Script to audit:\n\n{text[:3000]}",
            system_prompt=SAFETY_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=500,
            caller_id="content_safety_llm",
        )
        if not response:
            return {"issues": [], "context_cleared": []}
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(response[json_start:json_end])
            if isinstance(result, dict):
                return result
    except Exception:
        pass
    return {"issues": [], "context_cleared": []}


def check_content_safety(text: str, title: str = "") -> dict:
    text_lower = text.lower()
    title_lower = title.lower()
    combined = f"{title_lower} {text_lower}"
    issues = []
    for word, config in FORBIDDEN_WORDS.items():
        if not re.search(rf'\b{re.escape(word)}', combined):
            continue
        allowlisted = any(phrase in combined for phrase in config["allowlist"])
        if allowlisted:
            issues.append({
                "type": "contains_forbidden",
                "detail": f"Contains '{word}' (allowlisted context)",
                "severity": "info",
            })
        else:
            issues.append({
                "type": "contains_forbidden",
                "detail": f"Contains '{word}'",
                "severity": config["severity"],
            })
    trademark_mentions = []
    for tm in TRADEMARK_NAMES:
        if tm in combined:
            trademark_mentions.append(tm)
    if trademark_mentions:
        issues.append({
            "type": "trademark_clickbait",
            "detail": f"Mentions trademarks: {', '.join(trademark_mentions[:5])}",
            "severity": "low",
        })
    clickbait_patterns = ["you won't believe", "shocking", "mind blowing", "insane", "crazy"]
    for pattern in clickbait_patterns:
        if pattern in combined:
            issues.append({
                "type": "trademark_clickbait",
                "detail": f"Clickbait phrase detected: '{pattern}'",
                "severity": "medium",
            })
    copyright_risks = ["download", "torrent", "pirate", "crack", "keygen", "leaked"]
    for risk in copyright_risks:
        if risk in combined:
            issues.append({
                "type": "copyright_risk",
                "detail": f"Copyright risk keyword: '{risk}'",
                "severity": "medium",
            })
    is_safe = not any(i["severity"] == "high" for i in issues)

    try:
        llm_result = _llm_content_safety_check(text)
        for li in llm_result.get("issues", []):
            detail = li.get("detail", "")
            if not any(detail in i.get("detail", "") for i in issues):
                issues.append({
                    "type": li.get("type", "unknown"),
                    "detail": detail,
                    "severity": li.get("severity", "medium"),
                })
        is_safe = is_safe and not any(i["severity"] == "high" for i in issues)
    except Exception:
        pass

    return {
        "is_safe": is_safe,
        "issues": issues,
        "warning_count": len(issues),
        "high_severity_count": sum(1 for i in issues if i["severity"] == "high"),
    }


def validate_script_content(content: str) -> bool:
    content_lower = content.lower()
    for word, config in FORBIDDEN_WORDS.items():
        if config["severity"] != "high":
            continue
        if not re.search(rf'\b{re.escape(word)}\b', content_lower):
            continue
        if not any(phrase in content_lower for phrase in config["allowlist"]):
            return False
    return True
