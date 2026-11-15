---
name: unreal-mcp-playbook
description: "Drive a running Unreal Engine editor through its MCP server (the editor's built-in \"unreal-mcp\" / AllToolsets server, usually http://127.0.0.1:8000/mcp) to build and polish a game: connect and verify the server, discover toolsets, run editor Python, read and write Blueprint graphs with the Blueprint DSL, edit UMG widgets, start Play-In-Editor, simulate input, capture screenshots and frame sequences, back up content, and package a build. Use this skill whenever the user mentions Unreal, UE5, a .uproject, Blueprints, PIE, an Unreal MCP server, or asks an agent to build, fix, playtest, polish, record or package an Unreal game, even if they never say \"MCP\"."
---

# Unreal MCP Playbook

The Unreal editor can expose almost everything it does (assets, levels, Blueprints, widgets, Play-In-Editor, scene capture, Python) as MCP tools. An agent with that connection can build a whole game, but only if it works the way a careful developer at the editor would: look before changing, back up before big edits, compile and save after each step, and check the result in the running game instead of trusting that a call succeeded.

This skill was distilled from building a complete seven-level puzzle game in UE 5.9 for a four-day game jam, almost entirely through the MCP server. The rules below are the ones that cost real time to learn.

## 1. Connect and confirm (do this first, every session)

1. Find the server. Look for `.mcp.json` / `.codex/config.toml` (or your client's MCP config) in the project folder; the editor's **Editor Preferences → Agentic Workflows → Model Context Protocol** panel shows the port and has **Generate Client Config**. The usual endpoint is `http://127.0.0.1:8000/mcp` (use `127.0.0.1`, not `localhost`). The editor must be open: it *is* the server. If the port in the client config differs from the editor's, the tools silently won't appear; the Codex file in particular is written only once and goes stale.
2. If your client already lists the Unreal tools (names like `list_toolsets`, `describe_tools`, `call_tool`), use them directly.
3. If it doesn't (sandboxed agent, different client, tools not loaded), use the bundled stdlib client from a shell:
   ```bash
   python scripts/ue_mcp.py probe                 # handshake + server name/version + toolset count
   python scripts/ue_mcp.py toolsets              # list toolsets
   python scripts/ue_mcp.py py -c "unreal.SystemLibrary.get_engine_version()"
   ```
   Set `UE_MCP_URL` if the port differs. See `references/connecting.md` for client configs, the raw JSON-RPC handshake, and the browser-bridge variant for cloud agents that can only reach the user's machine through a browser.
4. Confirm it's the right editor and project before touching anything: one read-only call (engine version, project dir, current map, list of Blueprints under `/Game/<YourFolder>`). A 405 on a plain GET is normal for an MCP endpoint; it means something is listening.

The editor runs tool calls one at a time on its main thread, and clients may time out calls after about two minutes: send calls sequentially, and keep each one short.

Sessions don't survive reconnects. If calls start failing after a pause or editor restart, redo the handshake rather than debugging the tool.

## 2. Discover, don't guess

The server has 100+ toolsets and their names and parameters vary by engine version and enabled plugins. Before using a toolset for the first time, describe it:

- `list_toolsets` → names
- `describe_toolsets` (toolset names) → tools in each
- `describe_tools` (full tool names) → exact parameter names and shapes

Then call through the dispatcher: `call_tool` with `{tool_name, toolset_name, arguments}`. Parameter names are case-sensitive and the convention differs between toolsets (the Blueprint DSL tools took `assetPath`, while compile and UMG tools took `Blueprint` / `WidgetBlueprint` when called from Python), so copy them from `describe_tools` instead of assuming. Over JSON, object references are usually `{"refPath": "/Game/Folder/BP_Name.BP_Name"}`; inside editor Python you pass the loaded object. `references/toolsets.md` lists the toolsets that did the heavy lifting and the shapes that worked.

## 3. Pick the right lever

| Job | Best tool | Why |
|---|---|---|
| Inspect anything, batch edits, asset import, level actors, settings, files | **execute_python** | One call does what would take dozens of tool calls; returns a value you can check |
| Blueprint logic (functions, events, math) | **Blueprint DSL** `Read` / `Edit` / `Write` | Text you can diff and patch; far more reliable than wiring nodes one by one |
| Add function graphs, variables, compile | Blueprint toolset or `unreal.BlueprintEditorLibrary` in Python | |
| Widgets (HUD, menus) | UMG editor tools to create/add widgets, Python to lay out and style them, an actor Blueprint to drive them | The DSL could not edit Widget Blueprint graphs, so UI logic lives outside the widget. See `references/ui.md` |
| Play, input, screenshots | Editor app toolset (PIE) + scene capture + Python in the game world | |

`execute_python` takes `script: {"content": "<code>", "language": "Python"}`, not a bare string (a bare string fails or is ignored). The value of the last expression comes back as `returnValue`, so end scripts with a dict or string summarising what happened. Inside the script you can `await call_tool('Toolset.Name.Tool', arg=...)` to reach any other tool, which lets one script read a Blueprint, patch it, compile and save.

Blueprint DSL essentials (details and pitfalls in `references/blueprint-dsl.md`):
- `Read` with `scope` = a function/event name (or `""` for all) returns the graph as S-expressions plus a `revision`.
- Prefer `Edit` with `revision` and `edits: [{oldString, newString}]` for small changes: it fails loudly if the text moved, instead of overwriting someone else's change.
- For new functions, create the graph first (`AddFunctionGraph`), then `Write` its body.
- Always compile after a write and check `status` is up-to-date (not error) before moving on.

## 4. The working loop

Work in small, checkable steps. For each change:

1. **Back up** before anything structural (new systems, UI overhaul, big refactor): copy the project's content folder into `Saved/Backups_<agent>/<name>_<YYYYMMDD_HHMM>_<label>/` with Python `shutil.copytree`, and tell the user where it is. Make sure backup folders are excluded from cooking (see packaging).
2. **Change** with the lever from section 3.
3. **Compile** (Blueprints and widget Blueprints) and read the compile status.
4. **Save** (`EditorAssetLibrary.save_asset` / `save_directory`, or `EditorLoadingAndSavingUtils.save_dirty_packages`). Unsaved work is lost if the editor crashes, and the user will be asked about it on exit.
5. **Verify in play** (section 5). A successful tool call only means the call ran.

Stop Play-In-Editor before editing Blueprints or saving; edits during PIE are confusing at best and lost at worst.

Habits that kept a four-day project stable:

- **Playable at the end of every session.** Build a greybox with the final rules first (cubes are fine), then add models, sound and polish on top of a game that already works. Never leave the project half-converted.
- **Make changes to asset defaults, not to the running game.** Poking settings on live PIE objects (a camera, the game mode) can reset game state and gives results that vanish on the next run. Read live state freely; write to assets, then test in a fresh run.
- **Keep scripts as files.** Save anything you will run twice (UI layout, level data, a recorder, a regression run) under `Saved/<agent>/` and write it so re-running is safe. One "apply" script that rebuilds a whole HUD from a single file beats fifty one-off edits you can't replay.
- **Before changing shared logic, find every writer.** Dump the Blueprint DSL to a file and grep for the variable or widget you are about to change. Old rules that also set it are where "it worked until I changed the UI" bugs come from.
- **Taking over from another agent or session:** back up, read what changed, run the regression checks, and look at every screen before adding anything. Don't trust a change log that was never play-tested.

## 5. Verify like a player, not like a compiler

This is where most of the quality comes from. Read `references/verification.md` before your first playtest; it has the capture code.

- **Start PIE and wait until the game is actually ready** (poll for a key actor in the game world), not just until `IsPIERunning` says true.
- **Drive the game from Python**: get the game world, find actors, call their Blueprint functions (`actor.call_method('Fn')`), read their properties. This gives you automated playthroughs: run each level's known solution and assert it wins, after every significant change, as a regression test.
- **Look at it.** Capture the game viewport to a PNG, open it, and judge it critically: overlaps, text clipped or unreadable, empty "tofu" boxes from missing font glyphs, stray objects, debug messages on screen, things too small to see at the game camera's distance.
- **Record motion when motion matters** (animation, transitions, feel): capture a frame sequence (`scripts/editor/record_frames.py`), build a contact sheet or a short video (`scripts/contact_sheet.py`), and review it. Stills hide popping, smearing and stutter.
- **After any UI change, look at every screen**, not just the one you edited: title, play, pause/options, result, ending (`references/ui.md` has the per-screen checklist).
- **Give the game a reference to test against.** For rule-driven games, write the rules once outside the engine (a small Python model, plus a solver for puzzles), then check the Blueprint version against it: known solutions per level, and random input sequences compared state by state.
- **Play the packaged build early**, not on the last evening. Fog, cursor, loading, missing Exit button and performance problems only show up outside the editor (`references/packaging.md` has the checklist).
- Report what you verified and what you could not (e.g. real mouse clicks, audio, the packaged build) so the user knows what to test themselves.

## 6. Known traps

These each cost an hour or more. Full list with fixes in `references/gotchas.md`.

- A component left **Static** won't move, animate or update instances at runtime; set **Movable** for anything that changes.
- A **placed level instance keeps its own overrides** (materials, properties) and silently ignores changes to the Blueprint defaults. Fix the placed actor too, or set the value in BeginPlay.
- **`Fraction` and modulo go negative for negative inputs.** Procedural placement then puts half the objects underground with negative scale.
- **Motion blur** smears small fast objects in a top-down/board camera; consider turning it off.
- **Fonts without the glyph** (arrows, ✂, ◆) render as empty boxes. Check the glyph exists or use words.
- **Engine on-screen debug messages** (e.g. video memory warnings) show in captures and builds unless disabled.
- **Widget names must be unique** in a widget tree; creating `SubText` when one exists fails or collides.
- **Widget Blueprint graphs may be closed to the DSL.** Don't burn time trying to add click events there; drive the UI from an actor Blueprint.
- **UI assets at the wrong scale**: stretchable (9-slice) textures drawn at 2x get 2x borders, and UMG font sizes are points, not pixels.
- **Atmosphere that hides the game**: lights scattering in volumetric fog and shallow depth of field look moody in a still and unreadable in play.
- **Uncapped frame rate** cooks the CPU/GPU in a small game; cap it.
- **Long Python scripts block the editor.** Yield with `await asyncio.sleep(0)` in loops, and run long processes (packaging, ffmpeg, zip) as detached subprocesses you poll.

## 7. Packaging

Read `references/packaging.md` before the first attempt. In short: confirm maps to cook and directories never to cook (backups!), save everything, run `RunUAT BuildCookRun` as a detached process with a log, poll the log, then smoke-test the executable and check the archive size against any limit. With an installed (launcher) engine, editor-only plugins such as the MCP/AllToolsets plugin can force a source build that fails; restricting that plugin to the Editor target (`"TargetAllowList": ["Editor"]` in the `.uproject`) fixes it. Back up the `.uproject` before editing it. A machine without the platform SDK (e.g. no Windows SDK) can't compile a game executable at all: a Blueprint-only project can still ship with the engine's stock executable (`-skipbuild`). Then play the packaged build from start to finish, because it differs from PIE.

## 8. Talking to the user

- Before a big change, say what you'll do and where the backup will be.
- After a change, lead with what changed in the game, then what you verified and how (e.g. "all 7 levels still win at par"), then what's left to test by hand.
- Show the evidence: send the screenshot or contact sheet, before/after when you changed visuals.
- If a request is risky late in a deadline (e.g. rewriting the rules engine the night before submission), say so and offer the safer option.
