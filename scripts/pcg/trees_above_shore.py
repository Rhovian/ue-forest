# editor-py: fresh-siblings
"""Build the Trees group's shore filter graph, /Game/ForestBiome/PCG_TreesAboveShore.

    scripts/editor-py scripts/pcg/trees_above_shore.py [--shore CM] [--bands TOP:KEEP,...]

Removes points below the shore height (default: MI_ForestFloor's ShoreHeight, so trees meet the forest
floor where the sand ends). Optional bands thin the forest edge: points up to TOP cm above the shore keep the
KEEP fraction of trees (random, seeded), bands applied in order, everything higher kept. Default: no bands, an
abrupt living edge (#9 edge ruling, edge_in_01: closed forest within ~5-10 m of the sand; it replaced the former
150:0.35,350:0.7 thinning). Regenerate the Biome Core afterwards.
"""

import argparse
import sys
from pathlib import Path

import unreal

GRAPH = "/Game/ForestBiome/PCG_TreesAboveShore"
FLOOR = "/Game/ForestBiome/MI_ForestFloor"
LAND_Z = "LandZ"
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


def land_z(graph, source, pin):
    """Points from (source, pin) with LAND_Z: ground height plus the beach lift (#241), T_BeachLift's one baked line,
    which the floor material (forest_floor.py) and the forest foot (landheight.py) also read. Returns the node whose
    "Out" carries them. Samples a copy, so the points' own density and colour are untouched."""
    # Imported here, not at module load: offline tests import this module with a mocked unreal (test_budget.py).
    sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
    import beach_lift
    texture, settings = graph.add_node_of_type(unreal.PCGTextureSamplerSettings)  # "Get Texture Data"
    for name, value in {"texture": unreal.load_asset(f"/Game/ForestBiome/{beach_lift.NAME}"), "use_absolute_transform": True,
                        # Texture data spans local -1..1: the 1513 vertex samples cover +-HALF_CM (beach_lift.py).
                        "transform": unreal.Transform(scale=unreal.Vector(beach_lift.HALF_CM, beach_lift.HALF_CM, 1)),
                        "color_channel": unreal.PCGTextureColorChannel.RED, "use_density_source_channel": True,
                        "keep_zero_density_points": True, "filter": unreal.PCGTextureFilter.BILINEAR,
                        "force_editor_only_cpu_sampling": True}.items():
        settings.set_editor_property(name, value)
    sample, _ = graph.add_node_of_type(unreal.PCGSampleTextureSettings)  # density := lift on the copy
    link(graph, source, pin, sample, "Point")
    link(graph, texture, "Out", sample, "BaseTexture")
    lift = selector_node(graph, unreal.PCGCopyAttributesSettings, "$Density", "BeachLift", "input_source", "output_target")
    link(graph, sample, "Out", lift, "Source")
    link(graph, source, pin, lift, "Target")
    remap = selector_node(graph, unreal.PCGAttributeRemapSettings, "BeachLift", "BeachLiftCm", "input_source",
                          "output_target", range_min=0.0, range_max=1.0, out_range_min=0.0, out_range_max=float(beach_lift.LIFT_CM))
    link(graph, lift, "Out", remap, "In")
    total = selector_node(graph, unreal.PCGMetadataMathsSettings, "$Position.Z", LAND_Z, "input_source1",
                          "output_target", operation=unreal.PCGMetadataMathsOperation.ADD)
    second = unreal.PCGAttributePropertyInputSelector()
    second.import_text("PCGBegin(BeachLiftCm)PCGEnd")
    total.get_settings().set_editor_property("input_source2", second)
    for operand in ("InA", "InB"):  # each maths operand reads the data on its own pin
        link(graph, remap, "Out", total, operand)
    return total


def link(graph, source, source_pin, target, target_pin):
    """add_edge, failing loudly: UE 5.8 PCGGraph.cpp AddEdge returns the target node even when no edge was made."""
    def count():
        return sum(len(p.get_editor_property("edges")) for p in target.get_editor_property("input_pins"))
    before = count()
    graph.add_edge(source, source_pin, target, target_pin)
    if count() != before + 1:
        raise RuntimeError(f"PCG connection failed: {source_pin} -> {target_pin}")


def selector_node(graph, settings_class, source, target, source_name, target_name, **values):
    node, settings = graph.add_node_of_type(settings_class)
    selector, output = unreal.PCGAttributePropertyInputSelector(), unreal.PCGAttributePropertyOutputSelector()
    selector.import_text(f"PCGBegin({source})PCGEnd")
    output.import_text(f"PCGBegin({target})PCGEnd")
    settings.set_editor_property(source_name, selector)
    settings.set_editor_property(target_name, output)
    for name, value in values.items():
        settings.set_editor_property(name, value)
    return node


def shore_band(graph, low, high):
    """(first, last): LAND_Z >= low, then the true height below high, for bands whose top is not a shore line (the
    meadow's TOP, the damp ground's cap, the canopy gaps' ground): the lift is 1 across the whole interior, so lifting
    those tops would move them island-wide. Feed first's "In"; read last's InsideFilter and OutsideFilter."""
    first = z_range(graph, low, 1.0e7)
    last = z_range(graph, -1.0e7, high, "$Position.Z")
    link(graph, first, "InsideFilter", last, "In")
    return first, last


def z_range(graph, low, high, attribute=None):
    """A node keeping points with low <= LAND_Z (or attribute) < high on InsideFilter, the rest on OutsideFilter. The
    points must come through land_z."""
    node, settings = graph.add_node_of_type(unreal.PCGAttributeFilteringRangeSettings)
    selector = unreal.PCGAttributePropertyInputSelector()
    selector.import_text(f"PCGBegin({attribute or LAND_Z})PCGEnd")
    settings.set_editor_property("target_attribute", selector)
    for name, value, inclusive in (("min_threshold", low, True), ("max_threshold", high, False)):
        threshold = unreal.PCGAttributeFilterThresholdSettings()
        threshold.import_text(NUMBER.format(inc=inclusive, value=value))
        settings.set_editor_property(name, threshold)
    return node


def main():
    parser = argparse.ArgumentParser(prog="trees_above_shore.py")
    parser.add_argument("--shore", type=float, default=None, help="cm above sea level; default MI_ForestFloor")
    parser.add_argument("--bands", default="", help="TOP:KEEP pairs, TOP in cm above the shore; empty: none")
    args = parser.parse_args()
    shore = shore_height() if args.shore is None else args.shore
    bands = [(float(top), float(keep)) for top, keep in (pair.split(":") for pair in args.bands.split(",") if pair)]

    graph = unreal.load_asset(GRAPH)
    keep_io = {graph.get_input_node(), graph.get_output_node()}
    for node in [n for n in graph.get_editor_property("nodes") if n not in keep_io]:
        graph.remove_node(node)
    inp, out = graph.get_input_node(), graph.get_output_node()
    merge, _ = graph.add_node_of_type(unreal.PCGMergeSettings)

    above = z_range(graph, shore, 1.0e7)
    link(graph, land_z(graph, inp, "In"), "Out", above, "In")
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
