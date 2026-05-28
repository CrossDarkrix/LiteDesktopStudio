<div align="center">
	<a href="https://github.com/CrossDarkrix/LiteDesktopStudio">
	<img width="150px" height="150px" alt="LiteDesktopStudio" src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/icon.png"></a>
</div>
<h2 align="center">Lite Desktop Studio</h2>
<p align="center">A Simple Desktop Gadet.</p>

[日本語 README](README_ja.md)

LiteDesktopStudio is a lightweight desktop gadget studio built with Python and PySide6. It lets you place, edit, and customize desktop widgets such as music visualizers, system meters, network monitors, clocks, calendars, weather panels, media controls, HTML-style widgets, and JavaScript HTML widgets.

I also develop Artifacter and LiteDesktopStudio, but I do not have much spare time for development. If you would like to support continued development, donations are welcome: [Buy me a coffee](https://www.buymeacoffee.com/crossdarkrix)

## Screenshots

<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot1.png" width="300px" height="250px"></a>
<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot2.png" width="300px" height="250px"></a>
<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot3.png" width="300px" height="250px"></a>
<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot4.png" width="300px" height="250px"></a>


## Features

- **Freely place widgets on your desktop**  
  Place widgets anywhere on your desktop and adjust their position and size.

- **Intuitive edit mode**  
  Open the settings screen by quickly right-clicking twice. Select a widget with the left mouse button and press `E` to toggle placement editing.

- **Detailed visual customization**  
  Customize opacity, background color, accent color, size, position, and other widget settings.

- **Settings screen themes**  
  Switch between styles such as Liquid Glass, Dark, Material, and Light.

- **Music-reactive visualizer**  
  Display spectrum bars that react to currently playing audio, with optional peak bars and glow effects.

- **System and network widgets**  
  Display CPU, memory, disk, upload/download speeds, and network history graphs.

- **Desktop effect overlays**  
  Add visual overlays such as rain, particles, glow, ripples, rose petals, cherry blossoms, snow, water, fire, and shooting stars.

- **HTML/CSS-style widgets**  
  Create simple custom panels for notes, links, decorations, or personal information displays.

- **JavaScript HTML widgets**  
  Use Qt WebEngine-based widgets for richer HTML, CSS, and JavaScript experiences.

- **JSHTML Audio API**  
  JSHTML package widgets can build audio-reactive interfaces using LiteDesktopStudio's cached audio spectrum data.

- **Other Tools window**  
  v2.1.2 adds a dedicated tools window for JSHTML package building, image conversion, HTML/JSON/JavaScript editing, and diagnostics.

- **Easy to customize**  
  LiteDesktopStudio is implemented with Python and PySide6, so users who can read the source code can add widgets, modify behavior, or extend settings.

## JavaScript HTML Widget Runtime

LiteDesktopStudio includes an enhanced JavaScript HTML widget runtime. JSHTML widgets can run as quick inline HTML snippets or as ZIP-imported package widgets with their own directory, assets, persistent settings, and JavaScript API bridge.

### JSHTML modes

| Mode | Description |
|---|---|
| `inline` | Uses the HTML stored directly in the widget text field. Good for quick experiments and small custom panels. |
| `package` | Loads a ZIP-imported widget package from a dedicated per-widget directory. Packages can include `widget.json`, `index.html`, CSS, JavaScript, and assets. |

### Package structure

A minimal JSHTML package ZIP can look like this:

```text
my-widget.zip
├─ widget.json
├─ index.html
├─ style.css
├─ main.js
└─ assets/
   └─ image.svg
```

Example `widget.json`:

```json
{
  "id": "anime-sidebar-sample",
  "name": "Anime Sidebar Sample",
  "version": "1.1.0",
  "entry": "index.html",
  "permissions": {
    "readAssets": true,
    "writeConfig": true,
    "systemInfo": true,
    "openUrl": true,
    "readTextFile": true
  },
  "size": {
    "width": 300,
    "height": 620
  }
}
```

### JavaScript API

JSHTML widgets can access LiteDesktopStudio through `window.LDSReady` and `window.LDS`.

```javascript
await window.LDSReady;

const info = await LDS.getWidgetInfo();
const sys = await LDS.getSystemInfo();
const assets = await LDS.listAssets("assets");

await LDS.writeConfig("theme", "sakura");
const theme = await LDS.readConfig("theme");
```

Available API methods:

- `LDS.ping()`
- `LDS.getWidgetInfo()`
- `LDS.getWidgetRect()`
- `LDS.getSystemInfo()`
- `LDS.readConfig(key)`
- `LDS.writeConfig(key, value)`
- `LDS.openUrl(url)`
- `LDS.getLocalAssetUrl(path)`
- `LDS.listAssets(path)`
- `LDS.readTextFile(path)`

### JSHTML Audio API

v2.1.1 added audio-reactive APIs for JSHTML widgets.

```javascript
await window.LDSReady;

const info = await LDS.getAudioInfo();
const level = await LDS.getAudioLevel();
const spectrum = await LDS.getAudioSpectrum();
```

Available audio API methods:

- `LDS.getAudioInfo()`
- `LDS.getAudioLevel()`
- `LDS.getAudioSpectrum()`

The audio API reads LiteDesktopStudio's cached `AudioEngine` spectrum data. JSHTML widgets do not open the audio device directly, which helps avoid device conflicts when multiple widgets are running.

### Compatibility shim

A lightweight asynchronous compatibility shim is also provided:

```javascript
await System.Gadget.settings.write("key", "value");
const value = await System.Gadget.settings.read("key");
```

> Note: this is not a full Windows Gadget API implementation. It is an asynchronous helper for settings-style migration because the runtime uses Qt WebChannel.

### JSHTML package management UI

When a JavaScript HTML widget is selected, the property panel can show package controls such as:

- package status display
- ZIP package import
- open JSHTML widget folder
- reload JSHTML widget
- return to inline mode

### JSHTML right-click behavior

v2.1.2 improves the JSHTML widget right-click behavior. The WebEngine default context menu is suppressed, and right-click twice on a JSHTML widget opens the LiteDesktopStudio settings panel instead of showing browser-style actions such as reload.

## Other Tools

v2.1.2 replaces the old performance information area with a dedicated **Other Tools** window. The goal is to keep the main properties panel clean while providing a place for future utilities.

Current tool groups:

| Tool group | Purpose |
|---|---|
| Package | Validate a JSHTML package folder and pack real files into a ZIP package. |
| Image | Convert SVG to PNG and convert PNG frame folders into SVG frame sequences. |
| Editors | Edit HTML, JSON / `widget.json`, and JavaScript files with open/save dialogs. |
| Diagnostics | Show basic JSHTML, WebEngine, selected widget, and audio backend information. |

### Image tools

The Image tab includes:

- **SVG → PNG** conversion
- **PNG → SVG frames** conversion for `frame_000.svg`, `frame_001.svg`, ... style animation packages
- Worker-thread based conversion for heavier image operations
- Cancel support for PNG frame conversion

The PNG-to-SVG frame tool is intended for low-resolution, limited-color frame images such as pixel art, icons, and simple sidebar-style animation frames. Large photos or highly detailed gradients may generate heavy SVG files.

### Editors

The Editors tab includes:

- HTML Editor
- JSON / `widget.json` Editor with formatting and validation
- JavaScript Editor

These editors are meant as lightweight helper tools for JSHTML package development.

## Sample packages

LiteDesktopStudio includes JSHTML sample packages that demonstrate package widgets and APIs.

| Sample | Purpose |
|---|---|
| Anime Sidebar Sample | Visual package demo with `widget.json`, assets, theme persistence, and CPU/RAM/DISK display. |
| Audio Reactive Bars | Audio-reactive bar visualizer using `LDS.getAudioInfo()`, `LDS.getAudioLevel()`, and `LDS.getAudioSpectrum()`. |
| Sequential Image Animator | Numbered-frame animation sample using `LDS.listAssets()` and image swapping. |
| Sequential Image Animator Transparent | Transparent-background version designed for videos and sidebar-style demos. Supports SVG/PNG/JPG/WebP frames. |

## Security notes

- Widget file access is limited to each widget's dedicated directory.
- ZIP extraction validates paths to reduce traversal risks.
- URL opening is restricted to `http://` and `https://`.
- Arbitrary command execution is not exposed.
- JSHTML Audio API exposes normalized level and spectrum data, not raw recording data.
- Package ZIP Builder ignores symlinks by default to avoid unintentionally packing files outside the package folder.

## Configuration file location

- On Windows, the configuration file is generated directly under `%PROFILES%`.
- On non-Windows systems, the configuration file is placed in the user directory.

## Planned features

- Multilingual support
- Implement as many features as possible within the range supported by PySide6
- More JSHTML sample packages and API examples
- More tools in the Other Tools window

## License

See the repository license file.

### Desktop priority mode

v2.1.2 also adds a small desktop operation priority mode. Press `Alt + D` to toggle it. When enabled, LiteDesktopStudio tries to keep widgets visible while passing mouse operations through to the desktop as much as possible.

This is useful when overlay effects or transparent widgets are visible but you want to temporarily prioritize normal desktop interaction. A small Windows native hotkey fix is included so `Alt + D` can be used to exit the mode even after mouse input has been made transparent. The Windows hotkey code explicitly imports `ctypes.wintypes` to avoid startup log noise from `ctypes.wintypes.MSG` access.
