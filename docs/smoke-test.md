# Smoke test: Niles + MCP + UE 5.8 on Mac

Run 2026-10-05 against the [acceptance checklist](https://github.com/Rhovian/ue-forest/issues/8) as amended in [the issue comment](https://github.com/Rhovian/ue-forest/issues/8#issuecomment-6004862724): project `MyProject` in `MyProject/`, LFS backup and all pushes out of scope.

Environment: macOS 27.0.1, Xcode 26.1.1 (17B100), UE 5.8.3 (CL 58210709), Niles 1.5.0, Claude Code 2.1.285 (lead), codex-cli 0.160.0 (worker `codex:gpt-6.1-sol:medium`).

**Verdict: workable on Mac. All hard steps passed; no Windows fallback.**

| # | Step | Result |
| --- | --- | --- |
| 1 | Xcode ≥ 26.0, not 26.4 | Pass: 26.1.1 |
| 2 | Record UE patch | Pass: 5.8.3, CL 58210709 |
| 3 | C++ project | Pass (amended): `MyProject` in `MyProject/` |
| 4 | Plugins + provider None | Pass: persisted in `MyProject.uproject` (MCP + each All Toolsets member except `MCPClientToolset`, plus `LiveCodingToolset`; `AllToolsets` and `MCPClientToolset` disabled because the former hard-depends on the latter) and `Config/DefaultSourceControlSettings.ini`. Log mounts neither disabled plugin. |
| 5 | LFS backup | Dropped (out of scope) |
| 6 | Lead + `.mcp.json` | Pass |
| 7 | Launch with MCP flags | **Pass:** `LogHttpListener` bound `127.0.0.1:8000` |
| 8 | Discovery | **Pass:** `list_toolsets` / `describe_toolset` work. Tools are called with `toolset_name` + bare `tool_name`; a prefixed name returns "not found". |
| 9 | Schema export | Pass: 53 toolsets, 831 tools in `docs/research/ue58-toolsets.json` |
| 10 | Read-only query + identity | **Pass:** `find_actors` lists the open level; `ProjectID` over MCP matches `DefaultGame.ini`. `ProjectName` is blank (unset in config); the editor loads `libUnrealEditor-MyProject.dylib`. |
| 11 | Edit, save, revert | **Pass:** no create-level tool, so `L_Smoke` is a duplicate of `/Engine/Maps/Templates/Template_Default`, committed as the baseline. Placing a cube and saving gave a pointer-only `git diff`; after `git restore` and a reload the cube is gone. |
| 12 | INI auto-start | Pass (soft): `Config/DefaultEditorPerProjectUserSettings.ini` with `bAutoStartServer=True` starts the server with no flags. A relaunch right after quit failed to bind 8000 once; wait for the port to free before reopening. |
| 13 | Codex worker adds `ASmokeActor` | Pass: worktree branch `smoke-actor`, commit `fd89401`, no build. The first `--worktree` spawn needed the operator to accept Codex's folder-trust prompt (it applies to the repo root, so once). |
| 14 | Merge, close, build, reopen | **Pass:** `Build.sh MyProjectEditor Mac Development … -NoHotReload` succeeded in 9.5 s |
| 15 | Place `ASmokeActor` via MCP, commit | **Pass:** `SmokeActor_0` in `L_Smoke`, commit `2b744dd`; survives an editor restart. The C++ landed in the preceding fast-forward merge, not the same commit. |
| 16 | `CompileLiveCoding` | Fail (soft): "Live Coding is not available in this build configuration." C++ changes on Mac go through close → `Build.sh` → reopen. |
| 17 | Push | Dropped (no push at all) |
| 18 | Fresh clone from backup | Dropped (out of scope) |

## Capability notes from the export

- Blueprint graph editing: yes (`BlueprintTools.read_graph_dsl`, `write_graph_dsl`, `connect_pins`, …).
- PIE: yes (`EditorAppToolset.StartPIE` / `StopPIE` / `IsPIERunning`).
- Console commands: no exec tool; only `EditorAppToolset.SearchCVars`.
- Python: no arbitrary execution; `ProgrammaticToolset.execute_tool_script` is a sandbox that orchestrates other tools.
- No tool creates a new level; duplicate a template map.

## Follow-ups

- Toolset pruning (per the toolset decision) is now possible from the export.
- `GameFeatureData` asset-manager rule missing: two load errors at startup, harmless for now.
