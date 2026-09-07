"""Project Nova command-center skin for the JARVIS desktop assistant."""
from __future__ import annotations

import math
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

BLUE = QColor("#159DFF")
CYAN = QColor("#57D7FF")
GOLD = QColor("#F2C86B")
TEXT = QColor("#DCEEFF")
DARK = QColor("#030812")

def _alpha(color: QColor, value: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, value)))
    return c

class JarvisSentinelWidget(QWidget):
    """Original blue/gold JARVIS sentinel with animated HUD rings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(430, 430)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.status = "idle"
        self.response_style = "calm"
        self.mode = "wake_phrase"
        self.audio_level = 0.0
        self.speech_detected = False
        self._smooth_audio = 0.0
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_status(self, status: str) -> None:
        self.status = status or "idle"
        self.update()

    def set_response_style(self, style: str) -> None:
        self.response_style = style or "calm"

    def set_audio_level(self, level: float, speech_detected: bool, mode: str) -> None:
        self.audio_level = max(0.0, min(float(level) * 10.0, 1.0))
        self.speech_detected = bool(speech_detected)
        self.mode = mode or "wake_phrase"

    def _tick(self) -> None:
        self._phase = (self._phase + 0.018) % (math.tau * 100)
        self._smooth_audio += (self.audio_level - self._smooth_audio) * 0.10
        self.update()

    def _status_color(self) -> QColor:
        if self.status == "error":
            return QColor("#FF5A69")
        if self.status in {"thinking", "transcribing"}:
            return GOLD
        if self.status in {"speaking", "listening"}:
            return CYAN
        return BLUE

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.5, h * 0.49
        size = min(w, h)
        scale = size / 620.0
        accent = self._status_color()
        breath = 1.0 + 0.018 * math.sin(self._phase * 2.0) + self._smooth_audio * 0.035

        p.setPen(QPen(_alpha(BLUE, 18), max(1.0, scale)))
        grid = max(24, int(36 * scale))
        for x in range(0, w, grid):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, grid):
            p.drawLine(0, y, w, y)

        for idx, (ratio, alpha_v, width) in enumerate(((0.42, 125, 2.0), (0.49, 75, 1.4), (0.57, 42, 1.0))):
            r = size * ratio * breath
            rect = QRectF(cx-r, cy-r, r*2, r*2)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(_alpha(accent, alpha_v), width * scale))
            start = int((25 + idx * 33 + self._phase * (25 - idx * 5)) * 16)
            span = int((245 - idx * 30) * 16)
            p.drawArc(rect, start, span)
            p.drawArc(rect, start + 190 * 16, int(55 * 16))

        tick_r1 = size * 0.515
        tick_r2 = size * 0.535
        p.setPen(QPen(_alpha(CYAN, 105), max(1.0, 1.1 * scale)))
        for i in range(48):
            ang = math.radians(i * 7.5 + self._phase * 9)
            x1, y1 = cx + math.cos(ang)*tick_r1, cy + math.sin(ang)*tick_r1
            x2, y2 = cx + math.cos(ang)*tick_r2, cy + math.sin(ang)*tick_r2
            if i % 3 == 0:
                x1, y1 = cx + math.cos(ang)*size*0.505, cy + math.sin(ang)*size*0.505
            p.drawLine(QPointF(x1,y1), QPointF(x2,y2))

        halo = QRadialGradient(QPointF(cx, cy), size * 0.43)
        halo.setColorAt(0.0, _alpha(accent, 72))
        halo.setColorAt(0.42, _alpha(BLUE, 24))
        halo.setColorAt(1.0, _alpha(DARK, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), size*0.43, size*0.43)

        head_w, head_h = size*0.29, size*0.39
        top = cy - head_h*0.68
        left, right = cx-head_w*0.5, cx+head_w*0.5
        bottom = top + head_h
        head = QPainterPath()
        head.moveTo(cx, top)
        head.lineTo(right-head_w*0.12, top+head_h*0.10)
        head.lineTo(right, top+head_h*0.38)
        head.lineTo(right-head_w*0.08, top+head_h*0.75)
        head.lineTo(cx+head_w*0.19, bottom)
        head.lineTo(cx-head_w*0.19, bottom)
        head.lineTo(left+head_w*0.08, top+head_h*0.75)
        head.lineTo(left, top+head_h*0.38)
        head.lineTo(left+head_w*0.12, top+head_h*0.10)
        head.closeSubpath()
        metal = QLinearGradient(QPointF(left, top), QPointF(right, bottom))
        metal.setColorAt(0.0, QColor("#182A3D"))
        metal.setColorAt(0.42, QColor("#07111E"))
        metal.setColorAt(1.0, QColor("#13283C"))
        p.setBrush(metal)
        p.setPen(QPen(_alpha(BLUE, 190), 2.2*scale))
        p.drawPath(head)

        for sign in (-1, 1):
            panel = QPainterPath()
            panel.moveTo(cx, top+head_h*0.08)
            panel.lineTo(cx+sign*head_w*0.34, top+head_h*0.19)
            panel.lineTo(cx+sign*head_w*0.25, top+head_h*0.37)
            panel.lineTo(cx, top+head_h*0.31)
            panel.closeSubpath()
            p.setBrush(_alpha(GOLD, 62))
            p.setPen(QPen(_alpha(GOLD, 210), 1.2*scale))
            p.drawPath(panel)

        eye_y = top+head_h*0.42
        eye_gap, eye_w, eye_h = head_w*0.055, head_w*0.30, head_h*0.040
        eye_pen = QPen(_alpha(CYAN, 245), max(2.0, 5.0*scale))
        eye_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(eye_pen)
        p.drawLine(QPointF(cx-eye_gap-eye_w, eye_y), QPointF(cx-eye_gap, eye_y+eye_h))
        p.drawLine(QPointF(cx+eye_gap, eye_y+eye_h), QPointF(cx+eye_gap+eye_w, eye_y))

        p.setPen(QPen(_alpha(BLUE,155), 1.4*scale))
        p.drawLine(QPointF(left+head_w*0.10, top+head_h*0.54), QPointF(cx-head_w*0.13, top+head_h*0.72))
        p.drawLine(QPointF(right-head_w*0.10, top+head_h*0.54), QPointF(cx+head_w*0.13, top+head_h*0.72))

        shoulder_y = bottom + size*0.035
        shoulder = QPainterPath()
        shoulder.moveTo(cx-size*0.33, shoulder_y+size*0.13)
        shoulder.lineTo(cx-size*0.22, shoulder_y+size*0.015)
        shoulder.lineTo(cx-size*0.095, shoulder_y-size*0.025)
        shoulder.lineTo(cx, shoulder_y+size*0.05)
        shoulder.lineTo(cx+size*0.095, shoulder_y-size*0.025)
        shoulder.lineTo(cx+size*0.22, shoulder_y+size*0.015)
        shoulder.lineTo(cx+size*0.33, shoulder_y+size*0.13)
        p.setBrush(_alpha(QColor("#081521"),220))
        p.setPen(QPen(_alpha(BLUE,135),1.6*scale))
        p.drawPath(shoulder)

        core_y = shoulder_y + size*0.095
        core_r = size*(0.045 + 0.006*math.sin(self._phase*3.0))
        core_grad = QRadialGradient(QPointF(cx,core_y), core_r*2.2)
        core_grad.setColorAt(0.0, QColor("#FFFFFF"))
        core_grad.setColorAt(0.18, CYAN)
        core_grad.setColorAt(0.52, _alpha(BLUE,150))
        core_grad.setColorAt(1.0, _alpha(BLUE,0))
        p.setBrush(core_grad)
        p.setPen(QPen(_alpha(GOLD,200),1.8*scale))
        p.drawEllipse(QPointF(cx,core_y), core_r*1.8, core_r*1.8)

        font = QFont("Cascadia Code", max(7, int(8*scale)))
        p.setFont(font)
        p.setPen(_alpha(TEXT,175))
        x_left = max(8.0, cx-size*0.46)
        x_right = min(w-size*0.22, cx+size*0.31)
        p.drawText(QPointF(x_left,cy-size*0.23),"CORE AI  //  ONLINE")
        p.drawText(QPointF(x_left,cy-size*0.19),f"VOICE    //  {self.status.upper()}")
        p.setPen(_alpha(GOLD,185))
        p.drawText(QPointF(x_right,cy-size*0.23),"NOVA LINK")
        p.setPen(_alpha(TEXT,155))
        p.drawText(QPointF(x_right,cy-size*0.19),"ACCESS  //  READY")
        p.end()

_COMMAND_CENTER_QSS = """
QMainWindow { background: #02060C; }
QFrame#headerPanel {
    background: rgba(2,10,20,0.94);
    border: 1px solid rgba(21,157,255,0.34);
    border-radius: 4px;
}
QFrame#panel, QFrame#chatPanel, QFrame#hudSystemPanel, QFrame#hudIntelFeed, QFrame#providerCard {
    background: rgba(3,10,19,0.88);
    border: 1px solid rgba(21,157,255,0.24);
    border-radius: 5px;
}
QFrame#panel:hover, QFrame#providerCard:hover { border-color: rgba(87,215,255,0.56); }
QLabel#panelTitle {
    color: #62D6FF;
    font-family: "Cascadia Code", Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#muted { color: #66839E; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background: rgba(1,8,16,0.82);
    border: 1px solid rgba(21,157,255,0.22);
    border-radius: 4px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border-color: rgba(87,215,255,0.75);
}
QPushButton, QToolButton {
    background: rgba(21,157,255,0.055);
    border: 1px solid rgba(21,157,255,0.22);
    border-radius: 4px;
    color: #CFEAFF;
}
QPushButton:hover, QToolButton:hover {
    background: rgba(21,157,255,0.14);
    border-color: rgba(87,215,255,0.70);
}
QPushButton:pressed, QToolButton:pressed {
    background: rgba(242,200,107,0.12);
    border-color: rgba(242,200,107,0.72);
}
QProgressBar::chunk { background: #159DFF; }
QTabBar::tab:selected { color: #F2C86B; border-bottom: 2px solid #F2C86B; }
"""

def install_command_center(window, runtime=None) -> None:
    """Install the visual skin without changing assistant behavior."""
    if getattr(window, "_nova_command_center_installed", False):
        return
    old_orb = getattr(window, "orb", None)
    if old_orb is not None:
        parent = old_orb.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is not None:
            new_hero = JarvisSentinelWidget(parent)
            replaced = layout.replaceWidget(old_orb, new_hero)
            if replaced is not None:
                old_orb.hide()
                old_orb.setParent(None)
                old_orb.deleteLater()
                window.orb = new_hero

    if hasattr(window, "orb_status_label"):
        window.orb_status_label.setText("JARVIS")
        window.orb_status_label.setStyleSheet(
            "color:#DCEEFF; font-size:30px; font-weight:300; letter-spacing:8px;"
            "font-family:'Segoe UI Variable Display','Segoe UI',sans-serif;"
        )
    if hasattr(window, "orb_subtitle_label"):
        window.orb_subtitle_label.setText("AI ASSISTANT  //  PROJECT NOVA STUDIO")
        window.orb_subtitle_label.setStyleSheet(
            "color:#F2C86B; font-size:11px; font-weight:600; letter-spacing:2px;"
        )

    header_frame = window.findChild(QFrame, "headerPanel")
    if header_frame is not None and header_frame.layout() is not None:
        item = header_frame.layout().itemAt(0)
        top_row = item.widget() if item is not None else None
        top_layout = top_row.layout() if top_row is not None else None
        if top_layout is not None:
            brand = QLabel(
                "<span style='font-size:20px;font-weight:700;letter-spacing:4px;color:#DCEEFF;'>JARVIS</span>"
                "<br><span style='font-size:8px;letter-spacing:3px;color:#57D7FF;'>AI ASSISTANT · PROJECT NOVA STUDIO</span>"
            )
            brand.setObjectName("novaJarvisBrand")
            brand.setMinimumWidth(210)
            top_layout.insertWidget(0, brand)

    window.setStyleSheet(window.styleSheet() + _COMMAND_CENTER_QSS)
    window._nova_command_center_installed = True
