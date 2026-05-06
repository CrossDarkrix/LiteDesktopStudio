import concurrent.futures
import sys
import os
import json
import math
import time
import warnings
import queue
import ctypes
import threading
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import soundcard as sc
import numpy as np
import psutil
import calendar as py_calendar
from PySide6.QtCore import (
    Qt,
    QRectF,
    QPoint,
    QTimer,
    QSize,
    QEvent,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QFont,
    QPen,
    QIcon,
    QBrush,
    QLinearGradient,
    QTextDocument,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QTextEdit,
    QColorDialog,
    QFileDialog,
    QSpinBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QMessageBox,
    QListWidget,
    QCheckBox,
    QGridLayout,
    QScrollArea,
)
warnings.filterwarnings(
    "ignore",
    message="data discontinuity in recording",
    category=Warning
)

APP_NAME = "LiteDeskEngine"
CONFIG_PATH = "config.json"

def widget_bg_color(cfg, default_alpha=155):
    bg = QColor(getattr(cfg, "bg", None) or "#10141C")

    alpha = getattr(cfg, "bg_alpha", default_alpha)

    try:
        alpha = int(alpha)
    except Exception:
        alpha = default_alpha

    alpha = max(0, min(255, alpha))
    bg.setAlpha(alpha)

    return bg

def format_bytes_per_sec(value):
    value = float(value)

    units = ["B/s", "KB/s", "MB/s", "GB/s"]

    for unit in units:
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0

    return f"{value:.1f} TB/s"

class WindowsTheme:
    @staticmethod
    def is_dark_mode() -> bool:
        """
        Windows の AppsUseLightTheme を読む。
        0 = dark
        1 = light
        """
        try:
            import winreg
            path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
        except Exception:
            return False

    @staticmethod
    def apply_immersive_dark_titlebar(hwnd: int, enable: bool):
        """
        Windows 10/11 の DWM ダークタイトルバー属性。
        フレームレスなので実質補助的。
        """
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1 if enable else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:
            pass

class VolumeController:
    def __init__(self):
        self.available = False
        self._volume_cache = 50
        self._mute_cache = False
        self._running = True
        self._cmd_queue = queue.Queue()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        endpoint = None
        need_uninit = False
        try:
            import sys
            # comtypes が import 時に COM 初期化する前に指定する
            # COINIT_APARTMENTTHREADED = 0x2
            sys.coinit_flags = 0x2
            import comtypes
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            try:
                comtypes.CoInitializeEx(0x2)
                need_uninit = True
            except OSError as e:
                # RPC_E_CHANGED_MODE
                # すでにこのスレッドで別モード初期化済みの場合
                if getattr(e, "winerror", None) == -2147417850:
                    need_uninit = False
                else:
                    raise
            except Exception:
                need_uninit = False

            device = AudioUtilities.GetSpeakers()

            # 新しめの pycaw では AudioDevice.EndpointVolume を使う
            endpoint = getattr(device, "EndpointVolume", None)

            # 古い/別系統のAPI向け fallback
            if endpoint is None and hasattr(device, "Activate"):
                interface = device.Activate(
                    IAudioEndpointVolume._iid_,
                    CLSCTX_ALL,
                    None
                )
                endpoint = interface.QueryInterface(IAudioEndpointVolume)

            if endpoint is None:
                raise RuntimeError(
                    "Could not get endpoint volume from AudioUtilities.GetSpeakers()"
                )

            try:
                device_name = getattr(device, "FriendlyName", "Speakers")
            except Exception:
                device_name = "Speakers"

            with self._lock:
                self.available = True
                self._volume_cache = int(endpoint.GetMasterVolumeLevelScalar() * 100)
                self._mute_cache = bool(endpoint.GetMute())

            # print(f"[VolumeController] pycaw ready: {device_name}")

            last_poll = 0.0

            while self._running:
                try:
                    cmd = self._cmd_queue.get(timeout=0.05)
                except queue.Empty:
                    cmd = None

                if cmd:
                    name = cmd[0]

                    if name == "set_volume":
                        value = int(cmd[1])
                        value = max(0, min(100, value))
                        endpoint.SetMasterVolumeLevelScalar(value / 100.0, None)

                        with self._lock:
                            self._volume_cache = value

                    elif name == "set_mute":
                        value = bool(cmd[1])
                        endpoint.SetMute(value, None)

                        with self._lock:
                            self._mute_cache = value

                    elif name == "toggle_mute":
                        current = bool(endpoint.GetMute())
                        endpoint.SetMute(not current, None)

                        with self._lock:
                            self._mute_cache = not current

                    elif name == "stop":
                        break

                now = time.time()

                if now - last_poll >= 0.2:
                    try:
                        vol = int(endpoint.GetMasterVolumeLevelScalar() * 100)
                        mute = bool(endpoint.GetMute())

                        with self._lock:
                            self._volume_cache = vol
                            self._mute_cache = mute
                            self.available = True

                    except Exception:
                        pass

                    last_poll = now

        except Exception as e:
            print("[VolumeController] pycaw unavailable:", repr(e))

            with self._lock:
                self.available = False
        finally:
            try:
                endpoint = None
            except Exception:
                pass

            try:
                if need_uninit:
                    comtypes.CoUninitialize()
            except Exception:
                pass

            try:
                if "need_uninit" in locals() and need_uninit:
                    comtypes.CoUninitialize()
            except Exception:
                pass

    def get_volume(self) -> int:
        with self._lock:
            return int(self._volume_cache)

    def set_volume(self, value: int):
        value = max(0, min(100, int(value)))
        with self._lock:
            self._volume_cache = value

        if self.available:
            self._cmd_queue.put(("set_volume", value))

    def get_mute(self) -> bool:
        with self._lock:
            return bool(self._mute_cache)

    def set_mute(self, value: bool):
        with self._lock:
            self._mute_cache = bool(value)

        if self.available:
            self._cmd_queue.put(("set_mute", bool(value)))

    def toggle_mute(self):
        if self.available:
            self._cmd_queue.put(("toggle_mute",))

    def stop(self):
        self._running = False
        try:
            self._cmd_queue.put(("stop",))
        except Exception:
            pass

class AudioEngine:
    def __init__(self):
        self.bars = 52
        self.spectrum = np.zeros(self.bars, dtype=np.float32)
        self.running = False
        self.lock = threading.Lock()
        self.use_fake = False
        self.backend_name = "soundcard"

    def start(self):
        self.running = True
        concurrent.futures.ThreadPoolExecutor(os.cpu_count() * 999999).submit(self._run)

    def stop(self):
        self.running = False

    def get_spectrum(self) -> np.ndarray:
        with self.lock:
            return self.spectrum.copy()

    def _run(self):
        try:
            self._run_soundcard_loopback()
        except Exception:
            self.use_fake = True
            self.backend_name = "fallback"
            self._run_fake()

    def _find_loopback_microphone(self):
        # ループバックを含めてマイク一覧を取得
        # SoundCard 公式では include_loopback=True が speaker outputs 録音用
        mics = sc.all_microphones(include_loopback=True)

        # isloopback 属性があるものを優先
        loopbacks = [m for m in mics if getattr(m, "isloopback", False)]

        if loopbacks:
            # まず default speaker 名に近いものを探す
            try:
                default_speaker = sc.default_speaker()
                speaker_name = default_speaker.name.lower()

                for mic in loopbacks:
                    if speaker_name in mic.name.lower() or mic.name.lower() in speaker_name:
                        return mic
            except Exception:
                pass

            # 見つからなければ最初の loopback
            return loopbacks[0]

        # isloopback が取れない環境向けの保険
        for mic in mics:
            name = mic.name.lower()
            if "loopback" in name or "what u hear" in name or "stereo mix" in name:
                return mic

        raise RuntimeError("loopback microphone not found")

    def _run_soundcard_loopback(self):
        samplerate = 48000
        blocksize = 1024

        mic = self._find_loopback_microphone()
        self.backend_name = f"soundcard: {mic.name}"

        with mic.recorder(
            samplerate=samplerate,
            blocksize=blocksize
        ) as recorder:
            while self.running:
                data = recorder.record(numframes=blocksize)

                if data is None or len(data) == 0:
                    time.sleep(0.005)
                    continue

                # data は frames x channels の numpy array
                if data.ndim == 2:
                    mono = data.mean(axis=1)
                else:
                    mono = data

                # DC 成分除去
                mono = mono - np.mean(mono)

                # 窓関数でスペクトルを安定化
                window = np.hanning(len(mono))
                mono = mono * window

                spec = np.abs(np.fft.rfft(mono))

                # 低域〜中域を中心に使う
                spec = spec[:len(spec) // 2]

                if spec.size <= 0:
                    continue

                # 線形ではなく対数的にサンプリングすると見た目が自然
                idx = np.geomspace(1, spec.size - 1, self.bars).astype(int)
                bars = spec[idx]

                # 対数圧縮
                bars = np.log1p(bars)

                maxv = np.max(bars)
                if maxv > 0:
                    bars = bars / maxv

                # スムージング
                with self.lock:
                    self.spectrum = (
                        self.spectrum * 0.72 +
                        bars.astype(np.float32) * 0.28
                    )

    def _run_fake(self):
        t = 0.0
        while self.running:
            arr = []
            for i in range(self.bars):
                v = (
                    math.sin(t * 2.0 + i * 0.35) * 0.4 +
                    math.sin(t * 4.7 + i * 0.12) * 0.25 +
                    np.random.random() * 0.25
                )
                arr.append(max(0.03, min(1.0, abs(v))))

            with self.lock:
                self.spectrum = (
                    self.spectrum * 0.75 +
                    np.array(arr, dtype=np.float32) * 0.25
                )

            t += 0.08
            time.sleep(1 / 60)

class MediaController:
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3

    KEYEVENTF_KEYUP = 0x0002

    def __init__(self):
        self.available = sys.platform.startswith("win")

    def _press_key(self, vk_code: int):
        if not self.available:
            return

        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, self.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print("[MediaController] key press failed:", repr(e))

    def play_pause(self):
        self._press_key(self.VK_MEDIA_PLAY_PAUSE)

    def next_track(self):
        self._press_key(self.VK_MEDIA_NEXT_TRACK)

    def previous_track(self):
        self._press_key(self.VK_MEDIA_PREV_TRACK)

    def stop(self):
        self._press_key(self.VK_MEDIA_STOP)


class SystemMonitor:
    def __init__(self):
        _net_update = 0.0
        self.cpu = 0.0
        self.last_net_sent = None
        self.last_net_recv = None

        self._init_network_counters()
        self.memory = 0.0
        self.disk = 0.0

        self.net_up = 0.0
        self.net_down = 0.0
        self.net_sent_total = 0
        self.net_recv_total = 0

        self.net_up_history = []
        self.net_down_history = []
        self.net_history_limit = 30

        self.last_update = 0.0

    def _init_network_counters(self):
        try:
            counters = psutil.net_io_counters()

            self.last_net_sent = counters.bytes_sent
            self.last_net_recv = counters.bytes_recv
            self.net_sent_total = counters.bytes_sent
            self.net_recv_total = counters.bytes_recv

            self.last_net_update = time.time()

        except Exception as e:
            print("[SystemMonitor] network init failed:", repr(e))

            self.last_net_sent = 0
            self.last_net_recv = 0
            self.net_sent_total = 0
            self.net_recv_total = 0
            self.last_net_update = time.time()

    def update_network(self, now=None):
        if now is None:
            now = time.time()
        try:
            counters = psutil.net_io_counters()

            sent = counters.bytes_sent
            recv = counters.bytes_recv

            if self.last_net_sent is None or self.last_net_recv is None:
                self.last_net_sent = sent
                self.last_net_recv = recv
                self.last_net_update = now
                return

            elapsed = now - self.last_net_update

            if elapsed <= 0.0:
                elapsed = 1.0

            sent_delta = sent - self.last_net_sent
            recv_delta = recv - self.last_net_recv

            if sent_delta < 0:
                sent_delta = 0

            if recv_delta < 0:
                recv_delta = 0

            self.net_up = sent_delta / elapsed
            self.net_down = recv_delta / elapsed

            self.net_sent_total = sent
            self.net_recv_total = recv

            self.last_net_sent = sent
            self.last_net_recv = recv
            self.last_net_update = now
            self._push_network_history(self.net_down, self.net_up)
        except Exception:
            self.net_up = 0.0
            self.net_down = 0.0
            self._push_network_history(0.0, 0.0)
            self.last_net_update = now

    def _push_network_history(self, down_value, up_value):
        self.net_down_history.append(float(down_value))
        self.net_up_history.append(float(up_value))

        if len(self.net_down_history) > self.net_history_limit:
            self.net_down_history = self.net_down_history[-self.net_history_limit:]

        if len(self.net_up_history) > self.net_history_limit:
            self.net_up_history = self.net_up_history[-self.net_history_limit:]

    def update(self):
        now = time.time()

        if now - self.last_update >= 0.5:
            try:
                self.cpu = psutil.cpu_percent(interval=None)
            except Exception:
                self.cpu = 0.0

            try:
                self.memory = psutil.virtual_memory().percent
            except Exception:
                self.memory = 0.0

            try:
                self.disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
            except Exception:
                self.disk = 0.0
            if now - self.last_net_update >= 1.0:
                self.update_network(now)
            self.last_update = now

@dataclass
class WidgetConfig:
    type: str
    x: int = 100
    y: int = 100
    w: int = 300
    h: int = 120
    title: str = "Widget"
    color: str = "#5BE7FF"
    bg: str = "#141820"
    text: str = ""
    font_size: int = 14

    bg_alpha: int = 155
    """
    [bg_alpha]
        0   = 完全透明
        155 = 半透明
        255 = 完全不透明
    """
    cpu_color: str = "#5BE7FF"
    memory_color: str = "#B388FF"
    disk_color: str = "#80FF9F"


class BaseWidget:
    def __init__(self, cfg: WidgetConfig):
        self.cfg = cfg
        self.selected = False

    @property
    def rect(self) -> QRectF:
        return QRectF(self.cfg.x, self.cfg.y, self.cfg.w, self.cfg.h)

    def contains(self, pos: QPoint) -> bool:
        return self.rect.contains(pos)

    def paint(self, p: QPainter, ctx: Dict):
        raise NotImplementedError

    def to_config(self) -> WidgetConfig:
        return self.cfg


class VisualizerWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        audio: AudioEngine = ctx["audio"]
        bars = audio.get_spectrum()

        r = self.rect
        radius = 16

        p.setRenderHint(QPainter.Antialiasing, False)

        bg = widget_bg_color(self.cfg)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, radius, radius)

        margin = 14
        available_w = r.width() - margin * 2
        available_h = r.height() - margin * 2 - 18
        bar_gap = 3
        bar_w = max(2, (available_w / len(bars)) - bar_gap)

        color = QColor(self.cfg.color)

        grad = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        grad.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 240))
        grad.setColorAt(1, QColor(255, 255, 255, 90))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)

        base_y = r.bottom() - margin
        for i, v in enumerate(bars):
            h = max(2, available_h * float(v))
            x = r.left() + margin + i * (bar_w + bar_gap)
            y = base_y - h
            p.drawRoundedRect(QRectF(x, y, bar_w, h), 3, 3)

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QColor(230, 240, 255, 220))
        p.setFont(QFont("Segoe UI", 9))
        label = ""
        if audio.use_fake:
            label += " / fallback"
        p.drawText(QRectF(r.left() + 14, r.top() + 8, r.width() - 20, 18), label)

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

class MediaPlayerWidget(BaseWidget):
    def button_rects(self):
        r = self.rect
        button_size = min(46, max(32, int(r.height() * 0.28)))
        gap = 10
        total_w = button_size * 4 + gap * 3
        start_x = r.left() + (r.width() - total_w) / 2
        y = r.top() + r.height() * 0.48
        return {
            "prev": QRectF(
                start_x,
                y,
                button_size,
                button_size
            ),
            "play": QRectF(
                start_x + button_size + gap,
                y,
                button_size,
                button_size
            ),
            "next": QRectF(
                start_x + (button_size + gap) * 2,
                y,
                button_size,
                button_size
            ),
            "stop": QRectF(
                start_x + (button_size + gap) * 3,
                y,
                button_size,
                button_size
            ),
        }

    def button_at(self, pos: QPoint):
        rects = self.button_rects()
        for name, rect in rects.items():
            if rect.contains(pos):
                return name

        return None

    def paint(self, p: QPainter, ctx: Dict):
        r = self.rect
        p.save()
        bg = widget_bg_color(self.cfg)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        title_color = QColor(245, 248, 255)
        sub_color = QColor(210, 218, 230, 160)
        accent = QColor(self.cfg.color or "#5BE7FF")

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.cfg.title or ""
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(sub_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 34, r.width() - 28, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            "System media controls"
        )

        rects = self.button_rects()

        self._draw_button(p, rects["prev"], "⏮", accent)
        self._draw_button(p, rects["play"], "⏯", accent)
        self._draw_button(p, rects["next"], "⏭", accent)
        self._draw_button(p, rects["stop"], "⏹", accent)

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(210, 218, 230, 130))
        p.drawText(
            QRectF(r.left() + 12, r.bottom() - 24, r.width() - 24, 18),
            Qt.AlignCenter,
            "Prev / Play-Pause / Next / Stop"
        )

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()

    def _draw_button(self, p: QPainter, rect: QRectF, text: str, accent: QColor):
        p.setBrush(QColor(255, 255, 255, 24))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawRoundedRect(rect, 14, 14)

        p.setFont(QFont("Segoe UI Symbol", 16, QFont.Bold))
        p.setPen(accent)
        p.drawText(
            rect,
            Qt.AlignCenter,
            text
        )

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

class SystemWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        monitor: SystemMonitor = ctx["monitor"]
        monitor.update()

        r = self.rect

        bg = widget_bg_color(self.cfg)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(QColor(245, 248, 255))
        p.drawText(QRectF(r.left() + 14, r.top() + 10, r.width(), 24), self.cfg.title)

        items = [
            ("CPU", monitor.cpu, getattr(self.cfg, "cpu_color", None) or "#5BE7FF"),
            ("MEM", monitor.memory, getattr(self.cfg, "memory_color", None) or "#B388FF"),
            ("DISK", monitor.disk, getattr(self.cfg, "disk_color", None) or "#80FF9F"),
        ]

        y = r.top() + 42
        for name, value, col in items:
            self._draw_meter(p, r.left() + 14, y, r.width() - 28, 20, name, value, QColor(col))
            y += 28

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _draw_meter(self, p: QPainter, x, y, w, h, name, value, color: QColor):
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(230, 235, 245))
        p.drawText(QRectF(x, y - 2, 48, h), name)

        bx = x + 48
        bw = max(20, w - 92)

        p.setBrush(QColor(255, 255, 255, 28))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(bx, y + 3, bw, h - 6), 5, 5)

        fill_w = bw * max(0, min(100, value)) / 100.0
        p.setBrush(color)
        p.drawRoundedRect(QRectF(bx, y + 3, fill_w, h - 6), 5, 5)

        p.setPen(QColor(240, 240, 240))
        p.drawText(QRectF(bx + bw + 8, y - 2, 42, h), f"{value:>3.0f}%")

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


class NetworkWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        monitor = ctx["monitor"]
        monitor.update()
        r = self.rect

        bg = widget_bg_color(self.cfg)

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(QColor(245, 248, 255))
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.cfg.title or ""
        )

        content_x = r.left() + 16
        content_w = r.width() - 32

        self._draw_net_row(
            p,
            content_x,
            r.top() + 42,
            content_w,
            "DOWN",
            format_bytes_per_sec(getattr(monitor, "net_down", 0.0)),
            QColor("#5BE7FF")
        )

        self._draw_net_row(
            p,
            content_x,
            r.top() + 68,
            content_w,
            "UP",
            format_bytes_per_sec(getattr(monitor, "net_up", 0.0)),
            QColor("#80FF9F")
        )

        graph_top = r.top() + 98
        graph_bottom_margin = 32
        graph_h = r.bottom() - graph_top - graph_bottom_margin

        if graph_h < 36:
           graph_h = 36

        graph_rect = QRectF(
            content_x,
            graph_top,
            content_w,
            graph_h
        )

        down_history = getattr(monitor, "net_down_history", [])
        up_history = getattr(monitor, "net_up_history", [])

        self._draw_history_graph(
            p,
            graph_rect,
            down_history,
            up_history
        )

        total_down = self._format_total_bytes(
            getattr(monitor, "net_recv_total", 0)
        )
        total_up = self._format_total_bytes(
            getattr(monitor, "net_sent_total", 0)
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(210, 218, 230, 160))
        p.drawText(
            QRectF(r.left() + 16, r.bottom() - 26, r.width() - 32, 18),
            Qt.AlignCenter,
            f"Total ↓ {total_down}   ↑ {total_up}"
        )

        if self.selected and ctx.get("edit_mode", True):
           self._paint_selection(p)

    def _draw_net_row(self, p: QPainter, x, y, w, label, value, color):
        label_rect = QRectF(x, y, 64, 20)
        value_rect = QRectF(x + 70, y, w - 70, 20)

        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor(235, 240, 250))
        p.drawText(
            label_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            label
        )

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(color)
        p.drawText(
            value_rect,
            Qt.AlignRight | Qt.AlignVCenter,
            value
        )

    def _draw_history_graph(self, p: QPainter, rect: QRectF, down_history, up_history):
        if rect.width() <= 4 or rect.height() <= 4:
            return

        p.setBrush(QColor(255, 255, 255, 18))
        p.setPen(QPen(QColor(255, 255, 255, 35), 1))
        p.drawRoundedRect(rect, 8, 8)

        self._draw_grid(p, rect)

        down_values = list(down_history)
        up_values = list(up_history)
        combined = down_values + up_values

        if len(combined) == 0:
            self._draw_empty_graph_text(p, rect)
            return

        max_value = max(combined)

        if max_value <= 0.0:
            self._draw_empty_graph_text(p, rect)
            return

        padded_max = max_value * 1.15

        self._draw_graph_line(
            p,
            rect,
            down_values,
            padded_max,
            QColor("#5BE7FF"),
            True
        )

        self._draw_graph_line(
            p,
            rect,
            up_values,
            padded_max,
            QColor("#80FF9F"),
            False
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(230, 235, 245, 160))

        p.drawText(
            QRectF(rect.left() + 8, rect.top() + 4, rect.width() - 16, 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            "last 30s"
        )

        p.drawText(
            QRectF(rect.left() + 8, rect.bottom() - 20, rect.width() - 16, 16),
            Qt.AlignRight | Qt.AlignVCenter,
            f"max {format_bytes_per_sec(max_value)}"
        )

    def _draw_grid(self, p: QPainter, rect: QRectF):
        grid_pen = QPen(QColor(255, 255, 255, 26), 1)
        p.setPen(grid_pen)

        for i in range(1, 4):
            y = rect.top() + rect.height() * i / 4.0
            p.drawLine(
                int(rect.left()),
                int(y),
                int(rect.right()),
                int(y)
            )

        for i in range(1, 6):
            x = rect.left() + rect.width() * i / 6.0
            p.drawLine(
                int(x),
                int(rect.top()),
                int(x),
                int(rect.bottom())
            )

    def _draw_graph_line(self, p: QPainter, rect: QRectF, history, max_value, color, fill):
        if len(history) == 0:
            return

        values = list(history)

        if len(values) == 1:
            values = [0.0, values[0]]

        points = []
        count = len(values)

        for i, value in enumerate(values):
            x = rect.left() + rect.width() * i / max(1, count - 1)

            if max_value > 0.0:
                ratio = float(value) / max_value
            else:
                ratio = 0.0

            ratio = max(0.0, min(1.0, ratio))
            y = rect.bottom() - rect.height() * ratio

            points.append((x, y))

        if fill and len(points) >= 2:
            path = QPainterPath()
            path.moveTo(points[0][0], rect.bottom())

            for x, y in points:
                path.lineTo(x, y)

            path.lineTo(points[-1][0], rect.bottom())
            path.closeSubpath()

            fill_color = QColor(color)
            fill_color.setAlpha(36)

            p.setBrush(fill_color)
            p.setPen(Qt.NoPen)
            p.drawPath(path)

        pen = QPen(color, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        for i in range(1, len(points)):
            x1, y1 = points[i - 1]
            x2, y2 = points[i]

            p.drawLine(
                int(x1),
                int(y1),
                int(x2),
                int(y2)
            )

        last_x, last_y = points[-1]

        dot_color = QColor(color)
        dot_color.setAlpha(230)

        p.setBrush(dot_color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(
            QPoint(int(last_x), int(last_y)),
            3,
            3
        )

    def _draw_empty_graph_text(self, p: QPainter, rect: QRectF):
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(210, 218, 230, 120))
        p.drawText(
            rect,
            Qt.AlignCenter,
            "waiting for network data..."
        )

    def _format_total_bytes(self, value):
        value = float(value)
        units = ["B", "KB", "MB", "GB", "TB"]

        for unit in units:
            if value < 1024.0:
                return f"{value:.1f} {unit}"
            value /= 1024.0

        return f"{value:.1f} PB"

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


class AnalogClockWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        r = self.rect
        bg = widget_bg_color(self.cfg)

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        now = time.localtime()

        hour = now.tm_hour % 12
        minute = now.tm_min
        second = now.tm_sec

        cx = r.left() + r.width() / 2
        cy = r.top() + r.height() / 2 + 6
        radius = min(r.width(), r.height()) * 0.36

        accent = QColor(self.cfg.color)
        text_color = QColor(245, 248, 255)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(text_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 8, r.width() - 28, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.cfg.title or ""
        )

        p.setPen(QPen(QColor(255, 255, 255, 70), 2))
        p.setBrush(QColor(255, 255, 255, 12))
        p.drawEllipse(QPoint(int(cx), int(cy)), int(radius), int(radius))

        for i in range(60):
            angle = math.radians(i * 6 - 90)

            if i % 5 == 0:
                inner = radius * 0.82
                outer = radius * 0.95
                pen = QPen(QColor(255, 255, 255, 180), 2)
            else:
                inner = radius * 0.88
                outer = radius * 0.95
                pen = QPen(QColor(255, 255, 255, 75), 1)

            x1 = cx + math.cos(angle) * inner
            y1 = cy + math.sin(angle) * inner
            x2 = cx + math.cos(angle) * outer
            y2 = cy + math.sin(angle) * outer

            p.setPen(pen)
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        hour_angle = ((hour + minute / 60.0) * 30.0) - 90.0
        minute_angle = ((minute + second / 60.0) * 6.0) - 90.0
        second_angle = second * 6.0 - 90.0

        self._draw_hand(p, cx, cy, radius * 0.50, hour_angle, QColor(245, 248, 255), 5)
        self._draw_hand(p, cx, cy, radius * 0.70, minute_angle, QColor(210, 225, 255), 3)
        self._draw_hand(p, cx, cy, radius * 0.78, second_angle, accent, 2)

        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(int(cx), int(cy)), 5, 5)

        digital = time.strftime("%H:%M:%S", now)
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(230, 235, 245, 210))
        p.drawText(
            QRectF(r.left(), r.bottom() - 28, r.width(), 20),
            Qt.AlignCenter,
            digital
        )

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _draw_hand(self, p, cx, cy, length, angle_deg, color, width):
        angle = math.radians(angle_deg)
        x = cx + math.cos(angle) * length
        y = cy + math.sin(angle) * length

        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(int(cx), int(cy), int(x), int(y))

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

class CalendarWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        r = self.rect
        p.save()
        bg = widget_bg_color(self.cfg)

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        now = time.localtime()
        year = now.tm_year
        month = now.tm_mon
        today = now.tm_mday

        accent = QColor(self.cfg.color or "#80FF9F")

        title_color = QColor(245, 248, 255)
        month_color = QColor(235, 240, 250)
        weekday_color = QColor(210, 218, 230, 180)
        day_color = QColor(235, 240, 250, 220)
        weekend_color = QColor(255, 205, 205, 200)
        today_text_color = QColor(20, 24, 32)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.cfg.title or ""
        )

        month_label = f"{year} / {month:02d}"

        p.setFont(QFont("Segoe UI", 14, QFont.Bold))
        p.setPen(month_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 36, r.width() - 28, 30),
            Qt.AlignLeft | Qt.AlignVCenter,
            month_label
        )

        grid_left = r.left() + 14
        grid_top = r.top() + 76
        grid_w = r.width() - 28
        grid_h = r.height() - 92

        if grid_w <= 20 or grid_h <= 20:
            p.restore()
            return

        header_h = 22
        cell_w = grid_w / 7.0
        cell_h = max(18.0, (grid_h - header_h) / 6.0)

        weekdays = ["月", "火", "水", "木", "金", "土", "日"]

        p.setFont(QFont("Segoe UI", 8, QFont.Bold))

        for i, day_name in enumerate(weekdays):
            x = grid_left + cell_w * i
            header_rect = QRectF(x, grid_top, cell_w, header_h)

            if i >= 5:
                p.setPen(weekend_color)
            else:
                p.setPen(weekday_color)

            p.drawText(
                header_rect,
                Qt.AlignCenter,
                day_name
            )

        first_weekday, days_in_month = py_calendar.monthrange(year, month)

        day = 1

        for row in range(6):
            for col in range(7):
                cell_index = row * 7 + col

                if cell_index < first_weekday:
                    continue

                if day > days_in_month:
                    continue

                x = grid_left + cell_w * col
                y = grid_top + header_h + cell_h * row
                cell_rect = QRectF(x + 2, y + 2, cell_w - 4, cell_h - 4)

                is_today = day == today

                if is_today:
                    highlight = QColor(accent)
                    highlight.setAlpha(210)

                    p.setBrush(QBrush(highlight))
                    p.setPen(Qt.NoPen)

                    size = min(cell_rect.width(), cell_rect.height(), 28)
                    cx = cell_rect.center().x()
                    cy = cell_rect.center().y()

                    p.drawEllipse(
                        QPoint(int(cx), int(cy)),
                        int(size / 2),
                        int(size / 2)
                    )

                    p.setPen(today_text_color)
                    p.setFont(QFont("Segoe UI", 9, QFont.Bold))

                else:
                    p.setBrush(Qt.NoBrush)

                    if col >= 5:
                        p.setPen(weekend_color)
                    else:
                        p.setPen(day_color)

                    p.setFont(QFont("Segoe UI", 9))

                p.drawText(
                    cell_rect,
                    Qt.AlignCenter,
                    str(day)
                )

                day += 1

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

class HtmlWidget(BaseWidget):
    def __init__(self, cfg: WidgetConfig):
        super().__init__(cfg)
        self.doc = QTextDocument()
        self.last_text = None

    def paint(self, p: QPainter, ctx: Dict):
        r = self.rect

        bg = widget_bg_color(self.cfg)

        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        html = self.cfg.text or """
        <h2 style="color:#5BE7FF;">HTML Widget</h2>
        <p style="color:white;">ここに HTML/CSS 風の内容を書けます。</p>
        """

        if html != self.last_text:
            self.doc.setDefaultFont(QFont("Segoe UI", self.cfg.font_size))
            self.doc.setHtml(html)
            self.doc.setTextWidth(r.width() - 24)
            self.last_text = html

        p.save()
        p.translate(r.left() + 12, r.top() + 10)
        self.doc.drawContents(p, QRectF(0, 0, r.width() - 24, r.height() - 20))
        p.restore()

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

class VolumeWidget(BaseWidget):
    def slider_rect(self):
        r = self.rect
        bx = r.left() + 18
        by = r.top() + 54
        bw = r.width() - 36
        bh = 16
        return QRectF(bx, by, bw, bh)

    def hit_slider(self, pos: QPoint) -> bool:
        sr = self.slider_rect()

        hit_area = QRectF(
            sr.left(),
            sr.top() - 10,
            sr.width(),
            sr.height() + 20
        )

        return hit_area.contains(pos)

    def volume_from_pos(self, pos: QPoint) -> int:
        sr = self.slider_rect()

        if sr.width() <= 0:
            return 0

        ratio = (pos.x() - sr.left()) / sr.width()
        ratio = max(0.0, min(1.0, ratio))

        return int(round(ratio * 100))

    def paint(self, p: QPainter, ctx: Dict):
        volume: VolumeController = ctx["volume"]
        v = volume.get_volume()

        r = self.rect
        bg = widget_bg_color(self.cfg)

        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(QColor(245, 248, 255))
        p.drawText(QRectF(r.left() + 14, r.top() + 10, r.width(), 24), "Volume")

        bx = r.left() + 18
        by = r.top() + 54
        bw = r.width() - 36
        bh = 16

        p.setBrush(QColor(255, 255, 255, 30))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 8, 8)

        p.setBrush(QColor(self.cfg.color))
        p.drawRoundedRect(QRectF(bx, by, bw * v / 100.0, bh), 8, 8)

        p.setPen(QColor(240, 240, 240))
        p.setFont(QFont("Segoe UI", 18, QFont.Bold))
        p.drawText(QRectF(r.left(), r.top() + 72, r.width(), 40), Qt.AlignCenter, f"{v}%")

        if not volume.available:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(255, 210, 120))
            p.drawText(QRectF(r.left() + 12, r.bottom() - 22, r.width() - 24, 16),
                       "pycaw unavailable")

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


def create_widget(cfg: WidgetConfig) -> BaseWidget:
    if cfg.type == "visualizer":
        return VisualizerWidget(cfg)

    if cfg.type == "system":
        return SystemWidget(cfg)

    if cfg.type == "html":
        return HtmlWidget(cfg)

    if cfg.type == "volume":
        return VolumeWidget(cfg)

    if cfg.type == "clock":
        return AnalogClockWidget(cfg)

    if cfg.type == "network":
        return NetworkWidget(cfg)

    if cfg.type == "calendar":
        return CalendarWidget(cfg)

    if cfg.type == "media":
        return MediaPlayerWidget(cfg)

    return SystemWidget(cfg)

class WidgetEditor(QDialog):
    def __init__(self, widget: BaseWidget, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.setWindowTitle("ウィジェット編集")
        self.resize(520, 420)

        layout = QFormLayout(self)

        self.title = QLineEdit(widget.cfg.title)
        self.color = QLineEdit(widget.cfg.color)
        self.bg = QLineEdit(widget.cfg.bg)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(widget.cfg.font_size)

        self.text = QTextEdit()
        self.text.setPlainText(widget.cfg.text)

        color_btn = QPushButton("色を選択")
        color_btn.clicked.connect(self.pick_color)

        bg_btn = QPushButton("背景色を選択")
        bg_btn.clicked.connect(self.pick_bg)

        btns = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("キャンセル")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)

        layout.addRow("タイトル", self.title)
        layout.addRow("アクセント色", self.color)
        layout.addRow("", color_btn)
        layout.addRow("背景色", self.bg)
        layout.addRow("", bg_btn)
        layout.addRow("フォントサイズ", self.font_size)
        layout.addRow("HTML / Text", self.text)
        layout.addRow(btns)

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.color.text()), self)
        if c.isValid():
            self.color.setText(c.name())

    def pick_bg(self):
        c = QColorDialog.getColor(QColor(self.bg.text()), self)
        if c.isValid():
            self.bg.setText(c.name())

    def apply(self):
        self.widget.cfg.title = self.title.text()
        self.widget.cfg.color = self.color.text()
        self.widget.cfg.bg = self.bg.text()
        self.widget.cfg.font_size = self.font_size.value()
        self.widget.cfg.text = self.text.toPlainText()

class LiteDeskStudio(QMainWindow):
    def __init__(self, canvas):
        super().__init__()
        if os.path.exists(os.path.join(os.getcwd(), 'icon.png')):
            self.setWindowIcon(QIcon(os.path.join(os.getcwd(), 'icon.png')))
        self.updating_ui = False
        self.applying_properties = False
        self.canvas = canvas
        self.updating_ui = False

        self.setWindowTitle("LiteDesk Studio")
        self.resize(960, 640)

        self.build_ui()
        self.apply_style()
        self.refresh_layer_list()
        self.load_selected_to_editor()

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh_runtime_status)
        self.ui_timer.start(500)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main = QHBoxLayout(root)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(12)

        main.addWidget(self.build_left_panel(), 0)
        main.addWidget(self.build_center_panel(), 1)
        main.addWidget(self.build_property_panel(), 0)

    def build_left_panel(self):
        scroll = QScrollArea()
        scroll.setObjectName("SideScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(250)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        panel = QWidget()
        panel.setObjectName("SidePanel")
        scroll.setWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("LiteDesk Studio")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel("ウィジェットを追加して、直感的に編集できます。")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("SubText")
        layout.addWidget(subtitle)

        add_label = QLabel("Add Widget")
        add_label.setObjectName("SectionTitle")
        layout.addWidget(add_label)

        self.btn_add_visualizer = QPushButton("音楽ビジュアライザー")
        self.btn_add_system = QPushButton("CPU / Memory / Disk")
        self.btn_add_volume = QPushButton("音量操作")
        self.btn_add_clock = QPushButton("アナログ時計")
        self.btn_add_network = QPushButton("通信状況")
        self.btn_add_calendar = QPushButton("カレンダー")
        self.btn_add_media = QPushButton("音楽プレイヤー操作")
        self.btn_add_html = QPushButton("HTML / CSS 風")

        self.btn_add_visualizer.clicked.connect(lambda: self.add_widget("visualizer"))
        self.btn_add_system.clicked.connect(lambda: self.add_widget("system"))
        self.btn_add_volume.clicked.connect(lambda: self.add_widget("volume"))
        self.btn_add_clock.clicked.connect(lambda: self.add_widget("clock"))
        self.btn_add_network.clicked.connect(lambda: self.add_widget("network"))
        self.btn_add_calendar.clicked.connect(lambda: self.add_widget("calendar"))
        self.btn_add_media.clicked.connect(lambda: self.add_widget("media"))
        self.btn_add_html.clicked.connect(lambda: self.add_widget("html"))

        for button in [
            self.btn_add_visualizer,
            self.btn_add_system,
            self.btn_add_volume,
            self.btn_add_clock,
            self.btn_add_calendar,
            self.btn_add_network,
            self.btn_add_media,
            self.btn_add_html,
        ]:
            button.setMinimumHeight(36)
            layout.addWidget(button)

        layer_label = QLabel("Layers")
        layer_label.setObjectName("SectionTitle")
        layout.addWidget(layer_label)

        self.layer_list = QListWidget()
        self.layer_list.currentRowChanged.connect(self.on_layer_selected)
        layout.addWidget(self.layer_list, 1)

        layer_buttons = QHBoxLayout()

        self.btn_layer_down = QPushButton("背面")
        self.btn_layer_up = QPushButton("前面")

        self.btn_layer_down.clicked.connect(self.move_backward)
        self.btn_layer_up.clicked.connect(self.move_forward)

        layer_buttons.addWidget(self.btn_layer_down)
        layer_buttons.addWidget(self.btn_layer_up)

        layout.addLayout(layer_buttons)

        return scroll

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
            else:
                self.canvas.show()
                self.canvas.update()

        super().changeEvent(event)

    def build_center_panel(self):
        panel = QWidget()
        panel.setObjectName("CenterPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()

        self.status_label = QLabel("Status")
        self.status_label.setObjectName("StatusText")
        top.addWidget(self.status_label, 1)

        self.edit_mode_check = QCheckBox("編集モード")
        self.edit_mode_check.setChecked(self.canvas.edit_mode)
        self.edit_mode_check.stateChanged.connect(self.on_edit_mode_changed)
        top.addWidget(self.edit_mode_check)

        layout.addLayout(top)

        help_box = QTextEdit()
        help_box.setReadOnly(True)
        help_box.setFixedHeight(120)
        help_box.setObjectName("HelpBox")
        help_box.setPlainText(
            "操作方法:\n"
            "・デスクトップ上のウィジェットはドラッグで移動できます。\n"
            "・Layers からウィジェットを選択できます。\n"
            "・右側の Properties で位置、サイズ、色、HTMLを編集できます。\n"
            "・Volume ウィジェット上でホイールすると音量を変更できます。\n"
            "・Eキーで編集モード切替、Deleteキーで削除できます。"
        )
        layout.addWidget(help_box)

        action_label = QLabel("Actions")
        action_label.setObjectName("SectionTitle")
        layout.addWidget(action_label)

        action_grid = QGridLayout()
        action_grid.setSpacing(8)

        self.btn_save = QPushButton("設定を保存")
        self.btn_reload = QPushButton("UIを再読み込み")
        self.btn_duplicate = QPushButton("複製")
        self.btn_delete = QPushButton("削除")
        self.btn_export = QPushButton("エクスポート")
        self.btn_import = QPushButton("インポート")
        self.btn_close_canvas = QPushButton("アプリ終了")

        self.btn_save.clicked.connect(self.save)
        self.btn_reload.clicked.connect(self.reload_ui)
        self.btn_duplicate.clicked.connect(self.duplicate)
        self.btn_delete.clicked.connect(self.delete)
        self.btn_export.clicked.connect(self.export_config)
        self.btn_import.clicked.connect(self.import_config)
        self.btn_close_canvas.clicked.connect(QApplication.quit)

        buttons = [
            self.btn_save,
            self.btn_reload,
            self.btn_duplicate,
            self.btn_delete,
            self.btn_export,
            self.btn_import,
            self.btn_close_canvas,
        ]

        for i, button in enumerate(buttons):
            button.setMinimumHeight(38)
            action_grid.addWidget(button, i // 2, i % 2)

        layout.addLayout(action_grid)
        layout.addStretch(1)

        performance_label = QLabel("Performance")
        performance_label.setObjectName("SectionTitle")
        layout.addWidget(performance_label)

        self.performance_text = QTextEdit()
        self.performance_text.setReadOnly(True)
        self.performance_text.setFixedHeight(120)
        self.performance_text.setObjectName("HelpBox")
        layout.addWidget(self.performance_text)

        return panel

    def build_property_panel(self):
        scroll = QScrollArea()
        scroll.setObjectName("PropertyScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(370)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        panel = QWidget()
        panel.setObjectName("PropertyPanel")

        scroll.setWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Properties")
        title.setObjectName("Title")
        layout.addWidget(title)

        self.selected_name = QLabel("No widget selected")
        self.selected_name.setObjectName("SubText")
        layout.addWidget(self.selected_name)

        form = QFormLayout()
        self.property_form = form
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setVerticalSpacing(8)

        self.prop_type = QLineEdit()
        self.prop_type.setReadOnly(True)

        self.prop_title = QLineEdit()

        self.prop_x = QSpinBox()
        self.prop_y = QSpinBox()
        self.prop_w = QSpinBox()
        self.prop_h = QSpinBox()

        for spin in [self.prop_x, self.prop_y, self.prop_w, self.prop_h]:
            spin.setRange(-10000, 10000)
            spin.valueChanged.connect(self.apply_properties_live)

        self.prop_w.setMinimum(40)
        self.prop_h.setMinimum(40)

        self.prop_title.textChanged.connect(self.apply_properties_live)

        self.prop_color = QLineEdit()
        self.prop_bg = QLineEdit()
        self.prop_bg_alpha = QSpinBox()
        self.prop_bg_alpha.setRange(0, 255)
        self.prop_bg_alpha.setValue(155)
        self.prop_bg_alpha.valueChanged.connect(self.apply_properties_live)
        self.prop_cpu_color = QLineEdit()
        self.prop_memory_color = QLineEdit()
        self.prop_disk_color = QLineEdit()

        self.prop_color.textChanged.connect(self.apply_properties_live)
        self.prop_bg.textChanged.connect(self.apply_properties_live)
        self.prop_cpu_color.textChanged.connect(self.apply_properties_live)
        self.prop_memory_color.textChanged.connect(self.apply_properties_live)
        self.prop_disk_color.textChanged.connect(self.apply_properties_live)

        self.btn_pick_color = QPushButton("アクセント色を選択")
        self.btn_pick_bg = QPushButton("背景色を選択")

        self.btn_pick_color.clicked.connect(self.pick_color)
        self.btn_pick_bg.clicked.connect(self.pick_bg)
        self.btn_pick_cpu_color = QPushButton("CPU色を選択")
        self.btn_pick_memory_color = QPushButton("Memory色を選択")
        self.btn_pick_disk_color = QPushButton("Disk色を選択")

        self.btn_pick_cpu_color.clicked.connect(self.pick_cpu_color)
        self.btn_pick_memory_color.clicked.connect(self.pick_memory_color)
        self.btn_pick_disk_color.clicked.connect(self.pick_disk_color)

        self.prop_font_size = QSpinBox()
        self.prop_font_size.setRange(8, 72)
        self.prop_font_size.valueChanged.connect(self.apply_properties_live)

        form.addRow("Type", self.prop_type)
        form.addRow("Title", self.prop_title)
        form.addRow("X", self.prop_x)
        form.addRow("Y", self.prop_y)
        form.addRow("Width", self.prop_w)
        form.addRow("Height", self.prop_h)
        form.addRow("Color", self.prop_color)
        form.addRow("", self.btn_pick_color)
        form.addRow("Background", self.prop_bg)
        form.addRow("", self.btn_pick_bg)
        form.addRow("透明度", self.prop_bg_alpha)
        form.addRow("CPU Color", self.prop_cpu_color)
        form.addRow("", self.btn_pick_cpu_color)

        form.addRow("Memory Color", self.prop_memory_color)
        form.addRow("", self.btn_pick_memory_color)

        form.addRow("Disk Color", self.prop_disk_color)
        form.addRow("", self.btn_pick_disk_color)
        self.system_only_property_widgets = [
            self.prop_cpu_color,
            self.btn_pick_cpu_color,
            self.prop_memory_color,
            self.btn_pick_memory_color,
            self.prop_disk_color,
            self.btn_pick_disk_color,
        ]
        form.addRow("Font Size", self.prop_font_size)

        layout.addLayout(form)

        html_label = QLabel("HTML / Text")
        html_label.setObjectName("SectionTitle")
        layout.addWidget(html_label)

        self.prop_text = QTextEdit()
        self.prop_text.setPlaceholderText(
            "<h2 style='color:#5BE7FF;'>Custom Widget</h2>\n"
            "<p style='color:white;'>ここにHTML風テキストを書けます。</p>"
        )
        self.prop_text.textChanged.connect(self.apply_properties_live)
        layout.addWidget(self.prop_text, 1)

        bottom = QHBoxLayout()

        self.btn_apply = QPushButton("反映")
        self.btn_reset_selection = QPushButton("選択解除")

        self.btn_apply.clicked.connect(lambda: self.apply_properties(save=True))
        self.btn_reset_selection.clicked.connect(self.clear_selection)

        bottom.addWidget(self.btn_apply)
        bottom.addWidget(self.btn_reset_selection)

        layout.addLayout(bottom)
        self.set_system_color_controls_visible(False)
        return scroll

    def add_widget(self, kind):
        self.canvas.add_widget(kind)
        self.refresh_layer_list()

        index = len(self.canvas.widgets) - 1
        self.layer_list.setCurrentRow(index)
        self.canvas.select_widget_by_index(index)
        self.load_selected_to_editor()

    def on_layer_selected(self, row):
        if self.updating_ui:
            return

        if row < 0:
            return

        self.canvas.select_widget_by_index(row)
        self.load_selected_to_editor()

    def set_system_color_controls_visible(self, visible: bool):
        widgets = getattr(self, "system_only_property_widgets", [])

        for widget in widgets:
            widget.setVisible(visible)

            try:
                label = self.property_form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)
            except Exception:
                pass

    def refresh_layer_list(self):
        self.updating_ui = True

        try:
            self.layer_list.blockSignals(True)

            self.layer_list.clear()

            for i, widget in enumerate(self.canvas.widgets):
                cfg = widget.cfg
                name = f"{i + 1}. {cfg.title} [{cfg.type}]"
                self.layer_list.addItem(name)

            index = self.canvas.get_selected_index()

            if index >= 0:
                self.layer_list.setCurrentRow(index)
            else:
                self.layer_list.clearSelection()

        finally:
            try:
                self.layer_list.blockSignals(False)
            except Exception:
                pass

            self.updating_ui = False

    def load_selected_to_editor(self):
        self.updating_ui = True

        controls = [
            getattr(self, "prop_title", None),
            getattr(self, "prop_x", None),
            getattr(self, "prop_y", None),
            getattr(self, "prop_w", None),
            getattr(self, "prop_h", None),
            getattr(self, "prop_color", None),
            getattr(self, "prop_bg", None),
            getattr(self, "prop_font_size", None),
            getattr(self, "prop_text", None),
            getattr(self, "prop_cpu_color", None),
            getattr(self, "prop_memory_color", None),
            getattr(self, "prop_disk_color", None),
            getattr(self, "prop_bg_alpha", None),
        ]

        controls = [c for c in controls if c is not None]

        for c in controls:
            c.blockSignals(True)

        try:
            widget = getattr(self.canvas, "selected", None)

            if not widget:
                self.selected_name.setText("No widget selected")
                self.prop_type.setText("")
                self.prop_title.setText("")
                self.prop_x.setValue(0)
                self.prop_y.setValue(0)
                self.prop_w.setValue(40)
                self.prop_h.setValue(40)
                self.prop_color.setText("")
                self.prop_bg.setText("")
                self.prop_font_size.setValue(14)
                self.prop_text.setPlainText("")
                self.set_property_enabled(False)
                self.prop_cpu_color.setText("")
                self.prop_memory_color.setText("")
                self.prop_disk_color.setText("")
                self.set_property_enabled(False)
                self.set_system_color_controls_visible(False)
                self.prop_bg_alpha.setValue(155)
                return

            cfg = widget.cfg

            self.set_property_enabled(True)
            self.set_system_color_controls_visible(cfg.type == "system")
            is_system_widget = cfg.type == "system"
            self.set_system_color_controls_visible(is_system_widget)
            self.selected_name.setText(f"Selected: {cfg.title}")
            self.prop_type.setText(cfg.type)
            self.prop_title.setText(cfg.title)
            self.prop_x.setValue(cfg.x)
            self.prop_y.setValue(cfg.y)
            self.prop_w.setValue(max(40, cfg.w))
            self.prop_h.setValue(max(40, cfg.h))
            self.prop_color.setText(cfg.color or "#5BE7FF")
            self.prop_bg.setText(cfg.bg or "#10141C")
            self.prop_bg_alpha.setValue(max(0, min(255, int(getattr(cfg, "bg_alpha", 155)))))
            self.prop_font_size.setValue(cfg.font_size)
            self.prop_text.setPlainText(cfg.text or "")
            if cfg.type == "system":
                self.prop_cpu_color.setText(getattr(cfg, "cpu_color", "#5BE7FF"))
                self.prop_memory_color.setText(getattr(cfg, "memory_color", "#B388FF"))
                self.prop_disk_color.setText(getattr(cfg, "disk_color", "#80FF9F"))
            else:
                self.prop_cpu_color.setText("")
                self.prop_memory_color.setText("")
                self.prop_disk_color.setText("")

        finally:
            for c in controls:
                c.blockSignals(False)

            self.updating_ui = False

    def set_property_enabled(self, enabled):
        widgets = [
            self.prop_title,
            self.prop_x,
            self.prop_y,
            self.prop_w,
            self.prop_h,
            self.prop_color,
            self.prop_bg,
            self.prop_bg_alpha,
            self.prop_font_size,
            self.prop_text,
            self.btn_pick_color,
            self.btn_pick_bg,
            self.btn_apply,
            self.btn_reset_selection,
            self.btn_duplicate,
            self.btn_delete,
            self.btn_layer_up,
            self.btn_layer_down,
            self.prop_cpu_color,
            self.prop_memory_color,
            self.prop_disk_color,
            self.btn_pick_cpu_color,
            self.btn_pick_memory_color,
            self.btn_pick_disk_color,
        ]

        for widget in widgets:
            widget.setEnabled(enabled)

    def apply_properties_live(self, *args):
        if self.updating_ui:
            return

        if self.applying_properties:
            return

        if not getattr(self.canvas, "selected", None):
            return

        if not hasattr(self, "prop_color"):
            return

        self.apply_properties(save=False)

    def apply_properties(self, *args, save=True):
        if getattr(self, "updating_ui", False):
            return

        if getattr(self, "applying_properties", False):
            return

        widget = getattr(self.canvas, "selected", None)

        if widget is None:
            return

        if not hasattr(widget, "cfg"):
            return

        required_attrs = [
            "prop_title",
            "prop_x",
            "prop_y",
            "prop_w",
            "prop_h",
            "prop_color",
            "prop_bg",
            "prop_bg_alpha",
            "prop_font_size",
            "prop_text",
            "prop_cpu_color",
            "prop_memory_color",
            "prop_disk_color",

        ]

        for attr in required_attrs:
            if not hasattr(self, attr):
                return

        self.applying_properties = True

        try:
            cfg = widget.cfg

            title = self.prop_title.text()
            x = self.prop_x.value()
            y = self.prop_y.value()
            w = max(40, self.prop_w.value())
            h = max(40, self.prop_h.value())

            color_text = self.prop_color.text().strip()
            bg_text = self.prop_bg.text().strip()

            if not color_text:
                color_text = "#5BE7FF"

            if not bg_text:
                bg_text = "#10141C"

            font_size = self.prop_font_size.value()
            text = self.prop_text.toPlainText()
            cfg.title = title
            cfg.x = x
            cfg.y = y
            cfg.w = w
            cfg.h = h
            cfg.color = color_text
            cfg.bg = bg_text
            cfg.bg_alpha = self.prop_bg_alpha.value()
            cfg.font_size = font_size
            cfg.text = text

            if cfg.type == "system":
                cpu_color_text = self.prop_cpu_color.text().strip() or "#5BE7FF"
                memory_color_text = self.prop_memory_color.text().strip() or "#B388FF"
                disk_color_text = self.prop_disk_color.text().strip() or "#80FF9F"

                cfg.cpu_color = cpu_color_text
                cfg.memory_color = memory_color_text
                cfg.disk_color = disk_color_text

            if isinstance(widget, HtmlWidget):
                widget.last_text = None

            self.canvas.update()

            if save:
                self.canvas.save_config()
                self.refresh_layer_list()

        finally:
            self.applying_properties = False

    def pick_cpu_color(self):
        current = QColor(self.prop_cpu_color.text() or "#5BE7FF")
        color = QColorDialog.getColor(current, self, "CPU色を選択")

        if color.isValid():
            self.prop_cpu_color.blockSignals(True)
            self.prop_cpu_color.setText(color.name())
            self.prop_cpu_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_memory_color(self):
        current = QColor(self.prop_memory_color.text() or "#B388FF")
        color = QColorDialog.getColor(current, self, "Memory色を選択")

        if color.isValid():
            self.prop_memory_color.blockSignals(True)
            self.prop_memory_color.setText(color.name())
            self.prop_memory_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_disk_color(self):
        current = QColor(self.prop_disk_color.text() or "#80FF9F")
        color = QColorDialog.getColor(current, self, "Disk色を選択")

        if color.isValid():
            self.prop_disk_color.blockSignals(True)
            self.prop_disk_color.setText(color.name())
            self.prop_disk_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_color(self):
        current = QColor(self.prop_color.text() or "#5BE7FF")
        color = QColorDialog.getColor(current, self, "アクセント色を選択")

        if color.isValid():
            self.prop_color.blockSignals(True)
            self.prop_color.setText(color.name())
            self.prop_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_bg(self):
        current = QColor(self.prop_bg.text() or "#10141C")
        color = QColorDialog.getColor(current, self, "背景色を選択")

        if color.isValid():
            self.prop_bg.blockSignals(True)
            self.prop_bg.setText(color.name())
            self.prop_bg.blockSignals(False)
            self.apply_properties(save=True)

    def duplicate(self):
        self.canvas.duplicate_selected_widget()
        self.refresh_layer_list()
        self.load_selected_to_editor()

    def delete(self):
        self.canvas.delete_selected_widget()
        self.refresh_layer_list()
        self.load_selected_to_editor()

    def move_forward(self):
        self.canvas.move_selected_forward()
        self.refresh_layer_list()
        self.load_selected_to_editor()

    def move_backward(self):
        self.canvas.move_selected_backward()
        self.refresh_layer_list()
        self.load_selected_to_editor()

    def clear_selection(self):
        for widget in self.canvas.widgets:
            widget.selected = False

        self.canvas.selected = None
        self.canvas.update()
        self.layer_list.clearSelection()
        self.load_selected_to_editor()

    def save(self):
        self.apply_properties(save=True)
        self.canvas.save_config()
        QMessageBox.information(self, "保存", "設定を保存しました。")

    def reload_ui(self):
        self.refresh_layer_list()
        self.load_selected_to_editor()
        self.refresh_runtime_status()

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "設定をエクスポート",
            "litedesk_config.json",
            "JSON Files (*.json)"
        )

        if not path:
            return

        try:
            self.canvas.export_config_to(path)
            QMessageBox.information(self, "エクスポート", "設定を書き出しました。")
        except Exception as e:
            QMessageBox.warning(self, "エラー", str(e))

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "設定をインポート",
            "",
            "JSON Files (*.json)"
        )

        if not path:
            return

        try:
            self.canvas.import_config_from(path)
            self.refresh_layer_list()
            self.load_selected_to_editor()
            QMessageBox.information(self, "インポート", "設定を読み込みました。")
        except Exception as e:
            QMessageBox.warning(self, "エラー", str(e))

    def on_edit_mode_changed(self, state=None):
        self.canvas.edit_mode = self.edit_mode_check.isChecked()

        if not self.canvas.edit_mode:
            for widget in self.canvas.widgets:
                widget.selected = False

            self.canvas.selected = None
            self.canvas.dragging = False

        self.canvas.update()
        self.refresh_layer_list()
        self.load_selected_to_editor()

    def refresh_runtime_status(self):
        audio_name = getattr(self.canvas.audio, "backend_name", "unknown")
        audio_mode = "fallback" if self.canvas.audio.use_fake else audio_name

        volume = "OK" if self.canvas.volume.available else "unavailable"
        theme = "Dark" if self.canvas.dark_mode else "Light"

        self.status_label.setText(
            f"Theme: {theme} | Audio: {audio_mode} | Volume API: {volume}"
        )

        self.performance_text.setPlainText(
            "軽量化状態:\n"
            f"・Widget count: {len(self.canvas.widgets)}\n"
            "・Renderer: QPainter direct rendering\n"
            "・HTML: QTextDocument based, no WebEngine\n"
            "・System monitor update: throttled\n"
            "・Audio analysis: background thread\n"
            "・Config save: JSON"
        )

    def apply_style(self):
        if WindowsTheme.is_dark_mode():
            self.setStyleSheet("""
                QMainWindow {
                    background: #0F1117;
                    color: #F5F7FA;
                }

                QWidget {
                    font-family: "Segoe UI";
                    color: #F5F7FA;
                    background: transparent;
                }

                QWidget#SidePanel,
                QWidget#CenterPanel,
                QWidget#PropertyPanel {
                    background: #151922;
                    border: 1px solid #252B38;
                    border-radius: 16px;
                }

                QLabel#Title {
                    font-size: 22px;
                    font-weight: 700;
                    color: #FFFFFF;
                }

                QLabel#SectionTitle {
                    font-size: 13px;
                    font-weight: 700;
                    color: #80FF9F;
                    margin-top: 6px;
                }

                QLabel#SubText,
                QLabel#StatusText {
                    color: #AAB2C0;
                    font-size: 12px;
                }

                QPushButton {
                    background: #232A38;
                    color: #FFFFFF;
                    border: 1px solid #343D50;
                    border-radius: 10px;
                    padding: 8px 10px;
                }

                QPushButton:hover {
                    background: #24382D;
                    border: 1px solid #3DDC84;
                }

                QPushButton:pressed {
                    background: #1C2230;
                }

                QPushButton:disabled {
                    background: #1A1D25;
                    color: #555C68;
                    border: 1px solid #242936;
                }

                QLineEdit,
                QTextEdit,
                QSpinBox {
                    background: #0F131C;
                    color: #FFFFFF;
                    border: 1px solid #30384A;
                    border-radius: 8px;
                    padding: 6px;
                    selection-background-color: #2FA866;
                }

                QTextEdit#HelpBox {
                    background: #10141C;
                    color: #BFC7D5;
                    border: 1px solid #252B38;
                    border-radius: 12px;
                }

                QListWidget {
                    background: #0F131C;
                    border: 1px solid #30384A;
                    border-radius: 10px;
                    padding: 4px;
                }

                QListWidget::item {
                    padding: 8px;
                    border-radius: 8px;
                }

                QListWidget::item:selected {
                    background: #2FA866;
                    color: white;
                }

                QListWidget::item:hover {
                    background: #222A38;
                }

                QCheckBox {
                    spacing: 8px;
                    color: #FFFFFF;
                }

                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QScrollArea#PropertyScrollArea {
                    background: transparent;
                    border: none;
                }
                
                QScrollArea#PropertyScrollArea > QWidget > QWidget {
                    background: #151922;
                    border: 1px solid #252B38;
                    border-radius: 16px;
                }
                
                QScrollBar:vertical {
                    background: transparent;
                    width: 10px;
                    margin: 8px 2px 8px 2px;
                }
                
                QScrollBar::handle:vertical {
                    background: #343D50;
                    border-radius: 5px;
                    min-height: 30px;
                }
                
                QScrollBar::handle:vertical:hover {
                    background: #51617D;
                }
                
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {
                    background: transparent;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background: #F3F5F9;
                    color: #111318;
                }

                QWidget {
                    font-family: "Segoe UI";
                    color: #111318;
                    background: transparent;
                }

                QWidget#SidePanel,
                QWidget#CenterPanel,
                QWidget#PropertyPanel {
                    background: #FFFFFF;
                    border: 1px solid #DDE2EA;
                    border-radius: 16px;
                }

                QLabel#Title {
                    font-size: 22px;
                    font-weight: 700;
                    color: #111318;
                }

                QLabel#SectionTitle {
                    font-size: 13px;
                    font-weight: 700;
                    color: #2FA866;
                    margin-top: 6px;
                }

                QLabel#SubText,
                QLabel#StatusText {
                    color: #5A6475;
                    font-size: 12px;
                }

                QPushButton {
                    background: #FFFFFF;
                    color: #111318;
                    border: 1px solid #CED5E0;
                    border-radius: 10px;
                    padding: 8px 10px;
                }

                QPushButton:hover {
                    background: #EFFFF4;
                    border: 1px solid #80FF9F;
                }

                QPushButton:pressed {
                    background: #D7FFE3;
                }

                QPushButton:disabled {
                    background: #F1F3F6;
                    color: #A0A8B5;
                    border: 1px solid #D8DDE5;
                }

                QLineEdit,
                QTextEdit,
                QSpinBox {
                    background: #FFFFFF;
                    color: #111318;
                    border: 1px solid #CCD3DD;
                    border-radius: 8px;
                    padding: 6px;
                    selection-background-color: #2FA866;
                }

                QTextEdit#HelpBox {
                    background: #F8FAFE;
                    color: #384252;
                    border: 1px solid #DDE2EA;
                    border-radius: 12px;
                }

                QListWidget {
                    background: #FFFFFF;
                    border: 1px solid #CCD3DD;
                    border-radius: 10px;
                    padding: 4px;
                }

                QListWidget::item {
                    padding: 8px;
                    border-radius: 8px;
                }

                QListWidget::item:selected {
                    background: #2FA866;
                    color: white;
                }

                QListWidget::item:hover {
                    background: #EFFFF4;
                }

                QCheckBox {
                    spacing: 8px;
                    color: #111318;
                }

                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QScrollArea#PropertyScrollArea {
                    background: transparent;
                    border: none;
                }
                
                QScrollArea#PropertyBar::handle:vertical {QScrollArea#PropertyScrollArea > QWidget > QWidget {
                    background: #C5CDDA;
                    border-radius: 5px;
                    min-height: 30px;
                }
                
                QScrollBar::handle:vertical:hover {
                    background: #9AA8BB;
                }
                
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {
                    background: transparent;
                }
                    background: #FFFFFF;
                    border: 1px solid #DDE2EA;
                    border-radius: 16px;
                }
                
                QScrollBar:vertical {
                    background: transparent;
                    width: 10px;
                    margin: 8px 2px 8px 2px;
                }
            """)
    def closeEvent(self, event):
        try:
            if hasattr(self, "ui_timer") and self.ui_timer is not None:
                self.ui_timer.stop()
        except Exception:
            pass

        try:
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.show()
                self.canvas.update()
        except Exception:
            pass

        event.accept()

class DesktopCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.volume_sliding = False
        self.setWindowTitle(APP_NAME)
        self.setMouseTracking(True)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |
            Qt.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.audio = AudioEngine()
        self.monitor = SystemMonitor()
        self.volume = VolumeController()
        self.media = MediaController()
        self.widgets: List[BaseWidget] = []
        self.selected: Optional[BaseWidget] = None
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.edit_mode = False
        self.last_right_click_time = 0.0
        self.last_right_click_widget = None
        self.right_double_click_interval = QApplication.doubleClickInterval() / 1000.0
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.on_frame)
        self.render_timer.start(1000 // 60)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.check_theme)
        self.theme_timer.start(1500)

        self.dark_mode = WindowsTheme.is_dark_mode()

        self.load_config()
        self.audio.start()

    def widget_at_pos(self, pos: QPoint):
        for widget in reversed(self.widgets):
            if widget.contains(pos):
                return widget
        return None

    def on_studio_destroyed(self):
        self.control_panel = None

    def open_studio(self):
        if hasattr(self, "control_panel") and self.control_panel is not None:
            try:
                if self.control_panel.isVisible():
                    self.control_panel.raise_()
                    self.control_panel.activateWindow()
                    return
            except RuntimeError:
                self.control_panel = None

        self.control_panel = LiteDeskStudio(self)
        self.control_panel.destroyed.connect(self.on_studio_destroyed)
        self.control_panel.show()
        self.control_panel.raise_()
        self.control_panel.activateWindow()

    def show_menu(self):
            self.open_studio()

    def notify_studio_selection_changed(self):
        if hasattr(self, "control_panel") and self.control_panel:
            try:
                self.control_panel.refresh_layer_list()
                self.control_panel.load_selected_to_editor()
            except Exception:
                pass

    def select_widget_by_index(self, index: int):
        if index < 0 or index >= len(self.widgets):
            return

        for w in self.widgets:
            w.selected = False

        self.selected = self.widgets[index]
        self.selected.selected = True
        self.update()

    def get_selected_index(self) -> int:
        if self.selected is None:
            return -1

        try:
            return self.widgets.index(self.selected)
        except ValueError:
            return -1

    def delete_selected_widget(self):
        if self.selected and self.selected in self.widgets:
            self.widgets.remove(self.selected)
            self.selected = None
            self.save_config()
            self.update()

    def duplicate_selected_widget(self):
        if not self.selected:
            return

        old = self.selected.cfg

        cfg = WidgetConfig(
            type=old.type,
            x=old.x + 24,
            y=old.y + 24,
            w=old.w,
            h=old.h,
            title=old.title + " Copy",
            color=old.color,
            bg=old.bg,
            text=old.text,
            font_size=old.font_size,
            bg_alpha=getattr(old, "bg_alpha", 155),
            cpu_color=getattr(old, "cpu_color", "#5BE7FF"),
            memory_color=getattr(old, "memory_color", "#B388FF"),
            disk_color=getattr(old, "disk_color", "#80FF9F"),
        )

        widget = create_widget(cfg)
        self.widgets.append(widget)

        for w in self.widgets:
            w.selected = False

        self.selected = widget
        widget.selected = True

        self.save_config()
        self.update()

    def move_selected_forward(self):
        if not self.selected:
            return

        index = self.widgets.index(self.selected)
        if index < len(self.widgets) - 1:
            self.widgets[index], self.widgets[index + 1] = self.widgets[index + 1], self.widgets[index]

        self.save_config()
        self.update()

    def move_selected_backward(self):
        if not self.selected:
            return

        index = self.widgets.index(self.selected)
        if index > 0:
            self.widgets[index], self.widgets[index - 1] = self.widgets[index - 1], self.widgets[index]

        self.save_config()
        self.update()

    def export_config_to(self, path: str):
        data = {
            "widgets": [asdict(w.to_config()) for w in self.widgets]
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_config_from(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.widgets = []
        self.selected = None

        for item in data.get("widgets", []):
            cfg = WidgetConfig(**item)
            self.widgets.append(create_widget(cfg))

        self.save_config()
        self.update()

    def check_theme(self):
        now_dark = WindowsTheme.is_dark_mode()
        if now_dark != self.dark_mode:
            self.dark_mode = now_dark
            self.update()

    def on_frame(self):
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        ctx = {
            "audio": self.audio,
            "monitor": self.monitor,
            "volume": self.volume,
            "media": self.media,
            "dark": self.dark_mode,
            "edit_mode": self.edit_mode,
        }

        for w in self.widgets:
            w.paint(p, ctx)

        if self.edit_mode:
            self.paint_edit_badge(p)

    def paint_edit_badge(self, p: QPainter):
        text = "EDIT MODE: Drag / Double Click Edit / Right Click Menu"
        p.setFont(QFont("Segoe UI", 9))
        metrics = p.fontMetrics()
        w = metrics.horizontalAdvance(text) + 24
        h = 28

        rect = QRectF(16, 16, w, h)
        p.setBrush(QColor(20, 24, 32, 180))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 14, 14)

        p.setPen(QColor(255, 255, 255, 230))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()

            clicked_widget = None

            for widget in reversed(self.widgets):
                if widget.contains(pos):
                    clicked_widget = widget
                    break

            for widget in self.widgets:
                widget.selected = False

            self.selected = None
            self.dragging = False
            self.volume_sliding = False

            if clicked_widget is not None:
                self.selected = clicked_widget
                clicked_widget.selected = True

                if isinstance(clicked_widget, MediaPlayerWidget):
                    button = clicked_widget.button_at(pos)

                    if button is not None:
                        if button == "prev":
                            self.media.previous_track()
                        elif button == "play":
                            self.media.play_pause()
                        elif button == "next":
                            self.media.next_track()
                        elif button == "stop":
                            self.media.stop()

                        self.update()
                        self.notify_studio_selection_changed()
                        return

                if isinstance(clicked_widget, VolumeWidget) and clicked_widget.hit_slider(pos):
                    value = clicked_widget.volume_from_pos(pos)
                    self.volume.set_volume(value)
                    self.volume_sliding = True
                else:
                    if self.edit_mode:
                        self.dragging = True
                        self.drag_offset = pos - QPoint(
                            clicked_widget.cfg.x,
                            clicked_widget.cfg.y
                        )

            self.update()
            self.notify_studio_selection_changed()
        elif event.button() == Qt.MouseButton.RightButton:
            return

    def mouseMoveEvent(self, event):
        pos = event
        pos = event.position().toPoint()

        if self.dragging and self.selected and self.edit_mode:
            self.selected.cfg.x = pos.x() - self.drag_offset.x()
            self.selected.cfg.y = pos.y() - self.drag_offset.y()
            self.update()

        if self.volume_sliding and isinstance(self.selected, VolumeWidget):
            value = self.selected.volume_from_pos(pos)
            self.volume.set_volume(value)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.volume_sliding = False
            self.save_config()
            self.notify_studio_selection_changed()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            pos = event.position().toPoint()
            clicked_widget = self.widget_at_pos(pos)
            if clicked_widget is None:
                self.last_right_click_time = 0.0
                self.last_right_click_widget = None
                return
            self.last_right_click_widget = clicked_widget
            for widget in self.widgets:
                widget.selected = False
            self.selected = clicked_widget
            clicked_widget.selected = True
            self.update()
            self.notify_studio_selection_changed()
            self.open_studio()

    def wheelEvent(self, event):
        pos = event.position().toPoint()

        target = None

        for widget in reversed(self.widgets):
            if widget.contains(pos):
                target = widget
                break

        if isinstance(target, VolumeWidget):
            delta = event.angleDelta().y()
            cur = self.volume.get_volume()

            if delta > 0:
                cur += 3
            else:
                cur -= 3

            self.volume.set_volume(cur)
            self.update()
            event.accept()
            return

        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.selected:
            self.widgets.remove(self.selected)
            self.selected = None
            self.save_config()
            self.update()

        elif event.key() == Qt.Key.Key_E:
            self.edit_mode = not self.edit_mode
            self.update()

        elif event.key() == Qt.Key.Key_Escape:
            self.selected = None
            for w in self.widgets:
                w.selected = False
            self.update()

    def show_menu(self):
        self.open_studio()

    def add_widget(self, kind: str):
        if kind == "visualizer":
            cfg = WidgetConfig(
                type="visualizer",
                x=120,
                y=120,
                w=520,
                h=180,
                title="",
                color="#5BE7FF",
                bg="#10141C",
            )
        elif kind == "system":
            cfg = WidgetConfig(
                type="system",
                x=160,
                y=340,
                w=320,
                h=150,
                title="",
                color="#80FF9F",
                bg="#10141C",
            )
        elif kind == "volume":
            cfg = WidgetConfig(
                type="volume",
                x=520,
                y=340,
                w=240,
                h=150,
                title="",
                color="#B388FF",
                bg="#10141C",
            )
        elif kind == "clock":
            cfg = WidgetConfig(
                type="clock",
                x=820,
                y=120,
                w=240,
                h=240,
                title="",
                color="#FFCC66",
                bg="#10141C",
            )
        elif kind == "network":
            cfg = WidgetConfig(
                type="network",
                x=820,
                y=390,
                w=320,
                h=150,
                title="",
                color="#5BE7FF",
                bg="#10141C",
            )
        elif kind == "media":
            cfg = WidgetConfig(
                type="media",
                x=1180,
                y=450,
                w=320,
                h=160,
                title="",
                color="#5BE7FF",
                bg="#10141C",
            )
        elif kind == "calendar":
            cfg = WidgetConfig(
                type="calendar",
                x=1180,
                y=120,
                w=300,
                h=300,
                title="",
                color="#80FF9F",
                bg="#10141C",
            )
        else:
            cfg = WidgetConfig(
                type="html",
                x=220,
                y=520,
                w=360,
                h=180,
                title="",
                color="#5BE7FF",
                bg="#10141C",
                text="""
                <h2 style="color:#5BE7FF;">Custom HTML</h2>
                <p style="color:white;">軽量な HTML/CSS 風ウィジェットです。</p>
                <p style="color:#B388FF;">QTextDocument ベースなので WebView より軽量です。</p>
                """,
            )

        self.widgets.append(create_widget(cfg))
        self.save_config()
        self.update()

    def save_config(self):
        data = {
            "widgets": [asdict(w.to_config()) for w in self.widgets]
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            self.widgets = [
                create_widget(WidgetConfig(
                    type="visualizer",
                    x=120,
                    y=120,
                    w=560,
                    h=190,
                    title="音楽Spectrum",
                    color="#5BE7FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="clock",
                    x=820,
                    y=120,
                    w=240,
                    h=240,
                    title="時計",
                    color="#FFCC66",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="network",
                    x=820,
                    y=390,
                    w=320,
                    h=150,
                    title="通信",
                    color="#5BE7FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="system",
                    x=120,
                    y=340,
                    w=340,
                    h=150,
                    title="システム",
                    color="#80FF9F",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="volume",
                    x=500,
                    y=340,
                    w=250,
                    h=150,
                    title="音量",
                    color="#B388FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="media",
                    x=1180,
                    y=450,
                    w=320,
                    h=160,
                    title="メディアコントローラー",
                    color="#5BE7FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="html",
                    x=120,
                    y=520,
                    w=460,
                    h=180,
                    title="HTML/CSS",
                    color="#5BE7FF",
                    bg="#10141C",
                    text="""
                    <h2 style="color:#5BE7FF;">LiteDeskEngine</h2>
                    <p style="color:white;">右クリックでパネルを開けます。</p>
                    <p style="color:#80FF9F;">E キーで編集モード切替 / Delete で削除。</p>
                    """,
                )),
            ]
            self.save_config()
            return

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.widgets = []
            for item in data.get("widgets", []):
                cfg = WidgetConfig(**item)
                self.widgets.append(create_widget(cfg))

        except Exception:
            self.widgets = []

    def closeEvent(self, event):
        try:
            self.audio.stop()
        except:
            pass
        try:
            self.volume.stop()
        except Exception:
            pass
        self.save_config()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    canvas = DesktopCanvas()
    canvas.show()

    hwnd = int(canvas.winId())
    WindowsTheme.apply_immersive_dark_titlebar(hwnd, WindowsTheme.is_dark_mode())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()