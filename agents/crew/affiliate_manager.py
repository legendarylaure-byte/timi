import json
import os
from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm

AFFILIATE_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "affiliate_programs.json",
)


def _load_affiliates() -> dict:
    if os.path.exists(AFFILIATE_DATA_PATH):
        try:
            with open(AFFILIATE_DATA_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def find_relevant_affiliates(script_text: str, category: str = "") -> list:
    affiliates = _load_affiliates()
    script_lower = script_text.lower()
    matched = []
    for aff_id, aff_data in affiliates.items():
        cat_match = not category or category in aff_data.get("category_tags", [])
        kw_match = any(kw in script_lower for kw in aff_data.get("keywords", []))
        if cat_match and kw_match:
            matched.append(aff_data)
    return matched


def build_affiliate_section(script_text: str, category: str = "") -> str:
    matches = find_relevant_affiliates(script_text, category)
    if not matches:
        return ""
    section = "\n\n🔧 **Tools & Resources Used:**\n"
    for aff in matches:
        section += f"• {aff['name']}: {aff['url']}\n"
    section += "\n*Some links are affiliate links. I may earn a commission at no extra cost to you.*"
    return section


def create_affiliate_manager_crew(script: str = "", category: str = ""):
    llm = get_llm(temperature=0.3, max_tokens=1000)

    manager = Agent(
        role="Affiliate Link Strategist",
        goal="Match relevant tools and products mentioned in scripts with affiliate programs",
        backstory="""You are an affiliate marketing expert for tech content.
You know exactly which AI tools, platforms, and resources to recommend
based on the content of the video. You naturally integrate affiliate links
without being salesy.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    task = Task(
        description=f"""Analyze this script and find relevant affiliate/recommended products:

Category: {category}

Script excerpt:
{script[:500] if len(script) > 500 else script}

Return which affiliate products to recommend and why they're relevant.
The system will auto-inject appropriate links from the affiliate database.""",
        expected_output="List of recommended affiliate products with relevance reasoning.",
        agent=manager,
    )

    return Crew(agents=[manager], tasks=[task], verbose=True, memory=False, planning=False, cache=False)
