from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_voice_crew(script: str = ""):
    llm = get_llm(temperature=0.3, max_tokens=1000)

    voice_actor = Agent(
        role="Tech Narrator",
        goal="Generate clear, professional voice-over narration for educational tech content using Edge TTS",
        backstory="""You specialize in creating clear, authoritative, and engaging narration
for educational technology content. Your delivery is professional yet approachable,
with moderate pace (160-180 wpm) and precise articulation of technical terms.
You use Edge TTS (Microsoft neural voices) for free, high-quality synthesis.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    voice_task = Task(
        description="""Generate voice-over audio for this script:
{script}

Output the complete audio file path and timing information.
Use a clear, professional tone suitable for tech educational content.""",
        expected_output="Voice-over audio file path with duration and segment count.",
        agent=voice_actor,
    )

    return Crew(agents=[voice_actor], tasks=[voice_task], verbose=True)
