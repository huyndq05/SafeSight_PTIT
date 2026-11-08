import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from weapon_detection import config
from weapon_detection.detection import model
from weapon_detection.detection.streams import DetectionTracker
from weapon_detection.storage import db
import weapon_detection.web.app as web_app


class WeaponDetectorModelTests(unittest.TestCase):
    def test_loads_yolo_weights_and_applies_class_thresholds(self):
        created = {"predict_calls": []}

        class FakeTensor:
            def detach(self):
                return self

            def cpu(self):
                return self

            def tolist(self):
                return [
                    [10, 20, 30, 40, 0.8, 4],
                    [50, 60, 70, 80, 0.6, 3],
                    [15, 25, 35, 45, 0.7, 1],
                    [11, 21, 31, 41, 0.75, 6],
                ]

        class FakeModel:
            names = dict(enumerate(config.MODEL_CLASSES))

            def predict(self, frame, **kwargs):
                created.setdefault("predict_frames", []).append(frame)
                created["predict_calls"].append(kwargs)
                result = types.SimpleNamespace(
                    names=self.names,
                    boxes=types.SimpleNamespace(data=FakeTensor()),
                )
                return [result]

        class FakeYoloLoader:
            def __init__(self, model_path):
                created["model_path"] = model_path
                self.names = FakeModel.names
                self.model = FakeModel()

            def predict(self, frame, **kwargs):
                return self.model.predict(frame, **kwargs)

        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        fake_ultralytics = types.ModuleType("ultralytics")
        fake_ultralytics.YOLO = FakeYoloLoader

        with patch.dict(sys.modules, {"torch": fake_torch, "ultralytics": fake_ultralytics}):
            detector = model.WeaponDetector(Path("test-ss-final-1.pt"))
            detections = detector.detect(
                np.zeros((100, 120, 3), dtype=np.uint8),
                conf=0.5,
                imgsz=320,
                class_thresholds={
                    "knife": 0.7,
                    "pistol": 0.55,
                    "baseball_bat": 0.65,
                    "rifle": 0.65,
                },
                default_conf=0.5,
            )

        self.assertEqual(created["model_path"], "test-ss-final-1.pt")
        self.assertEqual(detector.names, dict(enumerate(config.MODEL_CLASSES)))
        self.assertEqual(created["predict_calls"][-1]["conf"], 0.5)
        self.assertEqual(created["predict_calls"][-1]["imgsz"], 320)
        self.assertEqual(
            [item["label"] for item in detections],
            ["knife", "baseball_bat", "pistol"],
        )
        self.assertEqual(detections[0]["box"], (10, 20, 30, 40))
        self.assertNotIn("rifle", [item["label"] for item in detections])

    def test_suppresses_nested_cross_class_boxes_for_the_same_object(self):
        detections = model._suppress_cross_class_duplicates([
            {"label": "pistol", "conf": 0.36, "box": (31, 34, 180, 204)},
            {"label": "rifle", "conf": 0.42, "box": (28, 30, 382, 207)},
        ])

        self.assertEqual([item["label"] for item in detections], ["rifle"])


class DetectionTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = DetectionTracker()

    def test_brief_missed_detection_keeps_box_stable_until_ttl(self):
        detection = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}
        self.tracker.update([detection], now=1.0)

        self.assertEqual(self.tracker.update([], now=1.1)[0]["box"], detection["box"])
        self.assertEqual(self.tracker.current(now=1.9)[0]["box"], detection["box"])
        self.assertEqual(self.tracker.current(now=2.51), [])

    def test_box_smoothing_and_prediction_stay_bounded(self):
        first = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}
        moved = {"label": "knife", "conf": 0.9, "box": (110, 10, 140, 40)}
        self.tracker.update([first], now=1.0)

        current = self.tracker.update([moved], now=1.1)

        self.assertEqual(len(current), 1)
        self.assertGreater(current[0]["box"][0], first["box"][0])
        predicted = self.tracker.current(now=2.1)[0]["box"]
        capped_prediction = self.tracker.current(now=2.2)[0]["box"]
        self.assertGreaterEqual(predicted[0], current[0]["box"][0])
        self.assertEqual(capped_prediction, predicted)

    def test_fast_object_motion_stays_on_the_same_track_between_slow_detections(self):
        first = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}
        moved = {"label": "knife", "conf": 0.9, "box": (110, 10, 140, 40)}
        self.tracker.update([first], now=1.0)

        updated = self.tracker.update([moved], now=1.5)
        predicted = self.tracker.current(now=1.75)

        self.assertEqual(len(updated), 1)
        self.assertEqual(len(predicted), 1)
        self.assertGreater(predicted[0]["box"][0], first["box"][0] + 70)

    def test_center_prediction_follows_30_fps_motion_without_changing_box_size(self):
        centers = []
        for index in range(31):
            now = 1.0 + index / 30
            center_x = 100 + index * 12 + (4 if index % 2 else -4)
            detection = {
                "label": "knife", "conf": 0.9,
                "box": (center_x - 15, 80, center_x + 15, 110),
            }
            tracked = self.tracker.update([detection], now=now)
            centers.append((tracked[0]["box"][0] + tracked[0]["box"][2]) / 2)
            self.assertAlmostEqual(tracked[0]["box"][2] - tracked[0]["box"][0], 30, delta=1)

        self.assertGreater(centers[-1] - centers[0], 340)
        self.assertLessEqual(abs(centers[-1] - 456), 6)
        self.assertTrue(all(left < right for left, right in zip(centers, centers[1:])))

    def test_unmatched_same_class_track_survives_brief_detection_gap(self):
        first = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}
        second = {"label": "knife", "conf": 0.9, "box": (200, 10, 230, 40)}
        self.tracker.update([first, second], now=1.0)

        tracked = self.tracker.update([second], now=1.1)

        self.assertEqual(len(tracked), 2)

    def test_single_missed_track_survives_and_resumes(self):
        knife = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}
        rifle = {"label": "rifle", "conf": 0.9, "box": (100, 100, 140, 140)}
        self.tracker.update([knife, rifle], now=1.0)

        one_missed = self.tracker.update([rifle], now=1.1)
        resumed = self.tracker.update([knife, rifle], now=1.2)

        self.assertEqual([item["label"] for item in one_missed], ["knife", "rifle"])
        self.assertEqual([item["label"] for item in resumed], ["knife", "rifle"])

    def test_old_track_is_removed_when_same_class_object_moves_far(self):
        first = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}
        far_away = {"label": "knife", "conf": 0.9, "box": (500, 300, 540, 340)}
        self.tracker.update([first], now=1.0)

        current = self.tracker.update([far_away], now=1.1)

        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["box"], far_away["box"])

    def test_detection_box_border_is_twice_the_previous_default_width(self):
        frame = type("Frame", (), {"shape": (100, 100, 3)})()
        detection = {"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}

        with patch.object(model.cv2, "rectangle") as rectangle, \
                patch.object(model.cv2, "putText"):
            model.draw_detections(frame, [detection])

        self.assertEqual(rectangle.call_args_list[0].args[-1], 4)


class DetectionSettingsMigrationTests(unittest.TestCase):
    def run_migration(self, detect_fps):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "settings.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT)"
                )
                connection.executemany(
                    "INSERT INTO settings VALUES(?, ?)",
                    [
                        ("detection_profile_version", json.dumps(3)),
                        ("detect_fps", json.dumps(detect_fps)),
                        ("conf_threshold", json.dumps(0.73)),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(config, "DB_PATH", db_path):
                db.init()
                return db.get_settings()

    def test_default_fps_is_increased_without_resetting_detection_thresholds(self):
        settings = self.run_migration(30)

        self.assertEqual(settings["detect_fps"], 45)
        self.assertEqual(settings["conf_threshold"], 0.73)

    def test_custom_fps_is_preserved(self):
        settings = self.run_migration(60)

        self.assertEqual(settings["detect_fps"], 60)

    def test_each_model_class_threshold_can_be_saved_and_validated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(config, "DB_PATH", Path(temp_dir) / "settings.db"):
                db.init()
                settings = db.set_settings({
                    "axe_conf_threshold": 0.73,
                    "baseball_bat_conf_threshold": 0.32,
                })

                self.assertEqual(settings["axe_conf_threshold"], 0.73)
                self.assertEqual(settings["baseball_bat_conf_threshold"], 0.32)
                with self.assertRaises(ValueError):
                    db.set_settings({"spear_conf_threshold": 1.1})


class StartupTests(unittest.TestCase):
    def test_missing_model_reports_the_required_weights_path(self):
        missing_model = Path("models") / "missing-ss-final-1.pt"
        with patch.object(web_app.config, "MODEL_PATH", missing_model):
            with self.assertRaisesRegex(FileNotFoundError, "ss_final_1.pt"):
                web_app.main()


if __name__ == "__main__":
    unittest.main()
