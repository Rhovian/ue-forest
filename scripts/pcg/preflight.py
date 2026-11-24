# editor-py: fresh-siblings
"""Lead only: check L_vilm's forest placement before a bake and report its instance counts.

    scripts/editor-py scripts/pcg/preflight.py

Never loads actors, regenerates or saves; counts describe currently loaded instances plus on-disk WP cell
descriptors. The bake itself is scripts/pcg/bake (World Partition builder): it generates placement.py's graph on the
PCG volume placement.LABEL, one 256 m cell at a time, over the builder volume placement.BUILDER_LABEL.
"""

import unreal
from deadwood_rocks import asset_lists, get
from placement import BUILDER_LABEL, LABEL, NAME, OUT

MAP = "/Game/L_vilm"


def actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def placement(loaded):
    found = [a for a in loaded if a.get_actor_label() == LABEL and isinstance(a, unreal.PCGVolume)]
    if len(found) != 1:
        raise RuntimeError(f"Expected one PCG volume {LABEL}, found {len(found)}: run placement.py")
    return found[0], found[0].get_component_by_class(unreal.PCGComponent)


def report(loaded, component):
    print(f"{LABEL}: partitioned={component.get_editor_property('is_component_partitioned')}, "
          f"trigger={component.get_editor_property('generation_trigger')}, "
          f"editing={component.get_editor_property('current_editing_mode')}")
    # Mesh membership comes from the group asset lists, including recursive children.
    groups, mesh_groups = set(), {}
    def palette(data, group, seen):
        if data in seen:
            return
        seen.add(data)
        for row in data.get_editor_property("BiomeAssets"):
            for key in ("Mesh", "SkeletalMesh"):
                mesh = get(row, key)
                if mesh:
                    mesh_groups.setdefault(mesh.get_path_name(), set()).add(group)
            child = get(row, "ChildAssets")
            if child:
                palette(child, group, seen)
    for data in asset_lists():
        group = data.get_name().removeprefix("DA_Forest_").removesuffix("Assets")
        groups.add(group)
        palette(data, group, set())
    cells = [a for a in loaded if isinstance(a, unreal.PCGPartitionActor) and a.get_local_component(component)]
    totals = dict.fromkeys(sorted(groups), 0)
    for actor in cells:
        for cls, prop in ((unreal.InstancedStaticMeshComponent, "static_mesh"),
                          (unreal.InstancedSkinnedMeshComponent, "skinned_asset")):
            for mesh_component in actor.get_components_by_class(cls):
                mesh = mesh_component.get_editor_property(prop)
                memberships = mesh_groups.get(mesh.get_path_name(), set()) if mesh else set()
                group = next(iter(memberships)) if len(memberships) == 1 else "UNCLASSIFIED/SHARED"
                totals[group] = totals.get(group, 0) + mesh_component.get_instance_count()
    generated = sum(bool(a.get_local_component(component).get_editor_property("generated")) for a in cells)
    print(f"Loaded placement partition cells: {len(cells)}; generated: {generated}")
    for group, count in sorted(totals.items()):
        print(f"Instances {group}: {count}")


def validate(loaded, volume, component):
    graph = component.get_graph()
    if not graph or graph.get_path_name() != f"{OUT}{NAME}.{NAME}":
        raise RuntimeError(f"{LABEL} must carry {OUT}{NAME}: run placement.py --attach")
    if not component.get_editor_property("is_component_partitioned") or (
            component.get_editor_property("generation_trigger") == unreal.PCGComponentGenerationTrigger.GENERATE_AT_RUNTIME
            or component.get_editor_property("current_editing_mode") != unreal.PCGEditorDirtyMode.NORMAL
            or component.get_editor_property("serialized_editing_mode") != unreal.PCGEditorDirtyMode.NORMAL):
        raise RuntimeError(f"{LABEL} must be partitioned, editor-generated and in saved Normal mode")
    builders = [a for a in loaded if a.get_actor_label() == BUILDER_LABEL and isinstance(a, unreal.PCGBuilderVolume)]
    origin, extent = volume.get_actor_bounds(False)
    if len(builders) != 1 or any(abs(a - b) > 1.0 for pair in zip(builders[0].get_actor_bounds(False), (origin, extent))
                                 for a, b in zip(pair[0].to_tuple(), pair[1].to_tuple())):
        raise RuntimeError(f"{BUILDER_LABEL} must match {LABEL}'s bounds: run placement.py --attach")
    plugin = sorted({a.get_actor_label() for a in loaded if a.get_class().get_path_name().startswith("/PCGBiome")}
                    | {a.get_actor_label() for a in loaded for c in a.get_components_by_class(unreal.PCGComponent)
                       if c.get_graph() and c.get_graph().get_path_name().startswith("/PCGBiome")})
    if plugin:
        raise RuntimeError(f"Biome Core actors or components in the level (#266): {plugin}")


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name() != MAP + ".L_vilm":
        raise RuntimeError("Open L_vilm in the editor (not PIE) before running")
    descriptors = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if descriptors is None:
        raise RuntimeError("World Partition descriptors unavailable")
    cell_class = unreal.PCGPartitionActor.static_class()
    cell_count = sum(unreal.MathLibrary.class_is_child_of(d.native_class, cell_class) for d in descriptors)
    print(f"On-disk WP partition cell actors: {cell_count} (excludes unsaved new cells)")
    loaded = actors()
    volume, component = placement(loaded)
    report(loaded, component)
    validate(loaded, volume, component)
    print("Preflight OK; counts are loaded instances only. Bake: scripts/editor.sh close, then scripts/pcg/bake")


if __name__ == "__main__":
    main()
