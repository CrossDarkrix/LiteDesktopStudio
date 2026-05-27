# JSHTML ウィジェット package ガイド

このドキュメントでは、LiteDesktopStudio の JavaScript HTML ウィジェット package ランタイムについて説明します。

## 概要

JSHTML ウィジェットには 2 つのモードがあります。

- `inline`: ウィジェット設定内の HTML を直接表示します。
- `package`: ZIP インポートされた package を、ウィジェット専用ディレクトリから読み込みます。

package モードは、再利用可能なウィジェット、凝ったデザイン、配布可能なウィジェットパックを作るための仕組みです。

## ディレクトリ構造

ZIP package をインポートすると、LiteDesktopStudio はウィジェットごとに専用ディレクトリを作成します。

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

`data/config.json` は、`LDS.writeConfig()` で書き込まれたウィジェット単位の永続データを保存します。

## widget.json

`widget.json` は任意ですが、package として配布する場合は用意することを推奨します。

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

| フィールド | 意味 |
|---|---|
| `id` | package 識別子 |
| `name` | 表示名 |
| `version` | package バージョン |
| `entry` | 起動 HTML。省略時は `index.html` |
| `permissions` | package が使いたい機能の宣言 |

## JavaScript API

API を使う前に、必ず `window.LDSReady` を待ちます。

```javascript
await window.LDSReady;
const result = await LDS.ping();
```

### `LDS.getWidgetInfo()`

ウィジェットの mode、entry、package 名、package バージョン、instance ID、専用ディレクトリなどを返します。

### `LDS.getSystemInfo()`

CPU、メモリ、ディスク、利用可能な場合はバッテリー情報、platform を返します。

### `LDS.readConfig(key)` / `LDS.writeConfig(key, value)`

ウィジェット単位の永続データを読み書きします。

```javascript
const before = await LDS.readConfig("bootCount");
const count = Number(before.value || 0) + 1;
await LDS.writeConfig("bootCount", count);
```

### `LDS.listAssets(path)`

ウィジェット専用ディレクトリ内の指定フォルダにあるファイル一覧を返します。

```javascript
const assets = await LDS.listAssets("assets");
```

### `LDS.getLocalAssetUrl(path)`

ウィジェット専用ディレクトリ内のファイルに対するローカル URL を返します。

### `LDS.readTextFile(path)`

ウィジェット専用ディレクトリ内の UTF-8 テキストファイルを読み込みます。大きすぎるファイルは拒否されます。

### `LDS.openUrl(url)`

`http://` または `https://` の URL を既定ブラウザで開きます。

## 互換 shim

LiteDesktopStudio は、設定読み書き移植用に非同期の `System.Gadget.settings` 風 shim を提供します。

```javascript
await System.Gadget.settings.write("theme", "sakura");
const theme = await System.Gadget.settings.read("theme");
```

これは Windows Gadget API の完全互換ではありません。

## UI 操作

JSHTML ウィジェットを選択すると、プロパティパネルで次の操作を行えます。

- package 状態表示
- ZIP package インポート
- ウィジェットフォルダを開く
- ウィジェット再読み込み
- inline モードに戻す

## セキュリティメモ

- ファイルアクセスはウィジェット専用ディレクトリ内に制限されます。
- ZIP 内の絶対パス、ドライブレター風パス、`..` パストラバーサルは拒否されます。
- URL を開く機能は `http://` と `https://` に制限されます。
- 任意コマンド実行 API は公開していません。
