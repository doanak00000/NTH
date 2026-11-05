"""
Điều khiển Nghịch Thủy Hàn bản PC (cửa sổ "Nghịch Thủy Hàn", mở qua launcher Level Up) thay cho adb.

- Chụp: PrintWindow vùng client (chạy cả khi cửa sổ bị che), thu về 960x540 -> dùng chung ảnh mẫu / toạ độ bản mobile.
- Bấm/kéo/gõ: PostMessage chuột/phím thẳng vào cửa sổ -> KHÔNG chiếm chuột thật, người dùng vẫn dùng máy được.
- Toạ độ tool luôn ở hệ 960x540; nhân theo kích thước client thật (1280x720 -> x4/3).
"""

from __future__ import annotations

import ctypes
import re
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

import numpy as np

from .adb import AdbError, Device

try:
    import cv2
except ImportError:
    cv2 = None

W, H = 960, 540                       # hệ toạ độ chung với bản mobile (ảnh mẫu chụp ở 960x540)
# UI: ô 'Cho phép mượn chuột + bàn phím' (mặc định bật). Tắt -> bước cần chuột/phím thật đứng chờ tới khi bật lại
CHO_PHEP_CHUOT = threading.Event()
CHO_PHEP_CHUOT.set()
TIEU_DE = "Nghịch Thủy Hàn"
_u = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
_g = ctypes.windll.gdi32 if hasattr(ctypes, "windll") else None
if _u:
    try:
        _u.SetProcessDPIAware()       # toạ độ client theo pixel thật, không bị Windows scale
    except Exception:  # noqa: BLE001
        pass

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102
# keycode Android -> phím Windows (chỉ những phím tool dùng)
_VK = {"4": 0x1B, "KEYCODE_BACK": 0x1B, "KEYCODE_ESCAPE": 0x1B, "KEYCODE_MOVE_END": 0x23, "123": 0x23,
       "KEYCODE_DEL": 0x08, "67": 0x08, "KEYCODE_ENTER": 0x0D, "66": 0x0D}


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("a", ctypes.c_int32), ("b", ctypes.c_int32),
                ("c", ctypes.c_uint32), ("d", ctypes.c_uint32)]


def tim_cua_so(tieu_de: str = TIEU_DE) -> int:
    return _u.FindWindowW(None, tieu_de) if _u else 0


def doi_toa_do(x, y, cw, ch) -> tuple[int, int]:
    """Toạ độ hệ 960x540 -> pixel client thật."""
    return int(round(x * cw / W)), int(round(y * ch / H))


def toa_do_sendevent(cmd: str) -> list[tuple[int, int]]:
    """Lấy chuỗi điểm (x, y) từ lệnh `sendevent ... 3 53 x; sendevent ... 3 54 y` (keo_that của custom.py)."""
    pts, x = [], None
    for code, val in re.findall(r"sendevent \S+ 3 (53|54) (\d+)", cmd):
        if code == "53":
            x = int(val)
        elif x is not None:
            pts.append((x, int(val)))
    return pts


@dataclass
class PcDevice(Device):
    """Cửa sổ game PC. serial = tiêu đề cửa sổ."""

    package: str = ""                 # game_package (để current_app trả đúng tên như bản mobile)
    _tick_tool: int = 0               # GetTickCount lần cuối tool tự click/gõ thật (cho_ranh_tay bỏ qua chính nó)

    @property
    def loai_may(self) -> str:
        return "PC"

    def _hwnd(self) -> int:
        h = tim_cua_so(self.serial)
        if not h:
            raise AdbError(f"Không thấy cửa sổ game PC '{self.serial}' (game chưa mở?)")
        return h

    def _client(self, h) -> tuple[int, int]:
        if _u.IsIconic(h):             # thu nhỏ -> game ngừng vẽ: mở lại cửa sổ nhưng KHÔNG giành focus
            _u.ShowWindow(h, 4)        # SW_SHOWNOACTIVATE
            time.sleep(1.5)
        r = wintypes.RECT()
        _u.GetClientRect(h, ctypes.byref(r))
        if not r.right or not r.bottom:
            # (02/11) game tự co cửa sổ về 0x0 khi bị ẩn -> trả về client 1280x720, không giành focus/không đổi lớp
            # shortcut: viền cửa sổ đo trên Win10 (16x39); theme/DPI khác thì client lệch vài px, ảnh vẫn được thu về 960x540
            w = wintypes.RECT()
            _u.GetWindowRect(h, ctypes.byref(w))
            _u.SetWindowPos(h, 0, w.left, max(w.top, 0), 1280 + 16, 720 + 39, 0x0014)   # NOZORDER | NOACTIVATE
            time.sleep(1.5)
            _u.GetClientRect(h, ctypes.byref(r))
        if not r.right or not r.bottom:
            raise AdbError("Cửa sổ game PC đang thu nhỏ (minimize) -> không chụp/bấm được, mở lại cửa sổ")
        return r.right, r.bottom

    # ---- kết nối ----------------------------------------------------------
    def connect(self) -> bool:
        return bool(tim_cua_so(self.serial))

    def is_online(self) -> bool:
        return self.connect()

    def getprop(self, name: str) -> str:
        return "1" if name == "sys.boot_completed" and self.connect() else ""

    # ---- chụp -------------------------------------------------------------
    def screencap(self) -> np.ndarray:
        h = self._hwnd()
        w, hh = self._client(h)
        hdc = _u.GetDC(h)
        mdc = _g.CreateCompatibleDC(hdc)
        bmp = _g.CreateCompatibleBitmap(hdc, w, hh)
        try:
            _g.SelectObject(mdc, bmp)
            if not _u.PrintWindow(h, mdc, 3):          # PW_CLIENTONLY | PW_RENDERFULLCONTENT (game DirectX)
                raise AdbError("PrintWindow thất bại")
            bi = _BIH(ctypes.sizeof(_BIH), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = (ctypes.c_char * (w * hh * 4))()
            _g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
        finally:
            _g.DeleteObject(bmp)
            _g.DeleteDC(mdc)
            _u.ReleaseDC(h, hdc)
        img = np.frombuffer(buf, np.uint8).reshape(hh, w, 4)[:, :, :3]
        return img.copy() if (w, hh) == (W, H) else cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)

    # ---- chuột / phím (PostMessage: không chiếm chuột thật) ----------------
    def _chuot(self, msg, x, y, h, cw, ch, wparam=0):
        px, py = doi_toa_do(x, y, cw, ch)
        _u.PostMessageW(h, msg, wparam, (py << 16) | (px & 0xFFFF))

    def tap(self, x: int, y: int, jitter: int = 0):
        import random
        if jitter:
            x += random.randint(-jitter, jitter)
            y += random.randint(-jitter, jitter)
        h = self._hwnd()
        cw, ch = self._client(h)
        self._chuot(WM_MOUSEMOVE, x, y, h, cw, ch)
        time.sleep(0.03)
        self._chuot(WM_LBUTTONDOWN, x, y, h, cw, ch, 1)
        time.sleep(0.07)
        self._chuot(WM_LBUTTONUP, x, y, h, cw, ch)

    def keo(self, pts: list[tuple[int, int]], gap: float = 0.01):
        """Kéo chuột (giữ nút trái) qua các điểm."""
        if not pts:
            return
        h = self._hwnd()
        cw, ch = self._client(h)
        self._chuot(WM_MOUSEMOVE, *pts[0], h, cw, ch)
        self._chuot(WM_LBUTTONDOWN, *pts[0], h, cw, ch, 1)
        for p in pts[1:]:
            time.sleep(gap)
            self._chuot(WM_MOUSEMOVE, *p, h, cw, ch, 1)
        time.sleep(0.05)
        self._chuot(WM_LBUTTONUP, *pts[-1], h, cw, ch)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        n = max(5, int(duration_ms) // 15)
        self.keo([(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n + 1)], gap=duration_ms / 1000 / n)

    def key(self, keycode: str | int):
        vk = _VK.get(str(keycode))
        if vk is None:
            return                     # phím Android không có tương đương trên PC (HOME...) -> bỏ qua
        h = self._hwnd()
        _u.PostMessageW(h, WM_KEYDOWN, vk, 0)
        time.sleep(0.03)
        _u.PostMessageW(h, WM_KEYUP, vk, 0xC0000001)

    def home(self):
        pass

    def text(self, value: str):
        h = self._hwnd()
        for c in str(value).replace("%s", " "):
            _u.PostMessageW(h, WM_CHAR, ord(c), 0)
            time.sleep(0.02)

    def shell(self, command: str, timeout: float = 20) -> str:
        """Giả lập các lệnh adb shell custom.py có dùng; lệnh khác (uiautomator, getevent...) -> ''."""
        if "sendevent" in command:
            self.keo(toa_do_sendevent(command), gap=0.009)
            return ""
        if command.startswith("input keyevent"):
            for k in command.split()[2:]:
                self.key(k)
            return ""
        m = re.match(r"input text '?(.*?)'?$", command, re.S)
        if m:
            self.text(m.group(1).replace("'\\''", "'"))
            return ""
        if command.startswith("input tap"):
            self.tap(*map(int, command.split()[2:4]))
        return ""

    # ---- "app" = cửa sổ game -------------------------------------------------
    def current_app(self) -> str:
        return self.package if self.connect() else ""

    def launch_app(self, package: str):
        if not self.connect():
            # shortcut: chưa tự mở game qua launcher Level Up; mở game tay rồi Start
            raise AdbError("Game PC chưa mở: mở Nghịch Thủy Hàn qua Level Up rồi bấm Start lại")

    def stop_app(self, package: str):
        pass                           # không tự tắt game PC (chưa tự mở lại được qua launcher)

    def start_activity(self, component: str):
        pass

    def screen_size(self) -> tuple[int, int]:
        return W, H

    # ---- hộp thoại đăng nhập VNGGAMES (cửa sổ riêng, KHÔNG nhận PostMessage -> chuột/phím thật) ----
    def chup_cua_so(self, tieu_de: str):
        """Ảnh BGR vùng client của cửa sổ `tieu_de` (kích thước thật, không thu về 960x540); không có -> None."""
        h = tim_cua_so(tieu_de)
        if not h:
            return None
        r = wintypes.RECT()
        _u.GetClientRect(h, ctypes.byref(r))
        w, hh = r.right, r.bottom
        if not w or not hh:
            return None
        hdc = _u.GetDC(h)
        mdc = _g.CreateCompatibleDC(hdc)
        bmp = _g.CreateCompatibleBitmap(hdc, w, hh)
        try:
            _g.SelectObject(mdc, bmp)
            _u.PrintWindow(h, mdc, 3)
            bi = _BIH(ctypes.sizeof(_BIH), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = (ctypes.c_char * (w * hh * 4))()
            _g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
        finally:
            _g.DeleteObject(bmp)
            _g.DeleteDC(mdc)
            _u.ReleaseDC(h, hdc)
        return np.frombuffer(buf, np.uint8).reshape(hh, w, 4)[:, :, :3].copy()

    def ranh_tay(self, giay: float = 3.0) -> bool:
        """Người dùng đã ngừng đụng chuột/phím >= `giay` giây? (để mượn chuột không giật lúc người đang dùng).
        Thao tác thật của chính tool cũng tính là 'có người dùng' -> lần nhập cuối trùng mốc tool vừa làm thì coi là rảnh."""
        class _LII(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        li = _LII(ctypes.sizeof(_LII), 0)
        _u.GetLastInputInfo(ctypes.byref(li))
        bay_gio = ctypes.windll.kernel32.GetTickCount()
        return (bay_gio - li.dwTime) / 1000 >= giay or bool(self._tick_tool and 0 <= li.dwTime - self._tick_tool < 400)

    def click_that(self, tieu_de: str, x: int, y: int):
        """Click chuột THẬT vào (x, y) client của cửa sổ `tieu_de` rồi trả chuột về chỗ cũ (~0.5s).
        Hộp thoại VNGGAMES bỏ qua click PostMessage (đo 02/11, kể cả đưa lên trước) nên chỉ cách này bấm được.
        Người gọi phải chờ CHO_PHEP_CHUOT + ranh_tay() trước (custom._cho_muon_chuot)."""
        h = tim_cua_so(tieu_de)
        if not h:
            raise AdbError(f"Không thấy cửa sổ '{tieu_de}'")
        p = wintypes.POINT(int(x), int(y))
        _u.ClientToScreen(h, ctypes.byref(p))
        cu = wintypes.POINT()
        _u.GetCursorPos(ctypes.byref(cu))
        _u.SetForegroundWindow(h)
        time.sleep(0.2)
        _u.SetCursorPos(p.x, p.y)
        time.sleep(0.1)
        _u.mouse_event(2, 0, 0, 0, 0)      # LEFTDOWN
        time.sleep(0.08)
        _u.mouse_event(4, 0, 0, 0, 0)      # LEFTUP
        time.sleep(0.1)
        _u.SetCursorPos(cu.x, cu.y)
        self._tick_tool = ctypes.windll.kernel32.GetTickCount()

    def go_that(self, text: str):
        """Gõ phím THẬT (SendInput unicode) vào cửa sổ đang focus (vừa click_that)."""
        for ch in str(text):
            for co in (4, 6):                # KEYEVENTF_UNICODE, | KEYEVENTF_KEYUP
                i = _INP(type=1)
                i.ki = _KI(0, ord(ch), co, 0, 0)
                _u.SendInput(1, ctypes.byref(i), ctypes.sizeof(_INP))
            time.sleep(0.03)
        self._tick_tool = ctypes.windll.kernel32.GetTickCount()


class _KI(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]


class _INP(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KI), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]
