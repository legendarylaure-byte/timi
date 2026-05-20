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
"""

    script_task = Task(
        description=f"""Write a script for a {format} video in the {category} category about "{topic}".

{format_instructions}

CRITICAL OUTPUT FORMAT — Follow this EXACT structure for EVERY scene:

--SCENE 1--
NARRATION: [Only the spoken words — what the voice-over actor will read aloud. This is the ONLY text that will be spoken.]
VISUAL: [Scene description for animators — camera angle, character positions, colors, actions, background details.]

--SCENE 2--
NARRATION: [Spoken text only]
VISUAL: [Visual description only]

...and so on for all scenes.

RULES (STRICT):
1. NARRATION lines contain ONLY text to be spoken aloud. No scene numbers, no timings, no descriptions.
2. VISUAL lines contain ONLY visual directions. Never spoken aloud.
3. NEVER include text like "Scene 1:" or "(0-30 seconds)" or "###" inside NARRATION.
4. Every NARRATION line WILL be read by the voice-over — so it must be complete, natural sentences.
5. Use character names in NARRATION when they speak: "PIXEL: Hello friends!" or just the dialogue.
6. Age group: 1-9 years old. Language must be simple, positive, and educational.

At the end include:
- Educational value statement (1-2 sentences)
- Call-to-action for kids to share with friends""",
        expected_output="""A complete script with each scene in EXACT format:
--SCENE 1--
NARRATION: [spoken text only]
VISUAL: [visual description only]

--SCENE 2--
NARRATION: [spoken text only]
VISUAL: [visual description only]""",
        agent=scriptwriter,
    )

    return Crew(
        agents=[scriptwriter],
        tasks=[script_task],
        verbose=True,
    )
