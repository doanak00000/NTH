"""
Lưu xu của từng nhân vật (3 ngày gần nhất) vào xu_web/xu.json rồi đẩy lên GitHub Pages
(xu_web/ là bản clone repo Pages; trang xem: xu_web/index.html).

xu.json: {tk_zing: {"<tên nhân vật>": {"ngay":{"2026-10-19": {"xu": "1.049M", "chua_rut": "46413", "luc": "14:20"}}}}}
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import unicodedata
from datetime import datetime

from .orchestrator import resolve_config_path

_lock = threading.Lock()
_push_lock = threading.Lock()
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}
SO_NGAY = 3


def _chuan(ten: str) -> str:
    """Tên nhân vật để so trùng: bỏ dấu tiếng Việt, chỉ giữ chữ/số ASCII, chữ thường ('TrânCẩmˆ' -> 'trancam')."""
    s = unicodedata.normalize("NFD", ten.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if c.isascii() and c.isalnum()).lower()


def cung(a, b):
    """Cùng 1 nhân vật dù OCR mỗi lần 1 kiểu: giống >= 0.85 ('Hoa Phi'/'Hoa Phii' 0.92, 'KRXI'/'KRIXI' 0.89) HOẶC
    đoạn chung dài nhất >= 85% tên ngắn hơn (rác đầu/cuối: "TêXuânDao"/"Š TềXuânDa6" chung "texuanda" 8/9).
    Chỉ so trong 1 tk. Khác người trong cùng tk gần nhất đo được: MissU/KissU 0.80.
    (20/10: ngưỡng 0.9 làm KRIXI->'KRXI', NhưƠïnhY->'NhữDinhY' bị tưởng nhân vật mới -> làm lại lần 2.)"""
    from difflib import SequenceMatcher
    if not a or not b:
        return False
    sm = SequenceMatcher(None, a, b)
    chung = sm.find_longest_match(0, len(a), 0, len(b)).size
    return sm.ratio() >= 0.85 or chung >= 0.85 * min(len(a), len(b))


def _chon_ten(nvs: dict, ten: str) -> str:
    """Tên nhân vật đã có trong `nvs` mà OCR `ten` thuộc về (cùng luật `cung` lúc chọn nhân vật -> web khớp với
    việc bot coi là 'đã làm'); nhiều tên khớp -> giống nhất. Không khớp -> tên mới.
    So cả `bien_the` của mỗi tên: các kiểu OCR đọc sai đã biết ('DoRWA' của DoRy, 'LowU' của LoveU) — OCR sai
    giữa chữ quá xa để `cung` nhận ra, ghép tay 1 lần trên xu.json là lần sau tự ghép."""
    from difflib import SequenceMatcher
    c = _chuan(ten)
    khop = [(max(SequenceMatcher(None, c, _chuan(t)).ratio() for t in ten_k), k)
            for k in nvs for ten_k in [[k, *nvs[k].get("bien_the", [])]] if any(cung(c, _chuan(t)) for t in ten_k)]
    return max(khop)[1] if khop else ten


def web_dir() -> str:
    return resolve_config_path("xu_web")


def ghi(user: str, nv: int, ten: str, xu: str, chua_rut: str, log=print):
    """Ghi xu của nhân vật thứ `nv` (1..6) của tk `user` cho hôm nay, bỏ ngày cũ hơn 3 ngày gần nhất, rồi push."""
    path = os.path.join(web_dir(), "xu.json")
    now = datetime.now()
    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        # khoá theo TÊN: list nhân vật xếp theo lần chơi gần nhất nên số thứ tự đổi mỗi ngày
        nvs = data.setdefault(user, {})
        hom_nay = now.strftime("%Y-%m-%d")
        # OCR cùng 1 tên mỗi lần 1 kiểu ('HuưToàn'/'HưToàn', 'KRXI'/'KRIXI') -> ghép vào tên cũ
        key = _chon_ten(nvs, ten or f"nv{nv}")
        rec = nvs.setdefault(key, {"ngay": {}})
        if ten and _chuan(ten) != _chuan(key) and ten not in rec.setdefault("bien_the", []):
            rec["bien_the"].append(ten)          # nhớ kiểu OCR sai này -> lần sau khớp chắc hơn
        rec["ngay"][hom_nay] = {"xu": xu, "chua_rut": chua_rut, "luc": now.strftime("%H:%M")}
        rec["ngay"] = dict(sorted(rec["ngay"].items())[-SO_NGAY:])
        # ghi file tạm rồi thay: tắt ngang lúc ghi không để lại xu.json hỏng (đọc hỏng = mất hết lịch sử)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(path + ".tmp", path)
    log(f"xu: nv{nv} {ten or ''} xu={xu or '?'} chưa rút={chua_rut or '?'}")
    threading.Thread(target=_push, args=(log,)).start()   # không daemon: thoát tiến trình vẫn chờ push xong (20/10 mất push)


def _git(*a):
    return subprocess.run(["git", "-C", web_dir(), *a], capture_output=True, text=True, timeout=60, **_NO_WINDOW)


def _doc(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _da_ap_path() -> str:
    return resolve_config_path(os.path.join("logs", "lenh_web.json"))   # {tk: id lệnh đã áp} — máy này, không lên git


def ap_lenh(log=print) -> int:
    """lenh.json (web ghi lên repo): {"gio": {tk: {"gio": "HH:MM" | "", "id": "..."}}} -> đổi giờ chạy acc PUBLIC.
    Mỗi id áp đúng 1 lần (bot tự dời giờ sau nhân vật 1 thì lệnh cũ không đè lại). Trả số lệnh đã áp."""
    from . import accounts
    cu = _doc(_da_ap_path())
    da_ap, moi = dict(cu), []
    for user, l in (_doc(os.path.join(web_dir(), "lenh.json")).get("gio") or {}).items():
        lid, gio = str(l.get("id", "")), str(l.get("gio", ""))
        if not lid or da_ap.get(user) == lid:
            continue
        a = accounts.get(user)
        if a is None or a["private"] or not re.fullmatch(r"(([01]\d|2[0-3]):[0-5]\d)?", gio):
            log(f"web: bỏ lệnh giờ không hợp lệ ({user}: {gio!r})")
        else:
            moi.append((user, gio))
        da_ap[user] = lid
    if da_ap != cu:
        with open(_da_ap_path(), "w", encoding="utf-8") as f:   # ghi trước: save() bên dưới đẩy trang_thai kèm id đã nhận
            json.dump(da_ap, f, ensure_ascii=False, indent=1)
    for user, gio in moi:
        accounts.dat_gio(user, gio, ep=True)
        log(f"web: đổi giờ chạy {user} -> {gio or 'chạy ngay'}")
    return len(moi)


def nghe_lenh(log=print, chu_ky: float = 20):
    """Thread nền (mở UI là chạy): repo có commit mới (git ls-remote, vài chục byte) mới pull rồi áp lệnh web.
    Vòng đầu chạy ngay -> lệnh web gửi lúc tool đang tắt được áp khi mở tool."""
    def chay():
        while True:
            try:
                xa = _git("ls-remote", "origin", "HEAD").stdout.split()[:1]
                if xa and xa[0] != _git("rev-parse", "HEAD").stdout.strip():
                    with _push_lock:
                        _git("pull", "--rebase", "--autostash", "-q")
                ap_lenh(log)
            except Exception as e:  # noqa: BLE001 - mất mạng: vòng sau thử lại
                log(f"web: đọc lệnh lỗi: {e}")
            time.sleep(chu_ky)
    threading.Thread(target=chay, daemon=True).start()


def ghi_trang_thai(accs: list[dict], log=print):
    """Trạng thái chạy của acc PUBLIC -> xu_web/trang_thai.json (acc private không bao giờ lên web), rồi push.
    {tk: {"st": ""|"chay"|"do"|"xong"|"loi", "nv": nv_xong, "may": "[0] LD", "bat_dau": "YYYY-MM-DD HH:MM", "ket_thuc": ...}}
    Chỉ ghi + push khi có thay đổi. bat_dau = lúc nhận acc chạy; chạy tiếp acc dở trong ngày thì giữ giờ cũ.
    ket_thuc = lúc acc chuyển từ đang chạy sang xong/lỗi (bắt đầu lượt mới thì xoá)."""
    from .accounts import RUNNING, moc_reset, phieu_hom_nay
    path = os.path.join(web_dir(), "trang_thai.json")
    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cu = json.load(f)
        except (OSError, ValueError):
            cu = {}
        moc = datetime.fromtimestamp(moc_reset()).strftime("%Y-%m-%d %H:%M")
        da_ap = _doc(_da_ap_path())
        moi = {}
        for a in accs:
            if a.get("private", False):
                continue
            s = a["status"]
            st = "chay" if s.startswith(RUNNING) else {"done": "xong", "error": "loi"}.get(s, "do" if a["nv_xong"] else "")
            c = cu.get(a["user"], {})
            bat_dau = c.get("bat_dau", "")
            ket_thuc = c.get("ket_thuc", "")
            if st == "chay" and c.get("st") != "chay" and not (a["nv_xong"] and bat_dau >= moc):
                bat_dau, ket_thuc = datetime.now().strftime("%Y-%m-%d %H:%M"), ""
            elif st in ("xong", "loi") and c.get("st") == "chay":   # vừa chạy xong / lỗi -> giờ kết thúc
                ket_thuc = datetime.now().strftime("%Y-%m-%d %H:%M")
            moi[a["user"]] = {"st": st, "nv": a["nv_xong"], "may": s[len(RUNNING):] if st == "chay" else "",
                              "bat_dau": bat_dau, "ket_thuc": ket_thuc,
                              "gio": a["gio"], "lenh": da_ap.get(a["user"], ""),   # giờ hẹn + id lệnh web đã nhận
                              # nhân vật làm hôm nay + bước lỗi (phiếu kết quả) -> web hiện ✓ / ⚠ từng nhân vật
                              "nhan_vat": [{"ten": t, "luc": datetime.fromtimestamp(p["luc"]).strftime("%H:%M"),
                                            "loi": loi, "treo": p.get("treo"),   # số ô treo được (không tính lần kệ đầy)
                                            "het_to": bool(p.get("hết tơ"))}     # treo thiếu vì túi hết tơ
                                           for t, p, loi in phieu_hom_nay(a)]}
        if moi == cu:
            return
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(moi, f, ensure_ascii=False, indent=1)
        os.replace(path + ".tmp", path)
    threading.Thread(target=_push, args=(log,)).start()   # không daemon: thoát tiến trình vẫn chờ push xong (20/10 mất push)


def _push(log):
    """git commit + push xu.json, trang_thai.json (chạy nền; lỗi chỉ ghi log, không làm hỏng task)."""
    d = web_dir()
    with _push_lock:
        try:
            git = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True,
                                            timeout=60, **_NO_WINDOW)
            git("add", "xu.json")
            git("add", "trang_thai.json")      # tách riêng: file chưa có thì add lỗi, không kéo theo xu.json
            if git("diff", "--cached", "--quiet").returncode == 0:
                return
            git("commit", "-m", "cập nhật xu")
            r = git("push")
            if r.returncode != 0:            # web vừa ghi lenh.json -> remote đi trước: kéo về rồi push lại
                git("pull", "--rebase", "--autostash", "-q")
                r = git("push")
            if r.returncode != 0:
                log(f"xu: push GitHub lỗi: {(r.stderr or r.stdout).strip()[:200]}")
        except Exception as e:
            log(f"xu: push GitHub lỗi: {e}")
