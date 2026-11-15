# Video xử lý trước

- Upload video: xem video gốc ngay, không tự động chạy model.
- Bấm **Xử lý video** trên thanh camera để xếp hàng quét từng khung hình.
  Thanh tiến trình và phần trăm nằm trên thanh tên camera. Trong lúc xử lý
  vẫn xem được bản gốc; camera trực tiếp vẫn dùng luồng nhận diện riêng.
- Sau khi hoàn tất, chọn **Video gốc** hoặc **Đã nhận diện** trên cùng thanh.
  Chuyển phiên bản giữ nguyên thời điểm phát; bản gốc không có box hoặc tạo
  cảnh báo từ kết quả đã lưu.
- Kết quả nằm cạnh video tại `data/videos/<video>.detections.json`.
- Khi phát, trình duyệt dùng thời gian của khung hình video để tra bảng kết quả.
  Không gửi ảnh đi suy luận, không dự đoán kéo dài box từ khung cũ.
- Tua và phát lại dùng cùng kết quả đã lưu. Đây là overlay dựng từ bảng kết quả,
  không phải một bản MP4 mới được ghi đè lên video gốc.
- Cảnh báo lúc phát dùng detection đã lưu; backend chỉ đọc ảnh nguồn để lưu bằng
  chứng, không gọi lại model. Quá trình quét trước không tạo cảnh báo.
- Đổi model, ngưỡng, image size hoặc bật thêm class cần bấm **Xử lý lại**.
  Tắt class có hiệu lực lọc hiển thị ngay qua cài đặt giao diện.
- Video demo cũ chưa xử lý cũng chờ người dùng bấm nút. Kết quả hoàn tất
  được giữ lại sau khi khởi động lại. Công việc bị ngắt khi tắt app sẽ chạy lại
  từ đầu khi bấm xử lý lại; kết quả ghi dở không được dùng để phát.

Khởi động lại app bằng `run.bat`, tải lại trang bằng Ctrl+F5 để nạp luồng mới.
