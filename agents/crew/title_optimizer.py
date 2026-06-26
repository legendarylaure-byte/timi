from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_title_optimizer_crew(topic: str = "", category: str = "", format_type: str = "shorts"):
    llm = get_llm(temperature=0.8, max_tokens=2000)

    optimizer = Agent(
        role="Title Optimization Specialist",
        goal="Generate multiple high-CTR title variants for tech educational videos",
        backstory="""You are a YouTube CTR optimization expert specializing in tech content.
You know exactly what title formulas drive clicks for AI and technology videos.
You generate diverse, clickable titles optimized for YouTube's algorithm.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    title_formats = "question, how-to, bold claim, number/list, curiosity gap, comparison"
    if format_type == "shorts":
        title_formats += ", short & punchy under 40 chars"

    task = Task(
        description=f"""Generate 3 diverse, high-CTR title variants for this video:

Topic: {topic}
Category: {category}
Format: {format_type}

Title formulas to use: {title_formats}

Rules:
1. Each title under 60 characters (40 for shorts)
2. Titles must be factually accurate (no misleading clickbait)
3. Each should use a DIFFERENT formula
4. Optimize for tech/AI audience
5. Include relevant keywords for SEO

Return EXACTLY this JSON format:
{{
  "variants": [
    {{"title": "Title A", "formula": "question", "ctr_prediction": "high|medium|low", "keywords": ["kw1", "kw2"]}},
    {{"title": "Title B", "formula": "how-to", "ctr_prediction": "high|medium|low", "keywords": ["kw1", "kw2"]}},
    {{"title": "Title C", "formula": "bold_claim", "ctr_prediction": "high|medium|low", "keywords": ["kw1", "kw2"]}}
  ],
  "recommended_order": ["A", "B", "C"]
}}""",
        expected_output="JSON object with 3 title variants and recommendation order.",
        agent=optimizer,
    )

    return Crew(agents=[optimizer], tasks=[task], verbose=True)
