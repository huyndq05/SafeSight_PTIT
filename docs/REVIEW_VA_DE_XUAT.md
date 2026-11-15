# Rà soát SafeSight

## Video tải lên

Video phát trong trình duyệt, ảnh JPEG được gửi tuần tự tới Flask để detect.
Trong thời gian chờ kết quả, video tiếp tục chạy. Vì vậy box luôn xuất phát từ
một ảnh cũ; đặt detect_fps=45 chỉ đặt mức trần, không đảm bảo 45 kết quả/giây.

Bản sửa ở static/js/app.js:

- Dùng requestVideoFrameCallback khi trình duyệt hỗ trợ để vẽ theo thời gian
  khung hình được trình bày, có requestAnimationFrame làm phương án dự phòng.
- Bỏ lớp làm mượt tâm thứ hai, vốn làm box chậm thêm sau bước nội suy/dự đoán.
- Bù chuyển động theo hai kết quả gần nhất trong tối đa 0,5 giây; giới hạn vận
  tốc và loại dữ liệu cũ để tránh dự đoán vô hạn.
- Giữ box qua một lần detect hụt ngắn, tối đa 0,2 giây từ lần thấy cuối.
- Bỏ kết quả cũ sau thao tác tua; dừng lên lịch khi phần tử video đã bị gỡ.

Đây là dự đoán vận tốc, không phải theo dõi chuyển động bằng ảnh. Vật thể đổi
hướng đột ngột, che khuất hoặc đổi lớp vẫn có thể làm box nhảy. Nếu thời gian
xử lý thường xuyên vượt 0,5 giây, cần tăng tốc suy luận hoặc chuyển sang phát
video đã xử lý trước để đảm bảo box khớp từng frame. Chưa xác minh trực quan
vì data/videos không có video mẫu.

Kiểm tra: python -m unittest discover -s tests -v; node --check static/js/app.js;
node tests/test_video_overlay.cjs.

## Model

Đã đọc ss_final_1.pt bằng Ultralytics: YOLO26m, 21.788.308 tham số; 10 lớp
khớp cấu hình. Metadata lưu imgsz=640; cấu hình chạy mặc định là 320.
torch.cuda.is_available() trong .venv trả về False tại thời điểm kiểm tra.
Benchmark sơ bộ trên ảnh đen 1280x720, đầu vào 320, CPU, sau warm-up:
5 lần mất 114,2–149,5 ms, trung bình 125,5 ms (xấp xỉ 8 lần/giây).
Đây chỉ là đo tổng thời gian predict trên ảnh tổng hợp; chưa bao gồm truyền
JPEG, Flask, lưu cảnh báo hoặc tải đồng thời nhiều nguồn.
Không có dataset, nhãn kiểm thử hay kết quả validation trong repo để kết luận
độ chính xác hoặc cặp lớp nào nhầm nhiều nhất. Không sửa/training lại weights.

Đề xuất thực hiện theo thứ tự:

1. Thu thập các đoạn video nhận nhầm và bỏ sót từ camera thực tế. Gắn nhãn đúng
   lớp/box, bổ sung cảnh không có hung khí và các vật dễ nhầm như điện thoại,
   dụng cụ, ô. Rà lại quy ước phân biệt knife/machete/sword, stick/baseball_bat.
2. Chia train/val/test theo video, camera hoặc phiên quay, tránh để frame liền
   nhau xuất hiện ở nhiều tập. Đo precision, recall và confusion matrix từng lớp.
3. Chọn ngưỡng từng lớp từ validation. Tăng ngưỡng lớp hay báo nhầm có thể giảm
   báo giả nhưng tăng bỏ sót; không mặc định tăng mọi lớp cùng một mức.
4. So sánh imgsz 320/480/640 trên cùng tập kiểm thử và đo thời gian suy luận.
   Chỉ tăng độ phân giải nếu lợi ích về vật thể nhỏ phù hợp ngân sách tốc độ.
5. Fine-tune từ weights hiện có bằng các mẫu đã sửa nhãn; so sánh với baseline
   trên test cố định. Nếu CPU là phần cứng triển khai, benchmark thêm model nhỏ
   và định dạng xuất phù hợp trước khi chọn model mới.

Tham khảo: https://docs.ultralytics.com/guides/model-testing/
và https://docs.ultralytics.com/guides/model-evaluation-insights/

## Các điểm khác cần ưu tiên

- streams.py xác nhận cảnh báo bằng chuỗi frame có bất kỳ detection nào. Hai
  frame liên tiếp có thể thuộc hai vật thể khác nhau; nên xác nhận theo track
  và lớp trước khi dùng cho cảnh báo thực tế.
- model.py lọc trùng chéo tất cả các lớp, kể cả trường hợp một box gần như nằm
  trong box khác. Quy tắc này có thể loại vật thể thật khi hai hung khí chồng
  lên nhau. Cần đánh giá trên dữ liệu có nhiều vật thể trước khi nới/siết NMS.
- Các nguồn dùng chung khóa suy luận của model. Nhiều camera/video có thể làm
  tăng thời gian chờ; cần đo độ trễ đầu-cuối theo nguồn, không chỉ FPS hiển thị.
- screen.py và luồng camera cũng vẽ dự đoán từ kết quả bất đồng bộ. Với chuyển
  động phi tuyến, dự đoán vận tốc không bảo đảm bám đúng ảnh; cần benchmark
  riêng, tránh đánh đồng FPS preview với FPS nhận diện.
