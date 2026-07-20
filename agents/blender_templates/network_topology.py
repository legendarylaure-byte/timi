import bpy, json, sys, math, os, random

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

node_count = params.get("nodes", 8)
import random as rnd
rnd.seed(42)

positions = []
for _ in range(node_count):
    angle = rnd.uniform(0, 2 * math.pi)
    radius = rnd.uniform(1.5, 3.5)
    x = math.cos(angle) * radius
    y = math.sin(angle) * radius
    z = rnd.uniform(0.2, 1.0)
    positions.append((x, y, z))

for i, pos in enumerate(positions):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=pos)
    node = bpy.context.active_object
    node.name = f"node_{i}"
    colors = [material_teal(), material_orange(), material_white(), material_gray()]
    node.data.materials.append(colors[i % len(colors)])

for i in range(min(20, node_count * 2)):
    a = rnd.randint(0, node_count - 1)
    b = rnd.randint(0, node_count - 1)
    if a == b:
        continue
    p1 = positions[a]
    p2 = positions[b]
    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2)
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dz = p2[2] - p1[2]
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
    bpy.ops.mesh.primitive_cylinder_add(vertices=4, radius=0.015, depth=dist,
                                        location=mid)
    conn = bpy.context.active_object
    conn.rotation_euler.x = math.atan2(dz, math.sqrt(dx*dx + dy*dy))
    conn.rotation_euler.z = math.atan2(dy, dx)
    conn.data.materials.append(material_white())

cam = add_camera(location=(0, -7, 5))
camera_orbit(cam, start_angle=-10, end_angle=10, radius=7, height=3,
             frame_start=1, frame_end=total_frames)

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
