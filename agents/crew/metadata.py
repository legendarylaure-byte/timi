from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_metadata_crew(script: str = "", fmt: str = "shorts"):
    llm = get_llm(temperature=0.5, max_tokens=3000)

    metadata_writer = Agent(
        role="SEO Metadata Specialist",
        goal="Write SEO-optimized titles, descriptions, and tags for tech educational content",
        backstory="""You are an SEO expert specializing in technology YouTube and social media content.
You write compelling titles, keyword-rich descriptions, and trending tags that maximize
discoverability for a tech audience. You follow YouTube's AI-generated content disclosure
requirements and optimize for the Science & Technology category.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    metadata_task = Task(
        description="""Write SEO-optimized metadata for this video:
{script}
Format: {format}

Include:
1. Title (under 60 chars, curiosity-driven, keyword-rich, tech-oriented)
2. Description (under 5000 chars, SEO-optimized, with timestamps, includes AI-generated content disclaimer)
3. Tags (15-20 relevant tech tags: AI, machine learning, tutorial, explainer, programming, etc.)
4. Category: Science & Technology (YouTube category 28)
5. Language settings (English primary)
6. Made for Kids: No
7. AI content disclosure: Yes (this is AI-generated content)
8. Hashtags for TikTok/Instagram (#tech #ai #explained #programming)

Optimize for maximum discoverability across YouTube, TikTok, Instagram, and Facebook.""",
        expected_output="Complete SEO metadata package with title, description, tags, and platform-specific settings.",
        agent=metadata_writer,
    )

    return Crew(
        agents=[metadata_writer],
        tasks=[metadata_task],
        verbose=True,
        memory=False,
        planning=False,
        cache=False,
    )
