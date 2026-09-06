"""Jarvis UI package helpers.

The design workspace and local GGUF model loader are attached to the normal
AdvancedChatWindow when that window class is loaded. Keeping the hooks here
avoids a second application entry point and works for both source runs and
packaged Windows builds.
"""
from jarvis.ui.design_workspace import DesignWorkspace, DesignController, install_design_workspace
from jarvis.ui.local_model_loader import install_local_model_loader


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
]
