import asyncio
import calendar as py_calendar
import ctypes
import json
import math
import random
import os
import queue
import sys
import threading
import time
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

import numpy as np
import psutil
import soundcard as sc
from PySide6.QtCore import (
    Qt,
    QRectF,
    QPoint,
    QTimer,
    QEvent,
    QUrl,
    QPointF,
    QRect, QCoreApplication,
 QTranslator,
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
)
from PySide6.QtWidgets import (
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
)
try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except Exception:
    QOpenGLWidget = None

warnings.filterwarnings(
    "ignore",
    message="data discontinuity in recording",
    category=Warning
)

APP_NAME = "Lite Desktop Studio v1.5.6"
CONFIG_PATH = os.path.join(os.path.expanduser('~'), "LiteDesktopStudio_config.json")




LDS_DEFAULT_LANGUAGE = "en_US"
LDS_SOURCE_LANGUAGE = "ja_JP"
LDS_LANGUAGE_CONFIG_KEY = "language"
_LDS_TRANSLATOR = None
_LDS_TRANSLATOR_LANG = ""
_LDS_TRANSLATOR_PATH = ""


def _lds_app_base_dir() -> str:
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
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
    except Exception:
        value = ""
    if not value:
        try:
            value = os.environ.get("LITEDESKTOPSTUDIO_LANG", "").strip()
        except Exception:
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
        except Exception:
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


def lds_tr(text: str) -> str:
    try:
        return QCoreApplication.translate("LiteDesktopStudio", str(text))
    except Exception:
        return str(text)


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


def install_litedesktopstudio_translator(app, lang=None, translations_dir=None) -> bool:
    global _LDS_TRANSLATOR, _LDS_TRANSLATOR_LANG, _LDS_TRANSLATOR_PATH
    try:
        if app is None:
            return False
        locale_name = _lds_normalize_lang(lang)
        try:
            if _LDS_TRANSLATOR is not None:
                app.removeTranslator(_LDS_TRANSLATOR)
        except Exception:
            pass
        _LDS_TRANSLATOR = None
        _LDS_TRANSLATOR_LANG = locale_name
        _LDS_TRANSLATOR_PATH = ""

        
        if _lds_is_source_language(locale_name):
            return True

        translator = QTranslator(app)
        for qm_path in _lds_translation_candidates(locale_name, translations_dir):
            try:
                if os.path.exists(qm_path) and translator.load(qm_path):
                    app.installTranslator(translator)
                    _LDS_TRANSLATOR = translator
                    _LDS_TRANSLATOR_PATH = qm_path
                    try:
                        app._litedesktopstudio_translator = translator
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
        return False
    except Exception:
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
            lang = data.get(LDS_LANGUAGE_CONFIG_KEY) or data.get("locale") or data.get("lang")
            if lang:
                return _lds_normalize_lang(lang)
    except Exception:
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
            except Exception:
                data = {}
        data[LDS_LANGUAGE_CONFIG_KEY] = _lds_normalize_lang(lang)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
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
STUDIO_THEME_LABELS = {
    STUDIO_THEME_LIQUID_GLASS: "リキッドグラス",
    STUDIO_THEME_DARK: "ダーク",
    STUDIO_THEME_MATERIAL: "マテリアル",
    STUDIO_THEME_LIGHT: "ライト",
}
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
    except Exception:
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
                except Exception:
                    pass
        try:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
            fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
            fmt.setSamples(0)
            fmt.setDepthBufferSize(0)
            fmt.setStencilBufferSize(0)
            QSurfaceFormat.setDefaultFormat(fmt)
        except Exception:
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
            except Exception:
                pass
            status.update({"available": True, "backend": backend, "message": lds_tr("GPU支援描画が利用可能です")})
            try:
                ctx.doneCurrent()
            except Exception:
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


LIGHTWEIGHT_ROSE_PETAL_DEFAULT_SETTINGS = {
    "rain_enabled": False,
    "particles_enabled": False,
    "noise_enabled": False,
    "glow_enabled": False,
    "ripple_enabled": False,
    "gpu_acceleration_enabled": True,
    "gpu_acceleration_prefer_opengl": True,
    "gpu_acceleration_smooth_pixmaps": True,
    "effect_frame_rate_enabled": True,
    "effect_frame_rate": 60,

    "mouse_ripple_enabled": False,
    "mouse_flee_enabled": False,
    "mouse_glow_enabled": False,

    "rain_ripple_enabled": False,
    "rose_petals_enabled": True,
    "rose_petal_ripple_enabled": False,
    "rose_petal_count": 24,
    "rose_petal_color": "#FF7AAE",
    "rose_petal_edge_color": "#FFD1E3",
    "rose_petal_speed": 0.25,
    "rose_petal_sway": 1.15,
    "rose_petal_size": 18.0,
    "rose_petal_alpha": 215,
    "rose_petal_surface_y": 0.84,
    "rose_petal_ripple_chance": 0.0,
    "rose_petal_rest_on_surface": False,
    "rose_petal_fade_on_surface": True,
    "rose_petal_fade_duration": 0.85,
    "rose_petal_fade_sink_distance": 10.0,
    "rose_petal_fade_spin": 0.35,
    "rose_petal_roundness": 0.78,
    "rose_petal_curl": 0.52,
    "rose_petal_shadow_alpha": 0,
    "rose_petal_highlight_alpha": 130,
    "rose_petal_vein_alpha": 90,
    "petal_night_enabled": False,
    "petal_night_tint_color": "#101A3A",
    "petal_night_tint_strength": 0.35,
    "petal_shadow_enabled": False,
    "petal_outline_enabled": True,
    "petal_outline_strength": 1.35,
    "petal_blizzard_enabled": False,
    "petal_wind_strength": 1.0,
    "petal_wind_randomness": 0.55,
    "petal_gust_interval": 4.0,
    "petal_gust_duration": 1.15,
    "petal_gust_strength": 1.45,
    "petal_mouse_flutter_enabled": True,
    "petal_mouse_flutter_strength": 1.0,
    "rose_flowers_enabled": False,
    "blooming_roses_enabled": False,
    "sakura_petals_enabled": False,
    "sakura_tree_enabled": False,
    "sakura_tree_petal_emit_enabled": False,
    "sakura_tree_realistic_blossoms": False,
    "sakura_tree_grand_mode": False,
    "sakura_tree_large_mode": False,
    "particle_count": 0,
    "rain_count": 0,
    "glow_count": 0,
    "intensity": 1.0,
    "background_alpha": 0,

    
    "snow_enabled": False,
    "snow_count": 90,
    "snow_speed": 0.18,
    "snow_size": 4.5,
    "snow_alpha": 210,
    "snow_color": "#F5FCFF",
    "snow_edge_color": "#CFEFFF",
    "snow_ripple_color": "#DFFBFF",
    "snow_ripple_enabled": True,
    "snow_ripple_chance": 0.38,
    "snow_surface_y": 0.86,
    "snow_accumulation_enabled": False,
    "snow_accumulation_start_y": 1.0,
    "snow_accumulation_max_depth": 1.0,
    "snow_accumulation_build_rate": 7.0,
    "snow_accumulation_column_width": 7.0,
    "snow_accumulation_alpha": 230,
    "snow_accumulation_mouse_remove_enabled": True,
    "snow_accumulation_remove_radius": 58.0,
    "snow_accumulation_remove_strength": 72.0,
    "snow_crystal_enabled": False,
    "snow_crystal_count": 22,
    "snow_crystal_speed": 0.12,
    "snow_crystal_size": 15.0,
    "snow_crystal_alpha": 220,
    "snow_crystal_color": "#EBFAFF",
    "snow_crystal_edge_color": "#D8F4FF",
    "snow_crystal_ripple_color": "#E8FBFF",
    "snow_crystal_ripple_enabled": True,
    "snow_crystal_ripple_chance": 0.55,
    "snow_crystal_surface_y": 0.86,
    "bubble_enabled": False,
    "bubble_count": 42,
    "bubble_speed": 0.26,
    "bubble_size": 12.0,
    "bubble_alpha": 150,
    "water_drop_color": "#7DDCFF",
    "water_drop_edge_color": "#D2F8FF",
    "flame_core_color": "#FFF58C",
    "flame_mid_color": "#FF7823",
    "flame_edge_color": "#FF1E00",
    "water_spray_color": "#82E1FF",
    "water_spray_edge_color": "#D7FAFF",
    "fireball_core_color": "#FFFFBE",
    "fireball_mid_color": "#FF7828",
    "fireball_edge_color": "#AA1400",
    "fireball_trail_color": "#FF5A14",
    "flame_enabled": False,
    "flame_count": 60,
    "flame_speed": 0.55,
    "flame_size": 22.0,
    "flame_alpha": 210,
    "water_spray_enabled": False,
    "water_spray_count": 64,
    "water_spray_speed": 0.75,
    "water_spray_size": 6.0,
    "water_spray_alpha": 190,
    "fireball_enabled": False,
    "fireball_count": 10,
    "fireball_speed": 0.34,
    "fireball_size": 20.0,
    "fireball_alpha": 225,
    "shooting_star_enabled": False,
    "shooting_star_count": 3,
    "shooting_star_speed": 0.8,
    "shooting_star_size": 18.0,
    "shooting_star_alpha": 230,
    "meteor_shower_enabled": False,
    "meteor_shower_count": 18,
    "meteor_shower_speed": 0.9,
    "meteor_shower_size": 12.0,
    "meteor_shower_alpha": 220,
    "balloon_enabled": False,
    "balloon_count": 12,
    "balloon_speed": 0.20,
    "balloon_size": 34.0,
    "balloon_alpha": 220,
    "star_sky_enabled": False,
    "star_sky_count": 360,
    "star_sky_speed": 0.35,
    "star_sky_size": 1.6,
    "star_sky_alpha": 220,
    "star_sky_color": "#F8FBFF",
    "star_sky_secondary_color": "#BFD8FF",
    "milky_way_enabled": False,
    "milky_way_star_count": 220,
    "milky_way_alpha": 120,
    "milky_way_width": 0.22,
    "milky_way_angle": -18.0,
    "milky_way_color": "#BFD7FF",
    "water_surface_enabled": False,
    "water_surface_alpha": 92,
    "water_surface_color": "#4FC3FF",
    "water_surface_highlight_color": "#D8FAFF",
    "water_surface_flow_angle": 0.0,
    "water_surface_flow_speed": 0.55,
    "water_surface_wave_count": 14,
    "water_surface_wave_height": 12.0,
    "water_surface_y": 0.58,
    "water_surface_depth": 0.42,
    "water_depth_enabled": True,
    "water_depth_strength": 0.75,
    "water_depth_haze_alpha": 48,
    "water_depth_color": "#1A5B70",
    "water_morning_fog_enabled": True,
    "water_morning_fog_follow_sunrise": True,
    "water_morning_fog_strength": 0.65,
    "water_morning_fog_alpha": 95,
    "water_morning_fog_height": 0.22,
    "water_morning_fog_drift": 0.35,
    "water_morning_fog_color": "#E9F6FF",
    "water_fish_enabled": True,
    "water_fish_count": 4,
    "water_fish_speed": 0.28,
    "water_fish_size": 24.0,
    "water_fish_alpha": 175,
    "water_fish_color": "#7FE7D1",
    "water_fish_secondary_color": "#D8FFF3",
    "water_mirror_enabled": False,
    "water_mirror_alpha": 110,
    "water_mirror_blur": 5.0,
    "water_mirror_depth": 0.65,
    "water_mirror_wave": 7.0,
    "water_mirror_tint_alpha": 58,
    "water_mirror_reflect_effects_enabled": True,
    "water_mirror_reflect_widgets_enabled": True,
    "water_mirror_reflect_snow": True,
    "water_mirror_reflect_snow_crystal": True,
    "water_mirror_reflect_petals": True,
    "water_mirror_reflect_bamboo": True,
    "water_mirror_reflect_shooting_star": True,
    "water_mirror_reflect_meteor_shower": True,
    "water_mirror_reflect_rain": True,
    "puddle_enabled": False,
    "puddle_x": 0.50,
    "puddle_y": 0.84,
    "puddle_width": 0.72,
    "puddle_height": 0.22,
    "puddle_edge_softness": 0.18,
    "puddle_count": 5,
    "puddle_spread": 0.72,
    "puddles_json": "",
    "ice_enabled": False,
    "ice_lightweight_enabled": True,
    "ice_static_cache_enabled": True,
    "ice_quality_scale": 0.58,
    "ice_max_facets": 72,
    "ice_max_cracks": 16,
    "ice_max_bubbles": 34,
    "ice_skip_reflected_effect_frames": 2,
    "ice_mirror_skip_frames": 2,
    "ice_x": 0.50,
    "ice_width": 1.00,
    "ice_reflect_widgets_enabled": True,
    "ice_reflect_snow": True,
    "ice_reflect_snow_crystal": True,
    "ice_reflect_petals": True,
    "ice_reflect_bamboo": True,
    "ice_reflect_shooting_star": True,
    "ice_reflect_meteor_shower": True,
    "ice_reflect_rain": True,
    "ice_alpha": 178,
    "ice_color": "#9BDDF2",
    "ice_edge_color": "#E8FBFF",
    "ice_highlight_color": "#F7FFFF",
    "ice_shadow_color": "#2C6F93",
    "ice_fog_color": "#EEF9FF",
    "ice_size": 185.0,
    "ice_angle": -6.0,
    "ice_y": 0.58,
    "ice_depth": 0.42,
    "ice_crack_intensity": 0.46,
    "ice_internal_bubble_intensity": 0.36,
    "ice_glacier_roughness": 0.55,
    "ice_mirror_enabled": True,
    "ice_mirror_alpha": 118,
    "ice_mirror_blur": 3.5,
    "ice_mirror_depth": 0.68,
    "ice_mirror_wave": 2.2,
    "ice_mirror_tint_alpha": 70,
    "ice_reflect_effects_enabled": True,
    "ice_fog_enabled": True,
    "ice_fog_alpha": 72,
    "ice_fog_height": 0.24,
    "ice_fog_drift": 0.30,
    "bamboo_grove_enabled": False,
    "bamboo_count": 12,
    "bamboo_thickness": 16.0,
    "bamboo_angle": 0.0,
    "bamboo_bend": 0.32,
    "bamboo_height": 0.92,
    "bamboo_alpha": 230,
    "bamboo_leaf_density": 4,
    "bamboo_depth_strength": 0.85,
    "bamboo_layer_spread": 0.42,
    "bamboo_highlight_alpha": 96,
    "bamboo_ground_shadow_enabled": True,
    "bamboo_atmosphere_enabled": True,
    "bamboo_stalk_color": "#3EA65A",
    "bamboo_shadow_color": "#1F6F3B",
    "bamboo_node_color": "#B7E37A",
    "bamboo_leaf_color": "#5ED06C",
    "water_drop_enabled": False,
    "water_drop_count": 55,
    "water_drop_speed": 0.48,
    "water_drop_size": 8.0,
    "water_drop_alpha": 210,
    "water_drop_ripple_enabled": True,
    "water_drop_ripple_chance": 0.75,
    "water_drop_surface_y": 0.86,
    "sunrise_enabled": False,
    "sunrise_angle": 0.0,
    "sunrise_strength": 0.65,
    "sunrise_warmth": 0.72,
    "sunrise_horizon_y": 0.72,
    "sunrise_spread": 0.62,
    "sunrise_color_top": "#1B2C64",
    "sunrise_color_mid": "#FF8A5C",
    "sunrise_color_horizon": "#FFD08A",
    "sun_enabled": False,
    "sunlight_enabled": False,
    "lens_flare_enabled": False,
    "sun_x": 0.22,
    "sun_y": 0.22,
    "sun_radius": 82.0,
    "sun_alpha": 235,
    "sun_angle": 0.0,
    "sun_color": "#FFD36E",
    "sun_edge_color": "#FF7A3D",
    "sunlight_angle": 18.0,
    "sunlight_radius": 420.0,
    "sunlight_alpha": 92,
    "sunlight_beam_width": 0.38,
    "sunlight_color": "#FFD08A",
    "lens_flare_angle": 18.0,
    "lens_flare_alpha": 128,
    "lens_flare_size": 1.0,
    "lens_flare_count": 6,
    "lens_flare_color": "#FFE2A6",
    "moon_body_enabled": False,
    "moonlight_enabled": False,
    "moon_shadow_enabled": False,
    "moon_x": 0.78,
    "moon_y": 0.18,
    "moon_body_angle": 0.0,
    "moon_radius": 74.0,
    "moon_alpha": 230,
    "moon_color": "#FFF3C4",
    "moon_edge_color": "#C9D7FF",
    "moon_crater_count": 9,
    "moon_crater_alpha": 54,
    "moonlight_radius": 260.0,
    "moonlight_alpha": 82,
    "moonlight_color": "#CFE8FF",
    "moonlight_angle": 0.0,
    "moonlight_beam_enabled": True,
    "moonlight_beam_alpha": 44,
    "moonlight_beam_width": 0.34,
    "moon_shadow_alpha": 70,
    "moon_shadow_color": "#061028",
    "moon_shadow_offset_x": 28.0,
    "moon_shadow_offset_y": 38.0,
    "moon_shadow_angle": 0.0,
    "moon_shadow_blur_radius": 150.0,
}


class EffectsOverlayEditorDialog(QDialog):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        try:
            canvas = getattr(parent, "canvas", None)
            theme = get_canvas_studio_theme(canvas) if canvas is not None else DEFAULT_STUDIO_THEME
            self.setWindowOpacity(get_studio_window_opacity(theme))
        except Exception:
            try:
                self.setWindowOpacity(0.90)
            except Exception:
                pass
        from PySide6.QtWidgets import QTabWidget, QGroupBox

        self.widget = widget
        self.cfg = widget.cfg
        ensure_effect_overlay_fields(self.cfg)
        self.settings = get_effect_overlay_settings(self.cfg)

        self.setWindowTitle(lds_tr("Lite Desktop Studio v1.5.6 - エフェクト設定"))
        self.resize(760, 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        title = QLabel(lds_tr("✨ Effects Overlay - 初心者にも分かる設定"))
        title.setObjectName("BeginnerTitle")
        title.setStyleSheet("font-size: 20px; font-weight: 850;")
        outer.addWidget(title)
        try:
            apply_beginner_photoshop_settings_style(self, theme)
        except Exception:
            pass
        outer.addWidget(make_beginner_guide_label(
            lds_tr("まずはここだけ見ればOK"),
            lds_tr("上のプリセットを押すだけで雰囲気を一括変更できます。細かい数値は、見た目を少し変えたい時だけ調整してください。分からない項目は初期値のままで大丈夫です。")
        ))
        quick = QHBoxLayout()
        self.btn_all_on = QPushButton(lds_tr("✅ 全部ON"))
        self.btn_all_off = QPushButton(lds_tr("⛔ 全部OFF"))
        self.btn_rose_only = QPushButton(lds_tr("🌹 軽量: バラ花びらだけ"))
        self.btn_mouse_only = QPushButton(lds_tr("🖱️ マウス系だけON"))
        self.btn_ambient_only = QPushButton(lds_tr("🌿 環境系だけON"))
        self.btn_all_on.clicked.connect(self.set_all_on)
        self.btn_all_off.clicked.connect(self.set_all_off)
        self.btn_rose_only.clicked.connect(self.set_rose_petals_only)
        self.btn_mouse_only.clicked.connect(self.set_mouse_only)
        self.btn_ambient_only.clicked.connect(self.set_ambient_only)
        for b in [self.btn_all_on, self.btn_all_off, self.btn_rose_only, self.btn_mouse_only, self.btn_ambient_only]:
            quick.addWidget(b)
        set_beginner_tooltip(self.btn_all_on, lds_tr("すべての演出を一度にONにします。重くなる場合があります。"))
        set_beginner_tooltip(self.btn_all_off, lds_tr("すべての演出をOFFにします。画面を軽くしたい時に使います。"))
        set_beginner_tooltip(self.btn_rose_only, lds_tr("初心者におすすめ。軽めのバラ花びらだけを表示します。"))
        set_beginner_tooltip(self.btn_mouse_only, lds_tr("マウス操作に反応する効果だけをONにします。"))
        set_beginner_tooltip(self.btn_ambient_only, lds_tr("雨・粒子など背景演出を中心にONにします。"))
        outer.addLayout(quick)

        theme_title = QLabel(lds_tr("🎨 テーマプリセット"))
        theme_title.setStyleSheet("font-weight: 700; margin-top: 4px;")
        outer.addWidget(theme_title)
        theme_grid = QGridLayout()
        theme_grid.setHorizontalSpacing(6)
        theme_grid.setVerticalSpacing(6)
        self.theme_preset_buttons = []
        theme_presets = [
            ('🌙 ' + lds_tr("静かな夜空"), "quiet_night"),
            ('🌌 ' + lds_tr("月夜の水面"), "moonlit_water"),
            ('🌸 ' + lds_tr("春の花びら"), "spring_petals"),
            ('🎋 ' + lds_tr("竹林の小径"), "bamboo_path"),
            ('🌧 ' + lds_tr("雨と波紋"), "rain_ripples"),
            ('❄ ' + lds_tr("雪景色"), "snow_scene"),
            ('🧊 ' + lds_tr("氷河の鏡面"), "glacier_mirror"),
            ('☄ ' + lds_tr("流星群"), "meteor_sky"),
            ('🔥 ' + lds_tr("炎と水"), "fire_and_water"),
        ]
        for i, (label, theme_id) in enumerate(theme_presets):
            btn = QPushButton(label)
            set_beginner_tooltip(btn, lds_tr("このテーマに合う複数の効果をまとめて設定します。初心者はまずここから選ぶのがおすすめです。"))
            btn.clicked.connect(lambda checked=False, t=theme_id: self.apply_effect_theme(t))
            self.theme_preset_buttons.append(btn)
            theme_grid.addWidget(btn, i // 4, i % 4)
        outer.addLayout(theme_grid)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        self.basic_form = self._create_tab(lds_tr("基本"))
        self.rose_form = self._create_tab(lds_tr("バラ花びら"))
        self.rose_flower_form = self._create_tab(lds_tr("バラ花・開花"))
        self.rain_form = self._create_tab(lds_tr("雨・粒子"))
        self.sakura_form = self._create_tab(lds_tr("桜花びら"))
        self.ripple_form = self._create_tab(lds_tr("波紋・全体"))
        self.color_form = self._create_tab(lds_tr("色"))
        self.extra_weather_form = self._create_tab(lds_tr("雪・水・火"))
        self.extra_sky_form = self._create_tab(lds_tr("空・その他"))
        self.sunrise_form = self._create_tab(lds_tr("朝焼け・太陽"))
        self.moon_form = self._create_tab(lds_tr("月"))

        
        self.form = self.basic_form

        self._build_basic_tab()
        self._build_rose_tab()
        self._build_rose_flower_tab()
        self._build_rain_particle_tab()
        self._build_sakura_tab()
        self._build_ripple_global_tab()
        self._build_color_tab()
        self._build_extra_weather_tab()
        self._build_extra_sky_tab()
        self._build_sunrise_tab()
        self._build_moon_tab()

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_apply = QPushButton(lds_tr("💾 適用"))
        self.btn_ok = QPushButton(lds_tr("✅ OK"))
        self.btn_cancel = QPushButton(lds_tr("✖ キャンセル"))
        self.btn_apply.clicked.connect(self.apply_to_config)
        self.btn_ok.clicked.connect(self.accept_with_apply)
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(self.btn_apply)
        bottom.addWidget(self.btn_ok)
        bottom.addWidget(self.btn_cancel)
        outer.addLayout(bottom)

    def _pictogram_text(self, text):
        s = str(text or "")
        
        if s[:1] in "⚙️🌹🌺🌧️🌸💧🎨❄️🌌✨✅⛔🖱️🌿🌨️💦🫧🔥🚿☄️🌠🎈🔘🔢⚡📏🪟〰️🌊🎵📊🔊🕒📡📅🎧🧪🌐🌤️📚⬇⬆📌✏️🛠️💾✖🎚️🖌️🧊🌫️💡🧲🖱🎯🧩➕🪄🗂️🧭🔎📐↔️↕️🔤🖼️🧠💽🌍📶⬇️⬆️🧾":
            return s
        mapping = {
            
            lds_tr("基本"): "⚙️",
            lds_tr("バラ花びら"): "🌹",
            lds_tr("バラ花・開花"): "🌺",
            lds_tr("雨・粒子"): "🌧️",
            lds_tr("桜花びら"): "🌸",
            lds_tr("波紋・全体"): "💧",
            lds_tr("色"): "🎨",
            lds_tr("雪・水・火"): "❄️",
            lds_tr("空・その他"): "🌌",
            lds_tr("月"): "🌙",
            lds_tr("朝焼け・太陽"): "🌅",
            lds_tr("朝焼け"): "🌅",
            lds_tr("太陽"): "☀️",
            lds_tr("太陽光"): "🌞",
            lds_tr("レンズフレア"): "✨",
            lds_tr("月光"): "🌕",
            lds_tr("月影"): "🌘",
            lds_tr("月本体"): "🌝",

            
            lds_tr("雨粒"): "🌧️",
            lds_tr("パーティクル"): "✨",
            lds_tr("ノイズ"): "🌫️",
            lds_tr("グロー"): "💡",
            lds_tr("自動/通常 波紋"): "〰️",
            lds_tr("バラの花びら"): "🌹",
            lds_tr("中くらいのバラの花"): "🌺",
            lds_tr("大きな咲いた花が散る"): "🌺",
            lds_tr("桜の花びら"): "🌸",
            lds_tr("雪"): "🌨️",
            lds_tr("中くらいの雪の結晶"): "❄️",
            lds_tr("水玉"): "💧",
            lds_tr("泡"): "🫧",
            lds_tr("炎"): "🔥",
            lds_tr("水が吹き出る"): "🚿",
            lds_tr("火の玉"): "🔥",
            lds_tr("満天の星空"): "🌌",
            lds_tr("星空"): "🌌",
            lds_tr("天の川"): "🌌",
            lds_tr("竹林"): "🎋",
            lds_tr("竹"): "🎋",
            lds_tr("竹色"): "🎨",
            lds_tr("竹の影色"): "🎨",
            lds_tr("竹の節色"): "🎨",
            lds_tr("竹の葉色"): "🎨",
            lds_tr("星空色"): "🎨",
            lds_tr("星空サブ色"): "🎨",
            lds_tr("天の川色"): "🎨",
            lds_tr("流れ星"): "☄️",
            lds_tr("流星群"): "🌠",
            lds_tr("バルーン"): "🎈",

            
            lds_tr("雨粒が水面に当たったら波紋"): "🌧️",
            lds_tr("マウスクリック波紋"): "🖱️",
            lds_tr("マウス周辺から微粒子が逃げる"): "🧲",
            lds_tr("マウス周辺だけ光る"): "💡",
            lds_tr("花びらが水面に落ちたら波紋"): "🌹",
            lds_tr("水面に少し浮かべる"): "🌊",
            lds_tr("水面で花びらをフェードアウト"): "🌊",
            lds_tr("バラ花が水面に落ちたら波紋"): "🌺",
            lds_tr("咲いた花を再生成"): "🔄",
            lds_tr("桜花びらが水面で波紋"): "🌸",
            lds_tr("下に落ちた時に波紋"): "〰️",

            
            lds_tr("ON/OFF"): "🔘",
            lds_tr("数"): "🔢",
            lds_tr("速度"): "⚡",
            lds_tr("サイズ"): "📏",
            lds_tr("透明度"): "🪟",
            lds_tr("波紋"): "〰️",
            lds_tr("波紋発生率"): "💧",
            lds_tr("水面Y"): "🌊",
            lds_tr("水面"): "🌊",
            lds_tr("水面色"): "🎨",
            lds_tr("水面ハイライト色"): "🎨",
            lds_tr("流れ角度"): "🧭",
            lds_tr("流れ速度"): "⚡",
            lds_tr("波の本数"): "🔢",
            lds_tr("波の高さ"): "📏",
            lds_tr("水面の深さ"): "🌊",
            lds_tr("色"): "🎨",
            lds_tr("波紋色"): "💧",
            lds_tr("ノイズ色"): "🌫️",
            lds_tr("マウスグロー色"): "💡",
        }
        icon = mapping.get(s)
        return f"{icon} {s}" if icon else s

    def _add_beginner_tab_guides(self):
        """Add short, theme-aware beginner explanations to every settings tab."""
        guides = [
            (self.basic_form, lds_tr("基本"), lds_tr("効果を表示するかどうかを切り替える入口です。迷った時はプリセットボタンを使うと安全です。")),
            (self.rose_form, lds_tr("バラ花びら"), lds_tr("花びらの数・速さ・大きさを調整します。数を増やすほど華やかですが、パソコン負荷も上がります。")),
            (self.rose_flower_form, lds_tr("バラ花・開花"), lds_tr("大きめの花や開花演出を調整します。まずは数を少なめにすると見やすくなります。")),
            (self.rain_form, lds_tr("雨・粒子"), lds_tr("雨や小さな光の粒を調整します。重く感じたら数を減らしてください。")),
            (self.sakura_form, lds_tr("桜花びら"), lds_tr("桜の花びらの量や揺れ方を調整します。春らしい雰囲気を作る画面です。")),
            (self.ripple_form, lds_tr("波紋・全体"), lds_tr("波紋、マウス光、描画のなめらかさを調整します。GPUやFPSは分からなければ初期値がおすすめです。")),
            (self.color_form, lds_tr("色"), lds_tr("各効果の色を選べます。Photoshopの色指定のように、カラーコードを直接入力することもできます。")),
            (self.extra_weather_form, lds_tr("雪・水・火"), lds_tr("雪・泡・炎などの追加演出です。ONにする効果を少なめにすると安定しやすくなります。")),
            (self.extra_sky_form, lds_tr("空・その他"), lds_tr("星空・天の川・水面・竹林・氷など、背景の雰囲気を作る画面です。")),
            (self.sunrise_form, lds_tr("朝焼け・太陽"), lds_tr("朝焼け、太陽、光、レンズフレアを調整します。位置と透明度から触ると分かりやすいです。")),
            (self.moon_form, lds_tr("月"), lds_tr("月本体・月光・月影を調整します。X/Y位置で場所、半径で大きさを変えられます。")),
        ]
        for form, title, body in guides:
            try:
                form.addRow(make_beginner_guide_label(title, body))
            except Exception:
                pass

    def _create_tab(self, title):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setVerticalSpacing(8)
        self.tabs.addTab(page, self._pictogram_text(title))
        return form

    def _section(self, form, text):
        label = QLabel(self._pictogram_text(text))
        label.setObjectName("BeginnerSection")
        label.setStyleSheet("font-weight: 850; color: #80FFCC; margin-top: 10px;")
        form.addRow(label)
        return label

    def _double_spin(self, minimum, maximum, value, step):
        spin = QDoubleSpinBox()
        spin.setRange(float(minimum), float(maximum))
        spin.setDecimals(3)
        spin.setSingleStep(float(step))
        spin.setValue(float(value))
        return spin

    def _int_spin(self, minimum, maximum, value):
        spin = QSpinBox()
        spin.setRange(int(minimum), int(maximum))
        spin.setValue(int(value))
        return spin

    def _color_row_on(self, form, label, value):
        edit = QLineEdit(str(value or ""))
        button = QPushButton(lds_tr("🎨 選択"))
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(button)
        form.addRow(label, row_widget)

        def pick():
            color = QColorDialog.getColor(QColor(edit.text() or "#FFFFFF"), self, label)
            if color.isValid():
                edit.setText(color.name())

        button.clicked.connect(pick)
        return edit

    def _color_row(self, label, value):
        return self._color_row_on(self.form, label, value)

    def _build_basic_tab(self):
        f = self.basic_form
        self._section(f, lds_tr("表示するエフェクト"))
        self.rain_enabled = QCheckBox(lds_tr("雨粒"))
        self.particles_enabled = QCheckBox(lds_tr("パーティクル"))
        self.noise_enabled = QCheckBox(lds_tr("ノイズ"))
        self.glow_enabled = QCheckBox(lds_tr("グロー"))
        self.ripple_enabled = QCheckBox(lds_tr("自動/通常 波紋"))
        self.rose_petals_enabled = QCheckBox(lds_tr("バラの花びら"))
        self.rose_flowers_enabled = QCheckBox(lds_tr("中くらいのバラの花"))
        self.blooming_roses_enabled = QCheckBox(lds_tr("大きな咲いた花が散る"))
        self.sakura_petals_enabled = QCheckBox(lds_tr("桜の花びら"))
        self.sunrise_enabled = QCheckBox(lds_tr("朝焼け"))
        self.sun_enabled = QCheckBox(lds_tr("太陽"))
        self.sunlight_enabled = QCheckBox(lds_tr("太陽光"))
        self.lens_flare_enabled = QCheckBox(lds_tr("レンズフレア"))
        self.moon_body_enabled = QCheckBox(lds_tr("月本体"))
        self.moonlight_enabled = QCheckBox(lds_tr("月光"))
        self.moon_shadow_enabled = QCheckBox(lds_tr("月影"))
        self.rain_ripple_enabled = QCheckBox(lds_tr("雨粒が水面に当たったら波紋"))
        self.mouse_ripple_enabled = QCheckBox(lds_tr("マウスクリック波紋"))
        self.mouse_flee_enabled = QCheckBox(lds_tr("マウス周辺から微粒子が逃げる"))
        self.mouse_glow_enabled = QCheckBox(lds_tr("マウス周辺だけ光る"))

        self.rain_enabled.setChecked(self.settings.rain_enabled)
        self.particles_enabled.setChecked(self.settings.particles_enabled)
        self.noise_enabled.setChecked(self.settings.noise_enabled)
        self.glow_enabled.setChecked(self.settings.glow_enabled)
        self.ripple_enabled.setChecked(self.settings.ripple_enabled)
        self.rose_petals_enabled.setChecked(getattr(self.settings, "rose_petals_enabled", True))
        self.rose_flowers_enabled.setChecked(getattr(self.settings, "rose_flowers_enabled", False))
        self.blooming_roses_enabled.setChecked(getattr(self.settings, "blooming_roses_enabled", False))
        self.sakura_petals_enabled.setChecked(getattr(self.settings, "sakura_petals_enabled", False))
        self.sunrise_enabled.setChecked(getattr(self.settings, "sunrise_enabled", False))
        self.sun_enabled.setChecked(getattr(self.settings, "sun_enabled", False))
        self.sunlight_enabled.setChecked(getattr(self.settings, "sunlight_enabled", False))
        self.lens_flare_enabled.setChecked(getattr(self.settings, "lens_flare_enabled", False))
        self.moon_body_enabled.setChecked(getattr(self.settings, "moon_body_enabled", False))
        self.moonlight_enabled.setChecked(getattr(self.settings, "moonlight_enabled", False))
        self.moon_shadow_enabled.setChecked(getattr(self.settings, "moon_shadow_enabled", False))
        self.rain_ripple_enabled.setChecked(getattr(self.settings, "rain_ripple_enabled", False))
        self.mouse_ripple_enabled.setChecked(self.settings.mouse_ripple_enabled)
        self.mouse_flee_enabled.setChecked(self.settings.mouse_flee_enabled)
        self.mouse_glow_enabled.setChecked(self.settings.mouse_glow_enabled)

        f.addRow(lds_tr("バラ"), self.rose_petals_enabled)
        f.addRow(lds_tr("バラ花"), self.rose_flowers_enabled)
        f.addRow(lds_tr("開花バラ"), self.blooming_roses_enabled)
        f.addRow(lds_tr("桜"), self.sakura_petals_enabled)
        f.addRow(lds_tr("朝焼け"), self.sunrise_enabled)
        f.addRow(lds_tr("太陽"), self.sun_enabled)
        f.addRow(lds_tr("太陽光"), self.sunlight_enabled)
        f.addRow(lds_tr("レンズフレア"), self.lens_flare_enabled)
        f.addRow(lds_tr("月本体"), self.moon_body_enabled)
        f.addRow(lds_tr("月光"), self.moonlight_enabled)
        f.addRow(lds_tr("月影"), self.moon_shadow_enabled)
        f.addRow(lds_tr("雨"), self.rain_enabled)
        f.addRow(lds_tr("粒子"), self.particles_enabled)
        f.addRow(lds_tr("ノイズ"), self.noise_enabled)
        f.addRow(lds_tr("グロー"), self.glow_enabled)
        f.addRow(lds_tr("波紋"), self.ripple_enabled)
        f.addRow(lds_tr("雨×波紋"), self.rain_ripple_enabled)

        self._section(f, lds_tr("マウス連動"))
        f.addRow(lds_tr("クリック"), self.mouse_ripple_enabled)
        f.addRow(lds_tr("粒子逃避"), self.mouse_flee_enabled)
        f.addRow(lds_tr("マウス光"), self.mouse_glow_enabled)

        self._section(f, lds_tr("軽量プリセット"))
        note = QLabel(lds_tr("💡 重い場合は『🌹 軽量: バラ花びらだけ』を押すと、バラ花びら以外をOFFにします。"))
        note.setWordWrap(True)
        f.addRow(note)

    def _build_rose_tab(self):
        f = self.rose_form
        self._section(f, lds_tr("バラ花びら: 数量・動き"))
        self.rose_petal_count = self._int_spin(0, 500, getattr(self.settings, "rose_petal_count", 24))
        self.rose_petal_speed = self._double_spin(0.01, 300.0, getattr(self.settings, "rose_petal_speed", 0.35), 0.01)
        self.rose_petal_sway = self._double_spin(0.0, 5.0, getattr(self.settings, "rose_petal_sway", 1.0), 0.05)
        self.rose_petal_size = self._double_spin(2.0, 80.0, getattr(self.settings, "rose_petal_size", 16.0), 0.5)
        self.rose_petal_alpha = self._int_spin(0, 255, getattr(self.settings, "rose_petal_alpha", 210))
        f.addRow(lds_tr("花びら数"), self.rose_petal_count)
        f.addRow(lds_tr("落下速度"), self.rose_petal_speed)
        f.addRow(lds_tr("揺れ"), self.rose_petal_sway)
        f.addRow(lds_tr("サイズ"), self.rose_petal_size)
        f.addRow(lds_tr("透明度"), self.rose_petal_alpha)

        self._section(f, lds_tr("立体感"))
        self.rose_petal_roundness = self._double_spin(0.0, 1.0, getattr(self.settings, "rose_petal_roundness", 0.72), 0.01)
        self.rose_petal_curl = self._double_spin(0.0, 1.0, getattr(self.settings, "rose_petal_curl", 0.42), 0.01)
        self.rose_petal_shadow_alpha = self._int_spin(0, 255, getattr(self.settings, "rose_petal_shadow_alpha", 0))
        self.rose_petal_highlight_alpha = self._int_spin(0, 255, getattr(self.settings, "rose_petal_highlight_alpha", 115))
        self.rose_petal_vein_alpha = self._int_spin(0, 255, getattr(self.settings, "rose_petal_vein_alpha", 95))
        f.addRow(lds_tr("丸み"), self.rose_petal_roundness)
        f.addRow(lds_tr("カール"), self.rose_petal_curl)
        f.addRow(lds_tr("影"), self.rose_petal_shadow_alpha)
        f.addRow(lds_tr("ハイライト"), self.rose_petal_highlight_alpha)
        f.addRow(lds_tr("葉脈"), self.rose_petal_vein_alpha)

        self._section(f, lds_tr("花びら共通: 夜景・花吹雪"))
        self.petal_night_enabled = QCheckBox(lds_tr("夜景化する"))
        self.petal_night_enabled.setChecked(bool(getattr(self.settings, "petal_night_enabled", False)))
        self.petal_night_tint_color = self._color_row_on(f, lds_tr("夜景の影色"), getattr(self.settings, "petal_night_tint_color", "#101A3A"))
        self.petal_night_tint_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "petal_night_tint_strength", 0.35), 0.01)
        self.petal_shadow_enabled = QCheckBox(lds_tr("旧: 花びら影を使う"))
        self.petal_shadow_enabled.setChecked(bool(getattr(self.settings, "petal_shadow_enabled", False)))
        self.petal_outline_enabled = QCheckBox(lds_tr("花びらの輪郭を強調"))
        self.petal_outline_enabled.setChecked(bool(getattr(self.settings, "petal_outline_enabled", True)))
        self.petal_outline_strength = self._double_spin(0.5, 4.0, getattr(self.settings, "petal_outline_strength", 1.35), 0.05)
        self.petal_blizzard_enabled = QCheckBox(lds_tr("一定時間ごとの突風花吹雪"))
        self.petal_blizzard_enabled.setChecked(bool(getattr(self.settings, "petal_blizzard_enabled", False)))
        self.petal_wind_strength = self._double_spin(0.0, 3.0, getattr(self.settings, "petal_wind_strength", 1.0), 0.05)
        self.petal_wind_randomness = self._double_spin(0.0, 1.0, getattr(self.settings, "petal_wind_randomness", 0.55), 0.01)
        self.petal_gust_interval = self._double_spin(0.8, 300.0, getattr(self.settings, "petal_gust_interval", 4.0), 0.1)
        self.petal_gust_duration = self._double_spin(0.2, 300.0, getattr(self.settings, "petal_gust_duration", 1.15), 0.05)
        self.petal_gust_strength = self._double_spin(0.2, 200.0, getattr(self.settings, "petal_gust_strength", 1.45), 0.05)
        self.petal_mouse_flutter_enabled = QCheckBox(lds_tr("マウスで花びらを舞わせる"))
        self.petal_mouse_flutter_enabled.setChecked(bool(getattr(self.settings, "petal_mouse_flutter_enabled", True)))
        self.petal_mouse_flutter_strength = self._double_spin(0.0, 3.0, getattr(self.settings, "petal_mouse_flutter_strength", 1.0), 0.05)
        f.addRow(lds_tr("夜景"), self.petal_night_enabled)
        f.addRow(lds_tr("夜景の強さ"), self.petal_night_tint_strength)
        f.addRow(lds_tr("旧影"), self.petal_shadow_enabled)
        f.addRow(lds_tr("輪郭強調"), self.petal_outline_enabled)
        f.addRow(lds_tr("輪郭の強さ"), self.petal_outline_strength)
        f.addRow(lds_tr("突風花吹雪"), self.petal_blizzard_enabled)
        f.addRow(lds_tr("通常風の強さ"), self.petal_wind_strength)
        f.addRow(lds_tr("突風のランダム感"), self.petal_wind_randomness)
        f.addRow(lds_tr("突風間隔"), self.petal_gust_interval)
        f.addRow(lds_tr("突風時間"), self.petal_gust_duration)
        f.addRow(lds_tr("突風の強さ"), self.petal_gust_strength)
        f.addRow(lds_tr("マウス舞い"), self.petal_mouse_flutter_enabled)
        f.addRow(lds_tr("マウス舞い強さ"), self.petal_mouse_flutter_strength)

        self._section(f, lds_tr("水面・消え方"))
        self.rose_petal_surface_y = self._double_spin(0.0, 1.0, getattr(self.settings, "rose_petal_surface_y", 0.84), 0.01)
        self.rose_petal_ripple_enabled = QCheckBox(lds_tr("花びらが水面に落ちたら波紋"))
        self.rose_petal_ripple_enabled.setChecked(getattr(self.settings, "rose_petal_ripple_enabled", True))
        self.rose_petal_ripple_chance = self._double_spin(0.0, 1.0, getattr(self.settings, "rose_petal_ripple_chance", 0.9), 0.05)
        self.rose_petal_ripple_min_radius = self._double_spin(1.0, 400.0, getattr(self.settings, "rose_petal_ripple_min_radius", 36.0), 1.0)
        self.rose_petal_ripple_max_radius = self._double_spin(1.0, 700.0, getattr(self.settings, "rose_petal_ripple_max_radius", 130.0), 1.0)
        self.rose_petal_ripple_cooldown = self._double_spin(0.0, 1.0, getattr(self.settings, "rose_petal_ripple_cooldown", 0.04), 0.005)
        self.rose_petal_rest_on_surface = QCheckBox(lds_tr("水面に少し浮かべる"))
        self.rose_petal_rest_on_surface.setChecked(getattr(self.settings, "rose_petal_rest_on_surface", False))
        self.rose_petal_fade_on_surface = QCheckBox(lds_tr("水面で花びらをフェードアウト"))
        self.rose_petal_fade_on_surface.setChecked(getattr(self.settings, "rose_petal_fade_on_surface", True))
        self.rose_petal_fade_duration = self._double_spin(0.05, 5.0, getattr(self.settings, "rose_petal_fade_duration", 0.85), 0.05)
        self.rose_petal_fade_sink_distance = self._double_spin(0.0, 80.0, getattr(self.settings, "rose_petal_fade_sink_distance", 10.0), 1.0)
        self.rose_petal_fade_spin = self._double_spin(0.0, 2.0, getattr(self.settings, "rose_petal_fade_spin", 0.35), 0.05)
        f.addRow(lds_tr("水面Y"), self.rose_petal_surface_y)
        f.addRow(lds_tr("花びら×波紋"), self.rose_petal_ripple_enabled)
        f.addRow(lds_tr("波紋発生率"), self.rose_petal_ripple_chance)
        f.addRow(lds_tr("波紋最小半径"), self.rose_petal_ripple_min_radius)
        f.addRow(lds_tr("波紋最大半径"), self.rose_petal_ripple_max_radius)
        f.addRow(lds_tr("波紋間隔"), self.rose_petal_ripple_cooldown)
        f.addRow(lds_tr("浮かべる"), self.rose_petal_rest_on_surface)
        f.addRow(lds_tr("フェード"), self.rose_petal_fade_on_surface)
        f.addRow(lds_tr("フェード時間"), self.rose_petal_fade_duration)
        f.addRow(lds_tr("沈む距離"), self.rose_petal_fade_sink_distance)
        f.addRow(lds_tr("フェード中の回転"), self.rose_petal_fade_spin)

    def _build_rose_flower_tab(self):
        f = self.rose_flower_form
        self._section(f, lds_tr("中くらいのバラ花"))
        self.rose_flower_count = self._int_spin(0, 100, getattr(self.settings, "rose_flower_count", 5))
        self.rose_flower_size = self._double_spin(8.0, 160.0, getattr(self.settings, "rose_flower_size", 42.0), 1.0)
        self.rose_flower_speed = self._double_spin(0.01, 300.0, getattr(self.settings, "rose_flower_speed", 0.22), 0.01)
        self.rose_flower_sway = self._double_spin(0.0, 5.0, getattr(self.settings, "rose_flower_sway", 0.85), 0.05)
        self.rose_flower_surface_y = self._double_spin(0.0, 1.0, getattr(self.settings, "rose_flower_surface_y", 0.84), 0.01)
        self.rose_flower_ripple_enabled = QCheckBox(lds_tr("バラ花が水面に落ちたら波紋"))
        self.rose_flower_ripple_enabled.setChecked(getattr(self.settings, "rose_flower_ripple_enabled", True))
        self.rose_flower_ripple_min_radius = self._double_spin(1.0, 600.0, getattr(self.settings, "rose_flower_ripple_min_radius", 80.0), 1.0)
        self.rose_flower_ripple_max_radius = self._double_spin(1.0, 900.0, getattr(self.settings, "rose_flower_ripple_max_radius", 220.0), 1.0)
        f.addRow(lds_tr("バラ花数"), self.rose_flower_count)
        f.addRow(lds_tr("サイズ"), self.rose_flower_size)
        f.addRow(lds_tr("落下速度"), self.rose_flower_speed)
        f.addRow(lds_tr("揺れ"), self.rose_flower_sway)
        f.addRow(lds_tr("水面Y"), self.rose_flower_surface_y)
        f.addRow(lds_tr("波紋"), self.rose_flower_ripple_enabled)
        f.addRow(lds_tr("波紋最小半径"), self.rose_flower_ripple_min_radius)
        f.addRow(lds_tr("波紋最大半径"), self.rose_flower_ripple_max_radius)

        self._section(f, lds_tr("咲いたバラ"))
        self.blooming_rose_count = self._int_spin(0, 20, getattr(self.settings, "blooming_rose_count", 2))
        self.blooming_rose_size = self._double_spin(20.0, 260.0, getattr(self.settings, "blooming_rose_size", 86.0), 1.0)
        self.blooming_rose_scatter_after = self._double_spin(0.1, 30.0, getattr(self.settings, "blooming_rose_scatter_after", 3.0), 0.1)
        self.blooming_rose_life = self._double_spin(0.2, 60.0, getattr(self.settings, "blooming_rose_life", 7.5), 0.1)
        self.blooming_rose_petal_count = self._int_spin(0, 300, getattr(self.settings, "blooming_rose_petal_count", 34))
        self.blooming_rose_respawn = QCheckBox(lds_tr("咲いた花を再生成"))
        self.blooming_rose_respawn.setChecked(getattr(self.settings, "blooming_rose_respawn", True))
        f.addRow(lds_tr("咲いた花数"), self.blooming_rose_count)
        f.addRow(lds_tr("咲いた花サイズ"), self.blooming_rose_size)
        f.addRow(lds_tr("散り始め"), self.blooming_rose_scatter_after)
        f.addRow(lds_tr("寿命"), self.blooming_rose_life)
        f.addRow(lds_tr("散る花びら数"), self.blooming_rose_petal_count)
        f.addRow(lds_tr("再生成"), self.blooming_rose_respawn)

    def _build_rain_particle_tab(self):
        f = self.rain_form
        self._section(f, lds_tr("数量"))
        self.particle_count = self._int_spin(0, 2000, self.settings.particle_count)
        self.rain_count = self._int_spin(0, 2000, self.settings.rain_count)
        self.glow_count = self._int_spin(0, 32, self.settings.glow_count)
        f.addRow(lds_tr("パーティクル数"), self.particle_count)
        f.addRow(lds_tr("雨粒数"), self.rain_count)
        f.addRow(lds_tr("グロー数"), self.glow_count)

        self._section(f, lds_tr("速度・サイズ"))
        self.particle_speed = self._double_spin(0.0, 300.0, self.settings.particle_speed, 0.05)
        self.rain_speed = self._double_spin(0.0, 10.0, self.settings.rain_speed, 0.05)
        self.rain_drop_min_size = self._double_spin(0.2, 20.0, getattr(self.settings, "rain_drop_min_size", 1.0), 0.1)
        self.rain_drop_max_size = self._double_spin(0.2, 300.0, getattr(self.settings, "rain_drop_max_size", 2.4), 0.1)
        self.rain_drop_length_randomness = self._double_spin(0.0, 2.0, getattr(self.settings, "rain_drop_length_randomness", 0.55), 0.05)
        self.particle_size = self._double_spin(0.1, 20.0, self.settings.particle_size, 0.1)
        self.rain_length = self._double_spin(1.0, 120.0, self.settings.rain_length, 1.0)
        self.glow_speed = self._double_spin(0.0, 10.0, self.settings.glow_speed, 0.05)
        self.glow_radius = self._double_spin(10.0, 600.0, self.settings.glow_radius, 5.0)
        f.addRow(lds_tr("粒子速度"), self.particle_speed)
        f.addRow(lds_tr("粒子サイズ"), self.particle_size)
        f.addRow(lds_tr("雨速度"), self.rain_speed)
        f.addRow(lds_tr("雨粒の最小太さ"), self.rain_drop_min_size)
        f.addRow(lds_tr("雨粒の最大太さ"), self.rain_drop_max_size)
        f.addRow(lds_tr("雨粒の長さランダム"), self.rain_drop_length_randomness)
        f.addRow(lds_tr("雨の長さ"), self.rain_length)
        f.addRow(lds_tr("グロー速度"), self.glow_speed)
        f.addRow(lds_tr("グロー半径"), self.glow_radius)

    def _build_sakura_tab(self):
        f = self.sakura_form
        self._section(f, lds_tr("桜花びら"))
        self.sakura_petal_count = self._int_spin(0, 2000, getattr(self.settings, "sakura_petal_count", 80))
        self.sakura_petal_speed = self._double_spin(0.01, 300.0, getattr(self.settings, "sakura_petal_speed", 0.32), 0.01)
        self.sakura_petal_sway = self._double_spin(0.0, 300.0, getattr(self.settings, "sakura_petal_sway", 1.15), 0.05)
        self.sakura_petal_size = self._double_spin(1.0, 300.0, getattr(self.settings, "sakura_petal_size", 9.0), 0.5)
        self.sakura_petal_surface_y = self._double_spin(0.0, 1.0, getattr(self.settings, "sakura_petal_surface_y", 0.84), 0.01)
        self.sakura_petal_ripple_enabled = QCheckBox(lds_tr("桜花びらが水面で波紋"))
        self.sakura_petal_ripple_enabled.setChecked(getattr(self.settings, "sakura_petal_ripple_enabled", True))
        self.sakura_petal_ripple_chance = self._double_spin(0.0, 1.0, getattr(self.settings, "sakura_petal_ripple_chance", 0.65), 0.05)
        self.sakura_petal_ripple_min_radius = self._double_spin(1.0, 300.0, getattr(self.settings, "sakura_petal_ripple_min_radius", 22.0), 1.0)
        self.sakura_petal_ripple_max_radius = self._double_spin(1.0, 500.0, getattr(self.settings, "sakura_petal_ripple_max_radius", 88.0), 1.0)
        f.addRow(lds_tr("桜花びら数"), self.sakura_petal_count)
        f.addRow(lds_tr("速度"), self.sakura_petal_speed)
        f.addRow(lds_tr("揺れ"), self.sakura_petal_sway)
        f.addRow(lds_tr("サイズ"), self.sakura_petal_size)
        f.addRow(lds_tr("水面Y"), self.sakura_petal_surface_y)
        f.addRow(lds_tr("波紋"), self.sakura_petal_ripple_enabled)
        f.addRow(lds_tr("波紋発生率"), self.sakura_petal_ripple_chance)
        f.addRow(lds_tr("波紋最小半径"), self.sakura_petal_ripple_min_radius)
        f.addRow(lds_tr("波紋最大半径"), self.sakura_petal_ripple_max_radius)

    def _build_ripple_global_tab(self):
        f = self.ripple_form
        self._section(f, lds_tr("雨波紋"))
        self.rain_ripple_chance = self._double_spin(0.0, 1.0, getattr(self.settings, "rain_ripple_chance", 0.55), 0.05)
        self.rain_ripple_surface_y = self._double_spin(0.0, 1.0, getattr(self.settings, "rain_ripple_surface_y", 0.82), 0.01)
        self.rain_ripple_min_radius = self._double_spin(1.0, 300.0, getattr(self.settings, "rain_ripple_min_radius", 24.0), 1.0)
        self.rain_ripple_max_radius_linked = self._double_spin(1.0, 500.0, getattr(self.settings, "rain_ripple_max_radius_linked", 92.0), 1.0)
        self.rain_ripple_cooldown = self._double_spin(0.0, 1.0, getattr(self.settings, "rain_ripple_cooldown", 0.025), 0.005)
        f.addRow(lds_tr("雨波紋の発生率"), self.rain_ripple_chance)
        f.addRow(lds_tr("水面Y位置"), self.rain_ripple_surface_y)
        f.addRow(lds_tr("雨波紋の最小半径"), self.rain_ripple_min_radius)
        f.addRow(lds_tr("雨波紋の最大半径"), self.rain_ripple_max_radius_linked)
        f.addRow(lds_tr("雨波紋の間隔"), self.rain_ripple_cooldown)

        self._section(f, lds_tr("全体"))
        self.ripple_speed = self._double_spin(0.05, 300.0, self.settings.ripple_speed, 0.05)
        self.ripple_max_radius = self._double_spin(10.0, 800.0, self.settings.ripple_max_radius, 5.0)
        self.mouse_glow_radius = self._double_spin(10.0, 600.0, self.settings.mouse_glow_radius, 5.0)
        self.intensity = self._double_spin(0.0, 5.0, self.settings.intensity, 0.05)
        self.noise_alpha = self._int_spin(0, 255, self.settings.noise_alpha)
        self.background_alpha = self._int_spin(0, 255, self.settings.background_alpha)
        self.gpu_acceleration_enabled = QCheckBox(lds_tr("GPU支援描画を使う（利用可能な場合）"))
        self.gpu_acceleration_enabled.setChecked(bool(getattr(self.settings, "gpu_acceleration_enabled", True)))
        set_beginner_tooltip(self.gpu_acceleration_enabled, lds_tr("パソコンが対応していれば描画をなめらかにします。分からない場合はONのままで大丈夫です。"))
        self.gpu_acceleration_prefer_opengl = QCheckBox(lds_tr("OpenGL/RHIを優先"))
        self.gpu_acceleration_prefer_opengl.setChecked(bool(getattr(self.settings, "gpu_acceleration_prefer_opengl", True)))
        set_beginner_tooltip(self.gpu_acceleration_prefer_opengl, lds_tr("描画方式の優先設定です。画面が乱れる時以外は変更しなくて大丈夫です。"))
        self.gpu_acceleration_smooth_pixmaps = QCheckBox(lds_tr("GPU向け画像補間を有効化"))
        self.gpu_acceleration_smooth_pixmaps.setChecked(bool(getattr(self.settings, "gpu_acceleration_smooth_pixmaps", True)))
        set_beginner_tooltip(self.gpu_acceleration_smooth_pixmaps, lds_tr("画像や反射をなめらかに見せる設定です。重い時はOFFを試してください。"))
        self.effect_frame_rate_enabled = QCheckBox(lds_tr("エフェクトFPS制限を使う"))
        self.effect_frame_rate_enabled.setChecked(bool(getattr(self.settings, "effect_frame_rate_enabled", True)))
        set_beginner_tooltip(self.effect_frame_rate_enabled, lds_tr("動きの上限を決めて、パソコンへの負荷を抑えます。"))
        self.effect_frame_rate = self._int_spin(1, 240, getattr(self.settings, "effect_frame_rate", 60))
        self.gpu_status_label = QLabel(effect_gpu_status_text())
        self.gpu_status_label.setWordWrap(True)
        f.addRow(lds_tr("波紋速度"), self.ripple_speed)
        f.addRow(lds_tr("波紋最大半径"), self.ripple_max_radius)
        f.addRow(lds_tr("マウスグロー半径"), self.mouse_glow_radius)
        f.addRow(lds_tr("全体強度"), self.intensity)
        f.addRow(lds_tr("ノイズ濃度"), self.noise_alpha)
        f.addRow(lds_tr("背景不透明度"), self.background_alpha)
        f.addRow(lds_tr("GPU支援描画"), self.gpu_acceleration_enabled)
        f.addRow(lds_tr("GPUバックエンド優先"), self.gpu_acceleration_prefer_opengl)
        f.addRow(lds_tr("画像補間"), self.gpu_acceleration_smooth_pixmaps)
        f.addRow(lds_tr("エフェクトFPS制限"), self.effect_frame_rate_enabled)
        f.addRow(lds_tr("エフェクトFPS"), self.effect_frame_rate)
        f.addRow(lds_tr("GPU状態"), self.gpu_status_label)

    def _build_color_tab(self):
        f = self.color_form
        self._section(f, lds_tr("バラ"))
        self.rose_petal_color = self._color_row_on(f, lds_tr("花びら色"), getattr(self.settings, "rose_petal_color", "#FF7AAE"))
        self.rose_petal_edge_color = self._color_row_on(f, lds_tr("花びら縁色"), getattr(self.settings, "rose_petal_edge_color", "#FFD1E3"))
        self.blooming_rose_color = self._color_row_on(f, lds_tr("咲いた花色"), getattr(self.settings, "blooming_rose_color", "#FF6FAE"))
        self.blooming_rose_edge_color = self._color_row_on(f, lds_tr("咲いた花縁色"), getattr(self.settings, "blooming_rose_edge_color", "#FFD5E8"))

        self._section(f, lds_tr("桜"))
        self.sakura_petal_color = self._color_row_on(f, lds_tr("桜花びら色"), getattr(self.settings, "sakura_petal_color", "#FFD1E8"))
        self.sakura_petal_edge_color = self._color_row_on(f, lds_tr("桜花びら縁色"), getattr(self.settings, "sakura_petal_edge_color", "#FF8FC7"))

        self._section(f, lds_tr("雪"))
        self.snow_color = self._color_row_on(f, lds_tr("雪の色"), getattr(self.settings, "snow_color", "#F5FCFF"))
        self.snow_edge_color = self._color_row_on(f, lds_tr("雪の縁色"), getattr(self.settings, "snow_edge_color", "#CFEFFF"))
        self.snow_ripple_color = self._color_row_on(f, lds_tr("雪の波紋色"), getattr(self.settings, "snow_ripple_color", "#DFFBFF"))
        self.snow_crystal_color = self._color_row_on(f, lds_tr("雪の結晶色"), getattr(self.settings, "snow_crystal_color", "#EBFAFF"))
        self.snow_crystal_edge_color = self._color_row_on(f, lds_tr("雪の結晶縁色"), getattr(self.settings, "snow_crystal_edge_color", "#D8F4FF"))
        self.snow_crystal_ripple_color = self._color_row_on(f, lds_tr("雪の結晶波紋色"), getattr(self.settings, "snow_crystal_ripple_color", "#E8FBFF"))

        self._section(f, lds_tr("水・火"))
        self.water_drop_color = self._color_row_on(f, lds_tr("水玉色"), getattr(self.settings, "water_drop_color", "#7DDCFF"))
        self.water_drop_edge_color = self._color_row_on(f, lds_tr("水玉縁色"), getattr(self.settings, "water_drop_edge_color", "#D2F8FF"))
        self.flame_core_color = self._color_row_on(f, lds_tr("炎の中心色"), getattr(self.settings, "flame_core_color", "#FFF58C"))
        self.flame_mid_color = self._color_row_on(f, lds_tr("炎の中間色"), getattr(self.settings, "flame_mid_color", "#FF7823"))
        self.flame_edge_color = self._color_row_on(f, lds_tr("炎の外側色"), getattr(self.settings, "flame_edge_color", "#FF1E00"))
        self.water_spray_color = self._color_row_on(f, lds_tr("水の吹き出し色"), getattr(self.settings, "water_spray_color", "#82E1FF"))
        self.water_spray_edge_color = self._color_row_on(f, lds_tr("水の吹き出し縁色"), getattr(self.settings, "water_spray_edge_color", "#D7FAFF"))
        self.water_surface_color = self._color_row_on(f, lds_tr("水面色"), getattr(self.settings, "water_surface_color", "#4FC3FF"))
        self.water_surface_highlight_color = self._color_row_on(f, lds_tr("水面ハイライト色"), getattr(self.settings, "water_surface_highlight_color", "#D8FAFF"))
        self.water_depth_color = self._color_row_on(f, lds_tr("水面奥行き色"), getattr(self.settings, "water_depth_color", "#1A5B70"))
        self.water_morning_fog_color = self._color_row_on(f, lds_tr("朝もや色"), getattr(self.settings, "water_morning_fog_color", "#E9F6FF"))
        self.water_fish_color = self._color_row_on(f, lds_tr("魚の色"), getattr(self.settings, "water_fish_color", "#7FE7D1"))
        self.water_fish_secondary_color = self._color_row_on(f, lds_tr("魚のハイライト色"), getattr(self.settings, "water_fish_secondary_color", "#D8FFF3"))
        self.fireball_core_color = self._color_row_on(f, lds_tr("火の玉中心色"), getattr(self.settings, "fireball_core_color", "#FFFFBE"))
        self.fireball_mid_color = self._color_row_on(f, lds_tr("火の玉中間色"), getattr(self.settings, "fireball_mid_color", "#FF7828"))
        self.fireball_edge_color = self._color_row_on(f, lds_tr("火の玉外側色"), getattr(self.settings, "fireball_edge_color", "#AA1400"))
        self.fireball_trail_color = self._color_row_on(f, lds_tr("火の玉の尾色"), getattr(self.settings, "fireball_trail_color", "#FF5A14"))

        self._section(f, lds_tr("星空・天の川"))
        self.star_sky_color = self._color_row_on(f, lds_tr("星空色"), getattr(self.settings, "star_sky_color", "#F8FBFF"))
        self.star_sky_secondary_color = self._color_row_on(f, lds_tr("星空サブ色"), getattr(self.settings, "star_sky_secondary_color", "#BFD8FF"))
        self.milky_way_color = self._color_row_on(f, lds_tr("天の川色"), getattr(self.settings, "milky_way_color", "#BFD7FF"))

        self._section(f, lds_tr("竹林"))
        self.bamboo_stalk_color = self._color_row_on(f, lds_tr("竹色"), getattr(self.settings, "bamboo_stalk_color", "#3EA65A"))
        self.bamboo_shadow_color = self._color_row_on(f, lds_tr("竹の影色"), getattr(self.settings, "bamboo_shadow_color", "#1F6F3B"))
        self.bamboo_node_color = self._color_row_on(f, lds_tr("竹の節色"), getattr(self.settings, "bamboo_node_color", "#B7E37A"))
        self.bamboo_leaf_color = self._color_row_on(f, lds_tr("竹の葉色"), getattr(self.settings, "bamboo_leaf_color", "#5ED06C"))

        self._section(f, lds_tr("環境"))
        self.particle_color = self._color_row_on(f, lds_tr("粒子色"), self.settings.particle_color)
        self.rain_color = self._color_row_on(f, lds_tr("雨色"), self.settings.rain_color)
        self.glow_color = self._color_row_on(f, lds_tr("グロー色"), self.settings.glow_color)
        self.ripple_color = self._color_row_on(f, self._pictogram_text(lds_tr("波紋色")), self.settings.ripple_color)
        self.noise_color = self._color_row_on(f, self._pictogram_text(lds_tr("ノイズ色")), self.settings.noise_color)
        self.mouse_glow_color = self._color_row_on(f, self._pictogram_text(lds_tr("マウスグロー色")), self.settings.mouse_glow_color)


    def _add_effect_block(self, form, title, prefix, label, count_default, speed_default, size_default, alpha_default, ripple=False, surface_default=0.86, chance_default=0.5):
        self._section(form, title)
        enabled = QCheckBox(self._pictogram_text(label))
        enabled.setChecked(bool(getattr(self.settings, f"{prefix}_enabled", False)))
        count = self._int_spin(0, 500, getattr(self.settings, f"{prefix}_count", count_default))
        speed = self._double_spin(0.01, 5.0, getattr(self.settings, f"{prefix}_speed", speed_default), 0.01)
        size = self._double_spin(1.0, 160.0, getattr(self.settings, f"{prefix}_size", size_default), 0.5)
        alpha = self._int_spin(0, 255, getattr(self.settings, f"{prefix}_alpha", alpha_default))
        setattr(self, f"{prefix}_enabled", enabled)
        setattr(self, f"{prefix}_count", count)
        setattr(self, f"{prefix}_speed", speed)
        setattr(self, f"{prefix}_size", size)
        setattr(self, f"{prefix}_alpha", alpha)
        form.addRow(self._pictogram_text("ON/OFF"), enabled)
        form.addRow(self._pictogram_text(lds_tr("数")), count)
        form.addRow(self._pictogram_text(lds_tr("速度")), speed)
        form.addRow(self._pictogram_text(lds_tr("サイズ")), size)
        form.addRow(self._pictogram_text(lds_tr("透明度")), alpha)
        if ripple:
            ripple_enabled = QCheckBox(lds_tr("下に落ちた時に波紋"))
            ripple_enabled.setChecked(bool(getattr(self.settings, f"{prefix}_ripple_enabled", True)))
            chance = self._double_spin(0.0, 1.0, getattr(self.settings, f"{prefix}_ripple_chance", chance_default), 0.05)
            surface = self._double_spin(0.0, 1.0, getattr(self.settings, f"{prefix}_surface_y", surface_default), 0.01)
            setattr(self, f"{prefix}_ripple_enabled", ripple_enabled)
            setattr(self, f"{prefix}_ripple_chance", chance)
            setattr(self, f"{prefix}_surface_y", surface)
            form.addRow(self._pictogram_text(lds_tr("波紋")), ripple_enabled)
            form.addRow(self._pictogram_text(lds_tr("波紋発生率")), chance)
            form.addRow(self._pictogram_text(lds_tr("水面Y")), surface)

    def _build_extra_weather_tab(self):
        f = self.extra_weather_form
        self._add_effect_block(f, lds_tr("雪"), "snow", lds_tr("小さな雪がゆっくり落ちる"), 90, 0.18, 4.5, 210, ripple=True, surface_default=0.86, chance_default=0.38)
        self._section(f, lds_tr("雪の積雪"))
        self.snow_accumulation_enabled = QCheckBox(lds_tr("雪が徐々に積もる"))
        self.snow_accumulation_enabled.setChecked(bool(getattr(self.settings, "snow_accumulation_enabled", False)))
        self.snow_accumulation_start_y = self._double_spin(0.0, 1.0, getattr(self.settings, "snow_accumulation_start_y", 1.0), 0.01)
        self.snow_accumulation_max_depth = self._double_spin(0.05, 1.0, getattr(self.settings, "snow_accumulation_max_depth", 1.0), 0.01)
        self.snow_accumulation_build_rate = self._double_spin(0.0, 120.0, getattr(self.settings, "snow_accumulation_build_rate", 7.0), 0.5)
        self.snow_accumulation_column_width = self._double_spin(2.0, 30.0, getattr(self.settings, "snow_accumulation_column_width", 7.0), 0.5)
        self.snow_accumulation_alpha = self._int_spin(0, 255, getattr(self.settings, "snow_accumulation_alpha", 230))
        self.snow_accumulation_mouse_remove_enabled = QCheckBox(lds_tr("マウスで積雪を除去"))
        self.snow_accumulation_mouse_remove_enabled.setChecked(bool(getattr(self.settings, "snow_accumulation_mouse_remove_enabled", True)))
        self.snow_accumulation_remove_radius = self._double_spin(4.0, 300.0, getattr(self.settings, "snow_accumulation_remove_radius", 58.0), 2.0)
        self.snow_accumulation_remove_strength = self._double_spin(1.0, 400.0, getattr(self.settings, "snow_accumulation_remove_strength", 72.0), 2.0)
        f.addRow(lds_tr("積雪"), self.snow_accumulation_enabled)
        f.addRow(lds_tr("積雪開始Y"), self.snow_accumulation_start_y)
        f.addRow(lds_tr("最大積雪量"), self.snow_accumulation_max_depth)
        f.addRow(lds_tr("積もる速度"), self.snow_accumulation_build_rate)
        f.addRow(lds_tr("積雪解像度"), self.snow_accumulation_column_width)
        f.addRow(lds_tr("積雪透明度"), self.snow_accumulation_alpha)
        f.addRow(lds_tr("マウス除雪"), self.snow_accumulation_mouse_remove_enabled)
        f.addRow(lds_tr("除雪半径"), self.snow_accumulation_remove_radius)
        f.addRow(lds_tr("除雪強さ"), self.snow_accumulation_remove_strength)
        self._add_effect_block(f, lds_tr("中くらいの雪の結晶"), "snow_crystal", lds_tr("雪の結晶がゆっくり落ちる"), 22, 0.12, 15.0, 220, ripple=True, surface_default=0.86, chance_default=0.55)
        self._add_effect_block(f, lds_tr("水玉"), "water_drop", lds_tr("水玉が上から落ちる"), 55, 0.48, 8.0, 210, ripple=True, surface_default=0.86, chance_default=0.75)
        self._add_effect_block(f, lds_tr("泡"), "bubble", lds_tr("泡が下からポコポコ登る"), 42, 0.26, 12.0, 150, ripple=False)
        self._add_effect_block(f, lds_tr("炎"), "flame", lds_tr("下から炎がゆらめく"), 60, 0.55, 22.0, 210, ripple=False)
        self._add_effect_block(f, lds_tr("水が吹き出る"), "water_spray", lds_tr("下から水が噴き上がる"), 64, 0.75, 6.0, 190, ripple=False)

    def _build_extra_sky_tab(self):
        f = self.extra_sky_form
        self._add_effect_block(f, lds_tr("火の玉"), "fireball", lds_tr("火の玉がゆらゆら上から降りる"), 10, 0.34, 20.0, 225, ripple=False)
        self._add_effect_block(f, lds_tr("満天の星空"), "star_sky", lds_tr("遠くで小さくキラキラ光る星"), 360, 0.35, 1.6, 220, ripple=False)
        self._section(f, lds_tr("天の川"))
        self.milky_way_enabled = QCheckBox(lds_tr("天の川を描画"))
        self.milky_way_enabled.setChecked(bool(getattr(self.settings, "milky_way_enabled", False)))
        self.milky_way_star_count = self._int_spin(0, 2000, getattr(self.settings, "milky_way_star_count", 220))
        self.milky_way_alpha = self._int_spin(0, 255, getattr(self.settings, "milky_way_alpha", 120))
        self.milky_way_width = self._double_spin(0.02, 1.0, getattr(self.settings, "milky_way_width", 0.22), 0.01)
        self.milky_way_angle = self._double_spin(-180.0, 180.0, getattr(self.settings, "milky_way_angle", -18.0), 1.0)
        f.addRow(lds_tr("天の川"), self.milky_way_enabled)
        f.addRow(lds_tr("天の川の星数"), self.milky_way_star_count)
        f.addRow(lds_tr("天の川透明度"), self.milky_way_alpha)
        f.addRow(lds_tr("天の川幅"), self.milky_way_width)
        f.addRow(lds_tr("天の川角度"), self.milky_way_angle)

        self._section(f, lds_tr("水面"))
        self.water_surface_enabled = QCheckBox(lds_tr("水面を描画"))
        self.water_surface_enabled.setChecked(bool(getattr(self.settings, "water_surface_enabled", False)))
        self.puddle_enabled = QCheckBox(lds_tr("水たまり（横長の楕円で水面を限定）"))
        self.puddle_enabled.setChecked(bool(getattr(self.settings, "puddle_enabled", False)))
        self.puddle_x = self._double_spin(0.0, 1.0, getattr(self.settings, "puddle_x", 0.50), 0.01)
        self.puddle_y = self._double_spin(0.0, 1.0, getattr(self.settings, "puddle_y", 0.84), 0.01)
        self.puddle_width = self._double_spin(0.05, 1.20, getattr(self.settings, "puddle_width", 0.72), 0.01)
        self.puddle_height = self._double_spin(0.02, 0.70, getattr(self.settings, "puddle_height", 0.22), 0.01)
        self.puddle_edge_softness = self._double_spin(0.0, 1.0, getattr(self.settings, "puddle_edge_softness", 0.18), 0.01)
        self.puddle_count = self._int_spin(1, 12, getattr(self.settings, "puddle_count", 5))
        self.puddle_spread = self._double_spin(0.0, 1.0, getattr(self.settings, "puddle_spread", 0.72), 0.01)
        self.water_surface_alpha = self._int_spin(0, 255, getattr(self.settings, "water_surface_alpha", 92))
        self.water_surface_flow_angle = self._double_spin(-180.0, 180.0, getattr(self.settings, "water_surface_flow_angle", 0.0), 1.0)
        self.water_surface_flow_speed = self._double_spin(0.0, 300.0, getattr(self.settings, "water_surface_flow_speed", 0.55), 0.01)
        self.water_surface_wave_count = self._int_spin(0, 120, getattr(self.settings, "water_surface_wave_count", 14))
        self.water_surface_wave_height = self._double_spin(0.0, 80.0, getattr(self.settings, "water_surface_wave_height", 12.0), 0.5)
        self.water_surface_y = self._double_spin(0.0, 1.0, getattr(self.settings, "water_surface_y", 0.58), 0.01)
        self.water_surface_depth = self._double_spin(0.05, 1.0, getattr(self.settings, "water_surface_depth", 0.42), 0.01)
        self.water_depth_enabled = QCheckBox(lds_tr("水面に奥行きを追加"))
        self.water_depth_enabled.setChecked(bool(getattr(self.settings, "water_depth_enabled", True)))
        self.water_depth_strength = self._double_spin(0.0, 2.0, getattr(self.settings, "water_depth_strength", 0.75), 0.01)
        self.water_depth_haze_alpha = self._int_spin(0, 255, getattr(self.settings, "water_depth_haze_alpha", 48))
        self.water_morning_fog_enabled = QCheckBox(lds_tr("朝もや/霧を水面に追加"))
        self.water_morning_fog_enabled.setChecked(bool(getattr(self.settings, "water_morning_fog_enabled", True)))
        self.water_morning_fog_follow_sunrise = QCheckBox(lds_tr("朝焼けON時のみ"))
        self.water_morning_fog_follow_sunrise.setChecked(bool(getattr(self.settings, "water_morning_fog_follow_sunrise", True)))
        self.water_morning_fog_strength = self._double_spin(0.0, 2.0, getattr(self.settings, "water_morning_fog_strength", 0.65), 0.01)
        self.water_morning_fog_alpha = self._int_spin(0, 255, getattr(self.settings, "water_morning_fog_alpha", 95))
        self.water_morning_fog_height = self._double_spin(0.05, 0.60, getattr(self.settings, "water_morning_fog_height", 0.22), 0.01)
        self.water_morning_fog_drift = self._double_spin(0.0, 3.0, getattr(self.settings, "water_morning_fog_drift", 0.35), 0.01)
        self.water_fish_enabled = QCheckBox(lds_tr("水面ON時に曲線で描いた丸々とした魚を泳がせる"))
        self.water_fish_enabled.setChecked(bool(getattr(self.settings, "water_fish_enabled", True)))
        self.water_fish_count = self._int_spin(0, 60, getattr(self.settings, "water_fish_count", 4))
        self.water_fish_speed = self._double_spin(0.0, 3.0, getattr(self.settings, "water_fish_speed", 0.28), 0.01)
        self.water_fish_size = self._double_spin(4.0, 90.0, getattr(self.settings, "water_fish_size", 24.0), 0.5)
        self.water_fish_alpha = self._int_spin(0, 255, getattr(self.settings, "water_fish_alpha", 175))
        self.water_mirror_enabled = QCheckBox(lds_tr("他ウィジェットを鏡面反射"))
        self.water_mirror_enabled.setChecked(bool(getattr(self.settings, "water_mirror_enabled", False)))
        self.water_mirror_alpha = self._int_spin(0, 255, getattr(self.settings, "water_mirror_alpha", 110))
        self.water_mirror_blur = self._double_spin(0.0, 24.0, getattr(self.settings, "water_mirror_blur", 5.0), 0.5)
        self.water_mirror_depth = self._double_spin(0.05, 1.0, getattr(self.settings, "water_mirror_depth", 0.65), 0.01)
        self.water_mirror_wave = self._double_spin(0.0, 40.0, getattr(self.settings, "water_mirror_wave", 7.0), 0.5)
        self.water_mirror_tint_alpha = self._int_spin(0, 255, getattr(self.settings, "water_mirror_tint_alpha", 58))
        self.water_mirror_reflect_effects_enabled = QCheckBox(lds_tr("指定エフェクトも反射"))
        self.water_mirror_reflect_widgets_enabled = QCheckBox(lds_tr("通常ウィジェットを反射"))
        self.water_mirror_reflect_widgets_enabled.setChecked(bool(getattr(self.settings, "water_mirror_reflect_widgets_enabled", True)))
        self.water_mirror_reflect_effects_enabled.setChecked(bool(getattr(self.settings, "water_mirror_reflect_effects_enabled", True)))
        self.water_mirror_reflect_snow = QCheckBox(lds_tr("雪を反射"))
        self.water_mirror_reflect_snow.setChecked(bool(getattr(self.settings, "water_mirror_reflect_snow", True)))
        self.water_mirror_reflect_snow_crystal = QCheckBox(lds_tr("雪の結晶を反射"))
        self.water_mirror_reflect_snow_crystal.setChecked(bool(getattr(self.settings, "water_mirror_reflect_snow_crystal", True)))
        self.water_mirror_reflect_petals = QCheckBox(lds_tr("花びらを反射"))
        self.water_mirror_reflect_petals.setChecked(bool(getattr(self.settings, "water_mirror_reflect_petals", True)))
        self.water_mirror_reflect_bamboo = QCheckBox(lds_tr("竹林を反射"))
        self.water_mirror_reflect_bamboo.setChecked(bool(getattr(self.settings, "water_mirror_reflect_bamboo", True)))
        self.water_mirror_reflect_shooting_star = QCheckBox(lds_tr("流れ星を反射"))
        self.water_mirror_reflect_shooting_star.setChecked(bool(getattr(self.settings, "water_mirror_reflect_shooting_star", True)))
        self.water_mirror_reflect_meteor_shower = QCheckBox(lds_tr("流星群を反射"))
        self.water_mirror_reflect_meteor_shower.setChecked(bool(getattr(self.settings, "water_mirror_reflect_meteor_shower", True)))
        self.water_mirror_reflect_rain = QCheckBox(lds_tr("雨を反射"))
        self.water_mirror_reflect_rain.setChecked(bool(getattr(self.settings, "water_mirror_reflect_rain", True)))
        f.addRow(lds_tr("水面"), self.water_surface_enabled)
        f.addRow(lds_tr("水たまり"), self.puddle_enabled)
        f.addRow(lds_tr("水たまりX"), self.puddle_x)
        f.addRow(lds_tr("水たまりY"), self.puddle_y)
        f.addRow(lds_tr("水たまり幅"), self.puddle_width)
        f.addRow(lds_tr("水たまり高さ"), self.puddle_height)
        f.addRow(lds_tr("水たまり縁なじみ"), self.puddle_edge_softness)
        f.addRow(lds_tr("水たまり数"), self.puddle_count)
        f.addRow(lds_tr("水たまり点在幅"), self.puddle_spread)
        f.addRow(lds_tr("水面透明度"), self.water_surface_alpha)
        f.addRow(lds_tr("流れ角度"), self.water_surface_flow_angle)
        f.addRow(lds_tr("流れ速度"), self.water_surface_flow_speed)
        f.addRow(lds_tr("波の本数"), self.water_surface_wave_count)
        f.addRow(lds_tr("波の高さ"), self.water_surface_wave_height)
        f.addRow(lds_tr("水面Y"), self.water_surface_y)
        f.addRow(lds_tr("水面の深さ"), self.water_surface_depth)
        f.addRow(lds_tr("奥行き"), self.water_depth_enabled)
        f.addRow(lds_tr("奥行き強度"), self.water_depth_strength)
        f.addRow(lds_tr("奥の霞(α)"), self.water_depth_haze_alpha)
        f.addRow(lds_tr("朝もや/霧"), self.water_morning_fog_enabled)
        f.addRow(lds_tr("朝焼け連動"), self.water_morning_fog_follow_sunrise)
        f.addRow(lds_tr("もや強度"), self.water_morning_fog_strength)
        f.addRow(lds_tr("もや透明度"), self.water_morning_fog_alpha)
        f.addRow(lds_tr("もや高さ"), self.water_morning_fog_height)
        f.addRow(lds_tr("もや流れ"), self.water_morning_fog_drift)
        f.addRow(lds_tr("丸々とした魚"), self.water_fish_enabled)
        f.addRow(lds_tr("魚の数"), self.water_fish_count)
        f.addRow(lds_tr("魚の速度"), self.water_fish_speed)
        f.addRow(lds_tr("魚の大きさ"), self.water_fish_size)
        f.addRow(lds_tr("魚の透明度"), self.water_fish_alpha)
        f.addRow(lds_tr("鏡面反射"), self.water_mirror_enabled)
        f.addRow(lds_tr("鏡面反射具合"), self.water_mirror_alpha)
        f.addRow(lds_tr("反射ぼかし"), self.water_mirror_blur)
        f.addRow(lds_tr("反射の深さ"), self.water_mirror_depth)
        f.addRow(lds_tr("反射の揺らぎ"), self.water_mirror_wave)
        f.addRow(lds_tr("水色なじませ"), self.water_mirror_tint_alpha)
        f.addRow(lds_tr("エフェクト反射"), self.water_mirror_reflect_effects_enabled)
        f.addRow(lds_tr("通常ウィジェット反射"), self.water_mirror_reflect_widgets_enabled)
        f.addRow(lds_tr("反射: 雪"), self.water_mirror_reflect_snow)
        f.addRow(lds_tr("反射: 雪の結晶"), self.water_mirror_reflect_snow_crystal)
        f.addRow(lds_tr("反射: 花びら"), self.water_mirror_reflect_petals)
        f.addRow(lds_tr("反射: 竹"), self.water_mirror_reflect_bamboo)
        f.addRow(lds_tr("反射: 流れ星"), self.water_mirror_reflect_shooting_star)
        f.addRow(lds_tr("反射: 流星群"), self.water_mirror_reflect_meteor_shower)
        f.addRow(lds_tr("反射: 雨"), self.water_mirror_reflect_rain)
        self._section(f, lds_tr("氷・氷河"))
        self.ice_enabled = QCheckBox(lds_tr("リアル寄りの氷・氷河を描画"))
        self.ice_enabled.setChecked(bool(getattr(self.settings, "ice_enabled", False)))
        self.ice_lightweight_enabled = QCheckBox(lds_tr("軽量描画を使う"))
        self.ice_lightweight_enabled.setChecked(bool(getattr(self.settings, "ice_lightweight_enabled", True)))
        self.ice_static_cache_enabled = QCheckBox(lds_tr("静的な氷模様をキャッシュする"))
        self.ice_static_cache_enabled.setChecked(bool(getattr(self.settings, "ice_static_cache_enabled", True)))
        self.ice_quality_scale = self._double_spin(0.25, 1.0, getattr(self.settings, "ice_quality_scale", 0.58), 0.01)
        self.ice_max_facets = self._int_spin(8, 600, getattr(self.settings, "ice_max_facets", 72))
        self.ice_max_cracks = self._int_spin(0, 200, getattr(self.settings, "ice_max_cracks", 16))
        self.ice_max_bubbles = self._int_spin(0, 400, getattr(self.settings, "ice_max_bubbles", 34))
        self.ice_skip_reflected_effect_frames = self._int_spin(0, 12, getattr(self.settings, "ice_skip_reflected_effect_frames", 2))
        self.ice_mirror_skip_frames = self._int_spin(0, 12, getattr(self.settings, "ice_mirror_skip_frames", 2))
        self.ice_alpha = self._int_spin(0, 255, getattr(self.settings, "ice_alpha", 178))
        self.ice_size = self._double_spin(20.0, 900.0, getattr(self.settings, "ice_size", 185.0), 2.0)
        self.ice_angle = self._double_spin(-180.0, 180.0, getattr(self.settings, "ice_angle", -6.0), 1.0)
        self.ice_y = self._double_spin(0.0, 1.0, getattr(self.settings, "ice_y", 0.58), 0.01)
        self.ice_x = self._double_spin(0.0, 1.0, getattr(self.settings, "ice_x", 0.50), 0.01)
        self.ice_width = self._double_spin(0.05, 1.50, getattr(self.settings, "ice_width", 1.00), 0.01)
        self.ice_depth = self._double_spin(0.05, 1.0, getattr(self.settings, "ice_depth", 0.42), 0.01)
        self.ice_crack_intensity = self._double_spin(0.0, 2.0, getattr(self.settings, "ice_crack_intensity", 0.46), 0.01)
        self.ice_internal_bubble_intensity = self._double_spin(0.0, 2.0, getattr(self.settings, "ice_internal_bubble_intensity", 0.36), 0.01)
        self.ice_glacier_roughness = self._double_spin(0.0, 1.5, getattr(self.settings, "ice_glacier_roughness", 0.55), 0.01)
        self.ice_mirror_enabled = QCheckBox(lds_tr("氷面に他ウィジェット/エフェクトを鏡面反射"))
        self.ice_mirror_enabled.setChecked(bool(getattr(self.settings, "ice_mirror_enabled", True)))
        self.ice_mirror_alpha = self._int_spin(0, 255, getattr(self.settings, "ice_mirror_alpha", 118))
        self.ice_mirror_blur = self._double_spin(0.0, 24.0, getattr(self.settings, "ice_mirror_blur", 3.5), 0.5)
        self.ice_mirror_depth = self._double_spin(0.05, 1.0, getattr(self.settings, "ice_mirror_depth", 0.68), 0.01)
        self.ice_mirror_wave = self._double_spin(0.0, 30.0, getattr(self.settings, "ice_mirror_wave", 2.2), 0.25)
        self.ice_mirror_tint_alpha = self._int_spin(0, 255, getattr(self.settings, "ice_mirror_tint_alpha", 70))
        self.ice_reflect_effects_enabled = QCheckBox(lds_tr("エフェクトも反射対象に含める"))
        self.ice_reflect_widgets_enabled = QCheckBox(lds_tr("通常ウィジェットを反射"))
        self.ice_reflect_widgets_enabled.setChecked(bool(getattr(self.settings, "ice_reflect_widgets_enabled", True)))
        self.ice_reflect_snow = QCheckBox(lds_tr("雪を反射"))
        self.ice_reflect_snow.setChecked(bool(getattr(self.settings, "ice_reflect_snow", True)))
        self.ice_reflect_snow_crystal = QCheckBox(lds_tr("雪の結晶を反射"))
        self.ice_reflect_snow_crystal.setChecked(bool(getattr(self.settings, "ice_reflect_snow_crystal", True)))
        self.ice_reflect_petals = QCheckBox(lds_tr("花びらを反射"))
        self.ice_reflect_petals.setChecked(bool(getattr(self.settings, "ice_reflect_petals", True)))
        self.ice_reflect_bamboo = QCheckBox(lds_tr("竹林を反射"))
        self.ice_reflect_bamboo.setChecked(bool(getattr(self.settings, "ice_reflect_bamboo", True)))
        self.ice_reflect_shooting_star = QCheckBox(lds_tr("流れ星を反射"))
        self.ice_reflect_shooting_star.setChecked(bool(getattr(self.settings, "ice_reflect_shooting_star", True)))
        self.ice_reflect_meteor_shower = QCheckBox(lds_tr("流星群を反射"))
        self.ice_reflect_meteor_shower.setChecked(bool(getattr(self.settings, "ice_reflect_meteor_shower", True)))
        self.ice_reflect_rain = QCheckBox(lds_tr("雨を反射"))
        self.ice_reflect_rain.setChecked(bool(getattr(self.settings, "ice_reflect_rain", True)))
        self.ice_reflect_effects_enabled.setChecked(bool(getattr(self.settings, "ice_reflect_effects_enabled", True)))
        self.ice_fog_enabled = QCheckBox(lds_tr("表面に薄い霧を掛ける"))
        self.ice_fog_enabled.setChecked(bool(getattr(self.settings, "ice_fog_enabled", True)))
        self.ice_fog_alpha = self._int_spin(0, 255, getattr(self.settings, "ice_fog_alpha", 72))
        self.ice_fog_height = self._double_spin(0.02, 0.80, getattr(self.settings, "ice_fog_height", 0.24), 0.01)
        self.ice_fog_drift = self._double_spin(0.0, 3.0, getattr(self.settings, "ice_fog_drift", 0.30), 0.01)
        self.ice_color = self._color_row_on(f, lds_tr("氷色"), getattr(self.settings, "ice_color", "#9BDDF2"))
        self.ice_edge_color = self._color_row_on(f, lds_tr("氷の縁/亀裂色"), getattr(self.settings, "ice_edge_color", "#E8FBFF"))
        self.ice_highlight_color = self._color_row_on(f, lds_tr("氷ハイライト色"), getattr(self.settings, "ice_highlight_color", "#F7FFFF"))
        self.ice_shadow_color = self._color_row_on(f, lds_tr("氷の奥影色"), getattr(self.settings, "ice_shadow_color", "#2C6F93"))
        self.ice_fog_color = self._color_row_on(f, lds_tr("霧色"), getattr(self.settings, "ice_fog_color", "#EEF9FF"))
        f.addRow(lds_tr("氷・氷河"), self.ice_enabled)
        f.addRow(lds_tr("軽量描画"), self.ice_lightweight_enabled)
        f.addRow(lds_tr("静的模様キャッシュ"), self.ice_static_cache_enabled)
        f.addRow(lds_tr("描画品質"), self.ice_quality_scale)
        f.addRow(lds_tr("最大氷面パーツ"), self.ice_max_facets)
        f.addRow(lds_tr("最大亀裂数"), self.ice_max_cracks)
        f.addRow(lds_tr("最大気泡数"), self.ice_max_bubbles)
        f.addRow(lds_tr("反射エフェクト間引き"), self.ice_skip_reflected_effect_frames)
        f.addRow(lds_tr("通常ウィジェット反射間引き"), self.ice_mirror_skip_frames)
        f.addRow(lds_tr("氷透明度"), self.ice_alpha)
        f.addRow(lds_tr("氷塊サイズ"), self.ice_size)
        f.addRow(lds_tr("氷角度"), self.ice_angle)
        f.addRow(lds_tr("氷面X"), self.ice_x)
        f.addRow(lds_tr("氷面幅"), self.ice_width)
        f.addRow(lds_tr("氷面Y"), self.ice_y)
        f.addRow(lds_tr("氷の深さ"), self.ice_depth)
        f.addRow(lds_tr("亀裂強度"), self.ice_crack_intensity)
        f.addRow(lds_tr("内部気泡/白濁"), self.ice_internal_bubble_intensity)
        f.addRow(lds_tr("氷河の凹凸"), self.ice_glacier_roughness)
        f.addRow(lds_tr("鏡面反射"), self.ice_mirror_enabled)
        f.addRow(lds_tr("反射透明度"), self.ice_mirror_alpha)
        f.addRow(lds_tr("反射ぼかし"), self.ice_mirror_blur)
        f.addRow(lds_tr("反射の深さ"), self.ice_mirror_depth)
        f.addRow(lds_tr("反射の揺らぎ"), self.ice_mirror_wave)
        f.addRow(lds_tr("氷色なじませ"), self.ice_mirror_tint_alpha)
        f.addRow(lds_tr("エフェクト反射"), self.ice_reflect_effects_enabled)
        f.addRow(lds_tr("通常ウィジェット反射"), self.ice_reflect_widgets_enabled)
        f.addRow(lds_tr("反射: 雪"), self.ice_reflect_snow)
        f.addRow(lds_tr("反射: 雪の結晶"), self.ice_reflect_snow_crystal)
        f.addRow(lds_tr("反射: 花びら"), self.ice_reflect_petals)
        f.addRow(lds_tr("反射: 竹"), self.ice_reflect_bamboo)
        f.addRow(lds_tr("反射: 流れ星"), self.ice_reflect_shooting_star)
        f.addRow(lds_tr("反射: 流星群"), self.ice_reflect_meteor_shower)
        f.addRow(lds_tr("反射: 雨"), self.ice_reflect_rain)
        f.addRow(lds_tr("薄霧"), self.ice_fog_enabled)
        f.addRow(lds_tr("霧透明度"), self.ice_fog_alpha)
        f.addRow(lds_tr("霧高さ"), self.ice_fog_height)
        f.addRow(lds_tr("霧流れ"), self.ice_fog_drift)

        self._section(f, lds_tr("竹林"))
        self.bamboo_grove_enabled = QCheckBox(lds_tr("竹林を描画"))
        self.bamboo_grove_enabled.setChecked(bool(getattr(self.settings, "bamboo_grove_enabled", False)))
        self.bamboo_count = self._int_spin(0, 120, getattr(self.settings, "bamboo_count", 12))
        self.bamboo_thickness = self._double_spin(2.0, 80.0, getattr(self.settings, "bamboo_thickness", 16.0), 0.5)
        self.bamboo_angle = self._double_spin(-45.0, 45.0, getattr(self.settings, "bamboo_angle", 0.0), 0.5)
        self.bamboo_bend = self._double_spin(0.0, 2.0, getattr(self.settings, "bamboo_bend", 0.32), 0.01)
        self.bamboo_height = self._double_spin(0.10, 1.50, getattr(self.settings, "bamboo_height", 0.92), 0.01)
        self.bamboo_alpha = self._int_spin(0, 255, getattr(self.settings, "bamboo_alpha", 230))
        self.bamboo_leaf_density = self._int_spin(0, 12, getattr(self.settings, "bamboo_leaf_density", 4))
        self.bamboo_depth_strength = self._double_spin(0.0, 2.0, getattr(self.settings, "bamboo_depth_strength", 0.85), 0.01)
        self.bamboo_layer_spread = self._double_spin(0.0, 1.0, getattr(self.settings, "bamboo_layer_spread", 0.42), 0.01)
        self.bamboo_highlight_alpha = self._int_spin(0, 255, getattr(self.settings, "bamboo_highlight_alpha", 96))
        self.bamboo_ground_shadow_enabled = QCheckBox(lds_tr("足元の影で奥行きを出す"))
        self.bamboo_ground_shadow_enabled.setChecked(bool(getattr(self.settings, "bamboo_ground_shadow_enabled", True)))
        self.bamboo_atmosphere_enabled = QCheckBox(lds_tr("奥の竹を霞ませる"))
        self.bamboo_atmosphere_enabled.setChecked(bool(getattr(self.settings, "bamboo_atmosphere_enabled", True)))
        f.addRow(lds_tr("竹林"), self.bamboo_grove_enabled)
        f.addRow(lds_tr("竹の本数"), self.bamboo_count)
        f.addRow(lds_tr("竹の太さ"), self.bamboo_thickness)
        f.addRow(lds_tr("竹の角度"), self.bamboo_angle)
        f.addRow(lds_tr("竹のしなり"), self.bamboo_bend)
        f.addRow(lds_tr("竹の高さ"), self.bamboo_height)
        f.addRow(lds_tr("竹の透明度"), self.bamboo_alpha)
        f.addRow(lds_tr("竹の葉の量"), self.bamboo_leaf_density)
        f.addRow(lds_tr("竹林の奥行き"), self.bamboo_depth_strength)
        f.addRow(lds_tr("前後レイヤー幅"), self.bamboo_layer_spread)
        f.addRow(lds_tr("竹のハイライト"), self.bamboo_highlight_alpha)
        f.addRow(lds_tr("足元影"), self.bamboo_ground_shadow_enabled)
        f.addRow(lds_tr("奥の霞"), self.bamboo_atmosphere_enabled)
        self._add_effect_block(f, lds_tr("流れ星"), "shooting_star", lds_tr("流れ星が斜めに走る"), 3, 0.8, 18.0, 230, ripple=False)
        self._add_effect_block(f, lds_tr("流星群"), "meteor_shower", lds_tr("流星群が連続して流れる"), 18, 0.9, 12.0, 220, ripple=False)
        self._add_effect_block(f, lds_tr("バルーン"), "balloon", lds_tr("バルーンがゆっくり登る"), 12, 0.20, 34.0, 220, ripple=False)


    def _set_extra_effect_toggles(self, value):
        for name in [
            "snow", "snow_crystal", "water_drop", "bubble", "flame", "water_spray",
            "fireball", "star_sky", "shooting_star", "meteor_shower", "balloon",
        "ice",
        ]:
            widget = getattr(self, f"{name}_enabled", None)
            if widget is not None:
                widget.setChecked(bool(value))
        milky_widget = getattr(self, "milky_way_enabled", None)
        if milky_widget is not None:
            milky_widget.setChecked(bool(value))
        water_surface_widget = getattr(self, "water_surface_enabled", None)
        if water_surface_widget is not None:
            water_surface_widget.setChecked(bool(value))
        bamboo_widget = getattr(self, "bamboo_grove_enabled", None)
        if bamboo_widget is not None:
            bamboo_widget.setChecked(bool(value))

    def _set_toggle_values(self, rain, particles, noise, glow, ripple, mouse_ripple, mouse_flee, mouse_glow):
        self.rain_enabled.setChecked(bool(rain))
        self.particles_enabled.setChecked(bool(particles))
        self.noise_enabled.setChecked(bool(noise))
        self.glow_enabled.setChecked(bool(glow))
        self.ripple_enabled.setChecked(bool(ripple))
        self.mouse_ripple_enabled.setChecked(bool(mouse_ripple))
        self.mouse_flee_enabled.setChecked(bool(mouse_flee))
        self.mouse_glow_enabled.setChecked(bool(mouse_glow))

    def set_all_on(self):
        self._set_toggle_values(True, True, True, True, True, True, True, True)
        self.rain_ripple_enabled.setChecked(True)
        self.rose_petals_enabled.setChecked(True)
        self.rose_flowers_enabled.setChecked(True)
        self.blooming_roses_enabled.setChecked(True)
        self.sakura_petals_enabled.setChecked(True)
        self.sunrise_enabled.setChecked(True)
        self.sun_enabled.setChecked(True)
        self.sunlight_enabled.setChecked(True)
        self.lens_flare_enabled.setChecked(True)
        self.moon_body_enabled.setChecked(True)
        self.moonlight_enabled.setChecked(True)
        self.moon_shadow_enabled.setChecked(True)
        self._set_extra_effect_toggles(True)

    def set_all_off(self):
        self._set_toggle_values(False, False, False, False, False, False, False, False)
        self.rain_ripple_enabled.setChecked(False)
        self.rose_petals_enabled.setChecked(False)
        self.rose_flowers_enabled.setChecked(False)
        self.blooming_roses_enabled.setChecked(False)
        self.sakura_petals_enabled.setChecked(False)
        self.sunrise_enabled.setChecked(False)
        self.sun_enabled.setChecked(False)
        self.sunlight_enabled.setChecked(False)
        self.lens_flare_enabled.setChecked(False)
        self.moon_body_enabled.setChecked(False)
        self.moonlight_enabled.setChecked(False)
        self.moon_shadow_enabled.setChecked(False)
        self._set_extra_effect_toggles(False)

    def set_mouse_only(self):
        self._set_toggle_values(False, False, False, False, False, True, True, True)
        self.rain_ripple_enabled.setChecked(False)
        self.rose_petals_enabled.setChecked(False)
        self.rose_flowers_enabled.setChecked(False)
        self.blooming_roses_enabled.setChecked(False)
        self.sakura_petals_enabled.setChecked(False)
        self.sunrise_enabled.setChecked(False)
        self.sun_enabled.setChecked(False)
        self.sunlight_enabled.setChecked(False)
        self.lens_flare_enabled.setChecked(False)
        self.moon_body_enabled.setChecked(False)
        self.moonlight_enabled.setChecked(False)
        self.moon_shadow_enabled.setChecked(False)
        self._set_extra_effect_toggles(False)

    def set_ambient_only(self):
        self._set_toggle_values(True, True, True, True, True, False, False, False)
        self.rain_ripple_enabled.setChecked(True)
        self.rose_petals_enabled.setChecked(True)
        self.rose_flowers_enabled.setChecked(False)
        self.blooming_roses_enabled.setChecked(False)
        self.sakura_petals_enabled.setChecked(False)
        self.sunrise_enabled.setChecked(False)
        self.sun_enabled.setChecked(False)
        self.sunlight_enabled.setChecked(False)
        self.lens_flare_enabled.setChecked(False)
        self.moon_body_enabled.setChecked(False)
        self.moonlight_enabled.setChecked(False)
        self.moon_shadow_enabled.setChecked(False)
        self._set_extra_effect_toggles(False)

    def _theme_set_checked(self, name: str, value: bool):
        widget = getattr(self, name, None)
        if widget is not None and hasattr(widget, "setChecked"):
            widget.setChecked(bool(value))

    def _theme_set_value(self, name: str, value):
        widget = getattr(self, name, None)
        if widget is not None and hasattr(widget, "setValue"):
            try:
                widget.setValue(value)
            except Exception:
                pass

    def _theme_set_text(self, name: str, value: str):
        widget = getattr(self, name, None)
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(str(value))

    def _theme_disable_all_visual_effects(self):
        self._set_toggle_values(False, False, False, False, False, False, False, False)
        for name in [
            "rain_ripple_enabled", "rose_petals_enabled", "rose_flowers_enabled", "blooming_roses_enabled",
            "sakura_petals_enabled", "sunrise_enabled", "sun_enabled", "sunlight_enabled", "lens_flare_enabled",
            "moon_body_enabled", "moonlight_enabled", "moon_shadow_enabled", "milky_way_enabled",
            "water_surface_enabled", "ice_enabled", "bamboo_grove_enabled",
        ]:
            self._theme_set_checked(name, False)
        self._set_extra_effect_toggles(False)

    def _theme_set_extra(self, prefix: str, enabled: bool = True, count=None, speed=None, size=None, alpha=None):
        self._theme_set_checked(f"{prefix}_enabled", enabled)
        if count is not None:
            self._theme_set_value(f"{prefix}_count", count)
        if speed is not None:
            self._theme_set_value(f"{prefix}_speed", speed)
        if size is not None:
            self._theme_set_value(f"{prefix}_size", size)
        if alpha is not None:
            self._theme_set_value(f"{prefix}_alpha", alpha)

    def _theme_apply_common_lightweight(self, fps: int = 30, quality: float = 0.70):
        self._theme_set_checked("effect_frame_rate_enabled", True)
        self._theme_set_value("effect_frame_rate", fps)
        self._theme_set_checked("software_lightweight_enabled", True)
        self._theme_set_value("software_quality_scale", quality)
        self._theme_set_value("software_max_fps", fps)
        self._theme_set_checked("software_disable_antialiasing", False)
        self._theme_set_value("software_skip_reflection_frames", 2)
        self._theme_set_value("software_max_extra_particles", 360)
        self._theme_set_value("software_max_petals", 120)
        self._theme_set_value("software_max_ripples", 36)

    def apply_effect_theme(self, theme_id: str):
        """Enable a curated group of effects as a theme preset."""
        self._theme_disable_all_visual_effects()
        self._theme_apply_common_lightweight()

        if theme_id == "quiet_night":
            self._theme_set_checked("moon_body_enabled", True)
            self._theme_set_checked("moonlight_enabled", True)
            self._theme_set_checked("moon_shadow_enabled", True)
            self._theme_set_value("moon_alpha", 225)
            self._theme_set_value("moonlight_alpha", 70)
            self._theme_set_extra("star_sky", True, count=300, speed=0.28, size=1.4, alpha=215)
            self._theme_set_checked("milky_way_enabled", True)
            self._theme_set_value("milky_way_star_count", 180)
            self._theme_set_value("milky_way_alpha", 92)
            self._theme_set_extra("shooting_star", True, count=2, speed=0.72, size=15.0, alpha=210)

        elif theme_id == "moonlit_water":
            self._theme_set_checked("moon_body_enabled", True)
            self._theme_set_checked("moonlight_enabled", True)
            self._theme_set_checked("moon_shadow_enabled", True)
            self._theme_set_extra("star_sky", True, count=220, speed=0.25, size=1.3, alpha=190)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_checked("water_fish_enabled", True)
            self._theme_set_value("water_fish_count", 3)
            self._theme_set_value("water_fish_speed", 0.32)
            self._theme_set_value("water_surface_alpha", 104)
            self._theme_set_value("water_surface_wave_count", 12)
            self._theme_set_value("water_surface_wave_height", 10.0)
            self._theme_set_checked("water_mirror_enabled", True)
            self._theme_set_value("water_mirror_alpha", 95)
            self._theme_set_value("water_mirror_blur", 6.0)
            self._theme_set_value("water_mirror_wave", 5.0)
            self._theme_set_checked("water_mirror_reflect_effects_enabled", True)
            self._theme_set_checked("water_mirror_reflect_snow", False)
            self._theme_set_checked("water_mirror_reflect_bamboo", False)

        elif theme_id == "spring_petals":
            self._theme_set_checked("rose_petals_enabled", True)
            self._theme_set_value("rose_petal_count", 42)
            self._theme_set_value("rose_petal_speed", 0.23)
            self._theme_set_value("rose_petal_sway", 1.35)
            self._theme_set_value("rose_petal_alpha", 220)
            self._theme_set_checked("sakura_petals_enabled", True)
            self._theme_set_value("sakura_petal_count", 64)
            self._theme_set_value("sakura_petal_speed", 0.20)
            self._theme_set_value("sakura_petal_sway", 1.50)
            self._theme_set_value("sakura_petal_alpha", 210)
            self._theme_set_checked("ripple_enabled", True)
            self._theme_set_checked("rose_petal_ripple_enabled", True)

        elif theme_id == "bamboo_path":
            self._theme_set_checked("bamboo_grove_enabled", True)
            self._theme_set_value("bamboo_count", 16)
            self._theme_set_value("bamboo_thickness", 15.5)
            self._theme_set_value("bamboo_bend", 0.42)
            self._theme_set_value("bamboo_alpha", 230)
            self._theme_set_value("bamboo_leaf_density", 5)
            self._theme_set_value("bamboo_depth_strength", 0.92)
            self._theme_set_value("bamboo_layer_spread", 0.50)
            self._theme_set_checked("bamboo_ground_shadow_enabled", True)
            self._theme_set_checked("bamboo_atmosphere_enabled", True)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_checked("water_fish_enabled", True)
            self._theme_set_value("water_fish_count", 3)
            self._theme_set_value("water_surface_alpha", 70)
            self._theme_set_checked("water_mirror_enabled", True)
            self._theme_set_value("water_mirror_alpha", 58)
            self._theme_set_checked("water_mirror_reflect_bamboo", True)

        elif theme_id == "rain_ripples":
            self._theme_set_toggle_values_for_rain = True
            self._theme_set_checked("rain_enabled", True)
            self._theme_set_value("rain_count", 85)
            self._theme_set_value("rain_speed", 1.12)
            self._theme_set_checked("ripple_enabled", True)
            self._theme_set_checked("rain_ripple_enabled", True)
            self._theme_set_value("rain_ripple_chance", 0.70)
            self._theme_set_value("rain_ripple_cooldown", 0.035)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_checked("puddle_enabled", True)
            self._theme_set_value("puddle_x", 0.50)
            self._theme_set_value("puddle_y", 0.84)
            self._theme_set_value("puddle_width", 0.72)
            self._theme_set_value("puddle_height", 0.22)
            self._theme_set_value("puddle_edge_softness", 0.18)
            self._theme_set_value("puddle_count", 5)
            self._theme_set_value("puddle_spread", 0.72)
            self._theme_set_checked("water_mirror_enabled", True)
            self._theme_set_checked("water_mirror_reflect_widgets_enabled", True)
            self._theme_set_checked("water_mirror_reflect_effects_enabled", True)
            self._theme_set_value("water_mirror_alpha", 116)
            self._theme_set_value("water_mirror_blur", 3.5)
            self._theme_set_value("water_mirror_wave", 4.5)
            self._theme_set_checked("water_fish_enabled", False)
            self._theme_set_value("water_fish_count", 0)
            self._theme_set_value("water_surface_alpha", 96)
            self._theme_set_value("water_surface_wave_count", 14)
            self._theme_set_extra("water_drop", True, count=36, speed=0.45, size=7.0, alpha=185)

        elif theme_id == "snow_scene":
            self._theme_set_extra("snow", True, count=120, speed=0.16, size=4.2, alpha=210)
            self._theme_set_extra("snow_crystal", True, count=28, speed=0.11, size=13.0, alpha=220)
            self._theme_set_checked("ripple_enabled", True)
            self._theme_set_checked("moon_body_enabled", True)
            self._theme_set_checked("moonlight_enabled", True)
            self._theme_set_extra("star_sky", True, count=160, speed=0.18, size=1.1, alpha=150)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_value("water_surface_alpha", 62)

        elif theme_id == "glacier_mirror":
            self._theme_set_checked("ice_enabled", True)
            self._theme_set_checked("ice_lightweight_enabled", True)
            self._theme_set_checked("ice_static_cache_enabled", True)
            self._theme_set_value("ice_quality_scale", 0.58)
            self._theme_set_value("ice_max_facets", 72)
            self._theme_set_value("ice_max_cracks", 16)
            self._theme_set_value("ice_max_bubbles", 34)
            self._theme_set_value("ice_skip_reflected_effect_frames", 2)
            self._theme_set_value("ice_mirror_skip_frames", 2)
            self._theme_set_value("ice_alpha", 185)
            self._theme_set_value("ice_size", 210.0)
            self._theme_set_value("ice_angle", -7.0)
            self._theme_set_value("ice_y", 0.56)
            self._theme_set_value("ice_depth", 0.44)
            self._theme_set_value("ice_crack_intensity", 0.58)
            self._theme_set_value("ice_internal_bubble_intensity", 0.42)
            self._theme_set_value("ice_glacier_roughness", 0.70)
            self._theme_set_checked("ice_mirror_enabled", True)
            self._theme_set_checked("ice_reflect_widgets_enabled", True)
            self._theme_set_checked("ice_reflect_effects_enabled", True)
            self._theme_set_checked("ice_reflect_snow", True)
            self._theme_set_checked("ice_reflect_snow_crystal", True)
            self._theme_set_checked("ice_reflect_petals", True)
            self._theme_set_checked("ice_reflect_rain", True)
            self._theme_set_value("ice_mirror_alpha", 130)
            self._theme_set_value("ice_mirror_blur", 3.0)
            self._theme_set_value("ice_mirror_wave", 1.7)
            self._theme_set_checked("ice_fog_enabled", True)
            self._theme_set_value("ice_fog_alpha", 76)
            self._theme_set_extra("snow", True, count=70, speed=0.13, size=3.8, alpha=185)
            self._theme_set_extra("snow_crystal", True, count=14, speed=0.09, size=12.0, alpha=200)
            self._theme_set_extra("star_sky", True, count=180, speed=0.18, size=1.1, alpha=150)
        elif theme_id == "meteor_sky":
            self._theme_set_extra("star_sky", True, count=340, speed=0.34, size=1.5, alpha=220)
            self._theme_set_checked("milky_way_enabled", True)
            self._theme_set_value("milky_way_star_count", 220)
            self._theme_set_value("milky_way_alpha", 112)
            self._theme_set_extra("shooting_star", True, count=4, speed=0.90, size=17.0, alpha=230)
            self._theme_set_extra("meteor_shower", True, count=18, speed=0.95, size=11.5, alpha=215)
            self._theme_set_checked("moon_body_enabled", True)
            self._theme_set_value("moon_alpha", 190)

        elif theme_id == "fire_and_water":
            self._theme_set_extra("flame", True, count=54, speed=0.55, size=21.0, alpha=205)
            self._theme_set_extra("fireball", True, count=8, speed=0.32, size=18.0, alpha=220)
            self._theme_set_extra("water_spray", True, count=52, speed=0.70, size=5.8, alpha=185)
            self._theme_set_extra("bubble", True, count=34, speed=0.24, size=11.0, alpha=145)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_value("water_surface_alpha", 88)
            self._theme_set_value("water_surface_wave_count", 13)
            self._theme_set_value("water_surface_wave_height", 12.0)

        try:
            self.apply_to_config()
        except Exception:
            pass

    def set_rose_petals_only(self):
        self._set_toggle_values(False, False, False, False, False, False, False, False)
        self.rain_ripple_enabled.setChecked(False)
        self.rose_petals_enabled.setChecked(True)
        self.rose_flowers_enabled.setChecked(False)
        self.blooming_roses_enabled.setChecked(False)
        self.sakura_petals_enabled.setChecked(False)
        self.rose_petal_ripple_enabled.setChecked(False)
        self.rose_petal_count.setValue(24)
        self.rose_petal_speed.setValue(0.25)
        self.rose_petal_sway.setValue(1.15)
        self.rose_petal_size.setValue(18.0)
        self.rose_petal_alpha.setValue(215)
    def _build_sunrise_tab(self):
        f = self.sunrise_form
        self._section(f, lds_tr("朝焼け"))
        self.sunrise_enabled_tab = QCheckBox(lds_tr("朝焼けを描画"))
        self.sunrise_enabled_tab.setChecked(bool(getattr(self.settings, "sunrise_enabled", False)))
        self.sunrise_enabled.toggled.connect(self.sunrise_enabled_tab.setChecked)
        self.sunrise_enabled_tab.toggled.connect(self.sunrise_enabled.setChecked)
        self.sunrise_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "sunrise_angle", 0.0), 1.0)
        self.sunrise_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "sunrise_strength", 0.65), 0.01)
        self.sunrise_warmth = self._double_spin(0.0, 1.0, getattr(self.settings, "sunrise_warmth", 0.72), 0.01)
        self.sunrise_horizon_y = self._double_spin(0.0, 1.0, getattr(self.settings, "sunrise_horizon_y", 0.72), 0.01)
        self.sunrise_spread = self._double_spin(0.05, 1.0, getattr(self.settings, "sunrise_spread", 0.62), 0.01)
        f.addRow(lds_tr("朝焼け"), self.sunrise_enabled_tab)
        f.addRow(lds_tr("朝焼け角度"), self.sunrise_angle)
        f.addRow(lds_tr("朝焼けの強さ"), self.sunrise_strength)
        f.addRow(lds_tr("朝焼け具合"), self.sunrise_warmth)
        f.addRow(lds_tr("地平線Y"), self.sunrise_horizon_y)
        f.addRow(lds_tr("広がり"), self.sunrise_spread)

        self._section(f, lds_tr("太陽"))
        self.sun_enabled_tab = QCheckBox(lds_tr("太陽を描画"))
        self.sun_enabled_tab.setChecked(bool(getattr(self.settings, "sun_enabled", False)))
        self.sun_enabled.toggled.connect(self.sun_enabled_tab.setChecked)
        self.sun_enabled_tab.toggled.connect(self.sun_enabled.setChecked)
        self.sun_x = self._double_spin(0.0, 1.0, getattr(self.settings, "sun_x", 0.22), 0.01)
        self.sun_y = self._double_spin(0.0, 1.0, getattr(self.settings, "sun_y", 0.22), 0.01)
        self.sun_radius = self._double_spin(4.0, 3000.0, getattr(self.settings, "sun_radius", 82.0), 1.0)
        self.sun_alpha = self._int_spin(0, 255, getattr(self.settings, "sun_alpha", 235))
        self.sun_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "sun_angle", 0.0), 1.0)
        f.addRow(lds_tr("太陽"), self.sun_enabled_tab)
        f.addRow(lds_tr("太陽X位置"), self.sun_x)
        f.addRow(lds_tr("太陽Y位置"), self.sun_y)
        f.addRow(lds_tr("太陽半径"), self.sun_radius)
        f.addRow(lds_tr("太陽透明度"), self.sun_alpha)
        f.addRow(lds_tr("太陽角度"), self.sun_angle)

        self._section(f, lds_tr("太陽光"))
        self.sunlight_enabled_tab = QCheckBox(lds_tr("太陽光を描画"))
        self.sunlight_enabled_tab.setChecked(bool(getattr(self.settings, "sunlight_enabled", False)))
        self.sunlight_enabled.toggled.connect(self.sunlight_enabled_tab.setChecked)
        self.sunlight_enabled_tab.toggled.connect(self.sunlight_enabled.setChecked)
        self.sunlight_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "sunlight_angle", 18.0), 1.0)
        self.sunlight_radius = self._double_spin(10.0, 3000.0, getattr(self.settings, "sunlight_radius", 420.0), 5.0)
        self.sunlight_alpha = self._int_spin(0, 255, getattr(self.settings, "sunlight_alpha", 92))
        self.sunlight_beam_width = self._double_spin(0.05, 1.0, getattr(self.settings, "sunlight_beam_width", 0.38), 0.01)
        f.addRow(lds_tr("太陽光"), self.sunlight_enabled_tab)
        f.addRow(lds_tr("太陽光角度"), self.sunlight_angle)
        f.addRow(lds_tr("太陽光半径"), self.sunlight_radius)
        f.addRow(lds_tr("太陽光透明度"), self.sunlight_alpha)
        f.addRow(lds_tr("太陽光幅"), self.sunlight_beam_width)

        self._section(f, lds_tr("レンズフレア"))
        self.lens_flare_enabled_tab = QCheckBox(lds_tr("レンズフレアを描画"))
        self.lens_flare_enabled_tab.setChecked(bool(getattr(self.settings, "lens_flare_enabled", False)))
        self.lens_flare_enabled.toggled.connect(self.lens_flare_enabled_tab.setChecked)
        self.lens_flare_enabled_tab.toggled.connect(self.lens_flare_enabled.setChecked)
        self.lens_flare_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "lens_flare_angle", 18.0), 1.0)
        self.lens_flare_alpha = self._int_spin(0, 255, getattr(self.settings, "lens_flare_alpha", 128))
        self.lens_flare_size = self._double_spin(0.1, 4.0, getattr(self.settings, "lens_flare_size", 1.0), 0.05)
        self.lens_flare_count = self._int_spin(0, 12, getattr(self.settings, "lens_flare_count", 6))
        f.addRow(lds_tr("レンズフレア"), self.lens_flare_enabled_tab)
        f.addRow(lds_tr("フレア角度"), self.lens_flare_angle)
        f.addRow(lds_tr("フレア透明度"), self.lens_flare_alpha)
        f.addRow(lds_tr("フレアサイズ"), self.lens_flare_size)
        f.addRow(lds_tr("フレア数"), self.lens_flare_count)

        self._section(f, lds_tr("色"))
        self.sunrise_color_top = self._color_row_on(f, lds_tr("朝焼け上部色"), getattr(self.settings, "sunrise_color_top", "#1B2C64"))
        self.sunrise_color_mid = self._color_row_on(f, lds_tr("朝焼け中間色"), getattr(self.settings, "sunrise_color_mid", "#FF8A5C"))
        self.sunrise_color_horizon = self._color_row_on(f, lds_tr("朝焼け地平線色"), getattr(self.settings, "sunrise_color_horizon", "#FFD08A"))
        self.sun_color = self._color_row_on(f, lds_tr("太陽色"), getattr(self.settings, "sun_color", "#FFD36E"))
        self.sun_edge_color = self._color_row_on(f, lds_tr("太陽縁色"), getattr(self.settings, "sun_edge_color", "#FF7A3D"))
        self.sunlight_color = self._color_row_on(f, lds_tr("太陽光色"), getattr(self.settings, "sunlight_color", "#FFD08A"))
        self.lens_flare_color = self._color_row_on(f, lds_tr("レンズフレア色"), getattr(self.settings, "lens_flare_color", "#FFE2A6"))

    def _build_moon_tab(self):
        f = self.moon_form
        self._section(f, lds_tr("月本体"))
        self.moon_body_enabled_tab = QCheckBox(lds_tr("月本体を描画"))
        self.moon_body_enabled_tab.setChecked(bool(getattr(self.settings, "moon_body_enabled", False)))
        self.moonlight_enabled_tab = QCheckBox(lds_tr("月光を描画"))
        self.moonlight_enabled_tab.setChecked(bool(getattr(self.settings, "moonlight_enabled", False)))
        self.moon_shadow_enabled_tab = QCheckBox(lds_tr("月影を描画"))
        self.moon_shadow_enabled_tab.setChecked(bool(getattr(self.settings, "moon_shadow_enabled", False)))
        self.moon_body_enabled.toggled.connect(self.moon_body_enabled_tab.setChecked)
        self.moon_body_enabled_tab.toggled.connect(self.moon_body_enabled.setChecked)
        self.moonlight_enabled.toggled.connect(self.moonlight_enabled_tab.setChecked)
        self.moonlight_enabled_tab.toggled.connect(self.moonlight_enabled.setChecked)
        self.moon_shadow_enabled.toggled.connect(self.moon_shadow_enabled_tab.setChecked)
        self.moon_shadow_enabled_tab.toggled.connect(self.moon_shadow_enabled.setChecked)
        self.moon_x = self._double_spin(0.0, 1.0, getattr(self.settings, "moon_x", 0.78), 0.01)
        self.moon_y = self._double_spin(0.0, 1.0, getattr(self.settings, "moon_y", 0.18), 0.01)
        self.moon_body_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "moon_body_angle", 0.0), 1.0)
        self.moon_radius = self._double_spin(4.0, 3000.0, getattr(self.settings, "moon_radius", 74.0), 1.0)
        self.moon_alpha = self._int_spin(0, 255, getattr(self.settings, "moon_alpha", 230))
        self.moon_crater_count = self._int_spin(0, 40, getattr(self.settings, "moon_crater_count", 9))
        self.moon_crater_alpha = self._int_spin(0, 255, getattr(self.settings, "moon_crater_alpha", 54))
        f.addRow(lds_tr("月本体"), self.moon_body_enabled_tab)
        f.addRow(lds_tr("月光"), self.moonlight_enabled_tab)
        f.addRow(lds_tr("月影"), self.moon_shadow_enabled_tab)
        f.addRow(lds_tr("X位置"), self.moon_x)
        f.addRow(lds_tr("Y位置"), self.moon_y)
        f.addRow(lds_tr("月本体角度"), self.moon_body_angle)
        f.addRow(lds_tr("半径"), self.moon_radius)
        f.addRow(lds_tr("透明度"), self.moon_alpha)
        f.addRow(lds_tr("クレーター数"), self.moon_crater_count)
        f.addRow(lds_tr("クレーター透明度"), self.moon_crater_alpha)
        self._section(f, lds_tr("月光"))
        self.moonlight_radius = self._double_spin(10.0, 900.0, getattr(self.settings, "moonlight_radius", 260.0), 5.0)
        self.moonlight_alpha = self._int_spin(0, 255, getattr(self.settings, "moonlight_alpha", 82))
        self.moonlight_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "moonlight_angle", 0.0), 1.0)
        self.moonlight_beam_enabled = QCheckBox(lds_tr("月光ビーム"))
        self.moonlight_beam_enabled.setChecked(bool(getattr(self.settings, "moonlight_beam_enabled", True)))
        self.moonlight_beam_alpha = self._int_spin(0, 255, getattr(self.settings, "moonlight_beam_alpha", 44))
        self.moonlight_beam_width = self._double_spin(0.05, 1.0, getattr(self.settings, "moonlight_beam_width", 0.34), 0.01)
        f.addRow(lds_tr("月光半径"), self.moonlight_radius)
        f.addRow(lds_tr("月光透明度"), self.moonlight_alpha)
        f.addRow(lds_tr("月光角度"), self.moonlight_angle)
        f.addRow(lds_tr("ビーム"), self.moonlight_beam_enabled)
        f.addRow(lds_tr("ビーム透明度"), self.moonlight_beam_alpha)
        f.addRow(lds_tr("ビーム幅"), self.moonlight_beam_width)
        self._section(f, lds_tr("月影"))
        self.moon_shadow_alpha = self._int_spin(0, 255, getattr(self.settings, "moon_shadow_alpha", 70))
        self.moon_shadow_offset_x = self._double_spin(-300.0, 300.0, getattr(self.settings, "moon_shadow_offset_x", 28.0), 1.0)
        self.moon_shadow_offset_y = self._double_spin(-300.0, 300.0, getattr(self.settings, "moon_shadow_offset_y", 38.0), 1.0)
        self.moon_shadow_angle = self._double_spin(-360.0, 360.0, getattr(self.settings, "moon_shadow_angle", 0.0), 1.0)
        self.moon_shadow_blur_radius = self._double_spin(4.0, 600.0, getattr(self.settings, "moon_shadow_blur_radius", 150.0), 5.0)
        f.addRow(lds_tr("月影透明度"), self.moon_shadow_alpha)
        f.addRow(lds_tr("影Xオフセット"), self.moon_shadow_offset_x)
        f.addRow(lds_tr("影Yオフセット"), self.moon_shadow_offset_y)
        f.addRow(lds_tr("月影角度"), self.moon_shadow_angle)
        f.addRow(lds_tr("影ぼかし半径"), self.moon_shadow_blur_radius)
        self._section(f, lds_tr("色"))
        self.moon_color = self._color_row_on(f, lds_tr("月色"), getattr(self.settings, "moon_color", "#FFF3C4"))
        self.moon_edge_color = self._color_row_on(f, lds_tr("月の縁色"), getattr(self.settings, "moon_edge_color", "#C9D7FF"))
        self.moonlight_color = self._color_row_on(f, lds_tr("月光色"), getattr(self.settings, "moonlight_color", "#CFE8FF"))
        self.moon_shadow_color = self._color_row_on(f, lds_tr("月影色"), getattr(self.settings, "moon_shadow_color", "#061028"))

    def build_settings(self):
        return EffectOverlaySettings(
            rain_enabled=self.rain_enabled.isChecked(),
            particles_enabled=self.particles_enabled.isChecked(),
            noise_enabled=self.noise_enabled.isChecked(),
            glow_enabled=self.glow_enabled.isChecked(),
            ripple_enabled=self.ripple_enabled.isChecked(),
            gpu_acceleration_enabled=self.gpu_acceleration_enabled.isChecked(),
            gpu_acceleration_prefer_opengl=self.gpu_acceleration_prefer_opengl.isChecked(),
            gpu_acceleration_smooth_pixmaps=self.gpu_acceleration_smooth_pixmaps.isChecked(),
            effect_frame_rate_enabled=self.effect_frame_rate_enabled.isChecked(),
            effect_frame_rate=self.effect_frame_rate.value(),
            mouse_ripple_enabled=self.mouse_ripple_enabled.isChecked(),
            mouse_flee_enabled=self.mouse_flee_enabled.isChecked(),
            mouse_glow_enabled=self.mouse_glow_enabled.isChecked(),
            particle_count=self.particle_count.value(),
            rain_count=self.rain_count.value(),
            glow_count=self.glow_count.value(),
            particle_color=self.particle_color.text().strip() or "#DDEBFF",
            rain_color=self.rain_color.text().strip() or "#9FD7FF",
            glow_color=self.glow_color.text().strip() or "#80FFCC",
            sakura_petals_enabled=self.sakura_petals_enabled.isChecked(),
            sakura_petal_count=self.sakura_petal_count.value(),
            sakura_petal_color=self.sakura_petal_color.text().strip() or "#FFD1E8",
            sakura_petal_edge_color=self.sakura_petal_edge_color.text().strip() or "#FF8FC7",
            sakura_petal_speed=self.sakura_petal_speed.value(),
            sakura_petal_sway=self.sakura_petal_sway.value(),
            sakura_petal_size=self.sakura_petal_size.value(),
            sakura_petal_surface_y=self.sakura_petal_surface_y.value(),
            sakura_petal_ripple_enabled=self.sakura_petal_ripple_enabled.isChecked(),
            sakura_petal_ripple_chance=self.sakura_petal_ripple_chance.value(),
            sakura_petal_ripple_min_radius=self.sakura_petal_ripple_min_radius.value(),
            sakura_petal_ripple_max_radius=self.sakura_petal_ripple_max_radius.value(),
            sunrise_enabled=self.sunrise_enabled.isChecked(),
            sunrise_angle=self.sunrise_angle.value(),
            sunrise_strength=self.sunrise_strength.value(),
            sunrise_warmth=self.sunrise_warmth.value(),
            sunrise_horizon_y=self.sunrise_horizon_y.value(),
            sunrise_spread=self.sunrise_spread.value(),
            sunrise_color_top=self.sunrise_color_top.text().strip() or "#1B2C64",
            sunrise_color_mid=self.sunrise_color_mid.text().strip() or "#FF8A5C",
            sunrise_color_horizon=self.sunrise_color_horizon.text().strip() or "#FFD08A",
            sun_enabled=self.sun_enabled.isChecked(),
            sunlight_enabled=self.sunlight_enabled.isChecked(),
            lens_flare_enabled=self.lens_flare_enabled.isChecked(),
            sun_x=self.sun_x.value(),
            sun_y=self.sun_y.value(),
            sun_radius=self.sun_radius.value(),
            sun_alpha=self.sun_alpha.value(),
            sun_angle=self.sun_angle.value(),
            sun_color=self.sun_color.text().strip() or "#FFD36E",
            sun_edge_color=self.sun_edge_color.text().strip() or "#FF7A3D",
            sunlight_angle=self.sunlight_angle.value(),
            sunlight_radius=self.sunlight_radius.value(),
            sunlight_alpha=self.sunlight_alpha.value(),
            sunlight_beam_width=self.sunlight_beam_width.value(),
            sunlight_color=self.sunlight_color.text().strip() or "#FFD08A",
            lens_flare_angle=self.lens_flare_angle.value(),
            lens_flare_alpha=self.lens_flare_alpha.value(),
            lens_flare_size=self.lens_flare_size.value(),
            lens_flare_count=self.lens_flare_count.value(),
            lens_flare_color=self.lens_flare_color.text().strip() or "#FFE2A6",
            moon_body_enabled=self.moon_body_enabled.isChecked(),
            moonlight_enabled=self.moonlight_enabled.isChecked(),
            moon_shadow_enabled=self.moon_shadow_enabled.isChecked(),
            moon_x=self.moon_x.value(),
            moon_y=self.moon_y.value(),
            moon_body_angle=self.moon_body_angle.value(),
            moon_radius=self.moon_radius.value(),
            moon_alpha=self.moon_alpha.value(),
            moon_color=self.moon_color.text().strip() or "#FFF3C4",
            moon_edge_color=self.moon_edge_color.text().strip() or "#C9D7FF",
            moon_crater_count=self.moon_crater_count.value(),
            moon_crater_alpha=self.moon_crater_alpha.value(),
            moonlight_radius=self.moonlight_radius.value(),
            moonlight_alpha=self.moonlight_alpha.value(),
            moonlight_color=self.moonlight_color.text().strip() or "#CFE8FF",
            moonlight_angle=self.moonlight_angle.value(),
            moonlight_beam_enabled=self.moonlight_beam_enabled.isChecked(),
            moonlight_beam_alpha=self.moonlight_beam_alpha.value(),
            moonlight_beam_width=self.moonlight_beam_width.value(),
            moon_shadow_alpha=self.moon_shadow_alpha.value(),
            moon_shadow_color=self.moon_shadow_color.text().strip() or "#061028",
            moon_shadow_offset_x=self.moon_shadow_offset_x.value(),
            moon_shadow_offset_y=self.moon_shadow_offset_y.value(),
            moon_shadow_angle=self.moon_shadow_angle.value(),
            moon_shadow_blur_radius=self.moon_shadow_blur_radius.value(),
            ripple_color=self.ripple_color.text().strip() or "#A8EFFF",
            rain_ripple_enabled=self.rain_ripple_enabled.isChecked(),
            rain_ripple_chance=self.rain_ripple_chance.value(),
            rain_ripple_surface_y=self.rain_ripple_surface_y.value(),
            rain_ripple_min_radius=self.rain_ripple_min_radius.value(),
            rain_ripple_max_radius_linked=self.rain_ripple_max_radius_linked.value(),
            rain_ripple_cooldown=self.rain_ripple_cooldown.value(),
            rain_drop_min_size=self.rain_drop_min_size.value(),
            rain_drop_max_size=self.rain_drop_max_size.value(),
            rain_drop_length_randomness=self.rain_drop_length_randomness.value(),
            rose_petals_enabled=self.rose_petals_enabled.isChecked(),
            rose_petal_ripple_enabled=self.rose_petal_ripple_enabled.isChecked(),
            rose_petal_count=self.rose_petal_count.value(),
            rose_petal_color=self.rose_petal_color.text().strip() or "#FF7AAE",
            rose_petal_edge_color=self.rose_petal_edge_color.text().strip() or "#FFD1E3",
            rose_petal_speed=self.rose_petal_speed.value(),
            rose_petal_sway=self.rose_petal_sway.value(),
            rose_petal_size=self.rose_petal_size.value(),
            rose_petal_alpha=self.rose_petal_alpha.value(),
            rose_petal_surface_y=self.rose_petal_surface_y.value(),
            rose_petal_ripple_chance=self.rose_petal_ripple_chance.value(),
            rose_petal_ripple_min_radius=self.rose_petal_ripple_min_radius.value(),
            rose_petal_ripple_max_radius=self.rose_petal_ripple_max_radius.value(),
            rose_petal_ripple_cooldown=self.rose_petal_ripple_cooldown.value(),
            rose_petal_rest_on_surface=self.rose_petal_rest_on_surface.isChecked(),
            rose_petal_roundness=self.rose_petal_roundness.value(),
            rose_petal_curl=self.rose_petal_curl.value(),
            rose_petal_shadow_alpha=self.rose_petal_shadow_alpha.value(),
            rose_petal_highlight_alpha=self.rose_petal_highlight_alpha.value(),
            rose_petal_vein_alpha=self.rose_petal_vein_alpha.value(),
            petal_night_enabled=self.petal_night_enabled.isChecked(),
            petal_night_tint_color=self.petal_night_tint_color.text().strip() or "#101A3A",
            petal_night_tint_strength=self.petal_night_tint_strength.value(),
            petal_shadow_enabled=self.petal_shadow_enabled.isChecked(),
            petal_outline_enabled=self.petal_outline_enabled.isChecked(),
            petal_outline_strength=self.petal_outline_strength.value(),
            petal_blizzard_enabled=self.petal_blizzard_enabled.isChecked(),
            petal_wind_strength=self.petal_wind_strength.value(),
            petal_wind_randomness=self.petal_wind_randomness.value(),
            petal_gust_interval=self.petal_gust_interval.value(),
            petal_gust_duration=self.petal_gust_duration.value(),
            petal_gust_strength=self.petal_gust_strength.value(),
            petal_mouse_flutter_enabled=self.petal_mouse_flutter_enabled.isChecked(),
            petal_mouse_flutter_strength=self.petal_mouse_flutter_strength.value(),
            rose_flowers_enabled=self.rose_flowers_enabled.isChecked(),
            rose_flower_count=self.rose_flower_count.value(),
            rose_flower_size=self.rose_flower_size.value(),
            rose_flower_speed=self.rose_flower_speed.value(),
            rose_flower_sway=self.rose_flower_sway.value(),
            rose_flower_surface_y=self.rose_flower_surface_y.value(),
            rose_flower_ripple_enabled=self.rose_flower_ripple_enabled.isChecked(),
            rose_flower_ripple_min_radius=self.rose_flower_ripple_min_radius.value(),
            rose_flower_ripple_max_radius=self.rose_flower_ripple_max_radius.value(),
            rose_petal_fade_on_surface=self.rose_petal_fade_on_surface.isChecked(),
            rose_petal_fade_duration=self.rose_petal_fade_duration.value(),
            rose_petal_fade_sink_distance=self.rose_petal_fade_sink_distance.value(),
            rose_petal_fade_spin=self.rose_petal_fade_spin.value(),
            blooming_roses_enabled=self.blooming_roses_enabled.isChecked(),
            blooming_rose_count=self.blooming_rose_count.value(),
            blooming_rose_size=self.blooming_rose_size.value(),
            blooming_rose_scatter_after=self.blooming_rose_scatter_after.value(),
            blooming_rose_life=self.blooming_rose_life.value(),
            blooming_rose_petal_count=self.blooming_rose_petal_count.value(),
            blooming_rose_respawn=self.blooming_rose_respawn.isChecked(),
            blooming_rose_color=self.blooming_rose_color.text().strip() or "#FF6FAE",
            blooming_rose_edge_color=self.blooming_rose_edge_color.text().strip() or "#FFD5E8",
            noise_color=self.noise_color.text().strip() or "#FFFFFF",
            mouse_glow_color=self.mouse_glow_color.text().strip() or "#80FFCC",
            particle_speed=self.particle_speed.value(),
            rain_speed=self.rain_speed.value(),
            glow_speed=self.glow_speed.value(),
            ripple_speed=self.ripple_speed.value(),
            particle_size=self.particle_size.value(),
            rain_length=self.rain_length.value(),
            glow_radius=self.glow_radius.value(),
            mouse_glow_radius=self.mouse_glow_radius.value(),
            ripple_max_radius=self.ripple_max_radius.value(),
            intensity=self.intensity.value(),
            noise_alpha=self.noise_alpha.value(),
            background_alpha=self.background_alpha.value(),

            snow_enabled=self.snow_enabled.isChecked(),
            snow_count=self.snow_count.value(),
            snow_speed=self.snow_speed.value(),
            snow_size=self.snow_size.value(),
            snow_alpha=self.snow_alpha.value(),
            snow_color=self.snow_color.text().strip() or "#F5FCFF",
            snow_edge_color=self.snow_edge_color.text().strip() or "#CFEFFF",
            snow_ripple_color=self.snow_ripple_color.text().strip() or "#DFFBFF",
            snow_ripple_enabled=self.snow_ripple_enabled.isChecked(),
            snow_ripple_chance=self.snow_ripple_chance.value(),
            snow_surface_y=self.snow_surface_y.value(),
            snow_accumulation_enabled=self.snow_accumulation_enabled.isChecked(),
            snow_accumulation_start_y=self.snow_accumulation_start_y.value(),
            snow_accumulation_max_depth=self.snow_accumulation_max_depth.value(),
            snow_accumulation_build_rate=self.snow_accumulation_build_rate.value(),
            snow_accumulation_column_width=self.snow_accumulation_column_width.value(),
            snow_accumulation_alpha=self.snow_accumulation_alpha.value(),
            snow_accumulation_mouse_remove_enabled=self.snow_accumulation_mouse_remove_enabled.isChecked(),
            snow_accumulation_remove_radius=self.snow_accumulation_remove_radius.value(),
            snow_accumulation_remove_strength=self.snow_accumulation_remove_strength.value(),
            snow_crystal_enabled=self.snow_crystal_enabled.isChecked(),
            snow_crystal_count=self.snow_crystal_count.value(),
            snow_crystal_speed=self.snow_crystal_speed.value(),
            snow_crystal_size=self.snow_crystal_size.value(),
            snow_crystal_alpha=self.snow_crystal_alpha.value(),
            snow_crystal_color=self.snow_crystal_color.text().strip() or "#EBFAFF",
            snow_crystal_edge_color=self.snow_crystal_edge_color.text().strip() or "#D8F4FF",
            snow_crystal_ripple_color=self.snow_crystal_ripple_color.text().strip() or "#E8FBFF",
            water_drop_color=self.water_drop_color.text().strip() or "#7DDCFF",
            water_drop_edge_color=self.water_drop_edge_color.text().strip() or "#D2F8FF",
            flame_core_color=self.flame_core_color.text().strip() or "#FFF58C",
            flame_mid_color=self.flame_mid_color.text().strip() or "#FF7823",
            flame_edge_color=self.flame_edge_color.text().strip() or "#FF1E00",
            water_spray_color=self.water_spray_color.text().strip() or "#82E1FF",
            water_spray_edge_color=self.water_spray_edge_color.text().strip() or "#D7FAFF",
            fireball_core_color=self.fireball_core_color.text().strip() or "#FFFFBE",
            fireball_mid_color=self.fireball_mid_color.text().strip() or "#FF7828",
            fireball_edge_color=self.fireball_edge_color.text().strip() or "#AA1400",
            fireball_trail_color=self.fireball_trail_color.text().strip() or "#FF5A14",
            snow_crystal_ripple_enabled=self.snow_crystal_ripple_enabled.isChecked(),
            snow_crystal_ripple_chance=self.snow_crystal_ripple_chance.value(),
            snow_crystal_surface_y=self.snow_crystal_surface_y.value(),
            bubble_enabled=self.bubble_enabled.isChecked(),
            bubble_count=self.bubble_count.value(),
            bubble_speed=self.bubble_speed.value(),
            bubble_size=self.bubble_size.value(),
            bubble_alpha=self.bubble_alpha.value(),
            flame_enabled=self.flame_enabled.isChecked(),
            flame_count=self.flame_count.value(),
            flame_speed=self.flame_speed.value(),
            flame_size=self.flame_size.value(),
            flame_alpha=self.flame_alpha.value(),
            water_spray_enabled=self.water_spray_enabled.isChecked(),
            water_spray_count=self.water_spray_count.value(),
            water_spray_speed=self.water_spray_speed.value(),
            water_spray_size=self.water_spray_size.value(),
            water_spray_alpha=self.water_spray_alpha.value(),
            fireball_enabled=self.fireball_enabled.isChecked(),
            fireball_count=self.fireball_count.value(),
            fireball_speed=self.fireball_speed.value(),
            fireball_size=self.fireball_size.value(),
            fireball_alpha=self.fireball_alpha.value(),
            shooting_star_enabled=self.shooting_star_enabled.isChecked(),
            shooting_star_count=self.shooting_star_count.value(),
            shooting_star_speed=self.shooting_star_speed.value(),
            shooting_star_size=self.shooting_star_size.value(),
            shooting_star_alpha=self.shooting_star_alpha.value(),
            meteor_shower_enabled=self.meteor_shower_enabled.isChecked(),
            meteor_shower_count=self.meteor_shower_count.value(),
            meteor_shower_speed=self.meteor_shower_speed.value(),
            meteor_shower_size=self.meteor_shower_size.value(),
            meteor_shower_alpha=self.meteor_shower_alpha.value(),
            balloon_enabled=self.balloon_enabled.isChecked(),
            balloon_count=self.balloon_count.value(),
            balloon_speed=self.balloon_speed.value(),
            balloon_size=self.balloon_size.value(),
            balloon_alpha=self.balloon_alpha.value(),
            star_sky_enabled=self.star_sky_enabled.isChecked(),
            star_sky_count=self.star_sky_count.value(),
            star_sky_speed=self.star_sky_speed.value(),
            star_sky_size=self.star_sky_size.value(),
            star_sky_alpha=self.star_sky_alpha.value(),
            star_sky_color=self.star_sky_color.text().strip() or "#F8FBFF",
            star_sky_secondary_color=self.star_sky_secondary_color.text().strip() or "#BFD8FF",
            milky_way_enabled=self.milky_way_enabled.isChecked(),
            milky_way_star_count=self.milky_way_star_count.value(),
            milky_way_alpha=self.milky_way_alpha.value(),
            milky_way_width=self.milky_way_width.value(),
            milky_way_angle=self.milky_way_angle.value(),
            milky_way_color=self.milky_way_color.text().strip() or "#BFD7FF",
            water_surface_enabled=self.water_surface_enabled.isChecked(),
            puddle_enabled=self.puddle_enabled.isChecked(),
            puddle_x=self.puddle_x.value(),
            puddle_y=self.puddle_y.value(),
            puddle_width=self.puddle_width.value(),
            puddle_height=self.puddle_height.value(),
            puddle_edge_softness=self.puddle_edge_softness.value(),
            puddle_count=self.puddle_count.value(),
            puddle_spread=self.puddle_spread.value(),
            puddles_json=getattr(self.settings, "puddles_json", ""),
            water_surface_alpha=self.water_surface_alpha.value(),
            water_surface_color=self.water_surface_color.text().strip() or "#4FC3FF",
            water_surface_highlight_color=self.water_surface_highlight_color.text().strip() or "#D8FAFF",
            water_surface_flow_angle=self.water_surface_flow_angle.value(),
            water_surface_flow_speed=self.water_surface_flow_speed.value(),
            water_surface_wave_count=self.water_surface_wave_count.value(),
            water_surface_wave_height=self.water_surface_wave_height.value(),
            water_surface_y=self.water_surface_y.value(),
            water_surface_depth=self.water_surface_depth.value(),
            water_depth_enabled=self.water_depth_enabled.isChecked(),
            water_depth_strength=self.water_depth_strength.value(),
            water_depth_haze_alpha=self.water_depth_haze_alpha.value(),
            water_depth_color=self.water_depth_color.text().strip() or "#1A5B70",
            water_morning_fog_enabled=self.water_morning_fog_enabled.isChecked(),
            water_morning_fog_follow_sunrise=self.water_morning_fog_follow_sunrise.isChecked(),
            water_morning_fog_strength=self.water_morning_fog_strength.value(),
            water_morning_fog_alpha=self.water_morning_fog_alpha.value(),
            water_morning_fog_height=self.water_morning_fog_height.value(),
            water_morning_fog_drift=self.water_morning_fog_drift.value(),
            water_morning_fog_color=self.water_morning_fog_color.text().strip() or "#E9F6FF",
            water_fish_enabled=self.water_fish_enabled.isChecked(),
            water_fish_count=self.water_fish_count.value(),
            water_fish_speed=self.water_fish_speed.value(),
            water_fish_size=self.water_fish_size.value(),
            water_fish_alpha=self.water_fish_alpha.value(),
            water_fish_color=self.water_fish_color.text().strip() or "#7FE7D1",
            water_fish_secondary_color=self.water_fish_secondary_color.text().strip() or "#D8FFF3",
            water_mirror_enabled=self.water_mirror_enabled.isChecked(),
            water_mirror_alpha=self.water_mirror_alpha.value(),
            water_mirror_blur=self.water_mirror_blur.value(),
            water_mirror_depth=self.water_mirror_depth.value(),
            water_mirror_wave=self.water_mirror_wave.value(),
            water_mirror_tint_alpha=self.water_mirror_tint_alpha.value(),
            water_mirror_reflect_effects_enabled=self.water_mirror_reflect_effects_enabled.isChecked(),
            water_mirror_reflect_widgets_enabled=self.water_mirror_reflect_widgets_enabled.isChecked(),
            water_mirror_reflect_snow=self.water_mirror_reflect_snow.isChecked(),
            water_mirror_reflect_snow_crystal=self.water_mirror_reflect_snow_crystal.isChecked(),
            water_mirror_reflect_petals=self.water_mirror_reflect_petals.isChecked(),
            water_mirror_reflect_bamboo=self.water_mirror_reflect_bamboo.isChecked(),
            water_mirror_reflect_shooting_star=self.water_mirror_reflect_shooting_star.isChecked(),
            water_mirror_reflect_meteor_shower=self.water_mirror_reflect_meteor_shower.isChecked(),
            water_mirror_reflect_rain=self.water_mirror_reflect_rain.isChecked(),
            ice_enabled=self.ice_enabled.isChecked(),
            ice_lightweight_enabled=self.ice_lightweight_enabled.isChecked(),
            ice_static_cache_enabled=self.ice_static_cache_enabled.isChecked(),
            ice_quality_scale=self.ice_quality_scale.value(),
            ice_max_facets=self.ice_max_facets.value(),
            ice_max_cracks=self.ice_max_cracks.value(),
            ice_max_bubbles=self.ice_max_bubbles.value(),
            ice_skip_reflected_effect_frames=self.ice_skip_reflected_effect_frames.value(),
            ice_mirror_skip_frames=self.ice_mirror_skip_frames.value(),
            ice_alpha=self.ice_alpha.value(),
            ice_color=self.ice_color.text().strip() or "#9BDDF2",
            ice_edge_color=self.ice_edge_color.text().strip() or "#E8FBFF",
            ice_highlight_color=self.ice_highlight_color.text().strip() or "#F7FFFF",
            ice_shadow_color=self.ice_shadow_color.text().strip() or "#2C6F93",
            ice_fog_color=self.ice_fog_color.text().strip() or "#EEF9FF",
            ice_size=self.ice_size.value(),
            ice_angle=self.ice_angle.value(),
            ice_x=self.ice_x.value(),
            ice_width=self.ice_width.value(),
            ice_y=self.ice_y.value(),
            ice_depth=self.ice_depth.value(),
            ice_crack_intensity=self.ice_crack_intensity.value(),
            ice_internal_bubble_intensity=self.ice_internal_bubble_intensity.value(),
            ice_glacier_roughness=self.ice_glacier_roughness.value(),
            ice_mirror_enabled=self.ice_mirror_enabled.isChecked(),
            ice_mirror_alpha=self.ice_mirror_alpha.value(),
            ice_mirror_blur=self.ice_mirror_blur.value(),
            ice_mirror_depth=self.ice_mirror_depth.value(),
            ice_mirror_wave=self.ice_mirror_wave.value(),
            ice_mirror_tint_alpha=self.ice_mirror_tint_alpha.value(),
            ice_reflect_effects_enabled=self.ice_reflect_effects_enabled.isChecked(),
            ice_reflect_widgets_enabled=self.ice_reflect_widgets_enabled.isChecked(),
            ice_reflect_snow=self.ice_reflect_snow.isChecked(),
            ice_reflect_snow_crystal=self.ice_reflect_snow_crystal.isChecked(),
            ice_reflect_petals=self.ice_reflect_petals.isChecked(),
            ice_reflect_bamboo=self.ice_reflect_bamboo.isChecked(),
            ice_reflect_shooting_star=self.ice_reflect_shooting_star.isChecked(),
            ice_reflect_meteor_shower=self.ice_reflect_meteor_shower.isChecked(),
            ice_reflect_rain=self.ice_reflect_rain.isChecked(),
            ice_fog_enabled=self.ice_fog_enabled.isChecked(),
            ice_fog_alpha=self.ice_fog_alpha.value(),
            ice_fog_height=self.ice_fog_height.value(),
            ice_fog_drift=self.ice_fog_drift.value(),
            bamboo_grove_enabled=self.bamboo_grove_enabled.isChecked(),
            bamboo_count=self.bamboo_count.value(),
            bamboo_thickness=self.bamboo_thickness.value(),
            bamboo_angle=self.bamboo_angle.value(),
            bamboo_bend=self.bamboo_bend.value(),
            bamboo_height=self.bamboo_height.value(),
            bamboo_alpha=self.bamboo_alpha.value(),
            bamboo_leaf_density=self.bamboo_leaf_density.value(),
            bamboo_depth_strength=self.bamboo_depth_strength.value(),
            bamboo_layer_spread=self.bamboo_layer_spread.value(),
            bamboo_highlight_alpha=self.bamboo_highlight_alpha.value(),
            bamboo_ground_shadow_enabled=self.bamboo_ground_shadow_enabled.isChecked(),
            bamboo_atmosphere_enabled=self.bamboo_atmosphere_enabled.isChecked(),
            bamboo_stalk_color=self.bamboo_stalk_color.text().strip() or "#3EA65A",
            bamboo_shadow_color=self.bamboo_shadow_color.text().strip() or "#1F6F3B",
            bamboo_node_color=self.bamboo_node_color.text().strip() or "#B7E37A",
            bamboo_leaf_color=self.bamboo_leaf_color.text().strip() or "#5ED06C",
            water_drop_enabled=self.water_drop_enabled.isChecked(),
            water_drop_count=self.water_drop_count.value(),
            water_drop_speed=self.water_drop_speed.value(),
            water_drop_size=self.water_drop_size.value(),
            water_drop_alpha=self.water_drop_alpha.value(),
            water_drop_ripple_enabled=self.water_drop_ripple_enabled.isChecked(),
            water_drop_ripple_chance=self.water_drop_ripple_chance.value(),
            water_drop_surface_y=self.water_drop_surface_y.value(),
        )

    def apply_to_config(self):
        settings = self.build_settings()
        set_effect_overlay_settings(self.cfg, settings)

        try:
            self.widget._particles.clear()
            self.widget._rain.clear()
            self.widget._ripples.clear()
            self.widget._rose_petals.clear()
            self.widget._extra_effects.clear()
        except Exception:
            pass

        try:
            self.widget._last_petal_ripple_time = 0.0
        except Exception:
            pass
        try:
            self.widget._rose_petals.clear()
        except Exception:
            pass

        try:
            self.widget._last_petal_ripple_time = 0.0
        except Exception:
            pass
        try:
            self.widget._rose_flowers.clear()
        except Exception:
            pass
        try:
            self.widget._blooming_roses.clear()
        except Exception:
            pass
        try:
            self.widget._rose_petals.clear()
        except Exception:
            pass
        try:
            self.widget._last_flower_ripple_time = 0.0
        except Exception:
            pass
        try:
            self.widget._sakura_petals.clear()
        except Exception:
            pass
        try:
            self.widget._last_sakura_ripple_time = 0.0
            self.widget._last_sakura_tree_emit_time = 0.0
        except Exception:
            pass
        try:
            if hasattr(self.widget, "_extra_effects"):
                self.widget._extra_effects.clear()
            self.widget._last_extra_ripple_time = 0.0
        except Exception:
            pass
        try:
            if hasattr(self.widget, "_ice_surface_cache_signature"):
                self.widget._ice_surface_cache_signature = None
                self.widget._ice_surface_cache_image = None
                self.widget._ice_reflected_effects_cache_signature = None
                self.widget._ice_reflected_effects_cache_image = None
        except Exception:
            pass
        try:
            if hasattr(self.widget, "_water_fish"):
                self.widget._water_fish.clear()
            self.widget._water_fish_rect_key = None
            self.widget._last_water_fish_update = 0.0
        except Exception:
            pass
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "canvas"):
                parent.canvas.save_config()
                parent.canvas.update()
        except Exception:
            pass

    def accept_with_apply(self):
        self.apply_to_config()
        self.accept()


@dataclass
class EffectOverlaySettings:
    rain_enabled: bool = True
    particles_enabled: bool = True
    noise_enabled: bool = False
    glow_enabled: bool = False
    ripple_enabled: bool = False
    gpu_acceleration_enabled: bool = True
    gpu_acceleration_prefer_opengl: bool = True
    gpu_acceleration_smooth_pixmaps: bool = True
    effect_frame_rate_enabled: bool = True
    effect_frame_rate: int = 60

    mouse_ripple_enabled: bool = True
    mouse_flee_enabled: bool = True
    mouse_glow_enabled: bool = True

    particle_count: int = 120
    rain_count: int = 90
    glow_count: int = 4

    particle_color: str = "#DDEBFF"
    rain_color: str = "#9FD7FF"
    glow_color: str = "#80FFCC"
    ripple_color: str = "#A8EFFF"
    noise_color: str = "#FFFFFF"
    mouse_glow_color: str = "#80FFCC"

    particle_speed: float = 0.55
    rain_speed: float = 1.0
    glow_speed: float = 0.55
    ripple_speed: float = 1.0

    particle_size: float = 2.0
    rain_length: float = 16.0
    glow_radius: float = 160.0
    mouse_glow_radius: float = 140.0
    ripple_max_radius: float = 180.0

    intensity: float = 1.0
    noise_alpha: int = 24
    background_alpha: int = 0

    rain_ripple_enabled: bool = True
    rain_ripple_chance: float = 0.55
    rain_ripple_surface_y: float = 0.82
    rain_ripple_min_radius: float = 24.0
    rain_ripple_max_radius_linked: float = 92.0
    rain_ripple_cooldown: float = 0.025

    rain_drop_min_size: float = 1.0
    rain_drop_max_size: float = 2.4
    rain_drop_length_randomness: float = 0.55

    rose_petals_enabled: bool = True
    rose_petal_ripple_enabled: bool = True
    rose_petal_count: int = 24
    rose_petal_color: str = "#FF7AAE"
    rose_petal_edge_color: str = "#FFD1E3"
    rose_petal_speed: float = 0.35
    rose_petal_sway: float = 1.0
    rose_petal_size: float = 16.0
    rose_petal_alpha: int = 210
    rose_petal_surface_y: float = 0.84
    rose_petal_ripple_chance: float = 0.9
    rose_petal_ripple_min_radius: float = 36.0
    rose_petal_ripple_max_radius: float = 130.0
    rose_petal_ripple_cooldown: float = 0.04
    rose_petal_rest_on_surface: bool = False

    rose_petal_roundness: float = 0.72
    rose_petal_curl: float = 0.42
    rose_petal_shadow_alpha: int = 72
    rose_petal_highlight_alpha: int = 115
    rose_petal_vein_alpha: int = 95
    petal_night_enabled: bool = False
    petal_night_tint_color: str = "#101A3A"
    petal_night_tint_strength: float = 0.35
    petal_shadow_enabled: bool = False
    petal_outline_enabled: bool = True
    petal_outline_strength: float = 1.35
    petal_blizzard_enabled: bool = False
    petal_wind_strength: float = 1.0
    petal_wind_randomness: float = 0.55
    petal_gust_interval: float = 4.0
    petal_gust_duration: float = 1.15
    petal_gust_strength: float = 1.45
    petal_mouse_flutter_enabled: bool = True
    petal_mouse_flutter_strength: float = 1.0

    rose_flowers_enabled: bool = True
    rose_flower_count: int = 5
    rose_flower_size: float = 42.0
    rose_flower_speed: float = 0.22
    rose_flower_sway: float = 0.85
    rose_flower_alpha: int = 220
    rose_flower_surface_y: float = 0.84
    rose_flower_ripple_enabled: bool = True
    rose_flower_ripple_chance: float = 1.0
    rose_flower_ripple_min_radius: float = 80.0
    rose_flower_ripple_max_radius: float = 220.0
    rose_flower_ripple_cooldown: float = 0.12

    blooming_roses_enabled: bool = True
    blooming_rose_count: int = 2
    blooming_rose_size: float = 86.0
    blooming_rose_life: float = 7.5
    blooming_rose_scatter_after: float = 3.0
    blooming_rose_petal_count: int = 34
    blooming_rose_respawn: bool = True
    blooming_rose_alpha: int = 230
    blooming_rose_color: str = "#FF6FAE"
    blooming_rose_edge_color: str = "#FFD5E8"

    sakura_petals_enabled: bool = True
    sakura_petal_count: int = 80
    sakura_petal_color: str = "#FFD1E8"
    sakura_petal_edge_color: str = "#FF8FC7"
    sakura_petal_speed: float = 0.32
    sakura_petal_sway: float = 1.15
    sakura_petal_size: float = 9.0
    sakura_petal_alpha: int = 210
    sakura_petal_surface_y: float = 0.84
    sakura_petal_ripple_enabled: bool = True
    sakura_petal_ripple_chance: float = 0.65
    sakura_petal_ripple_min_radius: float = 22.0
    sakura_petal_ripple_max_radius: float = 88.0
    sakura_petal_ripple_cooldown: float = 0.025

    sunrise_enabled: bool = False
    sunrise_angle: float = 0.0
    sunrise_strength: float = 0.65
    sunrise_warmth: float = 0.72
    sunrise_horizon_y: float = 0.72
    sunrise_spread: float = 0.62
    sunrise_color_top: str = "#1B2C64"
    sunrise_color_mid: str = "#FF8A5C"
    sunrise_color_horizon: str = "#FFD08A"
    sun_enabled: bool = False
    sunlight_enabled: bool = False
    lens_flare_enabled: bool = False
    sun_x: float = 0.22
    sun_y: float = 0.22
    sun_radius: float = 82.0
    sun_alpha: int = 235
    sun_angle: float = 0.0
    sun_color: str = "#FFD36E"
    sun_edge_color: str = "#FF7A3D"
    sunlight_angle: float = 18.0
    sunlight_radius: float = 420.0
    sunlight_alpha: int = 92
    sunlight_beam_width: float = 0.38
    sunlight_color: str = "#FFD08A"
    lens_flare_angle: float = 18.0
    lens_flare_alpha: int = 128
    lens_flare_size: float = 1.0
    lens_flare_count: int = 6
    lens_flare_color: str = "#FFE2A6"
    moon_body_enabled: bool = False
    moonlight_enabled: bool = False
    moon_shadow_enabled: bool = False
    moon_x: float = 0.78
    moon_y: float = 0.18
    moon_body_angle: float = 0.0
    moon_radius: float = 74.0
    moon_alpha: int = 230
    moon_color: str = "#FFF3C4"
    moon_edge_color: str = "#C9D7FF"
    moon_crater_count: int = 9
    moon_crater_alpha: int = 54
    moonlight_radius: float = 260.0
    moonlight_alpha: int = 82
    moonlight_color: str = "#CFE8FF"
    moonlight_angle: float = 0.0
    moonlight_beam_enabled: bool = True
    moonlight_beam_alpha: int = 44
    moonlight_beam_width: float = 0.34
    moon_shadow_alpha: int = 70
    moon_shadow_color: str = "#061028"
    moon_shadow_offset_x: float = 28.0
    moon_shadow_offset_y: float = 38.0
    moon_shadow_angle: float = 0.0
    moon_shadow_blur_radius: float = 150.0
    sakura_tree_enabled: bool = True
    sakura_tree_x: float = 0.15
    sakura_tree_ground_y: float = 0.92
    sakura_tree_scale: float = 1.0
    sakura_tree_alpha: int = 225
    sakura_tree_trunk_color: str = "#5B342E"
    sakura_tree_branch_color: str = "#7B4A42"
    sakura_tree_blossom_color: str = "#FFD1E8"
    sakura_tree_blossom_edge_color: str = "#FF9FCC"
    sakura_tree_petal_emit_enabled: bool = True
    sakura_tree_petal_emit_rate: float = 0.55
    sakura_tree_petal_emit_burst: int = 2

    sakura_tree_grand_mode: bool = True
    sakura_tree_height_ratio: float = 0.88
    sakura_tree_width_ratio: float = 0.68
    sakura_tree_trunk_thickness: float = 2.25
    sakura_tree_root_spread: float = 1.45
    sakura_tree_bark_detail: float = 0.85
    sakura_tree_branch_spread: float = 1.35
    sakura_tree_canopy_density: int = 12
    sakura_tree_canopy_opacity: float = 0.78
    sakura_tree_canopy_layering: float = 1.0
    sakura_tree_fine_branch_alpha: int = 150

    sakura_tree_realistic_blossoms: bool = True
    sakura_tree_blossom_rosette_count: int = 90
    sakura_tree_blossom_rosette_size: float = 13.0
    sakura_tree_blossom_rosette_layers: int = 3
    sakura_tree_blossom_rosette_opacity: float = 0.86
    sakura_tree_blossom_center_color: str = "#FFF2A8"
    sakura_tree_blossom_shadow_color: str = "#D96A9A"
    sakura_tree_blossom_highlight_alpha: int = 105

    rose_petal_fade_on_surface: bool = True
    rose_petal_fade_duration: float = 0.85
    rose_petal_fade_sink_distance: float = 10.0
    rose_petal_fade_spin: float = 0.35


    snow_enabled: bool = False
    snow_count: int = 90
    snow_speed: float = 0.18
    snow_size: float = 4.5
    snow_alpha: int = 210
    snow_color: str = "#F5FCFF"
    snow_edge_color: str = "#CFEFFF"
    snow_ripple_color: str = "#DFFBFF"
    snow_ripple_enabled: bool = True
    snow_ripple_chance: float = 0.38
    snow_surface_y: float = 0.86
    snow_accumulation_enabled: bool = False
    snow_accumulation_start_y: float = 1.0
    snow_accumulation_max_depth: float = 1.0
    snow_accumulation_build_rate: float = 7.0
    snow_accumulation_column_width: float = 7.0
    snow_accumulation_alpha: int = 230
    snow_accumulation_mouse_remove_enabled: bool = True
    snow_accumulation_remove_radius: float = 58.0
    snow_accumulation_remove_strength: float = 72.0
    snow_crystal_enabled: bool = False
    snow_crystal_count: int = 22
    snow_crystal_speed: float = 0.12
    snow_crystal_size: float = 15.0
    snow_crystal_alpha: int = 220
    snow_crystal_color: str = "#EBFAFF"
    snow_crystal_edge_color: str = "#D8F4FF"
    snow_crystal_ripple_color: str = "#E8FBFF"
    water_drop_color: str = "#7DDCFF"
    water_drop_edge_color: str = "#D2F8FF"
    flame_core_color: str = "#FFF58C"
    flame_mid_color: str = "#FF7823"
    flame_edge_color: str = "#FF1E00"
    water_spray_color: str = "#82E1FF"
    water_spray_edge_color: str = "#D7FAFF"
    fireball_core_color: str = "#FFFFBE"
    fireball_mid_color: str = "#FF7828"
    fireball_edge_color: str = "#AA1400"
    fireball_trail_color: str = "#FF5A14"
    snow_crystal_ripple_enabled: bool = True
    snow_crystal_ripple_chance: float = 0.55
    snow_crystal_surface_y: float = 0.86
    bubble_enabled: bool = False
    bubble_count: int = 42
    bubble_speed: float = 0.26
    bubble_size: float = 12.0
    bubble_alpha: int = 150
    flame_enabled: bool = False
    flame_count: int = 60
    flame_speed: float = 0.55
    flame_size: float = 22.0
    flame_alpha: int = 210
    water_spray_enabled: bool = False
    water_spray_count: int = 64
    water_spray_speed: float = 0.75
    water_spray_size: float = 6.0
    water_spray_alpha: int = 190
    fireball_enabled: bool = False
    fireball_count: int = 10
    fireball_speed: float = 0.34
    fireball_size: float = 20.0
    fireball_alpha: int = 225
    shooting_star_enabled: bool = False
    shooting_star_count: int = 3
    shooting_star_speed: float = 0.8
    shooting_star_size: float = 18.0
    shooting_star_alpha: int = 230
    meteor_shower_enabled: bool = False
    meteor_shower_count: int = 18
    meteor_shower_speed: float = 0.9
    meteor_shower_size: float = 12.0
    meteor_shower_alpha: int = 220
    balloon_enabled: bool = False
    balloon_count: int = 12
    balloon_speed: float = 0.20
    balloon_size: float = 34.0
    balloon_alpha: int = 220
    star_sky_enabled: bool = False
    star_sky_count: int = 360
    star_sky_speed: float = 0.35
    star_sky_size: float = 1.6
    star_sky_alpha: int = 220
    star_sky_color: str = "#F8FBFF"
    star_sky_secondary_color: str = "#BFD8FF"
    milky_way_enabled: bool = False
    milky_way_star_count: int = 220
    milky_way_alpha: int = 120
    milky_way_width: float = 0.22
    milky_way_angle: float = -18.0
    milky_way_color: str = "#BFD7FF"
    water_surface_enabled: bool = False
    water_surface_alpha: int = 92
    water_surface_color: str = "#4FC3FF"
    water_surface_highlight_color: str = "#D8FAFF"
    water_surface_flow_angle: float = 0.0
    water_surface_flow_speed: float = 0.55
    water_surface_wave_count: int = 14
    water_surface_wave_height: float = 12.0
    water_surface_y: float = 0.58
    water_surface_depth: float = 0.42
    water_depth_enabled: bool = True
    water_depth_strength: float = 0.75
    water_depth_haze_alpha: int = 48
    water_depth_color: str = "#1A5B70"
    water_morning_fog_enabled: bool = True
    water_morning_fog_follow_sunrise: bool = True
    water_morning_fog_strength: float = 0.65
    water_morning_fog_alpha: int = 95
    water_morning_fog_height: float = 0.22
    water_morning_fog_drift: float = 0.35
    water_morning_fog_color: str = "#E9F6FF"
    water_fish_enabled: bool = True
    water_fish_count: int = 4
    water_fish_speed: float = 0.28
    water_fish_size: float = 24.0
    water_fish_alpha: int = 175
    water_fish_color: str = "#7FE7D1"
    water_fish_secondary_color: str = "#D8FFF3"
    water_mirror_enabled: bool = False
    water_mirror_alpha: int = 110
    water_mirror_blur: float = 5.0
    water_mirror_depth: float = 0.65
    water_mirror_wave: float = 7.0
    water_mirror_tint_alpha: int = 58
    water_mirror_reflect_effects_enabled: bool = True
    water_mirror_reflect_widgets_enabled: bool = True
    water_mirror_reflect_snow: bool = True
    water_mirror_reflect_snow_crystal: bool = True
    water_mirror_reflect_petals: bool = True
    water_mirror_reflect_bamboo: bool = True
    water_mirror_reflect_shooting_star: bool = True
    water_mirror_reflect_meteor_shower: bool = True
    water_mirror_reflect_rain: bool = True
    puddle_enabled: bool = False
    puddle_x: float = 0.50
    puddle_y: float = 0.84
    puddle_width: float = 0.72
    puddle_height: float = 0.22
    puddle_edge_softness: float = 0.18
    puddle_count: int = 5
    puddle_spread: float = 0.72
    puddles_json: str = ""
    ice_enabled: bool = False
    ice_lightweight_enabled: bool = True
    ice_static_cache_enabled: bool = True
    ice_quality_scale: float = 0.58
    ice_max_facets: int = 72
    ice_max_cracks: int = 16
    ice_max_bubbles: int = 34
    ice_skip_reflected_effect_frames: int = 2
    ice_mirror_skip_frames: int = 2
    ice_alpha: int = 178
    ice_color: str = "#9BDDF2"
    ice_edge_color: str = "#E8FBFF"
    ice_highlight_color: str = "#F7FFFF"
    ice_shadow_color: str = "#2C6F93"
    ice_fog_color: str = "#EEF9FF"
    ice_size: float = 185.0
    ice_angle: float = -6.0
    ice_x: float = 0.50
    ice_width: float = 1.00
    ice_y: float = 0.58
    ice_depth: float = 0.42
    ice_crack_intensity: float = 0.46
    ice_internal_bubble_intensity: float = 0.36
    ice_glacier_roughness: float = 0.55
    ice_mirror_enabled: bool = True
    ice_mirror_alpha: int = 118
    ice_mirror_blur: float = 3.5
    ice_mirror_depth: float = 0.68
    ice_mirror_wave: float = 2.2
    ice_mirror_tint_alpha: int = 70
    ice_reflect_effects_enabled: bool = True
    ice_reflect_widgets_enabled: bool = True
    ice_reflect_snow: bool = True
    ice_reflect_snow_crystal: bool = True
    ice_reflect_petals: bool = True
    ice_reflect_bamboo: bool = True
    ice_reflect_shooting_star: bool = True
    ice_reflect_meteor_shower: bool = True
    ice_reflect_rain: bool = True
    ice_fog_enabled: bool = True
    ice_fog_alpha: int = 72
    ice_fog_height: float = 0.24
    ice_fog_drift: float = 0.30
    bamboo_grove_enabled: bool = False
    bamboo_count: int = 12
    bamboo_thickness: float = 16.0
    bamboo_angle: float = 0.0
    bamboo_bend: float = 0.32
    bamboo_height: float = 0.92
    bamboo_alpha: int = 230
    bamboo_leaf_density: int = 4
    bamboo_depth_strength: float = 0.85
    bamboo_layer_spread: float = 0.42
    bamboo_highlight_alpha: int = 96
    bamboo_ground_shadow_enabled: bool = True
    bamboo_atmosphere_enabled: bool = True
    bamboo_stalk_color: str = "#3EA65A"
    bamboo_shadow_color: str = "#1F6F3B"
    bamboo_node_color: str = "#B7E37A"
    bamboo_leaf_color: str = "#5ED06C"
    water_drop_enabled: bool = False
    water_drop_count: int = 55
    water_drop_speed: float = 0.48
    water_drop_size: float = 8.0
    water_drop_alpha: int = 210
    water_drop_ripple_enabled: bool = True
    water_drop_ripple_chance: float = 0.75
    water_drop_surface_y: float = 0.86
    def to_dict(self):
        return asdict(self)

@dataclass
class FallingRoseFlower:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    rotation: float
    rotation_speed: float
    sway_phase: float
    alpha: float
    seed: float


@dataclass
class BloomingRose:
    x: float
    y: float
    size: float
    created_at: float
    scatter_after: float
    life: float
    petal_count: int
    seed: float
    scattered: bool = False

@dataclass
class EffectParticle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    alpha: float
    seed: float


@dataclass
class EffectRipple:
    x: float
    y: float
    created_at: float
    max_radius: float
    color: str
    speed: float = 1.0

@dataclass
class SakuraPetal:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    rotation: float
    rotation_speed: float
    sway_phase: float
    alpha: float
    seed: float
    from_tree: bool = False

DEFAULT_EFFECT_OVERLAY_SETTINGS = LIGHTWEIGHT_ROSE_PETAL_DEFAULT_SETTINGS.copy()


def ensure_effect_overlay_fields(cfg):
    if not hasattr(cfg, "effects_json") or not getattr(cfg, "effects_json", ""):
        cfg.effects_json = json.dumps(LIGHTWEIGHT_ROSE_PETAL_DEFAULT_SETTINGS, ensure_ascii=False)
    if not hasattr(cfg, "effects_follow_mouse"):
        cfg.effects_follow_mouse = True


def get_effect_overlay_settings(cfg) -> EffectOverlaySettings:
    ensure_effect_overlay_fields(cfg)
    raw = getattr(cfg, "effects_json", "") or "{}"

    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    if not isinstance(data, dict):
        data = {}

    defaults = DEFAULT_EFFECT_OVERLAY_SETTINGS.copy()
    defaults.update(data)

    return EffectOverlaySettings(
        rain_enabled=bool(defaults.get("rain_enabled", True)),
        particles_enabled=bool(defaults.get("particles_enabled", True)),
        noise_enabled=bool(defaults.get("noise_enabled", False)),
        glow_enabled=bool(defaults.get("glow_enabled", True)),
        ripple_enabled=bool(defaults.get("ripple_enabled", True)),
        gpu_acceleration_enabled=bool(defaults.get("gpu_acceleration_enabled", True)),
        gpu_acceleration_prefer_opengl=bool(defaults.get("gpu_acceleration_prefer_opengl", True)),
        gpu_acceleration_smooth_pixmaps=bool(defaults.get("gpu_acceleration_smooth_pixmaps", True)),
        effect_frame_rate_enabled=bool(defaults.get("effect_frame_rate_enabled", True)),
        effect_frame_rate=max(1, min(240, int(defaults.get("effect_frame_rate", 60)))),
        mouse_ripple_enabled=bool(defaults.get("mouse_ripple_enabled", True)),
        mouse_flee_enabled=bool(defaults.get("mouse_flee_enabled", True)),
        mouse_glow_enabled=bool(defaults.get("mouse_glow_enabled", True)),
        particle_count=max(0, int(defaults.get("particle_count", 120))),
        rain_count=max(0, int(defaults.get("rain_count", 90))),
        glow_count=max(0, int(defaults.get("glow_count", 4))),
        particle_color=str(defaults.get("particle_color", "#DDEBFF")),
        rain_color=str(defaults.get("rain_color", "#9FD7FF")),
        glow_color=str(defaults.get("glow_color", "#80FFCC")),
        ripple_color=str(defaults.get("ripple_color", "#A8EFFF")),
        noise_color=str(defaults.get("noise_color", "#FFFFFF")),
        mouse_glow_color=str(defaults.get("mouse_glow_color", "#80FFCC")),
        particle_speed=float(defaults.get("particle_speed", 0.55)),
        rain_speed=float(defaults.get("rain_speed", 1.0)),
        glow_speed=float(defaults.get("glow_speed", 0.55)),
        ripple_speed=float(defaults.get("ripple_speed", 1.0)),
        particle_size=float(defaults.get("particle_size", 2.0)),
        rain_length=float(defaults.get("rain_length", 16.0)),
        glow_radius=float(defaults.get("glow_radius", 160.0)),
        mouse_glow_radius=float(defaults.get("mouse_glow_radius", 140.0)),
        ripple_max_radius=float(defaults.get("ripple_max_radius", 180.0)),
        intensity=float(defaults.get("intensity", 1.0)),
        noise_alpha=max(0, min(255, int(defaults.get("noise_alpha", 24)))),
        background_alpha=max(0, min(255, int(defaults.get("background_alpha", 0)))),
        rain_ripple_enabled=bool(defaults.get("rain_ripple_enabled", True)),
        rain_ripple_chance=float(defaults.get("rain_ripple_chance", 0.55)),
        rain_ripple_surface_y=float(defaults.get("rain_ripple_surface_y", 0.82)),
        rain_ripple_min_radius=float(defaults.get("rain_ripple_min_radius", 24.0)),
        rain_ripple_max_radius_linked=float(defaults.get("rain_ripple_max_radius_linked", 92.0)),
        rain_ripple_cooldown=float(defaults.get("rain_ripple_cooldown", 0.025)),
        rain_drop_min_size=float(defaults.get("rain_drop_min_size", 1.0)),
        rain_drop_max_size=float(defaults.get("rain_drop_max_size", 2.4)),
        rain_drop_length_randomness=float(defaults.get("rain_drop_length_randomness", 0.55)),
        rose_petals_enabled=bool(defaults.get("rose_petals_enabled", True)),
        rose_petal_ripple_enabled=bool(defaults.get("rose_petal_ripple_enabled", True)),
        rose_petal_count=max(0, int(defaults.get("rose_petal_count", 24))),
        rose_petal_color=str(defaults.get("rose_petal_color", "#FF7AAE")),
        rose_petal_edge_color=str(defaults.get("rose_petal_edge_color", "#FFD1E3")),
        rose_petal_speed=float(defaults.get("rose_petal_speed", 0.35)),
        rose_petal_sway=float(defaults.get("rose_petal_sway", 1.0)),
        rose_petal_size=float(defaults.get("rose_petal_size", 16.0)),
        rose_petal_alpha=max(0, min(255, int(defaults.get("rose_petal_alpha", 210)))),
        rose_petal_surface_y=float(defaults.get("rose_petal_surface_y", 0.84)),
        rose_petal_ripple_chance=float(defaults.get("rose_petal_ripple_chance", 0.9)),
        rose_petal_ripple_min_radius=float(defaults.get("rose_petal_ripple_min_radius", 36.0)),
        rose_petal_ripple_max_radius=float(defaults.get("rose_petal_ripple_max_radius", 130.0)),
        rose_petal_ripple_cooldown=float(defaults.get("rose_petal_ripple_cooldown", 0.04)),
        rose_petal_rest_on_surface=bool(defaults.get("rose_petal_rest_on_surface", False)),
        rose_petal_roundness=float(defaults.get("rose_petal_roundness", 0.72)),
        rose_petal_curl=float(defaults.get("rose_petal_curl", 0.42)),
        rose_petal_shadow_alpha=max(0, min(255, int(defaults.get("rose_petal_shadow_alpha", 72)))),
        rose_petal_highlight_alpha=max(0, min(255, int(defaults.get("rose_petal_highlight_alpha", 115)))),
        rose_petal_vein_alpha=max(0, min(255, int(defaults.get("rose_petal_vein_alpha", 95)))),
        petal_night_enabled=bool(defaults.get("petal_night_enabled", False)),
        petal_night_tint_color=str(defaults.get("petal_night_tint_color", "#101A3A")),
        petal_night_tint_strength=float(defaults.get("petal_night_tint_strength", 0.35)),
        petal_shadow_enabled=bool(defaults.get("petal_shadow_enabled", False)),
        petal_outline_enabled=bool(defaults.get("petal_outline_enabled", True)),
        petal_outline_strength=float(defaults.get("petal_outline_strength", 1.35)),
        petal_blizzard_enabled=bool(defaults.get("petal_blizzard_enabled", False)),
        petal_wind_strength=float(defaults.get("petal_wind_strength", 1.0)),
        petal_wind_randomness=float(defaults.get("petal_wind_randomness", 0.55)),
        petal_gust_interval=float(defaults.get("petal_gust_interval", 4.0)),
        petal_gust_duration=float(defaults.get("petal_gust_duration", 1.15)),
        petal_gust_strength=float(defaults.get("petal_gust_strength", 1.45)),
        petal_mouse_flutter_enabled=bool(defaults.get("petal_mouse_flutter_enabled", True)),
        petal_mouse_flutter_strength=float(defaults.get("petal_mouse_flutter_strength", 1.0)),
        rose_flowers_enabled=bool(defaults.get("rose_flowers_enabled", True)),
        rose_flower_count=max(0, int(defaults.get("rose_flower_count", 5))),
        rose_flower_size=float(defaults.get("rose_flower_size", 42.0)),
        rose_flower_speed=float(defaults.get("rose_flower_speed", 0.22)),
        rose_flower_sway=float(defaults.get("rose_flower_sway", 0.85)),
        rose_flower_alpha=max(0, min(255, int(defaults.get("rose_flower_alpha", 220)))),
        rose_flower_surface_y=float(defaults.get("rose_flower_surface_y", 0.84)),
        rose_flower_ripple_enabled=bool(defaults.get("rose_flower_ripple_enabled", True)),
        rose_flower_ripple_chance=float(defaults.get("rose_flower_ripple_chance", 1.0)),
        rose_flower_ripple_min_radius=float(defaults.get("rose_flower_ripple_min_radius", 80.0)),
        rose_flower_ripple_max_radius=float(defaults.get("rose_flower_ripple_max_radius", 220.0)),
        rose_flower_ripple_cooldown=float(defaults.get("rose_flower_ripple_cooldown", 0.12)),
        blooming_roses_enabled=bool(defaults.get("blooming_roses_enabled", True)),
        blooming_rose_count=max(0, int(defaults.get("blooming_rose_count", 2))),
        blooming_rose_size=float(defaults.get("blooming_rose_size", 86.0)),
        blooming_rose_life=float(defaults.get("blooming_rose_life", 7.5)),
        blooming_rose_scatter_after=float(defaults.get("blooming_rose_scatter_after", 3.0)),
        blooming_rose_petal_count=max(0, int(defaults.get("blooming_rose_petal_count", 34))),
        blooming_rose_respawn=bool(defaults.get("blooming_rose_respawn", True)),
        blooming_rose_alpha=max(0, min(255, int(defaults.get("blooming_rose_alpha", 230)))),
        blooming_rose_color=str(defaults.get("blooming_rose_color", "#FF6FAE")),
        blooming_rose_edge_color=str(defaults.get("blooming_rose_edge_color", "#FFD5E8")),
        sakura_petals_enabled=bool(defaults.get("sakura_petals_enabled", True)),
        sakura_petal_count=max(0, int(defaults.get("sakura_petal_count", 80))),
        sakura_petal_color=str(defaults.get("sakura_petal_color", "#FFD1E8")),
        sakura_petal_edge_color=str(defaults.get("sakura_petal_edge_color", "#FF8FC7")),
        sakura_petal_speed=float(defaults.get("sakura_petal_speed", 0.32)),
        sakura_petal_sway=float(defaults.get("sakura_petal_sway", 1.15)),
        sakura_petal_size=float(defaults.get("sakura_petal_size", 9.0)),
        sakura_petal_alpha=max(0, min(255, int(defaults.get("sakura_petal_alpha", 210)))),
        sakura_petal_surface_y=float(defaults.get("sakura_petal_surface_y", 0.84)),
        sakura_petal_ripple_enabled=bool(defaults.get("sakura_petal_ripple_enabled", True)),
        sakura_petal_ripple_chance=float(defaults.get("sakura_petal_ripple_chance", 0.65)),
        sakura_petal_ripple_min_radius=float(defaults.get("sakura_petal_ripple_min_radius", 22.0)),
        sakura_petal_ripple_max_radius=float(defaults.get("sakura_petal_ripple_max_radius", 88.0)),
        sakura_petal_ripple_cooldown=float(defaults.get("sakura_petal_ripple_cooldown", 0.025)),
        sunrise_enabled=bool(defaults.get("sunrise_enabled", False)),
        sunrise_angle=float(defaults.get("sunrise_angle", 0.0)),
        sunrise_strength=float(defaults.get("sunrise_strength", 0.65)),
        sunrise_warmth=float(defaults.get("sunrise_warmth", 0.72)),
        sunrise_horizon_y=float(defaults.get("sunrise_horizon_y", 0.72)),
        sunrise_spread=float(defaults.get("sunrise_spread", 0.62)),
        sunrise_color_top=str(defaults.get("sunrise_color_top", "#1B2C64")),
        sunrise_color_mid=str(defaults.get("sunrise_color_mid", "#FF8A5C")),
        sunrise_color_horizon=str(defaults.get("sunrise_color_horizon", "#FFD08A")),
        sun_enabled=bool(defaults.get("sun_enabled", False)),
        sunlight_enabled=bool(defaults.get("sunlight_enabled", False)),
        lens_flare_enabled=bool(defaults.get("lens_flare_enabled", False)),
        sun_x=float(defaults.get("sun_x", 0.22)),
        sun_y=float(defaults.get("sun_y", 0.22)),
        sun_radius=float(defaults.get("sun_radius", 82.0)),
        sun_alpha=max(0, min(255, int(defaults.get("sun_alpha", 235)))),
        sun_angle=float(defaults.get("sun_angle", 0.0)),
        sun_color=str(defaults.get("sun_color", "#FFD36E")),
        sun_edge_color=str(defaults.get("sun_edge_color", "#FF7A3D")),
        sunlight_angle=float(defaults.get("sunlight_angle", 18.0)),
        sunlight_radius=float(defaults.get("sunlight_radius", 420.0)),
        sunlight_alpha=max(0, min(255, int(defaults.get("sunlight_alpha", 92)))),
        sunlight_beam_width=float(defaults.get("sunlight_beam_width", 0.38)),
        sunlight_color=str(defaults.get("sunlight_color", "#FFD08A")),
        lens_flare_angle=float(defaults.get("lens_flare_angle", 18.0)),
        lens_flare_alpha=max(0, min(255, int(defaults.get("lens_flare_alpha", 128)))),
        lens_flare_size=float(defaults.get("lens_flare_size", 1.0)),
        lens_flare_count=max(0, int(defaults.get("lens_flare_count", 6))),
        lens_flare_color=str(defaults.get("lens_flare_color", "#FFE2A6")),
        moon_body_enabled=bool(defaults.get("moon_body_enabled", False)),
        moonlight_enabled=bool(defaults.get("moonlight_enabled", False)),
        moon_shadow_enabled=bool(defaults.get("moon_shadow_enabled", False)),
        moon_x=float(defaults.get("moon_x", 0.78)),
        moon_y=float(defaults.get("moon_y", 0.18)),
        moon_body_angle=float(defaults.get("moon_body_angle", 0.0)),
        moon_radius=float(defaults.get("moon_radius", 74.0)),
        moon_alpha=max(0, min(255, int(defaults.get("moon_alpha", 230)))),
        moon_color=str(defaults.get("moon_color", "#FFF3C4")),
        moon_edge_color=str(defaults.get("moon_edge_color", "#C9D7FF")),
        moon_crater_count=max(0, int(defaults.get("moon_crater_count", 9))),
        moon_crater_alpha=max(0, min(255, int(defaults.get("moon_crater_alpha", 54)))),
        moonlight_radius=float(defaults.get("moonlight_radius", 260.0)),
        moonlight_alpha=max(0, min(255, int(defaults.get("moonlight_alpha", 82)))),
        moonlight_color=str(defaults.get("moonlight_color", "#CFE8FF")),
        moonlight_angle=float(defaults.get("moonlight_angle", 0.0)),
        moonlight_beam_enabled=bool(defaults.get("moonlight_beam_enabled", True)),
        moonlight_beam_alpha=max(0, min(255, int(defaults.get("moonlight_beam_alpha", 44)))),
        moonlight_beam_width=float(defaults.get("moonlight_beam_width", 0.34)),
        moon_shadow_alpha=max(0, min(255, int(defaults.get("moon_shadow_alpha", 70)))),
        moon_shadow_color=str(defaults.get("moon_shadow_color", "#061028")),
        moon_shadow_offset_x=float(defaults.get("moon_shadow_offset_x", 28.0)),
        moon_shadow_offset_y=float(defaults.get("moon_shadow_offset_y", 38.0)),
        moon_shadow_angle=float(defaults.get("moon_shadow_angle", 0.0)),
        moon_shadow_blur_radius=float(defaults.get("moon_shadow_blur_radius", 150.0)),
        sakura_tree_enabled=bool(defaults.get("sakura_tree_enabled", True)),
        sakura_tree_x=float(defaults.get("sakura_tree_x", 0.15)),
        sakura_tree_ground_y=float(defaults.get("sakura_tree_ground_y", 0.92)),
        sakura_tree_scale=float(defaults.get("sakura_tree_scale", 1.0)),
        sakura_tree_alpha=max(0, min(255, int(defaults.get("sakura_tree_alpha", 225)))),
        sakura_tree_trunk_color=str(defaults.get("sakura_tree_trunk_color", "#5B342E")),
        sakura_tree_branch_color=str(defaults.get("sakura_tree_branch_color", "#7B4A42")),
        sakura_tree_blossom_color=str(defaults.get("sakura_tree_blossom_color", "#FFD1E8")),
        sakura_tree_blossom_edge_color=str(defaults.get("sakura_tree_blossom_edge_color", "#FF9FCC")),
        sakura_tree_petal_emit_enabled=bool(defaults.get("sakura_tree_petal_emit_enabled", True)),
        sakura_tree_petal_emit_rate=float(defaults.get("sakura_tree_petal_emit_rate", 0.55)),
        sakura_tree_petal_emit_burst=max(0, int(defaults.get("sakura_tree_petal_emit_burst", 2))),
        sakura_tree_grand_mode=bool(defaults.get("sakura_tree_grand_mode", True)),
        sakura_tree_height_ratio=float(defaults.get("sakura_tree_height_ratio", 0.88)),
        sakura_tree_width_ratio=float(defaults.get("sakura_tree_width_ratio", 0.68)),
        sakura_tree_trunk_thickness=float(defaults.get("sakura_tree_trunk_thickness", 2.25)),
        sakura_tree_root_spread=float(defaults.get("sakura_tree_root_spread", 1.45)),
        sakura_tree_bark_detail=float(defaults.get("sakura_tree_bark_detail", 0.85)),
        sakura_tree_branch_spread=float(defaults.get("sakura_tree_branch_spread", 1.35)),
        sakura_tree_canopy_density=max(4, int(defaults.get("sakura_tree_canopy_density", 12))),
        sakura_tree_canopy_opacity=float(defaults.get("sakura_tree_canopy_opacity", 0.78)),
        sakura_tree_canopy_layering=float(defaults.get("sakura_tree_canopy_layering", 1.0)),
        sakura_tree_fine_branch_alpha=max(0, min(255, int(defaults.get("sakura_tree_fine_branch_alpha", 150)))),
        sakura_tree_realistic_blossoms=bool(defaults.get("sakura_tree_realistic_blossoms", True)),
        sakura_tree_blossom_rosette_count=max(0, int(defaults.get("sakura_tree_blossom_rosette_count", 90))),
        sakura_tree_blossom_rosette_size=float(defaults.get("sakura_tree_blossom_rosette_size", 13.0)),
        sakura_tree_blossom_rosette_layers=max(1, int(defaults.get("sakura_tree_blossom_rosette_layers", 3))),
        sakura_tree_blossom_rosette_opacity=float(defaults.get("sakura_tree_blossom_rosette_opacity", 0.86)),
        sakura_tree_blossom_center_color=str(defaults.get("sakura_tree_blossom_center_color", "#FFF2A8")),
        sakura_tree_blossom_shadow_color=str(defaults.get("sakura_tree_blossom_shadow_color", "#D96A9A")),
        sakura_tree_blossom_highlight_alpha=max(0, min(255, int(defaults.get("sakura_tree_blossom_highlight_alpha", 105)))),

        snow_enabled=bool(defaults.get("snow_enabled", False)),
        snow_count=max(0, int(defaults.get("snow_count", 90))),
        snow_speed=float(defaults.get("snow_speed", 0.18)),
        snow_size=float(defaults.get("snow_size", 4.5)),
        snow_alpha=max(0, min(255, int(defaults.get("snow_alpha", 210)))),
        snow_color=str(defaults.get("snow_color", "#F5FCFF")),
        snow_edge_color=str(defaults.get("snow_edge_color", "#CFEFFF")),
        snow_ripple_color=str(defaults.get("snow_ripple_color", "#DFFBFF")),
        snow_ripple_enabled=bool(defaults.get("snow_ripple_enabled", True)),
        snow_ripple_chance=float(defaults.get("snow_ripple_chance", 0.38)),
        snow_surface_y=float(defaults.get("snow_surface_y", 0.86)),
        snow_accumulation_enabled=bool(defaults.get("snow_accumulation_enabled", False)),
        snow_accumulation_start_y=max(0.0, min(1.0, float(defaults.get("snow_accumulation_start_y", 1.0)))),
        snow_accumulation_max_depth=max(0.05, min(1.0, float(defaults.get("snow_accumulation_max_depth", 1.0)))),
        snow_accumulation_build_rate=max(0.0, min(120.0, float(defaults.get("snow_accumulation_build_rate", 7.0)))),
        snow_accumulation_column_width=max(2.0, min(30.0, float(defaults.get("snow_accumulation_column_width", 7.0)))),
        snow_accumulation_alpha=max(0, min(255, int(defaults.get("snow_accumulation_alpha", 230)))),
        snow_accumulation_mouse_remove_enabled=bool(defaults.get("snow_accumulation_mouse_remove_enabled", True)),
        snow_accumulation_remove_radius=max(4.0, min(300.0, float(defaults.get("snow_accumulation_remove_radius", 58.0)))),
        snow_accumulation_remove_strength=max(1.0, min(400.0, float(defaults.get("snow_accumulation_remove_strength", 72.0)))),
        snow_crystal_enabled=bool(defaults.get("snow_crystal_enabled", False)),
        snow_crystal_count=max(0, int(defaults.get("snow_crystal_count", 22))),
        snow_crystal_speed=float(defaults.get("snow_crystal_speed", 0.12)),
        snow_crystal_size=float(defaults.get("snow_crystal_size", 15.0)),
        snow_crystal_alpha=max(0, min(255, int(defaults.get("snow_crystal_alpha", 220)))),
        snow_crystal_color=str(defaults.get("snow_crystal_color", "#EBFAFF")),
        snow_crystal_edge_color=str(defaults.get("snow_crystal_edge_color", "#D8F4FF")),
        snow_crystal_ripple_color=str(defaults.get("snow_crystal_ripple_color", "#E8FBFF")),
        water_drop_color=str(defaults.get("water_drop_color", "#7DDCFF")),
        water_drop_edge_color=str(defaults.get("water_drop_edge_color", "#D2F8FF")),
        flame_core_color=str(defaults.get("flame_core_color", "#FFF58C")),
        flame_mid_color=str(defaults.get("flame_mid_color", "#FF7823")),
        flame_edge_color=str(defaults.get("flame_edge_color", "#FF1E00")),
        water_spray_color=str(defaults.get("water_spray_color", "#82E1FF")),
        water_spray_edge_color=str(defaults.get("water_spray_edge_color", "#D7FAFF")),
        fireball_core_color=str(defaults.get("fireball_core_color", "#FFFFBE")),
        fireball_mid_color=str(defaults.get("fireball_mid_color", "#FF7828")),
        fireball_edge_color=str(defaults.get("fireball_edge_color", "#AA1400")),
        fireball_trail_color=str(defaults.get("fireball_trail_color", "#FF5A14")),
        snow_crystal_ripple_enabled=bool(defaults.get("snow_crystal_ripple_enabled", True)),
        snow_crystal_ripple_chance=float(defaults.get("snow_crystal_ripple_chance", 0.55)),
        snow_crystal_surface_y=float(defaults.get("snow_crystal_surface_y", 0.86)),
        bubble_enabled=bool(defaults.get("bubble_enabled", False)),
        bubble_count=max(0, int(defaults.get("bubble_count", 42))),
        bubble_speed=float(defaults.get("bubble_speed", 0.26)),
        bubble_size=float(defaults.get("bubble_size", 12.0)),
        bubble_alpha=max(0, min(255, int(defaults.get("bubble_alpha", 150)))),
        flame_enabled=bool(defaults.get("flame_enabled", False)),
        flame_count=max(0, int(defaults.get("flame_count", 60))),
        flame_speed=float(defaults.get("flame_speed", 0.55)),
        flame_size=float(defaults.get("flame_size", 22.0)),
        flame_alpha=max(0, min(255, int(defaults.get("flame_alpha", 210)))),
        water_spray_enabled=bool(defaults.get("water_spray_enabled", False)),
        water_spray_count=max(0, int(defaults.get("water_spray_count", 64))),
        water_spray_speed=float(defaults.get("water_spray_speed", 0.75)),
        water_spray_size=float(defaults.get("water_spray_size", 6.0)),
        water_spray_alpha=max(0, min(255, int(defaults.get("water_spray_alpha", 190)))),
        fireball_enabled=bool(defaults.get("fireball_enabled", False)),
        fireball_count=max(0, int(defaults.get("fireball_count", 10))),
        fireball_speed=float(defaults.get("fireball_speed", 0.34)),
        fireball_size=float(defaults.get("fireball_size", 20.0)),
        fireball_alpha=max(0, min(255, int(defaults.get("fireball_alpha", 225)))),
        shooting_star_enabled=bool(defaults.get("shooting_star_enabled", False)),
        shooting_star_count=max(0, int(defaults.get("shooting_star_count", 3))),
        shooting_star_speed=float(defaults.get("shooting_star_speed", 0.8)),
        shooting_star_size=float(defaults.get("shooting_star_size", 18.0)),
        shooting_star_alpha=max(0, min(255, int(defaults.get("shooting_star_alpha", 230)))),
        meteor_shower_enabled=bool(defaults.get("meteor_shower_enabled", False)),
        meteor_shower_count=max(0, int(defaults.get("meteor_shower_count", 18))),
        meteor_shower_speed=float(defaults.get("meteor_shower_speed", 0.9)),
        meteor_shower_size=float(defaults.get("meteor_shower_size", 12.0)),
        meteor_shower_alpha=max(0, min(255, int(defaults.get("meteor_shower_alpha", 220)))),
        balloon_enabled=bool(defaults.get("balloon_enabled", False)),
        balloon_count=max(0, int(defaults.get("balloon_count", 12))),
        balloon_speed=float(defaults.get("balloon_speed", 0.20)),
        balloon_size=float(defaults.get("balloon_size", 34.0)),
        balloon_alpha=max(0, min(255, int(defaults.get("balloon_alpha", 220)))),
        star_sky_enabled=bool(defaults.get("star_sky_enabled", False)),
        star_sky_count=max(0, int(defaults.get("star_sky_count", 360))),
        star_sky_speed=float(defaults.get("star_sky_speed", 0.35)),
        star_sky_size=float(defaults.get("star_sky_size", 1.6)),
        star_sky_alpha=max(0, min(255, int(defaults.get("star_sky_alpha", 220)))),
        star_sky_color=str(defaults.get("star_sky_color", "#F8FBFF")),
        star_sky_secondary_color=str(defaults.get("star_sky_secondary_color", "#BFD8FF")),
        milky_way_enabled=bool(defaults.get("milky_way_enabled", False)),
        milky_way_star_count=max(0, int(defaults.get("milky_way_star_count", 220))),
        milky_way_alpha=max(0, min(255, int(defaults.get("milky_way_alpha", 120)))),
        milky_way_width=float(defaults.get("milky_way_width", 0.22)),
        milky_way_angle=float(defaults.get("milky_way_angle", -18.0)),
        milky_way_color=str(defaults.get("milky_way_color", "#BFD7FF")),
        water_surface_enabled=bool(defaults.get("water_surface_enabled", False)),
        puddle_enabled=bool(defaults.get("puddle_enabled", False)),
        puddle_x=max(0.0, min(1.0, float(defaults.get("puddle_x", 0.50)))),
        puddle_y=max(0.0, min(1.0, float(defaults.get("puddle_y", 0.84)))),
        puddle_width=max(0.05, min(1.20, float(defaults.get("puddle_width", 0.72)))),
        puddle_height=max(0.02, min(0.70, float(defaults.get("puddle_height", 0.22)))),
        puddle_edge_softness=max(0.0, min(1.0, float(defaults.get("puddle_edge_softness", 0.18)))),
        puddle_count=max(1, min(12, int(defaults.get("puddle_count", 5)))),
        puddle_spread=max(0.0, min(1.0, float(defaults.get("puddle_spread", 0.72)))),
        puddles_json=str(defaults.get("puddles_json", "") or ""),
        water_surface_alpha=max(0, min(255, int(defaults.get("water_surface_alpha", 92)))),
        water_surface_color=str(defaults.get("water_surface_color", "#4FC3FF")),
        water_surface_highlight_color=str(defaults.get("water_surface_highlight_color", "#D8FAFF")),
        water_surface_flow_angle=float(defaults.get("water_surface_flow_angle", 0.0)),
        water_surface_flow_speed=float(defaults.get("water_surface_flow_speed", 0.55)),
        water_surface_wave_count=max(0, int(defaults.get("water_surface_wave_count", 14))),
        water_surface_wave_height=float(defaults.get("water_surface_wave_height", 12.0)),
        water_surface_y=float(defaults.get("water_surface_y", 0.58)),
        water_surface_depth=float(defaults.get("water_surface_depth", 0.42)),
        water_depth_enabled=bool(defaults.get("water_depth_enabled", True)),
        water_depth_strength=float(defaults.get("water_depth_strength", 0.75)),
        water_depth_haze_alpha=max(0, min(255, int(defaults.get("water_depth_haze_alpha", 48)))),
        water_depth_color=str(defaults.get("water_depth_color", "#1A5B70")),
        water_morning_fog_enabled=bool(defaults.get("water_morning_fog_enabled", True)),
        water_morning_fog_follow_sunrise=bool(defaults.get("water_morning_fog_follow_sunrise", True)),
        water_morning_fog_strength=float(defaults.get("water_morning_fog_strength", 0.65)),
        water_morning_fog_alpha=max(0, min(255, int(defaults.get("water_morning_fog_alpha", 95)))),
        water_morning_fog_height=float(defaults.get("water_morning_fog_height", 0.22)),
        water_morning_fog_drift=float(defaults.get("water_morning_fog_drift", 0.35)),
        water_morning_fog_color=str(defaults.get("water_morning_fog_color", "#E9F6FF")),
        water_fish_enabled=bool(defaults.get("water_fish_enabled", True)),
        water_fish_count=max(0, int(defaults.get("water_fish_count", 4))),
        water_fish_speed=float(defaults.get("water_fish_speed", 0.28)),
        water_fish_size=float(defaults.get("water_fish_size", 24.0)),
        water_fish_alpha=max(0, min(255, int(defaults.get("water_fish_alpha", 175)))),
        water_fish_color=str(defaults.get("water_fish_color", "#7FE7D1")),
        water_fish_secondary_color=str(defaults.get("water_fish_secondary_color", "#D8FFF3")),
        water_mirror_enabled=bool(defaults.get("water_mirror_enabled", False)),
        water_mirror_alpha=max(0, min(255, int(defaults.get("water_mirror_alpha", 110)))),
        water_mirror_blur=float(defaults.get("water_mirror_blur", 5.0)),
        water_mirror_depth=float(defaults.get("water_mirror_depth", 0.65)),
        water_mirror_wave=float(defaults.get("water_mirror_wave", 7.0)),
        water_mirror_tint_alpha=max(0, min(255, int(defaults.get("water_mirror_tint_alpha", 58)))),
        water_mirror_reflect_effects_enabled=bool(defaults.get("water_mirror_reflect_effects_enabled", True)),
        water_mirror_reflect_widgets_enabled=bool(defaults.get("water_mirror_reflect_widgets_enabled", True)),
        water_mirror_reflect_snow=bool(defaults.get("water_mirror_reflect_snow", True)),
        water_mirror_reflect_snow_crystal=bool(defaults.get("water_mirror_reflect_snow_crystal", True)),
        water_mirror_reflect_petals=bool(defaults.get("water_mirror_reflect_petals", True)),
        water_mirror_reflect_bamboo=bool(defaults.get("water_mirror_reflect_bamboo", True)),
        water_mirror_reflect_shooting_star=bool(defaults.get("water_mirror_reflect_shooting_star", True)),
        water_mirror_reflect_meteor_shower=bool(defaults.get("water_mirror_reflect_meteor_shower", True)),
        water_mirror_reflect_rain=bool(defaults.get("water_mirror_reflect_rain", True)),
        ice_enabled=bool(defaults.get("ice_enabled", False)),
        ice_lightweight_enabled=bool(defaults.get("ice_lightweight_enabled", True)),
        ice_static_cache_enabled=bool(defaults.get("ice_static_cache_enabled", True)),
        ice_quality_scale=max(0.25, min(1.0, float(defaults.get("ice_quality_scale", 0.58)))),
        ice_max_facets=max(8, int(defaults.get("ice_max_facets", 72))),
        ice_max_cracks=max(0, int(defaults.get("ice_max_cracks", 16))),
        ice_max_bubbles=max(0, int(defaults.get("ice_max_bubbles", 34))),
        ice_skip_reflected_effect_frames=max(0, min(12, int(defaults.get("ice_skip_reflected_effect_frames", 2)))),
        ice_mirror_skip_frames=max(0, min(12, int(defaults.get("ice_mirror_skip_frames", 2)))),
        ice_alpha=max(0, min(255, int(defaults.get("ice_alpha", 178)))),
        ice_color=str(defaults.get("ice_color", "#9BDDF2")),
        ice_edge_color=str(defaults.get("ice_edge_color", "#E8FBFF")),
        ice_highlight_color=str(defaults.get("ice_highlight_color", "#F7FFFF")),
        ice_shadow_color=str(defaults.get("ice_shadow_color", "#2C6F93")),
        ice_fog_color=str(defaults.get("ice_fog_color", "#EEF9FF")),
        ice_size=float(defaults.get("ice_size", 185.0)),
        ice_angle=float(defaults.get("ice_angle", -6.0)),
        ice_x=float(defaults.get("ice_x", 0.50)),
        ice_width=float(defaults.get("ice_width", 1.00)),
        ice_y=float(defaults.get("ice_y", 0.58)),
        ice_depth=float(defaults.get("ice_depth", 0.42)),
        ice_crack_intensity=float(defaults.get("ice_crack_intensity", 0.46)),
        ice_internal_bubble_intensity=float(defaults.get("ice_internal_bubble_intensity", 0.36)),
        ice_glacier_roughness=float(defaults.get("ice_glacier_roughness", 0.55)),
        ice_mirror_enabled=bool(defaults.get("ice_mirror_enabled", True)),
        ice_mirror_alpha=max(0, min(255, int(defaults.get("ice_mirror_alpha", 118)))),
        ice_mirror_blur=float(defaults.get("ice_mirror_blur", 3.5)),
        ice_mirror_depth=float(defaults.get("ice_mirror_depth", 0.68)),
        ice_mirror_wave=float(defaults.get("ice_mirror_wave", 2.2)),
        ice_mirror_tint_alpha=max(0, min(255, int(defaults.get("ice_mirror_tint_alpha", 70)))),
        ice_reflect_effects_enabled=bool(defaults.get("ice_reflect_effects_enabled", True)),
        ice_reflect_widgets_enabled=bool(defaults.get("ice_reflect_widgets_enabled", True)),
        ice_reflect_snow=bool(defaults.get("ice_reflect_snow", True)),
        ice_reflect_snow_crystal=bool(defaults.get("ice_reflect_snow_crystal", True)),
        ice_reflect_petals=bool(defaults.get("ice_reflect_petals", True)),
        ice_reflect_bamboo=bool(defaults.get("ice_reflect_bamboo", True)),
        ice_reflect_shooting_star=bool(defaults.get("ice_reflect_shooting_star", True)),
        ice_reflect_meteor_shower=bool(defaults.get("ice_reflect_meteor_shower", True)),
        ice_reflect_rain=bool(defaults.get("ice_reflect_rain", True)),
        ice_fog_enabled=bool(defaults.get("ice_fog_enabled", True)),
        ice_fog_alpha=max(0, min(255, int(defaults.get("ice_fog_alpha", 72)))),
        ice_fog_height=float(defaults.get("ice_fog_height", 0.24)),
        ice_fog_drift=float(defaults.get("ice_fog_drift", 0.30)),
        bamboo_grove_enabled=bool(defaults.get("bamboo_grove_enabled", False)),
        bamboo_count=max(0, int(defaults.get("bamboo_count", 12))),
        bamboo_thickness=float(defaults.get("bamboo_thickness", 16.0)),
        bamboo_angle=float(defaults.get("bamboo_angle", 0.0)),
        bamboo_bend=float(defaults.get("bamboo_bend", 0.32)),
        bamboo_height=float(defaults.get("bamboo_height", 0.92)),
        bamboo_alpha=max(0, min(255, int(defaults.get("bamboo_alpha", 230)))),
        bamboo_leaf_density=max(0, int(defaults.get("bamboo_leaf_density", 4))),
        bamboo_depth_strength=float(defaults.get("bamboo_depth_strength", 0.85)),
        bamboo_layer_spread=float(defaults.get("bamboo_layer_spread", 0.42)),
        bamboo_highlight_alpha=max(0, min(255, int(defaults.get("bamboo_highlight_alpha", 96)))),
        bamboo_ground_shadow_enabled=bool(defaults.get("bamboo_ground_shadow_enabled", True)),
        bamboo_atmosphere_enabled=bool(defaults.get("bamboo_atmosphere_enabled", True)),
        bamboo_stalk_color=str(defaults.get("bamboo_stalk_color", "#3EA65A")),
        bamboo_shadow_color=str(defaults.get("bamboo_shadow_color", "#1F6F3B")),
        bamboo_node_color=str(defaults.get("bamboo_node_color", "#B7E37A")),
        bamboo_leaf_color=str(defaults.get("bamboo_leaf_color", "#5ED06C")),
        water_drop_enabled=bool(defaults.get("water_drop_enabled", False)),
        water_drop_count=max(0, int(defaults.get("water_drop_count", 55))),
        water_drop_speed=float(defaults.get("water_drop_speed", 0.48)),
        water_drop_size=float(defaults.get("water_drop_size", 8.0)),
        water_drop_alpha=max(0, min(255, int(defaults.get("water_drop_alpha", 210)))),
        water_drop_ripple_enabled=bool(defaults.get("water_drop_ripple_enabled", True)),
        water_drop_ripple_chance=float(defaults.get("water_drop_ripple_chance", 0.75)),
        water_drop_surface_y=float(defaults.get("water_drop_surface_y", 0.86)),
        rose_petal_fade_on_surface=bool(defaults.get("rose_petal_fade_on_surface", True)),
        rose_petal_fade_duration=float(defaults.get("rose_petal_fade_duration", 0.85)),
        rose_petal_fade_sink_distance=float(defaults.get("rose_petal_fade_sink_distance", 10.0)),
        rose_petal_fade_spin=float(defaults.get("rose_petal_fade_spin", 0.35)),
    )


@dataclass
class ExtraEffectParticle:
    kind: str
    x: float
    y: float
    vx: float
    vy: float
    size: float
    alpha: float
    seed: float
    rotation: float = 0.0
    rotation_speed: float = 0.0
    life: float = 6.0
    created_at: float = 0.0
@dataclass
class RosePetal:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    rotation: float
    rotation_speed: float
    sway_phase: float
    alpha: float
    seed: float
    resting: bool = False
    rest_created_at: float = 0.0
    fading: bool = False
    fade_started_at: float = 0.0
    fade_duration: float = 0.85
    fade_start_y: float = 0.0
    fade_sink_distance: float = 10.0

def set_effect_overlay_settings(cfg, settings: EffectOverlaySettings):
    ensure_effect_overlay_fields(cfg)
    cfg.effects_json = json.dumps(settings.to_dict(), ensure_ascii=False)


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


def get_studio_theme_label(value):
    value = normalize_studio_theme(value)
    return STUDIO_THEME_LABELS.get(value, STUDIO_THEME_LABELS[DEFAULT_STUDIO_THEME])


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
    except Exception:
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
    except Exception:
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
    except Exception:
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
    except Exception:
        pass

def set_canvas_studio_theme(canvas, theme):
    canvas.studio_theme = normalize_studio_theme(theme)


def get_canvas_studio_theme(canvas):
    return normalize_studio_theme(getattr(canvas, "studio_theme", DEFAULT_STUDIO_THEME))


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

def is_windows_only_desktop_overlay_supported():
    return is_windows()

def create_runtime_controllers(canvas):
    canvas.audio = AudioEngine()
    canvas.monitor = SystemMonitor()

    if is_windows():
        try:
            canvas.volume = VolumeController()
        except Exception:
            canvas.volume = DummyVolumeController()

        try:
            canvas.media = MediaController()
        except Exception:
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
    except Exception:
        pass


def show_js_views_if_present(canvas):
    try:
        if hasattr(canvas, "js_html_views"):
            canvas.js_html_views.set_visible(True)
    except Exception:
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
    except Exception:
        pass

    try:
        if hasattr(canvas, "volume") and canvas.volume is not None:
            canvas.volume.stop()
    except Exception:
        pass

    try:
        if hasattr(canvas, "media_meta") and canvas.media_meta is not None:
            canvas.media_meta.stop()
    except Exception:
        pass

    try:
        if hasattr(canvas, "weather") and canvas.weather is not None:
            canvas.weather.stop()
    except Exception:
        pass

    try:
        if hasattr(canvas, "js_html_views") and canvas.js_html_views is not None:
            canvas.js_html_views.clear()
    except Exception:
        pass

def get_network_down_color(cfg):
    return getattr(cfg, "network_down_color", None) or DEFAULT_NETWORK_DOWN_COLOR


def get_network_up_color(cfg):
    return getattr(cfg, "network_up_color", None) or DEFAULT_NETWORK_UP_COLOR


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
            except Exception:
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
            except Exception:
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

    def _run(self):
        try:
            self._run_soundcard_loopback()
        except Exception:
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
            except Exception:
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
        except Exception:
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
    mirror_reflect_enabled: bool = True
    """
    [bg_alpha]
        0   = 完全透明
        155 = 半透明
        255 = 完全不透明
    """
    cpu_color: str = "#5BE7FF"
    memory_color: str = "#B388FF"
    disk_color: str = "#80FF9F"
    clock_show_digital: bool = True
    visualizer_flip_vertical: bool = False
    visualizer_peak_bar_enabled: bool = True
    visualizer_glow_enabled: bool = True
    visualizer_bar_width_scale: float = 1.0
    visualizer_orientation: str = "horizontal"
    visualizer_frame_rate_enabled: bool = True
    visualizer_frame_rate: int = 60
    weather_location: str = ""
    network_down_color: str = "#5BE7FF"
    network_up_color: str = "#80FF9F"

    effects_json: str = "{}"
    effects_follow_mouse: bool = True


def widget_config_from_dict(item):
    if not isinstance(item, dict):
        item = {}
    valid_keys = set(WidgetConfig.__dataclass_fields__.keys())
    filtered = {k: v for k, v in item.items() if k in valid_keys}
    return WidgetConfig(**filtered)

class BaseWidget:
    def __init__(self, cfg: WidgetConfig):
        self.cfg = cfg
        self.selected = False

    @property
    def rect(self) -> QRectF:
        return QRectF(self.cfg.x, self.cfg.y, self.cfg.w, self.cfg.h)

    def interaction_rect(self) -> QRectF:
        """Mouse hit / selection area used by the canvas."""
        return self.rect

    def contains(self, pos: QPoint) -> bool:
        return self.interaction_rect().contains(QPointF(pos))

    def paint(self, p: QPainter, ctx: Dict):
        raise NotImplementedError

    def to_config(self) -> WidgetConfig:
        return self.cfg

    def reflects_in_mirrors(self) -> bool:
        """Return whether this widget should be included in water/ice mirror source images."""
        try:
            return bool(getattr(self.cfg, "mirror_reflect_enabled", True))
        except Exception:
            return True

    def set_reflects_in_mirrors(self, value: bool):
        try:
            self.cfg.mirror_reflect_enabled = bool(value)
        except Exception:
            pass

class EffectsOverlayWidget(BaseWidget):
    def __init__(self, cfg):
        super().__init__(cfg)
        ensure_effect_overlay_fields(self.cfg)
        self._particles: List[EffectParticle] = []
        self._rain: List[EffectParticle] = []
        self._ripples: List[EffectRipple] = []
        self._last_time = time.time()
        self._mouse_pos: Optional[QPointF] = None
        self._mouse_active_until = 0.0
        self._last_rect_size = (0, 0)
        self._random = random.Random(20260505)
        self._last_rain_ripple_time = 0.0
        self._rose_petals: List[RosePetal] = []
        self._last_petal_ripple_time = 0.0
        self._rose_flowers: List[FallingRoseFlower] = []
        self._blooming_roses: List[BloomingRose] = []
        self._last_flower_ripple_time = 0.0
        self._sakura_petals: List[SakuraPetal] = []
        self._last_sakura_ripple_time = 0.0
        self._last_sakura_tree_emit_time = 0.0
        self._extra_effects: Dict[str, List[ExtraEffectParticle]] = {}
        self._last_extra_ripple_time = 0.0
        self._snow_accum_heights = []
        self._snow_accum_rect_key = None
        self._last_snow_accum_update = 0.0
        self._moon_drag_offset = QPointF(0.0, 0.0)
        self._bamboo_grove_cache_key = None
        self._bamboo_grove_cache = []
        self._milky_way_cache_signature = None
        self._milky_way_cache = {"blobs": [], "stars": []}
        self._water_reflection_source_image = None
        self._water_reflection_cache_signature = None
        self._water_reflection_cache_image = None
        self._ice_reflection_cache_signature = None
        self._ice_reflection_cache_image = None
        self._ice_surface_cache_signature = None
        self._ice_surface_cache_image = None
        self._ice_reflected_effects_cache_signature = None
        self._ice_reflected_effects_cache_image = None
        self._water_fish = []
        self._water_fish_rect_key = None
        self._water_morning_fog = []
        self._water_morning_fog_rect_key = None
        self._last_water_morning_fog_update = 0.0
        self._petal_wind_phase = 0.0
        self._petal_wind_strength = 0.0
        self._petal_wind_until = 0.0
        self._next_petal_wind_event = time.time() + 1.5
        self._last_petal_mouse_flutter = 0.0
        self._petal_gust_active = False
        self._petal_gust_started_at = 0.0
        self._petal_gust_direction = 1.0
        self._last_petal_gust_rollup_at = 0.0

    def _has_visible_moon_effect(self, settings: Optional[EffectOverlaySettings] = None) -> bool:
        """Return True when any moon-related visual is enabled."""
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        return bool(
            getattr(settings, "moon_body_enabled", False)
            or getattr(settings, "moonlight_enabled", False)
            or getattr(settings, "moon_shadow_enabled", False)
        )

    def moon_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        """Compact hit/selection area for moon body, moonlight and moon shadow.

        The overlay widget itself can be full-screen. For moon effects, the selectable
        rectangle is the union of the enabled moon visuals only. The long moonlight
        beam is intentionally excluded from hit-testing so the selection area stays
        near the moon instead of stretching to the bottom of the screen.
        """
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        r = self.rect
        if not self._has_visible_moon_effect(settings):
            return QRectF(r)
        center = self._moon_center(r, settings)
        moon_radius = max(2.0, float(getattr(settings, "moon_radius", 74.0)))
        bounds = QRectF()
        has_bounds = False

        def unite(rect: QRectF):
            nonlocal bounds, has_bounds
            bounds = QRectF(rect) if not has_bounds else bounds.united(rect)
            has_bounds = True

        if getattr(settings, "moon_body_enabled", False):
            body_radius = moon_radius + moon_radius * 0.18 + 8.0
            unite(QRectF(center.x() - body_radius, center.y() - body_radius, body_radius * 2.0, body_radius * 2.0))

        if getattr(settings, "moonlight_enabled", False):
            light_radius = max(moon_radius * 1.2, float(getattr(settings, "moonlight_radius", 260.0))) * 1.08
            unite(QRectF(center.x() - light_radius, center.y() - light_radius, light_radius * 2.0, light_radius * 2.0))

        if getattr(settings, "moon_shadow_enabled", False):
            offset_x = float(getattr(settings, "moon_shadow_offset_x", 28.0))
            offset_y = float(getattr(settings, "moon_shadow_offset_y", 38.0))
            shadow_angle = self._angle_degrees(settings, "moon_shadow_angle", 0.0)
            rotated_shadow_offset = self._rotated_offset(offset_x, offset_y, shadow_angle)
            blur_radius = max(moon_radius, float(getattr(settings, "moon_shadow_blur_radius", 150.0)))
            shadow_center = QPointF(center.x() + rotated_shadow_offset.x(), center.y() + rotated_shadow_offset.y())
            unite(QRectF(shadow_center.x() - blur_radius * 1.05, shadow_center.y() - blur_radius * 0.95, blur_radius * 2.10, blur_radius * 1.90))

        if not has_bounds:
            return QRectF(r)
        return bounds.adjusted(-8.0, -8.0, 8.0, 8.0)

    def interaction_rect(self) -> QRectF:
        settings = get_effect_overlay_settings(self.cfg)
        rects = []
        if self._has_visible_sun_effect(settings):
            rects.append(self.sun_interaction_rect(settings))
        if self._has_visible_moon_effect(settings):
            rects.append(self.moon_interaction_rect(settings))
        if self._has_visible_ice_effect(settings):
            rects.append(self.ice_interaction_rect(settings))
        if self._has_visible_puddle_effect(settings):
            rects.append(self.puddle_interaction_rect(settings))
        bounds = self._united_interaction_rects(rects)
        return bounds if not bounds.isNull() else self.rect

    def contains(self, pos: QPoint) -> bool:
        settings = get_effect_overlay_settings(self.cfg)
        if self._has_visible_sun_effect(settings) or self._has_visible_moon_effect(settings) or self._has_visible_ice_effect(settings) or self._has_visible_puddle_effect(settings):
            return self.interaction_rect().contains(QPointF(pos))
        return self.rect.contains(pos)

    def is_moon_hit(self, pos: QPoint) -> bool:
        settings = get_effect_overlay_settings(self.cfg)
        return self._has_visible_moon_effect(settings) and self.moon_interaction_rect(settings).contains(QPointF(pos))

    def moon_drag_offset_from_pos(self, pos: QPoint) -> QPointF:
        settings = get_effect_overlay_settings(self.cfg)
        center = self._moon_center(self.rect, settings)
        return QPointF(float(pos.x()) - center.x(), float(pos.y()) - center.y())

    def move_moon_center_to(self, pos: QPoint, offset: Optional[QPointF] = None):
        """Move moon body/light/shadow together by updating moon_x and moon_y."""
        settings = get_effect_overlay_settings(self.cfg)
        r = self.rect
        if r.width() <= 0 or r.height() <= 0:
            return
        if offset is None:
            offset = QPointF(0.0, 0.0)
        new_center_x = float(pos.x()) - float(offset.x())
        new_center_y = float(pos.y()) - float(offset.y())
        settings.moon_x = max(0.0, min(1.0, (new_center_x - r.left()) / max(1.0, r.width())))
        settings.moon_y = max(0.0, min(1.0, (new_center_y - r.top()) / max(1.0, r.height())))
        set_effect_overlay_settings(self.cfg, settings)

    def _has_visible_ice_effect(self, settings: Optional[EffectOverlaySettings] = None) -> bool:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        return bool(getattr(settings, "ice_enabled", False))

    def ice_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not self._has_visible_ice_effect(settings):
            return QRectF()
        rect_func = getattr(type(self), "_ice_surface_rect", None)
        if rect_func is None:
            return QRectF(self.rect)
        ice_rect = rect_func(self, self.rect, settings)
        if ice_rect.isNull() or not ice_rect.isValid():
            return QRectF()
        return ice_rect.adjusted(-10.0, -10.0, 10.0, 10.0)

    def is_ice_hit(self, pos: QPoint) -> bool:
        settings = get_effect_overlay_settings(self.cfg)
        return self._has_visible_ice_effect(settings) and self.ice_interaction_rect(settings).contains(QPointF(pos))

    def ice_drag_offset_from_pos(self, pos: QPoint) -> QPointF:
        settings = get_effect_overlay_settings(self.cfg)
        ice_rect = self.ice_interaction_rect(settings)
        center = ice_rect.center() if ice_rect.isValid() and not ice_rect.isNull() else self.rect.center()
        return QPointF(float(pos.x()) - center.x(), float(pos.y()) - center.y())

    def move_ice_center_to(self, pos: QPoint, offset: Optional[QPointF] = None):
        """Move only the ice/glacier surface without moving the entire overlay widget."""
        settings = get_effect_overlay_settings(self.cfg)
        r = self.rect
        if r.width() <= 0 or r.height() <= 0:
            return
        if offset is None:
            offset = QPointF(0.0, 0.0)
        new_center_x = float(pos.x()) - float(offset.x())
        new_center_y = float(pos.y()) - float(offset.y())
        width_ratio = max(0.05, min(1.50, float(getattr(settings, "ice_width", 1.0))))
        depth_ratio = max(0.05, min(1.0, float(getattr(settings, "ice_depth", 0.42))))
        ice_w = r.width() * width_ratio
        ice_h = r.height() * depth_ratio
        new_left = new_center_x - ice_w * 0.5
        new_top = new_center_y - ice_h * 0.5
        settings.ice_x = max(0.0, min(1.0, (new_center_x - r.left()) / max(1.0, r.width())))
        settings.ice_y = max(0.0, min(1.0, (new_top - r.top()) / max(1.0, r.height())))
        set_effect_overlay_settings(self.cfg, settings)

    def _has_visible_sun_effect(self, settings: Optional[EffectOverlaySettings] = None) -> bool:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        return bool(getattr(settings, "sunrise_enabled", False) or getattr(settings, "sun_enabled", False) or getattr(settings, "sunlight_enabled", False) or getattr(settings, "lens_flare_enabled", False))

    def _united_interaction_rects(self, rects):
        bounds = QRectF()
        has_bounds = False
        for rect in rects:
            try:
                if rect is None or rect.isNull() or not rect.isValid():
                    continue
            except Exception:
                continue
            bounds = QRectF(rect) if not has_bounds else bounds.united(rect)
            has_bounds = True
        return bounds if has_bounds else QRectF()

    def _circle_interaction_rect(self, center: QPointF, radius: float) -> QRectF:
        radius = max(1.0, float(radius))
        return QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)

    def sun_body_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not getattr(settings, "sun_enabled", False):
            return QRectF()
        center = self._sun_center(self.rect, settings)
        radius = max(2.0, float(getattr(settings, "sun_radius", 82.0)))
        return self._circle_interaction_rect(center, radius * 1.34).adjusted(-4.0, -4.0, 4.0, 4.0)

    def sunlight_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not getattr(settings, "sunlight_enabled", False):
            return QRectF()
        center = self._sun_center(self.rect, settings)
        sun_radius = max(2.0, float(getattr(settings, "sun_radius", 82.0)))
        light_radius = max(sun_radius * 1.5, float(getattr(settings, "sunlight_radius", 420.0)))
        return self._circle_interaction_rect(center, light_radius).adjusted(-4.0, -4.0, 4.0, 4.0)

    def sunrise_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not getattr(settings, "sunrise_enabled", False):
            return QRectF()
        r = self.rect
        center = self._sun_center(r, settings)
        radius = max(2.0, float(getattr(settings, "sun_radius", 82.0)))
        spread = max(0.05, min(1.0, float(getattr(settings, "sunrise_spread", 0.62))))
        glow_radius = max(radius * 2.2, r.height() * (0.18 + spread * 0.55))
        return QRectF(center.x() - glow_radius, center.y() - glow_radius * 0.72, glow_radius * 2.0, glow_radius * 1.44).adjusted(-4.0, -4.0, 4.0, 4.0)

    def lens_flare_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not getattr(settings, "lens_flare_enabled", False):
            return QRectF()
        r = self.rect
        center = self._sun_center(r, settings)
        radius = max(2.0, float(getattr(settings, "sun_radius", 82.0)))
        count = max(0, int(getattr(settings, "lens_flare_count", 6)))
        if count <= 0:
            return QRectF()
        size_scale = max(0.1, min(4.0, float(getattr(settings, "lens_flare_size", 1.0))))
        rad = math.radians(self._angle_degrees(settings, "lens_flare_angle", 18.0))
        dx, dy = math.cos(rad), math.sin(rad)
        screen_center = r.center()
        base_len = math.hypot(screen_center.x() - center.x(), screen_center.y() - center.y())
        if base_len < 1.0:
            base_len = math.hypot(r.width(), r.height()) * 0.35
        rects = []
        for i in range(count):
            t = (i + 1) / (count + 1)
            sign = -1.0 if i % 2 else 1.0
            dist = base_len * (0.28 + t * 1.35) * sign
            x = center.x() + dx * dist
            y = center.y() + dy * dist
            flare_radius = radius * size_scale * (0.06 + 0.12 * (1.0 - abs(0.5 - t)))
            rx = max(3.0, flare_radius * 2.2)
            ry = max(3.0, flare_radius * (1.1 + 0.35 * (i % 3)))
            rects.append(QRectF(x - rx, y - ry, rx * 2.0, ry * 2.0))
        bounds = self._united_interaction_rects(rects)
        return bounds.adjusted(-5.0, -5.0, 5.0, 5.0) if not bounds.isNull() else QRectF()

    def sun_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not self._has_visible_sun_effect(settings):
            return QRectF()
        return self._united_interaction_rects([self.sunrise_interaction_rect(settings), self.sunlight_interaction_rect(settings), self.sun_body_interaction_rect(settings), self.lens_flare_interaction_rect(settings)])

    def sun_effect_hit_kind(self, pos: QPoint, settings: Optional[EffectOverlaySettings] = None):
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not self._has_visible_sun_effect(settings):
            return None
        p = QPointF(pos)
        for kind, rect in [("sun", self.sun_body_interaction_rect(settings)), ("lens_flare", self.lens_flare_interaction_rect(settings)), ("sunlight", self.sunlight_interaction_rect(settings)), ("sunrise", self.sunrise_interaction_rect(settings))]:
            if rect is not None and (not rect.isNull()) and rect.contains(p):
                return kind
        return None

    def is_sun_effect_hit(self, pos: QPoint) -> bool:
        return self.sun_effect_hit_kind(pos) is not None

    def sun_drag_offset_from_pos(self, pos: QPoint) -> QPointF:
        settings = get_effect_overlay_settings(self.cfg)
        center = self._sun_center(self.rect, settings)
        return QPointF(float(pos.x()) - center.x(), float(pos.y()) - center.y())

    def move_sun_center_to(self, pos: QPoint, offset: Optional[QPointF] = None, kind: str = "sun"):
        settings = get_effect_overlay_settings(self.cfg)
        r = self.rect
        if r.width() <= 0 or r.height() <= 0:
            return
        if offset is None:
            offset = QPointF(0.0, 0.0)
        new_center_x = float(pos.x()) - float(offset.x())
        new_center_y = float(pos.y()) - float(offset.y())
        settings.sun_x = max(0.0, min(1.0, (new_center_x - r.left()) / max(1.0, r.width())))
        settings.sun_y = max(0.0, min(1.0, (new_center_y - r.top()) / max(1.0, r.height())))
        if kind == "sunrise":
            settings.sunrise_horizon_y = settings.sun_y
        set_effect_overlay_settings(self.cfg, settings)

    def paint(self, p: QPainter, ctx: Dict):
        settings = get_effect_overlay_settings(self.cfg)
        if "_water_reflection_cache_key" in getattr(self, "__dict__", {}):
            try:
                delattr(self, "_water_reflection_cache_key")
            except Exception:
                pass
        self._water_reflection_source_image = ctx.get("reflection_source_image") if isinstance(ctx, dict) else None
        r = self.rect
        now = time.time()
        dt = max(0.001, min(0.05, now - self._last_time))
        self._last_time = now

        self._ensure_emitters(r, settings)
        self._update_particles(r, settings, dt, now)
        self._update_rain(r, settings, dt)
        self._cleanup_ripples(now)

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if bool(getattr(settings, "gpu_acceleration_enabled", True)) and bool(getattr(settings, "gpu_acceleration_smooth_pixmaps", True)):
            try:
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            except Exception:
                pass

        if settings.background_alpha > 0:
            bg = QColor(getattr(self.cfg, "bg", "#000000") or "#000000")
            bg.setAlpha(settings.background_alpha)
            p.setBrush(QBrush(bg))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(r)

        if settings.noise_enabled:
            self._draw_noise(p, r, settings, now)

        if (
            getattr(settings, "sunrise_enabled", False)
            or getattr(settings, "sun_enabled", False)
            or getattr(settings, "sunlight_enabled", False)
            or getattr(settings, "lens_flare_enabled", False)
        ):
            self._draw_sunrise_sun_integrated_effect(p, r, settings, now)
        if getattr(settings, "moonlight_enabled", False) or getattr(settings, "moon_shadow_enabled", False) or getattr(settings, "moon_body_enabled", False):
            self._draw_moon_integrated_effect(p, r, settings, now)

        self._ensure_extra_effects(r, settings, now)
        self._update_extra_effects(r, settings, dt, now)
        self._draw_extra_effects(p, r, settings, now)

        has_existing_rose_petals = len(getattr(self, "_rose_petals", [])) > 0
        rose_petals_enabled = bool(getattr(settings, "rose_petals_enabled", False))

        if rose_petals_enabled:
            self._ensure_rose_petals(r, settings)

        if rose_petals_enabled or has_existing_rose_petals:
            self._update_rose_petals(r, settings, dt, now)
            self._draw_rose_petals(p, r, settings, now)

        if settings.glow_enabled:
            self._draw_glow_orbs(p, r, settings, now)

        if getattr(settings, "sakura_petals_enabled", False) or len(getattr(self, "_sakura_petals", [])) > 0:
            if getattr(settings, "sakura_petals_enabled", False):
                self._ensure_sakura_petals(r, settings)
            self._update_sakura_petals(r, settings, dt, now)
            self._draw_sakura_petals(p, r, settings, now)

        if settings.mouse_glow_enabled and self._mouse_pos is not None and now <= self._mouse_active_until:
            self._draw_mouse_glow(p, r, settings, now)

        if settings.particles_enabled:
            self._draw_particles(p, r, settings, now)

        if settings.rain_enabled:
            self._draw_rain(p, r, settings)

        if settings.ripple_enabled or settings.mouse_ripple_enabled or len(getattr(self, "_ripples", [])) > 0:
            self._draw_ripples(p, r, settings, now)

        if getattr(settings, "rose_flowers_enabled", False):
            self._ensure_rose_flowers(r, settings)
            self._update_rose_flowers(r, settings, dt, now)
            self._draw_rose_flowers(p, r, settings, now)

        if getattr(settings, "blooming_roses_enabled", False):
            self._ensure_blooming_roses(r, settings, now)
            self._update_blooming_roses(r, settings, dt, now)
            self._draw_blooming_roses(p, r, settings, now)

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()


    def _moon_center(self, r: QRectF, settings: EffectOverlaySettings):
        x = r.left() + r.width() * max(0.0, min(1.0, float(getattr(settings, "moon_x", 0.78))))
        y = r.top() + r.height() * max(0.0, min(1.0, float(getattr(settings, "moon_y", 0.18))))
        return QPointF(x, y)

    def _angle_degrees(self, settings: EffectOverlaySettings, name: str, default: float = 0.0) -> float:
        """Safely read an angle setting in degrees."""
        try:
            return float(getattr(settings, name, default))
        except Exception:
            return float(default)

    def _rotated_offset(self, x: float, y: float, angle_degrees: float) -> QPointF:
        """Rotate an offset vector by angle_degrees around the origin."""
        rad = math.radians(float(angle_degrees))
        ca = math.cos(rad)
        sa = math.sin(rad)
        return QPointF(x * ca - y * sa, x * sa + y * ca)

    def _sun_center(self, r: QRectF, settings: EffectOverlaySettings):
        x = r.left() + r.width() * max(0.0, min(1.0, float(getattr(settings, "sun_x", 0.22))))
        y = r.top() + r.height() * max(0.0, min(1.0, float(getattr(settings, "sun_y", 0.22))))
        return QPointF(x, y)

    def _line_through_rect(self, r: QRectF, center: QPointF, angle_degrees: float):
        rad = math.radians(float(angle_degrees))
        dx = math.cos(rad)
        dy = math.sin(rad)
        span = math.hypot(max(1.0, r.width()), max(1.0, r.height())) * 0.72
        return QPointF(center.x() - dx * span, center.y() - dy * span), QPointF(center.x() + dx * span, center.y() + dy * span)

    def _draw_sunrise_sun_integrated_effect(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        center = self._sun_center(r, settings)
        radius = max(2.0, float(getattr(settings, "sun_radius", 82.0)))
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if getattr(settings, "sunrise_enabled", False):
            self._draw_sunrise_background(p, r, center, radius, settings, now)
        if getattr(settings, "sunlight_enabled", False):
            self._draw_sunlight(p, r, center, radius, settings, now)
        if getattr(settings, "sun_enabled", False):
            self._draw_sun_body(p, center, radius, settings, now)
        if getattr(settings, "lens_flare_enabled", False):
            self._draw_lens_flare(p, r, center, radius, settings, now)
        p.restore()

    def _draw_sunrise_background(self, p: QPainter, r: QRectF, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        strength = max(0.0, min(1.0, float(getattr(settings, "sunrise_strength", 0.65)))) * max(0.0, float(getattr(settings, "intensity", 1.0)))
        if strength <= 0.0:
            return
        warmth = max(0.0, min(1.0, float(getattr(settings, "sunrise_warmth", 0.72))))
        horizon_y = r.top() + r.height() * max(0.0, min(1.0, float(getattr(settings, "sunrise_horizon_y", 0.72))))
        spread = max(0.05, min(1.0, float(getattr(settings, "sunrise_spread", 0.62))))
        angle = self._angle_degrees(settings, "sunrise_angle", 0.0)
        start, end = self._line_through_rect(r, QPointF(r.center().x(), horizon_y), angle + 90.0)
        top = QColor(getattr(settings, "sunrise_color_top", "#1B2C64"))
        mid = QColor(getattr(settings, "sunrise_color_mid", "#FF8A5C"))
        horizon = QColor(getattr(settings, "sunrise_color_horizon", "#FFD08A"))
        top.setAlpha(max(0, min(255, int(42 * strength * (0.55 + 0.45 * (1.0 - warmth))))))
        mid.setAlpha(max(0, min(255, int(118 * strength * (0.55 + warmth * 0.45)))))
        horizon.setAlpha(max(0, min(255, int(150 * strength))))
        clear = QColor(horizon); clear.setAlpha(0)
        grad = QLinearGradient(start, end)
        grad.setColorAt(0.0, top)
        grad.setColorAt(max(0.05, 0.45 - spread * 0.22), mid)
        grad.setColorAt(max(0.10, 0.62 - spread * 0.20), horizon)
        grad.setColorAt(1.0, clear)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(r)
        glow_radius = max(radius * 2.2, r.height() * (0.18 + spread * 0.55))
        glow = QRadialGradient(center, glow_radius)
        g0 = QColor(horizon); g0.setAlpha(max(0, min(255, int(105 * strength))))
        g1 = QColor(mid); g1.setAlpha(max(0, min(255, int(48 * strength))))
        g2 = QColor(mid); g2.setAlpha(0)
        glow.setColorAt(0.0, g0)
        glow.setColorAt(0.38, g1)
        glow.setColorAt(1.0, g2)
        p.setBrush(QBrush(glow))
        p.drawEllipse(center, glow_radius, glow_radius * 0.72)

    def _draw_sunlight(self, p: QPainter, r: QRectF, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        color = QColor(getattr(settings, "sunlight_color", "#FFD08A"))
        alpha = max(0, min(255, int(getattr(settings, "sunlight_alpha", 92) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        light_radius = max(radius * 1.5, float(getattr(settings, "sunlight_radius", 420.0)))
        pulse = 0.94 + 0.06 * math.sin(now * 0.7)
        light_radius *= pulse
        angle = self._angle_degrees(settings, "sunlight_angle", 18.0)
        beam_width = max(0.05, min(1.0, float(getattr(settings, "sunlight_beam_width", 0.38))))
        grad = QRadialGradient(center, light_radius)
        c0 = QColor(color); c0.setAlpha(alpha)
        c1 = QColor(color); c1.setAlpha(int(alpha * 0.28))
        c2 = QColor(color); c2.setAlpha(0)
        grad.setColorAt(0.0, c0); grad.setColorAt(0.42, c1); grad.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawEllipse(center, light_radius, light_radius)
        corners = [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]
        reach = max(math.hypot(c.x() - center.x(), c.y() - center.y()) for c in corners) + radius
        top_w = radius * (0.42 + beam_width)
        bottom_w = max(top_w * 1.8, max(r.width(), r.height()) * beam_width)
        p.save()
        p.translate(center)
        p.rotate(angle)
        beam = QPainterPath()
        beam.moveTo(-top_w, radius * 0.15)
        beam.cubicTo(-bottom_w * 0.25, reach * 0.35, -bottom_w * 0.55, reach * 0.74, -bottom_w, reach)
        beam.lineTo(bottom_w, reach)
        beam.cubicTo(bottom_w * 0.55, reach * 0.74, bottom_w * 0.25, reach * 0.35, top_w, radius * 0.15)
        beam.closeSubpath()
        beam_grad = QLinearGradient(0, 0, 0, reach)
        b0 = QColor(color); b0.setAlpha(max(0, min(255, int(alpha * 0.75))))
        b1 = QColor(color); b1.setAlpha(max(0, min(255, int(alpha * 0.20))))
        b2 = QColor(color); b2.setAlpha(0)
        beam_grad.setColorAt(0.0, b0); beam_grad.setColorAt(0.55, b1); beam_grad.setColorAt(1.0, b2)
        p.setBrush(QBrush(beam_grad))
        p.drawPath(beam)
        p.restore()

    def _draw_sun_body(self, p: QPainter, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        sun_color = QColor(getattr(settings, "sun_color", "#FFD36E"))
        edge_color = QColor(getattr(settings, "sun_edge_color", "#FF7A3D"))
        alpha = max(0, min(255, int(getattr(settings, "sun_alpha", 235) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        angle = self._angle_degrees(settings, "sun_angle", 0.0)
        p.save()
        p.translate(center)
        p.rotate(angle)
        outer = QRadialGradient(QPointF(0.0, 0.0), radius * 1.85)
        o0 = QColor(sun_color); o0.setAlpha(int(alpha * 0.55))
        o1 = QColor(edge_color); o1.setAlpha(int(alpha * 0.18))
        o2 = QColor(edge_color); o2.setAlpha(0)
        outer.setColorAt(0.0, o0); outer.setColorAt(0.45, o1); outer.setColorAt(1.0, o2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(outer))
        p.drawEllipse(QPointF(0.0, 0.0), radius * 1.85, radius * 1.85)
        grad = QRadialGradient(QPointF(-radius * 0.28, -radius * 0.30), radius * 1.2)
        c0 = QColor(255, 250, 205, alpha)
        c1 = QColor(sun_color); c1.setAlpha(alpha)
        c2 = QColor(edge_color); c2.setAlpha(max(0, min(255, int(alpha * 0.95))))
        grad.setColorAt(0.0, c0); grad.setColorAt(0.55, c1); grad.setColorAt(1.0, c2)
        p.setPen(QPen(QColor(edge_color.red(), edge_color.green(), edge_color.blue(), int(alpha * 0.72)), max(1, int(radius * 0.025))))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(0.0, 0.0), radius, radius)
        ray_pen = QPen(QColor(edge_color.red(), edge_color.green(), edge_color.blue(), max(0, min(255, int(alpha * 0.36)))), max(1, int(radius * 0.035)))
        ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(ray_pen)
        for i in range(16):
            a = math.tau * i / 16.0
            wobble = 0.88 + 0.12 * math.sin(now * 1.1 + i)
            inner = radius * 1.06
            outer_len = radius * (1.30 + 0.20 * (i % 2)) * wobble
            p.drawLine(QPointF(math.cos(a) * inner, math.sin(a) * inner), QPointF(math.cos(a) * outer_len, math.sin(a) * outer_len))
        p.restore()

    def _draw_lens_flare(self, p: QPainter, r: QRectF, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        count = max(0, int(getattr(settings, "lens_flare_count", 6)))
        if count <= 0:
            return
        alpha_base = max(0, min(255, int(getattr(settings, "lens_flare_alpha", 128) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha_base <= 0:
            return
        size_scale = max(0.1, min(4.0, float(getattr(settings, "lens_flare_size", 1.0))))
        color = QColor(getattr(settings, "lens_flare_color", "#FFE2A6"))
        angle = self._angle_degrees(settings, "lens_flare_angle", 18.0)
        rad = math.radians(angle)
        dx = math.cos(rad)
        dy = math.sin(rad)
        screen_center = r.center()
        base_len = math.hypot(screen_center.x() - center.x(), screen_center.y() - center.y())
        if base_len < 1.0:
            base_len = math.hypot(r.width(), r.height()) * 0.35
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for i in range(count):
            t = (i + 1) / (count + 1)
            sign = -1.0 if i % 2 else 1.0
            dist = base_len * (0.28 + t * 1.35) * sign
            x = center.x() + dx * dist
            y = center.y() + dy * dist
            flare_radius = radius * size_scale * (0.06 + 0.12 * (1.0 - abs(0.5 - t)))
            flare_alpha = max(0, min(255, int(alpha_base * (0.68 - t * 0.36))))
            if flare_alpha <= 0:
                continue
            grad = QRadialGradient(QPointF(x, y), max(1.0, flare_radius * 2.2))
            c0 = QColor(255, 255, 255, flare_alpha)
            c1 = QColor(color); c1.setAlpha(int(flare_alpha * 0.55))
            c2 = QColor(color); c2.setAlpha(0)
            grad.setColorAt(0.0, c0); grad.setColorAt(0.46, c1); grad.setColorAt(1.0, c2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(x, y), flare_radius * 2.2, flare_radius * (1.1 + 0.35 * (i % 3)))
        line_color = QColor(color); line_color.setAlpha(max(0, min(255, int(alpha_base * 0.22))))
        pen = QPen(line_color, max(1.0, radius * 0.018 * size_scale))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(center.x() - dx * radius * 0.5, center.y() - dy * radius * 0.5), QPointF(center.x() + dx * base_len * 1.25, center.y() + dy * base_len * 1.25))
        p.restore()

    def _draw_moon_integrated_effect(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        center = self._moon_center(r, settings)
        radius = max(2.0, float(getattr(settings, "moon_radius", 74.0)))
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if getattr(settings, "moon_shadow_enabled", False):
            self._draw_moon_shadow(p, center, radius, settings, now)
        if getattr(settings, "moonlight_enabled", False):
            self._draw_moonlight(p, r, center, radius, settings, now)
        if getattr(settings, "moon_body_enabled", False):
            self._draw_moon_body(p, center, radius, settings, now)
        p.restore()

    def _draw_moonlight(self, p: QPainter, r: QRectF, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        color = QColor(getattr(settings, "moonlight_color", "#CFE8FF"))
        alpha = max(0, min(255, int(getattr(settings, "moonlight_alpha", 82) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        light_radius = max(radius * 1.2, float(getattr(settings, "moonlight_radius", 260.0)))
        light_radius *= 0.92 + 0.08 * math.sin(now * 0.85)
        angle = self._angle_degrees(settings, "moonlight_angle", 0.0)

        grad = QRadialGradient(center, light_radius)
        c0 = QColor(color); c0.setAlpha(alpha)
        c1 = QColor(color); c1.setAlpha(int(alpha * 0.30))
        c2 = QColor(color); c2.setAlpha(0)
        grad.setColorAt(0.0, c0); grad.setColorAt(0.38, c1); grad.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawEllipse(center, light_radius, light_radius)

        if bool(getattr(settings, "moonlight_beam_enabled", True)):
            beam_alpha = max(0, min(255, int(getattr(settings, "moonlight_beam_alpha", 44) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
            beam_width = max(0.05, min(1.0, float(getattr(settings, "moonlight_beam_width", 0.34))))
            top_w = radius * (0.35 + beam_width)
            bottom_w = max(top_w * 1.4, max(r.width(), r.height()) * beam_width)
            corners = [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]
            reach = max(math.hypot(c.x() - center.x(), c.y() - center.y()) for c in corners) + radius * 0.8
            start_y = radius * 0.22
            end_y = reach

            p.save()
            p.translate(center)
            p.rotate(angle)
            beam = QPainterPath()
            beam.moveTo(-top_w, start_y)
            beam.cubicTo(-bottom_w * 0.22, light_radius * 0.34, -bottom_w * 0.48, end_y - radius * 0.4, -bottom_w, end_y)
            beam.lineTo(bottom_w, end_y)
            beam.cubicTo(bottom_w * 0.48, end_y - radius * 0.4, bottom_w * 0.22, light_radius * 0.34, top_w, start_y)
            beam.closeSubpath()
            beam_grad = QLinearGradient(0, 0, 0, end_y)
            b0 = QColor(color); b0.setAlpha(beam_alpha)
            b1 = QColor(color); b1.setAlpha(int(beam_alpha * 0.20))
            b2 = QColor(color); b2.setAlpha(0)
            beam_grad.setColorAt(0.0, b0); beam_grad.setColorAt(0.58, b1); beam_grad.setColorAt(1.0, b2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(beam_grad))
            p.drawPath(beam)
            p.restore()
    def _draw_moon_shadow(self, p: QPainter, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        color = QColor(getattr(settings, "moon_shadow_color", "#061028"))
        alpha = max(0, min(255, int(getattr(settings, "moon_shadow_alpha", 70) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        offset_x = float(getattr(settings, "moon_shadow_offset_x", 28.0))
        offset_y = float(getattr(settings, "moon_shadow_offset_y", 38.0))
        angle = self._angle_degrees(settings, "moon_shadow_angle", 0.0)
        rotated_offset = self._rotated_offset(offset_x, offset_y, angle)
        blur_radius = max(radius, float(getattr(settings, "moon_shadow_blur_radius", 150.0)))
        shadow_center = QPointF(center.x() + rotated_offset.x(), center.y() + rotated_offset.y())
        grad = QRadialGradient(QPointF(0.0, 0.0), blur_radius)
        c0 = QColor(color); c0.setAlpha(alpha)
        c1 = QColor(color); c1.setAlpha(int(alpha * 0.28))
        c2 = QColor(color); c2.setAlpha(0)
        grad.setColorAt(0.0, c0); grad.setColorAt(0.48, c1); grad.setColorAt(1.0, c2)
        p.save()
        p.translate(shadow_center)
        p.rotate(angle)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(0.0, 0.0), blur_radius, blur_radius * 0.86)
        p.restore()
    def _draw_moon_body(self, p: QPainter, center: QPointF, radius: float, settings: EffectOverlaySettings, now: float):
        moon_color = QColor(getattr(settings, "moon_color", "#FFF3C4"))
        edge_color = QColor(getattr(settings, "moon_edge_color", "#C9D7FF"))
        alpha = max(0, min(255, int(getattr(settings, "moon_alpha", 230) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        angle = self._angle_degrees(settings, "moon_body_angle", 0.0)

        p.save()
        p.translate(center)
        p.rotate(angle)

        grad = QRadialGradient(QPointF(-radius * 0.26, -radius * 0.30), radius * 1.25)
        c0 = QColor(255, 255, 245, alpha)
        c1 = QColor(moon_color); c1.setAlpha(alpha)
        c2 = QColor(edge_color); c2.setAlpha(max(0, min(255, int(alpha * 0.92))))
        grad.setColorAt(0.0, c0); grad.setColorAt(0.52, c1); grad.setColorAt(1.0, c2)
        p.setPen(QPen(QColor(edge_color.red(), edge_color.green(), edge_color.blue(), int(alpha * 0.72)), max(1, int(radius * 0.025))))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(0.0, 0.0), radius, radius)

        crater_count = max(0, int(getattr(settings, "moon_crater_count", 9)))
        crater_alpha = max(0, min(255, int(getattr(settings, "moon_crater_alpha", 54) * alpha / 255)))
        rng = random.Random(7331 + int(radius * 10))
        for _ in range(crater_count):
            ang = rng.random() * math.tau
            dist = radius * (0.12 + rng.random() * 0.62)
            cx = math.cos(ang) * dist * 0.88
            cy = math.sin(ang) * dist * 0.78
            cr = radius * (0.035 + rng.random() * 0.075)
            shade = QColor(86, 92, 112, crater_alpha)
            light = QColor(255, 255, 245, int(crater_alpha * 0.36))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(shade))
            p.drawEllipse(QPointF(cx, cy), cr * 1.08, cr * 0.82)
            p.setBrush(QBrush(light))
            p.drawEllipse(QPointF(cx - cr * 0.25, cy - cr * 0.22), max(1.0, cr * 0.42), max(1.0, cr * 0.28))
        p.restore()
    def _extra_kind_specs(self):
        return {
            "snow": ("snow_enabled", "snow_count"),
            "snow_crystal": ("snow_crystal_enabled", "snow_crystal_count"),
            "bubble": ("bubble_enabled", "bubble_count"),
            "flame": ("flame_enabled", "flame_count"),
            "water_spray": ("water_spray_enabled", "water_spray_count"),
            "fireball": ("fireball_enabled", "fireball_count"),
            "star_sky": ("star_sky_enabled", "star_sky_count"),
            "shooting_star": ("shooting_star_enabled", "shooting_star_count"),
            "meteor_shower": ("meteor_shower_enabled", "meteor_shower_count"),
            "balloon": ("balloon_enabled", "balloon_count"),
            "water_drop": ("water_drop_enabled", "water_drop_count"),
        }

    def _ensure_extra_effects(self, r: QRectF, settings: EffectOverlaySettings, now: float):
        if not hasattr(self, "_extra_effects"):
            self._extra_effects = {}
        for kind, (enabled_attr, count_attr) in self._extra_kind_specs().items():
            enabled = bool(getattr(settings, enabled_attr, False))
            target = max(0, int(getattr(settings, count_attr, 0))) if enabled else 0
            items = self._extra_effects.setdefault(kind, [])
            while len(items) < target:
                items.append(self._new_extra_particle(kind, r, settings, now))
            if len(items) > target:
                self._extra_effects[kind] = items[:target]

    def _new_extra_particle(self, kind: str, r: QRectF, settings: EffectOverlaySettings, now: float):
        rnd = self._random
        w = max(1.0, r.width())
        h = max(1.0, r.height())
        def top_y(extra=0.35):
            return r.top() - rnd.random() * max(80.0, h * extra)
        def random_x():
            return r.left() + rnd.random() * w
        if kind == "snow":
            speed = max(0.01, float(getattr(settings, "snow_speed", 0.18)))
            size = max(1.0, float(getattr(settings, "snow_size", 4.5))) * (0.55 + rnd.random() * 0.9)
            return ExtraEffectParticle(kind, random_x(), top_y(), (-12 + rnd.random()*24)*speed, (20+rnd.random()*28)*speed, size, 0.55+rnd.random()*0.45, rnd.random()*10000, rnd.random()*math.tau, (-1+rnd.random()*2)*speed, 12, now)
        if kind == "snow_crystal":
            speed = max(0.01, float(getattr(settings, "snow_crystal_speed", 0.12)))
            size = max(3.0, float(getattr(settings, "snow_crystal_size", 15.0))) * (0.75 + rnd.random()*0.55)
            return ExtraEffectParticle(kind, random_x(), top_y(0.55), (-10+rnd.random()*20)*speed, (16+rnd.random()*20)*speed, size, 0.60+rnd.random()*0.40, rnd.random()*10000, rnd.random()*math.tau, (-0.9+rnd.random()*1.8)*speed, 16, now)
        if kind == "water_drop":
            speed = max(0.01, float(getattr(settings, "water_drop_speed", 0.48)))
            size = max(1.0, float(getattr(settings, "water_drop_size", 8.0))) * (0.65 + rnd.random()*0.75)
            return ExtraEffectParticle(kind, random_x(), top_y(0.45), (-7+rnd.random()*14)*speed, (90+rnd.random()*80)*speed, size, 0.65+rnd.random()*0.35, rnd.random()*10000, 0.0, 0.0, 8, now)
        if kind == "bubble":
            speed = max(0.01, float(getattr(settings, "bubble_speed", 0.26)))
            size = max(2.0, float(getattr(settings, "bubble_size", 12.0))) * (0.55 + rnd.random()*1.15)
            return ExtraEffectParticle(kind, random_x(), r.bottom()+rnd.random()*h*0.25, (-12+rnd.random()*24)*speed, -(22+rnd.random()*42)*speed, size, 0.45+rnd.random()*0.45, rnd.random()*10000, 0.0, 0.0, 14, now)
        if kind == "flame":
            speed = max(0.01, float(getattr(settings, "flame_speed", 0.55)))
            size = max(3.0, float(getattr(settings, "flame_size", 22.0))) * (0.45 + rnd.random()*1.05)
            x = r.left() + w * (0.38 + rnd.random()*0.24)
            return ExtraEffectParticle(kind, x, r.bottom()+rnd.random()*32, (-18+rnd.random()*36)*speed, -(70+rnd.random()*90)*speed, size, 0.55+rnd.random()*0.45, rnd.random()*10000, rnd.random()*math.tau, (-2+rnd.random()*4)*speed, 2.0+rnd.random()*1.5, now)
        if kind == "water_spray":
            speed = max(0.01, float(getattr(settings, "water_spray_speed", 0.75)))
            size = max(1.0, float(getattr(settings, "water_spray_size", 6.0))) * (0.5 + rnd.random()*1.0)
            x = r.center().x() + (-w*0.08 + rnd.random()*w*0.16)
            return ExtraEffectParticle(kind, x, r.bottom()+rnd.random()*16, (-90+rnd.random()*180)*speed, -(160+rnd.random()*210)*speed, size, 0.55+rnd.random()*0.45, rnd.random()*10000, 0.0, 0.0, 1.8+rnd.random()*1.2, now)
        if kind == "fireball":
            speed = max(0.01, float(getattr(settings, "fireball_speed", 0.34)))
            size = max(4.0, float(getattr(settings, "fireball_size", 20.0))) * (0.75 + rnd.random()*0.8)
            return ExtraEffectParticle(kind, random_x(), top_y(0.65), (-24+rnd.random()*48)*speed, (55+rnd.random()*55)*speed, size, 0.70+rnd.random()*0.30, rnd.random()*10000, rnd.random()*math.tau, (-1.5+rnd.random()*3)*speed, 12, now)
        if kind == "star_sky":
            size = max(0.2, float(getattr(settings, "star_sky_size", 1.6))) * (0.35 + rnd.random() * 1.25)
            return ExtraEffectParticle(kind, random_x(), r.top() + rnd.random() * h, 0.0, 0.0, size, 0.40 + rnd.random() * 0.60, rnd.random() * 10000, 0.0, 0.0, 999999.0, now)
        if kind in ("shooting_star", "meteor_shower"):
            speed = max(0.01, float(getattr(settings, f"{kind}_speed", 0.85)))
            size = max(3.0, float(getattr(settings, f"{kind}_size", 14.0))) * (0.70 + rnd.random()*0.75)
            x = r.left() - rnd.random()*w*0.35
            y = r.top() + rnd.random()*h*0.55 - h*0.12
            return ExtraEffectParticle(kind, x, y, (280+rnd.random()*260)*speed, (120+rnd.random()*180)*speed, size, 0.65+rnd.random()*0.35, rnd.random()*10000, -0.65, 0.0, 2.8+rnd.random()*2.2, now)
        if kind == "balloon":
            speed = max(0.01, float(getattr(settings, "balloon_speed", 0.20)))
            size = max(8.0, float(getattr(settings, "balloon_size", 34.0))) * (0.75 + rnd.random()*0.65)
            return ExtraEffectParticle(kind, random_x(), r.bottom()+rnd.random()*h*0.45, (-10+rnd.random()*20)*speed, -(25+rnd.random()*35)*speed, size, 0.75+rnd.random()*0.25, rnd.random()*10000, rnd.random()*math.tau, (-0.4+rnd.random()*0.8)*speed, 24, now)
        return ExtraEffectParticle(kind, random_x(), top_y(), 0.0, 20.0, 8.0, 1.0, rnd.random()*10000, 0.0, 0.0, 6, now)

    def _update_extra_effects(self, r: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        if not hasattr(self, "_extra_effects"):
            return
        for kind, items in list(self._extra_effects.items()):
            enabled = bool(getattr(settings, f"{kind}_enabled", False))
            if not enabled:
                self._extra_effects[kind] = []
                continue
            surface_attr = f"{kind}_surface_y"
            surface_y = r.top() + r.height() * max(0.0, min(1.0, float(getattr(settings, surface_attr, 0.86))))
            puddle_rect = self._puddle_rect(r, settings) if bool(getattr(settings, "puddle_enabled", False)) else QRectF()
            puddle_active = puddle_rect.isValid() and not puddle_rect.isNull()
            for item in list(items):
                prev_y = item.y
                if kind == "star_sky":
                    if not (r.left() - 4 <= item.x <= r.right() + 4 and r.top() - 4 <= item.y <= r.bottom() + 4):
                        item.__dict__.update(self._new_extra_particle(kind, r, settings, now).__dict__)
                    continue
                item.x += (item.vx + math.sin(now * 1.2 + item.seed) * 10.0) * dt
                item.y += item.vy * dt
                item.rotation += item.rotation_speed * dt
                
                if kind == "water_spray":
                    item.vy += 280.0 * dt
                if kind in ("flame", "water_spray") and now - item.created_at > item.life:
                    item.__dict__.update(self._new_extra_particle(kind, r, settings, now).__dict__)
                    continue
                impact_y = self._puddle_impact_y_for_x(r, settings, item.x) if puddle_active else surface_y
                hit_surface = kind in ("snow", "snow_crystal", "water_drop") and impact_y is not None and prev_y < impact_y <= item.y
                out = (item.y > r.bottom()+120 or item.y < r.top()-220 or item.x < r.left()-220 or item.x > r.right()+220)
                if hit_surface:
                    self._maybe_spawn_extra_ripple(kind, item, float(impact_y), settings, now)
                    item.__dict__.update(self._new_extra_particle(kind, r, settings, now).__dict__)
                    continue
                if out:
                    item.__dict__.update(self._new_extra_particle(kind, r, settings, now).__dict__)

    def _maybe_spawn_extra_ripple(self, kind: str, item, surface_y: float, settings: EffectOverlaySettings, now: float):
        ripple_enabled = bool(getattr(settings, f"{kind}_ripple_enabled", False))
        if not ripple_enabled:
            return
        chance = max(0.0, min(1.0, float(getattr(settings, f"{kind}_ripple_chance", 0.5))))
        if self._random.random() > chance:
            return
        if now - getattr(self, "_last_extra_ripple_time", 0.0) < 0.018:
            return
        if bool(getattr(settings, "puddle_enabled", False)):
            if not self._point_in_any_puddle(float(item.x), float(surface_y), self.rect, settings):
                return
        base = max(12.0, float(item.size) * (4.2 if kind == "snow_crystal" else 3.2))
        if kind == "water_drop":
            color = getattr(settings, "water_drop_color", "#9FE7FF")
        elif kind == "snow_crystal":
            color = getattr(settings, "snow_crystal_ripple_color", "#E8FBFF")
        else:
            color = getattr(settings, "snow_ripple_color", "#DFFBFF")
        self._ripples.append(EffectRipple(float(item.x), float(surface_y), now, base, color, max(0.05, float(getattr(settings, "ripple_speed", 1.0))) * 0.85))
        self._last_extra_ripple_time = now

    def _snow_accumulation_base_y(self, r: QRectF, settings: EffectOverlaySettings) -> float:
        """積雪が積もり始める基準Y座標を返す。0.0=上端、1.0=下端。"""
        ratio = max(0.0, min(1.0, float(getattr(settings, "snow_accumulation_start_y", 1.0))))
        return r.top() + r.height() * ratio

    def _ensure_snow_accumulation(self, r: QRectF, settings: EffectOverlaySettings):
        column_w = max(2.0, min(30.0, float(getattr(settings, "snow_accumulation_column_width", 7.0))))
        count = max(8, min(900, int(math.ceil(max(1.0, r.width()) / column_w))))
        start_y_key = round(max(0.0, min(1.0, float(getattr(settings, "snow_accumulation_start_y", 1.0)))), 3)
        key = (int(r.left()), int(r.top()), int(r.width()), int(r.height()), count, start_y_key)
        if getattr(self, "_snow_accum_rect_key", None) == key and len(getattr(self, "_snow_accum_heights", [])) == count:
            return
        old = list(getattr(self, "_snow_accum_heights", []))
        self._snow_accum_heights = [float(old[min(len(old)-1, int(i*len(old)/max(1,count)))]) if old else 0.0 for i in range(count)]
        self._snow_accum_rect_key = key
        self._last_snow_accum_update = time.time()

    def _update_snow_accumulation(self, r: QRectF, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "snow_accumulation_enabled", False)):
            self._last_snow_accum_update = now
            return
        self._ensure_snow_accumulation(r, settings)
        heights = getattr(self, "_snow_accum_heights", [])
        if not heights:
            return
        dt = max(0.0, min(0.15, now - float(getattr(self, "_last_snow_accum_update", now) or now)))
        self._last_snow_accum_update = now
        base_y = self._snow_accumulation_base_y(r, settings)
        available_depth = max(1.0, base_y - r.top())
        max_depth = max(1.0, available_depth * max(0.05, min(1.0, float(getattr(settings, "snow_accumulation_max_depth", 1.0)))))
        rate = max(0.0, float(getattr(settings, "snow_accumulation_build_rate", 7.0)))
        if dt <= 0.0 or rate <= 0.0:
            return
        snow_factor = 0.35 + min(2.0, max(0.0, float(getattr(settings, "snow_count", 90))) / 140.0)
        for i in range(len(heights)):
            drift = 0.72 + 0.28 * math.sin(now * 0.45 + i * 0.73)
            heights[i] = min(max_depth, max(0.0, heights[i] + rate * snow_factor * drift * dt))
        if len(heights) >= 3:
            smoothed = heights[:]
            for i in range(1, len(heights) - 1):
                smoothed[i] = heights[i] * 0.72 + (heights[i - 1] + heights[i + 1]) * 0.14
            self._snow_accum_heights = smoothed

    def _remove_snow_accumulation_at(self, pos: QPointF, settings: EffectOverlaySettings, strong: bool = False):
        if not bool(getattr(settings, "snow_accumulation_enabled", False)) or not bool(getattr(settings, "snow_accumulation_mouse_remove_enabled", True)):
            return
        r = self.rect
        self._ensure_snow_accumulation(r, settings)
        heights = getattr(self, "_snow_accum_heights", [])
        if not heights or r.width() <= 0:
            return
        radius = max(4.0, float(getattr(settings, "snow_accumulation_remove_radius", 58.0))) * (1.35 if strong else 1.0)
        strength = max(1.0, float(getattr(settings, "snow_accumulation_remove_strength", 72.0))) * (1.45 if strong else 1.0)
        column_w = max(1.0, r.width() / max(1, len(heights)))
        center = int((float(pos.x()) - r.left()) / column_w)
        reach = int(math.ceil(radius / column_w)) + 1
        for i in range(max(0, center - reach), min(len(heights), center + reach + 1)):
            cx = r.left() + (i + 0.5) * column_w
            dist = abs(cx - float(pos.x()))
            if dist <= radius:
                heights[i] = max(0.0, heights[i] - strength * ((1.0 - dist / max(1.0, radius)) ** 0.65))

    def _draw_snow_accumulation(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "snow_accumulation_enabled", False)):
            return
        self._update_snow_accumulation(r, settings, now)
        heights = getattr(self, "_snow_accum_heights", [])
        if not heights or r.width() <= 0 or r.height() <= 0:
            return
        alpha = max(0, min(255, int(getattr(settings, "snow_accumulation_alpha", 230) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0:
            return
        column_w = r.width() / max(1, len(heights))
        base_y = self._snow_accumulation_base_y(r, settings)
        path = QPainterPath(); path.moveTo(r.left(), base_y)
        for i, h in enumerate(heights):
            x = r.left() + i * column_w
            y = base_y - max(0.0, h) + math.sin(now * 0.35 + i * 0.55) * min(3.0, h * 0.05)
            path.lineTo(x, y)
        path.lineTo(r.right(), base_y - max(0.0, heights[-1])); path.lineTo(r.right(), base_y); path.closeSubpath()
        top = QColor(getattr(settings, "snow_color", "#F5FCFF")); top.setAlpha(alpha)
        shadow = QColor(getattr(settings, "snow_edge_color", "#CFEFFF")); shadow.setAlpha(max(0, min(255, int(alpha * 0.82))))
        grad = QLinearGradient(r.left(), r.top(), r.left(), r.bottom()); grad.setColorAt(0.0, top); grad.setColorAt(1.0, shadow)
        p.save(); p.setRenderHint(QPainter.RenderHint.Antialiasing, True); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawPath(path)
        pen = QPen(QColor(255, 255, 255, max(0, min(255, int(alpha * 0.72)))), max(1.0, min(4.0, column_w * 0.22))); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
        surface = QPainterPath()
        for i, h in enumerate(heights):
            x = r.left() + i * column_w
            y = base_y - max(0.0, h) + math.sin(now * 0.35 + i * 0.55) * min(3.0, h * 0.05)
            surface.moveTo(x, y) if i == 0 else surface.lineTo(x, y)
        p.drawPath(surface); p.restore()

    def _draw_extra_effects(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        if bool(getattr(settings, "water_surface_enabled", False)) or bool(getattr(settings, "puddle_enabled", False)):
            self._draw_water_surface(p, r, settings, now)
        if bool(getattr(settings, "ice_enabled", False)):
            self._draw_ice_surface(p, r, settings, now)
        if bool(getattr(settings, "milky_way_enabled", False)):
            self._draw_milky_way(p, r, settings, now)
        self._draw_snow_accumulation(p, r, settings, now)
        if not hasattr(self, "_extra_effects"):
            if bool(getattr(settings, "bamboo_grove_enabled", False)):
                self._draw_bamboo_grove(p, r, settings, now)
            return
        for kind, items in self._extra_effects.items():
            alpha_base = max(0, min(255, int(getattr(settings, f"{kind}_alpha", 210))))
            for item in list(items):
                alpha = max(0, min(255, int(alpha_base * item.alpha * max(0.0, float(getattr(settings, "intensity", 1.0))))))
                if alpha <= 0:
                    continue
                if kind == "snow":
                    self._draw_snow_dot(p, item, alpha, settings)
                elif kind == "snow_crystal":
                    self._draw_snow_crystal(p, item, alpha, settings)
                elif kind == "water_drop":
                    self._draw_water_drop(p, item, alpha, settings)
                elif kind == "bubble":
                    self._draw_bubble(p, item, alpha)
                elif kind == "flame":
                    self._draw_flame_particle(p, item, alpha, settings)
                elif kind == "water_spray":
                    self._draw_water_spray_particle(p, item, alpha, settings)
                elif kind == "fireball":
                    self._draw_fireball(p, item, alpha, settings)
                elif kind == "star_sky":
                    self._draw_star_sky_particle(p, item, alpha, settings, now)
                elif kind in ("shooting_star", "meteor_shower"):
                    self._draw_shooting_star(p, item, alpha)
                elif kind == "balloon":
                    self._draw_balloon(p, item, alpha)
        if bool(getattr(settings, "bamboo_grove_enabled", False)):
            self._draw_bamboo_grove(p, r, settings, now)

    def _draw_snow_dot(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings):
        base = QColor(getattr(settings, "snow_color", "#F5FCFF"))
        edge = QColor(getattr(settings, "snow_edge_color", "#CFEFFF"))
        base.setAlpha(alpha)
        edge.setAlpha(max(0, min(255, int(alpha * 0.72))))
        radius = max(1.0, item.size)
        p.setPen(QPen(edge, max(1, int(radius * 0.20))))
        p.setBrush(QBrush(base))
        p.drawEllipse(QPointF(item.x, item.y), radius, radius)

    def _draw_snow_crystal(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings):
        p.save()
        p.translate(item.x, item.y)
        p.rotate(math.degrees(item.rotation))
        c = QColor(getattr(settings, "snow_crystal_color", "#EBFAFF"))
        edge = QColor(getattr(settings, "snow_crystal_edge_color", "#D8F4FF"))
        c.setAlpha(alpha)
        edge.setAlpha(max(0, min(255, int(alpha * 0.70))))
        pen = QPen(c, max(1, int(item.size * 0.08)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for i in range(6):
            a = math.tau * i / 6.0
            x = math.cos(a) * item.size
            y = math.sin(a) * item.size
            p.drawLine(0, 0, int(x), int(y))
            bx = math.cos(a) * item.size * 0.58
            by = math.sin(a) * item.size * 0.58
            for sign in (-1, 1):
                ba = a + sign * 0.65
                p.drawLine(int(bx), int(by), int(bx + math.cos(ba)*item.size*0.25), int(by + math.sin(ba)*item.size*0.25))
        p.setPen(QPen(edge, max(1, int(item.size * 0.045))))
        p.drawEllipse(QPointF(0, 0), max(1.0, item.size * 0.16), max(1.0, item.size * 0.16))
        p.restore()

    def _draw_water_drop(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings):
        p.save()
        p.translate(item.x, item.y)
        path = QPainterPath()
        s = item.size
        path.moveTo(0, -s * 1.25)
        path.cubicTo(s * 0.85, -s * 0.25, s * 0.65, s * 0.85, 0, s * 1.0)
        path.cubicTo(-s * 0.65, s * 0.85, -s * 0.85, -s * 0.25, 0, -s * 1.25)
        base = QColor(getattr(settings, "water_drop_color", "#7DDCFF"))
        edge = QColor(getattr(settings, "water_drop_edge_color", "#D2F8FF"))
        dark = QColor(max(0, int(base.red() * 0.38)), max(0, int(base.green() * 0.58)), max(0, int(base.blue() * 0.82)), int(alpha * 0.72))
        grad = QRadialGradient(QPointF(-s * 0.25, -s * 0.35), max(1.0, s * 1.6))
        grad.setColorAt(0.0, QColor(255, 255, 255, min(255, alpha)))
        mid = QColor(base)
        mid.setAlpha(alpha)
        grad.setColorAt(0.45, mid)
        grad.setColorAt(1.0, dark)
        p.setBrush(QBrush(grad))
        outline = QColor(edge)
        outline.setAlpha(max(0, min(255, int(alpha * 0.75))))
        p.setPen(QPen(outline, max(1, int(s * 0.08))))
        p.drawPath(path)
        p.restore()

    def _draw_bubble(self, p: QPainter, item, alpha: int):
        c = QColor(170, 235, 255, max(20, int(alpha*0.55)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(c, max(1, int(item.size*0.08))))
        p.drawEllipse(QPointF(item.x, item.y), item.size, item.size)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255,255,255, int(alpha*0.35))))
        p.drawEllipse(QPointF(item.x-item.size*0.35, item.y-item.size*0.35), max(1.0,item.size*0.18), max(1.0,item.size*0.18))

    def _draw_flame_particle(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings):
        radius = max(2.0, item.size)
        core = QColor(getattr(settings, "flame_core_color", "#FFF58C"))
        mid = QColor(getattr(settings, "flame_mid_color", "#FF7823"))
        edge = QColor(getattr(settings, "flame_edge_color", "#FF1E00"))
        core.setAlpha(alpha)
        mid.setAlpha(max(0, min(255, int(alpha * 0.82))))
        edge.setAlpha(0)
        grad = QRadialGradient(QPointF(item.x, item.y), radius)
        grad.setColorAt(0.0, core)
        grad.setColorAt(0.45, mid)
        grad.setColorAt(1.0, edge)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(item.x, item.y), radius * 0.75, radius * 1.25)

    def _draw_water_spray_particle(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings):
        c = QColor(getattr(settings, "water_spray_color", "#82E1FF"))
        edge = QColor(getattr(settings, "water_spray_edge_color", "#D7FAFF"))
        c.setAlpha(alpha)
        edge.setAlpha(max(0, min(255, int(alpha * 0.55))))
        p.setPen(QPen(edge, max(1, int(item.size * 0.10))))
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(item.x, item.y), item.size, item.size)

    def _draw_fireball(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings):
        trail = QColor(getattr(settings, "fireball_trail_color", "#FF5A14"))
        for i in range(4, 0, -1):
            trail_alpha = int(alpha * 0.12 * i)
            tc = QColor(trail)
            tc.setAlpha(max(0, min(255, trail_alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(tc))
            p.drawEllipse(QPointF(item.x - item.vx * 0.012 * i, item.y - item.vy * 0.012 * i), item.size * (0.7 + i * 0.22), item.size * (0.7 + i * 0.22))
        core = QColor(getattr(settings, "fireball_core_color", "#FFFFBE"))
        mid = QColor(getattr(settings, "fireball_mid_color", "#FF7828"))
        edge = QColor(getattr(settings, "fireball_edge_color", "#AA1400"))
        core.setAlpha(alpha)
        mid.setAlpha(alpha)
        edge.setAlpha(0)
        grad = QRadialGradient(QPointF(item.x, item.y), item.size * 1.5)
        grad.setColorAt(0.0, core)
        grad.setColorAt(0.45, mid)
        grad.setColorAt(1.0, edge)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(item.x, item.y), item.size, item.size)

    def _has_water_mirror_reflection(self, settings: EffectOverlaySettings) -> bool:
        return bool(
            getattr(settings, "water_surface_enabled", False)
            and getattr(settings, "water_mirror_enabled", False)
            and int(getattr(settings, "water_mirror_alpha", 0)) > 0
        )

    def _blur_reflection_image(self, image: QImage, blur: float) -> QImage:
        blur = max(0.0, min(24.0, float(blur)))
        if image.isNull() or blur <= 0.05:
            return image
        
        factor = max(2, min(10, int(1.0 + blur * 0.45)))
        w = max(1, image.width() // factor)
        h = max(1, image.height() // factor)
        small = image.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        blurred = small.scaled(image.width(), image.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if blur >= 10.0:
            w2 = max(1, image.width() // max(2, factor // 2))
            h2 = max(1, image.height() // max(2, factor // 2))
            blurred = blurred.scaled(w2, h2, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).scaled(
                image.width(), image.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        return blurred


    def _puddle_specs(self, settings: EffectOverlaySettings):
        """Return normalized puddle specs. First puddle follows puddle_x/y; the rest are scattered deterministically."""
        count = max(1, min(12, int(getattr(settings, "puddle_count", 1))))
        base_x = max(0.0, min(1.0, float(getattr(settings, "puddle_x", 0.50))))
        base_y = max(0.0, min(1.0, float(getattr(settings, "puddle_y", 0.84))))
        base_w = max(0.05, min(1.20, float(getattr(settings, "puddle_width", 0.72))))
        base_h = max(0.02, min(0.70, float(getattr(settings, "puddle_height", 0.22))))
        spread = max(0.0, min(1.0, float(getattr(settings, "puddle_spread", 0.72))))
        loaded = []
        raw = getattr(settings, "puddles_json", "") or ""
        try:
            data = json.loads(raw) if raw else []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        loaded.append({
                            "x": max(0.0, min(1.0, float(item.get("x", base_x)))),
                            "y": max(0.0, min(1.0, float(item.get("y", base_y)))),
                            "width": max(0.03, min(1.20, float(item.get("width", base_w)))),
                            "height": max(0.015, min(0.70, float(item.get("height", base_h)))),
                        })
        except Exception:
            loaded = []
        if len(loaded) >= count:
            return loaded[:count]
        offsets = [
            (0.00, 0.00, 1.00, 1.00), (-0.26, -0.05, 0.54, 0.70),
            (0.28, 0.03, 0.48, 0.64), (-0.12, 0.13, 0.42, 0.56),
            (0.15, -0.14, 0.36, 0.50), (0.39, 0.13, 0.30, 0.46),
            (-0.42, 0.10, 0.32, 0.48), (0.02, -0.24, 0.28, 0.42),
            (0.45, -0.10, 0.25, 0.38), (-0.48, -0.16, 0.24, 0.36),
            (0.30, 0.25, 0.22, 0.34), (-0.28, 0.27, 0.22, 0.34),
        ]
        specs = list(loaded)
        for i in range(len(specs), count):
            ox, oy, sw, sh = offsets[i % len(offsets)]
            if count == 1:
                w = base_w
                h = base_h
            else:
                w = max(0.035, min(0.55, base_w * sw * 0.62))
                h = max(0.018, min(0.32, base_h * sh * 0.74))
            specs.append({
                "x": max(0.02, min(0.98, base_x + ox * spread)),
                "y": max(0.02, min(0.98, base_y + oy * spread)),
                "width": w,
                "height": h,
            })
        return specs

    def _set_puddle_specs(self, settings: EffectOverlaySettings, specs):
        cleaned = []
        for item in list(specs or [])[:12]:
            if isinstance(item, dict):
                cleaned.append({
                    "x": max(0.0, min(1.0, float(item.get("x", 0.5)))),
                    "y": max(0.0, min(1.0, float(item.get("y", 0.84)))),
                    "width": max(0.03, min(1.20, float(item.get("width", 0.20)))),
                    "height": max(0.015, min(0.70, float(item.get("height", 0.08)))),
                })
        settings.puddles_json = json.dumps(cleaned, ensure_ascii=False)
        if cleaned:
            settings.puddle_x = cleaned[0]["x"]
            settings.puddle_y = cleaned[0]["y"]
            if len(cleaned) == 1:
                settings.puddle_width = cleaned[0]["width"]
                settings.puddle_height = cleaned[0]["height"]

    def _puddle_rects(self, r: QRectF, settings: EffectOverlaySettings):
        rects = []
        if not bool(getattr(settings, "puddle_enabled", False)) or r.width() <= 0 or r.height() <= 0:
            return rects
        for i, spec in enumerate(self._puddle_specs(settings)):
            cx = r.left() + r.width() * max(0.0, min(1.0, float(spec.get("x", 0.5))))
            cy = r.top() + r.height() * max(0.0, min(1.0, float(spec.get("y", 0.84))))
            w = r.width() * max(0.03, min(1.20, float(spec.get("width", 0.2))))
            h = r.height() * max(0.015, min(0.70, float(spec.get("height", 0.08))))
            rects.append((i, QRectF(cx - w * 0.5, cy - h * 0.5, w, h)))
        return rects

    def _puddle_union_rect(self, r: QRectF, settings: EffectOverlaySettings) -> QRectF:
        rects = [rect for _, rect in self._puddle_rects(r, settings)]
        if not rects:
            return QRectF()
        union = QRectF(rects[0])
        for rect in rects[1:]:
            union = union.united(rect)
        return union

    def _puddle_rect(self, r: QRectF, settings: EffectOverlaySettings) -> QRectF:
        """Return the union bounds of all oval puddles."""
        return self._puddle_union_rect(r, settings)

    def _puddle_path(self, r: QRectF, settings: EffectOverlaySettings) -> QPainterPath:
        path = QPainterPath()
        for _, puddle_rect in self._puddle_rects(r, settings):
            if puddle_rect.isValid() and not puddle_rect.isNull():
                path.addEllipse(puddle_rect)
        return path

    def _point_in_puddle(self, x: float, y: float, puddle_rect: QRectF) -> bool:
        if puddle_rect is None or puddle_rect.isNull() or not puddle_rect.isValid():
            return False
        rx = max(1.0, puddle_rect.width() * 0.5)
        ry = max(1.0, puddle_rect.height() * 0.5)
        cx = puddle_rect.center().x()
        cy = puddle_rect.center().y()
        nx = (float(x) - cx) / rx
        ny = (float(y) - cy) / ry
        return nx * nx + ny * ny <= 1.0

    def _puddle_surface_y_for_x(self, x: float, puddle_rect: QRectF) -> Optional[float]:
        if puddle_rect is None or puddle_rect.isNull() or not puddle_rect.isValid():
            return None
        rx = max(1.0, puddle_rect.width() * 0.5)
        ry = max(1.0, puddle_rect.height() * 0.5)
        cx = puddle_rect.center().x()
        cy = puddle_rect.center().y()
        nx = (float(x) - cx) / rx
        if abs(nx) > 1.0:
            return None
        return cy - ry * math.sqrt(max(0.0, 1.0 - nx * nx))

    def _puddle_impact_y_for_x(self, r: QRectF, settings: EffectOverlaySettings, x: float) -> Optional[float]:
        best_y = None
        for _, rect in self._puddle_rects(r, settings):
            y = self._puddle_surface_y_for_x(x, rect)
            if y is not None and (best_y is None or y < best_y):
                best_y = y
        return best_y

    def _point_in_any_puddle(self, x: float, y: float, r: QRectF, settings: EffectOverlaySettings) -> bool:
        for _, rect in self._puddle_rects(r, settings):
            if self._point_in_puddle(x, y, rect):
                return True
        return False

    def _has_visible_puddle_effect(self, settings: Optional[EffectOverlaySettings] = None) -> bool:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        return bool(getattr(settings, "puddle_enabled", False))

    def puddle_interaction_rect(self, settings: Optional[EffectOverlaySettings] = None) -> QRectF:
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        rect = self._puddle_union_rect(self.rect, settings)
        if rect.isNull() or not rect.isValid():
            return QRectF()
        return rect.adjusted(-10.0, -10.0, 10.0, 10.0)

    def _puddle_hit_index(self, pos: QPoint, settings: Optional[EffectOverlaySettings] = None):
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        p = QPointF(pos)
        for index, rect in reversed(self._puddle_rects(self.rect, settings)):
            if rect.contains(p) and self._point_in_puddle(p.x(), p.y(), rect):
                return index
        return None

    def is_puddle_hit(self, pos: QPoint) -> bool:
        settings = get_effect_overlay_settings(self.cfg)
        return self._has_visible_puddle_effect(settings) and self._puddle_hit_index(pos, settings) is not None

    def puddle_drag_offset_from_pos(self, pos: QPoint):
        settings = get_effect_overlay_settings(self.cfg)
        index = self._puddle_hit_index(pos, settings)
        rects = dict(self._puddle_rects(self.rect, settings))
        rect = rects.get(index) if index is not None else self._puddle_rect(self.rect, settings)
        center = rect.center() if rect is not None and rect.isValid() and not rect.isNull() else self.rect.center()
        return index, QPointF(float(pos.x()) - center.x(), float(pos.y()) - center.y())

    def move_puddle_center_to(self, pos: QPoint, offset: Optional[QPointF] = None, index: Optional[int] = None):
        settings = get_effect_overlay_settings(self.cfg)
        r = self.rect
        if r.width() <= 0 or r.height() <= 0:
            return
        if offset is None:
            offset = QPointF(0.0, 0.0)
        specs = self._puddle_specs(settings)
        if not specs:
            return
        if index is None or index < 0 or index >= len(specs):
            index = 0
        new_center_x = float(pos.x()) - float(offset.x())
        new_center_y = float(pos.y()) - float(offset.y())
        specs[index]["x"] = max(0.0, min(1.0, (new_center_x - r.left()) / max(1.0, r.width())))
        specs[index]["y"] = max(0.0, min(1.0, (new_center_y - r.top()) / max(1.0, r.height())))
        self._set_puddle_specs(settings, specs)
        set_effect_overlay_settings(self.cfg, settings)

    def _puddle_resize_handles(self, rect: QRectF):
        """編集モード用: 個別水たまりのサイズ変更ハンドル。"""
        handle = max(8.0, min(16.0, min(rect.width(), rect.height()) * 0.12))
        return {
            "right": QRectF(rect.right() - handle * 0.5, rect.center().y() - handle * 0.5, handle, handle),
            "bottom": QRectF(rect.center().x() - handle * 0.5, rect.bottom() - handle * 0.5, handle, handle),
            "corner": QRectF(rect.right() - handle * 0.5, rect.bottom() - handle * 0.5, handle, handle),
        }

    def puddle_resize_hit_kind(self, pos: QPoint, settings: Optional[EffectOverlaySettings] = None):
        """サイズ変更ハンドルに当たった場合は (水たまりindex, handle_kind) を返す。"""
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        if not self._has_visible_puddle_effect(settings):
            return None, None
        point = QPointF(pos)
        for index, rect in reversed(self._puddle_rects(self.rect, settings)):
            handles = self._puddle_resize_handles(rect)
            for kind in ("corner", "right", "bottom"):
                if handles[kind].adjusted(-4.0, -4.0, 4.0, 4.0).contains(point):
                    return index, kind
        return None, None

    def is_puddle_resize_hit(self, pos: QPoint) -> bool:
        index, kind = self.puddle_resize_hit_kind(pos)
        return index is not None and kind is not None

    def resize_puddle_to(self, pos: QPoint, index: Optional[int] = None, kind: str = "corner"):
        """右/下/右下ハンドルのドラッグ位置から、指定した水たまりだけをリサイズする。"""
        settings = get_effect_overlay_settings(self.cfg)
        r = self.rect
        if r.width() <= 0 or r.height() <= 0:
            return
        specs = self._puddle_specs(settings)
        if not specs:
            return
        if index is None or index < 0 or index >= len(specs):
            index = 0
        spec = dict(specs[index])
        cx = r.left() + r.width() * max(0.0, min(1.0, float(spec.get("x", 0.5))))
        cy = r.top() + r.height() * max(0.0, min(1.0, float(spec.get("y", 0.84))))
        current_w = max(0.03, min(1.20, float(spec.get("width", getattr(settings, "puddle_width", 0.20)))))
        current_h = max(0.015, min(0.70, float(spec.get("height", getattr(settings, "puddle_height", 0.08)))))
        kind = str(kind or "corner")
        if kind in ("right", "corner"):
            spec["width"] = max(0.03, min(1.20, abs(float(pos.x()) - cx) * 2.0 / max(1.0, r.width())))
        else:
            spec["width"] = current_w
        if kind in ("bottom", "corner"):
            spec["height"] = max(0.015, min(0.70, abs(float(pos.y()) - cy) * 2.0 / max(1.0, r.height())))
        else:
            spec["height"] = current_h
        specs[index] = spec
        self._set_puddle_specs(settings, specs)
        set_effect_overlay_settings(self.cfg, settings)

    def _water_reflection_cache_key(self, source: QImage, water_rect: QRectF, settings: EffectOverlaySettings):
        return (
            int(source.cacheKey()) if source is not None and not source.isNull() else 0,
            int(water_rect.left()), int(water_rect.top()), int(water_rect.width()), int(water_rect.height()),
            round(float(getattr(settings, "water_mirror_blur", 5.0)), 2),
            round(float(getattr(settings, "water_mirror_depth", 0.65)), 3),
        )

    def _make_water_reflection_image(self, source: QImage, water_rect: QRectF, settings: EffectOverlaySettings) -> QImage:
        if source is None or source.isNull() or water_rect.width() <= 1 or water_rect.height() <= 1:
            return QImage()
        key_func = getattr(type(self), "_water_reflection_cache_key", None)
        if key_func is None:
            key = (
                int(source.cacheKey()) if source is not None and not source.isNull() else 0,
                int(water_rect.left()), int(water_rect.top()), int(water_rect.width()), int(water_rect.height()),
                round(float(getattr(settings, "water_mirror_blur", 5.0)), 2),
                round(float(getattr(settings, "water_mirror_depth", 0.65)), 3),
            )
        else:
            key = key_func(self, source, water_rect, settings)
        cached = getattr(self, "_water_reflection_cache_image", None)
        if getattr(self, "_water_reflection_cache_signature", None) == key and cached is not None and not cached.isNull():
            return cached
        x = max(0, int(water_rect.left()))
        w = max(1, min(int(water_rect.width()), source.width() - x))
        if w <= 0:
            return QImage()
        target_h = max(1, int(water_rect.height() * max(0.05, min(1.0, float(getattr(settings, "water_mirror_depth", 0.65))))))
        target_h = min(target_h, max(1, int(water_rect.height())))
        y0 = max(0, int(water_rect.top()))
        src_h = min(target_h, y0)
        if src_h <= 1:
            return QImage()
        src_y = max(0, y0 - src_h)
        reflected = source.copy(x, src_y, w, src_h).mirrored(False, True)
        if reflected.height() != target_h:
            reflected = reflected.scaled(w, target_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        reflected = self._blur_reflection_image(reflected, float(getattr(settings, "water_mirror_blur", 5.0)))
        self._water_reflection_cache_signature = key
        self._water_reflection_cache_image = reflected
        return reflected

    def _water_reflected_point(self, x: float, y: float, water_rect: QRectF, wave: float, now: float):
        surface_y = water_rect.top()
        reflected_y = surface_y + (surface_y - y)
        if reflected_y < water_rect.top() or reflected_y > water_rect.bottom():
            return None
        depth_t = max(0.0, min(1.0, (reflected_y - water_rect.top()) / max(1.0, water_rect.height())))
        wobble = math.sin(now * 1.15 + reflected_y * 0.055 + x * 0.015) * wave * (1.0 - depth_t * 0.55)
        return QPointF(x + wobble, reflected_y)

    def _draw_reflected_snow_like(self, p: QPainter, item, water_rect: QRectF, settings: EffectOverlaySettings, now: float, color_name: str, default_color: str, alpha: int, crystal: bool = False):
        pt = self._water_reflected_point(float(getattr(item, "x", 0.0)), float(getattr(item, "y", 0.0)), water_rect, float(getattr(settings, "water_mirror_wave", 7.0)), now)
        if pt is None:
            return
        depth_t = max(0.0, min(1.0, (pt.y() - water_rect.top()) / max(1.0, water_rect.height())))
        a = max(0, min(255, int(alpha * (0.52 - depth_t * 0.22))))
        if a <= 0:
            return
        c = QColor(getattr(settings, color_name, default_color)); c.setAlpha(a)
        size = max(1.0, float(getattr(item, "size", 3.0))) * (1.0 + depth_t * 0.18)
        if crystal:
            p.save(); p.translate(pt); p.rotate(math.degrees(float(getattr(item, "rotation", 0.0))))
            pen = QPen(c, max(1.0, size * 0.06)); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
            for i in range(6):
                ang = math.tau * i / 6.0
                p.drawLine(QPointF(0, 0), QPointF(math.cos(ang) * size, math.sin(ang) * size))
            p.restore()
        else:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawEllipse(pt, size, size * 0.72)

    def _draw_reflected_shooting_effect(self, p: QPainter, item, water_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha: int):
        pt = self._water_reflected_point(float(getattr(item, "x", 0.0)), float(getattr(item, "y", 0.0)), water_rect, float(getattr(settings, "water_mirror_wave", 7.0)), now)
        if pt is None:
            return
        vx = float(getattr(item, "vx", 1.0)); vy = -float(getattr(item, "vy", 0.48))
        speed_len = max(1.0, math.hypot(vx, vy)); tx = -vx / speed_len; ty = -vy / speed_len
        base_size = max(1.0, float(getattr(item, "size", 12.0)))
        tail = base_size * (6.0 if getattr(item, "kind", "") == "meteor_shower" else 7.5)
        a = max(0, min(255, int(alpha * 0.44)))
        pen = QPen(QColor(190, 230, 255, a), max(1.0, base_size * 0.10)); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(pt.x() + tx * tail, pt.y() + ty * tail), pt)
        core = QColor(235, 250, 255, max(0, min(255, int(a * 0.8))))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(core)); p.drawEllipse(pt, max(1.0, base_size * 0.22), max(1.0, base_size * 0.14))

    def _draw_reflected_petals_on_water(self, p: QPainter, water_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        rose_color = QColor(getattr(settings, "rose_petal_color", "#FF7AAE"))
        sakura_color = QColor(getattr(settings, "sakura_petal_color", "#FFB7D5"))
        for petal in list(getattr(self, "_rose_petals", [])):
            pt = self._water_reflected_point(float(petal.x), float(petal.y), water_rect, float(getattr(settings, "water_mirror_wave", 7.0)), now)
            if pt is None:
                continue
            c = QColor(rose_color); c.setAlpha(max(0, min(255, int(alpha_base * float(getattr(petal, "alpha", 1.0)) * 0.36))))
            p.save(); p.translate(pt); p.rotate(math.degrees(float(getattr(petal, "rotation", 0.0))))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c))
            s = max(1.0, float(getattr(petal, "size", 8.0)))
            p.drawEllipse(QPointF(0, 0), s * 0.45, s * 0.78)
            p.restore()
        for petal in list(getattr(self, "_sakura_petals", [])):
            pt = self._water_reflected_point(float(petal.x), float(petal.y), water_rect, float(getattr(settings, "water_mirror_wave", 7.0)), now)
            if pt is None:
                continue
            c = QColor(sakura_color); c.setAlpha(max(0, min(255, int(alpha_base * float(getattr(petal, "alpha", 1.0)) * 0.34))))
            p.save(); p.translate(pt); p.rotate(math.degrees(float(getattr(petal, "rotation", 0.0))))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c))
            s = max(1.0, float(getattr(petal, "size", 7.0)))
            p.drawEllipse(QPointF(0, 0), s * 0.50, s * 0.32)
            p.restore()

    def _draw_reflected_rain_on_water(self, p: QPainter, water_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        color = QColor(getattr(settings, "rain_color", "#9FD7FF"))
        base_length = float(getattr(settings, "rain_length", 16.0))
        for drop in list(getattr(self, "_rain", [])):
            pt = self._water_reflected_point(float(drop.x), float(drop.y), water_rect, float(getattr(settings, "water_mirror_wave", 7.0)), now)
            if pt is None:
                continue
            a = max(0, min(255, int(alpha_base * float(getattr(drop, "alpha", 1.0)) * 0.32)))
            c = QColor(color); c.setAlpha(a)
            pen = QPen(c, max(1, int(round(float(getattr(drop, "size", 1.0)))))); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            slant = float(getattr(drop, "vx", 0.0)) * 0.030
            p.drawLine(QPointF(pt.x(), pt.y()), QPointF(pt.x() - slant, pt.y() + base_length * 0.72))

    def _draw_reflected_bamboo_on_water(self, p: QPainter, r: QRectF, water_rect: QRectF, settings: EffectOverlaySettings, alpha_base: int):
        if not bool(getattr(settings, "bamboo_grove_enabled", False)):
            return
        cache = self._get_bamboo_grove_cache(r, settings) if hasattr(self, "_get_bamboo_grove_cache") else []
        if not cache:
            return
        stalk_src = QColor(getattr(settings, "bamboo_stalk_color", "#3EA65A"))
        shadow_src = QColor(getattr(settings, "bamboo_shadow_color", "#1F6F3B"))
        p.save(); p.setClipRect(water_rect); p.translate(0.0, water_rect.top() * 2.0); p.scale(1.0, -1.0)
        for item in cache:
            depth = float(item.get("depth", 1.0)); thickness = float(item.get("thickness", 8.0))
            a = max(0, min(255, int(alpha_base * (0.18 + 0.18 * depth))))
            shadow = QColor(shadow_src); shadow.setAlpha(max(0, min(255, int(a * 0.70))))
            stalk = QColor(stalk_src); stalk.setAlpha(a)
            pen_shadow = QPen(shadow, thickness * 1.08); pen_shadow.setCapStyle(Qt.PenCapStyle.RoundCap); pen_shadow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen_shadow); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(item.get("path", QPainterPath()))
            pen_stalk = QPen(stalk, thickness * 0.88); pen_stalk.setCapStyle(Qt.PenCapStyle.RoundCap); pen_stalk.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen_stalk); p.drawPath(item.get("path", QPainterPath()))
        p.restore()

    def _draw_reflected_effects_on_water(self, p: QPainter, r: QRectF, water_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        if not bool(getattr(settings, "water_mirror_reflect_effects_enabled", True)):
            return
        wave = max(0.0, float(getattr(settings, "water_mirror_wave", 7.0)))
        p.save(); p.setClipRect(water_rect)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        extra = getattr(self, "_extra_effects", {}) if hasattr(self, "_extra_effects") else {}
        if bool(getattr(settings, "water_mirror_reflect_snow", True)):
            for item in list(extra.get("snow", [])):
                self._draw_reflected_snow_like(p, item, water_rect, settings, now, "snow_color", "#F5FCFF", alpha_base, False)
        if bool(getattr(settings, "water_mirror_reflect_snow_crystal", True)):
            for item in list(extra.get("snow_crystal", [])):
                self._draw_reflected_snow_like(p, item, water_rect, settings, now, "snow_crystal_color", "#EBFAFF", alpha_base, True)
        if bool(getattr(settings, "water_mirror_reflect_shooting_star", True)):
            for item in list(extra.get("shooting_star", [])):
                self._draw_reflected_shooting_effect(p, item, water_rect, settings, now, alpha_base)
        if bool(getattr(settings, "water_mirror_reflect_meteor_shower", True)):
            for item in list(extra.get("meteor_shower", [])):
                self._draw_reflected_shooting_effect(p, item, water_rect, settings, now, alpha_base)
        if bool(getattr(settings, "water_mirror_reflect_petals", True)):
            self._draw_reflected_petals_on_water(p, water_rect, settings, now, alpha_base)
        if bool(getattr(settings, "water_mirror_reflect_rain", True)):
            self._draw_reflected_rain_on_water(p, water_rect, settings, now, alpha_base)
        p.restore()
        if bool(getattr(settings, "water_mirror_reflect_bamboo", True)):
            self._draw_reflected_bamboo_on_water(p, r, water_rect, settings, alpha_base)

    def _draw_water_mirror_reflection(self, p: QPainter, r: QRectF, water_rect: QRectF, settings: EffectOverlaySettings, now: float):
        if not self._has_water_mirror_reflection(settings):
            return
        alpha = max(0, min(255, int(getattr(settings, "water_mirror_alpha", 110) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0:
            return
        wave = max(0.0, float(getattr(settings, "water_mirror_wave", 7.0)))
        source = getattr(self, "_water_reflection_source_image", None)
        p.save()
        p.setClipRect(water_rect)
        if bool(getattr(settings, "water_mirror_reflect_widgets_enabled", True)) and source is not None and not source.isNull():
            reflected = self._make_water_reflection_image(source, water_rect, settings)
            if not reflected.isNull():
                p.setOpacity(alpha / 255.0)
                slice_h = max(2, min(12, int(reflected.height() / 36) if reflected.height() > 0 else 4))
                phase = now * (0.8 + max(0.0, float(getattr(settings, "water_surface_flow_speed", 0.55))) * 1.1)
                y = 0
                while y < reflected.height():
                    h = min(slice_h, reflected.height() - y)
                    yy = water_rect.top() + y
                    fade = 1.0 - min(1.0, y / max(1.0, reflected.height())) * 0.48
                    offset = math.sin(phase + y * 0.085) * wave * fade
                    src_rect = QRectF(0, y, reflected.width(), h)
                    dst_rect = QRectF(water_rect.left() + offset, yy, water_rect.width(), h)
                    p.drawImage(dst_rect, reflected, src_rect)
                    y += h
                p.setOpacity(1.0)
        p.restore()
        self._draw_reflected_effects_on_water(p, r, water_rect, settings, now, alpha)
        tint_alpha = max(0, min(255, int(getattr(settings, "water_mirror_tint_alpha", 58))))
        if tint_alpha > 0:
            p.save()
            p.setClipRect(water_rect)
            tint = QColor(getattr(settings, "water_surface_color", "#4FC3FF"))
            tint.setAlpha(max(0, min(255, int(tint_alpha * max(0.0, float(getattr(settings, "intensity", 1.0)))))))
            grad = QLinearGradient(water_rect.left(), water_rect.top(), water_rect.left(), water_rect.bottom())
            c0 = QColor(tint); c0.setAlpha(max(0, min(255, int(tint.alpha() * 0.25))))
            c1 = QColor(tint); c1.setAlpha(tint.alpha())
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRect(water_rect)
            p.restore()

    def _new_water_fish(self, water_rect: QRectF, settings: EffectOverlaySettings, now: float):
        rng = getattr(self, "_random", random.Random(20260505))
        direction = -1.0 if rng.random() < 0.5 else 1.0
        size = max(4.0, float(getattr(settings, "water_fish_size", 24.0))) * (0.70 + rng.random() * 0.65)
        y = water_rect.top() + water_rect.height() * (0.18 + rng.random() * 0.70)
        x = water_rect.left() + rng.random() * max(1.0, water_rect.width())
        speed = max(0.0, float(getattr(settings, "water_fish_speed", 0.28)))
        return {
            "x": float(x),
            "y": float(y),
            "vx": direction * (14.0 + rng.random() * 26.0) * (0.25 + speed),
            "size": float(size),
            "phase": rng.random() * math.tau,
            "depth": 0.55 + rng.random() * 0.45,
            "seed": rng.random() * 999.0,
        }

    def _ensure_water_fish(self, water_rect: QRectF, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "water_fish_enabled", True)):
            self._water_fish = []
            self._water_fish_rect_key = None
            return
        target = max(0, min(60, int(getattr(settings, "water_fish_count", 6))))
        if target <= 0:
            self._water_fish = []
            return
        rect_key = (int(water_rect.left()), int(water_rect.top()), int(water_rect.width()), int(water_rect.height()))
        if rect_key != getattr(self, "_water_fish_rect_key", None):
            self._water_fish = []
            self._water_fish_rect_key = rect_key
        while len(self._water_fish) < target:
            self._water_fish.append(self._new_water_fish(water_rect, settings, now))
        if len(self._water_fish) > target:
            self._water_fish = self._water_fish[:target]

    def _update_water_fish(self, water_rect: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        self._ensure_water_fish(water_rect, settings, now)
        if not getattr(self, "_water_fish", None):
            return
        pad = max(24.0, float(getattr(settings, "water_fish_size", 24.0)) * 4.0)
        for fish in self._water_fish:
            fish["x"] += fish["vx"] * dt
            fish["phase"] += dt * (2.2 + abs(fish["vx"]) * 0.018)
            fish["y"] += math.sin(fish["phase"] * 0.7 + fish["seed"]) * dt * 6.0
            fish["y"] = max(water_rect.top() + fish["size"] * 1.1, min(water_rect.bottom() - fish["size"] * 1.1, fish["y"]))
            if fish["vx"] > 0 and fish["x"] > water_rect.right() + pad:
                fish.update(self._new_water_fish(water_rect, settings, now))
                fish["x"] = water_rect.left() - pad
                fish["vx"] = abs(fish["vx"])
            elif fish["vx"] < 0 and fish["x"] < water_rect.left() - pad:
                fish.update(self._new_water_fish(water_rect, settings, now))
                fish["x"] = water_rect.right() + pad
                fish["vx"] = -abs(fish["vx"])

    def _draw_single_water_fish(self, p: QPainter, fish, settings: EffectOverlaySettings, alpha_base: int, now: float):
        """Draw a normal-sized, plump fish using curved QPainterPath shapes."""
        size = max(4.0, float(fish.get("size", 24.0)))
        direction = 1.0 if float(fish.get("vx", 1.0)) >= 0 else -1.0
        depth = max(0.15, min(1.0, float(fish.get("depth", 0.8))))
        alpha = max(0, min(255, int(alpha_base * (0.50 + depth * 0.50))))
        if alpha <= 0:
            return

        body = QColor(getattr(settings, "water_fish_color", "#7FE7D1"))
        body.setAlpha(alpha)
        hi = QColor(getattr(settings, "water_fish_secondary_color", "#D8FFF3"))
        hi.setAlpha(max(0, min(255, int(alpha * 0.76))))
        mid = QColor(
            min(255, int(body.red() * 1.08)),
            min(255, int(body.green() * 1.06)),
            min(255, int(body.blue() * 1.04)),
            alpha,
        )
        shade = QColor(
            max(0, int(body.red() * 0.58)),
            max(0, int(body.green() * 0.68)),
            max(0, int(body.blue() * 0.78)),
            max(0, min(255, int(alpha * 0.62))),
        )
        shadow = QColor(0, 48, 64, max(0, min(255, int(alpha * 0.18))))

        x = float(fish.get("x", 0.0))
        y = float(fish.get("y", 0.0))
        seed = float(fish.get("seed", 0.0))
        tail_wag = math.sin(now * 6.2 + seed) * size * 0.18
        body_bob = math.sin(now * 2.0 + seed * 0.07) * size * 0.04

        p.save()
        p.translate(x, y + body_bob)
        if direction < 0:
            p.scale(-1.0, 1.0)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)

        
        p.setBrush(QBrush(shadow))
        p.drawEllipse(QPointF(size * 0.04, size * 0.25), size * 1.10, size * 0.36)

        
        body_path = QPainterPath()
        body_path.moveTo(-size * 0.88, 0.0)
        body_path.cubicTo(-size * 0.70, -size * 0.68, size * 0.10, -size * 0.78, size * 0.88, -size * 0.18)
        body_path.cubicTo(size * 1.05, -size * 0.04, size * 1.04, size * 0.12, size * 0.88, size * 0.24)
        body_path.cubicTo(size * 0.22, size * 0.78, -size * 0.64, size * 0.68, -size * 0.88, 0.0)
        body_path.closeSubpath()

        body_grad = QRadialGradient(QPointF(size * 0.10, -size * 0.22), size * 1.28)
        body_grad.setColorAt(0.0, hi)
        body_grad.setColorAt(0.42, mid)
        body_grad.setColorAt(1.0, shade)
        p.setBrush(QBrush(body_grad))
        p.drawPath(body_path)

        
        tail = QPainterPath()
        tail.moveTo(-size * 0.74, 0.0)
        tail.cubicTo(-size * 1.02, -size * 0.56 + tail_wag, -size * 1.42, -size * 0.42 + tail_wag, -size * 1.28, -size * 0.02 + tail_wag * 0.30)
        tail.cubicTo(-size * 1.48, size * 0.42 + tail_wag, -size * 1.02, size * 0.56 + tail_wag, -size * 0.74, 0.0)
        tail.closeSubpath()
        tail_color = QColor(body)
        tail_color.setAlpha(max(0, min(255, int(alpha * 0.82))))
        p.setBrush(QBrush(tail_color))
        p.drawPath(tail)

        
        dorsal = QPainterPath()
        dorsal.moveTo(-size * 0.18, -size * 0.48)
        dorsal.cubicTo(-size * 0.02, -size * 0.92, size * 0.30, -size * 0.82, size * 0.44, -size * 0.38)
        dorsal.cubicTo(size * 0.18, -size * 0.50, size * 0.02, -size * 0.50, -size * 0.18, -size * 0.48)
        dorsal.closeSubpath()
        p.setBrush(QBrush(hi))
        p.drawPath(dorsal)

        
        lower_fin = QPainterPath()
        lower_fin.moveTo(-size * 0.02, size * 0.24)
        lower_fin.cubicTo(size * 0.10, size * 0.64, size * 0.44, size * 0.58, size * 0.42, size * 0.20)
        lower_fin.cubicTo(size * 0.26, size * 0.34, size * 0.12, size * 0.32, -size * 0.02, size * 0.24)
        lower_fin.closeSubpath()
        fin_color = QColor(hi)
        fin_color.setAlpha(max(0, min(255, int(alpha * 0.68))))
        p.setBrush(QBrush(fin_color))
        p.drawPath(lower_fin)

        
        shine = QPainterPath()
        shine.moveTo(size * 0.18, -size * 0.33)
        shine.cubicTo(size * 0.42, -size * 0.45, size * 0.68, -size * 0.32, size * 0.78, -size * 0.12)
        shine.cubicTo(size * 0.50, -size * 0.22, size * 0.34, -size * 0.22, size * 0.18, -size * 0.33)
        shine.closeSubpath()
        shine_color = QColor(255, 255, 255, max(0, min(255, int(alpha * 0.28))))
        p.setBrush(QBrush(shine_color))
        p.drawPath(shine)

        
        eye = QColor(4, 22, 28, max(0, min(255, int(alpha * 0.90))))
        p.setBrush(QBrush(eye))
        p.drawEllipse(QPointF(size * 0.62, -size * 0.12), max(1.2, size * 0.055), max(1.2, size * 0.055))
        p.setBrush(QBrush(QColor(255, 255, 255, max(0, min(255, int(alpha * 0.72))))))
        p.drawEllipse(QPointF(size * 0.64, -size * 0.14), max(0.45, size * 0.018), max(0.45, size * 0.018))
        mouth_pen = QPen(QColor(8, 42, 48, max(0, min(255, int(alpha * 0.50)))), max(1.0, size * 0.035))
        mouth_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(mouth_pen)
        mouth = QPainterPath()
        mouth.moveTo(size * 0.80, size * 0.03)
        mouth.cubicTo(size * 0.88, size * 0.08, size * 0.93, size * 0.04, size * 0.96, -size * 0.01)
        p.drawPath(mouth)

        p.restore()


    def _draw_water_fish(self, p: QPainter, water_rect: QRectF, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "water_fish_enabled", True)):
            return
        alpha = max(0, min(255, int(getattr(settings, "water_fish_alpha", 175) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0:
            return
        now_last = float(getattr(self, "_last_water_fish_update", now))
        dt = max(0.001, min(0.05, now - now_last))
        self._last_water_fish_update = now
        self._update_water_fish(water_rect, settings, dt, now)
        if not getattr(self, "_water_fish", None):
            return
        p.save()
        p.setClipRect(water_rect)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for fish in list(self._water_fish):
            self._draw_single_water_fish(p, fish, settings, alpha, now)
        p.restore()

    def _should_draw_morning_fog(self, settings: EffectOverlaySettings) -> bool:
        if not bool(getattr(settings, "water_morning_fog_enabled", True)):
            return False
        if bool(getattr(settings, "water_morning_fog_follow_sunrise", True)):
            return bool(getattr(settings, "sunrise_enabled", False))
        return True

    def _ensure_water_morning_fog(self, water_rect: QRectF, settings: EffectOverlaySettings, now: float):
        if not self._should_draw_morning_fog(settings):
            self._water_morning_fog = []
            self._water_morning_fog_rect_key = None
            return
        strength = max(0.0, float(getattr(settings, "water_morning_fog_strength", 0.65)))
        target = max(0, min(48, int(8 + strength * 12)))
        rect_key = (int(water_rect.left()), int(water_rect.top()), int(water_rect.width()), int(water_rect.height()))
        if rect_key != getattr(self, "_water_morning_fog_rect_key", None):
            self._water_morning_fog = []
            self._water_morning_fog_rect_key = rect_key
        rng = getattr(self, "_random", random.Random(20260505))
        height_ratio = max(0.05, min(0.60, float(getattr(settings, "water_morning_fog_height", 0.22))))
        while len(self._water_morning_fog) < target:
            self._water_morning_fog.append({
                "x": water_rect.left() + rng.random() * max(1.0, water_rect.width()),
                "y": water_rect.top() + rng.random() * max(1.0, water_rect.height() * height_ratio),
                "r": (18.0 + rng.random() * 54.0) * (0.55 + strength * 0.70),
                "seed": rng.random() * 999.0,
            })
        if len(self._water_morning_fog) > target:
            self._water_morning_fog = self._water_morning_fog[:target]

    def _update_water_morning_fog(self, water_rect: QRectF, settings: EffectOverlaySettings, now: float):
        self._ensure_water_morning_fog(water_rect, settings, now)
        if not getattr(self, "_water_morning_fog", None):
            return
        now_last = float(getattr(self, "_last_water_morning_fog_update", now))
        dt = max(0.001, min(0.05, now - now_last))
        self._last_water_morning_fog_update = now
        drift = max(0.0, float(getattr(settings, "water_morning_fog_drift", 0.35)))
        speed = (6.0 + drift * 18.0) * dt
        height_ratio = max(0.05, min(0.60, float(getattr(settings, "water_morning_fog_height", 0.22))))
        max_y = water_rect.top() + water_rect.height() * height_ratio
        for blob in self._water_morning_fog:
            blob["x"] += speed * (0.75 + 0.45 * math.sin(now * 0.35 + blob["seed"]))
            blob["y"] += math.sin(now * 0.55 + blob["seed"] * 0.03) * dt * (1.2 + drift * 2.0)
            if blob["x"] > water_rect.right() + blob["r"]:
                blob["x"] = water_rect.left() - blob["r"]
            if blob["y"] < water_rect.top() - blob["r"]:
                blob["y"] = water_rect.top() + blob["r"]
            blob["y"] = max(water_rect.top(), min(max_y, blob["y"]))

    def _draw_water_depth(self, p: QPainter, water_rect: QRectF, settings: EffectOverlaySettings, alpha_base: int):
        if not bool(getattr(settings, "water_depth_enabled", True)):
            return
        strength = max(0.0, min(2.0, float(getattr(settings, "water_depth_strength", 0.75))))
        if strength <= 0.01:
            return
        deep = QColor(getattr(settings, "water_depth_color", "#1A5B70"))
        haze_alpha = max(0, min(255, int(getattr(settings, "water_depth_haze_alpha", 48))))
        grad = QLinearGradient(water_rect.left(), water_rect.top(), water_rect.left(), water_rect.bottom())
        c0 = QColor(deep); c0.setAlpha(max(0, min(255, int(alpha_base * 0.06 * strength))))
        c1 = QColor(deep); c1.setAlpha(max(0, min(255, int(alpha_base * 0.18 * strength))))
        c2 = QColor(deep); c2.setAlpha(max(0, min(255, int(alpha_base * 0.34 * strength))))
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.55, c1)
        grad.setColorAt(1.0, c2)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(water_rect)
        if haze_alpha > 0:
            haze = QColor(255, 255, 255, max(0, min(255, int(haze_alpha * 0.55 * strength))))
            hgrad = QLinearGradient(water_rect.left(), water_rect.top(), water_rect.left(), water_rect.top() + water_rect.height() * 0.55)
            h0 = QColor(haze); h0.setAlpha(haze.alpha())
            h1 = QColor(haze); h1.setAlpha(0)
            hgrad.setColorAt(0.0, h0)
            hgrad.setColorAt(1.0, h1)
            p.setBrush(QBrush(hgrad))
            p.drawRect(QRectF(water_rect.left(), water_rect.top(), water_rect.width(), water_rect.height() * 0.55))
        p.restore()

    def _draw_water_morning_fog(self, p: QPainter, water_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        if not self._should_draw_morning_fog(settings):
            return
        strength = max(0.0, min(2.0, float(getattr(settings, "water_morning_fog_strength", 0.65))))
        alpha = max(0, min(255, int(getattr(settings, "water_morning_fog_alpha", 95) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0:
            return
        self._update_water_morning_fog(water_rect, settings, now)
        if not getattr(self, "_water_morning_fog", None):
            return
        fog_color = QColor(getattr(settings, "water_morning_fog_color", "#E9F6FF"))
        height_ratio = max(0.05, min(0.60, float(getattr(settings, "water_morning_fog_height", 0.22))))
        p.save()
        p.setClipRect(QRectF(water_rect.left(), water_rect.top(), water_rect.width(), water_rect.height() * height_ratio))
        p.setPen(Qt.PenStyle.NoPen)
        for blob in self._water_morning_fog:
            rr = float(blob.get("r", 28.0))
            x = float(blob.get("x", 0.0))
            y = float(blob.get("y", 0.0))
            fade = 0.65 + 0.35 * math.sin(now * 0.32 + float(blob.get("seed", 0.0)))
            a = max(0, min(255, int(alpha * 0.22 * strength * fade)))
            if a <= 0:
                continue
            c0 = QColor(fog_color); c0.setAlpha(a)
            c1 = QColor(fog_color); c1.setAlpha(0)
            g = QRadialGradient(QPointF(x, y), rr)
            g.setColorAt(0.0, c0)
            g.setColorAt(1.0, c1)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(x, y), rr, rr * (0.62 + 0.18 * strength))
        line_alpha = max(0, min(255, int(alpha * 0.28 * strength)))
        if line_alpha > 0:
            l = QColor(fog_color); l.setAlpha(line_alpha)
            lg = QLinearGradient(water_rect.left(), water_rect.top(), water_rect.left(), water_rect.top() + water_rect.height() * 0.22)
            l0 = QColor(l); l0.setAlpha(line_alpha)
            l1 = QColor(l); l1.setAlpha(0)
            lg.setColorAt(0.0, l0)
            lg.setColorAt(1.0, l1)
            p.setBrush(QBrush(lg))
            p.drawRect(QRectF(water_rect.left(), water_rect.top(), water_rect.width(), water_rect.height() * 0.22))
        p.restore()


    def _ice_reflected_effects_cache_key(self, ice_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        skip = max(0, min(12, int(getattr(settings, "ice_skip_reflected_effect_frames", 2))))
        bucket = int(now * 60.0) // max(1, skip + 1)
        extra = getattr(self, "_extra_effects", {}) if hasattr(self, "_extra_effects") else {}
        return (
            int(ice_rect.left()), int(ice_rect.top()), int(ice_rect.width()), int(ice_rect.height()),
            int(alpha_base), bucket,
            bool(getattr(settings, "ice_reflect_effects_enabled", True)),
            bool(getattr(settings, "ice_reflect_snow", True)), len(extra.get("snow", [])),
            bool(getattr(settings, "ice_reflect_snow_crystal", True)), len(extra.get("snow_crystal", [])),
            bool(getattr(settings, "ice_reflect_petals", True)), len(getattr(self, "_rose_petals", [])), len(getattr(self, "_sakura_petals", [])),
            bool(getattr(settings, "ice_reflect_bamboo", True)),
            bool(getattr(settings, "ice_reflect_shooting_star", True)), len(extra.get("shooting_star", [])),
            bool(getattr(settings, "ice_reflect_meteor_shower", True)), len(extra.get("meteor_shower", [])),
            bool(getattr(settings, "ice_reflect_rain", True)), len(getattr(self, "_rain", [])),
            round(float(getattr(settings, "ice_mirror_wave", 2.2)), 2),
        )

    def _draw_reflected_effects_on_ice(self, p: QPainter, r: QRectF, ice_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        """氷面の個別エフェクト反射を必要に応じて数フレームキャッシュする。"""
        if not bool(getattr(settings, "ice_reflect_effects_enabled", True)):
            return
        skip = max(0, min(12, int(getattr(settings, "ice_skip_reflected_effect_frames", 2))))
        if skip <= 0 or ice_rect.width() <= 1 or ice_rect.height() <= 1:
            self._draw_reflected_effects_on_ice_direct(p, r, ice_rect, settings, now, alpha_base)
            return
        key = self._ice_reflected_effects_cache_key(ice_rect, settings, now, alpha_base)
        cached = getattr(self, "_ice_reflected_effects_cache_image", None)
        if getattr(self, "_ice_reflected_effects_cache_signature", None) == key and cached is not None and not cached.isNull():
            p.drawImage(QPointF(ice_rect.left(), ice_rect.top()), cached)
            return
        img_w = max(1, int(math.ceil(ice_rect.width())))
        img_h = max(1, int(math.ceil(ice_rect.height())))
        image = QImage(img_w, img_h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        ip = QPainter(image)
        try:
            ip.setRenderHint(QPainter.RenderHint.Antialiasing, not bool(getattr(settings, "ice_lightweight_enabled", True)))
            ip.translate(-ice_rect.left(), -ice_rect.top())
            ip.setClipRect(ice_rect)
            self._draw_reflected_effects_on_ice_direct(ip, r, ice_rect, settings, now, alpha_base)
        finally:
            ip.end()
        self._ice_reflected_effects_cache_signature = key
        self._ice_reflected_effects_cache_image = image
        p.drawImage(QPointF(ice_rect.left(), ice_rect.top()), image)

    def _draw_reflected_effects_on_ice_direct(self, p: QPainter, r: QRectF, ice_rect: QRectF, settings: EffectOverlaySettings, now: float, alpha_base: int):
        """氷面専用の個別エフェクト反射。水面用の既存反射描画を流用しつつ、氷用ON/OFFで分岐する。"""
        if not bool(getattr(settings, "ice_reflect_effects_enabled", True)):
            return
        old_wave = getattr(settings, "water_mirror_wave", 7.0)
        try:
            settings.water_mirror_wave = float(getattr(settings, "ice_mirror_wave", 2.2))
            if bool(getattr(settings, "ice_reflect_snow", True)):
                for item in list(getattr(self, "_extra_effects", {}).get("snow", [])):
                    self._draw_reflected_snow_like(p, item, ice_rect, settings, now, "snow_color", "#F5FCFF", alpha_base, crystal=False)
            if bool(getattr(settings, "ice_reflect_snow_crystal", True)):
                for item in list(getattr(self, "_extra_effects", {}).get("snow_crystal", [])):
                    self._draw_reflected_snow_like(p, item, ice_rect, settings, now, "snow_crystal_color", "#EBFAFF", alpha_base, crystal=True)
            if bool(getattr(settings, "ice_reflect_petals", True)):
                self._draw_reflected_petals_on_water(p, ice_rect, settings, now, alpha_base)
            if bool(getattr(settings, "ice_reflect_bamboo", True)):
                self._draw_reflected_bamboo_on_water(p, r, ice_rect, settings, alpha_base)
            if bool(getattr(settings, "ice_reflect_shooting_star", True)):
                for item in list(getattr(self, "_extra_effects", {}).get("shooting_star", [])):
                    self._draw_reflected_shooting_effect(p, item, ice_rect, settings, now, alpha_base)
            if bool(getattr(settings, "ice_reflect_meteor_shower", True)):
                for item in list(getattr(self, "_extra_effects", {}).get("meteor_shower", [])):
                    self._draw_reflected_shooting_effect(p, item, ice_rect, settings, now, alpha_base)
            if bool(getattr(settings, "ice_reflect_rain", True)):
                self._draw_reflected_rain_on_water(p, ice_rect, settings, now, alpha_base)
        finally:
            try:
                settings.water_mirror_wave = old_wave
            except Exception:
                pass

    def _ice_surface_rect(self, r: QRectF, settings: EffectOverlaySettings) -> QRectF:
        """氷・氷河の描画領域を返す。水面とは独立してY/深さを調整できる。"""
        if r.width() <= 0 or r.height() <= 0:
            return QRectF()
        surface_ratio = max(0.0, min(1.0, float(getattr(settings, "ice_y", getattr(settings, "water_surface_y", 0.58)))))
        depth_ratio = max(0.05, min(1.0, float(getattr(settings, "ice_depth", getattr(settings, "water_surface_depth", 0.42)))))
        width_ratio = max(0.05, min(1.50, float(getattr(settings, "ice_width", 1.0))))
        center_ratio = max(0.0, min(1.0, float(getattr(settings, "ice_x", 0.50))))
        ice_w = max(1.0, r.width() * width_ratio)
        center_x = r.left() + r.width() * center_ratio
        x0 = center_x - ice_w * 0.5
        y0 = r.top() + r.height() * surface_ratio
        y1 = min(r.bottom(), y0 + r.height() * depth_ratio)
        if y1 <= y0:
            return QRectF()
        return QRectF(x0, y0, ice_w, y1 - y0)

    def _ice_reflection_cache_key(self, source: QImage, ice_rect: QRectF, settings: EffectOverlaySettings):
        skip = max(0, min(12, int(getattr(settings, "ice_mirror_skip_frames", 2))))
        if skip > 0:
            source_token = int(getattr(self, "_ice_reflection_frame_bucket", 0))
        else:
            source_token = int(source.cacheKey()) if source is not None and not source.isNull() else 0
        return (
            source_token,
            int(ice_rect.left()), int(ice_rect.top()), int(ice_rect.width()), int(ice_rect.height()),
            round(float(getattr(settings, "ice_mirror_blur", 3.5)), 2),
            round(float(getattr(settings, "ice_mirror_depth", 0.68)), 3),
            skip,
        )

    def _make_ice_reflection_image(self, source: QImage, ice_rect: QRectF, settings: EffectOverlaySettings) -> QImage:
        """氷面用の上下反転反射画像を作る。既存水面反射と同じ考え方だが、氷用パラメータで独立制御する。"""
        if source is None or source.isNull() or ice_rect.width() <= 1 or ice_rect.height() <= 1:
            return QImage()
        key = self._ice_reflection_cache_key(source, ice_rect, settings)
        cached = getattr(self, "_ice_reflection_cache_image", None)
        if getattr(self, "_ice_reflection_cache_signature", None) == key and cached is not None and not cached.isNull():
            return cached
        x = max(0, int(ice_rect.left()))
        w = max(1, min(int(ice_rect.width()), source.width() - x))
        if w <= 0:
            return QImage()
        target_h = max(1, int(ice_rect.height() * max(0.05, min(1.0, float(getattr(settings, "ice_mirror_depth", 0.68))))))
        target_h = min(target_h, max(1, int(ice_rect.height())))
        y0 = max(0, int(ice_rect.top()))
        src_h = min(target_h, y0)
        if src_h <= 1:
            return QImage()
        src_y = max(0, y0 - src_h)
        reflected = source.copy(x, src_y, w, src_h).mirrored(False, True)
        if reflected.height() != target_h:
            reflected = reflected.scaled(w, target_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        reflected = self._blur_reflection_image(reflected, float(getattr(settings, "ice_mirror_blur", 3.5)))
        self._ice_reflection_cache_signature = key
        self._ice_reflection_cache_image = reflected
        return reflected

    def _draw_ice_mirror_reflection(self, p: QPainter, r: QRectF, ice_rect: QRectF, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "ice_mirror_enabled", True)):
            return
        alpha = max(0, min(255, int(getattr(settings, "ice_mirror_alpha", 118) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0:
            return
        source = getattr(self, "_water_reflection_source_image", None)
        if not bool(getattr(settings, "ice_reflect_widgets_enabled", True)):
            return
        if source is None or source.isNull():
            return
        skip = max(0, min(12, int(getattr(settings, "ice_mirror_skip_frames", 2))))
        self._ice_reflection_frame_bucket = int(now * 60.0) // max(1, skip + 1)
        reflected = self._make_ice_reflection_image(source, ice_rect, settings)
        if reflected.isNull():
            return
        wave = max(0.0, float(getattr(settings, "ice_mirror_wave", 2.2)))
        p.save()
        p.setClipRect(ice_rect)
        p.setOpacity(alpha / 255.0)
        slice_h = max(2, min(10, int(reflected.height() / 42) if reflected.height() > 0 else 4))
        phase = now * (0.55 + max(0.0, float(getattr(settings, "water_surface_flow_speed", 0.55))) * 0.55)
        y = 0
        while y < reflected.height():
            h = min(slice_h, reflected.height() - y)
            fade = 1.0 - min(1.0, y / max(1.0, reflected.height())) * 0.62
            
            offset = math.sin(phase + y * 0.045) * wave * fade
            offset += math.sin(phase * 0.37 + y * 0.135) * wave * 0.32 * fade
            src_rect = QRectF(0, y, reflected.width(), h)
            dst_rect = QRectF(ice_rect.left() + offset, ice_rect.top() + y, ice_rect.width(), h)
            p.drawImage(dst_rect, reflected, src_rect)
            y += h
        p.setOpacity(1.0)
        tint_alpha = max(0, min(255, int(getattr(settings, "ice_mirror_tint_alpha", 70))))
        if tint_alpha > 0:
            tint = QColor(getattr(settings, "ice_color", "#9BDDF2"))
            tint.setAlpha(tint_alpha)
            grad = QLinearGradient(ice_rect.left(), ice_rect.top(), ice_rect.left(), ice_rect.bottom())
            t0 = QColor(tint); t0.setAlpha(max(0, min(255, int(tint_alpha * 0.22))))
            t1 = QColor(tint); t1.setAlpha(tint_alpha)
            t2 = QColor(tint); t2.setAlpha(max(0, min(255, int(tint_alpha * 0.45))))
            grad.setColorAt(0.0, t0)
            grad.setColorAt(0.52, t1)
            grad.setColorAt(1.0, t2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRect(ice_rect)
        p.restore()

    def _ice_static_cache_key(self, ice_rect: QRectF, settings: EffectOverlaySettings, alpha: int):
        q = max(0.25, min(1.0, float(getattr(settings, "ice_quality_scale", 0.58))))
        return (
            int(ice_rect.width()), int(ice_rect.height()), int(alpha), round(q, 3),
            str(getattr(settings, "ice_color", "#9BDDF2")),
            str(getattr(settings, "ice_edge_color", "#E8FBFF")),
            str(getattr(settings, "ice_highlight_color", "#F7FFFF")),
            str(getattr(settings, "ice_shadow_color", "#2C6F93")),
            round(float(getattr(settings, "ice_angle", -6.0)), 2),
            round(float(getattr(settings, "ice_size", 185.0)), 2),
            round(float(getattr(settings, "ice_crack_intensity", 0.46)), 3),
            round(float(getattr(settings, "ice_internal_bubble_intensity", 0.36)), 3),
            round(float(getattr(settings, "ice_glacier_roughness", 0.55)), 3),
            bool(getattr(settings, "ice_lightweight_enabled", True)),
            int(getattr(settings, "ice_max_facets", 72)),
            int(getattr(settings, "ice_max_cracks", 16)),
            int(getattr(settings, "ice_max_bubbles", 34)),
        )

    def _render_ice_static_surface_image(self, ice_rect: QRectF, settings: EffectOverlaySettings, alpha: int) -> QImage:
        """Render static ice geometry once into a small transparent image."""
        quality = max(0.25, min(1.0, float(getattr(settings, "ice_quality_scale", 0.58))))
        lightweight = bool(getattr(settings, "ice_lightweight_enabled", True))
        img_w = max(1, int(math.ceil(ice_rect.width() * quality)))
        img_h = max(1, int(math.ceil(ice_rect.height() * quality)))
        image = QImage(img_w, img_h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        ip = QPainter(image)
        try:
            ip.setRenderHint(QPainter.RenderHint.Antialiasing, not lightweight)
            local = QRectF(0.0, 0.0, float(img_w), float(img_h))
            base = QColor(getattr(settings, "ice_color", "#9BDDF2"))
            edge = QColor(getattr(settings, "ice_edge_color", "#E8FBFF"))
            hi = QColor(getattr(settings, "ice_highlight_color", "#F7FFFF"))
            shadow = QColor(getattr(settings, "ice_shadow_color", "#2C6F93"))
            angle = float(getattr(settings, "ice_angle", -6.0))
            block = max(20.0, float(getattr(settings, "ice_size", 185.0))) * quality
            roughness = max(0.0, min(1.5, float(getattr(settings, "ice_glacier_roughness", 0.55))))
            if lightweight:
                roughness *= 0.80
            grad = QLinearGradient(local.left(), local.top(), local.left(), local.bottom())
            c0 = QColor(hi); c0.setAlpha(max(0, min(255, int(alpha * 0.38))))
            c1 = QColor(base); c1.setAlpha(max(0, min(255, int(alpha * 0.64))))
            c2 = QColor(shadow); c2.setAlpha(max(0, min(255, int(alpha * 0.50))))
            grad.setColorAt(0.0, c0)
            grad.setColorAt(0.46, c1)
            grad.setColorAt(1.0, c2)
            ip.setPen(Qt.PenStyle.NoPen)
            ip.setBrush(QBrush(grad))
            ip.drawRect(local)

            rng_seed = 220515 + int(ice_rect.width()) * 7 + int(ice_rect.height()) * 11 + int(float(getattr(settings, "ice_size", 185.0))) * 13
            rng = random.Random(rng_seed)
            ip.save()
            center = local.center()
            ip.translate(center)
            ip.rotate(angle)
            ip.translate(-center)
            desired_cols = max(3, int(local.width() / max(24.0, block * 0.62)) + 2)
            desired_rows = max(2, int(local.height() / max(22.0, block * 0.42)) + 2)
            max_facets = max(8, int(getattr(settings, "ice_max_facets", 72)))
            if lightweight:
                max_facets = min(max_facets, 72)
            while desired_cols * desired_rows > max_facets and (desired_cols > 3 or desired_rows > 2):
                if desired_cols >= desired_rows and desired_cols > 3:
                    desired_cols -= 1
                elif desired_rows > 2:
                    desired_rows -= 1
                else:
                    break
            cols, rows = desired_cols, desired_rows
            cell_w = local.width() / max(1, cols - 1)
            cell_h = local.height() / max(1, rows - 1)
            start_x = local.left() - cell_w
            start_y = local.top() - cell_h
            facet_pen_width = max(0.5, block * (0.004 if lightweight else 0.006))
            for row in range(rows):
                for col in range(cols):
                    x = start_x + col * cell_w + rng.uniform(-cell_w, cell_w) * 0.14 * roughness
                    y = start_y + row * cell_h + rng.uniform(-cell_h, cell_h) * 0.17 * roughness
                    w = cell_w * rng.uniform(0.78, 1.25)
                    h = cell_h * rng.uniform(0.76, 1.30)
                    path = QPainterPath()
                    path.moveTo(x + rng.uniform(-w, w) * 0.04, y + rng.uniform(-h, h) * 0.04)
                    path.lineTo(x + w * rng.uniform(0.86, 1.14), y + h * rng.uniform(-0.06, 0.10))
                    path.lineTo(x + w * rng.uniform(0.80, 1.12), y + h * rng.uniform(0.84, 1.14))
                    path.lineTo(x + w * rng.uniform(-0.12, 0.15), y + h * rng.uniform(0.84, 1.12))
                    path.closeSubpath()
                    shade_pick = rng.random()
                    if shade_pick < 0.44:
                        fill = QColor(hi); fill.setAlpha(max(0, min(255, int(alpha * rng.uniform(0.06, 0.14)))))
                    elif shade_pick < 0.78:
                        fill = QColor(base); fill.setAlpha(max(0, min(255, int(alpha * rng.uniform(0.08, 0.20)))))
                    else:
                        fill = QColor(shadow); fill.setAlpha(max(0, min(255, int(alpha * rng.uniform(0.06, 0.14)))))
                    outline = QColor(edge); outline.setAlpha(max(0, min(255, int(alpha * rng.uniform(0.08, 0.20)))))
                    ip.setBrush(QBrush(fill))
                    ip.setPen(QPen(outline, facet_pen_width))
                    ip.drawPath(path)
            ip.restore()

            bubble_intensity = max(0.0, min(2.0, float(getattr(settings, "ice_internal_bubble_intensity", 0.36))))
            if bubble_intensity > 0.01:
                rng = random.Random(rng_seed + 101)
                count = int((local.width() * local.height()) / 14500.0 * bubble_intensity)
                count = min(max(0, count), max(0, int(getattr(settings, "ice_max_bubbles", 34))))
                for _ in range(count):
                    x = local.left() + rng.random() * local.width()
                    y = local.top() + rng.random() * local.height()
                    rr = rng.uniform(1.0, max(1.5, block * 0.030))
                    c = QColor(255, 255, 255, max(8, min(95, int(alpha * rng.uniform(0.06, 0.22)))))
                    ip.setPen(Qt.PenStyle.NoPen)
                    ip.setBrush(QBrush(c))
                    ip.drawEllipse(QPointF(x, y), rr, rr * rng.uniform(0.55, 1.05))

            crack_intensity = max(0.0, min(2.0, float(getattr(settings, "ice_crack_intensity", 0.46))))
            if crack_intensity > 0.01:
                rng = random.Random(rng_seed + 202)
                crack_count = int((local.width() / 150.0 + local.height() / 90.0) * crack_intensity)
                crack_count = min(max(1, crack_count), max(0, int(getattr(settings, "ice_max_cracks", 16))))
                for _ in range(crack_count):
                    x = local.left() + rng.random() * local.width()
                    y = local.top() + rng.random() * local.height()
                    length = rng.uniform(block * 0.32, block * 0.95) * (0.55 + crack_intensity * 0.30)
                    dir_angle = math.radians(angle + rng.uniform(-42, 42))
                    pts = [QPointF(x, y)]
                    segments = rng.randint(2 if lightweight else 3, 5 if lightweight else 7)
                    for _seg in range(segments):
                        step = length / max(1, segments) * rng.uniform(0.65, 1.14)
                        dir_angle += rng.uniform(-0.55, 0.55)
                        x += math.cos(dir_angle) * step
                        y += math.sin(dir_angle) * step
                        pts.append(QPointF(x, y))
                    crack_col = QColor(edge); crack_col.setAlpha(max(0, min(255, int(alpha * rng.uniform(0.28, 0.62)))))
                    pen = QPen(crack_col, rng.uniform(0.6, 1.8) * (0.80 + crack_intensity * 0.18))
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    ip.setPen(pen)
                    for a, b in zip(pts, pts[1:]):
                        ip.drawLine(a, b)
                        if (not lightweight) and rng.random() < 0.35:
                            branch_angle = math.atan2(b.y() - a.y(), b.x() - a.x()) + rng.choice([-1, 1]) * rng.uniform(0.55, 1.05)
                            branch_len = length * rng.uniform(0.06, 0.18)
                            ip.drawLine(b, QPointF(b.x() + math.cos(branch_angle) * branch_len, b.y() + math.sin(branch_angle) * branch_len))

            ip.save()
            ip.translate(local.center())
            ip.rotate(angle)
            ip.translate(-local.center())
            highlight_pen = QPen(QColor(255, 255, 255, max(0, min(255, int(alpha * 0.22)))), max(0.8, block * 0.006))
            highlight_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            ip.setPen(highlight_pen)
            line_count = max(3, min(10, int(local.width() / max(80.0 * quality, block * 0.55))))
            for i in range(line_count):
                yy = local.top() + local.height() * (0.12 + 0.70 * (i + 0.4) / max(1, line_count))
                ip.drawLine(QPointF(local.left() + block * 0.10, yy), QPointF(local.right() - block * 0.12, yy + math.sin(i) * block * 0.05))
            ip.restore()

            top_pen = QPen(QColor(edge.red(), edge.green(), edge.blue(), max(0, min(255, int(alpha * 0.68)))), max(1.0, block * 0.008))
            top_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            ip.setPen(top_pen)
            ip.drawLine(QPointF(local.left(), local.top() + 1.0), QPointF(local.right(), local.top() + 1.0))
        finally:
            ip.end()
        return image

    def _draw_ice_static_surface_cached(self, p: QPainter, ice_rect: QRectF, settings: EffectOverlaySettings, alpha: int):
        key = self._ice_static_cache_key(ice_rect, settings, alpha)
        cached = getattr(self, "_ice_surface_cache_image", None)
        if bool(getattr(settings, "ice_static_cache_enabled", True)) and getattr(self, "_ice_surface_cache_signature", None) == key and cached is not None and not cached.isNull():
            p.drawImage(ice_rect, cached)
            return
        image = self._render_ice_static_surface_image(ice_rect, settings, alpha)
        if bool(getattr(settings, "ice_static_cache_enabled", True)):
            self._ice_surface_cache_signature = key
            self._ice_surface_cache_image = image
        p.drawImage(ice_rect, image)

    def _draw_ice_fog_fast(self, p: QPainter, ice_rect: QRectF, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "ice_fog_enabled", True)):
            return
        fog_alpha = max(0, min(255, int(getattr(settings, "ice_fog_alpha", 72) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if fog_alpha <= 0:
            return
        fog_h = ice_rect.height() * max(0.02, min(0.80, float(getattr(settings, "ice_fog_height", 0.24))))
        drift = max(0.0, float(getattr(settings, "ice_fog_drift", 0.30)))
        fog_color = QColor(getattr(settings, "ice_fog_color", "#EEF9FF"))
        fog_rect = QRectF(ice_rect.left(), ice_rect.top(), ice_rect.width(), fog_h)
        fg = QLinearGradient(fog_rect.left(), fog_rect.top(), fog_rect.left(), fog_rect.bottom())
        f0 = QColor(fog_color); f0.setAlpha(max(0, min(255, int(fog_alpha * 0.18))))
        f1 = QColor(fog_color); f1.setAlpha(fog_alpha)
        f2 = QColor(fog_color); f2.setAlpha(0)
        fg.setColorAt(0.0, f0)
        fg.setColorAt(0.42, f1)
        fg.setColorAt(1.0, f2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fg))
        p.drawRect(fog_rect)
        if not bool(getattr(settings, "ice_lightweight_enabled", True)):
            fog_pen = QPen(QColor(fog_color.red(), fog_color.green(), fog_color.blue(), max(0, min(255, int(fog_alpha * 0.30)))), max(1.0, fog_h * 0.035))
            fog_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(fog_pen)
            for i in range(6):
                t = i / 5.0
                xoff = math.sin(now * (0.35 + drift) + i * 0.9) * ice_rect.width() * 0.028 * drift
                y = fog_rect.top() + fog_h * (0.18 + 0.58 * t)
                p.drawLine(QPointF(fog_rect.left() + xoff, y), QPointF(fog_rect.right() + xoff, y + math.sin(i * 1.3) * fog_h * 0.08))

    def _draw_ice_surface(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        """軽量化したリアル寄りの氷/氷河表現。
        静的な氷板・亀裂・気泡はキャッシュし、毎フレームは反射/霧だけを更新する。
        """
        alpha = max(0, min(255, int(getattr(settings, "ice_alpha", 178) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0 or r.width() <= 0 or r.height() <= 0:
            return
        ice_rect = self._ice_surface_rect(r, settings)
        if ice_rect.isNull() or not ice_rect.isValid():
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, not bool(getattr(settings, "ice_lightweight_enabled", True)))
        p.setClipRect(ice_rect)
        self._draw_ice_mirror_reflection(p, r, ice_rect, settings, now)
        self._draw_reflected_effects_on_ice(p, r, ice_rect, settings, now, alpha)
        self._draw_ice_static_surface_cached(p, ice_rect, settings, alpha)
        self._draw_ice_fog_fast(p, ice_rect, settings, now)
        p.restore()

    def _draw_water_surface(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        alpha = max(0, min(255, int(getattr(settings, "water_surface_alpha", 92) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha <= 0 or r.width() <= 0 or r.height() <= 0:
            return
        puddle_active = bool(getattr(settings, "puddle_enabled", False))
        if puddle_active:
            water_rect = self._puddle_rect(r, settings)
            if water_rect.isNull() or not water_rect.isValid() or water_rect.width() <= 1 or water_rect.height() <= 1:
                return
            y0 = water_rect.top()
            y1 = water_rect.bottom()
        else:
            surface_ratio = max(0.0, min(1.0, float(getattr(settings, "water_surface_y", 0.58))))
            depth_ratio = max(0.05, min(1.0, float(getattr(settings, "water_surface_depth", 0.42))))
            y0 = r.top() + r.height() * surface_ratio
            y1 = min(r.bottom(), y0 + r.height() * depth_ratio)
            if y1 <= y0:
                return
            water_rect = QRectF(r.left(), y0, r.width(), y1 - y0)
        base = QColor(getattr(settings, "water_surface_color", "#4FC3FF"))
        hi = QColor(getattr(settings, "water_surface_highlight_color", "#D8FAFF"))
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if puddle_active:
            puddle_path = self._puddle_path(r, settings)
            p.setClipPath(puddle_path)
        else:
            p.setClipRect(water_rect)
        self._draw_water_mirror_reflection(p, r, water_rect, settings, now)
        grad = QLinearGradient(water_rect.left(), water_rect.top(), water_rect.left(), water_rect.bottom())
        c0 = QColor(base); c0.setAlpha(max(0, min(255, int(alpha * 0.28))))
        c1 = QColor(base); c1.setAlpha(max(0, min(255, int(alpha * 0.76))))
        c2 = QColor(base); c2.setAlpha(max(0, min(255, int(alpha * 0.44))))
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.45, c1)
        grad.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(water_rect)
        self._draw_water_depth(p, water_rect, settings, alpha)
        self._draw_water_morning_fog(p, water_rect, settings, now, alpha)
        self._draw_water_fish(p, water_rect, settings, now)
        wave_count = max(0, min(120, int(getattr(settings, "water_surface_wave_count", 14))))
        if wave_count <= 0:
            p.restore()
            return
        angle = float(getattr(settings, "water_surface_flow_angle", 0.0))
        speed = max(0.0, float(getattr(settings, "water_surface_flow_speed", 0.55)))
        wave_height = max(0.0, float(getattr(settings, "water_surface_wave_height", 12.0)))
        span = math.hypot(max(1.0, r.width()), max(1.0, r.height())) * 1.35
        phase = now * (0.65 + speed * 1.75)
        center = water_rect.center()
        p.translate(center)
        p.rotate(angle)
        p.translate(-center)
        line_alpha = max(0, min(255, int(alpha * 0.62)))
        hi.setAlpha(line_alpha)
        base_line = QColor(base)
        base_line.setAlpha(max(0, min(255, int(alpha * 0.36))))
        step_y = max(4.0, water_rect.height() / max(1, wave_count))
        samples = 32
        for i in range(wave_count):
            y = water_rect.top() + (i + 0.5) * step_y
            amp = wave_height * (0.22 + 0.78 * (i + 1) / max(1, wave_count))
            wobble = math.sin(phase * 0.73 + i * 1.71)
            path = QPainterPath()
            for s in range(samples + 1):
                t = s / samples
                x = center.x() - span * 0.5 + span * t
                yy = y + math.sin(t * math.tau * (1.5 + (i % 4) * 0.35) + phase + i * 0.91) * amp * 0.35 + wobble * amp * 0.22
                if s == 0:
                    path.moveTo(x, yy)
                else:
                    path.lineTo(x, yy)
            pen_color = hi if i % 2 == 0 else base_line
            pen = QPen(pen_color, max(1.0, 0.8 + amp * 0.035))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        
        edge = QColor(hi)
        edge.setAlpha(max(0, min(255, int(alpha * 0.78))))
        p.setPen(QPen(edge, max(1.0, 1.3 + wave_height * 0.025)))
        if puddle_active:
            edge_softness = max(0.0, min(1.0, float(getattr(settings, "puddle_edge_softness", 0.18))))
            p.setPen(QPen(edge, max(1.0, 1.0 + wave_height * 0.02 + edge_softness * 2.0)))
            for _, puddle_rect in self._puddle_rects(r, settings):
                p.drawEllipse(puddle_rect.adjusted(1.5, 1.5, -1.5, -1.5))
        else:
            p.drawLine(QPointF(r.left() - span * 0.15, y0), QPointF(r.right() + span * 0.15, y0 + math.sin(phase) * max(1.0, wave_height * 0.08)))
        p.restore()

    def _bamboo_curve_point(self, base: QPointF, top: QPointF, bend: float, side: float, t: float):
        t = max(0.0, min(1.0, float(t)))
        height = base.y() - top.y()
        curve = math.sin(t * math.pi) * bend * height * 0.16 * side
        sway = math.sin(t * math.pi * 1.7) * bend * height * 0.035 * side
        x = base.x() + (top.x() - base.x()) * t + curve + sway
        y = base.y() + (top.y() - base.y()) * t
        return QPointF(x, y)

    def _bamboo_curve_tangent_angle(self, base: QPointF, top: QPointF, bend: float, side: float, t: float):
        p1 = self._bamboo_curve_point(base, top, bend, side, max(0.0, t - 0.01))
        p2 = self._bamboo_curve_point(base, top, bend, side, min(1.0, t + 0.01))
        return math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))

    def _draw_bamboo_leaf(self, p: QPainter, origin: QPointF, angle_degrees: float, length: float, width: float, color: QColor, depth: float = 1.0):
        p.save()
        p.translate(origin)
        p.rotate(angle_degrees)
        path = QPainterPath()
        path.moveTo(0.0, 0.0)
        path.cubicTo(length * 0.30, -width, length * 0.72, -width * 0.70, length, 0.0)
        path.cubicTo(length * 0.72, width * 0.70, length * 0.30, width, 0.0, 0.0)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        leaf = QColor(color)
        leaf.setAlpha(max(0, min(255, int(color.alpha() * (0.62 + 0.38 * depth)))))
        p.setBrush(QBrush(leaf))
        p.drawPath(path)
        p.restore()

    def _bamboo_cache_key(self, r: QRectF, settings: EffectOverlaySettings):
        return (
            int(r.width()), int(r.height()),
            max(0, int(getattr(settings, "bamboo_count", 12))),
            round(float(getattr(settings, "bamboo_thickness", 16.0)), 2),
            round(float(getattr(settings, "bamboo_angle", 0.0)), 2),
            round(float(getattr(settings, "bamboo_bend", 0.32)), 3),
            round(float(getattr(settings, "bamboo_height", 0.92)), 3),
            max(0, int(getattr(settings, "bamboo_leaf_density", 4))),
            round(float(getattr(settings, "bamboo_depth_strength", 0.85)), 3),
            round(float(getattr(settings, "bamboo_layer_spread", 0.42)), 3),
        )

    def _get_bamboo_grove_cache(self, r: QRectF, settings: EffectOverlaySettings):
        key = self._bamboo_cache_key(r, settings)
        if getattr(self, "_bamboo_grove_cache_key", None) == key and hasattr(self, "_bamboo_grove_cache"):
            return self._bamboo_grove_cache
        count = max(0, int(getattr(settings, "bamboo_count", 12)))
        thickness_base = max(2.0, float(getattr(settings, "bamboo_thickness", 16.0)))
        angle_base = max(-45.0, min(45.0, float(getattr(settings, "bamboo_angle", 0.0))))
        bend_base = max(0.0, min(2.0, float(getattr(settings, "bamboo_bend", 0.32))))
        height_ratio = max(0.10, min(1.50, float(getattr(settings, "bamboo_height", 0.92))))
        leaf_density = max(0, int(getattr(settings, "bamboo_leaf_density", 4)))
        depth_strength = max(0.0, min(2.0, float(getattr(settings, "bamboo_depth_strength", 0.85))))
        layer_spread = max(0.0, min(1.0, float(getattr(settings, "bamboo_layer_spread", 0.42))))
        rng = random.Random(88231 + count * 17)
        cache = []
        for i in range(count):
            slot = (i + 0.5) / max(1, count)
            jitter = (rng.random() - 0.5) / max(1, count) * 0.82
            x = r.left() + r.width() * max(0.0, min(1.0, slot + jitter))
            depth = 0.38 + 0.62 * rng.random()
            layer_offset = (depth - 0.5) * r.width() * 0.050 * layer_spread
            x += layer_offset
            depth_scale = 0.64 + 0.58 * depth_strength * depth
            thickness = thickness_base * depth_scale
            height = r.height() * height_ratio * (0.62 + 0.48 * depth)
            base = QPointF(x, r.bottom() + thickness * (1.1 + 0.8 * depth))
            angle = angle_base + (-6.0 + rng.random() * 12.0) * (0.65 + 0.35 * depth)
            rad = math.radians(angle)
            top = QPointF(base.x() + math.sin(rad) * height * 0.36, base.y() - math.cos(rad) * height)
            side = -1.0 if i % 2 else 1.0
            bend = bend_base * (0.70 + 0.62 * rng.random()) * (0.78 + depth * 0.34)
            path = QPainterPath()
            p0 = self._bamboo_curve_point(base, top, bend, side, 0.0)
            path.moveTo(p0)
            steps = 18
            for step in range(1, steps + 1):
                path.lineTo(self._bamboo_curve_point(base, top, bend, side, step / steps))
            segment_count = max(5, int(height / max(28.0, thickness * 2.2)))
            nodes = []
            branches = []
            leaves = []
            max_leaf_density = min(leaf_density, 5)
            for j in range(1, segment_count):
                t = j / segment_count
                c = self._bamboo_curve_point(base, top, bend, side, t)
                tangent = self._bamboo_curve_tangent_angle(base, top, bend, side, t)
                nodes.append((c, tangent))
                leaf_chance = 0.27 + 0.18 * depth
                if max_leaf_density > 0 and (j >= segment_count - 4 or (j % 3 == 1 and rng.random() < leaf_chance)):
                    branch_side = -1.0 if rng.random() < 0.5 else 1.0
                    branch_angle = tangent - 90.0 + branch_side * (25.0 + rng.random() * 31.0)
                    branch_len = thickness * (2.2 + rng.random() * 2.4)
                    end = QPointF(c.x() + math.cos(math.radians(branch_angle)) * branch_len, c.y() + math.sin(math.radians(branch_angle)) * branch_len)
                    branches.append((c, end))
                    leaves_for_branch = max(1, int(max_leaf_density * (0.72 + 0.38 * depth)))
                    for k in range(leaves_for_branch):
                        offset = (k - (leaves_for_branch - 1) / 2.0) * 10.0
                        leaf_len = thickness * (1.7 + rng.random() * 2.2)
                        leaf_w = max(2.0, thickness * (0.22 + rng.random() * 0.17))
                        ratio = 0.34 + 0.10 * k
                        origin = QPointF(c.x() + (end.x() - c.x()) * ratio, c.y() + (end.y() - c.y()) * ratio)
                        leaves.append((origin, branch_angle + offset, leaf_len, leaf_w))
            cache.append({"path": path, "thickness": thickness, "nodes": nodes, "branches": branches, "leaves": leaves, "depth": depth, "base": base})
        cache.sort(key=lambda item: item.get("depth", 0.0))
        self._bamboo_grove_cache_key = key
        self._bamboo_grove_cache = cache
        return cache

    def _draw_bamboo_depth_atmosphere(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, alpha_base: int):
        if not bool(getattr(settings, "bamboo_atmosphere_enabled", True)):
            return
        fog_alpha = max(0, min(255, int(alpha_base * 0.10)))
        if fog_alpha <= 0:
            return
        fog = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        c0 = QColor(120, 180, 120, 0)
        c1 = QColor(120, 190, 130, fog_alpha)
        c2 = QColor(80, 130, 80, max(0, min(255, int(fog_alpha * 0.55))))
        fog.setColorAt(0.0, c0)
        fog.setColorAt(0.55, c1)
        fog.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fog))
        p.drawRect(r)

    def _draw_bamboo_ground_shadows(self, p: QPainter, r: QRectF, cache, settings: EffectOverlaySettings, alpha_base: int):
        if not bool(getattr(settings, "bamboo_ground_shadow_enabled", True)):
            return
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for item in cache:
            base = item.get("base", QPointF(r.center().x(), r.bottom()))
            thickness = float(item.get("thickness", 8.0))
            depth = float(item.get("depth", 1.0))
            a = max(0, min(255, int(alpha_base * 0.10 * (0.55 + depth))))
            shadow = QColor(0, 35, 12, a)
            p.setBrush(QBrush(shadow))
            p.drawEllipse(QPointF(base.x(), r.bottom() - thickness * 0.15), thickness * (1.8 + depth * 1.1), thickness * (0.28 + depth * 0.12))
        p.restore()

    def _draw_bamboo_grove(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        count = max(0, int(getattr(settings, "bamboo_count", 12)))
        if count <= 0 or r.width() <= 0 or r.height() <= 0:
            return
        alpha_base = max(0, min(255, int(getattr(settings, "bamboo_alpha", 230) * max(0.0, float(getattr(settings, "intensity", 1.0))))))
        if alpha_base <= 0:
            return
        stalk_color_src = QColor(getattr(settings, "bamboo_stalk_color", "#3EA65A"))
        shadow_color_src = QColor(getattr(settings, "bamboo_shadow_color", "#1F6F3B"))
        node_color_src = QColor(getattr(settings, "bamboo_node_color", "#B7E37A"))
        leaf_color_src = QColor(getattr(settings, "bamboo_leaf_color", "#5ED06C"))
        highlight_alpha = max(0, min(255, int(getattr(settings, "bamboo_highlight_alpha", 96))))
        cache = self._get_bamboo_grove_cache(r, settings)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._draw_bamboo_ground_shadows(p, r, cache, settings, alpha_base)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for item in cache:
            depth = float(item.get("depth", 1.0))
            thickness = float(item["thickness"])
            rear_fade = 0.56 + 0.44 * depth
            stalk_color = QColor(stalk_color_src)
            stalk_color.setAlpha(max(0, min(255, int(alpha_base * rear_fade))))
            shadow_color = QColor(shadow_color_src)
            shadow_color.setAlpha(max(0, min(255, int(alpha_base * (0.58 + 0.22 * depth)))))
            node_color = QColor(node_color_src)
            node_color.setAlpha(max(0, min(255, int(alpha_base * (0.62 + 0.28 * depth)))))
            leaf_color = QColor(leaf_color_src)
            leaf_color.setAlpha(max(0, min(255, int(alpha_base * (0.55 + 0.35 * depth)))))
            pen_shadow = QPen(shadow_color, thickness * (1.10 + 0.05 * depth))
            pen_shadow.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_shadow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen_shadow)
            p.drawPath(item["path"])
            pen_main = QPen(stalk_color, thickness)
            pen_main.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_main.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen_main)
            p.drawPath(item["path"])
            hi_alpha = max(0, min(255, int(highlight_alpha * (0.30 + 0.70 * depth) * alpha_base / 255)))
            if hi_alpha > 0:
                highlight = QColor(220, 255, 170, hi_alpha)
                pen_hi = QPen(highlight, max(1.0, thickness * 0.12))
                pen_hi.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen_hi)
                p.drawPath(item["path"])
            p.setPen(QPen(node_color, max(1.0, thickness * 0.11)))
            for c, tangent in item["nodes"]:
                p.save()
                p.translate(c)
                p.rotate(tangent + 90.0)
                p.drawLine(QPointF(-thickness * 0.46, 0), QPointF(thickness * 0.46, 0))
                p.restore()
            branch_pen = QPen(shadow_color, max(1.0, thickness * 0.14))
            branch_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(branch_pen)
            for a, b in item["branches"]:
                p.drawLine(a, b)
            for origin, angle, length, width in item["leaves"]:
                self._draw_bamboo_leaf(p, origin, angle, length, width, leaf_color, depth)
        self._draw_bamboo_depth_atmosphere(p, r, settings, alpha_base)
        p.restore()

    def _draw_star_sky_particle(self, p: QPainter, item, alpha: int, settings: EffectOverlaySettings, now: float):
        speed = max(0.0, float(getattr(settings, "star_sky_speed", 0.35)))
        twinkle = 0.62 + 0.38 * math.sin(now * (1.2 + speed * 4.0) + float(getattr(item, "seed", 0.0)))
        star_alpha = max(0, min(255, int(alpha * twinkle)))
        if star_alpha <= 0:
            return
        base = QColor(getattr(settings, "star_sky_color", "#F8FBFF"))
        sub = QColor(getattr(settings, "star_sky_secondary_color", "#BFD8FF"))
        mix = 0.5 + 0.5 * math.sin(float(getattr(item, "seed", 0.0)))
        color = QColor(
            int(base.red() * mix + sub.red() * (1.0 - mix)),
            int(base.green() * mix + sub.green() * (1.0 - mix)),
            int(base.blue() * mix + sub.blue() * (1.0 - mix)),
            star_alpha,
        )
        radius = max(0.35, float(getattr(item, "size", 1.0)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color))
        if radius < 1.05:
            p.drawPoint(QPointF(item.x, item.y))
        else:
            p.drawEllipse(QPointF(item.x, item.y), radius, radius)

    def _milky_way_cache_key(self, r: QRectF, settings: EffectOverlaySettings):
        return (
            int(r.width()), int(r.height()),
            max(0, int(getattr(settings, "milky_way_star_count", 220))),
            round(float(getattr(settings, "milky_way_width", 0.22)), 3),
            round(float(getattr(settings, "milky_way_angle", -18.0)), 2),
            round(float(getattr(settings, "star_sky_size", 1.6)), 2),
        )

    def _get_milky_way_cache(self, r: QRectF, settings: EffectOverlaySettings):
        key_func = getattr(type(self), "_milky_way_cache_key", None)
        if key_func is None:
            key = (int(r.width()), int(r.height()), max(0, int(getattr(settings, "milky_way_star_count", 220))))
        else:
            key = key_func(self, r, settings)
        if getattr(self, "_milky_way_cache_signature", None) == key and hasattr(self, "_milky_way_cache"):
            return self._milky_way_cache
        width_ratio = max(0.02, min(1.0, float(getattr(settings, "milky_way_width", 0.22))))
        band_half = max(8.0, min(r.width(), r.height()) * width_ratio)
        length = math.hypot(max(1.0, r.width()), max(1.0, r.height())) * 1.22
        rng = random.Random(64157)
        blobs = []
        for i in range(14):
            t = -0.5 + i / 13.0
            x = t * length
            y = math.sin(t * math.tau * 1.15) * band_half * 0.18
            blobs.append((x, y, length * (0.10 + 0.05 * rng.random()), band_half * (0.85 + 0.65 * rng.random()), 0.16 + 0.14 * rng.random()))
        stars = []
        star_count = max(0, int(getattr(settings, "milky_way_star_count", 220)))
        for i in range(star_count):
            x = (rng.random() - 0.5) * length
            gaussian = sum(rng.random() - 0.5 for _ in range(6)) / 3.0
            y = gaussian * band_half * 1.22 + math.sin((x / max(1.0, length)) * math.tau * 2.0) * band_half * 0.12
            size = max(0.35, float(getattr(settings, "star_sky_size", 1.6)) * (0.25 + rng.random() * 0.75))
            stars.append((x, y, size, i * 1.731, 0.35 + rng.random() * 0.65))
        self._milky_way_cache_signature = key
        self._milky_way_cache = {"blobs": blobs, "stars": stars}
        return self._milky_way_cache

    def _draw_milky_way(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        alpha_base = max(0, min(255, int(getattr(settings, "milky_way_alpha", 120))))
        if alpha_base <= 0 or r.width() <= 0 or r.height() <= 0:
            return
        color = QColor(getattr(settings, "milky_way_color", "#BFD7FF"))
        angle = float(getattr(settings, "milky_way_angle", -18.0))
        cache = self._get_milky_way_cache(r, settings)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.translate(r.center())
        p.rotate(angle)
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, bw, bh, a_mul in cache.get("blobs", []):
            c = QColor(color)
            c.setAlpha(max(0, min(255, int(alpha_base * a_mul))))
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(x, y), bw, bh)
        base_star = QColor(getattr(settings, "star_sky_color", "#F8FBFF"))
        speed = float(getattr(settings, "star_sky_speed", 0.35))
        for x, y, size, phase, a_mul in cache.get("stars", []):
            twinkle = 0.72 + 0.28 * math.sin(now * (1.0 + speed * 2.0) + phase)
            c = QColor(base_star)
            c.setAlpha(max(0, min(255, int(alpha_base * a_mul * twinkle))))
            p.setBrush(QBrush(c))
            if size < 0.9:
                p.drawPoint(QPointF(x, y))
            else:
                p.drawEllipse(QPointF(x, y), size, size)
        p.restore()

    def _draw_shooting_star(self, p: QPainter, item, alpha: int):
        vx = float(getattr(item, "vx", 1.0))
        vy = float(getattr(item, "vy", 0.48))
        speed_len = max(1.0, math.hypot(vx, vy))
        dir_x = vx / speed_len
        dir_y = vy / speed_len
        tail_x = -dir_x
        tail_y = -dir_y
        base_size = max(1.0, float(getattr(item, "size", 12.0)))
        tail_length = base_size * (9.0 if getattr(item, "kind", "") == "shooting_star" else 6.5)
        flow = 0.72 + 0.28 * math.sin(time.time() * 9.0 + getattr(item, "seed", 0.0))
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        segments = 9
        for i in range(segments, 0, -1):
            t0 = i / segments
            t1 = (i - 1) / segments
            x0 = item.x + tail_x * tail_length * t0
            y0 = item.y + tail_y * tail_length * t0
            x1 = item.x + tail_x * tail_length * t1
            y1 = item.y + tail_y * tail_length * t1
            fade = pow(1.0 - t0, 1.45) * flow
            seg_alpha = max(0, min(255, int(alpha * fade * 0.95)))
            if seg_alpha <= 0:
                continue
            width = max(1.0, base_size * (0.045 + 0.20 * (1.0 - t0)))
            c = QColor(210, 240, 255, seg_alpha)
            pen = QPen(c, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        core_alpha = max(0, min(255, int(alpha * 0.72)))
        core_pen = QPen(QColor(255, 255, 255, core_alpha), max(1.0, base_size * 0.075))
        core_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(core_pen)
        p.drawLine(
            QPointF(item.x + tail_x * tail_length * 0.92, item.y + tail_y * tail_length * 0.92),
            QPointF(item.x, item.y),
        )
        glow_radius = max(4.0, base_size * 1.35)
        grad = QRadialGradient(QPointF(item.x, item.y), glow_radius)
        grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
        grad.setColorAt(0.35, QColor(190, 235, 255, int(alpha * 0.72)))
        grad.setColorAt(1.0, QColor(120, 190, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(item.x, item.y), glow_radius, glow_radius)
        p.setBrush(QBrush(QColor(255, 255, 255, max(0, min(255, alpha)))))
        p.drawEllipse(QPointF(item.x, item.y), max(1.0, base_size * 0.26), max(1.0, base_size * 0.26))
        p.restore()

    def _draw_balloon(self, p: QPainter, item, alpha: int):
        p.save()
        p.translate(item.x, item.y)
        p.rotate(math.sin(time.time()+item.seed)*4.0)
        palette = [QColor(255, 100, 145, alpha), QColor(255, 210, 80, alpha), QColor(100, 210, 255, alpha), QColor(150, 255, 150, alpha)]
        c = palette[int(item.seed) % len(palette)]
        grad = QRadialGradient(QPointF(-item.size*0.25, -item.size*0.25), item.size*1.2)
        grad.setColorAt(0.0, QColor(255,255,255, int(alpha*0.9)))
        grad.setColorAt(0.36, c)
        grad.setColorAt(1.0, QColor(max(0,c.red()-80), max(0,c.green()-80), max(0,c.blue()-80), alpha))
        p.setPen(QPen(QColor(255,255,255,int(alpha*0.55)), max(1, int(item.size*0.035))))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(0, 0), item.size*0.72, item.size)
        p.setPen(QPen(QColor(230,230,230,int(alpha*0.7)), 1))
        p.drawLine(0, int(item.size), 0, int(item.size*1.9))
        p.restore()

    def _ensure_sakura_petals(self, r: QRectF, settings: EffectOverlaySettings):
        if not hasattr(self, "_sakura_petals"):
            self._sakura_petals = []

        target = max(0, int(getattr(settings, "sakura_petal_count", 80)))
        ambient_count = len([p for p in self._sakura_petals if not getattr(p, "from_tree", False)])

        while ambient_count < target:
            self._sakura_petals.append(self._new_sakura_petal(r, settings, from_top=True, from_tree=False))
            ambient_count += 1

    def _new_sakura_petal(self, r: QRectF, settings: EffectOverlaySettings, from_top: bool = True,
                          from_tree: bool = False, origin=None):
        base_size = max(2.0, float(getattr(settings, "sakura_petal_size", 9.0)))
        speed = max(0.02, float(getattr(settings, "sakura_petal_speed", 0.32)))

        if origin is not None:
            x = float(origin[0])
            y = float(origin[1])
        else:
            x = r.left() + self._random.random() * max(1.0, r.width())
            if from_top:
                y = r.top() - self._random.random() * max(80.0, r.height() * 0.35)
            else:
                y = r.top() + self._random.random() * max(1.0, r.height())

        return SakuraPetal(
            x=float(x),
            y=float(y),
            vx=(-18.0 + self._random.random() * 36.0) * speed,
            vy=(18.0 + self._random.random() * 38.0) * speed,
            size=base_size * (0.65 + self._random.random() * 0.85),
            rotation=self._random.random() * math.tau,
            rotation_speed=(-2.0 + self._random.random() * 4.0) * speed,
            sway_phase=self._random.random() * math.tau,
            alpha=0.55 + self._random.random() * 0.45,
            seed=self._random.random() * 10000.0,
            from_tree=from_tree,
        )

    def _update_sakura_petals(self, r: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        if not hasattr(self, "_sakura_petals"):
            self._sakura_petals = []

        surface_y = r.top() + r.height() * max(0.0, min(1.0, float(getattr(settings, "sakura_petal_surface_y", 0.84))))
        sway = float(getattr(settings, "sakura_petal_sway", 1.15))
        ambient_enabled = bool(getattr(settings, "sakura_petals_enabled", False))
        to_remove = []

        for petal in list(self._sakura_petals):
            prev_y = petal.y
            wind_x, wind_y = self._petal_wind_velocity(settings, now, petal.seed, rose=False)
            petal.x += (petal.vx + math.sin(now * 1.3 + petal.sway_phase) * 34.0 * sway + wind_x) * dt
            petal.y += (petal.vy + wind_y) * dt
            petal.rotation += petal.rotation_speed * dt

            hit_surface = prev_y < surface_y <= petal.y
            out_of_bounds = (
                    petal.y > r.bottom() + 80 or
                    petal.x < r.left() - 140 or
                    petal.x > r.right() + 140
            )

            if hit_surface:
                self._maybe_spawn_sakura_ripple(petal, surface_y, settings, now)
                if ambient_enabled and not getattr(petal, "from_tree", False):
                    fresh = self._new_sakura_petal(r, settings, from_top=True, from_tree=False)
                    petal.__dict__.update(fresh.__dict__)
                else:
                    to_remove.append(petal)
                continue

            if out_of_bounds:
                if ambient_enabled and not getattr(petal, "from_tree", False):
                    fresh = self._new_sakura_petal(r, settings, from_top=True, from_tree=False)
                    petal.__dict__.update(fresh.__dict__)
                else:
                    to_remove.append(petal)

        if to_remove:
            remove_ids = {id(p) for p in to_remove}
            self._sakura_petals = [p for p in self._sakura_petals if id(p) not in remove_ids]

    def _maybe_spawn_sakura_ripple(self, petal, surface_y: float, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "sakura_petal_ripple_enabled", True)):
            return

        cooldown = max(0.0, float(getattr(settings, "sakura_petal_ripple_cooldown", 0.025)))
        if now - getattr(self, "_last_sakura_ripple_time", 0.0) < cooldown:
            return

        chance = max(0.0, min(1.0, float(getattr(settings, "sakura_petal_ripple_chance", 0.65))))
        if self._random.random() > chance:
            return

        min_radius = max(1.0, float(getattr(settings, "sakura_petal_ripple_min_radius", 22.0)))
        max_radius = max(min_radius, float(getattr(settings, "sakura_petal_ripple_max_radius", 88.0)))
        size_factor = max(0.2,
                          min(1.4, float(petal.size) / max(1.0, float(getattr(settings, "sakura_petal_size", 9.0)))))
        radius = min_radius + (max_radius - min_radius) * min(1.0, size_factor)

        self._ripples.append(
            EffectRipple(
                x=float(petal.x),
                y=float(surface_y),
                created_at=now,
                max_radius=radius,
                color=getattr(settings, "ripple_color", "#A8EFFF"),
                speed=max(0.05, float(getattr(settings, "ripple_speed", 1.0))) * 0.82,
            )
        )
        self._last_sakura_ripple_time = now

    def _draw_sakura_petals(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        base = QColor(getattr(settings, "sakura_petal_color", "#FFD1E8"))
        edge = QColor(getattr(settings, "sakura_petal_edge_color", "#FF8FC7"))
        alpha_base = max(0, min(255, int(getattr(settings, "sakura_petal_alpha", 210))))
        intensity = max(0.0, float(getattr(settings, "intensity", 1.0)))

        for petal in list(getattr(self, "_sakura_petals", [])):
            flutter = 0.72 + 0.28 * math.sin(now * 2.4 + petal.seed)
            alpha = int(alpha_base * petal.alpha * flutter * intensity)
            if alpha <= 0:
                continue

            c = QColor(base)
            c.setAlpha(max(0, min(255, alpha)))
            ec = QColor(edge)
            ec.setAlpha(max(0, min(255, int(alpha * 0.72))))
            self._draw_single_sakura_petal(p, petal.x, petal.y, petal.size, petal.rotation, c, ec, settings)

    def _draw_single_sakura_petal(self, p: QPainter, x: float, y: float, size: float, rotation: float, color: QColor,
                                  edge_color: QColor, settings: Optional[EffectOverlaySettings] = None):
        if settings is None:
            settings = get_effect_overlay_settings(self.cfg)
        color = self._apply_petal_night_tint(color, settings, edge=False)
        edge_color = self._apply_petal_night_tint(edge_color, settings, edge=True)
        outline_strength = max(0.5, min(4.0, float(getattr(settings, "petal_outline_strength", 1.35))))
        outline_enabled = bool(getattr(settings, "petal_outline_enabled", True))
        if outline_enabled:
            edge_color.setAlpha(max(edge_color.alpha(), min(255, int(color.alpha() * 0.92))))
        if False and bool(getattr(settings, "petal_shadow_enabled", False)):
            shadow_alpha = max(0, min(255, int(color.alpha() * (0.18 + 0.20 * max(0.0, min(1.0, float(getattr(settings, "petal_night_tint_strength", 0.35))))))))
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(8, 10, 24, shadow_alpha)))
            p.drawEllipse(QPointF(x + size * 0.16, y + size * 0.25), max(1.0, size * 0.52), max(1.0, size * 0.20))
            p.restore()
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(rotation))

        w = size * 0.72
        h = size * 1.05

        path = QPainterPath()
        path.moveTo(0.0, -h * 0.55)
        path.cubicTo(w * 0.62, -h * 0.38, w * 0.56, h * 0.18, 0.0, h * 0.55)
        path.cubicTo(-w * 0.56, h * 0.18, -w * 0.62, -h * 0.38, 0.0, -h * 0.55)
        path.closeSubpath()

        grad = QRadialGradient(QPointF(-w * 0.12, -h * 0.18), max(w, h))
        c0 = QColor(255, 255, 255, max(0, min(255, int(color.alpha() * 0.65))))
        c1 = QColor(color)
        c2 = QColor(edge_color)
        c2.setAlpha(max(0, min(255, int(color.alpha() * 0.8))))
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.42, c1)
        grad.setColorAt(1.0, c2)

        p.setBrush(QBrush(grad))
        p.setPen(QPen(edge_color, max(1.0, size * 0.055 * (outline_strength if outline_enabled else 1.0))))
        p.drawPath(path)

        notch_pen = QPen(edge_color, max(1, int(size * 0.035)))
        notch_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(notch_pen)
        p.drawLine(0, int(-h * 0.52), int(w * 0.12), int(-h * 0.28))
        p.drawLine(0, int(-h * 0.52), int(-w * 0.12), int(-h * 0.28))

        p.restore()

    def _draw_sakura_rosette_blossom(self, p: QPainter, x: float, y: float, size: float, rotation: float, color: QColor, edge_color: QColor, settings: EffectOverlaySettings):
        layers = max(1, int(getattr(settings, "sakura_tree_blossom_rosette_layers", 3)))
        center_color = QColor(getattr(settings, "sakura_tree_blossom_center_color", "#FFF2A8"))
        shadow_color = QColor(getattr(settings, "sakura_tree_blossom_shadow_color", "#D96A9A"))
        highlight_alpha = max(0, min(255, int(getattr(settings, "sakura_tree_blossom_highlight_alpha", 105))))

        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(rotation))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for layer in range(layers):
            count = 7 - min(layer, 3)
            radius = size * (0.34 - layer * 0.075)
            petal_size = size * (0.52 - layer * 0.08)
            angle_offset = layer * 0.47
            shade = 0.86 + layer * 0.055

            for i in range(max(3, count)):
                angle = math.tau * i / max(3, count) + angle_offset
                px = math.cos(angle) * radius
                py = math.sin(angle) * radius * 0.72
                petal_rot = angle + math.pi / 2.0

                c = QColor(
                    max(0, min(255, int(color.red() * shade))),
                    max(0, min(255, int(color.green() * shade))),
                    max(0, min(255, int(color.blue() * shade))),
                    color.alpha(),
                )
                ec = QColor(edge_color)
                ec.setAlpha(max(0, min(255, int(edge_color.alpha() * (0.70 + layer * 0.08)))))
                self._draw_single_sakura_rosette_petal(p, px, py, petal_size, petal_rot, c, ec, shadow_color,
                                                       highlight_alpha)

        center = QColor(center_color)
        center.setAlpha(max(0, min(255, int(color.alpha() * 0.86))))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(center))
        p.drawEllipse(QPointF(0, 0), max(1.0, size * 0.09), max(1.0, size * 0.075))

        p.restore()

    def _draw_single_sakura_rosette_petal(self, p: QPainter, x: float, y: float, size: float, rotation: float, color: QColor, edge_color: QColor, shadow_color: QColor, highlight_alpha: int):
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(rotation))

        w = size * 0.62
        h = size * 0.92

        path = QPainterPath()
        path.moveTo(0.0, -h * 0.50)
        path.cubicTo(w * 0.56, -h * 0.38, w * 0.62, h * 0.14, 0.0, h * 0.52)
        path.cubicTo(-w * 0.62, h * 0.14, -w * 0.56, -h * 0.38, 0.0, -h * 0.50)
        path.closeSubpath()

        grad = QRadialGradient(QPointF(-w * 0.15, -h * 0.20), max(1.0, size * 0.90))
        c0 = QColor(255, 255, 255, max(0, min(255, int(highlight_alpha * color.alpha() / 255))))
        c1 = QColor(color)
        c2 = QColor(shadow_color)
        c2.setAlpha(max(0, min(255, int(color.alpha() * 0.55))))
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.40, c1)
        grad.setColorAt(1.0, c2)

        p.setBrush(QBrush(grad))
        p.setPen(QPen(edge_color, max(1, int(size * 0.045))))
        p.drawPath(path)

        vein = QColor(edge_color)
        vein.setAlpha(max(0, min(255, int(edge_color.alpha() * 0.38))))
        pen = QPen(vein, max(1, int(size * 0.025)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(0, int(-h * 0.28), 0, int(h * 0.25))

        p.restore()

    def _ensure_rose_petals(self, r: QRectF, settings: EffectOverlaySettings):
        if not hasattr(self, "_rose_petals"):
            self._rose_petals = []

        target = max(0, int(getattr(settings, "rose_petal_count", 24)))

        while len(self._rose_petals) < target:
            self._rose_petals.append(self._new_rose_petal(r, settings, from_top=True))

        if len(self._rose_petals) > target:
            self._rose_petals = self._rose_petals[:target]

    def _ensure_rose_flowers(self, r: QRectF, settings: EffectOverlaySettings):
        if not hasattr(self, "_rose_flowers"):
            self._rose_flowers = []

        target = max(0, int(getattr(settings, "rose_flower_count", 5)))
        while len(self._rose_flowers) < target:
            self._rose_flowers.append(self._new_rose_flower(r, settings, from_top=True))
        if len(self._rose_flowers) > target:
            self._rose_flowers = self._rose_flowers[:target]

    def _new_rose_flower(self, r: QRectF, settings: EffectOverlaySettings, from_top: bool = False):
        size = max(8.0, float(getattr(settings, "rose_flower_size", 42.0)))
        speed = max(0.02, float(getattr(settings, "rose_flower_speed", 0.22)))
        x = r.left() + self._random.random() * max(1.0, r.width())
        if from_top:
            y = r.top() - self._random.random() * max(120.0, r.height() * 0.45)
        else:
            y = r.top() + self._random.random() * max(1.0, r.height())

        return FallingRoseFlower(
            x=float(x),
            y=float(y),
            vx=(-10.0 + self._random.random() * 20.0) * speed,
            vy=(16.0 + self._random.random() * 22.0) * speed,
            size=size * (0.82 + self._random.random() * 0.36),
            rotation=self._random.random() * math.tau,
            rotation_speed=(-0.65 + self._random.random() * 1.3) * speed,
            sway_phase=self._random.random() * math.tau,
            alpha=0.7 + self._random.random() * 0.3,
            seed=self._random.random() * 10000.0,
        )

    def _update_rose_flowers(self, r: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        surface_y = r.top() + r.height() * max(0.0, min(1.0, float(getattr(settings, "rose_flower_surface_y", 0.84))))
        sway = float(getattr(settings, "rose_flower_sway", 0.85))

        for flower in self._rose_flowers:
            prev_y = flower.y
            side_sway = math.sin(now * 0.9 + flower.sway_phase) * 28.0 * sway
            flower.x += (flower.vx + side_sway) * dt
            flower.y += flower.vy * dt
            flower.rotation += flower.rotation_speed * dt

            hit_surface = prev_y < surface_y <= flower.y
            out_of_bounds = (
                    flower.y > r.bottom() + 120 or
                    flower.x < r.left() - 160 or
                    flower.x > r.right() + 160
            )

            if hit_surface:
                self._maybe_spawn_rose_flower_ripple(flower, surface_y, settings, now)
                fresh = self._new_rose_flower(r, settings, from_top=True)
                flower.__dict__.update(fresh.__dict__)
                continue

            if out_of_bounds:
                fresh = self._new_rose_flower(r, settings, from_top=True)
                flower.__dict__.update(fresh.__dict__)

    def _maybe_spawn_rose_flower_ripple(self, flower, surface_y: float, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "rose_flower_ripple_enabled", True)):
            return
        if not bool(getattr(settings, "ripple_enabled", True)):
            return

        cooldown = max(0.0, float(getattr(settings, "rose_flower_ripple_cooldown", 0.12)))
        if now - getattr(self, "_last_flower_ripple_time", 0.0) < cooldown:
            return

        chance = max(0.0, min(1.0, float(getattr(settings, "rose_flower_ripple_chance", 1.0))))
        if self._random.random() > chance:
            return

        min_radius = max(1.0, float(getattr(settings, "rose_flower_ripple_min_radius", 80.0)))
        max_radius = max(min_radius, float(getattr(settings, "rose_flower_ripple_max_radius", 220.0)))
        size_factor = max(0.35,
                          min(1.8, float(flower.size) / max(1.0, float(getattr(settings, "rose_flower_size", 42.0)))))
        radius = min_radius + (max_radius - min_radius) * min(1.0, size_factor)

        self._ripples.append(
            EffectRipple(
                x=float(flower.x),
                y=float(surface_y),
                created_at=now,
                max_radius=radius,
                color=getattr(settings, "ripple_color", "#A8EFFF"),
                speed=max(0.05, float(getattr(settings, "ripple_speed", 1.0))) * 0.75,
            )
        )
        self._last_flower_ripple_time = now

    def _draw_rose_flowers(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        base = QColor(getattr(settings, "blooming_rose_color", "#FF6FAE"))
        edge = QColor(getattr(settings, "blooming_rose_edge_color", "#FFD5E8"))
        alpha_base = max(0, min(255, int(getattr(settings, "rose_flower_alpha", 220))))
        intensity = max(0.0, float(getattr(settings, "intensity", 1.0)))

        for flower in list(getattr(self, "_rose_flowers", [])):
            pulse = 0.92 + 0.08 * math.sin(now * 1.4 + flower.seed)
            alpha = int(alpha_base * flower.alpha * pulse * intensity)
            if alpha <= 0:
                continue
            c = QColor(base)
            c.setAlpha(max(0, min(255, alpha)))
            ec = QColor(edge)
            ec.setAlpha(max(0, min(255, int(alpha * 0.85))))
            self._draw_single_rose_flower(p, flower.x, flower.y, flower.size, flower.rotation, c, ec, open_amount=0.68)

    def _draw_single_rose_flower(self, p: QPainter, x: float, y: float, size: float, rotation: float, color: QColor,
                                 edge_color: QColor, open_amount: float = 0.8):
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(rotation))

        
        layers = [
            (8, size * 0.32, size * 0.54, 0.0),
            (7, size * 0.22, size * 0.42, 0.45),
            (5, size * 0.11, size * 0.30, 0.2),
        ]

        for count, radius, petal_size, angle_offset in layers:
            for i in range(count):
                angle = math.tau * i / max(1, count) + angle_offset
                px = math.cos(angle) * radius * open_amount
                py = math.sin(angle) * radius * open_amount * 0.72
                petal_rot = angle + math.pi / 2.0
                shade = 0.86 + 0.14 * math.sin(i + count)
                c = QColor(
                    max(0, min(255, int(color.red() * shade))),
                    max(0, min(255, int(color.green() * shade))),
                    max(0, min(255, int(color.blue() * shade))),
                    color.alpha(),
                )
                self._draw_single_rose_petal(p, px, py, petal_size, petal_rot, c, edge_color)

        center = QColor(color)
        center.setAlpha(max(0, min(255, int(color.alpha() * 0.95))))
        p.setPen(QPen(edge_color, max(1, int(size * 0.025))))
        p.setBrush(QBrush(center))
        p.drawEllipse(QPointF(0, 0), size * 0.10, size * 0.10)
        p.restore()

    def _ensure_blooming_roses(self, r: QRectF, settings: EffectOverlaySettings, now: float):
        if not hasattr(self, "_blooming_roses"):
            self._blooming_roses = []

        target = max(0, int(getattr(settings, "blooming_rose_count", 2)))
        while len(self._blooming_roses) < target:
            self._blooming_roses.append(self._new_blooming_rose(r, settings, now))
        if len(self._blooming_roses) > target:
            self._blooming_roses = self._blooming_roses[:target]

    def _new_blooming_rose(self, r: QRectF, settings: EffectOverlaySettings, now: float):
        size = max(12.0, float(getattr(settings, "blooming_rose_size", 86.0)))
        margin = size * 0.8
        return BloomingRose(
            x=float(r.left() + margin + self._random.random() * max(1.0, r.width() - margin * 2.0)),
            y=float(r.top() + margin + self._random.random() * max(1.0, r.height() * 0.45)),
            size=size * (0.82 + self._random.random() * 0.28),
            created_at=now,
            scatter_after=max(0.1, float(getattr(settings, "blooming_rose_scatter_after", 3.0))),
            life=max(0.2, float(getattr(settings, "blooming_rose_life", 7.5))),
            petal_count=max(0, int(getattr(settings, "blooming_rose_petal_count", 34))),
            seed=self._random.random() * 10000.0,
            scattered=False,
        )

    def _update_blooming_roses(self, r: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        respawn = bool(getattr(settings, "blooming_rose_respawn", True))

        for rose in list(getattr(self, "_blooming_roses", [])):
            age = now - rose.created_at
            if not rose.scattered and age >= rose.scatter_after:
                self._scatter_blooming_rose(rose, settings, now)
                rose.scattered = True

            if age >= rose.life:
                if respawn:
                    fresh = self._new_blooming_rose(r, settings, now)
                    rose.__dict__.update(fresh.__dict__)
                else:
                    try:
                        self._blooming_roses.remove(rose)
                    except ValueError:
                        pass

    def _scatter_blooming_rose(self, rose: BloomingRose, settings: EffectOverlaySettings, now: float):
        if not hasattr(self, "_rose_petals"):
            self._rose_petals = []

        base_petal_size = max(4.0, rose.size * 0.18)
        for i in range(max(0, int(rose.petal_count))):
            angle = math.tau * i / max(1, rose.petal_count) + self._random.random() * 0.45
            burst = 18.0 + self._random.random() * 54.0
            downward = 18.0 + self._random.random() * 32.0
            px = rose.x + math.cos(angle) * rose.size * 0.18
            py = rose.y + math.sin(angle) * rose.size * 0.12
            self._rose_petals.append(
                RosePetal(
                    x=float(px),
                    y=float(py),
                    vx=math.cos(angle) * burst,
                    vy=downward + max(0.0, math.sin(angle)) * burst * 0.25,
                    size=base_petal_size * (0.72 + self._random.random() * 0.75),
                    rotation=self._random.random() * math.tau,
                    rotation_speed=(-1.8 + self._random.random() * 3.6) * max(0.1, float(
                        getattr(settings, "rose_petal_speed", 0.35))),
                    sway_phase=self._random.random() * math.tau,
                    alpha=0.68 + self._random.random() * 0.32,
                    seed=self._random.random() * 10000.0,
                    resting=False,
                    rest_created_at=0.0,
                )
            )

    def _draw_blooming_roses(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        base = QColor(getattr(settings, "blooming_rose_color", "#FF6FAE"))
        edge = QColor(getattr(settings, "blooming_rose_edge_color", "#FFD5E8"))
        alpha_base = max(0, min(255, int(getattr(settings, "blooming_rose_alpha", 230))))
        intensity = max(0.0, float(getattr(settings, "intensity", 1.0)))

        for rose in list(getattr(self, "_blooming_roses", [])):
            if rose.scattered:
                continue
            age = now - rose.created_at
            open_t = max(0.0, min(1.0, age / max(0.1, rose.scatter_after)))
            open_amount = 0.35 + 0.65 * (1.0 - pow(1.0 - open_t, 3.0))
            alpha = int(alpha_base * intensity)
            if alpha <= 0:
                continue
            c = QColor(base)
            c.setAlpha(alpha)
            ec = QColor(edge)
            ec.setAlpha(max(0, min(255, int(alpha * 0.85))))
            rotation = math.sin(now * 0.25 + rose.seed) * 0.08
            self._draw_single_rose_flower(p, rose.x, rose.y, rose.size, rotation, c, ec, open_amount=open_amount)

    def _new_rose_petal(self, r: QRectF, settings: EffectOverlaySettings, from_top: bool = False):
        base_size = max(2.0, float(getattr(settings, "rose_petal_size", 16.0)))
        speed_scale = max(0.05, float(getattr(settings, "rose_petal_speed", 0.35)))

        x = r.left() + self._random.random() * max(1.0, r.width())
        if from_top:
            y = r.top() - self._random.random() * max(80.0, r.height() * 0.35)
        else:
            y = r.top() + self._random.random() * max(1.0, r.height())

        return RosePetal(
            x=float(x),
            y=float(y),
            vx=(-12.0 + self._random.random() * 24.0) * speed_scale,
            vy=(18.0 + self._random.random() * 34.0) * speed_scale,
            size=base_size * (0.7 + self._random.random() * 0.8),
            rotation=self._random.random() * math.tau,
            rotation_speed=(-1.2 + self._random.random() * 2.4) * speed_scale,
            sway_phase=self._random.random() * math.tau,
            alpha=0.55 + self._random.random() * 0.45,
            seed=self._random.random() * 10000.0,
            resting=False,
            rest_created_at=0.0,
        )

    def _update_rose_petals(self, r: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        if not hasattr(self, "_rose_petals"):
            self._rose_petals = []

        surface_y = r.top() + r.height() * max(
            0.0,
            min(1.0, float(getattr(settings, "rose_petal_surface_y", 0.84)))
        )
        sway = float(getattr(settings, "rose_petal_sway", 1.0))
        rest_on_surface = bool(getattr(settings, "rose_petal_rest_on_surface", False))
        ambient_petals_enabled = bool(getattr(settings, "rose_petals_enabled", False))

        fade_on_surface = bool(getattr(settings, "rose_petal_fade_on_surface", True))
        fade_duration_default = max(0.05, float(getattr(settings, "rose_petal_fade_duration", 0.85)))
        fade_sink_distance_default = float(getattr(settings, "rose_petal_fade_sink_distance", 10.0))
        fade_spin = float(getattr(settings, "rose_petal_fade_spin", 0.35))

        to_remove = []

        for petal in list(self._rose_petals):
            if not hasattr(petal, "fading"):
                petal.fading = False
            if not hasattr(petal, "fade_started_at"):
                petal.fade_started_at = 0.0
            if not hasattr(petal, "fade_duration"):
                petal.fade_duration = fade_duration_default
            if not hasattr(petal, "fade_start_y"):
                petal.fade_start_y = petal.y
            if not hasattr(petal, "fade_sink_distance"):
                petal.fade_sink_distance = fade_sink_distance_default

            if petal.fading:
                t = (now - petal.fade_started_at) / max(0.05, float(petal.fade_duration))
                if t >= 1.0:
                    if ambient_petals_enabled:
                        fresh = self._new_rose_petal(r, settings, from_top=True)
                        petal.__dict__.update(fresh.__dict__)
                    else:
                        to_remove.append(petal)
                    continue

                eased = 1.0 - pow(1.0 - max(0.0, min(1.0, t)), 3.0)
                petal.y = petal.fade_start_y + petal.fade_sink_distance * eased
                petal.rotation += petal.rotation_speed * fade_spin * dt
                continue

            if petal.resting:
                petal.x += math.sin(now * 0.8 + petal.seed) * 2.0 * dt
                petal.rotation += petal.rotation_speed * 0.15 * dt

                if now - petal.rest_created_at > 4.0:
                    if fade_on_surface:
                        petal.fading = True
                        petal.fade_started_at = now
                        petal.fade_duration = fade_duration_default
                        petal.fade_start_y = petal.y
                        petal.fade_sink_distance = fade_sink_distance_default
                    elif ambient_petals_enabled:
                        fresh = self._new_rose_petal(r, settings, from_top=True)
                        petal.__dict__.update(fresh.__dict__)
                    else:
                        to_remove.append(petal)
                continue

            prev_y = petal.y
            side_sway = math.sin(now * 1.2 + petal.sway_phase) * 24.0 * sway
            wind_x, wind_y = self._petal_wind_velocity(settings, now, petal.seed, rose=True)
            side_sway += wind_x
            petal.x += (petal.vx + side_sway) * dt
            petal.y += (petal.vy + wind_y) * dt
            petal.rotation += petal.rotation_speed * dt

            hit_surface = prev_y < surface_y <= petal.y
            out_of_bounds = (
                    petal.y > r.bottom() + 80 or
                    petal.x < r.left() - 120 or
                    petal.x > r.right() + 120
            )

            if hit_surface:
                self._maybe_spawn_petal_ripple(petal, surface_y, settings, now)
                petal.y = surface_y

                if rest_on_surface:
                    petal.vy = 0.0
                    petal.vx *= 0.2
                    petal.resting = True
                    petal.rest_created_at = now
                elif fade_on_surface:
                    petal.fading = True
                    petal.fade_started_at = now
                    petal.fade_duration = fade_duration_default
                    petal.fade_start_y = surface_y
                    petal.fade_sink_distance = fade_sink_distance_default
                    petal.vx *= 0.12
                    petal.vy = 0.0
                else:
                    if ambient_petals_enabled:
                        fresh = self._new_rose_petal(r, settings, from_top=True)
                        petal.__dict__.update(fresh.__dict__)
                    else:
                        to_remove.append(petal)
                continue

            if out_of_bounds:
                if ambient_petals_enabled:
                    fresh = self._new_rose_petal(r, settings, from_top=True)
                    petal.__dict__.update(fresh.__dict__)
                else:
                    to_remove.append(petal)

        if to_remove:
            remove_ids = {id(p) for p in to_remove}
            self._rose_petals = [p for p in self._rose_petals if id(p) not in remove_ids]

    def _maybe_spawn_petal_ripple(self, petal, surface_y: float, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "rose_petal_ripple_enabled", True)):
            return

        if not bool(getattr(settings, "ripple_enabled", True)):
            return

        cooldown = max(0.0, float(getattr(settings, "rose_petal_ripple_cooldown", 0.04)))
        if now - getattr(self, "_last_petal_ripple_time", 0.0) < cooldown:
            return

        chance = max(0.0, min(1.0, float(getattr(settings, "rose_petal_ripple_chance", 0.9))))
        if self._random.random() > chance:
            return

        min_radius = max(1.0, float(getattr(settings, "rose_petal_ripple_min_radius", 36.0)))
        max_radius = max(min_radius, float(getattr(settings, "rose_petal_ripple_max_radius", 130.0)))
        size_factor = max(0.2,
                          min(1.5, float(petal.size) / max(1.0, float(getattr(settings, "rose_petal_size", 16.0)))))
        radius = min_radius + (max_radius - min_radius) * min(1.0, size_factor)

        self._ripples.append(
            EffectRipple(
                x=float(petal.x),
                y=float(surface_y),
                created_at=now,
                max_radius=radius,
                color=getattr(settings, "ripple_color", "#A8EFFF"),
                speed=max(0.05, float(getattr(settings, "ripple_speed", 1.0))) * 0.85,
            )
        )
        self._last_petal_ripple_time = now

    def _draw_rose_petals(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        
        base = QColor(getattr(settings, "rose_petal_color", "#FF7AAE"))
        edge = QColor(getattr(settings, "rose_petal_edge_color", "#FFD1E3"))
        alpha_base = max(0, min(255, int(getattr(settings, "rose_petal_alpha", 210))))
        intensity = max(0.0, float(getattr(settings, "intensity", 1.0)))

        for petal in list(getattr(self, "_rose_petals", [])):
            flutter = 0.75 + 0.25 * math.sin(now * 2.0 + petal.seed)
            fade_multiplier = 1.0

            if getattr(petal, "fading", False):
                duration = max(0.05, float(getattr(petal, "fade_duration", 0.85)))
                t = max(0.0, min(1.0, (now - getattr(petal, "fade_started_at", now)) / duration))
                
                fade_multiplier = pow(1.0 - t, 1.7)

            alpha = int(alpha_base * petal.alpha * flutter * intensity * fade_multiplier)
            if alpha <= 0:
                continue

            c = QColor(base)
            c.setAlpha(max(0, min(255, alpha)))

            ec = QColor(edge)
            ec.setAlpha(max(0, min(255, int(alpha * 0.75))))

            self._draw_single_rose_petal(
                p,
                petal.x,
                petal.y,
                petal.size,
                petal.rotation,
                c,
                ec,
            )

    def _draw_single_rose_petal(self, p: QPainter, x: float, y: float, size: float, rotation: float, color: QColor, edge_color: QColor):
        settings = get_effect_overlay_settings(self.cfg)
        roundness = max(0.0, min(1.0, float(getattr(settings, "rose_petal_roundness", 0.72))))
        curl = max(0.0, min(1.0, float(getattr(settings, "rose_petal_curl", 0.42))))
        highlight_alpha = max(0, min(255, int(getattr(settings, "rose_petal_highlight_alpha", 115))))
        vein_alpha = max(0, min(255, int(getattr(settings, "rose_petal_vein_alpha", 95))))
        internal_shadow_alpha = max(0, min(255, int(getattr(settings, "rose_petal_shadow_alpha", 28))))
        color = self._apply_petal_night_tint(color, settings, edge=False)
        edge_color = self._apply_petal_night_tint(edge_color, settings, edge=True)
        if False and bool(getattr(settings, "petal_shadow_enabled", False)):
            external_shadow_alpha = max(0, min(255, int(color.alpha() * (0.22 + 0.18 * max(0.0, min(1.0, float(getattr(settings, "petal_night_tint_strength", 0.35))))))))
            shadow_color = QColor(8, 10, 24, external_shadow_alpha)
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(shadow_color))
            p.drawEllipse(QPointF(x + size * 0.18, y + size * 0.30), max(1.0, size * 0.62), max(1.0, size * 0.24))
            p.restore()
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(rotation))

        w = size * (0.70 + roundness * 0.18)
        h = size * (1.18 + roundness * 0.12)

        path = QPainterPath()
        path.moveTo(0.0, -h * 0.58)
        path.cubicTo(
            w * (0.52 + roundness * 0.16),
            -h * 0.48,
            w * (0.72 + roundness * 0.12),
            h * 0.08,
            w * 0.18,
            h * 0.55,
        )
        path.cubicTo(
            w * 0.04,
            h * 0.68,
            -w * 0.04,
            h * 0.68,
            -w * 0.18,
            h * 0.55,
        )
        path.cubicTo(
            -w * (0.72 + roundness * 0.12),
            h * 0.08,
            -w * (0.52 + roundness * 0.16),
            -h * 0.48,
            0.0,
            -h * 0.58,
        )
        path.closeSubpath()

        body_grad = QRadialGradient(QPointF(-w * 0.12, -h * 0.20), max(w, h) * 0.95)
        c_center = QColor(color)
        c_center.setAlpha(color.alpha())
        c_mid = QColor(
            min(255, int(color.red() * 1.08)),
            min(255, int(color.green() * 1.04)),
            min(255, int(color.blue() * 1.06)),
            color.alpha(),
        )
        c_edge = QColor(
            max(0, int(color.red() * 0.68)),
            max(0, int(color.green() * 0.62)),
            max(0, int(color.blue() * 0.70)),
            max(0, min(255, int(color.alpha() * 0.92))),
        )
        body_grad.setColorAt(0.0, c_mid)
        body_grad.setColorAt(0.45, c_center)
        body_grad.setColorAt(1.0, c_edge)

        p.setBrush(QBrush(body_grad))
        p.setPen(QPen(edge_color, max(1, int(size * 0.055))))
        p.drawPath(path)

        p.save()
        p.setClipPath(path)

        if internal_shadow_alpha > 0:
            shade = QColor(70, 0, 35, max(0, min(255, int(internal_shadow_alpha * color.alpha() / 255))))
            shade_clear = QColor(shade)
            shade_clear.setAlpha(0)
            shade_grad = QLinearGradient(0, -h * 0.20, 0, h * 0.58)
            shade_grad.setColorAt(0.0, shade_clear)
            shade_grad.setColorAt(0.72, shade_clear)
            shade_grad.setColorAt(1.0, shade)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(shade_grad))
            p.drawPath(path)

        highlight = QColor(255, 255, 255, max(0, min(255, int(highlight_alpha * color.alpha() / 255))))
        highlight_grad = QRadialGradient(QPointF(-w * 0.16, -h * 0.23), max(1.0, size * 0.72))
        h0 = QColor(highlight)
        h1 = QColor(highlight)
        h1.setAlpha(int(h0.alpha() * 0.22))
        h2 = QColor(highlight)
        h2.setAlpha(0)
        highlight_grad.setColorAt(0.0, h0)
        highlight_grad.setColorAt(0.55, h1)
        highlight_grad.setColorAt(1.0, h2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(highlight_grad))
        p.drawEllipse(QRectF(-w * 0.48, -h * 0.55, w * 0.72, h * 0.76))

        p.restore()

        curl_color = QColor(edge_color)
        curl_color.setAlpha(max(0, min(255, int(edge_color.alpha() * (0.35 + curl * 0.65)))))
        curl_pen = QPen(curl_color, max(1, int(size * (0.035 + curl * 0.035))))
        curl_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(curl_pen)
        curl_path = QPainterPath()
        curl_path.moveTo(w * 0.08, -h * 0.47)
        curl_path.cubicTo(w * 0.52, -h * 0.30, w * 0.48, h * 0.18, w * 0.10, h * 0.48)
        p.drawPath(curl_path)

        vein = QColor(edge_color)
        vein.setAlpha(max(0, min(255, int(vein_alpha * edge_color.alpha() / 255))))
        vein_pen = QPen(vein, max(1, int(size * 0.04)))
        vein_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(vein_pen)
        vein_path = QPainterPath()
        vein_path.moveTo(0.0, -h * 0.42)
        vein_path.cubicTo(-w * 0.08, -h * 0.12, w * 0.07, h * 0.20, 0.0, h * 0.42)
        p.drawPath(vein_path)

        p.restore()

    def _update_petal_wind(self, settings: EffectOverlaySettings, now: float):
        if not bool(getattr(settings, "petal_blizzard_enabled", False)):
            self._petal_wind_strength = 0.0
            self._petal_gust_active = False
            return
        base_strength = max(0.0, float(getattr(settings, "petal_wind_strength", 1.0)))
        randomness = max(0.0, min(1.0, float(getattr(settings, "petal_wind_randomness", 0.55))))
        interval = max(0.8, float(getattr(settings, "petal_gust_interval", 4.0)))
        duration = max(0.2, float(getattr(settings, "petal_gust_duration", 1.15)))
        gust_strength = max(0.2, float(getattr(settings, "petal_gust_strength", 1.45)))
        if not hasattr(self, "_next_petal_wind_event") or getattr(self, "_next_petal_wind_event", 0.0) <= 0.0:
            self._next_petal_wind_event = now + interval
        if now >= getattr(self, "_next_petal_wind_event", 0.0):
            self._petal_wind_phase = self._random.random() * math.tau
            self._petal_gust_direction = 1.0 if self._random.random() >= 0.5 else -1.0
            self._petal_wind_strength = (240.0 + self._random.random() * 260.0) * base_strength * gust_strength * (0.80 + randomness * 0.55)
            self._petal_wind_until = now + duration * (0.88 + self._random.random() * 0.34)
            self._petal_gust_active = True
            self._petal_gust_started_at = now
            self._next_petal_wind_event = self._petal_wind_until + interval * (0.90 + self._random.random() * 0.20)
            self._rollup_all_petals_by_gust(settings, now)
        if now > getattr(self, "_petal_wind_until", 0.0):
            self._petal_gust_active = False
            self._petal_wind_strength *= 0.82
            if self._petal_wind_strength < 1.0:
                self._petal_wind_strength = 0.0
        else:
            elapsed = max(0.0, now - getattr(self, "_petal_gust_started_at", now))
            life = max(0.2, getattr(self, "_petal_wind_until", now) - getattr(self, "_petal_gust_started_at", now))
            t = max(0.0, min(1.0, elapsed / life))
            envelope = math.sin(t * math.pi)
            self._petal_wind_strength = max(0.0, self._petal_wind_strength * (0.92 + 0.08 * envelope))


    def _petal_wind_velocity(self, settings: EffectOverlaySettings, now: float, seed: float, rose: bool = True):
        self._update_petal_wind(settings, now)
        base = float(getattr(self, "_petal_wind_strength", 0.0))
        if base <= 0.0:
            return 0.0, 0.0
        phase = float(getattr(self, "_petal_wind_phase", 0.0))
        gusting = bool(getattr(self, "_petal_gust_active", False))
        direction = float(getattr(self, "_petal_gust_direction", 1.0))
        wave = math.sin(now * (1.65 if rose else 1.85) + phase + seed * 0.013)
        fine = math.sin(now * 4.7 + seed * 0.031) * 0.18
        
        x = direction * base * (0.92 + 0.18 * wave + fine)
        lift = 0.18 if gusting else 0.06
        y = -abs(base) * (lift + 0.05 * math.sin(now * 2.0 + seed))
        return x, y


    def _rollup_all_petals_by_gust(self, settings: EffectOverlaySettings, now: float):
        if now - getattr(self, "_last_petal_gust_rollup_at", 0.0) < 0.12:
            return
        self._last_petal_gust_rollup_at = now
        direction = float(getattr(self, "_petal_gust_direction", 1.0))
        base = max(80.0, float(getattr(self, "_petal_wind_strength", 240.0)))
        gust_strength = max(0.2, float(getattr(settings, "petal_gust_strength", 1.45)))
        randomness = max(0.0, min(1.0, float(getattr(settings, "petal_wind_randomness", 0.55))))
        for seq_name in ("_rose_petals", "_sakura_petals"):
            petals = getattr(self, seq_name, [])
            for petal in list(petals):
                seed = float(getattr(petal, "seed", self._random.random() * 10000.0))
                individual = 0.78 + randomness * 0.44 + 0.18 * math.sin(seed)
                petal.vx = direction * (base * 0.92 * individual + self._random.random() * 90.0 * gust_strength)
                petal.vy = -abs(base) * (0.30 + 0.16 * self._random.random()) * gust_strength
                petal.rotation_speed += direction * (2.5 + self._random.random() * 5.5) * gust_strength
                petal.rotation += direction * (0.15 + self._random.random() * 0.55)
                if hasattr(petal, "resting"):
                    petal.resting = False
                if hasattr(petal, "fading"):
                    petal.fading = False
                if hasattr(petal, "rest_created_at"):
                    petal.rest_created_at = 0.0

    def _apply_petal_night_tint(self, color: QColor, settings: EffectOverlaySettings, edge: bool = False):
        c = QColor(color)
        if not bool(getattr(settings, "petal_night_enabled", False)):
            return c
        tint = QColor(getattr(settings, "petal_night_tint_color", "#101A3A"))
        strength = max(0.0, min(1.0, float(getattr(settings, "petal_night_tint_strength", 0.35))))
        if edge:
            strength = min(1.0, strength * 1.15)
        mixed = QColor(
            max(0, min(255, int(c.red() * (1.0 - strength) + tint.red() * strength))),
            max(0, min(255, int(c.green() * (1.0 - strength) + tint.green() * strength))),
            max(0, min(255, int(c.blue() * (1.0 - strength) + tint.blue() * strength))),
            c.alpha(),
        )
        return mixed

    def _apply_petal_mouse_flutter(self, pos: QPointF, settings: EffectOverlaySettings, now: float, strong: bool = False):
        if not bool(getattr(settings, "petal_mouse_flutter_enabled", True)):
            return
        if not strong and now - getattr(self, "_last_petal_mouse_flutter", 0.0) < 0.045:
            return
        self._last_petal_mouse_flutter = now
        strength = max(0.0, float(getattr(settings, "petal_mouse_flutter_strength", 1.0))) * (1.45 if strong else 0.85)
        radius = 120.0 + 70.0 * strength
        for seq_name in ("_rose_petals", "_sakura_petals"):
            petals = getattr(self, seq_name, [])
            for petal in list(petals):
                dx = float(petal.x) - float(pos.x())
                dy = float(petal.y) - float(pos.y())
                dist = math.hypot(dx, dy)
                if dist > radius or dist <= 1.0:
                    continue
                power = (1.0 - dist / radius) * strength
                if power <= 0.0:
                    continue
                nx = dx / dist
                ny = dy / dist
                petal.vx += nx * (90.0 + 150.0 * power) + (-35.0 + self._random.random() * 70.0) * power
                petal.vy += min(-28.0, ny * 95.0 - (75.0 + self._random.random() * 90.0) * power)
                petal.rotation_speed += (-3.5 + self._random.random() * 7.0) * power
                if hasattr(petal, "resting"):
                    petal.resting = False
                if hasattr(petal, "fading"):
                    petal.fading = False

    def on_mouse_move(self, pos: QPoint):
        self._mouse_pos = QPointF(pos)
        self._mouse_active_until = time.time() + 0.7
        try:
            settings = get_effect_overlay_settings(self.cfg)
            self._apply_petal_mouse_flutter(QPointF(pos), settings, time.time(), strong=False)
            self._remove_snow_accumulation_at(QPointF(pos), settings, strong=False)
        except Exception:
            pass

    def on_mouse_press(self, pos: QPoint):
        self._mouse_pos = QPointF(pos)
        self._mouse_active_until = time.time() + 1.0
        settings = get_effect_overlay_settings(self.cfg)

        if settings.mouse_ripple_enabled:
            self._ripples.append(
                EffectRipple(
                    x=float(pos.x()),
                    y=float(pos.y()),
                    created_at=time.time(),
                    max_radius=settings.ripple_max_radius,
                    color=settings.ripple_color,
                    speed=settings.ripple_speed,
                )
            )

        if settings.mouse_flee_enabled:
            self._push_particles_away(QPointF(pos), strength=420.0)

        self._remove_snow_accumulation_at(QPointF(pos), settings, strong=True)
        self._apply_petal_mouse_flutter(QPointF(pos), settings, time.time(), strong=True)

    def on_mouse_release(self, pos: QPoint):
        self._mouse_pos = QPointF(pos)
        self._mouse_active_until = time.time() + 0.4

    def _ensure_emitters(self, r: QRectF, settings: EffectOverlaySettings):
        size_key = (int(r.width()), int(r.height()))
        if size_key != self._last_rect_size:
            self._particles.clear()
            self._rain.clear()
            self._last_rect_size = size_key

        while len(self._particles) < settings.particle_count:
            self._particles.append(self._new_particle(r, settings))
        if len(self._particles) > settings.particle_count:
            self._particles = self._particles[:settings.particle_count]

        while len(self._rain) < settings.rain_count:
            self._rain.append(self._new_raindrop(r, settings))
        if len(self._rain) > settings.rain_count:
            self._rain = self._rain[:settings.rain_count]

    def _new_particle(self, r: QRectF, settings: EffectOverlaySettings):
        angle = self._random.random() * math.tau
        speed = 8.0 + self._random.random() * 22.0 * max(0.1, settings.particle_speed)
        return EffectParticle(
            x=float(r.left() + self._random.random() * max(1.0, r.width())),
            y=float(r.top() + self._random.random() * max(1.0, r.height())),
            vx=math.cos(angle) * speed,
            vy=math.sin(angle) * speed,
            size=max(0.4, settings.particle_size * (0.5 + self._random.random() * 1.4)),
            alpha=0.25 + self._random.random() * 0.75,
            seed=self._random.random() * 10000.0,
        )

    def _new_raindrop(self, r: QRectF, settings: EffectOverlaySettings):
        speed = 260.0 + self._random.random() * 340.0 * max(0.1, settings.rain_speed)
        wind = -45.0 + self._random.random() * 90.0

        min_size = max(0.2, float(getattr(settings, "rain_drop_min_size", 1.0)))
        max_size = max(min_size, float(getattr(settings, "rain_drop_max_size", 2.4)))
        drop_size = min_size + self._random.random() * (max_size - min_size)

        return EffectParticle(
            x=float(r.left() + self._random.random() * max(1.0, r.width())),
            y=float(r.top() - self._random.random() * max(1.0, r.height())),
            vx=wind,
            vy=speed,
            size=drop_size,
            alpha=0.25 + self._random.random() * 0.55,
            seed=self._random.random() * 10000.0,
        )

    def _update_particles(self, r: QRectF, settings: EffectOverlaySettings, dt: float, now: float):
        mouse = self._mouse_pos if (self._mouse_pos is not None and now <= self._mouse_active_until) else None

        for particle in self._particles:
            wobble = math.sin(now * 1.7 + particle.seed) * 8.0
            particle.x += (particle.vx + wobble) * dt
            particle.y += particle.vy * dt

            if mouse is not None and settings.mouse_flee_enabled:
                dx = particle.x - mouse.x()
                dy = particle.y - mouse.y()
                dist2 = dx * dx + dy * dy
                radius = 150.0
                if 1.0 < dist2 < radius * radius:
                    dist = math.sqrt(dist2)
                    force = (1.0 - dist / radius) * 220.0 * settings.intensity
                    particle.x += (dx / dist) * force * dt
                    particle.y += (dy / dist) * force * dt

            if particle.x < r.left() - 40:
                particle.x = r.right() + 20
            elif particle.x > r.right() + 40:
                particle.x = r.left() - 20
            if particle.y < r.top() - 40:
                particle.y = r.bottom() + 20
            elif particle.y > r.bottom() + 40:
                particle.y = r.top() - 20

    def _update_rain(self, r: QRectF, settings: EffectOverlaySettings, dt: float):
        now = time.time()
        surface_y = r.top() + r.height() * max(
            0.0,
            min(1.0, getattr(settings, "rain_ripple_surface_y", 0.82))
        )
        puddle_rect = self._puddle_rect(r, settings) if bool(getattr(settings, "puddle_enabled", False)) else QRectF()
        puddle_active = puddle_rect.isValid() and not puddle_rect.isNull()

        for drop in self._rain:
            prev_y = drop.y

            drop.x += drop.vx * dt
            drop.y += drop.vy * dt

            impact_y = self._puddle_impact_y_for_x(r, settings, drop.x) if puddle_active else surface_y
            hit_surface = impact_y is not None and prev_y < impact_y <= drop.y
            out_of_bounds = (
                    drop.y > r.bottom() + 60 or
                    drop.x < r.left() - 80 or
                    drop.x > r.right() + 80
            )

            if hit_surface:
                self._maybe_spawn_rain_ripple(drop, float(impact_y), settings, now)
                self._reset_raindrop(drop, r, settings)
                continue

            if out_of_bounds:
                self._reset_raindrop(drop, r, settings)

    def _cleanup_ripples(self, now: float):
        alive = []
        for ripple in self._ripples:
            age = now - ripple.created_at
            duration = max(0.2, 1.1 / max(0.05, ripple.speed))
            if age <= duration:
                alive.append(ripple)
        self._ripples = alive

    def _maybe_spawn_rain_ripple(self, drop, surface_y: float, settings: EffectOverlaySettings, now: float):
        if not getattr(settings, "rain_ripple_enabled", True):
            return

        if not getattr(settings, "ripple_enabled", True):
            return

        if bool(getattr(settings, "puddle_enabled", False)):
            if not self._point_in_any_puddle(float(drop.x), float(surface_y), self.rect, settings):
                return

        cooldown = max(0.0, float(getattr(settings, "rain_ripple_cooldown", 0.025)))
        if now - getattr(self, "_last_rain_ripple_time", 0.0) < cooldown:
            return

        chance = max(0.0, min(1.0, float(getattr(settings, "rain_ripple_chance", 0.55))))
        if self._random.random() > chance:
            return

        speed_factor = max(0.2, min(2.5, abs(float(drop.vy)) / 520.0))
        min_radius = max(1.0, float(getattr(settings, "rain_ripple_min_radius", 24.0)))
        max_radius = max(min_radius, float(getattr(settings, "rain_ripple_max_radius_linked", 92.0)))
        radius = min_radius + (max_radius - min_radius) * min(1.0, speed_factor)

        self._ripples.append(
            EffectRipple(
                x=float(drop.x),
                y=float(surface_y),
                created_at=now,
                max_radius=radius,
                color=getattr(settings, "ripple_color", "#A8EFFF"),
                speed=max(0.05, float(getattr(settings, "ripple_speed", 1.0))) * (0.9 + speed_factor * 0.2),
            )
        )
        self._last_rain_ripple_time = now

    def _reset_raindrop(self, drop, r: QRectF, settings: EffectOverlaySettings):
        fresh = self._new_raindrop(r, settings)
        drop.x = fresh.x
        drop.y = r.top() - self._random.random() * 160.0
        drop.vx = fresh.vx
        drop.vy = fresh.vy
        drop.size = fresh.size
        drop.alpha = fresh.alpha
        drop.seed = fresh.seed

    def _push_particles_away(self, pos: QPointF, strength: float):
        for particle in self._particles:
            dx = particle.x - pos.x()
            dy = particle.y - pos.y()
            dist2 = dx * dx + dy * dy
            radius = 220.0
            if 1.0 < dist2 < radius * radius:
                dist = math.sqrt(dist2)
                force = (1.0 - dist / radius) * strength
                particle.x += (dx / dist) * force * 0.016
                particle.y += (dy / dist) * force * 0.016
                particle.vx += (dx / dist) * force * 0.05
                particle.vy += (dy / dist) * force * 0.05

    def _draw_particles(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        base = QColor(settings.particle_color)
        p.setPen(Qt.PenStyle.NoPen)

        for particle in self._particles:
            twinkle = 0.55 + 0.45 * math.sin(now * 2.8 + particle.seed)
            c = QColor(base)
            c.setAlpha(int(180 * particle.alpha * twinkle * settings.intensity))
            p.setBrush(QBrush(c))
            radius = max(1, int(particle.size * (0.8 + twinkle * 0.4)))
            p.drawEllipse(QPoint(int(particle.x), int(particle.y)), radius, radius)

    def _draw_rain(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings):
        color = QColor(settings.rain_color)
        base_length = float(getattr(settings, "rain_length", 16.0))
        length_randomness = max(
            0.0,
            min(2.0, float(getattr(settings, "rain_drop_length_randomness", 0.55)))
        )

        for drop in self._rain:
            c = QColor(color)
            c.setAlpha(int(190 * drop.alpha * settings.intensity))

            thickness = max(1, int(round(float(drop.size))))

            pen = QPen(c, thickness)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)

            variance = (
                    1.0
                    - length_randomness * 0.5
                    + (abs(math.sin(drop.seed)) * length_randomness)
            )
            length = max(1.0, base_length * variance)

            slant = drop.vx * 0.035

            p.drawLine(
                int(drop.x),
                int(drop.y),
                int(drop.x - slant),
                int(drop.y - length),
            )

    def _draw_glow_orbs(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        if settings.glow_count <= 0:
            return

        base = QColor(settings.glow_color)
        for i in range(settings.glow_count):
            phase = now * settings.glow_speed + i * 2.399963
            x = r.left() + r.width() * (0.5 + 0.42 * math.sin(phase * 0.57 + i))
            y = r.top() + r.height() * (0.5 + 0.38 * math.cos(phase * 0.43 + i * 1.7))
            radius = settings.glow_radius * (0.75 + 0.25 * math.sin(phase + i))
            self._draw_radial_glow(p, x, y, radius, base, int(80 * settings.intensity))

    def _draw_mouse_glow(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        if self._mouse_pos is None:
            return
        base = QColor(settings.mouse_glow_color)
        pulse = 0.8 + 0.2 * math.sin(now * 6.0)
        self._draw_radial_glow(
            p,
            self._mouse_pos.x(),
            self._mouse_pos.y(),
            settings.mouse_glow_radius * pulse,
            base,
            int(95 * settings.intensity),
        )

    def _draw_radial_glow(self, p: QPainter, x: float, y: float, radius: float, color: QColor, alpha: int):
        gradient = QRadialGradient(x, y, max(1.0, radius))
        c0 = QColor(color)
        c0.setAlpha(max(0, min(255, alpha)))
        c1 = QColor(color)
        c1.setAlpha(max(0, min(255, int(alpha * 0.25))))
        c2 = QColor(color)
        c2.setAlpha(0)
        gradient.setColorAt(0.0, c0)
        gradient.setColorAt(0.45, c1)
        gradient.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(gradient))
        p.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))

    def _draw_ripples(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        puddle_rect = self._puddle_rect(r, settings) if bool(getattr(settings, "puddle_enabled", False)) else QRectF()
        puddle_active = puddle_rect.isValid() and not puddle_rect.isNull()
        puddle_path = self._puddle_path(r, settings) if puddle_active else QPainterPath()
        for ripple in self._ripples:
            age = now - ripple.created_at
            duration = max(0.2, 1.1 / max(0.05, ripple.speed))
            t = max(0.0, min(1.0, age / duration))
            radius = ripple.max_radius * self._ease_out_cubic(t)
            alpha = int(210 * (1.0 - t) * settings.intensity)
            c = QColor(ripple.color)
            c.setAlpha(max(0, min(255, alpha)))
            pen = QPen(c, max(1, int(3 * (1.0 - t) + 1)))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            should_clip_to_puddle = puddle_active and self._point_in_any_puddle(float(ripple.x), float(ripple.y), r, settings)
            if should_clip_to_puddle:
                p.save()
                p.setClipPath(puddle_path)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(ripple.x, ripple.y), radius, radius)
            if should_clip_to_puddle:
                p.restore()

    def _draw_noise(self, p: QPainter, r: QRectF, settings: EffectOverlaySettings, now: float):
        color = QColor(settings.noise_color)
        color.setAlpha(settings.noise_alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color))

        width = int(max(1, r.width()))
        height = int(max(1, r.height()))
        density = max(40, min(900, int(width * height / 18000)))
        seed = int(now * 18)
        rng = random.Random(seed)

        for _ in range(density):
            x = int(r.left() + rng.random() * width)
            y = int(r.top() + rng.random() * height)
            if rng.random() < 0.8:
                p.drawRect(x, y, 1, 1)
            else:
                p.drawRect(x, y, 2, 1)

    def _ease_out_cubic(self, t: float):
        return 1.0 - pow(1.0 - t, 3.0)

    def _paint_selection(self, p: QPainter):
        settings = get_effect_overlay_settings(self.cfg)
        selection_rect = self.interaction_rect() if (self._has_visible_sun_effect(settings) or self._has_visible_moon_effect(settings) or self._has_visible_ice_effect(settings) or self._has_visible_puddle_effect(settings)) else self.rect
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(selection_rect, 16, 16)
        marker_pen = QPen(QColor(255, 255, 255, 190), 1)
        marker_pen.setStyle(Qt.PenStyle.SolidLine)
        p.setPen(marker_pen)
        if self._has_visible_sun_effect(settings):
            center = self._sun_center(self.rect, settings)
            p.drawLine(QPointF(center.x() - 6.0, center.y()), QPointF(center.x() + 6.0, center.y()))
            p.drawLine(QPointF(center.x(), center.y() - 6.0), QPointF(center.x(), center.y() + 6.0))
        if self._has_visible_moon_effect(settings):
            center = self._moon_center(self.rect, settings)
            p.drawLine(QPointF(center.x() - 6.0, center.y()), QPointF(center.x() + 6.0, center.y()))
            p.drawLine(QPointF(center.x(), center.y() - 6.0), QPointF(center.x(), center.y() + 6.0))
        if self._has_visible_puddle_effect(settings):
            p.setPen(QPen(QColor(180, 235, 255, 190), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for _, puddle_rect in self._puddle_rects(self.rect, settings):
                p.drawEllipse(puddle_rect)
                center = puddle_rect.center()
                p.drawLine(QPointF(center.x() - 5.0, center.y()), QPointF(center.x() + 5.0, center.y()))
                p.drawLine(QPointF(center.x(), center.y() - 5.0), QPointF(center.x(), center.y() + 5.0))
                for handle_rect in self._puddle_resize_handles(puddle_rect).values():
                    p.fillRect(handle_rect, QColor(180, 235, 255, 160))
                    p.drawRect(handle_rect)

class VisualizerWidget(BaseWidget):
    def __init__(self, cfg):
        super().__init__(cfg)
        self._peak_levels = []
        self._last_peak_update = time.time()
        self._last_visualizer_frame_time = 0.0
        self._visualizer_frame_cache = None
        self._visualizer_frame_cache_key = None

    def _ensure_peak_levels(self, count):
        if len(self._peak_levels) != count:
            self._peak_levels = [0.0 for _ in range(count)]
            self._last_peak_update = time.time()

    def _visualizer_orientation(self):
        value = str(getattr(self.cfg, "visualizer_orientation", "horizontal") or "horizontal").strip().lower()
        return "vertical" if value in ("vertical", lds_tr("縦"), "vertical_stack", "side") else "horizontal"

    def _visualizer_bar_width_scale(self):
        try:
            scale = float(getattr(self.cfg, "visualizer_bar_width_scale", 1.0))
        except Exception:
            scale = 1.0
        return max(0.35, min(2.4, scale))

    def _visualizer_frame_interval_seconds(self) -> float:
        if not bool(getattr(self.cfg, "visualizer_frame_rate_enabled", True)):
            return 0.0
        try:
            fps = int(getattr(self.cfg, "visualizer_frame_rate", 60))
        except Exception:
            fps = 60
        fps = max(1, min(240, fps))
        return 1.0 / fps

    def _visualizer_frame_cache_key_for(self, ctx: Dict):
        r = self.rect
        return (
            int(r.x()), int(r.y()), int(r.width()), int(r.height()),
            self.cfg.color, self.cfg.bg, int(getattr(self.cfg, "bg_alpha", 155)),
            bool(getattr(self.cfg, "visualizer_flip_vertical", False)),
            bool(getattr(self.cfg, "visualizer_peak_bar_enabled", True)),
            bool(getattr(self.cfg, "visualizer_glow_enabled", True)),
            round(float(getattr(self.cfg, "visualizer_bar_width_scale", 1.0)), 3),
            str(getattr(self.cfg, "visualizer_orientation", "horizontal")),
            bool(getattr(self, "selected", False)),
            bool(ctx.get("edit_mode", True)) if isinstance(ctx, dict) else True,
        )

    def paint(self, p: QPainter, ctx: Dict):
        now = time.time()
        interval = self._visualizer_frame_interval_seconds()
        r = self.rect
        key = self._visualizer_frame_cache_key_for(ctx)
        cached = getattr(self, "_visualizer_frame_cache", None)
        due = (
            interval <= 0.0
            or cached is None
            or cached.isNull()
            or key != getattr(self, "_visualizer_frame_cache_key", None)
            or now - float(getattr(self, "_last_visualizer_frame_time", 0.0)) >= interval
        )
        if due:
            w = max(1, int(round(r.width())))
            h = max(1, int(round(r.height())))
            image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            ip = QPainter(image)
            try:
                ip.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                ip.translate(-r.left(), -r.top())
                self._paint_visualizer_direct(ip, ctx)
            finally:
                ip.end()
            self._visualizer_frame_cache = image
            self._visualizer_frame_cache_key = key
            self._last_visualizer_frame_time = now
            cached = image
        if cached is not None and not cached.isNull():
            p.drawImage(QPointF(r.left(), r.top()), cached)
        else:
            self._paint_visualizer_direct(p, ctx)

    def _paint_visualizer_direct(self, p: QPainter, ctx: Dict):
        audio: AudioEngine = ctx["audio"]
        bars = audio.get_spectrum()
        count = max(1, len(bars))
        r = self.rect
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg = widget_bg_color(self.cfg)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 16, 16)

        margin = 14
        label_h = 18
        available_w = max(1.0, r.width() - margin * 2)
        available_h = max(1.0, r.height() - margin * 2 - label_h)
        left = r.left() + margin
        top = r.top() + margin + label_h
        bottom = r.bottom() - margin
        right = r.right() - margin

        color = QColor(self.cfg.color)
        flip_vertical = bool(getattr(self.cfg, "visualizer_flip_vertical", False))
        peak_bar_enabled = bool(getattr(self.cfg, "visualizer_peak_bar_enabled", True))
        glow_enabled = bool(getattr(self.cfg, "visualizer_glow_enabled", True))
        orientation = self._visualizer_orientation()
        width_scale = self._visualizer_bar_width_scale()
        now = time.time()
        dt = max(0.001, min(0.08, now - getattr(self, "_last_peak_update", now)))
        self._last_peak_update = now
        self._ensure_peak_levels(count)
        peak_decay = 1.15 * dt

        if orientation == "vertical":
            slot_h = available_h / count
            gap = min(3.0, max(1.0, slot_h * 0.28))
            bar_h = max(2.0, min(slot_h * 0.96, slot_h * width_scale - gap))
            for i, v in enumerate(bars):
                value = max(0.0, min(1.0, float(v)))
                self._peak_levels[i] = max(value, max(0.0, self._peak_levels[i] - peak_decay)) if peak_bar_enabled else value
                y = top + i * slot_h + (slot_h - bar_h) / 2.0
                w = max(2.0, available_w * value)
                peak_x = left + available_w * self._peak_levels[i]
                x = left
                if flip_vertical:
                    x = right - w
                    peak_x = right - available_w * self._peak_levels[i]
                rect = QRectF(x, y, w, bar_h)
                if glow_enabled and value > 0.025:
                    self._draw_visualizer_bar_glow(p, rect, color, value, flip_vertical, orientation)
                grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
                grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 165))
                grad.setColorAt(0.62, QColor(color.red(), color.green(), color.blue(), 245))
                grad.setColorAt(1.0, QColor(255, 255, 255, 110))
                if flip_vertical:
                    grad.setStart(rect.right(), rect.top())
                    grad.setFinalStop(rect.left(), rect.top())
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 3, 3)
                if peak_bar_enabled:
                    self._draw_visualizer_peak_bar(p, x, y, rect.width(), bar_h, color, value, flip_vertical, orientation, peak_x)
        else:
            slot_w = available_w / count
            gap = min(3.0, max(1.0, slot_w * 0.28))
            bar_w = max(2.0, min(slot_w * 0.96, slot_w * width_scale - gap))
            for i, v in enumerate(bars):
                value = max(0.0, min(1.0, float(v)))
                h = max(2.0, available_h * value)
                x = left + i * slot_w + (slot_w - bar_w) / 2.0
                self._peak_levels[i] = max(value, max(0.0, self._peak_levels[i] - peak_decay)) if peak_bar_enabled else value
                y = top if flip_vertical else bottom - h
                peak_y = top + available_h * self._peak_levels[i] if flip_vertical else bottom - available_h * self._peak_levels[i]
                rect = QRectF(x, y, bar_w, h)
                if glow_enabled and value > 0.025:
                    self._draw_visualizer_bar_glow(p, rect, color, value, flip_vertical, orientation)
                grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
                if flip_vertical:
                    grad.setColorAt(0.0, QColor(255, 255, 255, 105))
                    grad.setColorAt(0.38, QColor(color.red(), color.green(), color.blue(), 245))
                    grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 165))
                else:
                    grad.setColorAt(0.0, QColor(255, 255, 255, 110))
                    grad.setColorAt(0.35, QColor(color.red(), color.green(), color.blue(), 245))
                    grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 165))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 3, 3)
                if peak_bar_enabled:
                    self._draw_visualizer_peak_bar(p, x, peak_y, bar_w, h, color, value, flip_vertical, orientation)

        p.setPen(QColor(230, 240, 255, 220))
        p.setFont(QFont("Segoe UI", 9))
        label = ""
        if audio.use_fake:
            label += " / fallback"
        if orientation == "vertical":
            label += " / vertical"
        p.drawText(QRectF(r.left() + 14, r.top() + 8, r.width() - 20, 18), label)
        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)
        p.restore()

    def _draw_visualizer_bar_glow(self, p: QPainter, bar_rect: QRectF, color: QColor, value: float, flip_vertical: bool, orientation: str = "horizontal"):
        glow = QColor(color)
        glow.setAlpha(max(18, min(145, int(42 + value * 125))))
        if orientation == "vertical":
            halo = QRectF(bar_rect.left() - 6, bar_rect.top() - max(2.0, bar_rect.height() * 0.45), bar_rect.width() + 12, bar_rect.height() + max(4.0, bar_rect.height() * 0.9))
        else:
            halo = QRectF(bar_rect.left() - max(2.0, bar_rect.width() * 0.45), bar_rect.top() - 5, bar_rect.width() + max(4.0, bar_rect.width() * 0.9), bar_rect.height() + 10)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(halo, 5, 5)
        edge = QColor(color)
        edge.setAlpha(max(20, min(120, int(30 + value * 100))))
        p.setBrush(QBrush(edge))
        if orientation == "vertical":
            edge_rect = QRectF((bar_rect.left() - 3) if flip_vertical else (bar_rect.right() - 3), bar_rect.top() - 1, 6, bar_rect.height() + 2)
        elif flip_vertical:
            edge_rect = QRectF(bar_rect.left() - 1, bar_rect.bottom() - 3, bar_rect.width() + 2, 6)
        else:
            edge_rect = QRectF(bar_rect.left() - 1, bar_rect.top() - 3, bar_rect.width() + 2, 6)
        p.drawRoundedRect(edge_rect, 3, 3)
        p.restore()

    def _draw_visualizer_peak_bar(self, p: QPainter, x: float, peak_pos: float, bar_w: float, bar_h: float, color: QColor, value: float, flip_vertical: bool, orientation: str = "horizontal", peak_x: float = None):
        p.save()
        peak_color = QColor(color)
        peak_color.setAlpha(max(150, min(255, int(165 + value * 90))))
        shine = QColor(255, 255, 255, max(80, min(210, int(90 + value * 120))))
        if orientation == "vertical":
            cap_x = peak_x if peak_x is not None else x + bar_w
            cap_x = cap_x - 2.0 if flip_vertical else cap_x + 2.0
            cap_rect = QRectF(cap_x, peak_pos - 0.75, 3.0, max(6.0, bar_h + 1.5))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(peak_color))
            p.drawRoundedRect(cap_rect, 1.5, 1.5)
            p.setBrush(QBrush(shine))
            p.drawRoundedRect(QRectF(cap_rect.left(), cap_rect.top(), 1.0, cap_rect.height()), 0.8, 0.8)
        else:
            cap_h = 3.0
            cap_w = max(6.0, bar_w + 1.5)
            cap_y = peak_pos + 2.0 if flip_vertical else peak_pos - cap_h - 2.0
            cap_rect = QRectF(x - 0.75, cap_y, cap_w, cap_h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(peak_color))
            p.drawRoundedRect(cap_rect, 1.5, 1.5)
            p.setBrush(QBrush(shine))
            p.drawRoundedRect(QRectF(cap_rect.left(), cap_rect.top(), cap_rect.width(), 1.0), 0.8, 0.8)
        p.restore()

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

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
            except Exception:
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
            except Exception:
                pass

            reader = DataReader(stream)
            await reader.load_async(size)

            data = bytearray(size)
            reader.read_bytes(data)

            try:
                reader.close()
            except Exception:
                pass

            return bytes(data)

        except Exception:
            return b""

class MediaPlayerWidget(BaseWidget):
    def __init__(self, cfg):
        super().__init__(cfg)
        self._last_thumbnail_bytes = None
        self._thumbnail_pixmap = None

    def button_rects(self):
        r = self.rect

        button_size = min(42, max(30, int(r.height() * 0.22)))
        gap = 10

        total_w = button_size * 4 + gap * 3
        start_x = r.left() + (r.width() - total_w) / 2
        y = r.bottom() - button_size - 18

        return {
            "prev": QRectF(start_x, y, button_size, button_size),
            "play": QRectF(start_x + button_size + gap, y, button_size, button_size),
            "next": QRectF(start_x + (button_size + gap) * 2, y, button_size, button_size),
            "stop": QRectF(start_x + (button_size + gap) * 3, y, button_size, button_size),
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

        try:
            bg = widget_bg_color(self.cfg)
        except Exception:
            bg = QColor(self.cfg.bg or "#10141C")
            bg.setAlpha(getattr(self.cfg, "bg_alpha", 155))

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        accent = QColor(self.cfg.color or "#80FF9F")
        title_color = QColor(245, 248, 255)
        sub_color = QColor(210, 218, 230, 160)
        muted_color = QColor(210, 218, 230, 115)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.cfg.title or ""
        )

        media_meta = ctx.get("media_meta")
        data = media_meta.snapshot() if media_meta is not None else {}

        cover_rect = QRectF(r.left() + 14, r.top() + 44, 76, 76)
        text_left = cover_rect.right() + 14
        text_w = r.right() - text_left - 14

        self._draw_cover(p, cover_rect, data.get("thumbnail_bytes", b""), accent)

        title = data.get("title", "") or "No media"
        artist = data.get("artist", "") or ""
        album = data.get("album", "") or ""
        status = data.get("playback_status", "") or ""
        app_id = data.get("app_id", "") or ""
        error = data.get("error", "") or ""

        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(text_left, r.top() + 46, text_w, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._elide_text(p, title, int(text_w))
        )

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(sub_color)
        p.drawText(
            QRectF(text_left, r.top() + 72, text_w, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._elide_text(p, artist or album or app_id, int(text_w))
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(muted_color)
        meta_line = status
        if album and artist:
            meta_line = f"{status} / {album}" if status else album
        elif app_id and not artist:
            meta_line = f"{status} / {app_id}" if status else app_id

        p.drawText(
            QRectF(text_left, r.top() + 94, text_w, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._elide_text(p, meta_line, int(text_w))
        )

        if error:
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QColor(255, 190, 130, 170))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 124, r.width() - 28, 16),
                Qt.AlignLeft | Qt.AlignVCenter,
                self._elide_text(p, error, int(r.width() - 28))
            )

        rects = self.button_rects()
        self._draw_button(p, rects["prev"], "⏮", accent)
        self._draw_button(p, rects["play"], "⏯", accent)
        self._draw_button(p, rects["next"], "⏭", accent)
        self._draw_button(p, rects["stop"], "⏹", accent)

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()

    def _draw_cover(self, p: QPainter, rect: QRectF, thumbnail_bytes, accent: QColor):
        pixmap = self._thumbnail_from_bytes(thumbnail_bytes)

        p.setBrush(QColor(255, 255, 255, 24))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawRoundedRect(rect, 14, 14)

        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                int(rect.width()),
                int(rect.height()),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            x = int(rect.left() + (rect.width() - scaled.width()) / 2)
            y = int(rect.top() + (rect.height() - scaled.height()) / 2)

            p.save()
            p.setClipRect(rect)
            p.drawPixmap(x, y, scaled)
            p.restore()
            return

        p.setFont(QFont("Segoe UI Symbol", 28, QFont.Bold))
        p.setPen(accent)
        p.drawText(rect, Qt.AlignCenter, "♪")

    def _thumbnail_from_bytes(self, thumbnail_bytes):
        if not thumbnail_bytes:
            self._last_thumbnail_bytes = None
            self._thumbnail_pixmap = None
            return None

        if self._last_thumbnail_bytes == thumbnail_bytes and self._thumbnail_pixmap is not None:
            return self._thumbnail_pixmap

        image = QImage.fromData(thumbnail_bytes)
        if image.isNull():
            self._last_thumbnail_bytes = None
            self._thumbnail_pixmap = None
            return None

        self._last_thumbnail_bytes = thumbnail_bytes
        self._thumbnail_pixmap = QPixmap.fromImage(image)
        return self._thumbnail_pixmap

    def _draw_button(self, p: QPainter, rect: QRectF, text: str, accent: QColor):
        p.setBrush(QColor(255, 255, 255, 24))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawRoundedRect(rect, 14, 14)

        p.setFont(QFont("Segoe UI Symbol", 15, QFont.Bold))
        p.setPen(accent)
        p.drawText(rect, Qt.AlignCenter, text)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

    def _elide_text(self, p: QPainter, text: str, width: int):
        metrics = p.fontMetrics()
        return metrics.elidedText(text or "", Qt.ElideRight, max(20, width))

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

        p.save()

        try:
            bg = widget_bg_color(self.cfg)
        except Exception:
            bg = QColor(self.cfg.bg or "#10141C")
            bg.setAlpha(getattr(self.cfg, "bg_alpha", 155))

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        down_color = QColor(get_network_down_color(self.cfg))
        up_color = QColor(get_network_up_color(self.cfg))

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
            "up",
            format_bytes_per_sec(getattr(monitor, "net_up", 0.0)),
            up_color
        )

        self._draw_net_row(
            p,
            content_x,
            r.top() + 68,
            content_w,
            "down",
            format_bytes_per_sec(getattr(monitor, "net_down", 0.0)),
            down_color
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
            up_history,
            down_color,
            up_color
        )

        total_down = self._format_total_bytes(
            getattr(monitor, "net_recv_total", 0)
        )
        total_up = self._format_total_bytes(
            getattr(monitor, "net_sent_total", 0)
        )

        self._draw_network_totals(
            p,
            QRectF(r.left() + 16, r.bottom() - 26, r.width() - 32, 18),
            total_down,
            total_up,
            down_color,
            up_color
        )

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()

    def _network_direction_label(self, direction):
        direction = str(direction or "").lower()
        if direction in ("up", "upload", "sent"):
            return lds_tr("上り")
        return lds_tr("下り")

    def _draw_net_row(self, p: QPainter, x, y, w, direction, value, color):
        icon_rect = QRectF(x, y, 28, 20)
        label_text = self._network_direction_label(direction)

        self._draw_network_arrow_icon(
            p,
            icon_rect,
            direction,
            color,
            QColor(255, 255, 255, 26)
        )

        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        label_metrics = p.fontMetrics()
        label_w = min(42, max(28, label_metrics.horizontalAdvance(label_text) + 8))
        label_rect = QRectF(x + 34, y, label_w, 20)
        value_rect = QRectF(x + 34 + label_w + 6, y, max(20, w - (34 + label_w + 6)), 20)

        label_color = QColor(235, 240, 250, 210)
        p.setPen(label_color)
        p.drawText(
            label_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            label_text
        )

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(color)
        p.drawText(
            value_rect,
            Qt.AlignRight | Qt.AlignVCenter,
            value
        )

    def _draw_network_arrow_icon(self, p: QPainter, rect: QRectF, direction, color, bg_color=None):
        """Draw upload/download arrow icon using QPainter primitives, not text glyphs."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if bg_color is not None:
            bg = QColor(bg_color)
            p.setPen(QPen(QColor(255, 255, 255, 34), 1))
            p.setBrush(QBrush(bg))
            pill = QRectF(rect.left() + 2, rect.top() + 1, min(rect.width() - 4, 22), rect.height() - 2)
            p.drawRoundedRect(pill, 9, 9)

        c = QColor(color)
        c.setAlpha(max(150, c.alpha()))
        pen = QPen(c, 2.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        cx = rect.left() + min(rect.width(), 24) / 2.0
        cy = rect.center().y()
        top = cy - 6.2
        bottom = cy + 6.2
        head = 5.0

        direction = str(direction or "").lower()

        if direction in ("up", "upload", "sent"):
            p.drawLine(QPointF(cx, bottom), QPointF(cx, top))
            p.drawLine(QPointF(cx, top), QPointF(cx - head, top + head))
            p.drawLine(QPointF(cx, top), QPointF(cx + head, top + head))
        else:
            p.drawLine(QPointF(cx, top), QPointF(cx, bottom))
            p.drawLine(QPointF(cx, bottom), QPointF(cx - head, bottom - head))
            p.drawLine(QPointF(cx, bottom), QPointF(cx + head, bottom - head))

        p.restore()

    def _draw_network_totals(self, p: QPainter, rect: QRectF, total_down, total_up, down_color, up_color):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setFont(QFont("Segoe UI", 8))

        total_text = "Total"
        down_label = "下り"
        up_label = "上り"
        gap = 5
        icon_w = 16
        metric = p.fontMetrics()
        total_w = metric.horizontalAdvance(total_text)
        down_label_w = metric.horizontalAdvance(down_label)
        up_label_w = metric.horizontalAdvance(up_label)
        down_w = metric.horizontalAdvance(str(total_down))
        up_w = metric.horizontalAdvance(str(total_up))
        full_w = (
            total_w + gap +
            icon_w + 2 + down_label_w + 4 + down_w +
            gap * 2 +
            icon_w + 2 + up_label_w + 4 + up_w
        )
        x = rect.left() + max(0, (rect.width() - full_w) / 2.0)
        y = rect.top()

        p.setPen(QColor(210, 218, 230, 160))
        p.drawText(QRectF(x, y, total_w, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, total_text)
        x += total_w + gap

        self._draw_network_arrow_icon(
            p,
            QRectF(x, y, icon_w, rect.height()),
            "down",
            down_color,
            None
        )
        x += icon_w + 2
        p.setPen(QColor(210, 218, 230, 170))
        p.drawText(QRectF(x, y, down_label_w, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, down_label)
        x += down_label_w + 4
        p.drawText(QRectF(x, y, down_w, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, str(total_down))
        x += down_w + gap * 2

        self._draw_network_arrow_icon(
            p,
            QRectF(x, y, icon_w, rect.height()),
            "up",
            up_color,
            None
        )
        x += icon_w + 2
        p.setPen(QColor(210, 218, 230, 170))
        p.drawText(QRectF(x, y, up_label_w, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, up_label)
        x += up_label_w + 4
        p.drawText(QRectF(x, y, up_w, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, str(total_up))

        p.restore()

    def _draw_history_graph(self, p: QPainter, rect: QRectF, down_history, up_history, down_color, up_color):
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
            up_values,
            padded_max,
            up_color,
            True
        )
        self._draw_graph_line(
            p,
            rect,
            down_values,
            padded_max,
            down_color,
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
        p.save()

        p.setRenderHint(QPainter.Antialiasing, True)

        cx = r.center().x()
        cy = r.center().y()
        radius = min(r.width(), r.height()) * 0.38
        accent = QColor(self.cfg.color)
        p.setBrush(QColor("#0E1118"))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        p.setPen(QPen(accent, 4))
        p.drawEllipse(QPointF(cx, cy), radius * 1.02, radius * 1.02)

        for i in range(60):
            angle = math.radians(i * 6 - 90)

            inner = radius * (0.80 if i % 5 == 0 else 0.88)
            outer = radius * 0.96

            pen = QPen(QColor(255, 255, 255, 200 if i % 5 == 0 else 80), 2 if i % 5 == 0 else 1)

            p.setPen(pen)
            p.drawLine(
                int(cx + math.cos(angle) * inner),
                int(cy + math.sin(angle) * inner),
                int(cx + math.cos(angle) * outer),
                int(cy + math.sin(angle) * outer)
            )

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(QColor(240, 240, 255))

        for num in range(1, 13):
            angle = math.radians(num * 30 - 90)
            tr = radius * 0.65

            x = cx + math.cos(angle) * tr
            y = cy + math.sin(angle) * tr

            p.drawText(QRectF(x - 12, y - 10, 24, 20), Qt.AlignCenter, str(num))

        now = time.localtime()
        h = now.tm_hour % 12
        m = now.tm_min
        s = now.tm_sec

        ha = ((h + m / 60) * 30) - 90
        ma = ((m + s / 60) * 6) - 90
        sa = s * 6 - 90

        self._draw_hand(p, cx, cy, radius * 0.58, ha, QColor('#D3D3D3'), 5)
        self._draw_hand(p, cx, cy, radius * 0.82, ma, QColor('#D3D3D3'), 3)
        self._draw_hand(p, cx, cy, radius * 0.92, sa, accent, 2)

        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 4, 4)
        p.restore()

    def _draw_hand(self, p, cx, cy, length, angle_deg, color, width):
        angle = math.radians(angle_deg)
        x = cx + math.cos(angle) * length
        y = cy + math.sin(angle) * length

        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)

        p.setPen(pen)
        p.drawLine(int(cx), int(cy), int(x), int(y))

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

        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
DEFAULT_JS_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: transparent;
    font-family: "Segoe UI", sans-serif;
    color: white;
}
.card {
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    border-radius: 16px;
    padding: 16px;
    background: rgba(16, 20, 28, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
}
.title {
    font-size: 20px;
    font-weight: 700;
    color: #80FF9F;
}
button {
    margin-top: 12px;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(128, 255, 159, 0.55);
    background: rgba(128, 255, 159, 0.12);
    color: white;
}""" + __htmls


def build_js_html_document(html: str) -> str:
    html = html or ""

    if "<html" in html.lower() or "<!doctype" in html.lower():
        return html

    return f"""<!doctype html>
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


class JSHtmlViewManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.views = {}
        self.last_html = {}
        self.available = True
        self.error = ""

        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView  
        except Exception as e:
            self.available = False
            self.error = repr(e)

    def set_visible(self, visible: bool):
        for view in list(getattr(self, "views", {}).values()):
            try:
                view.setVisible(visible)
            except Exception:
                pass

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
                view = self._create_view()
                self.views[key] = view

            self._sync_view(widget, view)

        stale_ids = [key for key in self.views.keys() if key not in active_ids]
        for key in stale_ids:
            view = self.views.pop(key)
            self.last_html.pop(key, None)
            try:
                view.hide()
                view.deleteLater()
            except Exception:
                pass

    def clear(self):
        for view in list(self.views.values()):
            try:
                view.hide()
                view.deleteLater()
            except Exception:
                pass

        self.views.clear()
        self.last_html.clear()

    def _create_view(self):
        from PySide6.QtWebEngineWidgets import QWebEngineView

        view = QWebEngineView(self.canvas)
        view.setAttribute(Qt.WA_TranslucentBackground, True)
        view.setStyleSheet("background: transparent;")

        try:
            page = view.page()
            page.setBackgroundColor(Qt.transparent)
        except Exception:
            pass

        try:
            settings = view.settings()
            try:
                from PySide6.QtWebEngineCore import QWebEngineSettings
                settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            except Exception:
                pass
        except Exception:
            pass
        thread = Thread()
        thread.set_func(view.show)
        thread.start()
        THREADS.append(thread)
        return view

    def _sync_view(self, widget, view):
        cfg = widget.cfg
        r = widget.rect

        view.setGeometry(
            int(r.left()),
            int(r.top()),
            max(1, int(r.width())),
            max(1, int(r.height()))
        )

        edit_mode = bool(getattr(self.canvas, "edit_mode", True))
        view.setAttribute(Qt.WA_TransparentForMouseEvents, edit_mode)

        html = get_js_html_from_config(cfg)
        html = build_js_html_document(html)

        key = id(widget)
        if self.last_html.get(key) != html:
            self.last_html[key] = html
            try:
                view.setHtml(html, QUrl("about:blank"))
            except Exception:
                view.setHtml(html)

        if not view.isVisible():
            thread = Thread()
            thread.set_func(view.show)
            thread.start()
            THREADS.append(thread)


def get_js_html_from_config(cfg):
    
    return getattr(cfg, "text", "") or DEFAULT_JS_HTML


def set_js_html_to_config(cfg, html: str):
    
    cfg.text = html or ""


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
        <p style="color:white;">{}</p>
        """.format(lds_tr("ここに HTML/CSS 風の内容を書けます。"))

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

class WeatherWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        weather = ctx["weather"]

        location = getattr(self.cfg, "weather_location", "")
        weather.set_location(location)

        data = weather.snapshot()
        r = self.rect

        p.save()

        try:
            bg = widget_bg_color(self.cfg)
        except Exception:
            bg = QColor(self.cfg.bg or "#10141C")
            bg.setAlpha(getattr(self.cfg, "bg_alpha", 155))

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        accent = QColor(self.cfg.color or "#80FF9F")
        title_color = QColor(245, 248, 255)
        sub_color = QColor(210, 218, 230, 170)
        text_color = QColor(235, 240, 250, 220)

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.cfg.title or ""
        )

        area_label = data.get("area") or location or lds_tr("現在地")
        country = data.get("country") or ""

        if country:
            place_text = f"{area_label}, {country}"
        else:
            place_text = area_label

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(sub_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 34, r.width() - 28, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            place_text
        )

        error = data.get("error", "")

        if error:
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor(255, 180, 120))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 62, r.width() - 28, 40),
                Qt.AlignLeft | Qt.AlignVCenter,
                lds_tr("天気の取得に失敗しました")
            )

            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(255, 210, 180, 160))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 98, r.width() - 28, 50),
                Qt.AlignLeft | Qt.TextWordWrap,
                error
            )

            if self.selected and ctx.get("edit_mode", True):
                self._paint_selection(p)

            p.restore()
            return

        temp = data.get("temperature", "--")
        feels = data.get("feels_like", "--")
        desc = data.get("description", "Loading...")
        humidity = data.get("humidity", "--")
        wind = data.get("wind_kmph", "--")
        icon = data.get("icon", "☁")

        icon_rect = QRectF(r.left() + 14, r.top() + 56, r.width() * 0.22, 62)
        temp_rect = QRectF(r.left() + r.width() * 0.25, r.top() + 58, r.width() * 0.23, 56)
        desc_rect = QRectF(r.left() + r.width() * 0.50, r.top() + 62, r.width() * 0.46, 24)
        feels_rect = QRectF(r.left() + r.width() * 0.50, r.top() + 88, r.width() * 0.46, 20)

        p.setFont(QFont("Segoe UI Emoji", 36))
        p.setPen(accent)
        p.drawText(
            icon_rect,
            Qt.AlignCenter,
            icon
        )

        p.setFont(QFont("Segoe UI", 34, QFont.Bold))
        p.setPen(accent)
        p.drawText(
            temp_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            f"{temp}°"
        )

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(text_color)
        p.drawText(
            desc_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            desc
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(sub_color)
        p.drawText(
            feels_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            lds_tr("体感 ") + f"{feels}°C"
        )

        info_top = r.top() + 122
        info_h = 22

        self._draw_info_row(
            p,
            r.left() + 14,
            info_top,
            r.width() - 28,
            lds_tr("湿度"),
            f"{humidity}%",
            sub_color,
            text_color
        )

        self._draw_info_row(
            p,
            r.left() + 14,
            info_top + info_h,
            r.width() - 28,
            lds_tr("風速"),
            f"{wind} km/h",
            sub_color,
            text_color
        )

        forecast = data.get("forecast", [])
        forecast_top = info_top + info_h * 2 + 8

        if forecast and r.height() >= 220:
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.setPen(sub_color)
            p.drawText(
                QRectF(r.left() + 14, forecast_top, r.width() - 28, 18),
                Qt.AlignLeft | Qt.AlignVCenter,
                lds_tr("3日予報")
            )

            card_top = forecast_top + 22
            card_w = (r.width() - 34) / 3.0

            for i, item in enumerate(forecast[:3]):
                x = r.left() + 14 + i * (card_w + 3)
                rect = QRectF(x, card_top, card_w, 56)

                p.setBrush(QColor(255, 255, 255, 20))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(rect, 10, 10)

                date = item.get("date", "")
                max_t = item.get("max", "--")
                min_t = item.get("min", "--")
                day_icon = item.get("icon", "☁")

                p.setFont(QFont("Segoe UI", 7))
                p.setPen(sub_color)
                p.drawText(
                    QRectF(rect.left() + 5, rect.top() + 3, rect.width() - 10, 12),
                    Qt.AlignCenter,
                    date[-5:] if len(date) >= 5 else date
                )

                p.setFont(QFont("Segoe UI Emoji", 14))
                p.setPen(accent)
                p.drawText(
                    QRectF(rect.left() + 5, rect.top() + 16, rect.width() - 10, 18),
                    Qt.AlignCenter,
                    day_icon
                )

                p.setFont(QFont("Segoe UI", 8, QFont.Bold))
                p.setPen(text_color)
                p.drawText(
                    QRectF(rect.left() + 5, rect.top() + 35, rect.width() - 10, 16),
                    Qt.AlignCenter,
                    f"{min_t}°/{max_t}°"
                )

        updated = data.get("updated_at", "")

        if updated:
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QColor(210, 218, 230, 120))
            p.drawText(
                QRectF(r.left() + 12, r.bottom() - 20, r.width() - 24, 14),
                Qt.AlignRight | Qt.AlignVCenter,
                lds_tr("更新 ") + f"{updated}"
            )

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()

    def _draw_info_row(self, p, x, y, w, label, value, label_color, value_color):
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(label_color)
        p.drawText(
            QRectF(x, y, w * 0.45, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            label
        )

        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(value_color)
        p.drawText(
            QRectF(x + w * 0.45, y, w * 0.55, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            value
        )

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

def create_widget(cfg: WidgetConfig) -> BaseWidget:
    if cfg.type == "visualizer":
        return VisualizerWidget(cfg)

    if cfg.type == "effects_overlay":
        return EffectsOverlayWidget(cfg)

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

    if cfg.type == "weather":
        return WeatherWidget(cfg)

    if cfg.type == "html_js":
        return JSHtmlWidget(cfg)

    return SystemWidget(cfg)

class WidgetEditor(QDialog):
    def __init__(self, widget: BaseWidget, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.setWindowTitle(lds_tr("Lite Desktop Studio v1.5.6 - ウィジェット編集"))
        self.resize(520, 420)

        layout = QFormLayout(self)

        self.title = QLineEdit(widget.cfg.title)
        self.color = QLineEdit(widget.cfg.color)
        self.bg = QLineEdit(widget.cfg.bg)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(widget.cfg.font_size)
        self.mirror_reflect_enabled = QCheckBox(lds_tr("鏡面反射に含める"))
        self.mirror_reflect_enabled.setChecked(bool(getattr(widget.cfg, "mirror_reflect_enabled", True)))

        self.text = QTextEdit()
        self.text.setPlainText(widget.cfg.text)

        color_btn = QPushButton(lds_tr("🎨 色を選択"))
        color_btn.clicked.connect(self.pick_color)

        bg_btn = QPushButton(lds_tr("🖼️ 背景色を選択"))
        bg_btn.clicked.connect(self.pick_bg)

        btns = QHBoxLayout()
        save = QPushButton(lds_tr("💾 保存"))
        cancel = QPushButton(lds_tr("✖ キャンセル"))
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)

        layout.addRow(lds_tr("タイトル"), self.title)
        layout.addRow(lds_tr("アクセント色"), self.color)
        layout.addRow("", color_btn)
        layout.addRow(lds_tr("背景色"), self.bg)
        layout.addRow("", bg_btn)
        layout.addRow(lds_tr("フォントサイズ"), self.font_size)
        layout.addRow(lds_tr("鏡面反射"), self.mirror_reflect_enabled)
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
        self.widget.cfg.mirror_reflect_enabled = self.mirror_reflect_enabled.isChecked()
        self.widget.cfg.text = self.text.toPlainText()

class LiteDeskStudio(QMainWindow):
    def __init__(self, canvas):
        super().__init__()
        self.STUDIO_LIQUID_GLASS_STYLESHEET = """
            QMainWindow { background: rgba(8, 14, 24, 92); color: #FFF7F7; }
            QWidget { font-family: "Segoe UI", "Yu Gothic UI", "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"; color: #FFF7F7; background: transparent; }
            QWidget#SidePanel, QWidget#CenterPanel, QWidget#PropertyPanel, QDialog {
                background: rgba(24, 36, 54, 150); border: 1px solid rgba(255, 214, 214, 82); border-radius: 24px;
            }
            QScrollArea#PropertyScrollArea, QScrollArea#SideScrollArea { background: transparent; border: none; }
            QScrollArea#PropertyScrollArea > QWidget > QWidget, QScrollArea#SideScrollArea > QWidget > QWidget {
                background: rgba(24, 36, 54, 138); border: 1px solid rgba(255, 214, 214, 66); border-radius: 24px;
            }
            QLabel#Title { font-size: 22px; font-weight: 800; color: #FFFFFF; }
            QLabel#SectionTitle { font-size: 13px; font-weight: 800; color: #FFD0D0; margin-top: 8px; }
            QLabel#SubText, QLabel#StatusText { color: rgba(245, 232, 232, 210); font-size: 12px; }
            QPushButton, QComboBox { background: rgba(255,255,255,30); color: #FFF7F7; border: 1px solid rgba(255,210,210,92); border-radius: 15px; padding: 8px 12px; font-weight: 650; }
            QPushButton:hover, QComboBox:hover { background: rgba(255,160,160,62); border: 1px solid rgba(255,165,165,165); }
            QPushButton:pressed { background: rgba(220,120,120,96); }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView { background: rgba(30,18,24,242); color: #FFF7F7; selection-background-color: #FFB3B3; selection-color: #1F1010; border: 1px solid rgba(255,210,210,120); outline: 0; }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox { background: rgba(12,8,14,118); color: #FFFFFF; border: 1px solid rgba(255,205,205,86); border-radius: 13px; padding: 7px; selection-background-color: #EFA0A0; selection-color: #241010; }
            QTextEdit#HelpBox, QListWidget { background: rgba(16,10,16,120); color: #F8E8E8; border: 1px solid rgba(255,214,214,64); border-radius: 17px; }
            QListWidget { padding: 6px; }
            QListWidget::item { padding: 9px; border-radius: 12px; }
            QListWidget::item:selected { background: rgba(239,160,160,160); color: #1F1010; }
            QListWidget::item:hover { background: rgba(255,255,255,28); }
            QListWidget#LayerList { background: rgba(255,238,238,58); color: #FFF8F8; border: 1px solid rgba(255,220,220,118); border-radius: 18px; padding: 8px; outline: 0; }
            QListWidget#LayerList::item { background: rgba(255,255,255,28); color: #FFF8F8; border: 1px solid rgba(255,225,225,46); border-radius: 12px; padding: 9px 10px; margin: 3px 2px; }
            QListWidget#LayerList::item:hover { background: rgba(255,190,190,86); color: #FFFFFF; border: 1px solid rgba(255,220,220,130); }
            QListWidget#LayerList::item:selected, QListWidget#LayerList::item:selected:active, QListWidget#LayerList::item:selected:!active { background: rgba(255,188,188,218); color: #241010; border: 1px solid rgba(255,235,235,230); font-weight: 800; }
            QCheckBox { spacing: 8px; color: #FFF7F7; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 6px; border: 1px solid rgba(255,205,205,115); background: rgba(255,255,255,24); }
            QCheckBox::indicator:checked { background: #FFB3B3; border: 1px solid #FFE0E0; }
            QTabWidget::pane { background: rgba(12,8,16,82); border: 1px solid rgba(255,214,214,56); border-radius: 18px; top: -1px; }
            QTabBar::tab { background: rgba(255,255,255,22); color: rgba(255,240,240,220); border: 1px solid rgba(255,214,214,52); border-bottom: none; padding: 8px 14px; margin-right: 4px; border-top-left-radius: 12px; border-top-right-radius: 12px; }
            QTabBar::tab:selected { background: rgba(255,170,170,98); color: #FFFFFF; border: 1px solid rgba(255,210,210,165); }
            QScrollBar:vertical { background: transparent; width: 11px; margin: 8px 2px 8px 2px; }
            QScrollBar::handle:vertical { background: rgba(255,190,190,86); border-radius: 5px; min-height: 34px; }
        """

        
        self.STUDIO_DARK_STYLESHEET = """
            QMainWindow { background: rgba(7, 10, 16, 218); color: #FFF7F7; }
            QWidget { font-family: "Segoe UI", "Yu Gothic UI", "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"; color: #FFF7F7; background: transparent; }
            QWidget#SidePanel, QWidget#CenterPanel, QWidget#PropertyPanel, QDialog { background: rgba(13,17,24,224); border: 1px solid rgba(78,86,104,170); border-radius: 18px; }
            QScrollArea#PropertyScrollArea, QScrollArea#SideScrollArea { background: transparent; border: none; }
            QLabel#Title { font-size: 22px; font-weight: 800; color: #FFFFFF; }
            QLabel#SectionTitle { font-size: 13px; font-weight: 800; color: #FFB3B3; margin-top: 8px; }
            QLabel#SubText, QLabel#StatusText { color: #C7B0B0; font-size: 12px; }
            QPushButton, QComboBox { background: rgba(30,37,49,210); color: #FFFFFF; border: 1px solid rgba(82,92,112,190); border-radius: 12px; padding: 8px 12px; font-weight: 600; }
            QPushButton:hover, QComboBox:hover { background: rgba(48,42,46,224); border: 1px solid #FF8F8F; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView { background: rgba(14,19,28,242); color: #FFF7F7; selection-background-color: #E98686; selection-color: #FFFFFF; border: 1px solid rgba(82,92,112,190); outline: 0; }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox { background: rgba(12,17,26,214); color: #FFFFFF; border: 1px solid rgba(70,82,104,190); border-radius: 10px; padding: 7px; selection-background-color: #E98686; }
            QTextEdit#HelpBox, QListWidget { background: rgba(12,17,26,210); color: #E6D6D6; border: 1px solid rgba(58,68,86,190); border-radius: 14px; }
            QListWidget::item { padding: 9px; border-radius: 10px; }
            QListWidget::item:selected { background: #E98686; color: white; }
            QCheckBox { spacing: 8px; color: #FFF7F7; }
            QTabWidget::pane { border: 1px solid rgba(58,68,86,190); border-radius: 14px; background: rgba(14,20,30,206); }
            QTabBar::tab { background: rgba(28,36,48,210); color: #D8C8C8; border: 1px solid rgba(58,68,86,190); padding: 8px 14px; margin-right: 4px; border-top-left-radius: 10px; border-top-right-radius: 10px; }
            QTabBar::tab:selected { background: rgba(74,44,44,230); color: #FFFFFF; border: 1px solid #FF8F8F; }
            QScrollBar:vertical { background: transparent; width: 10px; margin: 8px 2px 8px 2px; }
            QScrollBar::handle:vertical { background: rgba(68,78,96,190); border-radius: 5px; min-height: 34px; }
        """

        self.STUDIO_MATERIAL_STYLESHEET = """
            QMainWindow { background: rgba(17,19,24,222); color: #FFF7F7; }
            QWidget { font-family: "Segoe UI", "Yu Gothic UI", "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"; color: #FFF7F7; background: transparent; }
            QWidget#SidePanel, QWidget#CenterPanel, QWidget#PropertyPanel, QDialog { background: rgba(27,31,39,224); border: 1px solid rgba(65,75,92,176); border-radius: 12px; }
            QLabel#Title { font-size: 22px; font-weight: 800; color: #FFFFFF; }
            QLabel#SectionTitle { font-size: 13px; font-weight: 800; color: #F2A6A6; margin-top: 8px; }
            QLabel#SubText, QLabel#StatusText { color: #CDB8B8; font-size: 12px; }
            QPushButton, QComboBox { background: rgba(42,49,61,222); color: #FFF0F0; border: 1px solid rgba(74,84,104,205); border-radius: 8px; padding: 8px 12px; font-weight: 650; }
            QPushButton:hover, QComboBox:hover { background: rgba(56,58,68,228); border: 1px solid #F2A6A6; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView { background: rgba(27,31,39,242); color: #FFF7F7; selection-background-color: #F2A6A6; selection-color: #241010; border: 1px solid #4A5468; outline: 0; }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox { background: rgba(18,22,29,218); color: #FFF7F7; border: 1px solid rgba(74,84,104,205); border-radius: 8px; padding: 7px; selection-background-color: #F2A6A6; }
            QTextEdit#HelpBox, QListWidget { background: rgba(18,22,29,214); color: #E5D4D4; border: 1px solid rgba(56,64,78,205); border-radius: 10px; }
            QListWidget::item:selected { background: #F2A6A6; color: #241010; }
            QTabWidget::pane { border: 1px solid rgba(56,64,78,205); border-radius: 10px; background: rgba(23,27,35,214); }
            QTabBar::tab { background: rgba(32,38,49,214); color: #DCCACA; border: 1px solid rgba(56,64,78,205); padding: 8px 14px; margin-right: 3px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: rgba(58,52,58,230); color: #FFFFFF; border: 1px solid #F2A6A6; }
        """

        self.STUDIO_LIGHT_STYLESHEET = """
            QMainWindow { background: rgba(232,224,226,222); color: #2D2020; }
            QWidget { font-family: "Segoe UI", "Yu Gothic UI", "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"; color: #2D2020; background: transparent; }
            QWidget#SidePanel, QWidget#CenterPanel, QWidget#PropertyPanel, QDialog { background: rgba(252,247,247,218); border: 1px solid rgba(210,181,181,200); border-radius: 18px; }
            QLabel#Title { font-size: 22px; font-weight: 800; color: #291A1A; }
            QLabel#SectionTitle { font-size: 13px; font-weight: 800; color: #B85E5E; margin-top: 8px; }
            QLabel#SubText, QLabel#StatusText { color: #755959; font-size: 12px; }
            QPushButton, QComboBox { background: rgba(248,238,238,220); color: #2D2020; border: 1px solid rgba(204,174,174,205); border-radius: 12px; padding: 8px 12px; font-weight: 650; }
            QPushButton:hover, QComboBox:hover { background: rgba(244,227,227,230); border: 1px solid #EFA0A0; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView { background: rgba(252,247,247,245); color: #2D2020; selection-background-color: #F2B6B6; selection-color: #2A1212; border: 1px solid #D8BABA; outline: 0; }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox { background: rgba(255,255,255,226); color: #2D2020; border: 1px solid rgba(219,197,197,205); border-radius: 10px; padding: 7px; selection-background-color: #F2B6B6; selection-color: #2A1212; }
            QTextEdit#HelpBox, QListWidget { background: rgba(248,242,242,222); color: #513333; border: 1px solid rgba(229,210,210,205); border-radius: 14px; }
            QListWidget::item:selected { background: #F2B6B6; color: #2A1212; }
            QTabWidget::pane { border: 1px solid rgba(229,210,210,205); border-radius: 14px; background: rgba(248,242,242,210); }
            QTabBar::tab { background: rgba(243,231,231,218); color: #684C4C; border: 1px solid rgba(229,210,210,205); padding: 8px 14px; margin-right: 4px; border-top-left-radius: 10px; border-top-right-radius: 10px; }
            QTabBar::tab:selected { background: rgba(252,247,247,232); color: #2D2020; border: 1px solid #D8BABA; }
        """
        if os.path.exists(os.path.join(os.getcwd(), 'icon.png')):
            self.setWindowIcon(QIcon(os.path.join(os.getcwd(), 'icon.png')))
        self.updating_ui = False
        self.applying_properties = False
        self.canvas = canvas
        self.updating_ui = False

        self.setWindowTitle(lds_tr("Lite Desktop Studio v1.5.6"))
        self.apply_beginner_editor_window_geometry()

        self.build_ui()
        self.apply_style()
        self.refresh_layer_list()
        self.load_selected_to_editor()

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh_runtime_status)
        self.ui_timer.start(500)

    def apply_beginner_editor_window_geometry(self):
        """Make the main widget editor larger and readable, while staying on screen.

        The previous default size was compact. This screen-aware sizing keeps the
        editor comfortable on large monitors and still safe on smaller displays.
        """
        min_w = 1180
        min_h = 780
        fallback_w = 1280
        fallback_h = 840
        try:
            self.setMinimumSize(min_w, min_h)
        except Exception:
            pass
        try:
            screen = QApplication.primaryScreen()
            if screen is None:
                raise RuntimeError("primary screen is unavailable")
            geom = screen.availableGeometry()
            target_w = min(1440, max(min_w, int(geom.width() * 0.88)))
            target_h = min(940, max(min_h, int(geom.height() * 0.88)))
            target_w = min(target_w, max(min_w, geom.width() - 40))
            target_h = min(target_h, max(min_h, geom.height() - 40))
            self.resize(target_w, target_h)
            try:
                self.move(
                    geom.x() + max(0, (geom.width() - self.width()) // 2),
                    geom.y() + max(0, (geom.height() - self.height()) // 2),
                )
            except Exception:
                pass
        except Exception:
            self.resize(fallback_w, fallback_h)

    def configure_readable_help_text(self, text_edit, min_height=180, fixed_height=None):
        """Make explanatory QTextEdit boxes easier to read for beginners."""
        try:
            text_edit.setReadOnly(True)
        except Exception:
            pass
        try:
            text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        except Exception:
            try:
                text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
            except Exception:
                pass
        try:
            text_edit.setMinimumHeight(int(min_height))
        except Exception:
            pass
        if fixed_height is not None:
            try:
                text_edit.setFixedHeight(int(fixed_height))
            except Exception:
                pass
        try:
            font = text_edit.font()
            if font.pointSize() < 11:
                font.setPointSize(11)
            text_edit.setFont(font)
        except Exception:
            pass
        try:
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        except Exception:
            pass
        return text_edit

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main = QHBoxLayout(root)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(12)

        main.addWidget(self.build_left_panel(), 0)
        main.addWidget(self.build_center_panel(), 1)
        main.addWidget(self.build_property_panel(), 0)
        self.apply_beginner_main_tooltips()

    def apply_beginner_main_tooltips(self):
        """Beginner explanations for the main widget editor controls."""
        tips = {
            "btn_add_visualizer": lds_tr("音楽に合わせて動くバー表示を追加します。まずはこのボタンで追加し、右側でサイズや色を調整します。"),
            "btn_add_effects_overlay": lds_tr("花びら・雨・月・水面などの背景演出を追加します。細かい設定は中央の『エフェクト設定』から開けます。"),
            "btn_add_system": lds_tr("CPU、メモリ、ディスク使用率を表示するウィジェットを追加します。"),
            "btn_add_volume": lds_tr("音量を表示・操作するウィジェットを追加します。"),
            "btn_add_clock": lds_tr("アナログ時計を追加します。デジタル時刻の表示は右側で切り替えできます。"),
            "btn_add_network": lds_tr("通信速度を表示するウィジェットを追加します。DOWN/UP色は右側で変更できます。"),
            "btn_add_calendar": lds_tr("カレンダーを表示するウィジェットを追加します。"),
            "btn_add_media": lds_tr("再生/一時停止など、音楽プレイヤー操作用のウィジェットを追加します。"),
            "btn_add_html_js": lds_tr("JavaScriptを含むHTMLウィジェットを追加します。初心者は通常のHTML/CSS風から始めるのがおすすめです。"),
            "btn_add_html": lds_tr("文字や簡単なHTML/CSS風デザインを表示するウィジェットを追加します。"),
            "btn_add_weather": lds_tr("天気ウィジェットを追加します。地域名は右側のプロパティで変更します。"),
            "layer_list": lds_tr("追加したウィジェットの一覧です。ここで選ぶと、右側に編集項目が表示されます。"),
            "btn_layer_down": lds_tr("選択中のウィジェットを背面に移動します。重なり順を直したい時に使います。"),
            "btn_layer_up": lds_tr("選択中のウィジェットを前面に移動します。"),
            "edit_mode_check": lds_tr("ONにすると、ウィジェットをドラッグ移動・編集できます。普段使う時はOFFにすると誤操作を防げます。"),
            "theme_combo": lds_tr("メイン設定画面の見た目テーマを切り替えます。右側の説明や色もテーマに合わせて見やすくなります。"),
            "btn_effects_editor": lds_tr("エフェクトオーバーレイの詳細設定を開きます。"),
            "btn_save": lds_tr("現在の配置と設定を保存します。"),
            "btn_reload": lds_tr("画面を再読み込みします。表示が乱れた時に使います。"),
            "btn_duplicate": lds_tr("選択中のウィジェットをコピーします。"),
            "btn_delete": lds_tr("選択中のウィジェットを削除します。削除前に選択対象を確認してください。"),
            "btn_export": lds_tr("現在の設定をファイルとして保存します。別PCへの移動やバックアップに使えます。"),
            "btn_import": lds_tr("保存済みの設定ファイルを読み込みます。"),
            "btn_close_canvas": lds_tr("アプリを終了します。終了前に保存しておくと安心です。"),
            "prop_type": lds_tr("選択中ウィジェットの種類です。ここは確認用なので編集できません。"),
            "prop_title": lds_tr("ウィジェット名です。レイヤー一覧で見分けやすい名前にできます。"),
            "prop_x": lds_tr("画面左からの位置です。ドラッグ移動でも変更できます。"),
            "prop_y": lds_tr("画面上からの位置です。ドラッグ移動でも変更できます。"),
            "prop_w": lds_tr("ウィジェットの横幅です。大きくすると表示領域が広がります。"),
            "prop_h": lds_tr("ウィジェットの高さです。"),
            "prop_color": lds_tr("文字やグラフなどのアクセント色です。ボタンから色を選ぶのがおすすめです。"),
            "prop_bg": lds_tr("背景色です。透明度と組み合わせて見た目を調整します。"),
            "prop_bg_alpha": lds_tr("背景の濃さです。0は透明、255は不透明です。"),
            "prop_font_size": lds_tr("文字の大きさです。見づらい時は少し大きくしてください。"),
            "prop_mirror_reflect_enabled": lds_tr("水面や氷面の反射に、このウィジェットを含めるかを選びます。"),
        }
        for name, tip in tips.items():
            set_beginner_tooltip(getattr(self, name, None), tip)
        for name in ("btn_save", "btn_effects_editor"):
            try:
                getattr(self, name).setObjectName("PrimaryButton")
            except Exception:
                pass
        for name in ("btn_delete", "btn_close_canvas"):
            try:
                getattr(self, name).setObjectName("DangerButton")
            except Exception:
                pass

    def build_left_panel(self):
        scroll = QScrollArea()
        scroll.setObjectName("SideScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(300)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        panel = QWidget()
        panel.setObjectName("SidePanel")
        scroll.setWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel(lds_tr("🧩 Lite Desktop Studio"))
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel(lds_tr("🪄 ウィジェットを追加して、直感的に編集できます。"))
        subtitle.setWordWrap(True)
        subtitle.setObjectName("SubText")
        layout.addWidget(subtitle)

        layout.addWidget(make_beginner_guide_label(
            lds_tr("左から追加、右で編集"),
            lds_tr("使いたい部品を追加したら、下のLayersで選択します。選んだ部品の位置・サイズ・色は右側のPropertiesで変更できます。")
        ))

        add_label = QLabel(lds_tr("➕ Add Widget"))
        add_label.setObjectName("SectionTitle")
        layout.addWidget(add_label)

        self.btn_add_visualizer = QPushButton(lds_tr("🎵 音楽ビジュアライザー"))
        self.btn_add_effects_overlay = QPushButton(lds_tr("✨ エフェクトオーバーレイ"))
        self.btn_add_system = QPushButton(lds_tr("📊 CPU / Memory / Disk"))
        self.btn_add_volume = QPushButton(lds_tr("🔊 音量操作"))
        self.btn_add_clock = QPushButton(lds_tr("🕒 アナログ時計"))
        self.btn_add_network = QPushButton(lds_tr("📡 通信状況"))
        self.btn_add_calendar = QPushButton(lds_tr("📅 カレンダー"))
        self.btn_add_media = QPushButton(lds_tr("🎧 音楽プレイヤー操作"))
        self.btn_add_html_js = QPushButton(lds_tr("🧪 JavaScript HTML"))
        self.btn_add_html = QPushButton(lds_tr("🌐 HTML / CSS 風"))
        self.btn_add_weather = QPushButton(lds_tr("🌤️ 天気"))

        self.btn_add_visualizer.clicked.connect(lambda: self.add_widget("visualizer"))
        self.btn_add_effects_overlay.clicked.connect(lambda: self.add_widget("effects_overlay"))
        self.btn_add_system.clicked.connect(lambda: self.add_widget("system"))
        self.btn_add_volume.clicked.connect(lambda: self.add_widget("volume"))
        self.btn_add_clock.clicked.connect(lambda: self.add_widget("clock"))
        self.btn_add_weather.clicked.connect(lambda: self.add_widget("weather"))
        self.btn_add_network.clicked.connect(lambda: self.add_widget("network"))
        self.btn_add_calendar.clicked.connect(lambda: self.add_widget("calendar"))
        self.btn_add_media.clicked.connect(lambda: self.add_widget("media"))
        self.btn_add_html_js.clicked.connect(lambda: self.add_widget("html_js"))
        self.btn_add_html.clicked.connect(lambda: self.add_widget("html"))


        for button in [
            self.btn_add_visualizer,
            self.btn_add_effects_overlay,
            self.btn_add_system,
            self.btn_add_volume,
            self.btn_add_clock,
            self.btn_add_calendar,
            self.btn_add_weather,
            self.btn_add_network,
            self.btn_add_media,
            self.btn_add_html_js,
            self.btn_add_html,
        ]:
            button.setMinimumHeight(36)
            layout.addWidget(button)

        layer_label = QLabel(lds_tr("📚 Layers"))
        layer_label.setObjectName("SectionTitle")
        layout.addWidget(layer_label)

        self.layer_list = QListWidget()
        self.layer_list.setObjectName("LayerList")
        self.layer_list.currentRowChanged.connect(self.on_layer_selected)
        layout.addWidget(self.layer_list, 1)

        layer_buttons = QHBoxLayout()

        self.btn_layer_down = QPushButton(lds_tr("⬇ 背面"))
        self.btn_layer_up = QPushButton(lds_tr("⬆ 前面"))

        self.btn_layer_down.clicked.connect(self.move_backward)
        self.btn_layer_up.clicked.connect(self.move_forward)

        layer_buttons.addWidget(self.btn_layer_down)
        layer_buttons.addWidget(self.btn_layer_up)

        layout.addLayout(layer_buttons)

        return scroll

    def update_language_button_text(self):
        """Update the language toggle button label."""
        try:
            lang = _lds_normalize_lang(get_litedesktopstudio_language())
            if lang.lower().startswith("en"):
                label = "🌐 Lang: English / 日本語へ切替"
            else:
                label = "🌐 Lang: 日本語 / Switch to English"
            if hasattr(self, "btn_language"):
                self.btn_language.setText(lds_tr(label))
                self.btn_language.setToolTip(lds_tr("UIの表示言語を切り替えます。英語では en_US.qm を読み込みます。"))
        except Exception:
            pass

    def _snapshot_canvas_widget_configs(self):
        """Capture widget configs before language switching."""
        snapshot = {"configs": [], "selected_index": -1, "edit_mode": None}
        try:
            widgets = list(getattr(self.canvas, "widgets", []) or [])
            selected = getattr(self.canvas, "selected", None)
            if selected in widgets:
                snapshot["selected_index"] = widgets.index(selected)
            elif hasattr(self, "layer_list") and self.layer_list is not None:
                snapshot["selected_index"] = self.layer_list.currentRow()
            snapshot["edit_mode"] = getattr(self.canvas, "edit_mode", None)
            for widget in widgets:
                cfg = widget.to_config() if hasattr(widget, "to_config") else getattr(widget, "cfg", None)
                snapshot["configs"].append(asdict(cfg) if cfg is not None else {})
        except Exception:
            pass
        return snapshot

    def _restore_canvas_widget_configs(self, snapshot):
        """Restore desktop widget configs captured before a language switch."""
        try:
            if not isinstance(snapshot, dict):
                return
            widgets = list(getattr(self.canvas, "widgets", []) or [])
            configs = list(snapshot.get("configs", []) or [])
            if len(widgets) != len(configs):
                return
            for widget, cfg_data in zip(widgets, configs):
                cfg = getattr(widget, "cfg", None)
                if cfg is None or not isinstance(cfg_data, dict):
                    continue
                for key, value in cfg_data.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, value)
                try:
                    ensure_effect_overlay_fields(cfg)
                except Exception:
                    pass
            selected_index = snapshot.get("selected_index", -1)
            try:
                selected_index = int(selected_index)
            except Exception:
                selected_index = -1
            for widget in widgets:
                try:
                    widget.selected = False
                except Exception:
                    pass
            if 0 <= selected_index < len(widgets):
                self.canvas.selected = widgets[selected_index]
                try:
                    widgets[selected_index].selected = True
                except Exception:
                    pass
                try:
                    if hasattr(self, "layer_list") and self.layer_list is not None:
                        blocked = self.layer_list.blockSignals(True)
                        self.layer_list.setCurrentRow(selected_index)
                        self.layer_list.blockSignals(blocked)
                except Exception:
                    pass
            else:
                self.canvas.selected = None
            if snapshot.get("edit_mode") is not None:
                try:
                    self.canvas.edit_mode = bool(snapshot.get("edit_mode"))
                except Exception:
                    pass
            try:
                self.canvas.update_platform_hit_mask()
            except Exception:
                pass
            try:
                self.canvas.update()
            except Exception:
                pass
        except Exception:
            pass

    def on_language_button_clicked(self):
        """Toggle language without changing desktop widget placement."""
        snapshot = self._snapshot_canvas_widget_configs()
        try:
            app = QApplication.instance()
            current = _lds_normalize_lang(get_litedesktopstudio_language())
            next_lang = "ja_JP" if current.lower().startswith("en") else "en_US"
            loaded = set_litedesktopstudio_language(app, next_lang)

            
            self._restore_canvas_widget_configs(snapshot)
            self.canvas.language = next_lang

            self.apply_language_to_existing_ui()

            
            self._restore_canvas_widget_configs(snapshot)
            self.canvas.language = next_lang

            
            try:
                self.canvas.save_config()
            except Exception:
                pass
            save_litedesktopstudio_language_preference(next_lang)

            if next_lang.lower().startswith("en") and not loaded:
                QMessageBox.warning(
                    self,
                    lds_tr("翻訳ファイル"),
                    lds_tr("en_US.qm が見つからない、または読み込めませんでした。en_US.qm を実行ファイルと同じフォルダー、または translations フォルダーに配置してください。")
                )
        except Exception as exc:
            self._restore_canvas_widget_configs(snapshot)
            QMessageBox.warning(self, lds_tr("言語切替"), lds_tr(f"言語切替に失敗しました: {exc}"))

    def _set_widget_text(self, attr_name: str, source_text: str):
        try:
            widget = getattr(self, attr_name, None)
            if widget is not None:
                widget.setText(lds_tr(source_text))
        except Exception:
            pass

    def _set_form_label_text(self, field_attr_name: str, source_text: str):
        try:
            form = getattr(self, "property_form", None)
            field = getattr(self, field_attr_name, None)
            if form is not None and field is not None:
                label = form.labelForField(field)
                if label is not None:
                    label.setText(lds_tr(source_text))
        except Exception:
            pass

    def apply_language_to_existing_ui(self):
        """Retranslate existing widgets in-place without changing layout geometry."""
        try:
            self.setWindowTitle(lds_tr("Lite Desktop Studio v1.5.6"))
            try:
                self.canvas.setWindowTitle(lds_tr(APP_NAME))
            except Exception:
                pass

            
            widget_texts = {
                "btn_add_visualizer": lds_tr("🎵 音楽ビジュアライザー"),
                "btn_add_effects_overlay": lds_tr("✨ エフェクトオーバーレイ"),
                "btn_add_system": lds_tr("📊 CPU / Memory / Disk"),
                "btn_add_volume": lds_tr("🔊 音量操作"),
                "btn_add_clock": lds_tr("🕒 アナログ時計"),
                "btn_add_network": lds_tr("📡 通信状況"),
                "btn_add_calendar": lds_tr("📅 カレンダー"),
                "btn_add_media": lds_tr("🎧 音楽プレイヤー操作"),
                "btn_add_html_js": lds_tr("🧪 JavaScript HTML"),
                "btn_add_html": lds_tr("🌐 HTML / CSS 風"),
                "btn_add_weather": lds_tr("🌤️ 天気"),
                "btn_layer_down": lds_tr("⬇ 背面"),
                "btn_layer_up": lds_tr("⬆ 前面"),
                "status_label": lds_tr("📌 Status"),
                "edit_mode_check": lds_tr("✏️ 編集モード"),
                "btn_effects_editor": lds_tr("✨ エフェクト設定"),
                "btn_save": lds_tr("💾 設定を保存"),
                "btn_reload": lds_tr("🔄 UIを再読み込み"),
                "btn_duplicate": lds_tr("📄 複製"),
                "btn_delete": lds_tr("🗑️ 削除"),
                "btn_export": lds_tr("📤 エクスポート"),
                "btn_import": lds_tr("📥 インポート"),
                "btn_close_canvas": lds_tr("🚪 アプリ終了"),
                "prop_mirror_reflect_enabled": lds_tr("🪞 このウィジェットを水面/氷面の鏡面反射に含める"),
                "btn_pick_color": lds_tr("🎯 アクセント色を選択"),
                "btn_pick_bg": lds_tr("🖼️ 背景色を選択"),
                "btn_pick_cpu_color": lds_tr("🧠 CPU色を選択"),
                "btn_pick_memory_color": lds_tr("💽 Memory色を選択"),
                "btn_pick_disk_color": lds_tr("💾 Disk色を選択"),
                "btn_pick_network_down_color": lds_tr("⬇️ DOWN色を選択"),
                "btn_pick_network_up_color": lds_tr("⬆️ UP色を選択"),
                "prop_clock_show_digital": lds_tr("🕒 デジタル時刻を表示"),
                "prop_visualizer_flip_vertical": lds_tr("↕️ ビジュアライザーを上下反転"),
                "prop_visualizer_peak_bar_enabled": lds_tr("━ スペクトルピークバーを表示"),
                "prop_visualizer_glow_enabled": lds_tr("💡 スペクトル発光を有効化"),
                "prop_visualizer_frame_rate_enabled": lds_tr("🎞️ FPS制限を使う"),
            }
            for attr_name, source_text in widget_texts.items():
                self._set_widget_text(attr_name, source_text)

            if getattr(self.canvas, "selected", None) is None:
                self._set_widget_text("selected_name", "🔎 No widget selected")

            try:
                self.prop_weather_location.setPlaceholderText(lds_tr("例: Kobe / Tokyo / Osaka"))
            except Exception:
                pass

            
            
            form_labels = {
                "prop_type": lds_tr("🧩 Type"),
                "prop_title": lds_tr("🔖 Title"),
                "prop_x": lds_tr("↔️ X"),
                "prop_y": lds_tr("↕️ Y"),
                "prop_w": lds_tr("📐 Width"),
                "prop_h": lds_tr("📏 Height"),
                "prop_color": lds_tr("🎨 Color"),
                "prop_bg": lds_tr("🖼️ Background"),
                "prop_bg_alpha": lds_tr("透明度"),
                "prop_mirror_reflect_enabled": lds_tr("鏡面反射対象"),
                "prop_cpu_color": lds_tr("🧠 CPU Color"),
                "prop_memory_color": lds_tr("💽 Memory Color"),
                "prop_disk_color": lds_tr("💾 Disk Color"),
                "prop_weather_location": lds_tr("🌍 Weather Location"),
                "prop_network_down_color": lds_tr("⬇️ Network DOWN Color"),
                "prop_network_up_color": lds_tr("⬆️ Network UP Color"),
                "prop_font_size": lds_tr("🔤 Font Size"),
                "prop_visualizer_bar_width_scale": lds_tr("📏 スペクトルバー幅"),
                "prop_visualizer_orientation": lds_tr("🧭 スペクトル展開方向"),
                "prop_visualizer_frame_rate": lds_tr("🎞️ FPS"),
            }
            for field_attr_name, source_text in form_labels.items():
                self._set_form_label_text(field_attr_name, source_text)

            self.update_language_button_text()
            try:
                self.update_studio_theme_button_text()
            except Exception:
                pass
            
            try:
                self.canvas.update()
            except Exception:
                pass
        except Exception:
            pass

    def rebuild_ui_after_language_change(self):
        """Backward-compatible wrapper.  It no longer rebuilds layouts."""
        self.apply_language_to_existing_ui()

    def open_effects_overlay_editor(self):
        widget = getattr(self.canvas, "selected", None)
        if widget is None or widget.cfg.type != "effects_overlay":
            QMessageBox.information(
                self,
                lds_tr("エフェクト設定"),
                lds_tr("Effects Overlay ウィジェットを選択してください。")
            )
            return

        dialog = EffectsOverlayEditorDialog(widget, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.canvas.save_config()
            self.canvas.update()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
            else:
                thread = Thread()
                thread.set_func(self.canvas.show)
                thread.start()
                THREADS.append(thread)
                self.canvas.update()

        super().changeEvent(event)

    def build_center_panel(self):
        panel = QWidget()
        panel.setObjectName("CenterPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()

        self.status_label = QLabel(lds_tr("📌 Status"))
        self.status_label.setObjectName("StatusText")
        top.addWidget(self.status_label, 1)

        self.edit_mode_check = QCheckBox(lds_tr("✏️ 編集モード"))
        self.edit_mode_check.setChecked(self.canvas.edit_mode)
        self.edit_mode_check.stateChanged.connect(self.on_edit_mode_changed)
        top.addWidget(self.edit_mode_check)
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumHeight(32)
        self.populate_studio_theme_combo()
        self.theme_combo.currentIndexChanged.connect(self.on_studio_theme_combo_changed)
        top.addWidget(self.theme_combo)

        self.btn_language = QPushButton()
        self.btn_language.setMinimumHeight(32)
        self.btn_language.clicked.connect(self.on_language_button_clicked)
        top.addWidget(self.btn_language)

        self.update_studio_theme_button_text()
        self.update_language_button_text()
        layout.addLayout(top)

        help_box = QTextEdit()
        help_box.setReadOnly(True)
        self.configure_readable_help_text(help_box, min_height=190, fixed_height=210)
        help_box.setObjectName("HelpBox")
        help_box.setPlainText(lds_tr("初心者向けの操作方法:\n1. 左のAdd Widgetから部品を追加します。\n2. 左のLayersで編集したい部品を選びます。\n3. 右のPropertiesで位置・サイズ・色を調整します。\n4. 編集が終わったら『設定を保存』を押します。\n補足: 編集モードONならドラッグ移動できます。Eキーで編集モード切替、Deleteキーで削除できます。"))
        layout.addWidget(help_box)
        layout.addWidget(make_beginner_guide_label(
            lds_tr("中央は操作パネルです"),
            lds_tr("保存・複製・削除・インポート/エクスポートなど、全体操作をここにまとめています。危険な操作は赤系の枠で目立つようにしています。")
        ))

        action_label = QLabel(lds_tr("⚡ Actions"))
        action_label.setObjectName("SectionTitle")
        layout.addWidget(action_label)

        action_grid = QGridLayout()
        action_grid.setSpacing(8)
        self.btn_effects_editor = QPushButton(lds_tr("✨ エフェクト設定"))
        self.btn_effects_editor.clicked.connect(self.open_effects_overlay_editor)
        layout.addWidget(self.btn_effects_editor)
        self.btn_save = QPushButton(lds_tr("💾 設定を保存"))
        self.btn_reload = QPushButton(lds_tr("🔄 UIを再読み込み"))
        self.btn_duplicate = QPushButton(lds_tr("📄 複製"))
        self.btn_delete = QPushButton(lds_tr("🗑️ 削除"))
        self.btn_export = QPushButton(lds_tr("📤 エクスポート"))
        self.btn_import = QPushButton(lds_tr("📥 インポート"))
        self.btn_close_canvas = QPushButton(lds_tr("🚪 アプリ終了"))
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

        performance_label = QLabel(lds_tr("🚀 Performance"))
        performance_label.setObjectName("SectionTitle")
        layout.addWidget(performance_label)

        self.performance_text = QTextEdit()
        self.performance_text.setReadOnly(True)
        self.configure_readable_help_text(self.performance_text, min_height=150, fixed_height=170)
        self.performance_text.setObjectName("HelpBox")
        layout.addWidget(self.performance_text)

        return panel

    def build_property_panel(self):
        scroll = QScrollArea()
        scroll.setObjectName("PropertyScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(440)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        panel = QWidget()
        panel.setObjectName("PropertyPanel")

        scroll.setWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel(lds_tr("🛠️ Properties"))
        title.setObjectName("Title")
        layout.addWidget(title)

        self.selected_name = QLabel(lds_tr("🔎 No widget selected"))
        self.selected_name.setObjectName("SubText")
        layout.addWidget(self.selected_name)

        layout.addWidget(make_beginner_guide_label(
            lds_tr("右側は選択中ウィジェットの編集"),
            lds_tr("まずはタイトル・位置・サイズ・色だけ触れば十分です。数値が分からない場合は、ウィジェットをドラッグ移動してから微調整してください。")
        ))

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
        self.prop_mirror_reflect_enabled = QCheckBox(lds_tr("🪞 このウィジェットを水面/氷面の鏡面反射に含める"))
        self.prop_mirror_reflect_enabled.stateChanged.connect(self.apply_properties_live)
        self.prop_cpu_color = QLineEdit()
        self.prop_memory_color = QLineEdit()
        self.prop_disk_color = QLineEdit()
        self.prop_color.textChanged.connect(self.apply_properties_live)
        self.prop_network_down_color = QLineEdit()
        self.prop_network_up_color = QLineEdit()
        self.prop_bg.textChanged.connect(self.apply_properties_live)
        self.prop_cpu_color.textChanged.connect(self.apply_properties_live)
        self.prop_memory_color.textChanged.connect(self.apply_properties_live)
        self.prop_disk_color.textChanged.connect(self.apply_properties_live)

        self.btn_pick_color = QPushButton(lds_tr("🎯 アクセント色を選択"))
        self.btn_pick_bg = QPushButton(lds_tr("🖼️ 背景色を選択"))

        self.btn_pick_color.clicked.connect(self.pick_color)
        self.btn_pick_bg.clicked.connect(self.pick_bg)
        self.prop_network_down_color.textChanged.connect(self.apply_properties_live)
        self.prop_network_up_color.textChanged.connect(self.apply_properties_live)
        self.btn_pick_cpu_color = QPushButton(lds_tr("🧠 CPU色を選択"))
        self.btn_pick_memory_color = QPushButton(lds_tr("💽 Memory色を選択"))
        self.btn_pick_disk_color = QPushButton(lds_tr("💾 Disk色を選択"))

        self.btn_pick_cpu_color.clicked.connect(self.pick_cpu_color)
        self.btn_pick_memory_color.clicked.connect(self.pick_memory_color)
        self.btn_pick_disk_color.clicked.connect(self.pick_disk_color)
        self.btn_pick_network_down_color = QPushButton(lds_tr("⬇️ DOWN色を選択"))
        self.btn_pick_network_up_color = QPushButton(lds_tr("⬆️ UP色を選択"))
        self.prop_font_size = QSpinBox()
        self.prop_font_size.setRange(8, 72)
        self.prop_font_size.valueChanged.connect(self.apply_properties_live)
        self.prop_clock_show_digital = QCheckBox(lds_tr("🕒 デジタル時刻を表示"))
        self.prop_clock_show_digital.stateChanged.connect(self.apply_properties_live)
        self.prop_visualizer_flip_vertical = QCheckBox(lds_tr("↕️ ビジュアライザーを上下反転"))
        self.prop_visualizer_flip_vertical.stateChanged.connect(self.apply_properties_live)
        self.prop_visualizer_peak_bar_enabled = QCheckBox(lds_tr("━ スペクトルピークバーを表示"))
        self.prop_visualizer_peak_bar_enabled.stateChanged.connect(self.apply_properties_live)
        self.prop_visualizer_glow_enabled = QCheckBox(lds_tr("💡 スペクトル発光を有効化"))
        self.prop_visualizer_glow_enabled.stateChanged.connect(self.apply_properties_live)
        self.prop_visualizer_bar_width_scale = QDoubleSpinBox()
        self.prop_visualizer_bar_width_scale.setRange(0.35, 2.40)
        self.prop_visualizer_bar_width_scale.setDecimals(2)
        self.prop_visualizer_bar_width_scale.setSingleStep(0.05)
        self.prop_visualizer_bar_width_scale.valueChanged.connect(self.apply_properties_live)
        self.prop_visualizer_orientation = QComboBox()
        self.prop_visualizer_orientation.addItem(lds_tr("横向きに展開"), "horizontal")
        self.prop_visualizer_orientation.addItem(lds_tr("縦向きに展開"), "vertical")
        self.prop_visualizer_orientation.currentIndexChanged.connect(self.apply_properties_live)
        self.prop_visualizer_frame_rate_enabled = QCheckBox(lds_tr("🎞️ FPS制限を使う"))
        self.prop_visualizer_frame_rate_enabled.stateChanged.connect(self.apply_properties_live)
        self.prop_visualizer_frame_rate = QSpinBox()
        self.prop_visualizer_frame_rate.setRange(1, 500)
        self.prop_visualizer_frame_rate.valueChanged.connect(self.apply_properties_live)
        self.btn_pick_network_down_color.clicked.connect(self.pick_network_down_color)
        self.btn_pick_network_up_color.clicked.connect(self.pick_network_up_color)
        self.prop_weather_location = QLineEdit()
        self.prop_weather_location.setPlaceholderText(lds_tr("例: Kobe / Tokyo / Osaka"))
        self.prop_weather_location.textChanged.connect(self.apply_properties_live)

        form.addRow("🧩 Type", self.prop_type)
        form.addRow("🔖 Title", self.prop_title)
        form.addRow("↔️ X", self.prop_x)
        form.addRow("↕️ Y", self.prop_y)
        form.addRow("📐 Width", self.prop_w)
        form.addRow("📏 Height", self.prop_h)
        form.addRow("🎨 Color", self.prop_color)
        form.addRow("", self.btn_pick_color)
        form.addRow("🖼️ Background", self.prop_bg)
        form.addRow("", self.btn_pick_bg)
        form.addRow(lds_tr("透明度"), self.prop_bg_alpha)
        form.addRow(lds_tr("鏡面反射対象"), self.prop_mirror_reflect_enabled)
        form.addRow("🧠 CPU Color", self.prop_cpu_color)
        form.addRow("", self.btn_pick_cpu_color)

        form.addRow("💽 Memory Color", self.prop_memory_color)
        form.addRow("", self.btn_pick_memory_color)

        form.addRow("💾 Disk Color", self.prop_disk_color)
        form.addRow("", self.btn_pick_disk_color)
        form.addRow("🌍 Weather Location", self.prop_weather_location)
        form.addRow("⬇️ Network DOWN Color", self.prop_network_down_color)
        form.addRow("", self.btn_pick_network_down_color)
        form.addRow("⬆️ Network UP Color", self.prop_network_up_color)
        form.addRow("", self.btn_pick_network_up_color)

        self.network_only_property_widgets = [
            self.prop_network_down_color,
            self.btn_pick_network_down_color,
            self.prop_network_up_color,
            self.btn_pick_network_up_color,
        ]

        self.weather_only_property_widgets = [
            self.prop_weather_location,
        ]

        self.system_only_property_widgets = [
            self.prop_cpu_color,
            self.btn_pick_cpu_color,
            self.prop_memory_color,
            self.btn_pick_memory_color,
            self.prop_disk_color,
            self.btn_pick_disk_color,
        ]
        form.addRow("🔤 Font Size", self.prop_font_size)
        form.addRow("", self.prop_clock_show_digital)
        form.addRow("", self.prop_visualizer_flip_vertical)
        form.addRow("", self.prop_visualizer_peak_bar_enabled)
        form.addRow("", self.prop_visualizer_glow_enabled)
        form.addRow(lds_tr("📏 スペクトルバー幅"), self.prop_visualizer_bar_width_scale)
        form.addRow(lds_tr("🧭 スペクトル展開方向"), self.prop_visualizer_orientation)
        form.addRow("", self.prop_visualizer_frame_rate_enabled)
        form.addRow("🎞️ FPS", self.prop_visualizer_frame_rate)
        self.visualizer_only_property_widgets = [
            self.prop_visualizer_flip_vertical,
            self.prop_visualizer_peak_bar_enabled,
            self.prop_visualizer_glow_enabled,
            self.prop_visualizer_bar_width_scale,
            self.prop_visualizer_orientation,
            self.prop_visualizer_frame_rate_enabled,
            self.prop_visualizer_frame_rate,
        ]

        self.clock_only_property_widgets = [
            self.prop_clock_show_digital,
        ]

        layout.addLayout(form)

        html_label = QLabel(lds_tr("🧾 HTML / Text"))
        html_label.setObjectName("SectionTitle")
        layout.addWidget(html_label)

        self.prop_text = QTextEdit()
        self.prop_text.setPlaceholderText(
            "<h2 style='color:#5BE7FF;'>Custom Widget</h2>\n"
            "<p style='color:white;'>{}</p>".format(lds_tr("ここにHTML風テキストを書けます。"))
        )
        self.prop_text.textChanged.connect(self.apply_properties_live)
        layout.addWidget(self.prop_text, 1)

        bottom = QHBoxLayout()

        self.btn_apply = QPushButton(lds_tr("✅ 反映"))
        self.btn_reset_selection = QPushButton(lds_tr("🧹 選択解除"))

        self.btn_apply.clicked.connect(lambda: self.apply_properties(save=True))
        self.btn_reset_selection.clicked.connect(self.clear_selection)

        bottom.addWidget(self.btn_apply)
        bottom.addWidget(self.btn_reset_selection)

        layout.addLayout(bottom)
        self.set_system_color_controls_visible(False)
        self.set_clock_controls_visible(False)
        self.set_visualizer_controls_visible(False)

        return scroll

    def set_network_controls_visible(self, visible: bool):
        widgets = getattr(self, "network_only_property_widgets", [])

        for widget in widgets:
            widget.setVisible(visible)

            try:
                label = self.property_form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)
            except Exception:
                pass

    def pick_network_down_color(self):
        current = QColor(self.prop_network_down_color.text() or DEFAULT_NETWORK_DOWN_COLOR)
        color = QColorDialog.getColor(current, self, "DOWN色を選択")

        if color.isValid():
            self.prop_network_down_color.blockSignals(True)
            self.prop_network_down_color.setText(color.name())
            self.prop_network_down_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_network_up_color(self):
        current = QColor(self.prop_network_up_color.text() or DEFAULT_NETWORK_UP_COLOR)
        color = QColorDialog.getColor(current, self, "UP色を選択")

        if color.isValid():
            self.prop_network_up_color.blockSignals(True)
            self.prop_network_up_color.setText(color.name())
            self.prop_network_up_color.blockSignals(False)
            self.apply_properties(save=True)

    def set_weather_controls_visible(self, visible: bool):
        widgets = getattr(self, "weather_only_property_widgets", [])

        for widget in widgets:
            widget.setVisible(visible)

            try:
                label = self.property_form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)
            except Exception:
                pass

    def set_visualizer_controls_visible(self, visible: bool):
        widgets = getattr(self, "visualizer_only_property_widgets", [])

        for widget in widgets:
            widget.setVisible(visible)

            try:
                label = self.property_form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)
            except Exception:
                pass

    def set_clock_controls_visible(self, visible: bool):
        widgets = getattr(self, "clock_only_property_widgets", [])

        for widget in widgets:
            widget.setVisible(visible)

            try:
                label = self.property_form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)
            except Exception:
                pass

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

    def apply_lightweight_rose_petal_preset(self):
        widget = getattr(self.canvas, "selected", None)
        if widget is None or widget.cfg.type != "effects_overlay":
            QMessageBox.information(
                self,
                lds_tr("エフェクト設定"),
                lds_tr("Effects Overlay ウィジェットを選択してください。")
            )
            return

        widget.cfg.effects_json = json.dumps(LIGHTWEIGHT_ROSE_PETAL_DEFAULT_SETTINGS, ensure_ascii=False)

        try:
            widget._particles.clear()
            widget._rain.clear()
            widget._ripples.clear()
            widget._rose_petals.clear()
            widget._rose_flowers.clear()
            widget._blooming_roses.clear()
            widget._sakura_petals.clear()
        except Exception:
            pass

        self.canvas.save_config()
        self.canvas.update()

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
                reflect_mark = "" if bool(getattr(cfg, "mirror_reflect_enabled", True)) else " 🪞OFF"
                name = f"{i + 1}. {cfg.title} [{cfg.type}]{reflect_mark}"
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
            getattr(self, "prop_mirror_reflect_enabled", None),
            getattr(self, "prop_clock_show_digital", None),
            getattr(self, "prop_visualizer_flip_vertical", None),
            getattr(self, "prop_visualizer_peak_bar_enabled", None),
            getattr(self, "prop_visualizer_glow_enabled", None),
            getattr(self, "prop_visualizer_bar_width_scale", None),
            getattr(self, "prop_visualizer_orientation", None),
            getattr(self, "prop_visualizer_frame_rate_enabled", None),
            getattr(self, "prop_visualizer_frame_rate", None),
            getattr(self, "prop_network_down_color", None),
            getattr(self, "prop_network_up_color", None),
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
                self.prop_mirror_reflect_enabled.setChecked(True)
                self.prop_clock_show_digital.setChecked(True)
                self.set_clock_controls_visible(False)
                self.prop_visualizer_flip_vertical.setChecked(False)
                self.prop_visualizer_peak_bar_enabled.setChecked(True)
                self.prop_visualizer_glow_enabled.setChecked(True)
                self.prop_visualizer_bar_width_scale.setValue(1.0)
                self.prop_visualizer_orientation.setCurrentIndex(0)
                self.prop_visualizer_frame_rate_enabled.setChecked(True)
                self.prop_visualizer_frame_rate.setValue(60)
                self.set_visualizer_controls_visible(False)
                self.set_weather_controls_visible(False)
                self.prop_network_down_color.setText("")
                self.prop_network_up_color.setText("")
                self.set_network_controls_visible(False)

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
            self.prop_mirror_reflect_enabled.setChecked(bool(getattr(cfg, "mirror_reflect_enabled", True)))
            self.prop_font_size.setValue(cfg.font_size)
            self.prop_text.setPlainText(cfg.text or "")
            is_clock_widget = cfg.type == "clock"
            self.set_clock_controls_visible(is_clock_widget)
            is_visualizer_widget = cfg.type == "visualizer"
            self.set_visualizer_controls_visible(is_visualizer_widget)
            self.set_weather_controls_visible(cfg.type == "weather")
            is_network_widget = cfg.type == "network"
            self.set_network_controls_visible(is_network_widget)

            if cfg.type == "network":
                self.prop_network_down_color.setText(getattr(cfg, "network_down_color", "#5BE7FF"))
                self.prop_network_up_color.setText(getattr(cfg, "network_up_color", "#80FF9F"))
            else:
                self.prop_network_down_color.setText("")
                self.prop_network_up_color.setText("")

            if cfg.type == "weather":
                self.prop_weather_location.setText(getattr(cfg, "weather_location", ""))
            else:
                self.prop_weather_location.setText("")

            if cfg.type == "visualizer":
                self.prop_visualizer_flip_vertical.setChecked(
                    bool(getattr(cfg, "visualizer_flip_vertical", False))
                )
                self.prop_visualizer_peak_bar_enabled.setChecked(
                    bool(getattr(cfg, "visualizer_peak_bar_enabled", True))
                )
                self.prop_visualizer_glow_enabled.setChecked(
                    bool(getattr(cfg, "visualizer_glow_enabled", True))
                )
                try:
                    self.prop_visualizer_bar_width_scale.setValue(max(0.35, min(2.40, float(getattr(cfg, "visualizer_bar_width_scale", 1.0)))))
                except Exception:
                    self.prop_visualizer_bar_width_scale.setValue(1.0)
                orientation = str(getattr(cfg, "visualizer_orientation", "horizontal") or "horizontal").lower()
                idx = self.prop_visualizer_orientation.findData("vertical" if orientation == "vertical" else "horizontal")
                self.prop_visualizer_orientation.setCurrentIndex(max(0, idx))
                self.prop_visualizer_frame_rate_enabled.setChecked(bool(getattr(cfg, "visualizer_frame_rate_enabled", True)))
                self.prop_visualizer_frame_rate.setValue(max(1, min(240, int(getattr(cfg, "visualizer_frame_rate", 60)))))
            else:
                self.prop_visualizer_flip_vertical.setChecked(False)
                self.prop_visualizer_peak_bar_enabled.setChecked(True)
                self.prop_visualizer_glow_enabled.setChecked(True)
                self.prop_visualizer_bar_width_scale.setValue(1.0)
                self.prop_visualizer_orientation.setCurrentIndex(0)

            if cfg.type == "clock":
                self.prop_clock_show_digital.setChecked(
                    bool(getattr(cfg, "clock_show_digital", True))
                )
            else:
                self.prop_clock_show_digital.setChecked(True)

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
            self.prop_mirror_reflect_enabled,
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
            self.prop_clock_show_digital,
            self.prop_visualizer_flip_vertical,
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
            "prop_mirror_reflect_enabled",
            "prop_font_size",
            "prop_text",
            "prop_cpu_color",
            "prop_memory_color",
            "prop_disk_color",
            "prop_clock_show_digital",
            "prop_visualizer_flip_vertical",
            "prop_visualizer_peak_bar_enabled",
            "prop_visualizer_glow_enabled",
            "prop_visualizer_bar_width_scale",
            "prop_visualizer_orientation",
            "prop_visualizer_frame_rate_enabled",
            "prop_visualizer_frame_rate",
            "prop_network_down_color",
            "prop_network_up_color",

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
            self.canvas.update_platform_hit_mask()
            cfg.color = color_text
            cfg.bg = bg_text
            cfg.bg_alpha = self.prop_bg_alpha.value()
            cfg.mirror_reflect_enabled = self.prop_mirror_reflect_enabled.isChecked()
            cfg.font_size = font_size
            cfg.text = self.prop_text.toPlainText()

            if cfg.type == "html_js" and not cfg.text:
                self.prop_text.setPlainText(DEFAULT_JS_HTML)
            else:
                self.prop_text.setPlainText(cfg.text or "")

            if cfg.type == "weather":
                cfg.weather_location = self.prop_weather_location.text().strip()

            if cfg.type == "clock":
                cfg.clock_show_digital = self.prop_clock_show_digital.isChecked()

            if cfg.type == "visualizer":
                cfg.visualizer_flip_vertical = self.prop_visualizer_flip_vertical.isChecked()
                cfg.visualizer_peak_bar_enabled = self.prop_visualizer_peak_bar_enabled.isChecked()
                cfg.visualizer_glow_enabled = self.prop_visualizer_glow_enabled.isChecked()
                cfg.visualizer_bar_width_scale = self.prop_visualizer_bar_width_scale.value()
                cfg.visualizer_orientation = self.prop_visualizer_orientation.currentData() or "horizontal"
                cfg.visualizer_frame_rate_enabled = self.prop_visualizer_frame_rate_enabled.isChecked()
                cfg.visualizer_frame_rate = max(1, min(240, self.prop_visualizer_frame_rate.value()))
                if hasattr(widget, "_visualizer_frame_cache"):
                    widget._visualizer_frame_cache = None
                    widget._visualizer_frame_cache_key = None

            if cfg.type == "network":
                cfg.network_down_color = self.prop_network_down_color.text().strip() or "#5BE7FF"
                cfg.network_up_color = self.prop_network_up_color.text().strip() or "#80FF9F"

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
        color = QColorDialog.getColor(current, self, lds_tr("CPU色を選択"))

        if color.isValid():
            self.prop_cpu_color.blockSignals(True)
            self.prop_cpu_color.setText(color.name())
            self.prop_cpu_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_memory_color(self):
        current = QColor(self.prop_memory_color.text() or "#B388FF")
        color = QColorDialog.getColor(current, self, lds_tr("Memory色を選択"))

        if color.isValid():
            self.prop_memory_color.blockSignals(True)
            self.prop_memory_color.setText(color.name())
            self.prop_memory_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_disk_color(self):
        current = QColor(self.prop_disk_color.text() or "#80FF9F")
        color = QColorDialog.getColor(current, self, lds_tr("Disk色を選択"))

        if color.isValid():
            self.prop_disk_color.blockSignals(True)
            self.prop_disk_color.setText(color.name())
            self.prop_disk_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_color(self):
        current = QColor(self.prop_color.text() or "#5BE7FF")
        color = QColorDialog.getColor(current, self, lds_tr("アクセント色を選択"))

        if color.isValid():
            self.prop_color.blockSignals(True)
            self.prop_color.setText(color.name())
            self.prop_color.blockSignals(False)
            self.apply_properties(save=True)

    def pick_bg(self):
        current = QColor(self.prop_bg.text() or "#10141C")
        color = QColorDialog.getColor(current, self, lds_tr("背景色を選択"))

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
        QMessageBox.information(self, lds_tr("保存"), lds_tr("設定を保存しました。"))

    def reload_ui(self):
        self.refresh_layer_list()
        self.load_selected_to_editor()
        self.refresh_runtime_status()

    def export_config(self):
        if getattr(self, "exporting_config", False):
            return

        self.exporting_config = True

        try:
            dialog = QFileDialog(self, lds_tr("設定をエクスポート"))
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setNameFilter("JSON Files (*.json)")
            dialog.setDefaultSuffix("json")
            dialog.selectFile("litedesk_config.json")
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

            
            try:
                dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            except AttributeError:
                dialog.setOption(QFileDialog.DontUseNativeDialog, True)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            files = dialog.selectedFiles()
            if not files:
                return

            path = files[0]
            if not path:
                return

            if not path.lower().endswith(".json"):
                path += ".json"

            self.canvas.export_config_to(path)
            QMessageBox.information(self, lds_tr("エクスポート"), lds_tr("設定を書き出しました。"))

        except Exception as e:
            QMessageBox.warning(self, lds_tr("エラー"), str(e))

        finally:
            self.exporting_config = False

    def import_config(self):
        if getattr(self, "importing_config", False):
            return

        self.importing_config = True

        try:
            dialog = QFileDialog(self, lds_tr("設定をインポート"))
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilter("JSON Files (*.json)")
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

            
            try:
                dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            except AttributeError:
                dialog.setOption(QFileDialog.DontUseNativeDialog, True)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            files = dialog.selectedFiles()
            if not files:
                return

            path = files[0]
            if not path:
                return

            self.canvas.import_config_from(path)
            self.refresh_layer_list()
            self.load_selected_to_editor()
            QMessageBox.information(self, lds_tr("インポート"), lds_tr("設定を読み込みました。"))

        except Exception as e:
            QMessageBox.warning(self, lds_tr("エラー"), str(e))

        finally:
            self.importing_config = False

    def on_edit_mode_changed(self, state=None):
        self.canvas.edit_mode = self.edit_mode_check.isChecked()

        if not self.canvas.edit_mode:
            for widget in self.canvas.widgets:
                widget.selected = False

            self.canvas.selected = None
            self.canvas.dragging = False

        self.canvas.update_platform_hit_mask()
        self.canvas.update()
        self.refresh_layer_list()
        self.load_selected_to_editor()

    def refresh_runtime_status(self):
        audio_name = getattr(self.canvas.audio, "backend_name", "unknown")
        audio_mode = "fallback" if self.canvas.audio.use_fake else audio_name

        volume = "OK" if self.canvas.volume.available else "unavailable"
        theme = "Dark" if self.canvas.dark_mode else "Light"

        self.status_label.setText(
            f"Theme: {theme} | Lite Desktop Studio v1.5.6 を使用しています。"
        )

        self.performance_text.setPlainText(
            "lightened state:\n"
            f"・Widget count: {len(self.canvas.widgets)}\n"
            "・Renderer: QPainter direct rendering\n"
            "・Audio analysis: background thread\n"
            "・Config save: JSON"
        )

    def apply_studio_theme_stylesheet(self, studio, theme):
        theme = normalize_studio_theme(theme)
        stylesheet_map = {
            STUDIO_THEME_LIQUID_GLASS: self.STUDIO_LIQUID_GLASS_STYLESHEET,
            STUDIO_THEME_DARK: self.STUDIO_DARK_STYLESHEET,
            STUDIO_THEME_MATERIAL: self.STUDIO_MATERIAL_STYLESHEET,
            STUDIO_THEME_LIGHT: self.STUDIO_LIGHT_STYLESHEET,
        }
        stylesheet = stylesheet_map.get(theme, self.STUDIO_LIQUID_GLASS_STYLESHEET)
        try:
            stylesheet += "\n" + build_beginner_photoshop_main_qss(theme)
        except Exception:
            pass
        studio.setStyleSheet(stylesheet)

    def apply_window_opacity(self):
        try:
            theme = get_canvas_studio_theme(self.canvas)
            self.setWindowOpacity(get_studio_window_opacity(theme))
        except Exception:
            try:
                self.setWindowOpacity(0.92)
            except Exception:
                pass

    def apply_style(self):
        theme = get_canvas_studio_theme(self.canvas)
        self.apply_studio_theme_stylesheet(self, theme)
        self.apply_window_opacity()
        self.update_studio_theme_button_text()

    def init_studio_theme_button(self, parent_layout):
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumHeight(32)
        self.populate_studio_theme_combo()
        self.theme_combo.currentIndexChanged.connect(self.on_studio_theme_combo_changed)
        parent_layout.addWidget(self.theme_combo)
        self.update_studio_theme_button_text()

    def populate_studio_theme_combo(self):
        if not hasattr(self, "theme_combo"):
            return
        self.theme_combo.blockSignals(True)
        try:
            self.theme_combo.clear()
            for theme in STUDIO_THEME_ORDER:
                self.theme_combo.addItem(get_studio_theme_label(theme), theme)
        finally:
            self.theme_combo.blockSignals(False)

    def update_studio_theme_button_text(self):
        if not hasattr(self, "theme_combo"):
            return
        theme = get_canvas_studio_theme(self.canvas)
        self.theme_combo.blockSignals(True)
        try:
            index = self.theme_combo.findData(theme)
            if index < 0:
                self.populate_studio_theme_combo()
                index = self.theme_combo.findData(theme)
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)
        finally:
            self.theme_combo.blockSignals(False)

    def on_studio_theme_combo_changed(self, index):
        if not hasattr(self, "theme_combo"):
            return
        theme = self.theme_combo.itemData(index)
        if not theme:
            return
        set_canvas_studio_theme(self.canvas, theme)
        self.apply_style()
        try:
            self.canvas.save_config()
        except Exception:
            pass

    def toggle_studio_theme(self):
        current = get_canvas_studio_theme(self.canvas)
        next_theme = get_next_studio_theme(current)
        set_canvas_studio_theme(self.canvas, next_theme)
        self.apply_style()
        try:
            self.canvas.save_config()
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            if hasattr(self, "ui_timer") and self.ui_timer is not None:
                self.ui_timer.stop()
        except Exception:
            pass

        try:
            if hasattr(self, "canvas") and self.canvas is not None:
                self.canvas.show_canvas_after_studio_if_needed()
        except Exception:
            pass

        event.accept()

class DesktopCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.studio_theme = DEFAULT_STUDIO_THEME
        self.language = _lds_normalize_lang(get_litedesktopstudio_language())
        self.volume_sliding = False
        self.setWindowTitle(lds_tr(APP_NAME))
        self.setProperty("effectGpuStatus", effect_gpu_status_text())
        self.setProperty("effectFrameIntervalMs", self._effective_effect_frame_interval_ms() if hasattr(self, "_effective_effect_frame_interval_ms") else 16)
        self.setMouseTracking(True)
        self.js_html_views = JSHtmlViewManager(self)
        choose_canvas_window_flags(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        create_runtime_controllers(self)
        self.weather = WeatherEngine()
        self.weather.start()
        self.widgets: List[BaseWidget] = []
        self.selected: Optional[BaseWidget] = None
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.dragging_effect_moon = False
        self.effect_moon_drag_offset = QPointF(0.0, 0.0)
        self.dragging_effect_sun = False
        self.dragging_effect_ice = False
        self.effect_sun_drag_offset = QPointF(0.0, 0.0)
        self.effect_sun_drag_kind = "sun"
        self.edit_mode = False
        self.last_right_click_time = 0.0
        self.last_right_click_widget = None
        self.right_double_click_interval = QApplication.doubleClickInterval() / 1000.0
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.on_frame)
        self.render_timer.start(self._effective_effect_frame_interval_ms())

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.check_theme)
        self.theme_timer.start(1500)

        self.dark_mode = WindowsTheme.is_dark_mode()

        self.load_config()
        try:
            self.audio.start()
        except Exception:
            pass
        self.update_platform_hit_mask()

    def _effective_effect_frame_interval_ms(self) -> int:
        """Return the current canvas timer interval from enabled effect FPS settings.

        The canvas is painted as a single transparent window, so the safest way to
        control effect FPS without OpenGL is to throttle the shared render timer.
        When multiple effect overlays have FPS limits, the lowest enabled FPS is
        used to reduce load consistently.
        """
        fps_values = []
        try:
            for widget in getattr(self, "widgets", []):
                if isinstance(widget, EffectsOverlayWidget):
                    settings = get_effect_overlay_settings(widget.cfg)
                    if bool(getattr(settings, "effect_frame_rate_enabled", True)):
                        fps_values.append(max(1, min(240, int(getattr(settings, "effect_frame_rate", 60)))))
                elif isinstance(widget, VisualizerWidget):
                    if bool(getattr(widget.cfg, "visualizer_frame_rate_enabled", True)):
                        fps_values.append(max(1, min(240, int(getattr(widget.cfg, "visualizer_frame_rate", 60)))))
        except Exception:
            fps_values = []
        fps = min(fps_values) if fps_values else 60
        return max(4, int(round(1000.0 / max(1, fps))))

    def notify_effect_widgets_mouse_move(self, pos):
        for widget in self.widgets:
            if isinstance(widget, EffectsOverlayWidget):
                widget.on_mouse_move(pos)

    def notify_effect_widgets_mouse_press(self, pos):
        for widget in self.widgets:
            if isinstance(widget, EffectsOverlayWidget):
                widget.on_mouse_press(pos)

    def notify_effect_widgets_mouse_release(self, pos):
        for widget in self.widgets:
            if isinstance(widget, EffectsOverlayWidget):
                widget.on_mouse_release(pos)

    def should_widget_reflect_in_mirrors(self, widget) -> bool:
        """Return True when an individual widget is allowed to appear in water/ice mirror reflections."""
        try:
            if widget is None or not hasattr(widget, "cfg"):
                return False
            
            
            if isinstance(widget, EffectsOverlayWidget):
                return False
            if hasattr(widget, "reflects_in_mirrors"):
                return bool(widget.reflects_in_mirrors())
            return bool(getattr(widget.cfg, "mirror_reflect_enabled", True))
        except Exception:
            return False

    def update_platform_hit_mask(self):
        if is_windows():
            try:
                self.clearMask()
            except Exception:
                pass
            return

        try:
            region = QRegion()
            margin = 8 if getattr(self, "edit_mode", True) else 2

            for widget in self.widgets:
                try:
                    hit_rect = widget.interaction_rect() if hasattr(widget, "interaction_rect") else widget.rect
                    rect = hit_rect.toAlignedRect()
                except Exception:
                    rect = QRect(
                        int(widget.cfg.x),
                        int(widget.cfg.y),
                        int(widget.cfg.w),
                        int(widget.cfg.h)
                    )

                rect = rect.adjusted(
                    -margin,
                    -margin,
                    margin,
                    margin
                )

                region = region.united(QRegion(rect))

            if region.isEmpty():
                self.setMask(QRegion(QRect(0, 0, 1, 1)))
            else:
                self.setMask(region)

        except Exception as e:
            print("[DesktopCanvas] update_platform_hit_mask failed:", repr(e))

    def hide_canvas_for_studio_if_needed(self):
        if is_windows():
            return
        try:
            if hasattr(self, "js_html_views"):
                self.js_html_views.set_visible(False)
        except Exception:
            pass

        try:
            self.hide()
        except Exception:
            pass

    def show_canvas_after_studio_if_needed(self):
        if is_windows():
            return
        try:
            self.show()
            self.raise_()
            self.update_platform_hit_mask()
            self.update()
        except Exception:
            pass
        try:
            if hasattr(self, "js_html_views"):
                self.js_html_views.set_visible(True)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)

        try:
            self.update_platform_hit_mask()
        except Exception:
            pass

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

        self.hide_canvas_for_studio_if_needed()

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
            self.update_platform_hit_mask()
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
            clock_show_digital=getattr(old, "clock_show_digital", True),
            visualizer_flip_vertical=getattr(old, "visualizer_flip_vertical", False),
            visualizer_peak_bar_enabled=getattr(old, "visualizer_peak_bar_enabled", True),
            visualizer_glow_enabled=getattr(old, "visualizer_glow_enabled", True),
            visualizer_bar_width_scale=getattr(old, "visualizer_bar_width_scale", 1.0),
            visualizer_orientation=getattr(old, "visualizer_orientation", "horizontal"),
            effects_json=getattr(old, "effects_json", "{}"),
            effects_follow_mouse=getattr(old, "effects_follow_mouse", True),
            weather_location=getattr(old, "weather_location", ""),
            network_down_color=getattr(old, "network_down_color", DEFAULT_NETWORK_DOWN_COLOR),
            network_up_color=getattr(old, "network_up_color", DEFAULT_NETWORK_UP_COLOR),
        )

        widget = create_widget(cfg)
        self.widgets.append(widget)

        for w in self.widgets:
            w.selected = False

        self.selected = widget
        widget.selected = True

        self.save_config()
        self.update_platform_hit_mask()
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
            "studio_theme": get_canvas_studio_theme(self),
            LDS_LANGUAGE_CONFIG_KEY: _lds_normalize_lang(getattr(self, "language", get_litedesktopstudio_language())),
            "widgets": [asdict(w.to_config()) for w in self.widgets]
        }

        tmp_path = path + ".tmp"

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, path)

    def import_config_from(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.widgets = []
        self.selected = None

        for item in data.get("widgets", []):
            cfg = widget_config_from_dict(item)
            self.widgets.append(create_widget(cfg))

        self.save_config()
        self.update_platform_hit_mask()
        self.update()

    def check_theme(self):
        now_dark = WindowsTheme.is_dark_mode()
        if now_dark != self.dark_mode:
            self.dark_mode = now_dark
            self.update()

    def on_frame(self):
        try:
            interval = self._effective_effect_frame_interval_ms()
            if self.render_timer.interval() != interval:
                self.render_timer.setInterval(interval)
            self.setProperty("effectFrameIntervalMs", interval)
        except Exception:
            pass
        self.js_html_views.sync(self.widgets)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        ctx = {
            "audio": self.audio,
            "monitor": self.monitor,
            "volume": self.volume,
            "media": self.media,
            "media_meta": getattr(self, "media_meta", None),
            "weather": getattr(self, "weather", None),
            "dark": self.dark_mode,
            "edit_mode": self.edit_mode,
        }

        reflection_source_image = None
        try:
            needs_reflection_source = False
            for w in self.widgets:
                if isinstance(w, EffectsOverlayWidget):
                    s = get_effect_overlay_settings(w.cfg)
                    if (
                        bool(getattr(s, "water_surface_enabled", False))
                        and bool(getattr(s, "water_mirror_enabled", False))
                        and bool(getattr(s, "water_mirror_reflect_widgets_enabled", True))
                    ) or (
                        bool(getattr(s, "ice_enabled", False))
                        and bool(getattr(s, "ice_mirror_enabled", True))
                        and bool(getattr(s, "ice_reflect_widgets_enabled", True))
                    ):
                        needs_reflection_source = True
                        break
            if needs_reflection_source:
                reflection_source_image = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
                reflection_source_image.fill(Qt.GlobalColor.transparent)
                rp = QPainter(reflection_source_image)
                rp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                source_ctx = dict(ctx)
                source_ctx["reflection_source_image"] = None
                for src_w in self.widgets:
                    if self.should_widget_reflect_in_mirrors(src_w):
                        src_w.paint(rp, source_ctx)
                rp.end()
        except Exception:
            reflection_source_image = None
        ctx["reflection_source_image"] = reflection_source_image

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
            self.notify_effect_widgets_mouse_press(pos)
            clicked_widget = None

            for widget in reversed(self.widgets):
                if widget.contains(pos):
                    clicked_widget = widget
                    break

            for widget in self.widgets:
                widget.selected = False

            self.selected = None
            self.dragging = False
            self.dragging_effect_moon = False
            self.dragging_effect_sun = False
            self.dragging_effect_ice = False
            self.dragging_effect_puddle = False
            self.dragging_effect_puddle_resize = False
            self.effect_puddle_drag_index = None
            self.effect_puddle_resize_kind = "corner"
            self.effect_sun_drag_kind = "sun"
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

                        if hasattr(self, "media_meta"):
                            self.media_meta.force_refresh()

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
                        if isinstance(clicked_widget, EffectsOverlayWidget):
                            sun_kind = clicked_widget.sun_effect_hit_kind(pos)
                            resize_index, resize_kind = clicked_widget.puddle_resize_hit_kind(pos)
                            if sun_kind is not None:
                                self.dragging_effect_sun = True
                                self.effect_sun_drag_kind = sun_kind
                                self.effect_sun_drag_offset = clicked_widget.sun_drag_offset_from_pos(pos)
                                self.dragging_effect_moon = False
                                self.dragging_effect_ice = False
                                self.dragging_effect_puddle = False
                                self.dragging_effect_puddle_resize = False
                            elif clicked_widget.is_moon_hit(pos):
                                self.dragging_effect_moon = True
                                self.effect_moon_drag_offset = clicked_widget.moon_drag_offset_from_pos(pos)
                                self.dragging_effect_sun = False
                                self.dragging_effect_ice = False
                                self.dragging_effect_puddle = False
                                self.dragging_effect_puddle_resize = False
                            elif clicked_widget.is_ice_hit(pos):
                                self.dragging_effect_ice = True
                                self.effect_ice_drag_offset = clicked_widget.ice_drag_offset_from_pos(pos)
                                self.dragging_effect_sun = False
                                self.dragging_effect_moon = False
                                self.dragging_effect_puddle = False
                                self.dragging_effect_puddle_resize = False
                            elif resize_index is not None:
                                self.dragging_effect_puddle_resize = True
                                self.effect_puddle_drag_index = resize_index
                                self.effect_puddle_resize_kind = resize_kind or "corner"
                                self.dragging_effect_sun = False
                                self.dragging_effect_moon = False
                                self.dragging_effect_ice = False
                                self.dragging_effect_puddle = False
                            elif clicked_widget.is_puddle_hit(pos):
                                self.dragging_effect_puddle = True
                                self.effect_puddle_drag_index, self.effect_puddle_drag_offset = clicked_widget.puddle_drag_offset_from_pos(pos)
                                self.dragging_effect_sun = False
                                self.dragging_effect_moon = False
                                self.dragging_effect_ice = False
                                self.dragging_effect_puddle_resize = False
                            else:
                                self.dragging_effect_moon = False
                                self.dragging_effect_sun = False
                                self.dragging_effect_ice = False
                                self.dragging_effect_puddle = False
                                self.dragging_effect_puddle_resize = False
                                self.drag_offset = pos - QPoint(
                                    clicked_widget.cfg.x,
                                    clicked_widget.cfg.y
                                )
                        else:
                            self.dragging_effect_moon = False
                            self.dragging_effect_sun = False
                            self.dragging_effect_ice = False
                            self.dragging_effect_puddle = False
                            self.dragging_effect_puddle_resize = False
                            self.drag_offset = pos - QPoint(
                                clicked_widget.cfg.x,
                                clicked_widget.cfg.y
                            )

            self.update()
            self.notify_studio_selection_changed()
        elif event.button() == Qt.MouseButton.RightButton:
            pos = event.position().toPoint()
            self.notify_effect_widgets_mouse_press(pos)
            return

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self.notify_effect_widgets_mouse_move(pos)
        new_pos = pos - self.drag_offset

        if self.dragging and self.selected and self.edit_mode and isinstance(self.selected, EffectsOverlayWidget) and (getattr(self, "dragging_effect_sun", False) or getattr(self, "dragging_effect_moon", False) or getattr(self, "dragging_effect_ice", False) or getattr(self, "dragging_effect_puddle", False) or getattr(self, "dragging_effect_puddle_resize", False)):
            if getattr(self, "dragging_effect_sun", False):
                self.selected.move_sun_center_to(
                    pos,
                    getattr(self, "effect_sun_drag_offset", QPointF(0.0, 0.0)),
                    getattr(self, "effect_sun_drag_kind", "sun")
                )
            elif getattr(self, "dragging_effect_moon", False):
                self.selected.move_moon_center_to(pos, getattr(self, "effect_moon_drag_offset", QPointF(0.0, 0.0)))
            elif getattr(self, "dragging_effect_ice", False):
                self.selected.move_ice_center_to(pos, getattr(self, "effect_ice_drag_offset", QPointF(0.0, 0.0)))
            elif getattr(self, "dragging_effect_puddle_resize", False):
                self.selected.resize_puddle_to(pos, getattr(self, "effect_puddle_drag_index", None), getattr(self, "effect_puddle_resize_kind", "corner"))
            else:
                self.selected.move_puddle_center_to(pos, getattr(self, "effect_puddle_drag_offset", QPointF(0.0, 0.0)), getattr(self, "effect_puddle_drag_index", None))
            self.update_platform_hit_mask()
            self.update()
            return

        if self.dragging and self.selected and self.edit_mode:
            if getattr(self, "dragging_effect_moon", False) and isinstance(self.selected, EffectsOverlayWidget):
                self.selected.move_moon_center_to(pos, getattr(self, "effect_moon_drag_offset", QPointF(0.0, 0.0)))
            elif getattr(self, "dragging_effect_ice", False) and isinstance(self.selected, EffectsOverlayWidget):
                self.selected.move_ice_center_to(pos, getattr(self, "effect_ice_drag_offset", QPointF(0.0, 0.0)))
            elif getattr(self, "dragging_effect_puddle_resize", False) and isinstance(self.selected, EffectsOverlayWidget):
                self.selected.resize_puddle_to(pos, getattr(self, "effect_puddle_drag_index", None), getattr(self, "effect_puddle_resize_kind", "corner"))
            elif getattr(self, "dragging_effect_puddle", False) and isinstance(self.selected, EffectsOverlayWidget):
                self.selected.move_puddle_center_to(pos, getattr(self, "effect_puddle_drag_offset", QPointF(0.0, 0.0)), getattr(self, "effect_puddle_drag_index", None))
            else:
                self.selected.cfg.x = new_pos.x()
                self.selected.cfg.y = new_pos.y()
            self.update_platform_hit_mask()
        self.update()

        if self.volume_sliding and isinstance(self.selected, VolumeWidget):
            value = self.selected.volume_from_pos(pos)
            self.volume.set_volume(value)
            self.update()

    def mouseReleaseEvent(self, event):
        pos = event.position().toPoint()
        self.notify_effect_widgets_mouse_release(pos)
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.dragging_effect_moon = False
            self.dragging_effect_sun = False
            self.dragging_effect_ice = False
            self.dragging_effect_puddle = False
            self.dragging_effect_puddle_resize = False
            self.effect_puddle_drag_index = None
            self.effect_puddle_resize_kind = "corner"
            self.volume_sliding = False
            self.update_platform_hit_mask()
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
            self.update_platform_hit_mask()
            self.save_config()
            self.update()

        elif event.key() == Qt.Key.Key_E:
            self.edit_mode = not self.edit_mode
            self.update_platform_hit_mask()
            self.update()

        elif event.key() == Qt.Key.Key_Escape:
            self.selected = None
            for w in self.widgets:
                w.selected = False
            self.update()

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
        elif kind == "effects_overlay":
            cfg = WidgetConfig(
                type="effects_overlay",
                x=0,
                y=0,
                w=QApplication.primaryScreen().geometry().width(),
                h=QApplication.primaryScreen().geometry().height(),
                title="Overlay Widget",
                color="#FF7AAE",
                bg="#000000",
                bg_alpha=0,
            )
            ensure_effect_overlay_fields(cfg)
            cfg.effects_json = json.dumps(LIGHTWEIGHT_ROSE_PETAL_DEFAULT_SETTINGS, ensure_ascii=False)
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
                h=200,
                title="",
                color="#5BE7FF",
                bg="#10141C",
            )
        elif kind == "weather":
            cfg = WidgetConfig(
                type="weather",
                x=1180,
                y=630,
                w=320,
                h=300,
                title="Weather",
                color="#80FF9F",
                bg="#10141C",
                weather_location="",
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
        elif kind == "html_js":
            cfg = WidgetConfig(
                type="html_js",
                x=220,
                y=520,
                w=420,
                h=220,
                title="JavaScript HTML",
                color="#80FF9F",
                bg="#10141C",
                text=DEFAULT_JS_HTML,
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
                <p style="color:white;">{}</p>
                <p style="color:#B388FF;">{}</p>
                """.format(lds_tr("軽量な HTML/CSS 風ウィジェットです。"), lds_tr("QTextDocument ベースなので WebView より軽量です。")),
            )

        self.widgets.append(create_widget(cfg))
        self.save_config()
        self.update_platform_hit_mask()
        self.update()

    def save_config(self):
        data = {
            "studio_theme": get_canvas_studio_theme(self),
            LDS_LANGUAGE_CONFIG_KEY: _lds_normalize_lang(getattr(self, "language", get_litedesktopstudio_language())),
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
                    title=lds_tr("音楽Spectrum"),
                    color="#5BE7FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="clock",
                    x=820,
                    y=120,
                    w=240,
                    h=240,
                    title=lds_tr("時計"),
                    color="#FFCC66",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="network",
                    x=820,
                    y=390,
                    w=320,
                    h=150,
                    title=lds_tr("通信"),
                    color="#5BE7FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="system",
                    x=120,
                    y=340,
                    w=340,
                    h=150,
                    title=lds_tr("システム"),
                    color="#80FF9F",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="volume",
                    x=500,
                    y=340,
                    w=250,
                    h=150,
                    title=lds_tr("音量"),
                    color="#B388FF",
                    bg="#10141C",
                )),
                create_widget(WidgetConfig(
                    type="media",
                    x=1180,
                    y=450,
                    w=320,
                    h=160,
                    title=lds_tr("メディアコントローラー"),
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
                    <p style="color:white;">{}</p>
                    <p style="color:#80FF9F;">{}</p>
                    """.format(lds_tr("右クリックでパネルを開けます。"), lds_tr("E キーで編集モード切替 / Delete で削除。")),
                )),
            ]
            self.studio_theme = DEFAULT_STUDIO_THEME
            self.save_config()
            self.update_platform_hit_mask()
            return

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.studio_theme = normalize_studio_theme(data.get("studio_theme", DEFAULT_STUDIO_THEME))
                self.language = _lds_normalize_lang(data.get(LDS_LANGUAGE_CONFIG_KEY, get_litedesktopstudio_language()))
                set_litedesktopstudio_language(QApplication.instance(), self.language)
            self.widgets = []
            for item in data.get("widgets", []):
                cfg = widget_config_from_dict(item)
                self.widgets.append(create_widget(cfg))
            self.update_platform_hit_mask()

        except Exception:
            self.widgets = []

    def closeEvent(self, event):
        [thread.kill() for thread in THREADS]
        stop_runtime_controllers(self)
        self.save_config()
        event.accept()

def main():
    configure_effect_gpu_backend_before_app(True)
    app = QApplication(sys.argv)
    install_litedesktopstudio_translator(app, load_litedesktopstudio_language_preference())
    detect_effect_gpu_backend()
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    canvas = DesktopCanvas()
    canvas.show()

    if is_windows():
        hwnd = int(canvas.winId())
        WindowsTheme.apply_immersive_dark_titlebar(
            hwnd,
            WindowsTheme.is_dark_mode()
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()