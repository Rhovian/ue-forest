"""Append (Megascans-relative mesh path, relative weight) rows to extend each palette."""

VENDOR = "/Game/Fab/Megascans/3D/"
LOG_VARIANTS = [
    ("Nordic_Forest_Tree_Fallen_Medium_xicmfco/Medium/xicmfco_tier_2/StaticMeshes/xicmfco_tier_2", 0.85),
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 0.15),
    ("Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/StaticMeshes/wgrubc1s_tier_2", 0.15),
]
# Fallen logs lying in the meadow stretches (#38): only the short piece, whose footprint the meadow ground filter covers;
# the long trunks need deadwood_rocks.py's reach-aware water keepout and 8-degree support limit.
# Logs placed across the lake shoreline (shore_logs.py, #114): long trunks that read from the bank views.
SHORE_LOG_VARIANTS = [
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 1),
]
MEADOW_LOG_VARIANTS = [
    ("Nordic_Forest_Tree_Fallen_Medium_xicmfco/Medium/xicmfco_tier_2/StaticMeshes/xicmfco_tier_2", 1),
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
SOLID_SCANS = {VENDOR + path for path, _ in LOG_VARIANTS + STUMP_VARIANTS + SLAB_VARIANTS}

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
FERN_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/StaticMeshes/SM_vmkpdbeia_VarA", 1),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarA", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarB", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarC", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarD", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarE", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarF", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarG", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarH", 0.15),
    ("/Game/Fab/Megascans/Plants/Lady_Fern_wdvlditia/Medium/wdvlditia_tier_2/StaticMeshes/SM_wdvlditia_VarI", 0.15),
]
# Veteran beech (#80, interior_01's massive old trunks): the Megascans open-grown field tree, a static Nanite mesh.
VETERAN_VARIANTS = [
    ("/Game/EuropeanBeech/Geometry/SimpleWind/SM_EuropeanBeech_Field_01", 1),
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
IVY_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/StaticMeshes/SM_xfcnebhqx_VarA", 1),
]

# Project Nature Foliage Collection (#98), qualified in the interior and on the stream bank. The rest of the pack
# (wispy and straw-headed meadow grasses, tall pale ground stalks, single-stem meadow flowers) was deleted.
# Low connector between fern colonies (#100): soft green tufts and small leafy rosettes, ankle high.
GROUNDCOVER_VARIANTS = [
    ("/Game/PN_FoliageCollection/Meshes/grassMesh/lowGrass_01_01_SM", 4),
    ("/Game/PN_FoliageCollection/Meshes/grassMesh/lowGrass_01_02_SM", 4),
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
