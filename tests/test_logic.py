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


def test_doc_hoat_luc():
    assert custom._doc_hoat_luc("101/1500") == 101
    assert custom._doc_hoat_luc("1565/1500") == 1565      # vượt tối đa nhờ thưởng
    assert custom._doc_hoat_luc("1021") is None           # mất '/' ('101 /' đọc thành '1021') -> không mua đá
    assert custom._doc_hoat_luc("9999/1500") is None      # vô lý -> không tin
    assert custom._doc_hoat_luc("") is None


def test_so_da_dang_co():
    assert custom._so_da_dang_co("12/1") == 12
    assert custom._so_da_dang_co("/1") == 0               # OCR bỏ sót số 0 đỏ
    assert custom._so_da_dang_co("") == 0


def test_cung_ten():
    c = lambda a, b: xu.cung(xu._chuan(a), xu._chuan(b))
    assert c("KRIXI", "KRXI") and c("HưToàn", "HuưToàn") and c("Hoa Phi", "_— Hoa Phii")
    assert not c("MissU", "KissU")                        # 2 nhân vật khác nhau cùng tk


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
    for truoc, ket in [(True, []), (False, ["mốc: 0/4"])]:
        c = Ctx(truoc)
        custom.nhan_moc_hoat_dong(c, cho=0)
        assert accounts.loi_phieu(c.variables["_phieu"]) == ket


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


if __name__ == "__main__":
    for ten, fn in list(globals().items()):
        if ten.startswith("test_"):
            fn()
            print("OK", ten)
