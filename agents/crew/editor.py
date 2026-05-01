import os
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_editor_crew():
    editor = Agent(
        role="Video Editor",
        goal="Composite animation, voice, and music into polished final videos",
        backstory="""You are a professional video editor specializing in children's content.
You use FFmpeg to composite animation frames, voice-overs, and background music
into polished final videos. You optimize for platform-specific formats and quality.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.3,
            max_tokens=2000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    editing_task = Task(
        description="""Edit and composite the final video with these components:
- Animation: {animation}
- Voice-over: {voice}
- Background music: {music}
- Format: {format}

Include:
1. FFmpeg compositing commands
2. Audio mixing levels (voice: 80%, music: 20%)
3. Video quality settings (1080p, H.264)
4. Duration check (shorts: max 120s, long: max 300s)
5. Aspect ratio verification (9:16 or 16:9)
6. Final output file path and naming

Ensure the final video is polished, properly synced, and ready for upload.""",
        expected_output="Complete FFmpeg editing commands and compositing plan with quality settings.",
        agent=editor,
    )

    return Crew(
        agents=[editor],
        tasks=[editing_task],
        verbose=True,
    )
