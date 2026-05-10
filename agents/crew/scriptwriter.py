from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_scriptwriter_crew(topic: str = "", category: str = "", format: str = "shorts", max_duration: int = 120):
    is_long = format == "long"
    max_tokens = 8000 if is_long else 4000

    llm = get_llm(temperature=0.7 if is_long else 0.8, max_tokens=max_tokens)

    scriptwriter = Agent(
        role="Kids Content Scriptwriter",
        goal="Create engaging, educational, age-appropriate scripts for children aged 1-9",
        backstory="""You are an expert children's content creator specializing in educational and entertaining scripts.
You create content that is COPPA-compliant, culturally inclusive, and designed to be viral on social media.
Your scripts follow proven engagement patterns: hook in first 3 seconds, pattern interrupts every 5-7 seconds,
emotional triggers (wonder, curiosity, joy), and end with curiosity-building cliffhangers.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    if format == "long":
        format_instructions = f"""
CRITICAL: This is a LONG-FORM video. You MUST write enough content to fill at least \
{max_duration - 60} to {max_duration} seconds of narration.
- Write a MINIMUM of 1200 words for the narration/dialogue.
- Include 10-15 distinct scenes or chapters, each lasting 30-60 seconds.
- Each scene must have detailed narration, not just descriptions.
- Use storytelling with characters, dialogue, and educational explanations.
- Include interactive questions for viewers to answer.
- Add fun facts, did-you-know moments, and recap sections.
- Structure: Hook (30s) → Introduction (60s) → 10+ main scenes (30-60s each) → Recap (30s) → Outro (30s).
"""
    else:
        format_instructions = f"""
This is a SHORT video. Keep it fast-paced and visual.
- Maximum {max_duration} seconds total.
- 8-12 scenes, each 5-10 seconds.
- Quick hooks, pattern interrupts every 5-7 seconds.
- Minimal dialogue, focus on visual storytelling.
"""

    script_task = Task(
        description=f"""Write a script for a {format} video in the {category} category about "{topic}".

{format_instructions}

Include for EACH scene:
1. Scene title and timing (e.g., "Scene 1: Introduction (0-30 seconds)")
2. Detailed narration/dialogue that will be spoken out loud (this is what the voice-over will read)
3. Visual descriptions for animators
4. Emotional beats and engagement hooks
5. Character expressions and actions

At the end include:
- Educational value statement (1-2 sentences)
- Call-to-action for kids to share with friends

Age group: 1-9 years old. Language must be simple, positive, and educational.
Every scene MUST have spoken narration/dialogue — this is NOT a silent video.""",
        expected_output="A complete script with detailed narration for each scene, timing, visual descriptions, and engagement hooks.",  # noqa: E501
        agent=scriptwriter,
    )

    return Crew(
        agents=[scriptwriter],
        tasks=[script_task],
        verbose=True,
    )
