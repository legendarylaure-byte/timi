import os
import logging
import random
import re

logger = logging.getLogger(__name__)

COMMENT_PROMPTS = {
    "shorts": [
        "Which topic should I cover next? Comment below!",
        "Did this surprise you? Let me know in the comments.",
        "How do you use AI in your workflow? Share below!",
        "Try this yourself and tell me how it went!",
        "What's the hardest part of learning AI? Drop your answer.",
    ],
    "long": [
        "What part of this explanation was most useful to you?",
        "What should I deep-dive into next? Leave a suggestion!",
        "If you found this helpful, share it with a friend who's learning AI.",
        "Drop a timestamp of your favorite part in the comments!",
        "Which concept should I break down next? Let me know.",
    ],
}

PINNED_COMMENT_TEMPLATES = [
    "\U0001f4ac Discussion question: {question}\n\n\U0001f447 Drop your answer below \u2014 I read every comment!",
    "\U0001f914 Quick question: {question}\n\n\U0001f525 The best answers might get featured in my next video!",
    "\U0001f4cc Let's talk: {question}\n\n\U0001f4a1 Share your experience in the comments!",
]

AUTO_REPLY_RULES = [
    (r"\b(thank|thanks|thx|ty)\b", "You're welcome! Glad you found it helpful \U0001f64c"),
    (r"\b(great|awesome|amazing|nice|good|excellent)\b", "Appreciate the kind words! \U0001f64f"),
    (r"\b(question|how\s+(do|does|can)|what\s+(is|are)|why\s+(do|does|is)|help|explain)\b", "Great question! I'll consider covering this in a future video."),
    (r"\b(more|another|next|part\s*2|part2)\b", "More content is in the works! Subscribe so you don't miss it \U0001f514"),
    (r"\b(dislike|bad|terrible|wrong|hate|confus)\b", "Thanks for the honest feedback \u2014 I'll keep improving!"),
]

ENABLE_AUTO_REPLY = os.getenv("ENABLE_AUTO_REPLY", "true").lower() == "true"


def pick_comment_prompt(format_type: str = "shorts") -> str:
    prompts = COMMENT_PROMPTS.get(format_type, COMMENT_PROMPTS["shorts"])
    return random.choice(prompts)


def append_comment_prompt_to_script(script_text: str, topic: str, format_type: str = "shorts") -> str:
    prompt = pick_comment_prompt(format_type)
    cta = f"\n\n--SCENE FINAL--\nNARRATION: {prompt}\nVISUAL: TEXT OVERLAY: \"{prompt}\""
    if cta not in script_text:
        script_text += cta
    return script_text


def build_pinned_comment(topic: str, format_type: str = "shorts") -> str:
    question = pick_comment_prompt(format_type)
    template = random.choice(PINNED_COMMENT_TEMPLATES)
    return template.format(question=question)


def post_pinned_comment(video_id: str, comment_text: str, youtube_service=None) -> bool:
    if not youtube_service:
        logger.warning("No YouTube service provided for pinned comment")
        return False
    try:
        body = {
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {
                        "textOriginal": comment_text,
                    }
                },
            }
        }
        comment = youtube_service.commentThreads().insert(part="snippet", body=body).execute()
        comment_id = comment["id"]
        youtube_service.comments().setModerationStatus(
            id=comment_id, moderationStatus="published"
        ).execute()
        logger.info(f"Pinned comment posted for {video_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to post pinned comment: {e}")
        return False


def auto_reply_to_comments(video_id: str, youtube_service=None, max_replies: int = 5) -> int:
    if not youtube_service or not ENABLE_AUTO_REPLY:
        return 0
    replies_posted = 0
    try:
        response = youtube_service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=50,
            order="time",
        ).execute()

        for item in response.get("items", []):
            if replies_posted >= max_replies:
                break
            comment = item["snippet"]["topLevelComment"]["snippet"]
            text = comment.get("textDisplay", "")
            parent_id = item["id"]
            author = comment.get("authorDisplayName", "")

            if _already_replied(item, youtube_service):
                continue

            reply_text = _match_reply(text)
            if not reply_text:
                continue

            youtube_service.comments().insert(
                part="snippet",
                body={
                    "snippet": {
                        "parentId": parent_id,
                        "textOriginal": f"@{author} {reply_text}",
                    }
                },
            ).execute()
            replies_posted += 1
            logger.info(f"Auto-replied to {author} on video {video_id}")

        logger.info(f"Auto-reply complete: {replies_posted} replies posted for {video_id}")
    except Exception as e:
        logger.error(f"Auto-reply failed for {video_id}: {e}")
    return replies_posted


def _already_replied(comment_thread: dict, youtube_service) -> bool:
    try:
        if comment_thread["snippet"]["totalReplyCount"] > 0:
            replies = youtube_service.comments().list(
                part="snippet",
                parentId=comment_thread["id"],
                maxResults=5,
            ).execute()
            for reply in replies.get("items", []):
                author = reply["snippet"].get("authorDisplayName", "").lower()
                if author == "legendary laure" or "legendary laure" in author:
                    return True
    except Exception:
        pass
    return False


def _match_reply(comment_text: str) -> str | None:
    text_lower = comment_text.lower()
    for pattern, reply in AUTO_REPLY_RULES:
        if re.search(pattern, text_lower):
            return reply
    return None


def fetch_comment_count(video_id: str, youtube_service=None) -> int:
    if not youtube_service:
        return 0
    try:
        response = youtube_service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=1,
        ).execute()
        return response.get("pageInfo", {}).get("totalResults", 0)
    except Exception as e:
        logger.error(f"Failed to fetch comment count for {video_id}: {e}")
        return 0
