import argparse
import math
import threading
import time
from pathlib import Path

import cv2
import mss
import numpy as np

from weapon_detection import config
from weapon_detection.detection.model import (
    WeaponDetector, draw_detections, draw_stamp,
)
from weapon_detection.detection.streams import DetectionTracker


class LatestScreenCapture:
    def __init__(self, region):
        self._region = region
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._frame = None
        self._captured_at = 0.0
        self._sequence = 0
        self._error = None
        self._thread = threading.Thread(target=self._capture, daemon=True)

    def start(self):
        self._thread.start()

    def read(self, after_sequence):
        with self._condition:
            self._condition.wait_for(
                lambda: self._sequence > after_sequence
                or self._error is not None
                or self._stop_event.is_set()
            )
            if self._error is not None:
                raise RuntimeError("Screen capture failed.") from self._error
            if self._sequence <= after_sequence:
                return None, None, None
            return self._sequence, self._frame, self._captured_at

    @property
    def stopped(self):
        return self._stop_event.is_set()

    def wait(self, timeout):
        return self._stop_event.wait(timeout)

    def stop(self):
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        self._thread.join()

    def _capture(self):
        try:
            with mss.MSS() as capture:
                while not self._stop_event.is_set():
                    frame = cv2.cvtColor(
                        np.asarray(capture.grab(self._region)), cv2.COLOR_BGRA2BGR
                    )
                    captured_at = time.monotonic()
                    with self._condition:
                        self._frame = frame
                        self._captured_at = captured_at
                        self._sequence += 1
                        self._condition.notify_all()
        except Exception as error:
            with self._condition:
                self._error = error
                self._condition.notify_all()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture the screen and run YOLO weapon detection."
    )
    parser.add_argument(
        "--monitor", type=int, default=1,
        help="MSS monitor number, default: 1. Use --list-monitors to list monitors.",
    )
    parser.add_argument(
        "--list-monitors", action="store_true",
        help="List available monitors and exit.",
    )
    parser.add_argument(
        "--region", type=int, nargs=4, metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"),
        help="Capture only a region, relative to the selected monitor.",
    )
    parser.add_argument(
        "--conf", type=float, default=config.DEFAULT_SETTINGS["conf_threshold"],
        help="Confidence threshold, default: %(default)s.",
    )
    parser.add_argument(
        "--imgsz", type=int, default=config.DEFAULT_SETTINGS["imgsz"],
        help="Model input size, default: %(default)s.",
    )
    parser.add_argument(
        "--fps", type=float, default=30.0,
        help="Maximum preview and detection rate (default: %(default)s); "
             "the model may update detections more slowly.",
    )
    parser.add_argument(
        "--model", type=Path,
        default=config.MODEL_PATH,
        help="YOLO weights file, default: %(default)s.",
    )
    parser.add_argument(
        "--class-conf", action="append", default=[], metavar="CLASS=VALUE",
        help="Confidence threshold for a class (0-1); may be repeated.",
    )
    args = parser.parse_args()
    if not math.isfinite(args.conf) or not 0 <= args.conf <= 1:
        parser.error("--conf must be between 0 and 1")
    args.class_thresholds = {
        label: args.conf for label in config.MODEL_CLASSES
    }
    for item in args.class_conf:
        try:
            label, value = item.split("=", 1)
            threshold = float(value)
        except ValueError:
            parser.error(f"--class-conf must use CLASS=VALUE: {item}")
        if label not in config.MODEL_CLASSES:
            parser.error(
                f"unknown class {label!r}; choose from {', '.join(config.MODEL_CLASSES)}"
            )
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            parser.error(f"--class-conf value must be between 0 and 1: {item}")
        args.class_thresholds[label] = threshold
    if args.imgsz < 1:
        parser.error("--imgsz must be greater than 0")
    if args.fps <= 0:
        parser.error("--fps must be greater than 0")
    if args.region and (args.region[0] < 0 or args.region[1] < 0
                        or args.region[2] < 1 or args.region[3] < 1):
        parser.error("--region requires LEFT/TOP >= 0 and WIDTH/HEIGHT > 0")
    return args


def detect(model, frame, conf, imgsz, class_thresholds=None):
    thresholds = class_thresholds or {}
    return model.detect(
        frame, min([conf, *thresholds.values()]), imgsz,
        class_thresholds=thresholds,
        default_conf=conf,
    )


def main():
    args = parse_args()
    with mss.MSS() as capture:
        if args.list_monitors:
            for index, monitor in enumerate(capture.monitors):
                print(f"{index}: {monitor}")
            return
        if not 1 <= args.monitor < len(capture.monitors):
            raise SystemExit(
                f"--monitor must be between 1 and {len(capture.monitors) - 1}; "
                "use --list-monitors to see available monitors."
            )

        monitor = capture.monitors[args.monitor]
        if args.region:
            left, top, width, height = args.region
            if left + width > monitor["width"] or top + height > monitor["height"]:
                raise SystemExit("--region must fit inside the selected monitor.")
            region = dict(monitor)
            region.update({
                "left": monitor["left"] + left,
                "top": monitor["top"] + top,
                "width": width,
                "height": height,
            })
        else:
            left_offset = monitor["width"] // 2
            region = {
                **monitor,
                "left": monitor["left"] + left_offset,
                "width": monitor["width"] - left_offset,
            }

        if not args.model.is_file():
            raise SystemExit(f"YOLO model file not found: {args.model}")
        detector = WeaponDetector(args.model)
        print(f"Screen detector: YOLO {args.model.name}, device={detector.device}")

        print("Screen detection running. Press q or Esc in the preview to quit.")
        if not args.region:
            print("Capturing the right half of the selected monitor. Use --region "
                  "to choose another area.")
            print("Move the preview outside the capture area to avoid capturing it.")

        window_name = "SAFESIGHT - Screen Detection"
        interval = 1.0 / args.fps
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        screen_area = monitor["width"] * monitor["height"]
        preview_scale = min(
            math.sqrt(screen_area / (2 * region["width"] * region["height"])),
            monitor["width"] / region["width"],
            monitor["height"] / region["height"],
        )
        cv2.resizeWindow(
            window_name,
            max(1, round(region["width"] * preview_scale)),
            max(1, round(region["height"] * preview_scale)),
        )
        screen_capture = LatestScreenCapture(region)
        screen_capture.start()
        tracker = DetectionTracker()
        tracker_lock = threading.Lock()
        detection_error = []

        def detect_loop():
            last_sequence = 0
            while not screen_capture.stopped:
                sequence, frame, captured_at = screen_capture.read(last_sequence)
                if frame is None:
                    return
                last_sequence = sequence
                started = time.perf_counter()
                try:
                    detections = detect(
                        detector, frame, args.conf, args.imgsz,
                        args.class_thresholds,
                    )
                    with tracker_lock:
                        tracker.update(detections, captured_at)
                except Exception as error:
                    detection_error.append(error)
                    screen_capture.stop()
                    return
                screen_capture.wait(
                    max(0.0, interval - (time.perf_counter() - started))
                )

        detection_thread = threading.Thread(target=detect_loop, daemon=True)
        detection_thread.start()
        last_sequence = 0
        last_rendered_at = time.perf_counter()
        try:
            while True:
                started = time.perf_counter()
                last_sequence, frame, _ = screen_capture.read(last_sequence)
                if detection_error:
                    raise RuntimeError("Screen detection failed.") from detection_error[0]
                if frame is None:
                    break
                with tracker_lock:
                    detections = tracker.current()
                elapsed = started - last_rendered_at
                last_rendered_at = started
                output = draw_detections(frame.copy(), detections)
                draw_stamp(
                    output,
                    f"FPS {1 / max(elapsed, 1e-6):.1f}  "
                    f"Objects {len(detections)}  q/Esc: quit",
                )
                cv2.imshow(window_name, output)

                remaining = interval - (time.perf_counter() - started)
                key = cv2.waitKey(max(1, round(max(0, remaining) * 1000))) & 0xFF
                if key in (ord("q"), 27):
                    break
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            screen_capture.stop()
            detection_thread.join()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
