import math


def bounce(t: float, amplitude: float = 15, frequency: float = 2.0) -> dict:
    y_offset = -abs(math.sin(t * frequency * math.pi) * amplitude)
    return {"x": 0, "y": y_offset, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def float_anim(t: float, amplitude: float = 8, period: float = 3.0) -> dict:
    y_offset = math.sin(t * 2 * math.pi / period) * amplitude
    x_offset = math.cos(t * 2 * math.pi / (period * 1.5)) * amplitude * 0.5
    return {"x": x_offset, "y": y_offset, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def wave(t: float, max_angle: float = 25, frequency: float = 2.5) -> dict:
    rotation = math.sin(t * frequency * math.pi) * max_angle
    return {"x": 0, "y": 0, "rotation": rotation, "scale_x": 1.0, "scale_y": 1.0}


def grow(t: float, scale_min: float = 0.8, scale_max: float = 1.15, frequency: float = 1.5) -> dict:
    progress = (math.sin(t * frequency * math.pi) + 1) / 2
    scale = scale_min + (scale_max - scale_min) * progress
    return {"x": 0, "y": 0, "rotation": 0, "scale_x": scale, "scale_y": scale}


def wiggle(t: float, amplitude: float = 5, frequency: float = 4.0) -> dict:
    x_offset = math.sin(t * frequency * math.pi * 2) * amplitude
    return {"x": x_offset, "y": 0, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def slide_in(t: float, total_frames: int, direction: str = "left", duration_ratio: float = 0.5) -> dict:
    slide_frames = int(total_frames * duration_ratio)
    if t >= slide_frames:
        return {"x": 0, "y": 0, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}
    progress = t / max(slide_frames, 1)
    eased = 1 - (1 - progress) ** 2
    offsets = {
        "left": {"x": -800 * (1 - eased), "y": 0},
        "right": {"x": 800 * (1 - eased), "y": 0},
        "top": {"x": 0, "y": -800 * (1 - eased)},
        "bottom": {"x": 0, "y": 800 * (1 - eased)},
    }
    off = offsets.get(direction, {"x": 0, "y": 0})
    return {"x": off["x"], "y": off["y"], "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def thinking(t: float, angle_range: float = 15, frequency: float = 0.5) -> dict:
    rotation = math.sin(t * frequency * math.pi) * angle_range
    y_offset = -2
    return {"x": 0, "y": y_offset, "rotation": rotation, "scale_x": 1.0, "scale_y": 1.0}


def twinkle(t: float, scale_min: float = 0.85, scale_max: float = 1.1, frequency: float = 0.8) -> dict:
    progress = (math.sin(t * frequency * math.pi * 2) + 1) / 2
    scale = scale_min + (scale_max - scale_min) * progress
    return {"x": 0, "y": 0, "rotation": 0, "scale_x": scale, "scale_y": scale}


def spin(t: float, speed: float = 30, direction: str = "cw") -> dict:
    dir_mult = 1 if direction == "cw" else -1
    rotation = (t * speed * dir_mult) % 360
    return {"x": 0, "y": 0, "rotation": rotation, "scale_x": 1.0, "scale_y": 1.0}


def glide(t: float, amplitude: float = 6, period: float = 2.5) -> dict:
    x_offset = math.sin(t * 2 * math.pi / period) * amplitude
    y_offset = math.cos(t * 2 * math.pi / (period * 1.3)) * amplitude * 0.7
    return {"x": x_offset, "y": y_offset, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def squish(t: float, scale_x_min: float = 0.7, scale_x_max: float = 1.2, frequency: float = 1.0) -> dict:
    progress = (math.sin(t * frequency * math.pi) + 1) / 2
    sx = scale_x_min + (scale_x_max - scale_x_min) * progress
    sy = 2.0 - sx
    return {"x": 0, "y": 0, "rotation": 0, "scale_x": sx, "scale_y": sy}


def dance(t: float, amplitude: float = 18, frequency: float = 3.0) -> dict:
    x_offset = math.sin(t * frequency * math.pi) * amplitude
    rotation = math.sin(t * frequency * math.pi * 2) * 10
    y_offset = abs(math.sin(t * frequency * math.pi * 2)) * 8
    return {"x": x_offset, "y": y_offset, "rotation": rotation, "scale_x": 1.0, "scale_y": 1.0}


def sway(t: float, amplitude: float = 12, frequency: float = 1.2) -> dict:
    x_offset = math.sin(t * frequency * math.pi) * amplitude
    rotation = math.sin(t * frequency * math.pi) * 5
    return {"x": x_offset, "y": 0, "rotation": rotation, "scale_x": 1.0, "scale_y": 1.0}


def cry(t: float, amplitude: float = 8, frequency: float = 1.5) -> dict:
    phase = t * frequency * math.pi
    y_offset = abs(math.sin(phase)) * amplitude * 0.5
    x_shake = math.sin(phase * 3) * 3
    return {"x": x_shake, "y": y_offset, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def hug(t: float, scale_min: float = 0.9, scale_max: float = 1.05, frequency: float = 1.0) -> dict:
    progress = (math.sin(t * frequency * math.pi) + 1) / 2
    scale = scale_min + (scale_max - scale_min) * progress
    return {"x": 0, "y": 0, "rotation": 0, "scale_x": scale, "scale_y": scale}


def none_anim(t: float = 0) -> dict:
    return {"x": 0, "y": 0, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}


def breathe(t: float, amplitude: float = 3, period: float = 4.0) -> dict:
    progress = (math.sin(t * 2 * math.pi / period) + 1) / 2
    scale_y = 1.0 + (progress - 0.5) * amplitude * 0.01
    scale_x = 1.0 - (progress - 0.5) * amplitude * 0.005
    y_offset = -(progress - 0.5) * amplitude * 0.5
    return {"x": 0, "y": y_offset, "rotation": 0, "scale_x": scale_x, "scale_y": scale_y}


ANIMATION_FUNCTIONS = {
    "bounce": bounce,
    "float": float_anim,
    "wave": wave,
    "grow": grow,
    "wiggle": wiggle,
    "slide_in": slide_in,
    "thinking": thinking,
    "twinkle": twinkle,
    "spin": spin,
    "glide": glide,
    "squish": squish,
    "dance": dance,
    "sway": sway,
    "cry": cry,
    "hug": hug,
    "breathe": breathe,
    "none": none_anim,
}
