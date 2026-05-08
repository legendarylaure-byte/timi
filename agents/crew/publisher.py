import os
import sys
from crewai import Agent, Task, Crew
from crewai.llm import LLM

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def create_publisher_crew(video: str = "", thumbnail: str = "", metadata: str = "", format: str = "shorts"):
    llm = LLM(
        model=f"ollama/{OLLAMA_MODEL}",
        base_url=OLLAMA_BASE,
        temperature=0.3,
        max_tokens=2000,
    )

    publisher = Agent(
        role="Social Media Publisher",
        goal="Upload videos to YouTube, TikTok, Instagram, and Facebook with proper metadata",
        backstory="""You are a multi-platform publishing expert. You handle automated uploads
to all major social media platforms with proper metadata, scheduling, and notifications.
You ensure COPPA compliance and platform-specific optimization for each upload.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    publish_task = Task(
        description="""Upload the video to all platforms:
- Video file: {video}
- Thumbnail: {thumbnail}
- Metadata: {metadata}
- Format: {format}

Steps:
1. Upload to YouTube (Data API v3)
   - Set "Made for Kids" = true
   - Apply title, description, tags, thumbnail
   - Set privacy status to "public"
   - Use category ID "27" (Education) for kids content
   - If format is "shorts", add #Shorts to title

2. Upload to TikTok (Content Posting API)
   - Apply title and hashtags
   - Set appropriate privacy

3. Upload to Instagram (Graph API)
   - Post as Reel (for shorts) or video (for long)
   - Apply caption and hashtags

4. Upload to Facebook (Graph API)
   - Post to page
   - Apply description

5. After ALL uploads succeed:
   - Trigger R2 storage cleanup to delete the video file
   - Video was stored temporarily and is no longer needed

6. Send Telegram notification with all links and metadata

Return: Upload results with URLs for each platform.""",
        expected_output="Upload results with video URLs from each platform and confirmation of success.",
        agent=publisher,
    )

    return Crew(
        agents=[publisher],
        tasks=[publish_task],
        verbose=True,
    )
