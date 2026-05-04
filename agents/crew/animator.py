import os
from crewai import Agent, Task, Crew

OLLAMA_MODEL = "ollama/" + os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def create_animator_crew():
    animator = Agent(
        role="Animation Clip Director",
        goal="Select and arrange real stock video clips that match each scene of the script",
        backstory="""You are an expert at finding the perfect video footage for children's stories.
You analyze each scene and choose video clips from Pexels/Pixabay stock library
that have real motion - animals moving, nature scenes, kids playing, etc.
You avoid static images and prefer clips with smooth, continuous movement.""",
        llm=OLLAMA_MODEL,
        base_url=OLLAMA_BASE,
        verbose=True,
        allow_delegation=False,
    )

    animation_task = Task(
        description="""Analyze this storyboard and create a scene plan with search keywords for stock video:
{storyboard}

Format: {format}

For EACH scene, output:
1. Scene keyword (for stock video search)
2. Target duration (in seconds)
3. Description of motion needed (what action happens)

Output as JSON array: [{"keyword": "...", "target_duration": N, "description": "..."}]""",
        expected_output="JSON array of scenes with keyword, target_duration, and description.",
        agent=animator,
    )

    return Crew(agents=[animator], tasks=[animation_task], verbose=True)
