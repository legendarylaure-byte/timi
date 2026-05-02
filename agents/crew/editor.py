import os
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_editor_crew():
    editor = Agent(
        role="Video Editor",
        goal="Composite stock video clips, voice-over, and music into a polished final video",
        backstory="""You are a professional video editor specializing in children's content.
You use FFmpeg to composite real video clips from stock footage, voice-overs, and
background music into polished final videos with smooth transitions and proper audio mixing.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.3,
            max_tokens=1000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    editing_task = Task(
        description="""Composite the final video with:
- Video clips: {animation}
- Voice-over: {voice}
- Background music: {music}
- Format: {format}

Assemble with proper timing, audio mixing (voice dominant, music subtle),
and output as a platform-ready MP4 file.""",
        expected_output="Final video file path with format verification.",
        agent=editor,
    )

    return Crew(agents=[editor], tasks=[editing_task], verbose=True)
