# Art direction: target-look references

Reference images for what the Forest Biome, the sand shore and the transition between them should look like. The lead compares its `CaptureViewport` review views to these.

## Current direction (operator, 2026-11-08)

The concept art below is out of reach with the assets we have, so the build improvises from what is installed. The references set the mood (an old, deep, shaded forest floor full of life); they are not a checklist, and nothing in this doc overrides the operator's current instructions. When the operator's word and this doc disagree, the operator wins and this doc is updated to match.

- **Electric Dreams is a reference too.** The free Electric Dreams sample environment (Fab, `ElectricDreamsSample_5.8`) is both an asset source and a look reference: its dark shade with sun patches, its mixed floor and its plant density are targets (captures of its hero cameras: `Forest/Saved/Reviews/ed-reference/`, local).
- **Use its plants.** Every Electric Dreams plant is available, tropical ones included, mixed with the plants we already have. Hornbeam and elderberry join the beech.
- **Floor: less grass, denser plant life,** mixed with ground scans, stones, sticks and branches, surface roots and leaf litter. Bare earth, roots and rock are welcome; not every surface has to be green.
- **The terrain stays as it is** for now; dress it, don't reshape it.

## Rules for agents

- **A reference shows intent, not a spec.** Take only what each image's notes say to take. Image models make up plants, props and terrain that no free Fab asset can deliver.
- **Asset limit: free on Fab.** Anything in a reference must be buildable from assets listed Free on Fab (the operator acquires and checks each licence dialog), plus materials, lighting and Niagara. Already-installed assets are a subset, not the limit. A subject with no free listing is ignored, not faked.
- **Every reference has notes** (see the template at the end): what to take, what to ignore, and 2–4 observable targets.
- **Reference names match review views** (#30) and harness points (`scripts/measure/baseline.py`): `interior`, `canopy_up`, `beach`, `lake_shore`, `high_point`, plus `edge_in`, `edge_out`, `clearing`, `stream_bank`.
- Images live in `docs/art-direction/<view>_NN.png` (LFS).

## Target look

Old-growth European beech forest in high summer, deep and enclosed, green and full of life (not green on every surface: bare earth, roots and rock are fine, operator 2026-11-08), with moss on roots, logs, rocks and the lower trunks, ivy climbing the bark, fern colonies under the trees. It feels enchanted from **light and atmosphere, not props**: low mist in hollows, sun shafts through gaps with pollen and dust motes glowing in them, dew on the moss, soft green bounce light, backlit translucent leaves, slightly heightened saturation, and accents of blue and violet: drifting light wisps and scattered bluebells and violet woodland flowers (operator, 2026-11-06). No glowing plants or creatures. The forest ends at a narrow pale sand beach through a ragged band of thinner trees, with bleached fallen trunks lying on the sand.

Decided (operator, 2026-11-06): magic level **2, Enchanted**; the sand biome is the **beach strip only** (no dunes or heath).

Decided (operator, 2026-11-06), forest edge: **an abrupt living edge with a debris band on the sand.** Closed beech forest within ~5–10 m of the sand, on a low eroded bank with root flares, ferns and moss (`edge_in_01`); the transition is carried by deadwood on the sand: driftwood, fallen branches and a few bleached trunks, densest at the forest foot and thinning toward the water (`edge_in_03`). Along the coast the edge varies (operator likes `edge_in_04` and `edge_in_05`): the abrupt edge with debris band is the default; some stretches open into a grassy meadow fringe with scattered big beech before the closed forest (`edge_in_04`); and a few lone, large beech stand out on the beach itself, roots on the sand, some at the waterline (`edge_in_05`).

Ground transition (operator, 2026-11-06): a hard material change at a vertical bank face was tried and rejected; the ground should blend from sand into forest floor softly.

Not yet tuned (operator, 2026-11-06): the enchanted look is not consistent across the references (the shore shots lost it). Treat the colour and enchantment in the references as provisional; tune it later with lighting, grade and particles (#35 and the wisp system).

## Shared prompt pieces

Camera, matching the walker (eye 1.6 m, UE default 90° horizontal FOV):

```
eye-level view from 1.6 m, wide 18mm lens, natural perspective
```

Style suffix, appended to every prompt:

```
enchanted storybook atmosphere, small drifting wisps of soft blue and violet light, floating pollen and dust motes glowing in the sun shafts, scattered bluebells and violet woodland flowers, dew on the moss, slightly heightened saturation, photorealistic, Megascans-quality nature photography, Unreal Engine 5 realism, Lumen-like soft bounce light, high dynamic range, no people --ar 16:9 --style raw
```

Exclusions (Midjourney `--no`) — only things with no asset or not wanted in this build:

```
--no conifers, pine, spruce, birch, palm trees, hanging moss, sand dunes, stone path, stairs, ruins, buildings, fence, people, animals, glowing plants, glowing mushrooms, fairies, snow, autumn colors
```

Why each is excluded, so the list can change when a reason does:

| Excluded | Reason |
|---|---|
| conifers, birch, palm trees | beech is the main tree, with hornbeam and elderberry (operator, 2026-11-08, superseding the #9 beech-only ruling); Electric Dreams understory plants, small palms included, are allowed on the floor |
| hanging moss | #9 puts it in a later layer; no free asset verified (`forest-lushness.md` §6) |
| sand dunes | ruling 2026-11-06: beach strip only |
| glowing plants, glowing mushrooms, fairies | ruling 2026-11-06: Enchanted, not Fantasy |
| stone path, stairs, ruins, buildings, fence | no built structures; the footpath is a vegetation-free corridor |
| people, animals | wildlife out of scope (#9) |
| snow, autumn colors | #9: summer |

Subjects already installed (safe to name; anything else must have a free Fab listing): *European beech (smooth grey bark, high domed crowns), beech fern, English ivy, white wood anemone, low glossy-leaved shrubs, mossy fallen trunks, old mossy stumps, flat pale limestone slabs, red-capped white-spotted mushrooms, brown bolete mushrooms, dry brown beech leaf litter, thick green moss floor, rocky pale sand.*

## Shots

Each prompt is the shot text, then the style suffix, then the `--no` list. Prompts below are the versions actually run on 2026-11-06; `[--no + x]` means the shared list plus x. `--sref` names the reference image used as style.


| View | What it decides | Tickets |
|---|---|---|
| `interior` | understory density, colonies, moss continuity | #31 #32 #34 |
| `canopy_up` | canopy closure and gaps | #31 |
| `clearing` | gap shape, sapling regeneration, light shafts | #31 #35 |
| `stream_bank` / `lake_shore` | damp-ground lushness by water | #32 |
| `edge_in` | transition seen from the beach | shore thinning, floor material |
| `edge_out` | transition seen from inside the forest | shore thinning, #35 |
| `transition_ground` | sand → litter → moss blend on the ground | `forest_floor.py` |
| `beach` | the beach strip | floor material, shore assets |
| `nurse_log`, `rock_assembly` | children of logs and rocks | #32 |
| `high_point` | overall read of forest vs sand at distance | all |

### interior

```
Inside an ancient old-growth European beech forest in summer, eye-level view from 1.6 m, wide 18mm lens. Massive smooth grey beech trunks with moss climbing their roots and lower bark, English ivy spiralling up some trunks. Dense colonies of beech fern knee-high between trunks, patches of white wood anemone, thick unbroken green moss over the ground and over fallen logs, brown beech leaf litter showing between colonies. Closed canopy overhead, soft green light, thin mist between the far trunks, a few sun shafts. [style suffix] [--no]
```

### canopy_up

```
Looking straight up from the forest floor of an old-growth European beech forest in summer, wide 18mm lens. Tall smooth grey trunks converging, overlapping layers of backlit translucent green beech leaves almost closing the sky, a few small bright gaps, ivy on the trunks. [style suffix] [--no]
```

### clearing

```
A small natural clearing in an old-growth European beech forest where an old tree has fallen, eye-level view from 1.6 m, wide 18mm lens. The huge moss-covered fallen trunk lies across the clearing, dense young beech saplings and ferns filling the light gap, warm morning sun shafts falling through mist onto the moss, dark enclosed forest all around. [style suffix] [--no]
```

### stream_bank

```
A narrow clear stream winding through an old-growth European beech forest in summer, eye-level from 1.6 m on the bank, wide 18mm lens. Banks thick with bright green moss and dense beech fern, exposed mossy beech roots at the waterline, pale limestone slabs in the water coated in moss, low mist over the water, dappled light. [style suffix] [--no]
```

### lake_shore

```
The edge of a small still forest lake inside an old-growth European beech forest, eye-level from 1.6 m, wide 18mm lens. Mossy banks and fern colonies down to the water, a mossy fallen beech trunk half in the lake, beech crowns reflected in the dark water, mist lying on the surface, soft morning light. [style suffix] [--no]
```

### edge_in (sand → forest, looking inland)

```
Standing on a narrow pale sand beach of a small Baltic island looking inland at the edge of an old-growth European beech forest, eye-level from 1.6 m, wide 18mm lens. A strip of sand 10 to 20 m wide with a few bleached, weathered fallen beech trunks lying on it, then straight into a ragged forest edge of grey beech trees with exposed roots at the sand line, a few ferns and moss creeping onto the sand at the edge, the forest getting denser and darker behind into deep green shade with moss, ferns and bluebells. Calm summer morning, mist hanging inside the forest, soft sun shafts between the edge trees, small drifting ribbons of soft blue and violet light only inside the shade of the forest, glowing pollen motes, enchanted storybook atmosphere, slightly heightened saturation, [style suffix] --sref <interior_01> [--no + cliffs, pier, boat]
```

### edge_out (forest → sand, looking out)

```
From inside a dark mossy old-growth European beech forest looking out toward a bright narrow sand beach and calm Baltic sea, eye-level from 1.6 m, wide 18mm lens. Foreground of thick moss, beech ferns, bluebells and white wood anemone in deep green shade, then a low eroded bank with exposed beech roots at the forest edge, then a tangled band of bleached driftwood, fallen branches and weathered logs piled on the sand at the foot of the trees, thinning to scattered pieces toward the water, grey beech trunks framing the bright opening. Light spilling in from the sea side, mist drifting between the edge trunks, small drifting ribbons of soft blue and violet light in the shade of the foreground only, glowing pollen motes in the light, [style suffix] --sref <interior_01> [--no + cliffs, pier, boat]
```

### transition_ground (material reference)

```
Close ground-level view of where an old-growth beech forest slowly takes over a narrow Baltic beach, camera 1.6 m high looking down at 45 degrees, wide lens. The ground rises in a gentle mossy slope, no step or cliff. Warm pale sand at the bottom with blown beech leaves and twigs, then sand and forest floor interleaving over two to four metres: fingers of green moss creeping out onto the sand, beech roots snaking across the sand half buried, patches of brown leaf litter and sand mixed together, small ferns and the first bluebells and white wood anemone colonizing the sandy ground, then thick hummocky moss, ferns and flowers under the trees. Natural irregular boundaries, islands of moss on sand and pockets of sand inside the moss, no straight lines. Soft morning light, faint mist, gentle enchanted atmosphere, [style suffix] --sref <edge_out_01> <interior_01> [--no + cliff, bank, step, vertical edge, path]
```

### beach (sand strip)

```
A narrow quiet sand beach on a small Baltic island in summer, 10 to 20 m wide, eye-level from 1.6 m, wide 18mm lens, looking along the shore. Warm pale rocky sand, wet and darker at the waterline, dry higher up, scattered small pebbles and a few flat pale limestone stones, a band of bleached driftwood, fallen branches and weathered beech logs along the top of the beach, densest at the foot of the forest and thinning toward the water. At the back of the beach the ground rises in a gentle slope where tongues of moss, mossy roots and leaf litter creep out onto the sand, and the dark wall of an old-growth beech forest rises behind, one large lone beech standing out on the sand with its roots spread. Calm sea, soft morning haze, mist drifting out of the forest edge, gentle enchanted atmosphere, [style suffix] --sref <edge_out_01> [--no + cliff, step, beach grass, pier, boat, umbrella]
```

### nurse_log

```
Close view of a huge fallen beech trunk in an old-growth forest, eye-level from 1.6 m, wide 18mm lens. The trunk is fully coated in thick moss, small beech seedlings and ferns growing out of its top, red-capped white-spotted mushrooms and brown boletes along its side, ferns crowded around its base, leaf litter piled where it meets the ground. [style suffix] [--no]
```

### rock_assembly

```
A pale flat limestone slab half buried in an old-growth beech forest floor, eye-level from 1.6 m, wide 18mm lens. Moss growing over its top and edges, ivy creeping across it, beech fern and small plants packed around its base, leaf litter in its cracks. [style suffix] [--no]
```

### high_point

```
Aerial view from 60 m above a small low island in the Baltic Sea at early morning, looking across it at an angle. Dense old-growth beech forest canopy covering most of the island in rich layered greens, a few small clearings, a narrow stream winding to the sea and a small dark forest lake, low mist pooling in the hollows and drifting out of the forest. All round, a narrow strip of pale sand beach with a band of bleached driftwood along the forest foot, the forest edge closed and abrupt along most of the coast, opening in a few places into a small grassy meadow fringe with scattered big beech, and a few lone large beech standing out on the sand. Calm sea, soft low sun, faint blue and violet haze in the mist, gentle enchanted storybook atmosphere, photorealistic, Unreal Engine 5 realism, high dynamic range --ar 16:9 --style raw --sref <interior_01> <edge_out_01> --no conifers, pine, spruce, birch, palm trees, sand dunes, cliffs, roads, paths, buildings, boats, pier, people, snow, autumn colors
```

## Process

1. **Lock the palette first.** Generate `interior`. Pick the image whose colour and light you like best and use it as `--sref <url>` on every other shot, so the set reads as one place.
2. **4–8 runs per shot.** Pick 1–2 and commit them with notes.
3. **Real photos for the transition.** Add one or two real reference photos: Baltic beech forest meeting the beach (Vilm, Jasmund, Darßer Weststrand's wind-bent shore trees). Image models are weakest at believable transitions.
4. **Change one thing at a time** (time of day, mist strength) and keep the rest of the prompt fixed, so differences between images mean something.

## Magic level

**Enchanted (decided).** It is already in the style suffix. Its parts and what builds them:

- Mist in hollows, sun shafts, deep shade, saturation: fog, exposure and grade (#35)
- Glowing motes in the shafts and blue/violet wisps: a Niagara particle system (new work, not on the map yet)
- Blue/violet flowers: free Fab plant listings (bluebell, violet or similar), see gaps
- Dew and wet sheen on moss: the moss coating and floor material (#34, `forest_floor.py`), used sparingly

Not in scope: glowing plants or mushrooms, oversized trees, creatures (#9 keeps fantasy elements for a later layer).

## Gaps to fill from free Fab listings

The references will show things the installed set lacks. Each one is a #33 search for a free listing, not something for agents to fake. If no free listing exists, the fallback is noted.

- bleached, weathered fallen trunks for the sand. The two driftwood listings checked (2026-11-06) are paid. Fallback: the installed fallen trunks with a bleached, moss-free material variant
- edge beech variants with exposed roots. Fallback: new PVE exports from the free Megaplants European Beech (Beech A–D are upright forest trees)
- a second fern and shrub silhouette (one mesh each today). Candidates: Lady Fern (`forest-lushness.md` §6). Megaplants Common Hazel would be a strong shrub layer, but it is a second species, so it needs a #9 ruling
- moss clumps with height (the floor moss is a flat material). Candidates: Mossy Forest Boulder (§6). Nordic Forest Ledge Moss was tried and rejected: it reads as pale stone plates (#32), and was removed (#68); no free cushion-moss listing was found (#33)
- blue and violet woodland flowers (bluebell, violet or similar) for the enchanted colour accents
- grass for the meadow-fringe stretches of coast (`edge_in_04`, `high_point_01`)
- surface roots: mossy beech roots running across the floor and onto the sand (`transition_ground_02`); Beech A–D root flares end at the ground
- sparse beach grass at the top of the sand, if wanted (not excluded; needs a free listing)

## Open questions for the operator

- **Bank at the sand line:** soft slope everywhere (as `transition_ground_01`), or a low bank in places (as `edge_in_01`, `edge_out_01`)?
- **Second species:** Megaplants Common Hazel for the shrub layer (`clearing_02`) against #9's beech-only ruling.
- **Lone shore trees:** an exception to the Trees group's shore filter (`edge_in_05`, `beach_01`).
- **Wisps:** a ticket for the Niagara wisp and mote system (`clearing_01` shows the look).
- **Enchanted tuning:** the shore references are plain daylight; tune the whole set later with #35.

## Reference notes template

```
### <view>_NN.png — <source: Midjourney prompt link or photo credit>
- Take: <e.g. fern colonies ~knee high, covering most of the floor between trunks; moss continuous up root flares>
- Ignore: <e.g. the conifers at the back; the path; the glow>
- Targets: <2–4 observable checks, e.g. "sky ≤ 15% of canopy_up frame", "no bare floor patch wider than ~3 m in interior", "forest edge ~20–40 m deep from sand to closed canopy">
```

## References

Picked by the operator, 2026-11-06. Style reference for every shot after the first: `interior_01`.

### interior_01.png — Midjourney, prompt `interior` (revised with blue/violet), top-right of grid
- Take: the palette and light for the whole set (cool greens, blue/violet accents, soft mist between far trunks); moss climbing the root flares about 1–2 m up the trunk; ivy wrapping some trunks whole; fern colonies knee-high between trunks; mounded moss over the ground and over low logs; white anemone and bluebell patches as accents, not a carpet.
- Ignore: the very pale, almost white bark on the near trunk (beech is mid-grey); the tight, even trunk spacing in the background.
- Targets: almost no bare leaf litter in the near 10 m of the `interior` view; moss continuous from the floor onto every root flare; blue/violet accents visible but green still dominant.

### canopy_up_01.png — Midjourney, prompt `canopy_up`, image 1 of 2
- Take: canopy mostly closed with a few bright gaps; upright forking beech trunks; ivy climbing whole trunks; blue haze and motes in the light behind the trunks.
- Ignore: the fake signature text along the bottom edge.
- Targets: sky visible in at most ~15% of the `canopy_up` frame (60° pitch); several trunks ivy-covered to the crown.

### clearing_01.png — Midjourney, prompt `clearing`, image 3
- Take: the sapling patch filling the light gap thickly (beech saplings, knee-to-chest height); the **wisp look**: low ribbons of blue mist threading through the saplings near the ground, not orbs; a fully moss-coated fallen trunk with flowers and ferns crowding its base; sun shafts in the background.
- Ignore: the canopy, which is not visibly open here (take canopy from `canopy_up_01`); the anemone carpet's density, which is denser than `interior_01`'s accents.
- Targets: saplings densest where the canopy is open; Niagara wisps read as low, soft, blue mist ribbons at about knee height.

### clearing_02.png — Midjourney, prompt `clearing`, image 4
- Take: the **shrub layer**: one broad, airy leafy mass waist-to-head high filling the gap, with open floor around it; a fallen trunk in two pieces with a gap between them; bluebells in patches.
- Ignore: the lack of wisps (take those from `clearing_01`).
- Targets: shrubs as a few broad masses, not an even scatter. The installed Huckleberry Oak is lower and denser; this silhouette is closer to Hazel (second species, needs a #9 ruling).

### stream_bank_01.png — Midjourney, prompt `stream_bank`
- Take: green right down to the waterline on both banks, no bare mud; pale limestone slabs in the water with moss caps only on their tops; dense bluebell and anemone banks with strappy bluebell leaf clumps; mist hanging over the stream upstream; stream narrow enough to step across.
- Ignore: the giant tangle of moss-covered roots in the left foreground (no asset makes this; at most, small exposed roots where trunks meet the bank); the watermark text along the bottom edge; the absence of wisps (take from `clearing_01`).
- Targets: no bare bank wider than ~1 m along the stream; slabs in and beside the water use the moss coating on their top faces only; flowers densest on the banks (damp ground), sparser away from water.

### lake_shore_01.png — Midjourney, prompt `lake_shore`, image 1 of 3
- Take: fern colonies and mounded moss running straight into the water; a moss-coated fallen trunk lying half in the lake; low mist sheet on the surface with reflections still readable; wooded far shore close enough to see; bluebells and anemone on the near bank; faint blue motes over the water.
- Ignore: nothing major.
- Targets: lake reads as small (far shore visible from the `lake_shore` view); no bare bank; one or more deadwood pieces crossing the shoreline into the water (check whether the lake exclusion currently keeps deadwood off the shoreline; if so, this needs a shore-crossing rule).

### lake_shore_02.png — Midjourney, prompt `lake_shore`, image 3 of 3
- Take: a moss-covered rock or mound standing in shallow water (Mossy Forest Boulder candidate); moss banks meeting the water edge directly.
- Ignore: the oversized near-camera flowers.
- Targets: occasional mossy rocks in the shallows near the shore.

### edge_in_01.png — Midjourney, prompt `edge_in`, image 1 of 4
- Take: an **abrupt edge**: closed beech forest begins right at the sand, with no wide thinning band; a low eroded bank (about 0.5–1 m) at the sand line with moss, ferns and bluebells on top and root flares spilling onto the sand; dark misty interior visible between the edge trunks; bleached, branchy driftwood scattered on the sand; mist drifting along the shore.
- Ignore: the beach colour palette, which is cooler and plainer than the forest (correct: the enchanted colour stays inside the forest); the very pale bark.
- Targets: sand → closed canopy within ~5–10 m, not 20–40 m (operator ruling below: replaces the current 20–40 m shore-thinning bands); a visible step or bank at the sand line, if banks are kept (open question below; terrain, not placement: relevant to #37); driftwood pieces every few metres along the strip.

### edge_in_02.png — Midjourney, prompt `edge_in`, image 2 of 4
- Take: the straight-on read of the edge from the beach: sand, then a continuous fern band about knee-to-waist high along the foot of the trees, then trunks, then dark interior; a large bleached fallen trunk with its root plate on the sand.
- Ignore: the spindly, near-white, partly dead-looking trunks (Beech A–D are healthy forest trees); the even, wall-like canopy line.
- Targets: an unbroken fern/understory band at the forest foot; at least one big bleached trunk with root plate on the beach strip.

### edge_in_03.png — Midjourney, prompt `edge_in` (gradual-thinning variant), image 4 of 4
- Take: **the debris band**: a dense tangle of driftwood, bleached logs and fallen branches piled at the forest foot, thinning to scattered pieces toward the waterline; mist along the shore; dense forest close behind.
- Ignore: the dead snags standing in the surf and along the beach; the blue sky and hard daylight (enchantment is tuned later); the bright pale trunks.
- Targets: the debris band runs the length of the beach strip, densest within a few metres of the trees; pieces vary from twigs to whole trunks; the living forest edge itself stays abrupt (see `edge_in_01`).

### edge_in_04.png — Midjourney, `edge_in` gradual-thinning variant, image 1 of 4
- Take: a stretch of coast where the sand meets a **grassy meadow fringe** with moss, ferns and bluebells, scattered tall beech standing apart, and fallen logs lying across the grass, before the closed misty forest; mist pooling at the forest wall.
- Ignore: the watermark text in the bottom corners; the blue sky and hard light (enchantment is tuned later); the very pale trunks on the left.
- Targets: used on some stretches of shore, not everywhere; the fringe is grass and moss, not bare litter (needs a free Fab grass); fallen logs on the fringe, not only in the forest.

### edge_in_05.png — Midjourney, `edge_in` gradual-thinning variant, image 3 of 4
- Take: **lone, large beech standing out on the beach**, roots spread over the sand, one right at the waterline with mossy roots; branchy driftwood piled at the forest foot.
- Ignore: the watermark text along the bottom; the blue sky.
- Targets: a few lone shore trees along the coast, well spaced; their root flares spread over the sand. This needs an exception to the Trees group's shore filter, which today removes every tree below the shore height.

### edge_out_01.png — Midjourney, prompt `edge_out`, image 3 of 4
- Take: **exposure across the edge**: deep green foreground shade and bright sea and sky both readable, neither crushed nor blown (reference for #35); the layers in order: hummocky moss, ferns, bluebells and anemone in shade → the bank top → a ~0.5–1 m eroded bank face with a root mat → a strip of sand → the debris band → sea; mist drifting between the edge trunks; a few rocks in the shallows.
- Ignore: how tall and wall-like the debris pile is (keep it a low band, as in `edge_in_03`); the sea fading into a white sky at the horizon.
- Targets: from inside the forest the sea is visible through the edge trunks, framed, not as a wide open view; if a bank is kept (open question below), its face reads as a dark step, not a pit; the moss runs right to the bank lip.

### transition_ground_01.png — Midjourney, prompt `transition_ground` (soft blend), image 3 of 4
- Take: **the soft ground transition**: no step; sand and forest floor interleave over a few metres: tongues and islands of moss out on the sand, patches of brown beech litter mixed into the sand, mossy roots snaking across the sand from the edge trees, blown leaves and twigs on bare sand; hummocky moss, ferns, anemone and bluebells taking over under the trees; a mossy low rock at the sand edge; mist toward the sea.
- Ignore: nothing major.
- Targets: sand → forest floor over ~2–4 m of noisy interleaving (moss islands on sand, sand pockets in moss), never a straight line; litter mixes with sand rather than sitting as its own band; scattered leaves and twigs on the sand for several metres out.

### transition_ground_02.png — Midjourney, prompt `transition_ground` (soft blend), image 2 of 4
- Take: moss-covered surface roots running from the trunks out across litter and onto sand; moss hummocks with height at the tree bases; bluebells and anemone in clumps at the edge of the moss.
- Ignore: the near-white bark on the background trunks.
- Targets: edge trees have visible surface roots reaching onto the sand (gap: Beech A–D root flares end at the ground; needs a free root asset or decal/mesh); moss relief (hummocks), not only flat moss (gap: moss clumps with height).

### beach_01.png — Midjourney, prompt `beach`, image 1 of 2
- Take: a narrow sand strip curving along the shore; the debris band of driftwood and branches piled at the forest foot, with moss and litter creeping onto the sand under it; **one lone large beech standing out where the beach curves**, its roots on the sand at the waterline; flat pale limestone stones scattered on wet sand and in the shallows; mist lying along the coast.
- Ignore: the blue sky and hard daylight (enchantment tuned later); the bushy, shrubby edge in front of the forest wall.
- Targets: beach narrow enough that the forest wall dominates the view; lone shore trees rare and placed at points or curves where they read against the sea; limestone stones clustered at the waterline, not spread evenly.

### beach_02.png — Midjourney, prompt `beach`, image 2 of 2
- Take: the view the other way along the strip; the debris band continuous along the forest foot; a lone beech with spreading roots at the forest edge; pale stones scattered on dry sand; mist along the shore.
- Ignore: the exposed soil bank face on the right (the ground transition is soft; whether any bank exists is still an open operator question); the blue sky.
- Targets: the debris band reads continuous along the whole beach; stones on dry sand sparse, larger clusters near the water.

### nurse_log_01.png — Midjourney, prompt `nurse_log`, image 4 of 4
- Take: **the nurse-log assembly and its density**: a huge trunk fully coated in thick, hummocky moss; 3–5 beech seedlings and a few ferns spaced along its top; one or two mushroom clusters (red spotted plus brown boletes) on its side low down; a fern at the broken, splintered upper end; ferns, bluebells and anemone crowding its base; leaf litter piled where it meets the ground; a sun shaft across it.
- Ignore: the mushrooms growing out of the log's side as a shelf (the installed mushrooms are ground species; place them at the log's base or on its top).
- Targets: per large log, roughly 3–5 seedlings on top, 1–2 mushroom clusters, ferns at the ends and along the base, a litter pile at ground contact; moss coats the whole top and upper sides (moss coating, world up).

### nurse_log_02.png — Midjourney, prompt `nurse_log`, image 1 of 4
- Take: the upturned root plate standing at one end with ferns growing out of it; mushrooms clustered at ground level against the log; ferns spilling over the log's base onto the floor.
- Ignore: nothing major.
- Targets: some large logs carry a root plate (a log variant or a stump child at one end) with ferns on it.

### rock_assembly_01.png — Midjourney, prompt `rock_assembly`, image 2 of 4
- Take: a pale limestone slab beside a beech whose root runs up against it; **cushion moss with real height** covering about two thirds of the top, bare stone showing on the sides and one end; ivy spilling over one corner; leaf litter caught between the slab and the root on its uphill side; beech ferns, bluebells and anemone packed tight around the base; a few bluebells rooted in the moss on top.
- Ignore: nothing major.
- Targets: moss coating covers most of each slab's top face, little of its sides (world up, as decided in `moss-techniques.md`); the cushion relief needs geometry (moss clump meshes as children on top faces; gap: moss clumps with height); some slabs placed against tree roots; ferns and flowers as base children with no bare ring around the stone.

### high_point_01.png — Midjourney, prompt `high_point`, image 1 of 4
- Take: **the whole-island read**: unbroken canopy over most of the island; the beach a thin pale ribbon all round with a continuous debris band at the forest foot; the edge abrupt along most of the coast; one stretch opening into a small grassy meadow fringe with a couple of lone big beech; the stream mouth cutting the beach; a dark lake inside the forest; mist in drifting patches over low ground, not a blanket.
- Ignore: the meadow's size (keep meadow stretches smaller than this); the blue daytime sky.
- Targets: beach ≪ forest in area; meadow stretches are exceptions (a few short stretches of coast); lone shore trees sit at the meadow or at points, not along the whole coast.

### high_point_02.png — Midjourney, prompt `high_point`, image 3 of 4
- Take: the stream winding through the forest from the lake to the sea, with forest closing over it; the debris band reading as a continuous line along the whole beach.
- Ignore: the large meadow; the stream's width (the level's is a 4 m channel).
- Targets: from above, the stream is mostly hidden under canopy, visible in short stretches.
