"""Append (Megascans-relative mesh path, relative weight) rows to extend each palette."""

VENDOR = "/Game/Fab/Megascans/3D/"
LOG_VARIANTS = [
    ("Nordic_Forest_Tree_Fallen_Medium_xicmfco/Medium/xicmfco_tier_2/StaticMeshes/xicmfco_tier_2", 0.95),
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 0.05),
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
