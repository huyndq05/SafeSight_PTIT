
import math
import threading

import cv2

from weapon_detection import config
from weapon_detection.labels import normalize_label

COLORS = {
    "axe": (40, 160, 255),
    "baseball_bat": (255, 170, 40),
    "hammer": (200, 80, 220),
    "knife": (0, 170, 255),
    "machete": (60, 220, 110),
    "pistol": (60, 90, 255),
    "rifle": (180, 70, 70),
    "sword": (255, 90, 180),
    "stick": (220, 220, 40),
    "spear": (180, 120, 40),
}

CLASS_DUPLICATE_IOU = 0.65


def _suppress_cross_class_duplicates(detections):
    kept = []
    for detection in sorted(detections, key=lambda item: item["conf"], reverse=True):
        x1, y1, x2, y2 = detection["box"]
        area = max(0, x2 - x1) * max(0, y2 - y1)
        duplicate = False
        for accepted in kept:
            if detection["label"] == accepted["label"]:
                continue
            ax1, ay1, ax2, ay2 = accepted["box"]
            intersection = max(0, min(x2, ax2) - max(x1, ax1)) * max(
                0, min(y2, ay2) - max(y1, ay1))
            accepted_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
            union = area + accepted_area - intersection
            smaller_area = min(area, accepted_area)
            center_distance = math.hypot(
                (x1 + x2 - ax1 - ax2) / 2,
                (y1 + y2 - ay1 - ay2) / 2,
            )
            accepted_diagonal = math.hypot(ax2 - ax1, ay2 - ay1)
            detection_diagonal = math.hypot(x2 - x1, y2 - y1)
            same_object = (
                union and intersection / union >= CLASS_DUPLICATE_IOU
            ) or (
                smaller_area
                and intersection / smaller_area >= 0.9
                and center_distance <= max(accepted_diagonal, detection_diagonal) * 0.6
            )
            if same_object:
                duplicate = True
                break
        if not duplicate:
            kept.append(detection)
    return kept


class WeaponDetector:
    def __init__(self, model_path=config.MODEL_PATH):
        import torch
        import numpy as np
        from ultralytics import YOLO

        self.device = 0 if torch.cuda.is_available() else "cpu"
        self.model = YOLO(str(model_path))
        self.names = self.model.names
        self._lock = threading.Lock()
        print(f"[Detector] YOLO model={model_path} "
              f"classes={list(self.names.values())} "
              f"device={'GPU' if self.device != 'cpu' else 'CPU'}")
        self.detect(
            np.zeros((480, 640, 3), np.uint8),
            config.DEFAULT_SETTINGS["conf_threshold"],
            config.DEFAULT_SETTINGS["imgsz"],
        )

    def detect(self, frame, conf=0.5, imgsz=320, class_thresholds=None, default_conf=None):
        thresholds = class_thresholds or {}
        default_threshold = conf if default_conf is None else default_conf
        inference_conf = min([conf, default_threshold, *thresholds.values()])
        with self._lock:
            result = self.model.predict(
                frame,
                conf=inference_conf,
                imgsz=imgsz,
                device=self.device,
                verbose=False,
            )[0]
        out = []
        if result.boxes is None:
            return out

        for x1, y1, x2, y2, score, class_id in (
                result.boxes.data.detach().cpu().tolist()):
            label = normalize_label(result.names[int(class_id)]).lower().strip(" .")
            if label not in config.MODEL_CLASSES:
                continue
            confidence = float(score)
            threshold = thresholds.get(label, default_threshold)
            if confidence < threshold:
                continue
            out.append({
                "label": label,
                "conf": round(confidence, 3),
                "box": (int(x1), int(y1), int(x2), int(y2)),
            })
        return _suppress_cross_class_duplicates(out)


def draw_detections(frame, dets, color=None):
    scale = max(1.0, frame.shape[1] / 960)
    thickness = max(4, round(4 * scale))
    text_thickness = max(2, round(2 * scale))
    font_scale = 0.6 * scale
    for d in dets:
        x1, y1, x2, y2 = d["box"]
        c = color if color is not None else COLORS.get(d["label"], (0, 0, 255))
        cv2.rectangle(frame, (x1, y1), (x2, y2), c, thickness)
        text = f'{d["label"]} {d["conf"]:.2f}'
        (w, h), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_thickness)
        top = max(0, y1 - h - baseline - 8)
        cv2.rectangle(frame, (x1, top), (x1 + w + 8, y1), c, -1)
        cv2.putText(frame, text, (x1 + 4, max(h, y1 - baseline - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255),
                    text_thickness, cv2.LINE_AA)
    return frame


def draw_stamp(frame, text):
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(frame, (0, 0), (w + 14, h + 14), (0, 0, 0), -1)
    cv2.putText(frame, text, (7, h + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    return frame
