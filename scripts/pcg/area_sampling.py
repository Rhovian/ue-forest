"""Area-first sampling (#247): generator graphs whose sampler visits only the ground its family places on.

An area generator is a full copy of Biome Core's generator template with the Surface Sampler replaced by the Forest
Area Sampler (ForestPCGAreaSampler.h), fed by a Create Points node of tile boxes that cover the family's ground. The
sampler keeps the stock lattice, seeds and density rules, while also visiting lattice cells whose jitter can enter
the requested bounds. The family's filter graph then applies as before.

Converting a family (deadwood_rocks.generator's `region`): build it once without measured ranges (it samples the whole
island and saves its density ranges under PROBE), regenerate, record(groups) into area_ranges.json, then build again.
The ranges are kept with the generator settings they were measured with; changing those settings measures again.
A measuring regenerate costs what the stock one does: with only the Understory group enabled it still reached the 75 GB
guard (#247), so keep only the generators being measured (their rows in the group's asset list, in memory).
That route ran the in-editor regenerate; since #264 the Local is partitioned and bakes only with scripts/pcg/bake,
which reads saved assets, so measuring a new family has no working route yet.

Each area graph ends in a keep filter (ramp(), #264). The level was tuned with biome blending's rounding cull, which
kept a point with a chance that halved with each halving of its height below ~10 m (2^floor(log2(z / 10 m))), the
same for every generator: it is what kept the meadows and the low coast open. With blending off, a point at height z
is kept with chance min(1, z / ramp), each generator's ramp fitted so the island holds the counts it was tuned at.
"""

import json
import math
from pathlib import Path

import unreal

TEMPLATE = "/PCGBiomeCore/GraphTemplates/TPL_BiomeCore_Generator_Advanced"
SAMPLER = "SurfaceSampler_0"
# The template rescales density by the sampled set's own min and max (Attribute Reduce into Remap's input range) after
# the spatial noise, after the Voronoi breakup and after the colony density filter, so a cropped sample would shift
# every density, and with it which points pass the colony filter and which entry each picks. Area generators take
# those ranges as constants: {remap node: (reduce min, reduce max)}.
REMAPS = {"AttributeRemap_3": ("AttributeReduce_4", "AttributeReduce_5"),
          "AttributeRemap_2": ("AttributeReduce_2", "AttributeReduce_3"),
          "AttributeRemap_1": ("AttributeReduce_0", "AttributeReduce_1")}
# The template switches each rescale's branch with these generator parameters; all must be on for it to run.
REMAP_SWITCHES = {"AttributeRemap_3": ("EnableSpatialNoise", "EnableVoronoiNoiseBreakup"),
                  "AttributeRemap_2": ("EnableSpatialNoise", "EnableVoronoiNoiseBreakup"),
                  "AttributeRemap_1": ("EnableSpatialNoise",)}
TILE = 2000  # cm, side of a tile cell
TILE_Z = (-1.0e5, 1.0e6)  # cm; the Region is tested at the projected point, so a tile spans every ground height
RANGES = Path(__file__).with_name("area_ranges.json")  # {group: {"inputs", "ranges"}}, measured over the whole island
WHOLE = [(-1, -1), (-1, 0), (0, -1), (0, 0)]  # with cell=WHOLE_CELL: +-100 km, past any bounding shape
WHOLE_CELL = 1.0e7
AREA = "PCG_Forest_{}Area"  # a group's area graph, the parent of its generator instance
PROBE = "/Game/_AreaProbe"  # measuring graphs save their reduce values here; record() reads, then deletes them
# {group: {"blended", "unblended", "ramp"}}: generator roots island-wide in the level tuned with biome blending on (its
# BlendingDensity 0 rounding cull, #264) and generated per cell with blending off (2026-11-18, before any keep filter);
# ramp (cm) is fitted to the blending-off roots' heights so min(1, z / ramp) keeps the blended count (2026-11-20).
KEEPS = Path(__file__).with_name("blend_keep.json")
KEEP_ATTRIBUTE = "BlendKeep"  # per-point draw in [0, ramp), seeded by the point's $Seed: the same in every partition cell
POSITION_Z = (
    "(bInclusive=False,bUseConstantThreshold=False,ThresholdAttribute=PCGBegin($Position.Z)PCGEnd,"
    "bUseSpatialQuery=False,bFilterEachInputWithEachFilterDataRespectively=False)"
)


def _load():
    return json.loads(RANGES.read_text()) if RANGES.exists() else {}


def _store(measured):
    RANGES.write_text(json.dumps(measured, indent=1, sort_keys=True) + "\n")


def ranges(group, inputs):
    """The group's density ranges measured with these generator inputs, or None: never measured, or measured with
    other settings (the extrema depend on the lattice, slope mask and noise). The terrain and the biome volume are not in
    inputs: after changing either, delete the group's entries from area_ranges.json and measure again."""
    entry = _load().get(group)
    if entry and entry["inputs"] == inputs and entry["ranges"] is not None:
        return {remap: tuple(pair) for remap, pair in entry["ranges"].items()}
    return None


def pending(group, inputs):
    """Note that group's measuring graph was built with these inputs; record() fills in what it measures."""
    measured = _load()
    measured[group] = {"inputs": inputs, "ranges": None}
    _store(measured)


def record(groups):
    """Fill in groups' measured ranges (measure_ranges) after a regenerate with their measuring graphs."""
    measured = _load()
    for group in groups:
        if group not in measured:
            raise RuntimeError(f"{group}: no measuring build pending; build it first")
        measured[group]["ranges"] = {remap: list(pair) for remap, pair in measure_ranges(group, measured[group]["inputs"]).items()}
    _store(measured)
    unreal.EditorAssetLibrary.delete_directory(PROBE)
    return measured


def ramp(group):
    """The height (cm) below which group's area graph thins its points, keeping min(1, z / ramp); 0, keeping them all,
    when not measured (a new group is tuned with blending off from the start)."""
    counts = json.loads(KEEPS.read_text()).get(group) if KEEPS.exists() else None
    return counts.get("ramp", 0.0) if counts else 0.0


def tiles_near(points_cm, reach_cm, cell=TILE):
    """Cells of `cell` cm whose square comes within reach_cm (horizontal) of any of points_cm [(x, y), ...], as
    sorted (ix, iy) indices. Conservative: a cell is kept when its nearest point to a sample is within reach."""
    cells = set()
    span = math.ceil(reach_cm / cell) + 1
    for x, y in points_cm:
        cx, cy = math.floor(x / cell), math.floor(y / cell)
        for ix in range(cx - span, cx + span + 1):
            for iy in range(cy - span, cy + span + 1):
                dx = max(ix * cell - x, 0, x - (ix + 1) * cell)
                dy = max(iy * cell - y, 0, y - (iy + 1) * cell)
                if dx * dx + dy * dy <= reach_cm * reach_cm:
                    cells.add((ix, iy))
    return sorted(cells)


def tile_area_ha(cells, cell=TILE):
    return len(cells) * (cell / 100) ** 2 / 10000


def _edges(graph):
    nodes = list(graph.get_editor_property("nodes")) + [graph.get_input_node(), graph.get_output_node()]
    for node in nodes:
        for pin in node.get_editor_property("output_pins"):
            for e in pin.get_editor_property("edges"):
                # PCGEdge's input_pin is the upstream node's output pin (UE 5.8 PCGEdge.h)
                up, down = e.get_editor_property("input_pin"), e.get_editor_property("output_pin")
                yield (up.get_editor_property("node"), str(up.get_editor_property("properties").get_editor_property("label")),
                       down.get_editor_property("node"), str(down.get_editor_property("properties").get_editor_property("label")))


def _node(graph, name):
    for node in graph.get_editor_property("nodes"):
        if node.get_name() == name:
            return node
    raise RuntimeError(f"{graph.get_name()}: no node {name} (Biome Core template changed?)")


def _connect(graph, source, source_pin, target, target_pin):
    # UE 5.8 PCGGraph.cpp AddEdge always returns To, including on failure: count the target's edges instead.
    count = lambda: sum(len(p.get_editor_property("edges")) for p in target.get_editor_property("input_pins"))
    before = count()
    graph.add_edge(source, source_pin, target, target_pin)
    if count() != before + 1:
        raise RuntimeError(f"{graph.get_name()}: PCG connection failed: {source.get_name()}.{source_pin} -> {target.get_name()}.{target_pin}")


def area_graph(path, cells, ranges=None, cell=TILE, ramp=0.0):
    """A new generator graph at path sampling only `cells` (tiles_near). ranges {remap: (min, max)} fixes the template's
    density rescales ({} for a generator with spatial noise off, which never runs them); None samples the whole
    island and measures them (measure_ranges). ramp: the height below which it thins its points (ramp())."""
    if ranges is None:
        cells, cell = WHOLE, WHOLE_CELL
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    graph = unreal.EditorAssetLibrary.duplicate_asset(TEMPLATE, path)
    stock = _node(graph, SAMPLER)
    old = stock.get_settings()
    sampler, settings = graph.add_node_of_type(unreal.ForestPCGAreaSamplerSettings)
    for name in ("seed", "points_per_squared_meter", "point_extents", "looseness", "unbounded", "apply_density_to_points",
                 "point_steepness", "use_legacy_grid_creation_method"):
        settings.set_editor_property(name, old.get_editor_property(name))
    for up, up_pin, down, down_pin in list(_edges(graph)):
        if up == stock:
            _connect(graph, sampler, up_pin, down, down_pin)
        elif down == stock:
            _connect(graph, up, up_pin, sampler, down_pin)
    graph.remove_node(stock)
    tiles, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
    points = []
    for ix, iy in cells:
        point = unreal.PCGPoint()
        point.set_editor_property("transform", unreal.Transform(location=unreal.Vector((ix + 0.5) * cell, (iy + 0.5) * cell, 0)))
        point.set_editor_property("bounds_min", unreal.Vector(-cell / 2, -cell / 2, TILE_Z[0]))
        point.set_editor_property("bounds_max", unreal.Vector(cell / 2, cell / 2, TILE_Z[1]))
        point.set_editor_property("steepness", 1.0)
        points.append(point)
    settings.set_editor_property("points_to_create", points)
    settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
    settings.set_editor_property("cull_points_outside_volume", False)
    _connect(graph, tiles, "Out", sampler, "Region Tiles")
    _connect(graph, tiles, "Out", sampler, "Region")
    edges = list(_edges(graph))
    if ranges is not None:
        for remap, (low, high) in ranges.items():
            node = _node(graph, remap)
            for up, up_pin, down, down_pin in edges:
                if down == node and down_pin in ("InRangeMin", "InRangeMax"):
                    graph.remove_edge(up, up_pin, down, down_pin)
            node.get_settings().set_editor_property("range_min", low)
            node.get_settings().set_editor_property("range_max", high)
    else:
        _measure(graph, edges)
    thin(graph, ramp)
    if not unreal.EditorAssetLibrary.save_loaded_asset(graph, False):
        raise RuntimeError(f"Save failed: {path}")
    return graph


def thin(graph, ramp):
    """Keep min(1, z / ramp) of the points reaching graph's output at height z: a seeded draw per point in [0, ramp),
    kept below the point's height. Replaces an earlier thin; removes it at ramp 0. A draw per point, not a random
    choice over the set, so a partitioned cell keeps the same points the whole island does."""
    from trees_above_shore import z_range  # imported here: it pulls in this module's siblings

    output = graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        settings = node.get_settings()
        if isinstance(settings, unreal.PCGAttributeNoiseSettings) and KEEP_ATTRIBUTE in settings.get_editor_property("output_target").export_text():
            feeds = [(up, up_pin) for up, up_pin, down, _ in _edges(graph) if down == node]
            kept = [(down, down_pin) for up, _, filt, _ in _edges(graph) if up == node
                    for f, f_pin, down, down_pin in _edges(graph) if f == filt and f_pin == "InsideFilter"]
            filters = {filt for up, _, filt, _ in _edges(graph) if up == node}
            for f in filters:
                graph.remove_node(f)
            graph.remove_node(node)
            for (up, up_pin), (down, down_pin) in zip(feeds, kept, strict=True):
                _connect(graph, up, up_pin, down, down_pin)
    if ramp <= 0:
        return
    feeds = [(up, up_pin, down_pin) for up, up_pin, down, down_pin in _edges(graph) if down == output]
    if len(feeds) != 1:
        raise RuntimeError(f"{graph.get_name()}: {len(feeds)} edges into the output, expected 1 (Biome Core template changed?)")
    (up, up_pin, out_pin), = feeds
    graph.remove_edge(up, up_pin, output, out_pin)
    noise, settings = graph.add_node_of_type(unreal.PCGAttributeNoiseSettings)
    source, target = unreal.PCGAttributePropertyInputSelector(), unreal.PCGAttributePropertyOutputSelector()
    source.import_text("PCGBegin($Density)PCGEnd")
    target.import_text(f"PCGBegin({KEEP_ATTRIBUTE})PCGEnd")
    for name, value in (("input_source", source), ("output_target", target), ("mode", unreal.PCGAttributeNoiseMode.SET),
                        ("noise_min", 0.0), ("noise_max", float(ramp))):
        settings.set_editor_property(name, value)
    below = z_range(graph, 0.0, 0.0, KEEP_ATTRIBUTE)
    height = unreal.PCGAttributeFilterThresholdSettings()
    height.import_text(POSITION_Z)
    below.get_settings().set_editor_property("max_threshold", height)
    _connect(graph, up, up_pin, noise, "In")
    _connect(graph, noise, "Out", below, "In")
    _connect(graph, below, "InsideFilter", output, out_pin)


def _measure(graph, edges):
    """Save every reduce's value as a PCG data asset under PROBE (read back by measure_ranges). Biome Core keeps only its
    own attributes on generator points, so the values cannot ride on the points to the Local output."""
    for reduce in sorted({r for pair in REMAPS.values() for r in pair}):
        save_node, settings = graph.add_node_of_type(unreal.PCGSaveDataAssetSettings)
        params = settings.get_editor_property("params")
        for name, value in (("open_save_dialog", False), ("asset_name", f"{graph.get_name()}_{reduce}"), ("asset_path", PROBE),
                            ("save_on_export_ended", True)):
            params.set_editor_property(name, value)
        settings.set_editor_property("params", params)
        _connect(graph, _node(graph, reduce), "Out", save_node, "In")


def _probe_value(group, reduce):
    """The value a measuring graph saved for reduce, or None when it saved none."""
    asset = unreal.load_asset(f"{PROBE}/{AREA.format(group)}_{reduce}")
    if asset is None:
        return None
    found = unreal.PCGDataFunctionLibrary.get_typed_inputs(asset.get_editor_property("data"), unreal.PCGParamData)
    params = (found[0] if isinstance(found, tuple) else found)[0]
    metadata = params.const_metadata()
    names, _types = metadata.get_attributes()
    return unreal.PCGMetadataAccessorHelpers.get_double_attribute_by_metadata_key(0, metadata, names[0])


def measure_ranges(group, inputs):
    """{remap: (min, max)} from the probe assets a measuring generator built with inputs saved during a regenerate,
    for each rescale those inputs switch on (REMAP_SWITCHES). One that runs but saved nothing (an interrupted or failed
    measuring run) raises: freezing the others alone would leave it rescaling by the cropped sample."""
    measured = {}
    for remap, (low, high) in REMAPS.items():
        if all(inputs[switch] for switch in REMAP_SWITCHES[remap]):
            pair = (_probe_value(group, low), _probe_value(group, high))
            if None in pair:
                raise RuntimeError(f"{group}: {remap} runs but its probes are missing; regenerate with its measuring graph again")
            measured[remap] = pair
    return measured
