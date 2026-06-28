import re
from utils.groq_client import generate_completion

PROHIBITED_TOPIC_PATTERNS = [
    r'\bp[\._\s]*[o0][\._\s]*r[\._\s]*n[\._\s]*[o0]\b',
    r'\bs[\._\s]*e[\._\s]*x[\._\s]*\b',
    r'\bf[\._\s]*u[\._\s]*c[\._\s]*k\b',
    r'\bs[\._\s]*h[\._\s]*i[\._\s]*t\b',
    r'\bn[\._\s]*i[\._\s]*g[\._\s]*g[\._\s]*[e3]\b',
    r'\bb[\._\s]*i[\._\s]*t[\._\s]*c[\._\s]*h\b',
    r'\bd[\._\s]*i[\._\s]*c[\._\s]*k\b',
]


def has_prohibited_content(topic: str) -> bool:
    import re
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


def extract_hook(script_text: str, max_chars: int = 300) -> str:
    lines = script_text.strip().split("\n")
    narration_lines = []
    for line in lines:
        if line.upper().startswith("NARRATION:") or line.startswith("NARRATION:"):
            text = re.sub(r"^NARRATION:\s*", "", line, flags=re.IGNORECASE)
            narration_lines.append(text.strip())
        elif line.upper().startswith("--SCENE"):
            continue
    first_narration = " ".join(narration_lines) if narration_lines else script_text
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


def score_hook(script_text: str, category: str = "", format_type: str = "shorts") -> dict:
    if has_prohibited_content(script_text):
        return {"score": 0, "hook_score": 0, "approved": False, "weaknesses": ["Topic contains prohibited content"], "suggested_alternatives": []}
    hook = extract_hook(script_text)
    if not hook:
        return {"score": 0, "hook_score": 0, "approved": False, "weaknesses": ["No narration text found"], "suggested_alternatives": ["Start with a surprising question about your topic"]}
    prompt = f"""Script category: {category}
Format: {format_type}
Hook text (first {len(hook)} chars):
"{hook}"

Score this hook and suggest improvements."""
    try:
        response = generate_completion(prompt=prompt, system_prompt=SCORING_PROMPT, temperature=0.3, max_tokens=800)
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
        pass
    return {
        "score": 50,
        "hook_score": 50,
        "hook_text": hook,
        "approved": True,
        "strengths": [],
        "weaknesses": ["Could not evaluate with LLM, using default approval"],
        "suggested_alternatives": [],
    }


def enforce_rewrite(script_text: str) -> str:
    result = check_and_improve_hook(script_text)
    if result["passed"] or not result.get("rewrite"):
        return script_text
    rewrite = result["rewrite"].strip()
    lines = script_text.split("\n")
    for i, line in enumerate(lines):
        if i > 0 and line.strip().upper().startswith("--SCENE"):
            return rewrite + "\n" + "\n".join(lines[i:])
    return rewrite + "\n" + script_text


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
Return ONLY the rewritten first scene in this format:
--SCENE 1--
NARRATION: [rewritten hook]
VISUAL: [matching visual]"""
    try:
        rewrite = generate_completion(prompt=rewrite_prompt, system_prompt="You rewrite video script hooks for maximum engagement.", temperature=0.7, max_tokens=500)
        return {"passed": False, "result": result, "rewrite": rewrite}
    except Exception:
        return {"passed": False, "result": result, "rewrite": None}
