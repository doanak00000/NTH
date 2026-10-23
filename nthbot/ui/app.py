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
import re
import sys
import time
from datetime import date

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRect, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QSplitter,
    QFileDialog, QInputDialog, QMessageBox, QCheckBox, QHeaderView,
    QAbstractItemView,
)

# cho phép chạy trực tiếp file này
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from nthbot.orchestrator import (  # noqa: E402
    AppConfig, Orchestrator, discover_devices, list_tasks, load_task,
)
from nthbot import accounts  # noqa: E402
from nthbot.bot import ACC_DONE_MARK  # noqa: E402
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


_DA_SUA = Qt.UserRole + 1   # ô Giờ người dùng vừa gõ, chưa Lưu


class AccountsPanel(QWidget):
    """Kho tài khoản Zing dùng chung: mọi instance tự lấy acc chưa chạy (nthbot.accounts).

    Cột Trạng thái tự cập nhật mỗi giây theo file (bot ghi vào): trống / ▶ đang chạy x/6 / ⏸ dở / ✓ xong / ✗ lỗi.
    Rê chuột vào Trạng thái: danh sách tên nhân vật đã biết (✓ = xong hôm nay).
    Cột "Chọn": chỉ acc được tick mới được các máy lấy để chạy.
    Cột "Rút ví": tick = lúc treo bán bot bấm "Rút vào ví"; bỏ tick = để người chơi tự rút.
    Cột "Giờ": trống = chạy ngay; gõ HH:MM = hẹn giờ. Bot xong nhân vật 1 -> giờ hẹn tự đổi = giờ xong đó.
    """
    C_CHON, C_USER, C_PASS, C_RUT, C_GIO, C_ST = range(6)

    def __init__(self, log, private=False):
        super().__init__()
        self.log = log
        self.private = private   # True = kho acc private: không quét xu / không lên web
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("🔒 Kho acc PRIVATE (không quét xu, không đưa gì lên web):" if private else
                             "Kho tài khoản Zing (các máy tự lấy acc được tick Chọn, chưa chạy):"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Chọn", "Tài khoản", "Mật khẩu", "Rút ví", "Giờ", "Trạng thái"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for c in (self.C_CHON, self.C_RUT, self.C_GIO):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        lay.addWidget(self.table, 1)

        btns = QHBoxLayout()
        for text, fn in [("+ Thêm", self._add), ("− Xoá", self._remove), ("▲", lambda: self._move(-1)),
                         ("▼", lambda: self._move(1)), ("↺ Reset trạng thái", self._reset),
                         ("💾 Lưu", self._save)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        lay.addLayout(btns)

        accounts.release()   # mở lại tool -> acc "đang chạy" cũ (tool tắt ngang) về "chưa chạy"
        for a in accounts.load():
            if a["private"] != private:
                continue
            self._add(a["user"], a["pass"], a["status"], a["nv_xong"], a["rut_vi"], a["nhan_vat"], a["chon"],
                      a["gio"], a["gio_ngay"])
        self.table.itemChanged.connect(self._sua_o)

    @staticmethod
    def _status_text(st, nv=0, so_loi=0):
        loi = f" · {so_loi} nv lỗi" if so_loi else ""      # nhân vật có bước hụt hôm nay (phiếu kết quả)
        if st.startswith(accounts.RUNNING):                 # đang làm nhân vật thứ nv+1
            return f"▶ đang chạy {min(nv + 1, 6)}/6 ({st[len(accounts.RUNNING):]}){loi}"
        if not st and nv:
            return f"⏸ dở {nv}/6{loi}"
        if st == "done" and (0 < nv < 6 or so_loi):        # thiếu lượt / có nhân vật lỗi -> cảnh báo, đừng im lặng ✓
            return f"⚠ xong {nv}/6{loi}"
        return {"done": "✓ xong", "error": "✗ lỗi"}.get(st, "") + (loi if st else "")

    @staticmethod
    def _tooltip(nhan_vat, phieu=None):
        """Nhân vật hôm nay (theo thứ tự làm): ✓ / ⚠ + bước lỗi; dưới là các tên khác đã biết."""
        hom_nay = accounts.phieu_hom_nay({"phieu": phieu or {}})
        dong = [("⚠ " if loi else "✓ ") + t + time.strftime(" (%H:%M)", time.localtime(p["luc"]))
                + (" — " + ", ".join(loi) if loi else "") for t, p, loi in hom_nay]
        da = {t for t, _, _ in hom_nay}
        cu = [("✓ " if t >= accounts.moc_reset() else "· ") + ten for ten, t in (nhan_vat or {}).items() if ten not in da]
        if not dong and not cu:
            return "Chưa biết tên nhân vật (bot ghi lại khi chạy)"
        return "\n".join((["Hôm nay:"] + dong if dong else []) + (["", "Tên đã biết:"] + cu if cu else []))

    @staticmethod
    def _gio_text(gio, gio_ngay):
        g = accounts.gio_hom_nay({"gio": gio, "gio_ngay": gio_ngay})
        return g.strftime("%H:%M") if g else ""

    def _add(self, user="", pw="", status="", nv=0, rut_vi=True, nhan_vat=None, chon=True, gio="", gio_ngay=""):
        i = self.table.rowCount()
        self.table.insertRow(i)
        ch = QTableWidgetItem()
        ch.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        ch.setCheckState(Qt.Checked if chon else Qt.Unchecked)
        self.table.setItem(i, self.C_CHON, ch)
        self.table.blockSignals(True)
        for c, v in ((self.C_USER, user), (self.C_PASS, pw)):
            it = QTableWidgetItem(v)
            if self.private and v:
                it.setData(Qt.UserRole, v)   # giá trị thật; chữ hiện được _an() đổi thành tên giả
            self.table.setItem(i, c, it)
        self.table.blockSignals(False)
        rut = QTableWidgetItem()
        rut.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        rut.setCheckState(Qt.Checked if rut_vi else Qt.Unchecked)
        self.table.setItem(i, self.C_RUT, rut)
        self.table.blockSignals(True)
        g = QTableWidgetItem(self._gio_text(gio, gio_ngay))
        g.setData(Qt.UserRole, (gio, gio_ngay))
        g.setToolTip("Trống = chạy ngay. Gõ HH:MM = hẹn giờ. Bot xong nhân vật 1 thì giờ hẹn tự đổi = giờ xong đó (mai chạy lúc ấy).")
        self.table.setItem(i, self.C_GIO, g)
        self.table.blockSignals(False)
        st = QTableWidgetItem(self._status_text(status, nv))
        st.setData(Qt.UserRole, (status, nv))
        st.setToolTip(self._tooltip(nhan_vat))
        st.setFlags(st.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(i, self.C_ST, st)
        self._an()
        if not user:
            self.table.setCurrentCell(i, self.C_USER)
            self.table.editItem(self.table.item(i, self.C_USER))

    def _gia_tri(self, i, c):
        """Giá trị thật của ô tk / mk (kho private: chữ hiện là tên giả, giá trị thật nằm trong UserRole)."""
        it = self.table.item(i, c)
        if it is None:
            return ""
        return (it.data(Qt.UserRole) or "") if self.private else it.text()

    def _an(self):
        """Kho private: ô tk / mk chỉ hiện 'tk testN' / 'mk testN' (N = dòng), không lộ tk/mk thật trên UI."""
        if not self.private:
            return
        self.table.blockSignals(True)
        for i in range(self.table.rowCount()):
            for c, ten in ((self.C_USER, "tk"), (self.C_PASS, "mk")):
                it = self.table.item(i, c)
                if it is not None and it.data(Qt.UserRole):
                    it.setText(f"{ten} test{i + 1}")
        self.table.blockSignals(False)

    def _sua_o(self, it):
        """Gõ giờ hẹn -> chuẩn hoá HH:MM, ngày đặt = hôm nay.
        Gõ vào ô tk / mk của kho private -> chữ vừa gõ là giá trị thật, rồi hiện lại tên giả."""
        if it.column() == self.C_GIO:
            t = it.text().strip()
            m = re.fullmatch(r"(\d{1,2})[:hH.](\d{2})", t)
            ok = m and int(m[1]) < 24 and int(m[2]) < 60
            if t and not ok:
                QMessageBox.warning(self, "Giờ sai", f"'{t}' không phải giờ hợp lệ (vd 10:00). Đã để trống = chạy ngay.")
            gio = f"{int(m[1]):02d}:{m[2]}" if t and ok else ""
            self.table.blockSignals(True)
            it.setData(Qt.UserRole, (gio, date.today().isoformat() if gio else ""))
            it.setData(_DA_SUA, True)        # người dùng gõ -> Lưu ghi giờ này; ô không sửa thì theo file (bot dời giờ)
            it.setText(gio)
            self.table.blockSignals(False)
            return
        if not self.private or it.column() not in (self.C_USER, self.C_PASS):
            return
        self.table.blockSignals(True)
        it.setData(Qt.UserRole, it.text().strip() if it.column() == self.C_USER else it.text())
        self.table.blockSignals(False)
        self._an()

    def _selected_rows(self):
        return sorted({ix.row() for ix in self.table.selectedIndexes()})

    def _remove(self):
        for i in reversed(self._selected_rows()):
            self.table.removeRow(i)
        self._an()

    def _move(self, step):
        i = self.table.currentRow()
        j = i + step
        if i < 0 or not 0 <= j < self.table.rowCount():
            return
        self.table.blockSignals(True)   # setItem phát itemChanged -> _sua_o sẽ lấy tên giả làm tk thật
        for c in range(self.table.columnCount()):
            a, b = self.table.takeItem(i, c), self.table.takeItem(j, c)
            self.table.setItem(i, c, b)
            self.table.setItem(j, c, a)
        self.table.blockSignals(False)
        self.table.selectRow(j)
        self._an()

    def _rows_idx(self):
        """Chỉ số dòng có tk (cùng thứ tự với _rows)."""
        return [i for i in range(self.table.rowCount()) if self._gia_tri(i, self.C_USER).strip()]

    def _rows(self):
        out = []
        for i in range(self.table.rowCount()):
            u = self._gia_tri(i, self.C_USER).strip()
            if u:
                st, nv = self.table.item(i, self.C_ST).data(Qt.UserRole) or ("", 0)
                gio, gio_ngay = self.table.item(i, self.C_GIO).data(Qt.UserRole) or ("", "")
                out.append({"user": u, "gio": gio, "gio_ngay": gio_ngay,
                            "pass": self._gia_tri(i, self.C_PASS),
                            "status": st, "nv_xong": nv, "cap_nhat": 0,
                            "rut_vi": self.table.item(i, self.C_RUT).checkState() == Qt.Checked,
                            "chon": self.table.item(i, self.C_CHON).checkState() == Qt.Checked,
                            "private": self.private, "nhan_vat": {}})
        return out

    def _save(self, quiet=False):
        rows = self._rows()
        # 2 kho (public/private) chung 1 file -> giữ nguyên acc của kho kia
        others = [a for a in accounts.load() if a["private"] != self.private]
        users = [r["user"] for r in rows] + [a["user"] for a in others]
        dup = {u for u in users if users.count(u) > 1}
        if dup:
            QMessageBox.warning(self, "Trùng tài khoản", f"Tk bị nhập 2 lần: {', '.join(dup)}")
            return
        # trạng thái / tiến độ / tên nhân vật do bot ghi trong file là mới nhất -> giữ lại khi lưu
        live = {a["user"]: a for a in accounts.load()}
        for i, r in zip(self._rows_idx(), rows):
            if r["user"] in live:
                r.update({k: live[r["user"]][k] for k in ("status", "nv_xong", "cap_nhat", "nhan_vat", "phieu")})
                if not self.table.item(i, self.C_GIO).data(_DA_SUA):   # giờ bot tự dời giữ nguyên
                    r.update({k: live[r["user"]][k] for k in ("gio", "gio_ngay")})
        self.table.blockSignals(True)   # setData phát itemChanged -> _sua_o sẽ đánh dấu lại là 'người dùng sửa'
        for i in range(self.table.rowCount()):
            self.table.item(i, self.C_GIO).setData(_DA_SUA, None)
        self.table.blockSignals(False)
        accounts.save(others + rows if self.private else rows + others)
        if not quiet:
            self.log(f"Đã lưu {len(rows)} tài khoản Zing: {accounts.path()}")

    def _reset(self):
        """Đưa acc đã chọn (không chọn = tất cả) về 'chưa chạy', xoá tiến độ — trừ acc đang chạy.
        (Bình thường không cần: qua 5h sáng ngày kế tiếp kho tự reset.)"""
        self._save(quiet=True)
        rows = self._selected_rows() or range(self.table.rowCount())
        pick = {self._gia_tri(i, self.C_USER).strip() for i in rows}
        accs = accounts.load()
        for a in accs:
            if a["user"] in pick and not a["status"].startswith(accounts.RUNNING):
                a["status"], a["nv_xong"] = "", 0
        accounts.save(accs)
        self.refresh_status()

    def refresh_status(self):
        live = {a["user"]: a for a in accounts.load()}
        for i in range(self.table.rowCount()):
            u = self._gia_tri(i, self.C_USER).strip()
            st = self.table.item(i, self.C_ST)
            if u not in live:
                continue
            a = live[u]
            if tuple(st.data(Qt.UserRole) or ()) != (a["status"], a["nv_xong"]):
                st.setData(Qt.UserRole, (a["status"], a["nv_xong"]))
            chu = self._status_text(a["status"], a["nv_xong"], sum(1 for *_, l in accounts.phieu_hom_nay(a) if l))
            if st.text() != chu:
                st.setText(chu)
            tip = self._tooltip(a["nhan_vat"], a["phieu"])
            if st.toolTip() != tip:
                st.setToolTip(tip)
            g = self.table.item(i, self.C_GIO)   # bot dời giờ hẹn (xong nhân vật 1) -> hiện theo file
            moi = (a["gio"], a["gio_ngay"])
            if not g.data(_DA_SUA) and tuple(g.data(Qt.UserRole) or ("", "")) != moi:
                self.table.blockSignals(True)
                g.setData(Qt.UserRole, moi)
                g.setText(self._gio_text(*moi))
                self.table.blockSignals(False)


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
        self.acc_lines = {}   # tiến độ nhân vật theo máy (ô log vàng)

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
        top.addWidget(QLabel("Giãn cách treo tơ:"))
        self.gian_cach_box = QComboBox()
        for text, sec in [("Treo liền", 0), ("30 giây", 30), ("40 giây", 40), ("45 giây", 45), ("1 phút", 60),
                          ("3 phút", 180), ("5 phút", 300)]:
            self.gian_cach_box.addItem(text, sec)
        self.gian_cach_box.setCurrentIndex(self.gian_cach_box.findData(30))   # mặc định 30s
        top.addWidget(self.gian_cach_box)
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
        self.acc_panel = AccountsPanel(self.log_line)
        ll.addWidget(self.acc_panel, 1)
        self.acc_private = AccountsPanel(self.log_line, private=True)   # hiện khi bật 'Chế độ thử nghiệm'
        self.acc_private.hide()
        ll.addWidget(self.acc_private, 1)
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
        self.btn_thu_nghiem = QPushButton("🧪 Chế độ thử nghiệm")
        self.btn_thu_nghiem.setCheckable(True)
        self.btn_thu_nghiem.toggled.connect(self.acc_private.setVisible)
        ml.addWidget(self.btn_thu_nghiem)
        splitter.addWidget(mid)

        # phải: log
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Log:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        # Chỉ giữ 10 dòng log mới nhất (tự xoá dòng cũ cho đỡ nhiễu).
        self.log_view.document().setMaximumBlockCount(10)
        self.log_view.setStyleSheet("background:#0d0d0d;color:#ccc;font-family:monospace;font-size:12px;")
        rl.addWidget(self.log_view, 1)

        # Ô log riêng cho tiến độ tài khoản (chữ vàng): "acc 1 hoàn thành", ...
        rl.addWidget(QLabel("Tiến độ tài khoản:"))
        self.acc_log_view = QTextEdit()
        self.acc_log_view.setReadOnly(True)
        self.acc_log_view.setMaximumHeight(200)
        self.acc_log_view.setStyleSheet(
            "background:#0d0d0d;color:#ffd000;font-family:monospace;font-size:12px;font-weight:bold;"
        )
        rl.addWidget(self.acc_log_view)

        b_clear = QPushButton("Xoá log")
        b_clear.clicked.connect(self._clear_logs)
        rl.addWidget(b_clear)
        splitter.addWidget(right)

        splitter.setSizes([420, 480, 320])
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
        dang_chon = self.task_box.currentText() or "thanh_nhai_thu_6acc.yaml"   # mặc định: Thanh Nhai Thư 6 acc
        self.task_box.clear()
        tasks = list_tasks(self.cfg)
        self.task_box.addItems(tasks)
        if dang_chon in tasks:
            self.task_box.setCurrentText(dang_chon)
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

        task.variables["gian_cach_treo"] = self.gian_cach_box.currentData()
        self.acc_panel._save(quiet=True)   # acc vừa gõ chưa bấm Lưu vẫn được các máy thấy
        self.acc_private._save(quiet=True)
        for _i, d in chosen:
            # máy đang chạy -> bỏ qua: tạo runner mới đè lên thì runner cũ mất khỏi danh sách, Stop không dừng được,
            #  2 bot tranh 1 LDPlayer (23/10 21:11: bấm Start 2 lần -> 3 bot, bot chờ giờ hẹn tắt LDPlayer của bot kia)
            if (cu := self.runners.get(d.name)) and cu.thread and cu.thread.is_alive():
                self.log_line(f"{d.name} đang chạy -> bỏ qua (bấm Stop trước nếu muốn Start lại).")
                continue
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
        self.acc_panel.refresh_status()
        self.acc_private.refresh_status()
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

    def _clear_logs(self):
        self.log_view.clear()
        self.acc_log_view.clear()
        self.acc_lines.clear()

    def _on_log(self, name, msg):
        # Mốc hoàn thành 1 acc/1 vòng -> đưa sang ô log vàng riêng (không nhiễu log chính).
        if ACC_DONE_MARK in msg:
            # mỗi máy 1 khối tiến độ; sang tk mới (⟦MOI⟧) thì xoá tiến độ tk cũ của máy đó
            clean = msg.replace(ACC_DONE_MARK, "").strip()
            if "⟦MOI⟧" in clean:
                self.acc_lines[name] = [clean.replace("⟦MOI⟧", "").strip()]
            else:
                self.acc_lines.setdefault(name, []).append(clean)
            self.acc_log_view.setPlainText("\n\n".join(
                f"<{n}>\n" + "\n".join(lines) for n, lines in self.acc_lines.items()))
            return
        self.log_view.append(f"<{name}> {msg}")

    def _on_state(self, name, state):
        for i, d in enumerate(self.devices):
            if d.name == name:
                self.table.setItem(i, 2, QTableWidgetItem(state))


def main():
    app = QApplication(sys.argv)
    args = [a for a in sys.argv[1:] if a != "--start"]
    cfg_path = args[0] if args else "config.yaml"
    win = MainWindow(cfg_path)
    win.show()
    from nthbot import xu
    xu.nghe_lenh(log=lambda m: win.bridge.log.emit("web", m))   # đổi giờ chạy acc public từ web
    if "--start" in sys.argv:   # python run.py --start: tick mọi instance + Start task đang chọn (mặc định TNT 6 acc)
        def _tu_start():
            win._check_all(True)
            win.start_selected()
        QTimer.singleShot(1500, _tu_start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
