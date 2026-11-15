import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from weapon_detection import config
from weapon_detection.detection import offline
import weapon_detection.web.app as web


class OfflineVideoTests(unittest.TestCase):
    def setUp(self):
        auth_patch = patch.dict(web.app.config, AUTH_REQUIRED=False)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.setting_patch = patch.object(config, "VIDEO_DIR", self.root)
        self.setting_patch.start()
        self.filename = "sample.avi"
        writer = cv2.VideoWriter(
            str(self.root / self.filename), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 64)
        )
        for _ in range(6):
            writer.write(np.zeros((64, 64, 3), np.uint8))
        writer.release()
        self.detector = Mock()
        self.detector.detect.return_value = [dict(label="knife", conf=0.8, box=(10, 10, 30, 30))]
        offline._jobs[self.filename] = {"state": "queued", "progress": 0}

    def tearDown(self):
        offline._read.cache_clear()
        offline._jobs.pop(self.filename, None)
        self.setting_patch.stop()
        self.directory.cleanup()

    def scan(self):
        offline._scan(self.filename, self.detector, dict(config.DEFAULT_SETTINGS))
        self.assertEqual(offline._jobs[self.filename]["state"], "ready")

    def test_every_frame_processed_once_and_cache_reused(self):
        self.scan()
        timeline = offline.load(self.filename)
        self.assertEqual(len(timeline["frames"]), 6)
        self.assertEqual(self.detector.detect.call_count, 6)
        self.assertEqual(timeline["width"], 64)
        times = [item["time"] for item in timeline["frames"]]
        self.assertEqual(times, sorted(set(times)))
        status = offline.ensure(self.filename, self.detector, config.DEFAULT_SETTINGS)
        self.assertEqual(status["state"], "ready")
        self.assertEqual(self.detector.detect.call_count, 6)

    def test_status_does_not_start_processing(self):
        offline._jobs.pop(self.filename, None)
        self.assertEqual(offline.status(self.filename), {"state": "idle", "progress": 0})
        source = dict(id="test", name="Test", type="camera", url="demo:" + self.filename)
        with (
            patch.object(web.db, "get_source", return_value=source),
            patch.object(offline, "ensure") as ensure,
        ):
            response = web.app.test_client().get("/api/sources/test/analysis")
            self.assertEqual(response.get_json()["state"], "idle")
            ensure.assert_not_called()
        self.detector.detect.assert_not_called()

    def test_playback_uses_saved_detections_without_model_calls(self):
        self.scan()
        source = dict(id="test", name="Test", type="camera", url="demo:" + self.filename)
        with (
            patch.object(web.db, "get_source", return_value=source),
            patch.object(
                web.manager, "get_detection_settings", return_value=dict(config.DEFAULT_SETTINGS)
            ),
            patch.object(web.manager, "process_demo_detections") as process,
            patch.object(web, "detector", self.detector),
        ):
            client = web.app.test_client()
            response = client.get("/api/sources/test/analysis?results=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.get_json()["frames"]), 6)
            self.assertNotIn("telegram_token", response.get_json()["settings"])
            response.close()
            response = client.post("/api/sources/test/playback-event", json={"index": 2})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["ok"])
            self.assertEqual(process.call_args.args[2][0]["label"], "knife")
            self.assertEqual(
                client.post("/api/sources/test/playback-event", json={"index": 99}).status_code, 400
            )
        self.assertEqual(self.detector.detect.call_count, 6)

    def test_invalid_video_reports_error_without_partial_cache(self):
        (self.root / self.filename).write_bytes(b"invalid")
        offline._scan(self.filename, self.detector, config.DEFAULT_SETTINGS)
        self.assertEqual(offline._jobs[self.filename]["state"], "error")
        self.assertFalse(offline.cache_path(self.filename).exists())


if __name__ == "__main__":
    unittest.main()
