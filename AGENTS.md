# Agent rules

UE 5.8 C++ project on one Mac, coordinated by Niles. Decisions behind these rules: [UE 5.8 + Niles MCP working setup](https://github.com/Rhovian/ue-forest/issues/1).

## The editor

- There is one UE editor, opened on the main checkout. **Only the Niles lead uses it**, over MCP at `http://127.0.0.1:8000/mcp` and by running Python in it with `scripts/editor-py` (a file queue under `Saved/EditorPy`, no network).
- The lead's agent family (currently Claude) never runs as a worker or reviewer. Committed MCP client config is in that family's format, so no other agent connects.
- Workers never open, drive or connect to the editor. Anything that needs the editor goes to the lead as a request.

## Code changes

- Workers change C++ and other text in their own `--worktree` checkout and do not build the editor target.
- The lead merges, then runs `scripts/editor.sh restart` (close, `Build.sh … -NoHotReload`, reopen with MCP on 8000). `scripts/editor.sh` also has `open`, `close`, `build` and `hot`.
- Live Coding is Windows-only. When a merge changes only `.cpp` function bodies, the lead may instead hot reload with `scripts/editor.sh hot` while the editor is open. Any header, `UCLASS`/`UPROPERTY`/`UFUNCTION`, or constructor-default change takes the full `restart`, and assets are never saved after a hot reload of such a change.

## Assets and version control

- `.uasset` / `.umap` are LFS binaries and cannot be merged. No LFS locks: the lead and the human take turns, never editing assets at the same time.
- The editor's source control provider stays off; use CLI Git. After moves, renames or redirector fixup, stage `Content` changes together (`git add -A -- Content`).
- LFS objects go to a local `file://` backup via `lfs.url` / `lfs.pushurl`, never to GitHub LFS.
