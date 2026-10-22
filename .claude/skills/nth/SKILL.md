---
name: nth
description: Mở tool NTH Bot (có UI), tự Start task Thanh Nhai Thư 6 acc rồi trông chạy tới hết kho acc; gặp lỗi thì chẩn đoán, sửa code, cho làm lại đúng acc/nhân vật bị lỗi. Dùng khi người dùng gõ /nth hoặc bảo "chạy tool", "mở tool và trông nó".
---

# /nth — mở tool, trông chạy, sửa lỗi, làm lại cho chỉn chu

Thư mục: `C:\Users\hi\Doancute\hack2\NTH`. **Đọc `KINH_NGHIEM.md` trước** (luồng game, toạ độ, lỗi đã gặp).
Trả lời người dùng bằng tiếng Việt, ngắn.

## Luật cứng

1. **KHÔNG BAO GIỜ tự tắt tool** (không `Stop-Process`/`taskkill` tiến trình `python run.py`, không tắt LDPlayer).
   Sửa `custom.py` / ảnh mẫu trong `templates/` → tool **tự nạp lại đầu vòng kế** (giữa 2 nhân vật, log
   `Nạp lại custom.py + ảnh mẫu`), không cần tắt. Chỉ sửa `nthbot/*.py` hoặc `tasks/*.yaml` mới phải mở lại tool →
   **hỏi người dùng** trước; ưu tiên dồn fix vào `custom.py`. Tool tự tắt LDPlayer khi chờ giờ hẹn là bình thường.
2. **Mở tool TÁCH KHỎI Claude Code** để Claude Code thiếu RAM không giết nó (bash `run_in_background` bị giết, đã gặp 22/10):
   ```powershell
   Start-Process python -ArgumentList "run.py","--start" -WorkingDirectory "C:\Users\hi\Doancute\hack2\NTH"
   ```
   `--start` = tick mọi instance + Start task đang chọn (mặc định TNT 6 acc). Mở UI xong `accounts.release()` tự
   trả acc "đang chạy" cũ về "chưa chạy"; acc làm dở (nv_xong > 0) được lấy trước acc mới.
3. **Claude không được bỏ trông giữa chừng**: theo dõi liên tục bằng Monitor (re-arm mỗi khi hết hạn) tới khi log có
   `kho acc không còn acc nào chưa chạy` / `Báo cáo:` hoặc người dùng bảo dừng. Không kết thúc lượt khi tool còn chạy
   mà chưa có Monitor đang canh.
4. Không đẩy thông tin acc **private** lên web/GitHub. Không commit/push repo `NTH` khi người dùng chưa bảo
   (repo `xu_web/` tool tự push, đừng đụng trừ khi sửa web).

## Bước 1 — mở tool

- Đã có tiến trình chưa: `wmic process where "name='python.exe'" get ProcessId,CommandLine`.
  - Có `run.py` → **không mở thêm** (2 tool tranh LDPlayer). Xem log hôm nay: đang chạy thì chuyển sang bước 2;
    UI mở mà chưa Start (log không có dòng mới) → nhờ người dùng bấm **▶ Start**.
  - Chưa có → mở theo luật 2, chờ ~10s, xác nhận có dòng `Bắt đầu task` trong log.
- RAM trống < 2 GB (`wmic OS get FreePhysicalMemory`) → báo người dùng trước khi mở.

## Bước 2 — trông chạy

Log: `logs/<YYYY-MM-DD>.log` (đổi file khi qua ngày mới → re-arm Monitor với file mới).

```
Monitor(timeout_ms=1800000, description="NTH: lỗi / acc xong", command=
  cd "C:/Users/hi/Doancute/hack2/NTH" && tail -n 0 -F logs/$(date +%F).log | grep --line-buffered -E
  "CHỜ CLAUDE|BỎ QUA|⚠|✗|[Ll]ỗi|Traceback|Exception|Claude đã xử lý|failed|Đã dừng|kho acc không còn|Báo cáo:|hoàn thành|nhận tk Zing")
```
Hết hạn mà không có sự kiện → kiểm tra log còn chạy không (dòng cuối quá ~10 phút mà không phải đang chờ giờ hẹn
`chờ tới HH:MM` = **treo**) rồi re-arm. Báo người dùng gọn mỗi khi xong 1 acc hoặc có lỗi.

## Bước 3a — tool đang CHỜ CLAUDE (ưu tiên số 1, tool đứng im tối đa 15 phút rồi bỏ acc)

Log `⟦CHỜ CLAUDE⟧` = tool tự đóng banner + `claude -p` cứu 2 lần vẫn kẹt → tool DỪNG, giữ nguyên acc/nhân vật, chờ.
File `logs/cho_claude_<máy>.json`: `buoc`, `loi`, `acc`, `nv`, `serial`, `anh` (ảnh lúc kẹt), `tra_loi`.
Lúc này watchdog đứng yên, **chỉ mình Claude điều khiển** LDPlayer:

1. Read ảnh + log quanh lỗi, hiểu bước `buoc` cần đạt trạng thái gì (đọc hàm tương ứng trong `custom.py`).
2. Điều khiển bằng adb (`serial` trong json, màn 960x540), chụp lại sau MỖI thao tác để kiểm tra:
   ```bash
   A=C:/LDPlayer/LDPlayer14/adb.exe; S=127.0.0.1:5555
   "$A" -s $S exec-out screencap -p > "<scratchpad>/s.png"      # rồi Read
   "$A" -s $S shell input tap X Y
   "$A" -s $S shell input swipe X1 Y1 X2 Y2 400
   "$A" -s $S shell input keyevent KEYCODE_BACK
   ```
   Không mua bằng tiền thật / Văn Ngọc, không xoá nhân vật, không đổi mật khẩu; thao tác nào không chắc → hỏi người dùng.
3. Xong thì ghi trả lời vào json (giữ nguyên các trường khác), tool đọc trong ~3s:
   ```bash
   PYTHONIOENCODING=utf-8 python -c "import json,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['tra_loi']=sys.argv[2];json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False)" logs/cho_claude_0_LD.json LAM_LAI
   ```
   - `LAM_LAI`: đã đưa game về trạng thái đầu bước (thường là màn chính) → tool chạy lại bước đó.
   - `TIEP`: Claude đã tự làm XONG việc của bước → tool đi bước sau.
   - `BO_QUA`: không cứu được (sai mk, bảo trì...) → tool bỏ acc. Mỗi bước tool chờ tối đa 3 lần.
4. Sau đó sửa code (bước 3b) để lần sau tool tự qua được lỗi này.

## Bước 3b — gặp lỗi

Nguồn: dòng log quanh lỗi, `logs/loi_<giờ>.md` + `.png` (Claude chẩn đoán sẵn), `logs/phieu_*.png`,
phiếu kết quả trong `accounts.yaml` (`phieu` từng nhân vật, bước `failed`), `logs/bao_cao_<ngày>.md`.
Chụp màn hình hiện tại khi cần (adb trong `config.yaml`, hiện là LDPlayer14):
```bash
"C:/LDPlayer/LDPlayer14/adb.exe" -s 127.0.0.1:5555 exec-out screencap -p > "<scratchpad>/scr.png"
```
rồi Read ảnh. Phân loại:

- **Lỗi dữ liệu acc** (sai mk, tk khoá, mã 7020-13) → không sửa code, báo người dùng, để acc ✗.
- **Lỗi tool** (banner lạ, ảnh mẫu trượt, chờ sai màn, toạ độ) → sửa tận gốc trong `custom.py` / `nthbot/*.py`,
  đúng phong cách code hiện có (comment tiếng Việt ngắn, ghi ngày đo). Cần ảnh mẫu mới → cắt từ ảnh chụp màn hình
  bằng OpenCV (`nthbot.vision.imwrite_unicode`) vào `templates/`, hoặc nhờ người dùng cắt bằng nút ✂ trên UI.
  Chạy `python tests/test_logic.py`; logic mới không tầm thường → thêm 1 test vào đó.
  Ghi 1 dòng `(dd/mm) ...` vào `KINH_NGHIEM.md` mục lỗi tương ứng.
- Fix trong `custom.py`/`templates/` có hiệu lực từ nhân vật kế (xác nhận bằng dòng `Nạp lại custom.py` trong log;
  thấy `Nạp lại custom.py lỗi` = code mới hỏng, sửa ngay). Fix trong `nthbot/*.py`/`tasks/*.yaml` → luật 1.

## Bước 4 — làm lại cho chỉn chu

Tool đang chạy đọc lại `accounts.yaml` mỗi lần lấy acc → đổi trạng thái là tool tự làm lại, **không cần tắt tool**.
Sửa bằng hàm trong `nthbot/accounts.py` (có lock), không sửa tay file khi tool đang chạy:
```bash
PYTHONIOENCODING=utf-8 python -c "from nthbot import accounts; accounts.set_status('<user>', '')"
```
- **Acc ✗ lỗi do tool** (không phải lỗi dữ liệu) → `set_status(user, '')`: giữ `nv_xong`, tool làm tiếp từ nhân vật dở.
- **Nhân vật ⚠** (acc xong nhưng phiếu có bước `failed`) → đọc `doi_tk_zing` / `_chon_tu_duoi` / `doi_acc` trong
  `custom.py` trước: thứ tự nhân vật đổi theo lần chơi gần nhất và tk mà "dòng cuối đã làm hôm nay" bị coi là xong
  hết, nên reset `nv_xong` bừa sẽ chọn nhầm nhân vật hoặc bị ✓ luôn. Chưa có cách làm lại 1 nhân vật an toàn thì
  báo người dùng nhân vật nào thiếu bước gì, đề xuất cách (cần code thêm) và **hỏi trước khi làm**.
- Bước lỗi lặt vặt mà task tự bỏ qua được (vd Mộng Hoa Lục không like được) → ghi vào báo cáo cuối, không làm lại.

## Kết thúc

Khi log có `kho acc không còn` / `Báo cáo:`: đọc `logs/bao_cao_<ngày>.md`, tóm tắt cho người dùng: acc ✓, acc ✗ (lý do),
nhân vật ⚠ còn thiếu gì, code đã sửa gì (chưa có hiệu lực thì nói rõ). Tool tự dừng + tắt LDPlayer; không tắt UI.
