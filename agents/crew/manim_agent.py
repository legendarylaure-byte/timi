from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm


def create_manim_agent_crew(scene_description: str = "", category: str = "AI Explained", format_type: str = "long"):
    llm = get_llm(temperature=0.3, max_tokens=2000)

    agent = Agent(
        role="Manim Scene Designer",
        goal="Select the best Manim template or design a custom scene for educational tech/animation content",
        backstory="""You specialize in translating educational AI/tech concepts into Manim animation scenes.
You maintain a library of pre-built templates:
- neural_network: MLP/neural network diagrams with layers and connections
- attention: Self-attention / QKV visualization
- transformer: Full encoder-decoder transformer architecture
- algorithm_flow: Sequential process/setup flow with arrows
- bar_chart: Data comparison and benchmark charts
- text_reveal: Key insight / takeaway text reveals

For each scene you analyze, return:
1. Which template matches best (or "custom" for novel scenes)
2. The parameters to pass (title, labels, values, etc.)
3. Why this template was chosen""",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    task = Task(
        description="""Analyze this scene and select the best Manim template.

Scene description: {scene_description}
Category: {category}
Format: {format_type}

Return JSON with:
- "template": template name or "custom"
- "params": dict of parameters for the template
- "reason": why this template fits""",
        expected_output='{"template": "name", "params": {}, "reason": "..."}',
        agent=agent,
    )

    return Crew(agents=[agent], tasks=[task], verbose=False)
