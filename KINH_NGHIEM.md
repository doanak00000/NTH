# KINH NGHIỆM — NTH Bot (Nghịch Thủy Hàn trên LDPlayer)

Tổng hợp toàn bộ kinh nghiệm làm tool (phiên 18/10/2026, cập nhật 19–20/10). Đọc file này là đủ để dùng, sửa và debug tiếp.
Màn hình game đo ở **960x540** (LDPlayer14). Mọi toạ độ bên dưới theo độ phân giải này.

---

## 1. Tool làm gì

Task duy nhất: `tasks/thanh_nhai_thu_6acc.yaml` (`repeat: 0`). Trên UI: tick instance → **▶ Start**.

1. Instance LDPlayer đang tắt → tool tự bật (`BotRunner._bat_ldplayer`), chờ Android boot.
   (20/10) Chưa acc nào tới giờ mà còn acc hẹn giờ → **chưa bật LDPlayer** (đang bật thì tắt), 3 phút trước giờ hẹn
   mới bật (`BotRunner._cho_gio_hen`) — đỡ tốn RAM cả buổi.
2. `khoi_dong_game`: mở game nếu chưa mở, chờ qua loading tới 1 màn đã biết (đóng banner/trang lạ trên đường).
3. `nhan_acc`: lấy acc **chưa chạy** trong kho "Tài khoản Zing" → đăng xuất → đăng nhập → **cuộn xuống chọn dòng cuối**.
   Acc đang dở (vd 3/6) → bắt đầu từ nv4, bỏ qua nv đã xong. Tk đã làm hết nhân vật hôm nay → ✓ luôn, lấy tk khác.
4. Mỗi nhân vật: chờ 3s + dọn màn hình → chụp ảnh → Mộng Hoa Lục (like/unlike) → Hảo Cảm (tặng quà) → Du Ngoạn (hộp quà)
   → **chế tơ** → Thanh Nhai Thư (roll + nhận ô + 4 mốc) → **chế tơ lần 2** → **treo bán tơ** → đổi nhân vật.
5. Xong nhân vật: ghi tiến độ + tên nhân vật vào kho. Hết 6 nhân vật → acc ✓ → (20/10) **khởi động lại LDPlayer**
   (giải phóng RAM) nếu còn acc chạy được ngay; acc kế hẹn giờ > 10 phút nữa → tắt LDPlayer, bật lại sát giờ.
   (23/10) Acc kế hẹn ≤ 10 phút cũng khởi động lại LDPlayer (4 acc liền không khởi động lại → LDPlayer 55GB, hết RAM).
   Kho hết acc → tự dừng + tắt LDPlayer.

**Thời gian** (sau tối ưu): nhân vật mới ~7 phút (treo bán ~18s/ô), nhân vật đã làm ~3,5 phút, đổi nhân vật ~45–50s,
đăng nhập ~1,5–2 phút. 1 acc 6 nhân vật mới ~45 phút. Phần lớn còn lại là game tự load.

---

## 2. Dùng tool (UI)

- **Kho tài khoản Zing** (cột trái): + Thêm / − Xoá / ▲▼ thứ tự / ↺ Reset trạng thái / 💾 Lưu.
  - Cột **Chọn**: chỉ acc được tick mới được các máy lấy để chạy (bỏ tick = tạm gác acc, giữ nguyên tiến độ).
  - Cột **Rút ví**: tick = lúc treo bán bot bấm "Rút vào ví"; bỏ tick = để người chơi tự vào rút.
  - Cột **Trạng thái**: trống / ▶ đang chạy x/6 (máy) / ⏸ dở x/6 / ✓ xong / **⚠ xong x/6** / ✗ lỗi.
    x/6 đếm **LƯỢT chạy**, không phải số nhân vật khác nhau. ⚠ = tk bị đánh xong mà chưa đủ 6 lượt → kiểm tra tk đó.
    Rê chuột vào → danh sách **tên nhân vật** đã biết (✓ = xong hôm nay).
  - **Tự reset sau 5h sáng ngày kế tiếp** (✓ và dở → chưa chạy). ✗ lỗi giữ nguyên để người dùng xem.
    Nút Reset chỉ cần khi muốn chạy lại trong ngày.
- **Giãn cách treo tơ**: Treo liền / **30s (mặc định từ 19/10)** / 40s / 45s / 1 / 3 / 5 phút — chờ giữa 2 lần treo 1 ô.
- **Tiến độ tài khoản** (ô chữ vàng): mỗi máy 1 khối "Tài khoản X" + "Nhân vật N (tên) đã hoàn thành ✓";
  sang acc mới thì khối của máy đó xoá và bắt đầu lại.
- Tên máy hiển thị dạng `[0] LD`.
- Log đầy đủ: `logs/<ngày>.log`. Lỗi → `logs/loi_<giờ>.md` (Claude chẩn đoán) + `logs/loi_<giờ>.png`.
- Chạy không UI (debug): `python run_cli.py --task thanh_nhai_thu_6acc.yaml`. **Bảng log trên UI chỉ hiện bot do
  chính UI Start** — chạy bằng CLI thì xem cửa sổ CLI hoặc file log. Đừng chạy CLI và Start UI cùng lúc (tranh LDPlayer).
- Mở UI + tự Start luôn: `python run.py --start` (tick mọi instance + Start task đang chọn).
- (23/10) Bấm Start khi máy đang chạy từng tạo THÊM bot (bot cũ mất khỏi danh sách, Stop không dừng được → 3 bot tranh
  1 LDPlayer, bot chờ giờ hẹn tắt LDPlayer của bot kia). Giờ UI bỏ qua máy đang chạy.

---

## 3. File quan trọng

| File | Vai trò |
|---|---|
| `custom.py` | Toàn bộ logic game: `doi_tk_zing`, `nhan_acc`, `doi_acc`, `che_to`, `treo_to`, `dong_banner`, `_tim_nut_x(_hinh)`, `_hoi_claude_nut_x`, `nhan_moc_hoat_dong`, `roll_thanh_nhai_thu`, `mo_hoat_dong`, `khoi_dong_game`, `_doc_ten_nv`... |
| `tasks/thanh_nhai_thu_6acc.yaml` | Thứ tự bước + sleep cho các bước bấm toạ độ cố định + toạ độ slot nhân vật |
| `nthbot/accounts.py` | Kho acc (`accounts.yaml`): claim có lock (2 máy không lấy trùng), tiến độ, reset 5h sáng |
| `accounts.yaml` | tk/mk/trạng thái/tiến độ/rút ví/tên nhân vật. **Mật khẩu chữ thường — đã .gitignore** |
| `nthbot/bot.py` | Vòng repeat, tự bật LDPlayer, watchdog, log ra file, chẩn đoán lỗi bằng Claude |
| `nthbot/engine.py` | Chạy từng bước YAML; bước lỗi → đóng banner (mẫu/Claude) rồi làm lại |
| `nthbot/ui/app.py` | UI |
| `templates/` | Ảnh mẫu. Nút X banner mới: lưu tên `x_*.png` là bot tự dùng |
| `tessdata/` | Gói OCR tiếng Việt (`vie`) + `eng` cho đọc tên nhân vật |
| `banner_moi/` | Ảnh banner lạ Claude đã xử lý → cắt nút X thành `x_*.png` |

---

## 4. Bài học về GAME (quan trọng nhất)

### Đăng nhập / đổi acc Zing
- Đổi acc Zing: màn chính → Hoạt động → Cài đặt → "Giao diện đăng nhập: Đến" (440,215) → Xác nhận
  → **màn server** → icon người góc phải trên (`dang_xuat_zing.png`, 929,28) = đăng xuất Zing ngay, không hỏi.
- Form VNG: `chon_zing_id` → form ZingID (`form_zing`) → ô tk (480,212), ô mk (480,260) → Đăng nhập.
- **Bấm ZingID có thể TỰ ĐĂNG NHẬP tk lần trước** (vào thẳng màn server) → đăng xuất rồi thử lại.
- Tk mới lần đầu trên máy → popup điều khoản (tick + Đồng ý) — bot tự làm.
- **Banner hay bật ngay sau khi bấm Xông Pha ở màn server**, đóng xong có thể bị trả về màn server →
  `doi_tk_zing` bước sau đăng nhập là **vòng xử lý theo màn hình**: server → Xông Pha, banner → X,
  điều khoản → đồng ý, tới khi thấy danh sách nhân vật (tối đa 180s).
- (19/10) **Đóng banner xong game có thể VÀO THẲNG màn chính, bỏ qua màn chọn nhân vật** → vòng chờ cũ chỉ chờ
  màn nhân vật nên đứng 3 phút, bấm nhầm "X" trên màn chính rồi lỗi. Giờ vòng chờ thấy `thanh_nhai_thu.png`
  (góc phải trên) là coi như đã vào game, đi tiếp với nhân vật game tự chọn.
- Từ màn chọn nhân vật bấm back → "Xác nhận đăng nhập lại?" → Xác nhận → về màn server.
- Màn server và màn nhân vật **đều có chữ "Xông Pha Giang Hồ"** → phân biệt bằng vùng tìm (giữa vs phải-dưới).
- `input text` gõ được mật khẩu có `!@'$` (đã escape), **không gõ được chữ tiếng Việt có dấu**.

### Danh sách nhân vật
- **Game xếp nhân vật chơi gần nhất lên ĐẦU, gần nhì thứ 2...** (cả lúc đăng nhập lẫn đổi trong game).
- (20/10) Vì vậy **mọi lần chọn nhân vật = cuộn xuống đáy + bấm dòng cuối (119,322)** (`_chon_tu_duoi`): dòng cuối
  luôn là nhân vật lâu chưa chơi nhất → 6 lần là đủ 6, **không cần đọc đúng tên**. Kiểm tra bằng ẢNH, không OCR:
  cuộn xong vùng list (40,80,290,320) phải đổi (cuộn ăn lệch ~28, hụt <3, nhiễu ≤9 → ngưỡng 15); bấm xong ô tên
  (700,398,130,24) phải đổi (đổi nhân vật 37–62, không đổi <5 → ngưỡng 15). Hụt → làm lại tối đa 3 lần.
  - Dòng cuối là nhân vật **đã làm hôm nay** (tên trong kho) → kéo list về đầu, dò tên dòng 2–6 tìm nhân vật chưa
    làm (nhân vật làm DỞ đã nhảy lên trên, vd Miêu My doangia1608 20/10); không còn → tk ✓.
  - List không cuộn được (tk ít nhân vật) / bấm không đổi → dự phòng chọn theo tên (`_chon_theo_ten`).
  - (23/10) Tk **1 nhân vật**: bấm dòng nào tên cũng không đổi → cũ coi cả dòng 1 là "trống" → ✓ sai (1 tk private
    bỏ 2 ngày). Dòng 1 luôn có nhân vật → không bao giờ coi là trống.
  - Dừng tk khi đủ 6 lượt (đếm lượt). Bỏ dở 1 nhân vật giữa chừng thì nó KHÔNG được đếm.
- Toạ độ dòng đo trên acc 6 nhân vật: chưa cuộn y≈115 / 201 / 288 / 369 (dòng 4 chỉ hiện 1 phần 358–381);
  sau 1 lần cuộn: 152 / 240 / 320.
- **Bấm nhân vật quá sớm → game nhận tạm rồi ~3,5s sau tự quay về chọn dòng 1** (danh sách còn chạy hiệu ứng)
  → Xông Pha vào lại nhân vật cũ. Đo được: bấm 0,6s sau khi danh sách hiện → bị ghi đè; bấm 4,4s → ăn.
  Cách làm (user chốt): **chờ 4s sau khi danh sách hiện → bấm dòng → đợi 2s → bấm Xông Pha**
  (`_bam_xong_pha` bấm lại nếu 6s sau vẫn ở màn danh sách). Không kiểm tra màu dòng.
- `ve_man_hinh_chinh` KHÔNG được bấm back ở màn chọn nhân vật (back = popup "đăng nhập lại?").
- List nhân vật **bỏ qua `input swipe`** → cuộn bằng `keo_that` (sendevent thẳng vào /dev/input/event4 "input").
  (20/10) **Phải gửi `ABS_MT_SLOT 0` + `ABS_MT_PRESSURE 1` + tracking ID MỚI mỗi lần** (thiết bị có 002f slot, 003a
  pressure). Thiếu → game lúc nhận lúc không, hầu hết KHÔNG nhận → 2 nhân vật khuất dòng 5–6 không bao giờ được chạy,
  mỗi tk chỉ làm 4 nhân vật thật (+1 làm lại). Có đủ 3 thứ: ăn 10/10 cả kéo lên lẫn xuống. Kéo ở cột list (x=152).
- Tên nhân vật: OCR **ô tên góc phải dưới** (700,398,130,24) bằng tesseract `vie`. Ô này có **nét bút trang trí bên
  phải** → OCR đọc thành rác cuối tên ('La Xuân -z', 'Hoa Phii', 'TùHy TháiHậu ˆ'). (20/10) Thân chữ trắng tinh
  (≥190), nét bút/nền tối hơn → lấy cụm cột trắng lớn nhất làm vùng chữ, xoá phần ngoài, đọc ảnh Otsu (giữ dấu) +
  lề trắng 20px: 12 tên thật 7/12 → 10/12 (bỏ dấu 11/12). Ngưỡng cố định thay Otsu thì sạch rác nhưng MẤT DẤU.
  `tessdata_best` vie (12MB) KHÔNG tốt hơn bản fast đang dùng. Vẫn sai giữa chữ ('LoveU'→'LowU'/'LoeU').
- Đổi nhân vật: Cài đặt → "Chuyển đổi nhân vật" (846,147) → Xác nhận (KHÔNG phải nút đổi tài khoản).
- Vào nhân vật xong game hay bật **trễ ~3s** trang "Giang Hồ - Nội Dung Mới" (chỉ có nút back) → đầu mỗi nhân vật
  chờ 3s rồi `ve_man_hinh_chinh`.

### Bảng Hoạt động
- Mở bằng toạ độ (920,31). **Game hay bỏ qua lần bấm đầu** → `mo_hoat_dong` kiểm tra thấy `cai_dat.png`, chưa thì bấm lại.
- Nút ✕ thu bảng Hoạt động (917,28) **giống nút X quảng cáo** → `_tim_nut_x` bỏ qua nó khi bảng đang mở.

### Nhiệm vụ nhỏ
- Mộng Hoa Lục: **dùng toạ độ**, không dùng icon (icon trong suốt, thời tiết đổi là lệch): xã giao (319,498) →
  tab (30,122) → like/unlike (262,292) ×2 → thu (632,240).
- Hảo Cảm: **hảo cảm đã đầy** → popup "phần dư quy đổi sang Ngọc Tri Tâm, tiếp tục tặng?" → Xác Nhận. Chỉ 1 số nhân vật có.
- Du Ngoạn: Hoạt động → (595,285) → hộp quà (715,445) → đóng (480,450) → thoát (45,30).
- Chụp ảnh / hảo cảm để `required: false` → lỗi thì bỏ qua làm tiếp, không dừng cả task.
- Chụp ảnh (`chup_anh`): icon máy ảnh (33,506) → chụp (854,462) → **nút X vàng góc phải trên** (`xong_chup_anh.png`
  ~863,57; KHÔNG có nút chữ "Xong") hiện ~2s sau khi chụp → bấm X → thoát (34,25). (20/10) Game đôi khi bỏ qua lần bấm
  chụp (6 lần/2 ngày, TrânCẩm chờ 20s không thấy X → hụt nhiệm vụ → Thanh Nhai Thư 3/4) → 8s chưa thấy X thì chụp lại
  (tối đa 3). (21/10, có ảnh) có lúc game bỏ qua cả lần bấm **icon máy ảnh** → bot bấm "chụp" trên màn chính
  (854,462 = vùng nút đánh) → giờ mỗi lần chụp lại kiểm tra: icon máy ảnh còn trên màn = chưa vào chế độ chụp →
  bấm lại icon trước.
- Mộng Hoa Lục (`mong_hoa_luc`, 20/10): xã giao (319,498) → tab (30,122) toạ độ cố định; **nút like** dò bằng ảnh
  (`like_da.png` xanh/1, `like_chua.png` xám/0, trên trang ≥0.95, màn khác ≤0.57); bấm 2 lần (1 like + 1 unlike — lúc
  đầu đã like hay chưa đều được), mỗi lần vùng nút phải đổi (lệch 28–99, đứng yên 0). Hụt → bấm lại / mở lại.
- Hảo Cảm (`hao_cam`, 21/10 chuyển từ YAML sang hàm để Thanh Nhai Thư gọi lại được khi sót).
- Lần đầu mở nghề lạ (vd Câu Cá) có popup "Nhắc nhở" → **Hủy Bỏ**, đừng nhận.

### Chế tơ
- Nghề nghiệp → icon **Thiết Kế** (663,488) (KHÔNG phải (293,488) chế tác). Chờ thấy `thiet_ke_icon.png` vì trang load chậm.
  (23/10) Icon lúc có lúc không **chấm đỏ thông báo** góc phải trên → mẫu cũ có chấm chỉ khớp 0.64 khi không có
  (kẹt 20s, Claude cứu). Mẫu giờ cắt lõi 24x24 bỏ góc chấm: không chấm 1.0, có chấm 0.96, icon khác ≤0.55.
- Công thức: **Tơ Phiêu Vân-2 dòng thứ 3** (245,212) — toạ độ, vì dòng 1 thường được chọn sẵn.
- Đá vàng (Diệu Tinh Thạch) ở (525,322). Tap đầu đôi khi bị bỏ qua → thử lại 3 lần.
- 1 lần chế = 5 hoạt lực. Số lần = hoạt lực // 5; **chỉ mua phần thiếu** = số lần − số đá đang có; `^` (617,422) = tối đa → Chế Tạo.
- **Chỉ mua khi giá lô rẻ nhất ≤ 83** (OCR (277,120,40,22)). Đắt hơn → chỉ chế bằng đá đang có.
- Hoạt lực **có thể vượt tối đa** (vd 1565/1500).
- (20/10) OCR hoạt lực đôi lúc trượt 1 lần dù số rõ ('311/1500') → đọc lại tối đa 4 lần (cách 1,5s) rồi mới báo lỗi.
- (20/10) **Túi đầy** → bấm Chế Tạo hiện "Túi không đủ chỗ trống, không thể hoàn thành công thức này", hoạt lực không
  giảm. Trước đây bot bấm 3 lần + chế tơ lần 2 còn mua thêm đá vô ích (tk test3). Giờ: bấm xong mà hoạt lực không giảm
  → phiếu `nghề nghiệp: failed` + ảnh, dừng; chế tơ lần 2 của nhân vật đó bỏ qua (vẫn mở trang chế cho treo_to).
  Đá vẫn bị mua ở lần 1 (chưa biết túi đầy trước khi chế). Cần người dùng dọn túi.
- (20/10) **Bẫy làm lại bước**: bước `che_to` lỗi được làm lại khi đang ở trang Nghề Nghiệp → bấm (920,31) "nút Hoạt
  động" thì ở trang đó lại là **số hoạt lực** → bật tooltip "Hoạt Lực", không mở được bảng Hoạt động → bỏ cả tk
  (doangia1608). `_mo_trang_che` giờ `ve_man_hinh_chinh` trước. Hàm nào bắt đầu bằng toạ độ màn chính nên về màn chính trước.

### Mua / bán ở chợ (đường vòng — KHÔNG bấm icon Kỳ Trân vì icon hay đổi chỗ)
- Trang chế → bấm đá vàng → dòng "Cách nhận" → mũi tên cuối dòng → dropdown → **Khu Giao Dịch**.
- Mua: ô số lượng (770,368) mở **bàn phím số riêng của game**: 1(741,141) 2(796,141) 3(851,141) 4(741,197) 5(796,197)
  6(851,197) 7(741,252) 8(796,252) 9(851,252) 0(796,307), Hoàn tác (741,307), Xác nhận (851,307). Chữ số gõ nối tiếp.
  Mua xong "Chúc Mừng Nhận" → bấm (480,450).
- Bán: ở Khu Giao Dịch bấm "Gian Hàng Chợ" (55,104) để **thu dropdown** → "Vật Phẩm Bán".
  Bàn phím số ở bảng bán **thấp hơn bên mua 174px**. Ô số lượng bán (770,261).
- Kệ có **8 ô**, chỉ thấy 6 → cuộn (`keo_that` 720,330→720,130) xem 2 ô khuất.
- Tơ hết hạn: nhãn "Hết hạn giao dịch" (`het_han.png`) → nút Gỡ bên phải cùng hàng (+90px). Tơ còn hạn để yên.
- Treo: **599/ô**, bấm "−" đơn giá **15 lần** = chạm sàn −50% (min giá). Rút vào ví chỉ khi acc tick "Rút ví".
- Thứ tự treo (`treo_to` tham số `hang`): **Thanh Phong Tán-Hạ → Hồi Sinh Tán-Hạ (mỗi loại 1 ô) → tơ**. Bản Thượng
  KHÔNG treo. Mẫu `thanh_phong_tan.png` / `hoi_sinh_tan.png` khớp cả Hạ lẫn Thượng (cùng icon) → `_tim_thuoc_ha`
  phân biệt bằng màu nền góc trên-trái ô: Thượng xanh dương (B−R ≈ 39), Hạ xám (≈ 8), ngưỡng 20. Thuốc: nút ^ tối đa số lượng (914,261);
  tơ: gõ 599. Cùng giá sàn.

### Màn chờ
- Để game im **~1,5–2 phút** (kể cả đang ở bảng Giao Dịch) → game nhả **màn chờ** (rừng tre + người cưỡi ngựa, không có nút).
  Chạm bất kỳ đâu là mất, game **trả về đúng trang đang mở**. Mẫu `man_cho.png` (khớp 1.0, màn thường 0.50).
- `_tim_nut_x` coi màn chờ như banner → mọi vòng chờ ảnh / `dong_banner` tự thoát. `treo_to` kiểm tra sau mỗi lần giãn cách.
  `ve_man_hinh_chinh`: không thấy nút back → `dong_banner` → đóng được thì dò lại (màn chờ che nút back).
- Kệ đầy → thông báo thoáng qua "Cửa hàng của bạn không có ô hiệu lực để lên kệ" (`ke_day.png`) — **đầy là bình thường**.

### Thanh Nhai Thư
- 5 ô Đề Cử: ô đã làm hiện chữ **"Nhận"** → bấm để cộng điểm. Ô **đã nhận (dấu tích) mà bấm → game chuyển sang
  hoạt động đó** (vd mở trang Nghề Nghiệp) → chỉ bấm khi thấy `o_nhan.png`.
- Có điểm mới nhận được mốc: hàng dưới "Tiến Độ Hoạt Động Ngày" 4 mốc tại x = 205, 278, 350, 424 (y 488).
  Mỗi mốc cho Ngân Phiếu + **hoạt lực** → vì vậy có "chế tơ lần 2".
- Trang Thanh Nhai Thư có **nút back màu vàng** (`nut_dong_vang.png`), các trang khác màu xanh.
- Có nhân vật không bao giờ roll đủ 4 ô (bình thường).
- (20/10) Game hay **bỏ qua lần bấm mở** icon Thanh Nhai Thư (920,131) → bot roll trên màn chính, 0 ô, bỏ cả TNT
  (2/111 lần; DoanMyy doangia1608). `_mo_tnt` chờ nút back vàng, chưa thấy thì bấm lại icon (3 lần).
- (21/10) **Nhận diện ô Đề Cử → làm lại nhiệm vụ sót.** 5 ô ở x = 296/416/536/656/776 (rộng 113, y 285–430). Mỗi ô
  3 trạng thái: **chưa làm** = ô sáng (độ sáng ~180) + dòng mô tả + **nút roll** góc trên phải; **xong chưa nhận** = ô
  trắng (~240) chữ "Nhận" to, không nút roll; **đã nhận** = ô tối (~125) dấu tích to. Tiêu đề (ô y 40–60) mẫu
  `templates/tnt_{chup_anh,mong_hoa_luc,hao_cam,nghe_nghiep}.png`: khớp ≥0.90 ở cả 3 trạng thái, nhiệm vụ khác ≤0.60
  (ngưỡng 0.8). Nút roll ≥0.82, ô khác ≤0.35 (ngưỡng 0.6). `o_nhan.png` chỉ khớp 0.33 → không dùng.
  `roll_thanh_nhai_thu` mỗi vòng: 1 trong 4 nhiệm vụ bot tự làm mà ô vẫn CHƯA LÀM = đã sót → `_lam_lai_nv_tnt`: về màn
  chính, gọi lại `chup_anh` / `mong_hoa_luc` / `hao_cam` / `che_to`, mở lại TNT, nhận (mỗi nhiệm vụ 1 lần/nhân vật;
  thời gian làm lại không tính vào hạn 180s). Phiếu ghi `làm lại <nhiệm vụ>: 1`. Đã chạy thật 21/10 (KhâuSơnTùng
  tk test1, gọi roll TRƯỚC khi làm gì): tự làm lại cả 4 rồi nhận 4/4. Thử nhận diện trên 56 ô thật × 5 vị trí: đúng hết.
  Các nhiệm vụ khác trong Đề Cử (Cốt Truyện, Thi Đấu, Phó Bản, Trang Viên, Tiệc Trang Viên, Hoạt Động Bang, Thám Hiểm,
  Du Ngoạn) bot không làm → roll đi như cũ. Ảnh mẫu đã gom: `debug_tnt/` (tk test1 21/10), `debug_tnt_20_10/`.

### Popup / banner
- **Bot đứng im lâu = gần như chắc chắn đang bị banner/popup che.** Mọi lần "đứng im" trong phiên đều là banner/popup:
  Thám Vực, banner sinh nhật X trắng, ưu đãi nạp lần đầu, hảo cảm đầy, Câu Cá, trang Nội Dung Mới.
- Nút X mỗi banner 1 chỗ 1 cỡ → dò nhiều mẫu X ở nhiều tỉ lệ (`dong_update`, `dong_thong_bao`, `dong_quang_cao`, `x_*.png`).
- **Nút X trắng trong suốt**: nền banner đổi màu → so ảnh màu tụt ~0.7 → `_tim_nut_x_hinh` so **HÌNH DẠNG** nét trắng
  (gray > 200) ở góc trên-phải (740,0,220,160), ngưỡng 0.87 (banner ≥ 0.89, màn thường ≤ 0.82).
- Không mẫu nào khớp → **hỏi Claude** (`_hoi_claude_nut_x`, `claude -p` dùng subscription local): trả `X,Y` hoặc `NONE`,
  ~8s. Đúng trên mọi banner thật đã thử, trả NONE cho màn chính / bảng bán (prompt dặn "trang chức năng không tính").

---

## 5. Chống kẹt & báo lỗi

1. Mọi vòng chờ ảnh (`_cho_qua_popup`, dò mỗi 1s) + mỗi lần về màn chính: dò + đóng banner bằng mẫu X.
2. Chờ ảnh **quá 30s** mà không mẫu X nào khớp → tự hỏi Claude 1 lần.
3. `engine.run_steps`: bước báo lỗi → `dong_banner(hoi_claude=True)`; đóng được thì làm lại bước (tối đa 2 lần).
4. Watchdog (`BotRunner._watchdog`): **90s không có log mới** (trừ lúc cố ý `sleep >= 10s`) → `dong_banner(hoi_claude=True)`.
5. **Task lỗi → Claude chẩn đoán** (`BotRunner._chan_doan_loi`): chụp màn + log cuối → `claude -p` (CHỈ ĐỌC: Read/Glob/Grep)
   → `logs/loi_<giờ>.md` nêu nguyên nhân + cách sửa (file/dòng). Chạy êm thì **không gọi Claude, không tốn token**.
   Claude **không tự sửa code** lúc không có người xem — đọc file chẩn đoán rồi bảo Claude Code sửa.
- "Màn hình đứng im" **KHÔNG dùng được** làm dấu hiệu kẹt: màn chính / màn đăng nhập luôn có cảnh động
  (chênh 33–68 điểm giữa 2 ảnh cách 10s dù không bấm gì).

---

## 6. Bài học về KỸ THUẬT

- (19/10) `run.py`/`run.bat` chạy bằng **Python hệ thống**, không phải `.venv` → thiếu `pytesseract` thì `che_to` lỗi
  "OCR cần: pip install pytesseract" (OCR tên nhân vật ra "?" là dấu hiệu sớm). Đã cài vào Python hệ thống +
  bỏ comment dòng `pytesseract` trong `requirements.txt` (OCR là bắt buộc).
- (19/10) Mọi `ctx.sleep` (cả `sleep:`/`after:` YAML) tự cộng ngẫu nhiên 0–10% (19/10 hạ từ 20%) (`engine.py`) để nhịp không cố định.
  Chỉ cộng, không trừ: nhiều chỗ cần chờ tối thiểu.
- (19/10) **Web xu** https://doanak00000.github.io/nth-xu/ (repo `nth-xu`, clone ở `xu_web/`, đã gitignore).
  `treo_to` -> `_ghi_xu` ở trang Vật Phẩm Bán, TRƯỚC khi rút ví: OCR xu (688,8,66,26; game viết tắt "1.049M")
  + "Lợi ích" chưa rút (644,426,80,18; vùng cũ 650,424,80,22 không đọc được số 0 lẻ) -> `nthbot/xu.py` ghi `xu_web/xu.json` (3 ngày gần nhất) -> git push nền.
  Ghép tên trùng bằng `xu._chuan` (bỏ dấu tiếng Việt, ký tự lạ, dấu cách, hoa/thường): OCR ô tên vẫn lệch dấu
  ('NhiếpUyển'/'NhiếpUyến') hoặc dính ký tự ('TrânCẩmˆ') giữa các lượt.
  Khoá nhân vật theo **tên OCR**, không theo số thứ tự: list nhân vật xếp theo lần chơi gần nhất (dòng 1 =
  nhân vật chơi cuối) nên nv1..6 đổi mỗi ngày. Tên tk Zing hiện đầy đủ (chủ tool muốn vậy).
  OCR rỗng cả 2 số (màn chờ che) -> không ghi. Push lỗi chỉ log "xu: push GitHub lỗi".
- (19/10 23:19) **LDPlayer rò bộ nhớ**: chạy ~11 tiếng liền, `Ld9BoxHeadless` commit ~52 GB -> commit Windows còn
  0,3 GB -> adb server chết ("daemon not running... connection reset"), Python mới lỗi OpenBLAS cấp phát bộ nhớ.
  Tắt LDPlayer (`ldconsole quit --index 0`) -> trống lại 22 GB; Start tool tự bật lại. (20/10) Bot chạy xong
  ("Hoàn tất") tự tắt LDPlayer của máy đó (`BotRunner._tat_ldplayer`). (20/10) Giờ còn tự khởi động lại LDPlayer sau
  MỖI tk (`khoi_dong_lai_ldplayer`, ~1,5 phút) và tắt lúc chờ giờ hẹn (xem mục 1). Lỗi adb giờ được chờ 5s + nối lại + làm lại bước (tối đa 3 lần) trước khi tính là lỗi tk
  (trước đó bị bỏ qua oan myxinh1011).
- (19/10) **Claude cứu lỗi (tầng 1, người dùng chọn)**: bước lỗi (đã thử đóng banner) -> `ctx.cuu_loi` ->
  `BotRunner._claude_cuu`: chụp màn + log -> `claude -p` (chỉ Read/Grep, KHÔNG sửa file) chọn 1 thao tác:
  `BAM x y` / `VE_MAN_CHINH` / `MO_LAI_GAME` (mở lại + đăng nhập lại đúng tk) / `LAM_LAI` / `BO_QUA` (dòng cuối câu
  trả lời) -> bot làm rồi làm lại bước; tối đa 2 lần/bước, 8 lần hỏi/lượt. Vẫn lỗi -> `BoQuaAcc`: tk đang làm thành
  ✗ lỗi, sang tk kế (không dừng máy); bỏ qua 3 tk liên tiếp -> dừng máy (lỗi hệ thống). Sai mật khẩu không hỏi Claude.
  Báo cáo mỗi lần ở `logs/cuu_*.md` + ảnh. Lần thật đầu (19/10 23:08): popup "Xác nhận đăng nhập lại sao?" treo
  sau khi tắt tool giữa lúc đổi tk -> Claude bảo BAM (867,268) = nút Xác Nhận -> qua được (~15s). Đã thêm
  xac_nhan vào popup của `khoi_dong_game` để lần sau khỏi cần Claude. Watchdog đứng yên lúc chờ Claude (`dang_cuu`). Tầng 2 (Claude tự sửa
  code) KHÔNG làm: người dùng đổi ý chọn tầng 1.
- (19/10) Sai mật khẩu ZingID: SDK vẫn về màn server, bấm Xông Pha thì VNG hiện popup "Đăng nhập thất bại...
  [7020-13]" -> trước đây bot bấm Xông Pha sau popup 3 phút rồi mới lỗi. Giờ thấy `dn_that_bai.png` -> bấm OK, báo
  lỗi ngay (acc thành ✗ lỗi, nhan_acc bỏ qua). Gặp: myxinh1608 (mật khẩu trong kho sai).
- (20/10) So tên **gần đúng** dùng chung 1 luật `xu.cung` (trên `xu._chuan`) cho cả chọn nhân vật lẫn web: giống
  >= **0.85** HOẶC đoạn chung dài nhất >= 85% tên ngắn hơn. Ngưỡng cũ 0.9 làm 'KRIXI'->'KRXI' (0.89),
  'NhưƠïnhY'->'NhữDinhY' bị tưởng nhân vật mới -> **làm lại lần 2** (cùng xu 755K). Chỉ so trong 1 tk; khác người
  trong cùng tk gần nhất đo được: MissU/KissU 0.80 (TRiệu Vân/TriểuHân 0.875 là 2 tk khác nhau, không đụng nhau).
  Thử trên toàn bộ tên thật của các tk: mọi cặp >= 0.85 đều là biến thể OCR của cùng 1 tên.
- (19/10, thay 20/10) Cả NHÂN VẬT ĐẦU (vừa đăng nhập) cũng chọn dòng cuối (`nhan_acc tu_duoi: true` -> `doi_tk_zing`
  -> `_chon_tu_duoi`). Tk đã làm hết hôm nay (vd Reset rồi chạy lại) -> `doi_tk_zing` trả "het" -> `nhan_acc` ✓ tk,
  lấy tk khác (trước đây vào dòng 1 làm lại nhân vật đã xong). Cách chọn hiện tại: mục 4 "Danh sách nhân vật".
- (19/10) **Hẹn giờ chạy acc**: cột "Giờ" trên UI (trống = chạy ngay, mặc định). Kho lưu `gio` (HH:MM) + `gio_ngay`
  (ngày đặt/cập nhật). ~~+10 phút/ngày~~ (bỏ 19/10): bot xong **nhân vật 1** của acc hẹn giờ -> `accounts.dat_gio`
  đặt giờ hẹn = giờ xong đó + 3 phút (23/10 user chốt, trước +10) -> mai bắt đầu đúng lúc hàng treo hôm trước vừa hết hạn (vào sớm thì kệ còn đầy hàng chưa
  hết hạn, không treo được). Không chạy ngày nào thì giờ giữ nguyên; giờ trôi muộn dần -> người dùng gõ lại.
  UI: ô Giờ theo file (bot dời giờ); chỉ ô người dùng vừa gõ (`_DA_SUA`) mới được Lưu ghi đè. Xoá dấu `_DA_SUA`
  cũng phải `blockSignals` (self-check bắt được: không chặn thì mọi ô bị coi là "vừa sửa", giờ bot dời bị đè).
  `claim` chỉ lấy acc đã tới giờ, nhiều acc cùng sẵn sàng thì **public trước private**; không acc nào sẵn sàng mà còn acc hẹn chưa tới giờ -> `nhan_acc` chờ (sleep 30s/lần,
  rồi `khoi_dong_game` cho chắc) thay vì kết thúc task. Acc chạy lần lượt trên 1 máy; nhiều máy thì acc cùng giờ có
  thể chạy song song. Giờ hẹn trước 5h sáng: acc 'done' hôm trước chưa reset (reset lúc 5h) -> hôm đó không chạy.
- (19/10) Roll Thanh Nhai Thư tối đa **180s** (`max_giay`, người dùng chọn): hụt nhiệm vụ (vd chụp ảnh không xong)
  thì không bao giờ đủ 4 ô -> trước roll ~120 vòng (~8 phút). Giờ quá 180s thì thôi, nhận mốc rồi đi tiếp.
- **QUY TẮC ACC PRIVATE (bắt buộc):**
  - Acc người dùng nói là private -> LUÔN vào kho private (`private: true`). Không bao giờ quét xu, không đưa
    tên/tk/nhân vật/xu hay BẤT CỨ thông tin gì của acc private lên web (xu_web, GitHub), dù nút bật hay tắt.
  - **Không thêm/sửa acc private trong `accounts.yaml` khi tool đang chạy code CŨ** (UI mở trước khi có cờ
    `private`): code cũ ghi lại kho mỗi lần cập nhật tiến độ -> mất cờ `private` -> acc thành public, bị lấy chạy
    và đẩy xu lên web. Phải đợi bot dừng + mở lại UI (code mới) rồi mới thêm.
  - Mật khẩu chỉ nằm trong `accounts.yaml` (đã gitignore), không ghi vào file nào khác.
  - Trên UI + log: acc private chỉ hiện **"tk testN" / "mk testN"** (N = thứ tự trong kho private,
    `accounts.ten_hien`). Bảng private giữ giá trị thật trong `Qt.UserRole`; mọi chỗ đọc ô tk/mk phải qua
    `_gia_tri`. **Thao tác bảng (setItem / đổi dòng) phải `blockSignals`** — không thì itemChanged -> `_sua_o`
    lấy tên giả làm tk thật (self-check bắt được lỗi này ở nút ▲▼).
- (19/10) **Đăng nhập EMAIL** (tk có '@' -> `_dang_nhap_email`): form VNG -> "Phương thức khác" -> "Email" -> mở
  Chrome trang id.vnggames.app. Các màn có thể gặp (vòng xử lý theo màn hình, mẫu `web_*.png`, `chrome_khong_tk.png`):
  Chrome lần đầu hỏi tk Google -> "Use without an account"; "Chọn tài khoản đăng nhập" (list tk đã nhớ, chỉ ghi
  "User 0128..") -> LUÔN "Đăng nhập bằng tài khoản khác"; ô Email (672,128) -> Tiếp tục (672,194); trang mật khẩu
  hiện luôn mà chưa gõ email -> "Nhập lại email"; ô Mật khẩu (650,164) -> Đăng nhập (672,231) -> về game (popup
  điều khoản như ZingID). Đóng Chrome giữa chừng -> game báo "bỏ qua đăng nhập bằng Email [7002-13]" -> OK.
  Đã chạy thật trọn luồng 19/10. Dò màn: KHÔNG bấm toạ độ mù trên trang Cài Đặt (từng bấm trúng nút Rung).
- (19/10) **Kho acc private**: cùng `accounts.yaml`, cờ `private: true`, bảng riêng trên UI chỉ hiện khi bấm
  nút "🧪 Chế độ thử nghiệm" (tên ngụy trang, dưới nút Cắt ảnh mẫu). Acc private chạy bình thường theo tick
  Chọn nhưng `_ghi_xu` **không bao giờ** ghi/đẩy gì lên web, dù nút bật hay tắt. Mỗi bảng lưu chỉ phần của
  mình và giữ nguyên phần kho kia.
- (19/10) Tên nhân vật OCR ở **ô tên góc phải dưới** màn chọn nhân vật (700,398,130,24), không đọc ở dòng trong list
  (dòng 4 hiện 1 phần -> mỗi lần 1 tên). Quét xu 19/10: cuộn hụt cả nv5, nv6 -> vào lại nv4, ghi trùng xu
  (gốc là `keo_that` thiếu SLOT/PRESSURE, sửa 20/10).
- (19/10) Banner "Nhất Niên Hồi Ức" (10–22/10) nút X trắng ở (754,105) không có mẫu -> kẹt đăng nhập 3 phút
  rồi lỗi. Đã thêm `templates/x_nhat_nien.png` (màn khác chỉ khớp ≤0.64). NHƯNG nút X trong suốt: nền game
  đổi (tím -> xanh tuyết) là mẫu X tụt 0.64, so hình dạng 0.43 -> trượt (23:22, kẹt 2 phút tới khi watchdog hỏi
  Claude). Cách chắc: nhận BANNER bằng mốc cố định trên ảnh banner (`moc_nhat_nien.png` = nút "Kể Chuyện Ngay!",
  2 nền đều 0.98, màn khác ≤0.40) rồi bấm X ở toạ độ biết trước — bảng `_MOC_BANNER` trong custom.py.
- (19/10) Gỡ đồ hết hạn ở kệ: ~1s/món (trước 3s), không dính giãn cách treo. Sau mỗi lần Gỡ chờ tới khi vùng kệ
  thay đổi (tối đa +3s) — kệ dồn lên chậm mà bấm tiếp ngay thì nút Gỡ có thể trúng ô CÒN HẠN.
- (19/10) `run_cli.py` chạy nền/redirect trên Windows bị `UnicodeEncodeError` cp1252 → đã `reconfigure(utf-8)`.
- **OCR**: Tesseract ở `C:\Program Files\Tesseract-OCR` + `pytesseract` trong `.venv`; tiếng Việt ở `tessdata/` (truyền
  `--tessdata-dir` KHÔNG bọc ngoặc kép — pytesseract giữ nguyên ngoặc → lỗi; đường dẫn không được có dấu cách).
  Đọc hoạt lực **bắt buộc có "/"**: chỉ đọc số thì "/" hay thành "2" ("101 /" → "1021") → từng mua dư đá.
- **Sleep cố định là nguồn chậm chính** → thay bằng "chờ tới khi thấy ảnh". Đổi nhân vật từ ~3 phút xuống ~45s.
  Bước bấm toạ độ cố định giữ tối thiểu 1,5–2,5s để chạy 3 LDPlayer vẫn kịp.
- Đo được: chụp màn ~0,3s, lệnh adb ~0,04s, dò banner đa tỉ lệ ~0,7s, hỏi Claude ~8s, Claude chẩn đoán ~35s.
- Bot đang chạy **dùng code nạp lúc Start**; `bot.py`/`engine.py`/UI chỉ nạp lúc mở app → sửa xong phải mở lại app.
- LDPlayer14 **không có `monkey`** → `launch_app` dùng `cmd package resolve-activity` + `am start`.
- ADB của instance phải bật (`basicSettings.adbDebug: 1` trong `vms/config/leidianN.config`).
- Game crash SIGILL trên LDPlayer từng gặp → cài lại game là hết.
- Bash heredoc chứa nhiều `'''` đôi khi lỗi "unexpected EOF" → ghi script Python ra file bằng công cụ Write rồi chạy.
- (22/10) **Web chỉnh giờ chạy acc public**: nút 🔑 trên web (GitHub token fine-grained, chỉ repo `nth-xu`, Contents read/write, lưu ở localStorage trình duyệt) -> web ghi `lenh.json` `{gio:{tk:{gio,id}}}` qua GitHub API. UI mở là `xu.nghe_lenh` chạy nền: 20s `git ls-remote`, repo có commit mới mới pull -> `xu.ap_lenh` đổi giờ (`accounts.dat_gio(ep=True)`), mỗi id áp 1 lần (lưu `logs/lenh_web.json`, không đè giờ bot tự dời), `trang_thai.json` có `gio` + `lenh` (id đã nhận) -> web hiện ✓/⏳. Tool tắt lúc đổi -> mở lên áp ngay. Acc private / giờ sai bị bỏ.
- (20/10) **Web xu: trạng thái chạy** — `accounts.save` -> `xu.ghi_trang_thai` ghi `xu_web/trang_thai.json` (chỉ acc
  public: st chay/do/xong/loi, nv, may, bat_dau) + push khi có thay đổi; trang hiện "▶ đang chạy x/6", "⚠ xong x/6"
  (đỏ)... Giờ bắt đầu vẫn ghi trong json nhưng trang đã ẩn (người dùng không muốn hiện). `git add` từng file riêng
  (file chưa có thì add lỗi, không kéo theo file kia).
- (20/10) **Web xu: biến thể tên** — mỗi nhân vật trong `xu.json` có `bien_the` = các kiểu OCR từng đọc sai tên nó
  ('DoRWA' của DoRy, 'LowU'/'LoeU' của LoveU). `_chon_ten` so cả biến thể; ghép gần đúng được thì tự thêm biến thể.
  OCR sai giữa chữ quá xa để `cung` nhận ra -> người dùng báo tên nào là 1 -> gộp tay 1 lần trên xu.json là đủ.
  Gộp tay: ngày trùng thì giữ bản ghi `luc` muộn hơn (lượt làm lại). Tên hiển thị = key, sửa key nếu dính rác.
- (20/10) OCR **tiền chưa rút** ("Lợi ích") hay ra '?' (21/80 lần): thường chỉ là số **0** một chữ số — phóng x3 Tesseract
  bỏ sót (1/4 ảnh đọc được), x5 đọc 4/4 → `_doc_so_ocr` x3 không ra chữ số thì thử x5.
- (20/10) `ve_man_hinh_chinh` hết nút đóng thì đã dò banner trong vòng lặp rồi còn dò lại sau vòng (~1,3s thừa/lần,
  ~10 lần/nhân vật). Giờ chỉ dò lại khi màn hình đổi rõ (`_man_doi`: lệch > 5; đứng yên ~1–2, popup bật > 10).
- (20/10) `doi_tk_zing` dò `vao_server` 1 lần trượt trên màn server → tưởng màn chính → bấm (918,21) = **icon đăng xuất
  Zing** → hỏng đăng nhập (maianh0000001 bị ✗ oan). Giờ chờ tối đa 8s mới kết luận là màn chính.
- (20/10) **RAM**: "máy thiếu bộ nhớ" là **commit** (RAM + pagefile) sát giới hạn (73,9/83,6 GB), không phải RAM thật.
  LDPlayer máy ảo 6GB giữ commit 29,5GB sau ~5 tiếng; **SignalRgb** (phần mềm đèn RGB) rò ~9,7GB — bấm X chỉ thu xuống
  khay, phải Exit/tắt tiến trình (tự bật cùng Windows `--silent`). vmmem (WSL/Docker) ~6GB.
- (20/10) **Bài học debug: đừng kết luận từ tương quan ít mẫu.** Thấy "chạy UI cuộn hụt, chạy CLI cuộn ăn (2/2)" →
  đổ cho preview UI chụp màn mỗi giây → sai; lượt CLI kế tiếp vẫn hụt 3/3. Thử thẳng trên máy (so ảnh trước/sau từng
  kiểu kéo) mới ra gốc (SLOT/PRESSURE). Tool chạy bằng UI vẫn cuộn bình thường.
- (20/10) Thanh tiến độ x/6 đếm lượt → lượt làm lại / bỏ dở che mất nhân vật bị sót. Rà lỗi theo từng nhân vật: parse
  log theo đoạn "nhận tk" … "Nhân vật N (tên) đã hoàn thành", kiểm "Thanh Nhai Thư: đã nhận x/4", "Tiến độ … x/4 mốc",
  "treo N lượt" ("treo 0" + "kệ đã đầy" là bình thường).
- Debug trên máy thật: script nhỏ tạo `Context` thật rồi gọi thẳng hàm trong `custom.py`; chụp `adb exec-out screencap -p`.

---

## 7. Còn dang dở / nên làm tiếp

1. ~~Roll Thanh Nhai Thư không đủ 4 ô~~ -> ĐÃ SỬA 19/10 (tối đa 180s) + 21/10: nhận diện ô Đề Cử, nhiệm vụ nào trong
   4 việc bot làm còn "chưa làm" thì về làm lại (mục 4 Thanh Nhai Thư). Còn: Du Ngoạn có trong Đề Cử nhưng chưa có
   mẫu/làm lại (bot vẫn làm Du Ngoạn bằng toạ độ, không kiểm tra).
2. ~~Acc ít hơn 6 nhân vật~~ -> ĐÃ SỬA 19/10, thay 20/10 bằng chọn dòng cuối + kiểm tra bằng ảnh (mục 4). Chưa gặp
   thật tk < 6 nhân vật với cách mới (nhánh dự phòng `_chon_theo_ten` mới test bằng ảnh giả).
3. Chưa test chạy **3 LDPlayer cùng lúc**.
4. Phần hỏi Claude đóng banner lạ mới test trên ảnh, chưa gặp banner lạ thật lúc chạy (banner gặp được đều đã có mẫu).
5. Task lỗi vẫn **dừng hẳn** máy đó (đã có chẩn đoán). Có thể thêm tự Start lại (làm tiếp từ nhân vật dở) 1–2 lần.
6. `che_to` đôi khi chạy thêm 1 vòng mua 1 đá (hoạt lực hồi trong lúc chế) — tốn ~20s.
7. (20/10) Các sửa chưa chạy trên máy thật (chỉ self-check): OCR tên mới, OCR "Lợi ích" x5, `_mo_trang_che` về màn
   chính trước, biến thể tên web, `chup_anh` bấm lại icon máy ảnh (21/10). Đã chạy thật: phiếu kết quả ⚠,
   `mong_hoa_luc`, `doi_tk_zing` trả "het", làm lại nhiệm vụ TNT, `_cho_gio_hen`, hẹn Windows Task Scheduler mở tool.
8. OCR tên vẫn sai giữa chữ ('ư'→'u', 'v'→'w') -> web cần gộp tay biến thể. Nếu còn nhiều: thử Windows OCR / đọc 2–3
   lần lấy kết quả nhiều nhất (cần ảnh thật để đo).

---

## 8. Cách test nhanh

- Kho acc: **↺ Reset trạng thái** (hoặc `status: ''` trong `accounts.yaml`) để chạy lại acc đã ✓.
- Log realtime: `tail -F logs/<ngày>.log`, lọc `LỖI|ACC|doi_acc|che_to|treo_to|Watchdog|Claude`.
- Log im quá 2 phút = bot đứng → chụp màn hình xem kẹt ở popup nào → cắt ảnh mẫu / thêm bước xử lý.
