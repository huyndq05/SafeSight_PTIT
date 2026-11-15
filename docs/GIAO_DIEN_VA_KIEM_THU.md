# Giao diện và luồng vận hành

Khởi động lại ứng dụng bằng `run.bat` hoặc `.venv\Scripts\python.exe app.py`,
sau đó tải lại trang bằng Ctrl+F5. Các cột thông báo mới được bổ sung tự động
khi khởi động; cảnh báo và bằng chứng hiện có được giữ lại.

## Giám sát

Trang mặc định là **Giám sát trực tiếp**. Chọn loại nguồn hoặc trạng thái kết
nối bằng bộ lọc, chọn số cột bằng **Bố cục**. Nhấp tên nguồn để phóng lớn và
dùng **Trở về dạng lưới** để quay lại. Cột bên phải chứa các cảnh báo đang xử
lý; nhấp một mục để vào màn hình xác minh. Trạng thái trên video phân biệt
trực tiếp, video thử nghiệm, mất kết nối và đang tắt.

Menu chia thành Vận hành, Quản lý và Cấu hình. Thu gọn menu để tăng diện tích
xem hình. Các ô xem trước có cùng kích thước và tỉ lệ 16:9, kể cả khi nguồn
có ảnh dọc hoặc vuông. Khi phóng lớn, hình giữ đúng tỉ lệ gốc, không bị kéo
méo. Bố cục chuyển sang xếp dọc trên màn hình nhỏ.

## Tổng quan

Dashboard tập trung vào cảnh báo hôm nay, số mục chờ xác minh, tổng cảnh báo
chưa hoàn tất và trạng thái nguồn hiện tại. Biểu đồ xu hướng, thống kê vật thể
và nguồn phát sinh cảnh báo dùng cùng khoảng 7 hoặc 30 ngày được chọn. Các số
đếm vật thể là kết quả phát hiện, không phải số hung khí đã được người trực
xác nhận. Khu vực lỗi gửi tin xuất hiện khi có phiên gửi thất bại.

Các thẻ số liệu mở màn hình liên quan; chọn nguồn trong bảng trạng thái để
phóng lớn nguồn đó. Bản thiết kế tham khảo tổ chức thông tin từ
[Milestone XProtect](https://doc.milestonesys.com/xprotect/xprotect-smart-client/2026r1/en/get-statistics-on-alarms)
và [AXIS Camera Station Pro](https://help.axis.com/en-us/axis-camera-station-pro-feature-guide),
giữ nguyên chức năng và luồng SafeSight.

## Xử lý cảnh báo

1. Chọn cảnh báo từ hàng chờ bên trái, xem ảnh và các bằng chứng bổ sung ở giữa.
2. Kiểm tra thông tin bên phải. **Hiển thị nhận diện AI** bật/tắt cả khung lẫn nhãn
   trên ảnh chính và ảnh bổ sung; **Ảnh ban đầu**
   quay lại ảnh phát hiện đầu tiên. Điểm AI không phải kết luận của người trực.
3. Nếu dự đoán sai, chọn **Đánh dấu nhận diện sai**, chọn lý do và bổ sung mô tả.
   Kết quả được lưu vào lịch sử; bằng chứng không bị xóa.
4. Nếu cảnh báo đúng, chọn **Xác nhận & gửi cảnh báo** để xác nhận và gửi ngay
   trong một lần bấm, không cần xác nhận riêng trước.
5. Các cảnh báo đã xác nhận từ phiên cũ vẫn có nút **Gửi thông báo**.
   Nếu Telegram tắt, chỉ ghi nhật ký và giữ trạng thái Đã xác nhận. Nếu gửi lỗi,
   thông tin lỗi được hiển thị và cho phép thử lại. Chỉ đánh dấu Đã gửi thông báo
   khi notifier báo gửi thành công tới các thiết bị đang bật nhận.
6. Chọn **Hoàn tất xử lý** sau khi hoàn thành công việc tại hiện trường. Thao tác
   này độc lập với việc gửi thông báo, và chuyển mục khỏi hàng chờ đang xử lý.

Ghi chú chưa lưu được giữ trong phiên trang khi đổi màn hình hoặc dữ liệu tự
cập nhật; cần bấm **Lưu ghi chú** để lưu vào cơ sở dữ liệu. Tải lại trang sẽ bỏ
bản nháp chưa lưu. **Diễn biến cảnh báo** ghi lại các bước và kết quả gửi.

Thao tác hàng loạt nằm trong mục thu gọn và chỉ áp dụng cho cảnh báo chưa xác
minh. Các cảnh báo đã xác nhận không bị đánh dấu sai bằng thao tác hàng loạt.

Phím D xác nhận và gửi ngay mục đang chọn; phím X mở biểu mẫu nhận diện sai cho
mục chưa xác minh. Phím tắt chỉ hoạt động trên trang Xử lý cảnh báo, khi không
nhập văn bản hoặc mở hộp thoại.

Nếu một lần gửi bị gián đoạn hoặc gửi thành công tới một phần thiết bị, kiểm
tra bên nhận trước khi thử lại vì thiết bị đã nhận có thể nhận thêm tin lặp.
Trạng thái dispatched của dữ liệu cũ được giữ nguyên; không thể suy ra lại
kết quả giao tin của các phiên cũ không lưu thông tin này.

## Kiểm thử

Các lệnh chạy từ thư mục dự án:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/js/app.js
node tests/test_video_overlay.cjs
.venv\Scripts\python.exe tests/ui_smoke.py
```

Kiểm thử trình duyệt cần `playwright` (`python -m pip install playwright`) và
Chrome cài sẵn. Playwright chỉ phục vụ phát triển, không cần cho ứng dụng.
Script tạo SQLite, ảnh và cấu hình riêng trong thư mục tạm; không mở camera,
không dùng database thật và không gửi Telegram thật. Ảnh chụp kiểm thử lưu tại
`%TEMP%\safesight-ui-review`.

Đã kiểm tra:

- 28 kiểm thử Python, gồm chuyển trạng thái, lưu lý do, giữ bằng chứng,
  chặn gửi trùng, gửi lỗi/thử lại, Telegram tắt, phục hồi phiên gửi gián đoạn,
  gửi trực tiếp từ trạng thái pending và thống kê nhất quán theo 7/30 ngày.
- 6 tình huống hồi quy overlay video và kiểm tra cú pháp JavaScript.
- Chrome: xác minh → gửi giả lập → hoàn tất; nhận diện sai kèm lý do; giữ và
  lưu ghi chú; lọc nguồn; lọc lịch sử; điều hướng toàn bộ màn hình; sáng/tối;
  ẩn toàn bộ overlay AI; ô xem trước đồng đều với ảnh ngang/dọc/vuông;
  phóng lớn giữ tỉ lệ ảnh; gửi bằng một lần bấm; chọn kỳ thống kê dashboard.
- Bố cục xác minh ở 1600, 1280, 768 và 390 px; kiểm tra tràn ngang các màn hình
  ở 390 px; không ghi nhận lỗi JavaScript trong kịch bản kiểm thử.

Giới hạn: hình camera và việc gửi thông báo được giả lập trong kiểm thử giao
diện. Chưa kiểm thử giao Telegram thật, camera thật hay nền bản đồ qua mạng.
