import os
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_animator_crew():
    animator = Agent(
        role="3D Animation Specialist",
        goal="Generate 3D animated frames and sequences for children's content",
        backstory="""You are a 3D animation expert specializing in children's cartoon content.
You create vibrant, playful, and engaging animations using Stable Video Diffusion
and other open-source tools. Your animations are optimized for both shorts (9:16)
and long-form (16:9) formats.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.5,
            max_tokens=3000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    animation_task = Task(
        description="""Generate 3D animation frames based on this storyboard:
{storyboard}

Format: {format}

Include:
1. Frame generation prompts for SVD (Stable Video Diffusion)
2. Animation style: playful 3D cartoon for kids aged 1-9
3. Scene transitions and timing
4. Character movement descriptions
5. Color and lighting consistency notes
6. GPU rendering configuration (Modal/Replicate)

Ensure animations are smooth, colorful, and captivating for young audiences.""",
        expected_output="Complete animation generation plan with SVD prompts and rendering configuration.",
        agent=animator,
    )

    return Crew(
        agents=[animator],
        tasks=[animation_task],
        verbose=True,
    )
