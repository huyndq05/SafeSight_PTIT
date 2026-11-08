# Hướng dẫn sử dụng SAFESIGHT

SAFESIGHT hỗ trợ theo dõi camera, drone và robot, phát hiện vật thể bằng AI, xác minh cảnh báo và gửi thông báo tới điện thoại.

## 1. Khởi chạy hệ thống

Mở Terminal tại thư mục dự án và chạy:

```powershell
pip install -r requirements.txt
python app.py
```

Truy cập `http://127.0.0.1:5000` bằng trình duyệt trên máy đang chạy ứng dụng. Bản đồ cần kết nối Internet để tải bản đồ nền.

Trạng thái kết nối ở thanh trên cùng cho biết giao diện có kết nối được với máy chủ hay không. Nếu hiện mất kết nối, hãy kiểm tra cửa sổ Terminal và khởi động lại ứng dụng nếu cần.

## 2. Tổng quan các màn hình

| Màn hình | Công dụng |
|---|---|
| **Dashboard** | Xem số cảnh báo hôm nay, cảnh báo đang chờ, cảnh báo đã xử lý, tỷ lệ cảnh báo đã dispatch, trạng thái thiết bị và thống kê 7 ngày. |
| **Live Ops** | Theo dõi hình ảnh/video và trạng thái các nguồn thiết bị. |
| **Alerts** | Kiểm tra bằng chứng, ghi chú và quyết định dispatch hoặc xóa cảnh báo. |
| **Past Ops** | Tra cứu cảnh báo đã dispatch hoặc đã xóa. |
| **Cameras / Drones / Robots** | Khai báo, chỉnh sửa và xóa nguồn thiết bị tương ứng. |
| **Map** | Xem vị trí địa điểm, thiết bị và cảnh báo có tọa độ. |
| **Site** | Cấu hình tên, địa chỉ và tọa độ trung tâm của địa điểm. |
| **Notifications** | Cấu hình Telegram và quản lý điện thoại nhận thông báo. |
| **Settings** | Điều chỉnh giao diện, người trực, âm báo và tham số nhận diện. |
| **System Log** | Xem nhật ký sự kiện và hoạt động gần đây. |

## 3. Khai báo camera, drone và robot

1. Mở **Cameras**, **Drones** hoặc **Robots**.
2. Chọn **Thêm Camera/Drone/Robot**.
3. Nhập tên thiết bị và nguồn video. Có thể dùng webcam (ví dụ `0`), URL camera/video hoặc địa chỉ RTSP.
4. Với **Camera**, có thể chọn tải lên video demo định dạng MP4 hoặc WebM thay cho nguồn trực tiếp.
5. Với **Drone** và **Robot**, nhập thêm tọa độ nếu muốn hiển thị thiết bị trên bản đồ. Có thể bật hoặc tắt thiết bị tại biểu mẫu.
6. Chọn **Lưu**. Dùng **Sửa** để thay đổi cấu hình hoặc **Xóa** để gỡ thiết bị.

Drone và robot có thể gửi dữ liệu telemetry tới API của hệ thống. Ví dụ:

```powershell
curl -X POST http://127.0.0.1:5000/api/sources/<ID>/telemetry `
  -H "Content-Type: application/json" `
  -d '{"mode":"AUTO","battery":76,"altitude":46,"speed":5.4,"sats":15,"flight_time":"4:22"}'
```

Thay `<ID>` bằng ID thiết bị trong danh sách. Các trường telemetry tùy chọn gồm `mode`, `battery`, `voltage`, `signal`, `altitude`, `speed`, `heading`, `sats`, `temp`, `wind`, `flight_time`, `lat` và `lon`.

## 4. Theo dõi Live Ops

- Mở **Live Ops** để xem các nguồn thiết bị trong lưới.
- Chọn thanh tên camera hoặc vùng video để đưa nguồn đó lên khung lớn. Chọn **Trở về dạng lưới** để quay lại bố cục ban đầu.
- Nút toàn màn hình trên khung video bật/tắt chế độ toàn màn hình.
- Với video demo, dùng các điều khiển phát, tua và âm thanh tích hợp trên video; chọn **Phát tất cả video** để phát đồng thời. Video demo được cấu hình lặp liên tục.
- Box video demo dùng kết quả đúng frame đã gửi; nếu frame mới không phát hiện vật thể thì box cũ được xóa khi video tới đúng thời điểm đó, thay vì tiếp tục bám theo vị trí lỗi thời.
- Thanh trạng thái hiển thị trạng thái online/offline và dữ liệu thiết bị nếu có.

Việc chuyển giữa các trang không đồng nghĩa với việc thay đổi cấu hình nguồn. Nếu video không hiển thị, hãy kiểm tra URL, thiết bị có đang hoạt động và trạng thái kết nối ở thanh trên cùng.

## 5. Xác minh và xử lý cảnh báo

Khi hệ thống phát hiện vật thể đủ điều kiện, cảnh báo sẽ xuất hiện trong **Alerts** và được thêm vào hàng chờ.

1. Chọn thumbnail ở cạnh màn hình để chuyển giữa các cảnh báo đang chờ.
2. Xem ảnh phát hiện ban đầu và 5 ảnh theo dõi tiếp diễn (mỗi ảnh cách nhau 3 lần phân tích). Chọn thumbnail để mở ảnh lớn; rê chuột trên ảnh để dùng kính lúp. Mỗi ảnh hiển thị bounding box, nhãn, độ tin cậy và thời điểm riêng; dùng thanh trượt **Hiển thị nhãn nhận diện** để ẩn/hiện chữ nhãn mà vẫn giữ khung box. Ảnh tiếp diễn được gắn vào cùng cảnh báo và hiển thị dần sau khi cảnh báo xuất hiện.
3. Đối chiếu nhãn và bounding box trên từng ảnh. Nhãn hiển thị giữ nguyên tên lớp của model. Khi Telegram được bật, Dispatch gửi nhóm ảnh cùng thông tin nhận diện tương ứng cho từng ảnh. **Dispatch** xác nhận toàn bộ cảnh báo, không phải từng ảnh riêng lẻ. Kiểm tra thêm nguồn, vị trí, thời gian và Timeline.
4. Có thể nhập ghi chú rồi chọn **Lưu ghi chú**.
5. Chọn một trong các thao tác:
   - **Dispatch**: xác nhận và chuyển cảnh báo sang trạng thái đã dispatch. Nếu đã bật cấu hình Telegram, hệ thống gửi thông báo tới các thiết bị đang bật nhận tin.
   - **Delete alert**: đánh dấu cảnh báo là đã xóa/không dispatch.
   - **Clear all**: xóa toàn bộ cảnh báo đang chờ sau khi xác nhận.

Ảnh của cảnh báo đã tạo trước khi cập nhật có thể đã gắn nhãn trực tiếp vào ảnh nên không thể ẩn riêng phần chữ; các cảnh báo mới sau khi khởi động lại ứng dụng hỗ trợ đầy đủ thanh trượt.

Phím tắt khi đang ở **Alerts**:

- `D`: Dispatch cảnh báo đang chọn.
- `X`: Xóa cảnh báo đang chọn.

Không nhấn phím tắt khi đang nhập trong ô văn bản. Lịch sử thao tác và các cảnh báo đã xử lý có thể xem trong **Past Ops**; danh sách có thể lọc theo trạng thái.

## 6. Xem bản đồ và cấu hình địa điểm

- Trong **Site**, nhập tên địa điểm, địa chỉ, vĩ độ và kinh độ rồi chọn **Lưu thay đổi**.
- **Map** hiển thị ghim địa điểm đã cấu hình, các thiết bị có tọa độ và cảnh báo đang chờ có tọa độ.
- Có thể kéo bản đồ và dùng các điều khiển phóng to/thu nhỏ để xem khu vực.
- Chọn marker cảnh báo để chuyển tới **Live Ops**.
- Nếu chưa nhập tọa độ địa điểm, bản đồ dùng vị trí mặc định của ứng dụng. Marker thiết bị/cảnh báo chỉ xuất hiện khi có tọa độ tương ứng.

## 7. Cấu hình thông báo Telegram

### Chuẩn bị

1. Tạo bot Telegram và lấy bot token từ BotFather.
2. Trên mỗi điện thoại nhận tin, mở bot vừa tạo và gửi `/start`.
3. Xác định Chat ID của từng điện thoại.

### Thiết lập trong SAFESIGHT

1. Mở **Notifications**.
2. Nhập **Bot token** và bật **Gửi thông báo tới điện thoại khi Dispatch**.
3. Chọn **Thêm thiết bị di động**, nhập tên dễ nhận biết và Chat ID, rồi chọn **Thêm**.
4. Dùng **Gửi thử** ở dòng thiết bị để thử riêng một máy, hoặc **Gửi tin thử tới tất cả thiết bị đang bật**.
5. Bật/tắt **Nhận thông báo** riêng cho từng thiết bị. Có thể sửa tên hoặc xóa thiết bị.
6. Chọn **Lưu thay đổi** để lưu cấu hình Notifications.

Chỉ thiết bị đang bật nhận thông báo mới nhận tin Dispatch hoặc tin thử gửi tới tất cả. Hãy giữ bot token riêng tư; không chia sẻ token trong ảnh chụp màn hình, tài liệu công khai hoặc kho mã nguồn. Nếu token bị lộ, hãy thu hồi và tạo token mới bằng BotFather.

## 8. Tinh chỉnh nhận diện và giao diện

SAFESIGHT dùng weights YOLO cục bộ `models/ss_final_1.pt` với 10 lớp: `axe`, `baseball_bat`, `hammer`, `pistol`, `knife`, `sword`, `rifle`, `machete`, `stick` và `spear`. Các lớp/nhãn lấy từ model đã huấn luyện; lần chạy đầu không cần tải weights từ Hugging Face.
Khung hiển thị được làm mượt, đồng bộ tracking theo thời điểm chụp frame và dự đoán bù độ trễ suy luận tối đa 0,75 giây; video demo nội suy vị trí box theo từng frame phát, camera trực tiếp dùng vận tốc của tâm khung để dự đoán vị trí giữa các lần nhận diện. Cách này giúp box bám chuyển động liên tục hơn; kích thước khung vẫn được làm mượt riêng. Track được giữ tối đa 1 giây khi model tạm bỏ sót. Video demo giữ khung theo frame khi tạm dừng. Viền khung phát hiện dày gấp đôi trước đây. Cảnh báo chỉ dùng kết quả suy luận mới trong 0,35 giây để tránh dùng khung đã lệch khỏi hình Live Ops.

Trong **Settings**:

- **Chế độ tối**: dùng công tắc để chuyển giữa giao diện sáng và tối; thay đổi được lưu ngay.
- **Tên nhân viên trực**: tên này được ghi nhận trong lịch sử thao tác cảnh báo.
- **Phát âm báo khi có cảnh báo mới**: bật/tắt âm báo.
- **Ngưỡng tin cậy theo lớp**: có thể điều chỉnh riêng từ `0` đến `1` cho cả 10 lớp trong Settings. Ngưỡng cao lọc nhiều dự đoán yếu nhưng có thể bỏ sót hung khí thật.
- Khi các lớp khác nhau dự đoán gần như cùng một box, hệ thống chỉ giữ dự đoán confidence cao nhất để tránh vẽ hai nhãn cho cùng một vật thể.
- Các lớp khác nhau được giữ riêng kể cả khi khung phát hiện chồng lấp; hệ thống không còn thay nhãn một lớp bằng lớp khác chỉ vì confidence cao hơn.
- **Số lần nhận diện liên tiếp để tạo cảnh báo**: tăng giá trị để yêu cầu phát hiện ổn định hơn trước khi tạo cảnh báo.
- **Thời gian chờ giữa hai cảnh báo cùng thiết bị**: hạn chế cảnh báo lặp từ cùng một nguồn trong khoảng thời gian cấu hình.
- **Kích thước ảnh (`imgsz`)**: mặc định `320`. Tăng kích thước có thể hỗ trợ vật thể nhỏ/ở xa nhưng làm chậm xử lý.
- **Số lần nhận diện tối đa mỗi giây cho mỗi thiết bị (`detect_fps`)**: mặc định `45`; đây là mức trần, không phải FPS đảm bảo. Nhiều nguồn vẫn dùng chung model/GPU.

Nếu khung nhận diện chậm, giảm `imgsz` hoặc số nguồn chạy đồng thời; đặt `detect_fps` cao hơn thông lượng model không giúp khung cập nhật nhanh hơn. Nếu ứng dụng chạy trên máy có NVIDIA GPU, kiểm tra thông báo khởi động trong Terminal để xác nhận detector dùng GPU; không nên suy ra trạng thái GPU chỉ từ cấu hình card đồ họa.

Chọn **Lưu thay đổi** sau khi chỉnh các trường cấu hình. Nên thay đổi từng nhóm tham số một để dễ so sánh hiệu quả.

## 9. Nhật ký và khắc phục sự cố cơ bản

- Mở **System Log** để xem sự kiện gần đây. **Past Ops** dùng để xem kết quả xử lý từng cảnh báo.
- Nếu giao diện báo mất kết nối, kiểm tra ứng dụng Flask còn chạy trong Terminal hay không và thử tải lại trang.
- Nếu camera offline hoặc không có hình, kiểm tra nguồn video, quyền truy cập webcam/mạng và thông tin URL.
- Nếu bản đồ trống hoặc không tải nền, kiểm tra kết nối Internet vì bản đồ cần tải tài nguyên bên ngoài.
- Nếu Telegram không gửi được, xác nhận bot token, Chat ID, người nhận đã gửi `/start`, tùy chọn gửi thông báo đã bật và thiết bị nhận tin đang được bật.
- Nếu nhận diện chậm, giảm `imgsz`, giảm số nguồn chạy đồng thời hoặc kiểm tra trong Terminal detector có dùng GPU hay không.
