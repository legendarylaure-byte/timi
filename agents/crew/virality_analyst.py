from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm

MIN_VIRALITY_SCORE = 50


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
{script[:2000] if len(script) > 2000 else script}

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

If overall_virality_score < {MIN_VIRALITY_SCORE}, recommendation should be "block".
If between {MIN_VIRALITY_SCORE} and 70, recommendation should be "review".
If above 70, recommendation should be "approve".""",
        expected_output="JSON object with virality prediction and recommendation.",
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], verbose=True)


def get_virality_threshold() -> int:
    return MIN_VIRALITY_SCORE
