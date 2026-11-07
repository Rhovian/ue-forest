---
name: forest-pcg
description: Lessons for this project's Biome Core PCG placement of everything on the island, forest, meadow and beach (scripts/pcg/*.py, regenerate_biome.py). Read before adding or changing a placement group, a density, a generator, child assets or a filter graph, and when diagnosing a slow or memory-heavy regenerate or plants that float, vanish or clump wrongly. Not for lighting, fog or materials. Append each new failure here when it is understood.
---

Each rule below cost real time when it was learned. A new rule says what broke, why, and the check that prevents it.

## Cost: estimate before you build

- A generator samples the **whole biome volume** before any filter, so its cost is density x the island's bounds
  (~470 ha), not density x the area it ends up on.
- The sampler emits at most one point per (2 x extent)^2 cell; `extent` is in cm (half the cell side), so the cap is
  10,000 / (2 x extent / 100)^2 per ha. 600,000/ha at extent 8 hit the cap (390,000/ha) everywhere: ~185 million points
  that put the operator's 96 GB machine under memory pressure. Density above the cap adds only cost.
- `deadwood_rocks.generator()` refuses estimates above `MAX_CANDIDATES` (60 million, `candidate_estimate`). Don't raise
  the budget to get around it: change the design.
- Dense cover on less than the whole island (meadow grass, fern and herb drifts, moss carpets): a sparse anchor generator plus a child patch per anchor
  (`children()` with a disc of points, `ground=True`), as in `meadow.py`. Cost then scales with the anchors.
  The budget covers anchors only: the instance total is accepted anchors x children per patch, so measure it after
  each change (fern drifts: 16 children each, ~194k ferns). `candidate_estimate` uses the capped density.
- `regenerate_biome.py` prints duration and peak editor memory. Above `MEMORY_LIMIT_GB` (60) it cancels all PCG generation
  through `unreal.ForestPCGLibrary.cancel_all_pcg_generation()` (C++: `PCGComponent::CancelGeneration` is not exposed
  to Python) and saves nothing. Pass a density only as `generator()`'s `density`; a `PointsPerSquareMeter` override is
  refused because the budget would not see it.
  A full regenerate takes about 1 minute and peaks at 35-40 GB. If a run takes much longer or the peak grows, stop and
  find out why before tuning further.
- Change density or extent, not both, and check the estimate before each change.

## Counts do not scale smoothly

- The template's spatial noise thins candidates heavily and nonlinearly: driftwood went from ~400 pieces at 1,800/ha to
  17,600 at 2,500/ha; meadow anchors from 4,510 to 105,000 between 600 and 3,000/ha. Probe two or three densities and
  measure the instance count; don't extrapolate.

## Entries and groups

- Every entry needs a **unique `AssetType`**, even within a group. Entries sharing a type with another group's entries
  silently draw from that group's points (shore trees halved the forest; meadow logs never spawned); making the
  understory drift types unique raised anemones from 107k to 433k. Set
  `put(value, AssetType=f"<Group>_" + mesh.get_name())`.
- Groups that must not carve the forest get a priority number above the Trees group (0): Core differences point sets
  by priority before any later filter.
- Groups without `GeneratorAllowOverlap` are pruned against every earlier group's bounds, and beech crowns are wide:
  island-wide saplings keep ~5% of their points, and saplings in canopy gaps kept none until overlap was allowed.
- A non-overlapping group at a priority below the Trees group (0) prunes the beech around its points, but its own
  skinned instances did not spawn (a veteran-beech trial left canopy holes with no tree in them). Groups among the
  trees keep overlap on and a priority above 0, as ShoreTrees does.
- Distance's `SphereBounds` shape uses the bounds' half-diagonal as the radius and is signed (inside is negative), so
  a [0, x] density filter keeps only a ring outside it. Distance is 3D: for "within r of these points" on terrain use
  `CENTER` with `maximum_distance = r`, a density filter below 0.99, one Distance per radius, and a vertical column
  of targets per point (meadow.py, `canopy_filter()`).
- Equal-weight variants with the same density share every sampler point: nudge each density (deadwood_rocks.py).

## Children

- Water exclusions are two-tier (`water_exclusions.py`): `ForestExclusion_*` (tag `PCG_BiomeExclusion`, the narrow
  margin; Biome Core selects exclusions by that tag) keeps everything out of the water, and `ForestKeepout_*` (tag
  `Forest_WaterKeepout`, 3 m) keeps every group but the ground plants (`exact_exclusions.PLANT_GRAPHS`) back from it.
  A new ground-plant filter graph must be added to `PLANT_GRAPHS` to reach the banks.
- After rebuilding any group, run `exact_exclusions.py` before `regenerate_biome.py --save`: child graphs are rebuilt
  without the path, water and shore exclusions, so children can land across a path (#73 review).
- One child list applies every layout to every anchor. For several patch outlines, give each entry its own list and
  split the variant weight across them (`saplings_understory.py` drifts).

- Core walks a ChildAssets list entry by entry and drops points whose bounds overlap earlier entries' points: scale
  child bounds to 5% (`children()` does this).
- Children placed around a base must be projected onto the ground (`build_points_graph(..., ground=True)`); the parent's
  local z = 0 is only the ground at its pivot.
- Created child points need distinct seeds (`build_points_graph` sets `seed = 1 + index`) before Transform Points, or
  every sibling shares yaw, scale and mesh pick.

## Verification

- Generated points are readable with `unreal.ForestPCGLibrary.get_generated_point_locations(component, "GEN:<group>")`;
  skinned instances (trees, saplings, anemones) are GPU-only and their transforms are not readable from Python.
- Edits through the editor's MCP toolsets (Niagara stack inputs, for example) change the loaded asset only: save it
  (`unreal.EditorAssetLibrary.save_loaded_asset`) and check `git status` shows it before committing.
- Capture with `scripts/review/capture`: a single raw `CaptureViewport` returns the previous view's frame.

- `regenerate_biome.py`'s per-group instance count misattributes components when groups share a mesh; count by mesh,
  and to split two groups sharing a mesh, disable one and count again.
- After an editor restart, World Partition cells are unloaded; `scripts/editor.sh open` loads them. Traces and counts
  on an unloaded level are wrong.
- Sparse obstacles survive far below their candidate density: meadow logs kept ~10% (200/ha gave 38 logs on 2 ha), so
  15/ha gave ~3 and looked like "no logs at all". Measure the count before concluding a group is broken.
