"""Import the softened shore heights into L_vilm's landscape (#38). Lead only; runs in the editor via scripts/editor-py.

    scripts/editor-py scripts/terrain/import_heights.py [--check]

Draws Forest/Saved/Terrain/vilm_1513_shore_rg.png (from scripts/terrain/soft_shore.py: R high byte, G low byte) into a
transient RGBA8 render target and imports it with ALandscapeProxy::LandscapeImportHeightmapFromRenderTarget
(LandscapeEdit.cpp: height = R << 8 | G) into edit layer 0. --check imports nothing: it verifies that the render
target holds the file's values exactly, and that the landscape's own export matches heightmap.py's vilm_1513.png
(same pixel layout and encoding) at sample points.
"""

import argparse
from pathlib import Path

import unreal

SAMPLES = [(0, 0), (756, 756), (1000, 500), (500, 1000), (1512, 1512), (300, 1200), (1200, 300)]

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    landscapes = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                  if isinstance(a, unreal.Landscape)]
    if len(landscapes) != 1:
        raise RuntimeError(f"expected one Landscape actor, found {len(landscapes)}")
    landscape = landscapes[0]
    shore = draw(png_rg(terrain / "vilm_1513_shore_rg.png"))
    if args.check:
        # The file's values reach the render target exactly (no sRGB conversion or filtering).
        expected = png_rg(terrain / "vilm_1513_shore_rg.png")
        reference = draw(expected)
        exported = render_target()
        if not landscape.landscape_export_heightmap_to_render_target(exported, True, True):
            raise RuntimeError("landscape export failed")
        print("x y | shore RT | landscape now")
        for x, y in SAMPLES:
            print(x, y, "|", value(shore, x, y), value(reference, x, y), "|", value(exported, x, y))
        return
    if not landscape.landscape_import_heightmap_from_render_target(shore, True, 0):
        raise RuntimeError("landscape import failed")
    print("imported vilm_1513_shore_rg.png into edit layer 0; regenerate the biome and save the level")


main()
