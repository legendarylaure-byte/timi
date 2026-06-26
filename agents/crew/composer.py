from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_composer_crew(category: str = "", duration: int = 60):
    llm = get_llm(temperature=0.4, max_tokens=1000)

    composer = Agent(
        role="Tech Music Composer",
        goal="Create modern background music that matches the tone of educational tech content",
        backstory="""You are a music composer specializing in technology and educational content.
You create modern, electronic background music that enhances learning without distracting.
Your compositions use clean synth tones, subtle rhythmic elements, and professional production
quality. You match the emotional tone: focused for deep explanations, energetic for tutorials,
and cinematic for concept overviews.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    music_task = Task(
        description="""Compose background music for a {category} video with duration of {duration} seconds.

Select the appropriate mood: focused, energetic, cinematic, ambient, modern, or uplifting.
Generate a melody file path and mood selection.""",
        expected_output="Background music file path with mood and duration.",
        agent=composer,
    )

    return Crew(agents=[composer], tasks=[music_task], verbose=True)
