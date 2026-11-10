# editor-py: fresh-siblings
"""Keep tree trunks and shrub stems out of the rocks, logs and stumps (#182).

    scripts/editor-py scripts/pcg/solid_keepout.py [--check]

The solid groups allow overlap (deadwood_rocks.generator: Core's priority difference uses the trees' canopy bounds and
erased nearly every rock and log under them), so nothing kept a trunk out of a boulder: 413 of 1,357 solids had a stem
inside them, mostly hazel and huckleberry standing on the rocks' own sampler points. This bakes every placed solid's
footprint (its instance transform and mesh box) into each TransformGraph a tree, sapling or shrub uses, and drops the
plants standing in one, so they give way and the rocks keep their count. Graphs of the tree groups alone keep trunks
TRUNK_CM off; graphs shared with ferns and flowers test the pivot only. Child graphs are left alone: the seedlings on
the nurse logs stand on them by design. Re-runnable: a rerun replaces the baked footprints.

Footprints come from the placed level, so run it after a regenerate, then regenerate again: after exact_exclusions.py,
and again whenever the solid groups change (deadwood_rocks.py, shore_logs.py, biome_variants' solid palettes).
"""

import argparse
import itertools

import biome_variants
import unreal
from deadwood_rocks import edge, get, load_forest_actors, save
from exact_exclusions import connections

TITLE = "SolidFootprints"  # node title of the baked footprints, so a rerun finds and refreshes them
TRUNK_CM = 50.0  # trunk radius and root flare: how far a tree point stays off a footprint
FOOTPRINT_Z = 2000.0  # half height of a footprint in its local space: covers any slope under the solid
SOLIDS = {biome_variants.asset_path(path).rsplit("/", 1)[1] for path, _ in
          biome_variants.LOG_VARIANTS + biome_variants.MEADOW_LOG_VARIANTS + biome_variants.STUMP_VARIANTS
          + biome_variants.SLAB_VARIANTS + biome_variants.WATERLINE_BOULDER_VARIANTS}


TREE_GROUPS = ("DA_Forest_TreesAssets", "DA_Forest_VeteranAssets", "DA_Forest_HornbeamAssets", "DA_Forest_ShoreTreesAssets")
PIVOT_CM = 1.0  # a shared plant graph tests the pivot alone (a zero box overlaps nothing)


def kind(data, row):
    """"tree" for the tree groups' rows, "stems" for the Megaplants saplings and shrubs elsewhere, else None."""
    if data.get_name() in TREE_GROUPS:
        return "tree"
    mesh = get(row, "SkeletalMesh") or get(row, "Mesh")
    return "stems" if mesh and mesh.get_name().startswith(("Tree_", "Shrub_")) else None


def targets(actors):
    """{TransformGraph: margin cm} for each top-level graph a tree, sapling or shrub uses: TRUNK_CM where only tree
    groups use it, PIVOT_CM where ferns and flowers share it (they may stand at a rock's foot)."""
    rows, seen = {}, set()
    for actor in actors:
        if not actor.get_class().get_name().startswith("BP_PCGBiomeVolume"):
            continue
        for data in actor.get_editor_property("Assets"):
            if data in seen:
                continue
            seen.add(data)
            for row in data.get_editor_property("BiomeAssets"):
                graph = get(row, "TransformGraph")
                if graph:
                    rows.setdefault(graph, set()).add(kind(data, row))
    found = {graph: TRUNK_CM if kinds == {"tree"} else PIVOT_CM for graph, kinds in rows.items() if kinds - {None}}
    if not found:
        raise RuntimeError("No woody TransformGraphs loaded")
    return found


def footprints(actors):
    """A PCG point per placed solid: its world transform, bounds its mesh's xy box and FOOTPRINT_Z high."""
    points = []
    for actor in actors:
        for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            mesh = component.static_mesh
            if not mesh or mesh.get_name() not in SOLIDS:
                continue
            box = mesh.get_bounding_box()
            for i in range(component.get_instance_count()):
                point = unreal.PCGPoint()
                point.set_editor_property("transform", component.get_instance_transform(i, True))
                point.set_editor_property("bounds_min", unreal.Vector(box.min.x, box.min.y, -FOOTPRINT_Z))
                point.set_editor_property("bounds_max", unreal.Vector(box.max.x, box.max.y, FOOTPRINT_Z))
                point.set_editor_property("steepness", 1.0)
                points.append(point)
    if not points:
        raise RuntimeError("No placed solids found: regenerate the biome first")
    return points


def node(graph, settings_class, title=None, **values):
    added, settings = graph.add_node_of_type(settings_class)
    for name, value in values.items():
        settings.set_editor_property(name, value)
    if title:
        added.set_editor_property("node_title", title)
    return added


def copy(graph, source, target):
    """Copy one attribute or point property to another on the same points."""
    selector = unreal.PCGAttributePropertyInputSelector()
    selector.import_text(f"PCGBegin({source})PCGEnd")
    output = unreal.PCGAttributePropertyOutputSelector()
    output.import_text(f"PCGBegin({target})PCGEnd")
    return node(graph, unreal.PCGCopyAttributesSettings, input_source=selector, output_target=output)


def chain(graph, nodes):
    for a, b in itertools.pairwise(nodes):
        for pin in [p.get_editor_property("properties").get_editor_property("label") for p in b.get_editor_property("input_pins")]:
            edge(graph, a, "Out", b, pin)


def patch(graph, margin):
    """Splice footprint pruning in front of the output: plant bounds shrink to the margin round the pivot for the test
    (the difference keeps survivors' bounds as tested), then get their own back, which Core prunes canopies with."""
    previous = connections(graph)
    if not previous:
        raise RuntimeError(f"TransformGraph has no output connections: {graph.get_path_name()}")
    keep = [copy(graph, "$BoundsMin", "KeepoutBoundsMin"), copy(graph, "$BoundsMax", "KeepoutBoundsMax"),
            node(graph, unreal.PCGBoundsModifierSettings, mode=unreal.PCGBoundsModifierMode.SET,
                 bounds_min=unreal.Vector(-margin, -margin, -10), bounds_max=unreal.Vector(margin, margin, 10))]
    restore = [copy(graph, "KeepoutBoundsMin", "$BoundsMin"), copy(graph, "KeepoutBoundsMax", "$BoundsMax"),
               node(graph, unreal.PCGDeleteAttributesSettings, selected_attributes="KeepoutBoundsMin,KeepoutBoundsMax")]
    chain(graph, keep)
    chain(graph, restore)
    difference = node(graph, unreal.PCGDifferenceSettings, density_function=unreal.PCGDifferenceDensityFunction.BINARY,
                      mode=unreal.PCGDifferenceMode.DISCRETE, diff_metadata=False)
    marks = node(graph, unreal.PCGCreatePointsSettings, TITLE, coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                 cull_points_outside_volume=False)
    edge(graph, keep[-1], "Out", difference, "Source")
    edge(graph, marks, "Out", difference, "Differences")
    edge(graph, difference, "Out", restore[0], "Source")
    edge(graph, difference, "Out", restore[0], "Target")
    for old in previous:
        source, pin, target_pin = old.get_input_node(), old.get_input_pin_label(), old.get_output_pin_label()
        if not graph.remove_edge(source, pin, graph.get_output_node(), target_pin):
            raise RuntimeError("Could not splice the solid keep-out into the TransformGraph")
        edge(graph, source, pin, keep[0], "Source")
        edge(graph, source, pin, keep[0], "Target")
        if not any(e.get_input_node() == restore[-1] for e in connections(graph)):
            edge(graph, restore[-1], "Out", graph.get_output_node(), target_pin)
    return marks


def installed(graph):
    return next((n for n in graph.get_editor_property("nodes") if str(n.get_editor_property("node_title")) == TITLE), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actors = (unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if args.check else load_forest_actors())
    points = footprints(actors)
    for graph, margin in sorted(targets(actors).items(), key=lambda item: item[0].get_name()):
        marks = installed(graph)
        if args.check:
            print(f"{graph.get_name()}: margin {margin:g} cm, " + ("installed" if marks else "not installed"))
            continue
        marks = marks or patch(graph, margin)
        marks.get_settings().set_editor_property("points_to_create", points)
        save(graph)
        print(f"{graph.get_name()}: {len(points)} footprints, margin {margin:g} cm")
    if not args.check:
        print("Regenerate Core and save the level")


if __name__ == "__main__":
    main()
