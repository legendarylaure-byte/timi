"""Video SEO optimization — curated tags, description enhancement, CTA scoring."""
import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Keys must be VALID_CATEGORIES from utils.scene_schema. These used to be keyed on
# "AI Explained"/"Deep Tech"/"Paper Breakdowns"/"Tool Tutorials"/"Industry Analysis"/
# "Code & Build"/"Career & Learning" — all deleted back in D24, so every lookup missed
# and every video fell back to the same generic BASE_TAGS. Old tag pools are merged
# into the surviving categories so nothing valuable was lost.
CATEGORY_TAGS = {
    "AI News": [
        "AI news", "tech news", "latest AI", "AI update", "technology news",
        "breaking AI", "AI developments", "AI announcement", "tech update",
        "AI industry news", "AI breakthrough", "new AI model", "AI launch",
        "artificial intelligence", "machine learning", "GPT",
        "large language models", "AI industry", "tech industry", "market analysis",
        "industry trends", "AI adoption", "future of AI",
    ],
    "Science & Technology": [
        "artificial intelligence", "machine learning", "deep learning",
        "neural networks", "AI explained", "what is AI", "AI for beginners",
        "machine learning explained", "AI concepts", "transformers",
        "AI tutorial", "learn AI", "deep tech", "advanced AI",
        "machine learning research", "neural network architecture",
        "AI research", "technical deep dive", "algorithm", "computer science",
        "data science", "math for ML", "attention mechanism",
        "research paper", "AI paper explained", "paper breakdown",
        "AI research paper", "paper review", "latest research", "arXiv",
        "scientific paper", "conference paper", "NeurIPS",
    ],
    "Programming & Software": [
        "coding", "programming", "build with AI", "python tutorial",
        "coding tutorial", "software development", "AI coding",
        "programming tutorial", "code along", "build project",
        "github", "open source", "API tutorial", "developer tools",
        "practical AI", "tutorial", "how to", "AI tools", "step by step",
        "software tutorial", "AI software", "tech tutorial", "workflow",
        "automation", "beginner guide", "AI learning path", "learning resources",
    ],
    "World News (24hr)": [
        "world news", "breaking news", "global news", "today in news",
        "current events", "news explained", "headlines", "international news",
    ],
    "Nepal News": [
        "Nepal news", "Nepal", "news from Nepal", "Kathmandu",
        "Nepali news", "current affairs Nepal", "Nepal headlines",
        "Nepal politics", "Nepal economy", "नेपाल",
    ],
}

BASE_TAGS = ["technology", "educational", "science and technology", "tech explainer", "vyom-ai-cloud"]

CTA_PATTERNS = [
    r"subscribe", r"follow", r"like", r"share", r"comment",
    r"check\s+out", r"click\s+the", r"hit\s+that", r"ring\s+the",
    r"join\s+", r"support", r"don't\s+forget", r"let\s+me\s+know",
]

HASHTAG_PATTERNS = [
    r"#\w+",
]

LINK_PATTERNS = [
    r"https?://",
    r"www\.\w+",
]


def get_optimized_tags(category: str, format_type: str = "long", title: str = "") -> list[str]:
    """Get SEO-optimized tags for a video based on category."""
    tags = list(BASE_TAGS)
    category_lower = category.lower()

    if category in CATEGORY_TAGS:
        tags.extend(CATEGORY_TAGS[category])
    else:
        tags.append(category_lower)

    if format_type == "shorts":
        tags.extend(["shorts", "youtube shorts", "short video", "quick explainer"])
    else:
        tags.extend(["long form", "in depth", "detailed explanation"])

    if title:
        title_words = [w for w in title.lower().split() if len(w) > 3]
        for w in title_words:
            if w not in tags and len(tags) < 15:
                tags.append(w)

    return list(dict.fromkeys(tags))[:15]


def score_description_seo(description: str) -> dict:
    """Score a description for SEO completeness."""
    if not description:
        return {"score": 0, "missing": ["description"], "has_cta": False, "has_hashtags": False, "has_links": False}

    missing = []
    has_cta = any(re.search(p, description.lower()) for p in CTA_PATTERNS)
    has_hashtags = any(re.search(p, description) for p in HASHTAG_PATTERNS)
    has_links = any(re.search(p, description) for p in LINK_PATTERNS)

    if not has_cta:
        missing.append("call to action")
    if not has_hashtags:
        missing.append("hashtags")
    if not has_links:
        missing.append("links")

    score = 100
    score -= (len(missing) * 20)
    if len(description) < 200:
        score -= 20
    if len(description) > 2000:
        score -= 10

    return {
        "score": max(0, score),
        "missing": missing,
        "has_cta": has_cta,
        "has_hashtags": has_hashtags,
        "has_links": has_links,
        "length": len(description),
    }


def suggest_seo_improvements(category: str, format_type: str) -> list[str]:
    """Generate SEO improvement suggestions."""
    suggestions = []

    tags = get_optimized_tags(category, format_type)
    suggestions.append(f"Target tags: {', '.join(tags[:5])}...")

    if format_type == "shorts":
        suggestions.append("Add #Shorts hashtag in first line of description")
    else:
        suggestions.append("Include timestamps for key sections in description")
        suggestions.append("Add chapters with timestamps (00:00 Intro, 01:30 Topic...)")

    suggestions.append("End description with a question to boost comment engagement")
    suggestions.append('Include "Subscribe for more" CTA in first 2 lines')

    return suggestions
