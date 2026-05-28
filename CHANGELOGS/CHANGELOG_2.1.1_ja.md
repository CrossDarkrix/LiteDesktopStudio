# CHANGELOG

## v2.1.1 - JSHTML Audio API Update

### 追加

- JSHTML ウィジェット向けに `LDS.getAudioInfo()` を追加。
- JSHTML ウィジェット向けに `LDS.getAudioLevel()` を追加。
- JSHTML ウィジェット向けに `LDS.getAudioSpectrum()` を追加。
- `AudioEngine` に JSHTML 用の audio snapshot 取得処理を追加。
- Audio Reactive Bars サンプル package を追加。

### 改善

- JSHTML ウィジェットから音声反応 UI を作れるように改善。
- 音声デバイスを JSHTML 側で直接開かず、既存 `AudioEngine` のキャッシュ済みスペクトルを読む設計にしました。
- README / README_ja に JSHTML Audio API と Audio Reactive Bars サンプルの説明を追加。

### 注意

- JSHTML Audio API は生音声波形や録音データを渡しません。
- 高頻度更新しすぎると WebChannel 通信量が増えるため、適度な更新間隔を推奨します。
