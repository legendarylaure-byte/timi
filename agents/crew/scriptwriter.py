from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_scriptwriter_crew(topic: str = "", category: str = "", fmt: str = "shorts", max_duration: int = 120, extra_context: str = ""):
    is_long = fmt == "long"
    max_tokens = 8000 if is_long else 4000

    llm = get_llm(temperature=0.4, max_tokens=max_tokens)

    scriptwriter = Agent(
        role="Tech Content Scriptwriter",
        goal="Create engaging, accurate, educational scripts about AI and technology topics for a non-technical beginner audience",
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

    if fmt == "long":
        format_instructions = f"""
CRITICAL: This is a LONG-FORM video ({category}). Write enough content for {max_duration} seconds.
- Write 600-1200 words for the narration.
- Include 15-20 distinct scenes, each 10-15 seconds.
- Structure: Hook (0-15s) → Context (15-60s) → Main explanation (10-14 scenes) → Summary → Outro with CTA.
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

    opt_context = f"\nOptimization note: {extra_context}" if extra_context else ""
    script_task = Task(
        description=f"""Write a script for a {fmt} video in the {category} category about "{topic}".{opt_context}

{format_instructions}

CRITICAL OUTPUT FORMAT — Follow this EXACT structure for EVERY scene:

--SCENE 1--
NARRATION: [Only the spoken words — what the voice-over narrator will read aloud]
VISUAL: [RENDER_TYPE: description]

--SCENE 2--
NARRATION: [Spoken text only]
VISUAL: [RENDER_TYPE: description]

...and so on for all scenes.

RULES (STRICT):
1. NARRATION lines contain ONLY text to be spoken aloud. No scene numbers, no timings, no descriptions.
2. VISUAL lines contain ONLY visual directions. Never spoken aloud. Start with the render type tag in brackets.
3. RENDER_TYPE must be one of: [MANIM] for diagrams, math, concepts, architecture visualizations that need precise animation; [WAN2.1] for cinematic footage, b-roll, establishing shots, background atmospherics; [CODE] for code snippets, terminal output, syntax-highlighted blocks.
4. After the tag, write a detailed text-to-video prompt: camera angle, lighting, colors, specific objects, motion, composition. Example: "[WAN2.1] Close-up of glowing neural network chip with blue neon pathways, dramatic side lighting, camera slowly dollying in"
5. NEVER include text like "Scene 1:" or "(0-30 seconds)" or "###" inside NARRATION.
6. Every NARRATION line WILL be read by the voice-over — so it must be complete, natural sentences.
7. Do NOT use character names or dialogue. This is a single-narrator educational format.
8. FACTS MUST BE ACCURATE. Do not fabricate statistics, dates, or claims. If uncertain, say "it is believed that" or "experts suggest".
9. Content is for a NON-TECHNICAL beginner audience — assume ZERO prior knowledge. Explain every specialized term from first principles using everyday analogies. Write for someone who has never heard of this topic before. Avoid jargon entirely; when a technical term is necessary, define it immediately in plain language.
10. HOOK FORMULA — Use one of these hook styles for the first scene, rotating across videos: (a) Question hook — ask a surprising question, (b) Bold claim — start with a counter-intuitive statement, (c) Statistic — lead with a striking number, (d) Curiosity gap — tease something the viewer doesn't know, (e) Pain point — name a frustration. Do NOT start with "Today we'll learn" or "In this video".
11. POWER WORDS — Include 2-3 of these naturally: "secretly", "actually", "nobody", "everyone", "the truth", "why most", "what if", "imagine", "stop", "never realized".
12. VIRAL & TRENDING — Write for maximum shareability. Use hooks that tap into current AI trends, controversies, or breakthroughs (from extra_context if provided). Structure for: surprising insight → simple breakdown → mind-blown moment. Include a curiosity gap that makes viewers NEED to watch until the end. Use the "gap frame" technique: tease the most interesting insight in the hook, then deliver it at the end.

At the end include:
- Key takeaway (1-2 sentences)
- Call-to-action (like, subscribe, comment what you want to learn next)""",
        expected_output="""A complete script with each scene in EXACT format:
--SCENE 1--
NARRATION: [spoken text only]
VISUAL: [RENDER_TYPE: description]

--SCENE 2--
NARRATION: [spoken text only]
VISUAL: [RENDER_TYPE: description]""",
        agent=scriptwriter,
    )

    return Crew(
        agents=[scriptwriter],
        tasks=[script_task],
        verbose=True,
        memory=False,
        planning=False,
        cache=False,
    )
