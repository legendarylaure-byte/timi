from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_director_crew():
    llm = get_llm(temperature=0.3, max_tokens=2000)

    director = Agent(
        role="Content Director & Quality Reviewer",
        goal="Review children's content for quality, consistency, and age-appropriateness",
        backstory="""You are an experienced director of children's educational content.
You have a keen eye for quality, engagement, and educational value.
You review scripts, storyboards, and metadata to ensure every video meets
the channel's brand standards before it goes into production.
You are strict but fair — every issue you flag comes with a specific fix suggestion.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    review_task = Task(
        description="""Review the following children's video content and provide structured feedback.

Review the content against these criteria:

1. **Script Quality (40%)**
   - Age-appropriate language (target: 1-9 years old)
   - Clear educational value / learning objective
   - Strong hook in first 3 seconds
   - Pattern interrupts every 5-7 seconds
   - Proper NARRATION:/VISUAL: format (no scene markers in narration)
   - Positive, encouraging tone
   - COPPA-compliant (no personal info requests, no inappropriate content)

2. **Storyboard/Visual Consistency (30%)**
   - Visual descriptions match the narration
   - Consistent character usage
   - Appropriate scene transitions
   - Visual variety across scenes

3. **Engagement Potential (20%)**
   - Interactive elements (questions, call-and-response)
   - Emotional triggers (wonder, curiosity, joy, surprise)
   - Pacing appropriate for format (shorts: fast; long: varied)

4. **Technical Compliance (10%)**
   - No forbidden words or content
   - Proper structure for the format
   - Complete (has intro, body, outro)

Return your review as a JSON object with this exact structure:
{
  "decision": "pass" | "fix" | "block",
  "score": <0-100 integer>,
  "breakdown": {
    "script_quality": <0-100>,
    "visual_consistency": <0-100>,
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
- "block": Score < 50. Content has critical issues and should not proceed.

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
