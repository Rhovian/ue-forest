# Issue #264: partitioned Local input and sampling investigation

**Answer:** Partitioning changes Self/Actor data into the partition cell intersected with the original actor, changes execution bounds to the cell clipped to original bounds, and can change which landscape proxies and upstream component outputs are selected. It does **not** automatically change the component seed. These are actual engine branches, not assumptions about the Biome graphs. [C:413–461; R:175–211; H:120–152; C:3253–3315; D:958–978]

**The source does not establish the live 6–8× shortfall's cause.** In particular, ordinary cropping of a large legacy sampling rectangle does not inherently divide density by its area fraction: both the target count and lattice-cell count shrink. In the newer sampler mode, `Ratio` is exactly 1. The strongest next investigation is to find the **first divergent count or density**, starting at the effective sampler settings and continuing through its rejection steps and the generator's downstream filters. A lower legacy Ratio would preserve identical jittered XY positions as a strict subset, but source inspection alone cannot establish that Ratio actually falls in this project. [S:65–158,281–347; A:91–139,237–292; derivation below]

Biome Core's installed C++ has no Local-stage implementation, elements, data classes, or subsystems: its only header declares a module and its only `.cpp` contains empty startup/shutdown functions. The graph routing remains unverified until the lead dumps the binary assets. [B:7–20; BH:8–15; inventory below]

## Scope and citation key

Read-only source investigation on 2026-11-18. Repository revision: `git rev-parse HEAD` printed `b5ba36776b4a7d5d2e3abc86fc4b9ea2428bf337`. No editor, builds, project checks, or code changes were used. The supplied issue's historical probe results are treated as reported observations, not independently reproduced measurements.

All citations below are `file:line` references, with these exact path expansions:

- **P** = `/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/PCG/Source/PCG`.
- **C** = `P/Private/PCGComponent.cpp`.
- **E** = `P/Private/PCGComponentExecutionState.cpp`.
- **G** = `P/Private/Graph/PCGGraphExecutor.cpp`.
- **R** = `P/Private/Data/Registry/PCGGetDataFunctionRegistry.cpp`.
- **H** = `P/Private/Helpers/PCGHelpers.cpp`.
- **K** = `P/Public/Helpers/PCGSettingsHelpers.h`.
- **S** = `P/Private/Elements/PCGSurfaceSampler.cpp`.
- **T** = `P/Private/PCGSettings.cpp`.
- **X** = `P/Private/PCGContext.cpp`.
- **D** = `P/Private/Elements/PCGDataFromActor.cpp`.
- **L** = `P/Private/Data/PCGLandscapeData.cpp`.
- **V** = `P/Private/Data/PCGVolumeData.cpp`.
- **I** = `P/Private/Data/PCGIntersectionData.cpp`.
- **PA** = `P/Private/Grid/PCGPartitionActor.cpp`.
- **N** = `P/Private/Elements/PCGSpatialNoise.cpp`.
- **SG** = `P/Private/PCGSubgraph.cpp`.
- **A** = repository `Forest/Source/Forest/ForestPCGAreaSampler.cpp`.
- **AH** = repository `Forest/Source/Forest/ForestPCGAreaSampler.h`.
- **AS** = repository `scripts/pcg/area_sampling.py`.
- **B** = `/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/Experimental/PCGBiomeCore/Source/PCGBiomeCore/Private/PCGBiomeCore.cpp`.
- **BH** = same plugin `Source/PCGBiomeCore/Public/PCGBiomeCore.h`.
- **B0** = user-supplied verbatim issue #264, especially “Known (#203, 2026-11-16 probes, before #247)” and “What has changed since.” Its measurements have not been re-run here.

## 1. What changes at a partitioned component boundary

### Component and graph inputs

The partition actor creates or updates a local `UPCGComponent`, maps it to the original, and calls `SetPropertiesFromOriginal`. That copies the seed, graph and graph parameter overrides. `InputType` is copied, with one explicit exception: an original component using Actor input on a Landscape actor becomes Landscape input when its local owner is not a Landscape. This is not a blanket conversion of volume components to Landscape input. [PA:546–580; C:413–461]

Default graph inputs are constructed only when the graph allows default constructed inputs, and only for connected output pins. The executor obtains `In` via `GetPCGData`, `Input` via `GetInputPCGData`, `Actor` via `GetActorPCGData`, `Landscape` / `Landscape Height` via their getters, and `OriginalActor` via `GetOriginalActorPCGData`. `CreatePCGData` forwards to `GetInputPCGData`. Thus “graph input” and “landscape input” are not interchangeable. [G:3364–3430; C:3247–3250; pin spellings: P/Public/PCGInputOutputSettings.h:11–15]

| Input / context | Unpartitioned volume component | Partition local component | Source |
|---|---|---|---|
| Actor / Self | Data parsed from the original owner. A volume owner yields `UPCGVolumeData` initialized from that volume. | Normal Any-data actor parsing creates a `UPCGVolumeData` for `GetFixedBounds()`, then intersects it with the original actor's spatial data. The narrower Volume-only registry query instead initializes directly from clipped grid bounds. | C:3146–3189; R:175–211,230–237; E:12–15 |
| OriginalActor | Its own Actor data. | Original component's Actor data, with a creation fallback if unavailable. | C:3093–3116 |
| In / Input when `InputType=Actor` | Actor data as above. | Local Actor data as above. | C:3247–3250,3318–3328 |
| In / Input when `InputType=Landscape` | Landscape intersected with Actor data for a volume (dimension >=3); lower-dimensional Actor data is projected onto Landscape. | Same algorithm, but Actor data now includes the cell. | C:3331–3363 |
| Landscape / Landscape Height | Searches landscape proxies overlapping Actor-data bounds; initializes landscape data over the union of those proxies' grid bounds. Height-only is a property of the returned landscape data. | Search uses local Actor-data bounds, so the selected proxies may differ. Returned landscape bounds are **not necessarily clipped to the cell**: they are the selected proxies' bounds union. With the same single proxy, they can equal the whole-volume case. | C:3253–3315 |
| Seed | Component seed combined with effective node seed for nodes using seeds. | Original seed is copied; there is no automatic cell-coordinate salt in this path. Node overrides can still change it. | C:444–445; E:18–21; X:138–150; T:723–725 |
| Execution bounds (`GetExecutionState().GetBounds()`) | Owner grid bounds: ordinary actor bounds for a volume. | Partition fixed bounds overlapped with original execution-source bounds. | E:72–81; C:3387–3410; H:120–152 |
| Original bounds | Same bounds as component. | Bounds from the original component's owner. | C:3396–3410 |
| Target / transform / local-space bounds | Original actor and its transform/local bounds. | Partition actor and its transform; partition local-space box is the fixed cell box moved to zero. Original transform/bounds have separate accessors. | E:30–57,84–93; C:3413–3436; H:192–204 |

A 2D partition cell has XY half-extent `PCGGridSize/2` and Z half-extent `HALF_WORLD_MAX1`; a 3D cell uses `PCGGridSize/2` on every axis. The final execution bounds and Actor-data intersection can therefore differ from a raw partition box, especially at the volume boundary. [PA:317–330; H:124–135; R:195–205]

### Bounding Shape is selected at each sampler, not passed universally by the component

Both samplers call `PCGSettingsHelpers::ComputeBoundingShape`: use the spatial union on the explicit Bounding Shape pin; if absent, use execution Self data. They skip this when `bUnbounded` is true. **An explicitly connected original-volume shape does not automatically acquire a cell clip inside the sampler.** Conversely an unconnected pin falls back to local Self and therefore does change under partitioning. Which case applies to each live generator is unverified. [K:113–124; S:510–533; A:237–250]

Likewise, execution bounds are available to nodes but neither sampler initializer separately reads `GetBounds()` and clips every explicit input to it. The grid domain comes from Surface and selected Bounding Shape. Cell bounds influence it through Self fallback or graph wiring; they are not an additional unconditional third rectangle. [S:596–627; A:237–285]

Dynamic subgraphs forward input data and schedule using the same execution source; entering a generator subgraph does not, in this implementation, restore the original component's Self/bounds automatically. Actual Biome generator dispatch may use additional graph nodes and must be dumped. [SG:710–738,872–880]

### Upstream Actor-data retrieval can also change

`Get Actor Data` in PCG-component-output mode collects original and local components, filters optional allowed grids, and optionally restricts overlap using the current source bounds. It then copies the selected components' generated tagged outputs. The source establishes a mechanism for different cache/generator inputs under partitioning, not proof that LocalBiomeCore enables those options. [D:52–137,958–978,1029–1051]

## 2. Exact sampler domain, lattice, randomness and acceptance

### Domain used by both implementations

Let `B` be selected Bounding Shape bounds (invalid if unbounded), and `S` the Surface. Stock computes a single effective grid box `D` per Surface; Forest reproduces this selection before calling stock's exported grid initializer:

1. If `S.GetLocalBounds()` is valid: `D = OverlapBounds(LocalBounds.TransformBy(S.GetTransform()), B)`.
2. Otherwise, if Surface is bounded: start with `S.GetBounds()` and intersect with `B` only if `B` is valid.
3. Otherwise use `B`.

These are literal code branches. In branch 1, `OverlapBounds` returns invalid when either operand is invalid; do not generalize branch 2's optional-bounds behavior to every surface. `Surface.GetTransform()` is used by the code despite the surrounding stock comment's “without rotation” description. Invalid `D` fails initialization. [S:596–627,49–54; A:255–285; H:108–117]

Forest does **not** replace `D` by Region bounds or the tile cover. It first initializes the grid on `D`, then builds sparse row spans from Region Tiles, clipped to that grid's integer min/max indices. The tile inversion includes the full jitter interval and merges overlapping/adjacent spans. Region is a later predicate at the projected center; it does not contribute density or metadata to the output. [A:40–77,113–119,255–292; AH:12–18]

### Lattice construction

Use `e=(ex,ey,ez)` for PointExtents, `l` for Looseness, `p` for PointsPerSquaredMeter, and `s=(sx,sy,sz)` for CellSize, in centimeters. [S:28–40,65–106]

**Legacy:** `InterstitialDistance=2e`, `InnerCellSize=2e*l`, `InnerCellOffset=0`, `s=2e*(1+l)`. Density `p` does not change lattice spacing here. [S:100–106]

**New mode:** `U=10000/p` for positive `p` (otherwise a very large number). Let `m=2*min(ex,ey)`, `M=2*max(ex,ey)`, `b=sqrt(U/(M/m))`. Initially `sx=b*2*ex/m`, `sy=b*2*ey/m`; enforce `sx>=2ex`, `sy>=2ey`. Let `r=s-2e` and `lc=clamp(l,0,1)`. Then `InnerCellSize=r*lc`, `InnerCellOffset=r*(1-lc)/2`. In this mode density generally changes spacing; there is still only one candidate per lattice cell. [S:65–98]

In either mode:

```
ix_min = ceil(D.Min.X / sx); ix_max = floor(D.Max.X / sx)
iy_min = ceil(D.Min.Y / sy); iy_max = floor(D.Max.Y / sy)
Nx = 1 + ix_max - ix_min; Ny = 1 + iy_max - iy_min
N = Nx * Ny
```

The grid is aligned to coordinate zero, not rebased to the lower corner of each component. Invalid/empty/too-large cell counts fail initialization; there is no memory-pressure branch that keeps an arbitrary fraction of cells. [S:116–175]

### Ratio

**New mode:** `Ratio=1`. Its variable named `TargetPointCount` receives area, but is not used to compute a fractional Ratio. [S:147–158]

**Legacy:**

```
Area = (D.Max.X-D.Min.X) * (D.Max.Y-D.Min.Y)
Target = Area * p / 10000
Ratio = clamp(Target / N, 0, 1)
```

`D` controls both numerator and denominator. Forest copies effective settings into `Grid.Params` and invokes this exact engine initializer, so the project does not have an independent, divergent Ratio formula. “Original domain” in Forest means the stock Surface/Bounding Shape effective domain **before sparse Region restriction**, not an explicit fetch of the original unpartitioned component's domain. [S:147–158; A:255–292; AH:18]

The Forest class default is new mode (`false`), but its graph-building script copies `use_legacy_grid_creation_method` from the installed template. Stock also migrates old serialized samplers to legacy mode. Neither a C++ default nor that migration proves the currently loaded Area graphs' mode: print the saved/effective property. [AH:59–60; AS:135–146; S:440–450]

### Random stream and emitted point

For each global lattice index `(ix,iy)`, both implementations create `FRandomStream(ComputeSeed(Grid.Seed,ix,iy))`. First draw `Chance`; reject if `Chance>=Ratio`. Next draw `RandX`, `RandY`, and set preprojection XY to `(ix*sx+offset.x+RandX*inner.x, iy*sy+offset.y+RandY*inner.y)`. Skipping other cells does not advance this cell's stream. For unchanged grid parameters/seed, lowering Ratio keeps a nested subset at exactly unchanged jittered XY positions. This matches the *kind* of historical observation, not a demonstration of its cause. [S:274–303; A:87–103; H:45–47; B0]

Z before projection comes from `D.Max.Z` lowered by a small multiplier/epsilon and clamped to `D.Min.Z`. A nonzero Surface rotation activates a projection-plane transform built around the Surface translation. Thus a changed domain Z or Surface transform can change projection success even with unchanged XY lattice streams. [S:178–198; A:99–107,285]

After the chance test, stock projects to Surface; rejects failed projection; samples Bounding Shape using point extents; rejects failed shape sampling unless keep-zero is enabled; multiplies output density by the sampled shape density; optionally applies `(Ratio-Chance)/Ratio`; then emits. Forest follows that order with an extra Region-positive test after projection and before Bounding Shape. **Fractional Bounding Shape density is not itself another stochastic rejection in these samplers**, but downstream graph nodes may use it. Projection-produced density is not carried through: output density starts at 1 in both. [S:311–347; A:105–139]

### Why simply shrinking the rectangle is not a 6–8× explanation

For a rectangle spanning many lattice cells, `N ≈ Area/(sx*sy)`, so legacy `Ratio ≈ clamp(p*sx*sy/10000,0,1)`. The area cancels. This is an algebraic consequence of the exact preceding equations, not an editor observation. [S:116–158]

More precisely, write `Lx=D.Size.X`, `Ly=D.Size.Y`, `q=N/(Area/(sx*sy))`; then unclamped `Ratio=(p*sx*sy/10000)/q`, and `q <= (1+sx/Lx)*(1+sy/Ly)` because each axis includes at most `L/s+1` grid origins. If both dimensions are at least one cell spacing, `q<=4`; when both span many spacings it is near 1. To attribute a 6–8× loss to Ratio, compare the **actual two Ratios**, including clamp behavior and `q`, rather than comparing map areas. Extreme narrow/tiny domains can have large boundary effects; invalid boxes yield no output, not a uniform fractional output. [Derivation from S:116–168]

With fixed legacy parameters and an ordinary large-cell crop, a domain mismatch alone therefore does not supply the claimed multiplier. A density override reduced by 6–8× *can* lower legacy Ratio by that factor when unclamped while preserving positions; in new mode it generally changes spacing instead. A common later density/selection filter can preserve those positions too. [S:65–158,281–344; A:91–139; inference, live values unverified]

There is a separate crop-edge issue: `ceil(D.Min/s)` excludes lattice origins below `D.Min` even if their positive jitter could land inside the cell. Forest's tile padding helps tile boundaries **inside** `D`, but its spans remain clamped to grid indices, so it cannot repair origins already excluded by the domain crop. This predicts boundary strips, not a uniform deep-interior 6–8× thinning when cells span many lattice spacings. [S:116–120,294–297; A:43–50; inference]

## 3. What Biome Core C++ can establish

The command `rg --files '/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/Experimental/PCGBiomeCore/Source'` returned exactly:

```
PCGBiomeCore/Private/PCGBiomeCore.cpp
PCGBiomeCore/Public/PCGBiomeCore.h
PCGBiomeCore/PCGBiomeCore.Build.cs
```

The header declares only `FPCGBiomeCoreModule`, whose startup and shutdown bodies are empty. No Biome-specific C++ branch treats Local generators as partitioned. Its module dependencies are Core, CoreUObject, Engine, Slate and SlateCore. Any Local-specific routing/normalization in this installed plugin must be established by graph/Blueprint inspection rather than an invented C++ subsystem. [B:7–20; BH:8–15; plugin PCGBiomeCore.Build.cs:25–43; inventory command above]

One **generic PCG** difference relevant to generator graphs is Spatial Noise: it reads the current execution source's local-space bounds and transform, not original-source bounds/transform. A partition actor changes that context. Freezing per-set min/max does not freeze those coordinates. This is independently real but cannot alone explain the supplied noise-off historical repro. [N:712–737; E:30–44,84–93; H:192–204; B0]

The repository graph builder copies template settings and existing sampler edges, supplies Region and Region Tiles from a world-space Create Points node with outside-volume culling disabled, and replaces remap range inputs with constants when ranges are supplied. This supports checking inherited wiring and effective overrides; it does not verify the saved binary graphs or every runtime execution branch. [AS:135–170]

## 4. Ranked candidates and discriminating editor probes

Ranks are investigation priorities, not verified diagnoses. The historical subset/noise-off observations are from B0; current Area generators need the same measurements before assigning a cause.

| Rank | Candidate and evidence | Probe the lead should run; confirmation / elimination |
|---|---|---|
| 1 | **Shared effective input/parameter or density filtering differs across local execution.** In legacy mode a smaller effective `PointsPerSquaredMeter` lowers Ratio without shifting XY. If sampler outputs match, a shared density/colony/other filter can remove the same XY subset later. Both fit subset geometry; different source context and overrides are actual available mechanisms. [S:100–106,157–158,281–344; C:444–461; A:135–139] | On the original `PCG_LocalBiomeCore` component and its local components for `(1,-2)` and `(2,-2)`, inspect Trees, FernsGaps, Hornbeams generator invocations. Print effective sampler `p`, extents, looseness, legacy flag, seed, apply-density and unbounded flags, including override input values. Capture immediate sampler output and every subsequent density/colony/filter output, compared against whole-volume output cropped to the same cell. If legacy `Ratio_local/Ratio_whole≈1/6…1/8`, trace `p` and `q`; if Ratios/output match, locate the first later node that diverges. Equal actual values and equal point densities through those stages eliminate this candidate. |
| 2 | **Different spatial predicates or selected upstream data, including a Surface/Bounding Shape built from a different cache.** Actor/Self changes, Landscape proxy selection may change, and Get Actor Data can choose different components/grids. Shape/projection failures preserve surviving XY. A pure box volume adds binary membership, not a uniform fractional interior density: intersections sample both operands and combine densities, while volume interiors return 1. [R:175–205; C:3286–3313; D:91–134,958–978; I:113–134; V:169–203] | Dump LocalBiomeCore's data-retrieval paths and trace actual Surface and Bounding Shape inputs into each generator. Print class/path, all tags, bounds, local bounds, Surface transform; recursively identify union/intersection operands; selected landscape proxies; upstream original/local component paths, grid sizes and counts. Replay missing whole-volume points against **local** Surface projection and Bounding Shape sampling, with exact sampler extents. Confirm at the first failure/density delta. Equal selected data and equal results for missing points eliminate this explanation at the sampler. |
| 3 | **Legacy Ratio distorted by actual domain geometry or unexpected domain construction.** Possible only if live legacy mode is true. A smaller area alone is insufficient; exact grid rounding, clamping and effective settings matter. In new mode Ratio cannot explain stochastic thinning because it is 1. [S:116–168; A:255–285] | Print both actual `D.Min/Max`, `sx/sy`, integer min/max, `Nx/Ny/N`, `Area`, `Target`, Ratio and `q` at the initializer for all three generators. Recompute the formula outside the editor. Confirm only if the measured Ratio drop predicts losses at the first chance test with identical streams. Ratio equal (or both 1) eliminates this cause immediately. |
| 4 | **Noise coordinates change with execution actor; a downstream branch remains set-relative or density-dependent.** Current actor transform/local box changes in native Spatial Noise; the project freezes named remaps, not every potential binary-graph branch. Noise alone is contradicted as the sole explanation by the historical noise-off observation. [N:712–737; AS:23–33,163–170; B0] | First use Hornbeams with noise demonstrably bypassed in the *executed* branch. In Trees/FernsGaps compare per-point density before/after each spatial/Voronoi/slope/colony operation for matched XY; print effective remap limits and noise context. An identical no-noise shortfall excludes noise as the common sole cause; density divergence at a specific active node identifies an additional contribution. |
| 5 | **Area-specific missing tile/Region coverage or crop-edge omissions.** Tiles/Region independently reject points after the shared grid initializer; incomplete cover preserves a subset. These cannot explain the original stock-sampler-era problem by themselves, but could affect the current repro. Index clipping also loses jitter-in origins at cell minima. [A:40–77,113–117,209–235,285–295; B0; S:116–120] | For each missing reference point, recover its lattice index and test whether the local spans visit it, projection succeeds and Region returns density >0. Print tile count/bounds, Region class/bounds, visited-index count and positions of misses relative to cell edges. Confirm if misses align with absent spans/Region or boundary strips. Full interior coverage and successful predicates eliminate this candidate. |
| 6 | **Changed seed/grid parameters.** Local component seed is copied; per-cell streams depend on global indices, not partition enumeration order. Different seed or jitter parameters normally move points, conflicting with the historical exact jittered-XY matches (unless degenerate zero jitter or other coincidences). [C:444–445; S:65–120,281–303; A:91–103; B0] | Print component seed, effective node seed, `Context.GetSeed()`, spacing, jitter size/offset and Surface transform. For several common lattice indices compare `ComputeSeed`, Chance, RandX, RandY and preprojection position in both runs. Equality eliminates sampler random-stream changes. Differences require tracing effective overrides before blaming partitioning itself. |

### Minimal first probe: separate rejection stages

For each `(component, invocation stack, generator, surface datum)`, obtain these counts and a small deterministic set of lattice-index/point records. These are proposed probe fields, not existing editor API promises; internal values may require a lead-owned temporary diagnostic or debugger inspection.

1. **Initialized grid:** effective properties, Surface and Bounding Shape provenance, `D`, grid sizes/index ranges, Seed and Ratio. [S:49–158; A:237–285]
2. **Visited → chance accepted → projection succeeded → Region accepted → Bounding Shape accepted → emitted**, recording sampled shape density and final density. Stock has no Region step. Also count missing whole-volume indices excluded before visit. [A:87–147; S:281–347]
3. **Immediate sampler output → density/noise/colony/filter outputs → generator output → final Local roots**, comparing point sets and density at matched XY. The exact node names/edges after the sampler require the graph dumps below. [AS:135–170; binary topology unverified]

Normalize all comparisons to the same half-open world XY cell and the same generator/Surface invocation; compare whole-volume points in that cell against cell-generated points. Source volume membership uses inclusive minimum/exclusive maximum bounds. The known issue compares roots, which does not itself locate a loss at the sampler's Chance test; the first-output comparison is required. [H:95–105; S:281–347; B0]

## 5. Graph dumps needed from the lead

No binary graph contents were inferred from filenames. The following asset paths exist on disk (enumerated by `rg --files` in the plugin Content and repository Forest/Content trees); project construction references are additionally in AS:21,39,135–146.

- **Actual component graph for `PCG_LocalBiomeCore` on ForestBiomeVolume**, including graph-instance parameter overrides, default constructed input setting, hierarchical generation settings, grid size, InputType and seed, plus the matching partition local component properties. Follow its graph reference rather than assuming the component and graph share a name. Dump `/PCGBiomeCore/LocalBiomeCore` if it is the referenced asset. Purpose: identify Actor versus OriginalActor, explicit Bounding Shape versus Self fallback, retrieval/cache inputs and stage dispatch. [G:3364–3430; C:413–461; K:113–124]
- **`/PCGBiomeCore/Core/BiomeCore_RunGenerators` and `/PCGBiomeCore/Core/BiomeCore_PerGeneratorLoop`**, plus any referenced graphs on the actual path to the generator. Purpose: trace forwarded Surface/Bounding Shape data, per-generator parameters/seeds, cache selection, and any local-bounds arithmetic. These contents are unverified; the names identify inspection targets, not asserted internals.
- **`/PCGBiomeCore/GraphTemplates/TPL_BiomeCore_Generator_Advanced`**, and the actual `/Game/ForestBiome/PCG_Forest_TreesGenerator`, `PCG_Forest_FernsGapsGenerator`, `PCG_Forest_HornbeamsGenerator` with their referenced Area parent graphs and generator data assets. Purpose: inspect saved sampler mode/settings, pin-to-pin overrides and all downstream density/filter branches. The builder copies this template and inherited sampler edges, so inspecting only the C++ class default would miss serialized behavior. [AS:21,39,135–170]
- **Any LocalBiomeCore cache subgraphs actually feeding those inputs**; existing named candidates include `/PCGBiomeCore/Core/BiomeLocalCache`, `BiomeLocalCache_Volume`, `BiomeLocalCache_Spline`, `BiomeLocalCache_Texture`. Purpose: compare selected data/classes/bounds/density in whole and partition executions. Their involvement is unverified until the preceding dumps establish the edges.

Each dump should include node object name, settings class, graph references, seed/mode/overridable settings, selector/grid/overlap flags, graph parameters and every edge `(upstream node,pin → downstream node,pin)`. Pair topology with execution data; topology alone cannot establish an effective override or selected datum. [C:451–461; K:113–124; D:958–978; AS:139–146]

## 6. Constraints on a later fix

Do not multiply all generator densities by six without locating the first divergence. Matching roots requires matching per-index randomness and acceptance/density predicates, and can also require keeping the original-domain legacy Ratio while restricting enumeration separately. Forest already separates Region tile iteration from the stock grid initializer, but does not automatically retain the original component's domain under partitioning. [A:255–292,91–139; S:116–158]

Simply wiring the entire original bounding shape everywhere is not yet a cell-bounded solution: the sampler would derive the original grid domain, and the shared initializer still validates the whole rectangular cell count and applies its sampler-memory guard even though Forest later visits sparse spans. Any fix retaining a reference domain must also ensure per-cell enumeration/ownership and inspect those checks on larger maps. [K:113–124; A:255–292; S:123–175]

This investigation establishes source behavior and falsifiable probes. It does not establish the loaded graph wiring, current partition output counts, a fix, or memory/time measurements. Those require the lead's editor work and the issue's fresh-start measurements; none are reported as completed here.
