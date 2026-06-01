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
from litedesktopstudio.version import APP_NAME



def lds_tr(text: str) -> str:
    """Translate UI text.

    Primary path: Qt .qm translation files.
    Fallback path: a small built-in dictionary for labels added by this file,
    so cloud-related controls remain usable in Japanese or English even when
    external translation files are not installed.
    """
    source = str(text)
    try:
        translated = QApplication.translate("LiteDesktopStudio", source)
    except:
        translated = source
    try:
        if translated and translated != source:
            return translated
        lang = (globals().get("_LDS_TRANSLATOR_LANG") or QLocale.system().name() or "ja_JP").split("_", 1)[0].lower()
        table = globals().get("LDS_BUILTIN_TRANSLATIONS", {}).get(lang, {})
        return table.get(source, translated or source)
    except:
        return translated or source


CONFIG_PATH = os.path.join(os.path.expanduser('~'), "LiteDesktopStudio_config.json")


LDS_DEFAULT_LANGUAGE = "en_US"


LDS_SOURCE_LANGUAGE = "ja_JP"


LDS_LANGUAGE_CONFIG_KEY = "language"


_LDS_TRANSLATOR = None


_LDS_TRANSLATOR_LANG = ""


_LDS_TRANSLATOR_PATH = ""


LDS_BUILTIN_TRANSLATIONS = {
    "en": {
        "パムッカレの棚田な湖": "Pamukkale terrace pools",
        "ブルーホールの深い青の湖": "Blue Hole deep blue lake",
        "父母ヶ島の鏡面反射する水辺": "Chichibugahama mirror shore",
        "雲の流れ": "Cloud drift",
        "雲": "Clouds",
        "柔らかい雲が空をゆっくり流れる": "Soft clouds drift slowly across the sky",
        "雲の色": "Cloud color",
        "雲の影色": "Cloud shadow color",
        "雲のハイライト色": "Cloud highlight color",
        "雲の高さ": "Cloud altitude",
        "雲の奥行き": "Cloud depth",
        "雲の柔らかさ": "Cloud softness",
        "雲の形ランダム度": "Cloud shape randomness",
        "雲の立体感": "Cloud volume",
        "軽量ミスト雲": "Lightweight mist clouds",
        "軽量キャッシュ雲": "Lightweight cached clouds",
        "Shader風雲": "Shader-like clouds",
        "立体コントラスト": "Volumetric contrast",
        "ブルーム": "Bloom",
        "雲底影": "Cloud underside shadow",
        "輪郭光": "Rim light",
        "暖色ハイライト": "Warm highlight",
        "Shaders風ライティング": "Shaders-like lighting",
        "入道雲の盛り上がり": "Cumulus tower strength",
        "入道雲ふわふわ感": "Cumulus fluffiness",
        "入道雲モード": "Cumulus cloud mode",
        "雲キャッシュ最大数": "Cloud cache limit",
        "雲キャッシュ品質": "Cloud cache quality",
        "雲キャッシュを使う": "Use cloud cache",
        "ミスト透明感": "Mist translucency",
        "ミスト横伸び": "Mist stretch",
        "ミスト密度": "Mist density",
        "ミスト雲を使う": "Use mist clouds",
        "雲を反射": "Reflect clouds",
        "反射: 雲": "Reflection: Clouds",
        "ウユニ塩湖の静かな反射": "Uyuni salt-flat quiet reflection",
        "アンテロープキャニオンの岩肌": "Antelope Canyon warm rock walls",
        "ウユニ塩湖のような反射感": "Uyuni-like reflection",
        "アンテロープキャニオンのような迫りくる岩肌感": "Antelope Canyon-like enclosing rock walls",
        "サハラ砂漠の灼熱日光": "Sahara-like blazing desert sun",
        "風に流れる枯草の砂漠": "Wind-blown dry grass desert",
                "拙政園のゆったり水庭": "Humble Administrator's Garden - slow water garden",
                "留園の静かな庭": "Lingering Garden - quiet garden",
                "拙政園のようなゆったり感": "Slow spacious feeling like the Humble Administrator's Garden",
                "留園のような落ち着く感じ": "Calm feeling like the Lingering Garden",
        "🧰 その他のツール": "🧰 Other Tools",
        "🧰 その他のツールを開く": "🧰 Open Other Tools",
        "{} - その他のツール".format(APP_NAME): "{} - Other Tools".format(APP_NAME),
        "JSHTML package、画像変換、HTML/JSON/JavaScript編集、診断などの補助機能を開きます。\n\n右側のプロパティに詰め込みすぎず、今後ツールが増えてもこの画面から管理できるようにします。": "Open helper tools such as JSHTML package utilities, image conversion, HTML/JSON/JavaScript editing, and diagnostics.\n\nInstead of packing too much into the right-side properties panel, this screen keeps future tools organized in one place.",

        "デスクトップ操作優先モード": "Desktop priority mode",
        "デスクトップ操作優先モードをONにしました。LiteDesktopStudioは表示を優先し、マウス操作をできるだけデスクトップへ通します。": "Desktop priority mode is ON. LiteDesktopStudio prioritizes display and tries to pass mouse operations to the desktop.",
        "デスクトップ操作優先モードをOFFにしました。": "Desktop priority mode is OFF.",
    },
    "ja": {},
}


def _lds_app_base_dir() -> str:
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except:
        return os.getcwd()


def _lds_normalize_lang(lang=None) -> str:
    """Normalize language names used by QTranslator.

    Priority when *lang* is not specified:
    1. LITEDESKTOPSTUDIO_LANG environment variable
    2. --lang / --language / --locale command-line option
    3. LDS_DEFAULT_LANGUAGE (English)
    """
    try:
        value = (lang or "").strip()
    except:
        value = ""
    if not value:
        try:
            value = os.environ.get("LITEDESKTOPSTUDIO_LANG", "").strip()
        except:
            value = ""
    if not value:
        try:
            args = list(sys.argv or [])
            for i, arg in enumerate(args):
                if arg in ("--lang", "--language", "--locale") and i + 1 < len(args):
                    value = str(args[i + 1]).strip()
                    break
                if arg.startswith("--lang="):
                    value = arg.split("=", 1)[1].strip()
                    break
                if arg.startswith("--language="):
                    value = arg.split("=", 1)[1].strip()
                    break
                if arg.startswith("--locale="):
                    value = arg.split("=", 1)[1].strip()
                    break
        except:
            value = ""
    if not value:
        value = LDS_DEFAULT_LANGUAGE
    low = value.lower().replace("-", "_")
    aliases = {
        "ja": "ja_JP", "jp": "ja_JP", "japanese": "ja_JP", "日本語": "ja_JP",
        "en": "en_US", "english": "en_US", "us": "en_US", "english_us": "en_US",
    }
    return aliases.get(low, value.replace("-", "_"))


def _lds_is_source_language(lang=None) -> bool:
    return _lds_normalize_lang(lang).split("_", 1)[0].lower() == LDS_SOURCE_LANGUAGE.split("_", 1)[0].lower()


def _lds_translation_candidates(locale_name: str, translations_dir=None) -> List[str]:
    language_name = locale_name.split("_", 1)[0]
    app_dir = _lds_app_base_dir()
    base_dirs = []
    if translations_dir:
        base_dirs.append(translations_dir)
    base_dirs.extend([
        os.path.join(app_dir, "translations"),
        app_dir,
        os.getcwd(),
    ])
    names = [
        f"{locale_name}.qm",                         
        f"{language_name}.qm",                       
        f"LiteDesktopStudio_{locale_name}.qm",
        f"LiteDesktopStudio_{language_name}.qm",
        f"litedesktopstudio_{locale_name}.qm",
        f"litedesktopstudio_{language_name}.qm",
    ]
    candidates = []
    seen = set()
    for base_dir in base_dirs:
        for name in names:
            qm_path = os.path.abspath(os.path.join(base_dir, name))
            if qm_path not in seen:
                seen.add(qm_path)
                candidates.append(qm_path)
    return candidates


def install_litedesktopstudio_translator(app, lang=None, translations_dir=None, translator=None) -> bool:
    global _LDS_TRANSLATOR, _LDS_TRANSLATOR_LANG, _LDS_TRANSLATOR_PATH
    try:
        if app is None:
            return False
        locale_name = _lds_normalize_lang(lang)
        try:
            if _LDS_TRANSLATOR is not None:
                app.removeTranslator(_LDS_TRANSLATOR)
        except:
            pass
        _LDS_TRANSLATOR = None
        _LDS_TRANSLATOR_LANG = locale_name
        _LDS_TRANSLATOR_PATH = ""

        
        if _lds_is_source_language(locale_name):
            return True
        if lang == 'ja_JP':
            __locas = QLocale.Language.Japanese
        else:
            __locas = QLocale.Language.English
        if not translator:
            translator = QTranslator(app)
        for qm_path in _lds_translation_candidates(locale_name, translations_dir):
            try:
                if os.path.exists(qm_path) and translator.load(__locas, qm_path):
                    QCoreApplication.installTranslator(translator)
                    _LDS_TRANSLATOR = translator
                    _LDS_TRANSLATOR_PATH = qm_path
                    try:
                        app._litedesktopstudio_translator = translator
                    except:
                        pass
                    return True
            except:
                pass
        return False
    except:
        return False


def set_litedesktopstudio_language(app, lang: str, translations_dir=None) -> bool:
    return install_litedesktopstudio_translator(app, lang=lang, translations_dir=translations_dir)


def get_litedesktopstudio_language() -> str:
    return _LDS_TRANSLATOR_LANG or _lds_normalize_lang(None)


def get_litedesktopstudio_translator_path() -> str:
    return _LDS_TRANSLATOR_PATH


def load_litedesktopstudio_language_preference(default=None) -> str:
    """Read saved language from LiteDesktopStudio_config.json; fallback is English."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            lang = data.get(LDS_LANGUAGE_CONFIG_KEY) or data.get("locale") or data.get("language")
            if lang:
                return _lds_normalize_lang(lang)
    except:
        pass
    return _lds_normalize_lang(default or LDS_DEFAULT_LANGUAGE)


def save_litedesktopstudio_language_preference(lang: str) -> bool:
    """Persist language without touching widget settings when possible."""
    try:
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            except:
                data = {}
        data[LDS_LANGUAGE_CONFIG_KEY] = _lds_normalize_lang(lang)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False


DEFAULT_NETWORK_DOWN_COLOR = "#5BE7FF"


DEFAULT_NETWORK_UP_COLOR = "#80FF9F"


DEFAULT_STUDIO_THEME = "dark"


STUDIO_THEME_LIQUID_GLASS = "liquid_glass"


STUDIO_THEME_DARK = "dark"


STUDIO_THEME_MATERIAL = "material"


STUDIO_THEME_LIGHT = "light"


STUDIO_THEME_ORDER = [
    STUDIO_THEME_LIQUID_GLASS,
    STUDIO_THEME_DARK,
    STUDIO_THEME_MATERIAL,
    STUDIO_THEME_LIGHT,
]


STUDIO_THEME_LABEL_SOURCES = {
    STUDIO_THEME_LIQUID_GLASS: "リキッドグラス",
    STUDIO_THEME_DARK: "ダーク",
    STUDIO_THEME_MATERIAL: "マテリアル",
    STUDIO_THEME_LIGHT: "ライト",
}


STUDIO_THEME_LABEL_FALLBACKS = {
    STUDIO_THEME_LIQUID_GLASS: "Liquid Glass",
    STUDIO_THEME_DARK: "Dark",
    STUDIO_THEME_MATERIAL: "Material",
    STUDIO_THEME_LIGHT: "Light",
}


STUDIO_THEME_LABELS = STUDIO_THEME_LABEL_SOURCES


STUDIO_ACCENT_SOFT_RED = "#FFB3B3"


STUDIO_ACCENT_SOFT_RED_STRONG = "#FF8F8F"


THREADS = []


EFFECT_KIND_RAIN = "rain"


EFFECT_KIND_PARTICLES = "particles"


EFFECT_KIND_NOISE = "noise"


EFFECT_KIND_GLOW = "glow"


EFFECT_KIND_RIPPLE = "ripple"


MOUSE_EFFECT_RIPPLE = "click_ripple"


MOUSE_EFFECT_FLEE = "particle_flee"


MOUSE_EFFECT_GLOW = "mouse_glow"


EFFECT_GPU_ENV_FLAG = "LITEDESKTOPSTUDIO_EFFECT_GPU"


EFFECT_GPU_STATUS = {
    "requested": False,
    "configured": False,
    "available": False,
    "backend": lds_tr("未確認"),
    "message": lds_tr("GPU支援描画は未確認です"),
}


def _safe_qt_app_attr(name: str):
    try:
        return getattr(Qt.ApplicationAttribute, name)
    except:
        return None


def configure_effect_gpu_backend_before_app(force: bool = True) -> bool:
    """Configure Qt's GPU-friendly rendering path before QApplication is created.

    This does not rewrite every QPainter primitive into custom shaders. It enables
    Qt's OpenGL/RHI-friendly application attributes and default surface format so
    supported systems can use GPU-backed composition and pixmap/image paths.
    """
    if str(os.environ.get(EFFECT_GPU_ENV_FLAG, "1")).lower() in ("0", "false", "off", "no"):
        EFFECT_GPU_STATUS.update({"requested": False, "configured": False, "message": lds_tr("環境変数でGPU支援描画が無効です")})
        return False
    EFFECT_GPU_STATUS["requested"] = bool(force)
    try:
        for attr_name in ("AA_UseDesktopOpenGL", "AA_UseOpenGLES", "AA_ShareOpenGLContexts"):
            attr = _safe_qt_app_attr(attr_name)
            if attr is not None:
                try:
                    QApplication.setAttribute(attr, True)
                except:
                    pass
        try:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
            fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
            fmt.setSamples(0)
            fmt.setDepthBufferSize(0)
            fmt.setStencilBufferSize(0)
            QSurfaceFormat.setDefaultFormat(fmt)
        except:
            pass
        EFFECT_GPU_STATUS.update({"configured": True, "message": lds_tr("Qt GPU支援設定を適用しました")})
        return True
    except Exception as exc:
        EFFECT_GPU_STATUS.update({"configured": False, "message": "{} {exc}".format(lds_tr("Qt GPU支援設定に失敗:"), exc=exc)})
        return False


def detect_effect_gpu_backend() -> Dict[str, object]:
    """Best-effort OpenGL availability check after QApplication is available."""
    status = dict(EFFECT_GPU_STATUS)
    try:
        surface = QOffscreenSurface()
        surface.create()
        ctx = QOpenGLContext()
        created = bool(ctx.create())
        made_current = bool(created and surface.isValid() and ctx.makeCurrent(surface))
        if made_current:
            fmt = ctx.format()
            backend = "OpenGL"
            try:
                backend = f"OpenGL {fmt.majorVersion()}.{fmt.minorVersion()}"
            except:
                pass
            status.update({"available": True, "backend": backend, "message": lds_tr("GPU支援描画が利用可能です")})
            try:
                ctx.doneCurrent()
            except:
                pass
        else:
            status.update({"available": False, "backend": "Raster/Fallback", "message": lds_tr("OpenGLコンテキストを作成できないためCPU描画にフォールバックします")})
    except Exception as exc:
        status.update({"available": False, "backend": "Raster/Fallback", "message": "{} {exc}".format(lds_tr("GPU確認に失敗したためCPU描画にフォールバックします:"), exc=exc)})
    EFFECT_GPU_STATUS.update(status)
    return status


def effect_gpu_status_text() -> str:
    status = EFFECT_GPU_STATUS
    mark = "✅" if status.get("available") else ("⚙️" if status.get("configured") else "ℹ️")
    return f"{mark} {status.get('backend', '未確認')} - {status.get('message', '')}"


class Thread:
    def set_func(self, func):
        self.func = func
        self.thread = threading.Thread(target=self.func, daemon=True)

    def start(self):
        self.run()

    def run(self):
        self.threads = self.thread.start()
        return 0

    def running(self):
        try:
            return self.thread.is_alive()
        except:
            return None

    def kill(self):
        try:
            self.thread.join(0)
        except:
            pass


def normalize_studio_theme(value):
    value = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "glass": STUDIO_THEME_LIQUID_GLASS,
        "liquid": STUDIO_THEME_LIQUID_GLASS,
        "liquidglass": STUDIO_THEME_LIQUID_GLASS,
        "liquid_glass": STUDIO_THEME_LIQUID_GLASS,
        "dark": STUDIO_THEME_DARK,
        "material": STUDIO_THEME_MATERIAL,
        "material_design": STUDIO_THEME_MATERIAL,
        "light": STUDIO_THEME_LIGHT,
        "soft_light": STUDIO_THEME_LIGHT,
    }
    return aliases.get(value, DEFAULT_STUDIO_THEME)


def get_next_studio_theme(value):
    value = normalize_studio_theme(value)
    try:
        index = STUDIO_THEME_ORDER.index(value)
    except ValueError:
        index = 0
    return STUDIO_THEME_ORDER[(index + 1) % len(STUDIO_THEME_ORDER)]


def get_studio_theme_label(value, lang=None):
    """Return a Studio theme label for the current UI language.

    Important: this must be evaluated at display time, not at module import time.
    QTranslator is installed after QApplication is created, so translating theme
    labels in a global dictionary would freeze them in the wrong language.
    """
    value = normalize_studio_theme(value)
    source_label = STUDIO_THEME_LABEL_SOURCES.get(value, STUDIO_THEME_LABEL_SOURCES[DEFAULT_STUDIO_THEME])
    fallback_label = STUDIO_THEME_LABEL_FALLBACKS.get(value, STUDIO_THEME_LABEL_FALLBACKS[DEFAULT_STUDIO_THEME])
    locale_name = _lds_normalize_lang(lang or get_litedesktopstudio_language())

    # Japanese is the source UI language. When Japanese is selected, return the
    # Japanese source label directly, e.g. "リキッドグラス".
    if _lds_is_source_language(locale_name):
        return source_label

    # For English or other languages, prefer the .qm translation for the
    # Japanese source label. If that entry is not in the .qm file, use a safe
    # built-in English fallback so labels never stay Japanese in English mode.
    translated = lds_tr(source_label)
    if translated and translated != source_label:
        return translated
    if locale_name.lower().startswith("en"):
        return fallback_label
    return source_label


def get_studio_window_opacity(theme):
    theme = normalize_studio_theme(theme)
    if theme == STUDIO_THEME_LIQUID_GLASS:
        return 0.88
    if theme == STUDIO_THEME_DARK:
        return 0.94
    if theme == STUDIO_THEME_MATERIAL:
        return 0.94
    if theme == STUDIO_THEME_LIGHT:
        return 0.96
    return 0.92


def _qss_rgba(hex_color: str, alpha: int = 255) -> str:
    """Return rgba(r,g,b,a) for Qt style sheets. Keeps UI styling robust."""
    try:
        c = QColor(str(hex_color or "#FFFFFF"))
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {max(0, min(255, int(alpha)))})"
    except:
        return f"rgba(255, 255, 255, {max(0, min(255, int(alpha)))})"


def get_studio_settings_palette(theme):
    """Palette used by settings dialogs. It follows the current Studio theme.

    The goal is Photoshop-like contrast: dark panels, clear borders, blue/cyan
    accent colors, and readable beginner help cards. Light theme keeps the same
    structure but uses a bright surface.
    """
    theme = normalize_studio_theme(theme)
    if theme == STUDIO_THEME_LIGHT:
        return {
            "surface": "#F3F6FA",
            "panel": "#FFFFFF",
            "panel2": "#EEF3F9",
            "text": "#17202A",
            "muted": "#4F6275",
            "accent": "#1473E6",
            "accent2": "#00A8CC",
            "border": "#B8C7D8",
            "warn": "#B45B00",
        }
    if theme == STUDIO_THEME_MATERIAL:
        return {
            "surface": "#18212B",
            "panel": "#202B36",
            "panel2": "#263442",
            "text": "#F3F7FA",
            "muted": "#B7C8D6",
            "accent": "#64B5F6",
            "accent2": "#80CBC4",
            "border": "#3E5A70",
            "warn": "#FFD180",
        }
    if theme == STUDIO_THEME_LIQUID_GLASS:
        return {
            "surface": "#121B2A",
            "panel": "#1A2A3D",
            "panel2": "#223A54",
            "text": "#FFF7F7",
            "muted": "#D8E7F2",
            "accent": STUDIO_ACCENT_SOFT_RED_STRONG,
            "accent2": "#8BE8FF",
            "border": "#6A91B8",
            "warn": "#FFD8A8",
        }
    return {
        "surface": "#1F2229",
        "panel": "#2A2D35",
        "panel2": "#323640",
        "text": "#F4F6F8",
        "muted": "#B8C1CC",
        "accent": "#31A8FF",
        "accent2": "#00D2B8",
        "border": "#4A5568",
        "warn": "#FFCC66",
    }


def build_beginner_photoshop_settings_qss(theme):
    """Build a Photoshop-like, beginner-friendly QSS for settings dialogs."""
    p = get_studio_settings_palette(theme)
    return f"""
        QDialog {{
            background: {p['surface']};
            color: {p['text']};
            font-family: "Segoe UI", "Yu Gothic UI", "Meiryo", "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji";
            font-size: 13px;
        }}
        QTabWidget::pane {{
            background: {p['panel']};
            border: 1px solid {p['border']};
            border-radius: 14px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: {p['panel2']};
            color: {p['muted']};
            border: 1px solid {p['border']};
            border-bottom: none;
            padding: 9px 14px;
            min-height: 26px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            margin-right: 3px;
            font-weight: 650;
        }}
        QTabBar::tab:selected {{
            background: {p['panel']};
            color: {p['text']};
            border-top: 3px solid {p['accent']};
        }}
        QTabBar::tab:hover {{
            color: {p['text']};
            border-top: 3px solid {p['accent2']};
        }}
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QLabel {{
            color: {p['text']};
            background: transparent;
        }}
        QLabel#BeginnerTitle {{
            color: {p['text']};
            font-size: 20px;
            font-weight: 850;
            padding: 4px 2px;
        }}
        QLabel#BeginnerGuide {{
            color: {p['muted']};
            background: {_qss_rgba(p['panel2'], 230)};
            border: 1px solid {_qss_rgba(p['accent'], 120)};
            border-radius: 12px;
            padding: 10px 12px;
            line-height: 145%;
        }}
        QLabel#BeginnerSection {{
            color: {p['accent2']};
            font-size: 14px;
            font-weight: 850;
            margin-top: 12px;
            padding: 7px 10px;
            background: {_qss_rgba(p['panel2'], 190)};
            border-left: 4px solid {p['accent']};
            border-radius: 8px;
        }}
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {p['panel2']}, stop:1 {p['panel']});
            color: {p['text']};
            border: 1px solid {p['border']};
            border-radius: 10px;
            padding: 8px 13px;
            min-height: 30px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            border: 1px solid {p['accent']};
            background: {_qss_rgba(p['accent'], 45)};
        }}
        QPushButton:pressed {{
            background: {_qss_rgba(p['accent'], 85)};
        }}
        QCheckBox {{
            color: {p['text']};
            spacing: 8px;
            min-height: 28px;
            font-weight: 560;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 1px solid {p['border']};
            background: {p['panel2']};
        }}
        QCheckBox::indicator:checked {{
            background: {p['accent']};
            border: 1px solid {p['accent']};
        }}
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background: {p['panel2']};
            color: {p['text']};
            border: 1px solid {p['border']};
            border-radius: 8px;
            padding: 6px 8px;
            min-height: 26px;
            selection-background-color: {p['accent']};
        }}
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p['accent']};
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
            width: 22px;
            border: none;
            background: {_qss_rgba(p['accent'], 35)};
        }}
        QToolTip {{
            color: {p['text']};
            background: {p['panel']};
            border: 1px solid {p['accent']};
            padding: 7px;
            border-radius: 6px;
        }}
    """


def apply_beginner_photoshop_settings_style(dialog, theme=None):
    """Apply Photoshop-like styling to a settings dialog without changing logic."""
    try:
        if theme is None:
            parent = dialog.parent()
            canvas = getattr(parent, "canvas", None)
            theme = get_canvas_studio_theme(canvas) if canvas is not None else DEFAULT_STUDIO_THEME
        dialog.setStyleSheet(build_beginner_photoshop_settings_qss(theme))
    except:
        pass


def make_beginner_guide_label(title: str, body: str) -> QLabel:
    """Create a reusable beginner help card."""
    label = QLabel(f"<b>{title}</b><br>{body}")
    label.setObjectName("BeginnerGuide")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


def set_beginner_tooltip(widget, text: str):
    """Set a tooltip safely. Useful when UI labels are short but beginners need help."""
    try:
        if widget is not None:
            widget.setToolTip(str(text or ""))
    except:
        pass


def build_beginner_photoshop_main_qss(theme):
    """Extra QSS for the main widget editor.

    This is intentionally additive: the existing Studio theme still provides the
    base look, while this layer makes the editing screen more Photoshop-like and
    easier for beginners to scan.
    """
    p = get_studio_settings_palette(theme)
    return f"""
        QMainWindow {{
            background: {p['surface']};
        }}
        QWidget#SidePanel, QWidget#CenterPanel, QWidget#PropertyPanel {{
            background: {_qss_rgba(p['panel'], 236)};
            border: 1px solid {_qss_rgba(p['border'], 210)};
            border-radius: 18px;
        }}
        QScrollArea#PropertyScrollArea, QScrollArea#SideScrollArea {{
            background: transparent;
            border: none;
        }}
        QLabel#Title {{
            font-size: 22px;
            font-weight: 900;
            color: {p['text']};
            padding: 2px 0px 6px 0px;
        }}
        QLabel#SectionTitle {{
            color: {p['accent2']};
            font-size: 14px;
            font-weight: 900;
            margin-top: 10px;
            padding: 7px 10px;
            background: {_qss_rgba(p['panel2'], 190)};
            border-left: 4px solid {p['accent']};
            border-radius: 8px;
        }}
        QLabel#SubText, QLabel#StatusText {{
            color: {p['muted']};
            font-size: 12px;
        }}
        QLabel#BeginnerGuide {{
            color: {p['muted']};
            background: {_qss_rgba(p['panel2'], 220)};
            border: 1px solid {_qss_rgba(p['accent'], 115)};
            border-radius: 12px;
            padding: 10px 12px;
            line-height: 145%;
        }}
        QTextEdit#HelpBox {{
            color: {p['muted']};
            background: {_qss_rgba(p['panel2'], 220)};
            border: 1px solid {_qss_rgba(p['border'], 190)};
            border-radius: 12px;
            padding: 9px;
            selection-background-color: {p['accent']};
        }}
        QListWidget#LayerList {{
            color: {p['text']};
            background: {_qss_rgba(p['panel2'], 225)};
            border: 1px solid {_qss_rgba(p['border'], 200)};
            border-radius: 12px;
            padding: 6px;
            outline: 0;
        }}
        QListWidget#LayerList::item {{
            min-height: 30px;
            padding: 6px 8px;
            border-radius: 8px;
        }}
        QListWidget#LayerList::item:selected {{
            background: {_qss_rgba(p['accent'], 105)};
            color: {p['text']};
            border: 1px solid {p['accent']};
        }}
        QListWidget#LayerList::item:hover {{
            background: {_qss_rgba(p['accent2'], 55)};
        }}
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background: {_qss_rgba(p['panel2'], 235)};
            color: {p['text']};
            border: 1px solid {_qss_rgba(p['border'], 220)};
            border-radius: 9px;
            padding: 6px 8px;
            min-height: 26px;
            selection-background-color: {p['accent']};
        }}
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p['accent']};
            background: {_qss_rgba(p['panel2'], 255)};
        }}
        QCheckBox {{
            color: {p['text']};
            spacing: 8px;
            min-height: 28px;
            font-weight: 600;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 1px solid {_qss_rgba(p['border'], 230)};
            background: {_qss_rgba(p['panel2'], 245)};
        }}
        QCheckBox::indicator:checked {{
            background: {p['accent']};
            border: 1px solid {p['accent']};
        }}
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {_qss_rgba(p['panel2'], 255)}, stop:1 {_qss_rgba(p['panel'], 255)});
            color: {p['text']};
            border: 1px solid {_qss_rgba(p['border'], 230)};
            border-radius: 11px;
            padding: 8px 12px;
            min-height: 32px;
            font-weight: 760;
        }}
        QPushButton:hover {{
            border: 1px solid {p['accent']};
            background: {_qss_rgba(p['accent'], 50)};
        }}
        QPushButton:pressed {{
            background: {_qss_rgba(p['accent'], 90)};
        }}
        QPushButton#DangerButton {{
            border: 1px solid {_qss_rgba('#FF6B6B', 220)};
            color: #FFDADA;
        }}
        QPushButton#PrimaryButton {{
            border: 1px solid {p['accent']};
            background: {_qss_rgba(p['accent'], 65)};
        }}
        QToolTip {{
            color: {p['text']};
            background: {p['panel']};
            border: 1px solid {p['accent']};
            padding: 7px;
            border-radius: 6px;
        }}
    """


def apply_beginner_photoshop_main_style(studio, theme=None):
    """Apply only the beginner/Photoshop additive layer to a main editor window."""
    try:
        if theme is None:
            canvas = getattr(studio, "canvas", None)
            theme = get_canvas_studio_theme(canvas) if canvas is not None else DEFAULT_STUDIO_THEME
        current = studio.styleSheet() or ""
        extra = build_beginner_photoshop_main_qss(theme)
        if extra not in current:
            studio.setStyleSheet(current + "\n" + extra)
    except:
        pass


def set_canvas_studio_theme(canvas, theme):
    canvas.studio_theme = normalize_studio_theme(theme)


def get_canvas_studio_theme(canvas):
    return normalize_studio_theme(getattr(canvas, "studio_theme", DEFAULT_STUDIO_THEME))


def is_windows():
    return sys.platform.startswith("win")


def choose_canvas_window_flags(canvas):
    if is_windows():
        canvas.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |
            Qt.Tool
        )
    else:
        canvas.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
