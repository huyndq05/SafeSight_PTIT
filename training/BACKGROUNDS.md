# Bổ sung 350 ảnh nền nhãn rỗng

Đã chuẩn bị tại `E:/datasets/safesight_backgrounds_350`.

## Kết quả

- 350 ảnh và 350 file `.txt` rỗng, đúng 0 byte; không thêm lớp background hoặc person.
- Người và các đồ vật thường được bỏ qua trong nhãn của các ảnh này.
- 280 ảnh train, 35 validation, 35 test. 15 nhóm đều có ảnh trong cả ba tập.
- Cấu hình ghép với dữ liệu gốc: `E:/datasets/safesight_backgrounds_350/data.with_backgrounds.yaml`.
- Cấu hình mới dùng các ảnh có nhãn vật thể từ bộ gốc, bỏ qua 449 ảnh nền cũ để tổng ảnh nền đúng 350. File dữ liệu gốc không bị sửa/xóa. Không cần sao chép lại 35 nghìn ảnh cũ.

| Nhóm dùng để lựa ảnh, không phải lớp nhận diện | Số ảnh |
| --- | ---: |
| Bút | 31 |
| Điện thoại | 40 |
| Ví | 14 |
| Túi xách | 26 |
| Ghế | 35 |
| Bàn | 35 |
| Laptop | 32 |
| Máy tính bảng | 9 |
| Sách | 30 |
| Chai | 26 |
| Ô | 25 |
| Bàn phím | 25 |
| Chuột | 16 |
| Điều khiển | 3 |
| Đèn pin | 3 |

## Kiểm tra và giới hạn

Đã tải 400 ứng viên từ Open Images validation và LVIS/COCO, giữ thông tin nguồn trong `candidates.json`. Xem toàn bộ 400 ảnh qua 20 contact sheet, mở lớn các trường hợp không rõ và xem 60 vùng dự đoán có confidence cao nhất của model cũ. Loại 20 ảnh do dao thật, dao ăn/dụng cụ khó xác định, bối cảnh quá nhỏ hoặc ảnh tương tự. Một ảnh flat-lay có dao gấp mở được phát hiện và loại bỏ.

Không có ứng viên bị DCT pHash đánh dấu gần 35.892 ảnh gốc ở ngưỡng Hamming ≤ 6. Không có ảnh gần trùng nội bộ được phát hiện ở cùng ngưỡng trong các ứng viên được chấp nhận. Đây là kiểm tra theo heuristic, không bảo đảm tìm được mọi crop hoặc biến đổi.

Model cũ dự đoán ít nhất một lớp vũ khí ở confidence ≥ 0,2 trên 147/400 ứng viên, trong đó có chuột bị dự đoán là knife và điện thoại thành pistol. Bộ 350 ảnh được chọn có 143 ảnh thuộc nhóm model đánh dấu; đây là mẫu âm tính khó được chọn có chủ đích, không phải ước lượng tỷ lệ báo sai trên thực tế. Đã kiểm tra nội dung ảnh trước khi chấp nhận; không dùng việc model không detect làm bằng chứng ảnh không có vũ khí.

Đã xác minh số lượng, cặp ảnh/nhãn, nhãn 0 byte và SHA256 không trùng giữa ba tập. Không thể cam kết tuyệt đối rằng không có vật rất nhỏ/che khuất bị bỏ sót khi duyệt. Ảnh cảnh rộng có thể chứa đồ vật nhóm chính ở kích thước nhỏ.

Các tập **dương tính** vẫn giữ cách chia cũ, bao gồm vấn đề rò rỉ ảnh đã ghi ở `AUDIT_ORIGINAL.md`; cấu hình này chưa sửa toàn bộ việc chia dữ liệu và không chứng minh khả năng nhận diện ở 2–3 m. Chưa train hoặc thay weights.

## Sử dụng

```powershell
venv\Scripts\python.exe train.py --data E:/datasets/safesight_backgrounds_350/data.with_backgrounds.yaml --mode check
```

Khi huấn luyện sau này, dùng YAML trên để có cả dữ liệu dương tính và ảnh nền. Không train chỉ trên 350 ảnh nhãn rỗng. `selected.json` lưu nguồn, SHA256, nhóm lựa ảnh, trạng thái duyệt và split cho từng ảnh.

Nguồn: https://storage.googleapis.com/openimages/web/download_v7.html và https://github.com/lvis-dataset/lvis-api . Metadata ảnh Open Images và metadata license/nguồn COCO của ảnh ví được giữ trong manifest.
