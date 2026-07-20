import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_glass, material_metal,
    setup_lighting_3point, setup_backdrop, add_camera, camera_orbit, set_output_path)

params = parse_args()
title = params.get("title", "Device Cutaway")
dur = params.get("duration", 5.0)
engine = params.get("engine", "cycles")
samples = params.get("samples", 128)
fps = 24
total_frames = int(dur * fps)

clear_scene()
setup_scene(engine=engine, samples=samples)
set_frame_range(1, total_frames)

setup_lighting_3point()
setup_backdrop()

bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2.0, depth=0.3, location=(0, 0, 0))
base = bpy.context.active_object
base.name = "base"
base.data.materials.append(material_dark())

bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1.8, depth=1.5, location=(0, 0, 0.9))
body = bpy.context.active_object
body.name = "body"
body.data.materials.append(material_glass())

for i, (r, z, label) in enumerate([(1.5, 0.3, "Layer 1"), (1.2, 0.7, "Layer 2"),
                                      (0.9, 1.1, "Core"), (0.5, 1.4, "CPU")]):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r * 0.5, depth=0.15,
                                        location=(0, 0, z))
    layer = bpy.context.active_object
    layer.name = label
    mats = [material_teal(), material_orange(), material_white(), material_metal()]
    layer.data.materials.append(mats[i % len(mats)])

bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.05, depth=0.3,
                                    location=(0.5, 0.5, 0.15))
obj = bpy.context.active_object
obj.data.materials.append(material_metal())

cam = add_camera(location=(4, -5, 3))
camera_orbit(cam, start_angle=-10, end_angle=10, radius=5, height=2,
             frame_start=1, frame_end=total_frames)

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
