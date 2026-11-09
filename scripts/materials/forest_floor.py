"""Build the Forest Biome's procedural landscape material.

    scripts/editor-py scripts/materials/forest_floor.py [--assign]

Rebuilds /Game/ForestBiome/M_ForestFloor from scratch (no painted layers) and keeps MI_ForestFloor as its
tuning instance: sand below the shore height, darker and glossier at the waterline; mossy floor on low,
flat (damp) ground, broken up by the moss-patch mask; dry leaf litter everywhere else. Thresholds are
material parameters, so instance overrides survive a rebuild. Its Landscape Grass output carries the groundcover and
the further GRASS_LAYERS (#117): Electric Dreams undergrowth, debris and ground scans on the forest floor (not the
meadow stretches), and blown litter on the sand. --assign sets the instance on every
Landscape actor in the open level (streaming proxies inherit it).
"""

import importlib
import json
import sys
from pathlib import Path

import matgraph
import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
import biome_variants
from meadow import MEADOWS, TOP

importlib.reload(matgraph)  # the editor keeps imported modules between runs
mel = matgraph.mel
Graph = matgraph.Graph

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
    "ShoreBlend": 50.0,  # cm across, horizontally, of each sand/floor edge (through the slope, like ShoreWidth)
    "ShoreWidth": 450.0,  # cm across which sand and forest floor interleave (transition_ground_01: 2-4 m; #39; #117 review)
    "ShorePatchShare": 0.6,  # share of that width from the moss-patch texture: ragged edges, sand pockets in moss
    "SlopeMin": 0.05,  # the slope assumed on flat ground, so the interleave still has a width there
    "SlopeMax": 2.0,
    "LitterWidth": 400.0,  # cm out onto the sand that beech litter mixes in
    "LitterMix": 0.85,  # at most this much litter over sand
    "WetBandTop": 40.0,  # sand is fully wet below this, fully dry at ShoreHeight
    "WetDarkening": 0.6,
    "DryBrightening": 1.25,
    "WetRoughness": 0.45,  # multiplies sand roughness at the waterline
    "DampLow": 300.0,  # ground below DampLow counts as damp, above DampHigh as dry
    "DampHigh": 1200.0,
    "FlatLow": 0.85,  # vertex normal Z: steeper than FlatLow is never mossy
    "FlatHigh": 0.97,
    "ForestMoss": 1.0,  # moss everywhere above the shore, not only on damp low ground (interior_01, #49)
    # Vertex normal Z: ForestMoss is full up to ~60 deg and gone past ~75 deg, so the coastal bank faces read as mossy
    # living cover (edge_in, #71), not bare litter (was 0.5 / 0.75, ~41-60 deg).
    "ForestFlatLow": 0.25,
    "ForestFlatHigh": 0.5,
    "MossNoiseStrength": 1.6,  # how far large-scale noise pushes moss in and out of the damp zones
    "PatchTile": 800.0,
    "PatchStrength": 0.6,  # moss-patch texture adds edge detail inside the noise's mossy areas
    "DetailScale": 2.7,  # each layer is also sampled this many times larger, blended by slow noise (anti-tiling)
    "MacroBrightness": 0.15,  # +/- brightness variation across the ground
    "GrassRunLow": 0.3,  # groundcover noise: none below GrassRunLow, full above GrassRunHigh
    "GrassRunHigh": 0.55,
    # cm inland, horizontally, over which groundcover fades in above the (noisy) shore line: starting it at the sand
    # edge drew a crisp green line along the beach (transition_ground; operator on #38: no distinct line).
    "GrassShoreWidth": 500.0,
}
MOSS_TINT = matgraph.MOSS_TINT
MOSS_NOISE_CM = 2000.0  # feature size of the noise that places moss
MACRO_NOISE_CM = 1200.0  # feature size of the noise that hides texture repetition
SHORE_NOISE_CM = 350.0  # feature size of the shore line's tongues and islands
LITTER_NOISE_CM = 120.0  # feature size of the litter patches on sand
# Groundcover (#100): ankle-high tufts and rosettes (biome_variants.GROUNDCOVER_VARIANTS, #98) as Landscape Grass, which
# spawns only around the camera. As PCG children the density that reads as a continuous layer (~15/m2 in the #98
# trial) would be tens of millions of instances island-wide; PCG at 500 anchors/ha x 15 gave under 1/m2 and none
# showed in the interior view.
GRASS = f"{FOLDER}/DA_ForestGroundcover"  # a LandscapeGrassType; DA_ per the naming hook
# GrassVariety density ("per 10 m2") summed over the variants, where the weight is 1. Measured in the interior view:
# 120 and 250 read as a few scattered tufts; 1000 matches the #98 trial that read as one continuous layer.
GRASS_DENSITY = 1000.0
# cm beyond which groundcover is not spawned. No fade: StartCullDistance only feeds PerInstanceFadeAmount, which the
# Project Nature materials do not read (#108 review), so plants stop at this distance.
GRASS_CULL = 4000
GRASS_SCALE = (0.9, 1.6)
# Further Landscape Grass layers (#117; operator, 2026-11-08: less grass, denser plant life, with scans, stones, sticks
# and litter, after the Electric Dreams floor). Input name -> (asset, biome_variants list, density per 10 m2, cull cm,
# scale range, where): "gaps" fills where the groundcover runs are not, in colonies; "all" is the whole forest floor;
# "patches" is a sparse noise of its own, kept back from the sand (SCAN_MASK); "sand" is the litter patches on the upper sand;
# "waterline" is clusters on the sand at the water's edge and "dry sand" the sand above it, everywhere.
GRASS_LAYERS = {
    "Undergrowth": (f"{FOLDER}/DA_ForestUndergrowth", "UNDERGROWTH_VARIANTS", 60.0, 6000, (0.8, 1.3), "gaps"),
    "Debris": (f"{FOLDER}/DA_ForestDebris", "DEBRIS_VARIANTS", 150.0, 2500, (1.0, 2.5), "all"),
    "Leaves": (f"{FOLDER}/DA_ForestLeaves", "LEAF_LITTER_VARIANTS", 25.0, 2500, (0.4, 0.8), "all"),
    "Scans": (f"{FOLDER}/DA_ForestScans", "SCAN_VARIANTS", 25.0, 6000, (0.8, 1.3), "patches"),
    "SandLitter": (f"{FOLDER}/DA_SandLitter", "SAND_LITTER_VARIANTS", 150.0, 3000, (1.0, 2.0), "sand"),
    # #122: stones clustered at the waterline, a few big rocks among them, sparse stones on the dry sand.
    "WaterlineStones": (f"{FOLDER}/DA_WaterlineStones", "WATERLINE_STONE_VARIANTS", 120.0, 4000, (1.5, 3.5), "waterline"),
    "WaterlineGround": (f"{FOLDER}/DA_WaterlineGround", "WATERLINE_GROUND_VARIANTS", 3.0, 6000, (0.6, 1.0), "waterline"),
    # 6-9 m rocks: at 0.4 per 10 m2 they walled the beach in (#122 trial).
    "WaterlineBoulders": (f"{FOLDER}/DA_WaterlineBoulders", "WATERLINE_BOULDER_VARIANTS", 0.02, 10000, (0.25, 0.45), "waterline"),
    "DrySandStones": (f"{FOLDER}/DA_DrySandStones", "DRY_SAND_STONE_VARIANTS", 6.0, 3000, (1.5, 3.0), "dry sand"),
}
UNDERGROWTH_NOISE_CM = 1500.0  # feature size of the undergrowth colonies
SCAN_NOISE_CM = 700.0  # feature size of the scan patches
# z: fade in from under the water, full at the edge, out up the sand. L_vilm's beach lies only 0-20 cm above the sea:
# a band to 50 cm covered all of it (#122 trial).
WATERLINE_CM = (-30.0, -5.0, 3.0, 12.0)
WATERLINE_NOISE_CM = 900.0  # feature size of the waterline stone clusters
SAND_LITTER_ABOVE_CM = 30.0  # cm above the sea over which sand litter fades in
SAND_LITTER_NOISE_CM = 600.0  # feature size of the litter patches on the upper sand
MEADOW_BLEND_CM = 1000.0  # the further layers fade out over this inside each meadow stretch's edge (meadow.MEADOWS)
GRASS_NOISE_CM = 900.0  # feature size of the runs and openings
# No groundcover in water or on the footpath: groundcover_mask.py's 1 m grid over the island's bounds (forest_foot.json).
GRASS_MASK = f"{FOLDER}/T_GroundcoverMask"
# The ground scans are slabs of forest soil with hard edges: on or by the sand they read as cut-out tiles (operator,
# 2026-11-09). scan_mask.py's distance from the sand, on the same grid, keeps them 6-12 m inland.
SCAN_MASK = f"{FOLDER}/T_ScanSandMask"
ISLAND = json.loads((Path(unreal.Paths.project_dir()) / "../scripts/pcg/forest_foot.json").read_text())["island_m"]


def grass_type(path=GRASS, variants="GROUNDCOVER_VARIANTS", density=GRASS_DENSITY, cull=GRASS_CULL, scale=GRASS_SCALE):
    """A LandscapeGrassType at path with one variety per row of the named biome_variants list, sharing density by weight."""
    rows = getattr(importlib.reload(biome_variants), variants)
    grass = unreal.load_asset(path) or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        path.rsplit("/", 1)[1], FOLDER, unreal.LandscapeGrassType, None)
    total = sum(weight for _, weight in rows)
    varieties = []
    for mesh_path, weight in rows:
        variety = unreal.GrassVariety()
        mesh = unreal.load_asset(mesh_path)
        if mesh is None:
            raise SystemExit(f"missing {variants} mesh {mesh_path}")
        variety.set_editor_property("grass_mesh", mesh)
        variety.set_editor_property("grass_density", unreal.PerPlatformFloat(default=density * weight / total))
        variety.set_editor_property("start_cull_distance", unreal.PerPlatformInt(default=cull))
        variety.set_editor_property("end_cull_distance", unreal.PerPlatformInt(default=cull))
        variety.set_editor_property("scale_x", unreal.FloatInterval(*scale))
        variety.set_editor_property("scaling", unreal.GrassScaling.UNIFORM)
        variety.set_editor_property("random_rotation", True)
        variety.set_editor_property("align_to_surface", True)
        varieties.append(variety)
    grass.set_editor_property("grass_varieties", varieties)
    unreal.EditorAssetLibrary.save_loaded_asset(grass, False)
    return grass


def build():
    path = f"{FOLDER}/M_ForestFloor"
    material = matgraph.fresh_material(path)
    g = Graph(material)
    lerp = unreal.MaterialExpressionLinearInterpolate
    P = unreal.MaterialExpressionScalarParameter
    p = {name: g.node(P, 9, parameter_name=name, default_value=value) for name, value in SCALARS.items()}

    world = g.node(unreal.MaterialExpressionWorldPosition, 9)
    xy, z = g.mask(world, 8, "rg"), g.mask(world, 8, "b")
    nz = g.mask(g.node(unreal.MaterialExpressionVertexNormalWS, 9), 8, "b")

    patch_uv = g.wire(unreal.MaterialExpressionDivide, 6, {"A": xy, "B": p["PatchTile"]})
    patches = g.sample(PATCHES, patch_uv, 5)
    half = g.node(unreal.MaterialExpressionConstant, 6, r=0.5)

    def wobble(source, strength):
        """(source - 0.5) * strength: a signed offset from a 0..1 noise or texture channel."""
        centred_source = g.wire(unreal.MaterialExpressionSubtract, 6, {"A": source, "B": half})
        return g.wire(unreal.MaterialExpressionMultiply, 6, {"A": centred_source, "B": strength})

    # Sand below a noisy shore line, so sand and forest floor interleave over a few metres (transition_ground_01):
    # never a straight contour line. The material cannot measure distance from the forest edge, so a horizontal
    # width becomes a height offset through the local slope (rise = run * tan): about ShoreWidth wide on any slope.
    sine = g.wire(
        unreal.MaterialExpressionSquareRoot,
        6,
        {
            "": g.wire(
                unreal.MaterialExpressionOneMinus,
                6,
                {"": g.wire(unreal.MaterialExpressionMultiply, 7, {"A": nz, "B": nz})},
            )
        },
    )
    cosine = g.wire(
        unreal.MaterialExpressionMax, 6, {"A": nz, "B": g.node(unreal.MaterialExpressionConstant, 7, r=0.2)}
    )
    tangent = g.wire(
        unreal.MaterialExpressionClamp,
        5,
        {
            "": g.wire(unreal.MaterialExpressionDivide, 6, {"A": sine, "B": cosine}),
            "Min": p["SlopeMin"],
            "Max": p["SlopeMax"],
        },
    )
    rise = g.wire(unreal.MaterialExpressionMultiply, 5, {"A": p["ShoreWidth"], "B": tangent})
    one = g.node(unreal.MaterialExpressionConstant, 7, r=1.0)
    noise_share = g.wire(unreal.MaterialExpressionSubtract, 6, {"A": one, "B": p["ShorePatchShare"]})
    shore_z = g.wire(
        unreal.MaterialExpressionAdd,
        6,
        {
            "A": z,
            "B": g.wire(
                unreal.MaterialExpressionMultiply,
                5,
                {
                    "A": rise,
                    "B": g.wire(
                        unreal.MaterialExpressionAdd,
                        6,
                        {
                            "A": wobble(g.noise(7, SHORE_NOISE_CM), noise_share),
                            "B": wobble((patches, "A"), p["ShorePatchShare"]),
                        },
                    ),
                },
            ),
        },
    )
    # Exactly flat ground at ShoreHeight stays mixed however wide it is: only a distance-to-edge field could
    # bound that, and L_vilm has no such shelf (the shore rises through a bank, #38).
    blend_rise = g.wire(unreal.MaterialExpressionMultiply, 6, {"A": p["ShoreBlend"], "B": tangent})
    shore_min = g.wire(unreal.MaterialExpressionSubtract, 7, {"A": p["ShoreHeight"], "B": blend_rise})
    shore_max = g.wire(unreal.MaterialExpressionAdd, 7, {"A": p["ShoreHeight"], "B": blend_rise})
    above = g.wire(unreal.MaterialExpressionSmoothStep, 6, {"Min": shore_min, "Max": shore_max, "Value": shore_z})
    sand_mask = g.wire(unreal.MaterialExpressionOneMinus, 5, {"": above})
    # Beech litter mixes into the upper sand in patches rather than forming its own band.
    litter_rise = g.wire(unreal.MaterialExpressionMultiply, 6, {"A": p["LitterWidth"], "B": tangent})
    litter_low = g.wire(unreal.MaterialExpressionSubtract, 7, {"A": p["ShoreHeight"], "B": litter_rise})
    near_shore = g.wire(
        unreal.MaterialExpressionSmoothStep, 6, {"Min": litter_low, "Max": p["ShoreHeight"], "Value": shore_z}
    )
    litter_patches = g.wire(
        unreal.MaterialExpressionSmoothStep,
        6,
        {
            "Min": g.node(unreal.MaterialExpressionConstant, 7, r=0.45),
            "Max": g.node(unreal.MaterialExpressionConstant, 7, r=0.7),
            "Value": g.noise(7, LITTER_NOISE_CM),
        },
    )
    litter = g.wire(
        unreal.MaterialExpressionMultiply,
        5,
        {
            "A": g.wire(unreal.MaterialExpressionMultiply, 5, {"A": near_shore, "B": litter_patches}),
            "B": p["LitterMix"],
        },
    )
    flat = g.wire(unreal.MaterialExpressionSmoothStep, 6, {"Min": p["FlatLow"], "Max": p["FlatHigh"], "Value": nz})
    high = g.wire(unreal.MaterialExpressionSmoothStep, 6, {"Min": p["DampLow"], "Max": p["DampHigh"], "Value": z})
    damp = g.wire(
        unreal.MaterialExpressionMultiply, 5, {"A": flat, "B": g.wire(unreal.MaterialExpressionOneMinus, 5, {"": high})}
    )
    # Large-scale noise places moss (no tiled mask, so no grid); the patch texture only adds edge detail.
    moss_noise = g.noise(6, MOSS_NOISE_CM)
    centred = g.wire(
        unreal.MaterialExpressionSubtract,
        5,
        {"A": moss_noise, "B": g.node(unreal.MaterialExpressionConstant, 6, r=0.5)},
    )
    moss_term = g.wire(unreal.MaterialExpressionMultiply, 4, {"A": centred, "B": p["MossNoiseStrength"]})
    patch = g.wire(unreal.MaterialExpressionMultiply, 4, {"A": (patches, "A"), "B": p["PatchStrength"]})
    patch_term = g.wire(unreal.MaterialExpressionMultiply, 4, {"A": patch, "B": moss_noise})
    gentle = g.wire(
        unreal.MaterialExpressionSmoothStep, 6, {"Min": p["ForestFlatLow"], "Max": p["ForestFlatHigh"], "Value": nz}
    )
    forest = g.wire(unreal.MaterialExpressionMultiply, 5, {"A": gentle, "B": p["ForestMoss"]})
    moss_sum = g.wire(
        unreal.MaterialExpressionAdd,
        4,
        {
            "A": g.wire(unreal.MaterialExpressionMax, 5, {"A": damp, "B": forest}),
            "B": g.wire(unreal.MaterialExpressionAdd, 4, {"A": moss_term, "B": patch_term}),
        },
    )
    moss_mask = g.wire(unreal.MaterialExpressionSaturate, 3, {"": moss_sum})
    macro = g.noise(6, MACRO_NOISE_CM)
    dryness = g.wire(
        unreal.MaterialExpressionSmoothStep, 6, {"Min": p["WetBandTop"], "Max": p["ShoreHeight"], "Value": z}
    )
    tint = g.wire(lerp, 5, {"A": p["WetDarkening"], "B": p["DryBrightening"], "Alpha": dryness})
    wet_rough = g.wire(
        lerp, 5, {"A": p["WetRoughness"], "B": g.node(unreal.MaterialExpressionConstant, 6, r=1.0), "Alpha": dryness}
    )

    sets = {}
    for name, (prefix, tile) in LAYERS.items():
        size = g.node(P, 7, parameter_name=f"{name}Tile", default_value=tile)
        uv = g.wire(unreal.MaterialExpressionDivide, 6, {"A": xy, "B": size})
        big = g.wire(unreal.MaterialExpressionMultiply, 7, {"A": size, "B": p["DetailScale"]})
        uv_big = g.wire(unreal.MaterialExpressionDivide, 6, {"A": xy, "B": big})
        sets[name] = {
            kind: g.wire(
                lerp,
                4,
                {
                    "A": g.sample(f"{prefix}_{kind}", uv, 5),
                    "B": g.sample(f"{prefix}_{kind}", uv_big, 5),
                    "Alpha": macro,
                },
            )
            for kind in ("B", "N", "ORM")
        }

    # Moss albedo tint (#71 item 6, interior_01): the scanned moss reads dark grey-green under the canopy; the
    # reference floor is a bright yellow-green. A vector parameter, so MI_ForestFloor tunes it without a rebuild.
    moss_tint = g.node(unreal.MaterialExpressionVectorParameter, 9, parameter_name="MossTint",
                       default_value=unreal.LinearColor(*MOSS_TINT, 1.0))
    sets["Moss"]["B"] = g.wire(unreal.MaterialExpressionMultiply, 4, {"A": sets["Moss"]["B"], "B": moss_tint})

    def blend(sand, kind, column=2):
        floor = g.wire(lerp, column, {"A": sets["Leaves"][kind], "B": sets["Moss"][kind], "Alpha": moss_mask})
        littered = g.wire(lerp, column, {"A": sand, "B": sets["Leaves"][kind], "Alpha": litter})
        return g.wire(lerp, column - 1, {"A": floor, "B": littered, "Alpha": sand_mask})

    color = blend(g.wire(unreal.MaterialExpressionMultiply, 3, {"A": sets["Sand"]["B"], "B": tint}), "B")
    low_b = g.wire(unreal.MaterialExpressionOneMinus, 2, {"": p["MacroBrightness"]})
    high_b = g.wire(
        unreal.MaterialExpressionAdd,
        2,
        {"A": g.node(unreal.MaterialExpressionConstant, 3, r=1.0), "B": p["MacroBrightness"]},
    )
    color = g.wire(
        unreal.MaterialExpressionMultiply,
        0,
        {"A": color, "B": g.wire(lerp, 1, {"A": low_b, "B": high_b, "Alpha": macro})},
    )
    normal = blend(sets["Sand"]["N"], "N")
    orm = blend(sets["Sand"]["ORM"], "ORM")
    sand_rough = g.wire(
        unreal.MaterialExpressionMultiply, 3, {"A": g.mask(sets["Sand"]["ORM"], 4, "g"), "B": wet_rough}
    )
    floor_rough = g.wire(
        lerp,
        2,
        {"A": g.mask(sets["Leaves"]["ORM"], 3, "g"), "B": g.mask(sets["Moss"]["ORM"], 3, "g"), "Alpha": moss_mask},
    )
    littered_rough = g.wire(lerp, 2, {"A": sand_rough, "B": g.mask(sets["Leaves"]["ORM"], 3, "g"), "Alpha": litter})
    rough = g.wire(lerp, 1, {"A": floor_rough, "B": littered_rough, "Alpha": sand_mask})

    # Groundcover where the floor is forest (not sand), not on steep faces, in runs with openings between them.
    runs = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": p["GrassRunLow"], "Max": p["GrassRunHigh"],
                                                          "Value": g.noise(4, GRASS_NOISE_CM)})
    x_min, x_max, y_min, y_max = (v * 100 for v in ISLAND)
    mask_uv = g.wire(unreal.MaterialExpressionDivide, 3, {
        "A": g.wire(unreal.MaterialExpressionSubtract, 4, {"A": xy, "B": g.node(
            unreal.MaterialExpressionConstant2Vector, 5, r=x_min, g=y_min)}),
        "B": g.node(unreal.MaterialExpressionConstant2Vector, 4, r=x_max - x_min, g=y_max - y_min)})
    allowed = g.mask(g.sample(GRASS_MASK, mask_uv, 2), 2, "r")
    grass_rise = g.wire(unreal.MaterialExpressionMultiply, 3, {"A": p["GrassShoreWidth"], "B": tangent})
    inland = g.wire(unreal.MaterialExpressionSmoothStep, 2, {
        "Min": p["ShoreHeight"], "Max": g.wire(unreal.MaterialExpressionAdd, 3, {"A": p["ShoreHeight"], "B": grass_rise}),
        "Value": shore_z})
    weight = g.wire(unreal.MaterialExpressionMultiply, 1, {"A": g.wire(unreal.MaterialExpressionMultiply, 2, {
        "A": inland, "B": gentle}), "B": g.wire(unreal.MaterialExpressionMultiply, 2, {"A": runs, "B": allowed})})
    one = g.node(unreal.MaterialExpressionConstant, 4, r=1.0)
    # Not on the meadow stretches' low ground (meadow.py: within a MEADOWS circle, below TOP): their grass and heather
    # stay as they are; the undergrowth, debris and scans are the forest floor's.
    low = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": g.node(unreal.MaterialExpressionConstant, 4, r=TOP + 100),
                                                         "Max": g.node(unreal.MaterialExpressionConstant, 4, r=TOP), "Value": z})
    meadow = None
    for x, y, radius in MEADOWS:
        distance = g.wire(unreal.MaterialExpressionDistance, 3, {"A": xy, "B": g.node(
            unreal.MaterialExpressionConstant2Vector, 4, r=x * 100, g=y * 100)})
        inside = g.wire(unreal.MaterialExpressionSmoothStep, 3, {
            "Min": g.node(unreal.MaterialExpressionConstant, 4, r=radius * 100),
            "Max": g.node(unreal.MaterialExpressionConstant, 4, r=radius * 100 - MEADOW_BLEND_CM), "Value": distance})
        meadow = inside if meadow is None else g.wire(unreal.MaterialExpressionMax, 3, {"A": meadow, "B": inside})
    forest_only = g.wire(unreal.MaterialExpressionSubtract, 2, {"A": one, "B": g.wire(
        unreal.MaterialExpressionMultiply, 3, {"A": meadow, "B": low})})
    floor = g.wire(unreal.MaterialExpressionMultiply, 2, {"A": g.wire(unreal.MaterialExpressionMultiply, 2, {
        "A": inland, "B": gentle}), "B": g.wire(unreal.MaterialExpressionMultiply, 2, {"A": allowed, "B": forest_only})})
    colonies = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": p["GrassRunLow"], "Max": p["GrassRunHigh"],
                                                              "Value": g.noise(4, UNDERGROWTH_NOISE_CM)})
    gaps = g.wire(unreal.MaterialExpressionMultiply, 2, {  # where groundcover runs are not, in colonies
        "A": g.wire(unreal.MaterialExpressionSubtract, 3, {"A": one, "B": runs}), "B": colonies})
    patches = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": p["GrassRunHigh"], "Max": one,
                                                             "Value": g.noise(4, SCAN_NOISE_CM)})
    scan_inland = g.mask(g.sample(SCAN_MASK, mask_uv, 2), 2, "r")
    where = {"gaps": gaps, "patches": g.wire(unreal.MaterialExpressionMultiply, 2, {"A": patches, "B": scan_inland})}
    # Its own patches: the material's litter patches (LITTER_NOISE_CM) are finer than the 2 m landscape vertices the grass
    # weight is sampled at, so they gave almost no instances.
    # On the sand above the waterline (L_vilm's beach lies 0-20 cm above the sea, so no height ramp toward the water
    # holds), in patches; not a band (operator, #71). The floor material's own litter band (LitterWidth) is too narrow
    # to hold a 2 m vertex. Not masked by T_GroundcoverMask: the shore path is bare of plants, not of blown leaves.
    sand_reach = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": g.node(unreal.MaterialExpressionConstant, 4, r=0.0),
                                                                "Max": g.node(unreal.MaterialExpressionConstant, 4, r=SAND_LITTER_ABOVE_CM),
                                                                "Value": z})
    sand_patches = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": p["GrassRunLow"], "Max": p["GrassRunHigh"],
                                                                  "Value": g.noise(4, SAND_LITTER_NOISE_CM)})
    sand_litter = g.wire(unreal.MaterialExpressionMultiply, 1, {"A": g.wire(unreal.MaterialExpressionMultiply, 2, {
        "A": sand_reach, "B": sand_mask}), "B": sand_patches})
    w_low, w_full_low, w_full_high, w_high = (g.node(unreal.MaterialExpressionConstant, 4, r=v) for v in WATERLINE_CM)
    waterline_band = g.wire(unreal.MaterialExpressionMultiply, 2, {
        "A": g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": w_low, "Max": w_full_low, "Value": z}),
        "B": g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": w_high, "Max": w_full_high, "Value": z})})
    clusters = g.wire(unreal.MaterialExpressionSmoothStep, 3, {"Min": g.node(unreal.MaterialExpressionConstant, 4, r=0.55),
                                                              "Max": g.node(unreal.MaterialExpressionConstant, 4, r=0.7),
                                                              "Value": g.noise(4, WATERLINE_NOISE_CM)})
    waterline = g.wire(unreal.MaterialExpressionMultiply, 1, {"A": g.wire(unreal.MaterialExpressionMultiply, 2, {
        "A": waterline_band, "B": sand_mask}), "B": clusters})
    dry_sand = g.wire(unreal.MaterialExpressionMultiply, 1, {"A": sand_mask, "B": g.wire(
        unreal.MaterialExpressionSmoothStep, 2, {"Min": w_full_high, "Max": w_high, "Value": z})})
    weights = {"Groundcover": (weight, grass_type())}
    for name, (asset, variants, density, cull, scale, kind) in GRASS_LAYERS.items():
        if kind in ("sand", "waterline", "dry sand"):
            layer = {"sand": sand_litter, "waterline": waterline, "dry sand": dry_sand}[kind]
        else:
            layer = floor if kind == "all" else g.wire(unreal.MaterialExpressionMultiply, 1, {"A": floor, "B": where[kind]})
        weights[name] = (layer, grass_type(asset, variants, density, cull, scale))
    output = g.node(unreal.MaterialExpressionLandscapeGrassOutput, 0)
    inputs = []
    for name, (_, grass) in weights.items():
        grass_input = unreal.GrassInput()
        grass_input.set_editor_property("name", name)
        grass_input.set_editor_property("grass_type", grass)
        inputs.append(grass_input)
    output.set_editor_property("grass_types", inputs)
    for name, (layer, _) in weights.items():
        if not mel.connect_material_expressions(layer, "", output, name):
            raise SystemExit(f"could not connect the {name} weight")

    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(normal, "", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(g.mask(orm, 0, "r"), "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)

    instance = matgraph.instance_of(f"{FOLDER}/MI_ForestFloor", material)
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
