"""Append (Megascans-relative mesh path, relative weight) rows to extend each palette."""

VENDOR = "/Game/Fab/Megascans/3D/"
# Round trunks only (operator, 2026-11-09): the flattened Nordic_Forest_Tree_Fallen_Medium (2.7 m long, 14 cm tall)
# sank into slopes and showed as flat brown ovals, and logs should read bigger. asset_path() resolves each row.
LOG_VARIANTS = [
    ("Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/StaticMeshes/wgrubc1s_tier_2", 0.45),  # 6 m
    ("/Game/Megascans/3D_Assets/MossyTree/SM_MossyTree_01", 0.3),  # 7.8 m, mossy (Electric Dreams)
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 0.25),  # 17 m
]
# Fallen logs lying in the meadow stretches (#38): only the short piece, whose footprint the meadow ground filter covers;
# the long trunks need deadwood_rocks.py's reach-aware water keepout and 8-degree support limit.
# Logs placed across the lake shoreline (shore_logs.py, #114): long trunks that read from the bank views.
SHORE_LOG_VARIANTS = [
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 1),
]
MEADOW_LOG_VARIANTS = [  # the 6 m round trunk: the flattened Nordic piece showed as flat ovals (operator, 2026-11-09)
    ("Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/StaticMeshes/wgrubc1s_tier_2", 1),
]
STUMP_VARIANTS = [
    ("Old_Tree_Stump_wd0qcaobw/Medium/wd0qcaobw_tier_2/StaticMeshes/wd0qcaobw_tier_2", 1),
]
SLAB_VARIANTS = [
    ("Limestone_Slab_ubxbadpda/Medium/ubxbadpda_tier_2/StaticMeshes/ubxbadpda_tier_2", 1),
    ("Mossy_Forest_Boulder_wc1kebr/Medium/wc1kebr_tier_2/StaticMeshes/wc1kebr_tier_2", 0.15),
    ("Mossy_Forest_Boulder_wdbncbl/Medium/wdbncbl_tier_2/StaticMeshes/wdbncbl_tier_2", 0.15),
    ("Mossy_Forest_Boulder_wfstcdnaw/Medium/wfstcdnaw_tier_2/StaticMeshes/wfstcdnaw_tier_2", 0.15),
    ("Mossy_Forest_Boulder_wfstchwaw/Medium/wfstchwaw_tier_2/StaticMeshes/wfstchwaw_tier_2", 0.15),
]
FUNGI_VARIANTS = [
    ("Bolete_Mushrooms_pdvcB/Medium/pdvcB_tier_2/StaticMeshes/pdvcB_LOD0_TIER2_000", 1),
]
# Small bleached driftwood pieces (0.6-1.3 m) scattered on the beach (#38, debris; no collision).
DRIFTWOOD_VARIANTS = [
    ("Coast_African_Debris_Driftwood_S_01_xlnndfv/Medium/SM_xlnndfv_tier_2/StaticMeshes/SM_xlnndfv_tier_2", 1),
    ("Coast_African_Debris_Driftwood_S_02_xlnnden/Medium/SM_xlnnden_tier_2/StaticMeshes/SM_xlnnden_tier_2", 1),
    ("Coast_African_Debris_Driftwood_S_04_xlkoadp/Medium/SM_xlkoadp_tier_2/StaticMeshes/SM_xlkoadp_tier_2", 1),
    ("Coast_African_Debris_Driftwood_S_06_xlkoaaw/Medium/SM_xlkoaaw_tier_2/StaticMeshes/SM_xlkoaaw_tier_2", 1),
    ("Coast_African_Debris_Driftwood_S_07_xlknfje/Medium/SM_xlknfje_tier_2/StaticMeshes/SM_xlknfje_tier_2", 1),
]


def asset_path(path):
    """A palette row's package path: rows are VENDOR-relative unless they start with "/Game/" (#147 review)."""
    return path if path.startswith("/Game/") else VENDOR + path


SOLID_SCANS = {asset_path(path) for path, _ in LOG_VARIANTS + STUMP_VARIANTS + SLAB_VARIANTS}

# Plant palettes use full /Game paths (PVE exports and Megascans Plants share no vendor root).
SAPLING_VARIANTS = [
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_A", 1),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_B", 1),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_D", 1),
]
SHRUB_VARIANTS = [
    ("/Game/Megaplant_Library/Shrub_Huckleberry_Oak/Shrub_Huckleberry_Oak_01/Shrub_Huckleberry_Oak_01_A", 1),
    # Hazel A and B were removed: bone reduction cannot reduce them (#52).
    ("/Game/Megaplant_Library/Tree_Common_Hazel/Tree_Common_Hazel_01/Tree_Common_Hazel_01_C", 1),
    ("/Game/Megaplant_Library/Tree_Common_Hazel/Tree_Common_Hazel_01/Tree_Common_Hazel_01_D", 1),
]
# Broad waist-to-head shrub masses in the canopy gaps (clearing_02): the tall hazel only, not the low huckleberry oak.
GAP_SHRUB_VARIANTS = [
    ("/Game/Megaplant_Library/Tree_Common_Hazel/Tree_Common_Hazel_01/Tree_Common_Hazel_01_C", 1),
    ("/Game/Megaplant_Library/Tree_Common_Hazel/Tree_Common_Hazel_01/Tree_Common_Hazel_01_D", 1),
]
FAB_PLANTS = "/Game/Fab/Megascans/Plants/"
# Fern colonies, one kind per drift (#142; operator 2026-11-09: the Olympic rainforests layer several ferns, the floor
# showed one). saplings_understory.py places each list as its own drifts, FERN_COLONY_SHARES of the fern density.
# Lady fern: lacy, bright, up to 2 m.
FERN_VARIANTS = [
    *[(f"{FAB_PLANTS}Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_Var{v}", 1) for v in "ABCDEFGHI"],
]
# Sword-fern stand-in: Electric Dreams' Fern, long once-divided fronds in fountains.
SWORD_FERN_VARIANTS = [
    *[(f"/Game/Megascans/3D_Plants/Fern/SM_Fern_0{i}", 1) for i in range(1, 7)],
]
# Deer-fern stand-in: Silver Lady Fern, lower narrow-frond rosettes.
DEER_FERN_VARIANTS = [
    *[(f"/Game/Megascans/3D_Plants/SilverLadyFern/SM_SilverLadyFern_0{i}", 1) for i in range(1, 8)],
]
# Beech fern: low triangular fronds, an oak-fern stand-in.
BEECH_FERN_VARIANTS = [
    *[(f"{FAB_PLANTS}Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/StaticMeshes/SM_vmkpdbeia_Var{v}", 1) for v in "ABCDEFGH"],
]
FERN_COLONY_SHARES = {"Ferns": 0.35, "SwordFerns": 0.3, "DeerFerns": 0.2, "BeechFerns": 0.15}
# The Trees group's canopy (DA_Forest_TreesAssets, canopy_trees.py; #144). Operator decision (2026-11-09): spruce leads,
# toward the Olympic rainforests' Sitka spruce and hemlock, with maple (bigleaf maple's role), cypress (redcedar's) and
# alder (red alder's) mixed in and beech one tree of the mix. Shares: spruce 45%, beech 20%, maple 15%, cypress and
# alder 10% each, split evenly across each species' variants. Every listed tree was re-exported from PVE under the bone
# budget with Trunk Only collision; the variants that could not be yet (and the saplings) are on #154's list.
MEGAPLANTS = "/Game/Megaplant_Library/"
TREE_VARIANTS = [
    *[(f"{MEGAPLANTS}Tree_Norway_Spruce/Tree_Norway_Spruce_01/Tree_Norway_Spruce_01_{v}", 45 / 4) for v in "ABCD"],
    *[(f"{MEGAPLANTS}Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_{v}", 20 / 4) for v in "ABCD"],
    *[(f"{MEGAPLANTS}Tree_Norway_Maple/Tree_Norway_Maple_Forest_01/Tree_Norway_Maple_Forest_01_{v}", 15)
      for v in "A"],
    *[(f"{MEGAPLANTS}Tree_Japanese_Cypress/Tree_Japanese_Cypress_01/Tree_Japanese_Cypress_01_{v}", 10 / 2)
      for v in "BF"],
    *[(f"{MEGAPLANTS}Tree_Black_Alder/Tree_Black_Alder_01/Tree_Black_Alder_01_{v}", 10 / 2) for v in "BC"],
]
# Veteran beech (#80, interior_01's massive old trunks): the Megascans open-grown field tree, a static Nanite mesh.
VETERAN_VARIANTS = [
    ("/Game/EuropeanBeech/Geometry/SimpleWind/SM_EuropeanBeech_Field_01", 1),
]
# Hornbeam among the beech (#125; operator, 2026-11-08): Electric Dreams' Megascans European hornbeam, static Nanite
# forest trees. Forest_09 (6 m) is a sapling-sized tree and stays out; the Field trees are open-grown, wide-crowned
# (12-16 m across) and stay out of the closed forest (lead ruling on #125).
HORNBEAM_VARIANTS = [
    *[(f"/Game/Megascans/3D_Plants/EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Forest_{i:02}", 1)
      for i in (1, 2, 3, 4, 5, 6, 7, 8, 10)],
]
# Lone large beech standing on the sand (#38, edge_in_05, beach_01); the Trees group's own copies of these meshes.
SHORE_TREE_VARIANTS = [
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_A", 1),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_C", 1),
]
# Meadow grass for the grassy coast stretches (#38, edge_in_04).
GRASS_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/StaticMeshes/SM_skFjJ_VarA", 1),
    ("/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/StaticMeshes/SM_skFjJ_VarB", 1),
    ("/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/StaticMeshes/SM_skFjJ_VarC", 1),
    ("/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/StaticMeshes/SM_skFjJ_VarD", 1),
    ("/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/StaticMeshes/SM_skFjJ_VarE", 1),
]
# Children of logs and rocks (#32 nurse_log_01, rock_assembly_01). Only the 1 m sapling fits on a log as a seedling.
SEEDLING_VARIANTS = [
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_D", 1),
]
BASE_PLANT_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/StaticMeshes/SM_vmkpdbeia_VarA", 1),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarB", 0.3),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarE", 0.3),
    ("/Game/Megaplant_Library/Plant_Wood_Anemone/Plant_Wood_Anemone_01/Plant_Wood_Anemone_01_A", 1),
]
HERB_VARIANTS = [
    ("/Game/Megaplant_Library/Plant_Wood_Anemone/Plant_Wood_Anemone_01/Plant_Wood_Anemone_01_A", 1),
]
# Second flower colour (#82): small pale yellow balsam, a beech-wood floor and bank plant, in its own colonies.
BALSAM_VARIANTS = [
    ("/Game/Megaplant_Library/Plant_Small_Balsam/Plant_Small_Balsam_01/Plant_Small_Balsam_01_A", 1),
    ("/Game/Megaplant_Library/Plant_Small_Balsam/Plant_Small_Balsam_01/Plant_Small_Balsam_01_B", 1),
    ("/Game/Megaplant_Library/Plant_Small_Balsam/Plant_Small_Balsam_01/Plant_Small_Balsam_01_C", 1),
    ("/Game/Megaplant_Library/Plant_Small_Balsam/Plant_Small_Balsam_01/Plant_Small_Balsam_01_D", 1),
    ("/Game/Megaplant_Library/Plant_Small_Balsam/Plant_Small_Balsam_01/Plant_Small_Balsam_01_E", 1),
]
# Pink-purple heather (#82) in drifts on the sunny meadow stretches (meadow.py), not the shaded beech floor.
HEATHER_VARIANTS = [
    ("/Game/Megaplant_Library/Shrub_Heather/Shrub_Heather_01/Shrub_Heather_01_A", 1),
    ("/Game/Megaplant_Library/Shrub_Heather/Shrub_Heather_01/Shrub_Heather_01_B", 1),
    ("/Game/Megaplant_Library/Shrub_Heather/Shrub_Heather_01/Shrub_Heather_01_C", 1),
    ("/Game/Megaplant_Library/Shrub_Heather/Shrub_Heather_01/Shrub_Heather_01_D", 1),
    ("/Game/Megaplant_Library/Shrub_Heather/Shrub_Heather_01/Shrub_Heather_01_E", 1),
    ("/Game/Megaplant_Library/Shrub_Heather/Shrub_Heather_01/Shrub_Heather_01_F", 1),
]
# Ivy sheets baked up the lower trunks (trunk_ivy.py, #121, canopy_up_01 "several trunks ivy-covered"): Electric
# Dreams' English ivy, flat sheets with their leaves toward +Y.
# Over slab corners, where the sheets lie on the faces they cover.
SLAB_IVY_VARIANTS = [(f"/Game/Megascans/3D_Plants/EnglishIvy/SM_EnglishIvy_0{i}", 1) for i in range(1, 9)]
# Up tree trunks: only the narrow strands (7-48 cm wide). The 0.6-1.3 m wide sheets stood off a 40-80 cm trunk like
# fins, a fuzzy column with no trunk visible inside (#156).
TRUNK_IVY_VARIANTS = [(f"/Game/Megascans/3D_Plants/EnglishIvy/SM_EnglishIvy_0{i}", w) for i, w in ((2, 1), (5, 1), (6, 0.5))]
# Trees whose every copy carries trunk ivy: two of the four forest beech (half the Trees group; with one, canopy_up
# showed no ivy-covered trunk, #132 review), the veterans, and two of the hornbeam variants (those with a Trunk slot).
IVY_TREES = [  # (tree, coverage): coverage scales the share of trunk the strands cover (#156)
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_A", 1.6),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_C", 1.6),
    # The veteran's trunk is 1.5-2 m across: full coverage hid it inside a column of ivy (spot3).
    ("/Game/EuropeanBeech/Geometry/SimpleWind/SM_EuropeanBeech_Field_01", 0.45),
    ("/Game/Megascans/3D_Plants/EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Forest_04", 1.0),
    ("/Game/Megascans/3D_Plants/EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Forest_07", 1.0),
]
# Slabs and boulders with ivy spilling over one corner (trunk_ivy.py, #121, rock_assembly_01): all of them, as the
# rock_assembly view's own rock is a boulder (#132 review).
IVY_SLABS = [VENDOR + path for path, _ in SLAB_VARIANTS]
IVY_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/StaticMeshes/SM_xfcnebhqx_VarA", 1),
]

# Project Nature Foliage Collection (#98), qualified in the interior and on the stream bank. The rest of the pack
# (wispy and straw-headed meadow grasses, tall pale ground stalks, single-stem meadow flowers) was deleted.
# Low connector between fern colonies (#100): soft green tufts and small leafy rosettes, ankle high.
ED = "/Game/Megascans/3D_Plants/"  # Electric Dreams sample plants (free on Fab), an art-direction reference (operator, 2026-11-08)
EDA = "/Game/Megascans/3D_Assets/"
GROUNDCOVER_VARIANTS = [
    ("/Game/PN_FoliageCollection/Meshes/grassMesh/lowGrass_01_01_SM", 1.5),  # less grass, more plants (operator, 2026-11-08)
    ("/Game/PN_FoliageCollection/Meshes/grassMesh/lowGrass_01_02_SM", 1.5),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_01_01", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_01_02", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_01_03", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_01_04", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_01_05", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_02_01", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_02_02", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_02_03", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_02_04", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_02_05", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_03_01", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_03_02", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_03_03", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_03_04", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_03_05", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_03_06", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_04_01", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_04_02", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_04_03", 1),
    ("/Game/PN_FoliageCollection/Meshes/groundPlantMesh/ground_04_04", 1),
    *[(f"{ED}GroundCover/SM_GroundCover_0{i}", 1.5) for i in range(1, 9)],
    *[(f"{ED}MoneyPlant/SM_MoneyPlant_0{i}", 1) for i in range(1, 7)],
    *[(f"{ED}PurpleShamrock/SM_PurpleShamrock_0{i}", 1) for i in range(1, 4)],
    *[(f"{ED}CommonPurslane/SM_CommonPurslane_0{i}", 0.7) for i in range(1, 6)],
    *[(f"{ED}JungleGinger/SM_JungleGinger_0{i}", 1) for i in (2, 3, 4, 5)],
    *[(f"{ED}RedLachenalia/SM_RedLachenalia_{i:02}", 0.15) for i in (1, 2, 3, 4, 6, 12, 13, 14)],
    *[(f"{ED}CanePalm/SM_CanePalm_0{i}", 0.5) for i in range(1, 5)],
    # #121: the sample's Nanite beech fern (the leafy variants; 01-03, 06-08 are single fronds) and woodland flowers.
    *[(f"{ED}BeechFern/SM_BeechFern_{i:02}", 1) for i in (4, 5, 9, 10, 11, 12, 13, 15)],
    *[(f"{ED}LilyOfTheValley/SM_LilyOfTheValley_0{i}", 0.6) for i in range(1, 5)],
    *[(f"{ED}YellowArchangel/SM_YellowArchangel_0{i}", 0.5) for i in (4, 8)],
]
# Knee-to-head plants in colonies between the groundcover runs (operator, 2026-11-08: less grass, denser plant life).
UNDERGROWTH_VARIANTS = [
    *[(f"{ED}Taro/SM_Taro_{i:02}", 1) for i in range(1, 11)],
    *[(f"{ED}JungleGinger/SM_JungleGinger_0{i}", 1) for i in (1, 6, 7, 8, 9)],
    *[(f"{ED}Crownbeard/SM_Crownbeard_{i:02}", 0.15) for i in range(3, 11)],
    *[(f"{ED}PinkCordyline/SM_PinkCordyline_0{i}", 0.25) for i in range(1, 9)],
    *[(f"{ED}ArrowheadPlant/SM_ArrowheadPlant_0{i}", 1) for i in range(1, 6)],
    *[(f"{ED}Fern/SM_Fern_0{i}", 1.5) for i in range(1, 7)],
    *[(f"{ED}BroadleafLadyPalm/SM_BroadleafLadyPalm_0{i}", 0.6) for i in range(1, 6)],
    *[(f"{ED}CatPalm/SM_CatPalm_0{i}", 0.6) for i in range(1, 5)],
    *[(f"{ED}ZamiaPalm/SM_ZamiaPalm_0{i}", 0.5) for i in range(1, 4)],
    *[(f"{ED}Elderberry/SM_Elderberry_{i:02}", 1) for i in range(1, 14)],
    *[(f"{ED}CastorOilPlant/SM_CastorOilPlant_0{i}", 0.4) for i in range(1, 5)],
    *[(f"{ED}Amaryllis/SM_Amaryllis_0{i}", 0.05) for i in range(1, 5)],
    *[(f"{ED}VariegatedCroton/SM_VariegatedCroton_0{i}", 0.3) for i in range(1, 6)],
    *[(f"{ED}DragonTree/SM_DragonTree_0{i}", 0.3) for i in range(1, 6)],
    *[(f"{ED}EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Sapling_0{i}", 0.6) for i in range(1, 9)],
    *[(f"{ED}EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Seedling_0{i}", 0.6) for i in range(1, 6)],
    # #121: silver lady fern, white windflower, and periwinkle for the blue-violet accent.
    *[(f"{ED}SilverLadyFern/SM_SilverLadyFern_0{i}", 1) for i in range(1, 4)],
    *[(f"{ED}WhiteWindflower/SM_WhiteWindflower_0{i}", 0.3) for i in range(1, 8)],
    *[(f"{ED}Periwinkle/SM_Periwinkle_0{i}", 0.6) for i in range(1, 5)],
]
# Small debris over the whole forest floor: pebbles, twigs, dry branches and leaf-litter mats.
DEBRIS_VARIANTS = [
    *[(f"{EDA}SmallStonesPack/SM_SmallStonesPack_{i:02}", 1) for i in range(1, 15)],
    *[(f"{EDA}WoodenSticksAndTwigs/SM_WoodenSticksAndTwigs_{i:02}", 1.5) for i in range(1, 11)],
    *[(f"{EDA}DryBranches/SM_DryBranches_0{i}", 1) for i in range(1, 9)],
    (f"{EDA}OakBranch/SM_OakBranch_01", 1),
]
# Leaf drifts on the forest floor: flat 0.8-1.7 m leaf mats, placed smaller than the debris (forest_floor.py's Leaves
# layer). At the debris' 1-2.5x they lay as 4 m brown rugs that read as cut-outs on slopes (operator, 2026-11-09).
LEAF_LITTER_VARIANTS = [
    *[(f"{ED}DeadLeaves/SM_DeadLeaves_{i:02}", 1) for i in (1, 12, 13, 14)],
]
# Litter blown out onto the sand above the waterline, in forest_floor.py's own SandLitter patches (transition_ground_01),
# not a band.
SAND_LITTER_VARIANTS = [
    *[(f"{EDA}WoodenSticksAndTwigs/SM_WoodenSticksAndTwigs_{i:02}", 1) for i in range(1, 11)],
    *[(f"{EDA}DryBranches/SM_DryBranches_0{i}", 1) for i in range(1, 9)],
    (f"{ED}DeadLeaves/SM_DeadLeaves_12", 3),  # the 0.8 m mat only: the 1.7 m ones at this scale lay as 3 m rugs
]
# Leaf litter piled where logs and slabs meet the ground (#117, nurse_log_01, rock_assembly_01): deadwood_rocks.py
# places these as children along each log's sides and round each slab's base.
CONTACT_LITTER_VARIANTS = [  # the 0.8 m leaf mat only: the 1.7 m ones read as flat brown rugs (operator, 2026-11-09)
    (f"{ED}DeadLeaves/SM_DeadLeaves_12", 4),
    *[(f"{EDA}DryBranches/SM_DryBranches_0{i}", 0.3) for i in range(1, 9)],
]
# Beach stones (#122, beach_01/02: limestone stones clustered at the waterline, sparse on dry sand).
WATERLINE_STONE_VARIANTS = [  # 10-26 cm stones, scaled up
    (f"{EDA}NordicBeachRock/SM_NordicBeachRock_01", 3),
    *[(f"{EDA}SmallStonesPack/SM_SmallStonesPack_{i:02}", 0.5) for i in range(1, 15)],
]
WATERLINE_BOULDER_VARIANTS = [
    (f"{EDA}NordicBeachRocks/SM_NordicBeachRocks_01", 1),
    *[(f"{EDA}NordicBoulder/SM_NordicBoulder_0{i}", 0.5) for i in range(1, 3)],
]
# Low plants a little way out onto the sand before the forest edge, in patches (#38; operator 2026-11-09: the edge
# was abrupt). Purslane mats for creeping beach plants, grass tufts for dune grass, a little beech fern spilling out.
# The heather (Megaplant, skinned) cannot be Landscape Grass.
SAND_EDGE_VARIANTS = [
    *[(f"{ED}CommonPurslane/SM_CommonPurslane_0{i}", 1) for i in range(1, 8)],
    # The meadow's reeds rather than grass blades, which read as stickers on the sand (#165, operator 2026-11-09).
    *[(f"{FAB_PLANTS}Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/StaticMeshes/SM_skFjJ_Var{v}", 1) for v in "ABCDE"],
    (f"{FAB_PLANTS}Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/StaticMeshes/SM_vmkpdbeia_VarA", 0.6),
    (f"{FAB_PLANTS}Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/StaticMeshes/SM_vmkpdbeia_VarC", 0.6),
]
# In the lake (#141; operator 2026-11-09: nothing grew or lay in it): stones over its bed in patches, and plants in
# its shallows. No water plants are installed: Taro (a wetland plant) and Arrowhead Plant's arrow leaves stand in.
LAKE_STONE_VARIANTS = [
    *[(f"{EDA}SmallStonesPack/SM_SmallStonesPack_{i:02}", 1) for i in range(1, 15)],
    *[(f"{EDA}MossyForestRock/SM_MossyForestRock_0{i}", 1.5) for i in range(1, 4)],
]
LAKE_PLANT_VARIANTS = [
    *[(f"{ED}Taro/SM_Taro_{i:02}", 1) for i in range(1, 11)],
    *[(f"{ED}ArrowheadPlant/SM_ArrowheadPlant_0{i}", 1) for i in range(1, 6)],
]
DRY_SAND_STONE_VARIANTS = [
    (f"{EDA}NordicBeachRock/SM_NordicBeachRock_01", 1),
    *[(f"{EDA}SmallStonesPack/SM_SmallStonesPack_{i:02}", 0.2) for i in range(1, 15)],
]
# Ground scans (root mats, rough terrain, stony path) and fallen branches, in patches.
SCAN_VARIANTS = [
    *[(f"{EDA}MossyForestRoots/SM_MossyForestRoots_0{i}", 1) for i in range(1, 4)],
    *[(f"{EDA}ForestRoots/SM_ForestRoots_0{i}", 1) for i in range(1, 3)],
    *[(f"{EDA}ForestTerrain/SM_ForestTerrain_0{i}", 1) for i in range(1, 3)],
    (f"{EDA}ForestGround/SM_ForestGround_01", 1),
    (f"{EDA}RockyForestPath/SM_RockyForestPath_01", 0.5),
    *[(f"{EDA}MossyRocks/SM_MossyRocks_0{i}", 0.7) for i in range(1, 3)],
    *[(f"{EDA}OldTreeBranch/SM_OldTreeBranch_0{i}", 0.4) for i in range(1, 7)],
]
# Foxglove spikes (~1 m, pink-violet): a violet accent readable at eye height on banks and in gaps (#105).
FOXGLOVE_VARIANTS = [
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_01", 1),
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_02", 1),
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_03", 1),
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_04", 1),
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_05", 1),
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_06", 1),
    ("/Game/PN_FoliageCollection/Meshes/flowerMesh/flower_10_07", 1),
]

# UE MaterialInstance.cpp:SetMaterialUsage automatically adds required shader usage bits
# when these static plants first spawn (Nanite/InstancedStaticMeshes/Voxels). Save only these MIs.
PLANT_USAGE_MATERIALS = {
    "/Game/Fab/Megascans/Plants/Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/Materials/MI_vmkpdbeia",
    "/Game/Fab/Megascans/Plants/Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/Materials/MI_vmkpdbeia_Billboard",
    "/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/Materials/MI_xfcnebhqx",
    "/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/Materials/MI_xfcnebhqx_Billboard",
    "/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/Materials/MI_wdvlditia",
    "/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/Materials/MI_wdvlditia_Billboard",
    "/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/Materials/MI_skFjJ",
    "/Game/Fab/Megascans/Plants/Rough_Meadow_Grass_skFjJ/Medium/skFjJ_tier_2/Materials/MI_skFjJ_Billboard",
    # Solid scans added for #32 get the same usage bits when first spawned.
    "/Game/Fab/Megascans/3D/Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/Materials/MI_wgrubc1s",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wc1kebr/Medium/wc1kebr_tier_2/Materials/MI_wc1kebr",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wdbncbl/Medium/wdbncbl_tier_2/Materials/MI_wdbncbl",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wfstcdnaw/Medium/wfstcdnaw_tier_2/Materials/MI_wfstcdnaw",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wfstchwaw/Medium/wfstchwaw_tier_2/Materials/MI_wfstchwaw",
}
