import os
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_voice_crew():
    voice_actor = Agent(
        role="Kids Voice Actor",
        goal="Generate warm, expressive, age-appropriate voice-overs for children's content",
        backstory="""You specialize in creating friendly, clear, and expressive voice performances
for children aged 1-9. Your voices are warm, encouraging, and maintain perfect pacing
for young listeners. You use Piper TTS for efficient voice synthesis.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.5,
            max_tokens=2000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    voice_task = Task(
        description="""Generate voice-over directions and audio synthesis plan for this script:
{script}

Include:
1. Character voice profiles (pitch, tone, pace)
2. Emotional delivery notes for each line
3. TTS engine configuration (Piper TTS settings)
4. Audio file naming convention
5. Pronunciation guides for difficult words

Target: Clear, warm, engaging voices for children aged 1-9.""",
        expected_output="Complete voice synthesis plan with character profiles and TTS configuration.",
        agent=voice_actor,
    )

    return Crew(
        agents=[voice_actor],
        tasks=[voice_task],
        verbose=True,
    )
