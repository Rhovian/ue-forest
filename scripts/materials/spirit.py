"""Build M_Spirit, the material of the spirit fireflies (#137).

    scripts/editor-py scripts/materials/spirit.py

Additive and unlit on a small camera-facing sprite. Each firefly (Particle Random as its seed) gets its own life in
the shader rather than the emitter:
- a flash pattern: a period of 3-8 s, one flash or a double flash, its own brightness, and a faint ember between;
- a flight path by World Position Offset: slow loops of up to 60 cm on its own frequencies, a quick small jitter, a
  bob, and a short climb while it flashes (the J-shaped flash flight of real fireflies). The emitter only adds a slow
  drift, so they no longer all move the same way.
The particle colour sets the hue (NS_ForestEnchant's Spirits emitter: lapis lazuli); the shader turns some toward
violet, and INTENSITY sets the brightness.
"""

import unreal
from matgraph import Graph, fresh_material, mel

PATH = "/Game/ForestBiome/FX/M_Spirit"
INTENSITY = 14.0
X, MP = unreal, unreal.MaterialProperty

# Flash in 0..1 at this time; shared by the glow and the flight (which climbs while it flashes).
FLASH = """
float period = 3.0 + 5.0 * frac(Seed * 7.31);
float phase = frac(Time / period + Seed * 13.7);
float flash = exp(-pow((phase - 0.10) / 0.035, 2.0));
flash += (frac(Seed * 3.17) > 0.6) * exp(-pow((phase - 0.22) / 0.03, 2.0));  // a double flash on some
"""
GLOW = FLASH + """
float2 p = UV - 0.5;
float r2 = dot(p, p);
float ember = 0.03 + 0.09 * frac(Seed * 5.9);
float bright = 0.5 + frac(Seed * 3.71);
float core = exp(-r2 / 0.004);
float halo = exp(-r2 / 0.03);
float3 tint = lerp(float3(1.0, 1.0, 1.0), float3(2.2, 0.55, 0.9), Seed * Seed);  // some toward violet
return tint * (core * 3.0 + halo * 0.6) * (ember + bright * flash);
"""
FLIGHT = FLASH + """
float3 w = 0.25 + 0.5 * frac(Seed * float3(1.37, 2.71, 4.13));  // rad/s
float3 o = Seed * float3(17.0, 29.0, 43.0);
float reach = 25.0 + 35.0 * frac(Seed * 9.13);
float3 loops = reach * float3(sin(Time * w.x + o.x), cos(Time * w.y + o.y), 0.4 * sin(Time * w.z + o.z));
float3 jitter = 6.0 * float3(sin(Time * 3.1 + o.y), sin(Time * 2.3 + o.z), sin(Time * 2.7 + o.x));
return loops + jitter + float3(0.0, 0.0, 18.0 * flash);
"""

material = fresh_material(PATH)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
material.set_editor_property("used_with_niagara_sprites", True)
g = Graph(material)
sources = {"UV": g.node(X.MaterialExpressionTextureCoordinate, 5), "Time": g.node(X.MaterialExpressionTime, 5),
           "Seed": g.node(X.MaterialExpressionParticleRandom, 5)}


def custom(code, pins, description):
    node = g.node(X.MaterialExpressionCustom, 3, code=code, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                  description=description)
    inputs = []
    for name in pins:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", name)
        inputs.append(pin)
    node.set_editor_property("inputs", inputs)
    for name in pins:
        if not mel.connect_material_expressions(sources[name], "", node, name):
            raise SystemExit(f"could not connect {name}")
    return node


glow = custom(GLOW, ("UV", "Time", "Seed"), "SpiritGlow")
flight = custom(FLIGHT, ("Time", "Seed"), "SpiritFlight")
colour = g.node(X.MaterialExpressionParticleColor, 3)
strength = g.node(X.MaterialExpressionScalarParameter, 3, parameter_name="Intensity", default_value=INTENSITY)
scaled = g.wire(X.MaterialExpressionMultiply, 2, {"A": glow, "B": strength})
# Particle alpha fades each spirit in and out over its life (the emitter's colour curve).
lit = g.wire(X.MaterialExpressionMultiply, 1, {"A": g.wire(X.MaterialExpressionMultiply, 2, {"A": (colour, ""), "B": scaled}),
                                              "B": (colour, "A")})
for expression, prop in ((lit, MP.MP_EMISSIVE_COLOR), (flight, MP.MP_WORLD_POSITION_OFFSET)):
    if not mel.connect_material_property(expression, "", prop):
        raise SystemExit(f"could not connect {prop}")
mel.recompile_material(material)
if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
    raise SystemExit(f"could not save {PATH}")
print(f"{PATH}: {mel.get_num_material_expressions(material)} expressions")
