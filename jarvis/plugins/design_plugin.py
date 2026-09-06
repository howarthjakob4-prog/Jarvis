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
        """Optional GUI callback supplied by a workspace that can display design_scene payloads."""
        self._present = presenter

    def get_tools(self):
        return [(
            ToolDefinition(
                name="design_3d",
                description=(
                    "Create and present an editable 3D concept for Nova Frontier. Jarvis moves to the "
                    "left and shows the model on the right. Use a preset or supply a scene of box, "
                    "cylinder and pyramid parts; Y is up, sizes are full dimensions in meters. "
                    "This creates concept geometry, not finished production assets. "
                    "The user can rotate, edit, save and export OBJ for Blender in the workspace."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "preset_name": {"type": "string", "enum": ["outpost", "spaceship", "terrain"]},
                        "scene": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "project": {"type": "string"},
                                "objects": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 200,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "kind": {"type": "string", "enum": ["box", "cylinder", "pyramid"]},
                                            "position": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                                            "size": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                                            "color": {"type": "string"},
                                        },
                                        "required": ["kind"],
                                    },
                                },
                            },
                            "required": ["objects"],
                        },
                    },
                },
            ),
            self.create_design,
        )]

    async def create_design(self, preset_name="outpost", scene=None, **_):
        try:
            design = validate_scene(scene) if scene is not None else preset(preset_name)
        except (ValueError, TypeError, OverflowError) as exc:
            return f"Design not created: {exc}"
        if self._present is None:
            return {
                "status": "created",
                "title": design["title"],
                "parts": len(design["objects"]),
                "scene": design,
                "message": "Design workspace is unavailable in this runtime; scene data was created successfully.",
            }
        result = self._present("design_scene", {"scene": design})
        if hasattr(result, "__await__"):
            await result
        return f"Presented {design['title']} ({len(design['objects'])} parts) in the 3D workspace."
