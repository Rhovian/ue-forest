"""Build the Forest Biome's procedural landscape material.

    scripts/editor-py scripts/materials/forest_floor.py [--assign]

Rebuilds /Game/ForestBiome/M_ForestFloor from scratch (no painted layers) and keeps MI_ForestFloor as its
tuning instance: sand below the shore height, darker and glossier at the waterline; mossy floor on low,
flat (damp) ground, broken up by the moss-patch mask; dry leaf litter everywhere else. Thresholds are
material parameters, so instance overrides survive a rebuild. --assign sets the instance on every
Landscape actor in the open level (streaming proxies inherit it).
"""

import sys

import unreal

FOLDER = "/Game/ForestBiome"
FAB = "/Game/Fab/Megascans"
LAYERS = {  # layer -> (texture prefix, tile size in cm)
    "Sand": (f"{FAB}/Surfaces/Rocky_Sand_vmkecjj/Medium/vmkecjj_tier_2/Textures/T_vmkecjj_2K", 300.0),
    "Moss": (f"{FAB}/Surfaces/Mossy_Forest_Floor_vfylbge/Medium/vfylbge_tier_2/Textures/T_vfylbge_2K", 400.0),
    "Leaves": (f"{FAB}/Surfaces/Dry_Fallen_Leaves_vetladiaw/Medium/vetladiaw_tier_2/Textures/T_vetladiaw_2K", 300.0),
}
PATCHES = f"{FAB}/Decals/Tileable_Moss_Patches_sfdnqii/Medium/sfdnqii_tier_2/Textures/T_sfdnqii_2K_B-O"
SCALARS = {  # world units are cm; sea level is Z 0
    "ShoreHeight": 150.0,  # sand below, forest floor above
    "ShoreBlend": 60.0,
    "WetBandTop": 40.0,  # sand is fully wet below this, fully dry at ShoreHeight
    "WetDarkening": 0.6,
    "DryBrightening": 1.25,
    "WetRoughness": 0.45,  # multiplies sand roughness at the waterline
    "DampLow": 300.0,  # ground below DampLow counts as damp, above DampHigh as dry
    "DampHigh": 1200.0,
    "FlatLow": 0.85,  # vertex normal Z: steeper than FlatLow is never mossy
    "FlatHigh": 0.97,
    "PatchTile": 800.0,
    "PatchStrength": 0.6,
}

mel = unreal.MaterialEditingLibrary


def texture(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise SystemExit(f"missing texture {path}")
    return asset


def sampler_for(tex):
    """The sampler type Unreal requires for the texture's compression and colour space."""
    compression = tex.get_editor_property("compression_settings")
    srgb = tex.get_editor_property("srgb")
    TC, ST = unreal.TextureCompressionSettings, unreal.MaterialSamplerType
    if compression == TC.TC_NORMALMAP:
        return ST.SAMPLERTYPE_NORMAL
    if compression == TC.TC_MASKS:
        return ST.SAMPLERTYPE_MASKS
    if compression in (TC.TC_GRAYSCALE, TC.TC_ALPHA, TC.TC_DISPLACEMENTMAP):
        return ST.SAMPLERTYPE_GRAYSCALE if srgb else ST.SAMPLERTYPE_LINEAR_GRAYSCALE
    return ST.SAMPLERTYPE_COLOR if srgb else ST.SAMPLERTYPE_LINEAR_COLOR


class Graph:
    def __init__(self, material):
        self.material = material
        self.row = 0

    def node(self, cls, column, **props):
        self.row += 1
        expression = mel.create_material_expression(self.material, cls, -300 * column, 80 * self.row)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def wire(self, cls, column, inputs, **props):
        """Create a node and connect inputs: {input pin: expression or (expression, output pin)}."""
        expression = self.node(cls, column, **props)
        for pin, source in inputs.items():
            src, out = source if isinstance(source, tuple) else (source, "")
            mel.connect_material_expressions(src, out, expression, pin)
        return expression

    def mask(self, source, column, channels):
        flags = {c: c in channels for c in "rgba"}
        return self.wire(unreal.MaterialExpressionComponentMask, column, {"": source}, **flags)

    def sample(self, path, uv, column):
        tex = texture(path)
        return self.wire(
            unreal.MaterialExpressionTextureSample, column, {"UVs": uv}, texture=tex, sampler_type=sampler_for(tex)
        )


def build():
    path = f"{FOLDER}/M_ForestFloor"
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = unreal.load_asset(path) or tools.create_asset(
        "M_ForestFloor", FOLDER, unreal.Material, unreal.MaterialFactoryNew()
    )
    # delete_all_material_expressions skips about half the nodes (it deletes while iterating), so delete one by one.
    for expression in list(mel.get_material_expressions(material)):
        mel.delete_material_expression(material, expression)
    if mel.get_num_material_expressions(material):
        raise SystemExit(f"{path}: could not clear the old graph")
    g = Graph(material)
    P = unreal.MaterialExpressionScalarParameter
    p = {name: g.node(P, 9, parameter_name=name, default_value=value) for name, value in SCALARS.items()}

    world = g.node(unreal.MaterialExpressionWorldPosition, 9)
    xy, z = g.mask(world, 8, "rg"), g.mask(world, 8, "b")
    nz = g.mask(g.node(unreal.MaterialExpressionVertexNormalWS, 9), 8, "b")

    # Sand below the shore; moss on low flat ground plus patches; leaves elsewhere.
    shore_min = g.wire(unreal.MaterialExpressionSubtract, 7, {"A": p["ShoreHeight"], "B": p["ShoreBlend"]})
    shore_max = g.wire(unreal.MaterialExpressionAdd, 7, {"A": p["ShoreHeight"], "B": p["ShoreBlend"]})
    above = g.wire(unreal.MaterialExpressionSmoothStep, 6, {"Min": shore_min, "Max": shore_max, "Value": z})
    sand_mask = g.wire(unreal.MaterialExpressionOneMinus, 5, {"": above})
    flat = g.wire(unreal.MaterialExpressionSmoothStep, 6, {"Min": p["FlatLow"], "Max": p["FlatHigh"], "Value": nz})
    high = g.wire(unreal.MaterialExpressionSmoothStep, 6, {"Min": p["DampLow"], "Max": p["DampHigh"], "Value": z})
    damp = g.wire(
        unreal.MaterialExpressionMultiply, 5, {"A": flat, "B": g.wire(unreal.MaterialExpressionOneMinus, 5, {"": high})}
    )
    patch_uv = g.wire(unreal.MaterialExpressionDivide, 6, {"A": xy, "B": p["PatchTile"]})
    patches = g.sample(PATCHES, patch_uv, 5)
    patch = g.wire(unreal.MaterialExpressionMultiply, 4, {"A": (patches, "A"), "B": p["PatchStrength"]})
    moss_mask = g.wire(
        unreal.MaterialExpressionSaturate, 3, {"": g.wire(unreal.MaterialExpressionAdd, 4, {"A": damp, "B": patch})}
    )
    dryness = g.wire(
        unreal.MaterialExpressionSmoothStep, 6, {"Min": p["WetBandTop"], "Max": p["ShoreHeight"], "Value": z}
    )
    lerp = unreal.MaterialExpressionLinearInterpolate
    tint = g.wire(lerp, 5, {"A": p["WetDarkening"], "B": p["DryBrightening"], "Alpha": dryness})
    wet_rough = g.wire(
        lerp, 5, {"A": p["WetRoughness"], "B": g.node(unreal.MaterialExpressionConstant, 6, r=1.0), "Alpha": dryness}
    )

    sets = {}
    for name, (prefix, tile) in LAYERS.items():
        size = g.node(P, 7, parameter_name=f"{name}Tile", default_value=tile)
        uv = g.wire(unreal.MaterialExpressionDivide, 6, {"A": xy, "B": size})
        sets[name] = {kind: g.sample(f"{prefix}_{kind}", uv, 4) for kind in ("B", "N", "ORM")}

    def blend(sand, kind, column=2):
        floor = g.wire(lerp, column, {"A": sets["Leaves"][kind], "B": sets["Moss"][kind], "Alpha": moss_mask})
        return g.wire(lerp, column - 1, {"A": floor, "B": sand, "Alpha": sand_mask})

    color = blend(g.wire(unreal.MaterialExpressionMultiply, 3, {"A": sets["Sand"]["B"], "B": tint}), "B")
    normal = blend(sets["Sand"]["N"], "N")
    orm = blend(sets["Sand"]["ORM"], "ORM")
    sand_rough = g.wire(unreal.MaterialExpressionMultiply, 3, {"A": (sets["Sand"]["ORM"], "G"), "B": wet_rough})
    floor_rough = g.wire(
        lerp, 2, {"A": (sets["Leaves"]["ORM"], "G"), "B": (sets["Moss"]["ORM"], "G"), "Alpha": moss_mask}
    )
    rough = g.wire(lerp, 1, {"A": floor_rough, "B": sand_rough, "Alpha": sand_mask})

    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(normal, "", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(g.mask(orm, 0, "r"), "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)

    instance = unreal.load_asset(f"{FOLDER}/MI_ForestFloor") or tools.create_asset(
        "MI_ForestFloor", FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    mel.set_material_instance_parent(instance, material)
    unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    print(f"{path}: {mel.get_num_material_expressions(material)} expressions; MI_ForestFloor ready")
    return instance


instance = build()
if "--assign" in sys.argv[1:]:
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    landscapes = [a for a in actors if type(a) is unreal.Landscape]
    for landscape in landscapes:
        landscape.set_editor_property("landscape_material", instance)
    print(f"assigned to {len(landscapes)} landscape(s)")
