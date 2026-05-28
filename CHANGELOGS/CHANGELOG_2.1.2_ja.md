# CHANGELOG

## v2.1.2 - Other Tools / JSHTML 操作性改善

### 追加

- `その他のツール` 画面を追加。
- Package / Image / Editors / Diagnostics タブを追加。
- JSHTML package フォルダを ZIP 化する Package Builder を追加。
- SVG → PNG 変換ツールを追加。
- PNG → SVG frames 変換ツールを追加。
- PNG → SVG frames 変換にキャンセル操作を追加。
- HTML Editor / JSON Editor / JavaScript Editor を追加。
- JSON Editor に整形と構文チェックを追加。
- Diagnostics タブを追加。
- Sequential Image Animator Transparent sample を追加。
- `その他のツール` 関連文言を built-in translation に追加。

### 改善

- 画像変換処理を worker thread 化し、重い変換中に UI が固まりにくい構成へ変更。
- JSHTML ウィジェット上の右クリック挙動を改善。
- WebEngine 標準コンテキストメニューを抑止。
- JSHTML ウィジェット上でも右クリック2回で設定画面を開けるように改善。
- Sequential Image Animator の透明背景版で、SVG / PNG / JPG / JPEG / WebP フレームを読み込めるように改善。

### 注意

- PNG → SVG frames は低解像度・色数少なめの素材向けです。
- 写真や複雑なグラデーション画像では SVG が重くなる場合があります。
- Package Builder は既定でシンボリックリンクを無視します。
