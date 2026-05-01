import os
from crewai import Agent, Task, Crew
from langchain_groq import ChatGroq

def create_thumbnail_crew():
    thumbnail_creator = Agent(
        role="Thumbnail Designer",
        goal="Create eye-catching, high-CTR thumbnails for children's content",
        backstory="""You are a thumbnail design expert specializing in children's content.
You use Stable Diffusion XL to generate vibrant, expressive thumbnails that drive
high click-through rates. Your designs use bright colors, curious expressions,
and follow proven viral thumbnail formulas.""",
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.6,
            max_tokens=2000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    thumbnail_task = Task(
        description="""Design a thumbnail for a video about: {topic}
Format: {format}

Include:
1. SDXL image generation prompt
2. Color scheme (bright, contrasting, kid-friendly)
3. Text overlay suggestion (if any)
4. Character expression (curious, excited, surprised)
5. Thumbnail psychology hook (curiosity gap)
6. Dimensions: 1280x720 for YouTube, 1080x1920 for shorts

Thumbnail must make viewers WANT to click immediately.""",
        expected_output="Complete thumbnail design plan with SDXL prompt and visual specifications.",
        agent=thumbnail_creator,
    )

    return Crew(
        agents=[thumbnail_creator],
        tasks=[thumbnail_task],
        verbose=True,
    )
