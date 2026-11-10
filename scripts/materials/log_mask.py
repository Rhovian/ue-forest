"""Bake /Game/ForestBiome/T_LogMask: where the floor's tall Landscape Grass thins out around logs and rocks (#117).

    scripts/editor-py scripts/materials/log_mask.py

Landscape Grass knows nothing of the PCG logs, so ferns and undergrowth grew straight through them and hid them
(nurse_log stop, operator 2026-11-09: on and beside logs and rocks). This reads every placed log (biome_variants
LOG_VARIANTS and the meadow's) and rock slab or boulder (SLAB_VARIANTS) from the generated instances, rasterises its
footprint on T_GroundcoverMask's 2 m grid (same cells, same UVs) and grows it by two cells, at ON_LOG rather than
black: plants still grow on and against a log, only fewer (operator: a log with nothing on it is not the target
either). forest_floor.py multiplies it into the groundcover and undergrowth, and keeps its rock and slab layers
(SOLID_KINDS) off the logs entirely. The hand-placed shore logs (shore_logs.py) count too (#160).
Rerun after every regenerate that moves logs, then forest_floor.py.
"""

import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
import biome_variants
from groundcover_mask import CELL, bounds, import_texture
from mask_raster import dilate, fill

NAME = "T_LogMask"
ON_LOG = 0.3  # share of the tall cover kept on and beside a log or rock


def log_meshes():
    rows = (biome_variants.LOG_VARIANTS + biome_variants.MEADOW_LOG_VARIANTS + biome_variants.SHORE_LOG_VARIANTS
            + biome_variants.SLAB_VARIANTS)
    return {path.rsplit("/", 1)[1] for path, _ in rows}


def footprints():
    """Each placed log's footprint corners in world cm."""
    names, out = log_meshes(), []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        # Instanced: the PCG logs and rocks; plain: the hand-placed shore logs (shore_logs.py, #160).
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = component.static_mesh
            if not mesh or mesh.get_name() not in names:
                continue
            box = mesh.get_bounding_box()
            corners = [unreal.Vector(x, y, 0) for x, y in ((box.min.x, box.min.y), (box.max.x, box.min.y),
                                                            (box.max.x, box.max.y), (box.min.x, box.max.y))]
            if isinstance(component, unreal.InstancedStaticMeshComponent):
                transforms = [component.get_instance_transform(i, True) for i in range(component.get_instance_count())]
            else:
                transforms = [component.get_world_transform()]
            for transform in transforms:
                out.append([unreal.MathLibrary.transform_location(transform, c) for c in corners])
    return out


def main():
    x0, y0, width, height = bounds()
    pixels = bytearray(b"\xff" * (width * height))
    logs = footprints()
    if not logs:
        raise SystemExit("no placed logs found: regenerate the biome first")
    for corners in logs:
        fill(pixels, width, height, [((p.x - x0) / CELL, (p.y - y0) / CELL) for p in corners])
    # Two cells, not one: forest_floor.py keeps its rock layers at zero below CLEAR_OF_LOGS, and the grass weight is
    # interpolated between 2 m landscape vertices, so one cell let weight from the clear cell beyond leak into the
    # footprint (#173 review). The plants' thinning reaches as far.
    pixels = dilate(pixels, width, height, 2)
    kept = round(255 * ON_LOG)
    pixels = bytearray(kept if v == 0 else v for v in pixels)
    import_texture(pixels, width, height, NAME)
    print(f"{NAME}: {len(logs)} logs and rocks, {sum(1 for v in pixels if v == kept) * CELL * CELL / 1e4:.0f} m2 thinned")


if __name__ == "__main__":
    main()
