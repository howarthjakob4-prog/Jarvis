"""Qt integration checks. Run with QT_QPA_PLATFORM=offscreen on headless hosts."""
import unittest

try:
    from PyQt6.QtCore import QObject, pyqtSignal
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

    def setUp(self):
        class Bridge(QObject):
            event_received = pyqtSignal(object)
        class Runtime:
            def __init__(self):
                self.bridge = Bridge()
                self.messages = []
                self.plugin_manager = None
            def send_text(self, text):
                self.messages.append(text)
        self.runtime = Runtime()
        self.window = QMainWindow()
        self.original = QLabel("Original Jarvis interface")
        self.window.setCentralWidget(self.original)
        self.window.resize(1200, 800)
        install_design_workspace(self.window, self.runtime)
        self.controller = self.window._design_controller
        self.controller.open()
        self.workspace = self.controller.workspace
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_layout_render_and_back_preserve_scene(self):
        self.assertFalse(self.workspace.grab().isNull())
        self.workspace.viewport.resize(240, 220)
        self.workspace.viewport.update()
        self.app.processEvents()
        self.assertIs(self.controller.workspace, self.workspace)

    def test_edit_add_remove_and_send(self):
        self.workspace.parts.setCurrentRow(0)
        self.workspace.position[0].setValue(3.5)
        self.assertEqual(self.workspace.scene["objects"][0]["position"][0], 3.5)
        count = len(self.workspace.scene["objects"])
        self.workspace.add_part()
        self.assertEqual(len(self.workspace.scene["objects"]), count + 1)
        self.workspace.remove_part()
        self.workspace.prompt.setEditText("Design a hangar")
        self.workspace.ask()
        self.assertEqual(self.runtime.messages, ["Design a hangar"])

    def test_runtime_scene_event(self):
        scene = preset("spaceship")
        self.runtime.bridge.event_received.emit({"type": "design_scene", "scene": scene})
        self.app.processEvents()
        self.assertIn("Spaceship", self.workspace.scene["title"])


if __name__ == "__main__":
    unittest.main()
