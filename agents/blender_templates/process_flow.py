import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_gray,
    setup_lighting_studio, setup_backdrop, add_camera, camera_orbit, set_output_path)

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

stages = params.get("stages", ["Input A", "Step 1", "Step 2", "Output B"])
spacing = 2.0
total_w = (len(stages) - 1) * spacing
start_x = -total_w / 2

for i, stage in enumerate(stages):
    x = start_x + i * spacing
    bpy.ops.mesh.primitive_circle_add(vertices=32, fill_type="NGON", radius=0.5,
                                       location=(x, 0, 0.5))
    circle = bpy.context.active_object
    circle.name = f"stage_{i}"
    colors = [material_teal(), material_orange(), material_white(), material_dark()]
    circle.data.materials.append(colors[i % len(colors)])

for i in range(len(stages) - 1):
    x1 = start_x + i * spacing + 0.5
    x2 = start_x + (i + 1) * spacing - 0.5
    mid_x = (x1 + x2) / 2
    dist = x2 - x1
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=dist,
                                        location=(mid_x, 0, 0.5))
    conn = bpy.context.active_object
    conn.data.materials.append(material_gray())

cam = add_camera(location=(0, -7, 3))

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
