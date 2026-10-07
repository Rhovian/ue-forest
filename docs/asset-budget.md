# Asset Budget (feasibility phase)

The rules every asset must meet before a Forest Biome may place it. Decided in [#14](https://github.com/Rhovian/ue-forest/issues/14) from the measurements in [#13](https://github.com/Rhovian/ue-forest/issues/13).

## Scope

- **Caps, not frame-time gates.** These rules cap what is expensive to change later. Frame time is measured for every asset with `scripts/measure/run.sh` and recorded, but gates nothing until the optimization phase.
- **Measuring machine:** the target Mac (M2 Max), PIE in a 1920×1080 window, software Lumen, Epic scalability. The low-end PC target is decided when optimization starts.
- **Reference density:** about 150 trees per hectare.

## Rules for every asset

| Rule | Requirement |
|---|---|
| Nanite | Every mesh is Nanite. An exception needs a measured reason. |
| Opacity | Opaque or masked. Masked only on leaf and twig materials. No translucency. |
| Textures | At most 4096. Virtual texturing above 2048. Displacement maps up to 4096×8192 when shared across a species. |
| Bones | Skinned trees have at most 400 bones; reduce with PVE Bone Reduction at export. |
| Collision | Simple trunk collision only; no branch or leaf collision. Skinned trees: PVE physics asset, Trunk Only. Static trees: a simple capsule. |
| Plugin content | Master material and Wind Driver are used from PVE plugin sample content. Recheck them after each engine upgrade; copy them into the project only if an upgrade breaks them (Advanced Copy refuses engine-plugin content, so a copy needs a reference-remapping tool). |
| Wind | Every tree sways. Skinned spawns carry the `DynamicWindData` transform provider (PCG property override: the spawners drop it from the template). Each level has one Wind Driver. |
| Distant foliage | Nanite shape preservation: Voxelize, pending a visual comparison with PreserveArea and None. |

## What makes the cut

- **Species:** European Beech (Megaplants). Ground, rock and debris fill-ins inherit the rules above and get their own caps when chosen.
- **Tree Variants:** A, B, C, D from `PVE_European_Beech_01`. C (388 bones) and D (198) pass as shipped. A (1,113) and B (1,052) are re-exported under 400 bones; a variant whose sway looks wrong after reduction is dropped.
- **Quality tiers:** none yet; defined with the low-end target.
- **Variation:** the four variants, plus random yaw and uniform scale 0.8–1.2 in PCG. More PVE variants (via the Scale node) only if the forest looks repetitive.

## Deferred to optimization

- Frame-time gates and a low-end PC spec (including whether Windows is in scope).
- No wind on far trees.
- Tightening the bone cap toward 200.
