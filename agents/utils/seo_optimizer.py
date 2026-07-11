"""Video SEO optimization — curated tags, description enhancement, CTA scoring."""
import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CATEGORY_TAGS = {
    "AI Explained": [
        "artificial intelligence", "machine learning", "deep learning",
        "neural networks", "AI explained", "what is AI", "AI for beginners",
        "machine learning explained", "AI concepts", "artificial intelligence explained",
        "transformers", "GPT", "large language models", "AI tutorial", "learn AI",
    ],
    "Deep Tech": [
        "deep tech", "advanced AI", "machine learning research",
        "neural network architecture", "deep learning explained",
        "AI research", "technical deep dive", "algorithm", "computer science",
        "data science", "math for ML", "optimization", "backpropagation",
        "gradient descent", "attention mechanism",
    ],
    "Paper Breakdowns": [
        "research paper", "AI paper explained", "paper breakdown",
        "machine learning paper", "research explained", "academic paper",
        "AI research paper", "paper review", "deep learning paper",
        "paper summary", "latest research", "arXiv", "scientific paper",
        "conference paper", "NeurIPS",
    ],
    "Tool Tutorials": [
        "tutorial", "how to", "tool tutorial", "AI tools", "productivity",
        "beginner tutorial", "step by step", "software tutorial",
        "AI software", "tech tutorial", "tips and tricks", "workflow",
        "automation", "AI workflow", "beginner guide",
    ],
    "Industry Analysis": [
        "AI industry", "tech industry", "market analysis", "AI market",
        "industry trends", "tech business", "AI business", "startup",
        "tech companies", "industry insights", "AI adoption", "enterprise AI",
        "AI investment", "future of AI", "tech news analysis",
    ],
    "Code & Build": [
        "coding", "programming", "build with AI", "python tutorial",
        "coding tutorial", "software development", "AI coding",
        "programming tutorial", "code along", "build project",
        "github", "open source", "API tutorial", "developer tools",
        "practical AI",
    ],
    "AI News": [
        "AI news", "tech news", "latest AI", "AI update", "technology news",
        "breaking AI", "AI developments", "AI announcement", "tech update",
        "AI industry news", "AI breakthrough", "new AI model", "AI launch",
        "weekly AI news", "AI roundup",
    ],
    "Career & Learning": [
        "AI career", "tech career", "learn AI", "AI learning path",
        "career advice", "tech jobs", "AI jobs", "learning resources",
        "AI skills", "career growth", "tech skills", "AI certification",
        "study guide", "roadmap", "career development",
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
