# Distance wind and shadows — UE 5.8.3 / Metal

**Answer:** Use `AnimationMinScreenSize` on `InstancedSkinnedMeshComponent`, or raise `r.Skinning.DefaultAnimationMinScreenSize` from its default `0.1` when component values are `0`. The threshold is evaluated **per instance**, using primary-view projected bounds. Below it, Nanite renders the tree in bind pose and the instance ceases to be marked deforming; the same flag controls VSM skinning invalidation. This is the built-in way to retain near wind and animated shadows while allowing far tree shadows to cache. [S1, S2, S3, S4; Epic Nanite Foliage](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-foliage)

**Start with a reversible `0.2` trial**, then `0.15` or `0.3` as visual/performance tradeoffs require. These are proposed trial values, not measured settings. Do not expect `Rigid`, `Static`, WPO disable distance, or `ResolutionLodBiasDirectionalMoving` to solve active skeletal wind invalidation. The Nanite deformation path bypasses material invalidation suppression; “Moving” describes the light. PCG's skinned descriptor exposes neither animation screen size nor shadow invalidation behavior, so a global cvar is the shortest persistent route. [S4, S5, S6, S7]

No editor access, asset changes, build, gate, or GPU measurement was performed. The supplied 22 ms / 5 ms ShadowDepths measurements are accepted context, not independently verified. Savings below are predictions; reaching 33.3 ms is unverified. The inspected installation identifies itself as 5.8.3, CL 58210709, `++UE5+Release-5.8` in `Engine/Build/Build.version:2`.

## 1. Animation control and its actual scope

| Setting | Default / meaning | Lead application |
|---|---|---|
| `AnimationMinScreenSize` | Component default `0.0`: inherit global; negative: unlimited animation range; positive: projected-footprint cutoff. Component policy, per-instance decision. [S1, S3] | `comp.set_animation_min_screen_size(0.2)`; alternatively `comp.set_editor_property("animation_min_screen_size", 0.2)`. The setter is reflected and marks render state dirty. [S1, S8] |
| `r.Skinning.DefaultAnimationMinScreenSize` | `0.1`; applies only where component value is zero. Increasing it stops animation nearer the camera. [S2, S3] | `unreal.SystemLibrary.execute_console_command(world, "r.Skinning.DefaultAnimationMinScreenSize 0.2")` |
| `TransformProvider` | Component/provider asset assignment; no assignment falls back to the reference-pose provider. This is a whole-component choice, not a distance policy. [S9] | `comp.set_transform_provider(None)` for a deliberately static component; retain the original asset to restore. Do not assume this alone clears the renderer's distance-based deforming flag. [S3, S9] |
| `r.InstancedSkinnedMeshes.ForceRefPose` | `0`; setting it recreates component render states and forces reference-pose provider selection globally. Diagnostic only; fails the operator's near-wind requirement, and does not itself alter the screen-size flag test. [S10, S9, S3] | `unreal.SystemLibrary.execute_console_command(world, "r.InstancedSkinnedMeshes.ForceRefPose 1")`; restore `0`. |

The shader tests `screenMultipleSquared * radiusSquared >= thresholdSquared * cameraDistanceSquared`, where radius is the length of scaled local bounds extent, distance is to the bounds center, and the view is a primary renderer view. Thus it is **not an exact meter distance**: tree scale/bounds and camera projection affect it. For fixed bounds/projection, doubling the threshold halves the animation cutoff distance (inference from the inequality). The shader handles multiple primary views with separate bits. [S3]

Below threshold is **bind/reference pose**, not “freeze the last wind pose.” There is no gradual distance-amplitude blend in the inspected threshold implementation: it writes a deforming view mask. Possible visible snapping and threshold-crossing artifacts need the lead's visual check. [S3, S4; Epic Nanite Foliage](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-foliage)

DynamicWind source is present. `UDynamicWindData` is a GPU-only transform provider without editable distance/amplitude fields in its class declaration. It batches by skeleton, and instance transform yaw chooses the wind directionality slice. Its shader receives global wind speed, amplitude, time, and direction; no camera-distance fade parameter is declared. Therefore a smooth near/full → middle/less → far/none wind policy would need a custom provider/shader or another implementation; no stock distance-fade field was verified. [S11, S12, S13]

The existing wind controls are global, not per-instance distance LOD: `DynamicWind.OverrideSpeed=-1`, `DynamicWind.OverrideAmplitude=-1` (negative uses supplied wind parameters), `DynamicWind.OverrideRateOfChange=0.5` (amplitude smoothing), `DynamicWind.UseSine=false`, `DynamicWind.PreferAsyncCompute=false`. `DynamicWind.Enable=true` is read-only and controls subsystem creation. The parameter struct has `WindSpeed=15`, `WindAmplitude=1`, `SimulationCenter`, `SimulationExtents`, direction, texture, and debug modulation; center/extents are not verified as an animation cutoff and are absent from the evaluation shader parameter block. [S12, S13, S14]

Example global amplitude change: `unreal.SystemLibrary.execute_console_command(world, "DynamicWind.OverrideAmplitude 0.5")`; restore `-1`. It is **not** recommended for this task: less visible motion still passes the same deforming threshold and continues invalidating pages. Even zero amplitude is not a reliable cache fix because the renderer flag depends on projected size, not whether the matrices actually changed. [S3, S4, S12]

Bone maps/LOD storage exist, and `bUseGpuLodSelection` / `bForceAnimateSockets` exist on the component, but neither is documented in that header as a distance freeze. The GPU LOD-selection override shown is on the non-Nanite scene proxy. No stock per-instance update-rate, max-animation-distance, or progressive bone-distance wind LOD was found in the inspected component, provider, or skinning cvar declarations. Ordinary CPU animation tick optimization is not verified as affecting this GPU DynamicWind path; do not recommend it without a targeted test. [S1:116, S15:138, S16, S2, S11, S12]

## 2. VSM invalidation: why distance cutoff matters

**There are multiple invalidation paths.** Nanite cluster culling invalidates when material/WPO requires it **OR** the instance's primary-view `bIsDeforming` is true. The WPO helper applies `Rigid`/`Static` suppression only to the material term; it does not gate the deformation term. The per-page draw-command shader contains the same OR. Therefore neither mode reliably suppresses actively skinned Nanite tree invalidation in this build. [S4, S17, S18]

The GPU cache state tracks deforming status per instance and per primary view, including transitions. It invalidates on transitions **to dynamic**, and renders newly static instances into existing pages on transition back. The implementation explicitly acknowledges possible double shadows and has a TODO for hysteresis. This supports using the threshold, but also means crossing its boundary deserves visual inspection. It does not mean one near animated tree necessarily makes every far instance in its component animate. [S19, S20, S3]

Component updates/add/remove can invalidate instance ranges: the CPU collector uses the primitive's instance offset/count; static behavior suppresses updated-primitive invalidation, while removals still invalidate. Whole-primitive dynamic classification takes precedence over per-instance static classification. Consequently changing provider/settings or repeatedly recreating PCG components can cause fresh invalidation independent of distance, and moving components should not be assumed to get the same cache reuse as stationary PCG components. PCG's descriptor default mobility is Static. [S21, S18:109, S22]

| `ShadowCacheInvalidationBehavior` | Intended semantics and relevant limitation |
|---|---|
| `Auto` (component default) | Normal material/transform invalidation; CPU deformable-mesh path runs when enabled. Active Nanite skinning additionally invalidates via its instance flag. [S23, S24, S4] |
| `Always` | Explicit unconditional primitive invalidation; the cache manager processes these as transform updates. Avoid on these trees: it defeats distance-based cache reuse. [S23, S25] |
| `Rigid` | Suppresses material invalidations, preserves transform invalidation; skips the CPU Auto deformable path. Does **not** suppress the Nanite deforming OR. [S23, S24, S17, S4] |
| `Static` | Adds suppression of updated-transform invalidation; add/remove still invalidates. Does **not** suppress the Nanite deforming OR; inappropriate as a promise that animated near shadows will freeze correctly. [S23, S21, S4] |

Lead syntax for inspecting/changing the component enum, **not a recommended wind solution**:

```python
comp.get_editor_property("shadow_cache_invalidation_behavior")
comp.set_editor_property("shadow_cache_invalidation_behavior", unreal.ShadowCacheInvalidationBehavior.AUTO)
# RIGID, STATIC, ALWAYS are the other enum entries.
```

The property is inherited from `UPrimitiveComponent` (`Classes/Components/PrimitiveComponent.h:372`) and its native enum is in S23. Python enum spelling is expected from generated bindings but was not executed in the editor.

Epic's [UE-328823](https://issues.unrealengine.com/issue/UE-328823) confirms that Nanite skeletal meshes still invalidate under Rigid; the public entry was unresolved with target fix 6.0 when checked. Its affected-version list names 5.6/5.6.1, so it is not itself proof of 5.8.3 behavior; the local shader is that proof. Epic support reproduced the issue in the [associated forum thread](https://forums.unrealengine.com/t/nanite-skeletal-meshes-invalidate-vsm/2666444). Later user reports about procedural vegetation with wind disabled are anecdotal and not a substitute for a Metal test. [S4]

### Exact shadow knobs and applicability

| Cvar / property | Source default | Effect / applicability |
|---|---:|---|
| `r.Shadow.Virtual.Cache.DeformableMeshesInvalidate` | `1` | Enables CPU `HasDeformableMesh()` invalidation in Auto. Setting `0` does not remove Nanite's GPU deformation OR; global diagnostic with other skeletal shadow correctness implications. [S24, S4] |
| `r.Shadow.Virtual.ResolutionLodBiasDirectional` | `0.0` | `+1` halves linear directional shadow resolution; reduces redraw work at quality cost without stopping animation. Applies broadly, not only far or moving trees. [S5] |
| `r.Shadow.Virtual.ResolutionLodBiasDirectionalMoving` | `0.0` | Resolution bias for a **moving directional light**; interpolates to ordinary bias as light stops moving. Irrelevant to this static-sun wind distinction. [S5] |
| `r.Shadow.Virtual.Clipmap.WPODisableDistance` | `1` | Allows clipmap-based WPO disable, using primitive `WorldPositionOffsetDisableDistance`. Not a skeletal-animation control. [S5:99, S18:26] |
| `r.Shadow.Virtual.Clipmap.WPODisableDistance.LodBias` | `3` | Extra clipmap levels permitting shadow WPO past visible animation range; source suggests 2–4. Still WPO only: no skinning flag check. [S5:106, S26, S18] |
| `r.Shadow.Virtual.MarkCoarsePagesDirectional` | `2` | Performance mode suppresses dynamic geometry invalidations in coarse pages. `1` always marks coarse levels; `0` disables coarse marking. Already defaults to performance mode, so check actual runtime before expecting savings. [S5:142] |
| `r.Shadow.Virtual.CoarsePagePixelThresholdDynamicNanite` | `4.0` | Dynamic Nanite instances with smaller estimated footprint are excluded from coarse pages; raising to `8` is an optional trial with loss of small coarse shadow contributors. Not a fine-page distance-shadow cutoff. [S27] |
| `r.Shadow.Virtual.Clipmap.FirstLevel` / `.LastLevel` | `6` / `22` | Coverage/resolution range of directional clipmaps, doubling range per level. Reducing LastLevel is a global coverage cap, not a near/far wind policy. [S5:57; Epic VSM docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine) |

Defaults above are **registration defaults**, not queried runtime values. `Engine/Config/BaseScalability.ini:258` and `:296` set directional bias to `-1.5` in higher-quality shadow tiers, while lower tiers use `0` at `:147`, `:182`, `:220`. Thus first query the current value; a trial from `-1.5` to `-0.5` is a one-step resolution reduction, while setting `0.5` would be two steps. Project text search found only `r.Shadow.Virtual.Enable=1` in `Forest/Config/DefaultEngine.ini:7` among the searched wind/VSM patterns; editor/runtime overrides remain unknown.

There is no verified distinct `r.Shadow.Virtual.*` skeletal-animation-disable-distance setting in the inspected VSM cvar declarations. Skeletal animation uses the primary-view screen-size decision for both visible and shadow skinning. WPO's clipmap cutoff is a separate mechanism. Reducing SMRT ray counts targets shadow projection/filtering, not the measured ShadowDepths redraw source. `r.Shadow.RadiusThreshold` and the directional light's CSM Dynamic Shadow Distance / far-shadow culling are not general Nanite tree distance controls; Epic specifies the relevant CPU/distance-field alternatives for non-Nanite geometry. [S3, S4, S18; Epic VSM docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine)

## 3. What PCG/Biome Core can actually set

PCG's `FPCGSoftSkinnedMeshComponentDescriptor` inherits `FSoftSkinnedMeshComponentDescriptor`, whose base exposes `InstanceMinDrawDistance`, `InstanceStartCullDistance`, `InstanceEndCullDistance`, `bCastShadow`, `bCastDynamicShadow`, `bCastHiddenShadow`, `bEvaluateWorldPositionOffset`, `WorldPositionOffsetDisableDistance`, `NanitePixelProgrammableDistance`, `DetailMode`, and `ComponentClass`; the derived descriptor has `TransformProvider`. **Neither `AnimationMinScreenSize` nor `ShadowCacheInvalidationBehavior` is present**. `InitComponent` copies the listed fields but neither missing field. [S6, S7, S22]

`SkinnedMeshComponentPropertyOverrides` resolves against that descriptor, not any arbitrary component property. It partitions points by override values, then applies a descriptor per partition. Adding a string target `AnimationMinScreenSize` or `ShadowCacheInvalidationBehavior` therefore cannot reach the otherwise real inherited component property in stock PCG. [S28; Epic spawner API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/PCG/UPCGSkinnedMeshSpawnerSettings)

Biome's installed `Content/Core/BiomeCore_SpawningLoop.uasset` contains `SkinnedMeshSpawner`, `PCGSkinnedMeshSpawnerSettings`, `SkinnedMeshComponentPropertyOverrides` and targets `bCastShadow`, `InstanceStartCullDistance`, `InstanceEndCullDistance`, `bCastDynamicShadow`, `bCastHiddenShadow`, `bEvaluateWorldPositionOffset`, `DetailMode`, `TransformProvider`. Evidence: `strings '/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/Experimental/PCGBiomeCore/Content/Core/BiomeCore_SpawningLoop.uasset' | rg 'Skinned|Shadow|CullDistance|TransformProvider|AnimationMin|PropertyOverrides|EvaluateWorld|DetailMode'` printed those names and no animation-screen-size or invalidation target. Binary string inspection does **not** prove the exact live graph wiring or current project override values; the lead must inspect the graph for that.

For a persistent per-species threshold, the lead can reapply the reflected component setter after generation or use a custom component class with that default; `ComponentClass` is in the descriptor, and stock descriptor initialization does not overwrite `AnimationMinScreenSize`. A C++ descriptor extension would need the new fields threaded through init/copy/hash/equality; none was made here. These are implementation proposals, not tested solutions. The global cvar avoids this work when all relevant components retain zero. [S6, S7, S8, S28]

`InstanceEndCullDistance` culls the **tree**, not just wind or shadow. The scene proxy returns min/end draw range when end distance is positive, and Nanite uses it for visibility. Start distance is described as fade start in the component header, but smooth material fading of these particular skinned Nanite assets is unverified. Do not present cull distances as an independent shadow-distance feature. [S1:91, S29]

## 4. Ranked choices and concrete lead trials

Ranking is recommended trial order, balancing likely ShadowDepths saving with visual cost, not measured performance.

1. **Raise the animation cutoff; retain far cached bind-pose shadows.** Expected substantial saving if many shadow-contributing trees cross the cutoff; low-to-moderate visual cost (less distant wind, possible pose transition). Start global `0.2`; use per-component tuning for different tree sizes if needed. This directly removes the GPU deformation invalidation cause without removing trees or their shadows. [S2, S3, S4, S19]
2. **Remove far shadow casters using separate spatial component groups.** Potentially the greatest saving, but high visual cost (loss of canopy shadow/distant silhouette contribution). Use `far_comp.set_cast_shadow(False)` only for a genuinely separate far group; component setting cannot remove shadows from only distant instances in a mixed component. No stock independent per-instance shadow disable distance was verified. Camera-following distance bands/group switching would be additional implementation work, with transitions/hysteresis required as a design choice. PCG can partition on `bCastShadow`, but its attributes must supply the grouping; a fixed generation-time band will not follow a moving camera automatically. [PrimitiveComponent.h:1965, S6, S28, S3]
3. **Reduce directional VSM resolution one bias step.** Expected moderate-to-large saving in a dense forest if shadow rasterization dominates, with reduced near and far shadow detail; wind is unaffected. Query current bias and raise it by `1`, e.g. `-1.5` → `-0.5`, or `0` → `1`. It reduces required resolution rather than curing invalidation. [S5, BaseScalability.ini:258]
4. **Coarse-page performance/culling trials.** Likely smaller or zero incremental saving if defaults are already active. Ensure `MarkCoarsePagesDirectional=2`; optionally test `CoarsePagePixelThresholdDynamicNanite=8`. Assess coarse/fog shadow loss. These do not solve fine-page wind invalidation. [S5:142, S27]
5. **Cull entire far trees.** Potentially large saving in shadows and visibility, but greatest scenery cost unless a distant representation replaces them. For an explicit trial, `comp.set_editor_property("instance_start_cull_distance", 25000)` and `comp.set_editor_property("instance_end_cull_distance", 30000)` (cm; proposed values). Persist via descriptor properties/PCG overrides, not just regenerated component edits. Verify actual transition and shadow behavior in editor. [S1, S7, S29]
6. **Rejected as fixes:** `Rigid`/`Static`, `Cache.DeformableMeshesInvalidate=0`, reducing DynamicWind amplitude/speed, CPU update-rate optimization, or WPO distance knobs for bone wind. No expected dependable saving from these alone on the verified active Nanite deformation path; some can produce incorrect shadows or diminish near wind. [S3, S4, S12, S24, S18]

### Ready-to-run Python for the lead

Run through the lead's editor Python mechanism; **these lines were researched, not executed**. Explicit component setters are reflected in source. Python conversion of reflected Unreal names follows normal bindings but must be confirmed by the installed editor if any attribute raises an error. [S1:331, PrimitiveComponent.h:1965]

```python
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cmd = lambda s: unreal.SystemLibrary.execute_console_command(world, s)

# Query console output before changing settings; save the printed baselines.
cmd("r.Skinning.DefaultAnimationMinScreenSize")
cmd("r.Shadow.Virtual.ResolutionLodBiasDirectional")
cmd("r.Shadow.Virtual.MarkCoarsePagesDirectional")
cmd("r.Shadow.Virtual.CoarsePagePixelThresholdDynamicNanite")

# First trial: only zero-valued components inherit this.
cmd("r.Skinning.DefaultAnimationMinScreenSize 0.2")

# On a selected/generated forest component, explicit per-component alternative:
# comp.get_editor_property("animation_min_screen_size")
# comp.set_animation_min_screen_size(0.2)
# Restore component to global behavior:
# comp.set_animation_min_screen_size(0.0)

# Independent resolution trial, assuming queried baseline was -1.5:
# cmd("r.Shadow.Virtual.ResolutionLodBiasDirectional -0.5")

# Optional independent coarse trial:
# cmd("r.Shadow.Virtual.MarkCoarsePagesDirectional 2")
# cmd("r.Shadow.Virtual.CoarsePagePixelThresholdDynamicNanite 8")

# Separate far component only, if that grouping already exists:
# far_comp.set_cast_shadow(False)
```

For persistence after a successful trial, the lead can set `r.Skinning.DefaultAnimationMinScreenSize=0.2` under `[SystemSettings]` in the project's config, or establish an equivalent console-variable preset. That is a proposed application route; no configuration was modified and runtime precedence must be checked after reopen. Per-component changes must survive PCG regeneration via the chosen post-generation/default mechanism. [S2, S7, S28]

The verification request to the lead is narrow: same static sun and supplied inside-forest camera, allow caches to settle, compare baseline with `0.2` using the existing GPU profiler and VSM Cached Page/ShadowCasters visualization; then move across the cutoff and check pose pops/double shadows. Inspect component thresholds to confirm the cvar applies. Restore baseline before testing resolution/coarse changes separately. No saving in ms is claimed until that test. Epic documents the cached-page and caster visualization and notes that bounds size and geometry changes drive invalidation. [S19; Epic VSM docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine)

## Source index

All paths below are relative to **`/Users/Shared/Epic Games/UE_5.8/Engine/`**. A citation such as S3 means the file and line below; cited adjacent logic was read with `nl -ba` / `sed` and symbol searches with `rg`. Full class/descriptor declarations were inspected for absence claims. No unlisted worker briefs/reports were read.

- S1: `Source/Runtime/Engine/Classes/Components/InstancedSkinnedMeshComponent.h:63` (provider), `:85` (animation semantics), `:91` (draw/cull), `:116` (socket bones / GPU LOD), `:293` (provider functions), `:331` (animation setter).
- S2: `Source/Runtime/Renderer/Private/Skinning/SkinningSceneExtension.cpp:105` (provider enable), `:113` (animation threshold cvar).
- S3: `Shaders/Private/Nanite/NaniteSkinningUpdateViewData.usf:138` (skinned filter, thresholds, views, radius/distance inequality and mask).
- S4: `Shaders/Private/Nanite/NaniteClusterCulling.usf:734` (active skinning), `:754` (VSM deformation OR).
- S5: `Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapClipmap.cpp:42` (directional biases), `:57` (levels), `:99` (WPO cvars), `:142` (coarse mode), `:251` (moving-light bias interpolation).
- S6: `Source/Runtime/Engine/Classes/Animation/AnimBank.h:370` (base descriptor through :490), `:494` (hard descriptor through :535), `:538` (soft descriptor through :579).
- S7: `Source/Runtime/Engine/Private/Animation/AnimBank.cpp:1771` (base component init), `:1908` / `:1981` (derived init).
- S8: `Source/Runtime/Engine/Private/Components/InstancedSkinnedMeshComponent.cpp:1190` (setter marks render state dirty).
- S9: `Source/Runtime/Engine/Private/SkinningSceneExtensionProxy.cpp:195` (provider creation / reference-pose fallback).
- S10: `Source/Runtime/Engine/Private/Components/InstancedSkinnedMeshComponent.cpp:50` (ForceRefPose default/recreate callback).
- S11: `Plugins/Experimental/DynamicWind/Source/DynamicWind/Public/DynamicWindData.h:9` (entire data class); `Private/DynamicWindData.cpp:30` (batching), `:50` (slice selection).
- S12: `Plugins/Experimental/DynamicWind/Source/DynamicWind/Private/DynamicWindProvider.cpp:30` (all cvars through :63), `:107` (shader parameters), `:154` (skeleton batching registration), `:508` (global speed/amplitude and shader time).
- S13: `Plugins/Experimental/DynamicWind/Source/DynamicWind/Public/DynamicWindParameters.h:10` (complete parameter struct).
- S14: `Plugins/Experimental/DynamicWind/Source/DynamicWind/Private/DynamicWindSubsystem.cpp:24` (enable read-only default and subsystem creation).
- S15: `Source/Runtime/Engine/Private/InstancedSkinnedMeshSceneProxy.h:30` (Nanite proxy), `:77` (threshold getter), `:86` (non-Nanite proxy), `:138` (GPU LOD).
- S16: `Source/Runtime/Engine/Private/SkinningSceneExtensionProxy.cpp:18` (bone transform storage/maps); `Classes/Components/InstancedSkinnedMeshComponent.h:116` (sockets).
- S17: `Source/Runtime/Engine/Private/PrimitiveSceneProxy.cpp:823` (Rigid/Static material invalidation flag).
- S18: `Shaders/Private/VirtualShadowMaps/VirtualShadowMapPageCacheCommon.ush:11` (material invalidation), `:26` (WPO clipmap test), `:94` (static-cache decisions).
- S19: `Shaders/Private/VirtualShadowMaps/VirtualShadowMapCacheGPUInvalidation.usf:65` (per-instance/view masks, transition state, hysteresis TODO and double-shadow comment).
- S20: `Shaders/Private/VirtualShadowMaps/VirtualShadowMapPageOverlap.ush:334` (static-transition rendering).
- S21: `Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapCacheManager.cpp:565` (removed/updated/added handling and primitive instance range), `:2056` (scene updates).
- S22: `Plugins/PCG/Source/PCG/Public/MeshSelectors/PCGSkinnedMeshDescriptor.h:29` (inheritance); `Private/MeshSelectors/PCGSkinnedMeshDescriptor.cpp:11` (Static mobility), `:31` (base initialization).
- S23: `Source/Runtime/Engine/Public/SceneTypes.h:220` (complete enum); `Private/Components/PrimitiveComponent.cpp:347` (Auto default).
- S24: `Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapCacheManager.cpp:110` (cvar default), `:1281` (Auto deformable path and range).
- S25: `Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapCacheManager.cpp:2048` (Always collection).
- S26: `Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapClipmap.cpp:404` (WPO threshold calculation).
- S27: `Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapArray.cpp:504` (coarse thresholds); `Shaders/Private/VirtualShadowMaps/VirtualShadowMapPageOverlap.ush:362` (detail-geometry test, dynamic Nanite branch).
- S28: `Plugins/PCG/Source/PCG/Public/Elements/PCGSkinnedMeshSpawner.h:73` (override field); `Private/MeshSelectors/PCGSkinnedMeshSelector.cpp:129` (descriptor validation/partition/application).
- S29: `Source/Runtime/Engine/Private/InstancedSkinnedMeshSceneProxy.cpp:17` (min/end range); `Shaders/Private/Nanite/NaniteCullingCommon.ush:427` (visibility distance test).
- Additional corroboration: `Shaders/Private/VirtualShadowMaps/VirtualShadowMapBuildPerPageDrawCommands.usf:273` repeats the deformation invalidation OR.
