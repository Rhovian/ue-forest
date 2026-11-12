# Agent rules

UE 5.8 C++ project on one Mac, coordinated by Niles. Decisions behind these rules: [UE 5.8 + Niles MCP working setup](https://github.com/Rhovian/ue-forest/issues/1).

## The editor

- There is one UE editor, opened on the main checkout. **Only the Niles lead uses it**, over MCP at `http://127.0.0.1:8000/mcp` and by running Python in it with `scripts/editor-py` (a file queue under `Saved/EditorPy`, no network). The lead opens the editor itself when a task needs it (`scripts/editor.sh open`) and calls MCP with `scripts/editor-mcp`, which does not depend on the session's MCP client having connected at startup.
- Diagnose a failed or hung editor call with `scripts/editor.sh status` and the editor log before anything else. Do not use a workaround until the cause is known.
- Workers and reviewers may be of any family, including the lead's. The committed `.mcp.json` reaches the editor from any Claude checkout, so the next rule is what keeps workers off it.
- Workers never open, drive or connect to the editor. Anything that needs the editor goes to the lead as a request.
- Work that is judged in the editor (PCG tuning, placement, materials, lighting, anything judged by how it looks) is done by the lead directly, editing scripts and assets itself, in short change-and-look loops. It is not handed to a worker. The editor is single-threaded over MCP, so the lead is this project's main worker. Workers take only work they can verify without the editor, such as offline scripts or C++ with tests.

## Planning

- The operator's current instructions come first. docs/art-direction.md (its "Current direction" section, then the references) sets the mood the level aims for; the references are not a checklist, and a doc line never overrides what the operator has asked for. When they disagree, follow the operator and update the doc to match.
- The lead settles choices the operator hasn't spoken to, guided by the doc, including grilling issues, research choices and the doc's open questions. It records each on its issue in neutral wording, never quoting the operator, as "Lead ruling (date): …" or "Operator decision (date): …".
- Going against a recorded operator decision is a departure: the lead labels the issue `needs-operator`, says what and why, and works on other issues until the operator rules. The references' "Ignore" lists are guidance, not decisions.
- Work that spans several decision areas (for example canopy, ground cover, palette, moss) is split into separate issues before it starts.
- Assets are limited to free Fab listings (docs/art-direction.md). When a reference needs one that is not installed, the lead opens an issue labelled `operator:asset` naming the listing, the export settings and the target `/Game` path, uses the documented fallback meanwhile, and moves on.

## Running autonomously

- The lead works #9's open issues without waiting for the operator. Standing authorization: branch, commit, push, open and merge PRs, close an issue once its Done-when is met, spawn and close workers, and commission the reviews below.
- Workers default to the standard tier; when it falls short the lead moves to the frontier secondaries, then the frontier primary, without asking.
- The lead interrupts the operator only for an asset with no fallback, when every remaining issue is `needs-operator`, for a risk to repo or LFS data, or for a build or editor failure it cannot fix.
- Fab imports: the lead commits and closes the editor before handing it over; the operator imports, commits with `git add -A -- Content` and hands it back.

## Visual acceptance

- Each review view is judged against the reference of the same name. The lead reports, per view, which Targets are met and which aren’t, not just “looks better”.

- Counts, audits, tests and frame times are not acceptance for anything visible. Before the lead reports a visible change as ready, it captures fixed review views with MCP `CaptureViewport`, before and after the change, looks at them itself, and reports what it saw.
- Captures go to `Forest/Saved/Reviews/<issue>/<view>_{before,after}.png` (local, not committed) so any agent can read them.
- Before a visible change is reported ready, a reviewer of another family compares the after captures with the references and their Targets. Reading PNGs is not using the editor, so any worker can do it.
- Captures use the existing level and the existing time-of-day controls (`Forest.Time`, `Forest.Pause`); no separate test maps.

## Code changes

- Each issue lands as a PR from its own branch; the lead merges.
- Code diffs (Python, C++, scripts) and visual changes get a review from another family: at most 3 rounds, the first a full review, later rounds on the diff since the previous round. After round 3 the lead decides any remaining disagreement.
- Workers change C++ and other text in their own `--worktree` checkout and do not build the editor target.
- The lead merges, then runs `scripts/editor.sh restart` (close, `Build.sh … -NoHotReload`, reopen with MCP on 8000). `scripts/editor.sh` also has `open`, `close`, `build` and `hot`.
- Live Coding is Windows-only. When a merge changes only `.cpp` function bodies, the lead may instead hot reload with `scripts/editor.sh hot` while the editor is open. Any header, `UCLASS`/`UPROPERTY`/`UFUNCTION`, or constructor-default change takes the full `restart`, and assets are never saved after a hot reload of such a change.

## Assets and version control

- Enable the staged-content policy checks per clone with `git config core.hooksPath .githooks` (Python lint requires `ruff`: `brew install ruff`).
- `.uasset` / `.umap` are LFS binaries and cannot be merged. No LFS locks: the lead and the human take turns, never editing assets at the same time.
- The editor's source control provider stays off; use CLI Git. After moves, renames or redirector fixup, stage `Content` changes together (`git add -A -- Content`). Stage named paths, never `git commit -a`: while the operator has the editor it sweeps their session files in.
- LFS objects go to a local `file://` backup via `lfs.url` / `lfs.pushurl`, never to GitHub LFS.

## Forest Biome content

- Before adding or tuning a placement group, read `.claude/skills/forest-pcg/SKILL.md` (cost budget, AssetType, children, verification), and append each newly understood PCG failure to it.

- A newly imported asset of any kind passes `scripts/asset-budget.py` (fixed by re-export where needed) before it goes into any placement group or graph.

- Every placed asset kind (trees, logs, stumps, rocks, children of assemblies, plants) is an appendable list of variants in the script that builds it, even when it holds one mesh, so adding a variant is a one-line change.
