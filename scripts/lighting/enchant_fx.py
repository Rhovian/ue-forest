"""Place the enchanted wisps and motes (#40) over the forest of L_vilm.

    scripts/editor-py scripts/lighting/enchant_fx.py

NS_ForestEnchant (built in the editor; material from scripts/materials/wisp.py) has two emitters over a 30 m box:
low blue mist wisps at about knee height (clearing_01) and pale dust motes. One system sits on a fixed, seeded share
of the 30 m cells of land above the beach, so the wisps drift in patches; each emitter culls itself beyond 45 m.
Each system sits on, and tilts with, a plane fitted to the ground over its cell, so the spawn box follows slopes and
the wisps stay near knee height (#58 review: centre height alone left ~1 m errors on a quarter of the footprint).
Reruns update the systems in place by label. Saves only their actor packages.
"""

import math
import random

import unreal

SYSTEM = "/Game/ForestBiome/FX/NS_ForestEnchant"
LABEL = "Enchant"  # label prefix and outliner folder
CELL = 3000  # cm; matches the emitters' 30 m box
ABOVE = 60  # cm above the sea: land, including the low coastal meadow (clearing ~1 m), not the sand (~0.2 m)
STEEPEST = math.tan(math.radians(25))  # ground plane gradient above which a cell gets no system
UNEVEN = 150  # cm: largest ground deviation from the cell's plane, e.g. a bank inside the cell
SHARE = 0.7  # of land cells that get a system; gaps between patches stay, but every open meadow gets some

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name() != "/Game/L_vilm.L_vilm":
    raise RuntimeError("Open L_vilm in the editor (not PIE) before running")
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
# Every World Partition cell must be loaded, or traces over unloaded landscape miss (see forest_look.py).
unreal.WorldPartitionBlueprintLibrary.load_actors([d.guid for d in unreal.WorldPartitionBlueprintLibrary.get_actor_descs()])
system = unreal.load_asset(SYSTEM)


def ground(x, y):
    """Landscape height at (x, y), ignoring anything else the ray meets; None off the landscape."""
    start, end, ignored = unreal.Vector(x, y, 100000), unreal.Vector(x, y, -100000), []
    for _ in range(64):
        hit = unreal.SystemLibrary.line_trace_single(
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, unreal.DrawDebugTrace.NONE, True
        )
        if hit is None:
            return None
        fields = hit.to_tuple()
        if isinstance(fields[9], unreal.LandscapeProxy):
            return fields[4].z
        ignored.append(fields[9])
    return None


FIT = [-1200, -600, 0, 600, 1200]  # cm; 5 x 5 ground samples for the plane


def ground_plane(x, y):
    """Least-squares plane z = c + a*dx + b*dy through the ground around (x, y): (c, a, b, largest residual in cm), or
    None off the island."""
    samples = [(dx, dy, ground(x + dx, y + dy)) for dx in FIT for dy in FIT]
    samples = [s for s in samples if s[2] is not None]
    if len(samples) < len(FIT) ** 2 // 2:
        return None
    n = len(samples)
    mx, my, mz = (sum(s[k] for s in samples) / n for k in range(3))
    a = sum((s[0] - mx) * (s[2] - mz) for s in samples) / sum((s[0] - mx) ** 2 for s in samples)
    b = sum((s[1] - my) * (s[2] - mz) for s in samples) / sum((s[1] - my) ** 2 for s in samples)
    c = mz - a * mx - b * my
    return c, a, b, max(abs(s[2] - c - a * s[0] - b * s[1]) for s in samples)


old = {a.get_actor_label(): a for a in subsystem.get_all_level_actors() if a.get_actor_label().startswith(LABEL + "_")}
placed = []
for i in range(110000 // CELL + 1):
    for j in range(100000 // CELL + 1):
        x, y = i * CELL + CELL / 2, -j * CELL - CELL / 2
        z = ground(x, y)
        if z is None and 15000 < x < 100000 and -95000 < y < -10000:
            raise RuntimeError(f"no landscape under ({x / 100:.0f}, {y / 100:.0f}) m inside the island; are all cells loaded?")
        if z is None or z < ABOVE or random.Random(f"enchant {i},{j}").random() >= SHARE:
            continue
        plane = ground_plane(x, y)
        if plane is None:
            continue
        c, a, b, residual = plane
        # Mist lies on gentle, even ground; on or across a bank face it reads as floating blobs (beach, edge_in).
        if math.hypot(a, b) > STEEPEST or residual > UNEVEN:
            continue
        label = f"{LABEL}_{i:02d}_{j:02d}"
        actor = old.pop(label, None) or subsystem.spawn_actor_from_object(system, unreal.Vector(x, y, c))
        # Shape Location applies the owner's transform, so the box tilts with the actor.
        rotation = unreal.MathLibrary.make_rot_from_z(unreal.Vector(-a, -b, 1))
        actor.set_actor_location_and_rotation(unreal.Vector(x, y, c), rotation, False, False)
        actor.set_actor_label(label)
        actor.set_folder_path(LABEL)
        for component in actor.get_components_by_class(unreal.PrimitiveComponent):
            if not isinstance(component, unreal.NiagaraComponent):  # editor icon and arrow, which show in captures
                component.set_editor_property("visible", False)
        placed.append(actor)
packages = [a.get_package() for a in old.values()]
for actor in old.values():
    subsystem.destroy_actor(actor)
packages += [a.get_package() for a in placed]
if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
    raise RuntimeError("could not save the enchant actors")
print(f"{len(placed)} enchant systems; {len(old)} removed")
