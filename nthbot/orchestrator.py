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
from .bluestacks import list_instances as list_bs
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
    bluestacks_player: str = "C:/Program Files/BlueStacks_nxt/HD-Player.exe"
    bluestacks_conf: str = "C:/ProgramData/BlueStacks_nxt/bluestacks.conf"
    may_ao_mac_dinh: str = "PC"           # thiết bị loại này được tick sẵn khi mở tool / --start
    templates_pc_dir: str = "templates_pc"   # ảnh mẫu riêng bản PC (cùng tên -> thay ảnh chung)
    pc_tieu_de: str = "Nghịch Thủy Hàn"      # tiêu đề cửa sổ game PC; "" = không dùng bản PC
    ld_bo_qua: list = None                   # index LDPlayer không dùng (không hiện, không chạy)

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
            bluestacks_player=data.get("bluestacks_player") or cls.bluestacks_player,
            bluestacks_conf=data.get("bluestacks_conf") or cls.bluestacks_conf,
            may_ao_mac_dinh=data.get("may_ao_mac_dinh") or cls.may_ao_mac_dinh,
            templates_pc_dir=under_base(data.get("templates_pc_dir", "templates_pc")),
            pc_tieu_de=data.get("pc_tieu_de", cls.pc_tieu_de) or "",
            ld_bo_qua=[int(i) for i in data.get("ld_bo_qua") or []],
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
        # 2) game PC + BlueStacks (bluestacks.conf) + LDPlayer (ldconsole): liệt kê CẢ instance đang tắt
        if cfg.pc_tieu_de and os.name == "nt":
            from .pc import PcDevice
            devices.append(PcDevice(serial=cfg.pc_tieu_de, name=f"[PC] {cfg.pc_tieu_de}", package=cfg.game_package))
        if os.path.exists(cfg.bluestacks_player):
            bs, _ = list_bs(cfg.bluestacks_conf)
            for inst in bs:
                devices.append(Device(serial=inst.serial, name=f"[BS] {inst.display_name}", adb_path=cfg.adb_path,
                                      bs_instance=inst.name, bs_player=cfg.bluestacks_player))
        for inst in list_instances(cfg.ldconsole_path):
            if inst.index in (cfg.ld_bo_qua or []):
                continue
            devices.append(Device(serial=inst.serial, name=f"[{inst.index}] {inst.name.replace('LDPlayer', 'LD')}",
                                  adb_path=cfg.adb_path, ld_index=inst.index,
                                  ldconsole_path=cfg.ldconsole_path))
        if not devices:
            # 3) fallback: bất kỳ thiết bị nào adb đang thấy
            for serial in list_adb_devices(cfg.adb_path):
                devices.append(Device(serial=serial, name=serial, adb_path=cfg.adb_path))

    # tự connect các thiết bị host:port để sẵn sàng dùng (máy ảo đang tắt thì bỏ qua; LD #0 và BlueStacks
    #  cùng cổng 5555 -> chỉ connect máy đang chạy để preview đúng máy)
    for d in devices:
        if d.quan_ly and not d.may_dang_chay():
            continue
        if ":" in d.serial and d.loai_may != "PC":
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
        self.templates_pc = TemplateStore(cfg.templates_dir, override_dir=cfg.templates_pc_dir)
        self.runners: dict[str, BotRunner] = {}

    def make_runner(self, device: Device, task: Task, on_log=None, on_state=None) -> BotRunner:
        runner = BotRunner(
            device=device,
            task=task,
            templates=self.templates_pc if device.loai_may == "PC" else self.templates,
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
