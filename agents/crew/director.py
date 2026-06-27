from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_director_crew():
    llm = get_llm(temperature=0.3, max_tokens=4000)

    director = Agent(
        role="Tech Content Director & Quality Reviewer",
        goal="Review tech educational content for factual accuracy, clarity, engagement, and production quality",
        backstory="""You are an experienced director of educational technology content.
You have a keen eye for factual accuracy, explanation clarity, and viewer engagement.
You review scripts and storyboards to ensure every video is informative, accurate,
and accessible to a general tech audience. You are strict but fair — every issue
you flag comes with a specific fix suggestion. You prioritize truthfulness over hype.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    review_task = Task(
        description="""Review the following tech educational video content and provide structured feedback.

Review the content against these criteria:

1. **Script Quality (40%)**
   - FACTUAL ACCURACY: No false or misleading claims. If uncertain, it must be stated as opinion.
   - Clear learning objective: viewer should understand X after watching
   - Strong hook in first 3 seconds
   - Logical flow: concepts build on each other naturally
   - Proper NARRATION:/VISUAL: format (no scene markers in narration)
   - Accessible language: explains jargon, assumes tech-curious audience

2. **Visual Plan Effectiveness (30%)**
   - ASSET_TYPE choices match the narration content
   - Visual descriptions are specific enough for pipeline execution
   - Appropriate variety across scenes (not all stock footage)
   - Text overlays reinforce key points

3. **Engagement Potential (20%)**
   - Strong hook that creates curiosity
   - Clear pacing appropriate for format (shorts: fast; long: varied)
   - Practical takeaways for the viewer
   - Effective call-to-action

4. **Technical Compliance (10%)**
   - No fabricated statistics, dates, or claims
   - Proper NARRATION/VISUAL scene structure
   - Complete (has hook, body, conclusion)
   - Appropriate length for format

Return your review as a JSON object with this exact structure:
{
  "decision": "pass" | "fix" | "block",
  "score": <0-100 integer>,
  "breakdown": {
    "script_quality": <0-100>,
    "visual_effectiveness": <0-100>,
    "engagement": <0-100>,
    "technical": <0-100>
  },
  "issues": [
    {"severity": "critical" | "major" | "minor", "category": "<area>", "description": "<specific issue>", "suggestion": "<how to fix>"}
  ],
  "strengths": ["<strength 1>", "<strength 2>"],
  "feedback": "<2-3 sentence summary of the review>",
  "overall_score": <0-100>
}

Decisions:
- "pass": Score >= 75. Content is ready for production.
- "fix": Score 50-74. Content has issues that must be addressed before proceeding.
- "block": Score < 50. Content has critical factual errors or structural problems.

Content to review:
SCRIPT:
{script}

STORYBOARD:
{storyboard}

CATEGORY: {category}
FORMAT: {format}
TOPIC: {topic}""",
        expected_output="""JSON object with: decision, score, breakdown, issues, strengths, feedback, overall_score""",
        agent=director,
    )

    return Crew(
        agents=[director],
        tasks=[review_task],
        verbose=True,
    )
