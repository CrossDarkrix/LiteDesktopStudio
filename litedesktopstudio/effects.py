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
    "vector_image_cache_enabled": True,
    "vector_image_cache_fps": 24,
    "vector_image_cache_fps_extra": 45,
    "vector_image_cache_fps_rain": 24,
    "vector_image_cache_fps_ripples": 18,
    "vector_image_cache_fps_particles": 18,

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
    "snow_ripple_enabled": False,
    "snow_ripple_chance": 0.38,
    "snow_surface_y": 0.86,
    "snow_accumulation_enabled": False,
    "snow_accumulation_start_y": 1.0,
    "snow_accumulation_max_depth": 1.0,
    "snow_accumulation_build_rate": 7.0,
    "snow_accumulation_column_width": 7.0,
    "snow_accumulation_alpha": 230,
    "snow_accumulation_mouse_remove_enabled": False,
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
    "snow_crystal_ripple_enabled": False,
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
    "cloud_enabled": False,
    "cloud_count": 13,
    "cloud_speed": 1.050,
    "cloud_size": 120.0,
    "cloud_alpha": 200,
    "cloud_color": "#F4FAFF",
    "cloud_shadow_color": "#B8C7D8",
    "cloud_highlight_color": "#FFFFFF",
    "cloud_altitude": 0.22,
    "cloud_depth": 0.42,
    "cloud_softness": 0.72,
    "cloud_shape_randomness": 0.85,
    "cloud_volume_strength": 0.90,
    "cloud_mist_enabled": True,
    "cloud_mist_density": 0.52,
    "cloud_mist_stretch": 1.55,
    "cloud_mist_translucency": 0.86,
    "cloud_cache_enabled": True,
    "cloud_cache_quality_scale": 0.62,
    "cloud_cache_max_items": 96,
    "cloud_cumulus_enabled": False,
    "cloud_cumulus_fluffiness": 0.88,
    "cloud_cumulus_tower_strength": 0.72,
    "cloud_shader_lighting_enabled": True,
    "cloud_shader_sun_angle": -55.0,
    "cloud_shader_warmth": 0.42,
    "cloud_shader_rim_strength": 0.78,
    "cloud_shader_shadow_strength": 0.52,
    "cloud_shader_bloom_strength": 0.36,
    "cloud_shader_contrast": 0.58,
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
    "water_depth_enabled": False,
    "water_depth_strength": 0.75,
    "water_depth_haze_alpha": 48,
    "water_depth_color": "#1A5B70",
    "water_morning_fog_enabled": False,
    "water_morning_fog_follow_sunrise": False,
    "water_morning_fog_strength": 0.65,
    "water_morning_fog_alpha": 95,
    "water_morning_fog_height": 0.22,
    "water_morning_fog_drift": 0.35,
    "water_morning_fog_color": "#E9F6FF",
    "water_fish_enabled": False,
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
    "water_mirror_reflect_effects_enabled": False,
    "water_mirror_reflect_widgets_enabled": False,
    "water_mirror_reflect_snow": False,
    "water_mirror_reflect_snow_crystal": False,
    "water_mirror_reflect_petals": False,
    "water_mirror_reflect_bamboo": False,
    "water_mirror_reflect_shooting_star": False,
    "water_mirror_reflect_meteor_shower": False,
    "water_mirror_reflect_rain": False,
    "water_mirror_reflect_cloud": False,
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
    "ice_lightweight_enabled": False,
    "ice_static_cache_enabled": False,
    "ice_quality_scale": 0.58,
    "ice_max_facets": 72,
    "ice_max_cracks": 16,
    "ice_max_bubbles": 34,
    "ice_skip_reflected_effect_frames": 2,
    "ice_mirror_skip_frames": 2,
    "ice_x": 0.50,
    "ice_width": 1.00,
    "ice_reflect_widgets_enabled": False,
    "ice_reflect_snow": False,
    "ice_reflect_snow_crystal": False,
    "ice_reflect_petals": False,
    "ice_reflect_bamboo": False,
    "ice_reflect_shooting_star": False,
    "ice_reflect_meteor_shower": False,
    "ice_reflect_rain": False,
    "ice_reflect_cloud": False,
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
    "ice_mirror_enabled": False,
    "ice_mirror_alpha": 118,
    "ice_mirror_blur": 3.5,
    "ice_mirror_depth": 0.68,
    "ice_mirror_wave": 2.2,
    "ice_mirror_tint_alpha": 70,
    "ice_reflect_effects_enabled": False,
    "ice_fog_enabled": False,
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
    "bamboo_ground_shadow_enabled": False,
    "bamboo_atmosphere_enabled": False,
    "bamboo_stalk_color": "#3EA65A",
    "bamboo_shadow_color": "#1F6F3B",
    "bamboo_node_color": "#B7E37A",
    "bamboo_leaf_color": "#5ED06C",
    "water_drop_enabled": False,
    "water_drop_count": 55,
    "water_drop_speed": 0.48,
    "water_drop_size": 8.0,
    "water_drop_alpha": 210,
    "water_drop_ripple_enabled": False,
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
    "sun_shader_realistic_enabled": True,
    "sun_effect_cache_enabled": True,
    "sun_effect_cache_quality_scale": 0.58,
    "sun_effect_cache_max_items": 32,
    "sun_halo_outer_scale": 3.35,
    "sun_corona_ray_count": 18,
    "sun_lens_ghost_strength": 0.78,
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
    "moonlight_beam_enabled": False,
    "moonlight_beam_alpha": 44,
    "moonlight_beam_width": 0.34,
    "moon_shadow_alpha": 70,
    "moon_shadow_color": "#061028",
    "moon_shadow_offset_x": 28.0,
    "moon_shadow_offset_y": 38.0,
    "moon_shadow_angle": 0.0,
    "moon_shadow_blur_radius": 150.0,
}


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
    vector_image_cache_enabled: bool = True
    vector_image_cache_fps: int = 24
    vector_image_cache_fps_extra: int = 12
    vector_image_cache_fps_rain: int = 24
    vector_image_cache_fps_ripples: int = 18
    vector_image_cache_fps_particles: int = 18

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
    # Sildur's Vibrant shaders inspired cached sun rendering.
    # These defaults keep the existing UI compatible while enabling a richer, lighter path.
    sun_shader_realistic_enabled: bool = True
    sun_effect_cache_enabled: bool = True
    sun_effect_cache_quality_scale: float = 0.58
    sun_effect_cache_max_items: int = 32
    sun_halo_outer_scale: float = 3.35
    sun_corona_ray_count: int = 18
    sun_lens_ghost_strength: float = 0.78
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
    cloud_enabled: bool = False
    cloud_count: int = 9
    cloud_speed: float = 0.075
    cloud_size: float = 92.0
    cloud_alpha: int = 185
    cloud_color: str = "#F4FAFF"
    cloud_shadow_color: str = "#B8C7D8"
    cloud_highlight_color: str = "#FFFFFF"
    cloud_altitude: float = 0.22
    cloud_depth: float = 0.42
    cloud_softness: float = 0.72
    cloud_shape_randomness: float = 0.85
    cloud_volume_strength: float = 0.90
    cloud_mist_enabled: bool = True
    cloud_mist_density: float = 0.52
    cloud_mist_stretch: float = 1.55
    cloud_mist_translucency: float = 0.86
    cloud_cache_enabled: bool = True
    cloud_cache_quality_scale: float = 0.62
    cloud_cache_max_items: int = 96
    cloud_cumulus_enabled: bool = True
    cloud_cumulus_fluffiness: float = 0.88
    cloud_cumulus_tower_strength: float = 0.72
    cloud_shader_lighting_enabled: bool = True
    cloud_shader_sun_angle: float = -55.0
    cloud_shader_warmth: float = 0.42
    cloud_shader_rim_strength: float = 0.78
    cloud_shader_shadow_strength: float = 0.52
    cloud_shader_bloom_strength: float = 0.36
    cloud_shader_contrast: float = 0.58
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
    water_mirror_reflect_cloud: bool = True
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
    ice_reflect_cloud: bool = True
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
    except:
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
        effect_frame_rate=max(1, min(240, int(defaults.get("effect_frame_rate", 40)))),
        vector_image_cache_enabled=bool(defaults.get("vector_image_cache_enabled", True)),
        vector_image_cache_fps=max(1, min(60, int(defaults.get("vector_image_cache_fps", 24)))),
        vector_image_cache_fps_extra=max(1, min(60, int(defaults.get("vector_image_cache_fps_extra", 12)))),
        vector_image_cache_fps_rain=max(1, min(60, int(defaults.get("vector_image_cache_fps_rain", 24)))),
        vector_image_cache_fps_ripples=max(1, min(60, int(defaults.get("vector_image_cache_fps_ripples", 18)))),
        vector_image_cache_fps_particles=max(1, min(60, int(defaults.get("vector_image_cache_fps_particles", 18)))),
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
        cloud_enabled=bool(defaults.get("cloud_enabled", False)),
        cloud_count=max(0, int(defaults.get("cloud_count", 9))),
        cloud_speed=float(defaults.get("cloud_speed", 0.075)),
        cloud_size=float(defaults.get("cloud_size", 92.0)),
        cloud_alpha=max(0, min(255, int(defaults.get("cloud_alpha", 185)))),
        cloud_color=str(defaults.get("cloud_color", "#F4FAFF")),
        cloud_shadow_color=str(defaults.get("cloud_shadow_color", "#B8C7D8")),
        cloud_highlight_color=str(defaults.get("cloud_highlight_color", "#FFFFFF")),
        cloud_altitude=max(0.0, min(1.0, float(defaults.get("cloud_altitude", 0.22)))),
        cloud_depth=max(0.0, min(1.0, float(defaults.get("cloud_depth", 0.42)))),
        cloud_softness=max(0.0, min(1.0, float(defaults.get("cloud_softness", 0.72)))),
        cloud_shape_randomness=max(0.0, min(1.0, float(defaults.get("cloud_shape_randomness", 0.85)))),
        cloud_volume_strength=max(0.0, min(1.0, float(defaults.get("cloud_volume_strength", 0.90)))),
        cloud_mist_enabled=bool(defaults.get("cloud_mist_enabled", True)),
        cloud_mist_density=max(0.0, min(1.0, float(defaults.get("cloud_mist_density", 0.52)))),
        cloud_mist_stretch=max(0.5, min(3.0, float(defaults.get("cloud_mist_stretch", 1.55)))),
        cloud_mist_translucency=max(0.1, min(1.0, float(defaults.get("cloud_mist_translucency", 0.86)))),
        cloud_cache_enabled=bool(defaults.get("cloud_cache_enabled", True)),
        cloud_cache_quality_scale=max(0.25, min(1.0, float(defaults.get("cloud_cache_quality_scale", 0.62)))),
        cloud_cache_max_items=max(8, min(512, int(defaults.get("cloud_cache_max_items", 96)))),
        cloud_cumulus_enabled=bool(defaults.get("cloud_cumulus_enabled", True)),
        cloud_cumulus_fluffiness=max(0.0, min(1.0, float(defaults.get("cloud_cumulus_fluffiness", 0.88)))),
        cloud_cumulus_tower_strength=max(0.0, min(1.0, float(defaults.get("cloud_cumulus_tower_strength", 0.72)))),
        cloud_shader_lighting_enabled=bool(defaults.get("cloud_shader_lighting_enabled", True)),
        cloud_shader_sun_angle=max(-180.0, min(180.0, float(defaults.get("cloud_shader_sun_angle", -55.0)))),
        cloud_shader_warmth=max(0.0, min(1.0, float(defaults.get("cloud_shader_warmth", 0.42)))),
        cloud_shader_rim_strength=max(0.0, min(1.0, float(defaults.get("cloud_shader_rim_strength", 0.78)))),
        cloud_shader_shadow_strength=max(0.0, min(1.0, float(defaults.get("cloud_shader_shadow_strength", 0.52)))),
        cloud_shader_bloom_strength=max(0.0, min(1.0, float(defaults.get("cloud_shader_bloom_strength", 0.36)))),
        cloud_shader_contrast=max(0.0, min(1.0, float(defaults.get("cloud_shader_contrast", 0.58)))),
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
        water_mirror_reflect_cloud=bool(defaults.get("water_mirror_reflect_cloud", True)),
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
        ice_reflect_cloud=bool(defaults.get("ice_reflect_cloud", True)),
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
