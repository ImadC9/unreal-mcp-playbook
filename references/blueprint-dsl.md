# Blueprint DSL: reading and writing graphs as text

The `BlueprintToolsets.BlueprintDslToolset` toolset turns a Blueprint's graphs into S-expressions and back. It's the most reliable way for an agent to write real gameplay logic: you can read it, diff it, patch it, and keep a copy on disk.

**Learn the dialect from the server, not from memory.** The examples below are from real UE 5.9 projects, but the exact spelling can change between versions. Before writing anything, `Read` an existing graph that does something similar (or write a tiny test function and read it back) and copy its forms.

## Tools

| Tool | Arguments (observed) | Notes |
|---|---|---|
| `Read` | `assetPath`, `scope` | `scope` = a function or event name, or `""` for the whole Blueprint. Returns `dsl` and a `revision`. |
| `Edit` | `assetPath`, `revision`, `edits: [{oldString, newString}]` | Exact-match replacements. Fails if `oldString` isn't found exactly once or the revision is stale. Safest for small changes. |
| `Write` | `assetPath`, `scope`, `dsl` | Replaces the functions/events you include. Create a new function's graph first (`BlueprintToolset.AddFunctionGraph`), then write its body. |

Asset paths are package paths without the object suffix: `/Game/MyGame/Blueprints/BP_Board`.

After `Write` or `Edit`: compile, check status, save. A write can succeed and still leave the Blueprint in an error state.

## Forms seen in working graphs

```lisp
(event `self.ReceiveBeginPlay`
  (`MeshComponent.SetScalarParameterValueOnMaterials` (`self.Motes`) "Opacity" 0.7))

(event `self.ReceiveTick`
  (params (DeltaSeconds :type "Float (single-precision)"))
  (set `self.T` (+ (`self.T`) DeltaSeconds)))

(fn `TryCut` (params (Index :type `Integer`))
  (if (or (`self.bWon`) (< Index 0) (>= Index (`self.NumRobots`))) (return))
  (`self.PushUndo`)
  (`KismetArrayLibrary.Array_Set` (`self.Conn`) Index false false)
  (set `self.Cuts` (+ (`self.Cuts`) 1))
  (`self.RefreshVisuals`))

(fn `PopUndo` (returns (Popped :type `Boolean`)) ...)
```

| Thing | Form |
|---|---|
| Read a member variable | ``(`self.Speed`)`` |
| Set a member variable | ``(set `self.Speed` 2.0)`` |
| Local value | `(bind d (- B A))`, then use `d` |
| Call own function | ``(`self.Refresh`)`` |
| Call library / component function | ``(`KismetMathLibrary.Sin` x)``, ``(`StaticMeshComponent.SetStaticMesh` (`self.Mesh`) Mesh)`` |
| Variable on another Blueprint | ``(`/Game/MyGame/Blueprints/BP_Board.bRestoring` (`self.Board`))`` |
| Loop | `(for i (range 70) ...)` |
| Branch | `(if cond then-expr)` |
| Switch on int | ``(switch int Index (:`0` ...) (:`1` ...))`` |
| Select | ``(select `bool` cond :`false` a :`true` b)`` |
| Struct literal | `(0.0 0.0 1.0)` for vectors, ``(make `IntPoint` 2 3)`` |
| Arrays | ``(`|MakeArray` "a" "b")``, ``(`|GetArrayItem` (`self.Pos`) i)`` |
| Param types | `` `Integer` ``, `` `Boolean` ``, `` `String` ``, `` `Float (double-precision)` ``, `` `Vector Structure` ``, `` `LinearColor Structure` ``, `` `Static Mesh Object Reference` ``, `` `/Game/MyGame/Blueprints/BP_Robot Object Reference` `` |

## Working patterns

**Patch, don't rewrite.** Read the function, make string replacements, send them with `Edit`. Check each `oldString` occurs exactly once before sending; if it doesn't, widen it. This keeps unrelated logic untouched and avoids reformatting the whole graph.

**Keep a text copy.** Before a big change, `Read` every Blueprint you'll touch and write the DSL to `Saved/<agent>/dsl/<BP>.dsl`. It's a cheap, diffable backup and lets you search logic with grep.

**Generate repetitive logic.** Level data, lookup tables and per-item setup are easiest to generate from code (a small template function in your script that emits DSL), then write once. Validate the data outside the engine first (e.g. a solver for puzzle levels) so the Blueprint only has to load known-good data.

**Write in small batches.** One function per write while you learn the dialect; after a compile error, read the function back to see what the server actually built.

**Determinism for puzzles.** If the game is turn-based, put the whole rules step in one function (resolve, then apply) with a fixed order, keep undo as plain arrays of state, and test it by calling it from Python with known inputs. That's what makes automated regression runs possible.

**Widget Blueprints.** On UE 5.9 the DSL toolset did not support Widget Blueprint graphs, so a button could not be given an OnClicked event this way. What worked: mark the widgets as variables, and let an actor Blueprint that owns the HUD reference do the work in its tick, e.g. ``(if (`Button.IsPressed` (`/Game/MyGame/UI/WBP_HUD.StartButton` (`self.Hud`))) (`self.StartGame`))``, with a "was pressed last frame" flag so one click fires once. The same Blueprint sets text, visibility and colours on the widgets. Check whether your engine version has lifted this limit, and whether the DSL can bind the button's `OnClicked` delegate from the actor Blueprint (cleaner, untested here), before choosing the polling workaround.

**One engine for real moves and previews.** If the game shows a preview of a move, compute it with the same resolve function as the real move (run it on a copy of the state). Two implementations will disagree.

**Logic that outlives its purpose.** When a screen flow changes, old timing rules ("show the menu 2.4 s after the ending starts") keep firing. Search the dump for every place that writes the widget or variable you are changing.

## Pitfalls seen

- Float literal types: tick deltas are single precision, most math is double. When a pin type mismatch is reported, convert explicitly (``(`KismetMathLibrary.Conv_IntToDouble` i)``).
- `Fraction`, `%` and sine-based hashes go negative for negative inputs. Clamp or use `abs` before using them for positions or scales.
- Writing a function that the graph already defines with different parameters can leave stale pins; compile and read back.
- Text shown to the player: convert strings explicitly (``(`KismetTextLibrary.Conv_StringToText` Msg)``).
