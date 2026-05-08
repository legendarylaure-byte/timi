import os
from crewai import Agent, Task, Crew
from crewai.llm import LLM

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def create_storyboard_crew(script: str = "", format_type: str = "shorts"):
    is_long = format_type == "long"
    max_tokens = 8000 if is_long else 4000

    llm = LLM(
        model=f"ollama/{OLLAMA_MODEL}",
        base_url=OLLAMA_BASE,
        temperature=0.6,
        max_tokens=max_tokens,
    )

    if is_long:
        scene_instruction = """
CRITICAL: Create EXACTLY 10-15 distinct scenes total. Each scene should be 30-60 seconds long.
DO NOT create separate scenes for "Transition to Next Scene" — transitions should be part of each main scene.
DO NOT create separate scenes for camera angles, lighting, or mood — include these as details within each main scene.
Group related actions together into single scenes. Each scene is a CONTINUOUS moment, not a bullet point."""
    else:
        scene_instruction = """
CRITICAL: Create EXACTLY 8-12 scenes total (MAXIMUM 12). Each scene should be 5-15 seconds long.
DO NOT create separate scenes for "Transition to Next Scene" — describe transitions within each main scene.
DO NOT create separate scenes for camera angles, lighting, or mood — include these as details within each main scene.
Group related actions together. A short video of 60-120 seconds can ONLY have 8-12 scenes total."""

    storyboard_artist = Agent(
        role="Storyboard Artist for Kids Animation",
        goal="Create detailed scene-by-scene visual descriptions for 3D animated children's content",
        backstory="""You are a professional storyboard artist specializing in children's 3D animation.
You translate scripts into vivid visual descriptions that animators can use directly.
Your storyboards include camera angles, character positions, color palettes, lighting,
and mood descriptions optimized for the target age group (1-9 years).""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    storyboard_task = Task(
        description=f"""Create a detailed storyboard from the following script:
{{script}}

{scene_instruction}

For EACH scene include:
1. Scene title and timing (e.g., "Scene 1: Introduction (0-10 seconds)")
2. Camera angle and movement
3. Character positions and expressions
4. Color palette and lighting
5. Background elements
6. Transition to next scene (include at the END of each scene, not as a separate scene)
7. Mood and emotional tone

NUMBER your scenes consecutively. Count them. Ensure the total matches the requirement above.
Optimize for 3D cartoon style that appeals to children aged 1-9.""",
        expected_output=f"A detailed storyboard with {'10-15' if is_long else '8-12'} scenes, each with camera angles, character positions, colors, lighting, and transitions.",  # noqa: E501
        agent=storyboard_artist,
    )

    return Crew(
        agents=[storyboard_artist],
        tasks=[storyboard_task],
        verbose=True,
    )
