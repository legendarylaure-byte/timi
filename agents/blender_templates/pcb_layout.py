import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_white, material_gray, material_metal,
    setup_lighting_3point, setup_backdrop, add_camera, camera_orbit, set_output_path)

params = parse_args()
title = params.get("title", "PCB Layout")
dur = params.get("duration", 5.0)
engine = params.get("engine", "eevee")
fps = 24
total_frames = int(dur * fps)

clear_scene()
setup_scene(engine=engine, samples=params.get("samples", 64))
set_frame_range(1, total_frames)

setup_lighting_3point()
setup_backdrop()

bpy.ops.mesh.primitive_cube_add(size=(6, 4, 0.15), location=(0, 0, 0))
board = bpy.context.active_object
board.name = "pcb"
board.data.materials.append(material_dark())

components = params.get("components", [
    {"size": (0.8, 0.5, 0.3), "pos": (-2, 1, 0.25), "label": "CPU"},
    {"size": (0.6, 0.4, 0.2), "pos": (2, 1, 0.2), "label": "RAM"},
    {"size": (0.4, 0.3, 0.15), "pos": (2, -1, 0.15), "label": "PCH"},
    {"size": (0.3, 0.2, 0.1), "pos": (0, -1.5, 0.1), "label": "VRM"},
    {"size": (0.15, 0.15, 0.08), "pos": (-1, -0.5, 0.08), "label": "Caps"},
])

for i, comp in enumerate(components):
    bpy.ops.mesh.primitive_cube_add(size=1, location=comp["pos"])
    obj = bpy.context.active_object
    obj.scale = comp["size"]
    obj.name = f"comp_{i}"
    if i == 0:
        obj.data.materials.append(material_teal())
    elif i == 1:
        obj.data.materials.append(material_white())
    else:
        obj.data.materials.append(material_gray())

import random
random.seed(7)
for _ in range(30):
    x = random.uniform(-2.8, 2.8)
    y = random.uniform(-1.8, 1.8)
    bpy.ops.mesh.primitive_cylinder_add(vertices=4, radius=0.008, depth=0.05,
                                        location=(x, y, 0.08))
    via = bpy.context.active_object
    via.data.materials.append(material_metal())

cam = add_camera(location=(0, -7, 5))
camera_orbit(cam, start_angle=-5, end_angle=5, radius=7, height=3,
             frame_start=1, frame_end=total_frames)

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
