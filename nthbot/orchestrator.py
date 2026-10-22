"""
Tải cấu hình, dò thiết bị, nạp task, và chạy nhiều BotRunner song song.

Đây là tầng "keo" nối config + adb + ldplayer + bot. UI gọi vào đây.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import yaml

from .adb import Device, list_adb_devices
from .bot import BotRunner, Task
from .ldplayer import list_instances
from .vision import TemplateStore


def app_dir() -> str:
    """Thư mục gốc của ứng dụng (cạnh .exe khi đóng gói, hoặc gốc project khi chạy .py)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_config_path(path: str = "config.yaml") -> str:
    """Tìm config.yaml: ưu tiên đường dẫn truyền vào, nếu không có thì cạnh app."""
    if os.path.exists(path):
        return os.path.abspath(path)
    return os.path.join(app_dir(), os.path.basename(path))


@dataclass
class AppConfig:
    adb_path: str = "adb"
    ldconsole_path: str = ""
    game_package: str = ""
    templates_dir: str = "templates"
    tasks_dir: str = "tasks"
    confidence: float = 0.85
    multi_scale: bool = False
    manual_devices: list = None
    custom_path: str = "custom.py"

    @classmethod
    def load(cls, path: str = "config.yaml") -> "AppConfig":
        path = resolve_config_path(path)
        data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        vision = data.get("vision", {}) or {}
        base_dir = os.path.dirname(os.path.abspath(path))

        def under_base(p: str) -> str:
            # đường dẫn tương đối -> tính theo thư mục chứa config.yaml (không phụ thuộc cwd)
            return p if os.path.isabs(p) else os.path.join(base_dir, p)

        return cls(
            adb_path=data.get("adb_path") or "adb",
            ldconsole_path=data.get("ldconsole_path", ""),
            game_package=data.get("game_package", ""),
            templates_dir=under_base(data.get("templates_dir", "templates")),
            tasks_dir=under_base(data.get("tasks_dir", "tasks")),
            confidence=float(vision.get("confidence", 0.85)),
            multi_scale=bool(vision.get("multi_scale", False)),
            manual_devices=data.get("manual_devices") or [],
            custom_path=os.path.join(base_dir, "custom.py"),
        )


def discover_devices(cfg: AppConfig) -> list[Device]:
    """Tìm thiết bị theo MỘT nguồn duy nhất để tránh trùng lặp:
       1) manual_devices (nếu có)  ->  2) LDPlayer qua ldconsole  ->  3) adb devices.

    Mỗi instance LDPlayer xuất hiện cả dạng emulator-XXXX lẫn 127.0.0.1:port (cùng 1 máy),
    nên KHÔNG gộp nhiều nguồn -> tránh chạy bot 2 lần trên cùng instance.
    Tự `adb connect` các serial dạng host:port để preview/chạy được ngay.
    """
    devices: list[Device] = []

    # 1) khai báo tay -> dùng đúng những gì user khai
    if cfg.manual_devices:
        for d in cfg.manual_devices:
            devices.append(Device(serial=d["serial"], name=d.get("name", d["serial"]),
                                  adb_path=cfg.adb_path))
    else:
        # 2) LDPlayer qua ldconsole: liệt kê CẢ instance đang tắt -> Start sẽ tự bật
        instances = list_instances(cfg.ldconsole_path)
        if instances:
            for inst in instances:
                devices.append(Device(serial=inst.serial, name=f"[{inst.index}] {inst.name.replace('LDPlayer', 'LD')}",
                                      adb_path=cfg.adb_path, ld_index=inst.index,
                                      ldconsole_path=cfg.ldconsole_path))
        else:
            # 3) fallback: bất kỳ thiết bị nào adb đang thấy
            for serial in list_adb_devices(cfg.adb_path):
                devices.append(Device(serial=serial, name=serial, adb_path=cfg.adb_path))

    # tự connect các thiết bị host:port để sẵn sàng dùng (instance LDPlayer đang tắt thì bỏ qua)
    running = {i.index for i in instances if i.running} if not cfg.manual_devices and instances else None
    for d in devices:
        if d.ld_index is not None and running is not None and d.ld_index not in running:
            continue
        if ":" in d.serial:
            d.connect()

    return devices


def list_tasks(cfg: AppConfig) -> list[str]:
    d = cfg.tasks_dir
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.endswith((".yaml", ".yml")))


def load_task(cfg: AppConfig, filename: str) -> Task:
    path = filename if os.path.isabs(filename) else os.path.join(cfg.tasks_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Task(
        name=data.get("name", os.path.basename(path)),
        description=data.get("description", ""),
        package=data.get("package", "") or cfg.game_package,
        variables=data.get("variables", {}) or {},
        repeat=int(data.get("repeat", 1)),
        steps=data.get("steps", []) or [],
    )


class Orchestrator:
    """Chạy 1 task trên nhiều device song song."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.templates = TemplateStore(cfg.templates_dir)
        self.runners: dict[str, BotRunner] = {}

    def make_runner(self, device: Device, task: Task, on_log=None, on_state=None) -> BotRunner:
        runner = BotRunner(
            device=device,
            task=task,
            templates=self.templates,
            confidence=self.cfg.confidence,
            multi_scale=self.cfg.multi_scale,
            default_package=self.cfg.game_package,
            custom_path=self.cfg.custom_path,
            on_log=on_log,
            on_state=on_state,
        )
        self.runners[device.name] = runner
        return runner

    def start_all(self):
        for r in self.runners.values():
            r.start()

    def stop_all(self):
        for r in self.runners.values():
            r.stop()
