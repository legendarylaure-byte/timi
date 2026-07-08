import re
from utils.llm_client import generate_completion

PROHIBITED_TOPIC_PATTERNS = [
    r'\bp[\._\s]*[o0][\._\s]*r[\._\s]*n[\._\s]*[o0]\b',
    r'\bs[\._\s]*e[\._\s]*x[\._\s]*\b',
    r'\bf[\._\s]*u[\._\s]*c[\._\s]*k\b',
    r'\bs[\._\s]*h[\._\s]*i[\._\s]*t\b',
    r'\bn[\._\s]*i[\._\s]*g[\._\s]*g[\._\s]*[e3]\b',
    r'\bb[\._\s]*i[\._\s]*t[\._\s]*c[\._\s]*h\b',
    r'\bd[\._\s]*i[\._\s]*c[\._\s]*k\b',
]

LEAKED_PROMPT_PATTERNS = [
    "please provide the original script",
    "i need the existing opening",
    "i need the original script",
    "please provide the existing",
    "original script you want me",
    "i need the existing",
    "you want me to rewrite",
    "provide the original script",
]

CATEGORY_FALLBACK_HOOKS = {
    "AI Explained": "--SCENE 1--\nNARRATION: Most people think AI is decades away from being truly useful. What if I told you it's already changing your life in ways you haven't noticed?\nVISUAL: STOCK FOOTAGE: Fast-paced montage of everyday AI interactions - phone notifications, smart home devices, recommendation algorithms, with text overlay 'AI Is Already Here'",
    "Deep Tech": "--SCENE 1--\nNARRATION: There's a technology so advanced that most engineers don't fully understand how it works. Yet it's powering the next generation of computing.\nVISUAL: DIAGRAM ANIMATION: Abstract visualization of a complex neural network with data flowing through layers, glowing nodes activating in sequence",
    "Code & Build": "--SCENE 1--\nNARRATION: You've been writing code for months. But there's one concept that separates beginners from senior engineers - and it's simpler than you think.\nVISUAL: CODE SNIPPET: A split screen showing messy code on the left transforming into clean, well-structured code on the right",
    "Tool Tutorials": "--SCENE 1--\nNARRATION: Everyone's talking about this tool. But 90% of people are using it wrong. Here's the right way that actually gets results.\nVISUAL: SCREEN RECORDING: A cursor navigating through a popular tool interface, with a '90% do it wrong' overlay appearing",
    "AI News": "--SCENE 1--\nNARRATION: This week, something happened in AI that barely made the news. And it might be the most important development of the year.\nVISUAL: STOCK FOOTAGE: News-style footage with headlines flashing, zooming into one specific headline that glows",
    "Paper Breakdowns": "--SCENE 1--\nNARRATION: A research paper was just published that quietly solves one of AI's biggest problems. Here's what it means for everyone.\nVISUAL: DIAGRAM ANIMATION: A stylized academic paper with key equations highlighted, then a 'problem solved' animation",
    "Industry Analysis": "--SCENE 1--\nNARRATION: The industry is about to change. Not in five years. Not next year. Right now. And most companies aren't ready.\nVISUAL: STOCK FOOTAGE: Corporate buildings with a clock overlay ticking, then a graph showing a sudden market shift",
    "Career & Learning": "--SCENE 1--\nNARRATION: The skills that got you hired last year won't keep you employed next year. Here's what's changing and how to stay ahead.\nVISUAL: STATIC IMAGE: A roadmap showing old skills fading out and new skills emerging, with a 'future-proof' path highlighted",
}


def has_prohibited_content(topic: str) -> bool:
    topic_lower = topic.lower()
    for pattern in PROHIBITED_TOPIC_PATTERNS:
        if re.search(pattern, topic_lower):
            print(f"[SAFETY] Topic contains prohibited content (matched: {pattern}): {topic[:60]}")
            return True
    return False


HOOK_FORMULAS = [
    "question — Pose a surprising question the viewer wants answered",
    "bold_claim — Start with a counter-intuitive or impressive statement",
    "statistic — Lead with a striking number or data point",
    "story — Open with a brief anecdote or hypothetical scenario",
    "pattern_interrupt — Break an expectation (e.g. 'Everything you know about X is wrong')",
    "curiosity_gap — Tease something the viewer doesn't know",
    "pain_point — Name a frustration the viewer experiences",
]


def _detect_leaked_prompt(text: str) -> bool:
    """Check if text contains leaked meta-prompt instructions instead of actual script content."""
    lower = text.lower()
    for pattern in LEAKED_PROMPT_PATTERNS:
        if pattern in lower:
            return True
    return False


def extract_hook(script_text: str, max_chars: int = 300) -> str:
    lines = script_text.strip().split("\n")
    narration_lines = []
    for line in lines:
        if line.upper().startswith("NARRATION:") or line.startswith("NARRATION:"):
            text = re.sub(r"^NARRATION:\s*", "", line, flags=re.IGNORECASE)
            narration_lines.append(text.strip())
        elif line.upper().startswith("--SCENE"):
            continue
    if not narration_lines:
        return script_text[:max_chars]
    if len(narration_lines) > 0 and _detect_leaked_prompt(narration_lines[0]):
        narration_lines = narration_lines[1:]
    first_narration = " ".join(narration_lines) if narration_lines else script_text
    if _detect_leaked_prompt(first_narration):
        return ""
    return first_narration[:max_chars]


SCORING_PROMPT = """You are a hook optimization expert for tech educational videos.
Analyze the opening lines of this script and score the hook.

Score criteria (0-100, higher is better):
- Curiosity Gap (0-25): Does it make the viewer NEED to know the answer?
- Emotional Trigger (0-25): Does it spark surprise, awe, or urgency?
- Relevance (0-25): Does the target tech audience immediately care?
- Clarity (0-25): Is the hook instantly understandable?

FORMULAS (best for tech content):
1. Question: "How does GPT-4 actually work under the hood?"
2. Bold Claim: "The transformer paper changed AI forever — here's why."
3. Statistic: "90% of AI startups fail in the first year."
4. Curiosity Gap: "There's one architecture almost no one talks about..."
5. Pain Point: "Stuck on slow inference? Here's the fix."

Return ONLY JSON:
{
  "hook_score": 0-100,
  "formula_used": "question|bold_claim|statistic|curiosity_gap|pain_point|story|pattern_interrupt|none",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "suggested_alternatives": ["Hook alternative 1", "Hook alternative 2", "Hook alternative 3"],
  "approved": true_or_false
}

A hook is UNACCEPTABLE (approved=false) if:
- It's generic ("Today we'll learn about...")
- It's too slow to grab attention
- It lacks a clear value proposition
- Score is below 60"""


def _rule_based_score(hook: str) -> dict:
    text = hook.lower().strip()
    score = 50
    strengths = []
    weaknesses = []

    if not text or len(text) < 10:
        return {"score": 30, "hook_score": 30, "approved": False, "hook_text": hook, "strengths": [], "weaknesses": ["Hook too short"], "suggested_alternatives": ["Start with a surprising question about your topic"]}

    generic_openers = ["today we", "in this video", "in this tutorial", "welcome to", "let's learn", "in this article", "have you ever wondered"]
    for phrase in generic_openers:
        if text.startswith(phrase):
            score -= 20
            weaknesses.append("Generic opening — doesn't grab attention")
            break

    if "?" in text:
        score += 25
        strengths.append("Uses a question to create curiosity gap")

    digit_count = sum(c.isdigit() for c in text)
    if digit_count >= 2:
        score += 20
        strengths.append("Uses specific numbers/statistics")
    elif digit_count >= 1:
        score += 10
        strengths.append("References a data point")

    bold_markers = ["nobody", "everyone", "wrong", "secret", "truth", "actually", "real reason", "why most", "what if", "imagine", "stop", "never", "always", "the truth"]
    if any(m in text for m in bold_markers):
        score += 20
        strengths.append("Creates curiosity gap with bold framing")

    curiosity_markers = ["here's why", "here's how", "the reason", "what happens", "this is why", "one thing", "the problem"]
    if any(m in text for m in curiosity_markers):
        score += 15
        strengths.append("Teases information the viewer wants")

    pain_markers = ["struggle", "frustrat", "annoy", "waste", "hard", "difficult", "complicated", "confus", "stuck"]
    if any(m in text for m in pain_markers):
        score += 15
        strengths.append("Addresses a pain point")

    if len(text) > 300:
        score -= 10
        weaknesses.append("Hook is too long — may lose viewer interest")

    score = max(0, min(100, score))
    approved = score >= 60

    result = {
        "score": score,
        "hook_score": score,
        "hook_text": hook,
        "approved": approved,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggested_alternatives": [],
    }
    if not approved:
        if not weaknesses:
            weaknesses.append("Score below threshold ({}/100)".format(score))
    return result


def score_hook(script_text: str, category: str = "", format_type: str = "shorts") -> dict:
    if has_prohibited_content(script_text):
        return {"score": 0, "hook_score": 0, "approved": False, "weaknesses": ["Topic contains prohibited content"], "suggested_alternatives": []}
    hook = extract_hook(script_text)
    if not hook:
        return {"score": 0, "hook_score": 0, "approved": False, "weaknesses": ["No narration text found"], "suggested_alternatives": ["Start with a surprising question about your topic"]}
    if _detect_leaked_prompt(hook):
        return {"score": 70, "hook_score": 70, "approved": True, "hook_text": hook, "weaknesses": ["Leaked meta-text detected, auto-approved"], "suggested_alternatives": []}
    prompt = f"""Script category: {category}
Format: {format_type}
Hook text (first {len(hook)} chars):
"{hook}"

Score this hook and suggest improvements."""
    try:
        response = generate_completion(prompt=prompt, system_prompt=SCORING_PROMPT, temperature=0.3, max_tokens=800, caller_id="hook_scorer")
        import json
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(response[json_start:json_end])
            result["hook_text"] = hook
            if "hook_score" in result and "score" not in result:
                result["score"] = result["hook_score"]
            return result
    except Exception:
        print(f"[HOOK] LLM scoring failed — using rule-based fallback")
    return _rule_based_score(hook)


def _is_valid_rewrite(text: str) -> bool:
    stripped = text.strip()
    has_scene_marker = stripped.upper().startswith("--SCENE 1") or "NARRATION:" in stripped.upper()
    has_narration = "NARRATION:" in stripped.upper()
    has_no_meta = (
        "original script" not in stripped.lower()
        and "please provide" not in stripped.lower()
        and "i need the existing" not in stripped.lower()
        and "rewrite" not in stripped.lower()[:50]
    )
    return has_scene_marker and has_narration and has_no_meta


def _get_fallback_hook(category: str) -> str:
    for cat_key in CATEGORY_FALLBACK_HOOKS:
        if cat_key.lower() in category.lower():
            return CATEGORY_FALLBACK_HOOKS[cat_key]
    return CATEGORY_FALLBACK_HOOKS["AI Explained"]


def enforce_rewrite(script_text: str, category: str = "") -> str:
    result = check_and_improve_hook(script_text, category)
    if result["passed"] or not result.get("rewrite"):
        return script_text
    rewrite = result["rewrite"].strip()
    if _is_valid_rewrite(rewrite):
        lines = script_text.split("\n")
        for i, line in enumerate(lines):
            if i > 0 and line.strip().upper().startswith("--SCENE"):
                return rewrite + "\n" + "\n".join(lines[i:])
        return rewrite + "\n" + script_text
    fallback = _get_fallback_hook(category)
    print(f"[HOOK] Using curated fallback hook for category: {category}")
    lines = script_text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("--SCENE"):
            return fallback + "\n" + "\n".join(lines[i:])
    return fallback + "\n" + script_text


def check_and_improve_hook(script_text: str, category: str = "", format_type: str = "shorts", min_score: int = 60) -> dict:
    result = score_hook(script_text, category, format_type)
    if result.get("approved") and result.get("hook_score", 0) >= min_score:
        return {"passed": True, "result": result, "rewrite": None}
    alternatives = result.get("suggested_alternatives", [])
    if not alternatives:
        category_hints = {"gaming": "surprising game mechanic or a bold claim about player skill", "AI News": "counter-intuitive AI fact or a surprising prediction", "tech": "mind-blowing tech statistic or a curiosity gap"}
        hint = category_hints.get(category.lower(), "bold claim or question")
        alternatives = [f"Start with a {hint}"]
    rewrite_prompt = f"""Rewrite the opening of this script to have a stronger hook.
Current hook issues: {', '.join(result.get('weaknesses', ['weak']))}
Try one of these formulas: {', '.join(alternatives[:2]) if alternatives else 'bold claim or question'}
Keep the same topic and educational tone. Only change the first 1-3 sentences.
CRITICAL: Return ONLY the rewritten first scene in this exact format — no commentary, no explanation:
--SCENE 1--
NARRATION: [rewritten hook]
VISUAL: [matching visual]"""
    try:
        rewrite = generate_completion(prompt=rewrite_prompt, system_prompt="You rewrite video script hooks for maximum engagement. Return ONLY the rewritten scene — no preamble, no commentary.", temperature=0.7, max_tokens=500, caller_id="hook_rewrite")
        return {"passed": False, "result": result, "rewrite": rewrite}
    except Exception:
        return {"passed": False, "result": result, "rewrite": None}
