# JSHTML Widget Package Guide

This document describes the JavaScript HTML widget package runtime in LiteDesktopStudio.

## Overview

JSHTML widgets support two modes:

- `inline`: renders HTML stored directly in the widget configuration.
- `package`: renders a ZIP-imported package from a dedicated widget directory.

Package mode is intended for reusable widgets, richer designs, and shareable widget packs.

## Directory structure

After importing a ZIP package, LiteDesktopStudio creates a dedicated directory for that widget instance.

```text
LiteDesktopStudio_jshtml_widgets/
└─ <instance_id>/
   ├─ widget.json
   ├─ index.html
   ├─ style.css
   ├─ main.js
   ├─ assets/
   └─ data/
      └─ config.json
```

`data/config.json` stores per-widget persistent data written through `LDS.writeConfig()`.

## widget.json

`widget.json` is optional but recommended for packages.

```json
{
  "id": "example-widget",
  "name": "Example Widget",
  "version": "1.0.0",
  "entry": "index.html",
  "permissions": {
    "readAssets": true,
    "writeConfig": true,
    "systemInfo": true,
    "openUrl": true,
    "readTextFile": true
  }
}
```

| Field | Meaning |
|---|---|
| `id` | Package identifier |
| `name` | Display name |
| `version` | Package version |
| `entry` | Entry HTML file. Defaults to `index.html` |
| `permissions` | Declares intended package capabilities |

## JavaScript API

Always wait for `window.LDSReady` before using the API.

```javascript
await window.LDSReady;
const result = await LDS.ping();
```

### `LDS.getWidgetInfo()`

Returns widget mode, entry, package name, package version, instance ID, and dedicated widget directory.

### `LDS.getSystemInfo()`

Returns CPU, memory, disk, battery information when available, and platform.

### `LDS.readConfig(key)` / `LDS.writeConfig(key, value)`

Reads and writes persistent per-widget data.

```javascript
const before = await LDS.readConfig("bootCount");
const count = Number(before.value || 0) + 1;
await LDS.writeConfig("bootCount", count);
```

### `LDS.listAssets(path)`

Lists files inside a directory under the widget folder.

```javascript
const assets = await LDS.listAssets("assets");
```

### `LDS.getLocalAssetUrl(path)`

Returns a local URL for a file inside the widget directory.

### `LDS.readTextFile(path)`

Reads a UTF-8 text file inside the widget directory. Large files are rejected.

### `LDS.openUrl(url)`

Opens `http://` or `https://` URLs in the system browser.

## Compatibility shim

LiteDesktopStudio exposes a small asynchronous `System.Gadget.settings`-style shim.

```javascript
await System.Gadget.settings.write("theme", "sakura");
const theme = await System.Gadget.settings.read("theme");
```

This is not a full Windows Gadget API implementation.

## UI operations

When selecting a JSHTML widget, the property panel can show:

- package mode status
- package name and version
- entry file
- instance ID
- widget folder path
- ZIP import
- open widget folder
- reload widget
- return to inline mode

## Security notes

- Widget file access is restricted to the widget directory.
- ZIP entries with absolute paths, drive-letter paths, or `..` traversal are rejected.
- URL opening is restricted to `http://` and `https://`.
- Arbitrary command execution APIs are not exposed.
