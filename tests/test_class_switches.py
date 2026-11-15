import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from weapon_detection import config
from weapon_detection.storage import db
from weapon_detection.detection.model import WeaponDetector, detect_frame


class ClassSwitchTests(unittest.TestCase):
    def test_switches_persist_and_screen_reads_them(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(config, "DB_PATH", Path(directory) / "test.db"),
        ):
            db.init()
            self.assertIn("knife", db.read_enabled_classes())
            db.set_settings({"knife_enabled": False})
            db._load_settings()
            self.assertFalse(db.get_settings()["knife_enabled"])
            self.assertNotIn("knife", db.read_enabled_classes())
            self.assertIn("pistol", db.read_enabled_classes())
            with self.assertRaises(ValueError):
                db.set_settings({"knife_enabled": "false"})

    def test_disabled_class_cannot_suppress_enabled_class(self):
        detector = WeaponDetector.__new__(WeaponDetector)
        detector._lock = threading.Lock()
        detector._predict = Mock(
            return_value=[
                dict(label="knife", conf=0.99, box=(10, 10, 40, 40)),
                dict(label="pistol", conf=0.9, box=(10, 10, 40, 40)),
            ]
        )
        result = detector.detect(
            np.zeros((50, 50, 3), np.uint8), enabled_classes=["pistol"], cascade=True
        )
        self.assertEqual([item["label"] for item in result], ["pistol"])

    def test_all_disabled_skips_inference(self):
        detector = WeaponDetector.__new__(WeaponDetector)
        detector._predict = Mock()
        self.assertEqual(detector.detect(None, enabled_classes=[]), [])
        detector._predict.assert_not_called()

    def test_shared_pipeline_passes_only_enabled_classes(self):
        detector = Mock()
        settings = dict(config.DEFAULT_SETTINGS, knife_enabled=False)
        detect_frame(detector, None, settings)
        self.assertNotIn("knife", detector.detect.call_args.kwargs["enabled_classes"])
        self.assertIn("pistol", detector.detect.call_args.kwargs["enabled_classes"])


if __name__ == "__main__":
    unittest.main()
