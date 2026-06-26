from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_scriptwriter_crew(topic: str = "", category: str = "", format: str = "shorts", max_duration: int = 120):
    is_long = format == "long"
    max_tokens = 8000 if is_long else 4000

    llm = get_llm(temperature=0.7 if is_long else 0.8, max_tokens=max_tokens)

    scriptwriter = Agent(
        role="Tech Content Scriptwriter",
        goal="Create engaging, accurate, educational scripts about AI and technology topics for a general tech audience",
        backstory="""You are an expert tech content creator specializing in educational technology videos.
You explain complex AI and tech concepts in simple, intuitive terms without oversimplifying.
Your scripts are factually accurate, well-structured, and designed for maximum retention.
You follow proven engagement patterns: strong hook in first 3 seconds, clear logical flow,
analogies that make hard concepts intuitive, and practical takeaways at the end.
You NEVER fabricate facts, statistics, or claims. If unsure, you state the uncertainty.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    if format == "long":
        format_instructions = f"""
CRITICAL: This is a LONG-FORM video ({category}). Write enough content for {max_duration} seconds.
- Write 800-1500 words for the narration.
- Include 6-10 distinct scenes, each 30-90 seconds.
- Structure: Hook (0-15s) → Context (15-60s) → Main explanation (4-7 scenes) → Summary → Outro with CTA.
- Use analogies and real-world examples to explain concepts.
- Include visual cues in VISUAL lines for: diagrams, code snippets, screen recordings, or stock footage.
- End with a clear takeaway and call-to-action (like, subscribe, comment).
"""
    else:
        format_instructions = f"""
This is a SHORT video ({category}). Fast-paced and information-dense.
- Maximum {max_duration} seconds total.
- 5-8 scenes, each 5-15 seconds.
- Hook in first 2 seconds.
- One clear concept per short video.
- End with a takeaway or curiosity hook for next video.
"""

    script_task = Task(
        description=f"""Write a script for a {format} video in the {category} category about "{topic}".

{format_instructions}

CRITICAL OUTPUT FORMAT — Follow this EXACT structure for EVERY scene:

--SCENE 1--
NARRATION: [Only the spoken words — what the voice-over narrator will read aloud]
VISUAL: [Visual description — choose from: STOCK FOOTAGE, SCREEN RECORDING, DIAGRAM ANIMATION, CODE SNIPPET, or STATIC IMAGE with description]

--SCENE 2--
NARRATION: [Spoken text only]
VISUAL: [Visual description only]

...and so on for all scenes.

RULES (STRICT):
1. NARRATION lines contain ONLY text to be spoken aloud. No scene numbers, no timings, no descriptions.
2. VISUAL lines contain ONLY visual directions. Never spoken aloud. Start with the asset type in caps.
3. NEVER include text like "Scene 1:" or "(0-30 seconds)" or "###" inside NARRATION.
4. Every NARRATION line WILL be read by the voice-over — so it must be complete, natural sentences.
5. Do NOT use character names or dialogue. This is a single-narrator educational format.
6. FACTS MUST BE ACCURATE. Do not fabricate statistics, dates, or claims. If uncertain, say "it is believed that" or "experts suggest".
7. Content is for a general tech audience — assume basic familiarity with technology but explain specialized terms.

At the end include:
- Key takeaway (1-2 sentences)
- Call-to-action (like, subscribe, comment what you want to learn next)""",
        expected_output="""A complete script with each scene in EXACT format:
--SCENE 1--
NARRATION: [spoken text only]
VISUAL: [VISUAL TYPE: description]

--SCENE 2--
NARRATION: [spoken text only]
VISUAL: [VISUAL TYPE: description]""",
        agent=scriptwriter,
    )

    return Crew(
        agents=[scriptwriter],
        tasks=[script_task],
        verbose=True,
    )
