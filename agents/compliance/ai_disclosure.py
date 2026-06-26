def get_ai_disclosure(platform: str) -> dict:
    platform = platform.lower()
    if platform == "youtube":
        return {"containsSyntheticMedia": True}
    elif platform == "tiktok":
        return {"is_aigc": True}
    elif platform == "instagram":
        return {"is_ai_generated": True}
    elif platform == "facebook":
        return {"caption_hashtag": "#AI"}
    return {}


def get_disclosure_text(platform: str) -> str:
    platform = platform.lower()
    if platform == "youtube":
        return "\n\n🤖 This content was AI-generated with human oversight for accuracy."
    elif platform == "tiktok":
        return "\n\n#AI This content was created with AI assistance."
    elif platform in ("instagram", "facebook"):
        return "\n\nThis content was created with AI assistance. #AI"
    return "\n\n🤖 This content was AI-generated with human oversight for accuracy."
