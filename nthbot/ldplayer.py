"""
Tự dò các instance LDPlayer qua ldconsole.exe và map ra cổng ADB.

LDPlayer mở 1 cổng ADB cho mỗi instance:  port = 5555 + index * 2
(index 0 -> 5555, index 1 -> 5557, ...). 'ldconsole list2' cho biết
instance nào đang chạy (android_started = 1).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


@dataclass
class LdInstance:
    index: int
    name: str
    running: bool

    @property
    def adb_port(self) -> int:
        return 5555 + self.index * 2

    @property
    def serial(self) -> str:
        return f"127.0.0.1:{self.adb_port}"


def list_instances(ldconsole_path: str) -> list[LdInstance]:
    """Trả danh sách instance LDPlayer.

    Output 'ldconsole list2' là CSV mỗi dòng:
      index,title,top_handle,bind_handle,android_started,pid,vbox_pid
    """
    try:
        out = subprocess.run(
            [ldconsole_path, "list2"],
            capture_output=True, timeout=15, **_NO_WINDOW,
        ).stdout.decode("utf-8", "replace")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    instances: list[LdInstance] = []
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) < 5:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        name = parts[1].strip()
        running = parts[4].strip() == "1"
        instances.append(LdInstance(index=idx, name=name, running=running))
    return instances


def start_instance(ldconsole_path: str, index: int):
    """Bật 1 instance LDPlayer (cửa sổ tự dời sang màn hình phụ nếu có)."""
    subprocess.run([ldconsole_path, "launch", "--index", str(index)], timeout=60, **_NO_WINDOW)
    import threading
    threading.Thread(target=_doi_sang_man_phu, args=(ldconsole_path, index), daemon=True).start()


def man_phu() -> tuple[int, int] | None:
    """Góc trên-trái vùng làm việc của màn hình PHỤ (không phải màn chính); không có / đang tắt -> None."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class _MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]
    u = ctypes.WinDLL("user32")
    u.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
    kq = []

    def cb(hmon, _hdc, _rc, _lp):
        mi = _MI(cbSize=ctypes.sizeof(_MI))
        if u.GetMonitorInfoW(hmon, ctypes.byref(mi)) and not mi.dwFlags & 1:   # 1 = MONITORINFOF_PRIMARY
            kq.append((mi.rcWork.left, mi.rcWork.top))
        return True
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                              wintypes.LPARAM)(cb)
    u.EnumDisplayMonitors(None, None, proc, 0)
    return kq[0] if kq else None


def _doi_sang_man_phu(ldconsole_path: str, index: int):
    """(02/11 user) Cửa sổ LDPlayer vừa bật -> dời sang màn phụ (nếu có) rồi THU NHỎ xuống taskbar (05/11 user: không muốn
    cửa sổ hiện lên; adb chụp/bấm vẫn chạy khi thu nhỏ, đã thử). Làm vài lần trong ~20s vì LDPlayer tự đặt lại cửa sổ
    lúc boot. Màn phụ tắt -> Windows tự kéo về màn chính."""
    import time
    import ctypes
    if os.name != "nt":
        return
    xy = man_phu()
    u = ctypes.WinDLL("user32")
    h, lan = 0, 0
    for _ in range(60):
        if not h:
            try:
                out = subprocess.run([ldconsole_path, "list2"], capture_output=True, timeout=15,
                                     **_NO_WINDOW).stdout.decode("utf-8", "replace")
                h = next((int(d.split(",")[2]) for d in out.splitlines() if d.split(",")[0] == str(index)), 0)
            except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
                h = 0
        if h:
            if xy:
                u.SetWindowPos(h, 0, xy[0], xy[1], 0, 0, 0x15)   # NOSIZE | NOZORDER | NOACTIVATE
            u.ShowWindow(h, 7)                                   # SW_SHOWMINNOACTIVE: thu nhỏ, không cướp focus
            lan += 1
            if lan >= 3:
                return
            time.sleep(8)
        else:
            time.sleep(1)


def quit_instance(ldconsole_path: str, index: int):
    subprocess.run([ldconsole_path, "quit", "--index", str(index)], timeout=30, **_NO_WINDOW)
