# Agent rules

UE 5.8 C++ project on one Mac, coordinated by Niles. Decisions behind these rules: [UE 5.8 + Niles MCP working setup](https://github.com/Rhovian/ue-forest/issues/1).

## The editor

- There is one UE editor, opened on the main checkout. **Only the Niles lead uses it**, over MCP at `http://127.0.0.1:8000/mcp` and by running Python in it with `scripts/editor-py` (a file queue under `Saved/EditorPy`, no network). The lead opens the editor itself when a task needs it (`scripts/editor.sh open`) and calls MCP with `scripts/editor-mcp`, which does not depend on the session's MCP client having connected at startup.
- The lead's agent family (currently Claude) never runs as a worker or reviewer. Committed MCP client config is in that family's format, so no other agent connects.
- Workers never open, drive or connect to the editor. Anything that needs the editor goes to the lead as a request.
- Work that is judged in the editor (PCG tuning, placement, materials, lighting, anything judged by how it looks) is done by the lead directly, editing scripts and assets itself, in short change-and-look loops. It is not handed to a worker. Workers take only work they can verify without the editor, such as offline scripts or C++ with tests.

## Planning

- Research produces choices, not a plan. Before any build starts, the lead puts each open choice from the research and the issue to the operator and records the operator's ruling in the issue. If the approach is still open, nothing is built.
- Work that spans several decision areas (for example canopy, ground cover, palette, moss) is split into separate issues before it starts.
- A departure from the research or from an operator ruling, by anyone, goes to the operator before it is built on.

## Visual acceptance

- Counts, audits, tests and frame times are not acceptance for anything visible. Before the lead reports a visible change as ready, it captures fixed review views with MCP `CaptureViewport`, before and after the change, looks at them itself, and reports what it saw.
- Captures use the existing level and the existing time-of-day controls (`Forest.Time`, `Forest.Pause`); no separate test maps.

## Code changes

- Workers change C++ and other text in their own `--worktree` checkout and do not build the editor target.
- The lead merges, then runs `scripts/editor.sh restart` (close, `Build.sh … -NoHotReload`, reopen with MCP on 8000). `scripts/editor.sh` also has `open`, `close`, `build` and `hot`.
- Live Coding is Windows-only. When a merge changes only `.cpp` function bodies, the lead may instead hot reload with `scripts/editor.sh hot` while the editor is open. Any header, `UCLASS`/`UPROPERTY`/`UFUNCTION`, or constructor-default change takes the full `restart`, and assets are never saved after a hot reload of such a change.

## Assets and version control

- Enable the staged-content policy checks per clone with `git config core.hooksPath .githooks` (Python lint requires `ruff`: `brew install ruff`).
- `.uasset` / `.umap` are LFS binaries and cannot be merged. No LFS locks: the lead and the human take turns, never editing assets at the same time.
- The editor's source control provider stays off; use CLI Git. After moves, renames or redirector fixup, stage `Content` changes together (`git add -A -- Content`).
- LFS objects go to a local `file://` backup via `lfs.url` / `lfs.pushurl`, never to GitHub LFS.

## Forest Biome content

- Every placed asset kind (trees, logs, stumps, rocks, children of assemblies, plants) is an appendable list of variants in the script that builds it, even when it holds one mesh, so adding a variant is a one-line change.
