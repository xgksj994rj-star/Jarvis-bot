from __future__ import annotations

import ctypes
import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Optional, Callable
from actions.startup_manager import add_to_startup, remove_from_startup, is_in_startup

# Prevent Qt from reconfiguring DPI awareness in a way that triggers Windows access-denied warnings.
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget, QProgressBar, QComboBox,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    PAUSED    = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        sensors_fn = getattr(psutil, "sensors_temperatures", None)
        if callable(sensors_fn):
            try:
                temps = sensors_fn()
                candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                              "cpu-thermal", "zenpower", "it8688"]
                for name in candidates:
                    entries = temps.get(name) if isinstance(temps, dict) else None
                    if entries:
                        return float(entries[0].current)
                if isinstance(temps, dict):
                    for entries in temps.values():
                        if entries:
                            return float(entries[0].current)
            except Exception:
                pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                commands = [
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty CurrentTemperature)"] ,
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-WmiObject -Namespace root/wmi -Class MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty CurrentTemperature)"],
                ]
                for cmd in commands:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if r.returncode == 0 and r.stdout.strip():
                        raw = float(r.stdout.strip().splitlines()[0])
                        if raw > 0:
                            # WMI returns tenths of Kelvin on most Windows systems.
                            return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)




    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # grid dots
        p.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)

        r_face = fw * 0.31

        # halo glow
        for i in range(10):
            r   = r_face * (1.8 - i * 0.08)
            frc = 1.0 - i / 10
            a   = max(0, min(255, int(self._halo * 0.085 * frc)))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # pulse rings
        for pr in self._pulses:
            a   = max(0, int(230 * (1.0 - pr / (fw * 0.74))))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # spinning arc rings
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 3, 115, 78), (0.40, 2, 78, 55), (0.32, 1, 56, 40)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(255, int(self._halo * (1.0 - idx * 0.18))))
            col    = qcol(C.MUTED_C if self.muted else C.PRI, a_val)
            p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect  = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap

        # scanners
        sr = fw * 0.50
        sa = min(255, int(self._halo * 1.5))
        ex = 75 if self.speaking else 44
        p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        p.setPen(QPen(qcol(C.ACC, sa // 2), 1.5))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

        # tick marks
        t_out, t_in = fw * 0.497, fw * 0.474
        p.setPen(QPen(qcol(C.PRI, 140), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)),
            )

        # crosshair
        ch_r, gap_h = fw * 0.51, fw * 0.16
        p.setPen(QPen(qcol(C.PRI, int(self._halo * 0.5)), 1))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # corner brackets
        bl = 24
        bc = qcol(C.PRI, 210)
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # face
        if self._face_px:
            fsz    = int(fw * 0.62 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
        else:
            orb_r = int(fw * 0.27 * self._scale)
            if self.muted:
                oc = (200, 0, 50)
            elif self.state == "PAUSED":
                oc = (255, 203, 51)
            else:
                oc = (0, 60, 110)
            for i in range(8, 0, -1):
                r2  = int(orb_r * i / 8)
                frc = i / 8
                a   = max(0, min(255, int(self._halo * 1.1 * frc)))
                p.setBrush(QBrush(QColor(int(oc[0]*frc), int(oc[1]*frc), int(oc[2]*frc), a)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
            p.setPen(QPen(qcol(C.PRI, min(255, int(self._halo * 2))), 1))
            p.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
            p.drawText(QRectF(cx - 80, cy - 14, 160, 28),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # particles
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.PRI, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "●  SPEAKING",  qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.ACC2)
        elif self.state == "PAUSED":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  PAUSED",     qcol(C.PAUSED)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            elif self.speaking:
                hgt = random.randint(3, 20)
                cl  = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
            else:
                hgt = int(3 + 2 * math.sin(self._tick * 0.09 + i * 0.6))
                cl  = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}


class DiscordStatusIndicator(QWidget):
    """Small animated status bulb for Discord connection.

    States:
    - ONLINE: green pulsing
    - OFFLINE: red solid
    - TRANSIENT: amber rotating arc
    """
    def __init__(self, size: int = 12, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(self._size * 2, self._size)
        self._state = "OFFLINE"
        self._tick = 0.0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # clickable
    clicked = pyqtSignal()

    def mousePressEvent(self, ev):
        try:
            self.clicked.emit()
        except Exception:
            pass
        return super().mousePressEvent(ev)

    def _step(self):
        self._tick += 1.0
        self.update()

    def set_state(self, state: str):
        self._state = (state or "").upper()
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = min(self.width(), self.height())
        cx = self.width() - r
        cy = (self.height() - r) / 2

        if self._state == "ONLINE":
            # pulsing green
            import math
            pulse = 0.5 + 0.5 * math.sin(self._tick * 0.18)
            glow = int(120 + 135 * pulse)
            col = qcol(C.GREEN, 255)
            p.setBrush(col)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx), int(cy), r, r)
            # glow ring
            pen = QPen(qcol(C.GREEN, max(40, glow)), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(cx - 3), int(cy - 3), r + 6, r + 6)

        elif self._state == "OFFLINE":
            col = qcol(C.RED, 255)
            p.setBrush(col)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx), int(cy), r, r)
            pen = QPen(qcol(C.RED, 160), 1)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(cx), int(cy), r, r)

        else:
            # TRANSIENT / other: amber with rotating arc
            col = qcol(C.ACC, 255)
            p.setBrush(qcol(C.ACC, 64))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx), int(cy), r, r)
            pen = QPen(qcol(C.ACC, 255), 2)
            p.setPen(pen)
            rect = QRectF(int(cx), int(cy), r, r)
            start = int((self._tick * 8) % 360)
            span = 120
            p.drawArc(rect, start * 16, span * 16)

_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for JARVIS", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        layout.addWidget(_lbl("NGROK AUTH TOKEN (optional)", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._ngrok_input = QLineEdit()
        self._ngrok_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._ngrok_input.setPlaceholderText("twa...")
        self._ngrok_input.setFont(QFont("Courier New", 10))
        self._ngrok_input.setFixedHeight(32)
        self._ngrok_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._ngrok_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        token = self._ngrok_input.text().strip()
        self.done.emit(key, self._sel_os, token)


class MainWindow(QMainWindow):
    _log_sig                    = pyqtSignal(str)
    _state_sig                  = pyqtSignal(str)
    _context_status_sig         = pyqtSignal(str)
    _discord_status_sig         = pyqtSignal(str)
    _image_approval_request     = pyqtSignal(str, str, bool)
    _poll_image_picker_request  = pyqtSignal()

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — MARK 3")
        self._default_min_size = (_MIN_W, _MIN_H)
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self._headless_mode   = False
        self._startup_enabled = False
        self._startup_method  = "registry"
        self._current_file: str | None = None
        self._poll_image_picker_event: threading.Event | None = None
        self._poll_image_picker_result: list[str] | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # Animated Discord indicator (initialize before header uses it)
        self._discord_indicator = DiscordStatusIndicator(size=10, parent=self)
        self._header = self._build_header()
        root.addWidget(self._header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        self._footer = self._build_footer()
        root.addWidget(self._footer)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metrik güncelleme timer'ı
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._context_status_sig.connect(self._set_context_status)
        self._discord_status_sig.connect(self._handle_discord_status)
        self._image_approval_request.connect(self._handle_image_approval_request)
        self._poll_image_picker_request.connect(self._handle_poll_image_picker_request)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        # F-key quick toggles
        self._always_on_top = False
        self._mini_mode = False
        self._transparent_bg = False
        self._muted = False
        self._saved_geometry = None
        self._saved_header_visible = True
        self._saved_left_visible = True
        self._saved_right_visible = True
        self._saved_footer_visible = True
        self._remote_url = None
        self._remote_public_url = None
        self._discord_restart_callback: Optional[Callable[[], None]] = None

        # Thread safety for state changes
        self._state_lock = threading.Lock()

        # discord toggle callback (set by external code)
        self._discord_toggle_callback: Optional[Callable[[], None]] = None
        self._discord_sync_callback: Optional[Callable[[], None]] = None

        # Setup shortcuts (store as instance vars to prevent garbage collection)
        self._sc_f8 = QShortcut(QKeySequence("F8"), self)
        self._sc_f8.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._sc_f8.activated.connect(self._f8_action)
        
        self._sc_f11 = QShortcut(QKeySequence("F11"), self)
        self._sc_f11.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._sc_f11.activated.connect(self._toggle_fullscreen)

        self._setup_global_shortcuts()
        self._update_headless_button()
        self.set_startup_status(is_in_startup(self._startup_method))

    def _setup_global_shortcuts(self):
        """Setup shortcuts for F4-F7 with global fallback support."""
        bindings = {
            "f4": (self._toggle_mute, False),
            "f5": (self._toggle_always_on_top, False),
            "f6": (self._toggle_mini_mode, False),
            "f7": (self._toggle_transparent_bg, False),
        }

        def invoke(callback):
            QTimer.singleShot(0, callback)

        keyboard_available = False
        keyboard_module = None

        def try_import_keyboard():
            nonlocal keyboard_available, keyboard_module
            try:
                import keyboard as _kb  # type: ignore[import]
                keyboard_available = True
                keyboard_module = _kb
            except Exception:
                keyboard_available = False
                keyboard_module = None

        try_import_keyboard()

        if keyboard_available and keyboard_module is not None:
            for key, (callback, _) in bindings.items():
                try:
                    keyboard_module.add_hotkey(key, lambda cb=callback: invoke(cb))
                    bindings[key] = (callback, True)
                    if hasattr(self, "_log"):
                        self._log.append_log(f"SYS: Bound global hotkey {key.upper()} using keyboard package.")
                except Exception as exc:
                    if hasattr(self, "_log"):
                        msg = str(exc).lower()
                        if "permission" in msg or "access" in msg:
                            self._log.append_log(f"SYS: Could not bind global hotkey {key.upper()}: permission denied.")
                        else:
                            self._log.append_log(f"SYS: Could not bind global hotkey {key.upper()}: {exc}")

        elif _OS == "Windows":
            if hasattr(self, "_log"):
                self._log.append_log("SYS: Global `keyboard` package unavailable; using Windows RegisterHotKey fallback.")

        if _OS == "Windows":
            missing = [key for key, (_, bound) in bindings.items() if not bound]
            if missing:
                try:
                    user32 = ctypes.windll.user32
                    WM_HOTKEY = 0x0312
                    key_codes = {"f4": 0x73, "f5": 0x74, "f6": 0x75, "f7": 0x76}
                    hotkey_ids = {}

                    def register_win_hotkey(name, callback):
                        hotkey_id = len(hotkey_ids) + 1
                        if not user32.RegisterHotKey(None, hotkey_id, 0, key_codes[name]):
                            return False
                        hotkey_ids[hotkey_id] = callback
                        return True

                    for key in missing:
                        callback, _ = bindings[key]
                        if register_win_hotkey(key, callback):
                            bindings[key] = (callback, True)
                            if hasattr(self, "_log"):
                                self._log.append_log(f"SYS: Registered Windows fallback hotkey {key.upper()}.")
                        else:
                            if hasattr(self, "_log"):
                                self._log.append_log(f"SYS: Failed to register Windows fallback hotkey {key.upper()}.")

                    if hotkey_ids:
                        def hotkey_message_loop():
                            msg = wintypes.MSG()
                            while True:
                                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                                if result == 0:
                                    break
                                if result == -1:
                                    break
                                if msg.message == WM_HOTKEY:
                                    cb = hotkey_ids.get(msg.wParam)
                                    if cb:
                                        invoke(cb)
                                user32.TranslateMessage(ctypes.byref(msg))
                                user32.DispatchMessageW(ctypes.byref(msg))

                        t = threading.Thread(target=hotkey_message_loop, daemon=True, name="JarvisHotkeyLoop")
                        t.start()
                except Exception as exc:
                    if hasattr(self, "_log"):
                        self._log.append_log(f"SYS: Windows hotkey fallback failed: {exc}")

        # Local QShortcut fallbacks for keys that do not have a global binding.
        try:
            if not bindings["f4"][1]:
                self._sc_f4 = QShortcut(QKeySequence("F4"), self)
                self._sc_f4.setContext(Qt.ShortcutContext.ApplicationShortcut)
                self._sc_f4.activated.connect(self._toggle_mute)
            if not bindings["f5"][1]:
                self._sc_f5 = QShortcut(QKeySequence("F5"), self)
                self._sc_f5.setContext(Qt.ShortcutContext.ApplicationShortcut)
                self._sc_f5.activated.connect(self._toggle_always_on_top)
            if not bindings["f6"][1]:
                self._sc_f6 = QShortcut(QKeySequence("F6"), self)
                self._sc_f6.setContext(Qt.ShortcutContext.ApplicationShortcut)
                self._sc_f6.activated.connect(self._toggle_mini_mode)
            if not bindings["f7"][1]:
                self._sc_f7 = QShortcut(QKeySequence("F7"), self)
                self._sc_f7.setContext(Qt.ShortcutContext.ApplicationShortcut)
                self._sc_f7.activated.connect(self._toggle_transparent_bg)

            if hasattr(self, "_log"):
                if any(bound for _, bound in bindings.values()):
                    self._log.append_log("SYS: Using local shortcut fallback for unbound F-key hotkeys.")
                else:
                    self._log.append_log("SYS: Local shortcuts enabled for F4-F7.")
        except Exception:
            if hasattr(self, "_log"):
                self._log.append_log("SYS: Failed to create local shortcut fallbacks for F4-F7.")

    def _handle_image_approval_request(self, image_path: str, prompt: str, edited: bool):
        accepted = ImageApprovalDialog(image_path, prompt=prompt, edited=edited, parent=self).exec() == QDialog.DialogCode.Accepted
        if hasattr(self, '_approval_owner') and self._approval_owner is not None:
            self._approval_owner._approval_result = bool(accepted)
            self._approval_owner._approval_event.set()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge("MARK 3", C.PRI_DIM))
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        title = QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(title)
        sub = QLabel("Just A Rather Very Intelligent System")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 7))
        sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        self._context_badge = QLabel("PAUSED · General · Sensitivity 100%")
        self._context_badge.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._context_badge.setStyleSheet(f"color: {C.PAUSED}; background: transparent;")
        self._context_badge.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._context_badge)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("◈ SYS MONITOR")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        self._social_media_manager_btn = QPushButton("SOCIAL MEDIA MANAGER")
        self._social_media_manager_btn.setFixedHeight(26)
        self._social_media_manager_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._social_media_manager_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._social_media_manager_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        self._social_media_manager_btn.clicked.connect(self._open_social_media_manager_dialog)
        lay.addWidget(self._social_media_manager_btn)

        for txt, col in [
            ("AI CORE\nACTIVE",     C.GREEN),
            ("SEC\nCLEARED",        C.PRI),
            ("PROTOCOL\nXXXVIII",   C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        # Context overrides button is placed in the startup row below.

        fs_btn = QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.BORDER_B};
            }}
        """)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        headless_startup_row = QHBoxLayout()
        headless_startup_row.setSpacing(5)

        self._context_override_btn = QPushButton("⚙️  CONTEXT OVERRIDES")
        self._context_override_btn.setFixedHeight(24)
        self._context_override_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._context_override_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._context_override_btn.clicked.connect(self._edit_context_overrides)
        self._context_override_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        headless_startup_row.addWidget(self._context_override_btn)

        self._startup_btn = QPushButton("⏰ AUTOSTART")
        self._startup_btn.setFixedHeight(24)
        self._startup_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._startup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._startup_btn.setStyleSheet(self._small_toggle_style())
        self._startup_btn.setToolTip("Enable or disable Jarvis auto-start on Windows login.")
        self._startup_btn.clicked.connect(self._toggle_startup)
        headless_startup_row.addWidget(self._startup_btn)

        lay.addLayout(headless_startup_row)

        self._remote_url_lbl = QLabel("Remote URL: unavailable")
        self._remote_url_lbl.setFont(QFont("Courier New", 7))
        self._remote_url_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._remote_url_lbl.setWordWrap(True)
        self._remote_url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._remote_url_lbl.setOpenExternalLinks(True)
        self._remote_url_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self._remote_url_lbl)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen  ·  [F5] AlwaysOnTop  ·  [F6] Headless  ·  [F7] SeeThrough  ·  [F8] Restart Discord"))
        lay.addStretch()
        lay.addWidget(_fl("Devastator Industries  ·  MARK 3  ·  CLASSIFIED"))
        lay.addStretch()
        # Right-side small area: indicator + status label + brand
        right_small = QHBoxLayout(); right_small.setSpacing(6)
        # status label
        self._discord_status_lbl = QLabel("DISCORD  OFFLINE")
        self._discord_status_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._discord_status_lbl.setStyleSheet(f"color: {C.RED}; background: transparent;")
        # align to the right and slightly higher (center-vertical) so it sits
        # one step up from the bottom line for better visual balance
        self._discord_status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._discord_status_lbl.setFixedWidth(120)
        # clickable indicator (already created on init)
        try:
            self._discord_indicator.clicked.connect(self._discord_toggle_clicked)
        except Exception:
            pass
        self._discord_indicator.setToolTip("Click to toggle Discord bot on/off")

        self._discord_sync_btn = QPushButton("SYNC")
        self._discord_sync_btn.setFixedSize(44, 18)
        self._discord_sync_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._discord_sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._discord_sync_btn.setStyleSheet("""
            QPushButton {
                background: #2e2b36; color: #fff;
                border: 1px solid #666; border-radius: 3px;
            }
            QPushButton:hover { background: #444; border-color: #999; }
        """)
        self._discord_sync_btn.setToolTip("Sync Discord slash commands now")
        self._discord_sync_btn.clicked.connect(self._discord_sync_clicked)

        # place status label then stretch, put the sync button and indicator at the far right
        right_small.addWidget(self._discord_status_lbl)
        right_small.addStretch()
        right_small.addWidget(self._discord_sync_btn)
        right_small.addWidget(self._discord_indicator)
        lay.addLayout(right_small)
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell JARVIS what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _handle_discord_status(self, status: str):
        s = (status or "").upper()
        # ONLINE -> immediate green animated
        # sanitize status text (remove surrounding parentheses if present)
        s_clean = s.strip()
        # remove any parentheses that might be included in status strings
        s_clean = s_clean.replace("(", "").replace(")", "").strip()

        if s_clean == "ONLINE":
            self._discord_status_lbl.setText("DISCORD  ONLINE")
            self._discord_status_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
            self._discord_status_lbl.setToolTip("Connected — last seen: now")
            self._discord_indicator.set_state("ONLINE")
            return

        # OFFLINE -> immediate red
        if s_clean == "OFFLINE":
            self._discord_status_lbl.setText("DISCORD  OFFLINE")
            self._discord_status_lbl.setStyleSheet(f"color: {C.RED}; background: transparent;")
            self._discord_status_lbl.setToolTip("Disconnected or error")
            self._discord_indicator.set_state("OFFLINE")
            return

        # Other / transient states -> amber transient animation
        # remove parentheses around transient status labels
        self._discord_status_lbl.setText(f"DISCORD  {s_clean}")
        self._discord_status_lbl.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        self._discord_status_lbl.setToolTip(f"Status: {status}")
        self._discord_indicator.set_state("TRANSIENT")

    def _force_discord_offline(self):
        # Deprecated: offline is handled immediately by _handle_discord_status.
        return

    def _discord_toggle_clicked(self):
        # User clicked the indicator; call the registered toggle callback in a background thread.
        if self._discord_toggle_callback:
            try:
                threading.Thread(target=self._discord_toggle_callback, daemon=True).start()
                self._log.append_log("SYS: Toggling Discord bot (user request).")
            except Exception as exc:
                self._log.append_log(f"SYS: Discord toggle failed: {exc}")
        else:
            self._log.append_log("SYS: No Discord toggle callback configured.")

    def _discord_sync_clicked(self):
        if self._discord_sync_callback:
            try:
                threading.Thread(target=self._discord_sync_callback, daemon=True).start()
                self._log.append_log("SYS: Syncing Discord slash commands (user request).")
            except Exception as exc:
                self._log.append_log(f"SYS: Discord sync failed: {exc}")
        else:
            self._log.append_log("SYS: No Discord sync callback configured.")

    def set_discord_toggle_callback(self, callback: Optional[Callable[[], None]]):
        self._discord_toggle_callback = callback

    def set_discord_sync_callback(self, callback: Optional[Callable[[], None]]):
        self._discord_sync_callback = callback

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #140006; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 3px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #00140a; color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #001f10; }}
            """)

    def _edit_context_overrides(self):
        dlg = ContextOverrideDialog(self, CONFIG_DIR / "audio_context_overrides.json")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._log.append_log("SYS: Context override definitions saved.")

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _open_social_media_manager_dialog(self):
        dlg = SocialMediaManagerDialog(self, command_callback=self._sm_send_command)
        dlg.exec()

    def _sm_send_command(self, command: str):
        self._input.setText(command)
        self._send()

    def _handle_poll_image_picker_request(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select images for poll",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp)",
        )
        self._poll_image_picker_result = paths
        if self._poll_image_picker_event:
            self._poll_image_picker_event.set()

    def request_poll_image_paths(self) -> list[str]:
        self._poll_image_picker_event = threading.Event()
        self._poll_image_picker_result = None
        self._poll_image_picker_request.emit()
        self._poll_image_picker_event.wait(timeout=120)
        return self._poll_image_picker_result or []

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _set_context_status(self, status: str):
        status_text = status or "Context: unknown"
        color = C.PAUSED if "PAUSED" in status_text.upper() else C.GREEN if "LISTENING" in status_text.upper() else C.ACC2
        self._context_badge.setText(status_text)
        self._context_badge.setStyleSheet(f"color: {color}; background: transparent;")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str, ngrok_token: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "gemini_api_key": key,
            "os_system": os_name,
        }
        if ngrok_token:
            data["ngrok_auth_token"] = ngrok_token
        API_FILE.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. JARVIS online.")

    def _toggle_always_on_top(self):
        self._always_on_top = not self._always_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._always_on_top)
        self.show()  # re-show to apply flag
        self._log.append_log(f"SYS: Always-on-top {'enabled' if self._always_on_top else 'disabled'}.")

    def _toggle_mini_mode(self):
        # Compact the UI to a minimal footprint, or restore previous layout
        if not self._mini_mode:
            # enter mini mode: save state
            self._saved_geometry = self.saveGeometry()
            self._saved_left_visible = self._left_panel.isVisible()
            self._saved_header_visible = self._header.isVisible() if hasattr(self, '_header') else True
            self._saved_left_visible = self._left_panel.isVisible()
            self._saved_right_visible = self._right_panel.isVisible()
            self._saved_footer_visible = self._footer.isVisible() if hasattr(self, '_footer') else True
            # hide panels and shrink to face-only mode
            self._header.hide()
            self._left_panel.hide()
            self._right_panel.hide()
            if hasattr(self, '_footer'):
                self._footer.hide()
            self.setMinimumSize(220, 220)
            self._mini_mode = True
            self.resize(240, 240)
            self._log.append_log("SYS: Headless face-only mode enabled.")
        else:
            # restore
            try:
                if self._saved_header_visible and hasattr(self, '_header'):
                    self._header.show()
                if self._saved_left_visible:
                    self._left_panel.show()
                if self._saved_right_visible:
                    self._right_panel.show()
                if hasattr(self, '_footer') and self._saved_footer_visible:
                    self._footer.show()
            except Exception:
                pass
            self.setMinimumSize(*self._default_min_size)
            if self._saved_geometry:
                self.restoreGeometry(self._saved_geometry)
            self._mini_mode = False
            self._log.append_log("SYS: Headless face-only mode disabled.")
        self._update_headless_button()

    def _toggle_transparent_bg(self):
        # Toggle window opacity and click-through to make the UI a floating overlay.
        self._transparent_bg = not self._transparent_bg
        try:
            self.hide()
            if self._transparent_bg:
                self.setWindowOpacity(0.78)
                self._apply_transparent_input(True)
                self._log.append_log("SYS: See-through overlay enabled (click-through active).")
            else:
                self.setWindowOpacity(1.0)
                self._apply_transparent_input(False)
                self.activateWindow()
                self.raise_()
                self._log.append_log("SYS: See-through overlay disabled.")
        except Exception:
            self._log.append_log("ERR: Failed to toggle see-through overlay.")

    def _small_toggle_style(self) -> str:
        return f"""
            QPushButton {{
                background: #10131a; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                background: {C.BORDER_B}; color: {C.PRI};
                border-color: {C.PRI};
            }}
        """

    def _set_mouse_transparent(self, transparent: bool):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, transparent)
        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, transparent)

    def _set_native_click_through(self, enable: bool):
        if _OS != "Windows":
            return
        try:
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enable:
                style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def _apply_transparent_input(self, enable: bool):
        flags = self.windowFlags()
        if enable:
            flags |= Qt.WindowType.WindowTransparentForInput
            self._set_mouse_transparent(True)
            self._set_native_click_through(True)
        else:
            flags &= ~Qt.WindowType.WindowTransparentForInput
            self._set_mouse_transparent(False)
            self._set_native_click_through(False)
        self.setWindowFlags(flags)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enable)
        self.show()

    def _update_headless_button(self):
        if hasattr(self, '_headless_btn'):
            if self._mini_mode:
                self._headless_btn.setText("🕶 HEADLESS ON")
                self._headless_btn.setStyleSheet(f"background: {C.PRI}; color: {C.DARK}; border: 1px solid {C.GREEN}; border-radius: 3px; padding: 2px 6px;")
            else:
                self._headless_btn.setText("🕶 HEADLESS")
                self._headless_btn.setStyleSheet(self._small_toggle_style())

    def _update_startup_button(self):
        if hasattr(self, '_startup_btn'):
            if self._startup_enabled:
                self._startup_btn.setText("⏰ AUTOSTART ON")
                self._startup_btn.setStyleSheet(f"background: {C.GREEN}; color: {C.DARK}; border: 1px solid {C.GREEN}; border-radius: 3px; padding: 2px 6px;")
            else:
                self._startup_btn.setText("⏰ AUTOSTART")
                self._startup_btn.setStyleSheet(self._small_toggle_style())

    def _toggle_headless_mode(self):
        self._toggle_mini_mode()
        self._headless_mode = self._mini_mode

    def _toggle_startup(self):
        if os.name != "nt":
            self._log.append_log("SYS: Auto-start is only supported on Windows.")
            return

        try:
            if is_in_startup(self._startup_method):
                result = remove_from_startup(self._startup_method)
                self._startup_enabled = result.startswith("✅")
            else:
                result = add_to_startup(self._startup_method)
                self._startup_enabled = result.startswith("✅")
            self._log.append_log(f"SYS: {result}")
            self._update_startup_button()
        except Exception as exc:
            self._log.append_log(f"ERR: Auto-start toggle failed: {exc}")

    def set_startup_status(self, enabled: bool):
        self._startup_enabled = enabled
        self._update_startup_button()

    def _set_remote_urls(self, local_url: str | None, public_url: str | None, status_message: str | None = None):
        self._remote_url = local_url
        self._remote_public_url = public_url
        if public_url:
            remote_label = public_url
        elif local_url:
            remote_label = local_url
        elif status_message:
            remote_label = status_message
        else:
            remote_label = "unavailable"

        if remote_label and remote_label.startswith("http"):
            self._remote_url_lbl.setText(f'Remote URL: <a href="{remote_label}">{remote_label}</a>')
            self._remote_url_lbl.setToolTip("Click to open the remote control page")
        else:
            self._remote_url_lbl.setText(f"Remote URL: {remote_label}")
            self._remote_url_lbl.setToolTip("")

        self._log.append_log(f"SYS: Remote control URL set to {remote_label}")

    def _open_remote_url(self):
        url = self._remote_public_url or self._remote_url
        if not url:
            self._log.append_log("SYS: No remote URL is configured yet.")
            return
        self._log.append_log(f"SYS: Opening remote control URL: {url}")
        QDesktopServices.openUrl(QUrl(url))

    def set_discord_restart_callback(self, callback: Optional[Callable[[], None]]) -> None:
        self._discord_restart_callback = callback

    def _f8_action(self):
        if self._discord_restart_callback:
            self._log.append_log("SYS: Restarting Discord bot...")
            try:
                self._discord_restart_callback()
            except Exception as exc:
                self._log.append_log(f"SYS: Discord restart failed: {exc}")
        else:
            self._open_remote_url()

class ContextOverrideDialog(QDialog):
    def __init__(self, parent=None, config_path: Path | str = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Per-App Context Overrides")
        self.setModal(True)
        self.setMinimumSize(680, 500)

        self._config_path = Path(config_path) if config_path else CONFIG_DIR / "audio_context_overrides.json"
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        layout = QVBoxLayout(self)
        header = QLabel("Per-App Context Overrides")
        header.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(header)

        description = QLabel(
            "Define per-app audio context overrides as JSON.\n"
            "Use a root object with an 'overrides' list, where each override may include:\n"
            "  - pattern: regex to match window title or process name\n"
            "  - action: whitelist or blacklist\n"
            "  - context: gaming, meeting, coding, etc.\n"
            "  - should_listen: true/false\n"
            "  - sensitivity_multiplier: 0.0-1.0\n"
            "Example: {\"overrides\": [{\"pattern\": \"chrome.exe\", \"action\": \"whitelist\"}]}"
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        layout.addWidget(description)

        self._editor = QTextEdit()
        self._editor.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER};")
        layout.addWidget(self._editor, 1)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Overrides")
        save_btn.setStyleSheet(f"background: {C.GREEN}; color: {C.DARK}; padding: 8px; border-radius: 4px;")
        save_btn.clicked.connect(self._save_config)
        buttons.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"background: {C.ACC}; color: {C.DARK}; padding: 8px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

        self._load_config()

    def _load_config(self):
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as fh:
                    content = fh.read().strip()
                    if content:
                        self._editor.setPlainText(content)
                    else:
                        self._editor.setPlainText("{\n  \"overrides\": []\n}")
            except Exception:
                self._editor.setPlainText("{\n  \"overrides\": []\n}")
        else:
            self._editor.setPlainText("{\n  \"overrides\": []\n}")

    def _save_config(self):
        text = self._editor.toPlainText().strip()
        if not text:
            text = "{\n  \"overrides\": []\n}"

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                parsed = {"overrides": parsed}
            elif isinstance(parsed, dict) and "overrides" not in parsed:
                raise ValueError("Root object must contain an 'overrides' list.")
            if not isinstance(parsed["overrides"], list):
                raise ValueError("'overrides' must be a JSON array.")
            with open(self._config_path, "w", encoding="utf-8") as fh:
                json.dump(parsed, fh, indent=2)
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid JSON", f"Could not save overrides: {exc}")


class SocialMediaManagerDialog(QDialog):
    def __init__(self, parent=None, command_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Social Media Manager")
        self.setModal(True)
        self.setMinimumSize(520, 420)
        self._command_callback = command_callback

        layout = QVBoxLayout(self)
        header = QLabel("Social Media Manager")
        header.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(header)

        description = QLabel(
            "Create ideas, scripts, auto publish videos, schedule posts, and review analytics."
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        layout.addWidget(description)

        form = QVBoxLayout()
        self._platform_select = QComboBox()
        self._platform_select.addItems(["youtube", "tiktok"])
        self._platform_select.setFixedHeight(28)
        self._platform_select.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        form.addWidget(self._platform_select)

        self._niche_input = QLineEdit()
        self._niche_input.setPlaceholderText("Niche (e.g. productivity, finance)")
        self._niche_input.setFixedHeight(28)
        self._niche_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._niche_input)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Optional video title")
        self._title_input.setFixedHeight(28)
        self._title_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._title_input)

        self._channel_input = QLineEdit()
        self._channel_input.setPlaceholderText("Optional channel name or id")
        self._channel_input.setFixedHeight(28)
        self._channel_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._channel_input)

        self._description_input = QLineEdit()
        self._description_input.setPlaceholderText("Optional description for uploads")
        self._description_input.setFixedHeight(28)
        self._description_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._description_input)

        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("Optional comma-separated tags")
        self._tags_input.setFixedHeight(28)
        self._tags_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._tags_input)

        self._publish_time_input = QLineEdit()
        self._publish_time_input.setPlaceholderText("Schedule publish at (YYYY-MM-DDTHH:MM)")
        self._publish_time_input.setFixedHeight(28)
        self._publish_time_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._publish_time_input)

        self._recurrence_input = QLineEdit()
        self._recurrence_input.setPlaceholderText("Recurrence (daily, weekly, monthly)")
        self._recurrence_input.setFixedHeight(28)
        self._recurrence_input.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px;")
        form.addWidget(self._recurrence_input)

        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)

        idea_btn = QPushButton("Idea")
        idea_btn.setFixedHeight(30)
        idea_btn.setStyleSheet(f"background: {C.GREEN}; color: {C.DARK}; border-radius: 4px;")
        idea_btn.clicked.connect(self._idea)
        button_row.addWidget(idea_btn)

        script_btn = QPushButton("Script")
        script_btn.setFixedHeight(30)
        script_btn.setStyleSheet(f"background: {C.ACC2}; color: {C.DARK}; border-radius: 4px;")
        script_btn.clicked.connect(self._script)
        button_row.addWidget(script_btn)

        layout.addLayout(button_row)

        button_row2 = QHBoxLayout()
        button_row2.setSpacing(6)

        publish_btn = QPushButton("Auto Publish")
        publish_btn.setFixedHeight(30)
        publish_btn.setStyleSheet(f"background: {C.PRI}; color: {C.DARK}; border-radius: 4px;")
        publish_btn.clicked.connect(self._auto_publish)
        button_row2.addWidget(publish_btn)

        schedule_btn = QPushButton("Schedule")
        schedule_btn.setFixedHeight(30)
        schedule_btn.setStyleSheet(f"background: {C.ACC}; color: {C.DARK}; border-radius: 4px;")
        schedule_btn.clicked.connect(self._schedule)
        button_row2.addWidget(schedule_btn)

        layout.addLayout(button_row2)

        button_row_auth = QHBoxLayout()
        button_row_auth.setSpacing(6)

        auth_btn = QPushButton("Authorize YouTube")
        auth_btn.setFixedHeight(30)
        auth_btn.setStyleSheet(f"background: {C.BORDER}; color: {C.TEXT}; border-radius: 4px;")
        auth_btn.clicked.connect(self._authorize_youtube)
        button_row_auth.addWidget(auth_btn)

        open_page_btn = QPushButton("Open Upload Page")
        open_page_btn.setFixedHeight(30)
        open_page_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border-radius: 4px;")
        open_page_btn.clicked.connect(self._open_upload_page)
        button_row_auth.addWidget(open_page_btn)

        layout.addLayout(button_row_auth)

        button_row3 = QHBoxLayout()
        button_row3.setSpacing(6)

        list_btn = QPushButton("Schedules")
        list_btn.setFixedHeight(30)
        list_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border-radius: 4px;")
        list_btn.clicked.connect(self._list_schedules)
        button_row3.addWidget(list_btn)

        analytics_btn = QPushButton("Analytics")
        analytics_btn.setFixedHeight(30)
        analytics_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border-radius: 4px;")
        analytics_btn.clicked.connect(self._analytics)
        button_row3.addWidget(analytics_btn)

        layout.addLayout(button_row3)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(28)
        close_btn.setStyleSheet(f"background: {C.BORDER}; color: {C.TEXT}; border-radius: 4px;")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    def _build_command(self, action: str) -> str:
        platform = self._platform_select.currentText()
        niche = self._niche_input.text().strip() or "AI faceless content"
        title = self._title_input.text().strip()
        channel = self._channel_input.text().strip()
        description = self._description_input.text().strip()
        tags = self._tags_input.text().strip()
        publish_time = self._publish_time_input.text().strip()
        recurrence = self._recurrence_input.text().strip()

        cmd = f"social_media_creator action={action} platform={platform} niche=\"{niche}\""
        if title:
            cmd += f" title=\"{title}\""
        if channel:
            cmd += f" channel=\"{channel}\""
        if description:
            cmd += f" description=\"{description}\""
        if tags:
            cmd += f" tags=\"{tags}\""
        if publish_time:
            cmd += f" publish_time=\"{publish_time}\""
        if recurrence:
            cmd += f" recurrence={recurrence}"
        if action in ["auto_publish", "schedule_publish"]:
            cmd += " auto_create=true"
        return cmd

    def _execute(self, command: str):
        if self._command_callback:
            self._command_callback(command)
            self.accept()

    def _idea(self):
        self._execute(self._build_command("idea"))

    def _script(self):
        self._execute(self._build_command("script"))

    def _auto_publish(self):
        self._execute(self._build_command("auto_publish"))

    def _schedule(self):
        if not self._publish_time_input.text().strip():
            QMessageBox.warning(self, "Missing schedule", "Please enter a publish time before scheduling.")
            return
        self._execute(self._build_command("schedule_publish"))

    def _authorize_youtube(self):
        self._execute("social_media_creator action=authorize_youtube")

    def _open_upload_page(self):
        self._execute(f"social_media_creator action=open_upload platform={self._platform_select.currentText()}")

    def _list_schedules(self):
        self._execute("social_media_creator action=list_schedules")

    def _analytics(self):
        self._execute(f"social_media_creator action=analytics_summary platform={self._platform_select.currentText()}")

class ImageApprovalDialog(QDialog):
    def __init__(self, image_path: str, prompt: str = "", edited: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS Image Preview")
        self.setModal(True)
        self.setMinimumSize(700, 780)

        layout = QVBoxLayout(self)
        header = QLabel("Edited preview" if edited else "Generated image preview")
        header.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(header)

        label = QLabel()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            max_width = 660
            max_height = 620
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            face_overlay = QRectF(
                pixmap.width() * 0.20,
                pixmap.height() * 0.20,
                pixmap.width() * 0.60,
                pixmap.height() * 0.18,
            )
            painter.fillRect(face_overlay, qcol(C.BG, 180))
            painter.setPen(qcol(C.PRI, 255))
            painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            painter.drawText(face_overlay, Qt.AlignmentFlag.AlignCenter, "LIKE THIS FACE?")
            painter.end()
            label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        if prompt:
            prompt_label = QLabel(f"Prompt: {prompt}")
            prompt_label.setWordWrap(True)
            prompt_label.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
            layout.addWidget(prompt_label)

        buttons = QHBoxLayout()
        approve = QPushButton("Save to Photos")
        approve.setStyleSheet(f"background: {C.GREEN}; color: {C.DARK}; padding: 10px; border-radius: 5px;")
        approve.clicked.connect(self.accept)
        buttons.addWidget(approve)

        reject = QPushButton("Edit image")
        reject.setStyleSheet(f"background: {C.ACC}; color: {C.DARK}; padding: 10px; border-radius: 5px;")
        reject.clicked.connect(self.reject)
        buttons.addWidget(reject)
        layout.addLayout(buttons)

    def exec_(self) -> int:
        return super().exec()

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._approval_event = threading.Event()
        self._approval_result = False
        self._win._approval_owner = self
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def speaking(self) -> bool:
        return getattr(self._win.hud, "speaking", False)

    def open_poll_image_picker(self) -> list[str]:
        return self._win.request_poll_image_paths()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def set_discord_status(self, status: str):
        self._win._discord_status_sig.emit(status)

    def set_discord_restart_callback(self, callback: Optional[Callable[[], None]]):
        self._win.set_discord_restart_callback(callback)

    def set_discord_toggle_callback(self, callback: Optional[Callable[[], None]]):
        self._win.set_discord_toggle_callback(callback)

    def set_discord_sync_callback(self, callback: Optional[Callable[[], None]]):
        self._win.set_discord_sync_callback(callback)

    def set_context_status(self, status: str):
        self._win._context_status_sig.emit(status)

    def set_remote_urls(self, local_url: str | None, public_url: str | None, status_message: str | None = None):
        if hasattr(self._win, '_set_remote_urls'):
            self._win._set_remote_urls(local_url, public_url, status_message)

    # Alias for underscore version to match main.py calls
    def _set_remote_urls(self, local_url: str | None, public_url: str | None, status_message: str | None = None):
        self.set_remote_urls(local_url, public_url, status_message)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def show_image_approval(self, image_path: str, prompt: str = "", edited: bool = False) -> bool:
        self._approval_event.clear()
        self._approval_result = False
        self._win._image_approval_request.emit(image_path, prompt, edited)
        self._approval_event.wait(timeout=60)
        return bool(self._approval_result)
