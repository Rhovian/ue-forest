import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

import placement


class Properties:
    def __init__(self, **values):
        self.values = values

    def get_editor_property(self, name):
        return self.values.setdefault(name.removesuffix("_0_ABCD"), Properties())

    def set_editor_property(self, name, value):
        self.values[name] = value

    def export_text(self):
        return ",".join(f"{name}_0_ABCD=()" for name in self.values)

    def import_text(self, text):
        self.text = text

    def set_subgraph(self, graph):
        self.values["subgraph"] = graph


def recording_graph():
    graph, nodes, edges = MagicMock(), [], []

    def add_node(cls):
        settings, node = cls() if isinstance(cls, type) else Properties(), MagicMock()
        node.get_settings.return_value = settings
        nodes.append((cls, node, settings.values))
        return node, settings

    graph.add_node_of_type.side_effect = add_node
    return graph, nodes, edges


def row(mesh, layout=None, children=None, extents=(1, 1, 1)):
    return Properties(Weight=1, Generator=None, TransformGraph=layout, Mesh=mesh, ChildAssets=children,
                      AssetOptions=Properties(OrientUpward=0, ExtentsMultiplier=SimpleNamespace(**dict(zip("xyz", extents)))),
                      MeshOptions=Properties(Material=None, AllowCollision=False))


class ChildAttachmentTests(unittest.TestCase):
    def test_build_translates_child_lists_with_each_groups_parent_points(self):
        graph, nodes, edges = recording_graph()
        shared = Properties(BiomeAssets=[row("drift", "scatter"), row("moss", "shell"), row("moss_variant", "shell")])
        private = Properties(BiomeAssets=[row("pile", "pile_layout")])
        roots = [("Logs", "log_pose", shared), ("Stumps", "stump_pose", shared), ("Rocks", "rock_pose", private)]
        # Only adapt engine storage, struct construction and exclusion-asset loading; run the real Builder methods.
        with patch.multiple(placement.unreal, SkeletalMesh=type("SkeletalMesh", (), {}),
                            PCGSkinnedMeshSpawnerSettings=type("SkinnedSettings", (), {}),
                            PCGMeshSelectorWeightedEntry=Properties), \
                patch.object(placement, "edge", side_effect=lambda graph, *edge: edges.append(edge)), \
                patch.object(placement.Builder, "copy_exclusions", return_value=[]):
            generators = [{"name": name, "graph": f"{name}_sampler", "overlap": True,
                           "rows": placement.rows_of(Properties(BiomeAssets=[row(name, pose, children)]))}
                          for name, pose, children in roots]
            placement.Builder(graph).build(generators)

        def subgraph(asset):
            found = [node for cls, node, props in nodes if props.get("subgraph") == asset]
            self.assertEqual(len(found), 1, f"Expected one layout subgraph for {asset}")
            return found[0]

        for layout, parents, meshes in (("scatter", ["log_pose", "stump_pose"], ["drift"]),
                                        ("shell", ["log_pose", "stump_pose"], ["moss", "moss_variant"]),
                                        ("pile_layout", ["rock_pose"], ["pile"])):
            with self.subTest(layout=layout):
                child = subgraph(layout)
                self.assertCountEqual([(source, pin, into) for source, pin, target, into in edges if target is child],
                                      [(subgraph(parent), "Out", "In") for parent in parents])
                spawners = [props for cls, node, props in nodes if cls == placement.unreal.PCGStaticMeshSpawnerSettings
                            and (child, "Out", node, "In") in edges]
                self.assertEqual(len(spawners), 1, "Child layout must feed its mesh spawner")
                entries = spawners[0]["mesh_selector_parameters"].values["mesh_entries"]
                self.assertCountEqual([entry.values["descriptor"].values["static_mesh"] for entry in entries], meshes)


class FootprintTests(unittest.TestCase):
    def test_non_overlap_groups_rank_spawned_footprints_with_row_extents(self):
        graph, nodes, edges = recording_graph()
        skinned_settings = type("SkinnedSettings", (Properties,), {})
        with patch.multiple(placement.unreal, SkeletalMesh=MagicMock, PCGSkinnedMeshSpawnerSettings=skinned_settings,
                            PCGMeshSelectorWeightedEntry=Properties, Vector=lambda *xyz: xyz), \
                patch.object(placement, "edge", side_effect=lambda graph, *edge: edges.append(edge)), \
                patch.object(placement.Builder, "copy_exclusions", return_value=[]):
            generators = [{"name": name, "graph": name, "overlap": False,
                           "rows": placement.rows_of(Properties(BiomeAssets=[row(mesh, extents=extents)]))}
                          for name, mesh, extents in (("Veterans", "crown", (0.3, 0.3, 0.3)),
                                                      ("Trees", MagicMock(), (0.7, 0.7, 0.7)),
                                                      ("Herbs", "herb", (1, 1, 1)))]
            placement.Builder(graph).build(generators)
        spawners = [node for cls, node, props in nodes
                    if cls in (placement.unreal.PCGStaticMeshSpawnerSettings, skinned_settings)]
        self.assertEqual(len(spawners), 3)
        footprints = []
        for spawner, mode, low, high in (
                (spawners[0], placement.unreal.PCGBoundsModifierMode.SCALE, (0.3, 0.3, 0.3), (0.3, 0.3, 0.3)),
                (spawners[1], placement.unreal.PCGBoundsModifierMode.SET, (-1, -1, -1), (1, 1, 1))):
            found = [(node, props) for cls, node, props in nodes if cls == placement.unreal.PCGBoundsModifierSettings
                     and (spawner, "Out", node, "In") in edges]
            self.assertEqual(len(found), 1, "Each spawner feeds its footprint modifier")
            node, props = found[0]
            self.assertEqual((props["mode"], props["bounds_min"], props["bounds_max"]), (mode, low, high))
            footprints.append(node)
        for group, expected in (("Trees", footprints[:1]), ("Herbs", footprints)):
            with self.subTest(group=group):
                tag = next(node for cls, node, props in nodes if props.get("tags_to_add") == f"Root,GEN:{group}")
                source, pin = next((source, pin) for source, pin, target, into in edges if target is tag)
                self.assertEqual(pin, "Out")
                self.assertIn(source, [node for cls, node, props in nodes if cls == placement.unreal.PCGDifferenceSettings])
                self.assertCountEqual([(up, pin, into) for up, pin, target, into in edges
                                       if target is source and into == "Differences"],
                                      [(footprint, "Out", "Differences") for footprint in expected])


if __name__ == "__main__":
    unittest.main()
