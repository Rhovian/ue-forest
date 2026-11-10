"""Build the shared moss coating (#34; decisions in docs/research/moss-techniques.md) and apply it.

    scripts/editor-py scripts/materials/moss_coating.py

MF_MossCoating blends moss over a surface's colour, normal and roughness. Each coated master is a copy of the stock
master with the function spliced in front of its outputs, and each coated instance is reparented to that copy, so
its texture overrides carry over. Static meshes take "up" from the world; skinned trees from the rest pose, so
moss does not swim in the wind.
"""
# editor-py: fresh-siblings

import unreal
from matgraph import (
    ED_SURFACE,
    FLOOR_DETAIL_SCALE,
    FLOOR_MACRO_BRIGHTNESS,
    FLOOR_MACRO_NOISE_CM,
    FLOOR_MOSS,
    FLOOR_MOSS_TINT,
    FLOOR_VARIANT,
    FLOOR_VARIANT_NOISE_CM,
    FLOOR_VARIETY,
    MOSS_TINT,
    Graph,
    mel,
)

FOLDER = "/Game/ForestBiome/Moss"
FAB = "/Game/Fab/Megascans"
MOSS = f"{FAB}/Surfaces/Mossy_Forest_Floor_vfylbge/Medium/vfylbge_tier_2/Textures/T_vfylbge_2K"
PATCHES = f"{FAB}/Decals/Tileable_Moss_Patches_sfdnqii/Medium/sfdnqii_tier_2/Textures/T_sfdnqii_2K_B-O"
SCALARS = {  # shared by every coated surface; distances in cm, UVs in metres
    "MossAmount": 1.6,  # 0 = bare
    "SlopeLow": 0.35,  # surface normal Z: moss starts on faces tilted up past SlopeLow, full at SlopeHigh
    "SlopeHigh": 0.75,
    "SlopeWeight": 1.0,
    # Trees: each climbs to its own height (#99; the same 90 cm band on every trunk read as a green sock). The
    # per-instance seed picks the height where moss starts to thin, between ClimbLow and ClimbHigh, and the fade above
    # it; EdgeRelief makes the edge ragged; the trunk side facing (SideX, SideY) climbs SideHeight higher and the far
    # side as much lower. Moss below ContactTop is always full, so every root flare joins the floor (interior_01).
    "ClimbLow": 90.0,
    "ClimbHigh": 230.0,
    # A 40-140 cm fade read as a square-cut sleeve over bare bark (dark_shade stop, operator 2026-11-09, #123):
    # the moss thins out over 1.2-3 m now, with a more ragged edge.
    "FadeLow": 120.0,
    "FadeHigh": 300.0,
    "EdgeRelief": 120.0,
    "EdgeTile": 0.35,  # ragged edge repeats every ~3 m of bark UV
    "SideHeight": 50.0,
    "SideX": -0.6,
    "SideY": 0.8,
    "ContactTop": 45.0,
    "BaseWeight": 1.0,
    "PatchTile": 0.5,  # breakup texture repeats every 2 m
    "PatchStrength": 0.6,
    "EdgeWidth": 0.15,
    "MossTile": 0.25,  # moss texture repeats every 4 m, as on the floor (MI_ForestFloor MossTile 400): one moss (#103)
}
# Ground blend on static meshes (#157, #166): near the floor, a surface takes on the floor's moss and soil patches
# (matgraph FLOOR_*, sampled in world space as the floor samples them), so rocks, slabs and logs sit in the ground rather
# than on it. The floor's height comes from its runtime virtual texture (ground_rvt.py). Fully the floor at the
# contact, fading out over GroundBlendHeight cm above it, with a ragged top edge.
GROUND = {
    "GroundBlend": 1.0,  # 0 = off
    "GroundBlendHeight": 30.0,
    "GroundJitter": 25.0,  # cm the edge's top wanders up: the contact itself is always fully the floor
}
NOISE_CM = 70.0  # feature size of that wander (a node property, not a parameter)
RVT_HEIGHT = "/Game/ForestBiome/RVT/T_ForestHeightRVT"
STATIC = "static"
TREE = "tree"
MASTERS = {  # stock master -> (coated copy, how it finds up)
    "/Game/Fab/Materials/Standard/M_MS_Base": ("M_MS_Base_Moss", STATIC),
    "/Game/Fab/Materials/Standard/M_MS_Base_Fuzz": ("M_MS_Base_Fuzz_Moss", STATIC),
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials/MA_Foliage_Trees": ("M_Foliage_Trees_Moss", TREE),
}
SLAB = {"SlopeLow": 0.75, "SlopeHigh": 0.92}  # faces within ~25-40 deg of up
BARE = {"MossAmount": 0.0}  # ground blend only
LOG = {"SlopeLow": -0.5, "SlopeHigh": 0.1}  # top and sides down past the middle: no pale side stripe (nurse_log_01, #71)
COATED = {  # instances that get the coating, with their overrides; one line per variant
    f"{FAB}/3D/Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/Materials/MI_wd1mbcvbw": LOG,
    f"{FAB}/3D/Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/Materials/MI_wgrubc1s": LOG,
    f"{FAB}/3D/Old_Tree_Stump_wd0qcaobw/Medium/wd0qcaobw_tier_2/Materials/MI_wd0qcaobw": LOG,
    # Top face only (rock_assembly_01: "mostly bare sides"); the default band coated most of its tilted sides, and
    # the moss shell (moss_shells.py) carries the top's thickness (#110 review).
    f"{FAB}/3D/Limestone_Slab_ubxbadpda/Medium/ubxbadpda_tier_2/Materials/MI_ubxbadpda": SLAB,
    "/Game/Megaplant_Library/Tree_European_Beech/Materials/MI_European_Beech_Bark_01": {},
    # Already mossy scans: no extra moss, only the ground blend at their base (#166).
    **{f"{FAB}/3D/Mossy_Forest_Boulder_{key}/Medium/{key}_tier_2/Materials/MI_{key}": BARE
       for key in ("wc1kebr", "wdbncbl", "wfstcdnaw", "wfstchwaw")},
}
ATTRIBUTES = [  # MakeMaterialAttributes pins passed straight through on the tree master
    "Metallic", "Specular", "Anisotropy", "EmissiveColor", "Opacity", "OpacityMask", "Tangent",
    "WorldPositionOffset", "SubsurfaceColor", "ClearCoat", "ClearCoatRoughness", "AmbientOcclusion", "Refraction",
    "PixelDepthOffset", "ShadingModel", "Displacement",
]
MP = unreal.MaterialProperty
X = unreal  # expression classes, short


class FunctionGraph(Graph):
    def node(self, cls, column, **props):
        self.row += 1
        expression = mel.create_material_expression_in_function(self.material, cls, -300 * column, 80 * self.row)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression


def asset(folder, name, cls, factory):
    path = f"{folder}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.load_asset(path)
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)


def build_function():
    function = asset(FOLDER, "MF_MossCoating", unreal.MaterialFunction, unreal.MaterialFunctionFactoryNew())
    # Like matgraph.fresh_material: the delete-all call skips about half the nodes, so delete one by one.
    for expression in list(mel.get_material_function_expressions(function)):
        mel.delete_material_expression_in_function(function, expression)
    if mel.get_num_material_expressions_in_function(function):
        raise SystemExit("MF_MossCoating: could not clear the old graph")
    g = FunctionGraph(function)
    T = unreal.FunctionInputType
    inputs = {}
    for order, (name, kind) in enumerate([
        ("BaseColor", T.FUNCTION_INPUT_VECTOR3), ("Normal", T.FUNCTION_INPUT_VECTOR3),
        ("Roughness", T.FUNCTION_INPUT_SCALAR), ("UpZ", T.FUNCTION_INPUT_SCALAR),
        ("Height", T.FUNCTION_INPUT_SCALAR), ("UV", T.FUNCTION_INPUT_VECTOR2),
        ("Seed", T.FUNCTION_INPUT_SCALAR), ("Side", T.FUNCTION_INPUT_SCALAR),
    ]):
        inputs[name] = g.node(X.MaterialExpressionFunctionInput, 10, input_name=name, input_type=kind, sort_priority=order)
    p = {name: g.node(X.MaterialExpressionScalarParameter, 10, parameter_name=name, default_value=value, group="Moss")
         for name, value in SCALARS.items() if name not in ("SideX", "SideY")}  # those live in the tree master

    def op(cls, column, a, b):
        return g.wire(cls, column, {"A": a, "B": b})

    def const(value):
        return g.node(X.MaterialExpressionConstant, 9, r=value)

    slope = g.wire(X.MaterialExpressionSmoothStep, 8, {"Min": p["SlopeLow"], "Max": p["SlopeHigh"], "Value": inputs["UpZ"]})
    patches = g.sample(PATCHES, op(X.MaterialExpressionMultiply, 8, inputs["UV"], p["PatchTile"]), 7)
    edge_patches = g.sample(PATCHES, op(X.MaterialExpressionMultiply, 9, inputs["UV"], p["EdgeTile"]), 9)
    second = g.wire(X.MaterialExpressionFrac, 10, {"": op(X.MaterialExpressionMultiply, 10, inputs["Seed"], const(7.31))})
    climb = g.wire(X.MaterialExpressionLinearInterpolate, 9, {"A": p["ClimbLow"], "B": p["ClimbHigh"], "Alpha": inputs["Seed"]})
    ragged = op(X.MaterialExpressionMultiply, 9, op(X.MaterialExpressionSubtract, 9, (edge_patches, "A"), const(0.5)),
                p["EdgeRelief"])
    sided = op(X.MaterialExpressionMultiply, 9, inputs["Side"], p["SideHeight"])
    top = op(X.MaterialExpressionMax, 8, op(X.MaterialExpressionAdd, 8, climb, op(X.MaterialExpressionAdd, 9, ragged, sided)),
             p["ContactTop"])
    fade = g.wire(X.MaterialExpressionLinearInterpolate, 9, {"A": p["FadeLow"], "B": p["FadeHigh"], "Alpha": second})
    base_max = op(X.MaterialExpressionAdd, 8, top, fade)
    above = g.wire(X.MaterialExpressionSmoothStep, 8, {"Min": top, "Max": base_max, "Value": inputs["Height"]})
    base = g.wire(X.MaterialExpressionOneMinus, 7, {"": above})
    # Union, not product: base OR slope (moss-techniques.md).
    region = op(X.MaterialExpressionMax, 6, op(X.MaterialExpressionMultiply, 7, base, p["BaseWeight"]),
                op(X.MaterialExpressionMultiply, 7, slope, p["SlopeWeight"]))
    breakup = op(X.MaterialExpressionMultiply, 6, op(X.MaterialExpressionSubtract, 6, (patches, "A"), const(0.5)),
                 p["PatchStrength"])
    value = op(X.MaterialExpressionAdd, 5, op(X.MaterialExpressionMultiply, 5, region, p["MossAmount"]), breakup)
    low = op(X.MaterialExpressionSubtract, 5, const(0.5), p["EdgeWidth"])
    high = op(X.MaterialExpressionAdd, 5, const(0.5), p["EdgeWidth"])
    threshold = g.wire(X.MaterialExpressionSmoothStep, 4, {"Min": low, "Max": high, "Value": value})
    # Breakup alone can cross the threshold, so MossAmount also gates the result: 0 is always bare.
    mask = op(X.MaterialExpressionMultiply, 3, threshold, g.wire(X.MaterialExpressionSaturate, 4, {"": p["MossAmount"]}))

    moss_uv = op(X.MaterialExpressionMultiply, 8, inputs["UV"], p["MossTile"])
    # The floor's tint (matgraph.MOSS_TINT), so roots, logs and ground read as one moss (#71 item 6); a 0.6
    # brightness here turned trunk bases near-black.
    tint = g.node(X.MaterialExpressionVectorParameter, 10, parameter_name="MossTint", group="Moss",
                  default_value=unreal.LinearColor(*MOSS_TINT, 1.0))
    color = op(X.MaterialExpressionMultiply, 4, g.sample(f"{MOSS}_B", moss_uv, 5), tint)
    normal = g.sample(f"{MOSS}_N", moss_uv, 5)
    rough = g.mask(g.sample(f"{MOSS}_ORM", moss_uv, 5), 4, "g")

    def blend(a, b):
        return g.wire(X.MaterialExpressionLinearInterpolate, 3, {"A": a, "B": b, "Alpha": mask})

    outputs = {
        "BaseColor": blend(inputs["BaseColor"], color),
        "Normal": g.wire(X.MaterialExpressionNormalize, 2, {"": blend(inputs["Normal"], normal)}),
        "Roughness": blend(inputs["Roughness"], rough),
        "Mask": mask,
    }
    for order, (name, source) in enumerate(outputs.items()):
        g.wire(X.MaterialExpressionFunctionOutput, 1, {"": source}, output_name=name, sort_priority=order)
    mel.update_material_function(function)
    return function


def build_ground_function():
    function = asset(FOLDER, "MF_GroundBlend", unreal.MaterialFunction, unreal.MaterialFunctionFactoryNew())
    for expression in list(mel.get_material_function_expressions(function)):
        mel.delete_material_expression_in_function(function, expression)
    if mel.get_num_material_expressions_in_function(function):
        raise SystemExit("MF_GroundBlend: could not clear the old graph")
    g = FunctionGraph(function)
    T = unreal.FunctionInputType
    inputs = {name: g.node(X.MaterialExpressionFunctionInput, 8, input_name=name, input_type=kind, sort_priority=order)
              for order, (name, kind) in enumerate([("BaseColor", T.FUNCTION_INPUT_VECTOR3),
                                                    ("Normal", T.FUNCTION_INPUT_VECTOR3),
                                                    ("Roughness", T.FUNCTION_INPUT_SCALAR)])}
    p = {name: g.node(X.MaterialExpressionScalarParameter, 8, parameter_name=name, default_value=value, group="Ground")
         for name, value in GROUND.items()}
    Kind = unreal.RuntimeVirtualTextureMaterialType
    ground = g.node(X.MaterialExpressionRuntimeVirtualTextureSample, 6, virtual_texture=unreal.load_asset(RVT_HEIGHT),
                    material_type=Kind.WORLD_HEIGHT)
    position = g.node(X.MaterialExpressionWorldPosition, 7)
    above = g.wire(X.MaterialExpressionSubtract, 5, {"A": g.mask(position, 6, "b"), "B": (ground, "WorldHeight")})
    # Noise in 0..1 subtracted, so it only raises the edge: at the contact (above <= 0) the blend stays full (#168 review).
    noise = g.node(X.MaterialExpressionNoise, 6, scale=1.0 / NOISE_CM, levels=2, output_min=0.0, output_max=1.0)
    noisy = g.wire(X.MaterialExpressionMultiply, 6, {"A": noise, "B": p["GroundJitter"]})
    height = g.wire(X.MaterialExpressionSubtract, 4, {"A": above, "B": noisy})
    fade = g.wire(X.MaterialExpressionSmoothStep, 3, {"Min": g.node(X.MaterialExpressionConstant, 4, r=0.0),
                                                      "Max": p["GroundBlendHeight"], "Value": height})
    alpha = g.wire(X.MaterialExpressionMultiply, 2, {"A": g.wire(X.MaterialExpressionOneMinus, 3, {"": fade}),
                                                     "B": p["GroundBlend"]})
    # The floor at this point, built as forest_floor.py builds it (matgraph FLOOR_*): its moss at two scales blended by
    # the macro noise and tinted, the soil patches where the same world-space noise puts them, the macro brightness.
    def world_noise(feature_cm):  # matgraph.Graph.noise's settings, so the patterns line up with the floor's
        raw = g.node(X.MaterialExpressionNoise, 6, scale=1.0 / feature_cm, levels=3, output_min=0.0, output_max=1.0)
        return g.wire(X.MaterialExpressionSaturate, 5, {"": raw})

    def const(value):
        return g.node(X.MaterialExpressionConstant, 6, r=value)

    xy = g.mask(position, 6, "rg")
    moss_uv = g.wire(X.MaterialExpressionDivide, 5, {"A": xy, "B": const(FLOOR_MOSS[1])})
    detail_uv = g.wire(X.MaterialExpressionDivide, 5, {"A": xy, "B": const(FLOOR_MOSS[1] * FLOOR_DETAIL_SCALE)})
    soil_uv = g.wire(X.MaterialExpressionDivide, 5, {"A": xy, "B": const(FLOOR_VARIANT[1])})
    macro = world_noise(FLOOR_MACRO_NOISE_CM)
    share, low, high = FLOOR_VARIETY
    soil = g.wire(X.MaterialExpressionMultiply, 4, {"A": const(share), "B": g.wire(
        X.MaterialExpressionSmoothStep, 5, {"Min": const(low), "Max": const(high),
                                            "Value": world_noise(FLOOR_VARIANT_NOISE_CM)})})
    tint = g.node(X.MaterialExpressionConstant3Vector, 5, constant=unreal.LinearColor(*FLOOR_MOSS_TINT, 1.0))
    floor = {}
    for kind, suffix in ED_SURFACE.items():
        moss = g.wire(X.MaterialExpressionLinearInterpolate, 4, {
            "A": g.sample(FLOOR_MOSS[0] + suffix, moss_uv, 5), "B": g.sample(FLOOR_MOSS[0] + suffix, detail_uv, 5),
            "Alpha": macro})
        if kind == "B":
            moss = g.wire(X.MaterialExpressionMultiply, 3, {"A": moss, "B": tint})
        floor[kind] = g.wire(X.MaterialExpressionLinearInterpolate, 2, {
            "A": moss, "B": g.sample(FLOOR_VARIANT[0] + suffix, soil_uv, 4), "Alpha": soil})
    brightness = g.wire(X.MaterialExpressionLinearInterpolate, 2, {
        "A": const(1 - FLOOR_MACRO_BRIGHTNESS), "B": const(1 + FLOOR_MACRO_BRIGHTNESS), "Alpha": macro})
    floor["B"] = g.wire(X.MaterialExpressionMultiply, 2, {"A": floor["B"], "B": brightness})

    def blend(a, b):
        return g.wire(X.MaterialExpressionLinearInterpolate, 1, {"A": a, "B": b, "Alpha": alpha})

    outputs = {"BaseColor": blend(inputs["BaseColor"], floor["B"]),
               "Normal": g.wire(X.MaterialExpressionNormalize, 0, {"": blend(inputs["Normal"], floor["N"])}),
               "Roughness": blend(inputs["Roughness"], g.mask(floor["ORM"], 1, "g")),
               "Mask": alpha}
    for order, (name, source) in enumerate(outputs.items()):
        g.wire(X.MaterialExpressionFunctionOutput, 0, {"": source}, output_name=name, sort_priority=order)
    mel.update_material_function(function)
    return function


def coat_inputs(g, mode):
    """UpZ, Height and UV for the function: world-based for static meshes, rest-pose for skinned trees."""
    if mode == STATIC:
        up = g.mask(g.node(X.MaterialExpressionVertexNormalWS, 9), 8, "b")
        height = g.node(X.MaterialExpressionConstant, 8, r=1.0e6)  # no base band on rocks and logs
        uv = g.wire(X.MaterialExpressionDivide, 8, {"A": g.mask(g.node(X.MaterialExpressionWorldPosition, 9), 8, "rg"),
                                                    "B": g.node(X.MaterialExpressionConstant, 9, r=100.0)})
        zero = g.node(X.MaterialExpressionConstant, 8, r=0.0)
        return up, height, uv, zero, zero
    # Rest pose, interpolated from the vertex shader (moss-techniques.md: never the wind-deformed normal).
    normal = g.wire(X.MaterialExpressionVertexInterpolator, 8, {"": g.node(X.MaterialExpressionPreSkinnedNormal, 9)})
    position = g.node(X.MaterialExpressionLocalPosition, 9)
    position.set_editor_property("local_origin", unreal.LocalPositionOrigin.INSTANCE_PRE_SKINNING)
    rest = g.wire(X.MaterialExpressionVertexInterpolator, 8, {"": position})
    uv_scale = g.node(X.MaterialExpressionScalarParameter, 9, parameter_name="BarkUVToMetres", default_value=1.0,
                      group="Moss")
    uv = g.wire(X.MaterialExpressionMultiply, 8, {"A": g.node(X.MaterialExpressionTextureCoordinate, 9), "B": uv_scale})
    # Per-tree seed hashed from the instance origin in metres: PerInstanceRandom is 0 on Biome Core's skinned trees (#99).
    # The origin is the instance transform, so the seed stays put in the wind.
    origin = g.wire(X.MaterialExpressionTransformPosition, 10, {"": g.node(X.MaterialExpressionConstant3Vector, 11)},
                    transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_INSTANCE,
                    transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    metres = g.wire(X.MaterialExpressionDivide, 9, {"A": g.mask(origin, 10, "rg"),
                                                    "B": g.node(X.MaterialExpressionConstant, 10, r=100.0)})
    phase = g.wire(X.MaterialExpressionDotProduct, 9, {
        "A": metres, "B": g.node(X.MaterialExpressionConstant2Vector, 10, r=12.9898, g=78.233)})
    seed = g.wire(X.MaterialExpressionFrac, 8, {"": g.wire(X.MaterialExpressionMultiply, 8, {
        "A": g.wire(X.MaterialExpressionSine, 9, {"": phase}, period=6.283185),
        "B": g.node(X.MaterialExpressionConstant, 9, r=43758.5453)})})
    # The side bias is a world direction (one moss side across the forest), brought into each tree's rest frame.
    side_world = g.wire(X.MaterialExpressionAppendVector, 9, {
        "A": g.wire(X.MaterialExpressionAppendVector, 10, {
            "A": g.node(X.MaterialExpressionScalarParameter, 11, parameter_name="SideX", default_value=SCALARS["SideX"], group="Moss"),
            "B": g.node(X.MaterialExpressionScalarParameter, 11, parameter_name="SideY", default_value=SCALARS["SideY"], group="Moss")}),
        "B": g.node(X.MaterialExpressionConstant, 10, r=0.0)})
    side_local = g.wire(X.MaterialExpressionTransform, 8, {"": side_world},
                        transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
                        transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_INSTANCE)  # LOCAL is the primitive's
    side_dir = g.wire(X.MaterialExpressionNormalize, 7, {"": g.mask(side_local, 8, "rg")})  # undo the instance scale
    # PreSkinnedNormal comes back mirrored in Y against the instance frame (measured on #106: a +X side landed on +X,
    # a +Y side on -Y), so flip its Y before comparing.
    rest_xy = g.wire(X.MaterialExpressionMultiply, 8, {"A": g.mask(normal, 9, "rg"),
                                                       "B": g.node(X.MaterialExpressionConstant2Vector, 9, r=1.0, g=-1.0)})
    side = g.wire(X.MaterialExpressionDotProduct, 7, {"A": rest_xy, "B": side_dir})
    # Rest height times the tree's own z scale, so the climb is in physical cm on every tree size (#106 review).
    scale_z = g.wire(X.MaterialExpressionLength, 8, {"": g.wire(X.MaterialExpressionTransform, 9, {
        "": g.node(X.MaterialExpressionConstant3Vector, 10, constant=unreal.LinearColor(0, 0, 1, 0))},
        transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_INSTANCE,
        transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)})
    height = g.wire(X.MaterialExpressionMultiply, 7, {"A": g.mask(rest, 8, "b"), "B": scale_z})
    return g.mask(normal, 7, "b"), height, uv, seed, side


def coated_master(source_path, name, function, mode, ground):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    material = unreal.EditorAssetLibrary.duplicate_asset(source_path, path)
    g = Graph(material)
    g.row = 200  # below the stock graph
    call = g.node(X.MaterialExpressionMaterialFunctionCall, 2)
    call.set_material_function(function)
    up, height, uv, seed, side = coat_inputs(g, mode)
    for pin, source in {"UpZ": up, "Height": height, "UV": uv, "Seed": seed, "Side": side}.items():
        mel.connect_material_expressions(source, "", call, pin) or fail(name, pin)
    if mode == STATIC:
        # Stock outputs -> moss -> ground blend -> outputs.
        blend = g.node(X.MaterialExpressionMaterialFunctionCall, 1)
        blend.set_material_function(ground)
        for pin, prop in {"BaseColor": MP.MP_BASE_COLOR, "Normal": MP.MP_NORMAL, "Roughness": MP.MP_ROUGHNESS}.items():
            source = mel.get_material_property_input_node(material, prop)
            out = mel.get_material_property_input_node_output_name(material, prop)
            mel.connect_material_expressions(source, out, call, pin) or fail(name, pin)
            mel.connect_material_expressions(call, pin, blend, pin) or fail(name, pin)
            mel.connect_material_property(blend, pin, prop) or fail(name, pin)
    else:
        source = mel.get_material_property_input_node(material, MP.MP_MATERIAL_ATTRIBUTES)
        out = mel.get_material_property_input_node_output_name(material, MP.MP_MATERIAL_ATTRIBUTES)
        split = g.node(X.MaterialExpressionBreakMaterialAttributes, 3)
        mel.connect_material_expressions(source, out, split, "") or fail(name, "break")
        make = g.node(X.MaterialExpressionMakeMaterialAttributes, 1)
        for pin in ("BaseColor", "Normal", "Roughness"):
            mel.connect_material_expressions(split, pin, call, pin) or fail(name, pin)
            mel.connect_material_expressions(call, pin, make, pin) or fail(name, pin)
        missing = [pin for pin in ATTRIBUTES if not mel.connect_material_expressions(split, pin, make, pin)]
        if missing:
            print(f"{name}: attributes not passed through: {missing}")
        mel.connect_material_property(make, "", MP.MP_MATERIAL_ATTRIBUTES) or fail(name, "attributes")
    mel.recompile_material(material)
    return material


def fail(name, what):
    raise SystemExit(f"{name}: could not connect {what}")


def stock_master(instance):
    """The stock master an instance belongs to, whether it is parented to the stock master or its coated copy."""
    parent = instance.get_editor_property("parent").get_path_name().split(".")[0]
    for stock, (name, _) in MASTERS.items():
        if parent in (stock, f"{FOLDER}/{name}"):
            return stock
    raise SystemExit(f"{instance.get_path_name()}: parent {parent} is not a known master")


instances = {path: unreal.load_asset(path) for path in COATED}
stocks = {path: stock_master(instance) for path, instance in instances.items()}
for path, instance in instances.items():  # back to stock so the copies can be rebuilt
    mel.set_material_instance_parent(instance, unreal.load_asset(stocks[path]))
function = build_function()
ground = build_ground_function()
coated = {stock: coated_master(stock, name, function, mode, ground) for stock, (name, mode) in MASTERS.items()}
for path, instance in instances.items():
    mel.set_material_instance_parent(instance, coated[stocks[path]])
    # Drop stale moss and ground overrides (texture overrides stay), then apply this instance's.
    kept = [v for v in instance.get_editor_property("scalar_parameter_values")
            if str(v.parameter_info.name) not in SCALARS and str(v.parameter_info.name) not in GROUND]
    instance.set_editor_property("scalar_parameter_values", kept)
    for name in list(SCALARS) + list(GROUND):
        if name in COATED[path]:
            mel.set_material_instance_scalar_parameter_value(instance, name, COATED[path][name])
    mel.update_material_instance(instance)
    print(f"coated {path.rsplit('/', 1)[1]}")
unreal.EditorAssetLibrary.save_directory(FOLDER)
for path in COATED:
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)  # reparenting does not mark them dirty
