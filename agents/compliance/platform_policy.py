from compliance.thresholds import get_thresholds, get_platform_thresholds as _get_pt


MONETIZATION_THRESHOLDS = {
    "youtube": {
        "subs": 1000,
        "watch_hours": 4000,
        "shorts_views_90d": 10_000_000,
        "label": "YouTube Partner Program",
    },
    "tiktok": {
        "followers": 10000,
        "views_30d": 100_000,
        "label": "TikTok Creativity Program",
    },
    "instagram": {
        "followers": 10000,
        "watch_minutes_60d": 60_000,
        "label": "Instagram Partner Program",
    },
    "facebook": {
        "followers": 10000,
        "watch_minutes_60d": 60_000,
        "label": "Facebook Partner Program",
    },
}


def get_monetization_thresholds(platform: str = None) -> dict:
    try:
        all_thresholds = get_thresholds()
    except Exception:
        all_thresholds = MONETIZATION_THRESHOLDS
    if platform:
        pt = _get_pt(platform)
        label = MONETIZATION_THRESHOLDS.get(platform.lower(), {}).get("label", platform)
        return {**pt, "label": label}
    result = dict(all_thresholds)
    for p in result:
        label = MONETIZATION_THRESHOLDS.get(p, {}).get("label", p)
        result[p]["label"] = label
    return result


RESTRICTED_CONTENT = {
    "youtube": [
        "harmful_dangerous_acts",
        "hate_speech",
        "harassment_cyberbullying",
        "spam_misleading",
        "copyright_infringement",
        "violent_graphic",
    ],
    "tiktok": [
        "illegal_activities",
        "hate_speech",
        "harassment_bullying",
        "violent_extremism",
        "self_harm",
    ],
    "instagram": [
        "hate_speech",
        "bullying_harassment",
        "violence_incitement",
        "self_injury",
        "spam",
    ],
    "facebook": [
        "hate_speech",
        "violence_incitement",
        "harassment",
        "spam",
        "false_news",
    ],
}


def check_platform_compliance(video_data: dict, platform: str) -> list:
    warnings = []
    platform = platform.lower()
    policies = RESTRICTED_CONTENT.get(platform, [])
    title = (video_data.get("title") or "").lower()
    description = (video_data.get("description") or "").lower()
    script = (video_data.get("script") or "").lower()
    combined = f"{title} {description} {script}"
    red_flags = {
        "hate_speech": ["hate", "racist", "discriminat"],
        "violence_incitement": ["kill", "hurt", "attack", "violen"],
        "spam_misleading": ["click here", "free money", "get rich"],
        "copyright_infringement": ["download movie", "pirated", "cracked"],
    }
    for policy in policies:
        flags = red_flags.get(policy, [])
        if any(f in combined for f in flags):
            warnings.append(f"Potential {policy} detected for {platform}")
    return warnings
