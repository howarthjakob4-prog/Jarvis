# Nova Frontier 3D concept engine

## Jarvis tool

With a working AI provider, ask: **“Create a Nova Frontier outpost in the 3D studio.”**

The `design_3d` tool accepts `preset_name` or a structured `scene` containing `title`, optional `project`, and `objects`. Each object contains `kind` (`box`, `cylinder`, or `pyramid`), optional `name`, `position` and `size` XYZ arrays, and a six-digit hex `color`. At most 200 parts are allowed.

The local preset and editing controls work without an AI provider. The companion input uses the existing Jarvis request pipeline. This feature does not repair voice recognition or provider connectivity.

This is a **concept-modeling engine**, not a replacement for Blender's production mesh editing, sculpting, rigging, or rendering. Existing Blender tools remain available for those workflows with the Blender integration.

## Source versus installed app

The feature is included in this source tree. An existing installed `JARVIS.exe` does not load changes from this folder; rebuild/reinstall it to use the feature there. Source launch follows the normal project setup (`pip install -e .`, then `python -m jarvis`).

The engine can generate bounded primitive-based concept scenes and export OBJ geometry for Blender. The presets currently include `outpost`, `spaceship`, and `terrain`.
