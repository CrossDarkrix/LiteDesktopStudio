# CHANGELOG

## v2.1.0 - JSHTML Widget Runtime Update

### Added

- Added `package` mode for JavaScript HTML widgets.
- Added ZIP import for JSHTML packages.
- Added dedicated per-widget JSHTML directories.
- Added `assets/` and `data/config.json` management for package files and persistent settings.
- Added `widget.json` metadata loading for package name, version, entry file, and permissions.
- Added Qt WebChannel bridge exposed as `window.LDSReady` and `window.LDS`.
- Added per-widget persistent settings through `LDS.readConfig()` and `LDS.writeConfig()`.
- Added `LDS.getSystemInfo()` for CPU, RAM, and disk information.
- Added `LDS.listAssets()`, `LDS.getLocalAssetUrl()`, and `LDS.readTextFile()`.
- Added `LDS.openUrl()`, restricted to `http://` and `https://` URLs.
- Added asynchronous `System.Gadget.settings.read/write` compatibility shim.
- Added JSHTML property-panel controls for package status, ZIP import, opening the widget folder, reloading, and returning to inline mode.
- Added Anime Sidebar sample package.

### Improved

- Improved JSHTML widgets from inline-only HTML panels into reusable ZIP package widgets.
- Adjusted the settings window and property panel width for the expanded JSHTML package UI.
- Stabilized the ZIP import file dialog by aligning it with the existing config import/export dialog style.

### Security

- Rejected absolute paths, drive-letter style paths, and `..` traversal paths during ZIP extraction.
- Added file count, single file size, and total extracted size limits for ZIP import.
- Restricted JSHTML package file access to each widget's dedicated directory.
- Continued to avoid exposing arbitrary command execution APIs.

### Notes

- `System.Gadget.settings` shim is asynchronous.
- Full Windows Gadget API compatibility is not provided.
