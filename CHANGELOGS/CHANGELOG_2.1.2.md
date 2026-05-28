# CHANGELOG

## v2.1.2 - Other Tools and JSHTML Usability Update

### Added

- Added the Other Tools window.
- Added Package / Image / Editors / Diagnostics tabs.
- Added Package Builder for packing JSHTML package folders into ZIP packages.
- Added SVG → PNG conversion tool.
- Added PNG → SVG frames conversion tool.
- Added cancel support for PNG → SVG frames conversion.
- Added HTML Editor / JSON Editor / JavaScript Editor.
- Added JSON formatting and validation to the JSON Editor.
- Added Diagnostics tab.
- Added Sequential Image Animator Transparent sample.
- Added Other Tools related strings to built-in translations.

### Improved

- Image conversion now uses worker threads to reduce UI freezing during heavier operations.
- Improved JSHTML widget right-click behavior.
- Suppressed the WebEngine default context menu on JSHTML widgets.
- Right-click twice on a JSHTML widget now opens the LiteDesktopStudio settings panel.
- Sequential Image Animator Transparent can load SVG / PNG / JPG / JPEG / WebP frames.

### Notes

- PNG → SVG frames is best suited for low-resolution, limited-color artwork.
- Photos and complex gradients may generate heavy SVG files.
- Package Builder ignores symlinks by default.
