# CHANGELOG

## v2.1.1 - JSHTML Audio API Update

### Added

- Added `LDS.getAudioInfo()` for JSHTML widgets.
- Added `LDS.getAudioLevel()` for JSHTML widgets.
- Added `LDS.getAudioSpectrum()` for JSHTML widgets.
- Added an audio snapshot helper to `AudioEngine` for JSHTML widgets.
- Added the Audio Reactive Bars sample package.

### Improved

- JSHTML widgets can now build audio-reactive UIs.
- JSHTML widgets read cached spectrum data from the existing `AudioEngine` instead of opening audio devices directly.
- Updated README / README_ja with JSHTML Audio API and Audio Reactive Bars sample information.

### Notes

- JSHTML Audio API does not expose raw audio waveform or recording data.
- Very high update rates can increase WebChannel traffic, so moderate update intervals are recommended.
