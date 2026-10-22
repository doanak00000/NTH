# NTH Bot — Auto game qua ADB (LDPlayer)

Tool điều khiển game **Nghịch Thủy Hàn** (hoặc game khác) trên **LDPlayer** thông qua ADB:
chụp màn hình → nhận diện hình ảnh (OpenCV) → tap/vuốt. Chạy **nhiều instance song song**,
có **UI desktop**, và các bước bot khai báo bằng **file YAML dễ sửa**.

> ⚠️ **Vì sao LDPlayer chứ không phải BlueStacks Air?**
> BlueStacks Air (bản Mac) khoá ADB ở chế độ chỉ-đọc: `screencap` được nhưng `input tap/swipe`
> bị chặn → không điều khiển được. LDPlayer (Windows) mở ADB hoàn toàn nên dùng được đầy đủ.

---

## 1. Cài đặt (trên Windows)

1. Cài **Python 3.9+**: https://www.python.org/downloads/ (nhớ tick *Add Python to PATH*).
2. Cài **LDPlayer 9** và tạo các instance, cài sẵn game vào.
3. Mở **PowerShell/CMD** tại thư mục tool rồi chạy:
   ```bat
   pip install -r requirements.txt
   ```

## 2. Cấu hình — sửa `config.yaml`
p
```yaml
adb_path: "C:/LDPlayer/LDPlayer9/adb.exe"          # adb đi kèm LDPlayer
ldconsole_path: "C:/LDPlayer/LDPlayer9/ldconsole.exe"  # để tự dò instance
game_package: "vng.game.nth"                        # package game (xem cách lấy bên dưới)
```

**Lấy package name của game:** mở 1 instance có game, rồi liệt kê app đã cài (`-3` = chỉ app người dùng):
```bat
C:/LDPlayer/LDPlayer9/adb.exe devices
C:/LDPlayer/LDPlayer9/adb.exe -s emulator-5554 shell pm list packages -3
```
Tìm dòng giống tên game rồi dán vào `game_package`. Bản **VNG (Việt Nam)** là `vng.game.nth`;
bản China/Global có thể khác (vd `com.netease.nshm`) → **tự dò trên máy bạn, đừng đoán**.

> Lưu ý serial: LDPlayer thường hiện thiết bị dạng `emulator-5554`, `emulator-5556`, ... trong
> `adb devices` (không phải `127.0.0.1:5555`). Dùng đúng serial mà `adb devices` in ra.
> Cổng ADB theo công thức `5555 + index*2` (instance 0→5555, 1→5557, ...).
> Tool tự dò qua `ldconsole`; nếu không dùng ldconsole, khai báo tay ở `manual_devices`.

## 3. Chạy

**Giao diện (khuyên dùng):**
```bat
python run.py
```
- Bấm **↻ Dò instance** để thấy các máy LDPlayer đang chạy.
- Chọn **Task**, tick các instance → **▶ Start**. **■ Stop** để dừng tất cả.
- Bấm vào ảnh preview để lấy **toạ độ (x,y)**; nút **✂ Cắt ảnh mẫu** để tạo template.

**Dòng lệnh (chạy nền/không UI):**
```bat
python run_cli.py --list-devices
python run_cli.py --task thanh_nhai_thu_6acc.yaml
python run_cli.py --task thanh_nhai_thu_6acc.yaml --device 127.0.0.1:5555
```

---

## 4. Tạo ảnh mẫu (template)

Bot "nhìn" bằng cách so khớp ảnh mẫu. Cách tạo nhanh:
1. Trong UI, chọn instance để thấy màn hình game ở vùng cần.
2. Bấm **✂ Cắt ảnh mẫu**, kéo chuột khoanh đúng **nút/icon/NPC** (cắt sát, ít nền thừa).
3. Đặt tên đúng như trong task (vd `nut_nhiem_vu.png`). File lưu vào `templates/`.

Mẹo: ảnh mẫu nên chụp ở **đúng độ phân giải** instance sẽ chạy. Nếu chạy nhiều độ phân giải
khác nhau, bật `vision.multi_scale: true` trong config (chậm hơn chút).

---

## 5. Sửa các bước bot — file `tasks/*.yaml`

Mỗi task là 1 file YAML. Mỗi bước là `- action: tham_số`, chạy lần lượt từ trên xuống.

### Các action có sẵn

| Action | Tham số | Ý nghĩa |
|--------|---------|---------|
| `launch` | `"{package}"` | Mở app |
| `stop_app` | `"{package}"` | Tắt app |
| `tap` | `{x, y, jitter}` | Chạm toạ độ (jitter = nhiễu ngẫu nhiên) |
| `tap_match` | `{jitter}` | Chạm vào ảnh vừa tìm thấy gần nhất |
| `swipe` | `{x1,y1,x2,y2,duration}` | Vuốt |
| `key` / `back` / `home` | keycode | Phím cứng |
| `text` | `"chuỗi"` | Gõ chữ |
| `sleep` | số giây | Chờ |
| `log` | `"thông báo"` | Ghi log |
| `find` | `{image, timeout, confidence, region}` | Tìm ảnh (trả true/false) |
| `find_tap` | `{image, timeout, confidence, required, after, jitter}` | Tìm ảnh rồi tap vào tâm |
| `wait_image` | `{image, timeout, required}` | Chờ ảnh xuất hiện |
| `wait_vanish` | `{image, timeout}` | Chờ ảnh biến mất (loading) |
| `if` + `then`/`else` | `{image}` hoặc `{not_image}` | Rẽ nhánh theo ảnh |
| `loop` + `steps` | `{times}` / `{while_image}` / `{until_image}` / `{max}` | Lặp |
| `set` | `{ten_bien: gia_tri}` | Gán biến (dùng lại qua `{ten_bien}`) |
| `screenshot` | `{path}` | Lưu ảnh để debug |
| `python` | `{func, ...}` | Gọi hàm trong `custom.py` (nâng cao) |

### Ví dụ

```yaml
- find_tap: { image: "nut_nhiem_vu.png", timeout: 30, required: true, after: 1.5 }
- if: { image: "hop_thoai.png" }
  then:
    - tap: { x: 820, y: 430 }
  else:
    - log: "không có hộp thoại"
- loop: { times: 5, until_image: "xong.png" }
  steps:
    - find_tap: { image: "nut_tiep.png" }
    - sleep: 1
```

- `timeout`: chờ tối đa bao nhiêu giây cho ảnh xuất hiện (0 = tìm 1 lần).
- `confidence`: ngưỡng khớp 0–1 (mặc định 0.85 trong config). Khó khớp → giảm xuống 0.8.
- `required: true`: không thấy → báo lỗi & dừng task (mặc định false thì bỏ qua).
- `{ten_bien}`: thay bằng giá trị biến; `{package}` = package game.

### Nâng cao: viết Python (`custom.py`)
Khi cần logic phức tạp (đọc số liệu, điều kiện đặc biệt), viết hàm trong `custom.py` rồi gọi:
```yaml
- python: { func: vi_du, nguong: 0.9 }
```

---

## 6. Task mẫu "Thanh Nhai Thư"

File `tasks/thanh_nhai_thu_6acc.yaml` là **khung mẫu** — cần bạn:
1. Tạo các template được nhắc tới trong file (`man_hinh_chinh.png`, `nut_nhiem_vu.png`,
   `muc_thanh_nhai_thu.png`, `nut_nhan_thu.png`, `nut_giao_thu.png`, ...).
2. Chỉnh lại thứ tự bước/toạ độ cho khớp giao diện game thật.

Vì giao diện game thay đổi theo phiên bản/độ phân giải, không thể có template sẵn — bạn dùng
công cụ **✂ Cắt ảnh mẫu** trong UI để tạo nhanh.

---

## 7. Đóng gói thành .exe (tuỳ chọn)

```bat
pip install pyinstaller
pyinstaller --noconfirm --windowed --name NTHBot ^
  --add-data "config.yaml;." --add-data "tasks;tasks" --add-data "templates;templates" ^
  run.py
```
File chạy nằm trong `dist/NTHBot/`.

---

## Cấu trúc dự án
```
config.yaml              # cấu hình (adb path, package...)
run.py                   # mở UI
run_cli.py               # chạy không UI
custom.py                # hàm Python tuỳ chỉnh (nâng cao)
tasks/                   # các task .yaml (bạn sửa ở đây)
templates/               # ảnh mẫu (tạo qua UI)
nthbot/
  adb.py                 # bọc ADB
  ldplayer.py            # dò instance LDPlayer
  vision.py              # nhận diện ảnh (OpenCV)
  engine.py              # bộ chạy step (lõi)
  bot.py                 # chạy 1 task/1 máy (luồng riêng)
  orchestrator.py        # điều phối nhiều máy
  ui/app.py              # giao diện desktop
```

## Chạy nhiều tài khoản Zing

1. Bấm **👤 Tài khoản Zing** trong UI → thêm tk/mk vào kho acc (dùng chung cho mọi instance) → Lưu.
2. Cắt các ảnh mẫu đăng nhập Zing (danh sách ở đầu `tasks/thanh_nhai_thu_6acc.yaml`).
3. Tick các instance, chạy **Thanh Nhai Thư 6 acc**: mỗi máy tự lấy acc chưa chạy → làm 6 nhân vật → acc ✓ xong
   → lấy acc tiếp. Kho hết acc thì máy tự dừng. Bấm **↺ Reset trạng thái** để chạy lại từ đầu (vd ngày mới).
