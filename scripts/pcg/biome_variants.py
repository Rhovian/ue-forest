"""Append (Megascans-relative mesh path, relative weight) rows to extend each palette."""

VENDOR = "/Game/Fab/Megascans/3D/"
LOG_VARIANTS = [
    ("Nordic_Forest_Tree_Fallen_Medium_xicmfco/Medium/xicmfco_tier_2/StaticMeshes/xicmfco_tier_2", 0.85),
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 0.15),
]
STUMP_VARIANTS = [
    ("Old_Tree_Stump_wd0qcaobw/Medium/wd0qcaobw_tier_2/StaticMeshes/wd0qcaobw_tier_2", 1),
]
SLAB_VARIANTS = [
    ("Limestone_Slab_ubxbadpda/Medium/ubxbadpda_tier_2/StaticMeshes/ubxbadpda_tier_2", 1),
]
FUNGI_VARIANTS = [
    ("Bolete_Mushrooms_pdvcB/Medium/pdvcB_tier_2/StaticMeshes/pdvcB_LOD0_TIER2_000", 1),
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
]
FERN_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/Beech_Fern_vmkpdbeia/Medium/vmkpdbeia_tier_2/StaticMeshes/SM_vmkpdbeia_VarA", 1),
]
HERB_VARIANTS = [
    ("/Game/Megaplant_Library/Plant_Wood_Anemone/Plant_Wood_Anemone_01/Plant_Wood_Anemone_01_A", 1),
]
IVY_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/StaticMeshes/SM_xfcnebhqx_VarA", 1),
]
