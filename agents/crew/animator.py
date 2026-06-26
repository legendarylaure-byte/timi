from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_animator_crew(storyboard: str = "", format: str = "shorts"):
    llm = get_llm(temperature=0.4, max_tokens=4000)

    animator = Agent(
        role="Visual Asset Director",
        goal="Select and arrange visual assets (stock footage, screen captures, diagrams, code snippets) that match each scene",
        backstory="""You are an expert at finding the perfect visual assets for tech educational content.
You analyze each scene and choose the best asset type:
- STOCK_FOOTAGE from Pexels/Pixabay for atmosphere and concepts (tech, servers, coding, data centers)
- SCREEN_CAPTURE for tool demonstrations and UI walkthroughs
- DIAGRAM_ANIMATION for conceptual explanations (neural networks, architectures, flows)
- CODE_SNIPPET for code examples and technical details
- STATIC_IMAGE for infographics and comparison slides
You match the visual style to the content and ensure smooth visual flow across scenes.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    animation_task = Task(
        description="""Analyze this storyboard and create a scene plan with asset requirements:
{storyboard}

Format: {format}

For EACH scene, output:
1. ASSET_TYPE: STOCK_FOOTAGE | SCREEN_CAPTURE | DIAGRAM_ANIMATION | CODE_SNIPPET | STATIC_IMAGE
2. Search keyword or description (for stock searches or screen capture URLs)
3. Target duration (in seconds)
4. Description of visual content needed

Output as JSON array: [{"asset_type": "...", "keyword": "...", "target_duration": N, "description": "..."}]""",
        expected_output="JSON array of scenes with keyword, target_duration, and description.",
        agent=animator,
    )

    return Crew(agents=[animator], tasks=[animation_task], verbose=True)
