import re

CATEGORY_KEYWORDS = {
    "AI Explained": [
        "neural network", "transformer", "machine learning", "deep learning",
        "artificial intelligence", "llm", "gpt", "diffusion", "backpropagation",
        "gradient descent", "attention mechanism", "embedding", "tokenization",
        "fine-tuning", "inference", "training data", "model architecture",
        "supervised", "unsupervised", "reinforcement learning",
    ],
    "Code & Build": [
        "python", "javascript", "typescript", "react", "api", "docker",
        "deployment", "git", "function", "class", "import", "npm",
        "framework", "library", "compiler", "debug", "refactor",
    ],
    "Deep Tech": [
        "architecture", "protocol", "distributed", "consensus", "cryptography",
        "compiler", "kernel", "operating system", "database internals",
        "concurrency", "parallel", "low-level", "memory management",
    ],
    "Paper Breakdowns": [
        "arxiv", "paper", "research", "proposed method", "state-of-the-art",
        "benchmark", "dataset", "ablation", "baseline", "SOTA",
        "novel approach", "our method", "experimental results",
    ],
    "Tool Tutorials": [
        "tutorial", "guide", "how to", "step by step", "setup",
        "installation", "configure", "workflow", "integration",
        "plugin", "extension", "command line", "cli",
    ],
    "Industry Analysis": [
        "market", "industry", "revenue", "funding", "acquisition",
        "valuation", "ipo", "startup", "growth", "trend",
        "adoption", "enterprise", "business model",
    ],
    "AI News": [
        "announced", "released", "launch", "update", "new feature",
        "yesterday", "today", "this week", "latest", "breaking",
        "news", "unveiled", "partnership", "acquisition",
    ],
    "Career & Learning": [
        "career", "job", "salary", "interview", "resume",
        "learning path", "roadmap", "beginner", "advanced",
        "skill", "certification", "course", "bootcamp",
    ],
}


def detect_category(script: str, default: str = "AI Explained") -> str:
    if not script:
        return default
    lower = script.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            score += len(re.findall(re.escape(kw), lower))
        if score > 0:
            scores[cat] = score
    if not scores:
        return default
    return max(scores, key=scores.get)
