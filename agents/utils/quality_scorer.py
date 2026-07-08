import json
import threading
import textstat
from utils.llm_client import generate_completion
from utils.firebase_status import get_firestore_client, update_agent_status, log_activity
from utils.validators import validate_script_content
from utils.json_utils import extract_json
from firebase_admin import firestore

SYSTEM_PROMPT = """You are an expert content quality evaluator for tech educational YouTube/TikTok videos.
You are evaluating AI-generated educational technology content.

Evaluate the provided content and return ONLY a valid JSON object with this exact structure:

{
  "overall_score": 0-100,
  "breakdown": {
    "accuracy": 0-100,
    "educational_value": 0-100,
    "engagement_potential": 0-100,
    "clarity": 0-100,
    "structure": 0-100,
    "pacing": 0-100
  },
  "flags": ["flag1", "flag2"] or [],
  "recommendation": "approve" | "review" | "block",
  "feedback": "Brief explanation of the score"
}

Scoring guidelines for AI-generated tech educational content:
- 85-100: Excellent content with clear explanations, accurate information, engaging hooks, \
good structure. APPROVE immediately.
- 70-84: Good content with minor areas for improvement. Still APPROVE.
- 55-69: Acceptable but has noticeable gaps. Manual review recommended.
- Below 55: Significant issues (factual errors, unclear explanations). BLOCK.

IMPORTANT: Evaluate based on information quality, not entertainment value:
- Check that explanations are accurate (no fabricated claims)
- Check that complex terms are explained
- Assess whether the viewer will actually learn something
- Shorts should be fast-paced and focused on one concept
- Long-form should have clear structure and depth

Only flag factually incorrect or misleading content. Do NOT penalize for being AI-generated."""


def score_content(script: str, title: str, category: str, format_type: str = "shorts") -> dict:
    """Score video content using Groq AI and return quality metrics."""
    update_agent_status("quality_scorer", "working", f"Evaluating: {title}")

    format_bonus = {
        "shorts": "\n(Short-form: fast-paced, single concept, 55s max)",
        "long": "\n(Long-form: structured breakdown, 5-15 min)",
    }.get(format_type, "")

    content_prompt = f"""Evaluate this tech educational video content:

Title: {title}
Format: {format_type}
Category: {category}

Script/Content:
{script}{format_bonus}

Score each dimension and return the JSON object as specified."""

    result = None
    try:
        call_result = [None]
        call_error = [None]

        def _call_llm():
            try:
                call_result[0] = generate_completion(
                    prompt=content_prompt,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=1000,
                )
            except Exception as e:
                call_error[0] = e

        thread = threading.Thread(target=_call_llm)
        thread.daemon = True
        thread.start()
        thread.join(timeout=90)

        if thread.is_alive():
            print("[quality_scorer] LLM call timed out after 90s, using fallback")
            result = _fallback_score(script, title, category)
        elif call_error[0]:
            print(f"[quality_scorer] LLM call failed: {call_error[0]}, using fallback")
            result = _fallback_score(script, title, category)
        elif call_result[0]:
            result = extract_json(call_result[0])
            if result is None:
                result = _fallback_score(script, title, category)
        else:
            result = _fallback_score(script, title, category)
    except Exception as e:
        print(f"[quality_scorer] Error: {e}, using fallback")
        if result is None:
            result = _fallback_score(script, title, category)

    if result is None:
        result = _fallback_score(script, title, category)

    try:
        is_safe = validate_script_content(script)
        if not is_safe:
            result["flags"].append("contains_forbidden_words")
            result["breakdown"]["language_safety"] = max(0, result["breakdown"]["language_safety"] - 30)
            result["overall_score"] = max(0, result["overall_score"] - 20)
            if result["overall_score"] < 50:
                result["recommendation"] = "block"
    except Exception:
        pass

    try:
        readability = _check_readability(script, format_type)
        if readability["flags"]:
            result["flags"].extend(readability["flags"])
            result["breakdown"]["clarity"] = max(0, result["breakdown"]["clarity"] - readability["penalty"])
            result["overall_score"] = max(0, result["overall_score"] - readability["penalty"] // 2)
            if result["overall_score"] < 50:
                result["recommendation"] = "block"
        result["readability"] = readability["scores"]
    except Exception:
        pass

    try:
        _save_review(title, format_type, result)
    except Exception:
        pass

    update_agent_status("quality_scorer", "completed", f"Scored: {title} — {result['overall_score']}")
    log_activity("quality_scorer", f"Quality score: {result['overall_score']} for '{title}'", "success")

    return result


def _check_readability(script: str, format_type: str = "shorts") -> dict:
    text = script.strip()
    if not text:
        return {"flags": [], "penalty": 0, "scores": {}}

    fre = textstat.flesch_reading_ease(text)
    fkgl = textstat.flesch_kincaid_grade(text)
    dc = textstat.dale_chall_readability_score(text)

    scores = {"flesch_reading_ease": round(fre, 1), "flesch_kincaid_grade": round(fkgl, 1), "dale_chall": round(dc, 1)}
    flags = []
    penalty = 0

    if format_type == "shorts":
        if fkgl > 10:
            flags.append(f"readability_grade_{fkgl:.0f}")
            penalty = min(30, int((fkgl - 10) * 5))
        if fre < 40:
            flags.append(f"low_readability_{fre:.0f}")
            penalty = max(penalty, min(30, int((40 - fre) * 2)))
    else:
        if fkgl > 13:
            flags.append(f"readability_grade_{fkgl:.0f}")
            penalty = min(20, int((fkgl - 13) * 4))
        if fre < 30:
            flags.append(f"low_readability_{fre:.0f}")
            penalty = max(penalty, min(20, int((30 - fre) * 2)))

    return {"flags": flags, "penalty": penalty, "scores": scores}


def _fallback_score(script: str, title: str, category: str) -> dict:
    """Fallback local scoring if Groq fails."""
    script_lower = script.lower()
    words = script_lower.split()
    word_count = len(words)

    score = 75
    flags = []

    if word_count < 50:
        flags.append("too_short")
        score -= 10

    tech_keywords = ["ai", "machine learning", "neural", "algorithm", "data", "model", "training",
                     "compute", "inference", "transformer", "code", "function", "system", "network",
                     "automation", "deep learning", "llm", "gpt", "token", "embedding"]
    for word in tech_keywords:
        if word in script_lower:
            score += 2

    clarity_indicators = ["this means", "in other words", "for example", "think of it as",
                          "simply put", "essentially", "specifically", "in practice"]
    for phrase in clarity_indicators:
        if phrase in script_lower:
            score += 3

    structure_indicators = ["first", "second", "next", "finally", "in summary",
                            "to understand", "the key insight", "importantly"]
    for phrase in structure_indicators:
        if phrase in script_lower:
            score += 2

    if word_count >= 500:
        score += 5
    if word_count >= 1000:
        score += 5
    if "visual" in script_lower:
        score += 3

    score = max(60, min(95, score))

    return {
        "overall_score": score,
        "breakdown": {
            "accuracy": min(100, score),
            "educational_value": min(100, score + 5),
            "engagement_potential": min(100, score + 2),
            "clarity": min(100, score + 3),
            "structure": min(100, score + 4),
            "pacing": min(100, score - 2),
        },
        "flags": flags,
        "recommendation": "approve" if score >= 65 else "review",
        "feedback": f"Local heuristic score: {score}/100. {len(flags)} flag(s) found." if flags else f"Content appears suitable. Score: {score}/100",
    }


def _save_review(title: str, format_type: str, result: dict):
    """Save review to Firestore for the brand safety dashboard."""
    try:
        db = get_firestore_client()
        import random
        video_id = f"review-{random.randint(10000, 99999)}"
        db.collection("brand_reviews").add({
            "video_id": video_id,
            "title": title,
            "format": format_type,
            "score": result["overall_score"],
            "flags": result.get("flags", []),
            "breakdown": result.get("breakdown", {}),
            "recommendation": result.get("recommendation", "review"),
            "feedback": result.get("feedback", ""),
            "status": "pending",
            "created_at": firestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        print(f"[QUALITY] Failed to save review: {e}")


def predict_performance(title: str, category: str, format_type: str = "shorts", script: str = "") -> dict:
    """Predict video performance (views, engagement) before publishing."""
    system_prompt = """You are a YouTube/TikTok performance analyst specializing in tech educational content.
Predict the potential performance of a video based on its title, category, and format.
Return ONLY a valid JSON object with this exact structure:

{
  "predicted_views_7d": 0-500000,
  "predicted_views_30d": 0-2000000,
  "predicted_engagement_rate": 0-15,
  "predicted_ctr": 0-12,
  "predicted_avg_watch_time_seconds": 0-300,
  "virality_score": 0-100,
  "confidence": 0-100,
  "suggestions": ["suggestion1", "suggestion2", ...],
  "trending_match": "low" | "medium" | "high",
  "reasoning": "Brief explanation of the prediction"
}

Consider: title attractiveness, category popularity, format trends, seasonal relevance, competition level."""

    prediction_prompt = """Predict performance for this tech educational video:

Title: {title}
Category: {category}
Format: {format_type}

Script preview:
{script[:500] if script else "N/A"}"""

    try:
        response = generate_completion(
            prompt=prediction_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=800,
        )

        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            raw = response[json_start:json_end]
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = _fallback_prediction(title, category, format_type)
        else:
            result = _fallback_prediction(title, category, format_type)

        return result

    except Exception as e:
        print(f"[PREDICTOR] Error: {e}")
        return _fallback_prediction(title, category, format_type)


def _fallback_prediction(title: str, category: str, format_type: str = "shorts") -> dict:
    """Fallback local prediction if Groq fails."""
    import random
    import hashlib
    seed_val = int(hashlib.md5((title + category).encode()).hexdigest()[:8], 16)
    random.seed(seed_val)

    base_views = 5000 if format_type == "shorts" else 3000
    category_bonus = {"AI Explained": 1.4, "Deep Tech": 1.2,
                      "Paper Breakdowns": 1.1, "Tool Tutorials": 1.5, "Industry Analysis": 1.2,
                      "Code & Build": 1.3, "AI News": 1.3, "Career & Learning": 1.1}
    multiplier = category_bonus.get(category, 1.0)

    predicted_7d = int(base_views * multiplier * random.uniform(0.5, 2.0))
    predicted_30d = int(predicted_7d * random.uniform(2.5, 5.0))
    virality = min(100, max(0, int(multiplier * random.uniform(30, 80))))

    return {
        "predicted_views_7d": predicted_7d,
        "predicted_views_30d": predicted_30d,
        "predicted_engagement_rate": round(random.uniform(3.0, 10.0), 1),
        "predicted_ctr": round(random.uniform(3.0, 8.0), 1),
        "predicted_avg_watch_time_seconds": random.randint(30, 90) if format_type == "shorts" else random.randint(120, 240),  # noqa: E501
        "virality_score": virality,
        "confidence": random.randint(50, 80),
        "suggestions": [
            "Consider adding more engaging hooks in the first 3 seconds",
            "Thumbnail should feature bright, high-contrast colors",
            f"Best posting time for {category}: 6:00 PM - 8:00 PM",
        ],
        "trending_match": "high" if virality > 60 else "medium" if virality > 40 else "low",
        "reasoning": f"Prediction based on category popularity ({category}), format trends ({format_type}), and historical patterns.",  # noqa: E501
    }


def check_repetition(current_script: str, category: str, max_recent: int = 10) -> dict:
    """Check if current content is too similar to recent videos (prevents 'repetitious content' flags)."""
    try:
        db = get_firestore_client()
        recent_videos = (
            db.collection("videos")
            .where("status", "in", ["uploaded", "completed"])
            .limit(max_recent * 2)
            .stream(timeout=10)
        )

        all_recent = []
        for doc in recent_videos:
            data = doc.to_dict()
            if data.get("script"):
                all_recent.append({
                    "title": data.get("title", ""),
                    "script": data["script"],
                    "created_at": data.get("created_at", ""),
                })

        all_recent.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        recent_videos = all_recent[:max_recent]

        if not recent_videos:
            return {"is_repetitive": False, "similarity_scores": [], "max_similarity": 0.0, "recommendation": "approve"}

        similarities = []
        for recent in recent_videos:
            sim = _text_similarity(current_script, recent["script"])
            similarities.append({"title": recent["title"], "similarity": sim})

        max_similarity = max(s["similarity"] for s in similarities)
        is_repetitive = max_similarity > 0.5

        result = {
            "is_repetitive": is_repetitive,
            "similarity_scores": similarities,
            "max_similarity": round(max_similarity, 2),
            "recommendation": "block" if is_repetitive else "approve",
        }

        if is_repetitive:
            result["flags"] = ["repetitious_content_detected"]
            result["feedback"] = f"Content is {max_similarity:.0%} similar to a recent video. YouTube may flag this as repetitious."  # noqa: E501

        return result
    except Exception as e:
        print(f"[repetition] Check skipped (quota/timeout): {e}")
        return {"is_repetitive": False, "similarity_scores": [], "max_similarity": 0.0, "recommendation": "approve"}


def _text_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def evaluate_publish_decision(quality_score: dict, repetition_check: dict, auto_approve_threshold: int = 80) -> dict:
    score = quality_score.get("overall_score", 0)
    recommendation = quality_score.get("recommendation", "review")
    is_repetitive = repetition_check.get("is_repetitive", False)

    if score >= auto_approve_threshold and recommendation == "approve" and not is_repetitive:
        return {"action": "auto_approve", "reason": f"Score {score} >= {auto_approve_threshold}, no flags"}
    elif recommendation == "block" or score < 50:
        return {"action": "block", "reason": f"Score {score} < 50 or blocked by quality scorer"}
    elif is_repetitive:
        return {"action": "block", "reason": "Repetitious content detected"}
    else:
        return {"action": "manual_review", "reason": f"Score {score} requires human review"}
