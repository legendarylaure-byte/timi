from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_composer_crew(category: str = "", duration: int = 60):
    llm = get_llm(temperature=0.4, max_tokens=1000)

    composer = Agent(
        role="Children's Music Composer",
        goal="Create engaging background music that matches the emotional tone of each scene",
        backstory="""You are a music composer specializing in children's content.
You create simple, memorable melodies that are uplifting and perfectly matched
to the emotional tone of each scene. You use procedural music generation
with child-friendly tempos and instrument tones.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    music_task = Task(
        description="""Compose background music for a {category} video with duration of {duration} seconds.

Select the appropriate mood: happy, calm, adventure, bedtime, playful, exciting, or sad.
Generate a melody file path and mood selection.""",
        expected_output="Background music file path with mood and duration.",
        agent=composer,
    )

    return Crew(agents=[composer], tasks=[music_task], verbose=True)
