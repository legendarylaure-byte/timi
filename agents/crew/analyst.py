from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm
from datetime import datetime, timedelta
import json
import os


def load_recent_performance(days: int = 7) -> str:
    """Load recent analytics data and format as a report summary."""
    analytics_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "analytics"
    )
    analytics_file = os.path.join(analytics_dir, "video_analytics.json")
    if not os.path.exists(analytics_file):
        return "No analytics data available."

    try:
        with open(analytics_file, "r") as f:
            data = json.load(f)
    except Exception:
        return "Failed to load analytics data."

    videos = data.get("videos", {})
    daily_stats = data.get("daily_stats", {})

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent_videos = {k: v for k, v in videos.items() if v.get("created_at", "") >= cutoff}

    lines = [f"=== Performance Report (last {days} days) ==="]
    lines.append(f"Total videos analyzed: {len(recent_videos)}")

    by_type = {"shorts": 0, "long": 0}
    total_views = 0
    scores = []

    for vid, info in recent_videos.items():
        vtype = info.get("type", "unknown")
        by_type[vtype] = by_type.get(vtype, 0) + 1
        metrics = info.get("metrics", {})
        total_views += metrics.get("views", 0)
        score = info.get("score", 0)
        if score:
            scores.append(score)

    lines.append(f"Shorts: {by_type.get('shorts', 0)}, Longs: {by_type.get('long', 0)}")
    lines.append(f"Total views: {total_views}")
    if scores:
        lines.append(f"Avg quality score: {sum(scores)/len(scores):.1f}")
        lines.append(f"Best score: {max(scores)}, Worst: {min(scores)}")

    daily_lines = sorted(daily_stats.items())[-7:]
    if daily_lines:
        lines.append("\nDaily stats (last 7 days):")
        for day, stats in daily_lines:
            lines.append(f"  {day}: {stats.get('videos_created', 0)} videos, {stats.get('total_views', 0)} views")

    return "\n".join(lines)


def create_analyst_crew():
    llm = get_llm(temperature=0.4, max_tokens=2000)

    analyst = Agent(
        role="Content Performance Analyst",
        goal="Analyze video performance data and provide actionable insights",
        backstory="""You are a data-driven content strategist specializing in tech/AI educational YouTube channels.
You analyze engagement metrics, quality scores, and performance trends to identify
what content resonates best with tech audiences. Your insights help the creative team
optimize future videos for maximum engagement and educational impact.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    analysis_task = Task(
        description="""Analyze the following performance data for a tech/AI educational YouTube channel
and provide strategic recommendations.

PERFORMANCE DATA:
{performance_data}

Based on this data, produce a JSON analysis with:

1. **Top Performers**: Which content types/categories perform best?
2. **Growth Opportunities**: What content gaps or underserved topics exist?
3. **Quality Trends**: Is quality improving or declining? Which areas need focus?
4. **Actionable Recommendations**: 3-5 specific, concrete recommendations for the next content batch.

Return as JSON:
{
  "analysis_date": "<today's date>",
  "total_videos_analyzed": <number>,
  "top_performers": {
    "best_category": "<category name or 'N/A'>",
    "best_format": "shorts|long",
    "avg_score": <float>
  },
  "quality_trends": {
    "trend": "improving|declining|stable",
    "avg_score": <float>,
    "concerns": ["<concern 1>", "<concern 2>"]
  },
  "recommendations": [
    {"priority": "high|medium|low", "area": "<area>", "suggestion": "<specific actionable suggestion>"}
  ],
  "summary": "<2-3 sentence strategic summary>"
}""",
        expected_output="""JSON object with: analysis_date, total_videos_analyzed, top_performers, quality_trends, recommendations, summary""",
        agent=analyst,
    )

    return Crew(
        agents=[analyst],
        tasks=[analysis_task],
        verbose=True,
        memory=False,
        planning=False,
        cache=False,
    )


def run_analyst(days: int = 7) -> dict:
    """Run the Analyst agent and return analysis results."""
    try:
        perf_data = load_recent_performance(days)
        crew = create_analyst_crew()
        result = crew.kickoff(inputs={"performance_data": perf_data})
        raw = str(result)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"error": "Failed to parse analyst output", "raw": raw[:500]}
    except Exception as e:
        return {"error": str(e), "analysis_date": datetime.now().strftime("%Y-%m-%d"), "recommendations": []}
