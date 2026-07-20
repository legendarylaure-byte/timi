import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white,
    setup_lighting_studio, setup_backdrop, add_camera, set_output_path)

params = parse_args()
dur = params.get("duration", 5.0)
engine = params.get("engine", "eevee")
fps = 24
total_frames = int(dur * fps)

clear_scene()
setup_scene(engine=engine, samples=params.get("samples", 64))
set_frame_range(1, total_frames)

setup_lighting_studio()
setup_backdrop()

events = params.get("events", [
    {"year": "2017", "label": "Transformer", "height": 0.5},
    {"year": "2018", "label": "GPT-1", "height": 0.8},
    {"year": "2019", "label": "GPT-2", "height": 1.2},
    {"year": "2020", "label": "GPT-3", "height": 1.8},
    {"year": "2022", "label": "ChatGPT", "height": 2.5},
    {"year": "2023", "label": "GPT-4", "height": 3.0},
])

spacing = 1.2
total_w = (len(events) - 1) * spacing
start_x = -total_w / 2

bpy.ops.mesh.primitive_cube_add(size=(total_w + 2, 0.05, 0.05), location=(0, 0, 0))
line = bpy.context.active_object
line.data.materials.append(material_white())

for i, ev in enumerate(events):
    x = start_x + i * spacing
    h = ev.get("height", 0.5)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, h / 2))
    pillar = bpy.context.active_object
    pillar.scale = (0.08, 0.08, h)
    pillar.name = f"event_{i}"
    colors = [material_teal(), material_orange(), material_white()]
    pillar.data.materials.append(colors[i % len(colors)])

cam = add_camera(location=(0, -6, 3.5))

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
