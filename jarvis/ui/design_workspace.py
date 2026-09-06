"""Qt concept-modeling workspace for Jarvis.

This is intentionally lightweight: it edits the bounded scene format from
``jarvis.brain.design_engine`` and gives the user a live 2D/isometric preview,
part controls, JSON save, and OBJ export.  It does not replace Blender.
"""
from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from jarvis.brain.design_engine import preset, save_obj, save_scene, validate_scene


class DesignViewport(QWidget):
    """Small software-rendered isometric preview; safe on low-end Windows PCs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = preset("spaceship")
        self.yaw = math.radians(35)
        self.pitch = math.radians(25)
        self._drag = None
        self.setMinimumSize(360, 260)
        self.setStyleSheet("background:#071019;")

    def set_scene(self, scene):
        self.scene = validate_scene(scene)
        self.update()

    def mousePressEvent(self, event):
        self._drag = event.position()

    def mouseMoveEvent(self, event):
        if self._drag is None:
            return
        p = event.position()
        self.yaw += (p.x() - self._drag.x()) * 0.01
        self.pitch = max(-1.2, min(1.2, self.pitch + (p.y() - self._drag.y()) * 0.01))
        self._drag = p
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None

    def _project(self, xyz, scale, cx, cy):
        x, y, z = xyz
        cyaw, syaw = math.cos(self.yaw), math.sin(self.yaw)
        x, z = x * cyaw - z * syaw, x * syaw + z * cyaw
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        y, z = y * cp - z * sp, y * sp + z * cp
        return QPointF(cx + x * scale, cy - y * scale), z

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#071019"))
        p.setPen(QPen(QColor("#17344b"), 1))
        for x in range(0, self.width(), 32):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 32):
            p.drawLine(0, y, self.width(), y)

        if not self.scene.get("objects"):
            return
        max_extent = 1.0
        for obj in self.scene["objects"]:
            max_extent = max(max_extent, *(abs(v) for v in obj["position"]), *obj["size"])
        scale = min(self.width(), self.height()) / (max_extent * 8.0)
        cx, cy = self.width() / 2, self.height() / 2

        items = []
        for obj in self.scene["objects"]:
            pos, size = obj["position"], obj["size"]
            sx, sy, sz = [v / 2 for v in size]
            corners = []
            for dx, dy, dz in ((-sx,-sy,-sz),(sx,-sy,-sz),(sx,sy,-sz),(-sx,sy,-sz),
                               (-sx,-sy,sz),(sx,-sy,sz),(sx,sy,sz),(-sx,sy,sz)):
                q, depth = self._project((pos[0]+dx,pos[1]+dy,pos[2]+dz), scale, cx, cy)
                corners.append((q, depth))
            items.append((sum(d for _, d in corners)/8.0, obj, corners))

        for _depth, obj, c in sorted(items, key=lambda t: t[0]):
            color = QColor(obj.get("color", "#67cbd4"))
            faces = ((0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(0,3,7,4))
            for i, face in enumerate(faces):
                shade = color.lighter(105 + i * 5)
                shade.setAlpha(190)
                p.setBrush(shade)
                p.setPen(QPen(color.lighter(140), 1))
                p.drawPolygon(QPolygonF([c[n][0] for n in face]))


class DesignWorkspace(QWidget):
    def __init__(self, runtime=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.scene = preset("spaceship")
        self._building = False

        root = QHBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split)

        controls = QWidget()
        left = QVBoxLayout(controls)
        row = QHBoxLayout()
        self.preset_box = QComboBox()
        self.preset_box.addItems(["outpost", "spaceship", "terrain"])
        self.preset_box.setCurrentText("spaceship")
        load_btn = QPushButton("Load preset")
        load_btn.clicked.connect(self._load_preset)
        row.addWidget(self.preset_box)
        row.addWidget(load_btn)
        left.addLayout(row)

        self.parts = QListWidget()
        self.parts.currentRowChanged.connect(self._select_part)
        left.addWidget(self.parts, 1)

        form = QFormLayout()
        self.kind = QComboBox(); self.kind.addItems(["box", "cylinder", "pyramid"])
        form.addRow("Kind", self.kind)
        self.position = []
        self.size = []
        for label, bucket, lo, hi, default in (
            ("Position X", self.position, -1000, 1000, 0),
            ("Position Y", self.position, -1000, 1000, 0),
            ("Position Z", self.position, -1000, 1000, 0),
            ("Size X", self.size, .01, 1000, 1),
            ("Size Y", self.size, .01, 1000, 1),
            ("Size Z", self.size, .01, 1000, 1),
        ):
            spin = QDoubleSpinBox(); spin.setRange(lo, hi); spin.setDecimals(2); spin.setValue(default)
            spin.valueChanged.connect(self._apply_editor)
            bucket.append(spin); form.addRow(label, spin)
        self.kind.currentTextChanged.connect(self._apply_editor)
        left.addLayout(form)

        buttons = QHBoxLayout()
        for text, slot in (("Add box", self.add_part), ("Remove", self.remove_part), ("Save", self.save), ("Export OBJ", self.export_obj)):
            b = QPushButton(text); b.clicked.connect(slot); buttons.addWidget(b)
        left.addLayout(buttons)

        self.prompt = QComboBox(); self.prompt.setEditable(True)
        self.prompt.addItem("Design a hangar")
        ask = QPushButton("Ask Jarvis")
        ask.clicked.connect(self.ask)
        left.addWidget(QLabel("Companion request")); left.addWidget(self.prompt); left.addWidget(ask)

        self.viewport = DesignViewport()
        split.addWidget(controls); split.addWidget(self.viewport)
        split.setSizes([320, 700])
        self.set_scene(self.scene)

    def set_scene(self, scene):
        self.scene = validate_scene(deepcopy(scene))
        self._building = True
        self.parts.clear()
        for obj in self.scene["objects"]:
            self.parts.addItem(obj["name"])
        self._building = False
        self.parts.setCurrentRow(0)
        self.viewport.set_scene(self.scene)

    def _load_preset(self):
        self.set_scene(preset(self.preset_box.currentText()))

    def _select_part(self, row):
        if row < 0 or row >= len(self.scene["objects"]):
            return
        obj = self.scene["objects"][row]
        self._building = True
        self.kind.setCurrentText(obj["kind"])
        for spin, value in zip(self.position, obj["position"]): spin.setValue(value)
        for spin, value in zip(self.size, obj["size"]): spin.setValue(value)
        self._building = False

    def _apply_editor(self, *_):
        if self._building:
            return
        row = self.parts.currentRow()
        if row < 0 or row >= len(self.scene["objects"]):
            return
        obj = self.scene["objects"][row]
        obj["kind"] = self.kind.currentText()
        obj["position"] = [s.value() for s in self.position]
        obj["size"] = [s.value() for s in self.size]
        self.scene = validate_scene(self.scene)
        self.viewport.set_scene(self.scene)

    def add_part(self):
        if len(self.scene["objects"]) >= 200:
            return
        self.scene["objects"].append({"name": f"Part {len(self.scene['objects'])+1}", "kind": "box", "position": [0,0,0], "size": [1,1,1], "color": "#67cbd4"})
        self.set_scene(self.scene)
        self.parts.setCurrentRow(len(self.scene["objects"]) - 1)

    def remove_part(self):
        if len(self.scene["objects"]) <= 1:
            return
        row = max(0, self.parts.currentRow())
        self.scene["objects"].pop(row)
        self.set_scene(self.scene)

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Jarvis design", str(Path.home() / "jarvis-design.json"), "JSON (*.json)")
        if path: save_scene(self.scene, path)

    def export_obj(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export OBJ", str(Path.home() / "jarvis-design.obj"), "Wavefront OBJ (*.obj)")
        if path: save_obj(self.scene, path)

    def ask(self):
        text = self.prompt.currentText().strip()
        if text and self.runtime is not None and hasattr(self.runtime, "send_text"):
            self.runtime.send_text(text)


class DesignWorkspaceController:
    def __init__(self, window: QMainWindow, runtime):
        self.window = window
        self.runtime = runtime
        self.workspace = DesignWorkspace(runtime, window)
        self.original = window.centralWidget()
        if hasattr(runtime, "bridge") and hasattr(runtime.bridge, "event_received"):
            runtime.bridge.event_received.connect(self._event)

    def open(self, scene=None):
        if scene is not None:
            self.workspace.set_scene(scene)
        if self.window.centralWidget() is not self.workspace:
            old = self.window.takeCentralWidget()
            if old is not None and old is not self.original:
                old.setParent(self.window)
            self.window.setCentralWidget(self.workspace)
        self.window.show()
        return self.workspace

    def close(self):
        if self.window.centralWidget() is self.workspace:
            self.window.takeCentralWidget()
            if self.original is not None:
                self.window.setCentralWidget(self.original)

    def _event(self, event):
        if not isinstance(event, dict) or event.get("type") != "design_scene":
            return
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
        scene = payload.get("scene")
        if scene:
            self.open(scene)


def install_design_workspace(window: QMainWindow, runtime):
    """Attach the 3D concept workspace to an existing Jarvis main window."""
    existing = getattr(window, "_design_controller", None)
    if existing is not None:
        return existing
    controller = DesignWorkspaceController(window, runtime)
    window._design_controller = controller

    # Give the design plugin a direct presenter when it is already loaded.
    manager = getattr(runtime, "plugin_manager", None)
    plugin = getattr(manager, "plugins", {}).get("design_3d") if manager is not None else None
    if plugin is not None and hasattr(plugin, "set_presenter"):
        def presenter(kind, payload):
            if kind == "design_scene" and isinstance(payload, dict):
                controller.open(payload.get("scene"))
        plugin.set_presenter(presenter)
    return controller
