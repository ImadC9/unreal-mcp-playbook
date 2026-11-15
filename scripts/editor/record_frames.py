"""
record_frames.py - frame recorder that runs INSIDE the Unreal editor (via the MCP execute_python tool).

It is a template: the capture loop is the pattern used to record tutorial clips and trailer shots
through the UE 5.9 MCP server, but tool names and the capture result shape can differ between engine
versions, so check them with describe_tools and adjust the two hooks for your game.

Use (each line is one execute_python call; PIE must already be running and ready):

    exec(open(unreal.Paths.project_saved_dir() + 'Agent/record_frames.py').read())
    unreal._agent['job'] = asyncio.ensure_future(record('intro', seconds=6.0))   # returns immediately
    str(unreal._agent['STATUS'])                                                  # poll from later calls

Output: <Project>/Saved/Clips/<name>/f_0000.png ... plus meta.json with the game time of every frame,
so the clip can be resampled to a fixed frame rate afterwards (scripts/contact_sheet.py makes a
contact sheet or video from the folder).
"""
import asyncio
import base64
import json
import os

import unreal

CAPTURE_TOOL = 'SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport'   # verify with describe_tools

if not hasattr(unreal, '_agent'):
    unreal._agent = {}
unreal._agent.setdefault('STATUS', 'idle')


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


# ---- hook 1: what the game should do while recording -------------------------------------------
async def drive(world, t):
    """Called once per captured frame with the game time since recording started.
    Trigger gameplay here (call your manager Blueprint's functions at chosen times). Default: nothing."""
    return None


# ---- hook 2: extra data to store with each frame ------------------------------------------------
def describe(world):
    """Return a small dict saved with each frame (e.g. state flags, screen positions for overlays)."""
    return {}


async def record(name, seconds=5.0, time_dilation=0.1, max_resolution=960, pause=0.0):
    """Capture `seconds` of GAME time. time_dilation < 1 slows the game so captures are dense."""
    world = game_world()
    if world is None:
        unreal._agent['STATUS'] = 'error: PIE is not running'
        return unreal._agent['STATUS']
    out = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + 'Clips/' + name + '/'
    os.makedirs(out, exist_ok=True)
    frames, i = [], 0
    unreal.GameplayStatics.set_global_time_dilation(world, time_dilation)
    t0 = unreal.GameplayStatics.get_time_seconds(world)
    try:
        while True:
            t = unreal.GameplayStatics.get_time_seconds(world) - t0
            if t >= seconds:
                break
            await drive(world, t)
            res = await call_tool(CAPTURE_TOOL, world=None, maxResolution=max_resolution)  # noqa: F821 (provided by the MCP Python tool)
            open(out + 'f_%04d.png' % i, 'wb').write(base64.b64decode(res['image']['data']))
            frames.append(dict(f=i, t=round(t, 4), **describe(world)))
            i += 1
            unreal._agent['STATUS'] = 'recording %s: %d frames, t=%.2f/%.2f' % (name, i, t, seconds)
            await asyncio.sleep(pause)      # yield so the editor and the game keep running
    finally:
        unreal.GameplayStatics.set_global_time_dilation(world, 1.0)
    json.dump({'name': name, 'seconds': seconds, 'time_dilation': time_dilation, 'frames': frames},
              open(out + 'meta.json', 'w'))
    unreal._agent['STATUS'] = 'done %s: %d frames in %s' % (name, i, out)
    return unreal._agent['STATUS']
