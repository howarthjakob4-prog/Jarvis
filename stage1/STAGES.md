# Feature Roadmap

## Stage 1 — Foundation (this delivery)
- [x] Voice input (offline STT)
- [x] Voice output (offline TTS, natural-voice upgrade path documented)
- [x] Wake command (offline wake word + manual fallback)
- [x] Text chat
- [x] Approved-file-access-only permission system
- [x] App launching (approved list only)
- [x] Clean desktop interface
- [x] Settings: voice, permissions, connected features
- [x] Clear, non-silent error handling throughout

## Stage 2 — Project assistance
- [ ] Project registry (approved project folders get richer treatment:
      recent files, structure summary, quick-open)
- [ ] "What am I working on" / status summaries per project
- [ ] Extension point already exists: `brain/command_router.py` ->
      `register_command()`

## Stage 3 — Development assistance
- [ ] Run/read approved build & test commands (still permission-gated,
      only within approved project folders)
- [ ] Git status/diff read helpers (read-only first; write actions require
      explicit per-action confirmation, never silent)
- [ ] Code-aware Q&A over approved project files

## Stage 4 — 3D design assistance
- [ ] Hook for reviewing/organizing 3D asset folders (approved paths only)
- [ ] Integration point for asset pipeline tasks relevant to Nova Engine 3
      style workflows (model checks, naming conventions, export folder
      organization)
- [ ] Note: actual 3D rendering/viewing is out of scope for a Python
      control-plane app; this stage is about organizing and assisting the
      workflow around your existing 3D tools, not replacing them

## Stage 5 — Tablet support
- [ ] Split UI layer from core logic further (already mostly true — `ui/`
      only talks to `core`/`brain`/`voice` through defined interfaces)
- [ ] Lightweight companion UI (likely a separate client hitting a small
      local API server exposed by `core/`, so the permission system and
      brain stay on the desktop machine as the source of truth)

## Design principles carried through every stage
1. Nothing touches disk except through `files/file_access.py`, and that
   module refuses anything not in `permissions.json`.
2. Nothing launches a process except through `apps/app_launcher.py`,
   against an explicit approved list.
3. Every module reports errors through `core/errors.py` into the same
   UI-visible channel — no module is allowed to catch-and-hide a failure.
4. New capabilities register with `brain/command_router.py` rather than
   being wired directly into the UI, so the UI never needs to change shape
   as features are added.
