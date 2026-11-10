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
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    return material


def scan_instances():
    """The material instances of every Electric Dreams ground scan."""
    found = set()
    for path, _ in biome_variants.SCAN_VARIANTS:
        if path.startswith("/Game/Megascans/"):
            for slot in unreal.load_asset(path).static_materials:
                found.add(slot.material_interface.get_path_name().split(".")[0])
    return sorted(found)


def main():
    material = build()
    only = set(sys.argv[1:])
    for path in scan_instances():
        if only and path.rsplit("/", 1)[1] not in only:
            continue
        instance = unreal.load_asset(path)
        mel.set_material_instance_parent(instance, material)
        mel.update_material_instance(instance)
        unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
        print(f"reparented {path.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
