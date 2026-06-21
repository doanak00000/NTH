"""
BotRunner: chạy 1 task trên 1 thiết bị trong 1 luồng riêng, có thể Stop bất cứ lúc nào.
"""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from .adb import Device
from .engine import Context, Stopped, load_custom_funcs, run_steps
from .vision import TemplateStore


@dataclass
class Task:
    name: str
    steps: list
    description: str = ""
    package: str = ""
    variables: dict = field(default_factory=dict)
    # lặp lại toàn bộ task bao nhiêu lần (0 = vô hạn cho tới khi Stop)
    repeat: int = 1


class BotRunner:
    """Quản lý vòng đời chạy 1 task trên 1 device."""

    def __init__(
        self,
        device: Device,
        task: Task,
        templates: TemplateStore,
        *,
        confidence: float = 0.85,
        multi_scale: bool = False,
        default_package: str = "",
        custom_path: str = "",
        on_log: Callable[[str, str], None] | None = None,
        on_state: Callable[[str, str], None] | None = None,
    ):
        self.device = device
        self.task = task
        self.templates = templates
        self.confidence = confidence
        self.multi_scale = multi_scale
        self.default_package = default_package
        self.custom_path = custom_path
        self.on_log = on_log
        self.on_state = on_state

        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state = "idle"   # idle | running | stopped | done | error
        self.last_error = ""

    # ---- log/state callbacks -------------------------------------------
    def _log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        if self.on_log:
            self.on_log(self.device.name, line)
        else:
            print(f"{self.device.name}: {line}")

    def _set_state(self, state: str):
        self.state = state
        if self.on_state:
            self.on_state(self.device.name, state)

    # ---- điều khiển -----------------------------------------------------
    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def join(self, timeout=None):
        if self.thread:
            self.thread.join(timeout)

    @property
    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    # ---- thân chạy ------------------------------------------------------
    def _run(self):
        self._set_state("running")
        self._log(f"Bắt đầu task '{self.task.name}'")
        try:
            if not self.device.connect():
                raise RuntimeError(f"Không kết nối được {self.device.serial}")

            ctx = Context(
                device=self.device,
                templates=self.templates,
                package=self.task.package or self.default_package,
                variables=dict(self.task.variables),
                confidence=self.confidence,
                multi_scale=self.multi_scale,
                stop_event=self.stop_event,
                log=self._log,
                custom_funcs=load_custom_funcs(self.custom_path),
            )

            repeat = self.task.repeat
            count = 0
            while repeat == 0 or count < repeat:
                ctx.check_stop()
                if repeat != 1:
                    self._log(f"--- Vòng task #{count + 1} ---")
                run_steps(self.task.steps, ctx)
                count += 1

            self._log("Hoàn tất.")
            self._set_state("done")

        except Stopped:
            self._log("Đã dừng theo yêu cầu.")
            self._set_state("stopped")
        except Exception as e:  # noqa: BLE001
            self.last_error = f"{e}"
            self._log(f"LỖI: {e}")
            self._log(traceback.format_exc().strip().splitlines()[-1])
            self._set_state("error")
