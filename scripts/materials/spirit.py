"""Build M_Spirit, the material of the spirit fireflies (#137).

    scripts/editor-py scripts/materials/spirit.py

Additive and unlit on a small camera-facing sprite: a hot core and a soft halo that blink like a firefly, a short
flash then seconds dark, each on its own phase and rate (Particle Random), so the animation is in the shader rather
than the emitter. The particle colour sets the hue (NS_ForestEnchant's Spirits emitter: lapis lazuli); the shader turns
some toward violet, and INTENSITY sets the brightness.
"""

import unreal
from matgraph import Graph, fresh_material, mel

PATH = "/Game/ForestBiome/FX/M_Spirit"
INTENSITY = 14.0
X, MP = unreal, unreal.MaterialProperty

CODE = """
float2 p = UV - 0.5;
float r2 = dot(p, p);
float rate = 0.5 + Seed;  // flashes per ~6 s
float wave = sin(Time * rate + Seed * 50.0);
float blink = 0.08 + pow(saturate(wave), 12.0);  // a faint ember between flashes
float core = exp(-r2 / 0.004);
float halo = exp(-r2 / 0.03);
float3 tint = lerp(float3(1.0, 1.0, 1.0), float3(2.2, 0.55, 0.9), Seed * Seed);  // some toward violet
return tint * (core * 3.0 + halo * 0.6) * blink;
"""

material = fresh_material(PATH)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
material.set_editor_property("used_with_niagara_sprites", True)
g = Graph(material)
custom = g.node(X.MaterialExpressionCustom, 3, code=CODE, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                description="SpiritGlow")
inputs = []
for name in ("UV", "Time", "Seed"):
    pin = unreal.CustomInput()
    pin.set_editor_property("input_name", name)
    inputs.append(pin)
custom.set_editor_property("inputs", inputs)
for pin, source in (("UV", g.node(X.MaterialExpressionTextureCoordinate, 5)), ("Time", g.node(X.MaterialExpressionTime, 5)),
                    ("Seed", g.node(X.MaterialExpressionParticleRandom, 5))):
    if not mel.connect_material_expressions(source, "", custom, pin):
        raise SystemExit(f"could not connect {pin}")
colour = g.node(X.MaterialExpressionParticleColor, 3)
strength = g.node(X.MaterialExpressionScalarParameter, 3, parameter_name="Intensity", default_value=INTENSITY)
glow = g.wire(X.MaterialExpressionMultiply, 2, {"A": custom, "B": strength})
# Particle alpha fades each spirit in and out over its life (the emitter's colour curve).
lit = g.wire(X.MaterialExpressionMultiply, 1, {"A": g.wire(X.MaterialExpressionMultiply, 2, {"A": (colour, ""), "B": glow}),
                                              "B": (colour, "A")})
if not mel.connect_material_property(lit, "", MP.MP_EMISSIVE_COLOR):
    raise SystemExit("could not connect emissive")
mel.recompile_material(material)
if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
    raise SystemExit(f"could not save {PATH}")
print(f"{PATH}: {mel.get_num_material_expressions(material)} expressions")
