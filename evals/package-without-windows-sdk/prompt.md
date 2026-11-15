---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

UE 5.9 from the Epic launcher, Blueprint-only project, I'm driving the editor through the Unreal MCP server. Packaging for Windows failed twice: first it couldn't compile the game exe (I don't have Visual Studio or the Windows SDK installed and no time to install them tonight), then after a tweak it complained about needing a temporary target because of a plugin. The jam deadline is in 5 hours. Write package_plan.md: what's going wrong, the exact steps and commands you'd run through the MCP to get a build out, and how you'd check it.
