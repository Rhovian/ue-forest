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
# its surface is more than a few cm above the floor. The vertex offset sinks it by ScanSink cm, so only its stones and
# roots stand out. Near its edge (from RimStart of ScanRadius out from the pivot) what is still higher than RimLift cm
# above the floor height RVT is cut out, so the plate thins into the floor where the floor falls away under it: a hard,
# noisy edge (dithering read as a see-through ghost). The height RVT can't drape it instead: it reads empty in the
# vertex shader (no feedback there) and sank every scan. ScanRadius is set per instance from its mesh (main).
SCAN = {"ScanSink": 8.0, "ScanRadius": 150.0, "RimStart": 0.45, "RimLift": 4.0, "RimSoftness": 2.0}
RIM_NOISE_CM = 40.0  # feature size of the wander added to the edge, so the cut is not a circle
BRANCH = {"ScanSink": 3.0, "RimLift": 1000.0}  # the fallen branch scans lie on the floor whole: no rim cut
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
    zero = g.node(X.MaterialExpressionConstant, 2, r=0.0)
    sink = g.wire(X.MaterialExpressionAppendVector, 1, {
        "A": g.wire(X.MaterialExpressionAppendVector, 1, {"A": zero, "B": zero}),
        "B": g.wire(X.MaterialExpressionMultiply, 2, {"A": p["ScanSink"], "B": g.node(X.MaterialExpressionConstant, 3, r=-1.0)})})
    if not mel.connect_material_property(sink, "", MP.MP_WORLD_POSITION_OFFSET):
        raise SystemExit("could not connect the world position offset")
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    return material


def rim(g, p):
    """Opacity: 0 where a pixel is both near the scan's edge and more than RimLift above the floor height RVT."""
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
    lifted = g.wire(X.MaterialExpressionSmoothStep, 4, {
        "Min": p["RimLift"], "Max": g.wire(X.MaterialExpressionAdd, 5, {"A": p["RimLift"], "B": p["RimSoftness"]}),
        "Value": above})
    cut = g.wire(X.MaterialExpressionMultiply, 3, {"A": edge, "B": lifted})
    return g.wire(X.MaterialExpressionOneMinus, 2, {"": cut})


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
    material = build()
    only = set(sys.argv[1:])
    for path, radius in sorted(scan_instances().items()):
        if only and path.rsplit("/", 1)[1] not in only:
            continue
        instance = unreal.load_asset(path)
        mel.set_material_instance_parent(instance, material)
        # Drop earlier Scan overrides first (the texture overrides stay), so a value removed here does not linger.
        instance.set_editor_property("scalar_parameter_values", [
            v for v in instance.get_editor_property("scalar_parameter_values")
            if str(v.get_editor_property("parameter_info").get_editor_property("name")) not in SCAN])
        values = {"ScanRadius": radius, **(BRANCH if "OldTreeBranch" in path else {})}
        for name, value in values.items():
            mel.set_material_instance_scalar_parameter_value(instance, name, value)
        mel.update_material_instance(instance)
        unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
        print(f"reparented {path.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
