# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio
import concurrent.futures
import calendar as py_calendar
import ctypes
import ctypes.wintypes
import json
import math
import random
import os
import shutil
import queue
import sys
import threading
import time
import urllib.parse
import urllib.request
import warnings
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path

import numpy as np
import psutil
import soundcard as sc
from PySide6.QtCore import (QFileInfo,
    QObject,
    Signal,
    Slot,
    Qt,
    QRectF,
    QPoint,
    QTimer,
    QThread,
    QEvent,
    QUrl,
    QPointF,
    QRect,
    QCoreApplication,
    QTranslator,
    QAbstractNativeEventFilter,
    QLocale,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QFont,
    QPen,
    QIcon,
    QBrush,
    QRadialGradient,
    QLinearGradient,
    QTextDocument,
    QPainterPath,
    QImage,
    QPixmap,
    QRegion,
    QSurfaceFormat,
    QOpenGLContext,
    QOffscreenSurface,
    QFontMetrics,
    QDesktopServices,
)
from PySide6.QtWidgets import (QStyle, QFileIconProvider,
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QColorDialog,
    QFileDialog,
    QSpinBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QListWidget,
    QCheckBox,
    QGridLayout,
    QScrollArea,
    QDoubleSpinBox,
    QComboBox,
    QTabWidget,
    QGroupBox,
)
try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except:
    QOpenGLWidget = None
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from litedesktopstudio.core import *


class DummyVolumeController:
    def __init__(self):
        self.available = False
        self._volume = 50
        self._mute = False

    def get_volume(self):
        return int(self._volume)

    def set_volume(self, value):
        self._volume = max(0, min(100, int(value)))

    def get_mute(self):
        return bool(self._mute)

    def set_mute(self, value):
        self._mute = bool(value)

    def toggle_mute(self):
        self._mute = not self._mute

    def stop(self):
        pass


class DummyMediaController:
    def __init__(self):
        self.available = False

    def play_pause(self):
        pass

    def next_track(self):
        pass

    def previous_track(self):
        pass

    def stop(self):
        pass


class NullMediaMetadataEngine:
    def __init__(self, error="Media metadata is unavailable on this platform"):
        self.available = False
        self.error = error

    def start(self):
        pass

    def stop(self):
        pass

    def force_refresh(self):
        pass

    def snapshot(self):
        return {
            "available": False,
            "error": self.error,
            "title": "",
            "artist": "",
            "album": "",
            "app_id": "",
            "playback_status": "Unavailable",
            "thumbnail_bytes": b"",
            "updated_at": "",
        }


def create_runtime_controllers(canvas):
    canvas.audio = AudioEngine()
    canvas.monitor = SystemMonitor()

    if is_windows():
        try:
            canvas.volume = VolumeController()
        except:
            canvas.volume = DummyVolumeController()

        try:
            canvas.media = MediaController()
        except:
            canvas.media = DummyMediaController()

        try:
            canvas.media_meta = MediaMetadataEngine()
            canvas.media_meta.start()
        except Exception as e:
            canvas.media_meta = NullMediaMetadataEngine(repr(e))
    else:
        canvas.volume = DummyVolumeController()
        canvas.media = DummyMediaController()
        canvas.media_meta = NullMediaMetadataEngine(
            "Media metadata is available only on Windows with winsdk/winrt"
        )


def hide_js_views_if_present(canvas):
    try:
        if hasattr(canvas, "js_html_views"):
            canvas.js_html_views.set_visible(False)
    except:
        pass


def show_js_views_if_present(canvas):
    try:
        if hasattr(canvas, "js_html_views"):
            canvas.js_html_views.set_visible(True)
    except:
        pass


def build_safe_ctx(canvas):
    return {
        "audio": getattr(canvas, "audio", None),
        "monitor": getattr(canvas, "monitor", None),
        "volume": getattr(canvas, "volume", DummyVolumeController()),
        "media": getattr(canvas, "media", DummyMediaController()),
        "media_meta": getattr(canvas, "media_meta", NullMediaMetadataEngine()),
        "weather": getattr(canvas, "weather", None),
        "dark": getattr(canvas, "dark_mode", False),
        "edit_mode": getattr(canvas, "edit_mode", True),
    }


def stop_runtime_controllers(canvas):
    try:
        if hasattr(canvas, "audio") and canvas.audio is not None:
            canvas.audio.stop()
    except:
        pass

    try:
        if hasattr(canvas, "volume") and canvas.volume is not None:
            canvas.volume.stop()
    except:
        pass

    try:
        if hasattr(canvas, "media_meta") and canvas.media_meta is not None:
            canvas.media_meta.stop()
    except:
        pass

    try:
        if hasattr(canvas, "weather") and canvas.weather is not None:
            canvas.weather.stop()
    except:
        pass

    try:
        if hasattr(canvas, "js_html_views") and canvas.js_html_views is not None:
            canvas.js_html_views.clear()
    except:
        pass


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
        except:
            return False

    @staticmethod
    def apply_immersive_dark_titlebar(hwnd: int, enable: bool):
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1 if enable else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except:
            pass


class VolumeController:
    def __init__(self):
        self.available = False
        self._volume_cache = 50
        self._mute_cache = False
        self._running = True
        self._cmd_queue = queue.Queue()
        self._lock = threading.Lock()
        thread = Thread()
        thread.set_func(self._worker)
        thread.start()
        THREADS.append(thread)

    def _worker(self):
        endpoint = None
        need_uninit = False
        try:
            import sys
            
            
            sys.coinit_flags = 0x2
            import comtypes
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            try:
                comtypes.CoInitializeEx(0x2)
                need_uninit = True
            except OSError as e:
                
                
                if getattr(e, "winerror", None) == -2147417850:
                    need_uninit = False
                else:
                    raise
            except:
                need_uninit = False

            device = AudioUtilities.GetSpeakers()

            
            endpoint = getattr(device, "EndpointVolume", None)

            
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
            except:
                device_name = "Speakers"

            with self._lock:
                self.available = True
                self._volume_cache = int(endpoint.GetMasterVolumeLevelScalar() * 100)
                self._mute_cache = bool(endpoint.GetMute())

            

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

                    except:
                        pass

                    last_poll = now

        except Exception as e:
            print("[VolumeController] pycaw unavailable:", repr(e))

            with self._lock:
                self.available = False
        finally:
            try:
                endpoint = None
            except:
                pass

            try:
                if need_uninit:
                    comtypes.CoUninitialize()
            except:
                pass

            try:
                if "need_uninit" in locals() and need_uninit:
                    comtypes.CoUninitialize()
            except:
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
        except:
            pass


class AudioEngine:
    def __init__(self):
        self.bars = 52
        self.spectrum = np.zeros(self.bars, dtype=np.float32)
        self.running = False
        self.lock = threading.Lock()
        self.use_fake = False
        self.backend_name = "soundcard"
        self._thread = Thread()

    def start(self):
        self.running = True
        self._thread.set_func(self._run)
        self._thread.start()

    def stop(self):
        self.running = False
        self._thread.kill()

    def get_spectrum(self) -> np.ndarray:
        with self.lock:
            return self.spectrum.copy()

    def get_audio_snapshot(self) -> dict:
        """Return a normalized audio snapshot for visualizers and JSHTML widgets.

        The audio capture thread owns the soundcard recorder. Consumers should read
        this cached snapshot instead of opening another recorder, so multiple
        widgets do not compete for the same audio device.
        """
        try:
            spectrum = self.get_spectrum()
            arr = np.asarray(spectrum, dtype=np.float32)

            if arr.size <= 0:
                return {
                    "ok": True,
                    "bands": [],
                    "bandCount": 0,
                    "level": 0.0,
                    "peak": 0.0,
                    "rms": 0.0,
                    "backend": self.backend_name,
                    "useFake": bool(self.use_fake),
                    "running": bool(self.running),
                    "timestamp": time.time(),
                }

            arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
            arr = np.clip(arr, 0.0, 1.0)

            return {
                "ok": True,
                "bands": arr.tolist(),
                "bandCount": int(arr.size),
                "level": float(np.mean(arr)),
                "peak": float(np.max(arr)),
                "rms": float(np.sqrt(np.mean(arr * arr))),
                "backend": self.backend_name,
                "useFake": bool(self.use_fake),
                "running": bool(self.running),
                "timestamp": time.time(),
            }
        except Exception as e:
            return {
                "ok": False,
                "bands": [],
                "bandCount": 0,
                "level": 0.0,
                "peak": 0.0,
                "rms": 0.0,
                "backend": self.backend_name,
                "useFake": bool(self.use_fake),
                "running": bool(self.running),
                "timestamp": time.time(),
                "error": repr(e),
            }

    def _run(self):
        try:
            self._run_soundcard_loopback()
        except:
            self.use_fake = True
            self.backend_name = "fallback"
            self._run_fake()

    def _find_loopback_microphone(self):
        mics = sc.all_microphones(include_loopback=True)

        
        loopbacks = [m for m in mics if getattr(m, "isloopback", False)]

        if loopbacks:
            
            try:
                default_speaker = sc.default_speaker()
                speaker_name = default_speaker.name.lower()

                for mic in loopbacks:
                    if speaker_name in mic.name.lower() or mic.name.lower() in speaker_name:
                        return mic
            except:
                pass

            
            return loopbacks[0]

        
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
                    time.sleep(0.00005)
                    continue

                
                if data.ndim == 2:
                    mono = data.mean(axis=1)
                else:
                    mono = data

                
                mono = mono - np.mean(mono)

                
                window = np.hanning(len(mono))
                mono = mono * window

                spec = np.abs(np.fft.rfft(mono))

                
                spec = spec[:len(spec) // 2]

                if spec.size <= 0:
                    continue

                
                idx = np.geomspace(1, spec.size - 1, self.bars).astype(int)
                bars = spec[idx]

                
                bars = np.log1p(bars)

                maxv = np.max(bars)
                if maxv > 0:
                    bars = bars / maxv

                
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


class WeatherEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = True
        self._thread = Thread()

        self.location = ""
        self.temperature = "--"
        self.feels_like = "--"
        self.description = "Loading..."
        self.humidity = "--"
        self.wind_kmph = "--"
        self.area = ""
        self.country = ""
        self.updated_at = ""
        self.error = ""
        self.icon = "☁"
        self.weather_code = ""

        self.forecast = []

        self.refresh_interval = 600.0
        self._last_fetch = 0.0
        self._force_fetch = True
        self.last_fetch_date = ""

    def start(self):
        if self._thread.running() is not None:
            return

        self._running = True
        self._thread.set_func(self._worker)
        self._thread.start()

    def stop(self):
        self._running = False
        self._thread.kill()

    def set_location(self, location: str):
        location = (location or "").strip()

        with self._lock:
            if location != self.location:
                self.location = location
                
                self._force_fetch = True
                self._last_fetch = 0.0
                self.temperature = "--"
                self.feels_like = "--"
                self.description = "Loading..."
                self.humidity = "--"
                self.wind_kmph = "--"
                self.area = ""
                self.country = ""
                self.updated_at = ""
                self.error = ""
                self.icon = "☁"
                self.weather_code = ""
                self.forecast = []

    def set_refresh_interval(self, seconds: float):
        
        try:
            seconds = float(seconds)
        except:
            seconds = 600.0
        seconds = max(60.0, min(86400.0, seconds))
        with self._lock:
            self.refresh_interval = seconds
            self._force_fetch = True

    def snapshot(self):
        with self._lock:
            return {
                "location": self.location,
                "temperature": self.temperature,
                "feels_like": self.feels_like,
                "description": self.description,
                "humidity": self.humidity,
                "wind_kmph": self.wind_kmph,
                "area": self.area,
                "country": self.country,
                "updated_at": self.updated_at,
                "error": self.error,
                "icon": self.icon,
                "weather_code": self.weather_code,
                "forecast": list(self.forecast),
            }

    def _worker(self):
        
        while self._running:
            now = time.time()
            today = time.strftime("%Y-%m-%d")
            should_fetch = False

            with self._lock:
                interval = max(60.0, float(getattr(self, "refresh_interval", 600.0)))
                if self._force_fetch:
                    should_fetch = True
                elif now - self._last_fetch >= interval:
                    should_fetch = True

                location = self.location

            if should_fetch:
                self._fetch_weather(location)

                with self._lock:
                    self._last_fetch = time.time()
                    self.last_fetch_date = today
                    self._force_fetch = False

            
            time.sleep(1.0)

    def _build_url(self, location: str):
        query = urllib.parse.urlencode({
            "format": "j1",
            "lang": "ja"
        })

        if location:
            encoded = urllib.parse.quote(location)
            return f"https://wttr.in/{encoded}?{query}"
        else:
            return f"https://wttr.in/?{query}"

    def _translate_weather_desc(self, text: str):
        text = text or "--"

        table = {
            "Sunny": lds_tr("晴れ"),
            "Clear": lds_tr("快晴"),
            "Partly cloudy": lds_tr("一部曇り"),
            "Cloudy": lds_tr("曇り"),
            "Overcast": lds_tr("厚い曇り"),
            "Mist": lds_tr("霧"),
            "Fog": lds_tr("霧"),
            "Patchy rain nearby": lds_tr("所により雨"),
            "Light rain": lds_tr("小雨"),
            "Moderate rain": lds_tr("雨"),
            "Heavy rain": lds_tr("強い雨"),
            "Light drizzle": lds_tr("霧雨"),
            "Patchy light drizzle": lds_tr("所により霧雨"),
            "Patchy light rain": lds_tr("所により小雨"),
            "Light rain shower": lds_tr("弱いにわか雨"),
            "Moderate or heavy rain shower": lds_tr("強いにわか雨"),
            "Thunderstorm": lds_tr("雷雨"),
            "Patchy snow nearby": lds_tr("所により雪"),
            "Light snow": lds_tr("小雪"),
            "Moderate snow": lds_tr("雪"),
            "Heavy snow": lds_tr("大雪"),
            "Blizzard": lds_tr("吹雪"),
        }

        return table.get(text, text)

    def _weather_icon(self, code=None, desc=""):
        code_text = str(code or "").strip()
        desc_text = (desc or "").lower()

        code_icon_map = {
            "113": "☀",   # Sunny / Clear
            "116": "⛅",   # Partly cloudy
            "119": "☁",   # Cloudy
            "122": "☁",   # Overcast
            "143": "🌫",  # Mist
            "176": "🌦",  # Patchy rain nearby
            "179": "🌨",  # Patchy snow nearby
            "182": "🌨",  # Patchy sleet nearby
            "185": "🌧",  # Patchy freezing drizzle nearby
            "200": "⛈",  # Thundery outbreaks nearby
            "227": "🌨",  # Blowing snow
            "230": "❄",   # Blizzard
            "248": "🌫",  # Fog
            "260": "🌫",  # Freezing fog
            "263": "🌦",  # Patchy light drizzle
            "266": "🌧",  # Light drizzle
            "281": "🌧",  # Freezing drizzle
            "284": "🌧",  # Heavy freezing drizzle
            "293": "🌦",  # Patchy light rain
            "296": "🌧",  # Light rain
            "299": "🌧",  # Moderate rain at times
            "302": "🌧",  # Moderate rain
            "305": "🌧",  # Heavy rain at times
            "308": "🌧",  # Heavy rain
            "311": "🌧",  # Light freezing rain
            "314": "🌧",  # Moderate or heavy freezing rain
            "317": "🌨",  # Light sleet
            "320": "🌨",  # Moderate or heavy sleet
            "323": "🌨",  # Patchy light snow
            "326": "🌨",  # Light snow
            "329": "❄",   # Patchy moderate snow
            "332": "❄",   # Moderate snow
            "335": "❄",   # Patchy heavy snow
            "338": "❄",   # Heavy snow
            "350": "🌨",  # Ice pellets
            "353": "🌦",  # Light rain shower
            "356": "🌧",  # Moderate or heavy rain shower
            "359": "🌧",  # Torrential rain shower
            "362": "🌨",  # Light sleet showers
            "365": "🌨",  # Moderate or heavy sleet showers
            "368": "🌨",  # Light snow showers
            "371": "❄",   # Moderate or heavy snow showers
            "374": "🌨",  # Light showers of ice pellets
            "377": "🌨",  # Moderate or heavy showers of ice pellets
            "386": "⛈",  # Patchy light rain with thunder
            "389": "⛈",  # Moderate or heavy rain with thunder
            "392": "⛈",  # Patchy light snow with thunder
            "395": "⛈",  # Moderate or heavy snow with thunder
        }

        if code_text in code_icon_map:
            return code_icon_map[code_text]

        if "thunder" in desc_text or "雷" in desc_text:
            return "⛈"
        if "snow" in desc_text or "雪" in desc_text:
            return "❄"
        if "rain" in desc_text or "drizzle" in desc_text or "雨" in desc_text:
            return "🌧"
        if "fog" in desc_text or "mist" in desc_text or "霧" in desc_text:
            return "🌫"
        if "sunny" in desc_text or "clear" in desc_text or "晴" in desc_text or "快晴" in desc_text:
            return "☀"
        if "partly" in desc_text or "一部" in desc_text:
            return "⛅"
        if "cloud" in desc_text or "曇" in desc_text:
            return "☁"

        return "☁"

    def _fetch_weather(self, location: str):
        url = self._build_url(location)

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "WeatherWidget"
                }
            )

            with urllib.request.urlopen(req, timeout=8) as response:
                raw = response.read().decode(
                    "utf-8",
                    errors="replace"
                )

            data = json.loads(raw)

            current_list = data.get("current_condition", [])
            current = current_list[0] if current_list else {}

            nearest_area = data.get("nearest_area", [])
            area_data = nearest_area[0] if nearest_area else {}

            weather_list = data.get("weather", [])

            temp = current.get("temp_C", "--")
            feels = current.get("FeelsLikeC", "--")
            humidity = current.get("humidity", "--")
            wind = current.get("windspeedKmph", "--")
            weather_code = current.get("weatherCode", "")

            desc = "--"
            desc_list = current.get("weatherDesc", [])

            if desc_list:
                desc = desc_list[0].get("value", "--")

            icon = self._weather_icon(weather_code, desc)
            desc = self._translate_weather_desc(desc)

            area = ""
            area_names = area_data.get("areaName", [])

            if area_names:
                area = area_names[0].get("value", "")

            country = ""
            countries = area_data.get("country", [])

            if countries:
                country = countries[0].get("value", "")

            forecast = []

            for day_data in weather_list[:3]:
                date = day_data.get("date", "")
                max_temp = day_data.get("maxtempC", "--")
                min_temp = day_data.get("mintempC", "--")

                day_desc = ""
                day_code = ""
                hourly = day_data.get("hourly", [])

                if hourly:
                    mid = hourly[len(hourly) // 2]
                    weather_desc = mid.get("weatherDesc", [])
                    day_code = mid.get("weatherCode", "")

                    if weather_desc:
                        day_desc = weather_desc[0].get("value", "")

                day_icon = self._weather_icon(day_code, day_desc)
                day_desc = self._translate_weather_desc(day_desc)

                forecast.append({
                    "date": date,
                    "max": max_temp,
                    "min": min_temp,
                    "desc": day_desc,
                    "icon": day_icon,
                    "code": day_code,
                })

            with self._lock:
                self.temperature = temp
                self.feels_like = feels
                self.description = desc
                self.humidity = humidity
                self.wind_kmph = wind
                self.area = area
                self.country = country
                self.updated_at = time.strftime("%H:%M:%S")
                self.error = ""
                self.icon = icon
                self.weather_code = weather_code
                self.forecast = forecast

        except Exception as e:
            with self._lock:
                self.error = str(e)
                self.updated_at = time.strftime("%H:%M:%S")


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
        except:
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
            except:
                self.cpu = 0.0

            try:
                self.memory = psutil.virtual_memory().percent
            except:
                self.memory = 0.0

            try:
                self.disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
            except:
                self.disk = 0.0
            if now - self.last_net_update >= 1.0:
                self.update_network(now)
            self.last_update = now


class MediaMetadataEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = Thread()
        self._running = False

        self.available = False
        self.error = ""
        self.title = ""
        self.artist = ""
        self.album = ""
        self.app_id = ""
        self.playback_status = ""
        self.thumbnail_bytes = b""
        self.updated_at = ""

        self.poll_interval = 2.0
        self._force_fetch = True

    def start(self):
        if self._thread.running() is not None:
            return

        self._running = True
        self._thread.set_func(self._worker)
        self._thread.start()
    def stop(self):
        self._running = False
        self._thread.kill()

    def force_refresh(self):
        with self._lock:
            self._force_fetch = True

    def snapshot(self):
        with self._lock:
            return {
                "available": self.available,
                "error": self.error,
                "title": self.title,
                "artist": self.artist,
                "album": self.album,
                "app_id": self.app_id,
                "playback_status": self.playback_status,
                "thumbnail_bytes": self.thumbnail_bytes,
                "updated_at": self.updated_at,
            }

    def _get_media_manager_class(self):
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )
            return MediaManager, ""
        except Exception as e1:
            winsdk_error = repr(e1)

        error = (
            "Media metadata API is unavailable. "
            "Install winsdk or winrt media control package. "
            f"winsdk error: {winsdk_error}"
        )

        return None, error

    def _worker(self):
        while self._running:
            with self._lock:
                self._force_fetch = False

            self._run_async_fetch_once()
            time.sleep(self.poll_interval)

    def _run_async_fetch_once(self):
        try:
            asyncio.run(self._fetch_once())
        except Exception as e:
            with self._lock:
                self.available = False
                self.error = repr(e)
                self.updated_at = time.strftime("%H:%M:%S")

    async def _fetch_once(self):
        try:

            MediaManager, import_error = self._get_media_manager_class()

            if MediaManager is None:
                with self._lock:
                    self.available = False
                    self.error = import_error
                    self.title = ""
                    self.artist = ""
                    self.album = ""
                    self.app_id = ""
                    self.playback_status = "Unavailable"
                    self.thumbnail_bytes = b""
                    self.updated_at = time.strftime("%H:%M:%S")
                return

            manager = await MediaManager.request_async()
            session = manager.get_current_session()

            if session is None:
                with self._lock:
                    self.available = True
                    self.error = ""
                    self.title = ""
                    self.artist = ""
                    self.album = ""
                    self.app_id = ""
                    self.playback_status = "No session"
                    self.thumbnail_bytes = b""
                    self.updated_at = time.strftime("%H:%M:%S")
                return

            props = await session.try_get_media_properties_async()

            title = getattr(props, "title", "") or ""
            artist = getattr(props, "artist", "") or ""
            album = getattr(props, "album_title", "") or ""
            thumbnail = getattr(props, "thumbnail", None)
            app_id = getattr(session, "source_app_user_model_id", "") or ""

            playback_status = ""
            try:
                info = session.get_playback_info()
                status = getattr(info, "playback_status", "")
                playback_status = str(status).split(".")[-1]
            except:
                playback_status = ""

            thumb_bytes = b""
            if thumbnail is not None:
                thumb_bytes = await self._read_thumbnail_bytes(thumbnail)

            with self._lock:
                self.available = True
                self.error = ""
                self.title = title
                self.artist = artist
                self.album = album
                self.app_id = app_id
                self.playback_status = playback_status
                self.thumbnail_bytes = thumb_bytes
                self.updated_at = time.strftime("%H:%M:%S")

        except Exception as e:
            with self._lock:
                self.available = False
                self.error = repr(e)
                self.updated_at = time.strftime("%H:%M:%S")

    async def _read_thumbnail_bytes(self, thumbnail_ref):
        try:
            stream = await thumbnail_ref.open_read_async()
            size = int(getattr(stream, "size", 0) or 0)

            if size <= 0:
                return b""

            try:
                from winsdk.windows.storage.streams import DataReader
            except:
                pass

            reader = DataReader(stream)
            await reader.load_async(size)

            data = bytearray(size)
            reader.read_bytes(data)

            try:
                reader.close()
            except:
                pass

            return bytes(data)

        except:
            return b""
