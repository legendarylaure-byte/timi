import os
import asyncio
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_voice_crew():
    voice_actor = Agent(
        role="Kids Voice Actor",
        goal="Generate warm, expressive voice-over audio for children's content using Edge TTS",
        backstory="""You specialize in creating friendly, clear, and expressive voice performances
for children aged 1-9. Your voices are warm, encouraging, and maintain perfect pacing
for young listeners. You use Edge TTS (Microsoft neural voices) for free, high-quality synthesis.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.5,
            max_tokens=1000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    voice_task = Task(
        description="""Generate voice-over audio for this script:
{script}

Output the complete audio file path and timing information.
Use a warm, engaging tone suitable for children aged 1-9.""",
        expected_output="Voice-over audio file path with duration and segment count.",
        agent=voice_actor,
    )

    return Crew(agents=[voice_actor], tasks=[voice_task], verbose=True)
