# Moss on animated beech bark: evidence and recommended design

Research date: 2026-10-11. Scope: the UE 5.8.3/Mac/Metal/Nanite/software-Lumen/VSM setup supplied in the brief. Recommendation below is a proposed design, not an editor-tested implementation.

**Use an opaque bark–moss material blend, with coverage anchored to the tree's pre-skinned reference pose and moss sampled through stable mesh UVs. Add authored coverage controls; reserve actual moss geometry for close-up silhouettes.** Epic documents pre-skinned coordinates for locally aligned effects and warns that world-projected textures swim on animated objects. [E4, E5]

**Electric Dreams used custom dynamic blending materials, Megascans-derived textures, and art-directed PCG assemblies. The exact moss-on-bark graph, moss material/function names, parameters, RVT wiring, and dedicated moss scatter remain unverified.** Ben Wilson's firsthand production account establishes a shared dynamic blending system; the official PCG documentation establishes assemblies. Neither establishes a particular moss implementation. Joseph James explicitly says his later Substrate moss experiment did not make it into Electric Dreams. [E2, A1, A3]

## 1. What Electric Dreams actually establishes

| Candidate technique | Evidence and confidence |
| --- | --- |
| Custom layered/blending materials | **Verified generally.** Production contributor Ben Wilson describes dynamic blending materials, supporting textures based heavily on Megascans data, procedural albedo work, efficient blend masks, and a material/texture set shared across assets that reacts to its environment. His page does not specify graph nodes, parameter names, or which inputs make a surface mossy. [A1] |
| Landscape auto blend | **Verified generally.** Jack McKelvie says his landscape auto blend material and assemblies made the final demo. He also says the background PCG forest and microscatter work pictured on his page did not. Those images cannot establish the final project's moss scatter. [A2] |
| PCG assemblies | **Verified.** The official exporter preserves meshes, materials, transforms, tags and hierarchy. Named tools include `PCGUtility_LevelToPCG`, `SG_CopyPointsWithHierarchy`, and `ApplyHierarchy`; source/PCG assets are documented at `/PCG/Assets/PCGAssemblies`. The hierarchy example includes trunks and branches. These are assembly tools, not moss material functions. [E2] |
| World-aligned/triplanar moss blend | **Unverified for Electric Dreams.** A plausible implementation, but not stated in the reviewed production accounts or PCG documentation. General Quixel documentation supports world-aligned blending; that does not establish its use in this sample. [A1, E2, Q1] |
| Vertex-color moss painting | **Unverified for Electric Dreams.** Quixel's historical blend workflow supports vertex-color controls, but no reviewed Electric Dreams source identifies the moss channel or proves it was painted onto tree bark. [Q1, A1] |
| Runtime Nanite tessellation/displacement | **Unverified for Electric Dreams.** Current documentation distinguishes offline static displacement from experimental runtime tessellation. It does not establish either as a moss method in the original UE 5.2 sample. Do not use a current engine feature list to explain a 2023 asset. [E6, E7] |
| PCG-scattered moss meshes/cards | **Unverified.** Assemblies and clutter placement are documented, but moss-specific scatter assets, density masks, and settings are not established. PCG placement alone does not create a moss shader. [E2, A2] |
| RVT-based rocks/ground blend | **Unverified for this sample.** Wilson's phrase “react to the environment” does not identify RVT. Reviewed Epic CEDEC slides describe ground generation, rocks, clover, puddles and wet decals, not a confirmed moss RVT graph. [A1, E3] |
| Substrate moss/cloth fuzz | **Specific proposed experiment excluded.** Joseph James describes a tiling moss surface on a 3D Megascan using Substrate cloth response and custom breakup; he says there was no time to include it in Electric Dreams. Epic's SIGGRAPH 2023 slides explicitly say the GDC demo shipped with Substrate enabled across the board. That establishes framework use, not this specific moss experiment or a moss graph. The sample overview highlights the opal example. [A3, E1, E14] |

**Trees versus rocks:** reviewed sources do not provide an asset-by-asset moss attribution. The defensible answer is that environmental material blending and assemblies were used, but which trunks/rocks/logs received baked scan moss, procedural moss, or separate geometry is **unverified**. Even visually convincing moss in a screenshot cannot identify its implementation. [A1, A2, E2; evidentiary limitation]

**Exact moss asset/function names and parameters:** none verified. Do not invent names such as `MF_Moss` or claim that familiar generic Megascans masters were necessarily the sample's production shader. Verified sample locations useful to the lead are `/Game/Levels/ElectricDreams_Env`, `/Game/Levels/PCG/Breakdown_Levels/ElectricDreams_PCGLargeAssembly`, and the documented assembly directory above. [E1, E2]

To settle this, the lead should inspect representative mossy rock, standing trunk, and fallen-log material instances in the original sample; record full object paths, parent chains, function dependencies, switches, textures and parameter values. Check `RuntimeVirtualTextureSample/Output`, `VertexColor`, projection functions, displacement settings, mesh sections and PCG spawner meshes. Export graph/property evidence through the lead's editor tools. No sample/editor access was performed by this worker. [Method proposal; editor restriction: `/Users/tp/code/ue-forest/AGENTS.md:7`]

## 2. General UE5 practice, with version and performance distinctions

- **Material coating:** blend base color, roughness and normals using a separate coverage mask. Generic Quixel precedent is a blend master supporting up to three texture sets, world-aligned blend, fuzzy shading, layer controls, and vertex painting. Its UE4 documentation demonstrates moss as the top layer, R/G controls for lower layers and B for water; these are historical Quixel conventions, not PVE or Electric Dreams parameter contracts. [Q1]
- **Projection:** world projection is useful for static rocks and terrain-scale continuity. For animated bark use authored UVs or pre-skinned local projection. Inverse-transforming the animated world position to object space removes the rigid object transform; it does not undo skeletal deformation. This last statement follows from the distinct pre/post-deformation positions in the installed Nanite shader. [E4, E5, L2]
- **Coverage:** treat slope as a prior, not the whole growth mask. A vertical trunk has little upward normal, so a slope-only design suppresses trunk-side patches. Combine a base-height envelope, optional directional bias, irregular coverage, and authored inclusion/exclusion. This is a design inference from the dot-product mask, not an ecological claim. Baked cavity/AO/height data may bias breakup, but is not a moisture measurement. [Design inference; underlying normal/position inputs: E5]
- **Vertex colors:** asset vertex colors support Nanite; per-component instance vertex painting is not supported by the cited tool documentation. Do not promise individual-tree painting through that workflow. Preserve existing PVE vertex data until its use is inspected; choose an additional UV mask or an explicitly unused channel instead. [E10; preservation recommendation]
- **Normal/detail relief:** a normal map gives shading detail, not silhouette or fiber volume. `DetailTexturing` and `HeightLerp` are documented generic functions. Height blending adjusts the transition; it is not geometric displacement. [E4; distinction/design inference]
- **Geometry:** selective opaque tufts or a modeled moss shell can supply close-up thickness. Artist Chris Evry demonstrates tightly packed cards made with ZBrush Fibermesh, separate rock/moss material slots, Two Sided Foliage shading and dithered alpha. Label this as an independent artist technique, not Epic practice or a Nanite forest performance result. [A4]
- **Nanite cost:** masked-out pixels still cost nearly as much as drawn pixels; Epic recommends geometry over masked cards for Nanite foliage. Dense overlapping fibers remain aggregate geometry and can create overdraw. Nanite does not remove texture sampling or shader cost. [E7, E8; final statement is cost-model inference]
- **Displacement:** runtime tessellation is experimental; it creates new triangles and needs a corresponding shading normal. Large displacement magnitude hurts culling and VSM performance, and seams can crack. Current documented switches are `r.Nanite.AllowTessellation`, `r.Nanite.Tessellation`, material Enable Tessellation, Magnitude, Center, and pixel-size Displacement Fade. None are a verified Electric Dreams moss parameter. Metal plus this project's skinned Dynamic Wind path was not tested; do not assume compatibility from static-mesh examples. [E7; unverified-platform qualification]
- **Decals:** Nanite can receive projected decals. Decal cost depends strongly on screen coverage and material complexity. A projected decal lives in its projector coordinates; attaching the projector to the tree follows its rigid transform, not all branch skinning, so use decals mainly for static rocks/logs or nearly stationary bases. For moving branches prefer UV material masks. [E6, E11; attachment recommendation is geometric inference]
- **RVT:** useful as an optional static contact-blending system: sample ground color/normal and, if authored, world height near rock/log intersections. It supplies terrain context, not fibers or a complete trunk UV mapping. Epic classifies animated/skinned objects as poor RVT **writers** because this is a shading cache; this does not prohibit sampling a static terrain RVT on a tree. [E12; contact design inference]
- **Lumen:** UE 5.8 docs now describe skeletal Surface Cache support using six cards around pre-skinned bounds, with limited animated coverage. Software ray-tracing geometry support and Surface Cache material capture are separate concerns; a fine moss normal does not establish off-screen fiber occlusion. View-dependent material logic can capture incorrectly. Keep coverage camera-independent; fading only microdetail is safer. [E13; fine-detail/fade recommendation is inference]
- **VSM:** changing color/roughness in an opaque coating adds no geometry motion or opacity-mask work. Wind and additional animated tuft geometry can invalidate cached shadow pages; extra casters increase rendering work. Compare Shadow Depths and cached/invalidated pages, not only frame rate. [E9; coating cost comparison is inference]

Secondary artistic precedent: Marco de Goeij's forest breakdown uses detail maps and upward blending on rocks, matching ground textures across rock and landscape materials, and distance blending of texture scale. It illustrates art-directed continuity without proving RVT or Electric Dreams implementation. [A5]

## 3. Proposed node-level design for this project

Everything in this section is **our proposed design**, not recovered Epic moss code. Node semantics are supported by E4/E5 and the installed UE sources L1–L3. Names/defaults below are newly proposed parameters.

### Keep the PVE bark path intact

Extend a project-owned copy of the applicable bark branch/function, or inject the blend at its material-attributes stage. Preserve the existing tree's UV interpretation, normal packing, color/roughness controls and any data-dependent wind behavior. Do not change leaf sections to the bark moss material. The local audit script names PVE `MA_Foliage_Trees` and `Wind_TransformProvider`; this verifies project dependencies, not the full material graph. [Local `/Users/tp/code/ue-forest/scripts/asset-budget.py:8`]

Read-only file enumeration found `MI_European_Beech_Bark_01`, `T_European_Beech_Bark_01_C`, `T_European_Beech_Bark_01_NAH`, and the floor/patch textures below. The packed bark NAH channel meanings and `_B-O` opacity channel must be confirmed from the material graph/import metadata; filenames are insufficient evidence. [Command: `rg --files Forest/Content | rg -i 'moss|bark'`, executed 2026-10-11]

### Inputs and stable coordinates

1. Obtain reference position `P0` using **Local Position → Local Origin: Pre-Skinned Instance**; obtain `N0` using **Pre-Skinned Local Normal**. UE 5.8 deprecates the older PreSkinnedPosition node. The header describes the pre-skinned position as vertex-only and incompatible with conventional GPU Skin Cache; route the required values through Vertex Interpolator/Customized UVs for pixel use and test on the Nanite path. [L1, L3]
2. Prefer passing only `P0.z` plus `dot(N0,U0)` if UV-based noise is adequate. Pass `P0.xyz` only for local 3D noise/projection. Normalize the interpolated normal before using it if the full normal is passed. This is a bandwidth/ALU design choice.
3. `U0=(0,0,1)` is tree-local up for a normally oriented tree. For a tilted static log, supply gravity transformed into the object's rest space as a constant per placement. Do not recompute moss coverage from the current wind-deformed normal each frame. This keeps deposited coverage attached to the reference surface.
4. Start with a verified continuous bark UV channel for moss sampling: `UVm = UVb * MossUVScale + MossUVOffset`. Keep UV metric and seams under review. XY-only projection stretches on vertical trunks. Full local triplanar is an optional quality tier for seams/roots, not the default for every tree.

Installed Nanite code stores `PointLocal` and `PreSkinnedNormal` before applying skinning and sends those values to the material vertex parameters. This supports the rest-pose strategy; it does not replace a Metal compile and wind visual check. [L2]

### Coverage graph

Use SmoothStep, DotProduct, Subtract, Multiply, Max, Saturate and Lerp nodes. Suggested starting values are art-tuning guesses in local centimeters.

```text
z = P0.z - RootZOffset
Slope = SmoothStep(UpStart=0.15, UpFull=0.65, Dot(normalize(N0), U0))
Base  = 1 - SmoothStep(BaseFullCm=15, BaseEndCm=120, z)
Region = Max(Base * BaseWeight=0.7, Slope * SlopeWeight=0.4)

Noise = authored/baked low-frequency texture sampled in stable UVs
        OR scalar local noise from P0 / NoiseScaleCm=60
Patch = verified opacity/coverage channel of Tileable Moss Patches
        sampled in stable UVs with its own scale
Cavity = optional baked cavity bias; neutral value if not available

Score = Region + NoiseStrength * (Noise-0.5)
        + PatchStrength * (Patch-0.5) + CavityStrength * Cavity
AutoMask = SmoothStep(CoverageThreshold-EdgeWidth,
                      CoverageThreshold+EdgeWidth, Score)
Mask = Saturate(Lerp(AutoMask, AuthoredCoverage, AuthoredOverride)
                * MossAmount * (1-AuthoredExclude))
```

Set `MossAmount=0` for genuinely bare variants. Retain the `Max` union: `Base * Slope` would unnecessarily exclude vertical lower trunks. Allow authored patches above the base where the automatic envelope fails. Supply a stable per-instance seed/offset from the actual PCG/skinned-instance data interface once the lead verifies which interface is supported; do not promise `PerInstanceRandom` or Custom Primitive Data works identically on every instanced-skinned provider.

Optional side-direction coverage uses `dot(N0, PreferredSide0)` with a soft threshold, combined with authored coverage. It is an art control, not a universal “north side” rule. Optional height breakup uses `HeightLerp`'s Alpha for **all** attributes, not color alone. Keep its endpoints checked so Mask 0 is entirely bark and Mask 1 entirely moss. [Function contract: E4]

### Texture and shading outputs

Prefer a clean bark-appropriate moss surface/atlas; preview the current assets before choosing. `Mossy Forest Floor` may include ground debris, and suitability for bark is **unverified** until the lead views it. `Tileable Moss Patches` is a decal set, so confirm alpha handling/background and use its actual coverage rather than treating its RGB background as a continuous moss material. Observed available texture names include `T_vfylbge_2K_B/N/ORM/T` and `T_sfdnqii_2K_B-O/N/ORM`; channel interpretation is not verified. [Same file-enumeration command above]

```text
BaseColor = Lerp(BarkColor, MossColor * MossTint, Mask)
Roughness = Lerp(BarkRoughness, Clamp(MossRoughness * RoughnessScale), Mask)
Metallic = 0
Normal = Normalize(Lerp(BarkNormalTS, MossNormalTS, Mask))
```

Treat normalized normal interpolation as the initial replacement blend; use an established angle-corrected normal function when layering microdetail within each surface. A world/local triplanar normal must be reoriented into its projection basis and then the animated shading basis; simply feeding a local normal into a world-normal function is insufficient. UV-based tangent normals avoid this added implementation complexity. Preserve modest underlying bark relief where the coating is thin. Do not multiply arbitrary extra AO into base color to make moss “deep.”

Keep opaque bark opaque: the moss mask blends attributes and does **not** feed Opacity Mask. Avoid forcing the whole bark material into foliage/subsurface/cloth shading to get fuzz. Substrate fuzz can be investigated separately for a hero asset; it is not required for the base forest material, and James's experiment is not Electric Dreams evidence. [A3; proposed scope choice]

### Cost and quality tiers

These are analytical texture-fetch estimates, not GPU measurements: a UV moss B/N/ORM set adds three samples, plus one if coverage uses a separate texture. Sampling all three maps on three projection planes gives approximately nine moss samples before coverage/detail; two-plane variants reduce that. Runtime blends generally evaluate both texture sets even where Mask is zero. A distance Lerp fades appearance but does not, by itself, guarantee texture work disappears.

Use baked mask textures over expensive procedural noise at forest scale, keep close detail optional, and use static switches or separate material quality variants to remove unused features. Never fade broad moss coverage into bare bark with distance. Fade fine normal/fuzz/tufts while retaining average color and roughness. Profile fixed views with/without moss at equal resolution, wind, lights and streaming state. Have the lead inspect Nanite overdraw, VSM pages/Shadow Depths, Lumen Surface Cache, and shader cost on Metal. [Noise expense: E5; diagnostics: E8/E9/E13; design proposal]

### Rocks and logs

Reuse the same coating logic with object-local or world-up slope as appropriate. Static rocks can use world triplanar for consistent scale and optional RVT color/height contact blending. Use selective opaque Nanite tufts/baked geometry for close-up thickness, decals for local stains, and PCG/assemblies to place supporting ground litter. A log rotated onto its side requires gravity in its rest space; a fixed local Z mask would still treat its original crown direction as up. Any animated log/branch moss geometry must share compatible skin weights/provider behavior rather than merely being attached to the root. [Proposed adaptations; E4/E12/L2]

## 4. Verification still required from the lead

- Exact Electric Dreams graph/asset evidence described in section 1.
- Compile the proposed interpolated rest-pose inputs on the actual skinned Nanite/Metal material. Test strong wind, multiple tree variants, tilted/scaled placements and transitions into distant Nanite representations; ensure noise/coverage sticks.
- Inspect bark packing, current UVs/vertex-channel usage, and moss texture content. Confirm provider-supported per-instance variation before committing to a control interface.
- Compare material-only versus selective geometry at the closest intended camera distance. Measure base shading, VSM and overdraw separately. No numerical performance promise is possible without that scene test.

These are implementation verification requests, not checks run by the research worker. No editor, MCP, build, gate, asset save, install, commit or project code modification was performed.

## Sources

Primary Epic/Quixel sources:

- **E1:** [Electric Dreams sample overview and levels](https://dev.epicgames.com/documentation/en-us/unreal-engine/electric-dreams-environment-in-unreal-engine); [Epic project breakdown](https://www.unrealengine.com/electric-dreams-environment).
- **E2:** [Procedural Content Generation in Electric Dreams](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-in-electric-dreams).
- **E3:** [Epic Games Japan, CEDEC 2023 Electric Dreams PCG slides](https://www.docswell.com/s/EpicGamesJapan/5VVJXV-UE5_CEDEC2023_ElectricDreams), particularly slides 29 and 36. [Associated official talk](https://youtu.be/934CmNbEy0E). Slides reviewed as text; video not watched/transcribed.
- **E4:** [Texturing Material Functions](https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine).
- **E5:** [Vector Material Expressions](https://dev.epicgames.com/documentation/en-us/unreal-engine/vector-material-expressions-in-unreal-engine).
- **E6:** [Nanite Virtualized Geometry](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine).
- **E7:** [Working with Nanite-Enabled Content](https://dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content).
- **E8:** [Nanite Technical Details](https://dev.epicgames.com/documentation/unreal-engine/nanite-technical-details).
- **E9:** [Virtual Shadow Maps](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine).
- **E10:** [Paint Vertex Colors](https://dev.epicgames.com/documentation/en-us/unreal-engine/paint-vertex-colors-tool-in-unreal-engine).
- **E11:** [Decal Materials](https://dev.epicgames.com/documentation/en-us/unreal-engine/decal-materials-in-unreal-engine).
- **E12:** [Runtime Virtual Texturing](https://dev.epicgames.com/documentation/en-us/unreal-engine/runtime-virtual-texturing-in-unreal-engine).
- **E13:** [Lumen Technical Details](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine).
- **E14:** [Epic, SIGGRAPH 2023 Substrate presentation](https://advances.realtimerendering.com/s2023/2023%20Siggraph%20-%20Substrate.pdf), PDF page 82. Downloaded to `/tmp/mossresearch/substrate-2023.pdf`; Apple PDFKit extraction with `swift /tmp/mossresearch/extract-slides.swift` printed the explicit GDC Substrate statement.
- **Q1:** [Quixel Megascans Bridge Unreal Integration manual, PDF pages 4–5](https://d3uwib8iif8w1p.cloudfront.net/bridge/plugins/Megascans_Bridge_Unreal_Integration.pdf). Historical UE4 workflow, not a current PVE contract.
- **Q2:** [Quixel Megaplants: European Beech listing](https://www.fab.com/listings/cefe5722-9c31-4aa2-9ee2-e5426610d5e6?lang=en), describes PVE presets and Dynamic Wind skeletal-mesh compatibility; no moss parameter documented.

Firsthand contributor statements hosted on ArtStation; label separately from official documentation:

- **A1:** [Ben Wilson, Electric Dreams material/shader contribution](https://benwilson.artstation.com/projects/WB6YLG).
- **A2:** [Jack McKelvie, Electric Dreams PCG/material/assembly contribution](https://jackm.artstation.com/projects/DvmwAO).
- **A3:** [Joseph James, Substrate Moss](https://josephjames.artstation.com/projects/xDmRmR).

Secondary artist breakdowns:

- **A4:** [Chris Evry, Soft Velvet Moss Rocks UE5](https://katanalevy.artstation.com/projects/JeA43D). His inferred Horizon implementation is not verified here.
- **A5:** [Marco de Goeij, Magical Forest](https://www.marcodegoeij.com/magical-forest-in-ue5). Historical project; displacement discussion is not current UE 5.8 guidance.

Installed Epic UE 5.8 source, read-only inspection, primary evidence:

- **L1:** `/Users/Shared/Epic Games/UE_5.8/Engine/Source/Runtime/Engine/Public/Materials/MaterialExpressionLocalPosition.h:28` (vertex-only Pre-Skinned Instance); `/Users/Shared/Epic Games/UE_5.8/Engine/Source/Runtime/Engine/Private/Materials/MaterialExpressions.cpp:20764` (position deprecation) and `:20801` (normal tooltip).
- **L2:** `/Users/Shared/Epic Games/UE_5.8/Engine/Shaders/Private/Nanite/NaniteVertexDeformation.ush:37` and `:96` (rest values retained before skinning); `/Users/Shared/Epic Games/UE_5.8/Engine/Shaders/Private/Nanite/NaniteVertexFactory.ush:244` (material vertex parameters receive them).
- **L3:** `/Users/Shared/Epic Games/UE_5.8/Engine/Source/Runtime/Engine/Private/Materials/HLSLMaterialTranslator.cpp:6129` (Local Position Pre-Skinned Instance emits PreSkinnedPosition).

Additional primary media located, with limits:

- [Electric Dreams: From an Idea to a Demo, Unreal Fest 2023](https://www.youtube.com/watch?v=ZkbKXIsqF60): official description emphasizes vehicle physics/water and touches PCG/Substrate; video not watched or transcribed, no moss inference drawn.
- [Inside Unreal, Electric Dreams deep dive announcement, June 22 2023](https://forums.unrealengine.com/t/inside-unreal-deep-dive-into-the-electric-dreams-environment-sample-project/1206358): verifies presenters and session scope, not moss implementation.
- [Electric Dreams Environment: Unpacked course](https://dev.epicgames.com/community/learning/courses/x3L/unreal-engine-electric-dreams-environment-unpacked): page yielded no readable lesson content in this browser; no node-level moss attribution drawn.
- [Quixel Trees interview](https://magazine.artstation.com/2022/11/quixel-megascans-trees/): Quixel-team statements describe older Trees shader controls, quality tiers and simple/pivot-painter wind; these do not describe the current PVE bark moss interface.
- [Quixel 2020 blending blog URL](https://quixel.com/blog/2020/1/22/blending-megascans-assets-in-ue4) currently redirects to Quixel News, so its original article was not used as evidence.

## Decisions for this project (2026-10-11)

Agreed with the operator after this research:

- **One shared moss coating, not a bark material.** Build a material function (planned name `MF_MossCoating`) used by tree bark, rocks, fallen logs and stumps, so moss is tuned once and stays consistent across the forest.
- **Two sources for "up":**
  - Swaying skinned trees use the rest pose: Local Position with Local Origin = Pre-Skinned Instance, and Pre-Skinned Local Normal, passed through a vertex interpolator. Never the current, wind-deformed normal or world position, or the moss swims. The old PreSkinnedPosition node is deprecated in 5.8.
  - Static rocks, logs and stumps use world up and world position, which is cheaper and lets a fallen log gather moss on whichever side faces the sky.
- **Coverage:** `Region = Max(Base * BaseWeight, Slope * SlopeWeight)` (a union, not a product), plus breakup from the Tileable Moss Patches coverage channel sampled in stable UVs (cheaper than procedural noise across about 7,000 trees), then a soft threshold with an edge width. Add `MossAmount` (0 = bare variant). Normalize the blended normal. Don't fade coverage with distance; fade only fine detail.
- **Moss texture:** start with Mossy Forest Floor. If its twigs and debris read as dirt on bark, get a dedicated clean moss surface from Fab.
- **Timing:** after step 8a places deadwood and rocks with their stock materials (some Megascans logs and stumps may already be mossy), build the coating and apply it to bark, rocks and logs in one tuning pass with everything in view. Then step 8b: saplings, understory and the footpath.
- **Gotchas found while drafting:** the Noise expression's position input pin is `World Position`, not `Position`. The Megaplants bark normal `T_European_Beech_Bark_01_NAH` is a Masks texture: rebuild Z from R/G (`ConstantBiasScale` -0.5 ×2 → `DeriveNormalZ`); B appears to be AO, to be confirmed.
