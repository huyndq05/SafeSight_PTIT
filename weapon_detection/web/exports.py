"""Review exports retain predictions separately from human corrections."""

import csv
import io
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from flask import request, jsonify, send_file, url_for
from weapon_detection import config
from weapon_detection.storage import db

FIELDS = [
    "alert_id",
    "created_at",
    "status",
    "source_id",
    "source_name",
    "location",
    "handled_by",
    "handled_at",
    "review_reason",
    "actual_label",
    "review_note",
    "notification_status",
    "notification_info",
    "image_type",
    "captured_at",
    "image_file",
    "image_path",
    "image_url",
    "image_exists",
    "predictions_json",
    "events_json",
]


def safe_cell(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def build_export(alerts):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    images = {}
    for alert in alerts:
        entries = [
            dict(
                image=alert["image"],
                detections=alert["detections"],
                captured_at=alert["created_at"],
                image_type="initial",
            )
        ]
        entries += [{**item, "image_type": "evidence"} for item in alert["evidence_images"]]
        for entry in entries:
            image = entry["image"]
            path = config.ALERT_DIR / image
            exists = bool(image and Path(image).name == image and path.is_file())
            relative = "images/" + image if image and Path(image).name == image else ""
            if exists:
                images[relative] = path
            row = {key: alert.get(key, "") for key in FIELDS}
            row.update(
                alert_id=alert["id"],
                image_type=entry["image_type"],
                captured_at=entry.get("captured_at") or "",
                image_file=image,
                image_path=relative,
                image_url=url_for("alert_image", name=image, _external=True) if relative else "",
                image_exists=int(exists),
                predictions_json=json.dumps(entry.get("detections", []), ensure_ascii=False),
                events_json=json.dumps(alert["events"], ensure_ascii=False),
            )
            writer.writerow({key: safe_cell(value) for key, value in row.items()})
    return buffer.getvalue().encode("utf-8-sig"), images


def install(app):
    @app.get("/api/alerts/export")
    def api_export_alerts():
        status = request.args.get("status", "all")
        format = request.args.get("format", "csv")
        if format not in ("csv", "zip", "xlsx"):
            return jsonify(error="Invalid export format"), 400
        try:
            alerts = db.export_alerts(status)
        except ValueError:
            return jsonify(error="Invalid status"), 400
        content, images = build_export(alerts)
        filename = f"safesight_{status}_{datetime.now():%Y%m%d_%H%M%S}"
        if format == "xlsx":
            from weapon_detection.web.excel_export import create_excel
            from weapon_detection.web.preferences import get_preferences

            rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
            stream = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
            try:
                create_excel(stream, rows, images, get_preferences())
            except Exception:
                stream.close()
                raise
            response = send_file(
                stream,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=filename + ".xlsx",
            )
            response.call_on_close(stream.close)
            return response
        if format == "csv":
            return send_file(
                io.BytesIO(content),
                mimetype="text/csv; charset=utf-8",
                as_attachment=True,
                download_name=filename + ".csv",
            )
        stream = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("alerts.csv", content)
            for relative, path in images.items():
                try:
                    archive.write(path, relative)
                except FileNotFoundError:
                    pass
            archive.writestr(
                "README.txt",
                "CSV uses UTF-8 BOM. One row per image; image_path is relative to this ZIP.\n"
                "predictions_json contains model predictions, NOT verified training labels.\n"
                "actual_label is optional human review. Empty means unknown, not background.\n"
                "notification_status records delivery separately from the review verdict.\n"
                "Review boxes and split by source video/session before training.\n",
            )
        stream.seek(0)
        response = send_file(
            stream, mimetype="application/zip", as_attachment=True, download_name=filename + ".zip"
        )
        response.call_on_close(stream.close)
        return response
