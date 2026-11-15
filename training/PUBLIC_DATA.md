# Chuẩn bị dữ liệu công khai SafeSight

Thư mục dữ liệu: `E:/datasets/safesight_candidates`. Các tập này phục vụ duyệt và sửa nhãn, **chưa phải dataset sẵn sàng huấn luyện**.

## Kết quả đợt chuẩn bị

Đã tải 4.312 ảnh từ ba nguồn. Có 4.126 nội dung pixel riêng biệt. Manifest tổng hợp: `E:/datasets/safesight_candidates/public_review_manifest.json`; số liệu: `public_review_summary.json`.

| Trạng thái | Số ảnh |
| --- | ---: |
| Chờ duyệt nhãn và ánh xạ lớp | 3.966 |
| Giữ riêng vì gần giống ảnh cũ | 147 |
| Giữ riêng vì trùng pixel với ảnh ứng viên khác | 186 |
| Giữ riêng sau xem hình: hình minh họa/mô hình nhỏ/cơ cấu không phải dụng cụ | 13 |

151 ảnh bị pHash đánh dấu gần ảnh cũ trước khi phân loại trạng thái; 4 ảnh trong số đó đã được xếp vào nhóm trùng pixel nội bộ. Không cộng 151 vào 186 để tính số loại bỏ cuối cùng.

Số ảnh theo **nhãn đề xuất, chưa xác nhận** trong nhóm 3.966 ảnh chờ duyệt:

| Lớp đề xuất | Ảnh có lớp |
| --- | ---: |
| axe | 6 |
| baseball_bat | 842 |
| hammer | 26 |
| pistol | 744 |
| knife | 808 |
| sword | 43 |
| rifle | 839 |
| machete | 715 |
| stick | 14 |
| spear | 3 |

Một ảnh có thể có nhiều lớp. `Gun → pistol` chỉ là ánh xạ đề xuất để lập danh sách duyệt, chưa được dùng tạo nhãn train. Đã xem cả 6 contact sheet LVIS (103 ảnh); ảnh nhỏ/box mơ hồ vẫn cần xem ở độ phân giải gốc. Các ảnh còn lại không được mặc nhiên coi là đã duyệt chỉ vì chưa bị giữ riêng.

Đặc biệt, 3 ảnh giáo và 14 ảnh gậy chưa đủ giải quyết yêu cầu đa dạng kiểu dáng. Những nguồn cần tiếp cận thêm: [Roboflow stick/spear/sword](https://universe.roboflow.com/datalabel-vi0wl/weapon-03d2n) (đường tải hiện trả 403 từ môi trường này), [ChineseMPD](https://pmc.ncbi.nlm.nih.gov/articles/PMC11325024/) (bài công bố hướng dẫn đăng ký ScienceDB để tải; còn cần ánh xạ nhãn và kiểm tra miền ảnh phim). Chưa tải hoặc đưa hai nguồn này vào manifest.

## Dangerous Items — Zenodo 11582054

- Nguồn: https://zenodo.org/records/11582054 ; metadata công bố CC BY 4.0, giữ citation trong `source.json`.
- Đã tải archive 358.059.123 byte và xác minh MD5 với metadata Zenodo.
- `zenodo_11582054/prepared`: 4.000 ảnh, 4.379 đối tượng. Nhãn nguồn: Machete 879 box, Knife 880, Baseball Bat 872, Rifle 875, Gun 873.
- Không phát hiện lỗi box hoặc ảnh không đọc được. Không có ảnh trùng pixel chính xác với dữ liệu cũ; có 186 ảnh trùng nội bộ ngoài bản đầu tiên.
- Kiểm tra pHash đánh dấu 124 ảnh có khả năng gần trùng dữ liệu cũ. Mẫu cặp ảnh đã xem cho thấy một số là cùng ảnh sau thay đổi kích thước/nén/watermark. Toàn bộ 124 ảnh chưa được duyệt thủ công.
- Đã xem 12 mẫu Machete và 12 mẫu chứa Gun; có biến thể hình dáng/bối cảnh, nhưng còn box cần kiểm tra. Không coi nhãn Gun mặc nhiên là pistol cho toàn bộ bộ dữ liệu.
- Script chuẩn bị: `prepare_zenodo_candidates.py`. Đây là script kiểm tra và tạo manifest, không xuất YAML train.

## Open Images validation

- Nguồn: https://storage.googleapis.com/openimages/web/download_v7.html
- `openimages_validation`: 209 ảnh, metadata attribution theo từng ảnh, manifest và 9 contact sheet.
- Không trùng pixel chính xác với bộ cũ. Có 27 ảnh bị pHash đánh dấu gần trùng và cần duyệt.
- Nhãn nguồn Knife/Rifle rộng hơn ranh giới nhãn hiện tại: mẫu đã xem có mã tấu/kiếm và súng săn. Cần phân loại lại thay vì gộp tự động.
- Script: `download_openimages_candidates.py`.

## LVIS train — nguồn bổ sung lớp ít mẫu

- Nguồn chính: https://github.com/lvis-dataset/lvis-api ; annotation archive: https://dl.fbaipublicfiles.com/LVIS/lvis_v1_train.json.zip
- Trong toàn bộ train LVIS v1 có 8 box ax, 41 hammer, 9 spear, 72 sword và 21 walking_stick; tổng hợp thành 103 ảnh ứng viên. Đây là số box, không phải số ảnh từng lớp.
- Đã tải thành công 103/103 ảnh. Phân bố ảnh nguồn: axe 7, hammer 26, spear 4, sword 52, stick 14; không trùng pixel hoặc bị pHash đánh dấu gần dữ liệu cũ ở ngưỡng đang dùng. Phân bố trước khi duyệt hình, khác với bảng chờ duyệt ở trên.
- Walking stick chỉ là một nhóm nhỏ của stick. Nhãn LVIS có thể không đầy đủ cho mọi lớp trong ảnh; phải xem lại các vật SafeSight khác trước khi xuất YOLO.
- Giữ metadata ảnh COCO và nhãn gốc trong manifest. Chưa xác minh khoảng cách camera hoặc khả năng khái quát sang CCTV.
- Script: `download_lvis_candidates.py`, cần `ijson` trong `training/requirements.txt`. Script đọc annotation theo luồng để tránh nạp hơn 1 GB JSON vào RAM cùng lúc.

## Kiểm tra gần trùng

`audit_near_duplicates.py` dùng DCT pHash 64 bit, ngưỡng Hamming ≤ 6. Kết quả là gợi ý để duyệt, không phải chứng minh ảnh trùng. Có thể bỏ sót crop hoặc phát hiện nhầm các vật có hình dáng giống nhau. Không xóa ảnh tự động.

Ảnh và nhãn nguồn được giữ riêng với bộ dữ liệu cũ. Chưa trộn vào train, chưa huấn luyện và chưa thay trọng số ứng dụng. Cần duyệt nhãn, loại trùng, gom nhóm video/mẫu vật và chia tập trước khi fine-tune. Dữ liệu công khai hiện có chưa đủ chứng minh chất lượng ở khoảng cách 2–3 m.
