"""Run the real Jarvis design workspace without starting voice or AI services.

python tools/preview_design.py --preset achilles
python tools/preview_design.py --preset achilles --snapshot build/achilles
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
isolated = ROOT / ".venv" / "design-deps"
if isolated.exists():
    sys.path.insert(0, str(isolated))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default="achilles", choices=["outpost","spaceship","terrain","achilles"])
    parser.add_argument("--snapshot", type=Path, help="Render screenshots and export the scene, then exit")
    args = parser.parse_args()
    if args.snapshot:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
    from jarvis.brain.design_engine import preset, save_scene, obj_text
    from jarvis.ui.design_workspace import install_design_workspace

    class Bridge(QObject):
        event_received = pyqtSignal(object)

    class PreviewRuntime:
        def __init__(self): self.bridge = Bridge()
        def send_text(self, text):
            self.bridge.event_received.emit({"type":"status","status":"Source preview: AI/voice services are not started. Use the local modeling controls."})

    app = QApplication([])
    font_path = Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/"segoeui.ttf"
    if font_path.exists():
        families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(font_path)))
        if families: app.setFont(QFont(families[0],10))
    window = QMainWindow(); window.setWindowTitle("Jarvis 3D Studio — source preview (offline)"); window.resize(1440,940)
    original = QLabel("Jarvis 3D source preview. Open the studio from the bottom toolbar.\nThe installed JARVIS.exe is unchanged; AI and voice are not started in this preview.")
    original.setWordWrap(True); window.setCentralWidget(original)
    runtime = PreviewRuntime(); install_design_workspace(window,runtime); controller = window._design_controller; controller.open()
    scene = preset(args.preset); workspace = controller.workspace
    runtime.bridge.event_received.emit({"type":"design_scene","scene":scene}); workspace.parts.setCurrentRow(-1); window.show(); app.processEvents()
    if args.snapshot:
        destination = args.snapshot.resolve(); destination.mkdir(parents=True,exist_ok=True)
        save_scene(scene,destination/f"{args.preset}.json"); (destination/f"{args.preset}.obj").write_text(obj_text(scene),encoding="utf-8")
        workspace.grab().save(str(destination/"workspace.png")); workspace.viewport.grab().save(str(destination/"three-quarter.png")); workspace.viewport.top_view(); app.processEvents(); workspace.viewport.grab().save(str(destination/"top.png"))
        print(json.dumps({"output":str(destination),"parts":len(scene["objects"])})); window.close(); return 0
    return app.exec()


if __name__ == "__main__": raise SystemExit(main())
