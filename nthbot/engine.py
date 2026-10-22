"""
Step-engine: đọc 1 danh sách bước (steps) dạng YAML và thực thi trên 1 thiết bị.

ĐÂY LÀ PHẦN BẠN CHỈNH NHIỀU NHẤT thông qua file task .yaml — KHÔNG cần sửa code ở đây.

Mỗi bước là 1 mục YAML có 1 "action" (khoá chính) + tham số. Ví dụ:
    - tap: { x: 100, y: 200 }
    - find_tap: { image: "nut.png", timeout: 30 }
    - sleep: 2
    - if: { image: "hopthoai.png" }
      then:
        - tap: { x: 800, y: 400 }
      else:
        - log: "không thấy hộp thoại"
    - loop: { times: 5 }
      steps:
        - find_tap: { image: "thu.png" }
        - sleep: 1

Danh sách action có sẵn xem ở phần HANDLERS bên dưới (và README.md).
"""

from __future__ import annotations

import importlib.util
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .adb import Device
from .vision import Match, TemplateStore, find_template, ocr_text


class StepError(RuntimeError):
    """Lỗi logic khi chạy 1 bước (vd không tìm thấy ảnh bắt buộc)."""


class Stopped(Exception):
    """Người dùng bấm Stop -> dừng sạch sẽ."""


class TaskDone(Exception):
    """custom.py báo đã làm xong hết (vd hết tài khoản) -> kết thúc task như hoàn tất."""


class BoQuaAcc(Exception):
    """Bước lỗi, Claude cứu không được -> BotRunner bỏ qua tk Zing đang làm, sang tk kế (không dừng máy)."""


_VAR_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


@dataclass
class Context:
    """Trạng thái dùng chung trong suốt 1 lần chạy task trên 1 thiết bị."""

    device: Device
    templates: TemplateStore
    package: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.85
    multi_scale: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    log: Callable[[str], None] = print
    custom_funcs: dict[str, Callable] = field(default_factory=dict)

    last_match: Match = field(default_factory=lambda: Match(found=False))
    tien_trien: float = field(default_factory=time.time)   # lần cuối có tiến triển (watchdog đọc)
    # bước lỗi (đã thử đóng banner) -> cuu_loi(step, loi): True = đã xử lý, làm lại bước; False = chịu (BotRunner gắn)
    cuu_loi: Callable[[dict, Exception], bool] | None = None
    # cứu tự động vẫn chịu -> cho_claude(step, loi): chờ Claude phiên /nth điều khiển tay -> "LAM_LAI" | "TIEP" | "BO_QUA"
    cho_claude: Callable[[dict, Exception], str] | None = None

    # ---- tiện ích -------------------------------------------------------
    def ghi_phieu(self, buoc: str, gia_tri, loi: bool = False):
        """Phiếu kết quả của nhân vật đang làm: buoc -> 'failed' / '3/4' / số lần... (doi_acc lưu vào kho lúc xong
        nhân vật -> UI, web, báo cáo). loi=True -> chụp màn hình logs/phieu_<giờ>_<bước>.png để xem nguyên nhân sau."""
        self.variables.setdefault("_phieu", {})[buoc] = gia_tri
        if loi:
            try:
                from .orchestrator import app_dir
                from .vision import imwrite_unicode
                ten = time.strftime("phieu_%Y%m%d_%H%M%S_") + re.sub(r"\W+", "_", buoc) + ".png"
                imwrite_unicode(os.path.join(app_dir(), "logs", ten), self.capture())
            except Exception:  # noqa: BLE001 - chụp lỗi không được làm hỏng bước chính
                pass

    def check_stop(self):
        if self.stop_event.is_set():
            raise Stopped()

    def sleep(self, seconds: float):
        """Ngủ nhưng vẫn phản hồi nút Stop. Tự cộng thêm 0-10% ngẫu nhiên để nhịp không cố định
        (chỉ cộng, không trừ: nhiều chỗ cần chờ tối thiểu, vd hiệu ứng list nhân vật ~3.5s)."""
        seconds *= random.uniform(1.0, 1.1)
        end = time.time() + seconds
        if seconds >= 10:                    # cố ý chờ lâu (vd giãn cách treo) -> không phải kẹt
            self.tien_trien = max(self.tien_trien, end)
        while time.time() < end:
            self.check_stop()
            time.sleep(min(0.1, max(0, end - time.time())))

    def resolve(self, value: Any) -> Any:
        """Thay {bien} bằng giá trị trong variables (đệ quy cho dict/list)."""
        if isinstance(value, str):
            def repl(m):
                key = m.group(1)
                if key == "package":
                    return str(self.package)
                return str(self.variables.get(key, m.group(0)))
            return _VAR_RE.sub(repl, value)
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        return value

    def capture(self) -> np.ndarray:
        self.check_stop()
        return self.device.screencap()

    def find(self, image: str, confidence: float | None = None,
             region=None, screen: np.ndarray | None = None) -> Match:
        tmpl = self.templates.get(image)
        scr = screen if screen is not None else self.capture()
        m = find_template(
            scr, tmpl,
            confidence=confidence if confidence is not None else self.confidence,
            region=tuple(region) if region else None,
            multi_scale=self.multi_scale,
        )
        self.last_match = m
        return m

    def find_all(self, images: list[str], confidence: float | None = None) -> bool:
        """True nếu TẤT CẢ ảnh trong list đều xuất hiện (kiểm tra trên cùng 1 khung)."""
        scr = self.capture()
        return all(self.find(img, confidence=confidence, screen=scr).found for img in images)

    def find_any(self, images: list[str], confidence: float | None = None) -> bool:
        """True nếu CÓ ÍT NHẤT 1 ảnh xuất hiện."""
        scr = self.capture()
        return any(self.find(img, confidence=confidence, screen=scr).found for img in images)


# =========================================================================
#  Các handler cho từng action.  Mỗi handler: fn(params, step, ctx) -> bool
#  Giá trị trả về True/False dùng cho điều kiện (if/loop).
# =========================================================================

def _wait_for(ctx: Context, image: str, timeout: float, confidence, region,
              interval: float = 0.6) -> Match:
    """Chờ tới khi thấy image hoặc hết timeout. Trả Match (found True/False)."""
    end = time.time() + max(0, timeout)
    while True:
        m = ctx.find(image, confidence=confidence, region=region)
        if m.found:
            return m
        if time.time() >= end:
            return m
        ctx.sleep(interval)


def h_launch(params, step, ctx: Context):
    pkg = ctx.resolve(params) if isinstance(params, str) and params else ctx.package
    if not pkg:
        raise StepError("launch: chưa có package (đặt game_package trong config hoặc truyền vào).")
    ctx.log(f"Mở app {pkg}")
    ctx.device.launch_app(pkg)
    return True


def h_stop_app(params, step, ctx: Context):
    pkg = ctx.resolve(params) if isinstance(params, str) and params else ctx.package
    ctx.device.stop_app(pkg)
    return True


def h_tap(params, step, ctx: Context):
    p = ctx.resolve(params)
    ctx.device.tap(int(p["x"]), int(p["y"]), jitter=int(p.get("jitter", 0)))
    return True


def h_tap_match(params, step, ctx: Context):
    """Tap vào vị trí ảnh vừa tìm thấy gần nhất (last_match)."""
    if not ctx.last_match.found:
        raise StepError("tap_match: chưa có match nào trước đó.")
    j = int((params or {}).get("jitter", 0)) if isinstance(params, dict) else 0
    ctx.device.tap(ctx.last_match.x, ctx.last_match.y, jitter=j)
    return True


def h_swipe(params, step, ctx: Context):
    p = ctx.resolve(params)
    ctx.device.swipe(int(p["x1"]), int(p["y1"]), int(p["x2"]), int(p["y2"]),
                     duration_ms=int(p.get("duration", 300)))
    return True


def h_key(params, step, ctx: Context):
    ctx.device.key(ctx.resolve(params))
    return True


def h_back(params, step, ctx: Context):
    ctx.device.back()
    return True


def h_home(params, step, ctx: Context):
    ctx.device.home()
    return True


def h_text(params, step, ctx: Context):
    ctx.device.text(str(ctx.resolve(params)))
    return True


def h_sleep(params, step, ctx: Context):
    p = ctx.resolve(params)
    if isinstance(p, dict):
        secs = float(p.get("seconds", 1))
    else:
        secs = float(p)
    ctx.sleep(secs)
    return True


def h_log(params, step, ctx: Context):
    ctx.log(str(ctx.resolve(params)))
    return True


def h_find(params, step, ctx: Context):
    """Tìm ảnh. Trả True nếu thấy. Có thể đặt timeout để chờ."""
    p = ctx.resolve(params)
    image = p["image"]
    timeout = float(p.get("timeout", 0))
    conf = p.get("confidence")
    region = p.get("region")
    if timeout > 0:
        m = _wait_for(ctx, image, timeout, conf, region)
    else:
        m = ctx.find(image, confidence=conf, region=region)
    return m.found


def h_find_tap(params, step, ctx: Context):
    """Tìm ảnh (có thể chờ tới timeout) rồi tap vào tâm. Trả True nếu tap được."""
    p = ctx.resolve(params)
    image = p["image"]
    timeout = float(p.get("timeout", 0))
    conf = p.get("confidence")
    region = p.get("region")
    required = bool(p.get("required", False))
    m = _wait_for(ctx, image, timeout, conf, region) if timeout > 0 \
        else ctx.find(image, confidence=conf, region=region)
    if m.found:
        ctx.device.tap(m.x, m.y, jitter=int(p.get("jitter", 0)))
        ctx.log(f"Tap '{image}' ({m.confidence:.2f}) tại ({m.x},{m.y})")
        if "after" in p:
            ctx.sleep(float(p["after"]))
        return True
    if required:
        raise StepError(f"find_tap: bắt buộc nhưng không thấy '{image}' sau {timeout}s")
    ctx.log(f"Không thấy '{image}' (bỏ qua)")
    return False


def h_wait_image(params, step, ctx: Context):
    """Chờ ảnh xuất hiện. required=true sẽ báo lỗi nếu hết giờ."""
    p = ctx.resolve(params)
    m = _wait_for(ctx, p["image"], float(p.get("timeout", 15)),
                  p.get("confidence"), p.get("region"))
    if not m.found and p.get("required", False):
        raise StepError(f"wait_image: hết giờ chờ '{p['image']}'")
    return m.found


def h_wait_vanish(params, step, ctx: Context):
    """Chờ ảnh biến mất (vd màn loading)."""
    p = ctx.resolve(params)
    image = p["image"]
    end = time.time() + float(p.get("timeout", 30))
    while time.time() < end:
        if not ctx.find(image, confidence=p.get("confidence"), region=p.get("region")).found:
            return True
        ctx.sleep(0.6)
    return False


def h_if(params, step, ctx: Context):
    """Rẽ nhánh theo điều kiện ảnh. Đọc 'then'/'else' là sibling của 'if'."""
    p = ctx.resolve(params)
    cond = _eval_condition(p, ctx)
    branch = step.get("then") if cond else step.get("else")
    if branch:
        run_steps(branch, ctx)
    return cond


def h_loop(params, step, ctx: Context):
    """Lặp 'steps' (sibling). Điều kiện kết thúc (chọn 1 hoặc nhiều):
        times: N                 -> lặp đúng N lần
        while_image / until_image            -> theo 1 ảnh
        while_all_images / until_all_images  -> theo danh sách (TẤT CẢ)
        while_any_image  / until_any_image   -> theo danh sách (BẤT KỲ)
        max: N                   -> trần an toàn (mặc định 9999)
    """
    p = ctx.resolve(params) if isinstance(params, dict) else {}
    body = step.get("steps", [])
    times = p.get("times")
    conf = p.get("confidence")
    max_iter = int(p.get("max", 9999))

    def _stop_now() -> bool:
        # while_*: dừng khi điều kiện KHÔNG còn đúng
        if "while_image" in p and not ctx.find(p["while_image"], confidence=conf).found:
            return True
        if "while_all_images" in p and not ctx.find_all(p["while_all_images"], confidence=conf):
            return True
        if "while_any_image" in p and not ctx.find_any(p["while_any_image"], confidence=conf):
            return True
        # until_*: dừng khi điều kiện đã đúng
        if "until_image" in p and ctx.find(p["until_image"], confidence=conf).found:
            return True
        if "until_all_images" in p and ctx.find_all(p["until_all_images"], confidence=conf):
            return True
        if "until_any_image" in p and ctx.find_any(p["until_any_image"], confidence=conf):
            return True
        return False

    i = 0
    while i < max_iter:
        ctx.check_stop()
        if times is not None and i >= int(times):
            break
        if _stop_now():
            break
        run_steps(body, ctx)
        i += 1
    ctx.log(f"loop chạy {i} vòng")
    return True


def h_set(params, step, ctx: Context):
    """Gán biến: set: { ten_bien: gia_tri }."""
    for k, v in (params or {}).items():
        ctx.variables[k] = ctx.resolve(v)
    return True


def h_screenshot(params, step, ctx: Context):
    """Lưu ảnh màn hình ra file để debug."""
    from .vision import imwrite_unicode
    p = ctx.resolve(params) if isinstance(params, dict) else {"path": params}
    path = p.get("path", "debug_shot.png")
    imwrite_unicode(path, ctx.capture())
    ctx.log(f"Đã lưu screenshot: {path}")
    return True


def h_python(params, step, ctx: Context):
    """Gọi hàm Python tự viết (nâng cao). params: tên hàm trong custom.py.

    Hàm có chữ ký: def ten_ham(ctx, **kwargs) -> bool
    """
    p = ctx.resolve(params)
    name = p if isinstance(p, str) else p.get("func")
    kwargs = {} if isinstance(p, str) else {k: v for k, v in p.items() if k != "func"}
    fn = ctx.custom_funcs.get(name)
    if fn is None:
        raise StepError(f"python: không thấy hàm '{name}' trong custom.py")
    return bool(fn(ctx, **kwargs))


def _eval_condition(p: dict, ctx: Context) -> bool:
    """Điều kiện cho if. Hỗ trợ:
        image       -> 1 ảnh xuất hiện
        not_image   -> 1 ảnh KHÔNG xuất hiện
        all_images  -> [danh sách] tất cả xuất hiện
        any_image   -> [danh sách] có ít nhất 1
    """
    conf = p.get("confidence")
    if "image" in p:
        return ctx.find(p["image"], confidence=conf, region=p.get("region")).found
    if "not_image" in p:
        return not ctx.find(p["not_image"], confidence=conf, region=p.get("region")).found
    if "all_images" in p:
        return ctx.find_all(p["all_images"], confidence=conf)
    if "any_image" in p:
        return ctx.find_any(p["any_image"], confidence=conf)
    raise StepError(f"Điều kiện không hợp lệ: {p}")


HANDLERS: dict[str, Callable] = {
    "launch": h_launch,
    "stop_app": h_stop_app,
    "tap": h_tap,
    "tap_match": h_tap_match,
    "swipe": h_swipe,
    "key": h_key,
    "back": h_back,
    "home": h_home,
    "text": h_text,
    "sleep": h_sleep,
    "log": h_log,
    "find": h_find,
    "find_tap": h_find_tap,
    "wait_image": h_wait_image,
    "wait_vanish": h_wait_vanish,
    "if": h_if,
    "loop": h_loop,
    "set": h_set,
    "screenshot": h_screenshot,
    "python": h_python,
}


def run_step(step: dict, ctx: Context):
    if not isinstance(step, dict):
        raise StepError(f"Bước không hợp lệ (phải là dict): {step!r}")
    # tìm action = khoá đầu tiên khớp HANDLERS
    action = next((k for k in step if k in HANDLERS), None)
    if action is None:
        raise StepError(f"Bước không có action hợp lệ: {list(step)}")
    ctx.check_stop()
    return HANDLERS[action](step[action], step, ctx)


def run_steps(steps: list, ctx: Context, so_lan_cuu: int = 2):
    from .adb import AdbError
    for step in steps:
        lan = cuu = adb = cho = 0
        while True:
            try:
                run_step(step, ctx)
                break
            except (Stopped, TaskDone, BoQuaAcc):
                raise
            except AdbError as e:
                # adb server khởi động lại / rớt kết nối (gặp 19/10) -> lỗi máy, không phải lỗi tk: nối lại rồi làm lại
                if adb >= 3:
                    raise
                adb += 1
                ctx.log(f"adb rớt kết nối ({str(e)[:80]}) -> chờ 5s, nối lại, làm lại bước (lần {adb}/3)")
                ctx.sleep(5)
                try:
                    ctx.device.connect()
                except Exception:  # noqa: BLE001 - lần thử sau sẽ báo lỗi lại
                    pass
            except Exception as e:  # noqa: BLE001
                # bước lỗi thường do banner/popup che -> đóng được banner thì làm lại bước đó
                dong = ctx.custom_funcs.get("dong_banner")
                # dò ảnh mẫu X; không mẫu nào khớp thì hỏi Claude (banner lạ)
                if isinstance(e, StepError) and lan < 2 and dong is not None and dong(ctx, hoi_claude=True):
                    lan += 1
                    ctx.log("Bước bị banner che -> đã đóng banner, làm lại bước")
                    continue
                if ctx.cuu_loi is None:
                    raise
                # Claude xem màn hình, chọn 1 thao tác an toàn rồi làm lại bước; hết lượt / Claude chịu -> bỏ qua tk
                if cuu < so_lan_cuu and ctx.cuu_loi(step, e):
                    cuu += 1
                    ctx.log(f"Claude đã xử lý -> làm lại bước (lần cứu {cuu}/{so_lan_cuu})")
                    continue
                # vẫn chịu -> dừng chờ Claude (phiên /nth) điều khiển LDPlayer, đừng bỏ cả acc; tối đa 3 lần mỗi bước
                kq = ctx.cho_claude(step, e) if ctx.cho_claude is not None and cho < 3 else "BO_QUA"
                cho += 1
                if kq == "LAM_LAI":
                    continue
                if kq == "TIEP":             # Claude đã tự làm xong bước này -> đi bước sau
                    break
                raise BoQuaAcc(str(e)) from e


def load_custom_funcs(path: str) -> dict[str, Callable]:
    """Nạp các hàm trong custom.py (nếu có) cho action 'python'."""
    if not path or not os.path.exists(path):
        return {}
    spec = importlib.util.spec_from_file_location("nth_custom", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return {
        name: obj for name, obj in vars(mod).items()
        if callable(obj) and not name.startswith("_")
    }
