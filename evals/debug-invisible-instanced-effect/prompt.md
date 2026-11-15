---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

I made BP_Motes, an actor with an InstancedStaticMeshComponent: 70 instances added in BeginPlay, then moved every Tick with UpdateInstanceTransform, positions from Fraction(Sin(i*12.9898)*43758.55) mapped into the room. I dropped one in the level. It compiles fine but in PIE I see nothing at all. I already doubled the size and the glow twice. I'm driving the editor through the Unreal MCP server from Claude Code. What's going on and what should we do next? Write the diagnosis plan plus the exact python you'd run through the MCP into debug_plan.md
