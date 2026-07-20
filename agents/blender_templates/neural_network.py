import bpy, json, sys, math, os, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from blender_templates.common import (parse_args, clear_scene, setup_scene, set_frame_range,
    material_teal, material_dark, material_orange, material_white, material_emissive,
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

layer_sizes = params.get("layer_sizes", [4, 6, 5, 3])
layer_spacing = 2.5
z_spacing = 0.4

import random as rnd
rnd.seed(42)

for l, size in enumerate(layer_sizes):
    x_center = (l - len(layer_sizes) / 2) * layer_spacing
    r = 0.8 if size <= 4 else 1.0
    for n in range(size):
        angle = (n / size) * 2 * math.pi + l * 0.5
        x = x_center + math.cos(angle) * r
        z = math.sin(angle) * r + 0.5
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(x, 0, z))
        neuron = bpy.context.active_object
        neuron.name = f"neuron_l{l}_n{n}"
        colors = [material_teal(), material_orange(), material_white(), material_dark()]
        neuron.data.materials.append(colors[l % len(colors)])

for l in range(len(layer_sizes) - 1):
    s1 = layer_sizes[l]
    s2 = layer_sizes[l + 1]
    x1 = (l - len(layer_sizes) / 2) * layer_spacing
    x2 = (l + 1 - len(layer_sizes) / 2) * layer_spacing
    r1 = 0.8 if s1 <= 4 else 1.0
    r2 = 0.8 if s2 <= 4 else 1.0
    for n1 in range(min(s1, 3)):
        angle1 = (n1 / s1) * 2 * math.pi + l * 0.5
        p1 = (x1 + math.cos(angle1) * r1, 0, math.sin(angle1) * r1 + 0.5)
        for n2 in range(min(s2, 2)):
            angle2 = (n2 / s2) * 2 * math.pi + (l + 1) * 0.5
            p2 = (x2 + math.cos(angle2) * r2, 0, math.sin(angle2) * r2 + 0.5)
            mid = ((p1[0] + p2[0]) / 2, 0, (p1[2] + p2[2]) / 2)
            dx = p2[0] - p1[0]
            dz = p2[2] - p1[2]
            dist = math.sqrt(dx*dx + dz*dz)
            if dist < 0.01:
                continue
            bpy.ops.mesh.primitive_cylinder_add(vertices=4, radius=0.005, depth=dist,
                                                location=mid)
            conn = bpy.context.active_object
            conn.rotation_euler.x = math.atan2(dz, dx)
            conn.data.materials.append(material_white())

cam = add_camera(location=(0, -6, 4))

output = os.path.join(params.get("_output", ""), "frame_")
set_output_path(output)
bpy.ops.render.render(animation=True, write_still=False)
