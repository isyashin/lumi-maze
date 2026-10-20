import sys
import os
import bpy
import json

def log(msg):
    print(f"[export_pxltiger] {msg}")

def main():
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []

    if len(args) < 2:
        raise ValueError("Usage: blender.exe --background --factory-startup --python tools/export_pxltiger.py -- INPUT_DIR OUTPUT.glb")

    input_dir = args[0]
    output_glb = args[1]
    output_json = os.path.splitext(output_glb)[0] + ".json"

    log(f"Input dir: {input_dir}")
    log(f"Output glb: {output_glb}")

    # Verify input files
    base_fbx = os.path.join(input_dir, "Fox.fbx")
    if not os.path.exists(base_fbx):
        raise FileNotFoundError(f"Missing base Fox.fbx in {input_dir}")

    clips_def = [
        ("Idle", "Fox_Idle.fbx"),
        ("Run", "Fox_Run_InPlace.fbx"),
        ("Jump", "Fox_Jump_Pivot_InPlace.fbx"),
        ("InAir", "Fox_Jump_InAir.fbx"),
        ("Fall", "Fox_Falling.fbx"),
        ("Pickup", "Fox_Sit_Yes.fbx")
    ]

    for alias, fname in clips_def:
        fpath = os.path.join(input_dir, fname)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing clip {fname} in {input_dir}")

    textures = {
        "bc": os.path.join(input_dir, "T_Fox_BC.png"),
        "normal": os.path.join(input_dir, "T_Fox_Normal.png"),
        "ao": os.path.join(input_dir, "T_Fox_AO.png")
    }
    for tkey, tpath in textures.items():
        if not os.path.exists(tpath):
            log(f"Warning: Texture {tkey} not found at {tpath}")

    # 1. Start empty scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2. Import base Fox.fbx
    log(f"Importing base: {base_fbx}")
    bpy.ops.import_scene.fbx(filepath=base_fbx)

    # Identify base mesh and armature
    base_mesh = None
    base_armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            base_mesh = obj
        elif obj.type == 'ARMATURE':
            base_armature = obj

    if not base_mesh or not base_armature:
        raise RuntimeError("Failed to find base mesh and armature in Fox.fbx")

    base_mesh.name = "fox"
    base_armature.name = "FoxTransform"

    # Smooth normals on mesh
    bpy.context.view_layer.objects.active = base_mesh
    bpy.ops.object.mode_set(mode='OBJECT')
    # Apply smooth shading
    for poly in base_mesh.data.polygons:
        poly.use_smooth = True

    # 3. Build Principled BSDF Material and assign to base mesh
    mat = bpy.data.materials.new(name="M_Fox")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    shader_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader_node.location = (0, 0)
    shader_node.inputs['Roughness'].default_value = 0.82
    shader_node.inputs['Metallic'].default_value = 0.0

    material_output = nodes.new(type='ShaderNodeOutputMaterial')
    material_output.location = (300, 0)
    links.new(shader_node.outputs['BSDF'], material_output.inputs['Surface'])

    # BC Texture
    if os.path.exists(textures["bc"]):
        img_bc = bpy.data.images.load(textures["bc"])
        img_bc.colorspace_settings.name = 'sRGB'
        tex_bc = nodes.new(type='ShaderNodeTexImage')
        tex_bc.image = img_bc
        tex_bc.location = (-400, 200)
        links.new(tex_bc.outputs['Color'], shader_node.inputs['Base Color'])

    # Normal Texture
    if os.path.exists(textures["normal"]):
        img_n = bpy.data.images.load(textures["normal"])
        img_n.colorspace_settings.name = 'Non-Color'
        tex_n = nodes.new(type='ShaderNodeTexImage')
        tex_n.image = img_n
        tex_n.location = (-400, -200)

        normal_map = nodes.new(type='ShaderNodeNormalMap')
        normal_map.location = (-200, -200)
        links.new(tex_n.outputs['Color'], normal_map.inputs['Color'])
        links.new(normal_map.outputs['Normal'], shader_node.inputs['Normal'])

    if base_mesh.data.materials:
        base_mesh.data.materials[0] = mat
    else:
        base_mesh.data.materials.append(mat)

    # 4. Normalization and Centering
    # Compute rest vertex world bounds or mesh bounds
    bpy.context.view_layer.update()
    import mathutils
    bbox_corners = [base_mesh.matrix_world @ mathutils.Vector(corner) for corner in base_mesh.bound_box]
    min_x = min(c.x for c in bbox_corners)
    max_x = max(c.x for c in bbox_corners)
    min_y = min(c.y for c in bbox_corners)
    max_y = max(c.y for c in bbox_corners)
    min_z = min(c.z for c in bbox_corners)
    max_z = max(c.z for c in bbox_corners)

    size_x = max_x - min_x
    size_y = max_y - min_y
    size_z = max_z - min_z
    log(f"Original dimensions: {size_x:.2f}m x {size_y:.2f}m x {size_z:.2f}m")

    canonical_height = 1.10
    scale_factor = canonical_height / size_z if size_z > 0 else 1.0
    log(f"Calculated scale factor for ~1.1m height: {scale_factor:.4f}")

    # Center rest-mesh X,Y and ground Z0 based on actual rest vertex world bounds
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    ground_z = min_z

    log(f"Centering offset: X={-center_x:.2f}, Y={-center_y:.2f}, Z={-ground_z:.2f}")

    # Create root object for uniform scale and offset
    root_empty = bpy.data.objects.new("FoxRoot", None)
    bpy.context.scene.collection.objects.link(root_empty)
    root_empty.scale = (1, 1, 1)
    root_empty.location = (-center_x * scale_factor, -center_y * scale_factor, -ground_z * scale_factor)

    # Apply scale to mesh and armature data
    base_mesh.data.transform(mathutils.Matrix.Scale(scale_factor, 4))
    base_armature.data.transform(mathutils.Matrix.Scale(scale_factor, 4))

    # Reparent base_armature to root_empty
    base_armature.parent = root_empty

    # Apply transforms or let parent handle it? The prompt says:
    # "Keep rig hierarchy intact, parent everything to uniform-scale root or set global export scale via parent (do not scale mesh only)."
    # Since base_armature is parented to root_empty, root_empty's scale and location will apply to the entire armature and mesh hierarchy.

    # 5. Import clips, extract actions, and set up NLA tracks
    if not base_armature.animation_data:
        base_armature.animation_data_create()

    nla_tracks = base_armature.animation_data.nla_tracks

    clip_summaries = {}

    for alias, fname in clips_def:
        fpath = os.path.join(input_dir, fname)
        log(f"Processing clip {alias} from {fname}")

        # Remember objects before import
        objs_before = set(bpy.context.scene.objects)

        bpy.ops.import_scene.fbx(filepath=fpath)

        objs_after = set(bpy.context.scene.objects)
        new_objs = objs_after - objs_before

        # Find imported armature/action
        clip_armature = None
        for obj in new_objs:
            if obj.type == 'ARMATURE':
                clip_armature = obj
                break

        if clip_armature and clip_armature.animation_data and clip_armature.animation_data.action:
            act = clip_armature.animation_data.action
            act.name = f"Fox_{alias}"
            act.use_fake_user = True

            # Blender 4.5 layered actions slot handling
            slot = None
            if hasattr(act, 'slots') and len(act.slots) > 0:
                slot = act.slots[0]

            # Assign action to base armature NLA track
            track = nla_tracks.new()
            track.name = alias
            
            # Create strip
            # strip = track.strips.new(alias, int(act.frame_range[0]), act)
            # In Blender python API for NLA strips:
            # track.strips.new(name, start, action)
            start_frame = int(act.frame_range[0])
            strip = track.strips.new(alias, start_frame, act)

            # --- Scale translation keyframes for all actions ---
            # Scale translation keyframes for direct action fcurves
            if act.fcurves:
                for fcurve in act.fcurves:
                    if fcurve.data_path.endswith('location'):
                        for keyframe in fcurve.keyframe_points:
                            keyframe.co[1] *= scale_factor
                            keyframe.handle_left[1] *= scale_factor
                            keyframe.handle_right[1] *= scale_factor


            if slot and hasattr(strip, 'action_slot'):
                try:
                    strip.action_slot = slot
                except Exception as e:
                    log(f"Could not assign action_slot for {alias}: {e}")

            clip_summaries[alias] = {
                "source": fname,
                "frames": [float(act.frame_range[0]), float(act.frame_range[1])]
            }
        else:
            log(f"Warning: No action found for clip {alias} in {fname}")

        # Remove only just-imported objects and unused duplicate data
        for obj in new_objs:
            bpy.data.objects.remove(obj, do_unlink=True)

    # Clean up orphaned meshes/armatures/materials from imports if any remain in bpy.data
    for m in list(bpy.data.meshes):
        if m.users == 0 and m != base_mesh.data:
            bpy.data.meshes.remove(m)
    for ar in list(bpy.data.armatures):
        if ar.users == 0 and ar != base_armature.data:
            bpy.data.armatures.remove(ar)

    # 6. Export GLB using valid properties for Blender 4.5
    log(f"Exporting GLB to {output_glb}")

    # Select only base rig/mesh/root, no duplicate objects or camera/light
    bpy.ops.object.select_all(action='DESELECT')
    root_empty.select_set(True)
    base_armature.select_set(True)
    base_mesh.select_set(True)
    bpy.context.view_layer.objects.active = root_empty

    # Get RNA type properties to filter optional keyword parameters for 4.5
    export_op = bpy.ops.export_scene.gltf
    rna_props = export_op.get_rna_type().properties

    export_kwargs = {
        "filepath": output_glb,
        "export_format": 'GLB',
        "use_selection": True,
        "export_yup": True,
        "export_animations": True,
        "export_animation_mode": 'NLA_TRACKS',
        "export_nla_strips": True,
        "export_anim_slide_to_zero": True,
        "export_force_sampling": True,
        "export_texcoords": True,
        "export_normals": True,
        "export_materials": 'EXPORT',
        "export_image_format": 'AUTO'
    }

    filtered_kwargs = {k: v for k, v in export_kwargs.items() if k in rna_props}
    log(f"Filtered export kwargs for Blender 4.5: {list(filtered_kwargs.keys())}")

    bpy.ops.export_scene.gltf(**filtered_kwargs)

    # 7. Write JSON summary
    summary = {
        "blender_version": bpy.app.version_string,
        "dimensions": {
            "original": [size_x, size_y, size_z],
            "normalized_height": canonical_height,
            "scale_factor": scale_factor
        },
        "clips": clip_summaries
    }

    with open(output_json, 'w', encoding='utf-8') as jf:
        json.dump(summary, jf, indent=2)

    log(f"Successfully generated {output_glb} and {output_json}")

if __name__ == "__main__":
    main()
