# Rà soát giao diện SafeSight

## Phạm vi

Rà soát giao diện giám sát, xử lý cảnh báo, lịch sử, tổng quan, camera,
drone, robot, bản đồ, địa điểm, thông báo, cài đặt và nhật ký. Kiểm tra
desktop 1600×1000, laptop 1280×800, tablet 768×1024 và điện thoại 390×844
bằng dữ liệu thử trong cơ sở dữ liệu riêng. Không chỉnh dữ liệu vận hành.

## Đã điều chỉnh

- Chuẩn hóa chiều cao thanh trên, khoảng cách và chiều rộng vùng nội dung.
- Menu trên tablet/điện thoại dùng thanh icon và ngăn mở theo yêu cầu;
  chuyển trang/chọn mục con sẽ đóng ngăn để tránh che nội dung.
- Đưa truy cập tài khoản nhân viên vào sidebar cho quản trị viên, giữ
  thao tác đổi ca trên thanh trên ở màn hình nhỏ.
- Bỏ chiều cao cố định 42 px ở thanh camera video demo; nút chọn phiên bản,
  xử lý và tiến trình có thể xuống hàng mà không bị cắt.
- Hàng chờ cảnh báo có chiều cao theo nội dung và giới hạn cuộn,
  không kéo dài một khối rỗng bằng toàn bộ vùng camera.
- Phân bổ lại cột bằng chứng, hàng chờ và thao tác; tablet ưu tiên ảnh.
- Thu gọn thẻ thống kê, khoảng cách biểu đồ, khoảng cách hàng cài đặt.
- Nút lưu cài đặt luôn dễ tìm khi cuộn. Các bảng và bản đồ có giới hạn
  chiều cao phù hợp với viewport; bảng rộng cuộn trong vùng riêng.
- Giữ tông cam đất/xám ấm, chấm online xanh lá và offline đỏ.

Không phóng giãn video hoặc ảnh để lấp khoảng trống: vùng đen do khác tỉ lệ
ảnh vẫn được giữ để không cắt vật thể hay làm lệch box nhận diện. Màn hình
ít dữ liệu cũng không được chèn nội dung giả chỉ để lấp đầy chiều cao.

## Đề xuất phát triển

1. **Hàng đợi xử lý video:** hiển thị các tác vụ, thời gian dự kiến, hủy/tạm
   dừng và tiếp tục từ checkpoint sau khi khởi động lại. Hiện tại tác vụ
   đang quét chưa có cơ chế tiếp tục giữa chừng.
2. **Quản lý ca trực:** bàn giao các cảnh báo chưa xử lý, ghi giờ nhận/kết
   thúc ca, đổi/reset mật khẩu và vô hiệu hóa tài khoản. Hiện đã có đăng
   nhập/đổi ca và ghi tên người thao tác; chưa có quy trình bàn giao đầy đủ.
3. **Phân trang dữ liệu lớn:** phân trang phía server cho lịch sử/nhật ký,
   bộ lọc theo nhân viên, nguồn và khoảng thời gian; kiểm tra lại hiệu năng
   khi có hàng nghìn cảnh báo thay vì chỉ dữ liệu thử nhỏ.
4. **Chẩn đoán camera:** xem thử trước khi thêm, tên thiết bị, độ trễ và
   nguyên nhân mất tín hiệu để phân biệt lỗi nguồn với lỗi nhận diện.
5. **Đánh giá model:** tập video có nhãn độc lập, thống kê bỏ sót/báo nhầm
   theo class và khoảng cách, liên kết các trường hợp sai với ảnh bằng
   chứng; không dùng độ mượt giao diện thay cho độ chính xác.
6. **Bảo trì giao diện:** tách stylesheet theo thành phần và gom các quy
   tắc responsive đang kế thừa nhiều lần để giảm xung đột khi phát triển.

## Giới hạn kiểm tra

Kiểm thử trình duyệt xác nhận luồng thao tác và không tràn ngang ở các
kích thước trên. Chưa thay thế kiểm tra dài hạn trên dữ liệu thật, hàng
chục camera, video dài, mạng chậm hoặc mọi loại màn hình/DPI.
