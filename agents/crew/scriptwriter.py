import os
from crewai import Agent, Task, Crew
from crewai_tools import BaseTool
from langchain_groq import ChatGroq

class GroqLLMTool(BaseTool):
    name: str = "groq_llm"
    description: str = "Access Groq LLM for text generation"
    def _run(self, prompt: str) -> str:
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.7,
            max_tokens=2000,
        )
        return str(llm.invoke(prompt).content)

def create_scriptwriter_crew():
    scriptwriter = Agent(
        role="Kids Content Scriptwriter",
        goal="Create engaging, educational, age-appropriate scripts for children aged 1-9",
        backstory="""You are an expert children's content creator specializing in educational and entertaining scripts.
You create content that is COPPA-compliant, culturally inclusive, and designed to be viral on social media.
Your scripts follow proven engagement patterns: hook in first 3 seconds, pattern interrupts every 5-7 seconds,
emotional triggers (wonder, curiosity, joy), and end with curiosity-building cliffhangers.""",
        tools=[GroqLLMTool()],
        llm=ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.7,
            max_tokens=3000,
        ),
        verbose=True,
        allow_delegation=False,
    )

    script_task = Task(
        description="""Write a script for a {format} video in the {category} category about "{topic}".
Format requirements:
- Shorts: Maximum {max_duration} seconds, fast-paced, visual hooks
- Long: Maximum {max_duration} seconds, narrative-driven, deeper engagement

Include:
1. Scene-by-scene breakdown with timing
2. Character dialogue (simple, age-appropriate language)
3. Visual descriptions for each scene
4. Emotional beats and engagement hooks
5. Educational value statement

Age group: 1-9 years old. Language must be simple, positive, and educational.""",
        expected_output="A complete script with scenes, dialogue, timing, visual descriptions, and engagement hooks.",
        agent=scriptwriter,
    )

    return Crew(
        agents=[scriptwriter],
        tasks=[script_task],
        verbose=True,
    )
