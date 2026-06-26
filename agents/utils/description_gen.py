from utils.groq_client import generate_completion
from utils.json_utils import extract_json
from compliance.ai_disclosure import get_disclosure_text

SYSTEM_PROMPT = """You are an expert YouTube SEO specialist for technology educational content.
Generate optimized video descriptions that:
1. Include relevant tech keywords naturally for search optimization
2. Have a clear hook in the first 2 lines
3. Include timestamps/chapters for long-form content
4. Include AI-generated content disclaimer
5. Support affiliate link injection when provided

The description should be professional, informative, and optimized for YouTube's algorithm for Science & Technology content."""


def generate_description(
    title: str,
    script: str,
    category: str,
    format_type: str = "shorts",
    scenes: list = None,
    merch_links: dict = None,
    affiliate_links: list = None,
    channel_name: str = "Vyom Ai Cloud",
) -> dict:
    hook = script[:200] if len(script) > 200 else script

    chapters = ""
    if scenes and format_type == "long":
        chapters = "\n📖 Chapters:\n"
        current_time = 0
        for i, scene in enumerate(scenes):
            duration = scene.get("target_duration", 5)
            mins, secs = divmod(int(current_time), 60)
            chapters += f"{mins:02d}:{secs:02d} - {scene.get('keyword', f'Scene {i+1}')}\n"
            current_time += duration

    merch_section = ""
    if merch_links:
        merch_section = "\n🛍️ Merchandise:\n"
        for name, url in merch_links.items():
            merch_section += f"• {name}: {url}\n"

    affiliate_section = ""
    if affiliate_links:
        affiliate_section = "\n📚 Recommended Resources:\n"
        for link in affiliate_links:
            affiliate_section += f"• {link.get('name', 'Product')}: {link.get('url', '')}\n"

    ai_disclaimer = get_disclosure_text("youtube")

    prompt = f"""Generate a YouTube video description for this tech educational content:

Title: {title}
Category: {category}
Format: {format_type}
Channel: {channel_name}

Content preview:
{hook}

Generate a description that:
1. Starts with an engaging hook for tech/AI enthusiasts
2. Includes 5-8 relevant hashtags (tech-focused)
3. Clearly explains what the viewer will learn
4. Includes an AI-generated content disclaimer

Return ONLY a JSON object:
{{
  "description": "full description text",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
  "tags": ["tag1", "tag2", ...],
  "is_ai_generated": true
}}"""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=1000,
        )

        result = extract_json(response)
        if result is None:
            result = _fallback_description(title, category, format_type, hook)

        full_description = result.get("description", "")
        full_description += chapters
        full_description += merch_section
        full_description += affiliate_section
        full_description += ai_disclaimer
        full_description += f"\n\n© {channel_name}."

        result["full_description"] = full_description
        result["chapters"] = chapters.strip() if chapters else ""
        return result
    except Exception as e:
        print(f"[description_gen] Error: {e}")
        result = _fallback_description(title, category, format_type, hook)
        result["full_description"] = result.get("description", "") + chapters + merch_section
        return result


def _fallback_description(title: str, category: str, format_type: str, hook: str) -> dict:
    tags = {
        "AI Explained": ["artificial intelligence", "machine learning", "ai explained", "tech education", "deep learning"],
        "Deep Tech": ["technology explained", "how it works", "system design", "architecture", "engineering"],
        "Paper Breakdowns": ["research papers", "ai research", "machine learning papers", "academic", "breakthrough"],
        "Tool Tutorials": ["ai tools", "tutorial", "productivity", "software tutorial", "ai workflow"],
        "Industry Analysis": ["tech news", "industry trends", "ai industry", "market analysis", "future of tech"],
        "Code & Build": ["programming", "coding tutorial", "build projects", "software development", "hands-on"],
        "AI News": ["ai news", "weekly roundup", "tech updates", "latest in ai", "technology news"],
        "Career & Learning": ["tech career", "learn to code", "ai skills", "career advice", "tech jobs"],
    }

    safe_tags = tags.get(category, ["technology", "educational", "ai", "tutorial", "explainer"])
    hashtags = [f"#{category.replace(' ', '')}", "#Technology", "#AI"]

    description = f"Learn about {category.lower()} in this {format_type} explainer video.\n\n{hook[:150]}...\n\nThis educational content covers key concepts and practical insights."

    return {
        "description": description,
        "hashtags": hashtags,
        "tags": safe_tags[:15],
        "is_ai_generated": True,
    }


def get_tech_metadata(category: str, format_type: str = "shorts") -> dict:
    return {
        "madeForKids": False,
        "selfDeclaredMadeForKids": False,
        "categoryId": "28",
        "defaultLanguage": "en",
        "defaultAudioLanguage": "en",
        "privacyStatus": "public",
        "embeddable": True,
        "license": "youtube",
        "publicStatsViewable": True,
        "tags": [
            "technology",
            "artificial intelligence",
            "educational",
            category.lower(),
            "ai generated",
            "science and technology",
            "tech explainer",
            "machine learning",
        ],
    }
