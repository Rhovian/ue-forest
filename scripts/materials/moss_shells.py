"""Bake a moss shell for each log, stump and slab host (#102): moss with real thickness, not only colour.

    scripts/editor-py scripts/materials/moss_shells.py

For each host in SHELLS, Geometry Script copies the mesh, keeps the faces within the host's angle of up, closes the
holes in that selection, remeshes it to EDGE, and pushes it out along its normals: THICK plus lumps of value noise
(LUMP, LUMP_CM), ramped up from slightly buried at the shell's edge (BURY) over TAPER, so it grows out of the bark
rather than sitting on it. The result is SM_<host>_MossShell (Nanite, no collision), in the host's own space, with
MI_<host>_MossShell: the host's coated material with moss forced everywhere (moss_coating.py). deadwood_rocks.py
places each shell as a child at its host's exact transform. Rerun after a host or setting changes, then
deadwood_rocks.py, exact_exclusions.py and regenerate_biome.py.
"""

import math
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
import biome_variants

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
# Host (biome_variants vendor path) -> faces within this many degrees of up get a shell. Slabs: their top only.
SHELLS = {path: 60.0 for path, _ in biome_variants.LOG_VARIANTS + biome_variants.STUMP_VARIANTS}
SHELLS[biome_variants.SLAB_VARIANTS[0][0]] = 35.0  # the limestone slab; the boulders are mossy scans already


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


def build(host, angle):
    mesh = G.DynamicMesh()
    lod = G.GeometryScriptMeshReadLOD()
    lod.set_editor_property("lod_type", G.GeometryScriptLODType.SOURCE_MODEL)
    mesh, outcome = G.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
        host, mesh, G.GeometryScriptCopyMeshFromAssetOptions(), lod)
    if outcome != G.GeometryScriptOutcomePins.SUCCESS:
        raise SystemExit(f"could not read {host.get_path_name()}")
    if mesh.get_triangle_count() > MAX_TRIS:
        mesh = G.GeometryScript_MeshSimplification.apply_simplify_to_triangle_count(
            mesh, MAX_TRIS, G.GeometryScriptSimplifyMeshOptions())
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

    path = shell_path(host)
    shell = unreal.load_asset(path)
    if shell is None:
        options = G.GeometryScriptCreateNewStaticMeshAssetOptions()
        options.set_editor_property("enable_collision", False)  # the walker steps on the host's hulls
        shell, outcome = G.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, path, options)
    else:  # write into the existing asset, so the deadwood child lists that reference it keep their reference
        lod = G.GeometryScriptMeshWriteLOD()
        _, outcome = G.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
            mesh, shell, G.GeometryScriptCopyMeshToAssetOptions(), lod)
    if outcome != G.GeometryScriptOutcomePins.SUCCESS:
        raise SystemExit(f"could not write {path}")
    # Nanite (docs/asset-budget.md) with the default shape preservation, like the logs and rocks it covers; the
    # create options' Nanite flag did not reach the asset.
    nanite = shell.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", True)
    shell.set_editor_property("nanite_settings", nanite)
    shell.set_material(0, material(host))
    unreal.EditorAssetLibrary.save_loaded_asset(shell, False)
    return shell, len(points)


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


for path, angle in SHELLS.items():
    host = unreal.load_asset(biome_variants.VENDOR + path)
    shell, vertices = build(host, angle)
    print(f"{shell.get_name()}: {vertices} vertices, faces within {angle:.0f} deg of up")
