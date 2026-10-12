"""Helpers for building materials from code; imported by the scripts in scripts/materials."""

import unreal

mel = unreal.MaterialEditingLibrary


def fresh_material(path):
    """Load or create the material at path and remove every expression."""
    folder, name = path.rsplit("/", 1)
    material = unreal.load_asset(path) or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.Material, unreal.MaterialFactoryNew()
    )
    # delete_all_material_expressions skips about half the nodes (it deletes while iterating), so delete one by one.
    for expression in list(mel.get_material_expressions(material)):
        mel.delete_material_expression(material, expression)
    if mel.get_num_material_expressions(material):
        raise SystemExit(f"{path}: could not clear the old graph")
    return material


def instance_of(path, parent):
    """Load or create the material instance at path and parent it; existing overrides are kept."""
    folder, name = path.rsplit("/", 1)
    instance = unreal.load_asset(path) or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    mel.set_material_instance_parent(instance, parent)
    return instance


def texture(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise SystemExit(f"missing texture {path}")
    return asset


def sampler_for(tex):
    """The sampler type Unreal requires for the texture's compression and colour space."""
    compression = tex.get_editor_property("compression_settings")
    srgb = tex.get_editor_property("srgb")
    TC, ST = unreal.TextureCompressionSettings, unreal.MaterialSamplerType
    if compression == TC.TC_NORMALMAP:
        return ST.SAMPLERTYPE_NORMAL
    if compression == TC.TC_MASKS:
        return ST.SAMPLERTYPE_MASKS
    if compression in (TC.TC_GRAYSCALE, TC.TC_ALPHA, TC.TC_DISPLACEMENTMAP):
        return ST.SAMPLERTYPE_GRAYSCALE if srgb else ST.SAMPLERTYPE_LINEAR_GRAYSCALE
    return ST.SAMPLERTYPE_COLOR if srgb else ST.SAMPLERTYPE_LINEAR_COLOR


class Graph:
    def __init__(self, material):
        self.material = material
        self.row = 0

    def node(self, cls, column, **props):
        self.row += 1
        expression = mel.create_material_expression(self.material, cls, -300 * column, 80 * self.row)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def wire(self, cls, column, inputs, **props):
        """Create a node and connect inputs: {input pin: expression or (expression, output pin)}."""
        expression = self.node(cls, column, **props)
        for pin, source in inputs.items():
            src, out = source if isinstance(source, tuple) else (source, "")
            # A wrong pin name fails silently and leaves the input at its default (0 roughness looked like glass).
            if not mel.connect_material_expressions(src, out, expression, pin):
                raise SystemExit(
                    f"could not connect {src.get_name()}:{out or '-'} -> {expression.get_name()}:{pin or '-'}"
                )
        return expression

    def mask(self, source, column, channels):
        flags = {c: c in channels for c in "rgba"}
        return self.wire(unreal.MaterialExpressionComponentMask, column, {"": source}, **flags)

    def sample(self, tex, uv, column):
        """Sample a texture (asset or path) at uv (None: the mesh's first UV channel)."""
        tex = texture(tex) if isinstance(tex, str) else tex
        return self.wire(
            unreal.MaterialExpressionTextureSample,
            column,
            {"UVs": uv} if uv is not None else {},
            texture=tex,
            sampler_type=sampler_for(tex),
            # Shared wrap samplers: two samples per texture would exceed the 16-sampler limit.
            sampler_source=unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS,
        )

    def noise(self, column, feature_cm):
        """World-space noise clamped to 0..1, features about feature_cm across."""
        raw = self.node(
            unreal.MaterialExpressionNoise, column, scale=1.0 / feature_cm, levels=3, output_min=0.0, output_max=1.0
        )
        return self.wire(unreal.MaterialExpressionSaturate, column - 1, {"": raw})
