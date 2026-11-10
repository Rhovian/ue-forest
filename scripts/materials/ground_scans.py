"""Give the Electric Dreams ground scans a master that blends them into the floor (#135).

    scripts/editor-py scripts/materials/ground_scans.py [MI name ...]

The ground scans (biome_variants.SCAN_VARIANTS) sat on the floor as slabs with hard rims (stop 2, rock_assembly;
operator 2026-11-09). Their Electric Dreams master is a Substrate material, and splicing moss_coating's MF_GroundBlend
into a copy of it crashed the editor three ways (#135 lead note). This builds M_GroundScan, a plain master with the
scans' own texture parameters (Albedo, Normal, DR: displacement in R, roughness in G) followed by MF_GroundBlend, and
reparents each scan's material instance to it, so their texture overrides carry over. Names limit it to those
instances (a trial). Run moss_coating.py first: it builds MF_GroundBlend.
"""

import sys
from pathlib import Path

import unreal
from matgraph import Graph, fresh_material, mel, sampler_for

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
import biome_variants

PATH = "/Game/ForestBiome/Moss/M_GroundScan"
GROUND = "/Game/ForestBiome/Moss/MF_GroundBlend"
DEFAULTS = {  # parameter -> default texture (virtual-streamed like the scans', so the sampler types match)
    "Albedo": "/Game/MSPresets/MSVTTextures/DefaultDiffuse",
    "Normal": "/Game/MSPresets/MSVTTextures/Placeholder_Normal",
    "DR": "/Game/Megascans/3D_Assets/ForestTerrain/T_ForestTerrain_01_DpR",
}
ROUGHNESS = (0.55, 1.0)  # the DR green channel mapped onto this range
RVT_HEIGHT = "/Game/ForestBiome/RVT/T_ForestHeightRVT"
# A scan is placed flat at one landscape point and stands on the floor as a plate with a rim (#135, stop 2): most of
# its surface is more than a few cm above the floor. sink_meshes lowers each scan mesh by SINK_CM, so only its stones
# and roots stand out; in the mesh, as a material vertex offset made the interior view's frame time unsteady. What is
# still higher above the floor height RVT than an allowance is cut out: CoreLift cm at the pivot, falling from RimStart
# of ScanRadius out to RimLift cm at the edge. So the plate thins into the floor where the floor falls away under it,
# also partway in (cutting only the outer ring left an overhang on a hump, #178 review): a hard, noisy edge (dithering
# read as a see-through ghost). ScanRadius is set per instance from its mesh (main).
SCAN = {"ScanRadius": 150.0, "RimStart": 0.15, "CoreLift": 45.0, "RimLift": 4.0, "RimSoftness": 2.0}
SINK_CM = 8.0
SINK_SHARE = 0.4  # at most this share of a mesh's height above its pivot, so a thin scan (ForestGround, 5 cm) stays
SINK_TOLERANCE_CM = 0.5  # a rewrite shifts the bounds slightly; closer than this counts as already sunk
SINK_TAG = "ForestScanSinkCm"  # metadata on each mesh: how far it is already sunk, so a rerun moves it only the difference
RIM_NOISE_CM = 40.0  # feature size of the wander added to the edge, so the cut is not a circle
RETIRED = ("ScanSink",)  # overrides of parameters this master no longer has, dropped from the instances
BRANCH = {"CoreLift": 1000.0, "RimLift": 1000.0}  # the fallen branch scans lie on the floor whole: no cut, not sunk
X, MP = unreal, unreal.MaterialProperty


def build():
    material = fresh_material(PATH)
    g = Graph(material)
    samples = {}
    for name, default in DEFAULTS.items():
        texture = unreal.load_asset(default)
        samples[name] = g.node(X.MaterialExpressionTextureSampleParameter2D, 3, parameter_name=name, texture=texture,
                               sampler_type=sampler_for(texture),
                               sampler_source=unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
    rough = g.wire(X.MaterialExpressionLinearInterpolate, 2, {
        "A": g.node(X.MaterialExpressionConstant, 3, r=ROUGHNESS[0]), "B": g.node(X.MaterialExpressionConstant, 3, r=ROUGHNESS[1]),
        "Alpha": g.mask(samples["DR"], 3, "g")})
    blend = g.node(X.MaterialExpressionMaterialFunctionCall, 1)
    blend.set_material_function(unreal.load_asset(GROUND))
    for pin, source in (("BaseColor", g.mask(samples["Albedo"], 2, "rgb")), ("Normal", samples["Normal"]),
                        ("Roughness", rough)):
        if not mel.connect_material_expressions(source, "", blend, pin):
            raise SystemExit(f"could not connect {pin}")
    for pin, prop in (("BaseColor", MP.MP_BASE_COLOR), ("Normal", MP.MP_NORMAL), ("Roughness", MP.MP_ROUGHNESS)):
        if not mel.connect_material_property(blend, pin, prop):
            raise SystemExit(f"could not connect {prop}")
    p = {name: g.node(X.MaterialExpressionScalarParameter, 7, parameter_name=name, default_value=value, group="Scan")
         for name, value in SCAN.items()}
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    if not mel.connect_material_property(rim(g, p), "", MP.MP_OPACITY_MASK):
        raise SystemExit("could not connect the opacity mask")
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    return material


def rim(g, p):
    """Opacity: 0 where a pixel is higher above the floor height RVT than the allowance at its distance out."""
    # Local position, as Object Position, Object Radius and Object Local Bounds are the whole grass component's.
    local = g.mask(g.node(X.MaterialExpressionLocalPosition, 8), 7, "rg")
    reach = g.wire(X.MaterialExpressionDivide, 6, {"A": g.wire(X.MaterialExpressionLength, 6, {"": local}),
                                                   "B": p["ScanRadius"]})
    outward = g.wire(X.MaterialExpressionAdd, 5, {"A": reach, "B": g.wire(X.MaterialExpressionMultiply, 5, {
        "A": g.noise(7, RIM_NOISE_CM), "B": g.node(X.MaterialExpressionConstant, 6, r=0.15)})})
    edge = g.wire(X.MaterialExpressionSmoothStep, 4, {"Min": p["RimStart"], "Max": g.node(
        X.MaterialExpressionConstant, 5, r=1.0), "Value": outward})
    ground = g.node(X.MaterialExpressionRuntimeVirtualTextureSample, 6, virtual_texture=unreal.load_asset(RVT_HEIGHT),
                    material_type=unreal.RuntimeVirtualTextureMaterialType.WORLD_HEIGHT)
    above = g.wire(X.MaterialExpressionSubtract, 5, {"A": g.mask(g.node(X.MaterialExpressionWorldPosition, 7), 6, "b"),
                                                     "B": (ground, "WorldHeight")})
    allowed = g.wire(X.MaterialExpressionLinearInterpolate, 4, {"A": p["CoreLift"], "B": p["RimLift"], "Alpha": edge})
    cut = g.wire(X.MaterialExpressionSmoothStep, 3, {
        "Min": allowed, "Max": g.wire(X.MaterialExpressionAdd, 4, {"A": allowed, "B": p["RimSoftness"]}),
        "Value": above})
    return g.wire(X.MaterialExpressionOneMinus, 2, {"": cut})


def sink_meshes(only=()):
    """Lower every non-branch scan mesh into the floor by SINK_CM, or less if thin (geometry, not a vertex offset).

    With names, only the meshes using those material instances (a trial)."""
    G = unreal.GeometryScript_AssetUtils
    for path, _ in biome_variants.SCAN_VARIANTS:
        if not path.startswith("/Game/Megascans/") or "OldTreeBranch" in path:
            continue
        mesh = unreal.load_asset(path)
        if only and not any(s.material_interface.get_name() in only for s in mesh.static_materials):
            continue
        done = float(unreal.EditorAssetLibrary.get_metadata_tag(mesh, SINK_TAG) or 0.0)
        sink = round(min(SINK_CM, SINK_SHARE * (mesh.get_bounding_box().max.z + done)), 1)
        if abs(done - sink) < SINK_TOLERANCE_CM:
            continue
        dynamic = unreal.DynamicMesh()
        _, outcome = G.copy_mesh_from_static_mesh(mesh, dynamic, unreal.GeometryScriptCopyMeshFromAssetOptions(),
                                                  unreal.GeometryScriptMeshReadLOD())
        if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
            raise SystemExit(f"could not read {path}")
        unreal.GeometryScript_MeshTransforms.translate_mesh(dynamic, unreal.Vector(0, 0, done - sink))
        options = unreal.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=False,
                                                              enable_recompute_tangents=False,
                                                              enable_remove_degenerates=False)
        _, outcome = G.copy_mesh_to_static_mesh(dynamic, mesh, options, unreal.GeometryScriptMeshWriteLOD())
        if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
            raise SystemExit(f"could not write {path}")
        unreal.EditorAssetLibrary.set_metadata_tag(mesh, SINK_TAG, str(sink))
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
        print(f"sank {path.rsplit('/', 1)[1]} to {sink:g} cm")


def scan_instances():
    """{material instance path: the larger half extent of its mesh's bounds (cm)} for every Electric Dreams scan."""
    found = {}
    for path, _ in biome_variants.SCAN_VARIANTS:
        if path.startswith("/Game/Megascans/"):
            mesh = unreal.load_asset(path)
            box = mesh.get_bounding_box()
            half = max(box.max.x - box.min.x, box.max.y - box.min.y) / 2
            for slot in mesh.static_materials:
                key = slot.material_interface.get_path_name().split(".")[0]
                found[key] = max(found.get(key, 0.0), half)
    return found


def main():
    only = set(sys.argv[1:])
    sink_meshes(only)
    material = build()
    for path, radius in sorted(scan_instances().items()):
        if only and path.rsplit("/", 1)[1] not in only:
            continue
        instance = unreal.load_asset(path)
        mel.set_material_instance_parent(instance, material)
        # Drop earlier Scan overrides first (the texture overrides stay), so a branch value no longer set does not linger.
        instance.set_editor_property("scalar_parameter_values", [
            v for v in instance.get_editor_property("scalar_parameter_values")
            if str(v.get_editor_property("parameter_info").get_editor_property("name")) not in (*SCAN, *RETIRED)])
        values = {"ScanRadius": radius, **(BRANCH if "OldTreeBranch" in path else {})}
        for name, value in values.items():
            mel.set_material_instance_scalar_parameter_value(instance, name, value)
        mel.update_material_instance(instance)
        unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
        print(f"reparented {path.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
