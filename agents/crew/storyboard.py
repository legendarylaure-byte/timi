import os
from crewai import Agent, Task, Crew

OLLAMA_MODEL = "ollama/" + os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def create_storyboard_crew():
    storyboard_artist = Agent(
        role="Storyboard Artist for Kids Animation",
        goal="Create detailed scene-by-scene visual descriptions for 3D animated children's content",
        backstory="""You are a professional storyboard artist specializing in children's 3D animation.
You translate scripts into vivid visual descriptions that animators can use directly.
Your storyboards include camera angles, character positions, color palettes, lighting,
and mood descriptions optimized for the target age group (1-9 years).""",
        llm=OLLAMA_MODEL,
        base_url=OLLAMA_BASE,
        verbose=True,
        allow_delegation=False,
    )

    storyboard_task = Task(
        description="""Create a detailed storyboard from the following script:
{script}

For each scene include:
1. Camera angle and movement
2. Character positions and expressions
3. Color palette and lighting
4. Background elements
5. Transition to next scene
6. Mood and emotional tone

Optimize for 3D cartoon style that appeals to children aged 1-9.""",
        expected_output="A detailed storyboard with camera angles, character positions, colors, lighting, and transitions for each scene.",
        agent=storyboard_artist,
    )

    return Crew(
        agents=[storyboard_artist],
        tasks=[storyboard_task],
        verbose=True,
    )
