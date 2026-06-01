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
from litedesktopstudio.effects import *
from litedesktopstudio.version import APP_NAME


class EffectsOverlayEditorDialog(QDialog):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        try:
            canvas = getattr(parent, "canvas", None)
            theme = get_canvas_studio_theme(canvas) if canvas is not None else DEFAULT_STUDIO_THEME
            self.setWindowOpacity(get_studio_window_opacity(theme))
        except:
            try:
                self.setWindowOpacity(0.90)
            except:
                pass
        from PySide6.QtWidgets import QTabWidget, QGroupBox

        self.widget = widget
        self.cfg = widget.cfg
        ensure_effect_overlay_fields(self.cfg)
        self.settings = get_effect_overlay_settings(self.cfg)

        self.setWindowTitle(lds_tr(f"{APP_NAME} - エフェクト設定"))
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
        except:
            pass
        outer.addWidget(make_beginner_guide_label(
            lds_tr("まずはここだけ見ればOK"),
            lds_tr("上のプリセットを押すだけで雰囲気を一括変更できます。細かい数値は、見た目を少し変えたい時だけ調整してください。分からない項目は初期値のままで大丈夫です。")
        ))
        quick = QHBoxLayout()
        self.btn_all_off = QPushButton(lds_tr("⛔ 全部OFF"))
        self.btn_rose_only = QPushButton(lds_tr("🌹 軽量: バラ花びらだけ"))
        self.btn_mouse_only = QPushButton(lds_tr("🖱️ マウス系だけON"))
        self.btn_ambient_only = QPushButton(lds_tr("🌿 環境系だけON"))
        self.btn_all_off.clicked.connect(self.set_all_off)
        self.btn_rose_only.clicked.connect(self.set_rose_petals_only)
        self.btn_mouse_only.clicked.connect(self.set_mouse_only)
        self.btn_ambient_only.clicked.connect(self.set_ambient_only)
        for b in [self.btn_all_off, self.btn_rose_only, self.btn_mouse_only, self.btn_ambient_only]:
            quick.addWidget(b)
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
            ('🪷 ' + lds_tr("拙政園のゆったり水庭"), "suzhou_humble_garden"),
            ('🎋 ' + lds_tr("留園の静かな庭"), "suzhou_lingering_garden"),
            ('🌧 ' + lds_tr("雨と波紋"), "rain_ripples"),
            ('❄ ' + lds_tr("雪景色"), "snow_scene"),
            ('🧊 ' + lds_tr("氷河の鏡面"), "glacier_mirror"),
            ('☄ ' + lds_tr("流星群"), "meteor_sky"),
            ('🔥 ' + lds_tr("炎と水"), "fire_and_water"),
            ('🪞 ' + lds_tr("ウユニ塩湖の静かな反射"), "uyuni_salt_flat_reflection"),
            ('🏜️ ' + lds_tr("サハラ砂漠の灼熱日光"), "sahara_desert_sun"),
            ('🏜️ ' + lds_tr("アンテロープキャニオンの岩肌"), "antelope_canyon_depth"),
            ('🏞️ ' + lds_tr("パムッカレの棚田な湖"), "pamukkale_terrace_lake"),
            ('🔵 ' + lds_tr("ブルーホールの深い青の湖"), "blue_hole_deep_lake"),
            ('🪞 ' + lds_tr("父母ヶ島の鏡面反射する水辺"), "chichibugahama_mirror"),
            ('☁️ ' + lds_tr("雲の流れ"), "cloud_drift"),
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
            except:
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
        self.effect_frame_rate = self._int_spin(1, 240, getattr(self.settings, "effect_frame_rate", 40))
        self.vector_image_cache_enabled = QCheckBox(lds_tr("ベクター描画を画像キャッシュ化"))
        self.vector_image_cache_enabled.setChecked(bool(getattr(self.settings, "vector_image_cache_enabled", True)))
        set_beginner_tooltip(self.vector_image_cache_enabled, lds_tr("水面・花びら・雨などのベクター描画を一度QImageに描いてからdrawImageで表示します。FPS優先ならON推奨です。"))
        self.vector_image_cache_fps = self._int_spin(1, 60, getattr(self.settings, "vector_image_cache_fps", 45))
        self.vector_image_cache_fps_extra = self._int_spin(1, 60, getattr(self.settings, "vector_image_cache_fps_extra", 40))
        self.vector_image_cache_fps_rain = self._int_spin(1, 60, getattr(self.settings, "vector_image_cache_fps_rain", 24))
        self.vector_image_cache_fps_ripples = self._int_spin(1, 60, getattr(self.settings, "vector_image_cache_fps_ripples", 18))
        self.vector_image_cache_fps_particles = self._int_spin(1, 60, getattr(self.settings, "vector_image_cache_fps_particles", 18))
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
        self._section(f, lds_tr("drawImage高速化"))
        f.addRow(lds_tr("ベクター画像キャッシュ"), self.vector_image_cache_enabled)
        f.addRow(lds_tr("全体キャッシュ更新FPS"), self.vector_image_cache_fps)
        f.addRow(lds_tr("水面・氷・雲などFPS"), self.vector_image_cache_fps_extra)
        f.addRow(lds_tr("雨FPS"), self.vector_image_cache_fps_rain)
        f.addRow(lds_tr("波紋FPS"), self.vector_image_cache_fps_ripples)
        f.addRow(lds_tr("粒子・花びらFPS"), self.vector_image_cache_fps_particles)
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
        self._add_effect_block(f, lds_tr("雲"), "cloud", lds_tr("柔らかい雲が空をゆっくり流れる"), 9, 0.075, 92.0, 185, ripple=False)
        self.cloud_color = self._color_row_on(f, lds_tr("雲の色"), getattr(self.settings, "cloud_color", "#F4FAFF"))
        self.cloud_shadow_color = self._color_row_on(f, lds_tr("雲の影色"), getattr(self.settings, "cloud_shadow_color", "#B8C7D8"))
        self.cloud_highlight_color = self._color_row_on(f, lds_tr("雲のハイライト色"), getattr(self.settings, "cloud_highlight_color", "#FFFFFF"))
        self.cloud_altitude = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_altitude", 0.22), 0.01)
        self.cloud_depth = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_depth", 0.42), 0.01)
        self.cloud_softness = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_softness", 0.72), 0.01)
        self.cloud_shape_randomness = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_shape_randomness", 0.85), 0.01)
        self.cloud_volume_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_volume_strength", 0.90), 0.01)
        f.addRow(lds_tr("雲の高さ"), self.cloud_altitude)
        f.addRow(lds_tr("雲の奥行き"), self.cloud_depth)
        f.addRow(lds_tr("雲の柔らかさ"), self.cloud_softness)
        f.addRow(lds_tr("雲の形ランダム度"), self.cloud_shape_randomness)
        f.addRow(lds_tr("雲の立体感"), self.cloud_volume_strength)
        self.cloud_mist_enabled = QCheckBox(lds_tr("ミスト雲を使う"))
        self.cloud_mist_enabled.setChecked(bool(getattr(self.settings, "cloud_mist_enabled", True)))
        self.cloud_mist_density = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_mist_density", 0.52), 0.01)
        self.cloud_mist_stretch = self._double_spin(0.5, 3.0, getattr(self.settings, "cloud_mist_stretch", 1.55), 0.05)
        self.cloud_mist_translucency = self._double_spin(0.1, 1.0, getattr(self.settings, "cloud_mist_translucency", 0.86), 0.01)
        f.addRow(lds_tr("軽量ミスト雲"), self.cloud_mist_enabled)
        f.addRow(lds_tr("ミスト密度"), self.cloud_mist_density)
        f.addRow(lds_tr("ミスト横伸び"), self.cloud_mist_stretch)
        f.addRow(lds_tr("ミスト透明感"), self.cloud_mist_translucency)
        self.cloud_cache_enabled = QCheckBox(lds_tr("雲キャッシュを使う"))
        self.cloud_cache_enabled.setChecked(bool(getattr(self.settings, "cloud_cache_enabled", True)))
        self.cloud_cache_quality_scale = self._double_spin(0.25, 1.0, getattr(self.settings, "cloud_cache_quality_scale", 0.62), 0.01)
        self.cloud_cache_max_items = self._int_spin(8, 512, getattr(self.settings, "cloud_cache_max_items", 96))
        self.cloud_cumulus_enabled = QCheckBox(lds_tr("入道雲モード"))
        self.cloud_cumulus_enabled.setChecked(bool(getattr(self.settings, "cloud_cumulus_enabled", True)))
        self.cloud_cumulus_fluffiness = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_cumulus_fluffiness", 0.88), 0.01)
        self.cloud_cumulus_tower_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_cumulus_tower_strength", 0.72), 0.01)
        f.addRow(lds_tr("軽量キャッシュ雲"), self.cloud_cache_enabled)
        f.addRow(lds_tr("雲キャッシュ品質"), self.cloud_cache_quality_scale)
        f.addRow(lds_tr("雲キャッシュ最大数"), self.cloud_cache_max_items)
        f.addRow(lds_tr("入道雲モード"), self.cloud_cumulus_enabled)
        f.addRow(lds_tr("入道雲ふわふわ感"), self.cloud_cumulus_fluffiness)
        f.addRow(lds_tr("入道雲の盛り上がり"), self.cloud_cumulus_tower_strength)
        self.cloud_shader_lighting_enabled = QCheckBox(lds_tr("Shaders風ライティング"))
        self.cloud_shader_lighting_enabled.setChecked(bool(getattr(self.settings, "cloud_shader_lighting_enabled", True)))
        self.cloud_shader_sun_angle = self._double_spin(-180.0, 180.0, getattr(self.settings, "cloud_shader_sun_angle", -55.0), 1.0)
        self.cloud_shader_warmth = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_shader_warmth", 0.42), 0.01)
        self.cloud_shader_rim_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_shader_rim_strength", 0.78), 0.01)
        self.cloud_shader_shadow_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_shader_shadow_strength", 0.52), 0.01)
        self.cloud_shader_bloom_strength = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_shader_bloom_strength", 0.36), 0.01)
        self.cloud_shader_contrast = self._double_spin(0.0, 1.0, getattr(self.settings, "cloud_shader_contrast", 0.58), 0.01)
        f.addRow(lds_tr("Shader風雲"), self.cloud_shader_lighting_enabled)
        f.addRow(lds_tr("太陽角度"), self.cloud_shader_sun_angle)
        f.addRow(lds_tr("暖色ハイライト"), self.cloud_shader_warmth)
        f.addRow(lds_tr("輪郭光"), self.cloud_shader_rim_strength)
        f.addRow(lds_tr("雲底影"), self.cloud_shader_shadow_strength)
        f.addRow(lds_tr("ブルーム"), self.cloud_shader_bloom_strength)
        f.addRow(lds_tr("立体コントラスト"), self.cloud_shader_contrast)
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
        self.water_mirror_reflect_cloud = QCheckBox(lds_tr("雲を反射"))
        self.water_mirror_reflect_cloud.setChecked(bool(getattr(self.settings, "water_mirror_reflect_cloud", True)))
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
        f.addRow(lds_tr("反射: 雲"), self.water_mirror_reflect_cloud)
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
        self.ice_reflect_cloud = QCheckBox(lds_tr("雲を反射"))
        self.ice_reflect_cloud.setChecked(bool(getattr(self.settings, "ice_reflect_cloud", True)))
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
        f.addRow(lds_tr("反射: 雲"), self.ice_reflect_cloud)
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
            "fireball", "star_sky", "shooting_star", "meteor_shower", "balloon", "cloud",
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
        self._theme_clear_scenic_engine_flags()
        self._set_extra_effect_toggles(False)
        # Disable LiteDesktopStudio's foreground icon redraw to avoid double icons.
        try:
            os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
        except:
            pass

        try:
            globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                "key": None,
                "image": None,
            }
        except:
            pass

        try:
            globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
        except:
            pass
        try:
            if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                self.cfg["icon_scene_render_icons"] = "off"
        except:
            pass

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
            except:
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
        self._theme_clear_scenic_engine_flags()

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

    def _theme_set_raw_extra(self, name: str, value):
        """Store theme-only settings that are saved into effects_json."""
        try:
            if not hasattr(self, "_theme_extra_settings") or self._theme_extra_settings is None:
                self._theme_extra_settings = {}
            self._theme_extra_settings[str(name)] = value
        except:
            pass

    def _theme_clear_scenic_engine_flags(self):
        """Clear all mutually-exclusive full-screen scenic engine flags.

        Without writing explicit False values into effects_json, a previously
        selected scenic preset such as Pamukkale can remain active after choosing
        a non-scenic preset. This method is intentionally called by every preset
        reset path before enabling the next theme.
        """
        for flag in [
            "sahara_desert_engine_enabled",
            "uyuni_salt_flat_engine_enabled",
            "antelope_canyon_engine_enabled",
            "pamukkale_terrace_lake_engine_enabled",
            "blue_hole_deep_lake_engine_enabled",
            "chichibugahama_mirror_engine_enabled",
        ]:
            self._theme_set_raw_extra(flag, False)
        self._theme_set_raw_extra("realtime_scenic_sky_enabled", False)
        self._theme_set_raw_extra("realtime_scenic_sun_rays_enabled", False)
        self._theme_set_raw_extra("desktop_ui_aware_rendering_enabled", False)

    def _theme_select_fullscreen_scenic_engine(self, active_flag: str, fps: int = 60, cache_fps: int = 30, intensity: float = 0.88):
        """Select exactly one full-screen scenic engine and configure safe scenic defaults."""
        cache_fps = max(60, int(cache_fps))
        self._theme_apply_60fps_scenic_foundation(fps=fps, cache_fps=cache_fps)
        self._theme_clear_scenic_engine_flags()
        scenic_flags = [
            "sahara_desert_engine_enabled",
            "uyuni_salt_flat_engine_enabled",
            "antelope_canyon_engine_enabled",
            "pamukkale_terrace_lake_engine_enabled",
            "blue_hole_deep_lake_engine_enabled",
            "chichibugahama_mirror_engine_enabled",
        ]
        for flag in scenic_flags:
            self._theme_set_raw_extra(flag, flag == active_flag)
        self._theme_set_raw_extra("realtime_scenic_sky_enabled", active_flag == "chichibugahama_mirror_engine_enabled")
        self._theme_set_raw_extra("desktop_ui_aware_rendering_enabled", False)
        self._theme_set_raw_extra("desktop_ui_mask_padding", 24)
        self._theme_set_raw_extra("desktop_ui_mask_blur", 37)
        self._theme_set_raw_extra("desktop_ui_icon_remaining_alpha", 0.12)
        self._theme_set_raw_extra("desktop_ui_mask_refresh_sec", 1.0)
        self._theme_set_raw_extra("desktop_ui_fallback_strip_enabled", True)
        self._theme_set_raw_extra("desktop_ui_fallback_width_ratio", 0.22)
        self._theme_set_value("intensity", intensity)
        self._theme_set_value("background_alpha", 0)
        self._theme_set_checked("vector_image_cache_enabled", True)
        self._theme_set_value("vector_image_cache_fps", max(1, min(60, int(cache_fps))))
        self._theme_set_value("vector_image_cache_fps_extra", max(1, min(60, int(cache_fps))))
        try:
            os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "1"
        except:
            pass
        try:
            globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {"key": None, "image": None}
            globals()["_LDS_ICON_SCENE_OVERLAY_CACHE"] = {"key": None, "image": None}
        except:
            pass
        try:
            if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                self.cfg["icon_scene_render_icons"] = "on"
        except:
            pass

    def _theme_apply_60fps_scenic_foundation(self, fps: int = 60, cache_fps: int = 8):
        """Common 60fps-first baseline for large static scenic engines."""
        self._theme_disable_all_visual_effects()
        self._theme_apply_common_lightweight(fps=fps, quality=0.50)
        self._theme_set_checked("effect_frame_rate_enabled", True)
        self._theme_set_value("effect_frame_rate", fps)
        self._theme_set_checked("vector_image_cache_enabled", True)
        self._theme_set_value("vector_image_cache_fps", max(1, min(60, int(cache_fps))))
        self._theme_set_value("vector_image_cache_fps_extra", max(1, min(60, int(cache_fps))))
        self._theme_set_value("vector_image_cache_fps_rain", max(1, min(60, int(cache_fps))))
        self._theme_set_value("vector_image_cache_fps_ripples", max(1, min(60, int(cache_fps))))
        self._theme_set_value("vector_image_cache_fps_particles", max(1, min(60, int(cache_fps))))
        self._theme_set_value("background_alpha", 0)
        self._theme_set_checked("noise_enabled", False)
        self._theme_set_checked("rain_enabled", False)
        self._theme_set_checked("particles_enabled", False)
        self._theme_set_checked("glow_enabled", False)
        self._theme_set_checked("ripple_enabled", False)
        self._theme_set_checked("mouse_ripple_enabled", False)
        self._theme_set_checked("mouse_flee_enabled", False)
        self._theme_set_checked("mouse_glow_enabled", False)
        self._theme_set_checked("rose_petals_enabled", False)
        self._theme_set_checked("sakura_petals_enabled", False)
        self._theme_set_checked("rose_flowers_enabled", False)
        self._theme_set_checked("blooming_roses_enabled", False)
        self._theme_set_checked("sunrise_enabled", False)
        self._theme_set_checked("sun_enabled", False)
        self._theme_set_checked("sunlight_enabled", False)
        self._theme_set_checked("lens_flare_enabled", False)
        self._theme_set_checked("moon_body_enabled", False)
        self._theme_set_checked("moonlight_enabled", False)
        self._theme_set_checked("moon_shadow_enabled", False)
        self._theme_set_extra("cloud", enabled=False, count=0)

    def apply_effect_theme(self, theme_id: str):
        """Enable a curated group of effects as a theme preset."""
        self._theme_disable_all_visual_effects()
        self._theme_clear_scenic_engine_flags()
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
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass

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
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
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
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
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
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
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
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
        elif theme_id == "snow_scene":
            self._theme_set_extra("snow", True, count=120, speed=0.16, size=4.2, alpha=210)
            self._theme_set_extra("snow_crystal", True, count=28, speed=0.11, size=13.0, alpha=220)
            self._theme_set_checked("ripple_enabled", True)
            self._theme_set_checked("moon_body_enabled", True)
            self._theme_set_checked("moonlight_enabled", True)
            self._theme_set_extra("star_sky", True, count=160, speed=0.18, size=1.1, alpha=150)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_value("water_surface_alpha", 62)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
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
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
        elif theme_id in ("sahara_desert_sun", "sahara_desert", "dry_desert_sun"):
            # サハラ砂漠風: 静的QImageで砂丘と灼熱太陽を描き、枯草だけを低数でゆっくり流す。
            self._theme_disable_all_visual_effects()
            self._theme_apply_common_lightweight(fps=45, quality=0.50)
            self._theme_clear_scenic_engine_flags()
            self._theme_set_raw_extra("sahara_desert_engine_enabled", True)
            self._theme_set_raw_extra("realtime_scenic_sky_enabled", True)
            self._theme_set_raw_extra("realtime_scenic_sun_rays_enabled", False)
            self._theme_set_raw_extra("desktop_ui_aware_rendering_enabled", False)
            self._theme_set_raw_extra("desktop_ui_mask_padding", 24)
            self._theme_set_raw_extra("desktop_ui_mask_blur", 37)
            self._theme_set_raw_extra("desktop_ui_icon_remaining_alpha", 0.12)
            self._theme_set_raw_extra("desktop_ui_mask_refresh_sec", 1.0)
            self._theme_set_raw_extra("desktop_ui_fallback_strip_enabled", True)
            self._theme_set_raw_extra("desktop_ui_fallback_width_ratio", 0.22)
            self._theme_set_raw_extra("uyuni_salt_flat_engine_enabled", False)
            self._theme_set_raw_extra("antelope_canyon_engine_enabled", False)
            self._theme_set_checked("vector_image_cache_enabled", True)
            self._theme_set_value("vector_image_cache_fps", 8)
            self._theme_set_value("vector_image_cache_fps_extra", 120)
            self._theme_set_value("vector_image_cache_fps_particles", 8)
            self._theme_set_value("effect_frame_rate", 40)
            self._theme_set_value("background_alpha", 0)
            self._theme_set_value("intensity", 0.96)
            self._theme_set_checked("sun_enabled", False)
            self._theme_set_checked("sunlight_enabled", False)
            self._theme_set_checked("lens_flare_enabled", False)
            self._theme_set_checked("noise_enabled", False)
            self._theme_set_extra("cloud", enabled=True, count=5)
            self._theme_set_extra("star_sky", False, count=0)
            self._theme_set_extra("shooting_star", False, count=0)
            self._theme_set_extra("meteor_shower", False, count=0)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "1"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "on"
            except:
                pass
        elif theme_id == "meteor_sky":
            self._theme_set_extra("star_sky", True, count=340, speed=0.34, size=1.5, alpha=220)
            self._theme_set_checked("milky_way_enabled", True)
            self._theme_set_value("milky_way_star_count", 220)
            self._theme_set_value("milky_way_alpha", 112)
            self._theme_set_extra("shooting_star", True, count=4, speed=0.90, size=17.0, alpha=230)
            self._theme_set_extra("meteor_shower", True, count=18, speed=0.95, size=11.5, alpha=215)
            self._theme_set_checked("moon_body_enabled", True)
            self._theme_set_value("moon_alpha", 190)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
        elif theme_id == "cloud_drift":
            self._theme_disable_all_visual_effects()
            self._theme_apply_common_lightweight()
            self._theme_set_extra("cloud", enabled=True, count=12, speed=0.8650, size=105.0, alpha=190)
            self._theme_set_text("cloud_color", "#F4FAFF")
            self._theme_set_text("cloud_shadow_color", "#AEBED2")
            self._theme_set_text("cloud_highlight_color", "#FFFFFF")
            self._theme_set_value("cloud_altitude", 0.24)
            self._theme_set_value("cloud_depth", 0.48)
            self._theme_set_value("cloud_softness", 0.78)
            self._theme_set_value("cloud_shape_randomness", 0.88)
            self._theme_set_value("cloud_volume_strength", 0.92)
            self._theme_set_checked("cloud_mist_enabled", True)
            self._theme_set_value("cloud_mist_density", 0.54)
            self._theme_set_value("cloud_mist_stretch", 1.65)
            self._theme_set_value("cloud_mist_translucency", 0.88)
            self._theme_set_checked("cloud_cache_enabled", True)
            self._theme_set_value("cloud_cache_quality_scale", 0.62)
            self._theme_set_value("cloud_cache_max_items", 96)
            self._theme_set_checked("cloud_cumulus_enabled", True)
            self._theme_set_value("cloud_cumulus_fluffiness", 0.90)
            self._theme_set_value("cloud_cumulus_tower_strength", 0.76)
            self._theme_set_checked("cloud_shader_lighting_enabled", True)
            self._theme_set_value("cloud_shader_sun_angle", -55.0)
            self._theme_set_value("cloud_shader_warmth", 0.44)
            self._theme_set_value("cloud_shader_rim_strength", 0.82)
            self._theme_set_value("cloud_shader_shadow_strength", 0.54)
            self._theme_set_value("cloud_shader_bloom_strength", 0.38)
            self._theme_set_value("cloud_shader_contrast", 0.60)
            self._theme_set_checked("cloud_mist_enabled", False)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
        elif theme_id in ("suzhou_humble_garden", "suzhou_zhumyoen", "setsuseien", "humble_administrator_garden"):
            # 拙政園のようなゆったり感: 開けた水辺、淡い雲、薄い朝もや、少数の花びら。
            self._theme_disable_all_visual_effects()
            self._theme_apply_common_lightweight(fps=36, quality=0.82)
            self._theme_set_extra("cloud", enabled=True, count=10, speed=0.8650, size=124.0, alpha=118)
            self._theme_set_text("cloud_color", "#EEF7F4")
            self._theme_set_text("cloud_shadow_color", "#C8D9D4")
            self._theme_set_text("cloud_highlight_color", "#FFFFFF")
            self._theme_set_value("cloud_altitude", 0.24)
            self._theme_set_value("cloud_depth", 0.43)
            self._theme_set_value("cloud_softness", 0.88)
            self._theme_set_value("cloud_shape_randomness", 0.58)
            self._theme_set_value("cloud_volume_strength", 0.66)
            self._theme_set_checked("cloud_mist_enabled", True)
            self._theme_set_value("cloud_mist_density", 0.64)
            self._theme_set_value("cloud_mist_stretch", 1.92)
            self._theme_set_value("cloud_mist_translucency", 0.90)
            self._theme_set_checked("cloud_cache_enabled", True)
            self._theme_set_value("cloud_cache_quality_scale", 0.62)
            self._theme_set_checked("cloud_cumulus_enabled", False)
            self._theme_set_checked("cloud_shader_lighting_enabled", True)
            self._theme_set_value("cloud_shader_warmth", 0.28)
            self._theme_set_value("cloud_shader_rim_strength", 0.42)
            self._theme_set_value("cloud_shader_shadow_strength", 0.26)
            self._theme_set_value("cloud_shader_bloom_strength", 0.20)
            self._theme_set_value("cloud_shader_contrast", 0.26)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_checked("puddle_enabled", True)
            self._theme_set_value("puddle_x", 0.50)
            self._theme_set_value("puddle_y", 0.82)
            self._theme_set_value("puddle_width", 0.82)
            self._theme_set_value("puddle_height", 0.24)
            self._theme_set_value("puddle_edge_softness", 0.36)
            self._theme_set_value("puddle_count", 2)
            self._theme_set_value("puddle_spread", 0.46)
            self._theme_set_value("water_surface_alpha", 58)
            self._theme_set_text("water_surface_color", "#D9F2EC")
            self._theme_set_text("water_surface_highlight_color", "#F2FFFA")
            self._theme_set_value("water_surface_flow_angle", 2.0)
            self._theme_set_value("water_surface_flow_speed", 0.16)
            self._theme_set_value("water_surface_wave_count", 5)
            self._theme_set_value("water_surface_wave_height", 5.5)
            self._theme_set_value("water_surface_y", 0.60)
            self._theme_set_value("water_surface_depth", 0.33)
            self._theme_set_checked("water_depth_enabled", True)
            self._theme_set_value("water_depth_strength", 0.46)
            self._theme_set_value("water_depth_haze_alpha", 36)
            self._theme_set_text("water_depth_color", "#678F86")
            self._theme_set_checked("water_morning_fog_enabled", True)
            self._theme_set_checked("water_morning_fog_follow_sunrise", False)
            self._theme_set_value("water_morning_fog_strength", 0.54)
            self._theme_set_value("water_morning_fog_alpha", 62)
            self._theme_set_value("water_morning_fog_height", 0.18)
            self._theme_set_value("water_morning_fog_drift", 0.18)
            self._theme_set_text("water_morning_fog_color", "#EEF8F3")
            self._theme_set_checked("water_fish_enabled", True)
            self._theme_set_value("water_fish_count", 2)
            self._theme_set_value("water_fish_speed", 0.16)
            self._theme_set_value("water_fish_size", 20.0)
            self._theme_set_value("water_fish_alpha", 92)
            self._theme_set_checked("water_mirror_enabled", True)
            self._theme_set_value("water_mirror_alpha", 36)
            self._theme_set_value("water_mirror_blur", 8.0)
            self._theme_set_value("water_mirror_wave", 3.0)
            self._theme_set_value("water_mirror_tint_alpha", 28)
            self._theme_set_checked("water_mirror_reflect_widgets_enabled", True)
            self._theme_set_checked("water_mirror_reflect_effects_enabled", True)
            self._theme_set_checked("water_mirror_reflect_cloud", True)
            self._theme_set_checked("water_mirror_reflect_bamboo", False)
            self._theme_set_checked("water_mirror_reflect_rain", False)
            self._theme_set_checked("rose_petals_enabled", True)
            self._theme_set_value("rose_petal_count", 8)
            self._theme_set_text("rose_petal_color", "#F3C9C2")
            self._theme_set_text("rose_petal_edge_color", "#FFF1EA")
            self._theme_set_value("rose_petal_speed", 0.10)
            self._theme_set_value("rose_petal_sway", 0.72)
            self._theme_set_value("rose_petal_size", 13.5)
            self._theme_set_value("rose_petal_alpha", 82)
            self._theme_set_checked("rose_petal_ripple_enabled", True)
            self._theme_set_value("rose_petal_ripple_chance", 0.24)
            self._theme_set_value("rose_petal_ripple_min_radius", 28.0)
            self._theme_set_value("rose_petal_ripple_max_radius", 105.0)
            self._theme_set_value("rose_petal_ripple_cooldown", 0.12)
            self._theme_set_checked("rose_petal_fade_on_surface", True)
            self._theme_set_value("rose_petal_fade_duration", 1.65)
            self._theme_set_value("rose_petal_fade_sink_distance", 4.0)
            self._theme_set_checked("ripple_enabled", True)
            self._theme_set_value("ripple_speed", 0.36)
            self._theme_set_value("ripple_max_radius", 155.0)
            self._theme_set_value("intensity", 0.72)
            self._theme_set_value("background_alpha", 0)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
        elif theme_id in ("suzhou_lingering_garden", "suzhou_ryuen", "liuyuan", "lingering_garden"):
            # 留園のような落ち着く感じ: 竹・深い緑・静かな水鏡を中心にする。
            self._theme_disable_all_visual_effects()
            self._theme_apply_common_lightweight(fps=32, quality=0.78)
            self._theme_set_checked("bamboo_grove_enabled", True)
            self._theme_set_value("bamboo_count", 18)
            self._theme_set_value("bamboo_thickness", 13.2)
            self._theme_set_value("bamboo_angle", -1.2)
            self._theme_set_value("bamboo_bend", 0.22)
            self._theme_set_value("bamboo_height", 1.05)
            self._theme_set_value("bamboo_alpha", 208)
            self._theme_set_value("bamboo_leaf_density", 4)
            self._theme_set_value("bamboo_depth_strength", 1.10)
            self._theme_set_value("bamboo_layer_spread", 0.56)
            self._theme_set_value("bamboo_highlight_alpha", 58)
            self._theme_set_checked("bamboo_ground_shadow_enabled", True)
            self._theme_set_checked("bamboo_atmosphere_enabled", True)
            self._theme_set_text("bamboo_stalk_color", "#2E7450")
            self._theme_set_text("bamboo_shadow_color", "#183D2C")
            self._theme_set_text("bamboo_node_color", "#9ABF75")
            self._theme_set_text("bamboo_leaf_color", "#5E9F69")
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_checked("puddle_enabled", True)
            self._theme_set_value("puddle_x", 0.50)
            self._theme_set_value("puddle_y", 0.84)
            self._theme_set_value("puddle_width", 0.74)
            self._theme_set_value("puddle_height", 0.22)
            self._theme_set_value("puddle_edge_softness", 0.38)
            self._theme_set_value("puddle_count", 2)
            self._theme_set_value("puddle_spread", 0.42)
            self._theme_set_value("water_surface_alpha", 54)
            self._theme_set_text("water_surface_color", "#CFEADF")
            self._theme_set_text("water_surface_highlight_color", "#EFFFF8")
            self._theme_set_value("water_surface_flow_angle", -4.0)
            self._theme_set_value("water_surface_flow_speed", 0.11)
            self._theme_set_value("water_surface_wave_count", 4)
            self._theme_set_value("water_surface_wave_height", 4.2)
            self._theme_set_value("water_surface_y", 0.62)
            self._theme_set_value("water_surface_depth", 0.40)
            self._theme_set_checked("water_depth_enabled", True)
            self._theme_set_value("water_depth_strength", 0.72)
            self._theme_set_value("water_depth_haze_alpha", 44)
            self._theme_set_text("water_depth_color", "#244D42")
            self._theme_set_checked("water_morning_fog_enabled", True)
            self._theme_set_checked("water_morning_fog_follow_sunrise", False)
            self._theme_set_value("water_morning_fog_strength", 0.46)
            self._theme_set_value("water_morning_fog_alpha", 48)
            self._theme_set_value("water_morning_fog_height", 0.16)
            self._theme_set_value("water_morning_fog_drift", 0.10)
            self._theme_set_text("water_morning_fog_color", "#E6F4EC")
            self._theme_set_checked("water_fish_enabled", True)
            self._theme_set_value("water_fish_count", 1)
            self._theme_set_value("water_fish_speed", 0.11)
            self._theme_set_value("water_fish_size", 18.0)
            self._theme_set_value("water_fish_alpha", 74)
            self._theme_set_checked("water_mirror_enabled", True)
            self._theme_set_value("water_mirror_alpha", 72)
            self._theme_set_value("water_mirror_blur", 11.0)
            self._theme_set_value("water_mirror_depth", 0.70)
            self._theme_set_value("water_mirror_wave", 2.4)
            self._theme_set_value("water_mirror_tint_alpha", 42)
            self._theme_set_checked("water_mirror_reflect_widgets_enabled", True)
            self._theme_set_checked("water_mirror_reflect_effects_enabled", True)
            self._theme_set_checked("water_mirror_reflect_bamboo", True)
            self._theme_set_checked("water_mirror_reflect_cloud", False)
            self._theme_set_checked("water_mirror_reflect_rain", False)
            self._theme_set_checked("rose_petals_enabled", True)
            self._theme_set_value("rose_petal_count", 4)
            self._theme_set_text("rose_petal_color", "#D8B4A2")
            self._theme_set_text("rose_petal_edge_color", "#F4DED1")
            self._theme_set_value("rose_petal_speed", 0.075)
            self._theme_set_value("rose_petal_sway", 0.38)
            self._theme_set_value("rose_petal_size", 11.5)
            self._theme_set_value("rose_petal_alpha", 46)
            self._theme_set_checked("rose_petal_ripple_enabled", True)
            self._theme_set_value("rose_petal_ripple_chance", 0.16)
            self._theme_set_value("rose_petal_ripple_min_radius", 22.0)
            self._theme_set_value("rose_petal_ripple_max_radius", 82.0)
            self._theme_set_value("rose_petal_ripple_cooldown", 0.18)
            self._theme_set_checked("rose_petal_fade_on_surface", True)
            self._theme_set_value("rose_petal_fade_duration", 2.0)
            self._theme_set_value("rose_petal_fade_sink_distance", 3.0)
            self._theme_set_checked("ripple_enabled", True)
            self._theme_set_value("ripple_speed", 0.28)
            self._theme_set_value("ripple_max_radius", 118.0)
            self._theme_set_value("intensity", 0.60)
            self._theme_set_value("background_alpha", 0)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass
        elif theme_id in ("uyuni_salt_flat_reflection", "uyuni_salt_flat", "salar_de_uyuni"):
            # ウユニ塩湖: 反射背景に加えて、既存の水面・薄い氷/塩結晶エフェクトもONにする。
            self._theme_apply_60fps_scenic_foundation(fps=45, cache_fps=45)
            self._theme_clear_scenic_engine_flags()
            self._theme_set_raw_extra("uyuni_salt_flat_engine_enabled", True)
            self._theme_set_raw_extra("realtime_scenic_sky_enabled", True)
            self._theme_set_raw_extra("realtime_scenic_sun_rays_enabled", False)
            self._theme_set_raw_extra("desktop_ui_aware_rendering_enabled", False)
            self._theme_set_raw_extra("desktop_ui_mask_padding", 24)
            self._theme_set_raw_extra("desktop_ui_mask_blur", 37)
            self._theme_set_raw_extra("desktop_ui_icon_remaining_alpha", 0.12)
            self._theme_set_raw_extra("desktop_ui_mask_refresh_sec", 1.0)
            self._theme_set_raw_extra("desktop_ui_fallback_strip_enabled", True)
            self._theme_set_raw_extra("desktop_ui_fallback_width_ratio", 0.22)
            self._theme_set_raw_extra("antelope_canyon_engine_enabled", False)
            self._theme_set_value("intensity", 0.82)
            self._theme_set_value("vector_image_cache_fps", 6)
            self._theme_set_value("vector_image_cache_fps_extra", 120)
            self._theme_set_checked("water_surface_enabled", True)
            self._theme_set_checked("puddle_enabled", False)
            self._theme_set_value("water_surface_alpha", 52)
            self._theme_set_text("water_surface_color", "#EAFBFF")
            self._theme_set_text("water_surface_highlight_color", "#FFFFFF")
            self._theme_set_value("water_surface_flow_angle", 0.0)
            self._theme_set_value("water_surface_flow_speed", 0.035)
            self._theme_set_value("water_surface_wave_count", 4)
            self._theme_set_value("water_surface_wave_height", 1.8)
            self._theme_set_value("water_surface_y", 0.50)
            self._theme_set_value("water_surface_depth", 0.50)
            self._theme_set_checked("water_depth_enabled", True)
            self._theme_set_value("water_depth_strength", 0.28)
            self._theme_set_value("water_depth_haze_alpha", 22)
            self._theme_set_text("water_depth_color", "#D6F4FF")
            self._theme_set_checked("water_mirror_enabled", True)
            self._theme_set_value("water_mirror_alpha", 46)
            self._theme_set_value("water_mirror_blur", 7.5)
            self._theme_set_value("water_mirror_depth", 0.72)
            self._theme_set_value("water_mirror_wave", 1.2)
            self._theme_set_value("water_mirror_tint_alpha", 18)
            self._theme_set_checked("water_mirror_reflect_widgets_enabled", True)
            self._theme_set_checked("water_mirror_reflect_effects_enabled", True)
            self._theme_set_checked("ice_enabled", True)
            self._theme_set_checked("ice_lightweight_enabled", True)
            self._theme_set_checked("ice_static_cache_enabled", True)
            self._theme_set_value("ice_quality_scale", 0.42)
            self._theme_set_value("ice_max_facets", 20)
            self._theme_set_value("ice_max_cracks", 4)
            self._theme_set_value("ice_max_bubbles", 0)
            self._theme_set_value("ice_alpha", 36)
            self._theme_set_text("ice_color", "#F7FFFF")
            self._theme_set_text("ice_edge_color", "#FFFFFF")
            self._theme_set_text("ice_highlight_color", "#FFFFFF")
            self._theme_set_text("ice_shadow_color", "#CFEFFF")
            self._theme_set_value("ice_x", 0.50)
            self._theme_set_value("ice_width", 1.00)
            self._theme_set_value("ice_y", 0.50)
            self._theme_set_value("ice_depth", 0.50)
            self._theme_set_value("ice_crack_intensity", 0.08)
            self._theme_set_value("ice_internal_bubble_intensity", 0.0)
            self._theme_set_value("ice_glacier_roughness", 0.12)
            self._theme_set_checked("ice_mirror_enabled", False)
            self._theme_set_checked("ice_fog_enabled", False)
            self._theme_set_extra("cloud", enabled=True, count=6, speed=0.8650, size=112.0, alpha=176)
            self._theme_set_checked("water_mirror_reflect_cloud", True)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "1"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "on"
            except:
                pass
        elif theme_id in ("antelope_canyon_depth", "antelope_canyon", "warm_canyon_depth"):
            # アンテロープキャニオン: 背景はQImage静的レンダリング。既存水面/氷はOFFのまま。
            self._theme_apply_60fps_scenic_foundation(fps=60, cache_fps=8)
            self._theme_clear_scenic_engine_flags()
            self._theme_set_raw_extra("uyuni_salt_flat_engine_enabled", False)
            self._theme_set_raw_extra("antelope_canyon_engine_enabled", True)
            self._theme_set_raw_extra("desktop_ui_aware_rendering_enabled", False)
            self._theme_set_raw_extra("desktop_ui_mask_padding", 24)
            self._theme_set_raw_extra("desktop_ui_mask_blur", 37)
            self._theme_set_raw_extra("desktop_ui_icon_remaining_alpha", 0.12)
            self._theme_set_raw_extra("desktop_ui_mask_refresh_sec", 1.0)
            self._theme_set_raw_extra("desktop_ui_fallback_strip_enabled", True)
            self._theme_set_raw_extra("desktop_ui_fallback_width_ratio", 0.22)
            self._theme_set_value("intensity", 0.94)
            self._theme_set_value("vector_image_cache_fps", 8)
            self._theme_set_value("vector_image_cache_fps_extra", 120)
            try:
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "1"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "on"
            except:
                pass
        elif theme_id in ("pamukkale_terrace_lake", "pamukkale", "pamukkale_lake"):
            self._theme_select_fullscreen_scenic_engine("pamukkale_terrace_lake_engine_enabled", fps=60, cache_fps=8, intensity=0.84)
        elif theme_id in ("blue_hole_deep_lake", "blue_hole", "deep_blue_hole"):
            self._theme_select_fullscreen_scenic_engine("blue_hole_deep_lake_engine_enabled", fps=60, cache_fps=8, intensity=0.92)
        elif theme_id in ("chichibugahama_mirror", "chichibugahama", "mirror_beach"):
            self._theme_select_fullscreen_scenic_engine("chichibugahama_mirror_engine_enabled", fps=45, cache_fps=45, intensity=0.84)
            self._theme_set_raw_extra("scenic_atmosphere_enhancement_enabled", True)
            self._theme_set_extra("cloud", enabled=True, count=5, speed=0.8650, size=104.0, alpha=158)
            self._theme_set_checked("water_mirror_reflect_cloud", True)
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
                os.environ["LITEDESKTOPSTUDIO_ICON_SCENE_RENDER_ICONS"] = "0"
            except:
                pass

            try:
                globals()["_LDS_ICON_FOREGROUND_LAYER_CACHE"] = {
                    "key": None,
                    "image": None,
                }
            except:
                pass

            try:
                globals()["_LDS_ICON_SCENE_ACTIVE_PROFILE"] = "default"
            except:
                pass
            try:
                if hasattr(self, "cfg") and isinstance(self.cfg, dict):
                    self.cfg["icon_scene_render_icons"] = "off"
            except:
                pass

        try:
            self.apply_to_config()
        except:
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
            vector_image_cache_enabled=self.vector_image_cache_enabled.isChecked(),
            vector_image_cache_fps=self.vector_image_cache_fps.value(),
            vector_image_cache_fps_extra=self.vector_image_cache_fps_extra.value(),
            vector_image_cache_fps_rain=self.vector_image_cache_fps_rain.value(),
            vector_image_cache_fps_ripples=self.vector_image_cache_fps_ripples.value(),
            vector_image_cache_fps_particles=self.vector_image_cache_fps_particles.value(),
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
            cloud_enabled=self.cloud_enabled.isChecked(),
            cloud_count=self.cloud_count.value(),
            cloud_speed=self.cloud_speed.value(),
            cloud_size=self.cloud_size.value(),
            cloud_alpha=self.cloud_alpha.value(),
            cloud_color=self.cloud_color.text().strip() or "#F4FAFF",
            cloud_shadow_color=self.cloud_shadow_color.text().strip() or "#B8C7D8",
            cloud_highlight_color=self.cloud_highlight_color.text().strip() or "#FFFFFF",
            cloud_altitude=self.cloud_altitude.value(),
            cloud_depth=self.cloud_depth.value(),
            cloud_softness=self.cloud_softness.value(),
            cloud_shape_randomness=self.cloud_shape_randomness.value(),
            cloud_volume_strength=self.cloud_volume_strength.value(),
            cloud_mist_enabled=self.cloud_mist_enabled.isChecked(),
            cloud_mist_density=self.cloud_mist_density.value(),
            cloud_mist_stretch=self.cloud_mist_stretch.value(),
            cloud_mist_translucency=self.cloud_mist_translucency.value(),
            cloud_cache_enabled=self.cloud_cache_enabled.isChecked(),
            cloud_cache_quality_scale=self.cloud_cache_quality_scale.value(),
            cloud_cache_max_items=self.cloud_cache_max_items.value(),
            cloud_cumulus_enabled=self.cloud_cumulus_enabled.isChecked(),
            cloud_cumulus_fluffiness=self.cloud_cumulus_fluffiness.value(),
            cloud_cumulus_tower_strength=self.cloud_cumulus_tower_strength.value(),
            cloud_shader_lighting_enabled=self.cloud_shader_lighting_enabled.isChecked(),
            cloud_shader_sun_angle=self.cloud_shader_sun_angle.value(),
            cloud_shader_warmth=self.cloud_shader_warmth.value(),
            cloud_shader_rim_strength=self.cloud_shader_rim_strength.value(),
            cloud_shader_shadow_strength=self.cloud_shader_shadow_strength.value(),
            cloud_shader_bloom_strength=self.cloud_shader_bloom_strength.value(),
            cloud_shader_contrast=self.cloud_shader_contrast.value(),
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
            water_mirror_reflect_cloud=self.water_mirror_reflect_cloud.isChecked(),
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
            ice_reflect_cloud=self.ice_reflect_cloud.isChecked(),
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
        try:
            extra = dict(getattr(self, "_theme_extra_settings", {}) or {})
        except:
            extra = {}
        if extra:
            ensure_effect_overlay_fields(self.cfg)
            data = settings.to_dict()
            data.update(extra)
            self.cfg.effects_json = json.dumps(data, ensure_ascii=False)
        else:
            set_effect_overlay_settings(self.cfg, settings)

        try:
            if hasattr(self.widget, "clear_vector_image_cache"):
                self.widget.clear_vector_image_cache()
        except:
            pass

        try:
            if hasattr(self.widget, "clear_scenic_engine_cache"):
                self.widget.clear_scenic_engine_cache()
        except:
            pass

        try:
            if hasattr(self.widget, "clear_sahara_desert_cache"):
                self.widget.clear_sahara_desert_cache()
        except:
            pass

        try:
            self.widget._particles.clear()
            self.widget._rain.clear()
            self.widget._ripples.clear()
            self.widget._rose_petals.clear()
            self.widget._extra_effects.clear()
        except:
            pass

        try:
            self.widget._last_petal_ripple_time = 0.0
        except:
            pass
        try:
            self.widget._rose_petals.clear()
        except:
            pass

        try:
            self.widget._last_petal_ripple_time = 0.0
        except:
            pass
        try:
            self.widget._rose_flowers.clear()
        except:
            pass
        try:
            self.widget._blooming_roses.clear()
        except:
            pass
        try:
            self.widget._rose_petals.clear()
        except:
            pass
        try:
            self.widget._last_flower_ripple_time = 0.0
        except:
            pass
        try:
            self.widget._sakura_petals.clear()
        except:
            pass
        try:
            self.widget._last_sakura_ripple_time = 0.0
            self.widget._last_sakura_tree_emit_time = 0.0
        except:
            pass
        try:
            if hasattr(self.widget, "_extra_effects"):
                self.widget._extra_effects.clear()
            self.widget._last_extra_ripple_time = 0.0
        except:
            pass
        try:
            if hasattr(self.widget, "_sun_effect_render_cache"):
                self.widget._sun_effect_render_cache.clear()
                self.widget._sun_effect_render_cache_order.clear()
        except:
            pass
        try:
            if hasattr(self.widget, "_ice_surface_cache_signature"):
                self.widget._ice_surface_cache_signature = None
                self.widget._ice_surface_cache_image = None
                self.widget._ice_reflected_effects_cache_signature = None
                self.widget._ice_reflected_effects_cache_image = None
        except:
            pass
        try:
            if hasattr(self.widget, "_water_fish"):
                self.widget._water_fish.clear()
            self.widget._water_fish_rect_key = None
            self.widget._last_water_fish_update = 0.0
        except:
            pass
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "canvas"):
                parent.canvas.save_config()
                parent.canvas.update()
        except:
            pass

    def accept_with_apply(self):
        self.apply_to_config()
        self.accept()
