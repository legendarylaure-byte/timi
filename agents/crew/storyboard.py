from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_storyboard_crew(script: str = "", format_type: str = "shorts"):
    is_long = format_type == "long"
    max_tokens = 8000 if is_long else 4000

    llm = get_llm(temperature=0.6, max_tokens=max_tokens)

    if is_long:
        scene_instruction = """
CRITICAL: Create 6-10 distinct scenes. Each scene should be 30-90 seconds long.
Do NOT create separate scenes for transitions — describe them within each scene.
For each scene, specify the VISUAL ASSET TYPE to use."""
    else:
        scene_instruction = """
CRITICAL: Create 5-8 scenes total. Each scene should be 5-15 seconds long.
Do NOT create separate scenes for transitions — describe them within each scene.
For each scene, specify the VISUAL ASSET TYPE to use."""

    storyboard_artist = Agent(
        role="Visual Director for Tech Content",
        goal="Create scene-by-scene visual plans for educational tech videos using stock footage, screen captures, diagrams, and code snippets",
        backstory="""You are a professional visual director specializing in educational technology content.
You translate scripts into detailed visual plans that the video pipeline can execute.
Your storyboards specify which asset type to use per scene: stock footage for atmosphere,
screen captures for tool demonstrations, diagram animations for conceptual explanations,
and code snippets for technical deep-dives. You match visual style to content type.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    storyboard_task = Task(
        description=f"""Create a detailed visual plan from the following script:
{{script}}

{scene_instruction}

For EACH scene output:
1. Scene number and timing (e.g., "Scene 1: 0-12s")
2. ASSET TYPE: one of [STOCK_FOOTAGE, SCREEN_CAPTURE, DIAGRAM_ANIMATION, CODE_SNIPPET, STATIC_IMAGE]
3. Visual description: what the viewer sees — screen content, diagram elements, footage subject
4. Text overlay: any text that should appear on screen (titles, labels, bullet points, code)
5. Transition to next scene (cut, fade, slide)

OUTPUT FORMAT — one block per scene:
--SCENE 1 (0-12s)--
ASSET_TYPE: [STOCK_FOOTAGE | SCREEN_CAPTURE | DIAGRAM_ANIMATION | CODE_SNIPPET | STATIC_IMAGE]
VISUAL: [what the viewer sees]
TEXT_OVERLAY: [any on-screen text, or NONE]
TRANSITION: [cut | fade | slide]

NUMBER scenes consecutively. Ensure visual descriptions are specific enough for an automated pipeline to execute.""",
        expected_output=f"A detailed visual plan with {'6-10' if is_long else '5-8'} scenes, each with asset type, visual description, text overlay, and transition.",
        agent=storyboard_artist,
    )

    return Crew(
        agents=[storyboard_artist],
        tasks=[storyboard_task],
        verbose=True,
    )
