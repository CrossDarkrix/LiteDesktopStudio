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
    visualizer_shadow_enabled: bool = True
    visualizer_shadow_offset_x: float = 3.0
    visualizer_shadow_offset_y: float = 4.0
    visualizer_shadow_strength: float = 1.0
    visualizer_shadow_opacity: float = 0.65
    visualizer_shadow_depth: float = 1.0
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
        return 1.0 / fps


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
        }
        return aliases.get(value, value if value else "classic")

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
            shadow_strength = max(0.0, min(3.0, shadow_strength))
            shadow_opacity = max(0.0, min(1.0, shadow_opacity))
            shadow_depth = max(0.0, min(3.0, shadow_depth))
            if shadow_strength <= 0.0 or shadow_opacity <= 0.0 or shadow_depth <= 0.0:
                return
            depth_offset_scale = 0.45 + shadow_depth * 0.55
            ox *= depth_offset_scale
            oy *= depth_offset_scale
            alpha = max(0, min(190, int((30 + avg * 62 + bass * 22) * shadow_strength * shadow_opacity * (0.85 + shadow_depth * 0.10))))
            if alpha <= 0:
                return
            shadow = QColor(0, 0, 0, alpha)
            soft_shadow = QColor(0, 0, 0, max(1, int(alpha * (0.34 + shadow_depth * 0.08))))
            shadow_size = max(0.20, min(3.5, shadow_strength * (0.70 + shadow_depth * 0.30)))
            shadow_size *= max(0.35, min(2.4, self._visualizer_bar_width_scale()))
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(Qt.PenStyle.NoPen)

            circular = style in ("circle", "turntable", "spotlight_beat", "euphoria_motion", "luminance", "space", "energy_shield", "audio_ripple", "radar_scan", "circle_waveform")
            elliptic = style in ("ellipse", "parallax_waves")
            tunnel = style in ("audio_tunnel", "neon_tunnel_wire", "futuristic_tunnel")
            wave = style in ("aurora", "neon_soundwave", "enigmatic_echo_sound", "lofi_vibes", "electric_pulse")
            cloud = style in ("nebula", "cosmic_fusion", "meteor_shower", "reactive_lights")
            wall = style in ("music_beat_wall", "led_audio_wave", "hud_equalizer", "flat_spectrum", "cyber", "retro_future", "minimal", "alternative", "bass_drop", "audio_react", "rainbow", "dynamic_glitch", "urban_timelapse", "melodic_vibe", "hologram", "matrix", "electro_dubstep", "minimal_beat", "beat_fluorescent_app", "glow_beat_music")

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
        try:
            count = max(1, len(values))
            aw = max(1.0, float(area.width()))
            ah = max(1.0, float(area.height()))
            cx = area.center().x()
            cy = area.center().y()
            short_side = min(aw, ah)
            glow_base = QColor(base_color)
            base_alpha = max(20, min(150, int(34 + avg * 80 + bass * 45)))
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(Qt.PenStyle.NoPen)

            circular = style in ("circle", "turntable", "spotlight_beat", "euphoria_motion", "luminance", "space", "energy_shield", "audio_ripple", "radar_scan", "circle_waveform")
            elliptic = style in ("ellipse", "parallax_waves")
            tunnel = style in ("audio_tunnel", "neon_tunnel_wire", "futuristic_tunnel")
            wave = style in ("aurora", "neon_soundwave", "enigmatic_echo_sound", "lofi_vibes", "electric_pulse")
            cloud = style in ("nebula", "cosmic_fusion", "meteor_shower", "reactive_lights")
            wall = style in ("music_beat_wall", "led_audio_wave", "hud_equalizer", "flat_spectrum", "cyber", "retro_future", "minimal", "alternative", "bass_drop", "audio_react", "rainbow", "dynamic_glitch", "urban_timelapse", "melodic_vibe", "hologram", "matrix", "electro_dubstep", "minimal_beat", "beat_fluorescent_app", "glow_beat_music")

            if circular or elliptic:
                rx_scale = 1.34 if elliptic else 1.0
                ry_scale = 0.58 if elliptic else 1.0
                core = min(radius, max_effect_radius * 0.62)
                # broad center aura
                aura = QRadialGradient(QPointF(cx, cy), max(2.0, max_effect_radius * 1.04))
                c0 = QColor(glow_base); c0.setAlpha(max(18, int(base_alpha * 0.45)))
                c1 = QColor(glow_base); c1.setAlpha(0)
                aura.setColorAt(0.0, c0)
                aura.setColorAt(1.0, c1)
                p.setBrush(QBrush(aura))
                p.drawEllipse(QPointF(cx, cy), max_effect_radius * rx_scale, max_effect_radius * ry_scale)
                # line halos around active radial bars
                step = max(1, count // 36)
                pen_color = QColor(glow_base); pen_color.setAlpha(base_alpha)
                pen = QPen(pen_color, max(2.0, (short_side * 0.018 + bass * 3.0) * width_scale))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                for i in range(0, count, step):
                    v = max(0.0, min(1.0, float(values[i])))
                    if v <= 0.025:
                        continue
                    ang = i / count * math.tau - math.pi / 2.0
                    inner = core * 0.82
                    outer = min(max_effect_radius * 0.98, inner + short_side * (0.07 + v * 0.16))
                    col = self._rainbow_color(i / count + now * 0.06, base_alpha) if style in ("euphoria_motion", "rainbow", "circle_waveform") else pen_color
                    p.setPen(QPen(col, max(2.0, (short_side * 0.018 + v * 4.0) * width_scale)))
                    p.drawLine(
                        QPointF(cx + math.cos(ang) * inner * rx_scale, cy + math.sin(ang) * inner * ry_scale),
                        QPointF(cx + math.cos(ang) * outer * rx_scale, cy + math.sin(ang) * outer * ry_scale),
                    )
                p.restore(); return

            if tunnel:
                p.setBrush(Qt.BrushStyle.NoBrush)
                for k in range(7):
                    t = k / 6.0
                    scale = 1.0 - t * 0.78
                    rect = QRectF(cx - aw * scale * 0.41, cy - ah * scale * 0.34, aw * scale * 0.82, ah * scale * 0.68)
                    col = self._rainbow_color(0.52 + t * 0.34 + now * 0.04, max(18, int(base_alpha * (1.0 - t * 0.45))))
                    pen = QPen(col, max(2.0, (2.0 + (1.0 - t) * 3.4 + bass * 2.0) * width_scale))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.setPen(pen)
                    p.drawRoundedRect(rect, 8, 8)
                p.restore(); return

            if wave:
                colors = [QColor(glow_base), self._rainbow_color(0.78 + now * 0.03, base_alpha), self._rainbow_color(0.52 + now * 0.04, base_alpha)]
                for layer in range(2):
                    pts = []
                    for i, v in enumerate(values):
                        x = area.left() + aw * i / max(1, count - 1)
                        y = cy + math.sin(i * (0.16 + layer * 0.06) + now * (1.3 + layer * 0.25)) * ah * (0.07 + layer * 0.035) - (float(v) - avg) * ah * (0.22 + layer * 0.07)
                        pts.append(QPointF(x, y))
                    col = colors[layer % len(colors)]
                    self._draw_visualizer_polyline(p, pts, col, (5.0 + layer * 2.0 + bass * 3.0) * width_scale, max(35, int(base_alpha * 0.80)))
                p.restore(); return

            if cloud:
                step = max(1, count // 26)
                for i in range(0, count, step):
                    v = max(0.0, min(1.0, float(values[i])))
                    if v <= 0.02:
                        continue
                    angle = i / count * math.tau + now * 0.10
                    rr = min(max_effect_radius * 0.80, radius * (0.36 + (i % 6) * 0.055 + v * 0.38))
                    col = self._rainbow_color(0.62 + i / count * 0.42 + now * 0.03, max(28, int(base_alpha * (0.55 + v * 0.35)))) if style in ("nebula", "cosmic_fusion") else QColor(glow_base)
                    self._draw_visualizer_soft_orb(
                        p,
                        QPointF(cx + math.cos(angle) * rr, cy + math.sin(angle * 1.25) * rr * 0.62),
                        (7.0 + v * short_side * 0.060) * width_scale,
                        col,
                        max(28, int(base_alpha * 0.85)),
                    )
                p.restore(); return

            if wall:
                slot = aw / count
                p.setPen(Qt.PenStyle.NoPen)
                step = 1 if count <= 96 else max(1, count // 96)
                for i in range(0, count, step):
                    v = max(0.0, min(1.0, float(values[i])))
                    if v <= 0.02:
                        continue
                    x = area.left() + i * slot + slot * 0.08
                    h = ah * (0.08 + v * 0.88)
                    y = area.bottom() - h
                    bw = max(1.0, slot * min(1.18, 0.86 * width_scale))
                    col = self._rainbow_color(i / max(1, count) + now * 0.06, max(24, int(base_alpha * 0.85))) if style in ("rainbow", "beat_fluorescent_app", "retro_future") else QColor(glow_base)
                    col.setAlpha(max(20, min(170, int(base_alpha * (0.48 + v * 0.45)))))
                    p.setBrush(QBrush(col))
                    p.drawRoundedRect(QRectF(x - bw * 0.18, y - 4.0, bw * 1.36, h + 8.0), 6, 6)
                p.restore(); return
            p.restore()
        except Exception:
            try:
                p.restore()
            except Exception:
                pass

    def _paint_visualizer_styled(self, p: QPainter, bars, style: str, r: QRectF, area: QRectF, base_color: QColor, now: float):
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

        if style in ("energy_shield", "audio_ripple", "radar_scan", "circle_waveform"):
            rings = 5 if style != "circle_waveform" else 3
            for k in range(rings):
                rr = min(max_effect_radius, short_side * (0.11 + k * 0.075 + bass * 0.035 + ((now * 0.12 + k * 0.06) % 0.045 if style == "audio_ripple" else 0.0)))
                alpha = max(18, 115 - k * 17 + int(avg * 70))
                col = QColor(base_color)
                if style == "energy_shield": col = QColor(60, 210, 255, alpha)
                elif style == "radar_scan": col = QColor(80, 255, 140, alpha)
                elif style == "circle_waveform": col = self._rainbow_color(k * 0.13 + now * 0.05, alpha)
                else: col.setAlpha(alpha)
                p.setPen(QPen(col, (1.2 + bass * 3.2) * width_scale)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rr, rr)
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

        if style in ("electro_dubstep", "minimal_beat", "beat_fluorescent_app", "glow_beat_music"):
            slot = aw / count
            for i, v in enumerate(values):
                x = area.left() + i * slot; h = ah * (0.08 + v * 0.88)
                if style == "electro_dubstep":
                    col = QColor(120 + int(120 * v), 40, 255, 215)
                    if i % 4 == 0: h *= 1.18 + bass * 0.35
                elif style == "minimal_beat":
                    col = QColor(base_color); col.setAlpha(150 + int(v * 80))
                elif style == "glow_beat_music":
                    col = QColor(255, 230, 120, 180 + int(v * 70)); self._draw_visualizer_soft_orb(p, QPointF(x + slot * 0.5, area.bottom() - h), 5 + v * 18, col, 50 + int(v * 80))
                else:
                    col = self._rainbow_color(i / count + now * 0.11, 210, 0.95, 1.0)
                p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
                if style == "minimal_beat": p.drawRect(QRectF(x + slot*0.35, area.bottom() - h, max(1.0, slot * min(0.98, 0.30 * width_scale)), h))
                else: p.drawRoundedRect(QRectF(x + slot*0.16, area.bottom() - h, max(1.0, slot * min(0.98, 0.68 * width_scale)), h), 3, 3)
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

        style = self._visualizer_style()
        if style != "classic":
            inner_inset = max(6.0, min(available_w, available_h) * 0.060)
            area = QRectF(
                left + inner_inset,
                top + inner_inset,
                max(1.0, available_w - inner_inset * 2.0),
                max(1.0, available_h - inner_inset * 2.0),
            )
            self._paint_visualizer_styled(p, bars, style, r, area, color, now)
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
