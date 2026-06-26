FORBIDDEN_WORDS = ["violence", "scary", "death", "kill", "hurt", "fight", "war"]

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


def check_content_safety(text: str, title: str = "") -> dict:
    text_lower = text.lower()
    title_lower = title.lower()
    combined = f"{title_lower} {text_lower}"
    issues = []
    for word in FORBIDDEN_WORDS:
        if word in combined:
            issues.append({"type": "contains_forbidden", "detail": f"Contains '{word}'", "severity": "high"})
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
    return {
        "is_safe": is_safe,
        "issues": issues,
        "warning_count": len(issues),
        "high_severity_count": sum(1 for i in issues if i["severity"] == "high"),
    }


def validate_script_content(content: str) -> bool:
    content_lower = content.lower()
    return not any(word in content_lower for word in FORBIDDEN_WORDS)
