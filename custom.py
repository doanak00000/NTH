"""
(NÂNG CAO - tuỳ chọn) Viết hàm Python riêng để gọi từ task qua action `python`.

Trong task .yaml:
    - python: { func: vi_du, nguong: 0.9 }

Mỗi hàm nhận ctx (Context) + các tham số keyword, trả về True/False.
Qua ctx bạn truy cập:
    ctx.device      -> tap/swipe/screencap... (xem nthbot/adb.py)
    ctx.find(img)   -> tìm ảnh, trả Match(found, x, y, confidence)
    ctx.log("...")  -> ghi log ra UI
    ctx.sleep(s)    -> ngủ nhưng vẫn dừng được khi bấm Stop
    ctx.variables   -> dict biến của task
"""

import time


def ve_man_hinh_chinh(ctx, image="nut_dong.png", max=8, cho=1.2, confidence=None):
    """Bấm nút đóng (X) lặp lại cho tới khi KHÔNG còn thấy nút đóng nữa
    -> coi như đã đóng hết popup/màn con và về màn hình chính.

    (Game này bỏ qua phím Back cứng nên không dùng Back nữa.)

    Dùng trong task:  - python: { func: ve_man_hinh_chinh }
    Đổi ảnh nút đóng:  - python: { func: ve_man_hinh_chinh, image: "nut_x.png" }
    """
    closed, da_do_banner = 0, False
    for _ in range(int(max)):
        scr = ctx.capture()
        # màn chọn nhân vật: nút back ở đây = "đăng nhập lại?" -> KHÔNG bấm
        if ctx.find("xong_pha_giang_ho.png", region=(600, 430, 360, 110), screen=scr).found:
            break
        # nút back xanh (đa số trang) hoặc vàng (trang Thanh Nhai Thư)
        m = next((m for img in (image, "nut_dong_vang.png")
                  if (m := ctx.find(img, confidence=confidence, screen=scr)).found), None)
        if m is None:
            if dong_banner(ctx):             # banner / màn chờ che mất nút back -> đóng rồi dò lại
                continue
            da_do_banner = True              # vừa dò banner xong, không có -> khỏi dò lại (~1.3s/lần)
            break
        ctx.device.tap(m.x, m.y)
        closed += 1
        ctx.sleep(cho)
    # popup sự kiện / quảng cáo hay bật lên giữa chừng (vd sau Thanh Nhai Thư). Vừa dò banner rồi thì chỉ dò lại
    # khi màn hình đổi rõ (popup làm tối cả màn, lệch >10; màn đứng yên ~1-2): chụp 0.3s thay vì dò X ~1.3s
    if not da_do_banner or _man_doi(scr, ctx.capture()):
        dong_banner(ctx)
    ctx.log(f"Về màn hình chính: đã đóng {closed} màn (không còn nút đóng).")
    return True


def _man_doi(truoc, sau, nguong=5.0):
    """2 ảnh màn hình lệch trung bình > nguong (0-255) -> coi như màn đã đổi (vd popup mới bật)."""
    import numpy as np
    return truoc is None or sau is None or float(np.abs(sau.astype(np.int16) - truoc).mean()) > nguong


_X_MAC_DINH = ("dong_update.png", "dong_thong_bao.png", "dong_quang_cao.png")
# banner có nút X trong suốt (mẫu X trượt khi nền game đổi): mốc trên ảnh banner -> toạ độ nút X của nó
_MOC_BANNER = {"moc_nhat_nien.png": (754, 105)}   # 'Nhất Niên Hồi Ức' (10-22/10): nút 'Kể Chuyện Ngay!'


def _tim_nut_x(ctx, screen, confidence=0.85):
    """Tìm nút X đóng banner: thử mọi mẫu X đã biết + mọi file 'x_*.png' trong templates/,
    ở nhiều tỉ lệ (banner to nhỏ khác nhau thì nút X cũng to nhỏ / lệch chỗ). Trả Match tốt nhất."""
    import os
    from nthbot.vision import Match, find_template
    # màn chờ (game để im lâu tự hiện): chạm bất kỳ chỗ nào là mất -> trả về như 1 nút X để bấm
    m = find_template(screen, ctx.templates.get("man_cho.png"), confidence=confidence)
    if m.found:
        ctx.log("Màn chờ (để im lâu) -> chạm để thoát")
        return m
    names = list(_X_MAC_DINH) + sorted(f for f in os.listdir(ctx.templates.dir)
                                       if f.startswith("x_") and f.endswith(".png"))
    best = Match(found=False)
    for n in names:
        m = find_template(screen, ctx.templates.get(n), confidence=confidence, multi_scale=True)
        if m.found and m.confidence > best.confidence:
            best = m
    if not best.found:
        best = _tim_nut_x_hinh(ctx, screen, names)
    if not best.found:
        # nút X trong suốt, nền đổi là mẫu X trượt -> nhận BANNER bằng 1 mốc cố định trên ảnh banner, bấm X đúng chỗ
        for moc, (x, y) in _MOC_BANNER.items():
            m = find_template(screen, ctx.templates.get(moc), confidence=confidence)
            if m.found:
                return Match(found=True, x=x, y=y, confidence=m.confidence, width=32, height=32)
    # nút ✕ thu bảng Hoạt động (917,28) giống nút X quảng cáo -> bảng đang mở (thấy Cài đặt) thì bỏ
    if best.found and best.x > 890 and best.y < 50 and             find_template(screen, ctx.templates.get("cai_dat.png"), confidence=confidence).found:
        return Match(found=False)
    return best


_PROMPT_CLAUDE_X = (
    "Đọc file ảnh {path} (ảnh chụp màn hình game, kích thước 960x540 pixel). Nếu có POPUP NỔI đè lên "
    "màn hình (quảng cáo, khuyến mãi nạp thẻ, sự kiện, thông báo) có nút đóng X, hãy trả về toạ độ pixel "
    "TÂM của nút X đó theo dạng: X,Y . Các TRANG CHỨC NĂNG chiếm cả màn hình của game (trang giao dịch/"
    "bán hàng, túi đồ, nghề nghiệp, nhân vật) KHÔNG tính, kể cả khi có nút X. Nếu không có popup cần "
    "đóng thì trả: NONE . Chỉ trả đúng 1 dòng, không giải thích.")


def _hoi_claude_nut_x(ctx, screen, timeout=120):
    """Banner lạ (không có ảnh mẫu X): gửi ảnh màn hình cho Claude Code local (`claude -p`, dùng
    subscription trên máy) hỏi toạ độ nút đóng. Ảnh được giữ lại ở banner_moi/ để cắt mẫu x_*.png sau.
    Trả (x, y) hoặc None (không có claude / Claude bảo không có banner / trả lời lạ)."""
    import os
    import re
    import shutil
    import subprocess
    from nthbot.orchestrator import app_dir
    from nthbot.vision import imwrite_unicode
    exe = shutil.which("claude")
    if not exe:
        return None
    thu_muc = os.path.join(app_dir(), "banner_moi")
    os.makedirs(thu_muc, exist_ok=True)
    path = os.path.join(thu_muc, time.strftime("%Y%m%d_%H%M%S") + f"_{ctx.device.name}.png".replace(" ", ""))
    imwrite_unicode(path, screen)
    ctx.log("Hỏi Claude tìm nút đóng banner lạ...")
    try:
        out = subprocess.run([exe, "-p", _PROMPT_CLAUDE_X.format(path=path), "--allowedTools", "Read"],
                             cwd=thu_muc, capture_output=True, timeout=timeout,
                             creationflags=0x08000000 if os.name == "nt" else 0)
        text = out.stdout.decode("utf-8", "replace").strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        ctx.log(f"Claude lỗi: {e}")
        return None
    m = re.search(r"(\d{1,3})\s*,\s*(\d{1,3})\s*$", text)
    if not m:
        ctx.log(f"Claude: không có banner cần đóng ({text[-40:]!r})")
        os.remove(path)                      # chỉ giữ ảnh có banner thật để cắt mẫu
        return None
    x, y = int(m.group(1)), int(m.group(2))
    if not (0 <= x < 960 and 0 <= y < 540):
        return None
    ctx.log(f"Claude: nút đóng ở ({x},{y}) — ảnh lưu ở {path}, nên cắt nút X thành x_*.png")
    return x, y


def _tim_nut_x_hinh(ctx, screen, names, region=(740, 0, 220, 160), nguong=0.87):
    """Dò nút X theo HÌNH DẠNG nét trắng (ảnh nhị phân sáng > 200) ở góc trên-phải, nơi banner đặt nút X.
    Nút X trắng trong suốt một phần -> nền banner đổi màu là so ảnh màu tụt còn ~0.7, nhưng hình dạng vẫn
    khớp > 0.89. Màn không có banner cao nhất ~0.82 (nút X bảng bán) -> ngưỡng 0.87 (đo 18/10)."""
    import cv2
    import numpy as np
    from nthbot.vision import Match

    def trang(img):
        return (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 200).astype(np.float32)

    x0, y0, w, h = region
    vung = trang(screen[y0:y0 + h, x0:x0 + w])
    best = Match(found=False)
    for n in names:
        t0 = trang(ctx.templates.get(n))
        for sc in (0.8, 0.9, 1.0, 1.1, 1.25):
            t = cv2.resize(t0, None, fx=sc, fy=sc)
            if t.sum() < 10 or t.shape[0] > h or t.shape[1] > w:
                continue
            _, v, _, loc = cv2.minMaxLoc(cv2.matchTemplate(vung, t, cv2.TM_CCOEFF_NORMED))
            if v >= nguong and v > best.confidence:
                best = Match(found=True, x=x0 + loc[0] + t.shape[1] // 2, y=y0 + loc[1] + t.shape[0] // 2,
                             confidence=float(v), width=t.shape[1], height=t.shape[0])
    return best


def dong_banner(ctx, max=8, cho=2.5, confidence=0.85, hoi_claude=False):
    """Đóng hết banner quảng cáo / thông báo (nút X mỗi banner một chỗ, một cỡ).

    Gặp banner mới mà bot không đóng được: dùng '✂ Cắt ảnh mẫu' cắt sát nút X của nó,
    lưu tên bắt đầu bằng 'x_' (vd x_banner_tet.png) -> lần sau tự đóng, không cần sửa code.
    hoi_claude=True: không ảnh mẫu nào khớp thì hỏi Claude Code local (watchdog / bước lỗi lần 2 dùng).

    Trong task .yaml:  - python: { func: dong_banner }
    """
    closed = 0
    for _ in range(int(max)):
        scr = ctx.capture()
        m = _tim_nut_x(ctx, scr, confidence)
        if not m.found:
            xy = _hoi_claude_nut_x(ctx, scr) if hoi_claude and closed == 0 else None
            if xy is None:
                break
            ctx.device.tap(*xy)
            closed += 1
            ctx.sleep(float(cho))
            continue
        ctx.device.tap(m.x, m.y)
        closed += 1
        ctx.log(f"dong_banner: đóng banner tại ({m.x},{m.y}) [{m.confidence:.2f}]")
        ctx.sleep(float(cho))
    return closed > 0


def mo_hoat_dong(ctx, xy=(920, 31), lan=3, cho=4.0):
    """Mở bảng Hoạt động (nút góc phải trên màn chính). Game đôi khi bỏ qua lần bấm đầu
    -> bấm xong kiểm tra bảng đã mở (thấy nút Cài đặt) chưa, chưa thì đóng banner rồi bấm lại."""
    from nthbot.engine import StepError
    for _ in range(int(lan)):
        ctx.device.tap(int(xy[0]), int(xy[1]))
        if _cho_qua_popup(ctx, "cai_dat.png", timeout=cho).found:
            return True
        dong_banner(ctx)
    raise StepError("không mở được bảng Hoạt động")


def chup_anh(ctx, icon_xy=(33, 506), chup_xy=(854, 462), thoat_xy=(34, 25), lan=3, cho=8.0):
    """Nhiệm vụ chụp ảnh: nút máy ảnh -> bấm chụp -> chờ nút X vàng góc phải trên (xong_chup_anh.png ~863,57;
    hiện sau khi chụp) -> bấm X -> thoát chế độ chụp (34,25).
    Game đôi khi bỏ qua lần bấm chụp (6 lần/2 ngày; 20/10 TrânCẩm chờ 20s không thấy nút X -> hụt nhiệm vụ ->
    Thanh Nhai Thư 3/4) -> `cho` giây chưa thấy nút X thì bấm chụp lại. Bình thường nút X hiện ~2s sau khi chụp.

    Trong task .yaml:  - python: { func: chup_anh }
    """
    # icon máy ảnh cố định góc trái dưới -> bấm thẳng toạ độ: dò ảnh phụ thuộc nền (21/10 TháiHậu nền đá sáng chỉ
    #  khớp 0.77 -> failed). Kết quả vẫn kiểm bằng nút X sau khi chụp.
    ctx.device.tap(int(icon_xy[0]), int(icon_xy[1]), jitter=1)
    ctx.log(f"chụp ảnh: bấm icon máy ảnh ({icon_xy[0]},{icon_xy[1]})")
    ctx.sleep(3)
    icon = dict(confidence=0.7, region=(0, 460, 90, 80))
    for i in range(int(lan)):
        # icon máy ảnh còn trên màn = CHƯA vào chế độ chụp (game bỏ qua lần bấm icon; 21/10 KhâuSơnTùng: bấm chụp 3
        #  lần trên màn chính) -> bấm lại icon trước
        if i and _find_tap(ctx, "nut_start_chup_anh.png", 0, 3, **icon):
            ctx.log("chụp ảnh: chưa vào chế độ chụp -> bấm lại icon máy ảnh")
        ctx.device.tap(int(chup_xy[0]), int(chup_xy[1]), jitter=1)
        if _find_tap(ctx, "xong_chup_anh.png", cho, 2):
            break
        ctx.log(f"chụp ảnh: chưa thấy nút X sau khi chụp -> bấm chụp lại ({i + 1}/{lan})")
    else:
        ctx.ghi_phieu("chụp ảnh", "failed", loi=True)
    ctx.device.tap(int(thoat_xy[0]), int(thoat_xy[1]), jitter=1)
    ctx.sleep(2)
    return True


def mong_hoa_luc(ctx, xa_giao=(319, 498), tab=(30, 122), thu=(632, 240), vung_like=(200, 240, 140, 110),
                 lan=3, cho=1.5, nguong=10.0):
    """Mộng Hoa Lục: xã giao -> tab Mộng Hoa Lục -> bấm nút like 2 lần (1 like + 1 unlike: lúc đầu đã like hay chưa
    đều được, miễn mỗi lần bấm nút ĐỔI trạng thái) -> thu xã giao (`ve_man_hinh_chinh` sau đó đóng nốt).
    Kiểm tra bằng ảnh: thấy nút like (`like_da.png` xanh/1, `like_chua.png` xám/0; trên trang khớp >=0.95, màn khác
    <=0.57) = đã vào đúng trang; mỗi lần bấm vùng nút phải đổi (đổi trạng thái lệch 28–99, đứng yên 0 — đo 20/10).
    Hụt -> bấm lại tối đa `lan` lần; vẫn hỏng -> phiếu 'mộng hoa lục: failed' + ảnh.

    Trong task .yaml:  - python: { func: mong_hoa_luc }
    """
    def tim_nut():
        return next((m for img in ("like_da.png", "like_chua.png")
                     if (m := ctx.find(img, region=tuple(vung_like), confidence=0.85)).found), None)

    nut = None
    for i in range(int(lan)):
        if i:                                # chưa thấy nút: lần 2 bấm lại tab, lần 3 thu xã giao rồi mở lại từ đầu
            ctx.log(f"mộng hoa lục: chưa thấy nút like -> thử lại ({i + 1}/{lan})")
        if i != 1:
            if i == 2:
                ctx.device.tap(*thu)
                ctx.sleep(1.5)
            ctx.device.tap(*xa_giao)
            ctx.sleep(2.5)
        ctx.device.tap(*tab)
        ctx.sleep(2.5)
        if (nut := tim_nut()) is not None:
            break
    if nut is None:
        ctx.ghi_phieu("mộng hoa lục", "failed", loi=True)
        ctx.device.tap(*thu)
        ctx.sleep(1.5)
        return False

    def vung():
        return ctx.capture()[nut.y - 10:nut.y + 10, nut.x - 10:nut.x + 10]

    for k, ten in enumerate(("like", "unlike")):
        for i in range(int(lan)):
            truoc = vung()
            ctx.device.tap(nut.x, nut.y)
            ctx.sleep(float(cho))
            if _man_doi(truoc, vung(), nguong):
                break
            ctx.log(f"mộng hoa lục: bấm {ten} không đổi trạng thái -> bấm lại ({i + 1}/{lan})")
        else:
            ctx.ghi_phieu(f"mộng hoa lục ({ten})", "failed", loi=True)
            break
    ctx.device.tap(*thu)
    ctx.sleep(1.5)
    return True


_O_TNT_X = (296, 416, 536, 656, 776)   # mép trái 5 ô Đề Cử (rộng 113, y 285-430) trang Thanh Nhai Thư
_LAM_LAI_TNT = {"chụp ảnh": "tnt_chup_anh.png", "mộng hoa lục": "tnt_mong_hoa_luc.png",
                "hảo cảm": "tnt_hao_cam.png", "nghề nghiệp": "tnt_nghe_nghiep.png"}


def _mo_tnt(ctx):
    """Mở trang Thanh Nhai Thư (đang ở đó thì thôi). Game hay bỏ qua lần bấm mở (20/10 doangia1608 DoanMyy: vẫn ở màn
    chính -> roll 0 ô, bỏ cả TNT) -> chưa thấy nút back vàng (= trang TNT) thì bấm lại icon, tối đa 3 lần."""
    for lan in range(3):
        if _cho_qua_popup(ctx, "nut_dong_vang.png", timeout=4, dong_x=False).found:
            return True
        ctx.log(f"Thanh Nhai Thư: trang chưa mở -> bấm lại icon ({lan + 1}/3)")
        _find_tap(ctx, "thanh_nhai_thu.png", 5, 3, required=False)
    return False


def _o_tnt_chua_lam(ctx, scr):
    """Ô Đề Cử nào là 1 trong 4 nhiệm vụ bot tự làm (_LAM_LAI_TNT) mà vẫn CHƯA LÀM -> [(ô, tên)].
    Đo 21/10 trên 54 ô thật: tiêu đề mẫu tnt_*.png khớp >= 0.90 cả 3 trạng thái, nhiệm vụ khác <= 0.60 (ngưỡng 0.8);
    chưa làm = còn nút roll góc trên phải (>= 0.82, ô xong/đã nhận <= 0.35; ngưỡng 0.6)."""
    import cv2
    from nthbot.vision import find_template
    roll = ctx.templates.get("roll_thanh_nhai_thu.png")
    xam = cv2.cvtColor(scr, cv2.COLOR_BGR2GRAY)
    out = []
    for i, x in enumerate(_O_TNT_X):
        if not find_template(scr[285:330, x + 60:x + 113], roll, confidence=0.6).found:
            continue
        vung = xam[315:355, x:x + 113]
        for ten, mau in _LAM_LAI_TNT.items():
            t = cv2.cvtColor(ctx.templates.get(mau), cv2.COLOR_BGR2GRAY)
            if cv2.minMaxLoc(cv2.matchTemplate(vung, t, cv2.TM_CCOEFF_NORMED))[1] >= 0.8:
                out.append((i, ten))
                break
    return out


def _lam_lai_nv_tnt(ctx, ten):
    """Nhiệm vụ `ten` (1 trong _LAM_LAI_TNT) vẫn chưa làm trên Thanh Nhai Thư -> về màn chính làm lại, mở lại trang."""
    ctx.log(f"Thanh Nhai Thư: '{ten}' vẫn CHƯA LÀM -> đã sót bước, về màn chính làm lại")
    ctx.ghi_phieu(f"làm lại {ten}", 1)
    ve_man_hinh_chinh(ctx)
    {"chụp ảnh": chup_anh, "mộng hoa lục": mong_hoa_luc, "hảo cảm": hao_cam, "nghề nghiệp": che_to}[ten](ctx)
    ve_man_hinh_chinh(ctx)
    _find_tap(ctx, "thanh_nhai_thu.png", 20, 4)
    _mo_tnt(ctx)


def hao_cam(ctx):
    """Hảo Cảm (tặng quà): Hoạt động -> Hảo Cảm -> Tương Hội -> chọn người (905,121) -> chọn quà (619,184) -> Tặng
    -> hảo cảm đầy thì popup 'phần dư quy đổi sang Ngọc Tri Tâm, tiếp tục tặng?' -> Xác Nhận. Không thấy nút ->
    phiếu 'hảo cảm: failed' + ảnh (bỏ qua, làm tiếp). Rồi ve_man_hinh_chinh ở task.

    Trong task .yaml:  - python: { func: hao_cam }
    """
    mo_hoat_dong(ctx)                        # tự bấm lại nếu game bỏ qua
    for img in ("hao_cam.png", "tuong_hoi.png"):
        if not _find_tap(ctx, img, 20, 2.5):
            ctx.ghi_phieu("hảo cảm", "failed", loi=True)
    ctx.device.tap(905, 121, jitter=1)
    ctx.sleep(2)
    ctx.device.tap(619, 184, jitter=1)
    ctx.sleep(2)
    if not _find_tap(ctx, "tang.png", 20, 2):
        ctx.ghi_phieu("hảo cảm", "failed", loi=True)
    _find_tap(ctx, "xac_nhan.png", 2, 2)
    return True


def roll_thanh_nhai_thu(ctx, positions=None, image="roll_thanh_nhai_thu.png",
                        target=4, region=100, cho=1.5, max_rounds=120, max_giay=180,
                        confidence=0.78, confirm=None, settle=0.7, bam_nhan=True):
    """Roll 5 ô Thanh Nhai Thư tới khi đủ `target` ô trúng nhiệm vụ đã làm.
    Quá `max_giay` giây (vd hụt nhiệm vụ chụp ảnh -> không bao giờ đủ 4 ô) thì thôi, đi tiếp nhận mốc.

    Cơ chế: mỗi ô có 1 nút roll (ảnh `image`). Bấm LẦN LƯỢT từng vị trí trong `positions`:
      - Ô CÒN nút roll  -> bấm để roll lại (random nhiệm vụ khác).
      - Ô đã từng có nút roll mà giờ MẤT -> đã trúng nhiệm vụ đã làm -> bấm để NHẬN THƯỞNG.
    Dừng khi đã nhận thưởng đủ `target` ô (mặc định 4 / trong 5 ô).

    An toàn:
      - NHẬN THƯỞNG ở ô KHÔNG có nút roll CHỈ KHI detection đang chạy đúng
        (trong vòng đó có >=1 ô khác đang thấy nút roll) -> tránh claim bừa khi dò lỗi.
        Nhờ vậy cover được cả ô VỪA MỞ ĐÃ TRÚNG (không có nút roll từ đầu).
      - Nút roll "mất" thì chờ `settle` rồi dò lại mới quyết (tránh nhiễu do animation).
      - Một vòng mà KHÔNG bấm được gì -> dừng + cảnh báo (không claim bừa rồi thoát).

    Trong task .yaml:
      - python:
          func: roll_thanh_nhai_thu
          positions: [["{r1_x}","{r1_y}"], ...]   # 5 vị trí tâm nút roll
          target: 4
          region: 100        # cạnh ô vuông (px) quanh mỗi vị trí để dò nút roll
          confidence: 0.78   # ngưỡng dò nút roll (nút roll thật ~0.82-1.0)
          confirm: "nut_dong.png"   # (tuỳ chọn) ảnh đóng popup thưởng sau khi nhận
          bam_nhan: false    # không bấm ô đã trúng (thưởng nhận 1 lần ở mốc hoạt động ngày)
    """
    if not positions:
        ctx.log("roll_thanh_nhai_thu: chưa truyền 'positions' (5 vị trí nút roll).")
        return False

    _mo_tnt(ctx)
    pts = [(int(round(float(p[0]))), int(round(float(p[1])))) for p in positions]
    half = int(region) // 2

    def has_roll(x, y):
        reg = (max(0, x - half), max(0, y - half), int(region), int(region))
        return ctx.find(image, confidence=confidence, region=reg).found

    def _claim(i, x, y):
        # ô đã nhận trước đó (dấu tích) mà bấm vào thì game CHUYỂN sang hoạt động đó -> chỉ bấm
        # khi ô đang hiện chữ 'Nhận'
        if bam_nhan and not ctx.find("o_nhan.png", region=(x - 100, 375, 130, 50)).found:
            ctx.log(f"Ô {i + 1}: đã nhận từ trước ({x},{y}) [{len(claimed) + 1}/{target}]")
            truoc.add(i)
            return
        if not bam_nhan:                              # chỉ ghi nhận ô đã trúng; thưởng nhận 1 lần ở mốc
            ctx.log(f"Ô {i + 1}: đã trúng ({x},{y}) [{len(claimed) + 1}/{target}]")
            return
        ctx.device.tap(x, y)                          # bấm đúng chỗ nút roll cũ = nhận thưởng
        ctx.log(f"Ô {i + 1}: NHẬN THƯỞNG ({x},{y}) [{len(claimed) + 1}/{target}]")
        if confirm:
            ctx.sleep(0.8)
            try:
                m = ctx.find(confirm)
                if m.found:
                    ctx.device.tap(m.x, m.y)
            except Exception:
                pass

    import time
    claimed, da_lam_lai, truoc = set(), set(), set()
    ctx.variables["_tnt_xong_truoc"] = False
    rounds, het_gio = 0, time.time() + float(max_giay)
    while len(claimed) < int(target) and rounds < int(max_rounds):
        if time.time() > het_gio:
            ctx.log(f"roll_thanh_nhai_thu: quá {float(max_giay):.0f}s chưa đủ {target} ô -> thôi roll, đi tiếp")
            break
        rounds += 1
        scr = ctx.capture()
        # 0) 1 trong 4 nhiệm vụ bot tự làm mà ô vẫn CHƯA LÀM = đã sót bước đó -> về làm lại (mỗi nhiệm vụ 1 lần), mở lại
        #  trang; ô đó thành 'Nhận' -> vòng sau nhận như thường. Không có thì roll mù tới 180s vẫn không đủ 4 ô.
        sot = [t for _, t in _o_tnt_chua_lam(ctx, scr) if t not in da_lam_lai]
        if sot:
            for t in dict.fromkeys(sot):
                da_lam_lai.add(t)
                _lam_lai_nv_tnt(ctx, t)
            het_gio = time.time() + float(max_giay)   # thời gian làm lại không tính vào hạn roll
            continue
        # 1) chụp trạng thái: ô nào đang CÓ nút roll
        active = [i for i in range(len(pts)) if i not in claimed]
        present = {i: has_roll(*pts[i]) for i in active}
        detection_ok = any(present.values())   # có ít nhất 1 nút roll -> template đang match được

        progressed = False
        for i in active:
            ctx.check_stop()
            x, y = pts[i]
            if present[i]:
                ctx.device.tap(x, y)                  # còn nút roll -> roll lại
                progressed = True
                ctx.log(f"Ô {i + 1}: roll ({x},{y})")
                ctx.sleep(float(cho))
            elif detection_ok:
                # không có nút roll & detection đang chạy đúng -> ô đã trúng -> nhận thưởng
                ctx.sleep(float(settle))
                if has_roll(x, y):
                    continue                          # nhiễu animation, thực ra vẫn còn
                _claim(i, x, y)
                claimed.add(i)
                progressed = True
                ctx.sleep(float(cho))
            # else: không ô nào thấy nút roll -> nghi dò lỗi -> bỏ qua, không claim
        if not progressed:
            ctx.log("roll_thanh_nhai_thu: 1 vòng không bấm được gì -> dừng. "
                    "Kiểm tra lại ảnh roll / vị trí r1..r5 / region / confidence.")
            break

    ok = len(claimed) >= int(target)
    # đủ ô mà ô nào cũng 'đã nhận từ trước' = TNT đã làm xong trước khi bot tới (người chơi tay) -> mốc cũng đã nhận
    ctx.variables["_tnt_xong_truoc"] = len(truoc) >= int(target)
    ctx.ghi_phieu("roll", f"{len(claimed)}/{target}", loi=not ok)
    ctx.log(f"Thanh Nhai Thư: đã nhận {len(claimed)}/{target} ô sau {rounds} vòng"
            + ("" if ok else " (CHƯA ĐỦ - kiểm tra lại vị trí/ảnh roll/region)"))
    return ok


def nhan_moc_hoat_dong(ctx, xs=(205, 278, 350, 424), y=488, cho=2.0):
    """Trang Thanh Nhai Thư: bấm lần lượt các mốc 'Tiến Độ Hoạt Động Ngày' (20/40/60/80).
    Có quà -> 'Chúc Mừng Nhận' -> bấm chỗ trống đóng; không có quà -> bảng thông tin -> tắt."""
    from nthbot.engine import StepError
    if not ctx.find("nut_dong_vang.png").found:   # nút back vàng = đang ở trang Thanh Nhai Thư
        raise StepError("nhan_moc_hoat_dong: không ở trang Thanh Nhai Thư")
    nhan = 0
    for x in xs:
        ctx.device.tap(int(x), int(y))
        ctx.sleep(float(cho))
        if ctx.find("chuc_mung_nhan.png").found:
            nhan += 1
            ctx.device.tap(480, 450)         # 'nhấn vào chỗ trống để đóng'
        else:
            ctx.device.tap(620, 30)          # vùng trống trên tiêu đề -> tắt bảng thông tin
        ctx.sleep(1.2)
    if nhan == 0 and ctx.variables.get("_tnt_xong_truoc"):   # 21/10 KissU/Tắcc báo ⚠ 0/4 oan: mốc nhận từ trước
        ctx.log("Tiến độ hoạt động ngày: 4 ô đã nhận từ trước -> mốc cũng đã nhận từ trước")
        ctx.ghi_phieu("mốc", "đã nhận từ trước")
        return True
    ctx.log(f"Tiến độ hoạt động ngày: nhận {nhan}/{len(xs)} mốc")
    # mốc = thước đo chính: game chỉ cho đủ 4/4 khi mọi nhiệm vụ nhỏ xong (kể cả bước không tự kiểm tra được:
    #  mộng hoa lục, du ngoạn bấm toạ độ)
    ctx.ghi_phieu("mốc", f"{nhan}/{len(xs)}", loi=nhan < len(xs))
    return True


def _nav_to(ctx, nav, tx, ty):
    """Đi tới toạ độ (tx, ty) qua bản đồ + nhập toạ độ.

    `nav` là dict mô tả luồng (toạ độ các nút/ô nhập):
      open      : [x,y] nút mở bản đồ
      open_wait : giây chờ bản đồ mở (mặc định 2)
      field_x   : [x,y] ô nhập toạ độ X (tap rồi gõ số)
      field_y   : [x,y] ô nhập toạ độ Y
      clear     : True/False có xoá nội dung ô trước khi gõ (mặc định True)
      go        : [x,y] nút "đi tới / xác nhận"
      go_wait   : giây chờ chạy tới nơi (mặc định 10)
    """
    def _type(field, value):
        ctx.device.tap(int(field[0]), int(field[1]))
        ctx.sleep(0.4)
        if nav.get("clear", True):
            # bôi đen + xoá nội dung cũ trong ô
            ctx.device.key("KEYCODE_MOVE_END")
            for _ in range(8):
                ctx.device.key("KEYCODE_DEL")
        ctx.device.text(str(value))
        ctx.sleep(0.4)

    ctx.log(f"Đi tới toạ độ ({tx},{ty}) qua bản đồ")
    ctx.device.tap(int(nav["open"][0]), int(nav["open"][1]))
    ctx.sleep(float(nav.get("open_wait", 2)))
    if "field_x" in nav:
        _type(nav["field_x"], tx)
    if "field_y" in nav:
        _type(nav["field_y"], ty)
    if "go" in nav:
        ctx.device.tap(int(nav["go"][0]), int(nav["go"][1]))
    ctx.sleep(float(nav.get("go_wait", 10)))


_REG_XONG_PHA_NV = (600, 430, 360, 110)   # nút Xông Pha Giang Hồ góc phải dưới = đang ở màn chọn nhân vật


def _doc_ten_nv(ctx, reg=(700, 398, 130, 24)):
    """OCR tên nhân vật ĐANG CHỌN ở ô tên góc phải dưới màn chọn nhân vật (chữ trắng). Tiếng Việt (tessdata/vie).
    Không đọc ở dòng trong list: dòng 4 chỉ hiện 1 phần -> OCR mỗi lần 1 kiểu ('niêm Bäna' / 'DiêmBảoKỳ').
    Ô này đọc ổn định, chỉ hay thừa/thiếu dấu cách — web xu ghép tên bỏ qua dấu cách."""
    import os
    import re
    import cv2
    from nthbot.orchestrator import app_dir
    from nthbot.vision import _load_pytesseract
    import numpy as np
    try:
        tess = _load_pytesseract()
        x, y, w, h = reg
        k = 3
        g = cv2.cvtColor(ctx.capture()[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
        _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw = 255 - bw
        # nét bút trang trí bên phải ô tên + nền -> rác cuối tên ('La Xuân -z', 'Hoa Phii'). Thân chữ trắng tinh (>=190),
        #  nét bút/nền tối hơn -> lấy cụm cột trắng lớn nhất làm vùng chữ, xoá phần ngoài (dấu tiếng Việt mảnh không đủ
        #  sáng nên vẫn đọc từ ảnh Otsu). Đo 20/10 trên 12 tên thật: đúng 7/12 -> 10/12 (bỏ dấu 11/12)
        cot = np.where((g >= 190).sum(0) >= 2)[0]
        if len(cot):
            chinh = max(np.split(cot, np.where(np.diff(cot) > 8 * k)[0] + 1), key=len)
            bw[:, :max(0, chinh[0] - 3 * k)] = 255
            bw[:, chinh[-1] + 3 * k:] = 255
        bw = cv2.copyMakeBorder(bw, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)   # lề trắng: tesseract đọc ổn hơn
        # shortcut: đường dẫn không được có dấu cách (pytesseract giữ nguyên dấu ngoặc kép) — đổi chỗ cài nếu có
        tdir = os.path.join(app_dir(), "tessdata").replace("\\", "/")
        t = tess.image_to_string(bw, lang="vie", config=f"--tessdata-dir {tdir} --psm 7")
        return re.sub(r"^[\W_]+|[\W_]+$", "", t.strip())   # rác đầu/cuối: "_— Hoa Phi", "IGGY _"
    except Exception:  # noqa: BLE001 - OCR lỗi không được làm hỏng luồng chính
        return ""


# 6 dòng màn chọn nhân vật (x, y, số lần cuộn xuống trước khi bấm), đo trên 960x540. Dòng 4 chỉ hiện 1 phần.
_DONG_NV = [(139, 115, 0), (139, 202, 0), (176, 290, 0), (164, 369, 0), (109, 233, 1), (119, 322, 1)]


_REG_LIST_NV = (40, 80, 290, 320)     # vùng list nhân vật (bên trái) -> so ảnh xem cuộn có ăn
_REG_TEN_NV = (700, 398, 130, 24)     # ô tên nhân vật đang chọn (góc phải dưới) -> so ảnh xem bấm có ăn


def _da_lam_hom_nay(ctx, ten_cu=""):
    """Tên (đã _chuan) các nhân vật của tk đang đăng nhập đã làm từ 5h sáng (+ `ten_cu`)."""
    from nthbot import accounts
    from nthbot.xu import _chuan
    acc = accounts.get(ctx.variables.get("_zing_user") or ctx.variables.get("_dang_nhap", "")) or {}
    moc = accounts.moc_reset()
    return [_chuan(t) for t, luc in (acc.get("nhan_vat") or {}).items() if luc >= moc] + \
        ([_chuan(ten_cu)] if ten_cu else [])


def _chon_tu_duoi(ctx, dong=_DONG_NV, ten_cu="", scroll_keo=(152, 352, 152, 80), sau_vuot=2.0, lan=3, nguong=15.0):
    """Màn chọn nhân vật: cuộn xuống đáy rồi chọn DÒNG DƯỚI CÙNG. List xếp theo lần chơi gần nhất (vừa chơi -> nhảy
    lên đầu) -> dòng cuối luôn là nhân vật lâu chưa chơi nhất -> 6 lần là đủ 6 nhân vật, KHÔNG cần đọc đúng tên
    (20/10: chọn theo tên OCR làm lại nhân vật cũ khi OCR đọc lệch; cuộn hụt mà không biết -> bỏ sót dòng 5-6).
    Kiểm tra bằng ẢNH: cuộn xong vùng list phải đổi (lệch ~28; hụt <3, nhiễu <=9 — đo trên debug_scroll/), bấm xong
    ô tên phải đổi (đổi nhân vật ~37-62; không đổi <5). Hụt -> làm lại tối đa `lan` lần.
    List không cuộn được (tk < 5 nhân vật) / bấm không đổi -> chọn theo tên như cũ (_chon_theo_ten).
    Trả True nếu đã chọn được nhân vật (False chỉ từ nhánh dự phòng: tk đã làm hết)."""
    def vung(scr, r):
        x0, y0, w, h = r
        return scr[y0:y0 + h, x0:x0 + w]

    for i in range(int(lan)):
        truoc = ctx.capture()
        keo_that(ctx, *scroll_keo)
        ctx.sleep(float(sau_vuot))
        if _man_doi(vung(truoc, _REG_LIST_NV), vung(ctx.capture(), _REG_LIST_NV), nguong):
            break
        ctx.log(f"chọn nhân vật: cuộn hụt lần {i + 1}/{lan} (list không đổi)")
    else:
        ctx.log("chọn nhân vật: list không cuộn được (tk ít nhân vật?) -> chọn theo tên")
        return _chon_theo_ten(ctx, dong, ten_cu, scroll_keo, sau_vuot)

    x, y, _ = dong[-1]
    for i in range(int(lan)):
        truoc = vung(ctx.capture(), _REG_TEN_NV)
        _chon_nhan_vat(ctx, x, y)
        if _man_doi(truoc, vung(ctx.capture(), _REG_TEN_NV), nguong):
            break
        ctx.log(f"chọn nhân vật: bấm dòng cuối hụt lần {i + 1}/{lan} (ô tên không đổi)")
    else:
        ctx.log("chọn nhân vật: bấm dòng cuối không đổi được nhân vật -> chọn theo tên")
        return _chon_theo_ten(ctx, dong, ten_cu, scroll_keo, sau_vuot)
    # dòng cuối = nhân vật lâu chưa chơi nhất mà ĐÃ làm hôm nay -> tk đã làm hết (tk < 6 nhân vật, hoặc chạy bổ sung
    #  tk làm thiếu: làm nốt nhân vật còn thiếu rồi dừng). Muốn làm lại cả tk trong ngày phải xoá tên trong kho.
    from nthbot.xu import _chuan, cung
    ten = ctx.variables.get("_ten_nv", "")
    da_lam = _da_lam_hom_nay(ctx, ten_cu)
    if ten and any(cung(_chuan(ten), d) for d in da_lam):
        # nhân vật làm DỞ (vào game rồi bị ngắt) đã nhảy lên trên, không còn ở đáy (20/10 doangia1608: Miêu My
        #  bỏ dở lúc 16:26 -> bot tưởng hết, chỉ 5/6) -> dò từng dòng theo tên tìm nhân vật chưa làm hôm nay
        ctx.log(f"chọn nhân vật: dòng cuối '{ten}' đã làm hôm nay -> dò các dòng trên tìm nhân vật chưa làm")
        keo_that(ctx, scroll_keo[0], scroll_keo[3], scroll_keo[2], scroll_keo[1])   # kéo ngược: về đầu list
        ctx.sleep(float(sau_vuot))
        da_cuon = False
        # dò cả dòng 1 (nhân vật vừa chơi): thường đã làm -> tự bỏ qua; nhưng chạy lại 1 nhân vật trong ngày thì nó
        #  nằm ở dòng 1 (21/10 TháiHậu: bỏ dòng 1 -> tưởng tk đã làm hết)
        for x, y, n in _DONG_NV:
            if n and not da_cuon:
                keo_that(ctx, *scroll_keo)
                ctx.sleep(float(sau_vuot))
                da_cuon = True
            _chon_nhan_vat(ctx, x, y)
            t = ctx.variables.get("_ten_nv", "")
            if t and not any(cung(_chuan(t), d) for d in da_lam):
                ctx.log(f"chọn nhân vật: '{t}' chưa làm hôm nay -> làm")
                return True
        ctx.log("chọn nhân vật: mọi dòng đều đã làm hôm nay -> tk đã làm hết nhân vật")
        return False
    return True


def _chon_theo_ten(ctx, dong=_DONG_NV, ten_cu="", scroll_keo=(152, 352, 152, 80), sau_vuot=2.0):
    """(Dự phòng của _chon_tu_duoi) chọn DÒNG DƯỚI CÙNG chưa làm hôm nay theo TÊN OCR: dòng trống / nhân vật đã làm
    hôm nay (tên trong kho `nhan_vat` từ 5h sáng, hoặc `ten_cu`) -> thử dòng trên.
    Trả True nếu đã chọn được nhân vật chưa làm, False nếu không còn."""
    from nthbot.xu import _chuan, cung

    da_lam = _da_lam_hom_nay(ctx, ten_cu)
    # bấm dòng TRỐNG thì game giữ nhân vật đang chọn -> tên không đổi sau khi bấm = dòng trống (không phải dòng cuối)
    truoc = _chuan(_doc_ten_nv(ctx))
    # shortcut: dòng 1-4 dùng toạ độ list CHƯA cuộn; tk 5 nhân vật (cuộn được 1 phần) có thể chọn lệch dòng
    for x, y, n in reversed(dong):
        for _ in range(n):
            keo_that(ctx, *scroll_keo)
            ctx.sleep(float(sau_vuot))
        _chon_nhan_vat(ctx, x, y)
        ten = ctx.variables.get("_ten_nv", "")
        trong, truoc = cung(truoc, _chuan(ten)), _chuan(ten)
        if ten and not trong and not any(cung(_chuan(ten), d) for d in da_lam):
            return True
        ctx.log(f"chọn nhân vật: dòng ({x},{y}) = '{ten or '?'}' (đã làm hôm nay / trống) -> thử dòng trên")
    return False


def _chon_nhan_vat(ctx, x, y, cho=2.0):
    """Màn chọn nhân vật: bấm dòng (x,y), đợi 2s cho game chọn xong (user chốt: không kiểm tra màu)."""
    ctx.device.tap(int(x), int(y))
    ctx.sleep(float(cho))
    ctx.variables["_ten_nv"] = _doc_ten_nv(ctx)
    ctx.log(f"chọn nhân vật tại ({x},{y}): {ctx.variables['_ten_nv'] or '?'}")
    return True


def _bam_xong_pha(ctx, xy=(785, 475), lan=3, cho=6.0):
    """Bấm Xông Pha Giang Hồ; 6s sau vẫn còn ở màn chọn nhân vật (tap bị bỏ qua) thì bấm lại."""
    import time
    for i in range(int(lan)):
        ctx.device.tap(int(xy[0]), int(xy[1]))
        end = time.time() + float(cho)
        while time.time() < end:
            ctx.sleep(1)
            if not ctx.find("xong_pha_giang_ho.png", region=_REG_XONG_PHA_NV).found:
                return True
        ctx.log(f"Xông Pha chưa ăn -> bấm lại ({i + 1})")
    return False


def doi_acc(ctx, slots=None, idx_var="_acc_idx",
            hoat_dong_xy=(918, 21), cai_dat="cai_dat.png", xac_nhan="xac_nhan.png",
            dong_update="dong_update.png", doi_tk=(846, 147), vao_game=(785, 475),
            timeout=20, sau_mo=3.0, sau_xac_nhan=90.0, cho_chon=2.0, sau_vuot=2.0,
            sau_vao_game=120.0, cho_dong=1.5, dong_popup_sau_dn=True,
            scroll_keo=(152, 352, 152, 80), wrap=False, zing=False, tu_duoi=False):
    """Đổi sang TÀI KHOẢN KẾ TIẾP trong danh sách `slots` (mỗi lần gọi đổi 1 acc).

    Dùng cùng `repeat` của task: đặt steps = [ ...Thanh Nhai Thư... , doi_acc ] và
    `repeat: <số acc>`. Vì ctx.variables được giữ qua các vòng repeat nên hàm tự nhớ
    đang ở acc thứ mấy (biến `idx_var`) và đổi sang acc tiếp theo:

        vòng 1: làm TNT cho acc1 (đã đăng nhập sẵn) -> đổi sang slots[0] (acc2)
        vòng 2: làm TNT cho acc2                    -> đổi sang slots[1] (acc3)
        ...
        vòng cuối: làm TNT cho acc cuối             -> hết slots -> KHÔNG đổi nữa (dừng)
    => repeat nên = len(slots) + 1  (acc1 + mỗi slot là 1 acc kế tiếp).

    LUỒNG ĐỔI (bắt đầu ở MÀN HÌNH CHÍNH của acc hiện tại):
        hoat_dong -> cai_dat -> tap(doi_tk=852,417) -> xac_nhan
        -> tap(vị trí acc) -> tap(vao_game=793,475) -> chờ game load -> đóng popup.

    THAM SỐ (truyền trong .yaml):
      slots : danh sách vị trí TÀI KHOẢN trên màn chọn acc, theo THỨ TỰ sẽ đổi tới.
              Mỗi slot là [x, y]  hoặc  {x: .., y: .., scroll: n} (vuốt lên n lần
              trước khi chọn — dùng cho acc 5, 6 nằm dưới phải cuộn mới thấy).
              VD (toạ độ đo trên instance 960x540):
                - [139, 202]   # acc 2
                - [176, 290]   # acc 3
                - [164, 364]   # acc 4
      doi_tk     : toạ độ nút "đổi/đăng xuất tài khoản" trong Cài đặt (mặc định 852,417).
      vao_game   : toạ độ nút "vào game" sau khi chọn acc (mặc định 793,475).
      sau_vao_game : số giây chờ game của acc mới load xong (mặc định 25).
      dong_popup_sau_dn : True = sau khi vào game tự bấm đóng popup (ve_man_hinh_chinh).
      scroll_swipe : [x1,y1,x2,y2,duration] cú vuốt khi slot có 'scroll' (vuốt LÊN để
                     lộ acc bên dưới). Tinh chỉnh khi đã đo được acc 5/6.
      wrap   : True = hết danh sách thì quay lại slot đầu; False (mặc định) = dừng đổi.
      zing   : True = hết nhân vật thì đánh dấu tk Zing hiện tại XONG trong kho acc;
               vòng sau `nhan_acc` (bước đầu task) tự lấy acc chưa chạy tiếp theo.
      tu_duoi: True = luôn chọn DÒNG CUỐI (cuộn xuống). List xếp theo lần chơi gần nhất -> nhân vật vừa chơi
               nhảy lên đầu, dòng cuối luôn là nhân vật lâu chưa chơi nhất. Dòng cuối trống (tk < 6 nhân vật)
               hoặc là nhân vật đã làm hôm nay -> thử dần các dòng trên (slots đảo ngược); hết -> tk XONG.
    """
    from nthbot.engine import StepError
    if not slots:
        ctx.log("doi_acc: chưa khai báo 'slots' (danh sách vị trí acc) -> bỏ qua.")
        return False

    idx = int(ctx.variables.get(idx_var, 0) or 0)
    if zing and ctx.variables.get("_zing_user"):
        from nthbot import accounts
        from nthbot.bot import ACC_DONE_MARK
        ten = ctx.variables.get("_ten_nv", "")
        phieu = ctx.variables.pop("_phieu", {})
        accounts.set_nv_xong(ctx.variables["_zing_user"], idx + 1, ten, phieu)   # nhớ để chạy lại thì bỏ qua
        ctx.log(f"doi_acc: đã xong nv{idx + 1}")
        if idx == 0:   # acc hẹn giờ: mai bắt đầu = giờ xong nhân vật 1 hôm nay + 10 phút (hàng treo chắc chắn đã hết hạn)
            from datetime import datetime, timedelta
            gio = (datetime.now() + timedelta(minutes=10)).strftime("%H:%M")
            if accounts.dat_gio(ctx.variables["_zing_user"], gio):
                ctx.log(f"doi_acc: giờ hẹn mai = {gio} (giờ xong nhân vật 1 + 10 phút)")
        loi = accounts.loi_phieu(phieu)       # bước hụt -> ⚠ + liệt kê, đừng im lặng ✓ (20/10 nuốt lỗi TNT 0/4, chụp ảnh)
        ctx.log(f"{ACC_DONE_MARK} Nhân vật {idx + 1}" + (f" ({ten})" if ten else "")
                + (" xong nhưng ⚠ " + ", ".join(loi) if loi else " đã hoàn thành ✓"))
    def xong_tk():
        # hết nhân vật của tk Zing này -> đánh dấu XONG; vòng sau nhan_acc tự lấy acc mới
        from nthbot import accounts
        user = ctx.variables.pop("_zing_user", None)
        if user:
            accounts.set_status(user, "done")
            ctx.log(f"doi_acc: tk Zing {accounts.ten_hien(user)} XONG ✓")
        ctx.variables[idx_var] = 0
        # còn acc chạy được NGAY -> khởi động lại LDPlayer: chạy lâu LDPlayer phình bộ nhớ (20/10: 29GB cho máy ảo 6GB).
        # acc kế tiếp hẹn giờ sau -> nhan_acc tự tắt LDPlayer và bật lại sát giờ hẹn
        from datetime import datetime
        if any(accounts._san_sang(a, datetime.now()) for a in accounts.load()):
            try:                             # tk đã ✓: boot lỗi mà raise thì engine làm lại doi_acc với idx 0 trên
                khoi_dong_lai_ldplayer(ctx)  #  máy chưa lên -> chỉ ghi log, vòng sau khoi_dong_game chờ game
            except RuntimeError as e:        # StepError / AdbError; Stopped (nút Stop) vẫn đi qua
                ctx.log(f"doi_acc: khởi động lại LDPlayer lỗi ({e}) -> để vòng sau tự chờ")
        return True

    if idx >= len(slots):
        if zing:
            return xong_tk()
        if not wrap:
            ctx.log("doi_acc: đã hết danh sách acc -> không đổi nữa.")
            return False
        idx = 0

    slot = slots[idx]
    if isinstance(slot, dict):
        sx, sy = int(slot["x"]), int(slot["y"])
        scroll_n = int(slot.get("scroll", 0))
    else:
        sx, sy = int(slot[0]), int(slot[1])
        scroll_n = 0

    ctx.log(f"doi_acc: đổi sang acc kế tiếp (slot #{idx + 1} -> {sx},{sy})")

    # 1+2) màn chính -> mở màn CHỌN TÀI KHOẢN (hoat_dong -> cai_dat -> doi_tk -> xác nhận)
    if not _mo_man_chon_acc(ctx, hoat_dong_xy, cai_dat, xac_nhan, doi_tk,
                            timeout, sau_mo, sau_xac_nhan, dong_update):
        return False

    # 3) (nếu cần) cuộn để lộ acc nằm dưới (kéo thật bằng sendevent), rồi chọn acc
    # cuộn có lúc hụt -> bấm trượt, game giữ nhân vật cũ (đã vào lại nv4 thay vì nv5, 19/10)
    #  -> tên ở ô góc phải dưới vẫn là nhân vật vừa làm thì cuộn + chọn lại (list đã ở đáy thì cuộn thêm không sao)
    ten_cu = ctx.variables.get("_ten_nv", "").replace(" ", "")
    if tu_duoi:
        # dòng 1 là nhân vật vừa làm (vừa chơi -> lên đầu) -> chỉ xét dòng 2..6, từ dưới lên
        dong = [(int(s["x"]), int(s["y"]), int(s.get("scroll", 0))) if isinstance(s, dict)
                else (int(s[0]), int(s[1]), 0) for s in slots]
        if not _chon_tu_duoi(ctx, dong, ten_cu, scroll_keo, sau_vuot):
            if zing:
                ctx.log("doi_acc: không còn nhân vật chưa làm hôm nay"
                        + (f" ⚠ CHỈ LÀM ĐƯỢC {idx + 1}/{len(slots) + 1} lượt — kiểm tra tk này" if idx + 1 < len(slots) + 1 else ""))
                return xong_tk()
            return False
    else:
        for lan in range(3):
            for _ in range(scroll_n):
                keo_that(ctx, *scroll_keo)
                ctx.sleep(float(sau_vuot))
            _chon_nhan_vat(ctx, sx, sy)
            ten = ctx.variables.get("_ten_nv", "").replace(" ", "")
            if ten and ten != ten_cu:
                break
            if lan < 2:
                ctx.log(f"doi_acc: vẫn là nhân vật cũ / không đọc được tên -> chọn lại (lần {lan + 2})")
        else:
            # chọn 3 lần vẫn đúng nhân vật vừa làm = dòng này TRỐNG (tk ít hơn 6 nhân vật, vd chỉ 1 nhân vật)
            #  -> không vào lại nhân vật cũ làm lần nữa, coi như hết nhân vật (bot đang ở màn chọn nhân vật)
            if zing and ten and ten == ten_cu:
                ctx.log(f"doi_acc: slot #{idx + 1} không có nhân vật -> tk chỉ có {idx} nhân vật")
                return xong_tk()

    # 4) vào game + chờ TỚI KHI về màn chính (icon Thanh Nhai Thư), tối đa sau_vao_game
    _bam_xong_pha(ctx, vao_game)
    ctx.log("doi_acc: vào game, chờ load...")
    if not _cho_qua_popup(ctx, "thanh_nhai_thu.png", timeout=sau_vao_game,
                          region=(860, 90, 100, 100)).found:
        ctx.log("doi_acc: chưa thấy màn chính sau khi vào game (đi tiếp)")
    ctx.sleep(2)                             # popup sau khi vào game hay hiện trễ
    if dong_popup_sau_dn:
        ve_man_hinh_chinh(ctx, cho=float(cho_dong))

    ctx.variables[idx_var] = idx + 1
    return True


def khoi_dong_lai_ldplayer(ctx, timeout=240, cho_den=None):
    """Tắt rồi bật lại instance LDPlayer, chờ Android boot xong. Game sẽ được khoi_dong_game mở lại.
    cho_den (datetime): tắt xong để TẮT tới lúc đó mới bật (chờ giờ hẹn acc khỏi tốn RAM).
    Thiết bị không quản lý qua ldconsole (ld_index None) -> bỏ qua."""
    import time
    from datetime import datetime
    from nthbot.engine import StepError
    from nthbot.ldplayer import quit_instance, start_instance
    d = ctx.device
    if d.ld_index is None:
        return False
    ctx.log("Khởi động lại LDPlayer (giải phóng bộ nhớ)..." if cho_den is None
            else f"Tắt LDPlayer, {cho_den:%H:%M} mới bật lại")
    quit_instance(d.ldconsole_path, d.ld_index)
    ctx.sleep(8)
    while cho_den is not None and datetime.now() < cho_den:
        ctx.sleep(min(30.0, max(1.0, (cho_den - datetime.now()).total_seconds())))
        ctx.tien_trien = time.time() + 120           # watchdog: đang chờ giờ hẹn, LDPlayer tắt -> đừng đóng banner
    ctx.tien_trien = time.time() + timeout + 30      # watchdog: đang chờ boot, không phải kẹt
    start_instance(d.ldconsole_path, d.ld_index)
    end = time.time() + float(timeout)
    while time.time() < end:
        ctx.sleep(3)
        try:
            if d.connect() and d.getprop("sys.boot_completed") == "1":
                ctx.sleep(5)                 # boot xong vẫn cần vài giây mới mở app được
                ctx.log("LDPlayer đã bật lại")
                return True
        except Exception:  # noqa: BLE001 - đang boot, adb chưa sẵn sàng
            pass
    raise StepError(f"LDPlayer không boot xong sau {timeout}s")


def khoi_dong_game(ctx, timeout=300):
    """BƯỚC ĐẦU TASK: game chưa mở thì mở, rồi chờ qua màn loading tới 1 màn đã biết
    (form VNG / màn server / màn chọn nhân vật / màn chính), vừa chờ vừa đóng popup.
    Game đang ở màn chính sẵn -> xong ngay."""
    import time
    from nthbot.engine import StepError
    if ctx.package and ctx.package not in ctx.device.current_app():
        ctx.log(f"Mở game {ctx.package}...")
        ctx.device.launch_app(ctx.package)
        ctx.sleep(10)
    dich = (("chon_zing_id.png", None), ("form_zing.png", None),
            ("vao_server.png", (300, 380, 360, 90)), ("xong_pha_giang_ho.png", (600, 430, 360, 110)),
            ("thanh_nhai_thu.png", (860, 90, 100, 100)))         # icon Thanh Nhai Thư = màn chính
    # xac_nhan: popup 'Xác nhận đăng nhập lại sao?' còn treo khi tool bị tắt giữa lúc đổi tk (đã gặp 19/10)
    popups = ("tick_dieu_khoan.png", "dong_y_dieu_khoan.png", "xac_nhan.png")
    end = time.time() + float(timeout)
    while time.time() < end:
        scr = ctx.capture()
        for img, reg in dich:
            if ctx.find(img, region=reg, screen=scr).found:
                ctx.log(f"khoi_dong_game: game sẵn sàng ({img})")
                return True
        x = _tim_nut_x(ctx, scr)
        # đang ở trang con (Start lúc game mở dở) -> nút back xanh/vàng để thoát về màn chính
        p = x if x.found else next((m for img in popups + ("nut_dong.png", "nut_dong_vang.png")
                                    if (m := ctx.find(img, screen=scr)).found), None)
        if p is not None and p.found:
            ctx.device.tap(p.x, p.y)
        ctx.sleep(3)
    raise StepError(f"khoi_dong_game: sau {timeout}s game vẫn chưa tới màn đăng nhập / màn chính")


def nhan_acc(ctx, **login_kw):
    """BƯỚC ĐẦU TASK (chạy nhiều tk Zing): nếu máy chưa có acc -> lấy acc CHƯA CHẠY trong kho
    (bỏ qua acc xong / đang chạy ở máy khác), đăng nhập vào nhân vật 1. Hết acc -> kết thúc task.

    Đang chạy dở 1 acc (còn nhân vật) -> không làm gì.
    Đăng nhập lỗi -> đánh dấu acc 'error' rồi dừng máy này (tránh đốt hết kho nếu ảnh mẫu sai).

    Trong task .yaml:  - python: { func: nhan_acc }   (+ tham số của doi_tk_zing nếu cần)
    """
    from datetime import datetime, timedelta
    from nthbot import accounts
    from nthbot.engine import TaskDone

    if ctx.variables.get("_zing_user"):
        return True
    # đăng nhập lỗi -> engine đóng banner / Claude cứu rồi làm lại bước: thử lại ĐÚNG tk đó (đã bị đánh ✗), đừng lấy tk khác
    u = ctx.variables.pop("_dn_lai", None)
    if u and (acc := accounts.get(u)) and acc["status"] == "error":
        accounts.set_status(u, accounts.RUNNING + ctx.device.name)
    else:
        acc = accounts.claim(ctx.device.name)
    # còn acc hẹn giờ chưa tới giờ -> chờ (Start lúc 7h, acc hẹn 10h thì 10h mới chạy), không kết thúc task
    while acc is None and (hen := accounts.hen_som_nhat()) is not None:
        ctx.log(f"nhan_acc: chưa tới giờ hẹn -> chờ tới {hen:%H:%M}")
        if hen - datetime.now() > timedelta(minutes=10):  # chờ lâu -> tắt LDPlayer, 3 phút trước giờ hẹn mới bật
            khoi_dong_lai_ldplayer(ctx, cho_den=hen - timedelta(minutes=3))
        while datetime.now() < hen:
            ctx.sleep(min(30.0, max(1.0, (hen - datetime.now()).total_seconds())))
        khoi_dong_game(ctx)                      # chờ lâu: game có thể đã hiện màn chờ / văng
        acc = accounts.claim(ctx.device.name)
    if acc is None:
        raise TaskDone("kho acc không còn acc nào chưa chạy")
    from nthbot.bot import ACC_DONE_MARK
    ctx.log(f"nhan_acc: nhận tk Zing {accounts.ten_hien(acc['user'])}")
    ctx.log(f"{ACC_DONE_MARK}⟦MOI⟧ Tài khoản {accounts.ten_hien(acc['user'])}")
    try:
        kq = doi_tk_zing(ctx, acc, **login_kw)
    except Exception:
        accounts.set_status(acc["user"], "error")
        ctx.variables["_dn_lai"] = acc["user"]
        raise
    if kq == "het":                          # vd Reset tk đã làm đủ trong ngày -> ✓ luôn, lấy tk khác
        accounts.set_status(acc["user"], "done")
        ctx.log(f"nhan_acc: tk {accounts.ten_hien(acc['user'])} đã làm hết nhân vật hôm nay -> ✓, lấy tk khác")
        return nhan_acc(ctx, **login_kw)
    ctx.variables["_zing_user"] = acc["user"]
    # làm dở: đã xong k nhân vật -> nhân vật dòng 1 (chơi gần nhất) là nv k+1 đang dở, lần đổi kế tiếp
    # chọn slots[k]. (Lỡ dừng đúng lúc đang đổi nhân vật thì chỉ làm lại 1 nhân vật đã xong, không sót.)
    k = int(acc.get("nv_xong", 0) or 0)
    ctx.variables["_acc_idx"] = k
    ctx.variables["_phieu"] = {}             # phiếu kết quả nhân vật mới (tk trước bỏ dở thì đừng dính sang)
    ctx.log(f"nhan_acc: bắt đầu nv{k + 1}" + (f" (đã xong nv1..nv{k}, bỏ qua)" if k else ""))
    return True


def _go_chu(ctx, field, value):
    """Tap ô nhập, xoá sạch nội dung cũ rồi gõ `value` (an toàn với ký tự đặc biệt của mật khẩu)."""
    ctx.device.tap(int(field[0]), int(field[1]))
    ctx.sleep(1.0)
    ctx.device.shell("input keyevent KEYCODE_MOVE_END " + " ".join(["KEYCODE_DEL"] * 40))
    # shortcut: `input text` không gõ được ký tự Unicode/tiếng Việt, đủ cho tk/mk Zing (ASCII).
    safe = str(value).replace(" ", "%s").replace("'", "'\\''")
    ctx.device.shell(f"input text '{safe}'")
    ctx.sleep(1.0)


def _cho_qua_popup(ctx, target, popups=(), timeout=60.0, region=None, dong_x=True):
    """Chờ tới khi thấy `target` (trong `region`); trong lúc chờ gặp popup nào trong `popups`
    (điều khoản...) hoặc banner có nút X (dong_x) thì bấm đóng. Trả Match."""
    import time
    t0 = time.time()
    end, da_hoi = t0 + float(timeout), False
    while True:
        scr = ctx.capture()
        m = ctx.find(target, region=region, screen=scr)
        if m.found or time.time() >= end:
            return m
        pm = _tim_nut_x(ctx, scr) if dong_x else None
        if dong_x and not pm.found and not da_hoi and time.time() - t0 > 30:
            da_hoi = True                    # chờ lâu, không mẫu X nào khớp -> banner lạ? hỏi Claude 1 lần
            xy = _hoi_claude_nut_x(ctx, scr)
            if xy:
                ctx.device.tap(*xy)
                ctx.sleep(2)
                continue
        if pm is None or not pm.found:
            pm = next((x for p in popups if (x := ctx.find(p, screen=scr)).found), None)
        if pm is not None and pm.found:
            ctx.device.tap(pm.x, pm.y)
            ctx.log(f"Đóng popup/banner tại ({pm.x},{pm.y})")
            ctx.sleep(2)
        else:
            ctx.sleep(1)


def _dang_nhap_email(ctx, acc, timeout=60, o_email=(672, 128), nut_tiep=(672, 194),
                     o_mk=(650, 164), nut_dn=(672, 231)):
    """Form VNG -> 'Phương thức khác' -> 'Email' -> trang web id.vnggames.app (mở trong Chrome):
    gõ email -> Tiếp tục -> gõ mật khẩu -> Đăng nhập -> game tự quay lại (đo 19/10, 960x540).
    Chrome lần đầu hỏi tài khoản Google -> 'Use without an account'. Web hỏi 'Chọn tài khoản đăng nhập' ->
    'Đăng nhập bằng tài khoản khác'. Trang mật khẩu hiện luôn (web nhớ
    email lần trước) -> 'Nhập lại email' để chắc chắn gõ đúng email của acc này."""
    import time
    from nthbot import accounts
    from nthbot.engine import StepError
    _find_tap(ctx, "phuong_thuc_khac.png", 10, 2, required=True)
    _find_tap(ctx, "nut_email.png", 10, 3, required=True)
    end, da_go_email = time.time() + float(timeout), False
    while time.time() < end:
        scr = ctx.capture()
        # Chrome lần đầu hỏi tk Google / web hỏi 'Chọn tài khoản đăng nhập' (list tk đã nhớ, chỉ ghi 'User 0128..',
        #  không biết đúng acc không) -> luôn 'Đăng nhập bằng tài khoản khác' rồi gõ email
        if (m := next((q for img in ("chrome_khong_tk.png", "web_tk_khac.png")
                       if (q := ctx.find(img, screen=scr)).found), None)) is not None:
            ctx.device.tap(m.x, m.y)
            ctx.sleep(3)
        elif ctx.find("web_o_email.png", screen=scr).found:
            _go_chu(ctx, o_email, acc["user"])
            ctx.device.tap(*nut_tiep)
            da_go_email = True
            ctx.sleep(4)
        elif ctx.find("web_o_mat_khau.png", screen=scr).found:
            if not da_go_email:
                _find_tap(ctx, "web_nhap_lai_email.png", 5, 3, required=True)
                continue
            _go_chu(ctx, o_mk, acc["pass"])
            ctx.device.tap(*nut_dn)
            ctx.log(f"doi_tk_zing: đã gõ email + mật khẩu ({accounts.ten_hien(acc['user'])})")
            return True
        else:
            ctx.sleep(1)
    raise StepError("doi_tk_zing: không qua được trang đăng nhập email")


def doi_tk_zing(ctx, acc, hoat_dong_xy=(918, 21), cai_dat="cai_dat.png",
                giao_dien_dn_xy=(440, 215), xac_nhan="xac_nhan.png",
                dang_xuat_zing="dang_xuat_zing.png", chon_zing="chon_zing_id.png",
                form_zing="form_zing.png", o_tai_khoan=(480, 212), o_mat_khau=(480, 260),
                nut_dn_zing="nut_dang_nhap_zing.png", vao_server="vao_server.png",
                xong_pha="xong_pha_giang_ho.png", nhan_vat_1=(139, 115),
                popup_dn=("tick_dieu_khoan.png", "dong_y_dieu_khoan.png"),
                popup_server=(),             # banner có nút X: _cho_qua_popup tự đóng
                timeout=30, sau_mo=7.0, cho_login=90.0, sau_vao_game=120.0, cho_dong=1.5, tu_duoi=False):
    """Đăng xuất tk Zing hiện tại rồi đăng nhập tk `acc` ({user, pass}). Được nhan_acc gọi.

    LUỒNG (đã đo trên game thật, 960x540). Bắt đầu ở màn chính, màn chọn nhân vật, màn server,
    hoặc form VNG đều được:
      màn chọn nhân vật: back(48,27) -> 'đăng nhập lại?' xac_nhan -> màn server
      màn chính: hoat_dong(918,21) -> cai_dat -> "Giao diện đăng nhập: Đến"(440,215) -> xac_nhan
      màn server: icon người góc phải trên (dang_xuat_zing) -> form VNG
      form VNG: ZingID -> [form "Đăng nhập bằng ZingID"] gõ tk (480,212) -> gõ mk (480,260) -> Đăng nhập
               (ô tk có thể còn tên lần trước -> _go_chu xoá sạch rồi mới gõ)
      -> [điều khoản / thông báo] -> màn server: Xông Pha Giang Hồ (giữa)
      -> [quảng cáo] -> màn nhân vật: chọn nhân vật 1 -> Xông Pha Giang Hồ (phải dưới)
      -> chờ load -> đóng popup.
    Màn server và màn nhân vật đều có chữ "Xông Pha Giang Hồ" -> phân biệt bằng vùng tìm.
    """
    from nthbot import accounts
    from nthbot.engine import StepError

    reg_server = (300, 380, 360, 90)     # nút Xông Pha Giang Hồ ở GIỮA (màn server)
    reg_nhan_vat = (600, 430, 360, 110)  # nút Xông Pha Giang Hồ ở PHẢI DƯỚI (màn nhân vật)
    ctx.log(f"doi_tk_zing: đăng xuất -> đăng nhập {accounts.ten_hien(acc['user'])}")
    ctx.variables["_ten_nv"] = ""        # tên nhân vật của tk trước (game vào thẳng màn chính thì không đọc lại)

    # 1) đang ở đâu? -> đưa về form VNG
    scr = ctx.capture()
    if ctx.find("dn_that_bai.png", screen=scr).found:   # popup 'Đăng nhập thất bại' của tk trước còn che -> OK
        ctx.device.tap(480, 304)
        ctx.sleep(2)
        scr = ctx.capture()
    if not ctx.find(chon_zing, screen=scr).found and not ctx.find(form_zing, screen=scr).found:
        if ctx.find(xong_pha, region=reg_nhan_vat, screen=scr).found:
            # màn chọn nhân vật (game tự vào lại tk cũ) -> back -> 'đăng nhập lại?' -> màn server
            ctx.device.tap(48, 27)
            ctx.sleep(4)
            _find_tap(ctx, xac_nhan, timeout, 0, required=True)
            if not _cho_qua_popup(ctx, vao_server, popup_server, cho_login, reg_server).found:
                raise StepError("doi_tk_zing: không về được màn server")
        # chờ vài giây mới kết luận màn chính: dò trượt 1 lần trên màn server -> bấm (918,21) trúng icon đăng xuất
        elif not _cho_qua_popup(ctx, vao_server, timeout=8, region=reg_server, dong_x=False).found:
            # màn chính -> Cài đặt -> Giao diện đăng nhập -> Xác nhận -> màn server
            mo_hoat_dong(ctx, hoat_dong_xy)
            _find_tap(ctx, cai_dat, timeout, sau_mo, required=True)
            ctx.device.tap(int(giao_dien_dn_xy[0]), int(giao_dien_dn_xy[1]), jitter=1)
            ctx.sleep(float(sau_mo))
            _find_tap(ctx, xac_nhan, timeout, 0, required=True)
            if not _cho_qua_popup(ctx, vao_server, popup_server, cho_login, reg_server).found:
                raise StepError("doi_tk_zing: không về được màn server")
        _find_tap(ctx, dang_xuat_zing, timeout, 5, required=True)

    # 2) form VNG -> ZingID -> gõ tk/mk -> Đăng nhập   (tk có '@' = tk email: luồng web riêng)
    import time
    if "@" in acc["user"]:
        _dang_nhap_email(ctx, acc)
    else:
        for _ in range(3):
            _find_tap(ctx, chon_zing, 5, 4, required=False)   # form ZingID có thể đã mở sẵn
            # bấm ZingID có thể TỰ ĐĂNG NHẬP tk lần trước -> vào thẳng màn server -> đăng xuất, thử lại
            end, o = time.time() + float(timeout), None
            while time.time() < end and o is None:
                scr = ctx.capture()
                if ctx.find(form_zing, screen=scr).found:
                    o = "form"
                elif ctx.find(vao_server, region=reg_server, screen=scr).found:
                    o = "server"
                elif (x := _tim_nut_x(ctx, scr)).found:   # popup Thông Báo che form (22/10) -> đóng ngay, đừng chờ hết giờ
                    ctx.log(f"doi_tk_zing: đóng banner tại ({x.x},{x.y})")
                    ctx.device.tap(x.x, x.y)
                    ctx.sleep(2)
                    _find_tap(ctx, chon_zing, 3, 4, required=False)   # banner che lúc bấm ZingID -> bấm lại
                else:
                    ctx.sleep(2)
            if o == "form":
                break
            if o == "server":
                ctx.log("doi_tk_zing: SDK tự vào tk cũ -> đăng xuất")
                _find_tap(ctx, dang_xuat_zing, timeout, 5, required=True)
        else:
            raise StepError("doi_tk_zing: không thấy form đăng nhập ZingID")
        _go_chu(ctx, o_tai_khoan, acc["user"])
        _go_chu(ctx, o_mat_khau, acc["pass"])
        _find_tap(ctx, nut_dn_zing, timeout, 5, required=True)

    # 3+4) xử lý theo màn hình tới khi vào được màn chọn nhân vật:
    #   điều khoản -> tick/đồng ý; banner (hay bật ngay sau khi bấm Xông Pha ở màn server) -> đóng X;
    #   màn server (kể cả bị trả về đó sau khi đóng banner) -> bấm Xông Pha.
    import time
    end, m = time.time() + float(cho_login) * 2, None
    while time.time() < end:
        scr = ctx.capture()
        m = ctx.find(xong_pha, region=reg_nhan_vat, screen=scr)
        if m.found:
            break
        # VNG: 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin đăng nhập [7020-13]' (sai tk/mk) -> dừng ngay,
        #  không bấm Xông Pha phía sau popup 3 phút
        if (f := ctx.find("dn_that_bai.png", screen=scr)).found:
            ctx.device.tap(480, 304)          # OK
            raise StepError(f"doi_tk_zing: VNG báo ĐĂNG NHẬP THẤT BẠI [7020-13] cho {accounts.ten_hien(acc['user'])} "
                            "-> kiểm tra lại tài khoản / mật khẩu trong kho")
        # game có lúc bỏ qua màn nhân vật, vào thẳng màn chính -> không chờ màn nhân vật nữa
        if ctx.find("thanh_nhai_thu.png", region=(860, 90, 100, 100), screen=scr).found:
            ctx.log("doi_tk_zing: đã vào thẳng màn chính")
            ve_man_hinh_chinh(ctx, cho=float(cho_dong))
            return True
        sv = ctx.find(vao_server, region=reg_server, screen=scr)
        x = _tim_nut_x(ctx, scr)
        p = next((q for img in popup_dn if (q := ctx.find(img, screen=scr)).found), None)
        if x.found:
            ctx.device.tap(x.x, x.y)
            ctx.log(f"doi_tk_zing: đóng banner tại ({x.x},{x.y})")
            ctx.sleep(2)
        elif p is not None:
            ctx.device.tap(p.x, p.y)
            ctx.sleep(2)
        elif sv.found:
            ctx.device.tap(sv.x, sv.y)
            ctx.log("doi_tk_zing: màn server -> Xông Pha")
            ctx.sleep(5)
        else:
            ctx.sleep(1)
    if m is None or not m.found:
        raise StepError(f"doi_tk_zing: đăng nhập {accounts.ten_hien(acc['user'])} không vào được màn chọn nhân vật "
                        "(sai mật khẩu / captcha / banner lạ?)")
    ctx.sleep(4)   # list còn chạy hiệu ứng ~3.5s: bấm sớm hơn thì game tự quay về chọn dòng 1 (đo 18/10)
    # tu_duoi: nhân vật đầu tiên cũng cuộn xuống chọn dòng cuối chưa làm hôm nay (như doi_acc); không thì dòng 1
    ctx.variables["_dang_nhap"] = acc["user"]
    if tu_duoi:
        if not _chon_tu_duoi(ctx):
            return "het"                     # dòng cuối đã làm hôm nay -> tk đã làm hết, đừng vào làm lại dòng 1
    else:
        _chon_nhan_vat(ctx, *nhan_vat_1)    # dòng 1
    _bam_xong_pha(ctx, (m.x, m.y))
    ctx.log("doi_tk_zing: vào game, chờ load...")
    if not _cho_qua_popup(ctx, "thanh_nhai_thu.png", timeout=sau_vao_game,
                          region=(860, 90, 100, 100)).found:
        ctx.log("doi_tk_zing: chưa thấy màn chính sau khi vào game (đi tiếp)")
    ctx.sleep(2)                             # popup sau khi vào game hay hiện trễ
    _find_tap(ctx, "dong_update.png", 0, 3, required=False)   # popup "Cập nhật hoạt động mới"
    ve_man_hinh_chinh(ctx, cho=float(cho_dong))
    return True


# ---- CHẾ TƠ + TREO BÁN TƠ (đo trên game thật 960x540) ------------------------------
# Trang Nghề nghiệp > Thiết Kế: dòng 3 = Tơ Phiêu Vân-2 dùng Diệu Tinh Thạch (đá vàng).
_DA_XY = (525, 322)            # ô nguyên liệu đá vàng trên trang chế
_NUMPAD = {"1": (741, 141), "2": (796, 141), "3": (851, 141), "4": (741, 197), "5": (796, 197),
           "6": (851, 197), "7": (741, 252), "8": (796, 252), "9": (851, 252), "0": (796, 307)}
_NUMPAD_XOA, _NUMPAD_OK = (741, 307), (851, 307)


def _doc_so_ocr(ctx, region, whitelist="0123456789"):
    """OCR 1 vùng, thử cả 2 chiều sáng/tối, trả text đầu tiên có chữ số ('' nếu không đọc được).
    Phóng x3 không ra thì thử x5: số 1 chữ số ('Lợi ích: 0') x3 chỉ đọc được 1/4 ảnh, x5 đọc 4/4 (đo 20/10)."""
    from nthbot.vision import ocr_number
    scr = ctx.capture()
    for scale in (3, 5):
        for inv in (False, True):
            t = ocr_number(scr, region=tuple(region), whitelist=whitelist, invert=inv, scale=scale)
            if any(c.isdigit() for c in t):
                return t
    return ""


def _so_da_dang_co(text):
    """'12/1' -> 12. OCR hay bỏ sót số 0 đỏ ('/1' -> 0) hoặc dấu '/' ('1' -> 1)."""
    import re
    head = text.split("/")[0] if "/" in text else text
    m = re.search(r"\d+", head)
    return int(m.group()) if m else 0


def _doc_hoat_luc(text):
    """'101/1500' -> 101. Bắt buộc có '/': chỉ đọc mỗi chữ số thì dấu '/' hay bị OCR nhận thành
    '2' ('101 /' -> '1021') -> mua đá thừa. Không chắc -> None."""
    if "/" not in text:
        return None
    hl, _, cap = text.partition("/")
    cap = cap.strip("/")
    if not hl.isdigit() or not cap[:4].isdigit():
        return None
    hl, cap = int(hl), int(cap[:4])
    return hl if hl <= cap * 2 else None     # hoạt lực có thể vượt tối đa nhờ thưởng (vd 1565/1500)


def _mo_khu_giao_dich(ctx, sau=4.0):
    """Từ trang chế: bấm đá vàng -> mũi tên 'Cách nhận' -> Khu Giao Dịch (đường vòng vào chợ,
    KHÔNG bấm icon Kỳ Trân trên màn chính vì icon đó hay đổi vị trí)."""
    for _ in range(3):                       # tap đầu đôi khi bị bỏ qua (còn animation) -> thử lại
        ctx.device.tap(*_DA_XY)
        m = _cho_qua_popup(ctx, "cach_nhan.png", timeout=4)
        if m.found:
            break
    else:
        from nthbot.engine import StepError
        raise StepError("không thấy dòng 'Cách nhận' của đá vàng")
    ctx.device.tap(m.x + 97, m.y)            # mũi tên ở cuối dòng 'Cách nhận'
    ctx.sleep(2)
    _find_tap(ctx, "khu_giao_dich.png", 10, sau, required=True)


def _mua_da(ctx, so_luong, gia_toi_da=83, sau=3.0):
    """Mua `so_luong` Diệu Tinh Thạch ở lô rẻ nhất (game chọn sẵn), rồi quay về trang chế.
    Lô rẻ nhất giá > `gia_toi_da` (hoặc OCR không đọc được giá) -> KHÔNG mua. Trả True nếu đã mua."""
    import re
    from nthbot.engine import StepError
    _mo_khu_giao_dich(ctx)
    if not _cho_qua_popup(ctx, "nut_mua.png", timeout=15).found:
        raise StepError("không vào được màn mua đá vàng")
    m = re.search(r"\d+", _doc_so_ocr(ctx, (277, 120, 40, 22)))   # giá lô rẻ nhất (ô đầu tiên)
    gia = int(m.group()) if m else None
    if gia is None or gia > int(gia_toi_da):
        ctx.log(f"mua đá: giá lô rẻ nhất {gia} > {gia_toi_da} (hoặc không đọc được) -> KHÔNG mua")
        ctx.device.tap(45, 30)               # quay lại trang chế
        ctx.sleep(sau)
        return False
    ctx.log(f"mua đá: giá {gia} <= {gia_toi_da} -> mua {so_luong}")
    ctx.device.tap(770, 368)                 # ô số lượng -> hiện bàn phím số của game
    ctx.sleep(1.5)
    for _ in range(6):
        ctx.device.tap(*_NUMPAD_XOA)
        ctx.sleep(0.3)
    for ch in str(int(so_luong)):
        ctx.device.tap(*_NUMPAD[ch])
        ctx.sleep(0.3)
    ctx.device.tap(*_NUMPAD_OK)
    ctx.sleep(1.5)
    _find_tap(ctx, "nut_mua.png", 5, sau, required=True)
    if _cho_qua_popup(ctx, "chuc_mung_nhan.png", timeout=10).found:
        ctx.device.tap(480, 450)             # "nhấn vào chỗ trống để đóng"
        ctx.sleep(2)
    else:
        ctx.log("mua đá: không thấy 'Chúc Mừng Nhận' (hết tiền / lô hết hàng?)")
    ctx.device.tap(45, 30)                   # quay lại trang chế
    ctx.sleep(sau)
    return True


def _mo_trang_che(ctx, hoat_dong_xy=(920, 31), thiet_ke_xy=(663, 488), cong_thuc_xy=(245, 212)):
    """Màn chính -> Hoạt động -> Nghề nghiệp -> Thiết Kế -> Tơ Phiêu Vân-2 (dòng 3, dùng đá vàng)."""
    from nthbot.engine import StepError
    # bước lỗi được làm lại khi đang ở trang Nghề Nghiệp: (920,31) ở đó là số hoạt lực -> bật tooltip, không mở
    #  được bảng Hoạt động (20/10 bỏ cả tk doangia1608) -> về màn chính trước
    ve_man_hinh_chinh(ctx)
    mo_hoat_dong(ctx, hoat_dong_xy)
    _find_tap(ctx, "nghe_nghiep.png", 10, 0, required=True)
    # trang Nghề nghiệp load chậm (nhất là lần đầu sau khi đổi nhân vật) -> chờ thấy icon Thiết Kế
    if not _cho_qua_popup(ctx, "thiet_ke_icon.png", timeout=20, region=(620, 450, 90, 80)).found:
        raise StepError("che_to: không thấy icon nghề Thiết Kế")
    ctx.sleep(1)
    ctx.device.tap(*thiet_ke_xy)
    ctx.sleep(3)
    ctx.device.tap(*cong_thuc_xy)
    if not _cho_qua_popup(ctx, "da_vang.png", timeout=8, region=(480, 280, 90, 90), dong_x=False).found:
        raise StepError("che_to: dòng 3 không phải Tơ Phiêu Vân dùng đá vàng (kiểm tra cong_thuc_xy)")


def quet_xu(ctx, sau=3.0):
    """CHỈ QUÉT XU (không chế/treo): trang chế -> Khu Giao Dịch -> Vật Phẩm Bán -> _ghi_xu -> về màn chính.

    Trong task .yaml:  - python: { func: quet_xu }
    """
    _mo_trang_che(ctx)
    _mo_khu_giao_dich(ctx)
    _cho_qua_popup(ctx, "nut_mua.png", timeout=15)   # đợi trang Giao Dịch load
    ctx.device.tap(55, 104)                  # 'Gian Hàng Chợ' (đang mở dropdown) -> thu lại
    _find_tap(ctx, "vat_pham_ban.png", 10, sau, required=True)
    _ghi_xu(ctx)
    _find_tap(ctx, "thoat_giao_dich.png", 10, sau, required=False)
    ve_man_hinh_chinh(ctx)
    return True


def che_to(ctx, hoat_dong_xy=(920, 31), thiet_ke_xy=(663, 488), cong_thuc_xy=(245, 212),
           hoat_luc_reg=(843, 18, 80, 22), so_da_reg=(500, 348, 50, 18), hl_moi_lan=5,
           max_vong=3, toi_da=None, gia_da_toi_da=83, sau=3.0):
    """CHẾ TƠ PHIÊU VÂN: Hoạt động -> Nghề nghiệp -> Thiết Kế -> Tơ Phiêu Vân-2 (dòng 3)
    -> mua đá vàng VỪA ĐỦ theo hoạt lực hiện tại (OCR) -> chế tối đa (^) -> Chế Tạo.

    Lặp tối đa `max_vong` lần (đọc lại hoạt lực): OCR đọc sai số đá / lô hết hàng thì vòng sau
    tự mua bù. Kết thúc vẫn ĐỨNG Ở TRANG CHẾ (treo_to đi tiếp từ đây).
    toi_da: giới hạn tổng số lần chế (None = theo hoạt lực).
    gia_da_toi_da: chỉ mua đá khi giá lô rẻ nhất <= mức này (mặc định 83); đắt hơn thì chỉ chế
                   bằng đá đang có.

    Trong task .yaml:  - python: { func: che_to }
    """
    from nthbot.engine import StepError
    _mo_trang_che(ctx, hoat_dong_xy, thiet_ke_xy, cong_thuc_xy)   # treo_to đi tiếp từ trang chế -> luôn mở
    if ctx.variables.get("_phieu", {}).get("nghề nghiệp") == "failed":
        ctx.log("che_to: lần trước bấm Chế Tạo không ăn (túi đầy?) -> bỏ qua, không mua đá")
        return True

    da_che, hl_truoc = 0, None
    for vong in range(int(max_vong)):
        hl = None
        for _ in range(4):                   # OCR đôi lúc trượt 1 lần dù số rõ (20/10 '311/1500') -> đọc lại
            hl = _doc_hoat_luc(_doc_so_ocr(ctx, hoat_luc_reg, "0123456789/"))
            if hl is not None:
                break
            ctx.sleep(1.5)
        if hl is None:
            raise StepError("che_to: OCR không đọc chắc được hoạt lực -> không mua đá")
        if hl_truoc is not None and hl >= hl_truoc:
            # bấm Chế Tạo mà hoạt lực không giảm = không chế được. 20/10 tk test3: "Túi không đủ chỗ trống, không thể
            #  hoàn thành công thức này" -> trước đây bấm 3 lần + chế tơ lần 2 còn mua thêm 60 đá vô ích
            ctx.log(f"che_to: bấm Chế Tạo mà hoạt lực vẫn {hl} -> không chế được (túi đầy?), dừng")
            ctx.ghi_phieu("nghề nghiệp", "failed", loi=True)
            da_che = 0
            break
        lan = hl // int(hl_moi_lan)
        if toi_da is not None:
            lan = min(lan, int(toi_da) - da_che)
        if lan <= 0:
            break
        co = _so_da_dang_co(_doc_so_ocr(ctx, so_da_reg, "0123456789/"))
        ctx.log(f"che_to: hoạt lực {hl} -> chế được {lan} lần, đang có {co} đá")
        if lan > co:
            ctx.log(f"che_to: cần mua {lan - co} đá vàng")
            if not _mua_da(ctx, lan - co, gia_da_toi_da):
                if co <= 0:
                    break                    # đá đắt, không có đá -> bỏ qua chế
                lan = co
        if toi_da is None:
            ctx.device.tap(617, 422)         # ^ = tối đa (game lấy min(số đá, hoạt lực))
        else:
            for _ in range(lan - 1):
                ctx.device.tap(572, 422)     # + từng lần (chỉ dùng khi giới hạn toi_da, số nhỏ)
                ctx.sleep(0.3)
        ctx.sleep(1)
        hl_truoc = hl
        _find_tap(ctx, "che_tao.png", 10, sau, required=True)
        da_che += lan
    ctx.ghi_phieu("chế tơ", ctx.variables.get("_phieu", {}).get("chế tơ", 0) + da_che)   # cộng 2 lần chế
    return True


def _tim_thuoc_ha(ctx, screen, image, region, nguong=0.85):
    """Tìm thuốc bản HẠ trong túi. Mẫu khớp cả Hạ lẫn Thượng (cùng icon) -> phân biệt bằng màu nền ô:
    góc trên-trái ô bản Thượng xanh dương (B-R ≈ 39), bản Hạ xám (≈ 8) (đo 19/10). Trả (x, y) hoặc None."""
    import cv2
    import numpy as np
    t = ctx.templates.get(image)
    x0, y0, w, h = region
    r = cv2.matchTemplate(screen[y0:y0 + h, x0:x0 + w], t, cv2.TM_CCOEFF_NORMED)
    for y, x in sorted(zip(*np.where(r >= nguong)), key=lambda p: -r[p]):   # điểm khớp nhất trước
        cx, cy = x0 + int(x) + t.shape[1] // 2, y0 + int(y) + t.shape[0] // 2
        b, _, red = screen[cy - 17:cy - 11, cx - 23:cx - 17].reshape(-1, 3).mean(0)
        if b - red < 20:
            return cx, cy
    return None


def _ghi_xu(ctx, xu_reg=(688, 8, 66, 26), loi_ich_reg=(644, 426, 80, 18)):   # vùng hẹp hơn mới đọc được số 0 lẻ
    """Trang Vật Phẩm Bán: OCR xu (góc phải trên, cạnh icon đồng xu; game viết tắt '1.049M') + tiền bán
    chưa rút ('Lợi ích') -> nthbot.xu (web GitHub Pages). Lỗi chỉ ghi log, không dừng task."""
    from nthbot import accounts
    user = ctx.variables.get("_zing_user")
    acc = accounts.get(user) if user else None
    if not acc or acc["private"]:            # acc private: không đưa BẤT CỨ gì lên web
        return
    try:
        from nthbot import xu
        so_xu, chua_rut = _doc_so_ocr(ctx, xu_reg, "0123456789.MK"), _doc_so_ocr(ctx, loi_ich_reg)
        if not so_xu and not chua_rut:       # không đúng trang (màn chờ...) -> đừng đè số cũ bằng rỗng
            ctx.log("xu: không đọc được xu (bỏ qua)")
            ctx.ghi_phieu("đọc xu", "failed", loi=True)
            return
        if not chua_rut:
            ctx.ghi_phieu("đọc tiền chưa rút", "failed", loi=True)
        xu.ghi(user, int(ctx.variables.get("_acc_idx", 0) or 0) + 1, ctx.variables.get("_ten_nv", ""),
               so_xu, chua_rut, log=ctx.log)
    except Exception as e:
        ctx.log(f"xu: không ghi được xu ({e}) - bỏ qua")


def treo_to(ctx, ban_reg=(150, 90, 270, 350), max_treo=8, so_luong=599, so_lan_giam_gia=15, sau=3.0,
            gian_cach=30, rut_vi=None,
            hang=("thanh_phong_tan.png", "hoi_sinh_tan.png", "to_phieu_van.png")):
    """TREO BÁN TƠ (bắt đầu ở trang chế, sau che_to):
      đá vàng -> Cách nhận -> Khu Giao Dịch -> bấm 'Gian Hàng Chợ' (thu dropdown) -> Vật Phẩm Bán
      -> rút tiền vào ví -> gỡ tơ HẾT HẠN (kệ 8 ô, cuộn xem 2 ô khuất) -> treo tơ trong túi: gõ số lượng
      `so_luong` (599/ô; có ít hơn thì game tự lấy hết), bấm '-' giá tới mức sàn (min giá),
      Lên kệ -> lặp tới khi hết tơ / kệ đầy ('không có ô hiệu lực') -> về màn chính.
    gian_cach: số giây chờ giữa 2 lần treo (0 = treo liền; chọn trên UI 'Giãn cách treo').
    hang: thứ tự treo — Thanh Phong Tán-Hạ, Hồi Sinh Tán-Hạ (mỗi loại 1 ô, KHÔNG treo bản Thượng;
          không có thì bỏ qua) rồi mới tới tơ. Thuốc: nút ^ tối đa số lượng; tơ: gõ 599/ô. Cùng giá sàn.
    Tơ còn hạn để yên.
    """
    from nthbot.engine import StepError
    _mo_khu_giao_dich(ctx)
    _cho_qua_popup(ctx, "nut_mua.png", timeout=15)   # đợi trang Giao Dịch load
    ctx.device.tap(55, 104)                  # 'Gian Hàng Chợ' (đang mở dropdown) -> thu lại
    _find_tap(ctx, "vat_pham_ban.png", 10, sau, required=True)
    _ghi_xu(ctx)                             # trước khi rút ví: 'Lợi ích' còn nguyên
    if rut_vi is None:                      # mặc định theo tick "Rút ví" của tk trong kho acc (UI)
        from nthbot import accounts
        acc = accounts.get(ctx.variables.get("_zing_user", ""))
        rut_vi = bool(acc and acc["rut_vi"])
    if rut_vi:
        _find_tap(ctx, "rut_vao_vi.png", 3, 3, required=False)
    else:
        ctx.log("treo_to: không rút tiền vào ví (tk không tick 'Rút ví')")

    # Kệ 8 ô, chỉ thấy 6 -> gỡ ở phần đang thấy, hết thì cuộn xuống xem 2 ô khuất (kéo thật).
    # Gỡ liên tục ~1s/món (mọi món có nhãn 'Hết hạn giao dịch', không chỉ tơ); giãn cách chỉ áp cho lúc treo.
    import numpy as np
    kx, ky, kw, kh = ke = (520, 90, 410, 300)
    go, cuon = 0, False
    for _ in range(10):
        scr = ctx.capture()
        m = ctx.find("het_han.png", region=ke, screen=scr)
        if m.found:
            truoc = scr[ky:ky + kh, kx:kx + kw].astype(np.int16)
            ctx.device.tap(m.x + 90, m.y)    # nút Gỡ cùng hàng, bên phải nhãn 'Hết hạn giao dịch'
            go += 1
            ctx.sleep(1)
            for _ in range(6):               # kệ chưa cập nhật -> chờ thêm, kẻo lần sau bấm Gỡ nhầm ô còn hạn
                if np.abs(ctx.capture()[ky:ky + kh, kx:kx + kw] - truoc).mean() > 2:
                    break
                ctx.sleep(0.5)
        elif not cuon:
            keo_that(ctx, 720, 330, 720, 130)
            cuon = True
            ctx.sleep(1.5)
        else:
            break
    ctx.log(f"treo_to: gỡ {go} món hết hạn")

    thuoc_da_treo = set()                    # thuốc chỉ treo 1 ô mỗi loại

    def tim_hang():                          # món đầu tiên theo thứ tự `hang` còn trong TÚI (kệ cũng có icon)
        scr = ctx.capture()
        for img in hang:
            if img == "to_phieu_van.png":
                m = ctx.find(img, region=ban_reg, screen=scr)
                if m.found:
                    return img, (m.x, m.y)
            elif img not in thuoc_da_treo and (xy := _tim_thuoc_ha(ctx, scr, img, ban_reg)):
                return img, xy
        return None

    treo = 0
    for _ in range(int(max_treo)):
        th = tim_hang()
        if th is None:                       # có thể túi bị che (màn chờ/popup) chứ chưa hết hàng -> thử lại 1 lần
            m = ctx.find("man_cho.png")
            if m.found:
                ctx.device.tap(m.x, m.y)
                ctx.sleep(2)
            th = tim_hang()
        if th is None:
            ctx.log(f"treo_to: hết tơ trong túi (đã treo {treo})")
            if treo < int(max_treo):         # web hiện 'treo x/8 ô (hết tơ)'
                ctx.ghi_phieu("hết tơ", True, loi=True)   # chụp túi: TrânCẩm 22/10 bị báo hết dù còn tơ
            break
        img, xy = th
        ctx.device.tap(*xy)
        ctx.sleep(2)
        if img != "to_phieu_van.png":
            ctx.device.tap(914, 261)         # thuốc: nút ^ = tối đa số lượng (nhanh hơn gõ số)
            ctx.sleep(1)
        else:
            ctx.device.tap(770, 261)         # ô số lượng -> bàn phím số (thấp hơn bên mua 174px)
            ctx.sleep(1.5)
            for _ in range(2):               # ô số lượng mặc định '1' -> xoá 2 lần là sạch
                ctx.device.tap(_NUMPAD_XOA[0], _NUMPAD_XOA[1] + 174)
                ctx.sleep(0.3)
            for ch in str(int(so_luong)):
                ctx.device.tap(_NUMPAD[ch][0], _NUMPAD[ch][1] + 174)
                ctx.sleep(0.3)
            ctx.device.tap(_NUMPAD_OK[0], _NUMPAD_OK[1] + 174)
            ctx.sleep(1.5)
        for _ in range(int(so_lan_giam_gia)):
            ctx.device.tap(685, 320)         # - đơn giá (dừng ở sàn -50% = min giá)
            ctx.sleep(0.35)
        if not _find_tap(ctx, "len_ke.png", 5, 0, required=False):
            ctx.log(f"treo_to: không thấy nút Lên kệ (đã treo {treo})")
            ctx.ghi_phieu("treo dừng sớm", treo, loi=True)
            break
        day = False
        for _ in range(4):                   # thông báo hiện thoáng qua ngay sau khi bấm -> chụp dày ~1.5s
            if ctx.find("ke_day.png", region=(300, 70, 360, 45)).found:   # 'không có ô hiệu lực'
                day = True
                break
            ctx.sleep(0.4)
        if day:
            ctx.log("treo_to: kệ đã đầy 8 ô")
            ctx.ghi_phieu("kệ đầy", True)    # web hiện 'treo x/8 ô (kệ đầy)'
            ctx.device.tap(921, 120)         # X đóng bảng bán
            ctx.sleep(1)
            break
        treo += 1
        if img != "to_phieu_van.png":
            thuoc_da_treo.add(img)
        ctx.sleep(3)                         # chờ bảng bán đóng, túi cập nhật (1.5s chưa kịp: còn thấy xấp vừa treo)
        cho = float(gian_cach or 0) - 3      # 3s trên đã tính vào giãn cách (30 -> chờ thêm 27)
        if cho > 0 and tim_hang() is not None:
            ctx.log(f"treo_to: chờ {cho:.0f}s rồi treo ô tiếp theo")
            ctx.sleep(cho)
            m = ctx.find("man_cho.png")      # chờ lâu -> game nhả màn chờ, che mất túi đồ
            if m.found:
                ctx.log("treo_to: màn chờ -> chạm để thoát")
                ctx.device.tap(m.x, m.y)
                ctx.sleep(2)
    ctx.log(f"treo_to: treo {treo} lượt (thuốc + tơ)")
    ctx.ghi_phieu("treo", treo)              # 0 thường là kệ còn đầy hàng chưa hết hạn -> không tính lỗi
    _find_tap(ctx, "thoat_giao_dich.png", 10, sau, required=False)
    ve_man_hinh_chinh(ctx)
    return True


def _touch_device(ctx):
    """Tìm thiết bị cảm ứng (có ABS_MT_POSITION_X = mã 0035) qua getevent -p, cache lại.

    Cần cho keo_that: list acc của game bỏ qua `input swipe` (bơm tầng cao) nhưng
    NHẬN sự kiện chạm thật ở /dev/input/eventX. Mặc định fallback /dev/input/event2.
    """
    import re
    cached = ctx.variables.get("_touch_dev")
    if cached:
        return cached
    dev = None
    found = None
    in_abs = False
    try:
        out = ctx.device.shell("getevent -p", timeout=8)
    except Exception:
        out = ""
    for ln in out.splitlines():
        m = re.search(r"add device \d+:\s*(\S+)", ln)
        if m:
            dev, in_abs = m.group(1), False
            continue
        if "ABS (" in ln:
            in_abs = True
        elif re.match(r"\s*[A-Z]+ \(", ln):
            in_abs = False
        if in_abs and dev and re.search(r"\b0035\b", ln):
            found = dev
            break
    found = found or "/dev/input/event2"
    ctx.variables["_touch_dev"] = found
    ctx.log(f"keo_that: dùng thiết bị cảm ứng {found}")
    return found


def keo_that(ctx, x1, y1, x2, y2, steps=50, gap=0.009, hold=0.04):
    """KÉO THẬT (vuốt) bằng sendevent — cho các UI bỏ qua `input swipe` (vd list chọn acc).

    Bơm thẳng sự kiện chạm vào /dev/input/eventX trong 1 LỆNH adb shell, giãn nhịp ~9ms
    giữa các điểm bằng `sleep` trên device (mô phỏng đúng nhịp tay người ~8-10ms, tổng ~0.5s).
    Đây là cách DUY NHẤT cuộn được list acc của game này (đã kiểm chứng).

    x1,y1 -> x2,y2: đường kéo. Cuộn XUỐNG list (lộ acc bên dưới) = kéo NGÓN LÊN (y1 > y2).
    """
    dev = _touch_device(ctx)
    ABS, KEY, SYN = 3, 1, 0
    TID, X, Y, BTN = 57, 53, 54, 330   # ABS_MT_TRACKING_ID, _POSITION_X, _POSITION_Y, BTN_TOUCH
    x1, y1, x2, y2, steps = int(x1), int(y1), int(x2), int(y2), int(steps)

    def se(t, c, v):
        return f"sendevent {dev} {t} {c} {v}"

    # SLOT 0 + PRESSURE + tracking ID mới mỗi lần: thiếu 3 thứ này game lúc nhận lúc không (20/10: cũ hụt gần hết,
    #  thêm vào ăn 10/10 cả kéo lên lẫn xuống — đo trên màn chọn nhân vật)
    import random
    SLOT, PRES = 47, 58
    cmds = [se(ABS, SLOT, 0), se(ABS, TID, random.randint(100, 60000)), se(KEY, BTN, 1), se(ABS, PRES, 1),
            se(ABS, X, x1), se(ABS, Y, y1), se(SYN, 0, 0)]
    if hold:
        cmds.append(f"sleep {float(hold):.3f}")
    for i in range(1, steps + 1):
        x = int(x1 + (x2 - x1) * i / steps)
        y = int(y1 + (y2 - y1) * i / steps)
        cmds += [se(ABS, X, x), se(ABS, Y, y), se(SYN, 0, 0), f"sleep {float(gap):.3f}"]
    cmds += [se(ABS, TID, 4294967295), se(KEY, BTN, 0), se(SYN, 0, 0)]
    ctx.device.shell(";".join(cmds), timeout=30)
    return True


def _mo_man_chon_acc(ctx, hoat_dong_xy=(918, 21), cai_dat="cai_dat.png",
                     xac_nhan="xac_nhan.png", doi_tk=(846, 147),
                     timeout=20, sau_mo=3.0, sau_xac_nhan=90.0,
                     dong_update="dong_update.png"):
    """Từ MÀN CHÍNH -> mở màn CHỌN TÀI KHOẢN (list nhân vật).

    Luồng: mo_hoat_dong -> cai_dat -> tap(doi_tk 'Chuyển đổi nhân vật') -> xác nhận
           -> chờ tới khi hiện danh sách nhân vật.
    Nút Hoạt động dùng TOẠ ĐỘ CỐ ĐỊNH (icon hay đổi nên không tìm ảnh nữa).
    Trả True nếu vào được màn chọn acc.
    """
    from nthbot.engine import StepError
    mo_hoat_dong(ctx, hoat_dong_xy)          # tự bấm lại nếu game bỏ qua; banner đóng trong lúc chờ
    if not _find_tap(ctx, cai_dat, timeout, 1.5, required=True):
        return False
    ctx.device.tap(int(doi_tk[0]), int(doi_tk[1]), jitter=1)
    if not _find_tap(ctx, xac_nhan, timeout, 0, required=True):
        return False
    # chờ TỚI KHI hiện danh sách nhân vật (nút Xông Pha Giang Hồ góc phải dưới), tối đa sau_xac_nhan
    if not _cho_qua_popup(ctx, "xong_pha_giang_ho.png", timeout=sau_xac_nhan,
                          region=(600, 430, 360, 110)).found:
        raise StepError("doi_acc: không thấy màn chọn nhân vật")
    ctx.sleep(4)   # list còn chạy hiệu ứng ~3.5s: bấm sớm hơn thì game tự quay về chọn dòng 1 (đo 18/10)
    return True


def _find_tap(ctx, image, timeout, after, required=False, confidence=None, region=None):
    """Tìm ảnh (chờ tới timeout) rồi tap tâm — tiện dùng trong custom.py.

    Trả True nếu tap được; required=True mà không thấy -> raise (dừng task).
    """
    from nthbot.engine import StepError, _wait_for
    m = _wait_for(ctx, image, float(timeout), confidence, region) if timeout and float(timeout) > 0 \
        else ctx.find(image, confidence=confidence, region=region)
    if m.found:
        ctx.device.tap(m.x, m.y, jitter=0)
        ctx.log(f"Tap '{image}' ({m.confidence:.2f}) tại ({m.x},{m.y})")
        if after:
            ctx.sleep(float(after))
        return True
    if required:
        raise StepError(f"doi_acc: bắt buộc nhưng không thấy '{image}' sau {timeout}s")
    ctx.log(f"doi_acc: không thấy '{image}' (bỏ qua)")
    return False


def vi_du(ctx, nguong=0.85):
    """Ví dụ: tìm nút 'nut_nhan_thu.png' với ngưỡng tuỳ chỉnh rồi tap."""
    m = ctx.find("nut_nhan_thu.png", confidence=nguong)
    if m.found:
        ctx.device.tap(m.x, m.y)
        ctx.log(f"custom: đã tap (conf={m.confidence:.2f})")
        return True
    ctx.log("custom: không thấy nút")
    return False
