# editor-py: fresh-siblings
"""Install continuous XY exclusions in project asset TransformGraphs; never copy Core.

    scripts/editor-py scripts/pcg/exact_exclusions.py [--check]

Run after rebuilding groups, before regenerate_biome.py --save. Re-runnable. Check
only reads loaded actors/graphs; build retains WP inputs and saves project graphs.
"""

import argparse

import unreal
from deadwood_rocks import ROOT, edge, get, load_forest_actors, save

LOCAL = "/PCGBiomeCore/LocalBiomeCore.LocalBiomeCore"


def inputs(actors):
    return [component for actor in actors for component in actor.get_components_by_class(unreal.PCGComponent)
            if component.get_editor_property("graph_instance").get_const_pcg_graph().get_path_name() == LOCAL]


def graphs(actors):
    found, seen = set(), set()
    def visit(data):
        if data in seen:
            return
        seen.add(data)
        for row in data.get_editor_property("BiomeAssets"):
            graph = get(row, "TransformGraph")
            if graph:
                if not graph.get_path_name().startswith(ROOT):
                    raise RuntimeError(f"Refusing non-project TransformGraph: {graph.get_path_name()}")
                found.add(graph)
            child = get(row, "ChildAssets")
            if child:
                visit(child)
    for actor in actors:
        if actor.get_class().get_name().startswith("BP_PCGBiomeVolume"):
            for data in actor.get_editor_property("Assets"):
                visit(data)
    if not found:
        raise RuntimeError("No loaded forest asset TransformGraphs")
    return sorted(found, key=lambda graph: graph.get_path_name())


def bounds(graph, amount):
    node, settings = graph.add_node_of_type(unreal.PCGBoundsModifierSettings)
    settings.set_editor_property("mode", unreal.PCGBoundsModifierMode.TRANSLATE)
    settings.set_editor_property("bounds_min", unreal.Vector(0, 0, -amount))
    settings.set_editor_property("bounds_max", unreal.Vector(0, 0, amount))
    return node


def connections(graph):
    return [e for pin in graph.get_output_node().get_editor_property("input_pins") for e in pin.get_editor_property("edges")]


def patch(graph):
    if any(isinstance(n.get_settings(), unreal.PCGCreateSurfaceFromSplineSettings) for n in graph.get_editor_property("nodes")):
        return False
    previous = connections(graph)
    if not previous:
        raise RuntimeError(f"TransformGraph has no output connections: {graph.get_path_name()}")
    before, after = bounds(graph, 1.0e7), bounds(graph, -1.0e7)
    actors, settings = graph.add_node_of_type(unreal.PCGDataFromActorSettings)
    selector = settings.get_editor_property("actor_selector")
    for name, value in {"actor_filter": unreal.PCGActorFilter.ALL_WORLD_ACTORS,
                        "actor_selection": unreal.PCGActorSelection.BY_TAG,
                        "actor_selection_tag": "PCG_BiomeExclusion", "select_multiple": True,
                        "must_overlap_self": False}.items():
        selector.set_editor_property(name, value)
    settings.set_editor_property("actor_selector", selector)
    settings.set_editor_property("mode", unreal.PCGGetDataFromActorMode.PARSE_ACTOR_COMPONENTS)
    components = settings.get_editor_property("component_selector")
    components.set_editor_property("component_selection", unreal.PCGComponentSelection.BY_CLASS)
    components.set_editor_property("component_selection_class", unreal.SplineComponent)
    settings.set_editor_property("component_selector", components)
    # UE 5.8 LocalBiomeCore samples exclusion interiors every 400 cm. Use native
    # SplineInteriorSurfaceData::PointInsidePolygon instead of rasterizing a 3 m path.
    surface, _ = graph.add_node_of_type(unreal.PCGCreateSurfaceFromSplineSettings)
    difference, settings = graph.add_node_of_type(unreal.PCGDifferenceSettings)
    settings.set_editor_property("density_function", unreal.PCGDifferenceDensityFunction.BINARY)
    settings.set_editor_property("mode", unreal.PCGDifferenceMode.DISCRETE)
    settings.set_editor_property("diff_metadata", False)
    edge(graph, actors, "Out", surface, "In")
    edge(graph, surface, "Out", difference, "Differences")
    edge(graph, before, "Out", difference, "Source")
    edge(graph, difference, "Out", after, "In")
    # Surface SamplePoint also tests Z against the flat spline. DifferenceData.cpp
    # copies survivors' bounds unchanged: temporarily extend Z then invert BEFORE
    # returning to Core, preserving transforms, canopy pruning and collision bounds.
    for old in previous:
        source, pin, target_pin = old.get_input_node(), old.get_input_pin_label(), old.get_output_pin_label()
        if not graph.remove_edge(source, pin, graph.get_output_node(), target_pin):
            raise RuntimeError("Could not splice exact exclusions into TransformGraph")
        edge(graph, source, pin, before, "In")
        if not any(e.get_input_node() == after for e in connections(graph)):
            edge(graph, after, "Out", graph.get_output_node(), target_pin)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actors = (unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if args.check else load_forest_actors())
    targets = graphs(actors)
    if not any(a.get_actor_label() == "ForestFootpath_ShoreLake" for a in actors):
        raise RuntimeError("Load/build the footpath before installing exact exclusions")
    for graph in targets:
        if not connections(graph):
            raise RuntimeError(f"No output connections: {graph.get_path_name()}")
        if args.check:
            print("Exact exclusion target:", graph.get_path_name())
        else:
            changed = patch(graph)
            save(graph)
            print("Exact exclusions", "installed:" if changed else "retained:", graph.get_path_name())
    print(f"{len(targets)} project TransformGraphs; " + ("no edits, loads or saves" if args.check else "regenerate Local inputs/Core and save"))


if __name__ == "__main__":
    main()
