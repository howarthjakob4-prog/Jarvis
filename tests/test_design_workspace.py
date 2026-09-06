"""Qt integration checks. Run with QT_QPA_PLATFORM=offscreen on headless hosts."""
import unittest
import os
from pathlib import Path
from unittest.mock import patch

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
    from jarvis.ui.design_workspace import install_design_workspace
    from jarvis.brain.design_engine import preset
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, "PyQt6 is required for the workspace integration test")
class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        font_path = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts"/"segoeui.ttf"
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path)); families = QFontDatabase.applicationFontFamilies(font_id)
            if families: cls.app.setFont(QFont(families[0],10))

    def setUp(self):
        class Bridge(QObject): event_received = pyqtSignal(object)
        class Runtime:
            def __init__(self): self.bridge = Bridge(); self.messages = []
            def send_text(self,text): self.messages.append(text)
        self.runtime = Runtime(); self.window = QMainWindow(); self.original = QLabel("Original Jarvis interface"); self.window.setCentralWidget(self.original); self.window.resize(1280,820)
        install_design_workspace(self.window,self.runtime); self.controller = self.window._design_controller; self.controller.open(); self.workspace = self.controller.workspace; self.window.show(); self.app.processEvents()

    def tearDown(self): self.window.close(); self.window.deleteLater(); self.app.processEvents()

    def test_layout_render_and_back_preserve_scene(self):
        self.assertFalse(self.workspace.grab().isNull()); self.assertGreaterEqual(self.workspace.viewport.width(),240); self.assertGreaterEqual(self.workspace.viewport.height(),220)
        self.controller.stack.setCurrentIndex(0); self.assertIs(self.controller.stack.currentWidget(),self.original); self.controller.open(); self.assertIs(self.controller.workspace,self.workspace)

    def test_edit_add_remove_and_send(self):
        self.workspace.parts.setCurrentRow(0); self.workspace.fields["position",0].setValue(3.5); self.assertEqual(self.workspace.scene["objects"][0]["position"][0],3.5)
        count = len(self.workspace.scene["objects"]); self.workspace.add_part(); self.assertEqual(len(self.workspace.scene["objects"]),count+1); self.workspace.remove_part(); self.assertEqual(len(self.workspace.scene["objects"]),count)
        self.workspace.prompt.setText("Design a hangar"); self.workspace.ask(); self.assertEqual(self.runtime.messages,["Design a hangar"])

    def test_runtime_scene_and_unsaved_protection(self):
        self.runtime.bridge.event_received.emit({"type":"design_scene","scene":preset("spaceship")}); self.app.processEvents(); self.assertIn("Spaceship",self.workspace.scene["title"]); self.assertTrue(self.workspace.dirty)
        with patch.object(self.workspace,"confirm_replace",return_value=False):
            self.runtime.bridge.event_received.emit({"type":"design_scene","scene":preset("terrain")}); self.app.processEvents()
        self.assertIn("Spaceship",self.workspace.scene["title"])
        self.runtime.bridge.event_received.emit({"type":"design_scene","scene":{"objects":[]}}); self.app.processEvents(); self.assertIn("Spaceship",self.workspace.scene["title"])

    def test_reference_scene_can_be_presented(self):
        self.runtime.bridge.event_received.emit({"type":"design_scene","scene":preset("achilles")}); self.app.processEvents(); self.assertEqual(self.workspace.scene["reference_asset"],"achilles"); self.assertTrue(self.workspace.reference_box.isVisible()); self.workspace.viewport.top_view(); self.assertFalse(self.workspace.viewport.grab().isNull())


if __name__ == "__main__": unittest.main()
