import textwrap

INJECT_IMPORTS = """# manim
from manim import *
import numpy as np
config.disable_caching = True
config.verbosity = "WARNING"
"""


def neural_network_template(
    input_dim: int = 3,
    hidden_dims: list[int] = None,
    output_dim: int = 2,
    title: str = "Neural Network",
    duration: float = 6.0,
    layer_labels: list[str] = None,
    node_color: str = "#4ECDC4",
    edge_color: str = "#A29BFE",
) -> str:
    if hidden_dims is None:
        hidden_dims = [4, 5]
    hl = hidden_dims[:2]
    dims = [input_dim] + hl + [output_dim]
    if layer_labels is None:
        layer_labels = [f"Layer {i}" for i in range(len(dims))]
    template = INJECT_IMPORTS + """
class NeuralNetworkScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text))
        self.wait(0.3)
        layers = VGroup()
        spacing = 2.5
        max_nodes = __MAX_NODES__
        node_radius = 0.22
        dims = __DIMS__
        layer_labels = __LAYER_LABELS__
        for li, n_nodes in enumerate(dims):
            col = VGroup()
            for ni in range(n_nodes):
                y_offset = (max_nodes - n_nodes) * node_radius
                dot = Circle(radius=node_radius, color="__NODE_COLOR__", fill_opacity=0.8)
                dot.move_to([li * spacing - (len(dims)-1) * spacing / 2, ni * node_radius * 2.5 + y_offset - (max_nodes-1) * node_radius * 1.25, 0])
                col.add(dot)
            layers.add(col)
            label = Text(layer_labels[li] if li < len(layer_labels) else "", font_size=16, color=GRAY)
            label.next_to(col, DOWN, buff=0.3)
            self.play(Create(col), Write(label), run_time=0.5)
        self.wait(0.3)
        edges = VGroup()
        for li in range(len(dims) - 1):
            for d1 in layers[li]:
                for d2 in layers[li + 1]:
                    line = Line(d1.get_center(), d2.get_center(), stroke_width=1.5, stroke_opacity=0.3, color="__EDGE_COLOR__")
                    edges.add(line)
        if edges:
            self.play(Create(edges), run_time=1.0)
        self.wait(1.0)
        highlight = Circle(radius=0.3, color=YELLOW, stroke_width=3, fill_opacity=0)
        self.play(highlight.animate.move_to(layers[-1].get_center()), run_time=0.5)
        last_layer_center = layers[-1].get_center()
        output_label = Text("Output", font_size=20, color=YELLOW).move_to(last_layer_center + RIGHT * 0.8)
        self.play(Write(output_label))
        remaining = max(0, __DURATION__ - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__DIMS__", str(dims))
        .replace("__MAX_NODES__", str(max(dims)))
        .replace("__LAYER_LABELS__", str(layer_labels))
        .replace("__NODE_COLOR__", node_color)
        .replace("__EDGE_COLOR__", edge_color)
        .replace("__DURATION__", str(duration))
    )


def attention_template(
    num_heads: int = 4,
    query_dim: int = 64,
    title: str = "Attention Mechanism",
    duration: float = 6.0,
) -> str:
    template = INJECT_IMPORTS + """
class AttentionScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text))
        self.wait(0.3)
        sq_size = 0.35
        gap = 0.08
        def make_matrix(rows, cols, label, color_hex):
            group = VGroup()
            for r in range(rows):
                for c in range(cols):
                    sq = Square(side_length=sq_size, fill_opacity=0.6, fill_color=color_hex, stroke_width=1)
                    sq.move_to([c * (sq_size + gap) - (cols-1) * (sq_size + gap) / 2, -(r * (sq_size + gap) - (rows-1) * (sq_size + gap) / 2), 0])
                    group.add(sq)
            lbl = Text(label, font_size=16, color=color_hex).next_to(group, DOWN, buff=0.3)
            group.add(lbl)
            return group
        q = make_matrix(8, 4, "Query", "#FF6B6B")
        k = make_matrix(8, 4, "Key", "#4ECDC4")
        v = make_matrix(8, 4, "Value", "#A29BFE")
        q.move_to([-3.5, 0, 0])
        k.move_to([0, 0, 0])
        v.move_to([3.5, 0, 0])
        self.play(Create(q), Create(k), Create(v), run_time=1.0)
        self.wait(0.5)
        arrow_qk = Arrow(q.get_center(), k.get_center(), color=YELLOW, stroke_width=3)
        score_label = Text("Q \u00b7 K\u1d40", font_size=30, color=YELLOW).move_to([-1.75, 1.5, 0])
        self.play(Create(arrow_qk), Write(score_label), run_time=0.8)
        self.wait(0.5)
        arrow_kv = Arrow(k.get_center(), v.get_center(), color=YELLOW, stroke_width=3)
        softmax_label = Text("Softmax", font_size=28, color=ORANGE).move_to([1.75, 1.5, 0])
        self.play(Create(arrow_kv), Write(softmax_label), run_time=0.8)
        self.wait(0.5)
        result_label = Text("Weighted Sum", font_size=24, color=GREEN).next_to(q, LEFT, buff=0.8)
        self.play(Write(result_label))
        remaining = max(0, __DURATION__ - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return template.replace("__TITLE__", title).replace("__DURATION__", str(duration))


def transformer_block_template(
    title: str = "Transformer Architecture",
    duration: float = 6.0,
    num_encoder_layers: int = 2,
    num_decoder_layers: int = 2,
) -> str:
    template = INJECT_IMPORTS + """
class TransformerScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text))
        self.wait(0.3)
        box_w, box_h = 2.2, 0.55
        enc_count = __ENC_LAYERS__
        dec_count = __DEC_LAYERS__
        def enc_block(y, label):
            box = Rectangle(width=box_w, height=box_h * 2.5, fill_opacity=0.15, fill_color=BLUE, stroke_color=BLUE_C, stroke_width=2)
            box.move_to([-2.5, y, 0])
            lbl = Text(label, font_size=14, color=BLUE_C).next_to(box, UP, buff=0.1)
            mha = Text("Multi-Head\\nAttention", font_size=11, color=WHITE).move_to(box.get_center() + UP * box_h * 0.6)
            ff = Text("Feed\\nForward", font_size=11, color=WHITE).move_to(box.get_center() - UP * box_h * 0.6)
            return VGroup(box, lbl, mha, ff), box
        def dec_block(y, label):
            box = Rectangle(width=box_w, height=box_h * 3.5, fill_opacity=0.15, fill_color=GREEN, stroke_color=GREEN_C, stroke_width=2)
            box.move_to([2.5, y, 0])
            lbl = Text(label, font_size=14, color=GREEN_C).next_to(box, UP, buff=0.1)
            mmha = Text("Masked\\nMulti-Head Attn", font_size=10, color=WHITE).move_to(box.get_center() + UP * box_h * 1.0)
            mha = Text("Multi-Head\\nAttention", font_size=10, color=WHITE).move_to(box.get_center())
            ff = Text("Feed\\nForward", font_size=10, color=WHITE).move_to(box.get_center() - UP * box_h * 1.0)
            return VGroup(box, lbl, mmha, mha, ff), box
        inputs = Text("Input\\nEmbedding", font_size=14, color=GRAY).move_to([-2.5, -3.0, 0])
        outputs = Text("Output\\nEmbedding", font_size=14, color=GRAY).move_to([2.5, -3.0, 0])
        pos_enc_in = Text("+ Positional\\n  Encoding", font_size=10, color=GRAY, opacity=0.7).next_to(inputs, DOWN, buff=0.15)
        pos_enc_out = Text("+ Positional\\n  Encoding", font_size=10, color=GRAY, opacity=0.7).next_to(outputs, DOWN, buff=0.15)
        self.play(Create(inputs), Create(outputs), run_time=0.5)
        self.play(Write(pos_enc_in), Write(pos_enc_out), run_time=0.3)
        enc_groups = []
        prev_bx = None
        for i in range(enc_count):
            g, bx = enc_block(2.0 - i * 2.2, f"Encoder Layer {i+1}")
            enc_groups.append(g)
            self.play(Create(g), run_time=0.5)
            if prev_bx is not None:
                arrow = Arrow(prev_bx.get_bottom(), bx.get_top(), stroke_width=2, color=BLUE_D)
                self.play(Create(arrow), run_time=0.3)
            prev_bx = bx
        dec_groups = []
        prev_dec_bx = None
        for i in range(dec_count):
            g, bx = dec_block(2.5 - i * 2.5, f"Decoder Layer {i+1}")
            dec_groups.append(g)
            self.play(Create(g), run_time=0.5)
            if prev_dec_bx is not None:
                arrow = Arrow(prev_dec_bx.get_bottom(), bx.get_top(), stroke_width=2, color=GREEN_D)
                self.play(Create(arrow), run_time=0.3)
            prev_dec_bx = bx
        cross_arrows = VGroup()
        for i in range(min(enc_count, dec_count)):
            enc_bottom = enc_groups[i][0].get_bottom()
            dec_center = dec_groups[i][0].get_center()
            arr = Arrow(enc_bottom, dec_center, stroke_width=1.5, color=YELLOW, stroke_opacity=0.4)
            cross_arrows.add(arr)
        if cross_arrows:
            self.play(Create(cross_arrows), run_time=0.5)
        linear = Rectangle(width=2.0, height=0.5, fill_opacity=0.2, fill_color=YELLOW, stroke_color=YELLOW_C, stroke_width=2)
        linear.move_to([0, -3.5, 0])
        linear_label = Text("Linear + Softmax", font_size=14, color=YELLOW_C).move_to(linear.get_center())
        self.play(Create(linear), Write(linear_label), run_time=0.5)
        output_probs = Text("Output\\nProbabilities", font_size=14, color=WHITE).next_to(linear, DOWN, buff=0.4)
        self.play(Write(output_probs))
        remaining = max(0, __DURATION__ - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__ENC_LAYERS__", str(num_encoder_layers))
        .replace("__DEC_LAYERS__", str(num_decoder_layers))
        .replace("__DURATION__", str(duration))
    )


def algorithm_flow_template(
    steps: list[str] = None,
    title: str = "Algorithm Flow",
    duration: float = 6.0,
) -> str:
    if steps is None:
        steps = ["Input", "Process", "Output"]
    template = INJECT_IMPORTS + """
class AlgorithmFlowScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text))
        self.wait(0.3)
        steps = __STEPS__
        prev_box = None
        for i, step_name in enumerate(steps):
            box = RoundedRectangle(width=2.0, height=0.7, corner_radius=0.1, fill_opacity=0.2, fill_color=BLUE, stroke_color=BLUE_C, stroke_width=2)
            box.move_to([0, 2.0 - i * 1.5, 0])
            label = Text(step_name, font_size=18, color=WHITE).move_to(box.get_center())
            group = VGroup(box, label)
            self.play(Create(group), run_time=0.4)
            if prev_box is not None:
                arrow = Arrow(prev_box.get_bottom(), box.get_top(), stroke_width=2, color=YELLOW)
                self.play(Create(arrow), run_time=0.3)
            prev_box = box
        glow = box.copy().set_stroke(YELLOW, width=6).set_fill(opacity=0)
        self.play(Create(glow), run_time=0.3)
        remaining = max(0, __DURATION__ - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return template.replace("__TITLE__", title).replace("__STEPS__", str(steps)).replace("__DURATION__", str(duration))


def bar_chart_template(
    labels: list[str] = None,
    values: list[float] = None,
    title: str = "Performance Comparison",
    duration: float = 6.0,
    bar_color: str = "#00D2FF",
) -> str:
    if labels is None:
        labels = ["A", "B", "C", "D"]
    if values is None:
        values = [3.0, 5.0, 2.0, 7.0]
    template = INJECT_IMPORTS + """
class BarChartScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text))
        self.wait(0.3)
        labels = __LABELS__
        values = __VALUES__
        max_val = max(values) if values else 1
        bar_width = 0.6
        total_width = len(labels) * (bar_width + 0.3)
        start_x = -total_width / 2 + bar_width / 2
        for i, (label, val) in enumerate(zip(labels, values)):
            height = (val / max_val) * 3.0
            bar = Rectangle(width=bar_width, height=0.01, fill_opacity=0.8, fill_color="__BAR_COLOR__", stroke_width=1)
            bar.move_to([start_x + i * (bar_width + 0.3), -1.5 + height / 2, 0])
            self.play(
                bar.animate.set_height(height).move_to([start_x + i * (bar_width + 0.3), -1.5 + height / 2, 0]),
                run_time=0.5
            )
            lbl = Text(str(label), font_size=16, color=GRAY).next_to(bar, DOWN, buff=0.15)
            val_lbl = Text(f"{val:.1f}", font_size=14, color=WHITE).next_to(bar, UP, buff=0.1)
            self.play(Write(lbl), Write(val_lbl), run_time=0.2)
        remaining = max(0, __DURATION__ - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__LABELS__", str(labels))
        .replace("__VALUES__", str(values))
        .replace("__BAR_COLOR__", bar_color)
        .replace("__DURATION__", str(duration))
    )


def text_reveal_template(
    lines: list[str] = None,
    title: str = "Key Insight",
    duration: float = 6.0,
    line_color: str = "#FFD93D",
) -> str:
    if lines is None:
        lines = ["Key Insight", "Emerges from", "the data"]
    template = INJECT_IMPORTS + """
class TextRevealScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text))
        lines = __LINES__
        text_group = VGroup()
        for i, line in enumerate(lines):
            t = Text(line, font_size=28 - min(len(line) // 10, 3) * 2, color="__LINE_COLOR__")
            t.move_to([0, 1.0 - i * 0.8, 0])
            self.play(Write(t), run_time=0.5)
            text_group.add(t)
        self.wait(1.0)
        glow = SurroundingRectangle(text_group, buff=0.2, color="__LINE_COLOR__", stroke_width=1, stroke_opacity=0.5)
        self.play(Create(glow), run_time=0.5)
        remaining = max(0, __DURATION__ - self.time)
        if remaining > 0:
            self.wait(remaining)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__LINES__", str(lines))
        .replace("__LINE_COLOR__", line_color)
        .replace("__DURATION__", str(duration))
    )
