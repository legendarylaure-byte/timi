import bpy, json, sys, math, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_glass, material_metal,
    setup_lighting_3point, setup_backdrop, add_camera, camera_orbit, set_output_path)

params = parse_args()
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

layers = params.get("layers", 4)
base_size = 2.5
for i in range(layers):
    size = base_size - i * 0.4
    height = 0.2
    z = i * 0.4 + 0.1
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
    obj = bpy.context.active_object
    obj.scale = (size, size * 0.7, height)
    obj.name = f"layer_{i}"
    colors = [material_teal(), material_dark(), material_orange(), material_white(),
              material_glass(), material_metal()]
    obj.data.materials.append(colors[i % len(colors)])

cam = add_camera(location=(3, -5, 3))
camera_orbit(cam, start_angle=-15, end_angle=15, radius=5, height=2,
             frame_start=1, frame_end=total_frames)

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
