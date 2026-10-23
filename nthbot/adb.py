"""
Bọc ADB - mọi giao tiếp với 1 thiết bị (LDPlayer instance) đi qua đây.

Thiết kế cho LDPlayer trên Windows (ADB mở hoàn toàn): tap/swipe/launch đều chạy.
Vẫn chạy được trên macOS/Linux để dev (riêng screencap dùng chung cơ chế).
"""

from __future__ import annotations

import os
import random
import subprocess
import time
from dataclasses import dataclass

import numpy as np

try:
    import cv2
except ImportError:  # vision là optional ở tầng adb
    cv2 = None


# Trên Windows: chặn cửa sổ console (CMD đen) bật lên mỗi lần gọi adb.
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _run_quiet(cmd, timeout):
    """subprocess.run với capture + ẩn cửa sổ console (Windows)."""
    return subprocess.run(cmd, capture_output=True, timeout=timeout, **_NO_WINDOW)


def _giai_ma_tho(buf: bytes):
    """screencap thô: header (w, h, format[, colorspace]) uint32 + w*h*4 byte RGBA -> ảnh BGR; sai định dạng -> None."""
    if len(buf) < 12:
        return None
    w, h, fmt = np.frombuffer(buf[:12], dtype=np.uint32)
    n = int(w) * int(h) * 4
    if fmt != 1 or not w or not h or len(buf) - n not in (12, 16):   # 1 = RGBA_8888; Android 9+ thêm colorspace
        return None
    return cv2.cvtColor(np.frombuffer(buf[len(buf) - n:], dtype=np.uint8).reshape(int(h), int(w), 4), cv2.COLOR_RGBA2BGR)


class AdbError(RuntimeError):
    """Lỗi khi gọi adb."""


@dataclass
class Device:
    """Một thiết bị/instance ADB.

    serial: "host:port" (vd "127.0.0.1:5555") hoặc tên transport.
    name:   tên hiển thị thân thiện (vd "Máy 1").
    """

    serial: str
    name: str = ""
    adb_path: str = "adb"
    ld_index: int | None = None     # instance LDPlayer (để tự bật khi Start); None = thiết bị adb thường
    ldconsole_path: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.serial

    # ---- lớp gọi adb thô -------------------------------------------------
    def _run(self, args: list[str], timeout: float = 20, binary: bool = False):
        cmd = [self.adb_path, "-s", self.serial, *args]
        try:
            proc = _run_quiet(cmd, timeout)
        except FileNotFoundError as e:
            raise AdbError(f"Không tìm thấy adb tại '{self.adb_path}'. Sửa adb_path trong config.yaml.") from e
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"adb timeout sau {timeout}s: {' '.join(args)}") from e
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip()
            raise AdbError(f"adb lỗi ({' '.join(args)}): {err}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")

    def shell(self, command: str, timeout: float = 20) -> str:
        """Chạy 1 lệnh shell trên thiết bị, trả về stdout (text)."""
        return self._run(["shell", command], timeout=timeout)

    # ---- kết nối ---------------------------------------------------------
    def connect(self) -> bool:
        """adb connect tới serial (chỉ áp dụng host:port). Trả True nếu OK."""
        if ":" not in self.serial:
            return True  # transport sẵn có, không cần connect
        try:
            out = _run_quiet([self.adb_path, "connect", self.serial], 15) \
                .stdout.decode("utf-8", "replace")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return "connected" in out or "already" in out

    def is_online(self) -> bool:
        try:
            out = _run_quiet([self.adb_path, "devices"], 10) \
                .stdout.decode("utf-8", "replace")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        for line in out.splitlines():
            if line.startswith(self.serial) and "device" in line.split()[-1:]:
                return True
        return False

    # ---- thông tin thiết bị --------------------------------------------
    def getprop(self, name: str) -> str:
        return self.shell(f"getprop {name}").strip()

    def screen_size(self) -> tuple[int, int]:
        """Trả (width, height) theo wm size; fallback: kích thước screenshot."""
        try:
            out = self.shell("wm size")
            # "Physical size: 1280x720"
            part = out.strip().split(":")[-1].strip()
            w, h = part.lower().split("x")
            return int(w), int(h)
        except Exception:
            img = self.screencap()
            return img.shape[1], img.shape[0]

    # ---- chụp màn hình --------------------------------------------------
    def screencap(self) -> "np.ndarray":
        """Chụp màn hình -> ảnh BGR (numpy) để OpenCV xử lý.

        Dùng exec-out screencap ảnh THÔ (RGBA, không nén): 0.13s/lần thay vì 0.24s của PNG (-p), máy ảo đỡ nén
        (đo 23/10 LDPlayer14 960x540, ảnh giống hệt). Định dạng lạ (không phải RGBA_8888) -> lùi về PNG.
        """
        if cv2 is None:
            raise AdbError("Cần opencv-python để giải mã ảnh screencap.")
        img = _giai_ma_tho(self._run(["exec-out", "screencap"], timeout=20, binary=True))
        if img is not None:
            return img
        raw = self._run(["exec-out", "screencap", "-p"], timeout=20, binary=True)
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise AdbError("Giải mã screencap thất bại (dữ liệu rỗng/hỏng).")
        return img

    # ---- điều khiển (LDPlayer hỗ trợ đầy đủ) ---------------------------
    def tap(self, x: int, y: int, jitter: int = 0):
        """Chạm vào (x, y). jitter>0 thêm nhiễu ngẫu nhiên cho giống người."""
        if jitter:
            x += random.randint(-jitter, jitter)
            y += random.randint(-jitter, jitter)
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")

    def key(self, keycode: str | int):
        """Gửi keyevent. Có thể là số (vd 4) hoặc tên (vd KEYCODE_BACK)."""
        self.shell(f"input keyevent {keycode}")

    def back(self):
        self.key(4)

    def home(self):
        self.key(3)

    def text(self, value: str):
        """Nhập text (khoảng trắng -> %s cho input text)."""
        safe = value.replace(" ", "%s")
        self.shell(f"input text {safe}")

    # ---- ứng dụng -------------------------------------------------------
    def launch_app(self, package: str):
        """Mở app (không cần biết activity). LDPlayer14 không có `monkey` -> dùng am start."""
        act = self.shell(f"cmd package resolve-activity --brief {package}").strip().splitlines()
        if act and "/" in act[-1]:
            self.start_activity(act[-1].strip())
        else:
            self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def start_activity(self, component: str):
        """Mở thẳng 1 activity, vd com.foo/.MainActivity."""
        self.shell(f"am start -n {component}")

    def stop_app(self, package: str):
        self.shell(f"am force-stop {package}")

    def current_app(self) -> str:
        """Package đang focus (để kiểm tra game còn mở không).

        Lấy dumpsys rồi lọc phía Python (không dùng grep trên thiết bị cho
        tương thích mọi emulator).
        """
        try:
            out = self.shell("dumpsys window", timeout=15)
        except AdbError:
            return ""
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                for tok in line.replace("/", " ").split():
                    if "." in tok and tok[0].islower() and "{" not in tok:
                        return tok
        return ""


def list_adb_devices(adb_path: str = "adb") -> list[str]:
    """Liệt kê serial của các thiết bị đang online theo `adb devices`."""
    try:
        out = _run_quiet([adb_path, "devices"], 10).stdout.decode("utf-8", "replace")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    devs = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if line and line.split()[-1] == "device":
            devs.append(line.split()[0])
    return devs
