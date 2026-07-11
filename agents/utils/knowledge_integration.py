import logging
from typing import Optional

logger = logging.getLogger(__name__)


def inject_knowledge_context(topic: str, category: str, script_text: str = "") -> str:
    try:
        from utils.knowledge_graph import get_related_topics, get_prerequisites, get_learning_path, add_topic

        add_topic(
            topic_id=topic.lower().replace(" ", "_").replace("?", ""),
            title=topic,
            category=category,
        )

        related = get_related_topics(topic.lower().replace(" ", "_").replace("?", ""), max_depth=1)
        prereqs = get_prerequisites(topic.lower().replace(" ", "_").replace("?", ""))

        parts = []
        if prereqs:
            titles = [p["title"] for p in prereqs if not p.get("covered")]
            if titles:
                parts.append(f"Viewers may benefit from prerequisite knowledge: {', '.join(titles[:3])}")

        if related:
            titles = [r["title"] for r in related[:3]]
            parts.append(f"Related topics viewers might know: {', '.join(titles)}")

        if parts:
            return "Knowledge context:\n" + "\n".join(parts)

    except Exception as e:
        logger.debug(f"[KNOWLEDGE_INTEGRATION] Failed to inject context: {e}")

    return ""


def get_topic_suggestion(category: str = "") -> Optional[dict]:
    try:
        from utils.knowledge_graph import suggest_next_topic
        return suggest_next_topic(category)
    except Exception as e:
        logger.debug(f"[KNOWLEDGE_INTEGRATION] Topic suggestion failed: {e}")
    return None


def get_coverage_context() -> str:
    try:
        from utils.knowledge_graph import get_coverage_report, find_content_gaps
        coverage = get_coverage_report()
        gaps = find_content_gaps()

        parts = []
        if coverage.get("total_topics", 0) > 0:
            parts.append(
                f"Knowledge graph: {coverage['covered']}/{coverage['total_topics']} topics covered "
                f"({coverage['coverage_pct']}%)"
            )

        high_priority = [g for g in gaps if g.get("priority") == "high"]
        if high_priority:
            titles = [g.get("title", "") for g in high_priority[:3]]
            parts.append(f"Content gaps (high priority): {', '.join(titles)}")

        return "\n".join(parts) if parts else ""
    except Exception as e:
        logger.debug(f"[KNOWLEDGE_INTEGRATION] Coverage context failed: {e}")
    return ""


def suggest_trend_integration(trend_title: str, trend_category: str) -> Optional[str]:
    try:
        from utils.knowledge_graph import get_related_topics, get_prerequisites

        trend_id = trend_title.lower().replace(" ", "_").replace("?", "").replace("/", "_")
        related = get_related_topics(trend_id, max_depth=1)

        if related:
            prereq_titles = [
                r["title"] for r in related
                if r.get("relationship") == "prerequisite"
            ]
            if prereq_titles:
                return (
                    f"This trend builds on: {', '.join(prereq_titles[:3])}. "
                    f"Consider linking back to those videos."
                )

            related_titles = [r["title"] for r in related[:3]]
            return f"Related content: {', '.join(related_titles)}"

    except Exception as e:
        logger.debug(f"[KNOWLEDGE_INTEGRATION] Trend integration failed: {e}")
    return None


def record_video_knowledge(video_id: str, title: str, category: str, difficulty: str = "intermediate"):
    try:
        from utils.knowledge_graph import add_topic, add_relationship, _load_graph
        from utils.series_builder import pick_series_for_category

        tid = title.lower().replace(" ", "_").replace("?", "").replace("/", "_")
        add_topic(topic_id=tid, title=title, category=category, difficulty=difficulty, video_id=video_id)

        series = pick_series_for_category(category)
        if series:
            series_tid = series.get("title", "").lower().replace(" ", "_")
            graph = _load_graph()
            if series_tid and series_tid in graph.get("topics", {}):
                add_relationship(from_topic=tid, to_topic=series_tid, rel_type="related")

    except Exception as e:
        logger.debug(f"[KNOWLEDGE_INTEGRATION] Record knowledge failed: {e}")
