# editor-py: fresh-siblings
"""Build one step 8b group at a time; regenerate Core and measure after EACH build.

    scripts/editor-py scripts/pcg/saplings_understory.py saplings|understory [--check]
    scripts/editor-py scripts/pcg/saplings_understory.py understory --density-scale 0.5

Candidates/ha before slope, noise, canopy pruning and water/path exclusions. Saves
assets, attaches only the requested group; leaves regeneration/level saving to lead.
"""

import argparse
import importlib
import math

import biome_variants
import unreal
from deadwood_rocks import ROOT, asset_list, copy_asset, edge, entry, field, generator, get, load, put, save
from shore_path import LABEL
from trees_above_shore import shore_height, z_range


def damp_filter():
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_UnderstoryDamp")
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    shore = z_range(graph, shore_height() + 150, 1.0e7)
    edge(graph, inp, "In", shore, "In")
    low = z_range(graph, shore_height() + 150, 1200)
    edge(graph, shore, "InsideFilter", low, "In")
    merge, _ = graph.add_node_of_type(unreal.PCGMergeSettings)
    edge(graph, low, "InsideFilter", merge, "In")
    # UE 5.8 PCGDataFromActor/PCGSplineSampler/PCGDistance implement water proximity;
    # use sampled live water splines, not a custom spatial search or actor AABBs.
    water, settings = graph.add_node_of_type(unreal.PCGDataFromActorSettings)
    selector = settings.get_editor_property("actor_selector")
    for name, value in {"actor_filter": unreal.PCGActorFilter.ALL_WORLD_ACTORS,
                        "actor_selection": unreal.PCGActorSelection.BY_CLASS,
                        "actor_selection_class": unreal.WaterBody, "select_multiple": True}.items():
        selector.set_editor_property(name, value)
    settings.set_editor_property("actor_selector", selector)
    components = settings.get_editor_property("component_selector")
    components.set_editor_property("component_selection", unreal.PCGComponentSelection.BY_CLASS)
    components.set_editor_property("component_selection_class", unreal.SplineComponent)
    settings.set_editor_property("component_selector", components)
    sampler, settings = graph.add_node_of_type(unreal.PCGSplineSamplerSettings)
    params = settings.get_editor_property("sampler_params")
    params.set_editor_property("mode", unreal.PCGSplineSamplingMode.DISTANCE)
    params.set_editor_property("distance_increment", 500)
    params.set_editor_property("unbounded", True)  # include nearby water across PCG cell boundaries
    settings.set_editor_property("sampler_params", params)
    edge(graph, water, "Out", sampler, "Spline")
    distance, settings = graph.add_node_of_type(unreal.PCGDistanceSettings)
    settings.set_editor_property("set_density", True)
    settings.set_editor_property("maximum_distance", 3000)
    settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
    settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
    edge(graph, low, "OutsideFilter", distance, "Source")
    edge(graph, sampler, "Out", distance, "Target")
    near, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
    settings.set_editor_property("lower_bound", 0)
    settings.set_editor_property("upper_bound", 0.99)  # exclude the saturated no-neighbour distance
    edge(graph, distance, "Out", near, "In")
    edge(graph, near, "Out", merge, "In")
    edge(graph, merge, "Out", out, "Out")
    save(graph)
    return graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=("saplings", "understory"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--density-scale", type=float, default=1)
    args = parser.parse_args()
    if not math.isfinite(args.density_scale) or not 0 < args.density_scale <= 1:
        parser.error("--density-scale must be >0 and <=1; thin Understory first")
    variants = importlib.reload(biome_variants)
    # Sparse whole-area candidates, not the research's much higher within-colony densities.
    kinds = [("Saplings", variants.SAPLING_VARIANTS, 300)] if args.group == "saplings" else [
        ("Shrubs", variants.SHRUB_VARIANTS, 100), ("Ferns", variants.FERN_VARIANTS, 1000),
        ("Herbs", variants.HERB_VARIANTS, 2000), ("Ivy", variants.IVY_VARIANTS, 500)]
    paths = [path for _, rows, _ in kinds for path, _ in rows]
    if len(set(paths)) != len(paths) or any(not rows or any(w <= 0 for _, w in rows) for _, rows, _ in kinds):
        raise RuntimeError("Plant palettes must be nonempty, paths unique, weights positive")
    meshes = {path: load(path) for path in paths}
    if any(not isinstance(mesh, (unreal.StaticMesh, unreal.SkeletalMesh)) for mesh in meshes.values()):
        raise RuntimeError("Plant palette contains a non-mesh")
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    load(ROOT + "PCG_TreesAboveShore")
    load(ROOT + "PCG_Forest_TreesGenerator")
    load(ROOT + "DA_Forest_TreesGenerator")
    for name in ("Mesh", "SkeletalMesh", "Generator", "TransformGraph", "MeshOptions", "AssetOptions"):
        field(template, name)
    # Exercise native typed fields on detached struct copies before any asset/actor mutation.
    for mesh in meshes.values():
        entry(template, mesh, None, None, collision=False)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    biomes = [a for a in actors if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes or not any(a.get_actor_label() == LABEL and a.actor_has_tag("PCG_BiomeExclusion") for a in actors):
        raise RuntimeError("Load forest biome/all cells and build shore_path.py first")
    for water in [a for a in actors if isinstance(a, (unreal.WaterBodyLake, unreal.WaterBodyRiver))]:
        if not any(a.get_actor_label() == "ForestExclusion_" + water.get_actor_label()
                   and a.actor_has_tag("PCG_BiomeExclusion") for a in actors):
            raise RuntimeError("Run water_exclusions.py first, then shore_path.py")
    if args.check:
        print(f"{args.group} preflight OK: {len(paths)} variants, scale {args.density_scale}; no changes")
        return
    from deadwood_rocks import filter_graph
    plain = filter_graph("PCG_PlantsAboveShore")
    damp = damp_filter() if args.group == "understory" else None
    entries = []
    for kind, rows, density in kinds:
        for patch, share, transform, overlap in [("Gaps", 1 if damp is None else 0.5, plain, False)] + (
                [("Damp", 0.5, damp, True)] if damp else []):
            data = generator(kind + patch, density * args.density_scale * share, 25, 30 if damp is None else 40)
            value = data.get_editor_property("Generator")
            put(value, GeneratorAllowOverlap=overlap)
            data.set_editor_property("Generator", value)
            save(data)
            for path, weight in rows:
                mesh = meshes[path]
                value = entry(template, mesh, data, transform, weight, collision=False)
                # Core's OrientUpward preserves upright plants; stock wind/material settings survive.
                options = get(value, "AssetOptions")
                put(options, OrientUpward=1.0)
                put(value, AssetOptions=options)
                entries.append(value)
    group = asset_list("DA_Forest_" + args.group.title() + "Assets", entries)
    for actor in biomes:
        assets = list(actor.get_editor_property("Assets"))
        if group not in assets:
            actor.set_editor_property("Assets", assets + [group])
    print(f"{args.group} built: {[(k, d * args.density_scale) for k, _, d in kinds]} candidates/ha; nonblocking")
    print("Gaps use canopy pruning; Damp uses low (<12 m), flat (<25 deg) or within 30 m of water splines")
    print("Regenerate ALL Core groups, inspect path/contact/wind, save level, then measure; thin Understory first")


if __name__ == "__main__":
    main()
