TEMPLATE_REGISTRY = {}

TEMPLATE_KEYWORDS = {}

_template_order = []

def register_template(name, keywords, description="", engine="eevee", priority=5):
    TEMPLATE_REGISTRY[name] = {
        "name": name,
        "description": description,
        "engine": engine,
        "priority": priority,
        "keywords": keywords,
    }
    TEMPLATE_KEYWORDS[name] = keywords
    if name not in _template_order:
        _template_order.append(name)


def select_template(description, category="", engine_hint=""):
    desc_lower = description.lower()
    best_score = 0.0
    best = None
    for name in _template_order:
        info = TEMPLATE_REGISTRY[name]
        kws = info["keywords"]
        score = sum(2 for kw in kws if kw in desc_lower)
        if score == 0 and description:
            score = sum(1 for kw in kws if any(word in kw for word in desc_lower.split()))
        if engine_hint == "cycles" and info["engine"] == "cycles":
            score *= 1.2
        if score > best_score:
            best_score = score
            best = name
    if best and best_score > 0:
        return best, TEMPLATE_REGISTRY[best]["engine"], best_score / max(len(TEMPLATE_KEYWORDS.get(best, [])), 1)
    return None, "eevee", 0.0


def list_templates():
    return [(n, TEMPLATE_REGISTRY[n]["description"], TEMPLATE_REGISTRY[n]["engine"]) for n in _template_order]


register_template("chip_cross_section",
    ["chip", "die", "gpu", "cpu", "semiconductor", "transistor", "silicon", "wafer", "cutaway",
     "cross section", "processor", "core", "tensor", "cuda", "integrated circuit"],
    "GPU/CPU die with layered cutaway, highlighted blocks, transistor detail",
    engine="cycles", priority=9)

register_template("architecture_block",
    ["block diagram", "architecture", "hierarchy", "memory", "cache", "layout",
     "structure", "component", "module", "layer", "stack", "schematic"],
    "3D block diagrams with labeled components and connections",
    engine="eevee", priority=8)

register_template("data_flow",
    ["data flow", "particle", "arrow", "movement", "transfer", "traffic", "pipeline",
     "throughput", "stream", "flow", "path", "routing", "direction"],
    "Animated particles and arrows showing data movement through systems",
    engine="eevee", priority=7)

register_template("pcb_layout",
    ["pcb", "circuit board", "motherboard", "trace", "component", "hardware",
     "electronic", "solder", "connector", "bus", "slot", "socket"],
    "Circuit board with traces, labeled components and zoom effects",
    engine="eevee", priority=6)

register_template("cutaway_device",
    ["cutaway", "internal", "inside", "cross-section", "reveal", "peel",
     "exploded", "layers", "interior", "dissection", "breakdown"],
    "Device internals with peel-away layers revealing inner structure",
    engine="cycles", priority=8)

register_template("comparison_bars",
    ["comparison", "bar chart", "chart", "graph", "statistics", "data", "metric",
     "benchmark", "performance", "speed", "size comparison", "rating"],
    "3D bar and column charts for data comparison",
    engine="eevee", priority=5)

register_template("processor_pipeline",
    ["pipeline", "stage", "execute", "instruction", "fetch", "decode",
     "process", "step", "phase", "cycle", "clock"],
    "Pipeline stages with animated data tokens flowing through",
    engine="eevee", priority=6)

register_template("network_topology",
    ["network", "topology", "server", "cluster", "datacenter", "node",
     "connection", "distributed", "cloud", "infrastructure", "rack"],
    "Connected nodes representing network topology and server infrastructure",
    engine="eevee", priority=5)

register_template("timeline_3d",
    ["timeline", "history", "evolution", "progress", "milestone", "era",
     "generation", "version", "past", "future", "roadmap"],
    "Historical timeline with depth layers and event markers",
    engine="eevee", priority=4)

register_template("process_flow",
    ["process", "workflow", "flowchart", "sequence", "step by step",
     "procedure", "method", "production", "manufacturing"],
    "Process flow diagram with connected stages and animations",
    engine="eevee", priority=6)

register_template("layer_explosion",
    ["exploded view", "layers", "decomposition", "breakdown", "stack",
     "hierarchy", "nested", "component separation"],
    "Exploded view of layered systems with spreading animation",
    engine="cycles", priority=7)

register_template("neural_network",
    ["neural", "network", "deep learning", "layer", "neuron", "activation",
     "weight", "bias", "backpropagation", "forward pass", "ai model"],
    "Neural network visualization with firing nodes and weighted connections",
    engine="eevee", priority=6)
