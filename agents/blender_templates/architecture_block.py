import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_white, material_gray, material_orange,
    setup_lighting_studio, setup_backdrop, add_camera, camera_orbit, set_output_path)

params = parse_args()
title = params.get("title", "Architecture")
dur = params.get("duration", 5.0)
engine = params.get("engine", "eevee")
fps = 24
total_frames = int(dur * fps)

clear_scene()
setup_scene(engine=engine, samples=params.get("samples", 64))
set_frame_range(1, total_frames)

setup_lighting_studio()
setup_backdrop()

block_data = params.get("blocks", [
    {"label": "Input", "size": (1.5, 1.0, 0.8), "pos": (-3.0, 0, 0.4), "color": "teal"},
    {"label": "Process", "size": (2.0, 1.5, 1.2), "pos": (0, 0, 0.6), "color": "orange"},
    {"label": "Output", "size": (1.5, 1.0, 0.8), "pos": (3.0, 0, 0.4), "color": "teal"},
])

for i, block in enumerate(block_data):
    bpy.ops.mesh.primitive_cube_add(size=1, location=block["pos"])
    obj = bpy.context.active_object
    obj.scale = block["size"]
    obj.name = f"block_{i}_{block['label']}"
    color_map = {"teal": material_teal(), "orange": material_orange(),
                 "white": material_white(), "gray": material_gray(), "dark": material_dark()}
    obj.data.materials.append(color_map.get(block.get("color", "teal"), material_teal()))

if len(block_data) >= 2:
    for i in range(len(block_data) - 1):
        p1 = block_data[i]["pos"]
        p2 = block_data[i + 1]["pos"]
        mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2)
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.sqrt(dx * dx + dy * dy)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.05, depth=dist,
                                            location=mid)
        conn = bpy.context.active_object
        conn.rotation_euler.z = math.atan2(dy, dx)
        conn.data.materials.append(material_white())

cam = add_camera(location=(0, -8, 3))
camera_orbit(cam, start_angle=-10, end_angle=10, radius=8, height=2,
             frame_start=1, frame_end=total_frames)

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
