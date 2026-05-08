import os
from crewai import Agent, Task, Crew
from crewai.llm import LLM

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def create_editor_crew(animation: str = "", voice: str = "", music: str = "", format: str = "shorts"):
    llm = LLM(
        model=f"ollama/{OLLAMA_MODEL}",
        base_url=OLLAMA_BASE,
        temperature=0.3,
        max_tokens=1000,
    )

    editor = Agent(
        role="Video Editor",
        goal="Composite stock video clips, voice-over, and music into a polished final video",
        backstory="""You are a professional video editor specializing in children's content.
You use FFmpeg to composite real video clips from stock footage, voice-overs, and
background music into polished final videos with smooth transitions and proper audio mixing.""",
        llm=llm,
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
