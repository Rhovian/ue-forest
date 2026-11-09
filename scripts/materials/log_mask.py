"""Bake /Game/ForestBiome/T_LogMask: where the floor's tall Landscape Grass thins out around fallen logs (#117).

    scripts/editor-py scripts/materials/log_mask.py

Landscape Grass knows nothing of the PCG logs, so ferns and undergrowth grew straight through them and hid them
(nurse_log stop, operator 2026-11-09). This reads every placed log (biome_variants.LOG_VARIANTS and the meadow's) from
the generated instances, rasterises its footprint on T_GroundcoverMask's 2 m grid (same cells, same UVs) and grows it
by a cell, at ON_LOG rather than black: plants still grow on and against a log, only fewer (operator: a log with
nothing on it is not the target either). forest_floor.py multiplies it into the groundcover and undergrowth.
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
ON_LOG = 0.3  # share of the tall cover kept on and beside a log


def log_meshes():
    rows = biome_variants.LOG_VARIANTS + biome_variants.MEADOW_LOG_VARIANTS
    return {path.rsplit("/", 1)[1] for path, _ in rows}


def footprints():
    """Each placed log's footprint corners in world cm."""
    names, out = log_meshes(), []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            mesh = component.static_mesh
            if not mesh or mesh.get_name() not in names:
                continue
            box = mesh.get_bounding_box()
            corners = [unreal.Vector(x, y, 0) for x, y in ((box.min.x, box.min.y), (box.max.x, box.min.y),
                                                            (box.max.x, box.max.y), (box.min.x, box.max.y))]
            for index in range(component.get_instance_count()):
                transform = component.get_instance_transform(index, True)
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
    pixels = dilate(pixels, width, height, 1)
    kept = round(255 * ON_LOG)
    pixels = bytearray(kept if v == 0 else v for v in pixels)
    import_texture(pixels, width, height, NAME)
    print(f"{NAME}: {len(logs)} logs, {sum(1 for v in pixels if v == kept) * CELL * CELL / 1e4:.0f} m2 thinned")


if __name__ == "__main__":
    main()
