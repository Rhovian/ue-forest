"""Child layouts for logs and rocks: points on a parent mesh's surface and the PCG graph that places them."""

import math

import unreal


def mesh_surface(source):
    # Use Geometry Script's source-mesh copy/BVH, not a custom triangle parser/ray caster:
    # UE 5.8 GeometryScript/MeshAssetFunctions.h and MeshSpatialFunctions.h.
    # Source LOD0 when readable; some scans' source data (wd1mbcvbw after an editor restart) is not, and then the
    # render data's coarser mesh still gives the top surface.
    for lod in (unreal.GeometryScriptLODType.SOURCE_MODEL, unreal.GeometryScriptLODType.RENDER_DATA):
        mesh, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
            source, unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(),
            unreal.GeometryScriptMeshReadLOD(lod_type=lod, lod_index=0))
        if outcome == unreal.GeometryScriptOutcomePins.SUCCESS:
            break
    else:
        raise RuntimeError(f"Child layout: could not read {source.get_name()}'s source or render LOD0")
    mesh, bvh = unreal.GeometryScript_MeshSpatial.build_bvh_for_mesh(mesh)
    return mesh, bvh


# Child layouts for logs and rocks (#32 nurse_log_01, rock_assembly_01). Points are in the parent's local space,
# where the ground is z=0: Core places each obstacle's pivot on the sampled ground point.
GRID = 40


def surface_hits(mesh):
    """Downward hits on a GRID x GRID raster over the bounds: (x, y, z, up) with up = face normal Z."""
    dynamic, bvh = mesh_surface(mesh)
    bounds = mesh.get_bounds()
    o, e = bounds.origin, bounds.box_extent
    hits = []
    for i in range(GRID):
        for j in range(GRID):
            x, y = o.x + ((i + 0.5) / GRID * 2 - 1) * e.x, o.y + ((j + 0.5) / GRID * 2 - 1) * e.y
            _, found, outcome = unreal.GeometryScript_MeshSpatial.find_nearest_ray_intersection_with_mesh(
                dynamic, bvh, unreal.Vector(x, y, o.z + e.z + 100), unreal.Vector(0, 0, -1),
                unreal.GeometryScriptSpatialQueryOptions())
            if outcome == unreal.GeometryScriptSearchOutcomePins.FOUND and found.hit:
                normal, valid = unreal.GeometryScript_MeshQueries.get_triangle_face_normal(dynamic, found.hit_triangle_id)
                p = found.hit_position
                hits.append((p.x, p.y, p.z, abs(normal.z) if valid else 0))
    if len(hits) < 3:
        raise RuntimeError(f"Child layout: too few surface hits on {mesh.get_name()}")
    return hits


def along_top(hits, count, min_up=0.6):
    """`count` stations spread along the long axis (15-85%), each the highest upward-facing hit there."""
    axis = 0 if max(h[0] for h in hits) - min(h[0] for h in hits) >= max(h[1] for h in hits) - min(h[1] for h in hits) else 1
    low, high = min(h[axis] for h in hits), max(h[axis] for h in hits)
    points = []
    for k in range(count):
        at = low + (high - low) * (0.15 + 0.7 * (k + 0.5) / count)
        near = [h for h in hits if h[3] >= min_up and abs(h[axis] - at) <= (high - low) / GRID * 1.5]
        if near:
            points.append(max(near, key=lambda h: h[2])[:3])
    return points


def along_sides(hits, spacing, margin, depth=2):
    """Points every `spacing` cm along both sides of the trunk, `margin` cm out from its edge at each station, plus
    one beyond each end, at the ground. Follows the trunk, unlike a hull stretched by branches or a root plate."""
    axis = 0 if max(h[0] for h in hits) - min(h[0] for h in hits) >= max(h[1] for h in hits) - min(h[1] for h in hits) else 1
    side = 1 - axis
    low, high = min(h[axis] for h in hits), max(h[axis] for h in hits)
    points = []

    def at(u, v):
        p = [0.0, 0.0, -depth]
        p[axis], p[side] = u, v
        return tuple(p)

    steps = max(1, round((high - low) / spacing))
    for k in range(steps + 1):
        u = low + (high - low) * k / steps
        near = [h[side] for h in hits if abs(h[axis] - u) <= max(spacing / 2, (high - low) / GRID)]
        if not near:
            continue
        points += [at(u, min(near) - margin), at(u, max(near) + margin)]
        if k in (0, steps):
            points.append(at(u + (margin if k else -margin) * 2, (min(near) + max(near)) / 2))
    return points


def base_ring(hits, spacing, margin, depth=2):
    """Points every `spacing` cm along the footprint's convex hull, pushed `margin` cm outward, at the ground."""
    # Andrew's monotone chain.
    pts = sorted({(h[0], h[1]) for h in hits})
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]  # counter-clockwise
    points, carry = [], 0.0
    for a, b in zip(hull, hull[1:] + hull[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        nx, ny = dy / length, -dx / length  # outward for a counter-clockwise hull
        t = carry
        while t < length:
            points.append((a[0] + dx * t / length + nx * margin, a[1] + dy * t / length + ny * margin, -depth))
            t += spacing
        carry = t - length
    return points


def build_points_graph(graph, points, edge, scale=(1, 1)):
    """Copy local `points` onto every parent point, then upright each with a random yaw and scale."""
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    if not points:
        raise RuntimeError(f"{graph.get_name()}: no child points")
    create, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
    created = []
    for x, y, z in points:
        point = unreal.PCGPoint()
        point.set_editor_property("transform", unreal.Transform(location=unreal.Vector(x, y, z)))
        created.append(point)
    settings.set_editor_property("points_to_create", created)
    settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
    settings.set_editor_property("cull_points_outside_volume", False)
    # Native CopyPoints composes each source with each target transform, position included (PCGCopyPoints.cpp);
    # keep the parent's attributes, which Core reads downstream.
    copy, settings = graph.add_node_of_type(unreal.PCGCopyPointsSettings)
    settings.set_editor_property("attribute_inheritance", unreal.PCGCopyPointsMetadataInheritanceMode.TARGET_FIRST)
    edge(graph, create, "Out", copy, "Source")
    edge(graph, inp, "In", copy, "Target")
    upright, settings = graph.add_node_of_type(unreal.PCGTransformPointsSettings)
    settings.set_editor_property("absolute_rotation", True)
    # Created points all carry seed 0, so every child of one parent would share a seed, and with it the weighted mesh
    # pick, yaw and scale; reseed each from its own location.
    settings.set_editor_property("recompute_seed", True)
    settings.set_editor_property("rotation_max", unreal.Rotator(pitch=0, yaw=360, roll=0))
    settings.set_editor_property("uniform_scale", True)
    settings.set_editor_property("scale_min", unreal.Vector(scale[0], scale[0], scale[0]))
    settings.set_editor_property("scale_max", unreal.Vector(scale[1], scale[1], scale[1]))
    edge(graph, copy, "Out", upright, "In")
    edge(graph, upright, "Out", out, "Out")
    return graph
