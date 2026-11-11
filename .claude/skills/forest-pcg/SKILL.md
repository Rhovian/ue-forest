---
name: forest-pcg
description: Lessons for this project's Biome Core PCG placement of everything on the island, forest, meadow and beach (scripts/pcg/*.py, regenerate_biome.py). Read before adding or changing a placement group, a density, a generator, child assets or a filter graph, and when diagnosing a slow or memory-heavy regenerate or plants that float, vanish or clump wrongly. Not for lighting, fog or materials. Append each new failure here when it is understood.
---

Each rule below cost real time when it was learned. A new rule says what broke, why, and the check that prevents it.

## New assets: pass the budget before placing

- Run `scripts/asset-budget.py` on a newly imported asset, and fix what it reports, before adding it to any placement
  group. Megaplants trees came in over 400 bones and without trunk collision; they were placed first and had to be
  re-exported from PVE afterwards (Bone Reduction, Trunk Only collision; `scripts/pve-bone-reduction.py`), with several
  variants left out (#153, operator 2026-11-09). Variants that fail go on #154's list.

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
  A full regenerate takes about 1-2 minutes and peaks at 35-45 GB after a fresh editor start. The peak creeps up
  across many regenerates in one session (45 -> 54 GB for the same content): restart the editor (`editor.sh close`,
  then `open`) when it passes ~50 GB, and compare peaks only after a restart. If a run takes much longer or the peak grows beyond that, stop
  and find out why before tuning further.
  The first regenerate after a fresh `editor.sh open` sometimes fails with `PCGComponent: Internal Error -
  ObjectInstance is null!` or passes the 60 GB guard, and saves nothing; run it again (seen three times, each
  passed on the retry at 45-48 GB).
- With the spruce-led canopy, the shore-log keepouts and the meadow (November 2026), a full regenerate peaks at
  52-58 GB after a fresh start and has passed the 60 GB guard on a second run in the same session. Restart the editor
  before every regenerate, and add skinned children (heather drifts) sparingly: 250 sand-heather anchors/ha x 18
  plants passed the guard (#165).
- Change density or extent, not both, and check the estimate before each change.
- Continuous ankle-high cover (~10-15 plants/m2) is out of PCG's reach island-wide: 500 anchors/ha x 15 children gave
  under 1/m2 and nothing visible in the interior view, and the density that read lush would be tens of millions of
  instances. Use Landscape Grass from the floor material (forest_floor.py, #100): it spawns only around the camera.
  It ignores PCG exclusions, so its weight is masked by T_GroundcoverMask (groundcover_mask.py, baked from the
  water and footpath splines); rebake it when those splines change. GrassVariety density reads far sparser than its
  "per 10 m2" label: measure in the view.
- Landscape Grass weight is sampled per landscape vertex (2 m in L_vilm): a mask with features finer than that (the
  floor material's 1.2 m litter patches, a shore band a few cm high) spawns almost nothing. Give a grass layer its own
  noise of 6 m or more (forest_floor.py, #117).
- After forest_floor.py, newly used meshes build Nanite data and compile shaders for minutes; the grass shows nothing
  until they finish (watch the log go quiet), and the first frame-time run after it measured a GPU idling at 0.3 ms
  (rerun it). Grass also fills in over seconds after each camera move: scripts/review/capture waits GRASS_SETTLE.

- A grass mask that is only a texture (T_LogMask, T_SandEdgeMask, T_WaterBedMask) does not rebuild the grass when it
  is rebaked: run `grass.FlushCache` (or rebuild the floor material) before judging it (#151).
- Virtual-streamed textures (the Electric Dreams surfaces) need Virtual sampler types: with plain ones the whole floor
  material failed to compile and the landscape showed the default checker (matgraph.sampler_for, #149).
- Height bakes that trace the landscape must ignore each actor in the way (`actors_to_ignore`), not step down past it
  1 cm at a time: inside the large logs that stalled and ~880 cells came back as "no landscape" (scan_mask.py, #151).

- A height band alone cannot find "the sand just before the forest": low sand spits by the water lie at the same
  height as the upper beach, and sand heather in a 35-75 cm band landed on the spits (#165). Use something that knows
  the forest edge (distance to it, or a mask such as T_SandEdgeMask).

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
- Overlapping groups are not pruned against anything, so the rocks, logs and stumps stood on tree trunks (#182). Core's
  difference compares whole bounds (canopy against rock), so it cannot express "not on a trunk": `solid_keepout.py`
  bakes the placed solids' footprints into every TransformGraph a tree, sapling or shrub uses instead. Rerun it, then
  regenerate, after any change to the solid groups. The understory generators share the solids' sampler points (82
  hazel within 5 cm of a solid's pivot): the keep-out removed ~40% of the hazel and huckleberry, all inside a solid.
- A TransformGraph whose Distance node sets density (the canopy-gap filter, `canopy_filter()`) overwrites the
  generator's spatial noise: turning noise on for the gap saplings changed not one instance (#164). Thin such a group
  by density, or clump it with drift children.
- A non-overlapping group at a priority below the Trees group (0) prunes the beech around its points, but its own
  skinned instances did not spawn (a veteran-beech trial left canopy holes with no tree in them); static meshes do
  spawn there (veteran_trees.py: 81 field beech, each in its own opening). Groups among the
  trees keep overlap on and a priority above 0, as ShoreTrees does.
- Distance's `SphereBounds` shape uses the bounds' half-diagonal as the radius and is signed (inside is negative), so
  a [0, x] density filter keeps only a ring outside it. Distance is 3D: for "within r of these points" on terrain use
  `CENTER` with `maximum_distance = r`, a density filter below 0.99, one Distance per radius, and a vertical column
  of targets per point (meadow.py, `canopy_filter()`).
- Equal-weight variants with the same density share every sampler point: nudge each density (deadwood_rocks.py).
- With spatial noise on, a point's noise density picks the entry: five driftwood sticks on one noisy generator spawned
  only 2 meshes. Give each variant its own noise-free generator, or put the variants in a mixed child palette.
- A thin target area (beach sand) still costs a whole-volume sample per generator: five stick generators at
  2,500/ha passed the 60 GB limit. Get the count from children (piles of 12 per anchor, debris_band.py). One anchor
  generator at the summed density did not behave like five sparse ones (a wall of logs at 5,000/ha, a bare view at
  2,000/ha): measure before merging generators.
- A group can exist and still be invisible from the fixed views: check the instances' distance and bearing from the
  pose (4 trunks island-wide read as "no driftwood"), and their material in shade (bleach strong enough to read pale).

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
- A child at the parent's own point (moss shells, tufts) needs `AssetOptions.OverlapWithChildren` on the parent row,
  or Core prunes it against its parent: hand-set rows (the Trees group's) lack it and placed none (#116).
- Children are made before Core prunes the parents by priority, so a child outlives a parent pruned by another
  group's bounds: beech tuft children at 0.1% bounds stood alone round every veteran (one in eight). Give such a
  child its parent's bounds (`flare_moss.match_bounds`), so whatever prunes the parent prunes it too.
- Children are laid out from the parent's point after its TransformGraph: sinking the rocks 15-30% of their height
  with a Transform Points offset in their own graph (`PCG_Rock_*`, #166) moved their moss shells and ivy with them
  (shell minus rock z = 0 on all 404), while ground-projected children stayed on the floor.
- Every child layout runs per parent point, and regenerate memory scales with it: a second child (trunk ivy) on a quarter
  of the ~5,700 beech pushed regenerate past the 60 GB guard twice, where the same ivy merged into the trees' existing
  moss shell as an extra section (trunk_ivy.py) peaked at ~56 GB. Add geometry to an existing child's mesh before adding
  a child to a large group (#121). Landscape Grass held ~11 GB of that: regenerate_biome.py turns it off while it runs
  (peak ~49 GB, #132).

## Verification

- Generated points are readable with `unreal.ForestPCGLibrary.get_generated_point_locations(component, "GEN:<group>")`;
  skinned instances (trees, saplings, anemones) are GPU-only and their transforms are not readable from Python.
- Edits through the editor's MCP toolsets (Niagara stack inputs, for example) change the loaded asset only: save it
  (`unreal.EditorAssetLibrary.save_loaded_asset`) and check `git status` shows it before committing.
- Revert resaved graphs with `git checkout` only while the editor is closed: a loaded package reads its file lazily,
  and the next save of PCG_PlantsAboveShore after a revert under the open editor crashed it (seek past end of file, #164).
- Capture with `scripts/review/capture`: a single raw `CaptureViewport` returns the previous view's frame.

- `regenerate_biome.py`'s per-group instance count misattributes components when groups share a mesh; count by mesh,
  and to split two groups sharing a mesh, disable one and count again.
- After an editor restart, World Partition cells are unloaded; `scripts/editor.sh open` loads them. Traces and counts
  on an unloaded level are wrong.
- Sparse obstacles survive far below their candidate density: meadow logs kept ~10% (200/ha gave 38 logs on 2 ha), so
  15/ha gave ~3 and looked like "no logs at all". Measure the count before concluding a group is broken.
