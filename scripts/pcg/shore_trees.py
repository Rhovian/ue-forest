# editor-py: fresh-siblings
"""Build the Forest Biome ShoreTrees group: a few lone large beech on the sand (#38).

    scripts/editor-py scripts/pcg/shore_trees.py

edge_in_05 and beach_01 want rare lone shore trees standing out on the beach, roots on the sand, some at the
waterline. The Trees group's filter removes every point below the shore height, so these come from their own
generator, kept only on sand (just above the sea up to the shore height): the requested shore-filter exception, and
only near the coast's headlands, "placed at points or curves where they read against the sea" (beach_01,
high_point_01). Headlands are found from the island's outline: the outermost sand on rays from the island centre
every 3 degrees, ranked by how far each sticks out past its +-15 degree neighbours, at least 30 degrees apart.
Each entry copies the Trees group's entry for the same mesh (wind, scale and options) and changes only its generator
and filter. Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib
import math

import biome_variants
import unreal
from deadwood_rocks import ROOT, asset_list, copy_asset, edge, generator, get, load, load_forest_actors, put, save
from trees_above_shore import shore_height, z_range

PER_HA = 200  # candidates/ha island-wide; only sand near a headland survives: about one tree per headland
# Core differences generator point sets by priority before the sand filter runs; the Trees group (priority 0) must
# win, or these island-wide candidates' crown bounds clear the forest around them (#38: trees halved at priority 0).
PRIORITY = 50
HEADLANDS = 6  # most prominent coastal points that may carry a tree
NEAR = 2500  # cm from a headland's outermost sand
CENTRE = (50000, -50000)  # cm, the island's middle; the island lies in x 0..1100 m, y -1000..0 m
SAND_FROM = 3  # cm: the beach lies mostly 5-20 cm above the sea (z 0), the shallow sea floor below


def ground(world, x, y):
    """Landscape height at (x, y), ignoring anything else the ray meets; None off the landscape."""
    start, end, ignored = unreal.Vector(x, y, 100000), unreal.Vector(x, y, -100000), []
    for _ in range(64):
        hit = unreal.SystemLibrary.line_trace_single(
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, unreal.DrawDebugTrace.NONE, True
        )
        if hit is None:
            return None
        fields = hit.to_tuple()
        if isinstance(fields[9], unreal.LandscapeProxy):
            return fields[4].z
        ignored.append(fields[9])
    return None


def headlands(shore):
    """World (x, y) of the HEADLANDS most prominent points of the island's sand outline (see the module doc)."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    ring = []
    for bearing in range(0, 360, 3):
        outer = None
        for r in range(5000, 80000, 300):
            x, y = CENTRE[0] + r * math.cos(math.radians(bearing)), CENTRE[1] + r * math.sin(math.radians(bearing))
            z = ground(world, x, y) if 0 <= x <= 110000 and -100000 <= y <= 0 else None
            if z is not None and SAND_FROM <= z < shore:
                outer = (r, x, y)
        ring.append((bearing, outer))
    ranked = []
    for i, (bearing, outer) in enumerate(ring):
        near = [ring[(i + k) % len(ring)][1] for k in range(-5, 6) if k]
        near = [n[0] for n in near if n]
        if outer and near:
            ranked.append((outer[0] - sum(near) / len(near), bearing, outer[1], outer[2]))
    chosen = []
    for prominence, bearing, x, y in sorted(ranked, reverse=True):
        if prominence > 0 and all(min(abs(bearing - b), 360 - abs(bearing - b)) >= 30 for _, b, _, _ in chosen):
            chosen.append((prominence, bearing, x, y))
    if len(chosen) < HEADLANDS:
        raise RuntimeError(f"found {len(chosen)} headlands, expected {HEADLANDS}; are all cells loaded?")
    return [(x, y) for _, _, x, y in chosen[:HEADLANDS]]


def main():
    variants = importlib.reload(biome_variants).SHORE_TREE_VARIANTS
    trees = load(ROOT + "DA_Forest_TreesAssets")
    stock = {get(value, "SkeletalMesh").get_path_name().split(".")[0]: value for value in trees.get_editor_property("BiomeAssets")}
    missing = [path for path, _ in variants if path not in stock]
    if missing or any(weight <= 0 for _, weight in variants):
        raise RuntimeError(f"Shore tree variants must be Trees group meshes with positive weights: {missing}")
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_ShoreTreesOnSand")
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    sand = z_range(graph, SAND_FROM, shore_height())
    edge(graph, inp, "In", sand, "In")
    points = headlands(shore_height())
    marks, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
    created = []
    for x, y in points:
        point = unreal.PCGPoint()
        point.set_editor_property("transform", unreal.Transform(location=unreal.Vector(x, y, 0)))
        created.append(point)
    settings.set_editor_property("points_to_create", created)
    settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
    settings.set_editor_property("cull_points_outside_volume", False)
    # Same native distance and density filter as saplings_understory.damp_filter: density = distance / NEAR.
    distance, settings = graph.add_node_of_type(unreal.PCGDistanceSettings)
    settings.set_editor_property("set_density", True)
    settings.set_editor_property("maximum_distance", NEAR)
    settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
    settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
    edge(graph, sand, "InsideFilter", distance, "Source")
    edge(graph, marks, "Out", distance, "Target")
    near, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
    settings.set_editor_property("lower_bound", 0)
    settings.set_editor_property("upper_bound", 0.99)  # drop the saturated no-headland-within-NEAR distance
    edge(graph, distance, "Out", near, "In")
    edge(graph, near, "Out", out, "Out")
    save(graph)
    # No spatial noise: it thinned ~97% of candidates, too few for the small headland areas.
    group = generator("ShoreTrees", PER_HA, 15, PRIORITY, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    entries = []
    for path, weight in variants:
        value = stock[path].copy()
        # A distinct AssetType: entries sharing one with the Trees group drew from the forest's points (trees halved).
        put(value, AssetType="Shore_" + path.rsplit("/", 1)[1], Generator=group, TransformGraph=graph, Weight=weight)
        entries.append(value)
    assets = asset_list("DA_Forest_ShoreTreesAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Shore trees: {PER_HA} candidates/ha, sand {SAND_FROM}..{shore_height():.0f} cm within {NEAR / 100:.0f} m of"
          f" headlands {[(round(x / 100), round(y / 100)) for x, y in points]} m, {len(entries)} variants")


if __name__ == "__main__":
    main()
