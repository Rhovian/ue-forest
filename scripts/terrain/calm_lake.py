"""Calm the lake (#141): no Gerstner waves on the lake water body.

    scripts/editor-py scripts/terrain/calm_lake.py

The lake's LakeWaterWaves moved its surface like open water (lake_edge stop, operator 2026-11-09: too much movement).
Without waves only the water material's small surface detail remains. Saves the lake actor's package only.
"""

import unreal

LAKES = ("Lake",)  # water body labels to calm

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
lakes = [a for a in subsystem.get_all_level_actors() if isinstance(a, unreal.WaterBodyLake) and a.get_actor_label() in LAKES]
if len(lakes) != len(LAKES):
    raise SystemExit(f"expected lakes {LAKES}, found {[a.get_actor_label() for a in lakes]}")
for lake in lakes:
    lake.set_editor_property("water_waves", None)
if not unreal.EditorLoadingAndSavingUtils.save_packages([lake.get_package() for lake in lakes], False):
    raise SystemExit("could not save the lake")
print(f"calmed {[lake.get_actor_label() for lake in lakes]}")
