

import math
import os
import threading
import time
from datetime import datetime

import cv2
import numpy as np

from weapon_detection import config
from weapon_detection.detection.model import draw_detections
from weapon_detection.storage import db

workers = {}
telemetry = {}
STREAM_MAX_W = 960
TRACK_TTL = 1.5
TRACK_MAX_MISSES = 2
TRACK_PREDICTION_HORIZON = 1.0
ALERT_FRAME_MAX_AGE = 0.35
FOLLOWUP_EVIDENCE_COUNT = 5
FOLLOWUP_FRAME_INTERVAL = 3
_demo_alert_lock = threading.Lock()
_demo_alert_states = {}
_demo_latest_frames = {}
_demo_evidence_captures = {}
_settings_lock = threading.Lock()
_settings_cache = None
_settings_cached_at = 0.0


def _matching_alert_detections(anchor_detections, detections):
    unmatched = set(range(len(detections)))
    matched = []
    for anchor in anchor_detections:
        ax1, ay1, ax2, ay2 = anchor["box"]
        anchor_center = ((ax1 + ax2) / 2, (ay1 + ay2) / 2)
        anchor_scale = max(1.0, math.hypot(ax2 - ax1, ay2 - ay1))
        candidates = []
        for index in unmatched:
            detection = detections[index]
            if detection["label"] != anchor["label"]:
                continue
            box = detection["box"]
            center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            distance = math.dist(anchor_center, center)
            if distance <= max(64.0, anchor_scale * 1.5):
                candidates.append((distance, index))
        if candidates:
            _, index = min(candidates)
            unmatched.remove(index)
            matched.append(detections[index])
    return matched


class DetectionTracker:
    def __init__(self, ttl=TRACK_TTL):
        self.ttl = ttl
        self._tracks = {}
        self._next_id = 0

    @staticmethod
    def _center(box):
        x1, y1, x2, y2 = box
        return (x1 + x2) / 2, (y1 + y2) / 2

    @staticmethod
    def _move_box(box, dx, dy):
        x1, y1, x2, y2 = box
        return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

    @staticmethod
    def _iou(left, right):
        intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(
            0, min(left[3], right[3]) - max(left[1], right[1]))
        left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
        right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
        union = left_area + right_area - intersection
        return intersection / union if union else 0.0

    def update(self, detections, now=None):
        now = time.monotonic() if now is None else now
        self._tracks = {
            track_id: track for track_id, track in self._tracks.items()
            if now - track["last_seen"] <= self.ttl
        }
        unmatched = set(self._tracks)
        class_track_counts = {}
        for track in self._tracks.values():
            label = track["detection"]["label"]
            class_track_counts[label] = class_track_counts.get(label, 0) + 1

        for detection in detections:
            box = tuple(float(value) for value in detection["box"])
            center = self._center(box)
            match_id, match_score = None, float("inf")
            for track_id in unmatched:
                track = self._tracks[track_id]
                if track["detection"]["label"] != detection["label"]:
                    continue
                age = max(0.0, now - track["last_seen"])
                predicted = self._move_box(
                    track["box"], track["velocity"][0] * age, track["velocity"][1] * age)
                predicted_center = self._center(predicted)
                distance = math.dist(center, predicted_center)
                width = max(box[2] - box[0], predicted[2] - predicted[0])
                height = max(box[3] - box[1], predicted[3] - predicted[1])
                allowance = max(64.0, math.hypot(width, height) * 1.25) + age * 400
                overlap = self._iou(box, predicted)
                if overlap < 0.01 and distance > allowance:
                    continue
                score = distance / allowance * (1 - min(overlap, 0.9) * 0.5)
                if score < match_score:
                    match_id, match_score = track_id, score

            if match_id is None:
                track_id = self._next_id
                self._next_id += 1
                self._tracks[track_id] = {
                    "box": box, "measurement_box": box, "velocity": (0.0, 0.0),
                    "last_seen": now, "misses": 0, "detection": dict(detection),
                }
            else:
                track_id = match_id
                unmatched.remove(track_id)
                track = self._tracks[track_id]
                previous_box = track["box"]
                dt = max(now - track["last_seen"], 1e-3)
                previous_box_center = self._center(previous_box)
                predicted_center = (
                    previous_box_center[0] + track["velocity"][0] * dt,
                    previous_box_center[1] + track["velocity"][1] * dt,
                )
                residual = (center[0] - predicted_center[0],
                            center[1] - predicted_center[1])
                smoothed_center = (
                    predicted_center[0] + 0.85 * residual[0],
                    predicted_center[1] + 0.85 * residual[1],
                )
                velocity = tuple(
                    max(-2500.0, min(2500.0,
                                     current + 0.05 * error / dt))
                    for current, error in zip(track["velocity"], residual)
                )
                width = 0.8 * (box[2] - box[0]) + 0.2 * (previous_box[2] - previous_box[0])
                height = 0.8 * (box[3] - box[1]) + 0.2 * (previous_box[3] - previous_box[1])
                smoothed_box = (
                    smoothed_center[0] - width / 2,
                    smoothed_center[1] - height / 2,
                    smoothed_center[0] + width / 2,
                    smoothed_center[1] + height / 2,
                )
                track.update(box=smoothed_box, measurement_box=box,
                             velocity=velocity, last_seen=now, misses=0,
                             detection=dict(detection))

        detection_labels = {detection["label"] for detection in detections}
        for track_id in unmatched:
            track = self._tracks[track_id]
            track["misses"] += 1
            label = track["detection"]["label"]
            if (track["misses"] >= TRACK_MAX_MISSES
                    or (label in detection_labels and class_track_counts[label] == 1)):
                self._tracks.pop(track_id, None)

        return self.current(now)

    def current(self, now=None):
        now = time.monotonic() if now is None else now
        tracked = []
        for track in self._tracks.values():
            age = now - track["last_seen"]
            if age > self.ttl:
                continue
            prediction_age = min(max(0.0, age), TRACK_PREDICTION_HORIZON)
            predicted = self._move_box(
                track["box"], track["velocity"][0] * prediction_age,
                track["velocity"][1] * prediction_age)
            tracked.append({**track["detection"],
                            "box": tuple(round(value) for value in predicted)})
        return tracked


def text_jpeg(text):
    img = np.zeros((360, 640, 3), np.uint8)
    cv2.putText(img, text, (30, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (150, 160, 170), 2)
    return cv2.imencode(".jpg", img)[1].tobytes()


def get_detection_settings():
    global _settings_cache, _settings_cached_at
    now = time.monotonic()
    with _settings_lock:
        if _settings_cache is None or now - _settings_cached_at >= 1.0:
            _settings_cache = db.get_settings()
            _settings_cached_at = now
        return dict(_settings_cache)


def update_detection_settings(settings):
    global _settings_cache, _settings_cached_at
    with _settings_lock:
        _settings_cache = dict(settings)
        _settings_cached_at = time.monotonic()


def _resolve_url(url):
    url = str(url).strip()
    if url.isdigit():
        return int(url)
    if url.startswith(("rtsp://", "http://", "https://")):
        return url
    return str(config.BASE_DIR / url)


def _open(url):
    if isinstance(url, int):
        cap = cv2.VideoCapture(url, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    else:
        cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class StreamWorker(threading.Thread):
    def __init__(self, src, detector, on_detect, on_evidence):
        super().__init__(daemon=True)
        self.src, self.detector = src, detector
        self.on_detect, self.on_evidence = on_detect, on_evidence
        self.url = _resolve_url(src["url"])
        self.is_file = isinstance(self.url, str) and not self.url.startswith(("rtsp", "http"))
        self.online = False
        self.resolution = None
        self.fps = 0.0
        self.stopping = threading.Event()
        self.seq = 0
        self._jpeg = text_jpeg("Dang ket noi...")
        self._lock = threading.Lock()
        self._announced = None
        self._raw = None
        self._raw_seq = 0
        self._raw_ts = 0.0
        self._dets, self._dets_ts = [], 0.0
        self._display_tracker = DetectionTracker()
        self._display_lock = threading.Lock()
        self._streak, self._last_alert = 0, 0.0
        self._evidence_capture = None

    def stop(self):
        self.stopping.set()

    def get_jpeg(self):
        with self._lock:
            return self._jpeg

    def _put(self, jpeg):
        with self._lock:
            self._jpeg = jpeg
            self.seq += 1

    def _set_online(self, v):
        self.online = v
        if v != self._announced:
            self._announced = v
            db.log("INFO" if v else "ERROR", f'{self.src["name"]} {"online" if v else "offline"}',
                   f'{self.src["type"]} / {self.src["url"]}')


    def run(self):
        threading.Thread(target=self._detect_loop, daemon=True).start()
        while not self.stopping.is_set():
            cap = _open(self.url)
            if not cap.isOpened():
                self._set_online(False)
                self._put(text_jpeg("Mat tin hieu - dang thu lai"))
                self.stopping.wait(5)
                continue

            self._set_online(True)
            self.resolution = f"{int(cap.get(3))}x{int(cap.get(4))}"
            frame_time = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 25) if self.is_file else 0
            rewinds, t_prev, deadline = 0, time.time(), time.time()
            while not self.stopping.is_set():
                ok, frame = cap.read()
                if not ok:
                    if self.is_file and rewinds < 3:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        rewinds += 1
                        continue
                    break
                rewinds = 0
                self._raw, self._raw_seq, self._raw_ts = (
                    frame, self._raw_seq + 1, time.monotonic())

                with self._display_lock:
                    display_dets = self._display_tracker.current()
                out = draw_detections(frame.copy(), display_dets) if display_dets else frame
                h, w = out.shape[:2]
                if w > STREAM_MAX_W:
                    out = cv2.resize(out, (STREAM_MAX_W, int(h * STREAM_MAX_W / w)), interpolation=cv2.INTER_AREA)
                ok2, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok2:
                    self._put(buf.tobytes())

                now = time.time()
                self.fps = 0.9 * self.fps + 0.1 / max(now - t_prev, 1e-3)
                t_prev = now
                if frame_time:
                    deadline += frame_time
                    self.stopping.wait(max(0, deadline - time.time()))
            cap.release()
            self._set_online(False)
            self.stopping.wait(2)


    def _detect_loop(self):
        last_seq, last_t = -1, 0.0
        settings, settings_t = get_detection_settings(), time.monotonic()
        while not self.stopping.is_set():
            now = time.monotonic()
            if now - settings_t >= 1.0:
                settings = get_detection_settings()
                settings_t = now
            st = settings
            raw, seq, raw_ts = self._raw, self._raw_seq, self._raw_ts
            if raw is None or seq == last_seq or now - last_t < 1.0 / max(1, st["detect_fps"]):
                self.stopping.wait(0.01)
                continue
            last_seq, last_t = seq, now
            try:
                class_thresholds = {
                    label: st[key]
                    for label, key in config.CLASS_THRESHOLD_SETTINGS.items()
                }
                conf = min(class_thresholds.values())
                dets = self.detector.detect(
                    raw, conf, st["imgsz"], class_thresholds,
                    default_conf=st["conf_threshold"],
                )
            except Exception as e:
                db.log("ERROR", f'Detect lỗi trên {self.src["name"]}', str(e)[:200])
                self.stopping.wait(2)
                continue
            result_age = time.monotonic() - raw_ts
            self._dets, self._dets_ts = dets, raw_ts
            with self._display_lock:
                self._display_tracker.update(dets, raw_ts)
            if result_age <= ALERT_FRAME_MAX_AGE:
                try:
                    self._check_alert(raw, st)
                except Exception as e:
                    db.log("ERROR", f'Không thể lưu cảnh báo/bằng chứng trên {self.src["name"]}', str(e)[:200])
                    self.stopping.wait(1)

    def _check_alert(self, frame, st):
        if self._evidence_capture:
            self._evidence_capture["frames_until_sample"] -= 1
            if self._evidence_capture["frames_until_sample"] <= 0:
                capture = self._evidence_capture
                matching = _matching_alert_detections(capture["detections"], self._dets)
                if matching:
                    capture["detections"] = matching
                capture["captured"] += 1
                index = capture["captured"]
                self.on_evidence(
                    capture["alert_id"], self.src, frame, matching, datetime.now(), index)
                if index >= FOLLOWUP_EVIDENCE_COUNT:
                    self._evidence_capture = None
                else:
                    capture["frames_until_sample"] = FOLLOWUP_FRAME_INTERVAL

        self._streak = self._streak + 1 if self._dets else 0
        cooled = time.time() - self._last_alert > st["alert_cooldown"]
        if (self._evidence_capture is None
                and self._streak >= st["confirm_frames"] and cooled):
            alert_id = self.on_detect(self.src, frame.copy(), list(self._dets))
            self._evidence_capture = {
                "alert_id": alert_id,
                "detections": list(self._dets),
                "captured": 0,
                "frames_until_sample": FOLLOWUP_FRAME_INTERVAL,
            }
            self._last_alert = time.time()
            self._streak = 0


def start(src, detector, on_detect, on_evidence):
    stop(src["id"])
    if demo_video_filename(src):
        return
    if src.get("enabled"):
        w = StreamWorker(src, detector, on_detect, on_evidence)
        workers[src["id"]] = w
        w.start()


def stop(sid):
    with _demo_alert_lock:
        _demo_alert_states.pop(sid, None)
        _demo_latest_frames.pop(sid, None)
        _demo_evidence_captures.pop(sid, None)
    w = workers.pop(sid, None)
    if w:
        w.stop()


def get_telemetry(sid):
    ts, data = telemetry.get(sid, (0, {}))
    return data if time.time() - ts < 30 else {}


def demo_video_filename(src):
    url = str(src.get("url", ""))
    if not url.startswith("demo:"):
        return None
    filename = url.removeprefix("demo:")
    if not filename or filename != os.path.basename(filename):
        return None
    return filename


def get_demo_frame(sid):
    with _demo_alert_lock:
        frame = _demo_latest_frames.get(sid)
        return frame.copy() if frame is not None else None


def process_demo_detections(src, frame, dets, on_detect, on_evidence):
    settings = get_detection_settings()
    now = time.time()
    should_alert = False
    evidence_task = None
    with _demo_alert_lock:
        _demo_latest_frames[src["id"]] = frame.copy()
        streak, last_alert = _demo_alert_states.get(src["id"], (0, 0.0))
        streak = streak + 1 if dets else 0
        capture = _demo_evidence_captures.get(src["id"])
        if capture:
            capture["frames_until_sample"] -= 1
            if capture["frames_until_sample"] <= 0:
                capture["captured"] += 1
                index = capture["captured"]
                matching = _matching_alert_detections(capture["detections"], dets)
                if matching:
                    capture["detections"] = matching
                evidence_task = (capture["alert_id"], frame.copy(), matching, datetime.now(), index)
                if index >= FOLLOWUP_EVIDENCE_COUNT:
                    _demo_evidence_captures.pop(src["id"], None)
                else:
                    capture["frames_until_sample"] = FOLLOWUP_FRAME_INTERVAL
        if (not capture and streak >= settings["confirm_frames"]
                and now - last_alert > settings["alert_cooldown"]):
            should_alert = True
            streak, last_alert = 0, now
        _demo_alert_states[src["id"]] = streak, last_alert
    if should_alert:
        alert_id = on_detect(src, frame.copy(), list(dets))
        with _demo_alert_lock:
            _demo_evidence_captures[src["id"]] = {
                "alert_id": alert_id,
                "detections": list(dets),
                "captured": 0,
                "frames_until_sample": FOLLOWUP_FRAME_INTERVAL,
            }
    if evidence_task:
        on_evidence(
            evidence_task[0], evidence_task[1], evidence_task[2],
            evidence_task[3], evidence_task[4])
    return list(dets)
