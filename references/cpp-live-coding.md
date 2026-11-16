# C++ projects and Live Coding: field notes

What goes wrong in a multi-day C++ project built through Live Coding with nobody at the keyboard. Each rule cost an editor crash or a wasted review round on a real project (an on-rails mech shooter, UE 5.9).

## Live Coding keeps old memory alive

A Live Coding patch replaces code, not data. Globals, file-statics and function-local statics keep the bytes they had before the patch.

- **Never change the layout of a file-static struct or a live Slate widget class between patches.** Adding one member and then assigning or destroying the old instance is an access violation. Put new state in a separate new global, or stop PIE and restart the editor after a layout change.
- **Static lookup tables keep their old contents.** A `static const TCHAR* Names[]` edited in a patch may still hold the old strings. Make such tables plain locals, or rename them when their contents change.
- **A widget must not outlive its world.** Tear down anything added with `AddViewportWidgetContent` in `FWorldDelegates::OnWorldCleanup`. A widget that survives into the next patch is destroyed by code that no longer matches it.
- **Do not cache a failed asset lookup in a static map.** The asset may be imported later in the same session.
- **Keep UCLASS headers stable.** New state goes in file-statics or one shared state struct; free functions are declared in a plain header.
- **The DLL on disk is stale.** Live-coded work lives only in the running editor. After any restart, compile before the first PIE and check the map still has its game mode. Before handing over or packaging, do one real build with the editor closed.

## When the editor is minimised or in the background

- Slate does not tick or paint. Widgets never appear, `FSlateApplication::TakeScreenshot` fails, and `CaptureGameViewport` shows the scene without widgets or reports no framebuffer.
- The world ticks at a few frames per second. An automated run that takes a minute in focus can take an hour.
- Start PIE with `options: {playMode: "PlayMode_InEditorFloating"}` to get a window that renders. Tell the user first: a game window will appear on their screen.
- To capture widgets, add a console variable that the root widget polls in `Tick`, call `TakeScreenshot` on the game viewport widget, and save the PNG. `shot showui` and `FScreenshotRequest` did not produce files when driven through the MCP server.
- If world time stays at zero across two reads a few seconds apart, the editor is blocked. Stop and ask the user to look at the window; do not keep capturing blank frames.
- Do not try to restore or focus the user's windows with shell commands. Use the editor's own play modes or ask.

## Low-frame-rate captures hide frame-rate bugs

A capture loop runs the game at a handful of frames per second. Anything applied per frame without delta time looks fine there and breaks at 60 fps for the user.

- Never call `AddRelativeLocation` (or any additive offset) every frame for an effect. Store the offset, remove it at the start of the next frame, and clamp it.
- After adding camera, input or feel code, say plainly that it is unverified at real frame rate and ask the user to confirm on their next run.
- Mouse sensitivity and anything else felt by hand cannot be judged from stills. Give it an options slider and ask.
- After switching to a UI input mode for menus, switch back to game-only and return focus to the game viewport, or aiming receives only partial mouse movement.

## Leave the project playable

- Test console variables (bot, speed, forced overlays) survive between PIE sessions. Reset every one, stop PIE and delete test saves before reporting.
- When a tool call returns `Failed to fetch`, the editor has probably crashed. Read the tail of `Saved/Logs/<Project>.log` for the callstack first, fix the cause in source, and tell the user the editor needs reopening. The agent cannot relaunch it.
- With the editor closed there is no shell on the user's machine. File moves and deletes are not possible; give the user the manual steps rather than implying they were done.

## Rigging generated models (Meshy through fal)

- Endpoint `fal-ai/meshy/rigging/multi-animation` takes `model_url`, `height_meters` and up to ten `animation_action_ids`, and returns a rigged FBX plus one FBX per clip. Upload local meshes with a signed PUT from the user's machine (`curl --upload-file`), since an agent sandbox usually cannot reach the media host.
- Static meshes already in the project export with `unreal.GLTFExporter.export_to_gltf`.
- Import the rig with `FbxImportUI` (`import_as_skeletal`, `FBXIT_SKELETAL_MESH`), then each clip with `FBXIT_ANIMATION` and `skeleton` set to the new skeleton asset.
- **The clip library is humanoid and ground-based.** There are no flying or hovering clips. Combat stances read as a crouch and swim clips as treading water on a flying character. Decide whether the character suits the library before paying for jobs, and show the user one close-up before rigging the rest of the cast.
- **Check facing from the bounds.** If the wide axis is Y the mesh faces along X; confirm with a close crop instead of guessing a yaw.
- **Overlay materials need the skeletal usage flag.** A rim or outline shell without `used_with_skeletal_mesh` renders as flat grey over the whole character and looks like a ruined mesh.
- Keep the original static mesh as a fallback path, and switch the rig on only after a close-up crop looks right in idle and in one action.
- Sampling clips per bone into a `UPoseableMeshComponent` (`UAnimSequence::GetBoneTransform`, blend, write `BoneSpaceTransforms`, `RefreshBoneTransforms`) gives cross-fades and procedural layers without an Animation Blueprint. Lock the hip bone's horizontal translation so clips never move the character off its gameplay position.

## Changing the whole look from Python

A cel-shaded look needs no hand-made assets:

- A post-process material (`MD_POST_PROCESS`, before bloom) with one Custom node fed by SceneTexture nodes: `PostProcessInput0`, `BaseColor`, and five taps each of `SceneDepth` and `WorldNormal`. Band the lighting ratio (scene colour over base colour) into two or three steps, pass highlights and unlit pixels through untouched, and draw ink where depth or normals jump. Skip the normal test where the normal is zero, or unlit surfaces turn solid ink.
- Attach it in code with `Camera->PostProcessSettings.AddBlendable(MID, 1)` so a scalar parameter can drive effects such as impact frames.
- Flatten generated scenery with a second material that posterises texture luminance into two palette colours and keeps only highly saturated accents; set metallic to 0 and roughness to 1.

## Working with the person

- Before replacing an art direction, ask which direction they want, with three or four concrete options. Several rounds of guessed polish cost more than one question.
- Layering effects, sounds and menus on an unchanged core reads as "nothing changed". When the feedback is that the game feels the same, change what a minute of play looks like: camera, palette, shading, enemy behaviour.
- Judge every visual change from a close crop, not a full-frame still. Small characters hide broken poses and wrong facing.
- Do not reuse the user's concept images as final art unless asked; they are inspiration.
- Report three things separately: what was only compiled, what was seen in a capture, and what was never checked.
