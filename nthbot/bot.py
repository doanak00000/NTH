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
from .engine import BoQuaAcc, Context, Stopped, TaskDone, load_custom_funcs, run_steps
from .vision import TemplateStore

# Mốc "1 acc/1 vòng hoàn thành": log nào chứa marker này sẽ được UI tách
# sang ô log vàng riêng (tiến độ tài khoản). Không hiển thị ở log chính.
ACC_DONE_MARK = "⟦ACC⟧"  # ⟦ACC⟧


def _giu_may_thuc(bat: bool):
    """Windows: bot chạy thì không cho máy tự ngủ (bấm qua adb không tính là có người dùng -> máy để ngủ sau 30
    phút sẽ ngủ giữa chừng). Theo luồng bot: luồng xong / gọi False là máy ngủ bình thường lại."""
    import os
    if os.name == "nt":
        import ctypes
        # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if bat else 0x80000000)


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
        self.so_lan_hoi = 0       # số lần đã nhờ Claude cứu lỗi trong lượt chạy này
        self.dang_cuu = False     # đang chờ Claude -> watchdog đứng yên, không bấm chen

    # ---- log/state callbacks -------------------------------------------
    def _log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        try:   # log đầy đủ ra file theo ngày (UI chỉ giữ 10 dòng) -> lỗi lúc vắng mặt vẫn xem lại được
            import os
            from .orchestrator import app_dir
            os.makedirs(os.path.join(app_dir(), "logs"), exist_ok=True)
            with open(os.path.join(app_dir(), "logs", time.strftime("%Y-%m-%d") + ".log"), "a",
                      encoding="utf-8") as f:
                f.write(f"{self.device.name} {line}\n")
        except OSError:
            pass
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

    def _cho_gio_hen(self, som: float = 180):
        """Task dùng kho acc (nhan_acc) mà chưa acc nào tới giờ, còn acc hẹn giờ -> CHƯA bật LDPlayer (đang bật thì
        tắt), chờ tới `som` giây trước giờ hẹn mới bật: đỡ tốn RAM cả buổi (Start 7h, acc hẹn 10h -> 9h57 mới bật)."""
        from datetime import datetime, timedelta
        from . import accounts
        if not any(isinstance(s, dict) and (s.get("python") or {}).get("func") == "nhan_acc" for s in self.task.steps):
            return
        now = datetime.now()
        hen = accounts.hen_som_nhat(now)
        if hen is None or any(accounts._san_sang(a, now) for a in accounts.load()):
            return
        mo_luc = hen - timedelta(seconds=som)
        if mo_luc <= now:
            return
        self._tat_ldplayer()
        self._log(f"Chưa tới giờ hẹn ({hen:%H:%M}) -> {mo_luc:%H:%M} mới bật LDPlayer")
        while datetime.now() < mo_luc:
            if self.stop_event.wait(min(30.0, max(1.0, (mo_luc - datetime.now()).total_seconds()))):
                raise Stopped()

    def _bat_ldplayer(self, timeout: float = 240):
        """Instance LDPlayer đang tắt -> bật lên, chờ Android boot xong + adb kết nối được."""
        from .ldplayer import list_instances, start_instance
        d = self.device
        inst = next((i for i in list_instances(d.ldconsole_path) if i.index == d.ld_index), None)
        if inst is None:
            raise RuntimeError(f"Không thấy instance LDPlayer #{d.ld_index}")
        if not inst.running:
            self._log("Bật LDPlayer...")
            start_instance(d.ldconsole_path, d.ld_index)
        end = time.time() + timeout
        while time.time() < end:
            if self.stop_event.is_set():
                raise Stopped()
            try:
                if d.connect() and d.getprop("sys.boot_completed") == "1":
                    return
            except Exception:  # noqa: BLE001 - đang boot, adb chưa sẵn sàng
                pass
            time.sleep(3)
        raise RuntimeError(f"LDPlayer #{d.ld_index} không boot xong sau {timeout:.0f}s")

    def _tat_ldplayer(self):
        """Chạy xong hết -> tắt instance LDPlayer của máy này (LDPlayer chạy lâu rò bộ nhớ: 19/10 ăn ~52 GB làm adb
        chết). Start lần sau _bat_ldplayer tự bật lại. Instance không quản lý qua ldconsole (ld_index None) -> để yên."""
        d = self.device
        if d.ld_index is None:
            return
        from .ldplayer import quit_instance
        try:
            quit_instance(d.ldconsole_path, d.ld_index)
            self._log("Đã tắt LDPlayer để giải phóng bộ nhớ.")
        except Exception as e:  # noqa: BLE001 - tắt không được thì thôi, việc chính đã xong
            self._log(f"Không tắt được LDPlayer: {e}")

    def _watchdog(self, ctx, chu_ky: float = 15, ket: float = 90):
        """Chạy song song: bot không có tiến triển (không ghi log) quá `ket` giây -> gần như chắc chắn
        bị banner/popup che -> gọi dong_banner (custom.py): dò ảnh mẫu X, không thấy thì hỏi Claude.
        (Không dùng "màn hình đứng im" vì màn chính / màn đăng nhập luôn có cảnh động.)"""
        dong = ctx.custom_funcs.get("dong_banner")
        if dong is None:
            return
        while not self.stop_event.wait(chu_ky) and self.state == "running":
            im = time.time() - ctx.tien_trien
            if im < ket or self.dang_cuu:
                continue
            self._log(f"Watchdog: {im:.0f}s không có tiến triển -> dò banner")
            try:
                if self._bam_cho_anr():
                    ctx.tien_trien = time.time()
                    continue
                dong(ctx, hoi_claude=True)
            except Exception:  # noqa: BLE001 - Stop giữa chừng / lỗi adb: vòng sau thử lại
                pass
            ctx.tien_trien = time.time()

    def _bam_cho_anr(self) -> bool:
        """Hộp thoại Android "<app> isn't responding" (game đang tải tài nguyên, 21/10 che màn đăng nhập, Claude
        dò banner trả NONE) -> bấm Wait. Có hộp thoại -> True."""
        import re
        if "aerr_wait" not in (xml := self.device.shell(
                "uiautomator dump /sdcard/anr.xml >/dev/null && cat /sdcard/anr.xml", timeout=30)):
            return False
        m = re.search(r'aerr_wait"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
        if not m:
            return False
        x1, y1, x2, y2 = map(int, m.groups())
        self.device.tap((x1 + x2) // 2, (y1 + y2) // 2)
        self._log("Watchdog: game không phản hồi (ANR) -> bấm Wait")
        return True

    def _chan_doan_loi(self, loi: str):
        """CHỈ khi task lỗi (chạy êm thì không tốn token): chụp màn hình + lấy log cuối -> nhờ Claude Code local
        (`claude -p`, chỉ được ĐỌC) chẩn đoán nguyên nhân + đề xuất sửa -> logs/loi_<giờ>.md.
        Không cho Claude tự sửa code lúc không có người xem."""
        import os
        import shutil
        import subprocess
        from .orchestrator import app_dir
        from .vision import imwrite_unicode
        exe = shutil.which("claude")
        if not exe:
            return
        goc = app_dir()
        ten = time.strftime("loi_%Y%m%d_%H%M%S")
        anh = os.path.join(goc, "logs", ten + ".png")
        try:
            imwrite_unicode(anh, self.device.screencap())
        except Exception:  # noqa: BLE001 - LDPlayer có thể đã treo
            anh = "(không chụp được)"
        log_file = os.path.join(goc, "logs", time.strftime("%Y-%m-%d") + ".log")
        try:
            with open(log_file, encoding="utf-8") as f:
                cuoi = "".join(l for l in f.readlines() if l.startswith(self.device.name))[-6000:]
        except OSError:
            cuoi = ""
        prompt = (
            f"Tool auto game NTH (thư mục {goc}) vừa LỖI trên máy {self.device.name}: {loi}\n"
            f"Ảnh màn hình lúc lỗi: {anh}\nLog cuối:\n{cuoi}\n\n"
            "Đọc ảnh + log, xem code liên quan (custom.py, tasks/thanh_nhai_thu_6acc.yaml, KINH_NGHIEM.md) để chẩn "
            "đoán NGUYÊN NHÂN và đề xuất cách SỬA cụ thể (hàm/dòng nào, sửa gì). KHÔNG sửa file. Trả lời tiếng Việt, ngắn gọn.")
        self._log("Đã nhờ Claude chẩn đoán lỗi...")
        try:
            out = subprocess.run([exe, "-p", prompt, "--allowedTools", "Read", "Glob", "Grep"], cwd=goc,
                                 capture_output=True, timeout=300,
                                 creationflags=0x08000000 if os.name == "nt" else 0)
            bao_cao = out.stdout.decode("utf-8", "replace").strip()
        except (subprocess.TimeoutExpired, OSError) as e:
            bao_cao = f"(gọi Claude lỗi: {e})"
        md = os.path.join(goc, "logs", ten + ".md")
        with open(md, "w", encoding="utf-8") as f:
            f.write(f"# Lỗi {time.strftime('%d/%m %H:%M')} — {self.device.name}\n\n**Lỗi:** {loi}\n\n"
                    f"**Ảnh:** {anh}\n\n## Claude chẩn đoán\n\n{bao_cao}\n")
        self._log(f"Claude chẩn đoán xong: {md}")

    _PROMPT_CUU = (
        "Bạn đang cứu 1 bot auto game Nghịch Thủy Hàn (LDPlayer, màn hình 960x540) vừa bị KẸT.\n"
        "Bước đang làm: {buoc}\nLỗi: {loi}\nẢnh màn hình hiện tại: {anh} (dùng Read để xem)\nLog cuối:\n{log}\n\n"
        "Kinh nghiệm về game (đọc nếu cần): {kn}\n"
        "Xem ảnh, đoán vì sao kẹt (popup/thông báo che, đang ở sai màn hình, game treo...) rồi chọn ĐÚNG 1 thao tác:\n"
        "  BAM x y        - bấm 1 điểm (vd nút OK / X / Đóng của popup đang che)\n"
        "  VE_MAN_CHINH   - đóng hết trang con, về màn hình chính\n"
        "  MO_LAI_GAME    - tắt và mở lại game (game treo / màn đen / văng)\n"
        "  LAM_LAI        - không cần làm gì, chỉ làm lại bước (lỗi thoáng qua)\n"
        "  BO_QUA         - không cứu được (sai mật khẩu, captcha, bảo trì...) -> bot bỏ qua tài khoản này\n"
        "KHÔNG sửa file nào. Dòng CUỐI CÙNG của câu trả lời chỉ ghi đúng thao tác, vd: BAM 480 304")

    def _claude_cuu(self, ctx, step, loi, toi_da=8) -> bool:
        """Bước lỗi (đã thử đóng banner): nhờ Claude Code local xem ảnh + log, chọn 1 thao tác AN TOÀN trong game
        (bấm / về màn chính / mở lại game / làm lại / bỏ qua) rồi bot tự làm. Claude chỉ được ĐỌC (ảnh, log,
        KINH_NGHIEM), không sửa code. True = đã xử lý, làm lại bước; False = chịu -> bỏ qua tk."""
        import os
        import re
        import shutil
        import subprocess
        from .orchestrator import app_dir
        from .vision import imwrite_unicode
        if "ĐĂNG NHẬP THẤT BẠI" in str(loi):   # sai mật khẩu: Claude cũng không cứu được -> khỏi tốn token
            return False
        exe = shutil.which("claude")
        if not exe or self.so_lan_hoi >= toi_da:
            self._log("Cứu lỗi: không có Claude / đã hỏi quá nhiều lần trong lượt này -> bỏ qua")
            return False
        self.so_lan_hoi += 1
        goc = app_dir()
        ten = time.strftime("cuu_%Y%m%d_%H%M%S")
        anh = os.path.join(goc, "logs", ten + ".png")
        try:
            imwrite_unicode(anh, self.device.screencap())
        except Exception as e:  # noqa: BLE001 - LDPlayer treo / mất kết nối
            self._log(f"Cứu lỗi: không chụp được màn hình ({e}) -> bỏ qua")
            return False
        try:
            with open(os.path.join(goc, "logs", time.strftime("%Y-%m-%d") + ".log"), encoding="utf-8") as f:
                cuoi = "".join(l for l in f.readlines() if l.startswith(self.device.name))[-4000:]
        except OSError:
            cuoi = ""
        buoc = next((f"{k}: {v}" for k, v in step.items()), str(step))
        prompt = self._PROMPT_CUU.format(buoc=buoc, loi=loi, anh=anh, log=cuoi,
                                         kn=os.path.join(goc, "KINH_NGHIEM.md"))
        self._log(f"Cứu lỗi: nhờ Claude xem màn hình (lần {self.so_lan_hoi}/{toi_da})...")
        self.dang_cuu = True
        try:
            out = subprocess.run([exe, "-p", prompt, "--allowedTools", "Read", "Grep"], cwd=goc,
                                 capture_output=True, timeout=300,
                                 creationflags=0x08000000 if os.name == "nt" else 0)
            tra_loi = out.stdout.decode("utf-8", "replace").strip()
        except (subprocess.TimeoutExpired, OSError) as e:
            tra_loi = f"(gọi Claude lỗi: {e})"
        finally:
            self.dang_cuu = False
            ctx.tien_trien = time.time()
        with open(os.path.join(goc, "logs", ten + ".md"), "w", encoding="utf-8") as f:
            f.write(f"# Cứu lỗi {time.strftime('%d/%m %H:%M')} — {self.device.name}\n\n**Bước:** {buoc}\n\n"
                    f"**Lỗi:** {loi}\n\n**Ảnh:** {anh}\n\n## Claude\n\n{tra_loi}\n")
        dong = (tra_loi.splitlines() or [""])[-1].strip().upper()
        if m := re.fullmatch(r"BAM\s+(\d{1,3})\s+(\d{1,3})", dong):
            x, y = int(m[1]), int(m[2])
            if not (0 <= x < 960 and 0 <= y < 540):
                self._log(f"Cứu lỗi: Claude trả toạ độ ngoài màn hình ({x},{y}) -> bỏ qua")
                return False
            self._log(f"Cứu lỗi: Claude bảo BẤM ({x},{y})")
            self.device.tap(x, y)
            ctx.sleep(3)
        elif dong == "VE_MAN_CHINH":
            self._log("Cứu lỗi: Claude bảo VỀ MÀN HÌNH CHÍNH")
            ctx.custom_funcs["ve_man_hinh_chinh"](ctx)
        elif dong == "MO_LAI_GAME":
            self._log("Cứu lỗi: Claude bảo MỞ LẠI GAME")
            self.device.stop_app(ctx.package)
            ctx.sleep(3)
            ctx.custom_funcs["khoi_dong_game"](ctx)
            from . import accounts
            user = ctx.variables.get("_zing_user")
            if user and accounts.get(user):   # mở lại game = về màn đăng nhập -> vào lại đúng tk (nhân vật chưa làm)
                ctx.custom_funcs["doi_tk_zing"](ctx, accounts.get(user), tu_duoi=True)
        elif dong == "LAM_LAI":
            self._log("Cứu lỗi: Claude bảo LÀM LẠI bước")
        else:
            self._log(f"Cứu lỗi: Claude chịu ({dong[:60] or 'không trả lời'}) -> bỏ qua")
            return False
        return True

    def _cho_claude(self, ctx, step, loi, phut: float = 15) -> str:
        """Cứu tự động thất bại -> DỪNG CHỜ Claude phiên /nth (skill nth) điều khiển LDPlayer qua adb, thay vì bỏ cả acc.
        Ghi logs/cho_claude_<máy>.json (+ ảnh .png); Claude ghi "tra_loi": LAM_LAI (làm lại bước) / TIEP (đã tự làm
        xong bước, đi bước sau) / BO_QUA (bỏ acc). Quá `phut` phút không ai trả lời (không có phiên /nth) -> BO_QUA."""
        import json
        import os
        import re
        from .orchestrator import app_dir
        from .vision import imwrite_unicode
        path = os.path.join(app_dir(), "logs", "cho_claude_" + re.sub(r"\W+", "_", self.device.name).strip("_") + ".json")
        anh = path[:-5] + ".png"
        try:
            imwrite_unicode(anh, self.device.screencap())
        except Exception:  # noqa: BLE001 - LDPlayer treo: Claude tự chụp lại
            anh = ""
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"may": self.device.name, "serial": self.device.serial,
                       "buoc": next((f"{k}: {v}" for k, v in step.items()), str(step)), "loi": str(loi),
                       "acc": ctx.variables.get("_zing_user", ""), "nv": int(ctx.variables.get("_acc_idx", 0) or 0) + 1,
                       "anh": anh, "luc": time.strftime("%H:%M:%S"), "tra_loi": ""}, f, ensure_ascii=False, indent=1)
        self._log(f"⟦CHỜ CLAUDE⟧ tự cứu không được -> chờ Claude điều khiển tối đa {phut:.0f} phút "
                  f"({os.path.basename(path)})")
        self.dang_cuu = True                 # watchdog đứng yên, không bấm chen lúc Claude điều khiển
        kq, het = "BO_QUA", time.time() + phut * 60
        try:
            while time.time() < het:
                ctx.sleep(3)                 # Stop trên UI -> Stopped
                try:
                    with open(path, encoding="utf-8") as f:
                        tl = str(json.load(f).get("tra_loi", "")).strip().upper()
                except (OSError, ValueError):   # Claude đang ghi dở
                    continue
                if tl in ("LAM_LAI", "TIEP", "BO_QUA"):
                    kq = tl
                    break
            else:
                self._log(f"Chờ Claude quá {phut:.0f} phút -> bỏ qua tk")
        finally:
            self.dang_cuu = False
            ctx.tien_trien = time.time()
            try:
                os.remove(path)
            except OSError:
                pass
        self._log(f"Claude trả lời: {kq}")
        return kq

    def _moc_code(self) -> float:
        """Giờ sửa mới nhất của custom.py + ảnh mẫu (thấy đổi -> nạp lại)."""
        import os
        files = [self.custom_path] + [e.path for e in os.scandir(self.templates.dir) if e.is_file()]
        return max((os.path.getmtime(f) for f in files if os.path.exists(f)), default=0.0)

    def _ghi_bao_cao(self):
        """Chạy xong -> logs/bao_cao_<ngày>.md: từng tk, từng nhân vật hôm nay ✓ / ⚠ + bước lỗi (đọc 1 file là biết
        nhân vật nào cần làm bù, khỏi rà log)."""
        import os
        from . import accounts
        from .orchestrator import app_dir
        try:
            noi_dung = accounts.bao_cao()
            path = os.path.join(app_dir(), "logs", time.strftime("bao_cao_%Y%m%d.md"))
            with open(path, "w", encoding="utf-8") as f:
                f.write(noi_dung)
            so = noi_dung.count("\n- ⚠")
            self._log(f"Báo cáo: {path}" + (f" — ⚠ {so} nhân vật lỗi" if so else " — mọi nhân vật đủ ✓"))
        except Exception as e:  # noqa: BLE001 - báo cáo lỗi không được làm hỏng kết thúc task
            self._log(f"Không ghi được báo cáo: {e}")

    def _bo_qua_acc(self, ctx, loi):
        """Cứu không được -> đánh ✗ lỗi tk Zing đang làm, quên tiến độ trong ctx; vòng sau nhan_acc lấy tk kế
        (doi_tk_zing tự đăng xuất từ màn hình nào cũng được). Lỗi lúc đăng nhập: nhan_acc đã đánh ✗ sẵn."""
        from . import accounts
        user = ctx.variables.pop("_zing_user", None)
        ctx.variables.pop("_dn_lai", None)   # bỏ hẳn tk đăng nhập lỗi, vòng sau không thử lại
        idx = int(ctx.variables.get("_acc_idx", 0) or 0)
        ctx.variables["_acc_idx"] = 0
        phieu = ctx.variables.pop("_phieu", {})
        if user:
            # nhân vật đang làm dở: lưu phiếu + bước làm dừng -> UI/web/báo cáo thấy rõ (tiến độ nv_xong giữ nguyên)
            phieu[f"dừng ({str(loi)[:60]})"] = "failed"
            accounts.set_nv_xong(user, idx, ctx.variables.get("_ten_nv", ""), phieu, xong=False)
            accounts.set_status(user, "error")
        self._log(f"⟦ACC⟧ BỎ QUA tài khoản {accounts.ten_hien(user) if user else '(đang đăng nhập)'}: {loi}")

    # ---- thân chạy ------------------------------------------------------
    def _run(self):
        self._set_state("running")
        self._log(f"Bắt đầu task '{self.task.name}'")
        _giu_may_thuc(True)
        try:
            if self.device.ld_index is not None:
                self._cho_gio_hen()
                self._bat_ldplayer()
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

            log_goc = ctx.log

            def log_tien_trien(msg):
                ctx.tien_trien = time.time()
                log_goc(msg)
            ctx.log = log_tien_trien
            ctx.cuu_loi = lambda step, loi: self._claude_cuu(ctx, step, loi)
            ctx.cho_claude = lambda step, loi: self._cho_claude(ctx, step, loi)
            threading.Thread(target=self._watchdog, args=(ctx,), daemon=True).start()

            repeat = self.task.repeat
            count = bo_qua_lien = 0
            moc_code = self._moc_code()
            while repeat == 0 or count < repeat:
                ctx.check_stop()
                # sửa custom.py / ảnh mẫu lúc tool đang chạy -> nạp lại đầu vòng (giữa 2 nhân vật), khỏi tắt tool
                if (moc := self._moc_code()) != moc_code:
                    moc_code = moc
                    try:
                        ctx.custom_funcs = load_custom_funcs(self.custom_path)
                        self.templates._cache.clear()
                        self._log("Nạp lại custom.py + ảnh mẫu (code vừa sửa)")
                    except Exception as e:  # noqa: BLE001 - code mới lỗi cú pháp -> chạy tiếp bằng code cũ
                        self._log(f"Nạp lại custom.py lỗi, giữ code cũ: {e}")
                if repeat != 1:
                    self._log(f"--- Vòng task #{count + 1} ---")
                try:
                    run_steps(self.task.steps, ctx)
                    bo_qua_lien = 0
                except TaskDone as e:
                    self._log(f"Kết thúc: {e}")
                    break
                except BoQuaAcc as e:
                    bo_qua_lien += 1
                    self._bo_qua_acc(ctx, e)
                    if bo_qua_lien >= 3:   # lỗi hệ thống (LDPlayer treo, game bảo trì...) -> đừng đốt hết kho acc
                        raise RuntimeError(f"bỏ qua {bo_qua_lien} tài khoản liên tiếp -> dừng máy") from e
                count += 1

            self._log("Hoàn tất.")
            self._ghi_bao_cao()
            self._set_state("done")
            self._tat_ldplayer()

        except Stopped:
            self._log("Đã dừng theo yêu cầu.")
            self._set_state("stopped")
        except Exception as e:  # noqa: BLE001
            self.last_error = f"{e}"
            self._log(f"LỖI: {e}")
            self._log(traceback.format_exc().strip().splitlines()[-1])
            self._set_state("error")
            threading.Thread(target=self._chan_doan_loi, args=(str(e),), daemon=True).start()
        finally:
            _giu_may_thuc(False)
            from . import accounts   # import muộn: accounts -> orchestrator -> bot (vòng)
            accounts.release(self.device.name)   # Stop/lỗi giữa chừng -> acc về "chưa chạy"
