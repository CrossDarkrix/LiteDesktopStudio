# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtCore import (QThread,
                            )
from PySide6.QtGui import (
    QDesktopServices,
)
from PySide6.QtWidgets import (QWidget,
                               QVBoxLayout,
                               QHBoxLayout,
                               QPushButton,
                               QTextEdit,
                               QColorDialog,
                               QFileDialog,
                               QSpinBox,
                               QDialog,
                               QFormLayout,
                               QLineEdit,
                               QMessageBox,
                               QCheckBox,
                               QTabWidget,
                               )

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except:
    QOpenGLWidget = None

from litedesktopstudio.jshtml import *
from litedesktopstudio.version import APP_NAME


def _lds_set_non_native_file_dialog(dialog):
    try:
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    except AttributeError:
        try:
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        except:
            pass


def _lds_open_file_dialog(parent, title: str, name_filter: str) -> str:
    dialog = QFileDialog(parent, lds_tr(title))
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setNameFilter(name_filter)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    _lds_set_non_native_file_dialog(dialog)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return ""
    files = dialog.selectedFiles()
    return files[0] if files else ""


def _lds_save_file_dialog(parent, title: str, name_filter: str, default_suffix: str = "", selected_file: str = "") -> str:
    dialog = QFileDialog(parent, lds_tr(title))
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setNameFilter(name_filter)
    if default_suffix:
        dialog.setDefaultSuffix(default_suffix)
    if selected_file:
        dialog.selectFile(selected_file)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    _lds_set_non_native_file_dialog(dialog)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return ""
    files = dialog.selectedFiles()
    return files[0] if files else ""


def _lds_select_directory_dialog(parent, title: str) -> str:
    dialog = QFileDialog(parent, lds_tr(title))
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    _lds_set_non_native_file_dialog(dialog)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return ""
    files = dialog.selectedFiles()
    return files[0] if files else ""


class PackageBuilderToolsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(lds_tr("📦 JSHTML Package ZIP Builder"))
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(make_beginner_guide_label(
            lds_tr("JSHTML package を配布用ZIPにまとめます"),
            lds_tr("widget.json と assets フォルダを持つフォルダを選び、実ファイルだけをZIP化します。シンボリックリンクは既定では無視します。")
        ))

        form = QFormLayout()
        self.source_edit = QLineEdit()
        self.output_edit = QLineEdit()
        src_btn = QPushButton(lds_tr("参照..."))
        out_btn = QPushButton(lds_tr("保存先..."))
        src_row = QHBoxLayout(); src_row.addWidget(self.source_edit); src_row.addWidget(src_btn)
        out_row = QHBoxLayout(); out_row.addWidget(self.output_edit); out_row.addWidget(out_btn)
        form.addRow(lds_tr("Source folder"), src_row)
        form.addRow(lds_tr("Output zip"), out_row)
        layout.addLayout(form)

        self.exclude_data = QCheckBox(lds_tr("data/config.json を除外"))
        self.exclude_data.setChecked(True)
        self.exclude_git = QCheckBox(lds_tr(".git / __pycache__ / *.pyc を除外"))
        self.exclude_git.setChecked(True)
        self.ignore_symlinks = QCheckBox(lds_tr("シンボリックリンクを無視"))
        self.ignore_symlinks.setChecked(True)
        layout.addWidget(self.exclude_data)
        layout.addWidget(self.exclude_git)
        layout.addWidget(self.ignore_symlinks)

        btn_row = QHBoxLayout()
        self.validate_btn = QPushButton(lds_tr("検証"))
        self.build_btn = QPushButton(lds_tr("ZIP作成"))
        btn_row.addWidget(self.validate_btn)
        btn_row.addWidget(self.build_btn)
        layout.addLayout(btn_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        layout.addWidget(self.log)

        src_btn.clicked.connect(self.choose_source)
        out_btn.clicked.connect(self.choose_output)
        self.validate_btn.clicked.connect(self.validate_package)
        self.build_btn.clicked.connect(self.build_zip)

    def append_log(self, text):
        self.log.append(str(text))

    def choose_source(self):
        path = _lds_select_directory_dialog(self, "JSHTML package フォルダを選択")
        if path:
            self.source_edit.setText(path)
            if not self.output_edit.text().strip():
                self.output_edit.setText(str(Path(path).with_suffix(".zip")))

    def choose_output(self):
        path = _lds_save_file_dialog(self, "ZIP保存先を選択", "ZIP Files (*.zip);;All Files (*)", "zip", "jshtml_widget.zip")
        if path:
            if not path.lower().endswith(".zip"):
                path += ".zip"
            self.output_edit.setText(path)

    def _source_dir(self) -> Optional[Path]:
        path = self.source_edit.text().strip()
        if not path:
            return None
        return Path(path).resolve()

    def _validate(self):
        errors = []
        warnings_list = []
        source = self._source_dir()
        if source is None or not source.exists() or not source.is_dir():
            errors.append(lds_tr("Source folder が存在しません。"))
            return source, errors, warnings_list
        manifest = source / "widget.json"
        assets = source / "assets"
        if not manifest.exists() or not manifest.is_file():
            errors.append(lds_tr("widget.json が見つかりません。"))
        else:
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    errors.append(lds_tr("widget.json の内容がJSON objectではありません。"))
                else:
                    entry = str(data.get("entry") or "index.html")
                    entry_path = (source / entry).resolve()
                    try:
                        if source != entry_path and source not in entry_path.parents:
                            errors.append(lds_tr("entry がpackageフォルダ外を指しています。"))
                        elif not entry_path.exists() or not entry_path.is_file():
                            errors.append(lds_tr("entry HTML が見つかりません: ") + entry)
                    except Exception as e:
                        errors.append(lds_tr("entry 検証エラー: ") + repr(e))
            except Exception as e:
                errors.append(lds_tr("widget.json を読み込めません: ") + repr(e))
        if not assets.exists() or not assets.is_dir():
            errors.append(lds_tr("assets フォルダが見つかりません。"))
        for root, dirs, files in os.walk(source):
            root_path = Path(root)
            for name in dirs + files:
                p = root_path / name
                if p.is_symlink():
                    warnings_list.append(lds_tr("シンボリックリンク: ") + str(p.relative_to(source)))
        return source, errors, warnings_list

    def validate_package(self):
        self.log.clear()
        source, errors, warnings_list = self._validate()
        if source is not None:
            self.append_log(lds_tr("Source: ") + str(source))
        if errors:
            self.append_log(lds_tr("Errors:"))
            for e in errors:
                self.append_log("  - " + e)
        else:
            self.append_log(lds_tr("検証OK: packageとしてZIP化できます。"))
        if warnings_list:
            self.append_log(lds_tr("Warnings:"))
            for w in warnings_list:
                self.append_log("  - " + w)

    def _should_skip(self, source: Path, path: Path) -> bool:
        rel = path.relative_to(source)
        parts = rel.parts
        if self.exclude_git.isChecked():
            if ".git" in parts or "__pycache__" in parts or path.name.endswith(".pyc"):
                return True
        if self.exclude_data.isChecked():
            if rel.as_posix() == "data/config.json":
                return True
        if self.ignore_symlinks.isChecked() and path.is_symlink():
            return True
        return False

    def build_zip(self):
        self.log.clear()
        source, errors, warnings_list = self._validate()
        if errors:
            self.validate_package()
            QMessageBox.warning(self, lds_tr("ZIP作成不可"), lds_tr("package検証でエラーがあります。"))
            return
        output = self.output_edit.text().strip()
        if not output:
            self.choose_output()
            output = self.output_edit.text().strip()
        if not output:
            return
        if not output.lower().endswith(".zip"):
            output += ".zip"
            self.output_edit.setText(output)
        output_path = Path(output).resolve()
        try:
            count = 0
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(source.rglob("*")):
                    if not path.is_file():
                        continue
                    if self._should_skip(source, path):
                        self.append_log(lds_tr("skip: ") + str(path.relative_to(source)))
                        continue
                    if path.is_symlink() and not self.ignore_symlinks.isChecked():
                        resolved = path.resolve()
                        if source != resolved and source not in resolved.parents:
                            self.append_log(lds_tr("skip external symlink: ") + str(path.relative_to(source)))
                            continue
                        archive.write(resolved, path.relative_to(source).as_posix())
                    else:
                        archive.write(path, path.relative_to(source).as_posix())
                    count += 1
            self.append_log(lds_tr("ZIP作成完了: ") + str(output_path))
            self.append_log(lds_tr("files: ") + str(count))
            QMessageBox.information(self, lds_tr("完了"), lds_tr("JSHTML package ZIPを作成しました。"))
        except Exception as e:
            QMessageBox.warning(self, lds_tr("ZIP作成失敗"), str(e))


def _lds_png2svg_add_tuple(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _lds_png2svg_sub_tuple(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _lds_png2svg_direction(edge):
    return _lds_png2svg_sub_tuple(edge[1], edge[0])


def _lds_png2svg_magnitude(a):
    return int(pow(pow(a[0], 2) + pow(a[1], 2), 0.5))


def _lds_png2svg_normalize(a):
    mag = _lds_png2svg_magnitude(a)
    if not mag > 0:
        raise RuntimeError("Cannot normalize a zero-length vector")
    return (a[0] / mag, a[1] / mag)


def _lds_png2svg_header(width, height):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<svg width="%d" height="%d" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" version="1.1">\n'
        % (width, height, width, height)
    )


def _lds_png2svg_joined_edges(assorted_edges, keep_every_point=False):
    from collections import deque
    pieces = []
    piece = []
    directions = deque([(0, 1), (1, 0), (0, -1), (-1, 0)])
    while assorted_edges:
        if not piece:
            piece.append(assorted_edges.pop())
        current_direction = _lds_png2svg_normalize(_lds_png2svg_direction(piece[-1]))
        while current_direction != directions[2]:
            directions.rotate()
        for i in range(1, 4):
            next_end = _lds_png2svg_add_tuple(piece[-1][1], directions[i])
            next_edge = (piece[-1][1], next_end)
            if next_edge in assorted_edges:
                assorted_edges.remove(next_edge)
                if i == 2 and not keep_every_point:
                    piece[-1] = (piece[-1][0], next_edge[1])
                else:
                    piece.append(next_edge)
                if piece[0][0] == piece[-1][1]:
                    if not keep_every_point and _lds_png2svg_normalize(_lds_png2svg_direction(piece[0])) == _lds_png2svg_normalize(_lds_png2svg_direction(piece[-1])):
                        piece[-1] = (piece[-1][0], piece.pop(0)[1])
                    pieces.append(piece)
                    piece = []
                break
        else:
            raise RuntimeError("Failed to find connecting edge")
    return pieces


def _lds_rgba_image_to_svg_contiguous(im, background_rgb=(255, 255, 255), skip_background=True, opaque=False, keep_every_point=False):
    from PIL import Image
    adjacent = ((1, 0), (0, 1), (-1, 0), (0, -1))
    visited = Image.new('1', im.size, 0)
    color_pixel_lists = {}
    width, height = im.size
    for x in range(width):
        for y in range(height):
            here = (x, y)
            if visited.getpixel(here):
                continue
            rgba = im.getpixel((x, y))
            if skip_background and rgba[:3] == background_rgb:
                continue
            if opaque and not rgba[3]:
                continue
            piece = []
            queue = [here]
            visited.putpixel(here, 1)
            while queue:
                here = queue.pop()
                for offset in adjacent:
                    neighbour = _lds_png2svg_add_tuple(here, offset)
                    if not (0 <= neighbour[0] < width) or not (0 <= neighbour[1] < height):
                        continue
                    if visited.getpixel(neighbour):
                        continue
                    neighbour_rgba = im.getpixel(neighbour)
                    if neighbour_rgba != rgba:
                        continue
                    queue.append(neighbour)
                    visited.putpixel(neighbour, 1)
                piece.append(here)
            if rgba not in color_pixel_lists:
                color_pixel_lists[rgba] = []
            color_pixel_lists[rgba].append(piece)

    edges = {
        (-1, 0): ((0, 0), (0, 1)),
        (0, 1): ((0, 1), (1, 1)),
        (1, 0): ((1, 1), (1, 0)),
        (0, -1): ((1, 0), (0, 0)),
    }
    color_edge_lists = {}
    for rgba, pieces in list(color_pixel_lists.items()):
        for piece_pixel_list in pieces:
            edge_set = set()
            set_p = set(piece_pixel_list)
            for coord in piece_pixel_list:
                for offset, (start_offset, end_offset) in list(edges.items()):
                    neighbour = _lds_png2svg_add_tuple(coord, offset)
                    start_edge = _lds_png2svg_add_tuple(coord, start_offset)
                    end_edge = _lds_png2svg_add_tuple(coord, end_offset)
                    edge = (start_edge, end_edge)
                    if neighbour in set_p:
                        continue
                    edge_set.add(edge)
            if rgba not in color_edge_lists:
                color_edge_lists[rgba] = []
            color_edge_lists[rgba].append(edge_set)

    color_joined_pieces = {}
    for color, pieces in list(color_edge_lists.items()):
        color_joined_pieces[color] = []
        for assorted_edges in pieces:
            color_joined_pieces[color].append(_lds_png2svg_joined_edges(assorted_edges, keep_every_point))

    s = [_lds_png2svg_header(*im.size)]
    for color, shapes in list(color_joined_pieces.items()):
        for shape in shapes:
            s.append(' <path d=" ')
            for sub_shape in shape:
                here = sub_shape.pop(0)[0]
                s.append(' M %d,%d ' % here)
                for edge in sub_shape:
                    here = edge[0]
                    s.append(' L %d,%d ' % here)
                s.append(' Z ')
            s.append(' " style="fill:rgb%s; fill-opacity:%.3f; stroke:none;" />\n' % (color[0:3], float(color[3]) / 255.0))
    s.append('</svg>\n')
    return ''.join(s)


def _lds_png_to_svg_text(filename: str, background_rgb=(255, 255, 255), skip_background=True) -> str:
    from PIL import Image
    im_rgba = Image.open(filename).convert('RGBA')
    return _lds_rgba_image_to_svg_contiguous(im_rgba, background_rgb=background_rgb, skip_background=skip_background, opaque=False, keep_every_point=False)


def _lds_natural_path_key(path: Path):
    import re
    parts = re.split(r"(\d+)", path.stem)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


class SvgToPngWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, svg_path: str, png_path: str, width: int, height: int, transparent: bool, parent=None):
        super().__init__(parent)
        self.svg_path = str(svg_path)
        self.png_path = str(png_path)
        self.width = int(width or 0)
        self.height = int(height or 0)
        self.transparent = bool(transparent)

    @Slot()
    def run(self):
        try:
            from PySide6.QtSvg import QSvgRenderer
            renderer = QSvgRenderer(self.svg_path)
            if not renderer.isValid():
                raise RuntimeError("invalid SVG")
            size = renderer.defaultSize()
            width = self.width or max(1, size.width())
            height = self.height or max(1, size.height())
            if width <= 0:
                width = 512
            if height <= 0:
                height = 512
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent if self.transparent else QColor("white"))
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            if not image.save(self.png_path, "PNG"):
                raise RuntimeError("failed to save PNG")
            self.finished.emit(self.png_path)
        except Exception as e:
            self.failed.emit(str(e))


class PngToSvgFramesWorker(QObject):
    progress = Signal(str)
    finished = Signal(int, int)
    canceled = Signal(int, int)
    failed = Signal(str)

    def __init__(self, input_dir: str, output_dir: str, prefix: str, digits: int, overwrite: bool, skip_white: bool, parent=None):
        super().__init__(parent)
        self.input_dir = Path(str(input_dir)).resolve()
        self.output_dir = Path(str(output_dir)).resolve()
        self.prefix = str(prefix or "frame_")
        self.digits = int(digits or 3)
        self.overwrite = bool(overwrite)
        self.skip_white = bool(skip_white)
        self._cancel_requested = False

    @Slot()
    def request_cancel(self):
        self._cancel_requested = True

    @Slot()
    def run(self):
        converted = 0
        skipped = 0
        try:
            if not self.input_dir.exists() or not self.input_dir.is_dir():
                raise RuntimeError("PNG folder not found")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            png_files = sorted(
                [p for p in self.input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"],
                key=_lds_natural_path_key,
            )
            if not png_files:
                self.failed.emit(lds_tr("PNGファイルが見つかりません。"))
                return
            for index, src in enumerate(png_files):
                if self._cancel_requested:
                    self.canceled.emit(converted, skipped)
                    return
                dst = self.output_dir / f"{self.prefix}{index:0{self.digits}d}.svg"
                if dst.exists() and not self.overwrite:
                    skipped += 1
                    self.progress.emit(lds_tr("skip existing: ") + dst.name)
                    continue
                self.progress.emit(lds_tr("converting: ") + src.name)
                svg_text = _lds_png_to_svg_text(str(src), background_rgb=(255, 255, 255), skip_background=self.skip_white)
                if self._cancel_requested:
                    self.canceled.emit(converted, skipped)
                    return
                dst.write_text(svg_text, encoding="utf-8")
                converted += 1
                self.progress.emit(f"{src.name} -> {dst.name}")
            self.finished.emit(converted, skipped)
        except Exception as e:
            self.failed.emit(str(e))


class ImageToolsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.svg2png_thread = None
        self.svg2png_worker = None
        self.png2svg_thread = None
        self.png2svg_worker = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title = QLabel(lds_tr("🖼 Image Tools"))
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_svg_to_png_tab(), lds_tr("SVG → PNG"))
        tabs.addTab(self._build_png_to_svg_tab(), lds_tr("PNG → SVG frames"))
        layout.addWidget(tabs, 1)

    def _build_svg_to_png_tab(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        form = QFormLayout()
        self.svg_input = QLineEdit()
        self.png_output = QLineEdit()
        in_btn = QPushButton(lds_tr("参照..."))
        out_btn = QPushButton(lds_tr("保存先..."))
        in_row = QHBoxLayout(); in_row.addWidget(self.svg_input); in_row.addWidget(in_btn)
        out_row = QHBoxLayout(); out_row.addWidget(self.png_output); out_row.addWidget(out_btn)
        form.addRow(lds_tr("Input SVG"), in_row)
        form.addRow(lds_tr("Output PNG"), out_row)
        self.width_spin = QSpinBox(); self.width_spin.setRange(0, 8192); self.width_spin.setValue(0)
        self.height_spin = QSpinBox(); self.height_spin.setRange(0, 8192); self.height_spin.setValue(0)
        form.addRow(lds_tr("Width 0=auto"), self.width_spin)
        form.addRow(lds_tr("Height 0=auto"), self.height_spin)
        layout.addLayout(form)
        self.transparent_check = QCheckBox(lds_tr("透明背景"))
        self.transparent_check.setChecked(True)
        layout.addWidget(self.transparent_check)
        self.svg2png_convert_btn = QPushButton(lds_tr("変換"))
        layout.addWidget(self.svg2png_convert_btn)
        self.svg2png_status = QLabel("")
        self.svg2png_status.setObjectName("SubText")
        layout.addWidget(self.svg2png_status)
        layout.addStretch(1)
        in_btn.clicked.connect(self.choose_svg)
        out_btn.clicked.connect(self.choose_png)
        self.svg2png_convert_btn.clicked.connect(self.start_svg_to_png_worker)
        return panel

    def _build_png_to_svg_tab(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(make_beginner_guide_label(
            lds_tr("PNG連番素材をSVG連番素材へ変換"),
            lds_tr("Sequential Image Animator sample で使いやすい frame_000.svg 形式へ一括変換します。写真や高解像度画像はSVGが重くなる場合があります。")
        ))
        form = QFormLayout()
        self.png_frames_input = QLineEdit()
        self.svg_frames_output = QLineEdit()
        in_btn = QPushButton(lds_tr("参照..."))
        out_btn = QPushButton(lds_tr("出力先..."))
        in_row = QHBoxLayout(); in_row.addWidget(self.png_frames_input); in_row.addWidget(in_btn)
        out_row = QHBoxLayout(); out_row.addWidget(self.svg_frames_output); out_row.addWidget(out_btn)
        form.addRow(lds_tr("PNG folder"), in_row)
        form.addRow(lds_tr("SVG frames folder"), out_row)
        self.frame_prefix_edit = QLineEdit("frame_")
        self.frame_digits_spin = QSpinBox(); self.frame_digits_spin.setRange(1, 8); self.frame_digits_spin.setValue(3)
        form.addRow(lds_tr("Prefix"), self.frame_prefix_edit)
        form.addRow(lds_tr("Digits"), self.frame_digits_spin)
        layout.addLayout(form)
        self.skip_white_check = QCheckBox(lds_tr("白背景 RGB(255,255,255) を透過扱いでスキップ"))
        self.skip_white_check.setChecked(True)
        self.overwrite_svg_frames_check = QCheckBox(lds_tr("既存SVGを上書き"))
        self.overwrite_svg_frames_check.setChecked(False)
        layout.addWidget(self.skip_white_check)
        layout.addWidget(self.overwrite_svg_frames_check)
        btn_row = QHBoxLayout()
        self.png2svg_convert_btn = QPushButton(lds_tr("PNG→SVG frames 変換"))
        self.png2svg_cancel_btn = QPushButton(lds_tr("キャンセル"))
        self.png2svg_cancel_btn.setEnabled(False)
        btn_row.addWidget(self.png2svg_convert_btn)
        btn_row.addWidget(self.png2svg_cancel_btn)
        layout.addLayout(btn_row)
        self.png2svg_log = QTextEdit()
        self.png2svg_log.setReadOnly(True)
        self.png2svg_log.setMinimumHeight(180)
        layout.addWidget(self.png2svg_log, 1)
        in_btn.clicked.connect(self.choose_png_frames_input)
        out_btn.clicked.connect(self.choose_svg_frames_output)
        self.png2svg_convert_btn.clicked.connect(self.start_png_frames_to_svg_worker)
        self.png2svg_cancel_btn.clicked.connect(self.cancel_png_frames_to_svg_worker)
        return panel

    def choose_svg(self):
        path = _lds_open_file_dialog(self, "SVGファイルを選択", "SVG Files (*.svg);;All Files (*)")
        if path:
            self.svg_input.setText(path)
            if not self.png_output.text().strip():
                self.png_output.setText(str(Path(path).with_suffix(".png")))

    def choose_png(self):
        path = _lds_save_file_dialog(self, "PNG保存先を選択", "PNG Files (*.png);;All Files (*)", "png", "output.png")
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            self.png_output.setText(path)

    def choose_png_frames_input(self):
        path = _lds_select_directory_dialog(self, "PNG連番フォルダを選択")
        if path:
            self.png_frames_input.setText(path)
            if not self.svg_frames_output.text().strip():
                self.svg_frames_output.setText(str(Path(path).parent / "frames_svg"))

    def choose_svg_frames_output(self):
        path = _lds_select_directory_dialog(self, "SVG frames 出力フォルダを選択")
        if path:
            self.svg_frames_output.setText(path)

    def start_svg_to_png_worker(self):
        if self.svg2png_thread is not None:
            return
        svg_path = self.svg_input.text().strip()
        png_path = self.png_output.text().strip()
        if not svg_path or not Path(svg_path).exists():
            QMessageBox.warning(self, lds_tr("変換不可"), lds_tr("入力SVGが見つかりません。"))
            return
        if not png_path:
            self.choose_png()
            png_path = self.png_output.text().strip()
        if not png_path:
            return
        if not png_path.lower().endswith(".png"):
            png_path += ".png"
            self.png_output.setText(png_path)
        self.svg2png_convert_btn.setEnabled(False)
        self.svg2png_status.setText(lds_tr("変換中..."))
        self.svg2png_thread = QThread(self)
        self.svg2png_worker = SvgToPngWorker(
            svg_path,
            png_path,
            self.width_spin.value(),
            self.height_spin.value(),
            self.transparent_check.isChecked(),
        )
        self.svg2png_worker.moveToThread(self.svg2png_thread)
        self.svg2png_thread.started.connect(self.svg2png_worker.run)
        self.svg2png_worker.finished.connect(self.on_svg2png_finished)
        self.svg2png_worker.failed.connect(self.on_svg2png_failed)
        self.svg2png_worker.finished.connect(self.svg2png_thread.quit)
        self.svg2png_worker.failed.connect(self.svg2png_thread.quit)
        self.svg2png_thread.finished.connect(self.svg2png_worker.deleteLater)
        self.svg2png_thread.finished.connect(self.cleanup_svg2png_worker)
        self.svg2png_thread.start()

    @Slot(str)
    def on_svg2png_finished(self, path):
        self.svg2png_status.setText(lds_tr("完了: ") + str(path))
        QMessageBox.information(self, lds_tr("完了"), lds_tr("SVGをPNGへ変換しました。"))

    @Slot(str)
    def on_svg2png_failed(self, error):
        self.svg2png_status.setText(lds_tr("失敗: ") + str(error))
        QMessageBox.warning(self, lds_tr("変換失敗"), str(error))

    def cleanup_svg2png_worker(self):
        try:
            self.svg2png_thread.deleteLater()
        except:
            pass
        self.svg2png_thread = None
        self.svg2png_worker = None
        try:
            self.svg2png_convert_btn.setEnabled(True)
        except:
            pass

    def start_png_frames_to_svg_worker(self):
        if self.png2svg_thread is not None:
            return
        self.png2svg_log.clear()
        input_dir_text = self.png_frames_input.text().strip()
        output_dir_text = self.svg_frames_output.text().strip()
        if not input_dir_text or not Path(input_dir_text).exists():
            QMessageBox.warning(self, lds_tr("変換不可"), lds_tr("PNGフォルダが見つかりません。"))
            return
        if not output_dir_text:
            self.choose_svg_frames_output()
            output_dir_text = self.svg_frames_output.text().strip()
        if not output_dir_text:
            return
        self.png2svg_convert_btn.setEnabled(False)
        self.png2svg_cancel_btn.setEnabled(True)
        self.png2svg_thread = QThread(self)
        self.png2svg_worker = PngToSvgFramesWorker(
            input_dir_text,
            output_dir_text,
            self.frame_prefix_edit.text() or "frame_",
            self.frame_digits_spin.value(),
            self.overwrite_svg_frames_check.isChecked(),
            self.skip_white_check.isChecked(),
        )
        self.png2svg_worker.moveToThread(self.png2svg_thread)
        self.png2svg_thread.started.connect(self.png2svg_worker.run)
        self.png2svg_worker.progress.connect(self.png2svg_log.append)
        self.png2svg_worker.finished.connect(self.on_png2svg_finished)
        self.png2svg_worker.canceled.connect(self.on_png2svg_canceled)
        self.png2svg_worker.failed.connect(self.on_png2svg_failed)
        self.png2svg_worker.finished.connect(self.png2svg_thread.quit)
        self.png2svg_worker.canceled.connect(self.png2svg_thread.quit)
        self.png2svg_worker.failed.connect(self.png2svg_thread.quit)
        self.png2svg_thread.finished.connect(self.png2svg_worker.deleteLater)
        self.png2svg_thread.finished.connect(self.cleanup_png2svg_worker)
        self.png2svg_thread.start()

    def cancel_png_frames_to_svg_worker(self):
        worker = getattr(self, "png2svg_worker", None)
        if worker is not None:
            try:
                worker.request_cancel()
                self.png2svg_log.append(lds_tr("キャンセル要求を送信しました..."))
            except:
                pass

    @Slot(int, int)
    def on_png2svg_finished(self, converted, skipped):
        self.png2svg_log.append(lds_tr("完了 converted/skipped: ") + f"{converted}/{skipped}")
        QMessageBox.information(self, lds_tr("完了"), lds_tr("PNG frames を SVG frames に変換しました。"))

    @Slot(int, int)
    def on_png2svg_canceled(self, converted, skipped):
        self.png2svg_log.append(lds_tr("キャンセル converted/skipped: ") + f"{converted}/{skipped}")
        QMessageBox.information(self, lds_tr("キャンセル"), lds_tr("PNG→SVG変換をキャンセルしました。"))

    @Slot(str)
    def on_png2svg_failed(self, error):
        self.png2svg_log.append(lds_tr("失敗: ") + str(error))
        QMessageBox.warning(self, lds_tr("PNG→SVG変換失敗"), str(error))

    def cleanup_png2svg_worker(self):
        try:
            self.png2svg_thread.deleteLater()
        except:
            pass
        self.png2svg_thread = None
        self.png2svg_worker = None
        try:
            self.png2svg_convert_btn.setEnabled(True)
            self.png2svg_cancel_btn.setEnabled(False)
        except:
            pass


class SimpleTextEditorTool(QWidget):
    def __init__(self, title: str, name_filter: str, default_suffix: str, template_text: str = "", parent=None):
        super().__init__(parent)
        self.name_filter = name_filter
        self.default_suffix = default_suffix
        self.template_text = template_text
        self.current_path = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel(lds_tr(title)))
        self.path_label = QLabel(lds_tr("未保存"))
        self.path_label.setObjectName("SubText")
        top.addWidget(self.path_label, 1)
        layout.addLayout(top)
        btns = QHBoxLayout()
        self.open_btn = QPushButton(lds_tr("開く"))
        self.save_btn = QPushButton(lds_tr("保存"))
        self.save_as_btn = QPushButton(lds_tr("名前を付けて保存"))
        self.clear_btn = QPushButton(lds_tr("クリア"))
        self.template_btn = QPushButton(lds_tr("テンプレート"))
        for b in [self.open_btn, self.save_btn, self.save_as_btn, self.clear_btn, self.template_btn]:
            btns.addWidget(b)
        layout.addLayout(btns)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.editor, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("SubText")
        layout.addWidget(self.status_label)
        self.open_btn.clicked.connect(self.open_file)
        self.save_btn.clicked.connect(self.save_file)
        self.save_as_btn.clicked.connect(self.save_file_as)
        self.clear_btn.clicked.connect(self.editor.clear)
        self.template_btn.clicked.connect(self.insert_template)

    def set_status(self, text):
        self.status_label.setText(str(text))

    def open_file(self):
        path = _lds_open_file_dialog(self, "ファイルを開く", self.name_filter)
        if not path:
            return
        try:
            self.editor.setPlainText(Path(path).read_text(encoding="utf-8"))
            self.current_path = path
            self.path_label.setText(path)
            self.set_status(lds_tr("読み込みました。"))
        except Exception as e:
            QMessageBox.warning(self, lds_tr("読み込み失敗"), str(e))

    def validate_before_save(self) -> bool:
        return True

    def save_file(self):
        if not self.current_path:
            return self.save_file_as()
        if not self.validate_before_save():
            return
        try:
            Path(self.current_path).write_text(self.editor.toPlainText(), encoding="utf-8")
            self.set_status(lds_tr("保存しました: ") + self.current_path)
        except Exception as e:
            QMessageBox.warning(self, lds_tr("保存失敗"), str(e))

    def save_file_as(self):
        path = _lds_save_file_dialog(self, "名前を付けて保存", self.name_filter, self.default_suffix, "")
        if not path:
            return
        if self.default_suffix and "." not in Path(path).name:
            path += "." + self.default_suffix
        self.current_path = path
        self.path_label.setText(path)
        self.save_file()

    def insert_template(self):
        if self.template_text:
            self.editor.setPlainText(self.template_text)
            self.set_status(lds_tr("テンプレートを挿入しました。"))


class JsonEditorTool(SimpleTextEditorTool):
    def __init__(self, parent=None):
        template = json.dumps({
            "id": "my-widget",
            "name": "My Widget",
            "version": "1.0.0",
            "entry": "index.html",
            "permissions": {
                "readAssets": True,
                "writeConfig": True,
                "systemInfo": False,
                "openUrl": False,
                "readTextFile": True
            }
        }, ensure_ascii=False, indent=2)
        super().__init__("JSON / widget.json Editor", "JSON Files (*.json);;All Files (*)", "json", template, parent)
        self.format_btn = QPushButton(lds_tr("整形"))
        self.layout().itemAt(1).layout().addWidget(self.format_btn)
        self.format_btn.clicked.connect(self.format_json)

    def validate_before_save(self) -> bool:
        try:
            json.loads(self.editor.toPlainText() or "{}")
            self.set_status(lds_tr("JSON OK"))
            return True
        except Exception as e:
            QMessageBox.warning(self, lds_tr("JSONエラー"), str(e))
            return False

    def format_json(self):
        try:
            data = json.loads(self.editor.toPlainText() or "{}")
            self.editor.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
            self.set_status(lds_tr("JSONを整形しました。"))
        except Exception as e:
            QMessageBox.warning(self, lds_tr("JSONエラー"), str(e))


class EditorsToolsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        tabs = QTabWidget()
        html_template = """<!doctype html>\n<html lang=\"ja\">\n<head>\n  <meta charset=\"utf-8\">\n  <title>My JSHTML Widget</title>\n</head>\n<body>\n  <div id=\"app\">Hello JSHTML</div>\n  <script src=\"main.js\"></script>\n</body>\n</html>\n"""
        js_template = """document.addEventListener(\"DOMContentLoaded\", async function () {\n  await window.LDSReady;\n  const info = await LDS.getWidgetInfo();\n  console.log(info);\n});\n"""
        tabs.addTab(SimpleTextEditorTool("HTML Editor", "HTML Files (*.html *.htm);;All Files (*)", "html", html_template), lds_tr("HTML"))
        tabs.addTab(JsonEditorTool(), lds_tr("JSON"))
        tabs.addTab(SimpleTextEditorTool("JavaScript Editor", "JavaScript Files (*.js);;All Files (*)", "js", js_template), lds_tr("JavaScript"))
        layout.addWidget(tabs)


class DiagnosticsToolsTab(QWidget):
    def __init__(self, canvas=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        refresh_btn = QPushButton(lds_tr("更新"))
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(refresh_btn)
        layout.addWidget(self.text, 1)
        refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self):
        lines = []
        try:
            canvas = self.canvas
            manager = getattr(canvas, "js_html_views", None)
            lines.append("JSHTML WebEngine available: " + str(getattr(manager, "available", None)))
            lines.append("JSHTML WebEngine error: " + str(getattr(manager, "error", "")))
            audio = getattr(canvas, "audio", None)
            lines.append("Audio backend: " + str(getattr(audio, "backend_name", "unknown")))
            lines.append("Audio fallback: " + str(getattr(audio, "use_fake", False)))
            selected = getattr(canvas, "selected", None)
            lines.append("Selected widget: " + str(getattr(getattr(selected, "cfg", None), "type", None)))
            lines.append("JSHTML widgets dir: " + str(JSHTML_WIDGETS_DIR))
        except Exception as e:
            lines.append("Diagnostics error: " + repr(e))
        self.text.setPlainText("\n".join(lines))


class OtherToolsDialog(QDialog):
    def __init__(self, canvas=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        try:
            theme = get_canvas_studio_theme(canvas) if canvas is not None else DEFAULT_STUDIO_THEME
            self.setWindowOpacity(get_studio_window_opacity(theme))
        except:
            pass
        self.setWindowTitle(lds_tr(f"{APP_NAME} - その他のツール"))
        self.resize(860, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        title = QLabel(lds_tr("🧰 その他のツール"))
        title.setObjectName("Title")
        layout.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(PackageBuilderToolsTab(), lds_tr("Package"))
        tabs.addTab(ImageToolsTab(), lds_tr("Image"))
        tabs.addTab(EditorsToolsTab(), lds_tr("Editors"))
        tabs.addTab(DiagnosticsToolsTab(canvas), lds_tr("Diagnostics"))
        layout.addWidget(tabs, 1)
        close_btn = QPushButton(lds_tr("閉じる"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        try:
            apply_beginner_photoshop_settings_style(self, theme)
        except:
            pass


class WidgetEditor(QDialog):
    def __init__(self, widget: BaseWidget, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.setWindowTitle(lds_tr(f"{APP_NAME} - ウィジェット編集"))
        self.resize(520, 420)

        layout = QFormLayout(self)

        self.title = QLineEdit(widget.cfg.title)
        self.color = QLineEdit(widget.cfg.color)
        self.bg = QLineEdit(widget.cfg.bg)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(widget.cfg.font_size)
        self.mirror_reflect_enabled = QCheckBox(lds_tr("鏡面反射に含める"))
        self.mirror_reflect_enabled.setChecked(bool(getattr(widget.cfg, "mirror_reflect_enabled", True)))

        self.text = QTextEdit()
        self.text.setPlainText(widget.cfg.text)

        color_btn = QPushButton(lds_tr("🎨 色を選択"))
        color_btn.clicked.connect(self.pick_color)

        bg_btn = QPushButton(lds_tr("🖼️ 背景色を選択"))
        bg_btn.clicked.connect(self.pick_bg)

        btns = QHBoxLayout()
        save = QPushButton(lds_tr("💾 保存"))
        cancel = QPushButton(lds_tr("✖ キャンセル"))
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)

        self.jshtml_import_btn = None
        self.jshtml_open_dir_btn = None
        if getattr(widget.cfg, "type", "") == "html_js":
            ensure_jshtml_widget_fields(widget.cfg)
            self.jshtml_import_btn = QPushButton(lds_tr("📦 JSHTML ZIPをインポート"))
            self.jshtml_open_dir_btn = QPushButton(lds_tr("📁 JSHTMLフォルダを開く"))
            self.jshtml_import_btn.clicked.connect(self.import_jshtml_package)
            self.jshtml_open_dir_btn.clicked.connect(self.open_jshtml_folder)

        layout.addRow(lds_tr("タイトル"), self.title)
        layout.addRow(lds_tr("アクセント色"), self.color)
        layout.addRow("", color_btn)
        layout.addRow(lds_tr("背景色"), self.bg)
        layout.addRow("", bg_btn)
        layout.addRow(lds_tr("フォントサイズ"), self.font_size)
        layout.addRow(lds_tr("鏡面反射"), self.mirror_reflect_enabled)
        if self.jshtml_import_btn is not None:
            layout.addRow("", self.jshtml_import_btn)
            layout.addRow("", self.jshtml_open_dir_btn)
        layout.addRow("HTML / Text", self.text)
        layout.addRow(btns)

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.color.text()), self)
        if c.isValid():
            self.color.setText(c.name())

    def pick_bg(self):
        c = QColorDialog.getColor(QColor(self.bg.text()), self)
        if c.isValid():
            self.bg.setText(c.name())

    def import_jshtml_package(self):
        if getattr(self, "importing_jshtml_package", False):
            return

        self.importing_jshtml_package = True

        try:
            dialog = QFileDialog(self, lds_tr("JSHTML ZIPウィジェットを選択"))
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilter("ZIP Files (*.zip)")
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

            try:
                dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            except AttributeError:
                dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            files = dialog.selectedFiles()
            if not files:
                return

            path = files[0]
            if not path:
                return

            import_jshtml_widget_package_to_config(self.widget.cfg, path)
            QMessageBox.information(self, lds_tr("完了"), lds_tr("JSHTMLウィジェットをインポートしました。"))
        except Exception as e:
            QMessageBox.warning(self, lds_tr("インポート失敗"), str(e))
        finally:
            self.importing_jshtml_package = False

    def open_jshtml_folder(self):
        try:
            folder = get_jshtml_widget_dir(self.widget.cfg)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except Exception as e:
            QMessageBox.warning(self, lds_tr("フォルダを開けません"), str(e))

    def apply(self):
        self.widget.cfg.title = self.title.text()
        self.widget.cfg.color = self.color.text()
        self.widget.cfg.bg = self.bg.text()
        self.widget.cfg.font_size = self.font_size.value()
        self.widget.cfg.mirror_reflect_enabled = self.mirror_reflect_enabled.isChecked()
        self.widget.cfg.text = self.text.toPlainText()
