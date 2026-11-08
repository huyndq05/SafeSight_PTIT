# Phân tích cấu trúc và luồng hoạt động SAFESIGHT

> Tài liệu này mô tả mã nguồn đang có trong workspace tại thời điểm kiểm kê. Đường dẫn trong các liên kết là tương đối từ thư mục gốc dự án. Khi mã nguồn thay đổi, số lượng tệp và cách triển khai có thể thay đổi theo.

## 1. Tóm tắt và cách đếm tệp

Trong phạm vi thư mục dự án, loại trừ `.git`, các môi trường Python, cache và các thư mục dữ liệu/model, hiện có **18 tệp mã nguồn và kiểm thử**:

| Loại | Số tệp | Ghi chú |
|---|---:|---|
| Python (`.py`) | 15 | Gồm mã ứng dụng và một tệp kiểm thử. |
| JavaScript (`.js`) | 1 | Toàn bộ điều khiển giao diện nằm trong một tệp. |
| CSS (`.css`) | 1 | Kiểu dáng, bố cục và màu sắc giao diện. |
| HTML (`.html`) | 1 | Khung trang chính do Flask phục vụ. |
| **Tổng** | **18** | Không tính tài liệu, cấu hình, model AI, video, ảnh, database, virtualenv hoặc Git. |

Đây là số tệp mã nguồn, không phải tổng số tệp trong ổ đĩa. Các thư mục như `data/`, `models/`, `.git/`, `.venv/` và `venv/` chứa dữ liệu, model hoặc môi trường chạy nên không được cộng vào con số trên.

## 2. Sơ đồ kiến trúc tổng quát

```text
app.py
  └── weapon_detection/web/app.py             Flask: khởi tạo, HTTP/API, điều phối
       ├── weapon_detection/config.py          Đường dẫn, cài đặt mặc định
       ├── weapon_detection/storage/db.py      SQLite: nguồn, cảnh báo, settings, logs
       ├── weapon_detection/detection/model.py YOLO: inference và chuẩn hóa kết quả
       ├── weapon_detection/detection/streams.py
       │    ├── Camera/URL: đọc video, luồng JPEG và luồng detect
       │    └── Video demo: nhận từng frame do trình duyệt gửi lên
       ├── weapon_detection/notifications/notifier.py
       │    └── Telegram khi Dispatch hoặc khi gửi thử
       ├── templates/index.html                Khung HTML
       └── static/js/app.js + static/css/style.css
            └── giao diện, polling API và thao tác người dùng
```

### Sơ đồ luồng hoạt động đầy đủ

Mã nguồn PlantUML có thể mở/render riêng tại [LUONG_HE_THONG.puml](./LUONG_HE_THONG.puml).

### Các luồng quan trọng

**Khởi động**

1. Python chạy [app.py](./app.py), tệp này gọi `main()` từ [weapon_detection/web/app.py](./weapon_detection/web/app.py).
2. `main()` tạo thư mục lưu ảnh cảnh báo, gọi `db.init()` để khởi tạo/migrate SQLite và nạp cấu hình.
3. Ứng dụng khởi tạo YOLO với weights cục bộ `models/ss_final_1.pt` (10 lớp), rồi khởi chạy worker cho từng nguồn đang bật.
4. Flask phục vụ giao diện và API tại `127.0.0.1:5000`.
5. JavaScript tải settings, gọi refresh định kỳ và dựng các màn hình.

**Camera/URL trực tiếp**

```text
StreamWorker.run()
  ├── đọc frame bằng OpenCV
  ├── tạo JPEG cho /video_feed/<id>
  └── StreamWorker._detect_loop()
        └── WeaponDetector.detect()
              └── StreamWorker._check_alert()
                    └── on_detect() trong web/app.py
                          ├── lưu ảnh và ảnh bằng chứng
                          ├── db.create_alert()
                          └── db.log()
```

Luồng đọc video và luồng nhận diện tách nhau: video có thể tiếp tục được gửi tới giao diện trong khi detector xử lý frame. `detect_fps` là giới hạn tốc độ yêu cầu nhận diện trên mỗi worker, không phải cam kết FPS thực tế. Các worker dùng chung một detector; `WeaponDetector` khóa phần gọi model để tránh nhiều lần inference đồng thời trên cùng model.

**Video demo đã tải lên**

```text
Trình duyệt phát /source_video/<id>
  └── connectDemoVideo() lấy frame khi video đang phát
        └── POST JPEG tới /api/sources/<id>/frame
              ├── WeaponDetector.detect()
              ├── manager.process_demo_detections()
              └── on_detect() nếu đủ điều kiện tạo cảnh báo
```

Khác với nguồn camera trực tiếp, việc lấy frame video demo được điều khiển từ trình duyệt. Vì vậy video demo cần đang phát để gửi frame lên backend nhận diện.

**Xử lý cảnh báo**

```text
db.create_alert() -> status=pending -> giao diện Alerts
  ├── Dispatch -> db.set_status() -> notifier.send_dispatch() -> Telegram tùy cấu hình
  ├── Delete alert -> db.set_status(status=deleted)
  ├── Clear all -> db.clear_pending()
  └── Lưu ghi chú -> db.add_note()
```

Frontend gọi `refresh()` định kỳ để tải nguồn và cảnh báo đang chờ. Cảnh báo mới cập nhật badge, âm báo (nếu bật) và thông báo trên giao diện.

## 3. Danh sách tệp mã nguồn

### Thư mục gốc

#### [app.py](./app.py)

- **Vai trò:** Điểm vào để chạy ứng dụng.
- **Nội dung:** Import `app` và `main` từ `weapon_detection.web.app`; đưa hai tên này vào `__all__`.
- **Hàm:** Không định nghĩa hàm riêng. Khối `if __name__ == "__main__"` gọi `main()` khi chạy `python app.py`.
- **Liên kết:** Mọi khởi tạo thực tế nằm trong `main()` của [weapon_detection/web/app.py](./weapon_detection/web/app.py).
- **Mức độ quan trọng:** Quan trọng để biết lệnh chạy bắt đầu từ đâu; không chứa nghiệp vụ.

### Thư mục `weapon_detection/`

#### [weapon_detection/__init__.py](./weapon_detection/__init__.py)

- **Vai trò:** Đánh dấu `weapon_detection` là Python package.
- **Nội dung:** Hiện rỗng; không có hàm hoặc logic.
- **Có thể bỏ qua** khi đọc luồng nghiệp vụ.

#### [weapon_detection/config.py](./weapon_detection/config.py)

- **Vai trò:** Nơi tập trung hằng số đường dẫn và cấu hình mặc định.
- **Nội dung chính:** `BASE_DIR`, `MODEL_PATH`, danh sách lớp và khóa ngưỡng confidence theo lớp, `ALERT_DIR`, `VIDEO_DIR`, `DB_PATH`, giới hạn kích thước video demo, địa chỉ/port, `DEFAULT_SETTINGS` và `DEFAULT_SOURCES`.
- **Hàm:** Không có.
- **Liên kết:** Được dùng bởi `web/app.py`, `detection/streams.py`, `storage/db.py` và `notifications/notifier.py`.
- **Mức độ quan trọng:** Rất quan trọng khi cần hiểu dữ liệu nằm ở đâu, cấu hình mặc định lấy từ đâu, server chạy địa chỉ nào.
- **Lưu ý:** Cấu hình mặc định không nhất thiết là giá trị đang được dùng; settings đã lưu trong SQLite có thể khác.

#### [weapon_detection/labels.py](./weapon_detection/labels.py)

- **Vai trò:** Giữ tên lớp của model nhất quán ở giao diện và lịch sử.
- **Hàm:**
  - `normalize_label(label)`: loại khoảng trắng thừa, không gộp lớp khác nhau.
  - `normalize_summary(summary)`: cộng số lượng theo đúng tên lớp.
  - `normalize_text(text)`: giữ nguyên văn bản.
- **Liên kết:** `detection/model.py` chuẩn hóa kết quả model; `storage/db.py` chuẩn hóa dữ liệu đọc/ghi và log cũ.
- **Mức độ quan trọng:** Quan trọng nếu thay đổi tên lớp hoặc định dạng báo cáo; thường không cần sửa khi chỉ thay đổi UI.

### Thư mục `weapon_detection/detection/`

#### [weapon_detection/detection/__init__.py](./weapon_detection/detection/__init__.py)

- **Vai trò:** Đánh dấu thư mục `detection` là package.
- **Nội dung:** Hiện rỗng; không có hàm hoặc logic.
- **Có thể bỏ qua** khi đọc nghiệp vụ.

#### [weapon_detection/detection/model.py](./weapon_detection/detection/model.py)

- **Vai trò:** Bao bọc model YOLO qua Ultralytics; là lớp gọi inference dùng chung cho nguồn camera, video demo và nhận diện màn hình.
- **Lớp `WeaponDetector`:**
  - `__init__(model_path)`: nạp weights cục bộ, chọn CUDA khi khả dụng, tạo khóa đồng bộ và warm-up bằng một frame giả.
  - `detect(frame, conf=0.5, imgsz=320, class_thresholds=...)`: chạy inference dưới khóa, lọc confidence riêng theo lớp và trả `{label, conf, box}`.
- **Hàm cấp module:**
  - `draw_detections(frame, dets, color=None)`: vẽ hộp giới hạn và nhãn lên frame; trả lại frame đã vẽ.
  - `draw_stamp(frame, text)`: ghi chữ/nhãn thời gian lên đầu frame; trả lại frame.
- **Liên kết:** `web/app.py` khởi tạo detector một lần; `streams.StreamWorker` và API frame video demo gọi `detect()`. `streams.py` và `web/app.py` dùng hàm vẽ để tạo ảnh xem trước/cảnh báo.
- **Mức độ quan trọng:** Rất quan trọng để hiểu inference, GPU/CPU và định dạng đầu ra detector. Chỉ thay đổi hàm này khi cần thay đổi cách nạp model hoặc biểu diễn dự đoán.

#### [weapon_detection/detection/streams.py](./weapon_detection/detection/streams.py)

- **Vai trò:** Quản lý nguồn video, luồng đọc frame, luồng nhận diện, telemetry và ngưỡng tạo cảnh báo.
- **Biến dùng chung:** `workers` chứa các worker đang chạy; `telemetry` lưu dữ liệu telemetry mới nhận; `_settings_cache` cache settings nhận diện; các cấu trúc `_demo_*` giữ trạng thái video demo.
- **Hằng số chính:** `STREAM_MAX_W` giới hạn chiều rộng ảnh JPEG stream; `DETS_TTL` thời gian giữ dự đoán để vẽ; `ALERT_EVIDENCE_FRAME_COUNT` kích thước lịch sử frame làm bằng chứng.
- **Hàm hỗ trợ:**
  - `_same_detection(left, right)`: so sánh nhãn và mức giao nhau của hai bounding box để xác định có phải cùng một đối tượng.
  - `_matching_detection_frames(history, detections)`: lọc các frame lịch sử có chứa đối tượng tương ứng.
  - `text_jpeg(text)`: tạo ảnh JPEG thông báo như đang kết nối/offline.
  - `get_detection_settings()` / `update_detection_settings(settings)`: đọc settings từ DB có cache ngắn hạn hoặc cập nhật cache khi API settings thay đổi.
  - `_resolve_url(url)`: chuyển chuỗi số thành webcam index, giữ URL mạng, hoặc đổi đường dẫn tương đối thành đường dẫn dự án.
  - `_open(url)`: mở webcam/video bằng OpenCV, cài một số tham số capture.
  - `start(src, detector, on_detect)`: dừng worker cũ; không chạy camera worker cho video demo; chạy worker mới nếu nguồn được bật.
  - `stop(sid)`: dừng worker và xóa trạng thái demo của nguồn.
  - `get_telemetry(sid)`: trả telemetry nếu dữ liệu còn mới (trong 30 giây).
  - `demo_video_filename(src)`: xác thực nguồn `demo:` và chỉ trả tên tệp đơn, tránh chấp nhận đường dẫn lồng.
  - `get_demo_frame(sid)`: trả bản sao frame demo mới nhất nếu có.
  - `process_demo_detections(src, frame, dets, on_detect)`: giữ frame/detection history của video demo, áp dụng số frame xác nhận và cooldown, rồi gọi callback tạo cảnh báo khi đạt điều kiện.
- **Lớp `StreamWorker(threading.Thread)`:**
  - `__init__(src, detector, on_detect)`: tạo trạng thái cho một nguồn, bao gồm frame thô, JPEG gần nhất, detections gần nhất, streak và lịch sử bằng chứng.
  - `stop()`: yêu cầu dừng worker.
  - `get_jpeg()` / `_put(jpeg)`: đọc/cập nhật JPEG an toàn qua lock.
  - `_set_online(v)`: cập nhật online/offline và ghi log khi trạng thái đổi.
  - `run()`: mở nguồn lặp lại nếu mất kết nối, đọc frame, lưu frame thô cho detector, tạo JPEG cho browser và điều tiết tốc độ video file.
  - `_detect_loop()`: chạy song song với `run()`, đọc settings, chỉ infer khi có frame mới và chưa vượt `detect_fps`, gọi detector và cập nhật track theo timestamp frame đầu vào để bù độ trễ suy luận khi hiển thị; lọc vị trí theo vận tốc tâm box, dự đoán vị trí giới hạn 0,75 giây, giữ track tối đa 1 giây khi model tạm bỏ sót. Client video demo nội suy vị trí giữa các kết quả theo playhead, dự đoán vận tốc tâm box và ghép track theo vị trí dự đoán để giảm giật khi vật thể di chuyển nhanh. Chỉ chuyển sang kiểm tra cảnh báo nếu frame suy luận mới trong 0,35 giây.
  - `_check_alert(frame, st)`: đếm detections liên tiếp, lưu lịch sử bằng chứng, áp dụng `confirm_frames` và `alert_cooldown`; đủ điều kiện thì vẽ snapshot và gọi `on_detect`.
- **Liên kết:** Được điều khiển bởi `web/app.py` qua `manager.start`, `manager.stop`, `manager.get_telemetry`, `manager.get_detection_settings` và các hàm demo. Callback `on_detect` quay lại `web/app.py` để lưu ảnh/cảnh báo.
- **Mức độ quan trọng:** Là phần cốt lõi cùng `model.py`, `db.py` và `web/app.py`. Cần nắm file này để hiểu khác biệt camera trực tiếp/video demo và cách biến dự đoán thành cảnh báo.

### Thư mục `weapon_detection/storage/`

#### [weapon_detection/storage/__init__.py](./weapon_detection/storage/__init__.py)

- **Vai trò:** Đánh dấu thư mục `storage` là package.
- **Nội dung:** Hiện rỗng.
- **Có thể bỏ qua** khi đọc nghiệp vụ.

#### [weapon_detection/storage/db.py](./weapon_detection/storage/db.py)

- **Vai trò:** Lớp truy cập SQLite đang được ứng dụng sử dụng cho nguồn, cảnh báo, sự kiện, settings, thiết bị nhận Telegram, log và thống kê.
- **Kết nối và khởi tạo:**
  - `_db()`: context manager mở kết nối SQLite dưới `RLock`, tự commit khi thoát và đóng kết nối.
  - `now()`: trả thời điểm hiện tại dạng chuỗi ISO.
  - `init()`: tạo bảng, migrate cột `mobile_devices.enabled` nếu cần, chuyển cấu hình Chat ID cũ thành mobile device, thêm settings mặc định và thêm nguồn mặc định nếu bảng nguồn rỗng.
  - `_load_settings()`: nạp settings vào cache trong bộ nhớ.
  - `get_settings()` / `set_settings(data)`: đọc settings hoặc ép kiểu/lưu settings hợp lệ rồi nạp lại cache.
- **Quản lý điện thoại nhận thông báo:**
  - `list_mobile_devices()`: liệt kê thiết bị.
  - `add_mobile_device(name, chat_id)`: thêm thiết bị.
  - `update_mobile_device(device_id, name=None, enabled=None)`: cập nhật tên và/hoặc trạng thái nhận tin.
  - `delete_mobile_device(device_id)`: xóa thiết bị.
- **Quản lý nguồn thiết bị:**
  - `list_sources()` / `get_source(sid)`: đọc nguồn.
  - `save_source(s)` / `delete_source(sid)`: lưu hoặc xóa nguồn.
- **Quản lý cảnh báo:**
  - `_alert(c, r)`: chuyển SQLite row thành object, đọc summary, timeline và ảnh bằng chứng kèm detection/time; chuẩn hóa nhãn/văn bản.
  - `_event(c, aid, text)`: thêm sự kiện vào timeline.
  - `create_alert(src, dets, image, evidence_images=())`: tạo cảnh báo pending, lưu summary/detections và bằng chứng, thêm event phát hiện.
  - `add_alert_evidence(aid, image, detections, captured_at)`: gắn ảnh tiếp diễn và thông tin nhận diện tương ứng vào alert.
  - `list_alerts(group="pending", limit=200)` / `get_alert(aid)`: liệt kê hoặc đọc cảnh báo.
  - `set_status(aid, status, by)`: cập nhật trạng thái cảnh báo chưa xử lý và ghi người xử lý/event.
  - `clear_pending(by)`: chuyển toàn bộ pending thành deleted và ghi event.
  - `add_note(aid, text, by)`: thêm ghi chú vào event history.
- **Log và thống kê:**
  - `log(level, subject, info="")`: thêm log.
  - `list_logs(limit=200)`: đọc log mới nhất và chuẩn hóa nội dung.
  - `stats()`: tổng hợp số liệu hôm nay, theo status, 7 ngày, theo loại vật thể và cảnh báo gần đây.
- **Các bảng chính:** `sources`, `alerts`, `alert_evidence`, `alert_events`, `logs`, `settings`, `mobile_devices`.
- **Liên kết:** Hầu hết API trong `web/app.py`, worker trong `streams.py` và gửi tin trong `notifier.py` đọc/ghi qua module này.
- **Mức độ quan trọng:** Rất quan trọng. Đây là nguồn dữ liệu lâu dài; khi thêm trường mới thường cần cập nhật schema, migration, hàm đọc/ghi và API/UI tương ứng.

### Thư mục `weapon_detection/notifications/`

#### [weapon_detection/notifications/__init__.py](./weapon_detection/notifications/__init__.py)

- **Vai trò:** Đánh dấu thư mục `notifications` là package.
- **Nội dung:** Hiện rỗng.

#### [weapon_detection/notifications/notifier.py](./weapon_detection/notifications/notifier.py)

- **Vai trò:** Tạo thông báo cảnh báo và gửi Telegram.
- **Hàm:**
  - `build_message(a)`: ghép tên địa điểm/nguồn, tọa độ, thời gian, loại vật thể, confidence và mã cảnh báo thành nội dung tin.
  - `_telegram(text, chat_id, image_path=None)` / `_telegram_dispatch(...)`: gửi nội dung hoặc album ảnh; caption mỗi ảnh có thông tin nhận diện riêng.
  - `_telegram_error(error)`: chuyển lỗi HTTP/timeout/connection thành nội dung giải thích.
  - `send_dispatch(a)`: ghi log dispatch cục bộ, rồi gửi ảnh và tin tới tất cả thiết bị bật nhận nếu Telegram được bật và token có giá trị.
  - `send_test(chat_id, device_name="thiết bị")`: gửi tin thử tới một Chat ID.
- **Liên kết:** `web.app.api_dispatch()` gọi `send_dispatch()`; các API thử gọi `send_test()`; settings và danh sách recipients lấy từ `storage/db.py`.
- **Mức độ quan trọng:** Cần đọc nếu thay đổi hành vi dispatch, recipient hoặc Telegram; không cần đọc để hiểu inference.

### Thư mục `weapon_detection/web/`

#### [weapon_detection/web/__init__.py](./weapon_detection/web/__init__.py)

- **Vai trò:** Đánh dấu thư mục `web` là package.
- **Nội dung:** Hiện rỗng.

#### [weapon_detection/web/app.py](./weapon_detection/web/app.py)

- **Vai trò:** Trung tâm backend: tạo Flask app, khởi tạo hệ thống, cung cấp trang web, video và REST API.
- **Khởi tạo cấp module:** Thiết lập một số giới hạn upload/request, cấu hình Flask trỏ tới `static/` và `templates/`; `detector` ban đầu chưa được tạo cho đến khi gọi `main()`.
- **Hàm hỗ trợ:**
  - `enforce_request_size()`: giới hạn kích thước request, có ngoại lệ xử lý upload video demo theo giới hạn riêng.
  - `operator()`: lấy tên nhân viên hiện tại từ settings.
  - `on_detect(src, snapshot, dets)` / `on_evidence(...)`: tạo alert ngay khi phát hiện, sau đó lưu ảnh tiếp diễn có box và metadata vào cùng alert.
  - `index()`: trả template `index.html`.
  - `video_feed(sid)`: tạo multipart MJPEG stream từ worker; nếu không có worker trả ảnh trạng thái thiết bị tắt.
  - `alert_image(name)`: phục vụ file ảnh cảnh báo.
  - `source_video(sid)`: kiểm tra nguồn video demo rồi phục vụ file video.
  - `_clean_source(d, old=None)`: xác thực và chuẩn hóa loại, tên, URL, vị trí, tọa độ, enabled; sinh ID mới nếu cần.
  - `_save_source_from_request(old=None)`: đọc JSON hoặc multipart upload, xác thực MP4/WebM/kích thước, lưu video demo và nguồn vào DB; dọn file mới nếu lưu thất bại; xóa video cũ nếu được thay thế.
  - `_remove_demo_video(filename, sid)`: xóa file video demo và ghi log nếu hệ điều hành từ chối.
  - `_resolve(aid, status)`: cập nhật trạng thái pending, nếu không cập nhật được trả lỗi xung đột, rồi đọc lại cảnh báo.
  - `main()`: khởi tạo thư mục/DB/model/workers, ghi log khởi động và gọi Flask `app.run()`.
- **Các route trang và media:**
  - `index()` — `GET /`: trả giao diện.
  - `video_feed(sid)` — `GET /video_feed/<sid>`: MJPEG từ worker camera.
  - `alert_image(name)` — `GET /alert_images/<path:name>`: phục vụ ảnh cảnh báo.
  - `source_video(sid)` — `GET /source_video/<sid>`: phục vụ video demo đã xác thực.
- **Các route nguồn:**
  - `api_sources()` — `GET /api/sources`: danh sách thiết bị kèm online, resolution, FPS, telemetry, trạng thái video demo.
  - `api_source_create()` — `POST /api/sources`: tạo nguồn, log và khởi chạy worker.
  - `api_source_update(sid)` — `PUT /api/sources/<sid>`: cập nhật nguồn rồi khởi động lại worker.
  - `api_source_delete(sid)` — `DELETE /api/sources/<sid>`: dừng worker, xóa video demo nếu có và xóa nguồn.
  - `api_source_frame(sid)` — `POST /api/sources/<sid>/frame`: nhận một frame JPEG của video demo, chạy inference và xử lý detection.
  - `api_telemetry(sid)` — `POST /api/sources/<sid>/telemetry`: nhận telemetry cho drone/robot.
- **Các route cảnh báo/thống kê/settings:**
  - `api_alerts()` — `GET /api/alerts`: lấy nhóm pending/history/all.
  - `api_dispatch(aid)` — `POST /api/alerts/<aid>/dispatch`: chuyển trạng thái rồi yêu cầu notifier gửi tin.
  - `api_delete(aid)` — `POST /api/alerts/<aid>/delete`: đánh dấu đã xóa.
  - `api_clear()` — `POST /api/alerts/clear`: xóa toàn bộ đang chờ.
  - `api_note(aid)` — `POST /api/alerts/<aid>/note`: thêm ghi chú.
  - `api_stats()` — `GET /api/stats`; `api_logs()` — `GET /api/logs`: lấy thống kê và log.
  - `api_settings()` — `GET /api/settings`; `api_settings_put()` — `PUT /api/settings`: đọc/lưu cấu hình; cập nhật cache detection ngay sau khi lưu.
- **Các route thiết bị Telegram:**
  - `api_notify_test()` — `POST /api/notify/test`: gửi thử tới tất cả thiết bị đang bật.
  - `api_mobile_devices()` — `GET /api/mobile-devices`: danh sách thiết bị.
  - `api_mobile_device_create()` — `POST /api/mobile-devices`: thêm thiết bị, xác thực tên/Chat ID và xử lý Chat ID trùng.
  - `api_mobile_device_update(device_id)` — `PUT /api/mobile-devices/<device_id>`: sửa tên và/hoặc trạng thái nhận.
  - `api_mobile_device_delete(device_id)` — `DELETE /api/mobile-devices/<device_id>`: xóa thiết bị.
  - `api_mobile_device_test(device_id)` — `POST /api/mobile-devices/<device_id>/test`: gửi thử tới một thiết bị.
- **Liên kết:** Đây là điểm kết nối giữa frontend và mọi module backend. Các yêu cầu từ [static/js/app.js](./static/js/app.js) đi vào route tương ứng, route gọi DB/model/stream/notifier theo nghiệp vụ.
- **Mức độ quan trọng:** Tệp quan trọng nhất để hiểu API và luồng tích hợp toàn ứng dụng.

### Thư mục `templates/`

#### [templates/index.html](./templates/index.html)

- **Vai trò:** Khung HTML duy nhất được Flask trả về ở route `/`.
- **Nội dung:** Header, menu sidebar rỗng để JS dựng, vùng `<main>`, dialog, toast; nạp Leaflet từ CDN, CSS nội bộ và JavaScript nội bộ.
- **Hàm:** Không có.
- **Liên kết:** `static/js/app.js` dựng các màn hình vào `#sidebar`/`#main`; `static/css/style.css` định dạng các phần tử.
- **Mức độ quan trọng:** Cần biết các ID gốc (`#main`, `#sidebar`, `#dlg`, `#toast`) nếu sửa cấu trúc giao diện; có thể bỏ qua khi chỉ theo nghiệp vụ backend.

### Thư mục `static/js/`

#### [static/js/app.js](./static/js/app.js)

- **Vai trò:** Toàn bộ logic giao diện chạy trên trình duyệt: gọi API, lưu trạng thái tạm, dựng màn hình, xử lý sự kiện và refresh dữ liệu.
- **Helpers/trạng thái:**
  - `$`, `$$`: chọn một/nhiều phần tử DOM.
  - `esc(s)`: escape ký tự HTML trước khi đưa nội dung dữ liệu vào markup.
  - `fmt(iso)`, `wtext(a)`, `chips(a)`, `imgUrl(a)`, `evidenceStrip(a)`, `detectionInfo(...)`: định dạng thời gian, summary, ảnh và thông tin nhận diện theo frame.
  - `api(url, method, body)`: wrapper `fetch`; gửi JSON hoặc `FormData`, báo lỗi khi HTTP response không thành công.
  - `S`: trạng thái runtime của frontend: nguồn, cảnh báo chờ, settings, màn hình hiện tại, item đang chọn, map, cache chữ ký render, trạng thái refresh.
  - `toast(msg, ...)`: thông báo ngắn trên giao diện.
  - `beep()`: phát âm báo nếu setting bật và chưa tạm tắt.
  - `ICON`, `svg()`, `NAV`: biểu tượng và cấu hình menu. Chủ yếu phục vụ hiển thị.
  - `buildShell()`: dựng sidebar và section màn hình; gắn sự kiện chuyển trang.
  - `applySettings()`: áp dụng tên nhân viên và theme.
  - `showView(id)`: ẩn/hiện màn hình, cập nhật menu đang chọn và gọi `show()`/`tick()` của view.
- **Bản đồ/cảnh báo:**
  - `makeMap(el)`: tạo Leaflet map, tile imagery và layer marker; trả đối tượng map/layer/site position.
  - `updateMap(mp)`: dựng marker địa điểm, nguồn và cảnh báo đang chờ.
  - `current()`: lấy cảnh báo đang chọn, chuyển sang cảnh báo đầu tiên nếu lựa chọn không còn.
  - `timeline(a)`, `noteBox(a)`, `logTable(rows)`: dựng các thành phần hiển thị.
  - `act(what, id)`: gọi API Dispatch/Delete/Clear/Note rồi refresh dữ liệu.
  - `zoom(src)`, `attachAlertMagnifier(view)`: phóng to ảnh bằng dialog hoặc kính lúp khi rê chuột.
  - `toggleStreamFullscreen(button)`: chuyển khung nguồn sang toàn màn hình.
- **Event listeners toàn cục:** Sự kiện click xử lý các `data-act` (chọn alert, đổi frame bằng chứng, zoom, full-screen, dispatch/delete/note); event riêng điều khiển video demo, focus camera và trở về lưới. Phím `D`/`X` xử lý cảnh báo khi người dùng không đang nhập trong input/textarea/select.
  - `dirty()`: xóa chữ ký render cache của màn hình cảnh báo để lần tick kế tiếp dựng lại nội dung.
  - `tickCurrent()`: gọi `tick()` của màn hình hiện tại; được dùng sau thao tác focus camera/chọn cảnh báo.
- **Live Ops và video demo:**
  - `updateLivePlaybackButton()`: cập nhật nút phát/tạm dừng tất cả video demo.
  - `TYPE_NAME`: ánh xạ loại nguồn sang tên hiển thị; `demoVideoStates` giữ trạng thái xử lý riêng cho từng phần tử video.
  - `VIEWS.dashboard.tick()`: dựng thống kê, biểu đồ, thiết bị, cảnh báo gần đây.
  - `VIEWS.live.show()` / `VIEWS.live.tick()`: dựng lưới nguồn, trạng thái, focus camera và nút video.
  - `statBits(s)` / `hudText(s)`: chuyển telemetry và thông tin nguồn thành các dòng trạng thái trên ô video.
  - `connectDemoVideo(video, panel, sourceId)`: khi video demo chạy, lấy frame, đóng gói JPEG, POST lên API frame; giữ trạng thái request để tránh request chồng, hiển thị lỗi và vẽ detection.
  - `drawDemoDetections(canvas, detections, width, height)`: vẽ bounding boxes/nhãn lên canvas phủ video.
  - `clearDemoDetections(canvas)`: xóa lớp overlay.
  - `VIEWS.verify.tick()`: dựng màn hình xác minh, ảnh, bằng chứng, timeline, ghi chú và nút thao tác.
  - `VIEWS.history.show()`: lấy lịch sử và lọc theo trạng thái.
- **Thiết bị và cấu hình:**
  - `deviceView(type)`: tạo logic dùng chung cho Cameras/Drones/Robots; object trả về có `show()`, `draw()`, `form(s)`.
  - `VIEWS.map.show()` / `VIEWS.map.tick()`: tạo và cập nhật bản đồ.
  - `settingsForm(...)`: dựng form settings theo nhóm, nạp giá trị, lưu qua API; theme switch lưu ngay.
  - `VIEWS.site.show()`: form tên/địa chỉ/tọa độ địa điểm.
  - `VIEWS.settings.show()`: form theme, operator, sound, ngưỡng confidence riêng theo 10 lớp, cooldown, imgsz và detect FPS.
  - `VIEWS.notify.show()`: form token/bật tắt Telegram; tải, thêm, đổi tên, bật/tắt, thử hoặc xóa thiết bị di động.
  - `VIEWS.logs.show()`: tải và dựng nhật ký hệ thống.
- **Refresh/khởi động frontend:**
  - `loadSources()`: tải danh sách nguồn.
  - `refresh(force)`: tải sources/pending alerts, thỉnh thoảng tải stats/logs, cập nhật kết nối/badge/title, nhận ra cảnh báo mới và gọi render cho view hiện tại.
  - `start()`: dựng shell, tải settings, khởi tạo đồng hồ, refresh ban đầu, mở Dashboard và đặt timer refresh khoảng 2 giây.
- **Liên kết:** Các màn hình gọi backend qua `api()`; route và schema tương ứng nằm trong `web/app.py`/`storage/db.py`.
- **Mức độ quan trọng:** Tệp cốt lõi của frontend, nhưng khá dài và trộn logic UI với giao tiếp API. Khi tìm luồng nghiệp vụ, bắt đầu ở `VIEWS.*`, `api()`, `act()` và `refresh()`; không cần đọc từng biểu tượng/chuỗi HTML.

### Thư mục `static/css/`

#### [static/css/style.css](./static/css/style.css)

- **Vai trò:** CSS cho bố cục, màu, trạng thái hover, responsive layout, camera grid, forms, tables, dialogs, alerts, bản đồ và theme sáng/tối.
- **Hàm/logic nghiệp vụ:** Không có hàm JavaScript hay logic lưu trữ; CSS chỉ quyết định cách hiển thị.
- **Liên kết:** Các class/id do `templates/index.html` và `static/js/app.js` sinh ra được định dạng ở đây.
- **Có thể bỏ qua** khi muốn hiểu model, API, database hoặc điều kiện tạo cảnh báo. Đọc khi sửa khoảng cách, kích thước, màu sắc, bố cục hoặc trạng thái hiển thị.

## 4. Tệp không phải mã nguồn nhưng cần biết

| Tệp/thư mục | Công dụng |
|---|---|
| [requirements.txt](./requirements.txt) | Khai báo dependency Python: Flask, OpenCV, Requests, PyTorch, MSS và Ultralytics. Cài PyTorch phù hợp với cấu hình CPU/CUDA của máy trước khi chạy. |
| [README.md](./README.md) | Tóm tắt chạy ứng dụng, các trang, thông báo và ghi chú hiệu năng. |
| [HUONG_DAN_SU_DUNG.md](./HUONG_DAN_SU_DUNG.md) | Hướng dẫn thao tác sản phẩm dành cho người dùng hệ thống. |
| `models/ss_final_1.pt` | Weights YOLO cục bộ, 10 lớp được cấu hình trong [weapon_detection/config.py](./weapon_detection/config.py). |
| `data/weapon_guard.db` | Database đang được chọn bởi `config.DB_PATH`; lưu nguồn, cảnh báo, settings, logs và thiết bị Telegram. |
| `data/alerts/` | Ảnh cảnh báo và frame bằng chứng được tạo bởi `on_detect()`. |
| `data/videos/` | Video demo được upload từ giao diện. |
| `data/dispatch.log` | Bản ghi nội dung dispatch cục bộ do `notifier.send_dispatch()` ghi. |
| `.vscode/` | Cấu hình VS Code trỏ tới môi trường `venv`; không tham gia nghiệp vụ runtime nhưng hỗ trợ chạy dự án trong workspace. |
| `venv/`, `.git/`, `__pycache__/` | Môi trường Python, lịch sử Git và cache bytecode; không tính vào số mã nguồn ở trên. |

## 5. Những phần cần nắm trước để hiểu logic

### Nhóm bắt buộc cho luồng nhận diện

1. [weapon_detection/web/app.py](./weapon_detection/web/app.py): `main()`, `on_detect()`, route `/api/sources/<sid>/frame`, các API cảnh báo.
2. [weapon_detection/detection/model.py](./weapon_detection/detection/model.py): `WeaponDetector.__init__()` và `detect()`.
3. [weapon_detection/detection/streams.py](./weapon_detection/detection/streams.py): `StreamWorker.run()`, `_detect_loop()`, `_check_alert()`, `process_demo_detections()`.
4. [weapon_detection/storage/db.py](./weapon_detection/storage/db.py): `create_alert()`, `set_status()`, `list_alerts()`, `init()`.
5. [weapon_detection/config.py](./weapon_detection/config.py): đường dẫn model/database/ảnh/video và settings mặc định.

### Nhóm cần nắm khi làm thông báo

- `web/app.py`: `api_dispatch()`, API mobile devices và test notification.
- `notifications/notifier.py`: `build_message()`, `send_dispatch()`, `send_test()`.
- `storage/db.py`: các hàm mobile-device và settings.

### Nhóm cần nắm khi làm giao diện

- `templates/index.html`: điểm gắn CSS/JS và các ID gốc.
- `static/js/app.js`: `api()`, `S`, `showView()`, `VIEWS.*`, `act()`, `refresh()`, `start()`.
- `static/css/style.css`: bố cục và giao diện.

## 6. Phần có thể tạm bỏ qua

- Các giá trị màu (`COLORS`, `ICON`, CSS variables), font, border, hover và hiệu ứng: chỉ cần khi sửa giao diện hoặc cách vẽ.
- Các helper định dạng HTML/giờ/nhãn trong frontend: hữu ích cho hiển thị nhưng không quyết định việc model phát hiện.
- `__init__.py` rỗng: không có nghiệp vụ.
- Các chi tiết CSS: không cần đọc để hiểu camera -> model -> cảnh báo -> database -> Telegram.
- `draw_detections()` và `draw_stamp()` chủ yếu vẽ ảnh; hiểu cách tạo cảnh báo không đòi hỏi đọc chi tiết thuật toán vẽ.

Không nên bỏ qua `db.py`, `streams.py` hoặc `web/app.py` khi sửa xử lý cảnh báo. Thay đổi giao diện đơn lẻ thường không cần đọc các module này.

## 7. Một số quy tắc và quan hệ quan trọng

- **Settings có hai lớp:** `DEFAULT_SETTINGS` trong `config.py` tạo mặc định; SQLite lưu giá trị runtime; `db._load_settings()` đưa giá trị vào cache; `streams.get_detection_settings()` có cache riêng ngắn hạn cho detector. API PUT settings cập nhật DB và cache detection.
- **Nguồn trực tiếp và demo không chạy cùng cơ chế lấy frame:** camera/URL dùng `StreamWorker`; demo lấy frame trong browser rồi gửi API `/frame`.
- **Cảnh báo không được tạo từ một frame đơn:** backend yêu cầu số lượt liên tiếp theo `confirm_frames` và chờ `alert_cooldown` trước cảnh báo tiếp theo cùng nguồn.
- **Bằng chứng được ghép theo đối tượng:** detection hiện tại được so sánh nhãn và overlap bounding box với lịch sử frame gần nhất.
- **Nhận diện và hiển thị video là các luồng liên quan nhưng riêng biệt:** video stream tạo JPEG để hiển thị; inference cập nhật detection và chỉ ảnh hóa kết quả khi cần.
- **Cảnh báo cần trạng thái pending mới được xử lý:** `db.set_status()` chỉ cập nhật cảnh báo đang pending; thao tác đồng thời/trùng lặp có thể trả conflict.
- **Dispatch gồm hai việc:** backend cập nhật trạng thái cảnh báo trước, sau đó gửi thông báo (nếu cấu hình Telegram đã bật) và ghi log kết quả.
- **Nhãn được chuẩn hóa ở nhiều lớp:** model chuẩn hóa đầu ra; DB chuẩn hóa summary và dữ liệu cũ; UI hiển thị nhãn đã chuẩn hóa từ API.
- **Tọa độ:** vị trí địa điểm lấy từ Site settings; thiết bị và cảnh báo chỉ hiện marker riêng khi có tọa độ.

## 8. Thứ tự đọc đề xuất

### Nếu mới bắt đầu với toàn bộ hệ thống

1. [README.md](./README.md) và phần sơ đồ trong tài liệu này.
2. [app.py](./app.py) rồi `main()` trong [weapon_detection/web/app.py](./weapon_detection/web/app.py).
3. [weapon_detection/config.py](./weapon_detection/config.py).
4. `WeaponDetector` trong [weapon_detection/detection/model.py](./weapon_detection/detection/model.py).
5. `StreamWorker` trong [weapon_detection/detection/streams.py](./weapon_detection/detection/streams.py).
6. `on_detect()` trong [weapon_detection/web/app.py](./weapon_detection/web/app.py) và các hàm alert trong [weapon_detection/storage/db.py](./weapon_detection/storage/db.py).
7. [weapon_detection/notifications/notifier.py](./weapon_detection/notifications/notifier.py).
8. Cuối cùng đọc [static/js/app.js](./static/js/app.js), [templates/index.html](./templates/index.html) và [static/css/style.css](./static/css/style.css).

### Nếu chỉ cần làm một loại thay đổi

| Mục tiêu | Bắt đầu đọc |
|---|---|
| Tăng/giảm tốc độ nhận diện | `config.py` → Settings API trong `web/app.py` → cache/chu kỳ trong `streams.py` → inference trong `model.py`. |
| Thay ngưỡng tạo cảnh báo | `config.py` → `streams.py` (`_check_alert`, `process_demo_detections`) → `web/app.py` (settings API). |
| Thêm trường cho nguồn thiết bị | `web/app.py` (`_clean_source`, API nguồn) → `storage/db.py` (schema và CRUD) → `static/js/app.js` (form/bảng). |
| Thay đổi trạng thái hoặc thông tin cảnh báo | `storage/db.py` → API cảnh báo trong `web/app.py` → `static/js/app.js` (Alerts/Past Ops). |
| Thay đổi Telegram | `notifications/notifier.py` → route notification trong `web/app.py` → CRUD settings/devices trong `storage/db.py` → view Notifications trong `static/js/app.js`. |
| Sửa giao diện, màu hoặc khoảng cách | `static/css/style.css`; nếu cần thêm/bớt thành phần thì sửa view tương ứng trong `static/js/app.js`. |
| Đổi tên lớp/nhãn model | `labels.py` → `detection/model.py` → serialization/summary trong `storage/db.py` → UI nơi render label. |
