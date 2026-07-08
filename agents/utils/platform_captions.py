import re
import random

PERFORMANCE_HASHTAGS = {
    "youtube": {"AI Explained": ["#ArtificialIntelligence", "#MachineLearning", "#DeepLearning", "#AITrends", "#TechEducation"],
                "Code & Build": ["#Programming", "#Coding", "#SoftwareDev", "#WebDev", "#TechTutorial"],
                "Tool Tutorials": ["#Productivity", "#AITools", "#TechTips", "#Workflow", "#Automation"],
                "Deep Tech": ["#DeepTech", "#AIResearch", "#Innovation", "#FutureTech", "#TechBreakthroughs"],
                "default": ["#Tech", "#AI", "#Education", "#Learning", "#HowThingsWork"]},
    "tiktok": {"AI Explained": ["#AI", "#ArtificialIntelligence", "#TechTok", "#LearnOnTikTok", "#AITrends", "#DeepLearning", "#TechFacts", "#EdTech"],
               "Code & Build": ["#Coding", "#Programming", "#DevTok", "#CodeTok", "#SoftwareEngineer", "#BuildInPublic", "#TechTips", "#Developer"],
               "default": ["#TechTok", "#LearnOnTikTok", "#AI", "#TechFacts", "#Education", "#HowTo", "#ViralTech", "#Trending"]},
    "instagram": {"AI Explained": ["#AI", "#ArtificialIntelligence", "#MachineLearning", "#DeepLearning", "#TechReels", "#AITrends", "#FutureIsNow", "#AIGenerated", "#TechEducation", "#Innovation"],
                  "default": ["#Tech", "#AI", "#Education", "#Learning", "#HowThingsWork", "#TechTips", "#Innovation", "#Future", "#Knowledge", "#STEM"]},
    "facebook": {"AI Explained": ["#AI", "#Tech", "#Innovation", "#Future"],
                 "default": ["#AI", "#Tech", "#Innovation", "#Future"]},
}

PLATFORM_TITLE_RULES = {
    "tiktok": {"max_chars": 100, "strip_parentheses": True, "emoji_prefix": True},
    "instagram": {"max_chars": 150, "strip_parentheses": False, "emoji_prefix": True},
    "facebook": {"max_chars": 250, "strip_parentheses": False, "emoji_prefix": True},
    "youtube": {"max_chars": 300, "strip_parentheses": False, "emoji_prefix": False},
}

PLATFORM_CTAS = {
    "youtube": ["Drop a comment if you found this helpful!", "Subscribe for more AI deep dives 🔔", "Which topic should we cover next?"],
    "tiktok": ["👇 Comment 'MORE' for part 2!", "♬ Save this for later!", "Follow for daily tech insights 🔥"],
    "instagram": ["Save this post for later 📌", "Tag a friend who needs to see this! 💬", "Share your thoughts below 👇"],
    "facebook": ["What's your experience with this? Share below! 💬", "Know someone who'd love this? Tag them! 👇", "Drop a reaction if you learned something new! 👍"],
}

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


def optimize_title_for_platform(title: str, platform: str) -> str:
    rules = PLATFORM_TITLE_RULES.get(platform, PLATFORM_TITLE_RULES["youtube"])
    result = title
    if rules["strip_parentheses"]:
        result = re.sub(r'\([^)]*\)', '', result).strip()
    if rules["emoji_prefix"] and not any(c in result for c in "📌📢🤯🔥💡⚡"):
        emojis = {"tiktok": "🤯 ", "instagram": "📌 ", "facebook": "📢 "}
        result = emojis.get(platform, "") + result
    if len(result) > rules["max_chars"]:
        result = result[:rules["max_chars"] - 3].rsplit(" ", 1)[0] + "..."
    return result


def _get_platform_hashtags(category: str, platform: str, count: int) -> list[str]:
    cat_key = category if category in PERFORMANCE_HASHTAGS.get(platform, {}) else "default"
    pool = PERFORMANCE_HASHTAGS.get(platform, {}).get(cat_key, PERFORMANCE_HASHTAGS["youtube"]["default"])
    if count >= len(pool):
        return pool[:]
    return random.sample(pool, count)


def optimize_for_platform(base_title: str, base_description: str, platform: str, category: str = "AI Explained") -> str:
    """Generate a platform-optimized caption from the base description."""
    config = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["youtube"])
    selected_tags = _get_platform_hashtags(category, platform, config["hashtag_count"])
    cta = random.choice(PLATFORM_CTAS.get(platform, PLATFORM_CTAS["youtube"]))
    first_sentence = base_description.split(". ")[0] if ". " in base_description else base_description[:200]

    if platform == "youtube":
        lines = [base_description[:config["max_length"]]]
        if config["include_timestamps"]:
            lines.append("\n⏱️ Timeline:")
            lines.append("0:00 - Introduction")
            lines.append(f"0:00 - {base_title}")
            lines.append("— Full breakdown in the video —")
        lines.append("")
        lines.append(cta)
        lines.append("")
        lines.append(" ".join(selected_tags))
        return "\n".join(lines)

    elif platform == "tiktok":
        hook = f"🤯 {first_sentence[:100]}" if len(first_sentence) > 10 else f"🤯 Check this out!"
        lines = [
            hook,
            "",
            base_description[:min(300, config["max_length"] - 200)],
            "",
            cta,
            "",
            " ".join(selected_tags),
        ]
        return "\n".join(lines)

    elif platform == "instagram":
        lines = [
            base_description[:min(400, config["max_length"] - 300)],
            "",
            cta,
            "",
            " ".join(selected_tags),
        ]
        return "\n".join(lines)

    elif platform == "facebook":
        lines = [
            base_description[:min(500, config["max_length"] - 200)],
            "",
            cta,
            "",
            " ".join(selected_tags),
        ]
        return "\n".join(lines)

    return base_description[:config["max_length"]]
