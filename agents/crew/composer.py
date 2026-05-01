import os
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_composer_crew():
    composer = Agent(
        role="Children's Music Composer",
        goal="Create engaging, age-appropriate background music for kids' content",
        backstory="""You are a music composer specializing in children's content.
You create melodies that are memorable, uplifting, and perfectly matched to the
emotional tone of each scene. You use Meta's MusicGen for AI music generation.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.6,
            max_tokens=2000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    music_task = Task(
        description="""Compose background music plan for a {category} video with duration of {duration} seconds.

Include:
1. Music genre and style (lullaby, upbeat, adventurous, etc.)
2. Tempo and key
3. Instrument list
4. Emotional progression matching scenes
5. MusicGen prompt for generation
6. Fade in/out points

The music must be child-friendly, non-distracting, and enhance the storytelling.""",
        expected_output="Complete music composition plan with MusicGen prompts and timing markers.",
        agent=composer,
    )

    return Crew(
        agents=[composer],
        tasks=[music_task],
        verbose=True,
    )
