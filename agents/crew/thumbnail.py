from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm
from utils.thumbnail_renderer import generate_thumbnail_variants


def create_thumbnail_crew(topic: str = "", format: str = "shorts"):
    llm = get_llm(temperature=0.7, max_tokens=2000)

    thumbnail_creator = Agent(
        role="Tech Thumbnail Designer",
        goal="Generate high-CTR rendered thumbnails for educational tech content",
        backstory="""You are a thumbnail design expert specializing in technology content.
You create bold, contrast-rich thumbnails that drive high click-through rates.
You use dark backgrounds with bright accent colors, bold text overlays,
and proven tech thumbnail formulas: comparisons, numbered lists,
question hooks, and bold statements.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    thumbnail_task = Task(
        description=f"""Design and generate thumbnails for a video about: "{topic}"
Format: {format}

Style guidelines:
- Dark background (#0A0A0F) with indigo (#6366F1) and cyan (#22D3EE) accents
- Bold white/indigo text overlay, 3-5 words max
- Tech aesthetic: grid lines, subtle glow effects, gradient accents
- High contrast for maximum CTR

Generate 3 thumbnail variants (comparison, question, list styles).

The system will render them automatically. Return the rendering parameters.""",
        expected_output="3 rendered thumbnail images saved to data/thumbnails/",
        agent=thumbnail_creator,
    )

    return Crew(agents=[thumbnail_creator], tasks=[thumbnail_task], verbose=True)


def render_thumbnails(topic: str, category: str = "") -> list:
    return generate_thumbnail_variants(topic, category, count=3)
