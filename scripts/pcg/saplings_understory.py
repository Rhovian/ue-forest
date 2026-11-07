# editor-py: fresh-siblings
"""Build one step 8b group at a time; regenerate Core and measure after EACH build.

    scripts/editor-py scripts/pcg/saplings_understory.py saplings|understory [--check]
    scripts/editor-py scripts/pcg/saplings_understory.py understory --density-scale 0.5

Candidates/ha before slope, noise, canopy pruning and water/path exclusions. Saves
assets, attaches only the requested group; leaves regeneration/level saving to lead.
Both check and build retain WP actors for their prerequisites; check makes no explicit asset edits.
"""

import argparse
import importlib
import itertools
import math
import random

import biome_variants
import deadwood_rocks
import unreal
from deadwood_rocks import ROOT, asset_list, children, copy_asset, edge, entry, field, generator, get, load, put, save
from shore_path import LABEL
from trees_above_shore import shore_height, z_range

# Colonies (#71, lush-forest-placement.md §8.1): instead of single plants evenly spread, a sparse anchor carries a
# drift of plants as ground-projected children, so plants read as masses with moss between. (count, length cm, width cm)
# per kind; the anchor density is divided by count, so the plant total stays about the same.
DRIFTS = {"Ferns": (16, 550, 260), "Herbs": (80, 320, 200), "Shrubs": (5, 450, 350),
          "GapShrubs": (9, 400, 350)}  # Shrubs, GapShrubs: clearing_02 masses
# Child scale per drift kind: gap hazel overlaps into one broad waist-to-head mass (clearing_02, #81 review).
DRIFT_SCALE = {"GapShrubs": (1.1, 1.5)}
# Steepest slope (deg) a kind grows on; ferns and ivy clothe the coastal and stream bank faces (edge_in, #71). The
# coastal bluff behind edge_in rises 3-15 m at 53-66 deg (traced), so 45 deg left it bare.
SLOPE = {"Ferns": 65, "Ivy": 70}
SHAPES = 4  # drift outlines per kind; each variant's weight is split across them, so neighbouring drifts differ


def drift_points(count, length, width, shape):
    """`count` points in 2-4 overlapping lobes strung along the drift's length, with ragged spacing: an irregular
    colony outline (one fixed ellipse read as a planted row side-on, #73 review). `shape` seeds the outline."""
    rng = random.Random(shape)
    lobes = []
    for _ in range(rng.randint(2, 4)):
        lobes.append((rng.uniform(-0.35, 0.35) * length, rng.uniform(-0.25, 0.25) * width,
                      rng.uniform(0.25, 0.45) * length, rng.uniform(0.35, 0.6) * width))
    area = sum(rx * ry for _, _, rx, ry in lobes)
    points, i = [], 0
    for n, (cx, cy, rx, ry) in enumerate(lobes):
        share = count - len(points) if n == len(lobes) - 1 else round(count * rx * ry / area)
        for _ in range(share):
            r, a = math.sqrt((i % share + 0.5) / share) * rng.uniform(0.8, 1.1), i * 2.39996
            points.append((cx + rx / 2 * r * math.cos(a), cy + ry / 2 * r * math.sin(a), 0))
            i += 1
    return points


GAP_ONLY = {"GapShrubs"}  # kinds placed only in the canopy gaps

# x the Saplings density inside canopy gaps (canopy_gaps.json), with no spatial noise: regeneration is densest under
# the opening (clearing_01), while noise thins the island-wide saplings to about 1/ha. Saplings are skinned: measure.
CANOPY = 20  # about one sapling per 1.5 m2 in 0.7 ha of gaps: a few thousand skinned saplings

COLUMN_STEP = 100  # cm between a gap's stacked distance targets, from its lowest to its highest traced ground


def column(low, high):
    """Target heights in cm from a gap's lowest to highest ground (m), COLUMN_STEP apart, ends included."""
    count = max(1, math.ceil((high - low) * 100 / COLUMN_STEP))
    return [low * 100 + (high - low) * 100 * i / count for i in range(count + 1)]


# Bank colonies (#71 item 5): extra drifts that fall off with distance from a water spline, in steps of
# (band, inner cm, outer cm, {kind: x the kind's base density}). The river spline is its centreline, so the near band
# covers the half width (3.75 m) and the first metre or so of bank. Flowers fall off fastest (stream_bank_01).
BANKS = [("Near", 0, 500, {"Ferns": 2, "Herbs": 24}), ("Far", 500, 1000, {"Ferns": 1, "Herbs": 4})]


def canopy_filter():
    """Ground inside a canopy gap from canopy_gaps.json, by horizontal distance. Distance's SphereBounds uses the
    bounds' half-diagonal as the radius and is signed (inside is negative), so gaps are grouped by whole-metre radius
    instead: one Create Points + Distance (centre to centre, maximum = that radius) per group, merged. Distance is 3D,
    so each gap is a vertical column of targets COLUMN_STEP apart spanning the gap's traced ground range: the nearest
    is within half a step of every ground point's height, so the measured distance is the horizontal one to within
    sqrt(r^2 + 0.5^2) - r (#75 review)."""
    import json
    from pathlib import Path

    data = json.loads(Path(deadwood_rocks.__file__).with_name("canopy_gaps.json").read_text())
    groups = {}
    for x, y, low, high, radius in data["gaps_m [x, y, ground low, ground high, radius]"]:
        groups.setdefault(int(radius), []).append((x, y, low, high))
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_SaplingsCanopyGaps")
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    band = z_range(graph, shore_height() + 150, 1.0e7)
    edge(graph, inp, "In", band, "In")
    merge, _ = graph.add_node_of_type(unreal.PCGMergeSettings)
    for radius, centres in sorted(groups.items()):
        mark, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
        points = []
        for x, y, low, high in centres:
            for z in column(low, high):
                point = unreal.PCGPoint()
                point.set_editor_property("transform", unreal.Transform(location=unreal.Vector(x * 100, y * 100, z)))
                points.append(point)
        settings.set_editor_property("points_to_create", points)
        settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
        settings.set_editor_property("cull_points_outside_volume", False)
        distance, settings = graph.add_node_of_type(unreal.PCGDistanceSettings)
        settings.set_editor_property("set_density", True)
        settings.set_editor_property("maximum_distance", radius * 100)
        settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
        settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
        edge(graph, band, "InsideFilter", distance, "Source")
        edge(graph, mark, "Out", distance, "Target")
        inside, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
        settings.set_editor_property("lower_bound", 0)
        settings.set_editor_property("upper_bound", 0.99)  # drop the saturated beyond-radius distance
        edge(graph, distance, "Out", inside, "In")
        edge(graph, inside, "Out", merge, "In")
    edge(graph, merge, "Out", out, "Out")
    save(graph)
    return graph


def water_near(graph, source, pin, maximum, nearest=0.0):
    """Points from (source, pin) between nearest x maximum and maximum cm of a water body's spline (river centreline,
    lake shoreline)."""
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
    settings.set_editor_property("maximum_distance", maximum)
    settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
    settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
    edge(graph, source, pin, distance, "Source")
    edge(graph, sampler, "Out", distance, "Target")
    near, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
    settings.set_editor_property("lower_bound", nearest)
    settings.set_editor_property("upper_bound", 0.99)  # exclude the saturated no-neighbour distance
    edge(graph, distance, "Out", near, "In")
    return near, "Out"


def band_lower(inner, outer):
    """The density filter's lower bound for a band: Distance sets density = distance / outer, so this drops the inner
    part that a nearer band covers."""
    return inner / outer


def bank_filter(band, inner, outer):
    """Ground above the shore between inner and outer cm of a water spline: one step of the bank falloff."""
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_UnderstoryBank" + band)
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    shore = z_range(graph, shore_height() + 150, 1.0e7)
    edge(graph, inp, "In", shore, "In")
    near, pin = water_near(graph, shore, "InsideFilter", outer, band_lower(inner, outer))
    edge(graph, near, pin, out, "Out")
    save(graph)
    return graph


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
    near, pin = water_near(graph, low, "OutsideFilter", 3000)
    edge(graph, near, pin, merge, "In")
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
        # Candidates/ha inside colonies: research trial ferns 0.5-2/m2, herb clumps 2-8/m2 (#32).
        ("Shrubs", variants.SHRUB_VARIANTS, 150), ("Ferns", variants.FERN_VARIANTS, 24000),
        ("Herbs", variants.HERB_VARIANTS, 20000), ("Ivy", variants.IVY_VARIANTS, 500),
        # Hazel masses in every canopy gap (0.7 ha): ~2 drifts in a 5 m gap, ~6 in a 9 m one, merging; see GAP_ONLY.
        ("GapShrubs", variants.GAP_SHRUB_VARIANTS, 2000)]
    paths = list({path for _, rows, _ in kinds for path, _ in rows})
    # Unique within a kind; a mesh may serve two kinds, as their drift and gap entries carry their own AssetTypes.
    if any(len({p for p, _ in rows}) != len(rows) or not rows or any(w <= 0 for _, w in rows) for _, rows, _ in kinds):
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
    actors = deadwood_rocks.load_forest_actors()
    biomes = [a for a in actors if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes or not any(a.get_actor_label() == LABEL and a.actor_has_tag("PCG_BiomeExclusion") for a in actors):
        raise RuntimeError("Build shore_path.py first; loaded forest biome or footpath exclusion missing")
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
    banks = [(band, bank_filter(band, inner, outer), shares) for band, inner, outer, shares in BANKS
             ] if args.group == "understory" else []
    entries = []
    # Understory (#32 rulings, interior_01): colonies rather than an even scatter, and plants grow under trees too
    # (overlap, so canopy bounds do not prune them). The template's spatial noise is world-space with no seed
    # parameter, so these identical settings give every understory generator the same colony field; the band
    # rejects low noise, leaving open moss floor between colonies.
    colonies = ({"SpatialDensityLow": 0.3, "SpatialDensityHigh": 1.0}, {"EnableVoronoiNoiseBreakup": True})
    for kind, rows, density in kinds:
        drift = DRIFTS.get(kind)
        patches = [None]
        if drift:
            count, length, width = drift
            density = density / count
            patches = [children(f"DA_{kind}Drift{k}", template, [(f"PCG_{kind}Drift{k}", drift_points(count, length, width, k),
                                                                  DRIFT_SCALE.get(kind, (0.7, 1.15)),
                                                                  [(meshes[p], w) for p, w in rows], True)])
                       for k in range(SHAPES)]
        # Dry ground gets the full colony density; damp ground adds half again (stream_bank_01).
        spread = [("Canopy", 1, canopy_filter(), True)] if kind in GAP_ONLY else [("Gaps", 1, plain, damp is not None)] + (
            [("Damp", 0.5, damp, True)] if damp else []) + (
            [("Canopy", CANOPY, canopy_filter(), True)] if args.group == "saplings" else []) + (
            [("Bank" + band, shares[kind], graph, True) for band, graph, shares in banks if kind in shares])
        for patch, share, transform, overlap in spread:
            doubles, bools = colonies if damp is not None else (None, None)
            if patch == "Canopy":
                doubles, bools = {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False}
            elif patch.startswith("Bank"):  # the colony noise still breaks the bank into runs, but keeps more of it
                doubles = {**doubles, "SpatialDensityLow": 0.0}
            # One point per (2 x extent)^2 cell at most, so the extent must allow the requested rate (#32 review).
            extent = min(100, 50 / math.sqrt(density * share / 10000))
            data = generator(kind + patch, density * args.density_scale * share, SLOPE.get(kind, 25), 30 if damp is None else 40,
                             doubles, bools, extent)
            value = data.get_editor_property("Generator")
            put(value, GeneratorAllowOverlap=overlap)
            data.set_editor_property("Generator", value)
            save(data)
            for (path, weight), (k, patch_list) in itertools.product(rows, enumerate(patches)):
                mesh = meshes[path]
                value = entry(template, mesh, data, transform, weight / len(patches), children=patch_list,
                              collision=False)
                if drift or patch == "Canopy":  # entries sharing a mesh with another generator need their own AssetType
                    put(value, AssetType=f"{kind}{patch}_{mesh.get_name()}" + (f"_{k}" if drift else ""))
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
    print("Understory grows in colonies, under trees too; Damp adds low (<12 m), flat (<25 deg) or near-water density")
    print("Regenerate ALL Core groups, inspect path/contact/wind, save level, then measure; thin Understory first")


if __name__ == "__main__":
    main()
