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

stages = params.get("stages", ["Fetch", "Decode", "Execute", "Write"])
stage_w = 1.2
spacing = 1.8
total_w = (len(stages) - 1) * spacing
start_x = -total_w / 2

for i, stage in enumerate(stages):
    x = start_x + i * spacing
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0.6))
    box = bpy.context.active_object
    box.scale = (stage_w, 0.8, 1.2)
    box.name = f"stage_{i}"
    colors = [material_teal(), material_orange(), material_white(), material_dark()]
    box.data.materials.append(colors[i % len(colors)])

for i in range(len(stages) - 1):
    x1 = start_x + i * spacing + stage_w / 2
    x2 = start_x + (i + 1) * spacing - stage_w / 2
    mid_x = (x1 + x2) / 2
    dist = x2 - x1
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=dist,
                                        location=(mid_x, 0, 0.6))
    arrow = bpy.context.active_object
    arrow.rotation_euler.z = 0
    arrow.data.materials.append(material_white())

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(start_x, 0, 1.2))
token = bpy.context.active_object
token.name = "token"
token.data.materials.append(material_orange())

cam = add_camera(location=(0, -7, 3))

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
