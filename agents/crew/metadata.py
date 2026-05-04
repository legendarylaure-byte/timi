import os
from crewai import Agent, Task, Crew

OLLAMA_MODEL = "ollama/" + os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def create_metadata_crew():
    metadata_writer = Agent(
        role="SEO Metadata Specialist",
        goal="Write SEO-optimized titles, descriptions, and tags for children's content",
        backstory="""You are an SEO expert specializing in children's YouTube and social media content.
You write compelling titles, keyword-rich descriptions, and trending tags that maximize
discoverability while remaining COPPA-compliant and age-appropriate.""",
        llm=OLLAMA_MODEL,
        base_url=OLLAMA_BASE,
        verbose=True,
        allow_delegation=False,
    )

    metadata_task = Task(
        description="""Write SEO-optimized metadata for this video:
{script}
Format: {format}

Include:
1. Title (under 60 chars, curiosity-driven, keyword-rich)
2. Description (under 5000 chars, SEO-optimized, with timestamps)
3. Tags (15-20 relevant, trending tags)
4. Category selection
5. Language settings
6. Age restriction (Made for Kids - COPPA compliant)
7. Hashtags for TikTok/Instagram

Optimize for maximum discoverability across YouTube, TikTok, Instagram, and Facebook.""",
        expected_output="Complete SEO metadata package with title, description, tags, and platform-specific settings.",
        agent=metadata_writer,
    )

    return Crew(
        agents=[metadata_writer],
        tasks=[metadata_task],
        verbose=True,
    )
