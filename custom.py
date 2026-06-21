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


def ve_man_hinh_chinh(ctx, anchor="hud_chinh.png", max=6, cho=1.2):
    """Bấm Back lặp lại cho tới khi thấy 'anchor' (1 chi tiết luôn có ở màn chính).

    Dùng trong task:  - python: { func: ve_man_hinh_chinh }
    Nếu game dùng nút X để đóng thay vì Back, đổi sang dùng find_tap nút đóng.
    """
    for _ in range(int(max)):
        if ctx.find(anchor).found:
            ctx.log("Đã ở màn hình chính.")
            return True
        ctx.device.back()
        ctx.sleep(cho)
    ok = ctx.find(anchor).found
    if not ok:
        ctx.log("Cảnh báo: chưa chắc đã về được màn hình chính.")
    return ok


def vi_du(ctx, nguong=0.85):
    """Ví dụ: tìm nút 'nut_nhan_thu.png' với ngưỡng tuỳ chỉnh rồi tap."""
    m = ctx.find("nut_nhan_thu.png", confidence=nguong)
    if m.found:
        ctx.device.tap(m.x, m.y)
        ctx.log(f"custom: đã tap (conf={m.confidence:.2f})")
        return True
    ctx.log("custom: không thấy nút")
    return False
