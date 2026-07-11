"""Comment sentiment analysis for YouTube videos."""
import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

POSITIVE_WORDS = {
    "great", "awesome", "amazing", "excellent", "fantastic", "wonderful",
    "love", "best", "perfect", "helpful", "clear", "understand", "thanks",
    "thank you", "appreciate", "brilliant", "insightful", "informative",
    "useful", "practical", "well explained", "subscribed", "understood",
    "good", "nice", "cool", "superb", "outstanding", "impressive",
}

NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "horrible", "worst", "hate", "useless",
    "boring", "confusing", "waste", "wrong", "misleading", "incorrect",
    "fake", "nonsense", "trash", "garbage", "stupid", "annoying",
    "dislike", "poor", "lame", "painful", "unwatchable", "rubbish",
}

INTENSIFIERS = {"very", "extremely", "incredibly", "absolutely", "really", "so", "too"}

NEGATION_WORDS = {"not", "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't",
                   "won't", "wouldn't", "shouldn't", "can't", "couldn't", "never", "no"}


def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of a comment text.

    Returns:
        {"sentiment": "positive"|"negative"|"neutral",
         "score": float between -1.0 and 1.0,
         "positive_words": [str],
         "negative_words": [str],
         "intensity": "low"|"medium"|"high"}
    """
    if not text or not text.strip():
        return {"sentiment": "neutral", "score": 0.0, "positive_words": [], "negative_words": [], "intensity": "low"}

    clean = re.sub(r'[^\w\s\']', ' ', text.lower())
    words = clean.split()

    found_positive = []
    found_negative = []
    negated = False
    score = 0.0

    for w in words:
        if w in NEGATION_WORDS:
            negated = True
            continue

        multiplier = 1.0
        if w in INTENSIFIERS:
            multiplier = 1.5
            continue

        if w in POSITIVE_WORDS:
            found_positive.append(w)
            score += 0.2 * multiplier * (-1 if negated else 1)
            negated = False
        elif w in NEGATIVE_WORDS:
            found_negative.append(w)
            score -= 0.25 * multiplier * (-1 if negated else 1)
            negated = False
        else:
            negated = False

    score = max(-1.0, min(1.0, score))

    if score > 0.15:
        sentiment = "positive"
    elif score < -0.15:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    abs_score = abs(score)
    intensity = "high" if abs_score > 0.5 else "medium" if abs_score > 0.2 else "low"

    return {
        "sentiment": sentiment,
        "score": round(score, 3),
        "positive_words": found_positive,
        "negative_words": found_negative,
        "intensity": intensity,
    }


def analyze_video_comments(video_id: str, youtube_service=None, max_comments: int = 100) -> dict:
    """Fetch and analyze all comments for a YouTube video.

    Returns:
        {"total": int, "sentiments": {...}, "flagged": [...]}
    """
    if not youtube_service:
        logger.warning("[comment_analyzer] No YouTube service provided, skipping")
        return {"total": 0, "sentiments": {"positive": 0, "neutral": 0, "negative": 0, "toxic": 0}, "flagged": []}

    try:
        comments = []
        page_token = None
        while len(comments) < max_comments:
            req = youtube_service.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                pageToken=page_token,
                order="time",
            )
            resp = req.execute()
            for item in resp.get("items", []):
                snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                text = snippet.get("textDisplay", "")
                author = snippet.get("authorDisplayName", "unknown")
                if text.strip():
                    comments.append({"text": text, "author": author, "id": item.get("id", "")})

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        sentiments = {"positive": 0, "neutral": 0, "negative": 0, "toxic": 0}
        flagged = []
        comment_scores = []

        for c in comments:
            result = analyze_sentiment(c["text"])
            comment_scores.append(result["score"])
            if result["sentiment"] == "negative" and result["intensity"] == "high":
                sentiments["toxic"] += 1
                flagged.append({"author": c["author"], "text": c["text"][:200], "score": result["score"]})
            elif result["sentiment"] == "negative":
                sentiments["negative"] += 1
            elif result["sentiment"] == "positive":
                sentiments["positive"] += 1
            else:
                sentiments["neutral"] += 1

        avg_score = round(sum(comment_scores) / len(comment_scores), 3) if comment_scores else 0.0
        negative_ratio = round((sentiments["negative"] + sentiments["toxic"]) / max(len(comments), 1), 3)

        return {
            "total": len(comments),
            "sentiments": sentiments,
            "avg_score": avg_score,
            "negative_ratio": negative_ratio,
            "flagged": flagged[:10],
        }
    except Exception as e:
        logger.error("[comment_analyzer] Failed to analyze comments for %s: %s", video_id, e)
        return {"total": 0, "sentiments": {"positive": 0, "neutral": 0, "negative": 0, "toxic": 0}, "flagged": []}


def flag_negative_comments(video_id: str, youtube_service=None, threshold: float = 0.2) -> Optional[dict]:
    """Check if negative comment ratio exceeds threshold.

    Returns alert dict if flagged, None otherwise.
    """
    result = analyze_video_comments(video_id, youtube_service, max_comments=50)
    if result["total"] == 0:
        return None

    if result["negative_ratio"] > threshold:
        return {
            "video_id": video_id,
            "severity": "warning",
            "negative_ratio": result["negative_ratio"],
            "total_comments": result["total"],
            "flagged_comments": result["flagged"],
            "message": f"Negative comment ratio {result['negative_ratio']:.0%} exceeds {threshold:.0%} threshold",
        }

    return None
