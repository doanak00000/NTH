"""
Giao diện desktop (PySide6) cho NTH Bot.

Tính năng:
- Tự dò & liệt kê các instance (LDPlayer) — tick chọn instance muốn chạy.
- Chọn task (.yaml) và Start/Stop (chạy song song nhiều instance).
- Xem màn hình trực tiếp của instance đang chọn.
- Bấm vào ảnh preview để lấy toạ độ (x,y) game -> tiện viết bước tap.
- "Cắt ảnh mẫu": kéo chuột chọn vùng -> lưu thành template .png.
- Bảng log realtime.
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRect, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QSplitter,
    QFileDialog, QInputDialog, QMessageBox, QCheckBox, QHeaderView,
)

# cho phép chạy trực tiếp file này
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from nthbot.orchestrator import (  # noqa: E402
    AppConfig, Orchestrator, discover_devices, list_tasks, load_task,
)
from nthbot.vision import imwrite_unicode  # noqa: E402


def cv_to_qpixmap(img: np.ndarray) -> QPixmap:
    """BGR numpy -> QPixmap."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class Bridge(QObject):
    """Cầu nối tín hiệu từ luồng bot -> UI (Qt yêu cầu update UI ở main thread)."""
    log = Signal(str, str)
    state = Signal(str, str)


class PreviewLabel(QLabel):
    """Label hiển thị màn hình; hỗ trợ click lấy toạ độ và kéo chọn vùng cắt."""
    clicked = Signal(int, int)              # toạ độ theo ảnh gốc
    region_selected = Signal(int, int, int, int)

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 240)
        self.setStyleSheet("background:#111;color:#888;")
        self.setText("Chọn 1 instance để xem màn hình")
        self._img_size = (0, 0)     # (w,h) ảnh gốc
        self._draw_rect = None      # vùng pixmap hiển thị (để map toạ độ)
        self.crop_mode = False
        self._start = None
        self._cur_rect = None

    def set_image(self, img: np.ndarray):
        self._img_size = (img.shape[1], img.shape[0])
        pix = cv_to_qpixmap(img)
        scaled = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # tính vùng vẽ để map toạ độ click <-> ảnh gốc
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        self._draw_rect = QRect(x, y, scaled.width(), scaled.height())
        if self._cur_rect:
            p = QPainter(scaled)
            p.setPen(QPen(QColor(0, 200, 0), 2))
            r = self._cur_rect
            p.drawRect(r.translated(-x, -y))
            p.end()
        self.setPixmap(scaled)

    def _map_to_image(self, pos: QPoint):
        if not self._draw_rect or not self._draw_rect.contains(pos):
            return None
        iw, ih = self._img_size
        rel_x = (pos.x() - self._draw_rect.x()) / self._draw_rect.width()
        rel_y = (pos.y() - self._draw_rect.y()) / self._draw_rect.height()
        return int(rel_x * iw), int(rel_y * ih)

    def mousePressEvent(self, e):
        if self.crop_mode:
            self._start = e.position().toPoint()
        else:
            mapped = self._map_to_image(e.position().toPoint())
            if mapped:
                self.clicked.emit(*mapped)

    def mouseMoveEvent(self, e):
        if self.crop_mode and self._start:
            self._cur_rect = QRect(self._start, e.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.crop_mode and self._start:
            end = e.position().toPoint()
            a = self._map_to_image(self._start)
            b = self._map_to_image(end)
            self._start = None
            self._cur_rect = None
            if a and b:
                x1, y1 = a
                x2, y2 = b
                self.region_selected.emit(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


class MainWindow(QMainWindow):
    def __init__(self, config_path="config.yaml"):
        super().__init__()
        self.setWindowTitle("NTH Bot - LDPlayer Auto")
        self.resize(1180, 720)

        self.cfg = AppConfig.load(config_path)
        self.orch = Orchestrator(self.cfg)
        self.devices = []
        self.runners = {}
        self.cur_screen = None

        self.bridge = Bridge()
        self.bridge.log.connect(self._on_log)
        self.bridge.state.connect(self._on_state)

        self._build_ui()
        self.refresh_devices()
        self.refresh_tasks()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_preview)
        self.timer.start(1000)  # cập nhật preview mỗi giây

    # ---- dựng giao diện -------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # thanh điều khiển trên cùng
        top = QHBoxLayout()
        self.task_box = QComboBox()
        top.addWidget(QLabel("Task:"))
        top.addWidget(self.task_box, 2)
        btn_reload_task = QPushButton("↻ Tải lại task")
        btn_reload_task.clicked.connect(self.refresh_tasks)
        top.addWidget(btn_reload_task)
        btn_refresh = QPushButton("↻ Dò instance")
        btn_refresh.clicked.connect(self.refresh_devices)
        top.addWidget(btn_refresh)
        top.addStretch()
        self.btn_start = QPushButton("▶ Start (đã chọn)")
        self.btn_start.clicked.connect(self.start_selected)
        self.btn_start.setStyleSheet("background:#1b7f3b;color:white;font-weight:bold;padding:6px;")
        top.addWidget(self.btn_start)
        self.btn_stop = QPushButton("■ Stop tất cả")
        self.btn_stop.clicked.connect(self.stop_all)
        self.btn_stop.setStyleSheet("background:#a33;color:white;font-weight:bold;padding:6px;")
        top.addWidget(self.btn_stop)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # trái: bảng instance
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Instances (tick để chọn chạy):"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Chọn", "Tên", "Trạng thái"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._update_preview)
        ll.addWidget(self.table)
        chk_row = QHBoxLayout()
        b_all = QPushButton("Chọn tất cả")
        b_all.clicked.connect(lambda: self._check_all(True))
        b_none = QPushButton("Bỏ chọn")
        b_none.clicked.connect(lambda: self._check_all(False))
        chk_row.addWidget(b_all)
        chk_row.addWidget(b_none)
        ll.addLayout(chk_row)
        splitter.addWidget(left)

        # giữa: preview
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.addWidget(QLabel("Màn hình (bấm để lấy toạ độ):"))
        self.preview = PreviewLabel()
        self.preview.clicked.connect(self._on_preview_click)
        self.preview.region_selected.connect(self._on_region_selected)
        ml.addWidget(self.preview, 1)
        self.coord_label = QLabel("Toạ độ: -")
        ml.addWidget(self.coord_label)
        prow = QHBoxLayout()
        self.btn_crop = QPushButton("✂ Cắt ảnh mẫu")
        self.btn_crop.setCheckable(True)
        self.btn_crop.clicked.connect(self._toggle_crop)
        prow.addWidget(self.btn_crop)
        b_shot = QPushButton("📷 Lưu screenshot")
        b_shot.clicked.connect(self._save_screenshot)
        prow.addWidget(b_shot)
        ml.addLayout(prow)
        splitter.addWidget(mid)

        # phải: log
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Log:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background:#0d0d0d;color:#ccc;font-family:monospace;font-size:12px;")
        rl.addWidget(self.log_view)
        b_clear = QPushButton("Xoá log")
        b_clear.clicked.connect(self.log_view.clear)
        rl.addWidget(b_clear)
        splitter.addWidget(right)

        splitter.setSizes([300, 520, 360])
        self.status = self.statusBar()
        self.status.showMessage(f"adb: {self.cfg.adb_path} | package: {self.cfg.game_package or '(chưa đặt)'}")

    # ---- devices / tasks ------------------------------------------------
    def refresh_devices(self):
        self.devices = discover_devices(self.cfg)
        self.table.setRowCount(len(self.devices))
        for i, d in enumerate(self.devices):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked)
            self.table.setItem(i, 0, chk)
            self.table.setItem(i, 1, QTableWidgetItem(d.name))
            self.table.setItem(i, 2, QTableWidgetItem("idle"))
        self.log_line(f"Tìm thấy {len(self.devices)} instance.")

    def refresh_tasks(self):
        self.task_box.clear()
        tasks = list_tasks(self.cfg)
        self.task_box.addItems(tasks)
        if not tasks:
            self.log_line("Chưa có task nào trong thư mục tasks/.")

    def _check_all(self, checked: bool):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _selected_devices(self):
        out = []
        for i, d in enumerate(self.devices):
            if self.table.item(i, 0).checkState() == Qt.Checked:
                out.append((i, d))
        return out

    def _current_device(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.devices):
            return self.devices[row]
        return None

    # ---- chạy bot -------------------------------------------------------
    def start_selected(self):
        task_file = self.task_box.currentText()
        if not task_file:
            QMessageBox.warning(self, "Thiếu task", "Hãy chọn 1 task.")
            return
        chosen = self._selected_devices()
        if not chosen:
            QMessageBox.warning(self, "Chưa chọn", "Tick ít nhất 1 instance.")
            return
        try:
            task = load_task(self.cfg, task_file)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi task", f"Đọc task lỗi:\n{e}")
            return

        for _i, d in chosen:
            runner = self.orch.make_runner(
                d, task,
                on_log=lambda name, msg: self.bridge.log.emit(name, msg),
                on_state=lambda name, st: self.bridge.state.emit(name, st),
            )
            self.runners[d.name] = runner
            runner.start()
        self.log_line(f"Đã start {len(chosen)} instance với task '{task.name}'.")

    def stop_all(self):
        for r in self.runners.values():
            r.stop()
        self.log_line("Đã gửi lệnh Stop tới tất cả.")

    # ---- preview --------------------------------------------------------
    def _update_preview(self):
        d = self._current_device()
        if not d:
            return
        try:
            img = d.screencap()
        except Exception:  # noqa: BLE001
            # có thể chưa connect -> thử connect lại 1 lần
            d.connect()
            try:
                img = d.screencap()
            except Exception as e:  # noqa: BLE001
                self.preview.setText(f"Không chụp được màn hình:\n{e}\n\n"
                                     f"Kiểm tra: LDPlayer đang chạy? ADB đã bật? đúng cổng {d.serial}?")
                return
        self.cur_screen = img
        self.preview.set_image(img)

    def _on_preview_click(self, x, y):
        self.coord_label.setText(f"Toạ độ: x={x}, y={y}   (copy vào bước tap)")

    def _toggle_crop(self, checked):
        self.preview.crop_mode = checked
        self.coord_label.setText("Chế độ cắt: kéo chuột chọn vùng nút/icon..." if checked
                                 else "Toạ độ: -")

    def _on_region_selected(self, x, y, w, h):
        self.btn_crop.setChecked(False)
        self.preview.crop_mode = False
        if self.cur_screen is None or w < 4 or h < 4:
            return
        crop = self.cur_screen[y:y + h, x:x + w]
        name, ok = QInputDialog.getText(self, "Lưu ảnh mẫu",
                                        "Tên file (vd nut_nhiem_vu.png):")
        if not ok or not name:
            return
        if not name.endswith(".png"):
            name += ".png"
        os.makedirs(self.cfg.templates_dir, exist_ok=True)
        path = os.path.join(self.cfg.templates_dir, name)
        imwrite_unicode(path, crop)
        self.log_line(f"Đã lưu ảnh mẫu: {path}  ({w}x{h})")

    def _save_screenshot(self):
        if self.cur_screen is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu screenshot", "screenshot.png",
                                              "PNG (*.png)")
        if path:
            imwrite_unicode(path, self.cur_screen)
            self.log_line(f"Đã lưu: {path}")

    # ---- log / state ----------------------------------------------------
    def log_line(self, msg: str):
        self.log_view.append(msg)

    def _on_log(self, name, msg):
        self.log_view.append(f"<{name}> {msg}")

    def _on_state(self, name, state):
        for i, d in enumerate(self.devices):
            if d.name == name:
                self.table.setItem(i, 2, QTableWidgetItem(state))


def main():
    app = QApplication(sys.argv)
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    win = MainWindow(cfg_path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
