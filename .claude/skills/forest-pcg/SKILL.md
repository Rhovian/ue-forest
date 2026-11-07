---
name: forest-pcg
description: Lessons for building and tuning this project's Biome Core PCG placement (scripts/pcg/*.py, regenerate_biome.py). Read before adding or changing a placement group, a density, a generator, child assets or a filter graph. Append each new failure here when it is understood.
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
- `regenerate_biome.py` prints duration and peak editor memory. Above `MEMORY_LIMIT_GB` (60) it cancels all PCG generation
  through `unreal.ForestPCGLibrary.cancel_all_pcg_generation()` (C++: `PCGComponent::CancelGeneration` is not exposed
  to Python) and saves nothing. Pass a density only as `generator()`'s `density`; a `PointsPerSquareMeter` override is
  refused because the budget would not see it.
  A full regenerate takes about 1 minute and peaks at 35-39 GB. If a run takes much longer or the peak grows, stop and
  find out why before tuning further.
- Change density or extent, not both, and check the estimate before each change.

## Counts do not scale smoothly

- The template's spatial noise thins candidates heavily and nonlinearly: driftwood went from ~400 pieces at 1,800/ha to
  17,600 at 2,500/ha; meadow anchors from 4,510 to 105,000 between 600 and 3,000/ha. Probe two or three densities and
  measure the instance count; don't extrapolate.

## Entries and groups

- Every entry needs a **unique `AssetType`**. Entries sharing a type with another group's entries silently draw from
  that group's points (shore trees halved the forest; meadow logs never spawned). Set
  `put(value, AssetType=f"<Group>_" + mesh.get_name())`.
- Groups that must not carve the forest get a priority number above the Trees group (0): Core differences point sets
  by priority before any later filter.
- Equal-weight variants with the same density share every sampler point: nudge each density (deadwood_rocks.py).

## Children

- Core walks a ChildAssets list entry by entry and drops points whose bounds overlap earlier entries' points: scale
  child bounds to 5% (`children()` does this).
- Children placed around a base must be projected onto the ground (`build_points_graph(..., ground=True)`); the parent's
  local z = 0 is only the ground at its pivot.
- Created child points need distinct seeds (`build_points_graph` sets `seed = 1 + index`) before Transform Points, or
  every sibling shares yaw, scale and mesh pick.

## Verification

- `regenerate_biome.py`'s per-group instance count misattributes components when groups share a mesh; count by mesh,
  and to split two groups sharing a mesh, disable one and count again.
- After an editor restart, World Partition cells are unloaded; `scripts/editor.sh open` loads them. Traces and counts
  on an unloaded level are wrong.
- Sparse obstacles survive far below their candidate density: meadow logs kept ~10% (200/ha gave 38 logs on 2 ha), so
  15/ha gave ~3 and looked like "no logs at all". Measure the count before concluding a group is broken.
