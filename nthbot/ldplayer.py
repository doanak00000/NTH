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
    """Bật 1 instance LDPlayer."""
    subprocess.run([ldconsole_path, "launch", "--index", str(index)], timeout=60, **_NO_WINDOW)


def quit_instance(ldconsole_path: str, index: int):
    subprocess.run([ldconsole_path, "quit", "--index", str(index)], timeout=30, **_NO_WINDOW)
