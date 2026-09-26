import random
import re

# Titles that echo a raw news-feed or debug string instead of being written for
# a viewer. One long video published 2026-09-25 as
#   "AI News Update: GRIEF 97%x2, 91% \U0001F534 75%+ x55 \U0001F534 STREAM 392"
# -- a rolling live-blog headline carrying repetition counters, emoji, and a
# live ticker token. Emoji additionally render as .notdef boxes because the
# container fonts have no emoji glyphs (same constraint as the LIKE CTA fix).
# ponytail: neg lookbehind so "Pixel 2" is not read as the counter "x2".
_GARBAGE_TITLE_RE = re.compile(
    r"(?<![A-Za-z])x\d+"           # repetition counters: "97%x2", "x55"
    r"|[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"  # emoji / dingbats
    r"|\bSTREAM\s+\d+",             # live-blog ticker token
    re.IGNORECASE,
)


def is_garbage_title(title: str) -> bool:
    """True if a title is unusable for publication (raw feed/debug debris)."""
    t = (title or "").strip()
    if not t:
        return True
    if _GARBAGE_TITLE_RE.search(t):
        return True
    # Stat soup with no prose: mostly digits/punctuation, so not a title.
    # A false positive only costs a catchy title -- callers fall back to the
    # topic the script was actually written from.
    prose = sum(c.isalpha() or c.isspace() for c in t)
    return prose / len(t) < 0.6


TITLE_TEMPLATES = {
    "how": [
        "How {topic} in {time_period}",
        "How to {topic}: A {adjective} Guide",
        "How {topic} Changed {industry} Forever",
    ],
    "what": [
        "What {tech_giants} Know About {topic}",
        "What Happens When {topic} Goes {direction}",
        "What Is {topic}? (Explained Simply)",
    ],
    "why": [
        "Why {topic} Matters More Than Ever",
        "Why {tech_giants} Is Betting Big on {topic}",
        "Why You Should Care About {topic}",
    ],
    "number": [
        "{number} Ways {topic} Will Change {industry}",
        "{number} {topic} Tips You Need to Know",
        "Top {number} {topic} Predictions for {year}",
    ],
    "comparison": [
        "{topic} vs {alternative}: Which Is Better?",
        "{topic} vs {alternative}: The Ultimate Showdown",
    ],
}

ADJECTIVES = ["Complete", "Ultimate", "Practical", "Essential", "Advanced", "Beginner-Friendly", "Expert"]
INDUSTRIES = ["Tech", "AI", "Software Development", "Content Creation", "Machine Learning"]
TECH_GIANTS = ["Google", "OpenAI", "Meta", "Microsoft", "Apple", "Amazon"]
DIRECTIONS = ["Mainstream", "Viral", "Global", "Production"]
ALTERNATIVES = ["Traditional Methods", "The Old Way", "Manual Work", "Classic Approach"]


def generate_title_variations(base_title: str, count: int = 5) -> list:
    """Generate A/B test title variations from a base title."""
    words = base_title.split()
    topic = base_title
    if len(words) > 6:
        topic = " ".join(words[:6]) + "..."

    candidates = [base_title]
    templates_pool = []
    for group in TITLE_TEMPLATES.values():
        templates_pool.extend(group)

    random.shuffle(templates_pool)

    for template in templates_pool[:count * 2]:
        if len(candidates) >= count:
            break
        try:
            variation = template.format(
                topic=topic,
                topic_lower=topic.lower(),
                time_period=random.choice(["in 2026", "in Minutes", "Without Coding", "for Beginners"]),
                adjective=random.choice(ADJECTIVES),
                industry=random.choice(INDUSTRIES),
                tech_giants=random.choice(TECH_GIANTS),
                direction=random.choice(DIRECTIONS),
                number=str(random.randint(3, 10)),
                year="2026",
                alternative=random.choice(ALTERNATIVES),
            )
            if variation not in candidates:
                candidates.append(variation)
        except KeyError:
            continue

    return candidates[:count]


def score_title(title: str, keywords: list = None) -> dict:
    """Score a title for SEO and engagement potential."""
    length = len(title)
    has_number = any(c.isdigit() for c in title)
    has_keyword = any(k.lower() in title.lower() for k in (keywords or []))
    has_power_words = any(w in title.lower() for w in ["how", "why", "what", "best", "top", "guide", "vs", "tips"])

    score = 0
    if 30 <= length <= 70:
        score += 30
    elif length < 30:
        score += 15
    else:
        score += 10

    if has_number:
        score += 20
    if has_keyword:
        score += 25
    if has_power_words:
        score += 15

    return {
        "title": title,
        "score": score,
        "length": length,
        "has_number": has_number,
        "has_keyword": has_keyword,
        "has_power_words": has_power_words,
    }


def pick_best_title(base_title: str, keywords: list = None, count: int = 5) -> str:
    """Generate variations, score them, and return the best one."""
    variations = generate_title_variations(base_title, count)
    scored = [score_title(t, keywords) for t in variations]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[0]["title"]
