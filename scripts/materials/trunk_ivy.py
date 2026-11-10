"""Bake ivy up the lower trunks of biome_variants.IVY_TREES (#121, canopy_up_01: several trunks ivy-covered) and over
one corner of each IVY_SLABS slab (rock_assembly_01: ivy spilling over one corner).

    scripts/editor-py scripts/materials/trunk_ivy.py

For each tree, Geometry Script reads its bark below IVY_TOP (moss_shells.read) and scatters TRUNK_IVY_VARIANTS sheets
over its trunk's near-vertical faces (narrow strands, no branches): each sheet's back (-Y) against the bark, its up along the trunk, densest at the base and
thinning to none at IVY_TOP, in noisy vertical runs so the ivy climbs in strands rather than as an even sleeve. The
ivy is written into the host's moss shell as an "Ivy" section where it has one (so run this after moss_shells.py,
whose rebuild drops it), else into SM_<host>_Ivy (Nanite, no collision) in the host's own space, which
deadwood_rocks.shell_children places at the host's transform. A slab's ivy covers its top and sides within CORNER of its footprint's
+X+Y corner, sheets lying on the faces they cover. Rerun after a host or setting changes, then deadwood_rocks.py,
veteran_trees.py, flare_moss.py, hornbeam_trees.py, shore_trees.py, exact_exclusions.py and regenerate_biome.py.
"""

import importlib
import math
import random
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
import biome_variants
import moss_shells

biome_variants = importlib.reload(biome_variants)
moss_shells = importlib.reload(moss_shells)
G = unreal

FOLDER = "/Game/ForestBiome/Ivy"
# cm: ivy thins to none at this height. 12 m let ivy onto the branches of trees that sway (skinned beech, the hornbeam
# and veterans' wind offset) while the shell stays put, so it hung in the air (#156); the trunk moves least low down.
IVY_TOP = 700.0
TRUNK_REACH = 60.0  # cm from the trunk's axis (mesh space) that counts as trunk; branches lie further out
TRUNK_BAND = 100.0  # cm: the axis is followed up the trunk in bands this tall
CORNER = 0.45  # a slab's ivy reaches this share of the footprint's diagonal from its corner
DENSITY = 120.0  # strands per m2 of bark at the base: narrow strands need three times the 40 the wide sheets had (#156)
SLAB_DENSITY = 160.0  # sheets per m2 on a slab, where only its corner keeps them
MIN_CANDIDATES = 900  # at least this many candidate sheets per host: the slim Megaplants beech has 2.5 m2 of bark
VERTICAL = 0.5  # |normal.z| above this is a flare's top or a branch, not the trunk's side
RUN_CM = (60.0, 400.0)  # noise feature size around and along the trunk: narrow vertical runs
RUN_LOW, RUN_HIGH = 0.35, 0.55  # run noise: no ivy below RUN_LOW, full above RUN_HIGH
SCALE = (0.8, 1.4)  # slab sheets
TRUNK_SCALE = (0.6, 1.0)  # trunk strands: the tree's own scale (1.1-1.9) enlarges them again
SINK = 3.0  # cm into the bark


def trunk_only(faces):
    """The faces on the trunk itself: follow its axis up in TRUNK_BAND bands from the base (the bark centroid of the
    lowest band), each band's centre the mean of its faces within TRUNK_REACH of the band below's, and keep those
    faces. Ivy on branches hung in the air when the tree swayed (#156)."""
    bands = {}
    for face in faces:
        centre = face[1] + (face[2] + face[3]) / 3
        bands.setdefault(int(centre.z // TRUNK_BAND), []).append((face, centre))
    if not bands:
        return []
    kept = []
    low = min(bands)
    axis = None
    for band in range(low, max(bands) + 1):
        members = bands.get(band, [])
        near = [(f, c) for f, c in members if axis is None or math.hypot(c.x - axis[0], c.y - axis[1]) <= TRUNK_REACH]
        if not near:
            break  # the trunk ends, or is hidden: no ivy above a gap
        axis = (sum(c.x for _, c in near) / len(near), sum(c.y for _, c in near) / len(near))
        kept += [f for f, c in near if math.hypot(c.x - axis[0], c.y - axis[1]) <= TRUNK_REACH]
    return kept


def ivy_path(tree):
    return f"{FOLDER}/SM_{tree.get_name()}_Ivy"


def bake(tree, slab=False):
    """Ivy sheets over a tree's lower bark, or over a slab's corner; returns (mesh, count)."""
    bark = moss_shells.read(tree) if slab else moss_shells.read(tree, IVY_TOP)
    if slab:
        box = tree.get_bounding_box()
        corner = unreal.Vector(box.max.x, box.max.y, 0)
        reach = CORNER * math.hypot(box.max.x - box.min.x, box.max.y - box.min.y)
    queries = G.GeometryScript_MeshQueries
    rng = random.Random(tree.get_name())  # the same ivy on every rebuild
    variants = biome_variants.SLAB_IVY_VARIANTS if slab else biome_variants.TRUNK_IVY_VARIANTS
    weights = [w for _, w in variants]
    placed = [[] for _ in variants]
    triangles = G.GeometryScript_List.convert_index_list_to_array(queries.get_all_triangle_i_ds(bark)[1])
    faces = []
    for triangle in triangles:
        normal, valid = queries.get_triangle_face_normal(bark, triangle)
        if not valid or (normal.z < -VERTICAL if slab else abs(normal.z) > VERTICAL):
            continue
        a, b, c = (x for x in queries.get_triangle_positions(bark, triangle) if isinstance(x, unreal.Vector))
        faces.append((normal, a, b - a, c - a, (b - a).cross(c - a).length() / 2 / 10000))  # m2
    if not slab:
        faces = trunk_only(faces)
    density = max(SLAB_DENSITY if slab else DENSITY, MIN_CANDIDATES / max(sum(f[4] for f in faces), 0.01))
    for normal, a, ab, ac, area in faces:
        for _ in range(int(area * density + rng.random())):
            u, v = rng.random(), rng.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = a + ab * u + ac * v
            if slab:  # densest at the corner, thinning to none at `reach` from it
                keep = max(0.0, 1 - math.hypot(p.x - corner.x, p.y - corner.y) / reach) ** 0.7
                outward = normal
                lying = abs(normal.z) > 0.7
                up = unreal.Vector(rng.uniform(-1, 1), rng.uniform(-1, 1), 0) if lying else unreal.Vector(0, 0, -1)  # draped down the sides
            else:
                around = math.atan2(p.y, p.x) * 100 / RUN_CM[0]  # ~1 unit per RUN_CM of girth on a 1 m trunk
                run = moss_shells.noise(around + 31, p.z / RUN_CM[1], 7.0)
                t = min(1.0, max(0.0, (run - RUN_LOW) / (RUN_HIGH - RUN_LOW)))
                keep = t * t * (3 - 2 * t) * max(0.0, 1 - p.z / IVY_TOP) ** 1.2
                outward = unreal.Vector(normal.x, normal.y, 0).normal()
                up = unreal.Vector(rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 1)
            if rng.random() >= keep:
                continue
            rotation = unreal.MathLibrary.make_rot_from_yz(outward, up)  # leaves (+Y) out from the surface
            scale = rng.uniform(*(SCALE if slab else TRUNK_SCALE))
            index = rng.choices(range(len(variants)), weights)[0]
            placed[index].append(unreal.Transform(p - outward * SINK, rotation, unreal.Vector(scale, scale, scale)))
    ivy = G.DynamicMesh()
    for (path, _), transforms in zip(variants, placed):
        if transforms:
            source, outcome = G.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
                unreal.load_asset(path), G.DynamicMesh(), G.GeometryScriptCopyMeshFromAssetOptions(),
                G.GeometryScriptMeshReadLOD())
            if outcome != G.GeometryScriptOutcomePins.SUCCESS:
                raise SystemExit(f"could not read {path}")
            ivy = G.GeometryScript_MeshEdits.append_mesh_transformed(ivy, source, transforms, unreal.Transform())
    return ivy, sum(len(t) for t in placed)


def write(host, mesh):
    """Into the host's moss shell as an "Ivy" section where it has one (moss_shells.py), so the ivy costs no child of its
    own: a second child on a quarter of the beech pushed regenerate past its 60 GB limit (#121). Otherwise into
    SM_<host>_Ivy. A rebuild replaces the shell's previous ivy section."""
    material = unreal.load_asset(biome_variants.TRUNK_IVY_VARIANTS[0][0]).get_material(0)  # the sheets share one MI
    shell = unreal.load_asset(moss_shells.shell_path(host))
    if shell is not None:
        old = unreal.load_asset(ivy_path(host))
        if old is not None:  # a standalone ivy from before the host had a shell
            unreal.EditorAssetLibrary.delete_asset(old.get_path_name())
        lod = G.GeometryScriptMeshReadLOD()
        lod.set_editor_property("lod_type", G.GeometryScriptLODType.SOURCE_MODEL)
        base, outcome = G.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
            shell, G.DynamicMesh(), G.GeometryScriptCopyMeshFromAssetOptions(), lod)
        if outcome != G.GeometryScriptOutcomePins.SUCCESS:
            raise SystemExit(f"could not read {shell.get_path_name()}")
        slots = [str(s.get_editor_property("material_slot_name")) for s in shell.get_editor_property("static_materials")]
        materials = [s.get_editor_property("material_interface") for s in shell.get_editor_property("static_materials")]
        if "Ivy" in slots:
            base, previous = G.GeometryScript_MeshSelection.select_mesh_elements_by_material_id(
                base, slots.index("Ivy"), G.GeometryScriptMeshSelectionType.TRIANGLES)
            base, _ = G.GeometryScript_MeshEdits.delete_selected_triangles_from_mesh(base, previous, True)
        else:
            slots, materials = slots + ["Ivy"], materials + [material]
        mesh = G.GeometryScript_Materials.remap_material_i_ds(mesh, 0, slots.index("Ivy"))
        G.GeometryScript_MeshEdits.append_mesh(base, mesh, unreal.Transform())
        asset, mesh = shell, base
    else:
        slots, materials = ["Ivy"], [material]
        path = ivy_path(host)
        asset = unreal.load_asset(path)
        if asset is None:
            options = G.GeometryScriptCreateNewStaticMeshAssetOptions()
            options.set_editor_property("enable_collision", False)
            asset, outcome = G.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, path, options)
            if outcome != G.GeometryScriptOutcomePins.SUCCESS:
                raise SystemExit(f"could not create {path}")
    options = G.GeometryScriptCopyMeshToAssetOptions()
    options.set_editor_property("replace_materials", True)
    options.set_editor_property("new_materials", materials)
    options.set_editor_property("new_material_slot_names", slots)
    _, outcome = G.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(mesh, asset, options, G.GeometryScriptMeshWriteLOD())
    if outcome != G.GeometryScriptOutcomePins.SUCCESS:
        raise SystemExit(f"could not write {asset.get_path_name()}")
    nanite = asset.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", True)
    asset.set_editor_property("nanite_settings", nanite)
    unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
    return asset


def main():
    for path, slab in [(p, False) for p in biome_variants.IVY_TREES] + [(p, True) for p in biome_variants.IVY_SLABS]:
        host = unreal.load_asset(path)
        if host is None:
            raise SystemExit(f"missing ivy host {path}")
        mesh, count = bake(host, slab)
        if not count:
            raise SystemExit(f"{host.get_name()}: no ivy placed; check its bark slot, IVY_TOP and CORNER")
        asset = write(host, mesh)
        print(f"{asset.get_name()}: {count} ivy sheets" + (" over one corner" if slab else f" below {IVY_TOP:.0f} cm"))


main()
