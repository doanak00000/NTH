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
- (24/10) Bảng acc trên UI + web tự **xếp theo giờ chạy**: trống (chạy ngay) đầu, giờ sớm lên trước, cùng giờ giữ
  thứ tự cũ. ▲▼ chỉ còn tác dụng giữa các acc cùng giờ.
- (24/10) **Chọn 1 acc** trong bảng → ô dưới bảng hiện từng nhân vật + xu mới nhất (+ chưa rút, ngày nếu không phải
  hôm nay) và tổng xu, đọc `xu_web/xu.json` (`xu.xu_moi_nhat`). Acc private (từ 24/10) cũng quét xu nhưng ghi
  `xu_private.json` trên máy (gitignore), không push, không đụng xu_web.
- (26/10) **Treo lại tơ** (1 nút Start duy nhất, chạy full luôn ưu tiên): tick cột "Treo lại" (UI hoặc web, acc ✓
  cũng được). Kho xếp theo giờ như UI/web, chia **nhóm 5 acc** (31/10, trước là 4; `accounts.NHOM_TREO`); chạy full xong cả nhóm (✓/✗/bỏ tick Chọn) thì
  `nhan_acc` raise TaskDone → UI Start task `treo_lai_to.yaml` treo lại acc tick trong nhóm (`accounts.cho_treo_duoc`),
  xong tự quay về chạy full. Treo lại: đủ 6 nhân vật từ dưới lên (vẫn Xông Pha từng nhân vật), **tối đa 4 ô/nhân vật**,
  KHÔNG đụng status / nv_xong / giờ hẹn (trường `treo` riêng), xong acc tự bỏ tick.
  Acc hẹn giờ tới / còn < 30 phút → chạy full trước (`ranh_cho_treo`, xét trước mỗi acc treo); acc "chạy ngay" chờ.
  Acc chờ treo kế là PUBLIC → treo trước cả acc PRIVATE hẹn giờ (private chạy full sau).
  (30/10 user) Đang chạy acc PRIVATE mà acc PUBLIC hẹn giờ còn ≤ 15 phút (`_public_sap_toi`) → xong nhân vật đang
  làm thì `doi_acc` dừng acc private ở "dở x/6", `nhan_acc` không nhận private, chờ tới giờ chạy public; xong public
  thì claim lấy lại acc private dở (chọn dòng cuối như thường).
  (27/10) Giờ hẹn tính theo NGÀY GAME (sang ngày lúc 5h, `gio_hom_nay`): trước đây qua 0h acc hẹn 23:26 chưa kịp
  chạy bị tính sang 23:26 hôm sau (bỏ lượt). Giờ 00:00-04:59 = đêm cuối của ngày game.
  (26/10) Bấm Stop lúc đang đăng nhập từng đánh ✗ acc (nhan_acc bắt cả Stopped) → giờ bỏ qua Stopped.
  Tick từ web lúc tool đang chờ giờ hẹn → UI xét 30s/lần (`_xet_treo`). Web Start: tool đang dừng → chạy full;
  đang chạy → bỏ qua (không cắt ngang acc). UI phải đang mở.
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
- (05/11) Bấm ZingID mà form **không hiện** (chỉ còn màn nền) = lỗi máy, không phải lỗi tk → `doi_tk_zing` tự khởi động
  lại LDPlayer rồi thử lại (tối đa 2 lần). Vẫn hỏng thì báo lỗi nhưng **không đánh ✗ tk**, lần sau thử lại đúng tk đó.
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
  - (01/11) khadoan1608 có 'Lâm My' và 'Lâm Mỳ Mỳ': `xu.cung` luật "đoạn chung ≥ 85% tên ngắn" coi 'lammy' ⊂ 'lammymy'
    là trùng → ✓ 5/6. Giờ luật đó chỉ áp khi tên ngắn ≥ 80% tên dài.
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
  (02/11) Giữ thêm cụm chữ sát BÊN TRÁI cụm chính (cách ≤10px, `_cum_chu`): "Sư Tán" cách 9px bị cắt còn "Tán" → Y Tán/Sư Tán trùng tên, mylu1108 chỉ 5/6.
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
  (24/10) Có nhân vật (Đá Lâm) bấm nút like lại **mở trang chi tiết bài viết** → tưởng like được, unlike hụt, TNT 3/4
  (2 ngày liền). Giờ thấy nút like rời vùng cũ mà có ở thanh dưới (210,500) → bấm like ở đó.
- Hảo Cảm (`hao_cam`, 21/10 chuyển từ YAML sang hàm để Thanh Nhai Thư gọi lại được khi sót).
- (24/10) Popup **"Nhắc nhở" Giải Đấu Bang Hội** (không có X) bật giữa lúc mua đá → kẹt, Claude cứu bấm Hủy Bỏ
  (357,342). Đã thêm mốc `moc_nhac_nho.png` vào `_MOC_BANNER` → tự Hủy Bỏ.
- (01/11) Banner **"Nhất Niên Fashion Week"** (26/10–06/11) sau Xông Pha: không thấy nút X → watchdog + Claude cứu
  ~2 phút. Đóng ở góc phải trên (765,108). Thêm mốc `moc_fashion_week.png` vào `_MOC_BANNER`.
- (04/11) Banner **"Nhất Niên Đại Yên 1st"** (28/10–14/11) sau Xông Pha: X trắng ở (850,77) chìm khi nền game sáng
  → kẹt ~4 phút (Claude trả NONE 2 lần). Thêm mốc `moc_dai_yen.png` (chữ tiêu đề) → bấm (850,77).
- (31/10) Popup đó đè lên **bảng Hoạt động đang mở** (20:00) → `_tim_nut_x` khớp ✕ thu bảng, bỏ ✕ mà bỏ luôn mốc
  banner → CHỜ CLAUDE. Giờ lọc ✕ trước khi xét mốc. Thêm: `mo_hoat_dong` thấy bảng mở sẵn thì không bấm (bấm = thu lại).
- (31/10) Popup đó bật lúc đang **treo bán** (20:30) → `ve_man_hinh_chinh` bấm back hụt đủ 8 lần dưới popup, vẫn kẹt
  trang Giao Dịch → `doi_acc` bấm (918,21) trúng **'+' tiền → mở trang Nạp** (3 lần liền). Giờ bấm back mà màn không
  đổi thì `dong_banner` trước. Popup này hiện lại nhiều lần quanh 20:00-20:30 (Giải Đấu Bang Hội).
- Lần đầu mở nghề lạ (vd Câu Cá) có popup "Nhắc nhở" → **Hủy Bỏ**, đừng nhận.

### Chế tơ
- Nghề nghiệp → icon **Thiết Kế** (663,488) (KHÔNG phải (293,488) chế tác). Chờ thấy `thiet_ke_icon.png` vì trang load chậm.
  (23/10) Icon lúc có lúc không **chấm đỏ thông báo** góc phải trên → mẫu cũ có chấm chỉ khớp 0.64 khi không có
  (kẹt 20s, Claude cứu). Mẫu giờ cắt lõi 24x24 bỏ góc chấm: không chấm 1.0, có chấm 0.96, icon khác ≤0.55.
- Công thức: ~~Tơ Phiêu Vân-2 dòng thứ 3 (245,212)~~ — (06/11 game cập nhật) list có nhiều dòng "Tơ Phiêu Vân-2"
  (cấp 15/16/1 dùng HOA, cấp 11 thứ 2 = **đá trắng tím**, cấp 13 thứ 2 = **đá vàng**), 2 dòng đá nằm dưới, phải cuộn;
  cuộn mỗi lần lệch ~9px nên KHÔNG bấm toạ độ: `_chon_cong_thuc` tìm icon tơ (`to_cong_thuc.png`) trong list, bấm
  từng dòng tơ tới khi ô đá khớp `da_trang.png` / `da_vang.png` (đá trắng ↔ mẫu vàng chỉ 0.64). Hết list chưa thấy
  -> cuộn về đầu dò lại. Đo thật: màn chính -> công thức đá trắng 35s. Ảnh test: tests/anh/che_to_da_*.png.
- Đá vàng (Diệu Tinh Thạch) ở (525,322). Tap đầu đôi khi bị bỏ qua → thử lại 3 lần.
- 1 lần chế = 5 hoạt lực. Số lần = hoạt lực // 5; **chỉ mua phần thiếu** = số lần − số đá đang có; `^` (617,422) = tối đa → Chế Tạo.
- **Chỉ mua khi giá lô rẻ nhất ≤ 83** (OCR (277,120,40,22)). Đắt hơn → chỉ chế bằng đá đang có.
- Hoạt lực **có thể vượt tối đa** (vd 1565/1500).
- (20/10) OCR hoạt lực đôi lúc trượt 1 lần dù số rõ ('311/1500') → đọc lại tối đa 4 lần (cách 1,5s) rồi mới báo lỗi.
- (24/10) OCR hoạt lực x3 đọc '723/1500' thành **'7723/1500'** cả 8 lần (vô lý -> None) -> kẹt, CHỜ CLAUDE. x5 đọc đúng.
  `_doc_so_ocr(hop_le=...)`: cách đọc có số mà không hợp lệ thì thử tiếp (x5, đảo màu).
- (20/10) **Túi đầy** → bấm Chế Tạo hiện "Túi không đủ chỗ trống, không thể hoàn thành công thức này", hoạt lực không
  giảm. Trước đây bot bấm 3 lần + chế tơ lần 2 còn mua thêm đá vô ích (tk test3). Giờ: bấm xong mà hoạt lực không giảm
  → phiếu `nghề nghiệp: failed` + ảnh, dừng; chế tơ lần 2 của nhân vật đó bỏ qua (vẫn mở trang chế cho treo_to).
  Đá vẫn bị mua ở lần 1 (chưa biết túi đầy trước khi chế). Cần người dùng dọn túi.
- (01/11) OCR đọc hoạt lực 242 thành '22' → chế 4 lần xong còn 222 bị tưởng "không giảm" → báo túi đầy SAI, bỏ chế
  lần 2 (Lâm Mỳ Mỳ). Giờ chỉ coi là túi đầy khi hoạt lực BẰNG lần trước; tăng = lần đọc trước sai → chế tiếp.
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
- (01/11 user) **Chủ nhật** (ngày game, CN 5h → T2 4h59): nhận mốc ngày xong thì bấm ô vật phẩm "Tiến Độ Điểm Tuần"
  (626,490) — toạ độ cố định vì icon quà đổi theo tuần; KHÔNG bấm dòng tiêu đề (620,452). `_nhan_qua_tuan`. Popup quà tuần là "Nhận Thưởng" (`nhan_thuong_dong.png`), KHÁC "Chúc Mừng Nhận".
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
  thời gian làm lại không tính vào hạn 180s). Phiếu ghi `làm lại <nhiệm vụ>: 1`. Đã chạy thật 21/10 (tk test
  tk test1, gọi roll TRƯỚC khi làm gì): tự làm lại cả 4 rồi nhận 4/4. Thử nhận diện trên 56 ô thật × 5 vị trí: đúng hết.
  (24/10) Làm lại xong thì xoá phiếu 'failed' cũ của nhiệm vụ đó (trước đây TNT 4/4 mà nhân vật vẫn ⚠).
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

### Bản PC (02/11 — giả lập LDPlayer/BlueStacks kẹt ở SDK VNG, điện thoại thật vẫn chơi được)
- Thiết bị `[PC] Nghịch Thủy Hàn` (`nthbot/pc.py`): cửa sổ game để **1280x720** (đúng 16:9), tool chụp PrintWindow
  thu về 960x540 + click/kéo PostMessage (không chiếm chuột). Game co cửa sổ về 0x0 khi bị ẩn -> tool tự trả 1280x720.
- Trang toàn màn (Du Ngoạn, chế, chợ, bảng bán, Thanh Nhai Thư, chọn nhân vật, màn server) **giống hệt mobile**.
  Khác: HUD màn chính + bảng mở từ cạnh (Hoạt động dạng lưới, Xã Giao) nhỏ ~0.78 -> ảnh mẫu `templates_pc/`
  + `pc: {...}` trong task (Du Ngoạn 665,285; máy ảnh 26,513; Xã Giao 364,506, tab MHL 22,99, thu 508,246).
- Cài đặt PC **đổi chỗ**: 'Chuyển đổi nhân vật' (439,147), 'Giao diện đăng nhập' (844,147) — 846,147 của mobile
  trên PC là ĐĂNG XUẤT tk Zing.
- Đăng nhập: icon người ở màn server mở cửa sổ riêng `VNGGamesSDK_Dialog` (391x396) **không nhận PostMessage** ->
  click/gõ thật (`click_that`/`go_that`, mượn chuột ~0.5s). tk đã từng đăng nhập nằm sẵn trong list (OCR dòng
  y=124+48k) -> bấm là vào; tk mới: Add New -> ZingID -> gõ -> Login -> lần đầu có trang điều khoản (tick + Đồng ý).
- Chưa làm: tự mở game qua launcher Level Up (mở tay trước khi Start), tk email trên PC.

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
- (30/10) Khởi động lại LDPlayer giữa 2 acc xong, đăng nhập được ~1 phút thì **máy ảo sập** (mất `Ld9BoxHeadless`,
  `dnplayer` còn, adb `offline` mãi) -> AdbError 3 lần lọt khỏi vòng task, dừng cả máy. `bot.py` giờ bắt AdbError ở
  vòng task: khởi động lại LDPlayer 1 lần rồi làm lại vòng (sập 2 lần liền mới dừng).
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
  (01/11 mylu1108 sai mk) tk kế (tk test3) gặp popup "[7002] Bạn đã bỏ qua đăng nhập bằng ZingID!" (OK 480,304) ->
  Claude cứu 2 lần (~1,5 phút). Giờ `doi_tk_zing` thấy `bo_qua_zing_7002.png` cũng bấm OK như `dn_that_bai.png`.
- (20/10) So tên **gần đúng** dùng chung 1 luật `xu.cung` (trên `xu._chuan`) cho cả chọn nhân vật lẫn web: giống
  >= **0.85** HOẶC đoạn chung dài nhất >= 85% tên ngắn hơn. Ngưỡng cũ 0.9 làm 'KRIXI'->'KRXI' (0.89),
  'NhưƠïnhY'->'NhữDinhY' bị tưởng nhân vật mới -> **làm lại lần 2** (cùng xu 755K). Chỉ so trong 1 tk; khác người
  trong cùng tk gần nhất đo được: MissU/KissU 0.80 (TRiệu Vân/TriểuHân 0.875 là 2 tk khác nhau, không đụng nhau).
  Thử trên toàn bộ tên thật của các tk: mọi cặp >= 0.85 đều là biến thể OCR của cùng 1 tên.
- (19/10, thay 20/10) Cả NHÂN VẬT ĐẦU (vừa đăng nhập) cũng chọn dòng cuối (`nhan_acc tu_duoi: true` -> `doi_tk_zing`
  -> `_chon_tu_duoi`). Tk đã làm hết hôm nay (vd Reset rồi chạy lại) -> `doi_tk_zing` trả "het" -> `nhan_acc` ✓ tk,
  lấy tk khác (trước đây vào dòng 1 làm lại nhân vật đã xong). Cách chọn hiện tại: mục 4 "Danh sách nhân vật".
- (05-06/11 thay mục dưới) Loại đá chọn THEO ACC (cột "Đá vàng" UI / web, mặc định đá trắng tím), 2 luồng độc lập,
  không tự đổi; chọn công thức bằng ảnh (xem mục Công thức ở trên).
- (03/11, CŨ) **Đá trắng tím (Long Đảm Thạch)**: đá vàng không có lô <= 83 -> `che_to` bấm TỌA ĐỘ (245,86) lên dòng 1
  (Tơ Phiêu Vân-2 cấp 11, 5 hoạt lực/lần, thêm tơ 20% thay vì 40%; ảnh dòng giống hệt các dòng khác nên không dò ảnh),
  ô đá vẫn ở (525,322), Cách nhận -> Khu Giao Dịch -> chợ y hệt đá vàng (giá ô đầu đọc OCR được), mua <= 82.
  Nhớ theo nhân vật: chế tơ lần 2 vào thẳng dòng 1. Sang nhân vật khác thử lại đá vàng trước.
- (04/11) Báo lỗi giả (BAO_GIA_FAILED / _bao_loi_gia_public) ĐÃ GỠ theo ý user. Phiếu failed/3/4 ghi trước 11h 04/11 có thể là giả.
- (19/10) **Hẹn giờ chạy acc**: cột "Giờ" trên UI (trống = chạy ngay, mặc định). Kho lưu `gio` (HH:MM) + `gio_ngay`
  (ngày đặt/cập nhật). ~~+10 phút/ngày~~ (bỏ 19/10): bot xong **nhân vật 1** của acc hẹn giờ -> `accounts.dat_gio`
  đặt giờ hẹn = đúng giờ xong đó (3/11 user bỏ +3 phút; trước đó +3, +10) -> mai bắt đầu đúng lúc hàng treo hôm trước vừa hết hạn (vào sớm thì kệ còn đầy hàng chưa
  hết hạn, không treo được). Không chạy ngày nào thì giờ giữ nguyên; giờ trôi muộn dần -> người dùng gõ lại.
  UI: ô Giờ theo file (bot dời giờ); chỉ ô người dùng vừa gõ (`_DA_SUA`) mới được Lưu ghi đè. Xoá dấu `_DA_SUA`
  cũng phải `blockSignals` (self-check bắt được: không chặn thì mọi ô bị coi là "vừa sửa", giờ bot dời bị đè).
  `claim` chỉ lấy acc đã tới giờ, nhiều acc cùng sẵn sàng thì **public trước private**; không acc nào sẵn sàng mà còn acc hẹn chưa tới giờ -> `nhan_acc` chờ (sleep 30s/lần,
  rồi `khoi_dong_game` cho chắc) thay vì kết thúc task. Acc chạy lần lượt trên 1 máy; nhiều máy thì acc cùng giờ có
  thể chạy song song. Giờ hẹn trước 5h sáng: acc 'done' hôm trước chưa reset (reset lúc 5h) -> hôm đó không chạy.
- (19/10) Roll Thanh Nhai Thư tối đa **180s** (`max_giay`, người dùng chọn): hụt nhiệm vụ (vd chụp ảnh không xong)
  thì không bao giờ đủ 4 ô -> trước roll ~120 vòng (~8 phút). Giờ quá 180s thì thôi, nhận mốc rồi đi tiếp.
- **QUY TẮC ACC PRIVATE (bắt buộc):**
  - Acc người dùng nói là private -> LUÔN vào kho private (`private: true`). (24/10) Xu chỉ ghi `xu_private.json` trên máy để xem trên tool; không đưa
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
- (28/10) Bật LDPlayer xong LDStore tự mở đè game -> game nền ANR mãi, Android cũng "Process system isn't responding" -> kẹt khoi_dong_game 300s. `khoi_dong_game` giờ thấy app khác ở màn trước thì mở lại game (LDStore thì force-stop trước); quá 150s game chưa lên (thường ~45s) = Android đơ -> tự khởi động lại LDPlayer 1 lần. Đã `pm disable-user com.android.ld.appstore` trên LDPlayer14 (bật lại: `pm enable`).
- (02/11) Game ra bản vá tài nguyên (sáng T2, `Patch/version.info` mới) -> lần mở đầu "Đang dọn dẹp tệp và cục bộ" ăn 6 nhân CPU (load 22), lâu > 150s, adb rớt `device offline` -> tool khởi động lại LDPlayer giữa chừng, game dọn lại từ đầu, lặp. `khoi_dong_game` giờ thấy `moc_don_tep.png` thì chờ (tối đa 30 phút), không khởi động lại, chịu adb rớt.
- (28/10) **Báo Discord**: `bot._log` gặp CHỜ CLAUDE / BỎ QUA / ⚠ / LỖI: / Báo cáo / Kết thúc / Android đơ -> gửi webhook (`discord_webhook.txt`, gitignore; tên nhân vật bị cắt). Acc private KHÔNG báo (`_dang_lam_private`). Thêm: bước lỗi phải nhờ Claude cứu, adb rớt, Claude lỗi, đứng im ≥3 phút (2 lần watchdog liền, báo 1 lần/lần kẹt). Claude cứu lỗi (`claude -p`) có thêm thao tác `KHOI_DONG_LAI_LD`; không chụp được màn hình -> khởi động lại LDPlayer thay vì bỏ acc.
- (02/11) **Màn hình phụ**: có màn phụ thì UI tool mở ở đó (`ui/app.py main`), LDPlayer bật xong dời sang đó 3 lần trong ~20s (`ldplayer._doi_sang_man_phu`, gọi trong `start_instance`). Màn phụ tắt -> Windows tự kéo về màn chính.
- (02/11) Đã báo lỗi lên Discord -> lần `Tap '...'` kế báo thêm 1 dòng "✅ Đã chạy lại bình thường (sau lỗi lúc HH:MM)" (`BotRunner.loi_luc`).
- (28/10) OCR xu mất dấu chấm: Stylist Mỹ 1.1M đọc thành `11M` -> web hiện 11M. `_sua_xu`: M không chấm (xu không bao giờ ≥10M) -> chấm sau chữ số đầu; K ≥4 chữ số không chấm -> chấm trước số cuối.
- (28/10) Mộng Hoa Lục tk test2/Xún (lần 2, 26/10 cũng vậy): bài đầu là bài chia sẻ dài -> nút like ở đáy (264,511) ngoài `vung_like` -> "chưa thấy nút like" x3, TNT 3/4. Lần tìm đầu giờ nới vùng xuống đáy (khớp like_chua 0.92); kiểm tra trang chi tiết giữ vùng cũ.
- (01/11) Mộng Hoa Lục khadoan1608 (3/5 nhân vật): tab Theo Dõi trống "Chưa có nội dung Mộng Hoa Lục" (không theo dõi ai) -> chưa thấy nút like x3, TNT 3/4. Lần thử 2-3 bấm tab **Khám Phá** (108,75) — CHỈ khi thấy `tab_kham_pha.png` (bấm mù trên màn chính = mở bảng Nhiệm Vụ, Wfflec Dượcc). Chưa kiểm bố cục Khám Phá bằng ảnh.
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
