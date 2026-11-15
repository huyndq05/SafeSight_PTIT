"""Excel report with actual embedded images, separate predictions and review."""

import io
import json

import cv2
import numpy as np
import xlsxwriter

from weapon_detection.detection.model import draw_detections

STATUS = dict(
    pending="Chờ xác minh",
    confirmed="Đã xác nhận",
    dispatched="Đã gửi thông báo",
    completed="Hoàn tất",
    deleted="Nhận diện sai",
)


def create_excel(stream, rows, images, preferences):
    workbook = xlsxwriter.Workbook(stream, {"strings_to_formulas": False, "strings_to_urls": False})
    sheet = workbook.add_worksheet("Lịch sử cảnh báo")
    header = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#1B3558",
            "font_color": "#FFFFFF",
            "text_wrap": True,
            "valign": "vcenter",
            "border": 1,
        }
    )
    text = workbook.add_format(
        {"text_wrap": True, "valign": "vcenter", "border": 1, "border_color": "#DEE5EF"}
    )
    numeric = workbook.add_format({"valign": "vcenter", "border": 1, "border_color": "#DEE5EF"})
    headings = [
        "Ảnh gốc",
        "Ảnh nhận diện",
        "Mã cảnh báo",
        "Nguồn",
        "Vị trí camera",
        "Phát hiện lúc",
        "Trạng thái xử lý",
        "Loại ảnh",
        "AI dự đoán",
        "Độ tin cậy",
        "Loại thực tế",
        "Lý do nhận diện sai",
        "Ghi chú đánh giá",
        "Người xử lý",
        "Thời điểm xử lý",
        "Trạng thái gửi",
        "Thông tin gửi",
        "Tên ảnh",
        "Thời điểm ảnh",
        "Dự đoán và box (JSON)",
    ]
    sheet.write_row(0, 0, headings, header)
    sheet.set_row(0, 34)
    sheet.set_column_pixels(0, 1, 254)
    sheet.set_column(2, 2, 14)
    sheet.set_column(3, 8, 24)
    sheet.set_column(9, 10, 18)
    sheet.set_column(11, 16, 30)
    sheet.set_column(17, 19, 35)
    sheet.freeze_panes(1, 3)
    for index, row in enumerate(rows, 1):
        sheet.set_row_pixels(index, 180)
        predictions = json.loads(row["predictions_json"] or "[]")
        values = [
            int(row["alert_id"]),
            row["source_name"],
            row["location"],
            row["created_at"],
            STATUS.get(row["status"], row["status"]),
            "Ban đầu" if row["image_type"] == "initial" else "Bằng chứng",
            ", ".join(d.get("label", "") for d in predictions),
            ", ".join(f"{d.get('conf', 0) * 100:.1f}%" for d in predictions),
            row["actual_label"],
            row["review_reason"],
            row["review_note"],
            row["handled_by"],
            row["handled_at"],
            row["notification_status"],
            row["notification_info"],
            row["image_file"],
            row["captured_at"],
            row["predictions_json"],
        ]
        for column, value in enumerate(values, 2):
            if isinstance(value, int):
                sheet.write_number(index, column, value, numeric)
            else:
                sheet.write_string(index, column, str(value)[:32767], text)
        path = images.get(row["image_path"])
        frame = None
        if path:
            try:
                frame = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            except OSError:
                pass
        if frame is None:
            sheet.write(index, 0, "Không có ảnh / không đọc được ảnh", text)
            sheet.write(index, 1, "Không có ảnh / không đọc được ảnh", text)
            continue
        h, w = frame.shape[:2]
        ratio = min(238 / w, 164 / h, 1)
        preview = cv2.resize(frame, (max(1, round(w * ratio)), max(1, round(h * ratio))))
        detections = [
            {**d, "box": [float(v) * ratio for v in d["box"]]}
            for d in predictions
            if isinstance(d.get("box"), list) and len(d["box"]) == 4
        ]
        annotated = draw_detections(
            preview.copy(),
            detections,
            style_options={**preferences, "display_width": preview.shape[1]},
        )
        for column, image in enumerate((preview, annotated)):
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if ok:
                sheet.insert_image(
                    index,
                    column,
                    "preview.jpg",
                    {
                        "image_data": io.BytesIO(encoded.tobytes()),
                        "object_position": 1,
                        "x_offset": 8,
                        "y_offset": 8,
                        "description": row["image_file"],
                    },
                )
    sheet.autofilter(0, 0, len(rows), len(headings) - 1)
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.repeat_rows(0)
    notes = workbook.add_worksheet("Hướng dẫn")
    notes.set_column(0, 0, 110)
    for index, line in enumerate(
        [
            "Ảnh được nhúng trong file Excel; không cần kết nối lại với SafeSight để xem.",
            "Mỗi dòng là một ảnh ban đầu hoặc bằng chứng, có ảnh gốc và ảnh vẽ lại box AI.",
            "Ảnh nhúng là bản xem trước thu nhỏ; tải ZIP để giữ ảnh gốc đầy đủ độ phân giải.",
            "Dự đoán AI và loại thực tế do nhân viên đánh giá được lưu riêng.",
            "Loại thực tế để trống nghĩa là chưa xác định, không tự coi là không có hung khí.",
            "Đây là báo cáo, không tự động tạo nhãn train. Cần rà soát và sửa box trước khi train.",
        ]
    ):
        notes.write_string(index, 0, line, text)
        notes.set_row(index, 34)
    workbook.close()
    stream.seek(0)
