import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_gray,
    material_glass, material_metal, material_emissive,
    setup_lighting_3point, setup_backdrop, add_camera, camera_orbit, set_output_path)

params = parse_args()
title = params.get("title", "Chip Architecture")
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

die = bpy.ops.mesh.primitive_cube_add(size=3, location=(0, 0, 0))
die_obj = bpy.context.active_object
die_obj.name = "die"
die_obj.data.materials.append(material_teal())

bpy.ops.mesh.primitive_cube_add(size=2.5, location=(0, 0, 0.3))
inner = bpy.context.active_object
inner.name = "inner_layer"
inner.data.materials.append(material_dark())

bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0.8, 0.8, 0.6))
block1 = bpy.context.active_object
block1.name = "tensor_core"
block1.data.materials.append(material_orange())

bpy.ops.mesh.primitive_cube_add(size=0.5, location=(-0.8, 0.8, 0.6))
block2 = bpy.context.active_object
block2.name = "cuda_core"
block2.data.materials.append(material_white())

bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0.8, -0.8, 0.6))
block3 = bpy.context.active_object
block3.name = "cache"
block3.data.materials.append(material_white())

bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.05, depth=0.3, location=(0.8, 0.8, 0.1))
via1 = bpy.context.active_object
via1.data.materials.append(material_metal())

for x in (-0.5, 0.5):
    for y in (-0.5, 0.5):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.03, depth=0.8,
                                            location=(x, y, -0.9))
        obj = bpy.context.active_object
        obj.data.materials.append(material_metal())

cam = add_camera(location=(5, -5, 4))
camera_orbit(cam, start_angle=-15, end_angle=15, radius=6, height=3,
             frame_start=1, frame_end=total_frames)

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
