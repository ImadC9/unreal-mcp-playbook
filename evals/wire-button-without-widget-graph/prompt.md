---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

In my UE 5.9 project the HUD is /Game/Puzzle/UI/WBP_HUD and the game logic is in the actor Blueprint /Game/Puzzle/Blueprints/BP_Board, which has a Hud variable pointing at the widget and a RestartLevel function. I added a Button called RestartButton to the HUD through the Unreal MCP, but when I try to add an OnClicked event to the widget blueprint with the Blueprint DSL tool it errors: widget blueprints aren't supported. How do I make the button work, still through the MCP? Put the approach and the exact calls in button_plan.md.
