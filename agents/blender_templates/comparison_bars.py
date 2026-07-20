import bpy, json, sys, math, os, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_gray,
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

data = params.get("data", [3, 5, 2, 7, 4])
labels = params.get("labels", ["A", "B", "C", "D", "E"])
bar_width = 0.6
spacing = 1.2
total_w = (len(data) - 1) * spacing
start_x = -total_w / 2

max_val = max(data) if data else 1
for i, val in enumerate(data):
    h = (val / max_val) * 3.0
    x = start_x + i * spacing
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, h / 2))
    bar = bpy.context.active_object
    bar.scale = (bar_width, bar_width, h)
    bar.name = f"bar_{i}"
    colors = [material_teal(), material_orange(), material_white(), material_gray(), material_dark()]
    bar.data.materials.append(colors[i % len(colors)])

cam = add_camera(location=(0, -6, 4))

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
