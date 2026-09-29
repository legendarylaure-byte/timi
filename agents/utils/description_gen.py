from utils.llm_client import generate_completion
from utils.json_utils import extract_json
from compliance.ai_disclosure import get_disclosure_text
import re

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
    seo_fixes: list = None,
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

    # P6: a bounded retry. score_description_seo() reports what is missing; the
    # caller passes those findings back here so the second attempt is told
    # exactly what failed. Without this the scorer was a dead log line -- it
    # reported "missing: hashtags" on every video and nothing acted on it.
    fix_block = ""
    if seo_fixes:
        fix_block = """
YOUR PREVIOUS ATTEMPT WAS SCORED AND FAILED THESE CHECKS. Fix them:
""" + "".join(f"- {f}\n" for f in seo_fixes) + """
Do not pad with filler to satisfy a check. If a check cannot be satisfied
without inventing a fact, say so in one short line and move on.
"""

    prompt = f"""Generate a YouTube video description for this tech educational content:

Title: {title}
Category: {category}
Format: {format_type}
Channel: {channel_name}

Content preview:
{hook}

CRITICAL: The first 150 characters (visible before "show more") must contain:
- The main keyword/topic
- A hook that makes people want to click
- A clear value proposition

Generate a description that:
1. Starts with an engaging hook for tech/AI enthusiasts (KEY INFO IN FIRST 150 CHARS)
2. Includes 5-8 relevant hashtags (tech-focused)
3. Clearly explains what the viewer will learn
4. Includes a short subscribe/watch-next CTA
5. Includes an AI-generated content disclaimer

Do NOT invent links, sources, citations, or statistics. Only reference material
that actually appears in the content preview above.
{fix_block}
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
    except Exception as e:
        print(f"[description_gen] Error: {e}")
        result = None

    if not isinstance(result, dict):
        result = _fallback_description(title, category, format_type, hook)

    # Fall back on the BODY only. Swapping the whole dict out would throw away
    # the LLM's other keys (seo_title, tags) whenever the body key came back
    # missing or empty, which is what the extract_json contract allows.
    body = result.get("description") or result.get("full_description") or ""
    if not body.strip():
        body = _fallback_description(title, category, format_type, hook)["description"]

    # Assembled once, OUTSIDE the try. The disclosure is a YouTube policy
    # requirement, but it used to be appended inside the try, so the except path
    # returned a description with no disclosure, no copyright line and no
    # affiliate links: an LLM outage silently un-disclosed every upload.
    full_description = body
    full_description += chapters
    full_description += merch_section
    full_description += affiliate_section
    full_description += ai_disclaimer
    full_description += f"\n\n© {channel_name}."

    result["full_description"] = full_description
    result["chapters"] = chapters.strip() if chapters else ""
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


def _extract_title_tags(title: str) -> list[str]:
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "how",
                 "what", "why", "when", "where", "who", "which", "with", "for", "and",
                 "or", "not", "of", "in", "to", "explained", "understand", "works"}
    words = re.findall(r'[A-Za-z]{4,}', title)
    return [w.lower() for w in words if w.lower() not in stopwords][:5]


def get_tech_metadata(category: str, format_type: str = "shorts", title: str = "") -> dict:
    title_tags = _extract_title_tags(title) if title else []
    base_tags = [
        "technology",
        "artificial intelligence",
        "educational",
        category.lower(),
        "ai generated",
        "science and technology",
        "tech explainer",
        "machine learning",
    ]
    all_tags = list(dict.fromkeys(title_tags + base_tags))
    # News categories map to YouTube's News & Politics (25); everything else stays
    # Science & Technology (28). Both IDs are valid. The news set is a hardcoded copy
    # of NEWS_CATS, so any category added to scene_schema silently published as 28.
    from utils.scene_schema import NEWS_CATS
    category_id = "25" if category in NEWS_CATS else "28"
    return {
        "madeForKids": False,
        "selfDeclaredMadeForKids": False,
        "categoryId": category_id,
        "defaultLanguage": "en",
        "defaultAudioLanguage": "en",
        "privacyStatus": "public",
        "embeddable": True,
        "license": "youtube",
        "publicStatsViewable": True,
        "tags": all_tags[:15],
    }
