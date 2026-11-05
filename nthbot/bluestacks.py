"""
Dò instance BlueStacks 5 (BlueStacks_nxt) qua bluestacks.conf, bật/tắt bằng HD-Player.exe.

bluestacks.conf có các dòng dạng:  bst.instance.<tên>.adb_port="5555" / .display_name="BlueStacks App Player"
ADB phải được bật trong BlueStacks (Settings > Advanced > Android Debug Bridge) -> bst.enable_adb_access="1".
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}
_DONG = re.compile(r'^bst\.instance\.([^.]+)\.(display_name|adb_port|status\.adb_port)="(.*)"$')


@dataclass
class BsInstance:
    name: str           # tên instance trong conf (vd Pie64) -> HD-Player --instance <name>
    display_name: str
    adb_port: int

    @property
    def serial(self) -> str:
        return f"127.0.0.1:{self.adb_port}"


def doc_conf(text: str) -> tuple[list[BsInstance], bool]:
    """Trả (danh sách instance, adb đã bật chưa) từ nội dung bluestacks.conf."""
    info: dict[str, dict] = {}
    adb_bat = False
    for line in text.splitlines():
        line = line.strip()
        if line == 'bst.enable_adb_access="1"':
            adb_bat = True
        m = _DONG.match(line)
        if m:
            info.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
    out = []
    for name, v in info.items():
        port = v.get("status.adb_port") or v.get("adb_port")   # status.adb_port = cổng thật lúc đang chạy
        if port and port.isdigit():
            out.append(BsInstance(name, v.get("display_name") or name, int(port)))
    return out, adb_bat


def list_instances(conf_path: str) -> tuple[list[BsInstance], bool]:
    try:
        with open(conf_path, "r", encoding="utf-8", errors="replace") as f:
            return doc_conf(f.read())
    except OSError:
        return [], False


def dang_chay() -> bool:
    # shortcut: chỉ biết "có HD-Player nào chạy", không phân biệt instance; nhiều instance BlueStacks thì lọc theo commandline
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq HD-Player.exe", "/NH"],
                             capture_output=True, timeout=15, **_NO_WINDOW).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "HD-Player.exe" in out


def start_instance(player_path: str, name: str):
    subprocess.Popen([player_path, "--instance", name], **_NO_WINDOW)


def quit_instance():
    # shortcut: tắt mọi HD-Player (1 instance BlueStacks là đủ cho tool hiện tại)
    subprocess.run(["taskkill", "/F", "/IM", "HD-Player.exe"], capture_output=True, timeout=30, **_NO_WINDOW)
