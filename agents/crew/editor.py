from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_editor_crew(animation: str = "", voice: str = "", music: str = "", format: str = "shorts"):
    llm = get_llm(temperature=0.3, max_tokens=1000)

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
