"""Precompute a per-frame detection timeline; playback never runs the model."""

import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import cv2

from weapon_detection import config
from weapon_detection.detection.model import detect_frame

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-scan")
_lock = threading.Lock()
_jobs = {}


def cache_path(filename):
    return config.VIDEO_DIR / (filename + ".detections.json")


def load(filename):
    path = cache_path(filename)
    if not path.is_file():
        return None
    return _read(path, path.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _read(path, modified):
    return json.loads(path.read_text(encoding="utf-8"))


def ensure(filename, detector, settings, force=False):
    with _lock:
        current = _jobs.get(filename)
        if current and current["state"] in ("queued", "processing"):
            return dict(current)
        if not force and cache_path(filename).is_file():
            return {"state": "ready", "progress": 100}
        if not force and current and current["state"] == "error":
            return dict(current)
        if detector is None:
            return {"state": "error", "progress": 0, "error": "Model is not ready"}
        _jobs[filename] = {"state": "queued", "progress": 0}
        _pool.submit(_scan, filename, detector, dict(settings))
        return dict(_jobs[filename])


def status(filename):
    """Checking progress must never start inference."""
    with _lock:
        current = _jobs.get(filename)
        if current and current["state"] in ("queued", "processing", "error"):
            return dict(current)
        if cache_path(filename).is_file():
            return {"state": "ready", "progress": 100}
        return {"state": "idle", "progress": 0}


def _scan(filename, detector, settings):
    cap = cv2.VideoCapture(str(config.VIDEO_DIR / filename))
    output = cache_path(filename)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        if not cap.isOpened():
            raise ValueError("Cannot open video")
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Invalid video frame rate")
        count = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        frames, width, height = [], 0, 0
        with _lock:
            _jobs[filename] = {"state": "processing", "progress": 0}
        while True:
            if not (config.VIDEO_DIR / filename).is_file():
                raise ValueError("Video was removed during processing")
            ok, frame = cap.read()
            if not ok:
                break
            height, width = frame.shape[:2]
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if not math.isfinite(timestamp) or (frames and timestamp <= frames[-1]["time"]):
                timestamp = len(frames) / fps
            detections = detect_frame(detector, frame, settings)
            frames.append({"time": timestamp, "detections": detections})
            with _lock:
                _jobs[filename]["progress"] = min(99, round(len(frames) * 100 / count))
        if not frames:
            raise ValueError("Video contains no readable frames")
        detection_keys = {
            "imgsz",
            "conf_threshold",
            "detail_scan",
            *config.CLASS_THRESHOLD_SETTINGS.values(),
            *config.CLASS_ENABLED_SETTINGS.values(),
        }
        data = dict(
            version=1,
            fps=fps,
            width=width,
            height=height,
            frames=frames,
            settings={key: value for key, value in settings.items() if key in detection_keys},
            model=config.MODEL_PATH.name,
        )
        temporary.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        temporary.replace(output)
        with _lock:
            _jobs[filename] = {"state": "ready", "progress": 100}
    except Exception as error:
        temporary.unlink(missing_ok=True)
        with _lock:
            _jobs[filename] = {"state": "error", "progress": 0, "error": str(error)[:200]}
    finally:
        cap.release()
