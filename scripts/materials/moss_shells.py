"""Bake a moss shell for each log, stump and slab host (#102): moss with real thickness, not only colour.

    scripts/editor-py scripts/materials/moss_shells.py

For each host in SHELLS, Geometry Script copies the mesh, keeps the faces within the host's angle of up, closes the
holes in that selection, remeshes it to EDGE, and pushes it out along its normals: THICK plus lumps of value noise
(LUMP, LUMP_CM), ramped up from slightly buried at the shell's edge (BURY) over TAPER, so it grows out of the bark
rather than sitting on it. The result is SM_<host>_MossShell (Nanite, no collision), in the host's own space, with
MI_<host>_MossShell: the host's coated material with moss forced everywhere (moss_coating.py). Moss tufts (#116) are
baked on as its second section. TUFTS_ONLY hosts (the mossy boulders, the beech root flares) get an
SM_<host>_MossShell of tufts alone. deadwood_rocks.py places each shell as a child at its host's exact transform, as do
veteran_trees.py and flare_moss.py for the trees. A rebuild drops the ivy trunk_ivy.py adds to some shells. Rerun after
a host or setting changes, then trunk_ivy.py, deadwood_rocks.py,
veteran_trees.py, flare_moss.py, shore_trees.py, exact_exclusions.py and regenerate_biome.py.
"""

import importlib
import math
import random
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
import biome_variants

# The editor keeps imported modules between runs: without a reload, a variant appended since the last run of any builder
# would get no shell here while deadwood_rocks.py (which reloads) places it (#110 review).
biome_variants = importlib.reload(biome_variants)

G = unreal
mel = unreal.MaterialEditingLibrary
FOLDER = "/Game/ForestBiome/MossShells"
EDGE = 3.0  # cm, remesh edge length
THICK = 8.0  # cm, base thickness
LUMP = 12.0  # cm, lump amplitude on top of THICK
LUMP_CM = 35.0  # lump feature size; a third of it adds finer detail
TAPER = 18.0  # cm from the shell's edge over which thickness ramps up
BURY = -0.8  # cm at the edge: sunk into the host, so no visible lip
CLOSE = 3  # selection grow/shrink steps that close holes in a scan's top faces
MAX_TRIS = 80000  # simplify a host's source above this before selecting
MOSS = {"MossAmount": 10.0, "SlopeLow": -1.0, "SlopeHigh": -0.9}  # coating overrides: moss on every shell face
# Moss tufts (#116): the Electric Dreams sample's small masked moss clumps, baked onto each shell as its second material
# section, as the sample paints them onto its hero logs and rocks: thousands of 1.5-5 cm clumps standing on the
# surface give the moss its volume and break the host's outline; without them the same log reads as tinted bark.
TUFTS = [f"/Game/Megascans/3D_Plants/CustomMoss/SM_CustomMoss_0{i}" for i in range(1, 6)]  # appendable variants
TUFT_MATERIAL = f"{FOLDER}/MI_MossTuft"  # the sample's tuft material, tinted to the coating's moss
TUFT_PARENT = "/Game/Megascans/3D_Plants/CustomMoss/MI_CustomMoss_01"
# Overrides on TUFT_PARENT: its tufts are a pale yellow-olive (an ochre random variation at full strength), which
# read as lichen against the coating's deep moss green (#124 review).
TUFT_TINT = {"Albedo Tint": (0.55, 0.7, 0.4, 1.0)}
TUFT_SCALARS = {"Random Color Variation Amount": 0.3}
# Tufts per m2 of the host's mossy faces (within its SHELLS angle plus TUFT_CREEP of up, where the coating puts moss):
# DENSITY times BASE everywhere, rising to 1 inside noise patches of PATCH_CM. Sampled by area on the host, not on the
# shell's vertices: a scan's shell is patchy along its top (wd1mbcvbw's is dense at the root end and thin mid-trunk), so
# per-vertex tufts left most of the coated bark smooth. A tuft under the shell is lifted onto it (TUFT_LIFT).
TUFT_DENSITY, TUFT_BASE, TUFT_PATCH_CM = 2000.0, 0.5, 40.0
TUFT_CREEP = 15.0  # deg below the shell's angle that tufts still creep down the sides
TUFT_LIFT = 30.0  # cm: a shell surface this far above a host point carries that point's tuft
TUFT_SCALE = (0.2, 0.45)  # of the 10-17 cm source clumps: 2-7.5 cm
TUFT_SINK = 1.0  # cm into the surface
# Host (biome_variants vendor path) -> faces within this many degrees of up get a shell. Slabs: their top only.
# Vendor paths only: a full /Game path (the Electric Dreams MossyTree) is a mossy scan already. The meadow's short log
# keeps its shell though it left the forest's logs.
SHELLS = {path: 60.0 for path, _ in biome_variants.LOG_VARIANTS + biome_variants.MEADOW_LOG_VARIANTS
          + biome_variants.STUMP_VARIANTS if not path.startswith("/Game/")}
SHELLS[biome_variants.SLAB_VARIANTS[0][0]] = 35.0  # the limestone slab; the boulders are mossy scans already
# Hosts that get tufts but no shell, as SM_<host>_MossShell all the same (deadwood_rocks.py places it, and
# flare_moss.py on the trees): full /Game path -> (faces within this many degrees of up, only below this many cm or
# None). The boulders are mossy scans already: tufts on their tops. The beech: on their root flares, the bark's
# up-facing faces within FLARE_CM of the pivot at the ground (nurse_log_01, rock_assembly_01).
FLARE_CM = 120.0
FLARE_TREES = [  # appendable: the Trees group's beech (DA_Forest_TreesAssets) and the veterans
    f"/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_{v}" for v in "ABCD"
] + [path for path, _ in biome_variants.VETERAN_VARIANTS]
TUFTS_ONLY = {biome_variants.VENDOR + path: (50.0, None) for path, _ in biome_variants.SLAB_VARIANTS[1:]}
# 70 deg (85 with TUFT_CREEP): the Megaplants beech's bases are near-vertical, so at 55 almost none of their bark
# qualified; add_tufts thins the tufts upward instead, so the collar has no hard top edge.
TUFTS_ONLY.update({path: (70.0, FLARE_CM) for path in FLARE_TREES})


def shell_path(host):
    return f"{FOLDER}/SM_{host.get_name()}_MossShell"


def noise(x, y, z):
    """Smooth value noise in [0, 1] (hashed lattice, smoothstep blend)."""
    def h(i, j, k):
        n = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791)
        n = (n << 13) ^ n
        return ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7FFFFFFF) / 0x7FFFFFFF

    i, j, k = math.floor(x), math.floor(y), math.floor(z)
    u, v, w = (t * t * (3 - 2 * t) for t in (x - i, y - j, z - k))

    def lerp(a, b, t):
        return a + (b - a) * t

    return lerp(lerp(lerp(h(i, j, k), h(i + 1, j, k), u), lerp(h(i, j + 1, k), h(i + 1, j + 1, k), u), v),
                lerp(lerp(h(i, j, k + 1), h(i + 1, j, k + 1), u), lerp(h(i, j + 1, k + 1), h(i + 1, j + 1, k + 1), u), v), w)


def edge_distance(points, boundary):
    """Distance from each point to the nearest boundary point, capped at TAPER (grid of TAPER-sized cells)."""
    grid = {}
    for b in boundary:
        grid.setdefault((b.x // TAPER, b.y // TAPER, b.z // TAPER), []).append(b)
    out = []
    for p in points:
        key, best = (p.x // TAPER, p.y // TAPER, p.z // TAPER), TAPER
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for b in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        best = min(best, math.dist((p.x, p.y, p.z), (b.x, b.y, b.z)))
        out.append(best)
    return out


def bark_slot(host):
    """The host's bark material slot: the Megaplants beech's Bark, the field beech's Trunk."""
    slots = host.get_editor_property("materials" if isinstance(host, unreal.SkeletalMesh) else "static_materials")
    for index, slot in enumerate(slots):
        if any(word in str(slot.get_editor_property("material_slot_name")) for word in ("Bark", "Trunk")):
            return index
    raise SystemExit(f"{host.get_path_name()}: no Bark or Trunk material slot")


def read(host, below=None):
    """The host's source mesh (only its bark's faces below `below` cm, if given), simplified to MAX_TRIS."""
    lod = G.GeometryScriptMeshReadLOD()
    if isinstance(host, unreal.SkeletalMesh):  # the Megaplants beech: their LOD 0
        mesh, outcome = G.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            host, G.DynamicMesh(), G.GeometryScriptCopyMeshFromAssetOptions(), lod)
    else:
        lod.set_editor_property("lod_type", G.GeometryScriptLODType.SOURCE_MODEL)
        mesh, outcome = G.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
            host, G.DynamicMesh(), G.GeometryScriptCopyMeshFromAssetOptions(), lod)
    if outcome != G.GeometryScriptOutcomePins.SUCCESS:
        raise SystemExit(f"could not read {host.get_path_name()}")
    if below is not None:  # the bark below `below`: everything else goes before simplifying
        selection_api = G.GeometryScript_MeshSelection
        box = unreal.Box(unreal.Vector(-1e6, -1e6, -1e6), unreal.Vector(1e6, 1e6, below))
        mesh, high = selection_api.select_mesh_elements_in_box(
            mesh, box, G.GeometryScriptMeshSelectionType.TRIANGLES, True, 3)  # not all three corners below
        mesh, _ = G.GeometryScript_MeshEdits.delete_selected_triangles_from_mesh(mesh, high, True)
        mesh, bark = selection_api.select_mesh_elements_by_material_id(
            mesh, bark_slot(host), G.GeometryScriptMeshSelectionType.TRIANGLES)
        mesh, rest = selection_api.invert_mesh_selection(mesh, bark, True)
        mesh, _ = G.GeometryScript_MeshEdits.delete_selected_triangles_from_mesh(mesh, rest, True)
    if mesh.get_triangle_count() > MAX_TRIS:
        mesh = G.GeometryScript_MeshSimplification.apply_simplify_to_triangle_count(
            mesh, MAX_TRIS, G.GeometryScriptSimplifyMeshOptions())
    return mesh


def build(host, angle):
    mesh = read(host)
    selection_api = G.GeometryScript_MeshSelection
    mesh, top = selection_api.select_mesh_elements_by_normal_angle(
        mesh, unreal.Vector(0, 0, 1), angle, G.GeometryScriptMeshSelectionType.TRIANGLES, False, 1)
    for shrink in (False, True):
        mesh, top = selection_api.expand_contract_mesh_selection(mesh, top, CLOSE, shrink, False)
    mesh, rest = selection_api.invert_mesh_selection(mesh, top, True)
    mesh, _ = G.GeometryScript_MeshEdits.delete_selected_triangles_from_mesh(mesh, rest, True)
    uniform = G.GeometryScriptUniformRemeshOptions()
    uniform.set_editor_property("target_type", G.GeometryScriptUniformRemeshTargetType.TARGET_EDGE_LENGTH)
    uniform.set_editor_property("target_edge_length", EDGE)
    mesh = G.GeometryScript_Remeshing.apply_uniform_remesh(mesh, G.GeometryScriptRemeshOptions(), uniform)
    mesh = G.GeometryScript_Normals.recompute_normals(mesh, G.GeometryScriptCalculateNormalsOptions())

    to_array = G.GeometryScript_List.convert_vector_list_to_array
    points = list(to_array(G.GeometryScript_MeshQueries.get_all_vertex_positions(mesh, False)[1]))
    normals = list(to_array(G.GeometryScript_Normals.get_mesh_per_vertex_normals(mesh, True)[1]))
    mesh, edges = selection_api.select_mesh_boundary_edges(mesh)
    mesh, edge_vertices = selection_api.convert_mesh_selection(mesh, edges, G.GeometryScriptMeshSelectionType.VERTICES, True)
    boundary = [points[i] for i in selection_api.convert_mesh_selection_to_index_array(mesh, edge_vertices)[1]]
    offsets = []
    for p, n, d in zip(points, normals, edge_distance(points, boundary)):
        t = d / TAPER
        t = t * t * (3 - 2 * t)
        lump = 0.7 * noise(p.x / LUMP_CM, p.y / LUMP_CM, p.z / LUMP_CM) + 0.3 * noise(
            3 * p.x / LUMP_CM, 3 * p.y / LUMP_CM, 3 * p.z / LUMP_CM)
        amount = BURY + (THICK + LUMP * lump - BURY) * t
        offsets.append(unreal.Vector(n.x * amount, n.y * amount, n.z * amount))
    mesh, everything = selection_api.create_select_all_mesh_selection(mesh, G.GeometryScriptMeshSelectionType.VERTICES)
    mesh = G.GeometryScript_MeshDeformers.apply_displace_from_per_vertex_vectors(
        mesh, everything, G.GeometryScript_List.convert_array_to_vector_list(offsets), 1.0)
    smoothing = G.GeometryScriptIterativeMeshSmoothingOptions()
    smoothing.set_editor_property("num_iterations", 3)
    smoothing.set_editor_property("alpha", 0.3)
    mesh = G.GeometryScript_MeshDeformers.apply_iterative_smoothing_to_mesh(mesh, everything, smoothing)
    mesh = G.GeometryScript_Normals.recompute_normals(mesh, G.GeometryScriptCalculateNormalsOptions())
    mesh = G.GeometryScript_UVs.set_mesh_u_vs_from_box_projection(
        mesh, 0, unreal.Transform(scale=unreal.Vector(100, 100, 100)), everything, 2)  # UVs in metres, like the coating
    tufts = add_tufts(host, angle, mesh)
    return write(host, mesh, [material(host), tuft_material()], ["Shell", "Tufts"]), len(points), tufts


def build_tufts(host, angle, below):
    """SM_<host>_MossShell holding only tufts, on the host's faces within `angle` of up (below `below` cm, if given)."""
    mesh = G.DynamicMesh()
    tufts = add_tufts(host, angle, mesh, below, 0)
    return write(host, mesh, [tuft_material()], ["Tufts"]), 0, tufts


def write(host, mesh, materials, slots):
    """Write `mesh` into SM_<host>_MossShell with `materials` in `slots`, Nanite, saved."""
    path = shell_path(host)
    shell = unreal.load_asset(path)
    if shell is None:
        options = G.GeometryScriptCreateNewStaticMeshAssetOptions()
        options.set_editor_property("enable_collision", False)  # the walker steps on the host's hulls
        shell, outcome = G.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, path, options)
        if outcome != G.GeometryScriptOutcomePins.SUCCESS:
            raise SystemExit(f"could not create {path}")
    # Write (again) into the asset with both sections' materials; an existing asset is written in place, so the deadwood
    # child lists that reference it keep their reference.
    options = G.GeometryScriptCopyMeshToAssetOptions()
    options.set_editor_property("replace_materials", True)
    options.set_editor_property("new_materials", materials)
    options.set_editor_property("new_material_slot_names", slots)
    _, outcome = G.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(mesh, shell, options, G.GeometryScriptMeshWriteLOD())
    if outcome != G.GeometryScriptOutcomePins.SUCCESS:
        raise SystemExit(f"could not write {path}")
    # Nanite (docs/asset-budget.md) with the default shape preservation, like the logs and rocks it covers; the
    # create options' Nanite flag did not reach the asset.
    nanite = shell.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", True)
    shell.set_editor_property("nanite_settings", nanite)
    unreal.EditorAssetLibrary.save_loaded_asset(shell, False)
    return shell


def add_tufts(host, angle, shell, below=None, material_id=1):
    """Append moss tufts to the finished `shell` (possibly empty) as `material_id`; returns how many."""
    mesh = read(host, below)
    lift = shell.get_triangle_count() > 0
    if lift:
        _, bvh = G.GeometryScript_MeshSpatial.build_bvh_for_mesh(shell)
    queries = G.GeometryScript_MeshQueries
    rng = random.Random(host.get_name())  # the same tufts on every rebuild
    up = math.cos(math.radians(angle + TUFT_CREEP))
    placed = [[] for _ in TUFTS]
    for triangle in G.GeometryScript_List.convert_index_list_to_array(queries.get_all_triangle_i_ds(mesh)[1]):
        normal, valid = queries.get_triangle_face_normal(mesh, triangle)
        if not valid or normal.z < up:
            continue
        a, b, c = (x for x in queries.get_triangle_positions(mesh, triangle) if isinstance(x, unreal.Vector))
        ab, ac = b - a, c - a
        area = ab.cross(ac).length() / 2 / 10000  # m2
        expected = area * TUFT_DENSITY
        for _ in range(int(expected + rng.random())):
            u, v = rng.random(), rng.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = a + ab * u + ac * v
            patch = noise(p.x / TUFT_PATCH_CM + 17, p.y / TUFT_PATCH_CM, p.z / TUFT_PATCH_CM)
            t = min(1.0, max(0.0, (patch - 0.45) / 0.25))
            # Below a height limit (root flares) the tufts thin out upward to none at it: no hard top edge.
            fade = 1.0 if below is None else max(0.0, 1 - p.z / below) ** 1.5
            if rng.random() >= (TUFT_BASE + (1 - TUFT_BASE) * t * t * (3 - 2 * t)) * fade:
                continue
            surface = normal
            if lift:
                _, found, outcome = G.GeometryScript_MeshSpatial.find_nearest_ray_intersection_with_mesh(
                    shell, bvh, p - normal * 2, normal, G.GeometryScriptSpatialQueryOptions())
                if outcome == G.GeometryScriptSearchOutcomePins.FOUND and found.hit and found.ray_parameter < TUFT_LIFT:
                    # Lifted onto the shell: stand on, and sink into, the shell face it lands on, not the bark below
                    # it (a flat bark face under a mound's flank would leave the tuft upright on a slope; #124 review).
                    p = found.hit_position
                    shell_normal, valid = queries.get_triangle_face_normal(shell, found.hit_triangle_id)
                    if valid:
                        surface = shell_normal
            side = unreal.Vector(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))  # random yaw about the normal
            rotation = unreal.MathLibrary.make_rot_from_zx(surface, side)
            scale = rng.uniform(*TUFT_SCALE)
            placed[rng.randrange(len(TUFTS))].append(
                unreal.Transform(p - surface * TUFT_SINK, rotation, unreal.Vector(scale, scale, scale)))
    tufts = G.DynamicMesh()
    for path, transforms in zip(TUFTS, placed):
        if transforms:
            source, outcome = G.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
                unreal.load_asset(path), G.DynamicMesh(), G.GeometryScriptCopyMeshFromAssetOptions(),
                G.GeometryScriptMeshReadLOD())
            if outcome != G.GeometryScriptOutcomePins.SUCCESS:
                raise SystemExit(f"could not read {path}")
            tufts = G.GeometryScript_MeshEdits.append_mesh_transformed(tufts, source, transforms, unreal.Transform())
    if material_id:
        tufts = G.GeometryScript_Materials.remap_material_i_ds(tufts, 0, material_id)
    G.GeometryScript_MeshEdits.append_mesh(shell, tufts, unreal.Transform())
    return sum(len(t) for t in placed)


def tuft_material():
    """MI_MossTuft: the sample's tuft material with TUFT_TINT. The sample's master defaults four texture parameters to
    palm textures that every instance here overrides; pointing them at the moss's own keeps 37 MB of palm out."""
    parent = unreal.load_asset(TUFT_PARENT)
    moss = {str(p.parameter_info.name): p.parameter_value for p in parent.get_editor_property("texture_parameter_values")}
    master = parent.get_base_material()
    repointed = False
    for expression in mel.get_material_expressions(master):
        if isinstance(expression, unreal.MaterialExpressionTextureSampleParameter):
            texture, wanted = expression.get_editor_property("texture"), moss.get(str(expression.get_editor_property("parameter_name")))
            if texture and wanted and "/3D_Plants/CustomMoss/" not in texture.get_path_name() and texture != wanted:
                expression.set_editor_property("texture", wanted)
                repointed = True
    if repointed:
        mel.recompile_material(master)
        unreal.EditorAssetLibrary.save_loaded_asset(master, False)
    name = TUFT_MATERIAL.rsplit("/", 1)[1]
    instance = unreal.load_asset(TUFT_MATERIAL) or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(instance, parent)
    for parameter, value in TUFT_TINT.items():
        mel.set_material_instance_vector_parameter_value(instance, parameter, unreal.LinearColor(*value))
    for parameter, value in TUFT_SCALARS.items():
        mel.set_material_instance_scalar_parameter_value(instance, parameter, value)
    unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    return instance


def material(host):
    """MI_<host>_MossShell: the host's (coated) first material, with moss on every face."""
    source = host.get_editor_property("static_materials")[0].get_editor_property("material_interface")
    name = f"MI_{host.get_name()}_MossShell"
    instance = unreal.load_asset(f"{FOLDER}/{name}") or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(instance, source)
    for parameter, value in MOSS.items():
        mel.set_material_instance_scalar_parameter_value(instance, parameter, value)
    unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    return instance


def main():
    for path, angle in SHELLS.items():
        host = unreal.load_asset(biome_variants.asset_path(path))
        shell, vertices, tufts = build(host, angle)
        print(f"{shell.get_name()}: {vertices} vertices, faces within {angle:.0f} deg of up; {tufts} tufts")
    for path, (angle, below) in TUFTS_ONLY.items():
        host = unreal.load_asset(path)
        shell, _, tufts = build_tufts(host, angle, below)
        print(f"{shell.get_name()}: tufts only, faces within {angle:.0f} deg of up" + (f" below {below:.0f} cm" if below else "")
              + f"; {tufts} tufts")


if __name__ == "__main__":  # trunk_ivy.py imports read() and noise()
    main()
