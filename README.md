# SAFESIGHT

Quy trình: detect -> verify -> alert -> respond

## Tài liệu
- [Hướng dẫn sử dụng hệ thống](./HUONG_DAN_SU_DUNG.md)
- [Phân tích cấu trúc và luồng mã nguồn](./PHAN_TICH_HE_THONG.md)

## Cài đặt và chạy lần đầu trên Windows

1. Cài Python 3.10 trở lên và bảo đảm lệnh `py` hoặc `python` có trong `PATH`.
2. Giữ file model `models/ss_final_1.pt` trong thư mục `models`.
3. Chạy `setup.bat` để tạo môi trường Python riêng `.venv` và cài dependencies.
4. Chạy `run.bat` để khởi động ứng dụng, rồi mở http://127.0.0.1:5000.

Có thể chạy thủ công bằng `python -m venv .venv`, `.venv\Scripts\python.exe -m pip install -r requirements.txt` và `.venv\Scripts\python.exe app.py`. Bản đồ cần internet để tải Leaflet và ảnh vệ tinh.

## Thử nhận diện màn hình
```
python screen.py
```
Tool nhận diện màn hình và ứng dụng chính cùng dùng model YOLO `models/ss_final_1.pt` với 10 lớp. Mặc định chụp nửa bên phải màn hình đã chọn. Preview được làm mới độc lập với tốc độ suy luận; vị trí box được dự đoán giữa các lần detect, nên box di chuyển liên tục dù model chạy chậm hơn 30 FPS. Nhấn `q` hoặc `Esc` trong cửa sổ preview để thoát. Dùng `python screen.py --list-monitors` để xem màn hình; có thể chọn vùng khác bằng `python screen.py --monitor 1 --region 0 0 1280 720`, đổi model bằng `--model`, và chỉnh ngưỡng/kích thước/FPS bằng `--conf`, `--class-conf knife=0.65`, `--imgsz`, `--fps`. Đặt preview ngoài vùng đang chụp hoặc chuyển sang màn hình khác để tránh capture chính preview.

## Các trang
| Trang | Chức năng |
|---|---|
| Dashboard | Thống kê, biểu đồ 7 ngày, loại hung khí, trạng thái thiết bị, cảnh báo gần đây |
| Live Ops | Lưới video trực tiếp; nhấp một màn hình để đưa lên khung lớn bên phải, các màn hình khác xếp dọc bên trái; nút toàn màn hình bật/tắt chế độ toàn màn hình; nút **Phát tất cả video** chạy đồng thời các video demo và lặp liên tục; video vẫn được phát và nhận diện khi chuyển sang trang khác |
| Alerts | Màn hình xác minh: ảnh lớn cùng tối đa 5 khung hình bổ sung của cùng vật thể (tùy số frame nhận diện được), Dispatch / Delete alert / Clear all, hàng chờ thumbnail, bảng Messages |
| Past Ops | Lịch sử đã dispatch / đã xóa, lọc, xem ảnh, ghi chú |
| Cameras / Drones / Robots | Thêm, sửa, xóa thiết bị; camera hỗ trợ webcam/URL hoặc video demo MP4/WebM tải lên (tối đa 512 MB) |
| Map | Bản đồ vệ tinh: vị trí thiết bị + cảnh báo |
| Site / Notifications / Settings | Địa điểm, Telegram (thêm nhiều điện thoại theo Chat ID, gửi thử từng máy hoặc tất cả), ngưỡng confidence riêng cho 10 lớp, tên nhân viên |
| System Log | Nhật ký hệ thống |

Phím tắt khi đang xem cảnh báo: **D** = Dispatch, **X** = Delete alert.

## Telemetry cho drone/robot
```
curl -X POST http://127.0.0.1:5000/api/sources/<ID>/telemetry -H "Content-Type: application/json" \
  -d '{"mode":"AUTO","battery":76,"altitude":46,"speed":5.4,"sats":15,"flight_time":"4:22"}'
```
Các trường: mode, battery, voltage, signal, altitude, speed, heading, sats, temp, wind, flight_time, lat, lon.

## Thông báo Telegram tới điện thoại
- Tạo bot Telegram, lưu Bot token trong mục Notifications và bật **Gửi thông báo tới điện thoại khi Dispatch**.
- Trên mỗi điện thoại nhận tin, mở bot và gửi `/start`; thêm tên thiết bị cùng Chat ID trong Notifications.
- Có thể sửa tên và bật/tắt quyền nhận thông báo riêng cho từng thiết bị; thiết bị tắt sẽ không nhận Dispatch hoặc tin thử gửi tới tất cả.
- Dùng nút **Gửi thử** để kiểm tra riêng từng điện thoại hoặc **Gửi tin thử tới tất cả thiết bị đang bật**.
- Khi Dispatch, hệ thống gửi cảnh báo và ảnh tới tất cả thiết bị đang bật.

## Cấu trúc
```
app.py
weapon_detection/
  config.py
  detection/
    model.py
    streams.py
  notifications/
    notifier.py
  storage/
    db.py
  web/
    app.py
templates/index.html   static/css/style.css   static/js/app.js
models/ss_final_1.pt   data/(alerts, weapon_guard.db, dispatch.log, videos)
```
Ứng dụng dùng weights YOLO cục bộ `models/ss_final_1.pt`, gồm các lớp `axe`, `baseball_bat`, `hammer`, `pistol`, `knife`, `sword`, `rifle`, `machete`, `stick` và `spear`. Cài các dependencies trong `requirements.txt` trước khi chạy.

## Tăng FPS
- Video và detect chạy ở 2 luồng riêng: video luôn mượt, detect chạy theo tốc độ của máy.
- Settings mặc định dùng **imgsz 320**, ngưỡng tin cậy riêng **0,5 cho mỗi lớp**, và tối đa **45 lần detect mỗi giây cho mỗi nguồn**. FPS thực tế phụ thuộc phần cứng; tăng imgsz có thể hỗ trợ vật thể nhỏ/ở xa nhưng làm chậm xử lý, còn hạ ngưỡng có thể làm tăng nhận diện nhầm.
- FPS giới hạn là mức tối đa, không phải tốc độ bảo đảm; benchmark phụ thuộc model và độ phân giải khung hình.
- Nhiều nguồn dùng chung một model/GPU nên tổng lượt detect bị giới hạn bởi thông lượng suy luận và được chia sẻ giữa các nguồn; tăng FPS mục tiêu cho từng nguồn không làm GPU xử lý nhanh hơn.
- Video demo bắt đầu lượt detect mới ngay khi có thể và tính phần thời gian suy luận vào chu kỳ, tránh chờ thêm một khoảng FPS đầy đủ sau mỗi lần nhận diện.
- Video demo được thu nhỏ tối đa 1280 px trước khi gửi khung hình để tiết kiệm băng thông và thời gian mã hóa; độ phân giải suy luận vẫn do imgsz quyết định.
- Test video lấy khung hình mới ngay sau mỗi lần nhận diện xong (không chờ chu kỳ cố định), giảm khung gửi lên tối đa 640px và hiển thị FPS đo được cùng thời gian infer model.
- Có GPU NVIDIA và PyTorch bản CUDA: hệ thống tự dùng GPU (console in `device=GPU`). Cấu hình mặc định imgsz 320 ưu tiên tốc độ; hãy benchmark trên nguồn thực tế trước khi tăng kích thước.
- Chạy CPU vẫn được hỗ trợ; giảm imgsz hoặc số nguồn chạy đồng thời nếu cần. Cài PyTorch đúng cấu hình CPU/CUDA cho máy trước khi cài dependencies.
