"""asset-budget.py recognises foliage by its materials, wherever the mesh lives (python3 scripts/test_asset_budget.py).

The audit runs inside the editor; here `unreal` is a stand-in with just the classes and enums the rule reads.
"""

import importlib.util
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class Asset:
    def __init__(self, height=100, **properties):
        self.properties, self.height = properties, height

    def get_bounds(self):
        return types.SimpleNamespace(box_extent=types.SimpleNamespace(z=self.height / 2))

    def get_editor_property(self, name):
        return self.properties[name]


def load():
    unreal = types.ModuleType("unreal")
    for name in ("StaticMesh", "SkeletalMesh", "Material", "MaterialInstance", "Texture2D"):
        setattr(unreal, name, type(name, (Asset,), {}))
    unreal.BlendMode = types.SimpleNamespace(BLEND_OPAQUE="opaque", BLEND_MASKED="masked")
    unreal.NaniteShapePreservation = types.SimpleNamespace(VOXELIZE="voxelize", PRESERVE_AREA="preserve_area")
    sys.modules["unreal"] = unreal
    sys.path.insert(0, HERE)  # the audit imports pcg.biome_variants, which is plain data
    spec = importlib.util.spec_from_file_location("asset_budget", os.path.join(HERE, "asset-budget.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, unreal


BUDGET, UNREAL = load()


def material(blend, two_sided):
    return UNREAL.Material(blend_mode=blend, two_sided=two_sided)


def mesh(*materials, shape="preserve_area", height=100):
    return UNREAL.StaticMesh(
        height=height, static_materials=[Asset(material_interface=m) for m in materials],
        nanite_settings=Asset(enabled=True, shape_preservation=shape))


def rules(asset, package):
    data = types.SimpleNamespace(asset_name="SM_Test", package_name=package)
    return [rule for rule, _ in BUDGET.violations(asset, data)]


LEAF = ("masked", True)
VOXELIZE = "foliage Nanite shape preservation must be Voxelize"
HORNBEAM = "/Game/Megascans/3D_Plants/EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Forest_01"  # placed
SEEDLING = "/Game/Megascans/3D_Plants/EuropeanHornbeam/Geometry/SimpleWind/SM_EuropeanHornbeam_Seedling_01"  # placed


class FoliageRule(unittest.TestCase):
    def test_leaf_cards_outside_the_plants_folder_are_foliage(self):
        tree = mesh(material(*LEAF), material(*LEAF))
        self.assertEqual(rules(tree, "/Game/EuropeanBeech/Geometry/SimpleWind/SM_EuropeanBeech_Field_01"), [VOXELIZE])

    def test_the_same_tree_on_voxelize_passes(self):
        tree = mesh(material(*LEAF), shape="voxelize")
        self.assertEqual(rules(tree, HORNBEAM), [])

    def test_a_placed_hornbeam_on_preserve_area_is_flagged(self):
        self.assertEqual(rules(mesh(material(*LEAF)), HORNBEAM), [VOXELIZE])

    def test_a_leafy_mesh_no_variant_list_names_is_not_asked(self):
        self.assertEqual(rules(mesh(material(*LEAF)), "/Game/Megascans/3D_Plants/NotPlaced/SM_NotPlaced_01"), [])

    def test_a_tree_with_a_bark_slot_is_foliage(self):
        tree = mesh(material("opaque", False), material(*LEAF), height=1500)
        self.assertEqual(rules(tree, HORNBEAM), [VOXELIZE])

    def test_a_seedling_with_a_bark_slot_is_foliage(self):
        seedling = mesh(material("opaque", False), material(*LEAF), height=30)
        self.assertEqual(rules(seedling, SEEDLING), [VOXELIZE])

    def test_an_unplaced_solid_mesh_with_a_leaf_slot_is_not_asked(self):
        shell = mesh(material("opaque", False), material(*LEAF))
        self.assertEqual(rules(shell, "/Game/ForestBiome/MossShells/SM_Log_MossShell"), [])

    def test_masked_but_one_sided_is_not_foliage(self):
        self.assertEqual(rules(mesh(material("masked", False)), HORNBEAM), [])

    def test_two_sided_but_opaque_is_not_foliage(self):
        self.assertEqual(rules(mesh(material("opaque", True)), HORNBEAM), [])

    def test_an_instance_overrides_its_parent(self):
        parent = material("opaque", False)
        overrides = Asset(override_blend_mode=True, blend_mode="masked", override_two_sided=True, two_sided=True)
        instance = UNREAL.MaterialInstance(base_property_overrides=overrides, parent=parent)
        self.assertEqual(rules(mesh(instance), HORNBEAM), [VOXELIZE])

    def test_a_mesh_with_no_materials_is_not_foliage(self):
        self.assertEqual(rules(mesh(), HORNBEAM), [])


if __name__ == "__main__":
    unittest.main()
