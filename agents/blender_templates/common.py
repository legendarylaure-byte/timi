import bpy
import json
import os
import sys

# ── CLI arg parsing ──────────────────────────────────────────────

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if not argv:
        return {}
    if "--params" not in argv:
        return {}
    try:
        with open(argv[argv.index("--params") + 1]) as f:
            return json.load(f)
    except (ValueError, IndexError, OSError):
        return {}


def get_param(key, default=None):
    return parse_args().get(key, default)


# ── Scene setup ───────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat, do_unlink=True)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh, do_unlink=True)


def setup_scene(engine="eevee", samples=64, resolution=(1920, 1080), fps=24):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES" if engine == "cycles" else "BLENDER_EEVEE"
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    if engine == "cycles":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.01
    else:
        scene.eevee.taa_samples = 64
        try:
            scene.eevee.use_bloom = True
        except AttributeError:
            pass
        try:
            scene.eevee.use_ssr = True
        except AttributeError:
            pass
        try:
            scene.eevee.use_gtao = True
        except AttributeError:
            pass
        try:
            scene.eevee.use_motion_blur = True
        except AttributeError:
            pass
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium Contrast"


def set_frame_range(start, end):
    bpy.context.scene.frame_start = start
    bpy.context.scene.frame_end = end


# ── Materials ─────────────────────────────────────────────────────

_BRAND_TEAL = (0.0, 0.8, 0.8)
_BRAND_DARK = (0.117, 0.117, 0.117)
_BRAND_ORANGE = (1.0, 0.42, 0.21)
_WHITE = (0.9, 0.9, 0.9)
_LIGHT_GRAY = (0.2, 0.2, 0.22)


def _make_material(name, color, roughness=0.3, metallic=0.0, use_nodes=True):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = use_nodes
    if use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
            bsdf.inputs["Roughness"].default_value = roughness
            bsdf.inputs["Metallic"].default_value = metallic
    else:
        mat.diffuse_color = (*color, 1.0)
    return mat


def material_teal():
    return _make_material("teal", _BRAND_TEAL, roughness=0.2, metallic=0.1)


def material_dark():
    return _make_material("dark", _BRAND_DARK, roughness=0.6)


def material_orange():
    return _make_material("orange", _BRAND_ORANGE, roughness=0.3)


def material_white():
    return _make_material("white", _WHITE, roughness=0.4)


def material_gray():
    return _make_material("gray", _LIGHT_GRAY, roughness=0.5)


def material_glass():
    mat = _make_material("glass", (0.9, 0.9, 1.0), roughness=0.05)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Transmission"].default_value = 0.9
        bsdf.inputs["IOR"].default_value = 1.45
        bsdf.inputs["Alpha"].default_value = 0.3
    return mat


def material_metal():
    return _make_material("metal", (0.7, 0.7, 0.72), roughness=0.15, metallic=1.0)


def material_emissive(color, strength=1.0):
    mat = bpy.data.materials.new("emissive")
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    nodes.clear()
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1.0)
    emit.inputs["Strength"].default_value = strength
    output = nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(emit.outputs["Emission"], output.inputs["Surface"])
    return mat


# ── Lighting ──────────────────────────────────────────────────────

def clear_lights():
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)


def setup_lighting_3point():
    clear_lights()
    bpy.ops.object.light_add(type="AREA", location=(5, -5, 8))
    key = bpy.context.active_object
    key.data.energy = 800
    key.data.color = (1, 0.98, 0.95)
    bpy.ops.object.light_add(type="AREA", location=(-4, 4, 3))
    fill = bpy.context.active_object
    fill.data.energy = 300
    fill.data.color = (0.9, 0.92, 1.0)
    bpy.ops.object.light_add(type="AREA", location=(0, 0, -5))
    rim = bpy.context.active_object
    rim.data.energy = 200
    rim.data.color = (0.8, 0.85, 1.0)
    return key, fill, rim


def setup_lighting_studio():
    clear_lights()
    bpy.ops.object.light_add(type="AREA", location=(0, -6, 4))
    key = bpy.context.active_object
    key.data.energy = 1000
    key.data.color = (1, 0.98, 0.95)
    bpy.ops.object.light_add(type="AREA", location=(0, 5, 3))
    fill = bpy.context.active_object
    fill.data.energy = 400
    fill.data.color = (0.95, 0.96, 1.0)
    bpy.ops.object.light_add(type="AREA", location=(0, 0, 8))
    top = bpy.context.active_object
    top.data.energy = 300
    top.data.color = (1, 1, 1)
    return key, fill, top


def setup_backdrop(color=(0.117, 0.117, 0.117)):
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.5))
    plane = bpy.context.active_object
    mat = _make_material("backdrop", color, roughness=0.8)
    plane.data.materials.append(mat)
    return plane


# ── Camera ────────────────────────────────────────────────────────

def add_camera(location=(0, -8, 4), target=(0, 0, 0), lens=50):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.data.lens = lens
    track = cam.constraints.new(type="TRACK_TO")
    track.target = bpy.data.objects.new("target", None)
    track.target.location = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    return cam


def camera_orbit(cam, target=(0, 0, 0), radius=8, height=3, start_angle=0, end_angle=45, frame_start=1, frame_end=120):
    for frame in range(frame_start, frame_end + 1):
        t = (frame - frame_start) / (frame_end - frame_start)
        angle = start_angle + (end_angle - start_angle) * t
        rad = angle * 3.14159 / 180
        x = target[0] + radius * rad
        z = target[2] + height
        cam.location = (x, target[1] + radius, z)
        cam.keyframe_insert(data_path="location", index=-1, frame=frame)


# ── Output ────────────────────────────────────────────────────────

def set_output_path(path):
    bpy.context.scene.render.filepath = path
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_mode = "RGBA"


def render():
    bpy.ops.render.render(animation=True, write_still=False)
