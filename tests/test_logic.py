"""Test logic thuần (không cần LDPlayer): đọc số OCR quyết định MUA ĐÁ, ghép tên nhân vật, phiếu kết quả, kho acc.
Chạy:  python tests/test_logic.py     (hoặc python -m pytest tests nếu đã cài pytest)
"""
import importlib.util
import os
import sys
import tempfile
import time

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)
from nthbot import accounts, xu  # noqa: E402

_spec = importlib.util.spec_from_file_location("custom_test", os.path.join(GOC, "custom.py"))
custom = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(custom)


def test_sua_xu_mat_dau_cham():
    # (28/10) OCR đọc '1.1M' thành '11M' (Stylist Mỹ) -> web hiện 11M
    for doc, dung in [("11M", "1.1M"), ("1061M", "1.061M"), ("1.088M", "1.088M"), ("3993K", "399.3K"),
                      ("936.9K", "936.9K"), ("46413", "46413"), ("", "")]:
        assert custom._sua_xu(doc) == dung, doc


def test_doc_hoat_luc():
    assert custom._doc_hoat_luc("101/1500") == 101
    assert custom._doc_hoat_luc("1565/1500") == 1565      # vượt tối đa nhờ thưởng
    assert custom._doc_hoat_luc("1021") is None           # mất '/' ('101 /' đọc thành '1021') -> không mua đá
    assert custom._doc_hoat_luc("9999/1500") is None      # vô lý -> không tin
    assert custom._doc_hoat_luc("") is None


def test_gia_da_hop_le():
    # 05/11: '84' đọc thành '4', '27' -> tưởng rẻ, mua đá đắt
    assert not custom._gia_da_hop_le("4")
    assert not custom._gia_da_hop_le("27")
    assert not custom._gia_da_hop_le("")
    assert not custom._gia_da_hop_le("63") and not custom._gia_da_hop_le("81")   # sàn chợ là 82
    assert custom._gia_da_hop_le("82") and custom._gia_da_hop_le("99")
    # chốt giá: mọi lần đọc phải khớp, lệch / vô lý / quá ít -> None (không mua, sang đá trắng tím)
    assert custom._chot_gia(["82", "82", "", "82"]) == 82
    # lần đọc dưới giá sàn 82 = chắc chắn sai -> bỏ, không làm hỏng cả lần đọc (06/11: giá 82, 1 cách đọc ra '44')
    assert custom._chot_gia(["82", "82", "44", "82", "82", "82", "44", "82"]) == 82
    assert custom._chot_gia(["84", "4", "84", "84"]) == 84       # 84 > 83 -> _mua_da vẫn không mua
    assert custom._chot_gia(["82", "88", "82", "82"]) is None    # 2 số hợp lệ lệch nhau -> không chắc
    assert custom._chot_gia(["82", "", "", ""]) is None
    assert custom._chot_gia(["82", "44", "44", "44"]) is None    # chỉ 1 lần hợp lệ
    assert custom._chot_gia(["27", "27"]) is None


def test_doc_so_ocr_hop_le():
    # 24/10: x3 đọc '7723/1500' (sai), x5 đọc '723/1500' -> có hop_le thì lấy cách đọc hợp lệ kế tiếp
    import nthbot.vision as v
    doc = {3: "7723/1500", 5: "723/1500"}
    cu, v.ocr_number = v.ocr_number, lambda scr, region, whitelist, invert, scale: doc[scale]
    try:
        ctx = type("C", (), {"capture": lambda self: None})()
        ok = lambda t: custom._doc_hoat_luc(t) is not None
        assert custom._doc_so_ocr(ctx, (0, 0, 1, 1), hop_le=ok) == "723/1500"
        assert custom._doc_so_ocr(ctx, (0, 0, 1, 1)) == "7723/1500"           # không hop_le: như cũ
        doc[5] = "8888/1500"
        assert custom._doc_so_ocr(ctx, (0, 0, 1, 1), hop_le=ok) == "7723/1500"  # không cách nào hợp lệ -> text đầu
    finally:
        v.ocr_number = cu


def test_xu_private_khong_len_web():
    # acc private: xu ghi file riêng trên máy, KHÔNG đụng xu_web/xu.json, không push
    with tempfile.TemporaryDirectory() as d:
        cu = xu._xu_path, xu._push
        xu._xu_path = lambda private: os.path.join(d, "rieng.json" if private else "web.json")
        xu._push = lambda log: (_ for _ in ()).throw(AssertionError("acc private không được push"))
        try:
            xu.ghi("tk_an", 1, "NhanVat", "1.049M", "500", log=lambda s: None, private=True)
            assert not os.path.exists(os.path.join(d, "web.json"))
            assert xu.xu_moi_nhat("tk_an", private=True)[0][:3] == ("NhanVat", "1.049M", "500")
            assert xu.xu_moi_nhat("tk_an") == []
        finally:
            xu._xu_path, xu._push = cu
    assert xu.so_xu("1.049M") == 1049000 and xu.so_xu("159.2K") == 159200 and xu.so_xu("?") == 0


def test_so_da_dang_co():
    assert custom._so_da_dang_co("12/1") == 12
    assert custom._so_da_dang_co("/1") == 0               # OCR bỏ sót số 0 đỏ
    assert custom._so_da_dang_co("") == 0


def test_cung_ten():
    c = lambda a, b: xu.cung(xu._chuan(a), xu._chuan(b))
    assert c("KRIXI", "KRXI") and c("HưToàn", "HuưToàn") and c("Hoa Phi", "_— Hoa Phii")
    assert not c("MissU", "KissU")                        # 2 nhân vật khác nhau cùng tk
    assert c("LêMinhKhoa", "Š LềMinhKho6")                  # rác đầu/cuối
    assert not c("Lâm My", "Lâm Mỳ Mỳ")                   # 01/11 tên nằm trọn trong tên khác cùng tk


def test_chon_ten_bien_the():
    nvs = {"LoveU": {"ngay": {}, "bien_the": ["LowU", "LoeU"]}, "MissU": {"ngay": {}}, "KissU": {"ngay": {}}}
    assert xu._chon_ten(nvs, "LowU") == "LoveU"
    assert xu._chon_ten(nvs, "KissU") == "KissU"
    assert xu._chon_ten(nvs, "Nemo") == "Nemo"


def test_loi_phieu():
    assert accounts.loi_phieu({"roll": "4/4", "mốc": "4/4", "treo": 0, "luc": 1}) == []
    assert accounts.loi_phieu({"chụp ảnh": "failed", "mốc": "3/4", "làm lại hảo cảm": 1}) == \
        ["chụp ảnh: failed", "mốc: 3/4"]


def test_moc_nhan_tu_truoc():
    # TNT đã làm tay trước khi bot tới: không popup 'Chúc Mừng' nào -> không báo ⚠ mốc 0/4 (21/10 KissU, Tắcc)
    class Ctx:
        def __init__(s, truoc):
            s.variables = {"_tnt_xong_truoc": truoc}
            s.device = type("D", (), {"tap": lambda *a: None})()
        find = lambda s, img: type("M", (), {"found": img == "nut_dong_vang.png"})()
        sleep = log = lambda s, *a: None
        def ghi_phieu(s, buoc, v, loi=False):
            s.variables.setdefault("_phieu", {})[buoc] = v
    goc, custom._la_chu_nhat_game = custom._la_chu_nhat_game, lambda: False   # quà tuần CN: test không phụ thuộc ngày
    try:
        for truoc, ket in [(True, []), (False, ["mốc: 0/4"])]:
            c = Ctx(truoc)
            custom.nhan_moc_hoat_dong(c, cho=0)
            assert accounts.loi_phieu(c.variables["_phieu"]) == ket
    finally:
        custom._la_chu_nhat_game = goc


def test_che_to_da_trang_tim():
    # (03/11) đá vàng không có lô <= 83 -> dòng 1 (đá trắng tím, <= 82); chế tơ lần 2 cùng nhân vật vào thẳng dòng 1
    class Ctx:
        def __init__(s):
            s.variables, s.taps, s.hl = {"_zing_user": "u", "_acc_idx": 0}, [], 300
            s.device = type("D", (), {"tap": lambda _, x, y: s.taps.append((x, y))})()
        sleep = log = lambda s, *a: None
        def ghi_phieu(s, buoc, v, loi=False):
            s.variables.setdefault("_phieu", {})[buoc] = v
    mua = []
    def fake_mua(ctx, n, gia):
        mua.append(gia)
        return gia == 82
    def fake_tap(ctx, img, *a, **k):
        ctx.hl -= 5 * 60                     # Chế Tạo ăn hết hoạt lực
    goc = (custom._mo_trang_che, custom._doc_so_ocr, custom._mua_da, custom._find_tap)
    mo = []                                  # công thức đã mở: da_vang True / False
    custom._mo_trang_che = lambda ctx, hd, tk, da_vang: mo.append(da_vang)
    custom._doc_so_ocr = lambda ctx, reg, *a, **k: f"{ctx.hl}/1500" if reg[0] == 843 else "0/1"
    custom._mua_da, custom._find_tap = fake_mua, fake_tap
    try:
        c = Ctx()
        custom.che_to(c)
        # (05/11) acc mặc định (da = trang): công thức đá trắng tím, chỉ mua đá trắng tím
        assert mo == [False] and mua == [82] and c.variables["_phieu"]["chế tơ"] == 60
        # acc chọn đá vàng: công thức đá vàng, chỉ mua đá vàng; đá vàng đắt + không có sẵn -> KHÔNG đổi sang đá trắng tím
        goc_get = accounts.get
        accounts.get = lambda u: {"da": "vang"}
        try:
            mo.clear(); mua.clear(); c.hl = 300; c.variables["_phieu"] = {}
            custom.che_to(c)
            assert mo == [True] and mua == [83] and c.variables["_phieu"]["chế tơ"] == 0
        finally:
            accounts.get = goc_get
    finally:
        custom._mo_trang_che, custom._doc_so_ocr, custom._mua_da, custom._find_tap = goc


def test_chon_cong_thuc_theo_anh():
    # (06/11) ảnh thật trang Thiết Kế sau bản cập nhật: icon tơ chỉ khớp dòng Tơ Phiêu Vân, ô đá phân biệt trắng / vàng
    import cv2
    from nthbot.vision import TemplateStore, find_template, imread_unicode
    t = TemplateStore(os.path.join(GOC, "templates"))
    to, dt, dv = t.get("to_cong_thuc.png"), t.get("da_trang.png"), t.get("da_vang.png")
    for ten, lap in (("da_trang", (True, False)), ("da_vang", (False, True))):
        scr = imread_unicode(os.path.join(GOC, "tests", "anh", f"che_to_{ten}.png"))
        assert (find_template(scr, dt, 0.85, region=custom._REG_O_DA).found,
                find_template(scr, dv, 0.85, region=custom._REG_O_DA).found) == lap, ten
        x0, y0, w, h = custom._REG_DS_CONG_THUC
        assert cv2.matchTemplate(scr[y0:y0 + h, x0:x0 + w], to, cv2.TM_CCOEFF_NORMED).max() >= 0.85


def test_lenh_web_loai_da():
    # web chọn loại đá cho acc public đúng 1 lần mỗi id; acc private / giá trị lạ bị bỏ; trạng thái kèm da + id
    import json
    _kho_tam([{"user": "pub", "chon": True}, {"user": "priv", "private": True, "chon": True}])
    assert accounts.get("pub")["da"] == "trang"            # mặc định đá trắng tím
    d = xu.web_dir()
    xu._da_ap_path = lambda: os.path.join(d, "lenh_web.json")
    with open(os.path.join(d, "lenh.json"), "w", encoding="utf-8") as f:
        json.dump({"da": {"pub": {"da": "vang", "id": "1"}, "priv": {"da": "vang", "id": "1"},
                          "x": {"da": "tim", "id": "1"}}}, f)
    assert xu.ap_lenh(log=lambda *_: None) == 1
    assert accounts.get("pub")["da"] == "vang" and accounts.get("priv")["da"] == "trang"
    assert xu.ap_lenh(log=lambda *_: None) == 0
    tt = json.load(open(os.path.join(d, "trang_thai.json"), encoding="utf-8"))
    assert tt["pub"]["da"] == "vang" and tt["pub"]["lenh_da"] == "1" and "priv" not in tt


def test_mua_da_luon_check_gia():
    # (05/11) mọi lần mua: giá chắc chắn & <= mức tối đa ở CẢ lần vào lẫn ngay trước khi bấm Mua, không thì KHÔNG mua
    class Ctx:
        variables = {}
        sleep = log = lambda s, *a: None
        device = type("D", (), {"tap": lambda *a: None})()
    goc = (custom._mo_khu_giao_dich, custom._cho_qua_popup, custom._doc_gia_da, custom._find_tap)
    bam_mua = []
    custom._mo_khu_giao_dich = lambda ctx: None
    custom._cho_qua_popup = lambda *a, **k: type("M", (), {"found": True})()
    custom._find_tap = lambda ctx, img, *a, **k: bam_mua.append(img)
    try:
        for doc, ket_qua in [([84, 84], False), ([None, 82], False), ([82, 90], False), ([82, None], False),
                             ([83, 83], True), ([82, 82], True)]:
            seq = iter(doc)
            custom._doc_gia_da = lambda ctx: (next(seq), [])
            bam_mua.clear()
            assert custom._mua_da(Ctx(), 10, 83) is ket_qua, doc
            assert (bam_mua == ["nut_mua.png"]) is ket_qua, doc
    finally:
        custom._mo_khu_giao_dich, custom._cho_qua_popup, custom._doc_gia_da, custom._find_tap = goc


def _kho_tam(accs):
    d = tempfile.mkdtemp()
    f = os.path.join(d, "accounts.yaml")
    accounts.path = lambda: f
    xu.web_dir = lambda: d
    xu._push = lambda log=None: None
    import yaml
    with open(f, "w", encoding="utf-8") as fh:   # file thô như người dùng sửa tay; load() chuẩn hoá đủ trường
        yaml.safe_dump(accs, fh, allow_unicode=True)
    accounts.save(accounts.load())
    return f


def test_kho_acc():
    hom_qua = time.time() - 86400 * 2
    _kho_tam([{"user": "pub", "status": "done", "nv_xong": 6, "cap_nhat": hom_qua, "chon": True},
              {"user": "priv", "private": True, "chon": True},
              {"user": "bo_tick", "chon": False}])
    assert not os.path.exists(accounts.path() + ".tmp")   # ghi file tạm rồi thay, không để sót
    a = accounts.get("pub")
    assert a["status"] == "" and a["nv_xong"] == 0        # qua 5h sáng -> tự reset
    assert accounts.claim("[0] LD")["user"] == "pub"      # public trước private
    assert accounts.claim("[0] LD")["user"] == "priv"
    assert accounts.claim("[0] LD") is None               # acc bỏ tick không bao giờ được lấy
    # tk bị bỏ qua giữa chừng: lưu phiếu nhưng KHÔNG coi nhân vật dở là đã làm hôm nay
    accounts.set_nv_xong("pub", 2, "MiêuMy", {"dừng (lỗi)": "failed"}, xong=False)
    a = accounts.get("pub")
    assert "MiêuMy" not in a["nhan_vat"] and "MiêuMy" in a["phieu"] and a["nv_xong"] == 2
    accounts.set_nv_xong("pub", 3, "MiêuMy", {"roll": "4/4"})
    assert "MiêuMy" in accounts.get("pub")["nhan_vat"]
    # acc làm dở được lấy trước acc mới dù đứng sau trong kho
    _kho_tam([{"user": "moi", "chon": True}, {"user": "do", "chon": True, "nv_xong": 3, "cap_nhat": time.time()}])
    assert accounts.claim("[0] LD")["user"] == "do"


def test_nhan_acc_lam_lai_dung_tk():
    # đăng nhập lỗi (banner che) -> engine làm lại bước -> phải thử lại ĐÚNG tk đó, không nhảy sang tk khác
    _kho_tam([{"user": "a1", "chon": True}, {"user": "a2", "chon": True}])

    class Ctx:
        variables = {}
        device = type("D", (), {"name": "[0] LD"})()
        log = staticmethod(lambda *_: None)

    lan, goc = [], custom.doi_tk_zing
    def gia(ctx, acc, **_):
        lan.append(acc["user"])
        if len(lan) == 1:
            raise RuntimeError("banner che")
    custom.doi_tk_zing = gia
    try:
        try:
            custom.nhan_acc(Ctx)
        except RuntimeError:
            pass
        assert accounts.get("a1")["status"] == "error"
        custom.nhan_acc(Ctx)
    finally:
        custom.doi_tk_zing = goc
    assert lan == ["a1", "a1"] and Ctx.variables["_zing_user"] == "a1"
    assert accounts.get("a1")["status"].startswith(accounts.RUNNING) and accounts.get("a2")["status"] == ""


def test_nhan_acc_dang_nhap_lai_sau_khi_ld_sap():
    # (02/11) LDPlayer sập, khởi động lại -> game ở màn chọn Zing ID -> đăng nhập lại đúng tk đang làm; ở màn chính thì thôi
    _kho_tam([{"user": "a1", "chon": True}, {"user": "a2", "chon": True}])

    class Ctx:
        variables = {"_zing_user": "a1", "_can_dn_lai": True}
        device = type("D", (), {"name": "[0] LD"})()
        log = staticmethod(lambda *_: None)

    lan, goc = [], custom.doi_tk_zing
    custom.doi_tk_zing = lambda ctx, acc, **_: (lan.append(acc["user"]), ctx.variables.pop("_can_dn_lai", None))
    try:
        custom.nhan_acc(Ctx)
        custom.nhan_acc(Ctx)   # cờ đã xoá -> không đăng nhập lại lần nữa
    finally:
        custom.doi_tk_zing = goc
    assert lan == ["a1"] and accounts.get("a2")["status"] == ""


def test_moc_code_thay_doi_khi_sua():
    # sửa custom.py hoặc thêm ảnh mẫu -> mốc đổi -> bot nạp lại code đầu vòng
    from nthbot.bot import BotRunner
    d = tempfile.mkdtemp()
    code = os.path.join(d, "custom.py")
    open(code, "w").close()
    os.utime(code, (1000, 1000))
    gia = type("B", (), {"custom_path": code, "templates": type("T", (), {"dir": d})()})()
    m1 = BotRunner._moc_code(gia)
    anh = os.path.join(d, "moi.png")
    open(anh, "w").close()
    os.utime(anh, (2000, 2000))
    assert BotRunner._moc_code(gia) == 2000 > m1


def test_cho_claude():
    # cứu tự động chịu -> engine hỏi cho_claude: TIEP = đi bước sau, LAM_LAI = làm lại, BO_QUA = bỏ acc
    from nthbot.engine import BoQuaAcc, Context, StepError, run_steps
    lan = []

    def hong(ctx):
        lan.append(1)
        if len(lan) < 2:
            raise StepError("kẹt")
        return True
    ctx = Context(device=None, templates=None, log=lambda *_: None,
                  custom_funcs={"hong": hong, "ok": lambda ctx: lan.append("sau") or True})
    ctx.cuu_loi = lambda step, loi: False
    tl = iter(["LAM_LAI"])
    ctx.cho_claude = lambda step, loi: next(tl)
    run_steps([{"python": "hong"}, {"python": "ok"}], ctx)
    assert lan == [1, 1, "sau"]                            # làm lại bước lỗi rồi đi tiếp
    lan.clear()
    ctx.cho_claude = lambda step, loi: "TIEP"
    ctx.custom_funcs["hong"] = lambda ctx: (_ for _ in ()).throw(StepError("kẹt"))
    run_steps([{"python": "hong"}, {"python": "ok"}], ctx)
    assert lan == ["sau"]                                  # Claude tự làm xong bước -> bỏ qua bước, đi bước sau
    ctx.cho_claude = lambda step, loi: "BO_QUA"
    try:
        run_steps([{"python": "hong"}], ctx)
        assert False
    except BoQuaAcc:
        pass

    # giao thức file: bot ghi cho_claude_<máy>.json, Claude ghi tra_loi -> bot đọc rồi xoá file
    import json
    import threading
    from nthbot.bot import BotRunner
    from nthbot.orchestrator import app_dir
    dev = type("D", (), {"name": "[9] TEST", "serial": "x", "screencap": lambda self: (_ for _ in ()).throw(OSError())})()
    bot = type("B", (), {"device": dev, "dang_cuu": False, "_log": lambda self, m: None})()
    path = os.path.join(app_dir(), "logs", "cho_claude_9_TEST.json")
    ctx2 = Context(device=None, templates=None, variables={"_zing_user": "u", "_acc_idx": 2})

    def claude():
        while not os.path.exists(path):
            time.sleep(0.2)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        assert d["acc"] == "u" and d["nv"] == 3 and d["tra_loi"] == ""
        d["tra_loi"] = "tiep"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
    threading.Thread(target=claude).start()
    assert BotRunner._cho_claude(bot, ctx2, {"python": "x"}, StepError("kẹt"), phut=0.5) == "TIEP"
    assert not os.path.exists(path)


def test_lenh_web_doi_gio():
    # web ghi lenh.json -> tool đổi giờ acc public đúng 1 lần mỗi id; acc private / giờ sai bị bỏ; trạng thái kèm id
    import json
    _kho_tam([{"user": "pub", "chon": True, "gio": "10:00"}, {"user": "moi", "chon": True},
              {"user": "priv", "private": True, "chon": True, "gio": "09:00"}])
    d = xu.web_dir()
    xu._da_ap_path = lambda: os.path.join(d, "lenh_web.json")
    lenh = {"gio": {"pub": {"gio": "13:30", "id": "1"}, "moi": {"gio": "08:05", "id": "1"},
                    "priv": {"gio": "07:00", "id": "1"}, "x": {"gio": "25:00", "id": "1"}}}
    with open(os.path.join(d, "lenh.json"), "w", encoding="utf-8") as f:
        json.dump(lenh, f)
    assert xu.ap_lenh(log=lambda *_: None) == 2
    assert accounts.get("pub")["gio"] == "13:30" and accounts.get("moi")["gio"] == "08:05"
    assert accounts.get("priv")["gio"] == "09:00"
    accounts.dat_gio("pub", "14:10")                       # bot tự dời giờ sau nhân vật 1 -> lệnh cũ không đè lại
    assert xu.ap_lenh(log=lambda *_: None) == 0 and accounts.get("pub")["gio"] == "14:10"
    tt = json.load(open(os.path.join(d, "trang_thai.json"), encoding="utf-8"))
    assert tt["pub"]["gio"] == "14:10" and tt["pub"]["lenh"] == "1" and "priv" not in tt


def test_chon_theo_ten_tk_1_nhan_vat():
    # tk chỉ 1 nhân vật (đang chọn sẵn): bấm dòng nào tên cũng không đổi -> dòng 1 vẫn phải được chọn (23/10)
    class Ctx:
        variables = {}
        log = staticmethod(lambda *_: None)
        sleep = staticmethod(lambda *_: None)
    goc = custom._doc_ten_nv, custom._chon_nhan_vat, custom._da_lam_hom_nay
    custom._doc_ten_nv = lambda ctx: "NV A"
    custom._chon_nhan_vat = lambda ctx, x, y: ctx.variables.__setitem__("_ten_nv", "NV A")
    try:
        custom._da_lam_hom_nay = lambda ctx, ten_cu="": []
        assert custom._chon_theo_ten(Ctx, dong=[(1, 1, 0), (2, 2, 0)])
        custom._da_lam_hom_nay = lambda ctx, ten_cu="": [xu._chuan("NV A")]
        assert not custom._chon_theo_ten(Ctx, dong=[(1, 1, 0), (2, 2, 0)])
    finally:
        custom._doc_ten_nv, custom._chon_nhan_vat, custom._da_lam_hom_nay = goc


def test_treo_lai():
    # chế độ Treo lại tơ: lấy acc tick "Treo lại" kể cả acc ✓, KHÔNG đụng status / nv_xong; web tick + Start đúng 1 lần
    import json
    _kho_tam([{"user": "xong", "status": "done", "nv_xong": 6, "cap_nhat": time.time(), "chon": True},
              {"user": "priv", "private": True, "chon": False}])   # không acc chạy thường nào chờ -> rảnh treo
    d = xu.web_dir()
    xu._da_ap_path = lambda: os.path.join(d, "lenh_web.json")
    with open(os.path.join(d, "lenh.json"), "w", encoding="utf-8") as f:
        json.dump({"treo": {"xong": {"bat": True, "id": "1"}, "priv": {"bat": True, "id": "1"}},
                   "start": {"che_do": "treo", "id": "s1"}}, f)
    start = []
    assert xu.ap_lenh(log=lambda *_: None, bat_dau=start.append) == 2
    assert xu.ap_lenh(log=lambda *_: None, bat_dau=start.append) == 0 and start == ["treo"]
    assert accounts.get("xong")["treo"] == "cho" and accounts.get("priv")["treo"] == ""   # private không nhận lệnh web
    tt = json.load(open(os.path.join(d, "trang_thai.json"), encoding="utf-8"))
    assert tt["_tool"]["lenh_start"] == "s1" and tt["xong"]["lenh_treo"] == "1" and "priv" not in tt

    class Ctx:
        variables = {"treo_lai": True}
        device = type("D", (), {"name": "[0] LD"})()
        log = staticmethod(lambda *_: None)

    goc = custom.doi_tk_zing
    custom.doi_tk_zing = lambda ctx, acc, **_: True
    try:
        custom.nhan_acc(Ctx)
    finally:
        custom.doi_tk_zing = goc
    a = accounts.get("xong")
    assert Ctx.variables["_zing_user"] == "xong" and a["treo"].startswith(accounts.RUNNING)
    assert a["status"] == "done" and a["nv_xong"] == 6        # acc ✓ vẫn ✓
    Ctx.variables["_treo_da_lam"] = ["MiêuMy"]
    assert custom._da_lam_hom_nay(Ctx) == ["mieumy"]          # nhân vật "đã làm" = đã treo lại lượt này
    accounts.release("[0] LD")                                # Stop giữa chừng -> lần Start sau treo lại
    assert accounts.get("xong")["treo"] == "cho" and accounts.get("xong")["status"] == "done"


def test_ranh_cho_treo():
    # treo lại chỉ chạy khi chạy thường rảnh: không acc tới giờ / đang chạy, acc hẹn kế còn >= 40 phút
    from datetime import datetime
    now = datetime(2026, 10, 26, 14, 0)
    _kho_tam([{"user": "x", "status": "done", "cap_nhat": time.time(), "chon": True},
              {"user": "h", "chon": True, "gio": "14:20"}])
    assert not accounts.ranh_cho_treo(now=now)                # hẹn 20 phút nữa (< 30) -> nhường
    accounts.dat_gio("h", "15:00")
    assert accounts.ranh_cho_treo(now=now)                    # hẹn 60 phút nữa -> treo được
    accounts.set_status("h", accounts.RUNNING + "[0] LD")
    assert not accounts.ranh_cho_treo(now=now)                # acc đang chạy full
    _kho_tam([{"user": "ngay", "chon": True}])
    assert accounts.ranh_cho_treo(now=now)                    # acc "chạy ngay" chờ nhóm treo xong (luật nhóm 4 acc)
    # acc chờ treo là public -> treo trước cả acc private hẹn giờ đã tới
    _kho_tam([{"user": "pub", "status": "done", "cap_nhat": time.time(), "chon": True, "treo": "cho"},
              {"user": "priv", "private": True, "chon": True, "gio": "13:00"}])
    assert accounts.ranh_cho_treo(now=now)
    accounts.set_treo("pub", "")
    assert not accounts.ranh_cho_treo(now=now)                # không còn acc public chờ treo -> private chạy full


def test_cho_treo_duoc_nhom_5():
    # chạy full xong cả 5 acc của nhóm (thứ tự theo giờ như UI/web) mới treo lại acc tick trong nhóm đó
    xong = {"status": "done", "cap_nhat": time.time(), "chon": True}
    _kho_tam([{"user": "a1", **xong, "gio": "08:00", "treo": "cho"}, {"user": "a2", **xong, "gio": "09:00"},
              {"user": "a3", **xong, "gio": "10:00"}, {"user": "a4", "chon": True, "gio": "11:00"},
              {"user": "a5", **xong, "gio": "11:30"},
              {"user": "b1", **xong, "gio": "12:00", "treo": "cho"},
              {"user": "p1", **xong, "private": True, "treo": "cho"}])
    assert [a["user"] for a in accounts.cho_treo_duoc()] == ["b1", "p1"]  # a4 chưa chạy -> nhóm a1..a5 chưa treo; nhóm b1 xong
    accounts.set_status("a4", "error")                                   # ✗ cũng tính là xong nhóm
    assert [a["user"] for a in accounts.cho_treo_duoc()] == ["a1", "b1", "p1"]


def test_ghi_treo_lai():
    # treo lại xong nhân vật -> ghi số ô vào phiếu hôm nay (tên OCR lệch vẫn khớp), web có 'treo_lai'
    import json
    _kho_tam([{"user": "u", "chon": True}])
    accounts.set_nv_xong("u", 1, "KRIXI", {"treo": 8})
    assert accounts.ghi_treo_lai("u", "KRXI", 3)                  # OCR lần sau đọc thiếu chữ
    assert accounts.get("u")["phieu"]["KRIXI"]["treo lại"] == 3
    assert not accounts.ghi_treo_lai("u", "NguoiLa", 2)           # không có phiếu chạy full hôm nay
    tt = json.load(open(os.path.join(xu.web_dir(), "trang_thai.json"), encoding="utf-8"))
    assert tt["u"]["nhan_vat"][0]["treo_lai"] == 3 and tt["u"]["nhan_vat"][0]["treo_lai_luc"]


def test_gio_hom_nay_theo_ngay_game():
    # ngày game sang lúc 5h: 01:06 sáng 27/10 acc hẹn 23:26 vẫn là 23:26 ngày 26 (đã quá giờ -> chạy ngay)
    from datetime import datetime
    dem = datetime(2026, 10, 27, 1, 6)
    assert accounts.gio_hom_nay({"gio": "23:26"}, dem) == datetime(2026, 10, 26, 23, 26)
    assert accounts.gio_hom_nay({"gio": "02:00"}, dem) == datetime(2026, 10, 27, 2, 0)      # đêm cuối ngày 26
    trua = datetime(2026, 10, 27, 14, 0)
    assert accounts.gio_hom_nay({"gio": "23:26"}, trua) == datetime(2026, 10, 27, 23, 26)
    assert accounts.gio_hom_nay({"gio": "02:00"}, trua) == datetime(2026, 10, 28, 2, 0)


def test_screencap_tho():
    # header 16 byte (Android 9+) và 12 byte đều giải mã đúng; định dạng lạ -> None (lùi về PNG)
    import numpy as np
    from nthbot.adb import _giai_ma_tho
    rgba = np.zeros((2, 3, 4), np.uint8)
    rgba[0, 0] = (255, 0, 0, 255)                          # điểm đỏ
    for hd in (np.array([3, 2, 1, 0], np.uint32), np.array([3, 2, 1], np.uint32)):
        img = _giai_ma_tho(hd.tobytes() + rgba.tobytes())
        assert img.shape == (2, 3, 3) and tuple(img[0, 0]) == (0, 0, 255)   # BGR
    assert _giai_ma_tho(np.array([3, 2, 5, 0], np.uint32).tobytes() + rgba.tobytes()) is None
    assert _giai_ma_tho(b"") is None


def test_discord_khong_bao_private():
    # (28/10) acc private không được lên Discord: tên che 'tk testN' hoặc acc đang làm là private
    from unittest import mock
    from nthbot import accounts, bot
    r = bot.BotRunner.__new__(bot.BotRunner)
    r.ctx = mock.Mock(variables={})
    assert r._dang_lam_private("⟦ACC⟧ BỎ QUA tài khoản tk test1: x")
    with mock.patch.object(accounts, "get", lambda u: {"private": u == "bimat"}):
        r.ctx.variables = {"_zing_user": "bimat"}
        assert r._dang_lam_private("⟦CHỜ CLAUDE⟧ x")
        r.ctx.variables = {"_zing_user": "congkhai"}
        assert not r._dang_lam_private("⟦CHỜ CLAUDE⟧ x")
        r.ctx.variables = {"_dang_nhap": "bimat"}        # (06/11) lỗi lúc đang đăng nhập acc private
        assert r._dang_lam_private("Cứu lỗi: nhờ Claude xem màn hình (lần 1/8)...")
    r.ctx = None
    assert not r._dang_lam_private("Báo cáo: x")


def test_discord_khong_bao_het_kho_va_loi_private():
    # (29/10) 'Kết thúc: kho acc hết' và lỗi acc private trong báo cáo cuối không lên Discord
    from unittest import mock
    from nthbot import accounts, bot
    r = bot.BotRunner.__new__(bot.BotRunner)
    r.device, r.on_log, r.ctx, r.ket_tu = mock.Mock(), lambda *a: None, None, None
    r.device.name = "[0] LD"
    gui = []
    bc = "# Báo cáo\n\n## acc1 — ✓ xong 6/6\n- ✓ A (10:00)\n\n## tk test2 — ✓ xong 1/6\n- ⚠ X (23:07): y\n"
    with mock.patch.object(bot, "_bao_discord", gui.append), mock.patch.object(accounts, "bao_cao", lambda: bc), \
            mock.patch("builtins.open", mock.mock_open()):
        r._log("Kết thúc: kho acc không còn acc nào chưa chạy")
        r._ghi_bao_cao()
        assert gui == []
        bc += "\n## acc3 — ✓ xong 6/6\n- ⚠ Z (01:00): y\n"
        r._ghi_bao_cao()
        assert len(gui) == 1 and "⚠ 1 nhân vật lỗi" in gui[0]


def test_discord_dung_im_3_phut():
    # (28/10) watchdog 90s/lần: lần 2 liền nhau (~3 phút đứng im) báo 1 lần; có tiến triển thì đếm lại
    from unittest import mock
    from nthbot import bot
    r = bot.BotRunner.__new__(bot.BotRunner)
    r.device, r.on_log, r.ctx, r.ket_tu, r.loi_luc = mock.Mock(name="dev"), lambda *a: None, None, None, ""
    r.device.name = "[0] LD"
    gui, gio = [], [1000.0]
    with mock.patch.object(bot, "_bao_discord", gui.append), mock.patch.object(bot.time, "time", lambda: gio[0]), \
            mock.patch("builtins.open", mock.mock_open()):
        r._log("Watchdog: 93s không có tiến triển -> dò banner")
        gio[0] += 90
        r._log("Hỏi Claude tìm nút đóng banner lạ...")
        r._log("Watchdog: game không phản hồi (ANR) -> bấm Wait")
        assert len(gui) == 1 and "3 PHÚT" in gui[0]
        gio[0] += 90
        r._log("Watchdog: game không phản hồi (ANR) -> bấm Wait")
        assert len(gui) == 1                      # không báo lặp
        r._log("Tap 'x.png'")                     # có tiến triển -> đếm lại, báo đã chạy lại
        assert len(gui) == 2 and "chạy lại bình thường" in gui[1]
        r._log("Watchdog: 90s không có tiến triển -> dò banner")
        assert len(gui) == 2


def test_discord_bao_chay_lai_binh_thuong():
    # (02/11 user) đã báo lỗi lên Discord -> lần Tap kế báo 1 dòng 'chạy lại bình thường', không lặp
    from unittest import mock
    from nthbot import bot
    r = bot.BotRunner.__new__(bot.BotRunner)
    r.device, r.on_log, r.ctx, r.ket_tu, r.loi_luc = mock.Mock(name="dev"), lambda *a: None, None, None, ""
    r.device.name = "[0] LD"
    gui = []
    with mock.patch.object(bot, "_bao_discord", gui.append), mock.patch("builtins.open", mock.mock_open()):
        r._log("Tap 'x.png' (1.00) tại (1,2)")
        assert gui == []                          # chưa có lỗi -> không báo
        r._log("Cứu lỗi: nhờ Claude xem màn hình (lần 1/8)...")
        r._log("Claude đã xử lý -> làm lại bước (lần cứu 1/2)")
        r._log("Tap 'nghe_nghiep.png' (1.00) tại (591,137)")
        r._log("Tap 'y.png' (1.00) tại (1,2)")
        assert len(gui) == 2 and "chạy lại bình thường" in gui[1]


def test_cum_chu_giu_chu_ben_trai():
    # (02/11 mylu1108) 'Sư Tán': 'Sư' cách 'Tán' 9px -> phải giữ; nét trang trí bên phải cách 9px -> vẫn bỏ
    import numpy as np
    import custom
    cot = np.r_[37:44, 46:53, 62:82, 91:95]           # Sư | Tán | nét bút (k=1)
    assert custom._cum_chu(cot, 1) == (37, 81)
    assert custom._cum_chu(np.r_[10:14, 30:50], 1) == (30, 49)   # rác cách xa bên trái -> bỏ


def test_public_sap_toi_15_phut():
    from datetime import datetime
    from unittest import mock
    now = datetime(2026, 10, 30, 18, 0)
    accs = [dict(user="pub", private=False, chon=True, status="", gio="18:15"),
            dict(user="pub2", private=False, chon=True, status="done", gio="18:05"),   # đã ✓ -> bỏ
            dict(user="pri", private=True, chon=True, status="", gio="18:01")]          # private -> bỏ
    with mock.patch.object(accounts, "load", lambda: accs):
        assert custom._public_sap_toi(accounts, now=now) == datetime(2026, 10, 30, 18, 15)
        accs[0]["gio"] = "18:16"                                                        # còn 16 phút -> chưa
        assert custom._public_sap_toi(accounts, now=now) is None
        accs[0]["gio"] = "17:50"                                                        # đã tới giờ -> có
        assert custom._public_sap_toi(accounts, now=now) == datetime(2026, 10, 30, 17, 50)


def test_mo_hoat_dong_bang_da_mo_khong_bam():
    # (31/10) bảng Hoạt động mở sẵn -> không bấm (bấm là thu bảng lại)
    from types import SimpleNamespace
    from unittest import mock
    tap = mock.Mock()
    ctx = SimpleNamespace(device=SimpleNamespace(tap=tap))
    with mock.patch.object(custom, "_cho_qua_popup", lambda *a, **k: SimpleNamespace(found=True)):
        assert custom.mo_hoat_dong(ctx) is True
    tap.assert_not_called()


def test_ve_man_hinh_chinh_bam_hut_thi_dong_popup():
    # (31/10) popup không X đè trang: bấm back không đổi màn -> phải gọi dong_banner thay vì bấm hụt tới hết lượt
    import numpy as np
    from types import SimpleNamespace
    from unittest import mock
    man = np.zeros((540, 960, 3), np.uint8)
    co_popup = [True]
    def dong(ctx):
        if co_popup[0]:
            co_popup[0] = False
            return True
        return False
    taps = []
    ctx = SimpleNamespace(capture=lambda: man, log=lambda *a: None, sleep=lambda s: None,
                          device=SimpleNamespace(tap=lambda x, y: taps.append((x, y))),
                          # nút back còn thấy tới khi popup đóng + bấm 1 lần sau đó
                          find=lambda img, screen=None, **k: SimpleNamespace(
                              found=img == "nut_dong.png" and len(taps) < 2, x=50, y=27))
    with mock.patch.object(custom, "dong_banner", dong):
        custom.ve_man_hinh_chinh(ctx)
    assert not co_popup[0] and len(taps) == 2


def test_chu_nhat_game():
    from datetime import datetime
    assert custom._la_chu_nhat_game(datetime(2026, 11, 1, 12, 0))       # CN trưa
    assert not custom._la_chu_nhat_game(datetime(2026, 11, 1, 4, 59))   # CN rạng sáng = ngày game thứ 7
    assert custom._la_chu_nhat_game(datetime(2026, 11, 2, 4, 59))       # T2 rạng sáng = vẫn ngày game CN
    assert not custom._la_chu_nhat_game(datetime(2026, 11, 2, 5, 0))


def test_doc_bluestacks_conf():
    from nthbot.bluestacks import doc_conf
    from nthbot.adb import Device
    ds, adb = doc_conf('bst.enable_adb_access="0"\nbst.instance.Pie64.adb_port="5555"\n'
                       'bst.instance.Pie64.display_name="BlueStacks App Player"\n'
                       'bst.instance.Pie64.status.adb_port="5565"\nbst.instance.Rvc64.adb_port=""\n')
    assert not adb and len(ds) == 1
    assert (ds[0].name, ds[0].display_name, ds[0].serial) == ("Pie64", "BlueStacks App Player", "127.0.0.1:5565")
    assert doc_conf('bst.enable_adb_access="1"')[1]
    bs, ld, tay = Device("s", bs_instance="Pie64"), Device("s", ld_index=0), Device("s")
    assert (bs.quan_ly, bs.loai_may, ld.quan_ly, ld.loai_may, tay.quan_ly) == (True, "BlueStacks", True, "LDPlayer", False)


def test_pc_toa_do_va_keo():
    from nthbot.pc import PcDevice, doi_toa_do, toa_do_sendevent
    assert doi_toa_do(960, 540, 1280, 720) == (1280, 720) and doi_toa_do(45, 19, 1280, 720) == (60, 25)
    cmd = ("sendevent /dev/input/event2 3 47 0;sendevent /dev/input/event2 3 53 100;sendevent /dev/input/event2 3 54 400;"
           "sendevent /dev/input/event2 0 0 0;sleep 0.009;sendevent /dev/input/event2 3 53 100;"
           "sendevent /dev/input/event2 3 54 200;sendevent /dev/input/event2 3 57 4294967295")
    assert toa_do_sendevent(cmd) == [(100, 400), (100, 200)]
    pc = PcDevice("Nghịch Thủy Hàn")
    assert (pc.loai_may, pc.quan_ly) == ("PC", False)


def test_templates_pc_uu_tien():
    import numpy as np
    from nthbot.vision import TemplateStore, imwrite_unicode
    with tempfile.TemporaryDirectory() as chung, tempfile.TemporaryDirectory() as pc:
        imwrite_unicode(os.path.join(chung, "a.png"), np.zeros((4, 4, 3), np.uint8))
        imwrite_unicode(os.path.join(chung, "b.png"), np.zeros((4, 4, 3), np.uint8))
        imwrite_unicode(os.path.join(pc, "a.png"), np.full((6, 6, 3), 255, np.uint8))
        s = TemplateStore(chung, override_dir=pc)
        assert s.get("a.png").shape[0] == 6 and s.get("b.png").shape[0] == 4


def test_mau_trong_suot_bo_qua_nen():
    import numpy as np
    from nthbot.vision import TemplateStore, find_template, imwrite_unicode
    rng = np.random.default_rng(1)
    chu = np.zeros((12, 30, 3), np.uint8)
    chu[3:9, 2:28:4] = 255                                   # "nét chữ" trắng
    import cv2
    alpha = cv2.dilate((chu[:, :, 0] > 0).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))   # chữ + viền tối
    man = rng.integers(0, 120, (60, 100, 3), dtype=np.uint8)   # nền động khác hẳn lúc cắt mẫu
    man[20:32, 40:70][alpha > 0] = chu[alpha > 0]
    with tempfile.TemporaryDirectory() as d:
        imwrite_unicode(os.path.join(d, "m.png"), np.dstack([chu, alpha]))
        mau = TemplateStore(d).get("m.png")
        assert mau.shape[2] == 4
        m = find_template(man, mau, confidence=0.9)
        assert m.found and (m.x, m.y) == (55, 26)


def test_cho_muon_chuot_doi_o_cho_phep():
    import threading
    from types import SimpleNamespace
    from nthbot import pc
    logs = []
    ctx = SimpleNamespace(check_stop=lambda: None, log=logs.append, sleep=time.sleep, tien_trien=0,
                          device=SimpleNamespace(ranh_tay=lambda g: True))
    pc.CHO_PHEP_CHUOT.clear()
    threading.Timer(0.6, pc.CHO_PHEP_CHUOT.set).start()
    bd = time.time()
    custom._cho_muon_chuot(ctx)
    assert time.time() - bd >= 0.5 and len(logs) == 2 and pc.CHO_PHEP_CHUOT.is_set()


def test_ld_dang_chay_ma_do_thi_tat_bat_lai():
    # (04/11) LDPlayer báo đang chạy nhưng Android đơ (adb im) -> _bat_ldplayer tự tắt hẳn rồi bật lại, rồi boot xong
    import threading
    from nthbot import bot as botmod

    class MayDo:
        loai_may, name, bs_instance = "LDPlayer", "[1] LD", ""
        def __init__(self):
            self.chay, self.da_tat, self.da_bat = True, 0, 0
        def may_dang_chay(self):
            return self.chay
        def tat_may(self):
            self.da_tat += 1
            self.chay = False
        def bat_may(self):
            self.da_bat += 1
            self.chay = True
        def connect(self):
            return True
        def getprop(self, _):
            if not self.da_bat:          # chưa bật lại -> đơ
                raise RuntimeError("adb timeout")
            return "1"

    r = object.__new__(botmod.BotRunner)
    r.device, r.stop_event, r.on_log = MayDo(), threading.Event(), None
    r._log = lambda m: None
    ngu = botmod.time.sleep
    botmod.time.sleep = lambda s: None
    try:
        r._bat_ldplayer(timeout=5, treo=0)
    finally:
        botmod.time.sleep = ngu
    assert (r.device.da_tat, r.device.da_bat) == (1, 1)


if __name__ == "__main__":
    for ten, fn in list(globals().items()):
        if ten.startswith("test_"):
            fn()
            print("OK", ten)
