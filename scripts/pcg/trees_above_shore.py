"""Build the Trees group's shore filter graph, /Game/ForestBiome/PCG_TreesAboveShore.

    scripts/editor-py scripts/pcg/trees_above_shore.py [--shore CM] [--bands TOP:KEEP,...]

Removes points below the shore height (default: MI_ForestFloor's ShoreHeight, so trees meet the forest
floor where the sand ends), then thins the forest edge: points up to TOP cm above the shore keep the
KEEP fraction of trees (random, seeded), bands applied in order, everything higher kept.
Default bands 150:0.35,350:0.7: on Vilm's gentle shore, roughly the first 20 m and 40 m inland. Regenerate the Biome Core afterwards.
"""

import argparse

import unreal

GRAPH = "/Game/ForestBiome/PCG_TreesAboveShore"
FLOOR = "/Game/ForestBiome/MI_ForestFloor"
NUMBER = (
    "(bInclusive={inc},bUseConstantThreshold=True,ThresholdAttribute=PCGBegin($Density)PCGEnd,"
    "bUseSpatialQuery=False,bFilterEachInputWithEachFilterDataRespectively=False,"
    "AttributeTypes=(Type=Double,DoubleValue={value}))"
)


def shore_height():
    instance = unreal.load_asset(FLOOR)
    if instance is not None:
        for value in instance.get_editor_property("scalar_parameter_values"):
            if value.get_editor_property("parameter_info").get_editor_property("name") == "ShoreHeight":
                return value.get_editor_property("parameter_value")
    return 150.0


def z_range(graph, low, high):
    """A node keeping points with low <= Z < high on InsideFilter, the rest on OutsideFilter."""
    node, settings = graph.add_node_of_type(unreal.PCGAttributeFilteringRangeSettings)
    selector = unreal.PCGAttributePropertyInputSelector()
    selector.import_text("PCGBegin($Position.Z)PCGEnd")
    settings.set_editor_property("target_attribute", selector)
    for name, value, inclusive in (("min_threshold", low, True), ("max_threshold", high, False)):
        threshold = unreal.PCGAttributeFilterThresholdSettings()
        threshold.import_text(NUMBER.format(inc=inclusive, value=value))
        settings.set_editor_property(name, threshold)
    return node


def main():
    parser = argparse.ArgumentParser(prog="trees_above_shore.py")
    parser.add_argument("--shore", type=float, default=None, help="cm above sea level; default MI_ForestFloor")
    parser.add_argument("--bands", default="150:0.35,350:0.7", help="TOP:KEEP pairs, TOP in cm above the shore")
    args = parser.parse_args()
    shore = shore_height() if args.shore is None else args.shore
    bands = [(float(top), float(keep)) for top, keep in (pair.split(":") for pair in args.bands.split(","))]

    graph = unreal.load_asset(GRAPH)
    keep_io = {graph.get_input_node(), graph.get_output_node()}
    for node in [n for n in graph.get_editor_property("nodes") if n not in keep_io]:
        graph.remove_node(node)
    inp, out = graph.get_input_node(), graph.get_output_node()
    merge, _ = graph.add_node_of_type(unreal.PCGMergeSettings)

    above = z_range(graph, shore, 1.0e7)
    graph.add_edge(inp, "In", above, "In")
    remaining, pin = above, "InsideFilter"
    for i, (top, keep) in enumerate(bands):
        band = z_range(graph, shore, shore + top)
        graph.add_edge(remaining, pin, band, "In")
        choice, settings = graph.add_node_of_type(unreal.PCGRandomChoiceSettings)
        settings.set_editor_property("fixed_mode", False)  # defaults to keeping exactly FixedNumber (1) point
        settings.set_editor_property("ratio", keep)
        settings.set_editor_property("seed", 1000 + i)
        graph.add_edge(band, "InsideFilter", choice, "In")
        graph.add_edge(choice, "Chosen", merge, "In")
        remaining, pin = band, "OutsideFilter"
    graph.add_edge(remaining, pin, merge, "In")
    graph.add_edge(merge, "Out", out, "Out")
    # add_edge fails silently on a wrong pin label: every band plus the remainder must reach the merge.
    merged = sum(len(pin.get_editor_property("edges")) for pin in merge.get_editor_property("input_pins"))
    if merged != len(bands) + 1:
        raise SystemExit(f"{GRAPH}: merge has {merged} inputs, expected {len(bands) + 1}")
    unreal.EditorAssetLibrary.save_loaded_asset(graph, False)
    print(f"{GRAPH}: shore {shore:.0f} cm, bands {bands}")


if __name__ == "__main__":
    main()
