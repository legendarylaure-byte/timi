import os
from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm

MIN_VIRALITY_SCORE = 40  # used for shorts
MIN_VIRALITY_SCORE_LONG = 30


def create_virality_analyst_crew(script: str = "", title: str = "", category: str = "", format_type: str = "shorts"):
    llm = get_llm(temperature=0.3, max_tokens=4000)

    analyst = Agent(
        role="Viral Content Analyst",
        goal="Predict video performance and flag content unlikely to perform well",
        backstory="""You are a data-driven content analyst who predicts video performance
before publishing. You analyze scripts, titles, and categories to estimate
CTR, retention, shareability, and comment rates. Your predictions help
avoid publishing low-performing content.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    task = Task(
        description=f"""Analyze this content and predict its viral potential:

Title: {title}
Category: {category}
Format: {format_type}

Script:
{script[:4000] if len(script) > 4000 else script}

Score each dimension 0-100:
1. Hook Strength: Does the first 3 seconds grab attention?
2. Retention Potential: Will viewers watch to the end?
3. Shareability: Will viewers share this with others?
4. Commentability: Will viewers engage in comments?
5. Estimated CTR: How clickable is the title + content combo?
6. Educational Value: How useful is this for the target audience?

Return EXACTLY this JSON:
{{
  "hook_strength": 0-100,
  "retention_potential": 0-100,
  "shareability": 0-100,
  "commentability": 0-100,
  "estimated_ctr": 0-100,
  "educational_value": 0-100,
  "overall_virality_score": 0-100,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "recommendation": "approve|review|block",
  "improvement_tips": ["tip1", "tip2"]
}}

Overall virality is weighted: hook(25%) + retention(25%) + shareability(20%) + commentability(15%) + CTR(15%)

If overall_virality_score < {get_virality_threshold(format_type)}, recommendation should be "block".
If between {get_virality_threshold(format_type)} and 70, recommendation should be "review".
If above 70, recommendation should be "approve".""",
        expected_output="JSON object with virality prediction and recommendation.",
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], verbose=True, memory=False, planning=False, cache=False)


def get_virality_threshold(format_type: str = "shorts") -> int:
    if format_type == "long":
        return int(os.getenv("MIN_VIRALITY_SCORE_LONG", str(MIN_VIRALITY_SCORE_LONG)))
    return int(os.getenv("MIN_VIRALITY_SCORE", str(MIN_VIRALITY_SCORE)))


def get_prewriting_guidance(topic: str, category: str, format_type: str = "shorts") -> str:
    """Return short virality guidance for the scriptwriter before writing.

    Uses hook_tester stats + topic scoring to suggest formula, pacing, tone.
    """
    parts = []
    try:
        from utils.hook_tester import suggest_hook_formula, get_hook_stats
        formula = suggest_hook_formula(category)
        stats = get_hook_stats(category)
        best = stats.get(formula, {})
        if best.get("count", 0) > 0:
            parts.append(f"Best hook for {category}: '{formula}' ({best['avg_views']} avg views, {best['avg_retention']:.0%} retention, {best['count']} samples)")
        else:
            parts.append(f"Suggested hook for {category}: '{formula}'")
    except Exception:
        parts.append("Suggested hook: bold_claim or question")

    if format_type == "shorts":
        parts.append("Keep script under 45s for max completion rate")
        parts.append("Open with the most surprising claim in first 3 seconds")
    else:
        from utils.pillar_manager import CPM_RATES
        cpm = CPM_RATES.get(category, 8)
        if cpm >= 15:
            parts.append(f"High-CPM category ({category}, ${cpm}/1k) — aim for 5-8 min for max revenue")

    try:
        from utils.topic_scorer import score_topic
        s = score_topic(topic, category)
        if s.viral_potential < 10:
            parts.append("Low viral potential score — add stronger hook and broader appeal")
        if s.search_demand < 10:
            parts.append("Low search demand — consider adding trending keywords or a more searchable angle")
    except Exception:
        pass

    return "VIRALITY GUIDANCE:\n" + "\n".join(f"- {p}" for p in parts)
