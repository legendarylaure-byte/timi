from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_scriptwriter_crew(topic: str = "", category: str = "", fmt: str = "shorts", max_duration: int = 120, extra_context: str = ""):
    is_long = fmt == "long"
    max_tokens = 8000 if is_long else 4000

    llm = get_llm(temperature=0.0, max_tokens=max_tokens)

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
3. RENDER_TYPE must be: [MANIM] for precise diagram animations; [LTX] for cinematic/scene footage; [CODE] for code snippets.
4. CRITICAL — Every VISUAL line MUST include ALL of: camera angle (close-up/wide/dolly/tracking/top-down/over-the-shoulder), lighting (neon glow/soft diffused/dramatic side/volumetric/rim), colors, specific objects visible, and motion. Example good: "[LTX] Close-up dolly shot of glowing processor chip with neon circuit pathways, dramatic side lighting casting long shadows, deep violet and magenta color palette, particles flowing along circuits" Example bad (NEVER write): "[LTX] Animated visualization of AI processing data" or "[LTX] Technology concept" — these are too vague to generate anything specific.
5. NEVER include text like "Scene 1:" or "(0-30 seconds)" or "###" inside NARRATION.
6. Every NARRATION line WILL be read by the voice-over — so it must be complete, natural sentences.
7. Do NOT use character names or dialogue. This is a single-narrator educational format.
8. FACTS MUST BE ACCURATE. Do not fabricate statistics, dates, or claims. If uncertain, say "it is believed that" or "experts suggest".
9. Content is for a NON-TECHNICAL beginner audience — assume ZERO prior knowledge. Explain every specialized term from first principles using everyday analogies. Write for someone who has never heard of this topic before. Avoid jargon entirely; when a technical term is necessary, define it immediately in plain language.
10. HOOK FORMULA — Use one of these hook styles for the first scene, rotating across videos: (a) Question hook — ask a surprising question, (b) Bold claim — start with a counter-intuitive statement, (c) Statistic — lead with a striking number, (d) Curiosity gap — tease something the viewer doesn't know, (e) Pain point — name a frustration. Do NOT start with "Today we'll learn" or "In this video".
11. POWER WORDS — Include 2-3 of these naturally: "secretly", "actually", "nobody", "everyone", "the truth", "why most", "what if", "imagine", "stop", "never realized".
12. VIRAL & TRENDING — Write for maximum shareability. Use hooks that tap into current AI trends, controversies, or breakthroughs (from extra_context if provided). Structure for: surprising insight → simple breakdown → mind-blown moment. Include a curiosity gap that makes viewers NEED to watch until the end. Use the "gap frame" technique: tease the most interesting insight in the hook, then deliver it at the end.
13. CRITICAL — VISUAL-NARRATION COUPLING: The NARRATION and VISUAL must describe the SAME thing at the SAME time. Every sentence in NARRATION should have a corresponding visual element. If narration says "GPUs process thousands of operations in parallel", the VISUAL must show multiple GPU cores processing operations simultaneously. The visual is NOT b-roll — it IS the explanation. Never write narration about concept A while the visual shows concept B.
14. SHOW, DON'T TELL: Narrate what the viewer sees. Instead of "the attention mechanism computes similarity scores", write "watch how each word gets a brightness score next to every other word — that's the similarity score being computed". The narration walks the viewer through what's on screen.
15. TRANSITIONS MUST BE MOTIVATED: Every VISUAL change between scenes needs a narrative reason. "Now let's zoom in on that transformer block" → VISUAL should describe a zoom. "But wait, there's a catch" → VISUAL should show a pause/highlight. Don't just cut between unrelated visuals.
16. NARRATION ARC: Follow 3Blue1Brown's narrative structure:
    - Open with a CONCRETE VISUAL PUZZLE the viewer can see — not a definition. "What does this squiggle of code actually DO?" while showing the code.
    - Build intuition with a simple example first, before any formula or technical term.
    - Use "pause and think" moments: "Think about what happens when we change this number..." while the visual pauses.
    - Reveal the insight only after the viewer has been set up to understand it.
    - End with the big picture — how this connects to the broader topic.
17. NARRATION TONE: calm, curious, conversational. Never bullet-point reading. Never "in this video we will cover" or "today we'll learn". Write like you're explaining to a curious friend over coffee.
18. Let the visual lead: the narration describes what's happening on screen in real-time. If a diagram element appears, the narration arrives with it. "Now watch this weight change..." as the weight animates.

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


def create_deep_lesson_crew(topic: str = "", category: str = "", series_title: str = "", part_number: int = 1, total_parts: int = 1, previous_summary: str = "", max_duration: int = 900, extra_context: str = ""):
    """3Blue1Brown-style deep lesson script engine.
    
    Produces 10-20 minute educational deep dives with:
    - One running example throughout
    - WHY before WHAT structure
    - Progressive complexity (start simple, build up)
    - Manim-first visual approach
    - Recap + bonus section
    - Series-aware context
    """
    llm = get_llm(temperature=0.0, max_tokens=16000)

    scriptwriter = Agent(
        role="Educational Tech Content Writer",
        goal="Create deep, intuitive explanations of AI/ML concepts that build genuine understanding, not just surface-level familiarity",
        backstory="""You are an expert educator who explains complex technical concepts with crystal clarity.
You follow the pedagogy of Grant Sanderson (3Blue1Brown): you start with what the viewer already knows,
build intuition with ONE running example before introducing any formulas, and always explain WHY
before WHAT. You never skip the foundations. You acknowledge when you're simplifying. You respect
the viewer's intelligence while assuming zero prior knowledge of this specific topic.
Your explanations make viewers feel like they truly understand, not just that they memorized facts.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    series_context = ""
    if series_title:
        if previous_summary:
            series_context = f"""
This is Part {part_number} of {total_parts} in the series "{series_title}".
Previous part summary: {previous_summary}
Start with a brief "where we left off" reference (15-30 seconds) before introducing new material.
End with a teaser for Part {part_number + 1} if {part_number} < {total_parts}."""
        else:
            series_context = f"""
This is Part 1 of {total_parts} in the series "{series_title}".
Include a 60-second series preview after the hook showing the roadmap for all {total_parts} parts."""

    format_instructions = f"""
CRITICAL: This is a DEEP LESSON video ({category}). Total duration: ~{max_duration} seconds (10-20 minutes).
- Write 2000-4000 words for the narration.
- Include 20-60 distinct scenes.
- Use this EXACT structure:

--- SECTION 1: THE HOOK (0:60s) ---
Open with a concrete example that motivates the core question.
"What does it mean for a computer to 'recognize' a handwritten digit?"
ONE concrete example runs through the ENTIRE script. Never switch examples.

--- SECTION 2: SERIES CONTEXT (60-120s) ---
{series_context}

--- SECTION 3: FOUNDATIONS (2:00-6:00) ---
Introduce the SIMPLEST concept first.
Assume ZERO prior knowledge of THIS specific concept.
Build intuition visually before introducing any term or formula.
Explain WHY we need each piece before revealing WHAT it is.
Use analogies from everyday life.

--- SECTION 4: BUILDING UP (6:00-14:00) ---
Layer complexity step by step.
Each new piece is motivated by a question or problem with the current understanding.
Show formulas term by term — build them on screen, don't reveal them all at once.
After every key reveal: pause for 2+ seconds (add <break time="2000ms"/> in narration).
Color-code consistently: Input=Blue, Weights=Green, Output=Red, Key terms=Yellow.

--- SECTION 5: THE BIG PICTURE (14:00-17:00) ---
Show how all the pieces fit together.
The "thought experiment" technique: "Imagine doing X by hand..."
Connect back to the hook example.
Show the beautiful/insightful conclusion.

--- SECTION 6: RECAP (17:00-18:00) ---
Structured summary: "Here's what we learned..."
- Point 1: [key takeaway]
- Point 2: [key takeaway]
- Point 3: [key takeaway]

--- SECTION 7: WHAT'S NEXT (18:00-19:00) ---
"In part {part_number+1}, we'll explore..."
Subscribe/comment CTA — minimal, respectful.

--- SECTION 8: BONUS (19:00-20:00) [OPTIONAL] ---
Deeper dive on one tangential aspect.
"One more thing — if you're curious about X..."
This section can be skipped by casual viewers.
"""

    opt_context = f"\nAdditional context: {extra_context}" if extra_context else ""
    script_task = Task(
        description=f"""Write a deep educational lesson script for a {category} video about "{topic}".{opt_context}

{format_instructions}

CRITICAL OUTPUT FORMAT — Follow this EXACT structure for EVERY scene:

--SCENE 1--
NARRATION: [Only the spoken words — what the voice-over narrator will read aloud]
VISUAL: [RENDER_TYPE: description]

--SCENE 2--
NARRATION: [Spoken text only]
VISUAL: [RENDER_TYPE: description]

...and so on for all scenes.

DEEP LESSON RULES:
1. NARRATION lines contain ONLY text to be spoken aloud. Write complete, natural sentences.
2. VISUAL lines start with RENDER_TYPE in brackets: [MANIM] for all diagrams, animations, equations, concept visualizations → this is PREFERRED. [LTX] only for atmospheric establishing shots between major sections. [CODE] for code snippets.
3. [MANIM] is your PRIMARY visual tool. Every explanation should have a corresponding Manim visualization. Describe the animation precisely: what transforms into what, what appears on screen, colors, layout.
4. ONE RUNNING EXAMPLE: Choose ONE concrete scenario at the start and use it throughout. Every concept should be explained in terms of this example.
5. WHY BEFORE WHAT: Before introducing any concept, first explain WHY it's needed. "But why do we need layers? Let's look at edge detection..."
6. PROGRESSIVE REVEAL: Start with the simplest version. Add complexity gradually. Never show a complete equation or diagram upfront — build it piece by piece.
7. NO VIRAL TRICKS: Do NOT use hook formulas, power words lists, or gap-frame techniques. The content's intellectual curiosity IS the hook.
8. ACKNOWLEDGE LIMITATIONS: "This is a simplification, but it helps build intuition" or "Admittedly, this is an arbitrary choice" — honesty builds trust.
9. EVERY technical term is preceded by an intuitive explanation. Never use jargon without defining it in context first.
10. END EVERY SECTION with a natural pause or summary before moving to the next.
11. CRITICAL — VISUAL-NARRATION COUPLING: The NARRATION and VISUAL must describe the SAME thing simultaneously. Every NARRATION sentence corresponds to a visible change on screen. The Manim animation IS the explanation, not a decoration. Write narration that walks the viewer through what they're seeing: "Notice how the blue line climbs as we increase the temperature — that's the probability of 'hello' rising."
12. NARRATION TIMES VISUAL: Time your narration to animation steps. "First the input vector slides in from the left [PAUSE], then the weight matrix rotates into view [PAUSE], and now watch them multiply..." Each bracketed pause corresponds to an animation step completing.
13. PROGRESSIVE VISUAL BUILDING: Never reveal the full diagram at once. Each scene adds ONE new visual element. The narration arrives at the same moment as the visual. "Now we need one more piece — the bias term" → At this exact moment, the bias term fades in on screen.

At the end include:
- 3 key takeaways in a numbered recap
- Minimal CTA: "If this kind of deep understanding is valuable to you, consider subscribing"
- A bonus insight (1-2 paragraphs) for curious viewers""",
        expected_output="""A complete deep lesson script with 20-60 scenes in EXACT format:
--SCENE 1--
NARRATION: [spoken text only]
VISUAL: [MANIM: description of animation]

--SCENE 2--
NARRATION: [spoken text only]
VISUAL: [MANIM: description of animation]

[20-60 scenes total with recap and bonus]""",
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
