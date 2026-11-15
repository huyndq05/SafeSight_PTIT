# Cascade nhận diện

App (camera, video demo) và `screen.py` cùng gọi `WeaponDetector.detect()`.

1. Quét toàn ảnh bằng `ss_final_2.pt`, kích thước theo cấu hình hiện tại.
   Ngưỡng lấy ứng viên bằng 70% ngưỡng riêng của class.
2. Ứng viên đạt ít nhất 0.85 và ngưỡng class được đi thẳng.
   Các ứng viên còn lại được cắt thêm 25% ngữ cảnh mỗi phía và kiểm tra
   lại bằng cùng model ở kích thước 320. Mỗi lượt kiểm tra tối đa hai crop,
   ưu tiên confidence cao. Ứng viên vượt ngân sách bị bỏ trong lượt đó.
3. Chỉ giữ kết quả crop cùng class, confidence đạt ngưỡng class,
   IoU với ứng viên gốc ít nhất 0.3 và trung bình nhân hai confidence
   đạt ngưỡng class. Tọa độ crop được chuyển về toàn ảnh.
4. Kết quả đi qua tracker/luồng xác nhận cảnh báo hiện có. Screen chỉ
   hiển thị qua tracker; không có tầng phát cảnh báo mới. Cơ chế
   `confirm_frames` của app hiện có không phải xác nhận danh tính từng vật.

Đây là cascade kiểm tra lại cùng weights trên hai vùng nhìn, không phải
hai model độc lập. Confidence tổng hợp là điểm lọc, không phải xác suất
được hiệu chuẩn. Chưa có bằng chứng cải thiện precision/recall thực tế;
cần so sánh trên cùng video có nhãn, đặc biệt lúc nhiều vật giao nhau.
Crop có thể làm mất ngữ cảnh; ngân sách hai crop có thể bỏ sót khi đông vật.
Tải tối đa mỗi lần detect là một lượt toàn ảnh và hai lượt crop.
Camera chấp nhận kết quả tối đa 1 giây tuổi khi cascade bật (trước đây
0.35 giây) để tránh bỏ toàn bộ cảnh báo chỉ vì thêm lượt kiểm tra crop.
Kết quả cũ hơn giới hạn vẫn không dùng để tạo cảnh báo/bằng chứng.

Các hằng số `CASCADE_*` nằm trong `weapon_detection/config.py`. Đặt
`CASCADE_ENABLED = False` để quay về một lượt nhận diện. Khởi động lại
app và screen sau khi đổi cấu hình. Không có cache xác minh dùng chung
giữa camera hoặc giữa các khung hình.
