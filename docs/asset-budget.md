# Asset Budget (feasibility phase)

The rules every asset must meet before a Forest Biome may place it. Decided in [#14](https://github.com/Rhovian/ue-forest/issues/14) from the measurements in [#13](https://github.com/Rhovian/ue-forest/issues/13).

## Scope

- Read-only automated audit: the lead runs `scripts/editor-py scripts/asset-budget.py` for every rule below under `/Game` except `/Game/Scratch` and Megaplants `Instances` part meshes (a tree assembly overrides its parts' Nanite settings at build). Script policy: the displacement exception is recognised by `Displacement` in the name (case-insensitive) and does not check "shared across a species"; Fab's shared defaults under `/Game/Fab/Textures` are treated like plugin content (its wind noise feeds the vertex shader, where virtual textures cannot be sampled).
- **Caps, not frame-time gates.** These rules cap what is expensive to change later. Frame time is measured for every asset with `scripts/measure/run.sh` and recorded, but gates nothing until the optimization phase.
- **Measuring machine:** the target Mac (M2 Max), PIE in a 1920×1080 window, software Lumen, Epic scalability. The low-end PC target is decided when optimization starts.
- **Reference density:** about 150 trees per hectare.

## Rules for every asset

| Rule | Requirement |
|---|---|
| Nanite | Every mesh is Nanite. An exception needs a measured reason. |
| Opacity | Materials a mesh uses are opaque or masked; no translucency. Decals and surface sets (texture sources for the landscape material) are never on a mesh, so they are not checked. |
| Textures | At most 4096. Virtual texturing above 2048 on textures a material uses (generator inputs such as PVE displacement maps are never rendered). Displacement maps up to 4096×8192 when shared across a species. |
| Bones | Skinned trees have at most 400 bones; reduce with PVE Bone Reduction at export. |
| Collision | Trees (skinned plants taller than 6 m) have a physics asset (export with PVE collision, Trunk Only). Fallen logs, limestone slabs and stumps block the walker: 1–4 simple convex hulls, SimpleAsComplex trace mode and BlockAll profile on the scan; Biome MeshOptions.AllowCollision enabled. Saplings, shrubs, flowers, mushrooms and ground plants have none: the walker passes through them. |
| Plugin content | Master material (`MA_Foliage_Trees`), Wind Driver (`BP_GlobalFoliageActor_UE5`) and `Wind_TransformProvider` are used from PVE plugin sample content, and every material's parent must load. The audit checks they load, so rerun it after each engine upgrade; copy them into the project only if an upgrade breaks them (Advanced Copy refuses engine-plugin content, so a copy needs a reference-remapping tool). |
| Distant foliage | Foliage (skinned plants and Megascans plants) uses Nanite shape preservation: Voxelize. Rocks, logs, stumps and mushrooms keep their default. PreserveArea and None cost the same GPU time ([#17](https://github.com/Rhovian/ue-forest/issues/17)); switch the mesh's setting if distant trees look wrong in the forest. |

## What makes the cut

- **Species:** European Beech (Megaplants). Ground, rock and debris fill-ins inherit the rules above and get their own caps when chosen.
- **Tree Variants:** A, B, C, D from `PVE_European_Beech_01`. C (388 bones) and D (198) pass as shipped. A (1,113) and B (1,052) are re-exported with PVE Bone Reduction at Strength 1.0 (the only setting under 400): A 386, B 347; A's game-thread time at 100 trees drops 25–40%, to near D. Both passed the sway check (2026-10-07); a variant whose sway looks wrong after reduction is dropped.
- **Saplings:** A, B, D from `PVE_Tree_European_Beech_Saplings_01`. A and B re-exported with Bone Reduction at Strength 1.0 (`scripts/pve-bone-reduction.py`): A 77 bones, B 69; D 73 as shipped. C is dropped: its branches have no parent bones (`FindParentBoneForBranch fallback`), so reduction leaves all 1,134.
- **Quality tiers:** none yet; defined with the low-end target.
- **Variation:** the four variants, plus random yaw and uniform scale 0.8–1.2 in PCG. More PVE variants (via the Scale node) only if the forest looks repetitive.

## Deferred to optimization

- Frame-time gates and a low-end PC spec (including whether Windows is in scope).
- No wind on far trees.
- Tightening the bone cap toward 200.

## Deadwood and Rocks (step 8a)

`scripts/pcg/deadwood_rocks.py --check` validates loaded forest biome membership and source assets without edits.
Run without `--check` to build reusable generator/asset groups and attach them to the forest biome;
regenerate Biome Core and save the level afterwards. It leaves Trees settings and stock materials intact.
The audit reads all configured log, stump and slab mesh paths from
`scripts/pcg/biome_variants.py`, including Large Fallen Tree, as solid scans.
It counts their convex hulls with `get_convex_collision_count`; UE's `get_simple_collision_count`
counts only boxes, spheres and capsules and excludes convex hulls.
Instance collision still needs a walker check after generation (the asset audit cannot verify generated components).

- Deadwood: 18 candidates/ha, weighted 8 plain logs : 4 nurse logs : 6 stumps; slope at most 20°.
  A nurse log is the same fallen log with one attached Bolete mushroom cluster via Core recursive ChildAssets.
  `scripts/pcg/nurse_anchor.py` raycasts the source LOD0 triangles at log-local XY (0, 0), embeds
  the stem base 0.25 cm into that surface, applies the full parent transform including scale,
  and only then makes fungi upright. Both preflight and build fail if the source ray misses.
  Nurse logs stay below 12 m elevation, a low-ground dampness proxy; this reduces their final share below one third.
- Rocks: 30 slab candidates/ha, slopes 5–35° to concentrate on banks and slopes rather than flat clearings.
- Both use Core's inherited spatial-noise patches (density band 0.35–1), random yaw and uniform 0.8–1.2 scale.
  Counts decrease after masks and shore/water exclusions. Deadwood and Rocks bypass cross-generator
  priority difference (`GeneratorAllowOverlap=True`): full canopy bounds otherwise removed almost all
  ground obstacles (lead probe: 34 deadwood/28 slabs before bypass, 371/408 after). Tree output was
  identical in both cases. The new groups may overlap each other or trunks; inspect intersections
  visually rather than using canopy-sized exclusion bounds. Trees settings remain unchanged.
  Logs follow landscape normals; stumps, slabs and fungi use Core OrientUpward=1 (world up).
  Rotation ranges use named pitch/yaw/roll fields: Python's positional Rotator order is roll/pitch/yaw.
  XY scramble is disabled to preserve sampled terrain contact. Inspect contacts on steep ground.
- Root points must be at least 1.5 m above the floor's ShoreHeight (default total 2.25 m).
  Core's existing lake/river exclusion splines and future BiomePath keep-outs apply; step 8b must regenerate
  all groups after adding its path. No path route or landscape painting is invented here.
- Four convex hulls of at most 16 vertices per obstacle; fungi have instance collision disabled.
  No moss coating or broad understory is built. A second fallen-log silhouette would help repetition most;
  evaluate that visually before acquiring more assets.

The installed fallen-log scan is approximately 270×67×14 cm (lead-measured bounds), a shallow
weathered piece rather than the earlier research listing's dimensions. The root plate makes its
bounds center a poor fungi anchor: bounds maximum height is not the bark height there. Do not lift roots
based on an unrestricted BlockAll downward trace: it can hit the obstacle's own convex collision;
ignore all non-LandscapeProxy actors when measuring terrain contact.

## Appendable palettes and whole fallen trunks

`LOG_VARIANTS`, `STUMP_VARIANTS`, `SLAB_VARIANTS` and `FUNGI_VARIANTS` in
`scripts/pcg/biome_variants.py` accept one `(Megascans-relative mesh path, positive weight)` row
per variant. Append a row to extend a palette; run the builder again. Builder and audit reload
this module on each run, including in an already-open editor. Lists must be nonempty, paths unique.
All obstacle variants automatically receive collision generation and exact-path budget coverage;
fungi remain nonblocking. Fungi alternatives share one child graph per log; their stem-base pivots
must agree within 1 mm (preflight fails otherwise). Stock materials remain assigned by each mesh.

The two installed logs use weights 0.85 (2.7 m piece) and 0.15 (17.246 m Large Fallen Tree).
Each log has its own generator: total 12 log candidates/ha split by normalized weight,
with plain:nurse weights 2:1 per variant. Stumps use 6 candidates/ha; slab palette uses 30.
Changing the palette redistributes these fixed category totals, not the number of candidates per variant.
Existing debris placements may change; Trees assets/settings are untouched. The second Nordic
acquisition reimported the same small scan, so exactly two log variants are configured for now.
A future distinct scan can still be added as one row once its actual mesh path is known.

Meshes longer than 10 m automatically use an 8° root-slope limit. Their maximum scaled reach
(from source pivot to farthest bounds corner at 1.2 scale) adds `reach*sin(8°)` to the normal
shore rise. Plain and nurse graphs also subtract the bounds of every `PCG_BiomeExclusion` actor,
expanded sideways by reach + 3 m and vertically through the whole terrain. These conservative
boxes protect lake/stream margins even when their splines are curved; they may reject dry land
inside a stream's broad bounds. This mask affects only long-log entries, not shared exclusions or
Trees. Future tagged exclusions participate automatically. A root slope alone cannot detect a crest
or hollow under 17 m: lead acceptance checks along-trunk terrain support before saving.
The former 3° mask was too restrictive for useful variety. The 8° mask admits more gentle slopes;
the 50 cm along-trunk support tolerance and expanded water keep-out still apply.
Plain and nurse logs now share identical terrain/shore/water eligibility. The old 12 m nurse
altitude ceiling could discard selected nurses and is removed: altitude alone does not establish
forest dampness. Plain:nurse weights stay 2:1; actual realized counts must be checked after generation.

Both source logs are queried independently for nurse bark contact; no anchor is reused across scans.
A second log's source-ray miss is a fail-fast preflight error, never a fallback to AABB height.
The lead must inspect collision fit and bark contact on both variants and measure frame time.
