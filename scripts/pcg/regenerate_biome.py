# editor-py: fresh-siblings
"""Lead only: check L_vilm's partitioned Biome Core before a bake and report its instance counts.

    scripts/editor-py scripts/pcg/regenerate_biome.py

Never loads actors, regenerates or saves; counts describe currently loaded instances plus on-disk WP cell
descriptors. The bake itself is scripts/pcg/bake (World Partition builder, #264): one editor session cannot
generate the partitioned Local, whose footprint grows 8-10 GB per dense cell and is not returned.
"""

import unreal
from biome_volume import problems as volume_problems
from deadwood_rocks import get
from exact_exclusions import inputs as local_inputs

MAP = "/Game/L_vilm"
CORE = "/PCGBiomeCore/BiomeCore.BiomeCore"


def actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def roots(loaded):
    found = []
    for actor in loaded:
        if isinstance(actor, unreal.PCGPartitionActor):
            continue
        for component in actor.get_components_by_class(unreal.PCGComponent):
            instance = component.get_editor_property("graph_instance")
            if instance and instance.get_const_pcg_graph().get_path_name() == CORE:
                found.append((actor, component))
    if not found:
        raise RuntimeError("No loaded Biome Core actor/component found in L_vilm")
    return found


def report(loaded, cores):
    for actor, component in cores:
        print(f"Core {actor.get_actor_label()}: partitioned={component.get_editor_property('is_component_partitioned')}, "
              f"trigger={component.get_editor_property('generation_trigger')}, "
              f"editing={component.get_editor_property('current_editing_mode')}, "
              f"generated={component.get_editor_property('generated')}")
    # Mesh membership comes from the attached reusable asset lists, including recursive children.
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
    for actor in loaded:
        if actor.get_class().get_name().startswith("BP_PCGBiomeVolume"):
            for data in actor.get_editor_property("Assets"):
                group = data.get_name().removeprefix("DA_Forest_").removesuffix("Assets")
                groups.add(group)
                palette(data, group, set())
    cells = [a for a in loaded if isinstance(a, unreal.PCGPartitionActor)
             and any(a.get_local_component(c) for _, c in cores)]
    totals = dict.fromkeys(sorted(groups), 0)
    for actor in cells + [a for a, _ in cores]:
        for cls, prop in ((unreal.InstancedStaticMeshComponent, "static_mesh"),
                          (unreal.InstancedSkinnedMeshComponent, "skinned_asset")):
            for component in actor.get_components_by_class(cls):
                mesh = component.get_editor_property(prop)
                memberships = mesh_groups.get(mesh.get_path_name(), set()) if mesh else set()
                group = next(iter(memberships)) if len(memberships) == 1 else "UNCLASSIFIED/SHARED"
                totals[group] = totals.get(group, 0) + component.get_instance_count()
    generated = sum(any(local and local.get_editor_property("generated")
                        for local in (a.get_local_component(c) for _, c in cores)) for a in cells)
    print(f"Loaded Core partition cells: {len(cells)}; generated: {generated}")
    for group, count in sorted(totals.items()):
        print(f"Instances {group}: {count}")


def validate(cores):
    for _, component in cores:
        if not component.get_editor_property("is_component_partitioned") or (
                component.get_editor_property("generation_trigger") == unreal.PCGComponentGenerationTrigger.GENERATE_AT_RUNTIME
                or component.get_editor_property("current_editing_mode") != unreal.PCGEditorDirtyMode.NORMAL
                or component.get_editor_property("serialized_editing_mode") != unreal.PCGEditorDirtyMode.NORMAL):
            raise RuntimeError("Core must be partitioned, editor-generated and in saved Normal mode")
    found = volume_problems(local_inputs(actors()))
    if found:
        raise RuntimeError(f"Run biome_volume.py first: {'; '.join(found)}")


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name() != MAP + ".L_vilm":
        raise RuntimeError("Open L_vilm in the editor (not PIE) before running")
    descriptors = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if descriptors is None:
        raise RuntimeError("World Partition descriptors unavailable")
    cell_class = unreal.PCGPartitionActor.static_class()
    cell_count = sum(unreal.MathLibrary.class_is_child_of(d.native_class, cell_class) for d in descriptors)
    print(f"On-disk WP partition cell actors: {cell_count} (all PCG graphs; excludes unsaved new cells)")
    loaded = actors()
    cores = roots(loaded)
    report(loaded, cores)
    validate(cores)
    print("Preflight OK; counts are loaded instances only. Bake: scripts/editor.sh close, then scripts/pcg/bake")


if __name__ == "__main__":
    main()
