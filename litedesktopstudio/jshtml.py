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
from litedesktopstudio.widgets import *
from litedesktopstudio.effects import *
from litedesktopstudio.runtime import *


__htmls = """
</style>
</head>
<body>
<div class="card">
  <div class="title">JavaScript Widget</div>
  <p id="text">{lds}</p>
  <button onclick="document.getElementById('text').textContent = 'Clicked: ' + new Date().toLocaleTimeString();">
    Click me
  </button>
</div>
</body>
</html>
""".format(lds=lds_tr("この内容は WidgetConfig.text として config.json に保存されます。"))


JSHTML_WIDGETS_DIR = Path(CONFIG_PATH).with_name("LiteDesktopStudio_jshtml_widgets")


class JSHtmlPackageError(Exception):
    pass


def _jshtml_safe_identifier(value: str) -> str:
    value = str(value or "").strip()
    safe = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_"))
    return safe or str(uuid.uuid4())


def ensure_jshtml_widget_fields(cfg):
    if not getattr(cfg, "jshtml_mode", ""):
        cfg.jshtml_mode = "inline"
    if not getattr(cfg, "jshtml_entry", ""):
        cfg.jshtml_entry = "index.html"
    if not getattr(cfg, "jshtml_permissions_json", ""):
        cfg.jshtml_permissions_json = "{}"
    if not getattr(cfg, "jshtml_instance_id", ""):
        cfg.jshtml_instance_id = str(uuid.uuid4())
    cfg.jshtml_instance_id = _jshtml_safe_identifier(cfg.jshtml_instance_id)
    return cfg


def get_jshtml_widget_dir(cfg) -> Path:
    ensure_jshtml_widget_fields(cfg)
    base_dir = JSHTML_WIDGETS_DIR.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    widget_dir = (base_dir / cfg.jshtml_instance_id).resolve()
    if base_dir != widget_dir and base_dir not in widget_dir.parents:
        raise JSHtmlPackageError("Invalid JSHTML widget directory")
    widget_dir.mkdir(parents=True, exist_ok=True)
    (widget_dir / "assets").mkdir(exist_ok=True)
    (widget_dir / "data").mkdir(exist_ok=True)
    return widget_dir


def _jshtml_safe_path(root: Path, relative_path: str) -> Optional[Path]:
    try:
        root = Path(root).resolve()
        rel = str(relative_path or "").replace("\\", "/").lstrip("/")
        if ":" in rel:
            return None
        target = (root / rel).resolve()
        if target == root or root in target.parents:
            return target
    except:
        pass
    return None


def _is_safe_zip_member_name(name: str) -> bool:
    if not name:
        return False
    normalized = str(name).replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        return False
    for part in normalized.split("/"):
        if part == "..":
            return False
    return True


def safe_extract_jshtml_widget_zip(zip_path: str, destination_dir: Path, max_total_size: int = 50 * 1024 * 1024, max_file_size: int = 20 * 1024 * 1024, max_file_count: int = 1000) -> None:
    zip_path = Path(zip_path).resolve()
    destination_dir = Path(destination_dir).resolve()
    if not zip_path.exists() or not zip_path.is_file():
        raise JSHtmlPackageError("ZIPファイルが存在しません。")
    destination_dir.mkdir(parents=True, exist_ok=True)
    total_size = 0
    with zipfile.ZipFile(zip_path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > max_file_count:
            raise JSHtmlPackageError("ZIP内のファイル数が多すぎます。")
        for info in infos:
            member = info.filename
            if not _is_safe_zip_member_name(member):
                raise JSHtmlPackageError(f"危険なパスが含まれています: {member}")
            if info.file_size > max_file_size:
                raise JSHtmlPackageError(f"ファイルサイズが大きすぎます: {member}")
            total_size += int(info.file_size or 0)
            if total_size > max_total_size:
                raise JSHtmlPackageError("ZIPの総展開サイズが大きすぎます。")
        for info in infos:
            member = info.filename.replace("\\", "/")
            target = (destination_dir / member).resolve()
            if destination_dir != target and destination_dir not in target.parents:
                raise JSHtmlPackageError(f"展開先が範囲外です: {member}")
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as dest:
                shutil.copyfileobj(source, dest)


def import_jshtml_widget_package_to_config(cfg, zip_path: str) -> Path:
    ensure_jshtml_widget_fields(cfg)
    widget_dir = get_jshtml_widget_dir(cfg)
    if widget_dir.exists():
        for child in list(widget_dir.iterdir()):
            if child.name == "data":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except:
                    pass
    safe_extract_jshtml_widget_zip(zip_path, widget_dir)

    manifest_path = widget_dir / "widget.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest, dict):
                entry = str(manifest.get("entry") or "index.html")
                if _jshtml_safe_path(widget_dir, entry) is not None:
                    cfg.jshtml_entry = entry
                cfg.jshtml_package_name = str(manifest.get("name") or manifest.get("id") or cfg.jshtml_package_name or "")
                cfg.jshtml_package_version = str(manifest.get("version") or cfg.jshtml_package_version or "")
                permissions = manifest.get("permissions")
                if isinstance(permissions, dict):
                    cfg.jshtml_permissions_json = json.dumps(permissions, ensure_ascii=False)
        except Exception as e:
            raise JSHtmlPackageError(f"widget.json を読み込めません: {e}")

    entry_path = _jshtml_safe_path(widget_dir, getattr(cfg, "jshtml_entry", "index.html"))
    if entry_path is None or not entry_path.exists() or not entry_path.is_file():
        fallback = widget_dir / "index.html"
        if fallback.exists() and fallback.is_file():
            cfg.jshtml_entry = "index.html"
            entry_path = fallback
        else:
            raise JSHtmlPackageError("index.html または widget.json の entry が見つかりません。")

    cfg.jshtml_mode = "package"
    return widget_dir


def _jshtml_api_bootstrap() -> str:
    return r"""<!-- LiteDesktopStudio JSHTML API bootstrap -->
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
(function () {
  if (window.__LDS_JSHTML_API_BOOTSTRAPPED__) return;
  window.__LDS_JSHTML_API_BOOTSTRAPPED__ = true;


  // LiteDesktopStudio realtime diagnostics / visibility guard.
  // Chromium may throttle background/hidden pages. Native QtWebEngine flags are
  // applied on the Python side; this JS block only exposes diagnostics and asks
  // animation loops to keep an eye on FPS without changing widget behavior.
  window.__LDS_JSHTML_REALTIME_GUARD__ = window.__LDS_JSHTML_REALTIME_GUARD__ || {
    createdAt: Date.now(),
    lastFrameAt: Date.now(),
    estimatedFps: 0,
    frameCount: 0
  };
  (function realtimeGuardLoop(now) {
    try {
      var guard = window.__LDS_JSHTML_REALTIME_GUARD__;
      guard.frameCount += 1;
      if (!guard.lastFpsAt) guard.lastFpsAt = now;
      if (now - guard.lastFpsAt >= 1000) {
        guard.estimatedFps = guard.frameCount;
        guard.frameCount = 0;
        guard.lastFpsAt = now;
      }
      guard.lastFrameAt = Date.now();
    } catch (e) {}
    try { window.requestAnimationFrame(realtimeGuardLoop); } catch (e) {}
  })(performance.now());


  function parseJson(text) {
    try { return JSON.parse(text); }
    catch (error) { return { ok: false, error: String(error), raw: text }; }
  }

  window.LDSReady = new Promise(function (resolve, reject) {
    function fail(message) { reject(new Error(message)); }
    if (typeof QWebChannel === "undefined") { fail("QWebChannel is not available"); return; }
    if (typeof qt === "undefined" || !qt.webChannelTransport) { fail("qt.webChannelTransport is not available"); return; }

    new QWebChannel(qt.webChannelTransport, function (channel) {
      var raw = channel.objects.LDSApi;
      if (!raw) { fail("LDSApi is not available"); return; }

      window.LDS = {
        ping: async function () { return parseJson(await raw.ping()); },
        getWidgetInfo: async function () { return parseJson(await raw.getWidgetInfo()); },
        getWidgetRect: async function () { return parseJson(await raw.getWidgetRect()); },
        getSystemInfo: async function () { return parseJson(await raw.getSystemInfo()); },
        readConfig: async function (key) { return parseJson(await raw.readConfig(String(key))); },
        writeConfig: async function (key, value) { return parseJson(await raw.writeConfig(String(key), JSON.stringify(value))); },
        openUrl: async function (url) { return parseJson(await raw.openUrl(String(url))); },
        getLocalAssetUrl: async function (path) { return parseJson(await raw.getLocalAssetUrl(String(path))); },
        listAssets: async function (path) { return parseJson(await raw.listAssets(String(path || "assets"))); },
        readTextFile: async function (path) { return parseJson(await raw.readTextFile(String(path))); },
        getAudioInfo: async function () { return parseJson(await raw.getAudioInfo()); },
        getAudioLevel: async function () { return parseJson(await raw.getAudioLevel()); },
        getAudioSpectrum: async function () { return parseJson(await raw.getAudioSpectrum()); }
      };

      window.System = window.System || {};
      window.System.Gadget = window.System.Gadget || {};
      window.System.Gadget.version = "LiteDesktopStudio-compat";
      window.System.Gadget.settings = window.System.Gadget.settings || {};
      window.System.Gadget.settings.read = async function (key) {
        var result = await window.LDS.readConfig(key);
        return result ? result.value : null;
      };
      window.System.Gadget.settings.write = async function (key, value) {
        return await window.LDS.writeConfig(key, value);
      };
      resolve(window.LDS);
    });
  });
})();
</script>
"""


def inject_jshtml_api_bootstrap(html: str) -> str:
    html = html or ""
    if "__LDS_JSHTML_API_BOOTSTRAPPED__" in html:
        return html
    bootstrap = _jshtml_api_bootstrap()
    lower = html.lower()
    head_pos = lower.find("</head>")
    if head_pos >= 0:
        return html[:head_pos] + bootstrap + html[head_pos:]
    body_pos = lower.find("<body")
    if body_pos >= 0:
        body_end = html.find(">", body_pos)
        if body_end >= 0:
            return html[:body_end + 1] + bootstrap + html[body_end + 1:]
    return bootstrap + html


def build_js_html_document(html: str) -> str:
    html = html or ""
    if "<html" in html.lower() or "<!doctype" in html.lower():
        return inject_jshtml_api_bootstrap(html)
    document = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: transparent;
    font-family: "Segoe UI", sans-serif;
    color: white;
}}
body {{
    box-sizing: border-box;
}}
</style>
</head>
<body>
{html}
</body>
</html>"""
    return inject_jshtml_api_bootstrap(document)


class JSHtmlWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


class JSHtmlWidgetApi(QObject):
    configChanged = Signal(str, str)

    def __init__(self, canvas=None, view=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.view = view
        self.widget = None
        self.widget_dir = None
        self.config_path = None
        self.config_store = {}

    def bind_widget(self, widget):
        self.widget = widget
        ensure_jshtml_widget_fields(widget.cfg)
        self.widget_dir = get_jshtml_widget_dir(widget.cfg)
        data_dir = self.widget_dir / "data"
        data_dir.mkdir(exist_ok=True)
        self.config_path = data_dir / "config.json"
        self.config_store = self._load_config_store()

    def _result(self, ok: bool, **kwargs) -> str:
        data = {"ok": bool(ok)}
        data.update(kwargs)
        return json.dumps(data, ensure_ascii=False)

    def _load_config_store(self) -> dict:
        try:
            if self.config_path and self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except:
            pass
        return {}

    def _save_config_store(self) -> bool:
        try:
            if not self.config_path:
                return False
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(self.config_store, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except:
            return False

    def _safe_path(self, relative_path: str) -> Optional[Path]:
        if self.widget_dir is None:
            return None
        return _jshtml_safe_path(self.widget_dir, relative_path)

    @Slot(result=str)
    def ping(self) -> str:
        return self._result(True, message="pong", runtime="LiteDesktopStudio.JSHTML")

    @Slot(result=str)
    def getWidgetInfo(self) -> str:
        cfg = getattr(getattr(self, "widget", None), "cfg", None)
        if cfg is None:
            return self._result(False, error="widget is not bound")
        return self._result(True, title=getattr(cfg, "title", ""), mode=getattr(cfg, "jshtml_mode", "inline"), instanceId=getattr(cfg, "jshtml_instance_id", ""), entry=getattr(cfg, "jshtml_entry", "index.html"), packageName=getattr(cfg, "jshtml_package_name", ""), packageVersion=getattr(cfg, "jshtml_package_version", ""), widgetDir=str(self.widget_dir) if self.widget_dir else "")

    @Slot(result=str)
    def getWidgetRect(self) -> str:
        try:
            r = self.widget.rect
            return self._result(True, x=int(r.left()), y=int(r.top()), width=int(r.width()), height=int(r.height()))
        except Exception as e:
            return self._result(False, error=repr(e))

    @Slot(result=str)
    def getSystemInfo(self) -> str:
        try:
            battery = None
            try:
                b = psutil.sensors_battery()
                if b is not None:
                    battery = {"percent": b.percent, "powerPlugged": b.power_plugged}
            except:
                battery = None
            return self._result(True, cpuPercent=psutil.cpu_percent(interval=0.0), memoryPercent=psutil.virtual_memory().percent, diskPercent=psutil.disk_usage(os.path.expanduser("~")).percent, battery=battery, platform=sys.platform)
        except Exception as e:
            return self._result(False, error=repr(e))

    @Slot(str, result=str)
    def readConfig(self, key: str) -> str:
        return self._result(True, key=key, value=self.config_store.get(key))

    @Slot(str, str, result=str)
    def writeConfig(self, key: str, value_json: str) -> str:
        try:
            value = json.loads(value_json)
        except:
            value = value_json
        self.config_store[str(key)] = value
        saved = self._save_config_store()
        if saved:
            self.configChanged.emit(str(key), json.dumps(value, ensure_ascii=False))
        return self._result(saved, key=str(key), value=value)

    @Slot(str, result=str)
    def openUrl(self, url: str) -> str:
        url = str(url or "")
        if not (url.startswith("https://") or url.startswith("http://")):
            return self._result(False, error="Only http:// and https:// URLs are allowed")
        try:
            webbrowser.open(url)
            return self._result(True)
        except Exception as e:
            return self._result(False, error=repr(e))

    @Slot(str, result=str)
    def getLocalAssetUrl(self, relative_path: str) -> str:
        target = self._safe_path(relative_path)
        if target is None:
            return self._result(False, error="Path is outside widget directory")
        if not target.exists():
            return self._result(False, error="Asset not found")
        return self._result(True, path=str(target), url=QUrl.fromLocalFile(str(target)).toString())

    @Slot(str, result=str)
    def listAssets(self, relative_dir: str) -> str:
        target = self._safe_path(relative_dir or "assets")
        if target is None:
            return self._result(False, error="Path is outside widget directory")
        if not target.exists() or not target.is_dir():
            return self._result(False, error="Directory not found", items=[])
        items = []
        try:
            for child in sorted(target.iterdir(), key=lambda x: x.name.lower()):
                if child.is_file():
                    items.append({"name": child.name, "relativePath": str(child.relative_to(self.widget_dir)).replace("\\", "/"), "url": QUrl.fromLocalFile(str(child)).toString(), "size": child.stat().st_size})
            return self._result(True, items=items)
        except Exception as e:
            return self._result(False, error=repr(e), items=[])

    def _get_audio_engine(self):
        try:
            audio = getattr(self.canvas, "audio", None)
            if audio is not None:
                return audio
        except:
            pass
        return None

    def _get_audio_snapshot(self) -> dict:
        audio = self._get_audio_engine()
        if audio is None:
            return {
                "ok": False,
                "available": False,
                "bands": [],
                "bandCount": 0,
                "level": 0.0,
                "peak": 0.0,
                "rms": 0.0,
                "backend": "unavailable",
                "useFake": False,
                "running": False,
                "timestamp": time.time(),
                "error": "audio engine is not available",
            }

        try:
            if hasattr(audio, "get_audio_snapshot"):
                snapshot = audio.get_audio_snapshot()
                if isinstance(snapshot, dict):
                    return snapshot
        except Exception as e:
            return {
                "ok": False,
                "available": True,
                "bands": [],
                "bandCount": 0,
                "level": 0.0,
                "peak": 0.0,
                "rms": 0.0,
                "backend": getattr(audio, "backend_name", "unknown"),
                "useFake": bool(getattr(audio, "use_fake", False)),
                "running": bool(getattr(audio, "running", False)),
                "timestamp": time.time(),
                "error": repr(e),
            }

        try:
            spectrum = audio.get_spectrum()
            arr = np.asarray(spectrum, dtype=np.float32)
            arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
            arr = np.clip(arr, 0.0, 1.0)
            if arr.size <= 0:
                bands = []
                level = peak = rms = 0.0
            else:
                bands = arr.tolist()
                level = float(np.mean(arr))
                peak = float(np.max(arr))
                rms = float(np.sqrt(np.mean(arr * arr)))
            return {
                "ok": True,
                "available": True,
                "bands": bands,
                "bandCount": int(len(bands)),
                "level": level,
                "peak": peak,
                "rms": rms,
                "backend": getattr(audio, "backend_name", "unknown"),
                "useFake": bool(getattr(audio, "use_fake", False)),
                "running": bool(getattr(audio, "running", False)),
                "timestamp": time.time(),
            }
        except Exception as e:
            return {
                "ok": False,
                "available": True,
                "bands": [],
                "bandCount": 0,
                "level": 0.0,
                "peak": 0.0,
                "rms": 0.0,
                "backend": getattr(audio, "backend_name", "unknown"),
                "useFake": bool(getattr(audio, "use_fake", False)),
                "running": bool(getattr(audio, "running", False)),
                "timestamp": time.time(),
                "error": repr(e),
            }

    @Slot(result=str)
    def getAudioInfo(self) -> str:
        snapshot = self._get_audio_snapshot()
        return self._result(
            bool(snapshot.get("ok", False)),
            available=bool(snapshot.get("available", snapshot.get("ok", False))),
            backend=snapshot.get("backend", "unknown"),
            useFake=bool(snapshot.get("useFake", False)),
            running=bool(snapshot.get("running", False)),
            bars=int(snapshot.get("bandCount", 0) or 0),
            timestamp=float(snapshot.get("timestamp", 0.0) or 0.0),
            error=snapshot.get("error", "")
        )

    @Slot(result=str)
    def getAudioLevel(self) -> str:
        snapshot = self._get_audio_snapshot()
        return self._result(
            bool(snapshot.get("ok", False)),
            available=bool(snapshot.get("available", snapshot.get("ok", False))),
            level=float(snapshot.get("level", 0.0) or 0.0),
            peak=float(snapshot.get("peak", 0.0) or 0.0),
            rms=float(snapshot.get("rms", 0.0) or 0.0),
            bars=int(snapshot.get("bandCount", 0) or 0),
            backend=snapshot.get("backend", "unknown"),
            useFake=bool(snapshot.get("useFake", False)),
            running=bool(snapshot.get("running", False)),
            timestamp=float(snapshot.get("timestamp", 0.0) or 0.0),
            error=snapshot.get("error", "")
        )

    @Slot(result=str)
    def getAudioSpectrum(self) -> str:
        snapshot = self._get_audio_snapshot()
        bands = snapshot.get("bands", [])
        if not isinstance(bands, list):
            bands = []
        return self._result(
            bool(snapshot.get("ok", False)),
            available=bool(snapshot.get("available", snapshot.get("ok", False))),
            bands=bands,
            bandCount=int(snapshot.get("bandCount", len(bands)) or 0),
            level=float(snapshot.get("level", 0.0) or 0.0),
            peak=float(snapshot.get("peak", 0.0) or 0.0),
            rms=float(snapshot.get("rms", 0.0) or 0.0),
            backend=snapshot.get("backend", "unknown"),
            useFake=bool(snapshot.get("useFake", False)),
            running=bool(snapshot.get("running", False)),
            timestamp=float(snapshot.get("timestamp", 0.0) or 0.0),
            error=snapshot.get("error", "")
        )

    @Slot(str, result=str)
    def readTextFile(self, relative_path: str) -> str:
        target = self._safe_path(relative_path)
        if target is None:
            return self._result(False, error="Path is outside widget directory")
        if not target.exists() or not target.is_file():
            return self._result(False, error="File not found")
        try:
            if target.stat().st_size > 2 * 1024 * 1024:
                return self._result(False, error="File is too large")
            return self._result(True, text=target.read_text(encoding="utf-8"))
        except Exception as e:
            return self._result(False, error=repr(e))


def lds_keep_jshtml_webengine_active(view):
    """Best-effort keep-active hook for JSHTML QWebEngineView pages.

    This does not change widget content; it only asks QtWebEngine not to treat the
    page as discarded/frozen when Chromium lifecycle APIs are available.
    """
    try:
        if view is None:
            return False
        try:
            view.setUpdatesEnabled(True)
        except Exception:
            pass
        page = None
        try:
            page = view.page()
        except Exception:
            page = None
        if page is not None:
            try:
                from PySide6.QtWebEngineCore import QWebEnginePage
                if hasattr(page, "setLifecycleState"):
                    page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
                if hasattr(page, "setRecommendedState"):
                    page.setRecommendedState(QWebEnginePage.LifecycleState.Active)
            except Exception as e:
                try:
                    print("[LiteDesktopStudio] JSHTML lifecycle active failed:", repr(e))
                except Exception:
                    pass
            try:
                page.runJavaScript("window.__LDS_JSHTML_LAST_KEEPALIVE__ = Date.now();")
            except Exception:
                pass
        return True
    except Exception as e:
        try:
            print("[LiteDesktopStudio] keep JSHTML WebEngine active failed:", repr(e))
        except Exception:
            pass
        return False


def lds_install_jshtml_webengine_keepalive(view, interval_ms: int = 30000):
    """Install a lightweight keep-alive timer on a JSHTML WebEngine view."""
    try:
        if view is None:
            return False
        if getattr(view, "_lds_jshtml_keepalive_timer", None) is not None:
            return True
        timer = QTimer(view)
        timer.setInterval(max(5000, int(interval_ms)))
        timer.timeout.connect(lambda v=view: lds_keep_jshtml_webengine_active(v))
        timer.start()
        view._lds_jshtml_keepalive_timer = timer
        try:
            lds_keep_jshtml_webengine_active(view)
        except Exception:
            pass
        return True
    except Exception as e:
        try:
            print("[LiteDesktopStudio] install JSHTML keepalive failed:", repr(e))
        except Exception:
            pass
        return False


def lds_float_env(name: str, default_value: float, min_value: float, max_value: float) -> float:
    try:
        raw = os.environ.get(name, "")
        if raw == "":
            return float(default_value)
        value = float(raw)
        return max(float(min_value), min(float(max_value), value))
    except Exception:
        return float(default_value)


def lds_bool_env(name: str, default_value: bool = False) -> bool:
    try:
        raw = str(os.environ.get(name, "1" if default_value else "0")).strip().lower()
        if raw in ("1", "true", "yes", "on", "enable", "enabled"):
            return True
        if raw in ("0", "false", "no", "off", "disable", "disabled"):
            return False
    except Exception:
        pass
    return bool(default_value)


def lds_configure_jshtml_webengine_profile(profile) -> bool:
    if profile is None:
        return False
    ok = False
    try:
        from PySide6.QtWebEngineCore import QWebEngineProfile
    except Exception:
        QWebEngineProfile = None
    try:
        if QWebEngineProfile is not None:
            try:
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
                ok = True
            except Exception:
                try:
                    profile.setHttpCacheType(QWebEngineProfile.NoCache)
                    ok = True
                except Exception:
                    pass
            try:
                profile.setHttpCacheMaximumSize(0)
                ok = True
            except Exception:
                pass
            try:
                profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
                ok = True
            except Exception:
                try:
                    profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
                    ok = True
                except Exception:
                    pass
        try:
            profile.clearHttpCache()
            ok = True
        except Exception:
            pass
        try:
            profile.clearAllVisitedLinks()
            ok = True
        except Exception:
            pass
        try:
            profile.setSpellCheckEnabled(False)
            ok = True
        except Exception:
            pass
        try:
            profile.setPushServiceEnabled(False)
            ok = True
        except Exception:
            pass
    except Exception:
        pass
    return ok


def lds_qtwebengine_process_memory_mb():
    try:
        proc = psutil.Process(os.getpid())
        total = 0
        details = []
        for child in proc.children(recursive=True):
            try:
                name = child.name() or ""
                try:
                    cmdline = " ".join(child.cmdline() or [])
                except Exception:
                    cmdline = ""
                label = (name + " " + cmdline).lower()
                if "qtwebengineprocess" in label or "qtwebengine" in label:
                    rss = int(child.memory_info().rss)
                    total += rss
                    details.append({"pid": int(child.pid), "name": name, "rss_mb": round(rss / (1024 * 1024), 1)})
            except Exception:
                pass
        return total / (1024 * 1024), details
    except Exception:
        return 0.0, []


def lds_collect_python_after_webengine_recycle():
    try:
        import gc
        gc.collect()
    except Exception:
        pass


class JSHtmlViewManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.views = {}
        self.channels = {}
        self.apis = {}
        self.last_html = {}
        self.last_source = {}
        self.available = True
        self.error = ""
        self.memory_watchdog_timer = None
        self.memory_recycle_threshold_mb = lds_float_env("LITEDESKTOPSTUDIO_JSHTML_WEBENGINE_RECYCLE_MB", 1024.0, 128.0, 2048.0)
        self.memory_recycle_cooldown_sec = lds_float_env("LITEDESKTOPSTUDIO_JSHTML_WEBENGINE_RECYCLE_COOLDOWN_SEC", 25.0, 5.0, 600.0)
        self.last_memory_recycle_at = 0.0
        self.last_webengine_memory_mb = 0.0
        self.last_webengine_memory_details = []
        self.memory_watchdog_enabled = lds_bool_env("LITEDESKTOPSTUDIO_JSHTML_WEBENGINE_MEMORY_WATCHDOG", True)

        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebChannel import QWebChannel
        except Exception as e:
            self.available = False
            self.error = repr(e)
        if self.available and self.memory_watchdog_enabled:
            self._install_memory_watchdog()

    def set_visible(self, visible: bool):
        for view in list(getattr(self, "views", {}).values()):
            try:
                view.setVisible(visible)
            except:
                pass

    def _install_memory_watchdog(self):
        try:
            if getattr(self, "memory_watchdog_timer", None) is not None:
                return True
            timer = QTimer(self.canvas)
            timer.setInterval(int(lds_float_env("LITEDESKTOPSTUDIO_JSHTML_WEBENGINE_MEMORY_POLL_MS", 5000.0, 1000.0, 60000.0)))
            timer.timeout.connect(self._check_webengine_memory)
            timer.start()
            self.memory_watchdog_timer = timer
            return True
        except Exception as e:
            self.error = repr(e)
            return False

    def _check_webengine_memory(self):
        try:
            if not getattr(self, "views", None):
                return
            total_mb, details = lds_qtwebengine_process_memory_mb()
            self.last_webengine_memory_mb = float(total_mb)
            self.last_webengine_memory_details = list(details or [])
            try:
                self.canvas.setProperty("jshtmlWebEngineMemoryMb", round(float(total_mb), 1))
            except Exception:
                pass
            if total_mb <= 0:
                return
            threshold = float(getattr(self, "memory_recycle_threshold_mb", 360.0))
            if total_mb < threshold:
                return
            now = time.time()
            cooldown = float(getattr(self, "memory_recycle_cooldown_sec", 25.0))
            if now - float(getattr(self, "last_memory_recycle_at", 0.0)) < cooldown:
                return
            self.last_memory_recycle_at = now
            try:
                print("[LiteDesktopStudio] JSHTML QtWebEngineProcess RSS high:", round(total_mb, 1), "MB; recycling views", details)
            except Exception:
                pass
            self.recycle_all_views(reason="webengine-memory-high")
        except Exception as e:
            self.error = repr(e)

    def _cleanup_view_runtime(self, view, reason="dispose"):
        try:
            page = view.page() if view is not None else None
            if page is None:
                return False
            script = "try{if(window.LDSRuntime&&LDSRuntime.cleanup){LDSRuntime.cleanup(%r);}}catch(e){}" % str(reason)
            page.runJavaScript(script)
            return True
        except Exception:
            return False

    def _dispose_view(self, view, reason="dispose"):
        """Dispose JSHTML QWebEngine objects in page -> view -> profile order.

        QtWebEngine warns if a QWebEngineProfile is released while a
        QWebEnginePage using it still exists.  The page is therefore detached from
        JS state first, queued for deletion, and the profile deletion is delayed
        to a later event-loop turn.
        """
        if view is None:
            return

        page = None
        profile = None

        try:
            page = getattr(view, "_lds_jshtml_page", None)
            if page is None:
                page = view.page()
        except Exception:
            page = None

        try:
            profile = getattr(view, "_lds_jshtml_profile", None)
            if profile is None and page is not None:
                profile = page.profile()
        except Exception:
            profile = None

        try:
            self._cleanup_view_runtime(view, reason)
        except Exception:
            pass

        try:
            timer = getattr(view, "_lds_jshtml_keepalive_timer", None)
            if timer is not None:
                timer.stop()
                timer.deleteLater()
                view._lds_jshtml_keepalive_timer = None
        except Exception:
            pass

        try:
            view.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        try:
            view.hide()
        except Exception:
            pass

        # 1) Page first: stop JS/WebChannel/load, then queue page deletion.
        if page is not None:
            try:
                page.runJavaScript(
                    "try{if(window.LDSRuntime&&LDSRuntime.cleanup){LDSRuntime.cleanup(%r);}}catch(e){}" % str(reason)
                )
            except Exception:
                pass
            try:
                page.setWebChannel(None)
            except Exception:
                pass
            try:
                page.setHtml("<html><body></body></html>", QUrl("about:blank"))
            except Exception:
                try:
                    page.load(QUrl("about:blank"))
                except Exception:
                    pass
            try:
                QTimer.singleShot(0, page.deleteLater)
            except Exception:
                try:
                    page.deleteLater()
                except Exception:
                    pass

        # 2) View next.  Clear Python-side references so GC cannot keep profile/page alive.
        try:
            view._lds_jshtml_page = None
            view._lds_jshtml_profile = None
            view._lds_widget = None
        except Exception:
            pass
        try:
            QTimer.singleShot(0, view.deleteLater)
        except Exception:
            try:
                view.deleteLater()
            except Exception:
                pass

        # 3) Profile last.  Delay enough for page.deleteLater() to run first.
        if profile is not None:
            try:
                lds_configure_jshtml_webengine_profile(profile)
            except Exception:
                pass

            def _lds_delete_profile_later(p=profile):
                try:
                    p.clearHttpCache()
                except Exception:
                    pass
                try:
                    p.deleteLater()
                except Exception:
                    pass

            try:
                QTimer.singleShot(1000, _lds_delete_profile_later)
            except Exception:
                try:
                    profile.deleteLater()
                except Exception:
                    pass

    def recycle_all_views(self, reason="recycle"):
        try:
            widgets = [w for w in list(getattr(self.canvas, "widgets", []) or []) if isinstance(w, JSHtmlWidget)]
            for view in list(self.views.values()):
                try:
                    self._dispose_view(view, reason)
                except Exception:
                    pass
            self.views.clear(); self.channels.clear(); self.apis.clear(); self.last_html.clear(); self.last_source.clear()
            lds_collect_python_after_webengine_recycle()
            if widgets:
                try:
                    QTimer.singleShot(250, lambda: self.sync(getattr(self.canvas, "widgets", [])))
                except Exception:
                    self.sync(getattr(self.canvas, "widgets", []))
            return True
        except Exception as e:
            self.error = repr(e)
            return False

    def sync(self, widgets):
        if not self.available:
            return
        active_ids = set()
        for widget in widgets:
            if not isinstance(widget, JSHtmlWidget):
                continue
            key = id(widget)
            active_ids.add(key)
            view = self.views.get(key)
            if view is None:
                view = self._create_view(key)
                self.views[key] = view
            api = self.apis.get(key)
            if api is not None:
                try:
                    api.bind_widget(widget)
                except Exception as e:
                    self.error = repr(e)
            self._sync_view(widget, view)
        stale_ids = [key for key in self.views.keys() if key not in active_ids]
        for key in stale_ids:
            view = self.views.pop(key)
            self.channels.pop(key, None)
            self.apis.pop(key, None)
            self.last_html.pop(key, None)
            self.last_source.pop(key, None)
            try:
                self._dispose_view(view, "stale-widget")
            except:
                pass

    def clear(self):
        for view in list(self.views.values()):
            try:
                self._dispose_view(view, "manager-clear")
            except:
                pass
        self.views.clear(); self.channels.clear(); self.apis.clear(); self.last_html.clear(); self.last_source.clear()
        lds_collect_python_after_webengine_recycle()

    def reload_widget(self, widget) -> bool:
        try:
            if widget is None:
                return False
            key = id(widget)
            self.last_html.pop(key, None)
            self.last_source.pop(key, None)
            view = self.views.get(key)
            if view is not None:
                self._sync_view(widget, view)
            return True
        except Exception as e:
            self.error = repr(e)
            return False

    def _create_view(self, key):
        class _LDSJSHtmlWebEngineView(QWebEngineView):
            def __init__(self, canvas, parent=None):
                super().__init__(parent or canvas)
                self.canvas = canvas
                self._lds_widget = None
                self._lds_last_right_click_time = 0.0
                self._lds_installed_filter_ids = set()
                try:
                    self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
                except:
                    try:
                        self.setContextMenuPolicy(Qt.NoContextMenu)
                    except:
                        pass
                try:
                    self.installEventFilter(self)
                    self._lds_installed_filter_ids.add(id(self))
                except:
                    pass
                # QWebEngineView often receives mouse input through internal child widgets.
                # Install filters a few times after construction/load so right-clicks do not
                # get swallowed by WebEngine's own Reload context menu.
                for delay in (0, 100, 500, 1200):
                    try:
                        QTimer.singleShot(delay, self._install_jshtml_mouse_filters)
                    except:
                        pass


            def _install_jshtml_mouse_filters(self):
                targets = []
                try:
                    targets.append(self)
                except:
                    pass
                try:
                    proxy = self.focusProxy()
                    if proxy is not None:
                        targets.append(proxy)
                except:
                    pass
                try:
                    targets.extend(self.findChildren(QObject))
                except:
                    pass
                for obj in targets:
                    try:
                        key = id(obj)
                        if key in self._lds_installed_filter_ids:
                            continue
                        obj.installEventFilter(self)
                        self._lds_installed_filter_ids.add(key)
                    except:
                        pass

            def _canvas_pos_from_event(self, event):
                try:
                    return self.mapToParent(event.position().toPoint())
                except:
                    try:
                        return self.mapToParent(event.pos())
                    except:
                        return QPoint(0, 0)

            def _open_litedesktopstudio_for_this_widget(self):
                try:
                    widget = getattr(self, "_lds_widget", None)
                    if widget is not None and hasattr(self.canvas, "open_studio_for_widget"):
                        self.canvas.open_studio_for_widget(widget)
                        return True
                    if hasattr(self.canvas, "open_studio_for_point"):
                        return self.canvas.open_studio_for_point(QPoint(0, 0))
                    if hasattr(self.canvas, "open_studio"):
                        self.canvas.open_studio()
                        return True
                except Exception as e:
                    try: print("[LiteDesktopStudio] JSHTML right-click open failed:", repr(e))
                    except: pass
                return False

            def _handle_jshtml_right_click(self, event):
                now = time.time()
                try:
                    interval = QApplication.doubleClickInterval() / 1000.0
                except:
                    interval = 0.45
                try:
                    event.accept()
                except:
                    pass
                if now - self._lds_last_right_click_time <= max(0.15, interval):
                    self._lds_last_right_click_time = 0.0
                    self._open_litedesktopstudio_for_this_widget()
                    return True
                self._lds_last_right_click_time = now
                return True

            def contextMenuEvent(self, event):
                # Suppress QWebEngineView's default menu such as Reload / Back / Forward.
                try:
                    event.accept()
                except:
                    pass

            def eventFilter(self, obj, event):
                try:
                    event_type = event.type()
                    if event_type == QEvent.Type.ContextMenu:
                        try:
                            event.accept()
                        except:
                            pass
                        return True
                    if event_type == QEvent.Type.MouseButtonPress:
                        try:
                            if event.button() == Qt.MouseButton.RightButton:
                                return self._handle_jshtml_right_click(event)
                        except:
                            pass
                    if event_type == QEvent.Type.MouseButtonDblClick:
                        try:
                            if event.button() == Qt.MouseButton.RightButton:
                                self._lds_last_right_click_time = 0.0
                                self._open_litedesktopstudio_for_this_widget()
                                try:
                                    event.accept()
                                except:
                                    pass
                                return True
                        except:
                            pass
                except:
                    pass
                try:
                    return super().eventFilter(obj, event)
                except:
                    return False

            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.RightButton:
                    self._handle_jshtml_right_click(event)
                    return
                super().mousePressEvent(event)

            def mouseDoubleClickEvent(self, event):
                if event.button() == Qt.MouseButton.RightButton:
                    self._lds_last_right_click_time = 0.0
                    self._open_litedesktopstudio_for_this_widget()
                    try:
                        event.accept()
                    except:
                        pass
                    return
                super().mouseDoubleClickEvent(event)

        view = _LDSJSHtmlWebEngineView(self.canvas, self.canvas)
        try:
            from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
            # Keep the profile alive longer than the view/page.  If the profile is
            # parented to the view, Qt may request profile release while the page is
            # still queued for deleteLater(), causing:
            # "Release of profile requested but WebEnginePage still not deleted".
            profile = QWebEngineProfile(self.canvas)
            lds_configure_jshtml_webengine_profile(profile)
            page = QWebEnginePage(profile, view)
            view.setPage(page)
            view._lds_jshtml_profile = profile
            view._lds_jshtml_page = page
        except Exception as e:
            try:
                self.error = repr(e)
            except Exception:
                pass
            try:
                lds_configure_jshtml_webengine_profile(view.page().profile())
            except Exception:
                pass
        try:
            lds_keep_jshtml_webengine_active(view)
            lds_install_jshtml_webengine_keepalive(view)
        except Exception:
            pass
        view.setAttribute(Qt.WA_TranslucentBackground, True)
        view.setStyleSheet("background: transparent;")
        try:
            page = view.page()
            page.setBackgroundColor(Qt.transparent)
            try:
                lds_keep_jshtml_webengine_active(view)
            except Exception:
                pass
            try:
                view.loadFinished.connect(lambda ok, v=view: lds_keep_jshtml_webengine_active(v))
            except Exception:
                pass
        except:
            pass
        try:
            settings = view.settings()
            try:
                from PySide6.QtWebEngineCore import QWebEngineSettings
                settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            except:
                pass
        except:
            pass
        try:
            channel = QWebChannel(view)
            api = JSHtmlWidgetApi(self.canvas, view, view)
            channel.registerObject("LDSApi", api)
            view.page().setWebChannel(channel)
            try:
                QTimer.singleShot(0, view._install_jshtml_mouse_filters)
                QTimer.singleShot(500, view._install_jshtml_mouse_filters)
            except:
                pass
            self.channels[key] = channel
            self.apis[key] = api
        except Exception as e:
            self.error = repr(e)
        try:
            QTimer.singleShot(0, view.show)
        except:
            try: view.show()
            except: pass
        return view

    def _package_html_and_source(self, widget):
        cfg = widget.cfg
        widget_dir = get_jshtml_widget_dir(cfg)
        entry = getattr(cfg, "jshtml_entry", "index.html") or "index.html"
        entry_path = _jshtml_safe_path(widget_dir, entry)
        if entry_path is None or not entry_path.exists() or not entry_path.is_file():
            return None, None, widget_dir
        try:
            raw_html = entry_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_html = entry_path.read_text(encoding="utf-8", errors="replace")
        html = build_js_html_document(raw_html)
        try:
            source = f"package:{entry_path}:{entry_path.stat().st_mtime_ns}:{entry_path.stat().st_size}"
        except:
            source = f"package:{entry_path}:{time.time()}"
        return html, source, widget_dir

    def _sync_view(self, widget, view):
        cfg = widget.cfg
        ensure_jshtml_widget_fields(cfg)
        try:
            view._lds_widget = widget
        except:
            pass
        try:
            if hasattr(view, "_install_jshtml_mouse_filters"):
                view._install_jshtml_mouse_filters()
        except:
            pass
        r = widget.rect
        try:
            lds_keep_jshtml_webengine_active(view)
        except Exception:
            pass
        view.setGeometry(int(r.left()), int(r.top()), max(1, int(r.width())), max(1, int(r.height())))
        edit_mode = bool(getattr(self.canvas, "edit_mode", True))
        desktop_priority = bool(getattr(self.canvas, "desktop_priority_mode", False))
        view.setAttribute(Qt.WA_TransparentForMouseEvents, edit_mode or desktop_priority)
        key = id(widget)
        mode = str(getattr(cfg, "jshtml_mode", "inline") or "inline").lower()
        if mode == "package":
            html, source_key, widget_dir = self._package_html_and_source(widget)
            if html is None:
                html = build_js_html_document(f"""<div style='padding:14px;border:1px solid rgba(255,255,255,.2);border-radius:14px;background:rgba(20,24,32,.72);color:white;font-family:Segoe UI,sans-serif;'><h3 style='margin:0 0 8px;color:#FFCC66;'>JSHTML Package Error</h3><div>entry HTML が見つかりません: {getattr(cfg, 'jshtml_entry', 'index.html')}</div></div>""")
                source_key = "package-error:" + str(time.time())
                widget_dir = get_jshtml_widget_dir(cfg)
            base_url = QUrl.fromLocalFile(str(widget_dir) + os.sep)
        else:
            raw_html = get_js_html_from_config(cfg)
            html = build_js_html_document(raw_html)
            widget_dir = get_jshtml_widget_dir(cfg)
            base_url = QUrl.fromLocalFile(str(widget_dir) + os.sep)
            source_key = "inline:" + html
        if self.last_source.get(key) != source_key:
            try:
                self._cleanup_view_runtime(view, "html-source-change")
            except Exception:
                pass
            try:
                lds_configure_jshtml_webengine_profile(view.page().profile())
            except Exception:
                pass
            self.last_source[key] = source_key
            self.last_html[key] = html
            try:
                view.setHtml(html, base_url)
            except:
                try: view.setHtml(html)
                except Exception as e: self.error = repr(e)
        if not view.isVisible():
            try:
                QTimer.singleShot(0, view.show)
            except:
                try: view.show()
                except: pass


def get_js_html_from_config(cfg):
    
    return getattr(cfg, "text", "") or DEFAULT_JS_HTML


def set_js_html_to_config(cfg, html: str):
    
    cfg.text = html or ""
