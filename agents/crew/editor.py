from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_editor_crew(animation: str = "", voice: str = "", music: str = "", format: str = "shorts"):
    llm = get_llm(temperature=0.3, max_tokens=1000)

    editor = Agent(
        role="Video Editor",
        goal="Composite visual assets, voice-over, text overlays, and music into a polished educational tech video",
        backstory="""You are a professional video editor specializing in educational technology content.
You composite stock footage, screen captures, diagrams, and code snippets with voice-over
and background music into polished final videos. You add text overlays for key points,
smooth transitions between scenes, and ensure proper audio mixing with voice dominant over music.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    editing_task = Task(
        description="""Composite the final video with:
- Visual assets: {animation}
- Voice-over: {voice}
- Background music: {music}
- Format: {format}

Instructions:
1. Set voice-over volume to 80%, background music to 20% with ducking during narration
2. Add text overlays for key terms, bullet points, and labels where specified
3. Use Ken Burns effect (slow zoom) on static images
4. Smooth transitions (crossfade 0.5s) between scenes
5. Output as platform-ready MP4 with correct aspect ratio
6. For shorts: center-crop to 9:16, for long: 16:9""",
        expected_output="Final video file path with format verification.",
        agent=editor,
    )

    return Crew(agents=[editor], tasks=[editing_task], verbose=True, memory=False, planning=False, cache=False)
