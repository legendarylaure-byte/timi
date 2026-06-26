import os
import logging

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
    "💬 Discussion question: {question}\n\n👇 Drop your answer below — I read every comment!",
    "🤔 Quick question: {question}\n\n🔥 The best answers might get featured in my next video!",
    "📌 Let's talk: {question}\n\n💡 Share your experience in the comments!",
]


def pick_comment_prompt(format_type: str = "shorts") -> str:
    import random
    prompts = COMMENT_PROMPTS.get(format_type, COMMENT_PROMPTS["shorts"])
    return random.choice(prompts)


def append_comment_prompt_to_script(script_text: str, topic: str, format_type: str = "shorts") -> str:
    prompt = pick_comment_prompt(format_type)
    cta = f"\n\n--SCENE FINAL--\nNARRATION: {prompt}\nVISUAL: TEXT OVERLAY: \"{prompt}\""
    if cta not in script_text:
        script_text += cta
    return script_text


def build_pinned_comment(topic: str, format_type: str = "shorts") -> str:
    import random
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
