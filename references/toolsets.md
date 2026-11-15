# Toolsets and call shapes that worked

Names below were observed on UE 5.9's server. Versions differ: run `describe_tools` before relying on a parameter name. Calls go through `call_tool(toolset_name, tool_name, arguments)`; inside `execute_python` use `await call_tool('<Toolset>.<Tool>', **kwargs)`.

Parameter casing is not uniform. Calls that worked from Python: `...BlueprintDslToolset.Read(assetPath=..., scope='')` (camelCase; `AssetPath=` failed), `...BlueprintToolset.CompileBlueprint(Blueprint=bp, bWarningsAsErrors=False)` and `...WidgetBlueprintEditorSubsystem.CreateAndAddWidget(WidgetBlueprint=..., WidgetClass=..., WidgetDisplayName=..., ParentWidget=...)` (PascalCase, live objects). Over JSON the same tools took camelCase keys with `{refPath}` references. Results are dicts: the DSL `Read` returned `r['dsl']` and `r['revision']`.

## Contents
- Python scripting
- Blueprints
- UMG widgets
- Play-In-Editor and capture
- Useful Python recipes

## Python scripting

Toolset `editor_toolset.toolsets.python_scripting.PythonScriptingTools`, tool `execute_python`.

```json
{"script": {"content": "unreal.SystemLibrary.get_engine_version()", "language": "Python"}}
```

- `unreal` is already imported. The last expression is returned as `returnValue` (JSON-serialisable values work best: dict, list, str, numbers). Return `json.dumps(...)` for nested structures.
- Top-level `await` works, so you can call other tools: `r = await call_tool('BlueprintToolsets.BlueprintDslToolset.Read', assetPath=p, scope='')`.
- Module-level state persists between calls within the editor session (e.g. stash helpers and status on `unreal._agent = {}`), which helps for multi-step jobs: start a long async job, return, and read `unreal._agent['STATUS']` from later calls. Don't rely on it across editor restarts.
- Load your own script files instead of resending them: `exec(open(unreal.Paths.project_saved_dir() + 'Agent/recorder.py').read())`.
- Exceptions come back as tool errors with the traceback; read it, it's usually precise.

## Blueprints

Toolset `BlueprintToolsets.BlueprintDslToolset`: `Read`, `Write`, `Edit`. See `blueprint-dsl.md`.

Toolset `BlueprintToolsets.BlueprintToolset` (observed): `AddFunctionGraph {blueprint:{refPath}, graphName}`, `CompileBlueprint {blueprint:{refPath}}`, `ListVariables`, `AddVariable`, plus tools for components and nodes.

Other toolsets that earned their keep: `EditorToolset.TextureToolset.ImportFile` (textures), `ConsoleToolset.LogsToolset.GetLogEntries {logCategory}` (read `LogBlueprint` runtime errors after a playtest), `EditorToolset.AssetToolset`, `EditorToolset.LevelToolset`.

Python equivalents that are often simpler:
```python
bp = unreal.load_asset('/Game/MyGame/Blueprints/BP_Board')
BEL = unreal.BlueprintEditorLibrary
BEL.add_member_variable(bp, 'Speed', BEL.get_basic_type_by_name('real'))
BEL.compile_blueprint(bp)
str(bp.get_editor_property('status'))   # BS_UP_TO_DATE is good; BS_ERROR means read the compiler log
```

Creating a Blueprint and adding components from Python:
```python
AT = unreal.AssetToolsHelpers.get_asset_tools()
f = unreal.BlueprintFactory(); f.set_editor_property('parent_class', unreal.Actor)
bp = AT.create_asset('BP_Motes', '/Game/MyGame/Blueprints', unreal.Blueprint, f)
ss = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem); L = unreal.SubobjectDataBlueprintFunctionLibrary
handles = ss.k2_gather_subobject_data_for_blueprint(bp)
root = next(h for h in handles if L.is_root_component(L.get_data(h)))
h, _ = ss.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.InstancedStaticMeshComponent, blueprint_context=bp))
ss.rename_subobject(h, unreal.Text('Motes'))
comp = L.get_object(L.get_data(h))
comp.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)   # see gotchas
```

## UMG widgets

Toolset `UMGEditor.WidgetBlueprintEditorSubsystem` (observed): `CreateAndAddWidget {widgetBlueprint, widgetClass, widgetDisplayName, parentWidget, childIndex?}`, `ToggleWidgetAsVariable {widgetBlueprint, widget, bIsVariable}`, `RemoveWidget`, `CompileWidgetBlueprint`.

Widgets are addressed by object path: `/Game/MyGame/UI/WBP_HUD.WBP_HUD:WidgetTree.<WidgetName>`. Create structure with the tools, then style in Python:

```python
P = '/Game/MyGame/UI/WBP_HUD.WBP_HUD:WidgetTree.'
W = lambda n: unreal.load_object(None, P + n)
t = W('LevelTitle')
f = t.get_editor_property('font'); f.set_editor_property('size', 28); f.set_editor_property('letter_spacing', 120)
t.set_editor_property('font', f)
t.set_color_and_opacity(unreal.SlateColor(specified_color=unreal.LinearColor(0.95, 0.92, 0.86, 1)))
s = t.get_editor_property('slot')          # CanvasPanelSlot
s.set_anchors(unreal.Anchors(minimum=unreal.Vector2D(0.5, 0), maximum=unreal.Vector2D(0.5, 0)))
s.set_alignment(unreal.Vector2D(0.5, 0)); s.set_position(unreal.Vector2D(0, 40)); s.set_auto_size(True)
```
Then compile the widget Blueprint and save. Mark widgets you need from graphs as variables. Widget names must be unique in the tree; check with `unreal.find_object(None, P + name)` first.

For UI logic, a consistent look, texture scale and the per-screen checklist, read `ui.md`.

## Play-In-Editor and capture

Toolset `EditorToolset.EditorAppToolset` (observed): `StartPIE {options:{playMode:'PlayMode_InEditorFloating'}}`, `StopPIE`, `IsPIERunning`. From Python the equivalent is `unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()` / `.editor_request_end_play()`; both are asynchronous, so return and poll in a later call.

Toolset `SceneCaptureToolset.SceneCaptureToolset`: `CaptureGameViewport {world: null, maxResolution: 1600}` returns `{image: {data: <base64 PNG>}}`. Write it to disk from Python rather than shipping base64 through your context.

Game world and actors during PIE:
```python
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()   # None if PIE isn't running
board = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
             if a.get_class().get_name() == 'BP_Board_C')
board.call_method('ApplyMove', (1,))          # call a Blueprint function with args
board.get_editor_property('bWon')             # read a Blueprint variable
```

## Useful Python recipes

```python
# Project paths
proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())

# Inventory of a content folder
ar = unreal.AssetRegistryHelpers.get_asset_registry()
[(str(a.package_name), str(a.asset_class_path.asset_name)) for a in ar.get_assets_by_path('/Game/MyGame', recursive=True)]

# Level actors
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
[a.get_actor_label() for a in EAS.get_all_level_actors()]

# Import files (fonts, meshes from .glb/.fbx, textures, audio)
t = unreal.AssetImportTask()
for k, v in dict(filename=proj + 'Import/robot.glb', destination_path='/Game/MyGame/Models/robot',
                 automated=True, replace_existing=True, save=True).items():
    t.set_editor_property(k, v)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])

# Save everything dirty, report what is still dirty
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]

# In-game video (tutorial clips, cutscenes): files must live under Content/Movies to be packaged
at = unreal.AssetToolsHelpers.get_asset_tools(); D = '/Game/MyGame/UI/Video'
mp = at.create_asset('MP_Clip', D, unreal.MediaPlayer, unreal.MediaPlayerFactoryNew())
mp.set_editor_property('play_on_open', True); mp.set_editor_property('loop', True)
mt = at.create_asset('MT_Clip', D, unreal.MediaTexture, unreal.MediaTextureFactoryNew())
mt.set_editor_property('media_player', mp)          # use MT_Clip as an Image brush in the widget
src = at.create_asset('FMS_Intro', D, unreal.FileMediaSource, unreal.FileMediaSourceFactoryNew())
src.set_file_path('./Movies/intro.mp4')              # relative path, so it survives packaging
# check it really decodes: mp.open_source(src); wait ~2 s; mp.is_playing(), mp.get_time()

# Console commands (e.g. turn off on-screen debug messages)
unreal.SystemLibrary.execute_console_command(None, 'DisableAllScreenMessages')
```
