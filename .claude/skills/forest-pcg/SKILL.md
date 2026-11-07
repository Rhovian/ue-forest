---
name: forest-pcg
description: Lessons for building and tuning this project's Biome Core PCG placement (scripts/pcg/*.py, regenerate_biome.py). Read before adding or changing a placement group, a density, a generator, child assets or a filter graph. Append each new failure here when it is understood.
---

Each rule below cost real time when it was learned. Add a rule when a new failure is understood: what broke, why,
and the check that prevents it.

## Cost: estimate before you build

- A generator samples the **whole biome volume** before any filter, so its cost is density x the island's bounds
  (~470 ha), not density x the area it ends up on. 600,000/ha for a 2 ha meadow asked for ~185 million points and put
  the operator's 96 GB machine under memory pressure.
- `deadwood_rocks.generator()` refuses estimates above `MAX_CANDIDATES` (`candidate_estimate`). Never raise the budget
  to get around it: change the design.
- **Dense cover on a small area** (meadow grass, patches): a sparse anchor generator plus a child patch per anchor
  (`children()` with a disc of points, `ground=True`), as in `meadow.py`. Cost then scales with the anchors.
- `regenerate_biome.py` prints duration and peak editor memory, and cancels the generation above `MEMORY_LIMIT_GB`.
  A full regenerate takes about 1 minute and peaks at 35-39 GB. If a run takes much longer or the peak grows, stop and
  find out why before tuning further.
- Change one variable at a time (density *or* extent), and check the estimate before each change.

## Counts do not scale smoothly

- The template's spatial noise thins candidates heavily and nonlinearly: driftwood went from ~400 pieces at 1,800/ha to
  17,600 at 2,500/ha; meadow anchors from 4,510 to 105,000 between 600 and 3,000/ha. Probe two or three densities and
  measure the instance count; don't extrapolate.
- The sampler emits at most one point per (2 x extent)^2 cell: density above that cap does nothing but cost.

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
- Created child points need distinct seeds before Transform Points, or every sibling shares yaw and scale.

## Verification

- `regenerate_biome.py`'s per-group instance count misattributes components when groups share a mesh; count by mesh.
- After an editor restart, World Partition cells are unloaded; `scripts/editor.sh open` loads them. Traces and counts
  on an unloaded level are wrong.
- Never commit with `git commit -a` while the operator has the editor: it sweeps their unsaved-session files in.
