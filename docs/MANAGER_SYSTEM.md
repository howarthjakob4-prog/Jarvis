# JARVIS Manager System

JARVIS is the single top-level coordinator. The manager system classifies each request and delegates it to one specialist area.

## Built-in managers

- **System** — Windows, applications, desktop automation, screen, mouse and keyboard.
- **Files** — approved files and folders only.
- **3D** — Blender and 3D workflows, with approved-file access.
- **Projects** — project tasks, assets, plans and milestones.
- **Communications** — approved email, Discord, calendar and messaging workflows.
- **Security** — permissions, authorization, access boundaries and audits.
- **Memory** — conversation and project memory.

## Rules

1. The user talks to JARVIS, not directly to individual managers.
2. JARVIS selects a manager from the request text/action.
3. Every manager declares its own permissions.
4. File and 3D managers use approved-file permission scopes rather than unrestricted disk access.
5. Unknown commands safely fall back to the System manager rather than disappearing.
6. Managers can be extended with async handlers without changing the central routing contract.

## Python API

```python
from jarvis.managers import ManagerRequest, ManagerSystem

managers = ManagerSystem()
manager = managers.route(ManagerRequest("Open Blender and work on this model"))
print(manager.name)  # 3d

result = await managers.dispatch(ManagerRequest("Remember this project detail"))
```

`list_managers()` provides manager names, descriptions and permission scopes for UI/API exposure.
