# UI (UMG) through the MCP: what worked

UI was the largest single piece of rework in the project this skill came from: three passes, the last one a full overhaul on the final day. These notes are how to get it right earlier.

## Contents
- Where UI logic lives
- Audit before you change
- One visual system, generated once
- An apply script you can re-run
- Scale: textures and fonts
- Check every screen
- Shipping checklist

## Where UI logic lives

On UE 5.9 the Blueprint DSL could not edit Widget Blueprint graphs, so events inside the widget (OnClicked and friends) were out of reach. The split that worked:

- **Widget Blueprint = layout only.** Create widgets with the UMG tools, mark the ones you need as variables, style them from Python.
- **An actor Blueprint owns the behaviour.** It holds a reference to the HUD, sets text/visibility/colour each time state changes, and polls buttons in its tick (`Button.IsPressed`), acting on the frame a press starts so one click fires once.

It is less elegant than widget events, but everything stays in text you can read, patch and test.

Two things to try before settling for polling: check `describe_toolsets` on your engine version (if widget graphs are editable there, use events), and try binding the button's `OnClicked` delegate from the actor Blueprint (Bind Event to On Clicked, pointing at a custom event). That is cleaner and fires once per click, but it was not tried in the source project, so `Read` a small hand-made example first to see whether the DSL can express delegate bindings. Polling is the fallback that is known to work; it fires on press, not release.

## Audit before you change

Dump the widget tree with each widget's slot (position, size, anchors, alignment), text, font and visibility, and capture every screen. Most "janky" UI comes from things you can read straight off that dump: three font sizes that are almost the same, panels anchored to different corners, inconsistent padding, two colour schemes.

## One visual system, generated once

Players notice immediately when the HUD, pause menu and title screen look like three different games, and so will the user. Decide on day one:

- one surface material (e.g. paper, glass, metal: pick one),
- one text colour and **one** accent colour, each with a meaning (e.g. accent = the thing you can act on),
- one font family with a small set of sizes,
- one button shape and one panel style.

Generate the textures for that system from a script (Pillow is enough: panels, buttons, tags, stamps, cursor) so they share proportions, colours and noise, and regenerate them all when the design changes. Review the generated sheet as an image before importing.

## An apply script you can re-run

Keep the whole HUD's layout and styling in one editor-Python file with small helpers (`text(name, size, colour)`, `panel(name)`, `place(name, anchor, x, y, w, h)`), and make it safe to run repeatedly: look widgets up by name, create only what's missing, set every property explicitly. Then a redesign is an edit to one file plus one run, and a broken HUD can be rebuilt from scratch.

## Scale: textures and fonts

- **Box (9-slice) brushes**: the margin is a fraction of the texture. Draw the texture at the size you declare in the brush; a 2x texture declared as 1x renders borders twice as thick. If you want sharper art, double both the texture and the declared image size, and halve the margin.
- **Fonts**: UMG sizes are points. In the project this came from, 1 pt rendered as about 1.33 px, so a design in pixels needed `px × 0.75`. Put the conversion in one helper and confirm by measuring a screenshot.
- **Glyphs**: check that the font has every character you use (arrows, symbols, accented letters). Missing ones render as empty boxes, sometimes only in certain widgets.
- **Font loading**: a font used for the first time can show an empty widget for a frame. Use each font once at startup.

## Check every screen

After any UI change, capture and look at each state at 16:9 (and one smaller window): title, gameplay, a tutorial or hint, dialogue/subtitles, pause/options, level select, result, and the ending. Per screen:

- Does anything overlap, and is the stacking order right (menus above subtitles, tooltips above everything)?
- Does hover or selection feedback hide text beneath it?
- Is every element from the same visual system?
- Is anything shown that belongs to a different state (a help button on the ending, a menu fading in under a result card)?
- Does text fit on the intended number of lines?

## Shipping checklist

- Exit on the title screen; Main Menu from pause/options.
- Volume control and, if the game uses heavy rendering features, a quality toggle.
- Custom cursor with padding and a correct hotspot.
- A loading screen/splash in the game's style.
- No debug text, no editor-only shortcuts needed to progress.
