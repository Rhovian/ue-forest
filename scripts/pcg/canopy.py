# editor-py: fresh-siblings
"""Canopy closure for the Forest Biome Trees group (#31).

    scripts/editor-py scripts/pcg/canopy.py

canopy_up_01 wants the sky in at most ~15% of the `canopy_up` frame. Larger crowns close the canopy without adding
trees: at the stock 190 candidates/ha, scale 0.8-1.2 left a mean 30% sky over 30 upward views in the forest, scale
1.3-1.7 leaves 13%. Raising density instead needed 450/ha (2.4x the trees) for 14%. Saves the generator graph; the
lead regenerates Core and saves the level.
"""

import unreal
from deadwood_rocks import ROOT, area_parent, area_ranges, forest_floor_cells, load, save

PARAMETERS = {  # tree generator graph parameter -> value
    "PointsPerSquareMeter": 0.019,  # 190 candidates/ha, unchanged
    # Age roles (#71 item 3): 1.1-1.9 keeps the 1.3-1.7 mean and about the same mean crown area (E[s^2] 2.30 vs
    # 2.26), but trunks and crown heights now range from young-mature to old.
    "ScaleMin": unreal.Vector(1.1, 1.1, 1.1),
    "ScaleMax": unreal.Vector(1.9, 1.9, 1.9),
}

graph = load(ROOT + "PCG_Forest_TreesGenerator")
# #247: the Trees sample only the ground their filter (PCG_TreesAboveShore) can keep. The instance keeps the template's
# defaults for everything but PARAMETERS, so its density is what the measured ranges depend on. Other generators are
# copied from this instance, so generator() sets each copy's parent itself.
TEMPLATE_SWITCHES = {"EnableSpatialNoise": True, "EnableVoronoiNoiseBreakup": False}  # the template's, kept here
ranges = area_ranges("Trees", {"PointsPerSquareMeter": PARAMETERS["PointsPerSquareMeter"]} | TEMPLATE_SWITCHES)
parent = area_parent("Trees", forest_floor_cells(), ranges)
if graph.get_editor_property("graph") != parent:  # resets the overrides, so PARAMETERS are set after it
    graph.set_editor_property("graph", parent)
helpers = unreal.PCGGraphParametersHelpers
for name, value in PARAMETERS.items():
    if isinstance(value, unreal.Vector):
        helpers.set_vector_parameter(graph, name, value)
    else:
        helpers.set_double_parameter(graph, name, value)
save(graph)
print(f"Trees generator: {PARAMETERS}")
