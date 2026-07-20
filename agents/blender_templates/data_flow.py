import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_emissive,
    setup_lighting_studio, setup_backdrop, add_camera, set_output_path)

params = parse_args()
title = params.get("title", "Data Flow")
dur = params.get("duration", 5.0)
engine = params.get("engine", "eevee")
fps = 24
total_frames = int(dur * fps)

clear_scene()
setup_scene(engine=engine, samples=params.get("samples", 64))
set_frame_range(1, total_frames)

setup_lighting_studio()
setup_backdrop()

nodes = params.get("nodes", [
    {"pos": (-3, 0, 0.5), "label": "Source"},
    {"pos": (0, 1.5, 0.5), "label": "Process A"},
    {"pos": (0, -1.5, 0.5), "label": "Process B"},
    {"pos": (3, 0, 0.5), "label": "Dest"},
])

for i, node in enumerate(nodes):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=node["pos"])
    obj = bpy.context.active_object
    obj.name = f"node_{i}"
    if i == 0 or i == len(nodes) - 1:
        obj.data.materials.append(material_teal())
    else:
        obj.data.materials.append(material_orange())

import random
random.seed(42)
particle_count = params.get("particles", 50)
for p in range(particle_count):
    t = p / particle_count
    angle = t * 2 * math.pi
    x = math.cos(angle) * 3
    y = math.sin(angle) * 2
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(x, y, 0.5 + random.uniform(-0.2, 0.2)))
    sphere = bpy.context.active_object
    sphere.name = f"particle_{p}"
    mat = material_emissive((0.0, 0.8, 0.8), strength=2.0)
    sphere.data.materials.append(mat)

cam = add_camera(location=(0, -7, 4))

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
