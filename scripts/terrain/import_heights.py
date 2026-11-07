"""Import the softened shore heights into L_vilm's landscape (#38). Lead only; runs in the editor via scripts/editor-py.

    scripts/editor-py scripts/terrain/import_heights.py --check    # render target holds the file's values; no import
    scripts/editor-py scripts/terrain/import_heights.py            # import into edit layer 0
    scripts/editor-py scripts/terrain/import_heights.py --verify   # after import: landscape traces match the file

Draws Forest/Saved/Terrain/vilm_1513_shore_rg.png (scripts/terrain/soft_shore.py: R high byte, G low byte) into a
transient RGBA8 render target and imports it with ALandscapeProxy::LandscapeImportHeightmapFromRenderTarget
(LandscapeEdit.cpp: height = R << 8 | G). --check and --verify compare against vilm_1513_shore_samples.json, which
soft_shore.py decodes independently of this pipeline, and raise on any mismatch. Run --verify in a separate call:
landscape collision updates a few editor ticks after the import.
"""

import argparse
import json
from pathlib import Path

import unreal

TOLERANCE_CM = 2  # traced landscape height vs the file; one 16-bit step is ~0.08 cm

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name() != "/Game/L_vilm.L_vilm":
    raise RuntimeError("Open L_vilm in the editor (not PIE) before running")
terrain = Path(unreal.Paths.project_saved_dir()) / "Terrain"
rendering = unreal.RenderingLibrary


def render_target():
    return rendering.create_render_target2d(world, 1513, 1513, unreal.TextureRenderTargetFormat.RTF_RGBA8,
                                            unreal.LinearColor(0, 0, 0, 1), False)


def value(target, x, y):
    color = rendering.read_render_target_pixel(world, target, x, y)
    return color.r << 8 | color.g


def png_rg(path):
    texture = rendering.import_file_as_texture2d(world, str(path))
    if texture is None:
        raise RuntimeError(f"could not read {path}")
    texture.set_editor_property("srgb", False)
    texture.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    return texture


def draw(texture):
    target = render_target()
    canvas, _size, context = rendering.begin_draw_canvas_to_render_target(world, target)
    canvas.draw_texture(texture, unreal.Vector2D(0, 0), unreal.Vector2D(1513, 1513), unreal.Vector2D(0, 0),
                        unreal.Vector2D(1, 1), unreal.LinearColor(1, 1, 1, 1), unreal.BlendMode.BLEND_OPAQUE)
    rendering.end_draw_canvas_to_render_target(world, context)
    return target


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


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    samples = json.loads((terrain / "vilm_1513_shore_samples.json").read_text())
    if args.verify:
        bad = [(p, ground(p["x_cm"], p["y_cm"])) for p in samples]
        bad = [(p, z) for p, z in bad if z is None or abs(z - p["z_cm"]) > TOLERANCE_CM]
        if bad:
            raise RuntimeError(f"landscape differs from the file at {len(bad)} of {len(samples)} points: {bad[:3]}")
        print(f"landscape matches vilm_1513_shore at all {len(samples)} sample points (within {TOLERANCE_CM} cm)")
        return
    landscapes = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                  if isinstance(a, unreal.Landscape)]
    if len(landscapes) != 1:
        raise RuntimeError(f"expected one Landscape actor, found {len(landscapes)}")
    shore = draw(png_rg(terrain / "vilm_1513_shore_rg.png"))
    bad = [(p["col"], p["row"], p["encoded"], value(shore, p["col"], p["row"])) for p in samples]
    bad = [b for b in bad if b[2] != b[3]]
    if bad:
        raise RuntimeError(f"render target differs from the file at {len(bad)} of {len(samples)} pixels: {bad[:3]}")
    if args.check:
        print(f"render target matches the file at all {len(samples)} sample pixels; nothing imported")
        return
    if not landscapes[0].landscape_import_heightmap_from_render_target(shore, True, 0):
        raise RuntimeError("landscape import failed")
    print("imported vilm_1513_shore_rg.png into edit layer 0; run --verify, then regenerate the biome and save")


main()
