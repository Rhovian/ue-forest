"""Build M_Wisp, the soft particle material of the enchanted wisps and motes (#40).

    scripts/editor-py scripts/materials/wisp.py

Translucent, unlit: the particle colour, faded by a round soft-edged gradient over the sprite and by depth where it
meets the ground, so a wisp reads as mist, not a card or an orb.
"""

import unreal
from matgraph import Graph, fresh_material, mel

PATH = "/Game/ForestBiome/FX/M_Wisp"
OPACITY = 0.5
X, MP = unreal, unreal.MaterialProperty

material = fresh_material(PATH)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
material.set_editor_property("used_with_niagara_sprites", True)
g = Graph(material)
uv = g.node(X.MaterialExpressionTextureCoordinate, 6)
centre = g.node(X.MaterialExpressionConstant2Vector, 6, r=0.5, g=0.5)
radius = g.wire(X.MaterialExpressionDistance, 5, {"A": uv, "B": centre})
edge = g.wire(X.MaterialExpressionMultiply, 4, {"A": radius}, const_b=2.0)
inside = g.wire(X.MaterialExpressionOneMinus, 4, {"": edge})
clamped = g.wire(X.MaterialExpressionSaturate, 3, {"": inside})
soft = g.wire(X.MaterialExpressionPower, 3, {"Base": clamped}, const_exponent=2.0)
colour = g.node(X.MaterialExpressionParticleColor, 3)
# Opacity scales every wisp and mote (#71 item 8): at full particle alpha the blue mist washed whole views
# (interior, clearing reviews) instead of reading as ribbons; a scalar parameter, so it tunes without a rebuild.
strength = g.node(X.MaterialExpressionScalarParameter, 3, parameter_name="Opacity", default_value=OPACITY)
alpha = g.wire(X.MaterialExpressionMultiply, 2, {"A": g.wire(X.MaterialExpressionMultiply, 2, {"A": soft, "B": (colour, "A")}),
                                                 "B": strength})
faded = g.wire(X.MaterialExpressionDepthFade, 1, {"Opacity": alpha}, fade_distance_default=80.0)
for expression, out, prop in ((colour, "", MP.MP_EMISSIVE_COLOR), (faded, "", MP.MP_OPACITY)):
    if not mel.connect_material_property(expression, out, prop):
        raise SystemExit(f"could not connect {prop}")
mel.recompile_material(material)
if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
    raise SystemExit(f"could not save {PATH}")
print(f"{PATH}: {mel.get_num_material_expressions(material)} expressions")
