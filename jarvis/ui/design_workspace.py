"""Software-rendered concept viewport, shared by the native and web shells."""
from __future__ import annotations

import json
import math
from pathlib import Path

from PyQt6.QtCore import Qt, QPointF, QObject, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QImage
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QDoubleSpinBox, QFormLayout, QFileDialog, QMessageBox,
    QLineEdit, QSplitter, QStackedWidget, QToolBar, QColorDialog, QScrollArea, QDialog)

from jarvis.brain.design_engine import mesh, preset, validate_scene, save_scene, obj_text
from jarvis.brain.design_renderer import render_meshes


class DesignViewport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = preset()
        self.selected = -1
        self.setMinimumSize(240, 220)
        self.setToolTip("Drag to orbit · scroll to zoom · double-click to reset")
        self.reset_camera()

    def reset_camera(self):
        self.yaw, self.pitch, self.zoom = -.65, .5, 1.0
        if self.scene.get("reference_asset") == "achilles":
            self.yaw, self.pitch, self.zoom = 0, 1.16, 1.23
        self.update()

    def top_view(self):
        self.yaw, self.pitch = 0, math.pi/2
        self.update()

    def mousePressEvent(self, event): self._last = event.position()
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position() - self._last
            self.yaw += delta.x() * .01
            self.pitch = max(-1.4, min(1.4, self.pitch + delta.y() * .01))
            self._last = event.position(); self.update()
    def wheelEvent(self, event):
        self.zoom = max(.2, min(5, self.zoom * (1.12 if event.angleDelta().y() > 0 else 1/1.12))); self.update()
    def mouseDoubleClickEvent(self, event): self.reset_camera()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#09131e"))
        meshes = [mesh(obj) for obj in self.scene["objects"]]
        all_vertices = [v for vertices, _ in meshes for v in vertices]
        lo = [min(v[i] for v in all_vertices) for i in range(3)]; hi = [max(v[i] for v in all_vertices) for i in range(3)]
        center = [(a+b)/2 for a,b in zip(lo,hi)]; span = max(max(b-a for a,b in zip(lo,hi)), .1)
        scale = min(self.width(), self.height()) * .67 / span * self.zoom
        cy, sy = math.cos(self.yaw), math.sin(self.yaw); cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        def transform(v):
            x,y,z = [v[i]-center[i] for i in range(3)]; x,z = x*cy-z*sy, x*sy+z*cy; y,z = y*cp-z*sp, y*sp+z*cp; return x,y,z
        def screen(v): return QPointF(self.width()/2+v[0]*scale, self.height()/2-v[1]*scale)
        painter.setPen(QPen(QColor("#193044"), 1)); extent = span * .8
        for i in range(-5,6):
            p = i*extent/5
            painter.drawLine(screen(transform((center[0]+p,lo[1],center[2]-extent))), screen(transform((center[0]+p,lo[1],center[2]+extent))))
            painter.drawLine(screen(transform((center[0]-extent,lo[1],center[2]+p))), screen(transform((center[0]+extent,lo[1],center[2]+p))))
        renderables = []
        for index, (vertices, faces) in enumerate(meshes):
            rotated = [transform(v) for v in vertices]; color = QColor(self.scene["objects"][index]["color"]); rgb = (color.red(),color.green(),color.blue())
            if index == self.selected: rgb = tuple(int(c*.6+h*.4) for c,h in zip(rgb,(255,207,128)))
            renderables.append((rotated,faces,rgb))
        pixels = render_meshes(renderables,self.width(),self.height(),scale)
        raster = QImage(pixels.data,self.width(),self.height(),pixels.strides[0],QImage.Format.Format_RGBA8888)
        painter.drawImage(0,0,raster); painter.setPen(QColor("#8ca6ba"))
        units = "UNMEASURED CONCEPT" if self.scene.get("units") == "concept" else "METERS"
        painter.drawText(16,25,f"ORTHOGRAPHIC STUDY  /  Y UP  /  {units}")
        painter.drawText(16,self.height()-16,"Drag to orbit · Scroll to zoom · Double-click to reset"); painter.end()


class CompanionOrb(QWidget):
    def __init__(self, parent=None): super().__init__(parent); self.setFixedSize(180, 160)
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing); center = QPointF(90, 80); painter.setBrush(QColor("#102a3c"))
        for radius, color in [(70,"#234457"),(59,"#3c7085"),(46,"#67cbd4")]: painter.setPen(QPen(QColor(color), 2)); painter.drawEllipse(center, radius, radius)
        painter.setPen(QColor("#dfedf4")); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "JARVIS"); painter.end()


class DesignWorkspace(QWidget):
    def __init__(self, runtime, back, parent=None):
        super().__init__(parent); self.runtime = runtime; self.scene = preset(); self.dirty = False; self._loading = False
        self.setStyleSheet("QWidget {background:#0d1825;color:#dfedf4;} QPushButton,QComboBox,QLineEdit,QDoubleSpinBox {background:#1a3043;color:#dfedf4;padding:7px;border:1px solid #34516a;border-radius:5px;} QListWidget {background:#102232;} QLabel {background:transparent;}")
        layout = QHBoxLayout(self); companion = QWidget(); companion.setFixedWidth(200); left = QVBoxLayout(companion)
        left.addWidget(QLabel("J A R V I S")); left.addWidget(CompanionOrb()); left.addWidget(QLabel("Design companion")); self.status = QLabel("Ready to explore your idea"); self.status.setWordWrap(True); left.addWidget(self.status)
        left.addWidget(QLabel("NOVA FRONTIER\n3D concept workspace")); self.prompt = QLineEdit(); self.prompt.setPlaceholderText("Ask Jarvis…"); self.prompt.returnPressed.connect(self.ask); left.addWidget(self.prompt)
        ask = QPushButton("Send to Jarvis"); ask.clicked.connect(self.ask); left.addWidget(ask)
        self.reference_box = QWidget(); reference_layout = QVBoxLayout(self.reference_box); reference_layout.setContentsMargins(0,12,0,0); reference_layout.addWidget(QLabel("SOURCE REFERENCE")); self.reference_thumb = QLabel(); reference_layout.addWidget(self.reference_thumb)
        reference_button = QPushButton("View reference"); reference_button.clicked.connect(self.show_reference); reference_layout.addWidget(reference_button); reference_note = QLabel("Image-guided concept.\nDepth and underside inferred."); reference_note.setWordWrap(True); reference_layout.addWidget(reference_note); left.addWidget(self.reference_box); left.addStretch()
        note = QLabel("Local modeling works offline.\nAI requests need a configured provider."); note.setWordWrap(True); left.addWidget(note); close = QPushButton("Back to Jarvis"); close.clicked.connect(back); left.addWidget(close); layout.addWidget(companion)
        body = QWidget(); right = QVBoxLayout(body); self.title = QLineEdit(self.scene["title"]); self.title.textEdited.connect(self.rename); right.addWidget(self.title); buttons = QHBoxLayout(); self.presets = QComboBox(); self.presets.addItems(["outpost","spaceship","terrain","achilles"]); buttons.addWidget(self.presets)
        for label, handler in [("New concept",self.new_concept),("Open",self.open_scene),("Save",self.save),("Export OBJ",self.export)]: button = QPushButton(label); button.clicked.connect(handler); buttons.addWidget(button)
        right.addLayout(buttons); split = QSplitter(Qt.Orientation.Horizontal); self.viewport = DesignViewport(); camera_row = QHBoxLayout()
        for text, slot in [("Top view",self.viewport.top_view),("3D view",self.viewport.reset_camera)]: button = QPushButton(text); button.clicked.connect(slot); camera_row.addWidget(button)
        right.addLayout(camera_row); split.addWidget(self.viewport); inspector = QWidget(); form = QVBoxLayout(inspector); form.addWidget(QLabel("PARTS / TRANSFORM")); self.parts = QListWidget(); self.parts.currentRowChanged.connect(self.select); form.addWidget(self.parts); self.kind = QComboBox(); self.kind.addItems(["box","cylinder","pyramid","prism"]); form.addWidget(self.kind)
        for label, handler in [("Add part",self.add_part),("Remove selected",self.remove_part),("Part color",self.color)]: button = QPushButton(label); button.clicked.connect(handler); form.addWidget(button)
        fields = QFormLayout(); self.fields = {}
        for prop in ("position","size"):
            for axis in range(3):
                field = QDoubleSpinBox(); field.setRange(.01 if prop == "size" else -1000,1000); field.setDecimals(3); field.setSingleStep(.1); field.valueChanged.connect(self.transform); fields.addRow(f"{prop.title()} {'XYZ'[axis]}",field); self.fields[prop,axis] = field
        form.addLayout(fields); self.rotation = QDoubleSpinBox(); self.rotation.setRange(-360,360); self.rotation.setSuffix("°"); self.rotation.setSingleStep(5); self.rotation.valueChanged.connect(self.transform); fields.addRow("Rotation Y",self.rotation)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(inspector); scroll.setMinimumWidth(195); split.addWidget(scroll); split.setSizes([750,220]); right.addWidget(split,1); self.notice = QLabel("Concept geometry · OBJ exports geometry only; save JSON to keep colors and editability."); self.notice.setWordWrap(True); right.addWidget(self.notice); layout.addWidget(body,1); self.set_scene(self.scene)

    def ask(self):
        text = self.prompt.text().strip()
        if text: self.runtime.send_text(text); self.prompt.clear()
    def confirm_replace(self): return not self.dirty or QMessageBox.question(self,"Unsaved design","Replace the current unsaved design?",QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
    def set_scene(self, scene):
        self.scene = validate_scene(scene); self.title.setText(self.scene["title"]); self.viewport.scene = self.scene; is_reference = self.scene.get("reference_asset") == "achilles"; self.reference_box.setVisible(is_reference)
        if is_reference:
            self.presets.setCurrentText("achilles"); self.reference_pixmap = QPixmap(str(Path(__file__).parent/"assets"/"achilles-reference.jpg"))
            if self.reference_pixmap.isNull(): self.reference_thumb.setText("Reference image is not bundled in this build.")
            else: self.reference_thumb.setPixmap(self.reference_pixmap.scaledToWidth(180,Qt.TransformationMode.SmoothTransformation))
            self.notice.setText(f"{len(self.scene['objects'])} editable parts · Reference interpretation, not a dimensional reconstruction. Save JSON to keep colors.")
        else: self.notice.setText("Concept geometry · OBJ exports geometry only; save JSON to keep colors and editability.")
        self.parts.clear(); self.parts.addItems([o["name"] for o in self.scene["objects"]]); self.parts.setCurrentRow(0); self.viewport.reset_camera(); self.dirty = False
    def show_reference(self):
        if getattr(self, "reference_pixmap", QPixmap()).isNull(): QMessageBox.information(self, "Reference unavailable", "The reference image is not bundled in this build."); return
        dialog = QDialog(self); dialog.setWindowTitle("Achilles — supplied design reference"); dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose); layout = QVBoxLayout(dialog); label = QLabel(); label.setPixmap(self.reference_pixmap.scaledToWidth(1000,Qt.TransformationMode.SmoothTransformation)); layout.addWidget(label); self._reference_dialog = dialog; dialog.show()
    def rename(self, value): self.scene["title"] = value[:120]; self.dirty = True
    def select(self, row):
        self.viewport.selected = row; self._loading = True; self.rotation.setEnabled(row >= 0)
        if row >= 0: self.rotation.setValue(self.scene["objects"][row].get("rotation_y",0))
        for (prop,axis),field in self.fields.items(): field.setEnabled(row >= 0); field.setValue(self.scene["objects"][row][prop][axis]) if row >= 0 else None
        self._loading = False; self.viewport.update()
    def transform(self):
        row = self.parts.currentRow()
        if self._loading or row < 0: return
        self.scene["objects"][row]["rotation_y"] = self.rotation.value()
        for (prop,axis),field in self.fields.items(): self.scene["objects"][row][prop][axis] = field.value()
        self.dirty = True; self.viewport.update()
    def add_part(self):
        if len(self.scene["objects"]) >= 200: self.notice.setText("The concept limit is 200 parts."); return
        name = f"{self.kind.currentText().title()} {len(self.scene['objects'])+1}"; self.scene["objects"].append(dict(name=name,kind=self.kind.currentText(),position=[0,.5,0],size=[1,1,1],color="#67cbd4"))
        if self.kind.currentText() == "prism": self.scene["objects"][-1]["profile"] = [[-.5,-.5],[.5,-.5],[0,.5]]
        self.parts.addItem(name); self.parts.setCurrentRow(self.parts.count()-1); self.dirty = True
    def remove_part(self):
        row = self.parts.currentRow()
        if row < 0 or len(self.scene["objects"]) == 1: self.notice.setText("Keep at least one part in the scene."); return
        self.parts.blockSignals(True); self.scene["objects"].pop(row); self.parts.takeItem(row); self.parts.blockSignals(False); self.parts.setCurrentRow(min(row,self.parts.count()-1)); self.select(self.parts.currentRow()); self.dirty = True
    def color(self):
        row = self.parts.currentRow()
        if row < 0: return
        color = QColorDialog.getColor(QColor(self.scene["objects"][row]["color"]),self)
        if color.isValid(): self.scene["objects"][row]["color"] = color.name(); self.dirty = True; self.viewport.update()
    def new_concept(self):
        if self.confirm_replace(): self.set_scene(preset(self.presets.currentText())); self.dirty = True
    def open_scene(self):
        if not self.confirm_replace(): return
        path,_ = QFileDialog.getOpenFileName(self,"Open design","","Jarvis design (*.json)")
        if path:
            try:
                if Path(path).stat().st_size > 2_000_000: raise ValueError("Design file exceeds 2 MB")
                self.set_scene(json.loads(Path(path).read_text(encoding="utf-8")))
            except (OSError,ValueError,TypeError,OverflowError) as exc: QMessageBox.warning(self,"Cannot open design",str(exc))
    def save(self):
        path,_ = QFileDialog.getSaveFileName(self,"Save design","nova-frontier.json","Jarvis design (*.json)")
        if path:
            try: save_scene(self.scene,path); self.dirty = False; self.notice.setText(f"Saved: {path}")
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"Cannot save design",str(exc))
    def export(self):
        path,_ = QFileDialog.getSaveFileName(self,"Export for Blender","nova-frontier.obj","Wavefront OBJ (*.obj)")
        if path:
            try: Path(path).write_text(obj_text(self.scene),encoding="utf-8"); self.notice.setText(f"Exported {path} · Blender: File → Import → Wavefront OBJ; set Y as up.")
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"Cannot export design",str(exc))


class DesignController(QObject):
    def __init__(self, window, runtime):
        super().__init__(window); self.window = window; self.runtime = runtime; self.workspace = None; self.stack = None
        toolbar = QToolBar("Design",window); toolbar.setObjectName("novaFrontierToolbar"); toolbar.setMovable(False); toolbar.addAction("Nova Frontier · 3D Studio",self.open); window.addToolBar(Qt.ToolBarArea.BottomToolBarArea,toolbar); runtime.bridge.event_received.connect(self.on_event)
    def open(self):
        if self.workspace is None:
            original = self.window.takeCentralWidget(); self.stack = QStackedWidget(); self.stack.addWidget(original); self.workspace = DesignWorkspace(self.runtime,lambda:self.stack.setCurrentIndex(0)); self.stack.addWidget(self.workspace); self.window.setCentralWidget(self.stack)
        self.stack.setCurrentIndex(1)
    @pyqtSlot(object)
    def on_event(self,payload):
        if payload.get("type") == "design_scene":
            try: scene = validate_scene(payload["scene"])
            except (KeyError,ValueError,TypeError,OverflowError): return
            self.open()
            if self.workspace.confirm_replace(): self.workspace.set_scene(scene); self.workspace.dirty = True
        elif self.workspace is not None and payload.get("type") == "status": self.workspace.status.setText(str(payload.get("status","Ready")))


def install_design_workspace(window, runtime):
    existing = getattr(window, "_design_controller", None)
    if existing is not None: return existing
    controller = DesignController(window,runtime); window._design_controller = controller; return controller
