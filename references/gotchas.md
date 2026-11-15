# Gotchas (each one cost real time)

| Symptom | Cause | Fix |
|---|---|---|
| Effect or prop exists but never moves/animates; instance transforms don't update | Component mobility is **Static** | Set `ComponentMobility.MOVABLE` on anything that changes at runtime (in the Blueprint *and* on placed copies) |
| Changed a Blueprint default (material, colour, value) but the level still shows the old one | The **placed level actor has its own override** | Fix the placed actor too, or set the value in BeginPlay so the Blueprint always wins. Query the runtime value to confirm: `comp.get_material(0).get_path_name()` |
| Half the procedural objects are missing | `Fraction`, `%` or a sine hash returned **negative** values; objects placed below the floor or with negative scale | Clamp/abs before using as position or scale; inspect instance transforms live |
| Effect "too faint", made bigger and brighter twice, still invisible | It wasn't faint; it was broken (see the two rows above) | Query live state before tuning numbers |
| Robots/pieces smear on every move | **Motion blur** at a close tabletop camera | Disable motion blur in the post-process volume or camera |
| Empty white/grey boxes in text | Font has no glyph for that character (arrows, ✂, ◆, emoji) | Check glyph coverage; use a font that has it or use words/icons |
| A widget flashes empty for a frame before its text appears | Font loaded lazily the first time | Preload the font (use it once at startup) or set the text before showing the widget |
| Red/yellow engine text in screenshots ("video memory exhausted", etc.) | **On-screen debug messages** enabled | `DisableAllScreenMessages` at startup; also reduce VRAM use (ray tracing, texture sizes) if the warning is real |
| UI looks fine in PIE, clipped in a smaller window | Anchors/offsets assume one resolution | Anchor to edges/centre, use auto-size, test at 1280×720 and 1920×1080 |
| HUD, menus and title screen feel like different games | Each screen styled ad hoc | One style helper (panel, font sizes, button shape, colours) applied to every screen |
| Dialogue/subtitles cover buttons or menus | Z-order and position not planned per screen | Menus above subtitles; move subtitles per state (play vs menu) |
| `CreateAndAddWidget` fails or edits the wrong widget | **Widget name already exists** in the tree | Check `unreal.find_object(None, path)` first; use a unique prefix |
| Editor freezes during a long Python job, or the call times out | The script runs on the editor's main thread | `await asyncio.sleep(0)` inside loops; split work into several calls; run external tools as detached subprocesses and poll |
| A write "succeeded" but the game behaves the same | Blueprint not compiled, compile failed, or PIE still running old code | Compile, check status, save, restart PIE |
| Can't save / changes lost | Saved while PIE running, or never saved | Stop PIE, then `save_dirty_packages`; check the dirty list is empty |
| On quitting, the editor asks to save an unknown asset | An in-memory backup/duplicate was created but never written | Save backups to disk as files (copytree) instead of duplicating assets in memory; tell the user it's safe to discard |
| Agent says the Unreal tools don't exist | Client config points at the wrong port or `localhost`; the Codex config is written once by the editor and goes stale; client not restarted | Fix the URL to `http://127.0.0.1:<port>/mcp`, restart the client, or use `scripts/ue_mcp.py` |
| Calls fail or interleave when sent in parallel | The editor runs tool calls one at a time on its game thread | Send calls sequentially; batch work into one Python script |
| Lost connection after a pause | MCP session expired or editor restarted | Redo the handshake; re-run any client-side helper setup |
| Imported mesh is huge/tiny or offset | Source units and pivot differ | Read bounds after import (`get_bounds()`), scale and offset at placement |
| Imported textures bloat the build | 4K textures from generators | Set `max_texture_size` (e.g. 512–1024) on imported textures |
| Win/goal not detected in an edge case | Checks only run after one kind of action | Run end-condition checks after every state-changing action, and include that case in regression runs |
| Packaging fails with an installed engine, complaining about a temporary/source target | An editor-only plugin (the MCP/AllToolsets plugin) pulled into the game target | `"TargetAllowList": ["Editor"]` for that plugin in the `.uproject` (back it up first) |
| Build is far bigger than expected | Backups, test folders or video captures got cooked | `DirectoriesToNeverCook` for backup/test folders; list `MapsToCook` explicitly |
| Can't add a click event to a button | The Blueprint DSL didn't support Widget Blueprint graphs (UE 5.9) | Poll `Button.IsPressed` from the actor Blueprint that owns the HUD, with an edge flag; see `ui.md` |
| Panel borders twice as thick as designed | Stretchable (box/9-slice) texture drawn at 2x, with margins set for 1x | Author the texture at the size it is declared, and set the brush image size and margin to match (margin = border px / texture px) |
| Text a third larger than the mock-up | UMG font size is in points; 1 pt came out as about 1.33 px | Convert once in your style helper (px × 0.75) and measure a screenshot to confirm |
| A highlight or selection ring is visible on one object from the start | Its default state was never initialised to "off" | Set every hover/selection visual explicitly at BeginPlay and after level load |
| Custom cursor is cut off | Cursor texture has no padding or the hotspot is at the edge | Leave transparent padding, set the hotspot, and check it in the packaged build |
| Scene looks hazy; small pieces hard to read | Local lights scattering in volumetric fog, shallow depth of field | Turn off volumetric scattering on gameplay lights, lower fog density, widen depth of field; judge from the gameplay camera, not a beauty shot |
| Fans spin up, CPU/GPU pinned | Frame rate uncapped | Cap it (e.g. `t.MaxFPS 60` or a game user setting) |
| "Video memory exhausted" on a mid-range GPU | Ray tracing/Lumen hardware features on by default, 4K generated textures | Default the heavy features off with an Options toggle; cap prop textures (1K is plenty for small props) |
| Changing a setting on the running game reset the level or blacked out the scene | A live PIE object was modified from Python and re-ran its setup | Stop PIE, change the asset default, test in a fresh run |
| Ending or menu screens stack on top of each other | An older timed rule still shows a panel the new flow doesn't expect | Grep the DSL dump for every writer of that widget's visibility; remove or gate the old rule |
| First seconds of the packaged game show popping meshes or a hitch | Shaders and assets load on first use | Add a short loading screen/splash in the game's visual style and warm up the main scene behind it |
| No way to quit or go back | Menus built for PIE, where the editor's Stop button exists | Ship an Exit button on the title screen and a Main Menu button in the pause/options screen |
| A generated 3D prop never looks right wherever you put it | The model itself is wrong for the job (too thick, wrong silhouette) | Judge generated assets as critically as code; delete and replace, or build it from simple shapes |
| In-game video is black in the packaged build | The file is outside `Content/Movies` or referenced by absolute path | Put it under `Content/Movies` and use a relative `./Movies/...` path |
| Recorded clips play at uneven speed | Frames captured at irregular real-time intervals, or shots sped up by different factors | Record game time with each frame and resample to a fixed frame rate; use one speed for every shot |

