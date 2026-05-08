import json
from utils.groq_client import generate_completion

SYSTEM_PROMPT = """You are an expert YouTube SEO specialist for children's content.
Generate optimized video descriptions that:
1. Are COPPA-compliant (no personalized ad links, no external tracking)
2. Include relevant keywords naturally for search optimization
3. Have a clear hook in the first 2 lines
4. Include timestamps/chapters for long-form content
5. Include age-appropriate disclaimers
6. Support merch/affiliate link injection when provided

The description should be professional, parent-friendly, and optimized for YouTube's algorithm for kids' content."""


def _extract_json(response: str) -> dict:
    """Robustly extract JSON from LLM response, handling control characters."""
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        return None

    raw = response[json_start:json_end]

    for depth in range(3):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        cleaned = ""
        in_string = False
        escaped = False
        for c in raw:
            if escaped:
                cleaned += c
                escaped = False
                continue
            if c == '\\' and in_string:
                cleaned += c
                escaped = True
                continue
            if c == '"':
                in_string = not in_string
                cleaned += c
                continue
            if in_string and ord(c) < 32 and c not in '\n\r\t':
                cleaned += ' '
                continue
            cleaned += c
        raw = cleaned

    return None


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
        affiliate_section = "\n📚 Recommended Products:\n"
        for link in affiliate_links:
            affiliate_section += f"• {link.get('name', 'Product')}: {link.get('url', '')}\n"

    prompt = f"""Generate a YouTube video description for this children's content:

Title: {title}
Category: {category}
Format: {format_type}
Channel: {channel_name}

Content preview:
{hook}

Generate a description that:
1. Starts with an engaging hook for parents
2. Includes 3-5 relevant hashtags (kid-safe)
3. Is COPPA compliant (no personalized ad references)
4. Mentions the educational value

Return ONLY a JSON object:
{{
  "description": "full description text",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
  "tags": ["tag1", "tag2", ...],
  "is_coppa_compliant": true
}}"""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=1000,
        )

        result = _extract_json(response)
        if result is None:
            result = _fallback_description(title, category, format_type, hook)

        full_description = result.get("description", "")
        full_description += chapters
        full_description += merch_section
        full_description += affiliate_section
        full_description += f"\n\n© {channel_name}. Made for Kids. COPPA Compliant."

        result["full_description"] = full_description
        result["chapters"] = chapters.strip() if chapters else ""
        return result
    except Exception as e:
        print(f"[description_gen] Error: {e}")
        result = _fallback_description(title, category, format_type, hook)
        result["full_description"] = result.get("description", "") + chapters + merch_section
        return result


def _fallback_description(title: str, category: str, format_type: str, hook: str) -> dict:
    safe_tags = {
        "Self-Learning": ["kids learning", "educational videos", "preschool learning", "toddler education", "learn at home"],  # noqa: E501
        "Bedtime Stories": ["bedtime stories", "sleep stories", "calm stories", "kids sleep", "gentle stories"],
        "Science for Kids": ["science for kids", "kids experiments", "stem learning", "fun science", "educational science"],  # noqa: E501
        "Animated Fables": ["fables for kids", "moral stories", "animated stories", "kids tales", "story time"],
        "Rhymes & Songs": ["kids songs", "nursery rhymes", "children music", "sing along", "kids entertainment"],
        "Colors & Shapes": ["colors for kids", "shapes learning", "preschool colors", "toddler learning", "educational shapes"],  # noqa: E501
    }

    tags = safe_tags.get(category, ["kids content", "children videos", "educational"])
    hashtags = [f"#{category.replace(' ', '')}", "#KidsContent", "#MadeForKids"]

    description = f"Welcome to our channel! This {format_type} video is part of our {category} series for children ages 1-9.\n\n{hook[:150]}...\n\nThis video is designed to be educational, entertaining, and safe for young viewers."  # noqa: E501

    return {
        "description": description,
        "hashtags": hashtags,
        "tags": tags[:15],
        "is_coppa_compliant": True,
    }


def get_coppa_metadata(category: str, format_type: str = "shorts") -> dict:
    return {
        "madeForKids": True,
        "selfDeclaredMadeForKids": True,
        "categoryId": "27",
        "defaultLanguage": "en",
        "defaultAudioLanguage": "en",
        "privacyStatus": "public",
        "embeddable": True,
        "license": "youtube",
        "publicStatsViewable": True,
        "tags": [
            "kids content",
            "children videos",
            "educational",
            category.lower(),
            "made for kids",
            "coppa compliant",
            "family friendly",
            "safe for kids",
        ],
    }
