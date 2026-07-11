import os
import json
import logging
import random
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge_graph")
os.makedirs(DATA_DIR, exist_ok=True)
GRAPH_FILE = os.path.join(DATA_DIR, "graph.json")
CURRICULUM_FILE = os.path.join(DATA_DIR, "curricula.json")


def _load_graph() -> dict:
    if os.path.exists(GRAPH_FILE):
        try:
            with open(GRAPH_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load knowledge graph: {e}")
    return {"topics": {}, "edges": [], "meta": {"created_at": datetime.utcnow().isoformat(), "version": 2}}


def _save_graph(data: dict):
    with open(GRAPH_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _load_curricula() -> dict:
    if os.path.exists(CURRICULUM_FILE):
        try:
            with open(CURRICULUM_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load curricula: {e}")
    return {"curricula": []}


def _save_curricula(data: dict):
    with open(CURRICULUM_FILE, "w") as f:
        json.dump(data, f, indent=2)


DIFFICULTY_LEVELS = {"beginner": 1, "intermediate": 2, "advanced": 3}

RELATION_TYPES = ["prerequisite", "related", "builds_on", "continues", "contrasts_with"]


def add_topic(
    topic_id: str,
    title: str,
    category: str,
    difficulty: str = "intermediate",
    tags: list[str] | None = None,
    summary: str = "",
    video_id: str = "",
) -> dict:
    graph = _load_graph()
    topics = graph["topics"]

    if topic_id in topics:
        existing = topics[topic_id]
        existing["video_count"] = existing.get("video_count", 0) + 1
        if video_id and video_id not in existing.get("video_ids", []):
            existing.setdefault("video_ids", []).append(video_id)
        existing["last_covered"] = datetime.utcnow().isoformat()
        _save_graph(graph)
        return existing

    difficulty_norm = difficulty.lower()
    if difficulty_norm not in DIFFICULTY_LEVELS:
        difficulty_norm = "intermediate"

    topic = {
        "title": title,
        "category": category,
        "difficulty": difficulty_norm,
        "difficulty_level": DIFFICULTY_LEVELS[difficulty_norm],
        "tags": tags or [],
        "summary": summary,
        "video_ids": [video_id] if video_id else [],
        "video_count": 1 if video_id else 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_covered": datetime.utcnow().isoformat() if video_id else "",
        "coverage_score": 1,
    }
    topics[topic_id] = topic
    _save_graph(graph)
    logger.info(f"[KG] Added topic: {title} ({difficulty})")
    return topic


def add_relationship(from_topic: str, to_topic: str, rel_type: str = "related") -> bool:
    if rel_type not in RELATION_TYPES:
        logger.warning(f"[KG] Unknown relationship type: {rel_type}")
        return False

    graph = _load_graph()
    if from_topic not in graph["topics"] or to_topic not in graph["topics"]:
        logger.warning(f"[KG] Cannot add relationship: one or both topics missing")
        return False

    edge = {"source": from_topic, "target": to_topic, "type": rel_type}
    existing = any(
        e["source"] == from_topic and e["target"] == to_topic and e["type"] == rel_type
        for e in graph["edges"]
    )
    if not existing:
        graph["edges"].append(edge)
        _save_graph(graph)
        logger.info(f"[KG] Added edge: {from_topic} --[{rel_type}]--> {to_topic}")
    return True


def get_related_topics(topic_id: str, max_depth: int = 1) -> list[dict]:
    graph = _load_graph()
    if topic_id not in graph["topics"]:
        return []

    visited = {topic_id}
    queue = [(topic_id, 0)]
    results = []

    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        for e in graph["edges"]:
            neighbor = None
            if e["source"] == current and e["target"] not in visited:
                neighbor = e["target"]
            elif e["target"] == current and e["source"] not in visited:
                neighbor = e["source"]

            if neighbor:
                visited.add(neighbor)
                t = graph["topics"].get(neighbor, {})
                results.append({
                    "topic_id": neighbor,
                    "title": t.get("title", neighbor),
                    "category": t.get("category", ""),
                    "difficulty": t.get("difficulty", "intermediate"),
                    "relationship": e["type"],
                    "depth": depth + 1,
                    "video_count": t.get("video_count", 0),
                })
                queue.append((neighbor, depth + 1))

    return results


def get_prerequisites(topic_id: str) -> list[dict]:
    graph = _load_graph()
    if topic_id not in graph["topics"]:
        return []

    prereqs = []
    for e in graph["edges"]:
        if e["target"] == topic_id and e["type"] == "prerequisite":
            t = graph["topics"].get(e["source"], {})
            prereqs.append({
                "topic_id": e["source"],
                "title": t.get("title", e["source"]),
                "difficulty": t.get("difficulty", "intermediate"),
                "covered": t.get("video_count", 0) > 0,
            })
    prereqs.sort(key=lambda x: DIFFICULTY_LEVELS.get(x["difficulty"], 1))
    return prereqs


def get_learning_path(topic_id: str) -> list[dict]:
    graph = _load_graph()
    if topic_id not in graph["topics"]:
        return []

    path = []
    visited = set()
    queue = [topic_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        t = graph["topics"].get(current, {})
        path.append({
            "topic_id": current,
            "title": t.get("title", current),
            "difficulty": t.get("difficulty", "intermediate"),
            "difficulty_level": t.get("difficulty_level", 1),
            "video_count": t.get("video_count", 0),
            "covered": t.get("video_count", 0) > 0,
        })

        for e in graph["edges"]:
            if e["type"] == "builds_on" and e["source"] == current and e["target"] not in visited:
                queue.append(e["target"])

    path.sort(key=lambda x: x["difficulty_level"])
    return path


def get_coverage_report() -> dict:
    graph = _load_graph()
    topics = graph["topics"]
    if not topics:
        return {"total_topics": 0, "covered": 0, "coverage_pct": 0, "by_difficulty": {}, "by_category": {}}

    covered = sum(1 for t in topics.values() if t.get("video_count", 0) > 0)
    by_difficulty = {}
    by_category = {}

    for t in topics.values():
        d = t.get("difficulty", "intermediate")
        by_difficulty[d] = by_difficulty.get(d, 0) + 1
        c = t.get("category", "uncategorized")
        by_category[c] = by_category.get(c, 0) + 1

    return {
        "total_topics": len(topics),
        "covered": covered,
        "uncovered": len(topics) - covered,
        "coverage_pct": round(covered / len(topics) * 100, 1) if topics else 0,
        "by_difficulty": by_difficulty,
        "by_category": by_category,
    }


def find_content_gaps(category: str | None = None) -> list[dict]:
    graph = _load_graph()
    topics = graph["topics"]
    if not topics:
        return []

    gaps = []

    for e in graph["edges"]:
        if e["type"] == "prerequisite":
            src = graph["topics"].get(e["source"])
            tgt = graph["topics"].get(e["target"])
            if src and tgt:
                src_covered = src.get("video_count", 0) > 0
                tgt_covered = tgt.get("video_count", 0) > 0
                if tgt_covered and not src_covered:
                    gaps.append({
                        "type": "missing_prerequisite",
                        "missing_topic": e["source"],
                        "title": src.get("title", e["source"]),
                        "blocking": e["target"],
                        "blocking_title": tgt.get("title", e["target"]),
                        "priority": "high",
                    })

    for e in graph["edges"]:
        if e["type"] == "builds_on":
            src = graph["topics"].get(e["source"])
            tgt = graph["topics"].get(e["target"])
            if src and tgt:
                src_covered = src.get("video_count", 0) > 0
                tgt_covered = tgt.get("video_count", 0) > 0
                if src_covered and not tgt_covered:
                    gaps.append({
                        "type": "natural_next",
                        "next_topic": e["target"],
                        "title": tgt.get("title", e["target"]),
                        "follows": e["source"],
                        "follows_title": src.get("title", e["source"]),
                        "priority": "medium",
                    })

    uncovered = [(t_id, t) for t_id, t in graph["topics"].items() if t.get("video_count", 0) == 0]
    uncovered.sort(key=lambda x: DIFFICULTY_LEVELS.get(x[1].get("difficulty", "intermediate"), 2))
    for u_id, t in uncovered[:5]:
        if not any(g.get("missing_topic") == u_id or g.get("next_topic") == u_id for g in gaps):
            gaps.append({
                "type": "uncovered_topic",
                "topic_id": u_id,
                "title": t.get("title", ""),
                "difficulty": t.get("difficulty", "intermediate"),
                "category": t.get("category", ""),
                "priority": "low",
            })

    if category:
        gaps = [g for g in gaps if g.get("category") == category or category in str(g.get("title", ""))]

    gaps.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("priority", "low"), 3))
    return gaps


def prune_old_topics(days_threshold: int = 90) -> int:
    graph = _load_graph()
    cutoff = datetime.utcnow().isoformat()
    import time as _time
    cutoff_ts = _time.time() - days_threshold * 86400

    to_remove = []
    for t_id, t in graph["topics"].items():
        last = t.get("last_covered", "")
        if last:
            try:
                last_ts = datetime.fromisoformat(last).timestamp()
                if last_ts < cutoff_ts and t.get("video_count", 0) == 0:
                    to_remove.append(t_id)
            except Exception:
                pass

    for t_id in to_remove:
        graph["edges"] = [e for e in graph["edges"] if e["source"] != t_id and e["target"] != t_id]
        del graph["topics"][t_id]

    if to_remove:
        _save_graph(graph)
        logger.info(f"[KG] Pruned {len(to_remove)} stale topics")
    return len(to_remove)


def build_curriculum(name: str, description: str, topic_ids: list[str], category: str = "") -> dict:
    curricula = _load_curricula()
    graph = _load_graph()

    existing_names = [c["name"] for c in curricula["curricula"]]
    if name in existing_names:
        logger.warning(f"[KG] Curriculum '{name}' already exists")
        return {}

    resolved = []
    for t_id in topic_ids:
        if t_id in graph["topics"]:
            resolved.append({
                "topic_id": t_id,
                "title": graph["topics"][t_id].get("title", t_id),
                "difficulty": graph["topics"][t_id].get("difficulty", "intermediate"),
            })

    curriculum = {
        "name": name,
        "description": description,
        "category": category,
        "topics": resolved,
        "created_at": datetime.utcnow().isoformat(),
        "completed_count": sum(1 for t in resolved if graph["topics"].get(t["topic_id"], {}).get("video_count", 0) > 0),
        "total_count": len(resolved),
    }
    curricula["curricula"].append(curriculum)
    _save_curricula(curricula)
    logger.info(f"[KG] Built curriculum '{name}' with {len(resolved)} topics")
    return curriculum


def suggest_next_topic(category: str = "", difficulty: str = "intermediate") -> Optional[dict]:
    gaps = find_content_gaps(category)
    high_priority = [g for g in gaps if g.get("priority") == "high"]
    if high_priority:
        gap = random.choice(high_priority)
        return {
            "topic_id": gap.get("missing_topic", ""),
            "title": gap.get("title", ""),
            "reason": f"Prerequisite missing for '{gap.get('blocking_title', '')}'",
            "priority": "high",
        }

    medium = [g for g in gaps if g.get("priority") == "medium"]
    if medium:
        gap = random.choice(medium)
        return {
            "topic_id": gap.get("next_topic", ""),
            "title": gap.get("title", ""),
            "reason": f"Natural next after '{gap.get('follows_title', '')}'",
            "priority": "medium",
        }

    graph = _load_graph()
    uncovered = [
        (t_id, t) for t_id, t in graph["topics"].items()
        if t.get("video_count", 0) == 0
        and (not category or t.get("category") == category)
        and DIFFICULTY_LEVELS.get(t.get("difficulty", "intermediate"), 2) <= DIFFICULTY_LEVELS.get(difficulty, 2)
    ]
    if uncovered:
        t_id, t = random.choice(uncovered)
        return {
            "topic_id": t_id,
            "title": t.get("title", t_id),
            "reason": f"Uncovered topic in {t.get('category', 'general')}",
            "priority": "low",
        }

    return None
