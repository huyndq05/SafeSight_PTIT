# Đợt sắp xếp và dọn mã nguồn

## Đã thực hiện

- Lưu bản sao trước khi chỉnh tại
  `data/maintenance/20261112_054818/source_before.zip`.
- Gom chín tài liệu/sơ đồ từ thư mục gốc vào `docs/`, thêm mục lục và
  cập nhật các liên kết tương đối. Viết lại README theo luồng vận hành hiện tại.
- Định dạng thống nhất 50 tệp Python bằng Ruff; chuẩn hóa JavaScript, CSS,
  template và kiểm thử JavaScript bằng Prettier.
- Bỏ import không dùng; thay helper lambda trong phần thống kê bằng hàm rõ ràng.
- Bỏ phần frontend cũ dành cho ghi chú, diễn biến và thao tác tất cả không
  còn được giao diện sử dụng. Giữ API tương thích và dữ liệu ghi chú lịch sử.
- Bỏ một số selector CSS cho thành phần đã bị gỡ khỏi giao diện.
- Xóa 43 tệp bytecode `.pyc/.pyo` và tám thư mục cache rỗng trong cây mã
  nguồn. Danh sách cụ thể nằm trong `cleanup_manifest.json` cạnh bản sao.
- Bổ sung `.gitignore` cho môi trường ảo, công cụ phát triển, cache, bản sao
  bảo trì và đầu ra đánh giá sinh tự động.
- Thêm `pyproject.toml`, `requirements-dev.txt`, `package.json`, lockfile và
  lệnh kiểm tra định dạng có thể chạy lại.
- Chỉnh kiểm thử khởi động dùng khóa riêng trong thư mục tạm, tránh đụng
  tiến trình SafeSight đang chạy; kiểm thử JSON nhúng trong HTML không còn
  phụ thuộc vào việc template có xuống dòng hay không.

## Đã kiểm tra

- 78 kiểm thử Python, gồm tài khoản, xuất file, cảnh báo, video và tracker.
- Bốn script kiểm tra JavaScript: cú pháp, playback, kích thước overlay và vị trí.
- Kiểm thử trình duyệt trên database riêng, gồm đăng nhập, các thao tác vận
  hành và các kích thước desktop/tablet/điện thoại.
- Ruff lint/format và Prettier check đều đạt.
- Các liên kết tương đối trong README và tài liệu `docs/` không bị đứt sau khi chuyển.

## Giữ nguyên có chủ đích

Không xóa model, video, ảnh bằng chứng, database, khóa phiên đăng nhập hoặc
kết quả đánh giá model. Không xóa `venv` và `.venv`: môi trường CUDA và môi
trường phát triển/kiểm thử hiện có khác nhau. Công cụ trong `training/` vẫn
phục vụ chuẩn bị, kiểm tra và đánh giá dữ liệu, dù không được web app import.

Không thay toàn bộ cấu trúc API/database hay gom các rule CSS có thứ tự
cascade khác nhau chỉ để giảm số dòng. Các thay đổi đó cần được tách thành
đợt refactor riêng với kiểm tra hồi quy tương ứng. Thư mục cache có thể được
Python tạo lại khi chạy; chúng đã được loại khỏi các tệp cần quản lý mới.
