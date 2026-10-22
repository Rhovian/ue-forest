"""Source-triangle nurse-log anchor and its parent-space PCG transform graph."""

import unreal


def log_surface(log):
    # Use Geometry Script's source-mesh copy/BVH, not a custom triangle parser/ray caster:
    # UE 5.8 GeometryScript/MeshAssetFunctions.h and MeshSpatialFunctions.h.
    mesh, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
        log, unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0))
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError("Nurse anchor: could not read log source LOD0")
    mesh, bvh = unreal.GeometryScript_MeshSpatial.build_bvh_for_mesh(mesh)
    return mesh, bvh


def source_anchor(log, fungi):
    mesh, bvh = log_surface(log)
    bounds = log.get_bounds()
    _, hit, outcome = unreal.GeometryScript_MeshSpatial.find_nearest_ray_intersection_with_mesh(
        mesh, bvh, unreal.Vector(0, 0, bounds.origin.z + bounds.box_extent.z + 100),
        unreal.Vector(0, 0, -1), unreal.GeometryScriptSpatialQueryOptions())
    if outcome != unreal.GeometryScriptSearchOutcomePins.FOUND or not hit.hit:
        raise RuntimeError("Nurse anchor: no source surface at local XY (0, 0)")
    point = hit.hit_position.copy()
    # Local origin lies on the narrow trunk, unlike the AABB center displaced by its root plate.
    base = fungi.get_bounds()
    point.z -= base.origin.z - base.box_extent.z + 0.25  # bury the stem base 2.5 mm, not the cap
    print(f"Nurse anchor: source surface Z={hit.hit_position.z:.3f} cm; local stem root {point}")
    return point


def selector(kind, value):
    result = kind()
    if not result.import_text(f"PCGBegin({value})PCGEnd"):
        raise RuntimeError(f"Invalid PCG anchor selector: {value}")
    return result


def build_anchor_graph(graph, anchor, edge):
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    add, settings = graph.add_node_of_type(unreal.PCGAddAttributeSettings)
    settings.set_editor_property("output_target", selector(unreal.PCGAttributePropertyOutputSelector, "NurseAnchor"))
    value = settings.get_editor_property("attribute_types")
    value.set_editor_property("type", unreal.PCGMetadataTypes.VECTOR)
    value.set_editor_property("vector_value", anchor)
    settings.set_editor_property("attribute_types", value)
    edge(graph, inp, "In", add, "In")
    place, settings = graph.add_node_of_type(unreal.PCGMetadataVectorSettings)
    settings.set_editor_property("operation", unreal.PCGMetadataVectorOperation.TRANSFORM_LOCATION)
    for name, target in (("input_source1", "NurseAnchor"), ("input_source2", "$Transform")):
        settings.set_editor_property(name, selector(unreal.PCGAttributePropertyInputSelector, target))
    settings.set_editor_property("output_target", selector(unreal.PCGAttributePropertyOutputSelector, "$Position"))
    # Native TransformLocation uses TransformPosition including scale (PCGMetadataVectorOpElement.cpp),
    # whereas TransformPoints' local offset rotates but does not scale its offset (PCGTransformPoints.cpp).
    edge(graph, add, "Out", place, "In")
    edge(graph, add, "Out", place, "Transform")
    upright, settings = graph.add_node_of_type(unreal.PCGTransformPointsSettings)
    settings.set_editor_property("absolute_rotation", True)
    edge(graph, place, "Out", upright, "In")
    edge(graph, upright, "Out", out, "Out")
