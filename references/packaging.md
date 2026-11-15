# Packaging a build from the editor

Packaging takes minutes and can fail late, so prepare carefully, run it detached, and check the output yourself.

## 1. Prepare

- **Save everything** and confirm the dirty list is empty.
- **Back up** `Config/DefaultGame.ini` and the `.uproject` before editing them.
- **Project settings** (`Config/DefaultGame.ini`):
  ```ini
  [/Script/EngineSettings.GeneralProjectSettings]
  ProjectName=My Game
  ProjectVersion=1.0.0

  [/Script/UnrealEd.ProjectPackagingSettings]
  BuildConfiguration=PPBC_Development
  UsePakFile=True
  bCompressed=True
  IncludePrerequisites=True
  +MapsToCook=(FilePath="/Game/MyGame/Maps/L_Main")
  +DirectoriesToNeverCook=(Path="/Game/MyGame/Backups")
  +DirectoriesToNeverCook=(Path="/Game/Developers")
  ```
  Check the target's rules (a jam may recommend Development over Shipping, or set a size limit).
- **Game defaults**: default map and game mode set, debug screen messages off, test hooks unreachable from player UI.
- **Editor-only plugins**: with an installed (launcher) engine, a project plugin that isn't restricted to the editor can force UAT to build a temporary C++ target, which fails without a source build. Restrict editor tooling plugins (like the MCP/AllToolsets plugin) to the editor:
  ```json
  { "Name": "AllToolsets", "Enabled": true, "TargetAllowList": ["Editor"] }
  ```
- **No platform SDK installed** (e.g. no Windows SDK / Visual Studio): the game executable can't be compiled, so the first packaging attempt fails in the build step. A Blueprint-only project can still be packaged with the engine's prebuilt game executable: add `-skipbuild -nocompile -nocompileuat` and make sure nothing forces a project-specific target (the editor-only plugin rule above is usually what does). A custom exe icon also needs the SDK. If the project has C++ or runtime plugins, the SDK has to be installed; tell the user early, it is a large download.
- **Size**: cap generated prop textures (`max_texture_size` 1024), and list old audio takes, UI backups and capture folders under `DirectoriesToNeverCook`.
- **Video**: files played by a Media Player go in `Content/Movies` (they are copied as-is, not cooked) and are referenced by relative path.
- **Splash/loading**: replace the default splash (`Content/Splash/Splash.bmp`) with one in the game's style.
- **Icon** (Windows): `Build/Windows/Application.ico` (multi-size ICO, 16–256 px).
- The executable name comes from the project name; renaming it means renaming the project. Name the archive and its folder properly instead.

## 2. Run BuildCookRun detached

From `execute_python`, start UAT as a detached process writing to a log, then return immediately and poll. Never block the editor for the whole build.

```python
import os, subprocess
root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
eng  = unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_dir()).rstrip('/')
proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
out  = os.path.join(root, 'Packaged'); os.makedirs(out, exist_ok=True)
uat  = os.path.join(eng, 'Build', 'BatchFiles', 'RunUAT.bat')          # RunUAT.sh on macOS/Linux
exe  = os.path.join(eng, 'Binaries', 'Win64', 'UnrealEditor-Cmd.exe')
cmd = (f'"{uat}" BuildCookRun -nop4 -utf8output -project="{proj}" -unrealexe="{exe}" '
       f'-platform=Win64 -clientconfig=Development -installed -nocompileeditor -skipbuildeditor '
       f'-cook -stage -package -pak -iostore -compressed -prereqs -archive -archivedirectory="{out}"')
log = open(os.path.join(out, 'package_log.txt'), 'w')
subprocess.Popen(cmd, shell=True, stdout=log, stderr=subprocess.STDOUT,
                 creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | NEW_PROCESS_GROUP (Windows)
'started'
```

For a Blueprint-only project on an installed engine, replace the build step with `-skipbuild -nocompile -nocompileuat` if UAT tries to compile code it doesn't need or can't (no SDK).

Poll every 30–60 s: look for `BUILD SUCCESSFUL` / `AutomationTool exiting with ExitCode=0`, or the first `Error:` lines. The redirected log can be thin; UAT's own logs are more detailed. On Windows they are under `%APPDATA%\Unreal Engine\AutomationTool\Logs\<engine path with + for separators>\`: `Log.txt` for the run, `Cook-*.txt` for the cook (lines with `Packages Remain` show progress), and `UBA-*.txt` for compile errors. Cook errors usually name the asset; fix it, save, rerun. Expect more than one attempt and leave time for it.

## 3. Check the output yourself

- The archive folder has the executable and the pak/utoc files; note total size against any limit.
- **Smoke test**: launch the packaged exe windowed for ~20–30 s (`-windowed -ResX=1280 -ResY=720`), confirm the process stays alive, then read its log (`<Game>/Saved/Logs/` inside the build) for errors. Kill it afterwards.
- Zip it (`tar -a -c -f Game.zip Folder` on Windows 10+, run detached for large builds), then open the zip and check the exe is inside and no stray `.pdb`, captures or backups are included.

## 4. Play it like a stranger would

A smoke test proves it starts, nothing more. Ask the user to play the unzipped build start to finish (or do it yourself if you can see the screen), and check this list, every item of which was a real problem found only in a packaged build:

- First launch: is there a loading screen, or do meshes and shaders pop in?
- Can the player quit from the title screen, and get back to the main menu from pause/options?
- Does anything look hazier, darker or blurrier than in the editor (fog, depth of field)?
- Is the custom cursor whole, and does hover feedback cover other text?
- Is any highlight or selection shown before the player has done anything?
- Does the frame rate cap hold; are fans quiet?
- Heavy graphics features off by default, with a toggle?
- Do in-game videos play?
- Is progression right for the audience (e.g. all levels unlocked for jam judges who won't play in order)?
- Does the archive name and folder follow the submission rules (e.g. `TeamName_GameName.zip`)?

## 5. Tell the user

Where the build is, its size, what you checked (launched, stayed up, log clean), and what still needs a human: a full playthrough of the packaged build (packaged builds differ from PIE in loading, input focus and settings), and anything platform-specific.
