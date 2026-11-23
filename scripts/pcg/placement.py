# editor-py: fresh-siblings
"""Build PCG_ForestPlacement, the forest's placement graph, which replaced Biome Core (#266).

    scripts/editor-py scripts/pcg/placement.py [--only Trees,Hornbeams] [--attach]

Biome Core ran every group through generic loops over its generators, asset rows and children, in every partition
cell: ~900,000 PCG tasks and ~11 s a 256 m cell, ~32 min and 60 GB for the island. This builds one graph of stock
nodes doing the same work directly, ~1 s a cell, from the same definitions: the group scripts write the generator
data assets (DA_Forest_*Generator) and asset lists (DA_Forest_*Assets in ROOT and the child lists they name), and
every asset list there is read here (deadwood_rocks.asset_lists), so rebuild this after any group script.

Per generator, in Core's priority order: its generator graph (area sampler and density rules) on the cell's bounds;
the exclusion actors' interiors removed (copy_exclusions); points under WATER_LEVEL dropped; for the generators that
take part in Core's priority difference (GeneratorAllowOverlap False: Veterans, Trees, SaplingsGaps), the root
centres of each one ranked before removed; a weighted random split of the points over the generator's row groups
(rows sharing a transform graph, child list, OrientUpward and collision); then per group OrientUpward, its transform
graph and the stock mesh spawners, a weighted static selector for its static rows. Each child list runs once, on the
points of every group naming it (children()). Biome Core's per-asset filter options are all at their no-op defaults
here and its child-overlap pruning runs on 5% bounds (deadwood_rocks.children), so neither is reproduced.

The graph goes on the level's PCG volume LABEL, partitioned on the 256 m grid; its extent is the area filled, so a
larger world is a larger volume. --attach (re)applies the graph and component settings and fits the builder volume
(BUILDER_LABEL) to it without rebuilding. The bake generates it (scripts/pcg/bake). Saves the graph under
/Game/ForestPlacement; never saves the level.
"""

import argparse
import collections
import re
import time

import unreal
from deadwood_rocks import edge, get, save
from trees_above_shore import z_range

ROOT = "/Game/ForestBiome/"
OUT = "/Game/ForestPlacement/"
NAME = "PCG_ForestPlacement"
LABEL = "ForestPlacement"
BUILDER_LABEL = "ForestPlacementBuilderBounds"
WATER_LEVEL = -100.0  # cm: BiomeFilter_WaterDistance_Level's WaterLevel parameter
WEIGHT_SCALE = 1000  # row weights to the weighted mesh selector's integers
LOCAL_GRAPH = "/PCGBiomeCore/LocalBiomeCore"
# Its exclusion chain into Difference_3's Differences, by node name (UE 5.8 /PCGBiomeCore/LocalBiomeCore).
EXCLUSION_EDGES = (
    ("GetActorData_6", "Out", "FilterByTag_5", "In"),
    ("FilterByTag_5", "InsideFilter", "FilterByType_7", "In"), ("FilterByType_7", "InsideFilter", "SplineSampler_1", "Spline"),
    ("SplineSampler_1", "Out", "BoundsModifier_2", "In"), ("BoundsModifier_2", "Out", "Difference", "Differences"),
    ("FilterByTag_5", "InsideFilter", "FilterByType_8", "In"), ("FilterByType_8", "InsideFilter", "Difference", "Differences"),
    ("FilterByTag_5", "OutsideFilter", "FilterDataByTag_9", "In"),
    ("FilterDataByTag_9", "InsideFilter", "FilterDataByType_7", "In"),
    ("FilterDataByType_7", "InsideFilter", "Difference", "Differences"),
)
BOUNDING_TAG = "BoundingShape"  # the generator template reads its bounds from input data with this tag


def rows_of(asset_list):
    """Each BiomeAssets row of an asset list as a dict."""
    rows = []
    for row in asset_list.get_editor_property("BiomeAssets"):
        options, mesh_options = get(row, "AssetOptions"), get(row, "MeshOptions")
        rows.append({
            "weight": get(row, "Weight"), "generator": get(row, "Generator"), "transform": get(row, "TransformGraph"),
            "mesh": get(row, "Mesh") or get(row, "SkeletalMesh"), "children": get(row, "ChildAssets"),
            "upward": get(options, "OrientUpward"), "material": get(mesh_options, "Material"),
            "collision": get(mesh_options, "AllowCollision"),
        })
    return rows


def inventory():
    """Every generator with its root rows, in Core's priority order (lower first)."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    rows = collections.defaultdict(list)
    for found in registry.get_assets_by_path(ROOT.rstrip("/"), recursive=False):
        if re.fullmatch(r"DA_Forest_\w+Assets", str(found.asset_name)):
            for row in rows_of(unreal.load_asset(str(found.package_name))):
                rows[row["generator"]].append(row)
    generators = []
    for data, group_rows in rows.items():
        value = data.get_editor_property("Generator")
        generators.append({"name": str(get(value, "GeneratorType")), "graph": get(value, "GeneratorGraph"),
                           "priority": get(value, "GeneratorPriority"), "overlap": get(value, "GeneratorAllowOverlap"),
                           "rows": group_rows})
    return sorted(generators, key=lambda g: (g["priority"], g["name"]))


class Builder:
    def __init__(self, graph):
        self.graph = graph
        self.parents = collections.defaultdict(list)  # child list -> the root points of every group naming it
        self.exclusions = None

    def node(self, cls, source=None, pin="Out", into="In", **properties):
        node, settings = self.graph.add_node_of_type(cls)
        for name, value in properties.items():
            settings.set_editor_property(name, value)
        if source is not None:
            edge(self.graph, source, pin, node, into)
        return node

    @staticmethod
    def select(text):
        selector = unreal.PCGAttributePropertyInputSelector()
        selector.import_text(f"PCGBegin({text})PCGEnd")
        return selector

    @staticmethod
    def target(text):
        selector = unreal.PCGAttributePropertyOutputSelector()
        selector.import_text(f"PCGBegin({text})PCGEnd")
        return selector

    def subgraph(self, graph, source, pin="Out"):
        node = self.node(unreal.PCGSubgraphSettings, source, pin)
        node.get_settings().set_subgraph(graph)
        return node

    def split(self, source, pin, weights, seed):
        """[(node, pin)]: source's points split at random in proportion to weights. The draw is per point, so a cell
        keeps the same split the whole island would."""
        if len(weights) == 1:
            return [(source, pin)]
        total = float(sum(weights))
        noise = self.node(unreal.PCGAttributeNoiseSettings, source, pin, input_source=self.select("$Density"),
                          output_target=self.target("Pick"), mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0,
                          noise_max=total, seed=seed)
        parts, low, rest = [], 0.0, (noise, "Out")
        for index, weight in enumerate(weights):
            high = low + weight if index < len(weights) - 1 else total * 2  # the last part takes the remainder
            node = z_range(self.graph, low, high, "Pick")
            edge(self.graph, rest[0], rest[1], node, "In")
            rest, low = (node, "OutsideFilter"), high
            parts.append((node, "InsideFilter"))
        return parts

    def constant(self, source, pin, attribute, asset):
        node = self.node(unreal.PCGAddAttributeSettings, source, pin, output_target=self.target(attribute))
        settings = node.get_settings()
        value = settings.get_editor_property("attribute_types")
        value.set_editor_property("type", unreal.PCGMetadataTypes.SOFT_OBJECT_PATH)
        value.set_editor_property("soft_object_path_value", unreal.SoftObjectPath(asset.get_path_name()))
        settings.set_editor_property("attribute_types", value)
        return node

    def upward(self, source, pin, amount):
        """(node, pin): source's points stood upright with a random yaw when amount (OrientUpward) is at least 0.5, else
        left on the surface's orientation. Biome Core lerps the two by amount; the groups here use 0 (parts fitted to
        their host), 0.9 (trees: a tenth of the slope, ~3 degrees on the island's steepest tree ground) or 1."""
        if amount < 0.5:
            return source, pin
        upright = self.node(unreal.PCGTransformPointsSettings, source, pin, absolute_rotation=True,
                            rotation_max=unreal.Rotator(pitch=0, yaw=360, roll=0))
        return upright, "Out"

    def join(self, node, sources):
        for source, pin in sources:
            edge(self.graph, source, pin, node, "In")
        return node

    def static_spawner(self, sources, rows, collision):
        """One Static Mesh Spawner picking among rows by weight at each point (its weighted selector)."""
        spawner = self.node(unreal.PCGStaticMeshSpawnerSettings, apply_mesh_bounds_to_points=True,
                            mesh_selector_type=unreal.PCGMeshSelectorWeighted)
        entries = []
        for row in rows:
            entry = unreal.PCGMeshSelectorWeightedEntry()
            descriptor = entry.get_editor_property("descriptor")
            descriptor.set_editor_property("static_mesh", row["mesh"])
            if row["material"]:
                descriptor.set_editor_property("override_materials", [row["material"]])
            if not collision:
                body = descriptor.get_editor_property("body_instance")
                body.set_editor_property("collision_profile_name", "NoCollision")
                descriptor.set_editor_property("body_instance", body)
            entry.set_editor_property("descriptor", descriptor)
            entry.set_editor_property("weight", max(1, round(row["weight"] * WEIGHT_SCALE)))  # an int32 here
            entries.append(entry)
        spawner.get_settings().get_editor_property("mesh_selector_parameters").set_editor_property("mesh_entries", entries)
        return self.join(spawner, sources)

    def skinned_spawner(self, sources, rows, seed):
        """A Skinned Mesh Spawner, which selects only by attribute: the points split among rows by weight first."""
        spawner = self.node(unreal.PCGSkinnedMeshSpawnerSettings, apply_mesh_bounds_to_points=True)
        spawner.get_settings().get_editor_property("mesh_selector_parameters").set_editor_property(
            "mesh_attribute", self.select("Mesh"))
        merged = self.join(self.node(unreal.PCGMergeSettings), sources) if len(sources) > 1 else None
        source, pin = (merged, "Out") if merged else sources[0]
        for (node, part), row in zip(self.split(source, pin, [r["weight"] for r in rows], seed), rows, strict=True):
            edge(self.graph, self.constant(node, part, "Mesh", row["mesh"]), "Out", spawner, "In")
        return spawner

    def spawn(self, sources, rows, collision, seed):
        """Spawn sources' points as rows (picked by weight at each point); returns the spawners, whose Out carries the
        spawned points with their mesh bounds."""
        kinds = [[r for r in rows if isinstance(r["mesh"], unreal.SkeletalMesh) == skinned] for skinned in (False, True)]
        kinds = [(skinned, mine) for skinned, mine in zip((False, True), kinds) if mine]
        if len(kinds) == 2:  # static and skinned rows: split their shares first
            merged = self.join(self.node(unreal.PCGMergeSettings), sources) if len(sources) > 1 else None
            source, pin = (merged, "Out") if merged else sources[0]
            parts = self.split(source, pin, [sum(r["weight"] for r in mine) for _, mine in kinds], seed + 7)
        else:
            parts = [None]
        spawners = []
        for (skinned, mine), part in zip(kinds, parts, strict=True):
            mine_sources = [part] if part else sources
            spawners.append(self.skinned_spawner(mine_sources, mine, seed) if skinned
                            else self.static_spawner(mine_sources, mine, collision))
        return spawners

    def tap(self, sources, name):
        """The group's root points on the graph output, tagged as Biome Core tagged them (Root, GEN:<group>), for the
        audits that read them (canopy_gaps.py through ForestPCGLibrary.GetGeneratedPointLocations)."""
        tag = self.join(self.node(unreal.PCGAddTagSettings, tags_to_add=f"Root,GEN:{name}"), sources)
        edge(self.graph, tag, "Out", self.graph.get_output_node(), "Out")

    def generator(self, generator, bounds, ranked):
        """Place one generator's root points; returns them as [(node, pin)]. Child lists are queued for children()."""
        # Core's root filters keep FilterOptions' ranges, all at their defaults here; the one that culls is
        # BiomeFilter_WaterDistance_Level, which keeps only points above its graph's WaterLevel parameter (-100 cm).
        # The Local's exclusion (copied from LocalBiomeCore, copy_exclusions) at the generator's own point extents;
        # then the bounds shrink to ~1 cm: Core's priority difference tests root centres (it found no mesh bounds on
        # the skinned trees). The spawners give each point its mesh's bounds.
        kept = self.node(unreal.PCGDifferenceSettings, self.subgraph(generator["graph"], bounds), "Out", "Source",
                         density_function=unreal.PCGDifferenceDensityFunction.BINARY,
                         mode=unreal.PCGDifferenceMode.DISCRETE)  # points out, not a lazy spatial difference
        for node, pin in self.exclusions:
            edge(self.graph, node, pin, kept, "Differences")
        centre = self.node(unreal.PCGBoundsModifierSettings, kept, mode=unreal.PCGBoundsModifierMode.SET,
                           bounds_min=unreal.Vector(-1, -1, -1), bounds_max=unreal.Vector(1, 1, 1))
        points = self.node(unreal.PCGAttributeFilteringSettings, centre,
                           target_attribute=self.select("$Position.Z"), operator=unreal.PCGAttributeFilterOperator.GREATER,
                           use_constant_threshold=True)
        value = points.get_settings().get_editor_property("attribute_types")
        value.set_editor_property("type", unreal.PCGMetadataTypes.DOUBLE)
        value.set_editor_property("double_value", WATER_LEVEL)
        points.get_settings().set_editor_property("attribute_types", value)
        pin = "InsideFilter"
        if not generator["overlap"] and ranked:
            diff = self.node(unreal.PCGDifferenceSettings, points, pin, "Source",
                             density_function=unreal.PCGDifferenceDensityFunction.BINARY,
                         mode=unreal.PCGDifferenceMode.DISCRETE)  # points out, not a lazy spatial difference
            for node, ranked_pin in ranked:
                edge(self.graph, node, ranked_pin, diff, "Differences")
            points, pin = diff, "Out"
        groups = collections.defaultdict(list)
        for row in generator["rows"]:
            groups[(row["transform"], row["children"], row["upward"] >= 0.5, row["collision"])].append(row)
        seed = sum(map(ord, generator["name"]))
        weights = [sum(r["weight"] for r in rows) for rows in groups.values()]
        roots = []
        parts = self.split(points, pin, weights, seed)
        for ((transform, children, upward, collision), rows), (node, pin) in zip(groups.items(), parts, strict=True):
            node, pin = self.upward(node, pin, 1.0 if upward else 0.0)
            if transform:
                node, pin = self.subgraph(transform, node, pin), "Out"
            self.spawn([(node, pin)], rows, collision, seed + 1)
            roots.append((node, pin))
            if children:
                self.parents[children].append((node, pin))
        self.tap(roots, generator["name"])
        return roots

    def children(self):
        """Each queued child list once, on the points of every group naming it: each of its layout graphs, with a
        weighted pick of that layout's rows at each child point (deadwood_rocks.children)."""
        for index, (children, parents) in enumerate(self.parents.items()):
            layouts = collections.defaultdict(list)
            for row in rows_of(children):
                layouts[row["transform"]].append(row)
            for layout, rows in layouts.items():
                placed = self.join(self.node(unreal.PCGSubgraphSettings), parents)
                placed.get_settings().set_subgraph(layout)
                self.spawn([(placed, "Out")], rows, any(row["collision"] for row in rows), 1000 + index)

    def copy_exclusions(self):
        """LocalBiomeCore's exclusion sources, its nodes and edges copied (EXCLUSION_EDGES): the PCG_BiomeExclusion
        actors overlapping the cell; their BiomeExclusion-tagged splines' interiors sampled on a coarse subdivision
        grid and stretched tall, their primitives, and their other splines as they are. Returns [(node, pin)] for a
        Difference's Differences pin. The grid covers an interior unevenly, which is why Core kept some points inside
        the stream's exclusion and cleared the water line."""
        local = unreal.load_asset(LOCAL_GRAPH)
        found = {n.get_name(): n for n in local.get_editor_property("nodes")}
        copies = {}
        for name in {n for up, _, down, _ in EXCLUSION_EDGES for n in (up, down)} - {"Difference"}:
            if name not in found:
                raise RuntimeError(f"{LOCAL_GRAPH}: no node {name} (Biome Core changed?)")
            copies[name], _ = self.graph.add_node_copy(found[name].get_settings())
        outs = []
        for up, up_pin, down, down_pin in EXCLUSION_EDGES:
            if down == "Difference":
                outs.append((copies[up], up_pin))
            else:
                edge(self.graph, copies[up], up_pin, copies[down], down_pin)
        return outs

    def build(self, generators):
        bounds = self.node(unreal.PCGAddTagSettings, self.graph.get_input_node(), "In", tags_to_add=BOUNDING_TAG)
        self.exclusions = self.copy_exclusions()
        ranked = []
        for generator in generators:
            # Core's priority difference subtracts the root points of the generators ranked before, tested at their
            # centres (generator()).
            roots = self.generator(generator, bounds, ranked)
            if not generator["overlap"]:
                ranked += roots
        self.children()


def graph_asset():
    """PCG_ForestPlacement, emptied."""
    path = OUT + NAME
    graph = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else \
        unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, OUT.rstrip("/"), unreal.PCGGraph, unreal.PCGGraphFactory())
    # Each removal recompiles the graph (UPCGGraph::RemoveNodes, the bulk form, takes its array by reference, which
    # Python cannot pass), so clearing costs grow with the square of the node count: keep the graph small.
    for node in list(graph.get_editor_property("nodes")):
        graph.remove_node(node)
    return graph


def volume(graph):
    """The level's PCG volume LABEL, carrying the graph, partitioned and generated on demand (by the bake)."""
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    found = [a for a in actors if a.get_actor_label() == LABEL and isinstance(a, unreal.PCGVolume)]
    if len(found) != 1:
        raise RuntimeError(f"Expected one PCG volume labelled {LABEL} over the area to fill, found {len(found)}")
    component = found[0].get_component_by_class(unreal.PCGComponent)
    component.set_graph(graph)
    component.set_editor_property("is_component_partitioned", True)
    component.set_editor_property("generation_trigger", unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND)
    return found[0]


def builder_volume(placement):
    """A PCG builder volume over the placement volume (BUILDER_LABEL): the World Partition builder's 2D iteration, which
    the bake uses, then visits only its cells (PCGWorldPartitionBuilder.cpp GetPCGBuilderVolumeBounds) instead of the
    editor world bounds, which reach +-4 km here: 1,024 iterations a bake, ~916 of them empty, ~340 s (#266)."""
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    found = [a for a in actors if a.get_actor_label() == BUILDER_LABEL]
    if not found:
        found = [unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
            unreal.PCGBuilderVolume, placement.get_actor_location(), placement.get_actor_rotation())]
        found[0].set_actor_label(BUILDER_LABEL)
    origin, extent = placement.get_actor_bounds(False)
    found[0].set_actor_location(origin, False, False)
    found[0].set_actor_scale3d(unreal.Vector(extent.x / 100, extent.y / 100, extent.z / 100))
    return found[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated generator names (default: all)")
    parser.add_argument("--attach", action="store_true", help="only (re)place the volumes, with the saved graph")
    args = parser.parse_args()
    if args.attach:
        builder_volume(volume(unreal.load_asset(OUT + NAME)))
        return
    generators = inventory()
    if args.only:
        wanted = set(args.only.split(","))
        generators = [g for g in generators if g["name"] in wanted]
        if {g["name"] for g in generators} != wanted:
            raise RuntimeError(f"Unknown generators: {wanted - {g['name'] for g in generators}}")
    if not unreal.EditorAssetLibrary.does_directory_exist(OUT):
        unreal.EditorAssetLibrary.make_directory(OUT)
    # Detach the graph while it is built: every node and edge added to a graph a component uses notifies and refreshes
    # that component, which made a full build take over 10 minutes.
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        if actor.get_actor_label() == LABEL:
            actor.get_component_by_class(unreal.PCGComponent).set_graph(None)
    started = time.monotonic()
    graph = graph_asset()
    builder = Builder(graph)
    builder.build(generators)
    save(graph)
    actor = volume(graph)
    builder_volume(actor)
    print(f"built in {time.monotonic() - started:.0f} s")
    print(f"{NAME}: {len(generators)} generators, {len(graph.get_editor_property('nodes'))} nodes,"
          f" on {actor.get_actor_label()}")


if __name__ == "__main__":
    main()
