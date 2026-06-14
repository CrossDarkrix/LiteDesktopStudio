"""Preview3D runtime classes for LiteDesktopStudio.

Phase 23A4C fixes Effects Overlay selected-effect disable by resolving canvas owner robustly and clearing render caches.
The DesktopCanvas-owned state build/apply methods intentionally remain in the
main file because they are still tightly coupled to canvas widgets and settings.

Safety notes:
- Do not move QWidget/QMainWindow/QOpenGLWidget instances to another thread.
- Do not add nativeEvent handling for WM_RBUTTONDBLCLK / WM_CONTEXTMENU.
- Do not force-close #32768 popup windows.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict
from litedesktopstudio.version import APP_NAME

try:
    from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QEvent
    from PySide6.QtGui import QColor, QBrush, QPen, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QIcon, QPixmap
    from PySide6.QtWidgets import QApplication, QWidget, QMainWindow, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox, QComboBox, QGroupBox, QScrollArea, QMenu, QMessageBox
    try:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
    except Exception:
        QOpenGLWidget = None
except Exception:  # pragma: no cover - lightweight import fallback for non-GUI smoke tests.
    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass
        def __getattr__(self, name):
            return _Dummy()
        def __call__(self, *args, **kwargs):
            return _Dummy()
        def __or__(self, other):
            return self
        def __and__(self, other):
            return self
        def __bool__(self):
            return False
        def __float__(self):
            return 0.0
        def __int__(self):
            return 0
    Qt = _Dummy()
    QApplication = _Dummy
    QWidget = object
    QOpenGLWidget = None
    QMenu = QMessageBox = QTimer = _Dummy
    QMainWindow = QWidget
    QDialog = _Dummy
    QVBoxLayout = QHBoxLayout = QPushButton = QLabel = QCheckBox = QComboBox = QGroupBox = QScrollArea = _Dummy
    QIcon = QPixmap = _Dummy
    QPoint = QPointF = QRectF = QColor = QBrush = QPen = QPainter = QPainterPath = QLinearGradient = QRadialGradient = _Dummy

try:
    from litedesktopstudio.core import lds_tr, lds_ui_text, is_windows, lds_safe_desktop_geometry, _lds_app_base_dir, CONFIG_PATH, DEFAULT_STUDIO_THEME, normalize_studio_theme, get_studio_window_opacity, build_beginner_photoshop_settings_qss
except Exception:  # pragma: no cover - fallback for isolated module tests.
    def lds_tr(text):
        return str(text)

    def lds_ui_text(ja, en=None):
        return str(ja if ja is not None else (en or ""))

    CONFIG_PATH = os.path.join(str(Path.home()), "LiteDesktopStudio_config.json")
    DEFAULT_STUDIO_THEME = "material"

    def normalize_studio_theme(value):
        value = str(value or DEFAULT_STUDIO_THEME).strip().lower().replace("-", "_").replace(" ", "_")
        if value in ("liquid", "liquidglass", "glass"):
            return "liquid_glass"
        if value in ("dark", "material", "light", "liquid_glass"):
            return value
        return DEFAULT_STUDIO_THEME

    def get_studio_window_opacity(theme):
        return 0.94 if normalize_studio_theme(theme) != "light" else 0.96

    def build_beginner_photoshop_settings_qss(theme):
        return ""

    def _lds_app_base_dir():
        try:
            return Path(__file__).resolve().parent.parent
        except Exception:
            return Path(".")

    def is_windows():
        return sys.platform.startswith("win")

    def lds_safe_desktop_geometry():
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                return screen.geometry()
        except Exception:
            pass
        try:
            return QRectF(0, 0, 1920, 1080)
        except Exception:
            return None


def _lds_is_effects_overlay_widget(widget) -> bool:
    """Avoid importing the main-file EffectsOverlayWidget class during extraction."""
    try:
        if widget.__class__.__name__ == "EffectsOverlayWidget":
            return True
    except Exception:
        pass
    try:
        cfg = getattr(widget, "cfg", None)
        return str(getattr(cfg, "type", "")) == "effects_overlay"
    except Exception:
        return False


def _lds_create_detail_studio(canvas, preview_window):
    """Create LiteDeskStudio without importing LiteDesktopStudio at module import time.

    LDSPreview3DWindow moved out in Phase 23R4, while LiteDeskStudio still lives
    in the main file.  Looking it up lazily avoids a circular import during app
    startup and keeps the state/apply functions in the main module for now.
    """
    factory = None
    try:
        factory = getattr(preview_window, "_detail_studio_factory", None)
    except Exception:
        factory = None
    if factory is None:
        for module_name in ("__main__", "LiteDesktopStudio"):
            try:
                module = sys.modules.get(module_name)
                candidate = getattr(module, "LiteDeskStudio", None) if module is not None else None
                if candidate is not None:
                    factory = candidate
                    break
            except Exception:
                pass
    if factory is None:
        raise RuntimeError("LiteDeskStudio factory is not available yet; set _detail_studio_factory on LDSPreview3DWindow")
    return factory(canvas)

class LDSRightDoubleClickCatcher(QWidget):
    """Short-lived transparent right-click catcher for first normal-widget double-click.

    It is intentionally simple and temporary: the first right-click on a normal
    LiteDesktopStudio widget arms this window for about 0.6 seconds.  If the
    second right-click lands during that window, the catcher opens the Studio and
    consumes the click before Explorer can turn it into its own context menu.
    """

    def __init__(self, canvas):
        super().__init__(None)
        self.canvas = canvas
        self._target_pos = QPoint(0, 0)
        self._armed = False
        try:
            flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
            )
            try:
                flags |= Qt.WindowType.NoDropShadowWindowHint
            except Exception:
                pass
            try:
                flags |= Qt.WindowType.WindowDoesNotAcceptFocus
            except Exception:
                pass
            self.setWindowFlags(flags)
        except Exception:
            pass
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        try:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        except Exception:
            pass
        try:
            # Fully transparent top-level windows can be skipped by some desktop
            # compositions.  A near-zero opacity keeps it visually invisible while
            # remaining a reliable mouse target.
            self.setWindowOpacity(0.01)
        except Exception:
            pass
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.cancel)

    def arm(self, local_pos, timeout_ms=600):
        try:
            self._target_pos = QPoint(local_pos)
        except Exception:
            self._target_pos = QPoint(0, 0)
        self._armed = True
        try:
            if self.canvas is not None:
                self.canvas._right_double_click_catcher_active = True
        except Exception:
            pass
        try:
            screen = QApplication.primaryScreen()
            geom = screen.geometry() if screen is not None else lds_safe_desktop_geometry()
            self.setGeometry(geom)
        except Exception:
            try:
                self.setGeometry(lds_safe_desktop_geometry())
            except Exception:
                pass
        try:
            self.show()
            self.raise_()
        except Exception:
            pass
        try:
            self._timer.start(max(120, int(timeout_ms)))
        except Exception:
            pass
        return True

    def cancel(self):
        self._armed = False
        try:
            if self.canvas is not None:
                self.canvas._right_double_click_catcher_active = False
        except Exception:
            pass
        try:
            self.hide()
        except Exception:
            pass

    def _trigger(self, event=None):
        if not self._armed:
            try:
                if event is not None:
                    event.accept()
            except Exception:
                pass
            return
        target = QPoint(self._target_pos)
        # Do not hide the catcher before opening the 3D preview.  The flicker case
        # happens during this startup window: if the catcher disappears first, the
        # mouse release/context-menu sequence can briefly fall through to Explorer.
        self._armed = False
        try:
            if self.canvas is not None:
                self.canvas._right_double_click_catcher_active = True
        except Exception:
            pass
        try:
            if self.canvas is not None:
                self.canvas.open_studio_for_point(target)
        except Exception as e:
            try: print("[LiteDesktopStudio] right-double-click catcher open failed:", repr(e))
            except Exception: pass
        try:
            if event is not None:
                event.accept()
        except Exception:
            pass
        try:
            # Keep the invisible shield alive just long enough for the preview
            # window to finish show/raise/deferred initialization, then release it.
            self._timer.start(650)
        except Exception:
            self.cancel()

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.RightButton:
                self._trigger(event)
                return
            self.cancel()
            event.accept()
        except Exception:
            pass

    def mouseDoubleClickEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.RightButton:
                self._trigger(event)
                return
            event.accept()
        except Exception:
            pass

    def mouseReleaseEvent(self, event):
        try:
            event.accept()
        except Exception:
            pass

    def contextMenuEvent(self, event):
        try:
            event.accept()
        except Exception:
            pass

    def paintEvent(self, event):
        # Intentionally invisible.
        try:
            event.accept()
        except Exception:
            pass


class LDSPreview3DWidget(QOpenGLWidget if QOpenGLWidget is not None else QWidget):
    """Isolated 3D preview experiment.

    This intentionally does not touch cfg/effects_json yet. It only checks
    whether an OpenGL-backed preview surface can live inside the current
    PySide6 application. When QOpenGLWidget is unavailable, it falls back to
    QWidget while keeping the same UI shape.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._yaw = -28.0
        self._pitch = 58.0
        self._zoom = 1.0
        self._last_mouse_pos = None
        self._desktop_locked = False
        self._developer_mode = False
        self._preview_background_theme = "blue"
        self._snap_enabled = False
        self._drag_kind = None
        self._drag_notice = ""
        self._transient_notice_text = ""
        self._transient_notice_until = 0.0
        self._preview_selection_suppressed = False
        self._pending_sun_unit = None
        self._pending_moon_unit = None
        self._pending_puddle_state = None
        self._pending_puddle_states = {}
        self._selected_puddle_index = 0
        self._water_surface_selected = False
        self._bamboo_grove_selected = False
        self._cloud_selected = False
        self._fireball_selected = False
        self._pending_fireball_layer_state = None
        self._template_effect_selected_key = None
        self._pending_template_effect_states = {}
        self._template_effect_drag_start_pos = None
        self._template_effect_drag_start_state = None
        self._fireball_drag_start_pos = None
        self._fireball_drag_start_state = None
        self._pending_cloud_layer_state = None
        self._cloud_drag_start_pos = None
        self._cloud_drag_start_state = None
        self._cloud_resize_drag_start_pos = None
        self._cloud_resize_drag_start_state = None
        self._pending_bamboo_grove_state = None
        self._bamboo_grove_resize_drag_start_pos = None
        self._bamboo_grove_resize_drag_start_state = None
        self._pending_water_surface_state = None
        self._water_surface_drag_start_pos = None
        self._water_surface_drag_start_state = None
        self._water_surface_resize_drag_start_pos = None
        self._water_surface_resize_drag_start_state = None
        self._ice_selected = False
        self._pending_ice_state = None
        self._ice_drag_start_pos = None
        self._ice_drag_start_state = None
        self._ice_drag_basis = None
        self._ice_resize_drag_kind = None
        self._pending_widget_rect = None
        self._pending_widget_rects = {}
        self._preview_selected_widget_index = None
        self._widget_drag_start = None
        self._widget_drag_offset_unit = None
        self._widget_rotate_start_angle = None
        self._widget_rotate_start_pointer_angle = None
        self._widget_hit_cycle_key = None
        self._widget_hit_cycle_pos = 0
        self._drag_start_pos = None
        self._drag_start_puddle_state = None
        self._frame = 0
        self._preview_state = {}
        self.setMinimumSize(720, 460)
        try:
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        except Exception:
            pass
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        self._frame += 1
        self.update()

    def set_desktop_locked(self, locked):
        self._desktop_locked = bool(locked)
        self._last_mouse_pos = None
        try:
            self.update()
        except Exception:
            pass

    def is_desktop_locked(self):
        return bool(getattr(self, "_desktop_locked", False))

    def set_preview_background_theme(self, theme):
        try:
            theme = str(theme or "blue").strip().lower()
            if theme not in ("blue", "light_nvd", "white", "graphite", "black_lime"):
                theme = "blue"
            self._preview_background_theme = theme
            self.update()
        except Exception:
            pass

    def preview_background_theme(self):
        try:
            return str(getattr(self, "_preview_background_theme", "blue") or "blue")
        except Exception:
            return "blue"

    def _make_preview_background_gradient(self, rect):
        try:
            theme = self.preview_background_theme()
        except Exception:
            theme = "blue"
        bg = QLinearGradient(QPointF(0, 0), QPointF(0, rect.height()))
        if theme == "light_nvd":
            bg.setColorAt(0.0, QColor(246, 248, 250))
            bg.setColorAt(0.46, QColor(226, 232, 238))
            bg.setColorAt(1.0, QColor(198, 207, 216))
        elif theme == "white":
            bg.setColorAt(0.0, QColor(255, 255, 255))
            bg.setColorAt(0.50, QColor(242, 245, 248))
            bg.setColorAt(1.0, QColor(224, 230, 236))
        elif theme == "black_lime":
            bg.setColorAt(0.0, QColor(0, 0, 0))
            bg.setColorAt(1.0, QColor(0, 0, 0))
        elif theme == "graphite":
            bg.setColorAt(0.0, QColor(24, 26, 30))
            bg.setColorAt(0.48, QColor(42, 46, 52))
            bg.setColorAt(1.0, QColor(14, 16, 20))
        else:
            bg.setColorAt(0.0, QColor(8, 13, 28))
            bg.setColorAt(0.45, QColor(18, 31, 58))
            bg.setColorAt(1.0, QColor(7, 10, 18))
        return bg

    def _desktop_plane_palette_for_background(self):
        """Phase 24A-8g: choose desktop-plane colors to match the preview background."""
        try:
            theme = self.preview_background_theme()
        except Exception:
            theme = "blue"
        if theme in ("light_nvd", "white"):
            plane = QLinearGradient(QPointF(0, 0), QPointF(1, 1))
            plane.setColorAt(0.0, QColor(228, 232, 236, 112))
            plane.setColorAt(1.0, QColor(174, 184, 194, 72))
            return {
                "grid": QColor(92, 104, 116, 96),
                "major": QColor(76, 88, 100, 150),
                "edge": QColor(58, 68, 78, 178),
                "plane_gradient": plane,
            }
        if theme == "black_lime":
            plane = QLinearGradient(QPointF(0, 0), QPointF(1, 1))
            plane.setColorAt(0.0, QColor(118, 185, 0, 86))
            plane.setColorAt(1.0, QColor(28, 58, 0, 58))
            return {
                "grid": QColor(118, 185, 0, 118),
                "major": QColor(166, 255, 48, 178),
                "edge": QColor(184, 255, 64, 220),
                "plane_gradient": plane,
            }
        if theme == "graphite":
            plane = QLinearGradient(QPointF(0, 0), QPointF(1, 1))
            plane.setColorAt(0.0, QColor(246, 248, 250, 32))
            plane.setColorAt(1.0, QColor(118, 132, 148, 24))
            return {
                "grid": QColor(150, 164, 178, 72),
                "major": QColor(210, 216, 224, 112),
                "edge": QColor(232, 236, 242, 142),
                "plane_gradient": plane,
            }
        plane = QLinearGradient(QPointF(0, 0), QPointF(1, 1))
        plane.setColorAt(0.0, QColor(255, 255, 255, 34))
        plane.setColorAt(1.0, QColor(120, 170, 255, 18))
        return {
            "grid": QColor(142, 210, 255, 82),
            "major": QColor(255, 210, 210, 120),
            "edge": QColor(255, 246, 220, 155),
            "plane_gradient": plane,
        }

    def set_developer_mode(self, enabled):
        self._developer_mode = bool(enabled)
        try:
            self.update()
        except Exception:
            pass

    def is_developer_mode(self):
        return bool(getattr(self, "_developer_mode", False))

    def set_snap_enabled(self, enabled):
        self._snap_enabled = bool(enabled)
        self._drag_notice = "Snap ON: widget 20px / rotation 15° / effect 0.02" if self._snap_enabled else "Snap OFF"
        try:
            self.update()
        except Exception:
            pass

    def is_snap_enabled(self):
        return bool(getattr(self, "_snap_enabled", False))

    def _snap_int_value(self, value, step=20):
        try:
            if not self.is_snap_enabled():
                return int(round(float(value)))
            step = max(1, int(step))
            return int(round(float(value) / step) * step)
        except Exception:
            return int(value)

    def _snap_float_value(self, value, step=0.01):
        try:
            value = float(value)
            if not self.is_snap_enabled():
                return value
            step = max(1e-9, float(step))
            return round(value / step) * step
        except Exception:
            return value

    def initializeGL(self):
        try:
            self._gl_is_valid = True
        except Exception:
            pass

    def resizeGL(self, w, h):
        pass

    def paintGL(self):
        self._paint_preview()

    def widget_rotation_degrees(self, widget) -> float:
        try:
            cfg = getattr(widget, "cfg", None)
            return float(getattr(cfg, "rotation_degrees", getattr(cfg, "rotation", 0.0)))
        except Exception:
            return 0.0

    def paint_widget_transformed(self, painter: QPainter, widget, ctx: Dict):
        """Paint normal widgets with cfg.rotation_degrees applied around their rect center."""
        try:
            angle = self.widget_rotation_degrees(widget)
            # EffectsOverlayWidget has its own internal coordinate model and effect handles;
            # keep it unrotated for now so Sun/Moon/Puddle editing remains stable.
            if abs(angle) < 0.001 or _lds_is_effects_overlay_widget(widget):
                widget.paint(painter, ctx)
                return
            rect = widget.rect
            center = rect.center()
            painter.save()
            painter.translate(center)
            painter.rotate(angle)
            painter.translate(-center)
            widget.paint(painter, ctx)
            painter.restore()
        except Exception:
            try:
                widget.paint(painter, ctx)
            except Exception:
                pass

    def paintEvent(self, event):
        if QOpenGLWidget is None:
            self._paint_preview()
        else:
            super().paintEvent(event)

    def _show_transient_notice(self, text, msec=2600):
        """Show a lightweight non-modal notice inside the 3D preview."""
        try:
            self._transient_notice_text = str(text or "")
            self._transient_notice_until = time.time() + max(0.4, float(msec) / 1000.0)
            self._drag_notice = self._transient_notice_text
            self.update()
        except Exception:
            pass

    def _is_lock_notice_widget_target_at(self, pos):
        """Return True only for normal-widget 3D targets while Desktop Lock is OFF.

        Phase23D4A narrows the previous edit-target notification.  Effect layers
        and the pseudo desktop plane must remain free for normal view/orbit drag.
        """
        try:
            hit_widget = False
            try:
                hit_widget = bool(self._hit_widget_rect_marker(pos))
            except Exception:
                hit_widget = False
            try:
                hit_widget = bool(hit_widget or self._hit_widget_resize_handle(pos))
            except Exception:
                pass
            try:
                hit_widget = bool(hit_widget or self._hit_widget_rotation_handle(pos))
            except Exception:
                pass
            if not hit_widget:
                return False
            try:
                item = self._pick_widget_hit_candidate(pos)
            except Exception:
                item = None
            if item is None:
                try:
                    item = self._current_widget_rect_state()
                except Exception:
                    item = None
            if item is None:
                return False
            try:
                if str(dict(item).get("type", "")) == "effects_overlay":
                    return False
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _maybe_notify_lock_required_for_preview_target(self, pos):
        """Notify users that Desktop Lock is required before editing normal widgets.

        This intentionally does not consume the mouse event.  View/orbit dragging
        should continue to work even when the notice appears.
        """
        try:
            if self.is_desktop_locked():
                return False
            if not self._is_lock_notice_widget_target_at(pos):
                return False
            self._show_transient_notice(
                lds_ui_text(
                    "ウィジェットを3Dプレビューで移動・サイズ変更するには、画面固定をONにしてください。",
                    "Turn Desktop Lock ON to move or resize widgets in the 3D preview.",
                ),
                2600,
            )
            return True
        except Exception:
            return False

    def _event_global_pos(self, event):
        try:
            return event.globalPosition().toPoint()
        except Exception:
            try:
                return event.globalPos()
            except Exception:
                try:
                    return self.mapToGlobal(self._event_pos(event))
                except Exception:
                    return QPoint(0, 0)

    def _is_right_mouse_event(self, event):
        try:
            return event.button() == Qt.MouseButton.RightButton
        except Exception:
            try:
                return int(event.button()) == int(Qt.MouseButton.RightButton)
            except Exception:
                return False

    def _build_preview_state_from_canvas_owner_for_widget_delete(self, canvas):
        """Phase 24A-8c: rebuild preview widget list directly from the live canvas.

        The context-menu delete handler runs inside the Preview3D widget.  Depending
        on how the preview window/detail controller is wired, asking the controller
        for build_3d_preview_state() may fail or return stale state.  For immediate
        visual feedback after delete, rebuild the normal widget list directly from
        canvas.widgets.
        """
        state = {"selected": {}, "widgets": [], "effect": {}}
        try:
            if canvas is None:
                return state
            try:
                canvas_w = max(1, int(canvas.width()))
                canvas_h = max(1, int(canvas.height()))
            except Exception:
                canvas_w = 1920
                canvas_h = 1080
            selected_widget = getattr(canvas, "selected", None)
            common_keys = (
                "color", "bg", "text", "font_size", "cpu_color", "memory_color", "disk_color",
                "network_down_color", "network_up_color", "clock_show_digital",
                "visualizer_flip_vertical", "visualizer_peak_bar_enabled", "visualizer_glow_enabled",
                "visualizer_bar_width_scale", "visualizer_orientation", "visualizer_style", "visualizer_preset_key",
                "visualizer_shadow_enabled", "visualizer_shadow_offset_x", "visualizer_shadow_offset_y",
                "visualizer_shadow_strength", "visualizer_shadow_opacity", "visualizer_shadow_depth",
                "visualizer_shadow_blur", "visualizer_frame_rate_enabled", "visualizer_frame_rate",
            )
            for idx, widget_item in enumerate(list(getattr(canvas, "widgets", []) or [])):
                cfg = getattr(widget_item, "cfg", None)
                if cfg is None:
                    continue
                item = {
                    "index": idx,
                    "type": str(getattr(cfg, "type", "")),
                    "title": str(getattr(cfg, "title", "")),
                    "x": int(getattr(cfg, "x", 0)),
                    "y": int(getattr(cfg, "y", 0)),
                    "w": int(getattr(cfg, "w", 80)),
                    "h": int(getattr(cfg, "h", 80)),
                    "rotation": float(getattr(cfg, "rotation_degrees", getattr(cfg, "rotation", 0.0))),
                    "rotation_degrees": float(getattr(cfg, "rotation_degrees", getattr(cfg, "rotation", 0.0))),
                    "canvas_w": canvas_w,
                    "canvas_h": canvas_h,
                    "selected": bool(widget_item is selected_widget),
                }
                for key in common_keys:
                    try:
                        item[key] = getattr(cfg, key)
                    except Exception:
                        pass
                state["widgets"].append(item)
                if widget_item is selected_widget:
                    state["selected"] = dict(item)
        except Exception:
            pass
        return state

    def _select_widget_under_context_pos(self, local_pos):
        """Select the widget under a 3D context-click before showing the menu.

        Phase 19D keeps deletion target intuitive: right-clicking a widget outline
        selects that widget first, so the context menu deletes the item the user
        actually clicked rather than an older selection.
        """
        try:
            if not self.is_desktop_locked():
                return False
            item = self._pick_widget_hit_candidate(local_pos)
            if not item:
                return False
            self._clear_ice_preview_selection("")
            self._select_widget_from_preview(item)
            self._drag_notice = f"Context target selected: {str(item.get('title') or item.get('type') or item.get('index', 'widget'))}"
            return True
        except Exception:
            return False

    def _effect_context_target(self, local_pos=None):
        """Return the effect target for an Effects Overlay context-menu delete action."""
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            if str(selected.get("type", "")) != "effects_overlay":
                return None
            effect = dict(state.get("effect", {}) or {})
            if local_pos is not None:
                try:
                    template_key = self._lds_template_hit_effect_key(local_pos)
                    if template_key:
                        self._lds_template_select_effect_preview(template_key)
                        return {"kind": "__template__:" + str(template_key), "label": self._lds_template_effect_label(template_key), "template_key": str(template_key)}
                except Exception:
                    pass
                try:
                    if bool(effect.get("sun_visible", False)) and self._hit_sun_marker(local_pos):
                        return {"kind": "sun", "label": "Sun"}
                except Exception:
                    pass
                try:
                    if bool(effect.get("moon_visible", False)) and self._hit_moon_marker(local_pos):
                        return {"kind": "moon", "label": "Moon"}
                except Exception:
                    pass
                try:
                    if bool(effect.get("fireball_visible", False)) and self._hit_fireball_layer_marker(local_pos):
                        self._select_fireball_layer_preview()
                        return {"kind": "fireball", "label": "Fireball"}
                except Exception:
                    pass
                try:
                    if bool(effect.get("cloud_visible", False)) and self._hit_cloud_layer_marker(local_pos):
                        self._select_cloud_layer_preview()
                        return {"kind": "cloud", "label": "Cloud"}
                except Exception:
                    pass
                try:
                    if bool(effect.get("ice_visible", False)) and (self._ice_resize_hit_kind(local_pos) or self._hit_ice_marker(local_pos)):
                        self._select_ice_preview()
                        return {"kind": "ice", "label": "Ice"}
                except Exception:
                    pass
                try:
                    if bool(effect.get("puddle_visible", False)) and (self._hit_puddle_resize_handle(local_pos) or self._hit_puddle_marker(local_pos)):
                        hit_puddle = self._pick_puddle_hit_candidate(local_pos) or {"index": int(getattr(self, "_selected_puddle_index", 0))}
                        puddle_index = int(hit_puddle.get("index", 0))
                        self._select_puddle_preview_index(puddle_index)
                        label = "Puddle" if puddle_index == 0 else f"Puddle {puddle_index + 1}"
                        return {"kind": "puddle", "label": label, "index": puddle_index}
                except Exception:
                    pass
                try:
                    if bool(effect.get("water_surface_visible", False)) and (self._hit_water_surface_depth_resize_handle(local_pos) or self._hit_water_surface_marker(local_pos)):
                        self._select_water_surface_preview()
                        return {"kind": "water_surface", "label": "Water Surface"}
                except Exception:
                    pass
                try:
                    if bool(effect.get("bamboo_grove_visible", False)) and (self._hit_bamboo_grove_height_resize_handle(local_pos) or self._hit_bamboo_grove_marker(local_pos)):
                        self._select_bamboo_grove_preview()
                        return {"kind": "bamboo_grove", "label": "Bamboo Grove"}
                except Exception:
                    pass
            try:
                if bool(getattr(self, "_water_surface_selected", False)) and bool(effect.get("water_surface_visible", False)):
                    return {"kind": "water_surface", "label": "Water Surface"}
            except Exception:
                pass
            try:
                if bool(getattr(self, "_ice_selected", False)) and bool(effect.get("ice_visible", False)):
                    return {"kind": "ice", "label": "Ice"}
            except Exception as Err:
                pass
            try:
                if bool(getattr(self, "_bamboo_grove_selected", False)) and bool(effect.get("bamboo_grove_visible", False)):
                    return {"kind": "bamboo_grove", "label": "Bamboo Grove"}
            except Exception:
                pass
            try:
                if bool(getattr(self, "_cloud_selected", False)) and bool(effect.get("cloud_visible", False)):
                    return {"kind": "cloud", "label": "Cloud"}
            except Exception:
                pass
            try:
                if bool(getattr(self, "_fireball_selected", False)) and bool(effect.get("fireball_visible", False)):
                    return {"kind": "fireball", "label": "Fireball"}
            except Exception:
                pass
            try:
                template_key = str(getattr(self, "_template_effect_selected_key", "") or "")
                if template_key:
                    tstate = self._lds_template_effect_state(template_key) or {}
                    if bool(dict(tstate or {}).get("visible", False)):
                        return {"kind": "__template__:" + template_key, "label": self._lds_template_effect_label(template_key), "template_key": template_key}
            except Exception:
                pass
            return None
        except Exception:
            return None

    def _clear_effect_context_selection_after_disable(self, kind):
        try:
            kind = str(kind or "")
            if kind == "water_surface":
                self._water_surface_selected = False
                self._pending_water_surface_state = None
                self._water_surface_drag_start_pos = None
                self._water_surface_drag_start_state = None
                self._water_surface_resize_drag_start_pos = None
                self._water_surface_resize_drag_start_state = None
            elif kind == "ice":
                self._clear_ice_preview_selection("")
                self._pending_ice_state = None
            elif kind == "puddle":
                self._pending_puddle_state = None
                self._pending_puddle_states = {}
                self._selected_puddle_index = 0
            elif kind in ("bamboo_grove", "bamboo", "bamboo_grove_marker"):
                self._bamboo_grove_selected = False
                self._pending_bamboo_grove_state = None
                self._bamboo_grove_resize_drag_start_pos = None
                self._bamboo_grove_resize_drag_start_state = None
            elif kind in ("cloud", "cloud_layer", "cloud_marker"):
                self._cloud_selected = False
            elif kind in ("fireball", "fireball_layer", "fireball_marker"):
                self._fireball_selected = False
            elif kind.startswith("__template__:"):
                self._template_effect_selected_key = None
                self._pending_template_effect_states = dict(getattr(self, "_pending_template_effect_states", {}) or {})
            elif kind in ("sun", "moon"):
                if kind == "sun":
                    self._pending_sun_unit = None
                else:
                    self._pending_moon_unit = None
            self._drag_kind = None
            self.update()
        except Exception:
            pass

    def _sync_canvas_selection_to_preview_widget_for_context_delete(self, canvas, selected):
        """Phase 24A-8e: ensure normal-widget delete targets the preview-selected widget.

        The Preview3D context menu can show a normal-widget target while canvas.selected
        still points to an Effects Overlay.  Calling canvas.delete_selected_widget()
        in that state deletes the overlay instead of the widget shown in the menu.
        """
        try:
            if canvas is None:
                return False
            selected = dict(selected or {})
            selected_type = str(selected.get("type", ""))
            if not selected or selected_type == "effects_overlay":
                return False
            index = int(selected.get("index", -1))
            widgets = list(getattr(canvas, "widgets", []) or [])
            if index < 0 or index >= len(widgets):
                return False
            target = widgets[index]
            target_cfg = getattr(target, "cfg", None)
            if target_cfg is None or str(getattr(target_cfg, "type", "")) == "effects_overlay":
                return False
            # If the preview state says this is e.g. weather/network/system, avoid
            # deleting a different widget type at the same index after stale state.
            if selected_type and str(getattr(target_cfg, "type", "")) != selected_type:
                return False
            for widget_item in widgets:
                try:
                    widget_item.selected = False
                except Exception:
                    pass
            canvas.selected = target
            try:
                target.selected = True
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _show_3d_context_menu(self, local_pos, global_pos=None):
        try:
            # Phase 19A skeleton: show this menu only when the pseudo desktop is
            # locked for editing and the right-click is actually on the pseudo desktop.
            if not self.is_desktop_locked() or not self._is_pos_on_desktop_plane(local_pos):
                return False

            # First resolve an effect target from the current preview state.  Do this
            # before selecting a normal widget under the cursor; otherwise a right-click
            # on an Effects Overlay marker can be stolen by a widget footprint behind it.
            state = dict(getattr(self, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            is_layer_effect_selected = bool(
                getattr(self, "_water_surface_selected", False)
                or getattr(self, "_ice_selected", False)
                or getattr(self, "_bamboo_grove_selected", False)
                or getattr(self, "_cloud_selected", False)
                or getattr(self, "_fireball_selected", False)
            )
            is_effect_overlay_target = str(selected.get("type", "")) == "effects_overlay" or is_layer_effect_selected
            effect_context_target = self._effect_context_target(local_pos) if is_effect_overlay_target else None
            if effect_context_target is None:
                try:
                    self._select_widget_under_context_pos(local_pos)
                except Exception:
                    pass
                state = dict(getattr(self, "_preview_state", {}) or {})
                selected = dict(state.get("selected", {}) or {})
                is_layer_effect_selected = bool(
                    getattr(self, "_water_surface_selected", False)
                    or getattr(self, "_ice_selected", False)
                    or getattr(self, "_bamboo_grove_selected", False)
                    or getattr(self, "_cloud_selected", False)
                    or getattr(self, "_fireball_selected", False)
                )
                is_effect_overlay_target = str(selected.get("type", "")) == "effects_overlay" or is_layer_effect_selected
                effect_context_target = self._effect_context_target(local_pos) if is_effect_overlay_target else None
            selected_label = str(selected.get("title") or selected.get("type") or "None") if selected else "None"

            menu = QMenu(self)
            title_action = menu.addAction(lds_tr(f"対象: {selected_label}"))
            try:
                title_action.setEnabled(False)
            except Exception:
                pass
            menu.addSeparator()

            if is_effect_overlay_target:
                target_label = str(dict(effect_context_target or {}).get("label", ""))
                delete_action = menu.addAction(lds_tr(f"選択エフェクトをオフ" + (f" ({target_label})" if target_label else "")))
            else:
                delete_action = menu.addAction(lds_tr("ウィジェットを削除"))
            duplicate_action = menu.addAction(lds_tr("ウィジェットを複製"))
            menu.addSeparator()
            undo_action = menu.addAction(lds_tr("元に戻す"))
            redo_action = menu.addAction(lds_tr("やり直し"))

            canvas = None
            main_window = None
            preview_window = None
            try:
                preview_window = self.parent()
                if preview_window is not None and hasattr(preview_window, "_canvas_owner"):
                    canvas = preview_window._canvas_owner()
                if canvas is None:
                    parent_obj = preview_window.parent() if preview_window is not None else None
                    if parent_obj is not None and hasattr(parent_obj, "widgets") and hasattr(parent_obj, "save_config"):
                        canvas = parent_obj
                    else:
                        canvas = getattr(parent_obj, "canvas", None)
                try:
                    if preview_window is not None and hasattr(preview_window, "_controller"):
                        main_window = preview_window._controller()
                except Exception:
                    main_window = None
                if main_window is None:
                    parent_obj = preview_window.parent() if preview_window is not None else None
                    if parent_obj is not None and hasattr(parent_obj, "load_selected_to_editor"):
                        main_window = parent_obj
            except Exception:
                canvas = None
            try:
                has_effect_overlay_widget = False
                if is_effect_overlay_target and canvas is not None:
                    try:
                        selected_index = int(selected.get("index", -1))
                    except Exception:
                        selected_index = -1
                    try:
                        current_cfg = getattr(getattr(canvas, "selected", None), "cfg", None)
                        if str(getattr(current_cfg, "type", "")) != "effects_overlay":
                            widgets = list(getattr(canvas, "widgets", []) or [])
                            if selected_index >= 0 and 0 <= selected_index < len(widgets):
                                candidate = widgets[selected_index]
                                candidate_cfg = getattr(candidate, "cfg", None)
                                if str(getattr(candidate_cfg, "type", "")) == "effects_overlay":
                                    canvas.selected = candidate
                            current_cfg = getattr(getattr(canvas, "selected", None), "cfg", None)
                            if str(getattr(current_cfg, "type", "")) != "effects_overlay":
                                for candidate in widgets:
                                    candidate_cfg = getattr(candidate, "cfg", None)
                                    if str(getattr(candidate_cfg, "type", "")) == "effects_overlay":
                                        canvas.selected = candidate
                                        current_cfg = candidate_cfg
                                        break
                        has_effect_overlay_widget = str(getattr(current_cfg, "type", "")) == "effects_overlay"
                    except Exception:
                        has_effect_overlay_widget = False
                try:
                    selected_index_for_widget = int(selected.get("index", -1))
                except Exception:
                    selected_index_for_widget = -1
                normal_target_synced = False
                if not is_effect_overlay_target:
                    normal_target_synced = bool(self._sync_canvas_selection_to_preview_widget_for_context_delete(canvas, selected))
                current_selected_cfg = getattr(getattr(canvas, "selected", None), "cfg", None) if canvas is not None else None
                has_selected_widget = bool(
                    canvas is not None
                    and getattr(canvas, "selected", None) is not None
                    and selected_index_for_widget >= 0
                    and normal_target_synced
                    and str(getattr(current_selected_cfg, "type", "")) != "effects_overlay"
                )
                if is_effect_overlay_target:
                    try:
                        target_kind_for_enable = str(dict(effect_context_target or {}).get("kind", ""))
                    except Exception:
                        target_kind_for_enable = ""
                    delete_action.setEnabled(bool(has_effect_overlay_widget and effect_context_target is not None and (hasattr(canvas, "disable_selected_effect_overlay_effect") or target_kind_for_enable.startswith("__template__:"))))
                    duplicate_action.setEnabled(False)
                else:
                    delete_action.setEnabled(has_selected_widget)
                    duplicate_action.setEnabled(has_selected_widget)
            except Exception:
                try:
                    delete_action.setEnabled(False)
                except Exception:
                    pass
                try:
                    duplicate_action.setEnabled(False)
                except Exception:
                    pass
            # Phase23D3C: When this context menu is for a selected effect layer
            # (Fireball/Cloud/etc.), do not advertise canvas undo/redo here.
            # Effect OFF is persisted through the effect-overlay settings path and
            # the existing canvas undo/redo actions may appear enabled but no-op,
            # which feels inconsistent. Keep undo/redo available for normal widget
            # context menus only.
            if is_effect_overlay_target:
                try:
                    undo_action.setEnabled(False)
                except Exception:
                    pass
                try:
                    redo_action.setEnabled(False)
                except Exception:
                    pass
            else:
                try:
                    undo_action.setEnabled(bool(canvas is not None and canvas.can_undo()))
                except Exception:
                    undo_action.setEnabled(False)
                try:
                    redo_action.setEnabled(bool(canvas is not None and canvas.can_redo()))
                except Exception:
                    redo_action.setEnabled(False)

            if global_pos is None:
                try:
                    global_pos = self.mapToGlobal(local_pos)
                except Exception:
                    global_pos = QPoint(0, 0)
            chosen = menu.exec(global_pos)
            try:
                if chosen == delete_action and canvas is not None and getattr(canvas, "selected", None) is not None:
                    if is_effect_overlay_target and effect_context_target is not None and hasattr(canvas, "disable_selected_effect_overlay_effect"):
                        effect_context_target = dict(effect_context_target or {})
                        effect_label = str(effect_context_target.get("label") or effect_context_target.get("kind") or lds_tr("選択エフェクト"))
                        confirm = QMessageBox.question(
                            self,
                            lds_tr("3Dプレビュー"),
                            lds_tr(f"選択中のエフェクトをオフにしますか？\n{effect_label}\n\nエフェクトオーバーレイ自体は削除されません。"),
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No,
                        )
                        if confirm == QMessageBox.StandardButton.Yes:
                            target_kind = str(effect_context_target.get("kind") or "")
                            if target_kind.startswith("__template__:"):
                                template_key = str(effect_context_target.get("template_key") or target_kind.split(":", 1)[1])
                                disabled = bool(self._disable_template_effect_preview_pending(template_key))
                            else:
                                disabled = bool(canvas.disable_selected_effect_overlay_effect(
                                    effect_context_target.get("kind"),
                                    effect_context_target.get("index", None),
                                ))
                            if not disabled:
                                try:
                                    selected_cfg = getattr(getattr(canvas, "selected", None), "cfg", None)
                                    self._drag_notice = "Effect disable failed: canvas selected type=" + str(getattr(selected_cfg, "type", None))
                                    self.update()
                                except Exception:
                                    pass
                            if disabled:
                                self._drag_notice = f"Effect disabled: {effect_label} / undo available"
                                self._clear_effect_context_selection_after_disable(effect_context_target.get("kind"))
                                try:
                                    kind = str(effect_context_target.get("kind") or "")
                                    state = dict(getattr(self, "_preview_state", {}) or {})
                                    effect = dict(state.get("effect", {}) or {})
                                    if kind == "water_surface":
                                        effect["water_surface_visible"] = False
                                    elif kind == "ice":
                                        effect["ice_visible"] = False
                                    elif kind == "puddle":
                                        effect["puddle_visible"] = False
                                        effect["puddles"] = []
                                    elif kind in ("bamboo_grove", "bamboo", "bamboo_grove_marker"):
                                        effect["bamboo_grove_visible"] = False
                                    elif kind in ("cloud", "cloud_layer", "cloud_marker"):
                                        effect["cloud_visible"] = False
                                    elif kind in ("fireball", "fireball_layer", "fireball_marker"):
                                        effect["fireball_visible"] = False
                                    elif kind == "sun":
                                        effect["sun_visible"] = False
                                    elif kind == "moon":
                                        effect["moon_visible"] = False
                                    elif kind.startswith("__template__:"):
                                        template_key = str(effect_context_target.get("template_key") or kind.split(":", 1)[1])
                                        effect[f"{template_key}_visible"] = False
                                        try:
                                            spec = self._lds_template_effect_spec(template_key) or {}
                                            effect[str(dict(spec or {}).get("enabled_key") or f"{template_key}_enabled")] = False
                                        except Exception:
                                            pass
                                    state["effect"] = effect
                                    self._preview_state = state
                                    self.update()
                                except Exception:
                                    pass
                                self._pending_widget_rect = None
                                if main_window is not None and hasattr(main_window, "load_selected_to_editor"):
                                    main_window.load_selected_to_editor()
                                if main_window is not None and hasattr(main_window, "sync_3d_preview_test_window"):
                                    main_window.sync_3d_preview_test_window()
                    else:
                        if not self._sync_canvas_selection_to_preview_widget_for_context_delete(canvas, selected):
                            try:
                                self._drag_notice = "Delete canceled: preview target and canvas selection did not match"
                                self.update()
                            except Exception:
                                pass
                            return True
                        target_label = str(selected_label or lds_tr("選択中ウィジェット"))
                        confirm = QMessageBox.question(
                            self,
                            lds_tr("3Dプレビュー"),
                            lds_tr(f"選択中のウィジェットを削除しますか？\n{target_label}\n\n削除後は右クリックメニューの『元に戻す』で戻せます。"),
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No,
                        )
                        if confirm == QMessageBox.StandardButton.Yes:
                            canvas.delete_selected_widget()
                            self._drag_notice = "Widget deleted / undo available"
                            # Phase 24A-8b: deleting a normal widget from the 3D preview must
                            # not leave stale normal-widget pending maps or replace preview
                            # state with an empty widgets list.  The previous empty-state
                            # assignment made all non-target widgets disappear from the 3D
                            # preview until a later full rebuild.
                            try:
                                self._pending_widget_rect = None
                                self._pending_widget_rects = {}
                                self._preview_selected_widget_index = -1
                            except Exception:
                                pass
                            refreshed_state = None
                            # Rebuild immediately from the canvas that was actually mutated.
                            # This avoids waiting for Apply or for a later controller sync.
                            try:
                                refreshed_state = self._build_preview_state_from_canvas_owner_for_widget_delete(canvas)
                            except Exception:
                                refreshed_state = None
                            if not dict(refreshed_state or {}).get("widgets") and main_window is not None and hasattr(main_window, "build_3d_preview_state"):
                                try:
                                    refreshed_state = main_window.build_3d_preview_state()
                                except Exception:
                                    pass
                            if refreshed_state is not None:
                                try:
                                    self.set_preview_state(refreshed_state)
                                except Exception:
                                    pass
                            if main_window is not None and hasattr(main_window, "refresh_layer_list"):
                                try:
                                    main_window.refresh_layer_list()
                                except Exception:
                                    pass
                            if main_window is not None and hasattr(main_window, "load_selected_to_editor"):
                                main_window.load_selected_to_editor()
                            if refreshed_state is None and main_window is not None and hasattr(main_window, "sync_3d_preview_test_window"):
                                main_window.sync_3d_preview_test_window()
                            try:
                                self.update()
                            except Exception:
                                pass
                elif chosen == duplicate_action and canvas is not None and getattr(canvas, "selected", None) is not None:
                    canvas.duplicate_selected_widget()
                    self._drag_notice = "Widget duplicated / undo available"
                    self._pending_widget_rect = None
                    if main_window is not None and hasattr(main_window, "load_selected_to_editor"):
                        main_window.load_selected_to_editor()
                    if main_window is not None and hasattr(main_window, "sync_3d_preview_test_window"):
                        main_window.sync_3d_preview_test_window()
                elif chosen == undo_action and canvas is not None:
                    if canvas.undo_last_change():
                        self._drag_notice = "Undo applied"
                        if main_window is not None and hasattr(main_window, "load_selected_to_editor"):
                            main_window.load_selected_to_editor()
                        if main_window is not None and hasattr(main_window, "sync_3d_preview_test_window"):
                            main_window.sync_3d_preview_test_window()
                elif chosen == redo_action and canvas is not None:
                    if canvas.redo_last_change():
                        self._drag_notice = "Redo applied"
                        if main_window is not None and hasattr(main_window, "load_selected_to_editor"):
                            main_window.load_selected_to_editor()
                        if main_window is not None and hasattr(main_window, "sync_3d_preview_test_window"):
                            main_window.sync_3d_preview_test_window()
                self.update()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def contextMenuEvent(self, event):
        try:
            shown = self._show_3d_context_menu(self._event_pos(event), self._event_global_pos(event))
            try:
                event.accept() if shown else event.ignore()
            except Exception:
                pass
        except Exception:
            try:
                event.ignore()
            except Exception:
                pass


    def _is_normal_litedesktop_widget_at(self, pos):
        try:
            widget = self.widget_at_pos(pos)
            if widget is None:
                return None
            if _lds_is_effects_overlay_widget(widget):
                return None
            return widget
        except Exception:
            return None

    def _ensure_right_double_click_catcher(self):
        try:
            catcher = getattr(self, "_right_double_click_catcher", None)
            if catcher is None:
                catcher = LDSRightDoubleClickCatcher(self)
                self._right_double_click_catcher = catcher
            return catcher
        except Exception as e:
            try: print("[LiteDesktopStudio] ensure right double-click catcher failed:", repr(e))
            except Exception: pass
            return None

    def _arm_first_right_double_click_catcher(self, pos):
        try:
            if not is_windows():
                return False
            if bool(getattr(self, "_first_right_double_click_catcher_used", False)):
                return False
            if self._is_normal_litedesktop_widget_at(pos) is None:
                return False
            catcher = self._ensure_right_double_click_catcher()
            if catcher is None:
                return False
            self._first_right_double_click_catcher_used = True
            self._right_double_click_catcher_active = True
            return bool(catcher.arm(pos, 450))
        except Exception as e:
            try: print("[LiteDesktopStudio] arm first right double-click catcher failed:", repr(e))
            except Exception: pass
            return False

    def mousePressEvent(self, event):
        pos = self._event_pos(event)
        if self._is_right_mouse_event(event):
            self._last_mouse_pos = None
            self._drag_kind = None
            shown = self._show_3d_context_menu(pos, self._event_global_pos(event))
            try:
                event.accept() if shown else event.ignore()
            except Exception:
                pass
            return
        if not self.is_desktop_locked():
            self._maybe_notify_lock_required_for_preview_target(pos)
        self._last_mouse_pos = pos
        self._drag_kind = None
        if self.is_desktop_locked() and self._hit_sun_marker(pos):
            self._preview_selection_suppressed = False
            self._drag_kind = "sun"
            sx, sy, _visible = self._current_sun_unit()
            self._drag_notice = f"Sun drag started x={sx:.3f} y={sy:.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_moon_marker(pos):
            self._preview_selection_suppressed = False
            self._drag_kind = "moon"
            mx, my, _visible = self._current_moon_unit()
            self._drag_notice = f"Moon drag started x={mx:.3f} y={my:.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_fireball_layer_marker(pos):
            self._preview_selection_suppressed = True
            self._select_fireball_layer_preview()
            self._drag_kind = "fireball_move"
            self._begin_fireball_layer_move_drag(pos)
            state = self._current_fireball_layer_state()
            self._drag_notice = f"Fireball move started x={float(state.get('x', 0.50)):.2f} y={float(state.get('y', 0.38)):.2f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_cloud_layer_resize_handle(pos):
            self._preview_selection_suppressed = True
            self._select_cloud_layer_preview()
            self._drag_kind = "cloud_resize"
            self._begin_cloud_layer_resize_drag(pos)
            state = self._current_cloud_layer_state()
            self._drag_notice = f"Cloud resize started size={float(state.get('size', 92.0)):.1f} depth={float(state.get('depth', 0.42)):.2f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_cloud_layer_marker(pos):
            self._preview_selection_suppressed = True
            self._select_cloud_layer_preview()
            self._drag_kind = "cloud_move"
            self._begin_cloud_layer_move_drag(pos)
            state = self._current_cloud_layer_state()
            self._drag_notice = f"Cloud move started altitude={float(state.get('altitude', 0.22)):.2f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._ice_resize_hit_kind(pos):
            self._preview_selection_suppressed = False
            self._select_ice_preview()
            self._drag_kind = "ice_resize"
            ice_resize_kind = self._ice_resize_hit_kind(pos) or "bottom_right"
            self._begin_ice_resize_drag(pos, ice_resize_kind)
            ice = self._current_ice_state()
            self._drag_notice = f"Ice {ice_resize_kind} resize started width={ice.get('width', 1.0):.3f} depth={ice.get('depth', 0.42):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_ice_marker(pos):
            self._preview_selection_suppressed = False
            self._select_ice_preview()
            self._drag_kind = "ice"
            self._begin_ice_move_drag(pos)
            ice = self._current_ice_state()
            self._drag_notice = f"Ice move started x={ice.get('x', 0.50):.3f} y={ice.get('y', 0.58):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_puddle_resize_handle(pos):
            self._preview_selection_suppressed = False
            self._clear_ice_preview_selection("")
            self._drag_kind = "puddle_resize"
            puddle = self._current_puddle_state()
            self._begin_puddle_resize_drag(pos)
            self._drag_notice = f"Puddle resize started width={puddle.get('width', 0.20):.3f} height={puddle.get('height', 0.08):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_puddle_marker(pos):
            self._preview_selection_suppressed = False
            hit_puddle = self._pick_puddle_hit_candidate(pos) or {"index": 0}
            puddle_index = int(hit_puddle.get("index", 0))
            self._select_puddle_preview_index(puddle_index)
            self._drag_kind = "puddle"
            puddle = self._current_selected_puddle_state()
            self._drag_notice = f"Puddle {puddle_index + 1} move started x={puddle.get('x', 0.5):.3f} y={puddle.get('y', 0.84):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_water_surface_depth_resize_handle(pos):
            self._preview_selection_suppressed = False
            self._select_water_surface_preview()
            self._drag_kind = "water_surface_resize"
            self._begin_water_surface_depth_resize_drag(pos)
            water = self._current_water_surface_state()
            self._drag_notice = f"Water Surface depth resize started y={water.get('y', 0.58):.3f} depth={water.get('depth', 0.42):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_water_surface_marker(pos):
            self._preview_selection_suppressed = False
            self._select_water_surface_preview()
            self._drag_kind = "water_surface"
            self._begin_water_surface_move_drag(pos)
            water = self._current_water_surface_state()
            self._drag_notice = f"Water Surface move started y={water.get('y', 0.58):.3f} depth={water.get('depth', 0.42):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_bamboo_grove_height_resize_handle(pos):
            self._preview_selection_suppressed = False
            self._select_bamboo_grove_preview()
            self._drag_kind = "bamboo_grove_resize"
            self._begin_bamboo_grove_height_resize_drag(pos)
            state = self._current_bamboo_grove_state()
            self._drag_notice = f"Bamboo Grove height resize started height={float(state.get('height', 0.92)):.3f}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_bamboo_grove_marker(pos):
            self._preview_selection_suppressed = False
            self._select_bamboo_grove_preview()
            self._drag_kind = None
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._lds_template_hit_effect_key(pos):
            self._preview_selection_suppressed = True
            template_key = self._lds_template_hit_effect_key(pos)
            self._lds_template_select_effect_preview(template_key)
            template_spec = self._lds_template_effect_spec(template_key) or {}
            if bool(template_spec.get("supports_move", False)):
                self._drag_kind = "template_effect_move"
                self._lds_template_begin_move_drag(template_key, pos)
            else:
                self._drag_kind = None
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and bool(getattr(self, "_ice_selected", False)):
            # Phase 20B3: while Ice is selected, any plain left-click that did not
            # hit Sun/Moon/Ice/Puddle above should only clear Ice selection.  Do
            # not require _is_pos_on_desktop_plane(pos), because that projected
            # plane hit-test can miss near edges or after camera changes; if it
            # misses, the click falls through to widget-footprint hit cycling and
            # unrelated widgets appear/select one after another.
            self._preview_selection_suppressed = True
            self._drag_kind = None
            self._last_mouse_pos = None
            self._clear_ice_preview_selection("Ice selection cleared")
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and bool(getattr(self, "_water_surface_selected", False)):
            # While Water Surface is selected, a plain left-click that did not hit
            # Sun/Moon/Ice/Puddle/Water Surface above should only clear the Water
            # Surface selection.  This mirrors the Ice selection guard and avoids
            # accidental fall-through into normal widget hit cycling.
            self._preview_selection_suppressed = True
            self._drag_kind = None
            self._last_mouse_pos = None
            self._clear_water_surface_preview_selection("Water Surface selection cleared")
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_widget_rotation_handle(pos):
            self._preview_selection_suppressed = False
            self._drag_kind = "widget_rotate"
            self._begin_widget_rotate_drag(pos)
            widget = self._current_widget_rect_state()
            self._drag_notice = f"Widget rotation started angle={float(widget.get('rotation', 0.0)):.1f}°"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_widget_resize_handle(pos):
            self._preview_selection_suppressed = False
            self._drag_kind = "widget_resize"
            self._begin_widget_resize_drag(pos)
            widget = self._current_widget_rect_state()
            self._drag_notice = f"Widget resize started rotated-aware w={widget.get('w', '-')} h={widget.get('h', '-')}"
            try:
                event.accept()
            except Exception:
                pass
        elif self.is_desktop_locked() and self._hit_widget_rect_marker(pos):
            self._preview_selection_suppressed = False
            widget = self._pick_widget_hit_candidate(pos)
            if widget:
                self._select_widget_from_preview(widget)
                try:
                    self._notify_integrated_selection_bar_changed()
                except Exception:
                    pass
            if widget and str(dict(widget).get("type", "")) == "effects_overlay":
                # Effects Overlay is the entry point for Sun/Moon/Ice/Puddle editing.
                # Do not immediately treat the full-screen overlay as a movable widget;
                # otherwise a click intended to reveal effect handles can be consumed as
                # a widget-move drag while pending normal-widget edits suppress timer sync.
                self._drag_kind = None
                self._last_mouse_pos = None
                self._drag_notice = "Effects Overlay selected / effect handles enabled"
                try:
                    event.accept()
                except Exception:
                    pass
                self.update()
                return
            self._drag_kind = "widget_move"
            self._begin_widget_move_drag(pos)
            widget = self._current_widget_rect_state()
            self._drag_notice = f"Widget move started index={widget.get('index', '-')} x={widget.get('x', '-')} y={widget.get('y', '-')}"
            try:
                event.accept()
            except Exception:
                pass

    def mouseMoveEvent(self, event):
        if self._last_mouse_pos is None:
            return
        try:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                self._last_mouse_pos = None
                self._drag_kind = None
                return
        except Exception:
            pass
        pos = self._event_pos(event)
        if self.is_desktop_locked():
            if getattr(self, "_drag_kind", None) == "sun":
                sx, sy, _visible = self._current_sun_unit()
                nx, ny = self._screen_to_unit_on_desktop(pos, sx, sy)
                self._set_temp_sun_unit(nx, ny)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "moon":
                mx, my, _visible = self._current_moon_unit()
                nx, ny = self._screen_to_unit_on_desktop(pos, mx, my)
                self._set_temp_moon_unit(nx, ny)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "ice_resize":
                self._set_temp_ice_size_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "ice":
                self._set_temp_ice_unit_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "puddle":
                puddle = self._current_puddle_state()
                nx, ny = self._screen_to_unit_on_desktop(pos, puddle.get("x", 0.50), puddle.get("y", 0.84))
                self._set_temp_puddle_unit(nx, ny)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "puddle_resize":
                self._set_temp_puddle_size_from_screen_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "water_surface":
                self._set_temp_water_surface_y_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "water_surface_resize":
                self._set_temp_water_surface_depth_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "bamboo_grove_resize":
                self._set_temp_bamboo_grove_height_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "fireball_move":
                self._set_temp_fireball_layer_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "cloud_move":
                self._set_temp_cloud_layer_altitude_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "cloud_resize":
                self._set_temp_cloud_layer_size_from_drag_delta(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "template_effect_move":
                self._lds_template_set_temp_from_pos(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "widget_move":
                self._set_temp_widget_rect_from_pos(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "widget_resize":
                self._set_temp_widget_size_from_pos(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            elif getattr(self, "_drag_kind", None) == "widget_rotate":
                self._set_temp_widget_rotation_from_pos(pos)
                try:
                    event.accept()
                except Exception:
                    pass
            self._last_mouse_pos = pos
            return
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        try:
            orbit_ref_pos = QPointF(
                (float(pos.x()) + float(self._last_mouse_pos.x())) * 0.5,
                (float(pos.y()) + float(self._last_mouse_pos.y())) * 0.5,
            )
        except Exception:
            orbit_ref_pos = pos
        self._last_mouse_pos = pos
        # Phase23D4B: split horizontal orbit direction by the projected desktop
        # center.  D4A's single '-' sign made the lower half feel natural but the
        # upper half mirrored; the upper half keeps the old sign while the lower
        # half keeps the D4A sign.
        self._yaw += float(dx) * 0.45 * self._desktop_orbit_horizontal_sign(orbit_ref_pos)
        # Natural vertical drag: moving the mouse upward should move/tilt the pseudo
        # desktop upward on screen, not downward.  The previous sign used Qt's raw
        # screen-y direction directly, which felt inverted for direct manipulation.
        self._pitch = max(18.0, min(78.0, self._pitch - float(dy) * 0.30))
        self.update()

    def mouseReleaseEvent(self, event):
        if getattr(self, "_drag_kind", None) == "sun":
            sx, sy, _visible = self._current_sun_unit()
            self._drag_notice = f"Sun preview-only released x={sx:.3f} y={sy:.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "moon":
            mx, my, _visible = self._current_moon_unit()
            self._drag_notice = f"Moon preview-only released x={mx:.3f} y={my:.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "ice":
            ice = self._current_ice_state()
            self._drag_notice = f"Ice preview-only released x={ice.get('x', 0.50):.3f} y={ice.get('y', 0.58):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "ice_resize":
            ice = self._current_ice_state()
            self._drag_notice = f"Ice resize released width={ice.get('width', 1.0):.3f} depth={ice.get('depth', 0.42):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "puddle":
            puddle = self._current_puddle_state()
            self._drag_notice = f"Puddle preview-only released x={puddle.get('x', 0.50):.3f} y={puddle.get('y', 0.84):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "puddle_resize":
            puddle = self._current_puddle_state()
            self._drag_notice = f"Puddle resize released width={puddle.get('width', 0.20):.3f} height={puddle.get('height', 0.08):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "water_surface":
            water = self._current_water_surface_state()
            self._drag_notice = f"Water Surface move released y={water.get('y', 0.58):.3f} depth={water.get('depth', 0.42):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "water_surface_resize":
            water = self._current_water_surface_state()
            self._drag_notice = f"Water Surface depth resize released y={water.get('y', 0.58):.3f} depth={water.get('depth', 0.42):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "bamboo_grove_resize":
            state = self._current_bamboo_grove_state()
            self._drag_notice = f"Bamboo Grove height resize released height={float(state.get('height', 0.92)):.3f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "fireball_move":
            state = self._current_fireball_layer_state()
            self._drag_notice = f"Fireball move released x={float(state.get('x', 0.50)):.2f} y={float(state.get('y', 0.38)):.2f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "cloud_move":
            state = self._current_cloud_layer_state()
            self._drag_notice = f"Cloud move released altitude={float(state.get('altitude', 0.22)):.2f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "cloud_resize":
            state = self._current_cloud_layer_state()
            self._drag_notice = f"Cloud resize released size={float(state.get('size', 92.0)):.1f} depth={float(state.get('depth', 0.42)):.2f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "template_effect_move":
            key = str(getattr(self, "_template_effect_selected_key", "") or "")
            spec = self._lds_template_effect_spec(key) or {}
            state = self._lds_template_effect_state(key)
            self._drag_notice = f"{spec.get('display_name', key)} move released x={float(state.get('x', 0.5)):.2f} y={float(state.get('y', 0.5)):.2f} / pending apply"
        elif getattr(self, "_drag_kind", None) == "widget_move":
            widget = self._current_widget_rect_state()
            self._drag_notice = f"Widget move released x={widget.get('x', '-')} y={widget.get('y', '-')} / pending apply"
        elif getattr(self, "_drag_kind", None) == "widget_resize":
            widget = self._current_widget_rect_state()
            self._drag_notice = f"Widget resize released w={widget.get('w', '-')} h={widget.get('h', '-')} / pending apply"
        elif getattr(self, "_drag_kind", None) == "widget_rotate":
            widget = self._current_widget_rect_state()
            self._drag_notice = f"Widget rotation released angle={float(widget.get('rotation', 0.0)):.1f}° / pending apply"
        self._drag_kind = None
        self._widget_drag_start = None
        self._widget_drag_offset_unit = None
        self._widget_drag_start_pos = None
        self._widget_drag_jacobian = None
        self._widget_rotate_center = None
        self._widget_rotate_start_angle = None
        self._widget_rotate_start_pointer_angle = None
        self._drag_start_pos = None
        self._drag_start_puddle_state = None
        self._water_surface_drag_start_pos = None
        self._water_surface_drag_start_state = None
        self._water_surface_resize_drag_start_pos = None
        self._water_surface_resize_drag_start_state = None
        self._bamboo_grove_resize_drag_start_pos = None
        self._bamboo_grove_resize_drag_start_state = None
        self._cloud_drag_start_pos = None
        self._cloud_drag_start_state = None
        self._cloud_resize_drag_start_pos = None
        self._cloud_resize_drag_start_state = None
        self._ice_drag_start_pos = None
        self._ice_drag_start_state = None
        self._ice_drag_basis = None
        self._ice_resize_drag_kind = None
        self._last_mouse_pos = None

    def wheelEvent(self, event):
        if self.is_desktop_locked():
            try:
                event.accept()
            except Exception:
                pass
            return
        try:
            delta = event.angleDelta().y()
        except Exception:
            delta = 0
        if delta > 0:
            self._zoom = min(1.80, self._zoom * 1.08)
        elif delta < 0:
            self._zoom = max(0.55, self._zoom / 1.08)
        self.update()

    def _desktop_orbit_horizontal_sign(self, pos):
        """Return horizontal orbit sign for direct manipulation of the pseudo desktop.

        Phase23D4B: a single global sign fixed the lower projected half but made
        the upper half feel mirrored.  Split by the projected desktop center so
        dragging the visible upper half and lower half both follow the hand.
        """
        try:
            center, _scale = self._project_point(0.0, 0.0, 0.0)
            py = float(pos.y())
            cy = float(center.y())
            return 1.0 if py < cy else -1.0
        except Exception:
            return -1.0

    def _project_point(self, x, y, z):
        import math as _math
        yaw = _math.radians(float(self._yaw))
        pitch = _math.radians(float(self._pitch))
        cy = _math.cos(yaw)
        sy = _math.sin(yaw)
        cp = _math.cos(pitch)
        sp = _math.sin(pitch)
        x1 = x * cy - z * sy
        z1 = x * sy + z * cy
        y1 = y * cp - z1 * sp
        z2 = y * sp + z1 * cp
        distance = 900.0
        focal = 760.0 * float(self._zoom)
        scale = focal / max(120.0, distance + z2)
        sx = self.width() * 0.5 + x1 * scale
        sy2 = self.height() * 0.56 - y1 * scale
        return QPointF(sx, sy2), scale

    def _paint_preview(self):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            try:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            except Exception:
                pass
            rect = QRectF(0, 0, max(1, self.width()), max(1, self.height()))
            bg = self._make_preview_background_gradient(rect)
            painter.fillRect(rect, QBrush(bg))
            self._draw_desktop_plane(painter)
            self._draw_preview_objects(painter)
            self._draw_fault_structure_panel(painter)
            self._draw_transient_notice(painter)
            self._draw_overlay_text(painter)
        finally:
            painter.end()

    def _draw_line_3d(self, painter, a, b, color, width=1.0):
        p1, s1 = self._project_point(*a)
        p2, s2 = self._project_point(*b)
        alpha = max(30, min(220, int(color.alpha() * max(0.35, min(1.0, (s1 + s2) * 0.75)))))
        c = QColor(color)
        c.setAlpha(alpha)
        painter.setPen(QPen(c, max(1.0, float(width))))
        painter.drawLine(p1, p2)

    def _desktop_plane_path(self):
        try:
            half_w = 360.0
            half_h = 210.0
            corners = [
                self._project_point(-half_w, 0.0, -half_h)[0],
                self._project_point(half_w, 0.0, -half_h)[0],
                self._project_point(half_w, 0.0, half_h)[0],
                self._project_point(-half_w, 0.0, half_h)[0],
            ]
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            return path
        except Exception:
            return None

    def _is_pos_on_desktop_plane(self, pos):
        try:
            path = self._desktop_plane_path()
            if path is None:
                return False
            return bool(path.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _draw_desktop_plane(self, painter):
        palette = self._desktop_plane_palette_for_background()
        grid_color = QColor(palette.get("grid", QColor(142, 210, 255, 82)))
        major_color = QColor(palette.get("major", QColor(255, 210, 210, 120)))
        edge_color = QColor(palette.get("edge", QColor(255, 246, 220, 155)))
        half_w = 360.0
        half_h = 210.0
        step = 60.0
        path = self._desktop_plane_path()
        if path is None:
            return
        corners = [
            self._project_point(-half_w, 0.0, -half_h)[0],
            self._project_point(half_w, 0.0, -half_h)[0],
            self._project_point(half_w, 0.0, half_h)[0],
            self._project_point(-half_w, 0.0, half_h)[0],
        ]
        plane = QLinearGradient(corners[0], corners[2])
        try:
            src_plane = palette.get("plane_gradient", None)
            if src_plane is not None:
                # Recreate with projected endpoints while keeping the selected palette.
                theme = self.preview_background_theme()
                if theme in ("light_nvd", "white"):
                    plane.setColorAt(0.0, QColor(228, 232, 236, 112))
                    plane.setColorAt(1.0, QColor(174, 184, 194, 72))
                elif theme == "black_lime":
                    plane.setColorAt(0.0, QColor(118, 185, 0, 86))
                    plane.setColorAt(1.0, QColor(28, 58, 0, 58))
                elif theme == "graphite":
                    plane.setColorAt(0.0, QColor(246, 248, 250, 32))
                    plane.setColorAt(1.0, QColor(118, 132, 148, 24))
                else:
                    plane.setColorAt(0.0, QColor(255, 255, 255, 34))
                    plane.setColorAt(1.0, QColor(120, 170, 255, 18))
        except Exception:
            plane.setColorAt(0.0, QColor(255, 255, 255, 34))
            plane.setColorAt(1.0, QColor(120, 170, 255, 18))
        painter.setPen(QPen(edge_color, 2.0))
        painter.setBrush(QBrush(plane))
        painter.drawPath(path)
        x = -half_w
        while x <= half_w + 0.1:
            color = major_color if abs(x) < 0.1 else grid_color
            self._draw_line_3d(painter, (x, 0.0, -half_h), (x, 0.0, half_h), color, 1.0)
            x += step
        z = -half_h
        while z <= half_h + 0.1:
            color = major_color if abs(z) < 0.1 else grid_color
            self._draw_line_3d(painter, (-half_w, 0.0, z), (half_w, 0.0, z), color, 1.0)
            z += step

    def _draw_marker(self, painter, x, z, radius, color, label):
        point, scale = self._project_point(x, 14.0, z)
        r = max(5.0, float(radius) * scale)
        halo = QRadialGradient(point, r * 2.8)
        c0 = QColor(color)
        c0.setAlpha(150)
        c1 = QColor(color)
        c1.setAlpha(0)
        halo.setColorAt(0.0, c0)
        halo.setColorAt(1.0, c1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(point, r * 2.8, r * 2.8)
        body = QRadialGradient(QPointF(point.x() - r * 0.25, point.y() - r * 0.25), r * 1.25)
        body.setColorAt(0.0, QColor(255, 255, 255, 230))
        body.setColorAt(0.55, color)
        edge = QColor(color).darker(145)
        body.setColorAt(1.0, edge)
        painter.setBrush(QBrush(body))
        painter.setPen(QPen(QColor(255, 255, 255, 170), max(1.0, r * 0.08)))
        painter.drawEllipse(point, r, r)
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.0))
        painter.drawText(QPointF(point.x() + r + 6.0, point.y() + 4.0), str(label))

    def reconcile_with_persisted_effect_visibility(self, state):
        """Clear stale pending/selection state when detail settings turned effects off."""
        try:
            effect = dict((state or {}).get("effect", {}) or {})
            changed = False
            if not bool(effect.get("water_surface_visible", False)):
                if getattr(self, "_pending_water_surface_state", None) is not None or bool(getattr(self, "_water_surface_selected", False)):
                    self._pending_water_surface_state = None
                    self._water_surface_selected = False
                    self._water_surface_drag_start_pos = None
                    self._water_surface_drag_start_state = None
                    self._water_surface_resize_drag_start_pos = None
                    self._water_surface_resize_drag_start_state = None
                    changed = True
            if not bool(effect.get("ice_visible", False)):
                if getattr(self, "_pending_ice_state", None) is not None or bool(getattr(self, "_ice_selected", False)):
                    self._pending_ice_state = None
                    self._ice_selected = False
                    self._ice_drag_start_pos = None
                    self._ice_drag_start_state = None
                    self._ice_drag_basis = None
                    self._ice_resize_drag_kind = None
                    changed = True
            if not bool(effect.get("puddle_visible", False)):
                if getattr(self, "_pending_puddle_state", None) is not None or bool(getattr(self, "_pending_puddle_states", {}) or {}):
                    self._pending_puddle_state = None
                    self._pending_puddle_states = {}
                    self._selected_puddle_index = 0
                    self._drag_start_pos = None
                    self._drag_start_puddle_state = None
                    changed = True
            if not bool(effect.get("bamboo_grove_visible", False)):
                if bool(getattr(self, "_bamboo_grove_selected", False)) or getattr(self, "_pending_bamboo_grove_state", None) is not None:
                    self._bamboo_grove_selected = False
                    self._pending_bamboo_grove_state = None
                    self._bamboo_grove_resize_drag_start_pos = None
                    self._bamboo_grove_resize_drag_start_state = None
                    changed = True
            if not bool(effect.get("cloud_visible", False)):
                if bool(getattr(self, "_cloud_selected", False)) or getattr(self, "_pending_cloud_layer_state", None) is not None:
                    self._cloud_selected = False
                    self._pending_cloud_layer_state = None
                    self._cloud_drag_start_pos = None
                    self._cloud_drag_start_state = None
                    self._cloud_resize_drag_start_pos = None
                    self._cloud_resize_drag_start_state = None
                    changed = True
            if not bool(effect.get("fireball_visible", False)):
                if bool(getattr(self, "_fireball_selected", False)):
                    self._fireball_selected = False
                    changed = True
            if not bool(effect.get("sun_visible", False)) and getattr(self, "_pending_sun_unit", None) is not None:
                self._pending_sun_unit = None
                changed = True
            if not bool(effect.get("moon_visible", False)) and getattr(self, "_pending_moon_unit", None) is not None:
                self._pending_moon_unit = None
                changed = True
            if changed:
                self._drag_kind = None
                self._drag_notice = "3D preview synced with detail settings"
                try:
                    self.update()
                except Exception:
                    pass
            return bool(changed)
        except Exception:
            return False

    def set_preview_state(self, state):
        incoming = dict(state or {})
        try:
            self.reconcile_with_persisted_effect_visibility(incoming)
        except Exception:
            pass
        # Keep the temporary/pending preview-only Sun coordinates until the user
        # explicitly applies them or the widget is reset.  Without this, the 500ms
        # read-only parent sync can overwrite the dragged Sun immediately after
        # mouse release, making the Apply button appear to do nothing.
        try:
            pending = getattr(self, "_pending_sun_unit", None)
            pending_moon = getattr(self, "_pending_moon_unit", None)
            pending_puddle = getattr(self, "_pending_puddle_state", None)
            pending_puddles = dict(getattr(self, "_pending_puddle_states", {}) or {})
            pending_ice = getattr(self, "_pending_ice_state", None)
            pending_water_surface = getattr(self, "_pending_water_surface_state", None)
            pending_fireball = getattr(self, "_pending_fireball_layer_state", None)
            if pending is not None:
                incoming_effect = dict(incoming.get("effect", {}) or {})
                incoming_effect["sun_visible"] = True
                incoming_effect["sun_x"] = max(0.0, min(1.0, float(pending[0])))
                incoming_effect["sun_y"] = max(0.0, min(1.0, float(pending[1])))
                incoming["effect"] = incoming_effect
            if pending_moon is not None:
                incoming_effect = dict(incoming.get("effect", {}) or {})
                incoming_effect["moon_visible"] = True
                incoming_effect["moon_x"] = max(0.0, min(1.0, float(pending_moon[0])))
                incoming_effect["moon_y"] = max(0.0, min(1.0, float(pending_moon[1])))
                incoming["effect"] = incoming_effect
            if pending_fireball is not None:
                incoming_effect = dict(incoming.get("effect", {}) or {})
                pending_fireball = dict(pending_fireball or {})
                incoming_effect["fireball_visible"] = True
                incoming_effect["fireball_x"] = max(0.0, min(1.0, float(pending_fireball.get("x", incoming_effect.get("fireball_x", 0.50)))))
                incoming_effect["fireball_y"] = max(0.0, min(1.0, float(pending_fireball.get("y", incoming_effect.get("fireball_y", 0.38)))))
                incoming["effect"] = incoming_effect
            if pending_ice is not None:
                incoming_effect = dict(incoming.get("effect", {}) or {})
                pending_ice = dict(pending_ice or {})
                incoming_effect["ice_visible"] = True
                incoming_effect["ice_x"] = max(0.0, min(1.0, float(pending_ice.get("x", incoming_effect.get("ice_x", 0.50)))))
                incoming_effect["ice_y"] = max(0.0, min(1.0, float(pending_ice.get("y", incoming_effect.get("ice_y", 0.58)))))
                incoming_effect["ice_width"] = max(0.05, min(1.50, float(pending_ice.get("width", incoming_effect.get("ice_width", 1.0)))))
                incoming_effect["ice_depth"] = max(0.05, min(1.0, float(pending_ice.get("depth", incoming_effect.get("ice_depth", 0.42)))))
                incoming["effect"] = incoming_effect
            if pending_water_surface is not None:
                incoming_effect = dict(incoming.get("effect", {}) or {})
                pending_water_surface = dict(pending_water_surface or {})
                pending_depth = max(0.05, min(1.0, float(pending_water_surface.get("depth", incoming_effect.get("water_surface_depth", 0.42)))))
                incoming_effect["water_surface_visible"] = True
                incoming_effect["water_surface_y"] = max(0.0, min(max(0.0, 1.0 - pending_depth), float(pending_water_surface.get("y", incoming_effect.get("water_surface_y", 0.58)))))
                incoming_effect["water_surface_depth"] = pending_depth
                incoming_effect["water_surface_alpha"] = int(pending_water_surface.get("alpha", incoming_effect.get("water_surface_alpha", 92)))
                incoming_effect["water_surface_color"] = str(pending_water_surface.get("color", incoming_effect.get("water_surface_color", "#4FC3FF")))
                incoming_effect["water_surface_highlight_color"] = str(pending_water_surface.get("highlight_color", incoming_effect.get("water_surface_highlight_color", "#D8FAFF")))
                incoming["effect"] = incoming_effect
            if pending_puddles or pending_puddle is not None:
                incoming_effect = dict(incoming.get("effect", {}) or {})
                puddles = [dict(item or {}) for item in list(incoming_effect.get("puddles", []) or []) if isinstance(item, dict)]
                if pending_puddle is not None:
                    try:
                        pending_puddles[int(pending_puddle.get("index", getattr(self, "_selected_puddle_index", 0)))] = dict(pending_puddle)
                    except Exception:
                        pending_puddles[0] = dict(pending_puddle)
                for idx, pending_item in sorted(pending_puddles.items(), key=lambda kv: int(kv[0])):
                    try:
                        idx = max(0, int(idx))
                        pending_item = dict(pending_item or {})
                        while len(puddles) <= idx:
                            puddles.append({
                                "index": len(puddles),
                                "x": incoming_effect.get("puddle_x", 0.50),
                                "y": incoming_effect.get("puddle_y", 0.84),
                                "width": incoming_effect.get("puddle_width", 0.20),
                                "height": incoming_effect.get("puddle_height", 0.08),
                                "visible": True,
                            })
                        merged = dict(puddles[idx] or {})
                        merged.update(pending_item)
                        merged["index"] = idx
                        puddles[idx] = merged
                        if idx == 0:
                            incoming_effect["puddle_visible"] = True
                            incoming_effect["puddle_x"] = max(0.0, min(1.0, float(merged.get("x", 0.50))))
                            incoming_effect["puddle_y"] = max(0.0, min(1.0, float(merged.get("y", 0.84))))
                            incoming_effect["puddle_width"] = max(0.03, min(1.20, float(merged.get("width", incoming_effect.get("puddle_width", 0.20)))))
                            incoming_effect["puddle_height"] = max(0.015, min(0.70, float(merged.get("height", incoming_effect.get("puddle_height", 0.08)))))
                    except Exception:
                        pass
                if puddles:
                    incoming_effect["puddles"] = puddles
                incoming["effect"] = incoming_effect
            if pending is None and pending_moon is None and pending_puddle is None and not pending_puddles and getattr(self, "_drag_kind", None) == "sun":
                current = dict(getattr(self, "_preview_state", {}) or {})
                current_effect = dict(current.get("effect", {}) or {})
                incoming_effect = dict(incoming.get("effect", {}) or {})
                if "sun_x" in current_effect and "sun_y" in current_effect:
                    incoming_effect["sun_visible"] = True
                    incoming_effect["sun_x"] = current_effect.get("sun_x", incoming_effect.get("sun_x", 0.22))
                    incoming_effect["sun_y"] = current_effect.get("sun_y", incoming_effect.get("sun_y", 0.22))
                    incoming["effect"] = incoming_effect
        except Exception:
            pass
        try:
            pending_widget = getattr(self, "_pending_widget_rect", None)
            if pending_widget is not None:
                pending_widget = dict(pending_widget or {})
                incoming_selected = dict(incoming.get("selected", {}) or {})
                pending_index = int(pending_widget.get("index", -1))
                incoming_index = int(incoming_selected.get("index", -1))
                # Preserve a pending move only while the same widget is still selected.
                # If the user clicks/selects another widget, stale pending state must not
                # overwrite the new selection in the next 500ms sync.
                if pending_index >= 0 and pending_index == incoming_index:
                    incoming["selected"] = pending_widget
                else:
                    self._pending_widget_rect = None
                    self._widget_drag_start = None
                    self._widget_drag_offset_unit = None
                    self._widget_drag_start_pos = None
                    self._widget_drag_jacobian = None
        except Exception:
            pass
        try:
            preview_selected_index = getattr(self, "_preview_selected_widget_index", None)
            if preview_selected_index is not None:
                preview_selected_index = int(preview_selected_index)
                if preview_selected_index >= 0:
                    pending_widget_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                    pending_widget_for_selection = getattr(self, "_pending_widget_rect", None)
                    selected_from_widgets = None
                    try:
                        pending_data = dict(pending_widget_map.get(preview_selected_index) or {})
                        if pending_data:
                            selected_from_widgets = dict(pending_data)
                    except Exception:
                        selected_from_widgets = None
                    if selected_from_widgets is None:
                        try:
                            pending_data = dict(pending_widget_for_selection or {})
                            if int(pending_data.get("index", -1)) == preview_selected_index:
                                selected_from_widgets = dict(pending_data)
                        except Exception:
                            selected_from_widgets = None
                    widgets_for_selection = [dict(item or {}) for item in list(incoming.get("widgets", []) or []) if isinstance(item, dict)]
                    # Overlay every pending widget edit into the incoming widget list before selecting.
                    try:
                        for widget_item in list(incoming.get("widgets", []) or []):
                            if isinstance(widget_item, dict):
                                idx_for_widget = int(widget_item.get("index", -999999))
                                if idx_for_widget in pending_widget_map:
                                    widget_item.update(dict(pending_widget_map.get(idx_for_widget) or {}))
                    except Exception:
                        pass
                    if selected_from_widgets is None:
                        for widget_item in widgets_for_selection:
                            if int(widget_item.get("index", -999999)) == preview_selected_index:
                                selected_from_widgets = dict(widget_item)
                                break
                    if selected_from_widgets is not None:
                        incoming["selected"] = dict(selected_from_widgets)
                        for widget_item in list(incoming.get("widgets", []) or []):
                            if isinstance(widget_item, dict):
                                widget_item["selected"] = int(widget_item.get("index", -999999)) == preview_selected_index
                                if widget_item["selected"]:
                                    try:
                                        widget_item.update({
                                            "x": int(selected_from_widgets.get("x", widget_item.get("x", 0))),
                                            "y": int(selected_from_widgets.get("y", widget_item.get("y", 0))),
                                            "w": int(selected_from_widgets.get("w", widget_item.get("w", 80))),
                                            "h": int(selected_from_widgets.get("h", widget_item.get("h", 80))),
                                            "rotation": float(selected_from_widgets.get("rotation", widget_item.get("rotation", 0.0))),
                                        })
                                    except Exception:
                                        pass
                    else:
                        self._preview_selected_widget_index = None
        except Exception:
            pass
        if getattr(self, "_preview_selection_suppressed", False):
            try:
                incoming["selected"] = {}
                self._preview_selected_widget_index = None
            except Exception:
                pass
        self._preview_state = incoming
        try:
            self.update()
        except Exception:
            pass

    def _unit_to_plane(self, x_ratio, y_ratio):
        try:
            x_ratio = max(0.0, min(1.0, float(x_ratio)))
            y_ratio = max(0.0, min(1.0, float(y_ratio)))
        except Exception:
            x_ratio = 0.5
            y_ratio = 0.5
        plane_x = (x_ratio - 0.5) * 720.0
        plane_z = (y_ratio - 0.5) * 420.0
        return plane_x, plane_z

    def _draw_puddle_marker(self, painter, x_ratio, y_ratio, w_ratio=0.20, h_ratio=0.08, label="Puddle", show_handle=True, selected=False):
        px, pz = self._unit_to_plane(x_ratio, y_ratio)
        center, scale = self._project_point(px, 3.0, pz)
        rw = max(12.0, 360.0 * max(0.03, min(1.2, float(w_ratio))) * scale)
        rh = max(6.0, 210.0 * max(0.015, min(0.7, float(h_ratio))) * scale)
        puddle = QRadialGradient(center, rw)
        puddle.setColorAt(0.0, QColor(182, 236, 255, 148 if selected else 132))
        puddle.setColorAt(0.64, QColor(72, 158, 210, 96 if selected else 82))
        puddle.setColorAt(1.0, QColor(10, 40, 70, 0))
        painter.setPen(QPen(QColor(255, 246, 150, 230) if selected else QColor(210, 250, 255, 145), 2.4 if selected else 1.4))
        painter.setBrush(QBrush(puddle))
        painter.drawEllipse(center, rw, rh)
        painter.setPen(QPen(QColor(255, 246, 170, 235) if selected else QColor(230, 250, 255, 220), 1.0))
        painter.drawText(QPointF(center.x() + rw + 7.0, center.y() + 4.0), str(label) + (" [selected]" if selected else ""))
        if not show_handle:
            return
        # High-contrast resize handle.  The actual resize action is still gated
        # by desktop-lock mode in mouse events.
        handle_size = 18.0
        handle_center = QPointF(center.x() + rw, center.y() + rh)
        handle_rect = QRectF(
            handle_center.x() - handle_size * 0.5,
            handle_center.y() - handle_size * 0.5,
            handle_size,
            handle_size,
        )
        painter.setBrush(QBrush(QColor(255, 246, 110, 245)))
        painter.setPen(QPen(QColor(30, 25, 10, 245), 2.2))
        try:
            painter.drawRoundedRect(handle_rect, 4.0, 4.0)
        except Exception:
            painter.drawRect(handle_rect)
        painter.setPen(QPen(QColor(30, 25, 10, 245), 1.6))
        painter.drawLine(QPointF(handle_rect.left() + 4.0, handle_rect.bottom() - 5.0), QPointF(handle_rect.right() - 4.0, handle_rect.bottom() - 5.0))
        painter.drawLine(QPointF(handle_rect.right() - 5.0, handle_rect.top() + 4.0), QPointF(handle_rect.right() - 5.0, handle_rect.bottom() - 4.0))

    def _current_water_surface_state(self):
        effect = dict(dict(getattr(self, "_preview_state", {}) or {}).get("effect", {}) or {})
        pending = getattr(self, "_pending_water_surface_state", None)
        if pending is not None:
            try:
                pending = dict(pending or {})
                effect["water_surface_visible"] = True
                effect["water_surface_y"] = pending.get("y", effect.get("water_surface_y", 0.58))
                effect["water_surface_depth"] = pending.get("depth", effect.get("water_surface_depth", 0.42))
                effect["water_surface_alpha"] = pending.get("alpha", effect.get("water_surface_alpha", 92))
                effect["water_surface_color"] = pending.get("color", effect.get("water_surface_color", "#4FC3FF"))
                effect["water_surface_highlight_color"] = pending.get("highlight_color", effect.get("water_surface_highlight_color", "#D8FAFF"))
            except Exception:
                pass
        try:
            depth_ratio = max(0.05, min(1.0, float(effect.get("water_surface_depth", 0.42))))
        except Exception:
            depth_ratio = 0.42
        try:
            y_ratio = max(0.0, min(max(0.0, 1.0 - depth_ratio), float(effect.get("water_surface_y", 0.58))))
        except Exception:
            y_ratio = max(0.0, min(1.0, 0.58))
        try:
            alpha = max(0, min(255, int(effect.get("water_surface_alpha", 92))))
        except Exception:
            alpha = 92
        return {
            "visible": bool(effect.get("water_surface_visible", False)),
            "y": y_ratio,
            "depth": depth_ratio,
            "alpha": alpha,
            "color": str(effect.get("water_surface_color", "#4FC3FF") or "#4FC3FF"),
            "highlight_color": str(effect.get("water_surface_highlight_color", "#D8FAFF") or "#D8FAFF"),
        }

    def _draw_water_surface_marker(self, painter, y_ratio=0.58, depth_ratio=0.42, label="Water Surface", color="#4FC3FF", highlight_color="#D8FAFF", alpha=92, selected=False):
        # Display-only 3D preview marker for the rectangular Water Surface effect.
        # Phase 23A-1 intentionally does not add hit-testing, dragging, pending state,
        # or apply/save behavior. This keeps the marker from stealing input from
        # Puddle, Ice, or normal widgets while rendering is validated first.
        try:
            y_ratio = max(0.0, min(1.0, float(y_ratio)))
            depth_ratio = max(0.05, min(1.0, float(depth_ratio)))
            alpha = max(0, min(255, int(alpha)))
            top_v = y_ratio
            bottom_v = max(0.0, min(1.0, y_ratio + depth_ratio))
            if bottom_v <= top_v:
                return
            corners = []
            for u, v in ((0.0, top_v), (1.0, top_v), (1.0, bottom_v), (0.0, bottom_v)):
                px, pz = self._unit_to_plane(u, v)
                corners.append(self._project_point(px, 2.0, pz)[0])
            if len(corners) < 4:
                return
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()

            base = QColor(str(color or "#4FC3FF"))
            hi = QColor(str(highlight_color or "#D8FAFF"))
            fill = QColor(base)
            fill.setAlpha(max(32, min(136, int(alpha * (0.86 if selected else 0.68)))))
            edge = QColor(255, 246, 150, 235) if selected else QColor(hi)
            edge.setAlpha(max(110, min(235, int(alpha * (1.55 if selected else 1.35)))))
            painter.setPen(QPen(edge, 2.5 if selected else 1.7))
            painter.setBrush(QBrush(fill))
            painter.drawPath(path)

            line_count = 4
            painter.setPen(QPen(QColor(hi.red(), hi.green(), hi.blue(), max(55, min(180, int(alpha * 0.95)))), 1.0))
            for i in range(1, line_count + 1):
                t = i / float(line_count + 1)
                left = QPointF(
                    corners[0].x() * (1.0 - t) + corners[3].x() * t,
                    corners[0].y() * (1.0 - t) + corners[3].y() * t,
                )
                right = QPointF(
                    corners[1].x() * (1.0 - t) + corners[2].x() * t,
                    corners[1].y() * (1.0 - t) + corners[2].y() * t,
                )
                painter.drawLine(left, right)

            if selected:
                try:
                    handle_size = 18.0
                    handle_center = QPointF(
                        (corners[2].x() + corners[3].x()) * 0.5,
                        (corners[2].y() + corners[3].y()) * 0.5,
                    )
                    handle_rect = QRectF(
                        handle_center.x() - handle_size * 0.5,
                        handle_center.y() - handle_size * 0.5,
                        handle_size,
                        handle_size,
                    )
                    painter.setBrush(QBrush(QColor(255, 246, 110, 245)))
                    painter.setPen(QPen(QColor(30, 25, 10, 245), 2.2))
                    try:
                        painter.drawRoundedRect(handle_rect, 4.0, 4.0)
                    except Exception:
                        painter.drawRect(handle_rect)
                    painter.setPen(QPen(QColor(30, 25, 10, 245), 1.6))
                    painter.drawLine(
                        QPointF(handle_rect.left() + 4.0, handle_rect.center().y()),
                        QPointF(handle_rect.right() - 4.0, handle_rect.center().y()),
                    )
                    painter.drawLine(
                        QPointF(handle_rect.center().x(), handle_rect.top() + 4.0),
                        QPointF(handle_rect.center().x(), handle_rect.bottom() - 4.0),
                    )
                except Exception:
                    pass

            label_point = corners[1]
            painter.setPen(QPen(QColor(255, 246, 170, 235) if selected else QColor(230, 250, 255, 220), 1.0))
            painter.drawText(QPointF(label_point.x() + 8.0, label_point.y() + 5.0), str(label) + (" [selected]" if selected else ""))
        except Exception:
            return

    def _water_surface_marker_path(self, item=None):
        if item is None:
            item = self._current_water_surface_state()
        try:
            if not bool(item.get("visible", False)):
                return None
            y_ratio = max(0.0, min(1.0, float(item.get("y", 0.58))))
            depth_ratio = max(0.05, min(1.0, float(item.get("depth", 0.42))))
            top_v = y_ratio
            bottom_v = max(0.0, min(1.0, y_ratio + depth_ratio))
            if bottom_v <= top_v:
                return None
            corners = []
            for u, v in ((0.0, top_v), (1.0, top_v), (1.0, bottom_v), (0.0, bottom_v)):
                px, pz = self._unit_to_plane(u, v)
                corners.append(self._project_point(px, 2.0, pz)[0])
            if len(corners) < 4:
                return None
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            return path
        except Exception:
            return None

    def _hit_water_surface_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            path = self._water_surface_marker_path()
            if path is None:
                return False
            return bool(path.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _water_surface_depth_resize_handle_rect(self, item=None):
        if item is None:
            item = self._current_water_surface_state()
        try:
            if not bool(item.get("visible", False)):
                return None
            y_ratio = max(0.0, min(1.0, float(item.get("y", 0.58))))
            depth_ratio = max(0.05, min(1.0, float(item.get("depth", 0.42))))
            bottom_v = max(0.0, min(1.0, y_ratio + depth_ratio))
            if bottom_v <= y_ratio:
                return None
            left_x, left_z = self._unit_to_plane(0.0, bottom_v)
            right_x, right_z = self._unit_to_plane(1.0, bottom_v)
            left_point = self._project_point(left_x, 2.0, left_z)[0]
            right_point = self._project_point(right_x, 2.0, right_z)[0]
            handle_size = 20.0
            center = QPointF(
                (float(left_point.x()) + float(right_point.x())) * 0.5,
                (float(left_point.y()) + float(right_point.y())) * 0.5,
            )
            return QRectF(
                center.x() - handle_size * 0.5,
                center.y() - handle_size * 0.5,
                handle_size,
                handle_size,
            )
        except Exception:
            return None

    def _hit_water_surface_depth_resize_handle(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            if not bool(getattr(self, "_water_surface_selected", False)):
                return False
            rect = self._water_surface_depth_resize_handle_rect()
            if rect is None:
                return False
            return bool(rect.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _select_water_surface_preview(self):
        try:
            self._preview_selected_widget_index = None
            self._clear_ice_preview_selection("")
            self._clear_stale_puddle_preview_state_if_disabled()
            self._water_surface_selected = True
            water = self._current_water_surface_state()
            self._drag_notice = f"Water Surface selected / move+depth-resize y={water.get('y', 0.58):.3f} depth={water.get('depth', 0.42):.3f}"
            self.update()
        except Exception:
            pass

    def _clear_water_surface_preview_selection(self, notice="Water Surface selection cleared"):
        try:
            if bool(getattr(self, "_water_surface_selected", False)):
                self._water_surface_selected = False
                self._drag_notice = str(notice or "Water Surface selection cleared")
                self.update()
        except Exception:
            pass

    def _begin_water_surface_move_drag(self, pos):
        try:
            self._water_surface_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._water_surface_drag_start_state = dict(self._current_water_surface_state() or {})
        except Exception:
            self._water_surface_drag_start_pos = None
            self._water_surface_drag_start_state = None

    def _set_temp_water_surface_y(self, y_ratio):
        water = dict(self._current_water_surface_state() or {})
        try:
            depth_ratio = max(0.05, min(1.0, float(water.get("depth", 0.42))))
        except Exception:
            depth_ratio = 0.42
        max_y = max(0.0, 1.0 - depth_ratio)
        try:
            y_ratio = max(0.0, min(max_y, float(y_ratio)))
        except Exception:
            y_ratio = max(0.0, min(max_y, float(water.get("y", 0.58))))
        try:
            if self.is_snap_enabled():
                y_ratio = max(0.0, min(max_y, self._snap_float_value(y_ratio, 0.02)))
        except Exception:
            pass
        self._pending_water_surface_state = {
            "y": y_ratio,
            "depth": depth_ratio,
            "alpha": int(water.get("alpha", 92)),
            "color": str(water.get("color", "#4FC3FF") or "#4FC3FF"),
            "highlight_color": str(water.get("highlight_color", "#D8FAFF") or "#D8FAFF"),
            "visible": True,
        }
        self._water_surface_selected = True
        self._drag_notice = f"Water Surface preview-only y={y_ratio:.3f} depth={depth_ratio:.3f}" + (" SNAP" if self.is_snap_enabled() else "")
        try:
            self.update()
        except Exception:
            pass

    def _set_temp_water_surface_y_from_drag_delta(self, pos):
        try:
            start_state = dict(getattr(self, "_water_surface_drag_start_state", None) or self._current_water_surface_state() or {})
            start_pos = getattr(self, "_water_surface_drag_start_pos", None)
            if start_pos is None:
                self._begin_water_surface_move_drag(pos)
                start_pos = getattr(self, "_water_surface_drag_start_pos", None)
                start_state = dict(getattr(self, "_water_surface_drag_start_state", None) or self._current_water_surface_state() or {})
            start_y = float(start_state.get("y", 0.58))
            _, current_unit_y = self._screen_to_unit_on_desktop(pos, 0.50, start_y)
            _, start_unit_y = self._screen_to_unit_on_desktop(start_pos, 0.50, start_y)
            self._set_temp_water_surface_y(start_y + (current_unit_y - start_unit_y))
        except Exception:
            try:
                water = self._current_water_surface_state()
                _, ny = self._screen_to_unit_on_desktop(pos, 0.50, float(water.get("y", 0.58)))
                self._set_temp_water_surface_y(ny)
            except Exception:
                pass

    def _begin_water_surface_depth_resize_drag(self, pos):
        try:
            self._water_surface_resize_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._water_surface_resize_drag_start_state = dict(self._current_water_surface_state() or {})
        except Exception:
            self._water_surface_resize_drag_start_pos = None
            self._water_surface_resize_drag_start_state = None

    def _set_temp_water_surface_depth(self, depth_ratio):
        water = dict(self._current_water_surface_state() or {})
        try:
            y_ratio = max(0.0, min(1.0, float(water.get("y", 0.58))))
        except Exception:
            y_ratio = 0.58
        max_depth = max(0.05, 1.0 - y_ratio)
        try:
            depth_ratio = max(0.05, min(max_depth, float(depth_ratio)))
        except Exception:
            depth_ratio = max(0.05, min(max_depth, float(water.get("depth", 0.42))))
        try:
            if self.is_snap_enabled():
                depth_ratio = max(0.05, min(max_depth, self._snap_float_value(depth_ratio, 0.02)))
        except Exception:
            pass
        self._pending_water_surface_state = {
            "y": y_ratio,
            "depth": depth_ratio,
            "alpha": int(water.get("alpha", 92)),
            "color": str(water.get("color", "#4FC3FF") or "#4FC3FF"),
            "highlight_color": str(water.get("highlight_color", "#D8FAFF") or "#D8FAFF"),
            "visible": True,
        }
        self._water_surface_selected = True
        self._drag_notice = f"Water Surface depth preview-only y={y_ratio:.3f} depth={depth_ratio:.3f}" + (" SNAP" if self.is_snap_enabled() else "")
        try:
            self.update()
        except Exception:
            pass

    def _set_temp_water_surface_depth_from_drag_delta(self, pos):
        try:
            start_state = dict(getattr(self, "_water_surface_resize_drag_start_state", None) or self._current_water_surface_state() or {})
            start_pos = getattr(self, "_water_surface_resize_drag_start_pos", None)
            if start_pos is None:
                self._begin_water_surface_depth_resize_drag(pos)
                start_pos = getattr(self, "_water_surface_resize_drag_start_pos", None)
                start_state = dict(getattr(self, "_water_surface_resize_drag_start_state", None) or self._current_water_surface_state() or {})
            start_y = max(0.0, min(1.0, float(start_state.get("y", 0.58))))
            start_depth = max(0.05, min(1.0, float(start_state.get("depth", 0.42))))
            start_bottom = max(0.0, min(1.0, start_y + start_depth))
            _, current_unit_y = self._screen_to_unit_on_desktop(pos, 0.50, start_bottom)
            _, start_unit_y = self._screen_to_unit_on_desktop(start_pos, 0.50, start_bottom)
            new_bottom = start_bottom + (current_unit_y - start_unit_y)
            self._set_temp_water_surface_depth(new_bottom - start_y)
        except Exception:
            try:
                water = self._current_water_surface_state()
                y_ratio = float(water.get("y", 0.58))
                _, bottom_y = self._screen_to_unit_on_desktop(pos, 0.50, y_ratio + float(water.get("depth", 0.42)))
                self._set_temp_water_surface_depth(bottom_y - y_ratio)
            except Exception:
                pass

    def _draw_ice_marker(self, painter, x_ratio=0.50, y_ratio=0.58, width_ratio=1.0, depth_ratio=0.42, label="Ice", selected=False):
        try:
            x_ratio = max(0.0, min(1.0, float(x_ratio)))
            y_ratio = max(0.0, min(1.0, float(y_ratio)))
            width_ratio = max(0.05, min(1.50, float(width_ratio)))
            depth_ratio = max(0.05, min(1.0, float(depth_ratio)))
            left_u = max(-0.25, min(1.25, x_ratio - width_ratio * 0.5))
            right_u = max(-0.25, min(1.25, x_ratio + width_ratio * 0.5))
            top_v = max(0.0, min(1.0, y_ratio))
            bottom_v = max(0.0, min(1.0, y_ratio + depth_ratio))
            corners = []
            for u, v in ((left_u, top_v), (right_u, top_v), (right_u, bottom_v), (left_u, bottom_v)):
                px, pz = self._unit_to_plane(u, v)
                corners.append(self._project_point(px, 4.0, pz)[0])
            if len(corners) < 4:
                return
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            fill = QLinearGradient(corners[0], corners[2])
            fill.setColorAt(0.0, QColor(230, 255, 255, 122 if selected else 94))
            fill.setColorAt(0.55, QColor(126, 214, 255, 74 if selected else 54))
            fill.setColorAt(1.0, QColor(255, 255, 255, 36 if selected else 24))
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor(255, 246, 150, 230) if selected else QColor(218, 250, 255, 190), 2.6 if selected else 1.8))
            painter.drawPath(path)
            try:
                painter.setPen(QPen(QColor(245, 255, 255, 92), 1.0))
                painter.drawLine(corners[0], corners[2])
                painter.drawLine(corners[1], corners[3])
            except Exception:
                pass
            label_point = corners[1]
            painter.setPen(QPen(QColor(235, 252, 255, 225), 1.0))
            painter.drawText(QPointF(label_point.x() + 8.0, label_point.y() + 4.0), str(label) + (" [selected/display]" if selected else " [display]"))
        except Exception:
            pass

    def _widget_canvas_corners(self, item):
        try:
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            w = max(1.0, float(item.get("w", 80.0)))
            h = max(1.0, float(item.get("h", 80.0)))
            angle = math.radians(float(item.get("rotation", 0.0)))
            cx = x + w * 0.5
            cy = y + h * 0.5
            ca = math.cos(angle)
            sa = math.sin(angle)
            local = [(-w * 0.5, -h * 0.5), (w * 0.5, -h * 0.5), (w * 0.5, h * 0.5), (-w * 0.5, h * 0.5)]
            return [(cx + lx * ca - ly * sa, cy + lx * sa + ly * ca) for lx, ly in local]
        except Exception:
            return []

    def _widget_projected_corners(self, item, y_lift=8.0):
        try:
            cw = max(1.0, float(item.get("canvas_w", 1920.0)))
            ch = max(1.0, float(item.get("canvas_h", 1080.0)))
            points = []
            for px, py in self._widget_canvas_corners(item):
                plane_x, plane_z = self._unit_to_plane(px / cw, py / ch)
                points.append(self._project_point(plane_x, y_lift, plane_z)[0])
            return points
        except Exception:
            return []

    def _draw_widget_rotation_handle(self, painter, item, corners):
        try:
            if str(item.get("type", "")) == "effects_overlay" or not self.is_desktop_locked() or len(corners) < 4:
                return
            top_mid = QPointF((corners[0].x() + corners[1].x()) * 0.5, (corners[0].y() + corners[1].y()) * 0.5)
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            vx = top_mid.x() - center.x()
            vy = top_mid.y() - center.y()
            length = max(1.0, math.hypot(vx, vy))
            hx = top_mid.x() + vx / length * 26.0
            hy = top_mid.y() + vy / length * 26.0
            handle = QPointF(hx, hy)
            painter.setPen(QPen(QColor(90, 180, 255, 210), 1.8))
            painter.drawLine(top_mid, handle)
            painter.setBrush(QBrush(QColor(105, 190, 255, 245)))
            painter.setPen(QPen(QColor(8, 38, 70, 245), 2.0))
            painter.drawEllipse(handle, 9.0, 9.0)
            painter.setPen(QPen(QColor(8, 38, 70, 245), 1.2))
            painter.drawText(QPointF(handle.x() + 10.0, handle.y() + 4.0), "↻")
        except Exception:
            pass

    def _widget_rotation_handle_center(self, item=None):
        try:
            item = dict(item or self._current_widget_rect_state() or {})
            if not item or str(item.get("type", "")) == "effects_overlay":
                return None
            corners = self._widget_projected_corners(item)
            if len(corners) < 4:
                return None
            top_mid = QPointF((corners[0].x() + corners[1].x()) * 0.5, (corners[0].y() + corners[1].y()) * 0.5)
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            vx = top_mid.x() - center.x()
            vy = top_mid.y() - center.y()
            length = max(1.0, math.hypot(vx, vy))
            return QPointF(top_mid.x() + vx / length * 26.0, top_mid.y() + vy / length * 26.0)
        except Exception:
            return None

    def _effect_overlay_full_desktop_rect_item(self, item):
        try:
            item = dict(item or {})
            if str(item.get("type", "")) != "effects_overlay":
                return item
            canvas_w = max(1, int(item.get("canvas_w", 1920)))
            canvas_h = max(1, int(item.get("canvas_h", 1080)))
            item["x"] = 0
            item["y"] = 0
            item["w"] = canvas_w
            item["h"] = canvas_h
            item["rotation"] = 0.0
            if not str(item.get("title", "") or "").strip():
                item["title"] = "Effects Overlay"
            return item
        except Exception:
            return dict(item or {})

    def _draw_clock_widget_preview_marker(self, painter, item, corners, is_selected=False):
        """Draw a tiny clock face inside the 3D widget footprint for Phase 24A-2 smoke tests."""
        try:
            if not self._is_clock_widget_preview_item(item) or len(corners) < 4:
                return
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            width = max(8.0, ((corners[1].x() - corners[0].x()) ** 2 + (corners[1].y() - corners[0].y()) ** 2) ** 0.5)
            height = max(8.0, ((corners[3].x() - corners[0].x()) ** 2 + (corners[3].y() - corners[0].y()) ** 2) ** 0.5)
            radius = max(8.0, min(width, height) * 0.22)
            accent = QColor(str(item.get("color", "#FFCC66") or "#FFCC66"))
            bg = QColor(str(item.get("bg", "#10141C") or "#10141C"))
            bg.setAlpha(190 if is_selected else 145)
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(accent, 2.0 if is_selected else 1.2))
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QPen(QColor(245, 248, 255, 190), 1.0))
            for tick in range(12):
                angle = math.radians(tick * 30.0 - 90.0)
                inner = radius * 0.78
                outer = radius * 0.92
                painter.drawLine(
                    QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner),
                    QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer),
                )
            now = time.localtime()
            hour_angle = math.radians(((now.tm_hour % 12 + now.tm_min / 60.0) * 30.0) - 90.0)
            minute_angle = math.radians(((now.tm_min + now.tm_sec / 60.0) * 6.0) - 90.0)
            painter.setPen(QPen(QColor(235, 238, 245, 220), max(1.0, radius * 0.08)))
            painter.drawLine(center, QPointF(center.x() + math.cos(hour_angle) * radius * 0.48, center.y() + math.sin(hour_angle) * radius * 0.48))
            painter.setPen(QPen(accent, max(1.0, radius * 0.055)))
            painter.drawLine(center, QPointF(center.x() + math.cos(minute_angle) * radius * 0.68, center.y() + math.sin(minute_angle) * radius * 0.68))
            if bool(item.get("clock_show_digital", True)):
                painter.setPen(QPen(QColor(255, 245, 210, 230), 1.0))
                font = painter.font()
                try:
                    font.setPointSize(max(7, min(18, int(float(item.get("font_size", 12))))))
                    painter.setFont(font)
                except Exception:
                    pass
                painter.drawText(QPointF(center.x() - radius * 0.92, center.y() + radius + 13.0), time.strftime("%H:%M", now))
        except Exception:
            pass

    def _draw_system_network_widget_preview_marker(self, painter, item, corners, is_selected=False):
        """Phase 24A-5: draw tiny color swatches for system/network specific live-preview fields."""
        try:
            widget_type = str(dict(item or {}).get("type", "")).strip().lower()
            if widget_type not in ("system", "network") or len(corners) < 4:
                return
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            width = max(18.0, ((corners[1].x() - corners[0].x()) ** 2 + (corners[1].y() - corners[0].y()) ** 2) ** 0.5)
            height = max(14.0, ((corners[3].x() - corners[0].x()) ** 2 + (corners[3].y() - corners[0].y()) ** 2) ** 0.5)
            bg = QColor(str(item.get("bg", "#10141C") or "#10141C"))
            bg.setAlpha(180 if is_selected else 130)
            box_w = max(34.0, min(width * 0.52, 96.0))
            box_h = max(18.0, min(height * 0.28, 46.0))
            box = QRectF(center.x() - box_w * 0.5, center.y() - box_h * 0.5, box_w, box_h)
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(QColor(230, 240, 255, 180 if is_selected else 110), 1.0))
            try:
                painter.drawRoundedRect(box, 5.0, 5.0)
            except Exception:
                painter.drawRect(box)
            if widget_type == "system":
                swatches = [
                    ("CPU", str(item.get("cpu_color", item.get("color", "#5BE7FF")) or "#5BE7FF")),
                    ("MEM", str(item.get("memory_color", "#B388FF") or "#B388FF")),
                    ("DSK", str(item.get("disk_color", "#80FF9F") or "#80FF9F")),
                ]
            else:
                # Phase 24A-10b: color values are used only as paint colors;
                # do not render raw CSS/hex strings in the visible marker text.
                swatches = [
                    ("DN", str(item.get("network_down_color", item.get("color", "#5BE7FF")) or "#5BE7FF")),
                    ("UP", str(item.get("network_up_color", "#80FF9F") or "#80FF9F")),
                ]
            gap = 3.0
            swatch_w = max(8.0, (box.width() - gap * (len(swatches) + 1)) / max(1, len(swatches)))
            swatch_h = max(6.0, box.height() * 0.42)
            x = box.left() + gap
            y = box.top() + box.height() * 0.30
            for _label, color_text in swatches:
                rect = QRectF(x, y, swatch_w, swatch_h)
                painter.setBrush(QBrush(QColor(color_text)))
                painter.setPen(QPen(QColor(0, 0, 0, 120), 0.8))
                try:
                    painter.drawRoundedRect(rect, 2.0, 2.0)
                except Exception:
                    painter.drawRect(rect)
                x += swatch_w + gap
            painter.setPen(QPen(QColor(245, 248, 255, 205), 1.0))
            font = painter.font()
            try:
                font.setPointSize(max(6, min(10, int(float(item.get("font_size", 9))))))
                painter.setFont(font)
            except Exception:
                pass
            painter.drawText(QPointF(box.left() + 5.0, box.bottom() - 4.0), "System" if widget_type == "system" else "NET DOWN/UP")
        except Exception:
            pass

    def _preview_runtime_number_text(self, value, suffix="", decimals=0, fallback="--"):
        try:
            number = float(value)
            if decimals <= 0:
                return f"{number:.0f}{suffix}"
            return f"{number:.{int(decimals)}f}{suffix}"
        except Exception:
            return str(fallback)

    def _draw_runtime_widget_metric_overlay(self, painter, item, corners, is_selected=False):
        """Phase 24A-10C: show real runtime metrics passed by the main window."""
        try:
            data = dict(item or {})
            widget_type = str(data.get("type", "") or "").strip().lower()
            if widget_type not in ("system", "network", "calendar", "weather", "volume", "media"):
                return
            if len(corners) < 4:
                return
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            width = max(34.0, ((corners[1].x() - corners[0].x()) ** 2 + (corners[1].y() - corners[0].y()) ** 2) ** 0.5)
            height = max(22.0, ((corners[3].x() - corners[0].x()) ** 2 + (corners[3].y() - corners[0].y()) ** 2) ** 0.5)
            box_w = max(62.0, min(width * 0.72, 164.0))
            box_h = 18.0
            box = QRectF(center.x() - box_w * 0.5, center.y() + min(height * 0.25, 42.0), box_w, box_h)
            bg = QColor(5, 9, 14, 166 if is_selected else 126)
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(QColor(220, 240, 255, 130 if is_selected else 80), 0.8))
            try:
                painter.drawRoundedRect(box, 4.0, 4.0)
            except Exception:
                painter.drawRect(box)
            text = ""
            if widget_type == "system":
                cpu = self._preview_runtime_number_text(data.get("runtime_cpu_percent"), "%")
                mem = self._preview_runtime_number_text(data.get("runtime_memory_percent"), "%")
                disk = self._preview_runtime_number_text(data.get("runtime_disk_percent"), "%")
                text = f"CPU {cpu}  MEM {mem}  DSK {disk}"
            elif widget_type == "network":
                down = self._preview_runtime_number_text(data.get("runtime_network_down_kbps"), "K/s", 1)
                up = self._preview_runtime_number_text(data.get("runtime_network_up_kbps"), "K/s", 1)
                text = f"↓ {down}  ↑ {up}"
            elif widget_type == "calendar":
                date_text = str(data.get("runtime_calendar_date", "") or "")
                time_text = str(data.get("runtime_calendar_time", "") or "")
                text = (date_text + " " + time_text).strip() or "calendar"
            elif widget_type == "weather":
                text = str(data.get("runtime_weather_location", data.get("weather_location", "")) or "location")[:28]
            elif widget_type == "volume":
                vol = self._preview_runtime_number_text(data.get("runtime_volume_percent"), "%")
                muted = bool(data.get("runtime_volume_muted", False))
                available = bool(data.get("runtime_volume_available", False))
                text = ("MUTE " if muted else "VOL ") + vol
                if not available:
                    text += " (cached)"
            elif widget_type == "media":
                title = self._preview_widget_short_text(data.get("runtime_media_title", ""), "", 22)
                artist = self._preview_widget_short_text(data.get("runtime_media_artist", ""), "", 16)
                status = self._preview_widget_short_text(data.get("runtime_media_playback_status", ""), "", 12)
                available = bool(data.get("runtime_media_available", False))
                if title and artist:
                    text = f"{status} {title} / {artist}".strip()
                elif title:
                    text = f"{status} {title}".strip()
                elif status:
                    text = status
                else:
                    text = "Media unavailable" if not available else "Media"
            if not text:
                return
            font = painter.font()
            try:
                font.setPointSize(max(6, min(9, int(float(data.get("font_size", 8))))))
                painter.setFont(font)
            except Exception:
                pass
            painter.setPen(QPen(QColor(232, 246, 255, 224), 1.0))
            painter.drawText(QPointF(box.left()+5.0, box.bottom()-4.0), str(text)[:34])
        except Exception:
            pass

    def _preview_widget_short_text(self, value, fallback="", limit=24):
        try:
            text = str(value if value is not None else fallback)
            text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
            if not text:
                text = str(fallback or "")
            limit = max(4, int(limit))
            return text[:limit]
        except Exception:
            return str(fallback or "")[:24]

    def _draw_remaining_normal_widget_data_preview_marker(self, painter, item, corners, is_selected=False):
        """Phase 24A-10B: data-oriented lightweight markers for remaining normal widgets.

        This avoids inventing unavailable runtime data.  It only shows values that
        are available in the 3D preview payload, plus stable local date/time for
        Calendar-style context.
        """
        try:
            data = dict(item or {})
            widget_type = str(data.get("type", "") or "").strip().lower()
            if widget_type in ("", "effects_overlay", "clock", "visualizer", "system", "network"):
                return
            if len(corners) < 4:
                return
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            width = max(32.0, ((corners[1].x() - corners[0].x()) ** 2 + (corners[1].y() - corners[0].y()) ** 2) ** 0.5)
            height = max(22.0, ((corners[3].x() - corners[0].x()) ** 2 + (corners[3].y() - corners[0].y()) ** 2) ** 0.5)
            box_w = max(58.0, min(width * 0.66, 156.0))
            box_h = max(32.0, min(height * 0.44, 78.0))
            box = QRectF(center.x() - box_w * 0.5, center.y() - box_h * 0.5, box_w, box_h)
            bg = QColor(str(data.get("bg", "#10141C") or "#10141C")); bg.setAlpha(178 if is_selected else 132)
            accent = QColor(str(data.get("color", "#5BE7FF") or "#5BE7FF")); accent.setAlpha(238 if is_selected else 196)
            painter.setPen(QPen(QColor(230, 240, 255, 184 if is_selected else 112), 1.0))
            painter.setBrush(QBrush(bg))
            try:
                painter.drawRoundedRect(box, 6.0, 6.0)
            except Exception:
                painter.drawRect(box)
            painter.setPen(QPen(accent, 2.0))
            painter.drawLine(QPointF(box.left()+5.0, box.top()+6.0), QPointF(box.right()-5.0, box.top()+6.0))
            title = self._preview_widget_short_text(data.get("title", ""), "", 22)
            body_text = self._preview_widget_short_text(data.get("text", ""), "", 26)
            font = painter.font()
            try:
                font.setPointSize(max(6, min(10, int(float(data.get("font_size", 9))))))
                painter.setFont(font)
            except Exception:
                pass

            label = widget_type.upper()[:12]
            detail = title or body_text or "widget"
            painter.setPen(QPen(QColor(245, 248, 255, 232), 1.0))

            if widget_type == "calendar":
                label = "CALENDAR"
                try:
                    now = time.localtime()
                    detail = time.strftime("%Y-%m-%d", now)
                    day = int(time.strftime("%d", now))
                except Exception:
                    detail = title or "calendar"
                    day = 1
                grid_left = box.left() + 8.0
                grid_top = box.top() + 21.0
                cell_w = max(5.0, (box.width() - 16.0) / 7.0)
                cell_h = max(4.0, (box.height() - 33.0) / 3.0)
                painter.setPen(QPen(QColor(220, 230, 240, 96), 0.7))
                for row in range(4):
                    y = grid_top + row * cell_h
                    painter.drawLine(QPointF(grid_left, y), QPointF(box.right()-8.0, y))
                for col in range(8):
                    x = grid_left + col * cell_w
                    painter.drawLine(QPointF(x, grid_top), QPointF(x, box.bottom()-9.0))
                try:
                    col = (day - 1) % 7
                    row = ((day - 1) // 7) % 3
                    painter.setBrush(QBrush(accent)); painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(QRectF(grid_left + col*cell_w + 1.0, grid_top + row*cell_h + 1.0, max(3.0, cell_w-2.0), max(3.0, cell_h-2.0)), 2.0, 2.0)
                except Exception:
                    pass
            elif widget_type in ("media", "media_control", "media_controls"):
                label = "MEDIA"
                media_title = self._preview_widget_short_text(data.get("runtime_media_title", ""), "", 22)
                media_artist = self._preview_widget_short_text(data.get("runtime_media_artist", ""), "", 16)
                media_status = self._preview_widget_short_text(data.get("runtime_media_playback_status", ""), "", 12)
                if media_title and media_artist:
                    detail = f"{media_title} / {media_artist}"[:28]
                elif media_title:
                    detail = media_title
                elif media_status:
                    detail = media_status
                else:
                    detail = title or body_text or "No track metadata"
                painter.setBrush(QBrush(accent)); painter.setPen(Qt.PenStyle.NoPen)
                tri = QPainterPath(); tri.moveTo(box.left()+12.0, box.center().y()-8.0); tri.lineTo(box.left()+12.0, box.center().y()+8.0); tri.lineTo(box.left()+28.0, box.center().y()); tri.closeSubpath(); painter.drawPath(tri)
                painter.drawRect(QRectF(box.left()+36.0, box.center().y()-8.0, 3.5, 16.0)); painter.drawRect(QRectF(box.left()+44.0, box.center().y()-8.0, 3.5, 16.0))
                painter.setPen(QPen(QColor(220,235,245,150), 1.0)); painter.drawLine(QPointF(box.left()+55.0, box.center().y()), QPointF(box.right()-10.0, box.center().y()))
            elif widget_type == "volume":
                label = "VOLUME"
                if "runtime_volume_percent" in data:
                    detail = ("Muted " if bool(data.get("runtime_volume_muted", False)) else "Volume ") + self._preview_runtime_number_text(data.get("runtime_volume_percent"), "%")
                else:
                    detail = title or body_text or "system volume"
                painter.setPen(QPen(accent, 2.0)); painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(box.left()+12.0, box.center().y()-6.0, 9.0, 12.0))
                painter.drawArc(QRectF(box.left()+18.0, box.center().y()-15.0, 28.0, 30.0), -45*16, 90*16)
                painter.drawArc(QRectF(box.left()+23.0, box.center().y()-21.0, 40.0, 42.0), -38*16, 76*16)
            elif widget_type == "weather":
                label = "WEATHER"
                detail = self._preview_widget_short_text(data.get("weather_location", ""), title or "location", 24)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 211, 92, 225)))
                painter.drawEllipse(QRectF(box.left()+12.0, box.center().y()-13.0, 20.0, 20.0))
                painter.setBrush(QBrush(QColor(230, 242, 255, 160)))
                painter.drawRoundedRect(QRectF(box.left()+25.0, box.center().y()-2.0, 34.0, 13.0), 6.0, 6.0)
                painter.drawRoundedRect(QRectF(box.left()+17.0, box.center().y()+3.0, 30.0, 10.0), 5.0, 5.0)
            elif widget_type in ("html_js", "html", "css", "javascript"):
                label = "HTML / JS"
                mode = self._preview_widget_short_text(data.get("jshtml_mode", "inline"), "inline", 10)
                source = body_text or self._preview_widget_short_text(data.get("jshtml_entry", "index.html"), "index.html", 22)
                detail = (mode + " · " + source)[:28]
                painter.setPen(QPen(accent, 1.3)); painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawText(QPointF(box.left()+12.0, box.center().y()+4.0), "</>")
                painter.drawRect(QRectF(box.left()+8.0, box.top()+19.0, box.width()-16.0, box.height()-32.0))
            else:
                detail = title or body_text or widget_type

            painter.setPen(QPen(QColor(245, 248, 255, 232), 1.0))
            painter.drawText(QPointF(box.left()+7.0, box.top()+17.0), str(label)[:14])
            painter.setPen(QPen(QColor(222, 236, 246, 204), 1.0))
            painter.drawText(QPointF(box.left()+7.0, box.bottom()-6.0), str(detail)[:30])
        except Exception:
            pass

    def _draw_visualizer_widget_preview_marker(self, painter, item, corners, is_selected=False):
        """Phase 24A-6: draw a tiny visualizer preview for visualizer-specific live fields."""
        try:
            if str(dict(item or {}).get("type", "")).strip().lower() != "visualizer" or len(corners) < 4:
                return
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            width = max(24.0, ((corners[1].x() - corners[0].x()) ** 2 + (corners[1].y() - corners[0].y()) ** 2) ** 0.5)
            height = max(16.0, ((corners[3].x() - corners[0].x()) ** 2 + (corners[3].y() - corners[0].y()) ** 2) ** 0.5)
            bg = QColor(str(item.get("bg", "#10141C") or "#10141C")); bg.setAlpha(175 if is_selected else 125)
            box_w = max(40.0, min(width * 0.58, 118.0)); box_h = max(20.0, min(height * 0.34, 54.0))
            box = QRectF(center.x() - box_w * 0.5, center.y() - box_h * 0.5, box_w, box_h)
            if bool(item.get("visualizer_shadow_enabled", False)):
                painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(QRectF(box.left()+3, box.top()+3, box.width(), box.height()))
            painter.setBrush(QBrush(bg)); painter.setPen(QPen(QColor(230, 240, 255, 180 if is_selected else 110), 1.0)); painter.drawRect(box)
            accent = QColor(str(item.get("color", "#5BE7FF") or "#5BE7FF"))
            glow = bool(item.get("visualizer_glow_enabled", False)); peak = bool(item.get("visualizer_peak_bar_enabled", True))
            vertical = str(item.get("visualizer_orientation", "horizontal") or "horizontal") == "vertical"
            flip = bool(item.get("visualizer_flip_vertical", False))
            bar_count = 8; gap = 2.0
            scale = max(0.1, min(8.0, float(item.get("visualizer_bar_width_scale", 1.0) or 1.0)))
            if not vertical:
                usable_w = box.width() - gap * (bar_count + 1); bar_w = max(2.0, min(usable_w / bar_count * scale, usable_w / max(1, bar_count)))
                base_y = box.bottom() - 5.0
                for n in range(bar_count):
                    frac = (0.22 + 0.68 * ((n * 3) % 7) / 6.0)
                    bar_h = max(4.0, frac * (box.height() - 10.0)); x = box.left() + gap + n * (usable_w / bar_count + gap)
                    y = base_y - bar_h if not flip else box.top() + 5.0
                    rect = QRectF(x, y, bar_w, bar_h)
                    col = QColor(accent); col.setAlpha(230 if glow else 190)
                    painter.setBrush(QBrush(col)); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(rect)
                    if peak:
                        painter.setBrush(QBrush(QColor(255,255,255,210))); painter.drawRect(QRectF(x, y-3 if not flip else y+bar_h+1, bar_w, 2.0))
            else:
                usable_h = box.height() - gap * (bar_count + 1); bar_h = max(2.0, usable_h / bar_count)
                base_x = box.left() + 5.0
                for n in range(bar_count):
                    frac = (0.22 + 0.68 * ((n * 3) % 7) / 6.0)
                    bar_w = max(4.0, frac * (box.width() - 10.0)); y = box.top() + gap + n * (usable_h / bar_count + gap)
                    x = box.right() - 5.0 - bar_w if flip else base_x
                    col = QColor(accent); col.setAlpha(230 if glow else 190)
                    painter.setBrush(QBrush(col)); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(QRectF(x, y, bar_w, bar_h))
            painter.setPen(QPen(QColor(245,248,255,210), 1.0)); painter.drawText(QPointF(box.left()+4.0, box.top()+10.0), str(item.get("visualizer_preset_key", 'runtime_calendar_date', 'runtime_calendar_time', 'runtime_cpu_percent', 'runtime_memory_percent', 'runtime_disk_percent', 'runtime_network_down_bps', 'runtime_network_up_bps', 'runtime_network_down_kbps', 'runtime_network_up_kbps', 'runtime_sample_age_sec', 'runtime_weather_location', item.get("visualizer_style", "classic")) or "classic")[:12])
        except Exception:
            pass

    def _draw_widget_rect_marker(self, painter, item, is_selected=False):
        try:
            item = self._effect_overlay_full_desktop_rect_item(item)
            title = str(item.get("title") or item.get("type") or "Selected")
            corners = self._widget_projected_corners(item)
            if len(corners) < 4:
                return
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            if is_selected:
                painter.setBrush(QBrush(QColor(255, 190, 120, 58)))
                painter.setPen(QPen(QColor(255, 238, 160, 235), 3.0))
            else:
                painter.setBrush(QBrush(QColor(130, 180, 255, 18)))
                painter.setPen(QPen(QColor(150, 205, 255, 95), 1.2))
            painter.drawPath(path)
            try:
                self._draw_clock_widget_preview_marker(painter, item, corners, is_selected)
            except Exception:
                pass
            try:
                self._draw_system_network_widget_preview_marker(painter, item, corners, is_selected)
            except Exception:
                pass
            try:
                self._draw_runtime_widget_metric_overlay(painter, item, corners, is_selected)
            except Exception:
                pass
            try:
                self._draw_remaining_normal_widget_data_preview_marker(painter, item, corners, is_selected)
            except Exception:
                pass
            try:
                self._draw_visualizer_widget_preview_marker(painter, item, corners, is_selected)
            except Exception:
                pass
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            painter.setPen(QPen(QColor(255, 240, 220, 235) if is_selected else QColor(210, 230, 255, 150), 1.0))
            angle = float(item.get("rotation", 0.0))
            suffix = f"  {angle:.0f}°" if abs(angle) > 0.01 else ""
            painter.drawText(QPointF(center.x() + 8.0, center.y() - 8.0), title + suffix)
            if is_selected and str(item.get("type", "")) != "effects_overlay" and self.is_desktop_locked():
                handle_center = corners[2]
                handle_size = 18.0
                handle_rect = QRectF(
                    handle_center.x() - handle_size * 0.5,
                    handle_center.y() - handle_size * 0.5,
                    handle_size,
                    handle_size,
                )
                painter.setBrush(QBrush(QColor(120, 255, 170, 245)))
                painter.setPen(QPen(QColor(10, 45, 25, 245), 2.2))
                try:
                    painter.drawRoundedRect(handle_rect, 4.0, 4.0)
                except Exception:
                    painter.drawRect(handle_rect)
                painter.setPen(QPen(QColor(10, 45, 25, 245), 1.6))
                painter.drawLine(QPointF(handle_rect.left() + 4.0, handle_rect.bottom() - 5.0), QPointF(handle_rect.right() - 4.0, handle_rect.bottom() - 5.0))
                painter.drawLine(QPointF(handle_rect.right() - 5.0, handle_rect.top() + 4.0), QPointF(handle_rect.right() - 5.0, handle_rect.bottom() - 4.0))
                self._draw_widget_rotation_handle(painter, item, corners)
        except Exception:
            pass

    def _selected_widget_type(self):
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            return str(selected.get("type", ""))
        except Exception:
            return ""

    def _is_effect_overlay_selected(self):
        try:
            if self._selected_widget_type() == "effects_overlay":
                return True
            preview_selected_index = getattr(self, "_preview_selected_widget_index", None)
            if preview_selected_index is not None:
                preview_selected_index = int(preview_selected_index)
                for item in self._raw_widget_rect_states():
                    if int(item.get("index", -999999)) == preview_selected_index:
                        return str(item.get("type", "")) == "effects_overlay"
        except Exception:
            pass
        return False

    def _is_normal_widget_selected(self):
        selected_type = self._selected_widget_type()
        return bool(selected_type) and selected_type != "effects_overlay"

    # Phase 24A-1: common realtime-preview path for non Effects Overlay widgets.
    NORMAL_WIDGET_PREVIEW_COMMON_FIELDS = ("title", "color", "bg", "text", "font_size", "cpu_color", "memory_color", "disk_color", "network_down_color", "network_up_color", 'visualizer_flip_vertical', 'visualizer_peak_bar_enabled', 'visualizer_glow_enabled', 'visualizer_bar_width_scale', 'visualizer_orientation', 'visualizer_style', 'visualizer_shadow_enabled', 'visualizer_shadow_offset_x', 'visualizer_shadow_offset_y', 'visualizer_shadow_strength', 'visualizer_shadow_opacity', 'visualizer_shadow_depth', 'visualizer_shadow_blur', 'visualizer_frame_rate_enabled', 'visualizer_frame_rate', "visualizer_preset_key", 'weather_location', 'jshtml_mode', 'jshtml_entry', 'jshtml_package_name', 'jshtml_package_version', 'jshtml_permissions_json', 'jshtml_instance_id', 'runtime_calendar_date', 'runtime_calendar_time', 'runtime_cpu_percent', 'runtime_memory_percent', 'runtime_disk_percent', 'runtime_network_down_bps', 'runtime_network_up_bps', 'runtime_network_down_kbps', 'runtime_network_up_kbps', 'runtime_sample_age_sec', 'runtime_weather_location', 'runtime_volume_available', 'runtime_volume_percent', 'runtime_volume_muted', 'runtime_media_available', 'runtime_media_title', 'runtime_media_artist', 'runtime_media_album', 'runtime_media_app_id', 'runtime_media_playback_status', 'runtime_media_updated_at')
    NORMAL_WIDGET_PREVIEW_GEOMETRY_FIELDS = ("x", "y", "w", "h", "rotation", "rotation_degrees")

    def _normal_widget_preview_field_names(self):
        try:
            return set(self.NORMAL_WIDGET_PREVIEW_COMMON_FIELDS) | set(self.NORMAL_WIDGET_PREVIEW_GEOMETRY_FIELDS)
        except Exception:
            return {
                "x", "y", "w", "h", "rotation", "rotation_degrees",
                "title", "color", "bg", "text", "font_size",
                "cpu_color", "memory_color", "disk_color",
                "network_down_color", "network_up_color",
                "visualizer_flip_vertical", "visualizer_peak_bar_enabled", "visualizer_glow_enabled",
                "visualizer_bar_width_scale", "visualizer_orientation", "visualizer_style",
                "visualizer_preset_key", "visualizer_shadow_enabled", "visualizer_shadow_offset_x",
                "visualizer_shadow_offset_y", "visualizer_shadow_strength", "visualizer_shadow_opacity",
                "visualizer_shadow_depth", "visualizer_shadow_blur",
                "visualizer_frame_rate_enabled", "visualizer_frame_rate",
            }

    def _normal_widget_preview_selected_item(self, widget_index=None):
        try:
            if widget_index is None:
                selected = dict(dict(getattr(self, "_preview_state", {}) or {}).get("selected", {}) or {})
                widget_index = int(selected.get("index", getattr(self, "_preview_selected_widget_index", -1)))
            else:
                widget_index = int(widget_index)
            if widget_index < 0:
                return None
            pending = dict(getattr(self, "_pending_widget_rects", {}) or {}).get(widget_index)
            if pending is not None:
                item = dict(pending or {})
            else:
                item = None
                for candidate in self._raw_widget_rect_states():
                    candidate = dict(candidate or {})
                    if int(candidate.get("index", -999999)) == widget_index:
                        item = candidate
                        break
                if item is None:
                    selected = dict(dict(getattr(self, "_preview_state", {}) or {}).get("selected", {}) or {})
                    if int(selected.get("index", -999999)) == widget_index:
                        item = selected
            if not item or str(item.get("type", "")) == "effects_overlay":
                return None
            item["index"] = widget_index
            return item
        except Exception:
            return None

    def _normal_widget_preview_coerce_value(self, key, value, current=None):
        try:
            key = str(key or "")
            if key in ("x", "y"):
                return int(round(float(value)))
            if key in ("w", "h"):
                return max(24, int(round(float(value))))
            if key in ("rotation", "rotation_degrees"):
                return float(value)
            if key == "font_size":
                return max(1, min(512, int(round(float(value)))))
            if key in ("title", "color", "bg", "text", "cpu_color", "memory_color", "disk_color", "network_down_color", "network_up_color"):
                return str(value if value is not None else "")
            if key in ("visualizer_orientation", "visualizer_style", "visualizer_preset_key", "weather_location", "jshtml_mode", "jshtml_entry", "jshtml_package_name", "jshtml_package_version", "jshtml_permissions_json", "jshtml_instance_id", "runtime_calendar_date", "runtime_calendar_time", "runtime_weather_location", "runtime_media_title", "runtime_media_artist", "runtime_media_album", "runtime_media_app_id", "runtime_media_playback_status", "runtime_media_updated_at"):
                return str(value if value is not None else "")
            if key in ("visualizer_flip_vertical", "visualizer_peak_bar_enabled", "visualizer_glow_enabled", "visualizer_shadow_enabled", "visualizer_frame_rate_enabled", "runtime_volume_available", "runtime_volume_muted", "runtime_media_available"):
                return bool(value)
            if key == "visualizer_frame_rate":
                return max(1, min(240, int(round(float(value)))))
            if key in ("runtime_cpu_percent", "runtime_memory_percent", "runtime_disk_percent", "runtime_network_down_bps", "runtime_network_up_bps", "runtime_network_down_kbps", "runtime_network_up_kbps", "runtime_sample_age_sec", "runtime_volume_percent"):
                try:
                    return float(value)
                except Exception:
                    return 0.0
            if key in ("visualizer_bar_width_scale", "visualizer_shadow_offset_x", "visualizer_shadow_offset_y", "visualizer_shadow_strength", "visualizer_shadow_opacity", "visualizer_shadow_depth", "visualizer_shadow_blur"):
                return float(value)
        except Exception:
            pass
        try:
            return current
        except Exception:
            return value

    def _is_clock_widget_preview_item(self, item):
        try:
            return str(dict(item or {}).get("type", "")).strip().lower() == "clock"
        except Exception:
            return False

    def apply_clock_widget_preview_update(self, updates, widget_index=None):
        """Phase 24A-2: route clock property changes into the normal-widget preview path.

        Only the selected clock widget is affected.  Effects Overlay and other widget
        types are ignored so this remains a narrow smoke-test layer above Phase 24A-1.
        """
        try:
            if not isinstance(updates, dict) or not updates:
                return False
            item = self._normal_widget_preview_selected_item(widget_index)
            if not self._is_clock_widget_preview_item(item):
                return False
            common_updates = {}
            for key in ("x", "y", "w", "h", "rotation", "rotation_degrees", "title", "color", "bg", "text", "font_size"):
                if key in updates:
                    common_updates[key] = updates.get(key)
            changed = False
            if common_updates:
                changed = bool(self.apply_normal_widget_preview_update(common_updates, int(dict(item).get("index", -1)))) or changed
            # clock_show_digital is clock-specific, so keep it out of the common helper.
            if "clock_show_digital" in updates:
                item = self._normal_widget_preview_selected_item(widget_index)
                if not self._is_clock_widget_preview_item(item):
                    return changed
                value = bool(updates.get("clock_show_digital"))
                item["clock_show_digital"] = value
                idx = int(item.get("index", -1))
                if idx >= 0:
                    pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                    pending_map[idx] = dict(item)
                    self._pending_widget_rects = pending_map
                    self._pending_widget_rect = dict(item)
                    self._preview_selected_widget_index = idx
                    state = dict(getattr(self, "_preview_state", {}) or {})
                    widgets = [dict(w or {}) for w in list(state.get("widgets", []) or []) if isinstance(w, dict)]
                    replaced = False
                    for i, candidate in enumerate(widgets):
                        try:
                            if int(candidate.get("index", -999999)) == idx:
                                widgets[i] = dict(item)
                                replaced = True
                                break
                        except Exception:
                            pass
                    if not replaced:
                        widgets.append(dict(item))
                    state["widgets"] = widgets
                    state["selected"] = dict(item)
                    self._preview_state = state
                    changed = True
            if changed:
                try:
                    self._drag_notice = "Clock widget preview pending / Apply or Save to persist"
                    self.update()
                except Exception:
                    pass
            return bool(changed)
        except Exception:
            return False

    def apply_normal_widget_preview_update(self, updates, widget_index=None):
        """Apply common non-Effects-Overlay widget fields to 3D preview pending state only.

        This is intentionally a small Phase 24A-1 bridge.  It does not save by
        itself and it does not touch Effects Overlay template-effect logic.
        Apply / Save continues to flow through pending_preview_changes().
        """
        try:
            if not isinstance(updates, dict) or not updates:
                return False
            item = self._normal_widget_preview_selected_item(widget_index)
            if not item:
                return False
            allowed = self._normal_widget_preview_field_names()
            changed = False
            for key, value in dict(updates or {}).items():
                key = str(key or "")
                if key not in allowed:
                    continue
                item[key] = self._normal_widget_preview_coerce_value(key, value, item.get(key))
                changed = True
            if not changed:
                return False
            if "rotation_degrees" in item and "rotation" not in item:
                item["rotation"] = float(item.get("rotation_degrees", 0.0))
            if "rotation" in item:
                item["rotation_degrees"] = float(item.get("rotation", item.get("rotation_degrees", 0.0)))
            idx = int(item.get("index", -1))
            if idx < 0:
                return False
            pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
            pending_map[idx] = dict(item)
            self._pending_widget_rects = pending_map
            self._pending_widget_rect = dict(item)
            self._preview_selected_widget_index = idx
            state = dict(getattr(self, "_preview_state", {}) or {})
            widgets = [dict(w or {}) for w in list(state.get("widgets", []) or []) if isinstance(w, dict)]
            replaced = False
            for i, candidate in enumerate(widgets):
                try:
                    if int(candidate.get("index", -999999)) == idx:
                        widgets[i] = dict(item)
                        replaced = True
                        break
                except Exception:
                    pass
            if not replaced:
                widgets.append(dict(item))
            state["widgets"] = widgets
            state["selected"] = dict(item)
            self._preview_state = state
            try:
                self._drag_notice = "Widget preview pending / Apply or Save to persist"
                self.update()
            except Exception:
                pass
            try:
                self._notify_integrated_selection_bar_changed()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _should_show_effect_objects(self):
        # Effect handles/markers are only shown while an Effects Overlay widget is selected.
        return self._is_effect_overlay_selected()

    def _raw_widget_rect_states(self):
        state = dict(getattr(self, "_preview_state", {}) or {})
        widgets = [dict(item or {}) for item in list(state.get("widgets", []) or []) if isinstance(item, dict)]
        try:
            pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
            for pending_index, pending_item in pending_map.items():
                pending_item = dict(pending_item or {})
                pending_index = int(pending_item.get("index", pending_index))
                replaced = False
                for i, item in enumerate(widgets):
                    if int(item.get("index", -999999)) == pending_index:
                        widgets[i] = pending_item
                        replaced = True
                        break
                if not replaced:
                    widgets.append(pending_item)
        except Exception:
            pass
        pending = getattr(self, "_pending_widget_rect", None)
        if pending is not None:
            try:
                pending = dict(pending or {})
                pending_index = int(pending.get("index", -1))
                replaced = False
                for i, item in enumerate(widgets):
                    if int(item.get("index", -999999)) == pending_index:
                        widgets[i] = pending
                        replaced = True
                        break
                if not replaced:
                    widgets.append(pending)
            except Exception:
                pass
        return widgets

    def _all_widget_rect_states(self):
        # Visible/editable widgets for the current mode.  This remains mode-filtered
        # so normal editing does not show full Effects Overlay controls and vice versa.
        widgets = list(self._raw_widget_rect_states())
        try:
            if self._is_effect_overlay_selected():
                widgets = [item for item in widgets if str(item.get("type", "")) == "effects_overlay"]
            elif self._is_normal_widget_selected():
                widgets = [item for item in widgets if str(item.get("type", "")) != "effects_overlay"]
        except Exception:
            pass
        return widgets

    def _hidden_widget_rect_states_for_selection(self):
        # Faint selection-only outlines for widgets hidden by the current edit mode.
        # Without this, selecting a different kind of widget directly from the 3D
        # preview becomes impossible after the UI cleanup phase.
        try:
            raw = list(self._raw_widget_rect_states())
            visible_indexes = {int(item.get("index", -999999)) for item in self._all_widget_rect_states()}
            return [item for item in raw if int(item.get("index", -999999)) not in visible_indexes]
        except Exception:
            return []

    def _draw_widget_selection_ghost_marker(self, painter, item):
        try:
            path = self._widget_rect_path(item)
            if path is None:
                return
            painter.setBrush(QBrush(QColor(80, 130, 180, 10)))
            pen = QPen(QColor(150, 205, 255, 42), 1.0)
            try:
                pen.setStyle(Qt.PenStyle.DashLine)
            except Exception:
                pass
            painter.setPen(pen)
            painter.drawPath(path)
            corners = self._widget_projected_corners(item)
            if len(corners) >= 4:
                center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
                label = str(item.get("title") or item.get("type") or "Widget")
                painter.setPen(QPen(QColor(190, 220, 255, 92), 1.0))
                painter.drawText(QPointF(center.x() + 8.0, center.y() + 10.0), label)
        except Exception:
            pass

    def _draw_all_widget_rect_markers(self, painter):
        try:
            selected = dict(self._current_widget_rect_state() or {})
            selected_index = int(selected.get("index", -1)) if selected else -1
            if self.is_desktop_locked():
                for item in self._hidden_widget_rect_states_for_selection():
                    idx = int(item.get("index", -999999))
                    if idx != selected_index:
                        self._draw_widget_selection_ghost_marker(painter, item)
            for item in self._all_widget_rect_states():
                idx = int(item.get("index", -999999))
                if idx == selected_index:
                    continue
                self._draw_widget_rect_marker(painter, item, False)
            if selected:
                self._draw_widget_rect_marker(painter, selected, True)
        except Exception:
            pass

    def _widget_hit_candidates(self, pos):
        candidates = []
        try:
            # Selection hit-testing must consider all widgets, including the faint
            # selection-only outlines hidden by the current editing mode.
            for item in self._raw_widget_rect_states():
                path = self._widget_rect_path(item)
                if path is not None and path.contains(QPointF(float(pos.x()), float(pos.y()))):
                    candidates.append(dict(item))
        except Exception:
            pass
        try:
            # Later canvas entries are visually more front-like in the existing layer model.
            candidates.sort(key=lambda it: int(it.get("index", 0)), reverse=True)
        except Exception:
            pass
        return candidates

    def _pick_widget_hit_candidate(self, pos):
        candidates = self._widget_hit_candidates(pos)
        if not candidates:
            self._widget_hit_cycle_key = None
            self._widget_hit_cycle_pos = 0
            return None
        try:
            rounded = (int(float(pos.x()) // 12), int(float(pos.y()) // 12), tuple(int(c.get("index", -1)) for c in candidates))
        except Exception:
            rounded = None
        if rounded == getattr(self, "_widget_hit_cycle_key", None):
            self._widget_hit_cycle_pos = (int(getattr(self, "_widget_hit_cycle_pos", 0)) + 1) % len(candidates)
        else:
            self._widget_hit_cycle_key = rounded
            self._widget_hit_cycle_pos = 0
        return candidates[int(getattr(self, "_widget_hit_cycle_pos", 0)) % len(candidates)]

    def _notify_detail_layer_selection_from_preview(self, index):
        """Phase 24A-8j: sync 3D-touched widget selection to detail settings Layers.

        The preview widget may be hosted by either the standalone 3D window or an
        integrated panel.  Notify every reachable controller/window that knows how
        to select a widget index so the right-side detail Layers list follows the
        3D selection immediately.
        """
        notified = False
        try:
            index = int(index)
        except Exception:
            return False
        try:
            parent = self.parent()
        except Exception:
            parent = None
        candidates = []
        try:
            if parent is not None:
                candidates.append(parent)
        except Exception:
            pass
        try:
            if parent is not None and hasattr(parent, "_controller"):
                controller = parent._controller()
                if controller is not None:
                    candidates.append(controller)
        except Exception:
            pass
        try:
            if parent is not None and hasattr(parent, "parent"):
                parent_parent = parent.parent()
                if parent_parent is not None:
                    candidates.append(parent_parent)
                    controller = getattr(parent_parent, "controller", None)
                    if controller is not None:
                        candidates.append(controller)
        except Exception:
            pass
        seen = set()
        for target in candidates:
            try:
                if target is None:
                    continue
                key = id(target)
                if key in seen:
                    continue
                seen.add(key)
                if hasattr(target, "select_3d_preview_widget_index"):
                    target.select_3d_preview_widget_index(index)
                    notified = True
                elif hasattr(target, "select_widget_from_preview"):
                    target.select_widget_from_preview(index)
                    notified = True
            except Exception:
                pass
        return bool(notified)

    def _select_widget_from_preview(self, item):
        try:
            item = dict(item or {})
            idx = int(item.get("index", -1))
            if idx < 0:
                return
            self._preview_selected_widget_index = idx
            try:
                pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                if idx in pending_map:
                    item = dict(pending_map.get(idx) or item)
                    self._pending_widget_rect = dict(item)
                else:
                    pending = getattr(self, "_pending_widget_rect", None)
                    pending_index = int((pending or {}).get("index", -1)) if pending is not None else -1
                    if pending_index != idx:
                        self._pending_widget_rect = None
                self._widget_drag_start = None
                self._widget_drag_offset_unit = None
                self._widget_drag_start_pos = None
                self._widget_drag_jacobian = None
            except Exception:
                pass
            state = dict(getattr(self, "_preview_state", {}) or {})
            state["selected"] = dict(item)
            for widget_item in list(state.get("widgets", []) or []):
                if isinstance(widget_item, dict):
                    widget_item["selected"] = int(widget_item.get("index", -999999)) == idx
            self._preview_state = state
            try:
                if not self._notify_detail_layer_selection_from_preview(idx):
                    parent = self.parent()
                    if parent is not None and hasattr(parent, "select_widget_from_preview"):
                        parent.select_widget_from_preview(idx)
            except Exception:
                pass
        except Exception:
            pass

    def _current_widget_rect_state(self):
        pending = getattr(self, "_pending_widget_rect", None)
        if pending is not None:
            return dict(pending or {})
        state = dict(getattr(self, "_preview_state", {}) or {})
        return dict(state.get("selected", {}) or {})

    def _widget_rect_path(self, item=None):
        item = dict(item or self._current_widget_rect_state() or {})
        if not item:
            return None
        try:
            corners = self._widget_projected_corners(item)
            if len(corners) < 4:
                return None
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            return path
        except Exception:
            return None

    def _hit_widget_rect_marker(self, pos):
        try:
            return bool(self._widget_hit_candidates(pos))
        except Exception:
            return False

    def _hit_widget_rotation_handle(self, pos):
        try:
            point = self._widget_rotation_handle_center()
            if point is None:
                return False
            dx = float(pos.x()) - float(point.x())
            dy = float(pos.y()) - float(point.y())
            return (dx * dx + dy * dy) <= 30.0 ** 2
        except Exception:
            return False

    def _begin_widget_rotate_drag(self, pos):
        try:
            item = dict(self._current_widget_rect_state() or {})
            if not item:
                return
            corners = self._widget_projected_corners(item)
            if len(corners) < 4:
                return
            center = QPointF(sum(p.x() for p in corners) / 4.0, sum(p.y() for p in corners) / 4.0)
            self._widget_drag_start = dict(item)
            self._widget_rotate_center = center
            self._widget_rotate_start_angle = float(item.get("rotation", 0.0))
            self._widget_rotate_start_pointer_angle = math.degrees(math.atan2(float(pos.y()) - center.y(), float(pos.x()) - center.x()))
        except Exception:
            self._widget_drag_start = None
            self._widget_rotate_center = None
            self._widget_rotate_start_angle = None
            self._widget_rotate_start_pointer_angle = None

    def _set_temp_widget_rotation_from_pos(self, pos):
        try:
            item = dict(getattr(self, "_widget_drag_start", None) or self._current_widget_rect_state() or {})
            center = getattr(self, "_widget_rotate_center", None)
            start_angle = getattr(self, "_widget_rotate_start_angle", None)
            start_pointer = getattr(self, "_widget_rotate_start_pointer_angle", None)
            if not item or center is None or start_angle is None or start_pointer is None:
                return
            pointer = math.degrees(math.atan2(float(pos.y()) - center.y(), float(pos.x()) - center.x()))
            angle = float(start_angle) + (pointer - float(start_pointer))
            while angle <= -180.0:
                angle += 360.0
            while angle > 180.0:
                angle -= 360.0
            # Snap to 5-degree increments while Shift is unavailable in this isolated test.
            if self.is_snap_enabled():
                angle = round(angle / 15.0) * 15.0
            if abs(angle) < 0.75:
                angle = 0.0
            item["rotation"] = float(angle)
            self._pending_widget_rect = dict(item)
            try:
                pending_idx = int(item.get("index", -1))
                if pending_idx >= 0:
                    pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                    pending_map[pending_idx] = dict(item)
                    self._pending_widget_rects = pending_map
                self._preview_selected_widget_index = pending_idx
            except Exception:
                pass
            state = dict(getattr(self, "_preview_state", {}) or {})
            state["selected"] = dict(item)
            self._preview_state = state
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Widget rotation preview-only{snap_tag} angle={angle:.1f}°"
            self.update()
        except Exception:
            pass

    def reset_selected_widget_rotation_preview(self):
        try:
            item = dict(self._current_widget_rect_state() or {})
            if not item or str(item.get("type", "")) == "effects_overlay":
                self._drag_notice = "Select a normal widget before resetting rotation"
                self.update()
                return False
            item["rotation"] = 0.0
            self._pending_widget_rect = dict(item)
            try:
                pending_idx = int(item.get("index", -1))
                if pending_idx >= 0:
                    pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                    pending_map[pending_idx] = dict(item)
                    self._pending_widget_rects = pending_map
                self._preview_selected_widget_index = pending_idx
            except Exception:
                pass
            state = dict(getattr(self, "_preview_state", {}) or {})
            state["selected"] = dict(item)
            self._preview_state = state
            self._drag_notice = "Widget rotation reset preview-only angle=0.0° / pending apply"
            self.update()
            return True
        except Exception:
            return False

    def _widget_resize_handle_center(self, item=None):
        item = dict(item or self._current_widget_rect_state() or {})
        if not item or str(item.get("type", "")) == "effects_overlay":
            return None
        try:
            # The visual resize handle is drawn at the rotated bottom-right corner
            # (corners[2]).  Hit-testing must use the same projected corner;
            # otherwise a rotated widget can show the handle in one place while the
            # actual hit target remains at the unrotated bottom-right point.
            corners = self._widget_projected_corners(item)
            if len(corners) < 3:
                return None
            return corners[2]
        except Exception:
            return None

    def _hit_widget_resize_handle(self, pos):
        try:
            point = self._widget_resize_handle_center()
            if point is None:
                return False
            dx = float(pos.x()) - float(point.x())
            dy = float(pos.y()) - float(point.y())
            return (dx * dx + dy * dy) <= 28.0 ** 2
        except Exception:
            return False

    def _begin_widget_resize_drag(self, pos):
        try:
            item = dict(self._current_widget_rect_state() or {})
            if not item:
                return
            w = max(1.0, float(item.get("w", 80.0)))
            h = max(1.0, float(item.get("h", 80.0)))

            base_corners = self._widget_projected_corners(item)
            if len(base_corners) < 3:
                return
            base_p = base_corners[2]

            # Estimate how the rotated visual bottom-right handle moves when the
            # widget width/height change by one canvas pixel.  This local Jacobian
            # follows the widget's rotation, so resize remains possible after rotate.
            eps_w = max(1.0, min(12.0, w * 0.02))
            eps_h = max(1.0, min(12.0, h * 0.02))
            item_w = dict(item)
            item_h = dict(item)
            item_w["w"] = w + eps_w
            item_h["h"] = h + eps_h
            w_corners = self._widget_projected_corners(item_w)
            h_corners = self._widget_projected_corners(item_h)
            if len(w_corners) < 3 or len(h_corners) < 3:
                return
            wp = w_corners[2]
            hp = h_corners[2]
            j11 = (float(wp.x()) - float(base_p.x())) / eps_w
            j21 = (float(wp.y()) - float(base_p.y())) / eps_w
            j12 = (float(hp.x()) - float(base_p.x())) / eps_h
            j22 = (float(hp.y()) - float(base_p.y())) / eps_h
            self._widget_drag_start = dict(item)
            self._widget_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._widget_drag_jacobian = (j11, j12, j21, j22)
        except Exception:
            self._widget_drag_start = None
            self._widget_drag_start_pos = None
            self._widget_drag_jacobian = None

    def _set_temp_widget_size_from_pos(self, pos):
        try:
            item = dict(getattr(self, "_widget_drag_start", None) or self._current_widget_rect_state() or {})
            if not item:
                return
            cw = max(1.0, float(item.get("canvas_w", 1920.0)))
            ch = max(1.0, float(item.get("canvas_h", 1080.0)))
            x = int(round(float(item.get("x", 0.0))))
            y = int(round(float(item.get("y", 0.0))))
            start_w = max(1.0, float(item.get("w", 80.0)))
            start_h = max(1.0, float(item.get("h", 80.0)))
            start_pos = getattr(self, "_widget_drag_start_pos", None)
            jac = getattr(self, "_widget_drag_jacobian", None)
            if start_pos is not None and jac is not None:
                dx_screen = float(pos.x()) - float(start_pos.x())
                dy_screen = float(pos.y()) - float(start_pos.y())
                j11, j12, j21, j22 = jac
                det = j11 * j22 - j12 * j21
                if abs(det) > 1e-6:
                    dw = (dx_screen * j22 - j12 * dy_screen) / det
                    dh = (j11 * dy_screen - dx_screen * j21) / det
                else:
                    dw = 0.0
                    dh = 0.0
                new_w = int(round(start_w + dw))
                new_h = int(round(start_h + dh))
            else:
                new_w = int(round(start_w))
                new_h = int(round(start_h))
            min_w = 24
            min_h = 24
            max_w = max(min_w, int(cw - x))
            max_h = max(min_h, int(ch - y))
            new_w = self._snap_int_value(new_w, 20)
            new_h = self._snap_int_value(new_h, 20)
            new_w = int(max(min_w, min(max_w, new_w)))
            new_h = int(max(min_h, min(max_h, new_h)))
            x, y = self._clamp_widget_rect_to_canvas(x, y, new_w, new_h, cw, ch)
            item["x"] = int(x)
            item["y"] = int(y)
            item["w"] = int(new_w)
            item["h"] = int(new_h)
            self._pending_widget_rect = dict(item)
            try:
                pending_idx = int(item.get("index", -1))
                if pending_idx >= 0:
                    pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                    pending_map[pending_idx] = dict(item)
                    self._pending_widget_rects = pending_map
                self._preview_selected_widget_index = pending_idx
            except Exception:
                pass
            state = dict(getattr(self, "_preview_state", {}) or {})
            state["selected"] = dict(item)
            self._preview_state = state
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Widget resize preview-only{snap_tag} w={new_w} h={new_h}"
            self.update()
        except Exception:
            pass

    def _begin_widget_move_drag(self, pos):
        try:
            item = dict(self._current_widget_rect_state() or {})
            if not item:
                return
            cw = max(1.0, float(item.get("canvas_w", 1920.0)))
            ch = max(1.0, float(item.get("canvas_h", 1080.0)))
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            w = max(1.0, float(item.get("w", 80.0)))
            h = max(1.0, float(item.get("h", 80.0)))
            center_u = max(0.0, min(1.0, (x + w * 0.5) / cw))
            center_v = max(0.0, min(1.0, (y + h * 0.5) / ch))
            base_x, base_z = self._unit_to_plane(center_u, center_v)
            base_p, _ = self._project_point(base_x, 8.0, base_z)
            du = max(1.0 / cw, 0.0015)
            dv = max(1.0 / ch, 0.0015)
            px_x, px_z = self._unit_to_plane(min(1.0, center_u + du), center_v)
            py_x, py_z = self._unit_to_plane(center_u, min(1.0, center_v + dv))
            px_p, _ = self._project_point(px_x, 8.0, px_z)
            py_p, _ = self._project_point(py_x, 8.0, py_z)
            j11 = (float(px_p.x()) - float(base_p.x())) / (du * cw)
            j21 = (float(px_p.y()) - float(base_p.y())) / (du * cw)
            j12 = (float(py_p.x()) - float(base_p.x())) / (dv * ch)
            j22 = (float(py_p.y()) - float(base_p.y())) / (dv * ch)
            self._widget_drag_start = dict(item)
            self._widget_drag_offset_unit = None
            self._widget_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._widget_drag_jacobian = (j11, j12, j21, j22)
        except Exception:
            self._widget_drag_start = None
            self._widget_drag_offset_unit = None
            self._widget_drag_start_pos = None
            self._widget_drag_jacobian = None

    def _clamp_widget_rect_to_canvas(self, x, y, w, h, cw, ch):
        try:
            x = int(round(float(x)))
            y = int(round(float(y)))
            w = max(1, int(round(float(w))))
            h = max(1, int(round(float(h))))
            cw = max(1, int(round(float(cw))))
            ch = max(1, int(round(float(ch))))
            # Keep the widget footprint inside the pseudo desktop whenever it can fit.
            # The previous partial-offscreen clamp allowed corners to exceed the 0..1
            # plane range; _unit_to_plane then clamped each corner independently, which
            # made large widgets visually collapse/shrink near the lower edge and could
            # make hit-testing appear to disappear.
            if w <= cw:
                min_x = 0
                max_x = cw - w
            else:
                # Oversized widget: pin the left edge to the canvas origin so the
                # projected footprint remains stable instead of overflowing both sides.
                min_x = 0
                max_x = 0
            if h <= ch:
                min_y = 0
                max_y = ch - h
            else:
                # Oversized widget: pin the top edge to the canvas origin.
                min_y = 0
                max_y = 0
            return int(max(min_x, min(max_x, x))), int(max(min_y, min(max_y, y)))
        except Exception:
            return int(x), int(y)

    def _set_temp_widget_rect_from_pos(self, pos):
        try:
            item = dict(getattr(self, "_widget_drag_start", None) or self._current_widget_rect_state() or {})
            if not item:
                return
            cw = max(1.0, float(item.get("canvas_w", 1920.0)))
            ch = max(1.0, float(item.get("canvas_h", 1080.0)))
            w = max(1.0, float(item.get("w", 80.0)))
            h = max(1.0, float(item.get("h", 80.0)))
            start_x = float(item.get("x", 0.0))
            start_y = float(item.get("y", 0.0))
            start_pos = getattr(self, "_widget_drag_start_pos", None)
            jac = getattr(self, "_widget_drag_jacobian", None)
            if start_pos is not None and jac is not None:
                dx_screen = float(pos.x()) - float(start_pos.x())
                dy_screen = float(pos.y()) - float(start_pos.y())
                j11, j12, j21, j22 = jac
                det = j11 * j22 - j12 * j21
                if abs(det) > 1e-6:
                    dx_canvas = (dx_screen * j22 - j12 * dy_screen) / det
                    dy_canvas = (j11 * dy_screen - dx_screen * j21) / det
                else:
                    dx_canvas = 0.0
                    dy_canvas = 0.0
                new_x = int(round(start_x + dx_canvas))
                new_y = int(round(start_y + dy_canvas))
            else:
                start_center_u = max(0.0, min(1.0, (start_x + w * 0.5) / cw))
                start_center_v = max(0.0, min(1.0, (start_y + h * 0.5) / ch))
                grab_u, grab_v = self._screen_to_unit_on_desktop(pos, start_center_u, start_center_v)
                center_u = max(0.0, min(1.0, grab_u))
                center_v = max(0.0, min(1.0, grab_v))
                new_x = int(round(center_u * cw - w * 0.5))
                new_y = int(round(center_v * ch - h * 0.5))
            new_x = self._snap_int_value(new_x, 20)
            new_y = self._snap_int_value(new_y, 20)
            new_x, new_y = self._clamp_widget_rect_to_canvas(new_x, new_y, w, h, cw, ch)
            item["x"] = new_x
            item["y"] = new_y
            item["w"] = int(round(w))
            item["h"] = int(round(h))
            self._pending_widget_rect = dict(item)
            try:
                pending_idx = int(item.get("index", -1))
                if pending_idx >= 0:
                    pending_map = dict(getattr(self, "_pending_widget_rects", {}) or {})
                    pending_map[pending_idx] = dict(item)
                    self._pending_widget_rects = pending_map
                self._preview_selected_widget_index = pending_idx
            except Exception:
                pass
            state = dict(getattr(self, "_preview_state", {}) or {})
            state["selected"] = dict(item)
            self._preview_state = state
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Widget preview-only{snap_tag} x={new_x} y={new_y}"
            self.update()
        except Exception:
            pass

    def _event_pos(self, event):
        try:
            return event.position().toPoint()
        except Exception:
            try:
                return event.pos()
            except Exception:
                return QPoint(0, 0)

    def _current_sun_unit(self):
        if not self._should_show_effect_objects():
            return (0.22, 0.22, False)
        state = dict(getattr(self, "_preview_state", {}) or {})
        effect = dict(state.get("effect", {}) or {})
        sun_visible = bool(effect.get("sun_visible", False))
        if not sun_visible:
            # No demo fallback hit target in real editing mode.  Invisible demo
            # hit targets could create a pending Sun just by clicking the pseudo desktop.
            return (0.22, 0.22, False)
        return (
            max(0.0, min(1.0, float(effect.get("sun_x", 0.22)))),
            max(0.0, min(1.0, float(effect.get("sun_y", 0.22)))),
            sun_visible,
        )

    def _sun_screen_center(self):
        sx, sy, visible = self._current_sun_unit()
        if not visible:
            return None
        plane_x, plane_z = self._unit_to_plane(sx, sy)
        point, scale = self._project_point(plane_x, 14.0, plane_z)
        radius = max(9.0, 30.0 * scale)
        return point, radius

    def _hit_sun_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            item = self._sun_screen_center()
            if item is None:
                return False
            center, radius = item
            dx = float(pos.x()) - float(center.x())
            dy = float(pos.y()) - float(center.y())
            return (dx * dx + dy * dy) <= max(36.0, radius * 2.65) ** 2
        except Exception:
            return False

    def _screen_to_unit_on_desktop(self, pos, start_u=0.5, start_v=0.5):
        # Numeric inverse of _project_point for points on the preview desktop plane.
        # This is intentionally local to the isolated test and does not affect cfg/effects_json.
        try:
            target_x = float(pos.x())
            target_y = float(pos.y())
            u = max(0.0, min(1.0, float(start_u)))
            v = max(0.0, min(1.0, float(start_v)))
            eps = 0.002
            for _ in range(18):
                x, z = self._unit_to_plane(u, v)
                p, _scale = self._project_point(x, 14.0, z)
                fx = float(p.x()) - target_x
                fy = float(p.y()) - target_y
                if abs(fx) + abs(fy) < 0.35:
                    break
                x1, z1 = self._unit_to_plane(min(1.0, u + eps), v)
                pu, _ = self._project_point(x1, 14.0, z1)
                x2, z2 = self._unit_to_plane(u, min(1.0, v + eps))
                pv, _ = self._project_point(x2, 14.0, z2)
                j11 = (float(pu.x()) - float(p.x())) / eps
                j21 = (float(pu.y()) - float(p.y())) / eps
                j12 = (float(pv.x()) - float(p.x())) / eps
                j22 = (float(pv.y()) - float(p.y())) / eps
                det = j11 * j22 - j12 * j21
                if abs(det) < 1e-6:
                    break
                du = (-fx * j22 + j12 * fy) / det
                dv = (j21 * fx - j11 * fy) / det
                u = max(0.0, min(1.0, u + du))
                v = max(0.0, min(1.0, v + dv))
            return u, v
        except Exception:
            return start_u, start_v

    def _set_temp_sun_unit(self, x_ratio, y_ratio):
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect["sun_visible"] = True
            sx = self._snap_float_value(float(x_ratio), 0.02)
            sy = self._snap_float_value(float(y_ratio), 0.02)
            effect["sun_x"] = max(0.0, min(1.0, sx))
            effect["sun_y"] = max(0.0, min(1.0, sy))
            state["effect"] = effect
            self._preview_state = state
            self._pending_sun_unit = (effect["sun_x"], effect["sun_y"])
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Sun preview-only{snap_tag} x={effect['sun_x']:.3f} y={effect['sun_y']:.3f}"
            self.update()
        except Exception:
            pass

    def current_preview_sun_unit(self):
        pending = getattr(self, "_pending_sun_unit", None)
        if pending is not None:
            try:
                return max(0.0, min(1.0, float(pending[0]))), max(0.0, min(1.0, float(pending[1]))), True
            except Exception:
                pass
        sx, sy, visible = self._current_sun_unit()
        return sx, sy, visible

    def clear_pending_sun_unit(self):
        self._pending_sun_unit = None
        try:
            self.update()
        except Exception:
            pass

    def _current_moon_unit(self):
        if not self._should_show_effect_objects():
            return (0.78, 0.18, False)
        state = dict(getattr(self, "_preview_state", {}) or {})
        effect = dict(state.get("effect", {}) or {})
        moon_visible = bool(effect.get("moon_visible", False))
        if not moon_visible:
            # No demo fallback hit target in real editing mode.
            return (0.78, 0.18, False)
        return (
            max(0.0, min(1.0, float(effect.get("moon_x", 0.78)))),
            max(0.0, min(1.0, float(effect.get("moon_y", 0.18)))),
            moon_visible,
        )

    def _moon_screen_center(self):
        mx, my, visible = self._current_moon_unit()
        if not visible:
            return None
        plane_x, plane_z = self._unit_to_plane(mx, my)
        point, scale = self._project_point(plane_x, 14.0, plane_z)
        radius = max(8.0, 24.0 * scale)
        return point, radius

    def _hit_moon_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            item = self._moon_screen_center()
            if item is None:
                return False
            center, radius = item
            dx = float(pos.x()) - float(center.x())
            dy = float(pos.y()) - float(center.y())
            return (dx * dx + dy * dy) <= max(34.0, radius * 2.65) ** 2
        except Exception:
            return False

    def _set_temp_moon_unit(self, x_ratio, y_ratio):
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect["moon_visible"] = True
            mx = self._snap_float_value(float(x_ratio), 0.02)
            my = self._snap_float_value(float(y_ratio), 0.02)
            effect["moon_x"] = max(0.0, min(1.0, mx))
            effect["moon_y"] = max(0.0, min(1.0, my))
            state["effect"] = effect
            self._preview_state = state
            self._pending_moon_unit = (effect["moon_x"], effect["moon_y"])
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Moon preview-only{snap_tag} x={effect['moon_x']:.3f} y={effect['moon_y']:.3f}"
            self.update()
        except Exception:
            pass

    def current_preview_moon_unit(self):
        pending = getattr(self, "_pending_moon_unit", None)
        if pending is not None:
            try:
                return max(0.0, min(1.0, float(pending[0]))), max(0.0, min(1.0, float(pending[1]))), True
            except Exception:
                pass
        mx, my, visible = self._current_moon_unit()
        return mx, my, visible

    def clear_pending_moon_unit(self):
        self._pending_moon_unit = None
        try:
            self.update()
        except Exception:
            pass

    def _puddle_preview_has_real_targets(self):
        """Return True only when Puddle is actually enabled in preview state.

        This intentionally ignores stale puddles_json-derived entries and stale
        pending puddle state when effect["puddle_visible"] is False. Otherwise a
        hidden/demo Puddle can steal clicks from Water Surface and may appear as if
        a demo puddle was created by touching the pseudo desktop.
        """
        if not self._should_show_effect_objects():
            return False
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            return bool(effect.get("puddle_visible", False))
        except Exception:
            return False

    def _clear_stale_puddle_preview_state_if_disabled(self):
        try:
            if self._puddle_preview_has_real_targets():
                return
            self._pending_puddle_state = None
            self._pending_puddle_states = {}
            self._selected_puddle_index = 0
        except Exception:
            pass

    def _current_puddle_state(self):
        if not self._should_show_effect_objects():
            return {"x": 0.50, "y": 0.84, "width": 0.20, "height": 0.08, "visible": False}
        state = dict(getattr(self, "_preview_state", {}) or {})
        effect = dict(state.get("effect", {}) or {})
        visible = bool(effect.get("puddle_visible", False))
        if not visible:
            # No demo fallback hit target in real editing mode.  Invisible demo
            # hit targets could create a pending Puddle just by clicking the pseudo desktop.
            return {"x": 0.50, "y": 0.84, "width": 0.20, "height": 0.08, "visible": False}
        return {
            "x": max(0.0, min(1.0, float(effect.get("puddle_x", 0.50)))),
            "y": max(0.0, min(1.0, float(effect.get("puddle_y", 0.84)))),
            "width": max(0.03, min(1.20, float(effect.get("puddle_width", 0.20)))),
            "height": max(0.015, min(0.70, float(effect.get("puddle_height", 0.08)))),
            "visible": visible,
        }

    def _all_puddle_states(self):
        if not self._should_show_effect_objects():
            return []
        if not self._puddle_preview_has_real_targets():
            self._clear_stale_puddle_preview_state_if_disabled()
            return []
        states = []
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            raw = list(effect.get("puddles", []) or [])
            for i, item in enumerate(raw):
                if not isinstance(item, dict):
                    continue
                if not bool(item.get("visible", True)):
                    continue
                states.append({
                    "index": int(item.get("index", i)),
                    "x": max(0.0, min(1.0, float(item.get("x", effect.get("puddle_x", 0.50))))),
                    "y": max(0.0, min(1.0, float(item.get("y", effect.get("puddle_y", 0.84))))),
                    "width": max(0.03, min(1.20, float(item.get("width", effect.get("puddle_width", 0.20))))),
                    "height": max(0.015, min(0.70, float(item.get("height", effect.get("puddle_height", 0.08))))),
                    "visible": True,
                })
        except Exception:
            states = []
        try:
            pending_items = dict(getattr(self, "_pending_puddle_states", {}) or {})
            pending = getattr(self, "_pending_puddle_state", None)
            if pending is not None:
                try:
                    pending = dict(pending or {})
                    pending_items[int(pending.get("index", getattr(self, "_selected_puddle_index", 0)))] = pending
                except Exception:
                    pending_items[0] = dict(pending or {})
            if pending_items:
                for idx, pending in sorted(pending_items.items(), key=lambda kv: int(kv[0])):
                    idx = int(idx)
                    pending = dict(pending or {})
                    pending["index"] = idx
                    pending["visible"] = bool(pending.get("visible", True))
                    if not bool(pending.get("visible", True)):
                        continue
                    replaced = False
                    for i, item in enumerate(states):
                        if int(item.get("index", -1)) == idx:
                            merged = dict(item or {})
                            merged.update(pending)
                            merged["visible"] = True
                            states[i] = merged
                            replaced = True
                            break
                    if not replaced:
                        states.append(pending)
            else:
                current = dict(self._current_puddle_state() or {})
                if bool(current.get("visible", False)):
                    current["index"] = 0
                    if states:
                        states[0] = current
                    else:
                        states = [current]
        except Exception:
            pass
        return [item for item in states if bool(item.get("visible", False))]

    def _current_selected_puddle_state(self):
        if not self._puddle_preview_has_real_targets():
            self._clear_stale_puddle_preview_state_if_disabled()
            return {"x": 0.50, "y": 0.84, "width": 0.20, "height": 0.08, "visible": False}
        try:
            selected_index = int(getattr(self, "_selected_puddle_index", 0))
            pending_map = dict(getattr(self, "_pending_puddle_states", {}) or {})
            if selected_index in pending_map:
                data = dict(pending_map.get(selected_index) or {})
                data["visible"] = bool(data.get("visible", True))
                return data
            pending = getattr(self, "_pending_puddle_state", None)
            if pending is not None:
                pending = dict(pending or {})
                if int(pending.get("index", selected_index)) == selected_index:
                    pending["visible"] = bool(pending.get("visible", True))
                    return pending
            for item in self._all_puddle_states():
                if int(item.get("index", -1)) == selected_index:
                    return dict(item)
        except Exception:
            pass
        return self._current_puddle_state()

    def _merge_pending_selected_puddle_into_effect(self, effect, pending):
        try:
            pending = dict(pending or {})
            idx = int(pending.get("index", 0))
            puddles = [dict(item or {}) for item in list(effect.get("puddles", []) or []) if isinstance(item, dict)]
            if idx < 0:
                idx = 0
            while len(puddles) <= idx:
                puddles.append({
                    "index": len(puddles),
                    "x": effect.get("puddle_x", 0.50),
                    "y": effect.get("puddle_y", 0.84),
                    "width": effect.get("puddle_width", 0.20),
                    "height": effect.get("puddle_height", 0.08),
                    "visible": True,
                })
            old = dict(puddles[idx] or {})
            old.update({
                "index": idx,
                "x": pending.get("x", old.get("x", effect.get("puddle_x", 0.50))),
                "y": pending.get("y", old.get("y", effect.get("puddle_y", 0.84))),
                "width": pending.get("width", old.get("width", effect.get("puddle_width", 0.20))),
                "height": pending.get("height", old.get("height", effect.get("puddle_height", 0.08))),
                "visible": bool(pending.get("visible", old.get("visible", True))),
            })
            puddles[idx] = old
            effect["puddles"] = puddles
            if idx == 0:
                effect["puddle_visible"] = True
                effect["puddle_x"] = old["x"]
                effect["puddle_y"] = old["y"]
                effect["puddle_width"] = old.get("width", effect.get("puddle_width", 0.20))
                effect["puddle_height"] = old.get("height", effect.get("puddle_height", 0.08))
        except Exception:
            pass
        return effect

    def _puddle_screen_ellipse(self, item=None):
        item = dict(item or self._current_puddle_state() or {})
        if not bool(item.get("visible", False)):
            return None
        px, pz = self._unit_to_plane(item.get("x", 0.50), item.get("y", 0.84))
        center, scale = self._project_point(px, 3.0, pz)
        rw = max(12.0, 360.0 * max(0.03, min(1.2, float(item.get("width", 0.20)))) * scale)
        rh = max(6.0, 210.0 * max(0.015, min(0.7, float(item.get("height", 0.08)))) * scale)
        return center, rw, rh

    def _puddle_hit_candidates(self, pos):
        candidates = []
        if not self._should_show_effect_objects() or not self._puddle_preview_has_real_targets():
            self._clear_stale_puddle_preview_state_if_disabled()
            return candidates
        try:
            for item in reversed(self._all_puddle_states()):
                ellipse = self._puddle_screen_ellipse(item)
                if ellipse is None:
                    continue
                center, rw, rh = ellipse
                dx = (float(pos.x()) - float(center.x())) / max(18.0, float(rw) * 1.25)
                dy = (float(pos.y()) - float(center.y())) / max(10.0, float(rh) * 1.65)
                if dx * dx + dy * dy <= 1.0:
                    candidates.append(dict(item))
        except Exception:
            pass
        return candidates

    def _pick_puddle_hit_candidate(self, pos):
        candidates = self._puddle_hit_candidates(pos)
        if not candidates:
            return None
        return candidates[0]

    def _select_puddle_preview_index(self, index):
        try:
            self._preview_selected_widget_index = None
            self._clear_ice_preview_selection("")
            self._clear_water_surface_preview_selection("")
            self._selected_puddle_index = max(0, int(index))
            self._drag_notice = f"Puddle {self._selected_puddle_index + 1} selected / display-only" if self._selected_puddle_index != 0 else "Puddle 1 selected / editable"
            self.update()
        except Exception:
            pass

    def _current_ice_state(self):
        if not self._should_show_effect_objects():
            return {"x": 0.50, "y": 0.58, "width": 1.0, "depth": 0.42, "visible": False}
        try:
            pending = getattr(self, "_pending_ice_state", None)
            if pending is not None:
                data = dict(pending or {})
                return {
                    "x": max(0.0, min(1.0, float(data.get("x", 0.50)))),
                    "y": max(0.0, min(1.0, float(data.get("y", 0.58)))),
                    "width": max(0.05, min(1.50, float(data.get("width", 1.0)))),
                    "depth": max(0.05, min(1.0, float(data.get("depth", 0.42)))),
                    "visible": bool(data.get("visible", True)),
                }
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            return {
                "x": max(0.0, min(1.0, float(effect.get("ice_x", 0.50)))),
                "y": max(0.0, min(1.0, float(effect.get("ice_y", 0.58)))),
                "width": max(0.05, min(1.50, float(effect.get("ice_width", 1.0)))),
                "depth": max(0.05, min(1.0, float(effect.get("ice_depth", 0.42)))),
                "visible": bool(effect.get("ice_visible", False)),
            }
        except Exception:
            return {"x": 0.50, "y": 0.58, "width": 1.0, "depth": 0.42, "visible": False}

    def _ice_marker_path(self, item=None):
        try:
            item = dict(item or self._current_ice_state() or {})
            if not bool(item.get("visible", False)):
                return None
            x_ratio = max(0.0, min(1.0, float(item.get("x", 0.50))))
            y_ratio = max(0.0, min(1.0, float(item.get("y", 0.58))))
            width_ratio = max(0.05, min(1.50, float(item.get("width", 1.0))))
            depth_ratio = max(0.05, min(1.0, float(item.get("depth", 0.42))))
            left_u = max(-0.25, min(1.25, x_ratio - width_ratio * 0.5))
            right_u = max(-0.25, min(1.25, x_ratio + width_ratio * 0.5))
            top_v = max(0.0, min(1.0, y_ratio))
            bottom_v = max(0.0, min(1.0, y_ratio + depth_ratio))
            corners = []
            for u, v in ((left_u, top_v), (right_u, top_v), (right_u, bottom_v), (left_u, bottom_v)):
                px, pz = self._unit_to_plane(u, v)
                corners.append(self._project_point(px, 4.0, pz)[0])
            if len(corners) < 4:
                return None
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            return path
        except Exception:
            return None

    def _hit_ice_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            path = self._ice_marker_path()
            if path is None:
                return False
            return bool(path.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _select_ice_preview(self):
        try:
            self._preview_selected_widget_index = None
            self._clear_water_surface_preview_selection("")
            self._ice_selected = True
            self._drag_notice = "Ice selected / multi-handle directional resize in Phase 20E22"
            self.update()
        except Exception:
            pass

    def _clear_ice_preview_selection(self, notice="Ice selection cleared"):
        try:
            if bool(getattr(self, "_ice_selected", False)):
                self._ice_selected = False
                self._ice_resize_drag_kind = None
                self._drag_notice = str(notice or "Ice selection cleared")
                self.update()
        except Exception:
            pass

    def _ice_projected_corners(self, item=None):
        try:
            item = dict(item or self._current_ice_state() or {})
            if not bool(item.get("visible", False)):
                return []
            x_ratio = max(0.0, min(1.0, float(item.get("x", 0.50))))
            y_ratio = max(0.0, min(1.0, float(item.get("y", 0.58))))
            width_ratio = max(0.05, min(1.50, float(item.get("width", 1.0))))
            depth_ratio = max(0.05, min(1.0, float(item.get("depth", 0.42))))
            left_u = max(-0.25, min(1.25, x_ratio - width_ratio * 0.5))
            right_u = max(-0.25, min(1.25, x_ratio + width_ratio * 0.5))
            top_v = max(0.0, min(1.0, y_ratio))
            bottom_v = max(0.0, min(1.0, y_ratio + depth_ratio))
            corners = []
            for u, v in ((left_u, top_v), (right_u, top_v), (right_u, bottom_v), (left_u, bottom_v)):
                px, pz = self._unit_to_plane(u, v)
                corners.append(self._project_point(px, 4.0, pz)[0])
            return corners if len(corners) == 4 else []
        except Exception:
            return []

    def _ice_resize_handles(self, item=None):
        try:
            corners = self._ice_projected_corners(item)
            if len(corners) < 4:
                return {}
            handle_size = 14.0
            centers = {
                "top_left": corners[0],
                "top": QPointF((corners[0].x() + corners[1].x()) * 0.5, (corners[0].y() + corners[1].y()) * 0.5),
                "top_right": corners[1],
                "right": QPointF((corners[1].x() + corners[2].x()) * 0.5, (corners[1].y() + corners[2].y()) * 0.5),
                "bottom_right": corners[2],
                "bottom": QPointF((corners[2].x() + corners[3].x()) * 0.5, (corners[2].y() + corners[3].y()) * 0.5),
                "bottom_left": corners[3],
                "left": QPointF((corners[0].x() + corners[3].x()) * 0.5, (corners[0].y() + corners[3].y()) * 0.5),
            }
            return {
                kind: QRectF(
                    center.x() - handle_size * 0.5,
                    center.y() - handle_size * 0.5,
                    handle_size,
                    handle_size,
                )
                for kind, center in centers.items()
            }
        except Exception:
            return {}

    def _ice_resize_handle_rect(self, item=None):
        try:
            return self._ice_resize_handles(item).get("bottom_right", QRectF())
        except Exception:
            return QRectF()

    def _draw_ice_resize_handle(self, painter):
        try:
            if not self.is_desktop_locked() or not bool(getattr(self, "_ice_selected", False)):
                return
            ice = self._current_ice_state()
            if not bool(ice.get("visible", False)):
                return
            handles = self._ice_resize_handles(ice)
            if not handles:
                return
            active_kind = str(getattr(self, "_ice_resize_drag_kind", "") or "")
            for kind in ("top_left", "top", "top_right", "right", "bottom_right", "bottom", "bottom_left", "left"):
                handle_rect = handles.get(kind)
                if handle_rect is None or handle_rect.isNull() or not handle_rect.isValid():
                    continue
                is_corner = kind in ("top_left", "top_right", "bottom_right", "bottom_left")
                is_active = kind == active_kind
                painter.setBrush(QBrush(QColor(190, 252, 255, 255) if is_active else QColor(160, 245, 255, 238 if is_corner else 210)))
                painter.setPen(QPen(QColor(18, 64, 78, 255 if is_active else 235), 2.2 if is_active else (2.0 if is_corner else 1.6)))
                try:
                    painter.drawRoundedRect(handle_rect, 4.0, 4.0)
                except Exception:
                    painter.drawRect(handle_rect)
                painter.setPen(QPen(QColor(18, 64, 78, 245), 1.2))
                if kind in ("left", "right"):
                    painter.drawLine(QPointF(handle_rect.center().x(), handle_rect.top() + 3.0), QPointF(handle_rect.center().x(), handle_rect.bottom() - 3.0))
                elif kind in ("top", "bottom"):
                    painter.drawLine(QPointF(handle_rect.left() + 3.0, handle_rect.center().y()), QPointF(handle_rect.right() - 3.0, handle_rect.center().y()))
                else:
                    painter.drawLine(QPointF(handle_rect.left() + 4.0, handle_rect.bottom() - 4.0), QPointF(handle_rect.right() - 4.0, handle_rect.bottom() - 4.0))
                    painter.drawLine(QPointF(handle_rect.right() - 4.0, handle_rect.top() + 4.0), QPointF(handle_rect.right() - 4.0, handle_rect.bottom() - 4.0))
        except Exception:
            pass

    def _ice_resize_hit_kind(self, pos):
        if not self._should_show_effect_objects():
            return None
        if not self.is_desktop_locked() or not bool(getattr(self, "_ice_selected", False)):
            return None
        try:
            ice = self._current_ice_state()
            if not bool(ice.get("visible", False)):
                return None
            point = QPointF(float(pos.x()), float(pos.y()))
            handles = self._ice_resize_handles(ice)
            # Corners first, then sides.  This prevents a corner click from being
            # swallowed by a nearby side handle when the projected Ice plane is small.
            for kind in ("top_left", "top_right", "bottom_right", "bottom_left", "right", "bottom", "left", "top"):
                handle_rect = handles.get(kind)
                if handle_rect is not None and handle_rect.isValid() and not handle_rect.isNull():
                    if handle_rect.adjusted(-5.0, -5.0, 5.0, 5.0).contains(point):
                        return kind
            return None
        except Exception:
            return None

    def _hit_ice_resize_handle(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        return self._ice_resize_hit_kind(pos) is not None

    def _ice_screen_basis(self, item=None):
        try:
            item = dict(item or self._current_ice_state() or {})
            corners = self._ice_projected_corners(item)
            if len(corners) < 4:
                return None
            # Width axis: midpoint of right edge minus midpoint of left edge.
            left_mid = QPointF((corners[0].x() + corners[3].x()) * 0.5, (corners[0].y() + corners[3].y()) * 0.5)
            right_mid = QPointF((corners[1].x() + corners[2].x()) * 0.5, (corners[1].y() + corners[2].y()) * 0.5)
            # Depth axis: midpoint of bottom edge minus midpoint of top edge.
            top_mid = QPointF((corners[0].x() + corners[1].x()) * 0.5, (corners[0].y() + corners[1].y()) * 0.5)
            bottom_mid = QPointF((corners[2].x() + corners[3].x()) * 0.5, (corners[2].y() + corners[3].y()) * 0.5)
            width_ratio = max(0.05, min(1.50, float(item.get("width", 1.0))))
            depth_ratio = max(0.05, min(1.0, float(item.get("depth", 0.42))))
            wx = float(right_mid.x() - left_mid.x())
            wy = float(right_mid.y() - left_mid.y())
            vx = float(bottom_mid.x() - top_mid.x())
            vy = float(bottom_mid.y() - top_mid.y())
            det = wx * vy - vx * wy
            if abs(det) < 1e-6:
                return None
            return {
                "wx": wx,
                "wy": wy,
                "vx": vx,
                "vy": vy,
                "det": det,
                "width": width_ratio,
                "depth": depth_ratio,
            }
        except Exception:
            return None

    def _begin_ice_move_drag(self, pos):
        self._begin_ice_delta_drag(pos)

    def _begin_ice_resize_drag(self, pos, kind="bottom_right"):
        self._ice_resize_drag_kind = str(kind or "bottom_right")
        self._begin_ice_delta_drag(pos)

    def _begin_ice_delta_drag(self, pos):
        try:
            state = dict(self._current_ice_state() or {})
            self._ice_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._ice_drag_start_state = dict(state)
            self._ice_drag_basis = self._ice_screen_basis(state)
        except Exception:
            self._ice_drag_start_pos = None
            self._ice_drag_start_state = None
            self._ice_drag_basis = None

    def _ice_unit_delta_from_drag(self, pos):
        try:
            start_pos = getattr(self, "_ice_drag_start_pos", None)
            basis = getattr(self, "_ice_drag_basis", None)
            if start_pos is None or not isinstance(basis, dict):
                return None
            dx = float(pos.x()) - float(start_pos.x())
            dy = float(pos.y()) - float(start_pos.y())
            wx = float(basis.get("wx", 0.0))
            wy = float(basis.get("wy", 0.0))
            vx = float(basis.get("vx", 0.0))
            vy = float(basis.get("vy", 0.0))
            det = float(basis.get("det", wx * vy - vx * wy))
            if abs(det) < 1e-6:
                return None
            # Solve screen_delta = a * width_axis + b * depth_axis.
            a = (dx * vy - vx * dy) / det
            b = (wx * dy - dx * wy) / det
            du = a * max(0.05, min(1.50, float(basis.get("width", 1.0))))
            dv = b * max(0.05, min(1.0, float(basis.get("depth", 0.42))))
            return du, dv
        except Exception:
            return None

    def _set_temp_ice_unit_from_drag_delta(self, pos):
        try:
            start = getattr(self, "_ice_drag_start_state", None)
            delta = self._ice_unit_delta_from_drag(pos)
            if start is None or delta is None:
                ice = self._current_ice_state()
                nx, ny = self._screen_to_unit_on_desktop(pos, ice.get("x", 0.50), ice.get("y", 0.58))
                self._set_temp_ice_unit(nx, ny)
                return
            start = dict(start or {})
            du, dv = delta
            nx = float(start.get("x", 0.50)) + float(du)
            ny = float(start.get("y", 0.58)) + float(dv)
            self._set_temp_ice_unit(nx, ny)
        except Exception:
            pass

    def _set_temp_ice_size_from_drag_delta(self, pos):
        try:
            start = getattr(self, "_ice_drag_start_state", None)
            delta = self._ice_unit_delta_from_drag(pos)
            if start is None or delta is None:
                self._set_temp_ice_size_from_screen_pos(pos)
                return
            start = dict(start or {})
            du, dv = delta
            kind = str(getattr(self, "_ice_resize_drag_kind", "bottom_right") or "bottom_right")
            start_x = max(0.0, min(1.0, float(start.get("x", 0.50))))
            start_y = max(0.0, min(1.0, float(start.get("y", 0.58))))
            start_width = max(0.05, min(1.50, float(start.get("width", 1.0))))
            start_depth = max(0.05, min(1.0, float(start.get("depth", 0.42))))
            left_u = start_x - start_width * 0.5
            right_u = start_x + start_width * 0.5
            top_v = start_y
            bottom_v = start_y + start_depth

            if kind in ("left", "top_left", "bottom_left"):
                new_width = start_width - float(du)
                fixed_right = right_u
                new_width = max(0.05, min(1.50, self._snap_float_value(new_width, 0.02)))
                new_x = fixed_right - new_width * 0.5
            elif kind in ("right", "top_right", "bottom_right"):
                new_width = start_width + float(du)
                fixed_left = left_u
                new_width = max(0.05, min(1.50, self._snap_float_value(new_width, 0.02)))
                new_x = fixed_left + new_width * 0.5
            else:
                new_width = start_width
                new_x = start_x

            if kind in ("top", "top_left", "top_right"):
                new_depth = start_depth - float(dv)
                fixed_bottom = bottom_v
                new_depth = max(0.05, min(1.0, self._snap_float_value(new_depth, 0.02)))
                new_y = fixed_bottom - new_depth
            elif kind in ("bottom", "bottom_left", "bottom_right"):
                new_depth = start_depth + float(dv)
                fixed_top = top_v
                new_depth = max(0.05, min(1.0, self._snap_float_value(new_depth, 0.02)))
                new_y = fixed_top
            else:
                new_depth = start_depth
                new_y = start_y

            current = {
                "x": max(0.0, min(1.0, float(new_x))),
                "y": max(0.0, min(1.0, float(new_y))),
                "width": new_width,
                "depth": new_depth,
                "visible": True,
            }
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect["ice_visible"] = True
            effect["ice_x"] = current["x"]
            effect["ice_y"] = current["y"]
            effect["ice_width"] = current["width"]
            effect["ice_depth"] = current["depth"]
            state["effect"] = effect
            self._preview_state = state
            self._pending_ice_state = dict(current)
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Ice {kind} resize preview-only{snap_tag} width={new_width:.3f} depth={new_depth:.3f}"
            self.update()
        except Exception:
            pass

    def current_preview_ice_state(self):
        return dict(self._current_ice_state() or {})

    def clear_pending_ice_state(self):
        self._pending_ice_state = None
        try:
            self.update()
        except Exception:
            pass

    def current_preview_water_surface_state(self):
        return dict(self._current_water_surface_state() or {})

    def clear_pending_water_surface_state(self):
        self._pending_water_surface_state = None
        self._water_surface_selected = False
        self._water_surface_drag_start_pos = None
        self._water_surface_drag_start_state = None
        self._water_surface_resize_drag_start_pos = None
        self._water_surface_resize_drag_start_state = None
        try:
            self.update()
        except Exception:
            pass

    def _hit_puddle_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        try:
            return bool(self._puddle_hit_candidates(pos))
        except Exception:
            return False

    def _hit_puddle_resize_handle(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects() or not self._puddle_preview_has_real_targets():
            self._clear_stale_puddle_preview_state_if_disabled()
            return False
        try:
            item = self._puddle_screen_ellipse(self._current_selected_puddle_state())
            if item is None:
                return False
            center, rw, rh = item
            hx = float(center.x()) + float(rw)
            hy = float(center.y()) + float(rh)
            dx = float(pos.x()) - hx
            dy = float(pos.y()) - hy
            return (dx * dx + dy * dy) <= 16.0 ** 2
        except Exception:
            return False

    def _set_temp_puddle_size_from_unit(self, edge_x_ratio, edge_y_ratio):
        try:
            selected_index = int(getattr(self, "_selected_puddle_index", 0))
            current = self._current_selected_puddle_state()
            current["index"] = selected_index
            cx = max(0.0, min(1.0, float(current.get("x", 0.50))))
            cy = max(0.0, min(1.0, float(current.get("y", 0.84))))
            new_w = max(0.03, min(1.20, abs(float(edge_x_ratio) - cx) * 2.0))
            new_h = max(0.015, min(0.70, abs(float(edge_y_ratio) - cy) * 2.0))
            new_w = max(0.03, min(1.20, self._snap_float_value(new_w, 0.02)))
            new_h = max(0.015, min(0.70, self._snap_float_value(new_h, 0.02)))
            current["width"] = new_w
            current["height"] = new_h
            current["visible"] = True
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect = self._merge_pending_selected_puddle_into_effect(effect, current)
            state["effect"] = effect
            self._preview_state = state
            self._pending_puddle_state = dict(current)
            self._pending_puddle_states[selected_index] = dict(current)
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Puddle {selected_index + 1} resize preview-only{snap_tag} width={new_w:.3f} height={new_h:.3f}"
            self.update()
        except Exception:
            pass

    def _begin_puddle_resize_drag(self, pos):
        try:
            puddle = dict(self._current_selected_puddle_state() or {})
            puddle["index"] = int(getattr(self, "_selected_puddle_index", 0))
            item = self._puddle_screen_ellipse(puddle)
            scale_w = 1.0
            scale_h = 1.0
            if item is not None:
                _center, rw, rh = item
                scale_w = float(rw) / max(1e-6, 360.0 * max(0.03, float(puddle.get("width", 0.20))))
                scale_h = float(rh) / max(1e-6, 210.0 * max(0.015, float(puddle.get("height", 0.08))))
            puddle["_scale_w"] = max(1e-6, scale_w)
            puddle["_scale_h"] = max(1e-6, scale_h)
            self._drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._drag_start_puddle_state = puddle
        except Exception:
            self._drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._drag_start_puddle_state = dict(self._current_selected_puddle_state() or {})
            self._drag_start_puddle_state["index"] = int(getattr(self, "_selected_puddle_index", 0))

    def _set_temp_puddle_size_from_screen_delta(self, pos):
        try:
            start_pos = getattr(self, "_drag_start_pos", None)
            start = dict(getattr(self, "_drag_start_puddle_state", None) or {})
            if start_pos is None or not start:
                # Fallback to the earlier inverse-projection method.
                current = self._current_puddle_state()
                ex, ey = self._screen_to_unit_on_desktop(pos, current.get("x", 0.50), current.get("y", 0.84))
                self._set_temp_puddle_size_from_unit(ex, ey)
                return
            dx = float(pos.x()) - float(start_pos.x())
            dy = float(pos.y()) - float(start_pos.y())
            scale_w = max(1e-6, float(start.get("_scale_w", 1.0)))
            scale_h = max(1e-6, float(start.get("_scale_h", 1.0)))
            start_w = max(0.03, float(start.get("width", 0.20)))
            start_h = max(0.015, float(start.get("height", 0.08)))
            new_w = max(0.03, min(1.20, start_w + dx / (360.0 * scale_w)))
            new_h = max(0.015, min(0.70, start_h + dy / (210.0 * scale_h)))
            new_w = max(0.03, min(1.20, self._snap_float_value(new_w, 0.02)))
            new_h = max(0.015, min(0.70, self._snap_float_value(new_h, 0.02)))
            current = dict(start)
            selected_index = int(current.get("index", getattr(self, "_selected_puddle_index", 0)))
            current["index"] = selected_index
            current["width"] = new_w
            current["height"] = new_h
            current["visible"] = True
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect = self._merge_pending_selected_puddle_into_effect(effect, current)
            state["effect"] = effect
            current.pop("_scale_w", None)
            current.pop("_scale_h", None)
            self._preview_state = state
            self._pending_puddle_state = dict(current)
            self._pending_puddle_states[selected_index] = dict(current)
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Puddle {selected_index + 1} resize preview-only{snap_tag} width={new_w:.3f} height={new_h:.3f}"
            self.update()
        except Exception:
            pass

    def _set_temp_puddle_unit(self, x_ratio, y_ratio):
        try:
            selected_index = int(getattr(self, "_selected_puddle_index", 0))
            current = self._current_selected_puddle_state()
            current["index"] = selected_index
            current["x"] = max(0.0, min(1.0, float(x_ratio)))
            current["y"] = max(0.0, min(1.0, float(y_ratio)))
            current["visible"] = True
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect = self._merge_pending_selected_puddle_into_effect(effect, current)
            state["effect"] = effect
            self._preview_state = state
            self._pending_puddle_state = dict(current)
            self._pending_puddle_states[selected_index] = dict(current)
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"Puddle {selected_index + 1} preview-only{snap_tag} x={current['x']:.3f} y={current['y']:.3f}"
            self.update()
        except Exception:
            pass

    def current_preview_puddle_state(self):
        selected_index = int(getattr(self, "_selected_puddle_index", 0))
        pending_map = dict(getattr(self, "_pending_puddle_states", {}) or {})
        if selected_index in pending_map:
            return dict(pending_map.get(selected_index) or {})
        pending = getattr(self, "_pending_puddle_state", None)
        if pending is not None:
            return dict(pending)
        return self._current_selected_puddle_state()

    def clear_pending_puddle_state(self):
        self._pending_puddle_state = None
        self._pending_puddle_states = {}
        try:
            self.update()
        except Exception:
            pass

    def pending_preview_changes(self):
        changes = {}
        try:
            pending_sun = getattr(self, "_pending_sun_unit", None)
            if pending_sun is not None:
                changes["sun"] = {
                    "x": max(0.0, min(1.0, float(pending_sun[0]))),
                    "y": max(0.0, min(1.0, float(pending_sun[1]))),
                }
        except Exception:
            pass
        try:
            pending_moon = getattr(self, "_pending_moon_unit", None)
            if pending_moon is not None:
                changes["moon"] = {
                    "x": max(0.0, min(1.0, float(pending_moon[0]))),
                    "y": max(0.0, min(1.0, float(pending_moon[1]))),
                }
        except Exception:
            pass
        try:
            pending_items = dict(getattr(self, "_pending_puddle_states", {}) or {})
            pending_puddle = getattr(self, "_pending_puddle_state", None)
            if pending_puddle is not None:
                data = dict(pending_puddle or {})
                pending_items[int(data.get("index", getattr(self, "_selected_puddle_index", 0)))] = data
            if pending_items:
                puddle_changes = []
                for idx, data in sorted(pending_items.items(), key=lambda kv: int(kv[0])):
                    data = dict(data or {})
                    puddle_changes.append({
                        "index": int(data.get("index", idx)),
                        "x": max(0.0, min(1.0, float(data.get("x", 0.50)))),
                        "y": max(0.0, min(1.0, float(data.get("y", 0.84)))),
                        "width": max(0.03, min(1.20, float(data.get("width", 0.20)))),
                        "height": max(0.015, min(0.70, float(data.get("height", 0.08)))),
                        "visible": bool(data.get("visible", True)),
                    })
                changes["puddles"] = puddle_changes
                changes["puddle"] = dict(puddle_changes[-1])
        except Exception:
            pass
        try:
            pending_ice = getattr(self, "_pending_ice_state", None)
            if pending_ice is not None:
                data = dict(pending_ice or {})
                changes["ice"] = {
                    "x": max(0.0, min(1.0, float(data.get("x", 0.50)))),
                    "y": max(0.0, min(1.0, float(data.get("y", 0.58)))),
                    "width": max(0.05, min(1.50, float(data.get("width", 1.0)))),
                    "depth": max(0.05, min(1.0, float(data.get("depth", 0.42)))),
                    "visible": bool(data.get("visible", True)),
                }
        except Exception:
            pass
        try:
            pending_water = getattr(self, "_pending_water_surface_state", None)
            if pending_water is not None:
                data = dict(pending_water or {})
                depth = max(0.05, min(1.0, float(data.get("depth", 0.42))))
                changes["water_surface"] = {
                    "y": max(0.0, min(max(0.0, 1.0 - depth), float(data.get("y", 0.58)))),
                    "depth": depth,
                    "visible": bool(data.get("visible", True)),
                }
        except Exception:
            pass
        try:
            pending_bamboo = getattr(self, "_pending_bamboo_grove_state", None)
            if pending_bamboo is not None:
                data = dict(pending_bamboo or {})
                changes["bamboo_grove"] = {
                    "height": max(0.10, min(1.50, float(data.get("height", 0.92)))),
                    "visible": bool(data.get("visible", True)),
                }
        except Exception:
            pass
        try:
            pending_cloud = getattr(self, "_pending_cloud_layer_state", None)
            if pending_cloud is not None:
                data = dict(pending_cloud or {})
                changes["cloud"] = {
                    "size": max(18.0, min(180.0, float(data.get("size", 92.0)))),
                    "altitude": max(0.0, min(1.0, float(data.get("altitude", 0.22)))),
                    "depth": max(0.04, min(1.0, float(data.get("depth", 0.42)))),
                    "visible": bool(data.get("visible", True)),
                }
        except Exception:
            pass
        try:
            pending_fireball = getattr(self, "_pending_fireball_layer_state", None)
            if pending_fireball is not None:
                data = dict(pending_fireball or {})
                changes["fireball"] = {
                    "x": max(0.0, min(1.0, float(data.get("x", 0.50)))),
                    "y": max(0.0, min(1.0, float(data.get("y", 0.38)))),
                    "visible": bool(data.get("visible", True)),
                }
        except Exception:
            pass
        try:
            pending_templates = dict(getattr(self, "_pending_template_effect_states", {}) or {})
            for key, data in sorted(pending_templates.items()):
                spec = self._lds_template_effect_spec(key) or {}
                mode = str(spec.get("mode", ""))
                item = {"visible": bool(dict(data or {}).get("visible", True)), "mode": mode}
                if mode == "anchor_point":
                    item["x"] = max(0.0, min(1.0, float(dict(data or {}).get("x", spec.get("default_x", 0.5)))))
                    item["y"] = max(0.0, min(1.0, float(dict(data or {}).get("y", spec.get("default_y", 0.5)))))
                changes[str(key)] = item
        except Exception:
            pass
        try:
            pending_widgets = dict(getattr(self, "_pending_widget_rects", {}) or {})
            pending_widget = getattr(self, "_pending_widget_rect", None)
            if pending_widget is not None:
                data = dict(pending_widget or {})
                try:
                    pending_widgets[int(data.get("index", -1))] = data
                except Exception:
                    pass
            if pending_widgets:
                widget_changes = []
                for idx, data in sorted(pending_widgets.items(), key=lambda kv: int(kv[0])):
                    data = dict(data or {})
                    if int(data.get("index", idx)) < 0:
                        continue
                    widget_change = {
                        "index": int(data.get("index", idx)),
                        "x": int(data.get("x", 0)),
                        "y": int(data.get("y", 0)),
                        "w": int(data.get("w", 80)),
                        "h": int(data.get("h", 80)),
                        "rotation": float(data.get("rotation", data.get("rotation_degrees", 0.0))),
                        "rotation_degrees": float(data.get("rotation_degrees", data.get("rotation", 0.0))),
                        "type": str(data.get("type", "")),
                        "title": str(data.get("title", "")),
                    }
                    for common_key in ("color", "bg", "text", "font_size", "clock_show_digital", "cpu_color", "memory_color", "disk_color", "network_down_color", "network_up_color", 'visualizer_flip_vertical', 'visualizer_peak_bar_enabled', 'visualizer_glow_enabled', 'visualizer_bar_width_scale', 'visualizer_orientation', 'visualizer_style', 'visualizer_shadow_enabled', 'visualizer_shadow_offset_x', 'visualizer_shadow_offset_y', 'visualizer_shadow_strength', 'visualizer_shadow_opacity', 'visualizer_shadow_depth', 'visualizer_shadow_blur', 'visualizer_frame_rate_enabled', 'visualizer_frame_rate', "visualizer_preset_key", 'weather_location', 'jshtml_mode', 'jshtml_entry', 'jshtml_package_name', 'jshtml_package_version', 'jshtml_permissions_json', 'jshtml_instance_id', 'runtime_calendar_date', 'runtime_calendar_time', 'runtime_cpu_percent', 'runtime_memory_percent', 'runtime_disk_percent', 'runtime_network_down_bps', 'runtime_network_up_bps', 'runtime_network_down_kbps', 'runtime_network_up_kbps', 'runtime_sample_age_sec', 'runtime_weather_location', 'runtime_volume_available', 'runtime_volume_percent', 'runtime_volume_muted', 'runtime_media_available', 'runtime_media_title', 'runtime_media_artist', 'runtime_media_album', 'runtime_media_app_id', 'runtime_media_playback_status', 'runtime_media_updated_at'):
                        if common_key in data:
                            widget_change[common_key] = data.get(common_key)
                    widget_changes.append(widget_change)
                if widget_changes:
                    changes["widgets"] = widget_changes
                    changes["widget"] = dict(widget_changes[-1])
        except Exception:
            pass
        return changes

    def clear_all_pending_preview_changes(self):
        self._pending_sun_unit = None
        self._pending_moon_unit = None
        self._pending_puddle_state = None
        self._pending_puddle_states = {}
        self._selected_puddle_index = 0
        self._water_surface_selected = False
        self._bamboo_grove_selected = False
        self._cloud_selected = False
        self._fireball_selected = False
        self._pending_fireball_layer_state = None
        self._fireball_drag_start_pos = None
        self._fireball_drag_start_state = None
        self._pending_cloud_layer_state = None
        self._cloud_drag_start_pos = None
        self._cloud_drag_start_state = None
        self._cloud_resize_drag_start_pos = None
        self._cloud_resize_drag_start_state = None
        self._pending_bamboo_grove_state = None
        self._bamboo_grove_resize_drag_start_pos = None
        self._bamboo_grove_resize_drag_start_state = None
        self._pending_water_surface_state = None
        self._water_surface_drag_start_pos = None
        self._water_surface_drag_start_state = None
        self._water_surface_resize_drag_start_pos = None
        self._water_surface_resize_drag_start_state = None
        self._ice_selected = False
        self._pending_ice_state = None
        self._ice_drag_start_pos = None
        self._ice_drag_start_state = None
        self._ice_drag_basis = None
        self._ice_resize_drag_kind = None
        self._pending_widget_rect = None
        self._pending_widget_rects = {}
        self._preview_selected_widget_index = None
        self._widget_drag_start = None
        self._widget_drag_offset_unit = None
        self._widget_drag_start_pos = None
        self._widget_drag_jacobian = None
        self._widget_rotate_center = None
        self._widget_rotate_start_angle = None
        self._widget_rotate_start_pointer_angle = None
        self._drag_notice = "3D preview pending changes discarded"
        try:
            self.update()
        except Exception:
            pass

    def _current_bamboo_grove_state(self):
        try:
            effect = dict((getattr(self, "_preview_state", {}) or {}).get("effect", {}) or {})
            state = {
                "visible": bool(effect.get("bamboo_grove_visible", False)),
                "count": int(effect.get("bamboo_count", 12)),
                "height": float(effect.get("bamboo_height", 0.92)),
                "thickness": float(effect.get("bamboo_thickness", 16.0)),
                "angle": float(effect.get("bamboo_angle", 0.0)),
                "bend": float(effect.get("bamboo_bend", 0.32)),
            }
            pending = getattr(self, "_pending_bamboo_grove_state", None)
            if pending is not None:
                pending = dict(pending or {})
                state["visible"] = bool(pending.get("visible", True))
                state["height"] = max(0.10, min(1.50, float(pending.get("height", state.get("height", 0.92)))))
            return state
        except Exception:
            return {"visible": False, "count": 0, "height": 0.92, "thickness": 16.0, "angle": 0.0, "bend": 0.32}

    def _bamboo_grove_marker_path(self):
        try:
            state = self._current_bamboo_grove_state()
            if not bool(state.get("visible", False)):
                return None
            top_v = max(0.0, min(1.0, 0.18 + (1.0 - float(state.get("height", 0.92))) * 0.18))
            bottom_v = 1.05
            corners = []
            for u, v in ((0.0, top_v), (1.0, top_v), (1.05, bottom_v), (-0.05, bottom_v)):
                px, pz = self._unit_to_plane(u, v)
                corners.append(self._project_point(px, 8.0, pz)[0])
            if len(corners) < 4:
                return None
            path = QPainterPath()
            path.moveTo(corners[0])
            for point in corners[1:]:
                path.lineTo(point)
            path.closeSubpath()
            return path
        except Exception:
            return None

    def _hit_bamboo_grove_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            path = self._bamboo_grove_marker_path()
            if path is None:
                return False
            return bool(path.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _bamboo_grove_height_resize_handle_rect(self):
        try:
            if not bool(getattr(self, "_bamboo_grove_selected", False)):
                return None
            path = self._bamboo_grove_marker_path()
            if path is None:
                return None
            bounds = path.boundingRect()
            size = 20.0
            center = QPointF(bounds.center().x(), bounds.top() + 4.0)
            return QRectF(center.x() - size * 0.5, center.y() - size * 0.5, size, size)
        except Exception:
            return None

    def _hit_bamboo_grove_height_resize_handle(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            rect = self._bamboo_grove_height_resize_handle_rect()
            if rect is None:
                return False
            return bool(rect.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _begin_bamboo_grove_height_resize_drag(self, pos):
        try:
            self._bamboo_grove_resize_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._bamboo_grove_resize_drag_start_state = dict(self._current_bamboo_grove_state() or {})
        except Exception:
            self._bamboo_grove_resize_drag_start_pos = None
            self._bamboo_grove_resize_drag_start_state = None

    def _set_temp_bamboo_grove_height(self, height_ratio):
        state = dict(self._current_bamboo_grove_state() or {})
        try:
            height_ratio = max(0.10, min(1.50, float(height_ratio)))
        except Exception:
            height_ratio = max(0.10, min(1.50, float(state.get("height", 0.92))))
        try:
            if self.is_snap_enabled():
                height_ratio = max(0.10, min(1.50, self._snap_float_value(height_ratio, 0.02)))
        except Exception:
            pass
        self._pending_bamboo_grove_state = {"height": height_ratio, "visible": True}
        self._bamboo_grove_selected = True
        self._drag_notice = f"Bamboo Grove height preview-only height={height_ratio:.3f}" + (" SNAP" if self.is_snap_enabled() else "")
        try:
            self.update()
        except Exception:
            pass

    def _set_temp_bamboo_grove_height_from_drag_delta(self, pos):
        try:
            start_state = dict(getattr(self, "_bamboo_grove_resize_drag_start_state", None) or self._current_bamboo_grove_state() or {})
            start_pos = getattr(self, "_bamboo_grove_resize_drag_start_pos", None)
            if start_pos is None:
                self._begin_bamboo_grove_height_resize_drag(pos)
                start_pos = getattr(self, "_bamboo_grove_resize_drag_start_pos", None)
                start_state = dict(getattr(self, "_bamboo_grove_resize_drag_start_state", None) or self._current_bamboo_grove_state() or {})
            start_height = max(0.10, min(1.50, float(start_state.get("height", 0.92))))
            dy = float(start_pos.y()) - float(pos.y())
            scale = max(120.0, float(self.height()) * 0.55)
            self._set_temp_bamboo_grove_height(start_height + dy / scale)
        except Exception:
            pass

    def _select_bamboo_grove_preview(self):
        try:
            self._preview_selected_widget_index = None
            self._clear_ice_preview_selection("")
            self._clear_water_surface_preview_selection("")
            self._pending_puddle_state = None
            self._pending_puddle_states = {}
            self._bamboo_grove_selected = True
            state = self._current_bamboo_grove_state()
            self._drag_notice = f"Bamboo Grove selected / height-resize count={int(state.get('count', 12))} height={float(state.get('height', 0.92)):.2f}"
            self.update()
        except Exception:
            pass

    def _clear_bamboo_grove_preview_selection(self, notice=""):
        try:
            if bool(getattr(self, "_bamboo_grove_selected", False)):
                self._bamboo_grove_selected = False
                if notice:
                    self._drag_notice = str(notice)
                self.update()
        except Exception:
            pass

    def _draw_bamboo_leaf_3d_marker(self, painter, origin, angle_degrees, length, width, color):
        try:
            rad = math.radians(float(angle_degrees))
            ux = math.cos(rad)
            uy = math.sin(rad)
            px = -uy
            py = ux
            tip = QPointF(origin.x() + ux * length, origin.y() + uy * length)
            base_l = QPointF(origin.x() + px * width * 0.35, origin.y() + py * width * 0.35)
            base_r = QPointF(origin.x() - px * width * 0.35, origin.y() - py * width * 0.35)
            mid = QPointF(origin.x() + ux * length * 0.58, origin.y() + uy * length * 0.58)
            side = QPointF(mid.x() + px * width, mid.y() + py * width)
            path = QPainterPath()
            path.moveTo(base_l)
            path.quadTo(side, tip)
            path.quadTo(QPointF(mid.x() - px * width, mid.y() - py * width), base_r)
            path.closeSubpath()
            painter.setPen(QPen(QColor(20, 60, 22, 120), 0.8))
            painter.setBrush(QBrush(color))
            painter.drawPath(path)
        except Exception:
            pass

    def _draw_bamboo_grove_marker(self, painter, effect):
        """Display-only 3D marker for Bamboo Grove. No hit/pending/apply behavior in Phase 23B-1."""
        try:
            count = max(0, min(48, int(effect.get("bamboo_count", 12))))
            if count <= 0:
                return
            height_ratio = max(0.10, min(1.50, float(effect.get("bamboo_height", 0.92))))
            thickness_base = max(2.0, min(48.0, float(effect.get("bamboo_thickness", 16.0))))
            angle_base = max(-45.0, min(45.0, float(effect.get("bamboo_angle", 0.0))))
            bend_base = max(0.0, min(2.0, float(effect.get("bamboo_bend", 0.32))))
            leaf_density = max(0, min(5, int(effect.get("bamboo_leaf_density", 4))))
            layer_spread = max(0.0, min(1.0, float(effect.get("bamboo_layer_spread", 0.42))))
            depth_strength = max(0.0, min(2.0, float(effect.get("bamboo_depth_strength", 0.85))))
            stalk_color = QColor(str(effect.get("bamboo_stalk_color", "#3EA65A") or "#3EA65A"))
            shadow_color = QColor(str(effect.get("bamboo_shadow_color", "#1F6F3B") or "#1F6F3B"))
            node_color = QColor(str(effect.get("bamboo_node_color", "#B7E37A") or "#B7E37A"))
            leaf_color = QColor(str(effect.get("bamboo_leaf_color", "#5ED06C") or "#5ED06C"))
            selected = bool(getattr(self, "_bamboo_grove_selected", False))
            if selected:
                path = self._bamboo_grove_marker_path()
                if path is not None:
                    painter.setBrush(QBrush(QColor(90, 255, 110, 28)))
                    painter.setPen(QPen(QColor(220, 255, 170, 185), 2.0))
                    painter.drawPath(path)
                try:
                    handle_rect = self._bamboo_grove_height_resize_handle_rect()
                    if handle_rect is not None:
                        painter.setBrush(QBrush(QColor(255, 246, 110, 245)))
                        painter.setPen(QPen(QColor(30, 25, 10, 245), 2.0))
                        painter.drawRoundedRect(handle_rect, 4.0, 4.0)
                        painter.drawLine(QPointF(handle_rect.left() + 4.0, handle_rect.center().y()), QPointF(handle_rect.right() - 4.0, handle_rect.center().y()))
                        painter.drawLine(QPointF(handle_rect.center().x(), handle_rect.top() + 4.0), QPointF(handle_rect.center().x(), handle_rect.bottom() - 4.0))
                except Exception:
                    pass
            for i in range(count):
                slot = (i + 0.5) / max(1, count)
                jitter = math.sin((i + 1) * 12.9898) * 0.38 / max(1, count)
                depth = 0.32 + 0.68 * ((math.sin((i + 3) * 4.117) + 1.0) * 0.5)
                u = max(-0.12, min(1.12, slot + jitter + (depth - 0.5) * 0.06 * layer_spread))
                v_base = max(0.78, min(1.08, 0.98 + (depth - 0.5) * 0.10 * layer_spread))
                base_x, base_z = self._unit_to_plane(u, v_base)
                base_pt, base_scale = self._project_point(base_x, 5.0 + depth * 4.0, base_z)
                projected_height = max(36.0, min(self.height() * 0.72, self.height() * 0.40 * height_ratio * (0.72 + depth * 0.36)))
                angle = angle_base + math.sin((i + 5) * 2.31) * 7.5
                lean = math.sin(math.radians(angle)) * projected_height * 0.22
                top_pt = QPointF(base_pt.x() + lean, base_pt.y() - projected_height)
                bend = bend_base * (0.35 + depth * 0.28) * (1.0 if i % 2 == 0 else -1.0)
                ctrl = QPointF((base_pt.x() + top_pt.x()) * 0.5 + bend * 18.0, (base_pt.y() + top_pt.y()) * 0.5)
                path = QPainterPath()
                path.moveTo(base_pt)
                path.quadTo(ctrl, top_pt)
                width = max(1.4, thickness_base * (0.10 + 0.12 * depth_strength * depth) * max(0.65, base_scale))
                stalk = QColor(stalk_color); stalk.setAlpha(max(80, min(220, int(112 + depth * 105))))
                shadow = QColor(shadow_color); shadow.setAlpha(max(55, min(185, int(80 + depth * 85))))
                painter.setPen(QPen(shadow, width + 1.8)); painter.drawPath(path)
                painter.setPen(QPen(stalk, width)); painter.drawPath(path)
                segment_count = max(4, min(12, int(projected_height / max(26.0, width * 4.5))))
                node = QColor(node_color); node.setAlpha(max(90, min(235, int(130 + depth * 80))))
                painter.setPen(QPen(node, max(1.0, width * 0.36)))
                for j in range(1, segment_count):
                    t = j / float(segment_count)
                    x = (1 - t) * (1 - t) * base_pt.x() + 2 * (1 - t) * t * ctrl.x() + t * t * top_pt.x()
                    y = (1 - t) * (1 - t) * base_pt.y() + 2 * (1 - t) * t * ctrl.y() + t * t * top_pt.y()
                    painter.drawLine(QPointF(x - width * 1.4, y), QPointF(x + width * 1.4, y))
                    if leaf_density > 0 and j >= max(1, segment_count // 3) and ((i + j) % 2 == 0):
                        leaf = QColor(leaf_color); leaf.setAlpha(max(70, min(210, int(95 + depth * 90))))
                        side = -1.0 if (i + j) % 4 < 2 else 1.0
                        leaf_angle = -35.0 + side * (35.0 + 8.0 * math.sin(i + j))
                        self._draw_bamboo_leaf_3d_marker(painter, QPointF(x, y), leaf_angle, max(12.0, projected_height * 0.055 * (0.8 + 0.3 * depth)), max(4.0, width * 2.4), leaf)
            try:
                painter.setPen(QPen(QColor(210, 255, 200, 220), 1.0))
                painter.drawText(QPointF(18.0, max(24.0, self.height() - 26.0)), "Bamboo Grove [height-resize]" + (" [selected]" if bool(getattr(self, "_bamboo_grove_selected", False)) else ""))
            except Exception:
                pass
        except Exception:
            return

    def _current_cloud_layer_state(self):
        try:
            effect = dict((getattr(self, "_preview_state", {}) or {}).get("effect", {}) or {})
            state = {
                "visible": bool(effect.get("cloud_visible", False)),
                "count": int(effect.get("cloud_count", 0)),
                "size": float(effect.get("cloud_size", 92.0)),
                "speed": float(effect.get("cloud_speed", 0.075)),
                "altitude": float(effect.get("cloud_altitude", 0.22)),
                "depth": float(effect.get("cloud_depth", 0.42)),
            }
            pending = getattr(self, "_pending_cloud_layer_state", None)
            if pending is not None:
                pending = dict(pending or {})
                state["visible"] = bool(pending.get("visible", True))
                state["size"] = max(18.0, min(180.0, float(pending.get("size", state.get("size", 92.0)))))
                state["altitude"] = max(0.0, min(1.0, float(pending.get("altitude", state.get("altitude", 0.22)))))
                state["depth"] = max(0.04, min(1.0, float(pending.get("depth", state.get("depth", 0.42)))))
            return state
        except Exception:
            return {"visible": False, "count": 0, "size": 92.0, "speed": 0.075, "altitude": 0.22, "depth": 0.42}

    def _cloud_layer_marker_path(self):
        try:
            state = self._current_cloud_layer_state()
            if not bool(state.get("visible", False)):
                return None
            plane_path = self._desktop_plane_path()
            if plane_path is None:
                return None
            bounds = plane_path.boundingRect()
            if bounds.width() <= 2 or bounds.height() <= 2:
                return None
            altitude = max(0.0, min(1.0, float(state.get("altitude", 0.22))))
            depth = max(0.04, min(1.0, float(state.get("depth", 0.42))))
            center_y = bounds.top() + bounds.height() * altitude
            band_h = bounds.height() * max(0.10, min(0.72, depth))
            top = max(bounds.top() + bounds.height() * 0.03, center_y - band_h * 0.50)
            bottom = min(bounds.bottom() - bounds.height() * 0.03, center_y + band_h * 0.50)
            left = bounds.left() + bounds.width() * 0.04
            right = bounds.right() - bounds.width() * 0.04
            path = QPainterPath()
            path.addRoundedRect(QRectF(left, top, max(1.0, right - left), max(1.0, bottom - top)), 8.0, 8.0)
            return path
        except Exception:
            return None

    def _hit_cloud_layer_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            path = self._cloud_layer_marker_path()
            if path is None:
                return False
            return bool(path.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _cloud_layer_resize_handle_rect(self):
        try:
            if not bool(getattr(self, "_cloud_selected", False)):
                return None
            path = self._cloud_layer_marker_path()
            if path is None:
                return None
            bounds = path.boundingRect()
            size = 18.0
            center = QPointF(bounds.right() - 6.0, bounds.bottom() - 6.0)
            return QRectF(center.x() - size * 0.5, center.y() - size * 0.5, size, size)
        except Exception:
            return None

    def _hit_cloud_layer_resize_handle(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            rect = self._cloud_layer_resize_handle_rect()
            if rect is None:
                return False
            return bool(rect.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _set_temp_cloud_layer_state(self, size=None, altitude=None, depth=None):
        state = dict(self._current_cloud_layer_state() or {})
        try:
            if size is None:
                size = float(state.get("size", 92.0))
            if altitude is None:
                altitude = float(state.get("altitude", 0.22))
            if depth is None:
                depth = float(state.get("depth", 0.42))
            size = max(18.0, min(180.0, float(size)))
            altitude = max(0.0, min(1.0, float(altitude)))
            depth = max(0.04, min(1.0, float(depth)))
            try:
                if self.is_snap_enabled():
                    size = max(18.0, min(180.0, self._snap_float_value(size, 2.0)))
                    altitude = max(0.0, min(1.0, self._snap_float_value(altitude, 0.02)))
                    depth = max(0.04, min(1.0, self._snap_float_value(depth, 0.02)))
            except Exception:
                pass
            self._pending_cloud_layer_state = {"size": size, "altitude": altitude, "depth": depth, "visible": True}
            self._cloud_selected = True
            self._drag_notice = f"Cloud preview-only size={size:.1f} altitude={altitude:.2f} depth={depth:.2f}" + (" SNAP" if self.is_snap_enabled() else "")
            try:
                self.update()
                self._notify_integrated_selection_bar_changed()
            except Exception:
                pass
        except Exception:
            pass

    def _begin_cloud_layer_move_drag(self, pos):
        try:
            self._cloud_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._cloud_drag_start_state = dict(self._current_cloud_layer_state() or {})
        except Exception:
            self._cloud_drag_start_pos = None
            self._cloud_drag_start_state = None

    def _begin_cloud_layer_resize_drag(self, pos):
        try:
            self._cloud_resize_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
            self._cloud_resize_drag_start_state = dict(self._current_cloud_layer_state() or {})
        except Exception:
            self._cloud_resize_drag_start_pos = None
            self._cloud_resize_drag_start_state = None

    def _set_temp_cloud_layer_altitude_from_drag_delta(self, pos):
        try:
            start_pos = getattr(self, "_cloud_drag_start_pos", None)
            start_state = dict(getattr(self, "_cloud_drag_start_state", None) or self._current_cloud_layer_state() or {})
            if start_pos is None:
                self._begin_cloud_layer_move_drag(pos)
                start_pos = getattr(self, "_cloud_drag_start_pos", None)
                start_state = dict(getattr(self, "_cloud_drag_start_state", None) or self._current_cloud_layer_state() or {})
            dy = float(pos.y()) - float(start_pos.y())
            plane_path = self._desktop_plane_path()
            bounds = plane_path.boundingRect() if plane_path is not None else QRectF(0, 0, self.width(), self.height())
            altitude = float(start_state.get("altitude", 0.22)) + dy / max(1.0, float(bounds.height()))
            self._set_temp_cloud_layer_state(altitude=altitude)
        except Exception:
            pass

    def _set_temp_cloud_layer_size_from_drag_delta(self, pos):
        try:
            start_pos = getattr(self, "_cloud_resize_drag_start_pos", None)
            start_state = dict(getattr(self, "_cloud_resize_drag_start_state", None) or self._current_cloud_layer_state() or {})
            if start_pos is None:
                self._begin_cloud_layer_resize_drag(pos)
                start_pos = getattr(self, "_cloud_resize_drag_start_pos", None)
                start_state = dict(getattr(self, "_cloud_resize_drag_start_state", None) or self._current_cloud_layer_state() or {})
            dx = float(pos.x()) - float(start_pos.x())
            dy = float(pos.y()) - float(start_pos.y())
            delta = (dx + dy) * 0.50
            size = float(start_state.get("size", 92.0)) + delta * 0.35
            depth = float(start_state.get("depth", 0.42)) + dy / max(120.0, float(self.height()) * 0.80)
            self._set_temp_cloud_layer_state(size=size, depth=depth)
        except Exception:
            pass

    def _integrated_window_owner(self):
        try:
            obj = self.parent()
            visited = 0
            while obj is not None and visited < 8:
                if hasattr(obj, "update_integrated_selection_bar"):
                    return obj
                try:
                    obj = obj.parent()
                except Exception:
                    obj = None
                visited += 1
            try:
                obj = self.window()
                if obj is not None and hasattr(obj, "update_integrated_selection_bar"):
                    return obj
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _notify_integrated_selection_bar_changed(self):
        try:
            owner = self._integrated_window_owner()
            if owner is None:
                return
            def _do_update():
                try:
                    if hasattr(owner, "update_integrated_selection_bar"):
                        owner.update_integrated_selection_bar()
                    if hasattr(owner, "update_control_visibility"):
                        owner.update_control_visibility()
                except RuntimeError:
                    pass
                except Exception:
                    pass
            _do_update()
            try:
                QTimer.singleShot(0, _do_update)
            except Exception:
                pass
        except Exception:
            pass

    def _select_cloud_layer_preview(self):
        try:
            self._preview_selected_widget_index = None
            self._clear_ice_preview_selection("")
            self._clear_water_surface_preview_selection("")
            self._clear_bamboo_grove_preview_selection("")
            self._pending_puddle_state = None
            self._pending_puddle_states = {}
            self._cloud_selected = True
            state = self._current_cloud_layer_state()
            self._drag_notice = f"Cloud selected / move+resize count={int(state.get('count', 0))} size={float(state.get('size', 92.0)):.1f}"
            self.update()
            self._notify_integrated_selection_bar_changed()
        except Exception:
            pass

    def _clear_cloud_layer_preview_selection(self, notice=""):
        try:
            if bool(getattr(self, "_cloud_selected", False)):
                self._cloud_selected = False
                self._cloud_drag_start_pos = None
                self._cloud_drag_start_state = None
                self._cloud_resize_drag_start_pos = None
                self._cloud_resize_drag_start_state = None
                if notice:
                    self._drag_notice = str(notice)
                self.update()
                self._notify_integrated_selection_bar_changed()
        except Exception:
            pass

    def _draw_single_cloud_3d_marker(self, painter, center, scale, main_color, shadow_color, highlight_color, softness=0.72):
        try:
            softness = max(0.0, min(1.0, float(softness)))
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            main = QColor(main_color)
            shadow = QColor(shadow_color)
            hi = QColor(highlight_color)
            base_alpha = max(65, min(215, int(150 + softness * 45)))
            shadow.setAlpha(max(35, min(155, int(base_alpha * 0.48))))
            main.setAlpha(base_alpha)
            hi.setAlpha(max(40, min(180, int(base_alpha * 0.55))))
            puff_specs = [
                (-0.55, 0.18, 0.62, 0.40),
                (-0.20, -0.08, 0.78, 0.52),
                (0.24, -0.04, 0.70, 0.48),
                (0.58, 0.16, 0.54, 0.34),
                (0.02, 0.20, 1.12, 0.34),
            ]
            for ox, oy, rw, rh in puff_specs:
                rect = QRectF(
                    center.x() + ox * scale - rw * scale * 0.5,
                    center.y() + oy * scale - rh * scale * 0.5,
                    rw * scale,
                    rh * scale,
                )
                grad = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.62)
                c0 = QColor(hi if oy < 0.02 else main)
                c1 = QColor(main)
                c2 = QColor(main)
                c2.setAlpha(0)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(0.58 + softness * 0.18, c1)
                grad.setColorAt(1.0, c2)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(rect)
            shadow_rect = QRectF(center.x() - scale * 0.70, center.y() + scale * 0.14, scale * 1.38, scale * 0.34)
            painter.setBrush(QBrush(shadow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(shadow_rect)
            painter.restore()
        except Exception:
            try:
                painter.restore()
            except Exception:
                pass

    def _draw_cloud_layer_marker(self, painter, effect):
        """Display-only 3D marker for Cloud effect clipped to the pseudo desktop plane."""
        try:
            plane_path = self._desktop_plane_path()
            if plane_path is None:
                return
            bounds = plane_path.boundingRect()
            if bounds.width() <= 2 or bounds.height() <= 2:
                return
            cloud_state = dict(self._current_cloud_layer_state() or {})
            count = max(0, min(24, int(cloud_state.get("count", effect.get("cloud_count", 0)))))
            if count <= 0:
                count = 5
            size = max(18.0, min(180.0, float(cloud_state.get("size", effect.get("cloud_size", 92.0)))))
            speed = max(0.0, min(2.0, float(cloud_state.get("speed", effect.get("cloud_speed", 0.075)))))
            softness = max(0.0, min(1.0, float(effect.get("cloud_softness", 0.72))))
            main_color = QColor(str(effect.get("cloud_color", "#F4FAFF") or "#F4FAFF"))
            shadow_color = QColor(str(effect.get("cloud_shadow_color", "#C1CFDA") or "#C1CFDA"))
            highlight_color = QColor(str(effect.get("cloud_highlight_color", "#FFFFFF") or "#FFFFFF"))
            marker_path = self._cloud_layer_marker_path()
            marker_bounds = marker_path.boundingRect() if marker_path is not None else bounds
            if marker_bounds.width() <= 2 or marker_bounds.height() <= 2:
                marker_bounds = bounds
            painter.save()
            painter.setClipPath(plane_path)
            if bool(getattr(self, "_cloud_selected", False)):
                try:
                    if marker_path is not None:
                        painter.setBrush(QBrush(QColor(150, 220, 255, 32)))
                        painter.setPen(QPen(QColor(225, 245, 255, 190), 2.0))
                        painter.drawPath(marker_path)
                    handle_rect = self._cloud_layer_resize_handle_rect()
                    if handle_rect is not None:
                        painter.setBrush(QBrush(QColor(235, 248, 255, 245)))
                        painter.setPen(QPen(QColor(50, 90, 120, 245), 2.0))
                        painter.drawRoundedRect(handle_rect, 4.0, 4.0)
                        painter.drawLine(QPointF(handle_rect.left() + 4.0, handle_rect.bottom() - 4.0), QPointF(handle_rect.right() - 4.0, handle_rect.top() + 4.0))
                except Exception:
                    pass
            phase = float(getattr(self, "_frame", 0)) * 0.0025 * (0.40 + speed)
            visible_count = max(1, min(count, 12))
            scale_limit = max(10.0, min(marker_bounds.width() * 0.24, marker_bounds.height() * 0.50))
            for i in range(visible_count):
                row = i % 3
                slot = (i + 0.37 * row) / max(1, visible_count)
                drift = (phase + math.sin((i + 1) * 1.91) * 0.015) % 1.0
                u = (slot + drift) % 1.0
                cloud_scale = max(8.0, min(scale_limit, size * (0.32 + 0.12 * ((math.sin(i * 3.11) + 1.0) * 0.5))))
                margin = max(8.0, cloud_scale * 0.85)
                usable_w = max(1.0, marker_bounds.width() - margin * 2.0)
                x = marker_bounds.left() + margin + usable_w * u
                y = marker_bounds.top() + marker_bounds.height() * (0.22 + 0.22 * row + 0.045 * math.sin(i * 2.17 + phase * 10.0))
                y = max(marker_bounds.top() + margin * 0.45, min(marker_bounds.bottom() - margin * 0.55, y))
                self._draw_single_cloud_3d_marker(
                    painter,
                    QPointF(x, y),
                    cloud_scale,
                    main_color,
                    shadow_color,
                    highlight_color,
                    softness,
                )
            try:
                painter.setPen(QPen(QColor(225, 245, 255, 205), 1.0))
                painter.drawText(QPointF(bounds.left() + 10.0, bounds.top() + 18.0), "Cloud [move+resize]" + (" [selected]" if bool(getattr(self, "_cloud_selected", False)) else ""))
            except Exception:
                pass
            painter.restore()
        except Exception:
            try:
                painter.restore()
            except Exception:
                pass
            return

    def _lds_global_display_edit_lock_active(self):
        """Return True when a global/background template effect is active.

        While a global_display template effect is active, preset/built-in visual
        helpers such as Cloud, Water Surface, Puddle, Ice, Bamboo, Sun/Moon and
        Fireball are treated as part of the preset scene and are not directly
        editable from the 3D preview.  This prevents touching those helper
        objects from closing or destabilizing the global effect preview.
        """
        try:
            for key, _spec in self._lds_template_effect_specs(("global_display",)):
                state = self._lds_template_effect_state(key)
                if bool(dict(state or {}).get("visible", False)):
                    return True
        except Exception:
            pass
        return False

    def _lds_template_effect_label(self, key):
        try:
            spec = self._lds_template_effect_spec(str(key or "")) or {}
            return str(dict(spec or {}).get("display_name") or key)
        except Exception:
            return str(key or "")

    def _disable_template_effect_preview_pending(self, key):
        try:
            key = str(key or "")
            if not key:
                return False
            spec = self._lds_template_effect_spec(key) or {}
            if not spec:
                return False
            spec = dict(spec or {})
            mode = str(spec.get("mode", "")) or "display_toggle_only"
            pending = dict(getattr(self, "_pending_template_effect_states", {}) or {})
            item = {"visible": False, "mode": mode}
            if mode == "anchor_point":
                try:
                    state_now = self._lds_template_effect_state(key) or {}
                    item["x"] = max(0.0, min(1.0, float(state_now.get("x", spec.get("default_x", 0.5)))))
                    item["y"] = max(0.0, min(1.0, float(state_now.get("y", spec.get("default_y", 0.5)))))
                except Exception:
                    pass
            pending[key] = item
            self._pending_template_effect_states = pending
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect[f"{key}_visible"] = False
            try:
                enabled_key = str(spec.get("enabled_key") or f"{key}_enabled")
                effect[enabled_key] = False
            except Exception:
                pass
            state["effect"] = effect
            self._preview_state = state
            if str(getattr(self, "_template_effect_selected_key", "") or "") == key:
                self._template_effect_selected_key = None
            try:
                self._drag_notice = f"Effect disabled: {self._lds_template_effect_label(key)} / Apply or Save to persist"
                self.update()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _lds_template_effect_specs(self, modes=None):
        try:
            data = globals().get("LDS_3D_EFFECT_TEMPLATE_RUNTIME", {}) or {}
            effects = dict(data.get("effects", {}) or {})
            wanted = set(modes or []) if modes else None
            out = []
            for key, spec in effects.items():
                spec = dict(spec or {})
                mode = str(spec.get("mode", ""))
                if mode == "preview_skip":
                    continue
                if wanted is not None and mode not in wanted:
                    continue
                spec.setdefault("effect_key", key)
                spec.setdefault("display_name", key.replace("_", " ").title())
                spec.setdefault("enabled_key", f"{key}_enabled")
                spec.setdefault("x_key", f"{key}_x")
                spec.setdefault("y_key", f"{key}_y")
                spec.setdefault("default_x", 0.5)
                spec.setdefault("default_y", 0.5)
                out.append((key, spec))
            return out
        except Exception:
            return []

    def _lds_template_effect_spec(self, key):
        for item_key, spec in self._lds_template_effect_specs():
            if item_key == str(key or ""):
                return dict(spec or {})
        return None

    def _lds_template_effect_state(self, key):
        try:
            spec = self._lds_template_effect_spec(key) or {}
            effect = dict((getattr(self, "_preview_state", {}) or {}).get("effect", {}) or {})
            pending = dict(getattr(self, "_pending_template_effect_states", {}) or {}).get(str(key or ""), None)
            x_key = str(spec.get("x_key") or f"{key}_x")
            y_key = str(spec.get("y_key") or f"{key}_y")
            state = {
                "visible": bool(effect.get(f"{key}_visible", effect.get(str(spec.get("enabled_key") or f"{key}_enabled"), False))),
                "x": float(effect.get(x_key, spec.get("default_x", 0.5))),
                "y": float(effect.get(y_key, spec.get("default_y", 0.5))),
                "display_name": str(spec.get("display_name", key)),
                "mode": str(spec.get("mode", "")),
            }
            if pending is not None:
                pending = dict(pending or {})
                state["visible"] = bool(pending.get("visible", state["visible"]))
                state["x"] = max(0.0, min(1.0, float(pending.get("x", state["x"]))))
                state["y"] = max(0.0, min(1.0, float(pending.get("y", state["y"]))))
            return state
        except Exception:
            return {"visible": False, "x": 0.5, "y": 0.5, "display_name": str(key or ""), "mode": ""}

    def _lds_template_marker_path(self, key):
        try:
            state = self._lds_template_effect_state(key)
            if not bool(state.get("visible", False)):
                return None
            px, pz = self._unit_to_plane(state.get("x", 0.5), state.get("y", 0.5))
            center, scale = self._project_point(px, 10.0, pz)
            radius = max(10.0, 16.0 * float(scale))
            path = QPainterPath()
            path.addEllipse(center, radius, radius)
            return path
        except Exception:
            return None

    def _lds_template_hit_effect_key(self, pos):
        try:
            # Phase23E v2G: global_display effects must not capture the whole
            # desktop plane.  They are display/background-style effects; if the
            # entire plane is treated as their hit target, clicks cannot reach
            # the Effects Overlay/widget selection path and the user can be
            # trapped out of the effect preview.  Only movable anchor_point
            # template effects participate in direct hit-testing here.
            for key, spec in reversed(self._lds_template_effect_specs(("anchor_point",))):
                state = self._lds_template_effect_state(key)
                if not bool(state.get("visible", False)):
                    continue
                path = self._lds_template_marker_path(key)
                if path is not None and path.contains(QPointF(pos)):
                    return key
        except Exception:
            pass
        return None

    def _lds_template_select_effect_preview(self, key):
        self._template_effect_selected_key = str(key or "") or None
        self._water_surface_selected = False
        self._bamboo_grove_selected = False
        self._cloud_selected = False
        self._fireball_selected = False
        self._ice_selected = False
        self._preview_selection_suppressed = True
        spec = self._lds_template_effect_spec(key) or {}
        self._drag_notice = f"{spec.get('display_name', key)} selected"
        try: self.update()
        except Exception: pass

    def _lds_template_begin_move_drag(self, key, pos):
        self._template_effect_selected_key = str(key or "")
        self._template_effect_drag_start_pos = QPointF(pos)
        self._template_effect_drag_start_state = dict(self._lds_template_effect_state(key) or {})

    def _lds_template_set_temp_from_pos(self, pos):
        try:
            key = str(getattr(self, "_template_effect_selected_key", "") or "")
            if not key:
                return
            spec = self._lds_template_effect_spec(key) or {}
            start = dict(getattr(self, "_template_effect_drag_start_state", None) or self._lds_template_effect_state(key) or {})
            nx, ny = self._screen_to_unit_on_desktop(pos, start.get("x", 0.5), start.get("y", 0.5))
            nx = max(0.0, min(1.0, self._snap_float_value(float(nx), 0.02)))
            ny = max(0.0, min(1.0, self._snap_float_value(float(ny), 0.02)))
            pending = dict(getattr(self, "_pending_template_effect_states", {}) or {})
            pending[key] = {"x": nx, "y": ny, "visible": True}
            self._pending_template_effect_states = pending
            state = dict(getattr(self, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            effect[f"{key}_visible"] = True
            if spec.get("x_key"):
                effect[str(spec.get("x_key"))] = nx
            if spec.get("y_key"):
                effect[str(spec.get("y_key"))] = ny
            state["effect"] = effect
            self._preview_state = state
            snap_tag = " SNAP" if self.is_snap_enabled() else ""
            self._drag_notice = f"{spec.get('display_name', key)} preview-only{snap_tag} x={nx:.3f} y={ny:.3f}"
            self.update()
        except Exception:
            pass

    def _lds_draw_template_effects(self, painter):
        drew = False
        try:
            # Phase23E v2C: template effects are allowed to draw whenever the
            # preview state contains enabled template effect data.  This avoids
            # hiding them when the user has not explicitly selected the Effects
            # Overlay in the 3D preview yet.  Existing built-in effect markers
            # still keep their own _should_show_effect_objects() gate.
            for key, spec in self._lds_template_effect_specs(("anchor_point",)):
                state = self._lds_template_effect_state(key)
                if not bool(state.get("visible", False)):
                    continue
                px, pz = self._unit_to_plane(state.get("x", 0.5), state.get("y", 0.5))
                selected = str(getattr(self, "_template_effect_selected_key", "") or "") == key
                color = QColor(255, 214, 120) if selected else QColor(120, 220, 255)
                self._draw_marker(painter, px, pz, 18.0 if selected else 14.0, color, str(spec.get("display_name", key)))
                drew = True
            chip_y = 22.0
            for key, spec in self._lds_template_effect_specs(("global_display", "display_toggle_only")):
                state = self._lds_template_effect_state(key)
                if not bool(state.get("visible", False)):
                    continue
                selected = str(getattr(self, "_template_effect_selected_key", "") or "") == key
                label = str(spec.get("display_name", key)) + (" [selected]" if selected else "")
                if str(spec.get("mode")) == "global_display":
                    path = self._desktop_plane_path()
                    if path is not None:
                        painter.setPen(QPen(QColor(255, 214, 120, 230) if selected else QColor(150, 210, 255, 130), 2.0 if selected else 1.1))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawPath(path)
                painter.setPen(QPen(QColor(255, 238, 180, 240) if selected else QColor(210, 238, 255, 210), 1.0))
                painter.drawText(QPointF(18.0, chip_y), label)
                chip_y += 16.0
                drew = True
        except Exception:
            pass
        return drew

    def _current_fireball_layer_state(self):
        try:
            effect = dict((getattr(self, "_preview_state", {}) or {}).get("effect", {}) or {})
            state = {
                "visible": bool(effect.get("fireball_visible", False)),
                "count": int(effect.get("fireball_count", 0)),
                "size": float(effect.get("fireball_size", 20.0)),
                "x": float(effect.get("fireball_x", 0.50)),
                "y": float(effect.get("fireball_y", 0.38)),
                "speed": float(effect.get("fireball_speed", 0.34)),
            }
            pending = getattr(self, "_pending_fireball_layer_state", None)
            if pending is not None:
                pending = dict(pending or {})
                state["visible"] = bool(pending.get("visible", True))
                state["x"] = max(0.0, min(1.0, float(pending.get("x", state.get("x", 0.50)))))
                state["y"] = max(0.0, min(1.0, float(pending.get("y", state.get("y", 0.38)))))
            return state
        except Exception:
            return {"visible": False, "count": 0, "size": 20.0, "x": 0.50, "y": 0.38, "speed": 0.34}

    def _fireball_layer_marker_path(self):
        try:
            state = self._current_fireball_layer_state()
            if not bool(state.get("visible", False)):
                return None
            plane_path = self._desktop_plane_path()
            if plane_path is None:
                return None
            bounds = plane_path.boundingRect()
            if bounds.width() <= 2 or bounds.height() <= 2:
                return None
            # Fireballs move quickly, so use a forgiving movable interaction band around the emitter center.
            cx = bounds.left() + bounds.width() * max(0.0, min(1.0, float(state.get("x", 0.50))))
            cy = bounds.top() + bounds.height() * max(0.0, min(1.0, float(state.get("y", 0.38))))
            rect_w = bounds.width() * 0.78
            rect_h = bounds.height() * 0.62
            left = max(bounds.left(), min(bounds.right() - rect_w, cx - rect_w * 0.5))
            top = max(bounds.top(), min(bounds.bottom() - rect_h, cy - rect_h * 0.5))
            rect = QRectF(left, top, rect_w, rect_h)
            path = QPainterPath()
            path.addRoundedRect(rect, 8.0, 8.0)
            return path
        except Exception:
            return None

    def _hit_fireball_layer_marker(self, pos):
        if self._lds_global_display_edit_lock_active():
            return False
        if not self._should_show_effect_objects():
            return False
        try:
            path = self._fireball_layer_marker_path()
            if path is None:
                return False
            return bool(path.contains(QPointF(float(pos.x()), float(pos.y()))))
        except Exception:
            return False

    def _select_fireball_layer_preview(self):
        try:
            self._preview_selected_widget_index = None
            self._clear_ice_preview_selection("")
            self._clear_water_surface_preview_selection("")
            self._clear_bamboo_grove_preview_selection("")
            self._clear_cloud_layer_preview_selection("")
            self._pending_puddle_state = None
            self._pending_puddle_states = {}
            self._fireball_selected = True
            state = self._current_fireball_layer_state()
            self._drag_notice = f"Fireball selected / display-only count={int(state.get('count', 0))} size={float(state.get('size', 20.0)):.1f}"
            self.update()
            self._notify_integrated_selection_bar_changed()
        except Exception:
            pass

    def _clear_fireball_layer_preview_selection(self, notice=""):
        try:
            if bool(getattr(self, "_fireball_selected", False)):
                self._fireball_selected = False
                if notice:
                    self._drag_notice = str(notice)
                self.update()
                self._notify_integrated_selection_bar_changed()
        except Exception:
            pass

    def _begin_fireball_layer_move_drag(self, pos):
        self._fireball_drag_start_pos = QPointF(float(pos.x()), float(pos.y()))
        self._fireball_drag_start_state = dict(self._current_fireball_layer_state() or {})

    def _set_temp_fireball_layer_state(self, x=None, y=None):
        state = dict(self._current_fireball_layer_state() or {})
        x = state.get("x", 0.50) if x is None else x
        y = state.get("y", 0.38) if y is None else y
        x = max(0.0, min(1.0, float(x)))
        y = max(0.0, min(1.0, float(y)))
        try:
            if self.is_snap_enabled():
                x = max(0.0, min(1.0, self._snap_float_value(x, 0.02)))
                y = max(0.0, min(1.0, self._snap_float_value(y, 0.02)))
        except Exception:
            pass
        self._pending_fireball_layer_state = {"x": x, "y": y, "visible": True}
        self._fireball_selected = True
        self._drag_notice = f"Fireball preview-only x={x:.2f} y={y:.2f}" + (" SNAP" if self.is_snap_enabled() else "")
        self.update()
        self._notify_integrated_selection_bar_changed()

    def _set_temp_fireball_layer_from_drag_delta(self, pos):
        try:
            start = getattr(self, "_fireball_drag_start_pos", None)
            state = dict(getattr(self, "_fireball_drag_start_state", None) or self._current_fireball_layer_state() or {})
            if start is None:
                self._begin_fireball_layer_move_drag(pos)
                start = getattr(self, "_fireball_drag_start_pos", None)
                state = dict(getattr(self, "_fireball_drag_start_state", None) or self._current_fireball_layer_state() or {})
            path = self._desktop_plane_path()
            bounds = path.boundingRect() if path is not None else QRectF(0, 0, max(1, self.width()), max(1, self.height()))
            dx = (float(pos.x()) - float(start.x())) / max(1.0, bounds.width())
            dy = (float(pos.y()) - float(start.y())) / max(1.0, bounds.height())
            self._set_temp_fireball_layer_state(float(state.get("x", 0.50)) + dx, float(state.get("y", 0.38)) + dy)
        except Exception:
            pass

    def _draw_single_fireball_3d_marker(self, painter, center, radius, direction, core_color, mid_color, edge_color, trail_color):
        try:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            dx = math.cos(direction)
            dy = math.sin(direction)
            tail_len = max(18.0, radius * 3.2)
            tail_w = max(6.0, radius * 1.2)
            tip = QPointF(center.x(), center.y())
            tail = QPointF(center.x() - dx * tail_len, center.y() - dy * tail_len)
            nx = -dy
            ny = dx
            path = QPainterPath()
            path.moveTo(tip)
            path.quadTo(QPointF(center.x() - dx * tail_len * 0.55 + nx * tail_w, center.y() - dy * tail_len * 0.55 + ny * tail_w), tail)
            path.quadTo(QPointF(center.x() - dx * tail_len * 0.52 - nx * tail_w, center.y() - dy * tail_len * 0.52 - ny * tail_w), tip)
            path.closeSubpath()
            trail = QColor(trail_color)
            trail.setAlpha(125)
            edge = QColor(edge_color)
            edge.setAlpha(175)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(trail))
            painter.drawPath(path)
            grad = QRadialGradient(center, radius * 1.55)
            core = QColor(core_color); core.setAlpha(245)
            mid = QColor(mid_color); mid.setAlpha(220)
            edge2 = QColor(edge_color); edge2.setAlpha(30)
            grad.setColorAt(0.0, core)
            grad.setColorAt(0.46, mid)
            grad.setColorAt(1.0, edge2)
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(edge, max(1.0, radius * 0.12)))
            painter.drawEllipse(center, radius, radius)
            painter.restore()
        except Exception:
            try:
                painter.restore()
            except Exception:
                pass

    def _draw_fireball_layer_marker(self, painter, effect):
        """Display-only 3D marker for Fireball effect. No hit/pending/apply behavior in Phase 23D-1."""
        try:
            plane_path = self._desktop_plane_path()
            if plane_path is None:
                return
            bounds = plane_path.boundingRect()
            if bounds.width() <= 2 or bounds.height() <= 2:
                return
            fireball_state = dict(self._current_fireball_layer_state() or {})
            count = max(0, min(24, int(fireball_state.get("count", effect.get("fireball_count", 0)))))
            if count <= 0:
                count = 4
            size = max(4.0, min(80.0, float(fireball_state.get("size", effect.get("fireball_size", 20.0)))))
            speed = max(0.0, min(2.0, float(fireball_state.get("speed", effect.get("fireball_speed", 0.34)))))
            core_color = QColor(str(effect.get("fireball_core_color", "#FFFFBE") or "#FFFFBE"))
            mid_color = QColor(str(effect.get("fireball_mid_color", "#FF7828") or "#FF7828"))
            edge_color = QColor(str(effect.get("fireball_edge_color", "#AA1400") or "#AA1400"))
            trail_color = QColor(str(effect.get("fireball_trail_color", "#FF5A14") or "#FF5A14"))
            marker_path = self._fireball_layer_marker_path()
            marker_bounds = marker_path.boundingRect() if marker_path is not None else bounds
            if marker_bounds.width() <= 2 or marker_bounds.height() <= 2:
                marker_bounds = bounds
            painter.save()
            painter.setClipPath(plane_path)
            if bool(getattr(self, "_fireball_selected", False)):
                try:
                    if marker_path is not None:
                        painter.setBrush(QBrush(QColor(255, 120, 70, 24)))
                        painter.setPen(QPen(QColor(255, 200, 130, 190), 2.0))
                        painter.drawPath(marker_path)
                except Exception:
                    pass
            phase = float(getattr(self, "_frame", 0)) * 0.0065 * (0.45 + speed)
            visible_count = max(1, min(count, 10))
            direction = math.radians(34.0)
            for i in range(visible_count):
                lane = i % 4
                u = (phase + i * 0.173 + lane * 0.045) % 1.0
                x = marker_bounds.left() + marker_bounds.width() * (0.06 + 0.88 * u)
                y = marker_bounds.top() + marker_bounds.height() * (0.16 + 0.21 * lane)
                y += math.sin(phase * 9.0 + i * 1.7) * marker_bounds.height() * 0.025
                radius = min(max(5.0, size * (0.38 + 0.12 * math.sin(i * 2.13 + phase * 4.0))), marker_bounds.height() * 0.13)
                self._draw_single_fireball_3d_marker(
                    painter,
                    QPointF(x, y),
                    radius,
                    direction,
                    core_color,
                    mid_color,
                    edge_color,
                    trail_color,
                )
            try:
                painter.setPen(QPen(QColor(255, 210, 160, 220), 1.0))
                painter.drawText(QPointF(marker_bounds.left() + 10.0, marker_bounds.top() + 36.0), "Fireball [move-only]" + (" [selected]" if bool(getattr(self, "_fireball_selected", False)) else ""))
            except Exception:
                pass
            painter.restore()
        except Exception:
            try:
                painter.restore()
            except Exception:
                pass
            return

    def _draw_preview_objects(self, painter):
        import math as _math
        t = float(self._frame) * 0.035
        state = dict(getattr(self, "_preview_state", {}) or {})
        effect = dict(state.get("effect", {}) or {})
        selected = dict(state.get("selected", {}) or {})

        # Show all widget footprints so lower/non-top layers can be selected from 3D view.
        self._draw_all_widget_rect_markers(painter)

        # Effect overlay markers are only shown while an Effects Overlay widget is selected.
        drew_any_effect = False
        if self._should_show_effect_objects():
            if effect.get("cloud_visible"):
                self._draw_cloud_layer_marker(painter, effect)
                drew_any_effect = True
            if effect.get("fireball_visible"):
                self._draw_fireball_layer_marker(painter, effect)
                drew_any_effect = True
            if effect.get("bamboo_grove_visible"):
                self._draw_bamboo_grove_marker(painter, effect)
                drew_any_effect = True
            if effect.get("sun_visible"):
                sx, sz = self._unit_to_plane(effect.get("sun_x", 0.22), effect.get("sun_y", 0.22))
                self._draw_marker(painter, sx, sz, 30.0 + _math.sin(t) * 2.0, QColor(255, 191, 86), "Sun")
                drew_any_effect = True
            if effect.get("moon_visible"):
                mu, mv, _visible = self._current_moon_unit()
                mx, mz = self._unit_to_plane(mu, mv)
                self._draw_marker(painter, mx, mz, 24.0, QColor(210, 226, 255), "Moon")
                drew_any_effect = True
            if effect.get("water_surface_visible"):
                water_surface = self._current_water_surface_state()
                if water_surface.get("visible"):
                    self._draw_water_surface_marker(
                        painter,
                        water_surface.get("y", 0.58),
                        water_surface.get("depth", 0.42),
                        "Water Surface",
                        water_surface.get("color", "#4FC3FF"),
                        water_surface.get("highlight_color", "#D8FAFF"),
                        water_surface.get("alpha", 92),
                        selected=bool(getattr(self, "_water_surface_selected", False)),
                    )
                    drew_any_effect = True
            if effect.get("ice_visible"):
                ice_selected = bool(getattr(self, "_ice_selected", False))
                self._draw_ice_marker(
                    painter,
                    effect.get("ice_x", 0.50),
                    effect.get("ice_y", 0.58),
                    effect.get("ice_width", 1.0),
                    effect.get("ice_depth", 0.42),
                    "Ice",
                    selected=ice_selected,
                )
                if ice_selected:
                    self._draw_ice_resize_handle(painter)
                drew_any_effect = True
            if effect.get("puddle_visible"):
                puddles = self._all_puddle_states()
                if puddles:
                    selected_puddle_index = int(getattr(self, "_selected_puddle_index", 0))
                    for i, puddle in enumerate(puddles):
                        puddle_index = int(puddle.get("index", i))
                        self._draw_puddle_marker(
                            painter,
                            puddle.get("x", 0.50),
                            puddle.get("y", 0.84),
                            puddle.get("width", 0.20),
                            puddle.get("height", 0.08),
                            "Puddle" if puddle_index == 0 else f"Puddle {puddle_index + 1}",
                            show_handle=(puddle_index == selected_puddle_index),
                            selected=(puddle_index == selected_puddle_index),
                        )
                    drew_any_effect = True
                else:
                    puddle = self._current_puddle_state()
                    self._draw_puddle_marker(
                        painter,
                        puddle.get("x", 0.50),
                        puddle.get("y", 0.84),
                        puddle.get("width", 0.20),
                        puddle.get("height", 0.08),
                        "Puddle",
                    )
                    drew_any_effect = True

            if self._lds_draw_template_effects(painter):
                drew_any_effect = True

            # Do not draw fallback/demo effect markers in the real editing view.
            # If settings sync is briefly empty after saving, fake Sun/Moon/Water Surface/Ice/Puddle
            # markers look like real effects suddenly appeared.
            if not drew_any_effect:
                pass

    def _preview_mode_label_text(self):
        try:
            if str(getattr(self, "_template_effect_selected_key", "") or ""):
                return "Effects Overlay"
            if self._is_effect_overlay_selected():
                return "Effects Overlay"
            if self._is_normal_widget_selected():
                return "Widget"
        except Exception:
            pass
        return "None"

    def _pending_change_lines(self):
        lines = []
        try:
            changes = self.pending_preview_changes()
            if not changes:
                return ["Pending: none"]
            names = []
            if "widget" in changes:
                item = dict(changes.get("widget") or {})
                names.append("Widget")
                lines.append(
                    "Pending Widget: "
                    f"x={item.get('x', '-')} y={item.get('y', '-')} "
                    f"w={item.get('w', '-')} h={item.get('h', '-')} "
                    f"rot={float(item.get('rotation', 0.0)):.1f}°"
                )
            if "sun" in changes:
                item = dict(changes.get("sun") or {})
                names.append("Sun")
                lines.append(f"Pending Sun: x={float(item.get('x', 0.0)):.3f} y={float(item.get('y', 0.0)):.3f}")
            if "moon" in changes:
                item = dict(changes.get("moon") or {})
                names.append("Moon")
                lines.append(f"Pending Moon: x={float(item.get('x', 0.0)):.3f} y={float(item.get('y', 0.0)):.3f}")
            if "puddle" in changes:
                item = dict(changes.get("puddle") or {})
                names.append("Puddle")
                lines.append(
                    "Pending Puddle: "
                    f"x={float(item.get('x', 0.0)):.3f} y={float(item.get('y', 0.0)):.3f} "
                    f"w={float(item.get('width', 0.0)):.3f} h={float(item.get('height', 0.0)):.3f}"
                )
            if "water_surface" in changes:
                item = dict(changes.get("water_surface") or {})
                names.append("Water Surface")
                lines.append(
                    "Pending Water Surface: "
                    f"y={float(item.get('y', 0.0)):.3f} depth={float(item.get('depth', 0.0)):.3f}"
                )
            if names:
                lines.insert(0, "Pending targets: " + ", ".join(names))
            return lines or ["Pending: none"]
        except Exception:
            return ["Pending: unknown"]

    def _selected_detail_lines(self):
        try:
            state = dict(getattr(self, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            if not selected:
                return ["Selected: none"]
            title = selected.get("title") or selected.get("type") or "Widget"
            selected_type = str(selected.get("type", ""))
            lines = [f"Selected: {title} [{selected_type}]"]
            if selected_type:
                lines.append(
                    f"Geometry: x={selected.get('x', '-')} y={selected.get('y', '-')} "
                    f"w={selected.get('w', '-')} h={selected.get('h', '-')} "
                    f"rot={float(selected.get('rotation', 0.0)):.1f}°"
                )
            template_key = str(getattr(self, "_template_effect_selected_key", "") or "")
            if template_key:
                try:
                    spec = self._lds_template_effect_spec(template_key) or {}
                    tstate = self._lds_template_effect_state(template_key) or {}
                    tmode = str(spec.get("mode", tstate.get("mode", "")) or "")
                    if tmode == "anchor_point":
                        lines.append(
                            f"Effect: {spec.get('display_name', template_key)} [anchor-move] "
                            f"x={float(tstate.get('x', spec.get('default_x', 0.5))):.3f} "
                            f"y={float(tstate.get('y', spec.get('default_y', 0.5))):.3f}"
                        )
                    elif tmode:
                        lines.append(f"Effect: {spec.get('display_name', template_key)} [{tmode}]")
                except Exception:
                    lines.append(f"Effect: {template_key}")
            if bool(getattr(self, "_water_surface_selected", False)):
                water = self._current_water_surface_state()
                lines.append(
                    "Effect: Water Surface [move+depth-resize] "
                    f"y={float(water.get('y', 0.58)):.3f} "
                    f"depth={float(water.get('depth', 0.42)):.3f}"
                )
            return lines
        except Exception:
            return ["Selected: unknown"]

    def _draw_transient_notice(self, painter):
        try:
            notice = str(getattr(self, "_transient_notice_text", "") or "")
            until = float(getattr(self, "_transient_notice_until", 0.0) or 0.0)
            if not notice or time.time() > until:
                if notice:
                    self._transient_notice_text = ""
                    self._transient_notice_until = 0.0
                return
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            try:
                text_w = metrics.horizontalAdvance(notice)
            except Exception:
                text_w = len(notice) * 9
            panel_w = min(max(340, text_w + 42), max(340, self.width() - 32))
            panel_h = 42
            panel_x = max(16.0, (float(self.width()) - float(panel_w)) * 0.5)
            panel_y = max(16.0, float(self.height()) - float(panel_h) - 24.0)
            panel = QRectF(panel_x, panel_y, panel_w, panel_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(16, 22, 36, 218)))
            painter.drawRoundedRect(panel, 12, 12)
            painter.setPen(QPen(QColor(255, 214, 120, 230), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(panel, 12, 12)
            painter.setPen(QPen(QColor(255, 238, 180, 245), 1.0))
            painter.drawText(QPointF(panel.left() + 18.0, panel.top() + 27.0), notice)
        except Exception:
            pass

    def _draw_fault_structure_panel(self, painter):
        """Phase 24A-8i: diagnostics-only right-side fault/strata structure panel."""
        try:
            if not self.is_developer_mode():
                return
            width = max(1, int(self.width()))
            height = max(1, int(self.height()))
            if width < 720 or height < 360:
                return
            panel_w = min(260.0, max(210.0, width * 0.24))
            panel_h = min(330.0, max(250.0, height * 0.48))
            panel = QRectF(width - panel_w - 18.0, 72.0, panel_w, panel_h)
            theme = self.preview_background_theme()
            light_theme = theme in ("light_nvd", "white")
            lime_theme = theme == "black_lime"
            if light_theme:
                bg = QColor(248, 250, 252, 218)
                border = QColor(78, 88, 98, 185)
                title = QColor(42, 50, 58, 235)
                text = QColor(56, 66, 76, 225)
                fault = QColor(72, 84, 96, 230)
                layer_colors = [
                    QColor(232, 236, 240, 210),
                    QColor(214, 220, 226, 210),
                    QColor(196, 204, 212, 210),
                    QColor(178, 188, 198, 210),
                ]
            elif lime_theme:
                bg = QColor(0, 0, 0, 204)
                border = QColor(118, 185, 0, 220)
                title = QColor(184, 255, 64, 235)
                text = QColor(198, 238, 142, 225)
                fault = QColor(210, 255, 92, 242)
                layer_colors = [
                    QColor(18, 42, 4, 218),
                    QColor(30, 66, 8, 218),
                    QColor(48, 92, 12, 218),
                    QColor(70, 120, 18, 218),
                ]
            else:
                bg = QColor(10, 16, 28, 216)
                border = QColor(138, 204, 255, 150)
                title = QColor(225, 242, 255, 238)
                text = QColor(204, 226, 245, 220)
                fault = QColor(255, 220, 120, 230)
                layer_colors = [
                    QColor(22, 36, 62, 218),
                    QColor(30, 52, 86, 218),
                    QColor(42, 68, 104, 218),
                    QColor(58, 82, 112, 218),
                ]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(panel, 12, 12)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(border, 1.25))
            painter.drawRoundedRect(panel, 12, 12)

            font = painter.font()
            old_size = font.pointSize()
            font.setPointSize(max(8, old_size))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(title, 1.0))
            painter.drawText(QPointF(panel.left() + 14.0, panel.top() + 24.0), lds_ui_text("断層構造", "Fault Structure"))
            font.setBold(False)
            font.setPointSize(max(7, old_size - 1))
            painter.setFont(font)

            diagram = QRectF(panel.left() + 14.0, panel.top() + 42.0, panel.width() - 28.0, panel.height() - 92.0)
            layer_count = 4
            layer_h = diagram.height() / float(layer_count)
            labels = [
                lds_ui_text("背景層", "Background"),
                lds_ui_text("効果層", "Effects"),
                lds_ui_text("デスクトップ面", "Desktop"),
                lds_ui_text("ウィジェット層", "Widgets"),
            ]
            offset = 22.0
            fault_x_top = diagram.left() + diagram.width() * 0.55
            fault_x_bottom = diagram.left() + diagram.width() * 0.33
            for i in range(layer_count):
                top = diagram.top() + i * layer_h
                left_shift = 0.0 if i < 2 else offset
                right_shift = offset if i < 2 else 0.0
                path_left = QPainterPath()
                path_left.moveTo(diagram.left() + left_shift, top)
                path_left.lineTo(fault_x_top + (fault_x_bottom - fault_x_top) * (i / layer_count), top)
                path_left.lineTo(fault_x_top + (fault_x_bottom - fault_x_top) * ((i + 1) / layer_count), top + layer_h)
                path_left.lineTo(diagram.left() + right_shift, top + layer_h)
                path_left.closeSubpath()
                color = layer_colors[i % len(layer_colors)]
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(border, 0.65))
                painter.drawPath(path_left)

                path_right = QPainterPath()
                path_right.moveTo(fault_x_top + (fault_x_bottom - fault_x_top) * (i / layer_count), top)
                path_right.lineTo(diagram.right() - right_shift, top)
                path_right.lineTo(diagram.right() - left_shift, top + layer_h)
                path_right.lineTo(fault_x_top + (fault_x_bottom - fault_x_top) * ((i + 1) / layer_count), top + layer_h)
                path_right.closeSubpath()
                c2 = QColor(color)
                c2 = c2.lighter(112 if not light_theme else 96)
                c2.setAlpha(color.alpha())
                painter.setBrush(QBrush(c2))
                painter.setPen(QPen(border, 0.65))
                painter.drawPath(path_right)

                painter.setPen(QPen(text, 0.8))
                painter.drawText(QPointF(diagram.left() + 8.0, top + layer_h * 0.58), labels[i])

            painter.setPen(QPen(fault, 2.2))
            painter.drawLine(QPointF(fault_x_top, diagram.top()), QPointF(fault_x_bottom, diagram.bottom()))
            painter.setPen(QPen(fault, 1.0))
            painter.drawText(QPointF(fault_x_bottom + 8.0, diagram.bottom() - 8.0), lds_ui_text("断層", "Fault"))

            painter.setPen(QPen(text, 0.8))
            footer_y = panel.bottom() - 38.0
            try:
                pending = self.pending_preview_changes()
                pending_count = len(dict(pending or {}))
            except Exception:
                pending_count = 0
            painter.drawText(QPointF(panel.left() + 14.0, footer_y), lds_ui_text("診断表示 / 右サイド構造図", "Diagnostics / right-side structure"))
            painter.drawText(QPointF(panel.left() + 14.0, footer_y + 18.0), f"Pending groups: {pending_count}")
        except Exception:
            pass

    def _draw_overlay_text(self, painter):
        if not self.is_developer_mode():
            return
        mode = "QOpenGLWidget" if QOpenGLWidget is not None else "QWidget fallback"
        lock_text = "ON" if self.is_desktop_locked() else "OFF"
        if self.is_desktop_locked():
            if self._is_effect_overlay_selected():
                hint = "Effects: Ice movable; all Puddles movable/resizable"
            elif self._is_normal_widget_selected():
                hint = "Widget: drag=move, green=size, blue=rotate; next effects expand gradually"
            else:
                hint = "Select a widget or Effects Overlay from Layers or 3D outlines"
        else:
            hint = "View mode: drag to orbit naturally / enable desktop lock to edit objects"

        lines = [
            "LiteDesktopStudio 3D Edit Preview",
            f"Surface: {mode} / desktop lock: {lock_text} / natural drag / yaw={self._yaw:.1f} pitch={self._pitch:.1f} zoom={self._zoom:.2f}",
            f"Mode: {self._preview_mode_label_text()}",
        ]
        lines.extend(self._selected_detail_lines())
        lines.extend(self._pending_change_lines())
        lines.append("Hint: " + hint)
        notice = str(getattr(self, "_drag_notice", "") or "")
        if notice:
            lines.append("Notice: " + notice)

        try:
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            max_width = 0
            for line in lines:
                try:
                    max_width = max(max_width, metrics.horizontalAdvance(str(line)))
                except Exception:
                    max_width = max(max_width, len(str(line)) * 8)
            line_h = max(15, metrics.height() + 2)
            panel_w = min(max(420, max_width + 28), max(420, self.width() - 24))
            panel_h = min(len(lines) * line_h + 22, max(90, self.height() - 24))
            panel = QRectF(12, 12, panel_w, panel_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(6, 10, 22, 178)))
            painter.drawRoundedRect(panel, 10, 10)
            painter.setPen(QPen(QColor(130, 200, 255, 120), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(panel, 10, 10)

            y = int(panel.top() + 18)
            for i, line in enumerate(lines):
                if i == 0:
                    title_font = painter.font()
                    title_font.setBold(True)
                    painter.setFont(title_font)
                    painter.setPen(QPen(QColor(255, 255, 255, 235), 1.0))
                elif str(line).startswith("Pending targets:"):
                    normal_font = painter.font()
                    normal_font.setBold(False)
                    painter.setFont(normal_font)
                    painter.setPen(QPen(QColor(255, 230, 130, 235), 1.0))
                elif str(line).startswith("Notice:"):
                    painter.setPen(QPen(QColor(160, 255, 180, 235), 1.0))
                elif str(line).startswith("Hint:"):
                    painter.setPen(QPen(QColor(210, 230, 255, 210), 1.0))
                else:
                    normal_font = painter.font()
                    normal_font.setBold(False)
                    painter.setFont(normal_font)
                    painter.setPen(QPen(QColor(230, 240, 255, 218), 1.0))
                painter.drawText(24, y, str(line))
                y += line_h
                if y > panel.bottom() - 8:
                    break
        except Exception:
            # Very small fallback if the styled panel fails.
            painter.setPen(QPen(QColor(255, 255, 255, 230), 1.0))
            y = 28
            for line in lines[:6]:
                painter.drawText(18, y, str(line))
                y += 22




class LDS3DEffectPresetPickerDialog(QDialog):
    """Lightweight 3D-preview preset picker for Effects Overlay template effects."""
    HEAVY_GLOBAL_PRESETS = {"uyuni_salt_flat", "sahara_desert", "chichibugahama_mirror"}

    PRESET_GROUPS = [
        {"title_ja":"全体エフェクト（軽め・標準）","title_en":"Global effects - light / standard","description_ja":"画面全体の背景として表示します。位置・サイズ変更は行いません。パムッカレは固定壁紙に近い軽め寄りの確認用プリセットです。","description_en":"Display as a full-scene/background effect. Position and size are not edited. Pamukkale is a lighter, mostly static scenic preset.","columns":3,"items":[
            {"key":"pamukkale_terrace_lake","label_ja":"パムッカレ","label_en":"Pamukkale"},
            {"key":"blue_hole_deep_lake","label_ja":"ブルーホール","label_en":"Blue Hole Deep Lake"},
            {"key":"antelope_canyon","label_ja":"アンテロープキャニオン","label_en":"Antelope Canyon"},
        ]},
        {"title_ja":"全体エフェクト（重め注意）","title_en":"Global effects - heavy caution","description_ja":"リアルタイムの太陽・空・雲・反射を含むため、環境によって重くなる可能性があります。Apply / 保存前にプレビューの動作を確認してください。","description_en":"These presets can be heavy because they include realtime sun, sky, clouds, or reflection work. Check preview responsiveness before Apply / Save.","columns":3,"items":[
            {"key":"uyuni_salt_flat","label_ja":"ウユニ塩湖","label_en":"Uyuni Salt Flat","heavy":True},
            {"key":"sahara_desert","label_ja":"サハラ砂漠","label_en":"Sahara Desert","heavy":True},
            {"key":"chichibugahama_mirror","label_ja":"父母ヶ浜ミラー","label_en":"Chichibugahama Mirror","heavy":True},
        ]},
        {"title_ja":"空・天候・光","title_en":"Sky, weather, and light","description_ja":"代表マーカーを表示し、3Dプレビュー上で位置だけ変更できる追加エフェクトです。","description_en":"Anchor-style effects with a representative marker; only position can be edited in the 3D preview.","columns":4,"items":[
            {"key":"snow","label_ja":"雪","label_en":"Snow"},{"key":"snow_crystal","label_ja":"雪の結晶","label_en":"Snow Crystal"},{"key":"rain","label_ja":"雨","label_en":"Rain"},{"key":"star_sky","label_ja":"星空","label_en":"Star Sky"},
            {"key":"shooting_star","label_ja":"流れ星","label_en":"Shooting Star"},{"key":"meteor_shower","label_ja":"流星群","label_en":"Meteor Shower"},{"key":"milky_way","label_ja":"天の川","label_en":"Milky Way"},
        ]},
        {"title_ja":"水・花・装飾","title_en":"Water, flowers, and decorative effects","description_ja":"追加オブジェクト系のプリセットです。必要に応じて3Dプレビューで位置を調整してください。","description_en":"Decorative object presets. Adjust their position in the 3D preview when needed.","columns":4,"items":[
            {"key":"water_drop","label_ja":"水滴","label_en":"Water Drop"},{"key":"water_spray","label_ja":"水しぶき","label_en":"Water Spray"},{"key":"balloon","label_ja":"バルーン","label_en":"Balloon"},{"key":"flame","label_ja":"炎","label_en":"Flame"},
            {"key":"bubble","label_ja":"泡","label_en":"Bubble"},{"key":"rose_petals","label_ja":"バラの花びら","label_en":"Rose Petals"},{"key":"rose_flowers","label_ja":"バラの花","label_en":"Rose Flowers"},{"key":"blooming_roses","label_ja":"咲くバラ","label_en":"Blooming Roses"},{"key":"sakura_petals","label_ja":"桜の花びら","label_en":"Sakura Petals"},
        ]},
        {"title_ja":"表示トグル","title_en":"Display toggles","description_ja":"位置変更なしでON/OFF中心に扱います。プリセットからONにした後もプレビュー側でOFFにできます。","description_en":"Toggle-style effects without position editing. Effects enabled from presets can still be turned off from the preview.","columns":4,"items":[
            {"key":"glow","label_ja":"グロー","label_en":"Glow"},{"key":"ripple","label_ja":"リップル","label_en":"Ripple"},{"key":"particles","label_ja":"パーティクル","label_en":"Particles"},{"key":"noise","label_ja":"ノイズ","label_en":"Noise"},
            {"key":"snow_accumulation","label_ja":"積雪","label_en":"Snow Accumulation"},{"key":"water_fish","label_ja":"水中の魚","label_en":"Water Fish"},{"key":"water_morning_fog","label_ja":"水辺の朝霧","label_en":"Water Morning Fog"},
        ]},
    ]

    def __init__(self, preview_window, parent=None):
        super().__init__(parent or preview_window)
        self.preview_window = preview_window
        self.setWindowTitle(lds_ui_text("エフェクトプリセット", "Effect Presets"))
        try:
            self.setMinimumWidth(560); self.setMinimumHeight(420)
        except Exception:
            pass
        self._apply_theme(); self._build_ui()
    def _apply_theme(self):
        try:
            theme = "material"
            try:
                if self.preview_window is not None and hasattr(self.preview_window, "_resolve_preset_dialog_theme"):
                    theme = self.preview_window._resolve_preset_dialog_theme()
            except Exception:
                theme = "material"
            try:
                self.setWindowOpacity(get_studio_window_opacity(theme))
            except Exception:
                try: self.setWindowOpacity(0.94)
                except Exception: pass
            try: self.setStyleSheet(build_beginner_photoshop_settings_qss(theme))
            except Exception: pass
        except Exception:
            pass
    def _preset_item_is_heavy(self, item):
        try:
            return bool(dict(item or {}).get("heavy", False)) or str(dict(item or {}).get("key", "")) in self.HEAVY_GLOBAL_PRESETS
        except Exception:
            return False

    def _preset_tooltip(self, item):
        try:
            key = str(dict(item or {}).get("key", ""))
            base = lds_ui_text("3Dプレビューに未反映変更として追加します。Apply / 保存で確定します。", "Add to the 3D preview as a pending change. Use Apply / Save to persist it.")
            if self._preset_item_is_heavy(item):
                return base + "\n" + lds_ui_text("⚠ 重め注意: リアルタイムの太陽・空・雲・反射を含むため、環境によって重くなる可能性があります。", "⚠ Heavy caution: realtime sun, sky, clouds, or reflections may be demanding on some systems.")
            if key == "pamukkale_terrace_lake":
                return base + "\n" + lds_ui_text("軽め寄り: 固定壁紙に近い全体エフェクトとして追加します。", "Lighter preset: adds a mostly static scenic full-screen effect.")
            return base
        except Exception:
            return lds_ui_text("3Dプレビューに未反映変更として追加します。", "Add to the 3D preview as a pending change.")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        try:
            layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(10)
        except Exception: pass
        title = QLabel(lds_ui_text("エフェクトプリセット", "Effect Presets"))
        try: title.setObjectName("BeginnerTitle")
        except Exception: pass
        layout.addWidget(title)
        guide = QLabel(lds_ui_text("プリセットを選ぶと、3Dプレビューに未反映変更として追加されます。確定するには Apply / 保存 を押してください。\nv2K: パムッカレを追加し、全体エフェクトを軽め/重め注意で分類しました。", "Selecting a preset adds it as a pending 3D preview change. Use Apply / Save to persist it.\nv2K: Pamukkale is added, and global effects are grouped into lighter and heavy-caution presets."))
        try: guide.setObjectName("BeginnerGuide"); guide.setWordWrap(True)
        except Exception: pass
        layout.addWidget(guide)
        try:
            scroll = QScrollArea(self); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            body = QWidget(scroll); body_layout = QVBoxLayout(body); body_layout.setContentsMargins(2, 2, 2, 2); body_layout.setSpacing(10)
            scroll.setWidget(body); layout.addWidget(scroll, 1)
        except Exception:
            body = QWidget(self); body_layout = QVBoxLayout(body); layout.addWidget(body)
        for group in self.PRESET_GROUPS:
            box = QGroupBox(lds_ui_text(group.get("title_ja", ""), group.get("title_en", "")))
            box_layout = QVBoxLayout(box)
            desc = QLabel(lds_ui_text(group.get("description_ja", ""), group.get("description_en", "")))
            try: desc.setWordWrap(True)
            except Exception: pass
            box_layout.addWidget(desc)
            row = None
            try: columns = max(1, min(6, int(group.get("columns", 3))))
            except Exception: columns = 3
            for index, item in enumerate(list(group.get("items", []) or [])):
                if row is None or index % columns == 0:
                    row = QHBoxLayout()
                    try: row.setSpacing(8)
                    except Exception: pass
                    box_layout.addLayout(row)
                key = str(item.get("key", ""))
                label = lds_ui_text(item.get("label_ja", key), item.get("label_en", key))
                if self._preset_item_is_heavy(item): label = "⚠ " + label
                button = QPushButton(label); button.setToolTip(self._preset_tooltip(item))
                try:
                    if self._preset_item_is_heavy(item): button.setProperty("heavyPreset", True)
                except Exception: pass
                button.clicked.connect(lambda _checked=False, preset_key=key: self._choose_preset(preset_key))
                row.addWidget(button)
            try:
                if row is not None: row.addStretch(1)
            except Exception: pass
            body_layout.addWidget(box)
        try: body_layout.addStretch(1)
        except Exception: pass
        bottom = QHBoxLayout(); bottom.addStretch(1)
        close_btn = QPushButton(lds_ui_text("閉じる", "Close")); close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn); layout.addLayout(bottom)

    def _choose_preset(self, preset_key):
        try:
            preset_key = str(preset_key or "")
            if preset_key in self.HEAVY_GLOBAL_PRESETS:
                try: self.setWindowTitle(lds_ui_text("エフェクトプリセット - 重め注意", "Effect Presets - Heavy Caution"))
                except Exception: pass
            if self.preview_window is not None and hasattr(self.preview_window, "apply_effect_preset_to_preview"):
                ok = bool(self.preview_window.apply_effect_preset_to_preview(preset_key))
                if ok:
                    if preset_key in self.HEAVY_GLOBAL_PRESETS:
                        self.setWindowTitle(lds_ui_text("エフェクトプリセット - 追加済み（重め注意）", "Effect Presets - Added (Heavy Caution)"))
                    else:
                        self.setWindowTitle(lds_ui_text("エフェクトプリセット - 追加済み", "Effect Presets - Added"))
                    return
        except Exception as exc:
            try: QMessageBox.warning(self, lds_tr("プリセット"), lds_tr(f"プリセットを追加できませんでした:\n{exc}"))
            except Exception: pass



class LDSPreview3DWindow(QMainWindow):
    def set_detail_studio_factory(self, factory):
        """Set the main-file LiteDeskStudio factory without importing the main module.

        Phase 23R4B keeps the Preview3D window extracted while avoiding runtime
        lookup ambiguity when the application is launched as __main__.
        """
        try:
            self._detail_studio_factory = factory
        except Exception:
            pass

    def _canvas_owner(self):
        parent = getattr(self, "_canvas_owner_ref", None)
        if parent is None:
            parent = self.parent()
        try:
            if parent is not None and hasattr(parent, "widgets") and hasattr(parent, "save_config"):
                return parent
            if parent is not None and hasattr(parent, "canvas"):
                return parent.canvas
        except Exception:
            pass
        return getattr(self, "canvas", None)

    def _on_detail_studio_destroyed(self):
        try:
            self._detail_studio = None
        except Exception:
            pass

    def _ensure_detail_studio(self):
        try:
            controller = getattr(self, "_detail_studio", None)
            if controller is not None:
                try:
                    controller.isVisible()
                    return controller
                except RuntimeError:
                    self._detail_studio = None
            canvas = self._canvas_owner()
            if canvas is None:
                return None
            controller = _lds_create_detail_studio(canvas, self)
            controller.preview_3d_test_window = self
            try:
                controller.destroyed.connect(self._on_detail_studio_destroyed)
            except Exception:
                pass
            self._detail_studio = controller
            return controller
        except Exception as exc:
            try:
                detail_error_prefix = lds_ui_text("詳細設定を開けませんでした:", "Could not open details:")
                QMessageBox.warning(self, lds_ui_text("詳細設定", "Details"), f"{detail_error_prefix}\n{exc}")
            except Exception:
                pass
            return None

    def _controller(self):
        return self._ensure_detail_studio()

    def open_detail_settings_window(self):
        controller = self._ensure_detail_studio()
        controller.show()
        try:
            controller.raise_()
            controller.activateWindow()
        except Exception:
            pass
        if controller is not None:
            try:
                controller.refresh_layer_list()
                controller.load_selected_to_editor()
                controller.preview_3d_test_window = self
            except Exception:
                pass

    def select_widget_from_preview(self, index):
        controller = self._controller()
        if controller is not None and hasattr(controller, "select_3d_preview_widget_index"):
            controller.select_3d_preview_widget_index(index)
            try:
                # Force a fresh state after direct 3D selection.  This is especially
                # important when switching from a normal widget with pending edits to
                # an Effects Overlay widget, because timer sync is intentionally
                # suppressed while pending preview edits exist.
                self.set_preview_state(controller.build_3d_preview_state())
                try:
                    self.preview._preview_selected_widget_index = int(index)
                except Exception:
                    pass
            except Exception:
                pass


    def set_preview_state(self, state):
        try:
            self.preview.set_preview_state(state)
        except Exception:
            pass
        try:
            self.update_control_visibility()
        except Exception:
            pass
        try:
            self.update_integrated_selection_bar()
        except Exception:
            pass

    def _current_selected_preview_type(self):
        try:
            if bool(getattr(self.preview, "_cloud_selected", False)) or bool(getattr(self.preview, "_fireball_selected", False)):
                return "effects_overlay"
            if str(getattr(self.preview, "_template_effect_selected_key", "") or ""):
                return "effects_overlay"
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            return str(selected.get("type", ""))
        except Exception:
            return ""

    def update_control_visibility(self):
        try:
            selected_type = self._current_selected_preview_type()
            has_selection = bool(selected_type)
            is_effect = selected_type == "effects_overlay"
            is_widget = has_selection and not is_effect
            dev_mode = self.is_developer_mode()
            if hasattr(self, "mode_label"):
                self.mode_label.setVisible(bool(dev_mode))
                if is_effect:
                    self.mode_label.setText(lds_tr("編集モード: Effects Overlay / Sun・Moon・Puddle"))
                elif is_widget:
                    self.mode_label.setText(lds_tr("編集モード: 通常ウィジェット / 移動・サイズ・回転"))
                else:
                    self.mode_label.setText(lds_tr("編集モード: 未選択 / Layers または3D上の矩形を選択"))
            if hasattr(self, "preview_status_label"):
                self.preview_status_label.setVisible(bool(dev_mode))
            if hasattr(self, "preview_background_combo"):
                self.preview_background_combo.setVisible(bool(dev_mode))
                self.preview_background_combo.setEnabled(bool(dev_mode))
            if hasattr(self, "effect_controls_group"):
                self.effect_controls_group.setVisible(bool(is_effect))
            if hasattr(self, "widget_controls_group"):
                self.widget_controls_group.setVisible(bool(is_widget))
            if hasattr(self, "btn_reset_widget_rotation_preview"):
                self.btn_reset_widget_rotation_preview.setEnabled(bool(is_widget))
            if hasattr(self, "pending_summary_label"):
                self.pending_summary_label.setVisible(bool(dev_mode))
                try:
                    changes = self.pending_preview_changes()
                    if not changes:
                        self.pending_summary_label.setText(lds_tr("未反映: なし"))
                    else:
                        names = []
                        if "widget" in changes:
                            names.append("Widget")
                        if "sun" in changes:
                            names.append("Sun")
                        if "moon" in changes:
                            names.append("Moon")
                        if "ice" in changes:
                            names.append("Ice")
                        if "puddles" in changes:
                            names.append("Puddles")
                        elif "puddle" in changes:
                            names.append("Puddle")
                        try:
                            for template_key in sorted(dict(changes or {}).keys()):
                                spec = self.preview._lds_template_effect_spec(template_key) if hasattr(self.preview, "_lds_template_effect_spec") else None
                                if spec:
                                    template_label = str(dict(spec or {}).get("display_name", template_key))
                                    if template_label not in names:
                                        names.append(template_label)
                        except Exception:
                            pass
                        self.pending_summary_label.setText(lds_tr("未反映: ") + ", ".join(names))
                except Exception:
                    self.pending_summary_label.setText(lds_tr("未反映: 不明"))
            if hasattr(self, "detail_controls_group"):
                self.detail_controls_group.setVisible(bool(getattr(self, "_integrated_details_visible", False)))
            try:
                self.update_integrated_selection_bar()
            except Exception:
                pass
        except Exception:
            pass

    def set_desktop_locked(self, locked):
        locked = bool(locked)
        try:
            self.preview.set_desktop_locked(locked)
        except Exception:
            pass
        try:
            if hasattr(self, "desktop_lock_check"):
                self.desktop_lock_check.setText(lds_ui_text("固定: ON", "Lock: ON") if locked else lds_ui_text("固定: OFF", "Lock: OFF"))
                if self.desktop_lock_check.isChecked() != locked:
                    self.desktop_lock_check.setChecked(locked)
        except Exception:
            pass
        try:
            self.update_control_visibility()
        except Exception:
            pass

    def is_developer_mode(self):
        try:
            return bool(self.developer_mode_check.isChecked())
        except Exception:
            return False


    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
            else:
                self.show()
                self.update()

    def on_preview_background_theme_changed(self, *args):
        try:
            if not self.is_developer_mode():
                return
            theme = self.preview_background_combo.currentData()
            self.preview.set_preview_background_theme(theme)
        except Exception:
            pass

    def set_developer_mode(self, enabled):
        try:
            enabled = bool(enabled)
            self.preview.set_developer_mode(enabled)
            if hasattr(self, "preview_background_combo"):
                self.preview_background_combo.setVisible(enabled)
                self.preview_background_combo.setEnabled(enabled)
                if enabled:
                    self.preview.set_preview_background_theme(self.preview_background_combo.currentData())
        except Exception:
            pass
        try:
            self.update_control_visibility()
        except Exception:
            pass

    def is_snap_enabled(self):
        try:
            return bool(self.snap_edit_check.isChecked())
        except Exception:
            return False

    def set_snap_enabled(self, enabled):
        try:
            enabled = bool(enabled)
            self.preview.set_snap_enabled(enabled)
        except Exception:
            enabled = False
        try:
            if hasattr(self, "snap_edit_check"):
                self.snap_edit_check.setText(lds_ui_text("スナップ: ON", "Snap: ON") if enabled else lds_ui_text("スナップ: OFF", "Snap: OFF"))
        except Exception:
            pass
        try:
            self.update_control_visibility()
        except Exception:
            pass

    def current_preview_sun_unit(self):
        try:
            return self.preview.current_preview_sun_unit()
        except Exception:
            return 0.22, 0.22, False

    def clear_pending_sun_unit(self):
        try:
            self.preview.clear_pending_sun_unit()
        except Exception:
            pass

    def current_preview_moon_unit(self):
        try:
            return self.preview.current_preview_moon_unit()
        except Exception:
            return 0.78, 0.18, False

    def clear_pending_moon_unit(self):
        try:
            self.preview.clear_pending_moon_unit()
        except Exception:
            pass

    def apply_preview_moon_to_parent(self):
        controller = self._controller()
        if controller is None or not hasattr(controller, "apply_3d_preview_moon_to_selected_effects"):
            return
        try:
            self._ensure_effect_overlay_selected_for_preview_changes(controller, {"moon": {}})
            controller.apply_3d_preview_moon_to_selected_effects(self.current_preview_moon_unit())
            self.set_preview_state(controller.build_3d_preview_state())
        except Exception as exc:
            QMessageBox.warning(self, lds_tr("3Dプレビュー"), lds_tr(f"Moon位置を反映できませんでした:\n{exc}"))


    def current_preview_puddle_state(self):
        try:
            return self.preview.current_preview_puddle_state()
        except Exception:
            return {"x": 0.50, "y": 0.84, "width": 0.20, "height": 0.08, "visible": False}

    def clear_pending_puddle_state(self):
        try:
            self.preview.clear_pending_puddle_state()
        except Exception:
            pass

    def current_preview_ice_state(self):
        try:
            return self.preview.current_preview_ice_state()
        except Exception:
            return {"x": 0.50, "y": 0.58, "width": 1.0, "depth": 0.42, "visible": False}

    def clear_pending_ice_state(self):
        try:
            self.preview.clear_pending_ice_state()
        except Exception:
            pass

    def current_preview_water_surface_state(self):
        try:
            return self.preview.current_preview_water_surface_state()
        except Exception:
            return {"y": 0.58, "depth": 0.42, "visible": False}

    def clear_pending_water_surface_state(self):
        try:
            self.preview.clear_pending_water_surface_state()
        except Exception:
            pass

    def pending_preview_changes(self):
        try:
            return self.preview.pending_preview_changes()
        except Exception:
            return {}

    def clear_all_pending_preview_changes(self):
        try:
            self.preview.clear_all_pending_preview_changes()
        except Exception:
            pass

    def _selected_normal_widget_type_for_discard(self):
        try:
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            widget_type = str(selected.get("type", ""))
            if widget_type:
                return widget_type
        except Exception:
            pass
        try:
            item = self.preview._current_widget_rect_state()
            return str(dict(item or {}).get("type", ""))
        except Exception:
            return ""

    def _discard_normal_widget_live_preview_via_canvas_undo(self):
        """Phase 24A-5g: preview-side fallback when no detail-controller discard entry is reached."""
        try:
            widget_type = self._selected_normal_widget_type_for_discard()
            if widget_type not in ("system", "network"):
                return False
            canvas = self._canvas_owner()
            if canvas is None or not hasattr(canvas, "undo_last_change"):
                return False
            stack = list(getattr(canvas, "_undo_stack", []) or [])
            if not stack:
                return False
            latest = dict(stack[-1] or {})
            label = str(latest.get("label", ""))
            if label not in ("Normal widget 3D live preview", "Clock 3D live preview") and not bool(latest.get("widgets", [])):
                return False
            return bool(canvas.undo_last_change())
        except Exception:
            return False

    def discard_all_pending_preview_changes(self):
        try:
            controller = self._controller()
            restored = False
            # Phase 24A-5g: the actual Discard button lives in preview3d.py.
            # Normal-widget restore must be invoked from here before preview pending
            # state is cleared; otherwise the LiteDesktopStudio-side method may never
            # run, which matches the System/Network color symptom.
            if controller is not None and hasattr(controller, "discard_3d_preview_normal_widget_live_changes"):
                try:
                    restored = bool(controller.discard_3d_preview_normal_widget_live_changes(show_message=False))
                except Exception:
                    restored = False
            elif controller is not None and hasattr(controller, "discard_3d_preview_clock_live_changes"):
                try:
                    restored = bool(controller.discard_3d_preview_clock_live_changes(show_message=False))
                except Exception:
                    restored = False
            if not restored:
                try:
                    restored = bool(self._discard_normal_widget_live_preview_via_canvas_undo())
                except Exception:
                    restored = False
            self.preview.clear_all_pending_preview_changes()
            if controller is not None and hasattr(controller, "build_3d_preview_state"):
                self.set_preview_state(controller.build_3d_preview_state())
            else:
                try:
                    canvas = self._canvas_owner()
                    if canvas is not None and hasattr(canvas, "parent"):
                        parent = canvas.parent()
                        if parent is not None and hasattr(parent, "build_3d_preview_state"):
                            self.set_preview_state(parent.build_3d_preview_state())
                except Exception:
                    pass
            self.update_control_visibility()
        except Exception:
            pass


    def reset_selected_widget_rotation_preview(self):
        try:
            ok = self.preview.reset_selected_widget_rotation_preview()
            self.update_control_visibility()
            if not ok:
                QMessageBox.information(self, lds_tr("3Dプレビュー"), lds_tr("通常ウィジェットを選択してから回転をリセットしてください。"))
        except Exception as exc:
            QMessageBox.warning(self, lds_tr("3Dプレビュー"), lds_tr(f"回転リセットに失敗しました:\n{exc}"))

    def _ensure_effect_overlay_selected_for_preview_changes(self, controller, changes):
        """Keep main-side selection aligned before applying effect preview changes.

        Phase23E v2E: template effect changes also target the Effects Overlay.
        When template markers are shown from the fallback Effects Overlay state,
        the current 3D selected item may still be None or a normal widget.  In
        that case, select the Effects Overlay widget before calling the main-side
        apply function so apply/save can persist template x/y changes.
        """
        try:
            changes = dict(changes or {})
            builtin_effect_keys = ("sun", "moon", "water_surface", "ice", "puddle", "puddles", "bamboo_grove", "cloud", "fireball")
            has_builtin_effect_change = any(k in changes for k in builtin_effect_keys)
            has_template_effect_change = False
            try:
                for key in dict(changes or {}).keys():
                    if hasattr(self.preview, "_lds_template_effect_spec") and self.preview._lds_template_effect_spec(key):
                        has_template_effect_change = True
                        break
            except Exception:
                has_template_effect_change = False
            if not has_builtin_effect_change and not has_template_effect_change:
                return True

            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            selected_index = -1
            if str(selected.get("type", "")) == "effects_overlay":
                try:
                    selected_index = int(selected.get("index", -1))
                except Exception:
                    selected_index = -1

            if selected_index < 0:
                # Fallback: find the first Effects Overlay from preview state.
                try:
                    for item in list(state.get("widgets", []) or []):
                        item = dict(item or {})
                        if str(item.get("type", "")) == "effects_overlay":
                            selected_index = int(item.get("index", -1))
                            selected = item
                            break
                except Exception:
                    selected_index = -1

            if selected_index < 0:
                # Last fallback: find the first Effects Overlay from canvas widgets.
                try:
                    canvas = self._canvas_owner()
                    widgets = list(getattr(canvas, "widgets", []) or []) if canvas is not None else []
                    for i, widget in enumerate(widgets):
                        cfg = getattr(widget, "cfg", None)
                        if cfg is not None and str(getattr(cfg, "type", "")) == "effects_overlay":
                            selected_index = i
                            break
                except Exception:
                    selected_index = -1

            if selected_index < 0:
                return False

            try:
                if controller is not None and hasattr(controller, "select_3d_preview_widget_index"):
                    controller.select_3d_preview_widget_index(selected_index)
                    return True
            except Exception:
                pass
            try:
                canvas = self._canvas_owner()
                widgets = list(getattr(canvas, "widgets", []) or []) if canvas is not None else []
                if 0 <= selected_index < len(widgets):
                    canvas.selected = widgets[selected_index]
                    return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def _restore_template_effect_after_preview_apply(self, changes, previous_state=None):
        """Restore Phase23E template effect selection/state after Apply/Save rebuild."""
        try:
            changes = dict(changes or {})
            template_key = ""
            template_spec = None
            try:
                for candidate_key in sorted(changes.keys()):
                    if hasattr(self.preview, "_lds_template_effect_spec"):
                        candidate_spec = self.preview._lds_template_effect_spec(candidate_key)
                        if candidate_spec:
                            template_key = str(candidate_key)
                            template_spec = dict(candidate_spec or {})
                            break
            except Exception:
                template_key = ""
                template_spec = None
            if not template_key or not template_spec:
                return False

            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            previous_state = dict(previous_state or {})
            previous_selected = dict(previous_state.get("selected", {}) or {})
            overlay_selected = None
            if str(previous_selected.get("type", "")) == "effects_overlay":
                overlay_selected = dict(previous_selected)
            if overlay_selected is None:
                for source_state in (state, previous_state):
                    try:
                        for item in list(dict(source_state or {}).get("widgets", []) or []):
                            item = dict(item or {})
                            if str(item.get("type", "")) == "effects_overlay":
                                overlay_selected = item
                                break
                    except Exception:
                        pass
                    if overlay_selected is not None:
                        break
            if overlay_selected is None:
                current_selected = dict(state.get("selected", {}) or {})
                overlay_selected = dict(current_selected or {})
                overlay_selected["type"] = "effects_overlay"
                overlay_selected["title"] = overlay_selected.get("title") or "Effects Overlay"
                try:
                    overlay_selected.setdefault("index", int(overlay_selected.get("index", 0)))
                except Exception:
                    overlay_selected["index"] = 0
            try:
                state["selected"] = self.preview._effect_overlay_full_desktop_rect_item(overlay_selected)
            except Exception:
                state["selected"] = dict(overlay_selected)

            effect = dict(state.get("effect", {}) or {})
            item = dict(changes.get(template_key) or {})
            effect[f"{template_key}_visible"] = bool(item.get("visible", True))
            try:
                enabled_key = str(template_spec.get("enabled_key") or f"{template_key}_enabled")
                effect[enabled_key] = bool(item.get("visible", True))
            except Exception:
                pass
            if str(template_spec.get("mode", "")) == "anchor_point":
                x_key = str(template_spec.get("x_key") or f"{template_key}_x")
                y_key = str(template_spec.get("y_key") or f"{template_key}_y")
                try:
                    effect[x_key] = max(0.0, min(1.0, float(item.get("x", effect.get(x_key, template_spec.get("default_x", 0.5))))))
                except Exception:
                    effect[x_key] = float(template_spec.get("default_x", 0.5))
                try:
                    effect[y_key] = max(0.0, min(1.0, float(item.get("y", effect.get(y_key, template_spec.get("default_y", 0.5))))))
                except Exception:
                    effect[y_key] = float(template_spec.get("default_y", 0.5))
            state["effect"] = effect
            self.preview._preview_state = state
            self.preview._template_effect_selected_key = template_key
            self.preview._pending_template_effect_states = {}
            self.preview._template_effect_drag_start_pos = None
            self.preview._template_effect_drag_start_state = None
            self.preview._preview_selected_widget_index = None
            try:
                self.preview._water_surface_selected = False
                self.preview._bamboo_grove_selected = False
                self.preview._cloud_selected = False
                self.preview._fireball_selected = False
                self.preview._ice_selected = False
            except Exception:
                pass
            try:
                self.preview._drag_notice = f"{template_spec.get('display_name', template_key)} applied / effect mode restored"
                self.preview.update()
            except Exception:
                pass
            try:
                self.update_integrated_selection_bar()
                self.update_control_visibility()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _restore_cloud_layer_after_preview_apply(self, changes, previous_state=None):
        try:
            changes = dict(changes or {})
            if "cloud" not in changes:
                return False
            cloud = dict(changes.get("cloud") or {})
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            previous_state = dict(previous_state or {})
            previous_selected = dict(previous_state.get("selected", {}) or {})
            if str(previous_selected.get("type", "")) == "effects_overlay":
                state["selected"] = self.preview._effect_overlay_full_desktop_rect_item(previous_selected)
            else:
                current_selected = dict(state.get("selected", {}) or {})
                if str(current_selected.get("type", "")) != "effects_overlay":
                    selected_effect = dict(previous_state.get("effect", {}) or {})
                    if selected_effect or bool(cloud):
                        fallback_selected = dict(current_selected or {})
                        fallback_selected["type"] = "effects_overlay"
                        fallback_selected["title"] = fallback_selected.get("title") or "Effects Overlay"
                        state["selected"] = self.preview._effect_overlay_full_desktop_rect_item(fallback_selected)
            effect = dict(state.get("effect", {}) or {})
            effect["cloud_visible"] = True
            effect["cloud_size"] = max(18.0, min(180.0, float(cloud.get("size", effect.get("cloud_size", 92.0)))))
            effect["cloud_altitude"] = max(0.0, min(1.0, float(cloud.get("altitude", effect.get("cloud_altitude", 0.22)))))
            effect["cloud_depth"] = max(0.04, min(1.0, float(cloud.get("depth", effect.get("cloud_depth", 0.42)))))
            state["effect"] = effect
            self.preview._preview_state = state
            self.preview._pending_cloud_layer_state = None
            self.preview._cloud_selected = True
            self.preview._preview_selected_widget_index = None
            try:
                self.preview.update()
            except Exception:
                pass
            try:
                self.update_integrated_selection_bar()
                self.update_control_visibility()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _restore_fireball_layer_after_preview_apply(self, changes, previous_state=None):
        """Restore Fireball preview selection/state after Apply rebuild.

        Phase23D3A: keep Fireball aligned with Cloud. The preview state rebuild
        can replace the selected item with a normal widget; restore the pseudo
        full-desktop Effects Overlay selection before reselecting Fireball.
        """
        try:
            changes = dict(changes or {})
            if "fireball" not in changes:
                return False
            fireball = dict(changes.get("fireball") or {})
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            previous_state = dict(previous_state or {})
            previous_selected = dict(previous_state.get("selected", {}) or {})
            if str(previous_selected.get("type", "")) == "effects_overlay":
                state["selected"] = self.preview._effect_overlay_full_desktop_rect_item(previous_selected)
            else:
                current_selected = dict(state.get("selected", {}) or {})
                if str(current_selected.get("type", "")) != "effects_overlay":
                    selected_effect = dict(previous_state.get("effect", {}) or {})
                    if selected_effect or bool(fireball):
                        fallback_selected = dict(current_selected or {})
                        fallback_selected["type"] = "effects_overlay"
                        fallback_selected["title"] = fallback_selected.get("title") or "Effects Overlay"
                        state["selected"] = self.preview._effect_overlay_full_desktop_rect_item(fallback_selected)
            effect = dict(state.get("effect", {}) or {})
            effect["fireball_visible"] = True
            effect["fireball_x"] = max(0.0, min(1.0, float(fireball.get("x", effect.get("fireball_x", 0.50)))))
            effect["fireball_y"] = max(0.0, min(1.0, float(fireball.get("y", effect.get("fireball_y", 0.38)))))
            state["effect"] = effect
            self.preview._preview_state = state
            self.preview._pending_fireball_layer_state = None
            self.preview._fireball_selected = True
            self.preview._preview_selected_widget_index = None
            try:
                self.preview.update()
            except Exception:
                pass
            try:
                self.update_integrated_selection_bar()
                self.update_control_visibility()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def apply_all_pending_preview_changes_to_parent(self):
        controller = self._controller()
        if controller is None or not hasattr(controller, "apply_3d_preview_pending_changes_to_selected_effects"):
            return False
        try:
            changes = dict(self.pending_preview_changes() or {})
            self._ensure_effect_overlay_selected_for_preview_changes(controller, changes)
            previous_state = dict(getattr(self.preview, "_preview_state", {}) or {})
            result = bool(controller.apply_3d_preview_pending_changes_to_selected_effects(changes))
            self.update_control_visibility()
            try:
                self.set_preview_state(controller.build_3d_preview_state())
                self._restore_cloud_layer_after_preview_apply(changes, previous_state)
                self._restore_fireball_layer_after_preview_apply(changes, previous_state)
                self._restore_template_effect_after_preview_apply(changes, previous_state)
            except Exception:
                pass
            return result
        except Exception as exc:
            QMessageBox.warning(self, lds_tr("3Dプレビュー"), lds_tr(f"3Dプレビュー変更をまとめて反映できませんでした:\n{exc}"))
            return False


    def apply_preview_puddle_to_parent(self):
        controller = self._controller()
        if controller is None or not hasattr(controller, "apply_3d_preview_puddle_to_selected_effects"):
            return
        try:
            self._ensure_effect_overlay_selected_for_preview_changes(controller, {"puddle": {}})
            controller.apply_3d_preview_puddle_to_selected_effects(self.current_preview_puddle_state())
            self.set_preview_state(controller.build_3d_preview_state())
        except Exception as exc:
            QMessageBox.warning(self, lds_tr("3Dプレビュー"), lds_tr(f"Puddle位置を反映できませんでした:\n{exc}"))


    def apply_preview_sun_to_parent(self):
        controller = self._controller()
        if controller is None or not hasattr(controller, "apply_3d_preview_sun_to_selected_effects"):
            return
        try:
            self._ensure_effect_overlay_selected_for_preview_changes(controller, {"sun": {}})
            controller.apply_3d_preview_sun_to_selected_effects(self.current_preview_sun_unit())
            self.set_preview_state(controller.build_3d_preview_state())
        except Exception as exc:
            QMessageBox.warning(self, lds_tr("3Dプレビュー"), lds_tr(f"Sun位置を反映できませんでした:\n{exc}"))


    def _apply_nvd_control_panel_visual_style(self):
        """Phase 24A-9: lightweight NVD Control Panel inspired styling.

        This is intentionally cosmetic and local to the 3D preview window.  It does
        not change preview logic, pending data, or apply/discard behavior.
        """
        try:
            self.setStyleSheet(self.styleSheet() + """
                QMainWindow {
                    background: #0F1216;
                    color: #E7F2E7;
                }
                QGroupBox#LDSNvdStatusPanel, QGroupBox#LDSNvdControlsPanel {
                    border: 1px solid #2F5F24;
                    border-radius: 8px;
                    margin-top: 8px;
                    background-color: #151A20;
                    color: #DFF5DD;
                    font-weight: 700;
                }
                QGroupBox#LDSNvdStatusPanel::title, QGroupBox#LDSNvdControlsPanel::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #76B900;
                    font-weight: 900;
                }
                QLabel#LDSNvdMetricName {
                    color: #9EB39C;
                    font-size: 11px;
                    font-weight: 700;
                }
                QLabel#LDSNvdMetricValue {
                    color: #F2FFF1;
                    font-size: 12px;
                    font-weight: 800;
                    padding: 2px 6px;
                    border: 1px solid #26372A;
                    border-radius: 4px;
                    background: #0D1115;
                }
                QLabel#LDSNvdAccentValue {
                    color: #76B900;
                    font-size: 12px;
                    font-weight: 900;
                    padding: 2px 6px;
                    border: 1px solid #3E6F2B;
                    border-radius: 4px;
                    background: #101810;
                }
                QPushButton#LDSNvdApplyButton {
                    background-color: #76B900;
                    color: #081008;
                    font-weight: 900;
                    border-radius: 5px;
                    padding: 5px 14px;
                }
                QPushButton#LDSNvdDiscardButton {
                    background-color: #232A30;
                    color: #EAF5EA;
                    font-weight: 800;
                    border: 1px solid #59645D;
                    border-radius: 5px;
                    padding: 5px 12px;
                }
            """)
        except Exception:
            pass

    def _make_nvd_metric_column(self, title, value_text="--", accent=False):
        try:
            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(3)
            name = QLabel(str(title))
            name.setObjectName("LDSNvdMetricName")
            value = QLabel(str(value_text))
            value.setObjectName("LDSNvdAccentValue" if accent else "LDSNvdMetricValue")
            value.setMinimumWidth(92)
            col.addWidget(name)
            col.addWidget(value)
            return col, value
        except Exception:
            col = QVBoxLayout()
            value = QLabel(str(value_text))
            col.addWidget(value)
            return col, value

    def _create_nvd_control_panel_status_bar(self):
        try:
            panel = QGroupBox(lds_ui_text("3D コントロールパネル", "3D Control Panel"))
            panel.setObjectName("LDSNvdStatusPanel")
            row = QHBoxLayout(panel)
            row.setContentsMargins(10, 8, 10, 8)
            row.setSpacing(10)
            col, self.nvd_mode_value = self._make_nvd_metric_column(lds_ui_text("モード", "Mode"), lds_ui_text("直接編集", "Direct Edit"), True)
            row.addLayout(col)
            col, self.nvd_target_value = self._make_nvd_metric_column(lds_ui_text("対象", "Target"), lds_ui_text("未選択", "None"))
            row.addLayout(col)
            col, self.nvd_pending_value = self._make_nvd_metric_column(lds_ui_text("未反映", "Pending"), "0")
            row.addLayout(col)
            col, self.nvd_snap_value = self._make_nvd_metric_column(lds_ui_text("スナップ", "Snap"), "OFF")
            row.addLayout(col)
            col, self.nvd_lock_value = self._make_nvd_metric_column(lds_ui_text("視点", "View"), lds_ui_text("固定", "Locked"))
            row.addLayout(col)
            row.addStretch(1)
            return panel
        except Exception:
            return None

    def _refresh_live_status_panels(self):
        """Phase 24A-9b: refresh selection/pending UI independently of Apply.

        Some preview interactions update selection or pending state inside
        LDSPreview3DWidget without always notifying the window.  The status panels
        are display-only, so a small timer keeps them in sync without touching the
        underlying Apply/Discard logic.
        """
        if bool(getattr(self, "_live_status_refreshing", False)):
            return
        self._live_status_refreshing = True
        try:
            try:
                self.update_integrated_selection_bar()
            except Exception:
                pass
            try:
                self._update_nvd_control_panel_status()
            except Exception:
                pass
            try:
                self.update_control_visibility()
            except Exception:
                pass
        finally:
            self._live_status_refreshing = False

    def _start_live_status_refresh_timer(self):
        try:
            timer = getattr(self, "_live_status_refresh_timer", None)
            if timer is not None:
                try:
                    if timer.isActive():
                        return
                except Exception:
                    pass
            timer = QTimer(self)
            timer.setInterval(150)
            timer.timeout.connect(self._refresh_live_status_panels)
            timer.start()
            self._live_status_refresh_timer = timer
        except Exception:
            pass

    def _pending_preview_change_display_count(self, changes=None):
        """Phase 24A-9c: count pending items without alias double-counting.

        pending_preview_changes() intentionally exposes convenience aliases such
        as both "widgets" and "widget", and both "puddles" and "puddle".
        A plain len(changes) therefore reports alias keys instead of real pending
        items.  This helper counts unique pending items/groups for the status bar.
        """
        try:
            data = dict(changes or self.pending_preview_changes() or {})
        except Exception:
            data = {}
        count = 0
        try:
            widgets = data.get("widgets")
            if isinstance(widgets, list):
                seen = set()
                for item in widgets:
                    if not isinstance(item, dict):
                        continue
                    try:
                        idx = int(item.get("index", len(seen)))
                    except Exception:
                        idx = len(seen)
                    seen.add(idx)
                count += len(seen)
            elif isinstance(data.get("widget"), dict):
                count += 1
        except Exception:
            if isinstance(data.get("widget"), dict):
                count += 1
        try:
            puddles = data.get("puddles")
            if isinstance(puddles, list):
                seen = set()
                for item in puddles:
                    if not isinstance(item, dict):
                        continue
                    try:
                        idx = int(item.get("index", len(seen)))
                    except Exception:
                        idx = len(seen)
                    seen.add(idx)
                count += len(seen)
            elif isinstance(data.get("puddle"), dict):
                count += 1
        except Exception:
            if isinstance(data.get("puddle"), dict):
                count += 1
        alias_keys = {"widget", "widgets", "puddle", "puddles"}
        try:
            for key, value in data.items():
                if str(key) in alias_keys:
                    continue
                if value is None:
                    continue
                count += 1
        except Exception:
            pass
        return max(0, int(count))

    def _update_nvd_control_panel_status(self):
        try:
            if not hasattr(self, "nvd_mode_value"):
                return
            try:
                changes = dict(self.pending_preview_changes() or {})
            except Exception:
                changes = {}
            try:
                state = dict(getattr(self.preview, "_preview_state", {}) or {})
                selected = dict(state.get("selected", {}) or {})
            except Exception:
                selected = {}
            selected_type = str(selected.get("type", "") or "")
            selected_title = str(selected.get("title", "") or "")
            if not selected_title:
                selected_title = selected_type or lds_ui_text("未選択", "None")
            try:
                pending_count = self._pending_preview_change_display_count(changes)
            except Exception:
                pending_count = 0
            try:
                lock_text = lds_ui_text("固定", "Locked") if bool(getattr(self.preview, "_desktop_locked", False)) else lds_ui_text("視点操作", "Camera")
            except Exception:
                lock_text = lds_ui_text("固定", "Locked")
            try:
                snap_text = "ON" if bool(getattr(self.preview, "_snap_enabled", False)) else "OFF"
            except Exception:
                snap_text = "OFF"
            mode_text = lds_ui_text("通常", "Widget")
            if selected_type == "effects_overlay":
                mode_text = lds_tr("Effects")
            elif selected_type == "visualizer":
                mode_text = lds_ui_text("Visualizer", "Visualizer")
            elif selected_type == "clock":
                mode_text = lds_ui_text("Clock", "Clock")
            elif not selected_type:
                mode_text = lds_ui_text("待機", "Idle")
            self.nvd_mode_value.setText(str(mode_text))
            self.nvd_target_value.setText(str(selected_title)[:32])
            self.nvd_pending_value.setText(str(pending_count))
            self.nvd_snap_value.setText(str(snap_text))
            self.nvd_lock_value.setText(str(lock_text))
        except Exception:
            pass

    def update_integrated_selection_bar(self):
        try:
            if not hasattr(self, "integrated_selection_label"):
                return
            changes = {}
            try:
                changes = dict(self.pending_preview_changes() or {})
            except Exception:
                changes = {}
            label = lds_ui_text("なし", "None")
            parts = []
            try:
                template_key = str(getattr(self.preview, "_template_effect_selected_key", "") or "")
                if not template_key:
                    try:
                        for _candidate_key in sorted(dict(changes or {}).keys()):
                            if hasattr(self.preview, "_lds_template_effect_spec") and self.preview._lds_template_effect_spec(_candidate_key):
                                template_key = str(_candidate_key)
                                break
                    except Exception:
                        template_key = ""
                if template_key and hasattr(self.preview, "_lds_template_effect_spec") and self.preview._lds_template_effect_spec(template_key):
                    spec = dict(self.preview._lds_template_effect_spec(template_key) or {})
                    state = dict(self.preview._lds_template_effect_state(template_key) or {})
                    label = str(spec.get("display_name", template_key))
                    if str(spec.get("mode", state.get("mode", ""))) == "anchor_point":
                        parts = [
                            f"X {float(state.get('x', spec.get('default_x', 0.5))):.2f}",
                            f"Y {float(state.get('y', spec.get('default_y', 0.5))):.2f}",
                            lds_ui_text("移動のみ", "move only"),
                        ]
                    else:
                        parts = [str(spec.get("mode", state.get("mode", "")) or "display")]
                elif bool(getattr(self.preview, "_cloud_selected", False)) or "cloud" in changes:
                    try:
                        state = dict(self.preview._current_cloud_layer_state() or {})
                    except Exception:
                        state = {"count": 0, "size": 92.0}
                    label = lds_ui_text("雲", "Cloud")
                    parts = [
                        f"数 {int(state.get('count', 0))}",
                        f"サイズ {float(state.get('size', 92.0)):.1f}",
                        f"高度 {float(state.get('altitude', 0.22)):.2f}",
                        f"深さ {float(state.get('depth', 0.42)):.2f}",
                    ]
                elif bool(getattr(self.preview, "_fireball_selected", False)):
                    try:
                        state = dict(self.preview._current_fireball_layer_state() or {})
                    except Exception:
                        state = {"count": 0, "size": 20.0, "speed": 0.34}
                    label = lds_ui_text("火の玉", "Fireball")
                    parts = [
                        f"数 {int(state.get('count', 0))}",
                        f"サイズ {float(state.get('size', 20.0)):.1f}",
                        f"速度 {float(state.get('speed', 0.34)):.2f}",
                        f"X {float(state.get('x', 0.50)):.2f}",
                        f"Y {float(state.get('y', 0.38)):.2f}",
                    ]
                elif bool(getattr(self.preview, "_bamboo_grove_selected", False)) or "bamboo_grove" in changes:
                    state = dict(self.preview._current_bamboo_grove_state() or {})
                    label = lds_ui_text("竹林", "Bamboo Grove")
                    parts = [
                        f"本数 {int(state.get('count', 12))}",
                        f"高さ {float(state.get('height', 0.92)):.2f}",
                    ]
                elif bool(getattr(self.preview, "_water_surface_selected", False)) or "water_surface" in changes:
                    water = dict(self.current_preview_water_surface_state() or {})
                    label = lds_ui_text("水面", "Water Surface")
                    parts = [
                        f"Y {float(water.get('y', 0.58)):.2f}",
                        f"奥行 {float(water.get('depth', 0.42)):.2f}",
                    ]
                elif bool(getattr(self.preview, "_ice_selected", False)) or "ice" in changes:
                    ice = dict(self.current_preview_ice_state() or {})
                    label = lds_ui_text("氷", "Ice")
                    parts = [
                        f"X {float(ice.get('x', 0.50)):.2f}",
                        f"Y {float(ice.get('y', 0.58)):.2f}",
                        f"幅 {float(ice.get('width', 1.0)):.2f}",
                        f"奥行 {float(ice.get('depth', 0.42)):.2f}",
                    ]
                elif "puddle" in changes or "puddles" in changes:
                    puddle = dict(self.current_preview_puddle_state() or {})
                    label = lds_ui_text("水たまり", "Puddle")
                    parts = [
                        f"X {float(puddle.get('x', 0.50)):.2f}",
                        f"Y {float(puddle.get('y', 0.84)):.2f}",
                        f"幅 {float(puddle.get('width', 0.20)):.2f}",
                        f"高さ {float(puddle.get('height', 0.08)):.2f}",
                    ]
                elif "sun" in changes:
                    sx, sy, _visible = self.current_preview_sun_unit()
                    label = lds_ui_text("太陽", "Sun")
                    parts = [f"X {float(sx):.2f}", f"Y {float(sy):.2f}"]
                elif "moon" in changes:
                    mx, my, _visible = self.current_preview_moon_unit()
                    label = lds_ui_text("月", "Moon")
                    parts = [f"X {float(mx):.2f}", f"Y {float(my):.2f}"]
                elif "widget" in changes:
                    widget = dict(changes.get("widget") or {})
                    label = str(widget.get("title") or lds_ui_text("ウィジェット", "Widget"))
                    parts = [
                        f"X {int(widget.get('x', 0))}",
                        f"Y {int(widget.get('y', 0))}",
                        f"W {int(widget.get('w', 0))}",
                        f"H {int(widget.get('h', 0))}",
                    ]
                else:
                    state = dict(getattr(self.preview, "_preview_state", {}) or {})
                    selected = dict(state.get("selected", {}) or {})
                    selected_type = str(selected.get("type", ""))
                    if selected_type == "effects_overlay":
                        label = lds_tr("Effects Overlay")
                        effect = dict(state.get("effect", {}) or {})
                        if effect.get("water_surface_visible"):
                            parts = [f"Water Surface Y {float(effect.get('water_surface_y', 0.58)):.2f}", f"奥行 {float(effect.get('water_surface_depth', 0.42)):.2f}"]
                        elif effect.get("ice_visible"):
                            parts = [f"Ice X {float(effect.get('ice_x', 0.50)):.2f}", f"Y {float(effect.get('ice_y', 0.58)):.2f}"]
                        elif effect.get("puddle_visible"):
                            parts = [f"Puddle X {float(effect.get('puddle_x', 0.50)):.2f}", f"Y {float(effect.get('puddle_y', 0.84)):.2f}"]
                        elif effect.get("sun_visible"):
                            parts = [f"Sun X {float(effect.get('sun_x', 0.22)):.2f}", f"Y {float(effect.get('sun_y', 0.22)):.2f}"]
                        elif effect.get("moon_visible"):
                            parts = [f"Moon X {float(effect.get('moon_x', 0.78)):.2f}", f"Y {float(effect.get('moon_y', 0.18)):.2f}"]
                        elif effect.get("bamboo_grove_visible"):
                            parts = [f"Bamboo count {int(effect.get('bamboo_count', 12))}", f"height {float(effect.get('bamboo_height', 0.92)):.2f}"]
                        elif effect.get("cloud_visible"):
                            parts = [f"Cloud count {int(effect.get('cloud_count', 0))}", f"size {float(effect.get('cloud_size', 92.0)):.1f}"]
                        elif effect.get("fireball_visible"):
                            parts = [f"Fireball count {int(effect.get('fireball_count', 0))}", f"size {float(effect.get('fireball_size', 20.0)):.1f}"]
                        else:
                            try:
                                for template_key, spec in self.preview._lds_template_effect_specs():
                                    if bool(effect.get(f"{template_key}_visible", False)):
                                        label = str(dict(spec or {}).get("display_name", template_key))
                                        if str(dict(spec or {}).get("mode", "")) == "anchor_point":
                                            parts = [
                                                f"X {float(effect.get(str(dict(spec or {}).get('x_key') or template_key + '_x'), dict(spec or {}).get('default_x', 0.5))):.2f}",
                                                f"Y {float(effect.get(str(dict(spec or {}).get('y_key') or template_key + '_y'), dict(spec or {}).get('default_y', 0.5))):.2f}",
                                                lds_ui_text("移動のみ", "move only"),
                                            ]
                                        else:
                                            parts = [str(dict(spec or {}).get("mode", "display"))]
                                        break
                            except Exception:
                                pass
                    elif selected_type:
                        label = str(selected.get("title") or lds_ui_text("ウィジェット", "Widget"))
                        geom = selected.get("geometry") if isinstance(selected.get("geometry"), dict) else {}
                        if geom:
                            parts = [
                                f"X {int(geom.get('x', 0))}",
                                f"Y {int(geom.get('y', 0))}",
                                f"W {int(geom.get('w', 0))}",
                                f"H {int(geom.get('h', 0))}",
                            ]
            except Exception:
                label = lds_ui_text("不明", "Unknown")
                parts = []
            text = lds_ui_text("選択中: ", "Selected: ") + str(label)
            if parts:
                text += " | " + " | ".join(str(p) for p in parts)
            self.integrated_selection_label.setText(text)
            try:
                self._update_nvd_control_panel_status()
            except Exception:
                pass
        except Exception:
            pass

    def toggle_integrated_detail_settings(self):
        self.open_detail_settings_window()



    def _resolve_preset_dialog_theme(self):
        try:
            canvas = self._canvas_owner()
            theme = getattr(canvas, "studio_theme", "") if canvas is not None else ""
            if theme: return normalize_studio_theme(theme)
        except Exception: pass
        try:
            if CONFIG_PATH and os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f: data = json.load(f)
                return normalize_studio_theme(data.get("studio_theme", DEFAULT_STUDIO_THEME))
        except Exception: pass
        try: return normalize_studio_theme(DEFAULT_STUDIO_THEME)
        except Exception: return "material"
    def _effect_overlay_preview_selected_item(self):
        try:
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            selected = dict(state.get("selected", {}) or {})
            if str(selected.get("type", "")) == "effects_overlay": return dict(selected)
            for item in list(state.get("widgets", []) or []):
                item = dict(item or {})
                if str(item.get("type", "")) == "effects_overlay": return dict(item)
        except Exception: pass
        return {"type": "effects_overlay", "title": "Effects Overlay", "index": 0}
    def _set_effect_overlay_preview_selection_for_preset(self):
        try:
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            selected = self._effect_overlay_preview_selected_item()
            try: state["selected"] = self.preview._effect_overlay_full_desktop_rect_item(selected)
            except Exception: state["selected"] = dict(selected)
            self.preview._preview_state = state
            self.preview._preview_selected_widget_index = None
            return True
        except Exception: return False
    def apply_effect_preset_to_preview(self, preset_key):
        try:
            preset_key = str(preset_key or "")
            if not preset_key: return False
            spec = self.preview._lds_template_effect_spec(preset_key) if hasattr(self.preview, "_lds_template_effect_spec") else None
            if not spec:
                QMessageBox.information(self, lds_tr("プリセット"), lds_tr("このプリセットは現在の3Dテンプレートに登録されていません。")); return False
            spec = dict(spec or {}); mode = str(spec.get("mode", ""))
            pending = dict(getattr(self.preview, "_pending_template_effect_states", {}) or {})
            state = dict(getattr(self.preview, "_preview_state", {}) or {})
            effect = dict(state.get("effect", {}) or {})
            if mode == "global_display":
                try:
                    for global_key, global_spec in self.preview._lds_template_effect_specs(("global_display",)):
                        global_spec = dict(global_spec or {}); visible = str(global_key) == preset_key
                        pending[str(global_key)] = {"visible": visible, "mode": "global_display"}
                        effect[f"{global_key}_visible"] = visible
                        effect[str(global_spec.get("enabled_key") or f"{global_key}_enabled")] = visible
                except Exception:
                    pending[preset_key] = {"visible": True, "mode": mode}; effect[f"{preset_key}_visible"] = True
                # v2K global-display exclusivity fix:
                # When a full-screen/global preset is enabled after individual preset effects,
                # disable anchor_point and display_toggle_only template effects through the same
                # pending path used by manual OFF.  This keeps Apply / Save behavior consistent
                # and prevents individual effects from remaining visible over the global scene.
                try:
                    for other_key, other_spec in self.preview._lds_template_effect_specs(("anchor_point", "display_toggle_only")):
                        other_key = str(other_key or "")
                        if not other_key:
                            continue
                        other_spec = dict(other_spec or {})
                        other_mode = str(other_spec.get("mode", "")) or "display_toggle_only"
                        item = {"visible": False, "mode": other_mode}
                        if other_mode == "anchor_point":
                            x_key = str(other_spec.get("x_key") or f"{other_key}_x")
                            y_key = str(other_spec.get("y_key") or f"{other_key}_y")
                            try:
                                item["x"] = max(0.0, min(1.0, float(effect.get(x_key, other_spec.get("default_x", 0.5)))))
                                item["y"] = max(0.0, min(1.0, float(effect.get(y_key, other_spec.get("default_y", 0.5)))))
                            except Exception:
                                pass
                        pending[other_key] = item
                        effect[f"{other_key}_visible"] = False
                        effect[str(other_spec.get("enabled_key") or f"{other_key}_enabled")] = False
                except Exception:
                    pass
            elif mode == "anchor_point":
                x_key = str(spec.get("x_key") or f"{preset_key}_x"); y_key = str(spec.get("y_key") or f"{preset_key}_y")
                x = max(0.0, min(1.0, float(effect.get(x_key, spec.get("default_x", 0.5)))))
                y = max(0.0, min(1.0, float(effect.get(y_key, spec.get("default_y", 0.5)))))
                pending[preset_key] = {"visible": True, "mode": mode, "x": x, "y": y}
                effect[f"{preset_key}_visible"] = True; effect[x_key] = x; effect[y_key] = y
                effect[str(spec.get("enabled_key") or f"{preset_key}_enabled")] = True
            else:
                pending[preset_key] = {"visible": True, "mode": mode or "display_toggle_only"}
                effect[f"{preset_key}_visible"] = True
                effect[str(spec.get("enabled_key") or f"{preset_key}_enabled")] = True
            state["effect"] = effect; self.preview._preview_state = state
            self.preview._pending_template_effect_states = pending; self.preview._template_effect_selected_key = preset_key
            try:
                self.preview._water_surface_selected = False; self.preview._bamboo_grove_selected = False; self.preview._cloud_selected = False; self.preview._fireball_selected = False; self.preview._ice_selected = False
            except Exception: pass
            self._set_effect_overlay_preview_selection_for_preset()
            try: self.preview._drag_notice = f"{spec.get('display_name', preset_key)} preset pending / Apply or Save to persist"; self.preview.update()
            except Exception: pass
            try: self.update_integrated_selection_bar(); self.update_control_visibility()
            except Exception: pass
            return True
        except Exception as exc:
            try: QMessageBox.warning(self, lds_tr("プリセット"), lds_tr(f"プリセットを反映できませんでした:\n{exc}"))
            except Exception: pass
            return False
    def open_effect_preset_picker_dialog(self):
        try:
            dialog = LDS3DEffectPresetPickerDialog(self, self); dialog.show()
            try: dialog.raise_(); dialog.activateWindow()
            except Exception: pass
            self._preset_picker_dialog = dialog
        except Exception as exc:
            QMessageBox.warning(self, lds_tr("プリセット"), lds_tr(f"プリセットダイアログを開けませんでした:\n{exc}"))

    def show_integrated_presets_placeholder(self):
        self.open_effect_preset_picker_dialog()

    def save_integrated_preview_changes(self):
        applied_changes = False
        try:
            changes = dict(self.pending_preview_changes() or {})
        except Exception:
            changes = {}
        try:
            if changes:
                controller = self._controller()
                if controller is not None and hasattr(controller, "apply_3d_preview_pending_changes_to_selected_effects"):
                    self._ensure_effect_overlay_selected_for_preview_changes(controller, changes)
                    previous_state = dict(getattr(self.preview, "_preview_state", {}) or {})
                    applied_changes = bool(controller.apply_3d_preview_pending_changes_to_selected_effects(changes, show_message=False))
                    try:
                        self.update_control_visibility()
                    except Exception:
                        pass
                    try:
                        self.set_preview_state(controller.build_3d_preview_state())
                        self._restore_cloud_layer_after_preview_apply(changes, previous_state)
                        self._restore_fireball_layer_after_preview_apply(changes, previous_state)
                        self._restore_template_effect_after_preview_apply(changes, previous_state)
                    except Exception:
                        pass
                    if not applied_changes:
                        QMessageBox.warning(
                            self,
                            lds_ui_text("保存", "Save"),
                            lds_ui_text(
                                "3Dプレビュー変更を適用できなかったため、保存は中止しました。",
                                "Save was canceled because the 3D preview changes could not be applied."
                            ),
                        )
                        return
        except Exception as exc:
            try:
                apply_error_prefix = lds_ui_text("3Dプレビュー変更を適用できませんでした:", "Could not apply 3D preview changes:")
                QMessageBox.warning(self, lds_ui_text("保存", "Save"), f"{apply_error_prefix}\n{exc}")
            except Exception:
                pass
            return
        try:
            canvas = self._canvas_owner()
            if canvas is not None and hasattr(canvas, "save_config"):
                canvas.save_config()
                if applied_changes:
                    message = lds_ui_text(
                        "3Dプレビュー変更を適用し、設定を保存しました。",
                        "Applied 3D preview changes and saved the settings."
                    )
                else:
                    message = lds_ui_text("設定を保存しました。", "Settings saved.")
                QMessageBox.information(self, lds_ui_text("保存", "Save"), message)
                return
        except Exception as exc:
            try:
                save_error_prefix = lds_ui_text("保存できませんでした:", "Could not save:")
                QMessageBox.warning(self, lds_ui_text("保存", "Save"), f"{save_error_prefix}\n{exc}")
            except Exception:
                pass
            return
        try:
            QMessageBox.information(
                self,
                lds_ui_text("保存", "Save"),
                lds_ui_text("保存処理を完了しました。", "Save completed."),
            )
        except Exception:
            pass


    def apply_integrated_preview_window_geometry(self):
        min_w = 980
        min_h = 680
        fallback_w = 1280
        fallback_h = 780
        try:
            screen = QApplication.primaryScreen()
            if screen is None:
                raise RuntimeError("primary screen is unavailable")
            geom = screen.availableGeometry()
            safe_w = max(760, int(geom.width()) - 48)
            safe_h = max(560, int(geom.height()) - 48)
            target_w = min(1480, max(min_w, int(geom.width() * 0.86)))
            target_h = min(920, max(min_h, int(geom.height() * 0.86)))
            target_w = min(target_w, safe_w)
            target_h = min(target_h, safe_h)
            try:
                self.setMinimumSize(min(900, target_w), min(620, target_h))
            except Exception:
                pass
            self.resize(target_w, target_h)
            try:
                self.move(
                    geom.x() + max(0, (geom.width() - self.width()) // 2),
                    geom.y() + max(0, (geom.height() - self.height()) // 2),
                )
            except Exception:
                pass
        except Exception:
            try:
                self.setMinimumSize(900, 620)
            except Exception:
                pass
            self.resize(fallback_w, fallback_h)

    def close_application_from_integrated_ui(self):
        try:
            QApplication.quit()
        except Exception:
            pass

    def __init__(self, parent=None):
        # Keep a canvas owner reference, but do not make the 3D preview a child/tool window.
        # As a real top-level window it gets a normal taskbar entry and can be restored after minimize.
        self._canvas_owner_ref = parent
        super().__init__(None)
        try:
            flags = self.windowFlags()
            try:
                flags &= ~Qt.WindowType.Tool
            except Exception:
                pass
            flags |= Qt.WindowType.Window
            flags |= Qt.WindowType.WindowSystemMenuHint
            flags |= Qt.WindowType.WindowMinimizeButtonHint
            flags |= Qt.WindowType.WindowMaximizeButtonHint
            flags |= Qt.WindowType.WindowCloseButtonHint
            self.setWindowFlags(flags)
        except Exception:
            pass
        if os.path.exists(os.path.join(os.getcwd(), 'icon.png')):
            self.setWindowIcon(QIcon(os.path.join(os.getcwd(), 'icon.png')))
        self.setWindowTitle(lds_ui_text("{} - 3Dプレビュー".format(APP_NAME), "{} - 3D Preview".format(APP_NAME)))
        self.apply_integrated_preview_window_geometry()
        self._integrated_details_visible = False

        self.canvas = self._canvas_owner()
        self._detail_studio = None
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 2, 2)
        title_row.setSpacing(10)

        self.integrated_logo_label = QLabel()
        self.integrated_logo_label.setFixedSize(42, 42)
        self.integrated_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.integrated_logo_label.setVisible(False)
        try:
            icon_candidates = []
            try:
                icon_candidates.append(Path(__file__).resolve().parent / "icon.png")
            except Exception:
                pass
            try:
                icon_candidates.append(Path.cwd() / "icon.png")
            except Exception:
                pass
            try:
                base_dir = _lds_app_base_dir()
                if base_dir is not None:
                    icon_candidates.append(Path(base_dir) / "icon.png")
            except Exception:
                pass
            seen_icon_paths = set()
            for icon_path in icon_candidates:
                try:
                    icon_path = Path(icon_path)
                    key = str(icon_path.resolve()) if icon_path.exists() else str(icon_path)
                    if key in seen_icon_paths:
                        continue
                    seen_icon_paths.add(key)
                    if not icon_path.exists():
                        continue
                    pixmap = QPixmap(str(icon_path))
                    if pixmap.isNull():
                        continue
                    try:
                        pixmap = pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    except Exception:
                        pixmap = pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.integrated_logo_label.setPixmap(pixmap)
                    self.integrated_logo_label.setVisible(True)
                    self.integrated_logo_label.setToolTip(str(icon_path))
                    break
                except Exception:
                    continue
        except Exception:
            pass
        title_row.addWidget(self.integrated_logo_label)

        title_text_col = QVBoxLayout()
        title_text_col.setContentsMargins(0, 0, 0, 0)
        title_text_col.setSpacing(0)
        self.integrated_title_label = QLabel("Lite Desktop Studio")
        self.integrated_title_label.setObjectName("Title")
        self.integrated_subtitle_label = QLabel(lds_ui_text("3Dプレビュー / オブジェクトを直接ドラッグ・選択", "3D Preview / Directly drag and select objects"))
        self.integrated_subtitle_label.setObjectName("SubText")
        title_text_col.addWidget(self.integrated_title_label)
        title_text_col.addWidget(self.integrated_subtitle_label)
        title_row.addLayout(title_text_col, 1)
        layout.addLayout(title_row)

        try:
            self._apply_nvd_control_panel_visual_style()
            self.nvd_status_panel = self._create_nvd_control_panel_status_bar()
            if self.nvd_status_panel is not None:
                layout.addWidget(self.nvd_status_panel)
        except Exception:
            pass

        self.preview = LDSPreview3DWidget(self)
        layout.addWidget(self.preview, 1)

        selection_bar = QGroupBox(lds_ui_text("統合操作", "Controls"))
        selection_layout = QHBoxLayout(selection_bar)
        selection_layout.setContentsMargins(10, 6, 10, 6)
        self.integrated_selection_label = QLabel(lds_ui_text("選択中: なし | X -- | Y --", "Selected: None | X -- | Y --"))
        self.integrated_selection_label.setObjectName("StatusText")
        self.integrated_selection_label.setWordWrap(True)
        selection_layout.addWidget(self.integrated_selection_label, 1)
        self.btn_integrated_detail_settings = QPushButton(lds_ui_text("詳細設定", "Details"))
        self.btn_integrated_detail_settings.setToolTip(lds_ui_text("既存の詳細設定画面を開きます。", "Open the existing detailed settings window."))
        self.btn_integrated_detail_settings.clicked.connect(self.open_detail_settings_window)
        selection_layout.addWidget(self.btn_integrated_detail_settings)
        layout.addWidget(selection_bar)

        bottom_row = QHBoxLayout()
        self.btn_integrated_exit_app = QPushButton(lds_ui_text("終了", "Exit"))
        self.btn_integrated_exit_app.setObjectName("IntegratedExitButton")
        self.btn_integrated_exit_app.setStyleSheet("""
            QPushButton#IntegratedExitButton {
                color: #FF5A5A;
                font-weight: 800;
            }
            QPushButton#IntegratedExitButton:hover {
                color: #FF7777;
            }
            QPushButton#IntegratedExitButton:pressed {
                color: #FF3030;
            }
        """)
        self.btn_integrated_exit_app.setToolTip(lds_ui_text("Lite Desktop Studioを終了します。必要に応じて先に保存してください。", "Exit Lite Desktop Studio. Save first if needed."))
        self.btn_integrated_exit_app.clicked.connect(self.close_application_from_integrated_ui)
        bottom_row.addWidget(self.btn_integrated_exit_app)
        bottom_row.addSpacing(28)

        self.developer_mode_check = QCheckBox(lds_ui_text("診断", "Diagnostics"))
        self.developer_mode_check.setToolTip(lds_ui_text("ONにすると、3Dプレビュー上の詳細ステータスや未反映サマリーを表示します。", "Show detailed status and pending-change summaries in the 3D preview."))
        self.developer_mode_check.setChecked(False)
        self.developer_mode_check.stateChanged.connect(lambda state: self.set_developer_mode(state == Qt.CheckState.Checked.value or state == Qt.CheckState.Checked))
        bottom_row.addWidget(self.developer_mode_check)

        self.preview_background_combo = QComboBox()
        self.preview_background_combo.setToolTip(lds_ui_text("診断ONの間だけ、3Dプレビュー背景グラデーションを切り替えます。", "Change the 3D preview background gradient while Diagnostics is ON."))
        for _label, _value in [
            (lds_ui_text("背景: Blue", "Background: Blue"), "blue"),
            (lds_ui_text("背景: Light", "Background: Light"), "light_nvd"),
            (lds_ui_text("背景: Black Lime", "Background: Black Lime"), "black_lime"),
            (lds_ui_text("背景: White", "Background: White"), "white"),
            (lds_ui_text("背景: Graphite", "Background: Graphite"), "graphite"),
        ]:
            self.preview_background_combo.addItem(_label, _value)
        self.preview_background_combo.currentIndexChanged.connect(self.on_preview_background_theme_changed)
        self.preview_background_combo.setVisible(False)
        self.preview_background_combo.setEnabled(False)
        bottom_row.addWidget(self.preview_background_combo)

        self.btn_integrated_presets = QPushButton(lds_ui_text("プリセット", "Presets"))
        self.btn_integrated_presets.setToolTip(lds_ui_text("エフェクトプリセットを3Dプレビューの未反映変更として追加します。", "Add effect presets as pending 3D preview changes."))
        self.btn_integrated_presets.clicked.connect(self.show_integrated_presets_placeholder)
        bottom_row.addWidget(self.btn_integrated_presets)

        self.desktop_lock_check = QCheckBox(lds_ui_text("固定: ON", "Lock: ON"))
        self.desktop_lock_check.setToolTip(lds_ui_text("ONにすると、視点操作を止めて3Dプレビュー上のオブジェクトを直接編集できます。OFFではドラッグで視点操作できます。", "ON enables direct object editing in the 3D preview. OFF enables camera/view dragging."))
        self.desktop_lock_check.setChecked(False)
        self.desktop_lock_check.stateChanged.connect(lambda state: self.set_desktop_locked(state == Qt.CheckState.Checked.value or state == Qt.CheckState.Checked))
        bottom_row.addWidget(self.desktop_lock_check)

        self.snap_edit_check = QCheckBox(lds_ui_text("スナップ: OFF", "Snap: OFF"))
        self.snap_edit_check.setToolTip(lds_ui_text("ONにすると、移動/サイズ/回転やエフェクト座標が一定単位に吸着します。", "Snap movement, resizing, rotation, and effect coordinates to fixed increments."))
        self.snap_edit_check.setChecked(False)
        self.snap_edit_check.toggled.connect(self.set_snap_enabled)
        bottom_row.addWidget(self.snap_edit_check)

        self.btn_discard_preview_changes = QPushButton(lds_ui_text("破棄", "Discard"))
        self.btn_discard_preview_changes.setObjectName("LDSNvdDiscardButton")
        self.btn_discard_preview_changes.setToolTip(lds_ui_text("3Dプレビュー内で未反映の一時変更を破棄します。", "Discard unapplied temporary changes in the 3D preview."))
        self.btn_discard_preview_changes.clicked.connect(self.discard_all_pending_preview_changes)
        bottom_row.addWidget(self.btn_discard_preview_changes)
        bottom_row.addStretch(1)

        self.btn_apply_all_preview = QPushButton(lds_ui_text("適用", "Apply"))
        self.btn_apply_all_preview.setObjectName("LDSNvdApplyButton")
        self.btn_apply_all_preview.setToolTip(lds_ui_text("3Dプレビュー内の未反映変更を本体設定へ適用します。", "Apply unapplied 3D preview changes to the main settings."))
        self.btn_apply_all_preview.clicked.connect(self.apply_all_pending_preview_changes_to_parent)
        bottom_row.addWidget(self.btn_apply_all_preview)

        self.btn_save_integrated_preview = QPushButton(lds_ui_text("保存", "Save"))
        self.btn_save_integrated_preview.setToolTip(lds_ui_text("3Dプレビュー変更を適用し、設定ファイルへ保存します。", "Apply 3D preview changes and save the settings file."))
        self.btn_save_integrated_preview.clicked.connect(self.save_integrated_preview_changes)
        bottom_row.addWidget(self.btn_save_integrated_preview)
        layout.addLayout(bottom_row)

        controls_group = QGroupBox(lds_tr("詳細設定（従来UI）"))
        self.detail_controls_group = controls_group
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setContentsMargins(10, 8, 10, 8)
        controls_layout.setSpacing(6)

        self.mode_label = QLabel(lds_tr("編集モード: 未選択"))
        self.mode_label.setObjectName("StatusText")
        controls_layout.addWidget(self.mode_label)
        self.pending_summary_label = QLabel(lds_tr("未反映: なし"))
        self.pending_summary_label.setObjectName("StatusText")
        self.pending_summary_label.setWordWrap(True)
        controls_layout.addWidget(self.pending_summary_label)

        main_row = QHBoxLayout()
        main_row.addStretch(1)
        controls_layout.addLayout(main_row)

        self.widget_controls_group = QGroupBox(lds_tr("通常ウィジェット"))
        widget_row = QHBoxLayout(self.widget_controls_group)
        widget_row.setContentsMargins(8, 6, 8, 6)
        self.btn_reset_widget_rotation_preview = QPushButton(lds_tr("回転0°"))
        self.btn_reset_widget_rotation_preview.setToolTip(lds_tr("選択中の通常ウィジェットの回転を、3Dプレビュー上で一時的に0°へ戻します。反映には『適用』が必要です。"))
        self.btn_reset_widget_rotation_preview.clicked.connect(self.reset_selected_widget_rotation_preview)
        widget_row.addWidget(self.btn_reset_widget_rotation_preview)
        widget_row.addWidget(QLabel(lds_tr("矩形: ドラッグ=移動 / 緑=サイズ / 青=回転")))
        widget_row.addStretch(1)
        controls_layout.addWidget(self.widget_controls_group)

        self.effect_controls_group = QGroupBox(lds_tr("Effects Overlay"))
        effect_row = QHBoxLayout(self.effect_controls_group)
        effect_row.setContentsMargins(8, 6, 8, 6)
        self.btn_apply_sun_preview = QPushButton(lds_tr("Sun位置"))
        self.btn_apply_sun_preview.setToolTip(lds_tr("現在の3Dプレビュー上のSun位置を、選択中のエフェクトオーバーレイ設定へ書き戻します。"))
        self.btn_apply_sun_preview.clicked.connect(self.apply_preview_sun_to_parent)
        effect_row.addWidget(self.btn_apply_sun_preview)
        self.btn_apply_moon_preview = QPushButton(lds_tr("Moon位置"))
        self.btn_apply_moon_preview.setToolTip(lds_tr("現在の3Dプレビュー上のMoon位置を、選択中のエフェクトオーバーレイ設定へ書き戻します。"))
        self.btn_apply_moon_preview.clicked.connect(self.apply_preview_moon_to_parent)
        effect_row.addWidget(self.btn_apply_moon_preview)
        self.btn_apply_puddle_preview = QPushButton(lds_tr("選択Puddle位置/サイズ"))
        self.btn_apply_puddle_preview.setToolTip(lds_tr("現在の3Dプレビュー上の選択Puddle位置/サイズを、選択中のエフェクトオーバーレイ設定へ書き戻します。"))
        self.btn_apply_puddle_preview.clicked.connect(self.apply_preview_puddle_to_parent)
        effect_row.addWidget(self.btn_apply_puddle_preview)
        effect_row.addWidget(QLabel(lds_tr("Sun/Moon/Ice/Puddle: 3D直接編集。詳細な個別設定は既存設定画面で調整します。")))
        effect_row.addStretch(1)
        controls_layout.addWidget(self.effect_controls_group)

        layout.addWidget(controls_group)
        controls_group.setVisible(False)

        self.preview.set_desktop_locked(self.desktop_lock_check.isChecked())
        try:
            self.preview.set_developer_mode(self.developer_mode_check.isChecked())
            try:
                self.preview.set_preview_background_theme(self.preview_background_combo.currentData())
            except Exception:
                pass
            self.preview.set_snap_enabled(self.snap_edit_check.isChecked())
        except Exception:
            pass

        status_text = lds_tr("OpenGL: QOpenGLWidgetを使用中") if QOpenGLWidget is not None else lds_tr("OpenGL: QWidgetフォールバック")
        status = QLabel(status_text)
        status.setObjectName("StatusText")
        self.preview_status_label = status
        layout.addWidget(status)
        self.preview.set_developer_mode(self.is_developer_mode())
        try:
            controller = self._ensure_detail_studio()
            if controller is not None:
                controller.preview_3d_test_window = self
                self.set_preview_state(controller.build_3d_preview_state())
        except Exception:
            pass
        self.update_control_visibility()
        self.update_integrated_selection_bar()
        try:
            self._update_nvd_control_panel_status()
        except Exception:
            pass
        try:
            self._start_live_status_refresh_timer()
        except Exception:
            pass

@dataclass(frozen=True)
class Preview3DExtractionPlan:
    """Metadata documenting the current extraction phase."""

    phase: str = "23D4B"
    moved_classes: tuple[str, ...] = ("LDSRightDoubleClickCatcher", "LDSPreview3DWidget", "LDSPreview3DWindow")
    keep_in_main_initially: tuple[str, ...] = (
        "build_3d_preview_state",
        "apply_3d_preview_pending_changes_to_selected_effects",
    )


EXTRACTION_PLAN = Preview3DExtractionPlan()

__all__ = [
    "LDSRightDoubleClickCatcher",
    "LDSPreview3DWidget",
    "LDSPreview3DWindow",
    "Preview3DExtractionPlan",
    "EXTRACTION_PLAN",
]


def module_ready() -> bool:
    return True

# BEGIN GENERATED LDS_3D_EFFECT_TEMPLATE_SPECS
# {
#   "effects": {
#     "antelope_canyon": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Antelope Canyon",
#       "effect_key": "antelope_canyon",
#       "enabled_key": "antelope_canyon_engine_enabled",
#       "mode": "global_display",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "",
#       "y_key": ""
#     },
#     "balloon": {
#       "default_x": 0.5,
#       "default_y": 0.45,
#       "display_name": "Balloon",
#       "effect_key": "balloon",
#       "enabled_key": "balloon_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "balloon_x",
#       "y_key": "balloon_y"
#     },
#     "blooming_roses": {
#       "default_x": 0.5,
#       "default_y": 0.62,
#       "display_name": "Blooming Roses",
#       "effect_key": "blooming_roses",
#       "enabled_key": "blooming_roses_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "blooming_roses_x",
#       "y_key": "blooming_roses_y"
#     },
#     "blue_hole_deep_lake": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Blue Hole Deep Lake",
#       "effect_key": "blue_hole_deep_lake",
#       "enabled_key": "blue_hole_deep_lake_engine_enabled",
#       "mode": "global_display",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "",
#       "y_key": ""
#     },
#     "bubble": {
#       "default_x": 0.5,
#       "default_y": 0.62,
#       "display_name": "Bubble",
#       "effect_key": "bubble",
#       "enabled_key": "bubble_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "bubble_x",
#       "y_key": "bubble_y"
#     },
#     "chichibugahama_mirror": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Chichibugahama Mirror",
#       "effect_key": "chichibugahama_mirror",
#       "enabled_key": "chichibugahama_mirror_engine_enabled",
#       "mode": "global_display",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "",
#       "y_key": ""
#     },
#     "flame": {
#       "default_x": 0.5,
#       "default_y": 0.78,
#       "display_name": "Flame",
#       "effect_key": "flame",
#       "enabled_key": "flame_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "flame_x",
#       "y_key": "flame_y"
#     },
#     "glow": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Glow Orbs",
#       "effect_key": "glow",
#       "enabled_key": "glow_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "glow_x",
#       "y_key": "glow_y"
#     },
#     "meteor_shower": {
#       "default_x": 0.35,
#       "default_y": 0.22,
#       "display_name": "Meteor Shower",
#       "effect_key": "meteor_shower",
#       "enabled_key": "meteor_shower_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "meteor_shower_x",
#       "y_key": "meteor_shower_y"
#     },
#     "milky_way": {
#       "default_x": 0.5,
#       "default_y": 0.2,
#       "display_name": "Milky Way",
#       "effect_key": "milky_way",
#       "enabled_key": "milky_way_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "milky_way_x",
#       "y_key": "milky_way_y"
#     },
#     "mouse_glow": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Mouse Glow",
#       "effect_key": "mouse_glow",
#       "enabled_key": "mouse_glow_enabled",
#       "mode": "preview_skip",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": false,
#       "supports_resize": false,
#       "x_key": "mouse_glow_x",
#       "y_key": "mouse_glow_y"
#     },
#     "mouse_ripple": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Mouse Ripple",
#       "effect_key": "mouse_ripple",
#       "enabled_key": "mouse_ripple_enabled",
#       "mode": "preview_skip",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": false,
#       "supports_resize": false,
#       "x_key": "mouse_ripple_x",
#       "y_key": "mouse_ripple_y"
#     },
#     "noise": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Noise",
#       "effect_key": "noise",
#       "enabled_key": "noise_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "noise_x",
#       "y_key": "noise_y"
#     },
#     "pamukkale_terrace_lake": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Pamukkale Terrace Lake",
#       "effect_key": "pamukkale_terrace_lake",
#       "enabled_key": "pamukkale_terrace_lake_engine_enabled",
#       "mode": "global_display",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "",
#       "y_key": ""
#     },
#     "particles": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Particles",
#       "effect_key": "particles",
#       "enabled_key": "particles_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "particles_x",
#       "y_key": "particles_y"
#     },
#     "rain": {
#       "default_x": 0.5,
#       "default_y": 0.24,
#       "display_name": "Rain",
#       "effect_key": "rain",
#       "enabled_key": "rain_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "rain_x",
#       "y_key": "rain_y"
#     },
#     "ripple": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Ripples",
#       "effect_key": "ripple",
#       "enabled_key": "ripple_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "ripple_x",
#       "y_key": "ripple_y"
#     },
#     "rose_flowers": {
#       "default_x": 0.5,
#       "default_y": 0.38,
#       "display_name": "Rose Flowers",
#       "effect_key": "rose_flowers",
#       "enabled_key": "rose_flowers_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "rose_flowers_x",
#       "y_key": "rose_flowers_y"
#     },
#     "rose_petals": {
#       "default_x": 0.5,
#       "default_y": 0.32,
#       "display_name": "Rose Petals",
#       "effect_key": "rose_petals",
#       "enabled_key": "rose_petals_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "rose_petals_x",
#       "y_key": "rose_petals_y"
#     },
#     "sahara_desert": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Sahara Desert",
#       "effect_key": "sahara_desert",
#       "enabled_key": "sahara_desert_engine_enabled",
#       "mode": "global_display",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "",
#       "y_key": ""
#     },
#     "sakura_petals": {
#       "default_x": 0.5,
#       "default_y": 0.32,
#       "display_name": "Sakura Petals",
#       "effect_key": "sakura_petals",
#       "enabled_key": "sakura_petals_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "sakura_petals_x",
#       "y_key": "sakura_petals_y"
#     },
#     "shooting_star": {
#       "default_x": 0.35,
#       "default_y": 0.22,
#       "display_name": "Shooting Star",
#       "effect_key": "shooting_star",
#       "enabled_key": "shooting_star_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "shooting_star_x",
#       "y_key": "shooting_star_y"
#     },
#     "snow": {
#       "default_x": 0.5,
#       "default_y": 0.28,
#       "display_name": "Snow",
#       "effect_key": "snow",
#       "enabled_key": "snow_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "snow_x",
#       "y_key": "snow_y"
#     },
#     "snow_accumulation": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Snow Accumulation",
#       "effect_key": "snow_accumulation",
#       "enabled_key": "snow_accumulation_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "snow_accumulation_x",
#       "y_key": "snow_accumulation_y"
#     },
#     "snow_crystal": {
#       "default_x": 0.5,
#       "default_y": 0.28,
#       "display_name": "Snow Crystal",
#       "effect_key": "snow_crystal",
#       "enabled_key": "snow_crystal_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "snow_crystal_x",
#       "y_key": "snow_crystal_y"
#     },
#     "star_sky": {
#       "default_x": 0.5,
#       "default_y": 0.22,
#       "display_name": "Star Sky",
#       "effect_key": "star_sky",
#       "enabled_key": "star_sky_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "star_sky_x",
#       "y_key": "star_sky_y"
#     },
#     "uyuni_salt_flat": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Uyuni Salt Flat",
#       "effect_key": "uyuni_salt_flat",
#       "enabled_key": "uyuni_salt_flat_engine_enabled",
#       "mode": "global_display",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "",
#       "y_key": ""
#     },
#     "water_drop": {
#       "default_x": 0.5,
#       "default_y": 0.35,
#       "display_name": "Water Drop",
#       "effect_key": "water_drop",
#       "enabled_key": "water_drop_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "water_drop_x",
#       "y_key": "water_drop_y"
#     },
#     "water_fish": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Water Fish",
#       "effect_key": "water_fish",
#       "enabled_key": "water_fish_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "water_fish_x",
#       "y_key": "water_fish_y"
#     },
#     "water_morning_fog": {
#       "default_x": 0.5,
#       "default_y": 0.5,
#       "display_name": "Water Morning Fog",
#       "effect_key": "water_morning_fog",
#       "enabled_key": "water_morning_fog_enabled",
#       "mode": "display_toggle_only",
#       "notes": "",
#       "supports_move": false,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "water_morning_fog_x",
#       "y_key": "water_morning_fog_y"
#     },
#     "water_spray": {
#       "default_x": 0.5,
#       "default_y": 0.72,
#       "display_name": "Water Spray",
#       "effect_key": "water_spray",
#       "enabled_key": "water_spray_enabled",
#       "mode": "anchor_point",
#       "notes": "",
#       "supports_move": true,
#       "supports_preview_display": true,
#       "supports_resize": false,
#       "x_key": "water_spray_x",
#       "y_key": "water_spray_y"
#     }
#   },
#   "version": "Phase23E-template-v1"
# }
# END GENERATED LDS_3D_EFFECT_TEMPLATE_SPECS

# BEGIN GENERATED LDS_3D_EFFECT_TEMPLATE_RUNTIME
LDS_3D_EFFECT_TEMPLATE_RUNTIME = {'effects': {'antelope_canyon': {'default_x': 0.5,
                                 'default_y': 0.5,
                                 'display_name': 'Antelope Canyon',
                                 'effect_key': 'antelope_canyon',
                                 'enabled_key': 'antelope_canyon_engine_enabled',
                                 'mode': 'global_display',
                                 'notes': '',
                                 'supports_move': False,
                                 'supports_preview_display': True,
                                 'supports_resize': False,
                                 'x_key': '',
                                 'y_key': ''},
             'balloon': {'default_x': 0.5,
                         'default_y': 0.45,
                         'display_name': 'Balloon',
                         'effect_key': 'balloon',
                         'enabled_key': 'balloon_enabled',
                         'mode': 'anchor_point',
                         'notes': '',
                         'supports_move': True,
                         'supports_preview_display': True,
                         'supports_resize': False,
                         'x_key': 'balloon_x',
                         'y_key': 'balloon_y'},
             'blooming_roses': {'default_x': 0.5,
                                'default_y': 0.62,
                                'display_name': 'Blooming Roses',
                                'effect_key': 'blooming_roses',
                                'enabled_key': 'blooming_roses_enabled',
                                'mode': 'anchor_point',
                                'notes': '',
                                'supports_move': True,
                                'supports_preview_display': True,
                                'supports_resize': False,
                                'x_key': 'blooming_roses_x',
                                'y_key': 'blooming_roses_y'},
             'blue_hole_deep_lake': {'default_x': 0.5,
                                     'default_y': 0.5,
                                     'display_name': 'Blue Hole Deep Lake',
                                     'effect_key': 'blue_hole_deep_lake',
                                     'enabled_key': 'blue_hole_deep_lake_engine_enabled',
                                     'mode': 'global_display',
                                     'notes': '',
                                     'supports_move': False,
                                     'supports_preview_display': True,
                                     'supports_resize': False,
                                     'x_key': '',
                                     'y_key': ''},
             'bubble': {'default_x': 0.5,
                        'default_y': 0.62,
                        'display_name': 'Bubble',
                        'effect_key': 'bubble',
                        'enabled_key': 'bubble_enabled',
                        'mode': 'anchor_point',
                        'notes': '',
                        'supports_move': True,
                        'supports_preview_display': True,
                        'supports_resize': False,
                        'x_key': 'bubble_x',
                        'y_key': 'bubble_y'},
             'chichibugahama_mirror': {'default_x': 0.5,
                                       'default_y': 0.5,
                                       'display_name': 'Chichibugahama Mirror',
                                       'effect_key': 'chichibugahama_mirror',
                                       'enabled_key': 'chichibugahama_mirror_engine_enabled',
                                       'mode': 'global_display',
                                       'notes': '',
                                       'supports_move': False,
                                       'supports_preview_display': True,
                                       'supports_resize': False,
                                       'x_key': '',
                                       'y_key': ''},
             'flame': {'default_x': 0.5,
                       'default_y': 0.78,
                       'display_name': 'Flame',
                       'effect_key': 'flame',
                       'enabled_key': 'flame_enabled',
                       'mode': 'anchor_point',
                       'notes': '',
                       'supports_move': True,
                       'supports_preview_display': True,
                       'supports_resize': False,
                       'x_key': 'flame_x',
                       'y_key': 'flame_y'},
             'glow': {'default_x': 0.5,
                      'default_y': 0.5,
                      'display_name': 'Glow Orbs',
                      'effect_key': 'glow',
                      'enabled_key': 'glow_enabled',
                      'mode': 'display_toggle_only',
                      'notes': '',
                      'supports_move': False,
                      'supports_preview_display': True,
                      'supports_resize': False,
                      'x_key': 'glow_x',
                      'y_key': 'glow_y'},
             'meteor_shower': {'default_x': 0.35,
                               'default_y': 0.22,
                               'display_name': 'Meteor Shower',
                               'effect_key': 'meteor_shower',
                               'enabled_key': 'meteor_shower_enabled',
                               'mode': 'anchor_point',
                               'notes': '',
                               'supports_move': True,
                               'supports_preview_display': True,
                               'supports_resize': False,
                               'x_key': 'meteor_shower_x',
                               'y_key': 'meteor_shower_y'},
             'milky_way': {'default_x': 0.5,
                           'default_y': 0.2,
                           'display_name': 'Milky Way',
                           'effect_key': 'milky_way',
                           'enabled_key': 'milky_way_enabled',
                           'mode': 'anchor_point',
                           'notes': '',
                           'supports_move': True,
                           'supports_preview_display': True,
                           'supports_resize': False,
                           'x_key': 'milky_way_x',
                           'y_key': 'milky_way_y'},
             'mouse_glow': {'default_x': 0.5,
                            'default_y': 0.5,
                            'display_name': 'Mouse Glow',
                            'effect_key': 'mouse_glow',
                            'enabled_key': 'mouse_glow_enabled',
                            'mode': 'preview_skip',
                            'notes': '',
                            'supports_move': False,
                            'supports_preview_display': False,
                            'supports_resize': False,
                            'x_key': 'mouse_glow_x',
                            'y_key': 'mouse_glow_y'},
             'mouse_ripple': {'default_x': 0.5,
                              'default_y': 0.5,
                              'display_name': 'Mouse Ripple',
                              'effect_key': 'mouse_ripple',
                              'enabled_key': 'mouse_ripple_enabled',
                              'mode': 'preview_skip',
                              'notes': '',
                              'supports_move': False,
                              'supports_preview_display': False,
                              'supports_resize': False,
                              'x_key': 'mouse_ripple_x',
                              'y_key': 'mouse_ripple_y'},
             'noise': {'default_x': 0.5,
                       'default_y': 0.5,
                       'display_name': 'Noise',
                       'effect_key': 'noise',
                       'enabled_key': 'noise_enabled',
                       'mode': 'display_toggle_only',
                       'notes': '',
                       'supports_move': False,
                       'supports_preview_display': True,
                       'supports_resize': False,
                       'x_key': 'noise_x',
                       'y_key': 'noise_y'},
             'pamukkale_terrace_lake': {'default_x': 0.5,
                                        'default_y': 0.5,
                                        'display_name': 'Pamukkale Terrace Lake',
                                        'effect_key': 'pamukkale_terrace_lake',
                                        'enabled_key': 'pamukkale_terrace_lake_engine_enabled',
                                        'mode': 'global_display',
                                        'notes': '',
                                        'supports_move': False,
                                        'supports_preview_display': True,
                                        'supports_resize': False,
                                        'x_key': '',
                                        'y_key': ''},
             'particles': {'default_x': 0.5,
                           'default_y': 0.5,
                           'display_name': 'Particles',
                           'effect_key': 'particles',
                           'enabled_key': 'particles_enabled',
                           'mode': 'display_toggle_only',
                           'notes': '',
                           'supports_move': False,
                           'supports_preview_display': True,
                           'supports_resize': False,
                           'x_key': 'particles_x',
                           'y_key': 'particles_y'},
             'rain': {'default_x': 0.5,
                      'default_y': 0.24,
                      'display_name': 'Rain',
                      'effect_key': 'rain',
                      'enabled_key': 'rain_enabled',
                      'mode': 'anchor_point',
                      'notes': '',
                      'supports_move': True,
                      'supports_preview_display': True,
                      'supports_resize': False,
                      'x_key': 'rain_x',
                      'y_key': 'rain_y'},
             'ripple': {'default_x': 0.5,
                        'default_y': 0.5,
                        'display_name': 'Ripples',
                        'effect_key': 'ripple',
                        'enabled_key': 'ripple_enabled',
                        'mode': 'display_toggle_only',
                        'notes': '',
                        'supports_move': False,
                        'supports_preview_display': True,
                        'supports_resize': False,
                        'x_key': 'ripple_x',
                        'y_key': 'ripple_y'},
             'rose_flowers': {'default_x': 0.5,
                              'default_y': 0.38,
                              'display_name': 'Rose Flowers',
                              'effect_key': 'rose_flowers',
                              'enabled_key': 'rose_flowers_enabled',
                              'mode': 'anchor_point',
                              'notes': '',
                              'supports_move': True,
                              'supports_preview_display': True,
                              'supports_resize': False,
                              'x_key': 'rose_flowers_x',
                              'y_key': 'rose_flowers_y'},
             'rose_petals': {'default_x': 0.5,
                             'default_y': 0.32,
                             'display_name': 'Rose Petals',
                             'effect_key': 'rose_petals',
                             'enabled_key': 'rose_petals_enabled',
                             'mode': 'anchor_point',
                             'notes': '',
                             'supports_move': True,
                             'supports_preview_display': True,
                             'supports_resize': False,
                             'x_key': 'rose_petals_x',
                             'y_key': 'rose_petals_y'},
             'sahara_desert': {'default_x': 0.5,
                               'default_y': 0.5,
                               'display_name': 'Sahara Desert',
                               'effect_key': 'sahara_desert',
                               'enabled_key': 'sahara_desert_engine_enabled',
                               'mode': 'global_display',
                               'notes': '',
                               'supports_move': False,
                               'supports_preview_display': True,
                               'supports_resize': False,
                               'x_key': '',
                               'y_key': ''},
             'sakura_petals': {'default_x': 0.5,
                               'default_y': 0.32,
                               'display_name': 'Sakura Petals',
                               'effect_key': 'sakura_petals',
                               'enabled_key': 'sakura_petals_enabled',
                               'mode': 'anchor_point',
                               'notes': '',
                               'supports_move': True,
                               'supports_preview_display': True,
                               'supports_resize': False,
                               'x_key': 'sakura_petals_x',
                               'y_key': 'sakura_petals_y'},
             'shooting_star': {'default_x': 0.35,
                               'default_y': 0.22,
                               'display_name': 'Shooting Star',
                               'effect_key': 'shooting_star',
                               'enabled_key': 'shooting_star_enabled',
                               'mode': 'anchor_point',
                               'notes': '',
                               'supports_move': True,
                               'supports_preview_display': True,
                               'supports_resize': False,
                               'x_key': 'shooting_star_x',
                               'y_key': 'shooting_star_y'},
             'snow': {'default_x': 0.5,
                      'default_y': 0.28,
                      'display_name': 'Snow',
                      'effect_key': 'snow',
                      'enabled_key': 'snow_enabled',
                      'mode': 'anchor_point',
                      'notes': '',
                      'supports_move': True,
                      'supports_preview_display': True,
                      'supports_resize': False,
                      'x_key': 'snow_x',
                      'y_key': 'snow_y'},
             'snow_accumulation': {'default_x': 0.5,
                                   'default_y': 0.5,
                                   'display_name': 'Snow Accumulation',
                                   'effect_key': 'snow_accumulation',
                                   'enabled_key': 'snow_accumulation_enabled',
                                   'mode': 'display_toggle_only',
                                   'notes': '',
                                   'supports_move': False,
                                   'supports_preview_display': True,
                                   'supports_resize': False,
                                   'x_key': 'snow_accumulation_x',
                                   'y_key': 'snow_accumulation_y'},
             'snow_crystal': {'default_x': 0.5,
                              'default_y': 0.28,
                              'display_name': 'Snow Crystal',
                              'effect_key': 'snow_crystal',
                              'enabled_key': 'snow_crystal_enabled',
                              'mode': 'anchor_point',
                              'notes': '',
                              'supports_move': True,
                              'supports_preview_display': True,
                              'supports_resize': False,
                              'x_key': 'snow_crystal_x',
                              'y_key': 'snow_crystal_y'},
             'star_sky': {'default_x': 0.5,
                          'default_y': 0.22,
                          'display_name': 'Star Sky',
                          'effect_key': 'star_sky',
                          'enabled_key': 'star_sky_enabled',
                          'mode': 'anchor_point',
                          'notes': '',
                          'supports_move': True,
                          'supports_preview_display': True,
                          'supports_resize': False,
                          'x_key': 'star_sky_x',
                          'y_key': 'star_sky_y'},
             'uyuni_salt_flat': {'default_x': 0.5,
                                 'default_y': 0.5,
                                 'display_name': 'Uyuni Salt Flat',
                                 'effect_key': 'uyuni_salt_flat',
                                 'enabled_key': 'uyuni_salt_flat_engine_enabled',
                                 'mode': 'global_display',
                                 'notes': '',
                                 'supports_move': False,
                                 'supports_preview_display': True,
                                 'supports_resize': False,
                                 'x_key': '',
                                 'y_key': ''},
             'water_drop': {'default_x': 0.5,
                            'default_y': 0.35,
                            'display_name': 'Water Drop',
                            'effect_key': 'water_drop',
                            'enabled_key': 'water_drop_enabled',
                            'mode': 'anchor_point',
                            'notes': '',
                            'supports_move': True,
                            'supports_preview_display': True,
                            'supports_resize': False,
                            'x_key': 'water_drop_x',
                            'y_key': 'water_drop_y'},
             'water_fish': {'default_x': 0.5,
                            'default_y': 0.5,
                            'display_name': 'Water Fish',
                            'effect_key': 'water_fish',
                            'enabled_key': 'water_fish_enabled',
                            'mode': 'display_toggle_only',
                            'notes': '',
                            'supports_move': False,
                            'supports_preview_display': True,
                            'supports_resize': False,
                            'x_key': 'water_fish_x',
                            'y_key': 'water_fish_y'},
             'water_morning_fog': {'default_x': 0.5,
                                   'default_y': 0.5,
                                   'display_name': 'Water Morning Fog',
                                   'effect_key': 'water_morning_fog',
                                   'enabled_key': 'water_morning_fog_enabled',
                                   'mode': 'display_toggle_only',
                                   'notes': '',
                                   'supports_move': False,
                                   'supports_preview_display': True,
                                   'supports_resize': False,
                                   'x_key': 'water_morning_fog_x',
                                   'y_key': 'water_morning_fog_y'},
             'water_spray': {'default_x': 0.5,
                             'default_y': 0.72,
                             'display_name': 'Water Spray',
                             'effect_key': 'water_spray',
                             'enabled_key': 'water_spray_enabled',
                             'mode': 'anchor_point',
                             'notes': '',
                             'supports_move': True,
                             'supports_preview_display': True,
                             'supports_resize': False,
                             'x_key': 'water_spray_x',
                             'y_key': 'water_spray_y'}},
 'version': 'Phase23E-template-v1'}
# END GENERATED LDS_3D_EFFECT_TEMPLATE_RUNTIME
