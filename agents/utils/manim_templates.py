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
        q = make_matrix(8, 4, "Query", "#FF6B6B"
        k = make_matrix(8, 4, "Key", "#4ECDC4"
        v = make_matrix(8, 4, "Value", "#A29BFE"
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
        self.camera.background_color = "#1e1e1e"
        title_text = Text("__TITLE__", font_size=36, color="#00CCCC").to_edge(UP)
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
        self.camera.background_color = "#1e1e1e"
        components = json.loads('__COMPS__')
        title_text = Text("__TITLE__", font_size=32, color="#00CCCC").to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        boxes = VGroup()
        arrows = VGroup()
        n = len(components)
        total_w = n * 2.5 - 0.5
        start_x = -total_w / 2
        for i, name in enumerate(components):
            box = Rectangle(height=1.2, width=2.0, color="#00CCCC", fill_opacity=0.15)
            box.move_to([start_x + i * 2.5, 0, 0])
            label = Text(name, font_size=20, color=WHITE)
            label.move_to(box.get_center())
            boxes.add(VGroup(box, label))
            if i < n - 1:
                arrow = Arrow(
                    box.get_right(), [start_x + (i + 1) * 2.5 - 1.0, 0, 0],
                    color="#FF6B35", stroke_width=3
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
        self.camera.background_color = "#1e1e1e"
        nodes = json.loads('__NODES__')
        title_text = Text("__TITLE__", font_size=32, color="#00CCCC").to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        circles = VGroup()
        labels = VGroup()
        n = len(nodes)
        for i, name in enumerate(nodes):
            angle = -PI/2 + i * 2*PI / n
            pos = [2.5 * np.cos(angle), 2.5 * np.sin(angle), 0]
            circle = Circle(radius=0.7, color="#00CCCC", fill_opacity=0.15)
            circle.move_to(pos)
            label = Text(name, font_size=16, color=WHITE)
            label.move_to(pos)
            circles.add(circle)
            labels.add(label)
            if i > 0:
                prev_pos = [2.5 * np.cos(-PI/2 + (i-1) * 2*PI / n), 2.5 * np.sin(-PI/2 + (i-1) * 2*PI / n), 0]
                arrow = Arrow(prev_pos, pos, color="#FF6B35", stroke_width=2)
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
        self.camera.background_color = "#1e1e1e"
        milestones = json.loads('__MS__')
        title_text = Text("__TITLE__", font_size=32, color="#00CCCC").to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        line = Line([-5, 0, 0], [5, 0, 0], color="#00CCCC", stroke_width=3)
        self.play(Create(line), run_time=0.5)
        n = len(milestones)
        dots = VGroup()
        labels = VGroup()
        for i, ms in enumerate(milestones):
            x = -4.5 + i * 9.0 / (n - 1) if n > 1 else 0
            dot = Dot([x, 0, 0], color="#FF6B35", radius=0.1)
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
        self.camera.background_color = "#1e1e1e"
        left_items = json.loads('__LEFT__')
        right_items = json.loads('__RIGHT__')
        title_text = Text("__TITLE__", font_size=32, color="#00CCCC").to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        div = Line([0, -3, 0], [0, 3, 0], color="#00CCCC", stroke_width=1, opacity=0.5)
        self.play(Create(div), run_time=0.3)
        left_header = Text("__LEFT_LABEL__", font_size=24, color="#FF6B35").move_to([-3, 2.5, 0])
        right_header = Text("__RIGHT_LABEL__", font_size=24, color="#00CCCC").move_to([3, 2.5, 0])
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
        self.camera.background_color = "#1e1e1e"
        steps = json.loads('__STEPS__')
        title_text = Text("__TITLE__", font_size=32, color="#00CCCC").to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        n = len(steps)
        start_y = 2.5
        step_group = VGroup()
        for i, step in enumerate(steps):
            y = start_y - i * 1.5
            circle = Circle(radius=0.35, color="#00CCCC", fill_opacity=0.2)
            circle.move_to([-3, y, 0])
            num = Text(str(i+1), font_size=16, color="#00CCCC")
            num.move_to(circle.get_center())
            label = Text(step, font_size=20, color=WHITE)
            label.next_to(circle, RIGHT, buff=0.5)
            step_group.add(VGroup(circle, num, label))
            if i < n - 1:
                connector = Line([-3, y - 0.35, 0], [-3, y - 1.5 + 0.35, 0], color="#FF6B35", stroke_width=2)
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
        self.camera.background_color = "#1e1e1e"
        concepts = json.loads('__CONCEPTS__')
        title_text = Text("__TITLE__", font_size=32, color="#00CCCC").to_edge(UP)
        self.play(Write(title_text), run_time=0.5)
        n = len(concepts)
        center = [0, 0, 0] if n > 1 else [0, 0, 0]
        nodes = VGroup()
        for i, concept in enumerate(concepts):
            angle = -PI/2 + i * 2*PI / n
            r = 2.5
            pos = [r * np.cos(angle), r * np.sin(angle), 0]
            box = RoundedRectangle(corner_radius=0.2, height=0.7, width=1.8, color="#00CCCC", fill_opacity=0.15)
            box.move_to(pos)
            label = Text(concept, font_size=16, color=WHITE)
            label.move_to(pos)
            nodes.add(VGroup(box, label))
            if i > 0:
                prev_pos = [r * np.cos(-PI/2 + (i-1) * 2*PI / n), r * np.sin(-PI/2 + (i-1) * 2*PI / n), 0]
                line = Line(prev_pos, pos, color="#FF6B35", stroke_width=1.5, opacity=0.6)
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
                        line = Line(pos_i, pos_j, color="#00CCCC", stroke_width=0.5, opacity=0.2)
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


def intro_template(
    channel_name: str = "Vyom Ai Cloud",
    tagline: str = "AI Education for Everyone",
    duration: float = 4.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class IntroScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        bg = Rectangle(width=16, height=9, fill_opacity=0, stroke_width=0)
        accent_bar = Rectangle(width=0.08, height=1.2, fill_opacity=1, fill_color="#00CCCC", stroke_width=0)
        accent_bar.move_to([-1.8, 0, 0])
        self.play(FadeIn(accent_bar, scale=0.5), run_time=0.5)
        name_text = Text("__CHANNEL__", font_size=48, color="#00CCCC", weight=BOLD)
        name_text.next_to(accent_bar, RIGHT, buff=0.4)
        self.play(Write(name_text), run_time=0.6)
        tagline_text = Text("__TAGLINE__", font_size=22, color=GRAY)
        tagline_text.next_to(name_text, DOWN, buff=0.2, aligned_edge=LEFT)
        self.play(FadeIn(tagline_text, shift=UP * 0.1), run_time=0.4)
        glow = Rectangle(width=10, height=0.002, fill_opacity=0.3, fill_color="#00CCCC", stroke_width=0)
        glow.next_to(tagline_text, DOWN, buff=0.3)
        self.play(FadeIn(glow), run_time=0.3)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(accent_bar, name_text, tagline_text, glow)), run_time=__EXIT__)
""".replace("__CHANNEL__", channel_name).replace("__TAGLINE__", tagline)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def outro_template(
    channel_name: str = "Vyom Ai Cloud",
    cta_text: str = "Subscribe for more AI content",
    url: str = "vyomcloud.com",
    duration: float = 5.0,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class OutroScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        cta = Text("__CTA__", font_size=40, color=WHITE, weight=BOLD)
        cta.move_to([0, 0.5, 0])
        self.play(Write(cta), run_time=0.6)
        btn = RoundedRectangle(width=3.5, height=0.6, corner_radius=0.1, fill_opacity=0.2, fill_color="#00CCCC", stroke_color="#00CCCC", stroke_width=2)
        btn.next_to(cta, DOWN, buff=0.5)
        btn_label = Text("SUBSCRIBE", font_size=20, color="#00CCCC", weight=BOLD)
        btn_label.move_to(btn.get_center())
        self.play(FadeIn(btn, scale=0.8), Write(btn_label), run_time=0.5)
        pulse = btn.copy().set_stroke("#00CCCC", width=4).set_fill(opacity=0)
        self.play(pulse.animate.scale(1.08).set_opacity(0), run_time=0.6)
        url_text = Text("__URL__", font_size=16, color=GRAY)
        url_text.next_to(btn, DOWN, buff=0.3)
        self.play(FadeIn(url_text), run_time=0.3)
        channel = Text("__CHANNEL__", font_size=18, color="#00CCCC").to_corner(DR)
        self.play(FadeIn(channel), run_time=0.3)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(cta, btn, btn_label, url_text, channel)), run_time=__EXIT__)
""".replace("__CHANNEL__", channel_name).replace("__CTA__", cta_text).replace("__URL__", url)
    return (
        template
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def loss_landscape_template(
    title: str = "Loss Landscape",
    duration: float = 10.0,
    surface_type: str = "saddle",
    num_steps: int = 8,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    if surface_type == "saddle":
        def_surface = "def f(u, v): return np.array([u, v, 0.15 * (u**2 - v**2)])"
        contour_desc = "saddle point at center, gradients flow down the sides"
    elif surface_type == "plateau":
        def_surface = "def f(u, v): return np.array([u, v, 0.02 * (u**2 + v**2) + 0.5 / (1 + np.exp(-6 * (u**2 + v**2 - 2)))])"
        contour_desc = "flat plateau with steep ravines on the edges"
    else:
        def_surface = "def f(u, v): return np.array([u, v, 0.3 * (np.sin(u) * np.sin(v) + 0.3 * (u**2 + v**2) * 0.1)])"
        contour_desc = "multiple local minima with sinusoidal ridges"
    template = INJECT_IMPORTS + f"""
class LossLandscapeScene(ThreeDScene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title_text)
        self.play(Write(title_text), run_time=__ENTRY__)

        self.set_camera_orientation(phi=70 * DEGREES, theta=-40 * DEGREES, zoom=0.85)
        axes = ThreeDAxes(
            x_range=[-3, 3, 1], y_range=[-3, 3, 1], z_range=[-2, 3, 1],
            x_length=6, y_length=6, z_length=4,
        )
        x_label = Text("w₁", font_size=16, color=GRAY).move_to(axes.x_axis.get_end() + RIGHT * 0.3)
        y_label = Text("w₂", font_size=16, color=GRAY).move_to(axes.y_axis.get_end() + UP * 0.3)
        z_label = Text("Loss", font_size=16, color="#00CCCC").move_to(axes.z_axis.get_end() + OUT * 0.3)

        {def_surface}
        surface = Surface(
            f, u_range=[-2.5, 2.5], v_range=[-2.5, 2.5],
            resolution=(24, 24), fill_opacity=0.7, fill_color=BLUE_B,
            stroke_width=0.3, stroke_color=BLUE_D,
        )
        self.play(Create(axes), Write(x_label), Write(y_label), Write(z_label), run_time=0.5)
        self.play(Create(surface), run_time=1.2)

        contour_label = Text("{contour_desc}", font_size=16, color=GRAY_C).to_corner(DL)
        self.add_fixed_in_frame_mobjects(contour_label)
        self.play(Write(contour_label), run_time=0.3)

        np.random.seed(42)
        flat_region = [[-2 + 4 * np.random.random(), -2 + 4 * np.random.random()] for _ in range(__STEPS__)]
        grad_path = _compute_grad_descent_path(lr=0.2, steps=__STEPS__)
        points_3d = []
        for p in grad_path:
            f_out = f(p[0], p[1])
            z = f_out[2] + 0.05
            points_3d.append(np.array([p[0], p[1], z]))

        path_mob = VMobject(stroke_color="#FF6B35", stroke_width=5)
        path_mob.set_points_smoothly(points_3d)
        self.play(Create(path_mob), run_time=1.0)

        sphere = Sphere(radius=0.1, color="#FF6B35", fill_opacity=1.0)
        sphere.move_to(points_3d[0])
        self.add(sphere)

        step_label = Text("Init", font_size=20, color="#FF6B35").to_corner(DR)
        self.add_fixed_in_frame_mobjects(step_label)
        self.play(Write(step_label))

        for i, target in enumerate(points_3d[1:]):
            new_label = Text(f"Step {{i + 1}}", font_size=20, color="#FF6B35").to_corner(DR)
            self.add_fixed_in_frame_mobjects(new_label)
            self.play(sphere.animate.move_to(target), Transform(step_label, new_label), run_time=0.35)

        self.begin_ambient_camera_rotation(rate=0.08)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(title_text, axes, surface, contour_label, path_mob, sphere, step_label)), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
        .replace("__STEPS__", str(num_steps))
    )


def embedding_space_template(
    title: str = "Embedding Space",
    duration: float = 10.0,
    dimensions: int = 2,
    num_points: int = 8,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class EmbeddingSpaceScene(ThreeDScene):
    def construct(self):
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title_text)
        self.play(Write(title_text), run_time=__ENTRY__)

        axes = ThreeDAxes(
            x_range=[-4, 4, 1], y_range=[-4, 4, 1], z_range=[-4, 4, 1],
            x_length=7, y_length=7, z_length=5,
        )
        x_label = MathTex("x_1", font_size=24, color=GRAY).move_to(axes.x_axis.get_end() + RIGHT * 0.3)
        y_label = MathTex("x_2", font_size=24, color=GRAY).move_to(axes.y_axis.get_end() + UP * 0.3)
        z_label = MathTex("x_3", font_size=24, color=GRAY).move_to(axes.z_axis.get_end() + OUT * 0.3)
        self.play(Create(axes), Write(x_label), Write(y_label), Write(z_label), run_time=0.6)

        np.random.seed(42)
        vectors = []
        labels = ["king", "queen", "man", "woman", "apple", "orange", "car", "dog"]
        for _ in range(min(8, __POINTS__)):
            v = np.random.uniform(-3, 3, 3)
            v = v / np.linalg.norm(v) * np.random.uniform(1, 3)
            vectors.append(v)

        dots = []
        dot_labels = []
        for i, vec in enumerate(vectors):
            dot = Dot3D(point=vec, radius=0.08, color="#00CCCC")
            self.play(Create(dot), run_time=0.15)
            dots.append(dot)
            if i < len(labels):
                lbl = Text(labels[i].split("_")[0], font_size=12, color=GRAY_C).move_to(vec + [0, -0.3, 0])
                self.add_fixed_in_frame_mobjects(lbl)
                dot_labels.append(lbl)
                self.play(Write(lbl), run_time=0.1)

        king_vec = vectors[0] if len(vectors) > 0 else np.array([2, 1, 1])
        queen_vec = vectors[1] if len(vectors) > 1 else np.array([2, -1, 0])
        woman_vec = vectors[3] if len(vectors) > 3 else np.array([-1, 1, 1])
        man_vec = vectors[2] if len(vectors) > 2 else np.array([-1, -1, 0])

        arrow_king_queen = Arrow3D(king_vec, queen_vec, color="#FF6B35", thickness=0.02)
        arrow_man_woman = Arrow3D(man_vec, woman_vec, color="#FF6B35", thickness=0.02)
        self.play(Create(arrow_king_queen), Create(arrow_man_woman), run_time=0.5)

        gp_label = MathTex("\\vec{g}_{gender}", font_size=22, color="#FF6B35")
        gp_label.move_to((king_vec + queen_vec) / 2 + [0.5, 0.5, 0])
        self.add_fixed_in_frame_mobjects(gp_label)
        self.play(Write(gp_label), run_time=0.3)

        self.set_camera_orientation(phi=75 * DEGREES, theta=-30 * DEGREES)
        self.begin_ambient_camera_rotation(rate=0.06)
        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(title_text, axes, *dots, *dot_labels, arrow_king_queen, arrow_man_woman, gp_label)), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
        .replace("__POINTS__", str(min(num_points, 8)))
    )


def decision_boundary_template(
    title: str = "Decision Boundary",
    duration: float = 10.0,
    boundary_type: str = "linear",
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class DecisionBoundaryScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)

        axes = Axes(
            x_range=[-3, 3, 1], y_range=[-3, 3, 1],
            x_length=10, y_length=10,
            axis_config={'color': GRAY, 'stroke_width': 1},
        ).move_to([0, 0, 0])
        x_label = Text("x₁", font_size=18, color=GRAY).next_to(axes.x_axis.get_end(), RIGHT)
        y_label = Text("x₂", font_size=18, color=GRAY).next_to(axes.y_axis.get_end(), UP)
        self.play(Create(axes), Write(x_label), Write(y_label), run_time=0.5)

        def curve_func(x):
            __CURVE_BODY__

        boundary = axes.plot(curve_func, color="#00CCCC", stroke_width=3)
        fill_above = axes.get_area(boundary, x_range=[-3, 3], color="#00CCCC", opacity=0.1)
        fill_below = axes.get_area(
            axes.plot(lambda x: -3, stroke_width=0),
            x_range=[-3, 3], color="#FF6B35", opacity=0.1,
        )
        self.play(Create(boundary), run_time=0.6)
        self.play(FadeIn(fill_above), FadeIn(fill_below), run_time=0.3)

        np.random.seed(42)
        n_pos = 12
        n_neg = 12
        pos_x = np.random.uniform(-2, 0, n_pos)
        pos_y = np.random.uniform(curve_func(pos_x) + 0.2, 2.5)
        neg_x = np.random.uniform(-2, 2, n_neg)
        neg_y = np.random.uniform(-2.5, curve_func(neg_x) - 0.2)

        pos_dots = []
        neg_dots = []
        for i in range(n_pos):
            dot = Dot(axes.c2p(pos_x[i], pos_y[i]), radius=0.06, color="#00CCCC")
            self.play(Create(dot), run_time=0.08)
            pos_dots.append(dot)
        for i in range(n_neg):
            dot = Dot(axes.c2p(neg_x[i], neg_y[i]), radius=0.06, color="#FF6B35")
            self.play(Create(dot), run_time=0.08)
            neg_dots.append(dot)

        class_a_label = Text("Class A", font_size=16, color="#00CCCC").to_corner(UR)
        class_b_label = Text("Class B", font_size=16, color="#FF6B35").to_corner(UL)
        self.add_fixed_in_frame_mobjects(class_a_label, class_b_label)
        self.play(Write(class_a_label), Write(class_b_label), run_time=0.2)

        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(title_text, axes, boundary, fill_above, fill_below, *pos_dots, *neg_dots, class_a_label, class_b_label)), run_time=__EXIT__)
"""
    curve_body = "return 0.5 * x - 0.2"
    if boundary_type == "nonlinear":
        curve_body = "return 0.6 * np.sin(1.8 * x) + 0.1 * x**2 - 0.3"
    elif boundary_type == "complex":
        curve_body = "return 0.4 * np.sin(2.5 * x) + 0.2 * np.cos(3 * x) - 0.1 * x**2"
    return (
        template
        .replace("__TITLE__", title)
        .replace("__CURVE_BODY__", curve_body)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def matrix_multiplication_template(
    title: str = "Matrix Multiplication",
    duration: float = 12.0,
    rows_a: int = 3,
    cols_a: int = 3,
    cols_b: int = 2,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    np.random.seed(42)
    mat_a = np.random.randint(0, 5, (rows_a, cols_a)).tolist()
    mat_b = np.random.randint(0, 5, (cols_a, cols_b)).tolist()
    mat_c = np.dot(np.array(mat_a), np.array(mat_b)).tolist()
    a_json = json.dumps(mat_a)
    b_json = json.dumps(mat_b)
    c_json = json.dumps(mat_c)
    template = INJECT_IMPORTS + f"""
class MatrixMultiplyScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)

        a_data = {a_json}
        b_data = {b_json}
        c_data = {c_json}
        r_a, c_a = len(a_data), len(a_data[0])
        c_b = len(b_data[0])
        cell_size = 0.5
        gap = 0.6

        a_group = VGroup()
        for i in range(r_a):
            for j in range(c_a):
                val = a_data[i][j]
                sq = Square(side_length=cell_size, stroke_color=GRAY_C, stroke_width=1, fill_opacity=0.15)
                sq.move_to([j * gap - (c_a - 1) * gap / 2, (r_a - 1) * gap / 2 - i * gap, 0])
                num = Text(str(val), font_size=14, color="#00CCCC").move_to(sq.get_center())
                a_group.add(VGroup(sq, num))

        a_label = MathTex("A", font_size=28, color="#00CCCC").next_to(a_group, LEFT, buff=0.5)
        self.play(Create(a_group), Write(a_label), run_time=0.6)

        multiply = Text("×", font_size=24, color=WHITE).next_to(a_group, RIGHT, buff=0.3)

        b_group = VGroup()
        b_offset_x = (c_a - 1) * gap / 2 + gap + 0.6
        for i in range(c_a):
            for j in range(c_b):
                val = b_data[i][j]
                sq = Square(side_length=cell_size, stroke_color=GRAY_C, stroke_width=1, fill_opacity=0.15)
                sq.move_to([b_offset_x + j * gap - (c_b - 1) * gap / 2, (r_a - 1) * gap / 2 - i * gap, 0])
                num = Text(str(val), font_size=14, color="#FF6B35").move_to(sq.get_center())
                b_group.add(VGroup(sq, num))

        b_label = MathTex("B", font_size=28, color="#FF6B35").next_to(b_group, LEFT, buff=0.3)
        self.play(Write(multiply), Create(b_group), Write(b_label), run_time=0.6)

        equals = Text("=", font_size=24, color=WHITE).next_to(b_group, RIGHT, buff=0.3)

        c_group = VGroup()
        c_offset_x = b_offset_x + (c_b - 1) * gap / 2 + gap + 0.6
        for i in range(r_a):
            for j in range(c_b):
                val = c_data[i][j]
                sq = Square(side_length=cell_size, stroke_color=YELLOW, stroke_width=1, fill_opacity=0.15)
                sq.move_to([c_offset_x + j * gap - (c_b - 1) * gap / 2, (r_a - 1) * gap / 2 - i * gap, 0])
                num = Text(str(val), font_size=14, color=YELLOW).move_to(sq.get_center())
                c_group.add(VGroup(sq, num))

        self.play(Write(equals), run_time=0.2)

        row_highlight = VGroup()
        col_highlight = VGroup()
        result_highlight = VGroup()
        explanation = Text("Dot product: row × column", font_size=18, color=GRAY_C).to_corner(DL)
        self.add_fixed_in_frame_mobjects(explanation)
        self.play(Write(explanation))

        all_done = VGroup(a_group, b_group, c_group, multiply, equals, a_label, b_label)

        for ri in range(min(r_a, 3)):
            r_highlight = VGroup(*a_group[ri * c_a:(ri + 1) * c_a]).copy()
            r_highlight.set_stroke(YELLOW, width=3)
            self.play(r_highlight.animate.set_stroke(opacity=1), run_time=0.2)

            for ci in range(min(c_b, 2)):
                c_highlight = VGroup(*[b_group[i * c_b + ci] for i in range(c_a)]).copy()
                c_highlight.set_stroke(YELLOW, width=3)
                self.play(c_highlight.animate.set_stroke(opacity=1), run_time=0.2)
                cell_idx = ri * c_b + ci
                if cell_idx < len(c_group):
                    rh = c_group[cell_idx].copy().set_stroke("#00CCCC", width=3)
                    self.play(rh.animate.set_stroke(opacity=1), run_time=0.15)

            if r_highlight in self.mobjects:
                self.remove(r_highlight)

        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(all_done, explanation)), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


def backpropagation_template(
    title: str = "Backpropagation",
    duration: float = 14.0,
    num_layers: int = 4,
    learning_rate: float = 0.1,
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class BackpropagationScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)

        layer_sizes = [4, 5, 5, 3]
        layers = len(layer_sizes)
        spacing_x = 2.2
        neuron_radius = 0.15

        all_neurons = []
        all_edges = []
        for l in range(layers):
            n_count = layer_sizes[l]
            layer_neurons = []
            for i in range(n_count):
                y = (n_count - 1) * 0.35 / 2 - i * 0.35
                x = l * spacing_x - (layers - 1) * spacing_x / 2
                neuron = Circle(radius=neuron_radius, color=BLUE_C, fill_opacity=0.3, fill_color=BLUE_C)
                neuron.move_to([x, y, 0])
                layer_neurons.append(neuron)
                all_neurons.append(neuron)
            if l > 0:
                prev = all_neurons[-n_count - layer_sizes[l - 1]:-n_count] if l > 1 else all_neurons[:layer_sizes[l - 1]]
                for p in prev:
                    for n in layer_neurons:
                        edge = Line(p.get_center(), n.get_center(), stroke_color=GRAY_D, stroke_width=1)
                        all_edges.append(edge)

        network = VGroup(*all_neurons, *all_edges)
        self.play(Create(network), run_time=1.0)

        layer_labels = ["Input", "Hidden 1", "Hidden 2", "Output"]
        for l in range(layers):
            x = l * spacing_x - (layers - 1) * spacing_x / 2
            label = Text(layer_labels[l], font_size=14, color=GRAY_C).move_to([x, -2.0, 0])
            self.play(Write(label), run_time=0.1)

        fwd_label = Text("Forward pass", font_size=22, color="#00CCCC").to_corner(UR)
        self.add_fixed_in_frame_mobjects(fwd_label)
        self.play(Write(fwd_label))

        for e in all_edges:
            e.set_stroke("#00CCCC", width=1, opacity=0.3)
            self.play(e.animate.set_stroke(opacity=0.8), run_time=0.02)
        for n in all_neurons:
            self.play(n.animate.set_fill(opacity=0.6), run_time=0.02)

        loss_box = RoundedRectangle(width=2, height=0.5, corner_radius=0.08, stroke_color="#FF6B35", fill_opacity=0.15)
        loss_box.move_to([0, -2.8, 0])
        loss_text = Text("Loss = 2.47", font_size=16, color="#FF6B35").move_to(loss_box.get_center())
        self.play(Create(loss_box), Write(loss_text), run_time=0.3)

        bwd_label = Text("Backward pass", font_size=22, color="#FF6B35").to_corner(UR)
        self.add_fixed_in_frame_mobjects(bwd_label)
        self.play(Transform(fwd_label, bwd_label), run_time=0.3)

        loss_val = 2.47
        for step in range(4):
            loss_val *= 0.6
            new_loss = Text(f"Loss = {loss_val:.2f}", font_size=16, color="#FF6B35").move_to(loss_box.get_center())
            self.play(Transform(loss_text, new_loss), run_time=0.3)
            for i, n in enumerate(reversed(all_neurons)):
                if step < 2:
                    n.set_stroke(YELLOW, width=2)
                self.play(n.animate.set_fill(opacity=0.4 + 0.4 * (1 - step * 0.2)), run_time=0.005)

        grad_label = Text(f"lr = __LR__", font_size=16, color=GRAY_C).next_to(loss_box, DOWN, buff=0.2)
        self.add_fixed_in_frame_mobjects(grad_label)
        self.play(Write(grad_label))

        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(network, title_text, fwd_label, loss_box, loss_text, grad_label)), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
        .replace("__LR__", str(learning_rate))
    )


def probability_distribution_template(
    title: str = "Probability Distribution",
    duration: float = 10.0,
    dist_type: str = "gaussian",
    entry_time: float = 0.5,
    exit_time: float = 0.5,
) -> str:
    template = INJECT_IMPORTS + """
class ProbabilityDistributionScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e1e"
        title_text = Text("__TITLE__", font_size=36, color=WHITE).to_edge(UP)
        self.play(Write(title_text), run_time=__ENTRY__)

        axes = Axes(
            x_range=[-4, 4, 1], y_range=[0, 0.5, 0.1],
            x_length=10, y_length=6,
            axis_config={'color': GRAY, 'stroke_width': 1},
        ).move_to([0, -0.5, 0])
        x_label = Text("x", font_size=18, color=GRAY).next_to(axes.x_axis.get_end(), RIGHT)
        y_label = Text("P(x)", font_size=18, color="#00CCCC").next_to(axes.y_axis.get_end(), UP)
        self.play(Create(axes), Write(x_label), Write(y_label), run_time=0.5)

        mu = 0
        sigma = 1
        def gaussian(x):
            return np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))

        curve = axes.plot(gaussian, color="#00CCCC", stroke_width=3)
        fill = axes.get_area(curve, x_range=[-3, 3], color="#00CCCC", opacity=0.15)
        self.play(Create(curve), run_time=0.8)
        self.play(FadeIn(fill), run_time=0.3)

        mean_line = DashedLine(
            axes.c2p(mu, 0), axes.c2p(mu, gaussian(mu)),
            color=WHITE, stroke_width=1, dash_length=0.05,
        )
        mean_label = MathTex("\\mu", font_size=22, color=WHITE).next_to(mean_line, UP, buff=0.1)
        self.play(Create(mean_line), Write(mean_label), run_time=0.3)

        std_left = DashedLine(
            axes.c2p(mu - sigma, 0), axes.c2p(mu - sigma, gaussian(mu - sigma)),
            color="#FF6B35", stroke_width=1, dash_length=0.05,
        )
        std_right = DashedLine(
            axes.c2p(mu + sigma, 0), axes.c2p(mu + sigma, gaussian(mu + sigma)),
            color="#FF6B35", stroke_width=1, dash_length=0.05,
        )
        std_label = MathTex("\\pm\\sigma", font_size=18, color="#FF6B35")
        std_label.move_to([mu, gaussian(mu) * 0.6, 0])
        self.play(Create(std_left), Create(std_right), Write(std_label), run_time=0.3)

        sample_points = np.random.normal(mu, sigma, 50)
        sample_dots = VGroup()
        for val in sample_points:
            if -3.5 < val < 3.5:
                dot = Dot(axes.c2p(val, 0.005), radius=0.02, color=YELLOW)
                sample_dots.add(dot)
        self.play(LaggedStart(
            *[GrowFromCenter(d) for d in sample_dots],
            lag_ratio=0.03, run_time=1.0,
        ))

        n_label = Text("n = 50 samples", font_size=16, color=GRAY_C).to_corner(DL)
        self.add_fixed_in_frame_mobjects(n_label)
        self.play(Write(n_label))

        remaining = max(0, __DURATION__ - self.time - __EXIT__)
        if remaining > 0:
            self.wait(remaining)
        if __EXIT__ > 0:
            self.play(FadeOut(VGroup(title_text, axes, curve, fill, mean_line, mean_label, std_left, std_right, std_label, sample_dots, n_label)), run_time=__EXIT__)
"""
    return (
        template
        .replace("__TITLE__", title)
        .replace("__DURATION__", str(duration))
        .replace("__ENTRY__", str(entry_time))
        .replace("__EXIT__", str(exit_time))
    )


TEMPLATE_REGISTRY: dict[str, callable] = {
    "neural_network": neural_network_template,
    "attention": attention_template,
    "transformer": transformer_block_template,
    "convolution": convolution_template,
    "recurrent": recurrent_template,
    "algorithm_flow": algorithm_flow_template,
    "bar_chart": bar_chart_template,
    "gradient_descent": gradient_descent_template,
    "text_reveal": text_reveal_template,
    "architecture_diagram": architecture_diagram_template,
    "data_flow": data_flow_diagram_template,
    "timeline": timeline_template,
    "comparison": comparison_chart_template,
    "process_flow": process_flow_template,
    "concept_map": concept_map_template,
    "loss_landscape": loss_landscape_template,
    "embedding_space": embedding_space_template,
    "decision_boundary": decision_boundary_template,
    "matrix_multiplication": matrix_multiplication_template,
    "backpropagation": backpropagation_template,
    "probability_distribution": probability_distribution_template,
    "intro": intro_template,
    "outro": outro_template,
}


CUSTOM_TEMPLATE_REGISTRY: dict[str, callable] = {}


def register_custom_template(name: str, generator_fn: callable) -> None:
    """Register a new template function that takes (title, duration, **kwargs) and returns Manim code."""
    CUSTOM_TEMPLATE_REGISTRY[name] = generator_fn
