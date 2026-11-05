"""
Kho tài khoản Zing dùng CHUNG cho mọi instance (file accounts.yaml).

Mỗi acc: {user, pass, status, nv_xong, cap_nhat}. status:
    ""                -> chưa chạy (nv_xong > 0: đã làm dở tới nhân vật đó, lần sau làm tiếp)
    "running:<máy>"   -> đang chạy trên instance <máy>
    "done"            -> đã xong
    "error"           -> đăng nhập lỗi (sai mk / captcha...) -> bỏ qua
nv_xong : số nhân vật đã xong của tk (theo thứ tự), để chạy lại thì bỏ qua.
chon    : True = acc được tick "Chọn" trên UI -> máy được lấy để chạy; False = bỏ qua (thiếu = True).
private : True = kho acc private: KHÔNG BAO GIỜ quét xu / đưa gì lên web. Nút 'Chế độ thử nghiệm' trên UI
          (tên ngụy trang) chỉ ẩn/hiện bảng, không ảnh hưởng chạy hay ghi xu.
rut_vi  : True = lúc treo bán bấm "Rút vào ví" (tick trên UI); False = để người chơi tự rút sau.
da      : "trang" (mặc định) = cả acc mua + chế tơ bằng đá trắng tím; "vang" = cả acc mua + chế bằng đá vàng.
          2 luồng độc lập, không tự đổi qua nhau (UI cột "Đá vàng" / web chọn).
gio     : "HH:MM" = hẹn giờ chạy (trống = chạy ngay). gio_ngay: ngày đặt / cập nhật giờ (YYYY-MM-DD).
          Bot làm xong NHÂN VẬT 1 của acc hẹn giờ -> giờ hẹn = giờ xong đó (hôm sau bắt đầu đúng lúc hàng treo
          hôm trước vừa hết hạn) — xem dat_gio. Không chạy ngày nào thì giờ giữ nguyên.
nhan_vat: {tên nhân vật: thời điểm xong gần nhất} — OCR tên lúc chọn nhân vật, giữ vĩnh viễn để quản lý.
phieu   : {tên nhân vật: {bước: 'failed' / '3/4' / số..., 'luc': epoch}} — phiếu kết quả lượt gần nhất của từng
          nhân vật (ctx.ghi_phieu), giữ 3 ngày -> UI (tooltip), web (trang_thai.json), báo cáo cuối lượt.
treo    : "" | "cho" (tick "Treo lại" trên UI / web: chờ chế độ Treo lại tơ) | "running:<máy>" (đang treo lại).
          Chế độ Treo lại tơ chỉ đọc/ghi trường này, KHÔNG đụng status / nv_xong / nhan_vat (acc ✓ vẫn ✓).
cap_nhat: thời điểm (epoch) cập nhật trạng thái/tiến độ gần nhất. Qua 5h sáng ngày kế tiếp thì
          'done' và tiến độ dở dang tự reset (tk 'error' giữ nguyên để người dùng xem).

Các instance chạy song song trong cùng process -> claim/finish đi qua 1 lock
nên 2 máy không bao giờ nhận trùng 1 acc.
"""

from __future__ import annotations

import os
import re
import threading
import time
from datetime import date, datetime, timedelta

import yaml

from .orchestrator import resolve_config_path

_lock = threading.RLock()
RUNNING = "running:"


def path() -> str:
    return resolve_config_path("accounts.yaml")


def moc_reset(now: float | None = None) -> float:
    """Mốc 5h sáng gần nhất đã qua (hôm nay nếu đã quá 5h, không thì hôm qua)."""
    t = datetime.fromtimestamp(now or time.time())
    moc = t.replace(hour=5, minute=0, second=0, microsecond=0)
    if t < moc:
        moc -= timedelta(days=1)
    return moc.timestamp()


def load() -> list[dict]:
    with _lock:
        if not os.path.exists(path()):
            return []
        with open(path(), "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        if isinstance(data, dict):   # định dạng cũ (theo instance) -> gộp lại thành 1 kho
            data = [a for accs in data.values() for a in (accs or [])]
        accs = [{"user": str(a.get("user", "")).strip(), "pass": str(a.get("pass", "") or ""),
                 "status": str(a.get("status", "") or ""), "nv_xong": int(a.get("nv_xong", 0) or 0),
                 "cap_nhat": float(a.get("cap_nhat", 0) or 0), "rut_vi": bool(a.get("rut_vi", True)),
                 "chon": bool(a.get("chon", True)), "private": bool(a.get("private", False)),
                 "gio": str(a.get("gio", "") or ""), "gio_ngay": str(a.get("gio_ngay", "") or ""),
                 "nhan_vat": dict(a.get("nhan_vat") or {}), "phieu": dict(a.get("phieu") or {}),
                 "treo": str(a.get("treo", "") or ""),
                 "da": "vang" if a.get("da") == "vang" else "trang"} for a in data if a.get("user")]
        # qua 5h sáng ngày kế tiếp -> tk đã xong / làm dở được chạy lại từ đầu
        moc, doi = moc_reset(), False
        for a in accs:
            if a["cap_nhat"] < moc and (a["status"] == "done" or (a["status"] == "" and a["nv_xong"])):
                a["status"], a["nv_xong"], doi = "", 0, True
        if doi:
            save(accs)
        return accs


def save(accs: list[dict]):
    with _lock:
        # ghi file tạm rồi thay: bị tắt ngang lúc ghi (20/10 tool bị kill vì thiếu RAM) không làm rỗng kho acc
        with open(path() + ".tmp", "w", encoding="utf-8") as f:
            f.write("# Kho tài khoản Zing - quản lý trong UI. status: '' | running:<máy> | done | error\n")
            yaml.safe_dump(accs, f, allow_unicode=True, sort_keys=False)
        os.replace(path() + ".tmp", path())
        try:                         # trạng thái acc public lên web xu; lỗi web không được làm hỏng kho acc
            from . import xu
            xu.ghi_trang_thai(accs)
        except Exception as e:
            print(f"xu: ghi trạng thái lỗi: {e}")


def gio_hom_nay(a: dict, now: datetime | None = None) -> datetime | None:
    """Giờ chạy HÔM NAY của acc hẹn giờ (= giờ đang lưu; bot tự dời bằng dat_gio). Không hẹn -> None.
    'Hôm nay' theo ngày game (sang ngày lúc 5h sáng, như moc_reset): giờ 00:00-04:59 là đêm cuối của ngày đó.
    (27/10 01:06 acc hẹn 23:26 chưa kịp chạy -> trước đây tính 23:26 ngày 27, chờ gần 1 ngày, bỏ lượt 26/10.)"""
    if not a.get("gio"):
        return None
    now = now or datetime.now()
    h, m = (int(x) for x in a["gio"].split(":"))
    g = datetime.fromtimestamp(moc_reset(now.timestamp())).replace(hour=h, minute=m)
    return g + timedelta(days=1) if h < 5 else g


def dat_gio(user: str, gio: str, ep: bool = False) -> bool:
    """Acc ĐANG hẹn giờ -> đổi giờ hẹn thành `gio` (HH:MM), ngày đặt = hôm nay. Acc không hẹn giờ -> giữ nguyên.
    ep=True (lệnh từ web): đặt cả khi acc chưa hẹn giờ; gio '' = bỏ hẹn (chạy ngay)."""
    with _lock:
        accs = load()
        a = next((a for a in accs if a["user"] == user), None)
        if not a or not (a["gio"] or ep):
            return False
        a["gio"], a["gio_ngay"] = gio, date.today().isoformat()
        save(accs)
        return True


def _san_sang(a: dict, now: datetime) -> bool:
    gio = gio_hom_nay(a, now)
    return a["chon"] and not a["status"] and (gio is None or now >= gio)


def hen_som_nhat(now: datetime | None = None) -> datetime | None:
    """Giờ hẹn sớm nhất của acc được tick, chưa chạy, CHƯA tới giờ (bot chờ tới lúc đó). Không còn -> None."""
    now = now or datetime.now()
    hen = [g for a in load() if a["chon"] and not a["status"] and (g := gio_hom_nay(a, now)) and g > now]
    return min(hen, default=None)


def claim(device: str) -> dict | None:
    """Lấy acc ĐƯỢC TICK CHỌN + CHƯA CHẠY + (không hẹn giờ hoặc ĐÃ TỚI GIỜ) đầu tiên (cả public lẫn private),
    đánh dấu đang chạy trên `device`. Không có acc nào sẵn sàng -> None (xem hen_som_nhat để chờ).
    Nhiều acc cùng sẵn sàng -> ưu tiên acc PUBLIC trước, rồi mới tới acc private; trong mỗi loại acc làm dở
    trước (giữ thứ tự trong kho)."""
    with _lock:
        accs = load()
        now = datetime.now()
        # sort ổn định: public trước private; cùng loại thì acc LÀM DỞ (nv_xong > 0) trước, kẻo bỏ dở sang acc mới
        for a in sorted(accs, key=lambda a: (a["private"], not a["nv_xong"])):
            if _san_sang(a, now):
                a["status"], a["cap_nhat"] = RUNNING + device, time.time()
                save(accs)
                return a
        return None


NHOM_TREO = 5      # (26/10 user) chạy full xong cả 5 acc của 1 nhóm (31/10 user: 4 -> 5, kho lên 10 acc) -> treo lại các acc tick trong nhóm đó


def cho_treo_duoc(accs: list[dict] | None = None) -> list[dict]:
    """Acc tick "Treo lại" (treo == "cho") được treo NGAY: kho (public / private riêng) xếp như trên UI/web (giờ chạy,
    trống đầu, cùng giờ giữ thứ tự kho), chia nhóm NHOM_TREO acc; chỉ lấy acc thuộc nhóm mà mọi acc đã chạy full
    xong (✓ / ✗, hoặc bỏ tick Chọn). Thứ tự: nhóm đầu trước, public trước private."""
    accs = load() if accs is None else accs
    out = []
    for priv in (False, True):
        ds = sorted((a for a in accs if a["private"] == priv), key=lambda a: a["gio"])
        for i in range(0, len(ds), NHOM_TREO):
            nhom = ds[i:i + NHOM_TREO]
            if all(a["status"] in ("done", "error") or not a["chon"] for a in nhom):
                out += [a for a in nhom if a["treo"] == "cho"]
    return out


def ranh_cho_treo(phut: float = 30, now: datetime | None = None) -> bool:
    """Được treo lại (thêm 1 acc) không: không acc nào đang chạy full, không acc hẹn giờ nào chưa chạy mà đã tới giờ
    hoặc còn < `phut` phút (1 acc treo lại 6 nhân vật x 4 ô ~25-30 phút). Treo lại không đụng giờ hẹn."""
    now = now or datetime.now()
    accs = load()
    if any(a["status"].startswith(RUNNING) for a in accs):
        return False
    # acc HẸN GIỜ đã tới / sắp tới giờ -> chạy full trước; acc "chạy ngay" chờ nhóm treo xong (luật nhóm NHOM_TREO acc).
    # (26/10 user) acc chờ treo kế là PUBLIC -> treo trước cả acc private hẹn giờ (private chạy full sau)
    ke = cho_treo_duoc(accs)
    bo_private = bool(ke) and not ke[0]["private"]
    hen = [g for a in accs if a["chon"] and not a["status"] and not (bo_private and a["private"])
           and (g := gio_hom_nay(a, now))]
    return all(g - now >= timedelta(minutes=phut) for g in hen)


def claim_treo(device: str) -> dict | None:
    """Chế độ Treo lại tơ: lấy acc đầu tiên trong cho_treo_duoc (acc ✓ hôm nay cũng treo lại được). Không còn -> None."""
    with _lock:
        accs = load()
        for a in cho_treo_duoc(accs):
            a["treo"] = RUNNING + device
            save(accs)
            return a
        return None


def ghi_treo_lai(user: str, ten: str, so: int) -> bool:
    """Treo lại xong 1 nhân vật: ghi số ô vừa treo vào phiếu hôm nay của nhân vật đó ('treo lại', 'treo_lai_luc')
    -> UI / web hiện cạnh 'treo x/8 ô' lần chạy full. Tên OCR mỗi lần 1 kiểu -> so bằng xu.cung. Không có phiếu -> False."""
    from .xu import _chuan, cung
    with _lock:
        accs = load()
        a = next((a for a in accs if a["user"] == user), None)
        moc = moc_reset()
        k = next((k for k, p in (a or {}).get("phieu", {}).items()
                  if p.get("luc", 0) >= moc and cung(_chuan(k), _chuan(ten))), None) if ten else None
        if k is None:
            return False
        a["phieu"][k].update({"treo lại": int(so), "treo_lai_luc": time.time()})
        save(accs)
        return True


def set_treo(user: str, treo: str):
    with _lock:
        accs = load()
        for a in accs:
            if a["user"] == user:
                a["treo"] = treo
        save(accs)


def set_da(user: str, da: str):
    """Loại đá chế tơ của cả acc: "trang" | "vang" (giá trị khác -> "trang")."""
    with _lock:
        accs = load()
        for a in accs:
            if a["user"] == user:
                a["da"] = "vang" if da == "vang" else "trang"
        save(accs)


def set_status(user: str, status: str):
    with _lock:
        accs = load()
        for a in accs:
            if a["user"] == user:
                a["status"], a["cap_nhat"] = status, time.time()
        save(accs)


def set_nv_xong(user: str, n: int, ten: str = "", phieu: dict | None = None, xong: bool = True):
    """Ghi tiến độ: tk `user` đã xong `n` nhân vật đầu (theo thứ tự chạy); `ten` = tên nhân vật vừa xong,
    `phieu` = phiếu kết quả của nhân vật đó (giữ 3 ngày gần nhất).
    xong=False: nhân vật mới làm DỞ (tk bị bỏ qua giữa chừng) -> chỉ lưu phiếu, KHÔNG ghi vào `nhan_vat` (không thì
    lần chạy lại tưởng nhân vật đó đã làm hôm nay, bỏ qua luôn)."""
    with _lock:
        accs = load()
        for a in accs:
            if a["user"] == user:
                now = a["cap_nhat"] = time.time()
                a["nv_xong"] = int(n)
                if ten and xong:
                    a["nhan_vat"][ten] = now
                a["phieu"] = {t: p for t, p in a["phieu"].items() if p.get("luc", 0) > now - 3 * 86400}
                a["phieu"][ten or f"nv{n}"] = {**(phieu or {}), "luc": now}
        save(accs)


def loi_phieu(phieu: dict) -> list[str]:
    """Các bước lỗi trong phiếu 1 nhân vật: 'failed', hoặc 'x/y' với x < y (vd roll 3/4). ['chụp ảnh: failed', ...]"""
    out = []
    for k, v in phieu.items():
        m = re.fullmatch(r"(\d+)/(\d+)", str(v))
        if k != "luc" and (v == "failed" or (m and int(m[1]) < int(m[2]))):
            out.append(f"{k}: {v}")
    return out


def phieu_hom_nay(a: dict) -> list[tuple[str, dict, list[str]]]:
    """[(tên, phiếu, lỗi)] các nhân vật của tk `a` làm từ 5h sáng nay, theo thứ tự làm."""
    moc = moc_reset()
    return [(t, p, loi_phieu(p)) for t, p in sorted((a.get("phieu") or {}).items(), key=lambda x: x[1].get("luc", 0))
            if p.get("luc", 0) >= moc]


def bao_cao() -> str:
    """Báo cáo (markdown) các tk chạy hôm nay: từng nhân vật ✓ / ⚠ + bước lỗi. Acc private hiện tên giả."""
    trang = {"done": "✓ xong", "error": "✗ lỗi", "": "chưa xong"}
    dong = [f"# Báo cáo {datetime.now():%d/%m/%Y %H:%M}", ""]
    for a in load():
        ds = phieu_hom_nay(a)
        if not ds and a["status"] != "error":
            continue
        so_loi = sum(1 for *_, l in ds if l)
        st = "▶ đang chạy" if a["status"].startswith(RUNNING) else trang.get(a["status"], a["status"])
        dong.append(f"## {ten_hien(a['user'])} — {st} {a['nv_xong']}/6" + (f" — ⚠ {so_loi} nhân vật lỗi" if so_loi else ""))
        for t, p, loi in ds:
            dong.append(f"- {'⚠' if loi else '✓'} {t} ({datetime.fromtimestamp(p['luc']):%H:%M})"
                        + (": " + ", ".join(loi) if loi else ""))
        dong.append("")
    return "\n".join(dong)


def ten_hien(user: str) -> str:
    """Tên hiện trên UI / log: acc private -> 'tk testN' (N = thứ tự trong kho private), public -> chính tên tk."""
    priv = [a["user"] for a in load() if a["private"]]
    return f"tk test{priv.index(user) + 1}" if user in priv else user


def get(user: str) -> dict | None:
    return next((a for a in load() if a["user"] == user), None)


def release(device: str | None = None):
    """Trả acc 'đang chạy' (của `device`, hoặc mọi máy nếu None) về 'chưa chạy' — khi Stop/lỗi/mở lại tool."""
    with _lock:
        accs = load()
        hit = False
        for a in accs:
            if a["status"].startswith(RUNNING) and (device is None or a["status"] == RUNNING + device):
                a["status"] = ""
                hit = True
            if a["treo"].startswith(RUNNING) and (device is None or a["treo"] == RUNNING + device):
                a["treo"] = "cho"            # treo lại dở -> lần Start sau treo lại
                hit = True
        if hit:
            save(accs)
