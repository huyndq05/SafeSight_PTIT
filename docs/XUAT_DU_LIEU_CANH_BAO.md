# Xuất dữ liệu cảnh báo và sửa kết quả nhận diện

Trong **Lịch sử xử lý**, chọn trạng thái rồi chọn **Xuất CSV** hoặc
**Xuất CSV + ảnh (ZIP)**. Tất cả gồm cả cảnh báo chờ xác minh. Đã xử lý
gồm các trạng thái đã có thao tác của nhân viên, kể cả nhận diện sai.
Xuất dữ liệu không bị giới hạn 200 cảnh báo như danh sách trên giao diện.

Chọn **Xuất Excel kèm ảnh** để nhận file `.xlsx` có ảnh nhúng trực tiếp,
không cần đường dẫn ảnh bên ngoài. Mỗi dòng có ảnh gốc và ảnh vẽ lại box,
dự đoán AI, loại thực tế, lý do, người xử lý và thông tin gửi thông báo.
Ảnh nhúng là bản xem trước thu nhỏ giữ tỉ lệ; dùng ZIP nếu cần ảnh gốc
đầy đủ độ phân giải cho việc rà soát và bổ sung dữ liệu train.

CSV dùng UTF-8 BOM để Excel đọc đúng tiếng Việt, mỗi hàng tương ứng một
ảnh ban đầu hoặc bằng chứng. ZIP chứa `alerts.csv`, `images/` và README.
Đường dẫn `image_path` tương đối với gói ZIP; `image_url` là liên kết trong
app và cần phiên đăng nhập. `image_exists=0` nghĩa là ảnh hiện không còn.

Các cột quan trọng:

- `predictions_json`: loại, điểm tin cậy và box do AI dự đoán trên ảnh đó.
- `review_reason`, `review_note`: lý do và ghi chú của nhân viên.
- `actual_label`: loại thực tế do nhân viên chọn; trống là chưa xác định,
  `background` là nhân viên xác nhận không có hung khí.
- `handled_by`, `handled_at`: người và thời điểm xử lý.
- `notification_status`, `notification_info`: việc gửi thông báo, độc lập
  với kết luận đúng/sai của nhân viên.
- `events_json`: lịch sử thao tác, bao gồm ghi chú cũ trước khi bổ sung
  các trường review có cấu trúc.

Khi cảnh báo sai loại hoặc sai đối tượng, chọn **Đánh dấu nhận diện sai**,
chọn lý do và loại thực tế nếu xác định được. Có thể cập nhật kết luận
ngay cả sau khi thông báo đã được gửi; lịch sử gửi không bị xóa và hệ
thống không tự gửi thông báo đính chính. Không đánh dấu khi đang gửi.

Quy trình vận hành đề xuất: nhận cảnh báo như một nghi vấn, xem ảnh/bằng
chứng và xác minh trước khi xác nhận/chuyển tiếp. Nếu đã chuyển tiếp rồi
mới phát hiện nhầm, ghi rõ nhận diện sai và thực hiện đính chính theo
quy trình của đơn vị; không coi thao tác lưu review là đã thu hồi tin gửi.

Để bổ sung train, ưu tiên ZIP của nhóm nhận diện sai. Rà soát lại từng ảnh,
sửa box và nhãn; một kết luận trên cảnh báo không tự động là nhãn đúng
cho mọi vật trong mọi ảnh bằng chứng. Chia tập theo video/buổi quay để
tránh rò rỉ. Không tự động lấy dự đoán AI làm nhãn chuẩn.

**Xóa cảnh báo** là xóa thật cả dữ liệu/ảnh liên quan: không dùng thao tác
này nếu muốn giữ ảnh để bổ sung dữ liệu huấn luyện sau này.
