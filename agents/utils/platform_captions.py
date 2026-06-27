import random

PLATFORM_PROMPTS = {
    "youtube": {
        "max_length": 5000,
        "style": "informative and search-optimized with timestamps and resource links",
        "hashtag_count": 5,
        "include_timestamps": True,
    },
    "tiktok": {
        "max_length": 2200,
        "style": "trendy, punchy, with viral hooks and popular sound mentions",
        "hashtag_count": 8,
        "include_timestamps": False,
    },
    "instagram": {
        "max_length": 2200,
        "style": "storytelling with line breaks, emojis, and community hashtags",
        "hashtag_count": 10,
        "include_timestamps": False,
    },
    "facebook": {
        "max_length": 5000,
        "style": "conversational and community-oriented with questions to drive engagement",
        "hashtag_count": 3,
        "include_timestamps": False,
    },
}

TECH_HASHTAGS = {
    "ai": ["#ArtificialIntelligence", "#MachineLearning", "#DeepLearning", "#AI", "#Tech"],
    "coding": ["#Programming", "#Coding", "#SoftwareEngineering", "#Dev", "#TechTips"],
    "tools": ["#Productivity", "#Tools", "#TechTools", "#Workflow", "#Automation"],
    "news": ["#TechNews", "#Innovation", "#FutureTech", "#DigitalTransformation", "#AIRevolution"],
}


def optimize_for_platform(base_title: str, base_description: str, platform: str, category: str = "AI Explained") -> str:
    """Generate a platform-optimized caption from the base description."""
    config = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["youtube"])
    hashtag_pool = TECH_HASHTAGS.get(category.split()[0].lower() if category else "ai", TECH_HASHTAGS["ai"])
    selected_tags = random.sample(hashtag_pool, min(config["hashtag_count"], len(hashtag_pool)))

    first_sentence = base_description.split(". ")[0] if ". " in base_description else base_description[:200]

    if platform == "youtube":
        lines = [base_description[:config["max_length"]]]
        if config["include_timestamps"]:
            lines.append("\n⏱️ Timeline:")
            lines.append("0:00 - Introduction")
            lines.append(f"0:00 - {base_title}")
            lines.append("— Full breakdown in the video —")
        lines.append("\n" + " ".join(selected_tags[:5]))
        return "\n".join(lines)

    elif platform == "tiktok":
        hook = f"🤯 {first_sentence[:100]}" if len(first_sentence) > 10 else f"🤯 Check this out!"
        lines = [
            hook,
            "",
            base_description[:min(300, config["max_length"] - 200)],
            "",
            "👇 Drop a comment if you agree!",
            "",
            " ".join(selected_tags[:8]),
        ]
        return "\n".join(lines)

    elif platform == "instagram":
        lines = [
            f"📌 {base_title}",
            "",
            base_description[:min(400, config["max_length"] - 300)],
            "",
            "💬 What do you think? Share your thoughts below!",
            "",
            " ".join(selected_tags[:10]),
        ]
        return "\n".join(lines)

    elif platform == "facebook":
        lines = [
            f"📢 {base_title}",
            "",
            base_description[:min(500, config["max_length"] - 200)],
            "",
            "💭 What's your take on this? Let's discuss in the comments!",
            "",
            " ".join(selected_tags[:3]),
        ]
        return "\n".join(lines)

    return base_description[:config["max_length"]]
