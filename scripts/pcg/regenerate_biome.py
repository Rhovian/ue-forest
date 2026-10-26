# editor-py: deferred
"""Lead only: regenerate L_vilm's partitioned Biome Core; optionally save its packages.

    scripts/editor-py scripts/pcg/regenerate_biome.py [--check] [--save]

--check never loads actors, regenerates or saves; counts describe currently loaded
instances plus on-disk WP cell descriptors. Build retains all map actors for complete
inputs/counts. --save saves only dirty map/terrain/water/biome/PCG and ForestBiome packages.
"""

import argparse
import builtins
import contextlib
import io
import json
import os
import time
import traceback

import unreal
from deadwood_rocks import get

MAP = "/Game/L_vilm"
CORE = "/PCGBiomeCore/BiomeCore.BiomeCore"
ACTIVE = "_forest_biome_regeneration"
MARKER = "__EDITOR_PY_DEFERRED__"


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


def dirty_allowed(loaded, world):
    # FileHelpers.h SaveDirtyPackages is global; GetDirty* + SavePackages is the scoped native API.
    # EditorAssetLibrary.cpp:GetPackageForObject uses UObject::GetPackage, including external actors.
    allowed = {unreal.EditorAssetLibrary.get_package_for_object(world).get_name()}
    for actor in loaded:
        if isinstance(actor, (unreal.LandscapeProxy, unreal.WaterBody, unreal.PCGPartitionActor)) or (
                actor.get_class().get_name().startswith("BP_PCGBiome") or actor.get_class().get_name() == "PCGWorldActor"):
            allowed.add(unreal.EditorAssetLibrary.get_package_for_object(actor).get_name())
    utils = unreal.EditorLoadingAndSavingUtils
    dirty = list(utils.get_dirty_map_packages()) + list(utils.get_dirty_content_packages())
    return {p.get_name(): p for p in dirty if p.get_name() in allowed or p.get_name().startswith("/Game/ForestBiome/")}


class Regeneration:
    def __init__(self, cores, world, destination, save):
        self.cores, self.world, self.destination, self.save = cores, world, destination, save
        self.pending = {c for _, c in cores}
        self.started, self.bindings = set(), []
        self.error, self.handle, self.finishing = None, None, False
        self.deadline = time.monotonic() + 540

    def complete(self, component):
        self.pending.discard(component)

    def started_graph(self, component):
        self.started.add(component)

    def cancelled(self, component):
        self.error = f"Generation cancelled: {component.get_path_name()}; nothing saved"

    def start(self):
        # PCGComponent.cpp:GenerateInternal schedules tasks; its dynamic generated/cancelled
        # delegates are the native completion signals. Sleeping on the game thread prevents completion.
        for _, component in self.cores:
            for prop, callback in (("on_pcg_graph_generated_external", self.complete),
                                   ("on_pcg_graph_cancelled_external", self.cancelled),
                                   ("on_pcg_graph_start_generating_external", self.started_graph)):
                delegate = component.get_editor_property(prop)
                delegate.add_callable(callback)
                self.bindings.append((delegate, callback))
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        for actor, component in self.cores:
            component.generate_local(True)
            if component not in self.started:
                raise RuntimeError(f"Core did not start (already busy or not eligible): {actor.get_actor_label()}")

    def cleanup(self):
        for delegate, callback in self.bindings:
            delegate.remove_callable(callback)
        self.bindings.clear()
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        setattr(builtins, ACTIVE, None)

    def tick(self, _delta):
        if self.finishing or (not self.error and self.pending and time.monotonic() < self.deadline):
            return
        self.finishing = True  # saving can pump editor events; never reenter finalization
        output, ok = io.StringIO(), False
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                if self.error or self.pending:
                    raise RuntimeError(self.error or "Generation timed out; nothing saved; do not rerun while PCG is busy")
                loaded = actors()
                report(loaded, self.cores)
                if self.save:
                    packages = dirty_allowed(loaded, self.world)
                    for name, package in sorted(packages.items()):
                        if not unreal.EditorLoadingAndSavingUtils.save_packages([package], True):
                            raise RuntimeError(f"Save failed: {name}")
                        print(f"Saved {name}")
                    remaining = dirty_allowed(loaded, self.world)
                    if remaining:
                        raise RuntimeError(f"Target packages remain dirty: {sorted(remaining)}")
                    print(f"Saved {len(packages)} allowed dirty packages")
                print("Biome Core regeneration complete")
                ok = True
            except Exception:  # noqa: BLE001 -- deferred command must return every failure to editor-py
                traceback.print_exc()
            finally:
                self.cleanup()
        # init_unreal.py's queue runner is synchronous; the opt-in editor-py protocol waits
        # on this result while Slate/PCG keep ticking. No alternative native queue-await API exists.
        temporary = self.destination + ".tmp"
        with open(temporary, "w") as stream:
            json.dump({"ok": ok, "output": output.getvalue()}, stream)
        os.replace(temporary, self.destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name() != MAP + ".L_vilm":
        raise RuntimeError("Open L_vilm in the editor (not PIE) before running")
    if getattr(builtins, ACTIVE, None):
        raise RuntimeError("A biome regeneration command is already waiting for completion")
    descriptors = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if descriptors is None:
        raise RuntimeError("World Partition descriptors unavailable")
    cell_class = unreal.PCGPartitionActor.static_class()
    cell_count = sum(unreal.MathLibrary.class_is_child_of(d.native_class, cell_class) for d in descriptors)
    print(f"On-disk WP partition cell actors: {cell_count} (all PCG graphs; excludes unsaved new cells)")
    loaded = actors()
    cores = roots(loaded)
    report(loaded, cores)
    candidates = dirty_allowed(loaded, world)
    print(f"Allowed dirty packages ({len(candidates)}): {sorted(candidates)}")
    validate(cores)
    if args.check:
        print("Preflight OK; counts are loaded instances only; no loads, generation or saves (--save ignored)")
        return
    destination = globals().get("EDITOR_PY_DEFERRED_RESULT")
    if not destination:
        raise RuntimeError("Use the updated scripts/editor-py deferred runner")
    # UE 5.8.3 WPBlueprintLibrary.cpp:193–206 retains the native loader adapter;
    # LoadActors refreshes synchronously. Retain all map inputs and existing cell outputs.
    unreal.WorldPartitionBlueprintLibrary.load_actors([d.guid for d in descriptors])
    cores = roots(actors())
    validate(cores)
    job = Regeneration(cores, world, destination, args.save)
    setattr(builtins, ACTIVE, job)
    try:
        job.start()
    except Exception:
        job.cleanup()
        raise
    print("Regenerating all Core groups; waiting for native completion delegates")
    print(MARKER)


if __name__ == "__main__":
    main()
