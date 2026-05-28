# CHANGELOG

## v2.1.0 - JSHTML Widget Runtime Update

### 追加

- JavaScript HTML ウィジェットに `package` モードを追加。
- JSHTML package の ZIP インポートを追加。
- JSHTML ウィジェットごとの専用ディレクトリを追加。
- `assets/` と `data/config.json` によるファイル・永続設定管理を追加。
- `widget.json` から package 名、バージョン、entry ファイル、permissions を読み込む処理を追加。
- Qt WebChannel による `window.LDSReady` / `window.LDS` API ブリッジを追加。
- `LDS.readConfig()` / `LDS.writeConfig()` によるウィジェット単位の永続設定を追加。
- `LDS.getSystemInfo()` による CPU / RAM / DISK 取得を追加。
- `LDS.listAssets()` / `LDS.getLocalAssetUrl()` / `LDS.readTextFile()` を追加。
- `LDS.openUrl()` を追加。ただし `http://` / `https://` のみに制限。
- 非同期 `System.Gadget.settings.read/write` 互換 shim を追加。
- JSHTML プロパティパネルに package 状態表示、ZIP インポート、フォルダを開く、再読み込み、inline モードへ戻す操作を追加。
- Anime Sidebar サンプル package を追加。

### 改善

- JSHTML ウィジェットを inline HTML だけでなく、再利用可能な ZIP package として扱えるように改善。
- JSHTML package 用 UI を見やすくするため、設定画面と右側プロパティパネルの幅を調整。
- ZIP インポート時のファイルダイアログを既存の設定インポート/エクスポート方式に合わせて安定化。

### セキュリティ

- ZIP 展開時に絶対パス、ドライブレター風パス、`..` を含むパストラバーサルを拒否。
- ZIP 内のファイル数、単一ファイルサイズ、総展開サイズに制限を追加。
- JSHTML package のファイルアクセスをウィジェット専用ディレクトリ内に制限。
- 任意コマンド実行 API は公開しない方針を維持。

### 注意

- `System.Gadget.settings` shim は非同期です。
- Windows Gadget API の完全互換ではありません。
