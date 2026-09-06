"""Expose the local concept engine to Jarvis's AI tool registry."""
from jarvis.plugins.base import Plugin
from jarvis.models import ToolDefinition
from jarvis.brain.design_engine import preset, validate_scene


class DesignPlugin(Plugin):
    def __init__(self):
        super().__init__("design_3d")
        self._present = None

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def set_presenter(self, presenter):
        """Install an optional GUI presenter callback."""
        self._present = presenter

    def get_tools(self):
        return [(ToolDefinition(name="design_3d", description=(
            "Create and present an editable 3D concept for Nova Frontier. Jarvis moves to the "
            "left and shows the model on the right. Use a preset or supply a scene of box, "
            "cylinder, pyramid and convex extruded prism parts; Y is up. "
            "Use the achilles preset for the supplied reference-image study. "
            "Prism profiles are normalized convex XZ points; size scales them and rotation_y is degrees. "
            "Units default to meters; reference studies use unmeasured concept units. "
            "This creates concept geometry, not finished production assets. "
            "The user can rotate, edit, save and export OBJ for Blender in the workspace."),
            parameters={"type": "object", "properties": {
                "preset_name": {"type": "string", "enum": ["outpost", "spaceship", "terrain", "achilles"]},
                "scene": {"type": "object", "properties": {
                    "title": {"type": "string"}, "project": {"type": "string"},
                    "units": {"type": "string", "enum": ["meters", "concept"]},
                    "reference_asset": {"type": "string", "enum": ["achilles"]},
                    "objects": {"type": "array", "minItems": 1, "maxItems": 200,
                        "items": {"type": "object", "properties": {
                            "name": {"type": "string"},
                            "kind": {"type": "string", "enum": ["box", "cylinder", "pyramid", "prism"]},
                            "rotation_y": {"type": "number"},
                            "profile": {"type": "array", "minItems": 3, "maxItems": 32,
                                "items": {"type": "array", "minItems": 2, "maxItems": 2,
                                    "items": {"type": "number", "minimum": -1, "maximum": 1}}},
                            "position": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                            "size": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                            "color": {"type": "string"}}, "required": ["kind"]}}}, "required": ["objects"]}}}), self.create_design)]

    async def create_design(self, preset_name="outpost", scene=None, **_):
        try:
            design = validate_scene(scene) if scene is not None else preset(preset_name)
        except (ValueError, TypeError, OverflowError) as exc:
            return f"Design not created: {exc}"

        payload = {"type": "design_scene", "scene": design}
        if self._present is not None:
            result = self._present(payload)
            if hasattr(result, "__await__"):
                await result
        else:
            try:
                from jarvis.app import get_runtime
                runtime = get_runtime()
                if runtime is not None and hasattr(runtime, "_emit_ui_event"):
                    runtime._emit_ui_event(payload)
                else:
                    return {"status": "created", "title": design["title"],
                            "parts": len(design["objects"]), "scene": design,
                            "message": "Design created, but no desktop workspace is attached in this runtime."}
            except Exception:
                return {"status": "created", "title": design["title"],
                        "parts": len(design["objects"]), "scene": design,
                        "message": "Design created, but no desktop workspace is attached in this runtime."}
        return (f"Created {design['title']} ({len(design['objects'])} parts) and requested "
                "presentation in the 3D workspace. If there are unsaved edits, "
                "the workspace asks before replacing them.")
