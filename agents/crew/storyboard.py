from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_storyboard_crew(script: str = "", format_type: str = "shorts", is_deep: bool = False):
    is_long = format_type == "long"
    max_tokens = 8000 if is_long else 4000

    llm = get_llm(temperature=0.0, max_tokens=max_tokens, agent_id="storyboard")

    if is_deep:
        scene_instruction = """
CRITICAL: Create 20-60 distinct scenes. Each scene should be 5-12 seconds long.
Do NOT create separate scenes for transitions — describe them within each scene.
For each scene, specify the RENDER_TYPE and VISUAL ASSET TYPE to use."""
    elif is_long:
        scene_instruction = """
CRITICAL: Match the script's scene count (typically 12-18 scenes). Each scene should be 8-15 seconds.
Do NOT create separate scenes for transitions — describe them within each scene.
For each scene, specify the RENDER_TYPE and VISUAL ASSET TYPE to use."""
    else:
        scene_instruction = """
CRITICAL: Create 5-8 scenes total. Each scene should be 5-15 seconds long.
Do NOT create separate scenes for transitions — describe them within each scene.
For each scene, specify the RENDER_TYPE and VISUAL ASSET TYPE to use."""

    storyboard_artist = Agent(
        role="Visual Director for Tech Content",
        goal="Create scene-by-scene visual plans for educational tech videos using cinematic stock footage and diagrams",
        backstory="""You are a professional visual director specializing in educational technology content.
You translate scripts into detailed visual plans that the video pipeline can execute.
Your storyboards specify the topic and shot for each scene and lean on cinematic real-world
b-roll of the actual subject. You match visual style to content type.
You specify camera angles, lighting, and composition to ensure each scene is visually engaging.

IMPORTANT: Vary the SUBJECT and shot across scenes so consecutive scenes do not look alike.
On-screen code cards and screen-capture panels are NOT used -- every scene is real footage.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    storyboard_task = Task(
        description=f"""Create a detailed visual plan from the following script:
{{script}}

{scene_instruction}

PRESERVE the RENDER_TYPE tags from the script's VISUAL lines: [LTX] for cinematic/b-roll. Code-snippet scenes are not used; if a [CODE] tag appears, treat it as [LTX].

For EACH scene output:
1. Scene number and timing (e.g., "Scene 1: 0-12s")
2. RENDER_TYPE: [LTX]
3. ASSET TYPE: STOCK_FOOTAGE (STATIC_IMAGE only as a rare branded card)
4. Visual description: what the viewer sees — screen content, diagram elements, footage subject
5. Camera angle: specify the shot type (e.g., close-up on hands typing, wide shot of server room, over-the-shoulder at monitor, top-down of circuit board, dolly-in on neural network visualization, smooth pan across architecture diagram, macro shot of chip components)
6. Lighting: specify lighting style (e.g., dramatic side lighting, soft diffused overhead, neon glow from screens, warm key light with cool fill, volumetric god rays through server vents, rim lighting on subject, cinematic low-key for mystery)
7. Text overlay: any text that should appear on screen (titles, labels, bullet points, code)
8. Transition to next scene (cut, fade, slide)

OUTPUT FORMAT — one block per scene:
--SCENE 1 (0-12s)--
RENDER_TYPE: [LTX]
ASSET_TYPE: [STOCK_FOOTAGE | STATIC_IMAGE]
VISUAL: [what the viewer sees]
CAMERA: [shot type, camera movement]
LIGHTING: [lighting style]
TEXT_OVERLAY: [any on-screen text, or NONE]
TRANSITION: [cut | fade | slide]

Visual descriptions MUST be vivid and specific enough for an AI video generation model to interpret: describe colors, composition, movement, and focal points. For example, instead of "a person using a computer" say "a developer in a dark room with neon blue screen glow on their face, typing rapidly, camera slowly dollying in on the monitor showing streaming code". NUMBER scenes consecutively.""",
        expected_output=f"A detailed visual plan with {'6-10' if is_long else '5-8'} scenes, each with asset type, visual description, camera angle, lighting, text overlay, and transition.",
        agent=storyboard_artist,
    )

    return Crew(
        agents=[storyboard_artist],
        tasks=[storyboard_task],
        verbose=True,
        memory=False,
        planning=False,
        cache=False,
    )
