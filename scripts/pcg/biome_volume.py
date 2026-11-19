# editor-py: fresh-siblings
"""Set the forest biome volume's Local stage to bake per cell, with biome blending off (#264).

    scripts/editor-py scripts/pcg/biome_volume.py [--check]

Biome blending culls each generator's points by their distance to the biome's cache box, raised to
max(BlendingDensity, 1e-5). At BlendingDensity 0, PCGDistance's float rounding (+-2e-13 cm for interior points) turns
that exponent into a cull: positive residues become ~1 and the noise drops them, negative ones become NaN. It thinned
low ground unevenly unpartitioned and removed ~5/6 of every partitioned cell's points (#264). One biome has nothing to
blend: BlendingRange 0 makes BiomeCore_RunGenerators skip it. A partitioned Local generates cell by cell, so the bake is
bounded by a cell's content rather than the map's. regenerate_biome.py refuses to run unless both hold. Saves the
volume's package; the lead regenerates afterwards.
"""

import argparse

import unreal
from deadwood_rocks import load_forest_actors
from exact_exclusions import inputs

SETTINGS = {"BlendingRange": 0.0}  # operator decision on #264, 2026-11-18: one biome, no blending


def problems(locals_):
    """What keeps these Local components from a per-cell, unblended bake; empty when none."""
    found = [] if locals_ else ["no Local biome component loaded"]
    for local in locals_:
        volume = local.get_owner()
        found += [f"{volume.get_actor_label()}: {name} {volume.get_editor_property(name)}, want {value}"
                  for name, value in SETTINGS.items() if volume.get_editor_property(name) != value]
        if not local.get_editor_property("is_component_partitioned"):
            found.append(f"{volume.get_actor_label()}: Local is not partitioned")
    return found


def main():
    parser = argparse.ArgumentParser(prog="biome_volume.py")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actors = load_forest_actors() if not args.check else unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if args.check:
        print("\n".join(problems(inputs(actors))) or "Local: per cell, blending off")
        return
    for local in inputs(actors):
        volume = local.get_owner()
        volume.modify(True)
        for name, value in SETTINGS.items():
            volume.set_editor_property(name, value)
    # The volume's construction script replaces its components on edit: set partitioning on the fresh one.
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for local in inputs(actors):
        local.set_editor_property("is_component_partitioned", True)
    remaining = problems(inputs(actors))
    if remaining:
        raise RuntimeError("; ".join(remaining))
    for local in inputs(actors):
        package = unreal.EditorAssetLibrary.get_package_for_object(local.get_owner())
        if not unreal.EditorLoadingAndSavingUtils.save_packages([package], True):
            raise RuntimeError(f"Save failed: {package.get_name()}")
        print(f"Saved {package.get_name()}: Local per cell, blending off")


if __name__ == "__main__":
    main()
