import re
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ManimTiming(BaseModel):
    entry: float = Field(default=0.5, ge=0, le=5, description="Seconds for entry animation")
    dwell: float = Field(default=4.0, ge=1, le=60, description="Seconds the main content is visible")
    exit: float = Field(default=0.5, ge=0, le=5, description="Seconds for exit/fade animation")


class ManimScenePlan(BaseModel):
    template_name: str = Field(description="One of: neural_network, attention, transformer, algorithm_flow, bar_chart, text_reveal, gradient_descent, convolution, recurrent, custom")
    params: dict = Field(default_factory=dict, description="Template-specific parameters (title, labels, values, layers, etc.)")
    timing: ManimTiming = Field(default_factory=ManimTiming, description="Animation timing config")
    scene_type: str = Field(default="educational", description="educational | technical | data_viz | overview")
    reason: str = Field(default="", description="Why this template was chosen for this scene")


TEMPLATE_KEYWORDS: dict[str, list[str]] = {
    "neural_network": ["neural", "network", "layer", "deep learning", "mlp", "perceptron", "neuron", "feedforward", "fully connected"],
    "attention": ["attention", "qkv", "query", "key", "value", "self-attention", "multi-head", "attn"],
    "transformer": ["transformer", "encoder", "decoder", "architecture", "block", "encoder-decoder", "bert", "gpt"],
    "algorithm_flow": ["flow", "pipeline", "process", "step", "stage", "algorithm", "sequential", "workflow", "diagram"],
    "bar_chart": ["chart", "graph", "comparison", "performance", "benchmark", "metric", "stat", "accuracy", "bar"],
    "text_reveal": ["reveal", "insight", "key", "takeaway", "conclusion", "summary", "important", "lesson", "quote"],
    "gradient_descent": ["gradient", "descent", "optimization", "loss surface", "convergence", "learning rate", "saddle", "minimum", "optimizer"],
    "convolution": ["convolution", "conv", "kernel", "filter", "feature map", "cnn", "stride", "pooling", "convnet"],
    "recurrent": ["recurrent", "rnn", "lstm", "gru", "sequence", "hidden state", "time step", "recurrence", "memory"],
    "loss_landscape": ["loss", "landscape", "surface", "optimization path", "saddle point", "loss surface", "convergence", "gradient descent path", "minimum", "local minima"],
    "embedding_space": ["embedding", "vector space", "word vector", "latent space", "embedding space", "dimensionality reduction", "projection", "semantic space", "representation"],
    "decision_boundary": ["decision boundary", "classification", "classifier", "separating", "hyperplane", "binary classification", "class boundary", "logistic regression", "svm"],
    "matrix_multiplication": ["matrix", "multiplication", "dot product", "linear algebra", "matrix multiply", "matmul", "tensor product", "matrix operation", "matrix product"],
    "backpropagation": ["backpropagation", "backprop", "backward pass", "gradient flow", "chain rule", "gradient descent", "update weights", "weight update", "loss gradient"],
    "probability_distribution": ["probability", "distribution", "gaussian", "normal distribution", "pdf", "density", "statistics", "likelihood", "bayesian", "sampling", "random variable"],
    "intro": ["intro", "brand", "channel id", "channel_brand", "opening", "introduction"],
    "outro": ["outro", "subscribe", "cta", "call to action", "ending", "subscribe button", "closing"],
}


def _detect_scene_type(desc_lower: str) -> str:
    if any(kw in desc_lower for kw in ["benchmark", "compare", "chart", "graph", "metric", "accuracy", "latency", "throughput"]):
        return "data_viz"
    if any(kw in desc_lower for kw in ["overview", "survey", "roadmap", "history", "timeline", "evolution"]):
        return "overview"
    if any(kw in desc_lower for kw in ["math", "equation", "formula", "derivation", "function"]):
        return "technical"
    return "educational"


def _extract_numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"\d+\.?\d*", text) if float(n) < 1000]


def _infer_timing(scene: dict, desc: str) -> ManimTiming:
    dur = scene.get("target_duration", scene.get("duration", 6.0))
    entry = min(0.8, dur * 0.1)
    exit_t = min(0.5, dur * 0.08)
    dwell = max(dur - entry - exit_t, 2.0)
    return ManimTiming(entry=round(entry, 1), dwell=round(dwell, 1), exit=round(exit_t, 1))


def _extract_title(scene: dict, desc: str) -> str:
    if scene.get("text") and isinstance(scene["text"], list):
        first = scene["text"][0]
        if isinstance(first, dict) and first.get("text"):
            return first["text"]
    if scene.get("title"):
        return scene["title"]
    words = desc.split()[:6]
    return " ".join(words).title() if words else "Concept"


def _build_params(scene: dict, tmpl: str, desc_lower: str, desc: str) -> dict:
    params = {"title": _extract_title(scene, desc)}
    nums = _extract_numbers(desc)

    if tmpl == "gradient_descent":
        lr_candidates = [n for n in nums if 0.001 <= n <= 1.0]
        if lr_candidates:
            params["learning_rate"] = lr_candidates[0]
        step_candidates = [int(n) for n in nums if 3 <= int(n) <= 50]
        if step_candidates:
            params["num_steps"] = step_candidates[0]

    elif tmpl == "neural_network":
        if len(nums) >= 2:
            params["input_dim"] = int(nums[0])
            params["output_dim"] = int(nums[-1])
        if len(nums) >= 3:
            params["hidden_dims"] = [int(n) for n in nums[1:-1]]
        if "deep" in desc_lower:
            params.setdefault("hidden_dims", [6, 8, 6])

    elif tmpl == "bar_chart":
        scene_texts = scene.get("text", [])
        if isinstance(scene_texts, list) and len(scene_texts) > 1:
            labels = []
            values = []
            for t in scene_texts:
                if isinstance(t, dict):
                    labels.append(t.get("text", ""))
                    txt = t.get("text", "")
                    v = [n for n in _extract_numbers(txt) if n < 1000]
                    values.append(v[0] if v else 5.0)
            if labels and values:
                params["labels"] = labels[:8]
                params["values"] = values[:8]

    elif tmpl == "algorithm_flow":
        scene_texts = scene.get("text", [])
        if isinstance(scene_texts, list) and len(scene_texts) > 1:
            steps = [t.get("text", "") for t in scene_texts if isinstance(t, dict) and t.get("text")]
            if steps:
                params["steps"] = steps[:6]

    elif tmpl == "text_reveal":
        scene_texts = scene.get("text", [])
        lines = []
        for t in (scene_texts if isinstance(scene_texts, list) else []):
            if isinstance(t, dict) and t.get("text"):
                lines.append(t["text"])
        if not lines:
            lines = scene.get("asset_keywords", ["Key Insight", "From the data"])
        params["lines"] = lines[:5]

    elif tmpl == "convolution":
        if len(nums) >= 1:
            params["kernel_size"] = int(nums[0]) if nums[0] in (3, 5, 7) else 3
        if "rgb" in desc_lower:
            params["input_channels"] = 3

    elif tmpl == "recurrent":
        if len(nums) >= 1:
            params["num_steps"] = min(int(nums[0]), 8)

    return params


def enhance_manim_params(scene: dict) -> dict:
    """Build a ManimScenePlan from scene description using heuristics."""
    desc = (scene.get("description") or "") + " " + " ".join(scene.get("asset_keywords", []))
    desc_lower = desc.lower()

    tmpl = None
    max_score = 0
    for name, kws in TEMPLATE_KEYWORDS.items():
        score = sum(2 if kw in desc_lower else 0 for kw in kws)
        if score > max_score:
            max_score = score
            tmpl = name

    if not tmpl:
        if max_score == 0:
            tmpl = "custom"
        else:
            tmpl = "text_reveal"

    params = _build_params(scene, tmpl, desc_lower, desc)
    timing = _infer_timing(scene, desc)
    scene_type = _detect_scene_type(desc_lower)

    return ManimScenePlan(
        template_name=tmpl,
        params=params,
        timing=timing.model_dump(),
        scene_type=scene_type,
        reason=f"Keyword match score {max_score} for template '{tmpl}' in scene description"
    )


def create_manim_agent_crew(scene_description: str = "", category: str = "AI Explained", format_type: str = "long"):
    from crewai import Agent, Task, Crew
    from utils.llm_helper import get_llm

    llm = get_llm(temperature=0.3, max_tokens=2000)

    agent = Agent(
        role="Manim Scene Designer",
        goal="Select the best Manim template and configure parameters for educational tech/animation content",
        backstory="""You specialize in translating educational AI/tech concepts into Manim animation scenes.
You maintain a library of pre-built templates:
- neural_network: MLP/neural network diagrams with animated layers and connections
- attention: Self-attention / QKV pathway visualization with heatmaps
- transformer: Full encoder-decoder architecture with sublayer animations
- gradient_descent: 3D loss surface with optimization path and step counter
- algorithm_flow: Sequential process/workflow diagram with animated arrows
- bar_chart: Data comparison and benchmark bars with animated growth
- text_reveal: Key insight / takeaway text typewriter reveals with highlight frames
- convolution: CNN kernel sliding over feature maps with pooling visualization
- recurrent: RNN/LSTM cell with hidden state propagation through time steps

For novel scenes, return template_name "custom" with a description of what to build.""",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    task = Task(
        description=f"""Analyze this scene and select the best Manim template.

Scene description: {scene_description}
Category: {category}
Format: {format_type}

Return a ManimScenePlan with:
- template_name: one of neural_network, attention, transformer, algorithm_flow, bar_chart, text_reveal, gradient_descent, convolution, recurrent, custom
- params: dict with title, and template-specific fields (labels, values, layers, lines, etc.)
- timing: dict with entry, dwell, exit in seconds
- scene_type: educational | technical | data_viz | overview
- reason: briefly explain why this template fits""",
        expected_output="""
{{
  "template_name": "neural_network",
  "params": {{
    "title": "How Neural Networks Learn",
    "input_dim": 3,
    "hidden_dims": [5, 4],
    "output_dim": 2
  }},
  "timing": {{
    "entry": 0.5,
    "dwell": 4.0,
    "exit": 0.5
  }},
  "scene_type": "educational",
  "reason": "Scene describes neural network layers and forward propagation"
}}
""",
        agent=agent,
        output_pydantic=ManimScenePlan,
    )

    return Crew(agents=[agent], tasks=[task], verbose=False, memory=False, planning=False, cache=False)


def select_template_llm(scene: dict) -> ManimScenePlan | None:
    """Use CrewAI agent to pick a template for a scene (slower but more flexible than heuristic)."""
    desc = (scene.get("description") or "") + " " + " ".join(scene.get("asset_keywords", []))
    if not desc.strip():
        return None
    try:
        crew = create_manim_agent_crew(scene_description=desc)
        result = crew.kickoff()
        if result:
            if hasattr(result, "pydantic") and result.pydantic:
                return result.pydantic
            if isinstance(result, ManimScenePlan):
                return result
        return None
    except Exception as e:
        logger.debug(f"[ManimAgent] LLM template selection failed: {e}")
        return None
