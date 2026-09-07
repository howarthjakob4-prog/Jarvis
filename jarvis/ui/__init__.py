"""Jarvis UI package helpers.

The design workspace, local GGUF model loader, Project Nova command-center skin,
and dedicated HUD display mode are attached to the normal AdvancedChatWindow.
"""
from jarvis.ui.design_workspace import DesignWorkspace, DesignController, install_design_workspace
from jarvis.ui.local_model_loader import install_local_model_loader
from jarvis.ui.jarvis_command_center import install_command_center
from jarvis.ui.jarvis_display_mode import install_jarvis_display_mode


def _install_design_hook():
    try:
        from jarvis.ui.advanced_chat_window import AdvancedChatWindow
    except Exception:
        return
    if getattr(AdvancedChatWindow, "_jarvis_design_hooked", False):
        return
    original_init = AdvancedChatWindow.__init__

    def hooked_init(self, runtime, *args, **kwargs):
        original_init(self, runtime, *args, **kwargs)
        install_design_workspace(self, runtime)
        install_local_model_loader(self, runtime)
        install_command_center(self, runtime)
        install_jarvis_display_mode(self, runtime)

    AdvancedChatWindow.__init__ = hooked_init
    AdvancedChatWindow._jarvis_design_hooked = True


_install_design_hook()

DesignWorkspaceController = DesignController
__all__ = [
    "DesignWorkspace",
    "DesignController",
    "DesignWorkspaceController",
    "install_design_workspace",
    "install_local_model_loader",
    "install_command_center",
    "install_jarvis_display_mode",
]
