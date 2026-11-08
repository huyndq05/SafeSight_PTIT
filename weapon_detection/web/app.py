import os
import re
import sqlite3


os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay")

import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory

from weapon_detection import config
from weapon_detection.detection import streams as manager
from weapon_detection.detection.model import WeaponDetector, draw_detections, draw_stamp
from weapon_detection.notifications import notifier
from weapon_detection.storage import db

app = Flask(
    __name__,
    static_folder=str(config.BASE_DIR / "static"),
    template_folder=str(config.BASE_DIR / "templates"),
)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_DEMO_VIDEO_BYTES + 1024 * 1024
detector = None
MAX_FRAME_BYTES = 20 * 1024 * 1024
MAX_REQUEST_BYTES = 20 * 1024 * 1024


@app.before_request
def enforce_request_size():
    upload_route = request.endpoint in ("api_source_create", "api_source_update")
    if upload_route and request.mimetype == "multipart/form-data":
        video = request.files.get("video")
        if request.form.get("type") == "camera" and video and video.filename:
            return None
    if request.content_length and request.content_length > MAX_REQUEST_BYTES:
        return jsonify(error="Yêu cầu vượt quá giới hạn 20 MB"), 413
    return None


def operator():
    return db.get_settings()["operator"]


def on_detect(src, frame, dets):
    name = f'{src["id"]}_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg'
    image = frame.copy()
    draw_stamp(image, f'{src["name"]}  {datetime.now():%Y-%m-%d %H:%M:%S}')
    if not cv2.imwrite(str(config.ALERT_DIR / name), image):
        raise OSError(f"Không thể lưu ảnh cảnh báo: {name}")
    aid = db.create_alert(src, dets, name)
    labels = ", ".join(sorted({d["label"] for d in dets}))
    db.log("ALERT", f"Alert #{aid} từ {src['name']}", labels)
    print(f"[ALERT #{aid}] {src['name']}: {labels}")
    return aid


def on_evidence(aid, src, frame, dets, captured_at, index):
    name = f'{src["id"]}_{datetime.now():%Y%m%d_%H%M%S_%f}_e{index}.jpg'
    evidence = frame.copy()
    description = f'Ảnh theo dõi tiếp diễn {index}/5'
    if not dets:
        description += " - không phát hiện lại vật thể mục tiêu"
    draw_stamp(evidence, f'{description}  {captured_at:%Y-%m-%d %H:%M:%S.%f}')
    if not cv2.imwrite(str(config.ALERT_DIR / name), evidence):
        raise OSError(f"Không thể lưu ảnh bằng chứng: {name}")
    if not db.add_alert_evidence(aid, name, dets, captured_at):
        raise RuntimeError(f"Không tìm thấy cảnh báo #{aid} để gắn ảnh bằng chứng")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed/<sid>")
def video_feed(sid):
    def gen():
        last = -1
        while True:
            w = manager.workers.get(sid)
            if w is None:
                jpg, last = manager.text_jpeg("Thiet bi dang tat"), -1
                time.sleep(0.5)
            elif w.seq == last:
                time.sleep(0.005)
                continue
            else:
                last, jpg = w.seq, w.get_jpeg()
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/alert_images/<path:name>")
def alert_image(name):
    return send_from_directory(config.ALERT_DIR, name)


@app.get("/source_video/<sid>")
def source_video(sid):
    src = db.get_source(sid) or abort(404)
    filename = manager.demo_video_filename(src)
    if not filename or not (config.VIDEO_DIR / filename).is_file():
        abort(404)
    return send_from_directory(config.VIDEO_DIR, filename, conditional=True)


def _clean_source(d, old=None):
    t = d.get("type") or (old or {}).get("type")
    if t not in ("camera", "drone", "robot"):
        abort(400, "type phải là camera, drone hoặc robot")
    name, url = str(d.get("name", "")).strip(), str(d.get("url", "")).strip()
    if not name or not url:
        abort(400, "Cần tên và nguồn video")
    if url.startswith("demo:") and t != "camera":
        abort(400, "Video demo chỉ hỗ trợ camera")

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    enabled = d.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() in ("true", "1", "yes", "on")
    return {"id": (old or {}).get("id") or f"{t}-{uuid.uuid4().hex[:6]}", "name": name, "type": t, "url": url,
            "location": str(d.get("location", "")).strip(),
            "lat": None if t == "camera" else num(d.get("lat")),
            "lon": None if t == "camera" else num(d.get("lon")),
            "enabled": 1 if t == "camera" or enabled else 0}


def _save_source_from_request(old=None):
    upload = None
    if request.mimetype == "multipart/form-data":
        data = request.form.to_dict()
        upload = request.files.get("video")
    else:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            abort(400, "Thông tin thiết bị không hợp lệ")

    uploaded_path = None
    if upload and upload.filename:
        if (data.get("type") or (old or {}).get("type")) != "camera":
            abort(400, "Chỉ camera mới nhận video demo")
        if not str(data.get("name", "")).strip():
            abort(400, "Cần nhập tên camera")
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in (".mp4", ".webm"):
            abort(400, "Chỉ hỗ trợ video MP4 hoặc WebM")
        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size == 0:
            abort(400, "Tệp video rỗng")
        if size > config.MAX_DEMO_VIDEO_BYTES:
            abort(413, "Video vượt quá giới hạn 512 MB")
        config.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        uploaded_path = config.VIDEO_DIR / f"{uuid.uuid4().hex}{suffix}"
        data["url"] = f"demo:{uploaded_path.name}"
        upload.save(uploaded_path)

    try:
        src = _clean_source(data, old)
    except Exception:
        if uploaded_path:
            uploaded_path.unlink(missing_ok=True)
        raise
    filename = manager.demo_video_filename(src)
    if filename and not (config.VIDEO_DIR / filename).is_file():
        if uploaded_path:
            uploaded_path.unlink(missing_ok=True)
        abort(400, "Không tìm thấy tệp video demo")

    try:
        db.save_source(src)
    except Exception:
        if uploaded_path:
            uploaded_path.unlink(missing_ok=True)
        raise

    old_filename = manager.demo_video_filename(old or {})
    if old_filename and old_filename != filename:
        _remove_demo_video(old_filename, src["id"])
    return src


def _remove_demo_video(filename, sid):
    try:
        (config.VIDEO_DIR / filename).unlink(missing_ok=True)
    except PermissionError as error:
        db.log("ERROR", f"Không thể xóa video demo của nguồn {sid}", str(error)[:200])
        return False
    return True


@app.get("/api/sources")
def api_sources():
    out = []
    for s in db.list_sources():
        w = manager.workers.get(s["id"])
        demo_video = manager.demo_video_filename(s)
        video_available = bool(demo_video and (config.VIDEO_DIR / demo_video).is_file())
        out.append({**s, "demo_video": video_available,
                    "video_name": demo_video if video_available else None,
                    "online": bool((w and w.online) or video_available),
                    "resolution": w.resolution if w else None, "fps": round(w.fps, 1) if w else 0,
                    "telemetry": manager.get_telemetry(s["id"])})
    return jsonify(out)


@app.post("/api/sources")
def api_source_create():
    s = _save_source_from_request()
    db.log("INFO", f"Thêm thiết bị {s['name']}", s["type"])
    manager.start(s, detector, on_detect, on_evidence)
    return jsonify(s)


@app.put("/api/sources/<sid>")
def api_source_update(sid):
    old = db.get_source(sid) or abort(404)
    s = _save_source_from_request(old)
    db.log("INFO", f"Sửa thiết bị {s['name']}", s["type"])
    manager.start(s, detector, on_detect, on_evidence)
    return jsonify(s)


@app.delete("/api/sources/<sid>")
def api_source_delete(sid):
    s = db.get_source(sid) or abort(404)
    manager.stop(sid)
    filename = manager.demo_video_filename(s)
    if filename and not _remove_demo_video(filename, sid):
        manager.start(s, detector, on_detect, on_evidence)
        return jsonify(error="Đóng video trong Live Ops rồi thử xóa lại"), 409
    db.delete_source(sid)
    db.log("INFO", f"Xóa thiết bị {s['name']}", s["type"])
    return jsonify(ok=True)


@app.post("/api/sources/<sid>/frame")
def api_source_frame(sid):
    src = db.get_source(sid) or abort(404)
    filename = manager.demo_video_filename(src)
    if not filename or not (config.VIDEO_DIR / filename).is_file():
        abort(400, "Nguồn này không phải video demo hợp lệ")
    payload = request.stream.read(MAX_FRAME_BYTES + 1)
    if not payload:
        return jsonify(error="Khung hình video rỗng"), 400
    if len(payload) > MAX_FRAME_BYTES:
        return jsonify(error="Khung hình video vượt quá giới hạn 20 MB"), 413
    frame = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify(error="Khung hình video không hợp lệ"), 400
    if detector is None:
        return jsonify(error="Mô hình chưa được khởi tạo"), 503
    settings = manager.get_detection_settings()
    started = time.perf_counter()
    class_thresholds = {
        label: settings[key]
        for label, key in config.CLASS_THRESHOLD_SETTINGS.items()
    }
    conf = min(class_thresholds.values())
    dets = detector.detect(
        frame, conf, settings["imgsz"], class_thresholds,
        default_conf=settings["conf_threshold"],
    )
    display_dets = manager.process_demo_detections(
        src, frame, dets, on_detect,
        lambda aid, evidence_frame, evidence_dets, captured_at, index:
            on_evidence(aid, src, evidence_frame, evidence_dets, captured_at, index),
    )
    return jsonify(
        detections=display_dets,
        inference_ms=round((time.perf_counter() - started) * 1000, 1),
        width=frame.shape[1],
        height=frame.shape[0],
    )


@app.post("/api/sources/<sid>/telemetry")
def api_telemetry(sid):
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        abort(400)
    manager.telemetry[sid] = (time.time(), {k: v for k, v in data.items() if isinstance(v, (int, float, str))})
    return jsonify(ok=True)


@app.get("/api/alerts")
def api_alerts():
    group = request.args.get("status", "pending")
    return jsonify(db.list_alerts(group if group in ("pending", "history", "all") else "pending"))


def _resolve(aid, status):
    if not db.set_status(aid, status, operator()):
        abort(409)
    return db.get_alert(aid)


@app.post("/api/alerts/<int:aid>/dispatch")
def api_dispatch(aid):
    a = _resolve(aid, "dispatched")
    ok, info = notifier.send_dispatch(a)
    db.log("DISPATCH", f"Dispatch alert #{aid}", f"{operator()} - {info}")
    return jsonify(ok=ok, info=info)


@app.post("/api/alerts/<int:aid>/delete")
def api_delete(aid):
    _resolve(aid, "deleted")
    db.log("INFO", f"Delete alert #{aid}", f"{operator()} - báo động giả")
    return jsonify(ok=True)


@app.post("/api/alerts/clear")
def api_clear():
    n = db.clear_pending(operator())
    db.log("INFO", f"Clear all: xóa {n} alert", operator())
    return jsonify(ok=True, count=n)


@app.post("/api/alerts/<int:aid>/note")
def api_note(aid):
    text = str((request.get_json(force=True) or {}).get("text", "")).strip()
    if not text or not db.add_note(aid, text, operator()):
        abort(400)
    return jsonify(ok=True)


@app.get("/api/stats")
def api_stats():
    return jsonify(db.stats())


@app.get("/api/logs")
def api_logs():
    return jsonify(db.list_logs())


@app.get("/api/settings")
def api_settings():
    return jsonify(db.get_settings())


@app.put("/api/settings")
def api_settings_put():
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        abort(400, "Cài đặt phải có định dạng đối tượng JSON")
    try:
        s = db.set_settings(data)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    manager.update_detection_settings(s)
    db.log("INFO", "Cập nhật cài đặt", operator())
    return jsonify(s)


@app.post("/api/notify/test")
def api_notify_test():
    devices = [device for device in db.list_mobile_devices() if device["enabled"]]
    if not devices:
        return jsonify(ok=False, info="Chưa có thiết bị di động nào được bật để nhận thông báo.")
    results = [notifier.send_test(device["chat_id"], device["name"]) for device in devices]
    delivered = sum(ok for ok, _ in results)
    failures = [info for ok, info in results if not ok]
    info = f"Đã gửi thử tới {delivered}/{len(devices)} thiết bị."
    if failures:
        info += " " + " ".join(failures)
    return jsonify(ok=delivered == len(devices), info=info)


@app.get("/api/mobile-devices")
def api_mobile_devices():
    return jsonify(db.list_mobile_devices())


@app.post("/api/mobile-devices")
def api_mobile_device_create():
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        abort(400, "Thông tin thiết bị không hợp lệ")
    name = str(data.get("name", "")).strip()
    chat_id = str(data.get("chat_id", "")).strip()
    if not name or len(name) > 80:
        abort(400, "Tên thiết bị không hợp lệ")
    if not re.fullmatch(r"-?\d+", chat_id):
        abort(400, "Chat ID phải là số")
    try:
        return jsonify(db.add_mobile_device(name, chat_id)), 201
    except sqlite3.IntegrityError:
        abort(409, "Chat ID này đã được thêm")


@app.delete("/api/mobile-devices/<int:device_id>")
def api_mobile_device_delete(device_id):
    if not db.delete_mobile_device(device_id):
        abort(404)
    return jsonify(ok=True)


@app.put("/api/mobile-devices/<int:device_id>")
def api_mobile_device_update(device_id):
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        abort(400, "Thông tin thiết bị không hợp lệ")
    name = None
    enabled = None
    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > 80:
            abort(400, "Tên thiết bị không hợp lệ")
    if "enabled" in data:
        if not isinstance(data["enabled"], bool):
            abort(400, "Trạng thái thiết bị không hợp lệ")
        enabled = data["enabled"]
    if name is None and enabled is None:
        abort(400, "Không có thông tin cần cập nhật")
    device = db.update_mobile_device(device_id, name=name, enabled=enabled)
    if not device:
        abort(404)
    return jsonify(device)


@app.post("/api/mobile-devices/<int:device_id>/test")
def api_mobile_device_test(device_id):
    device = next((item for item in db.list_mobile_devices() if item["id"] == device_id), None)
    if not device:
        abort(404)
    ok, info = notifier.send_test(device["chat_id"], device["name"])
    return jsonify(ok=ok, info=info)


def main():
    global detector
    if not config.MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO weights not found: {config.MODEL_PATH}. "
            "Copy ss_final_1.pt into the models folder."
        )
    config.ALERT_DIR.mkdir(parents=True, exist_ok=True)
    db.init()
    detector = WeaponDetector(config.MODEL_PATH)
    print("Classes:", detector.names)
    for s in db.list_sources():
        manager.start(s, detector, on_detect, on_evidence)
    db.log("INFO", "Hệ thống khởi động", f"{len(db.list_sources())} thiết bị")
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)
