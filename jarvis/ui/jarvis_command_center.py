"""Project Nova command-center skin for the JARVIS desktop assistant."""
from __future__ import annotations

import math
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

BLUE = QColor("#159DFF")
CYAN = QColor("#57D7FF")
GOLD = QColor("#F2C86B")
TEXT = QColor("#DCEEFF")
DARK = QColor("#02060C")

def _alpha(c, a):
    c = QColor(c); c.setAlpha(max(0, min(255, a))); return c

class JarvisSentinelWidget(QWidget):
    """Dense original Project Nova radial command HUD; keeps the existing orb API."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(620, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.status, self.response_style, self.mode = "idle", "calm", "wake_phrase"
        self.audio_level = self._smooth_audio = self._phase = 0.0
        self.speech_detected = False
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(40)

    def set_status(self, status): self.status = status or "idle"; self.update()
    def set_response_style(self, style): self.response_style = style or "calm"
    def set_audio_level(self, level, speech_detected, mode):
        self.audio_level = max(0.0, min(float(level) * 10.0, 1.0)); self.speech_detected = bool(speech_detected); self.mode = mode or "wake_phrase"
    def _tick(self):
        self._phase += .018; self._smooth_audio += (self.audio_level-self._smooth_audio)*.1; self.update()
    def _status_color(self):
        return QColor("#FF5A69") if self.status == "error" else GOLD if self.status in {"thinking","transcribing"} else CYAN if self.status in {"speaking","listening"} else BLUE

    def _panel(self, p, rect, title, lines):
        p.setBrush(_alpha(QColor("#03101D"), 190)); p.setPen(QPen(_alpha(BLUE, 115), 1)); p.drawRect(rect)
        p.setFont(QFont("Cascadia Code", 8, 700)); p.setPen(_alpha(CYAN, 225)); p.drawText(rect.adjusted(9,6,-5,-5), Qt.AlignmentFlag.AlignTop, title)
        p.setFont(QFont("Cascadia Code", 7)); p.setPen(_alpha(TEXT, 155))
        y = rect.top()+28
        for line in lines:
            p.drawText(QPointF(rect.left()+9,y), line); y += 15

    def paintEvent(self, _event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height(); cx,cy=w*.50,h*.46; size=min(w*.64,h*.90); accent=self._status_color()
        p.fillRect(self.rect(), DARK)
        # blueprint grid
        p.setPen(QPen(_alpha(BLUE,18),1))
        for x in range(0,w,32): p.drawLine(x,0,x,h)
        for y in range(0,h,32): p.drawLine(0,y,w,y)
        # center crosshair guides
        p.setPen(QPen(_alpha(CYAN,38),1)); p.drawLine(0,int(cy),w,int(cy)); p.drawLine(int(cx),0,int(cx),h)
        # layered segmented radial system
        rings=[(.46,230,3,255,58),(.405,175,2,205,82),(.35,145,2,145,42),(.295,200,2,225,70),(.235,105,1,160,32),(.17,220,2,250,96)]
        for i,(ratio,a,width,span,gap) in enumerate(rings):
            r=size*ratio; rect=QRectF(cx-r,cy-r,2*r,2*r); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(_alpha(accent,a),width))
            rotation=(self._phase*(36 if i%2==0 else -24)+i*31)%360
            for base in range(0,360,span+gap): p.drawArc(rect,int((base+rotation)*16),int(span*16))
        # dense ticks
        for count,ratio,a in ((96,.435,115),(64,.325,90),(36,.215,145)):
            p.setPen(QPen(_alpha(CYAN,a),1))
            for i in range(count):
                ang=math.tau*i/count + self._phase*(.08 if count!=64 else -.06); outer=size*ratio; inner=outer-(10 if i%4==0 else 5)
                p.drawLine(QPointF(cx+math.cos(ang)*inner,cy+math.sin(ang)*inner),QPointF(cx+math.cos(ang)*outer,cy+math.sin(ang)*outer))
        # radar sweep
        sweep=self._phase*1.7; r=size*.29; path=QPainterPath(QPointF(cx,cy)); path.arcTo(QRectF(cx-r,cy-r,2*r,2*r),-math.degrees(sweep),26); path.closeSubpath(); p.setPen(Qt.PenStyle.NoPen); p.setBrush(_alpha(CYAN,22)); p.drawPath(path)
        # central core, intentionally original (no movie armor/branding)
        core=QRadialGradient(QPointF(cx,cy),size*.13); core.setColorAt(0,QColor("#FFFFFF")); core.setColorAt(.18,CYAN); core.setColorAt(.55,_alpha(BLUE,130)); core.setColorAt(1,_alpha(BLUE,0)); p.setBrush(core); p.setPen(QPen(_alpha(GOLD,190),2)); p.drawEllipse(QPointF(cx,cy),size*.115,size*.115)
        p.setPen(QPen(_alpha(CYAN,220),2));
        for i in range(6):
            a=math.tau*i/6+self._phase*.2; p.drawLine(QPointF(cx+math.cos(a)*size*.06,cy+math.sin(a)*size*.06),QPointF(cx+math.cos(a)*size*.105,cy+math.sin(a)*size*.105))
        # radial callout spokes
        p.setPen(QPen(_alpha(BLUE,105),1))
        for deg in (205,225,315,335,25,155):
            a=math.radians(deg); x1,y1=cx+math.cos(a)*size*.28,cy+math.sin(a)*size*.28; x2,y2=cx+math.cos(a)*size*.43,cy+math.sin(a)*size*.43; p.drawLine(QPointF(x1,y1),QPointF(x2,y2)); p.drawLine(QPointF(x2,y2),QPointF(x2+(25 if math.cos(a)>0 else -25),y2))
        # side telemetry panels matching reference density without copied branding
        pw=max(120,int(w*.18)); self._panel(p,QRectF(12,35,pw,118),"SYSTEM // 01",["CORE      ONLINE",f"VOICE     {self.status.upper()}","NOVA LINK READY","SECURITY  ACTIVE","MEMORY    NOMINAL"])
        self._panel(p,QRectF(12,165,pw,142),"DIAGNOSTICS",["CPU       MONITOR","AUDIO     LINKED","FILES     APPROVED","MODELS    READY","PLUGINS   STANDBY","NETWORK   SECURE"])
        self._panel(p,QRectF(w-pw-12,35,pw,118),"PROJECT NOVA",["JARVIS COMMAND","ACCESS    READY","HUD       ACTIVE","BUILD     1.0.5","STATE     NOMINAL"])
        self._panel(p,QRectF(w-pw-12,165,pw,142),"INTEL FEED",["SCAN      ACTIVE","TASKS     QUEUED","VOICE     ARMED","LOCAL AI  READY","SYSTEMS   LINKED","CONTROL   USER"])
        # top numbered bus + lower command indicators
        p.setFont(QFont("Cascadia Code",7,700)); p.setPen(_alpha(CYAN,145))
        for i in range(1,25): p.drawText(QPointF(12+(i-1)*(w-24)/24,18),f"{i:02}")
        y=h-35
        for i,label in enumerate(("SCAN","VOICE","CORE","NAV","LINK","FILES","APPS","TOOLS","SYS")):
            x=35+i*(w-70)/8; p.setPen(QPen(_alpha(CYAN,155),2)); p.setBrush(_alpha(BLUE,18)); p.drawEllipse(QPointF(x,y),19,19); p.setFont(QFont("Cascadia Code",5,700)); p.setPen(_alpha(TEXT,180)); p.drawText(QRectF(x-18,y-6,36,12),Qt.AlignmentFlag.AlignCenter,label)
        p.end()

_COMMAND_CENTER_QSS='''
QMainWindow { background:#02060C; }
QFrame#headerPanel { background:rgba(2,10,20,0.94); border:1px solid rgba(21,157,255,.34); border-radius:2px; }
QFrame#panel,QFrame#chatPanel,QFrame#hudSystemPanel,QFrame#hudIntelFeed,QFrame#providerCard { background:rgba(3,10,19,.90); border:1px solid rgba(21,157,255,.28); border-radius:2px; }
QLabel#panelTitle { color:#62D6FF; font-family:"Cascadia Code",Consolas,monospace; font-size:10px; font-weight:700; }
QLabel#muted { color:#66839E; }
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox { background:rgba(1,8,16,.86); border:1px solid rgba(21,157,255,.28); border-radius:2px; }
QPushButton,QToolButton { background:rgba(21,157,255,.06); border:1px solid rgba(21,157,255,.30); border-radius:12px; color:#CFEAFF; }
QPushButton:hover,QToolButton:hover { background:rgba(21,157,255,.16); border-color:#57D7FF; }
QProgressBar::chunk { background:#159DFF; }
QTabBar::tab:selected { color:#F2C86B; border-bottom:2px solid #F2C86B; }
'''

def install_command_center(window, runtime=None):
    if getattr(window,"_nova_command_center_installed",False): return
    old=getattr(window,"orb",None)
    if old is not None:
        parent=old.parentWidget(); layout=parent.layout() if parent else None
        if layout is not None:
            hero=JarvisSentinelWidget(parent); replaced=layout.replaceWidget(old,hero)
            if replaced is not None: old.hide(); old.setParent(None); old.deleteLater(); window.orb=hero
    if hasattr(window,"orb_status_label"):
        window.orb_status_label.setText("JARVIS"); window.orb_status_label.setStyleSheet("color:#DCEEFF;font-size:30px;font-weight:300;letter-spacing:8px;")
    if hasattr(window,"orb_subtitle_label"):
        window.orb_subtitle_label.setText("COMMAND CENTER // PROJECT NOVA STUDIO"); window.orb_subtitle_label.setStyleSheet("color:#57D7FF;font-size:10px;font-weight:600;letter-spacing:2px;")
    header=window.findChild(QFrame,"headerPanel")
    if header is not None and header.layout() is not None:
        item=header.layout().itemAt(0); row=item.widget() if item else None; top=row.layout() if row else None
        if top is not None:
            brand=QLabel("<span style='font-size:20px;font-weight:700;letter-spacing:4px;color:#DCEEFF;'>JARVIS</span><br><span style='font-size:8px;letter-spacing:3px;color:#57D7FF;'>PROJECT NOVA COMMAND NETWORK</span>"); brand.setObjectName("novaJarvisBrand"); brand.setMinimumWidth(230); top.insertWidget(0,brand)
    window.setStyleSheet(window.styleSheet()+_COMMAND_CENTER_QSS); window._nova_command_center_installed=True
