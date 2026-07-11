import json
import textwrap

INJECT_IMPORTS = """# manim
from manim import *
import numpy as np
import json
config.disable_caching = True
config.verbosity = "WARNING"
"""


def _compute_grad_descent_path(learning_rate: float = 0.25, steps: int = 6) -> list[list[float]]:
    points = [[2.0, 2.0]]
    x, y = 2.0, 2.0
    for _ in range(steps):
        dzdx = 0.8 * x
        dzdy = 0.8 * y
        x = x - learning_rate * dzdx
        y = y - learning_rate * dzdy
        points.append([round(x, 4), round(y, 4)])
    return points


def neural_network_template(
    input_dim: int = 3,
    hidden_dims: list[int] = None,
    output_dim: int = 2,
    title: str = "Neural Network",
    duration: float = 6.0,
    layer_labels: list[str] = None,
    node_color: str = "#4ECDC4",
    edge_color: str = "#A29BFE",
    entry_time: float = 0.5,
    exit_time: float = 0.5,
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
        self.play(Write(title_text), run_time=__ENTRY__)
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
                dot = Circle(radius=node_radius, color="__NODE_COLOR__", fill_opacity=0.8, stroke_width=1.5)
                dot.move_to([li * spacing - (len(dims)-1) * spacing / 2, ni * node_radius * 2.5 + y_offset - (max_nodes-1) * node_radius * 1.25, 0])
                col.add(dot)
            layers.add(col)
            label = Text(layer_labels[li] if li < len(layer_labels) else "", font_size=16, color=GRAY)
            label.next_to(col, DOWN, buff=0.3)
            self.play(Create(col), Write(label), run_time=0.4)
        edges = VGroup()
        for li in range(len(dims) - 1):
            for d1 in layers[li]:
                for d2 in layers[li + 1]:
                    line = Line(d1.get_center(), d2.get_center(), stroke_width=1.5, stroke_opacity=0.3, color="__EDGE_COLOR__")
                    edges.add(line)
        if edges:
            self.play(Create(edges), run_time=0.8)
        self.wait(0.3)
        glow = Circle(radius=0.3, color=YELLOW, stroke_width=3, fill_opacity=0)
        self.play(glow.animate.move_to(layers[-1].get_center()), run_time=0.3)
        output_label = Text("Output", font_size=20, color=YELLOW).next_to(layers[-1], RIGHT, buff=0.5)
        self.play(Write(output_label), run_time=0.3)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(layers), FadeOut(edges), FadeOut(glow), FadeOut(output_label), run_time=__EXIT__)
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
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def attention_template(
    num_heads: int = 4,
    query_dim: int = 64,
    title: str = "Attention Mechanism",
    duration: float = 6.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class AttentionScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)
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
        self.play(Create(q), Create(k), Create(v), run_time=0.8)
        self.wait(0.2)
        arrow_qk = Arrow(q.get_center(), k.get_center(), color=YELLOW, stroke_width=3)
        score_label = Text("Q \u00b7 K\u1d40", font_size=30, color=YELLOW).move_to([-1.75, 1.5, 0])
        self.play(Create(arrow_qk), Write(score_label), run_time=0.5)
        self.wait(0.2)
        heatmap = Square(side_length=2.0, fill_opacity=0.4, fill_color=ORANGE, stroke_color=YELLOW, stroke_width=2)
        heatmap.move_to([0, -2.5, 0])
        heat_lbl = Text("Attention Weights", font_size=16, color=ORANGE).next_to(heatmap, DOWN, buff=0.2)
        self.play(Create(heatmap), Write(heat_lbl), run_time=0.4)
        self.wait(0.2)
        arrow_kv = Arrow(k.get_center(), v.get_center(), color=YELLOW, stroke_width=3)
        softmax_label = Text("Softmax", font_size=28, color=ORANGE).move_to([1.75, 1.5, 0])
        self.play(Create(arrow_kv), Write(softmax_label), run_time=0.5)
        self.wait(0.2)
        result_label = Text("Weighted Sum", font_size=24, color=GREEN).next_to(q, LEFT, buff=0.8)
        self.play(Write(result_label))
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(q), FadeOut(k), FadeOut(v), FadeOut(heatmap), FadeOut(heat_lbl),
                      FadeOut(arrow_qk), FadeOut(arrow_kv), FadeOut(score_label), FadeOut(softmax_label), FadeOut(result_label), run_time=__EXIT__)
"""
    return template.replace("__TITLE__", title).replace("__DURATION__", str(duration)).replace("__ENTRY__", str(entry_time)).replace("__EXIT__", str(exit_time))


def transformer_block_template(
    title: str = "Transformer Architecture",
    duration: float = 6.0,
    num_encoder_layers: int = 2,
    num_decoder_layers: int = 2,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class TransformerScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)
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
        self.play(Create(inputs), Create(outputs), run_time=0.4)
        self.play(Write(pos_enc_in), Write(pos_enc_out), run_time=0.2)
        enc_groups = []
        prev_bx = None
        for i in range(enc_count):
            g, bx = enc_block(2.0 - i * 2.2, f"Encoder Layer {i+1}")
            enc_groups.append(g)
            self.play(Create(g), run_time=0.4)
            if prev_bx is not None:
                arrow = Arrow(prev_bx.get_bottom(), bx.get_top(), stroke_width=2, color=BLUE_D)
                self.play(Create(arrow), run_time=0.2)
            prev_bx = bx
        dec_groups = []
        prev_dec_bx = None
        for i in range(dec_count):
            g, bx = dec_block(2.5 - i * 2.5, f"Decoder Layer {i+1}")
            dec_groups.append(g)
            self.play(Create(g), run_time=0.4)
            if prev_dec_bx is not None:
                arrow = Arrow(prev_dec_bx.get_bottom(), bx.get_top(), stroke_width=2, color=GREEN_D)
                self.play(Create(arrow), run_time=0.2)
            prev_dec_bx = bx
        cross_arrows = VGroup()
        for i in range(min(enc_count, dec_count)):
            enc_bottom = enc_groups[i][0].get_bottom()
            dec_center = dec_groups[i][0].get_center()
            arr = Arrow(enc_bottom, dec_center, stroke_width=1.5, color=YELLOW, stroke_opacity=0.4)
            cross_arrows.add(arr)
        if cross_arrows:
            self.play(Create(cross_arrows), run_time=0.4)
        linear = Rectangle(width=2.0, height=0.5, fill_opacity=0.2, fill_color=YELLOW, stroke_color=YELLOW_C, stroke_width=2)
        linear.move_to([0, -3.5, 0])
        linear_label = Text("Linear + Softmax", font_size=14, color=YELLOW_C).move_to(linear.get_center())
        self.play(Create(linear), Write(linear_label), run_time=0.4)
        output_probs = Text("Output\\nProbabilities", font_size=14, color=WHITE).next_to(linear, DOWN, buff=0.4)
        self.play(Write(output_probs))
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            all_mobs = [title_text, inputs, outputs, pos_enc_in, pos_enc_out, linear, linear_label, output_probs] + enc_groups + dec_groups
            self.play(*[FadeOut(m) for m in all_mobs if m], run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__ENC_LAYERS__", str(num_encoder_layers))
        .replace("__DEC_LAYERS__", str(num_decoder_layers))
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def convolution_template(
    kernel_size: int = 3,
    input_channels: int = 1,
    title: str = "Convolution Operation",
    duration: float = 6.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class ConvolutionScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)
        cell_size = 0.4
        grid_rows, grid_cols = 7, 7
        kernel_s = __KERNEL_SIZE__
        offset = (kernel_s - 1) // 2

        input_grid = VGroup()
        for r in range(grid_rows):
            for c in range(grid_cols):
                val = np.random.random()
                intensity = int(255 * val)
                color_rgb = "#{:02x}{:02x}{:02x}".format(intensity, intensity, intensity)
                sq = Square(side_length=cell_size, fill_opacity=0.7 + 0.3 * val,
                            fill_color=color_rgb, stroke_color=GRAY_D, stroke_width=0.5)
                sq.move_to([c * cell_size - (grid_cols-1) * cell_size / 2,
                            -(r * cell_size - (grid_rows-1) * cell_size / 2), 0])
                input_grid.add(sq)
        input_grid.move_to([-3.5, 0, 0])
        input_label = Text("Input\\nFeature Map", font_size=14, color=GRAY).next_to(input_grid, DOWN, buff=0.3)
        self.play(Create(input_grid), Write(input_label), run_time=0.6)

        kernel_overlay = VGroup()
        for r in range(kernel_s):
            for c in range(kernel_s):
                sq = Square(side_length=cell_size, fill_opacity=0.0, stroke_color=YELLOW, stroke_width=3)
                sq.move_to([c * cell_size - (kernel_s-1) * cell_size / 2,
                            -(r * cell_size - (kernel_s-1) * cell_size / 2), 0])
                kernel_overlay.add(sq)
        kernel_overlay.move_to([-3.5, 0, 0])
        self.play(Create(kernel_overlay), run_time=0.3)
        kernel_label = Text("Kernel (Filter)", font_size=14, color=YELLOW).next_to(kernel_overlay, DOWN, buff=0.3)
        self.play(Write(kernel_label))

        formula = Text("(Input * Kernel) + Bias", font_size=20, color=ORANGE).move_to([0, 2.5, 0])
        self.play(Write(formula), run_time=0.3)

        output_grid = VGroup()
        out_size = grid_rows - kernel_s + 1
        for r in range(out_size):
            for c in range(out_size):
                sq = Square(side_length=cell_size, fill_opacity=0.5, fill_color=PURPLE_C, stroke_color=PURPLE, stroke_width=1)
                sq.move_to([c * cell_size - (out_size-1) * cell_size / 2,
                            -(r * cell_size - (out_size-1) * cell_size / 2), 0])
                output_grid.add(sq)
        output_grid.move_to([3.5, 0, 0])
        output_label = Text("Output\\nFeature Map", font_size=14, color=PURPLE).next_to(output_grid, DOWN, buff=0.3)
        self.play(Create(output_grid), Write(output_label), run_time=0.6)

        arrow_conv = Arrow(input_grid.get_center(), output_grid.get_center(), color=YELLOW, stroke_width=2)
        self.play(Create(arrow_conv), run_time=0.3)

        slide_tracker = kernel_overlay.copy()
        slide_tracker.set_stroke(RED, width=4)
        total_positions = grid_rows - kernel_s + 1
        start_pos = input_grid.get_center()
        step_x = cell_size
        step_y = cell_size
        positions = []
        for r in range(total_positions):
            for c in range(total_positions):
                pos = start_pos + np.array([c * step_x, -r * step_y, 0])
                positions.append(pos)

        if positions:
            self.play(slide_tracker.animate.move_to(positions[min(3, len(positions)-1)]), run_time=0.8)

        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(input_grid), FadeOut(kernel_overlay),
                      FadeOut(output_grid), FadeOut(arrow_conv), FadeOut(formula),
                      FadeOut(input_label), FadeOut(kernel_label), FadeOut(output_label),
                      slide_tracker.animate.set_opacity(0), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__KERNEL_SIZE__", str(kernel_size))
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def recurrent_template(
    num_steps: int = 4,
    title: str = "Recurrent Neural Network",
    duration: float = 6.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class RecurrentScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)

        n_steps = __NUM_STEPS__
        inputs = VGroup()
        hidden_states = VGroup()
        outputs = VGroup()
        for i in range(n_steps):
            inp = Square(side_length=0.5, fill_opacity=0.6, fill_color=BLUE_C, stroke_color=BLUE_D, stroke_width=2)
            inp.move_to([i * 1.8 - (n_steps-1) * 0.9, 1.5, 0])
            inp_lbl = Text(f"x[{i}]", font_size=12, color=WHITE).move_to(inp.get_center())
            inp_group = VGroup(inp, inp_lbl)
            inputs.add(inp_group)

            out = Square(side_length=0.5, fill_opacity=0.6, fill_color=GREEN_C, stroke_color=GREEN_D, stroke_width=2)
            out.move_to([i * 1.8 - (n_steps-1) * 0.9, -1.5, 0])
            out_lbl = Text(f"h[{i}]", font_size=12, color=WHITE).move_to(out.get_center())
            out_group = VGroup(out, out_lbl)
            outputs.add(out_group)

            hidden = RoundedRectangle(width=0.8, height=0.6, corner_radius=0.1,
                                      fill_opacity=0.7, fill_color=PURPLE, stroke_color=PURPLE_C, stroke_width=2)
            hidden.move_to([i * 1.8 - (n_steps-1) * 0.9, 0, 0])
            hidden_lbl = Text(f"A[{i}]", font_size=12, color=WHITE).move_to(hidden.get_center())
            hidden_group = VGroup(hidden, hidden_lbl)
            hidden_states.add(hidden_group)

        self.play(Create(inputs), run_time=0.5)
        self.play(Create(hidden_states), run_time=0.5)
        input_arrows = VGroup()
        for i in range(n_steps):
            arrow = Arrow(inputs[i].get_top(), hidden_states[i].get_bottom(), color=BLUE_C, stroke_width=2)
            input_arrows.add(arrow)
        self.play(Create(input_arrows), run_time=0.4)

        time_arrows = VGroup()
        for i in range(n_steps - 1):
            arrow = Arrow(hidden_states[i].get_right(), hidden_states[i+1].get_left(), color=PURPLE_C, stroke_width=3)
            time_arrows.add(arrow)
        self.play(Create(time_arrows), run_time=0.4)
        self.wait(0.2)

        self.play(Create(outputs), run_time=0.5)
        output_arrows = VGroup()
        for i in range(n_steps):
            arrow = Arrow(hidden_states[i].get_top(), outputs[i].get_bottom(), color=GREEN_C, stroke_width=2)
            output_arrows.add(arrow)
        self.play(Create(output_arrows), run_time=0.4)

        loop_label = Text("Hidden state propagates through time steps", font_size=18, color=PURPLE_C).to_edge(DOWN)
        self.play(Write(loop_label))

        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(inputs), FadeOut(hidden_states), FadeOut(outputs),
                      FadeOut(input_arrows), FadeOut(time_arrows), FadeOut(output_arrows), FadeOut(loop_label),
                      run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__NUM_STEPS__", str(num_steps))
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def algorithm_flow_template(
    steps: list[str] = None,
    title: str = "Algorithm Flow",
    duration: float = 6.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    if steps is None:
        steps = ["Input", "Process", "Output"]
    template = INJECT_IMPORTS + """
class AlgorithmFlowScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)
        steps = __STEPS__
        prev_box = None
        for i, step_name in enumerate(steps):
            box = RoundedRectangle(width=2.0, height=0.7, corner_radius=0.1, fill_opacity=0.2, fill_color=BLUE, stroke_color=BLUE_C, stroke_width=2)
            box.move_to([0, 2.0 - i * 1.5, 0])
            label = Text(step_name, font_size=18, color=WHITE).move_to(box.get_center())
            group = VGroup(box, label)
            self.play(Create(group), run_time=0.3)
            if prev_box is not None:
                arrow = Arrow(prev_box.get_bottom(), box.get_top(), stroke_width=2, color=YELLOW)
                self.play(Create(arrow), run_time=0.2)
            prev_box = box
        glow = box.copy().set_stroke(YELLOW, width=6).set_fill(opacity=0)
        self.play(Create(glow), run_time=0.2)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(group), FadeOut(glow), *[FadeOut(a) for a in self.mobjects if isinstance(a, Arrow)], run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__STEPS__", str(steps))
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def bar_chart_template(
    labels: list[str] = None,
    values: list[float] = None,
    title: str = "Performance Comparison",
    duration: float = 6.0,
    bar_color: str = "#00D2FF",
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    if labels is None:
        labels = ["A", "B", "C", "D"]
    if values is None:
        values = [3.0, 5.0, 2.0, 7.0]
    template = INJECT_IMPORTS + """
class BarChartScene(Scene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)
        labels = __LABELS__
        values = __VALUES__
        max_val = max(values) if values else 1
        bar_width = 0.6
        total_width = len(labels) * (bar_width + 0.3)
        start_x = -total_width / 2 + bar_width / 2
        bars_created = []
        for i, (label, val) in enumerate(zip(labels, values)):
            height = (val / max_val) * 3.0
            bar = Rectangle(width=bar_width, height=0.01, fill_opacity=0.8, fill_color="__BAR_COLOR__", stroke_width=1)
            bar.move_to([start_x + i * (bar_width + 0.3), -1.5 + 0.005, 0])
            self.play(
                bar.animate.set_height(height).move_to([start_x + i * (bar_width + 0.3), -1.5 + height / 2, 0]),
                run_time=0.4
            )
            lbl = Text(str(label), font_size=16, color=GRAY).next_to(bar, DOWN, buff=0.15)
            val_lbl = Text(f"{val:.1f}", font_size=14, color=WHITE).next_to(bar, UP, buff=0.1)
            self.play(Write(lbl), Write(val_lbl), run_time=0.15)
            bars_created.extend([bar, lbl, val_lbl])
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), *[FadeOut(m) for m in bars_created], run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__LABELS__", str(labels))
        .replace("__VALUES__", str(values))
        .replace("__BAR_COLOR__", bar_color)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def gradient_descent_template(
    title: str = "Gradient Descent",
    duration: float = 8.0,
    learning_rate: float = 0.25,
    num_steps: int = 6,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class GradientDescentScene(ThreeDScene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title_text)
        self.play(Write(title_text), run_time=__ENTRY__)

        self.set_camera_orientation(phi=65 * DEGREES, theta=-50 * DEGREES, zoom=0.9)

        axes = ThreeDAxes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            z_range=[-1, 4, 1],
            x_length=6,
            y_length=6,
            z_length=4,
        )
        x_label = Text("x", font_size=16, color=GRAY).move_to(axes.x_axis.get_end() + RIGHT * 0.3)
        y_label = Text("y", font_size=16, color=GRAY).move_to(axes.y_axis.get_end() + UP * 0.3)
        z_label = Text("Loss", font_size=16, color=GRAY_D).move_to(axes.z_axis.get_end() + OUT * 0.3)

        def loss_surface(u, v):
            return np.array([u, v, 0.4 * (u**2 + v**2)])

        surface = Surface(
            loss_surface,
            u_range=[-2.5, 2.5],
            v_range=[-2.5, 2.5],
            resolution=(20, 20),
            fill_opacity=0.75,
            fill_color=BLUE_B,
            stroke_width=0.3,
            stroke_color=BLUE_D,
        )
        self.play(Create(axes), Write(x_label), Write(y_label), Write(z_label), run_time=0.5)
        self.play(Create(surface), run_time=1.0)

        grad_path = __GRAD_PATH__
        points_3d = [np.array([p[0], p[1], 0.4 * (p[0]**2 + p[1]**2) + 0.05]) for p in grad_path]

        path_mobject = VMobject(stroke_color=YELLOW, stroke_width=5)
        path_mobject.set_points_smoothly(points_3d)
        self.play(Create(path_mobject), run_time=0.8)

        sphere = Sphere(radius=0.1, color=RED, fill_opacity=1.0)
        sphere.move_to(points_3d[0])
        self.add(sphere)

        step_label = Text("Step 0", font_size=20, color=RED).to_corner(DR)
        self.add_fixed_in_frame_mobjects(step_label)
        self.play(Write(step_label))

        for i, target in enumerate(points_3d[1:]):
            new_label = Text(f"Step {i + 1}", font_size=20, color=RED).to_corner(DR)
            self.add_fixed_in_frame_mobjects(new_label)
            self.play(
                sphere.animate.move_to(target),
                Transform(step_label, new_label),
                run_time=0.4,
            )

        self.begin_ambient_camera_rotation(rate=0.10)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(axes), FadeOut(surface),
                      FadeOut(path_mobject), FadeOut(sphere), FadeOut(step_label),
                      run_time=__EXIT__)
"""
    path = _compute_grad_descent_path(learning_rate=learning_rate, steps=num_steps)
    return (
        template
        .replace("__TITLE__", title)
        .replace("__GRAD_PATH__", json.dumps(path))
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def text_reveal_template(
    lines: list[str] = None,
    title: str = "Key Insight",
    duration: float = 6.0,
    line_color: str = "#00CCCC",
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    if lines is None:
        lines = ["Key Insight", "Emerges from", "the data"]
    template = INJECT_IMPORTS + """
class TextRevealScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        title_text = Text("__TITLE__", font_size=36, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)
        lines = __LINES__
        text_group = VGroup()
        for i, line in enumerate(lines):
            t = Text(line, font_size=28 - min(len(line) // 10, 3) * 2, color="__LINE_COLOR__")
            t.move_to([0, 1.0 - i * 0.8, 0])
            self.play(Write(t), run_time=0.4)
            text_group.add(t)
        self.wait(0.3)
        glow = SurroundingRectangle(text_group, buff=0.2, color="__LINE_COLOR__", stroke_width=1, stroke_opacity=0.5)
        self.play(Create(glow), run_time=0.3)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(title_text), FadeOut(text_group), FadeOut(glow), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__LINES__", str(lines))
        .replace("__LINE_COLOR__", line_color)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def architecture_diagram_template(
    title: str = "System Architecture",
    duration: float = 8.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
    components: list[str] = None,
) -> str:
    """Template for system architecture / pipeline diagrams."""
    if components is None:
        components = ["Input", "Process", "Output"]
    comps_json = json.dumps(components)
    template = INJECT_IMPORTS + """
class ArchitectureDiagramScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        components = json.loads('__COMPS__')
        title_text = Text("__TITLE__", font_size=32, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        boxes = VGroup()
        arrows = VGroup()
        n = len(components)
        total_w = n * 2.5 - 0.5
        start_x = -total_w / 2
        for i, name in enumerate(components):
            box = Rectangle(height=1.2, width=2.0, color=HexColor("#00CCCC"), fill_opacity=0.15)
            box.move_to([start_x + i * 2.5, 0, 0])
            label = Text(name, font_size=20, color=WHITE)
            label.move_to(box.get_center())
            boxes.add(VGroup(box, label))
            if i < n - 1:
                arrow = Arrow(
                    box.get_right(), [start_x + (i + 1) * 2.5 - 1.0, 0, 0],
                    color=HexColor("#FF6B35"), stroke_width=3
                )
                arrows.add(arrow)
        self.play(LaggedStart(*[FadeIn(b, shift=UP * 0.3) for b in boxes], lag_ratio=0.15), run_time=1.5)
        self.wait(0.3)
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.15), run_time=1.0)
        self.wait(max(0, __DURATION__ - 3.5 - __EXIT__))
        self.play(FadeOut(VGroup(boxes, arrows, title_text)), run_time=__EXIT__)
""".replace("__COMPS__", comps_json).replace("__TITLE__", title)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def data_flow_diagram_template(
    title: str = "Data Flow",
    duration: float = 8.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
    nodes: list[str] = None,
) -> str:
    """Template for data flow / pipeline diagrams."""
    if nodes is None:
        nodes = ["Source", "Transform", "Store", "Serve"]
    nodes_json = json.dumps(nodes)
    template = INJECT_IMPORTS + """
class DataFlowScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        nodes = json.loads('__NODES__')
        title_text = Text("__TITLE__", font_size=32, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        circles = VGroup()
        labels = VGroup()
        n = len(nodes)
        for i, name in enumerate(nodes):
            angle = -PI/2 + i * 2*PI / n
            pos = [2.5 * np.cos(angle), 2.5 * np.sin(angle), 0]
            circle = Circle(radius=0.7, color=HexColor("#00CCCC"), fill_opacity=0.15)
            circle.move_to(pos)
            label = Text(name, font_size=16, color=WHITE)
            label.move_to(pos)
            circles.add(circle)
            labels.add(label)
            if i > 0:
                prev_pos = [2.5 * np.cos(-PI/2 + (i-1) * 2*PI / n), 2.5 * np.sin(-PI/2 + (i-1) * 2*PI / n), 0]
                arrow = Arrow(prev_pos, pos, color=HexColor("#FF6B35"), stroke_width=2)
                self.play(GrowArrow(arrow), run_time=0.3)
            self.play(FadeIn(circle), Write(label), run_time=0.3)
        self.wait(max(0, __DURATION__ - 2.5 - __EXIT__))
        self.play(FadeOut(VGroup(circles, labels, title_text)), run_time=__EXIT__)
""".replace("__NODES__", nodes_json).replace("__TITLE__", title)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def timeline_template(
    title: str = "Timeline",
    duration: float = 8.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
    milestones: list[str] = None,
) -> str:
    """Template for chronological timeline / evolution."""
    if milestones is None:
        milestones = ["2018", "2020", "2022", "2024"]
    ms_json = json.dumps(milestones)
    template = INJECT_IMPORTS + """
class TimelineScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        milestones = json.loads('__MS__')
        title_text = Text("__TITLE__", font_size=32, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        line = Line([-5, 0, 0], [5, 0, 0], color=HexColor("#00CCCC"), stroke_width=3)
        self.play(Create(line), run_time=0.5)
        n = len(milestones)
        dots = VGroup()
        labels = VGroup()
        for i, ms in enumerate(milestones):
            x = -4.5 + i * 9.0 / (n - 1) if n > 1 else 0
            dot = Dot([x, 0, 0], color=HexColor("#FF6B35"), radius=0.1)
            label = Text(ms, font_size=18, color=WHITE).next_to(dot, DOWN if i % 2 == 0 else UP, buff=0.3)
            dots.add(dot)
            labels.add(label)
            self.play(FadeIn(dot), Write(label), run_time=0.3)
        self.wait(max(0, __DURATION__ - 3.0 - __EXIT__))
        self.play(FadeOut(VGroup(line, dots, labels, title_text)), run_time=__EXIT__)
""".replace("__MS__", ms_json).replace("__TITLE__", title)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def comparison_chart_template(
    title: str = "Comparison",
    duration: float = 8.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
    left_label: str = "Before",
    right_label: str = "After",
    left_items: list[str] = None,
    right_items: list[str] = None,
) -> str:
    """Template for side-by-side comparison."""
    if left_items is None:
        left_items = ["Slow", "Expensive", "Complex"]
    if right_items is None:
        right_items = ["Fast", "Cheap", "Simple"]
    left_json = json.dumps(left_items)
    right_json = json.dumps(right_items)
    template = INJECT_IMPORTS + """
class ComparisonScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        left_items = json.loads('__LEFT__')
        right_items = json.loads('__RIGHT__')
        title_text = Text("__TITLE__", font_size=32, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        div = Line([0, -3, 0], [0, 3, 0], color=HexColor("#00CCCC"), stroke_width=1, opacity=0.5)
        self.play(Create(div), run_time=0.3)
        left_header = Text("__LEFT_LABEL__", font_size=24, color=HexColor("#FF6B35")).move_to([-3, 2.5, 0])
        right_header = Text("__RIGHT_LABEL__", font_size=24, color=HexColor("#00CCCC")).move_to([3, 2.5, 0])
        self.play(Write(left_header), Write(right_header), run_time=0.5)
        left_group = VGroup()
        right_group = VGroup()
        for i, item in enumerate(left_items):
            t = Text(f"• {item}", font_size=18, color=WHITE)
            t.move_to([-3, 1.5 - i * 0.8, 0])
            left_group.add(t)
        for i, item in enumerate(right_items):
            t = Text(f"• {item}", font_size=18, color=WHITE)
            t.move_to([3, 1.5 - i * 0.8, 0])
            right_group.add(t)
        self.play(LaggedStart(*[Write(t) for t in left_group], lag_ratio=0.15), run_time=1.0)
        self.play(LaggedStart(*[Write(t) for t in right_group], lag_ratio=0.15), run_time=1.0)
        self.wait(max(0, __DURATION__ - 4.0 - __EXIT__))
        self.play(FadeOut(VGroup(title_text, div, left_header, right_header, left_group, right_group)), run_time=__EXIT__)
""".replace("__LEFT__", left_json).replace("__RIGHT__", right_json).replace("__TITLE__", title).replace("__LEFT_LABEL__", left_label).replace("__RIGHT_LABEL__", right_label)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def process_flow_template(
    title: str = "Process",
    duration: float = 8.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
    steps: list[str] = None,
) -> str:
    """Template for vertical step-by-step process."""
    if steps is None:
        steps = ["Step 1", "Step 2", "Step 3", "Step 4"]
    steps_json = json.dumps(steps)
    template = INJECT_IMPORTS + """
class ProcessFlowScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        steps = json.loads('__STEPS__')
        title_text = Text("__TITLE__", font_size=32, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        n = len(steps)
        start_y = 2.5
        step_group = VGroup()
        for i, step in enumerate(steps):
            y = start_y - i * 1.5
            circle = Circle(radius=0.35, color=HexColor("#00CCCC"), fill_opacity=0.2)
            circle.move_to([-3, y, 0])
            num = Text(str(i+1), font_size=16, color=HexColor("#00CCCC"))
            num.move_to(circle.get_center())
            label = Text(step, font_size=20, color=WHITE)
            label.next_to(circle, RIGHT, buff=0.5)
            step_group.add(VGroup(circle, num, label))
            if i < n - 1:
                connector = Line([-3, y - 0.35, 0], [-3, y - 1.5 + 0.35, 0], color=HexColor("#FF6B35"), stroke_width=2)
                step_group.add(connector)
        self.play(LaggedStart(*[FadeIn(s, shift=RIGHT * 0.3) for s in step_group], lag_ratio=0.2), run_time=2.0)
        self.wait(max(0, __DURATION__ - 3.5 - __EXIT__))
        self.play(FadeOut(VGroup(step_group, title_text)), run_time=__EXIT__)
""".replace("__STEPS__", steps_json).replace("__TITLE__", title)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def concept_map_template(
    title: str = "Concept Map",
    duration: float = 10.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
    concepts: list[str] = None,
) -> str:
    """Template for concept relationship map."""
    if concepts is None:
        concepts = ["AI", "ML", "NLP", "CV", "Robotics"]
    concepts_json = json.dumps(concepts)
    template = INJECT_IMPORTS + """
class ConceptMapScene(Scene):
    def construct(self):
        self.camera.background_color = HexColor("#1e1e1e")
        concepts = json.loads('__CONCEPTS__')
        title_text = Text("__TITLE__", font_size=32, color=HexColor("#00CCCC")).to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        n = len(concepts)
        center = [0, 0, 0] if n > 1 else [0, 0, 0]
        nodes = VGroup()
        for i, concept in enumerate(concepts):
            angle = -PI/2 + i * 2*PI / n
            r = 2.5
            pos = [r * np.cos(angle), r * np.sin(angle), 0]
            box = RoundedRectangle(corner_radius=0.2, height=0.7, width=1.8, color=HexColor("#00CCCC"), fill_opacity=0.15)
            box.move_to(pos)
            label = Text(concept, font_size=16, color=WHITE)
            label.move_to(pos)
            nodes.add(VGroup(box, label))
            if i > 0:
                prev_pos = [r * np.cos(-PI/2 + (i-1) * 2*PI / n), r * np.sin(-PI/2 + (i-1) * 2*PI / n), 0]
                line = Line(prev_pos, pos, color=HexColor("#FF6B35"), stroke_width=1.5, opacity=0.6)
                self.play(Create(line), run_time=0.2)
            self.play(FadeIn(box), Write(label), run_time=0.3)
        if n > 2:
            for i in range(n):
                for j in range(i+2, n):
                    if n <= 4 or (j - i) % n != 1:
                        angle_i = -PI/2 + i * 2*PI / n
                        angle_j = -PI/2 + j * 2*PI / n
                        pos_i = [r * np.cos(angle_i), r * np.sin(angle_i), 0]
                        pos_j = [r * np.cos(angle_j), r * np.sin(angle_j), 0]
                        line = Line(pos_i, pos_j, color=HexColor("#00CCCC"), stroke_width=0.5, opacity=0.2)
                        self.add(line)
                        self.wait(0.05)
        self.wait(max(0, __DURATION__ - 3.5 - __EXIT__))
        self.play(FadeOut(VGroup(nodes, title_text)), run_time=__EXIT__)
""".replace("__CONCEPTS__", concepts_json).replace("__TITLE__", title)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


CUSTOM_TEMPLATE_REGISTRY: dict[str, callable] = {}


def register_custom_template(name: str, generator_fn: callable) -> None:
    """Register a new template function that takes (title, duration, **kwargs) and returns Manim code."""
    CUSTOM_TEMPLATE_REGISTRY[name] = generator_fn
