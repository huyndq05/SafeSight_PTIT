# Kiểm tra dữ liệu gốc SafeSight — 11/11/2026

Nguồn: `C:/Users/quang/OneDrive/Desktop/safesight_data_final/final_data`.

## Kiểm tra toàn bộ

| Tập | Số ảnh | Ảnh nhãn rỗng |
| --- | ---: | ---: |
| Train | 29.469 | 370 |
| Validation | 4.154 | 58 |
| Test | 2.269 | 21 |
| Tổng | 35.892 | 449 |

Không phát hiện ảnh không đọc được, nhãn thiếu/thừa, ID lớp sai hoặc tọa độ không hợp lệ. Đây là kiểm tra cú pháp, chưa xác nhận mọi nhãn đúng về nội dung. Có 5.612 đối tượng dùng nhãn polygon hợp lệ. Số đếm ảnh và đối tượng từng lớp khớp `class_counts.csv` khi tính cả polygon.

## Trùng ảnh và độ độc lập của test

Có 192 nhóm ảnh trùng pixel; 146 nhóm xuất hiện ở nhiều tập, gồm tổng 592 lượt ảnh. Đây không phải 592 ảnh cần xóa: mỗi nhóm cần giữ bản phù hợp và kiểm tra nhãn.

| Cặp tập | Nhóm trùng pixel | Ảnh tập sau giống tập trước |
| --- | ---: | ---: |
| Train / validation | 114 | 175 |
| Train / test | 70 | 91 |
| Validation / test | 58 | 74 |

Các nhóm có thể giao nhau, không cộng trực tiếp các hàng. Chi tiết tại `training/audit_original/audit.json` và `manifest.jsonl`.

Danh sách `training/audit_original/test_without_exact_overlap.txt` giữ 2.159 ảnh test sau loại trùng train/validation và trùng nội bộ test. Danh sách này **vẫn chưa phải test độc lập theo video/mẫu vật**.

Mẫu ngẫu nhiên 12 ảnh mỗi lớp stick/spear trong train và test có người, đồ vật và bối cảnh rất giống nhau. Chưa có video ID để chia lại chắc chắn; chưa tìm gần trùng toàn bộ ảnh. Đây là bằng chứng cần kiểm tra việc chia dữ liệu, chưa chứng minh mức overfitting của model.

## Mốc đánh giá model hiện tại

Đã chạy `ss_final_1.pt` trên 2.269 ảnh test gốc, imgsz=640, batch=2, GPU CUDA. Kết quả trên tập có rò rỉ ảnh không dùng để cam kết chất lượng ở 2–3 m.

| Lớp | Precision | Recall | AP50 | AP50–95 |
| --- | ---: | ---: | ---: | ---: |
| Trung bình | 0,919 | 0,886 | 0,932 | 0,757 |
| axe | 0,972 | 0,989 | 0,994 | 0,844 |
| baseball_bat | 0,881 | 0,663 | 0,772 | 0,489 |
| hammer | 0,918 | 0,863 | 0,934 | 0,755 |
| pistol | 0,931 | 0,889 | 0,931 | 0,765 |
| knife | 0,922 | 0,903 | 0,962 | 0,804 |
| sword | 0,913 | 0,904 | 0,950 | 0,810 |
| rifle | 0,850 | 0,866 | 0,885 | 0,589 |
| machete | 0,898 | 0,891 | 0,941 | 0,757 |
| stick | 0,964 | 0,941 | 0,982 | 0,918 |
| spear | 0,940 | 0,951 | 0,974 | 0,838 |

Biểu đồ tại `runs/weapon_eval/original_baseline_640`; log tại `training/baseline_original_640.log`. Loader loại một nhãn sword trùng, còn 2.833 đối tượng khi đánh giá. Không thay weights triển khai.

Trong confusion matrix được sinh, khoảng 19% đối tượng stick được ghép thành spear. Ma trận này và bảng precision/recall có thể dùng điểm ngưỡng khác nhau; không diễn giải chúng như cùng một operating point. Cần đánh giá lại ở ngưỡng triển khai và trên mẫu vật mới.

## Ảnh ứng viên bổ sung

Đã tải 209 ảnh Open Images validation vào `E:/datasets/safesight_candidates/openimages_validation`, cùng manifest, 209 hồ sơ attribution và 9 contact sheet. Không tìm thấy trùng byte/pixel chính xác với dữ liệu gốc; chưa loại gần trùng.

Nguồn nhãn có baseball_bat 18 ảnh, rifle 97, knife 63, pistol 20, sword 25, hammer 1. Một ảnh có thể chứa nhiều lớp. Lần tải này chưa bổ sung axe/machete/stick/spear.

Đã xem contact sheet đầu tiên: nhãn Rifle có cả súng săn; Knife có vật có thể thuộc machete/sword. Không nhập tự động nhãn nguồn vào SafeSight. Tập này chỉ để duyệt, chưa xuất thành dataset train.

Nguồn: https://storage.googleapis.com/openimages/web/download_v7.html

## Việc còn lại trước khi fine-tune

1. Duyệt và sửa ánh xạ nhãn, bổ sung ảnh đủ 10 lớp với mẫu vật/camera/bối cảnh khác dữ liệu cũ.
2. Chia theo nhóm video/buổi quay/mẫu vật. Thu test riêng ở 2–3 m từ camera thực, giữ các biến thể chưa dùng train.
3. Tạo bản dữ liệu dẫn xuất, thống nhất polygon/bounding box và xử lý ảnh trùng. Không chỉnh nhãn nguồn trực tiếp.
4. Chạy smoke train đo VRAM, rồi fine-tune và so sánh từng lớp trên cùng test độc lập.

**Chưa huấn luyện model mới.**
