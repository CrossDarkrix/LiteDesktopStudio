# -*- coding: utf-8 -*-
from __future__ import annotations

import calendar as py_calendar
import dataclasses
import math
import time

from PySide6.QtCore import (QRectF,
                            QPoint,
                            QPointF,
                            )
from PySide6.QtGui import (
    QPainter,
    QFont,
    QPen,
    QBrush,
    QLinearGradient,
    QRadialGradient,
    QTextDocument,
    QPainterPath,
    QImage,
    QPixmap,
)

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except:
    QOpenGLWidget = None

from litedesktopstudio.effects import *
from litedesktopstudio.runtime import *


def get_network_down_color(cfg):
    return getattr(cfg, "network_down_color", None) or DEFAULT_NETWORK_DOWN_COLOR


def get_network_up_color(cfg):
    return getattr(cfg, "network_up_color", None) or DEFAULT_NETWORK_UP_COLOR


def widget_bg_color(cfg, default_alpha=155):
    bg = QColor(getattr(cfg, "bg", None) or "#10141C")

    alpha = getattr(cfg, "bg_alpha", default_alpha)

    try:
        alpha = int(alpha)
    except:
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


@dataclass
class WidgetConfig:
    type: str
    x: int = 100
    y: int = 100
    w: int = 300
    h: int = 120
    # Rotation in degrees.  rotation_degrees is the canonical field used by the
    # desktop canvas; rotation is kept as a compatibility alias for older/experimental
    # preview code that already wrote cfg.rotation.
    rotation_degrees: float = 0.0
    rotation: float = 0.0
    title: str = "Widget"
    color: str = "#5BE7FF"
    bg: str = "#141820"
    text: str = ""
    font_size: int = 14

    jshtml_mode: str = "inline"
    jshtml_instance_id: str = ""
    jshtml_entry: str = "index.html"
    jshtml_package_name: str = ""
    jshtml_package_version: str = ""
    jshtml_permissions_json: str = "{}"

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
    visualizer_style: str = "classic"
    # Phase 24A-8: stores which UI preset was last applied to the visualizer.
    # The actual visualizer appearance continues to be stored in the existing
    # concrete visualizer_* fields, so older configs remain compatible.
    visualizer_preset_key: str = "manual"
    visualizer_shadow_enabled: bool = True
    visualizer_shadow_offset_x: float = 3.0
    visualizer_shadow_offset_y: float = 4.0
    visualizer_shadow_strength: float = 1.0
    visualizer_shadow_opacity: float = 0.65
    visualizer_shadow_depth: float = 1.0
    visualizer_shadow_blur: float = 1.0
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
    try:
        if "rotation_degrees" not in filtered and "rotation" in filtered:
            filtered["rotation_degrees"] = float(filtered.get("rotation", 0.0))
        if "rotation" not in filtered and "rotation_degrees" in filtered:
            filtered["rotation"] = float(filtered.get("rotation_degrees", 0.0))
    except Exception:
        pass
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

    def rotation_degrees(self) -> float:
        try:
            return float(getattr(self.cfg, "rotation_degrees", getattr(self.cfg, "rotation", 0.0)))
        except Exception:
            return 0.0

    def _map_canvas_point_to_unrotated_local(self, pos: QPoint) -> QPointF:
        """Map a canvas point into this widget's unrotated coordinate space."""
        try:
            r = self.interaction_rect()
            angle = math.radians(-self.rotation_degrees())
            if abs(angle) < 1e-9:
                return QPointF(pos)
            center = r.center()
            dx = float(pos.x()) - float(center.x())
            dy = float(pos.y()) - float(center.y())
            ca = math.cos(angle)
            sa = math.sin(angle)
            return QPointF(center.x() + dx * ca - dy * sa, center.y() + dx * sa + dy * ca)
        except Exception:
            return QPointF(pos)

    def contains(self, pos: QPoint) -> bool:
        return self.interaction_rect().contains(self._map_canvas_point_to_unrotated_local(pos))

    def paint(self, p: QPainter, ctx: Dict):
        raise NotImplementedError

    def to_config(self) -> WidgetConfig:
        return self.cfg

    def reflects_in_mirrors(self) -> bool:
        """Return whether this widget should be included in water/ice mirror source images."""
        try:
            return bool(getattr(self.cfg, "mirror_reflect_enabled", True))
        except:
            return True

    def set_reflects_in_mirrors(self, value: bool):
        try:
            self.cfg.mirror_reflect_enabled = bool(value)
        except:
            pass


class VisualizerWidget(BaseWidget):
    def __init__(self, cfg):
        super().__init__(cfg)
        self._peak_levels = []
        self._last_peak_update = time.time()
        self._last_visualizer_frame_time = 0.0
        self._visualizer_frame_cache = None
        self._visualizer_frame_cache_key = None
        # Flat Audio Spectrum 軽量化用キャッシュ。
        # 静的装飾は QImage に描き切って再利用し、sin/cos はテーブル参照に寄せる。
        self._flat_spectrum_static_hologram_cache = None
        self._flat_spectrum_static_hologram_cache_key = None
        self._flat_spectrum_wave_table_size = 1024
        self._flat_spectrum_wave_table_mask = self._flat_spectrum_wave_table_size - 1
        self._flat_spectrum_sin_table = [
            math.sin((i / self._flat_spectrum_wave_table_size) * math.tau)
            for i in range(self._flat_spectrum_wave_table_size)
        ]
        self._flat_spectrum_cos_table = [
            math.cos((i / self._flat_spectrum_wave_table_size) * math.tau)
            for i in range(self._flat_spectrum_wave_table_size)
        ]
        self._last_media_thumbnail_bytes = None
        self._media_thumbnail_pixmap = None
        # Rainbow effect optimization caches.
        self._rainbow_color_lut = None
        self._rainbow_powder_sprite_cache = {}

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
        except:
            scale = 1.0
        return max(0.35, min(2.4, scale))

    def _visualizer_frame_interval_seconds(self) -> float:
        if not bool(getattr(self.cfg, "visualizer_frame_rate_enabled", True)):
            return 0.0
        try:
            fps = int(getattr(self.cfg, "visualizer_frame_rate", 40))
        except:
            fps = 60
        fps = max(1, min(240, fps))
        try:
            # The flat spectrum inner hologram layer has a continuously rotating transform.
            # Keep only this style at a higher redraw cadence so the rotation does not step visibly
            # when the user has a low FPS limit configured for spectrum bars.
            if self._visualizer_style() == "flat_spectrum":
                fps = max(fps, 120)
        except Exception:
            pass
        return 1.0 / fps

    def _flat_spectrum_inner_rotation_degrees(self, now: float) -> float:
        """Return a stable, smooth counter-clockwise rotation angle for flat_spectrum's inner layer."""
        try:
            now = float(now)
        except Exception:
            now = time.time()
        speed = 163.0
        try:
            last_now = float(getattr(self, "_flat_spectrum_inner_rotation_time", now))
            angle = float(getattr(self, "_flat_spectrum_inner_rotation_angle", (now * speed) % 360.0))
            dt = max(0.0, min(1.0 / 20.0, now - last_now))
            angle = (angle + speed * dt) % 360.0
            self._flat_spectrum_inner_rotation_time = now
            self._flat_spectrum_inner_rotation_angle = angle
            return angle
        except Exception:
            return ((now * speed) % 360.0)

    def _flat_spectrum_inner_rotation_degrees2(self, now: float) -> float:
        """Return a stable, smooth counter-clockwise rotation angle for flat_spectrum's inner layer."""
        try:
            now = float(now)
        except Exception:
            now = time.time()
        speed = 58.0
        try:
            last_now = float(getattr(self, "_flat_spectrum_inner_rotation_time2", now))
            angle = float(getattr(self, "_flat_spectrum_inner_rotation_angle2", (now * speed) % 360.0))
            dt = max(0.0, min(1.0 / 20.0, now - last_now))
            angle = (angle + speed * dt) % 360.0
            self._flat_spectrum_inner_rotation_time2 = now
            self._flat_spectrum_inner_rotation_angle2 = angle
            return angle
        except Exception:
            return ((now * speed) % 360.0)

    def _flat_spectrum_sin_cos_from_angle(self, angle: float):
        """Return an approximated (sin, cos) pair from a precomputed table.

        The flat spectrum effect calls trigonometric functions many times per frame.
        A 1024-sample table is visually smooth enough for this UI effect and avoids
        repeated Python-level math.sin/math.cos calls in the hot path.
        """
        try:
            table_size = self._flat_spectrum_wave_table_size
            mask = self._flat_spectrum_wave_table_mask
            index = int((float(angle) % math.tau) * table_size / math.tau) & mask
            return self._flat_spectrum_sin_table[index], self._flat_spectrum_cos_table[index]
        except Exception:
            return math.sin(angle), math.cos(angle)

    def _flat_spectrum_sin_cos_for_step(self, index: int, total: int, phase_turns: float = -0.25):
        """Return an approximated (sin, cos) pair for a circular step.

        phase_turns=-0.25 matches the existing -pi/2 start angle used by the
        circular spectrum drawing code.
        """
        try:
            total = max(1, int(total))
            table_size = self._flat_spectrum_wave_table_size
            mask = self._flat_spectrum_wave_table_mask
            table_index = int((((int(index) / total) + phase_turns) % 1.0) * table_size) & mask
            return self._flat_spectrum_sin_table[table_index], self._flat_spectrum_cos_table[table_index]
        except Exception:
            angle = -math.pi / 2.0 + (float(index) / max(1.0, float(total))) * math.tau
            return math.sin(angle), math.cos(angle)

    def _flat_spectrum_static_hologram_image(self, max_effect_radius: float, base_color: QColor, width_scale: float):
        """Build or reuse the static hologram background for flat_spectrum.

        This cache contains only non-audio-reactive elements: the radial fill and
        fixed circular guide lines. Audio-reactive radial bars are intentionally
        drawn outside this cache so they can keep reacting to the signal.
        """
        try:
            radius = max(1.0, float(max_effect_radius))
            scale = max(0.1, float(width_scale))
            cache_radius = int(math.ceil(radius * 0.60 + max(3.0, scale * 3.0) + 4.0))
            size = max(4, cache_radius * 2)
            key = (
                size,
                round(radius, 2),
                round(scale, 3),
                int(base_color.red()),
                int(base_color.green()),
                int(base_color.blue()),
            )
            if self._flat_spectrum_static_hologram_cache_key == key and self._flat_spectrum_static_hologram_cache is not None:
                return self._flat_spectrum_static_hologram_cache, cache_radius

            image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            pp = QPainter(image)
            try:
                cc = QPointF(cache_radius, cache_radius)
                inv = QColor(255 - base_color.red(), 255 - base_color.green(), 255 - base_color.blue(), 105)
                acc = QColor(base_color)
                acc.setAlpha(105)
                rg = QRadialGradient(cc, radius * 0.56)
                rg.setColorAt(0.0, QColor(0, 0, 0, 70))
                rg.setColorAt(0.50, QColor(base_color.red(), base_color.green(), base_color.blue(), 42))
                rg.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 0))
                pp.setPen(Qt.PenStyle.NoPen)
                pp.setBrush(QBrush(rg))
                pp.drawEllipse(cc, radius * 0.50, radius * 0.50)
                pp.setBrush(Qt.BrushStyle.NoBrush)
                pp.setPen(QPen(acc, 1.4 * scale))
                pp.drawEllipse(cc, radius * 0.41, radius * 0.41)
                pp.setPen(QPen(inv, 1.0 * scale))
                pp.drawEllipse(cc, radius * 0.53, radius * 0.53)
            finally:
                pp.end()

            self._flat_spectrum_static_hologram_cache_key = key
            self._flat_spectrum_static_hologram_cache = image
            return image, cache_radius
        except Exception:
            return None, 0

    def _visualizer_effect_padding(self) -> float:
        """External cache padding is disabled; visualizer effects are scaled to fit inside the widget frame."""
        return 0.0

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
            str(getattr(self.cfg, "visualizer_style", "classic")),
            bool(getattr(self.cfg, "visualizer_shadow_enabled", True)),
            round(float(getattr(self.cfg, "visualizer_shadow_offset_x", 3.0)), 2),
            round(float(getattr(self.cfg, "visualizer_shadow_offset_y", 4.0)), 2),
            round(float(getattr(self.cfg, "visualizer_shadow_strength", 1.0)), 2),
            round(float(getattr(self.cfg, "visualizer_shadow_opacity", 0.65)), 2),
            round(float(getattr(self.cfg, "visualizer_shadow_depth", 1.0)), 2),
            round(float(getattr(self.cfg, "visualizer_shadow_blur", 1.0)), 2),
            round(float(self._visualizer_effect_padding()), 2),
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
                try:
                    ip.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                except Exception:
                    pass
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


    def _visualizer_style(self):
        value = str(getattr(self.cfg, "visualizer_style", "classic") or "classic").strip().lower()
        aliases = {
            "クラシック": "classic", "classic": "classic",
            "ベースドロップス風": "bass_drop", "bass drop": "bass_drop", "bass_drop": "bass_drop",
            "メロディック・バイブ風": "melodic_vibe", "melodic vibe": "melodic_vibe", "melodic_vibe": "melodic_vibe",
            "オルタナティブ風": "alternative", "alternative": "alternative",
            "サークル風": "circle", "circle": "circle",
            "楕円形": "ellipse", "ellipse": "ellipse",
            "ターンテーブル風": "turntable", "turntable": "turntable",
            "スポットライト・ビート風": "spotlight_beat", "スポットライト・ビート風": "spotlight_beat", "spotlight beat": "spotlight_beat",
            "オーディオ・リアクト風": "audio_react", "audio react": "audio_react", "audio_react": "audio_react",
            "レトロな未来風": "retro_future", "retro future": "retro_future", "retro_future": "retro_future",
            "虹風": "rainbow", "rainbow": "rainbow",
            "ミニマル風": "minimal", "minimal": "minimal",
            "アーバンタイムラプス風": "urban_timelapse", "urban timelapse": "urban_timelapse",
            "ミュージックビートウォール風": "music_beat_wall", "music beat wall": "music_beat_wall",
            "ledオーディオ波風": "led_audio_wave", "led audio wave": "led_audio_wave",
            "euphoria in motion風": "euphoria_motion", "euphoria in motion": "euphoria_motion",
            "luminance風": "luminance", "luminance": "luminance",
            "parallax waves風": "parallax_waves", "parallax waves": "parallax_waves", "パララックスウェーブ風": "parallax_waves",
            "hudオーディオイコライザ風": "hud_equalizer", "hud equalizer": "hud_equalizer",
            "space風": "space", "space": "space",
            "フラットオーディオスペクトラム風": "flat_spectrum", "flat spectrum": "flat_spectrum",
            "ダイナミックグリッチ風": "dynamic_glitch", "ダイナミックグリッチ風": "dynamic_glitch", "dynamic glitch": "dynamic_glitch",
            "cyber風": "cyber", "cyber": "cyber",
            "オーロラ風": "aurora", "aurora": "aurora",
            "ホログラム風": "hologram", "hologram": "hologram",
            "エネルギーシールド風": "energy_shield", "energy shield": "energy_shield",
            "オーディオリップル風": "audio_ripple", "audio ripple": "audio_ripple",
            "ネビュラ風": "nebula", "nebula": "nebula",
            "matrix風": "matrix", "matrix": "matrix",
            "レーダースキャン風": "radar_scan", "radar scan": "radar_scan",
            "オーディオトンネル風": "audio_tunnel", "audio tunnel": "audio_tunnel",
            "オーディオトンネル2風": "audio_tunnel_sphere", "audio tunnel 2": "audio_tunnel_sphere", "audio_tunnel_sphere": "audio_tunnel_sphere",
            "流星群風": "meteor_shower", "meteor shower": "meteor_shower",
            "ネオン・トンネル・ワイヤー風": "neon_tunnel_wire", "neon tunnel wire": "neon_tunnel_wire",
            "ネオン音波ビジュアライザー風": "neon_soundwave", "neon soundwave": "neon_soundwave",
            "光彩ビートのミュージック風": "glow_beat_music", "glow beat music": "glow_beat_music",
            "エニマティック・コ響サウンド風": "enigmatic_echo_sound", "エニグマティック・共鳴サウンド風": "enigmatic_echo_sound", "enigmatic echo sound": "enigmatic_echo_sound",
            "音声反応型ライト風": "reactive_lights", "reactive lights": "reactive_lights",
            "エレクトロ・ダブステップ風": "electro_dubstep", "electro dubstep": "electro_dubstep",
            "ミニマルビート風": "minimal_beat", "minimal beat": "minimal_beat",
            "ローファイ・バイブス風": "lofi_vibes", "lofi vibes": "lofi_vibes",
            "コズミックフュージョン風": "cosmic_fusion", "cosmic fusion": "cosmic_fusion",
            "フューチャリスティックトンネル風": "futuristic_tunnel", "futuristic tunnel": "futuristic_tunnel",
            "エレクトリックパルス風": "electric_pulse", "electric pulse": "electric_pulse",
            "サークル波形風": "circle_waveform", "circle waveform": "circle_waveform",
            "ビート蛍光色視覚化アプリ風": "beat_fluorescent_app", "beat fluorescent app": "beat_fluorescent_app",
            "rainbow ring dj visualizer風": "rainbow_ring_dj", "rainbow ring dj visualizer": "rainbow_ring_dj", "rainbow_ring_dj": "rainbow_ring_dj",
            "liquid audio spectrum風": "liquid_audio_spectrum", "liquid audio spectrum": "liquid_audio_spectrum", "liquid_audio_spectrum": "liquid_audio_spectrum",
            "music logo reveal visualizer風": "music_logo_reveal", "music logo reveal visualizer": "music_logo_reveal", "music_logo_reveal": "music_logo_reveal",
            "particle audio visualizer風": "particle_audio_visualizer", "particle audio visualizer": "particle_audio_visualizer", "particle_audio_visualizer": "particle_audio_visualizer",
            "music lower third with audio visualizer風": "music_lower_third_audio", "music lower third with audio visualizer": "music_lower_third_audio", "music_lower_third_audio": "music_lower_third_audio",
            "digital base audio visualizer風": "digital_base_audio", "digital base audio visualizer": "digital_base_audio", "digital_base_audio": "digital_base_audio",
            "round base audio visualizer風": "round_base_audio", "round base audio visualizer": "round_base_audio", "round_base_audio": "round_base_audio",
        }
        value = aliases.get(value, value if value else "classic")
        removed_visualizer_styles = {
            "alternative",
            "audio_react",
            "audio_tunnel",
            "audio_tunnel_sphere",
            "bass_drop",
            "beat_fluorescent_app",
            "circle",
            "circle_waveform",
            "dynamic_glitch",
            "electric_pulse",
            "energy_shield",
            "euphoria_motion",
            "futuristic_tunnel",
            "led_audio_wave",
            "liquid_audio_spectrum",
            "lofi_vibes",
            "matrix",
            "melodic_vibe",
            "meteor_shower",
            "music_logo_reveal",
            "nebula",
            "neon_tunnel_wire",
            "parallax_waves",
            "particle_audio_visualizer",
            "radar_scan",
            "rainbow_ring_dj",
            "retro_future",
            "urban_timelapse",
        }
        if value in removed_visualizer_styles:
            return "classic"
        return value

    def _visualizer_energy(self, bars):
        try:
            vals = [max(0.0, min(1.0, float(v))) for v in bars]
            if not vals:
                return 0.0, 0.0, 0.0
            n = len(vals)
            bass_n = max(1, n // 5)
            bass = sum(vals[:bass_n]) / bass_n
            mid_vals = vals[bass_n:max(bass_n + 1, n * 3 // 5)]
            mid = sum(mid_vals) / max(1, len(mid_vals))
            avg = sum(vals) / n
            return avg, bass, max(mid, max(vals) * 0.35)
        except Exception:
            return 0.0, 0.0, 0.0

    def _rainbow_color(self, phase: float, alpha: int = 230, sat: float = 0.82, val: float = 1.0) -> QColor:
        try:
            c = QColor()
            c.setHsvF(float(phase) % 1.0, max(0.0, min(1.0, float(sat))), max(0.0, min(1.0, float(val))), max(0, min(255, int(alpha))) / 255.0)
            return c
        except Exception:
            return QColor(255, 255, 255, max(0, min(255, int(alpha))))

    def _rainbow_lut_color(self, phase: float, alpha: int = 230) -> QColor:
        try:
            lut = getattr(self, "_rainbow_color_lut", None)
            if not isinstance(lut, list) or len(lut) != 256:
                lut = []
                for i in range(256):
                    c = QColor()
                    c.setHsvF(i / 256.0, 0.82, 1.0, 1.0)
                    lut.append(c)
                self._rainbow_color_lut = lut
            c = QColor(lut[int((float(phase) % 1.0) * 256.0) & 255])
            c.setAlpha(max(0, min(255, int(alpha))))
            return c
        except Exception:
            return self._rainbow_color(phase, alpha)

    def _get_rainbow_powder_sprite(self, hue_bucket: int, size_bucket: int, angle_bucket: int) -> QImage:
        try:
            hue_bucket = int(hue_bucket) % 24
            size_bucket = max(0, min(2, int(size_bucket)))
            angle_bucket = int(angle_bucket) % 16
            key = (hue_bucket, size_bucket, angle_bucket)
            cache = getattr(self, "_rainbow_powder_sprite_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._rainbow_powder_sprite_cache = cache
            cached = cache.get(key)
            if cached is not None and not cached.isNull():
                return cached
            if len(cache) > 1536:
                cache.clear()
            image_size = 18 + size_bucket * 5
            image = QImage(image_size, image_size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            pp = QPainter(image)
            try:
                pp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                center = image_size * 0.5
                pr = image_size * (0.19 + size_bucket * 0.015)
                pp.translate(center, center)
                pp.rotate(angle_bucket * 22.5)
                c1 = self._rainbow_lut_color(hue_bucket / 24.0, 230)
                c2 = self._rainbow_lut_color((hue_bucket / 24.0 + 0.33) % 1.0, 230)
                c3 = QColor(255, 255, 255, 150)
                halo = QColor(c1)
                halo.setAlpha(44)
                pp.setPen(Qt.PenStyle.NoPen)
                pp.setBrush(QBrush(halo))
                pp.drawEllipse(QPointF(0, 0), pr * 1.55, pr * 0.48)
                grad = QLinearGradient(QPointF(-pr * 1.05, 0), QPointF(pr * 1.05, 0))
                grad.setColorAt(0.00, c1)
                grad.setColorAt(0.48, c3)
                grad.setColorAt(1.00, c2)
                flake = QPainterPath()
                flake.moveTo(QPointF(-pr * 0.95, -pr * 0.18))
                flake.lineTo(QPointF(-pr * 0.18, -pr * 0.50))
                flake.lineTo(QPointF(pr * 0.92, -pr * 0.12))
                flake.lineTo(QPointF(pr * 0.36, pr * 0.42))
                flake.lineTo(QPointF(-pr * 0.72, pr * 0.30))
                flake.closeSubpath()
                pp.setBrush(QBrush(grad))
                pp.drawPath(flake)
                pp.setPen(QPen(QColor(255, 255, 255, 115), max(0.6, image_size * 0.035)))
                pp.drawLine(QPointF(-pr * 0.50, -pr * 0.04), QPointF(pr * 0.52, pr * 0.07))
            finally:
                pp.end()
            cache[key] = image
            return image
        except Exception:
            fallback = QImage(8, 8, QImage.Format.Format_ARGB32_Premultiplied)
            fallback.fill(Qt.GlobalColor.transparent)
            return fallback








    def _paint_electro_dubstep_mesh_ring(self, p: QPainter, values, area: QRectF, ctx: Dict,
                                         base_color: QColor, now: float, avg: float, bass: float,
                                         max_effect_radius: float, width_scale: float):
        """Paint Electro Dubstep as a punch-reactive diagonal mesh with cover shockwave.

        Center remains cover-only, but strong low/mid hits temporarily scale the cover
        itself and emit a short outward shockwave.  The outer mesh keeps 3/6/9/12
        o'clock pinned to the circle, while diagonal spans are cinched outward by
        mid-band hits.
        """
        count = max(1, len(values))
        aw = max(1.0, float(area.width()))
        ah = max(1.0, float(area.height()))
        short_side = min(aw, ah)
        cx = area.center().x()
        cy = area.center().y()
        source_count = max(1, len(values))

        # Mid-band focus for the mesh pull.
        mid_start = min(source_count - 1, max(0, int(source_count * 0.20)))
        mid_end = min(source_count - 1, max(mid_start + 1, int(source_count * 0.66)))
        mid_span = max(1, mid_end - mid_start)

        sample_count = max(144, min(240, count if count > 0 else 176))
        raw = []
        for s in range(sample_count):
            pos = s / max(1, sample_count - 1)
            src = mid_start + int(pos * mid_span)
            src = max(0, min(source_count - 1, src))
            center_weight = 1.0 - min(1.0, abs(pos - 0.50) / 0.50)
            band_weight = 0.62 + center_weight * 0.38
            raw.append(max(0.0, min(1.0, float(values[src]) * band_weight)))

        # Heavy angular smoothing removes thorn-like randomness and makes the lobe pull fluid.
        for _ in range(5):
            raw = [
                raw[(i - 3) % sample_count] * 0.04 +
                raw[(i - 2) % sample_count] * 0.09 +
                raw[(i - 1) % sample_count] * 0.22 +
                raw[i] * 0.30 +
                raw[(i + 1) % sample_count] * 0.22 +
                raw[(i + 2) % sample_count] * 0.09 +
                raw[(i + 3) % sample_count] * 0.04
                for i in range(sample_count)
            ]

        previous_spectrum = getattr(self, "_electro_dubstep_outer_mesh_spectrum", None)
        if not isinstance(previous_spectrum, list) or len(previous_spectrum) != sample_count:
            previous_spectrum = raw[:]
        spectrum = []
        for cur, old in zip(raw, previous_spectrum):
            rate = 0.60 if cur >= old else 0.40
            spectrum.append(old * (1.0 - rate) + cur * rate)
        self._electro_dubstep_outer_mesh_spectrum = spectrum

        mid_peak = max(spectrum) if spectrum else 0.0
        mid_mean = sum(spectrum) / max(1, len(spectrum))
        mid_energy = max(0.0, min(1.0, mid_peak * 0.64 + mid_mean * 0.56))
        previous_mid_energy = float(getattr(self, "_electro_dubstep_outer_mesh_mid_energy", mid_energy))
        mid_onset = max(0.0, min(1.0, (mid_energy - previous_mid_energy) / 0.13))
        energy_gate = max(0.0, min(1.0, (mid_energy - 0.07) / 0.55))

        # Low + mid punch detector for the visible "ドンッ" shockwave.
        low_end = min(source_count, max(1, int(source_count * 0.18)))
        low_values = [max(0.0, min(1.0, float(values[i]))) for i in range(low_end)]
        low_peak = max(low_values) if low_values else 0.0
        low_mean = sum(low_values) / max(1, len(low_values))
        punch_energy = max(0.0, min(1.0, low_peak * 0.42 + low_mean * 0.24 + mid_peak * 0.30 + mid_mean * 0.22))
        previous_punch_energy = float(getattr(self, "_electro_dubstep_cover_punch_energy", punch_energy))
        punch_onset = max(0.0, min(1.0, (punch_energy - previous_punch_energy) / 0.16))
        punch_gate = max(0.0, min(1.0, (punch_energy - 0.12) / 0.58))
        punch_target = max(0.0, min(1.0, punch_onset * 1.70 + punch_gate * 0.30))
        if punch_onset < 0.065:
            punch_target *= 0.35
        if punch_target < 0.030:
            punch_target = 0.0

        impact = float(getattr(self, "_electro_dubstep_cover_impact", 0.0))
        impact_velocity = float(getattr(self, "_electro_dubstep_cover_impact_velocity", 0.0))
        impact_velocity += (punch_target - impact) * 0.860
        impact_velocity *= 0.500
        impact += impact_velocity
        if punch_target <= 0.02:
            impact *= 0.700
            impact_velocity *= 0.610
        if impact < 0.015 and punch_target <= 0.0:
            impact = 0.0
            impact_velocity = 0.0
        impact = max(0.0, min(1.0, impact))
        self._electro_dubstep_cover_punch_energy = punch_energy
        self._electro_dubstep_cover_impact = impact
        self._electro_dubstep_cover_impact_velocity = impact_velocity

        # Mesh pulse target: onset drives the big pull.  Sustained mid energy only
        # leaves a small amount of tension, so the mesh does not stay stretched.
        target = max(0.0, min(1.0, mid_onset * 1.82 + energy_gate * 0.18 + impact * 0.28))
        if mid_onset < 0.08 and impact < 0.12:
            target *= 0.28
        if target < 0.035:
            target = 0.0

        burst = float(getattr(self, "_electro_dubstep_outer_mesh_burst", 0.0))
        velocity = float(getattr(self, "_electro_dubstep_outer_mesh_burst_velocity", 0.0))
        velocity += (target - burst) * 0.800
        velocity *= 0.455
        burst += velocity
        if target <= 0.02:
            burst *= 0.735
            velocity *= 0.620
        if burst < 0.018 and target <= 0.0:
            burst = 0.0
            velocity = 0.0
        burst = max(0.0, min(1.0, burst))
        self._electro_dubstep_outer_mesh_mid_energy = mid_energy
        self._electro_dubstep_outer_mesh_burst = burst
        self._electro_dubstep_outer_mesh_burst_velocity = velocity

        # Cover image expands with low/mid punch, then immediately contracts.
        base_cover_radius = max(1.0, max_effect_radius * 0.46)
        cover_scale = 1.0 + impact * 0.115
        cover_radius = min(max_effect_radius * 0.58, base_cover_radius * cover_scale)
        cover_rect = QRectF(cx - cover_radius, cy - cover_radius, cover_radius * 2.0, cover_radius * 2.0)

        # Draw a visible outer shockwave before the cover and mesh.  This gives a
        # screen-obvious pulse while keeping the inside cover area clean.
        if impact > 0.010:
            wave_alpha = max(0, min(170, int(impact * 150)))
            wave_color = QColor(base_color)
            wave_color.setAlpha(wave_alpha)
            p.save()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(wave_color, max(1.0, (1.2 + impact * 3.0) * width_scale)))
            wave_radius = 0.0
            p.drawEllipse(QPointF(cx, cy), wave_radius, wave_radius)
            wave_color_2 = QColor(255, 255, 255, max(0, min(120, int(impact * 92))))
            p.setPen(QPen(wave_color_2, max(0.8, (0.8 + impact * 1.6) * width_scale)))
            p.drawEllipse(QPointF(cx, cy), wave_radius + max_effect_radius * 0.040, wave_radius + max_effect_radius * 0.040)
            p.restore()

        self._draw_visualizer_media_thumbnail_cover(
            p,
            cover_rect,
            ctx,
            clip_radius=cover_radius,
            fallback_accent=base_color,
        )

        anchor_gap = max(2.5, short_side * 0.009)
        anchor_radius = cover_radius + anchor_gap
        outer_limit = max(anchor_radius + 8.0, max_effect_radius * 0.995)
        max_push = max(7.0, outer_limit - anchor_radius)
        idle_band = 0.0
        pulled_band = max_push * (0.10 + burst * 1.42 + impact * 0.34)
        # No rotation: the mesh should only stretch and contract with the music.
        rotation = 0.0
        lobe_sigma = 0.430

        def _angle_distance(a, b):
            return abs((a - b + math.pi) % math.tau - math.pi)

        lobe_weights = []
        display_angles = []
        outer_radii = []
        for s, v in enumerate(spectrum):
            base_angle = (s / sample_count) * math.tau - math.pi / 2.0
            display_angle = base_angle + rotation
            upper_right_dist = _angle_distance(base_angle, -math.pi / 4.0)
            upper_left_dist = _angle_distance(base_angle, -math.pi * 3.0 / 4.0)
            lower_right_dist = _angle_distance(base_angle, math.pi / 4.0)
            lower_left_dist = _angle_distance(base_angle, math.pi * 3.0 / 4.0)
            upper_right_lobe = math.exp(-(upper_right_dist * upper_right_dist) / (2.0 * lobe_sigma * lobe_sigma))
            upper_left_lobe = math.exp(-(upper_left_dist * upper_left_dist) / (2.0 * lobe_sigma * lobe_sigma))
            lower_right_lobe = math.exp(-(lower_right_dist * lower_right_dist) / (2.0 * lobe_sigma * lobe_sigma))
            lower_left_lobe = math.exp(-(lower_left_dist * lower_left_dist) / (2.0 * lobe_sigma * lobe_sigma))
            upper_lobe = max(upper_right_lobe, upper_left_lobe)
            lower_lobe = max(lower_right_lobe, lower_left_lobe) * 0.50
            # Cardinal lock: 3, 6, 9, and 12 o'clock remain glued to the anchor circle.
            # sin(2a) is exactly zero at those four cardinal points and strongest on diagonals.
            cardinal_lock = abs(math.sin(base_angle * 2.0)) ** 1.55
            lobe_weight = (max(upper_lobe, lower_lobe) ** 0.92) * cardinal_lock
            soft_lobe = 0.5 + 0.5 * math.sin(now * 1.05 + s * 0.065)
            local = max(0.0, min(1.0, v * 0.82 + mid_energy * 0.18 + impact * 0.18 + soft_lobe * 0.018))
            pull = idle_band + pulled_band * lobe_weight * (0.12 + local * 0.88)
            outer_radii.append(min(outer_limit, anchor_radius + pull))
            lobe_weights.append(lobe_weight)
            display_angles.append(display_angle)

        rings = 7
        ring_points = []
        for ring in range(rings):
            t = ring / max(1, rings - 1)
            eased = t * t * (3.0 - 2.0 * t)
            pts = []
            for s, outer_r in enumerate(outer_radii):
                lobe_weight = lobe_weights[s]
                membrane_wobble = math.sin(now * (0.70 + eased * 0.18) + s * 0.080 + ring * 0.50)
                rr = anchor_radius + (outer_r - anchor_radius) * eased
                rr += membrane_wobble * short_side * 0.00048 * eased * lobe_weight * (0.08 + burst + impact * 0.45)
                rr = max(anchor_radius, min(outer_limit, rr))
                angle = display_angles[s]
                pts.append(QPointF(cx + math.cos(angle) * rr, cy + math.sin(angle) * rr))
            ring_points.append(pts)

        # Outside anchor only; this is the contracted attachment line of the mesh.
        attach_color = QColor(base_color)
        attach_color.setAlpha(34 + int(max(burst, impact) * 54))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(attach_color, max(0.55, (0.65 + max(burst, impact) * 0.34) * width_scale)))
        p.drawEllipse(QPointF(cx, cy), anchor_radius, anchor_radius)

        # Smooth circular strands.  3/6/9/12 stay pinned while diagonal spans are cinched outward.
        pulse_strength = max(burst, impact)
        for ring, pts in enumerate(ring_points):
            t = ring / max(1, rings - 1)
            alpha = max(16, min(225, int(26 + t * 54 + pulse_strength * 142)))
            col = QColor(base_color)
            col.setAlpha(alpha)
            self._draw_visualizer_polyline(
                p,
                pts + [pts[0]],
                col,
                max(0.48, (0.50 + t * 0.56 + pulse_strength * 0.62) * width_scale),
                alpha,
            )

        radial_step = max(3, sample_count // 46)
        diagonal_step = max(4, sample_count // 40)
        strand_alpha = max(14, min(198, int(20 + pulse_strength * 162)))
        strand = QColor(base_color)
        strand.setAlpha(strand_alpha)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(strand, max(0.34, (0.36 + pulse_strength * 0.64) * width_scale)))
        for s in range(0, sample_count, radial_step):
            for ring in range(rings - 1):
                p.drawLine(ring_points[ring][s], ring_points[ring + 1][s])

        diagonal = QColor(base_color)
        diagonal.setAlpha(max(12, int(strand_alpha * 0.58)))
        p.setPen(QPen(diagonal, max(0.30, (0.32 + pulse_strength * 0.40) * width_scale)))
        for s in range(0, sample_count, diagonal_step):
            offset = 1 + ((s // diagonal_step) % 2)
            for ring in range(rings - 1):
                p.drawLine(ring_points[ring][s], ring_points[ring + 1][(s + offset) % sample_count])
                if pulse_strength > 0.20:
                    p.drawLine(ring_points[ring][s], ring_points[ring + 1][(s - offset) % sample_count])

        # Dot lattice.  Dots are denser and larger in the pulled diagonal lobes.
        node_step = max(4, sample_count // 42)
        dot_alpha = max(28, min(220, int(38 + pulse_strength * 166)))
        p.setPen(Qt.PenStyle.NoPen)
        base_node_radius = max(0.60, (0.66 + pulse_strength * 1.36) * width_scale)
        for ring in range(rings):
            phase = (ring * 2) % node_step
            for s in range(phase, sample_count, node_step):
                lobe_weight = lobe_weights[s]
                pt = ring_points[ring][s]
                pulse = 0.86 + 0.14 * math.sin(now * 1.85 + s * 0.16 + ring * 0.55)
                alpha = max(18, min(230, int(dot_alpha * (0.45 + lobe_weight * 0.55))))
                node_color = QColor(255, 255, 255, alpha)
                p.setBrush(QBrush(node_color))
                r = base_node_radius * (0.56 + lobe_weight * 0.44 + ring / max(1, rings - 1) * 0.34) * pulse
                p.drawEllipse(pt, r, r)

        mid_step = max(5, sample_count // 36)
        mid_radius = max(0.44, base_node_radius * 0.52)
        for ring in range(rings - 1):
            for s in range((ring * 3) % mid_step, sample_count, mid_step):
                a = ring_points[ring][s]
                b = ring_points[ring + 1][(s + 1) % sample_count]
                mid = QPointF((a.x() + b.x()) * 0.5, (a.y() + b.y()) * 0.5)
                dx = mid.x() - cx
                dy = mid.y() - cy
                dist = math.hypot(dx, dy)
                if dist < anchor_radius and dist > 0.001:
                    mid = QPointF(cx + dx / dist * anchor_radius, cy + dy / dist * anchor_radius)
                lobe_weight = lobe_weights[s]
                alpha = max(16, min(190, int(dot_alpha * (0.32 + lobe_weight * 0.42))))
                mid_color = QColor(base_color)
                mid_color.setAlpha(alpha)
                p.setBrush(QBrush(mid_color))
                p.drawEllipse(mid, mid_radius * (0.74 + lobe_weight * 0.38), mid_radius * (0.74 + lobe_weight * 0.38))

    def _draw_visualizer_polyline(self, p: QPainter, points, color: QColor, width: float = 2.0, alpha: int = 220):
        if len(points) < 2:
            return
        c = QColor(color); c.setAlpha(max(0, min(255, int(alpha))))
        pen = QPen(c, max(0.5, float(width)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(points[0])
        for pt in points[1:]:
            path.lineTo(pt)
        p.drawPath(path)

    def _paint_luminance_wave_scene(self, p: QPainter, values, area: QRectF, base_color: QColor, now: float, avg: float, width_scale: float):
        """Paint Luminance as one continuous, dimensional waveform.

        Design goals:
        - Replace independent music bars with a single filled waveform.
        - Keep the existing accent-to-white gradient behavior.
        - Place three depth layers in a diagonal composition.
        - Alternate each waveform direction by depth: rear / middle / front = same / opposite / same.
        - Make the front waveform start at the upper-right when viewed from the front.
        """
        count = max(1, len(values))
        if count < 2:
            return

        aw = max(1.0, float(area.width()))
        ah = max(1.0, float(area.height()))
        cx = area.center().x()
        cy = area.center().y()
        diagonal_slope = float(getattr(self.cfg, "luminance_diagonal_slope", 0.30))

        def _smoothed_wave_points(y_offset: float = 0.0, x_offset: float = 0.0, amp_scale: float = 1.0, inverse: bool = False, reverse_x: bool = False):
            """Build a single continuous waveform layer.

            reverse_x=True makes t=0 begin on the right side. With the diagonal baseline,
            the front layer starts at upper-right and runs toward lower-left.
            inverse=True flips the waveform vertically so neighboring layers alternate.
            """
            top_pts = []
            bottom_pts = []
            center_pts = []
            smooth = float(avg)
            direction = -1.0 if inverse else 1.0
            for i, raw in enumerate(values):
                smooth = smooth * 0.82 + float(raw) * 0.18
                t = i / max(1, count - 1)
                x_t = 1.0 - t if reverse_x else t
                x = area.left() + aw * x_t + x_offset

                # t=0 is upper-right when reverse_x=True; t=1 ends lower-left.
                diagonal_y = (t - 0.5) * ah * diagonal_slope
                center_wave = math.sin(i * 0.095 + now * 0.72) * ah * 0.050 * direction
                fine_wave = math.sin(i * 0.235 - now * 0.38) * ah * 0.018 * direction
                center_y = cy + y_offset + diagonal_y + center_wave + fine_wave
                amp = ah * (0.070 + smooth * 0.255) * amp_scale

                top_pts.append(QPointF(x, center_y - amp * direction))
                bottom_pts.append(QPointF(x, center_y + amp * direction))
                center_pts.append(QPointF(x, center_y))
            return top_pts, bottom_pts, center_pts

        def _path_from_points(top_pts, bottom_pts):
            if not top_pts or not bottom_pts:
                return None
            path = QPainterPath(top_pts[0])
            for pt in top_pts[1:]:
                path.lineTo(pt)
            for pt in reversed(bottom_pts):
                path.lineTo(pt)
            path.closeSubpath()
            return path

        def _draw_wave(y_offset: float, x_offset: float, amp_scale: float, alpha_scale: float, inverse: bool, reflection: bool, reverse_x: bool = False):
            top_pts, bottom_pts, center_pts = _smoothed_wave_points(
                y_offset=y_offset,
                x_offset=x_offset,
                amp_scale=amp_scale,
                inverse=inverse,
                reverse_x=reverse_x,
            )
            wave_path = _path_from_points(top_pts, bottom_pts)
            if wave_path is None:
                return

            # Keep the original accent-color-to-white gradient direction on screen.
            grad = QLinearGradient(QPointF(area.left() + x_offset, cy + y_offset), QPointF(area.right() + x_offset, cy + y_offset))
            accent = QColor(base_color)
            accent.setAlpha(max(0, min(255, int(125 * alpha_scale))))
            white = QColor(255, 255, 255, max(0, min(255, int(170 * alpha_scale))))
            mid = QColor(base_color.red(), base_color.green(), base_color.blue(), max(0, min(255, int(148 * alpha_scale))))
            grad.setColorAt(0.0, accent)
            grad.setColorAt(0.58, mid)
            grad.setColorAt(1.0, white)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(wave_path)

            edge = QColor(255, 255, 255, max(0, min(255, int(112 * alpha_scale))))
            self._draw_visualizer_polyline(p, top_pts, edge, max(0.8, 1.4 * width_scale * amp_scale), edge.alpha())
            glow = QColor(base_color)
            glow.setAlpha(max(0, min(255, int(96 * alpha_scale))))
            self._draw_visualizer_polyline(p, center_pts, glow, max(0.9, 2.0 * width_scale * amp_scale), glow.alpha())

            if reflection:
                # Faint rear reflection: mirror the same continuous wave below the layer and fade it out.
                layer_cy = cy + y_offset
                refl_top = [QPointF(pt.x(), layer_cy + (layer_cy - pt.y()) * -0.42 + ah * 0.18) for pt in top_pts]
                refl_bottom = [QPointF(pt.x(), layer_cy + (layer_cy - pt.y()) * -0.42 + ah * 0.18) for pt in bottom_pts]
                refl_path = _path_from_points(refl_top, refl_bottom)
                if refl_path is not None:
                    refl_grad = QLinearGradient(QPointF(area.left() + x_offset, layer_cy + ah * 0.10), QPointF(area.right() + x_offset, layer_cy + ah * 0.24))
                    rc0 = QColor(base_color); rc0.setAlpha(max(0, min(255, int(42 * alpha_scale))))
                    rc1 = QColor(255, 255, 255, max(0, min(255, int(24 * alpha_scale))))
                    rc2 = QColor(base_color); rc2.setAlpha(0)
                    refl_grad.setColorAt(0.0, rc0)
                    refl_grad.setColorAt(0.45, rc1)
                    refl_grad.setColorAt(1.0, rc2)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(refl_grad))
                    p.drawPath(refl_path)

        p.save()
        try:
            # The waveform data itself starts at upper-right; this transform adds shallow 3D side-view depth.
            p.translate(cx, cy)
            p.rotate(float(getattr(self.cfg, "luminance_angle_degrees", -6.0)))
            p.shear(float(getattr(self.cfg, "luminance_shear_x", -0.12)), 0.0)
            p.scale(1.0, max(0.20, min(1.0, float(getattr(self.cfg, "luminance_side_view_y_scale", 0.60)))))
            p.translate(-cx, -cy)

            # Back -> middle -> front. Wave directions alternate: normal, inverted, normal.
            # All layers begin from the right side so the front layer starts at upper-right.
            # _draw_wave(y_offset=-ah * 0.29, x_offset=-aw * 0.075, amp_scale=0.70, alpha_scale=0.32, inverse=False, reflection=True, reverse_x=False)
            _draw_wave(y_offset=-ah * 0.145, x_offset=0.5, amp_scale=0.84, alpha_scale=1.0, inverse=True, reflection=True, reverse_x=False)
            _draw_wave(y_offset=0.0, x_offset=0.0, amp_scale=1.0, alpha_scale=1.0, inverse=False, reflection=True, reverse_x=False)
        finally:
            p.restore()
    def _draw_visualizer_soft_orb(self, p: QPainter, center: QPointF, radius: float, color: QColor, alpha: int):
        try:
            radius = max(1.0, float(radius))
            if not bool(getattr(self.cfg, "visualizer_glow_enabled", True)):
                c = QColor(color)
                c.setAlpha(max(0, min(255, int(alpha * 0.60))))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(c))
                p.drawEllipse(center, radius * 0.38, radius * 0.38)
                return
            grad = QRadialGradient(center, radius)
            c0 = QColor(color); c0.setAlpha(max(0, min(255, int(alpha))))
            c1 = QColor(color); c1.setAlpha(0)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(center, radius, radius)
        except Exception:
            pass


    def _paint_visualizer_depth_shadow(self, p: QPainter, values, style: str, area: QRectF, now: float, max_effect_radius: float, radius: float, avg: float, bass: float):
        """Draw a contained, low-alpha depth shadow under the active visualizer style."""
        try:
            count = max(1, len(values))
            aw = max(1.0, float(area.width()))
            ah = max(1.0, float(area.height()))
            cx = area.center().x()
            cy = area.center().y()
            short_side = min(aw, ah)
            if not bool(getattr(self.cfg, "visualizer_shadow_enabled", True)):
                return
            try:
                ox = float(getattr(self.cfg, "visualizer_shadow_offset_x", 3.0))
            except Exception:
                ox = 3.0
            try:
                oy = float(getattr(self.cfg, "visualizer_shadow_offset_y", 4.0))
            except Exception:
                oy = 4.0
            try:
                shadow_strength = float(getattr(self.cfg, "visualizer_shadow_strength", 1.0))
            except Exception:
                shadow_strength = 1.0
            try:
                shadow_opacity = float(getattr(self.cfg, "visualizer_shadow_opacity", 0.65))
            except Exception:
                shadow_opacity = 0.65
            try:
                shadow_depth = float(getattr(self.cfg, "visualizer_shadow_depth", 1.0))
            except Exception:
                shadow_depth = 1.0
            try:
                shadow_blur = float(getattr(self.cfg, "visualizer_shadow_blur", 1.0))
            except Exception:
                shadow_blur = 1.0
            shadow_strength = max(0.0, min(3.0, shadow_strength))
            shadow_opacity = max(0.0, min(1.0, shadow_opacity))
            shadow_depth = max(0.0, min(3.0, shadow_depth))
            shadow_blur = max(0.0, min(3.0, shadow_blur))
            if shadow_strength <= 0.0 or shadow_opacity <= 0.0 or shadow_depth <= 0.0:
                return
            depth_offset_scale = 0.25 + shadow_depth * 0.85
            ox *= depth_offset_scale
            oy *= depth_offset_scale
            alpha = max(0, min(190, int((30 + avg * 62 + bass * 22) * shadow_strength * shadow_opacity * (0.85 + shadow_depth * 0.10))))
            if alpha <= 0:
                return
            shadow = QColor(0, 0, 0, alpha)
            soft_shadow = QColor(0, 0, 0, max(1, int(alpha * (0.28 + shadow_depth * 0.06) / (0.85 + shadow_blur * 0.22))))
            shadow_size = max(0.20, min(4.2, shadow_strength * (0.70 + shadow_depth * 0.30) * (0.75 + shadow_blur * 0.25)))
            shadow_size *= max(0.35, min(2.4, self._visualizer_bar_width_scale()))
            # Style-specific branches use these adjusted values so strength/depth/opacity/blur remain visibly effective.
            style_shadow = QColor(0, 0, 0, max(0, min(235, int(alpha * (0.62 + shadow_strength * 0.18)))))
            style_soft_shadow = QColor(0, 0, 0, max(1, min(210, int(style_shadow.alpha() / (1.10 + shadow_blur * 0.42)))))
            style_shadow_size = max(0.15, min(6.0, shadow_size * (0.72 + shadow_strength * 0.12 + shadow_blur * 0.18)))
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(Qt.PenStyle.NoPen)

            circular = style in ("circle", "turntable", "spotlight_beat", "euphoria_motion", "luminance", "space", "energy_shield", "audio_ripple", "radar_scan", "circle_waveform", "rainbow_ring_dj", "round_base_audio")
            elliptic = style in ("ellipse", "parallax_waves")
            tunnel = style in ("audio_tunnel", "neon_tunnel_wire", "futuristic_tunnel")
            wave = style in ("aurora", "neon_soundwave", "enigmatic_echo_sound", "lofi_vibes", "electric_pulse", "liquid_audio_spectrum")
            cloud = style in ("nebula", "cosmic_fusion", "meteor_shower", "reactive_lights", "particle_audio_visualizer")
            wall = style in ("music_beat_wall", "led_audio_wave", "hud_equalizer", "flat_spectrum", "cyber", "retro_future", "minimal", "alternative", "bass_drop", "audio_react", "rainbow", "dynamic_glitch", "urban_timelapse", "melodic_vibe", "hologram", "matrix", "electro_dubstep", "minimal_beat", "beat_fluorescent_app", "glow_beat_music", "music_logo_reveal", "music_lower_third_audio", "digital_base_audio")


            # Style-specific shadows: keep the shadow silhouette aligned with each visualizer skin.
            if style == "bass_drop":
                slot = aw / count
                center_y = cy + oy
                p.setPen(QPen(style_soft_shadow, max(1.0, 2.2 * style_shadow_size)))
                p.drawLine(QPointF(area.left() + ox, center_y), QPointF(area.right() + ox, center_y))
                bass_n = max(4, count // 4)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(style_shadow))
                for i, v in enumerate(values):
                    low_boost = values[min(i, bass_n - 1)] if i < bass_n else v * 0.45
                    value = max(v * 0.35, low_boost)
                    h = ah * (0.035 + value * (0.34 + bass * 0.22))
                    x = area.left() + i * slot + ox
                    bw = max(1.0, slot * min(0.92, 0.52 * style_shadow_size))
                    p.drawRoundedRect(QRectF(x + slot * 0.24, center_y - h, bw, h * 2.0), 4, 4)
                p.restore(); return

            if style in ("melodic_vibe", "liquid_audio_spectrum", "rainbow", "parallax_waves", "space", "aurora", "neon_soundwave", "enigmatic_echo_sound", "lofi_vibes", "electric_pulse"):
                layers = 3 if style in ("parallax_waves", "liquid_audio_spectrum", "melodic_vibe") else 2
                for layer in range(layers):
                    pts = []
                    smooth = avg
                    speed = 0.55 + layer * 0.28
                    for i, raw in enumerate(values):
                        smooth = smooth * 0.80 + float(raw) * 0.20
                        x = area.left() + aw * i / max(1, count - 1) + ox
                        y = cy + oy + math.sin(i * (0.10 + layer * 0.03) + now * speed) * ah * (0.045 + layer * 0.025) - (smooth - avg) * ah * (0.15 + layer * 0.05)
                        pts.append(QPointF(x, y + (layer - 1) * ah * 0.035))
                    self._draw_visualizer_polyline(p, pts, shadow, (2.2 + layer * 1.0) * style_shadow_size, alpha)
                p.restore(); return

            if style == "alternative":
                slot = aw / count
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(style_shadow))
                for i, v in enumerate(values):
                    skew = ((i * 17 + int(now * 9)) % 11 - 5) * slot * 0.055
                    h = ah * (0.05 + v * (0.60 + ((i % 5) * 0.055)))
                    x = area.left() + i * slot + skew + ox
                    y = (area.bottom() - h if i % 2 else area.top() + ah * 0.10) + oy
                    p.drawRect(QRectF(x + slot * 0.25, y, max(1.0, slot * min(0.86, 0.36 * style_shadow_size)), h))
                p.restore(); return

            if style in ("circle", "ellipse", "euphoria_motion", "circle_waveform", "rainbow_ring_dj", "round_base_audio", "energy_shield", "audio_ripple"):
                rx_scale = 1.58 if style == "ellipse" else 1.0
                ry_scale = 0.54 if style == "ellipse" else 1.0
                core = min(radius, max_effect_radius * (0.48 if style == "ellipse" else 0.56))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(style_soft_shadow, max(1.0, 2.0 * style_shadow_size)))
                p.drawEllipse(QPointF(cx + ox, cy + oy), core * rx_scale, core * ry_scale)
                step = max(1, count // 84)
                p.setPen(QPen(style_shadow, max(1.0, 1.5 * style_shadow_size)))
                for i in range(0, count, step):
                    v = values[i]
                    ang = i / count * math.tau - math.pi / 2.0
                    inner = core
                    outer = min(max_effect_radius * 0.98, inner + short_side * (0.035 + v * 0.18))
                    p.drawLine(QPointF(cx + ox + math.cos(ang) * inner * rx_scale, cy + oy + math.sin(ang) * inner * ry_scale), QPointF(cx + ox + math.cos(ang) * outer * rx_scale, cy + oy + math.sin(ang) * outer * ry_scale))
                p.restore(); return

            if style == "turntable":
                # Side-view turntable silhouette: extend the outer black platter and keep bars inside it.
                cover_r = min(max_effect_radius * 0.58, short_side * 0.29)
                outer_r = min(max_effect_radius * 0.98, cover_r + 70.0)
                side_y_scale = 0.38
                tilt_degrees = -3.0
                p.save()
                try:
                    p.translate(cx + ox, cy + oy)
                    p.rotate(tilt_degrees)
                    p.scale(1.0, side_y_scale)
                    p.translate(-(cx + ox), -(cy + oy))
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(style_soft_shadow))
                    p.drawEllipse(QPointF(cx + ox, cy + oy), outer_r, outer_r)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(style_shadow, max(1.0, 1.2 * style_shadow_size)))
                    for k in range(4):
                        rr = cover_r * (0.34 + k * 0.17)
                        p.drawEllipse(QPointF(cx + ox, cy + oy), rr, rr)
                finally:
                    p.restore()
                p.restore(); return

            if style == "spotlight_beat":
                for k in range(7):
                    ang = -math.pi * 0.86 + k * math.pi / 3.0 + math.sin(now * 0.82 + k) * (0.12 + bass * 0.11)
                    p.setPen(QPen(style_soft_shadow, max(7.0, (13.0 + bass * 25.0) * style_shadow_size)))
                    p.drawLine(QPointF(cx + ox, area.bottom() + oy), QPointF(cx + ox + math.cos(ang) * aw * 0.72, cy + oy + math.sin(ang) * ah * 0.84))
                p.restore(); return

            if style in ("audio_react", "minimal", "flat_spectrum", "luminance", "cyber", "dynamic_glitch", "digital_base_audio", "electro_dubstep", "minimal_beat", "beat_fluorescent_app", "glow_beat_music"):
                slot = aw / count
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(style_shadow if style not in ("minimal", "flat_spectrum") else style_soft_shadow))
                for i, v in enumerate(values):
                    h = ah * (0.04 + v * 0.84)
                    x = area.left() + i * slot + ox
                    y = area.bottom() - h + oy
                    p.drawRoundedRect(QRectF(x + slot * 0.20, y, max(1.0, slot * min(0.90, 0.54 * style_shadow_size)), h), 3, 3)
                p.restore(); return

            if style == "retro_future":
                horizon = area.top() + ah * 0.46 + oy
                p.setPen(QPen(style_soft_shadow, max(1.0, 1.0 * style_shadow_size)))
                for gy in range(7):
                    y = horizon + (((gy / 6.0 + (now * 0.08) % 1.0) % 1.0) ** 1.7) * ah * 0.48
                    p.drawLine(QPointF(area.left() + ox, y), QPointF(area.right() + ox, y))
                slot = aw / count
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(style_shadow))
                for i, v in enumerate(values):
                    h = ah * (0.045 + v * 0.40)
                    p.drawRoundedRect(QRectF(area.left() + i * slot + slot * 0.18 + ox, horizon - h, max(1.0, slot * min(0.88, 0.56 * style_shadow_size)), h), 3, 3)
                p.restore(); return

            if style == "urban_timelapse":
                slot = aw / count
                p.setPen(QPen(style_shadow, max(1.0, 1.4 * style_shadow_size)))
                for i, v in enumerate(values):
                    trail = ((now * (28 + v * 42) + i * 13) % max(1.0, aw))
                    x = area.left() + trail + ox
                    y = area.top() + ah * (0.20 + (i % 9) / 12.0) + oy
                    length = slot * (1.0 + v * 6.0)
                    p.drawLine(QPointF(x - length, y), QPointF(x, y))
                p.restore(); return

            if style in ("music_beat_wall", "hologram", "hud_equalizer", "music_lower_third_audio", "music_logo_reveal"):
                slot = aw / count
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(style_shadow))
                if style in ("music_lower_third_audio", "music_logo_reveal"):
                    panel_w = aw * (0.92 if style == "music_lower_third_audio" else 0.58)
                    panel_h = ah * (0.32 if style == "music_lower_third_audio" else 0.30)
                    px = area.left() + aw * 0.04 if style == "music_lower_third_audio" else cx - panel_w / 2.0
                    py = area.bottom() - panel_h - ah * 0.06 if style == "music_lower_third_audio" else cy - panel_h / 2.0 - ah * 0.05
                    p.drawRoundedRect(QRectF(px + ox, py + oy, panel_w, panel_h), 12, 12)
                for i, v in enumerate(values):
                    h = ah * (0.05 + v * 0.70)
                    p.drawRoundedRect(QRectF(area.left() + i * slot + slot * 0.18 + ox, area.bottom() - h + oy, max(1.0, slot * min(0.90, 0.58 * style_shadow_size)), h), 2, 2)
                p.restore(); return

            if style == "led_audio_wave":
                slot = aw / count
                dot = max(1.4, min(6.0, slot * 0.42 * style_shadow_size))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(style_shadow))
                for i, v in enumerate(values):
                    y = cy + oy + math.sin(i * 0.25 + now * 2.4) * ah * 0.12
                    steps = max(1, int(v * 6))
                    for j in range(-steps, steps + 1):
                        p.drawEllipse(QPointF(area.left() + i * slot + slot * 0.5 + ox, y + j * dot * 1.65), dot, dot)
                p.restore(); return

            if style in ("audio_tunnel", "neon_tunnel_wire", "futuristic_tunnel"):
                p.setBrush(Qt.BrushStyle.NoBrush)
                for k in range(7):
                    t = k / 6.0
                    scale = 1.0 - t * 0.78
                    rect = QRectF(cx - aw * scale * 0.40 + ox, cy - ah * scale * 0.33 + oy, aw * scale * 0.80, ah * scale * 0.66)
                    pen = QPen(QColor(0, 0, 0, max(10, int(alpha * (1.0 - t * 0.55)))), max(1.0, (1.0 + (1.0 - t) * 2.0) * style_shadow_size))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(pen)
                    p.drawRoundedRect(rect, 8, 8)
                p.restore(); return

            if style in ("nebula", "cosmic_fusion", "meteor_shower", "reactive_lights", "particle_audio_visualizer"):
                step = max(1, count // 28)
                for i in range(0, count, step):
                    v = values[i]
                    angle = i / count * math.tau + now * 0.08
                    rr = min(max_effect_radius * 0.78, radius * (0.30 + (i % 7) * 0.045 + v * 0.34))
                    self._draw_visualizer_soft_orb(p, QPointF(cx + ox + math.cos(angle) * rr, cy + oy + math.sin(angle * 1.25) * rr * 0.62), (3.0 + v * short_side * 0.040) * style_shadow_size, shadow, max(12, int(alpha * 0.60)))
                p.restore(); return

            if style == "matrix":
                p.setFont(QFont("Consolas", max(8, min(14, int(ah / 13.5)))))
                cols = max(6, min(48, count // 2))
                p.setPen(soft_shadow)
                for col in range(cols):
                    x = area.left() + col * aw / max(1, cols) + ox
                    y = area.top() + ((now * 8 + col * 17) % max(1.0, ah)) + oy
                    p.drawText(QPointF(x, y), "0" if col % 2 else "1")
                p.restore(); return

            if circular or elliptic:
                rx_scale = 1.32 if elliptic else 1.0
                ry_scale = 0.56 if elliptic else 1.0
                core = min(radius, max_effect_radius * 0.62)
                p.setBrush(Qt.BrushStyle.NoBrush)
                ring_pen = QPen(soft_shadow, max(1.0, short_side * 0.015 * shadow_size))
                ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(ring_pen)
                for k in range(2):
                    rr = min(max_effect_radius * 0.82, core * (0.92 + k * 0.26 + bass * 0.08))
                    p.drawEllipse(QPointF(cx + ox, cy + oy), rr * rx_scale, rr * ry_scale)
                ray_pen = QPen(shadow, max(1.0, (short_side * 0.010 + bass * 2.0) * shadow_size))
                ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(ray_pen)
                step = max(1, count // 28)
                for i in range(0, count, step):
                    v = max(0.0, min(1.0, float(values[i])))
                    ang = i / count * math.tau - math.pi / 2.0
                    inner = core * 0.86
                    outer = min(max_effect_radius * 0.96, inner + short_side * (0.045 + v * 0.12))
                    p.drawLine(
                        QPointF(cx + ox + math.cos(ang) * inner * rx_scale, cy + oy + math.sin(ang) * inner * ry_scale),
                        QPointF(cx + ox + math.cos(ang) * outer * rx_scale, cy + oy + math.sin(ang) * outer * ry_scale),
                    )
                p.restore(); return

            if tunnel:
                p.setBrush(Qt.BrushStyle.NoBrush)
                for k in range(7):
                    t = k / 6.0
                    scale = 1.0 - t * 0.78
                    rect = QRectF(cx - aw * scale * 0.40 + ox, cy - ah * scale * 0.33 + oy, aw * scale * 0.80, ah * scale * 0.66)
                    pen = QPen(QColor(0, 0, 0, max(10, int(alpha * (1.0 - t * 0.55)))), (1.0 + (1.0 - t) * 2.0) * shadow_size)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(pen)
                    p.drawRoundedRect(rect, 8, 8)
                p.restore(); return

            if wave:
                layers = 2
                for layer in range(layers):
                    pts = []
                    for i, v in enumerate(values):
                        x = area.left() + aw * i / max(1, count - 1) + ox
                        y = cy + oy + math.sin(i * (0.16 + layer * 0.06) + now * (1.4 + layer * 0.25)) * ah * (0.055 + layer * 0.030) - (float(v) - avg) * ah * (0.18 + layer * 0.06)
                        pts.append(QPointF(x, y))
                    self._draw_visualizer_polyline(p, pts, shadow, (3.0 + layer * 2.0 + bass * 2.5) * shadow_size, alpha)
                p.restore(); return

            if cloud:
                step = max(1, count // 24)
                for i in range(0, count, step):
                    v = max(0.0, min(1.0, float(values[i])))
                    angle = i / count * math.tau + now * 0.08
                    rr = min(max_effect_radius * 0.78, radius * (0.35 + (i % 5) * 0.055 + v * 0.32))
                    self._draw_visualizer_soft_orb(
                        p,
                        QPointF(cx + ox + math.cos(angle) * rr, cy + oy + math.sin(angle * 1.25) * rr * 0.62),
                        (4.0 + v * short_side * 0.040) * shadow_size,
                        shadow,
                        max(14, int(alpha * 0.70)),
                    )
                p.restore(); return

            if wall:
                slot = aw / count
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(shadow))
                step = 1 if count <= 72 else max(1, count // 72)
                for i in range(0, count, step):
                    v = max(0.0, min(1.0, float(values[i])))
                    x = area.left() + i * slot + slot * 0.18 + ox
                    h = ah * (0.055 + v * 0.72)
                    y = area.bottom() - h + oy
                    p.drawRoundedRect(QRectF(x, y, max(1.0, slot * 0.64), h), 4, 4)
                p.restore(); return
            p.restore()
        except Exception:
            try:
                p.restore()
            except Exception:
                pass


    def _paint_visualizer_style_glow(self, p: QPainter, values, style: str, area: QRectF, base_color: QColor, now: float, max_effect_radius: float, radius: float, avg: float, bass: float, width_scale: float):
        """Draw classic-like colored glow behind styled visualizers."""
        if not bool(getattr(self.cfg, "visualizer_glow_enabled", True)):
            return
        pass


    def _hud_clamp01(self, value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0

    def _hud_project_point(self, rect: QRectF, x: float, y: float, z: float):
        """
        Lightweight mathematical perspective projection for the HUD equalizer skin.

        World coordinates:
            x: left/right on the hologram floor
            y: height above the floor
            z: depth; small z is foreground, large z is background

        Returns:
            (QPointF, scale) where scale is larger in the foreground and smaller in depth.
        """
        aw = max(1.0, float(rect.width()))
        ah = max(1.0, float(rect.height()))
        left = float(rect.left())
        top = float(rect.top())
        cx = float(rect.center().x())
        bottom = float(rect.bottom())

        z = max(0.05, float(z))
        depth_scale = 1.0 / (1.0 + z * 0.235)
        # Floor converges toward the horizon as z grows.
        horizon_y = top + ah * 0.165
        floor_front_y = bottom - ah * 0.075
        floor_t = z / (z + 3.45)
        floor_y = floor_front_y + (horizon_y - floor_front_y) * floor_t

        # Subtle yaw makes the whole hologram feel like a tilted 3D game UI plane.
        yaw_offset = z * aw * 0.023
        sx = cx + x * aw * 0.47 * depth_scale + yaw_offset
        sy = floor_y - y * ah * 0.42 * depth_scale
        return QPointF(sx, sy), depth_scale

    def _hud_path_from_points_cubic(self, points):
        """Create an organic smooth cubic path from projected points; no polyline graph look."""
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        if len(points) == 1:
            return path
        for i in range(1, len(points)):
            p0 = points[i - 1]
            p1 = points[i]
            pm = points[i - 2] if i >= 2 else p0
            pn = points[i + 1] if i + 1 < len(points) else p1
            c1 = QPointF(
                p0.x() + (p1.x() - pm.x()) * 0.165,
                p0.y() + (p1.y() - pm.y()) * 0.165,
            )
            c2 = QPointF(
                p1.x() - (pn.x() - p0.x()) * 0.165,
                p1.y() - (pn.y() - p0.y()) * 0.165,
            )
            path.cubicTo(c1, c2, p1)
        return path

    def _draw_hud_neon_path(
        self,
        p: QPainter,
        path: QPainterPath,
        color: QColor,
        core_width: float = 2.0,
        glow_scale: float = 1.0,
        dashed: bool = False,
        dash_offset: float = 0.0,
    ):
        """Multi-pass neon: wide transparent strokes -> bright narrow core stroke."""
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        layers = (
            (18.0 * glow_scale, 0.055),
            (12.0 * glow_scale, 0.095),
            (7.0 * glow_scale, 0.180),
            (4.0 * glow_scale, 0.360),
            (max(1.0, core_width), 1.000),
        )
        for width, alpha_f in layers:
            c = QColor(color)
            c.setAlphaF(max(0.0, min(1.0, alpha_f)))
            pen = QPen(c, max(0.75, width))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
                pen.setDashOffset(float(dash_offset))
            p.setPen(pen)
            p.drawPath(path)
        p.restore()

    def _hud_draw_projected_poly(self, p: QPainter, points, edge_color: QColor, fill_color: QColor = None, core_width: float = 1.4):
        if not points:
            return
        path = QPainterPath(points[0])
        for pt in points[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        p.save()
        if fill_color is not None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(fill_color))
            p.drawPath(path)
        self._draw_hud_neon_path(p, path, edge_color, core_width=core_width, glow_scale=0.65)
        p.restore()

    def _hud_projected_ring_path(self, rect: QRectF, cx: float, cy: float, cz: float, radius: float, now: float, phase: float = 0.0, samples: int = 72):
        pts = []
        for i in range(samples + 1):
            a = (i / samples) * math.tau + phase
            # A tilted target plane: x uses cos, y/z share sin, so projection creates real perspective.
            wx = cx + math.cos(a) * radius
            wy = cy + math.sin(a) * radius * 0.34
            wz = cz + math.sin(a) * radius * 0.42
            pt, _ = self._hud_project_point(rect, wx, wy, wz)
            pts.append(pt)
        return self._hud_path_from_points_cubic(pts)

    def _paint_hud_equalizer_scene(
        self,
        p: QPainter,
        values,
        area: QRectF,
        base_color: QColor,
        now: float,
        width_scale: float,
    ):
        """
        HUDオーディオイコライザ風・円形プロトタイプ v2。

        今回の修正:
            - リング群全体を横から見たように縦圧縮し、さらに約8度傾けて奥行き感を出す。
            - 各半透明リングに、ゆっくり一定周期で回転するハイライト/ノッチを追加する。
            - 音楽バーは短くし、密度を上げ、アクセントカラーのみで統一する。
            - 追加リングは大円リング上・音楽バー上に重ねず、内側領域に収める。
            - 背景は透明にし、リングと音楽バーだけで近未来感を出す。
            - 各リングは軽量なマルチパス霧ブラーで、半透明な雲のように滲ませる。
            - 軽量化のため、リング構造は維持しつつ、バーと装飾だけを必要最小限にする。
        """
        values = [self._hud_clamp01(v) for v in values]
        count = max(1, len(values))

        aw = max(1.0, float(area.width()))
        ah = max(1.0, float(area.height()))
        left = float(area.left())
        top = float(area.top())
        right = float(area.right())
        bottom = float(area.bottom())
        short_side = max(1.0, min(aw, ah))

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        except Exception:
            pass

        scene_rect = QRectF(left, top, aw, ah)
        ring_rect = QRectF(left + aw * 0.05, top + ah * 0.06, aw * 0.90, ah * 0.88)

        # 背景は透明。円と音楽バーだけで近未来感を出す。
        # ここでは塗りつぶしを行わず、既存のARGBキャッシュ透明度を活かす。
        p.setPen(Qt.PenStyle.NoPen)

        cx = float(ring_rect.center().x())
        cy = float(ring_rect.center().y())

        # 音楽バーを短くする分、密度を上げても全体が窮屈になりにくい。
        max_bar_len = short_side * 0.055
        bar_gap = short_side * 0.014
        outer_r = min(ring_rect.width(), ring_rect.height()) * 0.372
        outer_r = min(outer_r, short_side * 0.430 - max_bar_len)
        outer_r = max(18.0, outer_r)

        main_band_w = max(8.0, outer_r * 0.145)
        main_inner_r = max(1.0, outer_r - main_band_w)

        accent = QColor(base_color)
        if not accent.isValid():
            accent = QColor(0, 245, 255)
        accent.setAlpha(230)
        cyan = QColor(0, 245, 255)
        magenta = QColor(255, 42, 225)
        green = QColor(80, 255, 130)

        def _ring_path(x0: float, y0: float, radius: float, band: float) -> QPainterPath:
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.OddEvenFill)
            r0 = max(1.0, float(radius))
            inner = max(0.5, r0 - max(1.0, float(band)))
            path.addEllipse(QPointF(x0, y0), r0, r0)
            path.addEllipse(QPointF(x0, y0), inner, inner)
            return path

        def _arc_path(x0: float, y0: float, radius: float, start_rad: float, span_rad: float, samples: int = 18) -> QPainterPath:
            path = QPainterPath()
            samples = max(3, int(samples))
            for i in range(samples + 1):
                t = i / float(samples)
                a = start_rad + span_rad * t
                pt = QPointF(x0 + math.cos(a) * radius, y0 + math.sin(a) * radius)
                if i == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            return path

        def _draw_rotating_ring_marks(
            x0: float,
            y0: float,
            radius: float,
            band: float,
            color: QColor,
            rotation: float,
            alpha: int,
            mark_count: int = 3,
        ):
            # 円自体は回転しても見た目が変わらないため、一定間隔の短い弧/ノッチを回す。
            # samplesを少なめにし、軽量な疑似回転表現にする。
            p.save()
            mark_r = max(1.0, radius - band * 0.42)
            for i in range(max(1, mark_count)):
                a = rotation + i * math.tau / float(mark_count)
                span = math.tau * 0.045
                c = QColor(color)
                c.setAlpha(max(0, min(255, alpha)))
                arc = _arc_path(x0, y0, mark_r, a, span, samples=10)
                self._draw_hud_neon_path(
                    p,
                    arc,
                    c,
                    core_width=max(0.35, 0.85 * width_scale),
                    glow_scale=0.16,
                )
                # 小さなノッチ。リング幅の内側に収める。
                r0 = max(1.0, radius - band * 0.88)
                r1 = max(r0 + 1.0, radius - band * 0.10)
                notch = QPainterPath(QPointF(x0 + math.cos(a) * r0, y0 + math.sin(a) * r0))
                notch.lineTo(QPointF(x0 + math.cos(a) * r1, y0 + math.sin(a) * r1))
                self._draw_hud_neon_path(
                    p,
                    notch,
                    QColor(255, 255, 255, min(220, alpha + 50)),
                    core_width=max(0.45, 0.65 * width_scale),
                    glow_scale=0.12,
                )
            p.restore()

        def _draw_frosted_ring(
            x0: float,
            y0: float,
            radius: float,
            band: float,
            fill_alpha: int,
            edge_color: QColor,
            edge_alpha: int,
            rotation: float,
            mark_count: int,
            glow: bool = True,
        ):
            """Draw a transparent frosted ring with lightweight multi-pass mist blur."""
            path = _ring_path(x0, y0, radius, band)
            p.save()
            p.setPen(Qt.PenStyle.NoPen)

            # 霧ブラー層: 本物の画像ブラーは重くなりやすいため、
            # 半径と帯幅を少しずつ広げた低透明度リングを複数回重ねて、
            # 雲のように滲む半透明リングを軽量に作る。
            fog_color = QColor(edge_color)
            white_fog = QColor(230, 250, 255)
            fog_layers = (
                (0.22, 0.20, 0.115),
                (0.78, 0.80, 0.085),
                (0.18, 2.45, 0.060),
                (0.62, 3.15, 0.040),
                (1.10, 3.95, 0.026),
            )
            for spread_mul, band_mul, alpha_mul in fog_layers:
                spread = max(1.0, band * spread_mul)
                fog_band = max(1.0, band * band_mul)
                fog_radius = max(1.0, radius + spread * 0.34)
                c = QColor(fog_color)
                c.setAlpha(max(2, min(80, int(fill_alpha * alpha_mul))))
                p.setBrush(QBrush(c))
                p.drawPath(_ring_path(x0, y0, fog_radius, fog_band))

                wc = QColor(white_fog)
                wc.setAlpha(max(1, min(52, int(fill_alpha * alpha_mul * 0.56))))
                p.setBrush(QBrush(wc))
                p.drawPath(_ring_path(x0, y0, max(1.0, fog_radius - band * 0.18), max(1.0, fog_band * 0.54)))

            # 幅広の霧アーク。完全な円ではなく、雲の濃淡がゆっくり流れるように見せる。
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(4):
                a = rotation * (0.74 + i * 0.05) + i * math.tau / 4.0
                span = math.tau * (0.15 + 0.025 * (i % 2))
                arc = _arc_path(x0, y0, max(1.0, radius - band * (0.34 + i * 0.035)), a, span, samples=12)
                ac = QColor(edge_color)
                ac.setAlpha(max(2, min(38, int(fill_alpha * (0.070 - i * 0.008)))))
                pen = QPen(ac, max(1.0, band * (0.62 - i * 0.055)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.drawPath(arc)

            # 中心のガラス本体。前回より少し薄くし、霧層と混ざるようにする。
            p.setPen(Qt.PenStyle.NoPen)
            core_alpha = max(18, min(170, int(fill_alpha * 0.58)))
            p.setBrush(QBrush(QColor(210, 245, 255, core_alpha)))
            p.drawPath(path)

            # すりガラスの色むら。固定ベタ塗りではなく、淡い帯として残す。
            tint = QColor(edge_color)
            tint.setAlpha(max(6, min(48, int(fill_alpha * 0.18))))
            p.setBrush(QBrush(tint))
            p.drawPath(_ring_path(x0, y0, radius - band * 0.18, band * 0.30))

            # 外縁・内縁の細い光。霧化しても輪郭が完全に消えないよう弱めに残す。
            edge = QColor(edge_color)
            edge.setAlpha(max(0.05, int(edge_alpha * 0.74)))
            outer = QPainterPath()
            outer.addEllipse(QPointF(x0, y0), radius, radius)
            inner = QPainterPath()
            inner.addEllipse(QPointF(x0, y0), max(1.0, radius - band), max(1.0, radius - band))
            if glow:
                self._draw_hud_neon_path(p, outer, edge, core_width=max(0.45, 0.88 * width_scale), glow_scale=0.24)
                self._draw_hud_neon_path(p, inner, QColor(255, 255, 255, max(50, min(165, int(edge_alpha * 0.82)))), core_width=max(0.35, 0.66 * width_scale), glow_scale=0.14)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(edge, max(0.65, 0.86 * width_scale)))
                p.drawPath(outer)
                p.setPen(QPen(QColor(255, 255, 255, max(50, min(165, int(edge_alpha * 0.82)))), max(0.48, 0.62 * width_scale)))
                p.drawPath(inner)

            # 回転ノッチも霧の中に溶ける程度に弱める。
            _draw_rotating_ring_marks(
                x0,
                y0,
                radius,
                band,
                edge_color,
                rotation,
                alpha=max(2, min(120, int(edge_alpha * 0.24))),
                mark_count=mark_count,
            )
            p.restore()

        # ここからリング群全体を横から見たHUDディスクのように傾ける。
        # 8度ほど回転させつつ、縦方向を強めに圧縮してサイドビュー寄りの奥行きを作る。
        p.save()
        p.setClipRect(scene_rect.adjusted(-2, -2, 2, 2))
        p.translate(cx, cy)
        p.rotate(2.22)
        p.scale(1.0, 0.62)
        p.translate(-cx, -cy)

        # Z0: リング背後の薄いブルーム。
        halo = QRadialGradient(QPointF(cx, cy), outer_r * 1.38)
        halo.setColorAt(0.0, QColor(0, 245, 255, 34))
        halo.setColorAt(0.46, QColor(255, 42, 225, 14))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), outer_r * 1.38, outer_r * 1.38)

        # Z1: 100%のすりガラス帯状円。回転マークは最もゆっくり。
        _draw_frosted_ring(
            cx,
            cy,
            outer_r,
            main_band_w,
            fill_alpha=153,
            edge_color=cyan,
            edge_alpha=145,
            rotation=now * 0.18,
            mark_count=4,
            glow=True,
        )

        # Z2: 外側音楽バー。短く、密度高め、アクセントカラーのみ。
        bar_count = 112
        base_r = outer_r + bar_gap
        for i in range(bar_count):
            u = i / float(bar_count)
            a = u * math.tau - math.pi / 2.0
            idx = int((i / max(1, bar_count - 1)) * (count - 1))
            v = values[idx]
            pulse = 0.5 + 0.5 * math.sin(now * 2.0 + i * 0.29)
            length = short_side * (0.010 + v * 0.038 + pulse * 0.004)
            r0 = base_r
            r1 = base_r + length
            x0 = cx + math.cos(a) * r0
            y0 = cy + math.sin(a) * r0
            x1 = cx + math.cos(a) * r1
            y1 = cy + math.sin(a) * r1
            c = QColor(accent)
            c.setAlpha(100 + int(v * 92))
            bar_path = QPainterPath(QPointF(x0, y0))
            bar_path.lineTo(QPointF(x1, y1))
            self._draw_hud_neon_path(
                p,
                bar_path,
                c,
                core_width=max(0.75, (0.80 + v * 1.05) * width_scale),
                glow_scale=0.20,
            )

        # Z3: 内側30%リング。回転方向を大円と逆にする。
        inner30_r = min(outer_r * 0.30, main_inner_r * 0.40)
        inner30_band = max(5.0, inner30_r * 0.22)
        _draw_frosted_ring(
            cx,
            cy,
            inner30_r,
            inner30_band,
            fill_alpha=128,
            edge_color=green,
            edge_alpha=128,
            rotation=-now * 0.28,
            mark_count=3,
            glow=True,
        )

        # Z4: 48%リングを上方向へ3層。各層は一定間隔・一定速度差で回転。
        stack_r = min(outer_r * 0.48, main_inner_r * 0.58)
        stack_band = max(5.0, stack_r * 0.135)
        desired_gap = max(5.0, outer_r * 0.085)
        max_gap = max(5.0, (main_inner_r - stack_r - 2.0) / 2.25)
        stack_gap = min(desired_gap, max_gap)
        stack_colors = [magenta, cyan, green]
        for layer in range(3):
            y = cy - stack_gap * (2 - layer)
            x = cx + math.sin(now * 0.34 + layer * 0.8) * outer_r * 0.008
            edge = stack_colors[layer % 3]
            alpha = 82 + layer * 16
            _draw_frosted_ring(
                x,
                y,
                stack_r * (0.985 + layer * 0.012),
                stack_band,
                fill_alpha=62 + layer * 9,
                edge_color=edge,
                edge_alpha=alpha,
                rotation=now * (0.22 + layer * 0.07) + layer * math.tau / 3.0,
                mark_count=3,
                glow=True,
            )
            # 立体感用の短いハイライト。リング内側に収める。
            highlight = QPainterPath(QPointF(x - stack_r * 0.42, y - stack_r * 0.08))
            highlight.cubicTo(
                QPointF(x - stack_r * 0.18, y - stack_r * 0.18),
                QPointF(x + stack_r * 0.18, y - stack_r * 0.18),
                QPointF(x + stack_r * 0.42, y - stack_r * 0.08),
            )
            self._draw_hud_neon_path(
                p,
                highlight,
                QColor(255, 255, 255, 105),
                core_width=max(0.48, 0.62 * width_scale),
                glow_scale=0.13,
            )

        # 中央アクセントも変換内で描くので、全体の傾きに馴染む。
        p.setPen(Qt.PenStyle.NoPen)
        for k, col in enumerate((accent, cyan, green)):
            dot_r = max(1.2, short_side * (0.0040 + k * 0.0010))
            c = QColor(col)
            c.setAlpha(105 - k * 18)
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(cx + (k - 1) * dot_r * 2.7, cy), dot_r, dot_r)

        p.restore()
        p.restore()

    def _paint_visualizer_styled(self, p: QPainter, bars, style: str, r: QRectF, area: QRectF, base_color: QColor, now: float, ctx: Dict = None):
        values = [max(0.0, min(1.0, float(v))) for v in bars]
        count = max(1, len(values))
        avg, bass, mid = self._visualizer_energy(values)
        cx = area.center().x(); cy = area.center().y()
        aw = max(1.0, area.width()); ah = max(1.0, area.height())
        short_side = min(aw, ah)
        # Scale all "maximum" extents so the strongest beat remains inside the frame.
        max_effect_radius = max(2.0, short_side * 0.43)
        radius = min(short_side * (0.23 + 0.12 * bass), max_effect_radius * 0.72)
        width_scale = self._visualizer_bar_width_scale()
        glow_enabled = bool(getattr(self.cfg, "visualizer_glow_enabled", True))
        flip_vertical = bool(getattr(self.cfg, "visualizer_flip_vertical", False))
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if flip_vertical:
            # Mirror the whole styled visualizer vertically inside its own drawing area.
            p.translate(0.0, area.top() + area.bottom())
            p.scale(1.0, -1.0)
        self._paint_visualizer_depth_shadow(p, values, style, area, now, max_effect_radius, radius, avg, bass)
        self._paint_visualizer_style_glow(p, values, style, area, base_color, now, max_effect_radius, radius, avg, bass, width_scale)

        # Spec-no-line visualizer skins: no FFT bars, no waveform-line/oscilloscope/ECG/chart style.
        # Rendering uses radial capsules, filled ribbons, dots, discs, particles and closed blobs only.
        def _cap(cx0, cy0, ang0, r0, length0, w0, color0, round0=4):
            p.save(); p.translate(cx0 + math.cos(ang0)*r0, cy0 + math.sin(ang0)*r0); p.rotate(math.degrees(ang0)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color0)); p.drawRoundedRect(QRectF(0, -w0*0.5, length0, w0), round0, round0); p.restore()
        def _dot(x0, y0, r0, color0):
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color0)); p.drawEllipse(QPointF(x0,y0), r0, r0)
        def _filled_ring_blob(cx0, cy0, inner_r, outer_r, samples, color0, rot0=0.0, wobble=0.0):
            outer=[]; inner=[]
            for s in range(samples+1):
                a=s/samples*math.tau-math.pi/2+rot0
                vv=values[int((s%samples)*count/samples)%count]
                rr_outer=outer_r + vv*wobble + math.sin(now*1.3+s*0.37)*wobble*0.22
                rr_inner=inner_r + math.sin(now*0.9+s*0.31)*wobble*0.08
                outer.append(QPointF(cx0+math.cos(a)*rr_outer, cy0+math.sin(a)*rr_outer))
                inner.append(QPointF(cx0+math.cos(a)*rr_inner, cy0+math.sin(a)*rr_inner))
            path=QPainterPath(outer[0])
            for pt in outer[1:]: path.lineTo(pt)
            for pt in reversed(inner): path.lineTo(pt)
            path.closeSubpath(); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color0)); p.drawPath(path)

        if style == "bass_drop":
            sx=math.sin(now*28)*bass*short_side*0.016; sy=math.cos(now*24)*bass*short_side*0.013; ccx=cx+sx; ccy=cy+sy
            core=min(max_effect_radius*0.50, short_side*(0.22+bass*0.09))
            self._draw_visualizer_soft_orb(p,QPointF(ccx,ccy),core*1.35,QColor(base_color.red(),base_color.green(),base_color.blue(),82),44+int(bass*80))
            for k in range(38):
                ph=(k*0.618+now*0.05)%1.0; rr=core*(0.12+((k*37)%100)/100*0.70); a=ph*math.tau+math.sin(now*0.7+k)*0.18; pc=QColor(base_color); pc.setAlpha(42+int(avg*70)); _dot(ccx+math.cos(a)*rr, ccy+math.sin(a)*rr, 1.3+bass*1.7, pc)
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,180), max(1.2,2.2*width_scale))); p.drawEllipse(QPointF(ccx,ccy),core,core)
            pals=[QColor(135,60,255,175),QColor(45,150,255,175),QColor(255,70,90,175)]
            step=max(1,count//96)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2+math.sin(now*2+i*0.08)*bass*0.10; inner=core*0.94; length=short_side*(0.04+v*0.16+bass*0.11); w=max(2.0,(2.4+v*5.4)*width_scale); ci=QColor(255,255,255,135+int(v*80)); _cap(ccx,ccy,a,inner,length*0.45,w,ci); co=QColor(pals[(i//step)%3]); co.setAlpha(150+int(v*80)); _cap(ccx,ccy,a,inner+length*0.34,length*0.72,w*1.05,co)
            p.restore(); return

        if style == "melodic_vibe":
            for k in range(48):
                ph=k/48; rr=max_effect_radius*(0.05+ph*0.90); a=now*(0.15+ph*0.08)+ph*math.tau*2.8; x=cx+math.cos(a)*rr*(0.28+ph*0.55); y=cy+math.sin(a*1.11)*rr*(0.20+ph*0.42); al=max(10,int((56+avg*60)*(1-ph*0.64))); self._draw_visualizer_soft_orb(p,QPointF(x,y),short_side*(0.07+ph*0.07),QColor(255,255,255,al),al)
            ac=QColor(base_color); ac.setAlpha(34+int(avg*82)); self._draw_visualizer_soft_orb(p,QPointF(cx,cy),max_effect_radius*(0.72+bass*0.18),ac,ac.alpha())
            p.restore(); return

        if style == "alternative":
            stride=max(1,count//80); last=None
            for i in range(0,count,stride):
                raw=values[i]; x=area.left()+aw*i/max(1,count-1); y=cy+math.sin(i*0.08+now*0.82)*ah*0.16-(raw-avg)*ah*0.28; shade=210 if i%2 else 245; col=QColor(shade,shade,shade,105+int(raw*125)); w=max(3.0, aw/max(80,count)*1.4); h=5.6*width_scale; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawRoundedRect(QRectF(x-w*0.5,y-h*0.5,w,h),3,3); last=(x,y,h,col)
            if last:
                x,y,h,col=last; _dot(x,y,h*0.82,col); _dot(area.left()+aw*0.02, cy, h*0.82, QColor(240,240,240,120))
            p.restore(); return

        if style == "circle":
            core=min(radius,max_effect_radius*0.52); col=QColor(base_color); col.setAlpha(108+int(avg*80)); _filled_ring_blob(cx,cy,core*0.86,core+short_side*0.055,144,col,now*0.18,short_side*0.15); p.setBrush(Qt.BrushStyle.NoBrush); edge=QColor(base_color); edge.setAlpha(150); p.setPen(QPen(edge,max(1.0,1.5*width_scale))); p.drawEllipse(QPointF(cx,cy),core,core); p.restore(); return

        if style == "ellipse":
            rx=1.58; ry=0.54; core=min(radius,max_effect_radius*0.48); step=max(1,count//88)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2; col=QColor(base_color); col.setAlpha(130+int(v*110)); length=short_side*(0.035+v*0.16); p.save(); p.translate(cx+math.cos(a)*core*rx, cy+math.sin(a)*core*ry); p.rotate(math.degrees(a)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawRoundedRect(QRectF(0,-(1.5+v*3)*width_scale,length, (3+v*6)*width_scale),4,4); p.restore()
            p.restore(); return

        if style == "turntable":
            # 横から見たターンテーブル風。カバー外側の黒い盤面を約70px拡張し、バーをその内側へ収める。
            cover_r=max(1.0,min(max_effect_radius*0.62,short_side*0.31)*0.84-10.0)
            outer_r=min(max_effect_radius*0.98,cover_r+70.0)
            side_y_scale=0.38; tilt_degrees=-3.0
            p.save()
            try:
                p.translate(cx,cy); p.rotate(tilt_degrees); p.scale(1.0,side_y_scale); p.translate(-cx,-cy)
                grad=QRadialGradient(QPointF(cx,cy),outer_r); grad.setColorAt(0,QColor(245,248,255,235)); grad.setColorAt(0.22,QColor(base_color.red(),base_color.green(),base_color.blue(),135)); grad.setColorAt(0.56,QColor(18,20,26,235)); grad.setColorAt(1,QColor(4,5,8,245)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawEllipse(QPointF(cx,cy),outer_r,outer_r); p.setBrush(Qt.BrushStyle.NoBrush)
                for k in range(5): p.setPen(QPen(QColor(220,230,245,45+k*15),1)); p.drawEllipse(QPointF(cx,cy),cover_r*(0.34+k*0.13),cover_r*(0.34+k*0.13))
                turntable_cover_rect=QRectF(cx-cover_r,cy-cover_r,cover_r*2.0,cover_r*2.0)
                p.save()
                try:
                    p.translate(cx,cy); p.rotate(math.degrees(now*0.55)); p.translate(-cx,-cy)
                    self._draw_visualizer_media_thumbnail_cover(p,turntable_cover_rect,ctx,clip_radius=cover_r,fallback_accent=base_color)
                finally:
                    p.restore()
                step=max(1,count//74); bar_inner=min(outer_r-2.0,cover_r+8.0); bar_room=max(1.0,outer_r-bar_inner-4.0)
                for i in range(0,count,step): v=values[i]; a=i/count*math.tau-math.pi/2; _cap(cx,cy,a,bar_inner,min(bar_room,short_side*(0.025+v*0.13)),max(1.8,(2+v*4)*width_scale),QColor(230,235,245,110+int(v*110)))
            finally:
                p.restore()
            p.restore(); return

        if style == "spotlight_beat":
            for ring in range(2):
                pulse=1+bass*(0.025+ring*0.012); rx=max_effect_radius*(0.54+ring*0.22)*pulse; ry=rx*(0.45+bass*0.018); phase=now*(0.36 if ring==0 else -0.32)
                for k in range(42):
                    v=values[(k*count//42)%count]; a=k/42*math.tau+phase+math.sin(now*1.2+k*0.17)*v*0.05; stretch=1+v*4.85+bass*0.90; x=cx+math.cos(a)*rx; y=cy+math.sin(a)*ry*(-1 if ring else 1); col=QColor(base_color) if ring else QColor(245,248,255); col.setAlpha(72+int(v*175)); self._draw_visualizer_soft_orb(p,QPointF(x,y),5+v*16,col,30+int(v*78)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); bw=max(3.8,4.95*width_scale); bh=bw*stretch; p.drawRoundedRect(QRectF(x-bw/2,y-bh/2,bw,bh),3,3)
            p.restore(); return

        if style == "audio_react":
            rg=QRadialGradient(QPointF(cx,cy),max_effect_radius*0.62); rg.setColorAt(0,QColor(base_color.red(),base_color.green(),base_color.blue(),50)); rg.setColorAt(1,QColor(0,0,0,80)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(rg)); p.drawEllipse(QPointF(cx,cy),radius*1.18,radius*1.18)
            for i in range(72):
                v=values[int(i*count/72)]; a=i/72*math.tau+math.sin(now*1.6+i)*0.04; r=radius*1.08+short_side*(0.025+v*0.15); c=QColor(255,255,255,95+int(v*100)); _dot(cx+math.cos(a)*r, cy+math.sin(a)*r, 1.5+v*4, c)
            p.restore(); return

        if style == "retro_future":
            for side in (-1,1):
                for j in range(18):
                    t=j/17; y=area.bottom()-t*ah; x=cx+side*aw*0.08+math.sin(now*1.1+t*6+side)*aw*0.025; c=QColor(base_color); c.setAlpha(max(18,int((1-t)*130+avg*55))); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawRoundedRect(QRectF(x-2*width_scale,y-8*(1-t),4*width_scale,16*(1-t)+3),3,3)
            p.restore(); return

        if style == "rainbow":
            # Fine iridescent scale-powder steam version, emitted only on bar peaks.
            # Bars stay compact; particles are small flattened flakes with per-flake rainbow gradients.
            # Peak detection compares this frame against the previous frame, then keeps spawned powder alive briefly.
            slot=aw/count
            bw=max(1.0,slot*0.38*width_scale)
            particle_step=max(1,count//15)
            # Left-edge bass push: on a deep bass transient, move only the existing left bars.
            # No oscillation is added; the bars push once with the bass envelope and then return smoothly.
            prev_left_bass=float(getattr(self,"_rainbow_left_edge_prev_bass",bass))
            left_bass_rise=bass-prev_left_bass
            self._rainbow_left_edge_prev_bass=bass
            prev_left_time=float(getattr(self,"_rainbow_left_edge_last_time",now))
            left_dt=max(0.0,min(0.10,now-prev_left_time))
            self._rainbow_left_edge_last_time=now
            prev_left_push=float(getattr(self,"_rainbow_left_edge_push",0.0))
            left_edge_target=0.0
            if bass>=0.18 and left_bass_rise>=0.035:
                left_edge_target=max(0.0,min(1.0,(bass-0.18)*3.0+left_bass_rise*8.0))
            left_edge_push=0
            self._rainbow_left_edge_push=left_edge_push
            bar_tops=[]
            for i,v in enumerate(values):
                t=i/max(1,count-1)
                # Tone layout across the bar field:
                # left = low/bass, center = high/treble, right = mid/vocal-like band.
                low_idx=max(0,min(count-1,int((0.05+0.11*t)*(count-1))))
                mid_idx=max(0,min(count-1,int((0.42+0.18*t)*(count-1))))
                high_idx=max(0,min(count-1,int((0.74+0.10*(1.0-abs(t-0.5)*2.0))*(count-1))))
                low_v=values[low_idx]
                mid_v=values[mid_idx]
                high_v=values[high_idx]
                low_weight=(1.0-t)**8.55
                mid_weight=t**0.85
                high_weight=max(0.0,1.0-abs(t-0.5)*2.0)**1.80*1.65
                local_weight=0.012
                avg_weight=0.0008
                weight_sum=low_weight+mid_weight+high_weight+local_weight+avg_weight
                tone_v=max(0.0,min(1.0,(low_v*low_weight+mid_v*mid_weight+high_v*high_weight+v*local_weight+avg*avg_weight)/max(0.001,weight_sum)))
                x=area.left()+i*slot
                h=ah*(0.030+tone_v*0.340)
                left_edge_weight=max(0.0,1.0-t*5.0)**1.70
                if left_edge_push>0.001 and left_edge_weight>0.001:
                    x+=left_edge_weight*left_edge_push*slot*0.85
                c=self._rainbow_lut_color(t+now*0.050,230)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(c))
                bx=x+slot*0.31
                p.drawRoundedRect(QRectF(bx,cy-h,bw,h),3,3)
                bar_tops.append((x+slot*0.5,cy-h,t,tone_v))
                ref=QColor(c)
                ref.setAlpha(14+int(tone_v*22))
                p.setBrush(QBrush(ref))
                p.drawRoundedRect(QRectF(bx,cy+2,bw,h*0.12),3,3)

            # Spawn powder only when a sampled bar sharply rises into a peak.
            # peak_rise_threshold: larger = stricter peak-only emission; smaller = more frequent powder.
            # peak_level_threshold: larger = only taller bars emit powder.
            peak_rise_threshold=0.055
            peak_level_threshold=0.120
            peak_cooldown=0.140
            powder_life=1.01
            prev_levels=getattr(self,"_rainbow_peak_prev_levels",None)
            if not isinstance(prev_levels,list) or len(prev_levels)!=len(bar_tops):
                prev_levels=[0.0]*len(bar_tops)
            last_spawn=getattr(self,"_rainbow_peak_last_spawn",None)
            if not isinstance(last_spawn,list) or len(last_spawn)!=len(bar_tops):
                last_spawn=[-9999.0]*len(bar_tops)
            particles=getattr(self,"_rainbow_peak_particles",None)
            if not isinstance(particles,list):
                particles=[]
            for i in range(0,len(bar_tops),particle_step):
                base_x,base_y,t,tone_v=bar_tops[i]
                rise=tone_v-prev_levels[i]
                if tone_v>=peak_level_threshold and rise>=peak_rise_threshold and now-last_spawn[i]>=peak_cooldown:
                    for spark in range(6):
                        seed=(i*0.017+spark*0.109+now*0.013)%1.0
                        particles.append((now,base_x,base_y,t,tone_v,spark,seed))
                    last_spawn[i]=now
            self._rainbow_peak_prev_levels=[bt[3] for bt in bar_tops]
            self._rainbow_peak_last_spawn=last_spawn

            # Draw only particles that were born from peaks; they rise and fade after the peak.
            p.setPen(Qt.PenStyle.NoPen)
            active_particles=[]
            for birth,base_x,base_y,t,tone_v,spark,seed in particles:
                age=(now-birth)/max(0.001,powder_life)
                if age<0.0 or age>=1.0:
                    continue
                active_particles.append((birth,base_x,base_y,t,tone_v,spark,seed))
                flutter=math.sin(now*1.35+seed*17.0+spark*1.77)*slot*(0.85+age*2.35)
                flutter+=math.sin(now*2.55+seed*11.0+spark*2.63)*slot*(0.38+age*1.15)
                flutter+=math.sin(age*math.tau*2.5+spark*0.73)*slot*0.44
                px=base_x+flutter+(spark-4)*slot*0.105
                py=base_y-age*ah*(0.42+tone_v*0.30)-spark*ah*0.005+math.sin(now*1.90+i*0.11+spark)*ah*0.014
                pr=(0.65+tone_v*1.05+(spark%3)*0.885)*max(1.0,width_scale)
                angle=math.sin(now*1.65+seed*13.0+spark*0.97)*58.0+age*155.0+spark*23.0
                fade=max(0.0,1.0-age)
                alpha=max(0,int((fade*fade*fade)*230))
                hue_bucket=int(((t+spark*0.081+now*0.030+age*0.065)%1.0)*24.0)
                size_bucket=max(0,min(2,int(tone_v*3.0)))
                angle_bucket=int((angle%360.0)/22.5)%16
                sprite=self._get_rainbow_powder_sprite(hue_bucket,size_bucket,angle_bucket)
                draw_size=max(3.0,pr*4.2)
                p.save()
                p.setOpacity(max(0.0,min(1.0,alpha/255.0)))
                p.drawImage(QRectF(px-draw_size*0.5,py-draw_size*0.5,draw_size,draw_size),sprite)
                p.restore()
            self._rainbow_peak_particles=active_particles[-700:]
            p.restore(); return

        if style == "minimal":
            slot=aw/count; c=QColor(base_color); c.setAlpha(195); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c))
            for i,v in enumerate(values): h=ah*(0.025+v*0.46); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.28,cy-h/2,max(1,slot*0.44*width_scale),h),2,2)
            p.restore(); return

        if style == "urban_timelapse":
            lanes=min(18,max(8,count//5))
            for i in range(lanes): v=values[int(i*count/lanes)]; y=area.top()+ah*(0.16+i/max(1,lanes-1)*0.68); x0=area.left()+((now*(35+i*2)+i*31)%max(1,aw)); length=aw*(0.10+v*0.18); col=QColor(80,170,255,120) if i%2 else QColor(255,155,55,120); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawRoundedRect(QRectF(x0-length,y-1.5,length,3.0),2,2); _dot(x0,y+math.sin(now*2+i)*ah*0.025,2+v*3,col)
            p.restore(); return

        if style == "music_beat_wall":
            slot=aw/count
            for i,v in enumerate(values): h=ah*(0.06+v*0.76); c=QColor(base_color); c.setAlpha(102+int(v*55)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.16,area.bottom()-h,max(1,slot*0.64*width_scale),h),3,3)
            p.restore(); return

        if style == "led_audio_wave":
            rail_gap=ah*0.10; c=QColor(base_color); c.setAlpha(90); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawRoundedRect(QRectF(area.left(),cy-rail_gap-1,aw,2),1,1); p.drawRoundedRect(QRectF(area.left(),cy+rail_gap-1,aw,2),1,1)
            for i in range(0,count,max(1,count//64)):
                v=values[i]; x=area.left()+aw*i/max(1,count-1); y=cy+math.sin(i*0.15+now*1.6)*ah*0.055-(v-avg)*ah*0.20; _dot(x,y,1.4+v*2.4,QColor(base_color.red(),base_color.green(),base_color.blue(),120+int(v*70)))
            p.restore(); return

        if style == "euphoria_motion":
            for k in range(6): v=values[int(k*count/6)]; y=cy+(k-2.5)*ah*0.095+math.sin(now*3+k)*bass*ah*0.025; length=aw*(0.22+v*0.34+bass*0.10); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(250,250,255,135+int(v*100)))); p.drawRoundedRect(QRectF(cx-length/2,y-2.5*width_scale,length,5*width_scale),4,4)
            p.restore(); return

        if style == "luminance":
            self._paint_luminance_wave_scene(p, values, area, base_color, now, avg, width_scale)
            p.restore(); return

        if style == "hud_equalizer":
            self._paint_hud_equalizer_scene(p, values, area, base_color, now, width_scale)
            p.restore(); return

        if style == "space":
            for i in range(54): _dot(area.left()+((i*73+int(now*20))%int(max(1,aw))), area.top()+((i*41+int(now*8))%int(max(1,ah))), 1, QColor(150,180,255,34+(i%4)*14))
            slot=aw/count
            for i,v in enumerate(values): h=ah*(0.03+v*0.34); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255,255,255,145+int(v*80)))); x=area.left()+i*slot+slot*0.5; p.drawRoundedRect(QRectF(x-0.8*width_scale,cy-h,1.6*width_scale,h*2),2,2)
            p.restore(); return

        if style == "flat_spectrum":
            # Flat Audio Spectrum custom composition.
            # - Outer line: audio-ripple style circular waveform, copied locally so audio_ripple itself is untouched.
            # - Inner layer: hologram-style rings / radial ticks, rotated counter-clockwise only inside this style.
            # - Center: no hologram music bars; use a translucent circle instead.
            mint = QColor(base_color)
            mint.setAlpha(235)
            # Side-view transform for Flat Audio Spectrum.
            # 5.0 degrees is used for the requested overall angle; vertical scale makes it look viewed from the side.
            # These can be overridden from cfg without breaking existing configs:
            #   flat_spectrum_angle_degrees=5.0
            #   flat_spectrum_side_view_y_scale=0.22
            flat_spectrum_angle_degrees = float(getattr(self.cfg, "flat_spectrum_angle_degrees", 0.5))
            flat_spectrum_side_view_y_scale = max(0.1, min(1.0, float(getattr(self.cfg, "flat_spectrum_side_view_y_scale", 0.47))))
            p.save()
            p.translate(cx, cy)
            p.rotate(flat_spectrum_angle_degrees)
            p.scale(1.0, flat_spectrum_side_view_y_scale)
            p.translate(-cx, -cy)
            outer_base_radius = max_effect_radius * 0.70
            outer_max_radius = max_effect_radius * 0.92
            outer_min_radius = max_effect_radius * 0.54
            sample_count = max(100, min(256, count if count > 0 else 128))

            # Same restrained vocal/main-source focus as audio_ripple.
            # It uses the middle band, weakens broadband bass influence, and gates idle motion.
            half_count = max(2, sample_count // 2)
            source_count = max(1, len(values))
            mid_start = min(source_count - 1, max(0, int(source_count * 0.18)))
            mid_end = min(source_count - 1, max(mid_start + 1, int(source_count * 0.64)))
            mid_span = max(1, mid_end - mid_start)
            vocal_half = []
            for si in range(half_count):
                pos = si / max(1, half_count - 1)
                src_i = mid_start + int(pos * mid_span)
                src_i = max(0, min(source_count - 1, src_i))
                center_weight = 1.0 - min(1.0, abs(pos - 0.45) / 0.45)
                band_weight = 0.36 + center_weight * 0.64
                value = max(0.0, float(values[src_i]) - bass * 0.18)
                vocal_half.append(max(0.0, min(1.0, value * band_weight * 1.58)))

            focused_values = vocal_half + list(reversed(vocal_half))
            sample_count = len(focused_values)
            focused_peak = max(focused_values) if focused_values else 0.0
            focused_avg = sum(focused_values) / max(1, len(focused_values))
            focused_energy = focused_peak * 0.68 + focused_avg * 0.32
            previous_energy = float(getattr(self, "_flat_spectrum_focused_energy", focused_energy))

            # User-tuned settings: slower gate curve and slightly slower onset denominator.
            energy_gate = max(0.0, min(1.0, (focused_energy - 0.08) / 0.57))
            onset_gate = max(0.0, min(1.0, (focused_energy - previous_energy) / 0.18))
            target_gate = max(energy_gate, onset_gate * 0.80)
            if target_gate < 0.055:
                target_gate = 0.0
            smoothed_gate = float(getattr(self, "_flat_spectrum_focused_gate", 0.0))
            if target_gate >= smoothed_gate:
                smoothed_gate = smoothed_gate * 0.54 + target_gate * 0.46
            else:
                smoothed_gate = smoothed_gate * 0.88 + target_gate * 0.12
            if smoothed_gate < 0.035:
                smoothed_gate = 0.0
            self._flat_spectrum_focused_energy = focused_energy
            self._flat_spectrum_focused_gate = smoothed_gate

            raw_fft_values = [v * smoothed_gate for v in focused_values]
            previous_smoothed = getattr(self, "_flat_spectrum_audio_ripple_smoothed", None)
            if not isinstance(previous_smoothed, list) or len(previous_smoothed) != sample_count:
                previous_smoothed = list(raw_fft_values)
            temporal_smoothed = []
            for si, current_value in enumerate(raw_fft_values):
                if current_value >= previous_smoothed[si]:
                    temporal_smoothed.append(previous_smoothed[si] * 0.70 + current_value * 0.30)
                else:
                    temporal_smoothed.append(previous_smoothed[si] * 0.90 + current_value * 0.10)
            self._flat_spectrum_audio_ripple_smoothed = temporal_smoothed
            fft_values = []
            for si, current_value in enumerate(temporal_smoothed):
                fft_values.append(
                    temporal_smoothed[si - 2] * 0.10
                    + temporal_smoothed[si - 1] * 0.20
                    + current_value * 0.40
                    + temporal_smoothed[(si + 1) % sample_count] * 0.20
                    + temporal_smoothed[(si + 2) % sample_count] * 0.10
                )
            local_peak = max(raw_fft_values) if raw_fft_values else 0.0
            smoothed_peak = max(fft_values) if fft_values else 0.0
            volume_peak_gate = max(0.0, min(1.0, (max(local_peak, smoothed_peak, bass, avg) - 0.58) / 0.42))
            available_push = max(8.0, outer_max_radius - outer_base_radius)
            outer_points = []
            white_spark_points = []
            for si, fft_value in enumerate(fft_values):
                sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(si, sample_count)
                angle = -math.pi / 2.0 + (si / sample_count) * math.tau
                prev_v = fft_values[si - 1]
                next_v = fft_values[(si + 1) % sample_count]
                local_contrast = max(0.0, fft_value - (prev_v + next_v) * 0.5)
                spike_gate = max(0.0, min(1.0, (fft_value - 0.64) / 0.36))
                mirror_i = min(si, sample_count - 1 - si)
                seed = ((mirror_i * 37 + 13) % 97) / 97.0
                raw_value = raw_fft_values[si]
                raw_prev = raw_fft_values[si - 1]
                raw_next = raw_fft_values[(si + 1) % sample_count]
                raw_contrast = max(0.0, raw_value - (raw_prev + raw_next) * 0.5)
                transient_gate = max(0.0, min(1.0, (raw_value - temporal_smoothed[si]) / 0.16))
                level_gate = max(0.0, min(1.0, (raw_value - 0.055) / 0.34))
                peak_gate = max(0.0, min(1.0, volume_peak_gate)) * smoothed_gate
                audio_reactivity = max(transient_gate * 1.10, spike_gate * smoothed_gate, level_gate * 1.28, peak_gate * 0.22)
                audio_reactivity = max(0.0, min(1.0, audio_reactivity))
                audio_reactivity = audio_reactivity * audio_reactivity
                tip_speed = 0.32 + seed * 0.22 + audio_reactivity * 0.55
                snap_cycle = now * tip_speed + seed * 5.0 + mirror_i * 0.031
                snap_phase = snap_cycle - math.floor(snap_cycle)
                if snap_phase < 0.050:
                    snap_envelope = snap_phase / 0.050
                elif snap_phase < 0.210:
                    snap_envelope = 1.0 - (snap_phase - 0.050) / 0.160
                else:
                    snap_envelope = 0.0
                snap_envelope = max(0.0, min(1.0, snap_envelope)) * audio_reactivity
                snap_index = int(math.floor(snap_cycle))
                tip_sign = -1.0 if ((snap_index + mirror_i * 3) % 5) < 2 else 1.0
                tip_energy = max(raw_value, raw_contrast * 3.2, local_contrast * 2.4, spike_gate)
                tip_amount = tip_energy * available_push * (0.12 + 0.52 * audio_reactivity) * snap_envelope
                rr = max(outer_min_radius, min(outer_base_radius + tip_sign * tip_amount, outer_max_radius))
                point = QPointF(cx + cos_a * rr, cy + sin_a * rr)
                outer_points.append(point)

                # Spark follows the added white outer line and appears only on real jagged snaps.
                spark_strength = snap_envelope * audio_reactivity * max(0.0, min(0.36, tip_amount / max(1.0, available_push * 0.22)))
                if spark_strength > 0.30:
                    spark_radius = rr + 2.0
                    white_spark_points.append((
                        QPointF(cx + cos_a * spark_radius, cy + sin_a * spark_radius),
                        angle,
                        max(0.0, min(1.0, spark_strength)),
                        seed,
                    ))
            if outer_points:
                outer_path = QPainterPath(outer_points[0])
                for pt in outer_points[1:]:
                    outer_path.lineTo(pt)
                outer_path.closeSubpath()
                def _make_outer_offset_path(offset):
                    offset_path = QPainterPath()
                    first = outer_points[0]
                    first_len = max(1.0, math.hypot(first.x() - cx, first.y() - cy))
                    offset_path.moveTo(QPointF(first.x() + (first.x() - cx) / first_len * offset, first.y() + (first.y() - cy) / first_len * offset))
                    for pt in outer_points[1:]:
                        plen = max(1.0, math.hypot(pt.x() - cx, pt.y() - cy))
                        offset_path.lineTo(QPointF(pt.x() + (pt.x() - cx) / plen * offset, pt.y() + (pt.y() - cy) / plen * offset))
                    offset_path.closeSubpath()
                    return offset_path

                for offset, alpha_scale in ((-3.0, 0.22), (3.0, 0.16)):
                    offset_path = _make_outer_offset_path(offset)
                    trail_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), int(32 * alpha_scale)), max(1.0, 1.25 * width_scale))
                    trail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    trail_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(trail_pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(offset_path)
                glow_pen_1 = QPen(QColor(mint.red(), mint.green(), mint.blue(), 20), max(8.0, 8.0 * width_scale + bass * 4.0))
                glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_1)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(outer_path)
                glow_pen_2 = QPen(QColor(mint.red(), mint.green(), mint.blue(), 40), max(5.0, 5.0 * width_scale + bass * 2.0))
                glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_2)
                p.drawPath(outer_path)

                # Second white line, placed 2 px outside the flat-spectrum outer ripple.
                white_outer_path = _make_outer_offset_path(2.0)
                white_glow_pen_1 = QPen(QColor(255, 255, 255, 40), max(7.0, 8.5 * width_scale + smoothed_gate * 3.0))
                white_glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_1)
                p.drawPath(white_outer_path)
                white_glow_pen_2 = QPen(QColor(255, 255, 255, 72), max(3.6, 4.5 * width_scale + smoothed_gate * 1.6))
                white_glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_2)
                p.drawPath(white_outer_path)
                white_pen = QPen(QColor(255, 255, 255, 238), max(1.2, 2.0 * width_scale))
                white_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_pen)
                p.drawPath(white_outer_path)

                core_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), 255), max(1.4, 2.0 * width_scale))
                core_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                core_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(core_pen)
                p.drawPath(outer_path)

                if white_spark_points:
                    for spark_pt, spark_angle, spark_strength, spark_seed in white_spark_points:
                        spark_alpha = max(0, min(255, int(70 + spark_strength * 185)))
                        spark_size = short_side * (0.006 + spark_strength * 0.012)
                        self._draw_visualizer_soft_orb(p, spark_pt, spark_size * 2.8, QColor(255, 255, 255, spark_alpha), spark_alpha)
                        spark_sin, spark_cos = self._flat_spectrum_sin_cos_from_angle(spark_angle)
                        radial = QPointF(spark_cos, spark_sin)
                        tangent = QPointF(-spark_sin, spark_cos)
                        ray_len = spark_size * (1.45 + spark_strength * 1.35)
                        ray_alpha = max(0, min(255, int(105 + spark_strength * 125)))
                        ray_pen = QPen(QColor(255, 255, 255, ray_alpha), max(0.7, 1.15 * width_scale))
                        ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(ray_pen)
                        p.drawLine(
                            QPointF(spark_pt.x() - radial.x() * ray_len, spark_pt.y() - radial.y() * ray_len),
                            QPointF(spark_pt.x() + radial.x() * ray_len, spark_pt.y() + radial.y() * ray_len),
                        )
                        p.drawLine(
                            QPointF(spark_pt.x() - tangent.x() * ray_len * 0.62, spark_pt.y() - tangent.y() * ray_len * 0.62),
                            QPointF(spark_pt.x() + tangent.x() * ray_len * 0.62, spark_pt.y() + tangent.y() * ray_len * 0.62),
                        )

            flat_spectrum_rotation_degrees = self._flat_spectrum_inner_rotation_degrees(now)
            flat_spectrum_rotation_degrees2 = self._flat_spectrum_inner_rotation_degrees2(now)
            p.save()
            try:
                p.translate(cx, cy)
                p.rotate(flat_spectrum_rotation_degrees)
                p.translate(-cx, -cy)
                static_hologram_image, static_hologram_radius = self._flat_spectrum_static_hologram_image(max_effect_radius, base_color, width_scale)
                if static_hologram_image is not None and static_hologram_radius > 0:
                    p.drawImage(
                        QRectF(
                            cx - static_hologram_radius,
                            cy - static_hologram_radius,
                            static_hologram_radius * 2,
                            static_hologram_radius * 2,
                        ),
                        static_hologram_image,
                    )
                hologram_outer_circle_radius = max_effect_radius * 0.53
                hologram_max_bar_overhang_px = 50.0
                hologram_inner_bar_alpha = 210
                hologram_outer_bar_alpha = int(255 * 0.40)
                for hi in range(0, count, max(1, count // 72)):
                    v = values[hi]
                    sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(hi, count)
                    base_inner = max_effect_radius * 0.44
                    max_outer = hologram_outer_circle_radius + hologram_max_bar_overhang_px
                    max_len = min(40.0, max(3.0, max_outer - base_inner))
                    min_bar_len = min(max_len, max(2.0, short_side * 0.025))
                    max_bar_len = max(min_bar_len, max_len)
                    threshold = max(0.12, avg * 1.20)
                    band_signal = max(float(v), bass * 0.72)
                    peak_amount = max(0.0, min(1.0, (band_signal - threshold) / max(0.001, 1.0 - threshold)))
                    peak_amount = peak_amount * peak_amount * (3.0 - 2.0 * peak_amount)
                    wave = 0.92 + 0.08 * math.sin(now * (2.8 + peak_amount * 3.0) + hi * 0.31)
                    motion = max(0.0, min(1.0, peak_amount * wave))
                    bar_len = min(max_len, min_bar_len + (max_bar_len - min_bar_len) * motion)
                    inner = base_inner
                    outer = min(max_outer, inner + bar_len)
                    if outer <= inner:
                        continue
                    steps = max(1, int(math.ceil(outer - inner)))
                    pen_width = max(1.4, min(5.0, 2.6 * width_scale))
                    for hs in range(steps):
                        r1 = inner + hs
                        r2 = min(outer, inner + hs + 1.0)
                        if r2 <= r1:
                            continue
                        t = hs / max(1, steps - 1)
                        alpha = int(hologram_inner_bar_alpha * (1.0 - t) + hologram_outer_bar_alpha * t)
                        c = QColor(base_color)
                        c.setAlpha(alpha)
                        p.setPen(QPen(c, pen_width))
                        p.drawLine(QPointF(cx + cos_a * r1, cy + sin_a * r1), QPointF(cx + cos_a * r2, cy + sin_a * r2))
            finally:
                p.restore()

            center_radius = max(5.0, max_effect_radius * 0.23)

            # Flat Spectrum cover layer:
            #   bottom: translucent accent field
            #   middle: current media cover image
            #   top/surrounding: hologram music bars and outer spectrum line
            # The cover now reaches from just under the music bars down through the center circle.
            cover_outer_radius = max(center_radius + 2.0, max_effect_radius * 0.44 - 10.0)
            cover_grad = QRadialGradient(QPointF(cx, cy), cover_outer_radius)
            cover_grad.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 78))
            cover_grad.setColorAt(0.58, QColor(base_color.red(), base_color.green(), base_color.blue(), 42))
            cover_grad.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 16))
            p.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 92), max(1.0, 1.0 * width_scale)))
            p.setBrush(QBrush(cover_grad))
            p.drawEllipse(QPointF(cx, cy), cover_outer_radius, cover_outer_radius)

            cover_rect = QRectF(
                cx - cover_outer_radius,
                cy - cover_outer_radius,
                cover_outer_radius * 2.0,
                cover_outer_radius * 2.0,
            )
            # Rotate the cover image with the same angle used by the flat-spectrum music bars.
            # The circular clip stays centered; only the artwork inside visually spins with the bars.
            p.save()
            try:
                p.translate(cx, cy)
                p.rotate(flat_spectrum_rotation_degrees2)
                p.translate(-cx, -cy)
                has_cover_image = self._draw_visualizer_media_thumbnail_cover(
                    p,
                    cover_rect,
                    ctx,
                    clip_radius=cover_outer_radius,
                    fallback_accent=mint,
                )
            finally:
                p.restore()

            # Keep a subtle center-circle accent when a cover exists, but do not hide the artwork.
            if has_cover_image:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 42), max(1.0, 1.0 * width_scale)))
                p.drawEllipse(QPointF(cx, cy), center_radius, center_radius)
            p.restore()
            p.restore(); return

        if style == "dynamic_glitch":
            for k in range(48):
                v=values[int(k*count/48)]; x=area.left()+((aw*k/48-(now*34%max(1,aw)))%aw); y=cy+((-1)**k)*ah*(0.025+v*0.20); c=self._rainbow_color(k/48+now*0.02,90,0.55,0.8); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawPolygon([QPointF(x-5,y),QPointF(x,y-4-v*8),QPointF(x+5,y),QPointF(x,y+4+v*8)])
            p.restore(); return

        if style == "cyber":
            base_y=area.top()+ah*0.28; slot=aw/count
            for i,v in enumerate(values): x=area.left()+i*slot; col=self._rainbow_color(i/count*0.85+now*0.035,150+int(v*80),0.85,1.0); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); h=ah*(0.04+v*0.55); p.drawRoundedRect(QRectF(x-slot*0.25,base_y, max(1,slot*0.5), h),2,2); 
            for i in range(0,count,max(1,count//36)):
                v=values[i]; x=area.left()+i*slot; age=(now*0.65+i*0.021)%1.0; pc=self._rainbow_color(i/count+now*0.035,int((1-age)*120)); _dot(x,base_y+ah*(0.04+v*0.55)+age*ah*0.16,1.5+v*2,pc)
            p.restore(); return

        if style == "aurora":
            # Fast aurora: one continuous translucent light cloth.
            # A faint rainbow minimal spectrum is composited above it at 40% opacity.
            # No per-frame bitmap allocation, no independent aurora bars.
            sky_grad = QLinearGradient(QPointF(area.left(), area.top()), QPointF(area.left(), area.bottom()))
            sky_grad.setColorAt(0.00, QColor(3, 8, 20, 72))
            sky_grad.setColorAt(0.42, QColor(7, 18, 36, 34))
            sky_grad.setColorAt(1.00, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(sky_grad)); p.drawRect(area)

            slow_t = now * 0.075
            final_opacity = 0.42
            edge_blur_px = max(5.0, short_side * 0.15)
            middle_blur_px = max(12.0, short_side * 0.42)
            core_blur_px = max(16.0, short_side * 0.56)
            fft_shift = (avg - 0.5) * max(0.8, short_side * 0.004)
            phase_shift = math.sin(slow_t * 0.22) * max(1.4, short_side * 0.016) + fft_shift
            aurora_colors = [
                QColor(72, 255, 168, 178), QColor(132, 255, 122, 172), QColor(255, 238, 96, 158),
                QColor(255, 170, 84, 150), QColor(255, 96, 112, 146), QColor(180, 118, 255, 152),
                QColor(84, 210, 255, 166), QColor(92, 245, 220, 174),
            ]

            sample_count = 48
            base_top = area.top() + ah * 0.105
            cloth_height = ah * 0.72
            top_points = []
            bottom_points = []
            for i in range(sample_count):
                t = i / max(1, sample_count - 1)
                x = area.left() + t * aw + phase_shift
                wave_a = math.sin(t * math.tau * 1.05 + slow_t * 0.30) * ah * 0.034
                wave_b = math.sin(t * math.tau * 1.75 - slow_t * 0.20) * ah * 0.009
                y_top = base_top + wave_a + wave_b
                y_bottom = y_top + cloth_height + math.sin(t * math.tau * 1.05 + slow_t * 0.30 + 1.2) * ah * 0.011
                top_points.append(QPointF(x, y_top)); bottom_points.append(QPointF(x, y_bottom))
            cloth_path = QPainterPath(); cloth_path.moveTo(top_points[0])
            for pt in top_points[1:]: cloth_path.lineTo(pt)
            for pt in reversed(bottom_points): cloth_path.lineTo(pt)
            cloth_path.closeSubpath()

            cloth_grad = QLinearGradient(QPointF(area.left(), area.top()), QPointF(area.right(), area.top()))
            n = len(aurora_colors)
            for i, col in enumerate(aurora_colors):
                pos = i / max(1, n - 1); cloth_grad.setColorAt(pos, QColor(col))
                if i < n - 1:
                    nxt = aurora_colors[i + 1]
                    mid = QColor(int((col.red()+nxt.red())*0.5), int((col.green()+nxt.green())*0.5), int((col.blue()+nxt.blue())*0.5), int((col.alpha()+nxt.alpha())*0.5))
                    cloth_grad.setColorAt((pos + (i + 1) / max(1, n - 1)) * 0.5, mid)

            inner_top=[]; inner_bottom=[]
            for i in range(sample_count):
                t = i / max(1, sample_count - 1)
                x = area.left() + t * aw + phase_shift
                wave_a = math.sin(t * math.tau * 1.05 + slow_t * 0.30) * ah * 0.034
                wave_b = math.sin(t * math.tau * 1.75 - slow_t * 0.20) * ah * 0.009
                y_top = base_top + ah * 0.20 + wave_a * 0.55 + wave_b * 0.45
                y_bottom = y_top + cloth_height * 0.42
                inner_top.append(QPointF(x, y_top)); inner_bottom.append(QPointF(x, y_bottom))
            core_path = QPainterPath(); core_path.moveTo(inner_top[0])
            for pt in inner_top[1:]: core_path.lineTo(pt)
            for pt in reversed(inner_bottom): core_path.lineTo(pt)
            core_path.closeSubpath()
            core_grad = QLinearGradient(QPointF(area.left(), area.top()), QPointF(area.right(), area.top()))
            for i, col in enumerate(aurora_colors):
                pos = i / max(1, n - 1); c = QColor(col); c.setAlpha(min(210, int(col.alpha()*1.18))); core_grad.setColorAt(pos, c)
                if i < n - 1:
                    nxt=aurora_colors[i+1]
                    mid=QColor(int((col.red()+nxt.red())*0.5), int((col.green()+nxt.green())*0.5), int((col.blue()+nxt.blue())*0.5), min(210, int((col.alpha()+nxt.alpha())*0.62)))
                    core_grad.setColorAt((pos + (i + 1) / max(1, n - 1)) * 0.5, mid)

            def _draw_path_offset(path0, brush0, dx0, dy0, opacity0):
                p.save(); p.setOpacity(opacity0); p.translate(dx0, dy0); p.setBrush(QBrush(brush0)); p.setPen(Qt.PenStyle.NoPen); p.drawPath(path0); p.restore()

            for dx, dy, op in [(-edge_blur_px,0,0.070),(edge_blur_px,0,0.070),(-edge_blur_px*0.55,0,0.050),(edge_blur_px*0.55,0,0.050),(0,-edge_blur_px*0.18,0.035),(0,edge_blur_px*0.18,0.035)]:
                _draw_path_offset(cloth_path, cloth_grad, dx, dy, op)
            p.save(); p.setClipRect(QRectF(area.left()+aw*0.08, area.top(), aw*0.84, ah))
            for dx, dy, op in [(-middle_blur_px,0,0.052),(middle_blur_px,0,0.052),(-middle_blur_px*0.62,0,0.042),(middle_blur_px*0.62,0,0.042),(-middle_blur_px*0.35,0,0.034),(middle_blur_px*0.35,0,0.034)]:
                _draw_path_offset(cloth_path, cloth_grad, dx, dy, op)
            for dx, dy, op in [(-core_blur_px,0,0.070),(core_blur_px,0,0.070),(-core_blur_px*0.62,0,0.054),(core_blur_px*0.62,0,0.054),(-core_blur_px*0.35,0,0.044),(core_blur_px*0.35,0,0.044)]:
                _draw_path_offset(core_path, core_grad, dx, dy, op)
            p.restore()

            p.save(); p.setOpacity(final_opacity); p.setBrush(QBrush(cloth_grad)); p.setPen(Qt.PenStyle.NoPen)
            # User-tuned faster sway: keeps the cloth visibly alive without using height/bar motion.
            p.translate(math.sin(slow_t * 10.00) * max(1.0, edge_blur_px * 0.10), 0.0); p.drawPath(cloth_path); p.restore()

            # Minimal-style rainbow spectrum overlay at 40% opacity, drawn above the aurora cloth.
            # This restores the music-spectrum identity without turning the aurora itself back into bars.
            p.save(); p.setOpacity(0.40); p.setPen(Qt.PenStyle.NoPen)
            overlay_count = min(count, 72)
            slot = aw / max(1, overlay_count)
            overlay_palette = [
                QColor(255, 80, 120, 210), QColor(255, 160, 70, 210), QColor(255, 235, 80, 210),
                QColor(120, 255, 120, 210), QColor(80, 230, 255, 210), QColor(110, 150, 255, 210),
                QColor(210, 110, 255, 210),
            ]
            for i in range(overlay_count):
                src_i = int(i * count / max(1, overlay_count))
                v = values[src_i]
                col = QColor(overlay_palette[i % len(overlay_palette)])
                # Minimal effect: short, centered rounded bars. Keep it subtle and semi-transparent.
                h = ah * (0.018 + v * 0.24)
                x = area.left() + i * slot + slot * 0.31
                y = cy - h * 0.5
                bw = max(1.0, slot * 0.38 * width_scale)
                p.setBrush(QBrush(col))
                p.drawRoundedRect(QRectF(x, y, bw, h), 2.0, 2.0)
            p.restore()

            glow = QLinearGradient(QPointF(area.left(), area.top()+ah*0.30), QPointF(area.left(), area.top()+ah*0.84))
            glow.setColorAt(0.00, QColor(base_color.red(), base_color.green(), base_color.blue(), 0))
            glow.setColorAt(0.48, QColor(base_color.red(), base_color.green(), base_color.blue(), 12 + int(avg * 8)))
            glow.setColorAt(1.00, QColor(0,0,0,0))
            p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen); p.drawRect(QRectF(area.left(), area.top()+ah*0.28, aw, ah*0.58))
            p.restore(); return

        if style == "hologram":
            inv=QColor(255-base_color.red(),255-base_color.green(),255-base_color.blue(),105); acc=QColor(base_color); acc.setAlpha(105); rg=QRadialGradient(QPointF(cx,cy),max_effect_radius*0.62); rg.setColorAt(0,QColor(0,0,0,78)); rg.setColorAt(0.5,QColor(base_color.red(),base_color.green(),base_color.blue(),45)); rg.setColorAt(1,QColor(base_color.red(),base_color.green(),base_color.blue(),0)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(rg)); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.55,max_effect_radius*0.55); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(acc,1.4*width_scale)); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.45,max_effect_radius*0.45); p.setPen(QPen(inv,1.0*width_scale)); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.58,max_effect_radius*0.58)
            hologram_outer_circle_radius=max_effect_radius*0.58
            hologram_max_bar_overhang_px=10.0
            hologram_inner_bar_alpha=235
            hologram_outer_bar_alpha=int(255*0.40)
            for i in range(0,count,max(1,count//72)):
                v=values[i]
                a=i/count*math.tau-math.pi/2
                base_inner=max_effect_radius*0.48
                max_outer=hologram_outer_circle_radius+hologram_max_bar_overhang_px
                max_len=max(0.0,max_outer-base_inner)
                min_bar_len=min(max_len,max(2.0,short_side*0.025))
                max_bar_len=max(min_bar_len,max_len)
                threshold=max(0.12,avg*1.20)
                band_signal=max(float(v),bass*0.72)
                peak_amount=max(0.0,min(1.0,(band_signal-threshold)/max(0.001,1.0-threshold)))
                peak_amount=peak_amount*peak_amount*(3.0-2.0*peak_amount)
                wave=0.92+0.08*math.sin(now*(2.8+peak_amount*3.0)+i*0.31)
                motion=max(0.0,min(1.0,peak_amount*wave))
                bar_len=min(max_len,min_bar_len+(max_bar_len-min_bar_len)*motion)
                inner=base_inner
                outer=min(max_outer,inner+bar_len)
                if outer <= inner:
                    continue
                steps=max(1,int(math.ceil(outer-inner)))
                pen_width=max(7.0,min(5.0,2.6*width_scale))
                for s in range(steps):
                    r1=inner+s
                    r2=min(outer,inner+s+1.0)
                    if r2 <= r1:
                        continue
                    t=s/max(1,steps-1)
                    alpha=int(hologram_inner_bar_alpha*(1.0-t)+hologram_outer_bar_alpha*t)
                    c=QColor(base_color)
                    c.setAlpha(alpha)
                    p.setPen(QPen(c,pen_width))
                    p.drawLine(QPointF(cx+math.cos(a)*r1,cy+math.sin(a)*r1),QPointF(cx+math.cos(a)*r2,cy+math.sin(a)*r2))
            hologram_inner_circle_radius=max_effect_radius*0.45

            # Hologram center layer order:
            #   bottom: translucent accent-color hologram field and rings above
            #   middle: current media cover image, fitted 10px inside the center circle
            #   top: center music bars drawn below
            hologram_cover_inset=min(10.0,max(0.0,hologram_inner_circle_radius-2.0))
            hologram_cover_radius=max(1.0,hologram_inner_circle_radius-hologram_cover_inset)
            hologram_cover_rect=QRectF(
                cx-hologram_cover_radius,
                cy-hologram_cover_radius,
                hologram_cover_radius*2.0,
                hologram_cover_radius*2.0,
            )
            self._draw_visualizer_media_thumbnail_cover(
                p,
                hologram_cover_rect,
                ctx,
                clip_radius=hologram_cover_radius,
                fallback_accent=acc,
            )

            center_bar_limit=max(1.0,hologram_inner_circle_radius-5.0)
            center_span_width=center_bar_limit*2.0
            center_bars=max(3,int(count*center_span_width/max(1.0,aw)))
            center_slot=center_span_width/center_bars
            center_bar_w=max(1.0,center_slot*0.28*width_scale)
            for j in range(center_bars):
                src_i=min(count-1,int(j*count/max(1,center_bars)))
                v=values[src_i]
                x=cx-center_bar_limit+j*center_slot+(center_slot-center_bar_w)*0.5
                bar_center_x=x+center_bar_w*0.5
                bar_edge_dx=abs(bar_center_x-cx)+center_bar_w*0.5
                max_inner_circle_h=2.0*math.sqrt(max(0.0,center_bar_limit*center_bar_limit-bar_edge_dx*bar_edge_dx))
                h=min(max_inner_circle_h,ah*(0.018+v*0.24))
                c=QColor(255,255,255,75+int(v*70))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(c))
                p.drawRoundedRect(QRectF(x,cy-h/2,center_bar_w,h),2,2)
            p.restore(); return

        if style == "nebula":
            c=QColor(base_color); c.setAlpha(105)
            for k in range(64):
                t=k/63; x=area.left()+aw*t; y=cy+math.sin(t*math.tau*1.7+now*0.8)*ah*0.14-(values[int(t*(count-1))]-avg)*ah*0.25; rr=2.4*(1-abs(t-0.5))+1.1; _dot(x,y,rr,c)
            idx=int((now*18)%64); ox=area.left()+aw*idx/63; oy=cy+math.sin(idx/63*math.tau*1.7+now*0.8)*ah*0.14; self._draw_visualizer_soft_orb(p,QPointF(ox,oy),7+avg*14,QColor(255,255,255,165),105)
            for k in range(36): _dot(area.left()+((k*53+int(now*8))%int(max(1,aw))), area.top()+((k*31+int(now*18))%int(max(1,ah))), 1.2+(k%3)*0.45, QColor(255,255,255,60+(k%5)*18))
            p.restore(); return

        if style == "matrix":
            bg=QLinearGradient(QPointF(area.left(),area.top()),QPointF(area.left(),area.bottom())); bg.setColorAt(0,QColor(0,35,14,80)); bg.setColorAt(1,QColor(0,8,5,120)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bg)); p.drawRect(area); fs=max(8,min(14,int(ah/14))); p.setFont(QFont("Consolas",fs)); cols=max(10,min(44,int(aw/max(8,fs*0.75))))
            for cidx in range(cols):
                base_x=area.left()+cidx*aw/max(1,cols-1); drop=(now*7+cidx*19)%max(1,ah+fs*7)-fs*5; swirl=math.sin(cidx*0.42+now*0.35)*avg*short_side*0.08
                for r in range(9):
                    y=area.top()+drop+r*fs*1.25; x=base_x+(swirl*math.cos((y-cy)/max(1,short_side)*math.pi) if abs(y-cy)<short_side*0.22 else 0); p.setPen(QColor(120,255,150,max(28,145-r*13))); p.drawText(QPointF(x,y),"01"[(cidx+r+int(now*0.7))%2])
            p.restore(); return

        if style == "audio_tunnel":
            for k in range(8):
                c=self._rainbow_color(k*0.12+now*0.04,105); rr=max_effect_radius*(0.15+k*0.036)
                for s in range(0,80,3):
                    a=s/80*math.tau+now*(0.25+k*0.02); wig=math.sin(s*0.31+now*2+k)*short_side*0.016; _dot(cx+math.cos(a)*(rr+wig),cy+math.sin(a)*(rr+wig),1.1,c)
            for i in range(0,count,max(1,count//72)):
                v=values[i]; a=i/count*math.tau-math.pi/2+now*0.22
                for band,sign in [(0.46,-1),(0.64,1)]: col=self._rainbow_color(i/count+now*0.08,175); _cap(cx,cy,a,max_effect_radius*band,sign*short_side*(0.035+v*0.18),max(1.8,(2+v*5)*width_scale),col)
            p.restore(); return

        if style == "audio_tunnel_sphere":
            pulse=1+avg*0.045+bass*0.025; r=max_effect_radius*0.48*pulse; edge=QColor(base_color); edge.setAlpha(145); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(edge,max(2,3.2*width_scale))); p.drawEllipse(QPointF(cx,cy),r,r)
            for lat in range(-4,5): rr=r*math.cos(lat/5*math.pi/2); y=cy+math.sin(lat/5*math.pi/2)*r*0.72+math.sin(now*0.35+lat)*3; p.setPen(QPen(QColor(base_color.red(),base_color.green(),base_color.blue(),55),1)); p.drawEllipse(QPointF(cx,y),abs(rr),abs(rr)*0.22)
            for k in range(84): a=k/84*math.tau+now*0.28; rr=r*(0.18+(k%13)/13*0.76); y=cy+math.sin(a+now*0.2)*rr*0.62; x=cx+math.cos(a)*rr; _dot(x,y,1.35,QColor(base_color.red(),base_color.green(),base_color.blue(),64))
            p.restore(); return

        if style == "neon_tunnel_wire":
            shapes=[3,4,6,5]
            for depth in range(7):
                t=depth/6; scale=1-t*0.74; sides=shapes[depth%4]; phase=now*(0.42+t*0.15)+depth*0.7; col=QColor(base_color); col.setAlpha(int(55+105*(1-t)+bass*50))
                for k in range(sides):
                    a=k/sides*math.tau+phase; x=cx+math.cos(a)*aw*0.38*scale; y=cy+math.sin(a)*ah*0.32*scale; _dot(x,y,max(1.5,(4-2*t)*width_scale),col)
                    if bass>0.35 and depth%2==0: _dot(x,y,max(2.5,(6-3*t)*width_scale),QColor(255,255,255,120))
            p.restore(); return

        if style == "neon_soundwave":
            for k in range(3): rr=max_effect_radius*(0.26+k*0.15); col=QColor(base_color); col.setAlpha(68); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(col,max(1,(2-k*0.25)*width_scale))); p.drawEllipse(QPointF(cx,cy),rr,rr)
            neon_cover_radius=max(1.0,max_effect_radius*0.53)
            neon_cover_rect=QRectF(cx-neon_cover_radius,cy-neon_cover_radius,neon_cover_radius*2.0,neon_cover_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,neon_cover_rect,ctx,clip_radius=neon_cover_radius,fallback_accent=base_color)
            for i in range(0,count,max(1,count//72)): v=values[i]; a=i/count*math.tau-math.pi/2+now*0.38; col=QColor(base_color); col.setAlpha(100+int(v*70)); _cap(cx,cy,a,max_effect_radius*0.53,short_side*(0.035+v*0.17),max(1.6,(2+v*4)*width_scale),col); _dot(cx+math.cos(a)*max_effect_radius*0.73,cy+math.sin(a)*max_effect_radius*0.73,2,QColor(base_color.red(),base_color.green(),base_color.blue(),70))
            p.restore(); return

        if style == "glow_beat_music":
            glow_cover_radius=max(1.0,max_effect_radius*0.46)
            glow_cover_rect=QRectF(cx-glow_cover_radius,cy-glow_cover_radius,glow_cover_radius*2.0,glow_cover_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,glow_cover_rect,ctx,clip_radius=glow_cover_radius,fallback_accent=base_color)
            for k in range(60): ph=(k*0.618+now*0.9)%1; a=k*2.399+now*0.3; rr=max_effect_radius*0.08+ph*max_effect_radius*0.55; _dot(cx+math.cos(a)*rr,cy+math.sin(a)*rr,1.1+ph*1.4,QColor(255,255,255,max(0,int((1-ph)*140))))
            for i in range(0,count,max(1,count//84)): v=values[i]; a=i/count*math.tau-math.pi/2; col=QColor(255,255,255,82+int(v*120)); _cap(cx,cy,a,max_effect_radius*0.46,short_side*(0.04+v*0.23),max(1.8,(2.5+v*5)*width_scale),col); _dot(cx+math.cos(a)*(max_effect_radius*0.46-5),cy+math.sin(a)*(max_effect_radius*0.46-5),1.6,QColor(255,255,255,70+int(v*80)))
            p.restore(); return

        if style == "enigmatic_echo_sound":
            slot=aw/count; bar_w=max(2,8*width_scale); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255,255,255,205)))
            for i,v in enumerate(values): boost=1.35 if i<count*0.22 or i>count*0.78 else 0.82; h=ah*(0.05+v*0.74*boost); x=area.left()+i*slot+slot*0.5-bar_w/2; p.drawRoundedRect(QRectF(x,cy-h/2,bar_w,h),3,3)
            p.restore(); return

        if style == "reactive_lights":
            reactive_center_radius=max_effect_radius*0.25
            cr=QRadialGradient(QPointF(cx,cy),max_effect_radius*0.28); cr.setColorAt(0,QColor(255,255,255,120)); cr.setColorAt(1,QColor(255,255,255,20)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(cr)); p.drawEllipse(QPointF(cx,cy),reactive_center_radius,reactive_center_radius)

            # Reactive Lights cover layer:
            #   bottom: existing translucent white center circle
            #   middle: current media cover image on the white circle
            #   top: radial reactive light bars and slow outer rings
            reactive_cover_rect=QRectF(cx-reactive_center_radius,cy-reactive_center_radius,reactive_center_radius*2.0,reactive_center_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,reactive_cover_rect,ctx,clip_radius=reactive_center_radius,fallback_accent=base_color)

            for k in range(17): v=values[int(k*count/17)]; a=k/17*math.tau-math.pi/2+now*0.08; col=QColor(base_color); col.setAlpha(120+int(v*100)); _cap(cx,cy,a,max_effect_radius*0.30,short_side*(0.04+v*0.22),max(1.8,(2+v*4)*width_scale),col)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for r_i in range(4): col=QColor(base_color); col.setAlpha(52-r_i*7); p.setPen(QPen(col,1)); rr=max_effect_radius*(0.86+r_i*0.035); p.drawEllipse(QPointF(cx,cy),rr,rr)
            p.restore(); return

        if style == "electro_dubstep":
            # Circular audio-reactive mesh ring around the current media cover. No equalizer bars.
            self._paint_electro_dubstep_mesh_ring(p, values, area, ctx, base_color, now, avg, bass, max_effect_radius, width_scale)
            p.restore(); return

        if style == "minimal_beat":
            outer=max_effect_radius*0.82; p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(base_color.red(),base_color.green(),base_color.blue(),90),1.2*width_scale)); p.drawEllipse(QPointF(cx,cy),outer,outer); p.drawEllipse(QPointF(cx,cy),outer-5,outer-5)
            for s in range(96): v=values[int(s*count/96)]; a=s/96*math.tau-math.pi/2; rr=outer-2.5+(((-1)**s)*short_side*(0.006+v*0.025)); _dot(cx+math.cos(a)*rr,cy+math.sin(a)*rr,1.1,QColor(base_color.red(),base_color.green(),base_color.blue(),105))
            minimal_inner_radius=max_effect_radius*0.32
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(0,0,0,82))); p.drawEllipse(QPointF(cx,cy),minimal_inner_radius,minimal_inner_radius)

            # Minimal Beat cover layer:
            #   bottom: existing black inner circle
            #   middle: current media cover image, fitted 10px inside that black circle
            #   top: accent-color beat bars around the inner circle
            minimal_cover_inset=min(10.0,max(0.0,minimal_inner_radius-2.0))
            minimal_cover_radius=max(1.0,minimal_inner_radius-minimal_cover_inset)
            minimal_cover_rect=QRectF(cx-minimal_cover_radius,cy-minimal_cover_radius,minimal_cover_radius*2.0,minimal_cover_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,minimal_cover_rect,ctx,clip_radius=minimal_cover_radius,fallback_accent=base_color)

            for i in range(0,count,max(1,count//80)): v=values[i]; a=i/count*math.tau-math.pi/2; col=QColor(base_color); col.setAlpha(205); _cap(cx,cy,a,max_effect_radius*0.38,short_side*(0.035+v*0.19),max(1.5,(2+v*4)*width_scale),col)
            p.restore(); return

        if style == "lofi_vibes":
            slot=aw/count; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255,255,255,205)))
            for i,v in enumerate(values): h=ah*(0.04+v*0.48); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.25,cy-h/2,max(1,slot*0.5*width_scale),h),2,2)
            for layer in range(2):
                for i in range(0,count,max(1,count//70)):
                    raw=values[i]; x=area.left()+aw*i/max(1,count-1); y=cy+ah*(0.22+layer*0.08)+math.sin(i*0.12+now*(0.9+layer*0.2))*ah*0.06-(raw-avg)*ah*0.18; _dot(x,y,1.4,QColor(255,255,255,185-layer*35))
            p.restore(); return

        if style == "cosmic_fusion":
            # Cosmic Fusion: circular cover + lightweight flat left bars + smooth right bars.
            # Current direction:
            #   - Center is a circular media cover image.
            #   - Left/thick arc is reduced to exactly 7 flat-design bars for performance.
            #   - Each left bar uses one solid rainbow color instead of per-bar gradients.
            #   - Right/thin arc keeps the smooth rainbow gradient animation.
            #   - Particle / dust drawing is intentionally removed.
            #   - The whole effect is rendered into a QImage layer, then composited with drawImage.
            base_p = p
            layer_w = int(max(1.0, math.ceil(area.width())))
            layer_h = int(max(1.0, math.ceil(area.height())))
            layer = QImage(layer_w, layer_h, QImage.Format.Format_ARGB32_Premultiplied)
            layer.fill(QColor(0, 0, 0, 0))

            p = QPainter(layer)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.translate(-area.left(), -area.top())
            p.setPen(Qt.PenStyle.NoPen)

            cosmic_alpha = 217  # about 85% opacity.
            cover_radius = max(18.0, min(aw, ah) * 0.245)
            ring_inner_radius = cover_radius + max(4.0, short_side * 0.026)
            ring_outer_limit = max_effect_radius * 1.08
            max_bar_len = max(8.0, ring_outer_limit - ring_inner_radius)
            cover_rect = QRectF(cx - cover_radius, cy - cover_radius, cover_radius * 2.0, cover_radius * 2.0)

            # Keep only a soft background glow. No particle / dust field is drawn.
            halo = QRadialGradient(QPointF(cx, cy), ring_outer_limit * 1.02)
            halo.setColorAt(0.0, QColor(255, 255, 255, 26))
            halo.setColorAt(0.35, QColor(base_color.red(), base_color.green(), base_color.blue(), 20 + int(avg * 22)))
            halo.setColorAt(0.74, QColor(150, 64, 255, 10 + int(bass * 16)))
            halo.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(cx, cy), ring_outer_limit * 1.02, ring_outer_limit * 1.02)

            def _arc_t(t: float, start: float, span: float) -> float:
                # Qt screen angle convention: 0=right, 90=down, 180=left, 270=up.
                return (float(start) + float(span) * float(t)) % 360.0

            def _rainbow_rect_gradient(length: float, width: float, phase: float, alpha: int) -> QLinearGradient:
                grad = QLinearGradient(QPointF(0.0, 0.0), QPointF(length, 0.0))
                for stop in range(7):
                    grad.setColorAt(stop / 6.0, self._rainbow_color(phase + stop / 7.0, alpha, 0.88, 1.0))
                return grad

            def _draw_flat_radial_bar(deg: float, length: float, width: float, color: QColor):
                # Lightweight left bar: 7 flat bars with a tiny pseudo-3D bevel.
                # It stays much cheaper than the old many-bar / glow / particle version.
                if length <= 0.5 or width <= 0.5:
                    return
                p.save()
                p.translate(QPointF(cx, cy))
                p.rotate(deg)
                rect = QRectF(ring_inner_radius, -width * 0.5, length, width)

                top = QColor(color).lighter(128)
                mid = QColor(color)
                bottom = QColor(color).darker(145)
                top.setAlpha(color.alpha())
                mid.setAlpha(color.alpha())
                bottom.setAlpha(color.alpha())

                # Cheap depth: one soft offset shadow + one 3-stop vertical bevel gradient.
                shadow = QColor(0, 0, 0, max(18, int(color.alpha() * 0.18)))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(shadow))
                p.drawRect(rect.adjusted(width * 0.14, width * 0.16, width * 0.14, width * 0.16))

                bevel = QLinearGradient(QPointF(0.0, -width * 0.5), QPointF(0.0, width * 0.5))
                bevel.setColorAt(0.0, top)
                bevel.setColorAt(0.48, mid)
                bevel.setColorAt(1.0, bottom)
                p.setBrush(QBrush(bevel))
                p.drawRect(rect)

                # Minimal bevel lines. No particles, no glow.
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, max(18, int(color.alpha() * 0.20))), max(0.6, width * 0.045)))
                p.drawLine(QPointF(ring_inner_radius, -width * 0.34), QPointF(ring_inner_radius + length, -width * 0.34))
                p.setPen(QPen(QColor(0, 0, 0, max(16, int(color.alpha() * 0.16))), max(0.6, width * 0.045)))
                p.drawLine(QPointF(ring_inner_radius, width * 0.34), QPointF(ring_inner_radius + length, width * 0.34))
                p.restore()

            def _draw_thin_radial_bar(deg: float, length: float, width: float, phase: float, alpha: int):
                # Right side only: keep smooth rainbow gradient, but no particles/glow.
                if length <= 0.5 or width <= 0.5:
                    return
                p.save()
                p.translate(QPointF(cx, cy))
                p.rotate(deg)
                rect = QRectF(ring_inner_radius, -width * 0.5, length, width)
                radius = width * 0.5
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(_rainbow_rect_gradient(length, width, phase, alpha)))
                p.drawRoundedRect(rect, radius, radius)
                p.restore()

            # Diagonal split. Swap starts if the thick/thin side appears reversed.
            thick_start = 45.0
            thick_span = 180.0
            thin_start = 225.0
            # Extend the right/thin arc downward by widening the angular spacing range.
            # This does not stretch each bar; it spreads the bars farther around the circle,
            # reaching closer to the lower-center area under the cover.
            thin_span = 230.0

            # Left side: exactly 7 bars, one solid rainbow color per bar.
            # The angular spacing is derived from a target visual gap of about 7px.
            thick_count = 7
            thin_count = max(34, min(72, int(short_side * 0.24)))
            thick_width = max(7.0, short_side * 0.055 * width_scale)
            thick_gap_px = 14.0
            thick_step_deg = math.degrees((thick_width + thick_gap_px) / max(1.0, ring_inner_radius))
            thick_span_cluster = thick_step_deg * max(0, thick_count - 1)
            # Move the left 7-bar cluster slightly upward around the circle.
            # Qt screen angle convention here is 0=right, 90=down, 180=left, 270=up,
            # so adding degrees moves the left-side cluster from lower-left toward upper-left.
            thick_vertical_shift_deg = 22.0
            thick_center_deg = thick_start + thick_span * 0.5 + thick_vertical_shift_deg
            thick_cluster_start = thick_center_deg - thick_span_cluster * 0.5
            thin_width = max(1.25, short_side * 0.0105 * width_scale)

            # Smooth rainbow movement for the right/thin side.
            thin_phase_smooth = now * 0.085

            for j in range(thick_count):
                t = j / max(1, thick_count - 1)
                deg = thick_cluster_start + thick_step_deg * j
                src_idx = int(t * (count - 1))
                v = values[src_idx]
                wave = 0.5 + 0.5 * math.sin(now * 0.55 + j * 0.72)
                edge_bias = 0.34 + 0.66 * abs(math.cos((t - 0.5) * math.pi))
                # Large, stable lengths for a strong flat-design silhouette.
                length = max_bar_len * (0.54 + v * 0.70 + wave * 0.08 + edge_bias * 0.20)
                length = max(max_bar_len * 0.50, min(max_bar_len * 1.20, length))
                color = self._rainbow_color(j / 7.0, cosmic_alpha, 0.86, 1.0)
                _draw_flat_radial_bar(deg, length, thick_width, color)

            for j in range(thin_count):
                t = j / max(1, thin_count - 1)
                deg = _arc_t(t, thin_start, thin_span)
                src_idx = int(t * (count - 1))
                v = values[src_idx]
                wave = 0.5 + 0.5 * math.sin(now * 1.18 + j * 0.73)
                length = max_bar_len * (0.12 + v * 0.47 + wave * 0.11)
                length = max(max_bar_len * 0.10, min(max_bar_len * 0.82, length))
                phase = thin_phase_smooth + j * 0.043
                _draw_thin_radial_bar(deg, length, thin_width * (0.86 + 0.26 * wave), phase, cosmic_alpha)

            # Circular center cover image clipped to the middle of the ring.
            # drawImage is used for the cover as well.
            pixmap = self._get_media_thumbnail_pixmap(ctx)
            clip_path = QPainterPath()
            clip_path.addEllipse(cover_rect)
            p.save()
            p.setClipPath(clip_path)
            if pixmap is not None and not pixmap.isNull():
                image = pixmap.toImage()
                scaled_image = image.scaled(
                    int(max(1.0, cover_rect.width())),
                    int(max(1.0, cover_rect.height())),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                ix = int(cover_rect.left() + (cover_rect.width() - scaled_image.width()) / 2.0)
                iy = int(cover_rect.top() + (cover_rect.height() - scaled_image.height()) / 2.0)
                p.drawImage(ix, iy, scaled_image)
            else:
                fallback = QRadialGradient(QPointF(cx, cy), cover_radius)
                fallback.setColorAt(0.0, QColor(255, 255, 255, 48))
                fallback.setColorAt(0.48, self._rainbow_color(now * 0.030, 132))
                fallback.setColorAt(1.0, self._rainbow_color(now * 0.030 + 0.58, 164))
                p.setBrush(QBrush(fallback))
                p.drawEllipse(cover_rect)
            p.restore()

            p.save()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 64), max(1.0, cover_radius * 0.024)))
            p.drawEllipse(cover_rect)
            p.setPen(QPen(self._rainbow_color(now * 0.018 + 0.12, 78), max(1.0, cover_radius * 0.030)))
            p.drawEllipse(cover_rect.adjusted(-1.0, -1.0, 1.0, 1.0))
            p.restore()

            p.end()
            base_p.drawImage(QPointF(area.left(), area.top()), layer)
            p = base_p
            p.restore(); return


        atmospheric = {"space", "cyber", "retro_future", "hud_equalizer", "aurora", "hologram", "energy_shield", "nebula", "matrix", "radar_scan", "audio_tunnel", "neon_tunnel_wire", "cosmic_fusion", "futuristic_tunnel", "beat_fluorescent_app"}
        if glow_enabled and style in atmospheric:
            grad = QRadialGradient(QPointF(cx, cy), max(aw, ah) * 0.78)
            if style == "aurora":
                grad.setColorAt(0.0, QColor(90, 255, 210, 56 + int(avg * 60)))
                grad.setColorAt(0.55, QColor(170, 80, 255, 28 + int(bass * 42)))
            elif style == "nebula":
                grad.setColorAt(0.0, QColor(150, 70, 255, 58 + int(avg * 64)))
                grad.setColorAt(0.45, QColor(255, 70, 180, 30 + int(mid * 58)))
            elif style == "matrix":
                grad.setColorAt(0.0, QColor(0, 42, 20, 38 + int(avg * 32)))
                grad.setColorAt(0.7, QColor(0, 14, 8, 16))
            elif style in ("audio_tunnel", "neon_tunnel_wire", "futuristic_tunnel"):
                grad.setColorAt(0.0, QColor(0, 230, 255, 46 + int(avg * 54)))
                grad.setColorAt(0.58, QColor(160, 40, 255, 28 + int(bass * 42)))
            else:
                grad.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 40 + int(avg * 52)))
                grad.setColorAt(0.58, QColor(0, 0, 0, 12))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad)); p.setPen(Qt.PenStyle.NoPen); p.drawRect(area)

        if style in ("space", "nebula", "cosmic_fusion", "meteor_shower"):
            for i in range(54):
                x = area.left() + ((i * 73 + int(now * (20 + bass * 60))) % int(max(1, aw)))
                y = area.top() + ((i * 47 + int(now * (9 + avg * 24))) % int(max(1, ah)))
                p.setPen(QPen(QColor(190, 230, 255, 45 + ((i * 17) % 70)), 1))
                p.drawPoint(QPointF(x, y))


        if style == "rainbow_ring_dj":
            ring_count = 5
            for k in range(ring_count):
                t = k / max(1, ring_count - 1)
                rr = min(max_effect_radius * (0.28 + t * 0.58 + bass * 0.035), max_effect_radius * 0.94)
                col = self._rainbow_color(t + now * 0.045, 185 + int(avg * 50), 0.92, 1.0)
                p.setPen(QPen(col, max(1.0, (1.2 + (1.0 - t) * 2.3 + bass * 2.0) * width_scale)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rr, rr)
            step = max(1, count // 64)
            for i in range(0, count, step):
                v = values[i]
                ang = i / count * math.tau - math.pi / 2.0 + now * 0.18
                inner = max_effect_radius * 0.50
                outer = min(max_effect_radius * 0.98, inner + short_side * (0.035 + v * 0.20))
                col = self._rainbow_color(i / count + now * 0.07, 210 + int(v * 40))
                pen = QPen(col, max(1.0, (1.4 + v * 3.8) * width_scale))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(cx + math.cos(ang) * inner, cy + math.sin(ang) * inner), QPointF(cx + math.cos(ang) * outer, cy + math.sin(ang) * outer))
            p.restore(); return

        if style == "liquid_audio_spectrum":
            # Smooth liquid-style spectrum: cubic Bezier curves, no sharp corners.
            palettes = [QColor(base_color), self._rainbow_color(0.52 + now * 0.03, 210), self._rainbow_color(0.78 + now * 0.02, 190)]
            for layer in range(3):
                pts = []
                phase = now * (1.05 + layer * 0.22)
                smooth_prev = avg
                for i, raw in enumerate(values):
                    # light interpolation to avoid sharp FFT corners
                    smooth_prev = smooth_prev * 0.72 + float(raw) * 0.28
                    x = area.left() + aw * i / max(1, count - 1)
                    wobble = math.sin(i * (0.10 + layer * 0.025) + phase) * ah * (0.040 + layer * 0.018)
                    y = cy + wobble - (smooth_prev - avg) * ah * (0.26 + layer * 0.055)
                    pts.append(QPointF(x, y))
                col = QColor(palettes[layer % len(palettes)])
                col.setAlpha(115 + int(avg * 105))
                pen = QPen(col, max(1.0, (2.6 + layer * 1.3 + bass * 2.4) * width_scale))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                if len(pts) >= 2:
                    path = QPainterPath(pts[0])
                    for j in range(1, len(pts)):
                        p0 = pts[j - 1]
                        p1 = pts[j]
                        mid_x = (p0.x() + p1.x()) * 0.5
                        path.cubicTo(QPointF(mid_x, p0.y()), QPointF(mid_x, p1.y()), p1)
                    p.drawPath(path)
            fill = QColor(base_color); fill.setAlpha(26 + int(avg * 38))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(fill))
            base_h = ah * (0.10 + bass * 0.14)
            p.drawRoundedRect(QRectF(area.left(), area.bottom() - base_h, aw, base_h), 12, 12)
            p.restore(); return

        if style == "music_logo_reveal":
            text_value = str(getattr(self.cfg, "text", "") or getattr(self.cfg, "title", "Music") or "Music")[:28]
            panel_w = aw * 0.58
            panel_h = ah * 0.30
            panel = QRectF(cx - panel_w / 2.0, cy - panel_h / 2.0 - ah * 0.05, panel_w, panel_h)
            p.drawRoundedRect(panel, 14, 14)
            p.setFont(QFont("Segoe UI", max(12, int(min(28, panel_h * 0.40))), QFont.Weight.Bold))
            p.setPen(QColor(245, 250, 255, 210 + int(avg * 35)))
            p.drawText(panel, Qt.AlignmentFlag.AlignCenter, text_value)
            slot = aw / count
            bar_base = min(area.bottom() - 6, panel.bottom() + ah * 0.18)
            for i, v in enumerate(values):
                x = area.left() + i * slot
                h = ah * (0.025 + v * 0.18)
                col = self._rainbow_color(i / count + now * 0.05, 180) if i % 3 == 0 else QColor(base_color)
                col.setAlpha(120 + int(v * 100))
                p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(x + slot * 0.22, bar_base - h, max(1.0, slot * min(0.76, 0.42 * width_scale)), h), 2, 2)
            p.restore(); return

        if style == "particle_audio_visualizer":
            # Lightweight deterministic particle burst: particles move outward and fade.
            step = max(1, count // 72)
            cycle = 2.4
            for i in range(0, count, step):
                v = values[i]
                if v <= 0.018:
                    continue
                seed_phase = (i * 0.61803398875) % 1.0
                age = (now * (0.32 + bass * 0.18) + seed_phase) % 1.0
                fade = 1.0 - age
                angle = i / count * math.tau + seed_phase * math.pi * 0.65
                start_r = max_effect_radius * (0.16 + (i % 7) * 0.018)
                travel = max_effect_radius * (0.16 + v * 0.48) * age
                orbit = min(max_effect_radius * 0.96, start_r + travel)
                x = cx + math.cos(angle) * orbit
                y = cy + math.sin(angle * 1.21) * orbit * 0.76
                alpha = max(0, min(220, int((70 + v * 150) * fade)))
                if alpha <= 4:
                    continue
                col = self._rainbow_color(i / count + now * 0.045, alpha, 0.86, 1.0)
                size = max(1.2, (1.8 + v * 5.2) * width_scale * (0.45 + fade * 0.75))
                if glow_enabled:
                    self._draw_visualizer_soft_orb(p, QPointF(x, y), size * 2.3, col, max(10, int(alpha * 0.45)))
                col.setAlpha(alpha)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
                p.drawEllipse(QPointF(x, y), size, size)
            p.restore(); return

        if style == "music_lower_third_audio":
            panel_h = ah * 0.32
            panel = QRectF(area.left() + aw * 0.04, area.bottom() - panel_h - ah * 0.06, aw * 0.92, panel_h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(10, 14, 24, 118 + int(avg * 46))))
            p.drawRoundedRect(panel, 12, 12)
            accent = QColor(base_color); accent.setAlpha(160 + int(bass * 70))
            p.setBrush(QBrush(accent))
            p.drawRoundedRect(QRectF(panel.left(), panel.top(), max(3.0, panel.width() * 0.018), panel.height()), 5, 5)
            p.setFont(QFont("Segoe UI", max(9, int(panel.height() * 0.22)), QFont.Weight.Bold))
            p.setPen(QColor(245, 248, 255, 215))
            p.drawText(QRectF(panel.left() + 18, panel.top() + 4, panel.width() * 0.48, panel.height() * 0.44), Qt.AlignmentFlag.AlignVCenter, str(getattr(self.cfg, "title", "Music") or "Music")[:34])
            slot = panel.width() * 0.45 / count
            bx = panel.left() + panel.width() * 0.52
            base_y = panel.bottom() - panel.height() * 0.18
            for i, v in enumerate(values):
                x = bx + i * slot
                h = panel.height() * (0.08 + v * 0.64)
                col = self._rainbow_color(i / count + now * 0.04, 170) if i % 4 == 0 else QColor(base_color)
                col.setAlpha(115 + int(v * 120))
                p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(x, base_y - h, max(1.0, slot * min(0.96, 0.55 * width_scale)), h), 2, 2)
            p.restore(); return

        if style == "digital_base_audio":
            p.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 32 + int(avg * 42)), 1))
            for gy in range(1, 5):
                y = area.top() + ah * gy / 5.0
                p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            low_n = max(4, count // 4)
            slot = aw / low_n
            for i in range(low_n):
                v = values[i]
                x = area.left() + i * slot
                for j in range(6):
                    if (j + 1) / 6.0 <= v + 0.08:
                        col = QColor(base_color) if i % 3 else self._rainbow_color(0.52 + i / low_n * 0.16, 190)
                        col.setAlpha(55 + int((j + 1) / 6.0 * 150))
                        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
                        cell_h = ah * 0.105
                        y = area.bottom() - (j + 1) * cell_h * 1.18
                        p.drawRoundedRect(QRectF(x + slot * 0.16, y, max(1.0, slot * min(0.82, 0.58 * width_scale)), cell_h * 0.78), 2, 2)
            p.restore(); return

        if style == "round_base_audio":
            base_r = min(max_effect_radius * 0.56, short_side * 0.28)
            p.setBrush(Qt.BrushStyle.NoBrush)
            ring_col = QColor(base_color); ring_col.setAlpha(105 + int(avg * 70))
            p.setPen(QPen(ring_col, max(1.2, 2.0 * width_scale)))
            p.drawEllipse(QPointF(cx, cy), base_r, base_r)
            step = max(1, count // 80)
            for i in range(0, count, step):
                v = values[i]
                ang = i / count * math.tau - math.pi / 2.0
                inner = base_r
                outer = min(max_effect_radius * 0.98, inner + short_side * (0.04 + v * 0.18))
                col = QColor(base_color) if i % 2 else self._rainbow_color(i / count + now * 0.05, 205)
                col.setAlpha(150 + int(v * 90))
                p.setPen(QPen(col, max(1.0, (1.3 + v * 3.4) * width_scale)))
                p.drawLine(QPointF(cx + math.cos(ang) * inner, cy + math.sin(ang) * inner), QPointF(cx + math.cos(ang) * outer, cy + math.sin(ang) * outer))
            p.restore(); return

        if style == "aurora":
            colors = [QColor(40, 255, 210, 120), QColor(140, 90, 255, 110), QColor(255, 120, 210, 90)]
            for band in range(3):
                pts = []
                for i, v in enumerate(values):
                    x = area.left() + aw * i / max(1, count - 1)
                    y = area.top() + ah * (0.22 + band * 0.16) + math.sin(i * 0.23 + now * (0.9 + band * 0.18)) * ah * (0.08 + bass * 0.10) - v * ah * 0.18
                    pts.append(QPointF(x, y))
                self._draw_visualizer_polyline(p, pts, colors[band], (4.0 + band * 2.2 + bass * 4.0) * width_scale, 85 + int(avg * 95))
            p.restore(); return

        if style == "hologram":
            p.setPen(QPen(QColor(120, 245, 255, 70), 1))
            for gy in range(9):
                y = area.top() + ah * gy / 8.0
                p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            slot = aw / count
            for i, v in enumerate(values):
                x = area.left() + i * slot + slot * 0.5
                h = ah * (0.16 + v * 0.72)
                p.setPen(QPen(QColor(120, 245, 255, 115 + int(v * 110)), max(1.0, slot * 0.18 * width_scale)))
                p.drawLine(QPointF(x, cy + h * 0.5), QPointF(x, cy - h * 0.5))
            p.restore(); return

        if style == "matrix":
            # 目に優しい Matrix 風: 0/1 がゆっくり落下する表示。
            soft_bg = QLinearGradient(QPointF(area.left(), area.top()), QPointF(area.left(), area.bottom()))
            soft_bg.setColorAt(0.0, QColor(0, 18, 10, 28)); soft_bg.setColorAt(1.0, QColor(0, 6, 4, 10))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(soft_bg)); p.drawRect(area)
            font_size = max(8, min(14, int(ah / 13.5)))
            p.setFont(QFont("Consolas", font_size))
            cell_h = max(10.0, font_size * 1.45); cell_w = max(9.0, font_size * 0.95)
            cols = max(6, int(aw / cell_w)); rows = max(4, int(ah / cell_h) + 3)
            base_speed = 6.0 + bass * 10.0
            time_bucket = int(now * 0.55)
            for col in range(cols):
                v = values[int(col * count / max(1, cols)) % count]
                speed = base_speed + (col % 5) * 0.7 + v * 3.5
                phase = (now * speed + col * cell_h * 0.83) % (rows * cell_h)
                x = area.left() + col * cell_w + cell_w * 0.15
                trail_len = 4 + int(v * 5)
                for row in range(rows):
                    y = area.top() + row * cell_h + phase - rows * cell_h * 0.42
                    if y < area.top() - cell_h or y > area.bottom() + cell_h:
                        continue
                    digit = "1" if ((col * 17 + row * 31 + time_bucket) & 1) else "0"
                    distance = abs((row % max(1, trail_len + 1)))
                    alpha = max(18, min(128, int(42 + v * 58 + bass * 24 - distance * 10)))
                    color = QColor(170, 255, 190, max(alpha, min(155, int(78 + v * 55 + bass * 28)))) if row % (trail_len + 1) == 0 else QColor(45, 190, 90, alpha)
                    p.setPen(color); p.drawText(QPointF(x, y), digit)
            p.restore(); return

        if style in ("energy_shield", "radar_scan", "circle_waveform", "rainbow_ring_dj", "round_base_audio"):
            rings = 5 if style != "circle_waveform" else 3
            for k in range(rings):
                rr = min(max_effect_radius, short_side * (0.11 + k * 0.075 + bass * 0.035))
                alpha = max(18, 115 - k * 17 + int(avg * 70))
                col = QColor(base_color)
                if style == "energy_shield": col = QColor(60, 210, 255, alpha)
                elif style == "radar_scan": col = QColor(80, 255, 140, alpha)
                elif style == "circle_waveform": col = self._rainbow_color(k * 0.13 + now * 0.05, alpha)
                else: col.setAlpha(alpha)
                p.setPen(QPen(col, (1.2 + bass * 3.2) * width_scale)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rr, rr)
            if style == "energy_shield" and rings >= 1:
                # Hexagonal shield mesh overlay.
                shield_r = min(max_effect_radius * 0.82, radius * 1.45)
                hex_pts = []
                for h_i in range(6):
                    a = math.tau * h_i / 6.0 - math.pi / 6.0
                    hex_pts.append(QPointF(cx + math.cos(a) * shield_r, cy + math.sin(a) * shield_r))
                hex_path = QPainterPath(hex_pts[0])
                for pt in hex_pts[1:]:
                    hex_path.lineTo(pt)
                hex_path.closeSubpath()
                p.setPen(QPen(QColor(80, 220, 255, 92 + int(bass * 80)), max(1.0, 1.2 * width_scale)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(hex_path)
            if style == "radar_scan":
                ang = now * 1.8
                p.setPen(QPen(QColor(120, 255, 160, 140), 3 + bass * 5))
                p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(ang) * max_effect_radius, cy + math.sin(ang) * max_effect_radius))
            for i, v in enumerate(values):
                ang = i / count * math.tau - math.pi / 2
                inner_r = radius * (0.72 if style == "circle_waveform" else 0.95)
                outer_r = min(max_effect_radius, inner_r + short_side * (0.04 + v * 0.14))
                col = self._rainbow_color(i / count + now * 0.05, 220) if style == "circle_waveform" else QColor(base_color)
                p.setPen(QPen(col, max(1.0, (1.5 + v * 4.0) * width_scale)))
                p.drawLine(QPointF(cx + math.cos(ang)*inner_r, cy + math.sin(ang)*inner_r), QPointF(cx + math.cos(ang)*outer_r, cy + math.sin(ang)*outer_r))
            p.restore(); return

        if style in ("audio_tunnel", "neon_tunnel_wire", "futuristic_tunnel"):
            for k in range(9):
                t = k / 8.0; scale = 1.0 - t * 0.82
                wobble = math.sin(now * 1.4 + k) * bass * 12.0
                rect = QRectF(cx - aw*scale*0.44 + wobble, cy - ah*scale*0.36, aw*scale*0.88, ah*scale*0.72)
                col = self._rainbow_color(0.52 + t * 0.34 + now * 0.04, 55 + int((1.0 - t) * 150))
                if style == "futuristic_tunnel": col = QColor(120, 235, 255, 65 + int((1.0 - t) * 150))
                p.setPen(QPen(col, (1.0 + (1.0 - t) * 2.5 + bass * 2.0) * width_scale)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect, 8, 8)
                if style == "neon_tunnel_wire":
                    p.drawLine(QPointF(area.left(), cy), QPointF(rect.left(), rect.top()))
                    p.drawLine(QPointF(area.right(), cy), QPointF(rect.right(), rect.bottom()))
            p.restore(); return

        if style in ("nebula", "cosmic_fusion"):
            for i, v in enumerate(values):
                angle = i / count * math.tau + now * 0.12
                rr = min(max_effect_radius * 0.82, radius * (0.38 + (i % 7) * 0.065 + v * 0.42))
                col = self._rainbow_color(0.70 + i / count * 0.35 + now * 0.02, 42 + int(v * 130), 0.78, 1.0)
                self._draw_visualizer_soft_orb(p, QPointF(cx + math.cos(angle) * rr, cy + math.sin(angle * 1.3) * rr * 0.65), 3 + v * short_side * 0.045, col, 35 + int(v * 90))
            p.restore(); return

        if style == "meteor_shower":
            for i in range(18):
                v = values[(i * 3) % count]
                x = area.left() + ((i * 83 + int(now * (90 + v * 170))) % int(max(1, aw + 80))) - 40
                y = area.top() + ((i * 41 + int(now * (28 + bass * 55))) % int(max(1, ah)))
                p.setPen(QPen(self._rainbow_color(0.55 + i * 0.03, 120 + int(v * 110)), 1.5 + v * 4.0))
                p.drawLine(QPointF(x, y), QPointF(x - 24 - v * 50, y + 18 + v * 26))
            p.restore(); return

        if style in ("neon_soundwave", "enigmatic_echo_sound", "lofi_vibes", "electric_pulse"):
            palettes = [QColor(0, 245, 255, 220), QColor(255, 60, 210, 190), QColor(255, 245, 90, 170)]
            layers = 3
            if style == "lofi_vibes":
                palettes = [QColor(255, 180, 150, 170), QColor(130, 190, 255, 145)]; layers = 2
            if style == "electric_pulse":
                palettes = [QColor(60, 230, 255, 230), QColor(255, 255, 255, 190), QColor(90, 120, 255, 160)]
            for layer in range(layers):
                pts = []
                for i, v in enumerate(values):
                    x = area.left() + aw * i / max(1, count - 1)
                    y = cy + math.sin(i * (0.18 + layer * 0.04) + now * (2.0 + layer * 0.35)) * ah * (0.07 + layer * 0.035) - (v - avg) * ah * (0.30 + layer * 0.08)
                    if style == "enigmatic_echo_sound": y += math.sin(i * 0.51 - now * 1.1) * ah * 0.045
                    pts.append(QPointF(x, y))
                self._draw_visualizer_polyline(p, pts, palettes[layer], (2.0 + layer * 1.2 + bass * 3.0) * width_scale, 105 + int(avg * 120))
            p.restore(); return

        if style == "reactive_lights":
            lamps = max(8, min(28, count // 2))
            for i in range(lamps):
                v = values[int(i * count / lamps)]
                self._draw_visualizer_soft_orb(p, QPointF(area.left() + aw * (i + 0.5) / lamps, cy), ah * (0.06 + v * 0.26), self._rainbow_color(i / lamps + now * 0.08, 70 + int(v * 170)), 40 + int(v * 120))
            p.restore(); return

        if style in ("minimal_beat", "beat_fluorescent_app", "glow_beat_music"):
            slot = aw / count
            for i, v in enumerate(values):
                x = area.left() + i * slot; h = ah * (0.08 + v * 0.88)
                if style == "minimal_beat":
                    col = QColor(base_color); col.setAlpha(150 + int(v * 80))
                elif style == "glow_beat_music":
                    col = QColor(255, 230, 120, 180 + int(v * 70)); self._draw_visualizer_soft_orb(p, QPointF(x + slot * 0.5, area.bottom() - h), 5 + v * 18, col, 50 + int(v * 80))
                else:
                    col = self._rainbow_color(i / count + now * 0.11, 210, 0.95, 1.0)
                p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
                if style == "minimal_beat": p.drawRect(QRectF(x + slot*0.35, area.bottom() - h, max(1.0, slot * min(0.98, 0.30 * width_scale)), h))
                else: p.drawRoundedRect(QRectF(x + slot*0.16, area.bottom() - h, max(1.0, slot * min(0.98, 0.68 * width_scale)), h), 3, 3)
            p.restore(); return


        # Spec-refined first-wave skins. These branches intentionally override the older generic families below.
        if style == "bass_drop":
            # Heavy bass: white circular structure, sticky 3-color waveform, inner accent particles, bass shake.
            sx = math.sin(now * 28.0) * bass * short_side * 0.015
            sy = math.cos(now * 24.0) * bass * short_side * 0.012
            ccx, ccy = cx + sx, cy + sy
            core = min(max_effect_radius * 0.54, short_side * (0.23 + bass * 0.10))
            if glow_enabled:
                self._draw_visualizer_soft_orb(p, QPointF(ccx, ccy), core * (1.25 + bass * 0.25), QColor(base_color.red(), base_color.green(), base_color.blue(), 88), 38 + int(bass * 74))
            for k in range(30):
                ph = (k * 0.61803398875 + now * 0.045) % 1.0
                rr = core * (0.12 + ((k * 37) % 100) / 100.0 * 0.70)
                aa = ph * math.tau + math.sin(now * 0.7 + k) * 0.18
                pc = QColor(base_color); pc.setAlpha(35 + int(avg * 70))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(pc))
                p.drawEllipse(QPointF(ccx + math.cos(aa) * rr, ccy + math.sin(aa) * rr), 1.2 + bass * 1.5, 1.2 + bass * 1.5)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 170 + int(bass * 55)), max(1.2, 2.1 * width_scale)))
            p.drawEllipse(QPointF(ccx, ccy), core, core)
            p.setPen(QPen(QColor(255,255,255,60 + int(bass * 50)), max(1.0, 1.0 * width_scale)))
            p.drawEllipse(QPointF(ccx, ccy), core * 0.70, core * 0.70)
            palette = [QColor(135, 60, 255), QColor(45, 150, 255), QColor(255, 70, 90)]
            step = max(1, count // 96)
            for i in range(0, count, step):
                v=values[i]; ang=i/count*math.tau-math.pi/2.0+math.sin(now*2.0+i*0.08)*bass*0.10
                stretch=short_side*(0.035+v*0.12+bass*0.12); inner=core*(0.94-v*0.05); outer=min(max_effect_radius*0.98, core+stretch)
                c_inner=QColor(255,255,255,165+int(v*65)); c_outer=QColor(palette[(i//step)%3]); c_outer.setAlpha(170+int(v*70))
                p.setPen(QPen(c_inner, max(1.0,(1.2+v*2.4)*width_scale)))
                p.drawLine(QPointF(ccx+math.cos(ang)*inner, ccy+math.sin(ang)*inner), QPointF(ccx+math.cos(ang)*(inner+stretch*0.42), ccy+math.sin(ang)*(inner+stretch*0.42)))
                p.setPen(QPen(c_outer, max(1.0,(1.5+v*4.2+bass*2.8)*width_scale)))
                p.drawLine(QPointF(ccx+math.cos(ang)*(inner+stretch*0.36), ccy+math.sin(ang)*(inner+stretch*0.36)), QPointF(ccx+math.cos(ang)*outer, ccy+math.sin(ang)*outer))
            p.restore(); return

        if style == "melodic_vibe":
            # Cloud-like glowing space with denser spiral toward center.
            for k in range(28):
                ph=k/28.0; rr=max_effect_radius*(0.12+ph*0.86); aa=now*(0.18+ph*0.10)+ph*math.tau*2.2
                x=cx+math.cos(aa)*rr*(0.36+ph*0.52); y=cy+math.sin(aa*1.13)*rr*(0.24+ph*0.38)
                a=max(10,int((44+avg*48)*(1.0-ph*0.60)))
                self._draw_visualizer_soft_orb(p,QPointF(x,y),short_side*(0.08+ph*0.055),QColor(255,255,255,a),a)
            if glow_enabled:
                ac=QColor(base_color); ac.setAlpha(34+int(avg*74)); self._draw_visualizer_soft_orb(p,QPointF(cx,cy),max_effect_radius*(0.72+bass*0.16),ac,ac.alpha())
            p.restore(); return

        if style == "alternative":
            # Horizontal smooth waveform built from softened rods and dotted ends. Slightly larger musical sway.
            pts=[]; smooth=avg
            for i,raw in enumerate(values):
                smooth=smooth*0.78+float(raw)*0.22; x=area.left()+aw*i/max(1,count-1); y=cy+math.sin(i*0.08+now*0.82)*ah*0.16-(smooth-avg)*ah*0.30; pts.append(QPointF(x,y))
            stride=max(1,count//74); p.setPen(Qt.PenStyle.NoPen)
            for i in range(0,len(pts),stride):
                v=values[min(i,count-1)]; shade=205 if i%2 else 245; col=QColor(shade,shade,shade,100+int(v*125)); p.setBrush(QBrush(col))
                rod_h=5.6*width_scale; rod_w=max(2.0,aw/max(40,count)*0.92); p.drawRoundedRect(QRectF(pts[i].x()-rod_w*0.5,pts[i].y()-rod_h*0.5,rod_w,rod_h),3,3)
                if i==0 or i+stride>=len(pts): p.drawEllipse(pts[i],rod_h*0.76,rod_h*0.76)
            p.restore(); return

        if style == "circle":
            # Seamless smooth circular waveform: first/last coordinates are identical and only outer/inner loops are stroked.
            core = min(radius, max_effect_radius * 0.52)
            rot = now * 0.18
            sample_count = max(96, min(224, count))
            outer_pts = []
            inner_pts = []
            first_outer = None
            first_inner = None
            for s in range(sample_count + 1):
                if s == sample_count and first_outer is not None and first_inner is not None:
                    # Reuse exact first coordinates at 360° to remove the numerical seam completely.
                    outer_pts.append(QPointF(first_outer))
                    inner_pts.append(QPointF(first_inner))
                    continue
                src = int(s * count / sample_count) % count
                v = values[src]
                ang = s / sample_count * math.tau - math.pi / 2.0 + rot
                wobble = math.sin(now * 1.2 + s * 0.12) * 0.022
                inner = core * (0.90 + avg * 0.04 + wobble)
                outer = min(max_effect_radius * 0.98, core + short_side * (0.045 + v * 0.18))
                op = QPointF(cx + math.cos(ang) * outer, cy + math.sin(ang) * outer)
                ip = QPointF(cx + math.cos(ang) * inner, cy + math.sin(ang) * inner)
                if s == 0:
                    first_outer = QPointF(op)
                    first_inner = QPointF(ip)
                outer_pts.append(op)
                inner_pts.append(ip)
            if outer_pts and inner_pts:
                fill_path = QPainterPath(outer_pts[0])
                for pt in outer_pts[1:]:
                    fill_path.lineTo(pt)
                for pt in reversed(inner_pts):
                    fill_path.lineTo(pt)
                fill_path.closeSubpath()
                fill = QColor(base_color)
                fill.setAlpha(98 + int(avg * 85))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(fill))
                p.drawPath(fill_path)

                # Stroke outer and inner loops separately. This avoids drawing a radial seam line.
                edge = QColor(base_color)
                edge.setAlpha(160 + int(avg * 70))
                pen = QPen(edge, max(1.0, 1.65 * width_scale))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(pen)
                outer_path = QPainterPath(outer_pts[0])
                for pt in outer_pts[1:]:
                    outer_path.lineTo(pt)
                outer_path.closeSubpath()
                inner_path = QPainterPath(inner_pts[0])
                for pt in inner_pts[1:]:
                    inner_path.lineTo(pt)
                inner_path.closeSubpath()
                p.drawPath(outer_path)
                p.drawPath(inner_path)
            p.restore(); return

        if style == "ellipse":
            # Horizontal elliptical spectrum; uses widget accent color.
            rx_scale=1.58; ry_scale=0.54; core=min(radius,max_effect_radius*0.48); step=max(1,count//84)
            for i in range(0,count,step):
                v=values[i]; ang=i/count*math.tau-math.pi/2.0; inner=core; outer=min(max_effect_radius*0.96,inner+short_side*(0.035+v*0.16)); col=QColor(base_color); col.setAlpha(135+int(v*110)); p.setPen(QPen(col,max(1.0,(1.25+v*3.0)*width_scale))); p.drawLine(QPointF(cx+math.cos(ang)*inner*rx_scale,cy+math.sin(ang)*inner*ry_scale),QPointF(cx+math.cos(ang)*outer*rx_scale,cy+math.sin(ang)*outer*ry_scale))
            p.restore(); return

        if style == "turntable":
            # 横から見たターンテーブル風。カバー外側の黒い盤面を約70px拡張し、バーをその内側へ収める。
            base_disc_r=min(max_effect_radius*0.62,short_side*0.31)
            turntable_cover_radius=max(1.0,base_disc_r*0.84-10.0)
            outer_disc_r=min(max_effect_radius*0.98,turntable_cover_radius+100.0)
            side_y_scale=0.38; tilt_degrees=1.3
            p.save()
            try:
                p.translate(cx,cy); p.rotate(tilt_degrees); p.scale(1.0,side_y_scale); p.translate(-cx,-cy)
                grad=QRadialGradient(QPointF(cx,cy),outer_disc_r); grad.setColorAt(0.0,QColor(245,248,255,235)); grad.setColorAt(0.20,QColor(base_color.red(),base_color.green(),base_color.blue(),135)); grad.setColorAt(0.52,QColor(26,28,35,235)); grad.setColorAt(1.0,QColor(4,5,8,245)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawEllipse(QPointF(cx,cy),outer_disc_r,outer_disc_r)
                p.setBrush(Qt.BrushStyle.NoBrush)
                for k in range(5):
                    rr=turntable_cover_radius*(0.34+k*0.13+math.sin(now*1.2+k)*0.006); p.setPen(QPen(QColor(210,220,235,55+k*14),max(0.8,1.0*width_scale))); p.drawEllipse(QPointF(cx,cy),rr,rr)
                turntable_cover_rect=QRectF(cx-turntable_cover_radius,cy-turntable_cover_radius,turntable_cover_radius*2.0,turntable_cover_radius*2.0)
                p.save()
                try:
                    p.translate(cx,cy)
                    p.rotate(math.degrees(now*0.55))
                    p.translate(-cx,-cy)
                    self._draw_visualizer_media_thumbnail_cover(p,turntable_cover_rect,ctx,clip_radius=turntable_cover_radius,fallback_accent=base_color)
                finally:
                    p.restore()
                step=max(1,count//72); bar_inner=min(outer_disc_r-2.0,turntable_cover_radius+8.0); bar_room=max(1.0,outer_disc_r-bar_inner-4.0)
                for i in range(0,count,step):
                    v=values[i]; ang=i/count*math.tau-math.pi/2.0; outer=bar_inner+min(bar_room,short_side*(0.024+v*0.13)); p.setPen(QPen(QColor(230,235,245,115+int(v*115)),max(1.0,(1.0+v*2.8)*width_scale))); p.drawLine(QPointF(cx+math.cos(ang)*bar_inner,cy+math.sin(ang)*bar_inner),QPointF(cx+math.cos(ang)*outer,cy+math.sin(ang)*outer))
            finally:
                p.restore()
            p.restore(); return

        if style == "spotlight_beat":
            # Two blurred elliptical dotted rings moving inverted from each other. Strong dot-to-bar stretch, calmer ring pulse.
            for ring in range(2):
                # Keep the bar stretch strong, but reduce whole-ring breathing so the inner ring stays visually inside the outer ring.
                ring_pulse = 1.0 + bass * (0.025 + ring * 0.012)
                rx=max_effect_radius*(0.54+ring*0.22)*ring_pulse; ry=rx*(0.45 + bass*0.018); phase=now*(0.36 if ring==0 else -0.32)
                for k in range(42):
                    v=values[(k*count//42)%count]
                    ang=k/42*math.tau+phase+math.sin(now*1.20+k*0.17)*v*0.050
                    stretch=1.0+v*4.85+bass*0.90
                    x=cx+math.cos(ang)*rx; y=cy+math.sin(ang)*ry*(-1 if ring else 1)
                    col=QColor(base_color) if ring else QColor(245,248,255); col.setAlpha(72+int(v*175))
                    if glow_enabled: self._draw_visualizer_soft_orb(p,QPointF(x,y),5.0+v*16.0,col,30+int(v*78))
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
                    bar_w=max(3.8,4.95*width_scale)
                    bar_h=bar_w*stretch
                    p.drawRoundedRect(QRectF(x-bar_w*0.5,y-bar_h*0.5,bar_w,bar_h),3,3)
            p.restore(); return

        if style == "audio_react":
            # Translucent blurred circle with white wavy contour.
            if glow_enabled: self._draw_visualizer_soft_orb(p,QPointF(cx,cy),max_effect_radius*0.76,QColor(base_color.red(),base_color.green(),base_color.blue(),85),42+int(avg*70))
            p.setBrush(QBrush(QColor(base_color.red(),base_color.green(),base_color.blue(),36+int(avg*35)))); p.setPen(QPen(QColor(255,255,255,60),max(1.0,1.0*width_scale))); p.drawEllipse(QPointF(cx,cy),radius*1.15,radius*1.15)
            pts=[]; step=max(1,count//128)
            for i in range(0,count,step):
                v=values[i]; ang=i/count*math.tau-math.pi/2.0; rr=radius*1.10+short_side*(0.025+v*0.15)+math.sin(now*1.7+i*0.10)*short_side*0.012; pts.append(QPointF(cx+math.cos(ang)*rr,cy+math.sin(ang)*rr))
            if pts:
                path=QPainterPath(pts[0]); [path.lineTo(pt) for pt in pts[1:]]; path.closeSubpath(); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,160+int(avg*70)),max(1.0,2.0*width_scale))); p.drawPath(path)
            p.restore(); return

        if style == "retro_future":
            # Two travelling accent neon lines fading backward.
            gap=aw*0.08
            for side in (-1,1):
                base_x=cx+side*gap; prev=None
                for j in range(18):
                    t=j/17.0; y=area.bottom()-t*ah; x=base_x+math.sin(now*1.1+t*6.0+side)*aw*0.025; col=QColor(base_color); col.setAlpha(max(18,int((1.0-t)*130+avg*55))); p.setPen(QPen(col,max(1.0,(2.6-t*1.4)*width_scale)))
                    if prev: p.drawLine(prev,QPointF(x,y))
                    prev=QPointF(x,y)
            p.restore(); return

        if style == "rainbow":
            # Fine iridescent scale-powder steam version, emitted only on bar peaks.
            # Bars stay compact; particles are small flattened flakes with per-flake rainbow gradients.
            # Peak detection compares this frame against the previous frame, then keeps spawned powder alive briefly.
            slot=aw/count
            bw=max(1.0,slot*0.38*width_scale)
            particle_step=max(1,count//15)
            # Left-edge bass push: on a deep bass transient, move only the existing left bars.
            # No oscillation is added; the bars push once with the bass envelope and then return smoothly.
            prev_left_bass=float(getattr(self,"_rainbow_left_edge_prev_bass",bass))
            left_bass_rise=bass-prev_left_bass
            self._rainbow_left_edge_prev_bass=bass
            prev_left_time=float(getattr(self,"_rainbow_left_edge_last_time",now))
            left_dt=max(0.0,min(0.10,now-prev_left_time))
            self._rainbow_left_edge_last_time=now
            prev_left_push=float(getattr(self,"_rainbow_left_edge_push",0.0))
            left_edge_target=0.0
            if bass>=0.18 and left_bass_rise>=0.035:
                left_edge_target=max(0.0,min(1.0,(bass-0.18)*3.0+left_bass_rise*8.0))
            left_edge_push=0
            self._rainbow_left_edge_push=left_edge_push
            bar_tops=[]
            for i,v in enumerate(values):
                t=i/max(1,count-1)
                # Tone layout across the bar field:
                # left = low/bass, center = high/treble, right = mid/vocal-like band.
                low_idx=max(0,min(count-1,int((0.05+0.11*t)*(count-1))))
                mid_idx=max(0,min(count-1,int((0.42+0.18*t)*(count-1))))
                high_idx=max(0,min(count-1,int((0.74+0.10*(1.0-abs(t-0.5)*2.0))*(count-1))))
                low_v=values[low_idx]
                mid_v=values[mid_idx]
                high_v=values[high_idx]
                low_weight=(1.0-t)**8.55
                mid_weight=t**0.85
                high_weight=max(0.0,1.0-abs(t-0.5)*2.0)**1.80*1.65
                local_weight=0.012
                avg_weight=0.0008
                weight_sum=low_weight+mid_weight+high_weight+local_weight+avg_weight
                tone_v=max(0.0,min(1.0,(low_v*low_weight+mid_v*mid_weight+high_v*high_weight+v*local_weight+avg*avg_weight)/max(0.001,weight_sum)))
                x=area.left()+i*slot
                h=ah*(0.030+tone_v*0.340)
                left_edge_weight=max(0.0,1.0-t*5.0)**1.70
                if left_edge_push>0.001 and left_edge_weight>0.001:
                    x+=left_edge_weight*left_edge_push*slot*0.85
                c=self._rainbow_lut_color(t+now*0.050,230)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(c))
                bx=x+slot*0.31
                p.drawRoundedRect(QRectF(bx,cy-h,bw,h),3,3)
                bar_tops.append((x+slot*0.5,cy-h,t,tone_v))
                ref=QColor(c)
                ref.setAlpha(14+int(tone_v*22))
                p.setBrush(QBrush(ref))
                p.drawRoundedRect(QRectF(bx,cy+2,bw,h*0.12),3,3)

            # Spawn powder only when a sampled bar sharply rises into a peak.
            # peak_rise_threshold: larger = stricter peak-only emission; smaller = more frequent powder.
            # peak_level_threshold: larger = only taller bars emit powder.
            peak_rise_threshold=0.055
            peak_level_threshold=0.120
            peak_cooldown=0.140
            powder_life=1.01
            prev_levels=getattr(self,"_rainbow_peak_prev_levels",None)
            if not isinstance(prev_levels,list) or len(prev_levels)!=len(bar_tops):
                prev_levels=[0.0]*len(bar_tops)
            last_spawn=getattr(self,"_rainbow_peak_last_spawn",None)
            if not isinstance(last_spawn,list) or len(last_spawn)!=len(bar_tops):
                last_spawn=[-9999.0]*len(bar_tops)
            particles=getattr(self,"_rainbow_peak_particles",None)
            if not isinstance(particles,list):
                particles=[]
            for i in range(0,len(bar_tops),particle_step):
                base_x,base_y,t,tone_v=bar_tops[i]
                rise=tone_v-prev_levels[i]
                if tone_v>=peak_level_threshold and rise>=peak_rise_threshold and now-last_spawn[i]>=peak_cooldown:
                    for spark in range(6):
                        seed=(i*0.017+spark*0.109+now*0.013)%1.0
                        particles.append((now,base_x,base_y,t,tone_v,spark,seed))
                    last_spawn[i]=now
            self._rainbow_peak_prev_levels=[bt[3] for bt in bar_tops]
            self._rainbow_peak_last_spawn=last_spawn

            # Draw only particles that were born from peaks; they rise and fade after the peak.
            p.setPen(Qt.PenStyle.NoPen)
            active_particles=[]
            for birth,base_x,base_y,t,tone_v,spark,seed in particles:
                age=(now-birth)/max(0.001,powder_life)
                if age<0.0 or age>=1.0:
                    continue
                active_particles.append((birth,base_x,base_y,t,tone_v,spark,seed))
                flutter=math.sin(now*1.35+seed*17.0+spark*1.77)*slot*(0.85+age*2.35)
                flutter+=math.sin(now*2.55+seed*11.0+spark*2.63)*slot*(0.38+age*1.15)
                flutter+=math.sin(age*math.tau*2.5+spark*0.73)*slot*0.44
                px=base_x+flutter+(spark-4)*slot*0.105
                py=base_y-age*ah*(0.42+tone_v*0.30)-spark*ah*0.005+math.sin(now*1.90+i*0.11+spark)*ah*0.014
                pr=(0.65+tone_v*1.05+(spark%3)*0.885)*max(1.0,width_scale)
                angle=math.sin(now*1.65+seed*13.0+spark*0.97)*58.0+age*155.0+spark*23.0
                fade=max(0.0,1.0-age)
                alpha=max(0,int((fade*fade*fade)*230))
                hue_bucket=int(((t+spark*0.081+now*0.030+age*0.065)%1.0)*24.0)
                size_bucket=max(0,min(2,int(tone_v*3.0)))
                angle_bucket=int((angle%360.0)/22.5)%16
                sprite=self._get_rainbow_powder_sprite(hue_bucket,size_bucket,angle_bucket)
                draw_size=max(3.0,pr*4.2)
                p.save()
                p.setOpacity(max(0.0,min(1.0,alpha/255.0)))
                p.drawImage(QRectF(px-draw_size*0.5,py-draw_size*0.5,draw_size,draw_size),sprite)
                p.restore()
            self._rainbow_peak_particles=active_particles[-700:]
            p.restore(); return

        if style == "minimal":
            # Centered smooth tight bars, accent color.
            slot=aw/count; col=QColor(base_color); col.setAlpha(195); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
            for i,v in enumerate(values):
                h=ah*(0.025+v*0.46); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.28,cy-h*0.5,max(1.0,slot*min(0.80,0.44*width_scale)),h),2,2)
            p.restore(); return

        if style == "urban_timelapse":
            # Lines with bouncing spheres at tips.
            lanes=min(18,max(8,count//5))
            for i in range(lanes):
                v=values[int(i*count/lanes)]; y=area.top()+ah*(0.16+(i%lanes)/max(1,lanes-1)*0.68); x0=area.left()+((now*(35+i*2)+i*31)%max(1.0,aw)); length=aw*(0.10+v*0.18); col=QColor(80,170,255,100+int(v*90)) if i%2 else QColor(255,155,55,100+int(v*90)); p.setPen(QPen(col,max(1.0,(1.2+v*2.2)*width_scale))); p.drawLine(QPointF(x0-length,y),QPointF(x0,y)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawEllipse(QPointF(x0,y+math.sin(now*2.0+i)*ah*0.025),2.0+v*3.0,2.0+v*3.0)
            p.restore(); return

        if style == "music_beat_wall":
            # Semi-transparent bars that blend into background.
            slot=aw/count
            for i,v in enumerate(values):
                h=ah*(0.06+v*0.76); col=QColor(base_color); col.setAlpha(38+int(v*72)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.16,area.bottom()-h,max(1.0,slot*min(0.92,0.64*width_scale)),h),3,3)
            p.restore(); return

        if style == "led_audio_wave":
            # Two center rails with one accent waveform and fading endpoint dots.
            rail_gap=ah*0.10; p.setPen(QPen(QColor(base_color.red(),base_color.green(),base_color.blue(),70),max(1.0,1.0*width_scale))); p.drawLine(QPointF(area.left(),cy-rail_gap),QPointF(area.right(),cy-rail_gap)); p.drawLine(QPointF(area.left(),cy+rail_gap),QPointF(area.right(),cy+rail_gap))
            pts=[]; smooth=avg
            for i,raw in enumerate(values):
                smooth=smooth*0.78+raw*0.22; x=area.left()+aw*i/max(1,count-1); y=cy+math.sin(i*0.15+now*1.6)*ah*0.055-(smooth-avg)*ah*0.20; pts.append(QPointF(x,y))
            self._draw_visualizer_polyline(p,pts,QColor(base_color),2.0*width_scale,145)
            for i in range(0,len(pts),max(1,len(pts)//18)):
                age=(now*0.7+i*0.03)%1.0; c=QColor(base_color); c.setAlpha(int((1.0-age)*125)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawEllipse(pts[i],2.0,2.0)
            p.restore(); return

        if style == "euphoria_motion":
            # Six neon white horizontal bars that shake with music.
            for k in range(6):
                v=values[int(k*count/6)]; y=cy+(k-2.5)*ah*0.095+math.sin(now*3.0+k)*bass*ah*0.025; length=aw*(0.22+v*0.34+bass*0.10); col=QColor(250,250,255,135+int(v*100)); p.setPen(QPen(col,max(2.0,(3.0+v*6.0)*width_scale))); p.drawLine(QPointF(cx-length*0.5,y),QPointF(cx+length*0.5,y))
            p.restore(); return

        if style == "luminance":
            self._paint_luminance_wave_scene(p, values, area, base_color, now, avg, width_scale)
            p.restore(); return

        if style == "parallax_waves":
            # Center circle with two mochi-like waves.
            core=min(radius,max_effect_radius*0.40); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,125),max(1.0,1.2*width_scale))); p.drawEllipse(QPointF(cx,cy),core,core)
            for layer in range(2):
                pts=[]; step=max(1,count//128)
                for i in range(0,count,step):
                    v=values[i]; ang=i/count*math.tau-math.pi/2.0+now*(0.10+layer*0.06); rr=core*(1.08+layer*0.22)+short_side*(0.035+v*(0.12+layer*0.04)); pts.append(QPointF(cx+math.cos(ang)*rr,cy+math.sin(ang)*rr))
                col=QColor(base_color if layer==0 else QColor(255,255,255)); col.setAlpha(145-layer*25)
                if pts:
                    path=QPainterPath(pts[0]); [path.lineTo(pt) for pt in pts[1:]]; path.closeSubpath(); p.setPen(QPen(col,max(1.0,(2.4+layer)*width_scale))); p.drawPath(path)
            p.restore(); return

        if style == "hud_equalizer":
            self._paint_hud_equalizer_scene(p, values, area, base_color, now, width_scale)
            p.restore(); return

        if style == "space":
            # Center white-bar waveform with thin particles around it.
            for i in range(54):
                x=area.left()+((i*73+int(now*20))%int(max(1,aw))); y=area.top()+((i*41+int(now*8))%int(max(1,ah))); p.setPen(QPen(QColor(150,180,255,34+(i%4)*14),1)); p.drawPoint(QPointF(x,y))
            slot=aw/count
            for i,v in enumerate(values):
                h=ah*(0.03+v*0.34); p.setPen(QPen(QColor(255,255,255,145+int(v*80)),max(1.0,1.2*width_scale))); x=area.left()+i*slot+slot*0.5; p.drawLine(QPointF(x,cy-h),QPointF(x,cy+h))
            p.restore(); return

        if style == "flat_spectrum":
            # Flat Audio Spectrum custom composition.
            # - Outer line: audio-ripple style circular waveform, copied locally so audio_ripple itself is untouched.
            # - Inner layer: hologram-style rings / radial ticks, rotated counter-clockwise only inside this style.
            # - Center: no hologram music bars; use a translucent circle instead.
            mint = QColor(base_color)
            mint.setAlpha(235)
            # Side-view transform for Flat Audio Spectrum.
            # 5.0 degrees is used for the requested overall angle; vertical scale makes it look viewed from the side.
            # These can be overridden from cfg without breaking existing configs:
            #   flat_spectrum_angle_degrees=5.0
            #   flat_spectrum_side_view_y_scale=0.22
            flat_spectrum_angle_degrees = float(getattr(self.cfg, "flat_spectrum_angle_degrees", 5.0))
            flat_spectrum_side_view_y_scale = max(0.05, min(1.0, float(getattr(self.cfg, "flat_spectrum_side_view_y_scale", 0.22))))
            p.save()
            p.translate(cx, cy)
            p.rotate(flat_spectrum_angle_degrees)
            p.scale(1.0, flat_spectrum_side_view_y_scale)
            p.translate(-cx, -cy)
            outer_base_radius = max_effect_radius * 0.70
            outer_max_radius = max_effect_radius * 0.92
            outer_min_radius = max_effect_radius * 0.54
            sample_count = max(100, min(256, count if count > 0 else 128))

            # Same restrained vocal/main-source focus as audio_ripple.
            # It uses the middle band, weakens broadband bass influence, and gates idle motion.
            half_count = max(2, sample_count // 2)
            source_count = max(1, len(values))
            mid_start = min(source_count - 1, max(0, int(source_count * 0.18)))
            mid_end = min(source_count - 1, max(mid_start + 1, int(source_count * 0.64)))
            mid_span = max(1, mid_end - mid_start)
            vocal_half = []
            for si in range(half_count):
                pos = si / max(1, half_count - 1)
                src_i = mid_start + int(pos * mid_span)
                src_i = max(0, min(source_count - 1, src_i))
                center_weight = 1.0 - min(1.0, abs(pos - 0.45) / 0.45)
                band_weight = 0.36 + center_weight * 0.64
                value = max(0.0, float(values[src_i]) - bass * 0.18)
                vocal_half.append(max(0.0, min(1.0, value * band_weight * 1.58)))

            focused_values = vocal_half + list(reversed(vocal_half))
            sample_count = len(focused_values)
            focused_peak = max(focused_values) if focused_values else 0.0
            focused_avg = sum(focused_values) / max(1, len(focused_values))
            focused_energy = focused_peak * 0.68 + focused_avg * 0.32
            previous_energy = float(getattr(self, "_flat_spectrum_focused_energy", focused_energy))

            # User-tuned settings: slower gate curve and slightly slower onset denominator.
            energy_gate = max(0.0, min(1.0, (focused_energy - 0.08) / 0.57))
            onset_gate = max(0.0, min(1.0, (focused_energy - previous_energy) / 0.18))
            target_gate = max(energy_gate, onset_gate * 0.80)
            if target_gate < 0.055:
                target_gate = 0.0
            smoothed_gate = float(getattr(self, "_flat_spectrum_focused_gate", 0.0))
            if target_gate >= smoothed_gate:
                smoothed_gate = smoothed_gate * 0.54 + target_gate * 0.46
            else:
                smoothed_gate = smoothed_gate * 0.88 + target_gate * 0.12
            if smoothed_gate < 0.035:
                smoothed_gate = 0.0
            self._flat_spectrum_focused_energy = focused_energy
            self._flat_spectrum_focused_gate = smoothed_gate

            raw_fft_values = [v * smoothed_gate for v in focused_values]
            previous_smoothed = getattr(self, "_flat_spectrum_audio_ripple_smoothed", None)
            if not isinstance(previous_smoothed, list) or len(previous_smoothed) != sample_count:
                previous_smoothed = list(raw_fft_values)
            temporal_smoothed = []
            for si, current_value in enumerate(raw_fft_values):
                if current_value >= previous_smoothed[si]:
                    temporal_smoothed.append(previous_smoothed[si] * 0.70 + current_value * 0.30)
                else:
                    temporal_smoothed.append(previous_smoothed[si] * 0.90 + current_value * 0.10)
            self._flat_spectrum_audio_ripple_smoothed = temporal_smoothed
            fft_values = []
            for si, current_value in enumerate(temporal_smoothed):
                fft_values.append(
                    temporal_smoothed[si - 2] * 0.10
                    + temporal_smoothed[si - 1] * 0.20
                    + current_value * 0.40
                    + temporal_smoothed[(si + 1) % sample_count] * 0.20
                    + temporal_smoothed[(si + 2) % sample_count] * 0.10
                )
            local_peak = max(raw_fft_values) if raw_fft_values else 0.0
            smoothed_peak = max(fft_values) if fft_values else 0.0
            volume_peak_gate = max(0.0, min(1.0, (max(local_peak, smoothed_peak, bass, avg) - 0.58) / 0.42))
            available_push = max(8.0, outer_max_radius - outer_base_radius)
            outer_points = []
            white_spark_points = []
            for si, fft_value in enumerate(fft_values):
                sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(si, sample_count)
                angle = -math.pi / 2.0 + (si / sample_count) * math.tau
                prev_v = fft_values[si - 1]
                next_v = fft_values[(si + 1) % sample_count]
                local_contrast = max(0.0, fft_value - (prev_v + next_v) * 0.5)
                spike_gate = max(0.0, min(1.0, (fft_value - 0.64) / 0.36))
                mirror_i = min(si, sample_count - 1 - si)
                seed = ((mirror_i * 37 + 13) % 97) / 97.0
                raw_value = raw_fft_values[si]
                raw_prev = raw_fft_values[si - 1]
                raw_next = raw_fft_values[(si + 1) % sample_count]
                raw_contrast = max(0.0, raw_value - (raw_prev + raw_next) * 0.5)
                transient_gate = max(0.0, min(1.0, (raw_value - temporal_smoothed[si]) / 0.16))
                level_gate = max(0.0, min(1.0, (raw_value - 0.055) / 0.34))
                peak_gate = max(0.0, min(1.0, volume_peak_gate)) * smoothed_gate
                audio_reactivity = max(transient_gate * 1.10, spike_gate * smoothed_gate, level_gate * 1.28, peak_gate * 0.22)
                audio_reactivity = max(0.0, min(1.0, audio_reactivity))
                audio_reactivity = audio_reactivity * audio_reactivity
                tip_speed = 0.32 + seed * 0.22 + audio_reactivity * 0.55
                snap_cycle = now * tip_speed + seed * 5.0 + mirror_i * 0.031
                snap_phase = snap_cycle - math.floor(snap_cycle)
                if snap_phase < 0.050:
                    snap_envelope = snap_phase / 0.050
                elif snap_phase < 0.210:
                    snap_envelope = 1.0 - (snap_phase - 0.050) / 0.160
                else:
                    snap_envelope = 0.0
                snap_envelope = max(0.0, min(1.0, snap_envelope)) * audio_reactivity
                snap_index = int(math.floor(snap_cycle))
                tip_sign = -1.0 if ((snap_index + mirror_i * 3) % 5) < 2 else 1.0
                tip_energy = max(raw_value, raw_contrast * 3.2, local_contrast * 2.4, spike_gate)
                tip_amount = tip_energy * available_push * (0.12 + 0.52 * audio_reactivity) * snap_envelope
                rr = max(outer_min_radius, min(outer_base_radius + tip_sign * tip_amount, outer_max_radius))
                point = QPointF(cx + cos_a * rr, cy + sin_a * rr)
                outer_points.append(point)

                # Spark follows the added white outer line and appears only on real jagged snaps.
                spark_strength = snap_envelope * audio_reactivity * max(0.0, min(0.36, tip_amount / max(1.0, available_push * 0.22)))
                if spark_strength > 0.30:
                    spark_radius = rr + 2.0
                    white_spark_points.append((
                        QPointF(cx + cos_a * spark_radius, cy + sin_a * spark_radius),
                        angle,
                        max(0.0, min(1.0, spark_strength)),
                        seed,
                    ))
            if outer_points:
                outer_path = QPainterPath(outer_points[0])
                for pt in outer_points[1:]:
                    outer_path.lineTo(pt)
                outer_path.closeSubpath()
                def _make_outer_offset_path(offset):
                    offset_path = QPainterPath()
                    first = outer_points[0]
                    first_len = max(1.0, math.hypot(first.x() - cx, first.y() - cy))
                    offset_path.moveTo(QPointF(first.x() + (first.x() - cx) / first_len * offset, first.y() + (first.y() - cy) / first_len * offset))
                    for pt in outer_points[1:]:
                        plen = max(1.0, math.hypot(pt.x() - cx, pt.y() - cy))
                        offset_path.lineTo(QPointF(pt.x() + (pt.x() - cx) / plen * offset, pt.y() + (pt.y() - cy) / plen * offset))
                    offset_path.closeSubpath()
                    return offset_path

                for offset, alpha_scale in ((-3.0, 0.22), (3.0, 0.16)):
                    offset_path = _make_outer_offset_path(offset)
                    trail_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), int(32 * alpha_scale)), max(1.0, 1.25 * width_scale))
                    trail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    trail_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(trail_pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(offset_path)
                glow_pen_1 = QPen(QColor(mint.red(), mint.green(), mint.blue(), 20), max(8.0, 8.0 * width_scale + bass * 4.0))
                glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_1)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(outer_path)
                glow_pen_2 = QPen(QColor(mint.red(), mint.green(), mint.blue(), 40), max(5.0, 5.0 * width_scale + bass * 2.0))
                glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_2)
                p.drawPath(outer_path)

                # Second white line, placed 2 px outside the flat-spectrum outer ripple.
                white_outer_path = _make_outer_offset_path(2.0)
                white_glow_pen_1 = QPen(QColor(255, 255, 255, 40), max(7.0, 8.5 * width_scale + smoothed_gate * 3.0))
                white_glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_1)
                p.drawPath(white_outer_path)
                white_glow_pen_2 = QPen(QColor(255, 255, 255, 72), max(3.6, 4.5 * width_scale + smoothed_gate * 1.6))
                white_glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_2)
                p.drawPath(white_outer_path)
                white_pen = QPen(QColor(255, 255, 255, 238), max(1.2, 2.0 * width_scale))
                white_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_pen)
                p.drawPath(white_outer_path)

                core_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), 255), max(1.4, 2.0 * width_scale))
                core_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                core_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(core_pen)
                p.drawPath(outer_path)

                if white_spark_points:
                    for spark_pt, spark_angle, spark_strength, spark_seed in white_spark_points:
                        spark_alpha = max(0, min(255, int(70 + spark_strength * 185)))
                        spark_size = short_side * (0.006 + spark_strength * 0.012)
                        self._draw_visualizer_soft_orb(p, spark_pt, spark_size * 2.8, QColor(255, 255, 255, spark_alpha), spark_alpha)
                        spark_sin, spark_cos = self._flat_spectrum_sin_cos_from_angle(spark_angle)
                        radial = QPointF(spark_cos, spark_sin)
                        tangent = QPointF(-spark_sin, spark_cos)
                        ray_len = spark_size * (1.45 + spark_strength * 1.35)
                        ray_alpha = max(0, min(255, int(105 + spark_strength * 125)))
                        ray_pen = QPen(QColor(255, 255, 255, ray_alpha), max(0.7, 1.15 * width_scale))
                        ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(ray_pen)
                        p.drawLine(
                            QPointF(spark_pt.x() - radial.x() * ray_len, spark_pt.y() - radial.y() * ray_len),
                            QPointF(spark_pt.x() + radial.x() * ray_len, spark_pt.y() + radial.y() * ray_len),
                        )
                        p.drawLine(
                            QPointF(spark_pt.x() - tangent.x() * ray_len * 0.62, spark_pt.y() - tangent.y() * ray_len * 0.62),
                            QPointF(spark_pt.x() + tangent.x() * ray_len * 0.62, spark_pt.y() + tangent.y() * ray_len * 0.62),
                        )

            flat_spectrum_rotation_degrees = self._flat_spectrum_inner_rotation_degrees(now)
            flat_spectrum_rotation_degrees2 = self._flat_spectrum_inner_rotation_degrees2(now)
            p.save()
            try:
                p.translate(cx, cy)
                p.rotate(flat_spectrum_rotation_degrees)
                p.translate(-cx, -cy)
                static_hologram_image, static_hologram_radius = self._flat_spectrum_static_hologram_image(max_effect_radius, base_color, width_scale)
                if static_hologram_image is not None and static_hologram_radius > 0:
                    p.drawImage(
                        QRectF(
                            cx - static_hologram_radius,
                            cy - static_hologram_radius,
                            static_hologram_radius * 2,
                            static_hologram_radius * 2,
                        ),
                        static_hologram_image,
                    )
                hologram_outer_circle_radius = max_effect_radius * 0.53
                hologram_max_bar_overhang_px = 10.0
                hologram_inner_bar_alpha = 235
                hologram_outer_bar_alpha = int(255 * 0.40)
                for hi in range(0, count, max(1, count // 72)):
                    v = values[hi]
                    sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(hi, count)
                    base_inner = max_effect_radius * 0.44
                    max_outer = hologram_outer_circle_radius + hologram_max_bar_overhang_px
                    max_len = min(30.0, max(0.0, max_outer - base_inner))
                    min_bar_len = min(max_len, max(2.0, short_side * 0.025))
                    max_bar_len = max(min_bar_len, max_len)
                    threshold = max(0.12, avg * 1.20)
                    band_signal = max(float(v), bass * 0.72)
                    peak_amount = max(0.0, min(1.0, (band_signal - threshold) / max(0.001, 1.0 - threshold)))
                    peak_amount = peak_amount * peak_amount * (3.0 - 2.0 * peak_amount)
                    wave = 0.92 + 0.08 * math.sin(now * (2.8 + peak_amount * 3.0) + hi * 0.31)
                    motion = max(0.0, min(1.0, peak_amount * wave))
                    bar_len = min(max_len, min_bar_len + (max_bar_len - min_bar_len) * motion)
                    inner = base_inner
                    outer = min(max_outer, inner + bar_len)
                    if outer <= inner:
                        continue
                    steps = max(1, int(math.ceil(outer - inner)))
                    pen_width = max(1.4, min(5.0, 2.6 * width_scale))
                    for hs in range(steps):
                        r1 = inner + hs
                        r2 = min(outer, inner + hs + 1.0)
                        if r2 <= r1:
                            continue
                        t = hs / max(1, steps - 1)
                        alpha = int(hologram_inner_bar_alpha * (1.0 - t) + hologram_outer_bar_alpha * t)
                        c = QColor(base_color)
                        c.setAlpha(alpha)
                        p.setPen(QPen(c, pen_width))
                        p.drawLine(QPointF(cx + cos_a * r1, cy + sin_a * r1), QPointF(cx + cos_a * r2, cy + sin_a * r2))
            finally:
                p.restore()

            center_radius = max(5.0, max_effect_radius * 0.23)
            center_grad = QRadialGradient(QPointF(cx, cy), center_radius)
            center_grad.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 78))
            center_grad.setColorAt(0.62, QColor(base_color.red(), base_color.green(), base_color.blue(), 44))
            center_grad.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 18))
            p.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 92), max(1.0, 1.0 * width_scale)))
            p.setBrush(QBrush(center_grad))
            p.drawEllipse(QPointF(cx, cy), center_radius, center_radius)
            p.restore()
            p.restore(); return

        if style == "dynamic_glitch":
            # Dark frosted jagged rainbow waveform moving left.
            pts=[]
            for i,v in enumerate(values):
                x=area.left()+((aw*i/max(1,count-1)-(now*34%max(1,aw)))%aw); y=cy+((-1)**i)*ah*(0.025+v*0.20); pts.append(QPointF(x,y))
            for i in range(1,len(pts)):
                col=self._rainbow_color(i/max(1,len(pts))+now*0.02,90,0.55,0.8); p.setPen(QPen(col,max(1.0,2.2*width_scale))); p.drawLine(pts[i-1],pts[i])
            p.restore(); return

        if style == "cyber":
            # Long color-shifting line with downward bars and falling fading particles.
            base_y=area.top()+ah*0.28; slot=aw/count
            for i,v in enumerate(values):
                x=area.left()+i*slot; col=self._rainbow_color(i/count*0.85+now*0.035,150+int(v*80),0.85,1.0); p.setPen(QPen(col,max(1.0,1.6*width_scale)))
                if i>0: p.drawLine(QPointF(x-slot,base_y+math.sin((i-1)*0.08+now)*ah*0.025),QPointF(x,base_y+math.sin(i*0.08+now)*ah*0.025))
                h=ah*(0.04+v*0.55); p.setPen(QPen(col,max(1.0,1.3*width_scale))); p.drawLine(QPointF(x,base_y),QPointF(x,base_y+h))
                if i%max(1,count//36)==0:
                    age=(now*0.65+i*0.021)%1.0; pc=QColor(col); pc.setAlpha(int((1.0-age)*120)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(pc)); p.drawEllipse(QPointF(x,base_y+h+age*ah*0.16),1.5+v*2.0,1.5+v*2.0)
            p.restore(); return

        # Spec-final visualizer skins: cinematic QPainter-only implementations, avoiding chart/ECG-like line graphs.
        if style == "bass_drop":
            sx=math.sin(now*28.0)*bass*short_side*0.015; sy=math.cos(now*24.0)*bass*short_side*0.012; ccx=cx+sx; ccy=cy+sy
            core=min(max_effect_radius*0.54, short_side*(0.23+bass*0.10))
            if glow_enabled: self._draw_visualizer_soft_orb(p,QPointF(ccx,ccy),core*(1.26+bass*0.25),QColor(base_color.red(),base_color.green(),base_color.blue(),88),40+int(bass*78))
            for k in range(34):
                ph=(k*0.618+now*0.05)%1.0; rr=core*(0.12+((k*37)%100)/100*0.70); a=ph*math.tau+math.sin(now*0.7+k)*0.18
                pc=QColor(base_color); pc.setAlpha(38+int(avg*72)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(pc)); p.drawEllipse(QPointF(ccx+math.cos(a)*rr,ccy+math.sin(a)*rr),1.3+bass*1.6,1.3+bass*1.6)
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,172+int(bass*55)),max(1.2,2.1*width_scale))); p.drawEllipse(QPointF(ccx,ccy),core,core)
            palette=[QColor(135,60,255),QColor(45,150,255),QColor(255,70,90)]; step=max(1,count//96)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2+math.sin(now*2+i*0.08)*bass*0.10; stretch=short_side*(0.035+v*0.12+bass*0.12); inner=core*(0.94-v*0.05); outer=min(max_effect_radius*0.98,core+stretch)
                ci=QColor(255,255,255,165+int(v*65)); co=QColor(palette[(i//step)%3]); co.setAlpha(170+int(v*70)); p.setPen(QPen(ci,max(1.0,(1.2+v*2.4)*width_scale))); p.drawLine(QPointF(ccx+math.cos(a)*inner,ccy+math.sin(a)*inner),QPointF(ccx+math.cos(a)*(inner+stretch*0.42),ccy+math.sin(a)*(inner+stretch*0.42)))
                p.setPen(QPen(co,max(1.0,(1.5+v*4.2+bass*2.8)*width_scale))); p.drawLine(QPointF(ccx+math.cos(a)*(inner+stretch*0.36),ccy+math.sin(a)*(inner+stretch*0.36)),QPointF(ccx+math.cos(a)*outer,ccy+math.sin(a)*outer))
            p.restore(); return

        if style == "melodic_vibe":
            for k in range(34):
                ph=k/34; rr=max_effect_radius*(0.08+ph*0.88); a=now*(0.16+ph*0.10)+ph*math.tau*2.6
                x=cx+math.cos(a)*rr*(0.30+ph*0.52); y=cy+math.sin(a*1.12)*rr*(0.22+ph*0.38); alpha=max(12,int((50+avg*56)*(1-ph*0.62)))
                self._draw_visualizer_soft_orb(p,QPointF(x,y),short_side*(0.085+ph*0.060),QColor(255,255,255,alpha),alpha)
            ac=QColor(base_color); ac.setAlpha(34+int(avg*76)); self._draw_visualizer_soft_orb(p,QPointF(cx,cy),max_effect_radius*(0.74+bass*0.16),ac,ac.alpha())
            p.restore(); return

        if style == "alternative":
            pts=[]; smooth=avg
            for i,raw in enumerate(values):
                smooth=smooth*0.78+raw*0.22; x=area.left()+aw*i/max(1,count-1); y=cy+math.sin(i*0.08+now*0.82)*ah*0.16-(smooth-avg)*ah*0.30; pts.append(QPointF(x,y))
            stride=max(1,count//74); p.setPen(Qt.PenStyle.NoPen)
            for i in range(0,len(pts),stride):
                v=values[min(i,count-1)]; shade=205 if i%2 else 245; col=QColor(shade,shade,shade,100+int(v*125)); p.setBrush(QBrush(col)); rod_h=5.6*width_scale; rod_w=max(2.0,aw/max(40,count)*0.92); p.drawRoundedRect(QRectF(pts[i].x()-rod_w*0.5,pts[i].y()-rod_h*0.5,rod_w,rod_h),3,3)
                if i==0 or i+stride>=len(pts): p.drawEllipse(pts[i],rod_h*0.76,rod_h*0.76)
            p.restore(); return

        if style == "circle":
            core=min(radius,max_effect_radius*0.52); rot=now*0.18; sample_count=max(96,min(224,count)); outer_pts=[]; inner_pts=[]; first_outer=None; first_inner=None
            for s in range(sample_count+1):
                if s==sample_count and first_outer is not None:
                    outer_pts.append(QPointF(first_outer)); inner_pts.append(QPointF(first_inner)); continue
                src=int(s*count/sample_count)%count; v=values[src]; a=s/sample_count*math.tau-math.pi/2+rot; wob=math.sin(now*1.2+s*0.12)*0.022; inner=core*(0.90+avg*0.04+wob); outer=min(max_effect_radius*0.98,core+short_side*(0.045+v*0.18)); op=QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer); ip=QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner)
                if s==0: first_outer=QPointF(op); first_inner=QPointF(ip)
                outer_pts.append(op); inner_pts.append(ip)
            path=QPainterPath(outer_pts[0]); [path.lineTo(pt) for pt in outer_pts[1:]]; [path.lineTo(pt) for pt in reversed(inner_pts)]; path.closeSubpath(); fill=QColor(base_color); fill.setAlpha(98+int(avg*85)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(fill)); p.drawPath(path)
            edge=QColor(base_color); edge.setAlpha(160+int(avg*70)); pen=QPen(edge,max(1.0,1.65*width_scale)); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(pen); outer_path=QPainterPath(outer_pts[0]); [outer_path.lineTo(pt) for pt in outer_pts[1:]]; outer_path.closeSubpath(); inner_path=QPainterPath(inner_pts[0]); [inner_path.lineTo(pt) for pt in inner_pts[1:]]; inner_path.closeSubpath(); p.drawPath(outer_path); p.drawPath(inner_path)
            p.restore(); return

        if style == "ellipse":
            rx_scale=1.58; ry_scale=0.54; core=min(radius,max_effect_radius*0.48); step=max(1,count//84)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2; inner=core; outer=min(max_effect_radius*0.96,inner+short_side*(0.035+v*0.16)); col=QColor(base_color); col.setAlpha(135+int(v*110)); p.setPen(QPen(col,max(1.0,(1.25+v*3.0)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner*rx_scale,cy+math.sin(a)*inner*ry_scale),QPointF(cx+math.cos(a)*outer*rx_scale,cy+math.sin(a)*outer*ry_scale))
            p.restore(); return

        if style == "turntable":
            disc_r=min(max_effect_radius*0.62,short_side*0.31); grad=QRadialGradient(QPointF(cx,cy),disc_r); grad.setColorAt(0,QColor(245,248,255,235)); grad.setColorAt(0.20,QColor(base_color.red(),base_color.green(),base_color.blue(),135)); grad.setColorAt(0.45,QColor(26,28,35,230)); grad.setColorAt(1,QColor(4,5,8,240)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawEllipse(QPointF(cx,cy),disc_r,disc_r); p.setBrush(Qt.BrushStyle.NoBrush)
            for k in range(5): rr=disc_r*(0.34+k*0.13+math.sin(now*1.2+k)*0.006); p.setPen(QPen(QColor(210,220,235,55+k*14),max(0.8,1.0*width_scale))); p.drawEllipse(QPointF(cx,cy),rr,rr)
            turntable_cover_radius=max(1.0,disc_r*0.84-10.0)
            turntable_cover_rect=QRectF(cx-turntable_cover_radius,cy-turntable_cover_radius,turntable_cover_radius*2.0,turntable_cover_radius*2.0)
            p.save()
            try:
                p.translate(cx,cy); p.rotate(math.degrees(now*0.55)); p.translate(-cx,-cy)
                self._draw_visualizer_media_thumbnail_cover(p,turntable_cover_rect,ctx,clip_radius=turntable_cover_radius,fallback_accent=base_color)
            finally:
                p.restore()
            step=max(1,count//72)
            for i in range(0,count,step): v=values[i]; a=i/count*math.tau-math.pi/2; inner=disc_r*0.90; outer=min(max_effect_radius*0.98,inner+short_side*(0.024+v*0.13)); p.setPen(QPen(QColor(230,235,245,115+int(v*115)),max(1.0,(1+v*2.8)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer))
            p.restore(); return

        if style == "spotlight_beat":
            for ring in range(2):
                ring_pulse=1.0+bass*(0.025+ring*0.012); rx=max_effect_radius*(0.54+ring*0.22)*ring_pulse; ry=rx*(0.45+bass*0.018); phase=now*(0.36 if ring==0 else -0.32)
                for k in range(42):
                    v=values[(k*count//42)%count]; a=k/42*math.tau+phase+math.sin(now*1.20+k*0.17)*v*0.050; stretch=1.0+v*4.85+bass*0.90; x=cx+math.cos(a)*rx; y=cy+math.sin(a)*ry*(-1 if ring else 1); col=QColor(base_color) if ring else QColor(245,248,255); col.setAlpha(72+int(v*175));
                    if glow_enabled: self._draw_visualizer_soft_orb(p,QPointF(x,y),5.0+v*16.0,col,30+int(v*78))
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); bar_w=max(3.8,4.95*width_scale); bar_h=bar_w*stretch; p.drawRoundedRect(QRectF(x-bar_w*0.5,y-bar_h*0.5,bar_w,bar_h),3,3)
            p.restore(); return

        if style == "audio_react":
            self._draw_visualizer_soft_orb(p,QPointF(cx,cy),max_effect_radius*0.76,QColor(base_color.red(),base_color.green(),base_color.blue(),85),42+int(avg*70)); p.setBrush(QBrush(QColor(base_color.red(),base_color.green(),base_color.blue(),44))); p.setPen(QPen(QColor(255,255,255,60),max(1.0,1.0*width_scale))); p.drawEllipse(QPointF(cx,cy),radius*1.15,radius*1.15); pts=[]; step=max(1,count//128)
            for i in range(0,count,step): v=values[i]; a=i/count*math.tau-math.pi/2; rr=radius*1.10+short_side*(0.025+v*0.15)+math.sin(now*1.7+i*0.10)*short_side*0.012; pts.append(QPointF(cx+math.cos(a)*rr,cy+math.sin(a)*rr))
            path=QPainterPath(pts[0]); [path.lineTo(pt) for pt in pts[1:]]; path.closeSubpath(); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,160+int(avg*70)),max(1.0,2.0*width_scale))); p.drawPath(path); p.restore(); return

        if style == "retro_future":
            gap=aw*0.08
            for side in (-1,1):
                base_x=cx+side*gap; prev=None
                for j in range(18):
                    t=j/17; y=area.bottom()-t*ah; x=base_x+math.sin(now*1.1+t*6+side)*aw*0.025; col=QColor(base_color); col.setAlpha(max(18,int((1-t)*130+avg*55))); p.setPen(QPen(col,max(1.0,(2.6-t*1.4)*width_scale)))
                    if prev: p.drawLine(prev,QPointF(x,y))
                    prev=QPointF(x,y)
            p.restore(); return

        if style == "rainbow":
            # Fine iridescent scale-powder steam version, emitted only on bar peaks.
            # Bars stay compact; particles are small flattened flakes with per-flake rainbow gradients.
            # Peak detection compares this frame against the previous frame, then keeps spawned powder alive briefly.
            slot=aw/count
            bw=max(1.0,slot*0.38*width_scale)
            
            particle_step=max(1,count//15)
            # Left-edge bass push: on a deep bass transient, move only the existing left bars.
            # No oscillation is added; the bars push once with the bass envelope and then return smoothly.
            prev_left_bass=float(getattr(self,"_rainbow_left_edge_prev_bass",bass))
            left_bass_rise=bass-prev_left_bass
            self._rainbow_left_edge_prev_bass=bass
            prev_left_time=float(getattr(self,"_rainbow_left_edge_last_time",now))
            left_dt=max(0.0,min(0.10,now-prev_left_time))
            self._rainbow_left_edge_last_time=now
            prev_left_push=float(getattr(self,"_rainbow_left_edge_push",0.0))
            left_edge_target=0.0
            if bass>=0.18 and left_bass_rise>=0.035:
                left_edge_target=max(0.0,min(1.0,(bass-0.18)*3.0+left_bass_rise*8.0))
            left_edge_push=0
            self._rainbow_left_edge_push=left_edge_push
            bar_tops=[]
            for i,v in enumerate(values):
                t=i/max(1,count-1)
                # Tone layout across the bar field:
                # left = low/bass, center = high/treble, right = mid/vocal-like band.
                low_idx=max(0,min(count-1,int((0.05+0.11*t)*(count-1))))
                mid_idx=max(0,min(count-1,int((0.42+0.18*t)*(count-1))))
                high_idx=max(0,min(count-1,int((0.74+0.10*(1.0-abs(t-0.5)*2.0))*(count-1))))
                low_v=values[low_idx]
                mid_v=values[mid_idx]
                high_v=values[high_idx]
                low_weight=(1.0-t)**8.55
                mid_weight=t**0.85
                high_weight=max(0.0,1.0-abs(t-0.5)*2.0)**1.80*1.65
                local_weight=0.012
                avg_weight=0.0008
                weight_sum=low_weight+mid_weight+high_weight+local_weight+avg_weight
                tone_v=max(0.0,min(1.0,(low_v*low_weight+mid_v*mid_weight+high_v*high_weight+v*local_weight+avg*avg_weight)/max(0.001,weight_sum)))
                x=area.left()+i*slot
                h=ah*(0.030+tone_v*0.340)
                left_edge_weight=max(0.0,1.0-t*5.0)**1.70
                if left_edge_push>0.001 and left_edge_weight>0.001:
                    x+=left_edge_weight*left_edge_push*slot*0.85
                c=self._rainbow_lut_color(t+now*0.050,230)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(c))
                bx=x+slot*0.31
                p.drawRoundedRect(QRectF(bx,cy-h,bw,h),3,3)
                bar_tops.append((x+slot*0.5,cy-h,t,tone_v))
                ref=QColor(c)
                ref.setAlpha(14+int(tone_v*22))
                p.setBrush(QBrush(ref))
                p.drawRoundedRect(QRectF(bx,cy+2,bw,h*0.12),3,3)

            # Spawn powder only when a sampled bar sharply rises into a peak.
            # peak_rise_threshold: larger = stricter peak-only emission; smaller = more frequent powder.
            # peak_level_threshold: larger = only taller bars emit powder.
            peak_rise_threshold=0.055
            peak_level_threshold=0.120
            peak_cooldown=0.140
            powder_life=1.01
            prev_levels=getattr(self,"_rainbow_peak_prev_levels",None)
            if not isinstance(prev_levels,list) or len(prev_levels)!=len(bar_tops):
                prev_levels=[0.0]*len(bar_tops)
            last_spawn=getattr(self,"_rainbow_peak_last_spawn",None)
            if not isinstance(last_spawn,list) or len(last_spawn)!=len(bar_tops):
                last_spawn=[-9999.0]*len(bar_tops)
            particles=getattr(self,"_rainbow_peak_particles",None)
            if not isinstance(particles,list):
                particles=[]
            for i in range(0,len(bar_tops),particle_step):
                base_x,base_y,t,tone_v=bar_tops[i]
                rise=tone_v-prev_levels[i]
                if tone_v>=peak_level_threshold and rise>=peak_rise_threshold and now-last_spawn[i]>=peak_cooldown:
                    for spark in range(6):
                        seed=(i*0.017+spark*0.109+now*0.013)%1.0
                        particles.append((now,base_x,base_y,t,tone_v,spark,seed))
                    last_spawn[i]=now
            self._rainbow_peak_prev_levels=[bt[3] for bt in bar_tops]
            self._rainbow_peak_last_spawn=last_spawn

            # Draw only particles that were born from peaks; they rise and fade after the peak.
            p.setPen(Qt.PenStyle.NoPen)
            active_particles=[]
            for birth,base_x,base_y,t,tone_v,spark,seed in particles:
                age=(now-birth)/max(0.001,powder_life)
                if age<0.0 or age>=1.0:
                    continue
                active_particles.append((birth,base_x,base_y,t,tone_v,spark,seed))
                flutter=math.sin(now*1.35+seed*17.0+spark*1.77)*slot*(0.85+age*2.35)
                flutter+=math.sin(now*2.55+seed*11.0+spark*2.63)*slot*(0.38+age*1.15)
                flutter+=math.sin(age*math.tau*2.5+spark*0.73)*slot*0.44
                px=base_x+flutter+(spark-4)*slot*0.105
                py=base_y-age*ah*(0.42+tone_v*0.30)-spark*ah*0.005+math.sin(now*1.90+i*0.11+spark)*ah*0.014
                pr=(0.65+tone_v*1.05+(spark%3)*0.885)*max(1.0,width_scale)
                angle=math.sin(now*1.65+seed*13.0+spark*0.97)*58.0+age*155.0+spark*23.0
                fade=max(0.0,1.0-age)
                alpha=max(0,int((fade*fade*fade)*230))
                hue_bucket=int(((t+spark*0.081+now*0.030+age*0.065)%1.0)*24.0)
                size_bucket=max(0,min(2,int(tone_v*3.0)))
                angle_bucket=int((angle%360.0)/22.5)%16
                sprite=self._get_rainbow_powder_sprite(hue_bucket,size_bucket,angle_bucket)
                draw_size=max(3.0,pr*4.2)
                p.save()
                p.setOpacity(max(0.0,min(1.0,alpha/255.0)))
                p.drawImage(QRectF(px-draw_size*0.5,py-draw_size*0.5,draw_size,draw_size),sprite)
                p.restore()
            self._rainbow_peak_particles=active_particles[-700:]
            p.restore(); return

        if style == "minimal":
            slot=aw/count; col=QColor(base_color); col.setAlpha(195); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
            for i,v in enumerate(values): h=ah*(0.025+v*0.46); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.28,cy-h*0.5,max(1.0,slot*min(0.80,0.44*width_scale)),h),2,2)
            p.restore(); return

        if style == "urban_timelapse":
            lanes=min(18,max(8,count//5))
            for i in range(lanes): v=values[int(i*count/lanes)]; y=area.top()+ah*(0.16+(i%lanes)/max(1,lanes-1)*0.68); x0=area.left()+((now*(35+i*2)+i*31)%max(1.0,aw)); length=aw*(0.10+v*0.18); col=QColor(80,170,255,100+int(v*90)) if i%2 else QColor(255,155,55,100+int(v*90)); p.setPen(QPen(col,max(1.0,(1.2+v*2.2)*width_scale))); p.drawLine(QPointF(x0-length,y),QPointF(x0,y)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawEllipse(QPointF(x0,y+math.sin(now*2+i)*ah*0.025),2+v*3,2+v*3)
            p.restore(); return

        if style == "music_beat_wall":
            slot=aw/count
            for i,v in enumerate(values): h=ah*(0.06+v*0.76); col=QColor(base_color); col.setAlpha(102+int(v*55)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.16,area.bottom()-h,max(1.0,slot*min(0.92,0.64*width_scale)),h),3,3)
            p.restore(); return

        if style == "led_audio_wave":
            rail_gap=ah*0.10; p.setPen(QPen(QColor(base_color.red(),base_color.green(),base_color.blue(),70),max(1.0,1.0*width_scale))); p.drawLine(QPointF(area.left(),cy-rail_gap),QPointF(area.right(),cy-rail_gap)); p.drawLine(QPointF(area.left(),cy+rail_gap),QPointF(area.right(),cy+rail_gap)); pts=[]; smooth=avg
            for i,raw in enumerate(values): smooth=smooth*0.78+raw*0.22; x=area.left()+aw*i/max(1,count-1); y=cy+math.sin(i*0.15+now*1.6)*ah*0.055-(smooth-avg)*ah*0.20; pts.append(QPointF(x,y))
            self._draw_visualizer_polyline(p,pts,QColor(base_color),2.0*width_scale,145)
            for i in range(0,len(pts),max(1,len(pts)//18)): age=(now*0.7+i*0.03)%1.0; c=QColor(base_color); c.setAlpha(int((1-age)*125)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(c)); p.drawEllipse(pts[i],2,2)
            p.restore(); return

        if style == "euphoria_motion":
            for k in range(6): v=values[int(k*count/6)]; y=cy+(k-2.5)*ah*0.095+math.sin(now*3+k)*bass*ah*0.025; length=aw*(0.22+v*0.34+bass*0.10); p.setPen(QPen(QColor(250,250,255,135+int(v*100)),max(2.0,(3+v*6)*width_scale))); p.drawLine(QPointF(cx-length*0.5,y),QPointF(cx+length*0.5,y))
            p.restore(); return

        if style == "luminance":
            self._paint_luminance_wave_scene(p, values, area, base_color, now, avg, width_scale)
            p.restore(); return

        if style == "hud_equalizer":
            self._paint_hud_equalizer_scene(p, values, area, base_color, now, width_scale)
            p.restore(); return

        if style == "space":
            for i in range(54): x=area.left()+((i*73+int(now*20))%int(max(1,aw))); y=area.top()+((i*41+int(now*8))%int(max(1,ah))); p.setPen(QPen(QColor(150,180,255,34+(i%4)*14),1)); p.drawPoint(QPointF(x,y))
            slot=aw/count
            for i,v in enumerate(values): h=ah*(0.03+v*0.34); p.setPen(QPen(QColor(255,255,255,145+int(v*80)),max(1.0,1.2*width_scale))); x=area.left()+i*slot+slot*0.5; p.drawLine(QPointF(x,cy-h),QPointF(x,cy+h))
            p.restore(); return

        if style == "flat_spectrum":
            # Flat Audio Spectrum custom composition.
            # - Outer line: audio-ripple style circular waveform, copied locally so audio_ripple itself is untouched.
            # - Inner layer: hologram-style rings / radial ticks, rotated counter-clockwise only inside this style.
            # - Center: no hologram music bars; use a translucent circle instead.
            mint = QColor(base_color)
            mint.setAlpha(235)
            # Side-view transform for Flat Audio Spectrum.
            # 5.0 degrees is used for the requested overall angle; vertical scale makes it look viewed from the side.
            # These can be overridden from cfg without breaking existing configs:
            #   flat_spectrum_angle_degrees=5.0
            #   flat_spectrum_side_view_y_scale=0.22
            flat_spectrum_angle_degrees = float(getattr(self.cfg, "flat_spectrum_angle_degrees", 5.0))
            flat_spectrum_side_view_y_scale = max(0.05, min(1.0, float(getattr(self.cfg, "flat_spectrum_side_view_y_scale", 0.22))))
            p.save()
            p.translate(cx, cy)
            p.rotate(flat_spectrum_angle_degrees)
            p.scale(1.0, flat_spectrum_side_view_y_scale)
            p.translate(-cx, -cy)
            outer_base_radius = max_effect_radius * 0.70
            outer_max_radius = max_effect_radius * 0.92
            outer_min_radius = max_effect_radius * 0.54
            sample_count = max(100, min(256, count if count > 0 else 128))

            # Same restrained vocal/main-source focus as audio_ripple.
            # It uses the middle band, weakens broadband bass influence, and gates idle motion.
            half_count = max(2, sample_count // 2)
            source_count = max(1, len(values))
            mid_start = min(source_count - 1, max(0, int(source_count * 0.18)))
            mid_end = min(source_count - 1, max(mid_start + 1, int(source_count * 0.64)))
            mid_span = max(1, mid_end - mid_start)
            vocal_half = []
            for si in range(half_count):
                pos = si / max(1, half_count - 1)
                src_i = mid_start + int(pos * mid_span)
                src_i = max(0, min(source_count - 1, src_i))
                center_weight = 1.0 - min(1.0, abs(pos - 0.45) / 0.45)
                band_weight = 0.36 + center_weight * 0.64
                value = max(0.0, float(values[src_i]) - bass * 0.18)
                vocal_half.append(max(0.0, min(1.0, value * band_weight * 1.58)))

            focused_values = vocal_half + list(reversed(vocal_half))
            sample_count = len(focused_values)
            focused_peak = max(focused_values) if focused_values else 0.0
            focused_avg = sum(focused_values) / max(1, len(focused_values))
            focused_energy = focused_peak * 0.68 + focused_avg * 0.32
            previous_energy = float(getattr(self, "_flat_spectrum_focused_energy", focused_energy))

            # User-tuned settings: slower gate curve and slightly slower onset denominator.
            energy_gate = max(0.0, min(1.0, (focused_energy - 0.08) / 0.57))
            onset_gate = max(0.0, min(1.0, (focused_energy - previous_energy) / 0.18))
            target_gate = max(energy_gate, onset_gate * 0.80)
            if target_gate < 0.055:
                target_gate = 0.0
            smoothed_gate = float(getattr(self, "_flat_spectrum_focused_gate", 0.0))
            if target_gate >= smoothed_gate:
                smoothed_gate = smoothed_gate * 0.54 + target_gate * 0.46
            else:
                smoothed_gate = smoothed_gate * 0.88 + target_gate * 0.12
            if smoothed_gate < 0.035:
                smoothed_gate = 0.0
            self._flat_spectrum_focused_energy = focused_energy
            self._flat_spectrum_focused_gate = smoothed_gate

            raw_fft_values = [v * smoothed_gate for v in focused_values]
            previous_smoothed = getattr(self, "_flat_spectrum_audio_ripple_smoothed", None)
            if not isinstance(previous_smoothed, list) or len(previous_smoothed) != sample_count:
                previous_smoothed = list(raw_fft_values)
            temporal_smoothed = []
            for si, current_value in enumerate(raw_fft_values):
                if current_value >= previous_smoothed[si]:
                    temporal_smoothed.append(previous_smoothed[si] * 0.70 + current_value * 0.30)
                else:
                    temporal_smoothed.append(previous_smoothed[si] * 0.90 + current_value * 0.10)
            self._flat_spectrum_audio_ripple_smoothed = temporal_smoothed
            fft_values = []
            for si, current_value in enumerate(temporal_smoothed):
                fft_values.append(
                    temporal_smoothed[si - 2] * 0.10
                    + temporal_smoothed[si - 1] * 0.20
                    + current_value * 0.40
                    + temporal_smoothed[(si + 1) % sample_count] * 0.20
                    + temporal_smoothed[(si + 2) % sample_count] * 0.10
                )
            local_peak = max(raw_fft_values) if raw_fft_values else 0.0
            smoothed_peak = max(fft_values) if fft_values else 0.0
            volume_peak_gate = max(0.0, min(1.0, (max(local_peak, smoothed_peak, bass, avg) - 0.58) / 0.42))
            available_push = max(8.0, outer_max_radius - outer_base_radius)
            outer_points = []
            white_spark_points = []
            for si, fft_value in enumerate(fft_values):
                sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(si, sample_count)
                angle = -math.pi / 2.0 + (si / sample_count) * math.tau
                prev_v = fft_values[si - 1]
                next_v = fft_values[(si + 1) % sample_count]
                local_contrast = max(0.0, fft_value - (prev_v + next_v) * 0.5)
                spike_gate = max(0.0, min(1.0, (fft_value - 0.64) / 0.36))
                mirror_i = min(si, sample_count - 1 - si)
                seed = ((mirror_i * 37 + 13) % 97) / 97.0
                raw_value = raw_fft_values[si]
                raw_prev = raw_fft_values[si - 1]
                raw_next = raw_fft_values[(si + 1) % sample_count]
                raw_contrast = max(0.0, raw_value - (raw_prev + raw_next) * 0.5)
                transient_gate = max(0.0, min(1.0, (raw_value - temporal_smoothed[si]) / 0.16))
                level_gate = max(0.0, min(1.0, (raw_value - 0.055) / 0.34))
                peak_gate = max(0.0, min(1.0, volume_peak_gate)) * smoothed_gate
                audio_reactivity = max(transient_gate * 1.10, spike_gate * smoothed_gate, level_gate * 1.28, peak_gate * 0.22)
                audio_reactivity = max(0.0, min(1.0, audio_reactivity))
                audio_reactivity = audio_reactivity * audio_reactivity
                tip_speed = 0.32 + seed * 0.22 + audio_reactivity * 0.55
                snap_cycle = now * tip_speed + seed * 5.0 + mirror_i * 0.031
                snap_phase = snap_cycle - math.floor(snap_cycle)
                if snap_phase < 0.050:
                    snap_envelope = snap_phase / 0.050
                elif snap_phase < 0.210:
                    snap_envelope = 1.0 - (snap_phase - 0.050) / 0.160
                else:
                    snap_envelope = 0.0
                snap_envelope = max(0.0, min(1.0, snap_envelope)) * audio_reactivity
                snap_index = int(math.floor(snap_cycle))
                tip_sign = -1.0 if ((snap_index + mirror_i * 3) % 5) < 2 else 1.0
                tip_energy = max(raw_value, raw_contrast * 3.2, local_contrast * 2.4, spike_gate)
                tip_amount = tip_energy * available_push * (0.12 + 0.52 * audio_reactivity) * snap_envelope
                rr = max(outer_min_radius, min(outer_base_radius + tip_sign * tip_amount, outer_max_radius))
                point = QPointF(cx + cos_a * rr, cy + sin_a * rr)
                outer_points.append(point)

                # Spark follows the added white outer line and appears only on real jagged snaps.
                spark_strength = snap_envelope * audio_reactivity * max(0.0, min(0.36, tip_amount / max(1.0, available_push * 0.22)))
                if spark_strength > 0.30:
                    spark_radius = rr + 2.0
                    white_spark_points.append((
                        QPointF(cx + cos_a * spark_radius, cy + sin_a * spark_radius),
                        angle,
                        max(0.0, min(1.0, spark_strength)),
                        seed,
                    ))
            if outer_points:
                outer_path = QPainterPath(outer_points[0])
                for pt in outer_points[1:]:
                    outer_path.lineTo(pt)
                outer_path.closeSubpath()
                def _make_outer_offset_path(offset):
                    offset_path = QPainterPath()
                    first = outer_points[0]
                    first_len = max(1.0, math.hypot(first.x() - cx, first.y() - cy))
                    offset_path.moveTo(QPointF(first.x() + (first.x() - cx) / first_len * offset, first.y() + (first.y() - cy) / first_len * offset))
                    for pt in outer_points[1:]:
                        plen = max(1.0, math.hypot(pt.x() - cx, pt.y() - cy))
                        offset_path.lineTo(QPointF(pt.x() + (pt.x() - cx) / plen * offset, pt.y() + (pt.y() - cy) / plen * offset))
                    offset_path.closeSubpath()
                    return offset_path

                for offset, alpha_scale in ((-3.0, 0.22), (3.0, 0.16)):
                    offset_path = _make_outer_offset_path(offset)
                    trail_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), int(32 * alpha_scale)), max(1.0, 1.25 * width_scale))
                    trail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    trail_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(trail_pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(offset_path)
                glow_pen_1 = QPen(QColor(mint.red(), mint.green(), mint.blue(), 20), max(8.0, 8.0 * width_scale + bass * 4.0))
                glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_1)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(outer_path)
                glow_pen_2 = QPen(QColor(mint.red(), mint.green(), mint.blue(), 40), max(5.0, 5.0 * width_scale + bass * 2.0))
                glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_2)
                p.drawPath(outer_path)

                # Second white line, placed 2 px outside the flat-spectrum outer ripple.
                white_outer_path = _make_outer_offset_path(2.0)
                white_glow_pen_1 = QPen(QColor(255, 255, 255, 40), max(7.0, 8.5 * width_scale + smoothed_gate * 3.0))
                white_glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_1)
                p.drawPath(white_outer_path)
                white_glow_pen_2 = QPen(QColor(255, 255, 255, 72), max(3.6, 4.5 * width_scale + smoothed_gate * 1.6))
                white_glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_2)
                p.drawPath(white_outer_path)
                white_pen = QPen(QColor(255, 255, 255, 238), max(1.2, 2.0 * width_scale))
                white_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_pen)
                p.drawPath(white_outer_path)

                core_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), 255), max(1.4, 2.0 * width_scale))
                core_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                core_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(core_pen)
                p.drawPath(outer_path)

                if white_spark_points:
                    for spark_pt, spark_angle, spark_strength, spark_seed in white_spark_points:
                        spark_alpha = max(0, min(255, int(70 + spark_strength * 185)))
                        spark_size = short_side * (0.006 + spark_strength * 0.012)
                        self._draw_visualizer_soft_orb(p, spark_pt, spark_size * 2.8, QColor(255, 255, 255, spark_alpha), spark_alpha)
                        spark_sin, spark_cos = self._flat_spectrum_sin_cos_from_angle(spark_angle)
                        radial = QPointF(spark_cos, spark_sin)
                        tangent = QPointF(-spark_sin, spark_cos)
                        ray_len = spark_size * (1.45 + spark_strength * 1.35)
                        ray_alpha = max(0, min(255, int(105 + spark_strength * 125)))
                        ray_pen = QPen(QColor(255, 255, 255, ray_alpha), max(0.7, 1.15 * width_scale))
                        ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(ray_pen)
                        p.drawLine(
                            QPointF(spark_pt.x() - radial.x() * ray_len, spark_pt.y() - radial.y() * ray_len),
                            QPointF(spark_pt.x() + radial.x() * ray_len, spark_pt.y() + radial.y() * ray_len),
                        )
                        p.drawLine(
                            QPointF(spark_pt.x() - tangent.x() * ray_len * 0.62, spark_pt.y() - tangent.y() * ray_len * 0.62),
                            QPointF(spark_pt.x() + tangent.x() * ray_len * 0.62, spark_pt.y() + tangent.y() * ray_len * 0.62),
                        )

            flat_spectrum_rotation_degrees = self._flat_spectrum_inner_rotation_degrees(now)
            flat_spectrum_rotation_degrees2 = self._flat_spectrum_inner_rotation_degrees2(now)
            p.save()
            try:
                p.translate(cx, cy)
                p.rotate(flat_spectrum_rotation_degrees)
                p.translate(-cx, -cy)
                static_hologram_image, static_hologram_radius = self._flat_spectrum_static_hologram_image(max_effect_radius, base_color, width_scale)
                if static_hologram_image is not None and static_hologram_radius > 0:
                    p.drawImage(
                        QRectF(
                            cx - static_hologram_radius,
                            cy - static_hologram_radius,
                            static_hologram_radius * 2,
                            static_hologram_radius * 2,
                        ),
                        static_hologram_image,
                    )
                hologram_outer_circle_radius = max_effect_radius * 0.53
                hologram_max_bar_overhang_px = 10.0
                hologram_inner_bar_alpha = 235
                hologram_outer_bar_alpha = int(255 * 0.40)
                for hi in range(0, count, max(1, count // 72)):
                    v = values[hi]
                    sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(hi, count)
                    base_inner = max_effect_radius * 0.44
                    max_outer = hologram_outer_circle_radius + hologram_max_bar_overhang_px
                    max_len = min(30.0, max(0.0, max_outer - base_inner))
                    min_bar_len = min(max_len, max(2.0, short_side * 0.025))
                    max_bar_len = max(min_bar_len, max_len)
                    threshold = max(0.12, avg * 1.20)
                    band_signal = max(float(v), bass * 0.72)
                    peak_amount = max(0.0, min(1.0, (band_signal - threshold) / max(0.001, 1.0 - threshold)))
                    peak_amount = peak_amount * peak_amount * (3.0 - 2.0 * peak_amount)
                    wave = 0.92 + 0.08 * math.sin(now * (2.8 + peak_amount * 3.0) + hi * 0.31)
                    motion = max(0.0, min(1.0, peak_amount * wave))
                    bar_len = min(max_len, min_bar_len + (max_bar_len - min_bar_len) * motion)
                    inner = base_inner
                    outer = min(max_outer, inner + bar_len)
                    if outer <= inner:
                        continue
                    steps = max(1, int(math.ceil(outer - inner)))
                    pen_width = max(1.4, min(5.0, 2.6 * width_scale))
                    for hs in range(steps):
                        r1 = inner + hs
                        r2 = min(outer, inner + hs + 1.0)
                        if r2 <= r1:
                            continue
                        t = hs / max(1, steps - 1)
                        alpha = int(hologram_inner_bar_alpha * (1.0 - t) + hologram_outer_bar_alpha * t)
                        c = QColor(base_color)
                        c.setAlpha(alpha)
                        p.setPen(QPen(c, pen_width))
                        p.drawLine(QPointF(cx + cos_a * r1, cy + sin_a * r1), QPointF(cx + cos_a * r2, cy + sin_a * r2))
            finally:
                p.restore()

            center_radius = max(5.0, max_effect_radius * 0.23)
            center_grad = QRadialGradient(QPointF(cx, cy), center_radius)
            center_grad.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 78))
            center_grad.setColorAt(0.62, QColor(base_color.red(), base_color.green(), base_color.blue(), 44))
            center_grad.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 18))
            p.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 92), max(1.0, 1.0 * width_scale)))
            p.setBrush(QBrush(center_grad))
            p.drawEllipse(QPointF(cx, cy), center_radius, center_radius)
            p.restore()
            p.restore(); return

        if style == "dynamic_glitch":
            pts=[]
            for i,v in enumerate(values): x=area.left()+((aw*i/max(1,count-1)-(now*34%max(1,aw)))%aw); y=cy+((-1)**i)*ah*(0.025+v*0.20); pts.append(QPointF(x,y))
            for i in range(1,len(pts)): col=self._rainbow_color(i/max(1,len(pts))+now*0.02,90,0.55,0.8); p.setPen(QPen(col,max(1.0,2.2*width_scale))); p.drawLine(pts[i-1],pts[i])
            p.restore(); return

        if style == "cyber":
            base_y=area.top()+ah*0.28; slot=aw/count
            for i,v in enumerate(values):
                x=area.left()+i*slot; col=self._rainbow_color(i/count*0.85+now*0.035,150+int(v*80),0.85,1.0); p.setPen(QPen(col,max(1.0,1.6*width_scale)))
                if i>0: p.drawLine(QPointF(x-slot,base_y+math.sin((i-1)*0.08+now)*ah*0.025),QPointF(x,base_y+math.sin(i*0.08+now)*ah*0.025))
                h=ah*(0.04+v*0.55); p.setPen(QPen(col,max(1.0,1.3*width_scale))); p.drawLine(QPointF(x,base_y),QPointF(x,base_y+h))
                if i%max(1,count//36)==0: age=(now*0.65+i*0.021)%1.0; pc=QColor(col); pc.setAlpha(int((1-age)*120)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(pc)); p.drawEllipse(QPointF(x,base_y+h+age*ah*0.16),1.5+v*2,1.5+v*2)
            p.restore(); return

        # Spec-refined remaining skins. These branches follow the new reference-feature notes.
        if style == "aurora":
            # Seven-color curtain ribbons fluttering with audio.
            colors = [QColor(255,80,150,70), QColor(255,160,70,64), QColor(255,240,90,60), QColor(80,255,150,68), QColor(70,220,255,70), QColor(120,110,255,72), QColor(210,90,255,65)]
            for layer, col in enumerate(colors):
                pts_top=[]; pts_bottom=[]
                phase=now*(0.35+layer*0.035)+layer*0.7
                for i in range(count):
                    v=values[i]
                    x=area.left()+aw*i/max(1,count-1)
                    y=area.top()+ah*(0.18+layer*0.085)+math.sin(i*0.09+phase)*ah*(0.035+avg*0.045)+(v-avg)*ah*0.10
                    pts_top.append(QPointF(x,y))
                    pts_bottom.append(QPointF(x,y+ah*(0.045+v*0.10)))
                if pts_top:
                    path=QPainterPath(pts_top[0])
                    for pt in pts_top[1:]: path.lineTo(pt)
                    for pt in reversed(pts_bottom): path.lineTo(pt)
                    path.closeSubpath()
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawPath(path)
            p.restore(); return

        if style == "hologram":
            # Semi-transparent dual-color circle, radial fuzzy bars and center vertical bars.
            inv=QColor(255-base_color.red(),255-base_color.green(),255-base_color.blue(),105)
            acc=QColor(base_color); acc.setAlpha(105)
            rg=QRadialGradient(QPointF(cx,cy),max_effect_radius*0.62)
            rg.setColorAt(0.0,QColor(0,0,0,76)); rg.setColorAt(0.45,QColor(base_color.red(),base_color.green(),base_color.blue(),45)); rg.setColorAt(1.0,QColor(base_color.red(),base_color.green(),base_color.blue(),0))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(rg)); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.55,max_effect_radius*0.55)
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(acc,max(1.0,1.4*width_scale))); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.45,max_effect_radius*0.45)
            p.setPen(QPen(inv,max(1.0,1.0*width_scale))); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.58,max_effect_radius*0.58)
            step=max(1,count//72)
            hologram_outer_circle_radius=max_effect_radius*0.58
            hologram_max_bar_overhang_px=10.0
            hologram_inner_bar_alpha=235
            hologram_outer_bar_alpha=int(255*0.40)
            for i in range(0,count,step):
                v=values[i]
                a=i/count*math.tau-math.pi/2.0
                base_inner=max_effect_radius*0.48
                max_outer=hologram_outer_circle_radius+hologram_max_bar_overhang_px
                max_len=max(0.0,max_outer-base_inner)
                min_bar_len=min(max_len,max(2.0,short_side*0.025))
                max_bar_len=max(min_bar_len,max_len)
                threshold=max(0.12,avg*1.20)
                band_signal=max(float(v),bass*0.72)
                peak_amount=max(0.0,min(1.0,(band_signal-threshold)/max(0.001,1.0-threshold)))
                peak_amount=peak_amount*peak_amount*(3.0-2.0*peak_amount)
                wave=0.92+0.08*math.sin(now*(2.8+peak_amount*3.0)+i*0.31)
                motion=max(0.0,min(1.0,peak_amount*wave))
                bar_len=min(max_len,min_bar_len+(max_bar_len-min_bar_len)*motion)
                inner=base_inner
                outer=min(max_outer,inner+bar_len)
                if outer <= inner:
                    continue
                steps=max(1,int(math.ceil(outer-inner)))
                pen_width=max(2.0,min(3.0,2.6*width_scale))
                for s in range(steps):
                    r1=inner+s
                    r2=min(outer,inner+s+1.0)
                    if r2 <= r1:
                        continue
                    t=s/max(1,steps-1)
                    alpha=int(hologram_inner_bar_alpha*(1.0-t)+hologram_outer_bar_alpha*t)
                    col=QColor(base_color)
                    col.setAlpha(alpha)
                    p.setPen(QPen(col,pen_width))
                    p.drawLine(QPointF(cx+math.cos(a)*r1,cy+math.sin(a)*r1),QPointF(cx+math.cos(a)*r2,cy+math.sin(a)*r2))
            hologram_inner_circle_radius=max_effect_radius*0.45
            center_bar_limit=max(1.0,hologram_inner_circle_radius-5.0)
            center_span_width=center_bar_limit*2.0
            bars=max(3,int(count*center_span_width/max(1.0,aw)))
            center_slot=center_span_width/bars
            center_bar_w=max(1.0,center_slot*0.28*width_scale)
            for j in range(bars):
                src_i=min(count-1,int(j*count/max(1,bars)))
                v=values[src_i]
                x=cx-center_bar_limit+j*center_slot+(center_slot-center_bar_w)*0.5
                bar_center_x=x+center_bar_w*0.5
                bar_edge_dx=abs(bar_center_x-cx)+center_bar_w*0.5
                max_inner_circle_h=2.0*math.sqrt(max(0.0,center_bar_limit*center_bar_limit-bar_edge_dx*bar_edge_dx))
                h=min(max_inner_circle_h,ah*(0.018+v*0.24))
                col=QColor(255,255,255,75+int(v*70))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(col))
                p.drawRoundedRect(QRectF(x,cy-h*0.5,center_bar_w,h),2,2)
            p.restore(); return

        if style == "audio_ripple":
            # Audio Ripple: Circular Waveform Spectrum.
            # Base circle stays readable; spike tips move inward/outward with moderated speed.
            # Use the widget accent color instead of a fixed mint color.
            # Alpha variants below keep the existing glow / afterimage balance.
            mint = QColor(base_color)
            mint.setAlpha(235)
            mint_glow_1 = QColor(base_color)
            mint_glow_1.setAlpha(20)
            mint_glow_2 = QColor(base_color)
            mint_glow_2.setAlpha(40)
            mint_after = QColor(base_color)
            mint_after.setAlpha(32)

            background_radius = max_effect_radius * 0.52
            bg = QRadialGradient(QPointF(cx, cy), background_radius * 1.18)
            bg.setColorAt(0.00, QColor(0, 0, 0, 224))
            bg.setColorAt(0.62, QColor(0, 15, 18, 172))
            bg.setColorAt(1.00, QColor(0, 54, 50, 58))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(bg))
            p.drawEllipse(QPointF(cx, cy), background_radius, background_radius)

            # Soft plexus background.
            plex_nodes = []
            plex_count = 32
            for n in range(plex_count):
                hx = ((n * 37) % 101) / 100.0
                hy = ((n * 61 + 17) % 101) / 100.0
                x = area.left() + aw * hx + math.sin(now * 0.10 + n * 1.47) * short_side * 0.010
                y = area.top() + ah * hy + math.cos(now * 0.09 + n * 1.13) * short_side * 0.010
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) < (background_radius * 0.92) ** 2:
                    push = background_radius * 1.20 / max(1.0, math.hypot(x - cx, y - cy))
                    x = cx + (x - cx) * push
                    y = cy + (y - cy) * push
                plex_nodes.append(QPointF(x, y))

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(mint.red(), mint.green(), mint.blue(), 20 + int(avg * 22)), max(0.45, 0.60 * width_scale)))
            link_limit2 = (short_side * 0.27) ** 2
            for i, a_pt in enumerate(plex_nodes):
                for j in range(i + 1, min(plex_count, i + 6)):
                    b_pt = plex_nodes[j]
                    dx = a_pt.x() - b_pt.x()
                    dy = a_pt.y() - b_pt.y()
                    if dx * dx + dy * dy < link_limit2:
                        p.drawLine(a_pt, b_pt)

            for n, pt in enumerate(plex_nodes):
                pulse = 0.50 + 0.50 * math.sin(now * 1.10 + n * 0.73)
                dot_col = QColor(mint.red(), mint.green(), mint.blue(), int(24 + pulse * 40 + avg * 22))
                self._draw_visualizer_soft_orb(p, pt, short_side * (0.0032 + pulse * 0.0025), dot_col, dot_col.alpha())

            # Layer order for Audio Ripple:
            #   bottom: translucent circular accent field
            #   middle: current media cover image, fitted 10px inside that circle
            #   top: jagged audio ripple line drawn below
            cover_inset = 10.0
            cover_rect = QRectF(
                cx - background_radius + cover_inset,
                cy - background_radius + cover_inset,
                max(1.0, background_radius * 2.0 - cover_inset * 2.0),
                max(1.0, background_radius * 2.0 - cover_inset * 2.0),
            )
            has_cover_image = self._draw_visualizer_media_thumbnail_cover(
                p,
                cover_rect,
                ctx,
                clip_radius=background_radius - cover_inset,
                fallback_accent=mint,
            )

            circle_gap = max(3.0, short_side * 0.016)
            base_radius = background_radius + circle_gap
            max_wave_radius = max_effect_radius * 0.88
            inner_wave_radius = max(4.0, background_radius * 0.22)
            available_push = max(8.0, max_wave_radius - base_radius)
            deformation_scale = 0.48
            sensitivity = min(150.0, max(50.0, available_push * 0.60))
            sample_count = max(100, min(256, count if count > 0 else 128))

            # Vocal / main-source focused mode: use the middle band instead of global peaks.
            # This keeps bass hits and isolated high-frequency peaks from driving the ripple too much,
            # while still reacting when the vocal or main melody band actually rises.
            half_count = max(2, sample_count // 2)
            source_count = max(1, len(values))
            mid_start = min(source_count - 1, max(0, int(source_count * 0.18)))
            mid_end = min(source_count - 1, max(mid_start + 1, int(source_count * 0.64)))
            mid_span = max(1, mid_end - mid_start)
            vocal_half = []
            for i in range(half_count):
                pos = i / max(1, half_count - 1)
                src_i = mid_start + int(pos * mid_span)
                src_i = max(0, min(source_count - 1, src_i))

                # Weight the center of the vocal/main range.  The edges still contribute a little,
                # but they cannot keep the line moving by themselves.
                center_weight = 1.0 - min(1.0, abs(pos - 0.45) / 0.45)
                band_weight = 0.36 + center_weight * 0.64

                # Reduce broadband low-end influence.  This is deliberately conservative because
                # the goal is not a perfect vocal separator; it is a visually stable main-source follower.
                value = max(0.0, float(values[src_i]) - bass * 0.18)
                vocal_half.append(max(0.0, min(1.0, value * band_weight * 1.58)))

            focused_values = vocal_half + list(reversed(vocal_half))
            sample_count = len(focused_values)

            focused_peak = max(focused_values) if focused_values else 0.0
            focused_avg = sum(focused_values) / max(1, len(focused_values))
            focused_energy = focused_peak * 0.68 + focused_avg * 0.32
            previous_energy = float(getattr(self, "_audio_ripple_focused_energy", focused_energy))

            # Gate and hysteresis: below the threshold the ripple returns to the base circle.
            # Attack is faster than release, so vocals/main sounds feel responsive without idle jitter.
            energy_gate = max(0.0, min(1.0, (focused_energy - 0.08) / 0.57))
            onset_gate = max(0.0, min(1.0, (focused_energy - previous_energy) / 0.18))
            target_gate = max(energy_gate, onset_gate * 0.80)
            if target_gate < 0.055:
                target_gate = 0.0
            smoothed_gate = float(getattr(self, "_audio_ripple_focused_gate", 0.0))
            if target_gate >= smoothed_gate:
                smoothed_gate = smoothed_gate * 0.54 + target_gate * 0.46
            else:
                smoothed_gate = smoothed_gate * 0.88 + target_gate * 0.12
            if smoothed_gate < 0.035:
                smoothed_gate = 0.0
            self._audio_ripple_focused_energy = focused_energy
            self._audio_ripple_focused_gate = smoothed_gate

            raw_fft_values = [v * smoothed_gate for v in focused_values]

            # Base waveform remains smoothed so the circular silhouette does not collapse.
            previous_smoothed = getattr(self, "_audio_ripple_smoothed", None)
            if not isinstance(previous_smoothed, list) or len(previous_smoothed) != sample_count:
                previous_smoothed = list(raw_fft_values)
            temporal_smoothed = []
            for i, current_value in enumerate(raw_fft_values):
                if current_value >= previous_smoothed[i]:
                    temporal_smoothed.append(previous_smoothed[i] * 0.70 + current_value * 0.30)
                else:
                    temporal_smoothed.append(previous_smoothed[i] * 0.90 + current_value * 0.10)
            self._audio_ripple_smoothed = temporal_smoothed

            fft_values = []
            for i, current_value in enumerate(temporal_smoothed):
                prev2_v = temporal_smoothed[i - 2]
                prev_v = temporal_smoothed[i - 1]
                next_v = temporal_smoothed[(i + 1) % sample_count]
                next2_v = temporal_smoothed[(i + 2) % sample_count]
                fft_values.append(prev2_v * 0.10 + prev_v * 0.20 + current_value * 0.40 + next_v * 0.20 + next2_v * 0.10)

            local_peak = max(raw_fft_values) if raw_fft_values else 0.0
            smoothed_peak = max(fft_values) if fft_values else 0.0
            volume_peak_gate = max(0.0, min(1.0, (max(local_peak, smoothed_peak, bass, avg) - 0.58) / 0.42))

            points = []
            white_spark_points = []
            for i, fft_value in enumerate(fft_values):
                # Use the current loop index for the cached trig lookup.
                # A previous flat_spectrum optimization used ``si`` in similar loops;
                # audio_ripple uses ``i`` here, so referencing ``si`` can raise
                # UnboundLocalError during paintEvent.
                sin_a, cos_a = self._flat_spectrum_sin_cos_for_step(i, sample_count)
                angle = -math.pi / 2.0 + (i / sample_count) * math.tau
                prev_v = fft_values[i - 1]
                next_v = fft_values[(i + 1) % sample_count]
                local_contrast = max(0.0, fft_value - (prev_v + next_v) * 0.5)
                spike_gate = max(0.0, min(1.0, (fft_value - 0.64) / 0.36))

                # Keep the main waveform glued to the background circle.
                # FFT deformation is used as a trigger/strength signal for snap tips,
                # not as a continuous outward lift of the whole line.
                base_amplitude = 0.0

                mirror_i = min(i, sample_count - 1 - i)
                seed = ((mirror_i * 37 + 13) % 97) / 97.0

                raw_value = raw_fft_values[i]
                raw_prev = raw_fft_values[i - 1]
                raw_next = raw_fft_values[(i + 1) % sample_count]
                raw_contrast = max(0.0, raw_value - (raw_prev + raw_next) * 0.5)

                # Audio-reactive gates.
                # transient_gate responds to sudden rises; level_gate keeps sustained vocals/main sounds alive.
                # The global peak gate is intentionally weak so peak-only events do not dominate the ripple.
                transient_gate = max(0.0, min(1.0, (raw_value - temporal_smoothed[i]) / 0.16))
                level_gate = max(0.0, min(1.0, (raw_value - 0.055) / 0.34))
                peak_gate = max(0.0, min(1.0, volume_peak_gate)) * smoothed_gate
                audio_reactivity = max(transient_gate * 1.10, spike_gate * smoothed_gate, level_gate * 1.28, peak_gate * 0.22)
                audio_reactivity = max(0.0, min(1.0, audio_reactivity))
                # Squaring suppresses idle/fallback noise, so tips do not move constantly.
                audio_reactivity = audio_reactivity * audio_reactivity

                # Snap tip motion: バチッ、スッ.  The clock still provides the sharp impulse shape,
                # but its visibility and strength are now gated by the actual audio energy above.
                tip_speed = 0.32 + seed * 0.22 + audio_reactivity * 0.55
                snap_cycle = now * tip_speed + seed * 5.0 + mirror_i * 0.031
                snap_phase = snap_cycle - math.floor(snap_cycle)

                if snap_phase < 0.050:
                    snap_envelope = snap_phase / 0.050
                elif snap_phase < 0.210:
                    snap_envelope = 1.0 - (snap_phase - 0.050) / 0.160
                else:
                    snap_envelope = 0.0
                snap_envelope = max(0.0, min(1.0, snap_envelope))
                snap_envelope *= audio_reactivity

                # Direction changes per impulse, not continuously inside the impulse.
                snap_index = int(math.floor(snap_cycle))
                tip_sign = -1.0 if ((snap_index + mirror_i * 3) % 5) < 2 else 1.0

                tip_energy = max(raw_value, raw_contrast * 3.2, spike_gate)
                tip_amount = tip_energy * available_push * (0.12 + 0.52 * audio_reactivity) * snap_envelope

                # Baseline stays exactly on base_radius; only audio-triggered tip impulses move.
                radius = base_radius + tip_sign * tip_amount
                radius = max(inner_wave_radius, min(radius, max_wave_radius))
                point = QPointF(cx + cos_a * radius, cy + sin_a * radius)
                points.append(point)

                # Spark only when the jagged tip is actually snapping.
                # This follows the white outer line, so the spark appears on the second line's tip.
                spark_strength = snap_envelope * audio_reactivity * max(0.0, min(0.36, tip_amount / max(1.0, available_push * 0.22)))
                if spark_strength > 0.30:
                    spark_radius = radius + 1.0
                    white_spark_points.append((
                        QPointF(cx + cos_a * spark_radius, cy + sin_a * spark_radius),
                        angle,
                        max(0.0, min(1.0, spark_strength)),
                        seed,
                    ))

            def _make_offset_path(offset):
                path = QPainterPath()
                if not points:
                    return path
                first = points[0]
                first_len = max(1.0, math.hypot(first.x() - cx, first.y() - cy))
                path.moveTo(QPointF(first.x() + (first.x() - cx) / first_len * offset,
                                    first.y() + (first.y() - cy) / first_len * offset))
                for pt in points[1:]:
                    length = max(1.0, math.hypot(pt.x() - cx, pt.y() - cy))
                    path.lineTo(QPointF(pt.x() + (pt.x() - cx) / length * offset,
                                        pt.y() + (pt.y() - cy) / length * offset))
                path.closeSubpath()
                return path

            p.setBrush(Qt.BrushStyle.NoBrush)
            for offset, alpha_scale in ((0.0, 1.00), (short_side * 0.010, 0.58), (short_side * 0.020, 0.36), (short_side * 0.030, 0.22)):
                path_offset = _make_offset_path(offset)
                if offset > 0.0:
                    trail_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), int(mint_after.alpha() * alpha_scale)), max(1.0, 1.25 * width_scale))
                    trail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    trail_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(trail_pen)
                    p.drawPath(path_offset)
                    continue

                glow_pen_1 = QPen(QColor(mint.red(), mint.green(), mint.blue(), mint_glow_1.alpha()), max(8.0, 8.0 * width_scale + bass * 4.0))
                glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_1)
                p.drawPath(path_offset)

                glow_pen_2 = QPen(QColor(mint.red(), mint.green(), mint.blue(), mint_glow_2.alpha()), max(5.0, 5.0 * width_scale + bass * 2.0))
                glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(glow_pen_2)
                p.drawPath(path_offset)

                # Two-line ripple: accent line + a white line placed 2 px outside.
                # The white line has its own soft glow so it stays subtly luminous even while idle.
                white_outer_path = _make_offset_path(2.0)
                white_glow_pen_1 = QPen(QColor(255, 255, 255, 40), max(7.0, 8.5 * width_scale + smoothed_gate * 3.0))
                white_glow_pen_1.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_1.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_1)
                p.drawPath(white_outer_path)

                white_glow_pen_2 = QPen(QColor(255, 255, 255, 72), max(3.6, 4.5 * width_scale + smoothed_gate * 1.6))
                white_glow_pen_2.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_glow_pen_2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_glow_pen_2)
                p.drawPath(white_outer_path)

                white_pen = QPen(QColor(255, 255, 255, 238), max(1.2, 2.0 * width_scale))
                white_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                white_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(white_pen)
                p.drawPath(white_outer_path)

                core_pen = QPen(QColor(mint.red(), mint.green(), mint.blue(), 255), max(1.4, 2.0 * width_scale))
                core_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                core_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(core_pen)
                p.drawPath(path_offset)

            # Spark flashes on the white line tips when the waveform becomes jagged.
            # Draw after the lines so the flash sits visually on top of the second line.
            if white_spark_points:
                for spark_pt, spark_angle, spark_strength, spark_seed in white_spark_points:
                    spark_alpha = max(0, min(255, int(70 + spark_strength * 185)))
                    spark_size = short_side * (0.006 + spark_strength * 0.012)
                    self._draw_visualizer_soft_orb(p, spark_pt, spark_size * 2.8, QColor(255, 255, 255, spark_alpha), spark_alpha)

                    # Small star glint.  Tangential and radial strokes make it read as a spark,
                    # but the alpha/length are gated so it does not become noisy while idle.
                    radial = QPointF(math.cos(spark_angle), math.sin(spark_angle))
                    tangent = QPointF(-math.sin(spark_angle), math.cos(spark_angle))
                    ray_len = spark_size * (1.45 + spark_strength * 1.35)
                    ray_alpha = max(0, min(255, int(105 + spark_strength * 125)))
                    ray_pen = QPen(QColor(255, 255, 255, ray_alpha), max(0.7, 1.15 * width_scale))
                    ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(ray_pen)
                    p.drawLine(
                        QPointF(spark_pt.x() - radial.x() * ray_len, spark_pt.y() - radial.y() * ray_len),
                        QPointF(spark_pt.x() + radial.x() * ray_len, spark_pt.y() + radial.y() * ray_len),
                    )
                    p.drawLine(
                        QPointF(spark_pt.x() - tangent.x() * ray_len * 0.62, spark_pt.y() - tangent.y() * ray_len * 0.62),
                        QPointF(spark_pt.x() + tangent.x() * ray_len * 0.62, spark_pt.y() + tangent.y() * ray_len * 0.62),
                    )

            label = str(getattr(self.cfg, "text", "") or "").strip()
            if label and not has_cover_image:
                lines = [line.strip() for line in label.splitlines() if line.strip()]
                p.setPen(QColor(mint.red(), mint.green(), mint.blue(), 215))
                base_fs = max(8, int(background_radius * 0.20))
                p.setFont(QFont("Segoe UI", base_fs, QFont.Weight.DemiBold))
                line_h = base_fs * 1.22
                total_h = line_h * len(lines[:3])
                start_y = cy - total_h * 0.5 + base_fs
                for li, line in enumerate(lines[:3]):
                    p.drawText(QRectF(cx - background_radius * 0.82, start_y + li * line_h - base_fs, background_radius * 1.64, line_h),
                               Qt.AlignmentFlag.AlignCenter, line)

            p.restore(); return

        if style == "nebula":
            # One frayed translucent accent thread, white orb center, falling white particles.
            pts=[]; smooth=avg
            for i,raw in enumerate(values):
                smooth=smooth*0.82+raw*0.18
                x=area.left()+aw*i/max(1,count-1)
                y=cy+math.sin(i*0.075+now*0.85)*ah*0.15-(smooth-avg)*ah*0.32
                pts.append(QPointF(x,y))
            col=QColor(base_color); col.setAlpha(105)
            self._draw_visualizer_polyline(p,pts,col,3.0*width_scale,105)
            if glow_enabled: self._draw_visualizer_polyline(p,pts,col,8.0*width_scale,36)
            orb_i=int((now*18)%max(1,len(pts))) if pts else 0
            if pts: self._draw_visualizer_soft_orb(p,pts[orb_i],6+avg*14,QColor(255,255,255,165),95+int(avg*60))
            for k in range(34):
                x=area.left()+((k*53+int(now*8))%int(max(1,aw))); y=area.top()+((k*31+int(now*18))%int(max(1,ah)))
                a=55+(k%5)*18; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255,255,255,a))); p.drawEllipse(QPointF(x,y),1.2+(k%3)*0.45,1.2+(k%3)*0.45)
            p.restore(); return

        if style == "matrix":
            # Slow waterfall of light-green characters; columns bend into a subtle center circle.
            bg=QLinearGradient(QPointF(area.left(),area.top()),QPointF(area.left(),area.bottom())); bg.setColorAt(0,QColor(0,35,14,70)); bg.setColorAt(1,QColor(0,8,5,110))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bg)); p.drawRect(area)
            font_size=max(8,min(14,int(ah/14))); p.setFont(QFont("Consolas",font_size)); cols=max(10,min(44,int(aw/max(8,font_size*0.75))))
            for c in range(cols):
                x=area.left()+c*aw/max(1,cols-1)
                drop=(now*7+c*19)%max(1,ah+font_size*7)-font_size*5
                swirl=math.sin(c*0.42+now*0.35)*avg*short_side*0.08
                for r in range(9):
                    y=area.top()+drop+r*font_size*1.25
                    if abs(y-cy)<short_side*0.22: x2=x+swirl*math.cos((y-cy)/max(1,short_side)*math.pi)
                    else: x2=x
                    p.setPen(QColor(120,255,150,max(28,145-r*13)))
                    ch="01"[(c+r+int(now*0.7))%2]
                    p.drawText(QPointF(x2,y),ch)
            p.restore(); return

        if style == "audio_tunnel":
            # Rainbow circular tunnel: tangled inner threads, downward inner bars, upward outer bars.
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k in range(8):
                pts=[]; rr=max_effect_radius*(0.16+k*0.035)
                for s in range(80):
                    a=s/80*math.tau+now*(0.25+k*0.02); wig=math.sin(s*0.31+now*2.0+k)*short_side*0.018*(1+avg)
                    pts.append(QPointF(cx+math.cos(a)*(rr+wig),cy+math.sin(a)*(rr+wig)))
                self._draw_visualizer_polyline(p,pts,self._rainbow_color(k*0.12+now*0.04,120),1.0*width_scale,100)
            step=max(1,count//72)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2.0+now*0.22
                for band,sign in [(0.46,-1),(0.64,1)]:
                    inner=max_effect_radius*band; outer=inner+sign*short_side*(0.035+v*0.18)
                    col=self._rainbow_color(i/count+now*0.08,175)
                    p.setPen(QPen(col,max(1.0,(1.2+v*3.4)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer))
            p.restore(); return

        if style == "audio_tunnel_sphere":
            # Accent sphere: dotted lattice rotates upward, edge is thicker, pulse is calm.
            pulse=1.0+avg*0.045+bass*0.025; r=max_effect_radius*0.48*pulse
            edge=QColor(base_color); edge.setAlpha(145); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(edge,max(2.0,3.2*width_scale))); p.drawEllipse(QPointF(cx,cy),r,r)
            for lat in range(-4,5):
                rr=r*math.cos(lat/5*math.pi/2); y=cy+math.sin(lat/5*math.pi/2)*r*0.72+math.sin(now*0.35+lat)*3
                p.setPen(QPen(QColor(base_color.red(),base_color.green(),base_color.blue(),55),1)); p.drawEllipse(QPointF(cx,y),abs(rr),abs(rr)*0.22)
            p.setPen(Qt.PenStyle.NoPen)
            for k in range(84):
                a=k/84*math.tau+now*0.28; rr=r*(0.18+(k%13)/13*0.76); y=cy+math.sin(a+now*0.2)*rr*0.62; x=cx+math.cos(a)*rr
                c=QColor(base_color); c.setAlpha(64); p.setBrush(QBrush(c)); p.drawEllipse(QPointF(x,y),1.35,1.35)
            p.restore(); return

        if style == "neon_tunnel_wire":
            # Stylish depth wire tunnel: transient bright shapes, thick tips taper outward.
            shapes=[3,4,6,5]
            for depth in range(7):
                t=depth/6; scale=1.0-t*0.74; sides=shapes[depth%len(shapes)]; phase=now*(0.42+t*0.15)+depth*0.7
                pts=[]
                for k in range(sides+1):
                    a=k/sides*math.tau+phase; wob=math.sin(now*2.0+k+depth)*0.05
                    pts.append(QPointF(cx+math.cos(a+wob)*aw*0.38*scale,cy+math.sin(a+wob)*ah*0.32*scale))
                col=QColor(base_color); col.setAlpha(int(55+105*(1-t)+bass*50))
                self._draw_visualizer_polyline(p,pts,col,max(1.0,(3.2-2.0*t)*width_scale),col.alpha())
                if bass>0.35 and depth%2==0: self._draw_visualizer_polyline(p,pts,QColor(255,255,255,160),max(1.0,(4.0-2.3*t)*width_scale),120)
            p.restore(); return

        if style == "neon_soundwave":
            # Cover image fills the full inside of the neon music-bar circle; bars stay on top.
            for k in range(3):
                rr=max_effect_radius*(0.26+k*0.15); col=QColor(base_color); col.setAlpha(68); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(col,max(1.0,(2.0-k*0.25)*width_scale))); p.drawEllipse(QPointF(cx,cy),rr,rr)
            neon_cover_radius=max(1.0,max_effect_radius*0.53)
            neon_cover_rect=QRectF(cx-neon_cover_radius,cy-neon_cover_radius,neon_cover_radius*2.0,neon_cover_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,neon_cover_rect,ctx,clip_radius=neon_cover_radius,fallback_accent=base_color)
            step=max(1,count//72)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2.0+now*0.38; inner=max_effect_radius*0.53; outer=min(max_effect_radius*0.95,inner+short_side*(0.035+v*0.17)); col=QColor(base_color); col.setAlpha(100+int(v*70)); p.setPen(QPen(col,max(1.0,(1.2+v*3.2)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer))
                if i%max(1,count//24)==0: p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(base_color.red(),base_color.green(),base_color.blue(),70))); p.drawEllipse(QPointF(cx+math.cos(a)*(outer+math.sin(now*3+i)*4),cy+math.sin(a)*(outer+math.cos(now*2+i)*4)),2,2)
            p.restore(); return

        if style == "glow_beat_music":
            # Media cover inside the music-bar circle, with translucent moving particles and bars above it.
            glow_cover_radius=max(1.0,max_effect_radius*0.46)
            glow_cover_rect=QRectF(cx-glow_cover_radius,cy-glow_cover_radius,glow_cover_radius*2.0,glow_cover_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,glow_cover_rect,ctx,clip_radius=glow_cover_radius,fallback_accent=base_color)
            p.setPen(Qt.PenStyle.NoPen)
            for k in range(60):
                ph=(k*0.618+now*0.9)%1.0; a=k*2.399+now*0.3; rr=max_effect_radius*0.08+ph*max_effect_radius*0.55; alpha=int((1-ph)*140)
                p.setBrush(QBrush(QColor(255,255,255,max(0,alpha)))); p.drawEllipse(QPointF(cx+math.cos(a)*rr,cy+math.sin(a)*rr),1.1+ph*1.4,1.1+ph*1.4)
            step=max(1,count//84)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2.0; inner=max_effect_radius*0.46; outer=min(max_effect_radius*0.98,inner+short_side*(0.04+v*0.23)); col=QColor(255,255,255,82+int(v*120)); p.setPen(QPen(col,max(1.0,(1.4+v*4.0)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer)); p.setBrush(QBrush(QColor(255,255,255,70+int(v*80)))); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(cx+math.cos(a)*(inner-5),cy+math.sin(a)*(inner-5)),1.6,1.6)
            p.restore(); return

        if style == "enigmatic_echo_sound":
            # 8px translucent white bars, left and right react strongly.
            slot=aw/count; bar_w=max(2.0,8.0*width_scale); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255,255,255,205)))
            for i,v in enumerate(values):
                side_boost=1.35 if i<count*0.22 or i>count*0.78 else 0.82
                h=ah*(0.05+v*0.74*side_boost); x=area.left()+i*slot+slot*0.5-bar_w*0.5; p.drawRoundedRect(QRectF(x,cy-h*0.5,bar_w,h),3,3)
            p.restore(); return

        if style == "reactive_lights":
            # 17 radial bars around a media cover on the translucent white center, with slow outer rings spaced about 5px.
            reactive_center_radius=max_effect_radius*0.25
            center_rg=QRadialGradient(QPointF(cx,cy),max_effect_radius*0.28); center_rg.setColorAt(0,QColor(255,255,255,120)); center_rg.setColorAt(1,QColor(255,255,255,20)); p.setBrush(QBrush(center_rg)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(cx,cy),reactive_center_radius,reactive_center_radius)
            reactive_cover_rect=QRectF(cx-reactive_center_radius,cy-reactive_center_radius,reactive_center_radius*2.0,reactive_center_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,reactive_cover_rect,ctx,clip_radius=reactive_center_radius,fallback_accent=base_color)
            bars=17
            for k in range(bars):
                v=values[int(k*count/bars)]; a=k/bars*math.tau-math.pi/2.0+now*0.08; inner=max_effect_radius*0.30; outer=min(max_effect_radius*0.82,inner+short_side*(0.04+v*0.22)); col=QColor(base_color); col.setAlpha(120+int(v*100)); p.setPen(QPen(col,max(1.0,(1.6+v*3.6)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for r_i in range(4):
                rr=max_effect_radius*(0.86+r_i*0.035); col=QColor(base_color); col.setAlpha(52-r_i*7); p.setPen(QPen(col,1)); p.drawEllipse(QPointF(cx,cy),rr,rr)
            p.restore(); return

        if style == "electro_dubstep":
            # Circular audio-reactive mesh ring around the current media cover. No equalizer bars.
            self._paint_electro_dubstep_mesh_ring(p, values, area, ctx, base_color, now, avg, bass, max_effect_radius, width_scale)
            p.restore(); return

        if style == "minimal_beat":
            # Outer double ring with jagged waveform between, assertive translucent bars around inner circle.
            outer=max_effect_radius*0.82; p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(base_color.red(),base_color.green(),base_color.blue(),90),1.2*width_scale)); p.drawEllipse(QPointF(cx,cy),outer,outer); p.drawEllipse(QPointF(cx,cy),outer-5,outer-5)
            pts=[]; sample=96
            for s in range(sample+1):
                v=values[int((s%sample)*count/sample)%count]; a=s/sample*math.tau-math.pi/2; rr=outer-2.5+(((-1)**s)*short_side*(0.006+v*0.025)); pts.append(QPointF(cx+math.cos(a)*rr,cy+math.sin(a)*rr))
            self._draw_visualizer_polyline(p,pts,QColor(base_color),1.4*width_scale,105)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(0,0,0,82))); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.32,max_effect_radius*0.32)
            step=max(1,count//80)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2; inner=max_effect_radius*0.38; outer2=min(max_effect_radius*0.70,inner+short_side*(0.035+v*0.19)); col=QColor(base_color); col.setAlpha(205); p.setPen(QPen(col,max(1.0,(1.3+v*3.6)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer2,cy+math.sin(a)*outer2))
            p.restore(); return

        if style == "lofi_vibes":
            # Horizontal translucent white bars with two assertive white waveform lines below.
            slot=aw/count; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255,255,255,205)))
            for i,v in enumerate(values):
                h=ah*(0.04+v*0.48); p.drawRoundedRect(QRectF(area.left()+i*slot+slot*0.25,cy-h*0.5,max(1.0,slot*0.5*width_scale),h),2,2)
            for layer in range(2):
                pts=[]; smooth=avg
                for i,raw in enumerate(values):
                    smooth=smooth*0.80+raw*0.20; x=area.left()+aw*i/max(1,count-1); y=cy+ah*(0.22+layer*0.08)+math.sin(i*0.12+now*(0.9+layer*0.2))*ah*0.06-(smooth-avg)*ah*0.18; pts.append(QPointF(x,y))
                self._draw_visualizer_polyline(p,pts,QColor(255,255,255,185-layer*35),2.0*width_scale,185-layer*35)
            p.restore(); return

        if style == "cosmic_fusion":
            # Frosted translucent circle, media cover inside the bars, and assertive translucent rainbow bars.
            rg=QRadialGradient(QPointF(cx,cy),max_effect_radius*0.46); rg.setColorAt(0,QColor(255,255,255,46)); rg.setColorAt(0.6,QColor(base_color.red(),base_color.green(),base_color.blue(),42)); rg.setColorAt(1,QColor(255,255,255,20)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(rg)); p.drawEllipse(QPointF(cx,cy),max_effect_radius*0.46,max_effect_radius*0.46)
            cosmic_cover_radius=max(1.0,max_effect_radius*0.46)
            cosmic_cover_rect=QRectF(cx-cosmic_cover_radius,cy-cosmic_cover_radius,cosmic_cover_radius*2.0,cosmic_cover_radius*2.0)
            self._draw_visualizer_media_thumbnail_cover(p,cosmic_cover_rect,ctx,clip_radius=cosmic_cover_radius,fallback_accent=base_color)
            step=max(1,count//96)
            for i in range(0,count,step):
                v=values[i]; a=i/count*math.tau-math.pi/2; inner=max_effect_radius*0.48; outer=min(max_effect_radius*0.98,inner+short_side*(0.045+v*0.24)); col=self._rainbow_color(i/count+now*0.04,205); p.setPen(QPen(col,max(1.0,(1.5+v*4.5)*width_scale))); p.drawLine(QPointF(cx+math.cos(a)*inner,cy+math.sin(a)*inner),QPointF(cx+math.cos(a)*outer,cy+math.sin(a)*outer))
            p.restore(); return

        # Existing first-wave style families.
        circular = style in ("circle", "turntable", "spotlight_beat", "euphoria_motion", "luminance", "space")
        elliptic = style in ("ellipse", "parallax_waves")
        wall = style in ("music_beat_wall", "led_audio_wave", "hud_equalizer", "flat_spectrum", "cyber", "retro_future", "minimal", "alternative", "bass_drop", "audio_react", "rainbow", "dynamic_glitch", "urban_timelapse", "melodic_vibe")
        if circular or elliptic:
            rx_scale = 1.40 if elliptic else 1.0
            ry_scale = 0.58 if elliptic else 1.0
            max_core_radius = max(2.0, min(aw / max(1.0, rx_scale), ah / max(1.0, ry_scale)) * 0.30)
            core_radius = min(radius, max_core_radius)
            rx = core_radius * rx_scale; ry = core_radius * ry_scale
            max_ray_len = max(2.0, min(max(1.0, aw * 0.48 - rx), max(1.0, ah * 0.48 - ry)))
            if style == "turntable":
                p.setPen(QPen(QColor(255,255,255,42), 2)); p.setBrush(Qt.BrushStyle.NoBrush)
                for k in range(4): p.drawEllipse(QPointF(cx, cy), core_radius * (0.45 + k * 0.18 + bass * 0.03), core_radius * (0.45 + k * 0.18 + bass * 0.03))
                p.setBrush(QBrush(QColor(base_color.red(), base_color.green(), base_color.blue(), 80))); p.drawEllipse(QPointF(cx, cy), core_radius * 0.18, core_radius * 0.18)
            if style == "spotlight_beat":
                for k in range(6):
                    ang = now * 0.8 + k * math.pi / 3.0
                    p.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 26 + int(bass*70)), 12 + bass*18)); p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(ang) * rx * 1.5, cy + math.sin(ang) * ry * 1.5))
            for i, v in enumerate(values):
                ang = (i / count) * math.tau - math.pi / 2.0 + (now * 0.25 if style in ("turntable", "euphoria_motion") else 0.0)
                length = min(max_ray_len, short_side * (0.05 + 0.16 * v))
                col = self._rainbow_color(i / count + now * 0.08, 235) if style in ("euphoria_motion", "rainbow") else QColor(base_color)
                if style == "luminance": col = QColor(255, 255, 240, 130 + int(v * 125))
                p.setPen(QPen(col, max(1.0, (1.5 + v * 4.0) * width_scale)))
                p.drawLine(QPointF(cx + math.cos(ang) * rx, cy + math.sin(ang) * ry), QPointF(cx + math.cos(ang) * (rx + length), cy + math.sin(ang) * (ry + length)))
            p.restore(); return
        if wall:
            slot = aw / count
            for i, v in enumerate(values):
                x = area.left() + i * slot; h = max(2.0, ah * (0.08 + v * 0.88)); col = QColor(base_color)
                if style == "rainbow": col = self._rainbow_color(i / max(1, count) + now * 0.06, 230)
                elif style == "cyber": col = QColor(0, 245, 255, 220)
                elif style == "retro_future": col = self._rainbow_color(0.78 + i/count*0.16, 210)
                elif style == "bass_drop": col = QColor(255, 60 + int(80*v), 90, 230)
                elif style == "minimal": col.setAlpha(175)
                elif style == "hud_equalizer": col = QColor(80, 255, 190, 220)
                elif style == "dynamic_glitch": col = QColor(255 if i % 3 == 0 else base_color.red(), base_color.green(), 255 if i % 4 == 0 else base_color.blue(), 220)
                elif style == "urban_timelapse": col = QColor(255, 188, 80, 210)
                elif style == "flat_spectrum": col = QColor(base_color.red(), base_color.green(), base_color.blue(), 210)
                if style == "music_beat_wall":
                    levels = 5; cell_h = ah / levels * 0.72
                    for j in range(levels):
                        if (j + 1) / levels <= v + 0.12:
                            cc = QColor(col); cc.setAlpha(80 + int(150 * ((j+1)/levels))); p.setBrush(QBrush(cc)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(QRectF(x + slot*0.16, area.bottom() - (j+1)*ah/levels, slot*0.68, cell_h), 2, 2)
                elif style == "led_audio_wave":
                    dot = max(2.0, min(7.0, slot * 0.45)); y = cy + math.sin(i * 0.32 + now * 3.2) * ah * 0.12; steps = max(1, int(v * 7))
                    for j in range(-steps, steps + 1):
                        cc = QColor(col); cc.setAlpha(max(35, 210 - abs(j)*22)); p.setBrush(QBrush(cc)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(x + slot/2, y + j * dot * 1.7), dot, dot)
                elif style == "dynamic_glitch":
                    jitter = ((i * 17 + int(now * 60)) % 7 - 3) * (1.0 + bass * 3.0); p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen); p.drawRect(QRectF(x + slot*0.18 + jitter, area.bottom() - h, max(1.0, slot * min(0.98, 0.62 * width_scale)), h))
                elif style in ("audio_react", "melodic_vibe"):
                    p.setPen(QPen(col, max(1.0, slot*0.24))); p.drawLine(QPointF(x + slot/2, cy + h*0.45), QPointF(x + slot/2, cy - h*0.5))
                elif style == "minimal":
                    p.setPen(QPen(col, 2.0)); p.drawLine(QPointF(x + slot/2, area.bottom()), QPointF(x + slot/2, area.bottom() - h))
                else:
                    p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(QRectF(x + slot*0.18, area.bottom() - h, max(1.0, slot * min(0.98, 0.64 * width_scale)), h), 1 if style == "flat_spectrum" else 4, 1 if style == "flat_spectrum" else 4)
            if style in ("retro_future", "cyber", "hud_equalizer"):
                p.setPen(QPen(QColor(255,255,255,38), 1))
                for gy in range(1, 5): p.drawLine(QPointF(area.left(), area.top() + ah * gy / 5.0), QPointF(area.right(), area.top() + ah * gy / 5.0))
            p.restore(); return
        p.restore()

    def _paint_visualizer_direct(self, p: QPainter, ctx: Dict):
        audio: AudioEngine = ctx["audio"]
        bars = audio.get_spectrum()
        count = max(1, len(bars))
        r = self.rect
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        style = self._visualizer_style()
        # hud_equalizer is intentionally transparent: only the rings and audio bars are drawn.
        # Other visualizer styles keep the normal widget background.
        if style == "hud_equalizer":
            p.setPen(Qt.PenStyle.NoPen)
        else:
            bg = widget_bg_color(self.cfg)
            p.setBrush(QBrush(bg))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 16, 16)
        # All visualizer effects are clipped to the rounded widget frame.
        clip_path = QPainterPath()
        clip_path.addRoundedRect(r, 16, 16)
        p.setClipPath(clip_path)

        margin = 14
        label_h = 0
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

        if style != "classic":
            inner_inset = max(6.0, min(available_w, available_h) * 0.060)
            area = QRectF(
                left + inner_inset,
                top + inner_inset,
                max(1.0, available_w - inner_inset * 2.0),
                max(1.0, available_h - inner_inset * 2.0),
            )
            self._paint_visualizer_styled(p, bars, style, r, area, color, now, ctx)
            p.setPen(QColor(230, 240, 255, 220))
            p.setFont(QFont("Segoe UI", 9))
            label = ""
            if audio.use_fake:
                label += "fallback"
            pass  # label hidden
            if self.selected and ctx.get("edit_mode", True):
                self._paint_selection(p)
            p.restore()
            return
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
        pass  # label hidden
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

    def _get_media_thumbnail_pixmap(self, ctx: Dict):
        media_meta = ctx.get("media_meta") if isinstance(ctx, dict) else None
        thumbnail_bytes = b""

        if media_meta is not None:
            try:
                if hasattr(media_meta, "get_thumbnail_bytes"):
                    thumbnail_bytes = media_meta.get_thumbnail_bytes()
                else:
                    data = media_meta.snapshot() if hasattr(media_meta, "snapshot") else {}
                    thumbnail_bytes = data.get("thumbnail_bytes", b"") if isinstance(data, dict) else b""
            except:
                thumbnail_bytes = b""

        if not thumbnail_bytes:
            self._last_media_thumbnail_bytes = None
            self._media_thumbnail_pixmap = None
            return None

        if self._last_media_thumbnail_bytes == thumbnail_bytes and self._media_thumbnail_pixmap is not None:
            return self._media_thumbnail_pixmap

        image = QImage.fromData(thumbnail_bytes)
        if image.isNull():
            self._last_media_thumbnail_bytes = None
            self._media_thumbnail_pixmap = None
            return None

        self._last_media_thumbnail_bytes = thumbnail_bytes
        self._media_thumbnail_pixmap = QPixmap.fromImage(image)
        return self._media_thumbnail_pixmap

    def _draw_visualizer_media_thumbnail_cover(self, p: QPainter, rect: QRectF, ctx: Dict, clip_radius: float, fallback_accent: QColor):
        pixmap = self._get_media_thumbnail_pixmap(ctx)

        if pixmap is None or pixmap.isNull():
            p.save()
            p.setBrush(QColor(fallback_accent.red(), fallback_accent.green(), fallback_accent.blue(), 22))
            p.setPen(QPen(QColor(fallback_accent.red(), fallback_accent.green(), fallback_accent.blue(), 52), 1.0))
            p.drawEllipse(rect)
            p.restore()
            return False

        scaled = pixmap.scaled(
            int(max(1.0, rect.width())),
            int(max(1.0, rect.height())),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = int(rect.left() + (rect.width() - scaled.width()) / 2.0)
        y = int(rect.top() + (rect.height() - scaled.height()) / 2.0)

        clip_path = QPainterPath()
        clip_path.addEllipse(rect)

        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setClipPath(clip_path)
        p.drawPixmap(x, y, scaled)
        p.restore()

        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 48), max(1.0, clip_radius * 0.010)))
        p.drawEllipse(rect)
        p.setPen(QPen(QColor(fallback_accent.red(), fallback_accent.green(), fallback_accent.blue(), 72), max(1.0, clip_radius * 0.014)))
        p.drawEllipse(rect.adjusted(1.5, 1.5, -1.5, -1.5))
        p.restore()

        return True

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


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
        except:
            bg = QColor(self.cfg.bg or "#10141C")
            bg.setAlpha(getattr(self.cfg, "bg_alpha", 155))

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 16, 16)

        accent = QColor(self.cfg.color or "#80FF9F")
        title_color = QColor(245, 248, 255)
        sub_color = QColor(210, 218, 230, 160)
        muted_color = QColor(210, 218, 230, 115)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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

        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(text_left, r.top() + 46, text_w, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._elide_text(p, title, int(text_w))
        )

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(sub_color)
        p.drawText(
            QRectF(text_left, r.top() + 72, text_w, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._elide_text(p, meta_line, int(text_w))
        )

        if error:
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QColor(255, 190, 130, 170))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 124, r.width() - 28, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )

            x = int(rect.left() + (rect.width() - scaled.width()) / 2)
            y = int(rect.top() + (rect.height() - scaled.height()) / 2)

            p.save()
            p.setClipRect(rect)
            p.drawPixmap(x, y, scaled)
            p.restore()
            return

        p.setFont(QFont("Segoe UI Symbol", 28, QFont.Weight.Bold))
        p.setPen(accent)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "♪")

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

        p.setFont(QFont("Segoe UI Symbol", 15, QFont.Weight.Bold))
        p.setPen(accent)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)

    def _elide_text(self, p: QPainter, text: str, width: int):
        metrics = p.fontMetrics()
        return metrics.elidedText(text or "", Qt.TextElideMode.ElideRight, max(20, width))


class SystemWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        monitor: SystemMonitor = ctx["monitor"]
        monitor.update()

        r = self.rect

        bg = widget_bg_color(self.cfg)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 16, 16)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
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
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bx, y + 3, bw, h - 6), 5, 5)

        fill_w = bw * max(0, min(100, value)) / 100.0
        p.setBrush(color)
        p.drawRoundedRect(QRectF(bx, y + 3, fill_w, h - 6), 5, 5)

        p.setPen(QColor(240, 240, 240))
        p.drawText(QRectF(bx + bw + 8, y - 2, 42, h), f"{value:>3.0f}%")

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


class NetworkWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        monitor = ctx["monitor"]
        monitor.update()

        r = self.rect

        p.save()

        try:
            bg = widget_bg_color(self.cfg)
        except:
            bg = QColor(self.cfg.bg or "#10141C")
            bg.setAlpha(getattr(self.cfg, "bg_alpha", 155))

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 16, 16)

        down_color = QColor(get_network_down_color(self.cfg))
        up_color = QColor(get_network_up_color(self.cfg))

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QColor(245, 248, 255))
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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

        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        label_metrics = p.fontMetrics()
        label_w = min(42, max(28, label_metrics.horizontalAdvance(label_text) + 8))
        label_rect = QRectF(x + 34, y, label_w, 20)
        value_rect = QRectF(x + 34 + label_w + 6, y, max(20, w - (34 + label_w + 6)), 20)

        label_color = QColor(235, 240, 250, 210)
        p.setPen(label_color)
        p.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label_text
        )

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(color)
        p.drawText(
            value_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
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
        p.drawText(QRectF(x, y, total_w, rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, total_text)
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
        p.drawText(QRectF(x, y, down_label_w, rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, down_label)
        x += down_label_w + 4
        p.drawText(QRectF(x, y, down_w, rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(total_down))
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
        p.drawText(QRectF(x, y, up_label_w, rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, up_label)
        x += up_label_w + 4
        p.drawText(QRectF(x, y, up_w, rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(total_up))

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
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "last 30s"
        )

        p.drawText(
            QRectF(rect.left() + 8, rect.bottom() - 20, rect.width() - 16, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
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
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

        pen = QPen(color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

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
        p.setPen(Qt.PenStyle.NoPen)
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
            Qt.AlignmentFlag.AlignCenter,
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
        pen.setStyle(Qt.PenStyle.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)


class AnalogClockWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        r = self.rect
        p.save()

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

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

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QColor(240, 240, 255))

        for num in range(1, 13):
            angle = math.radians(num * 30 - 90)
            tr = radius * 0.65

            x = cx + math.cos(angle) * tr
            y = cy + math.sin(angle) * tr

            p.drawText(QRectF(x - 12, y - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, str(num))

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
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 4, 4)
        p.restore()

    def _draw_hand(self, p, cx, cy, length, angle_deg, color, width):
        angle = math.radians(angle_deg)
        x = cx + math.cos(angle) * length
        y = cy + math.sin(angle) * length

        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        p.setPen(pen)
        p.drawLine(int(cx), int(cy), int(x), int(y))


class CalendarWidget(BaseWidget):
    def paint(self, p: QPainter, ctx: Dict):
        r = self.rect
        p.save()
        bg = widget_bg_color(self.cfg)

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
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

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.cfg.title or ""
        )

        month_label = f"{year} / {month:02d}"

        p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        p.setPen(month_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 36, r.width() - 28, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))

        for i, day_name in enumerate(weekdays):
            x = grid_left + cell_w * i
            header_rect = QRectF(x, grid_top, cell_w, header_h)

            if i >= 5:
                p.setPen(weekend_color)
            else:
                p.setPen(weekday_color)

            p.drawText(
                header_rect,
                Qt.AlignmentFlag.AlignCenter,
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
                    p.setPen(Qt.PenStyle.NoPen)

                    size = min(cell_rect.width(), cell_rect.height(), 28)
                    cx = cell_rect.center().x()
                    cy = cell_rect.center().y()

                    p.drawEllipse(
                        QPoint(int(cx), int(cy)),
                        int(size / 2),
                        int(size / 2)
                    )

                    p.setPen(today_text_color)
                    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

                else:
                    p.setBrush(Qt.BrushStyle.NoBrush)

                    if col >= 5:
                        p.setPen(weekend_color)
                    else:
                        p.setPen(day_color)

                    p.setFont(QFont("Segoe UI", 9))

                p.drawText(
                    cell_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    str(day)
                )

                day += 1

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

        p.restore()

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
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
        p.setPen(Qt.PenStyle.NoPen)
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
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
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
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 16, 16)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QColor(245, 248, 255))
        p.drawText(QRectF(r.left() + 14, r.top() + 10, r.width(), 24), "Volume")

        bx = r.left() + 18
        by = r.top() + 54
        bw = r.width() - 36
        bh = 16

        p.setBrush(QColor(255, 255, 255, 30))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 8, 8)

        p.setBrush(QColor(self.cfg.color))
        p.drawRoundedRect(QRectF(bx, by, bw * v / 100.0, bh), 8, 8)

        p.setPen(QColor(240, 240, 240))
        p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        p.drawText(QRectF(r.left(), r.top() + 72, r.width(), 40), Qt.AlignmentFlag.AlignCenter, f"{v}%")

        if not volume.available:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(255, 210, 120))
            p.drawText(QRectF(r.left() + 12, r.bottom() - 22, r.width() - 24, 16),
                       "pycaw unavailable")

        if self.selected and ctx.get("edit_mode", True):
            self._paint_selection(p)

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
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
        except:
            bg = QColor(self.cfg.bg or "#10141C")
            bg.setAlpha(getattr(self.cfg, "bg_alpha", 155))

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 16, 16)

        accent = QColor(self.cfg.color or "#80FF9F")
        title_color = QColor(245, 248, 255)
        sub_color = QColor(210, 218, 230, 170)
        text_color = QColor(235, 240, 250, 220)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(title_color)
        p.drawText(
            QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            place_text
        )

        error = data.get("error", "")

        if error:
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor(255, 180, 120))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 62, r.width() - 28, 40),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                lds_tr("天気の取得に失敗しました")
            )

            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(255, 210, 180, 160))
            p.drawText(
                QRectF(r.left() + 14, r.top() + 98, r.width() - 28, 50),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
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
            Qt.AlignmentFlag.AlignCenter,
            icon
        )

        p.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
        p.setPen(accent)
        p.drawText(
            temp_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{temp}°"
        )

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(text_color)
        p.drawText(
            desc_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            desc
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(sub_color)
        p.drawText(
            feels_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
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
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            p.setPen(sub_color)
            p.drawText(
                QRectF(r.left() + 14, forecast_top, r.width() - 28, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                lds_tr("3日予報")
            )

            card_top = forecast_top + 22
            card_w = (r.width() - 34) / 3.0

            for i, item in enumerate(forecast[:3]):
                x = r.left() + 14 + i * (card_w + 3)
                rect = QRectF(x, card_top, card_w, 56)

                p.setBrush(QColor(255, 255, 255, 20))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 10, 10)

                date = item.get("date", "")
                max_t = item.get("max", "--")
                min_t = item.get("min", "--")
                day_icon = item.get("icon", "☁")

                p.setFont(QFont("Segoe UI", 7))
                p.setPen(sub_color)
                p.drawText(
                    QRectF(rect.left() + 5, rect.top() + 3, rect.width() - 10, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    date[-5:] if len(date) >= 5 else date
                )

                p.setFont(QFont("Segoe UI Emoji", 14))
                p.setPen(accent)
                p.drawText(
                    QRectF(rect.left() + 5, rect.top() + 16, rect.width() - 10, 18),
                    Qt.AlignmentFlag.AlignCenter,
                    day_icon
                )

                p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                p.setPen(text_color)
                p.drawText(
                    QRectF(rect.left() + 5, rect.top() + 35, rect.width() - 10, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{min_t}°/{max_t}°"
                )

        updated = data.get("updated_at", "")

        if updated:
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QColor(210, 218, 230, 120))
            p.drawText(
                QRectF(r.left() + 12, r.bottom() - 20, r.width() - 24, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
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
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label
        )

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(value_color)
        p.drawText(
            QRectF(x + w * 0.45, y, w * 0.55, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            value
        )

    def _paint_selection(self, p: QPainter):
        pen = QPen(QColor("#FFFFFF"))
        pen.setStyle(Qt.PenStyle.DashLine)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect, 16, 16)
