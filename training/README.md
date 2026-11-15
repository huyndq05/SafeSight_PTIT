# Huấn luyện SafeSight v2

Đã nhận dữ liệu cục bộ và chạy đánh giá model cũ. Xem [báo cáo kiểm tra dữ liệu gốc](AUDIT_ORIGINAL.md) để biết tình trạng mới nhất; các thông tin bên dưới mô tả bước chuẩn bị ban đầu.

Đã tải và lọc sơ bộ dữ liệu công khai bổ sung: xem [PUBLIC_DATA.md](PUBLIC_DATA.md). Chưa chạy train mới.

## Hiện trạng kiểm tra ngày 11/11/2026

- Checkpoint hiện tại: YOLO26m, 21.788.308 tham số, 10 lớp; cấu hình cũ dùng ảnh 640, epochs=35 và time=11 giờ. Đây là cấu hình lưu trong checkpoint, không phải bằng chứng đã chạy đủ 35 epoch.
- `venv/Scripts/python.exe`: PyTorch 2.14.1+cu130, CUDA hoạt động. `.venv` hiện là bản CPU.
- RTX 3050 Laptop có 4 GB VRAM. Batch 2 / imgsz 640 là cấu hình thử ban đầu, chưa đo bộ nhớ khi train. Nếu hết VRAM, thử batch 1; model m có thể cần GPU lớn hơn.
- Chưa có dataset huấn luyện trong repo; chưa train model mới. Không thể xác nhận overfitting nếu thiếu dữ liệu và kết quả trên tập độc lập.

## Nguồn dữ liệu ứng viên — chưa tải, chưa duyệt ảnh/nhãn

| Nguồn | Phạm vi và việc cần làm |
| --- | --- |
| [Open Images V7](https://storage.googleapis.com/openimages/web/download_v7.html) | Danh sách boxable có Axe, Baseball bat, Hammer, Handgun, Knife, Rifle, Sword. Không bao phủ đủ 10 lớp. Phải kiểm tra Knife/Kitchen knife/Dagger trước khi ánh xạ; không tự gộp Shotgun vào rifle. Giữ attribution theo từng ảnh. |
| [datalabel / weapon](https://universe.roboflow.com/datalabel-vi0wl/weapon-03d2n) | Trang công bố 801 ảnh, stick/spear/sword, CC BY 4.0. Ưu tiên kiểm tra có trùng bộ cũ, ảnh thật hay game/ảnh sản phẩm, chất lượng box và biến thể stick. |
| [Swetha Nair L / weapon](https://universe.roboflow.com/swetha-nair-l-amu3a/weapon-jmeyk-unyl3) | Trang công bố 592 ảnh, 23 lớp, CC BY 4.0. Chỉ là ứng viên; cần kiểm tra miền ảnh và ánh xạ nhãn thủ công. |
| [OD-WeaponDetection](https://github.com/ari-dasci/OD-WeaponDetection) | Có bộ pistol/knife detection và vật cầm tay dễ nhầm. Chọn bản detection, không dùng nhãn classification như bounding box. Đối chiếu giấy phép của gói thực tải. |

Ngày đăng mới không bảo đảm dữ liệu khác bộ cũ hoặc phù hợp camera. Không có nguồn nào trên đây đã được xác minh đạt yêu cầu khoảng cách 2–3 m.

## Quy trình dữ liệu

1. Lấy bộ cũ hoặc notebook/manifest nguồn. Lưu nguồn, phiên bản, giấy phép và ID ảnh của mỗi bộ mới.
2. Chốt quy tắc nhãn: stick gồm những loại gậy/ống/thanh nào; phân biệt baseball_bat; spear cần mũi giáo; sword/machete/knife có ranh giới nhất quán. Không chuyển toàn bộ lớp `weapon`, `gun`, `long_gun` thành rifle.
3. Duyệt ảnh thật, các góc cầm, vật bị che, độ dài/màu/chất liệu khác nhau. Gán nhãn mọi vật thuộc 10 lớp trong ảnh; nhãn thiếu có thể khiến mô hình học vật đó là nền.
4. Bổ sung ảnh âm tính và vật dễ nhầm: ô, chổi, dụng cụ, đồ chơi, điện thoại. Không dùng ảnh có hung khí chưa gán nhãn như ảnh âm tính.
5. Loại trùng và gần trùng trước khi chia; giữ mọi frame cùng video, cùng buổi quay và cùng vật thể mẫu vào cùng nhóm. Giữ các mẫu vật chưa xuất hiện trong train cho test để đo khả năng khái quát.
6. Thu một tập riêng bằng camera thực tại 2–3 m, nhiều ánh sáng/bối cảnh, giữ riêng để test. Khoảng cách mét không suy ra chắc chắn từ ảnh Internet; kích thước vật theo pixel và góc nhìn cũng quan trọng.
7. Trộn dữ liệu cũ đã kiểm tra với dữ liệu mới; thống kê số ảnh, số box và kích thước box theo lớp. Không chỉ nhân bản/augmentation một số mẫu rồi coi là dữ liệu đa dạng.

## Chạy sau khi đã chuẩn bị dữ liệu

Copy `training/data.example.yaml` thành YAML riêng, sửa path. Ảnh đặt ở `images/{train,val,test}`, nhãn YOLO ở `labels/{train,val,test}` với cùng tên gốc.

```powershell
venv\Scripts\python.exe train.py --data E:/datasets/safesight_v2/data.yaml --mode check
venv\Scripts\python.exe train.py --data E:/datasets/safesight_v2/data.yaml --mode train --epochs 1 --name smoke_v2
venv\Scripts\python.exe train.py --data E:/datasets/safesight_v2/data.yaml --mode train --name weapons_v2
```

`check` chỉ kiểm tra đường dẫn và thứ tự lớp, không xác thực nhãn/trùng ảnh. Cấu hình train là điểm khởi đầu cần đánh giá, không bảo đảm tốt hơn model cũ. Script mở phiên fine-tune mới từ weights cũ, không resume optimizer của lần train cũ.

## Đánh giá trước khi sử dụng

Đánh giá model cũ và mới trên cùng test, cùng imgsz; chạy riêng ở 320 và 640 để tách ảnh hưởng độ phân giải khỏi ảnh hưởng huấn luyện.

```powershell
venv\Scripts\python.exe train.py --data E:/datasets/safesight_v2/data.yaml --mode val --model models/ss_final_1.pt --imgsz 640 --name baseline_640
venv\Scripts\python.exe train.py --data E:/datasets/safesight_v2/data.yaml --mode val --model runs/weapon_train/weapons_v2/weights/best.pt --imgsz 640 --name candidate_640
```

Xem precision/recall/AP từng lớp, confusion matrix (spear→rifle/sword), false positives trên video không có vũ khí, và recall riêng tập 2–3 m. Chọn checkpoint bằng val; không điều chỉnh lặp lại theo test. Đo FPS trên máy thực. Chỉ thay model triển khai khi kết quả phù hợp; script không ghi đè `models/ss_final_1.pt`.

Tham khảo API: https://docs.ultralytics.com/modes/train/ và https://docs.ultralytics.com/guides/yolo-data-augmentation/.
