<div align="center">
	<a href="https://github.com/CrossDarkrix/LiteDesktopStudio">
	<img width="150px" height="150px" alt="LiteDesktopStudio" src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/icon.png"></a>
</div>
<h2 align="center">Lite Desktop Studio</h2>
<p align="center">A Simple Desktop Gadet.</p>

[English README](README.md)

LiteDesktopStudio は、Python / PySide6 で作られた軽量デスクトップガジェットスタジオです。音楽ビジュアライザー、システム情報、通信状況、時計、カレンダー、天気、メディア操作、HTML/CSS風ウィジェット、JavaScript HTML ウィジェットなどをデスクトップ上に配置・編集・カスタマイズできます。

Artifacter や LiteDesktopStudio を作っていますが、開発に十分な余裕がありません。開発の励みになりますので、よろしければ支援をお願いします: [Buy me a coffee](https://www.buymeacoffee.com/crossdarkrix)

## スクリーンショット

<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot1.png" width="300px" height="250px"></a>
<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot2.png" width="300px" height="250px"></a>
<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot3.png" width="300px" height="250px"></a>
<a href="https://github.com/CrossDarkrix/LiteDesktopStudio"><img src="https://raw.githubusercontent.com/CrossDarkrix/LiteDesktopStudio/refs/heads/main/Images/screenshot4.png" width="300px" height="250px"></a>


## 特徴

- **デスクトップ上にウィジェットを自由配置**  
  ウィジェットを好きな位置・サイズでデスクトップ上に配置できます。

- **直感的な編集モード**  
  設定画面へは右クリックを素早く2回。ウィジェットを左クリックで選択し、`E` キーで配置編集を切り替えられます。

- **見た目を細かくカスタマイズ**  
  ウィジェットごとに透明度、背景色、アクセントカラー、サイズ、位置などを調整できます。

- **設定画面テーマ**  
  Liquid Glass、Dark、Material、Light などの設定画面テーマを切り替えられます。

- **音楽に反応するビジュアライザー**  
  再生中の音に合わせてスペクトルバーを表示できます。ピークバーや発光演出も利用できます。

- **システム・ネットワーク表示**  
  CPU、メモリ、ディスク使用率、上り/下り通信速度、通信履歴グラフなどを表示できます。

- **エフェクトオーバーレイ**  
  雨、粒子、グロー、波紋、バラ花びら、桜、雪、水、炎、流れ星などの演出をデスクトップに重ねられます。

- **HTML/CSS風ウィジェット**  
  メモ、リンク集、装飾パネルなど、簡単なカスタム表示を作れます。

- **JavaScript HTML ウィジェット**  
  Qt WebEngine ベースのウィジェットで、HTML / CSS / JavaScript を使ったよりリッチな表示を作れます。

- **JSHTML Audio API**  
  LiteDesktopStudio の音声スペクトルキャッシュを利用して、JSHTML package から音楽反応 UI を作れます。

- **その他のツール画面**  
  v2.1.2 では、JSHTML package 作成、画像変換、HTML/JSON/JavaScript編集、診断をまとめる専用ツール画面を追加しました。

- **改造しやすい構成**  
  Python / PySide6 実装なので、ソースコードを読める方であれば、ウィジェット追加、描画変更、設定項目追加などを行いやすい構成です。

## JavaScript HTML ウィジェットランタイム

LiteDesktopStudio には、強化された JavaScript HTML ウィジェットランタイムがあります。JSHTML ウィジェットは、簡単な inline HTML として動かすことも、ZIP インポート型の package ウィジェットとして動かすこともできます。package ウィジェットは、専用ディレクトリ、assets、永続設定、JavaScript API ブリッジを持てます。

### JSHTML モード

| モード | 説明 |
|---|---|
| `inline` | ウィジェットのテキスト欄に保存された HTML を直接表示します。小さなカスタムパネルや実験向けです。 |
| `package` | ZIP インポートしたウィジェットパッケージを、ウィジェット専用ディレクトリから読み込みます。`widget.json`、`index.html`、CSS、JavaScript、assets を含められます。 |

### パッケージ構成

最小構成の JSHTML パッケージ ZIP は次のような形です。

```text
my-widget.zip
├─ widget.json
├─ index.html
├─ style.css
├─ main.js
└─ assets/
   └─ image.svg
```

`widget.json` の例:

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

JSHTML ウィジェットからは `window.LDSReady` と `window.LDS` を使って LiteDesktopStudio の API にアクセスできます。

```javascript
await window.LDSReady;

const info = await LDS.getWidgetInfo();
const sys = await LDS.getSystemInfo();
const assets = await LDS.listAssets("assets");

await LDS.writeConfig("theme", "sakura");
const theme = await LDS.readConfig("theme");
```

利用できる API:

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

v2.1.1 では、JSHTML ウィジェット向けの音声反応 API を追加しました。

```javascript
await window.LDSReady;

const info = await LDS.getAudioInfo();
const level = await LDS.getAudioLevel();
const spectrum = await LDS.getAudioSpectrum();
```

利用できる Audio API:

- `LDS.getAudioInfo()`
- `LDS.getAudioLevel()`
- `LDS.getAudioSpectrum()`

Audio API は LiteDesktopStudio の `AudioEngine` が持つキャッシュ済みスペクトルを読み取ります。JSHTML ウィジェット側から音声デバイスを直接開かないため、複数ウィジェット実行時のデバイス競合を避けやすくなっています。

### 互換 shim

設定読み書き系の移植補助として、非同期の互換 shim も用意しています。

```javascript
await System.Gadget.settings.write("key", "value");
const value = await System.Gadget.settings.read("key");
```

> 注意: これは Windows Gadget API の完全互換ではありません。Qt WebChannel を使うため、非同期の設定読み書き補助として提供しています。

### JSHTML package 管理 UI

JavaScript HTML ウィジェットを選択すると、プロパティパネルで次のような package 管理操作ができます。

- package 状態表示
- ZIP package インポート
- JSHTML ウィジェットフォルダを開く
- JSHTML ウィジェット再読み込み
- inline モードに戻す

### JSHTML の右クリック挙動

v2.1.2 では、JSHTML ウィジェット上の右クリック挙動を改善しました。WebEngine 標準の右クリックメニューを抑止し、JSHTML ウィジェット上でも右クリック2回で LiteDesktopStudio の設定画面を開けるようにしています。

## その他のツール

v2.1.2 では、以前のパフォーマンス情報欄を **その他のツール** 画面へ置き換えました。右側プロパティパネルに機能を詰め込みすぎず、今後の補助機能を整理して追加できるようにするための画面です。

現在のツール分類:

| ツール分類 | 目的 |
|---|---|
| Package | JSHTML package フォルダを検証し、実ファイルを ZIP package にまとめます。 |
| Image | SVG→PNG変換、PNG連番フォルダ→SVG連番フレーム変換を行います。 |
| Editors | HTML、JSON / `widget.json`、JavaScript を開いて編集・保存できます。 |
| Diagnostics | JSHTML、WebEngine、選択中ウィジェット、Audio backend などの基本情報を表示します。 |

### Image tools

Image タブには以下があります。

- **SVG → PNG** 変換
- **PNG → SVG frames** 変換。`frame_000.svg`、`frame_001.svg` のような連番フレームを作成します。
- 重くなりやすい画像変換は worker thread で処理します。
- PNG frame 変換にはキャンセル操作を用意しています。

PNG→SVG frames は、低解像度・色数少なめのドット絵、アイコン、sidebar風連番アニメーション素材などに向いています。写真や細かいグラデーションの多い画像では、SVGが重くなる可能性があります。

### Editors

Editors タブには以下があります。

- HTML Editor
- JSON / `widget.json` Editor。整形と構文チェック付き。
- JavaScript Editor

JSHTML package 作成を補助する軽量エディターとして利用できます。

## サンプルパッケージ

LiteDesktopStudio には、JSHTML package の作り方を確認するためのサンプルを用意しています。

| サンプル | 目的 |
|---|---|
| Anime Sidebar Sample | `widget.json`、assets、テーマ保存、CPU/RAM/DISK 表示を含む総合デモ。 |
| Audio Reactive Bars | `LDS.getAudioInfo()`、`LDS.getAudioLevel()`、`LDS.getAudioSpectrum()` を使う音楽反応バーサンプル。 |
| Sequential Image Animator | `LDS.listAssets()` で連番画像を読み込み、画像差し替えでアニメーションするサンプル。 |
| Sequential Image Animator Transparent | 動画紹介やsidebar風デモ向けの透明背景版。SVG/PNG/JPG/WebP フレームに対応。 |

## セキュリティについて

- ウィジェットのファイルアクセスは、各ウィジェット専用ディレクトリ内に制限されます。
- ZIP 展開時には、パストラバーサルを避けるためのチェックを行います。
- URL を開く機能は `http://` と `https://` に制限されます。
- 任意コマンド実行 API は公開していません。
- JSHTML Audio API は正規化されたレベル値とスペクトル値を渡すもので、生の録音データは渡しません。
- Package ZIP Builder は、package 外のファイルを誤って含めにくくするため、既定でシンボリックリンクを無視します。

## 設定ファイルの場所

- Windows では `%PROFILES%` 直下に生成されます。
- Windows 以外ではユーザーディレクトリに配置されます。

## 今後の予定

- 多言語化
- PySide6 で実装できる範囲で可能な限り機能を実装
- JSHTML サンプル package と API 例の追加
- その他のツール画面への補助機能追加

## ライセンス

リポジトリ内のライセンスファイルを確認してください。

### デスクトップ操作優先モード

v2.1.2 では、小さな改善としてデスクトップ操作優先モードも追加しました。`Alt + D` でON/OFFを切り替えられます。ONにすると、LiteDesktopStudio の表示を残しつつ、マウス操作をできるだけ通常のデスクトップ側へ通します。

Overlayエフェクトや透明ウィジェットを表示したまま、通常のデスクトップ操作を優先したい時に使えます。また、マウス入力を透過した後でも `Alt + D` で戻せるよう、Windows native hotkey 側の処理も入れています。`ctypes.wintypes.MSG` 参照時の起動ログを避けるため、`ctypes.wintypes` を明示 import する小修正も含めています。