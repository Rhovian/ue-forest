"""Conservative long-trunk water keep-out; never changes shared biome exclusions."""

import unreal


def water_keepout(graph, source, pin, reach, edge):
    # Native actor bounds, BoundsModifier.Translate and binary Difference already do the job:
    # UE 5.8 PCGBasePointData.cpp:AddSinglePointFromActor; PCGBoundsModifier.cpp:Translate.
    water, settings = graph.add_node_of_type(unreal.PCGDataFromActorSettings)
    selection = settings.get_editor_property("actor_selector")
    for name, value in {"actor_filter": unreal.PCGActorFilter.ALL_WORLD_ACTORS,
                        "actor_selection_tag": "PCG_BiomeExclusion", "select_multiple": True}.items():
        selection.set_editor_property(name, value)
    settings.set_editor_property("actor_selector", selection)
    settings.set_editor_property("mode", unreal.PCGGetDataFromActorMode.GET_SINGLE_POINT)
    expand, settings = graph.add_node_of_type(unreal.PCGBoundsModifierSettings)
    settings.set_editor_property("mode", unreal.PCGBoundsModifierMode.TRANSLATE)
    settings.set_editor_property("bounds_min", unreal.Vector(-reach - 300, -reach - 300, -1.0e7))
    settings.set_editor_property("bounds_max", unreal.Vector(reach + 300, reach + 300, 1.0e7))
    edge(graph, water, "Out", expand, "In")
    difference, settings = graph.add_node_of_type(unreal.PCGDifferenceSettings)
    settings.set_editor_property("density_function", unreal.PCGDifferenceDensityFunction.BINARY)
    settings.set_editor_property("mode", unreal.PCGDifferenceMode.DISCRETE)
    settings.set_editor_property("diff_metadata", False)
    edge(graph, expand, "Out", difference, "Differences")
    edge(graph, source, pin, difference, "Source")
    return difference, "Out"
