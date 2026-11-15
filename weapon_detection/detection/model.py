import math
import threading

import cv2

from weapon_detection import config
from weapon_detection.labels import normalize_label
from weapon_detection.detection.presentation import COLORS, DETECTION_STYLE, detection_label
from weapon_detection.detection.spatial import detail_views, merge_same_class

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
            intersection = max(0, min(x2, ax2) - max(x1, ax1)) * max(0, min(y2, ay2) - max(y1, ay1))
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
                union
                and intersection / union >= CLASS_DUPLICATE_IOU
                and center_distance <= min(accepted_diagonal, detection_diagonal) * 0.15
                and smaller_area / max(area, accepted_area, 1) >= 0.8
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
        print(
            f"[Detector] YOLO model={model_path} "
            f"classes={list(self.names.values())} "
            f"device={'GPU' if self.device != 'cpu' else 'CPU'}"
        )
        self.detect(
            np.zeros((480, 640, 3), np.uint8),
            config.DEFAULT_SETTINGS["conf_threshold"],
            config.DEFAULT_SETTINGS["imgsz"],
            cascade=False,
        )

    def detect(
        self,
        frame,
        conf=0.5,
        imgsz=320,
        class_thresholds=None,
        default_conf=None,
        cascade=None,
        enabled_classes=None,
        detail_scan=False,
    ):
        thresholds = class_thresholds or {}
        default_threshold = conf if default_conf is None else default_conf
        inference_conf = min([conf, default_threshold, *thresholds.values()])
        use_cascade = config.CASCADE_ENABLED if cascade is None else cascade
        enabled = set(config.MODEL_CLASSES if enabled_classes is None else enabled_classes)
        if not enabled:
            return []
        with self._lock:
            proposals = self._predict(
                frame,
                inference_conf * config.CASCADE_PROPOSAL_RATIO if use_cascade else inference_conf,
                imgsz,
            )
            if detail_scan:
                proposals.extend(self._detail_proposals(frame, inference_conf))
                proposals = merge_same_class(proposals)
            proposals = [item for item in proposals if item["label"] in enabled]
            if use_cascade:
                return self._cascade(frame, proposals, thresholds, default_threshold)
        return _suppress_cross_class_duplicates(
            [
                item
                for item in proposals
                if item["conf"] >= thresholds.get(item["label"], default_threshold)
            ]
        )

    def _detail_proposals(self, frame, conf):
        out = []
        height, width = frame.shape[:2]
        for left, top, crop in detail_views(frame):
            h, w = crop.shape[:2]
            for item in self._predict(crop, conf, 640):
                x1, y1, x2, y2 = item["box"]
                if (
                    (left > 0 and x1 < 3)
                    or (top > 0 and y1 < 3)
                    or (left + w < width and x2 > w - 3)
                    or (top + h < height and y2 > h - 3)
                ):
                    continue
                out.append({**item, "box": (x1 + left, y1 + top, x2 + left, y2 + top)})
        return out

    def _predict(self, frame, conf, imgsz):
        result = self.model.predict(
            frame, conf=conf, imgsz=imgsz, device=self.device, verbose=False
        )[0]
        out = []
        if result.boxes is None:
            return out

        for x1, y1, x2, y2, score, class_id in result.boxes.data.detach().cpu().tolist():
            label = normalize_label(result.names[int(class_id)]).lower().strip(" .")
            if label not in config.MODEL_CLASSES:
                continue
            confidence = float(score)
            if not math.isfinite(confidence) or not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                continue
            height, width = frame.shape[:2]
            x1, x2 = max(0, min(width, int(x1))), max(0, min(width, int(x2)))
            y1, y2 = max(0, min(height, int(y1))), max(0, min(height, int(y2)))
            if x2 <= x1 or y2 <= y1:
                continue
            out.append(
                {
                    "label": label,
                    "conf": round(confidence, 3),
                    "box": (int(x1), int(y1), int(x2), int(y2)),
                }
            )
        return out

    @staticmethod
    def _overlap(left, right):
        intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(
            0, min(left[3], right[3]) - max(left[1], right[1])
        )
        union = (
            (left[2] - left[0]) * (left[3] - left[1])
            + (right[2] - right[0]) * (right[3] - right[1])
            - intersection
        )
        return intersection / union if union > 0 else 0.0

    def _cascade(self, frame, proposals, thresholds, default_threshold):
        accepted, verified = [], 0
        height, width = frame.shape[:2]
        for proposal in _suppress_cross_class_duplicates(proposals):
            threshold = thresholds.get(proposal["label"], default_threshold)
            if proposal["conf"] < threshold * config.CASCADE_PROPOSAL_RATIO:
                continue
            if proposal["conf"] >= max(threshold, config.CASCADE_DIRECT_CONF):
                accepted.append(proposal)
                continue
            if verified >= config.CASCADE_MAX_VERIFY:
                continue
            x1, y1, x2, y2 = proposal["box"]
            px, py = (
                (x2 - x1) * config.CASCADE_CROP_PADDING,
                (y2 - y1) * config.CASCADE_CROP_PADDING,
            )
            left, top = max(0, int(x1 - px)), max(0, int(y1 - py))
            right, bottom = min(width, math.ceil(x2 + px)), min(height, math.ceil(y2 + py))
            crop = frame[top:bottom, left:right]
            if not crop.size:
                continue
            verified += 1
            candidates = self._predict(crop, threshold, config.CASCADE_VERIFY_IMGSZ)
            for candidate in sorted(candidates, key=lambda item: item["conf"], reverse=True):
                if candidate["label"] != proposal["label"] or candidate["conf"] < threshold:
                    continue
                bx1, by1, bx2, by2 = candidate["box"]
                box = (bx1 + left, by1 + top, bx2 + left, by2 + top)
                score = math.sqrt(proposal["conf"] * candidate["conf"])
                if score >= threshold and self._overlap(proposal["box"], box) >= 0.3:
                    accepted.append(
                        {"label": proposal["label"], "conf": round(score, 3), "box": box}
                    )
                    break
        return _suppress_cross_class_duplicates(accepted)


def draw_detections(frame, dets, color=None, style_options=None):
    options = style_options or {}
    scale = max(1.0, frame.shape[1] / DETECTION_STYLE["reference_width"])
    if options.get("display_width"):
        scale = frame.shape[1] / max(160, options["display_width"])
    thickness = max(1, round(options.get("box_width", DETECTION_STYLE["line_width"]) * scale))
    text_thickness = max(2, round(2 * scale))
    font_scale = 0.6 * scale * options.get("label_size", 18) / 18
    for d in dets:
        if len(d.get("box", [])) != 4 or not all(math.isfinite(v) for v in (*d["box"], d["conf"])):
            continue
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [
            max(0, min(limit - 1, int(v)))
            for v, limit in zip(d["box"], (width, height, width, height))
        ]
        if x2 <= x1 or y2 <= y1:
            continue
        c = color if color is not None else COLORS.get(d["label"], (0, 0, 255))
        custom_color = options.get("color_" + d["label"])
        if (
            isinstance(custom_color, str)
            and len(custom_color) == 7
            and custom_color.startswith("#")
        ):
            try:
                c = tuple(int(custom_color[index : index + 2], 16) for index in (5, 3, 1))
            except ValueError:
                pass
        cv2.rectangle(frame, (x1, y1), (x2, y2), c, thickness)
        if options.get("label_content") == "none":
            continue
        text = detection_label(d)
        if options.get("label_content") == "name":
            text = d["label"]
        elif options.get("label_content") == "confidence":
            text = f"{round(d['conf'] * 100)}%"
        (w, h), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_thickness
        )
        padding = max(1, round(DETECTION_STYLE["padding"] * scale))
        tag_height = max(
            round((options.get("label_size", DETECTION_STYLE["font_size"]) + 10) * scale),
            h + baseline + 2 * padding,
        )
        left = max(0, min(x1, width - w - 2 * padding))
        top = max(0, min(y1 - tag_height, height - tag_height))
        cv2.rectangle(
            frame,
            (left, top),
            (min(width - 1, left + w + 2 * padding), min(height - 1, top + tag_height)),
            c,
            -1,
        )
        cv2.putText(
            frame,
            text,
            (left + padding, top + tag_height - baseline - padding),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (17, 17, 17) if 0.299 * c[2] + 0.587 * c[1] + 0.114 * c[0] > 150 else (255, 255, 255),
            text_thickness,
            cv2.LINE_AA,
        )
    return frame


def detect_frame(detector, frame, settings):
    """Use the same model options for camera workers and uploaded video frames."""
    thresholds = {label: settings[key] for label, key in config.CLASS_THRESHOLD_SETTINGS.items()}
    enabled = [
        label for label, key in config.CLASS_ENABLED_SETTINGS.items() if settings.get(key, True)
    ]
    return detector.detect(
        frame,
        min(thresholds.values()),
        settings["imgsz"],
        thresholds,
        default_conf=settings["conf_threshold"],
        enabled_classes=enabled,
        detail_scan=settings.get("detail_scan", False),
    )


def draw_stamp(frame, text):
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(frame, (0, 0), (w + 14, h + 14), (0, 0, 0), -1)
    cv2.putText(
        frame, text, (7, h + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA
    )
    return frame
