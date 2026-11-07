"""Append (Megascans-relative mesh path, relative weight) rows to extend each palette."""

VENDOR = "/Game/Fab/Megascans/3D/"
LOG_VARIANTS = [
    ("Nordic_Forest_Tree_Fallen_Medium_xicmfco/Medium/xicmfco_tier_2/StaticMeshes/xicmfco_tier_2", 0.85),
    ("Large_Fallen_Tree_wd1mbcvbw/Medium/wd1mbcvbw_tier_2/StaticMeshes/wd1mbcvbw_tier_2", 0.15),
    ("Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/StaticMeshes/wgrubc1s_tier_2", 0.15),
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
SOLID_SCANS = {VENDOR + path for path, _ in LOG_VARIANTS + STUMP_VARIANTS + SLAB_VARIANTS}

# Plant palettes use full /Game paths (PVE exports and Megascans Plants share no vendor root).
SAPLING_VARIANTS = [
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_A", 1),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_B", 1),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/Tree_European_Beech_Sapling_01_D", 1),
]
SHRUB_VARIANTS = [
    ("/Game/Megaplant_Library/Shrub_Huckleberry_Oak/Shrub_Huckleberry_Oak_01/Shrub_Huckleberry_Oak_01_A", 1),
    # Hazel A and B join after their bone-reduced re-export (#52).
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
# Lone large beech standing on the sand (#38, edge_in_05, beach_01); the Trees group's own copies of these meshes.
SHORE_TREE_VARIANTS = [
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_A", 1),
    ("/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_C", 1),
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
IVY_VARIANTS = [
    ("/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/StaticMeshes/SM_xfcnebhqx_VarA", 1),
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
    # Solid scans added for #32 get the same usage bits when first spawned.
    "/Game/Fab/Megascans/3D/Large_Fallen_Tree_wgrubc1s/Medium/wgrubc1s_tier_2/Materials/MI_wgrubc1s",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wc1kebr/Medium/wc1kebr_tier_2/Materials/MI_wc1kebr",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wdbncbl/Medium/wdbncbl_tier_2/Materials/MI_wdbncbl",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wfstcdnaw/Medium/wfstcdnaw_tier_2/Materials/MI_wfstcdnaw",
    "/Game/Fab/Megascans/3D/Mossy_Forest_Boulder_wfstchwaw/Medium/wfstchwaw_tier_2/Materials/MI_wfstchwaw",
}
