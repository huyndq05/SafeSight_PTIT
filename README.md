# SafeSight

Giám sát camera và video, phát hiện hung khí, xác minh cảnh báo và gửi thông
báo tới điện thoại. Nhận diện trực tiếp và xử lý trước video là hai luồng riêng.

## Khởi chạy trên Windows

1. Giữ weights `models/ss_final_2.pt` và cài Python 3.10 trở lên.
2. Chạy `setup.bat` nếu chưa có môi trường Python và dependencies.
3. Chạy `run.bat`, mở <http://127.0.0.1:5000>.
4. Lần đầu tạo tài khoản quản trị, sau đó tạo tài khoản nhân viên để đổi ca.

`run.bat` ưu tiên `venv` nếu dùng được CUDA và đủ dependencies, nếu không
sẽ dùng `.venv`. Hai môi trường có vai trò khác nhau, không cần xóa một
trong hai để chạy app. Dependencies ứng dụng nằm trong `requirements.txt`.
Chạy `run_screen.bat` để nhận diện màn hình bằng cùng model.

## Cấu trúc dự án

```text
app.py                   Điểm vào ứng dụng web
screen.py                Nhận diện màn hình
train.py                 Kiểm tra / train / đánh giá model
weapon_detection/
  config.py              Cấu hình mặc định và class model
  detection/             Model, tracker, camera, xử lý trước video
  web/                   HTTP API, tài khoản, giao diện cá nhân, xuất dữ liệu
  storage/               SQLite và quy tắc chuyển trạng thái cảnh báo
  notifications/         Nội dung và gửi Telegram
static/                  JavaScript và CSS giao diện
templates/               Trang đăng nhập và khung ứng dụng
tests/                   Kiểm thử Python, JavaScript và trình duyệt
training/                Công cụ chuẩn bị và đánh giá dữ liệu huấn luyện
docs/                    Hướng dẫn và báo cáo kỹ thuật
models/                  Weights cục bộ
data/                    Dữ liệu vận hành, video, ảnh, database và log
```

## Luồng vận hành

- **Giám sát:** xem camera, bố cục lưới/phóng lớn và chế độ giản lược.
- **Video:** xem bản gốc ngay; bấm xử lý để quét trước, rồi chuyển sang
  bản đã nhận diện. Phát và tua không chạy lại model.
- **Cảnh báo:** xác nhận và gửi, đánh dấu sai hoặc xóa thật; hỗ trợ chọn
  nhiều cảnh báo để xóa/đánh dấu sai. Kết luận sai và lịch sử gửi được lưu riêng.
- **Lịch sử:** lọc trạng thái, xuất CSV, ZIP ảnh hoặc Excel nhúng ảnh.
- **Cài đặt:** ngưỡng/class dùng chung; bố cục, màu box và giao diện lưu
  riêng theo tài khoản. Đổi mặc định trong mã không tự ghi đè cài đặt đã lưu.

Xem [danh mục tài liệu](docs/README.md), [video xử lý trước](docs/VIDEO_XU_LY_TRUOC.md)
và [xuất dữ liệu](docs/XUAT_DU_LIEU_CANH_BAO.md).

## Phát triển và kiểm thử

Cài thêm `requirements-dev.txt` trong môi trường phát triển; kiểm thử trình
duyệt sử dụng Playwright và Chrome đã cài. Công cụ định dạng giao diện cài
bằng `npm ci`; Node chỉ dùng cho công cụ phát triển, không phải web server.

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m ruff check app.py screen.py train.py weapon_detection tests training
python -m ruff format --check app.py screen.py train.py weapon_detection tests training
npm run test:js
npm run format:check
python tests/ui_smoke.py
```

Định dạng mã bằng `python -m ruff format ...` và `npm run format`.
Kiểm thử giao diện dùng database và thông báo giả trong thư mục tạm;
không gửi Telegram thật. Giữ nguyên database, ảnh, video, weights và khóa
phiên đăng nhập khi cập nhật mã nguồn.
