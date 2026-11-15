# Verifying in play: screenshots, recordings, automated playthroughs

"The tool call succeeded" proves nothing about the game. Effects can be invisible, UI can overlap, a rule change can break level 5. This is the checking loop that caught those problems.

## Contents
- Make the game testable
- Start PIE reliably
- Drive the game from Python
- Screenshots
- Recording motion
- Reviewing what you captured
- Regression runs
- Reporting

## Make the game testable

Structure decides how much you can check automatically:

- **Put the rules in one place.** One manager Blueprint resolves a turn or tick in a fixed order; other actors only play back the events it emits. Then a test only has to call that one object and read its state.
- **Write a reference model outside the engine.** A few dozen lines of Python that implement the same rules let you prove things before building them (is each level solvable, what is the minimum number of moves, is there an unintended shortcut) and give you expected results to test the Blueprint against. For puzzle games add a breadth-first solver; a generator that keeps only boards with few shortest solutions finds better levels than hand design, and exposes loose ones (one hand-made level turned out to have 1,801 shortest solutions).
- **Test two ways**: replay each level's known solution and expect a win at the expected move count, and feed random input sequences to both the reference and the running game and compare states step by step. The second kind finds the bugs nobody thought to script.
- **Add debug entry points** (`DebugLoadLevel`, `SkipIntro`, a way to jump to the ending). A screen you can't reach from a script is a screen you won't check; if one can't be forced, say so in the report.

## Start PIE reliably

`IsPIERunning` turns true before the game world has spawned your actors. Poll for something the game needs:

```python
# returns 'ready' when the game world exists and the key actor is spawned
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
ok = bool(w) and any(a.get_class().get_name() == 'BP_Board_C'
                     for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor))
'ready' if ok else 'waiting'
```
Start with `EditorAppToolset.StartPIE {options:{playMode:'PlayMode_InEditorFloating'}}`, then poll every 1–2 s, retrying the start a few times. Stop PIE (`StopPIE`) before editing assets.

## Drive the game from Python

Call the same Blueprint functions your input bindings call. That's more reliable than synthesising key presses and lets you script exact sequences:

```python
import asyncio
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
b = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor) if a.get_class().get_name() == 'BP_Board_C')
for move in [1, 1, 2]:
    b.call_method('ApplyMove', (move,))
    await asyncio.sleep(0.35)          # let the step animation play; also keeps the editor responsive
{'won': b.get_editor_property('bWon'), 'beat': b.get_editor_property('Beat')}
```

Add small test hooks to the game where it helps (e.g. `DebugLoadLevel(n)`, `SkipIntro`) and keep them out of player-facing UI.

What this doesn't cover: real mouse hit-testing, hover states and controller input. Say so in your report, or test clicks by projecting a world point to the screen and calling the UI's handler directly.

## Screenshots

Capture the game viewport and write it to disk:

```python
import base64, os
res = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=1600)
d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + 'AgentShots/'
os.makedirs(d, exist_ok=True)
open(d + 'l3_after_cut.png', 'wb').write(base64.b64decode(res['image']['data']))
```
(`python scripts/ue_mcp.py shot l3_after_cut` does the same.)

Name shots by what they show and when (`title_before.png`, `l3_after_cut.png`) so before/after pairs are easy to build later. Keep them: a game-jam dev log or a bug report will want them.

## Recording motion

For animation, transitions and "feel", capture a frame sequence while the game runs: loop `CaptureGameViewport` at a fixed interval from an async Python script, save `f_0000.jpg…`, and write a `meta.json` with timestamps and game events (move made, cut, win) so you can line frames up with what happened. Zip the folder on the editor side if you need to move it to another machine.

Capturing at a fixed interval is not real-time: each capture takes a variable amount of time and the game keeps running in between. What produced clean footage:

- Slow the game while recording (global time dilation / `slomo`) so each captured frame covers a small slice of game time.
- Store **game time** with every frame in `meta.json`, plus markers for events and any on-screen points you want to annotate later (e.g. projected positions for a cursor overlay).
- Afterwards, resample to a fixed frame rate (30 fps) by picking the nearest captured frame for each output frame. Use the same speed for every shot; mixing speed-ups makes the motion visibly uneven between cuts.
- Record gameplay, not menus, and check a contact sheet of each clip before building anything on top of it.

`scripts/editor/record_frames.py` is a starting point for the recorder (it runs inside the editor through `execute_python`; adapt the two hooks to your game).

Turn frames into something reviewable:
```bash
python scripts/contact_sheet.py Saved/Clips/cut  sheet.jpg --n 12      # grid of evenly spaced frames
python scripts/contact_sheet.py Saved/Clips/cut  cut.mp4  --fps 30     # video (ffmpeg)
python scripts/contact_sheet.py before.png compare.jpg --after after.png
```

## Reviewing what you captured

Open every image you capture and judge it like a picky player seeing it for the first time. Check for:

- Text: clipped, wrapping where it shouldn't, too small at 1080p, low contrast against the scene, empty boxes (missing glyphs).
- Layout: HUD overlapping game objects or other HUD, things hidden behind panels, inconsistent spacing or styles between screens.
- Scene: stray or floating objects, props intersecting, debug text or warnings on screen, effects too small to see from the game camera.
- Motion (contact sheet/video): a frame where a widget appears empty before its content, objects popping, motion blur smearing, stutter between steps, abrupt cuts that should fade.
- State: does the screen show what the game state says (score, moves, who is selected)?

If an effect isn't visible, query it live before changing numbers: instance counts, transforms, material actually in use, visibility, mobility. Guessing (making it "bigger and brighter") wastes iterations when the real cause is a negative scale or an overridden material.

## Regression runs

For games with known solutions or scripted paths, keep a table of `level → input sequence → expected result` and run all of it after every significant change. It takes seconds and catches the bugs no one would find by looking. In the jam project this ran after every pass ("all 7 levels still win at par") and caught a missed win check that only showed up on the final level.

## PIE is not the shipped game

The editor's play window hides a class of problems. Before calling anything finished, run the packaged build (see `packaging.md`) and expect differences in: first-launch loading and shader hitches, default graphics settings (ray tracing, resolution, window mode), mouse cursor and input focus, fog and post-processing at the real resolution, frame rate caps, video playback, and anything that relied on the editor's Stop button. Do this at least a day before a deadline.

## Reporting

Tell the user:
1. What changed in the game.
2. How you checked it (screenshots reviewed, levels replayed, frames reviewed).
3. What you couldn't check (packaged build, real clicks, audio mix) and should be tested by hand.
4. Show the evidence: send the key screenshots or a before/after image.
